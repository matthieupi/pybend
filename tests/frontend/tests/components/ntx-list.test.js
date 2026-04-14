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

import { NTTList } from '../../components/ntx-list.js';
import { ListElement } from '../../components/ListElement.js';

const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve()));

describe('ntx-list.js (NTTList)', () => {
  it('should be registered as ntx-list custom element', () => {
    expect(customElements.get('ntx-list')).toBe(NTTList);
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

  it('should own the default list render implementation', () => {
    const desc = Object.getOwnPropertyDescriptor(NTTList.prototype, 'render');
    expect(desc).toBeTruthy();
  });

  it('should own the default surgical update implementation', () => {
    const desc = Object.getOwnPropertyDescriptor(NTTList.prototype, 'update');
    expect(desc).toBeTruthy();
  });

  it('should own the default modal create flow', () => {
    const desc = Object.getOwnPropertyDescriptor(NTTList.prototype, 'openCreateModal');
    expect(desc).toBeTruthy();
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
      const el = document.createElement('ntx-list');
      el.select('addr-1');
      expect(el.selected.has('addr-1')).toBe(true);
    });

    it('deselect() should remove address from selected set', () => {
      const el = document.createElement('ntx-list');
      el.select('addr-1');
      el.deselect('addr-1');
      expect(el.selected.has('addr-1')).toBe(false);
    });

    it('toggle() should add if not present', () => {
      const el = document.createElement('ntx-list');
      el.toggle('addr-1');
      expect(el.selected.has('addr-1')).toBe(true);
    });

    it('toggle() should remove if present', () => {
      const el = document.createElement('ntx-list');
      el.select('addr-1');
      el.toggle('addr-1');
      expect(el.selected.has('addr-1')).toBe(false);
    });

    it('clearSelection() should empty the set', () => {
      const el = document.createElement('ntx-list');
      el.select('addr-1');
      el.select('addr-2');
      el.clearSelection();
      expect(el.selected.size).toBe(0);
    });
  });

  describe('childTag resolution', () => {
    it('should default to ntx-item', () => {
      const el = document.createElement('ntx-list');
      expect(el.childTag).toBe('ntx-item');
    });

    it('should respect item-tag attribute', () => {
      const el = document.createElement('ntx-list');
      el.setAttribute('item-tag', 'custom-item');
      expect(el.childTag).toBe('custom-item');
    });

    it('should use schema renderer hint', () => {
      const el = document.createElement('ntx-list');
      el.schema = { ui: { renderer: { item: 'ntx-user' } } };
      expect(el.childTag).toBe('ntx-user');
    });
  });

  describe('createChild(addr)', () => {
    it('should create child element with correct tag', () => {
      const el = document.createElement('ntx-list');
      const child = el.createChild('http://localhost:5000/products/1');
      expect(child.tagName.toLowerCase()).toBe('ntx-item');
    });

    it('should set ref on child', () => {
      const el = document.createElement('ntx-list');
      const child = el.createChild('http://localhost:5000/products/1');
      expect(child.ref || child.getAttribute('ref')).toBeTruthy();
    });

    it('should set select-target to list address', () => {
      const el = document.createElement('ntx-list');
      const child = el.createChild('http://localhost:5000/products/1');
      expect(child.getAttribute('select-target')).toBeTruthy();
    });
  });

  describe('header icons', () => {
    it('should render schema ui.icon in the list header', () => {
      const el = document.createElement('ntx-list');
      el.model = 'Grant';
      el.schema = { __name__: 'Grant', ui: { icon: '💸' }, access: {} };
      el.value = [];
      Object.defineProperty(el, 'proto', {
        value: { _paginationMeta: null },
        configurable: true,
      });

      el.render();

      const icon = el.shadowRoot.querySelector('.list-title-wrap ntx-icon');
      expect(icon).not.toBeNull();
      expect(icon.getAttribute('value')).toBe('💸');
    });
  });

  describe('packed layout', () => {
    it('should assign row spans for wide card children', async () => {
      const el = document.createElement('ntx-list');
      el.model = 'Demo';
      el.schema = { __name__: 'Demo', ui: {}, access: {} };
      el.value = ['alpha', 'beta'];
      el.setAttribute('item-display', 'card');
      document.body.appendChild(el);

      el.render();

      const grid = el.shadowRoot.querySelector('.list-grid');
      const children = Array.from(grid.children);
      const heights = [120, 260];

      children.forEach((child, index) => {
        Object.defineProperty(child, 'getBoundingClientRect', {
          configurable: true,
          value: () => ({ height: heights[index] }),
        });
      });

      await nextFrame();

      expect(grid.classList.contains('list-grid--packed')).toBe(true);
      expect(children[0].style.gridRowEnd).toBe('span 15');
      expect(children[1].style.gridRowEnd).toBe('span 33');

      document.body.removeChild(el);
    });

    it('should stay disabled for sidebar dropdown lists', () => {
      const el = document.createElement('ntx-list');
      el.model = 'Demo';
      el.schema = { __name__: 'Demo', ui: {}, access: {} };
      el.value = ['alpha'];
      el.setAttribute('item-display', 'card');
      el.setAttribute('sidebar-dropdown', '');

      el.render();

      const grid = el.shadowRoot.querySelector('.list-grid');
      expect(grid.classList.contains('list-grid--packed')).toBe(false);
    });
  });
});
