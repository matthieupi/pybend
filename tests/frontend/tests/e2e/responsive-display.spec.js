/**
 * Responsive/Adaptive Display — E2E Tests
 */
import { test, expect } from './fixtures/parallel.js';
import { gotoApp, reloadApp, waitForAppReady, waitForUiSettled } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('Responsive Display', () => {

  test('small viewport (360px) renders items', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const list = page.locator('#product-list');
    await expect(list).toBeVisible();

    const itemCount = await list.evaluate((el) => {
      const grid = el.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length : 0;
    });
    expect(itemCount).toBeGreaterThan(0);
  });

  test('medium viewport (600px) renders items', async ({ page }) => {
    await page.setViewportSize({ width: 600, height: 900 });
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const itemCount = await page.locator('#product-list').evaluate((el) => {
      const grid = el.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length : 0;
    });
    expect(itemCount).toBeGreaterThan(0);
  });

  test('large viewport (1200px) renders items', async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 800 });
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const itemCount = await page.locator('#product-list').evaluate((el) => {
      const grid = el.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length : 0;
    });
    expect(itemCount).toBeGreaterThan(0);
  });

  test('detail view renders at 480px viewport', async ({ page }) => {
    await page.setViewportSize({ width: 480, height: 800 });
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const hasContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('detail view renders at 1920px viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const hasContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('list items have data-display attribute', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const displays = await page.locator('#product-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => {
        const card = item.shadowRoot?.querySelector('.card');
        return card?.dataset?.display || '';
      }).filter(Boolean);
    });

    // All items should have a display mode set
    expect(displays.length).toBeGreaterThan(0);
    displays.forEach(d => {
      expect(['xs', 'sm', 'md', 'lg', 'xl']).toContain(d);
    });
  });

  test('viewport change does not cause errors', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await gotoApp(page, APP_URL);


    await waitForAppReady(page);

    // Resize through multiple breakpoints
    await page.setViewportSize({ width: 1200, height: 800 });
    await waitForUiSettled(page);
    await page.setViewportSize({ width: 768, height: 1024 });
    await waitForUiSettled(page);
    await page.setViewportSize({ width: 480, height: 640 });
    await waitForUiSettled(page);
    await page.setViewportSize({ width: 360, height: 640 });
    await waitForUiSettled(page);
    await page.setViewportSize({ width: 1920, height: 1080 });
    await waitForUiSettled(page);

    const realErrors = errors.filter(e => !e.includes('AssertionError'));
    expect(realErrors).toHaveLength(0);
  });

  test('child items have cascaded display mode', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const childDisplays = await page.locator('#product-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => {
        return item.getAttribute('display') || '';
      }).filter(Boolean);
    });

    expect(childDisplays.length).toBeGreaterThan(0);
  });
});
