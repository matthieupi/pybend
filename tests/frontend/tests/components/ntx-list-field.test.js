import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../core/NTT.js', () => ({
  NTT: {
    get: vi.fn(),
  },
}));

import { NTT } from '../../core/NTT.js';
import '../../components/ntx-list-field.js';

function encode(value) {
  return encodeURIComponent(JSON.stringify(value));
}

function mountListField({
  field = 'tools',
  mode = 'edit',
  value = ['http://localhost:5000/tools/1', 'http://localhost:5000/tools/2'],
  schema = {
    type: 'array',
    title: 'Tools',
    items: { $ref: '#/$defs/Tool' },
  },
  defs = {
    Tool: {
      __tablename__: 'tools',
      ui: { renderer: { item: 'ntx-item' } },
    },
  },
} = {}) {
  const el = document.createElement('ntx-list-field');
  el.setAttribute('field', field);
  el.setAttribute('mode', mode);
  el.setAttribute('schema', encode(schema));
  el.setAttribute('defs', encode(defs));
  el.setAttribute('value', encode(value));
  el.setAttribute('parent-model', 'Product');
  el.setAttribute('parent-table', 'products');
  el.setAttribute('parent-id', '1');
  document.body.appendChild(el);
  return el;
}

describe('ntx-list-field.js', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    NTT.get.mockReset();
  });

  it('renders ref picker without deferred persistence for ref arrays', () => {
    const el = mountListField();

    const picker = el.shadowRoot.querySelector('ntx-ref-picker');
    expect(picker).not.toBeNull();
    expect(picker.getAttribute('defer-save')).not.toBe('true');
  });

  it('sends DELETE through the parent entity when removing a ref', () => {
    const parentSend = vi.fn();
    NTT.get.mockReturnValue({
      addr: 'Product/1',
      send: parentSend,
    });
    const el = mountListField();

    el.shadowRoot.querySelector('[data-array-action="remove-ref"]').click();

    expect(NTT.get).toHaveBeenCalledWith('Product/1');
    expect(parentSend).toHaveBeenCalledWith(expect.objectContaining({
      name: 'DELETE',
      source: 'Product/1',
      target: 'http://localhost:5000/tools/1',
      meta: { inbox: '_response_' },
    }));
  });

  it('renders class-name string refs as-is', () => {
    const ref = 'http://localhost:5000/Product/1/Comment/2';
    const el = mountListField({ value: [ref], mode: 'display' });

    const child = el.shadowRoot.querySelector('ntx-item');
    expect(child.getAttribute('ref')).toBe(ref);
  });

  it('sends DELETE using class-name refs as-is', () => {
    const ref = 'http://localhost:5000/Product/1/Comment/2';
    const parentSend = vi.fn();
    NTT.get.mockReturnValue({
      addr: 'Product/1',
      send: parentSend,
    });
    const el = mountListField({ value: [ref] });

    el.shadowRoot.querySelector('[data-array-action="remove-ref"]').click();

    expect(parentSend).toHaveBeenCalledWith(expect.objectContaining({
      name: 'DELETE',
      target: ref,
    }));
  });

  it('renders object refs using their class-name $id', () => {
    const ref = 'http://localhost:5000/Product/1/Comment/2';
    const el = mountListField({ value: [{ id: 2, $id: ref, name: 'Comment' }] });

    const child = el.shadowRoot.querySelector('ntx-item');
    const remove = el.shadowRoot.querySelector('[data-array-action="remove-ref"]');

    expect(child.getAttribute('ref')).toBe(ref);
    expect(remove.dataset.ref).toBe(ref);
  });

  it('still updates local state after removing a ref', () => {
    NTT.get.mockReturnValue({
      addr: 'Product/1',
      send: vi.fn(),
    });
    const el = mountListField();

    el.shadowRoot.querySelector('[data-array-action="remove-ref"]').click();

    expect(decodeURIComponent(el.getAttribute('value'))).toBe(JSON.stringify(['http://localhost:5000/tools/2']));
  });

  it('emits typed integer values for scalar arrays', () => {
    const el = mountListField({
      field: 'scores',
      value: [1],
      schema: {
        type: 'array',
        title: 'Scores',
        items: { type: 'integer' },
      },
      defs: {},
    });

    const changes = [];
    el.addEventListener('field-change', (e) => changes.push(e.detail.value));

    const input = el.shadowRoot.querySelector('[data-index="0"]');
    input.value = '7';
    input.dispatchEvent(new Event('input', { bubbles: true }));

    expect(changes.at(-1)).toEqual([7]);
  });

  it('emits typed boolean values for scalar arrays', () => {
    const el = mountListField({
      field: 'flags',
      value: [false],
      schema: {
        type: 'array',
        title: 'Flags',
        items: { type: 'boolean' },
      },
      defs: {},
    });

    const changes = [];
    el.addEventListener('field-change', (e) => changes.push(e.detail.value));

    const input = el.shadowRoot.querySelector('[data-index="0"]');
    input.checked = true;
    input.dispatchEvent(new Event('change', { bubbles: true }));

    expect(changes.at(-1)).toEqual([true]);
  });
});
