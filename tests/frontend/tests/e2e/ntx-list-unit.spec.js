/**
 * ntx-list — Comprehensive Unit Tests
 *
 * Tests the list component's rendering, item display, create button,
 * pagination, click-to-navigate, and edge cases.
 */
import { test, expect } from './fixtures/parallel.js';
import { gotoApp, waitForAppReady } from './fixtures/ui.js';

const APP_URL = '/';

test.describe('ntx-list — Basic Rendering', () => {

  test('ntx-list element is visible on page load', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const list = page.locator('#product-list');
    await expect(list).toBeVisible();
  });
});


test.describe('ntx-list — Item Display Content', () => {

  test('first item shows product name', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

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
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

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
});


test.describe('ntx-list — Click-to-Navigate', () => {

  test('clicking an item navigates to detail view (hash changes)', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    await page.locator('#product-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntx-item');
      if (item?.shadowRoot) {
        item.shadowRoot.querySelector('.card')?.click();
      }
    });
    await waitForAppReady(page);

    expect(page.url()).toContain('#Product');
  });

  test('click triggers hash change without full page reload', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    // Track navigation events
    let fullNavigation = false;
    page.on('load', () => { fullNavigation = true; });

    await page.locator('#product-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntx-item');
      if (item?.shadowRoot) {
        item.shadowRoot.querySelector('.card')?.click();
      }
    });
    await waitForAppReady(page);

    expect(fullNavigation).toBe(false);
    expect(page.url()).toContain('#Product');
  });

  test('after click, ntx-router shows the detail view', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    await page.locator('#product-list').evaluate((el) => {
      const item = el.shadowRoot?.querySelector('ntx-item');
      if (item?.shadowRoot) {
        item.shadowRoot.querySelector('.card')?.click();
      }
    });
    await waitForAppReady(page);

    const hasContent = await page.locator('ntx-router').evaluate((r) => {
      return !!r.shadowRoot?.querySelector('.router-content');
    });
    expect(hasContent).toBe(true);
  });
});


test.describe('ntx-list — Structure', () => {
  test('list has model attribute set to "Product"', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const model = await page.locator('#product-list').evaluate((el) => {
      return el.getAttribute('model') || '';
    });
    expect(model).toBe('Product');
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
      await gotoApp(page, APP_URL);

      await waitForAppReady(page);

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


test.describe('ntx-list — Packed Card Layout', () => {

  test('wide card lists pack uneven heights without changing DOM order', async ({ page }) => {
    await gotoApp(page, APP_URL);

    await waitForAppReady(page);

    const layout = await page.evaluate(async () => {
      if (!customElements.get('test-height-card')) {
        class TestHeightCard extends HTMLElement {
          static get observedAttributes() {
            return ['ref'];
          }

          constructor() {
            super();
            this.attachShadow({ mode: 'open' });
          }

          connectedCallback() {
            this.render();
          }

          attributeChangedCallback() {
            this.render();
          }

          render() {
            const ref = this.getAttribute('ref') || 'a';
            const heights = { a: 340, b: 120, c: 150, d: 110 };
            const height = heights[ref] || 120;
            this.shadowRoot.innerHTML = `
              <style>
                :host { display: block; }
                .card {
                  height: ${height}px;
                  border-radius: 14px;
                  background: linear-gradient(180deg, #f5f7f7 0%, #e4ecec 100%);
                  border: 1px solid rgba(0, 70, 74, 0.12);
                  box-sizing: border-box;
                }
              </style>
              <div class="card"></div>
            `;
          }
        }

        customElements.define('test-height-card', TestHeightCard);
      }

      const host = document.createElement('section');
      host.innerHTML = `
        <ntx-list id="packed-layout-test" model="Demo" display="xl">
          <template item-template>
            <test-height-card></test-height-card>
          </template>
        </ntx-list>
      `;
      document.body.appendChild(host);

      const list = host.querySelector('#packed-layout-test');
      list.style.display = 'block';
      list.style.width = '960px';
      list.schema = { __name__: 'Demo', access: {}, ui: {} };
      list.value = ['a', 'b', 'c', 'd'];
      list.render();

      await new Promise((resolve) => {
        const grid = list.shadowRoot.querySelector('.list-grid');
        if (!grid) {
          resolve();
          return;
        }

        const isPacked = () => Array.from(grid.children).every((child) => child.style.gridRowEnd);
        let observer;
        const done = () => {
          observer?.disconnect();
          resolve();
        };
        if (isPacked()) {
          done();
          return;
        }

        observer = new MutationObserver(() => {
          if (!isPacked()) return;
          done();
        });
        observer.observe(grid, { attributes: true, subtree: true, attributeFilter: ['style'] });

        let frames = 0;
        const tick = () => {
          if (isPacked() || frames++ >= 30) {
            done();
            return;
          }
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });

      const grid = list.shadowRoot.querySelector('.list-grid');
      const packedClass = grid.classList.contains('list-grid--packed');
      const items = Array.from(grid.children).map((child) => {
        const rect = child.getBoundingClientRect();
        return {
          ref: child.getAttribute('ref'),
          top: rect.top,
          bottom: rect.bottom,
          left: rect.left,
        };
      });

      host.remove();

      return {
        refs: items.map((item) => item.ref),
        packedClass,
        items,
      };
    });

    expect(layout.packedClass).toBe(true);
    expect(layout.refs).toEqual(['a', 'b', 'c', 'd']);
    expect(layout.items).toHaveLength(4);

    const [first, second, third] = layout.items;
    expect(Math.abs(first.top - second.top)).toBeLessThan(4);
    expect(Math.abs(third.left - second.left)).toBeLessThan(4);
    expect(third.top).toBeLessThan(first.bottom - 40);
  });
});
