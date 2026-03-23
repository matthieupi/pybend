/**
 * tx-detail.js — Request chain drill-down panel.
 *
 * Shows all TXs with the same trace_id, ordered by timestamp.
 * Displays time offset from root TX, badges, and total duration.
 */

class TxDetail extends HTMLElement {
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
                    border-top: 1px solid #30363d;
                    background: #1c2128;
                    max-height: 40%;
                    overflow-y: auto;
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
                }
                .header h4 {
                    font-size: 12px;
                    font-weight: 600;
                    color: #58a6ff;
                }
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
                .chain-list { flex: 1; overflow-y: auto; }
                .chain-entry {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 4px 12px;
                    font-size: 11px;
                    border-bottom: 1px solid rgba(48, 54, 61, 0.5);
                }
                .offset {
                    color: #6e7681;
                    min-width: 55px;
                    text-align: right;
                }
                .chain-name { font-weight: 500; }
                .chain-name.error { color: #f85149; }
                .chain-name.stream { color: #39d4c5; }
                .chain-route {
                    color: #8b949e;
                    flex: 1;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .arrow { color: #6e7681; margin: 0 2px; }
                .badge {
                    font-size: 9px;
                    padding: 1px 4px;
                    border-radius: 3px;
                    text-transform: uppercase;
                    font-weight: 600;
                }
                .badge-root { background: rgba(88, 166, 255, 0.2); color: #58a6ff; }
                .badge-response { background: rgba(63, 185, 80, 0.2); color: #3fb950; }
                .badge-error { background: rgba(248, 81, 73, 0.2); color: #f85149; }
                .badge-stream { background: rgba(57, 212, 197, 0.2); color: #39d4c5; }
                .duration {
                    padding: 6px 12px;
                    font-size: 11px;
                    color: #8b949e;
                    border-top: 1px solid #30363d;
                    position: sticky;
                    bottom: 0;
                    background: #1c2128;
                }
            </style>
            <div class="header">
                <h4>Request Chain</h4>
                <button class="close-btn">x</button>
            </div>
            <div class="chain-list"></div>
            <div class="duration"></div>
        `;

        this._listEl = this.shadowRoot.querySelector('.chain-list');
        this._durationEl = this.shadowRoot.querySelector('.duration');

        this.shadowRoot.querySelector('.close-btn').addEventListener('click', () => {
            this.hide();
            this.dispatchEvent(new CustomEvent('detail-close', { bubbles: true }));
        });
    }

    show(entries) {
        if (!entries.length) {
            this.hide();
            return;
        }

        this.classList.add('visible');
        this._listEl.innerHTML = '';

        // Sort by timestamp
        const sorted = [...entries].sort((a, b) => a.timestamp - b.timestamp);
        const rootTs = sorted[0].timestamp;

        for (const entry of sorted) {
            const el = document.createElement('div');
            el.className = 'chain-entry';

            const offset = ((entry.timestamp - rootTs) * 1000).toFixed(1);

            let nameClass = 'chain-name';
            if (entry.is_error || entry.name === 'ERROR') nameClass += ' error';
            else if (entry.is_stream) nameClass += ' stream';

            // Badges
            let badges = '';
            if (entry.timestamp === rootTs && !entry.req) {
                badges += '<span class="badge badge-root">root</span> ';
            }
            if (entry.req && !entry.is_error && !entry.is_stream) {
                badges += '<span class="badge badge-response">resp</span> ';
            }
            if (entry.is_error) {
                badges += '<span class="badge badge-error">err</span> ';
            }
            if (entry.is_stream) {
                badges += `<span class="badge badge-stream">stream${entry.seq ? ' #' + entry.seq : ''}</span> `;
            }

            el.innerHTML = `
                <span class="offset">+${offset}ms</span>
                <span class="${nameClass}">${entry.name}</span>
                <span class="chain-route">
                    ${entry.source}<span class="arrow"> → </span>${entry.target}
                </span>
                ${badges}
            `;

            this._listEl.appendChild(el);
        }

        // Duration
        const duration = ((sorted[sorted.length - 1].timestamp - rootTs) * 1000).toFixed(1);
        this._durationEl.textContent = `Chain: ${sorted.length} TXs, ${duration}ms total`;
    }

    hide() {
        this.classList.remove('visible');
    }
}

customElements.define('tx-detail', TxDetail);
