/**
 * NTTChatConv — Sidebar conversation item.
 *
 * Extends NTTItem. Overrides xs/sm for slim sidebar rendering.
 * Click dispatches select-conversation event instead of standard NAVIGATE.
 */
import { NTTItem } from './ntx-item.js';

export class NTTChatConv extends NTTItem {

  get styles() { return new URL('./ntx-chat-conv.css', import.meta.url).href; }

  /** Escape HTML. */
  #esc(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
  }

  xs() { return this.sm(); }

  sm() {
    const name = this.#esc(this.value?.name || 'Untitled');
    return `<div class="conv-name">${name}</div>`;
  }

  render() {
    if (!this.value) return;
    this.shadowRoot.innerHTML = this.sm();
    // Click dispatches custom event for cross-component wiring
    this.shadowRoot.querySelector('.conv-name')?.addEventListener('click', () => {
      const ref = this.value?.['$id'] || this.value?.href || `conversations/${this.value?.id}`;
      this.dispatchEvent(new CustomEvent('select-conversation', {
        detail: ref,
        bubbles: true,
        composed: true,
      }));
    });
  }

  /** Set active state from parent sidebar. */
  set active(v) {
    this.shadowRoot.querySelector('.conv-name')
      ?.classList.toggle('active', !!v);
  }
}

customElements.define('ntx-chat-conv', NTTChatConv);
