import { NTTStream } from './ntx-stream.js';
import { showToast } from '../utils/Toast.js';

export class NTTStreamAgent extends NTTStream {

    get styles() {
        const parent = super.styles;
        const inherited = Array.isArray(parent) ? parent : parent ? [parent] : [];
        return [...inherited, new URL('./ntx-stream-agent.css', import.meta.url).href];
    }

    _toolCards = new Map();
    _textBuf = '';
    _textRendered = 0;
    _textTimer = null;
    _thinkBuf = '';
    _thinkRendered = 0;
    _thinkTimer = null;
    _outputEl = null;

    THINKING(data, meta) {
        const text = data?.text || '';
        if (!text) {
            this.setThinkingState(true);
            return;
        }

        this._thinkBuf += text;
        let entry = this.getAgentOutputElement().querySelector('.entry-thinking-active');
        if (!entry) {
            entry = this.addAgentEntry('thinking', '');
            entry.classList.add('entry-thinking-active');
        }
        this.scheduleAgentRender(entry, 'think');
    }

    TOOL_CALL(data, meta) {
        this.setThinkingState(false);
        if (typeof data.args === 'string') {
            try { data.args = JSON.parse(data.args); } catch { data.args = { raw: data.args }; }
        }
        const argsHtml = this.renderAgentToolArgs(data.args);
        const entry = this.addAgentEntry('tool-call',
            `<span class="entry-icon">⚙</span> Calling <strong>${this.escapeAgentHtml(data.tool || 'Tool')}</strong>${argsHtml}`);
        const spinner = document.createElement('span');
        spinner.className = 'entry-spin';
        spinner.textContent = ' ●';
        entry.querySelector('.entry-content').appendChild(spinner);
        if (argsHtml) entry.classList.add('collapsible');
        if (data.call_id) this._toolCards.set(data.call_id, entry);
        this.scrollAgentToBottom();
    }

    TOOL_RESULT(data, meta) {
        const card = data.call_id && this._toolCards.get(data.call_id);
        const resultHtml = this.renderAgentToolResult(data.result);
        if (card) {
            card.querySelector('.entry-spin')?.remove();
            card.classList.add('complete');
            if (resultHtml) {
                const resultDiv = document.createElement('div');
                resultDiv.className = 'tool-result-text';
                resultDiv.innerHTML = resultHtml;
                card.querySelector('.entry-content').appendChild(resultDiv);
            }
        } else {
            this.addAgentEntry('tool-result',
                `<span class="entry-icon">✔</span> ${this.escapeAgentHtml(data.tool || 'Tool')}: result received`);
        }
        this.scrollAgentToBottom();
    }

    TEXT(data, meta) {
        this.setThinkingState(false);
        this._textBuf += (data?.text || '');

        let entry = this.getAgentOutputElement().querySelector('.entry-text-output');
        if (!entry) {
            entry = this.addAgentEntry('text-output', '');
            entry.querySelector('.entry-content').classList.add('entry-text-output-content');
            entry.classList.add('entry-text-output');
        }
        this.scheduleAgentRender(entry, 'text');
    }

    DONE(data, meta) {
        this.setThinkingState(false);
        this.flushAgentRender();
        const usage = data?.usage;
        const footer = this.getAgentFooterElement();
        if (usage && footer) {
            let footerEl = footer.querySelector('.stream-footer');
            if (!footerEl) {
                footerEl = document.createElement('div');
                footerEl.className = 'stream-footer';
                footer.appendChild(footerEl);
            }
            footerEl.innerHTML =
                `<span>Tokens: ${usage.input_tokens || 0} in / ${usage.output_tokens || 0} out</span>` +
                (data.tool_calls ? ` &middot; <span>${data.tool_calls} tool calls</span>` : '');
        }
        this.scrollAgentToBottom();
    }

    STREAM_END(data) {
        this.setThinkingState(false);
        this.flushAgentRender();
        if (this.ntt?.pull) this.ntt.pull();
    }

    STREAM_ERROR(data) {
        this.setThinkingState(false);
        this.flushAgentRender();
        const msg = (typeof data === 'string') ? data
            : data?.message || data?.detail || data?.error || 'Stream error';
        this.addAgentEntry('error', `Error: ${this.escapeAgentHtml(msg)}`);
        showToast(msg, 'error');
    }

    render() {
        super.render();
        const el = this.shadowRoot.querySelector('.stream-output');
        if (el) el.remove();
    }

    callMethod() {
        this.resetAgentRenderState();
        this.prepareAgentOutput();
        super.callMethod();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        clearTimeout(this._textTimer);
        clearTimeout(this._thinkTimer);
    }

    getAgentOutputElement() {
        if (this._outputEl?.isConnected) return this._outputEl;
        let el = this.shadowRoot.querySelector('.agent-output');
        if (!el) {
            el = document.createElement('div');
            el.className = 'agent-output';
            this.shadowRoot.appendChild(el);
        }
        this._bindAgentOutput(el);
        this._outputEl = el;
        return el;
    }

    getAgentFooterElement() {
        return this.getAgentOutputElement();
    }

    prepareAgentOutput() {
        const output = this.getAgentOutputElement();
        if (output) output.innerHTML = '';
        const footer = this.getAgentFooterElement();
        if (footer && footer !== output) footer.innerHTML = '';
    }

    resetAgentRenderState() {
        this._toolCards.clear();
        this._textBuf = '';
        this._textRendered = 0;
        clearTimeout(this._textTimer);
        this._thinkBuf = '';
        this._thinkRendered = 0;
        clearTimeout(this._thinkTimer);
        this._outputEl = null;
    }

    addAgentEntry(type, html) {
        const el = document.createElement('div');
        el.className = `entry entry-${type}`;
        el.innerHTML = `<div class="entry-content">${html}</div>`;
        this.getAgentOutputElement().appendChild(el);
        this.scrollAgentToBottom();
        return el;
    }

    setThinkingState(on) {
        const output = this.getAgentOutputElement();
        let el = output.querySelector('.entry-thinking-active');
        if (on && !el) {
            el = this.addAgentEntry('thinking', '<span class="thinking-anim">Thinking</span>');
            el.classList.add('entry-thinking-active');
        } else if (!on && el) {
            const content = el.querySelector('.entry-content');
            if (content?.querySelector('.thinking-anim')) {
                el.remove();
            } else {
                clearTimeout(this._thinkTimer);
                this.renderAgentMarkdown(el, 'think');
                el.classList.remove('entry-thinking-active');
                el.classList.add('collapsible');
                this._thinkBuf = '';
                this._thinkRendered = 0;
            }
        }
    }

    scheduleAgentRender(entry, kind) {
        const buf = kind === 'text' ? this._textBuf : this._thinkBuf;
        const rendered = kind === 'text' ? this._textRendered : this._thinkRendered;
        const fresh = buf.slice(rendered);
        const hasNewline = fresh.includes('\n');

        if (kind === 'text') {
            clearTimeout(this._textTimer);
            if (hasNewline) this.renderAgentMarkdown(entry, kind);
            else this._textTimer = setTimeout(() => this.renderAgentMarkdown(entry, kind), 300);
        } else {
            clearTimeout(this._thinkTimer);
            if (hasNewline) this.renderAgentMarkdown(entry, kind);
            else this._thinkTimer = setTimeout(() => this.renderAgentMarkdown(entry, kind), 300);
        }
        this.scrollAgentToBottom();
    }

    renderAgentMarkdown(entry, kind) {
        if (!entry) return;
        const buf = kind === 'text' ? this._textBuf : this._thinkBuf;
        if (!buf) return;
        const content = entry.querySelector('.entry-text-output-content')
            || entry.querySelector('.entry-content');
        if (typeof marked !== 'undefined' && marked.parse) {
            content.innerHTML = marked.parse(buf);
        } else {
            content.textContent = buf;
        }
        if (kind === 'text') this._textRendered = buf.length;
        else this._thinkRendered = buf.length;
        this.scrollAgentToBottom();
    }

    flushAgentRender() {
        clearTimeout(this._textTimer);
        clearTimeout(this._thinkTimer);
        const output = this.getAgentOutputElement();
        const textEntry = output.querySelector('.entry-text-output');
        if (textEntry) this.renderAgentMarkdown(textEntry, 'text');
        const thinkEntry = output.querySelector('.entry-thinking-active');
        if (thinkEntry) this.renderAgentMarkdown(thinkEntry, 'think');
    }

    renderAgentToolArgs(args) {
        if (!args || (typeof args === 'object' && !Object.keys(args).length)) return '';
        const argsStr = typeof args === 'string' ? args : JSON.stringify(args, null, 2);
        return `<div class="tool-json">${this.escapeAgentHtml(argsStr)}</div>`;
    }

    renderAgentToolResult(result) {
        const resultStr = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
        return this.escapeAgentHtml((resultStr || '').slice(0, 500));
    }

    scrollAgentToBottom() {
        const el = this.getAgentOutputElement();
        const atBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 100;
        if (atBottom) el.scrollTop = el.scrollHeight;
    }

    escapeAgentHtml(text) {
        const d = document.createElement('div');
        d.textContent = text || '';
        return d.innerHTML;
    }

    _bindAgentOutput(el) {
        if (el.dataset.boundAgentOutput === 'true') return;
        el.dataset.boundAgentOutput = 'true';
        el.addEventListener('click', (e) => {
            const entry = e.target.closest('.entry.collapsible');
            if (entry) entry.classList.toggle('expanded');
        });
    }
}

customElements.define('ntx-stream-agent', NTTStreamAgent);
