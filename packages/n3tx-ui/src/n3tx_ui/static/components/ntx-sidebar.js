/**
 * NTTSidebar — Framework-level slide-in sidebar with model navigation.
 *
 * Standalone web component (no Actor dependency).
 * Uses NTT.attach() to bootstrap model schemas and lazy-load record lists.
 *
 * Attributes:
 *   models — Comma-separated model class names (e.g. "Grant,Source,AgentActor")
 *   router — Router actor address for item click navigation (e.g. "main")
 *   view   — Default list component: "grid" (ntx-list) or "table" (ntx-table). Default: "grid"
 *   open   — Present when sidebar is visible
 *
 * Route templates (Light DOM children):
 *   Child elements with a `model` attribute serve as declarative route templates.
 *   Clicking the model name in the sidebar navigates to the component tag and
 *   attributes specified by the template element.  Children are hidden on connect.
 *
 *   When children are present and no `models` attribute is set, the model list
 *   is derived from the children (in DOM order).
 *
 *   Three entry types are supported:
 *
 *   <ntx-sidebar router="main">
 *     <ntx-table model="Grant" allow-create></ntx-table>   <!-- model: expandable list -->
 *     <ntx-list  model="Source"></ntx-list>                 <!-- model: expandable list -->
 *     <ntx-item  model="Organization"></ntx-item>           <!-- item: singleton nav -->
 *     <a href="#settings">Settings</a>                      <!-- link: hash navigation -->
 *   </ntx-sidebar>
 *
 *   Clicking "Grant" → router opens <ntx-table model="Grant" allow-create>
 *   Clicking "Organization" → router opens <ntx-item model="Organization" ref="Organization/1">
 *   Clicking "Settings" → router dispatches "#settings" hash route
 *
 * Listens for:
 *   sidebar-toggle — on document (from ntx-topbar hamburger)
 *
 * Legacy usage (still supported):
 *   <ntx-sidebar models="Grant,Source,AgentActor" view="table"></ntx-sidebar>
 */
import { NTT } from '../core/NTT.js';
import { matrix } from '../core/Matrix.js';
import { buildRoute } from '../core/Router.js';

const SIDEBAR_CSS = new URL('./ntx-sidebar.css', import.meta.url).href;

const ICON_CLOSE = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
const CHEVRON_RIGHT = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>`;
const ICON_LINK = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>`;

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
  #entries = [];            // ordered [{type, name, ...}]
  #models = [];             // model names (for NTT.attach bootstrapping)
  #routeTemplates = new Map(); // modelName → {tag, attrs}
  #dynamicClasses = {};     // modelName → DynamicClass
  #itemRefs = {};           // modelName → 'ModelName/id' (for item entries)
  #itemNames = {};          // modelName → display name (for item entries)
  #expanded = new Set();    // expanded model names
  #unsubs = [];             // cleanup callbacks

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    this.#link = document.createElement('link');
    this.#link.rel = 'stylesheet';
    this.#link.href = SIDEBAR_CSS;
    this.shadowRoot.appendChild(this.#link);
  }

  connectedCallback() {
    // Scan ALL direct children in DOM order
    const children = [...this.children];
    const SKIP = new Set(['model', 'slot', 'class', 'style', 'id', 'display']);

    for (const child of children) {
      if (child.hasAttribute('model')) {
        const modelName = child.getAttribute('model');
        const tag = child.tagName.toLowerCase();
        const attrs = {};
        for (const attr of child.attributes) {
          if (!SKIP.has(attr.name)) attrs[attr.name] = attr.value;
        }
        this.#routeTemplates.set(modelName, { tag, attrs });

        if (tag === 'ntx-item') {
          this.#entries.push({ type: 'item', name: modelName });
        } else {
          this.#entries.push({ type: 'model', name: modelName });
        }
        child.hidden = true;
      } else if (child.tagName === 'A' && child.hasAttribute('href')) {
        this.#entries.push({
          type: 'link',
          label: child.textContent.trim(),
          href: child.getAttribute('href'),
        });
        child.hidden = true;
      }
    }

    // Derive #models from model+item entries (for NTT.attach bootstrapping)
    this.#models = this.#entries
      .filter(e => e.type === 'model' || e.type === 'item')
      .map(e => e.name);

    // Legacy: if no children parsed, fall back to models attribute
    if (this.#entries.length === 0) {
      const modelsAttr = this.getAttribute('models') || '';
      const names = modelsAttr.split(',').map(s => s.trim()).filter(Boolean);
      for (const name of names) {
        this.#entries.push({ type: 'model', name });
      }
      this.#models = names;
    }

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
      const entry = this.#entries.find(e => e.name === modelName);
      const isItem = entry?.type === 'item';

      NTT.attach(modelName, (DC) => {
        this.#dynamicClasses[modelName] = DC;
        this.#updateModelHeader(modelName);

        if (isItem) {
          this.#fetchItemRef(modelName, DC);
        }

        // Subscribe to class-level UPDATE observable for count changes
        const unsub = DC.observe('UPDATE', () => {
          if (!isItem) this.#updateModelCount(modelName);
        });
        this.#unsubs.push(unsub);
      });
    }
  }

  /** Fetch the singleton item for an item-type entry */
  async #fetchItemRef(modelName, DC) {
    const token = localStorage.getItem('jwtToken');
    const headers = {};
    if (token) headers['x-access-token'] = token;

    try {
      const resp = await fetch(`${DC.href}?limit=1`, { headers });
      if (!resp.ok) return;
      const result = await resp.json();
      const data = result.data || result;
      if (data.length > 0) {
        const item = data[0];
        const id = item.id || item.$id?.split('/').pop();
        if (id) {
          this.#itemRefs[modelName] = `${modelName}/${id}`;
          const displayName = item.name || item.title || modelName;
          this.#itemNames[modelName] = displayName;

          // Update the name in the sidebar
          const nameEl = this.shadowRoot.querySelector(
            `.model-section[data-model="${modelName}"] .model-name`
          );
          if (nameEl) nameEl.textContent = displayName;
        }
      }
    } catch (e) {
      console.warn(`[ntx-sidebar] Failed to fetch item for ${modelName}:`, e);
    }
  }

  #updateModelHeader(modelName) {
    const header = this.shadowRoot.querySelector(`.model-section[data-model="${modelName}"] .model-header`);
    if (!header) return;

    const DC = this.#dynamicClasses[modelName];
    if (!DC) return;

    const entry = this.#entries.find(e => e.name === modelName);
    // For item entries, don't overwrite with schema name — wait for fetchItemRef
    if (entry?.type !== 'item') {
      const displayName = DC._schema?.__name__ || modelName;
      const nameEl = header.querySelector('.model-name');
      if (nameEl) nameEl.textContent = displayName;
    }

    if (entry?.type !== 'item') {
      this.#updateModelCount(modelName);
    }
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

  // View attribute → component tag mapping
  static VIEW_TAGS = {
    grid:  'ntx-list',
    table: 'ntx-table',
  };

  #navigateToModel(modelName) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    const template = this.#routeTemplates.get(modelName);
    const params = {};

    if (template) {
      // Map template tag to view= param
      if (template.tag === 'ntx-table') params.view = 'table';
      else if (template.tag !== 'ntx-list') params.view = template.tag.replace('ntx-', '');
      // Forward template attrs as query params
      for (const [k, v] of Object.entries(template.attrs)) {
        params[k] = v;
      }
    } else {
      const view = this.getAttribute('view') || 'grid';
      if (view === 'table') params.view = 'table';
      params['allow-create'] = '';
    }

    const route = buildRoute({
      type: 'model',
      model: modelName,
      params: Object.keys(params).length > 0 ? params : undefined,
    });

    matrix.dispatch({
      name: 'NAVIGATE',
      source: 'sidebar',
      target: routerAddr,
      data: route,
    });
    this.close();
  }

  #navigateToItem(modelName) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    const itemRef = this.#itemRefs[modelName];
    if (!itemRef) {
      this.#navigateToModel(modelName);
      return;
    }

    // itemRef is already "Model/id" — a valid route string
    matrix.dispatch({
      name: 'NAVIGATE',
      source: 'sidebar',
      target: routerAddr,
      data: itemRef,
    });
    this.close();
  }

  #navigateToLink(href) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    // Convert hash links to @appRoutes
    const route = href.startsWith('#') ? '@' + href.slice(1) : href;

    matrix.dispatch({
      name: 'NAVIGATE',
      source: 'sidebar',
      target: routerAddr,
      data: route,
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
      // Lazy-create ntx-list on first expand
      this.#ensureList(modelName, section);
    }
  }

  #ensureList(modelName, section) {
    const records = section.querySelector('.model-records');
    if (!records || records.childElementCount > 0) return;

    const list = document.createElement('ntx-list');
    list.setAttribute('model', modelName);
    list.setAttribute('display', 'sm');
    list.setAttribute('headless', '');
    const routerAttr = this.getAttribute('router');
    if (routerAttr) list.setAttribute('router', routerAttr);
    records.appendChild(list);
  }

  // ── Render ──

  #render() {
    let avatarIdx = 0;

    const sectionsHtml = this.#entries.map((entry) => {
      if (entry.type === 'model') {
        return this.#renderModelEntry(entry.name, avatarIdx++);
      } else if (entry.type === 'item') {
        return this.#renderItemEntry(entry.name, avatarIdx++);
      } else if (entry.type === 'link') {
        return this.#renderLinkEntry(entry, avatarIdx++);
      }
      return '';
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

    // Bind entry-specific events
    for (const entry of this.#entries) {
      if (entry.type === 'model') {
        this.#bindModelEvents(entry.name);
      } else if (entry.type === 'item') {
        this.#bindItemEvents(entry.name);
      } else if (entry.type === 'link') {
        this.#bindLinkEvents(entry);
      }
    }
  }

  #renderModelEntry(modelName, idx) {
    const initial = modelName[0].toUpperCase();
    const gradient = AVATAR_GRADIENTS[idx % AVATAR_GRADIENTS.length];

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
  }

  #renderItemEntry(modelName, idx) {
    const initial = modelName[0].toUpperCase();
    const gradient = AVATAR_GRADIENTS[idx % AVATAR_GRADIENTS.length];

    return `
      <div class="model-section model-section--item" data-model="${modelName}">
        <button class="model-header">
          <div class="model-avatar" style="background: ${gradient}">${initial}</div>
          <span class="model-name">${modelName}</span>
        </button>
      </div>
    `;
  }

  #renderLinkEntry(entry, idx) {
    const gradient = AVATAR_GRADIENTS[idx % AVATAR_GRADIENTS.length];

    return `
      <div class="sidebar-link" data-href="${entry.href}">
        <button class="model-header">
          <div class="link-icon" style="background: ${gradient}">${ICON_LINK}</div>
          <span class="model-name">${entry.label}</span>
        </button>
      </div>
    `;
  }

  #bindModelEvents(modelName) {
    const section = this.shadowRoot.querySelector(`.model-section[data-model="${modelName}"]`);
    if (!section) return;
    // Click on model name → navigate to list view
    section.querySelector('.model-name')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.#navigateToModel(modelName);
    });
    // Click elsewhere on header → toggle accordion
    section.querySelector('.model-header')?.addEventListener('click', () => {
      this.#toggleSection(modelName);
    });
  }

  #bindItemEvents(modelName) {
    const section = this.shadowRoot.querySelector(
      `.model-section--item[data-model="${modelName}"]`
    );
    if (!section) return;
    // Click anywhere → navigate to item (no accordion)
    section.querySelector('.model-header')?.addEventListener('click', () => {
      this.#navigateToItem(modelName);
    });
  }

  #bindLinkEvents(entry) {
    const linkEl = this.shadowRoot.querySelector(`.sidebar-link[data-href="${entry.href}"]`);
    if (!linkEl) return;
    linkEl.querySelector('.model-header')?.addEventListener('click', () => {
      this.#navigateToLink(entry.href);
    });
  }
}

customElements.define('ntx-sidebar', NTTSidebar);
