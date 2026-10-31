/**
 * Component — Unified base class for all NTT web components.
 *
 * Merges the Actor bridge (addr, hash, Matrix registration) with
 * schema-aware entity lifecycle (model, ref, proto, value).
 *
 * Subclasses:
 *   NTTElement  — single entity (components/NTTElement.js)
 *   ListElement — entity collection (components/ListElement.js) */
import {generateId, isUrl} from "./Utils.js";
import Logging from "../utils/Logging.js";
import {matrix} from "./Matrix.js";
import Actor from "./Actor.js";
import TX from "./TX.js";

// ── Constructable Stylesheet Cache ──
// Fetch each CSS file once; share its stylesheet across shadow roots.
const _sheetCache = new Map();  // URL → CSSStyleSheet (resolved)
const _sheetPending = new Map();  // URL → Promise<CSSStyleSheet> (in-flight)


/** Bridge custom elements, actors, entity state and responsive styles. */
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
   * @param {string|null} value Display size or alias.
   * @returns {string|null} Normalized size, or automatic/unknown. */
  static normalizeDisplay(value) {
    if (!value || value === 'auto') return null;
    return Component.ALIASES[value] ||
      (Component.SIZES.includes(value) ? value : null);
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
  #styleReady = null;  // null (no styles/cache hit) or in-flight Promise

  /**
   * Initialize actor identity, entity state and shared shadow styles.
   * @param {Object|Array} [defaultValue={}] Entity or collection default. */
  constructor(defaultValue = {}) {
    super();
    // 0. Create the native open shadow root and stable actor identity.
    this.attachShadow({mode: 'open'});

    this.#hash = this.getAttribute('hash') || generateId();
    this.#addr = this.getAttribute('addr') ||
      `${this.constructor.name}-${this.#hash}`;
    matrix.register(this);
    this.constructor.register(this);
    // 1. Initialize entity state and externally passed callbacks.
    this.#model = this.getAttribute('model') || undefined;
    this.#href = this.getAttribute('href') || undefined;
    this.#defaultValue = defaultValue;
    this.#data = defaultValue;

    this.define = this.define.bind(this);
    // 2. Adopt constructable stylesheets, parsed once and shared.
    // Cache hit: adopt synchronously (no FOUC).
    // Cache miss: scheduleRender() waits for the adoption promise.
    const styleUrls = this.#styleUrls(this.styles);
    if (styleUrls.length) {
      const cachedSheets = styleUrls.map(url => _sheetCache.get(url))
        .filter(Boolean);
      if (cachedSheets.length) {
        this.shadowRoot.adoptedStyleSheets = cachedSheets;
      }

      if (cachedSheets.length !== styleUrls.length) {
        this.#styleReady = this.#adoptStylesheets(styleUrls);
      }
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Observed Attributes                  **/
  /** ─────────────────────────────────────────── **/

  /** Attributes routed into identity, entity and display state.
   * @returns {string[]} Observed attribute names. */
  static get observedAttributes() {
    return ['model', 'addr', 'hash', 'ref', 'display'];
  }

  /** Apply attribute changes through native state and attachment mechanisms.
   * @param {string} name Changed attribute.
   * @param {string|null} oldVal Previous value.
   * @param {string|null} newVal Current value.
   * @returns {void} */
  attributeChangedCallback(name, oldVal, newVal) {
    if (oldVal === newVal) return;
    // 0. Resolve display overrides without changing entity attachments.
    if (name === 'display') {
      const normalized = Component.normalizeDisplay(newVal);
      if (normalized && normalized !== this.#displayMode) {
        const old = this.#displayMode;
        this.#displayMode = normalized;
        this.displayModeChanged(old, normalized);
      }
      return;
    } else if (name === 'model') {
      // 1. Resolve the model and register its update watcher.
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
      // 2. Delegate entity references to their native attachment path.
      this.ref = newVal;
      return;
    }
    this[name] = newVal;
  }


  /** ─────────────────────────────────────────── **/
  /**         Actor Interface                      **/
  /** ─────────────────────────────────────────── **/

  /** Read the stable actor address.
   * @returns {string} Component actor address. */
  get addr() { return this.#addr; }

  /** Set an address only before identity has been established.
   * @param {string} addr Requested actor address.
   * @throws {Error} If the established address would change. */
  set addr(addr) {
    if (!this.#addr)
      this.#addr = addr;
    else if (this.#addr === addr)
      return;
    else
      throw new Error(
        `[${this.#addr}] Address already set, cannot change to ${addr}.`,
      );
  }


  /** ─────────────────────────────────────────── **/
  /**         Schema / Proto Resolution            **/
  /** ─────────────────────────────────────────── **/

  /** Read the attached model name.
   * @returns {string|undefined} Model name. */
  get model() { return this.#model; }

  /** Store a model name without initiating attachment.
   * @param {string} name Model name. */
  set model(name) { this.#model = name; }

  /** Read the resolved native model prototype.
   * @returns {Object} Model prototype. */
  get proto() { return this.#proto; }

  /** Read the explicit or prototype-derived schema.
   * @returns {Object} Runtime model schema. */
  get schema() {
    if (!this._schema)
      this._schema = this.#proto?.schema || {};
    return this._schema;
  }

  /** Store an explicit schema override.
   * @param {Object|null} schema Runtime schema or cache invalidation. */
  set schema(schema) { this._schema = schema; }

  /**
   * Called by the NTT system when the DynamicClass prototype is ready.
   * Sets proto, infers model name, triggers definedCallback().
   * @param {Object} ptt Resolved model prototype with schema.
   * @returns {void} */
  define(ptt) {
    // 0. Accept a newly resolved model and invalidate its schema cache.
    if (!ptt.schema ||
        ptt.schema.__name__ === this.#proto?.schema?.__name__) return;
    if (!this.#model) { this.#model = ptt.schema.__name__; }
    this.#proto = ptt;
    this._schema = null;  // Clear stale cache so getter re-reads from proto
    this.definedCallback();
  }

  /**
   * Hook called after define() sets the prototype.
   * Override in subclasses (e.g. ListElement subscribes + triggers READ here).
   * @returns {void} */
  definedCallback() {}


  /** ─────────────────────────────────────────── **/
  /**         Ref / Href Resolution                **/
  /** ─────────────────────────────────────────── **/

  /** Read the attached entity reference.
   * @returns {string|undefined} Native address or URL. */
  get ref() { return this.#href; }

  /** Attach to an entity using its model hint, URL or native address.
   * @param {string} href Native entity address or canonical URL. */
  set ref(href) {
    // 0. Preserve the reference and resolve the native attachment route.
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

  /** Read the initial entity or collection default.
   * @returns {Object|Array} Default data value. */
  get defaultValue() { return this.#defaultValue; }

  /** Read current data with its initial default fallback.
   * @returns {Object|Array} Current data. */
  get value() { return this.#data || this.#defaultValue; }

  /** Store compatible data without automatically rendering.
   * @param {Object|Array} data New component data. */
  set value(data) {
    // 0. Keep the constructor's value category and update by identity.
    if (typeof data !== typeof this.#defaultValue) {
      Logging.dev(`[Component] Type mismatch: expected ` +
        `${typeof this.#defaultValue}, got ${typeof data} ` +
        `in ${this.constructor.name}.`);
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
   * @returns {string|string[]|null} Stylesheet URLs, or no styles. */
  get styles() { return null; }

  /** Normalize the stylesheet hook into nonempty URLs.
   * @param {string|string[]|null} styles Stylesheet hook value.
   * @returns {string[]} Stylesheet URLs. */
  #styleUrls(styles) {
    if (!styles) return [];
    const urls = Array.isArray(styles) ? styles : [styles];
    return urls.filter(Boolean);
  }

  /**
   * Fetch a CSS file, create a CSSStyleSheet, cache it, and adopt it.
   * Deduplicates in-flight fetches across concurrent constructors.
   * @param {string} url Stylesheet URL.
   * @returns {Promise<CSSStyleSheet|null>} Shared sheet or failed load. */
  async #loadStylesheet(url) {
    // 0. Reuse resolved or in-flight stylesheets.
    const cached = _sheetCache.get(url);
    if (cached) return cached;

    let pending = _sheetPending.get(url);
    if (!pending) {
      // 1. Fetch and cache a sheet; failures permit a later retry.
      pending = fetch(url)
        .then(r => {
          if (!r.ok) throw new Error(`CSS ${r.status}`);
          return r.text();
        })
        .then(css => {
          const sheet = new CSSStyleSheet();
          sheet.replaceSync(css);
          _sheetCache.set(url, sheet);
          _sheetPending.delete(url);
          return sheet;
        })
        .catch(err => {
          Logging.warn(
            `[Component] Failed to load stylesheet: ${url}`, err.message,
          );
          _sheetPending.delete(url);
          return null;
        });
      _sheetPending.set(url, pending);
    }
    return pending;
  }

  /** Adopt all successfully loaded stylesheets in declared order.
   * @param {string[]} urls Stylesheet URLs.
   * @returns {Promise<void>} Completion after stylesheet adoption. */
  async #adoptStylesheets(urls) {
    const loaded = await Promise.all(
      urls.map(url => this.#loadStylesheet(url)),
    );
    const sheets = loaded.filter(Boolean);
    if (sheets.length) this.shadowRoot.adoptedStyleSheets = sheets;
  }


  /** ─────────────────────────────────────────── **/
  /**         Adaptive Display Mode                **/
  /** ─────────────────────────────────────────── **/

  /**
   * Breakpoint thresholds (px) for display mode resolution.
   * Override in subclass to customize. Keys are size names (xs–xl),
   * values are minimum widths. Evaluated largest-first.
   * @returns {Object<string, number>} Size thresholds in pixels. */
  get displayBreakpoints() {
    return { xl: 800, lg: 600, md: 400, sm: 200, xs: 0 };
  }

  /**
   * Current display mode (xs, sm, md, lg, xl).
   * Driven by ResizeObserver unless forced via the `display` attribute.
   * @returns {string} Current normalized size. */
  get displayMode() { return this.#displayMode; }

  /**
   * The `display` attribute value (or 'auto' if unset).
   * Set to a size name or semantic alias to force a display mode.
   * @returns {string} Explicit display attribute or auto. */
  get display() {
    return this.getAttribute('display') || 'auto';
  }

  /** Apply or clear a display override.
   * @param {string|null} value Display size, alias or automatic sizing. */
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
   * @param {string} oldMode Previous normalized size.
   * @param {string} newMode Current normalized size.
   * @returns {void} */
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
   * @returns {void} */
  scheduleRender() {
    // 0. Coalesce pending renders and wait for initial style readiness.
    if (this.#renderPending) return;
    this.#renderPending = true;

    /** Complete a scheduled render.
     * @returns {void} */
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
   * @returns {void} */
  #startResizeObserver() {
    // 0. Observe layout only when no explicit display size is selected.
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

  /** Stop observing layout after an actual disconnection.
   * @returns {void} */
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
   * @param {Object} tt Observable entity or model class.
   * @param {string} attribute Event or property name.
   * @param {Function} callback Observer callback.
   * @returns {void} */
  subscribe(tt, attribute, callback) {
    this.#unsubscribe?.();
    this.#unsubscribe = tt.observe(attribute, callback);
  }

  /**
   * Attach to an NTT address via NTT.attach().
   * Cleans up previous attachment automatically.
   * @param {string} addr Native model or entity address.
   * @returns {void} */
  attach(addr) {
    // 0. Resolve lazily to avoid the runtime's circular dependency.
    import('./NTT.js').then(({NTT}) => {
      this.#detach?.();
      this.#detach = NTT.attach(addr, this.define);
    });
  }


  /** ─────────────────────────────────────────── **/
  /**         Web Component Lifecycle              **/
  /** ─────────────────────────────────────────── **/

  /** Initialize display observation and structural UI on connection.
   * @returns {void} */
  connectedCallback() {
    // 0. Apply forced display mode if set before connection.
    const forced = Component.normalizeDisplay(this.getAttribute('display'));
    if (forced && forced !== this.#displayMode) {
      const old = this.#displayMode;
      this.#displayMode = forced;
      this.displayModeChanged(old, forced);
    }
    // 1. Observe responsive layout and mount the structural UI.
    this.#startResizeObserver();
    this.prerender();
  }

  /** Preserve subscriptions and DOM during a browser state-preserving move.
   * Every nested custom element needs its own move-safe lifecycle; this
   * callback does not suppress descendant reactions or real disconnects.
   * @returns {void} */
  connectedMoveCallback() {}

  /** Release native observers and attachments after actual disconnection.
   * @returns {void} */
  disconnectedCallback() {
    this.#stopResizeObserver();
    this.#detach?.();
    this.#unsubscribe?.();
  }

  /**
   * Pre-schema structural UI. Called once from connectedCallback().
   * Override in subclasses to render DOM skeleton before schema loads.
   * @returns {void} */
  prerender() {}

  /**
   * Abstract — subclasses must implement.
   * @returns {void}
   * @throws {Error} When a subclass has not supplied its renderer. */
  render() {
    throw new Error(
      `render() must be implemented in ${this.constructor.name}.`,
    );
  }
}

Actor.subclass(Component);
matrix.register(Component);

/* Changelog
 * - 2026-10-26: Preserve native lifecycle on state-preserving DOM moves.
 *   Document existing contracts and normalize source line lengths. */
