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
import { renderJson, jsonTreeCSS, initJsonToggle } from '../widgets/JsonTree.js';

class NTTAgentLive extends NTTStream {
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
        this.shadowRoot.innerHTML = `<style>${NTTAgentLive.styles}</style>
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

    static styles = `
        :host { display: block; font-family: system-ui, -apple-system, sans-serif; font-size: .85rem; }

        .live-panel {
            border: 1px solid var(--border, #333); border-radius: .5rem;
            background: var(--surface-1, #1a1a2e);
            display: flex; flex-direction: column; max-height: 600px;
        }

        .live-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: .5rem .75rem;
            border-bottom: 1px solid var(--border, #333);
            background: var(--surface-2, #16213e);
            border-radius: .5rem .5rem 0 0;
        }
        .live-title { font-weight: 600; font-size: .7rem; text-transform: uppercase; letter-spacing: .05em; color: var(--text-2, #aaa); }
        .live-status {
            font-size: .65rem; font-weight: 600; text-transform: uppercase;
            padding: .15rem .4rem; border-radius: .2rem;
            background: var(--surface-3, #0f3460); color: var(--text-2, #aaa);
        }
        .live-status.running { background: var(--accent, #4cc9f0); color: #000; }
        .live-status.done { background: var(--success, #4ade80); color: #000; }
        .live-status.error { background: var(--error, #f87171); color: #000; }

        .live-input {
            display: flex; gap: .4rem; padding: .5rem .75rem;
            border-bottom: 1px solid var(--border, #333);
        }
        .live-input textarea {
            flex: 1; resize: none; padding: .4rem .5rem; border-radius: .3rem;
            background: var(--surface-3, #0f3460); color: var(--text-1, #eee);
            border: 1px solid var(--border, #333); font-family: inherit; font-size: .8rem;
            box-sizing: border-box;
        }
        .live-input textarea:focus { outline: 1px solid var(--accent, #4cc9f0); }
        .run-btn {
            padding: .4rem .8rem; border-radius: .3rem; border: none;
            background: var(--accent, #4cc9f0); color: #000; cursor: pointer;
            font-weight: 600; font-size: .8rem;
        }
        .run-btn:hover { filter: brightness(1.1); }
        .run-btn:disabled { opacity: .4; cursor: not-allowed; }

        .live-log {
            flex: 1; overflow-y: auto; padding: .5rem .75rem;
            min-height: 150px; max-height: 400px;
        }

        .entry { margin-bottom: .4rem; line-height: 1.5; }
        .entry-content { padding: .3rem .5rem; border-radius: .3rem; }

        /* Collapsible entries — show ~3 lines, click to expand */
        .entry.collapsible:not(.expanded) .entry-content {
            max-height: 4.2em;
            overflow: hidden;
            cursor: pointer;
        }
        .entry.collapsible:not(.expanded)::after {
            content: '\u25BE  more';
            display: block;
            text-align: center;
            font-size: .6rem;
            letter-spacing: .03em;
            color: var(--text-2, #aaa);
            cursor: pointer;
            padding: .1rem 0;
            opacity: .5;
        }
        .entry.collapsible:not(.expanded):hover::after { opacity: .8; }
        .entry.collapsible.expanded .entry-content { cursor: pointer; }

        .entry-task .entry-content {
            background: var(--surface-3, #0f3460); font-weight: 600;
            border-left: 2px solid var(--accent, #4cc9f0);
        }
        .entry-thinking .entry-content {
            background: rgba(167, 139, 250, 0.08);
            border-left: 2px solid var(--thinking, #a78bfa);
            word-break: break-word; line-height: 1.5;
        }
        .entry-thinking p { margin: .3em 0; }
        .entry-thinking code {
            background: rgba(0,0,0,.2); padding: .1em .3em; border-radius: 3px;
            font-size: .85em; font-family: 'SF Mono', Consolas, Monaco, monospace;
        }
        .entry-thinking pre {
            background: rgba(0,0,0,.2); border-radius: .3rem;
            padding: .3rem .5rem; overflow-x: auto; font-size: .8em; margin: .3em 0;
        }
        .entry-thinking pre code { background: none; padding: 0; }
        .entry-tool-call .entry-content {
            background: var(--surface-3, #0f3460);
            border-left: 2px solid var(--warning, #f59e0b);
        }
        .entry-tool-call.complete .entry-content {
            border-left-color: var(--success, #22c55e);
        }
        .entry-text-output .entry-content {
            word-break: break-word;
            border-left: 2px solid var(--text-accent, #38bdf8);
            line-height: 1.6;
        }
        .entry-text-output h1, .entry-text-output h2, .entry-text-output h3 {
            margin: .6em 0 .3em; font-size: 1.1em;
        }
        .entry-text-output p { margin: .4em 0; }
        .entry-text-output code {
            background: rgba(0,0,0,.3); padding: .1em .3em; border-radius: 3px;
            font-size: .85em; font-family: 'SF Mono', Consolas, Monaco, monospace;
        }
        .entry-text-output pre {
            background: rgba(0,0,0,.3); border-radius: .3rem;
            padding: .4rem .6rem; overflow-x: auto; font-size: .8em; margin: .4em 0;
        }
        .entry-text-output pre code { background: none; padding: 0; }
        .entry-text-output blockquote {
            border-left: 2px solid var(--text-2, #aaa); margin: .4em 0;
            padding: .2em .8em; opacity: .8;
        }
        .entry-text-output ul, .entry-text-output ol {
            padding-left: 1.5em; margin: .3em 0;
        }
        .entry-text-output a { color: var(--accent, #4cc9f0); }
        .entry-error .entry-content {
            background: rgba(248, 113, 113, 0.1);
            border-left: 2px solid var(--error, #f87171);
            color: var(--error, #f87171);
        }
        .entry-icon { opacity: .6; margin-right: .2rem; }
        .entry-spin { animation: spin 1s linear infinite; color: var(--warning, #fbbf24); font-size: .6rem; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .tool-json {
            margin: .3rem 0 0; padding: .3rem .5rem;
            background: rgba(0,0,0,.2); border-radius: .2rem;
            font-size: .75rem; font-family: 'SF Mono', Consolas, Monaco, monospace;
            overflow: auto; max-height: 200px;
        }
        .tool-result-text {
            margin-top: .3rem; font-size: .75rem;
            font-family: 'SF Mono', Consolas, Monaco, monospace;
            overflow: auto; max-height: 200px;
        }
        ${jsonTreeCSS}

        .thinking-anim::after { content: ''; animation: dots 1.5s steps(3, end) infinite; }
        @keyframes dots { 0% { content: '.'; } 33% { content: '..'; } 66% { content: '...'; } }
        .entry-thinking-active .entry-content:empty + .entry-content,
        .entry-thinking-active .thinking-anim { opacity: .5; font-style: italic; }
        .entry-thinking-active .entry-content { font-style: italic; opacity: .7; color: var(--thinking, #a78bfa); font-size: .8rem; }

        .live-footer {
            padding: .3rem .75rem; font-size: .65rem; color: var(--text-2, #aaa);
            border-top: 1px solid var(--border, #333);
            min-height: 1.2rem;
        }
    `;
}

customElements.define('ntx-agent-live', NTTAgentLive);
export { NTTAgentLive };
