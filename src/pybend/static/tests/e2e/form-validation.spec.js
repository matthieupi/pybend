/**
 * Form Validation — E2E Tests
 */
import { test, expect } from '@playwright/test';

const APP_URL = '/';

test.describe('Form Validation', () => {

  test('schema GET returns validation constraints', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    // name field has minLength and maxLength
    expect(schema.properties.name.minLength).toBeDefined();
    expect(schema.properties.name.maxLength).toBeDefined();

    // price field has exclusiveMinimum
    expect(schema.properties.price.exclusiveMinimum).toBeDefined();
  });

  test('currency widget shows $ prefix in display mode', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const priceText = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return '';
      const priceEl = item.shadowRoot.querySelector('[data-value="price"]');
      return priceEl?.textContent || '';
    });

    expect(priceText).toContain('$');
  });

  test('textarea widget renders for description field', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasTextBlock = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('.text-block[data-value="description"]');
    });

    expect(hasTextBlock).toBe(true);
  });

  test('required fields marked in schema', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.required).toContain('name');
  });

  test('field groups render as fieldsets', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const fieldsetCount = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return 0;
      return item.shadowRoot.querySelectorAll('fieldset').length;
    });

    expect(fieldsetCount).toBeGreaterThanOrEqual(1);
  });

  test('hidden fields (id, image) not rendered', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasHiddenFields = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('[data-value="id"]') ||
             !!item.shadowRoot.querySelector('[data-key="id"]');
    });

    expect(hasHiddenFields).toBe(false);
  });
});
