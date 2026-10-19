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

import { NtxAgents } from '../../../../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agents.js';

function makeSchema() {
  return {
    __name__: 'AgentActor',
    title: 'AgentActor',
    access: { create: { rule: 'authenticated' } },
    ui: { renderer: { item: 'ntx-agent' }, icon: 'veille-tools' },
  };
}

function makeCatalog() {
  return [
    {
      id: 'pipeline',
      title: 'Pipeline Agent',
      summary: 'Runs the source-to-grant pipeline and orchestrates analysis.',
      icon: 'veille-execute',
      route: '',
      cta: 'Open Pipeline',
      kind: 'built-in',
    },
    {
      id: 'grant-analysis',
      title: 'Grant Analysis Agent',
      summary: 'Explains that grant analysis runs from the Grants workflow.',
      icon: 'veille-analyze',
      route: 'grants',
      cta: 'Open Grants',
      kind: 'built-in',
    },
  ];
}

describe('ntx-agents', () => {
  beforeEach(() => {
    window.NTX_AGENT_CATALOGS = { veille: makeCatalog() };
    window.location.hash = '';
    document.body.innerHTML = '';
  });

  it('should be registered as ntx-agents', () => {
    expect(customElements.get('ntx-agents')).toBe(NtxAgents);
  });

  it('renders built-in entries from the configured catalog', () => {
    const el = document.createElement('ntx-agents');
    el.model = 'AgentActor';
    el.schema = makeSchema();
    el.value = ['AgentActor/1'];
    el.setAttribute('catalog', 'veille');
    el.setAttribute('display', 'xl');

    el.render();

    const builtins = [...el.shadowRoot.querySelectorAll('.agent-launch-card')];
    expect(builtins).toHaveLength(2);
    expect(el.shadowRoot.textContent).toContain('Built-in Agents');
    expect(el.shadowRoot.textContent).toContain('Pipeline Agent');
  });

  it('renders stored entries through the inherited child flow', () => {
    const el = document.createElement('ntx-agents');
    el.model = 'AgentActor';
    el.schema = makeSchema();
    el.value = ['AgentActor/1', 'AgentActor/2'];
    el.setAttribute('display', 'xl');

    el.render();

    const stored = [...el.shadowRoot.querySelectorAll('.agents-stored-list ntx-agent')];
    expect(stored).toHaveLength(2);
    expect(stored[0].ref || stored[0].getAttribute('ref')).toBe('AgentActor/1');
  });

  it('omits the built-in section when the catalog is absent', () => {
    const el = document.createElement('ntx-agents');
    el.model = 'AgentActor';
    el.schema = makeSchema();
    el.value = ['AgentActor/1'];

    el.render();

    expect(el.shadowRoot.querySelector('.agents-builtins')).toBeNull();
    expect(el.shadowRoot.querySelectorAll('.agents-stored-list ntx-agent')).toHaveLength(1);
  });

  it('switches to compact rows in sidebar-dropdown mode', () => {
    const el = document.createElement('ntx-agents');
    el.model = 'AgentActor';
    el.schema = makeSchema();
    el.value = ['AgentActor/1'];
    el.setAttribute('catalog', 'veille');
    el.setAttribute('sidebar-dropdown', '');

    el.render();

    expect(el.shadowRoot.querySelector('.agent-launch-link')).toBeTruthy();
    expect(el.shadowRoot.querySelector('.agents-stored-list ntx-sidebar-link-item')).toBeTruthy();
  });

  it('dispatches router navigation for built-in entry clicks when router is configured', () => {
    const el = document.createElement('ntx-agents');
    el.model = 'AgentActor';
    el.schema = makeSchema();
    el.value = [];
    el.setAttribute('catalog', 'veille');
    el.setAttribute('router', 'main');
    el.send = vi.fn();

    el.render();
    el.shadowRoot.querySelector('.agent-launch-card[data-route="grants"]')?.click();

    expect(el.send).toHaveBeenCalledTimes(1);
    const tx = el.send.mock.calls[0][0];
    expect(tx?.name).toBe('NAVIGATE');
    expect(tx?.target).toBe('main');
    expect(tx?.data).toBe('grants');
  });
});
