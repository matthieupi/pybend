/**
 * <ntx-chat> — responsive threaded agent chat.
 */
import { NTT } from '../core/NTT.js';
import HTTP from '../core/transport/HTTP.js';
import { NTTStreamAgent } from './ntx-stream-agent.js';

const ICON_CHAT = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
const ICON_CLOSE = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
const ICON_SEND = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;

class NTTChat extends NTTStreamAgent {
    get styles() {
        const parent = super.styles;
        const inherited = Array.isArray(parent) ? parent : parent ? [parent] : [];
        return [...inherited, new URL('./ntx-chat.css', import.meta.url).href];
    }

    #items = [];
    #selectedId = null;
    #open = false;
    #threadId = null;
    #size = 'xs';
    #resizeObserver = null;
    #currentAssistantEl = null;
    #currentAssistantOutputEl = null;
    #els;

    connectedCallback() {
        if (!this.getAttribute('method')) this.setAttribute('method', 'agentic_stream');
        super.connectedCallback();
        this.addEventListener('click', (e) => e.stopPropagation());
        this.#setupResizeObserver();
    }

    disconnectedCallback() {
        this.#resizeObserver?.disconnect();
        super.disconnectedCallback();
    }

    prerender() {
        this.shadowRoot.innerHTML = `
            <button class="chat-tab" aria-label="Open chat">${ICON_CHAT}</button>
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">${this.getAttribute('model') || ''} · ${this.getAttribute('method') || ''}</span>
                    <button class="panel-close" aria-label="Close">${ICON_CLOSE}</button>
                </div>
                <div class="panel-controls">
                    <select class="instance-select"><option value="">Loading...</option></select>
                </div>
                <div class="chat-messages"></div>
                <div class="chat-input">
                    <textarea placeholder="Type your message..." rows="2"></textarea>
                    <button class="send-btn" aria-label="Send">${ICON_SEND}</button>
                </div>
            </div>`;

        this.#cacheEls();
        this.#bindListeners();
        this.#applyPanelState();
    }

    render() {
        const title = this.shadowRoot.querySelector('.panel-title');
        if (title) title.textContent = `${this.model} · ${this.method}`;
        this.#syncControlsVisibility();
    }

    definedCallback() {
        super.definedCallback();
        this.#resolveTargetFromRef();
        if (!this.uuid && !this.#selectedId) this.#loadInstances();
        this.#syncControlsVisibility();
    }

    callMethod() {
        const task = this.#els.textarea.value.trim();
        this.#resolveTargetFromRef();
        const targetId = this.uuid || this.#selectedId;
        if (!task || !targetId) return;

        this.#appendUserMessage(task);
        this.#els.textarea.value = '';

        this.uuid = targetId;
        this.ntt = NTT.get(this.model + '/' + targetId);
        this.#els.send.disabled = true;
        this.#createAssistantMessage();
        this.value = this.#threadId
            ? { task, thread_id: this.#threadId }
            : { task };
        super.callMethod();
    }

    _response_(data, tx) {
        this.#els.send.disabled = false;
        const answer = data?.answer
            || (typeof data?.result === 'string' ? data.result : null)
            || JSON.stringify(data);
        this.#appendAssistantText(answer);
    }

    DONE(data, meta) {
        const threadId = data?.thread_id || data?.data?.thread_id || data?.result?.thread_id;
        if (threadId) this.#threadId = threadId;
        if (!this.getAgentOutputElement().querySelector('.entry-text-output') && data?.answer) {
            this.addAgentEntry('text-output', `<div class="entry-text-output-content">${this.escapeAgentHtml(data.answer)}</div>`)
                .classList.add('entry-text-output');
        }
        this.#els.send.disabled = false;
        super.DONE(data, meta);
    }

    STREAM_END(data) {
        this.setThinkingState(false);
        this.flushAgentRender();
        this.#els.send.disabled = false;
        this.#currentAssistantEl = null;
        this.#currentAssistantOutputEl = null;
    }

    STREAM_ERROR(err) {
        super.STREAM_ERROR(err);
        this.#els.send.disabled = false;
        this.#currentAssistantEl = null;
        this.#currentAssistantOutputEl = null;
    }

    getAgentOutputElement() {
        if (this.#currentAssistantOutputEl) {
            this._bindAgentOutput(this.#currentAssistantOutputEl);
            return this.#currentAssistantOutputEl;
        }
        const lastAssistant = this.#els?.messages?.querySelector('.msg-assistant:last-of-type .assistant-events');
        if (lastAssistant) {
            this._bindAgentOutput(lastAssistant);
            return lastAssistant;
        }
        return super.getAgentOutputElement();
    }

    getAgentFooterElement() {
        return this.#currentAssistantOutputEl || super.getAgentFooterElement();
    }

    prepareAgentOutput() {
        const output = this.getAgentOutputElement();
        if (output) output.innerHTML = '';
    }

    scrollAgentToBottom() {
        const messages = this.#els?.messages;
        if (messages) messages.scrollTop = messages.scrollHeight;
    }

    #cacheEls() {
        this.#els = {
            tab: this.shadowRoot.querySelector('.chat-tab'),
            panel: this.shadowRoot.querySelector('.panel'),
            close: this.shadowRoot.querySelector('.panel-close'),
            controls: this.shadowRoot.querySelector('.panel-controls'),
            select: this.shadowRoot.querySelector('.instance-select'),
            messages: this.shadowRoot.querySelector('.chat-messages'),
            textarea: this.shadowRoot.querySelector('textarea'),
            send: this.shadowRoot.querySelector('.send-btn'),
        };
    }

    #bindListeners() {
        this.#els.tab.addEventListener('click', () => this.#toggle(true));
        this.#els.close.addEventListener('click', () => this.#toggle(false));
        this.#els.send.addEventListener('click', () => this.callMethod());
        this.#els.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.callMethod();
            }
        });
        this.#els.select.addEventListener('change', () => {
            this.#selectedId = this.#els.select.value;
            this.#threadId = null;
        });
    }

    #toggle(nextOpen = !this.#open) {
        if (this.#size !== 'xs') return;
        this.#open = nextOpen;
        this.#applyPanelState();
        if (this.#open) this.#els.textarea.focus();
    }

    #applyPanelState() {
        const inline = this.#size !== 'xs';
        this.toggleAttribute('data-inline', inline);
        this.setAttribute('data-size', this.#size);
        this.#els?.panel.classList.toggle('open', inline || this.#open);
        this.#els?.tab.classList.toggle('hidden', inline || this.#open);
        this.#els?.close.classList.toggle('hidden', inline);
    }

    #syncControlsVisibility() {
        if (!this.#els) return;
        const hasFixedRef = !!(this.getAttribute('ref') || this.uuid);
        this.#els.controls.classList.toggle('hidden', hasFixedRef);
    }

    #resolveTargetFromRef() {
        const ref = this.getAttribute('ref') || '';
        if (!ref || this.uuid) return;
        const id = ref.includes('/') ? ref.split('/').pop() : ref;
        if (!id) return;
        this.#selectedId = id;
        this.uuid = id;
        this.ntt = NTT.get(this.model + '/' + id);
    }

    #setupResizeObserver() {
        const observedEl = this.parentElement || this;
        this.#resizeObserver?.disconnect();
        this.#resizeObserver = new ResizeObserver((entries) => {
            const containerWidth = entries[0]?.contentRect?.width || observedEl.getBoundingClientRect().width || window.innerWidth;
            const width = Math.min(containerWidth || window.innerWidth, window.innerWidth || containerWidth);
            const nextSize = this.#computeSize(width);
            if (nextSize === this.#size) return;
            this.#size = nextSize;
            this.#open = nextSize !== 'xs';
            this.#applyPanelState();
        });
        this.#resizeObserver.observe(observedEl);
        const initialContainerWidth = observedEl.getBoundingClientRect().width || window.innerWidth;
        const initialWidth = Math.min(initialContainerWidth || window.innerWidth, window.innerWidth || initialContainerWidth);
        this.#size = this.#computeSize(initialWidth);
        this.#open = this.#size !== 'xs';
        this.#applyPanelState();
    }

    #computeSize(width) {
        if (width < 640) return 'xs';
        if (width < 768) return 'sm';
        if (width < 1024) return 'md';
        if (width < 1280) return 'lg';
        return 'xl';
    }

    #loadInstances() {
        const tablename = this.schema?.__tablename__ || this.model?.toLowerCase() + 's';
        HTTP.get(`/${tablename}`, (resp) => {
            this.#items = resp.data || resp || [];
            this.#els.select.innerHTML = this.#items.map((item) => {
                const label = item.name || item.title || `#${item.id}`;
                return `<option value="${item.id}">${label}</option>`;
            }).join('');
            if (this.#items.length) this.#selectedId = String(this.#items[0].id);
        }, () => {
            this.#els.select.innerHTML = '<option value="">No instances</option>';
        });
    }

    #appendUserMessage(text) {
        const el = document.createElement('div');
        el.className = 'msg msg-user';
        el.innerHTML = `<span class="msg-role">user</span><span class="msg-text">${this.escapeAgentHtml(text)}</span>`;
        this.#els.messages.appendChild(el);
        this.scrollAgentToBottom();
    }

    #appendAssistantText(text) {
        const el = document.createElement('div');
        el.className = 'msg msg-assistant';
        el.innerHTML = `<span class="msg-role">assistant</span><div class="assistant-events"><div class="msg-text">${this.escapeAgentHtml(text)}</div></div>`;
        this.#els.messages.appendChild(el);
        this.scrollAgentToBottom();
    }

    #createAssistantMessage() {
        const el = document.createElement('div');
        el.className = 'msg msg-assistant';
        el.innerHTML = `
            <span class="msg-role">assistant</span>
            <div class="assistant-events"></div>`;
        this.#els.messages.appendChild(el);
        this.#currentAssistantEl = el;
        this.#currentAssistantOutputEl = el.querySelector('.assistant-events');
        this.scrollAgentToBottom();
    }
}

customElements.define('ntx-chat', NTTChat);
export { NTTChat };
