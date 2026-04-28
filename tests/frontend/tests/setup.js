/**
 * Test setup file — provides common mocks for jsdom environment.
 *
 * Mocks: localStorage, fetch, CustomElements, ShadowDOM, ResizeObserver,
 *        location, WebSocket, import.meta.url, window globals
 */

// ── localStorage Mock ──
// Uses a Proxy to support both .getItem()/.setItem() and bracket-access
// patterns (e.g. window.localStorage['jwtToken'] used by HTTP.js).
const store = {};
const localStorageMock = {
  getItem: vi.fn((key) => store[key] ?? null),
  setItem: vi.fn((key, value) => { store[key] = String(value); }),
  removeItem: vi.fn((key) => { delete store[key]; }),
  clear: vi.fn(() => { Object.keys(store).forEach(k => delete store[k]); }),
  get length() { return Object.keys(store).length; },
  key: vi.fn((i) => Object.keys(store)[i] ?? null),
};
const localStorageProxy = new Proxy(localStorageMock, {
  get(target, prop) {
    if (prop in target) return target[prop];
    return store[prop] ?? undefined;
  },
  set(target, prop, value) {
    if (prop in target) { target[prop] = value; return true; }
    store[prop] = String(value);
    return true;
  },
  deleteProperty(target, prop) {
    delete store[prop];
    return true;
  }
});
Object.defineProperty(window, 'localStorage', { value: localStorageProxy, writable: true });

// ── fetch Mock ──
global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
    text: () => Promise.resolve(''),
  })
);

// ── ResizeObserver Mock ──
class ResizeObserverMock {
  constructor(callback) {
    this._callback = callback;
    this._targets = [];
  }
  observe(target) {
    this._targets.push(target);
  }
  unobserve(target) {
    this._targets = this._targets.filter(t => t !== target);
  }
  disconnect() {
    this._targets = [];
  }
  // Helper for tests to trigger resize
  _trigger(entries) {
    this._callback(entries, this);
  }
}
global.ResizeObserver = ResizeObserverMock;

// ── URL Mock ──
// jsdom provides URL but import.meta.url may not work in tests
if (!global.URL) {
  global.URL = URL;
}

// ── WebSocket Mock ──
class WebSocketMock {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances = new Set();

  constructor(url) {
    this.url = url;
    this.readyState = WebSocketMock.CONNECTING;
    this.onopen = null;
    this.onclose = null;
    this.onmessage = null;
    this.onerror = null;
    this._sent = [];
    WebSocketMock.instances.add(this);
  }
  send(data) { this._sent.push(data); }
  close(code, reason) {
    this.readyState = WebSocketMock.CLOSED;
    WebSocketMock.instances.delete(this);
  }

  static closeAll() {
    for (const socket of Array.from(WebSocketMock.instances)) {
      socket.close();
    }
    WebSocketMock.instances.clear();
  }
}
global.WebSocket = WebSocketMock;

// ── location Mock helpers ──
// jsdom provides location but we may need to reset it between tests

// ── window globals used by Socket.js ──
window.success = vi.fn();
window.warn = vi.fn();
window.error = vi.fn();

// ── console suppression (optional — prevent noisy test output) ──
// Uncomment if needed:
// vi.spyOn(console, 'log').mockImplementation(() => {});
// vi.spyOn(console, 'warn').mockImplementation(() => {});
// vi.spyOn(console, 'info').mockImplementation(() => {});

// ── Unhandled rejection listener ──
// Captures leaked promise rejections from stale module state after
// vi.resetModules(). These are infrastructure leaks, not test bugs.
// Logged but not surfaced as test failures.
const _unhandledRejections = [];
process.on('unhandledRejection', (reason) => {
  _unhandledRejections.push(reason);
});

// ── Cleanup between tests ──
beforeEach(() => {
  _unhandledRejections.length = 0;

  // Clear localStorage
  Object.keys(store).forEach(k => delete store[k]);
  localStorageMock.getItem.mockClear();
  localStorageMock.setItem.mockClear();
  localStorageMock.removeItem.mockClear();
  localStorageMock.clear.mockClear();
  localStorageMock.key.mockClear();

  // Clear browser storage backed by jsdom.
  window.sessionStorage?.clear?.();

  // Clear fetch
  global.fetch.mockClear();
  global.fetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
    text: () => Promise.resolve(''),
  });
});

afterEach(async () => {
  // Give pending promise callbacks a chance to surface unhandled rejections
  // before the next test starts.
  await Promise.resolve();
  await new Promise(resolve => queueMicrotask(resolve));

  const leakedRejection = _unhandledRejections.shift();
  _unhandledRejections.length = 0;

  // Remove neutral browser/runtime state that should not survive tests.
  WebSocketMock.closeAll();
  document.body.replaceChildren();
  window.sessionStorage?.clear?.();

  try {
    vi.clearAllTimers();
  } finally {
    vi.useRealTimers();
  }

  // Restore all mocks to prevent leaked callbacks between tests
  vi.restoreAllMocks();

  // Re-establish fetch mock (restoreAllMocks clears it)
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve(''),
    })
  );

  // Re-establish window globals
  window.success = vi.fn();
  window.warn = vi.fn();
  window.error = vi.fn();

  if (leakedRejection) {
    throw leakedRejection instanceof Error
      ? leakedRejection
      : new Error(String(leakedRejection));
  }
});
