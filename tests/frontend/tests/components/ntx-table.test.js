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

import { NTTTable } from '../../components/ntx-table.js';
import { Formidable } from '../../generators/form.js';
import { permissions } from '../../utils/Permissions.js';

// Grant-like schema with protected/$ref field for create-row tests
const grantSchema = {
  __name__: 'Grant',
  __tablename__: 'grants',
  properties: {
    id: { type: 'integer', ui: { display: false } },
    title: { type: 'string', title: 'Title', minLength: 1 },
    agency: { type: 'string', title: 'Agency' },
    amount: { type: 'number', title: 'Amount' },
    user_owner: { type: '$ref', $ref: '#/$defs/User', title: 'Owner', ui: { protected: true } },
  },
  required: ['title'],
  ui: { field_order: ['title', 'agency', 'amount', 'user_owner'] },
  access: {},
  methods: {},
};

/** Helper: create an NTTTable wired with schema, proto mock, and allow-create. */
function createTable(schema = grantSchema, opts = {}) {
  const el = document.createElement('ntx-table');
  el.setAttribute('allow-create', '');
  el.schema = schema;
  el.value = opts.value || [];
  const callMock = vi.fn();
  const observeMock = vi.fn(() => vi.fn()); // returns unsubscribe
  Object.defineProperty(el, 'proto', {
    value: { _paginationMeta: null, call: callMock, observe: observeMock },
    configurable: true,
    writable: true,
  });
  return { el, callMock, observeMock };
}

describe('ntx-table.js (NTTTable)', () => {

  beforeEach(() => {
    permissions.canAction.mockImplementation(() => true);
    permissions.canView.mockImplementation(() => true);
  });

  describe('header icons', () => {
    it('should render schema ui.icon in the table header', () => {
      const { el } = createTable({
        ...grantSchema,
        ui: { ...grantSchema.ui, icon: '💸' },
      });
      el.render();

      const icon = el.shadowRoot.querySelector('.list-title-wrap ntx-icon');
      expect(icon).not.toBeNull();
      expect(icon.getAttribute('value')).toBe('💸');
    });
  });


  /* ────────────────────────────────────────────── */
  /*   Inline Create: Column Filtering               */
  /* ────────────────────────────────────────────── */

  describe('createColumns() excludes protected and $ref fields', () => {
    it('should NOT include protected/$ref fields in createColumns()', () => {
      const { el } = createTable();
      const createCols = el.createColumns();
      expect(createCols).not.toContain('user_owner');
      expect(createCols).toContain('title');
      expect(createCols).toContain('agency');
    });

    it('should still include protected/$ref fields in tableColumns() (display)', () => {
      const { el } = createTable();
      const tableCols = el.tableColumns();
      expect(tableCols).toContain('user_owner');
    });
  });


  /* ────────────────────────────────────────────── */
  /*   Inline Create: Input Rendering                */
  /* ────────────────────────────────────────────── */

  describe('create row inputs use createColumns', () => {
    it('should NOT render an input for protected fields in the create row', () => {
      const { el } = createTable();
      el.render();
      // Open create row
      el.shadowRoot.querySelector('.inline-add-btn')?.click();
      const ownerInput = el.shadowRoot.querySelector('.create-row [data-key="user_owner"]');
      expect(ownerInput).toBeNull();
    });

    it('should render inputs for non-protected fields in the create row', () => {
      const { el } = createTable();
      el.render();
      el.shadowRoot.querySelector('.inline-add-btn')?.click();
      const titleInput = el.shadowRoot.querySelector('.create-row [data-key="title"]');
      expect(titleInput).not.toBeNull();
    });
  });


  /* ────────────────────────────────────────────── */
  /*   Inline Create: Client-side Validation         */
  /* ────────────────────────────────────────────── */

  describe('#submitCreate() validation', () => {
    it('should show error and NOT call proto.call when required field is empty', () => {
      const { el, callMock } = createTable();
      el.render();
      // Open create row
      el.shadowRoot.querySelector('.inline-add-btn')?.click();
      // Fill agency but leave title empty (title is required)
      const agencyInput = el.shadowRoot.querySelector('.create-row [data-key="agency"]');
      if (agencyInput) agencyInput.value = 'NSF';
      // Click save
      el.shadowRoot.querySelector('.save-create-btn')?.click();
      // Should have error indicator on title
      const titleInput = el.shadowRoot.querySelector('.create-row [data-key="title"]');
      expect(titleInput?.classList.contains('input-error')).toBe(true);
      // proto.call should NOT have been called
      expect(callMock).not.toHaveBeenCalled();
    });
  });


  /* ────────────────────────────────────────────── */
  /*   Inline Create: Keep Row Open After Submit     */
  /* ────────────────────────────────────────────── */

  describe('#submitCreate() keeps create row visible', () => {
    it('should keep create row visible after a valid submit', () => {
      const { el, callMock } = createTable();
      el.render();
      // Open create row
      el.shadowRoot.querySelector('.inline-add-btn')?.click();
      // Fill required field
      const titleInput = el.shadowRoot.querySelector('.create-row [data-key="title"]');
      if (titleInput) titleInput.value = 'New Grant';
      // Submit
      el.shadowRoot.querySelector('.save-create-btn')?.click();
      // proto.call should have been called
      expect(callMock).toHaveBeenCalled();
      // Create row should still be visible (not hidden)
      const row = el.shadowRoot.querySelector('.create-row');
      expect(row?.style.display).not.toBe('none');
    });

    it('should disable inputs while pending (loading state)', () => {
      const { el } = createTable();
      el.render();
      el.shadowRoot.querySelector('.inline-add-btn')?.click();
      const titleInput = el.shadowRoot.querySelector('.create-row [data-key="title"]');
      if (titleInput) titleInput.value = 'New Grant';
      el.shadowRoot.querySelector('.save-create-btn')?.click();
      // Inputs should be disabled while pending
      const inputs = el.shadowRoot.querySelectorAll('.create-row input');
      inputs.forEach(input => {
        expect(input.disabled).toBe(true);
      });
    });
  });


  /* ────────────────────────────────────────────── */
  /*   Inline Create: Successful Create Closes Row   */
  /* ────────────────────────────────────────────── */

  describe('update() closes create row on successful addition', () => {
    it('should close create row when update() receives new additions while pending', () => {
      const { el } = createTable();
      el.render();
      // Open create row and submit
      el.shadowRoot.querySelector('.inline-add-btn')?.click();
      const titleInput = el.shadowRoot.querySelector('.create-row [data-key="title"]');
      if (titleInput) titleInput.value = 'New Grant';
      el.shadowRoot.querySelector('.save-create-btn')?.click();
      // Simulate backend response: update() with a new address
      const result = el.update([], ['Grant/1']);
      // Create row should be hidden now
      const row = el.shadowRoot.querySelector('.create-row');
      expect(row?.style.display).toBe('none');
      // Create button should be visible
      const btn = el.shadowRoot.querySelector('.create-btn-row');
      expect(btn?.style.display).not.toBe('none');
    });
  });


  /* ────────────────────────────────────────────── */
  /*   Inline Create: Error Recovery                 */
  /* ────────────────────────────────────────────── */

  describe('create error re-enables the create row', () => {
    it('should re-enable inputs and show errors on ERROR event', () => {
      const { el, observeMock } = createTable();
      el.render();
      // Open create row and submit
      el.shadowRoot.querySelector('.inline-add-btn')?.click();
      const titleInput = el.shadowRoot.querySelector('.create-row [data-key="title"]');
      if (titleInput) titleInput.value = 'New Grant';
      el.shadowRoot.querySelector('.save-create-btn')?.click();
      // Inputs should be disabled (loading)
      expect(titleInput?.disabled).toBe(true);

      // Simulate ERROR observer callback
      // Find the ERROR observer registration from definedCallback or render
      // and fire it manually
      el.handleCreateError({ data: { detail: 'Validation failed' } });

      // After error: inputs should be re-enabled
      expect(titleInput?.disabled).toBe(false);
      // Create row should still be visible
      const row = el.shadowRoot.querySelector('.create-row');
      expect(row?.style.display).not.toBe('none');
    });
  });


  /* ────────────────────────────────────────────── */
  /*   Sort Indicator (existing tests)               */
  /* ────────────────────────────────────────────── */

  describe('sort indicator in header cells', () => {
    it('should render sort arrow in a separate span so it is not truncated', () => {
      const el = document.createElement('ntx-table');
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
      const el = document.createElement('ntx-table');
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
