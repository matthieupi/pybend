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

import { NTTUser } from '../../components/ntx-user.js';
import { NTTItem } from '../../components/ntx-item.js';

describe('ntx-user.js (NTTUser)', () => {

  describe('custom element registration', () => {
    it('should be registered as ntx-user', () => {
      expect(customElements.get('ntx-user')).toBe(NTTUser);
    });
  });

  describe('inheritance', () => {
    it('should extend NTTItem', () => {
      expect(NTTUser.prototype instanceof NTTItem).toBe(true);
    });

    it('should inherit md, lg, xl methods from NTTItem', () => {
      expect(typeof NTTUser.prototype.md).toBe('function');
      expect(typeof NTTUser.prototype.lg).toBe('function');
      expect(typeof NTTUser.prototype.xl).toBe('function');
    });

    it('should override xs method', () => {
      expect(NTTUser.prototype.xs).not.toBe(NTTItem.prototype.xs);
    });

    it('should override sm method', () => {
      expect(NTTUser.prototype.sm).not.toBe(NTTItem.prototype.sm);
    });
  });

  describe('styles getter', () => {
    it('should return a CSS URL string', () => {
      const el = document.createElement('ntx-user');
      const styles = el.styles;
      expect(typeof styles).toBe('string');
      expect(styles).toContain('ntx-user.css');
    });
  });

  // Note: xs() and sm() use #avatarUrl() which is a private method.
  // We cannot call xs()/sm() via prototype.call(ctx) because private
  // methods require the receiver to be an actual instance of the class.
  // Instead, we create real NTTUser elements with value set directly.

  describe('xs()', () => {
    it('should render an img element with class user-avatar', () => {
      const el = document.createElement('ntx-user');
      Object.defineProperty(el, 'value', {
        get: () => ({ name: 'Alice', email: 'alice@test.com' }),
        configurable: true,
      });
      const html = el.xs();
      expect(html).toContain('<img');
      expect(html).toContain('class="user-avatar"');
    });

    it('should use image URL when value.image exists', () => {
      const el = document.createElement('ntx-user');
      Object.defineProperty(el, 'value', {
        get: () => ({ name: 'Alice', email: 'alice@test.com', image: 'https://example.com/photo.jpg' }),
        configurable: true,
      });
      const html = el.xs();
      expect(html).toContain('src="https://example.com/photo.jpg"');
    });

    it('should use ui-avatars.com fallback when no image', () => {
      const el = document.createElement('ntx-user');
      Object.defineProperty(el, 'value', {
        get: () => ({ name: 'Alice', email: 'alice@test.com' }),
        configurable: true,
      });
      const html = el.xs();
      expect(html).toContain('ui-avatars.com');
      expect(html).toContain('name=Alice');
    });

    it('should encode name for URL', () => {
      const el = document.createElement('ntx-user');
      Object.defineProperty(el, 'value', {
        get: () => ({ name: 'John Doe', email: 'john@test.com' }),
        configurable: true,
      });
      const html = el.xs();
      expect(html).toContain('name=John%20Doe');
    });
  });

  describe('sm()', () => {
    it('should render avatar img and name span', () => {
      const el = document.createElement('ntx-user');
      Object.defineProperty(el, 'value', {
        get: () => ({ name: 'Alice', email: 'alice@test.com' }),
        configurable: true,
      });
      const html = el.sm();
      expect(html).toContain('<img');
      expect(html).toContain('user-avatar');
      expect(html).toContain('sm-name');
      expect(html).toContain('Alice');
    });

    it('should use email prefix when name is missing', () => {
      const el = document.createElement('ntx-user');
      Object.defineProperty(el, 'value', {
        get: () => ({ email: 'bob@test.com' }),
        configurable: true,
      });
      const html = el.sm();
      expect(html).toContain('bob');
    });

    it('should fallback to "User" when both name and email are missing', () => {
      const el = document.createElement('ntx-user');
      Object.defineProperty(el, 'value', {
        get: () => ({}),
        configurable: true,
      });
      const html = el.sm();
      expect(html).toContain('User');
    });
  });
});
