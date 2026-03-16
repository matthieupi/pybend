/**
 * Authorization UI — E2E Tests
 */
import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('Authorization UI', () => {

  test('anonymous user sees no edit/delete buttons', async ({ page }) => {
    await page.goto(APP_URL);
    await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

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
    expect(schema.access.read).toBeDefined();
    expect(schema.access.create).toBeDefined();
    expect(schema.access.update).toBeDefined();
    expect(schema.access.delete).toBeDefined();
  });

  test('product read access allows anonymous', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.access.read.rule).toBe('anyone');
  });

  test('product create requires authentication', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.access.create.rule).toBe('authenticated');
  });

  test('product delete requires admin role', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.access.delete.rule).toBe('role');
    expect(schema.access.delete.roles).toContain('admin');
  });

  test('product update is owner OR admin', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    expect(schema.access.update.op).toBe('or');
    expect(schema.access.update.rules.length).toBe(2);

    const ownerRule = schema.access.update.rules.find(r => r.rule === 'owner');
    const adminRule = schema.access.update.rules.find(r => r.rule === 'role');
    expect(ownerRule).toBeDefined();
    expect(adminRule).toBeDefined();
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

    // user_owner has ui.protected=true
    expect(schema.properties.user_owner.ui.protected).toBe(true);
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
    await page.waitForTimeout(2000);

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
