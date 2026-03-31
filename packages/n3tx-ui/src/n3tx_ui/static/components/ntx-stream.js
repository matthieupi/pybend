import { NTTMethod } from './ntx-method.js';
import TX from '../core/TX.js';
import { showToast } from '../utils/Toast.js';

export class NTTStream extends NTTMethod {

    get styles() {
        const parent = super.styles;
        const inherited = Array.isArray(parent) ? parent : parent ? [parent] : [];
        return [...inherited, new URL('./ntx-stream.css', import.meta.url).href];
    }

    // ── State ──
    #streaming = false;     // true while stream is active
    #textBuf = '';          // accumulated text from TEXT events
    #boundHandler = null;   // name of currently bound dynamic alias
    #cancelled = false;     // ignore flag for cancelled streams
    #streamReqId = null;    // correlation ID for cancel TX

    constructor() {
        super();
    }

    // ── STREAM inbox handler ──
    // All stream chunks route here via dynamic alias.
    // Dispatches to UPPERCASE sub-handlers by event name.
    // Untyped chunks (no data.name) fall through to TEXT().
    STREAM(data, tx) {
        if (this.#cancelled) return;
        if (tx?.meta?.error)      return this.STREAM_ERROR(data);
        if (tx?.meta?.stream_end) return this.STREAM_END(data);

        // Typed event dispatch: {name: 'thinking', data: {text: '...'}} → this.THINKING({text: '...'})
        const name = data?.name?.toUpperCase();
        if (name && typeof this[name] === 'function') {
            this[name](data.data, data.meta);
        } else {
            // Untyped fallback — treat entire chunk as text
            this.TEXT(data);
        }
    }

    // ── callMethod override ──
    // Sends TX with meta.stream=true through Actor system.
    // Binds dynamic alias so reply TXs (named after method) route to STREAM().
    callMethod() {
        const target = this.ntt?.href || this.proto?.href;
        if (!target) return;

        this.#reset();
        this.#streaming = true;
        this.#cancelled = false;
        this.#renderOutput();

        // Dynamic alias: reply TX arrives as this[method]() → forwards to STREAM()
        // This bridges method-name TX routing to the unified STREAM handler.
        const name = this.method;
        if (this.#boundHandler && this.#boundHandler !== name) {
            delete this[this.#boundHandler];
        }
        this[name] = (data, tx) => this.STREAM(data, tx);
        this.#boundHandler = name;

        this.#streamReqId = `${this.addr}-${Date.now()}`;

        this.send(new TX({
            name: this.method,
            source: this.addr,
            target: target,
            data: { ...this.value },
            meta: { stream: true, req: this.#streamReqId },
        }));
    }

    // ── Default UPPERCASE handlers ──
    // Subclasses override these for rich rendering.
    // Base NTTStream provides backward-compatible plain text accumulation.

    TEXT(data) {
        // Extract text from various chunk formats
        const text = data?.text || data?.chunk || data?.content || '';
        if (typeof data === 'string') this.#textBuf += data;
        else this.#textBuf += text;
        this.#renderOutput();
    }

    STREAM_END(data) {
        this.#streaming = false;
        this.#renderOutput();
        // Refresh parent entity so list/item components update
        if (this.ntt?.pull) this.ntt.pull();
    }

    STREAM_ERROR(data) {
        this.#streaming = false;
        const msg = (typeof data === 'string') ? data
            : data?.message || data?.detail || data?.error || 'Stream error';
        this.response = { error: msg };
        showToast(msg, 'error');
        this.#renderOutput();
    }

    // ── Rendering ──

    render() {
        super.render();
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
        el.innerHTML = `<div class="stream-text">${this.#esc(this.#textBuf)}</div>`
            + (this.#streaming ? '<span class="stream-cursor">|</span>' : '');
    }

    #reset() {
        this.#textBuf = '';
        this.#streaming = false;
        this.response = null;
        const el = this.shadowRoot?.querySelector('.stream-output');
        if (el) el.innerHTML = '';
    }

    #esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    /**
     * Cancel the active stream.
     * Sets ignore flag, drops incoming chunks, resets UI state.
     * Sends STREAM_CANCEL TX for future backend support.
     */
    cancel() {
        if (!this.#streaming) return;
        this.#cancelled = true;
        this.#streaming = false;

        const target = this.ntt?.href || this.proto?.href;
        if (target && this.#streamReqId) {
            this.send(new TX({
                name: 'STREAM_CANCEL',
                source: this.addr,
                target: target,
                meta: { req: this.#streamReqId },
            }));
        }

        this.STREAM_END({});
    }

    disconnectedCallback() {
        this.cancel();
        super.disconnectedCallback();
    }
}

customElements.define('ntx-stream', NTTStream);
