/**
 * <ntx-run-output> — Structured run progress + analysis feed.
 *
 * Extends NTTStreamAgent with two phases:
 * 1. Scraping phase: source cards with per-source agent output
 * 2. Analysis phase: spawn <ntx-grant-analyze> per discovered grant
 *
 * Key technique: does NOT override TEXT/THINKING/TOOL_CALL/TOOL_RESULT/DONE.
 * Instead, on each SOURCE_START, pre-creates the parent's `.agent-output`
 * inside the current source card. The parent's #output() finds it via
 * querySelector and renders there — full accumulation, markdown, tool cards,
 * and CSS for free.
 *
 * Between sources, resets the parent's private buffers by calling
 * super.callMethod() with send() temporarily disabled.
 *
 * Wired via Run.__ui__['methods']['execute|adhoc']['renderer'] = 'ntx-run-output'
 */
import { NTTStreamAgent } from './ntx-stream-agent.js';

class NTXRunOutput extends NTTStreamAgent {

    #currentSourceEl = null;
    #grantsFound = [];
    #sourcesCompleted = 0;
    #sourcesTotal = 0;
    #progressEl = null;
    #phasesEl = null;

    // ── Source lifecycle events ────────────────────────────────

    SOURCE_START(data, meta) {
        // Retire previous source's .agent-output so querySelector won't find it
        const oldOutput = this.shadowRoot.querySelector('.agent-output');
        if (oldOutput) {
            oldOutput.className = 'ro-agent-captured';
            this.#resetParentState();
        }

        this.#sourcesTotal = data.total || this.#sourcesTotal;
        this.#updateProgress(data.index, this.#sourcesTotal);

        const container = this.#phases();

        // Create source card
        const card = document.createElement('div');
        card.className = 'ro-source-card ro-source-active';
        card.dataset.sourceId = data.source_id || '';
        card.innerHTML = `
            <div class="ro-source-header">
                <span class="ro-source-spinner"></span>
                <span class="ro-source-name">${this.#esc(data.name || data.url)}</span>
                ${data.url ? `<a class="ro-source-url" href="${this.#esc(data.url)}" target="_blank" rel="noopener">${this.#esc(this.#shortUrl(data.url))}</a>` : ''}
            </div>
            <div class="ro-source-agent ro-agent-open"></div>
            <div class="ro-source-grants"></div>
        `;
        container.appendChild(card);

        // Click header to toggle agent output
        card.querySelector('.ro-source-header').addEventListener('click', () => {
            card.querySelector('.ro-source-agent').classList.toggle('ro-agent-open');
        });

        // Pre-create .agent-output inside this source card.
        // Parent's #output() will find it via querySelector('.agent-output')
        // and render all TEXT/THINKING/TOOL_CALL/TOOL_RESULT events there.
        const agentArea = card.querySelector('.ro-source-agent');
        const agentOutput = document.createElement('div');
        agentOutput.className = 'agent-output';
        agentOutput.addEventListener('click', (e) => {
            const entry = e.target.closest('.entry.collapsible');
            if (entry) entry.classList.toggle('expanded');
        });
        agentArea.appendChild(agentOutput);

        this.#currentSourceEl = card;
    }

    SOURCE_DONE(data, meta) {
        this.#sourcesCompleted++;
        if (this.#currentSourceEl) {
            this.#currentSourceEl.classList.remove('ro-source-active');
            this.#currentSourceEl.classList.add('ro-source-done');

            // Spinner → checkmark
            const spinner = this.#currentSourceEl.querySelector('.ro-source-spinner');
            if (spinner) {
                spinner.textContent = '\u2713';
                spinner.className = 'ro-source-check';
            }

            // Grant count badge
            const grantsFound = data.grants_found || 0;
            if (grantsFound > 0) {
                const countEl = document.createElement('span');
                countEl.className = 'ro-source-count';
                countEl.textContent = `${grantsFound} grant${grantsFound > 1 ? 's' : ''}`;
                this.#currentSourceEl.querySelector('.ro-source-header').appendChild(countEl);
            }

            // Collapse agent output
            const agentEl = this.#currentSourceEl.querySelector('.ro-source-agent');
            if (agentEl) agentEl.classList.remove('ro-agent-open');
        }

        this.#updateProgress(this.#sourcesCompleted, this.#sourcesTotal);
        this.#currentSourceEl = null;
    }

    GRANT_FOUND(data, meta) {
        this.#grantsFound.push(data);

        if (this.#currentSourceEl) {
            const grantsEl = this.#currentSourceEl.querySelector('.ro-source-grants');
            if (grantsEl) {
                const pill = document.createElement('a');
                pill.className = 'ro-grant-pill';
                pill.textContent = data.title || `Grant #${data.id}`;
                pill.href = `#grants/${data.id}`;
                grantsEl.appendChild(pill);
            }
        }
    }

    // TEXT, THINKING, TOOL_CALL, TOOL_RESULT, DONE — NOT overridden.
    // Parent NTTStreamAgent handles them, rendering into the .agent-output
    // we pre-created inside the current source card.

    STREAM_END(data) {
        // Retire last source's .agent-output
        const lastOutput = this.shadowRoot.querySelector('.agent-output');
        if (lastOutput) lastOutput.className = 'ro-agent-captured';

        this.#updateProgress(this.#sourcesTotal, this.#sourcesTotal, true);

        if (this.#grantsFound.length > 0) {
            this.#startAnalysisPhase();
        }

        if (this.ntt?.pull) this.ntt.pull();
    }

    STREAM_ERROR(data) {
        const msg = (typeof data === 'string') ? data
            : data?.message || data?.detail || data?.error || 'Stream error';
        const container = this.#phases();
        const errEl = document.createElement('div');
        errEl.className = 'ro-error';
        errEl.textContent = `Error: ${msg}`;
        container.appendChild(errEl);
    }

    // ── Parent state reset ────────────────────────────────────

    /**
     * Reset the parent NTTStreamAgent's private buffers (#textBuf, #thinkBuf,
     * #toolCards, #outputEl) between sources. Calls super.callMethod() with
     * send() temporarily disabled to avoid dispatching a duplicate stream TX.
     */
    #resetParentState() {
        const origSend = this.send.bind(this);
        this.send = () => {};
        try { super.callMethod(); } catch { /* ignore */ }
        this.send = origSend;
        // Clean up .stream-output created by NTTStream.callMethod()
        const streamOut = this.shadowRoot.querySelector('.stream-output');
        if (streamOut) streamOut.remove();
    }

    // ── Analysis phase ────────────────────────────────────────

    #startAnalysisPhase() {
        const container = this.#phases();

        const divider = document.createElement('div');
        divider.className = 'ro-divider';
        divider.textContent = `Analysis \u2014 ${this.#grantsFound.length} grant${this.#grantsFound.length > 1 ? 's' : ''}`;
        container.appendChild(divider);

        for (const grant of this.#grantsFound) {
            const card = document.createElement('div');
            card.className = 'ro-analysis-card';
            card.innerHTML = `
                <div class="ro-analysis-header">
                    <span class="ro-analysis-status ro-status-pending">\u25CB</span>
                    <span class="ro-analysis-title">${this.#esc(grant.title || `Grant #${grant.id}`)}</span>
                    <span class="ro-analysis-badge"></span>
                </div>
                <div class="ro-analysis-body ro-collapsed"></div>
            `;
            container.appendChild(card);

            const header = card.querySelector('.ro-analysis-header');
            const body = card.querySelector('.ro-analysis-body');
            header.addEventListener('click', () => body.classList.toggle('ro-collapsed'));

            const analyzeEl = document.createElement('ntx-grant-analyze');
            analyzeEl.setAttribute('model', 'Grant');
            analyzeEl.setAttribute('uuid', String(grant.id));
            analyzeEl.setAttribute('method', 'analyze');
            body.appendChild(analyzeEl);

            this.#wireAnalyzeComponent(analyzeEl, card, grant.id);
        }
    }

    #wireAnalyzeComponent(analyzeEl, card, grantId) {
        const statusIcon = card.querySelector('.ro-analysis-status');
        const badge = card.querySelector('.ro-analysis-badge');

        const poll = setInterval(() => {
            if (analyzeEl.methodSchema) {
                clearInterval(poll);
                statusIcon.textContent = '\u25CF';
                statusIcon.className = 'ro-analysis-status ro-status-running';

                const origEnd = analyzeEl.STREAM_END?.bind(analyzeEl);
                analyzeEl.STREAM_END = (data) => {
                    if (origEnd) origEnd(data);
                    statusIcon.textContent = '\u2713';
                    statusIcon.className = 'ro-analysis-status ro-status-done';
                    this.#fetchGrantStatus(grantId, badge);
                };

                const origError = analyzeEl.STREAM_ERROR?.bind(analyzeEl);
                analyzeEl.STREAM_ERROR = (data) => {
                    if (origError) origError(data);
                    statusIcon.textContent = '\u2717';
                    statusIcon.className = 'ro-analysis-status ro-status-failed';
                    badge.textContent = 'failed';
                    badge.className = 'ro-analysis-badge ro-badge-failed';
                };

                analyzeEl.callMethod();
            }
        }, 100);

        setTimeout(() => clearInterval(poll), 15000);
    }

    async #fetchGrantStatus(grantId, badge) {
        try {
            const token = localStorage.getItem('jwtToken');
            const resp = await fetch(`/grants/${grantId}`, {
                headers: { 'x-access-token': token },
            });
            if (!resp.ok) return;
            const grant = await resp.json();
            const status = grant.status || 'analyzed';
            const score = grant.admissibility_score;

            badge.textContent = score != null
                ? `${status} (${Math.round(score * 100)}%)`
                : status;

            const classMap = {
                'admissible': 'ro-badge-admissible',
                'partially admissible': 'ro-badge-partial',
                'non-admissible': 'ro-badge-non',
            };
            badge.className = `ro-analysis-badge ${classMap[status] || 'ro-badge-done'}`;
        } catch { /* ignore */ }
    }

    // ── DOM helpers ──────────────────────────────────────────

    render() {
        super.render();
        const style = this.shadowRoot.querySelector('style');
        if (style && !style.textContent.includes('ro-source-card')) {
            style.textContent += NTXRunOutput.runOutputStyles;
        }
    }

    callMethod() {
        this.#currentSourceEl = null;
        this.#grantsFound = [];
        this.#sourcesCompleted = 0;
        this.#sourcesTotal = 0;
        this.#progressEl = null;
        this.#phasesEl = null;
        super.callMethod();
    }

    #phases() {
        if (this.#phasesEl) return this.#phasesEl;
        let el = this.shadowRoot.querySelector('.ro-phases');
        if (!el) {
            el = document.createElement('div');
            el.className = 'ro-phases';
            this.shadowRoot.appendChild(el);
        }
        this.#phasesEl = el;
        return el;
    }

    #updateProgress(current, total, done = false) {
        if (!this.#progressEl) {
            this.#progressEl = document.createElement('div');
            this.#progressEl.className = 'ro-progress';
            const phases = this.#phases();
            phases.parentNode.insertBefore(this.#progressEl, phases);
        }
        const pct = total > 0 ? Math.round((current / total) * 100) : 0;
        const label = done
            ? `Scraping complete \u2014 ${total} source${total > 1 ? 's' : ''}`
            : `${current}/${total} sources`;
        this.#progressEl.innerHTML = `
            <div class="ro-progress-bar">
                <div class="ro-progress-fill" style="width: ${pct}%"></div>
            </div>
            <span class="ro-progress-label">${label}</span>
        `;
        if (done) this.#progressEl.classList.add('ro-progress-done');
    }

    #shortUrl(url) {
        try {
            const u = new URL(url);
            return u.hostname + (u.pathname.length > 30
                ? u.pathname.slice(0, 27) + '...'
                : u.pathname);
        } catch { return url; }
    }

    #esc(t) {
        const d = document.createElement('div');
        d.textContent = String(t ?? '');
        return d.innerHTML;
    }

    // ── Styles ────────────────────────────────────────────────

    static runOutputStyles = `
        /* Progress bar */
        .ro-progress {
            margin-bottom: .75rem;
            display: flex; align-items: center; gap: .75rem;
        }
        .ro-progress-bar {
            flex: 1; height: 6px; background: var(--surface-3, #1a1a2e);
            border-radius: 3px; overflow: hidden;
        }
        .ro-progress-fill {
            height: 100%; background: var(--accent, #4cc9f0);
            transition: width .3s ease;
        }
        .ro-progress-done .ro-progress-fill {
            background: var(--success, #22c55e);
        }
        .ro-progress-label {
            font-size: .75rem; color: var(--text-2, #aaa); white-space: nowrap;
        }

        /* Phases container */
        .ro-phases {
            display: flex; flex-direction: column; gap: .5rem;
        }

        /* Source cards */
        .ro-source-card {
            border: 1px solid var(--border, #333);
            border-radius: .5rem; overflow: hidden;
        }
        .ro-source-active { border-color: var(--accent, #4cc9f0); }
        .ro-source-done { border-color: var(--success, #22c55e); opacity: .85; }

        .ro-source-header {
            display: flex; align-items: center; gap: .5rem;
            padding: .5rem .75rem;
            background: var(--surface-2, #16213e);
            cursor: pointer; user-select: none;
        }
        .ro-source-header:hover { background: var(--surface-3, #1a1a2e); }

        .ro-source-spinner {
            display: inline-block; width: 1em; height: 1em;
            border: 2px solid var(--accent, #4cc9f0);
            border-top-color: transparent;
            border-radius: 50%;
            animation: ro-spin .8s linear infinite;
            flex-shrink: 0;
        }
        @keyframes ro-spin { to { transform: rotate(360deg); } }

        .ro-source-check {
            color: var(--success, #22c55e);
            font-weight: bold; flex-shrink: 0;
        }
        .ro-source-name {
            font-weight: 500; flex: 1; overflow: hidden;
            text-overflow: ellipsis; white-space: nowrap;
        }
        .ro-source-url {
            font-size: .7rem; color: var(--text-2, #aaa);
            text-decoration: none; flex-shrink: 0;
        }
        .ro-source-url:hover { text-decoration: underline; }
        .ro-source-count {
            font-size: .7rem; color: var(--success, #22c55e);
            background: rgba(34, 197, 94, 0.1);
            padding: .1rem .4rem; border-radius: .2rem;
        }

        /* Agent output inside source cards — override parent defaults */
        .ro-source-agent .agent-output {
            max-height: none;
            margin-top: 0;
        }

        /* Collapsible agent area */
        .ro-source-agent {
            max-height: 0; overflow: hidden;
            transition: max-height .3s ease;
            background: var(--surface-1, #0f0f23);
        }
        .ro-source-agent.ro-agent-open {
            max-height: 400px; overflow-y: auto;
        }

        /* Retired agent outputs — hidden, no layout */
        .ro-agent-captured { display: none; }

        /* Grant pills in source cards */
        .ro-source-grants {
            display: flex; flex-wrap: wrap; gap: .3rem;
            padding: .3rem .75rem;
        }
        .ro-source-grants:empty { display: none; }
        .ro-grant-pill {
            font-size: .7rem;
            padding: .15rem .5rem;
            background: var(--accent, #4cc9f0);
            color: var(--surface-1, #0f0f23);
            border-radius: 1rem;
            text-decoration: none;
            white-space: nowrap;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .ro-grant-pill:hover { opacity: .8; }

        /* Divider */
        .ro-divider {
            margin: 1rem 0 .5rem;
            padding: .4rem .75rem;
            font-size: .8rem;
            font-weight: 600;
            color: var(--text-2, #aaa);
            border-top: 1px solid var(--border, #333);
            border-bottom: 1px solid var(--border, #333);
        }

        /* Analysis cards */
        .ro-analysis-card {
            border: 1px solid var(--border, #333);
            border-radius: .5rem;
            overflow: hidden;
        }
        .ro-analysis-header {
            display: flex; align-items: center; gap: .5rem;
            padding: .5rem .75rem;
            background: var(--surface-2, #16213e);
            cursor: pointer; user-select: none;
        }
        .ro-analysis-header:hover { background: var(--surface-3, #1a1a2e); }

        .ro-analysis-status { flex-shrink: 0; }
        .ro-status-pending { color: var(--text-2, #aaa); }
        .ro-status-running { color: var(--warning, #f59e0b); animation: ro-pulse 1s ease infinite; }
        .ro-status-done { color: var(--success, #22c55e); }
        .ro-status-failed { color: var(--error, #f87171); }
        @keyframes ro-pulse { 50% { opacity: .4; } }

        .ro-analysis-title {
            flex: 1; overflow: hidden;
            text-overflow: ellipsis; white-space: nowrap;
            font-size: .85rem;
        }
        .ro-analysis-badge {
            font-size: .65rem;
            padding: .1rem .4rem;
            border-radius: .2rem;
        }
        .ro-badge-admissible { background: rgba(34, 197, 94, 0.15); color: var(--success, #22c55e); }
        .ro-badge-partial { background: rgba(245, 158, 11, 0.15); color: var(--warning, #f59e0b); }
        .ro-badge-non { background: rgba(248, 113, 113, 0.15); color: var(--error, #f87171); }
        .ro-badge-done { background: rgba(76, 201, 240, 0.15); color: var(--accent, #4cc9f0); }
        .ro-badge-failed { background: rgba(248, 113, 113, 0.15); color: var(--error, #f87171); }

        .ro-analysis-body {
            transition: max-height .3s ease;
            overflow: hidden;
        }
        .ro-analysis-body.ro-collapsed {
            max-height: 0;
        }
        .ro-analysis-body:not(.ro-collapsed) {
            max-height: 600px;
            overflow-y: auto;
            padding: .5rem;
        }

        /* Error */
        .ro-error {
            padding: .5rem .75rem;
            color: var(--error, #f87171);
            font-style: italic;
        }
    `;
}

customElements.define('ntx-run-output', NTXRunOutput);
export { NTXRunOutput };
