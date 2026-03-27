import { describe, it, expect, vi, beforeEach } from 'vitest';

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

describe('ntx-router.js (NTTRouter)', () => {

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
  });
});
