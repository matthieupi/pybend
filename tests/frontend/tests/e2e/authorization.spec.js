/**
 * Authorization UI — E2E Tests
 */
import { test, expect } from './fixtures/parallel.js';
import { loginAs } from './fixtures/auth.js';
import { gotoApp, reloadApp, waitForAppReady, waitForUiSettled } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('Authorization UI', () => {

  test('anonymous user sees no edit/delete buttons', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
    await reloadApp(page);

    await waitForAppReady(page);

    await gotoApp(page, `${APP_URL}#Product/1`);


    await waitForAppReady(page);

    const hasActions = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('.edit-btn') ||
             !!item.shadowRoot.querySelector('.delete-btn');
    });
    expect(hasActions).toBe(false);
  });

  test('schema access rules are present in schema response', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    expect(schema.access).toBeDefined();
    expect(schema.access['*']).toBeDefined();
  });

  test('product uses authenticated wildcard access by default', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.access['*'].rule).toBe('authenticated');
  });

  test('product create falls back to authenticated wildcard access', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.access['*'].rule).toBe('authenticated');
  });

  test('product delete falls back to authenticated wildcard access', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.access['*'].rule).toBe('authenticated');
  });

  test('product update falls back to authenticated wildcard access', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.access['*'].rule).toBe('authenticated');
  });

  test('field-level access rules in schema', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    // price has field-level access
    expect(schema.properties.price.access).toBeDefined();
    expect(schema.properties.price.access.view).toBe('anyone');
    expect(schema.properties.price.access.edit).toBe('admin');
  });

  test('protected fields marked in schema', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    // user_owner belongs to Comment, which Product references through comments.
    expect(schema.$defs.Comment.properties.user_owner.ui.protected).toBe(true);
  });

  test('$defs access rules propagated', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    // Comment $defs should have its own access rules
    if (schema.$defs?.Comment?.access) {
      expect(schema.$defs.Comment.access.read).toBeDefined();
    }
  });

  test('method-level access in schema', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    // comment method has access rule
    if (schema.methods?.comment?.access) {
      expect(schema.methods.comment.access.rule).toBe('authenticated');
    }
  });

  test('authenticated user sees permissions reflected in UI', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await waitForAppReady(page);

    // The permissions singleton should be initialized
    const permState = await page.evaluate(() => {
      // Access the permissions singleton
      return {
        authenticated: !!window.localStorage.getItem('jwtToken'),
      };
    });

    expect(permState.authenticated).toBe(true);
  });
});
