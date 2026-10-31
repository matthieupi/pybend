/**
 * @file Render resolved native icons inside an isolated custom element. */
import { resolveIcon } from '../utils/icon-resolver.js';

/** Component-local layout and inherited icon token defaults. */
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

/**
 * Escape text for safe insertion into HTML text or attribute values.
 *
 * @param {*} [value=''] Value to encode.
 * @returns {string} HTML-escaped value. */
function escapeHtml(value = '') {
  // 0. Escape characters with HTML markup meaning.
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Escape a value for insertion into a double-quoted HTML attribute.
 *
 * @param {*} [value=''] Value to encode.
 * @returns {string} Attribute-escaped value. */
function escapeAttr(value = '') {
  // 0. Escape markup and the attribute delimiter.
  return escapeHtml(value).replace(/"/g, '&quot;');
}

/** Native custom element that renders one resolved icon. */
class NTTIcon extends HTMLElement {

  /** List the attributes that refresh icon presentation.
   * @returns {string[]} Attributes that trigger a rerender when changed. */
  static get observedAttributes() {
    // 0. Observe the source and accessibility attributes.
    return ['value', 'label', 'title', 'decorative'];
  }

  /** Construct the element with its isolated rendering root. */
  constructor() {
    // 0. Initialize the native element and its isolated rendering root.
    super();
    this.attachShadow({ mode: 'open' });
  }

  /** Render when the element enters the document.
   * @returns {void} */
  connectedCallback() {
    // 0. Resolve the current icon on connection.
    this.render();
  }

  /** Rerender after any observed attribute changes.
   * @returns {void} */
  attributeChangedCallback() {
    // 0. Refresh the icon source and accessibility presentation.
    this.render();
  }

  /** Render the current value and preserve its accessible label behavior.
   * @returns {void} */
  render() {
    // 1. Resolve the input and derive the shared accessible text.
    const resolved = resolveIcon(this.getAttribute('value'));
    const decorative = this.hasAttribute('decorative');
    const label = this.getAttribute('label') ||
      this.getAttribute('title') || resolved?.raw || '';
    const title = this.getAttribute('title') || label;
    // 2. Build markup for the resolved media kind.
    let body = '';
    if (resolved?.kind === 'image') {
      body = `<img class="icon icon--image"
        src="${escapeAttr(resolved.value)}"
        alt="${decorative ? '' : escapeAttr(label)}"
        title="${escapeAttr(title)}" />`;
    } else if (resolved?.kind === 'svg') {
      const strokeWidth = escapeAttr(
        resolved.strokeWidth || '2',
      );
      body = `<svg class="icon icon--svg"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="${escapeAttr(resolved.viewBox || '0 0 24 24')}"
        fill="${escapeAttr(resolved.fill || 'none')}"
        stroke="${escapeAttr(resolved.stroke || 'currentColor')}"
        stroke-width="var(--icon-stroke-width, ${strokeWidth})"
        stroke-linecap="${escapeAttr(resolved.strokeLinecap || 'round')}"
        stroke-linejoin="${escapeAttr(resolved.strokeLinejoin || 'round')}"${
          decorative
            ? ' aria-hidden="true"'
            : ` role="img" aria-label="${escapeAttr(label)}"`
        } title="${escapeAttr(title)}">${resolved.value}</svg>`;
    } else if (resolved?.kind === 'emoji') {
      body = `<span class="icon icon--emoji"${
        decorative
          ? ' aria-hidden="true"'
          : ` role="img" aria-label="${escapeAttr(label)}"`
      } title="${escapeAttr(title)}">${escapeHtml(resolved.value)}</span>`;
    } else if (resolved?.kind === 'text') {
      body = `<span class="icon icon--text"${
        decorative
          ? ' aria-hidden="true"'
          : ` role="img" aria-label="${escapeAttr(label)}"`
      } title="${escapeAttr(title)}">${escapeHtml(resolved.value)}</span>`;
    }
    // 3. Replace the shadow contents with current styles and rendered markup.
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>${body}`;
  }
}

customElements.define('ntx-icon', NTTIcon);

/* Changelog
 * - 2026-10-26: Allow inherited --icon-stroke-width SVG overrides with
 *   registered fallbacks; document and format the native icon renderer. */
