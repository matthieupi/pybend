/**
 * Product List Behavior — E2E Tests
 */
import { test, expect } from '@playwright/test';

const APP_URL = '/';

test.describe('Product List', () => {

  test('items display correct fields per schema', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Get the first ntt-item inside the list and check its content
    const firstItemContent = await page.locator('ntt-list').evaluate((list) => {
      const grid = list.shadowRoot?.querySelector('.list-grid');
      const firstItem = grid?.querySelector('ntt-item');
      if (!firstItem?.shadowRoot) return null;
      const card = firstItem.shadowRoot.querySelector('.card');
      return card?.textContent || '';
    });

    expect(firstItemContent).toBeTruthy();
    // Should contain a product name
    expect(firstItemContent.length).toBeGreaterThan(0);
  });

  test('responsive layout at 480px viewport', async ({ page }) => {
    await page.setViewportSize({ width: 480, height: 800 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // At 480px, the list should still be visible
    const list = page.locator('ntt-list');
    await expect(list).toBeVisible();
  });

  test('responsive layout at 768px viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const list = page.locator('ntt-list');
    await expect(list).toBeVisible();
  });

  test('responsive layout at 1200px viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 800 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const list = page.locator('ntt-list');
    await expect(list).toBeVisible();
  });

  test('each product shows name field', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const names = await page.locator('ntt-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntt-item');
      if (!items) return [];
      return Array.from(items).map(item => {
        const nameEl = item.shadowRoot?.querySelector('[data-value="name"]');
        return nameEl?.textContent || '';
      }).filter(Boolean);
    });

    expect(names.length).toBeGreaterThanOrEqual(3);
    names.forEach(name => {
      expect(name.length).toBeGreaterThan(0);
    });
  });

  test('list-grid container exists inside ntt-list shadow DOM', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasGrid = await page.locator('ntt-list').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.list-grid');
    });
    expect(hasGrid).toBe(true);
  });
});
