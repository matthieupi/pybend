/**
 * Auth fixtures for Playwright E2E tests.
 *
 * Provides login helpers, token management, and pre-computed user data.
 */

/**
 * Seed user credentials.
 */
export const USERS = {
  alice: { email: 'alice@example.com', password: 'alice123', name: 'Alice Martin' },
  bob: { email: 'bob@example.com', password: 'bob123', name: 'Bob Johnson' },
  charlie: { email: 'charlie@example.com', password: 'charlie123', name: 'Charlie Lee' },
};

/**
 * Login via API and return the JWT token.
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {string} email
 * @param {string} password
 * @returns {Promise<string>} JWT token
 */
export async function getToken(request, email, password) {
  const resp = await request.post('/users/login', {
    data: { email, password },
  });
  const json = await resp.json();
  const token = json.token || json.data?.token;
  if (!token) {
    throw new Error(`Login failed for ${email}: ${JSON.stringify(json)}`);
  }
  return token;
}

/**
 * Set a JWT token in localStorage via page.evaluate.
 * Must be called after page.goto() since localStorage is per-origin.
 * @param {import('@playwright/test').Page} page
 * @param {string} token
 */
export async function setToken(page, token) {
  await page.evaluate((t) => {
    window.localStorage.setItem('jwtToken', t);
  }, token);
}

/**
 * Clear JWT token from localStorage.
 * @param {import('@playwright/test').Page} page
 */
export async function clearToken(page) {
  await page.evaluate(() => {
    window.localStorage.removeItem('jwtToken');
  });
}

/**
 * Login as a named user: fetches token via API, stores it in localStorage,
 * then reloads the page so components pick up the auth state.
 * @param {import('@playwright/test').Page} page
 * @param {string} userName - 'alice', 'bob', or 'charlie'
 */
export async function loginAs(page, userName) {
  const user = USERS[userName];
  if (!user) throw new Error(`Unknown user: ${userName}`);

  const token = await getToken(page.request, user.email, user.password);
  await setToken(page, token);
  await page.reload({ waitUntil: 'networkidle' });
}

/**
 * Logout: clear token and reload.
 * @param {import('@playwright/test').Page} page
 */
export async function logout(page) {
  await clearToken(page);
  await page.reload({ waitUntil: 'networkidle' });
}
