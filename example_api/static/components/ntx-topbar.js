/**
 * NTTTopbar — Sticky navigation bar with brand and user menu.
 *
 * Standalone web component (no Actor dependency).
 * Uses the Permissions singleton for user state.
 *
 * Usage:
 *   <ntx-topbar></ntx-topbar>
 *
 * Shows brand (logo + title + version) on the left.
 * Shows user pill with hover dropdown (Profile, Logout) on the right,
 * or a "Sign in" link when not authenticated.
 */
import { permissions } from '../utils/Permissions.js';
import { getTheme, toggleTheme } from '../utils/theme.js';

const TOPBAR_CSS = new URL('./ntx-topbar.css', import.meta.url).href;

// SVG icons for dropdown items
const ICON_PROFILE = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
const ICON_LOGOUT = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`;
const CHEVRON = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`;

// Theme toggle icons (16px for dropdown)
const ICON_SUN = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
const ICON_MOON = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;

class NTTTopbar extends HTMLElement {

  #link;

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    // Stylesheet
    this.#link = document.createElement('link');
    this.#link.rel = 'stylesheet';
    this.#link.href = TOPBAR_CSS;
    this.shadowRoot.appendChild(this.#link);

    // Initial render (before user data loads)
    this.#render();
  }

  connectedCallback() {
    // Wait for permissions to resolve, then re-render with user data
    permissions.init().then(() => this.#render());
    // Re-render on external theme change
    document.addEventListener('theme-change', () => this.#render());
  }

  #render() {
    const user = permissions.user;

    const actionsHtml = user
      ? this.#userPillHtml(user)
      : `<a href="/login.html" class="signin-link">Sign in</a>`;

    // Build nav
    const nav = document.createElement('nav');
    nav.className = 'topbar';

    nav.innerHTML = `
      <a href="/" class="topbar-brand">
        <div class="topbar-logo">N3</div>
        <span class="topbar-title">NTT<span class="accent">TX</span></span>
        <span class="topbar-tag">v0.6</span>
      </a>
      <div class="topbar-nav">
        ${user ? '<a href="#@favorites" class="topbar-nav-link">Favorites</a>' : ''}
      </div>
      <div class="topbar-actions">
        ${actionsHtml}
      </div>
    `;

    // Replace shadow content (keep stylesheet)
    this.shadowRoot.replaceChildren(this.#link, nav);

    // Bind events
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

customElements.define('ntx-topbar', NTTTopbar);
