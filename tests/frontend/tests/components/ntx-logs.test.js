import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../config.js', () => ({
  config: { LOGGING: 3, LOGEVENTS: false, DEBUG: false, API_URL: 'http://localhost:5000' }
}));
vi.mock('../../utils/Logging.js', () => {
  let listeners = [];
  let entries = [];
  return {
    default: {
      addListener: vi.fn((fn) => listeners.push(fn)),
      removeListener: vi.fn((fn) => { listeners = listeners.filter(f => f !== fn); }),
      getEntries: vi.fn(() => entries.slice()),
      get size() { return entries.length; },
      clear: vi.fn(() => {
        entries = [];
        listeners.forEach(fn => fn());
      }),
      error: vi.fn((msg, detail) => {
        const e = { level: 'error', message: msg, detail, timestamp: Date.now() };
        entries.push(e);
        listeners.forEach(fn => fn(e));
      }),
      warn: vi.fn((msg, detail) => {
        const e = { level: 'warn', message: msg, detail, timestamp: Date.now() };
        entries.push(e);
        listeners.forEach(fn => fn(e));
      }),
      debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn(),
    }
  };
});

// Import after mocks
await import('../../../../examples/core/static/components/ntx-logs.js');
const Logging = (await import('../../utils/Logging.js')).default;

describe('ntx-logs.js (NTTLogs)', () => {

  describe('custom element registration', () => {
    it('should be registered as ntx-logs', () => {
      expect(customElements.get('ntx-logs')).toBeTruthy();
    });
  });

  describe('constructor', () => {
    it('should create shadow DOM', () => {
      const el = document.createElement('ntx-logs');
      expect(el.shadowRoot).toBeTruthy();
    });
  });

  describe('connectedCallback', () => {
    it('should render toggle button and panel', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      const toggle = el.shadowRoot.querySelector('.toggle');
      expect(toggle).toBeTruthy();
      const panel = el.shadowRoot.querySelector('.panel');
      expect(panel).toBeTruthy();
      document.body.removeChild(el);
    });

    it('should render filter buttons for all levels', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      const filters = el.shadowRoot.querySelectorAll('.filter-btn');
      expect(filters.length).toBe(6); // error, warn, info, event, debug, dev
      document.body.removeChild(el);
    });

    it('should have clear button', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      const clearBtn = el.shadowRoot.querySelector('.clear-btn');
      expect(clearBtn).toBeTruthy();
      document.body.removeChild(el);
    });

    it('should subscribe to Logging.addListener', () => {
      Logging.addListener.mockClear();
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      expect(Logging.addListener).toHaveBeenCalled();
      document.body.removeChild(el);
    });

    it('should have a badge element showing 0 initially', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      const badge = el.shadowRoot.querySelector('.badge');
      expect(badge).toBeTruthy();
      expect(badge.textContent).toBe('0');
      document.body.removeChild(el);
    });
  });

  describe('disconnectedCallback', () => {
    it('should remove listener', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      Logging.removeListener.mockClear();
      document.body.removeChild(el);
      expect(Logging.removeListener).toHaveBeenCalled();
    });
  });

  describe('panel toggle', () => {
    it('should open panel when toggle button is clicked', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      const toggle = el.shadowRoot.querySelector('.toggle');
      const panel = el.shadowRoot.querySelector('.panel');
      toggle.click();
      expect(panel.classList.contains('open')).toBe(true);
      document.body.removeChild(el);
    });

    it('should close panel when close button is clicked', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      const toggle = el.shadowRoot.querySelector('.toggle');
      toggle.click(); // open
      const closeBtn = el.shadowRoot.querySelector('.close-btn');
      closeBtn.click(); // close
      const panel = el.shadowRoot.querySelector('.panel');
      expect(panel.classList.contains('open')).toBe(false);
      document.body.removeChild(el);
    });
  });

  describe('filter toggle', () => {
    it('should activate filter button on click', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      const errorBtn = el.shadowRoot.querySelector('.filter-btn[data-level="error"]');
      errorBtn.click();
      expect(errorBtn.classList.contains('active')).toBe(true);
      document.body.removeChild(el);
    });

    it('should deactivate filter on second click (toggle off)', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      const errorBtn = el.shadowRoot.querySelector('.filter-btn[data-level="error"]');
      errorBtn.click(); // activate
      errorBtn.click(); // deactivate
      expect(errorBtn.classList.contains('active')).toBe(false);
      document.body.removeChild(el);
    });

    it('should deactivate previous filter when new one is clicked', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      const errorBtn = el.shadowRoot.querySelector('.filter-btn[data-level="error"]');
      const warnBtn = el.shadowRoot.querySelector('.filter-btn[data-level="warn"]');
      errorBtn.click();
      warnBtn.click();
      expect(errorBtn.classList.contains('active')).toBe(false);
      expect(warnBtn.classList.contains('active')).toBe(true);
      document.body.removeChild(el);
    });
  });

  describe('clear button', () => {
    it('should call Logging.clear when clicked', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      Logging.clear.mockClear();
      const clearBtn = el.shadowRoot.querySelector('.clear-btn');
      clearBtn.click();
      expect(Logging.clear).toHaveBeenCalled();
      document.body.removeChild(el);
    });
  });

  describe('entry appending', () => {
    it('should append an entry to the log list when open and an error is logged', () => {
      const el = document.createElement('ntx-logs');
      document.body.appendChild(el);
      el.shadowRoot.querySelector('.toggle').click();

      Logging.error('Test error', 'detail');
      const entries = el.shadowRoot.querySelectorAll('.entry');
      expect(entries.length).toBeGreaterThan(0);
      const lastEntry = entries[entries.length - 1];
      expect(lastEntry.classList.contains('level-error')).toBe(true);
      document.body.removeChild(el);
    });
  });
});
