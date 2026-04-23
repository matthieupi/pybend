import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Permissions.js', () => ({
  permissions: {
    canView: vi.fn(() => true),
    canEdit: vi.fn(() => true),
    canAction: vi.fn(() => true),
    user: null, authenticated: false, role: 'anonymous',
  }
}));

import { permissions } from '../../utils/Permissions.js';
vi.mock('../../config.js', () => ({
  config: { LOGGING: 3, LOGEVENTS: false, DEBUG: false, API_URL: 'http://localhost:5000' }
}));
vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import { Formidable } from '../../generators/form.js';

describe('form.js (Formidable)', () => {

  beforeEach(() => {
    // Clear layout cache between tests to prevent cross-test cache poisoning.
    // The cache keys on schema.__name__:mode:role, so tests that override
    // schema.ui.groups (same __name__) get stale cached layouts without groups.
    Formidable.clearCache();
  });

  const schema = {
    __name__: 'Product',
    __tablename__: 'products',
    properties: {
      id: { type: 'integer', readOnly: true, title: 'ID', ui: { display: false } },
      name: { type: 'string', title: 'Name', minLength: 1, maxLength: 200 },
      price: { type: 'number', title: 'Price', ui: { widget: 'currency' }, minimum: 0 },
      description: { type: 'string', title: 'Description', ui: { widget: 'textarea' } },
      active: { type: 'boolean', title: 'Active' },
    },
    required: ['name'],
    ui: {
      field_order: ['name', 'price', 'description', 'active'],
    },
    access: {},
    methods: {},
  };

  const makeNtt = (value = {}) => ({
    schema,
    value: { id: 1, name: 'Test Product', price: 29.99, description: 'A test', active: true, ...value },
    ref: 'http://localhost:5000/products/1',
    name: 'Product',
  });

  describe('getForm(ntt, mode, attachedMethods)', () => {
    it('should render form with header and fields', () => {
      const html = Formidable.getForm(makeNtt(), 'display');
      expect(html).toContain('Test Product');
    });

    it('should filter protected fields in edit mode', () => {
      const ntt = makeNtt();
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          secret: { type: 'string', title: 'Secret', ui: { protected: true } },
        },
        ui: { ...schema.ui, field_order: ['name', 'price', 'description', 'active', 'secret'] }
      };
      const html = Formidable.getForm(ntt, 'edit');
      // Protected field should not have an edit input
      expect(html).not.toContain('data-key="secret"');
    });

    it('should respect field_order', () => {
      const html = Formidable.getForm(makeNtt(), 'display');
      // 'price' and 'active' are non-header fields in field_order
      // Price should appear before Active in the output
      const pricePos = html.indexOf('Price');
      const activePos = html.indexOf('Active');
      expect(pricePos).toBeLessThan(activePos);
    });

    it('should handle groups when defined', () => {
      const ntt = makeNtt();
      // 'description' is a header field so it's excluded from renderableFields.
      // Use non-header fields in groups to test grouping.
      ntt.schema = {
        ...schema,
        ui: {
          ...schema.ui,
          groups: { Main: ['price'], Settings: ['active'] }
        }
      };
      const html = Formidable.getForm(ntt, 'display');
      expect(html).toContain('Main');
      expect(html).toContain('Settings');
    });

    it('should handle missing schema gracefully', () => {
      const ntt = { schema: {}, value: {}, ref: '', name: '' };
      // The function reads properties from schema, which may be undefined
      // It should not throw
      const html = Formidable.getForm(ntt, 'display');
      expect(typeof html).toBe('string');
    });
  });

  describe('getFields(ntt, mode, attachedMethods)', () => {
    it('should render method-style boolean parameters as checkboxes', () => {
      const html = Formidable.getFields({
        schema: {
          __name__: 'Source.fetch',
          parameters: {
            use_js: { type: 'boolean', title: 'Use JS' },
          },
          required: [],
          ui: {},
        },
        value: { use_js: true },
        name: 'fetch',
      }, 'edit');

      expect(html).toContain('data-key="use_js"');
      expect(html).toContain('type="checkbox"');
      expect(html).not.toContain('<input type="boolean"');
      expect(html).toContain('checked');
    });

    it('should render method-style array parameters through the list field path', () => {
      const html = Formidable.getFields({
        schema: {
          __name__: 'Search.filter',
          parameters: {
            tags: { type: 'array', title: 'Tags', items: { type: 'string' } },
          },
          required: [],
          ui: {},
        },
        value: { tags: ['grant', 'canada'] },
        name: 'filter',
      }, 'edit');

      expect(html).toContain('list-field');
      expect(html).toContain('data-key="tags"');
    });

    it('should keep supporting entity-style property schemas', () => {
      const html = Formidable.getFields(makeNtt(), 'edit');
      expect(html).toContain('data-key="price"');
      expect(html).toContain('data-key="active"');
    });

    it('should render equivalent boolean fields for method parameters and entity properties', () => {
      const methodHtml = Formidable.getFields({
        schema: {
          __name__: 'Source.fetch',
          parameters: { use_js: { type: 'boolean', title: 'Use JS' } },
          required: [],
          ui: {},
        },
        value: { use_js: true },
        name: 'fetch',
      }, 'edit');

      const entityHtml = Formidable.getFields({
        schema: {
          __name__: 'SourceConfig',
          properties: { use_js: { type: 'boolean', title: 'Use JS' } },
          required: [],
          ui: {},
        },
        value: { use_js: true },
        name: 'SourceConfig',
      }, 'edit');

      expect(methodHtml).toContain('data-key="use_js"');
      expect(entityHtml).toContain('data-key="use_js"');
      expect(methodHtml).toContain('type="checkbox"');
      expect(entityHtml).toContain('type="checkbox"');
    });
  });

  describe('getHeader(ntt, mode)', () => {
    it('should render h2 + h4 in display mode', () => {
      const html = Formidable.getForm(makeNtt(), 'display');
      expect(html).toContain('<h2');
      expect(html).toContain('Test Product');
    });

    it('should preserve the rendered header text without mutating the source value', () => {
      const ntt = makeNtt({ name: 'lower case title' });
      const html = Formidable.getForm(ntt, 'display');
      expect(html).toContain('lower case title');
      expect(ntt.value.name).toBe('lower case title');
    });

    it('should render input + textarea in edit mode', () => {
      const html = Formidable.getForm(makeNtt(), 'edit');
      expect(html).toContain('data-key="name"');
    });
  });

  describe('getInput(ntt, key, mode)', () => {
    it('should render text input for string type', () => {
      const html = Formidable.getInput(makeNtt(), 'name', 'edit');
      expect(html).toContain('type="text"');
      expect(html).toContain('data-key="name"');
    });

    it('should render number input for number type', () => {
      const html = Formidable.getInput(makeNtt(), 'price', 'edit');
      expect(html).toContain('type="number"');
    });

    it('should render checkbox for boolean type', () => {
      const html = Formidable.getInput(makeNtt(), 'active', 'edit');
      expect(html).toContain('type="checkbox"');
    });

    it('should keep boolean edit checkboxes checked when the value is true', () => {
      const html = Formidable.getInput(makeNtt({ active: true }), 'active', 'edit');
      expect(html).toContain('type="checkbox"');
      expect(html).toContain('widget-bool');
      expect(html).toContain('checked');
    });

    it('should keep boolean display checkboxes checked when the value is true', () => {
      const html = Formidable.getInput(makeNtt({ active: true }), 'active', 'display');
      expect(html).toContain('type="checkbox"');
      expect(html).toContain('widget-bool');
      expect(html).toContain('checked');
      expect(html).toContain('aria-disabled="true"');
    });

    it('should render textarea for textarea widget', () => {
      const html = Formidable.getInput(makeNtt(), 'description', 'edit');
      expect(html).toContain('<textarea');
    });

    it('should render currency display in display mode', () => {
      const html = Formidable.getInput(makeNtt(), 'price', 'display');
      expect(html).toContain('$29.99');
    });

    it('should render text-block for textarea widget in display mode', () => {
      const html = Formidable.getInput(makeNtt(), 'description', 'display');
      expect(html).toContain('text-block');
    });

    it('should apply validation attributes in edit mode', () => {
      const html = Formidable.getInput(makeNtt(), 'name', 'edit');
      expect(html).toContain('minlength="1"');
      expect(html).toContain('maxlength="200"');
      expect(html).toContain('required');
    });
  });

  describe('getListInput(ntt, key, mode)', () => {
    it('should render list field with items', () => {
      const ntt = {
        schema: {
          __name__: 'Product',
          properties: {
            comments: {
              type: 'array',
              title: 'Comments',
              items: { $ref: '#/$defs/Comment' }
            }
          },
          $defs: { Comment: { ui: { renderer: { item: 'ntx-item' } } } }
        },
        value: {
          comments: [
            'http://localhost:5000/products/1/comments/1',
            'http://localhost:5000/products/1/comments/2',
            'http://localhost:5000/products/1/comments/3',
          ]
        },
        ref: 'http://localhost:5000/products/1',
        name: 'Product',
      };
      const html = Formidable.getListInput(ntt, 'comments', 'display');
      expect(html).toContain('list-field');
      expect(html).toContain('field="comments"');
      expect(html).toContain('value="%5B');
    });

    it('should show first 2 items visible and rest collapsed', () => {
      const ntt = {
        schema: {
          __name__: 'Product',
          properties: {
            items: {
              type: 'array', title: 'Items',
              items: { $ref: '#/$defs/Item' }
            }
          },
          $defs: { Item: {} }
        },
        value: {
          items: ['http://a/1', 'http://a/2', 'http://a/3', 'http://a/4']
        },
        ref: 'http://a',
        name: 'Product',
      };
      const html = Formidable.getListInput(ntt, 'items', 'display');
      expect(html).toContain('field="items"');
      expect(html).toContain('mode="display"');
    });

    it('should handle populated objects with $id', () => {
      const ntt = {
        schema: {
          __name__: 'Product',
          properties: {
            tags: { type: 'array', title: 'Tags', items: { $ref: '#/$defs/Tag' } }
          },
          $defs: { Tag: {} }
        },
        value: {
          tags: [
            { $id: 'http://a/tags/1', name: 'Tag1' },
            { $id: 'http://a/tags/2', name: 'Tag2' },
          ]
        },
        ref: 'http://a',
        name: 'Product',
      };
      const html = Formidable.getListInput(ntt, 'tags', 'display');
      expect(html).toContain('field="tags"');
      expect(html).toContain('%24id');
    });
  });

  describe('renderGroupedFields()', () => {
    it('should render fieldsets per group', () => {
      const ntt = makeNtt();
      ntt.schema = {
        ...schema,
        ui: { ...schema.ui, groups: { Main: ['name', 'price'] } }
      };
      const html = Formidable.renderGroupedFields(
        ntt, ['name', 'price', 'description'], { Main: ['name', 'price'] }, 'display', {}
      );
      expect(html).toContain('<fieldset');
      expect(html).toContain('Main');
    });

    it('should render ungrouped fields at end', () => {
      const ntt = makeNtt();
      const html = Formidable.renderGroupedFields(
        ntt, ['name', 'price', 'description'], { Main: ['name'] }, 'display', {}
      );
      expect(html).toContain('Price');
      expect(html).toContain('Description');
    });
  });

  describe('formatDisplayValue(def, key, value)', () => {
    it('should format currency as $X.XX', () => {
      const result = Formidable.formatDisplayValue({ ui: { widget: 'currency' } }, 'price', 29.99);
      expect(result).toBe('$29.99');
    });

    it('should format $ref with entity name', () => {
      const result = Formidable.formatDisplayValue({ type: '$ref' }, 'user', { name: 'Alice' });
      expect(result).toContain('Alice');
    });

    it('should format selfref as [Parent: #id] or (top-level)', () => {
      expect(Formidable.formatDisplayValue({ type: 'selfref' }, 'parent_id', 5)).toBe('[Parent: #5]');
      expect(Formidable.formatDisplayValue({ type: 'selfref' }, 'parent_id', null)).toBe('(top-level)');
      expect(Formidable.formatDisplayValue({ type: 'selfref' }, 'parent_id', 0)).toBe('(top-level)');
    });

    it('should return empty string for null/undefined value', () => {
      expect(Formidable.formatDisplayValue({}, 'x', null)).toBe('');
      expect(Formidable.formatDisplayValue({}, 'x', undefined)).toBe('');
    });

    it('should return raw value for unknown type', () => {
      expect(Formidable.formatDisplayValue({}, 'x', 'hello')).toBe('hello');
    });
  });

  describe('validationAttrs(def, isRequired)', () => {
    it('should build required attribute', () => {
      const result = Formidable.validationAttrs({}, true);
      expect(result).toContain('required');
    });

    it('should build minlength/maxlength', () => {
      const result = Formidable.validationAttrs({ minLength: 3, maxLength: 100 }, false);
      expect(result).toContain('minlength="3"');
      expect(result).toContain('maxlength="100"');
    });

    it('should build min/max from minimum/maximum', () => {
      const result = Formidable.validationAttrs({ minimum: 0, maximum: 999 }, false);
      expect(result).toContain('min="0"');
      expect(result).toContain('max="999"');
    });

    it('should build pattern', () => {
      const result = Formidable.validationAttrs({ pattern: '^[a-z]+$' }, false);
      expect(result).toContain('pattern="^[a-z]+$"');
    });

    it('should build placeholder from ui', () => {
      const result = Formidable.validationAttrs({ ui: { placeholder: 'Enter name...' } }, false);
      expect(result).toContain('placeholder="Enter name..."');
    });

    it('should return empty string when no constraints', () => {
      const result = Formidable.validationAttrs({}, false);
      expect(result).toBe('');
    });
  });

  describe('title field not duplicated (models using title instead of name)', () => {
    const grantSchema = {
      __name__: 'Grant',
      __tablename__: 'grants',
      properties: {
        id: { type: 'integer', readOnly: true, title: 'ID', ui: { display: false } },
        title: { type: 'string', title: 'Title', minLength: 1 },
        amount_min: { type: 'number', title: 'Amount Min', ui: { widget: 'currency' } },
        amount_max: { type: 'number', title: 'Amount Max', ui: { widget: 'currency' } },
        status: { type: 'string', title: 'Status' },
      },
      required: ['title'],
      ui: { field_order: ['title', 'amount_min', 'amount_max', 'status'] },
      access: {},
      methods: {},
    };

    const makeGrantNtt = (value = {}) => ({
      schema: grantSchema,
      value: { id: 1, title: 'NSF Computer Science Grant', amount_min: 50000, amount_max: 100000, status: 'open', ...value },
      ref: 'http://localhost:5000/grants/1',
      name: 'Grant',
    });

    it('should render title in h2 header, not as a duplicate form field', () => {
      const html = Formidable.getForm(makeGrantNtt(), 'display');
      // Title should appear in the h2 header
      expect(html).toContain('<h2');
      expect(html).toContain('NSF Computer Science Grant');
      // Title should NOT appear as a labeled form field
      const labelMatches = html.match(/<label[^>]*>Title<\/label>/g);
      expect(labelMatches).toBeNull();
    });

    it('should use title as header key in display mode', () => {
      const html = Formidable.getForm(makeGrantNtt(), 'display');
      expect(html).toContain('data-value="title"');
    });

    it('should preserve displayed title headers without mutating grant data', () => {
      const ntt = makeGrantNtt({ title: 'nsf computer science grant' });
      const html = Formidable.getForm(ntt, 'display');
      expect(html).toContain('nsf computer science grant');
      expect(ntt.value.title).toBe('nsf computer science grant');
    });

    it('should use title as header key in edit mode', () => {
      const html = Formidable.getForm(makeGrantNtt(), 'edit');
      expect(html).toContain('data-key="title"');
    });

    it('should still use name as header key for models with name field', () => {
      const html = Formidable.getForm(makeNtt(), 'display');
      expect(html).toContain('data-value="name"');
    });

    it('should exclude title from renderable fields just like name', () => {
      const html = Formidable.getForm(makeGrantNtt(), 'display');
      // amount_min and status should appear as regular fields
      expect(html).toContain('Amount Min');
      expect(html).toContain('Status');
      // Count how many times "Title" appears — should only be in the h2, not in body
      const h2Match = html.match(/<h2[^>]*>.*?NSF Computer Science Grant.*?<\/h2>/);
      expect(h2Match).not.toBeNull();
    });
  });

  describe('widget fields include labels', () => {
    it('should render label for currency widget fields', () => {
      const html = Formidable.getInput(makeNtt(), 'price', 'display');
      expect(html).toContain('<label');
      expect(html).toContain('Price');
    });

    it('should render label for currency widget in edit mode', () => {
      const html = Formidable.getInput(makeNtt(), 'price', 'edit');
      expect(html).toContain('<label');
      expect(html).toContain('Price');
    });

    it('should render label for widget fields with custom title', () => {
      const ntt = makeNtt();
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          deadline: { type: 'string', title: 'Deadline', ui: { widget: 'date' } },
        },
      };
      ntt.value.deadline = '2025-01-15';
      const html = Formidable.getInput(ntt, 'deadline', 'display');
      expect(html).toContain('<label');
      expect(html).toContain('Deadline');
    });

    it('should render label for url widget fields', () => {
      const ntt = makeNtt();
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          website: { type: 'string', title: 'Website', ui: { widget: 'url' } },
        },
      };
      ntt.value.website = 'https://example.com';
      const html = Formidable.getInput(ntt, 'website', 'display');
      expect(html).toContain('<label');
      expect(html).toContain('Website');
    });

    it('should NOT render label for name or id fields even with widget', () => {
      const ntt = makeNtt();
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          name: { ...schema.properties.name, ui: { widget: 'textarea' } },
        },
      };
      const html = Formidable.getInput(ntt, 'name', 'display');
      expect(html).not.toContain('<label');
    });
  });

  describe('resolveAnyOf(def)', () => {
    it('should resolve single non-null entry by stripping null from anyOf', () => {
      const ntt = {
        schema: {
          ...schema,
          properties: {
            ...schema.properties,
            status: {
              anyOf: [{ type: 'string', title: 'Status' }, { type: 'null' }],
              title: 'Status',
            },
          },
          ui: { ...schema.ui, field_order: ['name', 'price', 'description', 'active', 'status'] },
        },
        value: { id: 1, name: 'Test', price: 10, description: '', active: true, status: 'active' },
        ref: 'http://localhost:5000/products/1',
        name: 'Product',
      };
      // getInput calls resolveAnyOf internally for anyOf fields
      const html = Formidable.getInput(ntt, 'status', 'edit');
      expect(html).toContain('type="text"');
      expect(html).toContain('data-key="status"');
    });

    it('should throw for multiple non-null entries', () => {
      const ntt = {
        schema: {
          ...schema,
          properties: {
            ...schema.properties,
            multi: {
              anyOf: [{ type: 'string' }, { type: 'number' }],
              title: 'Multi',
            },
          },
        },
        value: { id: 1, name: 'Test', multi: 'x' },
        ref: '',
        name: 'Product',
      };
      expect(() => Formidable.getInput(ntt, 'multi', 'display')).toThrow('Multiple definitions');
    });
  });

  describe('validateForm(ntt)', () => {
    it('should return empty array for valid data', () => {
      const ntt = makeNtt();
      const errors = Formidable.validateForm(ntt);
      expect(errors).toEqual([]);
    });

    it('should catch missing required fields', () => {
      const ntt = makeNtt({ name: '' });
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'name')).toBe(true);
    });

    it('should catch minLength violations', () => {
      const ntt = makeNtt();
      // Override schema to have a strict minLength on description
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          description: { type: 'string', title: 'Description', minLength: 10, ui: { widget: 'textarea' } },
        },
      };
      ntt.value.description = 'short';
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'description')).toBe(true);
    });

    it('should catch maxLength violations', () => {
      const ntt = makeNtt();
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          name: { ...schema.properties.name, maxLength: 5 },
        },
      };
      ntt.value.name = 'Too Long Name';
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'name')).toBe(true);
    });

    it('should skip protected fields', () => {
      const ntt = makeNtt();
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          internal: { type: 'string', title: 'Internal', minLength: 10, ui: { protected: true } },
        },
        ui: { ...schema.ui, field_order: ['name', 'price', 'description', 'active', 'internal'] },
      };
      ntt.value.internal = 'x'; // would violate minLength but should be skipped
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'internal')).toBe(false);
    });

    it('should skip hidden fields', () => {
      const ntt = makeNtt();
      // id is already hidden (ui.display=false), give it a required violation
      ntt.schema = {
        ...schema,
        required: ['name', 'id'],
      };
      ntt.value.id = '';
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'id')).toBe(false);
    });

    it('should run widget validate() for widget fields', () => {
      const ntt = makeNtt();
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          website: { type: 'string', title: 'Website', ui: { widget: 'url' } },
        },
        ui: { ...schema.ui, field_order: ['name', 'price', 'description', 'active', 'website'] },
      };
      ntt.value.website = 'not-a-valid-url';
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'website')).toBe(true);
    });

    it('should catch number minimum violations', () => {
      const ntt = makeNtt({ price: -5 });
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          price: { type: 'number', title: 'Price', minimum: 0, ui: { widget: 'currency' } },
        },
      };
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'price')).toBe(true);
    });

    it('should catch number maximum violations', () => {
      const ntt = makeNtt({ price: 10000 });
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          price: { type: 'number', title: 'Price', maximum: 999, ui: { widget: 'currency' } },
        },
      };
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'price')).toBe(true);
    });

    it('should catch exclusiveMinimum violations', () => {
      const ntt = makeNtt({ price: 0 });
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          price: { type: 'number', title: 'Price', exclusiveMinimum: 0, ui: { widget: 'currency' } },
        },
      };
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'price')).toBe(true);
    });

    it('should catch exclusiveMaximum violations', () => {
      const ntt = makeNtt({ price: 100 });
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          price: { type: 'number', title: 'Price', exclusiveMaximum: 100, ui: { widget: 'currency' } },
        },
      };
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'price')).toBe(true);
    });

    it('should not report errors for valid number values', () => {
      const ntt = makeNtt({ price: 50 });
      ntt.schema = {
        ...schema,
        properties: {
          ...schema.properties,
          price: { type: 'number', title: 'Price', minimum: 0, maximum: 999, ui: { widget: 'currency' } },
        },
      };
      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'price')).toBe(false);
    });

    it('should validate expanded top-level $ref required fields', () => {
      const ntt = {
        schema: {
          __name__: 'CommentMethod',
          parameters: {
            comment: { type: '$ref', $ref: '#/$defs/Comment', title: 'Comment' },
          },
          $defs: {
            Comment: {
              properties: {
                text: { type: 'string', title: 'Text', minLength: 1 },
                rating: { type: 'integer', title: 'Rating' },
              },
              required: ['text'],
            },
          },
          required: [],
          ui: {},
        },
        value: { comment: { text: '' } },
        name: 'comment',
      };

      const errors = Formidable.validateForm(ntt);
      expect(errors.some(e => e.field === 'comment.text')).toBe(true);
    });
  });

  describe('getInput() edge cases', () => {
    it('should render selfref in edit mode as number input', () => {
      const ntt = {
        schema: {
          ...schema,
          properties: {
            ...schema.properties,
            parent_id: { type: 'selfref', title: 'Parent' },
          },
        },
        value: { id: 1, name: 'Test', parent_id: 5 },
        ref: '',
        name: 'Product',
      };
      const html = Formidable.getInput(ntt, 'parent_id', 'edit');
      expect(html).toContain('type="number"');
      expect(html).toContain('data-type="selfref"');
    });

    it('should render selfref in display mode as (top-level) for null', () => {
      const ntt = {
        schema: {
          ...schema,
          properties: {
            ...schema.properties,
            parent_id: { type: 'selfref', title: 'Parent' },
          },
        },
        value: { id: 1, name: 'Test', parent_id: null },
        ref: '',
        name: 'Product',
      };
      const html = Formidable.getInput(ntt, 'parent_id', 'display');
      expect(html).toContain('(top-level)');
    });

    it('should render $ref in display mode as [Reference: ...]', () => {
      const ntt = {
        schema: {
          ...schema,
          properties: {
            ...schema.properties,
            user: { type: '$ref', $ref: '#/$defs/User', title: 'User' },
          },
        },
        value: { id: 1, name: 'Test', user: { name: 'Alice', id: 1 } },
        ref: '',
        name: 'Product',
      };
      const html = Formidable.getInput(ntt, 'user', 'display');
      expect(html).toContain('Alice');
    });

    it('should render $ref href as ntx-item component with display="sm"', () => {
      const ntt = {
        schema: {
          ...schema,
          properties: {
            ...schema.properties,
            user_owner: { type: '$ref', $ref: '#/$defs/User', title: 'Owner', ui: { protected: true } },
          },
          $defs: { User: { ui: { renderer: { item: 'ntx-user' } } } },
        },
        value: { id: 1, name: 'Test', user_owner: 'http://localhost:5000/users/1' },
        ref: 'http://localhost:5000/products/1',
        name: 'Product',
      };
      const html = Formidable.getInput(ntt, 'user_owner', 'display');
      // Should render as a component, not plain text
      expect(html).toContain('ntx-user');
      expect(html).toContain('ref="http://localhost:5000/users/1"');
      expect(html).toContain('display="sm"');
      expect(html).toContain('data-model="User"');
      expect(html).toContain('ref-field');
    });

    it('should render $ref with $id object as ntx-item component', () => {
      const ntt = {
        schema: {
          ...schema,
          properties: {
            ...schema.properties,
            author: { type: '$ref', $ref: '#/$defs/User', title: 'Author' },
          },
          $defs: { User: {} },
        },
        value: { id: 1, name: 'Test', author: { $id: 'http://localhost:5000/users/2', name: 'Bob' } },
        ref: 'http://localhost:5000/products/1',
        name: 'Product',
      };
      const html = Formidable.getInput(ntt, 'author', 'display');
      expect(html).toContain('ntx-item');
      expect(html).toContain('ref="http://localhost:5000/users/2"');
      expect(html).toContain('display="sm"');
    });

    it('should fallback to formatRefDisplay for non-href $ref values', () => {
      const ntt = {
        schema: {
          ...schema,
          properties: {
            ...schema.properties,
            user: { type: '$ref', $ref: '#/$defs/User', title: 'User' },
          },
          $defs: { User: {} },
        },
        value: { id: 1, name: 'Test', user: null },
        ref: '',
        name: 'Product',
      };
      const html = Formidable.getInput(ntt, 'user', 'display');
      // Null value should not render a component — should fallback gracefully
      expect(html).not.toContain('ntx-item');
      expect(html).toContain('data-value="user"');
    });

    it('should use display mode when canEdit returns false even in edit mode', () => {
      permissions.canEdit.mockImplementation(() => false);
      const html = Formidable.getInput(makeNtt(), 'price', 'edit');
      // Should render display version (currency display) not edit input
      expect(html).toContain('$29.99');
      permissions.canEdit.mockImplementation(() => true);
    });

    it('should handle empty value object', () => {
      const ntt = {
        schema,
        value: {},
        ref: '',
        name: 'Product',
      };
      // Should not throw for missing values
      const html = Formidable.getInput(ntt, 'price', 'display');
      expect(typeof html).toBe('string');
    });
  });
});
