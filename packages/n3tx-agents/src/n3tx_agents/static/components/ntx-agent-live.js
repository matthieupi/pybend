/**
 * <ntx-agent-live> — Real-time agent activity view.
 *
 * Shows structured activity log with typed events:
 * thinking, tool calls, tool results, text generation.
 *
 * Extends NTTStream for TX-based streaming (replaces StreamActor).
 *
 * Attributes:
 *   model  — Class name (e.g., 'AgentActor')
 *   ref    — Entity ref (e.g., 'agents/1')
 *   method — Streaming method name (default: 'agentic_stream')
 *
 * Usage:
 *   <ntx-agent-live model="AgentActor" ref="agents/1"></ntx-agent-live>
 */
import { NTTStream } from './ntx-stream.js';
import { NTT } from '../core/NTT.js';
import { renderJson, initJsonToggle } from '../widgets/JsonTree.js';

class NTTAgentLive extends NTTStream {
    get styles() {
        const parent = super.styles;
        const inherited = Array.isArray(parent) ? parent : parent ? [parent] : [];
        return [
            ...inherited,
            new URL('./ntx-agent-live.css', import.meta.url).href,
            new URL('../widgets/json-tree.css', import.meta.url).href,
        ];
    }

    #toolCards = new Map();
    #els;
    #textBuf = ''; #textRendered = 0; #textTimer = null;
    #thinkBuf = ''; #thinkRendered = 0; #thinkTimer = null;

    connectedCallback() {
        if (!this.getAttribute('method')) this.setAttribute('method', 'agentic_stream');
        super.connectedCallback();
        this.addEventListener('click', (e) => e.stopPropagation());
    }

    prerender() {
        this.shadowRoot.innerHTML = `
            <div class="live-panel">
                <div class="live-header">
                    <span class="live-title">${this.getAttribute('model') || ''} &middot; Live</span>
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

        // Click-to-expand/collapse on collapsible entries
        this.#els.log.addEventListener('click', (e) => {
            if (e.target.closest('.jt-toggle') || e.target.closest('a')) return;
            const entry = e.target.closest('.entry.collapsible');
            if (entry) entry.classList.toggle('expanded');
        });
    }

    render() {
        // Additive — never wipes prerender() DOM.
        // Update title with resolved model name if available.
        if (this.#els && this.model) {
            const title = this.shadowRoot.querySelector('.live-title');
            if (title) title.textContent = `${this.model} · Live`;
        }
    }

    callMethod() {
        const task = this.#els.textarea.value.trim();
        if (!task) return;

        // Extract uuid from ref attribute if needed
        const ref = this.getAttribute('ref') || '';
        if (ref && !this.uuid) {
            const id = ref.includes('/') ? ref.split('/').pop() : ref;
            this.uuid = id;
            this.ntt = NTT.get(this.model + '/' + id);
        }

        this.#els.textarea.value = '';
        this.#reset();
        this.#els.status.textContent = 'running';
        this.#els.status.className = 'live-status running';
        this.#els.runBtn.disabled = true;
        this.#addEntry('task', `Task: ${task}`);

        this.value = { task };
        super.callMethod();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        clearTimeout(this.#textTimer);
        clearTimeout(this.#thinkTimer);
    }

    // -- TX inbox handlers (UPPERCASE) ------------------------------------------

    THINKING(data, meta) {
        const text = data?.text || '';
        if (!text) { this.#setThinking(true); return; }

        this.#thinkBuf += text;
        let entry = this.#els.log.querySelector('.entry-thinking-active');
        if (!entry) {
            entry = this.#addEntry('thinking', '');
            entry.classList.add('entry-thinking-active');
        }
        this.#scheduleRender(entry, 'think');
    }

    TOOL_CALL(data, meta) {
        this.#setThinking(false);
        if (typeof data.args === 'string') {
            try { data.args = JSON.parse(data.args); } catch { data.args = { raw: data.args }; }
        }
        const argsHtml = data.args && Object.keys(data.args).length
            ? `<div class="tool-json">${renderJson(data.args)}</div>` : '';
        const entry = this.#addEntry('tool-call',
            `<span class="entry-icon">\u2699</span> Calling <strong>${this.#esc(data.tool)}</strong>${argsHtml}`);
        const spinner = document.createElement('span');
        spinner.className = 'entry-spin';
        spinner.textContent = ' \u25CF';
        entry.querySelector('.entry-content').appendChild(spinner);
        if (argsHtml) entry.classList.add('collapsible');
        if (data.call_id) this.#toolCards.set(data.call_id, entry);
    }

    TOOL_RESULT(data, meta) {
        const card = data.call_id && this.#toolCards.get(data.call_id);
        if (card) {
            card.querySelector('.entry-spin')?.remove();
            card.classList.add('complete');
            const resultDiv = document.createElement('div');
            resultDiv.className = 'tool-result-text';
            resultDiv.innerHTML = renderJson(data.result);
            card.querySelector('.entry-content').appendChild(resultDiv);
        } else {
            this.#addEntry('tool-result',
                `<span class="entry-icon">\u2714</span> ${this.#esc(data.tool)}: <div class="tool-result-text">${renderJson(data.result)}</div>`);
        }
    }

    TEXT(data, meta) {
        this.#setThinking(false);
        this.#textBuf += (data?.text || '');

        let entry = this.#els.log.querySelector('.entry-text-output');
        if (!entry) {
            entry = this.#addEntry('text-output', '');
            entry.querySelector('.entry-content').classList.add('entry-text-output-content');
            entry.classList.add('entry-text-output');
        }
        this.#scheduleRender(entry, 'text');
    }

    DONE(data, meta) {
        this.#setThinking(false);
        this.#flushRender();
        const usage = data?.usage;
        if (usage) {
            this.#els.footer.innerHTML =
                `<span>Tokens: ${usage.input_tokens || 0} in / ${usage.output_tokens || 0} out</span>` +
                (data.tool_calls ? ` &middot; <span>${data.tool_calls} tool calls</span>` : '');
        }
        this.#scrollToBottom();
    }

    STREAM_END(data) {
        if (this.#els) {
            this.#els.status.textContent = 'done';
            this.#els.status.className = 'live-status done';
            this.#els.runBtn.disabled = false;
        }
        this.#setThinking(false);
    }

    STREAM_ERROR(err) {
        if (this.#els) {
            this.#els.status.textContent = 'error';
            this.#els.status.className = 'live-status error';
            this.#els.runBtn.disabled = false;
        }
        this.#addEntry('error', `Error: ${err?.message || err?.detail || err}`);
    }

    // -- Internal helpers -------------------------------------------------------

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
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.callMethod(); }
        });
    }

    #reset() {
        this.#els.log.innerHTML = '';
        this.#els.footer.innerHTML = '';
        this.#toolCards.clear();
        this.#textBuf = ''; this.#textRendered = 0; clearTimeout(this.#textTimer);
        this.#thinkBuf = ''; this.#thinkRendered = 0; clearTimeout(this.#thinkTimer);
    }

    #addEntry(type, html) {
        const el = document.createElement('div');
        el.className = `entry entry-${type}`;
        el.innerHTML = `<div class="entry-content">${html}</div>`;
        this.#els.log.appendChild(el);
        this.#scrollToBottom();
        return el;
    }

    #setThinking(on) {
        let el = this.#els.log.querySelector('.entry-thinking-active');
        if (on && !el) {
            el = this.#addEntry('thinking', '<span class="thinking-anim">Thinking</span>');
            el.classList.add('entry-thinking-active');
        } else if (!on && el) {
            const content = el.querySelector('.entry-content');
            if (content?.querySelector('.thinking-anim')) {
                el.remove();
            } else {
                clearTimeout(this.#thinkTimer);
                this.#renderMd(el, 'think');
                el.classList.remove('entry-thinking-active');
                el.classList.add('collapsible');
                this.#thinkBuf = ''; this.#thinkRendered = 0;
            }
        }
    }

    #scheduleRender(entry, kind) {
        const buf = kind === 'text' ? this.#textBuf : this.#thinkBuf;
        const rendered = kind === 'text' ? this.#textRendered : this.#thinkRendered;
        const fresh = buf.slice(rendered);
        const hasNewline = fresh.includes('\n');

        if (kind === 'text') {
            clearTimeout(this.#textTimer);
            if (hasNewline) this.#renderMd(entry, kind);
            else this.#textTimer = setTimeout(() => this.#renderMd(entry, kind), 300);
        } else {
            clearTimeout(this.#thinkTimer);
            if (hasNewline) this.#renderMd(entry, kind);
            else this.#thinkTimer = setTimeout(() => this.#renderMd(entry, kind), 300);
        }
        this.#scrollToBottom();
    }

    #renderMd(entry, kind) {
        if (!entry) return;
        const buf = kind === 'text' ? this.#textBuf : this.#thinkBuf;
        if (!buf) return;
        const content = entry.querySelector('.entry-text-output-content')
            || entry.querySelector('.entry-content');
        if (typeof marked !== 'undefined' && marked.parse) {
            content.innerHTML = marked.parse(buf);
        } else {
            content.textContent = buf;
        }
        if (kind === 'text') this.#textRendered = buf.length;
        else this.#thinkRendered = buf.length;
        this.#scrollToBottom();
    }

    #flushRender() {
        clearTimeout(this.#textTimer);
        clearTimeout(this.#thinkTimer);
        const textEntry = this.#els.log.querySelector('.entry-text-output');
        if (textEntry) this.#renderMd(textEntry, 'text');
        const thinkEntry = this.#els.log.querySelector('.entry-thinking-active');
        if (thinkEntry) this.#renderMd(thinkEntry, 'think');
    }

    #scrollToBottom() {
        this.#els.log.scrollTop = this.#els.log.scrollHeight;
    }

    #esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }
}

customElements.define('ntx-agent-live', NTTAgentLive);
export { NTTAgentLive };
