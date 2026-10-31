/** Collection lifecycle with optional instance-owned method query pages. */
import {Component} from '../core/Component.js';
import {NTT} from '../core/NTT.js';
import {generateId} from '../core/Utils.js';
import TX from '../core/TX.js';
import Logging from '../utils/Logging.js';
import {permissions} from '../utils/Permissions.js';

/** Share native entities while keeping query membership local to a list. */
export class ListElement extends Component {
  static SIZE_CASCADE = {
    xl: 'md', lg: 'sm', md: 'sm', sm: 'xs', xs: 'xs', row: 'row',
  };

  #selected = new Set();
  #pageSize = 20;
  #offset = 0;
  #query = null;
  #queryInvalid = false;
  #queryAttributeSeen = false;
  #pageIdentity = null;
  #pageModel = null;
  #pageRowCount = 0;
  #attachment = 0;
  #queryDetach;
  #rowUnsubs = [];
  meta = null;
  state = 'loading';
  error = null;
  pending = null;
  requestedOffset = 0;
  /** Successful read completion on the performance clock; zero otherwise. */
  completedRead = 0;
  hasCurrentPage = false;

  /** Initialize an empty collection. */
  constructor() {
    super([]);
  }

  /** Observe declarative query configuration alongside native attributes.
   * @returns {string[]} Native attributes plus strict JSON query input. */
  static get observedAttributes() {
    return [...super.observedAttributes, 'query'];
  }

  /** Return a defensive copy of valid configuration, otherwise null.
   * @returns {Object|null} Query, or null; queryInvalid identifies errors. */
  get query() {
    return this.#query && structuredClone(this.#query);
  }

  /** Distinguish query mode, including invalid input, from legacy READ mode.
   * @returns {boolean} Whether unrestricted legacy reads are disabled. */
  get hasQuery() {
    return this.#query !== null || this.#queryInvalid;
  }

  /** Block automatic adapter configuration after invalid explicit input.
   * @returns {boolean} Only explicit valid query assignment should recover. */
  get queryInvalid() { return this.#queryInvalid; }

  /** Retire old requests and reset pages only when changing query mode.
   * @param {Object|null} query Method name and query arguments; null is legacy.
   * @returns {void}
   * @throws {TypeError} Invalid configuration retires the previous query. */
  set query(query) {
    // 0. Own the query arguments; offset belongs exclusively to loadPage.
    let next = null;
    try {
      if (query !== null) {
        const keys = ['method', 'query', 'filters', 'order_by', 'direction',
          'limit'];
        if (Object.prototype.toString.call(query) !== '[object Object]' ||
            Object.keys(query).some(key => !keys.includes(key))) {
          throw new TypeError('Query must be an object or null.');
        }
        next = structuredClone({
          method: 'SEARCH', query: '', filters: {}, order_by: 'id',
          direction: 'asc', limit: 20, ...query,
        });
        if (typeof next.method !== 'string' || !next.method ||
            typeof next.query !== 'string' ||
            Object.prototype.toString.call(next.filters) !==
              '[object Object]' ||
            typeof next.order_by !== 'string' || !next.order_by ||
            !['asc', 'desc'].includes(next.direction) ||
            !Number.isInteger(next.limit) || next.limit < 1) {
          throw new TypeError('Invalid collection query configuration.');
        }
        JSON.stringify(next);
      }
    } catch {
      this.invalidateQuery('Invalid collection query configuration.');
      throw new TypeError('Invalid collection query configuration.');
    }
    if (!this.#queryInvalid &&
        JSON.stringify(next) === JSON.stringify(this.#query)) return;
    const previous = this.#query;
    this.pending = null;
    this.#query = next;
    this.#queryInvalid = false;
    if (!next) {
      this.#attachment++;
      this.#queryDetach?.();
      this.#queryDetach = undefined;
    }
    if (Boolean(previous) !== Boolean(next)) this.#resetPage();
    // 1. Resolve only connected lists; schema delivery starts the read.
    if (!this.isConnected) return;
    if (this.proto?.schema?.__name__ === this.model) {
      if (next) {
        if (!previous) this.attach(this.model);
        else this.loadPage();
      }
      else {
        this.UPDATE([...this.proto.instances.keys()].map(id =>
          `${this.proto.addr}/${id}`,
        ));
        this.definedCallback();
      }
    } else if (this.model) {
      this.attach(this.model);
    }
  }

  /** Retire invalid configuration without enabling legacy collection reads.
   * @param {string} message Visible configuration failure.
   * @returns {void} */
  invalidateQuery(message) {
    // 0. Retire the old query, attachments and pages before showing the error.
    this.#query = null;
    this.#queryInvalid = true;
    this.#attachment++;
    this.#queryDetach?.();
    this.#queryDetach = undefined;
    this.#resetPage();
    this.failPage(message);
  }

  /** Parse HTML strictly and pass configuration through subclass setters.
   * @param {string|null} value JSON attribute value; absence selects legacy.
   * @returns {void} */
  #bindQueryAttribute(value) {
    // 0. Attribute null is removal; JSON null is not an object configuration.
    this.#queryAttributeSeen = true;
    try {
      const query = value === null ? null : JSON.parse(value);
      if (value !== null &&
          (!query || typeof query !== 'object' || Array.isArray(query))) {
        throw new TypeError('Query attribute must contain a JSON object.');
      }
      this.query = query;
    } catch {
      this.invalidateQuery('Invalid query attribute: expected a valid ' +
        'JSON query object.');
    }
  }

  /** Return the selected model name.
   * @returns {string|undefined} The native model name. */
  get model() { return super.model; }

  /** Retarget query lists without accepting a previous model's response.
   * @param {string} name Native model name.
   * @returns {void} */
  set model(name) {
    const changed = name !== super.model;
    super.model = name;
    if (!changed || !this.hasQuery) return;
    if (!this.#queryInvalid) this.#resetPage();
    if (this.isConnected && name) this.attach(name);
  }

  /** Handle query model attributes without registering global list watchers.
   * @param {string} name Changed attribute name.
   * @param {string|null} oldVal Previous attribute value.
   * @param {string|null} newVal New attribute value.
   * @returns {void} */
  attributeChangedCallback(name, oldVal, newVal) {
    // 0. Bind initial markup before model attachment, in either attr order.
    if (oldVal === newVal) return;
    if (name === 'query') {
      this.#bindQueryAttribute(newVal);
      return;
    }
    if (name === 'model' && !this.#queryAttributeSeen &&
        this.hasAttribute('query')) {
      this.#bindQueryAttribute(this.getAttribute('query'));
    }
    if (name === 'model' && this.hasQuery) {
      this.model = newVal;
      return;
    }
    super.attributeChangedCallback(name, oldVal, newVal);
  }

  /** Ignore schema callbacks left over from a previous query target.
   * @param {Object} proto Native dynamic model class.
   * @returns {void} */
  define(proto) {
    if (this.hasQuery && proto.schema?.__name__ !== this.model) return;
    if (this.hasQuery && this.proto === proto) {
      if (!this.pending && !this.hasCurrentPage && this.isConnected) {
        this.definedCallback();
      }
      return;
    }
    super.define(proto);
  }

  /** Attach query schemas with lifecycle guards for delayed native callbacks.
   * @param {string} addr Native model address.
   * @returns {void} */
  attach(addr) {
    if (!this.hasQuery) {
      super.attach(addr);
      return;
    }
    this.#queryDetach?.();
    const attachment = ++this.#attachment;
    if (!this.isConnected) return;
    this.#queryDetach = NTT.attach(addr, proto => {
      if (!this.isConnected || attachment !== this.#attachment ||
          addr !== this.model) return;
      this.define(proto);
    });
  }

  /** Reestablish schema subscriptions and reload query pages on reconnect.
   * @returns {void} */
  connectedCallback() {
    super.connectedCallback();
    if (!this.hasQuery) return;
    if (this.model) this.attach(this.model);
  }

  /** Invalidate outstanding query reads before native subscription cleanup.
   * @returns {void} */
  disconnectedCallback() {
    this.#attachment++;
    this.#queryDetach?.();
    if (this.#query) this.#resetPage();
    super.disconnectedCallback();
  }

  /** Expose the local selection set.
   * @returns {Set<string>} Selected entity addresses. */
  get selected() { return this.#selected; }

  /** Select an entity address.
   * @param {string} addr Entity address.
   * @returns {void} */
  select(addr) { this.#selected.add(addr); }

  /** Deselect an entity address.
   * @param {string} addr Entity address.
   * @returns {void} */
  deselect(addr) { this.#selected.delete(addr); }

  /** Toggle local selection.
   * @param {string} addr Entity address.
   * @returns {void} */
  toggle(addr) {
    this.#selected.has(addr) ? this.deselect(addr) : this.select(addr);
  }

  /** Clear local selection.
   * @returns {void} */
  clearSelection() { this.#selected.clear(); }

  /** Subscribe to native updates and initiate the appropriate collection read.
   * @returns {void} */
  definedCallback() {
    // 0. Query subscriptions belong to a connected list, not a cached model.
    if (this.#queryInvalid || (this.hasQuery && !this.isConnected)) return;
    this.subscribe(this.proto, 'UPDATE', (data) => this.UPDATE(data));
    if (this.#query) {
      if (this.isConnected) this.loadPage();
      return;
    }
    // 1. Preserve the legacy shared-cache collection read and deduplication.
    if (this.value.length > 0) {
      this.scheduleRender();
      return;
    }
    if (this.proto._listReadPending || this.proto.instances?.size > 0) return;
    this.proto._listReadPending = true;
    this.#offset = 0;
    const depth = this.proto._schema?.ui?.populate?.depth ?? 1;
    this.proto.call('READ', {
      limit: this.#pageSize, offset: 0, ...(depth > 0 ? {depth} : {}),
    }, {inbox: 'UPDATE'});
  }

  /** Snapshot the current caller, including permission-relevant identity data.
   * @returns {string} Stable caller snapshot; not a credential. */
  #identity() {
    const user = permissions.user;
    return JSON.stringify(user && Object.fromEntries(
      Object.keys(user).sort().map(key => [key, user[key]]),
    ));
  }

  /** Invalidate local membership without discarding child controllers.
   * @returns {void} */
  #resetPage() {
    // 0. Retire request and membership state without disposing rendered cards.
    this.#releaseRows();
    this.pending = null;
    this.value = [];
    this.meta = null;
    this.error = null;
    this.state = 'loading';
    this.requestedOffset = 0;
    this.completedRead = 0;
    this.#pageRowCount = 0;
    this.#pageIdentity = null;
    this.#pageModel = null;
    this.hasCurrentPage = false;
    this.clearSelection();
    this.scheduleRender();
  }

  /** Check whether query data, requests and errors belong to this caller/model.
   * @returns {boolean} Whether the current query context remains valid. */
  get hasQueryContext() {
    return !this.#query || (
      this.#pageIdentity === this.#identity() &&
      this.#pageModel === this.model
    );
  }

  /** Identify the caller/model boundary used for retaining child controllers.
   * @returns {string} Noncredential context key for native renderers. */
  get queryContextKey() {
    return JSON.stringify([this.model, this.#identity()]);
  }

  /** Request one query-owned page through the native POST/RESULT transport.
   * @param {number} [offset=0] Nonnegative page offset.
   * @param {Object} [options={}] Page presentation options.
   * @param {boolean} [options.retain=false] Keep valid data during refresh.
   * @param {boolean} [options.append=false] Append to the current query page.
   * @returns {void} */
  loadPage(offset = 0, {retain = false, append = false} = {}) {
    if (!this.#query || !this.isConnected) return;
    // 0. Invalidate prior requests before validating the declared contract.
    const sameContext = this.hasQueryContext;
    this.pending = null;
    this.requestedOffset = offset;
    this.error = null;
    this.completedRead = 0;
    this.state = 'loading';
    if (!sameContext || (!retain && !append)) {
      this.hasCurrentPage = false;
    }
    if (!sameContext) {
      this.value = [];
      this.meta = null;
      this.#pageRowCount = 0;
      this.clearSelection();
    }
    this.#pageIdentity = this.#identity();
    this.#pageModel = this.model;
    this.scheduleRender();
    if (this.proto?.schema?.__name__ !== this.model) return;
    // 1. Resolve a collection POST action from native schema metadata.
    const {method: name, ...data} = structuredClone(this.#query);
    const method = this.schema.methods?.[name];
    let base;
    try {
      base = new URL(this.schema.$id);
    } catch {
      this.failPage('Missing collection query identity.');
      return;
    }
    if (!method || method.requires_instance !== false ||
        !Array.isArray(method.methods) || !method.methods.includes('POST') ||
        !/^\/[a-z][a-z0-9_-]*(\/\w[\w-]*)*$/i.test(method.route || '') ||
        !['http:', 'https:'].includes(base.protocol) ||
        base.username || base.password || base.search || base.hash ||
        base.pathname.endsWith('/') || base.href !== this.schema.$id ||
        !Number.isInteger(data.limit) || data.limit < 1 ||
        !Number.isInteger(offset) || offset < 0) {
      this.failPage('Unsupported collection query contract.');
      return;
    }
    // 2. Bind response acceptance to the exact request, model and caller.
    const target = `${this.schema.$id}${method.route}`;
    const correlation = generateId();
    this.pending = {
      correlation, model: this.model, identity: this.#identity(),
      limit: data.limit, offset, operation: 'read', target,
      schemaId: this.schema.$id,
      append: append && sameContext && this.meta !== null,
    };
    try {
      this.send(new TX({
        name: 'CREATE', source: this.addr, target, data: {...data, offset},
        meta: {inbox: 'RESULT', correlation},
      }));
    } catch {
      this.failPage('Unable to dispatch the collection query.');
    }
  }

  /** Advance by accepted query rows, or request the next legacy cache page.
   * @returns {void} */
  loadMore() {
    if (this.hasQuery) {
      if (this.pending || !this.meta?.has_more) return;
      this.loadPage(this.meta.offset + this.#pageRowCount, {
        retain: true, append: true,
      });
      return;
    }
    this.#offset += this.#pageSize;
    const depth = this.proto._schema?.ui?.populate?.depth ?? 1;
    this.proto.call('READ', {
      limit: this.#pageSize, offset: this.#offset,
      ...(depth > 0 ? {depth} : {}),
    }, {inbox: 'UPDATE'});
  }

  /** Verify transport provenance and current request ownership.
   * @param {Object} tx Response transaction.
   * @param {string} correlation Correlation from response or failed request.
   * @returns {boolean} Whether this response may change local state. */
  #accepts(tx, correlation) {
    const pending = this.pending;
    if (!this.#query || !this.isConnected || !pending) return false;
    // 0. Ignore unrelated replies before invalidating a changed caller/model.
    if (correlation !== pending.correlation || tx?.source !== pending.target ||
        (tx?.target !== this.addr && tx?.target !== `/${this.addr}`)) {
      return false;
    }
    if (pending.identity !== this.#identity() || pending.model !== this.model ||
        pending.schemaId !== this.schema.$id) {
      this.#resetPage();
      this.failPage('Login or model changed. Refresh this collection.');
      return false;
    }
    return true;
  }

  /** Accept a validated page and hydrate native entities without member reads.
   * @param {Object} data Canonical {data, meta} page envelope.
   * @param {Object} tx Native RESULT transaction.
   * @returns {void} */
  RESULT(data, tx) {
    if (!this.#accepts(tx, tx?.meta?.correlation)) return;
    // 0. Validate the complete page before publishing any entity or membership.
    const pending = this.pending;
    const rows = data?.data;
    const meta = data?.meta;
    const base = this.schema.$id;
    const validRows = Array.isArray(rows) && rows.every(row =>
      row && typeof row === 'object' &&
      (typeof row.id === 'number' || typeof row.id === 'string') &&
      (typeof row.id !== 'number' ||
        (Number.isSafeInteger(row.id) && row.id > 0)) &&
      String(row.id) !== '0' &&
      /^[a-z0-9_-]+$/i.test(String(row.id)) &&
      row.$schema === base && row.$id === `${base}/${row.id}`,
    );
    if (!validRows || !meta ||
        !Number.isInteger(meta.total) || meta.total < 0 ||
        meta.limit !== pending.limit || meta.offset !== pending.offset ||
        typeof meta.has_more !== 'boolean' || rows.length > meta.limit ||
        new Set(rows.map(row => row.$id)).size !== rows.length ||
        (rows.length > 0 && meta.offset + rows.length > meta.total) ||
        meta.has_more !== (meta.offset + rows.length < meta.total) ||
        (meta.has_more && rows.length === 0)) {
      this.failPage('Invalid collection query response.');
      return;
    }
    // 1. Publish through NTT, never through the class-wide pagination envelope.
    this.proto.READ(rows);
    if (this.pending !== pending ||
        !this.#accepts(tx, tx?.meta?.correlation)) return;
    const addresses = rows.map(row => row.$id);
    this.value = pending.append
      ? [...new Set([...this.value, ...addresses])] : addresses;
    this.meta = {
      total: meta.total, limit: meta.limit, offset: meta.offset,
      has_more: meta.has_more,
    };
    this.#pageIdentity = pending.identity;
    this.#pageModel = pending.model;
    this.#pageRowCount = rows.length;
    this.pending = null;
    this.error = null;
    this.completedRead = performance.now();
    this.hasCurrentPage = true;
    this.state = this.value.length ? 'ready' : 'empty';
    // 2. Observe accepted entities without adopting class-cache membership.
    this.#releaseRows();
    this.#rowUnsubs = this.value.map(addr => {
      const row = NTT.get(`${this.model}/${addr.split('/').pop()}`);
      return row?.signal?.(() => this.UPDATE(), true);
    }).filter(Boolean);
    this.scheduleRender();
    this.dispatchEvent(new CustomEvent('ntx:page-loaded', {
      detail: {value: [...this.value], meta: {...this.meta}},
      bubbles: true, composed: true,
    }));
  }

  /** Accept only errors belonging to the exact current native read.
   * @param {Object} original Failed native request supplied by the transport.
   * @param {Object} tx Native ERROR transaction.
   * @returns {void} */
  ERROR(original, tx) {
    if (!this.#accepts(tx, original?.meta?.correlation)) return;
    const source = `${this.constructor.addr}/${this.addr}`;
    if ((original.source !== this.addr && original.source !== source) ||
        original.target !== this.pending.target) return;
    const response = tx?.meta?.response;
    const message = response?.detail || response?.message || response?.error;
    this.failPage(typeof message === 'string' ? message : 'Query failed.');
  }

  /** Hide failed query results while retaining their child controllers.
   * @param {string} message User-facing failure text.
   * @returns {void} */
  failPage(message) {
    // 0. Never carry another caller's page counts into a new error context.
    this.#releaseRows();
    if (!this.hasQueryContext) {
      this.value = [];
      this.meta = null;
      this.#pageRowCount = 0;
    }
    this.#pageIdentity = this.#identity();
    this.#pageModel = this.model;
    this.pending = null;
    this.error = message;
    this.state = 'error';
    this.completedRead = 0;
    this.hasCurrentPage = false;
    this.scheduleRender();
  }

  /** Release subscriptions owned by the last accepted query membership.
   * @returns {void} */
  #releaseRows() {
    this.#rowUnsubs.forEach(off => off());
    this.#rowUnsubs = [];
  }

  /** Consume cache notifications without adopting cache membership in queries.
   * @param {string[]} data Native cached entity addresses.
   * @returns {void} */
  UPDATE(data) {
    if (this.hasQuery) {
      if (!this.hasQueryContext && this.hasCurrentPage) {
        this.#resetPage();
        this.failPage('Login or model changed. Refresh this collection.');
      }
      this.scheduleRender();
      return;
    }
    if (Array.isArray(data)) {
      const prev = this.value;
      this.value = data;
      if (!this.update(prev, data)) this.scheduleRender();
    } else {
      Logging.warn('[ListElement] UPDATE expected array, got', typeof data);
    }
  }

  /** Toggle a child selection and optionally forward native navigation.
   * @param {string} data Selected entity address.
   * @param {Object} tx Native SELECT envelope.
   * @returns {void} */
  SELECT(data, tx) {
    this.toggle(data);
    const router = this.getAttribute('router');
    if (router) this.send(new TX({
      name: 'NAVIGATE', source: this.addr, target: router, data,
    }));
  }

  /** Append explicit addresses to a legacy collection.
   * @param {string[]} data Entity addresses.
   * @returns {void} */
  append(data) {
    if (this.hasQuery) return;
    if (Array.isArray(data)) this.value = [...this.value, ...data];
    else Logging.warn('[ListElement] append() expects an array');
  }

  /** Resolve the native item renderer from attributes and runtime schema.
   * @returns {string} Custom element tag. */
  get childTag() {
    return this.getAttribute('item-tag') ||
      this.schema?.ui?.renderer?.item || 'ntx-item';
  }

  /** Resolve the explicit or cascading child display mode.
   * @returns {string} Native display size. */
  get childDisplay() {
    const explicit = this.getAttribute('item-display');
    if (explicit) return Component.normalizeDisplay(explicit) || explicit;
    return ListElement.SIZE_CASCADE[this.displayMode] || 'xs';
  }

  /** Stamp a native child using public capabilities, including borrowed calls.
   * @param {string} addr Canonical entity identity or native address.
   * @returns {HTMLElement} Newly stamped child. */
  createChild(addr) {
    // 0. Set the model hint before the reference to avoid a direct URL fetch.
    const template = this.querySelector('template[item-template]');
    const el = template
      ? template.content.firstElementChild.cloneNode(true)
      : document.createElement(this.childTag);
    if (this.query) el.setAttribute('data-model', this.model);
    if (template) el.setAttribute('ref', addr);
    else {
      el.ref = addr;
      el.setAttribute('display', this.childDisplay);
    }
    el.setAttribute('select-target', this.addr);
    return el;
  }

  /** Let concrete renderers reconcile addresses without recreating children.
   * @param {string[]} prev Previous addresses.
   * @param {string[]} next Next addresses.
   * @returns {boolean} False requests the concrete render method. */
  update(prev, next) { return false; }
}

/* Changelog
 * - 2026-10-28: Preserve pages across query changes while retiring requests;
 *   reset page state when switching between query and legacy modes.
 * - 2026-10-26: Add native query pages and guarded reply lifecycle.
 *   Preserve same-model schema subscriptions and observe accepted row updates.
 *   Preserve borrowed factories, short-page offsets and successful timestamps.
 *   Bind page counts and errors to the active caller/model context.
 *   Expose query objects and fail-closed strict JSON attribute binding. */
