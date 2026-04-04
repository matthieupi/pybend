/**
 * ntx-list — Comprehensive Unit Tests
 *
 * Tests the list component's rendering, item display, create button,
 * pagination, click-to-navigate, and edge cases.
 */
import { test, expect } from '@playwright/test';
import { loginAs, logout, getToken, USERS } from './fixtures/auth.js';

const APP_URL = '/';

test.describe('ntx-list — Basic Rendering', () => {

  test('ntx-list element is visible on page load', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const list = page.locator('#product-list');
    await expect(list).toBeVisible();
  });

  test('list-header h1 says "Products"', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const header = await page.locator('#product-list').evaluate((el) => {
      return el.shadowRoot?.querySelector('.list-header h1')?.textContent || '';
    });
    expect(header).toContain('Product');
  });

  test('list-count shows total product count', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const count = await page.locator('#product-list').evaluate((el) => {
      return el.shadowRoot?.querySelector('.list-count')?.textContent || '';
    });
    expect(count.length).toBeGreaterThan(0);
    // Should parse to at least 3 (seed data)
    expect(parseInt(count)).toBeGreaterThanOrEqual(3);
  });

  test('list-grid contains at least 3 ntx-item elements', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const itemCount = await page.locator('#product-list').evaluate((el) => {
      const grid = el.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.querySelectorAll('ntx-item').length : 0;
    });
    expect(itemCount).toBeGreaterThanOrEqual(3);
  });

  test('each ntx-item has a display attribute', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const displays = await page.locator('#product-list').evaluate((el) => {
      const items = el.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => item.getAttribute('display') || '');
    });
    expect(displays.length).toBeGreaterThanOrEqual(3);
    displays.forEach(d => {
      expect(d.length).toBeGreaterThan(0);
    });
  });
});


test.describe('ntx-list — Item Display Content', () => {

  test('first item shows product name', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const name = await page.locator('#product-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntx-item');
      if (!item?.shadowRoot) return '';
      const nameEl = item.shadowRoot.querySelector('[data-value="name"]') ||
                     item.shadowRoot.querySelector('.sm-name');
      return nameEl?.textContent?.trim() || '';
    });
    expect(name.length).toBeGreaterThan(0);
  });

  test('items display currency with $ prefix for price', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasPrice = await page.locator('#product-list').evaluate((el) => {
      const items = el.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return false;
      for (const item of items) {
        const card = item.shadowRoot?.querySelector('.card');
        if (card?.textContent?.includes('$')) return true;
      }
      return false;
    });
    expect(hasPrice).toBe(true);
  });

  test('each item has a .card element with data-display', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const cardDisplays = await page.locator('#product-list').evaluate((el) => {
      const items = el.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => {
        const card = item.shadowRoot?.querySelector('.card');
        return card?.dataset?.display || '';
      }).filter(Boolean);
    });
    expect(cardDisplays.length).toBeGreaterThan(0);
    cardDisplays.forEach(d => {
      expect(['xs', 'sm', 'md', 'lg', 'xl']).toContain(d);
    });
  });

  test('items have consistent display modes within the list', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const displays = await page.locator('#product-list').evaluate((el) => {
      const items = el.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => {
        const card = item.shadowRoot?.querySelector('.card');
        return card?.dataset?.display || '';
      }).filter(Boolean);
    });
    // All items should have the same display size
    if (displays.length > 1) {
      const firstDisplay = displays[0];
      displays.forEach(d => expect(d).toBe(firstDisplay));
    }
  });

  test('all product names are non-empty', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const names = await page.locator('#product-list').evaluate((el) => {
      const items = el.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => {
        const nameEl = item.shadowRoot?.querySelector('[data-value="name"]') ||
                       item.shadowRoot?.querySelector('.sm-name');
        return nameEl?.textContent?.trim() || '';
      }).filter(Boolean);
    });
    expect(names.length).toBeGreaterThanOrEqual(3);
    names.forEach(name => expect(name.length).toBeGreaterThan(0));
  });
});


test.describe('ntx-list — Click-to-Navigate', () => {

  test('clicking an item navigates to detail view (hash changes)', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await page.locator('#product-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntx-item');
      if (item?.shadowRoot) {
        item.shadowRoot.querySelector('.card')?.click();
      }
    });
    await page.waitForTimeout(1000);

    expect(page.url()).toContain('#Product');
  });

  test('click triggers hash change without full page reload', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Track navigation events
    let fullNavigation = false;
    page.on('load', () => { fullNavigation = true; });

    await page.locator('#product-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntx-item');
      if (item?.shadowRoot) {
        item.shadowRoot.querySelector('.card')?.click();
      }
    });
    await page.waitForTimeout(1000);

    expect(fullNavigation).toBe(false);
    expect(page.url()).toContain('#Product');
  });

  test('after click, ntx-router shows the detail view', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await page.locator('#product-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntx-item');
      if (item?.shadowRoot) {
        item.shadowRoot.querySelector('.card')?.click();
      }
    });
    await page.waitForTimeout(1500);

    const hasContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });
});


test.describe('ntx-list — Structure', () => {

  test('list has list-header and list-grid in shadow DOM', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const structure = await page.locator('#product-list').evaluate((el) => {
      const sr = el.shadowRoot;
      return {
        hasHeader: !!sr?.querySelector('.list-header'),
        hasH1: !!sr?.querySelector('.list-header h1'),
        hasCount: !!sr?.querySelector('.list-count'),
        hasGrid: !!sr?.querySelector('.list-grid'),
      };
    });
    expect(structure.hasHeader).toBe(true);
    expect(structure.hasH1).toBe(true);
    expect(structure.hasCount).toBe(true);
    expect(structure.hasGrid).toBe(true);
  });

  test('list has model attribute set to "Product"', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');

    const model = await page.locator('#product-list').evaluate((el) => {
      return el.getAttribute('model') || '';
    });
    expect(model).toBe('Product');
  });

  test('items have select-target attribute pointing to list', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const selectTargets = await page.locator('#product-list').evaluate((el) => {
      const items = el.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => item.getAttribute('select-target') || '');
    });
    expect(selectTargets.length).toBeGreaterThan(0);
    // All should have a non-empty select-target
    selectTargets.forEach(st => expect(st.length).toBeGreaterThan(0));
  });

  test('items have data-value attribute with ref URL', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const refs = await page.locator('#product-list').evaluate((el) => {
      const items = el.shadowRoot?.querySelectorAll('ntx-item');
      if (!items?.length) return [];
      return Array.from(items).map(item => item.getAttribute('data-value') || '');
    });
    expect(refs.length).toBeGreaterThan(0);
    refs.forEach(r => expect(r.length).toBeGreaterThan(0));
  });

  test('count badge matches actual number of rendered items', async ({ page }) => {
    await page.goto(APP_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const { countText, renderedCount } = await page.locator('#product-list').evaluate((el) => {
      const sr = el.shadowRoot;
      const countText = sr?.querySelector('.list-count')?.textContent || '';
      const items = sr?.querySelectorAll('.list-grid ntx-item');
      return { countText, renderedCount: items?.length || 0 };
    });
    // Count badge may show "5 / 5" or just "5"
    const displayedNum = parseInt(countText);
    expect(displayedNum).toBe(renderedCount);
  });
});


test.describe('ntx-list — Responsive Breakpoints', () => {

  const breakpoints = [
    { width: 360, height: 640, name: '360px mobile' },
    { width: 480, height: 800, name: '480px small' },
    { width: 768, height: 1024, name: '768px tablet' },
    { width: 1024, height: 768, name: '1024px laptop' },
    { width: 1200, height: 800, name: '1200px desktop' },
    { width: 1920, height: 1080, name: '1920px widescreen' },
  ];

  for (const bp of breakpoints) {
    test(`list renders correctly at ${bp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: bp.width, height: bp.height });
      await page.goto(APP_URL);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      const visible = await page.locator('#product-list').evaluate((el) => {
        const sr = el.shadowRoot;
        return {
          hasGrid: !!sr?.querySelector('.list-grid'),
          itemCount: sr?.querySelectorAll('.list-grid ntx-item').length || 0,
        };
      });
      expect(visible.hasGrid).toBe(true);
      expect(visible.itemCount).toBeGreaterThan(0);
    });
  }
});
