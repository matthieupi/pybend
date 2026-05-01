/**
 * Route Grammar Smoke — browser refresh/back coverage for explicit @ view routes.
 */
import { test, expect } from './fixtures/parallel.js';
import { gotoApp, reloadApp, waitForAppReady, waitForRouterContent } from './fixtures/ui.js';

const APP_URL = '/';

async function waitForMountedRoute(page, selector) {
  await waitForRouterContent(page);
  await expect.poll(async () => page.locator('ntx-router').evaluate((router, innerSelector) => {
    const content = router.shadowRoot?.querySelector('.router-content');
    return !!content?.querySelector(innerSelector);
  }, selector), {
    timeout: 10000,
    intervals: [100, 250, 500],
  }).toBe(true);
}

async function mountedRouteState(page) {
  return page.locator('ntx-router').evaluate((router) => {
    const content = router.shadowRoot?.querySelector('.router-content');
    const first = content?.firstElementChild;
    return {
      hash: window.location.hash,
      tag: first?.tagName?.toLowerCase() || '',
      model: first?.getAttribute('model') || '',
      ref: first?.getAttribute('ref') || '',
      display: first?.getAttribute('display') || '',
      hasSlot: !!content?.querySelector('slot'),
    };
  });
}

async function expectProductSelectedInSidebar(page) {
  await expect.poll(async () => page.locator('ntx-sidebar').evaluate((sidebar) => {
    const section = sidebar.shadowRoot?.querySelector('.model-section[data-model="Product"]');
    const header = section?.querySelector('.model-header');
    return {
      selected: section?.classList.contains('model-section--selected') || false,
      current: header?.getAttribute('aria-current') || '',
    };
  }), {
    timeout: 10000,
    intervals: [100, 250, 500],
  }).toEqual({ selected: true, current: 'page' });
}

test.describe('Route grammar smoke — @ view routes', () => {
  test('collection @ routes render, refresh, and highlight sidebar state', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/@`);
    await waitForMountedRoute(page, 'ntx-list[model="Product"]');

    let state = await mountedRouteState(page);
    expect(state).toMatchObject({ hash: '#Product/@', tag: 'ntx-list', model: 'Product' });
    await expectProductSelectedInSidebar(page);

    await reloadApp(page);
    await waitForMountedRoute(page, 'ntx-list[model="Product"]');
    state = await mountedRouteState(page);
    expect(state).toMatchObject({ hash: '#Product/@', tag: 'ntx-list', model: 'Product' });

    await gotoApp(page, `${APP_URL}#Product/@table`);
    await waitForMountedRoute(page, 'ntx-table[model="Product"]');
    state = await mountedRouteState(page);
    expect(state).toMatchObject({ hash: '#Product/@table', tag: 'ntx-table', model: 'Product' });
    await expectProductSelectedInSidebar(page);

    await reloadApp(page);
    await waitForMountedRoute(page, 'ntx-table[model="Product"]');
    state = await mountedRouteState(page);
    expect(state).toMatchObject({ hash: '#Product/@table', tag: 'ntx-table', model: 'Product' });
  });

  test('member @ routes render, refresh, and browser back returns to collection route', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/@table`);
    await waitForMountedRoute(page, 'ntx-table[model="Product"]');

    await page.evaluate(() => { window.location.hash = '#Product/1/@'; });
    await waitForMountedRoute(page, 'ntx-item[ref="Product/1"]');

    let state = await mountedRouteState(page);
    expect(state).toMatchObject({ hash: '#Product/1/@', tag: 'ntx-item', ref: 'Product/1', display: 'lg' });
    await expectProductSelectedInSidebar(page);

    await reloadApp(page);
    await waitForMountedRoute(page, 'ntx-item[ref="Product/1"]');
    state = await mountedRouteState(page);
    expect(state).toMatchObject({ hash: '#Product/1/@', tag: 'ntx-item', ref: 'Product/1', display: 'lg' });

    await page.evaluate(() => { window.location.hash = '#Product/1/@item'; });
    await waitForMountedRoute(page, 'ntx-item[ref="Product/1"]');
    state = await mountedRouteState(page);
    expect(state).toMatchObject({ hash: '#Product/1/@item', tag: 'ntx-item', ref: 'Product/1', display: 'lg' });

    await page.goBack();
    await waitForMountedRoute(page, 'ntx-item[ref="Product/1"]');
    expect(await page.evaluate(() => window.location.hash)).toBe('#Product/1/@');

    await page.goBack();
    await waitForMountedRoute(page, 'ntx-table[model="Product"]');
    expect(await page.evaluate(() => window.location.hash)).toBe('#Product/@table');
  });

  test('legacy routes still render and home navigation clears hash without #@', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product`);
    await waitForMountedRoute(page, 'ntx-list[model="Product"]');
    expect(await page.evaluate(() => window.location.hash)).toBe('#Product');

    await gotoApp(page, `${APP_URL}#Product/1`);
    await waitForMountedRoute(page, 'ntx-item[ref="Product/1"]');
    expect(await page.evaluate(() => window.location.hash)).toBe('#Product/1');

    await gotoApp(page, `${APP_URL}#Product/1/countdown`);
    await waitForMountedRoute(page, 'ntx-stream[method="countdown"]');
    expect(await page.evaluate(() => window.location.hash)).toBe('#Product/1/countdown');

    await page.locator('ntx-topbar').evaluate((topbar) => {
      topbar.shadowRoot?.querySelector('.topbar-brand')?.click();
    });
    await waitForAppReady(page);

    const hash = await page.evaluate(() => window.location.hash);
    expect(hash === '' || hash === '#').toBe(true);
    expect(hash).not.toBe('#@');
  });
});
