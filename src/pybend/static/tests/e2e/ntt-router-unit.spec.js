/**
 * ntt-router — Comprehensive Unit Tests
 *
 * Tests the router component's navigation, hash-based routing,
 * back button, special routes, and edge cases.
 */
import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.js';

const APP_URL = '/matrix.html';

test.describe('ntt-router — Root State (No Hash)', () => {

  test('at root, router shows slot content (ntt-list)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const rootState = await page.locator('ntt-router').evaluate((r) => {
      const sr = r.shadowRoot;
      return {
        hasSlot: !!sr?.querySelector('slot'),
        hasRouterContent: !!sr?.querySelector('.router-content'),
        hasBackBtn: !!sr?.querySelector('.back-btn'),
      };
    });
    expect(rootState.hasSlot).toBe(true);
    expect(rootState.hasRouterContent).toBe(false);
    expect(rootState.hasBackBtn).toBe(false);
  });

  test('ntt-list is visible inside router at root', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const listVisible = await page.evaluate(() => {
      const list = document.querySelector('ntt-router ntt-list');
      return !!list;
    });
    expect(listVisible).toBe(true);
  });
});


test.describe('ntt-router — Detail Navigation', () => {

  test('navigating to #Product/1 shows detail view', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const detailState = await page.locator('ntt-router').evaluate((r) => {
      const sr = r.shadowRoot;
      return {
        hasRouterContent: !!sr?.querySelector('.router-content'),
        hasItem: !!sr?.querySelector('.router-content ntt-item'),
        hasChrome: !!sr?.querySelector('.router-chrome'),
        hasBackBtn: !!sr?.querySelector('.back-btn'),
        title: sr?.querySelector('.router-title')?.textContent || '',
      };
    });
    expect(detailState.hasRouterContent).toBe(true);
    expect(detailState.hasItem).toBe(true);
    expect(detailState.hasChrome).toBe(true);
    expect(detailState.hasBackBtn).toBe(true);
    expect(detailState.title).toContain('Product');
  });

  test('detail item in router uses ref attribute', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const ref = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('.router-content ntt-item');
      return item?.getAttribute('ref') || '';
    });
    expect(ref).toContain('Product/1');
  });
});


test.describe('ntt-router — Back Navigation', () => {

  test('click back returns to list (slot content)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Navigate to detail by clicking an item
    await page.locator('ntt-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntt-item');
      if (item?.shadowRoot) {
        item.shadowRoot.querySelector('.card')?.click();
      }
    });
    await page.waitForTimeout(1500);
    expect(page.url()).toContain('#Product');

    // Click back
    await page.locator('ntt-router').evaluate((r) => {
      r.shadowRoot?.querySelector('.back-btn')?.click();
    });
    await page.waitForTimeout(1000);

    // Should be back at root
    const hash = new URL(page.url()).hash;
    expect(hash === '' || hash === '#').toBe(true);

    // List should be visible again
    const hasSlot = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('slot');
    });
    expect(hasSlot).toBe(true);
  });
});


test.describe('ntt-router — Hash-Based Routing', () => {

  test('direct URL with hash loads detail view directly', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasContent = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('programmatic hash change triggers navigation', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await page.evaluate(() => { window.location.hash = '#Product/2'; });
    await page.waitForTimeout(1500);

    const hasContent = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('clearing hash returns to root/list view', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await page.evaluate(() => { window.location.hash = ''; });
    await page.waitForTimeout(1000);

    const hasSlot = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('slot');
    });
    expect(hasSlot).toBe(true);
  });

  test('non-existent product hash handles gracefully (no crash)', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(`${APP_URL}#Product/99999`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Router should still be functional
    const routerOk = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot;
    });
    expect(routerOk).toBe(true);
  });
});


test.describe('ntt-router — Special Routes', () => {

  test('#@favorites navigates to favorites view', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    await page.evaluate(() => { window.location.hash = '#@favorites'; });
    await page.waitForTimeout(2000);

    const hasFavComponent = await page.locator('ntt-router').evaluate((r) => {
      const content = r.shadowRoot?.querySelector('.router-content');
      return !!content?.querySelector('ntt-favorites');
    });
    expect(hasFavComponent).toBe(true);
  });

  test('#@profile navigates to profile view', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    await page.evaluate(() => { window.location.hash = '#@profile'; });
    await page.waitForTimeout(2000);

    const hasProfileComponent = await page.locator('ntt-router').evaluate((r) => {
      const content = r.shadowRoot?.querySelector('.router-content');
      return !!content?.querySelector('ntt-profile');
    });
    expect(hasProfileComponent).toBe(true);
  });

  test('unknown @route does not crash router', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    await page.evaluate(() => { window.location.hash = '#@unknown'; });
    await page.waitForTimeout(1500);

    // Router should still be functional (may show an empty component)
    const routerOk = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot;
    });
    expect(routerOk).toBe(true);
  });
});


test.describe('ntt-router — History', () => {

  test('browser back button works after hash navigation', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Navigate to detail
    await page.evaluate(() => { window.location.hash = '#Product/1'; });
    await page.waitForTimeout(1500);
    expect(page.url()).toContain('#Product/1');

    // Use browser back
    await page.goBack();
    await page.waitForTimeout(1000);

    // Should be at root or previous state
    const hash = new URL(page.url()).hash;
    expect(hash === '' || hash === '#' || !hash.includes('Product/1')).toBe(true);
  });
});


test.describe('ntt-router — Edge Cases', () => {

  test('rapid sequential hash changes do not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    await page.evaluate(() => { window.location.hash = '#Product/1'; });
    await page.waitForTimeout(100);
    await page.evaluate(() => { window.location.hash = '#Product/2'; });
    await page.waitForTimeout(100);
    await page.evaluate(() => { window.location.hash = '#Product/3'; });
    await page.waitForTimeout(100);
    await page.evaluate(() => { window.location.hash = ''; });
    await page.waitForTimeout(1500);

    const routerOk = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot;
    });
    expect(routerOk).toBe(true);

    // No critical unhandled errors
    const critical = errors.filter(e =>
      !e.includes('AssertionError') && !e.includes('Assertion error') && !e.includes('ResizeObserver')
    );
    expect(critical).toHaveLength(0);
  });

  test('router renders at mobile viewport (360px)', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasContent = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('router renders at desktop viewport (1280px)', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasContent = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('router chrome has correct CSS structure', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const structure = await page.locator('ntt-router').evaluate((r) => {
      const sr = r.shadowRoot;
      return {
        hasChrome: !!sr?.querySelector('.router-chrome'),
        hasTitle: !!sr?.querySelector('.router-title'),
        hasContent: !!sr?.querySelector('.router-content'),
        hasStylesheet: !!sr?.querySelector('link[rel="stylesheet"]'),
      };
    });
    expect(structure.hasChrome).toBe(true);
    expect(structure.hasTitle).toBe(true);
    expect(structure.hasContent).toBe(true);
    expect(structure.hasStylesheet).toBe(true);
  });
});
