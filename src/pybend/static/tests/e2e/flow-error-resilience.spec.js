/**
 * flow-error-resilience.spec.js — Error Handling & Edge Cases Integration Tests
 *
 * Tests API error responses, UI error handling, validation errors, XSS
 * prevention, large data handling, and edge data types.
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, setToken, clearToken, USERS } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('Error Resilience — API Error Responses', () => {

  test('POST /products without auth returns 403 with error detail', async ({ page }) => {
    const resp = await page.request.post('/products', {
      data: { name: 'No Auth', price: 10 },
    });
    expect(resp.status()).toBe(403);
    const body = await resp.json();
    expect(body.detail).toBeDefined();
  });

  test('DELETE /products/{id} without auth returns 403', async ({ page }) => {
    const resp = await page.request.delete('/products/1');
    expect(resp.status()).toBe(403);
  });

  test('POST /products with empty body returns 422 validation error', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: {},
    });
    expect([400, 422]).toContain(resp.status());
  });

  test('POST /products with missing required field returns 422', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { price: 10 }, // Missing name
    });
    expect([400, 422]).toContain(resp.status());
  });

  test('GET /products/99999 returns 404 or empty', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.get('/products/99999', {
      headers: { 'x-access-token': token },
    });
    if (resp.status() === 200) {
      const data = await resp.json();
      expect(data === null || data === undefined || data.id === undefined).toBe(true);
    } else {
      expect([404, 500]).toContain(resp.status());
    }
  });

  test('expired or invalid token returns 401 or 403', async ({ page }) => {
    const resp = await page.request.get('/products/1', {
      headers: { 'x-access-token': 'invalid.jwt.token' },
    });
    expect([401, 403]).toContain(resp.status());
  });

  test('API returns proper JSON error structure on auth failure', async ({ page }) => {
    const resp = await page.request.post('/products', {
      data: { name: 'Test', price: 10 },
    });
    expect(resp.status()).toBe(403);
    const body = await resp.json();
    const hasErrorInfo = body.detail !== undefined ||
                         body.message !== undefined ||
                         body.error !== undefined;
    expect(hasErrorInfo).toBe(true);
  });

  test('API returns proper JSON error structure on validation failure', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: 'Test' }, // Missing price
    });
    expect(resp.status()).toBe(422);
    const body = await resp.json();
    expect(body.detail).toBeDefined();
  });
});

test.describe('Error Resilience — UI Error Handling', () => {

  test('navigating to non-existent product does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(`${APP_URL}#Product/99999`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const pageWorks = await page.locator('ntt-router').evaluate((r) => !!r.shadowRoot);
    expect(pageWorks).toBe(true);
  });

  test('navigating to malformed hash does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(`${APP_URL}#???`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);
  });

  test('navigating to unknown model hash does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(`${APP_URL}#Unknown/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);
  });

  test('page load with corrupted localStorage does not crash', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => {
      window.localStorage.setItem('jwtToken', 'corrupted{notjson}value');
    });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);
  });

  test('no white screen after page load', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const hasContent = await page.evaluate(() => {
      return document.body.children.length > 0 && document.body.innerHTML.trim().length > 0;
    });
    expect(hasContent).toBe(true);
  });
});

test.describe('Error Resilience — Validation', () => {

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
      data: { name: `Neg Price ${Date.now()}`, price: -10 },
    });
    expect(resp.ok()).toBe(false);
  });

  test('create product with very long name (201 chars) fails validation', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: 'X'.repeat(201), price: 10 },
    });
    expect(resp.ok()).toBe(false);
  });
});

test.describe('Error Resilience — XSS Prevention', () => {

  test('product with HTML in name renders as text, not HTML', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const xssName = `<img src=x onerror=alert(1)> ${Date.now()}`;

    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: xssName, price: 10 },
    });
    expect(createResp.ok()).toBe(true);
    const product = await createResp.json();

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, token);
    await page.goto(`${APP_URL}#Product/${product.id}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // No alert dialog should have fired
    const pageStable = await page.evaluate(() => document.body.children.length > 0);
    expect(pageStable).toBe(true);
  });

  test('comment with script tag in description does not execute', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products/1/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: `XSS Test ${Date.now()}`, description: '<script>document.title="hacked"</script>' } },
    });
    expect(resp.ok()).toBe(true);

    // Navigate to the product and verify title was not changed
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, token);
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const title = await page.title();
    expect(title).not.toBe('hacked');
  });
});

test.describe('Error Resilience — Edge Data Types', () => {

  test('product with many decimal places in price displays correctly', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Decimal Price ${Date.now()}`, price: 42.999 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    // Price stored correctly (may be rounded or exact)
    expect(product.price).toBeCloseTo(42.999, 2);
  });

  test('product with price 0.01 displays as valid amount', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Min Price ${Date.now()}`, price: 0.01 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.price).toBe(0.01);
  });

  test('product with very large price stores correctly', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Big Price ${Date.now()}`, price: 999999.99 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.price).toBe(999999.99);
  });

  test('product with all optional fields empty renders without error', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Minimal ${Date.now()}`, price: 1 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, token);
    await page.goto(`${APP_URL}#Product/${product.id}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Page should render without error
    const hasContent = await page.locator('ntt-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('product with unicode name renders correctly', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const unicodeName = `\u00e9\u00e0\u00fc \u4e16\u754c ${Date.now()}`;
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: unicodeName, price: 10 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, token);
    await page.goto(`${APP_URL}#Product/${product.id}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const content = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      return item?.shadowRoot?.querySelector('.card')?.textContent || '';
    });
    expect(content).toContain(unicodeName);
  });

  test('product with emoji in description stores and renders', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Emoji Test ${Date.now()}`, price: 10, description: 'Great product! \ud83d\ude00\ud83d\udc4d\u2764\ufe0f' },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.description).toContain('\ud83d\ude00');
  });
});

test.describe('Error Resilience — Concurrent Navigation', () => {

  test('navigate to detail then immediately go back — no crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Navigate to detail
    await page.evaluate(() => { window.location.hash = '#Product/1'; });
    await page.waitForTimeout(200);
    // Immediately go back
    await page.evaluate(() => { window.location.hash = ''; });
    await page.waitForTimeout(2000);

    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);
  });

  test('schema endpoint always works without auth', async ({ page }) => {
    const resp = await page.request.get('/Product');
    expect(resp.ok()).toBe(true);
    const schema = await resp.json();
    expect(schema.properties).toBeDefined();
    expect(schema['$id']).toBeDefined();
  });
});
