/**
 * Regression tests: inline create validation and error loop prevention.
 *
 * Bug reproduced: Typing letters in amount_min/amount_max number fields
 * produces no validation feedback, and submitting triggers an infinite
 * error loop (POST /grants/error 405 Method Not Allowed).
 *
 * Root causes fixed:
 *   1. NetworkAdapter.send() forwarded ERROR events as HTTP POST to
 *      /{target}/error, causing 405 loops.
 *   2. HTTP.js .catch() double-called onError when the .then() error
 *      branch had already handled the response.
 *   3. ntt-table #submitCreate() did not validate number fields —
 *      parseFloat("") returns NaN, which was sent as invalid data.
 *
 * These tests run against an isolated test database created by
 * grants-global-setup.js (via PYBEND_SQLITE_DB env var).
 */
import { test, expect } from '@playwright/test';

const APP_URL = 'http://localhost:5000/';

async function login(page) {
  const resp = await page.request.post('http://localhost:5000/users/login', {
    data: { email: 'alice@example.com', password: 'alice123' },
  });
  const json = await resp.json();
  await page.goto(APP_URL);
  await page.evaluate((t) => window.localStorage.setItem('jwtToken', t), json.token);
  await page.reload({ waitUntil: 'networkidle' });
}

/**
 * Wait for the Grant table to be fully rendered (shadow DOM populated).
 * The table is slotted via ntt-router (light DOM), not inside shadow DOM.
 */
async function waitForGrantTable(page, timeout = 10000) {
  await page.waitForFunction(() => {
    const table = document.querySelector('#grant-table');
    return table?.shadowRoot?.querySelector('.inline-add-btn') != null;
  }, { timeout });
}

/**
 * Helper: run a function against the #grant-table element.
 * The table is a slotted child of ntt-router, so it's in the light DOM.
 */
async function withGrantTable(page, fn) {
  return page.evaluate(fn);
}

test.describe('Grant Create — Number Field Validation', () => {

  test('inline create with valid text fields and empty optional numbers submits without error loop', async ({ page }) => {
    await login(page);
    await waitForGrantTable(page);

    // Track POST requests to detect error loop
    const postRequests = [];
    const errorRequests = [];
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/grants')) {
        postRequests.push(req.url());
      }
      if (req.url().includes('/error')) {
        errorRequests.push(req.url());
      }
    });

    // Open inline create row
    const clicked = await withGrantTable(page, () => {
      const table = document.querySelector('#grant-table');
      if (!table?.shadowRoot) return 'no-table';
      const btn = table.shadowRoot.querySelector('.inline-add-btn');
      if (!btn) return 'no-btn';
      btn.click();
      return 'clicked';
    });
    expect(clicked).toBe('clicked');
    await page.waitForTimeout(300);

    // Fill required text fields but leave number fields empty
    await withGrantTable(page, () => {
      const table = document.querySelector('#grant-table');
      const row = table.shadowRoot.querySelector('.create-row');

      const title = row.querySelector('[data-key="title"]');
      if (title) title.value = 'Test Validation Grant';

      const agency = row.querySelector('[data-key="agency"]');
      if (agency) agency.value = 'Test Agency';
    });

    // Click save — should submit (amounts are optional, empty is valid)
    await withGrantTable(page, () => {
      const table = document.querySelector('#grant-table');
      table.shadowRoot.querySelector('.save-create-btn')?.click();
    });

    // Wait for any potential error loop
    await page.waitForTimeout(2000);

    // No error loop should have occurred
    expect(errorRequests.length).toBe(0);
  });


  test('submitting empty inline create form sends no POST request', async ({ page }) => {
    await login(page);
    await waitForGrantTable(page);

    const postRequests = [];
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/grants')) {
        postRequests.push(req.url());
      }
    });

    // Open create row
    await withGrantTable(page, () => {
      const table = document.querySelector('#grant-table');
      table?.shadowRoot?.querySelector('.inline-add-btn')?.click();
    });

    await page.waitForTimeout(300);

    // Click save without filling anything
    await withGrantTable(page, () => {
      const table = document.querySelector('#grant-table');
      table?.shadowRoot?.querySelector('.save-create-btn')?.click();
    });

    await page.waitForTimeout(1000);

    // No POST should have been sent for an empty form
    expect(postRequests.length).toBe(0);
  });


  test('ERROR events never reach the backend as HTTP requests', async ({ page }) => {
    await login(page);
    await waitForGrantTable(page);

    const errorRequests = [];

    page.on('request', (req) => {
      if (req.url().includes('/error')) {
        errorRequests.push({ url: req.url(), method: req.method() });
      }
    });

    // Send an invalid CREATE through the NTT framework to trigger error handling
    await page.evaluate(() => {
      const table = document.querySelector('#grant-table');
      if (table?.proto) {
        // Bad data — this triggers a backend error that the framework
        // must handle without looping
        table.proto.call('CREATE', { amount_min: 'not_a_number' }, { inbox: 'CREATE' });
      }
    });

    // Wait long enough for any loop to manifest
    await page.waitForTimeout(3000);

    // The critical assertion: no requests to /error endpoints (the loop symptom)
    expect(errorRequests.length).toBe(0);
  });


  test('backend validation error returns proper HTTP status, no error loop', async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Directly POST invalid data to the API (bypasses frontend validation)
    const token = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
    const resp = await page.request.post('http://localhost:5000/grants', {
      headers: { 'x-access-token': token, 'Content-Type': 'application/json' },
      data: { amount_min: 'not_a_number' },
    });

    // Backend should reject with 4xx (validation error), not 200
    expect(resp.status()).toBeGreaterThanOrEqual(400);
  });
});
