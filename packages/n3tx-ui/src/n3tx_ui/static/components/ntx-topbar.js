/**
 * NTTTopbar — Framework-level sticky navigation bar.
 *
 * Standalone web component (no Actor dependency).
 * Uses the Permissions singleton for user state.
 * Fetches /_meta for app name + version defaults.
 *
 * Attributes:
 *   brand   — App name (default: from /_meta)
 *   version — Version tag (default: from /_meta)
 *   logo    — Logo text (default: first 2 chars of brand)
 *   href    — Brand link destination (default: "/")
 *   no-user — Hide the user pill entirely
 *   hide-brand — Omit the brand block when another shell owns it
 *
 * Slots:
 *   nav — Center navigation links (light DOM children)
 *   user-menu — Manual authenticated dropdown actions
 *
 * Events dispatched:
 *   sidebar-toggle — on document, when hamburger is clicked
 *
 * Usage:
 *   <ntx-topbar brand="My App" version="1.0">
 *     <a href="#@favorites" slot="nav">Favorites</a>
 *     <ntx-theme-button slot="user-menu"></ntx-theme-button>
 *   </ntx-topbar>
 */
import { permissions } from '../utils/Permissions.js';
import { config } from '../config.js';
import './ntx-theme-button.js';

const TOPBAR_CSS = new URL('./ntx-topbar.css', import.meta.url).href;

// SVG icons
const ICON_PROFILE = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
const ICON_LOGOUT = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`;
const CHEVRON = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`;
const ICON_HAMBURGER = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`;

// Module-level /_meta cache
let _metaCache = null;
let _metaPromise = null;

function fetchMeta() {
  if (_metaPromise) return _metaPromise;
  _metaPromise = fetch(`${config.API_URL}/_meta`)
    .then(r => r.ok ? r.json() : null)
    .catch(() => null)
    .then(data => { _metaCache = data; return data; });
  return _metaPromise;
}


class NTTTopbar extends HTMLElement {

  #link;

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    this.#link = document.createElement('link');
    this.#link.rel = 'stylesheet';
    this.#link.href = TOPBAR_CSS;
    this.shadowRoot.appendChild(this.#link);

    this.#render();
  }

  connectedCallback() {
    // Resolve /_meta defaults then re-render
    fetchMeta().then(() => this.#render());
    // Wait for permissions to resolve, then re-render with user data
    permissions.init().then(() => this.#render());
  }

  static get observedAttributes() {
    return ['brand', 'version', 'logo', 'href', 'no-user', 'hide-brand'];
  }

  attributeChangedCallback() {
    this.#render();
  }

  get #brand() {
    return this.getAttribute('brand') || _metaCache?.name || 'NTT';
  }

  get #version() {
    return this.getAttribute('version') || _metaCache?.version || '';
  }

  get #logo() {
    return this.getAttribute('logo') || this.#brand.slice(0, 2).toUpperCase();
  }

  get #href() {
    return this.getAttribute('href') || '/';
  }

  get #hasSidebar() {
    return !!document.querySelector('ntx-sidebar');
  }

  #render() {
    const user = permissions.user;
    const hideUser = this.hasAttribute('no-user');

    let actionsHtml = '';
    if (!hideUser) {
      actionsHtml = user
        ? this.#userPillHtml(user)
        : `<a href="/login.html" class="signin-link">Sign in</a>`;
    }

    const hamburgerHtml = this.#hasSidebar
      ? `<button class="sidebar-toggle" aria-label="Toggle sidebar">${ICON_HAMBURGER}</button>`
      : '';

    const versionHtml = this.#version
      ? `<span class="topbar-tag">v${this.#version.replace(/^v/, '')}</span>`
      : '';

    const hideBrand = this.hasAttribute('hide-brand');
    const navStyle = hideBrand
      ? 'flex:1 1 auto;justify-content:center;padding-left:0;margin-left:0;'
      : 'flex:1 1 auto;justify-content:center;padding-left:0.4rem;margin-left:0;';
    const actionsStyle = 'margin-left:auto;flex-shrink:0;';
    const brandHtml = hideBrand
      ? ''
      : `<a href="${this.#href}" class="topbar-brand">
          <div class="topbar-logo">${this.#logo}</div>
          <span class="topbar-title">${this.#brand}</span>
          ${versionHtml}
        </a>`;

    const nav = document.createElement('nav');
    nav.className = `topbar${hideBrand ? ' topbar--brandless' : ''}`;
    nav.innerHTML = `
      ${hamburgerHtml}
      ${brandHtml}
      <div class="topbar-nav" style="${navStyle}">
        <slot name="nav"></slot>
      </div>
      <div class="topbar-actions" style="${actionsStyle}">
        ${actionsHtml}
      </div>
    `;

    this.shadowRoot.replaceChildren(this.#link, nav);
    this.#syncUserMenuSlot();

    // Bind events
    this.shadowRoot.querySelector('.sidebar-toggle')
      ?.addEventListener('click', () => {
        document.dispatchEvent(new CustomEvent('sidebar-toggle'));
      });
    this.shadowRoot.querySelector('.logout-btn')
      ?.addEventListener('click', this.#onLogout);
  }

  #userPillHtml(user) {
    const initial = (user.name || user.email || '?')[0].toUpperCase();
    const displayName = user.name || user.email.split('@')[0];
    const email = user.email || '';
    const role = user.role || '';
    const avatarHtml = user.image
      ? `<img class="user-avatar" src="${user.image}" alt="${initial}" />`
      : `<div class="user-avatar">${initial}</div>`;

    return `
      <div class="user-pill">
        ${avatarHtml}
        <span class="user-name">${displayName}</span>
        <span class="user-chevron">${CHEVRON}</span>
        <div class="user-dropdown">
          <div class="dropdown-header">
            <div class="dropdown-email">${email}</div>
            ${role ? `<div class="dropdown-role">${role}</div>` : ''}
          </div>
          <div class="dropdown-divider user-menu-divider" hidden></div>
          <div class="user-menu-slot-wrap" hidden>
            <slot name="user-menu"></slot>
          </div>
          <a href="#@profile" class="dropdown-item">
            <span class="dropdown-icon">${ICON_PROFILE}</span>
            Profile
          </a>
          <div class="dropdown-divider"></div>
          <button class="dropdown-item danger logout-btn">
            <span class="dropdown-icon">${ICON_LOGOUT}</span>
            Logout
          </button>
        </div>
      </div>
    `;
  }

  #syncUserMenuSlot() {
    const slot = this.shadowRoot.querySelector('slot[name="user-menu"]');
    const wrap = this.shadowRoot.querySelector('.user-menu-slot-wrap');
    const divider = this.shadowRoot.querySelector('.user-menu-divider');

    if (!slot || !wrap || !divider) return;

    const update = () => {
      const hasContent = slot.assignedElements({ flatten: true }).length > 0;
      wrap.hidden = !hasContent;
      divider.hidden = !hasContent;
    };

    slot.addEventListener('slotchange', update);
    update();
  }

  #onLogout = (e) => {
    e.preventDefault();
    window.localStorage.removeItem('jwtToken');
    window.location.href = '/login.html';
  };
}

customElements.define('ntx-topbar', NTTTopbar);
