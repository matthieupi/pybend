/**
 * NTTChatSidebar — Conversation list sidebar.
 *
 * Extends ListElement. Custom sidebar layout with header,
 * conversation list, footer with LLM status and user info.
 */
import { ListElement } from './ListElement.js';
import { permissions } from '../utils/Permissions.js';
import HTTP from '../core/transport/HTTP.js';

export class NTTChatSidebar extends ListElement {

  #llmInterval = null;
  #activeRef = null;

  get childTag() { return 'ntx-chat-conv'; }
  get childDisplay() { return 'sm'; }
  get styles() { return new URL('./ntx-chat-sidebar.css', import.meta.url).href; }

  connectedCallback() {
    super.connectedCallback();
    this.#startLLMPoll();

    // Listen for conversation selection to update active state
    document.addEventListener('select-conversation', (e) => {
      this.#setActive(e.detail);
    });
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.#llmInterval) {
      clearInterval(this.#llmInterval);
      this.#llmInterval = null;
    }
  }

  render() {
    if (!this.schema) return;

    const canCreate = permissions.canAction(this.schema?.access, 'create');

    this.shadowRoot.innerHTML = `
      <div class="sidebar-header">
        <h2>Chats</h2>
        ${canCreate ? '<button class="btn-new" id="btnNew">+ New</button>' : ''}
      </div>
      <div class="conv-list list-grid" id="convList"></div>
      <div class="sidebar-footer">
        <div class="llm-status" id="llmStatus">
          <span class="dot connecting"></span>
          <span class="label">Connecting...</span>
        </div>
        <div class="user-row">
          <span id="userName"></span>
          <button class="btn-logout" id="btnLogout">Sign out</button>
        </div>
      </div>
    `;

    // Stamp conversation children
    const grid = this.shadowRoot.getElementById('convList');
    if (grid && Array.isArray(this.value)) {
      const fragment = document.createDocumentFragment();
      this.value.forEach(addr => {
        const child = this.createChild(addr);
        child.setAttribute('data-value', addr);
        fragment.appendChild(child);
      });
      grid.appendChild(fragment);
    }

    // Bind new button
    this.shadowRoot.getElementById('btnNew')?.addEventListener('click', () => {
      this.proto.call('CREATE', { name: 'New Chat' }, { inbox: 'CREATE' });
    });

    // Bind logout
    this.shadowRoot.getElementById('btnLogout')?.addEventListener('click', () => {
      localStorage.removeItem('jwtToken');
      window.location.reload();
    });

    // Display user info from JWT
    this.#displayUser();

    // Check LLM status immediately
    this.#checkLLMStatus();
  }

  #displayUser() {
    const el = this.shadowRoot.getElementById('userName');
    if (!el) return;
    try {
      const token = localStorage.getItem('jwtToken');
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        el.textContent = payload.email || 'User';
      }
    } catch {}
  }

  #startLLMPoll() {
    if (this.#llmInterval) clearInterval(this.#llmInterval);
    this.#llmInterval = setInterval(() => this.#checkLLMStatus(), 15000);
  }

  async #checkLLMStatus() {
    const el = this.shadowRoot?.getElementById('llmStatus');
    if (!el) return;
    try {
      const resp = await fetch(`${window.location.origin}/api/llm-status`);
      const data = await resp.json();
      const dot = el.querySelector('.dot');
      const label = el.querySelector('.label');
      dot.className = 'dot ' + data.status;
      const model = (data.model || '').replace(/^ollama:/, '');
      label.textContent = data.status === 'ready'
        ? (model || 'LLM ready')
        : (model ? `${model} (offline)` : 'LLM offline');
    } catch {
      const dot = el.querySelector('.dot');
      const label = el.querySelector('.label');
      if (dot) dot.className = 'dot offline';
      if (label) label.textContent = 'LLM offline';
    }
  }

  #setActive(ref) {
    this.#activeRef = ref;
    const grid = this.shadowRoot?.getElementById('convList');
    if (!grid) return;
    grid.querySelectorAll('ntx-chat-conv').forEach(el => {
      const addr = el.getAttribute('data-value') || '';
      el.active = addr === ref || addr.endsWith(`/${ref.split('/').pop()}`);
    });
  }
}

customElements.define('ntx-chat-sidebar', NTTChatSidebar);
