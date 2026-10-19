/**
 * NTTChatInput — Streaming chat input.
 *
 * Extends NTTStream. Provides custom textarea + send button and handles
 * SSE streaming. Dispatches events for parent ntx-chat-view to consume:
 *   - user-message: immediate display of user's text
 *   - stream-chunk: each token from the LLM
 *   - stream-done:  streaming complete
 */
import { NTTStream } from './ntx-stream.js';
import HTTP from '../core/transport/HTTP.js';

export class NTTChatInput extends NTTStream {

  #conversationRef = null;
  #streaming = false;
  #chunks = [];

  get styles() { return new URL('./ntx-chat-input.css', import.meta.url).href; }

  /** Override — skip NTTMethod.load() which requires model/uuid attributes.
   * This component is created by ntx-chat-view and renders its own UI. */
  connectedCallback() {
    this.render();
  }

  /** Set the conversation reference URL for chat endpoint. */
  set conversationRef(ref) {
    this.#conversationRef = ref;
    this.#updateDisabled();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <div class="input-area">
        <textarea rows="1" placeholder="Type a message..." id="chatInput"></textarea>
        <button class="btn-send" id="btnSend" disabled>Send</button>
      </div>
    `;
    this.#bind();
  }

  #bind() {
    const textarea = this.shadowRoot.getElementById('chatInput');
    const btn = this.shadowRoot.getElementById('btnSend');

    textarea?.addEventListener('input', () => {
      this.#autoResize(textarea);
      this.#updateDisabled();
    });

    textarea?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.#send();
      }
    });

    btn?.addEventListener('click', () => this.#send());
  }

  #autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }

  #updateDisabled() {
    const btn = this.shadowRoot.getElementById('btnSend');
    const textarea = this.shadowRoot.getElementById('chatInput');
    if (btn) {
      btn.disabled = this.#streaming || !this.#conversationRef || !textarea?.value?.trim();
    }
  }

  #send() {
    const textarea = this.shadowRoot.getElementById('chatInput');
    const content = textarea?.value?.trim();
    if (!content || !this.#conversationRef || this.#streaming) return;

    // Dispatch user-message for immediate display
    this.dispatchEvent(new CustomEvent('user-message', {
      detail: { content },
      bubbles: true,
      composed: true,
    }));

    // Clear input
    textarea.value = '';
    this.#autoResize(textarea);

    // Start streaming
    this.#chunks = [];
    this.#streaming = true;
    this.#setInputDisabled(true);

    const url = `${this.#conversationRef}/chat`;
    this._streamHandle = HTTP.stream(url, { content },
      (chunk) => this.#onChunk(chunk),
      (data) => this.#onDone(data),
      (err) => this.#onError(err),
    );
  }

  #onChunk(data) {
    this.#chunks.push(data);
    this.dispatchEvent(new CustomEvent('stream-chunk', {
      detail: data,
      bubbles: true,
      composed: true,
    }));
  }

  #onDone(data) {
    this.#streaming = false;
    this._streamHandle = null;
    this.#setInputDisabled(false);
    this.dispatchEvent(new CustomEvent('stream-done', {
      detail: data,
      bubbles: true,
      composed: true,
    }));
  }

  #onError(data) {
    this.#streaming = false;
    this._streamHandle = null;
    this.#setInputDisabled(false);
    this.dispatchEvent(new CustomEvent('stream-done', {
      detail: { error: data?.message || data?.error || 'Stream error' },
      bubbles: true,
      composed: true,
    }));
  }

  #setInputDisabled(disabled) {
    const textarea = this.shadowRoot.getElementById('chatInput');
    const btn = this.shadowRoot.getElementById('btnSend');
    if (textarea) textarea.disabled = disabled;
    if (btn) btn.disabled = disabled;
    if (!disabled) {
      textarea?.focus();
      this.#updateDisabled();
    }
  }

  /** No-op — output is rendered by parent ntx-chat-view. */
  _renderOutput() {}

  /** Override callMethod — we handle streaming ourselves. */
  callMethod() { this.#send(); }
}

customElements.define('ntx-chat-input', NTTChatInput);
