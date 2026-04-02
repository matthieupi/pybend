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
} = {}) {
  const el = document.createElement('ntx-list-field');
  el.setAttribute('field', field);
  el.setAttribute('mode', mode);
  el.setAttribute('schema', encode({
    type: 'array',
    title: 'Tools',
    items: { $ref: '#/$defs/Tool' },
  }));
  el.setAttribute('defs', encode({
    Tool: {
      __tablename__: 'tools',
      ui: { renderer: { item: 'ntx-item' } },
    },
  }));
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

  it('still updates local state after removing a ref', () => {
    NTT.get.mockReturnValue({
      addr: 'Product/1',
      send: vi.fn(),
    });
    const el = mountListField();

    el.shadowRoot.querySelector('[data-array-action="remove-ref"]').click();

    expect(decodeURIComponent(el.getAttribute('value'))).toBe(JSON.stringify(['http://localhost:5000/tools/2']));
  });
});
