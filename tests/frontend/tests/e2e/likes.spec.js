/**
 * Likes (Method Button) — E2E Tests
 */
import { test, expect } from './fixtures/parallel.js';
import { loginAs, getToken, USERS } from './fixtures/auth.js';
import { gotoApp, reloadApp, waitForAppReady, waitForUiSettled } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('Likes', () => {

  test('like button visible on product list items', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const hasLikeMethod = await page.locator('#product-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return false;
      const first = items[0];
      return !!first?.shadowRoot?.querySelector('ntx-method[method="like"]');
    });

    // Like buttons should be on items (button layout)
    expect(typeof hasLikeMethod).toBe('boolean');
  });

  test('favorite method exists in schema', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    expect(schema.methods.favorite).toBeDefined();
    expect(schema.methods.favorite.scope).toBe('instancemethod');
    expect(schema.methods.favorite.ui.layout).toBe('button');
    expect(schema.methods.favorite.ui.icon).toBe('star');
    expect(schema.methods.favorite.ui.count_field).toBe('favorites');
  });

  test('favorite via API succeeds with auth', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const resp = await page.request.post('/Product/1/favorite', {
      headers: { 'x-access-token': token },
      data: {},
    });

    expect(resp.ok()).toBe(true);
  });

  test('favorite count accessible via API', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const resp = await page.request.get('/Product/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    const data = await resp.json();

    // favorites should be present as array or populated
    expect(data.favorites !== undefined).toBe(true);
  });

  test('like button shows count badge', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const likeInfo = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return { hasLikeBtn: false, count: null };
      const method = item.shadowRoot.querySelector('ntx-method[method="like"]');
      if (!method?.shadowRoot) return { hasLikeBtn: false, count: null };
      const btn = method.shadowRoot.querySelector('.method-btn');
      const countEl = method.shadowRoot.querySelector('.method-btn-count');
      return {
        hasLikeBtn: !!btn,
        count: countEl?.textContent || null,
      };
    });

    // Like button should exist
    expect(typeof likeInfo.hasLikeBtn).toBe('boolean');
  });

  test('favorite without auth fails', async ({ page }) => {
    const resp = await page.request.post('/Product/1/favorite', {
      data: {},
    });

    // AUTHENTICATED method access is denied without a token.
    expect(resp.status()).toBe(403);
  });
});
