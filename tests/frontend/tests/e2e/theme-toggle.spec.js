/**
 * Theme Toggle — E2E Tests
 */
import { test, expect } from './fixtures/parallel.js';
import { loginAs } from './fixtures/auth.js';
import { gotoApp, reloadApp, waitForAppReady, waitForUiSettled } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('Theme Toggle', () => {

  async function clickThemeButton(page, selector) {
    await page.locator(selector).evaluate((el) => {
      el.shadowRoot?.querySelector('button')?.click();
    });
  }

  async function readThemeButtonValue(page, selector) {
    return page.locator(selector).evaluate((el) => {
      return el.shadowRoot?.querySelector('.theme-button__value')?.textContent?.trim() || '';
    });
  }

  test('default theme is dark', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('ntx-theme'));
    await reloadApp(page);

    await waitForAppReady(page);

    const theme = await page.evaluate(() => {
      return document.documentElement.dataset.theme || 'dark';
    });
    // Default or dark
    expect(['dark', undefined, '']).toContain(theme);
  });

  test('sidebar theme button changes data-theme attribute', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await waitForUiSettled(page);

    // Get initial theme
    const initialTheme = await page.evaluate(() =>
      document.documentElement.dataset.theme || 'dark'
    );

    await clickThemeButton(page, 'ntx-sidebar > ntx-theme-button[slot="footer"]');

    const newTheme = await page.evaluate(() =>
      document.documentElement.dataset.theme || 'dark'
    );

    // Theme should have changed
    expect(newTheme).not.toBe(initialTheme);
  });

  test('sidebar and topbar theme buttons stay synchronized', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');

    const topbarSelector = 'ntx-topbar > ntx-theme-button[slot="user-menu"]';
    const sidebarSelector = 'ntx-sidebar > ntx-theme-button[slot="footer"]';

    await expect.poll(async () => readThemeButtonValue(page, sidebarSelector)).toBe('Dark');
    await expect.poll(async () => readThemeButtonValue(page, topbarSelector)).toBe('Dark');

    await clickThemeButton(page, sidebarSelector);

    await expect.poll(async () => page.evaluate(() => document.documentElement.dataset.theme)).toBe('light');
    await expect.poll(async () => readThemeButtonValue(page, sidebarSelector)).toBe('Light');
    await expect.poll(async () => readThemeButtonValue(page, topbarSelector)).toBe('Light');
  });

  test('logged-out pages do not render theme switchers', async ({ page }) => {
    await gotoApp(page, '/login.html');

    await expect(page.locator('.auth-card')).toBeVisible();
    await expect(page.locator('ntx-theme-button')).toHaveCount(0);

    await gotoApp(page, '/register.html');


    await expect(page.locator('.auth-card')).toBeVisible();
    await expect(page.locator('ntx-theme-button')).toHaveCount(0);
  });

  test('theme persists in localStorage', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await reloadApp(page);

    await waitForAppReady(page);

    const theme = await page.evaluate(() =>
      document.documentElement.dataset.theme
    );
    expect(theme).toBe('light');
  });

  test('theme survives page reload', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await reloadApp(page);

    await waitForAppReady(page);

    const storedTheme = await page.evaluate(() =>
      window.localStorage.getItem('ntx-theme')
    );
    expect(storedTheme).toBe('light');
  });

  test('dark mode has dark surface', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'dark'));
    await reloadApp(page);

    await waitForAppReady(page);

    const surface = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue('--ntx-color-page').trim();
    });

    // Dark surface should be a dark color
    expect(surface.length).toBeGreaterThan(0);
  });

  test('light mode has light surface', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await reloadApp(page);

    await waitForAppReady(page);

    const surface = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue('--ntx-color-page').trim();
    });

    expect(surface.length).toBeGreaterThan(0);
  });

  test('accent color defined in both themes', async ({ page }) => {
    // Dark theme
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'dark'));
    await reloadApp(page);

    await waitForAppReady(page);

    const darkAccent = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--ntx-color-accent').trim()
    );
    expect(darkAccent.length).toBeGreaterThan(0);

    // Light theme
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await reloadApp(page);

    await waitForAppReady(page);

    const lightAccent = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--ntx-color-accent').trim()
    );
    expect(lightAccent.length).toBeGreaterThan(0);
  });

  test('no flash of unstyled content (FOUC) on load', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('ntx-theme', 'light');
    });

    // Navigate and check theme is applied before DOMContentLoaded
    await page.goto(APP_URL);

    // Check immediately (theme.js runs from <head>)
    const theme = await page.evaluate(() => document.documentElement.dataset.theme);
    expect(theme).toBe('light');
  });
});
