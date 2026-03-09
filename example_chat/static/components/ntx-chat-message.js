/**
 * NTTChatMessage — Chat message bubble.
 *
 * Extends NTTItem. Overrides rendering for chat bubble format.
 * Receives message data directly via messageData setter (messages
 * are loaded in bulk, not individually via ATTACH/READ).
 *
 * User messages: plain text, right-aligned.
 * Assistant messages: markdown-rendered, left-aligned.
 */
import { NTTItem } from './ntx-item.js';

export class NTTChatMessage extends NTTItem {

  get styles() { return new URL('./ntx-chat-message.css', import.meta.url).href; }

  /** Allow setting message data directly without going through NTT attach. */
  set messageData(data) {
    this.value = data;
    // Provide a minimal schema so render() proceeds
    if (!this.schema || !this.schema.__name__) {
      this.schema = { __name__: 'Message', properties: {} };
    }
    this.scheduleRender();
  }

  /** Escape HTML to prevent XSS. */
  #esc(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
  }

  /** Render markdown for assistant messages. Falls back to escaped text. */
  #renderMarkdown(text) {
    if (window.marked) {
      try { return window.marked.parse(text); } catch {}
    }
    return `<p>${this.#esc(text)}</p>`;
  }

  /** Chat bubble — used for all sizes. */
  #bubble() {
    const v = this.value || {};
    const role = v.role || 'user';
    const content = v.content || '';

    // Skip system/empty messages
    if (role === 'system' || !content) return '';

    const body = role === 'assistant'
      ? this.#renderMarkdown(content)
      : this.#esc(content);

    return `<div class="chat-bubble ${role}">${body}</div>`;
  }

  xs() { return this.#bubble(); }
  sm() { return this.#bubble(); }
  md() { return this.#bubble(); }
  lg() { return this.#bubble(); }
  xl() { return this.#bubble(); }

  render() {
    const v = this.value || {};
    if (!v.content || v.role === 'system') {
      this.shadowRoot.innerHTML = '';
      return;
    }
    this.shadowRoot.innerHTML = this.#bubble();
  }
}

customElements.define('ntx-chat-message', NTTChatMessage);
