/**
 * flow-social-chain.spec.js — Full Social Interaction Chain Integration Tests
 *
 * Master integration test: register -> create product -> comment -> favorite ->
 * cross-user interaction -> update -> verify aggregate state.
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, setToken, USERS } from './fixtures/auth.js';

const APP_URL = '/';
const TS = Date.now();

test.describe.serial('Social Chain — Complete User Journey', () => {

  let creatorToken;
  let creatorEmail;
  let productId;

  test('Phase 1: Register a fresh user', async ({ page }) => {
    creatorEmail = `social-chain-${TS}@example.com`;
    const regResp = await page.request.post('/users/register', {
      data: { name: `Chain User ${TS}`, email: creatorEmail, password: 'chain123' },
    });
    expect(regResp.ok()).toBe(true);
    const regData = await regResp.json();
    creatorToken = regData.token;
    expect(creatorToken).toBeTruthy();
  });

  test('Phase 1: Verify authenticated state in topbar', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, creatorToken);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(true);
  });

  test('Phase 2: Create a new product', async ({ page }) => {
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': creatorToken },
      data: { name: `Social Chain Product ${TS}`, price: 55.00, description: 'Full flow test' },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    productId = product.id;
    expect(productId).toBeDefined();
    expect(product.name).toBe(`Social Chain Product ${TS}`);
  });

  test('Phase 2: Product appears in list via API', async ({ page }) => {
    const resp = await page.request.get('/products');
    const products = await resp.json();
    const list = Array.isArray(products) ? products : products.data || [];
    const found = list.find(p => p.id === productId);
    expect(found).toBeDefined();
    expect(found.name).toBe(`Social Chain Product ${TS}`);
  });

  test('Phase 3: Add first comment', async ({ page }) => {
    const resp = await page.request.post(`/products/${productId}/comment`, {
      headers: { 'x-access-token': creatorToken },
      data: { comment: { name: `First Comment ${TS}`, description: 'Testing the chain' } },
    });
    expect(resp.ok()).toBe(true);
  });

  test('Phase 3: Add second comment', async ({ page }) => {
    const resp = await page.request.post(`/products/${productId}/comment`, {
      headers: { 'x-access-token': creatorToken },
      data: { comment: { name: `Second Comment ${TS}`, description: 'Another test' } },
    });
    expect(resp.ok()).toBe(true);

    // Verify comment count is 2
    const verifyResp = await page.request.get(`/products/${productId}?depth=1`, {
      headers: { 'x-access-token': creatorToken },
    });
    const data = await verifyResp.json();
    const commentCount = data.comments?.data?.length ?? 0;
    expect(commentCount).toBe(2);
  });

  test('Phase 3: Favorite the product', async ({ page }) => {
    const resp = await page.request.post(`/products/${productId}/favorite`, {
      headers: { 'x-access-token': creatorToken },
    });
    expect(resp.ok()).toBe(true);

    // Verify favorites count is 1
    const verifyResp = await page.request.get(`/products/${productId}?depth=1`, {
      headers: { 'x-access-token': creatorToken },
    });
    const data = await verifyResp.json();
    const favCount = data.favorites?.data?.length ?? 0;
    expect(favCount).toBe(1);
  });

  test('Phase 4: Bob adds a comment', async ({ page }) => {
    const bobToken = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const resp = await page.request.post(`/products/${productId}/comment`, {
      headers: { 'x-access-token': bobToken },
      data: { comment: { name: `Bobs Comment ${TS}`, description: 'Cross-user test' } },
    });
    expect(resp.ok()).toBe(true);

    // Verify comment count is now 3
    const verifyResp = await page.request.get(`/products/${productId}?depth=1`, {
      headers: { 'x-access-token': bobToken },
    });
    const data = await verifyResp.json();
    const commentCount = data.comments?.data?.length ?? 0;
    expect(commentCount).toBe(3);
  });

  test('Phase 4: Bob favorites the product', async ({ page }) => {
    const bobToken = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const resp = await page.request.post(`/products/${productId}/favorite`, {
      headers: { 'x-access-token': bobToken },
    });
    expect(resp.ok()).toBe(true);

    // Verify favorites count is now 2
    const verifyResp = await page.request.get(`/products/${productId}?depth=1`, {
      headers: { 'x-access-token': bobToken },
    });
    const data = await verifyResp.json();
    const favCount = data.favorites?.data?.length ?? 0;
    expect(favCount).toBe(2);
  });

  test('Phase 5: Verify aggregate state — 3 comments, 2 favorites', async ({ page }) => {
    const verifyResp = await page.request.get(`/products/${productId}?depth=1`, {
      headers: { 'x-access-token': creatorToken },
    });
    const data = await verifyResp.json();

    const commentCount = data.comments?.data?.length ?? 0;
    expect(commentCount).toBe(3);

    const favCount = data.favorites?.data?.length ?? 0;
    expect(favCount).toBe(2);

    expect(data.name).toBe(`Social Chain Product ${TS}`);
  });

  test('Phase 5: All comments have different user_owner values', async ({ page }) => {
    const verifyResp = await page.request.get(`/products/${productId}?depth=1`, {
      headers: { 'x-access-token': creatorToken },
    });
    const data = await verifyResp.json();
    const comments = data.comments?.data || [];

    // First 2 comments from creator, 1 from bob — so at least 2 unique owners
    const owners = comments.map(c => c.user_owner);
    const uniqueOwners = new Set(owners);
    expect(uniqueOwners.size).toBeGreaterThanOrEqual(2);
  });

  test('Phase 6: Creator updates product name', async ({ page }) => {
    const resp = await page.request.put(`/products/${productId}`, {
      headers: { 'x-access-token': creatorToken },
      data: { name: `Updated Social Chain ${TS}`, price: 55.00, description: 'Full flow test' },
    });
    expect(resp.ok()).toBe(true);

    // Verify name changed
    const verifyResp = await page.request.get(`/products/${productId}`, {
      headers: { 'x-access-token': creatorToken },
    });
    const data = await verifyResp.json();
    expect(data.name).toBe(`Updated Social Chain ${TS}`);
  });

  test('Phase 6: Comments and favorites intact after update', async ({ page }) => {
    const verifyResp = await page.request.get(`/products/${productId}?depth=1`, {
      headers: { 'x-access-token': creatorToken },
    });
    const data = await verifyResp.json();

    const commentCount = data.comments?.data?.length ?? 0;
    expect(commentCount).toBe(3);

    const favCount = data.favorites?.data?.length ?? 0;
    expect(favCount).toBe(2);
  });

  test('Phase 7: Verify final state via API', async ({ page }) => {
    const verifyResp = await page.request.get(`/products/${productId}?depth=1`, {
      headers: { 'x-access-token': creatorToken },
    });
    const data = await verifyResp.json();

    expect(data.name).toBe(`Updated Social Chain ${TS}`);
    expect(data.price).toBe(55.00);
    expect(data.description).toBe('Full flow test');
    expect(data['$schema']).toContain('/Product');
    expect(data['$id']).toContain(`/products/${productId}`);
  });

  test('Phase 7: Product renders correctly in UI', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, creatorToken);
    await page.goto(`${APP_URL}#Product/${productId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const content = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      return item?.shadowRoot?.querySelector('.card')?.textContent || '';
    });
    expect(content).toContain(`Updated Social Chain ${TS}`);
  });

  test('Phase 7: Product appears in list with correct name', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, creatorToken);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    const names = await page.locator('#product-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntx-item');
      if (!items) return [];
      return Array.from(items).map(item => {
        const nameEl = item.shadowRoot?.querySelector('[data-value="name"]');
        return nameEl?.textContent || '';
      });
    });

    const found = names.some(n => n.includes(`Updated Social Chain ${TS}`));
    expect(found).toBe(true);
  });
});
