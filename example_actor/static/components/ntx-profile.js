/**
 * NTTProfile — User profile placeholder.
 *
 * Standalone web component (no Actor dependency).
 * Shows the current user's info in a glass card.
 * Routed via @profile hash (e.g. #@profile).
 */
import { permissions } from '../utils/Permissions.js';

class NTTProfile extends HTMLElement {

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    permissions.init().then(() => this.#render());
  }

  #render() {
    const user = permissions.user;

    if (!user) {
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; padding: 2rem; text-align: center; color: var(--text-2, #8891ab); }
        </style>
        <p>Not authenticated</p>
      `;
      return;
    }

    const initial = (user.name || user.email || '?')[0].toUpperCase();
    const displayName = user.name || user.email.split('@')[0];

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          max-width: 480px;
          margin: 2rem auto;
          animation: fadeIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
        }
        .profile-card {
          background: var(--glass-bg, rgba(14, 16, 24, 0.55));
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          border: 1px solid var(--glass-border, rgba(255,255,255,0.08));
          border-radius: var(--radius-lg, 16px);
          padding: 2.5rem;
          text-align: center;
        }
        .avatar {
          width: 80px;
          height: 80px;
          border-radius: 50%;
          background: linear-gradient(135deg, var(--accent, #22d3c5), #1a9e94);
          display: grid;
          place-items: center;
          font-size: 2rem;
          font-weight: 700;
          color: var(--surface-0, #08090c);
          margin: 0 auto 1.5rem;
          box-shadow: 0 4px 24px rgba(34, 211, 197, 0.15);
        }
        h2 {
          font-size: 1.25rem;
          font-weight: 600;
          color: var(--text-0, #f0f2f8);
          margin-bottom: 0.25rem;
        }
        .email {
          font-size: 0.9rem;
          color: var(--text-2, #8891ab);
          margin-bottom: 1rem;
        }
        .role {
          display: inline-block;
          font-size: 0.7rem;
          font-weight: 600;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: var(--accent-text, #5eeadf);
          background: var(--accent-dim, rgba(34, 211, 197, 0.12));
          border: 1px solid rgba(34, 211, 197, 0.15);
          border-radius: 100px;
          padding: 0.25rem 0.75rem;
        }
        .placeholder {
          margin-top: 2rem;
          padding-top: 1.5rem;
          border-top: 1px solid var(--border, rgba(255,255,255,0.06));
          color: var(--text-3, #555e78);
          font-size: 0.85rem;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      </style>
      <div class="profile-card">
        <div class="avatar">${initial}</div>
        <h2>${displayName}</h2>
        <div class="email">${user.email}</div>
        ${user.role ? `<span class="role">${user.role}</span>` : ''}
        <div class="placeholder">Profile settings coming soon</div>
      </div>
    `;
  }
}

customElements.define('ntx-profile', NTTProfile);
