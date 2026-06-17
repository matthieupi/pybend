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
 *   Use `sidebar-label="..."` on a template child to override the label shown
 *   in the sidebar without changing the mounted route/view.
 *
 *   When children are present and no `models` attribute is set, the model list
 *   is derived from the children (in DOM order).
 *
 *   Three entry types are supported:
 *
 *   <ntx-sidebar router="main">
 *     <ntx-table model="Grant" allow-create></ntx-table>   <!-- model: expandable list -->
 *     <ntx-list model="AgentActor" sidebar-label="Agents"></ntx-list>
 *     <ntx-list  model="Source"></ntx-list>                 <!-- model: expandable list -->
 *     <ntx-item  model="Organization"></ntx-item>           <!-- item: singleton nav -->
 *     <a href="#settings" icon="settings">Settings</a>      <!-- link: hash navigation -->
 *     <ntx-theme-button slot="footer"></ntx-theme-button>   <!-- footer: manual shell action -->
 *   </ntx-sidebar>
 *
 *   Clicking "Grant" → router opens Grant/@table?allow-create=
 *   Clicking "Organization" → router opens Organization/1/@
 *   Clicking "Settings" → router dispatches @settings
 *
 * Listens for:
 *   sidebar-toggle — on document (from ntx-topbar hamburger)
 *
 * Legacy usage (still supported):
 *   <ntx-sidebar models="Grant,Source,AgentActor" view="table"></ntx-sidebar>
 */
import { NTT } from '../core/NTT.js';
import { matrix } from '../core/Matrix.js';
import { buildRoute, getRouter, parseRoute } from '../core/Router.js';
import { iconMarkup } from '../utils/icon-resolver.js';
import './ntx-icon.js';
import './ntx-sidebar-link-item.js';
import './ntx-theme-button.js';

const SIDEBAR_CSS = new URL('./ntx-sidebar.css', import.meta.url).href;

const ICON_CLOSE = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
const CHEVRON_RIGHT = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>`;
const ICON_LINK = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>`;

// Accent gradient palette for model avatars
const AVATAR_GRADIENTS = [
  'linear-gradient(135deg, #3adffa, #00cbe6)',
  'linear-gradient(135deg, #6ef9e2, #2fbca6)',
  'linear-gradient(135deg, #ffb866, #c97b24)',
  'linear-gradient(135deg, #90d7de, #4e6874)',
  'linear-gradient(135deg, #89c4ff, #2d7fa7)',
  'linear-gradient(135deg, #9ee3d5, #257a48)',
  'linear-gradient(135deg, #ffd9a8, #a36310)',
  'linear-gradient(135deg, #b9d6ff, #3f5f8f)',
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
  #routerUnsub = null;

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
    const SKIP = new Set(['model', 'slot', 'class', 'style', 'id', 'display', 'sidebar-label']);

    for (const child of children) {
      if (child.hasAttribute('model')) {
        const modelName = child.getAttribute('model');
        const tag = child.tagName.toLowerCase();
        const sidebarLabel = child.getAttribute('sidebar-label') || '';
        const attrs = {};
        for (const attr of child.attributes) {
          if (!SKIP.has(attr.name)) attrs[attr.name] = attr.value;
        }
        this.#routeTemplates.set(modelName, { tag, attrs });

        if (tag === 'ntx-item') {
          this.#entries.push({ type: 'item', name: modelName, label: sidebarLabel || '' });
        } else {
          this.#entries.push({ type: 'model', name: modelName, label: sidebarLabel || '' });
        }
        child.hidden = true;
      } else if (child.tagName === 'A' && child.hasAttribute('href')) {
        this.#entries.push({
          type: 'link',
          label: child.textContent.trim(),
          href: child.getAttribute('href'),
          icon: child.getAttribute('icon') || '',
        });
        child.hidden = true;
      }
    }

    // Derive #models from model+item entries (for NTT.attach bootstrapping)
    this.#models = this.#entries
      .filter(e => e.type === 'model' || e.type === 'item')
      .map(e => e.name);

    const modelsAttr = this.getAttribute('models') || '';
    const explicitNames = modelsAttr.split(',').map(s => s.trim()).filter(Boolean);
    if (explicitNames.length > 0) {
      this.#entries = explicitNames.map(name => ({ type: 'model', name }));
      this.#models = explicitNames;
    }

    // Legacy: if no children parsed, fall back to models attribute
    if (this.#entries.length === 0) {
      const names = explicitNames;
      for (const name of names) {
        this.#entries.push({ type: 'model', name });
      }
      this.#models = names;
    }

    this.#render();
    this.#bootstrapModels();
    this.#applyActiveRoute(this.#getCurrentRoute());
    this.#bindRouterState();
    queueMicrotask(() => this.#bindRouterState());

    // Listen for toggle events from topbar
    this._onToggle = () => this.toggle();
    document.addEventListener('sidebar-toggle', this._onToggle);

    // Close on Escape
    this._onKeydown = (e) => { if (e.key === 'Escape' && this.hasAttribute('open')) this.close(); };
    document.addEventListener('keydown', this._onKeydown);

    // Auto-close on navigation
    this._onNavigate = () => {
      if (this.hasAttribute('open')) this.close();
      this.#applyActiveRoute(this.#getCurrentRoute());
    };
    window.addEventListener('hashchange', this._onNavigate);
  }

  disconnectedCallback() {
    document.removeEventListener('sidebar-toggle', this._onToggle);
    document.removeEventListener('keydown', this._onKeydown);
    window.removeEventListener('hashchange', this._onNavigate);
    this.#routerUnsub?.();
    this.#routerUnsub = null;
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
          const entry = this.#entries.find((e) => e.name === modelName);
          const displayName = entry?.label || item.name || item.title || modelName;
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
      const displayName = entry?.label || DC._schema?.title || DC._schema?.__name__ || modelName;
      const nameEl = header.querySelector('.model-name');
      if (nameEl) nameEl.textContent = displayName;
    }

    const avatar = header.querySelector('.model-avatar');
    const icon = DC._schema?.ui?.icon;
    if (avatar) {
      avatar.innerHTML = icon
        ? iconMarkup(icon, { label: DC._schema?.__name__ || modelName, className: 'sidebar-model-icon' })
        : modelName[0].toUpperCase();
      avatar.classList.toggle('model-avatar--icon', !!icon);
      avatar.style.background = icon ? 'transparent' : '';
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

  #bindRouterState() {
    this.#routerUnsub?.();
    this.#routerUnsub = null;

    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    const router = getRouter(routerAddr);
    if (!router?.observe) return;

    this.#applyActiveRoute(typeof router.current === 'string' ? router.current : this.#getCurrentRoute());
    this.#routerUnsub = router.observe('route', (route) => {
      this.#applyActiveRoute(route || '');
    });
  }

  #getCurrentRoute() {
    const hashRoute = window.location.hash.startsWith('#')
      ? window.location.hash.slice(1)
      : '';
    if (hashRoute) return hashRoute;

    const routerAddr = this.getAttribute('router');
    const router = routerAddr ? getRouter(routerAddr) : null;
    return typeof router?.current === 'string' ? router.current : '';
  }

  #clearActiveRoute() {
    this.shadowRoot.querySelectorAll('.model-section--selected')
      .forEach((section) => section.classList.remove('model-section--selected'));
    this.shadowRoot.querySelectorAll('.sidebar-link--selected')
      .forEach((link) => link.classList.remove('sidebar-link--selected'));
    this.shadowRoot.querySelectorAll('.model-header[aria-current="page"]')
      .forEach((header) => header.removeAttribute('aria-current'));
  }

  #applyActiveRoute(route = '') {
    if (!this.shadowRoot) return;

    this.#clearActiveRoute();

    const parsed = parseRoute(route);
    if (!parsed || parsed.type === 'home') return;

    if (parsed.type === 'app') {
      const activeLink = [...this.shadowRoot.querySelectorAll('.sidebar-link')].find((linkEl) => {
        const href = linkEl.getAttribute('data-href') || '';
        if (href.startsWith('#@')) return href.slice(2) === parsed.app;
        if (href.startsWith('#')) return href.slice(1) === parsed.app;
        return href === route;
      });
      if (!activeLink) return;

      activeLink.classList.add('sidebar-link--selected');
      activeLink.querySelector('.model-header')?.setAttribute('aria-current', 'page');
      return;
    }

    const activeSection = this.shadowRoot.querySelector(
      `.model-section[data-model="${parsed.model}"]`
    );
    if (!activeSection) return;

    activeSection.classList.add('model-section--selected');
    activeSection.querySelector('.model-header')?.setAttribute('aria-current', 'page');
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
    let view = null;

    if (template) {
      // Map template tags to explicit @ view routes. Table is a semantic view;
      // other custom component tags keep the existing tag-derived fallback.
      if (template.tag === 'ntx-table') view = 'table';
      else if (template.tag !== 'ntx-list') view = template.tag.replace('ntx-', '');
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
      isViewRoute: true,
      view,
      params: Object.keys(params).length > 0 ? params : undefined,
    });

    matrix.dispatch({
      name: 'NAVIGATE',
      source: 'sidebar',
      target: routerAddr,
      data: route,
      meta: { reset: true },
    });
    this.#applyActiveRoute(route);
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

    const [model, id] = itemRef.split('/');
    const route = buildRoute({
      type: 'detail',
      model: model || modelName,
      id,
      isViewRoute: true,
    });

    matrix.dispatch({
      name: 'NAVIGATE',
      source: 'sidebar',
      target: routerAddr,
      data: route,
      meta: { reset: true },
    });
    this.#applyActiveRoute(route);
    this.close();
  }

  #navigateToLink(href) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    // Convert hash links to router routes. Bare '#' means home.
    const route = href === '#'
      ? ''
      : href.startsWith('#@')
        ? href.slice(1)
        : href.startsWith('#')
          ? '@' + href.slice(1)
          : href;

    matrix.dispatch({
      name: 'NAVIGATE',
      source: 'sidebar',
      target: routerAddr,
      data: route,
      meta: { reset: true },
    });
    this.#applyActiveRoute(route);
    this.close();
  }

  #navigateHome() {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    matrix.dispatch({
      name: 'NAVIGATE',
      source: 'sidebar',
      target: routerAddr,
      data: buildRoute({ type: 'home' }),
      meta: { reset: true },
    });
    this.#applyActiveRoute('');
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

    const template = this.#routeTemplates.get(modelName);
    const templateTag = template?.tag || 'ntx-list';
    const usesCustomDropdownTag = templateTag !== 'ntx-list' && templateTag !== 'ntx-table';
    const tag = usesCustomDropdownTag ? templateTag : 'ntx-list';
    const list = document.createElement(tag);
    if (usesCustomDropdownTag) {
      for (const [key, value] of Object.entries(template?.attrs || {})) {
        list.setAttribute(key, value);
      }
    }
    list.setAttribute('model', modelName);
    list.setAttribute('sidebar-dropdown', '');
    list.setAttribute('headless', '');
    const routerAttr = this.getAttribute('router');
    if (routerAttr) list.setAttribute('router', routerAttr);
    if (!list.hasAttribute('display')) list.setAttribute('display', 'sm');
    list.style.setProperty('--ntx-sidebar-record-indent', '3.48rem');

    if (tag === 'ntx-list') {
      list.setAttribute('item-tag', 'ntx-sidebar-link-item');
      list.setAttribute('item-display', 'sm');
    }

    records.appendChild(list);
  }

  // ── Render ──

  get #brand() {
    return this.getAttribute('brand') || '';
  }

  get #subtitle() {
    return this.getAttribute('subtitle') || '';
  }

  get #brandLogo() {
    return this.getAttribute('brand-logo') || '';
  }

  #render() {
    let avatarIdx = 0;

    const sectionsHtml = this.#entries.map((entry) => {
      if (entry.type === 'model') {
        return this.#renderModelEntry(entry, avatarIdx++);
      } else if (entry.type === 'item') {
        return this.#renderItemEntry(entry, avatarIdx++);
      } else if (entry.type === 'link') {
        return this.#renderLinkEntry(entry);
      }
      return '';
    }).join('');

    const container = document.createElement('div');
    container.className = 'sidebar-container';
    const headerHtml = this.#brand
      ? `
        <div class="sidebar-brand">
          <div class="sidebar-brand-copy${this.getAttribute('router') ? ' sidebar-brand-copy--clickable' : ''}">
            ${this.#brandLogo ? `<img class="sidebar-brand-logo" src="${this.#brandLogo}" alt="${this.#brand} logo">` : ''}
            <div class="sidebar-brand-text">
            <div class="sidebar-brand-title">${this.#brand}</div>
            ${this.#subtitle ? `<div class="sidebar-brand-subtitle">${this.#subtitle}</div>` : ''}
            </div>
          </div>
          <button class="sidebar-close" aria-label="Close sidebar">${ICON_CLOSE}</button>
        </div>`
      : `
        <div class="sidebar-header">
          <span class="sidebar-title">Models</span>
          <button class="sidebar-close" aria-label="Close sidebar">${ICON_CLOSE}</button>
        </div>`;
    container.innerHTML = `
      <div class="sidebar-overlay"></div>
      <nav class="sidebar">
        ${headerHtml}
        <div class="sidebar-models">
          ${sectionsHtml}
        </div>
        <div class="sidebar-footer" hidden>
          <slot name="footer"></slot>
        </div>
      </nav>
    `;

    this.shadowRoot.replaceChildren(this.#link, container);
    this.#syncFooterSlot();

    // Bind events
    this.shadowRoot.querySelector('.sidebar-overlay')
      ?.addEventListener('click', () => this.close());
    this.shadowRoot.querySelector('.sidebar-close')
      ?.addEventListener('click', () => this.close());
    this.shadowRoot.querySelector('.sidebar-brand-copy--clickable')
      ?.addEventListener('click', () => this.#navigateHome());

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

  #syncFooterSlot() {
    const slot = this.shadowRoot.querySelector('slot[name="footer"]');
    const footer = this.shadowRoot.querySelector('.sidebar-footer');

    if (!slot || !footer) return;

    const update = () => {
      footer.hidden = slot.assignedElements({ flatten: true }).length === 0;
    };

    slot.addEventListener('slotchange', update);
    update();
  }

  #renderModelEntry(entry, idx) {
    const modelName = entry.name;
    const initial = modelName[0].toUpperCase();
    const gradient = AVATAR_GRADIENTS[idx % AVATAR_GRADIENTS.length];

    return `
      <div class="model-section" data-model="${modelName}">
        <button class="model-header">
          <div class="model-avatar" style="background: ${gradient}">${initial}</div>
          <span class="model-name">${entry.label || modelName}</span>
          <span class="model-count"></span>
          <span class="model-chevron">${CHEVRON_RIGHT}</span>
        </button>
        <div class="model-records"></div>
      </div>
    `;
  }

  #renderItemEntry(entry, idx) {
    const modelName = entry.name;
    const initial = modelName[0].toUpperCase();
    const gradient = AVATAR_GRADIENTS[idx % AVATAR_GRADIENTS.length];

    return `
      <div class="model-section model-section--item" data-model="${modelName}">
        <button class="model-header">
          <div class="model-avatar" style="background: ${gradient}">${initial}</div>
          <span class="model-name">${entry.label || modelName}</span>
        </button>
      </div>
    `;
  }

  #renderLinkEntry(entry) {
    const icon = entry.icon
      ? iconMarkup(entry.icon, { label: entry.label, className: 'sidebar-link-icon' })
      : ICON_LINK;

    return `
      <div class="sidebar-link" data-href="${entry.href}">
        <button class="model-header">
          <div class="link-icon">${icon}</div>
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
