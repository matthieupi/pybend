/**
 * ntx-logs — Browser-only style/layout contracts.
 *
 * Component behavior is covered in Vitest (`tests/components/ntx-logs.test.js`)
 * and basic browser integration is covered in `logs-panel.spec.js`.
 */
import { test, expect } from './fixtures/parallel.js';
import { gotoApp, waitForAppReady } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('ntx-logs — Browser Layout', () => {
  test('closed panel uses browser-computed slide transform', async ({ page }) => {
    await gotoApp(page, APP_URL);
    await waitForAppReady(page);

    const transform = await page.locator('ntx-logs').evaluate((el) => {
      const panel = el.shadowRoot?.querySelector('.panel');
      return panel ? getComputedStyle(panel).transform : '';
    });

    expect(transform).not.toBe('none');
  });

  test('component remains mounted at mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await gotoApp(page, APP_URL);
    await waitForAppReady(page);

    const hasToggle = await page.locator('ntx-logs').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.toggle');
    });

    expect(hasToggle).toBe(true);
  });

  test('host and toggle keep fixed floating chrome', async ({ page }) => {
    await gotoApp(page, APP_URL);
    await waitForAppReady(page);

    const style = await page.locator('ntx-logs').evaluate((el) => {
      const toggle = el.shadowRoot?.querySelector('.toggle');
      return {
        position: getComputedStyle(el).position,
        toggleRadius: toggle ? getComputedStyle(toggle).borderRadius : '',
      };
    });

    expect(style.position).toBe('fixed');
    expect(style.toggleRadius).toBe('50%');
  });
});
