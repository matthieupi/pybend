import { describe, it, expect, vi, beforeEach } from 'vitest';

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

import { NTTMethod } from '../../components/ntx-method.js';

describe('ntx-method.js (NTTMethod)', () => {

  describe('static observedAttributes', () => {
    it('should return attribute list', () => {
      const attrs = NTTMethod.observedAttributes;
      expect(attrs).toContain('model');
      expect(attrs).toContain('method');
      expect(attrs).toContain('uuid');
      expect(attrs).toContain('mode');
      expect(attrs).toContain('layout');
      expect(attrs).toContain('icon');
      expect(attrs).toContain('count-field');
    });

    it('should include label attribute', () => {
      expect(NTTMethod.observedAttributes).toContain('label');
    });

    it('should include forward attribute', () => {
      expect(NTTMethod.observedAttributes).toContain('forward');
    });

    it('should include button-label attribute', () => {
      expect(NTTMethod.observedAttributes).toContain('button-label');
    });

    it('should include widget attribute', () => {
      expect(NTTMethod.observedAttributes).toContain('widget');
    });

    it('should include placeholder attribute', () => {
      expect(NTTMethod.observedAttributes).toContain('placeholder');
    });
  });

  describe('constructor', () => {
    it('should be registered as ntx-method', () => {
      expect(customElements.get('ntx-method')).toBe(NTTMethod);
    });

    it('should create shadow DOM', () => {
      const method = new NTTMethod();
      expect(method.shadowRoot).toBeTruthy();
    });

    it('should initialize value as empty object', () => {
      const method = new NTTMethod();
      expect(method.value).toEqual({});
    });

    it('should initialize schema, proto, ntt, response as null', () => {
      const method = new NTTMethod();
      expect(method.schema).toBeNull();
      expect(method.proto).toBeNull();
      expect(method.ntt).toBeNull();
      expect(method.response).toBeNull();
    });
  });

  describe('handleInput(e)', () => {
    it('should update value from simple input', () => {
      const method = new NTTMethod();
      method.mode = 'manual';
      const e = { target: { name: 'text', type: 'text', value: 'hello' } };
      method.handleInput(e);
      expect(method.value.text).toBe('hello');
    });

    it('should handle nested params (dot notation)', () => {
      const method = new NTTMethod();
      method.mode = 'manual';
      const e = { target: { name: 'comment.text', type: 'text', value: 'nested' } };
      method.handleInput(e);
      expect(method.value.comment.text).toBe('nested');
    });

    it('should create nested object if it does not exist', () => {
      const method = new NTTMethod();
      method.mode = 'manual';
      expect(method.value.comment).toBeUndefined();
      method.handleInput({ target: { name: 'comment.body', type: 'text', value: 'test' } });
      expect(method.value.comment).toEqual({ body: 'test' });
    });

    it('should handle checkbox input', () => {
      const method = new NTTMethod();
      method.mode = 'manual';
      const e = { target: { name: 'active', type: 'checkbox', checked: true } };
      method.handleInput(e);
      expect(method.value.active).toBe(true);
    });

    it('should handle unchecked checkbox', () => {
      const method = new NTTMethod();
      method.mode = 'manual';
      method.handleInput({ target: { name: 'active', type: 'checkbox', checked: false } });
      expect(method.value.active).toBe(false);
    });

    it('should auto-call if mode=auto', () => {
      const method = new NTTMethod();
      method.mode = 'auto';
      method.callMethod = vi.fn();
      const e = { target: { name: 'x', type: 'text', value: 'y' } };
      method.handleInput(e);
      expect(method.callMethod).toHaveBeenCalled();
    });

    it('should not auto-call if mode=manual', () => {
      const method = new NTTMethod();
      method.mode = 'manual';
      method.callMethod = vi.fn();
      method.handleInput({ target: { name: 'x', type: 'text', value: 'y' } });
      expect(method.callMethod).not.toHaveBeenCalled();
    });
  });

  describe('callMethod()', () => {
    it('should no-op when no ntt or proto', () => {
      const method = new NTTMethod();
      method.proto = null;
      method.ntt = null;
      method.schema = { scope: 'instancemethod', parameters: {} };
      // Should not throw
      expect(() => method.callMethod()).not.toThrow();
    });

    it('should call instance method via ntt.call when scope=instancemethod', () => {
      const method = new NTTMethod();
      const callMock = vi.fn();
      method.ntt = { call: callMock };
      method.proto = { call: vi.fn() };
      method.schema = { scope: 'instancemethod', parameters: {} };
      method.method = 'like';
      method.value = {};
      method.layout = 'fieldset';
      method.shadowRoot.innerHTML = '<div></div>';
      method.callMethod();
      expect(callMock).toHaveBeenCalledWith('like', {}, { inbox: '_response_' });
    });

    it('should call class method via proto.call for non-instance methods', () => {
      const method = new NTTMethod();
      const callMock = vi.fn();
      method.ntt = null;
      method.proto = { call: callMock };
      method.schema = { scope: 'classmethod', parameters: {} };
      method.method = 'search';
      method.value = { q: 'test' };
      method.layout = 'fieldset';
      method.shadowRoot.innerHTML = '<div></div>';
      method.callMethod();
      expect(callMock).toHaveBeenCalledWith('search', { q: 'test' }, { inbox: '_response_' });
    });

    it('should set response to { status: "sent" } after calling', () => {
      const method = new NTTMethod();
      method.ntt = { call: vi.fn() };
      method.schema = { scope: 'instancemethod', parameters: {} };
      method.method = 'like';
      method.value = {};
      method.layout = 'button'; // button layout avoids #postCall re-render issues
      method.shadowRoot.innerHTML = '<button class="method-btn"></button>';
      method.callMethod();
      expect(method.response).toEqual({ status: 'sent' });
    });

    it('should copy value payload (not pass reference)', () => {
      const method = new NTTMethod();
      const callMock = vi.fn();
      method.proto = { call: callMock };
      method.schema = { scope: 'classmethod', parameters: {} };
      method.method = 'test';
      method.value = { a: 1 };
      method.layout = 'fieldset';
      method.shadowRoot.innerHTML = '<div></div>';
      method.callMethod();
      const payload = callMock.mock.calls[0][1];
      // Payload should be a copy, not the same reference
      expect(payload).toEqual({ a: 1 });
      expect(payload).not.toBe(method.value);
    });
  });

  describe('render()', () => {
    it('should dispatch to renderInline for inline layout', () => {
      const method = new NTTMethod();
      method.layout = 'inline';
      method.schema = { parameters: {} };
      method.proto = { schema: { $defs: {} } };
      const spy = vi.spyOn(method, 'renderInline');
      method.render();
      expect(spy).toHaveBeenCalled();
    });

    it('should dispatch to renderButton for button layout', () => {
      const method = new NTTMethod();
      method.layout = 'button';
      method.schema = { parameters: {} };
      method.iconName = 'heart';
      method.countField = '';
      method.label = 'Like';
      const spy = vi.spyOn(method, 'renderButton');
      method.render();
      expect(spy).toHaveBeenCalled();
    });

    it('should dispatch to renderFieldset for fieldset layout', () => {
      const method = new NTTMethod();
      method.layout = 'fieldset';
      method.schema = { parameters: {} };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Comment';
      method.mode = 'manual';
      method.buttonLabel = 'Submit';
      const spy = vi.spyOn(method, 'renderFieldset');
      method.render();
      expect(spy).toHaveBeenCalled();
    });

    it('should default to renderFieldset for unknown layout', () => {
      const method = new NTTMethod();
      method.layout = 'unknown';
      method.schema = { parameters: {} };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Test';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      const spy = vi.spyOn(method, 'renderFieldset');
      method.render();
      expect(spy).toHaveBeenCalled();
    });
  });

  describe('renderButton()', () => {
    it('should render icon and count', () => {
      const method = new NTTMethod();
      method.iconName = 'heart';
      method.countField = 'likes';
      method.label = 'Like';
      method.ntt = { value: { likes: [1, 2, 3] } };
      method.renderButton();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('method-btn');
      expect(html).toContain('3'); // count
    });

    it('should handle missing count field', () => {
      const method = new NTTMethod();
      method.iconName = 'star';
      method.countField = '';
      method.label = 'Star';
      method.renderButton();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('method-btn');
    });

    it('should handle populated wrapper for count ({data: [...], meta: {total}})', () => {
      const method = new NTTMethod();
      method.iconName = 'heart';
      method.countField = 'likes';
      method.label = 'Like';
      method.ntt = { value: { likes: { data: [1, 2], meta: { total: 10 } } } };
      method.renderButton();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('10');
    });

    it('should fallback to data.length when meta.total missing in populated wrapper', () => {
      const method = new NTTMethod();
      method.iconName = 'heart';
      method.countField = 'likes';
      method.label = 'Like';
      method.ntt = { value: { likes: { data: [1, 2, 3], meta: {} } } };
      method.renderButton();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('3');
    });

    it('should use default icon when icon name not recognized', () => {
      const method = new NTTMethod();
      method.iconName = 'unknown_icon';
      method.countField = '';
      method.label = 'Test';
      method.renderButton();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('method-btn-icon');
    });

    it('should use heart icon for heart name', () => {
      const method = new NTTMethod();
      method.iconName = 'heart';
      method.countField = '';
      method.label = 'Like';
      method.renderButton();
      const html = method.shadowRoot.innerHTML;
      // heart SVG has a specific path
      expect(html).toContain('20.84 4.61');
    });

    it('should use star icon for star name', () => {
      const method = new NTTMethod();
      method.iconName = 'star';
      method.countField = '';
      method.label = 'Star';
      method.renderButton();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('polygon');
    });

    it('should use reply icon for reply name', () => {
      const method = new NTTMethod();
      method.iconName = 'reply';
      method.countField = '';
      method.label = 'Reply';
      method.renderButton();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('polyline');
    });

    it('should show 0 count when countField value is not an array or object', () => {
      const method = new NTTMethod();
      method.iconName = 'heart';
      method.countField = 'likes';
      method.label = 'Like';
      method.ntt = { value: { likes: 'not-an-array' } };
      method.renderButton();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('0');
    });

    it('should bind click handler to button', () => {
      const method = new NTTMethod();
      method.iconName = 'heart';
      method.countField = '';
      method.label = 'Like';
      method.callMethod = vi.fn();
      method.renderButton();
      const btn = method.shadowRoot.querySelector('.method-btn');
      btn.click();
      expect(method.callMethod).toHaveBeenCalled();
    });
  });

  describe('renderFieldset()', () => {
    it('should render fieldset with legend', () => {
      const method = new NTTMethod();
      method.schema = { parameters: {} };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Comment';
      method.mode = 'manual';
      method.buttonLabel = 'Submit';
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('<fieldset');
      expect(html).toContain('<legend>Comment</legend>');
    });

    it('should render submit button in manual mode', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { text: { type: 'string', title: 'Text' } } };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Comment';
      method.mode = 'manual';
      method.buttonLabel = 'Submit';
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('<button type="submit">Submit</button>');
    });

    it('should not render submit button in auto mode', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { text: { type: 'string', title: 'Text' } } };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Search';
      method.mode = 'auto';
      method.buttonLabel = 'Run';
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).not.toContain('<button type="submit">');
    });

    it('should render inputs for string parameters', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { name: { type: 'string', title: 'Name' } } };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Test';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      method.value = {};
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('<label>Name</label>');
      expect(html).toContain('name="name"');
      // renderFieldset uses the raw schema type directly (e.g. type="string")
      expect(html).toContain('type="string"');
    });

    it('should render number input for number parameters', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { count: { type: 'number', title: 'Count' } } };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Test';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      method.value = {};
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('type="number"');
    });

    it('should render selfref parameter as number input with placeholder', () => {
      const method = new NTTMethod();
      method.schema = {
        parameters: { parent_id: { type: 'selfref', title: 'Parent' } }
      };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Test';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      method.value = {};
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('<label>Parent</label>');
      expect(html).toContain('name="parent_id"');
      expect(html).toContain('type="number"');
      expect(html).toContain('Parent ID (optional)');
    });

    it('should render $ref parameter with resolved fields from $defs', () => {
      const method = new NTTMethod();
      method.schema = {
        parameters: {
          comment: { type: '$ref', $ref: '#/$defs/Comment', title: 'Comment' }
        }
      };
      method.proto = {
        schema: {
          $defs: {
            Comment: {
              properties: {
                text: { type: 'string', title: 'Text' },
                rating: { type: 'number', title: 'Rating' },
              },
              required: ['text'],
            }
          }
        }
      };
      method.label = 'Add Comment';
      method.mode = 'manual';
      method.buttonLabel = 'Submit';
      method.value = {};
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      // Should render only required fields (text)
      expect(html).toContain('name="comment.text"');
      expect(html).toContain('<label>Text</label>');
      // Non-required field (rating) should not appear
      expect(html).not.toContain('name="comment.rating"');
    });

    it('should show "(unresolved)" for $ref with missing $defs entry', () => {
      const method = new NTTMethod();
      method.schema = {
        parameters: {
          item: { type: '$ref', $ref: '#/$defs/Missing', title: 'Item' }
        }
      };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Test';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      method.value = {};
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('(unresolved)');
    });

    it('should show response output when response exists', () => {
      const method = new NTTMethod();
      method.schema = { parameters: {} };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Test';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      method.response = { status: 'sent', data: 'result' };
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('class="output"');
      expect(html).toContain('"status": "sent"');
    });

    it('should not show response output when response is null', () => {
      const method = new NTTMethod();
      method.schema = { parameters: {} };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Test';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      method.response = null;
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).not.toContain('class="output"');
    });

    it('should use key as label fallback when title is missing', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { myParam: { type: 'string' } } };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Test';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      method.value = {};
      method.renderFieldset();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('<label>myParam</label>');
    });
  });

  describe('renderInline()', () => {
    it('should render inline container with form', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { q: { type: 'string', title: 'Query' } } };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Search';
      method.mode = 'manual';
      method.buttonLabel = 'Go';
      method.placeholderText = 'Search...';
      method.widgetOverride = '';
      method.value = {};
      method.renderInline();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('method-inline');
      expect(html).toContain('<form');
    });

    it('should render single simple param as input + button row', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { q: { type: 'string', title: 'Query' } } };
      method.proto = { schema: { $defs: {} } };
      method.buttonLabel = 'Go';
      method.placeholderText = 'Search...';
      method.widgetOverride = '';
      method.value = {};
      method.renderInline();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('method-inline-row');
      expect(html).toContain('placeholder="Search..."');
      expect(html).toContain('name="q"');
    });

    it('should render textarea when widgetOverride is textarea', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { text: { type: 'string', title: 'Text' } } };
      method.proto = { schema: { $defs: {} } };
      method.buttonLabel = 'Post';
      method.placeholderText = 'Write something...';
      method.widgetOverride = 'textarea';
      method.value = {};
      method.renderInline();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('<textarea');
      expect(html).toContain('placeholder="Write something..."');
    });

    it('should render $ref param with single required field as inline input', () => {
      const method = new NTTMethod();
      method.schema = {
        parameters: {
          comment: { type: '$ref', $ref: '#/$defs/Comment' }
        }
      };
      method.proto = {
        schema: {
          $defs: {
            Comment: {
              properties: {
                text: { type: 'string', title: 'Text' },
                optional_field: { type: 'string', title: 'Optional' },
              },
              required: ['text'],
            }
          }
        }
      };
      method.buttonLabel = 'Post';
      method.placeholderText = '';
      method.widgetOverride = '';
      method.value = {};
      method.renderInline();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('name="comment.text"');
      expect(html).toContain('method-inline-row');
    });

    it('should render $ref param with textarea widget override', () => {
      const method = new NTTMethod();
      method.schema = {
        parameters: {
          comment: { type: '$ref', $ref: '#/$defs/Comment' }
        }
      };
      method.proto = {
        schema: {
          $defs: {
            Comment: {
              properties: { text: { type: 'string', title: 'Text' } },
              required: ['text'],
            }
          }
        }
      };
      method.buttonLabel = 'Post';
      method.placeholderText = 'Write a comment...';
      method.widgetOverride = 'textarea';
      method.value = {};
      method.renderInline();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('<textarea');
      expect(html).toContain('name="comment.text"');
    });

    it('should render $ref param with multiple required fields as stacked inputs', () => {
      const method = new NTTMethod();
      method.schema = {
        parameters: {
          review: { type: '$ref', $ref: '#/$defs/Review' }
        }
      };
      method.proto = {
        schema: {
          $defs: {
            Review: {
              properties: {
                title: { type: 'string', title: 'Title' },
                body: { type: 'string', title: 'Body' },
              },
              required: ['title', 'body'],
            }
          }
        }
      };
      method.buttonLabel = 'Submit';
      method.placeholderText = '';
      method.widgetOverride = '';
      method.value = {};
      method.renderInline();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('name="review.title"');
      expect(html).toContain('name="review.body"');
      expect(html).toContain('placeholder="Title"');
      expect(html).toContain('placeholder="Body"');
      // Form content should be stacked inputs, not wrapped in an inline-row div
      const form = method.shadowRoot.querySelector('form');
      expect(form.querySelector('.method-inline-row')).toBeNull();
    });

    it('should render multiple params as stacked inputs', () => {
      const method = new NTTMethod();
      method.schema = {
        parameters: {
          name: { type: 'string', title: 'Name' },
          age: { type: 'number', title: 'Age' },
        }
      };
      method.proto = { schema: { $defs: {} } };
      method.buttonLabel = 'Submit';
      method.placeholderText = '';
      method.widgetOverride = '';
      method.value = {};
      method.renderInline();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('name="name"');
      expect(html).toContain('name="age"');
      expect(html).toContain('placeholder="Name"');
      expect(html).toContain('placeholder="Age"');
    });

    it('should show external submit button for textarea layout', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { text: { type: 'string' } } };
      method.proto = { schema: { $defs: {} } };
      method.buttonLabel = 'Post';
      method.placeholderText = '';
      method.widgetOverride = 'textarea';
      method.value = {};
      method.renderInline();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('class="actions"');
      expect(html).toContain('Post');
    });

    it('should show external submit button for multi-param layout', () => {
      const method = new NTTMethod();
      method.schema = {
        parameters: {
          a: { type: 'string', title: 'A' },
          b: { type: 'string', title: 'B' },
        }
      };
      method.proto = { schema: { $defs: {} } };
      method.buttonLabel = 'Go';
      method.placeholderText = '';
      method.widgetOverride = '';
      method.value = {};
      method.renderInline();
      const html = method.shadowRoot.innerHTML;
      expect(html).toContain('class="actions"');
    });
  });

  describe('#postCall (via callMethod)', () => {
    it('should clear value and inputs for inline layout after call', () => {
      const method = new NTTMethod();
      method.ntt = { call: vi.fn() };
      method.schema = { scope: 'instancemethod', parameters: { q: { type: 'string' } } };
      method.method = 'search';
      method.layout = 'inline';
      method.proto = { schema: { $defs: {} } };
      method.placeholderText = '';
      method.widgetOverride = '';
      method.buttonLabel = 'Go';
      method.mode = 'manual';
      method.value = { q: 'test' };
      // Render first to create the DOM
      method.renderInline();
      const input = method.shadowRoot.querySelector('input');
      if (input) input.value = 'test';

      method.callMethod();
      // After postCall, value should be reset
      expect(method.value).toEqual({});
      expect(method.response).toBeNull();
    });

    it('should re-render for fieldset layout after call', () => {
      const method = new NTTMethod();
      method.ntt = { call: vi.fn() };
      method.schema = { scope: 'instancemethod', parameters: {} };
      method.method = 'like';
      method.layout = 'fieldset';
      method.proto = { schema: { $defs: {} } };
      method.label = 'Like';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      method.value = {};
      method.renderFieldset();
      const spy = vi.spyOn(method, 'render');
      method.callMethod();
      expect(spy).toHaveBeenCalled();
    });
  });

  describe('form submission', () => {
    it('should call callMethod on form submit in fieldset layout', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { q: { type: 'string' } } };
      method.proto = { schema: { $defs: {} } };
      method.label = 'Test';
      method.mode = 'manual';
      method.buttonLabel = 'Run';
      method.value = {};
      method.callMethod = vi.fn();
      method.renderFieldset();
      const form = method.shadowRoot.querySelector('form');
      form.dispatchEvent(new Event('submit', { cancelable: true }));
      expect(method.callMethod).toHaveBeenCalled();
    });

    it('should call callMethod on form submit in inline layout', () => {
      const method = new NTTMethod();
      method.schema = { parameters: { q: { type: 'string' } } };
      method.proto = { schema: { $defs: {} } };
      method.buttonLabel = 'Go';
      method.placeholderText = '';
      method.widgetOverride = '';
      method.value = {};
      method.callMethod = vi.fn();
      method.renderInline();
      const form = method.shadowRoot.querySelector('form');
      form.dispatchEvent(new Event('submit', { cancelable: true }));
      expect(method.callMethod).toHaveBeenCalled();
    });
  });

  describe('static styles', () => {
    it('should have baseStyles', () => {
      expect(NTTMethod.baseStyles).toBeTruthy();
      expect(typeof NTTMethod.baseStyles).toBe('string');
    });

    it('should have inlineStyles', () => {
      expect(NTTMethod.inlineStyles).toBeTruthy();
    });

    it('should have buttonStyles', () => {
      expect(NTTMethod.buttonStyles).toBeTruthy();
    });

    it('baseStyles should contain fieldset rules', () => {
      expect(NTTMethod.baseStyles).toContain('fieldset');
    });

    it('inlineStyles should contain method-inline rules', () => {
      expect(NTTMethod.inlineStyles).toContain('method-inline');
    });

    it('buttonStyles should contain method-btn rules', () => {
      expect(NTTMethod.buttonStyles).toContain('method-btn');
    });
  });
});
