import { describe, it, expect, vi } from 'vitest';

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

describe('Formidable detail-only display formatting', () => {
  it('preserves name field values in display mode', () => {
    const formatted = Formidable.formatDisplayValue({ type: 'string', title: 'Name' }, 'name', 'mixed case title');
    expect(formatted).toBe('mixed case title');
  });

  it('preserves title field values in display mode', () => {
    const formatted = Formidable.formatDisplayValue({ type: 'string', title: 'Title' }, 'title', 'mixed case grant title');
    expect(formatted).toBe('mixed case grant title');
  });
});
