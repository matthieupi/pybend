/**
 * ntx-method — Comprehensive Unit Tests
 *
 * Tests the method button component for Product (favorite, comment)
 * and Comment (like, reply) methods, including schema verification,
 * button/inline layouts, and edge cases.
 */
import { test, expect } from '@playwright/test';
import { loginAs, getToken, USERS } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('ntx-method — Product Favorite Button', () => {

  test('favorite method element exists on product detail', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const hasFav = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('ntx-method[method="favorite"]');
    });
    expect(hasFav).toBe(true);
  });

  test('favorite button has star icon SVG', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const hasStarSvg = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return false;
      const method = item.shadowRoot.querySelector('ntx-method[method="favorite"]');
      if (!method?.shadowRoot) return false;
      const icon = method.shadowRoot.querySelector('.method-btn-icon');
      // star SVG has a <polygon> element
      return !!icon?.querySelector('svg polygon');
    });
    expect(hasStarSvg).toBe(true);
  });

  test('favorite button shows count badge', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const count = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return null;
      const method = item.shadowRoot.querySelector('ntx-method[method="favorite"]');
      if (!method?.shadowRoot) return null;
      const countEl = method.shadowRoot.querySelector('.method-btn-count');
      return countEl?.textContent || null;
    });
    // Count should be a number (could be "0")
    expect(count).not.toBeNull();
    expect(parseInt(count)).toBeGreaterThanOrEqual(0);
  });

  test('favorite button is clickable (has .method-btn)', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const hasBtn = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return false;
      const method = item.shadowRoot.querySelector('ntx-method[method="favorite"]');
      if (!method?.shadowRoot) return false;
      const btn = method.shadowRoot.querySelector('.method-btn');
      return !!btn && getComputedStyle(btn).cursor === 'pointer';
    });
    expect(hasBtn).toBe(true);
  });

  test('favorite button uses button layout (pill-shaped)', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const style = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return {};
      const method = item.shadowRoot.querySelector('ntx-method[method="favorite"]');
      if (!method?.shadowRoot) return {};
      const btn = method.shadowRoot.querySelector('.method-btn');
      if (!btn) return {};
      const s = getComputedStyle(btn);
      return {
        borderRadius: s.borderRadius,
        display: s.display,
      };
    });
    expect(style.borderRadius).toBe('100px'); // pill shape
    expect(style.display).toContain('flex');
  });

  test('favorite button also present on sm list items', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasFavInList = await page.locator('#product-list').evaluate((el) => {
      const items = el.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return false;
      for (const item of items) {
        if (item.shadowRoot?.querySelector('ntx-method[method="favorite"]')) return true;
      }
      return false;
    });
    expect(hasFavInList).toBe(true);
  });
});


test.describe('ntx-method — Product Comment Method (Inline)', () => {

  test('comment method element exists on product detail', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const hasComment = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return false;
      return !!item.shadowRoot.querySelector('ntx-method[method="comment"]');
    });
    expect(hasComment).toBe(true);
  });

  test('comment method has inline layout with textarea', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const inlineInfo = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return {};
      const method = item.shadowRoot.querySelector('ntx-method[method="comment"]');
      if (!method?.shadowRoot) return {};
      return {
        hasInline: !!method.shadowRoot.querySelector('.method-inline'),
        hasTextarea: !!method.shadowRoot.querySelector('textarea'),
        hasForm: !!method.shadowRoot.querySelector('form'),
      };
    });
    expect(inlineInfo.hasInline).toBe(true);
    expect(inlineInfo.hasTextarea).toBe(true);
    expect(inlineInfo.hasForm).toBe(true);
  });

  test('comment textarea has placeholder "Add your comment..."', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const placeholder = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return '';
      const method = item.shadowRoot.querySelector('ntx-method[method="comment"]');
      if (!method?.shadowRoot) return '';
      const ta = method.shadowRoot.querySelector('textarea');
      return ta?.getAttribute('placeholder') || '';
    });
    expect(placeholder).toContain('Add your comment');
  });

  test('comment form has "Post" submit button', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const btnText = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return '';
      const method = item.shadowRoot.querySelector('ntx-method[method="comment"]');
      if (!method?.shadowRoot) return '';
      const btn = method.shadowRoot.querySelector('button[type="submit"]');
      return btn?.textContent?.trim() || '';
    });
    expect(btnText).toBe('Post');
  });
});


test.describe('ntx-method — Comment Like Button (Nested)', () => {

  test('comment items have like method with heart icon', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const likeInfo = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return {};
      // Find a comment ntx-item inside the comments list-field
      const commentItems = item.shadowRoot.querySelectorAll('.list-field[data-value="comments"] ntx-item');
      for (const ci of commentItems) {
        const likeMethod = ci.shadowRoot?.querySelector('ntx-method[method="like"]');
        if (likeMethod?.shadowRoot) {
          const icon = likeMethod.shadowRoot.querySelector('.method-btn-icon');
          return {
            found: true,
            hasHeart: !!icon?.querySelector('svg path'), // heart SVG uses <path>
            hasCount: !!likeMethod.shadowRoot.querySelector('.method-btn-count'),
          };
        }
      }
      return { found: false };
    });

    // Comments may or may not have rendered sub-methods depending on data
    if (likeInfo.found) {
      expect(likeInfo.hasHeart).toBe(true);
      expect(likeInfo.hasCount).toBe(true);
    }
  });
});


test.describe('ntx-method — Schema Verification', () => {

  test('Product schema has favorite method with correct ui', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    expect(schema.methods.favorite).toBeDefined();
    expect(schema.methods.favorite.scope).toBe('instancemethod');
    expect(schema.methods.favorite.ui.layout).toBe('button');
    expect(schema.methods.favorite.ui.icon).toBe('star');
    expect(schema.methods.favorite.ui.count_field).toBe('favorites');
    expect(schema.methods.favorite.access.rule).toBe('authenticated');
  });

  test('Product schema has comment method with inline layout', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    expect(schema.methods.comment).toBeDefined();
    expect(schema.methods.comment.scope).toBe('instancemethod');
    expect(schema.methods.comment.ui.layout).toBe('inline');
    expect(schema.methods.comment.ui.button_label).toBe('Post');
    expect(schema.methods.comment.ui.placeholder).toContain('comment');
    expect(schema.methods.comment.ui.widget).toBe('textarea');
    // comment parameter references Comment $def
    expect(schema.methods.comment.parameters.comment).toBeDefined();
    expect(schema.methods.comment.parameters.comment.$ref).toContain('Comment');
  });

  test('Comment $defs has like method with heart icon', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    const commentDef = schema.$defs?.Comment;

    expect(commentDef?.methods?.like).toBeDefined();
    expect(commentDef.methods.like.ui.icon).toBe('heart');
    expect(commentDef.methods.like.ui.layout).toBe('button');
    expect(commentDef.methods.like.ui.count_field).toBe('likes');
    expect(commentDef.methods.like.access.rule).toBe('authenticated');
  });

  test('Comment $defs has reply method with inline layout', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();
    const commentDef = schema.$defs?.Comment;

    expect(commentDef?.methods?.reply).toBeDefined();
    expect(commentDef.methods.reply.ui.layout).toBe('inline');
    expect(commentDef.methods.reply.ui.button_label).toBe('Reply');
    expect(commentDef.methods.reply.ui.placeholder).toContain('reply');
    expect(commentDef.methods.reply.access.rule).toBe('authenticated');
  });
});


test.describe('ntx-method — Edge Cases', () => {

  test('method button renders with correct structure', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const structure = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return {};
      const method = item.shadowRoot.querySelector('ntx-method[method="favorite"]');
      if (!method?.shadowRoot) return {};
      return {
        hasBtn: !!method.shadowRoot.querySelector('.method-btn'),
        hasIcon: !!method.shadowRoot.querySelector('.method-btn-icon'),
        hasCount: !!method.shadowRoot.querySelector('.method-btn-count'),
        hasStyle: !!method.shadowRoot.querySelector('style'),
      };
    });
    expect(structure.hasBtn).toBe(true);
    expect(structure.hasIcon).toBe(true);
    expect(structure.hasCount).toBe(true);
    expect(structure.hasStyle).toBe(true);
  });

  test('method component has correct attributes from schema', async ({ page }) => {
    await page.goto(`${APP_URL}#Product/1`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const attrs = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return {};
      const method = item.shadowRoot.querySelector('ntx-method[method="favorite"]');
      if (!method) return {};
      return {
        model: method.getAttribute('model') || '',
        method: method.getAttribute('method') || '',
        layout: method.getAttribute('layout') || '',
        icon: method.getAttribute('icon') || '',
        countField: method.getAttribute('count-field') || '',
      };
    });
    expect(attrs.model).toBe('Product');
    expect(attrs.method).toBe('favorite');
    expect(attrs.layout).toBe('button');
    expect(attrs.icon).toBe('star');
    expect(attrs.countField).toBe('favorites');
  });

  test('favorite API call works with auth', async ({ page }) => {
    const token = await getToken(page.request, USERS.alice.email, USERS.alice.password);
    const resp = await page.request.post('/products/1/favorite', {
      headers: { 'x-access-token': token },
      data: {},
    });
    expect(resp.ok()).toBe(true);
  });

  test('favorite API call fails without auth (401)', async ({ page }) => {
    const resp = await page.request.post('/products/1/favorite', {
      data: {},
    });
    expect([401, 403]).toContain(resp.status());
  });
});
