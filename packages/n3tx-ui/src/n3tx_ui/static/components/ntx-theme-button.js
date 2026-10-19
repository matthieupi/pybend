import {
  getConfiguredThemes,
  getNextTheme,
  getTheme,
  toggleTheme,
} from '../utils/theme.js';

const THEME_BUTTON_CSS = new URL('./ntx-theme-button.css', import.meta.url).href;
const ICON_THEME = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3"/><path d="M18.36 5.64l-2.12 2.12"/><path d="M21 12h-3"/><path d="M18.36 18.36l-2.12-2.12"/><path d="M12 18v3"/><path d="M7.76 16.24l-2.12 2.12"/><path d="M6 12H3"/><path d="M7.76 7.76L5.64 5.64"/><circle cx="12" cy="12" r="4"/></svg>`;

function formatThemeName(theme) {
  const value = String(theme || '').trim();
  if (!value) return 'Dark';
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ');
}

class NTTThemeButton extends HTMLElement {
  #link;
  #onThemeChange = () => this.render();

  static get observedAttributes() {
    return ['label', 'slot'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    this.#link = document.createElement('link');
    this.#link.rel = 'stylesheet';
    this.#link.href = THEME_BUTTON_CSS;
    this.shadowRoot.appendChild(this.#link);
  }

  connectedCallback() {
    document.addEventListener('theme-change', this.#onThemeChange);
    this.render();
  }

  disconnectedCallback() {
    document.removeEventListener('theme-change', this.#onThemeChange);
  }

  attributeChangedCallback() {
    this.render();
  }

  get #variant() {
    return this.getAttribute('slot') === 'user-menu' ? 'menu' : 'footer';
  }

  render() {
    const themes = getConfiguredThemes();
    const currentTheme = getTheme();
    const nextTheme = getNextTheme(currentTheme);
    const currentLabel = formatThemeName(currentTheme);
    const nextLabel = formatThemeName(nextTheme);
    const disabled = themes.length <= 1;
    const title = this.getAttribute('label') || 'Theme';
    const description = disabled ? currentLabel : `Next: ${nextLabel}`;
    const actionLabel = disabled
      ? `${title}: ${currentLabel}`
      : `${title}: ${currentLabel}. Switch to ${nextLabel}`;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = `theme-button theme-button--${this.#variant}`;
    button.setAttribute('aria-label', actionLabel);
    button.innerHTML = `
      <span class="theme-button__icon" aria-hidden="true">${ICON_THEME}</span>
      <span class="theme-button__copy">
        <span class="theme-button__label">${title}</span>
        <span class="theme-button__description">${description}</span>
      </span>
      <span class="theme-button__value">${currentLabel}</span>
    `;

    if (disabled) {
      button.disabled = true;
    } else {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleTheme();
      });
    }

    this.shadowRoot.replaceChildren(this.#link, button);
  }
}

customElements.define('ntx-theme-button', NTTThemeButton);
