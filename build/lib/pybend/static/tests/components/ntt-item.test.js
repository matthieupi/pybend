import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => { if (!cond) throw new Error(msg || 'Assertion failed'); }),
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
    canAction: vi.fn(() => true),
    canView: vi.fn(() => true),
    canEdit: vi.fn(() => true),
    user: null,
    authenticated: false,
    role: 'anonymous',
    init: vi.fn(() => Promise.resolve(null)),
  }
}));

import { NTTItem } from '../../components/ntt-item.js';
import { permissions } from '../../utils/Permissions.js';

/**
 * NTTItem test patterns:
 *
 * - prototype.call(ctx) is acceptable for pure-function methods that do NOT
 *   access private fields/methods (xs, handleInputChange, update, placeholder).
 *   These methods only build HTML or manipulate data without accessing #private.
 *
 * - For methods that access private members (#smFields, #resolveChildTag,
 *   #standaloneMethodsHtml, #bindEvents), use actual element instances created
 *   via document.createElement('ntt-item') with schema/value set directly on
 *   the element.
 */

// Helper to create an NTTItem element with schema and value set for testing.
function createItem(schema, value, opts = {}) {
  const el = document.createElement('ntt-item');
  el.schema = schema;
  // Set value directly on the underlying storage, bypassing the setter's
  // auto-render (which would trigger full lifecycle side-effects).
  Object.defineProperty(el, '_testValue', { value, writable: true });
  Object.defineProperty(el, 'value', {
    get() { return this._testValue; },
    set(v) { this._testValue = v; },
    configurable: true,
  });
  el.mode = opts.mode || 'display';
  el.ref = opts.ref || '';
  return el;
}

// Minimal product schema for testing
const productSchema = {
  __name__: 'Product',
  __tablename__: 'products',
  properties: {
    id: { type: 'integer', ui: { display: false } },
    name: { type: 'string', title: 'Name' },
    price: { type: 'number', title: 'Price', ui: { widget: 'currency' } },
    description: { type: 'string', title: 'Description', ui: { widget: 'textarea' } },
  },
  required: ['name'],
  ui: { field_order: ['name', 'price', 'description'] },
  access: {},
  methods: {},
};

describe('ntt-item.js (NTTItem)', () => {

  beforeEach(() => {
    permissions.canAction.mockImplementation(() => true);
    permissions.canView.mockImplementation(() => true);
    permissions.canEdit.mockImplementation(() => true);
  });

  describe('class definition', () => {
    it('should be defined and registered as ntt-item', () => {
      expect(typeof NTTItem).toBe('function');
      expect(customElements.get('ntt-item')).toBe(NTTItem);
    });
  });

  describe('mode property', () => {
    it('should default to "display"', () => {
      const el = document.createElement('ntt-item');
      expect(el.mode).toBe('display');
    });
  });

  describe('styles getter', () => {
    it('should return a CSS URL', () => {
      const desc = Object.getOwnPropertyDescriptor(NTTItem.prototype, 'styles');
      expect(desc).toBeTruthy();
    });
  });

  describe('placeholder(size)', () => {
    it('should return xs skeleton (pill)', () => {
      const html = NTTItem.prototype.placeholder('xs');
      expect(html).toContain('bone');
      expect(html).toContain('border-radius:999px');
    });

    it('should return sm skeleton (avatar + name)', () => {
      const html = NTTItem.prototype.placeholder('sm');
      expect(html).toContain('bone');
      expect(html).toContain('border-radius:50%');
    });

    it('should return md/lg/xl skeleton (text lines)', () => {
      const html = NTTItem.prototype.placeholder('md');
      expect(html).toContain('bone');
    });
  });

  describe('xs() size method', () => {
    it('should return pill HTML with name', () => {
      const ctx = {
        value: { name: 'Product A' },
        schema: { __name__: 'Product' }
      };
      const html = NTTItem.prototype.xs.call(ctx);
      expect(html).toContain('pill-label');
      expect(html).toContain('Product A');
    });

    it('should fallback to title when no name', () => {
      const ctx = {
        value: { title: 'My Title' },
        schema: { __name__: 'Article' }
      };
      const html = NTTItem.prototype.xs.call(ctx);
      expect(html).toContain('My Title');
    });

    it('should fallback to schema name when no name/title', () => {
      const ctx = {
        value: {},
        schema: { __name__: 'Widget' }
      };
      const html = NTTItem.prototype.xs.call(ctx);
      expect(html).toContain('Widget');
    });
  });

  describe('sm() size method', () => {
    it('should render name and currency fields', () => {
      const el = createItem(productSchema, {
        id: 1, name: 'Test Product', price: 29.99, description: 'desc',
      });
      const html = el.sm();
      expect(html).toContain('sm-name');
      expect(html).toContain('Test Product');
      expect(html).toContain('$29.99');
    });

    it('should render method buttons with button layout', () => {
      const schema = {
        ...productSchema,
        methods: {
          like: {
            scope: 'instancemethod',
            ui: { layout: 'button', icon: 'heart', count_field: 'likes' },
            title: 'Like',
          },
        },
      };
      const el = createItem(schema, { id: 1, name: 'Product' });
      const html = el.sm();
      expect(html).toContain('ntt-method');
      expect(html).toContain('layout="button"');
    });

    it('should render reply button when reply method exists', () => {
      const schema = {
        ...productSchema,
        methods: {
          reply: {
            scope: 'instancemethod',
            ui: { layout: 'inline', placeholder: 'Write a reply...' },
            title: 'Reply',
          },
        },
      };
      const el = createItem(schema, { id: 1, name: 'Comment' });
      const html = el.sm();
      expect(html).toContain('sm-reply-btn');
    });

    it('should render action buttons when permissions allow', () => {
      const schema = {
        ...productSchema,
        access: { update: { rule: 'anyone' }, delete: { rule: 'anyone' } },
      };
      const el = createItem(schema, { id: 1, name: 'Product' });
      const html = el.sm();
      expect(html).toContain('edit-btn');
      expect(html).toContain('delete-btn');
      expect(html).toContain('sm-actions');
    });

    it('should delegate to md() in edit mode', () => {
      const el = createItem(productSchema, {
        id: 1, name: 'Product', price: 10, description: 'test',
      }, { mode: 'edit', ref: 'http://localhost:5000/products/1' });
      el.name = 'Product';
      const html = el.sm();
      // md() renders a form via Formidable - just check it renders something
      expect(html).toBeTruthy();
      expect(typeof html).toBe('string');
    });

    it('should resolve $ref field as leading avatar', () => {
      const schema = {
        __name__: 'Comment',
        properties: {
          id: { type: 'integer', ui: { display: false } },
          user: { type: '$ref', $ref: '#/$defs/User' },
          name: { type: 'string' },
        },
        ui: { field_order: ['user', 'name'] },
        $defs: { User: { ui: { renderer: { item: 'ntt-user' } } } },
        access: {},
        methods: {},
      };
      const el = createItem(schema, {
        id: 1, user: 'http://localhost:5000/users/1', name: 'Comment',
      });
      const html = el.sm();
      expect(html).toContain('ntt-user');
      expect(html).toContain('display="xs"');
    });
  });

  describe('#smFields() — field filtering (via sm())', () => {
    it('should filter out id fields', () => {
      const el = createItem(productSchema, { id: 1, name: 'Test', price: 10 });
      const html = el.sm();
      expect(html).not.toContain('data-value="id"');
    });

    it('should filter out fields with ui.display=false', () => {
      const schema = {
        ...productSchema,
        properties: {
          ...productSchema.properties,
          secret: { type: 'string', ui: { display: false } },
        },
      };
      const el = createItem(schema, { id: 1, name: 'Test', secret: 'hidden' });
      const html = el.sm();
      expect(html).not.toContain('hidden');
    });

    it('should filter out array fields', () => {
      const schema = {
        ...productSchema,
        properties: {
          ...productSchema.properties,
          tags: { type: 'array', items: { type: 'string' } },
        },
      };
      const el = createItem(schema, { id: 1, name: 'Test', tags: ['a', 'b'] });
      const html = el.sm();
      expect(html).not.toContain('data-value="tags"');
    });

    it('should filter out selfref fields', () => {
      const schema = {
        __name__: 'Comment',
        properties: {
          id: { type: 'integer', ui: { display: false } },
          name: { type: 'string' },
          parent_id: { type: 'selfref' },
        },
        ui: {},
        access: {},
        methods: {},
      };
      const el = createItem(schema, { id: 1, name: 'Reply', parent_id: 5 });
      const html = el.sm();
      expect(html).not.toContain('data-value="parent_id"');
    });

    it('should filter out fields where canView returns false', () => {
      permissions.canView.mockImplementation((def) => {
        if (def?.access?.view === 'admin') return false;
        return true;
      });
      const schema = {
        ...productSchema,
        properties: {
          ...productSchema.properties,
          secret: { type: 'string', access: { view: 'admin' } },
        },
      };
      const el = createItem(schema, { id: 1, name: 'Test', secret: 'hidden' });
      const html = el.sm();
      expect(html).not.toContain('data-value="secret"');
    });
  });

  describe('md() size method', () => {
    it('should render card with action buttons when permitted', () => {
      const schema = {
        ...productSchema,
        access: { update: { rule: 'anyone' }, delete: { rule: 'anyone' } },
      };
      const el = createItem(schema, {
        id: 1, name: 'Product', price: 29.99, description: 'A test',
      }, { ref: 'http://localhost:5000/products/1' });
      el.name = 'Product';
      const html = el.md();
      expect(html).toContain('card-actions');
      expect(html).toContain('edit-btn');
      expect(html).toContain('delete-btn');
    });

    it('should render image when value has image', () => {
      const el = createItem(productSchema, {
        id: 1, name: 'Product', image: 'http://example.com/img.png',
      }, { ref: 'http://localhost:5000/products/1' });
      el.name = 'Product';
      const html = el.md();
      expect(html).toContain('card-image');
      expect(html).toContain('http://example.com/img.png');
    });

    it('should render standalone methods in display mode', () => {
      const schema = {
        ...productSchema,
        methods: {
          like: {
            scope: 'instancemethod',
            title: 'Like',
            ui: { layout: 'button', icon: 'heart', count_field: 'likes' },
          },
        },
      };
      const el = createItem(schema, { id: 1, name: 'Product' }, {
        ref: 'http://localhost:5000/products/1',
      });
      el.name = 'Product';
      const html = el.md();
      expect(html).toContain('ntt-method');
    });

    it('should NOT render standalone methods in edit mode', () => {
      const schema = {
        ...productSchema,
        methods: {
          like: {
            scope: 'instancemethod',
            title: 'Like',
            ui: { layout: 'button', icon: 'heart', count_field: 'likes' },
          },
        },
      };
      const el = createItem(schema, { id: 1, name: 'Product' }, {
        ref: 'http://localhost:5000/products/1',
        mode: 'edit',
      });
      el.name = 'Product';
      const html = el.md();
      expect(html).not.toContain('ntt-method');
    });
  });

  describe('lg() and xl()', () => {
    it('should delegate to md()', () => {
      const mdMock = vi.fn(() => '<div>md</div>');
      const ctx = { md: mdMock, schema: { properties: {} }, value: {}, mode: 'display' };
      NTTItem.prototype.lg.call(ctx);
      expect(mdMock).toHaveBeenCalled();
    });

    it('xl should also delegate to md()', () => {
      const mdMock = vi.fn(() => '<div>md-xl</div>');
      const ctx = { md: mdMock };
      NTTItem.prototype.xl.call(ctx);
      expect(mdMock).toHaveBeenCalled();
    });
  });

  describe('handleInputChange(e)', () => {
    it('should handle text input', () => {
      const ctx = { value: { name: 'old' } };
      const e = { target: { dataset: { key: 'name', type: 'string' }, value: 'new', type: 'text' } };
      NTTItem.prototype.handleInputChange.call(ctx, e);
      expect(ctx.value.name).toBe('new');
    });

    it('should handle checkbox input', () => {
      const ctx = { value: { active: false } };
      const e = { target: { dataset: { key: 'active', type: 'boolean' }, type: 'checkbox', checked: true } };
      NTTItem.prototype.handleInputChange.call(ctx, e);
      expect(ctx.value.active).toBe(true);
    });

    it('should handle number input', () => {
      const ctx = { value: { price: 0 } };
      const e = { target: { dataset: { key: 'price', type: 'number' }, value: '42.50', type: 'number' } };
      NTTItem.prototype.handleInputChange.call(ctx, e);
      expect(ctx.value.price).toBe(42.50);
    });

    it('should handle array element update', () => {
      const ctx = { value: { tags: ['a', 'b'] } };
      const e = { target: { dataset: { key: 'tags', index: '1', type: 'string' }, value: 'c', type: 'text' } };
      NTTItem.prototype.handleInputChange.call(ctx, e);
      expect(ctx.value.tags[1]).toBe('c');
    });

    it('should create array if missing when index is provided', () => {
      const ctx = { value: {} };
      const e = { target: { dataset: { key: 'items', index: '0', type: 'string' }, value: 'new', type: 'text' } };
      NTTItem.prototype.handleInputChange.call(ctx, e);
      expect(ctx.value.items[0]).toBe('new');
    });
  });

  describe('update(prev, next)', () => {
    it('should return false if prev is null', () => {
      const result = NTTItem.prototype.update.call(
        { shadowRoot: document.createElement('div'), _rendered: true, schema: { properties: {} } },
        null, {}
      );
      expect(result).toBe(false);
    });

    it('should return false if next is null', () => {
      const result = NTTItem.prototype.update.call(
        { shadowRoot: document.createElement('div'), _rendered: true, schema: { properties: {} } },
        {}, null
      );
      expect(result).toBe(false);
    });

    it('should return false if not yet rendered', () => {
      const result = NTTItem.prototype.update.call(
        { shadowRoot: document.createElement('div'), _rendered: false, schema: { properties: {} } },
        { name: 'a' }, { name: 'b' }
      );
      expect(result).toBe(false);
    });
  });

  describe('render()', () => {
    it('should be a function on prototype', () => {
      expect(typeof NTTItem.prototype.render).toBe('function');
    });

    it('should no-op if no schema or value', () => {
      const ctx = {
        schema: null,
        value: null,
        displayMode: 'md',
        shadowRoot: document.createElement('div'),
      };
      NTTItem.prototype.render.call(ctx);
    });

    // Note: render() calls #bindEvents() which is a private method.
    // Testing render dispatch via actual elements rather than prototype.call
    // to avoid "Receiver must be an instance" errors.
    it('should dispatch to the correct size method via element', () => {
      const schema = {
        __name__: 'Test',
        properties: { name: { type: 'string' } },
        ui: {},
        access: {},
        methods: {},
      };
      const el = createItem(schema, { name: 'Test' });
      // Override displayMode getter for test
      Object.defineProperty(el, 'displayMode', { get: () => 'xs', configurable: true });
      el.render();
      expect(el.shadowRoot.innerHTML).toContain('pill-label');
    });

    it('should add reply-indent class for replies with parent_id', () => {
      const schema = {
        __name__: 'Comment',
        properties: {
          name: { type: 'string' },
          parent_id: { type: 'selfref' },
        },
        ui: {},
        access: {},
        methods: {},
      };
      const el = createItem(schema, { name: 'Reply', parent_id: 5 });
      Object.defineProperty(el, 'displayMode', { get: () => 'xs', configurable: true });
      el.render();
      expect(el.shadowRoot.innerHTML).toContain('reply-indent');
    });

    it('should NOT add reply-indent for top-level items', () => {
      const schema = {
        __name__: 'Comment',
        properties: {
          name: { type: 'string' },
          parent_id: { type: 'selfref' },
        },
        ui: {},
        access: {},
        methods: {},
      };
      const el = createItem(schema, { name: 'Top', parent_id: null });
      Object.defineProperty(el, 'displayMode', { get: () => 'xs', configurable: true });
      el.render();
      expect(el.shadowRoot.innerHTML).not.toContain('reply-indent');
    });
  });

  describe('deleteItem()', () => {
    it('should abort when canAction returns false for delete', () => {
      permissions.canAction.mockImplementation(() => false);
      const confirmSpy = vi.spyOn(globalThis, 'confirm');
      const ctx = {
        schema: { __name__: 'Product', access: { delete: { rule: 'admin' } } },
        value: { id: 1, $id: 'http://localhost:5000/products/1' },
      };
      NTTItem.prototype.deleteItem.call(ctx);
      expect(confirmSpy).not.toHaveBeenCalled();
    });

    it('should abort when confirm() returns false', () => {
      vi.spyOn(globalThis, 'confirm').mockReturnValue(false);
      const ctx = {
        schema: { __name__: 'Product', access: { delete: { rule: 'anyone' } } },
        value: { id: 1, $id: 'http://localhost:5000/products/1' },
      };
      NTTItem.prototype.deleteItem.call(ctx);
      expect(globalThis.confirm).toHaveBeenCalled();
    });
  });

  describe('toggleMode()', () => {
    it('should abort when canAction returns false for update', () => {
      permissions.canAction.mockImplementation(() => false);
      const renderSpy = vi.fn();
      const ctx = {
        schema: { __name__: 'Product', access: { update: { rule: 'admin' } } },
        value: { id: 1 },
        mode: 'display',
        render: renderSpy,
      };
      NTTItem.prototype.toggleMode.call(ctx);
      expect(renderSpy).not.toHaveBeenCalled();
      expect(ctx.mode).toBe('display');
    });

    it('should toggle from display to edit when permitted', () => {
      const renderSpy = vi.fn();
      const ctx = {
        schema: { __name__: 'Product', access: { update: { rule: 'anyone' } } },
        value: { id: 1 },
        mode: 'display',
        save: vi.fn(),
        render: renderSpy,
      };
      NTTItem.prototype.toggleMode.call(ctx);
      expect(ctx.mode).toBe('edit');
      expect(renderSpy).toHaveBeenCalled();
    });

    it('should toggle from edit to display and call save()', () => {
      const saveSpy = vi.fn();
      const renderSpy = vi.fn();
      const ctx = {
        schema: { __name__: 'Product', access: { update: { rule: 'anyone' } } },
        value: { id: 1 },
        mode: 'edit',
        save: saveSpy,
        render: renderSpy,
      };
      NTTItem.prototype.toggleMode.call(ctx);
      expect(saveSpy).toHaveBeenCalled();
      expect(ctx.mode).toBe('display');
    });
  });

  describe('permission-denied UI paths', () => {
    it('should hide edit/delete buttons in md() when denied', () => {
      permissions.canAction.mockImplementation(() => false);
      const schema = {
        ...productSchema,
        access: { update: { rule: 'owner' }, delete: { rule: 'admin' } },
      };
      const el = createItem(schema, { id: 1, name: 'Product' }, {
        ref: 'http://localhost:5000/products/1',
      });
      el.name = 'Product';
      const html = el.md();
      expect(html).not.toContain('edit-btn');
      expect(html).not.toContain('delete-btn');
      expect(html).not.toContain('card-actions');
    });

    it('should hide action buttons in sm() when denied', () => {
      permissions.canAction.mockImplementation(() => false);
      const schema = {
        ...productSchema,
        access: { update: { rule: 'owner' }, delete: { rule: 'admin' } },
      };
      const el = createItem(schema, { id: 1, name: 'Product' });
      const html = el.sm();
      expect(html).not.toContain('edit-btn');
      expect(html).not.toContain('delete-btn');
      expect(html).not.toContain('sm-actions');
    });
  });
});
