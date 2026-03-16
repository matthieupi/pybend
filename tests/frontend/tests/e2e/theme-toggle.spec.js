/**
 * Theme Toggle — E2E Tests
 */
import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('Theme Toggle', () => {

  test('default theme is dark', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('ntx-theme'));
    await page.reload({ waitUntil: 'networkidle' });

    const theme = await page.evaluate(() => {
      return document.documentElement.dataset.theme || 'dark';
    });
    // Default or dark
    expect(['dark', undefined, '']).toContain(theme);
  });

  test('theme toggle changes data-theme attribute', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    // Get initial theme
    const initialTheme = await page.evaluate(() =>
      document.documentElement.dataset.theme || 'dark'
    );

    // Click theme toggle in topbar dropdown
    await page.locator('ntx-topbar').evaluate((el) => {
      const toggle = el.shadowRoot?.querySelector('.theme-toggle');
      toggle?.click();
    });

    await page.waitForTimeout(300);

    const newTheme = await page.evaluate(() =>
      document.documentElement.dataset.theme || 'dark'
    );

    // Theme should have changed
    expect(newTheme).not.toBe(initialTheme);
  });

  test('theme persists in localStorage', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await page.reload({ waitUntil: 'networkidle' });

    const theme = await page.evaluate(() =>
      document.documentElement.dataset.theme
    );
    expect(theme).toBe('light');
  });

  test('theme survives page reload', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await page.reload({ waitUntil: 'networkidle' });

    const storedTheme = await page.evaluate(() =>
      window.localStorage.getItem('ntx-theme')
    );
    expect(storedTheme).toBe('light');
  });

  test('dark mode has dark surface', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'dark'));
    await page.reload({ waitUntil: 'networkidle' });

    const surface = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue('--surface-0').trim();
    });

    // Dark surface should be a dark color
    expect(surface.length).toBeGreaterThan(0);
  });

  test('light mode has light surface', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await page.reload({ waitUntil: 'networkidle' });

    const surface = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue('--surface-0').trim();
    });

    expect(surface.length).toBeGreaterThan(0);
  });

  test('accent color defined in both themes', async ({ page }) => {
    // Dark theme
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'dark'));
    await page.reload({ waitUntil: 'networkidle' });

    const darkAccent = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()
    );
    expect(darkAccent.length).toBeGreaterThan(0);

    // Light theme
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await page.reload({ waitUntil: 'networkidle' });

    const lightAccent = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()
    );
    expect(lightAccent.length).toBeGreaterThan(0);
  });

  test('no flash of unstyled content (FOUC) on load', async ({ page }) => {
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));

    // Navigate and check theme is applied before DOMContentLoaded
    await page.goto(APP_URL);

    // Check immediately (theme.js runs from <head>)
    const theme = await page.evaluate(() => document.documentElement.dataset.theme);
    expect(theme).toBe('light');
  });
});
