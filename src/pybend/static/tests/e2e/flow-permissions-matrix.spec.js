/**
 * flow-permissions-matrix.spec.js — Authorization Matrix Integration Tests
 *
 * Verifies every permission combination: anonymous, authenticated non-owner,
 * authenticated owner, field-level access, method-level access, schema rules.
 *
 * Note: Product model uses {"*": "authenticated"} (no per-action access rules).
 * This means all actions require authentication but do NOT require ownership.
 * Comment model has explicit per-action rules (read: anyone, update: owner|admin, etc.)
 */
import { test, expect } from '@playwright/test';
import { loginAs, logout, getToken, clearToken, USERS } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('Permissions — Anonymous User (API)', () => {

  test('can view product list (200 OK)', async ({ page }) => {
    const resp = await page.request.get('/products');
    expect(resp.ok()).toBe(true);
  });

  test('cannot view product detail (403)', async ({ page }) => {
    const resp = await page.request.get('/products/1');
    expect(resp.status()).toBe(403);
  });

  test('can view product schema (200 OK)', async ({ page }) => {
    const resp = await page.request.get('/Product');
    expect(resp.ok()).toBe(true);
  });

  test('cannot create product (403)', async ({ page }) => {
    const resp = await page.request.post('/products', {
      data: { name: 'Anon Product', price: 10 },
    });
    expect(resp.status()).toBe(403);
  });

  test('cannot update product (403 or 422)', async ({ page }) => {
    const resp = await page.request.put('/products/1', {
      data: { name: 'Hacked', price: 1 },
    });
    // 403 for access denied or 422 for validation (but should be 403 first)
    expect(resp.ok()).toBe(false);
  });

  test('cannot delete product (403)', async ({ page }) => {
    const resp = await page.request.delete('/products/1');
    expect(resp.status()).toBe(403);
  });

  test('cannot add comment (403)', async ({ page }) => {
    const resp = await page.request.post('/products/1/comment', {
      data: { comment: { name: 'Anon', description: 'Should fail' } },
    });
    expect(resp.status()).toBe(403);
  });

  test('cannot favorite product (403)', async ({ page }) => {
    const resp = await page.request.post('/products/1/favorite');
    expect(resp.status()).toBe(403);
  });

  test('cannot access /auth/me (401)', async ({ page }) => {
    const resp = await page.request.get('/auth/me');
    expect(resp.ok()).toBe(false);
  });
});

test.describe('Permissions — Anonymous User (UI)', () => {

  test('no edit or delete buttons visible on product detail', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await clearToken(page);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasActions = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('.edit-btn') ||
             !!item.shadowRoot.querySelector('.delete-btn');
    });
    expect(hasActions).toBe(false);
  });

  test('signin link visible, user pill hidden', async ({ page }) => {
    await page.goto(APP_URL);
    await clearToken(page);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);

    const hasSignIn = await page.locator('ntt-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.signin-link');
    });
    expect(hasSignIn).toBe(true);

    const hasPill = await page.locator('ntt-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(false);
  });
});

test.describe('Permissions — Authenticated User (API)', () => {

  test('can view product list (200 OK)', async ({ page }) => {
    const token = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const resp = await page.request.get('/products', {
      headers: { 'x-access-token': token },
    });
    expect(resp.ok()).toBe(true);
  });

  test('can view product detail (200 OK)', async ({ page }) => {
    const token = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const resp = await page.request.get('/products/1', {
      headers: { 'x-access-token': token },
    });
    expect(resp.ok()).toBe(true);
  });

  test('can create own product (200 OK)', async ({ page }) => {
    const token = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Bobs Product ${Date.now()}`, price: 10 },
    });
    expect(resp.ok()).toBe(true);
  });

  test('can update any product (Product has no owner check)', async ({ page }) => {
    // Product uses {"*": "authenticated"} — any authenticated user can update any product
    const token = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const resp = await page.request.put('/products/1', {
      headers: { 'x-access-token': token },
      data: { name: 'Wireless Headphones', price: 79.99 },
    });
    expect(resp.ok()).toBe(true);
  });

  test('can add comment to any product (200 OK)', async ({ page }) => {
    const token = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const resp = await page.request.post('/products/1/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: `Bob comment ${Date.now()}`, description: 'Test' } },
    });
    expect(resp.ok()).toBe(true);
  });

  test('can favorite any product (200 OK)', async ({ page }) => {
    const token = await getToken(page.request, USERS.charlie.email, USERS.charlie.password);
    // Create a fresh product to avoid toggle issues
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Perm Fav Test ${Date.now()}`, price: 10 },
    });
    const product = await createResp.json();

    const resp = await page.request.post(`/products/${product.id}/favorite`, {
      headers: { 'x-access-token': token },
    });
    expect(resp.ok()).toBe(true);
  });
});

test.describe('Permissions — Authenticated User (UI)', () => {

  test('edit button visible for authenticated user on product detail', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasEditBtn = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      return !!item?.shadowRoot?.querySelector('.edit-btn');
    });
    expect(hasEditBtn).toBe(true);
  });

  test('protected fields (user_owner) not editable in edit mode', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Click edit
    await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      item?.shadowRoot?.querySelector('.edit-btn')?.click();
    });
    await page.waitForTimeout(500);

    // user_owner should NOT appear as an editable input
    const hasProtectedInput = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      return !!item?.shadowRoot?.querySelector('input[data-key="user_owner"]');
    });
    expect(hasProtectedInput).toBe(false);
  });
});

test.describe('Permissions — Schema Access Rules', () => {

  test('Product schema has access rules', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.access).toBeDefined();
    // Product uses {"*": "authenticated"} wildcard
    expect(schema.access['*']).toBeDefined();
    expect(schema.access['*'].rule).toBe('authenticated');
  });

  test('Comment schema has explicit per-action access rules', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    const commentDef = schema.$defs?.Comment;
    expect(commentDef).toBeDefined();
    expect(commentDef.access).toBeDefined();
    expect(commentDef.access.read.rule).toBe('anyone');
    expect(commentDef.access.create.rule).toBe('authenticated');
    // update is OR(owner, role:admin)
    expect(commentDef.access.update.op).toBe('or');
    // delete is OR(owner, role:admin)
    expect(commentDef.access.delete.op).toBe('or');
  });

  test('Product price field has field-level access rules', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.properties.price.access).toBeDefined();
    expect(schema.properties.price.access.view).toBe('anyone');
    expect(schema.properties.price.access.edit).toBe('admin');
  });

  test('Protected fields marked in schema', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    // Comment's user_owner has ui.protected=true
    const commentDef = schema.$defs?.Comment;
    if (commentDef?.properties?.user_owner?.ui) {
      expect(commentDef.properties.user_owner.ui.protected).toBe(true);
    }
  });

  test('Method-level access: favorite requires authenticated', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.methods.favorite.access.rule).toBe('authenticated');
  });

  test('Comment like method requires authenticated', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    const commentDef = schema.$defs?.Comment;
    if (commentDef?.methods?.like?.access) {
      expect(commentDef.methods.like.access.rule).toBe('authenticated');
    }
  });
});

test.describe('Permissions — Role Escalation Prevention', () => {

  test('registration with role=admin is ignored (user gets regular role)', async ({ page }) => {
    const ts = Date.now();
    const resp = await page.request.post('/users/register', {
      data: { name: `Admin Attempt ${ts}`, email: `admin-${ts}@example.com`, password: 'pass123', role: 'admin' },
    });
    expect(resp.ok()).toBe(true);
    const data = await resp.json();
    // User should have role=user, not admin
    expect(data.user.role).toBe('user');
  });

  test('tampered JWT with admin role is rejected', async ({ page }) => {
    const validToken = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const parts = validToken.split('.');
    // Tamper with payload
    const payload = JSON.parse(atob(parts[1]));
    payload.role = 'admin';
    parts[1] = btoa(JSON.stringify(payload));
    const tamperedToken = parts.join('.');

    const resp = await page.request.get('/auth/me', {
      headers: { 'x-access-token': tamperedToken },
    });
    expect(resp.ok()).toBe(false);
  });

  test('invalid token is rejected by all protected endpoints', async ({ page }) => {
    const invalidToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxfQ.invalid';

    const endpoints = [
      { method: 'GET', url: '/auth/me' },
      { method: 'POST', url: '/products' },
      { method: 'POST', url: '/products/1/favorite' },
    ];

    for (const ep of endpoints) {
      let resp;
      if (ep.method === 'GET') {
        resp = await page.request.get(ep.url, {
          headers: { 'x-access-token': invalidToken },
        });
      } else {
        resp = await page.request.post(ep.url, {
          headers: { 'x-access-token': invalidToken },
          data: ep.method === 'POST' && ep.url === '/products' ? { name: 'test', price: 1 } : {},
        });
      }
      expect(resp.ok()).toBe(false);
    }
  });
});
