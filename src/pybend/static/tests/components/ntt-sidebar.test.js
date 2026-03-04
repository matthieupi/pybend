/**
 * Test plan for ntt-sidebar.js
 * ==============================
 *
 * UNIT TESTS — behavior validation
 *   - test_custom_element_registration
 *   - test_constructor_creates_shadow_dom
 *   - test_constructor_creates_stylesheet_link
 *   - test_open_sets_open_attribute
 *   - test_close_removes_open_attribute
 *   - test_toggle_switches_open_state
 *   - test_toggle_from_closed_to_open
 *   - test_toggle_from_open_to_closed
 *
 * EDGE CASES — boundary conditions
 *   - test_models_attribute_empty_string
 *   - test_models_attribute_whitespace_only
 *   - test_models_attribute_with_extra_spaces
 *   - test_models_attribute_single_model
 *   - test_models_attribute_multiple_models
 *   - test_no_models_attribute_no_children
 *   - test_children_without_model_attribute_ignored
 *
 * ROUTE TEMPLATES — declarative child patterns
 *   - test_route_templates_from_children_with_model_attribute
 *   - test_route_templates_capture_non_skip_attributes
 *   - test_route_templates_skip_model_slot_class_style_id
 *   - test_route_templates_hide_children_on_connect
 *   - test_models_derived_from_children_when_no_models_attribute
 *   - test_models_attribute_overrides_children
 *
 * VIEW_TAGS STATIC — mapping
 *   - test_VIEW_TAGS_grid_maps_to_ntt_list
 *   - test_VIEW_TAGS_table_maps_to_ntt_table
 *
 * RENDER OUTPUT — DOM structure
 *   - test_render_creates_sidebar_container
 *   - test_render_creates_sidebar_nav
 *   - test_render_creates_model_sections
 *   - test_render_creates_model_avatars_with_gradients
 *   - test_render_creates_model_names
 *   - test_render_creates_model_count_elements
 *   - test_render_creates_chevron_icons
 *   - test_render_creates_close_button
 *   - test_render_creates_overlay
 *   - test_avatar_initial_is_uppercase_first_char
 *   - test_avatar_gradient_cycles_through_palette
 *
 * EVENT LISTENERS — interaction
 *   - test_sidebar_toggle_event_triggers_toggle
 *   - test_escape_key_closes_sidebar_when_open
 *   - test_escape_key_noop_when_closed
 *   - test_hashchange_closes_sidebar_when_open
 *   - test_close_button_click_closes_sidebar
 *   - test_overlay_click_closes_sidebar
 *
 * CLEANUP / RESOURCES
 *   - test_disconnect_removes_sidebar_toggle_listener
 *   - test_disconnect_removes_keydown_listener
 *   - test_disconnect_removes_hashchange_listener
 *   - test_disconnect_calls_unsub_callbacks
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock dependencies
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
         NAVIGATE: 'NAVIGATE', BACK: 'BACK', SELECT: 'SELECT' },
    DEFAULT_HEADERS: {}, TIMEOUT: 5000, RETRY_LIMIT: 3,
  }
}));
vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

// Mock NTT.attach to prevent actual schema fetching
const mockNTT = {
  attach: vi.fn((addr, callback) => {
    // Return a mock unsubscribe function
    return () => {};
  }),
  get: vi.fn(),
};
vi.mock('../../core/NTT.js', () => ({
  NTT: mockNTT
}));

// Import after mocks
await import('../../components/ntt-sidebar.js');

describe('ntt-sidebar.js (NTTSidebar)', () => {

  beforeEach(() => {
    mockNTT.attach.mockClear();
    mockNTT.get.mockClear();
    // Reset mock implementation
    mockNTT.attach.mockImplementation((addr, callback) => () => {});
  });

  describe('custom element registration', () => {
    it('should be registered as ntt-sidebar', () => {
      const Ctor = customElements.get('ntt-sidebar');
      expect(Ctor).toBeTruthy();
      expect(Ctor.name).toBe('NTTSidebar');
    });
  });

  describe('constructor', () => {
    it('should create shadow DOM', () => {
      const el = document.createElement('ntt-sidebar');
      expect(el.shadowRoot).toBeTruthy();
      expect(el.shadowRoot.mode).toBe('open');
    });

    it('should create stylesheet link in shadow DOM', () => {
      const el = document.createElement('ntt-sidebar');
      const link = el.shadowRoot.querySelector('link');
      expect(link).toBeTruthy();
      expect(link.getAttribute('rel')).toBe('stylesheet');
      expect(link.getAttribute('href')).toContain('ntt-sidebar.css');
    });
  });

  describe('open/close/toggle API', () => {
    it('should set open attribute when open() is called', () => {
      const el = document.createElement('ntt-sidebar');
      expect(el.hasAttribute('open')).toBe(false);
      el.open();
      expect(el.hasAttribute('open')).toBe(true);
    });

    it('should remove open attribute when close() is called', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('open', '');
      expect(el.hasAttribute('open')).toBe(true);
      el.close();
      expect(el.hasAttribute('open')).toBe(false);
    });

    it('should toggle from closed to open', () => {
      const el = document.createElement('ntt-sidebar');
      expect(el.hasAttribute('open')).toBe(false);
      el.toggle();
      expect(el.hasAttribute('open')).toBe(true);
    });

    it('should toggle from open to closed', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('open', '');
      expect(el.hasAttribute('open')).toBe(true);
      el.toggle();
      expect(el.hasAttribute('open')).toBe(false);
    });
  });

  describe('VIEW_TAGS static mapping', () => {
    it('should map grid to ntt-list', () => {
      const Ctor = customElements.get('ntt-sidebar');
      expect(Ctor.VIEW_TAGS.grid).toBe('ntt-list');
    });

    it('should map table to ntt-table', () => {
      const Ctor = customElements.get('ntt-sidebar');
      expect(Ctor.VIEW_TAGS.table).toBe('ntt-table');
    });
  });

  describe('models attribute parsing (legacy)', () => {
    it('should parse comma-separated model names', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Grant,Source,AgentActor');
      document.body.appendChild(el);

      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('data-model="Grant"');
      expect(html).toContain('data-model="Source"');
      expect(html).toContain('data-model="AgentActor"');

      document.body.removeChild(el);
    });

    it('should handle single model', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('data-model="Product"');

      document.body.removeChild(el);
    });

    it('should handle empty string as no models', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', '');
      document.body.appendChild(el);

      const sections = el.shadowRoot.querySelectorAll('.model-section');
      expect(sections.length).toBe(0);

      document.body.removeChild(el);
    });

    it('should trim whitespace around model names', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', ' Grant , Source , AgentActor ');
      document.body.appendChild(el);

      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('data-model="Grant"');
      expect(html).toContain('data-model="Source"');
      expect(html).toContain('data-model="AgentActor"');

      document.body.removeChild(el);
    });

    it('should filter empty entries from whitespace-only segments', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Grant,,Source,  ,AgentActor');
      document.body.appendChild(el);

      const sections = el.shadowRoot.querySelectorAll('.model-section');
      expect(sections.length).toBe(3); // Not 5

      document.body.removeChild(el);
    });
  });

  describe('route templates from children', () => {
    it('should derive models from children with model attribute when no models attribute', () => {
      const el = document.createElement('ntt-sidebar');

      const child1 = document.createElement('ntt-table');
      child1.setAttribute('model', 'Grant');
      el.appendChild(child1);

      const child2 = document.createElement('ntt-list');
      child2.setAttribute('model', 'Source');
      el.appendChild(child2);

      document.body.appendChild(el);

      const sections = el.shadowRoot.querySelectorAll('.model-section');
      expect(sections.length).toBe(2);
      expect(el.shadowRoot.innerHTML).toContain('data-model="Grant"');
      expect(el.shadowRoot.innerHTML).toContain('data-model="Source"');

      document.body.removeChild(el);
    });

    it('should hide template children on connect', () => {
      const el = document.createElement('ntt-sidebar');

      const child1 = document.createElement('ntt-table');
      child1.setAttribute('model', 'Grant');
      el.appendChild(child1);

      const child2 = document.createElement('ntt-list');
      child2.setAttribute('model', 'Source');
      el.appendChild(child2);

      expect(child1.hidden).toBe(false);
      expect(child2.hidden).toBe(false);

      document.body.appendChild(el);

      expect(child1.hidden).toBe(true);
      expect(child2.hidden).toBe(true);

      document.body.removeChild(el);
    });

    it('should capture non-skip attributes from template children', () => {
      const el = document.createElement('ntt-sidebar');

      const child = document.createElement('ntt-table');
      child.setAttribute('model', 'Grant');
      child.setAttribute('allow-create', '');
      child.setAttribute('display', 'lg');
      child.setAttribute('custom-attr', 'value');
      // Skip attributes that should NOT be captured
      child.setAttribute('class', 'test-class');
      child.setAttribute('style', 'color: red;');
      child.setAttribute('id', 'test-id');
      child.setAttribute('slot', 'test-slot');

      el.appendChild(child);
      document.body.appendChild(el);

      // We can't directly access #routeTemplates, but we can verify the child was processed
      expect(child.hidden).toBe(true);

      document.body.removeChild(el);
    });

    it('should ignore children without model attribute', () => {
      const el = document.createElement('ntt-sidebar');

      const child1 = document.createElement('ntt-table');
      child1.setAttribute('model', 'Grant');
      el.appendChild(child1);

      const child2 = document.createElement('div');
      // No model attribute
      el.appendChild(child2);

      document.body.appendChild(el);

      const sections = el.shadowRoot.querySelectorAll('.model-section');
      expect(sections.length).toBe(1);
      expect(child1.hidden).toBe(true);
      expect(child2.hidden).toBe(false); // Not hidden

      document.body.removeChild(el);
    });

    it('should use models attribute even when children are present', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product,User');

      const child = document.createElement('ntt-table');
      child.setAttribute('model', 'Grant');
      el.appendChild(child);

      document.body.appendChild(el);

      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('data-model="Product"');
      expect(html).toContain('data-model="User"');
      // Grant should still be hidden but not in the model list
      expect(child.hidden).toBe(true);

      document.body.removeChild(el);
    });
  });

  describe('render output', () => {
    it('should create sidebar-container', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const container = el.shadowRoot.querySelector('.sidebar-container');
      expect(container).toBeTruthy();

      document.body.removeChild(el);
    });

    it('should create sidebar nav element', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const sidebar = el.shadowRoot.querySelector('.sidebar');
      expect(sidebar).toBeTruthy();
      expect(sidebar.tagName.toLowerCase()).toBe('nav');

      document.body.removeChild(el);
    });

    it('should create sidebar-overlay', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const overlay = el.shadowRoot.querySelector('.sidebar-overlay');
      expect(overlay).toBeTruthy();

      document.body.removeChild(el);
    });

    it('should create sidebar-close button', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const closeBtn = el.shadowRoot.querySelector('.sidebar-close');
      expect(closeBtn).toBeTruthy();
      expect(closeBtn.tagName.toLowerCase()).toBe('button');
      expect(closeBtn.getAttribute('aria-label')).toBe('Close sidebar');

      document.body.removeChild(el);
    });

    it('should create model sections with data-model attribute', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product,User');
      document.body.appendChild(el);

      const sections = el.shadowRoot.querySelectorAll('.model-section');
      expect(sections.length).toBe(2);
      expect(sections[0].getAttribute('data-model')).toBe('Product');
      expect(sections[1].getAttribute('data-model')).toBe('User');

      document.body.removeChild(el);
    });

    it('should create model-header button for each section', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product,User');
      document.body.appendChild(el);

      const headers = el.shadowRoot.querySelectorAll('.model-header');
      expect(headers.length).toBe(2);
      expect(headers[0].tagName.toLowerCase()).toBe('button');
      expect(headers[1].tagName.toLowerCase()).toBe('button');

      document.body.removeChild(el);
    });

    it('should create model-avatar with gradient background', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const avatar = el.shadowRoot.querySelector('.model-avatar');
      expect(avatar).toBeTruthy();
      expect(avatar.getAttribute('style')).toContain('background:');
      expect(avatar.getAttribute('style')).toContain('linear-gradient');

      document.body.removeChild(el);
    });

    it('should set avatar initial to uppercase first character', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'product,user');
      document.body.appendChild(el);

      const avatars = el.shadowRoot.querySelectorAll('.model-avatar');
      expect(avatars[0].textContent).toBe('P');
      expect(avatars[1].textContent).toBe('U');

      document.body.removeChild(el);
    });

    it('should cycle through avatar gradient palette', () => {
      const el = document.createElement('ntt-sidebar');
      // More models than gradients (8 gradients in palette)
      el.setAttribute('models', 'M1,M2,M3,M4,M5,M6,M7,M8,M9');
      document.body.appendChild(el);

      const avatars = el.shadowRoot.querySelectorAll('.model-avatar');
      expect(avatars.length).toBe(9);

      // First and 9th should have same gradient (0 % 8 === 8 % 8)
      const style1 = avatars[0].getAttribute('style');
      const style9 = avatars[8].getAttribute('style');
      expect(style1).toBe(style9);

      document.body.removeChild(el);
    });

    it('should create model-name span', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const name = el.shadowRoot.querySelector('.model-name');
      expect(name).toBeTruthy();
      expect(name.textContent).toBe('Product');

      document.body.removeChild(el);
    });

    it('should create empty model-count span', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const count = el.shadowRoot.querySelector('.model-count');
      expect(count).toBeTruthy();
      expect(count.textContent).toBe(''); // Empty initially

      document.body.removeChild(el);
    });

    it('should create model-chevron with SVG', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const chevron = el.shadowRoot.querySelector('.model-chevron');
      expect(chevron).toBeTruthy();
      expect(chevron.innerHTML).toContain('<svg');
      expect(chevron.innerHTML).toContain('polyline');

      document.body.removeChild(el);
    });

    it('should create model-records container', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      const records = el.shadowRoot.querySelector('.model-records');
      expect(records).toBeTruthy();
      expect(records.childElementCount).toBe(0); // Empty initially

      document.body.removeChild(el);
    });
  });

  describe('event listeners on connect', () => {
    it('should toggle sidebar on sidebar-toggle event', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      expect(el.hasAttribute('open')).toBe(false);

      const event = new CustomEvent('sidebar-toggle');
      document.dispatchEvent(event);

      expect(el.hasAttribute('open')).toBe(true);

      document.body.removeChild(el);
    });

    it('should close sidebar on Escape key when open', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      el.setAttribute('open', '');
      document.body.appendChild(el);

      expect(el.hasAttribute('open')).toBe(true);

      const event = new KeyboardEvent('keydown', { key: 'Escape' });
      document.dispatchEvent(event);

      expect(el.hasAttribute('open')).toBe(false);

      document.body.removeChild(el);
    });

    it('should not close sidebar on Escape key when already closed', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      expect(el.hasAttribute('open')).toBe(false);

      const event = new KeyboardEvent('keydown', { key: 'Escape' });
      document.dispatchEvent(event);

      expect(el.hasAttribute('open')).toBe(false);

      document.body.removeChild(el);
    });

    it('should ignore non-Escape keys', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      el.setAttribute('open', '');
      document.body.appendChild(el);

      expect(el.hasAttribute('open')).toBe(true);

      const event = new KeyboardEvent('keydown', { key: 'Enter' });
      document.dispatchEvent(event);

      expect(el.hasAttribute('open')).toBe(true);

      document.body.removeChild(el);
    });

    it('should close sidebar on hashchange when open', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      el.setAttribute('open', '');
      document.body.appendChild(el);

      expect(el.hasAttribute('open')).toBe(true);

      const event = new Event('hashchange');
      window.dispatchEvent(event);

      expect(el.hasAttribute('open')).toBe(false);

      document.body.removeChild(el);
    });

    it('should not close sidebar on hashchange when already closed', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      expect(el.hasAttribute('open')).toBe(false);

      const event = new Event('hashchange');
      window.dispatchEvent(event);

      expect(el.hasAttribute('open')).toBe(false);

      document.body.removeChild(el);
    });

    it('should close sidebar when overlay is clicked', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      el.setAttribute('open', '');
      document.body.appendChild(el);

      expect(el.hasAttribute('open')).toBe(true);

      const overlay = el.shadowRoot.querySelector('.sidebar-overlay');
      overlay.click();

      expect(el.hasAttribute('open')).toBe(false);

      document.body.removeChild(el);
    });

    it('should close sidebar when close button is clicked', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      el.setAttribute('open', '');
      document.body.appendChild(el);

      expect(el.hasAttribute('open')).toBe(true);

      const closeBtn = el.shadowRoot.querySelector('.sidebar-close');
      closeBtn.click();

      expect(el.hasAttribute('open')).toBe(false);

      document.body.removeChild(el);
    });
  });

  describe('cleanup on disconnect', () => {
    it('should remove sidebar-toggle listener', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      document.body.appendChild(el);

      // Toggle works when connected
      const event = new CustomEvent('sidebar-toggle');
      document.dispatchEvent(event);
      expect(el.hasAttribute('open')).toBe(true);

      // Disconnect
      document.body.removeChild(el);

      // Reset state
      el.removeAttribute('open');

      // Toggle should not work after disconnect
      document.dispatchEvent(event);
      expect(el.hasAttribute('open')).toBe(false);
    });

    it('should remove keydown listener', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      el.setAttribute('open', '');
      document.body.appendChild(el);

      // Escape works when connected
      const event = new KeyboardEvent('keydown', { key: 'Escape' });
      document.dispatchEvent(event);
      expect(el.hasAttribute('open')).toBe(false);

      // Disconnect
      document.body.removeChild(el);

      // Reset state
      el.setAttribute('open', '');

      // Escape should not work after disconnect
      document.dispatchEvent(event);
      expect(el.hasAttribute('open')).toBe(true);
    });

    it('should remove hashchange listener', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product');
      el.setAttribute('open', '');
      document.body.appendChild(el);

      // Hashchange works when connected
      const event = new Event('hashchange');
      window.dispatchEvent(event);
      expect(el.hasAttribute('open')).toBe(false);

      // Disconnect
      document.body.removeChild(el);

      // Reset state
      el.setAttribute('open', '');

      // Hashchange should not work after disconnect
      window.dispatchEvent(event);
      expect(el.hasAttribute('open')).toBe(true);
    });

    it('should call all unsub callbacks', () => {
      const unsubMock1 = vi.fn();
      const unsubMock2 = vi.fn();

      // The unsub callback is returned by DC.observe(), which is called inside
      // the NTT.attach callback. We need to mock the DC.observe call.
      const mockDC = {
        observe: vi.fn(),
        _schema: { __name__: 'TestModel' },
      };

      mockNTT.attach.mockImplementation((addr, callback) => {
        if (addr === 'Product') {
          mockDC.observe.mockReturnValueOnce(unsubMock1);
        } else if (addr === 'User') {
          mockDC.observe.mockReturnValueOnce(unsubMock2);
        }
        // Invoke the callback to simulate schema ready
        callback(mockDC);
        return () => {}; // Return a noop unsub for NTT.attach itself
      });

      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product,User');
      document.body.appendChild(el);

      expect(unsubMock1).not.toHaveBeenCalled();
      expect(unsubMock2).not.toHaveBeenCalled();

      document.body.removeChild(el);

      expect(unsubMock1).toHaveBeenCalledTimes(1);
      expect(unsubMock2).toHaveBeenCalledTimes(1);
    });
  });

  describe('NTT.attach bootstrap', () => {
    it('should call NTT.attach for each model', () => {
      const el = document.createElement('ntt-sidebar');
      el.setAttribute('models', 'Product,User,Grant');
      document.body.appendChild(el);

      expect(mockNTT.attach).toHaveBeenCalledTimes(3);
      expect(mockNTT.attach).toHaveBeenCalledWith('Product', expect.any(Function));
      expect(mockNTT.attach).toHaveBeenCalledWith('User', expect.any(Function));
      expect(mockNTT.attach).toHaveBeenCalledWith('Grant', expect.any(Function));

      document.body.removeChild(el);
    });

    it('should call NTT.attach for models derived from children', () => {
      const el = document.createElement('ntt-sidebar');

      const child1 = document.createElement('ntt-table');
      child1.setAttribute('model', 'Grant');
      el.appendChild(child1);

      const child2 = document.createElement('ntt-list');
      child2.setAttribute('model', 'Source');
      el.appendChild(child2);

      document.body.appendChild(el);

      expect(mockNTT.attach).toHaveBeenCalledTimes(2);
      expect(mockNTT.attach).toHaveBeenCalledWith('Grant', expect.any(Function));
      expect(mockNTT.attach).toHaveBeenCalledWith('Source', expect.any(Function));

      document.body.removeChild(el);
    });

    it('should not call NTT.attach when no models', () => {
      const el = document.createElement('ntt-sidebar');
      document.body.appendChild(el);

      expect(mockNTT.attach).not.toHaveBeenCalled();

      document.body.removeChild(el);
    });
  });
});
