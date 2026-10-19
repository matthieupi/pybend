import { resolveIcon } from '../utils/icon-resolver.js';

const STYLES = `
  :host {
    --icon-size: 1.05rem;
    --icon-opacity: 0.92;
    --icon-filter: grayscale(1) contrast(1.1);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--icon-size);
    block-size: var(--icon-size);
    flex-shrink: 0;
    line-height: 1;
    vertical-align: middle;
  }

  .icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: 100%;
    block-size: 100%;
    opacity: var(--icon-opacity);
  }

  .icon--emoji {
    filter: var(--icon-filter);
    font-size: var(--icon-size);
  }

  .icon--image {
    inline-size: 100%;
    block-size: 100%;
    object-fit: contain;
  }

  .icon--svg {
    inline-size: 100%;
    block-size: 100%;
  }

  .icon--text {
    min-inline-size: max-content;
    font-size: calc(var(--icon-size) * 0.72);
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
`;

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeAttr(value = '') {
  return escapeHtml(value).replace(/"/g, '&quot;');
}

class NTTIcon extends HTMLElement {
  static get observedAttributes() {
    return ['value', 'label', 'title', 'decorative'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.render();
  }

  attributeChangedCallback() {
    this.render();
  }

  render() {
    const resolved = resolveIcon(this.getAttribute('value'));
    const decorative = this.hasAttribute('decorative');
    const label = this.getAttribute('label') || this.getAttribute('title') || resolved?.raw || '';
    const title = this.getAttribute('title') || label;

    let body = '';
    if (resolved?.kind === 'image') {
      body = `<img class="icon icon--image" src="${escapeAttr(resolved.value)}" alt="${decorative ? '' : escapeAttr(label)}" title="${escapeAttr(title)}" />`;
    } else if (resolved?.kind === 'svg') {
      body = `<svg class="icon icon--svg" xmlns="http://www.w3.org/2000/svg" viewBox="${escapeAttr(resolved.viewBox || '0 0 24 24')}" fill="${escapeAttr(resolved.fill || 'none')}" stroke="${escapeAttr(resolved.stroke || 'currentColor')}" stroke-width="${escapeAttr(resolved.strokeWidth || '2')}" stroke-linecap="${escapeAttr(resolved.strokeLinecap || 'round')}" stroke-linejoin="${escapeAttr(resolved.strokeLinejoin || 'round')}"${decorative ? ' aria-hidden="true"' : ` role="img" aria-label="${escapeAttr(label)}"`} title="${escapeAttr(title)}">${resolved.value}</svg>`;
    } else if (resolved?.kind === 'emoji') {
      body = `<span class="icon icon--emoji"${decorative ? ' aria-hidden="true"' : ` role="img" aria-label="${escapeAttr(label)}"`} title="${escapeAttr(title)}">${escapeHtml(resolved.value)}</span>`;
    } else if (resolved?.kind === 'text') {
      body = `<span class="icon icon--text"${decorative ? ' aria-hidden="true"' : ` role="img" aria-label="${escapeAttr(label)}"`} title="${escapeAttr(title)}">${escapeHtml(resolved.value)}</span>`;
    }

    this.shadowRoot.innerHTML = `<style>${STYLES}</style>${body}`;
  }
}

customElements.define('ntx-icon', NTTIcon);
