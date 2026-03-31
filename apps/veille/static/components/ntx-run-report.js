/**
 * <ntx-run-report> — Per-run admissibility report panel.
 *
 * Displays a structured report for a completed scraping run, showing
 * grants grouped by admissibility classification with scores and justifications.
 *
 * Usage:
 *   <ntx-run-report run-id="42"></ntx-run-report>
 *
 * Observed attributes:
 *   run-id  — the numeric ID of the run to display
 */
import { config } from '../config.js';

const STYLES_URL = new URL('./ntx-run-report.css', import.meta.url).href;

class NTXRunReport extends HTMLElement {
    #els;
    #runId = null;
    #report = null;

    static get observedAttributes() {
        return ['run-id'];
    }

    attributeChangedCallback(name, oldVal, newVal) {
        if (name === 'run-id' && newVal && newVal !== oldVal) {
            this.#runId = newVal;
            if (this.shadowRoot) this.#loadReport();
        }
    }

    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `
            <link rel="stylesheet" href="${STYLES_URL}">
            <div class="panel">
                <div class="panel-header">
                    <div class="header-left">
                        <button class="back-btn" id="back-btn">← Back to Runs</button>
                        <h2 id="panel-title">Run Report</h2>
                    </div>
                    <span class="status-badge" id="run-status">loading</span>
                </div>

                <div class="run-meta" id="run-meta">
                    <div class="meta-placeholder">Loading run details...</div>
                </div>

                <div class="counts-bar" id="counts-bar" style="display:none">
                </div>

                <div class="report-body" id="report-body">
                    <div class="loading-placeholder">Loading report...</div>
                </div>
            </div>
        `;

        this.#els = {
            panelTitle:  this.shadowRoot.getElementById('panel-title'),
            runStatus:   this.shadowRoot.getElementById('run-status'),
            runMeta:     this.shadowRoot.getElementById('run-meta'),
            countsBar:   this.shadowRoot.getElementById('counts-bar'),
            reportBody:  this.shadowRoot.getElementById('report-body'),
            backBtn:     this.shadowRoot.getElementById('back-btn'),
        };

        this.#els.backBtn.addEventListener('click', () => {
            window.location.hash = 'runs';
        });

        // Stop click propagation (in case embedded in a card)
        this.addEventListener('click', (e) => e.stopPropagation());

        // Load if attribute was set before connectedCallback
        if (this.#runId) {
            this.#loadReport();
        }
    }

    // ── Data loading ──────────────────────────────────────────────

    async #loadReport() {
        if (!this.#runId || !this.#els) return;

        const token = localStorage.getItem('jwtToken');
        if (!token) {
            this.#showError('Not authenticated. Please log in.');
            return;
        }

        // Show loading state
        this.#els.reportBody.innerHTML = '<div class="loading-placeholder">Loading report...</div>';
        this.#els.countsBar.style.display = 'none';

        try {
            const resp = await fetch(`${config.API_URL}/runs/report?run_id=${this.#runId}`, {
                headers: { 'x-access-token': token },
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: resp.statusText }));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }

            this.#report = await resp.json();
            this.#render();

        } catch (err) {
            this.#showError(`Failed to load report: ${err.message}`);
        }
    }

    // ── Rendering ─────────────────────────────────────────────────

    #render() {
        const r = this.#report;
        if (!r) return;

        const run = r.run || {};
        const counts = r.counts || {};

        // Update header
        this.#els.panelTitle.textContent = `Run Report #${r.run_id}`;
        const runStatus = run.status || 'unknown';
        this.#els.runStatus.textContent = runStatus;
        this.#els.runStatus.className = `status-badge status-${runStatus}`;

        // Render run metadata bar
        this.#els.runMeta.innerHTML = `
            <div class="meta-grid">
                <div class="meta-item">
                    <span class="meta-label">Type</span>
                    <span class="meta-value">
                        <span class="type-pill type-${this.#esc(run.type || 'full')}">${this.#esc(run.type || 'full')}</span>
                    </span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Started</span>
                    <span class="meta-value">${this.#formatDate(run.started_at)}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Completed</span>
                    <span class="meta-value">${this.#formatDate(run.completed_at)}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Grants Found</span>
                    <span class="meta-value meta-count">${counts.total ?? 0}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Sources</span>
                    <span class="meta-value meta-count">${run.sources_covered ?? '—'}</span>
                </div>
            </div>
        `;

        // Render summary counts bar
        this.#els.countsBar.style.display = '';
        this.#els.countsBar.innerHTML = `
            <div class="count-pill count-admissible">
                <span class="count-num">${counts.admissible ?? 0}</span>
                <span class="count-label">Admissible</span>
            </div>
            <div class="count-pill count-partial">
                <span class="count-num">${counts.partially_admissible ?? 0}</span>
                <span class="count-label">Partial</span>
            </div>
            <div class="count-pill count-nonadmissible">
                <span class="count-num">${counts.non_admissible ?? 0}</span>
                <span class="count-label">Non-admissible</span>
            </div>
            <div class="count-pill count-new">
                <span class="count-num">${counts.new ?? 0}</span>
                <span class="count-label">Unanalyzed</span>
            </div>
        `;

        // Render grouped grant sections
        const admissible        = r.admissible        || [];
        const partiallyAdmissible = r.partially_admissible || [];
        const nonAdmissible     = r.non_admissible    || [];
        const unanalyzed        = r.new               || [];

        const totalGrants = counts.total || 0;

        if (totalGrants === 0) {
            this.#els.reportBody.innerHTML = `
                <div class="empty-state">
                    <p>No grants found in this run.</p>
                </div>
            `;
            return;
        }

        this.#els.reportBody.innerHTML = `
            ${this.#renderSection('Admissible', admissible, 'admissible')}
            ${this.#renderSection('Partially Admissible', partiallyAdmissible, 'partial')}
            ${this.#renderSection('Non-Admissible', nonAdmissible, 'nonadmissible')}
            ${this.#renderSection('Unanalyzed', unanalyzed, 'new')}
        `;
    }

    #renderSection(title, grants, colorClass) {
        const grantHtml = grants.length === 0
            ? '<div class="section-empty">None</div>'
            : grants.map(g => this.#renderGrantCard(g)).join('');

        return `
            <div class="report-section">
                <div class="section-header section-header-${colorClass}">
                    <span class="section-title">${this.#esc(title)}</span>
                    <span class="section-count">${grants.length}</span>
                </div>
                <div class="section-grants">
                    ${grantHtml}
                </div>
            </div>
        `;
    }

    #renderGrantCard(grant) {
        const score = grant.admissibility_score != null
            ? Math.round(grant.admissibility_score * 100)
            : (grant.score != null ? Math.round(grant.score * 100) : null);

        const scoreHtml = score != null
            ? `<span class="score-pill ${this.#scoreClass(score / 100)}">${score}%</span>`
            : `<span class="score-pill score-none">—</span>`;

        // Truncate justification to ~200 chars for preview
        const reasoning = grant.admissibility_reasoning || grant.justification || '';
        const reasoningPreview = reasoning.length > 200
            ? reasoning.slice(0, 200) + '…'
            : reasoning;

        const deadlineHtml = grant.deadline
            ? `<span class="grant-meta-item">Deadline: ${this.#esc(grant.deadline)}</span>`
            : '';

        const funderHtml = grant.funder
            ? `<span class="grant-meta-item">${this.#esc(grant.funder)}</span>`
            : '';

        return `
            <div class="grant-card">
                <div class="grant-card-header">
                    ${scoreHtml}
                    <a class="grant-title-link" href="#analyze/${grant.id}">
                        ${this.#esc(grant.title || `Grant #${grant.id}`)}
                    </a>
                </div>
                <div class="grant-card-meta">
                    ${funderHtml}
                    ${deadlineHtml}
                </div>
                ${reasoningPreview ? `
                <div class="grant-reasoning">
                    ${this.#esc(reasoningPreview)}
                </div>` : ''}
            </div>
        `;
    }

    #showError(msg) {
        if (!this.#els) return;
        this.#els.reportBody.innerHTML = `
            <div class="error-state">
                <p>${this.#esc(msg)}</p>
            </div>
        `;
    }

    // ── Helpers ───────────────────────────────────────────────────

    #scoreClass(score) {
        if (score == null) return 'score-none';
        if (score >= 0.7) return 'score-high';
        if (score >= 0.4) return 'score-mid';
        return 'score-low';
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
        d.textContent = String(t);
        return d.innerHTML;
    }
}

customElements.define('ntx-run-report', NTXRunReport);
export { NTXRunReport };
