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

import { NTTRow } from '../../components/ntx-row.js';
import { Formidable } from '../../generators/form.js';
import { permissions } from '../../utils/Permissions.js';

// Helper to create an NTTRow element with schema and value
function createRow(schema, value, opts = {}) {
  const el = document.createElement('ntx-row');
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

// Grant-like schema for testing
const grantSchema = {
  __name__: 'Grant',
  __tablename__: 'grants',
  properties: {
    id: { type: 'integer', ui: { display: false } },
    title: { type: 'string', title: 'Title', minLength: 1 },
    agency: { type: 'string', title: 'Agency' },
    deadline: { type: 'string', title: 'Deadline', ui: { widget: 'date' } },
    amount_min: { type: 'number', title: 'Amount Min', ui: { widget: 'currency' } },
    amount_max: { type: 'number', title: 'Amount Max', ui: { widget: 'currency' } },
    url: { type: 'string', title: 'URL', ui: { widget: 'url' } },
    status: { type: 'string', title: 'Status' },
    user_owner: { type: '$ref', $ref: '#/$defs/User', title: 'Owner', ui: { protected: true } },
  },
  required: ['title', 'agency', 'url'],
  ui: { field_order: ['title', 'agency', 'deadline', 'amount_min', 'amount_max', 'url', 'status', 'user_owner'] },
  access: { update: { rule: 'anyone' }, delete: { rule: 'anyone' } },
  methods: {},
  $defs: { User: { ui: { renderer: { item: 'ntx-user' } } } },
};

describe('ntx-row.js (NTTRow)', () => {

  beforeEach(() => {
    permissions.canAction.mockImplementation(() => true);
    permissions.canView.mockImplementation(() => true);
    permissions.canEdit.mockImplementation(() => true);
  });

  describe('protected fields in edit mode', () => {
    it('should NOT render an edit input for protected fields like user_owner', () => {
      const el = createRow(grantSchema, {
        id: 1, title: 'Test Grant', agency: 'NSF', url: 'https://example.com',
        user_owner: 'http://localhost:5000/users/1',
      }, { mode: 'edit' });
      el.render();

      // user_owner is protected — should NOT have an input for it
      const ownerInput = el.shadowRoot.querySelector('[data-key="user_owner"]');
      expect(ownerInput).toBeNull();
    });

    it('should still render edit inputs for non-protected fields', () => {
      const el = createRow(grantSchema, {
        id: 1, title: 'Test Grant', agency: 'NSF', url: 'https://example.com',
      }, { mode: 'edit' });
      el.render();

      const titleInput = el.shadowRoot.querySelector('[data-key="title"]');
      expect(titleInput).not.toBeNull();
    });
  });

  describe('validation before save', () => {
    it('should validate fields before saving and block on errors', () => {
      const el = createRow(grantSchema, {
        id: 1, title: '', agency: 'NSF', url: 'https://example.com',
      }, { mode: 'edit', ref: 'http://localhost:5000/grants/1' });
      el.save = vi.fn();
      el.render();

      // Set empty title in the input
      const titleInput = el.shadowRoot.querySelector('[data-key="title"]');
      if (titleInput) titleInput.value = '';

      el.toggleMode();

      // Should NOT have called save because title is required and empty
      expect(el.save).not.toHaveBeenCalled();
      // Should remain in edit mode
      expect(el.mode).toBe('edit');
    });

    it('should call save when validation passes', () => {
      const el = createRow(grantSchema, {
        id: 1, title: 'Valid Grant', agency: 'NSF', url: 'https://example.com',
      }, { mode: 'edit', ref: 'http://localhost:5000/grants/1' });
      el.save = vi.fn();
      el.render();

      el.toggleMode();

      expect(el.save).toHaveBeenCalled();
      expect(el.mode).toBe('display');
    });
  });

  describe('widget-aware edit cells', () => {
    it('should render date input for date widget fields', () => {
      const el = createRow(grantSchema, {
        id: 1, title: 'Grant', agency: 'NSF', deadline: '2025-12-31',
        url: 'https://example.com',
      }, { mode: 'edit' });
      el.render();

      const deadlineInput = el.shadowRoot.querySelector('[data-key="deadline"]');
      expect(deadlineInput).not.toBeNull();
      // Should be a date input, not a plain text input
      expect(deadlineInput.type).toBe('date');
    });

    it('should render url input for url widget fields', () => {
      const el = createRow(grantSchema, {
        id: 1, title: 'Grant', agency: 'NSF', url: 'https://example.com',
      }, { mode: 'edit' });
      el.render();

      const urlInput = el.shadowRoot.querySelector('[data-key="url"]');
      expect(urlInput).not.toBeNull();
      // Should be a url input, not a plain text input
      expect(urlInput.type).toBe('url');
    });
  });

  describe('error banner in row', () => {
    it('should render error banner when error is set', () => {
      const el = createRow(grantSchema, {
        id: 1, title: 'Grant', agency: 'NSF', url: 'https://example.com',
      });
      el.error = 'Database update failed';
      el.render();

      expect(el.shadowRoot.innerHTML).toContain('ntx-error');
      expect(el.shadowRoot.innerHTML).toContain('Database update failed');
    });

    it('should not render error banner when error is null', () => {
      const el = createRow(grantSchema, {
        id: 1, title: 'Grant', agency: 'NSF', url: 'https://example.com',
      });
      el.error = null;
      el.render();

      expect(el.shadowRoot.innerHTML).not.toContain('ntx-error');
    });
  });
});
