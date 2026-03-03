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

// ── Constructable Stylesheet Cache ──
// Fetch + parse each CSS file once; share the CSSStyleSheet across all shadow roots.
const _sheetCache   = new Map();  // URL → CSSStyleSheet (resolved)
const _sheetPending = new Map();  // URL → Promise<CSSStyleSheet> (in-flight)


export class Component extends HTMLElement {

  // ── Size constants ──
  static SIZES = ['xs', 'sm', 'md', 'lg', 'xl', 'row'];
  static ALIASES = {
    pill: 'xs',
    'list-item': 'sm',
    card: 'md',
    detail: 'lg',
    page: 'xl',
    row: 'row',
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
  #renderPending = false;

  // ── Stylesheet readiness ──
  #styleReady = null;  // null (no styles / cache hit) or Promise (in-flight fetch)

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

    // Stylesheet — constructable stylesheet, parsed once and shared.
    // Cache hit: adopt synchronously (no FOUC).
    // Cache miss: store the adoption promise; scheduleRender() defers until ready.
    if (this.styles) {
      const url = this.styles;
      const cached = _sheetCache.get(url);
      if (cached) {
        this.shadowRoot.adoptedStyleSheets = [cached];
      } else {
        this.#styleReady = this.#adoptStylesheet(url);
      }
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
      // attach() triggers define() → definedCallback() (sets #proto, schema)
      this.attach(newVal);
      // ATTACH TX registers this component as a _watcher on the DynamicClass
      // so it receives UPDATE notifications after READ/CREATE/DELETE
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
    const model = this.getAttribute('data-model');
    if (isUrl(href) && model) {
      // URL ref with known model — route through ATTACH for caching + dedup
      const id = href.split('/').pop();
      this.send(new TX({
        name: 'ATTACH',
        source: this.addr,
        target: 'NTT',
        data: `${model}/${id}`,
        meta: {href: href},
      }));
    } else if (isUrl(href)) {
      // Direct URL, no model hint — fall back to direct fetch
      this.send(new TX({
        name: 'READ',
        source: this.addr,
        target: href,
      }));
    } else {
      // NTT address — ATTACH flow (existing)
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

  /**
   * Fetch a CSS file, create a CSSStyleSheet, cache it, and adopt it.
   * Deduplicates in-flight fetches so concurrent constructors share one request.
   */
  async #adoptStylesheet(url) {
    let pending = _sheetPending.get(url);
    if (!pending) {
      pending = fetch(url)
        .then(r => { if (!r.ok) throw new Error(`CSS ${r.status}`); return r.text(); })
        .then(css => {
          const sheet = new CSSStyleSheet();
          sheet.replaceSync(css);
          _sheetCache.set(url, sheet);
          _sheetPending.delete(url);
          return sheet;
        })
        .catch(err => {
          Logging.warn(`[Component] Failed to load stylesheet: ${url}`, err.message);
          _sheetPending.delete(url);
          return null;
        });
      _sheetPending.set(url, pending);
    }
    const sheet = await pending;
    if (sheet) this.shadowRoot.adoptedStyleSheets = [sheet];
  }


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
   * Default: schedules a render if schema is available.
   * Override for custom behavior (e.g. CSS-only swap).
   * @param {string} oldMode
   * @param {string} newMode
   */
  displayModeChanged(oldMode, newMode) {
    if (this._schema || this.#proto?.schema) {
      this.scheduleRender();
    }
  }

  /**
   * Coalesce render calls — multiple triggers in the same frame
   * produce a single render(). Prevents double-render when DESCRIBE
   * and ResizeObserver fire in quick succession.
   *
   * If a stylesheet is still being fetched (#styleReady), defers the
   * render until the sheet is adopted — prevents unstyled content flash.
   */
  scheduleRender() {
    if (this.#renderPending) return;
    this.#renderPending = true;
    const doRender = () => {
      this.#renderPending = false;
      this.render();
    };
    if (this.#styleReady) {
      this.#styleReady.then(() => requestAnimationFrame(doRender));
    } else {
      requestAnimationFrame(doRender);
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
