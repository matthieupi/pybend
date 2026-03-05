import { NTTMethod } from './ntx-method.js';
import HTTP from '../core/transport/HTTP.js';

export class NTTStream extends NTTMethod {
    constructor() {
        super();
        this._chunks = [];
        this._streaming = false;
        this._streamHandle = null;
    }

    callMethod() {
        // Cancel any in-progress stream
        if (this._streamHandle) {
            this._streamHandle.cancel();
            this._streamHandle = null;
        }

        const payload = { ...this.value };
        this._chunks = [];
        this._streaming = true;
        this._renderOutput();

        const href = this.ntt ? `${this.ntt.href}` : this.proto?.href;
        if (!href) return;
        const url = `${href}/${this.method}`;

        this._streamHandle = HTTP.stream(url, payload,
            (chunk) => this._onChunk(chunk),
            (data)  => this._onDone(data),
            (err)   => this._onError(err),
        );
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        if (this._streamHandle) {
            this._streamHandle.cancel();
            this._streamHandle = null;
        }
    }

    _onChunk(data) {
        this._chunks.push(data);
        this._renderOutput();
    }

    _onDone(data) {
        this._streaming = false;
        this._streamHandle = null;
        if (data && Object.keys(data).length) this._chunks.push(data);
        this._renderOutput();
        if (this.ntt?.pull) this.ntt.pull();
    }

    _onError(data) {
        this._streaming = false;
        this._streamHandle = null;
        this.response = { error: data?.message || 'Stream error' };
        this._renderOutput();
    }

    _renderOutput() {
        let el = this.shadowRoot.querySelector('.stream-output');
        if (!el) {
            el = document.createElement('div');
            el.className = 'stream-output';
            this.shadowRoot.appendChild(el);
        }
        const text = this._chunks
            .map(c => c.chunk || c.text || c.content || JSON.stringify(c))
            .join('');
        el.innerHTML = `<div class="stream-text">${this._esc(text)}</div>`
            + (this._streaming ? '<span class="stream-cursor">|</span>' : '');
    }

    _esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

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
    `;
}

customElements.define('ntx-stream', NTTStream);
