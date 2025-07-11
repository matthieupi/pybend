import {isUrl, Utils} from './Utils.js';
import assert from "../utils/Assert.js";
import {registry, registrar, getRegistrar} from "./registrar.js";
import Event from "./Event.js";
import {remote} from "./Remote.js";

class TT {
  
    static #registry = new Map();
    
    #addr;
    #href;
    
    constructor(addr, href) {
        assert(this, addr && typeof addr === 'string', `TT: Address must be a non-empty string.`);
        assert(this, !TT.#registry.has(addr), `TT: Address '${addr}' is already registered.`);
        assert(this, href && typeof href === 'string', `TT: HREF must be a non-empty string.`);
        assert(this, !registry.has(href), `TT: HREF '${href}' is already registered in the Registry.`);
        assert(this, href.startsWith('http'), `TT: HREF must be a valid HTTP URL, got: ${href}`);
        
        this.#addr = addr;
        this.#href = href;
        TT.#registry.set(addr, href);
    }
    
    // Protected getters for subclasses
    get addr() { return this.#addr; }
    get href() { return this.#href; }
    
    static register(addr, href) {
        console.warn(`Registering address '${addr}' with HREF '${href}'`)
        assert(this, addr && typeof addr === 'string' && !!addr,
            `Address must be a non-empty string.`);
        assert(this, !TT.#registry.has(addr),
            `Address '${addr}' is already registered.`);
        assert(this, isUrl(href),
            `HREF must be a valid URL, got: ${href}`);
        TT.#registry.set(addr, href);
    }
    
    static get(addr) {
        return TT.#registry.get(addr);
    }
   
    /**
     * Send an event via the registrar callback
     * @param event {Event}
     */
    send(event) {
        assert(this, event && typeof event === 'object', `Data must be a non-empty object.`);
        // Retrieve href callback and dispatch the event to it
        console.warn(`Sending event '${event.name}' from ${event.source} to ${event.target}`, event)
        console.log(registry)
        registry.get(event.target)(event)
    }
    
    
    /**
     * Inbox method to handle incoming events
     * @param event {Event}
     */
    inbox(event) {
        // Check if the event name matches a method in this class
        let method_name = `_${event.name}`.toLowerCase();
        // Dispatch the event internally to the corresponding method
        if (typeof this[method_name] === 'function') {
            this[method_name](event.data);
        } else {
            console.warn(`No handler ${method_name} for event '${event.name}' in PTT instance.`);
        }
        
    }
  
  
    /**
     * Call a distant method on the PTT instance
     * @param method {string} - Method name to call
     * @param data {Object} - Data (args and kwargs) to send with the method call
     * @param [meta] {Object} - Additional metadata for the call
     */
    call(method, data = {}, meta = {}) {
      this.send(
        new Event({
            name: method,
            source: this.addr,
            target: this.href,
            data: data,
            meta: meta,
            timestamp: Date.now()
        })
      )
    }
    
    _error(event) {
        console.group(`[TT] Error received from ${event.source}:`, event.name);
        console.error(`[TT] Error received from ${event.source}->${event.target}`);
        console.warn(`[TT] Error data:`, event.data);
        console.warn(`[TT] Event meta:`, event.meta);
        console.groupEnd()
    }
    
    
}


/**
 * PTT (ProtoTransferType) - Protocol Transfer Type
 * Acts as a proxy for remote registered models
 */
export class PTT extends TT{
  
    static #registry = new Map();
    static #models = new Map();
    
    #schema;
    #cls;
    #observers = new Set();
  
    constructor(addr, href) {
        super(addr, href);
        // Save the Prototype instance to the PTT local registry
        PTT.#registry.set(addr, this);
        // Register the inbox method to handle incoming events
        registrar(addr, this.inbox.bind(this))
        // Register the uplink for remote communication
        registrar(href, remote.send)
        // Also bind to schema description
        registrar(`${href}/schema`, this.inbox.bind(this));
    }
    
    // Leaving for example legacy
    get data() { return this.#schema; }
    set data(val) { return this.#schema = val; }
    get schema() { return this.#schema; }
    set schema(val) { this.#schema = val; }
    
    
    pull() {
        assert(this, isUrl(this.href), `HREF must be a valid HTTP URL, got: ${this.href}`);
        // Register the inbox method to handle incoming events
        this.call('SCHEMA', {}, {remote: true});
        return this;
    }
  
    _schema(data) {
        console.log("[PTT] Received schema data for", this.addr, ":", data);
        // Create a subclass of NTT with the provided schema
        this.#schema = data;
        this.#cls = PTT.define(this.addr, data)
    }
    
    
    // ------------------ Static Methods ------------------ //
    
    /**
     * Creates a PTT instance and registers it in the global registry.
     * @param addr
     * @param href
     * @returns {PTT}
     */
    static register(addr, href) {
        assert(this, !PTT.#registry.has(addr), `Address '${addr}' is already registered.`);
        return new PTT(addr, href).pull().constructor;
    }
    
    static get(addr) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        if (!PTT.#registry.has(addr)) {
            throw new Error(`Address '${addr}' is not registered.`);
        }
        return PTT.#registry.get(addr);
    }
    
    
    static define(addr, schema) {
  
        const fields = Object.keys(schema.properties || {});
        const className = addr
  
        // 1. Create a subclass of NTT with dynamic properties
        const SubClass = class extends PTT {
          constructor(opts) {
            super(opts);
          }
        };
        // 1.1 Set the class name dynamically
        Object.defineProperty(SubClass, 'name', {value: className});
        Object.defineProperty(SubClass, 'schema', {value: schema});
  
        // 2. Add schema properties to the subclass prototype
        for (const field of fields) {
          const definition = schema.properties[field];
          const isReadonly = definition.readOnly === true;
          const label = definition.title || field;
          const hidden = definition.extra && definition.extra.hidden;
    
          Object.defineProperty(SubClass.prototype, field, {
            enumerable: !hidden,
            configurable: true,
            // 2.1 Variable access
            get() {
              return this[field];
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
            },
          });
    
          // 2.3 Add labels for UI representation
          if (!SubClass.labels) SubClass.labels = {};
          SubClass.labels[field] = label;
        }
  
        // 3. Add schema methods to the subclass prototype
        // ToDo: When backend is ready, implement remote method calling (RPC) from the prototype
  
        return SubClass;
    }
 
}

/**
 * NTT (Named Transfer Type) - Core entity class
 * Represents virtual backend entities with functional state management
 */
export class NTT extends TT {
  
  
    #data;
    #meta = {};
  
  /**
   * Create a new NTT instance
   * @param {string} name - Entity name
   * @param {string} addr - Backend address/endpoint
   * @param {string} [href] - View URL (defaults to addr)
   * @param {Object} [data={}] - Initial data/state
   * @param {Object|string} [schema={}] - Schema or URL
   * @param {Object} [meta={}] - Additional metadata
   * @param {string} [id] - Custom ID (auto-generated if not provided)
   */
  constructor({ addr="", href= "" , data = {}, schema = {}, meta = {}, }) {
    super(addr, href);
    this.#data = { ...data };
    this.schema = schema;

    // Initialize functional state management in meta
    this.#meta = {
      ...meta,
      remoteState: { ...data },          // Last known server state
      pendingOps: [],                    // Uncommitted transformations
      hash: Utils.simpleHash(data),   // Data integrity hash
      subscribers: new Set(),            // Change subscribers
      propertyObservers: new Map(),      // Property-specific observers
    };

    // Register this instance with EntityRegistry
    if (href) {
      registrar(`${href}/schema`, this.describe.bind(this));
      registrar(`${href}`, this.update.bind(this));
    }
  }

  get data() { return { ...this.#data }; }
  set data(val) {
    if (typeof val !== 'object') {
      throw new TypeError('data must be an object');
    }
    this.#data = { ...this.#data, ...val };
  }

  get proto() { return { ...this.#meta["proto"] }; }
  set proto(val) { this.#meta['proto'] = val }
  
  update(data) {
    this.#data = { ...this.#data, ...data };
    if (data.hasOwnProperty('name') && data.name === "error") {
      console.warn(`[NTT] Error received from ${this.addr}:`, data.message || data.error || "Unknown error")
    }
    // Notify subscribers about data change
    else{
      this.#meta.subscribers.forEach(callback => callback(this));
    }
  }

  describe(proto, data = {}) {
    assert(this, proto && typeof proto === 'object', 'Proto must be an object');
    this.#meta['proto'] = { ...this.#meta['proto'], ...proto };
    // Notify subscribers about schema change
    this.#meta.subscribers.forEach(callback => callback(this));
  }
 
  observe(callback) {
    assert(this, callback && typeof callback === 'function', 'Callback must be a function');
    this.#meta.subscribers.add(callback);
    // Return unsubscribe function
    return () => {
      this.#meta.subscribers.delete(callback);
    };
  }
 
  _error(event) {
    console.error(`[NTT] ${event.name} from ${event.source}:`, event.data);
  }
  
  _read(event) {
    assert(this, event.data && typeof event.data === 'object', "Read event data must be an object");
    this.#meta.remoteState = event.data;
    this.data = event.data;
  }
  
  _schema(event) {
    assert(this, event.data && typeof event.data === 'object', `Invalid error event ${event}`);
    this.#meta['schema'] = event.data;
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

  /**
   * Create a deep copy of this NTT instance
   * @returns {NTT} Cloned instance
   */
  clone() {
    const Ctor = Object.getPrototypeOf(this).constructor;
    return new Ctor({
      addr: this.addr,
      href: this.href,
      data: structuredClone(this.#data),
      meta: {
        ...structuredClone(this.#meta),
        // Reset functional state for clone
        subscribers: new Set(),
        propertyObservers: new Map(),
        conflictResolver: this.#meta.conflictResolver
      }
    });
  }
 
  // ------------------ Static Methods (Delegated to specialized classes) ------------------

  /* Entity Registry Methods */
  
  /**
   */
  static register(addr, href) {
    assert(this, addr, 'Address must be provided for registration');
    assert(this, typeof addr === 'string', `Address must be a string, got ${typeof addr}`);
    //assert(this, href, 'HREF must be provided for registration');
    //assert(this, typeof href === 'string', `HREF must be a string, got ${typeof href}`);
    //assert(this, href.startsWith('http'), `HREF must be a valid HTTP URL, got: ${href}`);
    // Load schema from registry or create new NTT instance
    Registry.register(`${href}/schema`, NTT.define.bind(NTT, addr))
  }

  
   /**
   */
  static create(model, data, callback = null) {
    
    const evt = new NTT.Event(
      'create',
      Utils.generateId(),
      model,
      `${DEFAULT_API_URL}/${model}`,
      data,
      callback
    );
    
    evt.dispatch();
  }


  /**
   * Get NTT instance by ID
   * @param {string} instanceId - Instance identifier
   * @returns {NTT|null} NTT instance or null if not found
   */
  static get(instanceId) {
    assert(this, instanceId, 'Instance ID must be provided');
    // ToDo Get instance from registry from NTT.get(instanceId)
  }

  /**
   * Remove NTT instance from registry
   * @param {string} instanceId - Instance identifier
   * @returns {boolean} True if instance was removed
   */
  //static remove = Registry.unregister.bind(Registry);

  /**
   * Clear all instances and factories
   */
  //static clear = Registry.clear.bind(Registry);

  /**
   * Discover API schemas and register them
   * @param {string} url - Schema discovery endpoint
   */
  // static discover = Registry.discover.bind(Registry);

  /* Functional Operations */
  
  /**
   * Apply a pure transformation to an NTT instance's state
   * @param {string} instanceId - NTT instance identifier
   * @param {Function|Object} transformation - Function or object to merge
   * @param {Object} metadata - Optional operation metadata
   * @returns {NTT} The updated NTT instance
   */
  // static evolve = NTTFunctional.evolve.bind(NTTFunctional);

  /**
   * Commit pending changes to the server for an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @returns {Promise<NTT>} Promise resolving to the NTT instance
   */
  // static commit = NTTFunctional.commit.bind(NTTFunctional);

  /**
   * Discard pending changes and revert to remote state
   * @param {string} instanceId - NTT instance identifier
   * @returns {NTT} The NTT instance
   */
  // static rollback = NTTFunctional.rollback.bind(NTTFunctional);

  /**
   * Merge with another NTT instance, resolving conflicts
   * @param {string} instanceId - Target NTT instance identifier
   * @param {string} otherInstanceId - Source NTT instance identifier
   * @param {Function} conflictResolver - Optional custom conflict resolver
   * @returns {NTT} The merged NTT instance
   */
  // static merge = NTTFunctional.merge.bind(NTTFunctional);

  /**
   * Pull/refresh data for an NTT instance from server
   * @param {string} instanceId - NTT instance identifier
   */
  // static pull = NTTFunctional.pull.bind(NTTFunctional);

  /**
   * Set custom conflict resolver for an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @param {Function} resolver - Conflict resolution function
   */
  // static setConflictResolver = NTTFunctional.setConflictResolver.bind(NTTFunctional);

  /* Reactive Operations */
  
  /**
   * Subscribe to all changes on an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @param {Function} callback - Callback function (newData, oldData, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  // static subscribe = NTTReactive.subscribe.bind(NTTReactive);

  /**
   * Observe changes to a specific property on an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @param {string} property - Property name to observe
   * @param {Function} callback - Callback function (newValue, oldValue, property, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  // static observe = NTTReactive.observe.bind(NTTReactive);

  /**
   * Unsubscribe all observers from an NTT instance
   * @param {string} instanceId - NTT instance identifier
   */
  // static unsubscribeAll = NTTReactive.unsubscribeAll.bind(NTTReactive);

  // ------------------ Legacy Compatibility ------------------

  /**
   * Access method for backward compatibility
   * @param {string} instanceId - NTT instance identifier
   * @returns {Object|null} Instance data or null
   */
  static access(instanceId) {
    const instance = Registry.get(instanceId);
    return instance ? instance.data : null;
  }
}

// Global exposure for backward compatibility
window.NTT = NTT;