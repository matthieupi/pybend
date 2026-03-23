/**
 * <ntx-run-panel> — Run launcher + live output + history.
 *
 * Plain HTMLElement (not Component) that composes:
 * - Launcher section with URL input + action buttons
 * - Dynamic ntx-stream-agent for live run output
 * - ntx-list for run history
 *
 * Flow: click button → POST /runs (create) → register NTT instance
 *       → append ntx-stream-agent → auto-trigger execute → live output.
 */
import { NTT } from '../core/NTT.js';

class NTXRunPanel extends HTMLElement {

    connectedCallback() {
        this.innerHTML = `
            <div class="run-launcher">
                <h3 class="run-launcher-title">New Run</h3>
                <div class="run-launcher-row">
                    <input type="url" class="run-url-input"
                           placeholder="Paste a URL to scan (leave empty for full run)...">
                    <button class="run-btn run-btn-scan">Scan URL</button>
                    <button class="run-btn run-btn-full">Full Run</button>
                </div>
                <div class="run-launcher-status"></div>
            </div>
            <div class="run-live-output"></div>
            <h4 class="run-history-title">Previous Runs</h4>
            <ntx-list model="Run" display="sm"></ntx-list>
        `;

        this.querySelector('.run-btn-scan').addEventListener('click', () => this.#startRun('adhoc'));
        this.querySelector('.run-btn-full').addEventListener('click', () => this.#startRun('full'));
    }

    async #startRun(type) {
        const urlInput = this.querySelector('.run-url-input');
        const statusEl = this.querySelector('.run-launcher-status');
        const adhocUrl = type === 'adhoc' ? urlInput.value.trim() : '';

        if (type === 'adhoc' && !adhocUrl) {
            statusEl.textContent = 'Please enter a URL to scan.';
            statusEl.className = 'run-launcher-status error';
            return;
        }

        // Disable buttons during creation
        const buttons = this.querySelectorAll('.run-btn');
        buttons.forEach(b => b.disabled = true);
        statusEl.textContent = 'Creating run...';
        statusEl.className = 'run-launcher-status';

        try {
            const token = localStorage.getItem('jwtToken');
            const resp = await fetch('/runs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-access-token': token,
                },
                body: JSON.stringify({ type, adhoc_url: adhocUrl }),
            });
            if (!resp.ok) throw new Error(`Failed to create run (${resp.status})`);
            const run = await resp.json();

            // Register the new run as an NTT instance so the stream agent
            // can resolve it via NTT.get('Run/{id}') in its load() method.
            const RunDC = NTT.get('Run');
            if (RunDC) {
                if (!RunDC.instances.has(String(run.id))) {
                    new RunDC(run);
                }
            }

            // Show run info header
            const output = this.querySelector('.run-live-output');
            output.innerHTML = '';

            const header = document.createElement('div');
            header.className = 'run-live-header';
            header.innerHTML = `
                <span class="run-id">#${run.id}</span>
                <span class="run-type ${type === 'full' ? 'type-full' : 'type-adhoc'}">${type}</span>
                <span class="run-status run-status-running">running</span>
                ${adhocUrl ? `<span class="run-live-url">${this.#esc(adhocUrl)}</span>` : ''}
            `;
            output.appendChild(header);

            // Create stream agent for live output
            const agent = document.createElement('ntx-stream-agent');
            agent.setAttribute('model', 'Run');
            agent.setAttribute('uuid', String(run.id));
            agent.setAttribute('method', 'execute');
            output.appendChild(agent);

            statusEl.textContent = '';

            // Hook into stream completion to update status header
            const statusPill = header.querySelector('.run-status');
            const origEnd = agent.STREAM_END?.bind(agent);
            agent.STREAM_END = (data) => {
                if (origEnd) origEnd(data);
                if (statusPill) {
                    statusPill.className = 'run-status run-status-complete';
                    statusPill.textContent = 'complete';
                }
                // Refresh the run list to show the completed run
                const list = this.querySelector('ntx-list');
                if (list?.proto?.pull) list.proto.pull();
            };
            const origError = agent.STREAM_ERROR?.bind(agent);
            agent.STREAM_ERROR = (data) => {
                if (origError) origError(data);
                if (statusPill) {
                    statusPill.className = 'run-status run-status-failed';
                    statusPill.textContent = 'failed';
                }
            };

            // Auto-trigger once schema is resolved
            const poll = setInterval(() => {
                if (agent.methodSchema) {
                    clearInterval(poll);
                    agent.callMethod();
                    buttons.forEach(b => b.disabled = false);
                    urlInput.value = '';
                }
            }, 50);

            // Safety timeout
            setTimeout(() => {
                clearInterval(poll);
                buttons.forEach(b => b.disabled = false);
            }, 10000);

        } catch (err) {
            statusEl.textContent = err.message;
            statusEl.className = 'run-launcher-status error';
            buttons.forEach(b => b.disabled = false);
        }
    }

    #esc(t) {
        const d = document.createElement('div');
        d.textContent = String(t ?? '');
        return d.innerHTML;
    }
}

customElements.define('ntx-run-panel', NTXRunPanel);
export { NTXRunPanel };
