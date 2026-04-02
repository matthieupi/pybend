/**
 * <ntx-chat> — Collapsible agent chat side-panel.
 *
 * Renders as a small tab on the right edge of the viewport.
 * Clicking the tab slides open a chat panel. Clicking again (or the X) closes it.
 *
 * Extends NTTStream for TX-based streaming (replaces StreamActor).
 *
 * Attributes:
 *   model    — Class name (e.g., "Product", "AgentActor")
 *   method   — Route name (e.g., "ask", "run")
 *
 * Usage:
 *   <ntx-chat model="Product" method="ask"></ntx-chat>
 *   <ntx-chat model="AgentActor" method="run"></ntx-chat>
 */
import { NTTStream } from './ntx-stream.js';
import { NTT } from '../core/NTT.js';
import HTTP from '../core/transport/HTTP.js';

const ICON_CHAT = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
const ICON_CLOSE = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
const ICON_SEND = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;

class NTTChat extends NTTStream {
    get styles() {
        const parent = super.styles;
        const inherited = Array.isArray(parent) ? parent : parent ? [parent] : [];
        return [...inherited, new URL('./ntx-chat.css', import.meta.url).href];
    }

    #items = [];
    #isStream; #isStreaming = false; #selectedId = null;
    #messages = []; #open = false;
    #els; #toolCards;
    // Per-message streaming state
    #currentMsgEl; #currentTextEl; #currentText;

    connectedCallback() {
        if (!this.getAttribute('display')) this.setAttribute('display', 'md');
        super.connectedCallback();
    }

    prerender() {
        this.shadowRoot.innerHTML = `
            <button class="chat-tab" aria-label="Open chat">${ICON_CHAT}</button>
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">${this.getAttribute('model') || ''} &middot; ${this.getAttribute('method') || ''}</span>
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
    }

    render() {
        // Additive — never wipes prerender() DOM.
        if (this.#els) {
            const title = this.shadowRoot.querySelector('.panel-title');
            if (title) title.textContent = `${this.model} · ${this.method}`;
        }
    }

    definedCallback() {
        super.definedCallback();
        this.#isStream = !!this.methodSchema?.stream;
        if (!this.uuid) this.#loadInstances();
    }

    callMethod() {
        const task = this.#els.textarea.value.trim();
        if (!task || !this.#selectedId) return;

        this.#appendMsg('user', task);
        this.#els.textarea.value = '';

        this.uuid = this.#selectedId;
        this.ntt = NTT.get(this.model + '/' + this.#selectedId);
        this.value = { task };

        if (this.#isStream) {
            this.#isStreaming = true;
            this.#els.send.disabled = true;
            this.#currentText = '';
            this.#currentMsgEl = this.#appendMsg('assistant', '');
            this.#currentTextEl = this.#currentMsgEl.querySelector('.msg-text');
            this.#toolCards = new Map();
            super.callMethod();
        } else {
            // Non-streaming: use entity call path
            this.#els.send.disabled = true;
            const caller = this.ntt || this.proto;
            if (caller?.call) {
                caller.call(this.method, { ...this.value }, { inbox: '_response_' });
            }
        }
    }

    _response_(data, tx) {
        this.#els.send.disabled = false;
        const answer = data?.answer || data?.result || JSON.stringify(data);
        this.#appendMsg('assistant', answer);
    }

    // -- TX inbox handlers (UPPERCASE) ------------------------------------------

    THINKING(data, meta) {
        let thinkEl = this.#currentMsgEl.querySelector('.msg-thinking');
        if (!thinkEl) {
            thinkEl = document.createElement('div');
            thinkEl.className = 'msg-thinking';
            thinkEl.innerHTML = '<span class="thinking-dots">thinking</span>';
            this.#currentMsgEl.insertBefore(thinkEl, this.#currentTextEl);
        }
    }

    TOOL_CALL(data, meta) {
        this.#currentMsgEl.querySelector('.msg-thinking')?.remove();
        const card = document.createElement('div');
        card.className = 'tool-card';
        card.innerHTML = `<div class="tool-header"><span class="tool-icon">\u2699</span> ${this.#esc(data.tool)} <span class="tool-spin">\u25CF</span></div>`;
        this.#currentMsgEl.insertBefore(card, this.#currentTextEl);
        if (data.call_id) this.#toolCards.set(data.call_id, card);
    }

    TOOL_RESULT(data, meta) {
        const card = data.call_id && this.#toolCards.get(data.call_id);
        if (card) {
            card.querySelector('.tool-spin')?.remove();
            const summary = (data.result || '').slice(0, 120);
            card.innerHTML += `<div class="tool-result">${this.#esc(summary)}</div>`;
        }
    }

    TEXT(data, meta) {
        this.#currentMsgEl.querySelector('.msg-thinking')?.remove();
        const t = data?.text || '';
        this.#currentText += t;
        this.#currentTextEl.textContent = this.#currentText;
        this.#currentMsgEl.querySelector('.cursor')?.remove();
        this.#currentTextEl.insertAdjacentHTML('afterend', '<span class="cursor">|</span>');
        this.#scrollToBottom();
    }

    DONE(data, meta) {
        this.#currentMsgEl.querySelector('.msg-thinking')?.remove();
        if (data?.answer && !this.#currentText) {
            this.#currentTextEl.textContent = data.answer;
            this.#currentText = data.answer;
        }
        if (data?.tool_calls > 0) {
            const stats = document.createElement('div');
            stats.className = 'msg-stats';
            stats.textContent = `${data.tool_calls} tool call${data.tool_calls > 1 ? 's' : ''}`;
            this.#currentMsgEl.appendChild(stats);
        }
        this.#scrollToBottom();
    }

    STREAM_END(data) {
        this.#isStreaming = false;
        if (this.#els) this.#els.send.disabled = false;
        this.#toolCards = null;
        this.#currentMsgEl?.querySelector('.cursor')?.remove();
        this.#currentMsgEl?.querySelector('.msg-thinking')?.remove();
        this.#scrollToBottom();
    }

    STREAM_ERROR(err) {
        this.#isStreaming = false;
        if (this.#els) this.#els.send.disabled = false;
        this.#toolCards = null;
        this.#currentMsgEl?.querySelector('.cursor')?.remove();
        this.#currentMsgEl?.querySelector('.msg-thinking')?.remove();
        this.#appendMsg('system', `Error: ${err?.message || err?.detail || err}`);
    }

    // -- Internal helpers -------------------------------------------------------

    #cacheEls() {
        this.#els = {
            tab: this.shadowRoot.querySelector('.chat-tab'),
            panel: this.shadowRoot.querySelector('.panel'),
            close: this.shadowRoot.querySelector('.panel-close'),
            select: this.shadowRoot.querySelector('.instance-select'),
            messages: this.shadowRoot.querySelector('.chat-messages'),
            textarea: this.shadowRoot.querySelector('textarea'),
            send: this.shadowRoot.querySelector('.send-btn'),
        };
    }

    #bindListeners() {
        this.#els.tab.addEventListener('click', () => this.#toggle());
        this.#els.close.addEventListener('click', () => this.#toggle());
        this.#els.send.addEventListener('click', () => this.callMethod());
        this.#els.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.callMethod(); }
        });
    }

    #toggle() {
        this.#open = !this.#open;
        this.#els.panel.classList.toggle('open', this.#open);
        this.#els.tab.classList.toggle('hidden', this.#open);
        if (this.#open) this.#els.textarea.focus();
    }

    #loadInstances() {
        const tablename = this.schema?.__tablename__ || this.model?.toLowerCase() + 's';
        const url = `/${tablename}`;
        HTTP.get(url, (resp) => {
            this.#items = resp.data || resp || [];
            const sel = this.#els.select;
            sel.innerHTML = this.#items.map(item => {
                const label = item.name || item.title || `#${item.id}`;
                return `<option value="${item.id}">${label}</option>`;
            }).join('');
            if (this.#items.length) this.#selectedId = this.#items[0].id;
            sel.addEventListener('change', () => { this.#selectedId = sel.value; });
        }, (err) => {
            this.#els.select.innerHTML = '<option value="">No instances</option>';
        });
    }

    #appendMsg(role, text) {
        const el = document.createElement('div');
        el.className = `msg msg-${role}`;
        el.innerHTML = `<span class="msg-role">${role}</span><span class="msg-text">${this.#esc(text)}</span>`;
        this.#els.messages.appendChild(el);
        this.#scrollToBottom();
        return el;
    }

    #scrollToBottom() {
        this.#els.messages.scrollTop = this.#els.messages.scrollHeight;
    }

    #esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }
}

customElements.define('ntx-chat', NTTChat);
export { NTTChat };
