/**
 * ntx-router — Browser integration coverage
 *
 * Pure Router and component rendering contracts live in Vitest router tests. This
 * file keeps checks that need a browser URL, history stack, auth-backed shell, or
 * live backend data.
 */
import { test, expect } from './fixtures/parallel.js';
import { loginAs } from './fixtures/auth.js';
import { gotoApp, waitForAppReady, waitForRouterContent, waitForUiSettled } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('ntx-router — Browser Root And Detail Navigation', () => {
  test('at root, router shows slotted list content', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const rootState = await page.locator('ntx-router').evaluate((r) => {
      const sr = r.shadowRoot;
      return {
        hasSlot: !!sr?.querySelector('.router-content slot'),
        chromeHidden: sr?.querySelector('.router-chrome')?.hidden ?? false,
        hasList: !!document.querySelector('ntx-router ntx-list'),
      };
    });

    expect(rootState.hasSlot).toBe(true);
    expect(rootState.chromeHidden).toBe(true);
    expect(rootState.hasList).toBe(true);
  });

  test('direct URL with hash loads backend-backed detail view', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const detailState = await page.locator('ntx-router').evaluate((r) => {
      const sr = r.shadowRoot;
      return {
        hasItem: !!sr?.querySelector('.router-content ntx-item'),
        title: sr?.querySelector('.router-title')?.textContent || '',
      };
    });

    expect(detailState.hasItem).toBe(true);
    expect(detailState.title).toContain('Product');
  });

  test('router back button returns to list and clears hash', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    await page.locator('#product-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntx-item');
      item?.shadowRoot?.querySelector('.card')?.click();
    });
    await waitForAppReady(page);
    expect(page.url()).toContain('#Product');

    await page.locator('ntx-router').evaluate((r) => {
      r.shadowRoot?.querySelector('.back-btn')?.click();
    });
    await waitForAppReady(page);

    const hash = new URL(page.url()).hash;
    expect(hash === '' || hash === '#').toBe(true);

    const hasSlot = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('slot');
    });
    expect(hasSlot).toBe(true);
  });
});

test.describe('ntx-router — Browser Hash And History', () => {
  test('programmatic hash change triggers navigation and clearing hash returns home', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    await page.evaluate(() => { window.location.hash = '#Product/2'; });
    await waitForAppReady(page);

    const hasContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content ntx-item');
    });
    expect(hasContent).toBe(true);

    await page.evaluate(() => { window.location.hash = ''; });
    await waitForAppReady(page);

    const hasSlot = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('slot');
    });
    expect(hasSlot).toBe(true);
  });

  test('browser back button works after hash navigation', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    await page.evaluate(() => { window.location.hash = '#Product/1'; });
    await waitForAppReady(page);
    expect(page.url()).toContain('#Product/1');

    await page.goBack();
    await waitForAppReady(page);

    const hash = new URL(page.url()).hash;
    expect(hash === '' || hash === '#' || !hash.includes('Product/1')).toBe(true);
  });

  test('rapid sequential hash changes do not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    await page.evaluate(() => { window.location.hash = '#Product/1'; });
    await waitForUiSettled(page);
    await page.evaluate(() => { window.location.hash = '#Product/2'; });
    await waitForUiSettled(page);
    await page.evaluate(() => { window.location.hash = '#Product/3'; });
    await waitForUiSettled(page);
    await page.evaluate(() => { window.location.hash = ''; });
    await waitForAppReady(page);

    const routerOk = await page.locator('ntx-router').evaluate((r) => !!r.shadowRoot);
    expect(routerOk).toBe(true);

    const critical = errors.filter(e =>
      !e.includes('AssertionError') && !e.includes('Assertion error') && !e.includes('ResizeObserver')
    );
    expect(critical).toHaveLength(0);
  });
});

test.describe('ntx-router — Authenticated App Routes', () => {
  test('#@favorites navigates to favorites view', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    await page.evaluate(() => { window.location.hash = '#@favorites'; });
    await waitForRouterContent(page);

    const hasFavComponent = await page.locator('ntx-router').evaluate((r) => {
      const content = r.shadowRoot?.querySelector('.router-content');
      return !!content?.querySelector('ntx-favorites');
    });
    expect(hasFavComponent).toBe(true);
  });

  test('#@profile navigates to profile view', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    await page.evaluate(() => { window.location.hash = '#@profile'; });
    await waitForRouterContent(page);

    const hasProfileComponent = await page.locator('ntx-router').evaluate((r) => {
      const content = r.shadowRoot?.querySelector('.router-content');
      return !!content?.querySelector('ntx-profile');
    });
    expect(hasProfileComponent).toBe(true);
  });
});

test.describe('ntx-router — Responsive Browser Rendering', () => {
  test('router renders at mobile viewport (360px)', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const hasContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('router renders at desktop viewport (1280px)', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const hasContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });
});
