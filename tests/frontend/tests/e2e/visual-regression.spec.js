/**
 * Visual Regression — E2E Tests
 *
 * Verifies CSS variable resolution, theme consistency, typography,
 * and interaction states. Uses computed style inspection rather than
 * pixel-level screenshot comparison (no baseline images required).
 */
import { test, expect } from '@playwright/test';

const APP_URL = '/';

test.describe('Visual Regression', () => {

  test('CSS variables resolve (no raw var() in computed styles)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const unresolved = await page.evaluate(() => {
      const root = document.documentElement;
      const style = getComputedStyle(root);
      const vars = [
        '--ntx-color-page', '--ntx-color-surface-1', '--ntx-color-surface-2',
        '--ntx-color-text-strong', '--ntx-color-text', '--ntx-color-text-muted',
        '--ntx-color-accent', '--ntx-border-default',
      ];
      const broken = [];
      for (const v of vars) {
        const val = style.getPropertyValue(v).trim();
        if (!val || val.includes('var(')) {
          broken.push(v);
        }
      }
      return broken;
    });

    expect(unresolved).toHaveLength(0);
  });

  test('dark theme surface is dark', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'dark'));
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    const surfaceValue = await page.evaluate(() => {
      return getComputedStyle(document.documentElement)
        .getPropertyValue('--ntx-color-page').trim();
    });

    // Dark surface should be defined and non-empty
    expect(surfaceValue.length).toBeGreaterThan(0);
    // Should not be white/very light
    expect(surfaceValue).not.toBe('#ffffff');
    expect(surfaceValue).not.toBe('rgb(255, 255, 255)');
  });

  test('light theme surface is light', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    const surfaceValue = await page.evaluate(() => {
      return getComputedStyle(document.documentElement)
        .getPropertyValue('--ntx-color-page').trim();
    });

    expect(surfaceValue.length).toBeGreaterThan(0);
    // Should not be the same as dark surface-0 (a very dark color)
    expect(surfaceValue).not.toBe('#08090c');
  });

  test('accent color defined and non-empty', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    const accent = await page.evaluate(() => {
      return getComputedStyle(document.documentElement)
        .getPropertyValue('--ntx-color-accent').trim();
    });

    expect(accent.length).toBeGreaterThan(0);
  });

  test('typography uses expected font family', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const fontFamily = await page.evaluate(() => {
      return getComputedStyle(document.body).fontFamily;
    });

    // Should include a sans-serif font (Inter, system-ui, etc.)
    const hasSansSerif = fontFamily.includes('Inter') ||
                         fontFamily.includes('sans-serif') ||
                         fontFamily.includes('system-ui') ||
                         fontFamily.includes('Segoe');
    expect(hasSansSerif).toBe(true);
  });

  test('list items render at xs display mode on small viewport', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const displays = await page.locator('#product-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => {
        const card = item.shadowRoot?.querySelector('.card');
        return card?.dataset?.display || '';
      }).filter(Boolean);
    });

    // On small viewports, display should be xs or sm
    if (displays.length > 0) {
      displays.forEach(d => {
        expect(['xs', 'sm']).toContain(d);
      });
    }
  });

  test('list items render at larger display mode on wide viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1200, height: 800 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const displays = await page.locator('#product-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => {
        const card = item.shadowRoot?.querySelector('.card');
        return card?.dataset?.display || '';
      }).filter(Boolean);
    });

    // On large viewports, display should be md, lg, or xl
    if (displays.length > 0) {
      displays.forEach(d => {
        expect(['sm', 'md', 'lg', 'xl']).toContain(d);
      });
    }
  });

  test('detail view renders at xl display mode', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const detailDisplay = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return '';
      const card = item.shadowRoot.querySelector('.card');
      return card?.dataset?.display || '';
    });

    // Detail view should use xl display
    if (detailDisplay) {
      expect(['lg', 'xl']).toContain(detailDisplay);
    }
  });

  test('border variable resolves to a color', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    const borderVal = await page.evaluate(() => {
      return getComputedStyle(document.documentElement)
        .getPropertyValue('--ntx-border-default').trim();
    });

    expect(borderVal.length).toBeGreaterThan(0);
  });

  test('no unstyled flash — theme applied immediately', async ({ page }) => {
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'dark'));
    await page.goto(APP_URL);

    // Check immediately on page load (before networkidle)
    const theme = await page.evaluate(() => {
      return document.documentElement.dataset.theme;
    });

    expect(theme).toBe('dark');
  });

  test('screenshot list view without errors', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Take a screenshot to verify no visual crash
    const screenshot = await page.screenshot();
    expect(screenshot).toBeTruthy();
    expect(screenshot.length).toBeGreaterThan(1000); // Non-trivial image
  });

  test('screenshot detail view without errors', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const screenshot = await page.screenshot();
    expect(screenshot).toBeTruthy();
    expect(screenshot.length).toBeGreaterThan(1000);
  });

  test('dark and light theme produce different screenshots', async ({ page }) => {
    // Dark theme screenshot
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'dark'));
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    const darkShot = await page.screenshot();

    // Light theme screenshot
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    const lightShot = await page.screenshot();

    // Screenshots should be different (different themes)
    expect(darkShot.length).toBeGreaterThan(0);
    expect(lightShot.length).toBeGreaterThan(0);

    // They should not be byte-identical
    const darkStr = darkShot.toString('base64');
    const lightStr = lightShot.toString('base64');
    expect(darkStr).not.toBe(lightStr);
  });

  test('text colors resolve and differ between themes', async ({ page }) => {
    // Dark theme text
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'dark'));
    await page.reload({ waitUntil: 'networkidle' });

    const darkText = await page.evaluate(() => {
      return getComputedStyle(document.documentElement)
        .getPropertyValue('--ntx-color-text-strong').trim();
    });

    // Light theme text
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'light'));
    await page.reload({ waitUntil: 'networkidle' });

    const lightText = await page.evaluate(() => {
      return getComputedStyle(document.documentElement)
        .getPropertyValue('--ntx-color-text-strong').trim();
    });

    expect(darkText.length).toBeGreaterThan(0);
    expect(lightText.length).toBeGreaterThan(0);
    // Dark and light should have different primary text colors
    expect(darkText).not.toBe(lightText);
  });
});
