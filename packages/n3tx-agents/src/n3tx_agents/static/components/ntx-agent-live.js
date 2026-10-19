/**
 * <ntx-agent-live> — Real-time agent activity view.
 */
import { NTT } from '../core/NTT.js';
import { renderJson, initJsonToggle } from '../widgets/JsonTree.js';
import { NTTStreamAgent } from './ntx-stream-agent.js';

class NTTAgentLive extends NTTStreamAgent {
    get styles() {
        const parent = super.styles;
        const inherited = Array.isArray(parent) ? parent : parent ? [parent] : [];
        return [
            ...inherited,
            new URL('./ntx-agent-live.css', import.meta.url).href,
            new URL('../widgets/json-tree.css', import.meta.url).href,
        ];
    }

    #els;

    connectedCallback() {
        if (!this.getAttribute('method')) this.setAttribute('method', 'agentic_stream');
        super.connectedCallback();
        this.addEventListener('click', (e) => e.stopPropagation());
    }

    prerender() {
        this.shadowRoot.innerHTML = `
            <div class="live-panel">
                <div class="live-header">
                    <span class="live-title">${this.getAttribute('model') || ''} · Live</span>
                    <span class="live-status" id="status">idle</span>
                </div>
                <div class="live-input">
                    <textarea placeholder="Enter task..." rows="2"></textarea>
                    <button class="run-btn">Run</button>
                </div>
                <div class="live-log" id="log"></div>
                <div class="live-footer" id="footer"></div>
            </div>`;

        this.#cacheEls();
        this.#bindListeners();
        initJsonToggle(this.shadowRoot);
    }

    render() {
        if (this.#els && this.model) {
            const title = this.shadowRoot.querySelector('.live-title');
            if (title) title.textContent = `${this.model} · Live`;
        }
    }

    callMethod() {
        const task = this.#els.textarea.value.trim();
        if (!task) return;

        const ref = this.getAttribute('ref') || '';
        if (ref && !this.uuid) {
            const id = ref.includes('/') ? ref.split('/').pop() : ref;
            this.uuid = id;
            this.ntt = NTT.get(this.model + '/' + id);
        }

        this.#els.textarea.value = '';
        this.#els.status.textContent = 'running';
        this.#els.status.className = 'live-status running';
        this.#els.runBtn.disabled = true;
        this.value = { task };
        super.callMethod();
        this.addAgentEntry('task', `Task: ${this.escapeAgentHtml(task)}`);
    }

    STREAM_END(data) {
        super.STREAM_END(data);
        if (this.#els) {
            this.#els.status.textContent = 'done';
            this.#els.status.className = 'live-status done';
            this.#els.runBtn.disabled = false;
        }
    }

    STREAM_ERROR(err) {
        super.STREAM_ERROR(err);
        if (this.#els) {
            this.#els.status.textContent = 'error';
            this.#els.status.className = 'live-status error';
            this.#els.runBtn.disabled = false;
        }
    }

    getAgentOutputElement() {
        if (this.#els?.log) {
            this._bindAgentOutput(this.#els.log);
            return this.#els.log;
        }
        return super.getAgentOutputElement();
    }

    getAgentFooterElement() {
        return this.#els?.footer || super.getAgentFooterElement();
    }

    renderAgentToolArgs(args) {
        if (!args || (typeof args === 'object' && !Object.keys(args).length)) return '';
        return `<div class="tool-json">${renderJson(args)}</div>`;
    }

    renderAgentToolResult(result) {
        return renderJson(result);
    }

    scrollAgentToBottom() {
        const el = this.getAgentOutputElement();
        el.scrollTop = el.scrollHeight;
    }

    #cacheEls() {
        this.#els = {
            status: this.shadowRoot.getElementById('status'),
            log: this.shadowRoot.getElementById('log'),
            footer: this.shadowRoot.getElementById('footer'),
            textarea: this.shadowRoot.querySelector('textarea'),
            runBtn: this.shadowRoot.querySelector('.run-btn'),
        };
    }

    #bindListeners() {
        this.#els.runBtn.addEventListener('click', () => this.callMethod());
        this.#els.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.callMethod();
            }
        });
    }
}

customElements.define('ntx-agent-live', NTTAgentLive);
export { NTTAgentLive };
