/**
 * ntx-method — browser/backend contracts.
 *
 * Static rendering behavior is covered in Vitest component tests. This spec keeps
 * real-page rendering, browser-computed style, schema, and authenticated API
 * coverage that still needs Playwright.
 */
import { test, expect } from './fixtures/parallel.js';
import { getToken, USERS } from './fixtures/auth.js';
import { gotoApp, waitForAppReady } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('ntx-method — Product Detail Rendering', () => {
  test('favorite method renders with icon, count, and browser-computed button layout', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/1`);
    await waitForAppReady(page);

    const info = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      const method = item?.shadowRoot?.querySelector('ntx-method[method="favorite"]');
      const btn = method?.shadowRoot?.querySelector('.method-btn');
      const styles = btn ? getComputedStyle(btn) : null;
      return {
        found: !!method,
        hasStarSvg: !!method?.shadowRoot?.querySelector('ntx-icon')?.shadowRoot?.querySelector('svg polygon'),
        count: method?.shadowRoot?.querySelector('.method-btn-count')?.textContent ?? null,
        cursor: styles?.cursor ?? '',
        borderRadius: styles?.borderRadius ?? '',
        display: styles?.display ?? '',
      };
    });

    expect(info.found).toBe(true);
    expect(info.hasStarSvg).toBe(true);
    expect(parseInt(info.count, 10)).toBeGreaterThanOrEqual(0);
    expect(info.cursor).toBe('pointer');
    expect(parseFloat(info.borderRadius)).toBeGreaterThanOrEqual(100);
    expect(info.display).toContain('flex');
  });

  test('comment method renders inline textarea form from live schema', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/1`);
    await waitForAppReady(page);

    const inlineInfo = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      const method = item?.shadowRoot?.querySelector('ntx-method[method="comment"]');
      const textarea = method?.shadowRoot?.querySelector('textarea');
      const submit = method?.shadowRoot?.querySelector('button[type="submit"]');
      return {
        hasInline: !!method?.shadowRoot?.querySelector('.method-inline'),
        hasForm: !!method?.shadowRoot?.querySelector('form'),
        placeholder: textarea?.getAttribute('placeholder') || '',
        buttonText: submit?.textContent?.trim() || '',
      };
    });

    expect(inlineInfo.hasInline).toBe(true);
    expect(inlineInfo.hasForm).toBe(true);
    expect(inlineInfo.placeholder).toContain('Add your comment');
    expect(inlineInfo.buttonText).toBe('Post');
  });

  test('favorite method is also present on product list items', async ({ page }) => {
    await gotoApp(page, APP_URL);
    await waitForAppReady(page);

    const hasFavInList = await page.locator('#product-list').evaluate((el) => {
      const items = el.shadowRoot?.querySelectorAll('ntx-item');
      return Array.from(items || []).some((item) => item.shadowRoot?.querySelector('ntx-method[method="favorite"]'));
    });

    expect(hasFavInList).toBe(true);
  });
});

test.describe('ntx-method — Backend Schema', () => {
  test('Product and Comment method schema exposes expected ui/access contracts', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    const commentDef = schema.$defs?.Comment;

    expect(schema.methods.favorite).toMatchObject({
      scope: 'instancemethod',
      ui: { layout: 'button', icon: 'star', count_field: 'favorites' },
      access: { rule: 'authenticated' },
    });
    expect(schema.methods.comment.scope).toBe('instancemethod');
    expect(schema.methods.comment.ui).toMatchObject({
      layout: 'inline',
      button_label: 'Post',
      widget: 'textarea',
    });
    expect(schema.methods.comment.ui.placeholder).toContain('comment');
    expect(schema.methods.comment.parameters.comment.$ref).toContain('Comment');

    expect(commentDef?.methods?.like.ui).toMatchObject({
      icon: 'heart',
      layout: 'button',
      count_field: 'likes',
    });
    expect(commentDef.methods.like.access.rule).toBe('authenticated');
    expect(commentDef.methods.reply.ui.layout).toBe('inline');
    expect(commentDef.methods.reply.ui.button_label).toBe('Reply');
    expect(commentDef.methods.reply.ui.placeholder).toContain('reply');
    expect(commentDef.methods.reply.access.rule).toBe('authenticated');
  });
});

test.describe('ntx-method — Authenticated API Calls', () => {
  test('favorite API call works with auth', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products/1/favorite', {
      headers: { 'x-access-token': token },
      data: {},
    });
    expect(resp.ok()).toBe(true);
  });

  test('favorite API call fails without auth', async ({ page }) => {
    const resp = await page.request.post('/products/1/favorite', {
      data: {},
    });
    expect([401, 403]).toContain(resp.status());
  });
});
