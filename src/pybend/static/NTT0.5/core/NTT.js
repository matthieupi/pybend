import assert from "../utils/Assert.js";
import {config} from "../config.js";
import {isUrl, Utils} from './Utils.js';
import {registry, registrar, getRegistrar} from "./registrar.js";
import Event from "./Event.js";
import {remote} from "./Remote.js";

/**
 * TT (Transfer Type) - Base class for transfer types
 */
class TT {
    
    /** Registry of all TT instances */
    static #registry = new Map();
    
    
    #addr;
    #href;
    #signals = new Set(); // Map of signals for this instance
    #observers = new Map(); // Map of property observers
    
    constructor(addr, href, remote = TT.remote) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        assert(this, href && typeof isUrl(href), `[TT] ${addr} - HREF must be a valid URL, got: ${href}`);
        
        if (TT.#registry.has(href)) { console.warn(`[TT] '${href}' will be overwritten in the Registry.`); }
        
        this.#addr = addr;
        this.#href = href;
        TT.#registry.set(addr, href);
    }
    
    // Protected getters for subclasses
    get addr() { return this.#addr; }
    get href() { return this.#href; }
    set href(href) {
        assert(this, isUrl(href), `[TT] ${this.addr} - HREF must be a valid URL, got: ${href}`);
        this.#href = href
        TT.#registry.set(this.#addr, href);
    }
    
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
    
    notify(property, newValue, oldValue) {
        assert(this, property && typeof property === 'string', `Property must be a non-empty string.`);
        assert(this, this.#observers.has(property), `No observers registered for property '${property}'.`);
        // Notify all observers for the specified property
        this.#observers.get(property).forEach(callback => callback(newValue, oldValue, property, this));
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
   
    /**
     * Send an event via the registrar callback
     * @param event {Event}
     */
    send(event) {
        assert(this, event && typeof event === 'object', `Data must be a non-empty object.`);
        // Retrieve href callback and dispatch the event to it
        console.warn(`Sending event '${event.name}' from ${event.source} to ${event.target}`, event)
        registry.get(event.target)(event)
    }
    
    /**
     * Inbox method to handle incoming events
     * @param event {Event}
     */
    inbox(event) {
        // Check if the event name matches a method in this class
        let method_name = `_${event.name}_`.toLowerCase();
        // Dispatch the event internally to the corresponding method
        if (typeof this[method_name] === 'function') {
            this[method_name](event.data);
        } else if (this.#observers.has(event.name)) {
            // If the event name is registered as an observer, notify observers
            this.#observers.get(event.name).forEach(callback => callback(event.data, null, event.name, this));
        } else {
            console.warn(`No handler ${method_name} for event '${event.name}' in PTT instance.`);
        }
        
    }
    
    observe(property, callback) {
        assert(this, property && typeof property === 'string', `Property must be a non-empty string.`);
        assert(this, callback && typeof callback === 'function', `Callback must be a function.`);
        
        if (!this.#observers.has(property)) {
            this.#observers.set(property, new Set());
        }
        //
        this.#observers.get(property).add(callback);
        
        // Return unsubscribe function
        return () => {
            this.#observers.get(property).delete(callback);
            if (this.#observers.get(property).size === 0) {
                this.#observers.delete(property);
            }
        };
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
    
    _error_(event) {
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
  
    static #prototypes = new Map();
    static #models = new Map();
    
    #instances;
    #data;
    #cls;
  
    constructor(addr, href) {
        super(addr, href);
        // Save the Prototype instance to the PTT local registry
        PTT.#prototypes.set(addr, this);
        this.#instances = new Map();
        // Register the inbox method to handle incoming events
        registrar(addr, this.inbox.bind(this))
        // Register the uplink for remote communication
        registrar(href, remote.send)
    }
    
    get schema() { return this.#data; }
    get value() { return this.#data; }
    set value(val) {
        this.#data = val;
        this.#cls = prototype(this.addr, this.#data);
        this.signal()
    }
    
    pull() {
        assert(this, isUrl(this.href), `[PTT] ${this.addr} HREF must be a valid HTTP URL, got: ${this.href}`);
        // Register the inbox method to handle incoming events
        this.call('SCHEMA', {}, {remote: true});
        return this;
    }
  
    _schema_(data) {
        // If the data has a __tablename__, we need to link this prototype to the endpoint
        if (data['__tablename__']) {
            this.href = `${config.API_URL}/${data['__tablename__']}`;
            registrar(this.href, remote.send)
        }
        // Create a subclass of NTT with the provided schema
        console.log("[PTT] Received schema data for", this.addr, ":", data);
        this.value = data;
    }
    
    
    
    // ------------------ Static Methods ------------------ //
    
    /**
     * Creates a PTT instance and registers it in the global registry.
     * @param addr
     * @param href
     * @returns {PTT}
     */
    static register(addr, href) {
        assert(this, !PTT.#prototypes.has(addr), `Address '${addr}' is already registered.`);
        return new PTT(addr, href).pull();
    }
    
    static get(addr) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        if (!PTT.#prototypes.has(addr)) {
            throw new Error(`Trying to get Proto with address '${addr}': is not registered.`);
        }
        return PTT.#prototypes.get(addr);
    }
    
    static attach(addr, callback) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        assert(this, callback && typeof callback === 'function', `Callback must be a function.`);
        let unsubscribe;
        if (!PTT.#prototypes.has(addr)) {
            // If the address is not registered, get the PTT instance from the backend
            const href = `${config.API_URL}/${addr}`;
            unsubscribe =  PTT.register(addr, href).signal(callback, true);
            
        } else {
            unsubscribe = PTT.#prototypes.get(addr).signal(callback);
        }
        
        // Return unregister
        return unsubscribe;
        
    }
    
    
    

 
}

/**
 * NTT (Named Transfer Type) - Core entity class
 * Represents virtual backend entities with functional state management
 */
export class NTT extends TT {
  
  
    #proto;
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
      Registry.register(`${href}/schema`, this.describe.bind(this));
      Registry.register(`${href}`, this.update.bind(this));
      //Registry.pull(`${href}/schema`);
      //Registry.pull(`${href}`);
    }
  }

  get data() { return { ...this.#data }; }
  set data(val) {
    if (typeof val !== 'object') {
      throw new TypeError('data must be an object');
    }
    this.#data = { ...this.#data, ...val };
  }

  get schema() { return { ...this.#meta["schema"] }; }
  set schema(val) { this.#meta['schema'] = val }
  
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

  describe(schema) {
    assert(this, schema && typeof schema === 'object', 'Schema must be an object');
    this.#meta['schema'] = { ...this.#meta[schema], ...schema };
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


/**
 *
 * @param addr
 * @param schema
 * @returns {class}
 */
function prototype(addr, schema) {

    const fields = Object.keys(schema.properties || {});
    const className = addr

    // 1. Create a subclass of NTT with dynamic properties
    const DynamicClass = class extends PTT {
      constructor(opts) {
        super(opts);
      }
    };
    // 1.1 Set the class name dynamically
    Object.defineProperty(DynamicClass, 'name', {value: className});
    Object.defineProperty(DynamicClass, 'schema', {value: schema});

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
      if (!DynamicClass.labels) DynamicClass.labels = {};
      DynamicClass.labels[field] = label;
    }

    // 3. Add schema methods to the subclass prototype
    // ToDo: When backend is ready, implement remote method calling (RPC) from the prototype

    return DynamicClass;
}