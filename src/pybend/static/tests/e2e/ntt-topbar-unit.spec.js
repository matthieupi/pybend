/**
 * ntt-topbar — Comprehensive Unit Tests
 *
 * Tests the topbar component's rendering, user pill, dropdown,
 * logout flow, theme toggle, and edge cases in isolation.
 *
 * NOTE: Some basic topbar tests exist in page-load.spec.js and
 * authentication.spec.js. This file covers deeper component behavior
 * and edge cases that those files do not.
 */
import { test, expect } from '@playwright/test';
import { loginAs, logout, USERS } from './fixtures/auth.js';

const APP_URL = '/';

/** Helper: go to app in anonymous mode */
async function gotoAnonymous(page) {
  await page.goto(APP_URL);
  await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
}

/** Helper: go to app and login */
async function gotoAuthenticated(page, user = 'alice') {
  await page.goto(APP_URL);
  await loginAs(page, user);
  await page.waitForTimeout(2000);
}

test.describe('ntt-topbar — Anonymous State', () => {

  test('topbar renders with .topbar nav and brand', async ({ page }) => {
    await gotoAnonymous(page);

    const structure = await page.locator('ntt-topbar').evaluate((el) => {
      const sr = el.shadowRoot;
      return {
        hasNav: !!sr?.querySelector('nav.topbar'),
        brandHref: sr?.querySelector('.topbar-brand')?.getAttribute('href') || '',
        title: sr?.querySelector('.topbar-title')?.textContent || '',
        logo: sr?.querySelector('.topbar-logo')?.textContent?.trim() || '',
        tag: sr?.querySelector('.topbar-tag')?.textContent?.trim() || '',
      };
    });
    expect(structure.hasNav).toBe(true);
    expect(structure.brandHref).toBe('/');
    expect(structure.title).toContain('NTT');
    expect(structure.logo).toBe('N3');
    expect(structure.tag).toBe('v0.6');
  });

  test('signin-link present with correct text and href', async ({ page }) => {
    await gotoAnonymous(page);

    const signIn = await page.locator('ntt-topbar').evaluate((el) => {
      const link = el.shadowRoot?.querySelector('.signin-link');
      return {
        text: link?.textContent?.trim() || '',
        href: link?.getAttribute('href') || '',
      };
    });
    expect(signIn.text).toContain('Sign in');
    expect(signIn.href).toBe('/login.html');
  });

  test('user-pill, user-dropdown, favorites, profile are NOT present', async ({ page }) => {
    await gotoAnonymous(page);

    const absent = await page.locator('ntt-topbar').evaluate((el) => {
      const sr = el.shadowRoot;
      return {
        hasPill: !!sr?.querySelector('.user-pill'),
        hasDropdown: !!sr?.querySelector('.user-dropdown'),
        hasFav: !!sr?.querySelector('a[href="#@favorites"]'),
        hasProfile: !!sr?.querySelector('a[href="#@profile"]'),
      };
    });
    expect(absent.hasPill).toBe(false);
    expect(absent.hasDropdown).toBe(false);
    expect(absent.hasFav).toBe(false);
    expect(absent.hasProfile).toBe(false);
  });
});


test.describe('ntt-topbar — Authenticated State', () => {

  test('user-pill visible with avatar initial, name, and chevron', async ({ page }) => {
    await gotoAuthenticated(page, 'alice');

    const pill = await page.locator('ntt-topbar').evaluate((el) => {
      const sr = el.shadowRoot;
      return {
        hasPill: !!sr?.querySelector('.user-pill'),
        avatar: sr?.querySelector('.user-avatar')?.textContent?.trim() || '',
        name: sr?.querySelector('.user-name')?.textContent?.trim() || '',
        hasChevron: !!sr?.querySelector('.user-chevron'),
      };
    });
    expect(pill.hasPill).toBe(true);
    expect(pill.avatar).toBe('A'); // Alice's initial
    expect(pill.name.length).toBeGreaterThan(0);
    expect(pill.hasChevron).toBe(true);
  });

  test('signin-link NOT present when authenticated', async ({ page }) => {
    await gotoAuthenticated(page, 'alice');

    const hasSignIn = await page.locator('ntt-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.signin-link');
    });
    expect(hasSignIn).toBe(false);
  });

  test('dropdown contains email, role, theme, profile, logout', async ({ page }) => {
    await gotoAuthenticated(page, 'alice');

    const dropdown = await page.locator('ntt-topbar').evaluate((el) => {
      const sr = el.shadowRoot;
      const dd = sr?.querySelector('.user-dropdown');
      return {
        email: dd?.querySelector('.dropdown-email')?.textContent?.trim() || '',
        hasRole: !!dd?.querySelector('.dropdown-role'),
        hasTheme: !!dd?.querySelector('.theme-toggle'),
        hasProfile: !!dd?.querySelector('a[href="#@profile"]'),
        hasLogout: !!dd?.querySelector('.logout-btn'),
        hasFav: !!sr?.querySelector('a[href="#@favorites"]'),
        hasHeader: !!dd?.querySelector('.dropdown-header'),
        dividerCount: dd?.querySelectorAll('.dropdown-divider').length || 0,
        itemCount: dd?.querySelectorAll('.dropdown-item').length || 0,
      };
    });
    expect(dropdown.email).toBe(USERS.alice.email);
    expect(dropdown.hasRole).toBe(true);
    expect(dropdown.hasTheme).toBe(true);
    expect(dropdown.hasProfile).toBe(true);
    expect(dropdown.hasLogout).toBe(true);
    expect(dropdown.hasFav).toBe(true);
    expect(dropdown.hasHeader).toBe(true);
    expect(dropdown.dividerCount).toBeGreaterThanOrEqual(1);
    expect(dropdown.itemCount).toBeGreaterThanOrEqual(3);
  });

  test('dropdown shows correct email per user (bob)', async ({ page }) => {
    await gotoAuthenticated(page, 'bob');

    const info = await page.locator('ntt-topbar').evaluate((el) => {
      return {
        email: el.shadowRoot?.querySelector('.dropdown-email')?.textContent?.trim() || '',
        avatar: el.shadowRoot?.querySelector('.user-avatar')?.textContent?.trim() || '',
      };
    });
    expect(info.email).toBe(USERS.bob.email);
    expect(info.avatar).toBe('B');
  });

  test('dropdown shows correct email per user (charlie)', async ({ page }) => {
    await gotoAuthenticated(page, 'charlie');

    const info = await page.locator('ntt-topbar').evaluate((el) => {
      return {
        email: el.shadowRoot?.querySelector('.dropdown-email')?.textContent?.trim() || '',
        avatar: el.shadowRoot?.querySelector('.user-avatar')?.textContent?.trim() || '',
      };
    });
    expect(info.email).toBe(USERS.charlie.email);
    expect(info.avatar).toBe('C');
  });
});


test.describe('ntt-topbar — Dropdown Visibility', () => {

  test('dropdown is initially hidden (opacity 0, visibility hidden)', async ({ page }) => {
    await gotoAuthenticated(page, 'alice');

    const vis = await page.locator('ntt-topbar').evaluate((el) => {
      const dd = el.shadowRoot?.querySelector('.user-dropdown');
      if (!dd) return { visibility: 'missing', opacity: '' };
      const s = getComputedStyle(dd);
      return { visibility: s.visibility, opacity: s.opacity };
    });
    expect(vis.visibility).toBe('hidden');
    expect(vis.opacity).toBe('0');
  });
});


test.describe('ntt-topbar — Logout Flow', () => {

  test('clicking logout removes JWT from localStorage', async ({ page }) => {
    await gotoAuthenticated(page, 'alice');

    const tokenBefore = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
    expect(tokenBefore).toBeTruthy();

    // Click logout (this triggers window.location.href = '/login.html')
    await page.locator('ntt-topbar').evaluate((el) => {
      el.shadowRoot?.querySelector('.logout-btn')?.click();
    });
    await page.waitForTimeout(500);

    // Token should be removed
    const tokenAfter = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
    expect(tokenAfter).toBeNull();
  });
});


test.describe('ntt-topbar — Theme Toggle', () => {

  test('clicking theme toggle changes theme and shows correct label', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('ntt-theme', 'dark'));
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    // Initial: dark mode, toggle should say "Light mode"
    const initialLabel = await page.locator('ntt-topbar').evaluate((el) => {
      return el.shadowRoot?.querySelector('.theme-toggle')?.textContent?.trim() || '';
    });
    expect(initialLabel).toContain('Light');

    // Click toggle
    await page.locator('ntt-topbar').evaluate((el) => {
      el.shadowRoot?.querySelector('.theme-toggle')?.click();
    });
    await page.waitForTimeout(500);

    const newTheme = await page.evaluate(() =>
      document.documentElement.dataset.theme
    );
    expect(newTheme).toBe('light');
  });

  test('theme toggle has SVG icon', async ({ page }) => {
    await gotoAuthenticated(page, 'alice');

    const hasSvg = await page.locator('ntt-topbar').evaluate((el) => {
      const icon = el.shadowRoot?.querySelector('.theme-toggle .dropdown-icon');
      return !!icon?.querySelector('svg');
    });
    expect(hasSvg).toBe(true);
  });
});


test.describe('ntt-topbar — Responsive', () => {

  test('at 360px mobile: user-name and topbar-tag hidden', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await gotoAuthenticated(page, 'alice');

    const visibility = await page.locator('ntt-topbar').evaluate((el) => {
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

    const visibility = await page.locator('ntt-topbar').evaluate((el) => {
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


test.describe('ntt-topbar — Edge Cases', () => {

  test('corrupted JWT does not crash the page', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.setItem('jwtToken', 'not.a.valid.jwt'));
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

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
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const position = await page.locator('ntt-topbar').evaluate((el) => {
      return getComputedStyle(el).position;
    });
    expect(position).toBe('sticky');
  });

  test('topbar z-index ensures it stays on top', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const zIndex = await page.locator('ntt-topbar').evaluate((el) => {
      return getComputedStyle(el).zIndex;
    });
    expect(parseInt(zIndex)).toBeGreaterThanOrEqual(100);
  });

  test('topbar height is 56px', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const height = await page.locator('ntt-topbar').evaluate((el) => {
      const nav = el.shadowRoot?.querySelector('.topbar');
      return nav ? getComputedStyle(nav).height : '';
    });
    expect(height).toBe('56px');
  });
});
