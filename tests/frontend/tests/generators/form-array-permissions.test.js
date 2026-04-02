import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Permissions.js', () => ({
  permissions: {
    canView: vi.fn(() => true),
    canEdit: vi.fn(() => true),
    canAction: vi.fn(() => true),
    user: null,
    authenticated: false,
    role: 'anonymous',
  },
}));

vi.mock('../../config.js', () => ({
  config: { LOGGING: 3, LOGEVENTS: false, DEBUG: false, API_URL: 'http://localhost:5000' }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import { permissions } from '../../utils/Permissions.js';
import { Formidable } from '../../generators/form.js';

describe('form.js array permissions', () => {
  beforeEach(() => {
    Formidable.clearCache();
    permissions.canEdit.mockImplementation(() => true);
  });

  it('downgrades array fields to display mode when canEdit returns false', () => {
    permissions.canEdit.mockImplementation(() => false);

    const html = Formidable.getInput({
      schema: {
        __name__: 'Product',
        __tablename__: 'products',
        properties: {
          tools: {
            type: 'array',
            title: 'Tools',
            items: { $ref: '#/$defs/Tool' },
            access: { edit: 'admin' },
          },
        },
        $defs: { Tool: { __tablename__: 'tools' } },
      },
      value: {
        id: 1,
        tools: ['http://localhost:5000/tools/1'],
      },
      name: 'Product',
    }, 'tools', 'edit');

    expect(html).toContain('mode="display"');
    expect(html).not.toContain('<ntx-ref-picker');
    expect(html).not.toContain('data-array-action="remove-ref"');
  });
});
