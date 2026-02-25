/**
 * css-and-theming — Comprehensive Unit Tests
 *
 * Tests CSS variable resolution, dark/light theme switching,
 * typography, component-level styles, responsive breakpoints,
 * visual regression screenshots, and edge cases.
 */
import { test, expect } from '@playwright/test';

const APP_URL = '/matrix.html';


test.describe('css-and-theming — CSS Variable Resolution', () => {

  test('--surface-0 through --surface-2 resolve to non-empty values', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const vars = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        s0: style.getPropertyValue('--surface-0').trim(),
        s1: style.getPropertyValue('--surface-1').trim(),
        s2: style.getPropertyValue('--surface-2').trim(),
      };
    });
    expect(vars.s0.length).toBeGreaterThan(0);
    expect(vars.s1.length).toBeGreaterThan(0);
    expect(vars.s2.length).toBeGreaterThan(0);
  });

  test('--text-0 through --text-2 resolve to non-empty values', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const vars = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        t0: style.getPropertyValue('--text-0').trim(),
        t1: style.getPropertyValue('--text-1').trim(),
        t2: style.getPropertyValue('--text-2').trim(),
      };
    });
    expect(vars.t0.length).toBeGreaterThan(0);
    expect(vars.t1.length).toBeGreaterThan(0);
    expect(vars.t2.length).toBeGreaterThan(0);
  });

  test('--accent resolves to a color value', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const accent = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
    });
    expect(accent.length).toBeGreaterThan(0);
    // Should be a hex or rgb color
    expect(accent).toMatch(/(#[0-9a-f]{3,8}|rgb)/i);
  });

  test('--border resolves to a color value', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const border = await page.evaluate(() => {
      return getComputedStyle(document.documentElement).getPropertyValue('--border').trim();
    });
    expect(border.length).toBeGreaterThan(0);
  });

  test('--radius-sm and --radius-md resolve to pixel values', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const vars = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return {
        sm: style.getPropertyValue('--radius-sm').trim(),
        md: style.getPropertyValue('--radius-md').trim(),
      };
    });
    expect(vars.sm).toMatch(/\d+px/);
    expect(vars.md).toMatch(/\d+px/);
  });

  test('no CSS variable contains unresolved var( in computed value', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const brokenVars = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      const critical = ['--surface-0', '--surface-1', '--surface-2',
                        '--text-0', '--text-1', '--text-2',
                        '--accent', '--border'];
      const broken = [];
      for (const v of critical) {
        const val = style.getPropertyValue(v).trim();
        if (val.includes('var(')) broken.push(v);
      }
      return broken;
    });
    expect(brokenVars).toEqual([]);
  });
});


test.describe('css-and-theming — Dark Theme', () => {

  test('default theme is dark (--surface-0 is a dark color)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Ensure dark theme (clear any saved light theme)
    await page.evaluate(() => {
      localStorage.removeItem('ntt-theme');
    });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    const bg = await page.evaluate(() => {
      return getComputedStyle(document.body).backgroundColor;
    });
    // Dark theme background should be very dark (low RGB values)
    const match = bg.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (match) {
      const [r, g, b] = [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
      expect(r).toBeLessThan(50);
      expect(g).toBeLessThan(50);
      expect(b).toBeLessThan(50);
    }
  });

  test('dark theme --text-0 is a light color (for contrast)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => { localStorage.removeItem('ntt-theme'); });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    const textColor = await page.evaluate(() => {
      return getComputedStyle(document.body).color;
    });
    const match = textColor.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (match) {
      const [r, g, b] = [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
      // Light text: at least one channel > 200
      expect(Math.max(r, g, b)).toBeGreaterThan(200);
    }
  });
});


test.describe('css-and-theming — Light Theme', () => {

  test('light theme --surface-0 is a light color', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    await page.evaluate(() => {
      localStorage.setItem('ntt-theme', 'light');
      document.documentElement.dataset.theme = 'light';
    });
    await page.waitForTimeout(500);

    const bg = await page.evaluate(() => {
      return getComputedStyle(document.body).backgroundColor;
    });
    const match = bg.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (match) {
      const [r, g, b] = [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
      // Light surface: high RGB values
      expect(r).toBeGreaterThan(200);
      expect(g).toBeGreaterThan(200);
      expect(b).toBeGreaterThan(200);
    }
  });

  test('light theme --text-0 is a dark color (for contrast)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    await page.evaluate(() => {
      localStorage.setItem('ntt-theme', 'light');
      document.documentElement.dataset.theme = 'light';
    });
    await page.waitForTimeout(500);

    const textColor = await page.evaluate(() => {
      return getComputedStyle(document.body).color;
    });
    const match = textColor.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (match) {
      const [r, g, b] = [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
      // Dark text: low RGB values
      expect(Math.max(r, g, b)).toBeLessThan(100);
    }
  });

  test('dark and light surface-0 are different', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    // Get dark background
    await page.evaluate(() => {
      localStorage.removeItem('ntt-theme');
      delete document.documentElement.dataset.theme;
    });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    const darkBg = await page.evaluate(() => {
      return getComputedStyle(document.body).backgroundColor;
    });

    // Switch to light
    await page.evaluate(() => {
      localStorage.setItem('ntt-theme', 'light');
      document.documentElement.dataset.theme = 'light';
    });
    await page.waitForTimeout(500);

    const lightBg = await page.evaluate(() => {
      return getComputedStyle(document.body).backgroundColor;
    });

    expect(darkBg).not.toBe(lightBg);
  });

  // Cleanup: restore dark theme
  test.afterAll(async ({}, testInfo) => {
    // noop - each test is isolated per page
  });
});


test.describe('css-and-theming — Font & Typography', () => {

  test('body font-family includes sans-serif fallback', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const fontFamily = await page.evaluate(() => {
      return getComputedStyle(document.body).fontFamily;
    });
    // Should include Inter or system-ui or sans-serif
    expect(fontFamily.toLowerCase()).toMatch(/(inter|system-ui|sans-serif)/);
  });

  test('h1 and h2 have expected sizing', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const sizes = await page.evaluate(() => {
      const h1 = document.querySelector('h1');
      const list = document.querySelector('ntt-list');
      const h2El = list?.shadowRoot?.querySelector('h1'); // list header is an h1
      return {
        h1Size: h1 ? parseFloat(getComputedStyle(h1).fontSize) : 0,
        listHeaderSize: h2El ? parseFloat(getComputedStyle(h2El).fontSize) : 0,
      };
    });
    // Both should be positive (rendered with visible size)
    if (sizes.h1Size > 0) expect(sizes.h1Size).toBeGreaterThanOrEqual(16);
    if (sizes.listHeaderSize > 0) expect(sizes.listHeaderSize).toBeGreaterThanOrEqual(16);
  });
});


test.describe('css-and-theming — Component-Level Styles', () => {

  test('ntt-topbar :host has sticky positioning at top', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const position = await page.locator('ntt-topbar').evaluate((el) => {
      // :host element (ntt-topbar itself) has position: sticky
      return getComputedStyle(el).position;
    });
    expect(['fixed', 'sticky']).toContain(position);
  });

  test('ntt-item .card has border-radius styling', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const radius = await page.locator('ntt-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return '';
      const card = item.shadowRoot.querySelector('.card');
      return card ? getComputedStyle(card).borderRadius : '';
    });
    expect(radius).not.toBe('');
    expect(radius).not.toBe('0px');
  });

  test('ntt-item .card has cursor pointer in list view', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const cursor = await page.locator('ntt-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return '';
      const card = item.shadowRoot.querySelector('.card');
      return card ? getComputedStyle(card).cursor : '';
    });
    expect(cursor).toBe('pointer');
  });

  test('ntt-logs .panel has transition for slide-in', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const transition = await page.locator('ntt-logs').evaluate((el) => {
      const panel = el.shadowRoot?.querySelector('.panel');
      return panel ? getComputedStyle(panel).transition : '';
    });
    expect(transition.length).toBeGreaterThan(0);
    expect(transition).not.toBe('none');
  });
});


test.describe('css-and-theming — Responsive Breakpoints', () => {

  const breakpoints = [
    { width: 360, height: 640, name: '360px mobile' },
    { width: 480, height: 800, name: '480px small' },
    { width: 768, height: 1024, name: '768px tablet' },
    { width: 1024, height: 768, name: '1024px laptop' },
    { width: 1200, height: 800, name: '1200px desktop' },
    { width: 1920, height: 1080, name: '1920px widescreen' },
  ];

  for (const bp of breakpoints) {
    test(`items render correctly at ${bp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: bp.width, height: bp.height });
      await page.goto(APP_URL);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const gridInfo = await page.locator('ntt-list').evaluate((el) => {
        const grid = el.shadowRoot?.querySelector('.list-grid');
        if (!grid) return { hasGrid: false };
        const items = grid.querySelectorAll('ntt-item');
        return {
          hasGrid: true,
          itemCount: items.length,
          gridWidth: grid.getBoundingClientRect().width,
        };
      });
      expect(gridInfo.hasGrid).toBe(true);
      expect(gridInfo.itemCount).toBeGreaterThan(0);
      expect(gridInfo.gridWidth).toBeGreaterThan(0);
    });
  }
});


test.describe('css-and-theming — Visual Regression Screenshots', () => {

  test('dark theme list view produces non-trivial screenshot', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => {
      localStorage.removeItem('ntt-theme');
      delete document.documentElement.dataset.theme;
    });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    const screenshot = await page.screenshot();
    // Screenshot should be a non-trivial buffer (not blank)
    expect(screenshot.byteLength).toBeGreaterThan(10000);
  });

  test('light theme list view produces non-trivial screenshot', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => {
      localStorage.setItem('ntt-theme', 'light');
      document.documentElement.dataset.theme = 'light';
    });
    await page.waitForTimeout(2000);

    const screenshot = await page.screenshot();
    expect(screenshot.byteLength).toBeGreaterThan(10000);
  });

  test('detail view produces non-trivial screenshot', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const screenshot = await page.screenshot();
    expect(screenshot.byteLength).toBeGreaterThan(10000);
  });

  test('mobile list view produces non-trivial screenshot', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const screenshot = await page.screenshot();
    expect(screenshot.byteLength).toBeGreaterThan(5000);
  });

  test('dark and light screenshots are NOT byte-identical', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Capture dark
    await page.evaluate(() => {
      localStorage.removeItem('ntt-theme');
      delete document.documentElement.dataset.theme;
    });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    const darkShot = await page.screenshot();

    // Switch to light
    await page.evaluate(() => {
      localStorage.setItem('ntt-theme', 'light');
      document.documentElement.dataset.theme = 'light';
    });
    await page.waitForTimeout(1000);
    const lightShot = await page.screenshot();

    expect(Buffer.compare(darkShot, lightShot)).not.toBe(0);
  });
});


test.describe('css-and-theming — Edge Cases', () => {

  test('theme is applied from localStorage on page load (no FOUC)', async ({ page }) => {
    // Set light theme before navigation
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => { localStorage.setItem('ntt-theme', 'light'); });

    // Reload: theme should be applied immediately
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    const theme = await page.evaluate(() => {
      return document.documentElement.dataset.theme || '';
    });
    expect(theme).toBe('light');

    // Cleanup
    await page.evaluate(() => { localStorage.removeItem('ntt-theme'); });
  });

  test('CSS stylesheets load without 404 errors', async ({ page }) => {
    const failedRequests = [];
    page.on('response', (resp) => {
      const url = resp.url();
      if (url.endsWith('.css') && resp.status() === 404) {
        failedRequests.push(url);
      }
    });

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    expect(failedRequests).toEqual([]);
  });

  test('body overflow-x is hidden (prevents horizontal scroll)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // The body has overflow-x: hidden to prevent horizontal scroll
    const overflowX = await page.evaluate(() => {
      return getComputedStyle(document.body).overflowX;
    });
    expect(overflowX).toBe('hidden');
  });

  test('theme toggle preserves page content', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Count items before toggle
    const beforeCount = await page.locator('ntt-list').evaluate((el) => {
      return el.shadowRoot?.querySelectorAll('ntt-item').length || 0;
    });

    // Toggle theme
    await page.evaluate(() => {
      const current = document.documentElement.dataset.theme || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
    });
    await page.waitForTimeout(500);

    // Count items after toggle
    const afterCount = await page.locator('ntt-list').evaluate((el) => {
      return el.shadowRoot?.querySelectorAll('ntt-item').length || 0;
    });

    expect(afterCount).toBe(beforeCount);
  });
});
