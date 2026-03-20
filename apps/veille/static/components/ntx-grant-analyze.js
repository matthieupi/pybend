/**
 * <ntx-grant-analyze> — Per-grant admissibility analysis panel.
 *
 * Loads a specific grant's details and allows the user to re-run
 * admissibility analysis with real-time streaming progress.
 *
 * Usage:
 *   <ntx-grant-analyze grant-id="42"></ntx-grant-analyze>
 *
 * Observed attributes:
 *   grant-id  — the numeric ID of the grant to analyze
 *
 * Uses the StreamActor mixin for TX-aware SSE dispatch.
 */
import { StreamActor } from './StreamActor.js';
import { config } from '../config.js';

class NTXGrantAnalyze extends StreamActor(HTMLElement) {
    #els;
    #grantId = null;
    #grant = null;
    #textBuf = '';
    #textRendered = 0;
    #textTimer = null;

    static get observedAttributes() {
        return ['grant-id'];
    }

    attributeChangedCallback(name, oldVal, newVal) {
        if (name === 'grant-id' && newVal && newVal !== oldVal) {
            this.#grantId = newVal;
            if (this.shadowRoot) {
                this.#reset();
                this.#loadGrant();
            }
        }
    }

    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `
            <style>${NTXGrantAnalyze.styles}</style>
            <div class="panel">
                <div class="panel-header">
                    <div class="header-left">
                        <button class="back-btn" id="back-btn">← Back to Grants</button>
                        <h2 id="grant-title">Loading grant...</h2>
                    </div>
                    <span class="status-badge" id="status">idle</span>
                </div>

                <div class="grant-info" id="grant-info">
                    <div class="info-placeholder">Loading...</div>
                </div>

                <div class="controls" id="controls">
                    <button class="btn btn-primary" id="analyze-btn" disabled>
                        Re-run Analysis
                    </button>
                    <span class="controls-hint">
                        Runs full admissibility check against your organisation profile.
                    </span>
                </div>

                <div class="log-container" id="log-container">
                    <div class="log-placeholder" id="placeholder">
                        Click "Re-run Analysis" to evaluate this grant against your organisation profile.
                    </div>
                    <div class="log" id="log"></div>
                </div>

                <div class="footer" id="footer"></div>
            </div>
        `;

        this.#els = {
            status:       this.shadowRoot.getElementById('status'),
            grantTitle:   this.shadowRoot.getElementById('grant-title'),
            grantInfo:    this.shadowRoot.getElementById('grant-info'),
            analyzeBtn:   this.shadowRoot.getElementById('analyze-btn'),
            controls:     this.shadowRoot.getElementById('controls'),
            logContainer: this.shadowRoot.getElementById('log-container'),
            log:          this.shadowRoot.getElementById('log'),
            placeholder:  this.shadowRoot.getElementById('placeholder'),
            footer:       this.shadowRoot.getElementById('footer'),
            backBtn:      this.shadowRoot.getElementById('back-btn'),
        };

        this.#els.analyzeBtn.addEventListener('click', () => this.#startAnalysis());
        this.#els.backBtn.addEventListener('click', () => {
            window.location.hash = '';
        });

        // Stop click propagation (in case embedded in a card)
        this.addEventListener('click', (e) => e.stopPropagation());

        // Load grant if attribute was set before connectedCallback
        if (this.#grantId) {
            this.#loadGrant();
        }
    }

    disconnectedCallback() {
        this.streamClose();
        clearTimeout(this.#textTimer);
    }

    // ── Grant loading ─────────────────────────────────────────────

    async #loadGrant() {
        if (!this.#grantId || !this.#els) return;

        const token = localStorage.getItem('jwtToken');
        if (!token) {
            this.#showGrantError('Not authenticated. Please log in.');
            return;
        }

        try {
            const resp = await fetch(`${config.API_URL}/grants/${this.#grantId}`, {
                headers: { 'x-access-token': token },
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: resp.statusText }));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }

            this.#grant = await resp.json();
            this.#renderGrantInfo();
            this.#els.analyzeBtn.disabled = false;

        } catch (err) {
            this.#showGrantError(`Failed to load grant: ${err.message}`);
        }
    }

    #renderGrantInfo() {
        const g = this.#grant;
        if (!g) return;

        this.#els.grantTitle.textContent = g.title || `Grant #${this.#grantId}`;

        const score = g.score != null ? `${Math.round(g.score * 100)}%` : 'N/A';
        const statusClass = this.#statusClass(g.status);

        this.#els.grantInfo.innerHTML = `
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">Funder</span>
                    <span class="info-value">${this.#esc(g.funder || '—')}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Status</span>
                    <span class="info-value">
                        <span class="grant-status ${statusClass}">${this.#esc(g.status || 'new')}</span>
                    </span>
                </div>
                <div class="info-item">
                    <span class="info-label">Admissibility Score</span>
                    <span class="info-value score ${this.#scoreClass(g.score)}">${score}</span>
                </div>
                ${g.url ? `
                <div class="info-item info-item--full">
                    <span class="info-label">URL</span>
                    <span class="info-value">
                        <a href="${this.#esc(g.url)}" target="_blank" rel="noopener">${this.#esc(g.url)}</a>
                    </span>
                </div>` : ''}
                ${g.deadline ? `
                <div class="info-item">
                    <span class="info-label">Deadline</span>
                    <span class="info-value">${this.#esc(g.deadline)}</span>
                </div>` : ''}
                ${g.amount != null ? `
                <div class="info-item">
                    <span class="info-label">Amount</span>
                    <span class="info-value">${this.#esc(String(g.amount))}</span>
                </div>` : ''}
            </div>
            ${g.justification ? `
            <div class="justification">
                <span class="info-label">Last Analysis</span>
                <div class="justification-text">${this.#esc(g.justification)}</div>
            </div>` : ''}
        `;
    }

    #showGrantError(msg) {
        if (!this.#els) return;
        this.#els.grantTitle.textContent = 'Error';
        this.#els.grantInfo.innerHTML = `<div class="info-error">${this.#esc(msg)}</div>`;
        this.#els.analyzeBtn.disabled = true;
    }

    // ── Analysis lifecycle ────────────────────────────────────────

    async #startAnalysis() {
        if (!this.#grantId) return;

        // Reset log
        this.#reset();
        this.#els.placeholder.style.display = 'none';
        this.#setStatus('analyzing');
        this.#els.analyzeBtn.disabled = true;

        const token = localStorage.getItem('jwtToken');
        if (!token) {
            this.#addEntry('error', 'Not authenticated. Please log in.');
            this.#setStatus('error');
            this.#els.analyzeBtn.disabled = false;
            return;
        }

        const url = `${config.API_URL}/grants/${this.#grantId}/analyze`;
        this.#addEntry('info', `Starting admissibility analysis for grant #${this.#grantId}...`);
        this.stream(url, {});
    }

    // ── TX inbox handlers (UPPERCASE) ─────────────────────────────

    THINKING(data, meta) {
        const text = data?.text || '';
        if (!text) {
            let el = this.#els.log.querySelector('.entry-thinking-active');
            if (!el) {
                el = this.#addEntry('thinking', '<span class="thinking-anim">Thinking</span>');
                el.classList.add('entry-thinking-active');
            }
            return;
        }
        let entry = this.#els.log.querySelector('.entry-thinking-active');
        if (!entry) {
            entry = this.#addEntry('thinking', '');
            entry.classList.add('entry-thinking-active');
        }
        const content = entry.querySelector('.entry-content');
        content.textContent = (content.textContent || '') + text;
    }

    TOOL_CALL(data, meta) {
        this.#clearThinking();

        const tool = data?.tool || 'unknown';
        const args = data?.args || {};
        let detail = '';

        // Friendly descriptions for known analysis tools
        if (tool.includes('organizations_list') || tool.includes('organizations_read')) {
            detail = 'Reading organisation profile';
        } else if (tool.includes('grants_update')) {
            detail = `Saving analysis results for grant #${this.#grantId}`;
        } else if (tool.includes('grants_read')) {
            detail = `Reading grant details`;
        } else if (tool.includes('grants_list')) {
            detail = 'Listing grants';
        } else if (tool.includes('sources_list')) {
            detail = 'Reading configured sources';
        } else if (tool.includes('scrape_js')) {
            detail = `Fetching (JS): ${args.url || ''}`;
        } else if (tool.includes('scrape')) {
            detail = `Fetching: ${args.url || ''}`;
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

                // For grant updates, show confirmation
                const result = data?.result;
                if (result && typeof result === 'object' && result.score != null) {
                    const score = Math.round(result.score * 100);
                    const info = document.createElement('div');
                    info.className = 'tool-result-brief';
                    info.textContent = `Score updated: ${score}%`;
                    card.querySelector('.entry-content').appendChild(info);
                }
                return;
            }
        }
        this.#addEntry('tool-result', '\u2714 Result received');
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
        this.#els.analyzeBtn.disabled = false;
        this.#flushText();

        this.#addEntry('info', 'Analysis complete. Reloading grant details...');

        // Reload grant info to show updated score/status/justification
        this.#loadGrant().then(() => {
            this.#renderGrantInfo();
        });
    }

    STREAM_ERROR(err) {
        this.#setStatus('error');
        this.#els.analyzeBtn.disabled = false;
        this.#flushText();
        this.#addEntry('error', `Error: ${err?.message || err?.detail || String(err)}`);
    }

    // ── Internal helpers ──────────────────────────────────────────

    #reset() {
        if (!this.#els) return;
        this.#els.log.innerHTML = '';
        this.#els.footer.innerHTML = '';
        this.#els.placeholder.style.display = '';
        this.#textBuf = '';
        this.#textRendered = 0;
        clearTimeout(this.#textTimer);
        this.streamClose();
    }

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

    #scrollToBottom() {
        const container = this.#els.logContainer;
        container.scrollTop = container.scrollHeight;
    }

    #statusClass(status) {
        const map = {
            new: 'status-new',
            analyzing: 'status-analyzing',
            admissible: 'status-admissible',
            inadmissible: 'status-inadmissible',
            error: 'status-error',
        };
        return map[status] || 'status-new';
    }

    #scoreClass(score) {
        if (score == null) return '';
        if (score >= 0.7) return 'score-high';
        if (score >= 0.4) return 'score-mid';
        return 'score-low';
    }

    #esc(t) {
        const d = document.createElement('div');
        d.textContent = String(t);
        return d.innerHTML;
    }

    // ── Styles ────────────────────────────────────────────────────

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

        /* Header */
        .panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border, #333);
            background: var(--surface-2, #16213e);
            gap: 0.75rem;
        }

        .header-left {
            display: flex;
            flex-direction: column;
            gap: 0.2rem;
            min-width: 0;
        }

        .panel-header h2 {
            margin: 0;
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-1, #eee);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 40vw;
        }

        .back-btn {
            background: none;
            border: none;
            color: var(--accent, #4cc9f0);
            cursor: pointer;
            font-size: 0.75rem;
            padding: 0;
            opacity: 0.8;
            transition: opacity 0.15s;
        }
        .back-btn:hover { opacity: 1; }

        /* Status badge */
        .status-badge {
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
            padding: 0.15rem 0.5rem;
            border-radius: 0.25rem;
            background: var(--surface-3, #0f3460);
            color: var(--text-2, #aaa);
            flex-shrink: 0;
        }
        .status-badge.analyzing { background: var(--accent, #4cc9f0); color: #000; }
        .status-badge.done      { background: var(--success, #4ade80); color: #000; }
        .status-badge.error     { background: var(--error, #f87171); color: #000; }

        /* Grant info card */
        .grant-info {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border, #333);
            background: var(--surface-2, #16213e);
        }

        .info-placeholder {
            color: var(--text-2, #aaa);
            font-style: italic;
            font-size: 0.8rem;
        }

        .info-error {
            color: var(--error, #f87171);
            font-size: 0.8rem;
        }

        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 0.5rem 1.5rem;
            margin-bottom: 0.5rem;
        }

        .info-item {
            display: flex;
            flex-direction: column;
            gap: 0.1rem;
        }
        .info-item--full {
            grid-column: 1 / -1;
        }

        .info-label {
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-2, #aaa);
            font-weight: 600;
        }

        .info-value {
            font-size: 0.85rem;
            color: var(--text-1, #eee);
            word-break: break-word;
        }
        .info-value a {
            color: var(--accent, #4cc9f0);
            text-decoration: none;
            font-size: 0.8rem;
        }
        .info-value a:hover { text-decoration: underline; }

        /* Grant status pill */
        .grant-status {
            font-size: 0.7rem;
            font-weight: 600;
            padding: 0.1rem 0.4rem;
            border-radius: 0.2rem;
            text-transform: capitalize;
        }
        .status-new          { background: var(--surface-3, #0f3460); color: var(--text-2, #aaa); }
        .status-analyzing    { background: var(--accent, #4cc9f0); color: #000; }
        .status-admissible   { background: var(--success, #4ade80); color: #000; }
        .status-inadmissible { background: var(--error, #f87171); color: #fff; }
        .status-error        { background: var(--warning, #f59e0b); color: #000; }

        /* Score */
        .score {
            font-weight: 700;
            font-size: 1rem;
        }
        .score-high { color: var(--success, #4ade80); }
        .score-mid  { color: var(--warning, #f59e0b); }
        .score-low  { color: var(--error, #f87171); }

        /* Justification */
        .justification {
            margin-top: 0.5rem;
            padding-top: 0.5rem;
            border-top: 1px solid var(--border, #333);
        }

        .justification-text {
            margin-top: 0.25rem;
            font-size: 0.8rem;
            color: var(--text-1, #eee);
            line-height: 1.5;
            max-height: 4.5em;
            overflow: hidden;
            text-overflow: ellipsis;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
        }

        /* Controls */
        .controls {
            padding: 0.6rem 1rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            border-bottom: 1px solid var(--border, #333);
            background: var(--surface-1, #1a1a2e);
        }

        .controls-hint {
            font-size: 0.75rem;
            color: var(--text-2, #aaa);
            font-style: italic;
        }

        /* Buttons */
        .btn {
            padding: 0.5rem 1rem;
            border-radius: 0.3rem;
            border: none;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.8rem;
            transition: filter 0.15s;
            white-space: nowrap;
        }
        .btn:hover { filter: brightness(1.1); }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }

        .btn-primary {
            background: var(--accent, #4cc9f0);
            color: #000;
        }

        /* Log */
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
            0%  { content: '.'; }
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
    `;
}

customElements.define('ntx-grant-analyze', NTXGrantAnalyze);
export { NTXGrantAnalyze };
