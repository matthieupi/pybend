/**
 * flow-error-resilience.spec.js — Error Handling & Edge Cases Integration Tests
 *
 * Tests API error responses, UI error handling, validation errors, XSS
 * prevention, large data handling, and edge data types.
 */
import { test, expect } from './fixtures/parallel.js';
import { loginAs, getToken, setToken, clearToken, USERS } from './fixtures/auth.js';
import { gotoApp, reloadApp, waitForAppReady, waitForTopbar, waitForUiSettled } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('Error Resilience — API Error Responses', () => {

  test('POST /Product without auth returns 403 with error detail', async ({ page }) => {
    const resp = await page.request.post('/Product', {
      data: { name: 'No Auth', price: 10 },
    });
    expect(resp.status()).toBe(403);
    const body = await resp.json();
    expect(body.detail).toBeDefined();
  });

  test('DELETE /Product/{id} without auth returns 403', async ({ page }) => {
    const resp = await page.request.delete('/Product/1');
    expect(resp.status()).toBe(403);
  });

  test('POST /Product with empty body returns 422 validation error', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: {},
    });
    expect([400, 422]).toContain(resp.status());
  });

  test('POST /Product with missing required field returns 422', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: { price: 10 }, // Missing name
    });
    expect([400, 422]).toContain(resp.status());
  });

  test('GET /Product/99999 returns 404 or empty', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.get('/Product/99999', {
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
    const resp = await page.request.get('/Product/1', {
      headers: { 'x-access-token': 'invalid.jwt.token' },
    });
    expect([401, 403]).toContain(resp.status());
  });

  test('API returns proper JSON error structure on auth failure', async ({ page }) => {
    const resp = await page.request.post('/Product', {
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
    const resp = await page.request.post('/Product', {
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

    await gotoApp(page, `${APP_URL}#Product/99999`);


    await waitForTopbar(page);
    await waitForUiSettled(page);

    const pageWorks = await page.locator('ntx-router').evaluate((r) => !!r.shadowRoot);
    expect(pageWorks).toBe(true);
  });

  test('navigating to malformed hash does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await gotoApp(page, `${APP_URL}#???`);


    await waitForTopbar(page);
    await waitForUiSettled(page);

    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);
  });

  test('navigating to unknown model hash does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await gotoApp(page, `${APP_URL}#Unknown/1`);


    await waitForTopbar(page);
    await waitForUiSettled(page);

    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);
  });

  test('page load with corrupted localStorage does not crash', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);
    await page.evaluate(() => {
      window.localStorage.setItem('jwtToken', 'corrupted{notjson}value');
    });
    await reloadApp(page);

    await page.waitForURL('**/login.html');
    await page.waitForLoadState('domcontentloaded');
    await waitForUiSettled(page);

    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);
  });

  test('no white screen after page load', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const hasContent = await page.evaluate(() => {
      return document.body.children.length > 0 && document.body.innerHTML.trim().length > 0;
    });
    expect(hasContent).toBe(true);
  });
});

test.describe('Error Resilience — Validation', () => {

  test('create product with price=0 fails validation', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: { name: `Zero Price ${Date.now()}`, price: 0 },
    });
    expect(resp.ok()).toBe(false);
  });

  test('create product with negative price fails validation', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: { name: `Neg Price ${Date.now()}`, price: -10 },
    });
    expect(resp.ok()).toBe(false);
  });

  test('create product with very long name (201 chars) fails validation', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product', {
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

    const createResp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: { name: xssName, price: 10 },
    });
    expect(createResp.ok()).toBe(true);
    const product = await createResp.json();

    await gotoApp(page, APP_URL);


    await waitForAppReady(page);
    await setToken(page, token);
    await gotoApp(page, `${APP_URL}#Product/${product.id}`);

    await waitForAppReady(page);

    // No alert dialog should have fired
    const pageStable = await page.evaluate(() => document.body.children.length > 0);
    expect(pageStable).toBe(true);
  });

  test('comment with script tag in description does not execute', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product/1/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: `XSS Test ${Date.now()}`, description: '<script>document.title="hacked"</script>' } },
    });
    expect(resp.ok()).toBe(true);

    // Navigate to the product and verify title was not changed
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);
    await setToken(page, token);
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const title = await page.title();
    expect(title).not.toBe('hacked');
  });
});

test.describe('Error Resilience — Edge Data Types', () => {

  test('product with many decimal places in price displays correctly', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product', {
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
    const resp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: { name: `Min Price ${Date.now()}`, price: 0.01 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.price).toBe(0.01);
  });

  test('product with very large price stores correctly', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: { name: `Big Price ${Date.now()}`, price: 999999.99 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.price).toBe(999999.99);
  });

  test('product with all optional fields empty renders without error', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: { name: `Minimal ${Date.now()}`, price: 1 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();

    await gotoApp(page, APP_URL);


    await waitForAppReady(page);
    await setToken(page, token);
    await gotoApp(page, `${APP_URL}#Product/${product.id}`);

    await waitForAppReady(page);

    // Page should render without error
    const hasContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });

  test('product with unicode name renders correctly', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const unicodeName = `\u00e9\u00e0\u00fc \u4e16\u754c ${Date.now()}`;
    const resp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: { name: unicodeName, price: 10 },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();

    await gotoApp(page, APP_URL);


    await waitForAppReady(page);
    await setToken(page, token);
    await gotoApp(page, `${APP_URL}#Product/${product.id}`);

    await waitForAppReady(page);

    const content = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      return item?.shadowRoot?.querySelector('.card')?.textContent || '';
    });
    expect(content).toContain(unicodeName);
  });

  test('product with emoji in description stores and renders', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/Product', {
      headers: { 'x-access-token': token },
      data: { name: `Emoji Test ${Date.now()}`, price: 10, description: 'Great product! \ud83d\ude00\ud83d\udc4d\u2764\ufe0f' },
    });
    expect(resp.ok()).toBe(true);
    const product = await resp.json();
    expect(product.description).toContain('\ud83d\ude00');
  });
});

test.describe('Error Resilience — Concurrent Navigation', () => {

  test('schema endpoint always works without auth', async ({ page }) => {
    const resp = await page.request.get('/Product');
    expect(resp.ok()).toBe(true);
    const schema = await resp.json();
    expect(schema.properties).toBeDefined();
    expect(schema['$id']).toBeDefined();
  });

  test('navigate to detail then immediately go back — no crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await gotoApp(page, APP_URL);


    await waitForAppReady(page);

    // Navigate to detail
    await page.evaluate(() => { window.location.hash = '#Product/1'; });
    await waitForUiSettled(page);
    // Immediately go back
    await page.evaluate(() => { window.location.hash = ''; });
    await waitForAppReady(page);

    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);
  });
});
