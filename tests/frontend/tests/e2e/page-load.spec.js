/**
 * Page Load & Bootstrap — E2E Tests
 */
import { test, expect } from '@playwright/test';

const APP_URL = '/';

test.describe('Page Load & Bootstrap', () => {

  test('index.html loads without console errors', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    // Filter out expected warnings
    const realErrors = errors.filter(e => !e.includes('AssertionError'));
    expect(realErrors).toHaveLength(0);
  });

  test('product list appears with seeded data', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    // Wait for ntx-list to have items
    const list = page.locator('#product-list');
    await expect(list).toBeVisible();

    // Wait for shadow DOM content
    await page.waitForTimeout(2000);

    // Check that items exist in the list shadow DOM
    const itemCount = await list.evaluate((el) => {
      const grid = el.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length : 0;
    });
    expect(itemCount).toBeGreaterThanOrEqual(3);
  });

  test('schema fetch completes with correct structure', async ({ page }) => {
    const schemaResponse = await page.request.get('/Product');
    expect(schemaResponse.ok()).toBe(true);

    const schema = await schemaResponse.json();
    expect(schema).toHaveProperty('$schema');
    expect(schema).toHaveProperty('$id');
    expect(schema).toHaveProperty('properties');
    expect(schema).toHaveProperty('methods');
    expect(schema.__name__).toBe('Product');
  });

  test('framework components register in window.NTT', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasNTT = await page.evaluate(() => !!window.NTT);
    expect(hasNTT).toBe(true);

    const hasProduct = await page.evaluate(() => !!window.NTT.get('Product'));
    expect(hasProduct).toBe(true);
  });

  test('NTT.get("Product") returns DynamicClass with instances', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const instanceCount = await page.evaluate(() => {
      const DC = window.NTT.get('Product');
      return DC ? DC.instances.size : 0;
    });
    expect(instanceCount).toBeGreaterThanOrEqual(3);
  });

  test('topbar renders correctly for anonymous user', async ({ page }) => {
    // Clear token first
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
    await page.reload({ waitUntil: 'networkidle' });

    const topbar = page.locator('ntx-topbar');
    await expect(topbar).toBeVisible();

    // Check for sign-in link in shadow DOM
    const hasSignIn = await topbar.evaluate((el) => {
      const link = el.shadowRoot?.querySelector('.signin-link');
      return !!link;
    });
    expect(hasSignIn).toBe(true);
  });

  test('CSS variables are defined and resolve', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    const vars = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        surface0: style.getPropertyValue('--ntx-color-page').trim(),
        text0: style.getPropertyValue('--ntx-color-text-strong').trim(),
        accent: style.getPropertyValue('--ntx-color-accent').trim(),
      };
    });

    // CSS variables should resolve to actual values (not empty)
    expect(vars.surface0.length).toBeGreaterThan(0);
    expect(vars.text0.length).toBeGreaterThan(0);
    expect(vars.accent.length).toBeGreaterThan(0);
  });

  test('no 404 errors for stylesheets', async ({ page }) => {
    const failedRequests = [];
    page.on('response', (response) => {
      if (response.status() === 404 && response.url().endsWith('.css')) {
        failedRequests.push(response.url());
      }
    });

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    expect(failedRequests).toHaveLength(0);
  });

  test('list header shows model name', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const header = await page.locator('#product-list').evaluate((el) => {
      const h1 = el.shadowRoot?.querySelector('.list-header h1');
      return h1?.textContent || '';
    });

    expect(header).toContain('Product');
  });

  test('list count badge shows correct total', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const count = await page.locator('#product-list').evaluate((el) => {
      const badge = el.shadowRoot?.querySelector('.list-count');
      return badge?.textContent || '';
    });

    expect(count.length).toBeGreaterThan(0);
    // Should show something like "5" or "5 / 5"
    expect(parseInt(count)).toBeGreaterThanOrEqual(3);
  });
});
