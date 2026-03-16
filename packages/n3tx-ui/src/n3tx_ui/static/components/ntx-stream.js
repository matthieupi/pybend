import { NTTMethod } from './ntx-method.js';
import TX from '../core/TX.js';
import Logging from '../utils/Logging.js';
import { showToast } from '../utils/Toast.js';

export class NTTStream extends NTTMethod {
    
    #chunks;
    #streaming;
    #boundHandler;
    
    constructor() {
        console.log("Init NtxStream")
        super();
        this.#chunks = [];
        this.#streaming = false;
    }

    /**
     * Bind a dynamic handler for this.method (uppercase) so that reply TXs
     * dispatched by the Actor inbox (e.g. GENERATE, CHAT) route here.
     * Idempotent — unbinds the previous handler if the method name changed.
     */
    #bindStreamHandler() {
        const name = this.method;
        if (!name) return;
        // Unbind previous handler if method changed
        if (this.#boundHandler && this.#boundHandler !== name) {
            delete this[this.#boundHandler];
        }
        if (this.#boundHandler === name) return;
        this[name] = (data, tx) => {
            if (tx?.meta?.error)       return this.#onError(data);
            if (tx?.meta?.stream_end)  return this.#onDone(data);
            this.#onChunk(data);
        };
        this.#boundHandler = name;
    }

    /**
     * Send through actor system with meta.stream — component IS the source.
     * Reply TXs named this.method (uppercase) arrive at the dynamic handler.
     */
    callMethod() {
        const target = this.ntt?.href || this.proto?.href;
        if (!target) return;

        this.#chunks = [];
        this.response = null;
        this.#streaming = true;
        this.#renderOutput();
        this.#bindStreamHandler();

        this.send(new TX({
            name: this.method,
            source: this.addr,
            target: target,
            data: { ...this.value },
            meta: { stream: true },
        }));
    }

    disconnectedCallback() {
        super.disconnectedCallback();
    }

    #onChunk(data) {
        console.warn("ONCHUNK", data)
        this.#chunks.push(data);
        this.#renderOutput();
    }

    #onDone(data) {
        this.#streaming = false;
        if (data && Object.keys(data).length) this.#chunks.push(data);
        this.#renderOutput();
        if (this.ntt?.pull) this.ntt.pull();
    }

    #onError(data) {
        this.#streaming = false;
        const msg = (typeof data === 'string') ? data
            : data?.message || data?.detail || data?.error || 'Stream error';
        this.response = { error: msg };
        showToast(msg, 'error');
        Logging.error(`[ntx-stream] ${this.model}.${this.method} error`, msg);
        this.#renderOutput();
    }

    #renderOutput() {
        let el = this.shadowRoot.querySelector('.stream-output');
        if (!el) {
            el = document.createElement('div');
            el.className = 'stream-output';
            this.shadowRoot.appendChild(el);
        }
        if (this.response?.error) {
            el.innerHTML = `<div class="stream-error">${this.#esc(this.response.error)}</div>`;
            return;
        }
        const text = this.#chunks
            .map(c => c.data?.text || c.text || c.chunk || c.content || '')
            .join('');
        el.innerHTML = `<div class="stream-text">${this.#esc(text)}</div>`
            + (this.#streaming ? '<span class="stream-cursor">|</span>' : '');
    }

    #esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    render() {
        super.render();
        const style = this.shadowRoot.querySelector('style');
        if (style && !style.textContent.includes('stream-output')) {
            style.textContent += NTTStream.streamStyles;
        }
    }

    static streamStyles = `
        .stream-output { margin-top: .75rem; padding: .8rem; background: var(--surface-3);
            border: 1px solid var(--border); border-radius: .5rem; min-height: 2rem;
            max-height: 400px; overflow-y: auto; white-space: pre-wrap; color: var(--text-1); }
        .stream-cursor { animation: blink 1s step-end infinite; color: var(--accent); }
        @keyframes blink { 50% { opacity: 0; } }
        .stream-text { line-height: 1.5; }
        .stream-error { color: var(--error, #f87171); font-style: italic; line-height: 1.5; }
    `;
}

customElements.define('ntx-stream', NTTStream);
