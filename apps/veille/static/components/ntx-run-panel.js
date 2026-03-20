/**
 * <ntx-run-panel> — Scraping run execution panel.
 *
 * Allows users to:
 * - Start a full scraping run across all configured sources
 * - Scan a specific ad-hoc URL for grants
 * - Watch real-time streaming progress (agent thinking, tool calls, text output)
 *
 * Uses the StreamActor mixin for TX-aware SSE dispatch.
 */
import { StreamActor } from './StreamActor.js';
import { config } from '../config.js';

class NTXRunPanel extends StreamActor(HTMLElement) {
    #els;
    #currentRunId = null;
    #textBuf = '';
    #textRendered = 0;
    #textTimer = null;

    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `
            <style>${NTXRunPanel.styles}</style>
            <div class="panel">
                <div class="panel-header">
                    <h2>Scraping Runs</h2>
                    <span class="status-badge" id="status">idle</span>
                </div>

                <div class="controls">
                    <button class="btn btn-primary" id="start-btn">
                        Start Full Run
                    </button>
                    <div class="adhoc-row">
                        <input type="text" id="adhoc-url"
                               placeholder="https://... (scan a specific URL)"
                               class="url-input" />
                        <button class="btn btn-secondary" id="scan-btn">
                            Scan URL
                        </button>
                    </div>
                </div>

                <div class="log-container" id="log-container">
                    <div class="log-placeholder" id="placeholder">
                        No run in progress. Click "Start Full Run" to scrape all configured sources,
                        or enter a URL to scan a specific page.
                    </div>
                    <div class="log" id="log"></div>
                </div>

                <div class="footer" id="footer"></div>

                <div class="history-section" id="history-section">
                    <div class="history-header">
                        <h3>Run History</h3>
                        <button class="btn btn-secondary btn-sm" id="refresh-history-btn">Refresh</button>
                    </div>
                    <div class="history-list" id="history-list">
                        <div class="history-placeholder">Loading run history...</div>
                    </div>
                </div>
            </div>
        `;

        this.#els = {
            status: this.shadowRoot.getElementById('status'),
            startBtn: this.shadowRoot.getElementById('start-btn'),
            scanBtn: this.shadowRoot.getElementById('scan-btn'),
            adhocUrl: this.shadowRoot.getElementById('adhoc-url'),
            logContainer: this.shadowRoot.getElementById('log-container'),
            log: this.shadowRoot.getElementById('log'),
            placeholder: this.shadowRoot.getElementById('placeholder'),
            footer: this.shadowRoot.getElementById('footer'),
            historyList: this.shadowRoot.getElementById('history-list'),
            refreshHistoryBtn: this.shadowRoot.getElementById('refresh-history-btn'),
        };

        this.#els.startBtn.addEventListener('click', () => this.#startFullRun());
        this.#els.scanBtn.addEventListener('click', () => this.#startAdhocRun());
        this.#els.adhocUrl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.#startAdhocRun();
        });
        this.#els.refreshHistoryBtn.addEventListener('click', () => this.#loadHistory());

        // Stop click propagation (in case embedded in a card)
        this.addEventListener('click', (e) => e.stopPropagation());

        // Load run history on connect
        this.#loadHistory();
    }

    disconnectedCallback() {
        this.streamClose();
        clearTimeout(this.#textTimer);
    }

    // ── Run lifecycle ────────────────────────────────────────────

    async #startFullRun() {
        await this.#createAndExecuteRun('full');
    }

    async #startAdhocRun() {
        const url = this.#els.adhocUrl.value.trim();
        if (!url) {
            this.#els.adhocUrl.focus();
            return;
        }
        await this.#createAndExecuteRun('adhoc', url);
    }

    async #createAndExecuteRun(type, adhocUrl = '') {
        // Reset UI
        this.#els.log.innerHTML = '';
        this.#els.footer.innerHTML = '';
        this.#els.placeholder.style.display = 'none';
        this.#textBuf = '';
        this.#textRendered = 0;
        clearTimeout(this.#textTimer);

        this.#setStatus('creating');
        this.#setButtonsDisabled(true);

        const token = localStorage.getItem('jwtToken');
        if (!token) {
            this.#addEntry('error', 'Not authenticated. Please log in.');
            this.#setStatus('error');
            this.#setButtonsDisabled(false);
            return;
        }

        try {
            // Step 1: Create a Run record via CRUD
            const createBody = { type };
            if (adhocUrl) createBody.adhoc_url = adhocUrl;

            const resp = await fetch(`${config.API_URL}/runs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-access-token': token,
                },
                body: JSON.stringify(createBody),
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: resp.statusText }));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }

            const run = await resp.json();
            this.#currentRunId = run.id;

            // Step 2: Stream execution
            this.#setStatus('running');
            const runType = type === 'adhoc' ? `Ad-hoc scan: ${adhocUrl}` : 'Full run (all sources)';
            this.#addEntry('info', `${runType} -- Run #${run.id}`);

            const execUrl = `${config.API_URL}/runs/${run.id}/execute`;
            const payload = adhocUrl ? { adhoc_url: adhocUrl } : {};
            this.stream(execUrl, payload);

        } catch (err) {
            this.#addEntry('error', `Failed to start run: ${err.message}`);
            this.#setStatus('error');
            this.#setButtonsDisabled(false);
        }
    }

    // ── TX inbox handlers (UPPERCASE) ────────────────────────────

    THINKING(data, meta) {
        const text = data?.text || '';
        if (!text) {
            // Empty thinking = just show the indicator
            let el = this.#els.log.querySelector('.entry-thinking-active');
            if (!el) {
                el = this.#addEntry('thinking', '<span class="thinking-anim">Thinking</span>');
                el.classList.add('entry-thinking-active');
            }
            return;
        }
        // Thinking with content — append to active entry
        let entry = this.#els.log.querySelector('.entry-thinking-active');
        if (!entry) {
            entry = this.#addEntry('thinking', '');
            entry.classList.add('entry-thinking-active');
        }
        const content = entry.querySelector('.entry-content');
        content.textContent = (content.textContent || '') + text;
    }

    TOOL_CALL(data, meta) {
        // Remove thinking indicator
        this.#clearThinking();

        const tool = data?.tool || 'unknown';
        const args = data?.args || {};
        let detail = '';

        // Friendly descriptions for known tools
        if (tool.includes('scrape_js')) {
            detail = `Fetching (JS): ${args.url || ''}`;
        } else if (tool.includes('scrape')) {
            detail = `Fetching: ${args.url || ''}`;
        } else if (tool.includes('check_duplicate')) {
            detail = `Checking duplicate: ${args.url || args.title || ''}`;
        } else if (tool.includes('grants_create')) {
            detail = `Creating grant: ${args.title || ''}`;
        } else if (tool.includes('sources_create')) {
            detail = `Adding source: ${args.name || args.url || ''}`;
        } else if (tool.includes('sources_list')) {
            detail = 'Reading configured sources';
        } else {
            const argStr = Object.entries(args).map(([k, v]) => {
                const val = typeof v === 'string' ? v.slice(0, 80) : JSON.stringify(v).slice(0, 80);
                return `${k}=${val}`;
            }).join(', ');
            detail = `${tool}(${argStr})`;
        }

        const entry = this.#addEntry('tool-call', `<span class="tool-icon">\u2699</span> ${this.#esc(detail)}`);
        const spinner = document.createElement('span');
        spinner.className = 'spinner';
        spinner.textContent = ' \u25CF';
        entry.querySelector('.entry-content').appendChild(spinner);

        if (data.call_id) entry.dataset.callId = data.call_id;
    }

    TOOL_RESULT(data, meta) {
        const callId = data?.call_id;
        if (callId) {
            const card = this.#els.log.querySelector(`[data-call-id="${callId}"]`);
            if (card) {
                card.querySelector('.spinner')?.remove();
                card.classList.add('complete');

                // For grant creation, show a brief confirmation
                const result = data?.result;
                if (result && typeof result === 'object' && result.title) {
                    const info = document.createElement('div');
                    info.className = 'tool-result-brief';
                    info.textContent = `Created: ${result.title}`;
                    card.querySelector('.entry-content').appendChild(info);
                }
                return;
            }
        }
        // Fallback: standalone result entry
        this.#addEntry('tool-result', `\u2714 Result received`);
    }

    TEXT(data, meta) {
        this.#clearThinking();
        const text = data?.text || '';
        if (!text) return;

        this.#textBuf += text;
        let entry = this.#els.log.querySelector('.entry-text-active');
        if (!entry) {
            entry = this.#addEntry('text-output', '');
            entry.classList.add('entry-text-active');
        }

        // Render with debounce — immediate on newline, 300ms otherwise
        clearTimeout(this.#textTimer);
        const fresh = this.#textBuf.slice(this.#textRendered);
        if (fresh.includes('\n')) {
            this.#renderText(entry);
        } else {
            this.#textTimer = setTimeout(() => this.#renderText(entry), 300);
        }
    }

    DONE(data, meta) {
        this.#clearThinking();
        this.#flushText();

        const usage = data?.usage;
        if (usage) {
            this.#els.footer.innerHTML =
                `<span>Tokens: ${usage.input_tokens || 0} in / ${usage.output_tokens || 0} out</span>` +
                (data.tool_calls ? ` &middot; <span>${data.tool_calls} tool calls</span>` : '');
        }
    }

    STREAM_END(data) {
        this.#setStatus('done');
        this.#setButtonsDisabled(false);
        this.#flushText();

        // Add completion entry
        this.#addEntry('info', 'Run complete. Check the Grants list for results.');

        // Refresh history so the completed run appears with "View Report"
        this.#loadHistory();
    }

    STREAM_ERROR(err) {
        this.#setStatus('error');
        this.#setButtonsDisabled(false);
        this.#addEntry('error', `Error: ${err?.message || err?.detail || err}`);
    }

    // ── Internal helpers ─────────────────────────────────────────

    #addEntry(type, html) {
        const el = document.createElement('div');
        el.className = `entry entry-${type}`;
        el.innerHTML = `<div class="entry-content">${html}</div>`;
        this.#els.log.appendChild(el);
        this.#scrollToBottom();
        return el;
    }

    #clearThinking() {
        const el = this.#els.log.querySelector('.entry-thinking-active');
        if (el) {
            el.classList.remove('entry-thinking-active');
            // Remove if it was just the animation placeholder
            if (el.querySelector('.thinking-anim')) el.remove();
        }
    }

    #renderText(entry) {
        if (!entry || !this.#textBuf) return;
        const content = entry.querySelector('.entry-content');
        if (typeof marked !== 'undefined' && marked.parse) {
            content.innerHTML = marked.parse(this.#textBuf);
        } else {
            content.textContent = this.#textBuf;
        }
        this.#textRendered = this.#textBuf.length;
        this.#scrollToBottom();
    }

    #flushText() {
        clearTimeout(this.#textTimer);
        const entry = this.#els.log.querySelector('.entry-text-active');
        if (entry) {
            this.#renderText(entry);
            entry.classList.remove('entry-text-active');
        }
        this.#textBuf = '';
        this.#textRendered = 0;
    }

    #setStatus(status) {
        this.#els.status.textContent = status;
        this.#els.status.className = `status-badge ${status}`;
    }

    #setButtonsDisabled(disabled) {
        this.#els.startBtn.disabled = disabled;
        this.#els.scanBtn.disabled = disabled;
        this.#els.adhocUrl.disabled = disabled;
    }

    #scrollToBottom() {
        const container = this.#els.logContainer;
        container.scrollTop = container.scrollHeight;
    }

    // ── Run history ───────────────────────────────────────────────

    async #loadHistory() {
        if (!this.#els) return;
        const token = localStorage.getItem('jwtToken');
        if (!token) return;

        try {
            const resp = await fetch(`${config.API_URL}/runs?limit=20`, {
                headers: { 'x-access-token': token },
            });
            if (!resp.ok) return;
            const result = await resp.json();
            const runs = result.data || result;

            runs.sort((a, b) => {
                const ta = a.started_at || '';
                const tb = b.started_at || '';
                return tb.localeCompare(ta);
            });

            this.#renderHistory(runs);
        } catch (e) {
            console.warn('Failed to load run history:', e);
        }
    }

    #renderHistory(runs) {
        if (!this.#els?.historyList) return;

        if (!runs || runs.length === 0) {
            this.#els.historyList.innerHTML = `
                <div class="history-empty">No runs yet. Start your first run above.</div>
            `;
            return;
        }

        const rows = runs.map(run => {
            const statusClass = this.#runStatusClass(run.status);
            const typeClass = run.type === 'full' ? 'type-full' : 'type-adhoc';
            const viewReportHtml = run.status === 'complete'
                ? `<a class="report-link" href="#report/${run.id}">View Report</a>`
                : `<span class="report-link-disabled">—</span>`;

            return `
                <div class="history-row">
                    <span class="history-cell run-id">#${run.id}</span>
                    <span class="history-cell">
                        <span class="type-pill ${typeClass}">${this.#esc(run.type || 'full')}</span>
                    </span>
                    <span class="history-cell">
                        <span class="run-status-pill ${statusClass}">${this.#esc(run.status || 'pending')}</span>
                    </span>
                    <span class="history-cell run-date">${this.#formatDate(run.started_at)}</span>
                    <span class="history-cell run-count">${run.grants_found ?? '—'}</span>
                    <span class="history-cell run-count">${run.sources_covered ?? '—'}</span>
                    <span class="history-cell">${viewReportHtml}</span>
                </div>
            `;
        }).join('');

        this.#els.historyList.innerHTML = `
            <div class="history-table-header">
                <span class="history-cell">Run</span>
                <span class="history-cell">Type</span>
                <span class="history-cell">Status</span>
                <span class="history-cell">Started</span>
                <span class="history-cell">Grants</span>
                <span class="history-cell">Sources</span>
                <span class="history-cell">Actions</span>
            </div>
            ${rows}
        `;
    }

    #runStatusClass(status) {
        const map = {
            complete: 'run-status-complete',
            running:  'run-status-running',
            failed:   'run-status-failed',
            pending:  'run-status-pending',
        };
        return map[status] || 'run-status-pending';
    }

    #formatDate(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            return d.toLocaleDateString('en', { month: 'short', day: 'numeric' })
                + ', ' + d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });
        } catch {
            return iso;
        }
    }

    #esc(t) {
        const d = document.createElement('div');
        d.textContent = t;
        return d.innerHTML;
    }

    // ── Styles ───────────────────────────────────────────────────

    static styles = `
        :host {
            display: block;
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 0.875rem;
            height: 100%;
        }

        .panel {
            display: flex;
            flex-direction: column;
            height: 100%;
            max-height: calc(100vh - 80px);
            background: var(--surface-1, #1a1a2e);
            border-radius: 0.5rem;
            overflow: hidden;
        }

        .panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border, #333);
            background: var(--surface-2, #16213e);
        }
        .panel-header h2 {
            margin: 0;
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-1, #eee);
        }

        .status-badge {
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
            padding: 0.15rem 0.5rem;
            border-radius: 0.25rem;
            background: var(--surface-3, #0f3460);
            color: var(--text-2, #aaa);
        }
        .status-badge.creating { background: var(--warning, #f59e0b); color: #000; }
        .status-badge.running { background: var(--accent, #4cc9f0); color: #000; }
        .status-badge.done { background: var(--success, #4ade80); color: #000; }
        .status-badge.error { background: var(--error, #f87171); color: #000; }

        .controls {
            padding: 0.75rem 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            border-bottom: 1px solid var(--border, #333);
        }

        .adhoc-row {
            display: flex;
            gap: 0.4rem;
        }

        .url-input {
            flex: 1;
            padding: 0.4rem 0.6rem;
            border-radius: 0.3rem;
            background: var(--surface-3, #0f3460);
            color: var(--text-1, #eee);
            border: 1px solid var(--border, #333);
            font-family: inherit;
            font-size: 0.8rem;
        }
        .url-input:focus { outline: 1px solid var(--accent, #4cc9f0); }
        .url-input:disabled { opacity: 0.5; }

        .btn {
            padding: 0.5rem 1rem;
            border-radius: 0.3rem;
            border: none;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.8rem;
            transition: filter 0.15s;
        }
        .btn:hover { filter: brightness(1.1); }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }

        .btn-primary {
            background: var(--accent, #4cc9f0);
            color: #000;
        }
        .btn-secondary {
            background: var(--surface-3, #0f3460);
            color: var(--text-1, #eee);
            border: 1px solid var(--border, #333);
        }

        .log-container {
            flex: 1;
            overflow-y: auto;
            padding: 0.5rem 0.75rem;
            min-height: 200px;
        }

        .log-placeholder {
            color: var(--text-2, #aaa);
            font-style: italic;
            padding: 2rem 1rem;
            text-align: center;
        }

        .entry {
            margin-bottom: 0.35rem;
            line-height: 1.5;
        }
        .entry-content {
            padding: 0.3rem 0.5rem;
            border-radius: 0.3rem;
        }

        .entry-info .entry-content {
            background: var(--surface-3, #0f3460);
            border-left: 2px solid var(--accent, #4cc9f0);
            font-weight: 500;
        }

        .entry-thinking .entry-content {
            background: rgba(167, 139, 250, 0.08);
            border-left: 2px solid var(--thinking, #a78bfa);
            font-style: italic;
            opacity: 0.7;
            font-size: 0.8rem;
            color: var(--thinking, #a78bfa);
        }

        .entry-tool-call .entry-content {
            background: var(--surface-3, #0f3460);
            border-left: 2px solid var(--warning, #f59e0b);
            font-size: 0.8rem;
        }
        .entry-tool-call.complete .entry-content {
            border-left-color: var(--success, #22c55e);
        }
        .tool-icon { opacity: 0.6; margin-right: 0.2rem; }
        .spinner {
            animation: spin 1s linear infinite;
            color: var(--warning, #fbbf24);
            font-size: 0.6rem;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .tool-result-brief {
            margin-top: 0.2rem;
            font-size: 0.75rem;
            color: var(--success, #4ade80);
        }

        .entry-tool-result .entry-content {
            font-size: 0.8rem;
            color: var(--text-2, #aaa);
        }

        .entry-text-output .entry-content {
            word-break: break-word;
            border-left: 2px solid var(--text-accent, #38bdf8);
            line-height: 1.6;
        }
        .entry-text-output p { margin: 0.3em 0; }
        .entry-text-output code {
            background: rgba(0,0,0,0.3);
            padding: 0.1em 0.3em;
            border-radius: 3px;
            font-size: 0.85em;
        }
        .entry-text-output pre {
            background: rgba(0,0,0,0.3);
            border-radius: 0.3rem;
            padding: 0.4rem 0.6rem;
            overflow-x: auto;
            font-size: 0.8em;
        }

        .entry-error .entry-content {
            background: rgba(248, 113, 113, 0.1);
            border-left: 2px solid var(--error, #f87171);
            color: var(--error, #f87171);
        }

        .thinking-anim::after {
            content: '';
            animation: dots 1.5s steps(3, end) infinite;
        }
        @keyframes dots {
            0% { content: '.'; }
            33% { content: '..'; }
            66% { content: '...'; }
        }

        .footer {
            padding: 0.3rem 0.75rem;
            font-size: 0.65rem;
            color: var(--text-2, #aaa);
            border-top: 1px solid var(--border, #333);
            min-height: 1.2rem;
        }

        /* ── Run History ─────────────────────────────────────────────── */

        .history-section {
            border-top: 1px solid var(--border, #333);
            background: var(--surface-1, #1a1a2e);
        }

        .history-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.5rem 1rem;
            border-bottom: 1px solid var(--border, #333);
            background: var(--surface-2, #16213e);
        }

        .history-header h3 {
            margin: 0;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-2, #aaa);
        }

        .btn-sm {
            padding: 0.25rem 0.6rem;
            font-size: 0.7rem;
        }

        .history-list {
            overflow-y: auto;
            max-height: 300px;
        }

        .history-placeholder,
        .history-empty {
            padding: 1rem;
            text-align: center;
            color: var(--text-2, #aaa);
            font-style: italic;
            font-size: 0.8rem;
        }

        .history-table-header {
            display: grid;
            grid-template-columns: 3rem 4.5rem 5.5rem 1fr 4rem 4.5rem 6rem;
            padding: 0.25rem 0.75rem;
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--text-2, #aaa);
            border-bottom: 1px solid var(--border, #333);
            background: var(--surface-2, #16213e);
            position: sticky;
            top: 0;
        }

        .history-row {
            display: grid;
            grid-template-columns: 3rem 4.5rem 5.5rem 1fr 4rem 4.5rem 6rem;
            padding: 0.35rem 0.75rem;
            font-size: 0.78rem;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            align-items: center;
            transition: background 0.12s;
        }
        .history-row:hover {
            background: var(--surface-2, #16213e);
        }

        .history-cell {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text-1, #eee);
        }

        .run-id {
            font-weight: 600;
            color: var(--text-2, #aaa);
            font-size: 0.75rem;
        }

        .run-date {
            font-size: 0.75rem;
            color: var(--text-2, #aaa);
        }

        .run-count {
            text-align: center;
            font-weight: 600;
        }

        .type-pill {
            font-size: 0.65rem;
            font-weight: 600;
            padding: 0.1rem 0.35rem;
            border-radius: 0.2rem;
            text-transform: capitalize;
        }
        .type-full  { background: var(--accent, #4cc9f0); color: #000; }
        .type-adhoc { background: var(--warning, #f59e0b); color: #000; }

        .run-status-pill {
            font-size: 0.65rem;
            font-weight: 600;
            padding: 0.1rem 0.35rem;
            border-radius: 0.2rem;
            text-transform: capitalize;
        }
        .run-status-complete { background: var(--success, #4ade80); color: #000; }
        .run-status-running  { background: var(--accent, #4cc9f0); color: #000; }
        .run-status-failed   { background: var(--error, #f87171); color: #fff; }
        .run-status-pending  { background: var(--surface-3, #0f3460); color: var(--text-2, #aaa); }

        .report-link {
            color: var(--accent, #4cc9f0);
            text-decoration: none;
            font-size: 0.75rem;
            font-weight: 500;
        }
        .report-link:hover { text-decoration: underline; }

        .report-link-disabled {
            color: var(--text-2, #555);
            font-size: 0.75rem;
        }
    `;
}

customElements.define('ntx-run-panel', NTXRunPanel);
export { NTXRunPanel };
