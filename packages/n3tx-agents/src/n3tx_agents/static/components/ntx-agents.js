import TX from '../core/TX.js';
import { permissions } from '../utils/Permissions.js';
import { NTTList } from './ntx-list.js';
import './ntx-agent.js';
import './ntx-icon.js';
import './ntx-sidebar-link-item.js';

export class NtxAgents extends NTTList {

  get styles() {
    const base = super.styles;
    return [
      ...(Array.isArray(base) ? base : [base]),
      new URL('./ntx-agents.css', import.meta.url).href,
    ];
  }

  get childTag() {
    if (this.hasAttribute('sidebar-dropdown')) {
      return this.getAttribute('item-tag') || 'ntx-sidebar-link-item';
    }
    return super.childTag;
  }

  get childDisplay() {
    if (this.hasAttribute('sidebar-dropdown')) {
      return this.getAttribute('item-display') || 'sm';
    }
    return super.childDisplay;
  }

  update() {
    return false;
  }

  render() {
    if (!this.schema || !Array.isArray(this.value)) return;

    const meta = this.proto?._paginationMeta;
    const total = meta?.total ?? this.value.length;
    const hasMore = meta?.has_more ?? false;
    const headless = this.hasAttribute('headless');
    const builtIns = this.#catalogEntries();
    const canCreate = !headless && this.hasAttribute('allow-create')
      && permissions.canAction(this.schema?.access, 'create');

    this.shadowRoot.innerHTML = `
      ${headless ? '' : this.#headerHtml(total, canCreate)}
      <div class="agents-shell">
        ${this.#builtInsSection(builtIns)}
        ${this.#storedSection()}
      </div>
      ${hasMore ? '<button class="load-more-btn">Load More</button>' : ''}
    `;

    this.#mountStoredEntries();
    this.#bindBuiltInNavigation();
    this.shadowRoot.querySelector('.load-more-btn')?.addEventListener('click', () => this.loadMore());
    this.shadowRoot.querySelector('.add-btn')?.addEventListener('click', () => this.openCreateModal());
  }

  #catalogEntries() {
    const catalog = this.getAttribute('catalog');
    if (!catalog) return [];
    const catalogs = window.NTX_AGENT_CATALOGS || {};
    const entries = catalogs[catalog];
    return Array.isArray(entries) ? entries : [];
  }

  #headerHtml(total, canCreate) {
    const description = this.schema?.ui?.description || '';
    const createLabel = this.schema?.ui?.create_label || '';
    const addBtnClass = createLabel ? 'add-btn add-btn--text' : 'add-btn';
    const addBtnTitle = createLabel || 'Add new';
    const addBtnContent = createLabel
      ? `<span class="add-btn-plus">+</span><span class="add-btn-label">${this.#esc(createLabel)}</span>`
      : '+';

    return `
      <div class="list-header">
        <div class="list-heading">
          <div class="list-title-wrap">
            ${this.#headerIcon()}
            <h1>${this.#esc(this.#title())} <span class="list-count">${this.value.length}${this.proto?._paginationMeta ? ` / ${total}` : ''}</span></h1>
          </div>
          ${description ? `<p class="list-description">${this.#esc(description)}</p>` : ''}
        </div>
        ${canCreate ? `<button class="${addBtnClass}" title="${this.#esc(addBtnTitle)}">${addBtnContent}</button>` : ''}
      </div>
    `;
  }

  #headerIcon() {
    const icon = this.schema?.ui?.icon;
    if (!icon) return '';
    return `<ntx-icon value="${this.#escAttr(icon)}" label="${this.#escAttr(this.#title())}" class="list-title-icon"></ntx-icon>`;
  }

  #title() {
    return this.getAttribute('title')
      || this.schema?.ui?.title
      || this.schema?.title
      || this.schema?.__name__
      || this.model
      || 'Agents';
  }

  #builtInsSection(entries) {
    if (!entries.length) return '';

    const items = entries.map((entry) => this.hasAttribute('sidebar-dropdown')
      ? this.#builtInLink(entry)
      : this.#builtInCard(entry)).join('');

    return `
      <section class="agents-section agents-section--builtins">
        <div class="agents-section-header">Built-in Agents</div>
        <div class="agents-builtins">${items}</div>
      </section>
    `;
  }

  #storedSection() {
    return `
      <section class="agents-section agents-section--stored">
        <div class="agents-section-header">Stored Agents</div>
        <div class="agents-stored-list"></div>
      </section>
    `;
  }

  #builtInCard(entry) {
    const route = this.#routeFor(entry);
    return `
      <button type="button" class="agent-launch-card" data-route="${this.#escAttr(route)}">
        <span class="agent-launch-card-top">
          ${this.#iconMarkup(entry.icon, entry.title)}
          <span class="agent-launch-kind">Built-in</span>
        </span>
        <span class="agent-launch-title">${this.#esc(entry.title || 'Agent')}</span>
        <span class="agent-launch-summary">${this.#esc(entry.summary || '')}</span>
        <span class="agent-launch-cta">${this.#esc(entry.cta || 'Open')}</span>
      </button>
    `;
  }

  #builtInLink(entry) {
    const route = this.#routeFor(entry);
    return `
      <button type="button" class="agent-launch-link" data-route="${this.#escAttr(route)}">
        <span class="agent-launch-link-main">
          ${this.#iconMarkup(entry.icon, entry.title)}
          <span class="agent-launch-link-copy">
            <span class="agent-launch-title">${this.#esc(entry.title || 'Agent')}</span>
            <span class="agent-launch-summary">${this.#esc(entry.summary || '')}</span>
          </span>
        </span>
        <span class="agent-launch-cta">${this.#esc(entry.cta || 'Open')}</span>
      </button>
    `;
  }

  #iconMarkup(icon, label) {
    if (!icon) return '<span class="agent-launch-icon agent-launch-icon--empty"></span>';
    return `<ntx-icon class="agent-launch-icon" value="${this.#escAttr(icon)}" label="${this.#escAttr(label || 'Agent')}"></ntx-icon>`;
  }

  #mountStoredEntries() {
    const host = this.shadowRoot.querySelector('.agents-stored-list');
    if (!host) return;
    if (!this.value.length) {
      host.innerHTML = '<div class="agents-empty">No stored agents yet.</div>';
      return;
    }

    const fragment = document.createDocumentFragment();
    this.value.forEach((addr, index) => {
      const child = this.createChild(addr);
      child.setAttribute('data-value', addr);
      child.style.setProperty('--stagger-delay', `${index * 50}ms`);
      fragment.appendChild(child);
    });
    host.appendChild(fragment);
  }

  #bindBuiltInNavigation() {
    this.shadowRoot.querySelectorAll('[data-route]').forEach((button) => {
      button.addEventListener('click', () => this.#navigate(button.getAttribute('data-route') || ''));
    });
  }

  #navigate(route) {
    const router = this.getAttribute('router');
    if (router) {
      this.send(new TX({
        name: 'NAVIGATE',
        source: this.addr,
        target: router,
        data: route,
        meta: { reset: true },
      }));
      return;
    }
    window.location.hash = route || '';
  }

  #routeFor(entry) {
    return typeof entry?.route === 'string' ? entry.route : '';
  }

  #esc(value) {
    const node = document.createElement('div');
    node.textContent = String(value ?? '');
    return node.innerHTML;
  }

  #escAttr(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
}

customElements.define('ntx-agents', NtxAgents);
