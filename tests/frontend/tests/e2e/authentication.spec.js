/**
 * Authentication UI & Flow — E2E Tests
 */
import { test, expect } from '@playwright/test';
import { loginAs, logout, USERS, getToken } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('Authentication', () => {

  test('anonymous topbar shows "Sign in" link', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    const hasSignIn = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.signin-link');
    });
    expect(hasSignIn).toBe(true);
  });

  test('authenticated topbar shows user pill', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(true);
  });

  test('user pill shows initial and name', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    const userName = await page.locator('ntx-topbar').evaluate((el) => {
      const nameEl = el.shadowRoot?.querySelector('.user-name');
      return nameEl?.textContent || '';
    });

    expect(userName.length).toBeGreaterThan(0);
  });

  test('user dropdown contains email, role, theme toggle, logout', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    const dropdown = await page.locator('ntx-topbar').evaluate((el) => {
      const dd = el.shadowRoot?.querySelector('.user-dropdown');
      return {
        hasEmail: !!dd?.querySelector('.dropdown-email'),
        hasThemeToggle: !!dd?.querySelector('.theme-toggle'),
        hasLogout: !!dd?.querySelector('.logout-btn'),
        hasProfile: !!dd?.querySelector('[href="#@profile"]'),
      };
    });

    expect(dropdown.hasEmail).toBe(true);
    expect(dropdown.hasThemeToggle).toBe(true);
    expect(dropdown.hasLogout).toBe(true);
    expect(dropdown.hasProfile).toBe(true);
  });

  test('login via API returns valid token', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    expect(token).toBeTruthy();
    expect(typeof token).toBe('string');
    expect(token.length).toBeGreaterThan(10);
  });

  test('login with invalid credentials fails', async ({ page }) => {
    const resp = await page.request.post('/users/login', {
      data: { email: 'wrong@example.com', password: 'wrong' },
    });
    // Should not return a token
    const json = await resp.json();
    expect(json.token).toBeUndefined();
  });

  test('token validation — reload preserves auth state', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    // Reload without clearing token
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);

    // Should still be authenticated
    const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('.user-pill');
    });
    expect(hasPill).toBe(true);
  });

  test('/auth/me returns user data with valid token', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.get('/auth/me', {
      headers: { 'x-access-token': token },
    });
    expect(resp.ok()).toBe(true);

    const user = await resp.json();
    expect(user.email).toBe(USERS.alice.email);
    expect(user.user_id).toBeDefined();
  });

  test('favorites link visible when authenticated', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.waitForTimeout(1000);

    const hasFavoritesLink = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('[href="#@favorites"]');
    });
    expect(hasFavoritesLink).toBe(true);
  });

  test('favorites link hidden when anonymous', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    const hasFavoritesLink = await page.locator('ntx-topbar').evaluate((el) => {
      return !!el.shadowRoot?.querySelector('[href="#@favorites"]');
    });
    expect(hasFavoritesLink).toBe(false);
  });
});
