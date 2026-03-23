/**
 * <ntx-run-item> — Custom run card renderer.
 *
 * Extends NTTItem with run-specific layout:
 * - Status badge (pending/running/complete/failed)
 * - Type pill (full/adhoc)
 * - Started/completed timestamps
 * - Grant + source counts
 * - View Report link for completed runs
 *
 * The execute method renders as generic ntx-stream-agent
 * via Run.__ui__['methods']['execute']['renderer'].
 *
 * Wired via Run.__ui__['renderer']['item'] = 'ntx-run-item'
 */
import { NTTItem } from './ntx-item.js';

class NTXRunItem extends NTTItem {

    md() {
        const r = this.value;
        if (!r || !r.id) return super.md();

        const schema = this.schema;
        const statusClass = this.#runStatusClass(r.status);
        const typeClass = r.type === 'full' ? 'type-full' : 'type-adhoc';

        const html = [];

        html.push(`
            <div class="run-header">
                <span class="run-id">#${r.id}</span>
                <span class="run-type ${typeClass}">${this.#esc(r.type || 'full')}</span>
                <span class="run-status ${statusClass}">${this.#esc(r.status || 'pending')}</span>
            </div>
        `);

        html.push('<div class="run-info-grid">');
        if (r.started_at) {
            html.push(`<div class="run-field">
                <span class="run-label">Started</span>
                <span class="run-value">${this.#formatDate(r.started_at)}</span>
            </div>`);
        }
        if (r.completed_at) {
            html.push(`<div class="run-field">
                <span class="run-label">Completed</span>
                <span class="run-value">${this.#formatDate(r.completed_at)}</span>
            </div>`);
        }
        html.push(`<div class="run-field">
            <span class="run-label">Grants Found</span>
            <span class="run-value run-count">${r.grants_found ?? '—'}</span>
        </div>`);
        html.push(`<div class="run-field">
            <span class="run-label">Sources</span>
            <span class="run-value run-count">${r.sources_covered ?? '—'}</span>
        </div>`);
        html.push('</div>');

        if (r.adhoc_url) {
            html.push(`<div class="run-url">
                <span class="run-label">URL</span>
                <a href="${this.#esc(r.adhoc_url)}" target="_blank" rel="noopener">${this.#esc(r.adhoc_url)}</a>
            </div>`);
        }

        if (r.error) {
            html.push(`<div class="run-error">${this.#esc(r.error)}</div>`);
        }

        // Report link for completed runs
        if (r.status === 'complete') {
            html.push(`<div class="run-actions">
                <a class="run-report-link" href="#report/${r.id}">View Report</a>
            </div>`);
        }

        // Standalone methods (execute button etc.)
        const methods = schema.methods || {};
        for (const [name, def] of Object.entries(methods)) {
            const tag = def.ui?.renderer || (def.stream ? 'ntx-stream' : 'ntx-method');
            const label = def.title || name;
            html.push(`<${tag}
                model="${schema.__name__}"
                uuid="${r.id}"
                method="${name}"
                layout="${def.ui?.layout || 'fieldset'}"
                label="${label}">
            </${tag}>`);
        }

        return html.join('');
    }

    sm() {
        const r = this.value;
        if (!r || !r.id) return super.sm();

        const statusClass = this.#runStatusClass(r.status);
        const typeClass = r.type === 'full' ? 'type-full' : 'type-adhoc';

        return `
            <span class="sm-name" data-value="id">#${r.id}</span>
            <span class="sm-fields">
                <span class="sm-field"><span class="run-type ${typeClass}">${this.#esc(r.type || 'full')}</span></span>
                <span class="sm-field"><span class="run-status ${statusClass}">${this.#esc(r.status || 'pending')}</span></span>
                <span class="sm-field">${this.#formatDate(r.started_at)}</span>
                <span class="sm-field">${r.grants_found ?? '—'} grants</span>
            </span>
        `;
    }

    #runStatusClass(status) {
        const map = {
            complete: 'run-status-complete',
            running: 'run-status-running',
            failed: 'run-status-failed',
            pending: 'run-status-pending',
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
        d.textContent = String(t ?? '');
        return d.innerHTML;
    }
}

customElements.define('ntx-run-item', NTXRunItem);
export { NTXRunItem };
