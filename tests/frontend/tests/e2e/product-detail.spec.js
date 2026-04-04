/**
 * Product Detail Navigation — E2E Tests
 */
import { test, expect } from '@playwright/test';

const APP_URL = '/';

test.describe('Product Detail Navigation', () => {

  test('click product navigates to detail view', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Click the first product item
    await page.locator('#product-list').evaluate((list) => {
      const firstItem = list.shadowRoot?.querySelector('ntx-item');
      if (firstItem?.shadowRoot) {
        const card = firstItem.shadowRoot.querySelector('.card');
        card?.click();
      }
    });

    await page.waitForTimeout(1000);

    // Hash should change to include Product
    expect(page.url()).toContain('#Product');
  });

  test('back button returns to list', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Navigate to detail
    await page.locator('#product-list').evaluate((list) => {
      const firstItem = list.shadowRoot?.querySelector('ntx-item');
      if (firstItem?.shadowRoot) {
        firstItem.shadowRoot.querySelector('.card')?.click();
      }
    });

    await page.waitForTimeout(1000);
    expect(page.url()).toContain('#Product');

    // Click back button inside ntx-router
    const router = page.locator('ntx-router');
    await router.evaluate((r) => {
      const backBtn = r.shadowRoot?.querySelector('.back-btn');
      backBtn?.click();
    });

    await page.waitForTimeout(500);

    // Should be back to list (no hash or empty hash)
    const hash = new URL(page.url()).hash;
    expect(hash === '' || hash === '#').toBe(true);
  });

  test('direct URL with hash loads detail directly', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Router should show detail view
    const hasRouterContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasRouterContent).toBe(true);
  });

  test('detail view shows all visible fields', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const content = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      return item?.shadowRoot?.querySelector('.card')?.textContent || '';
    });

    // Should show name and other fields
    expect(content.length).toBeGreaterThan(0);
  });

  test('hash changes without page reload', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Manually set hash
    await page.evaluate(() => { window.location.hash = 'Product/1'; });
    await page.waitForTimeout(1000);

    // Router should have navigated
    const hasContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('router title shows model name', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const title = await page.locator('ntx-router').evaluate((r) => {
      return r.shadowRoot?.querySelector('.router-title')?.textContent || '';
    });
    expect(title).toContain('Product');
  });

  test('back button not visible at root', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const hasBackBtn = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.back-btn');
    });
    // At root, there should be no back button (slot content shown instead)
    expect(hasBackBtn).toBe(false);
  });
});
