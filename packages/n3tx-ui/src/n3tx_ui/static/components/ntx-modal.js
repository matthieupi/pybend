/**
 * NTTModal — Generic overlay dialog.
 *
 * A framework-level modal that any component can use.
 * Supports both declarative (slot) and programmatic content.
 *
 * Usage:
 *   const modal = NTTModal.open({ title: 'Create Product' });
 *   modal.body.appendChild(someElement);
 *   modal.onSubmit = () => { ... };
 *   modal.onCancel = () => { ... };
 *
 * Closes on: backdrop click, Escape key, X button, cancel, submit.
 * Fires 'modal-close' CustomEvent with detail.reason on close.
 */

// ── Constructable Stylesheet (shared singleton) ──
const _cssURL = new URL('./ntx-modal.css', import.meta.url).href;
let _sheet = null;
let _sheetPromise = null;

function getSheet() {
  if (_sheet) return Promise.resolve(_sheet);
  if (_sheetPromise) return _sheetPromise;
  _sheetPromise = fetch(_cssURL)
    .then(r => r.text())
    .then(css => {
      _sheet = new CSSStyleSheet();
      _sheet.replaceSync(css);
      return _sheet;
    });
  return _sheetPromise;
}


export class NTTModal extends HTMLElement {

  #resolve = null;
  #config = {};

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  /** The modal body container — append content here. */
  get body() {
    return this.shadowRoot.querySelector('.modal-body');
  }

  /** Submit callback — set by opener. */
  onSubmit = null;

  /** Cancel callback — set by opener. */
  onCancel = null;


  /**
   * Open a modal and append it to the document.
   * @param {Object} config
   * @param {string} config.title - Header title
   * @param {boolean} [config.showFooter=true] - Show submit/cancel footer
   * @param {string} [config.submitLabel='Create'] - Submit button text
   * @param {string} [config.cancelLabel='Cancel'] - Cancel button text
   * @returns {NTTModal} The modal instance (with .body to append content)
   */
  static open(config = {}) {
    const modal = document.createElement('ntx-modal');
    modal.#config = {
      title: config.title || 'Modal',
      showFooter: config.showFooter !== false,
      submitLabel: config.submitLabel || 'Create',
      cancelLabel: config.cancelLabel || 'Cancel',
    };
    document.body.appendChild(modal);
    return modal;
  }

  /**
   * Open and return a Promise that resolves on close.
   * @param {Object} config - Same as open()
   * @returns {Promise<{reason: string}>}
   */
  static async prompt(config = {}) {
    const modal = NTTModal.open(config);
    return new Promise(resolve => { modal.#resolve = resolve; });
  }


  connectedCallback() {
    this.#render();
    this.#bind();
    // Trap focus inside modal
    requestAnimationFrame(() => {
      const first = this.shadowRoot.querySelector('.close-btn');
      first?.focus();
    });
  }

  disconnectedCallback() {
    document.removeEventListener('keydown', this._escHandler);
  }


  /**
   * Close the modal with an animated exit.
   * @param {string} reason - 'submit' | 'cancel' | 'backdrop' | 'escape'
   */
  close(reason = 'cancel') {
    this.classList.add('closing');
    this.addEventListener('animationend', () => {
      this.remove();
      this.dispatchEvent(new CustomEvent('modal-close', { detail: { reason } }));
      this.#resolve?.({ reason });
    }, { once: true });
  }


  #render() {
    const { title, showFooter, submitLabel, cancelLabel } = this.#config;

    // Adopt stylesheet
    getSheet().then(sheet => {
      this.shadowRoot.adoptedStyleSheets = [sheet];
    });

    this.shadowRoot.innerHTML = `
      <div class="backdrop"></div>
      <div class="modal-panel" role="dialog" aria-modal="true" aria-label="${title}">
        <div class="modal-header">
          <span class="modal-title">${title}</span>
          <button class="close-btn" title="Close" aria-label="Close"></button>
        </div>
        <div class="modal-body"></div>
        ${showFooter ? `
        <div class="modal-footer">
          <button class="modal-cancel">${cancelLabel}</button>
          <button class="modal-submit">${submitLabel}</button>
        </div>` : ''}
      </div>
    `;
  }

  #bind() {
    // Backdrop click
    this.shadowRoot.querySelector('.backdrop').addEventListener('click', () => this.close('backdrop'));

    // Close button
    this.shadowRoot.querySelector('.close-btn').addEventListener('click', () => this.close('cancel'));

    // Footer buttons
    this.shadowRoot.querySelector('.modal-cancel')?.addEventListener('click', () => {
      this.onCancel?.();
      this.close('cancel');
    });
    this.shadowRoot.querySelector('.modal-submit')?.addEventListener('click', () => {
      this.onSubmit?.();
    });

    // Escape key
    this._escHandler = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        this.close('escape');
      }
    };
    document.addEventListener('keydown', this._escHandler);

    // Prevent scroll on body while modal is open
    document.body.style.overflow = 'hidden';
    this.addEventListener('modal-close', () => {
      document.body.style.overflow = '';
    }, { once: true });
  }
}

customElements.define('ntx-modal', NTTModal);
