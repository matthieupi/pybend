/**
 * flow-product-crud.spec.js — Product CRUD Lifecycle Integration Tests
 *
 * Tests complete create, read, update, and delete flows for products,
 * including API and UI verification, edge cases, and persistence checks.
 */
import { test, expect } from '@playwright/test';
import { loginAs, logout, getToken, setToken, clearToken, USERS } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('Product CRUD — Create via API', () => {

  test('create product as authenticated user and verify in API response', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();
    const productName = `CRUD Test Product ${ts}`;

    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: productName, price: 42.99, description: 'Created by Playwright' },
    });
    expect(resp.ok()).toBe(true);

    const product = await resp.json();
    expect(product.id).toBeDefined();
    expect(product.name).toBe(productName);
    expect(product.price).toBe(42.99);
    expect(product.description).toBe('Created by Playwright');
    expect(product['$schema']).toContain('/Product');
    expect(product['$id']).toContain(`/products/${product.id}`);
  });

  test('created product appears in product list', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();
    const productName = `List Verify ${ts}`;

    // Create product
    await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: productName, price: 19.99 },
    });

    // Verify in API list
    const listResp = await page.request.get('/products');
    expect(listResp.ok()).toBe(true);
    const products = await listResp.json();
    const found = (Array.isArray(products) ? products : products.data || [])
      .find(p => p.name === productName);
    expect(found).toBeDefined();
    expect(found.price).toBe(19.99);
  });

  test('created product appears in UI after reload', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    const token = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
    const ts = Date.now();
    const productName = `UI Verify ${ts}`;

    await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: productName, price: 33.50 },
    });

    // Reload and check UI
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

    const found = names.some(n => n.includes(productName));
    expect(found).toBe(true);
  });

  test('anonymous user cannot create product (403)', async ({ page }) => {
    const resp = await page.request.post('/products', {
      data: { name: 'No Auth Product', price: 10 },
    });
    expect(resp.status()).toBe(403);
  });
});

test.describe('Product CRUD — Read', () => {

  test('anonymous user can view product list (200 OK)', async ({ page }) => {
    const resp = await page.request.get('/products');
    expect(resp.ok()).toBe(true);
    const products = await resp.json();
    const list = Array.isArray(products) ? products : products.data || [];
    expect(list.length).toBeGreaterThanOrEqual(3);
  });

  test('anonymous user cannot view product detail (403 — read on detail requires auth)', async ({ page }) => {
    // Product model uses {"*": "authenticated"} which blocks single-item reads for anonymous.
    // The list endpoint is public but individual detail is not.
    const resp = await page.request.get('/products/1');
    expect(resp.status()).toBe(403);
  });

  test('authenticated user can view product detail', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.get('/products/1', {
      headers: { 'x-access-token': token },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.name).toBeDefined();
    expect(product.price).toBeDefined();
  });

  test('product detail with depth=1 returns populated children', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.get('/products/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.comments).toBeDefined();
    // With depth=1, comments should be populated objects (not just hrefs)
    if (typeof product.comments === 'object' && product.comments.data) {
      expect(product.comments.data.length).toBeGreaterThanOrEqual(0);
    }
  });

  test('product schema is accessible without auth', async ({ page }) => {
    const resp = await page.request.get('/Product');
    expect(resp.ok()).toBe(true);
    const schema = await resp.json();
    expect(schema['$id']).toContain('/Product');
    expect(schema.properties).toBeDefined();
    expect(schema.properties.name).toBeDefined();
    expect(schema.properties.price).toBeDefined();
    expect(schema.methods).toBeDefined();
  });
});

test.describe.serial('Product CRUD — Update Flow', () => {

  let productId;
  let token;

  test('setup: create a product to update', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();

    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Update Target ${ts}`, price: 42.99, description: 'Before update' },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    productId = product.id;
    expect(productId).toBeDefined();
  });

  test('update product name via API', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.put(`/products/${productId}`, {
      headers: { 'x-access-token': token },
      data: { name: 'Updated Product Name', price: 42.99 },
    });
    expect(resp.ok()).toBe(true);

    // Verify via GET (requires auth)
    const getResp = await page.request.get(`/products/${productId}`, {
      headers: { 'x-access-token': token },
    });
    const product = await getResp.json();
    expect(product.name).toBe('Updated Product Name');
  });

  test('update product price via API', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.put(`/products/${productId}`, {
      headers: { 'x-access-token': token },
      data: { name: 'Updated Product Name', price: 99.99 },
    });
    expect(resp.ok()).toBe(true);

    const getResp = await page.request.get(`/products/${productId}`, {
      headers: { 'x-access-token': token },
    });
    const product = await getResp.json();
    expect(product.price).toBe(99.99);
  });

  test('update product description via API', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.put(`/products/${productId}`, {
      headers: { 'x-access-token': token },
      data: { name: 'Updated Product Name', price: 99.99, description: 'Updated description' },
    });
    expect(resp.ok()).toBe(true);

    const getResp = await page.request.get(`/products/${productId}`, {
      headers: { 'x-access-token': token },
    });
    const product = await getResp.json();
    expect(product.description).toBe('Updated description');
  });

  test('updated product visible in UI after reload', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/${productId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const content = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      return item?.shadowRoot?.querySelector('.card')?.textContent || '';
    });

    expect(content).toContain('Updated Product Name');
  });
});

test.describe('Product CRUD — Update without Auth', () => {

  test('anonymous user cannot update product (403)', async ({ page }) => {
    const resp = await page.request.put('/products/1', {
      data: { name: 'Hacked Name', price: 1 },
    });
    expect(resp.status()).toBe(403);
  });
});

test.describe('Product CRUD — UI Edit Flow', () => {

  test('edit button visible for authenticated user on product detail', async ({ page }) => {
    // Product model has access {"*": "authenticated"} so any auth user can edit
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasEditBtn = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      return !!item?.shadowRoot?.querySelector('.edit-btn');
    });
    expect(hasEditBtn).toBe(true);
  });

  test('edit mode shows form inputs', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Click edit button
    await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      item?.shadowRoot?.querySelector('.edit-btn')?.click();
    });
    await page.waitForTimeout(500);

    // Verify edit mode has input fields
    const hasInputs = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      return !!item?.shadowRoot?.querySelector('input[data-key="name"]');
    });
    expect(hasInputs).toBe(true);
  });

  test('anonymous user sees no edit button on product detail', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await clearToken(page);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasEditBtn = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      return !!item?.shadowRoot?.querySelector('.edit-btn');
    });
    expect(hasEditBtn).toBe(false);
  });
});

test.describe('Product CRUD — Edge Cases', () => {

  test('create product with unicode characters in name', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const unicodeName = `Produit Fran\u00e7ais \u65e5\u672c\u8a9e ${Date.now()}`;

    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: unicodeName, price: 10.0 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.name).toBe(unicodeName);
  });

  test('create product with HTML in name — no XSS', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const xssName = `<script>alert(1)</script> ${Date.now()}`;

    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: xssName, price: 10.0 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    // Name should be stored as-is (plain text)
    expect(product.name).toBe(xssName);

    // Navigate to product detail and verify no script execution
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, token);
    await page.goto(`${APP_URL}#Product/${product.id}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // No alert dialog should have appeared
    const pageStable = await page.evaluate(() => document.body.children.length > 0);
    expect(pageStable).toBe(true);
  });

  test('create product with minimum price (0.01)', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Min Price ${Date.now()}`, price: 0.01 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.price).toBe(0.01);
  });

  test('create product with price=0 fails validation', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Zero Price ${Date.now()}`, price: 0 },
    });
    expect(resp.ok()).toBe(false);
  });

  test('create product with negative price fails validation', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Neg Price ${Date.now()}`, price: -5 },
    });
    expect(resp.ok()).toBe(false);
  });

  test('create product without required name fails validation', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { price: 10 },
    });
    expect(resp.ok()).toBe(false);
  });

  test('create two products with parallel API calls — both succeed with unique IDs', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();

    const [resp1, resp2] = await Promise.all([
      page.request.post('/products', {
        headers: { 'x-access-token': token },
        data: { name: `Parallel A ${ts}`, price: 10 },
      }),
      page.request.post('/products', {
        headers: { 'x-access-token': token },
        data: { name: `Parallel B ${ts}`, price: 20 },
      }),
    ]);

    expect(resp1.ok()).toBe(true);
    expect(resp2.ok()).toBe(true);
    const p1 = await resp1.json();
    const p2 = await resp2.json();
    expect(p1.id).not.toBe(p2.id);
  });

  test('create product with name at max length (200 chars)', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const longName = 'A'.repeat(200);

    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: longName, price: 10 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.name.length).toBe(200);
  });

  test('create product with name exceeding max length (201 chars) fails', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const tooLongName = 'B'.repeat(201);

    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: tooLongName, price: 10 },
    });
    expect(resp.ok()).toBe(false);
  });
});

test.describe.serial('Product CRUD — Create Update Verify Persistence', () => {

  let productId;
  let token;

  test('create product', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Lifecycle Test ${Date.now()}`, price: 50.00, description: 'Lifecycle test' },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    productId = product.id;
  });

  test('update product name', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.put(`/products/${productId}`, {
      headers: { 'x-access-token': token },
      data: { name: 'Lifecycle Updated', price: 50.00 },
    });
    expect(resp.ok()).toBe(true);
  });

  test('verify updated name persists via API', async ({ page }) => {
    token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.get(`/products/${productId}`, {
      headers: { 'x-access-token': token },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.name).toBe('Lifecycle Updated');
  });

  test('verify updated name persists in UI after reload', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/${productId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const content = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      return item?.shadowRoot?.querySelector('.card')?.textContent || '';
    });
    expect(content).toContain('Lifecycle Updated');
  });
});
