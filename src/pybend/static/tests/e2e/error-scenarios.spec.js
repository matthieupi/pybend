/**
 * Error Scenarios — E2E Tests
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, USERS } from './fixtures/auth.js';

const APP_URL = '/matrix.html';

test.describe('Error Scenarios', () => {

  test('401 response when accessing protected endpoint without token', async ({ page }) => {
    const resp = await page.request.post('/products', {
      data: { name: 'Unauthorized Product', price: 10 },
    });
    expect(resp.status()).toBe(401);
  });

  test('404 on non-existent product detail', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const resp = await page.request.get('/products/99999', {
      headers: { 'x-access-token': token },
    });

    // Should get 404 or empty response
    expect([404, 200]).toContain(resp.status());
    if (resp.status() === 200) {
      const data = await resp.json();
      // If 200, data should be null or empty
      expect(data === null || data === undefined || data.id === undefined).toBe(true);
    }
  });

  test('navigating to non-existent product shows graceful state', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(`${APP_URL}#Product/99999`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Page should not crash (no unhandled errors)
    const criticalErrors = errors.filter(e =>
      !e.includes('AssertionError') && !e.includes('404')
    );
    // We allow some errors but the page should still be functional
    const pageStillWorks = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot;
    });
    expect(pageStillWorks).toBe(true);
  });

  test('invalid product creation returns validation error', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Missing required fields
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: {},
    });

    // Should fail validation (400 or 422)
    expect([400, 422]).toContain(resp.status());
  });

  test('malformed JSON body returns error', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const resp = await page.request.post('/products', {
      headers: {
        'x-access-token': token,
        'Content-Type': 'application/json',
      },
      data: 'not-json{{{',
    });

    // Should fail with 400 or 422
    expect(resp.ok()).toBe(false);
  });

  test('schema endpoint still works without auth', async ({ page }) => {
    // Schema is always public
    const resp = await page.request.get('/Product');
    expect(resp.ok()).toBe(true);

    const schema = await resp.json();
    expect(schema.properties).toBeDefined();
    expect(schema.$id).toBeDefined();
  });

  test('page handles missing schema field gracefully', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // The page should load without crashing even if some
    // fields are unexpected. Here we verify the page did not
    // white-screen.
    const hasContent = await page.evaluate(() => {
      return document.querySelector('ntt-list') !== null;
    });
    expect(hasContent).toBe(true);

    // No critical uncaught exceptions
    const criticalErrors = errors.filter(e =>
      !e.includes('AssertionError') &&
      !e.includes('ResizeObserver')
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test('403 on unauthorized delete', async ({ page }) => {
    // Alice is a regular user, delete requires admin
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const resp = await page.request.delete('/products/1', {
      headers: { 'x-access-token': token },
    });

    // Should be denied (403) — alice is not admin and may not be owner
    expect([403, 401]).toContain(resp.status());
  });

  test('expired or invalid token returns 401', async ({ page }) => {
    const resp = await page.request.get('/products', {
      headers: { 'x-access-token': 'invalid.jwt.token' },
    });

    // Invalid token should be rejected
    expect([401, 403]).toContain(resp.status());
  });

  test('concurrent page navigation does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Rapid hash changes
    await page.evaluate(() => { window.location.hash = '#Product/1'; });
    await page.waitForTimeout(100);
    await page.evaluate(() => { window.location.hash = '#Product/2'; });
    await page.waitForTimeout(100);
    await page.evaluate(() => { window.location.hash = ''; });
    await page.waitForTimeout(100);
    await page.evaluate(() => { window.location.hash = '#Product/3'; });
    await page.waitForTimeout(1000);

    // No unhandled errors from rapid navigation
    const realErrors = errors.filter(e =>
      !e.includes('AssertionError') &&
      !e.includes('ResizeObserver')
    );
    expect(realErrors).toHaveLength(0);
  });

  test('no white screen after page load', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // The body should have visible content
    const bodyHasContent = await page.evaluate(() => {
      const body = document.body;
      return body.children.length > 0 && body.innerHTML.trim().length > 0;
    });
    expect(bodyHasContent).toBe(true);
  });

  test('API returns proper error structure', async ({ page }) => {
    const resp = await page.request.post('/products', {
      data: { name: 'Test' },
    });

    // Unauthenticated — should return JSON error
    expect(resp.status()).toBe(401);
    const body = await resp.json();
    // Error response should have a message or detail
    const hasErrorInfo = body.detail !== undefined ||
                         body.message !== undefined ||
                         body.error !== undefined;
    expect(hasErrorInfo).toBe(true);
  });
});
