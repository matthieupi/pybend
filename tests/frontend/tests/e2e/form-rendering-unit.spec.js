/**
 * form-rendering — Browser integration coverage
 *
 * Static Formidable rendering contracts live in Vitest generator tests. This file
 * keeps browser/backend checks where real Shadow DOM, CSS, auth, or seeded data
 * affect the result.
 */
import { test, expect } from './fixtures/parallel.js';
import { loginAs } from './fixtures/auth.js';
import { gotoApp, waitForAppReady } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('form-rendering — Browser Form Behavior', () => {
  test('detail header uses uppercase text-transform in large detail view only', async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 1000 });
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const detailInfo = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return {};
      const card = item.shadowRoot.querySelector('.card');
      const h2 = item.shadowRoot.querySelector('h2[data-value="name"]');
      return {
        display: card?.dataset?.display || '',
        textTransform: h2 ? getComputedStyle(h2).textTransform : '',
      };
    });

    expect(['lg', 'xl']).toContain(detailInfo.display);
    expect(detailInfo.textTransform).toBe('uppercase');
  });

  test('authenticated edit mode opens real browser controls for editable header fields', async ({ page }) => {
    await page.goto(APP_URL);
    await loginAs(page, 'alice');
    await page.evaluate(() => { window.location.hash = '#Product/1'; });
    await waitForAppReady(page);

    const editClicked = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      const btn = item?.shadowRoot?.querySelector('.edit-btn');
      if (!btn) return false;
      btn.click();
      return true;
    });
    expect(editClicked).toBe(true);
    await waitForAppReady(page);

    const controls = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      const input = item?.shadowRoot?.querySelector('input[data-key="name"]');
      const textarea = item?.shadowRoot?.querySelector('textarea[data-key="description"]');
      return {
        nameExists: !!input,
        nameType: input?.getAttribute('type') || '',
        nameValue: input?.value || '',
        descriptionType: textarea?.dataset?.type || '',
      };
    });

    expect(controls.nameExists).toBe(true);
    expect(controls.nameType).toBe('text');
    expect(controls.nameValue.length).toBeGreaterThan(0);
    if (controls.descriptionType) {
      expect(['string', 'text']).toContain(controls.descriptionType);
    }
  });
});

test.describe('form-rendering — List Field Components', () => {
  test('comments array hydrates the ntx-list-field Shadow DOM with Comment metadata', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);
    await page.waitForFunction(() => {
      const r = document.querySelector('ntx-router');
      const item = r?.shadowRoot?.querySelector('ntx-item');
      const host = item?.shadowRoot?.querySelector('ntx-list-field[data-key="comments"]');
      return !!host?.shadowRoot?.querySelector('.list-field[data-value="comments"]');
    });

    const listField = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      const host = item?.shadowRoot?.querySelector('ntx-list-field[data-key="comments"]');
      const lf = host?.shadowRoot?.querySelector('.list-field[data-value="comments"]');
      if (!lf) return { found: false };
      return {
        found: true,
        dataModel: lf.dataset.model,
        hasHeader: !!lf.querySelector('.list-field-header'),
        hasLabel: !!lf.querySelector('.list-field-label'),
        hasCount: !!lf.querySelector('.list-field-count'),
        count: parseInt(lf.querySelector('.list-field-count')?.textContent || '0'),
        childCount: lf.querySelectorAll('ntx-item').length,
        firstDisplay: lf.querySelector('ntx-item')?.getAttribute('display') || '',
      };
    });

    expect(listField.found).toBe(true);
    expect(listField.dataModel).toBe('Comment');
    expect(listField.hasHeader).toBe(true);
    expect(listField.hasLabel).toBe(true);
    expect(listField.hasCount).toBe(true);
    expect(listField.count).toBeGreaterThanOrEqual(0);
    if (listField.childCount > 0) {
      expect(listField.firstDisplay).toBe('sm');
    }
  });

  test('collapsed list-field rows expose show-more chrome when seeded data exceeds preview count', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const collapsed = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      const host = item?.shadowRoot?.querySelector('ntx-list-field[data-key="comments"]');
      const lf = host?.shadowRoot?.querySelector('.list-field[data-value="comments"]');
      if (!lf) return {};
      const count = parseInt(lf.querySelector('.list-field-count')?.textContent || '0');
      const wrapper = lf.querySelector('.nested-collapsed');
      const btn = lf.querySelector('.show-more-btn');
      return {
        count,
        hasWrapper: !!wrapper,
        wrapperItemCount: wrapper?.querySelectorAll('ntx-item').length || 0,
        hasBtn: !!btn,
        btnText: btn?.textContent || '',
      };
    });

    if (collapsed.count > 2) {
      expect(collapsed.hasWrapper).toBe(true);
      expect(collapsed.wrapperItemCount).toBe(collapsed.count - 2);
      expect(collapsed.hasBtn).toBe(true);
      expect(collapsed.btnText).toContain('Show');
      expect(collapsed.btnText).toContain('more');
    }
  });

  test('favorites array hydrates as a Like list-field', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const favField = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      const host = item?.shadowRoot?.querySelector('ntx-list-field[data-key="favorites"]');
      const lf = host?.shadowRoot?.querySelector('.list-field[data-value="favorites"]');
      if (!lf) return { found: false };
      return { found: true, dataModel: lf.dataset.model };
    });

    expect(favField.found).toBe(true);
    expect(favField.dataModel).toBe('Like');
  });
});

test.describe('form-rendering — Backend Schema Contract', () => {
  test('Product schema exposes rendering hints consumed by Formidable', async ({ page }) => {
    const resp = await page.request.get('/Product');
    const schema = await resp.json();

    expect(schema.ui.field_order).toEqual(['name', 'price', 'description', 'comments', 'favorites']);
    expect(schema.ui.groups.main).toEqual(['name', 'description', 'price']);
    expect(schema.ui.groups.Social).toEqual(['comments', 'favorites']);
    expect(schema.properties.name.minLength).toBe(1);
    expect(schema.properties.name.maxLength).toBe(200);
    expect(schema.properties.name.ui.placeholder).toBe('Product name...');
    expect(schema.properties.price.exclusiveMinimum).toBe(0);
    expect(schema.properties.price.ui.widget).toBe('currency');
    expect(schema.properties.description.ui.widget).toBe('textarea');
    expect(schema.properties.id.ui.display).toBe(false);
    expect(schema.properties.image.ui.display).toBe(false);
  });
});

test.describe('form-rendering — Responsive And Nested Browser Rendering', () => {
  test('very long field values do not overflow container', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const overflow = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return true;
      const card = item.shadowRoot.querySelector('.card');
      if (!card) return true;
      return card.scrollWidth > card.clientWidth + 20;
    });

    expect(overflow).toBe(false);
  });

  test('form renders at mobile viewport without breaking', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const hasCard = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      return !!item?.shadowRoot?.querySelector('.card');
    });

    expect(hasCard).toBe(true);
  });

  test('nested Comment items render with their own form structure', async ({ page }) => {
    await gotoApp(page, `${APP_URL}#Product/1`);

    await waitForAppReady(page);

    const commentStructure = await page.locator('ntx-router').evaluate((r) => {
      const item = r.shadowRoot?.querySelector('ntx-item');
      const host = item?.shadowRoot?.querySelector('ntx-list-field[data-key="comments"]');
      const commentItem = host?.shadowRoot?.querySelector('.list-field[data-value="comments"] ntx-item');
      if (!commentItem?.shadowRoot) return {};
      return {
        hasCard: !!commentItem.shadowRoot.querySelector('.card'),
        hasName: !!commentItem.shadowRoot.querySelector('[data-value="name"]') ||
                 !!commentItem.shadowRoot.querySelector('.sm-name'),
      };
    });

    if (commentStructure.hasCard !== undefined) {
      expect(commentStructure.hasCard).toBe(true);
    }
  });
});
