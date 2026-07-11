import assert from "../utils/Assert.js";
import {config} from "../config.js";
import {isEmpty, isTypeCompatible, isUrl, Utils} from './Utils.js';
//import {registry, registrar, getRegistrar} from "./registrar.js";
import TX from "./TX.js";
// NetworkAdapter imported by Matrix — 'remote' flag is a TX meta key, not a binding

import Logging from "../utils/Logging.js";
import Actor from "./Actor.js";


import {matrix} from "./Matrix.js";
import Observable from "./Observable.js";

const E = config.E;

/**
 * TT (Transfer Type) - Base class for transfer types
 */
class TT extends Actor{

    #href;
    #watchers = new Set();
    #observers = new Map();

    constructor(addr, href) {
        super(addr);
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        //assert(this, href && typeof isUrl(href), `[TT] ${addr} - HREF must be a valid URL, got: ${href}`);

        if (!href)
            href = `${config.API_URL}/${addr}`;
        this.#href = href;
    }

    // Protected getters for subclasses
    get href() { return this.#href; }
    set href(href) {
        assert(this, isUrl(href), `[TT] ${this.addr} - HREF must be a valid URL, got: ${href}`);
        const oldHref = this.#href;
        this.#href = href
    }

    watch(addr, immediate = true) {
        this.#watchers.add(addr);
        if (this.value && immediate){
            this.send(new TX({
                name: E.update,
                source: this.addr,
                target: addr,
                data: this.value
            }))
        }
    }


    notify(value) {
        let data = []
        if (!value){
            data = [...this.value].map(child => child.addr);
        }
        else {
            data = Array.isArray(value) ? value : [value];
        }
        this.#watchers.forEach( (addr) => {
            this.send(
                new TX({
                    name: E.update,
                    source: this.addr,
                    target: addr,
                    data: data,
                })
            )
        });
    }

    ATTACH(data, tx) {
        Logging.dev("[TT] ATTACHING")
        this.watch(tx.source)
    }



    /**
     * Call a distant method on the PTT instance
     * @param method {string} - Method name to call
     * @param data {Object} - Data (args and kwargs) to send with the method call
     * @param [meta] {Object} - Additional metadata for the call
     */
    call(method, data = {}, meta = {}) {
      this.send(
        new TX({
            name: method,
            source: this.addr,
            target: this.href,
            data: data,
            meta: meta,
            timestamp: Date.now()
        })
      )
    }

    _error_(event) {
        Logging.error(`[TT] Error from ${event.source}->${event.target}`, event.data);
    }
}


/**
 * NTT (Named Transfer Type) - Core entity class + universal type registry.
 *
 * Static level:
 *   - Global registry of DynamicClass types (#prototypes)
 *   - Universal ATTACH router for both type-level and instance-level
 *   - SCHEMA handler for bootstrap completion
 *
 * Instance level:
 *   - Per-entity data with functional state management
 *   - ATTACH/UPDATE/DESCRIBE handlers for entity lifecycle
 */
export class NTT extends TT {

    // ── Type Registry (replaces PTT) ──
    static #prototypes = new Map();  // addr → DynamicClass | null
    static #waiting = new Map();     // addr → TX[] | {_attachCallback}[]

    #proto;
    #data;
    #detach;
    #unsubscribe;
    #meta = {};

    /**
     * Create a new NTT instance
     * @param {string} model - Entity model name
     * @param {string} hash - Entity ID
     * @param {Object} [data={}] - Initial data/state
     * @param {Object} [meta={}] - Additional metadata
     */
    constructor(model, hash, data = {}, meta = {}) {
        const id = hash || Utils.generateId();
        const href = `${config.API_URL}/${model}/${id}`;
        const addr = `${id}`;
        super(addr, href);
    }

    // ──────────────────────────────────────────────
    // STATIC: SSR Pre-loading
    // ──────────────────────────────────────────────

    /**
     * Check for an inline <script data-ntx-schema="ModelName"> in the document.
     * If found, parse and feed to NTT.SCHEMA() directly, skipping network fetch.
     * The script tag is removed after consumption (one-shot).
     * @param {string} model - Model name (e.g. "Product")
     * @returns {boolean} true if pre-loaded schema was found and consumed
     */
    static #consumePreloadedSchema(model) {
        const el = document.querySelector(`script[data-ntx-schema="${model}"]`);
        if (!el) return false;
        try {
            const data = JSON.parse(el.textContent);
            el.remove();
            NTT.SCHEMA(data);
            return true;
        } catch (e) {
            Logging.error(`[NTT] Failed to parse pre-loaded schema for ${model}`, e);
            return false;
        }
    }

    /**
     * Check for an inline <script data-ntx-data="tablename"> in the document.
     * If found, parse and return the data array. The script tag is removed.
     * @param {string} tablename - Table/collection name (e.g. "products")
     * @returns {Array|null} Pre-loaded data or null
     */
    static #consumePreloadedData(tablename) {
        const el = document.querySelector(`script[data-ntx-data="${tablename}"]`);
        if (!el) return null;
        try {
            const data = JSON.parse(el.textContent);
            el.remove();
            return data;
        } catch (e) {
            Logging.error(`[NTT] Failed to parse pre-loaded data for ${tablename}`, e);
            return null;
        }
    }

    // ──────────────────────────────────────────────
    // STATIC: Registry
    // ──────────────────────────────────────────────

    /**
     * Check if a DynamicClass is registered for the given address.
     * @param {string} addr - Model name (e.g., "Product")
     * @returns {boolean}
     */
    static has(addr) {
        return NTT.#prototypes.has(addr);
    }

    /**
     * Dual lookup:
     *   NTT.get("Product")   → DynamicClass
     *   NTT.get("Product/1") → NTT instance
     * @param {string} addr
     * @returns {DynamicClass|NTT|undefined}
     */
    static get(addr) {
        if (!addr) return undefined;
        addr = String(addr);
        if (addr.includes('/')) {
            const [model, id] = addr.split('/');
            const DC = NTT.#prototypes.get(model);
            return DC ? DC.children.get(id) : undefined;
        }
        return NTT.#prototypes.get(addr) || undefined;
    }

    /**
     * Imperative attach with callback — fires when DynamicClass is ready.
     * If DC exists, fires immediately. If pending, queues. If unknown, bootstraps.
     * @param {string} addr - Model name
     * @param {Function} callback - Called with DynamicClass when ready
     * @returns {Function|undefined} Unsubscribe function
     */
    static attach(addr, callback) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        assert(this, callback && typeof callback === 'function', `Callback must be a function.`);

        const DC = NTT.#prototypes.get(addr);

        if (DC) {
            // DynamicClass exists → signal immediately
            return DC.signal(callback);
        } else if (DC === null) {
            // Schema in flight → queue callback
            NTT.#waiting.get(addr).push({_attachCallback: callback});
        } else {
            // Never seen → queue callback, then try pre-loaded before network
            NTT.#prototypes.set(addr, null);
            NTT.#waiting.set(addr, [{_attachCallback: callback}]);
            if (!NTT.#consumePreloadedSchema(addr)) {
                matrix.dispatch(new TX({
                    name: 'SCHEMA',
                    source: 'NTT',
                    target: `${config.API_URL}/${addr}`,
                    meta: {remote: true}
                }));
            }
        }
    }

    // ──────────────────────────────────────────────
    // STATIC: Message Handlers
    // ──────────────────────────────────────────────

    /**
     * Universal ATTACH router — single entry point for all entity ATTACHes.
     * Handles both type-level ("Product") and instance-level ("Product/1").
     *
     * Three states per model:
     *   undefined → never seen → bootstrap (set null, fetch schema, queue TX)
     *   null      → schema in flight → queue TX
     *   DynClass  → ready → forward TX to DynamicClass
     */
    static ATTACH(data, tx) {
        tx = tx instanceof TX ? tx : new TX(tx);
        const addr = typeof data === 'string' ? data : tx.data;
        const model = addr.split('/')[0];

        const DC = NTT.#prototypes.get(model);

        if (DC) {
            // DynamicClass exists → call ATTACH directly (bypasses Actor routing
            // which would throw for instance-level targets when instance doesn't exist)
            DC.ATTACH(addr, tx);
        } else if (DC === null) {
            // Schema in flight → queue
            NTT.#waiting.get(model).push(tx);
        } else {
            // Never seen → queue TX, then try pre-loaded before network
            NTT.#prototypes.set(model, null);
            NTT.#waiting.set(model, [tx]);
            if (!NTT.#consumePreloadedSchema(model)) {
                matrix.dispatch(new TX({
                    name: 'SCHEMA',
                    source: 'NTT',
                    target: `${config.API_URL}/${model}`,
                    meta: {remote: true}
                }));
            }
        }
    }

    /**
     * Bootstrap completion — receives schema from backend, creates DynamicClass,
     * stores it in registry, replays queued messages, triggers initial READ.
     */
    static SCHEMA(data, tx) {
        const addr = data.__name__;
        const href = modelHref(data, addr);

        // Handle $defs (nested schemas) first — skip the main model itself.
        // Use inline $defs even when a separate fetch is in-flight (null in prototypes)
        // to avoid waiting for the network when the data is already here.
        if (data.$defs && typeof data.$defs === 'object') {
            for (const [key, value] of Object.entries(data.$defs)) {
                if (key === addr) continue; // Main model handled below
                // !NTT.#prototypes.get(key) is true for both undefined (never seen)
                // and null (in-flight) — either way, create from inline $def
                if (value.type === 'object' && value.properties && !NTT.#prototypes.get(key)) {
                    const defHref = modelHref(value, key);
                    const DC = prototype(key, value, defHref);
                    NTT.#prototypes.set(key, DC);
                    NTT.#replayWaiting(key, DC);
                }
            }
        }

        // Create DynamicClass for the main model — skip if already created
        // (e.g. from another schema's $defs) to avoid orphaning existing references
        let DC = NTT.#prototypes.get(addr);
        if (!DC) {
            DC = prototype(addr, data, href);
            NTT.#prototypes.set(addr, DC);
        }

        // Replay queued messages + callbacks
        NTT.#replayWaiting(addr, DC);

        // Check for pre-loaded data (SSR) — if present, feed directly to DC.READ.
        // No network READ is fired here — consumer components (ListElement, etc.)
        // trigger their own paginated READs in definedCallback().
        const tablename = data.__tablename__ || addr.toLowerCase() + 's';
        const preloadedData = NTT.#consumePreloadedData(tablename);
        if (preloadedData) {
            DC.READ(preloadedData);
        }
    }

    /**
     * Replay queued TXs and attach callbacks for a model.
     * @param {string} addr - Model name
     * @param {class} DC - The DynamicClass
     */
    static #replayWaiting(addr, DC) {
        const queue = NTT.#waiting.get(addr);
        if (!queue) return;
        for (const entry of queue) {
            if (entry._attachCallback) {
                DC.signal(entry._attachCallback);
            } else {
                const repr = entry instanceof TX ? entry.repr() : {...entry};
                repr.target = typeof repr.data === 'string' ? repr.data : addr;
                if (repr.name === 'ATTACH') {
                    // Route ATTACH directly to DC.ATTACH (avoids Actor routing
                    // throw when instance doesn't exist yet)
                    DC.ATTACH(repr.data || repr.target, new TX(repr));
                } else {
                    DC.inbox(repr);
                }
            }
        }
        NTT.#waiting.delete(addr);
    }

    // ──────────────────────────────────────────────
    // INSTANCE: Handlers
    // ──────────────────────────────────────────────

    static UPDATE(data) {
        for (const [addr, value] of Object.entries(data)) {
            const instance = this.get(value.id);
            if (instance) {
                instance.update(value);
            } else {
                new this(value)
            }

        }
    }

    ATTACH(data, event) {
        const tx = event instanceof TX ? event : new TX(event);
        this.watch(tx.source, false);
        this.send(new TX({
            name: 'DESCRIBE',
            source: this.addr,
            target: tx.source,
            data: {proto: this.constructor._schema, data: this.value}
        }))
    }

    get value() {
        return this.#data
    }

    set value(val) {
        if (typeof val !== 'object') {
            throw new TypeError('data must be an object');
        }
        this.#data = val;
        this.signal();
    }

    get proto() {
        return this.#proto;
    }

    get schema() {
        return this.constructor._schema;
    }

    define(proto) {
        this.#proto = proto;
        if (proto && proto.href) {
            this.href = `${proto.href}/${this.addr}`;
        }
    }

    describe(proto, data) {
        if (!proto || typeof proto !== 'object') return
        this.define(proto)
        this.update(data || this.#data || {});
    }

    static READ(data) {
        assert(this, data && typeof data === 'object', `Data must be a non-empty object.`);
        // Update the NTT instance with the received data
        this.update(data);
    }

    UPDATE(data, event) {
        this.update(data);
        if (!event.source?.startsWith('http')) {
            this.call('UPDATE', this.value);
        }
    }

    update(data) {
        this.value = {...this.#data, ...data};
        if (data.hasOwnProperty('name') && data.name === "error") {
            Logging.warn(`[NTT] Error received from ${this.addr}`, data.message || data.error || "Unknown error")
        }
    }

    ERROR(event) {
        Logging.error(`[NTT] ${event.name} from ${event.source}`, event.data);
    }

    _read_(data) {
        assert(this, data && typeof data === 'object', `Data must be a non-empty object.`);
        // Update the NTT instance with the received data
        this.update(data);
    }

    /**
     * Serialize NTT instance to JSON
     * @returns {Object} JSON representation
     */
    toJSON() {
        return {
            addr: this.addr,
            href: this.href,
            data: this.#data,
            meta: {
                ...structuredClone(this.#meta),
                // Exclude non-serializable items
                subscribers: undefined,
                propertyObservers: undefined,
                conflictResolver: undefined
            }
        };
    }

    pull() {
        assert(this, isUrl(this.href), `[NTT] ${this.addr} HREF must be a valid HTTP URL, got: ${this.href}`);
        const popDepth = this.constructor._schema?.ui?.populate?.depth ?? 1;
        this.call('READ', popDepth > 0 ? {depth: popDepth} : {}, {remote: true});
        return this;
    }

}


// ──────────────────────────────────────────────
// Populate normalization helpers
// ──────────────────────────────────────────────

/**
 * Resolve the child model name from a schema property definition.
 * Handles $ref in items, anyOf with $ref, etc.
 */
function resolveModelName(def) {
    if (!def || typeof def !== 'object') return null;
    if (def.$ref) return def.$ref.split('/').pop();
    if (def.anyOf) {
        const ref = def.anyOf.find(a => a.$ref);
        return ref ? ref.$ref.split('/').pop() : null;
    }
    return resolveModelName(def.items);
}

function isExplicitRef(def) {
    return def?.type === '$ref' && typeof def.$ref === 'string';
}

function isExplicitRefList(def) {
    return def?.type === 'array' && isExplicitRef(def.items);
}

function relationshipValueId(value) {
    if (value && typeof value === 'object' && value.id !== undefined) return String(value.id);
    if (value && typeof value === 'object' && value.$id) value = value.$id;
    if (typeof value !== 'string') return null;
    return value.replace(/\/$/, '').split('/').pop() || null;
}

/**
 * Resolve the API base URL from a schema $id. The backend schema URL is the
 * authority when available because it carries the deployed API origin/prefix.
 */
function schemaApiBase(schemaId) {
    if (!schemaId) return config.API_URL;
    try {
        const url = new URL(schemaId);
        url.pathname = url.pathname.replace(/\/[^/]*$/, '');
        const base = url.toString().replace(/\/$/, '');
        return base || config.API_URL;
    } catch {
        return config.API_URL;
    }
}

/**
 * Resolve the class-name model base href from schema metadata.
 *
 * Collection transport appends the explicit '_' marker at collection call sites;
 * member transport appends the id directly. Keeping the shared static href at
 * the model base avoids accidentally building member URLs like /Model/_/id.
 */
function modelHref(schema, addr) {
    const base = schemaApiBase(schema?.$id);
    const model = schema?.__name__ || addr;
    return `${base}/${model}`;
}

/**
 * Register an entity in a DynamicClass's instance cache.
 * Updates existing instances or creates new ones.
 */
function registerInstance(DC, data) {
    return upsertInstance(DC, data);
}

/**
 * Create or update an entity in a DynamicClass's instance cache.
 * DynamicClass instances are actor children, so their canonical keys are
 * string address segments even when backend ids are numeric.
 */
function upsertInstance(DC, data) {
    if (!DC || !data || data.id === undefined) return undefined;

    normalizePopulated(data, DC._schema);

    const id = String(data.id);
    const existing = DC.instances.get(id);
    if (existing) {
        existing.update(data);
        return existing;
    }

    // Constructor registers instance via Actor._register (string key)
    return new DC(data);
}

/**
 * Normalize populated (eager-loaded) data in an entity response.
 * Registers hydrated children while preserving owned relationship objects.
 * Explicit Ref fields retain pointer semantics.
 *
 * Handles two cases:
 * 1. Owned T/list[T]: hydrated object(s) remain in parent state.
 * 2. Ref[T]/list[Ref[T]]: populated objects normalize to pointer strings.
 */
function normalizePopulated(entity, schema) {
    if (!entity || !schema?.properties) return;
    for (const [key, def] of Object.entries(schema.properties)) {
        const val = entity[key];
        if (!val) continue;

        const childModelName = resolveModelName(def);
        const ChildDC = childModelName ? NTT.get(childModelName) : null;

        // Relationship collection wrapper: preserve objects for owned lists,
        // but retain href semantics for explicit pointer lists.
        if (def.type === 'array' && !Array.isArray(val) && Array.isArray(val?.data) && val?.meta) {
            const items = val.data;
            for (const item of items) {
                if (item && typeof item === 'object' && item.$id) {
                    if (ChildDC) {
                        normalizePopulated(item, ChildDC._schema);
                        registerInstance(ChildDC, item);
                    }
                }
            }
            entity[key] = isExplicitRefList(def)
                ? items.map(item => item && typeof item === 'object' ? item.$id : item).filter(Boolean)
                : items;
            continue;
        }

        // Plain hydrated relationship values (without pagination wrapper).
        if (Array.isArray(val) && childModelName) {
            for (const item of val) {
                if (item && typeof item === 'object' && item.$id && ChildDC) {
                    normalizePopulated(item, ChildDC._schema);
                    registerInstance(ChildDC, item);
                }
            }
            if (isExplicitRefList(def)) {
                entity[key] = val.map(item => item && typeof item === 'object' ? item.$id : item).filter(Boolean);
            }
            continue;
        }

        if (childModelName && typeof val === 'object' && val.$id) {
            if (ChildDC) {
                normalizePopulated(val, ChildDC._schema);
                registerInstance(ChildDC, val);
            }
            if (isExplicitRef(def)) entity[key] = val.$id;
        }
    }
}

/**
 * Generate a DynamicClass — a runtime NTT subclass for a specific model type.
 * The class IS the type: holds schema, instances, CRUD, Observable.
 * Born complete — never exists in a half-initialized state.
 *
 * @param {string} addr - Model name (e.g., "Product")
 * @param {Object} schema - JSON schema from backend
 * @param {string} href - CRUD endpoint URL (e.g., "http://.../products")
 * @returns {class} DynamicClass extends NTT
 */
function prototype(addr, schema, href) {
    const fields = Object.keys(schema.properties || {});
    const methods = Object.keys(schema.methods || {});
    const className = addr;


    // 1. Create a subclass of NTT with dynamic properties
    const DynamicClass = class extends NTT {

      static instances = new Map();
      static _schema = schema;

      // Bridge: Actor.subclass() creates _children/children if not defined.
      // DynamicClass stores entities in `instances`, so alias children → instances
      // so that Actor routing (DynamicClass.children.get(id)) finds them.
      static get _children() { return this.instances; }
      static get children()  { return this.instances; }

      _data;


      constructor(data) {
        super(className, data.id);
        this.value = data;
        // Use the entity's $id (context-specific URL) when available.
        // For nested entities (e.g. comments inside products), $id carries
        // the correct CRUD path (/Product/1/Comment/3). DynamicClass.href is
        // the class-name model base (/Comment), with '_' appended only where
        // collection transport is required.
        this.href = data.$id || `${href}/${this.id}`;
        Logging.dev(`[NTT] Created instance of ${className}`, this.addr)
      }

      get value() {
          if (!this._data) {
              return undefined
          }
          return {
              ...this._data,
              "$schema": this.constructor._schema?.$id || `${config.API_URL}/${this.constructor.addr}`,
              "$id": this.href,
          };
      }
      set value(val) {
            if (typeof val !== 'object') {
                throw new TypeError('data must be an object');
            }
            this._data = val;
            this.signal();
      }
    };

    // 1.1 Set the class name and href
    Object.defineProperty(DynamicClass, 'name', {value: className});
    Object.defineProperty(DynamicClass, 'href', {value: href, writable: true});
    Object.defineProperty(DynamicClass, 'schema', {
        configurable: true,
        get() { return DynamicClass._schema; }
    });

    // 1.2 Static type-level state
    DynamicClass._watchers = new Set();
    DynamicClass._pendingAttaches = [];
    DynamicClass.__signals = new Set();
    DynamicClass.__observers = new Map();
    DynamicClass._listReadPending = false; // Dedup flag: prevents multiple list READs in same cycle


    // 2. Add schema properties to the subclass prototype
    for (const field of fields) {
      const definition = schema.properties[field];
      const isReadonly = definition.readOnly === true;
      const label = definition.title || field;
      const hidden = definition.extra && definition.extra.hidden;

      Object.defineProperty(DynamicClass.prototype, field, {
        enumerable: !hidden,
        configurable: true,
        // 2.1 Variable access
        get() {
          return this.value?.[field]
        },
        // 2.2 Variable assignment with type checking and validation
        set(value) {
          if (isReadonly) {
            throw new Error(`Trying to set read-only '${field}' with data ${JSON.stringify(value)}.`);
          }
          const expectedType = definition.type;
          if (expectedType && !isTypeCompatible(value, expectedType)) {
            throw new TypeError(`Invalid type for '${field}': expected ${expectedType}`);
          }
          // Cache the old value for observers
          const oldValue = this._data?.[field];
          // Assign the value to the field
          this._data[field] = value;
          // If this field has property observers, notify them
          this.notify(field, value, oldValue);
        },
      });

      // 2.3 Add fields labels for UI representation
      if (!DynamicClass.labels) DynamicClass.labels = {};
      DynamicClass.labels[field] = label;
    }


    // 3. Add schema functions to the subclass prototype
    for (const method of methods) {
      const definition = schema.methods[method];
      // Add the method to the prototype
      DynamicClass.prototype[method] = function(...args) {
          // Validate the arguments against the method definition
        if (definition.parameters) {
            for (const [param, paramDef] of Object.entries(definition.parameters)) {
                // Check if the parameter is a required field
                if (paramDef.required && !args[param]) {
                    throw new TypeError(`Missing required parameter '${param}' in method '${method}'.`);
                }
                // Check if the type is a reference to another schema
                if (paramDef.$ref) {
                    // If the parameter is a reference, ensure it matches the schema
                    const refSchemaName = schema.$defs[paramDef.$ref.replace('#/$defs/', '')];
                    // Validate the argument against the referenced schema
                    if (args[param] && args[param]?.addr !== refSchemaName) {
                        throw new TypeError(`Parameter '${param}' in method '${method}' must match schema '${refSchemaName}'. ` +
                            `Got: ${JSON.stringify(args[param])}`);
                    }
                } else if (!isTypeCompatible(args[param], paramDef.type)) {
                    throw new TypeError(`Invalid type for parameter '${param}' in method '${method}': expected ${paramDef.type}`);
                }
            }
        }
        // Call the remote method with the provided arguments
        this.call(method, args, {});
      };
    }


    // ── 4. Static type-level methods ──
    // DynamicClass acts as a type actor: holds schema, instances, CRUD.
    // These are added manually because Observable.apply only targets prototype.

    /**
     * Static call — sends TX from the DynamicClass (type-level).
     * Does NOT set source so Actor._send assigns it to className.
     */
    DynamicClass.call = function(method, data = {}, meta = {}) {
        DynamicClass.send(new TX({
            name: method,
            target: `${DynamicClass.href}/_`,
            data: data,
            meta: meta,
            timestamp: Date.now()
        }));
    };

    /**
     * Static signal — Observable pattern at class level.
     * @param {Function} [callback] - If provided, registers listener. If omitted, fires all.
     * @param {boolean} [wait=false] - If true, don't fire callback immediately.
     * @returns {Function|undefined} Unsubscribe function when callback is provided.
     */
    DynamicClass.signal = function(callback, wait = false) {
        if (callback) {
            if (!wait) callback(DynamicClass);
            DynamicClass.__signals.add(callback);
            return () => DynamicClass.__signals.delete(callback);
        } else {
            DynamicClass.__signals.forEach(cb => cb(DynamicClass));
        }
    };

    /**
     * Static observe — Observable pattern at class level.
     * Used by subscribe(this.proto, 'UPDATE', ...) in components.
     */
    DynamicClass.observe = function(property, callback) {
        if (!DynamicClass.__observers.has(property)) {
            DynamicClass.__observers.set(property, new Set());
        }
        DynamicClass.__observers.get(property).add(callback);
        return () => {
            const set = DynamicClass.__observers.get(property);
            if (!set) return;
            set.delete(callback);
            if (set.size === 0) DynamicClass.__observers.delete(property);
        };
    };

    /**
     * Static ATTACH — handles type-level and instance-level ATTACHes
     * forwarded from NTT.ATTACH.
     */
    DynamicClass.ATTACH = function(data, tx) {
        tx = tx instanceof TX ? tx : new TX(tx);
        const addr = typeof data === 'string' ? data : tx.data;

        if (addr && addr.includes('/')) {
            // Instance-level ATTACH
            const id = addr.split('/')[1];
            const instance = DynamicClass.children.get(id);
            if (instance) {
                // Instance exists — forward directly
                const reprTx = tx instanceof TX ? tx.repr() : {...tx};
                reprTx.target = `/${id}`;
                instance.inbox(reprTx);
            } else {
                // Instance not yet created — queue for replay after READ
                const queuedTx = tx instanceof TX ? tx.repr() : {...tx};
                queuedTx.target = `/${id}`;
                DynamicClass._pendingAttaches.push({id, tx: queuedTx});
                // Trigger individual fetch if not already in-flight
                if (!DynamicClass._fetchingIds) DynamicClass._fetchingIds = new Set();
                if (!DynamicClass._fetchingIds.has(id)) {
                    DynamicClass._fetchingIds.add(id);
                    const fetchUrl = `${DynamicClass.href}/${id}`;
                    const popDepth = DynamicClass._schema?.ui?.populate?.depth ?? 1;
                    DynamicClass.send(new TX({
                        name: 'READ',
                        target: fetchUrl,
                        data: popDepth > 0 ? {depth: popDepth} : {},
                    }));
                }
            }
        } else {
            // Type-level → add watcher
            DynamicClass._watchers.add(tx.source);
            // If instances are already loaded, send immediate UPDATE
            if (DynamicClass.instances.size > 0) {
                const addrs = [...DynamicClass.instances.keys()].map(
                    id => `${DynamicClass.addr}/${id}`
                );
                DynamicClass.send(new TX({
                    name: E.update,
                    source: DynamicClass.addr,
                    target: tx.source,
                    data: addrs
                }));
            }
        }
    };

    /**
     * Static READ — creates/updates NTT instances from backend records.
     * Replays pending instance ATTACHes, then notifies all watchers.
     */
    DynamicClass.READ = function(data) {
        // Clear dedup flag — the in-flight READ has completed
        DynamicClass._listReadPending = false;

        // Detect paginated response: {data: [...], meta: {...}}
        if (data && !Array.isArray(data) && Array.isArray(data.data) && data.meta) {
            DynamicClass._paginationMeta = data.meta;
            data = data.data;
        }

        // Normalize: single entity response → array
        if (data && typeof data === 'object' && !Array.isArray(data) && data.id !== undefined) {
            data = [data];
        }

        if (Array.isArray(data)) {
            for (const value of data) {
                upsertInstance(DynamicClass, value);
            }
        } else if (typeof data === 'object') {
            for (const value of Object.values(data)) {
                upsertInstance(DynamicClass, value);
            }
        }

        // Clean up in-flight tracking for any instances just created
        if (DynamicClass._fetchingIds) {
            for (const id of DynamicClass.instances.keys()) {
                DynamicClass._fetchingIds.delete(String(id));
            }
        }

        // Replay pending instance ATTACHes (only for instances that now exist)
        if (DynamicClass._pendingAttaches.length > 0) {
            const pending = DynamicClass._pendingAttaches.splice(0);
            const remaining = [];
            for (const {id, tx} of pending) {
                const instance = DynamicClass.children.get(id);
                if (instance) {
                    instance.inbox(tx);
                } else {
                    remaining.push({id, tx});
                }
            }
            if (remaining.length > 0) {
                DynamicClass._pendingAttaches.push(...remaining);
            }
        }

        // Notify watchers with instance addresses
        const childrenAddrs = [...DynamicClass.instances.keys()].map(
            id => id.toString().startsWith(`${DynamicClass.addr}/`) ? id : `${DynamicClass.addr}/${id}`
        );
        Logging.dev("[NTT] CHILDREN ADDR", childrenAddrs);
        DynamicClass._watchers.forEach(addr => {
            DynamicClass.send(new TX({
                name: E.update,
                source: DynamicClass.addr,
                target: addr,
                data: childrenAddrs
            }));
        });

        // Notify class-level observers (e.g. sidebar count)
        if (DynamicClass.__observers.has('UPDATE')) {
            DynamicClass.__observers.get('UPDATE').forEach(cb => cb(childrenAddrs));
        }
    };

    /**
     * Static UPDATE — delegates to READ (handles meta.inbox='UPDATE' responses).
     */
    DynamicClass.UPDATE = function(data, tx) {
        DynamicClass.READ(data, tx);
    };

    /**
     * Static CREATE — adds new instance to registry and notifies watchers.
     * Called after a successful backend CREATE (POST) response.
     */
    DynamicClass.CREATE = function(data, tx) {
        upsertInstance(DynamicClass, data);
        // Re-notify watchers with updated instance list
        const childrenAddrs = [...DynamicClass.instances.keys()].map(
            id => `${DynamicClass.addr}/${id}`
        );
        DynamicClass._watchers.forEach(addr => {
            DynamicClass.send(new TX({
                name: E.update,
                source: DynamicClass.addr,
                target: addr,
                data: childrenAddrs
            }));
        });

        // Notify class-level observers (ListElement subscribes here)
        if (DynamicClass.__observers.has('UPDATE')) {
            DynamicClass.__observers.get('UPDATE').forEach(cb => cb(childrenAddrs));
        }
    };

    /**
     * Static DELETE — removes instance from registry and notifies watchers.
     * Called after a successful backend DELETE response.
     * The httpCallback swaps source/target, so tx.source is the entity URL.
     */
    DynamicClass.DELETE = function(data, tx) {
        // Keep as string — Map keys are strings (from Actor constructor registration)
        const id = tx.source?.split('/').pop();
        if (id) {
            DynamicClass.instances.delete(id);
        }
        // Re-notify watchers with updated instance list
        const childrenAddrs = [...DynamicClass.instances.keys()].map(
            id => `${DynamicClass.addr}/${id}`
        );
        DynamicClass._watchers.forEach(addr => {
            DynamicClass.send(new TX({
                name: E.update,
                source: DynamicClass.addr,
                target: addr,
                data: childrenAddrs
            }));
        });

        // Notify class-level observers (ListElement subscribes here)
        if (DynamicClass.__observers.has('UPDATE')) {
            DynamicClass.__observers.get('UPDATE').forEach(cb => cb(childrenAddrs));
        }
    };

    /**
     * Static ERROR — notifies observers when an error occurs (e.g. failed CREATE).
     * Components subscribe via proto.observe('ERROR', cb) to handle error recovery.
     */
    DynamicClass.ERROR = function(data, tx) {
        Logging.error(`[${DynamicClass.addr}] ERROR from ${tx?.source || 'unknown'}`, data);
        if (DynamicClass.__observers.has('ERROR')) {
            DynamicClass.__observers.get('ERROR').forEach(cb => cb({ data, tx }));
        }
    };

    /**
     * Instance READ — handles pull() responses for individual entities.
     * Normalizes relationship wrappers and pre-registers hydrated child
     * instances, same as the class-level READ.
     */
    DynamicClass.prototype.READ = function(data) {
        normalizePopulated(data, DynamicClass._schema);
        this.update(data);
    };

    /**
     * Instance _response_ — handles method call responses (e.g. like, comment).
     *
     * Three cases:
     * 1. Action response with _field hint (like/favorite toggle):
     *    Appends or removes child ref from the named array field.
     * 2. Entity data response (has id, no action):
     *    Updates this instance directly — no network pull needed.
     * 3. Otherwise: pull authoritative state after simple/ambiguous success.
     */
    DynamicClass.prototype._response_ = function(data, tx) {
        if (!data || typeof data !== 'object') {
            return this.pull();
        }

        // Case 1: Action response with field hint — update array in-place
        if (data.action && data._field && data.id !== undefined) {
            const field = data._field;
            const arr = Array.isArray(this._data[field]) ? [...this._data[field]] : [];
            const props = DynamicClass._schema?.properties?.[field];
            const childModel = props ? resolveModelName(props) : null;
            const ChildDC = childModel ? NTT.get(childModel) : null;

            if (data.action === 'liked' || data.action === 'favorited') {
                if (!ChildDC) return this.pull();
                const childHref = `${ChildDC.href}/${data.id}`;
                const child = {
                    ...data,
                    $schema: ChildDC._schema?.$id || ChildDC.href,
                    $id: data.$id || childHref,
                };
                registerInstance(ChildDC, child);
                const value = isExplicitRefList(props) ? child.$id : child;
                if (!arr.some(item => relationshipValueId(item) === String(data.id))) {
                    arr.push(value);
                }
            } else if (data.action === 'unliked' || data.action === 'unfavorited') {
                const idStr = String(data.id);
                const idx = arr.findIndex(item => relationshipValueId(item) === idStr);
                if (idx >= 0) arr.splice(idx, 1);
            }

            this.value = { ...this._data, [field]: arr };
            return;
        }

        // Case 2: Same-entity data response — update directly.
        // Custom methods can return a different entity type (e.g. Product.comment
        // returns a Comment). In that case, pull the original instance so the
        // parent collection refreshes instead of corrupting this instance with
        // another model's fields.
        if (data.id !== undefined) {
            const responseSchema = data.$schema || data.schema;
            const currentSchema = DynamicClass._schema?.$id || DynamicClass._schema?.__name__;
            if (responseSchema && currentSchema && responseSchema !== currentSchema) {
                return this.pull();
            }
            normalizePopulated(data, DynamicClass._schema);
            this.update(data);
            return;
        }

        return this.pull();
    };


    // 5. Apply Actor and Mixins
    Actor.subclass(DynamicClass, Observable);

    return DynamicClass;
}


window.NTT = NTT;

Actor.subclass(TT);

Actor.subclass(NTT, Observable);
