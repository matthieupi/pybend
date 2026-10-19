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

function buildMethod(params = {}) {
  const method = new NTTMethod();
  method.schema = { parameters: params };
  method.proto = { schema: { $defs: {} }, call: vi.fn() };
  method.method = 'fetch';
  method.label = 'Fetch';
  method.mode = 'manual';
  method.buttonLabel = 'Run';
  method.layout = 'fieldset';
  method.value = {};
  return method;
}

describe('ntx-method optional field disclosure', () => {
  beforeEach(() => {
    Object.defineProperty(NTTMethod.prototype, 'proto', {
      value: null, writable: true, configurable: true,
    });
  });

  it('hides optional-only method parameters by default', () => {
    const method = buildMethod({
      use_js: { type: 'boolean', title: 'Use JS' },
    });

    method.renderFieldset();

    expect(method.shadowRoot.querySelector('[data-key="use_js"]')).toBeNull();
  });

  it('shows optional parameters only after expanding advanced options', () => {
    const method = buildMethod({
      use_js: { type: 'boolean', title: 'Use JS' },
    });

    method.renderFieldset();

    const toggle = method.shadowRoot.querySelector('.method-optional-toggle');
    expect(toggle).not.toBeNull();
    toggle.click();

    expect(method.shadowRoot.querySelector('[data-key="use_js"]')).not.toBeNull();
  });
});
