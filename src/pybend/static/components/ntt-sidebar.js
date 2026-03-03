/**
 * NTTSidebar — Framework-level slide-in sidebar with model navigation.
 *
 * Standalone web component (no Actor dependency).
 * Uses NTT.attach() to bootstrap model schemas and lazy-load record lists.
 *
 * Attributes:
 *   models — Comma-separated model class names (e.g. "Grant,Source,AgentActor")
 *   router — Router actor address for item click navigation (e.g. "main")
 *   open   — Present when sidebar is visible
 *
 * Listens for:
 *   sidebar-toggle — on document (from ntt-topbar hamburger)
 *
 * Usage:
 *   <ntt-sidebar models="Grant,Source,AgentActor"></ntt-sidebar>
 */
import { NTT } from '../core/NTT.js';

const SIDEBAR_CSS = new URL('./ntt-sidebar.css', import.meta.url).href;

const ICON_CLOSE = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
const CHEVRON_RIGHT = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>`;

// Accent gradient palette for model avatars
const AVATAR_GRADIENTS = [
  'linear-gradient(135deg, #22d3c5, #1a9e94)',
  'linear-gradient(135deg, #6366f1, #4f46e5)',
  'linear-gradient(135deg, #f59e0b, #d97706)',
  'linear-gradient(135deg, #ec4899, #db2777)',
  'linear-gradient(135deg, #10b981, #059669)',
  'linear-gradient(135deg, #8b5cf6, #7c3aed)',
  'linear-gradient(135deg, #ef4444, #dc2626)',
  'linear-gradient(135deg, #06b6d4, #0891b2)',
];


class NTTSidebar extends HTMLElement {

  #link;
  #models = [];           // parsed model names
  #dynamicClasses = {};   // modelName → DynamicClass
  #expanded = new Set();  // expanded model names
  #unsubs = [];           // cleanup callbacks

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    this.#link = document.createElement('link');
    this.#link.rel = 'stylesheet';
    this.#link.href = SIDEBAR_CSS;
    this.shadowRoot.appendChild(this.#link);
  }

  connectedCallback() {
    // Parse models attribute
    const modelsAttr = this.getAttribute('models') || '';
    this.#models = modelsAttr.split(',').map(s => s.trim()).filter(Boolean);

    this.#render();
    this.#bootstrapModels();

    // Listen for toggle events from topbar
    this._onToggle = () => this.toggle();
    document.addEventListener('sidebar-toggle', this._onToggle);

    // Close on Escape
    this._onKeydown = (e) => { if (e.key === 'Escape' && this.hasAttribute('open')) this.close(); };
    document.addEventListener('keydown', this._onKeydown);

    // Auto-close on navigation
    this._onNavigate = () => {
      if (this.hasAttribute('open')) this.close();
    };
    window.addEventListener('hashchange', this._onNavigate);
  }

  disconnectedCallback() {
    document.removeEventListener('sidebar-toggle', this._onToggle);
    document.removeEventListener('keydown', this._onKeydown);
    window.removeEventListener('hashchange', this._onNavigate);
    for (const unsub of this.#unsubs) unsub();
    this.#unsubs = [];
  }

  // ── Public API ──

  toggle() {
    if (this.hasAttribute('open')) this.close();
    else this.open();
  }

  open() {
    this.setAttribute('open', '');
  }

  close() {
    this.removeAttribute('open');
  }

  // ── Model bootstrapping ──

  #bootstrapModels() {
    for (const modelName of this.#models) {
      NTT.attach(modelName, (DC) => {
        this.#dynamicClasses[modelName] = DC;
        this.#updateModelHeader(modelName);

        // Subscribe to class-level UPDATE observable for count changes
        const unsub = DC.observe('UPDATE', () => this.#updateModelCount(modelName));
        this.#unsubs.push(unsub);
      });
    }
  }

  #updateModelHeader(modelName) {
    const header = this.shadowRoot.querySelector(`.model-section[data-model="${modelName}"] .model-header`);
    if (!header) return;

    const DC = this.#dynamicClasses[modelName];
    if (!DC) return;

    const displayName = DC._schema?.__name__ || modelName;
    const nameEl = header.querySelector('.model-name');
    if (nameEl) nameEl.textContent = displayName;

    this.#updateModelCount(modelName);
  }

  #updateModelCount(modelName) {
    const countEl = this.shadowRoot.querySelector(`.model-section[data-model="${modelName}"] .model-count`);
    if (!countEl) return;

    const DC = this.#dynamicClasses[modelName];
    if (!DC) return;

    const total = DC._paginationMeta?.total ?? DC.instances?.size ?? '';
    countEl.textContent = total !== '' ? String(total) : '';
  }

  // ── Navigation ──

  #navigateToModel(modelName) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    // Dispatch NAVIGATE TX to the router via a custom event on window,
    // since the sidebar is not an Actor. The router listens for hashchange,
    // but object routes can't be serialized to hash — so we import Matrix
    // and send a TX directly.
    import('../core/Matrix.js').then(({ matrix }) => {
      const TX = matrix.constructor.TX || Object;
      // Build a simple TX-like message that the Router understands
      matrix.dispatch({
        name: 'NAVIGATE',
        source: 'sidebar',
        target: routerAddr,
        data: {
          tag: 'ntt-list',
          attrs: { model: modelName, 'allow-create': '' },
          title: modelName,
        },
      });
    });
    this.close();
  }

  // ── Section expand/collapse ──

  #toggleSection(modelName) {
    const section = this.shadowRoot.querySelector(`.model-section[data-model="${modelName}"]`);
    if (!section) return;

    if (this.#expanded.has(modelName)) {
      this.#expanded.delete(modelName);
      section.classList.remove('expanded');
    } else {
      this.#expanded.add(modelName);
      section.classList.add('expanded');
      // Lazy-create ntt-list on first expand
      this.#ensureList(modelName, section);
    }
  }

  #ensureList(modelName, section) {
    const records = section.querySelector('.model-records');
    if (!records || records.childElementCount > 0) return;

    const list = document.createElement('ntt-list');
    list.setAttribute('model', modelName);
    list.setAttribute('display', 'sm');
    list.setAttribute('headless', '');
    const routerAttr = this.getAttribute('router');
    if (routerAttr) list.setAttribute('router', routerAttr);
    records.appendChild(list);
  }

  // ── Render ──

  #render() {
    const sectionsHtml = this.#models.map((modelName, i) => {
      const initial = modelName[0].toUpperCase();
      const gradient = AVATAR_GRADIENTS[i % AVATAR_GRADIENTS.length];

      return `
        <div class="model-section" data-model="${modelName}">
          <button class="model-header">
            <div class="model-avatar" style="background: ${gradient}">${initial}</div>
            <span class="model-name">${modelName}</span>
            <span class="model-count"></span>
            <span class="model-chevron">${CHEVRON_RIGHT}</span>
          </button>
          <div class="model-records"></div>
        </div>
      `;
    }).join('');

    const container = document.createElement('div');
    container.className = 'sidebar-container';
    container.innerHTML = `
      <div class="sidebar-overlay"></div>
      <nav class="sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">Models</span>
          <button class="sidebar-close" aria-label="Close sidebar">${ICON_CLOSE}</button>
        </div>
        <div class="sidebar-models">
          ${sectionsHtml}
        </div>
      </nav>
    `;

    this.shadowRoot.replaceChildren(this.#link, container);

    // Bind events
    this.shadowRoot.querySelector('.sidebar-overlay')
      ?.addEventListener('click', () => this.close());
    this.shadowRoot.querySelector('.sidebar-close')
      ?.addEventListener('click', () => this.close());

    // Bind section headers
    for (const modelName of this.#models) {
      const section = this.shadowRoot.querySelector(`.model-section[data-model="${modelName}"]`);
      // Click on model name → navigate to list view
      section?.querySelector('.model-name')?.addEventListener('click', (e) => {
        e.stopPropagation();
        this.#navigateToModel(modelName);
      });
      // Click elsewhere on header → toggle accordion
      section?.querySelector('.model-header')?.addEventListener('click', () => {
        this.#toggleSection(modelName);
      });
    }
  }
}

customElements.define('ntt-sidebar', NTTSidebar);
