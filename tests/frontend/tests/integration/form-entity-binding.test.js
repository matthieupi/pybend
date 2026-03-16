/**
 * Form Generation + Entity Binding — Integration Tests
 *
 * Tests: Formidable form rendering, field order, widgets, grouping, validation attrs
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, makeProductData, API_URL } from './helpers/mock-schemas.js';
import { flush } from './helpers/test-env.js';

let Formidable, permissions;

afterEach(async () => {
  await flush(10);
});

beforeEach(async () => {
  vi.resetModules();
  global.fetch = vi.fn(() => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve({}),
  }));

  const formMod = await import('../../generators/form.js');
  const permMod = await import('../../utils/Permissions.js');
  Formidable = formMod.Formidable;
  permissions = permMod.permissions;
});

function makeNtt(schema = ProductSchema, value = makeProductData(1)) {
  return { schema, value, name: schema.__name__, ref: value.$id };
}

describe('Form Generation', () => {

  it('getForm renders header with name', () => {
    const ntt = makeNtt();
    const html = Formidable.getForm(ntt, 'display');
    expect(html).toContain('Test Product 1');
    expect(html).toContain('data-value="name"');
  });

  it('getForm in edit mode renders input for name', () => {
    const ntt = makeNtt();
    const html = Formidable.getForm(ntt, 'edit');
    expect(html).toContain('data-key="name"');
    expect(html).toContain('type="text"');
  });

  it('field_order from schema.ui is respected', () => {
    const ntt = makeNtt();
    const html = Formidable.getForm(ntt, 'display');
    // Description is in headerFields and rendered as <h4> before grouped fields.
    // Price is in the 'main' group. Both should be present.
    // Verify field_order does not include hidden fields (id, image, user_owner)
    expect(html).not.toContain('data-value="id"');
    expect(html).toContain('Price');
    // Comments and Likes are in the Social group and should appear after main group
    const mainPos = html.indexOf('ntx-group-main');
    const socialPos = html.indexOf('ntx-group-Social');
    expect(mainPos).toBeLessThan(socialPos);
  });

  it('fields with ui.display=false are hidden', () => {
    const ntt = makeNtt();
    const html = Formidable.getForm(ntt, 'display');
    // id has ui.display=false
    expect(html).not.toContain('data-value="id"');
    // image has ui.display=false
    expect(html).not.toContain('data-value="image"');
  });

  it('protected fields are hidden in edit mode', () => {
    const ntt = makeNtt();
    const html = Formidable.getForm(ntt, 'edit');
    // user_owner has ui.protected=true
    expect(html).not.toContain('data-key="user_owner"');
  });

  it('currency widget renders $ prefix', () => {
    const ntt = makeNtt();
    const html = Formidable.getForm(ntt, 'display');
    expect(html).toContain('$29.99');
    expect(html).toContain('currency-display');
  });

  it('currency widget in edit mode renders currency-input with $ symbol', () => {
    const ntt = makeNtt();
    // Make permissions allow edit for price field
    const originalCanEdit = permissions.canEdit.bind(permissions);
    vi.spyOn(permissions, 'canEdit').mockReturnValue(true);

    const html = Formidable.getForm(ntt, 'edit');
    expect(html).toContain('currency-symbol');
    expect(html).toContain('$');
    expect(html).toContain('type="number"');

    permissions.canEdit.mockRestore?.();
  });

  it('textarea widget renders <textarea> in edit mode', () => {
    const ntt = makeNtt();
    ntt.value.description = 'Test description';
    const html = Formidable.getForm(ntt, 'edit');
    expect(html).toContain('<textarea');
    expect(html).toContain('data-key="description"');
  });

  it('description rendered as header in display mode', () => {
    const ntt = makeNtt();
    ntt.value.description = 'Test description';
    const html = Formidable.getForm(ntt, 'display');
    // description is in headerFields, so it renders as <h4> not text-block
    expect(html).toContain('<h4');
    expect(html).toContain('Test description');
  });

  it('boolean field renders checkbox', () => {
    const boolSchema = {
      ...ProductSchema,
      __name__: 'BoolTest',
      properties: {
        ...ProductSchema.properties,
        active: { type: 'boolean', title: 'Active' },
      },
      ui: { field_order: ['name', 'active'] },
    };
    const ntt = makeNtt(boolSchema, { ...makeProductData(1), active: true });
    const html = Formidable.getForm(ntt, 'edit');
    expect(html).toContain('type="checkbox"');
    expect(html).toContain('checked');
  });

  it('number field renders number input', () => {
    const ntt = makeNtt();
    vi.spyOn(permissions, 'canEdit').mockReturnValue(true);
    const html = Formidable.getForm(ntt, 'edit');
    // Price is a number field
    expect(html).toContain('data-type="number"');
    permissions.canEdit.mockRestore?.();
  });

  it('field groups render fieldsets with legends', () => {
    const ntt = makeNtt();
    const html = Formidable.getForm(ntt, 'display');
    expect(html).toContain('<fieldset');
    expect(html).toContain('<legend>');
    expect(html).toContain('main');
    expect(html).toContain('Social');
  });

  it('array fields render list-field container', () => {
    const ntt = makeNtt();
    ntt.value.comments = [
      `${API_URL}/products/1/comments/1`,
      `${API_URL}/products/1/comments/2`,
    ];
    const html = Formidable.getForm(ntt, 'display');
    expect(html).toContain('list-field');
    expect(html).toContain('list-field-count');
  });

  it('attached methods render ntx-method elements after target field', () => {
    const ntt = makeNtt();
    const attached = {
      comment: ProductSchema.methods.comment,
    };
    const html = Formidable.getForm(ntt, 'display', attached);
    expect(html).toContain('ntx-method');
    expect(html).toContain('method="comment"');
  });

  it('methods are hidden in edit mode', () => {
    const ntt = makeNtt();
    const attached = {
      comment: ProductSchema.methods.comment,
    };
    const html = Formidable.getForm(ntt, 'edit', attached);
    expect(html).not.toContain('ntx-method');
  });

  it('validationAttrs generates correct HTML5 attributes', () => {
    const def = {
      minLength: 3,
      maxLength: 100,
      minimum: 0,
      exclusiveMinimum: null,
      maximum: 1000,
      pattern: '^[a-z]+$',
      ui: { placeholder: 'Enter...' },
    };
    const attrs = Formidable.validationAttrs(def, true);
    expect(attrs).toContain('required');
    expect(attrs).toContain('minlength="3"');
    expect(attrs).toContain('maxlength="100"');
    expect(attrs).toContain('min="0"');
    expect(attrs).toContain('max="1000"');
    expect(attrs).toContain('pattern="^[a-z]+$"');
    expect(attrs).toContain('placeholder="Enter..."');
  });

  it('validationAttrs with no constraints returns empty string', () => {
    const attrs = Formidable.validationAttrs({}, false);
    expect(attrs).toBe('');
  });

  it('formatDisplayValue handles currency widget', () => {
    const def = { ui: { widget: 'currency' }, type: 'number' };
    expect(Formidable.formatDisplayValue(def, 'price', 29.99)).toBe('$29.99');
  });

  it('formatDisplayValue handles selfref type', () => {
    const def = { type: 'selfref' };
    expect(Formidable.formatDisplayValue(def, 'parent_id', 5)).toBe('[Parent: #5]');
    expect(Formidable.formatDisplayValue(def, 'parent_id', null)).toBe('(top-level)');
  });

  it('formatDisplayValue returns plain value for standard fields', () => {
    const def = { type: 'string' };
    expect(Formidable.formatDisplayValue(def, 'name', 'hello')).toBe('hello');
  });

  it('getListInput with show-more for arrays > VISIBLE_COUNT', () => {
    const ntt = makeNtt();
    ntt.value.comments = [
      `${API_URL}/products/1/comments/1`,
      `${API_URL}/products/1/comments/2`,
      `${API_URL}/products/1/comments/3`,
    ];
    const html = Formidable.getListInput(ntt, 'comments', 'display');
    expect(html).toContain('show-more-btn');
    expect(html).toContain('nested-collapsed');
  });

  it('getListInput resolves child tag from $defs renderer hints', () => {
    const ntt = makeNtt();
    ntt.value.comments = [`${API_URL}/products/1/comments/1`];
    const html = Formidable.getListInput(ntt, 'comments', 'display');
    // Default childTag from renderer config or ntx-item
    expect(html).toContain('ntx-item');
  });
});
