import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Permissions.js', () => ({
  permissions: {
    canView: vi.fn(() => true),
    canEdit: vi.fn(() => true),
    canAction: vi.fn(() => true),
    user: null, authenticated: false, role: 'anonymous',
  }
}));

vi.mock('../../config.js', () => ({
  config: { LOGGING: 3, LOGEVENTS: false, DEBUG: false, API_URL: 'http://localhost:5000' }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import { Formidable } from '../../generators/form.js';

describe('Formidable detail-only title headers', () => {
  beforeEach(() => {
    Formidable.clearCache();
  });

  it('keeps name headers in their original case in display mode', () => {
    const ntt = {
      schema: {
        __name__: 'Product',
        __tablename__: 'products',
        properties: {
          name: { type: 'string', title: 'Name' },
          price: { type: 'number', title: 'Price' },
        },
        ui: { field_order: ['name', 'price'] },
        access: {},
        methods: {},
      },
      value: { name: 'mixed case title', price: 10 },
      ref: 'http://localhost:5000/Product/1',
      name: 'Product',
    };

    const html = Formidable.getForm(ntt, 'display');
    expect(html).toContain('mixed case title');
    expect(ntt.value.name).toBe('mixed case title');
  });

  it('keeps title headers in their original case in display mode', () => {
    const ntt = {
      schema: {
        __name__: 'Grant',
        __tablename__: 'grants',
        properties: {
          title: { type: 'string', title: 'Title' },
          status: { type: 'string', title: 'Status' },
        },
        ui: { field_order: ['title', 'status'] },
        access: {},
        methods: {},
      },
      value: { title: 'mixed case grant title', status: 'open' },
      ref: 'http://localhost:5000/grants/1',
      name: 'Grant',
    };

    const html = Formidable.getForm(ntt, 'display');
    expect(html).toContain('mixed case grant title');
    expect(ntt.value.title).toBe('mixed case grant title');
  });
});
