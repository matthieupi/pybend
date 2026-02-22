/**
 * Component — Unified base class for all NTT web components.
 *
 * Merges the Actor bridge (addr, hash, Matrix registration) with
 * schema-aware entity lifecycle (model, ref, proto, value).
 *
 * Subclasses:
 *   NTTElement  — single entity (components/NTTElement.js)
 *   ListElement — entity collection (components/ListElement.js)
 */
import {generateId, isUrl} from "./Utils.js";
import Logging from "../utils/Logging.js";
import {matrix} from "./Matrix.js";
import Actor from "./Actor.js";
import TX from "./TX.js";


export class Component extends HTMLElement {

  // ── Size constants ──
  static SIZES = ['xs', 'sm', 'md', 'lg', 'xl'];
  static ALIASES = {
    pill: 'xs',
    'list-item': 'sm',
    card: 'md',
    detail: 'lg',
    page: 'xl',
  };

  /**
   * Normalize a display value to an abstract size (xs–xl).
   * Accepts both abstract ('sm') and semantic ('pill') names.
   * Returns null for 'auto' or unrecognized values.
   */
  static normalizeDisplay(value) {
    if (!value || value === 'auto') return null;
    return Component.ALIASES[value] || (Component.SIZES.includes(value) ? value : null);
  }

  // ── Actor identity ──
  #addr;
  #hash;

  // ── Entity state ──
  #href;
  #model;
  #proto = {};
  #data;
  #defaultValue;
  #detach = undefined;
  #unsubscribe = undefined;

  // ── Adaptive display ──
  #displayMode = 'md';
  #resizeObserver = null;

  // ── Stylesheet ──
  $styles = null;

  /**
   * @param {Object|Array} defaultValue — subclass passes {} (entity) or [] (collection)
   */
  constructor(defaultValue = {}) {
    super();

    // Shadow DOM
    this.attachShadow({mode: 'open'});

    // Actor identity
    this.#hash = this.getAttribute('hash') || generateId();
    this.#addr = this.getAttribute('addr') || `${this.constructor.name}-${this.#hash}`;
    matrix.register(this);
    this.constructor.register(this);

    // Entity state
    this.#model = this.getAttribute('model') || undefined;
    this.#href = this.getAttribute('href') || undefined;
    this.#defaultValue = defaultValue;
    this.#data = defaultValue;

    // Bind callbacks that are passed as references
    this.define = this.define.bind(this);

    // Stylesheet
    if (this.styles) {
      const $link = document.createElement('link');
      $link.setAttribute('rel', 'stylesheet');
      $link.setAttribute('href', this.styles);
      this.shadowRoot.appendChild($link);
      this.$styles = $link;
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Observed Attributes                  **/
  /** ─────────────────────────────────────────── **/

  static get observedAttributes() {
    return ['model', 'addr', 'hash', 'ref', 'display'];
  }

  attributeChangedCallback(name, oldVal, newVal) {
    if (oldVal === newVal) return;
    Logging.debug(`[Component] ${this.constructor.name}.${name}: ${oldVal} => ${newVal}`);

    if (name === 'display') {
      const normalized = Component.normalizeDisplay(newVal);
      if (normalized && normalized !== this.#displayMode) {
        const old = this.#displayMode;
        this.#displayMode = normalized;
        this.displayModeChanged(old, normalized);
      }
      return;
    } else if (name === 'model') {
      this[name] = newVal;
      this.send(new TX({
        name: 'ATTACH',
        source: this.addr,
        target: 'NTT',
        data: newVal
      }));
      return;
    } else if (name === 'ref') {
      this.ref = newVal;
      return;
    }
    this[name] = newVal;
  }


  /** ─────────────────────────────────────────── **/
  /**         Actor Interface                      **/
  /** ─────────────────────────────────────────── **/

  get addr() { return this.#addr; }
  set addr(addr) {
    if (!this.#addr)
      this.#addr = addr;
    else if (this.#addr === addr)
      return;
    else
      throw new Error(`[${this.#addr}] Address already set, cannot change to ${addr}.`);
  }


  /** ─────────────────────────────────────────── **/
  /**         Schema / Proto Resolution            **/
  /** ─────────────────────────────────────────── **/

  get model() { return this.#model; }
  set model(name) { this.#model = name; }

  get proto() { return this.#proto; }

  get schema() {
    if (!this._schema)
      this._schema = this.#proto?.schema || {};
    return this._schema;
  }
  set schema(schema) { this._schema = schema; }

  /**
   * Called by the NTT system when the DynamicClass prototype is ready.
   * Sets proto, infers model name, triggers definedCallback().
   */
  define(ptt) {
    Logging.debug(`[Component] ${this.model} — define()`, ptt);
    if (!ptt.schema || ptt.schema.__name__ === this.#proto?.schema?.__name__) return;
    if (!this.#model) { this.#model = ptt.schema.__name__; }
    this.#proto = ptt;
    this.definedCallback();
  }

  /**
   * Hook called after define() sets the prototype.
   * Override in subclasses (e.g. ListElement subscribes + triggers READ here).
   */
  definedCallback() {}


  /** ─────────────────────────────────────────── **/
  /**         Ref / Href Resolution                **/
  /** ─────────────────────────────────────────── **/

  get ref() { return this.#href; }
  set ref(href) {
    this.#href = href;
    if (isUrl(href)) {
      // Direct URL — fetch the resource
      this.send(new TX({
        name: 'READ',
        source: this.addr,
        target: href,
      }));
    } else {
      // NTT address — ATTACH flow
      this.send(new TX({
        name: 'ATTACH',
        source: this.addr,
        target: 'NTT',
        data: href,
      }));
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Value Management                     **/
  /** ─────────────────────────────────────────── **/

  get defaultValue() { return this.#defaultValue; }

  get value() { return this.#data || this.#defaultValue; }
  set value(data) {
    if (typeof data !== typeof this.#defaultValue) {
      Logging.dev(`[Component] Type mismatch: expected ${typeof this.#defaultValue}, got ${typeof data} in ${this.constructor.name}.`);
      return;
    }
    if (data !== this.#data) {
      this.#data = data;
    }
    // No auto-render here — subclasses decide when to render.
  }


  /** ─────────────────────────────────────────── **/
  /**         Stylesheet Hook                      **/
  /** ─────────────────────────────────────────── **/

  /**
   * Override in subclass to provide a CSS URL.
   * @returns {string|null}
   */
  get styles() { return null; }


  /** ─────────────────────────────────────────── **/
  /**         Adaptive Display Mode                **/
  /** ─────────────────────────────────────────── **/

  /**
   * Breakpoint thresholds (px) for display mode resolution.
   * Override in subclass to customize. Keys are size names (xs–xl),
   * values are minimum widths. Evaluated largest-first.
   * @returns {Object}
   */
  get displayBreakpoints() {
    return { xl: 800, lg: 600, md: 400, sm: 200, xs: 0 };
  }

  /**
   * Current display mode (xs, sm, md, lg, xl).
   * Driven by ResizeObserver unless forced via the `display` attribute.
   * @returns {string}
   */
  get displayMode() { return this.#displayMode; }

  /**
   * The `display` attribute value (or 'auto' if unset).
   * Set to a size name or semantic alias to force a display mode.
   */
  get display() {
    return this.getAttribute('display') || 'auto';
  }
  set display(value) {
    if (!value || value === 'auto') {
      this.removeAttribute('display');
    } else {
      this.setAttribute('display', value);
    }
  }

  /**
   * Hook called when displayMode changes due to resize.
   * Default: re-renders if schema is available.
   * Override for custom behavior (e.g. CSS-only swap).
   * @param {string} oldMode
   * @param {string} newMode
   */
  displayModeChanged(oldMode, newMode) {
    if (this._schema || this.#proto?.schema) {
      this.render();
    }
  }

  /**
   * Start the ResizeObserver that tracks displayMode.
   * Called automatically from connectedCallback.
   */
  #startResizeObserver() {
    if (this.#resizeObserver) return;
    this.#resizeObserver = new ResizeObserver(([entry]) => {
      // Skip if display mode is forced via attribute
      if (Component.normalizeDisplay(this.getAttribute('display'))) return;

      const width = entry.contentRect.width;
      if (width === 0) return; // not laid out yet
      const bp = this.displayBreakpoints;
      const sorted = Object.entries(bp).sort(([, a], [, b]) => b - a);
      const newMode = sorted.find(([, min]) => width >= min)?.[0] || 'xs';
      if (newMode !== this.#displayMode) {
        const oldMode = this.#displayMode;
        this.#displayMode = newMode;
        this.displayModeChanged(oldMode, newMode);
      }
    });
    this.#resizeObserver.observe(this);
  }

  #stopResizeObserver() {
    this.#resizeObserver?.disconnect();
    this.#resizeObserver = null;
  }


  /** ─────────────────────────────────────────── **/
  /**         Subscription Helpers                 **/
  /** ─────────────────────────────────────────── **/

  /**
   * Subscribe to an observable property on a TT/DynamicClass.
   * Cleans up previous subscription automatically.
   */
  subscribe(tt, attribute, callback) {
    this.#unsubscribe?.();
    this.#unsubscribe = tt.observe(attribute, callback);
  }

  /**
   * Attach to an NTT address via NTT.attach().
   * Cleans up previous attachment automatically.
   */
  attach(addr) {
    // Lazy import to avoid circular dependency
    import('./NTT.js').then(({NTT}) => {
      this.#detach?.();
      this.#detach = NTT.attach(addr, this.define);
    });
  }


  /** ─────────────────────────────────────────── **/
  /**         Web Component Lifecycle              **/
  /** ─────────────────────────────────────────── **/

  connectedCallback() {
    // Apply forced display mode if set before connect
    const forced = Component.normalizeDisplay(this.getAttribute('display'));
    if (forced && forced !== this.#displayMode) {
      const old = this.#displayMode;
      this.#displayMode = forced;
      this.displayModeChanged(old, forced);
    }
    this.#startResizeObserver();
  }

  disconnectedCallback() {
    this.#stopResizeObserver();
    this.#detach?.();
    this.#unsubscribe?.();
  }

  /**
   * Abstract — subclasses must implement.
   */
  render() {
    throw new Error(`render() must be implemented in ${this.constructor.name}.`);
  }
}

Actor.subclass(Component);
matrix.register(Component);
