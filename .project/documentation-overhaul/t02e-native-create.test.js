// Runtime schema is captured from the extracted, disposable tutorial server.
// No copied client model, runtime patch, or successful HTTP create substitute.
import { Formidable } from '../../generators/form.js';
import schema from './t02e-issue-schema.json';

describe('R01 tutorial empty-value native create form', () => {
  beforeEach(() => Formidable.clearCache());

  it('renders the required name header from value={} and reads typed input for native validation', () => {
    expect(schema.required).toContain('name');
    expect(schema.properties).not.toHaveProperty('title');
    const ntt = {schema, value: {}}; // ntx-list.openCreateModal initializes exactly this value.
    const root = document.createElement('div');
    root.innerHTML = Formidable.getForm(ntt, 'edit');
    const input = root.querySelector('input[data-key="name"]');
    expect(input).not.toBeNull();
    expect(input.hasAttribute('name')).toBe(false);
    expect(Formidable.validateForm(ntt)).toEqual(expect.arrayContaining([
      expect.objectContaining({field: 'name'}),
    ]));
    input.value = 'Native create name';
    const value = Formidable.readFormValue(root, ntt);
    expect(value.name).toBe('Native create name');
    expect(Formidable.validateForm({schema, value})).toEqual([]);
  });

  it('rejects empty and HTML-bearing names without claiming to sanitize other fields', () => {
    for (const name of ['', '<b>bad</b>']) {
      expect(Formidable.validateForm({schema, value: {name}})).toEqual(expect.arrayContaining([
        expect.objectContaining({field: 'name'}),
      ]));
    }
  });

  it('reproduces why a required title fails in the same empty-value header path', () => {
    const oldSchema = structuredClone(schema);
    oldSchema.properties.title = oldSchema.properties.name;
    delete oldSchema.properties.name;
    oldSchema.required = oldSchema.required.map(key => key === 'name' ? 'title' : key);
    const ntt = {schema: oldSchema, value: {}};
    const root = document.createElement('div');
    root.innerHTML = Formidable.getForm(ntt, 'edit');
    expect(root.querySelector('input[data-key="title"]')).toBeNull();
    const input = root.querySelector('input[data-key="name"]');
    expect(input).not.toBeNull();
    input.value = 'Cannot supply title';
    expect(Formidable.validateForm({schema: oldSchema, value: Formidable.readFormValue(root, ntt)}))
      .toEqual(expect.arrayContaining([expect.objectContaining({field: 'title'})]));
  });
});
