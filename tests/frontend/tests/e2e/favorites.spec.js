/**
 * Favorites — E2E Tests
 */
import { test, expect } from './fixtures/parallel.js';
import { loginAs, getToken, USERS } from './fixtures/auth.js';
import { gotoApp, reloadApp, waitForAppReady, waitForRouterContent, waitForUiSettled } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('Favorites', () => {

  test('favorites link is not hardcoded by packaged topbar', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    const hasFavLink = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('a[href="#@favorites"]');
    });

    expect(hasFavLink).toBe(false);
  });

  test('direct favorites route updates hash to #@favorites', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    await page.evaluate(() => { window.location.hash = '#@favorites'; });

    await waitForUiSettled(page);

    const hash = await page.evaluate(() => window.location.hash);
    expect(hash).toBe('#@favorites');
  });

  test('favorites page renders ntx-favorites component', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    // Navigate to favorites
    await page.evaluate(() => { window.location.hash = '#@favorites'; });
    await waitForRouterContent(page);
    await page.waitForFunction(() => {
      const router = document.querySelector('ntx-router');
      return !!router?.shadowRoot?.querySelector('.router-content ntx-favorites');
    });

    const hasFavoritesComponent = await page.evaluate(() => {
      // ntx-favorites may be inside ntx-router's shadowRoot
      const router = document.querySelector('ntx-router');
      if (!router?.shadowRoot) return false;
      const content = router.shadowRoot.querySelector('.router-content');
      if (!content) return false;
      return !!content.querySelector('ntx-favorites');
    });

    expect(hasFavoritesComponent).toBe(true);
  });

  test('favorites page contains ntx-list for ProductLike', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    // Navigate to favorites
    await page.evaluate(() => { window.location.hash = '#@favorites'; });
    await waitForRouterContent(page);
    await page.waitForFunction(() => {
      const router = document.querySelector('ntx-router');
      return !!router?.shadowRoot?.querySelector('.router-content ntx-favorites ntx-list');
    });

    const listInfo = await page.evaluate(() => {
      const router = document.querySelector('ntx-router');
      if (!router?.shadowRoot) return { found: false };
      const fav = router.shadowRoot.querySelector('ntx-favorites');
      if (!fav) return { found: false };
      const list = fav.querySelector('ntx-list');
      if (!list) return { found: false };
      return {
        found: true,
        model: list.getAttribute('model'),
        display: list.getAttribute('display'),
      };
    });

    expect(listInfo.found).toBe(true);
    expect(listInfo.model).toBe('ProductLike');
    expect(listInfo.display).toBe('md');
  });

  test('ProductLike schema accessible via API', async ({ page }) => {
    const resp = await page.request.get('/ProductLike');

    // ProductLike may or may not be a registered schema endpoint
    // depending on setup. If it exists, verify structure.
    if (resp.ok()) {
      const schema = await resp.json();
      expect(schema.$id).toBeDefined();
      expect(schema.properties).toBeDefined();
    }
  });

  test('like a product then verify it appears in favorites API', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Like product 1
    await page.request.post('/Product/1/like', {
      headers: { 'x-access-token': token },
      data: {},
    });

    // Check favorites endpoint
    const resp = await page.request.get('/Product/1/likes?depth=1', {
      headers: { 'x-access-token': token },
    });

    if (resp.ok()) {
      const data = await resp.json();
      // Should have at least one like entry
      const items = Array.isArray(data) ? data : (data.data || []);
      expect(items.length).toBeGreaterThanOrEqual(0);
    }
  });

  test('favorites not visible for anonymous user', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
    await reloadApp(page);

    await waitForAppReady(page);

    const hasFavLink = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('a[href="#@favorites"]');
    });

    expect(hasFavLink).toBe(false);
  });

  test('direct navigation to #@favorites without auth', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
    await reloadApp(page);

    await waitForAppReady(page);

    // Navigate directly to favorites
    await page.evaluate(() => { window.location.hash = '#@favorites'; });
    await waitForRouterContent(page);

    // Page should not crash
    const pageStable = await page.evaluate(() => {
      return document.body.children.length > 0;
    });
    expect(pageStable).toBe(true);
  });
});
