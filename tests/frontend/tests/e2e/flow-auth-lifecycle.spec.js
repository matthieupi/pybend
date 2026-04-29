/**
 * flow-auth-lifecycle.spec.js — Authentication Lifecycle Integration Tests
 *
 * Tests complete user journeys: registration, login, session persistence,
 * logout, multi-user switching, and token edge cases.
 */
import { test, expect } from './fixtures/parallel.js';
import { loginAs, logout, getToken, setToken, clearToken, USERS, authPayload } from './fixtures/auth.js';
import { gotoApp, reloadApp, waitForAppReady, waitForUiSettled } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('Auth Lifecycle — Registration Flow', () => {

  test('register a new user via API and login with those credentials', async ({ page }) => {
    const ts = Date.now();
    const email = `flow-reg-${ts}@example.com`;

    // Register
    const regResp = await page.request.post('/users/register', {
      data: { name: `FlowUser ${ts}`, email, password: 'testpass123' },
    });
    expect(regResp.ok()).toBe(true);
    const regData = await regResp.json();
    const registered = authPayload(regData);
    expect(registered.token).toBeTruthy();
    expect(registered.user).toBeDefined();
    expect(registered.user.email).toBe(email);

    // Login with the newly registered credentials
    const loginResp = await page.request.post('/users/login', {
      data: { email, password: 'testpass123' },
    });
    expect(loginResp.ok()).toBe(true);
    const loginData = await loginResp.json();
    const loggedIn = authPayload(loginData);
    expect(loggedIn.token).toBeTruthy();

    // Set token and verify in UI
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);
    await setToken(page, loggedIn.token);
    await reloadApp(page);

    await waitForAppReady(page);

    const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(true);

    // Verify /auth/me returns correct data
    const meResp = await page.request.get('/auth/me', {
      headers: { 'x-access-token': loggedIn.token },
    });
    expect(meResp.ok()).toBe(true);
    const meData = await meResp.json();
    expect(meData.email).toBe(email);
  });

  test('register with empty name — backend accepts it (no server-side validation)', async ({ page }) => {
    // BUG: Backend does not validate empty name on registration. It accepts it and returns a token.
    const ts = Date.now();
    const resp = await page.request.post('/users/register', {
      data: { name: '', email: `empty-name-${ts}@example.com`, password: 'pass123' },
    });
    // Current behavior: succeeds (200 OK) despite empty name
    expect(resp.ok()).toBe(true);
    const data = await resp.json();
    expect(authPayload(data).token).toBeTruthy();
  });

  test('register with duplicate email returns 409 conflict', async ({ page }) => {
    // First registration with a unique email
    const email = `dup-check-${Date.now()}@example.com`;
    const firstResp = await page.request.post('/users/register', {
      data: { name: 'First', email, password: 'pass123' },
    });
    expect(firstResp.ok()).toBe(true);

    // Second registration with the same email
    const secondResp = await page.request.post('/users/register', {
      data: { name: 'Second', email, password: 'pass456' },
    });
    expect(secondResp.status()).toBe(409);
    const body = await secondResp.json();
    expect(body.detail).toContain('already registered');
  });

  test('register with empty password — backend accepts it (no server-side validation)', async ({ page }) => {
    // BUG: Backend does not validate empty password on registration.
    const resp = await page.request.post('/users/register', {
      data: { name: 'Test', email: `no-pass-${Date.now()}@example.com`, password: '' },
    });
    // Current behavior: succeeds despite empty password
    expect(resp.ok()).toBe(true);
  });
});

test.describe('Auth Lifecycle — Login Flow', () => {

  test('login as alice via API returns valid JWT token', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    expect(token).toBeTruthy();
    expect(typeof token).toBe('string');
    // JWT has 3 parts separated by dots
    expect(token.split('.').length).toBe(3);
  });

  test('login sets localStorage token and topbar shows user pill', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    // Check localStorage
    const storedToken = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
    expect(storedToken).toBeTruthy();
    expect(storedToken.split('.').length).toBe(3);

    // Check topbar
    const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(true);
  });

  test('authenticated API call succeeds, unauthenticated call returns 403', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Authenticated call
    const authResp = await page.request.post('/products', {
      headers: { 'x-access-token': token },
      data: { name: `Auth Test ${Date.now()}`, price: 10.0 },
    });
    expect(authResp.ok()).toBe(true);

    // Unauthenticated call (same endpoint)
    const noAuthResp = await page.request.post('/products', {
      data: { name: 'No Auth', price: 10.0 },
    });
    expect(noAuthResp.status()).toBe(403);
  });

  test('login with wrong password fails', async ({ page }) => {
    const resp = await page.request.post('/users/login', {
      data: { email: USERS.alice.email, password: 'wrongpassword' },
    });
    const json = await resp.json();
    expect(json.token).toBeUndefined();
  });

  test('login with non-existent email fails', async ({ page }) => {
    const resp = await page.request.post('/users/login', {
      data: { email: 'nonexistent@example.com', password: 'somepass' },
    });
    const json = await resp.json();
    expect(json.token).toBeUndefined();
  });

  test('login with empty credentials fails', async ({ page }) => {
    const resp = await page.request.post('/users/login', {
      data: { email: '', password: '' },
    });
    const json = await resp.json();
    expect(json.token).toBeUndefined();
  });
});

test.describe('Auth Lifecycle — Session Persistence', () => {

  test('token survives page reload and topbar stays authenticated', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    // One reload is enough to validate persistence while keeping the full suite deterministic.
    for (let i = 0; i < 1; i++) {
      await reloadApp(page);

      await waitForAppReady(page);

      const token = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
      expect(token).toBeTruthy();

      const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
        return !!el.shadowRoot?.querySelector('.user-pill');
      });
      expect(hasPill).toBe(true);
    }
  });

  test('product list loads after each reload while authenticated', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    for (let i = 0; i < 2; i++) {
      await reloadApp(page);

      await waitForAppReady(page);

      const hasItems = await page.locator('#product-list').evaluate((list) => {
        const grid = list.shadowRoot?.querySelector('.list-grid');
        return grid ? grid.children.length > 0 : false;
      });
      expect(hasItems).toBe(true);
    }
  });
});

test.describe('Auth Lifecycle — Logout Flow', () => {

  test('logout clears token and reverts topbar to signin link', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    // Verify authenticated state
    let hasPill = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(true);

    // Logout
    await logout(page);
    await waitForAppReady(page);

    // Token should be gone
    const token = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
    expect(token).toBeNull();

    // Topbar should show signin
    const hasSignIn = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.signin-link');
    });
    expect(hasSignIn).toBe(true);
  });

  test('page still functions after logout (product list visible)', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);
    await loginAs(page, 'alice');
    await waitForAppReady(page);
    await logout(page);
    await waitForAppReady(page);

    // Products should still load (read is public)
    const hasItems = await page.locator('#product-list').evaluate((list) => {
      const grid = list.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length > 0 : false;
    });
    expect(hasItems).toBe(true);
  });
});

test.describe('Auth Lifecycle — Multi-User Switching', () => {

  test('switch between alice, bob, and charlie with correct states', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const users = ['alice', 'bob', 'charlie'];
    for (const userName of users) {
      await loginAs(page, userName);
      await waitForAppReady(page);

      // Verify user pill is visible
      const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
        return !!el.shadowRoot?.querySelector('.user-pill');
      });
      expect(hasPill).toBe(true);

      // Verify /auth/me matches
      const token = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
      const meResp = await page.request.get('/auth/me', {
        headers: { 'x-access-token': token },
      });
      const me = await meResp.json();
      expect(me.email).toBe(USERS[userName].email);

      // Logout before next user
      await logout(page);
      await waitForUiSettled(page);
    }
  });
});

test.describe('Auth Lifecycle — Token Edge Cases', () => {

  test('invalid JWT in localStorage is handled gracefully', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    // Set garbage JWT
    await page.evaluate(() => {
      window.localStorage.setItem('jwtToken', 'garbage.invalid.token');
    });
    await reloadApp(page);

    await page.waitForURL(/\/login\.html$/);

    // Invalid stored credentials redirect to the standalone login page without crashing.
    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);

    // API call with invalid token should fail
    const resp = await page.request.get('/auth/me', {
      headers: { 'x-access-token': 'garbage.invalid.token' },
    });
    expect(resp.ok()).toBe(false);
  });

  test('anonymous state visible when no token is set', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);
    await clearToken(page);
    await reloadApp(page);

    await waitForAppReady(page);

    const hasSignIn = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.signin-link');
    });
    expect(hasSignIn).toBe(true);

    const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(false);
  });

  test('modified JWT payload is rejected by server', async ({ page }) => {
    // Get a valid token, then tamper with it
    const validToken = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const parts = validToken.split('.');
    // Modify the payload to claim admin role
    const payload = JSON.parse(atob(parts[1]));
    payload.role = 'admin';
    parts[1] = btoa(JSON.stringify(payload));
    const tamperedToken = parts.join('.');

    const resp = await page.request.get('/auth/me', {
      headers: { 'x-access-token': tamperedToken },
    });
    // Tampered token should be rejected (signature mismatch)
    expect(resp.ok()).toBe(false);
  });
});
