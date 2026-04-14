import { describe, it, expect, vi, afterEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => { if (!cond) throw new Error(msg || 'Assertion failed'); }),
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
    canAction: vi.fn(() => false),
    canView: vi.fn(() => true),
    canEdit: vi.fn(() => false),
    user: null,
    authenticated: false,
    role: 'anonymous',
    init: vi.fn(() => Promise.resolve(null)),
  }
}));

await import('../../components/ntx-sidebar.js');

function createSidebarLinkItem(schema, value) {
  const Ctor = customElements.get('ntx-sidebar-link-item');
  expect(Ctor).toBeTruthy();
  const el = document.createElement('ntx-sidebar-link-item');
  el.schema = schema;
  Object.defineProperty(el, '_testValue', { value, writable: true });
  Object.defineProperty(el, 'value', {
    get() { return this._testValue; },
    set(v) { this._testValue = v; },
    configurable: true,
  });
  return el;
}

function renderSidebarLinkItem(schema, value) {
  const el = createSidebarLinkItem(schema, value);
  el.setAttribute('display', 'sm');
  document.body.appendChild(el);
  el.render();
  return el;
}

afterEach(() => {
  vi.useRealTimers();
  document.querySelectorAll('.ntx-sidebar-link-tooltip').forEach((el) => el.remove());
  document.body.querySelectorAll('ntx-sidebar-link-item').forEach((el) => el.remove());
});

describe('ntx-sidebar-link-item.js', () => {
  it('should register the sidebar link item custom element', () => {
    const Ctor = customElements.get('ntx-sidebar-link-item');
    expect(Ctor).toBeTruthy();
  });

  it('should render a real detail anchor for named records', () => {
    const el = createSidebarLinkItem(
      { __name__: 'Grant', properties: {}, access: {}, methods: {} },
      { id: 5, name: 'Energy Grant' },
    );

    const html = el.sm();
    expect(html).toContain('<a');
    expect(html).toContain('href="#Grant/5"');
    expect(html).toContain('aria-label="Energy Grant"');
    expect(html).toContain('data-tooltip="Energy Grant"');
    expect(html).toContain('Energy Grant');
  });

  it('should fall back to title when name is missing', () => {
    const el = createSidebarLinkItem(
      { __name__: 'Source', properties: {}, access: {}, methods: {} },
      { id: 3, title: 'Funding Feed' },
    );

    const html = el.sm();
    expect(html).toContain('href="#Source/3"');
    expect(html).toContain('data-tooltip="Funding Feed"');
    expect(html).toContain('Funding Feed');
  });

  it('should escape tooltip attributes for quoted labels', () => {
    const el = createSidebarLinkItem(
      { __name__: 'Grant', properties: {}, access: {}, methods: {} },
      { id: 9, title: 'Alpha "Beta" <Gamma>' },
    );

    const html = el.sm();
    expect(html).toContain('data-tooltip="Alpha &quot;Beta&quot; &lt;Gamma&gt;"');
    expect(html).toContain('Alpha "Beta" &lt;Gamma&gt;');
  });

  it('should show the custom tooltip after a shorter hover delay for truncated labels', () => {
    vi.useFakeTimers();

    const el = renderSidebarLinkItem(
      { __name__: 'Grant', properties: {}, access: {}, methods: {} },
      { id: 12, title: 'A very long grant title that does not fit in the sidebar row' },
    );

    const link = el.shadowRoot.querySelector('.sidebar-record-link');
    const label = el.shadowRoot.querySelector('.sidebar-record-label');
    Object.defineProperty(label, 'scrollWidth', { configurable: true, value: 240 });
    Object.defineProperty(label, 'clientWidth', { configurable: true, value: 72 });

    link.dispatchEvent(new MouseEvent('mouseenter'));
    vi.advanceTimersByTime(219);
    expect(document.querySelector('.ntx-sidebar-link-tooltip')).toBeNull();

    vi.advanceTimersByTime(1);
    const tooltip = document.querySelector('.ntx-sidebar-link-tooltip');
    expect(tooltip).toBeTruthy();
    expect(tooltip.textContent).toContain('A very long grant title');
    expect(tooltip.style.visibility).toBe('visible');

    link.dispatchEvent(new MouseEvent('mouseleave'));
    expect(tooltip.style.visibility).toBe('hidden');
  });

  it('should skip the tooltip when the label fits without truncation', () => {
    vi.useFakeTimers();

    const el = renderSidebarLinkItem(
      { __name__: 'Source', properties: {}, access: {}, methods: {} },
      { id: 4, title: 'Short title' },
    );

    const link = el.shadowRoot.querySelector('.sidebar-record-link');
    const label = el.shadowRoot.querySelector('.sidebar-record-label');
    Object.defineProperty(label, 'scrollWidth', { configurable: true, value: 60 });
    Object.defineProperty(label, 'clientWidth', { configurable: true, value: 120 });

    link.dispatchEvent(new MouseEvent('mouseenter'));
    vi.advanceTimersByTime(250);

    expect(document.querySelector('.ntx-sidebar-link-tooltip')).toBeNull();
  });
});
