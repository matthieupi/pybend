/**
 * NTTProfile — User profile page component.
 *
 * Displays the authenticated user's identity (avatar, name, email, role).
 * Shown when navigating to #@profile via the topbar user menu.
 */
import { permissions } from '../utils/Permissions.js';

const STYLES_URL = new URL('./ntx-profile.css', import.meta.url).href;

class NTTProfile extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.#load();
  }

  async #load() {
    await permissions.init();
    this.#render();
  }

  #render() {
    const user = permissions.user;

    if (!user) {
      this.shadowRoot.innerHTML = `
        <link rel="stylesheet" href="${STYLES_URL}">
        <div class="profile-empty">Not authenticated</div>
      `;
      return;
    }

    const name = user.name || user.email?.split('@')[0] || '?';
    const initial = name.charAt(0).toUpperCase();
    const roleBadge = user.role
      ? `<span class="role">${user.role}</span>`
      : '';

    this.shadowRoot.innerHTML = `
      <link rel="stylesheet" href="${STYLES_URL}">
      <div class="profile-card">
        <div class="profile-card-shell">
          <div class="avatar">${initial}</div>
          <div class="profile-copy">
            <div class="profile-kicker">Profile</div>
            <h2>${name}</h2>
            <span class="email">${user.email || ''}</span>
            ${roleBadge}
          </div>
          <p class="profile-note">Profile settings coming soon.</p>
        </div>
      </div>
    `;
  }
}

customElements.define('ntx-profile', NTTProfile);

export { NTTProfile };
