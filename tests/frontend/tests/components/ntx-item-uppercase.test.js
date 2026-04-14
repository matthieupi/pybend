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

import { NTTItem } from '../../components/ntx-item.js';
import { permissions } from '../../utils/Permissions.js';

function createItem(schema, value, opts = {}) {
  const el = document.createElement('ntx-item');
  el.schema = schema;
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

const productSchema = {
  __name__: 'Product',
  __tablename__: 'products',
  properties: {
    id: { type: 'integer', ui: { display: false } },
    name: { type: 'string', title: 'Name' },
    price: { type: 'number', title: 'Price' },
  },
  required: ['name'],
  ui: { field_order: ['name', 'price'] },
  access: {},
  methods: {},
};

describe('ntx-item detail-only title treatment', () => {
  beforeEach(() => {
    permissions.canAction.mockImplementation(() => true);
    permissions.canView.mockImplementation(() => true);
    permissions.canEdit.mockImplementation(() => true);
  });

  it('keeps pill titles in their original case for xs display', () => {
    const ctx = {
      value: { title: 'mixed case title' },
      schema: { __name__: 'Article' }
    };
    const html = NTTItem.prototype.xs.call(ctx);
    expect(html).toContain('mixed case title');
    expect(ctx.value.title).toBe('mixed case title');
  });

  it('keeps compact names in their original case for sm display', () => {
    const el = createItem(productSchema, {
      id: 1,
      name: 'mixed case title',
      price: 29.99,
    });
    const html = el.sm();
    expect(html).toContain('mixed case title');
    expect(el.value.name).toBe('mixed case title');
  });
});
