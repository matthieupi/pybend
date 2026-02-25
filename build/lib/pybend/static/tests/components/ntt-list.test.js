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

import { NTTList } from '../../components/ntt-list.js';
import { ListElement } from '../../components/ListElement.js';

describe('ntt-list.js (NTTList)', () => {
  it('should be registered as ntt-list custom element', () => {
    expect(customElements.get('ntt-list')).toBe(NTTList);
  });

  it('should have styles getter returning CSS URL', () => {
    const desc = Object.getOwnPropertyDescriptor(NTTList.prototype, 'styles');
    expect(desc).toBeTruthy();
  });

  it('should inherit all ListElement behavior', () => {
    expect(typeof NTTList.prototype.loadMore).toBe('function');
    expect(typeof NTTList.prototype.render).toBe('function');
    expect(typeof NTTList.prototype.select).toBe('function');
  });

  it('should extend ListElement', () => {
    expect(NTTList.prototype instanceof ListElement).toBe(true);
  });
});

describe('ListElement (via NTTList)', () => {

  describe('SIZE_CASCADE', () => {
    it('should map parent xl to child md', () => {
      expect(ListElement.SIZE_CASCADE.xl).toBe('md');
    });

    it('should map parent lg to child sm', () => {
      expect(ListElement.SIZE_CASCADE.lg).toBe('sm');
    });

    it('should map parent md to child sm', () => {
      expect(ListElement.SIZE_CASCADE.md).toBe('sm');
    });

    it('should map parent sm to child xs', () => {
      expect(ListElement.SIZE_CASCADE.sm).toBe('xs');
    });

    it('should map parent xs to child xs', () => {
      expect(ListElement.SIZE_CASCADE.xs).toBe('xs');
    });
  });

  describe('Selection API', () => {
    it('select() should add address to selected set', () => {
      const el = document.createElement('ntt-list');
      el.select('addr-1');
      expect(el.selected.has('addr-1')).toBe(true);
    });

    it('deselect() should remove address from selected set', () => {
      const el = document.createElement('ntt-list');
      el.select('addr-1');
      el.deselect('addr-1');
      expect(el.selected.has('addr-1')).toBe(false);
    });

    it('toggle() should add if not present', () => {
      const el = document.createElement('ntt-list');
      el.toggle('addr-1');
      expect(el.selected.has('addr-1')).toBe(true);
    });

    it('toggle() should remove if present', () => {
      const el = document.createElement('ntt-list');
      el.select('addr-1');
      el.toggle('addr-1');
      expect(el.selected.has('addr-1')).toBe(false);
    });

    it('clearSelection() should empty the set', () => {
      const el = document.createElement('ntt-list');
      el.select('addr-1');
      el.select('addr-2');
      el.clearSelection();
      expect(el.selected.size).toBe(0);
    });
  });

  describe('childTag resolution', () => {
    it('should default to ntt-item', () => {
      const el = document.createElement('ntt-list');
      expect(el.childTag).toBe('ntt-item');
    });

    it('should respect item-tag attribute', () => {
      const el = document.createElement('ntt-list');
      el.setAttribute('item-tag', 'custom-item');
      expect(el.childTag).toBe('custom-item');
    });

    it('should use schema renderer hint', () => {
      const el = document.createElement('ntt-list');
      el.schema = { ui: { renderer: { item: 'ntt-user' } } };
      expect(el.childTag).toBe('ntt-user');
    });
  });

  describe('createChild(addr)', () => {
    it('should create child element with correct tag', () => {
      const el = document.createElement('ntt-list');
      const child = el.createChild('http://localhost:5000/products/1');
      expect(child.tagName.toLowerCase()).toBe('ntt-item');
    });

    it('should set ref on child', () => {
      const el = document.createElement('ntt-list');
      const child = el.createChild('http://localhost:5000/products/1');
      expect(child.ref || child.getAttribute('ref')).toBeTruthy();
    });

    it('should set select-target to list address', () => {
      const el = document.createElement('ntt-list');
      const child = el.createChild('http://localhost:5000/products/1');
      expect(child.getAttribute('select-target')).toBeTruthy();
    });
  });
});
