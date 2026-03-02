import Logging from '../utils/Logging.js';

const LEVEL_COLORS = {
  error: '#ff5555',
  warn:  '#ffb86c',
  info:  '#8be9fd',
  event: '#bd93f9',
  debug: '#6272a4',
  dev:   '#50fa7b',
};

const LEVELS = ['error', 'warn', 'info', 'event', 'debug', 'dev'];
const COLLAPSE_THRESHOLD = 120;

class NTTLogs extends HTMLElement {
  #open = false;
  #filter = null;
  #panel;
  #badge;
  #list;
  #listener = null;
  #counts = Object.fromEntries(LEVELS.map(l => [l, 0]));
  #rendered = false;  // true once the log list has been populated

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.shadowRoot.innerHTML = `
      <style>${NTTLogs.styles}</style>
      <button class="toggle" title="Toggle log viewer">
        <span class="icon">&#9776;</span>
        <span class="badge">0</span>
      </button>
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">Logs</span>
          <button class="close-btn" title="Close">&times;</button>
        </div>
        <div class="toolbar">
          <div class="filters">
            ${LEVELS.map(l => `<button class="filter-btn" data-level="${l}" style="--lvl:${LEVEL_COLORS[l]}">${l} <span class="filter-count" data-count-level="${l}"></span></button>`).join('')}
          </div>
          <button class="clear-btn" title="Clear logs">Clear</button>
        </div>
        <div class="log-list"></div>
      </div>
    `;

    this.#panel = this.shadowRoot.querySelector('.panel');
    this.#badge = this.shadowRoot.querySelector('.badge');
    this.#list  = this.shadowRoot.querySelector('.log-list');

    // Toggle side panel open
    this.shadowRoot.querySelector('.toggle').addEventListener('click', () => {
      this.#setOpen(true);
    });

    // Close button
    this.shadowRoot.querySelector('.close-btn').addEventListener('click', () => {
      this.#setOpen(false);
    });

    // Filter buttons
    this.shadowRoot.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const level = btn.dataset.level;
        if (this.#filter === level) {
          this.#filter = null;
          btn.classList.remove('active');
        } else {
          this.shadowRoot.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
          this.#filter = level;
          btn.classList.add('active');
        }
        this.#applyFilter();
        for (const l of LEVELS) this.#updateCount(l);
      });
    });

    // Clear
    this.shadowRoot.querySelector('.clear-btn').addEventListener('click', () => {
      Logging.clear();
    });

    // Delegate click for expand/collapse and JSON toggles
    this.#list.addEventListener('click', (e) => {
      const expandBtn = e.target.closest('.expand-btn');
      if (expandBtn) {
        const entry = expandBtn.closest('.entry');
        entry.classList.toggle('expanded');
        expandBtn.textContent = entry.classList.contains('expanded') ? 'less' : 'more';
        return;
      }
      const jsonToggle = e.target.closest('.json-toggle');
      if (jsonToggle) {
        const block = jsonToggle.closest('.json-node');
        block.classList.toggle('collapsed');
      }
    });

    // Subscribe to new entries via listener.
    // While the panel is closed we only update the badge counter —
    // actual DOM entries are created lazily when the panel opens.
    this.#listener = (entry) => {
      this.#badge.textContent = Logging.size;
      if (entry) {
        // Track counts even while closed (for filter badges)
        if (entry.level in this.#counts) this.#counts[entry.level]++;
        // Only append DOM when the panel is already open and rendered
        if (this.#open && this.#rendered) {
          this.#appendEntry(entry, false);  // skip count — already incremented
          this.#scrollToBottom();
        }
      } else {
        // clear event
        this.#list.innerHTML = '';
        this.#badge.textContent = '0';
        this.#rendered = false;
        this.#resetCounts();
      }
    };
    Logging.addListener(this.#listener);

    // Just set the badge — don't render entries yet
    queueMicrotask(() => {
      // Count existing entries for filter badges
      for (const entry of Logging.getEntries()) {
        if (entry.level in this.#counts) this.#counts[entry.level]++;
      }
      this.#badge.textContent = Logging.size;
    });
  }

  disconnectedCallback() {
    if (this.#listener) {
      Logging.removeListener(this.#listener);
      this.#listener = null;
    }
  }

  #setOpen(open) {
    this.#open = open;
    this.#panel.classList.toggle('open', open);
    if (open) {
      if (!this.#rendered) this.#renderEntries();
      this.#scrollToBottom();
    }
  }

  /** Populate the log list DOM from the Logging buffer. Called once on first open. */
  #renderEntries() {
    this.#list.innerHTML = '';
    const existing = Logging.getEntries();
    const frag = document.createDocumentFragment();
    for (const entry of existing) {
      frag.appendChild(this.#createEntryEl(entry));
    }
    this.#list.appendChild(frag);
    for (const l of LEVELS) this.#updateCount(l);
    this.#rendered = true;
  }

  #scrollToBottom() {
    this.#list.scrollTop = this.#list.scrollHeight;
  }

  #updateCount(level) {
    const el = this.shadowRoot.querySelector(`.filter-count[data-count-level="${level}"]`);
    if (el) el.textContent = this.#counts[level];
  }

  #resetCounts() {
    for (const l of LEVELS) { this.#counts[l] = 0; this.#updateCount(l); }
  }

  /** Hide/show entries based on active filter — no DOM rebuild */
  #applyFilter() {
    const entries = this.#list.children;
    for (const el of entries) {
      if (!this.#filter || el.dataset.level === this.#filter) {
        el.style.display = '';
      } else {
        el.style.display = 'none';
      }
    }
  }

  /** Create a DOM element for a log entry (without appending). */
  #createEntryEl(entry) {
    const el = document.createElement('div');
    el.className = `entry level-${entry.level}`;
    el.dataset.level = entry.level;

    if (this.#filter && entry.level !== this.#filter) {
      el.style.display = 'none';
    }

    const time = new Date(entry.timestamp).toLocaleTimeString('en-US', { hour12: false });
    const msgContent = this.#formatContent(entry.message);
    const detailContent = entry.detail != null ? this.#formatContent(entry.detail) : '';

    el.innerHTML =
      `<div class="entry-header">` +
        `<span class="level-dot" style="background:${LEVEL_COLORS[entry.level]}"></span>` +
        `<span class="time">${time}</span>` +
        `<span class="level" style="color:${LEVEL_COLORS[entry.level]}">${entry.level}</span>` +
      `</div>` +
      `<div class="entry-body">${msgContent}${detailContent ? '<div class="detail">' + detailContent + '</div>' : ''}</div>`;

    return el;
  }

  /**
   * Append a single entry to the live DOM list.
   * @param {Object} entry
   * @param {boolean} trackCount — false when count was already incremented by the listener
   */
  #appendEntry(entry, trackCount = true) {
    if (trackCount && entry.level in this.#counts) {
      this.#counts[entry.level]++;
    }
    this.#list.appendChild(this.#createEntryEl(entry));
  }

  /** Format a value for display — handles JSON objects, long strings, etc. */
  #formatContent(value) {
    if (value == null) return '';

    // Object/Array → JSON tree
    if (typeof value === 'object') {
      return this.#renderJson(value);
    }

    const str = String(value);

    // String that looks like JSON → parse and render as tree
    if ((str.startsWith('{') || str.startsWith('[')) && str.length > 2) {
      try {
        const parsed = JSON.parse(str);
        return this.#renderJson(parsed);
      } catch { /* not JSON, render as text */ }
    }

    // Long strings → collapsible
    if (str.length > COLLAPSE_THRESHOLD) {
      const preview = this.#esc(str.slice(0, COLLAPSE_THRESHOLD));
      const full = this.#esc(str);
      return `<span class="collapsible"><span class="preview">${preview}</span><span class="full">${full}</span> <button class="expand-btn">more</button></span>`;
    }

    return `<span class="text">${this.#esc(str)}</span>`;
  }

  /** Render a JSON value as a collapsible, syntax-highlighted tree */
  #renderJson(value, depth = 0) {
    if (depth > 8) return '<span class="json-str">"[max depth]"</span>';
    if (value === null) return '<span class="json-null">null</span>';
    if (typeof value === 'boolean') return `<span class="json-bool">${value}</span>`;
    if (typeof value === 'number') return `<span class="json-num">${value}</span>`;
    if (typeof value === 'string') return `<span class="json-str">"${this.#esc(value)}"</span>`;

    if (Array.isArray(value)) {
      if (value.length === 0) return '<span class="json-bracket">[]</span>';
      const items = value.map(v => `<div class="json-item">${this.#renderJson(v, depth + 1)}</div>`).join('');
      const collapsed = depth > 0 ? ' collapsed' : '';
      return `<span class="json-node${collapsed}"><span class="json-toggle json-bracket">[${value.length}]</span><div class="json-children">${items}</div></span>`;
    }

    if (typeof value === 'object') {
      const keys = Object.keys(value);
      if (keys.length === 0) return '<span class="json-bracket">{}</span>';
      const items = keys.map(k =>
        `<div class="json-item"><span class="json-key">${this.#esc(k)}</span>: ${this.#renderJson(value[k], depth + 1)}</div>`
      ).join('');
      const preview = keys.slice(0, 3).join(', ') + (keys.length > 3 ? ', ...' : '');
      const collapsed = depth > 0 ? ' collapsed' : '';
      return `<span class="json-node${collapsed}"><span class="json-toggle json-bracket">{${this.#esc(preview)}}</span><div class="json-children">${items}</div></span>`;
    }

    return this.#esc(String(value));
  }

  #esc(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  static styles = `
    :host {
      position: fixed;
      bottom: 1rem;
      right: 1rem;
      z-index: 99999;
      font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
      font-size: 12px;
    }

    /* ── Toggle Button ── */
    .toggle {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      border: 1px solid var(--border, #444);
      background: var(--glass-bg, rgba(30,30,30,0.85));
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      color: var(--text-0, #eee);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
    }
    .toggle:hover { border-color: var(--accent, #22d3c5); }
    .icon { font-size: 16px; }
    .badge {
      position: absolute;
      top: -4px;
      right: -4px;
      background: var(--accent, #22d3c5);
      color: var(--surface-0, #08090c);
      border-radius: 8px;
      padding: 0 5px;
      font-size: 10px;
      min-width: 16px;
      text-align: center;
      line-height: 16px;
      font-weight: 700;
    }

    /* ── Side Panel ── */
    .panel {
      position: fixed;
      top: 0;
      right: 0;
      width: min(480px, 85vw);
      height: 100vh;
      background: var(--surface-1, #0e1018);
      border-left: 1px solid var(--border, rgba(255,255,255,0.07));
      display: flex;
      flex-direction: column;
      transform: translateX(100%);
      transition: transform 0.2s ease;
      box-shadow: -4px 0 24px rgba(0,0,0,0.4);
    }
    .panel.open {
      transform: translateX(0);
    }

    /* ── Panel Header ── */
    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border, rgba(255,255,255,0.07));
      background: var(--surface-2, #151822);
      flex-shrink: 0;
    }
    .panel-title {
      font-weight: 700;
      font-size: 14px;
      color: var(--text-0, #f0f2f8);
      letter-spacing: 0.02em;
    }
    .close-btn {
      background: none;
      border: 1px solid var(--border, #444);
      color: var(--text-2, #8891ab);
      width: 28px;
      height: 28px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 18px;
      line-height: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: color 0.1s, border-color 0.1s;
    }
    .close-btn:hover {
      color: var(--text-0, #f0f2f8);
      border-color: var(--text-2, #8891ab);
    }

    /* ── Toolbar ── */
    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      border-bottom: 1px solid var(--border, rgba(255,255,255,0.07));
      gap: 6px;
      flex-shrink: 0;
      background: var(--surface-1, #0e1018);
    }
    .filters { display: flex; gap: 4px; flex-wrap: wrap; }
    .filter-btn {
      background: transparent;
      border: 1px solid var(--lvl);
      color: var(--lvl);
      border-radius: 4px;
      padding: 2px 8px;
      cursor: pointer;
      font-size: 11px;
      text-transform: uppercase;
      opacity: 0.5;
      transition: opacity 0.1s;
    }
    .filter-btn:hover { opacity: 0.85; }
    .filter-btn.active { background: var(--lvl); color: var(--surface-0, #08090c); opacity: 1; font-weight: 700; }
    .filter-count {
      font-size: 10px;
      opacity: 0.7;
      margin-left: 2px;
      font-weight: 600;
    }
    .filter-btn.active .filter-count { opacity: 0.9; }
    .clear-btn {
      background: transparent;
      border: 1px solid var(--border, #444);
      color: var(--text-2, #8891ab);
      border-radius: 4px;
      padding: 2px 8px;
      cursor: pointer;
      font-size: 11px;
      flex-shrink: 0;
    }
    .clear-btn:hover { color: #ff5555; border-color: #ff5555; }

    /* ── Log List ── */
    .log-list {
      overflow-y: auto;
      flex: 1;
      padding: 0;
    }

    /* ── Entry ── */
    .entry {
      padding: 6px 12px 6px 14px;
      border-bottom: 1px solid var(--border, rgba(255,255,255,0.04));
      border-left: 3px solid transparent;
      transition: background 0.1s;
    }
    .entry:hover { background: var(--surface-2, rgba(255,255,255,0.03)); }

    /* ── Level color-coding on entries ── */
    .entry.level-error  { border-left-color: ${LEVEL_COLORS.error}; background: rgba(255, 85, 85, 0.05); }
    .entry.level-warn   { border-left-color: ${LEVEL_COLORS.warn};  background: rgba(255,184,108, 0.04); }
    .entry.level-info   { border-left-color: ${LEVEL_COLORS.info}; }
    .entry.level-event  { border-left-color: ${LEVEL_COLORS.event}; }
    .entry.level-debug  { border-left-color: ${LEVEL_COLORS.debug}; }
    .entry.level-dev    { border-left-color: ${LEVEL_COLORS.dev}; }

    .entry.level-error:hover { background: rgba(255, 85, 85, 0.09); }
    .entry.level-warn:hover  { background: rgba(255,184,108, 0.08); }

    .entry-header {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 2px;
    }
    .level-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .time { color: var(--text-3, #555e78); white-space: nowrap; font-size: 11px; }
    .level { font-weight: 700; text-transform: uppercase; font-size: 10px; letter-spacing: 0.04em; }
    .entry-body { color: var(--text-1, #c4c9da); line-height: 1.5; word-break: break-word; padding-left: 14px; }
    .detail { margin-top: 4px; padding-left: 8px; border-left: 2px solid var(--border, rgba(255,255,255,0.07)); }

    /* ── Collapsible long text ── */
    .collapsible .full { display: none; }
    .entry.expanded .collapsible .preview { display: none; }
    .entry.expanded .collapsible .full { display: inline; }
    .expand-btn {
      background: none;
      border: none;
      color: var(--accent, #22d3c5);
      cursor: pointer;
      font-size: 11px;
      padding: 0 2px;
      font-family: inherit;
      opacity: 0.8;
    }
    .expand-btn:hover { opacity: 1; text-decoration: underline; }

    /* ── JSON Tree ── */
    .json-node { display: inline; }
    .json-children {
      display: block;
      padding-left: 16px;
      border-left: 1px solid var(--border, rgba(255,255,255,0.06));
      margin-left: 2px;
    }
    .json-node.collapsed > .json-children { display: none; }
    .json-toggle {
      cursor: pointer;
      user-select: none;
    }
    .json-toggle:hover { opacity: 0.8; }
    .json-item { line-height: 1.6; }
    .json-bracket { color: var(--text-3, #555e78); }
    .json-key { color: var(--accent-text, #5eeadf); }
    .json-str { color: #f1fa8c; }
    .json-num { color: #bd93f9; }
    .json-bool { color: #ff79c6; }
    .json-null { color: var(--text-3, #555e78); font-style: italic; }
    .text { color: var(--text-1, #c4c9da); }
  `;
}

customElements.define('ntt-logs', NTTLogs);
