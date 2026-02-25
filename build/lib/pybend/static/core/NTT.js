import assert from "../utils/Assert.js";
import {config} from "../config.js";
import {isEmpty, isTypeCompatible, isUrl, Utils} from './Utils.js';
//import {registry, registrar, getRegistrar} from "./registrar.js";
import TX from "./TX.js";
import {remote} from "./transport/NetworkAdapter.js";
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
    notify(property, newValue, oldValue) {
        assert(this, property && typeof property === 'string', `Property must be a non-empty string.`);
        //assert(this, this.#observers.has(property), `No observers registered for property '${property}'.`);
        // Notify all observers for the specified property
        if (this.#observers.has(property)) {
            this.#observers.get(property).forEach(callback => callback(newValue, oldValue, property, this));
        }
    }

    signal(callback = undefined, wait = false) {
        assert(this, !callback || typeof callback === 'function', `Callback must be a function if given.`);
        if (callback) {
            if (!wait) {
                // When wait is false, immediately call the callback
                callback(this);
            }
            // Add the callback to the signals set
            this.#signals.add(callback);
            // Return an unsubscribe function
            return () => { this.#signals.delete(callback); };
        }
        else {
            // When called with no callback, signal to all listeners
            this.#signals.forEach((callback) => { callback(this); });
        }

    }
     **/

    /**
     * Send an event via the registrar callback
     * @param event {TX}
     */

    /**
    send(event) {
        assert(this, event && typeof event === 'object', `Data must be a non-empty object.`);
        // Retrieve href callback and dispatch the event to it
        Logging.event(`Sending event '${event.name}' from ${event.source} to ${event.target}\n`, event.str())
        matrix.dispatch(event)
    }
     **/

    /**
     * Inbox method to handle incoming events
     * @param event {TX}
     */
    /**
    inbox(event) {
        // Check if the event name matches a method in this class
        let method_name = `_${event.name}_`.toLowerCase();
        // Dispatch the event internally to the corresponding method
        if (typeof this[method_name] === 'function') {
            this[method_name](event.data);
        } else if (this.#observers.has(event.name)) {
            // If the event name is registered as an observer, notify observers
            this.#observers.get(event.name).forEach(callback => callback(event.data));
        } else {
            Logging.dev(`No handler ${method_name} for event '${event.name}' in PTT [${this.addr}] instance.`);
            Logging.debug(event)
        }

    }
     **/

    /**
    observe(property, callback) {
        assert(this, property && typeof property === 'string', `Property must be a non-empty string.`);
        assert(this, callback && typeof callback === 'function', `Callback must be a function.`);
        // Create a new Set for observers if it doesn't exist
        if (!this.#observers.has(property)) {
            this.#observers.set(property, new Set());
        }
        // Add subscriber to the property observers
        this.#observers.get(property).add(callback);
        // Return unsubscribe function
        return () => {
            this.#observers.get(property).delete(callback);
            if (this.#observers.get(property).size === 0) {
                this.#observers.delete(property);
            }
        };
    }
     **/

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
     * Check for an inline <script data-ntt-schema="ModelName"> in the document.
     * If found, parse and feed to NTT.SCHEMA() directly, skipping network fetch.
     * The script tag is removed after consumption (one-shot).
     * @param {string} model - Model name (e.g. "Product")
     * @returns {boolean} true if pre-loaded schema was found and consumed
     */
    static #consumePreloadedSchema(model) {
        const el = document.querySelector(`script[data-ntt-schema="${model}"]`);
        if (!el) return false;
        try {
            const data = JSON.parse(el.textContent);
            el.remove();
            Logging.debug(`[NTT] Pre-loaded schema for ${model}`);
            NTT.SCHEMA(data);
            return true;
        } catch (e) {
            Logging.error(`[NTT] Failed to parse pre-loaded schema for ${model}`, e);
            return false;
        }
    }

    /**
     * Check for an inline <script data-ntt-data="tablename"> in the document.
     * If found, parse and return the data array. The script tag is removed.
     * @param {string} tablename - Table/collection name (e.g. "products")
     * @returns {Array|null} Pre-loaded data or null
     */
    static #consumePreloadedData(tablename) {
        const el = document.querySelector(`script[data-ntt-data="${tablename}"]`);
        if (!el) return null;
        try {
            const data = JSON.parse(el.textContent);
            el.remove();
            Logging.debug(`[NTT] Pre-loaded data for ${tablename}`);
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
        const href = data.__tablename__
            ? `${config.API_URL}/${data.__tablename__}`
            : `${config.API_URL}/${addr}`;

        // Handle $defs (nested schemas) first — skip the main model itself
        if (data.$defs && typeof data.$defs === 'object') {
            for (const [key, value] of Object.entries(data.$defs)) {
                if (key === addr) continue; // Main model handled below
                if (value.type === 'object' && value.properties && !NTT.has(key)) {
                    Logging.debug(`[NTT.SCHEMA] Registering nested schema: ${key}`);
                    const defHref = value['$id'] || `${config.API_URL}/${key}`;
                    const DC = prototype(key, value, defHref);
                    NTT.#prototypes.set(key, DC);
                    NTT.#replayWaiting(key, DC);
                }
            }
        }

        // Create DynamicClass for the main model
        const DC = prototype(addr, data, href);
        NTT.#prototypes.set(addr, DC);

        // Replay queued messages + callbacks
        NTT.#replayWaiting(addr, DC);

        // Check for pre-loaded data before network fetch
        const tablename = data.__tablename__ || addr.toLowerCase() + 's';
        const preloadedData = NTT.#consumePreloadedData(tablename);
        if (preloadedData) {
            DC.READ(preloadedData);
        } else {
            const popDepth = data.ui?.populate?.depth ?? 1;
            DC.call('READ', popDepth > 0 ? {depth: popDepth} : {});
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
    const items = def.items || {};
    if (items.$ref) return items.$ref.split('/').pop();
    if (items.anyOf) {
        const ref = items.anyOf.find(a => a.$ref);
        return ref ? ref.$ref.split('/').pop() : null;
    }
    return null;
}

/**
 * Register an entity in a DynamicClass's instance cache.
 * Updates existing instances or creates new ones.
 */
function registerInstance(DC, data) {
    const id = data.id;
    if (DC.instances.has(id)) {
        DC.instances.get(id).update(data);
    } else {
        const inst = new DC(data);
        DC.instances.set(id, inst);
    }
}

/**
 * Normalize populated (eager-loaded) data in an entity response.
 * Converts inline objects back to href strings and pre-registers
 * the children as NTT instances so downstream code works unchanged.
 *
 * Handles two cases:
 * 1. Populated collection: {data: [...], meta: {...}} → href array
 * 2. Populated single Ref: inline object with $id → href string
 */
function normalizePopulated(entity, schema) {
    if (!entity || !schema?.properties) return;
    for (const [key, def] of Object.entries(schema.properties)) {
        const val = entity[key];
        if (!val) continue;

        // Case 1: Populated collection with pagination wrapper {data: [...], meta: {...}}
        if (def.type === 'array' && !Array.isArray(val) && Array.isArray(val?.data) && val?.meta) {
            const childModelName = resolveModelName(def);
            const ChildDC = childModelName ? NTT.get(childModelName) : null;
            const hrefs = [];
            for (const item of val.data) {
                if (item && typeof item === 'object' && item.$id) {
                    if (ChildDC) {
                        normalizePopulated(item, ChildDC._schema);
                        registerInstance(ChildDC, item);
                    }
                    hrefs.push(item.$id);
                } else if (typeof item === 'string') {
                    hrefs.push(item);
                }
            }
            entity[key] = hrefs;
            continue;
        }

        // Case 2: Populated single Ref — inline object with $id
        if (def.$ref && typeof val === 'object' && val.$id) {
            const refModelName = def.$ref.split('/').pop();
            const RefDC = refModelName ? NTT.get(refModelName) : null;
            if (RefDC) {
                normalizePopulated(val, RefDC._schema);
                registerInstance(RefDC, val);
            }
            entity[key] = val.$id;
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

    Logging.debug(`[NTT] Creating DynamicClass for ${addr}`);
    const fields = Object.keys(schema.properties || {});
    const methods = Object.keys(schema.methods || {});
    const className = addr;


    // 1. Create a subclass of NTT with dynamic properties
    const DynamicClass = class extends NTT {

      static instances = new Map();
      static _schema = schema;

      _data;


      constructor(data) {
        Logging.init(`Dynamic ${className} ${data.id}`, data)
        super(className, data.id);
        this.value = data;
        // Use the entity's $id (context-specific URL) when available.
        // For nested entities (e.g. comments inside products), $id carries
        // the correct CRUD path (/products/1/comments/3) while the
        // DynamicClass-level href points to the standalone collection (/comments).
        this.href = data.$id || `${href}/${this.id}`;
        Logging.dev(`[NTT] Created instance of ${className}`, this.addr)
      }

      get value() {
          if (!this._data) {
              return undefined
          }
          let data = this._data;
          data["$schema"] = `${config.API_URL}/${this.constructor.addr}`;
          data["$id"] = this.href;
          return this._data;
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
          const oldValue = this.value[field];
          // Assign the value to the field
          this.value[field] = value;
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
            target: DynamicClass.href,
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
                // Update href if the attaching component knows a more specific URL
                // (e.g. a nested entity whose href was set from DynamicClass default
                // but meta.href carries the correct parent-scoped URL)
                if (tx.meta?.href && tx.meta.href !== instance.href) {
                    instance.href = tx.meta.href;
                }
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
                    const fetchUrl = tx.meta?.href || `${DynamicClass.href}/${id}`;
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
                normalizePopulated(value, DynamicClass._schema);
                const id = value.id;
                if (DynamicClass.instances.has(id)) {
                    DynamicClass.instances.get(id).update(value);
                } else {
                    const instance = new DynamicClass(value);
                    DynamicClass.instances.set(id, instance);
                }
            }
        } else if (typeof data === 'object') {
            for (const [id, value] of Object.entries(data)) {
                normalizePopulated(value, DynamicClass._schema);
                if (DynamicClass.instances.has(id)) {
                    DynamicClass.instances.get(id).update(value);
                } else {
                    const instance = new DynamicClass(value);
                    DynamicClass.instances.set(id, instance);
                }
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
        if (data && data.id !== undefined) {
            if (!DynamicClass.instances.has(data.id)) {
                const instance = new DynamicClass(data);
                DynamicClass.instances.set(data.id, instance);
            } else {
                DynamicClass.instances.get(data.id).update(data);
            }
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
    };

    /**
     * Static DELETE — removes instance from registry and notifies watchers.
     * Called after a successful backend DELETE response.
     * The httpCallback swaps source/target, so tx.source is the entity URL.
     */
    DynamicClass.DELETE = function(data, tx) {
        const id = parseInt(tx.source?.split('/').pop());
        if (!isNaN(id)) {
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
    };

    /**
     * Instance READ — handles pull() responses for individual entities.
     * Normalizes populated wrappers ({data, meta} → href arrays) and
     * pre-registers child instances, same as the class-level READ.
     * Without this, pull() responses would store raw wrappers, breaking
     * components that expect href arrays for collection fields.
     */
    DynamicClass.prototype.READ = function(data) {
        normalizePopulated(data, DynamicClass._schema);
        this.update(data);
    };

    /**
     * Instance _response_ — handles method call responses (e.g. comment).
     * After a method executes server-side, re-pull the entity so child
     * lists (comments, etc.) reflect the new state.
     */
    DynamicClass.prototype._response_ = function(data, tx) {
        this.pull();
    };


    // 5. Apply Actor and Mixins
    Actor.subclass(DynamicClass, Observable);

    return DynamicClass;
}


window.NTT = NTT;

Actor.subclass(TT);

Actor.subclass(NTT, Observable);
