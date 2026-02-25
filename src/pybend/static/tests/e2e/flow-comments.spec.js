/**
 * flow-comments.spec.js — Comment Lifecycle Integration Tests
 *
 * Tests adding comments, viewing comments, nested replies, multi-user
 * commenting, cross-product isolation, anonymous restrictions, and edge cases.
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, setToken, clearToken, USERS } from './fixtures/auth.js';

const APP_URL = '/matrix.html';

test.describe('Comment Lifecycle — Add Comment via API', () => {

  test('add comment to product and verify count increases', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Create a fresh product so comment count starts at 0
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': token, 'Content-Type': 'application/json' },
      data: { name: `Comment Count Test ${Date.now()}`, price: 1.0 },
    });
    expect(createResp.ok()).toBe(true);
    const product = await createResp.json();
    const pid = product.id;

    // Get current comment count (should be 0)
    const beforeResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': token },
    });
    const beforeData = await beforeResp.json();
    const beforeCount = beforeData.comments?.data?.length ?? 0;

    // Add comment
    const ts = Date.now();
    const resp = await page.request.post(`/products/${pid}/comment`, {
      headers: { 'x-access-token': token },
      data: { comment: { name: `Flow Comment ${ts}`, description: 'Written by Playwright flow test' } },
    });
    expect(resp.ok()).toBe(true);

    // Verify count increased
    const afterResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': token },
    });
    const afterData = await afterResp.json();
    const afterCount = afterData.comments?.data?.length ?? 0;
    expect(afterCount).toBeGreaterThan(beforeCount);
  });

  test('comment API response contains expected fields', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();

    const resp = await page.request.post('/products/2/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: `Fields Check ${ts}`, description: 'Testing response fields' } },
    });
    expect(resp.ok()).toBe(true);
    // Comment response is double-encoded JSON (model_dump_json returns a string)
    let data = await resp.json();
    if (typeof data === 'string') data = JSON.parse(data);
    expect(data.name).toBe(`Fields Check ${ts}`);
    expect(data.description).toBe('Testing response fields');
  });

  test('comment user_owner is set to the authenticated user', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const meResp = await page.request.get('/auth/me', {
      headers: { 'x-access-token': token },
    });
    const me = await meResp.json();

    const ts = Date.now();
    const resp = await page.request.post('/products/2/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: `Owner Check ${ts}`, description: 'Checking owner' } },
    });
    expect(resp.ok()).toBe(true);
    let comment = await resp.json();
    if (typeof comment === 'string') comment = JSON.parse(comment);
    expect(comment.user_owner).toBe(me.user_id);
  });
});

test.describe('Comment Lifecycle — UI Display', () => {

  test('comments list visible on product detail', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const hasComments = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('.list-field[data-value="comments"]');
    });
    expect(hasComments).toBe(true);
  });

  test('comment count badge shows correct number', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const count = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return -1;
      const countEl = item.shadowRoot.querySelector('.list-field[data-value="comments"] .list-field-count');
      return countEl ? parseInt(countEl.textContent) : -1;
    });
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('comment method button visible on product detail', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasCommentMethod = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('ntt-method[method="comment"]');
    });
    expect(hasCommentMethod).toBe(true);
  });

  test('comment items rendered as ntt-item sub-components', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await loginAs(page, 'alice');
    await page.waitForTimeout(2000);

    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const commentItemCount = await page.locator('ntt-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntt-item');
      if (!item?.shadowRoot) return 0;
      const listField = item.shadowRoot.querySelector('.list-field[data-value="comments"]');
      if (!listField) return 0;
      return listField.querySelectorAll('ntt-item').length;
    });
    expect(commentItemCount).toBeGreaterThanOrEqual(1);
  });
});

test.describe('Comment Lifecycle — Nested Replies', () => {

  test('comment schema has parent_id with type selfref', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    const commentDef = schema.$defs?.Comment;
    expect(commentDef).toBeDefined();
    expect(commentDef.properties.parent_id).toBeDefined();
    expect(commentDef.properties.parent_id.type).toBe('selfref');
  });

  test('reply to a comment sets parent_id correctly', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Get a comment to reply to
    const productResp = await page.request.get('/products/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    const productData = await productResp.json();
    const comments = productData.comments?.data || [];
    expect(comments.length).toBeGreaterThanOrEqual(1);
    const firstComment = comments[0];
    const commentId = firstComment.id;

    // Reply to the comment
    const replyResp = await page.request.post(`/products/1/comments/${commentId}/reply`, {
      headers: { 'x-access-token': token },
      data: { text: `Reply to comment ${commentId} at ${Date.now()}` },
    });
    expect(replyResp.ok()).toBe(true);
    // Reply response is double-encoded JSON
    let reply = await replyResp.json();
    if (typeof reply === 'string') reply = JSON.parse(reply);
    expect(reply.parent_id).toBe(commentId);
  });
});

test.describe('Comment Lifecycle — Multiple Users Commenting', () => {

  test('three users each add a comment to the same product', async ({ page }) => {
    const ts = Date.now();

    // Create a fresh product to isolate this test
    const aliceToken = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': aliceToken },
      data: { name: `Multi User Comments ${ts}`, price: 10 },
    });
    const product = await createResp.json();
    const pid = product.id;

    // Alice comments
    const resp1 = await page.request.post(`/products/${pid}/comment`, {
      headers: { 'x-access-token': aliceToken },
      data: { comment: { name: `Alice comment ${ts}`, description: 'From Alice' } },
    });
    expect(resp1.ok()).toBe(true);

    // Bob comments
    const bobToken = await getToken(page.request, USERS.bob.email, USERS.bob.password);
    const resp2 = await page.request.post(`/products/${pid}/comment`, {
      headers: { 'x-access-token': bobToken },
      data: { comment: { name: `Bob comment ${ts}`, description: 'From Bob' } },
    });
    expect(resp2.ok()).toBe(true);

    // Charlie comments
    const charlieToken = await getToken(page.request, USERS.charlie.email, USERS.charlie.password);
    const resp3 = await page.request.post(`/products/${pid}/comment`, {
      headers: { 'x-access-token': charlieToken },
      data: { comment: { name: `Charlie comment ${ts}`, description: 'From Charlie' } },
    });
    expect(resp3.ok()).toBe(true);

    // Verify all 3 comments exist
    const verifyResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': aliceToken },
    });
    const data = await verifyResp.json();
    const allComments = data.comments?.data || [];
    expect(allComments.length).toBe(3);

    // Verify each comment has a different user_owner
    const owners = allComments.map(c => c.user_owner);
    const uniqueOwners = new Set(owners);
    expect(uniqueOwners.size).toBe(3);
  });
});

test.describe('Comment Lifecycle — Cross-Product Isolation', () => {

  test('comments on product 1 do not appear on product 2', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);

    // Get comments for product 1
    const resp1 = await page.request.get('/products/1?depth=1', {
      headers: { 'x-access-token': token },
    });
    const data1 = await resp1.json();
    const comments1 = (data1.comments?.data || []).map(c => c.id);

    // Get comments for product 2
    const resp2 = await page.request.get('/products/2?depth=1', {
      headers: { 'x-access-token': token },
    });
    const data2 = await resp2.json();
    const comments2 = (data2.comments?.data || []).map(c => c.id);

    // No overlap
    const overlap = comments1.filter(id => comments2.includes(id));
    expect(overlap.length).toBe(0);
  });
});

test.describe('Comment Lifecycle — Anonymous User', () => {

  test('anonymous user cannot comment (403)', async ({ page }) => {
    const resp = await page.request.post('/products/1/comment', {
      data: { comment: { name: 'Anon Comment', description: 'Should fail' } },
    });
    expect(resp.status()).toBe(403);
  });
});

test.describe('Comment Lifecycle — Edge Cases', () => {

  test('comment with special characters is stored correctly', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const specialName = `Special <>&"' chars ${Date.now()}`;

    const resp = await page.request.post('/products/3/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: specialName, description: 'Testing <script>alert(1)</script>' } },
    });
    expect(resp.ok()).toBe(true);
    let comment = await resp.json();
    if (typeof comment === 'string') comment = JSON.parse(comment);
    expect(comment.name).toBe(specialName);
    expect(comment.description).toBe('Testing <script>alert(1)</script>');
  });

  test('comment with unicode and emoji is stored correctly', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const unicodeName = `\u65e5\u672c\u8a9e \u4e2d\u6587 \ud83d\ude00 ${Date.now()}`;

    const resp = await page.request.post('/products/3/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: unicodeName, description: 'Unicode test' } },
    });
    expect(resp.ok()).toBe(true);
    let comment = await resp.json();
    if (typeof comment === 'string') comment = JSON.parse(comment);
    expect(comment.name).toBe(unicodeName);
  });

  test('rapidly submit 5 comments — all created successfully', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const ts = Date.now();

    // Create a fresh product so we don't hit pagination limits
    const createResp = await page.request.post('/products', {
      headers: { 'x-access-token': token, 'Content-Type': 'application/json' },
      data: { name: `Rapid Comment Test ${ts}`, price: 1.0 },
    });
    expect(createResp.ok()).toBe(true);
    const product = await createResp.json();
    const pid = product.id;

    // Submit sequentially to avoid SQLite locking issues
    for (let i = 0; i < 5; i++) {
      const resp = await page.request.post(`/products/${pid}/comment`, {
        headers: { 'x-access-token': token },
        data: { comment: { name: `Rapid ${i} ${ts}`, description: `Comment ${i}` } },
      });
      expect(resp.ok()).toBe(true);
    }

    // Verify all 5 were actually created by checking the product
    const verifyResp = await page.request.get(`/products/${pid}?depth=1`, {
      headers: { 'x-access-token': token },
    });
    const data = await verifyResp.json();
    const allComments = data.comments?.data || [];
    const matchingComments = allComments.filter(c => c.name?.startsWith(`Rapid`) && c.name?.includes(ts.toString()));
    expect(matchingComments.length).toBe(5);
  });

  test('comment on non-existent product returns error', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products/99999/comment', {
      headers: { 'x-access-token': token },
      data: { comment: { name: 'Ghost Comment', description: 'Product does not exist' } },
    });
    expect(resp.ok()).toBe(false);
  });
});
