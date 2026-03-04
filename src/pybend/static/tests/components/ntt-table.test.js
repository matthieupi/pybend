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

import { NTTTable } from '../../components/ntt-table.js';
import { permissions } from '../../utils/Permissions.js';

describe('ntt-table.js (NTTTable)', () => {

  beforeEach(() => {
    permissions.canAction.mockImplementation(() => true);
    permissions.canView.mockImplementation(() => true);
  });

  describe('sort indicator in header cells', () => {
    it('should render sort arrow in a separate span so it is not truncated', () => {
      const el = document.createElement('ntt-table');
      const schema = {
        __name__: 'Grant',
        properties: {
          title: { type: 'string', title: 'A Very Long Column Name That Will Get Truncated' },
          agency: { type: 'string', title: 'Agency' },
        },
        ui: { field_order: ['title', 'agency'] },
        access: {},
        methods: {},
      };
      el.schema = schema;
      el.value = [];
      Object.defineProperty(el, 'proto', { value: { _paginationMeta: null }, configurable: true });

      // First render: no sort active
      el.render();
      const firstHeader = el.shadowRoot.querySelector('.header-cell[data-sort="title"]');
      expect(firstHeader).not.toBeNull();

      // Label text should be in its own span
      const labelSpan = firstHeader.querySelector('.header-label');
      expect(labelSpan).not.toBeNull();
      expect(labelSpan.textContent).toBe('A Very Long Column Name That Will Get Truncated');

      // Click header to sort, then manually re-render (scheduleRender is async)
      firstHeader.click();
      el.render();

      // After sort, the arrow should be in its own span element
      const arrow = el.shadowRoot.querySelector('.header-cell[data-sort="title"] .sort-arrow');
      expect(arrow).not.toBeNull();
      expect(arrow.textContent.trim()).toMatch(/[▲▼]/);
    });

    it('should separate label from arrow to prevent ellipsis from clipping the arrow', () => {
      const el = document.createElement('ntt-table');
      el.schema = {
        __name__: 'Test',
        properties: {
          name: { type: 'string', title: 'Name' },
        },
        ui: { field_order: ['name'] },
        access: {},
        methods: {},
      };
      el.value = [];
      Object.defineProperty(el, 'proto', { value: { _paginationMeta: null }, configurable: true });
      el.render();

      // Click to sort
      el.shadowRoot.querySelector('.header-cell[data-sort="name"]').click();
      el.render();

      // Arrow must be flex-shrink:0 (verified by being a separate element)
      const arrow = el.shadowRoot.querySelector('.sort-arrow');
      expect(arrow).not.toBeNull();
      // Label must be in its own element
      const label = el.shadowRoot.querySelector('.header-label');
      expect(label).not.toBeNull();
    });
  });
});
