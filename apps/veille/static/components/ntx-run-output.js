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

    get styles() {
        const parent = super.styles;
        const inherited = Array.isArray(parent) ? parent : parent ? [parent] : [];
        return [...inherited, new URL('./ntx-run-output.css', import.meta.url).href];
    }

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
}

customElements.define('ntx-run-output', NTXRunOutput);
export { NTXRunOutput };
