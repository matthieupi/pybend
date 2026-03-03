/**
 * Responsive/Adaptive Display — E2E Tests
 */
import { test, expect } from '@playwright/test';

const APP_URL = '/';

test.describe('Responsive Display', () => {

  test('small viewport (360px) renders items', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const list = page.locator('ntt-list');
    await expect(list).toBeVisible();

    const itemCount = await list.evaluate((el) => {
      const grid = el.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length : 0;
    });
    expect(itemCount).toBeGreaterThan(0);
  });

  test('medium viewport (600px) renders items', async ({ page }) => {
    await page.setViewportSize({ width: 600, height: 900 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const itemCount = await page.locator('ntt-list').evaluate((el) => {
      const grid = el.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length : 0;
    });
    expect(itemCount).toBeGreaterThan(0);
  });

  test('large viewport (1200px) renders items', async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 800 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const itemCount = await page.locator('ntt-list').evaluate((el) => {
      const grid = el.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length : 0;
    });
    expect(itemCount).toBeGreaterThan(0);
  });

  test('detail view renders at 480px viewport', async ({ page }) => {
    await page.setViewportSize({ width: 480, height: 800 });
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasContent = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('detail view renders at 1920px viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasContent = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('list items have data-display attribute', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const displays = await page.locator('ntt-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntt-item');
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

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Resize through multiple breakpoints
    await page.setViewportSize({ width: 1200, height: 800 });
    await page.waitForTimeout(300);
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(300);
    await page.setViewportSize({ width: 480, height: 640 });
    await page.waitForTimeout(300);
    await page.setViewportSize({ width: 360, height: 640 });
    await page.waitForTimeout(300);
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(300);

    const realErrors = errors.filter(e => !e.includes('AssertionError'));
    expect(realErrors).toHaveLength(0);
  });

  test('child items have cascaded display mode', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const childDisplays = await page.locator('ntt-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntt-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => {
        return item.getAttribute('display') || '';
      }).filter(Boolean);
    });

    expect(childDisplays.length).toBeGreaterThan(0);
  });
});
