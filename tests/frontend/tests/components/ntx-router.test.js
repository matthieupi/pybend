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
  });

  afterEach(() => {
    document.body.innerHTML = '';
    window.location.hash = '';
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
