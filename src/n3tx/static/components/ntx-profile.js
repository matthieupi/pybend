/**
 * NTTProfile — User profile page component.
 *
 * Displays the authenticated user's identity (avatar, name, email, role).
 * Shown when navigating to #@profile via the topbar user menu.
 */
import { permissions } from '../utils/Permissions.js';

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
        <style>${STYLES}</style>
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
      <style>${STYLES}</style>
      <div class="profile-card">
        <div class="avatar">${initial}</div>
        <h2>${name}</h2>
        <span class="email">${user.email || ''}</span>
        ${roleBadge}
        <p class="placeholder">Profile settings coming soon.</p>
      </div>
    `;
  }
}

const STYLES = `
  :host {
    display: block;
    padding: 2rem;
  }
  .profile-empty {
    text-align: center;
    color: var(--text-2, #9ba3bd);
    padding: 3rem;
    font-size: 1.1rem;
  }
  .profile-card {
    max-width: 400px;
    margin: 0 auto;
    text-align: center;
    padding: 2rem;
    background: var(--glass-bg, rgba(22, 26, 38, 0.6));
    border: 1px solid var(--border, rgba(255,255,255,0.06));
    border-radius: 1rem;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }
  .avatar {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--gradient-accent, linear-gradient(135deg, #22d3c5, #6366f1));
    color: white;
    font-size: 1.8rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1rem;
  }
  h2 {
    margin: 0 0 0.25rem;
    color: var(--text-0, #e8ecf4);
    font-size: 1.4rem;
  }
  .email {
    display: block;
    color: var(--text-2, #9ba3bd);
    font-size: 0.9rem;
    margin-bottom: 0.75rem;
  }
  .role {
    display: inline-block;
    padding: 0.2rem 0.75rem;
    border-radius: 100px;
    background: var(--accent-dim, rgba(34,211,197,0.08));
    color: var(--accent-text, #5eeadf);
    font-size: 0.8rem;
    font-weight: 600;
  }
  .placeholder {
    margin-top: 1.5rem;
    color: var(--text-3, #6b7280);
    font-size: 0.85rem;
    font-style: italic;
  }
`;

customElements.define('ntx-profile', NTTProfile);

export { NTTProfile };
