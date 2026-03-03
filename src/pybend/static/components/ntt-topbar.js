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
 *
 * Slots:
 *   nav — Center navigation links (light DOM children)
 *
 * Events dispatched:
 *   sidebar-toggle — on document, when hamburger is clicked
 *
 * Usage:
 *   <ntt-topbar brand="My App" version="1.0">
 *     <a href="#@favorites" slot="nav">Favorites</a>
 *   </ntt-topbar>
 */
import { permissions } from '../utils/Permissions.js';
import { getTheme, toggleTheme } from '../utils/theme.js';
import { config } from '../config.js';

const TOPBAR_CSS = new URL('./ntt-topbar.css', import.meta.url).href;

// SVG icons
const ICON_PROFILE = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
const ICON_LOGOUT = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`;
const CHEVRON = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`;
const ICON_SUN = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
const ICON_MOON = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
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
    // Re-render on external theme change
    document.addEventListener('theme-change', () => this.#render());
  }

  static get observedAttributes() {
    return ['brand', 'version', 'logo', 'href', 'no-user'];
  }

  attributeChangedCallback() {
    this.#render();
  }

  get #brand() {
    return this.getAttribute('brand') || _metaCache?.name || 'PyBend';
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
    return !!document.querySelector('ntt-sidebar');
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

    const nav = document.createElement('nav');
    nav.className = 'topbar';
    nav.innerHTML = `
      ${hamburgerHtml}
      <a href="${this.#href}" class="topbar-brand">
        <div class="topbar-logo">${this.#logo}</div>
        <span class="topbar-title">${this.#brand}</span>
        ${versionHtml}
      </a>
      <div class="topbar-nav">
        <slot name="nav"></slot>
      </div>
      <div class="topbar-actions">
        ${actionsHtml}
      </div>
    `;

    this.shadowRoot.replaceChildren(this.#link, nav);

    // Bind events
    this.shadowRoot.querySelector('.sidebar-toggle')
      ?.addEventListener('click', () => {
        document.dispatchEvent(new CustomEvent('sidebar-toggle'));
      });
    this.shadowRoot.querySelector('.logout-btn')
      ?.addEventListener('click', this.#onLogout);
    this.shadowRoot.querySelector('.theme-toggle')
      ?.addEventListener('click', (e) => { e.stopPropagation(); toggleTheme(); });
  }

  #userPillHtml(user) {
    const initial = (user.name || user.email || '?')[0].toUpperCase();
    const displayName = user.name || user.email.split('@')[0];
    const email = user.email || '';
    const role = user.role || '';
    const isDark = getTheme() === 'dark';
    const themeIcon = isDark ? ICON_SUN : ICON_MOON;
    const themeLabel = isDark ? 'Light mode' : 'Dark mode';

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
          <div class="dropdown-divider"></div>
          <button class="dropdown-item theme-toggle">
            <span class="dropdown-icon">${themeIcon}</span>
            ${themeLabel}
          </button>
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

  #onLogout = (e) => {
    e.preventDefault();
    window.localStorage.removeItem('jwtToken');
    window.location.href = '/login.html';
  };
}

customElements.define('ntt-topbar', NTTTopbar);
