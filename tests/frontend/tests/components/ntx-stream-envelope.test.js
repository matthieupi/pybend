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
vi.mock('../../utils/Toast.js', () => ({
  showToast: vi.fn()
}));

import { NTTStream } from '../../components/ntx-stream.js';

class TestStreamElement extends NTTStream {
  constructor() {
    super();
    this.events = [];
  }
  TEXT(data) { this.events.push(['TEXT', data]); }
  STREAM_END(data) { this.events.push(['STREAM_END', data]); }
  STREAM_ERROR(data) { this.events.push(['STREAM_ERROR', data]); }
}

if (!customElements.get('test-ntx-stream-envelope')) {
  customElements.define('test-ntx-stream-envelope', TestStreamElement);
}

describe('NTTStream wrapped stream envelope handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('treats wrapped done envelopes as stream termination instead of plain chunks', () => {
    const el = new TestStreamElement();

    el.STREAM(
      { name: 'STREAM', data: { name: 'done', data: { answer: 'ok' }, meta: { stream_end: true, seq: 2 } }, meta: { stream_end: true, seq: 2 } },
      { meta: { stream: true, req: 'req-1' } },
    );

    expect(el.events).toContainEqual(['STREAM_END', { answer: 'ok' }]);
  });

  it('treats wrapped error envelopes as stream errors instead of text chunks', () => {
    const el = new TestStreamElement();

    el.STREAM(
      { name: 'STREAM', data: { name: 'error', data: { message: 'Invalid JSON' }, meta: { error: true, seq: 3 } }, meta: { error: true, seq: 3 } },
      { meta: { stream: true, req: 'req-1' } },
    );

    expect(el.events).toContainEqual(['STREAM_ERROR', { message: 'Invalid JSON' }]);
  });

  it('does not render the fallback stream output box by default', () => {
    const el = new TestStreamElement();

    NTTStream.prototype.TEXT.call(el, { text: 'hello' });

    expect(el.shadowRoot.querySelector('.stream-output')).toBeNull();
  });

  it('renders the fallback stream output box when show-output is enabled', () => {
    const el = new TestStreamElement();
    el.setAttribute('show-output', '');

    NTTStream.prototype.TEXT.call(el, { text: 'hello' });

    const output = el.shadowRoot.querySelector('.stream-output');
    expect(output).toBeTruthy();
    expect(output.textContent).toContain('hello');
  });
});
