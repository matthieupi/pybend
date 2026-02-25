/**
 * flow-data-integrity.spec.js — Data Integrity & Consistency Integration Tests
 *
 * Verifies data consistency across UI and API: create/update/verify everywhere,
 * schema consistency, pagination, FK integrity, and concurrent modifications.
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, setToken, clearToken, USERS } from './fixtures/auth.js';

const APP_URL = '/matrix.html';

test.describe('Data Integrity — Create and Verify Everywhere', () => {

  test('created product has consistent data across API and UI', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();
    const productName = `Integrity Test ${ts}`;

    // Create via API
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: productName, price: 42.99, description: 'Integrity check' },
    });
    expect(createResp.ok()).toBe(true);
    const product = await createResp.json();
    const pid = product.id;

    // Verify $schema and $id
    expect(product['$schema']).toContain('/Product');
    expect(product['$id']).toContain(`/products/${pid}`);

    // Verify via API GET
    const getResp = await page.request.get(`/products/${pid}`, {
      headers: { 'x-access-token': token },
    });
    const getProduct = await getResp.json();
    expect(getProduct.name).toBe(productName);
    expect(getProduct.price).toBe(42.99);
    expect(getProduct.description).toBe('Integrity check');
    expect(getProduct.id).toBe(pid);

    // Verify in list API
    const listResp = await page.request.get('/products');
    const listProducts = await listResp.json();
    const list = Array.isArray(listProducts) ? listProducts : listProducts.data || [];
    const inList = list.find(p => p.id === pid);
    expect(inList).toBeDefined();
    expect(inList.name).toBe(productName);

    // Verify in UI
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, token);
    await page.goto(`${APP_URL}#Product/${pid}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const content = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      return item?.shadowRoot?.querySelector('.card')?.textContent || '';
    });
    expect(content).toContain(productName);
  });
});

test.describe.serial('Data Integrity — Update and Verify Everywhere', () => {

  let pid;
  let token;

  test('setup: create product', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Update Integrity ${Date.now()}`, price: 50.00 },
    });
    const product = await resp.json();
    pid = product.id;
  });

  test('update name — consistent in API GET', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    await page.request.put(`/products/${pid}`, {
      headers: { 'x-access-token': token },
      data: { name: 'Updated Integrity Name', price: 50.00 },
    });

    const resp = await page.request.get(`/products/${pid}`, {
      headers: { 'x-access-token': token },
    });
    const product = await resp.json();
    expect(product.name).toBe('Updated Integrity Name');
    expect(product.id).toBe(pid); // ID unchanged
  });

  test('update price — format consistent', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    await page.request.put(`/products/${pid}`, {
      headers: { 'x-access-token': token },
      data: { name: 'Updated Integrity Name', price: 75.50 },
    });

    const resp = await page.request.get(`/products/${pid}`, {
      headers: { 'x-access-token': token },
    });
    const product = await resp.json();
    expect(product.price).toBe(75.5);
  });

  test('update reflected in list view', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, token);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    const names = await page.locator('ntt-list').evaluate((list) => {
      const items = list.shadowRoot?.querySelectorAll('ntt-item');
      if (!items) return [];
      return Array.from(items).map(item => {
        const nameEl = item.shadowRoot?.querySelector('[data-value="name"]');
        return nameEl?.textContent || '';
      });
    });
    const found = names.some(n => n.includes('Updated Integrity Name'));
    expect(found).toBe(true);
  });
});

test.describe('Data Integrity — Comment FK Relationship', () => {

  test('comment belongs to correct product', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();

    // Create product
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `FK Test ${ts}`, price: 10 },
    });
    const product = await createResp.json();
    const pid = product.id;

    // Add comment to this product
    await page.request.post(`/products/${pid}/comment`, {
      headers: { 'x-access-token': token },
      data: { comment: { name: `FK Comment ${ts}`, description: 'Testing FK' } },
    });

    // Verify comment appears in this product's comments
    const prodResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': token },
    });
    const prodData = await prodResp.json();
    const comments = prodData.comments?.data || [];
    const found = comments.find(c => c.name === `FK Comment ${ts}`);
    expect(found).toBeDefined();
  });

  test('comment $schema and $id URLs are correct', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const resp = await page.request.get('/products/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    const data = await resp.json();
    const comments = data.comments?.data || [];
    expect(comments.length).toBeGreaterThanOrEqual(1);

    const firstComment = comments[0];
    // Join model is named ProductComment, so $schema contains that
    expect(firstComment['$schema']).toContain('/ProductComment');
    expect(firstComment['$id']).toContain('/products/1/comments/');
  });

  test('comment user_owner matches the commenter', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const meResp = await page.request.get('/auth/me', {
      headers: { 'x-access-token': token },
    });
    const me = await meResp.json();

    const ts = Date.now();
    await page.request.post('/products/2/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: `Owner Verify ${ts}`, description: 'Testing' } },
    });

    const resp = await page.request.get('/products/2?depth=1', {
      headers: { 'x-access-token': token },
    });
    const data = await resp.json();
    const comments = data.comments?.data || [];
    const myComment = comments.find(c => c.name === `Owner Verify ${ts}`);
    expect(myComment).toBeDefined();
    // user_owner in depth=1 response is an href string like "http://localhost:5000/users/1"
    // me.user_id is the numeric ID, so check that the href contains the user ID
    const ownerVal = myComment.user_owner;
    if (typeof ownerVal === 'string') {
      expect(ownerVal).toContain(`/users/${me.user_id}`);
    } else {
      expect(ownerVal).toBe(me.user_id);
    }
  });
});

test.describe('Data Integrity — Favorite Relationship', () => {

  test('favorite belongs to correct product', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();

    // Create two products
    const resp1 = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Fav Integrity A ${ts}`, price: 10 },
    });
    const productA = await resp1.json();

    const resp2 = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Fav Integrity B ${ts}`, price: 20 },
    });
    const productB = await resp2.json();

    // Favorite only product A
    await page.request.post(`/products/${productA.id}/favorite`, {
      headers: { 'x-access-token': token },
    });

    // Verify A has favorite, B does not
    const dataA = await (await page.request.get(`/products/${productA.id}?depth=1`, {
      headers: { 'x-access-token': token },
    })).json();
    const dataB = await (await page.request.get(`/products/${productB.id}?depth=1`, {
      headers: { 'x-access-token': token },
    })).json();

    const favCountA = dataA.favorites?.data?.length ?? 0;
    const favCountB = dataB.favorites?.data?.length ?? 0;
    expect(favCountA).toBe(1);
    expect(favCountB).toBe(0);
  });
});

test.describe('Data Integrity — Schema Consistency', () => {

  test('schema properties match entity data structure', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Get schema
    const schemaResp = await page.request.get('/Product');
    const schema = await schemaResp.json();
    const schemaProps = Object.keys(schema.properties);

    // Get entity
    const entityResp = await page.request.get('/products/1', {
      headers: { 'x-access-token': token },
    });
    const entity = await entityResp.json();
    const entityKeys = Object.keys(entity).filter(k => !k.startsWith('$'));

    // Every entity field should exist in schema (excluding $schema and $id)
    for (const key of entityKeys) {
      expect(schemaProps).toContain(key);
    }
  });

  test('schema methods match available API endpoints', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const schemaResp = await page.request.get('/Product');
    const schema = await schemaResp.json();
    const methods = Object.keys(schema.methods || {});

    // Each method should be callable
    for (const method of methods) {
      const methodDef = schema.methods[method];
      expect(methodDef.route).toBeDefined();
      expect(methodDef.scope).toBeDefined();
    }

    // comment and favorite should be available
    expect(methods).toContain('comment');
    expect(methods).toContain('favorite');
  });

  test('required fields in schema are always present in entity data', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const schemaResp = await page.request.get('/Product');
    const schema = await schemaResp.json();
    const required = schema.required || [];

    const entityResp = await page.request.get('/products/1', {
      headers: { 'x-access-token': token },
    });
    const entity = await entityResp.json();

    for (const field of required) {
      expect(entity[field]).toBeDefined();
    }
  });

  test('$defs schemas match their entity data structures', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    const schemaResp = await page.request.get('/Product');
    const schema = await schemaResp.json();

    const commentDef = schema.$defs?.Comment;
    expect(commentDef).toBeDefined();
    expect(commentDef.properties).toBeDefined();

    // Get an actual comment
    const prodResp = await page.request.get('/products/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    const prodData = await prodResp.json();
    const comments = prodData.comments?.data || [];
    if (comments.length > 0) {
      const commentKeys = Object.keys(comments[0]).filter(k => !k.startsWith('$') && k !== 'product_id');
      const defKeys = Object.keys(commentDef.properties);
      // Every comment field should exist in $defs
      for (const key of commentKeys) {
        expect(defKeys).toContain(key);
      }
    }
  });
});

test.describe('Data Integrity — Unique IDs', () => {

  test('all products have unique IDs', async ({ page }) => {
    const resp = await page.request.get('/products');
    const products = await resp.json();
    const list = Array.isArray(products) ? products : products.data || [];
    const ids = list.map(p => p.id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(ids.length);
  });
});

test.describe('Data Integrity — Concurrent Modifications', () => {

  test('two users can interact with the same product without data corruption', async ({ page }) => {
    const aliceToken = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const bobToken = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const ts = Date.now();

    // Create a product
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': aliceToken },
      data: { name: `Concurrent Test ${ts}`, price: 100 },
    });
    const product = await createResp.json();
    const pid = product.id;

    // Alice updates the product while Bob comments on it (in parallel)
    const [updateResp, commentResp] = await Promise.all([
      page.request.put(`/products/${pid}`, {
        headers: { 'x-access-token': aliceToken },
        data: { name: `Concurrent Updated ${ts}`, price: 100 },
      }),
      page.request.post(`/products/${pid}/comment`, {
        headers: { 'x-access-token': bobToken },
        data: { comment: { name: `Bob Concurrent ${ts}`, description: 'Concurrent test' } },
      }),
    ]);

    expect(updateResp.ok()).toBe(true);
    expect(commentResp.ok()).toBe(true);

    // Verify both changes persisted
    const verifyResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': aliceToken },
    });
    const verifyData = await verifyResp.json();
    expect(verifyData.name).toBe(`Concurrent Updated ${ts}`);
    const comments = verifyData.comments?.data || [];
    const bobComment = comments.find(c => c.name === `Bob Concurrent ${ts}`);
    expect(bobComment).toBeDefined();
  });

  test('rapid create-update cycle produces consistent final state', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();

    // Create
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Rapid Cycle ${ts}`, price: 10 },
    });
    const product = await createResp.json();
    const pid = product.id;

    // Update twice in sequence
    await page.request.put(`/products/${pid}`, {
      headers: { 'x-access-token': token },
      data: { name: `Rapid Cycle Updated 1 ${ts}`, price: 20 },
    });

    await page.request.put(`/products/${pid}`, {
      headers: { 'x-access-token': token },
      data: { name: `Rapid Cycle Final ${ts}`, price: 30 },
    });

    // Verify final state
    const verifyResp = await page.request.get(`/products/${pid}`, {
      headers: { 'x-access-token': token },
    });
    const verifyData = await verifyResp.json();
    expect(verifyData.name).toBe(`Rapid Cycle Final ${ts}`);
    expect(verifyData.price).toBe(30);
  });
});
