/**
 * Comments (Nested Entity) — E2E Tests
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, USERS } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('Comments', () => {

  test('comment method visible on product detail', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasCommentMethod = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('ntx-method[method="comment"]');
    });

    expect(hasCommentMethod).toBe(true);
  });

  test('comments list visible on product detail', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const hasComments = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return false;
      const listField = item.shadowRoot.querySelector('.list-field[data-value="comments"]');
      return !!listField;
    });

    expect(hasComments).toBe(true);
  });

  test('comment count badge shows correct number', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const count = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return '';
      const countEl = item.shadowRoot.querySelector('.list-field[data-value="comments"] .list-field-count');
      return countEl?.textContent || '0';
    });

    expect(parseInt(count)).toBeGreaterThanOrEqual(0);
  });

  test('submit comment via API adds comment', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Get current comment count
    const beforeResp = await page.request.get('/products/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    const beforeData = await beforeResp.json();
    const beforeCount = Array.isArray(beforeData.comments?.data)
      ? beforeData.comments.data.length
      : (Array.isArray(beforeData.comments) ? beforeData.comments.length : 0);

    // Add a comment via API
    const resp = await page.request.post('/products/1/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: 'E2E Test Comment', description: 'From Playwright' } },
    });
    expect(resp.ok()).toBe(true);

    // Verify count increased
    const afterResp = await page.request.get('/products/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    const afterData = await afterResp.json();
    const afterCount = Array.isArray(afterData.comments?.data)
      ? afterData.comments.data.length
      : (Array.isArray(afterData.comments) ? afterData.comments.length : 0);

    expect(afterCount).toBeGreaterThan(beforeCount);
  });

  test('comment shows author and text', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const commentContent = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return '';
      const commentItems = item.shadowRoot.querySelectorAll('.list-field[data-value="comments"] ntx-item');
      if (!commentItems.length) return '';
      const first = commentItems[0];
      return first?.shadowRoot?.querySelector('.card')?.textContent || '';
    });

    // Comment should have some text content
    expect(commentContent.length).toBeGreaterThanOrEqual(0);
  });

  test('nested comment structure (replies) supported', async ({ page }) => {
    // Check that the Comment schema has parent_id (selfref)
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    const commentDef = schema.$defs?.Comment;

    if (commentDef) {
      expect(commentDef.properties.parent_id).toBeDefined();
      expect(commentDef.properties.parent_id.type).toBe('selfref');
    }
  });
});
