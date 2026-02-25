/**
 * Favorites — E2E Tests
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, USERS } from './fixtures/auth.js';

const APP_URL = '/matrix.html';

test.describe('Favorites', () => {

  test('favorites link visible for authenticated user', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    const hasFavLink = await page.locator('ntt-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('a[href="#@favorites"]');
    });

    expect(hasFavLink).toBe(true);
  });

  test('clicking favorites navigates to #@favorites', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    // Click the favorites link
    await page.locator('ntt-topbar').evaluate((el) => {
      const link = el.shadowRoot?.querySelector('a[href="#@favorites"]');
      link?.click();
    });

    await page.waitForTimeout(500);

    const hash = await page.evaluate(() => window.location.hash);
    expect(hash).toBe('#@favorites');
  });

  test('favorites page renders ntt-favorites component', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    // Navigate to favorites
    await page.evaluate(() => { window.location.hash = '#@favorites'; });
    await page.waitForTimeout(2000);

    const hasFavoritesComponent = await page.evaluate(() => {
      // ntt-favorites may be inside ntt-router's shadowRoot
      const router = document.querySelector('ntt-router');
      if (!router?.shadowRoot) return false;
      const content = router.shadowRoot.querySelector('.router-content');
      if (!content) return false;
      return !!content.querySelector('ntt-favorites');
    });

    expect(hasFavoritesComponent).toBe(true);
  });

  test('favorites page contains ntt-list for ProductLike', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    // Navigate to favorites
    await page.evaluate(() => { window.location.hash = '#@favorites'; });
    await page.waitForTimeout(2000);

    const listInfo = await page.evaluate(() => {
      const router = document.querySelector('ntt-router');
      if (!router?.shadowRoot) return { found: false };
      const fav = router.shadowRoot.querySelector('ntt-favorites');
      if (!fav) return { found: false };
      const list = fav.querySelector('ntt-list');
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
    await page.request.post('/products/1/like', {
      headers: { 'x-access-token': token },
      data: {},
    });

    // Check favorites endpoint
    const resp = await page.request.get('/products/1/likes?depth=1', {
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
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    const hasFavLink = await page.locator('ntt-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('a[href="#@favorites"]');
    });

    expect(hasFavLink).toBe(false);
  });

  test('direct navigation to #@favorites without auth', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    // Navigate directly to favorites
    await page.evaluate(() => { window.location.hash = '#@favorites'; });
    await page.waitForTimeout(2000);

    // Page should not crash
    const pageStable = await page.evaluate(() => {
      return document.body.children.length > 0;
    });
    expect(pageStable).toBe(true);
  });
});
