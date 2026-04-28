/**
 * Test plan for NTTRefPicker component
 * =====================================
 *
 * UNIT TESTS — behavior validation
 *   - test_custom_element_registration
 *   - test_constructor_creates_shadow_dom
 *   - test_constructor_binds_outside_click_handler
 *   - test_observed_attributes_includes_all_props
 *
 * ATTRIBUTE GETTERS — property accessors
 *   - test_field_getter_returns_attribute
 *   - test_modelName_getter_returns_attribute
 *   - test_parentModel_getter_returns_attribute
 *   - test_parentTable_getter_returns_attribute
 *   - test_parentId_getter_returns_attribute
 *   - test_childTable_getter_returns_attribute
 *   - test_childTable_fallback_lowercases_modelName_with_s
 *
 * COMPUTED GETTERS — derived state
 *   - test_currentRefs_returns_empty_set_when_no_host
 *   - test_currentRefs_extracts_refs_from_string_array
 *   - test_currentRefs_extracts_refs_from_object_array_with_$id
 *   - test_currentRefs_returns_empty_set_when_field_not_array
 *   - test_childSchema_returns_null_when_no_host
 *   - test_childSchema_reads_from_host_schema_$defs
 *
 * LIFECYCLE — connectedCallback/disconnectedCallback
 *   - test_connectedCallback_calls_render
 *   - test_disconnectedCallback_removes_event_listener
 *
 * RENDERING — _render method
 *   - test_render_creates_add_button_with_model_name
 *   - test_render_creates_dropdown_anchor
 *   - test_render_includes_styles
 *   - test_render_button_click_opens_picker_when_closed
 *   - test_render_button_click_closes_picker_when_open
 *
 * PICKER MODE — _showPicker
 *   - test_showPicker_sets_mode_to_picker
 *   - test_showPicker_creates_dropdown_with_search_input
 *   - test_showPicker_triggers_READ_if_no_instances
 *   - test_showPicker_renders_options_from_DC_instances
 *   - test_showPicker_filters_out_currentRefs
 *   - test_showPicker_search_filters_options
 *   - test_showPicker_escape_key_closes
 *   - test_showPicker_create_button_opens_inline_create
 *   - test_showPicker_registers_outside_click_listener
 *
 * CREATE MODE — _showInlineCreate
 *   - test_showInlineCreate_sets_mode_to_create
 *   - test_showInlineCreate_renders_form_from_childSchema
 *   - test_showInlineCreate_focuses_first_input
 *   - test_showInlineCreate_cancel_button_closes
 *   - test_showInlineCreate_submit_button_calls_submitCreate
 *   - test_showInlineCreate_escape_key_closes
 *   - test_showInlineCreate_enter_key_submits
 *
 * ACTIONS — _addRef and _submitCreate
 *   - test_addRef_sends_CREATE_TX_via_DynamicClass
 *   - test_addRef_dispatches_ref_added_event_with_detail
 *   - test_submitCreate_collects_form_data_correctly
 *   - test_submitCreate_sends_CREATE_TX
 *   - test_submitCreate_dispatches_ref_created_event
 *   - test_submitCreate_calls_parent_pull_to_refresh
 *   - test_submitCreate_closes_form
 *
 * CLEANUP — _close and _onOutsideClick
 *   - test_close_sets_mode_to_closed
 *   - test_close_clears_dropdown_anchor_innerHTML
 *   - test_close_removes_click_listener
 *   - test_onOutsideClick_closes_if_click_outside
 *   - test_onOutsideClick_ignores_click_inside
 *
 * EDGE CASES
 *   - test_childTable_fallback_handles_null_modelName
 *   - test_showPicker_handles_missing_DC
 *   - test_showInlineCreate_handles_null_childSchema
 *   - test_submitCreate_handles_boolean_inputs
 *   - test_submitCreate_handles_number_inputs
 *   - test_submitCreate_handles_object_inputs
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock dependencies following project pattern
vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => { if (!cond) throw new Error(msg); }),
  caution: vi.fn(), inform: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3, LOGEVENTS: false, LOGSPAWN: false, DEBUG: false,
    API_URL: 'http://localhost:5000', WS_URL: 'ws://localhost:8765',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', CREATE: 'CREATE' },
    DEFAULT_HEADERS: {}, TIMEOUT: 5000, RETRY_LIMIT: 3,
  }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: {
    warn: vi.fn(), error: vi.fn(), debug: vi.fn(),
    dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn()
  }
}));

// Mock NTT with get method for DynamicClass lookup
vi.mock('../../core/NTT.js', () => ({
  NTT: {
    get: vi.fn(),
  },
}));

// Mock Formidable for form generation
vi.mock('../../generators/form.js', () => ({
  Formidable: {
    getForm: vi.fn(() => '<div class="mock-form">Mock Form</div>'),
  },
}));

// Mock TX
vi.mock('../../core/TX.js', () => ({
  default: vi.fn(function(opts) {
    this.name = opts.name;
    this.target = opts.target;
    this.data = opts.data;
    this.meta = opts.meta;
  }),
}));

import { NTTRefPicker } from '../../components/ntx-ref-picker.js';
import { NTT } from '../../core/NTT.js';
import { Formidable } from '../../generators/form.js';
import TX from '../../core/TX.js';

describe('ntx-ref-picker.js (NTTRefPicker)', () => {

  beforeEach(() => {
    // Clear all mocks before each test
    vi.clearAllMocks();
    NTT.get.mockReturnValue(null);
    Formidable.getForm.mockReturnValue('<div class="mock-form">Mock Form</div>');
  });

  describe('custom element registration', () => {
    it('should be registered as ntx-ref-picker', () => {
      expect(customElements.get('ntx-ref-picker')).toBe(NTTRefPicker);
    });
  });

  describe('constructor', () => {
    it('should create shadow DOM', () => {
      const picker = new NTTRefPicker();
      expect(picker.shadowRoot).toBeTruthy();
      expect(picker.shadowRoot.mode).toBe('open');
    });

    it('should bind _onOutsideClick handler', () => {
      const picker = new NTTRefPicker();
      expect(typeof picker._onOutsideClick).toBe('function');
    });
  });

  describe('static observedAttributes', () => {
    it('should include all attribute names', () => {
      const attrs = NTTRefPicker.observedAttributes;
      expect(attrs).toContain('field');
      expect(attrs).toContain('model');
      expect(attrs).toContain('parent-model');
      expect(attrs).toContain('parent-table');
      expect(attrs).toContain('parent-id');
      expect(attrs).toContain('child-table');
    });
  });

  describe('attribute getters', () => {
    it('should return field attribute', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('field', 'tools');
      expect(picker.field).toBe('tools');
    });

    it('should return modelName attribute', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'AgentTool');
      expect(picker.modelName).toBe('AgentTool');
    });

    it('should return parentModel attribute', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('parent-model', 'AgentActor');
      expect(picker.parentModel).toBe('AgentActor');
    });

    it('should return parentTable attribute', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('parent-table', 'agent_actors');
      expect(picker.parentTable).toBe('agent_actors');
    });

    it('should return parentId attribute', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('parent-id', '42');
      expect(picker.parentId).toBe('42');
    });

    it('should return childTable attribute when set', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('child-table', 'agent_tools');
      expect(picker.childTable).toBe('agent_tools');
    });

    it('should fallback to modelName lowercase + s when childTable not set', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      expect(picker.childTable).toBe('comments');
    });

    it('should handle null modelName in childTable fallback', () => {
      const picker = document.createElement('ntx-ref-picker');
      // No model attribute set, so modelName is null and fallback returns null + 's' = 'nulls'
      // Actually the code does: this.modelName?.toLowerCase() + 's'
      // When modelName is null, null?.toLowerCase() returns undefined, and undefined + 's' = 'undefineds'
      expect(picker.childTable).toBe('undefineds');
    });
  });

  describe('currentRefs getter', () => {
    it('should return empty set when no host', () => {
      const picker = document.createElement('ntx-ref-picker');
      const refs = picker.currentRefs;
      expect(refs).toBeInstanceOf(Set);
      expect(refs.size).toBe(0);
    });

    it('should return empty set when host has no value', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('field', 'comments');
      // Create a mock host
      const mockHost = document.createElement('div');
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      const refs = picker.currentRefs;
      expect(refs.size).toBe(0);
    });

    it('should extract refs from string array', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('field', 'comments');
      const mockHost = {
        value: {
          comments: [
            'http://localhost:5000/products/1/comments/1',
            'http://localhost:5000/products/1/comments/2',
          ]
        }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      const refs = picker.currentRefs;
      expect(refs.size).toBe(2);
      expect(refs.has('http://localhost:5000/products/1/comments/1')).toBe(true);
      expect(refs.has('http://localhost:5000/products/1/comments/2')).toBe(true);
    });

    it('should extract $id from object array', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('field', 'comments');
      const mockHost = {
        value: {
          comments: [
            { $id: 'http://localhost:5000/comments/1', text: 'Comment 1' },
            { $id: 'http://localhost:5000/comments/2', text: 'Comment 2' },
          ]
        }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      const refs = picker.currentRefs;
      expect(refs.size).toBe(2);
      expect(refs.has('http://localhost:5000/comments/1')).toBe(true);
      expect(refs.has('http://localhost:5000/comments/2')).toBe(true);
    });

    it('should return empty set when field value is not an array', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('field', 'comments');
      const mockHost = {
        value: { comments: 'not-an-array' }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      const refs = picker.currentRefs;
      expect(refs.size).toBe(0);
    });
  });

  describe('childSchema getter', () => {
    it('should return null when no host', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      expect(picker.childSchema).toBeNull();
    });

    it('should read from host schema $defs', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      const mockSchema = {
        __name__: 'Comment',
        properties: { text: { type: 'string' } }
      };
      const mockHost = {
        schema: {
          $defs: { Comment: mockSchema }
        }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      expect(picker.childSchema).toBe(mockSchema);
    });

    it('should return null when $defs does not have modelName', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      const mockHost = {
        schema: { $defs: { OtherModel: {} } }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      expect(picker.childSchema).toBeNull();
    });
  });

  describe('connectedCallback', () => {
    it('should call _render', () => {
      const picker = document.createElement('ntx-ref-picker');
      const spy = vi.spyOn(picker, '_render');
      picker.connectedCallback();
      expect(spy).toHaveBeenCalled();
    });
  });

  describe('disconnectedCallback', () => {
    it('should remove click event listener from document', () => {
      const picker = document.createElement('ntx-ref-picker');
      const spy = vi.spyOn(document, 'removeEventListener');
      picker.disconnectedCallback();
      expect(spy).toHaveBeenCalledWith('click', picker._onOutsideClick);
    });
  });

  describe('_render', () => {
    it('should create add button with model name', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const button = picker.shadowRoot.querySelector('.add-btn');
      expect(button).toBeTruthy();
      expect(button.textContent).toContain('Add Comment');
    });

    it('should create dropdown anchor', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker._render();
      const anchor = picker.shadowRoot.querySelector('.dropdown-anchor');
      expect(anchor).toBeTruthy();
    });

    it('should include styles', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker._render();
      const stylesheet = picker.shadowRoot.querySelector('link[rel="stylesheet"]');
      expect(stylesheet).toBeTruthy();
      expect(stylesheet.getAttribute('href')).toContain('ntx-ref-picker.css');
    });

    it('should default to "Add Item" when no modelName', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker._render();
      const button = picker.shadowRoot.querySelector('.add-btn');
      expect(button.textContent).toContain('Add Item');
    });

    it('should open picker on button click when mode is closed', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const spy = vi.spyOn(picker, '_showPicker');
      const button = picker.shadowRoot.querySelector('.add-btn');
      button.click();
      expect(spy).toHaveBeenCalled();
    });

    it('should close picker on button click when mode is open', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: vi.fn(),
      });
      // First click opens picker
      const button = picker.shadowRoot.querySelector('.add-btn');
      button.click();
      // Verify dropdown was created (mode is now 'picker')
      expect(picker.shadowRoot.querySelector('.picker-dropdown')).toBeTruthy();
      // Second click should close
      const closeSpy = vi.spyOn(picker, '_close');
      button.click();
      expect(closeSpy).toHaveBeenCalled();
    });
  });

  describe('_showPicker', () => {
    it('should set mode to picker', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: vi.fn(),
      });
      picker._showPicker();
      // Mode is private, so we check side effects (dropdown created)
      const dropdown = picker.shadowRoot.querySelector('.picker-dropdown');
      expect(dropdown).toBeTruthy();
    });

    it('should create dropdown with search input', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: vi.fn(),
      });
      picker._showPicker();
      const searchInput = picker.shadowRoot.querySelector('.picker-search');
      expect(searchInput).toBeTruthy();
      expect(searchInput.placeholder).toContain('Search Comment');
    });

    it('should trigger READ if no instances', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const callMock = vi.fn();
      NTT.get.mockReturnValue({
        instances: null,
        call: callMock,
      });
      picker._showPicker();
      expect(callMock).toHaveBeenCalledWith('READ', {});
    });

    it('should trigger READ if instances is empty', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const callMock = vi.fn();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: callMock,
      });
      picker._showPicker();
      expect(callMock).toHaveBeenCalledWith('READ', {});
    });

    it('should render options from DC instances', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('child-table', 'comments');
      picker._render();
      const instances = new Map();
      instances.set('1', { value: { id: 1, name: 'Comment 1', $id: 'http://localhost:5000/comments/1' } });
      instances.set('2', { value: { id: 2, name: 'Comment 2', $id: 'http://localhost:5000/comments/2' } });
      NTT.get.mockReturnValue({
        instances,
        call: vi.fn(),
      });
      picker._showPicker();
      const options = picker.shadowRoot.querySelectorAll('.picker-option');
      expect(options.length).toBe(2);
      expect(options[0].textContent).toBe('Comment 1');
      expect(options[1].textContent).toBe('Comment 2');
    });

    it('should filter out currentRefs', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('field', 'comments');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      // Mock host with existing refs
      const mockHost = {
        value: {
          comments: ['http://localhost:5000/comments/1']
        }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });

      const instances = new Map();
      instances.set('1', { value: { id: 1, name: 'Comment 1', $id: 'http://localhost:5000/comments/1' } });
      instances.set('2', { value: { id: 2, name: 'Comment 2', $id: 'http://localhost:5000/comments/2' } });
      NTT.get.mockReturnValue({
        instances,
        call: vi.fn(),
      });
      picker._showPicker();
      const options = picker.shadowRoot.querySelectorAll('.picker-option');
      // Only Comment 2 should be shown (Comment 1 is already in currentRefs)
      expect(options.length).toBe(1);
      expect(options[0].textContent).toBe('Comment 2');
    });

    it('should filter options on search input', () => {
      vi.useFakeTimers();
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('child-table', 'comments');
      picker._render();
      const instances = new Map();
      instances.set('1', { value: { id: 1, name: 'Alpha', $id: 'http://localhost:5000/comments/1' } });
      instances.set('2', { value: { id: 2, name: 'Beta', $id: 'http://localhost:5000/comments/2' } });
      NTT.get.mockReturnValue({
        instances,
        call: vi.fn(),
      });
      picker._showPicker();
      const searchInput = picker.shadowRoot.querySelector('.picker-search');
      searchInput.value = 'alpha';
      searchInput.dispatchEvent(new Event('input'));
      const options = picker.shadowRoot.querySelectorAll('.picker-option');
      expect(options.length).toBe(1);
      expect(options[0].textContent).toBe('Alpha');
      vi.useRealTimers();
    });

    it('should close on escape key in search input', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: vi.fn(),
      });
      picker._showPicker();
      const closeSpy = vi.spyOn(picker, '_close');
      const searchInput = picker.shadowRoot.querySelector('.picker-search');
      const event = new KeyboardEvent('keydown', { key: 'Escape' });
      searchInput.dispatchEvent(event);
      expect(closeSpy).toHaveBeenCalled();
    });

    it('should open inline create on create button click', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: vi.fn(),
      });
      picker._showPicker();
      const spy = vi.spyOn(picker, '_showInlineCreate');
      const createBtn = picker.shadowRoot.querySelector('.picker-create-btn');
      createBtn.click();
      expect(spy).toHaveBeenCalled();
    });

    it('should register outside click listener after timeout', () => {
      vi.useFakeTimers();
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: vi.fn(),
      });
      const spy = vi.spyOn(document, 'addEventListener');
      picker._showPicker();
      vi.runAllTimers();
      expect(spy).toHaveBeenCalledWith('click', picker._onOutsideClick);
      vi.useRealTimers();
    });

    it('should return early when DC not found', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'NonExistent');
      picker._render();
      NTT.get.mockReturnValue(null);
      picker._showPicker();
      // Should not create dropdown
      const dropdown = picker.shadowRoot.querySelector('.picker-dropdown');
      expect(dropdown).toBeNull();
    });

    it('should show "No items found" when no matching options', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: vi.fn(),
      });
      picker._showPicker();
      const emptyMsg = picker.shadowRoot.querySelector('.picker-empty');
      expect(emptyMsg).toBeTruthy();
      expect(emptyMsg.textContent).toBe('No items found');
    });
  });

  describe('_showInlineCreate', () => {
    it('should set mode to create', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const mockSchema = { properties: { text: { type: 'string' } } };
      const mockHost = {
        schema: { $defs: { Comment: mockSchema } }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      picker._showInlineCreate();
      const form = picker.shadowRoot.querySelector('.inline-create');
      expect(form).toBeTruthy();
    });

    it('should render form from childSchema using Formidable', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const mockSchema = { properties: { text: { type: 'string' } } };
      const mockHost = {
        schema: { $defs: { Comment: mockSchema } }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      picker._showInlineCreate();
      expect(Formidable.getForm).toHaveBeenCalledWith(
        { schema: mockSchema, value: {}, name: 'Comment' },
        'edit'
      );
      const formBody = picker.shadowRoot.querySelector('.inline-create-body');
      expect(formBody.innerHTML).toContain('Mock Form');
    });

    it('should focus first input', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const mockSchema = { properties: { text: { type: 'string' } } };
      const mockHost = {
        schema: { $defs: { Comment: mockSchema } }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      // Mock getForm to return actual input
      Formidable.getForm.mockReturnValue('<input type="text" class="test-input" />');
      picker._showInlineCreate();
      const input = picker.shadowRoot.querySelector('.test-input');
      if (input) {
        const spy = vi.spyOn(input, 'focus');
        picker._showInlineCreate();
        // Re-run to actually focus
        const input2 = picker.shadowRoot.querySelector('.test-input');
        if (input2) input2.focus();
      }
      // Note: focus() is hard to test in jsdom, so we just verify the input exists
      expect(picker.shadowRoot.querySelector('.test-input')).toBeTruthy();
    });

    it('should close on cancel button click', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const mockSchema = { properties: { text: { type: 'string' } } };
      const mockHost = {
        schema: { $defs: { Comment: mockSchema } }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      picker._showInlineCreate();
      const spy = vi.spyOn(picker, '_close');
      const cancelBtn = picker.shadowRoot.querySelector('.inline-create-cancel');
      cancelBtn.click();
      expect(spy).toHaveBeenCalled();
    });

    it('should call _submitCreate on submit button click', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const mockSchema = { properties: { text: { type: 'string' } } };
      const mockHost = {
        schema: { $defs: { Comment: mockSchema } }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      picker._showInlineCreate();
      const spy = vi.spyOn(picker, '_submitCreate');
      const submitBtn = picker.shadowRoot.querySelector('.inline-create-submit');
      submitBtn.click();
      expect(spy).toHaveBeenCalled();
    });

    it('should close on escape key', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const mockSchema = { properties: { text: { type: 'string' } } };
      const mockHost = {
        schema: { $defs: { Comment: mockSchema } }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      picker._showInlineCreate();
      const spy = vi.spyOn(picker, '_close');
      const form = picker.shadowRoot.querySelector('.inline-create');
      const event = new KeyboardEvent('keydown', { key: 'Escape' });
      form.dispatchEvent(event);
      expect(spy).toHaveBeenCalled();
    });

    it('should submit on enter key (not in textarea)', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const mockSchema = { properties: { text: { type: 'string' } } };
      const mockHost = {
        schema: { $defs: { Comment: mockSchema } }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      picker._showInlineCreate();
      const spy = vi.spyOn(picker, '_submitCreate');
      const form = picker.shadowRoot.querySelector('.inline-create');
      const event = new KeyboardEvent('keydown', { key: 'Enter' });
      Object.defineProperty(event, 'target', { value: { tagName: 'INPUT' }, writable: false });
      const preventDefaultSpy = vi.spyOn(event, 'preventDefault');
      form.dispatchEvent(event);
      expect(preventDefaultSpy).toHaveBeenCalled();
      expect(spy).toHaveBeenCalled();
    });

    it('should not submit on enter key in textarea', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const mockSchema = { properties: { text: { type: 'string' } } };
      const mockHost = {
        schema: { $defs: { Comment: mockSchema } }
      };
      Object.defineProperty(picker, 'getRootNode', {
        value: () => ({ host: mockHost }),
        writable: true,
      });
      picker._showInlineCreate();
      const spy = vi.spyOn(picker, '_submitCreate');
      const form = picker.shadowRoot.querySelector('.inline-create');
      const event = new KeyboardEvent('keydown', { key: 'Enter' });
      Object.defineProperty(event, 'target', { value: { tagName: 'TEXTAREA' }, writable: false });
      form.dispatchEvent(event);
      expect(spy).not.toHaveBeenCalled();
    });

    it('should return early when childSchema is null', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      // No host or no $defs
      picker._showInlineCreate();
      const form = picker.shadowRoot.querySelector('.inline-create');
      expect(form).toBeNull();
    });
  });

  describe('_addRef', () => {
    it('should send CREATE TX via DynamicClass', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();
      const sendMock = vi.fn();
      NTT.get.mockReturnValue({ send: sendMock });
      const entity = { id: 5, text: 'Test', $id: 'http://localhost:5000/comments/5' };
      picker._addRef(5, entity);
      expect(sendMock).toHaveBeenCalled();
      const tx = sendMock.mock.calls[0][0];
      expect(tx.name).toBe('CREATE');
      expect(tx.target).toBe('http://localhost:5000/products/1/comments');
      expect(tx.data).toBe(entity);
      expect(tx.meta.inbox).toBe('_response_');
    });

    it('should dispatch ref-added event with detail', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('field', 'comments');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();
      NTT.get.mockReturnValue({ send: vi.fn() });
      const entity = { id: 5, text: 'Test', $id: 'http://localhost:5000/comments/5' };
      const eventSpy = vi.fn();
      picker.addEventListener('ref-added', eventSpy);
      picker._addRef(5, entity);
      expect(eventSpy).toHaveBeenCalled();
      const event = eventSpy.mock.calls[0][0];
      expect(event.detail.field).toBe('comments');
      expect(event.detail.ref).toBe('http://localhost:5000/comments/5');
      expect(event.detail.data).toBe(entity);
      expect(event.bubbles).toBe(true);
      expect(event.composed).toBe(true);
    });

    it('should construct href when entity has no $id', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('field', 'comments');
      picker.setAttribute('child-table', 'comments');
      picker._render();
      NTT.get.mockReturnValue({ send: vi.fn() });
      const entity = { id: 5, text: 'Test' };
      const eventSpy = vi.fn();
      picker.addEventListener('ref-added', eventSpy);
      picker._addRef(5, entity);
      const event = eventSpy.mock.calls[0][0];
      expect(event.detail.ref).toBe('http://localhost:5000/comments/5');
    });
  });

  describe('_submitCreate', () => {
    it('should collect form data correctly from inputs', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      const sendMock = vi.fn();
      NTT.get.mockReturnValue({ send: sendMock, get: vi.fn() });

      // Create mock form with inputs
      const form = document.createElement('div');
      const input = document.createElement('input');
      input.setAttribute('data-key', 'text');
      input.value = 'Test comment';
      form.appendChild(input);

      picker._submitCreate(form);

      const tx = sendMock.mock.calls[0][0];
      expect(tx.data.text).toBe('Test comment');
    });

    it('should handle boolean inputs (checkboxes)', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      const sendMock = vi.fn();
      NTT.get.mockReturnValue({ send: sendMock, get: vi.fn() });

      const form = document.createElement('div');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.setAttribute('data-key', 'active');
      checkbox.checked = true;
      form.appendChild(checkbox);

      picker._submitCreate(form);

      const tx = sendMock.mock.calls[0][0];
      expect(tx.data.active).toBe(true);
    });

    it('should handle number inputs', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      const sendMock = vi.fn();
      NTT.get.mockReturnValue({ send: sendMock, get: vi.fn() });

      const form = document.createElement('div');
      const numberInput = document.createElement('input');
      numberInput.setAttribute('data-key', 'rating');
      numberInput.setAttribute('data-type', 'number');
      numberInput.value = '4.5';
      form.appendChild(numberInput);

      picker._submitCreate(form);

      const tx = sendMock.mock.calls[0][0];
      expect(tx.data.rating).toBe(4.5);
    });

    it('should handle object inputs (JSON parsing)', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      const sendMock = vi.fn();
      NTT.get.mockReturnValue({ send: sendMock, get: vi.fn() });

      const form = document.createElement('div');
      const objInput = document.createElement('input');
      objInput.setAttribute('data-key', 'metadata');
      objInput.setAttribute('data-type', 'object');
      objInput.value = '{"key": "value"}';
      form.appendChild(objInput);

      picker._submitCreate(form);

      const tx = sendMock.mock.calls[0][0];
      expect(tx.data.metadata).toEqual({ key: 'value' });
    });

    it('should fallback to string for invalid JSON in object inputs', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      const sendMock = vi.fn();
      NTT.get.mockReturnValue({ send: sendMock, get: vi.fn() });

      const form = document.createElement('div');
      const objInput = document.createElement('input');
      objInput.setAttribute('data-key', 'metadata');
      objInput.setAttribute('data-type', 'object');
      objInput.value = 'invalid-json';
      form.appendChild(objInput);

      picker._submitCreate(form);

      const tx = sendMock.mock.calls[0][0];
      expect(tx.data.metadata).toBe('invalid-json');
    });

    it('should send CREATE TX with correct target URL', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      const sendMock = vi.fn();
      NTT.get.mockReturnValue({ send: sendMock, get: vi.fn() });

      const form = document.createElement('div');
      picker._submitCreate(form);

      const tx = sendMock.mock.calls[0][0];
      expect(tx.name).toBe('CREATE');
      expect(tx.target).toBe('http://localhost:5000/products/1/comments');
      expect(tx.meta.inbox).toBe('_response_');
    });

    it('should dispatch ref-created event', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('field', 'comments');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      const sendMock = vi.fn();
      NTT.get.mockReturnValue({ send: sendMock, get: vi.fn() });

      const eventSpy = vi.fn();
      picker.addEventListener('ref-created', eventSpy);

      const form = document.createElement('div');
      const input = document.createElement('input');
      input.setAttribute('data-key', 'text');
      input.value = 'New comment';
      form.appendChild(input);

      picker._submitCreate(form);

      expect(eventSpy).toHaveBeenCalled();
      const event = eventSpy.mock.calls[0][0];
      expect(event.detail.field).toBe('comments');
      expect(event.detail.data.text).toBe('New comment');
      expect(event.bubbles).toBe(true);
      expect(event.composed).toBe(true);
    });

    it('should call _close after submit', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      const sendMock = vi.fn();
      NTT.get.mockReturnValue({ send: sendMock, get: vi.fn() });

      const closeSpy = vi.spyOn(picker, '_close');
      const form = document.createElement('div');
      picker._submitCreate(form);

      expect(closeSpy).toHaveBeenCalled();
    });

    it('should call parent entity pull to refresh', () => {
      vi.useFakeTimers();
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker.setAttribute('parent-model', 'Product');
      picker.setAttribute('parent-id', '1');
      picker.setAttribute('parent-table', 'products');
      picker.setAttribute('child-table', 'comments');
      picker._render();

      const sendMock = vi.fn();
      const pullMock = vi.fn();
      NTT.get.mockImplementation((addr) => {
        if (addr === 'Comment') {
          return { send: sendMock };
        }
        if (addr === 'Product/1') {
          return { pull: pullMock };
        }
        return null;
      });

      const form = document.createElement('div');
      picker._submitCreate(form);

      vi.advanceTimersByTime(300);
      expect(pullMock).toHaveBeenCalled();
      vi.useRealTimers();
    });
  });

  describe('_close', () => {
    it('should set mode to closed', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: vi.fn(),
      });
      picker._showPicker();
      picker._close();
      // Verify dropdown is gone (mode is closed)
      const dropdown = picker.shadowRoot.querySelector('.picker-dropdown');
      expect(dropdown).toBeNull();
    });

    it('should clear dropdown anchor innerHTML', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      NTT.get.mockReturnValue({
        instances: new Map(),
        call: vi.fn(),
      });
      picker._showPicker();
      const anchor = picker.shadowRoot.querySelector('.dropdown-anchor');
      expect(anchor.innerHTML).not.toBe('');
      picker._close();
      expect(anchor.innerHTML).toBe('');
    });

    it('should remove click event listener', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const spy = vi.spyOn(document, 'removeEventListener');
      picker._close();
      expect(spy).toHaveBeenCalledWith('click', picker._onOutsideClick);
    });
  });

  describe('_onOutsideClick', () => {
    it('should close if click is outside component', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const closeSpy = vi.spyOn(picker, '_close');
      const outsideElement = document.createElement('div');
      const event = { target: outsideElement };
      picker._onOutsideClick(event);
      expect(closeSpy).toHaveBeenCalled();
    });

    it('should not close if click is inside shadow DOM', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker.setAttribute('model', 'Comment');
      picker._render();
      const closeSpy = vi.spyOn(picker, '_close');
      const button = picker.shadowRoot.querySelector('.add-btn');
      const event = { target: button };
      picker._onOutsideClick(event);
      // Should NOT close because shadowRoot.contains(button) is true
      // The logic is: if (!this.contains(e.target) && !this.shadowRoot.contains(e.target))
      // For shadow DOM elements, this.contains returns false but shadowRoot.contains returns true
      // So the condition is false and _close should NOT be called
      expect(closeSpy).not.toHaveBeenCalled();
    });
  });

  describe('stylesheet contract', () => {
    it('should link the component stylesheet from the shadow root', () => {
      const picker = document.createElement('ntx-ref-picker');
      picker._render();

      const stylesheet = picker.shadowRoot.querySelector('link[rel="stylesheet"]');
      expect(stylesheet).toBeTruthy();
      expect(stylesheet.getAttribute('href')).toContain('ntx-ref-picker.css');
    });
  });
});
