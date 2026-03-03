/**
 * flow-favorites-and-likes.spec.js — Favorite & Like Lifecycle Integration Tests
 *
 * Product has `favorite` method (star icon, toggles).
 * Comment has `like` method (heart icon, toggles) and `reply` method.
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, setToken, clearToken, USERS } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('Favorite — Toggle via API', () => {

  test('favorite a product and verify action response', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // First, ensure we are in a known state by unfavoriting if already favorited
    const firstResp = await page.request.post('/products/3/favorite', {
      headers: { 'x-access-token': token },
    });
    expect(firstResp.ok()).toBe(true);
    let firstData = await firstResp.json();
    if (typeof firstData === 'string') firstData = JSON.parse(firstData);
    const firstAction = firstData.action; // either "favorited" or "unfavorited"

    // Now toggle again to get the opposite action
    const secondResp = await page.request.post('/products/3/favorite', {
      headers: { 'x-access-token': token },
    });
    expect(secondResp.ok()).toBe(true);
    let secondData = await secondResp.json();
    if (typeof secondData === 'string') secondData = JSON.parse(secondData);

    // Actions should be opposite
    if (firstAction === 'favorited') {
      expect(secondData.action).toBe('unfavorited');
    } else {
      expect(secondData.action).toBe('favorited');
    }
  });

  test('favorite count changes after toggle', async ({ page }) => {
    const token = await getToken(page.request, USERS.bob.email, USERS.bob.password);

    // Create a fresh product to test on
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Fav Count Test ${Date.now()}`, price: 10 },
    });
    const product = await createResp.json();
    const pid = product.id;

    // Check initial favorites count
    const beforeResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': token },
    });
    const beforeData = await beforeResp.json();
    const beforeCount = beforeData.favorites?.data?.length ?? (Array.isArray(beforeData.favorites) ? beforeData.favorites.length : 0);
    expect(beforeCount).toBe(0);

    // Favorite the product
    const favResp = await page.request.post(`/products/${pid}/favorite`, {
      headers: { 'x-access-token': token },
    });
    expect(favResp.ok()).toBe(true);

    // Check count increased
    const afterResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': token },
    });
    const afterData = await afterResp.json();
    const afterCount = afterData.favorites?.data?.length ?? (Array.isArray(afterData.favorites) ? afterData.favorites.length : 0);
    expect(afterCount).toBe(1);

    // Unfavorite
    const unfavResp = await page.request.post(`/products/${pid}/favorite`, {
      headers: { 'x-access-token': token },
    });
    expect(unfavResp.ok()).toBe(true);

    // Check count decreased
    const finalResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': token },
    });
    const finalData = await finalResp.json();
    const finalCount = finalData.favorites?.data?.length ?? (Array.isArray(finalData.favorites) ? finalData.favorites.length : 0);
    expect(finalCount).toBe(0);
  });
});

test.describe('Favorite — Without Auth', () => {

  test('favorite without auth returns 403', async ({ page }) => {
    const resp = await page.request.post('/products/1/favorite');
    expect(resp.status()).toBe(403);
  });
});

test.describe('Favorite — Multiple Users', () => {

  test('multiple users can favorite the same product', async ({ page }) => {
    // Create a clean product
    const aliceToken = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': aliceToken },
      data: { name: `Multi Fav ${Date.now()}`, price: 10 },
    });
    const product = await createResp.json();
    const pid = product.id;

    // Alice favorites
    const r1 = await page.request.post(`/products/${pid}/favorite`, {
      headers: { 'x-access-token': aliceToken },
    });
    expect(r1.ok()).toBe(true);

    // Bob favorites
    const bobToken = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const r2 = await page.request.post(`/products/${pid}/favorite`, {
      headers: { 'x-access-token': bobToken },
    });
    expect(r2.ok()).toBe(true);

    // Charlie favorites
    const charlieToken = await getToken(page.request, USERS.charlie.email, USERS.charlie.password);
    const r3 = await page.request.post(`/products/${pid}/favorite`, {
      headers: { 'x-access-token': charlieToken },
    });
    expect(r3.ok()).toBe(true);

    // Verify count is 3
    const verifyResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': aliceToken },
    });
    const data = await verifyResp.json();
    const favCount = data.favorites?.data?.length ?? 0;
    expect(favCount).toBe(3);
  });
});

test.describe('Favorite — UI Button', () => {

  test('favorite button visible on product detail', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasFavBtn = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('ntt-method[method="favorite"]');
    });
    expect(hasFavBtn).toBe(true);
  });

  test('favorite button shows count badge', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const favInfo = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return { hasBtn: false, count: null };
      const method = item.shadowRoot.querySelector('ntt-method[method="favorite"]');
      if (!method?.shadowRoot) return { hasBtn: false, count: null };
      const btn = method.shadowRoot.querySelector('.method-btn');
      const countEl = method.shadowRoot.querySelector('.method-btn-count');
      return {
        hasBtn: !!btn,
        count: countEl?.textContent ?? null,
      };
    });
    expect(favInfo.hasBtn).toBe(true);
    // Count should be a number string
    expect(favInfo.count).not.toBeNull();
  });

  test('favorite button visible in product list items', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    const hasFavInList = await page.locator('ntt-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntt-item');
      if (!items?.length) return false;
      const first = items[0];
      return !!first?.shadowRoot?.querySelector('ntt-method[method="favorite"]');
    });
    expect(hasFavInList).toBe(true);
  });
});

test.describe('Favorite — Cross-Product Independence', () => {

  test('favorites on product A are independent from product B', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Create two products
    const ts = Date.now();
    const respA = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Cross Fav A ${ts}`, price: 10 },
    });
    const productA = await respA.json();

    const respB = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Cross Fav B ${ts}`, price: 20 },
    });
    const productB = await respB.json();

    // Favorite only product A
    await page.request.post(`/products/${productA.id}/favorite`, {
      headers: { 'x-access-token': token },
    });

    // Verify A has 1 favorite, B has 0
    const dataA = await (await page.request.get(`/products/${productA.id}?depth=1`, {
      headers: { 'x-access-token': token },
    })).json();
    const dataB = await (await page.request.get(`/products/${productB.id}?depth=1`, {
      headers: { 'x-access-token': token },
    })).json();

    const countA = dataA.favorites?.data?.length ?? 0;
    const countB = dataB.favorites?.data?.length ?? 0;
    expect(countA).toBe(1);
    expect(countB).toBe(0);
  });
});

test.describe('Comment Like — Toggle via API', () => {

  test('like a comment and verify toggle behavior', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Get a comment to like
    const productResp = await page.request.get('/products/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    const productData = await productResp.json();
    const comments = productData.comments?.data || [];
    expect(comments.length).toBeGreaterThanOrEqual(1);
    const commentId = comments[0].id;

    // Like the comment
    const likeResp = await page.request.post(`/products/1/comments/${commentId}/like`, {
      headers: { 'x-access-token': token },
    });
    expect(likeResp.ok()).toBe(true);
    let likeData = await likeResp.json();
    if (typeof likeData === 'string') likeData = JSON.parse(likeData);
    const firstAction = likeData.action;
    expect(['liked', 'unliked']).toContain(firstAction);

    // Toggle again — should be opposite
    const unlikeResp = await page.request.post(`/products/1/comments/${commentId}/like`, {
      headers: { 'x-access-token': token },
    });
    expect(unlikeResp.ok()).toBe(true);
    let unlikeData = await unlikeResp.json();
    if (typeof unlikeData === 'string') unlikeData = JSON.parse(unlikeData);
    if (firstAction === 'liked') {
      expect(unlikeData.action).toBe('unliked');
    } else {
      expect(unlikeData.action).toBe('liked');
    }
  });

  test('like comment without auth returns 403', async ({ page }) => {
    const resp = await page.request.post('/products/1/comments/1/like');
    expect(resp.status()).toBe(403);
  });
});

test.describe('Comment Like — UI Button', () => {

  test('like button visible on comment items in product detail', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const hasLikeBtn = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return false;
      const listField = item.shadowRoot.querySelector('.list-field[data-value="comments"]');
      if (!listField) return false;
      const commentItems = listField.querySelectorAll('ntt-item');
      if (!commentItems.length) return false;
      const firstComment = commentItems[0];
      if (!firstComment?.shadowRoot) return false;
      return !!firstComment.shadowRoot.querySelector('ntt-method[method="like"]');
    });
    expect(hasLikeBtn).toBe(true);
  });
});

test.describe('Favorites Page — Navigation', () => {

  test('favorites page renders ntt-favorites component', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    await page.evaluate(() => { window.location.hash = '#@favorites'; });
    await page.waitForTimeout(2000);

    const hasFavoritesComponent = await page.evaluate(() => {
      const router = document.querySelector('ntt-router');
      if (!router?.shadowRoot) return false;
      const content = router.shadowRoot.querySelector('.router-content');
      if (!content) return false;
      return !!content.querySelector('ntt-favorites');
    });
    expect(hasFavoritesComponent).toBe(true);
  });

  test('favorites page shows ProductLike list', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

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
      };
    });
    expect(listInfo.found).toBe(true);
    expect(listInfo.model).toBe('ProductLike');
  });
});

test.describe('Favorite — Edge Cases', () => {

  test('favorite count survives page reload', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Create product and favorite it
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Reload Fav ${Date.now()}`, price: 10 },
    });
    const product = await createResp.json();
    await page.request.post(`/products/${product.id}/favorite`, {
      headers: { 'x-access-token': token },
    });

    // Load the page, verify count
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, token);
    await page.goto(`${APP_URL}#Product/${product.id}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const countBefore = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return null;
      const method = item.shadowRoot.querySelector('ntt-method[method="favorite"]');
      if (!method?.shadowRoot) return null;
      const countEl = method.shadowRoot.querySelector('.method-btn-count');
      return countEl?.textContent ?? null;
    });

    // Reload
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    const countAfter = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return null;
      const method = item.shadowRoot.querySelector('ntt-method[method="favorite"]');
      if (!method?.shadowRoot) return null;
      const countEl = method.shadowRoot.querySelector('.method-btn-count');
      return countEl?.textContent ?? null;
    });

    expect(countBefore).toBe(countAfter);
  });
});
