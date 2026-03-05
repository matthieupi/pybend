/**
 * flow-auth-lifecycle.spec.js — Authentication Lifecycle Integration Tests
 *
 * Tests complete user journeys: registration, login, session persistence,
 * logout, multi-user switching, and token edge cases.
 */
import { test, expect } from '@playwright/test';
import { loginAs, logout, getToken, setToken, clearToken, USERS } from './fixtures/auth.js';

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
    expect(regData.token).toBeTruthy();
    expect(regData.user).toBeDefined();
    expect(regData.user.email).toBe(email);

    // Login with the newly registered credentials
    const loginResp = await page.request.post('/users/login', {
      data: { email, password: 'testpass123' },
    });
    expect(loginResp.ok()).toBe(true);
    const loginData = await loginResp.json();
    expect(loginData.token).toBeTruthy();

    // Set token and verify in UI
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await setToken(page, loginData.token);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(true);

    // Verify /auth/me returns correct data
    const meResp = await page.request.get('/auth/me', {
      headers: { 'x-access-token': loginData.token },
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
    expect(data.token).toBeTruthy();
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
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

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
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    // Reload 3 times
    for (let i = 0; i < 3; i++) {
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(1500);

      const token = await page.evaluate(() => window.localStorage.getItem('jwtToken'));
      expect(token).toBeTruthy();

      const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
        return !!el.shadowRoot?.querySelector('.user-pill');
      });
      expect(hasPill).toBe(true);
    }
  });

  test('product list loads after each reload while authenticated', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    for (let i = 0; i < 2; i++) {
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(2000);

      const hasItems = await page.locator('ntx-list').evaluate((list) => {
        const grid = list.shadowRoot?.querySelector('.list-grid');
        return grid ? grid.children.length > 0 : false;
      });
      expect(hasItems).toBe(true);
    }
  });
});

test.describe('Auth Lifecycle — Logout Flow', () => {

  test('logout clears token and reverts topbar to signin link', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    // Verify authenticated state
    let hasPill = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(true);

    // Logout
    await logout(page);
    await page.waitForTimeout(1500);

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
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);
    await logout(page);
    await page.waitForTimeout(2000);

    // Products should still load (read is public)
    const hasItems = await page.locator('ntx-list').evaluate((list) => {
      const grid = list.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length > 0 : false;
    });
    expect(hasItems).toBe(true);
  });
});

test.describe('Auth Lifecycle — Multi-User Switching', () => {

  test('switch between alice, bob, and charlie with correct states', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    const users = ['alice', 'bob', 'charlie'];
    for (const userName of users) {
      await loginAs(page, userName);
      await page.waitForTimeout(1500);

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
      await page.waitForTimeout(500);
    }
  });
});

test.describe('Auth Lifecycle — Token Edge Cases', () => {

  test('invalid JWT in localStorage is handled gracefully', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    // Set garbage JWT
    await page.evaluate(() => {
      window.localStorage.setItem('jwtToken', 'garbage.invalid.token');
    });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    // Page should not crash
    const hasBody = await page.evaluate(() => document.body.children.length > 0);
    expect(hasBody).toBe(true);

    // API call with invalid token should fail
    const resp = await page.request.get('/auth/me', {
      headers: { 'x-access-token': 'garbage.invalid.token' },
    });
    expect(resp.ok()).toBe(false);
  });

  test('anonymous state visible when no token is set', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await clearToken(page);
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);

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
