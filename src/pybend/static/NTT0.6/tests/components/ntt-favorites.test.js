import { describe, it, expect, vi } from 'vitest';

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
         NAVIGATE: 'NAVIGATE', BACK: 'BACK', SELECT: 'SELECT', delete: 'DELETE', create: 'CREATE' },
    DEFAULT_HEADERS: {}, TIMEOUT: 5000, RETRY_LIMIT: 3,
  }
}));
vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));
vi.mock('../../utils/Permissions.js', () => ({
  permissions: {
    canAction: vi.fn(() => true), canView: vi.fn(() => true), canEdit: vi.fn(() => true),
    user: null, authenticated: false, role: 'anonymous', init: vi.fn(() => Promise.resolve(null)),
  }
}));

// Import after mocks — ntt-favorites has no named exports, just registers the custom element
await import('../../components/ntt-favorites.js');

describe('ntt-favorites.js (NTTFavorites)', () => {

  describe('custom element registration', () => {
    it('should be registered as ntt-favorites', () => {
      const Ctor = customElements.get('ntt-favorites');
      expect(Ctor).toBeTruthy();
    });
  });

  describe('constructor', () => {
    it('should create an element', () => {
      const el = document.createElement('ntt-favorites');
      expect(el).toBeTruthy();
      expect(el.tagName.toLowerCase()).toBe('ntt-favorites');
    });
  });

  describe('connectedCallback', () => {
    it('should render an ntt-list element', () => {
      const el = document.createElement('ntt-favorites');
      document.body.appendChild(el);
      const list = el.querySelector('ntt-list');
      expect(list).toBeTruthy();
      document.body.removeChild(el);
    });

    it('should set model attribute to ProductLike on the ntt-list', () => {
      const el = document.createElement('ntt-favorites');
      document.body.appendChild(el);
      const list = el.querySelector('ntt-list');
      expect(list.getAttribute('model')).toBe('ProductLike');
      document.body.removeChild(el);
    });

    it('should set display attribute to md on the ntt-list', () => {
      const el = document.createElement('ntt-favorites');
      document.body.appendChild(el);
      const list = el.querySelector('ntt-list');
      expect(list.getAttribute('display')).toBe('md');
      document.body.removeChild(el);
    });
  });
});
