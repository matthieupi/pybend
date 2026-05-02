import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => { if (!cond) throw new Error(msg); }),
  caution: vi.fn(), inform: vi.fn(),
}));
vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3, LOGEVENTS: false, LOGSPAWN: false, DEBUG: false,
    API_URL: 'http://localhost:5000', WS_URL: 'ws://localhost:8765',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', ENABLE: 'ENABLE', DISABLE: 'DISABLE',
         SCHEMA: 'SCHEMA', DESCRIBE: 'DESCRIBE', connect: 'CONNECT', update: 'UPDATE', read: 'READ',
         NAVIGATE: 'NAVIGATE', BACK: 'BACK', SELECT: 'SELECT' },
    DEFAULT_HEADERS: {}, TIMEOUT: 5000, RETRY_LIMIT: 3,
  }
}));
vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import { NTTRouter } from '../../components/ntx-router.js';
import { getRouter } from '../../core/Router.js';

describe('ntx-router.js (NTTRouter)', () => {

  beforeEach(() => {
    window.location.hash = '';
    document.body.innerHTML = '';
    delete window.NTT;
  });

  afterEach(() => {
    document.body.innerHTML = '';
    window.location.hash = '';
    delete window.NTT;
  });

  describe('custom element registration', () => {
    it('should be registered as ntx-router', () => {
      expect(customElements.get('ntx-router')).toBe(NTTRouter);
    });
  });

  describe('constructor', () => {
    it('should create element with shadow DOM', () => {
      const el = document.createElement('ntx-router');
      expect(el.shadowRoot).toBeTruthy();
    });
  });

  describe('styles getter', () => {
    it('should return CSS URL', () => {
      const desc = Object.getOwnPropertyDescriptor(NTTRouter.prototype, 'styles');
      expect(desc).toBeTruthy();
    });
  });

  describe('prerender()', () => {
    it('should create persistent chrome and content structure', () => {
      const el = document.createElement('ntx-router');
      el.prerender();
      const sr = el.shadowRoot;
      expect(sr.querySelector('.router-chrome')).toBeTruthy();
      expect(sr.querySelector('.router-chrome').hidden).toBe(true);
      expect(sr.querySelector('.back-btn')).toBeTruthy();
      expect(sr.querySelector('.router-title')).toBeTruthy();
      expect(sr.querySelector('.router-content')).toBeTruthy();
      expect(sr.querySelector('.router-content slot')).toBeTruthy();
    });
  });

  describe('render()', () => {
    it('should show slot when no route (chrome hidden)', () => {
      const el = document.createElement('ntx-router');
      el.prerender();
      el.render();
      const sr = el.shadowRoot;
      expect(sr.querySelector('.router-chrome').hidden).toBe(true);
      expect(sr.querySelector('.router-content slot')).toBeTruthy();
    });

    it('should enable URL sync by default when mounted without hash attribute', () => {
      const el = document.createElement('ntx-router');
      el.setAttribute('name', 'router-default-hash');
      document.body.appendChild(el);

      const router = getRouter('router-default-hash');
      router.NAVIGATE('Product/9');

      expect(window.location.hash).toBe('#Product/9');
    });

    it('should hide router chrome when deep-linked with no back history', async () => {
      window.location.hash = '#Product/9';

      const el = document.createElement('ntx-router');
      el.setAttribute('name', 'router-deeplink');
      document.body.appendChild(el);

      await Promise.resolve();

      const sr = el.shadowRoot;
      expect(sr.querySelector('.router-chrome').hidden).toBe(true);
      expect(sr.querySelector('.router-content ntx-item')).toBeTruthy();
    });

    it('should mount collection default view routes from deep links', async () => {
      window.location.hash = '#Product/@';
      window.NTT = {
        get: vi.fn(() => ({ schema: { ui: { renderer: { page: 'ntx-products-page', list: 'ntx-products' } } } })),
      };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-view-deeplink-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      const mounted = el.shadowRoot.querySelector('.router-content ntx-products-page');
      expect(mounted).toBeTruthy();
      expect(mounted.getAttribute('model')).toBe('Product');
      expect(mounted.getAttribute('router')).toBe(el.getAttribute('name'));
      expect(el.shadowRoot.querySelector('.router-chrome').hidden).toBe(true);
    });

    it('should mount named collection view routes from schema renderers', async () => {
      window.location.hash = '#Product/@table';
      window.NTT = {
        get: vi.fn(() => ({ schema: { ui: { renderer: { table: 'ntx-product-table' } } } })),
      };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-named-view-deeplink-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      const mounted = el.shadowRoot.querySelector('.router-content ntx-product-table');
      expect(mounted).toBeTruthy();
      expect(mounted.getAttribute('model')).toBe('Product');
      expect(mounted.getAttribute('router')).toBe(el.getAttribute('name'));
    });

    it('should mount named collection view fallback components', async () => {
      window.location.hash = '#Product/@table';
      window.NTT = { get: vi.fn(() => ({ schema: {} })) };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-named-view-fallback-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      const mounted = el.shadowRoot.querySelector('.router-content ntx-table');
      expect(mounted).toBeTruthy();
      expect(mounted.getAttribute('model')).toBe('Product');
    });

    it('should not mount unknown custom collection views without schema renderers', async () => {
      window.location.hash = '#Product/@custom-card';
      window.NTT = { get: vi.fn(() => ({ schema: {} })) };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-unknown-custom-view-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      expect(el.shadowRoot.querySelector('.router-content ntx-custom-card')).toBeFalsy();
      expect(el.shadowRoot.querySelector('.router-content slot')).toBeTruthy();
    });

    it('should mount member default view routes from schema renderers', async () => {
      window.location.hash = '#Product/1/@';
      window.NTT = {
        get: vi.fn(() => ({ schema: { ui: { renderer: { detail: 'ntx-product-detail', item: 'ntx-product-card' } } } })),
      };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-member-view-deeplink-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      const mounted = el.shadowRoot.querySelector('.router-content ntx-product-detail');
      expect(mounted).toBeTruthy();
      expect(mounted.getAttribute('ref')).toBe('Product/1');
      expect(mounted.getAttribute('display')).toBe('lg');
      expect(mounted.hasAttribute('method')).toBe(false);
    });

    it('should mount named member view routes from schema renderers', async () => {
      window.location.hash = '#Product/1/@item';
      window.NTT = {
        get: vi.fn(() => ({ schema: { ui: { renderer: { item: 'ntx-product-card' } } } })),
      };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-named-member-view-deeplink-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      const mounted = el.shadowRoot.querySelector('.router-content ntx-product-card');
      expect(mounted).toBeTruthy();
      expect(mounted.getAttribute('ref')).toBe('Product/1');
      expect(mounted.getAttribute('display')).toBe('lg');
      expect(mounted.hasAttribute('method')).toBe(false);
    });

    it('should mount same-named member view without method attrs', async () => {
      window.location.hash = '#Product/1/@run';
      window.NTT = {
        get: vi.fn(() => ({
          schema: {
            ui: { renderer: { run: 'ntx-run-view' } },
            methods: { run: { ui: { renderer: 'ntx-run-method' } } },
          },
        })),
      };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-run-member-view-deeplink-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      const mounted = el.shadowRoot.querySelector('.router-content ntx-run-view');
      expect(mounted).toBeTruthy();
      expect(mounted.getAttribute('ref')).toBe('Product/1');
      expect(mounted.hasAttribute('method')).toBe(false);
    });

    it('should mount nested class-name detail routes with child model hint and absolute nested ref', async () => {
      window.location.hash = '#Product/1/Comment/2';
      window.NTT = {
        get: vi.fn((model) => ({
          schema: { ui: { renderer: model === 'Comment' ? { item: 'ntx-comment-card' } : { item: 'ntx-product-card' } } },
        })),
      };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-nested-detail-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      const mounted = el.shadowRoot.querySelector('.router-content ntx-comment-card');
      expect(mounted).toBeTruthy();
      expect(window.NTT.get).toHaveBeenCalledWith('Comment');
      expect(mounted.getAttribute('data-model')).toBe('Comment');
      expect(mounted.getAttribute('ref')).toBe('http://localhost:5000/Product/1/Comment/2');
      expect(mounted.getAttribute('display')).toBe('lg');
      expect(mounted.hasAttribute('method')).toBe(false);
    });

    it('should mount nested class-name named views without method attrs', async () => {
      window.location.hash = '#Product/1/Comment/2/@like';
      window.NTT = {
        get: vi.fn(() => ({
          schema: {
            ui: { renderer: { like: 'ntx-like-view' } },
            methods: { like: { ui: { renderer: 'ntx-like-method' } } },
          },
        })),
      };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-nested-view-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      const mounted = el.shadowRoot.querySelector('.router-content ntx-like-view');
      expect(mounted).toBeTruthy();
      expect(mounted.getAttribute('data-model')).toBe('Comment');
      expect(mounted.getAttribute('ref')).toBe('http://localhost:5000/Product/1/Comment/2');
      expect(mounted.hasAttribute('method')).toBe(false);
    });

    it('should mount nested class-name action routes with method attrs', async () => {
      window.location.hash = '#Product/1/Comment/2/like';
      window.NTT = {
        get: vi.fn(() => ({
          schema: { methods: { like: { ui: { renderer: 'ntx-like-method' } } } },
        })),
      };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-nested-action-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      const mounted = el.shadowRoot.querySelector('.router-content ntx-like-method');
      expect(mounted).toBeTruthy();
      expect(mounted.getAttribute('data-model')).toBe('Comment');
      expect(mounted.getAttribute('ref')).toBe('http://localhost:5000/Product/1/Comment/2');
      expect(mounted.getAttribute('method')).toBe('like');
      expect(mounted.getAttribute('display')).toBe('lg');
    });

    it('should not mount invalid view routes or arbitrary extra components', async () => {
      window.location.hash = '#Product/1/@item/extra';
      window.NTT = { get: vi.fn(() => ({ schema: {} })) };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-invalid-view-route-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      expect(el.shadowRoot.querySelector('.router-content ntx-extra')).toBeFalsy();
      expect(el.shadowRoot.querySelector('.router-content slot')).toBeTruthy();
    });

    it('should not mount invalid nested extra segments as arbitrary components', async () => {
      window.location.hash = '#Product/1/Comment/2/@item/extra';
      window.NTT = { get: vi.fn(() => ({ schema: {} })) };

      const el = document.createElement('ntx-router');
      el.setAttribute('name', `router-invalid-nested-route-${Math.random().toString(36).slice(2)}`);
      document.body.appendChild(el);

      await Promise.resolve();

      expect(el.shadowRoot.querySelector('.router-content ntx-extra')).toBeFalsy();
      expect(el.shadowRoot.querySelector('.router-content slot')).toBeTruthy();
    });

    it('should mount model detail views with ref and display attributes', async () => {
      const el = document.createElement('ntx-router');
      el.setAttribute('name', 'router-detail-render');
      document.body.appendChild(el);

      getRouter('router-detail-render').NAVIGATE('Product/1');
      await Promise.resolve();

      const item = el.shadowRoot.querySelector('.router-content ntx-item');
      expect(item).toBeTruthy();
      expect(item.getAttribute('ref')).toBe('Product/1');
      expect(item.getAttribute('display')).toBe('lg');
    });

    it('should mount app routes as ntx-prefixed components', async () => {
      const el = document.createElement('ntx-router');
      el.setAttribute('name', 'router-app-route');
      document.body.appendChild(el);

      getRouter('router-app-route').NAVIGATE('@profile');
      await Promise.resolve();

      expect(el.shadowRoot.querySelector('.router-content ntx-profile')).toBeTruthy();
      expect(el.shadowRoot.querySelector('.router-title').textContent).toBe('Profile');
    });

    it('should mount unknown app routes without throwing', async () => {
      const el = document.createElement('ntx-router');
      el.setAttribute('name', 'router-unknown-app-route');
      document.body.appendChild(el);

      getRouter('router-unknown-app-route').NAVIGATE('@unknown');
      await Promise.resolve();

      expect(el.shadowRoot.querySelector('.router-content ntx-unknown')).toBeTruthy();
      expect(el.shadowRoot.querySelector('.router-title').textContent).toBe('Unknown');
    });
  });
});
