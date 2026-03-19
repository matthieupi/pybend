/**
 * <ntx-chat> — Collapsible agent chat side-panel.
 *
 * Renders as a small tab on the right edge of the viewport.
 * Clicking the tab slides open a chat panel. Clicking again (or the X) closes it.
 *
 * Attributes:
 *   model    — Class name (e.g., "Product", "AgentActor")
 *   method   — Route name (e.g., "ask", "run")
 *
 * Usage:
 *   <ntx-chat model="Product" method="ask"></ntx-chat>
 *   <ntx-chat model="AgentActor" method="run"></ntx-chat>
 */
import { StreamActor } from './StreamActor.js';
import HTTP from '../core/transport/HTTP.js';
import { config } from '../config.js';
import { NTT } from '../core/NTT.js';

const ICON_CHAT = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
const ICON_CLOSE = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
const ICON_SEND = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;

class NTTChat extends StreamActor(HTMLElement) {
    #model; #method; #items; #schema; #tablename;
    #isStream; #isStreaming; #selectedId; #messages; #open;
    #els; #toolCards;
    // Per-message streaming state
    #currentMsgEl; #currentTextEl; #currentText;

    connectedCallback() {
        this.#model = this.getAttribute('model');
        this.#method = this.getAttribute('method');
        this.#items = [];
        this.#schema = null;
        this.#tablename = null;
        this.#isStreaming = false;
        this.#selectedId = null;
        this.#messages = [];
        this.#open = false;

        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `<style>${NTTChat.styles}</style>
            <button class="chat-tab" aria-label="Open chat">${ICON_CHAT}</button>
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">${this.#model} &middot; ${this.#method}</span>
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

        this.#els = {
            tab: this.shadowRoot.querySelector('.chat-tab'),
            panel: this.shadowRoot.querySelector('.panel'),
            close: this.shadowRoot.querySelector('.panel-close'),
            select: this.shadowRoot.querySelector('.instance-select'),
            messages: this.shadowRoot.querySelector('.chat-messages'),
            textarea: this.shadowRoot.querySelector('textarea'),
            send: this.shadowRoot.querySelector('.send-btn'),
        };

        this.#els.tab.addEventListener('click', () => this.#toggle());
        this.#els.close.addEventListener('click', () => this.#toggle());
        this.#els.send.addEventListener('click', () => this.#send());
        this.#els.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.#send(); }
        });

        this.#loadSchema();
    }

    disconnectedCallback() {
        this.streamClose();
    }

    #toggle() {
        this.#open = !this.#open;
        this.#els.panel.classList.toggle('open', this.#open);
        this.#els.tab.classList.toggle('hidden', this.#open);
        if (this.#open) this.#els.textarea.focus();
    }

    #loadSchema() {
        NTT.attach(this.#model, (DC) => {
            const schema = DC._schema;
            this.#schema = schema;
            this.#tablename = schema.__tablename__ || this.#model.toLowerCase() + 's';
            this.#isStream = !!(schema.methods?.[this.#method]?.stream);
            this.#loadInstances();
        });
    }

    #loadInstances() {
        const url = `${config.API_URL}/${this.#tablename}`;
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

    #send() {
        const task = this.#els.textarea.value.trim();
        if (!task || !this.#selectedId) return;

        this.#els.textarea.value = '';
        this.#appendMsg('user', task);

        const url = `${config.API_URL}/${this.#tablename}/${this.#selectedId}/${this.#method}`;
        const payload = { task };

        if (this.#isStream) {
            this.#isStreaming = true;
            this.#els.send.disabled = true;
            this.#currentText = '';
            this.#currentMsgEl = this.#appendMsg('assistant', '');
            this.#currentTextEl = this.#currentMsgEl.querySelector('.msg-text');
            this.#toolCards = new Map();
            this.stream(url, payload);
        } else {
            this.#sendPost(url, payload);
        }
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
        this.#els.send.disabled = false;
        this.#toolCards = null;
        this.#currentMsgEl?.querySelector('.cursor')?.remove();
        this.#currentMsgEl?.querySelector('.msg-thinking')?.remove();
        this.#scrollToBottom();
    }

    STREAM_ERROR(err) {
        this.#isStreaming = false;
        this.#els.send.disabled = false;
        this.#toolCards = null;
        this.#currentMsgEl?.querySelector('.cursor')?.remove();
        this.#currentMsgEl?.querySelector('.msg-thinking')?.remove();
        this.#appendMsg('system', `Error: ${err?.message || err?.detail || err}`);
    }

    // -- Internal helpers -------------------------------------------------------

    #sendPost(url, payload) {
        this.#els.send.disabled = true;
        HTTP.post(url, payload,
            (resp) => {
                this.#els.send.disabled = false;
                let answer;
                if (typeof resp === 'string') {
                    try { answer = JSON.parse(resp).answer || resp; } catch { answer = resp; }
                } else {
                    answer = resp.answer || resp.result || JSON.stringify(resp, null, 2);
                }
                this.#appendMsg('assistant', answer);
            },
            (err) => {
                this.#els.send.disabled = false;
                this.#appendMsg('system', `Error: ${err?.message || err?.detail || err}`);
            },
        );
    }

    #appendMsg(role, text) {
        const el = document.createElement('div');
        el.className = `msg msg-${role}`;
        el.innerHTML = `<span class="msg-role">${role}</span><span class="msg-text">${this.#esc(text)}</span>`;
        this.#els.messages.appendChild(el);
        this.#scrollToBottom();
        return el;
    }

    #clear() {
        this.#messages = [];
        this.#els.messages.innerHTML = '';
        this.streamClose();
        this.#isStreaming = false;
        this.#els.send.disabled = false;
    }

    #scrollToBottom() {
        this.#els.messages.scrollTop = this.#els.messages.scrollHeight;
    }

    #esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    static styles = `
        :host {
            display: block; position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 9000;
            font-family: system-ui, -apple-system, sans-serif; font-size: .875rem;
        }

        /* -- Floating tab button -- */
        .chat-tab {
            width: 48px; height: 48px; border-radius: 50%;
            background: var(--accent, #4cc9f0); color: #000;
            border: none; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 16px rgba(0,0,0,.4);
            transition: transform .15s, box-shadow .15s;
        }
        .chat-tab:hover { transform: scale(1.08); box-shadow: 0 6px 24px rgba(0,0,0,.5); }
        .chat-tab.hidden { display: none; }

        /* -- Slide-up panel -- */
        .panel {
            position: absolute; bottom: 0; right: 0;
            width: 380px; max-height: 520px;
            border: 1px solid var(--border, #333); border-radius: .75rem;
            background: var(--surface-1, #1a1a2e);
            box-shadow: 0 8px 32px rgba(0,0,0,.5);
            display: flex; flex-direction: column;
            transform: translateY(10px) scale(.95); opacity: 0; pointer-events: none;
            transition: transform .2s ease, opacity .2s ease;
        }
        .panel.open {
            transform: translateY(0) scale(1); opacity: 1; pointer-events: auto;
        }

        /* -- Panel header -- */
        .panel-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: .6rem .75rem;
            background: var(--surface-2, #16213e);
            border-bottom: 1px solid var(--border, #333);
            border-radius: .75rem .75rem 0 0;
        }
        .panel-title {
            font-weight: 600; font-size: .7rem;
            text-transform: uppercase; letter-spacing: .05em;
            color: var(--text-2, #aaa);
        }
        .panel-close {
            background: none; border: none; color: var(--text-2, #aaa);
            cursor: pointer; padding: .2rem; border-radius: .25rem;
            display: flex; align-items: center; justify-content: center;
        }
        .panel-close:hover { color: var(--text-1, #eee); background: var(--surface-3, #0f3460); }

        /* -- Controls -- */
        .panel-controls {
            padding: .4rem .75rem; border-bottom: 1px solid var(--border, #333);
        }
        .instance-select {
            width: 100%; padding: .3rem .5rem; border-radius: .3rem;
            background: var(--surface-3, #0f3460); color: var(--text-1, #eee);
            border: 1px solid var(--border, #333); font-size: .8rem;
        }

        /* -- Messages area -- */
        .chat-messages {
            flex: 1; overflow-y: auto; padding: .5rem .75rem;
            min-height: 150px; max-height: 300px;
        }
        .msg { margin-bottom: .5rem; line-height: 1.5; }
        .msg-role {
            display: inline-block; font-size: .65rem; font-weight: 700;
            text-transform: uppercase; margin-right: .4rem; opacity: .6;
        }
        .msg-text { white-space: pre-wrap; word-break: break-word; }
        .msg-user .msg-role { color: var(--accent, #4cc9f0); }
        .msg-assistant .msg-role { color: var(--success, #4ade80); }
        .msg-system .msg-role { color: var(--warning, #fbbf24); }
        .msg-system .msg-text { opacity: .7; font-style: italic; }
        .cursor { animation: blink 1s step-end infinite; color: var(--accent, #4cc9f0); }
        @keyframes blink { 50% { opacity: 0; } }

        /* -- Input area -- */
        .chat-input {
            display: flex; gap: .4rem; align-items: flex-end;
            padding: .5rem .75rem;
            border-top: 1px solid var(--border, #333);
            background: var(--surface-2, #16213e);
            border-radius: 0 0 .75rem .75rem;
        }
        textarea {
            flex: 1; resize: none; padding: .4rem .5rem; border-radius: .3rem;
            background: var(--surface-3, #0f3460); color: var(--text-1, #eee);
            border: 1px solid var(--border, #333); font-family: inherit; font-size: .8rem;
            box-sizing: border-box; min-height: 36px; max-height: 80px;
        }
        textarea:focus { outline: 1px solid var(--accent, #4cc9f0); }
        .send-btn {
            width: 36px; height: 36px; border-radius: .3rem; border: none;
            background: var(--accent, #4cc9f0); color: #000; cursor: pointer;
            display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }
        .send-btn:hover { filter: brightness(1.1); }
        .send-btn:disabled { opacity: .4; cursor: not-allowed; }

        /* -- Tool cards -- */
        .tool-card {
            margin: .3rem 0; padding: .3rem .5rem;
            background: var(--surface-3, #0f3460); border-radius: .3rem;
            font-size: .75rem; border-left: 2px solid var(--accent, #4cc9f0);
        }
        .tool-header { font-weight: 600; display: flex; align-items: center; gap: .3rem; }
        .tool-icon { opacity: .6; }
        .tool-spin { animation: spin 1s linear infinite; font-size: .5rem; color: var(--accent, #4cc9f0); }
        @keyframes spin { to { transform: rotate(360deg); } }
        .tool-result { margin-top: .2rem; opacity: .7; font-size: .7rem; word-break: break-word; }

        /* -- Thinking indicator -- */
        .msg-thinking {
            font-style: italic; opacity: .5; font-size: .75rem; margin-bottom: .3rem;
        }
        .thinking-dots::after {
            content: ''; animation: dots 1.5s steps(3, end) infinite;
        }
        @keyframes dots { 0% { content: '.'; } 33% { content: '..'; } 66% { content: '...'; } }

        /* -- Stats -- */
        .msg-stats {
            font-size: .65rem; opacity: .4; margin-top: .2rem;
        }
    `;
}

customElements.define('ntx-chat', NTTChat);
export { NTTChat };
