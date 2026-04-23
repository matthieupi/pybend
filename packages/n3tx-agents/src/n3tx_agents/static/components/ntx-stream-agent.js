import { NTTStream } from './ntx-stream.js';
import { showToast } from '../utils/Toast.js';

export class NTTStreamAgent extends NTTStream {

    get styles() {
        const parent = super.styles;
        const inherited = Array.isArray(parent) ? parent : parent ? [parent] : [];
        return [...inherited, new URL('./ntx-stream-agent.css', import.meta.url).href];
    }

    #toolCards = new Map();
    #textBuf = '';
    #textRendered = 0;
    #textTimer = null;
    #thinkBuf = '';
    #thinkRendered = 0;
    #thinkTimer = null;
    #outputEl = null;

    // ── UPPERCASE handlers ──

    THINKING(data, meta) {
        const text = data?.text || '';
        if (!text) { this.#setThinking(true); return; }

        this.#thinkBuf += text;
        let entry = this.#output().querySelector('.entry-thinking-active');
        if (!entry) {
            entry = this.#addEntry('thinking', '');
            entry.classList.add('entry-thinking-active');
        }
        this.#scheduleRender(entry, 'think');
    }

    TOOL_CALL(data, meta) {
        this.#setThinking(false);
        // Normalize: args may arrive as JSON string from some LLM providers
        if (typeof data.args === 'string') {
            try { data.args = JSON.parse(data.args); } catch { data.args = { raw: data.args }; }
        }
        const argsHtml = data.args && Object.keys(data.args).length
            ? `<div class="tool-json">${this.#esc(JSON.stringify(data.args, null, 2))}</div>` : '';
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
            const resultStr = typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2);
            resultDiv.textContent = resultStr.slice(0, 500);
            card.querySelector('.entry-content').appendChild(resultDiv);
        } else {
            this.#addEntry('tool-result',
                `<span class="entry-icon">\u2714</span> ${this.#esc(data.tool || 'Tool')}: result received`);
        }
    }

    TEXT(data, meta) {
        this.#setThinking(false);
        this.#textBuf += (data?.text || '');

        let entry = this.#output().querySelector('.entry-text-output');
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
            let footer = this.#output().querySelector('.stream-footer');
            if (!footer) {
                footer = document.createElement('div');
                footer.className = 'stream-footer';
                this.#output().appendChild(footer);
            }
            footer.innerHTML =
                `<span>Tokens: ${usage.input_tokens || 0} in / ${usage.output_tokens || 0} out</span>` +
                (data.tool_calls ? ` &middot; <span>${data.tool_calls} tool calls</span>` : '');
        }
        this.#scrollToBottom();
    }

    STREAM_END(data) {
        this.#setThinking(false);
        this.#flushRender();
        // Refresh parent entity
        if (this.ntt?.pull) this.ntt.pull();
    }

    STREAM_ERROR(data) {
        this.#setThinking(false);
        this.#flushRender();
        const msg = (typeof data === 'string') ? data
            : data?.message || data?.detail || data?.error || 'Stream error';
        this.#addEntry('error', `Error: ${this.#esc(msg)}`);
        showToast(msg, 'error');
    }

    // ── Rendering ──

    render() {
        super.render();
        // Replace NTTStream's simple output with our rich output container
        let el = this.shadowRoot.querySelector('.stream-output');
        if (el) el.remove();
    }

    callMethod() {
        this.#toolCards.clear();
        this.#textBuf = ''; this.#textRendered = 0; clearTimeout(this.#textTimer);
        this.#thinkBuf = ''; this.#thinkRendered = 0; clearTimeout(this.#thinkTimer);
        this.#outputEl = null;
        super.callMethod();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        clearTimeout(this.#textTimer);
        clearTimeout(this.#thinkTimer);
    }

    // ── Internal helpers ──

    /** Get or create the output container for agent entries */
    #output() {
        if (this.#outputEl) return this.#outputEl;
        let el = this.shadowRoot.querySelector('.agent-output');
        if (!el) {
            el = document.createElement('div');
            el.className = 'agent-output';
            this.shadowRoot.appendChild(el);

            // Click-to-expand/collapse on collapsible entries (event delegation)
            el.addEventListener('click', (e) => {
                const entry = e.target.closest('.entry.collapsible');
                if (entry) entry.classList.toggle('expanded');
            });
        }
        this.#outputEl = el;
        return el;
    }

    #addEntry(type, html) {
        const el = document.createElement('div');
        el.className = `entry entry-${type}`;
        el.innerHTML = `<div class="entry-content">${html}</div>`;
        this.#output().appendChild(el);
        this.#scrollToBottom();
        return el;
    }

    #setThinking(on) {
        const output = this.#output();
        let el = output.querySelector('.entry-thinking-active');
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
        const output = this.#output();
        const textEntry = output.querySelector('.entry-text-output');
        if (textEntry) this.#renderMd(textEntry, 'text');
        const thinkEntry = output.querySelector('.entry-thinking-active');
        if (thinkEntry) this.#renderMd(thinkEntry, 'think');
    }

    #scrollToBottom() {
        const el = this.#output();
        // Only auto-scroll if user is at the very bottom (within 10px)
        const atBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 100;
        if (atBottom) {
            el.scrollTop = el.scrollHeight;
        }
    }

    #esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

}

customElements.define('ntx-stream-agent', NTTStreamAgent);
