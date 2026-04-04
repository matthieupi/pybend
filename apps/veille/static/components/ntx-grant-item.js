/**
 * <ntx-grant-item> — Custom grant card renderer.
 *
 * Extends NTTItem with grant-specific rendering:
 * - Score color coding (high/mid/low)
 * - Status pills (admissible/inadmissible/new/analyzing)
 * - Justification truncation
 * - Funder, deadline, amount display
 *
 * Wired via Grant.__ui__['renderer']['item'] = 'ntx-grant-item'
 */
import { NTTItem } from './ntx-item.js';

const OPEN_ICON = `
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path d="M14 5H19V10" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"></path>
        <path d="M19 5L10 14" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"></path>
        <path d="M19 14V19H5V5H10" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"></path>
    </svg>
`;

class NTXGrantItem extends NTTItem {

    get styles() {
        const base = super.styles;
        return [
            ...(Array.isArray(base) ? base : [base]),
            new URL('./ntx-grant-item.css', import.meta.url).href,
        ];
    }

    md() {
        const g = this.value;
        if (!g || !g.id) return super.md();

        const schema = this.schema;
        const score = g.admissibility_score != null
            ? `${Math.round(g.admissibility_score * 100)}%` : 'N/A';
        const amount = this.#formatAmount(g.amount_min, g.amount_max);
        const statusClass = this.#statusClass(g.status);
        const scoreClass = this.#scoreClass(g.admissibility_score);
        const reasoningPreview = this.#previewReasoning(g.admissibility_reasoning);

        const html = [];

        html.push(`<div class="grant-header">
            <span class="grant-status ${statusClass}">${this.#esc(g.status || 'new')}</span>
            <a class="grant-open-link" href="#analyze/${g.id}" title="View details" aria-label="View details">
                ${OPEN_ICON}
            </a>
        </div>`);

        html.push(`<h3 class="grant-title">${this.#esc(g.title)}</h3>`);

        html.push('<div class="grant-info-grid">');
        html.push(`<div class="grant-field">
            <span class="grant-label">Funder</span>
            <span class="grant-value grant-value--truncate">${this.#esc(g.funder || '—')}</span>
        </div>`);
        html.push(`<div class="grant-field grant-field--align-end">
            <span class="grant-label">Score</span>
            <span class="grant-value grant-score ${scoreClass}">${score}</span>
        </div>`);
        html.push(`<div class="grant-field">
            <span class="grant-label">Deadline</span>
            <span class="grant-value">${this.#esc(g.deadline || '—')}</span>
        </div>`);
        html.push(`<div class="grant-field grant-field--align-end">
            <span class="grant-label">Amount</span>
            <span class="grant-value grant-value--amount">${this.#esc(amount)}</span>
        </div>`);
        html.push('</div>');

        if (reasoningPreview) {
            html.push(`<div class="grant-justification">
                <span class="grant-label">Analysis</span>
                <div class="grant-justification-text">${this.#esc(reasoningPreview)}</div>
            </div>`);
        }

        const methods = schema.methods || {};
        const methodHtml = Object.entries(methods).map(([name, def]) => {
            const tag = def.ui?.renderer || (def.stream ? 'ntx-stream' : 'ntx-method');
            const label = def.title || name;
            return `<${tag}
                model="${schema.__name__}"
                uuid="${g.id}"
                method="${name}"
                layout="button"
                label="${label}"
                button-label="Run"
                show-label>
            </${tag}>`;
        }).join('');

        html.push(`<div class="grant-actions">
            ${methodHtml}
            <a class="grant-details-link" href="#analyze/${g.id}">Details</a>
        </div>`);

        return html.join('');
    }

    lg() {
        const g = this.value;
        if (!g || !g.id) return super.lg();

        const schema = this.schema;
        const score = g.admissibility_score != null
            ? `${Math.round(g.admissibility_score * 100)}%` : 'N/A';
        const statusClass = this.#statusClass(g.status);
        const scoreClass = this.#scoreClass(g.admissibility_score);

        const html = [];

        // Action buttons
        html.push(`<div class="card-actions">
            <button class="edit-btn mode-display" title="Edit"></button>
        </div>`);

        // Grant header
        html.push(`
            <div class="grant-header">
                <h3 class="grant-title">${this.#esc(g.title)}</h3>
                <span class="grant-status ${statusClass}">${this.#esc(g.status || 'new')}</span>
            </div>
        `);

        // Info grid
        html.push('<div class="grant-info-grid">');
        if (g.funder) {
            html.push(`<div class="grant-field">
                <span class="grant-label">Funder</span>
                <span class="grant-value">${this.#esc(g.funder)}</span>
            </div>`);
        }
        html.push(`<div class="grant-field">
            <span class="grant-label">Score</span>
            <span class="grant-value grant-score ${scoreClass}">${score}</span>
        </div>`);
        if (g.deadline) {
            html.push(`<div class="grant-field">
                <span class="grant-label">Deadline</span>
                <span class="grant-value">${this.#esc(g.deadline)}</span>
            </div>`);
        }
        if (g.amount_min != null || g.amount_max != null) {
            const amt = g.amount_min != null && g.amount_max != null
                ? `$${g.amount_min.toLocaleString()} – $${g.amount_max.toLocaleString()}`
                : g.amount_min != null ? `$${g.amount_min.toLocaleString()}+`
                : `Up to $${g.amount_max.toLocaleString()}`;
            html.push(`<div class="grant-field">
                <span class="grant-label">Amount</span>
                <span class="grant-value">${amt}</span>
            </div>`);
        }
        html.push('</div>');

        // URLs
        if (g.url || g.source_url) {
            html.push('<div class="grant-urls">');
            if (g.url) {
                html.push(`<div class="grant-field">
                    <span class="grant-label">URL</span>
                    <a href="${this.#esc(g.url)}" target="_blank" rel="noopener">${this.#esc(g.url)}</a>
                </div>`);
            }
            if (g.source_url) {
                html.push(`<div class="grant-field">
                    <span class="grant-label">Source</span>
                    <a href="${this.#esc(g.source_url)}" target="_blank" rel="noopener">${this.#esc(g.source_url)}</a>
                </div>`);
            }
            html.push('</div>');
        }

        // Description
        if (g.description) {
            html.push(`<div class="grant-section">
                <div class="grant-description">${this.#esc(g.description)}</div>
            </div>`);
        }

        // Eligibility criteria
        if (g.eligibility_criteria && g.eligibility_criteria.length) {
            html.push(`<div class="grant-section">
                <span class="grant-label">Eligibility Criteria</span>
                <ul class="grant-list">${g.eligibility_criteria.map(c => `<li>${this.#esc(c)}</li>`).join('')}</ul>
            </div>`);
        }

        // Required documents
        if (g.required_documents && g.required_documents.length) {
            html.push(`<div class="grant-section">
                <span class="grant-label">Required Documents</span>
                <ul class="grant-list">${g.required_documents.map(d => `<li>${this.#esc(d)}</li>`).join('')}</ul>
            </div>`);
        }

        // Application process
        if (g.application_process) {
            html.push(`<div class="grant-section">
                <span class="grant-label">Application Process</span>
                <div class="grant-description">${this.#esc(g.application_process)}</div>
            </div>`);
        }

        // Metadata row
        const metaParts = [];
        if (g.language && g.language !== 'en') metaParts.push(`Language: ${this.#esc(g.language)}`);
        if (g.discovered_at) metaParts.push(`Discovered: ${this.#esc(g.discovered_at)}`);
        if (metaParts.length) {
            html.push(`<div class="grant-meta">${metaParts.join(' · ')}</div>`);
        }

        // Admissibility reasoning
        if (g.admissibility_reasoning) {
            html.push(`<div class="grant-justification">
                <span class="grant-label">Analysis</span>
                <div class="grant-justification-text">${this.#esc(g.admissibility_reasoning)}</div>
            </div>`);
        }

        // Standalone methods (analyze button etc.)
        const methods = schema.methods || {};
        const methodHtml = Object.entries(methods).map(([name, def]) => {
            const tag = def.ui?.renderer || (def.stream ? 'ntx-stream' : 'ntx-method');
            const label = def.title || name;
            return `<${tag}
                model="${schema.__name__}"
                uuid="${g.id}"
                method="${name}"
                layout="${def.ui?.layout || 'button'}"
                label="${label}">
            </${tag}>`;
        }).join('');
        if (methodHtml) {
            html.push(`<div class="grant-actions">${methodHtml}</div>`);
        }

        return html.join('');
    }

    sm() {
        const g = this.value;
        if (!g || !g.id) return super.sm();

        const score = g.admissibility_score != null
            ? `${Math.round(g.admissibility_score * 100)}%` : '';
        const statusClass = this.#statusClass(g.status);
        const scoreClass = this.#scoreClass(g.admissibility_score);

        return `
            <div class="sm-body" style="flex:1;min-width:0">
                <span class="sm-name" data-value="title">${this.#esc(g.title)}</span>
                <span class="sm-fields">
                    ${g.funder ? `<span class="sm-field">${this.#esc(g.funder)}</span>` : ''}
                    <span class="sm-field"><span class="grant-status ${statusClass}">${this.#esc(g.status || 'new')}</span></span>
                    ${score ? `<span class="sm-field grant-score ${scoreClass}">${score}</span>` : ''}
                </span>
            </div>
        `;
    }

    #statusClass(status) {
        const map = {
            new: 'status-new',
            analyzing: 'status-analyzing',
            admissible: 'status-admissible',
            'partially admissible': 'status-partial',
            'non-admissible': 'status-inadmissible',
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

    #formatAmount(min, max) {
        if (min != null && max != null) {
            return `$${min.toLocaleString()} - $${max.toLocaleString()}`;
        }
        if (min != null) {
            return `$${min.toLocaleString()}+`;
        }
        if (max != null) {
            return `Up to $${max.toLocaleString()}`;
        }
        return '—';
    }

    #previewReasoning(reasoning) {
        if (!reasoning) return '';
        const text = String(reasoning).replace(/\s+/g, ' ').trim();
        if (text.length <= 220) return text;
        return `${text.slice(0, 217).trimEnd()}...`;
    }

    #esc(t) {
        const d = document.createElement('div');
        d.textContent = String(t ?? '');
        return d.innerHTML;
    }
}

customElements.define('ntx-grant-item', NTXGrantItem);
export { NTXGrantItem };
