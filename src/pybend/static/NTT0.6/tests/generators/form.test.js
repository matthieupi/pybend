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

  describe('getHeader(ntt, mode)', () => {
    it('should render h2 + h4 in display mode', () => {
      const html = Formidable.getForm(makeNtt(), 'display');
      expect(html).toContain('<h2');
      expect(html).toContain('Test Product');
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
          $defs: { Comment: { ui: { renderer: { item: 'ntt-item' } } } }
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
      expect(html).toContain('list-field-count');
      expect(html).toContain('3'); // count
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
      expect(html).toContain('nested-collapsed');
      expect(html).toContain('Show 2 more');
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
      expect(html).toContain('list-field-count');
      expect(html).toContain('2');
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

    it('should format $ref as [Reference: ...]', () => {
      const result = Formidable.formatDisplayValue({ type: '$ref' }, 'user', { name: 'Alice' });
      expect(result).toContain('Reference');
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
      expect(html).toContain('Reference');
      expect(html).toContain('Alice');
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
