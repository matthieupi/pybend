import { describe, it, expect, vi } from 'vitest';

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
    canAction: vi.fn(() => true), canView: vi.fn(() => true), canEdit: vi.fn(() => true),
    user: null, authenticated: false, role: 'anonymous', init: vi.fn(() => Promise.resolve(null)),
  }
}));

import { NTTItem } from '../../components/ntx-item.js';

function createItem(schema, value) {
  const el = document.createElement('ntx-item');
  el.schema = schema;
  Object.defineProperty(el, '_testValue', { value, writable: true });
  Object.defineProperty(el, 'value', {
    get() { return this._testValue; },
    set(v) { this._testValue = v; },
    configurable: true,
  });
  el.mode = 'display';
  return el;
}

describe('ntx-item standalone method attrs', () => {
  it('passes button layout attrs to sm-row methods', () => {
    const schema = {
      __name__: 'Product',
      properties: {
        id: { type: 'integer', ui: { display: false } },
        name: { type: 'string', title: 'Name' },
      },
      methods: {
        favorite: {
          scope: 'instancemethod',
          title: 'Favorite',
          ui: {
            layout: 'button',
            icon: 'star',
            count_field: 'favorites',
          },
        },
      },
    };
    const el = createItem(schema, { id: 7, name: 'Widget', favorites: [] });

    const html = el.sm();

    expect(html).toContain('model="Product"');
    expect(html).toContain('uuid="7"');
    expect(html).toContain('method="favorite"');
    expect(html).toContain('layout="button"');
    expect(html).toContain('icon="star"');
    expect(html).toContain('count-field="favorites"');
    expect(html).toContain('label="Favorite"');
  });

  it('passes button-label, placeholder, and widget attrs to standalone methods', () => {
    const schema = {
      __name__: 'Source',
      properties: {
        id: { type: 'integer', ui: { display: false } },
        name: { type: 'string', title: 'Name' },
      },
      methods: {
        scrape_js: {
          scope: 'instancemethod',
          ui: {
            layout: 'fieldset',
            button_label: 'Fetch now',
            placeholder: 'Optional override',
            widget: 'textarea',
          },
        },
      },
    };
    const el = createItem(schema, { id: 1, name: 'Source A' });

    const html = el.lg();

    expect(html).toContain('button-label="Fetch now"');
    expect(html).toContain('placeholder="Optional override"');
    expect(html).toContain('widget="textarea"');
    expect(html).toContain('label="scrape js"');
  });

  it('passes inline method attrs from schema ui to standalone methods', () => {
    const schema = {
      __name__: 'Product',
      properties: {
        id: { type: 'integer', ui: { display: false } },
        name: { type: 'string', title: 'Name' },
      },
      methods: {
        comment: {
          scope: 'instancemethod',
          ui: {
            layout: 'inline',
            button_label: 'Post',
            placeholder: 'Add your comment...',
            widget: 'textarea',
          },
        },
      },
    };
    const el = createItem(schema, { id: 3, name: 'Widget' });

    const html = el.lg();

    expect(html).toContain('model="Product"');
    expect(html).toContain('uuid="3"');
    expect(html).toContain('method="comment"');
    expect(html).toContain('layout="inline"');
    expect(html).toContain('button-label="Post"');
    expect(html).toContain('placeholder="Add your comment..."');
    expect(html).toContain('widget="textarea"');
    expect(html).toContain('label="comment"');
  });
});
