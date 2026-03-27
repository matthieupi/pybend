/**
 * tx-entry-detail.js — Single TX entry inspector panel.
 *
 * Shows all fields of a single TX entry in a key-value layout,
 * with an interactive JSON tree viewer for the data payload.
 *
 * Events emitted:
 *   entry-detail-close  — close button clicked
 */

import { buildJsonTree, hasData, JSON_TREE_CSS } from './json-tree.js';

class TxEntryDetail extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
    }

    connectedCallback() {
        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: none;
                    flex-direction: column;
                    background: #1c2128;
                    overflow: hidden;
                    min-height: 80px;
                    font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
                    font-size: 12px;
                    color: #e6edf3;
                }
                :host(.visible) { display: flex; }
                .header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 8px 12px;
                    border-bottom: 1px solid #30363d;
                    position: sticky;
                    top: 0;
                    background: #1c2128;
                    z-index: 1;
                    flex-shrink: 0;
                }
                .header h4 {
                    font-size: 12px;
                    font-weight: 600;
                    color: #d29922;
                }
                .header-actions {
                    display: flex;
                    align-items: center;
                    gap: 4px;
                }
                .header-btn {
                    background: none;
                    border: none;
                    color: #8b949e;
                    cursor: pointer;
                    font-size: 13px;
                    padding: 2px 5px;
                    line-height: 1;
                    border-radius: 3px;
                }
                .header-btn:hover { color: #e6edf3; background: rgba(88, 166, 255, 0.1); }
                .header-btn.copied { color: #3fb950; }
                .close-btn {
                    background: none;
                    border: none;
                    color: #8b949e;
                    cursor: pointer;
                    font-size: 16px;
                    padding: 0 4px;
                    line-height: 1;
                }
                .close-btn:hover { color: #e6edf3; }
                .fields {
                    flex: 1;
                    overflow-y: auto;
                    padding: 4px 0;
                }
                .field {
                    display: flex;
                    padding: 3px 12px;
                    gap: 8px;
                    border-bottom: 1px solid rgba(48, 54, 61, 0.3);
                }
                .field:hover {
                    background: rgba(88, 166, 255, 0.05);
                }
                .field-key {
                    color: #8b949e;
                    min-width: 90px;
                    flex-shrink: 0;
                    font-size: 11px;
                    padding-top: 1px;
                }
                .field-value {
                    color: #e6edf3;
                    word-break: break-all;
                    font-size: 11px;
                }
                .field-value.uuid { color: #58a6ff; font-size: 10px; }
                .field-value.error { color: #f85149; }
                .field-value.stream { color: #39d4c5; }
                .field-value.muted { color: #6e7681; }
                .data-section {
                    border-top: 1px solid #30363d;
                }
                .data-header {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 6px 12px;
                    font-size: 11px;
                    color: #8b949e;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.3px;
                }
                ${JSON_TREE_CSS}
            </style>
            <div class="header">
                <h4>TX Detail</h4>
                <div class="header-actions">
                    <button class="header-btn copy-btn" title="Copy TX as JSON">&#x2398;</button>
                    <button class="close-btn">x</button>
                </div>
            </div>
            <div class="fields"></div>
        `;

        this._fieldsEl = this.shadowRoot.querySelector('.fields');

        this.shadowRoot.querySelector('.close-btn').addEventListener('click', () => {
            this.hide();
            this.dispatchEvent(new CustomEvent('entry-detail-close', { bubbles: true }));
        });

        this.shadowRoot.querySelector('.copy-btn').addEventListener('click', () => {
            if (!this._entry) return;
            const json = JSON.stringify(this._entry, null, 2);
            const btn = this.shadowRoot.querySelector('.copy-btn');
            navigator.clipboard.writeText(json).then(() => {
                const orig = btn.innerHTML;
                btn.textContent = '\u2713';
                btn.classList.add('copied');
                setTimeout(() => { btn.innerHTML = orig; btn.classList.remove('copied'); }, 1500);
            });
        });
    }

    show(entry) {
        if (!entry) { this.hide(); return; }

        this._entry = entry;
        this.classList.add('visible');
        this._fieldsEl.innerHTML = '';

        const ts = new Date(entry.timestamp * 1000);
        const timeStr = ts.toTimeString().slice(0, 8) + '.' +
            String(ts.getMilliseconds()).padStart(3, '0');

        const fields = [
            { key: 'tx_uuid', value: entry.tx_uuid, cls: 'uuid' },
            { key: 'name', value: entry.name, cls: entry.is_error || entry.name === 'ERROR' ? 'error' : '' },
            { key: 'source', value: entry.source },
            { key: 'target', value: entry.target },
            { key: 'trace_id', value: entry.trace_id, cls: 'uuid' },
            { key: 'timestamp', value: timeStr },
        ];

        if (entry.req) fields.push({ key: 'req', value: entry.req, cls: 'uuid' });
        if (entry.is_error) fields.push({ key: 'is_error', value: 'true', cls: 'error' });
        if (entry.is_stream) fields.push({ key: 'is_stream', value: 'true', cls: 'stream' });
        if (entry.seq != null) fields.push({ key: 'seq', value: String(entry.seq) });

        for (const f of fields) {
            const el = document.createElement('div');
            el.className = 'field';
            el.innerHTML = `
                <span class="field-key">${f.key}</span>
                <span class="field-value${f.cls ? ' ' + f.cls : ''}">${f.value || '\u2014'}</span>
            `;
            this._fieldsEl.appendChild(el);
        }

        // JSON data section
        if (hasData(entry.data)) {
            const section = document.createElement('div');
            section.className = 'data-section';
            section.innerHTML = '<div class="data-header">Data</div>';

            const tree = document.createElement('div');
            buildJsonTree(tree, entry.data);
            section.appendChild(tree);

            this._fieldsEl.appendChild(section);
        }
    }

    hide() {
        this.classList.remove('visible');
    }
}

customElements.define('tx-entry-detail', TxEntryDetail);
