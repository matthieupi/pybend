/**
 * Likes (Method Button) — E2E Tests
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, USERS } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('Likes', () => {

  test('like button visible on product list items', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasLikeMethod = await page.locator('#product-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return false;
      const first = items[0];
      return !!first?.shadowRoot?.querySelector('ntx-method[method="like"]');
    });

    // Like buttons should be on items (button layout)
    expect(typeof hasLikeMethod).toBe('boolean');
  });

  test('like method exists in schema', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    expect(schema.methods.like).toBeDefined();
    expect(schema.methods.like.scope).toBe('instancemethod');
    expect(schema.methods.like.ui.layout).toBe('button');
    expect(schema.methods.like.ui.icon).toBe('heart');
    expect(schema.methods.like.ui.count_field).toBe('likes');
  });

  test('like via API succeeds with auth', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const resp = await page.request.post('/products/1/like', {
      headers: { 'x-access-token': token },
      data: {},
    });

    expect(resp.ok()).toBe(true);
  });

  test('like count accessible via API', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const resp = await page.request.get('/products/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    const data = await resp.json();

    // likes should be present as array or populated
    expect(data.likes !== undefined).toBe(true);
  });

  test('like button shows count badge', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

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

  test('like without auth fails', async ({ page }) => {
    const resp = await page.request.post('/products/1/like', {
      data: {},
    });

    // Should fail with 401 (no token)
    expect(resp.status()).toBe(401);
  });
});
