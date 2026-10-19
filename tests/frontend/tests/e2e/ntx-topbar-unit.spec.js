/**
 * ntx-topbar — Comprehensive Unit Tests
 *
 * Tests the topbar component's rendering, user pill, dropdown,
 * logout flow, theme toggle, and edge cases in isolation.
 *
 * NOTE: Some basic topbar tests exist in page-load.spec.js and
 * authentication.spec.js. This file covers deeper component behavior
 * and edge cases that those files do not.
 */
import { test, expect } from './fixtures/parallel.js';
import { loginAs } from './fixtures/auth.js';
import { gotoApp, reloadApp, waitForAppReady, waitForUiSettled } from './fixtures/ui.js';

const APP_URL = '/';

/** Helper: go to app and login */
async function gotoAuthenticated(page, user = 'alice') {
  await page.goto(APP_URL);
  await loginAs(page, user);
  await waitForAppReady(page);
}

test.describe('ntx-topbar — Dropdown Visibility', () => {

  test('dropdown is initially hidden (opacity 0, visibility hidden)', async ({ page }) => {
    await gotoAuthenticated(page, 'alice');

    const vis = await page.locator('ntx-topbar').evaluate((el) => {
      const dd = el.shadowRoot?.querySelector('.user-dropdown');
      if (!dd) return { visibility: 'missing', opacity: '' };
      const s = getComputedStyle(dd);
      return { visibility: s.visibility, opacity: s.opacity };
    });
    expect(vis.visibility).toBe('hidden');
    expect(vis.opacity).toBe('0');
  });
});


test.describe('ntx-topbar — Logout Flow', () => {

  test('clicking logout removes JWT from localStorage', async ({ page }) => {
    await gotoAuthenticated(page, 'alice');

    const tokenBefore = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
    expect(tokenBefore).toBeTruthy();

    // Click logout (this triggers window.location.href = '/login.html')
    await page.locator('ntx-topbar').evaluate((el) => {
      el.shadowRoot?.querySelector('.logout-btn')?.click();
    });
    await page.waitForURL('**/login.html');

    // Token should be removed
    const tokenAfter = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
    expect(tokenAfter).toBeNull();
  });
});


test.describe('ntx-topbar — Theme Toggle', () => {

  test('clicking theme toggle changes theme and shows correct label', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntx-theme', 'dark'));
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    // Initial: dark mode, slotted theme button should offer light mode next.
    const initialLabel = await page.locator('ntx-topbar ntx-theme-button[slot="user-menu"]').evaluate((el) => {
      return el.shadowRoot?.querySelector('button')?.getAttribute('aria-label') || '';
    });
    expect(initialLabel).toContain('Light');

    // Click toggle
    await page.locator('ntx-topbar ntx-theme-button[slot="user-menu"]').evaluate((el) => {
      el.shadowRoot?.querySelector('button')?.click();
    });
    await waitForUiSettled(page);

    const newTheme = await page.evaluate(() =>
      document.documentElement.dataset.theme
    );
    expect(newTheme).toBe('light');
  });

  test('slotted theme button has SVG icon', async ({ page }) => {
    await gotoAuthenticated(page, 'alice');

    const hasSvg = await page.locator('ntx-topbar ntx-theme-button[slot="user-menu"]').evaluate((el) => {
      const icon = el.shadowRoot?.querySelector('.theme-button__icon');
      return !!icon?.querySelector('svg');
    });
    expect(hasSvg).toBe(true);
  });
});


test.describe('ntx-topbar — Responsive', () => {

  test('at 360px mobile: user-name and topbar-tag hidden', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await gotoAuthenticated(page, 'alice');

    const visibility = await page.locator('ntx-topbar').evaluate((el) => {
      const sr = el.shadowRoot;
      const name = sr?.querySelector('.user-name');
      const tag = sr?.querySelector('.topbar-tag');
      const chevron = sr?.querySelector('.user-chevron');
      return {
        nameHidden: name ? getComputedStyle(name).display === 'none' : true,
        tagHidden: tag ? getComputedStyle(tag).display === 'none' : true,
        chevronHidden: chevron ? getComputedStyle(chevron).display === 'none' : true,
      };
    });
    expect(visibility.nameHidden).toBe(true);
    expect(visibility.tagHidden).toBe(true);
    expect(visibility.chevronHidden).toBe(true);
  });

  test('at 1920px widescreen: all elements visible', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await gotoAuthenticated(page, 'alice');

    const visibility = await page.locator('ntx-topbar').evaluate((el) => {
      const sr = el.shadowRoot;
      const name = sr?.querySelector('.user-name');
      const tag = sr?.querySelector('.topbar-tag');
      return {
        nameVisible: name ? getComputedStyle(name).display !== 'none' : false,
        tagVisible: tag ? getComputedStyle(tag).display !== 'none' : false,
        hasBrand: !!sr?.querySelector('.topbar-brand'),
      };
    });
    expect(visibility.nameVisible).toBe(true);
    expect(visibility.tagVisible).toBe(true);
    expect(visibility.hasBrand).toBe(true);
  });
});


test.describe('ntx-topbar — Edge Cases', () => {

  test('corrupted JWT does not crash the page', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('jwtToken', 'not.a.valid.jwt'));
    await reloadApp(page);

    // Invalid JWT may trigger an async auth redirect after the app shell starts.
    await page.waitForURL('**/login.html', { timeout: 5000 }).catch(() => {});
    await page.waitForLoadState('domcontentloaded');

    // The page may redirect to login.html (valid behavior for bad JWT)
    // or may degrade to anonymous. Either way: no crash.
    const url = page.url();
    const pageHasContent = await page.evaluate(() => {
      return document.body.children.length > 0;
    });
    expect(pageHasContent).toBe(true);

    // No critical unhandled errors (filter known framework assertion messages)
    const critical = errors.filter(e =>
      !e.includes('AssertionError') && !e.includes('Assertion error')
    );
    expect(critical).toHaveLength(0);
  });

  test('topbar has sticky positioning via :host', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const position = await page.locator('ntx-topbar').evaluate((el) => {
      return getComputedStyle(el).position;
    });
    expect(position).toBe('sticky');
  });

  test('topbar z-index ensures it stays on top', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const zIndex = await page.locator('ntx-topbar').evaluate((el) => {
      return getComputedStyle(el).zIndex;
    });
    expect(parseInt(zIndex)).toBeGreaterThanOrEqual(100);
  });

  test('topbar has a usable positive height', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const height = await page.locator('ntx-topbar').evaluate((el) => {
      const nav = el.shadowRoot?.querySelector('.topbar');
      return nav ? nav.getBoundingClientRect().height : 0;
    });
    expect(height).toBeGreaterThanOrEqual(56);
  });
});
