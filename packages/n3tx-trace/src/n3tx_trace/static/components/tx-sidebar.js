/**
 * tx-sidebar.js — Scrollable TX list with hover/click interaction.
 *
 * Events emitted:
 *   tx-hover   { detail: { entry } }      — hover over a TX entry
 *   tx-select  { detail: { trace_id } }   — click on a TX entry
 *   tx-clear   { detail: {} }             — clear selection
 */

class TxSidebar extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this._entries = [];
        this._filter = '';
        this._selectedTraceId = null;
        this._autoScroll = true;
        this._maxEntries = 2000;
    }

    connectedCallback() {
        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                    overflow: hidden;
                    font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
                    font-size: 12px;
                    color: #e6edf3;
                }
                .header {
                    padding: 8px 12px;
                    border-bottom: 1px solid #30363d;
                    background: #1c2128;
                }
                .header h3 {
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    color: #8b949e;
                    margin-bottom: 6px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .count {
                    font-weight: 400;
                    color: #6e7681;
                }
                input {
                    width: 100%;
                    padding: 4px 8px;
                    background: #0d1117;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    color: #e6edf3;
                    font-family: inherit;
                    font-size: 12px;
                    outline: none;
                }
                input:focus { border-color: #58a6ff; }
                .toolbar {
                    display: flex;
                    gap: 4px;
                    margin-top: 6px;
                }
                button {
                    padding: 2px 8px;
                    background: transparent;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    color: #8b949e;
                    cursor: pointer;
                    font-family: inherit;
                    font-size: 11px;
                }
                button:hover { border-color: #58a6ff; color: #e6edf3; }
                .list {
                    flex: 1;
                    overflow-y: auto;
                    overflow-x: hidden;
                }
                .entry {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 4px 12px;
                    border-bottom: 1px solid rgba(48, 54, 61, 0.5);
                    cursor: pointer;
                    transition: background 0.1s;
                    white-space: nowrap;
                    overflow: hidden;
                }
                .entry:hover { background: #1c2128; }
                .entry.selected {
                    background: rgba(88, 166, 255, 0.1);
                    border-left: 2px solid #58a6ff;
                }
                .entry.dimmed { opacity: 0.3; }
                .time {
                    color: #6e7681;
                    font-size: 11px;
                    min-width: 55px;
                }
                .name { font-weight: 500; }
                .name.error { color: #f85149; }
                .name.stream { color: #39d4c5; }
                .route {
                    color: #8b949e;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    flex: 1;
                }
                .arrow { color: #6e7681; margin: 0 2px; }
            </style>
            <div class="header">
                <h3>Transactions <span class="count">0</span></h3>
                <input type="text" placeholder="Filter..." />
                <div class="toolbar">
                    <button class="btn-clear">Clear</button>
                    <button class="btn-scroll">Auto-scroll: ON</button>
                </div>
            </div>
            <div class="list"></div>
        `;

        this._listEl = this.shadowRoot.querySelector('.list');
        this._countEl = this.shadowRoot.querySelector('.count');
        this._filterInput = this.shadowRoot.querySelector('input');
        this._btnClear = this.shadowRoot.querySelector('.btn-clear');
        this._btnScroll = this.shadowRoot.querySelector('.btn-scroll');

        this._filterInput.addEventListener('input', () => {
            this._filter = this._filterInput.value.toLowerCase();
            this._renderList();
        });

        this._btnClear.addEventListener('click', () => {
            this._selectedTraceId = null;
            this._renderList();
            this.dispatchEvent(new CustomEvent('tx-clear', { bubbles: true }));
        });

        this._btnScroll.addEventListener('click', () => {
            this._autoScroll = !this._autoScroll;
            this._btnScroll.textContent = `Auto-scroll: ${this._autoScroll ? 'ON' : 'OFF'}`;
        });

        // Detect manual scroll
        this._listEl.addEventListener('scroll', () => {
            const el = this._listEl;
            const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
            if (!atBottom && this._autoScroll) {
                this._autoScroll = false;
                this._btnScroll.textContent = 'Auto-scroll: OFF';
            }
        });
    }

    addEntry(entry) {
        this._entries.push(entry);
        if (this._entries.length > this._maxEntries) {
            this._entries.shift();
        }
        this._countEl.textContent = this._entries.length;

        // Fast path: if no filter and no selection, just append
        if (!this._filter && !this._selectedTraceId) {
            this._appendEntryEl(entry);
        } else if (this._matchesFilter(entry)) {
            this._appendEntryEl(entry);
        }
    }

    loadEntries(entries) {
        this._entries = entries;
        this._countEl.textContent = this._entries.length;
        this._renderList();
    }

    _matchesFilter(entry) {
        if (!this._filter) return true;
        const text = `${entry.name} ${entry.source} ${entry.target} ${entry.trace_id}`.toLowerCase();
        return text.includes(this._filter);
    }

    _renderList() {
        this._listEl.innerHTML = '';
        for (const entry of this._entries) {
            if (this._matchesFilter(entry)) {
                this._appendEntryEl(entry);
            }
        }
    }

    _appendEntryEl(entry) {
        const el = document.createElement('div');
        el.className = 'entry';

        if (this._selectedTraceId) {
            if (entry.trace_id === this._selectedTraceId) {
                el.classList.add('selected');
            } else {
                el.classList.add('dimmed');
            }
        }

        // Name class for coloring
        let nameClass = 'name';
        if (entry.is_error || entry.name === 'ERROR') nameClass += ' error';
        else if (entry.is_stream) nameClass += ' stream';

        // Time display (seconds since epoch → HH:MM:SS.mmm)
        const d = new Date(entry.timestamp * 1000);
        const time = d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0');

        el.innerHTML = `
            <span class="time">${time}</span>
            <span class="${nameClass}">${entry.name}</span>
            <span class="route">
                ${entry.source}<span class="arrow"> → </span>${entry.target}
            </span>
        `;

        el.addEventListener('mouseenter', () => {
            this.dispatchEvent(new CustomEvent('tx-hover', {
                bubbles: true, detail: { entry }
            }));
        });

        el.addEventListener('click', () => {
            this._selectedTraceId = entry.trace_id;
            // Update all entry classes
            for (const child of this._listEl.children) {
                child.classList.remove('selected', 'dimmed');
                const childTraceId = child.dataset.traceId;
                if (childTraceId === entry.trace_id) {
                    child.classList.add('selected');
                } else {
                    child.classList.add('dimmed');
                }
            }
            this.dispatchEvent(new CustomEvent('tx-select', {
                bubbles: true, detail: { trace_id: entry.trace_id }
            }));
        });

        el.dataset.traceId = entry.trace_id;

        this._listEl.appendChild(el);

        if (this._autoScroll) {
            this._listEl.scrollTop = this._listEl.scrollHeight;
        }
    }
}

customElements.define('tx-sidebar', TxSidebar);
