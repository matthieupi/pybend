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
import HTTP from '../core/transport/HTTP.js';
import { config } from '../config.js';

const ICON_CHAT = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
const ICON_CLOSE = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
const ICON_SEND = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;

class NTTChat extends HTMLElement {
    connectedCallback() {
        this._model = this.getAttribute('model');
        this._method = this.getAttribute('method');
        this._items = [];
        this._schema = null;
        this._tablename = null;
        this._isStreaming = false;
        this._selectedId = null;
        this._messages = [];
        this._streamHandle = null;
        this._open = false;

        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `<style>${NTTChat.styles}</style>
            <button class="chat-tab" aria-label="Open chat">${ICON_CHAT}</button>
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">${this._model} &middot; ${this._method}</span>
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

        this._els = {
            tab: this.shadowRoot.querySelector('.chat-tab'),
            panel: this.shadowRoot.querySelector('.panel'),
            close: this.shadowRoot.querySelector('.panel-close'),
            select: this.shadowRoot.querySelector('.instance-select'),
            messages: this.shadowRoot.querySelector('.chat-messages'),
            textarea: this.shadowRoot.querySelector('textarea'),
            send: this.shadowRoot.querySelector('.send-btn'),
        };

        this._els.tab.addEventListener('click', () => this._toggle());
        this._els.close.addEventListener('click', () => this._toggle());
        this._els.send.addEventListener('click', () => this._send());
        this._els.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._send(); }
        });

        this._loadSchema();
    }

    disconnectedCallback() {
        if (this._streamHandle) { this._streamHandle.cancel(); this._streamHandle = null; }
    }

    _toggle() {
        this._open = !this._open;
        this._els.panel.classList.toggle('open', this._open);
        this._els.tab.classList.toggle('hidden', this._open);
        if (this._open) this._els.textarea.focus();
    }

    _loadSchema() {
        const url = `${config.API_URL}/${this._model}`;
        HTTP.get(url, (schema) => {
            this._schema = schema;
            this._tablename = schema.__tablename__ || this._model.toLowerCase() + 's';
            this._isStream = !!(schema.methods?.[this._method]?.stream);
            this._loadInstances();
        }, (err) => {
            this._appendMsg('system', `Failed to load schema: ${err?.detail || err}`);
        });
    }

    _loadInstances() {
        const url = `${config.API_URL}/${this._tablename}`;
        HTTP.get(url, (resp) => {
            this._items = resp.data || resp || [];
            const sel = this._els.select;
            sel.innerHTML = this._items.map(item => {
                const label = item.name || item.title || `#${item.id}`;
                return `<option value="${item.id}">${label}</option>`;
            }).join('');
            if (this._items.length) this._selectedId = this._items[0].id;
            sel.addEventListener('change', () => { this._selectedId = sel.value; });
        }, (err) => {
            this._els.select.innerHTML = '<option value="">No instances</option>';
        });
    }

    _send() {
        const task = this._els.textarea.value.trim();
        if (!task || !this._selectedId) return;

        this._els.textarea.value = '';
        this._appendMsg('user', task);

        const url = `${config.API_URL}/${this._tablename}/${this._selectedId}/${this._method}`;
        const payload = { task };

        if (this._isStream) {
            this._sendStream(url, payload);
        } else {
            this._sendPost(url, payload);
        }
    }

    _sendStream(url, payload) {
        this._isStreaming = true;
        this._els.send.disabled = true;
        let text = '';
        const msgEl = this._appendMsg('assistant', '');

        this._streamHandle = HTTP.stream(url, payload,
            (chunk) => {
                // SSE chunks are TX-aligned: {name, data, meta}
                // Text chunks: {name: "text", data: {text: "..."}}
                // Done chunks: {name: "done", data: {answer, usage}}
                if (chunk.name === 'done') {
                    if (chunk.data?.answer && !text) {
                        msgEl.querySelector('.msg-text').textContent = chunk.data.answer;
                        text = chunk.data.answer;
                    }
                    return;
                }
                const t = chunk.data?.text || chunk.text || chunk.chunk || chunk.content || '';
                text += t;
                msgEl.querySelector('.msg-text').textContent = text;
                msgEl.querySelector('.cursor')?.remove();
                msgEl.querySelector('.msg-text').insertAdjacentHTML('afterend',
                    '<span class="cursor">|</span>');
                this._scrollToBottom();
            },
            (data) => {
                // SSE done sentinel — empty {}, just clean up
                this._isStreaming = false;
                this._streamHandle = null;
                this._els.send.disabled = false;
                msgEl.querySelector('.cursor')?.remove();
                this._scrollToBottom();
            },
            (err) => {
                this._isStreaming = false;
                this._streamHandle = null;
                this._els.send.disabled = false;
                msgEl.querySelector('.cursor')?.remove();
                this._appendMsg('system', `Error: ${err?.message || err?.detail || err}`);
            },
        );
    }

    _sendPost(url, payload) {
        this._els.send.disabled = true;
        HTTP.post(url, payload,
            (resp) => {
                this._els.send.disabled = false;
                let answer;
                if (typeof resp === 'string') {
                    try { answer = JSON.parse(resp).answer || resp; } catch { answer = resp; }
                } else {
                    answer = resp.answer || resp.result || JSON.stringify(resp, null, 2);
                }
                this._appendMsg('assistant', answer);
            },
            (err) => {
                this._els.send.disabled = false;
                this._appendMsg('system', `Error: ${err?.message || err?.detail || err}`);
            },
        );
    }

    _appendMsg(role, text) {
        const el = document.createElement('div');
        el.className = `msg msg-${role}`;
        el.innerHTML = `<span class="msg-role">${role}</span><span class="msg-text">${this._esc(text)}</span>`;
        this._els.messages.appendChild(el);
        this._scrollToBottom();
        return el;
    }

    _clear() {
        this._messages = [];
        this._els.messages.innerHTML = '';
        if (this._streamHandle) { this._streamHandle.cancel(); this._streamHandle = null; }
        this._isStreaming = false;
        this._els.send.disabled = false;
    }

    _scrollToBottom() {
        this._els.messages.scrollTop = this._els.messages.scrollHeight;
    }

    _esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    static styles = `
        :host {
            display: block; position: fixed; bottom: 1.5rem; right: 1.5rem; z-index: 9000;
            font-family: system-ui, -apple-system, sans-serif; font-size: .875rem;
        }

        /* ── Floating tab button ── */
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

        /* ── Slide-up panel ── */
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

        /* ── Panel header ── */
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

        /* ── Controls ── */
        .panel-controls {
            padding: .4rem .75rem; border-bottom: 1px solid var(--border, #333);
        }
        .instance-select {
            width: 100%; padding: .3rem .5rem; border-radius: .3rem;
            background: var(--surface-3, #0f3460); color: var(--text-1, #eee);
            border: 1px solid var(--border, #333); font-size: .8rem;
        }

        /* ── Messages area ── */
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

        /* ── Input area ── */
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
    `;
}

customElements.define('ntx-chat', NTTChat);
export { NTTChat };
