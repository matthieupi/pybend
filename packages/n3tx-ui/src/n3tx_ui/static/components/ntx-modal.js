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
  #closing = false;
  #closed = false;
  #closeReason = 'cancel';
  #closeFrame = null;
  #focusFrame = null;
  #overflow = null;
  #previousFocus = null;

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
    const existing = [...document.querySelectorAll('ntx-modal')].find(modal =>
      modal instanceof NTTModal && modal !== this && !modal.#closed);
    this.#overflow = existing?.#overflow || ['overflow-x', 'overflow-y'].map(property => [
      property, document.body.style.getPropertyValue(property), document.body.style.getPropertyPriority(property),
    ]);
    this.#previousFocus = document.activeElement;
    while (this.#previousFocus?.shadowRoot?.activeElement) {
      this.#previousFocus = this.#previousFocus.shadowRoot.activeElement;
    }
    this.#render();
    this.#bind();
    // Set initial focus; cancel this work if the modal closes before the frame.
    this.#focusFrame = requestAnimationFrame(() => {
      const first = this.shadowRoot.querySelector('.close-btn');
      first?.focus();
    });
  }

  disconnectedCallback() {
    this.#finishClose();
  }


  /**
   * Close the modal with an animated exit.
   * @param {string} reason - 'submit' | 'cancel' | 'backdrop' | 'escape'
   */
  close(reason = 'cancel') {
    if (this.#closing || this.#closed) return;
    this.#closing = true;
    this.#closeReason = reason;
    cancelAnimationFrame(this.#focusFrame);
    this.classList.add('closing');
    // Only actual host animations own the exit, never descendant events. Missing,
    // cancelled, paused or unbounded motion must not hold lifecycle cleanup open.
    const animations = this.getAnimations().filter(animation => animation.effect?.target === this);
    const finishWhenStopped = () => {
      if (this.#closed) return;
      if (animations.some(animation => animation.playState === 'running' &&
          animation.playbackRate !== 0 && Number.isFinite(animation.effect.getComputedTiming().endTime))) {
        this.#closeFrame = requestAnimationFrame(finishWhenStopped);
      } else {
        this.#finishClose();
      }
    };
    finishWhenStopped();
    // Completion/cancellation can settle even when a background tab stops frames;
    // the frame check above also handles pauses, which do not settle finished.
    Promise.allSettled(animations.map(animation => animation.finished)).then(() => this.#finishClose());
  }

  #finishClose() {
    if (this.#closed) return;
    this.#closed = true;
    cancelAnimationFrame(this.#closeFrame);
    cancelAnimationFrame(this.#focusFrame);
    document.removeEventListener('keydown', this._escHandler);
    const remaining = [...document.querySelectorAll('ntx-modal')].filter(modal =>
      modal instanceof NTTModal && modal !== this && !modal.#closed);
    // A later modal may have been opened from this one's shadow tree. Preserve
    // its return-focus chain even when the lower modal is closed first.
    for (const modal of remaining) {
      let target = modal.#previousFocus;
      while (target && target !== this) target = target.parentNode || target.host;
      if (target === this) modal.#previousFocus = this.#previousFocus;
    }
    const restoreFocus = document.activeElement === this || document.activeElement === document.body;
    this.remove();
    if (!remaining.length && this.#overflow) {
      for (const [property, value, priority] of this.#overflow) document.body.style.setProperty(property, value, priority);
    }
    const top = remaining.at(-1);
    let focusTarget = this.#previousFocus;
    if (top) {
      // Rapid opens can capture the same page opener before either focus frame.
      let owner = focusTarget;
      while (owner && owner !== top) owner = owner.parentNode || owner.host;
      if (owner !== top) focusTarget = top.shadowRoot.querySelector('.close-btn');
    }
    if ((restoreFocus || (top && !top.contains(document.activeElement))) && focusTarget?.isConnected) {
      focusTarget.focus();
    }
    const reason = this.#closeReason;
    this.dispatchEvent(new CustomEvent('modal-close', { detail: { reason } }));
    this.#resolve?.({ reason });
    this.#resolve = null;
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
      if (e.key === 'Escape' && [...document.querySelectorAll('ntx-modal')]
          .filter(modal => modal instanceof NTTModal && !modal.#closed).at(-1) === this) {
        e.stopPropagation();
        this.close('escape');
      }
    };
    document.addEventListener('keydown', this._escHandler);

    // Prevent scroll on body while modal is open
    document.body.style.overflow = 'hidden';
  }
}

customElements.define('ntx-modal', NTTModal);
