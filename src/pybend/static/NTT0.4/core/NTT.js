import { Utils } from './Utils.js';
import assert from "../utils/Assert.js";
import { Registry } from './Registry.js';
//import { NTTFunctional } from './NTTFunctional.js';
//import { NTTReactive } from './NTTReactive.js';

class PTT{
  
  static #registry = new Map();
  
  #addr;
  #href;
  
  
  constructor(addr, href) {
    assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
    assert(this, !PTT.#registry.has(addr), `Address '${addr}' is already registered.`);
    assert(this, href && typeof href === 'string', `HREF must be a non-empty string.`);
    assert(this, !Registry.has(href), `HREF '${href}' is already registered in the Registry.`);
    assert(this, href.startsWith('http'), `HREF must be a valid HTTP URL, got: ${href}`);
    this.#addr = addr;
    this.#href = href;
    this.#registry.set(href, this);
    Registry.register(`${href}/schema`, this.update.bind(this));
    Registry.pull(`${href}/schema`);
  }
  
  update(data) {
  
  }
  
}

/**
 * NTT (Named Thing) - Core entity class
 * Represents virtual backend entities with functional state management
 */
export default class NTT {
  
  static #prototypes = new Map();
  
  #addr;
  #href;
  #data;
  #schema;
  #meta;
  #id;
  
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
  constructor({ addr="", href= "" , data = {}, schema = {}, meta = {}, id = null }) {
    
    this.#addr = addr;
    this.href = href || addr;
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
      Registry.pull(`${href}/schema`);
      Registry.pull(`${href}`);
    }
  }

  get href() { return this.#href; }
  set href(val) { this.#href = val; }

  get data() { return { ...this.#data }; }
  set data(val) {
    if (typeof val !== 'object') {
      throw new TypeError('data must be an object');
    }
    this.#data = { ...this.#data, ...val };
  }

  get schema() { return { ...this.#schema }; }
  set schema(val) { this.#schema = val }
  
  update(data) {
    this.#data = { ...this.#data, ...data };
    // Notify subscribers about data change
    this.#meta.subscribers.forEach(callback => callback(this));
  }

  describe(schema) {
    assert(this, schema && typeof schema === 'object', 'Schema must be an object');
    this.#schema = { ...this.#schema, ...schema };
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
    this.#schema = event.data;
  }

  /**
   * Serialize NTT instance to JSON
   * @returns {Object} JSON representation
   */
  toJSON() {
    return {
      id: this.#id,
      addr: this.#addr,
      href: this.#href,
      data: this.#data,
      schema: this.#schema,
      meta: {
        ...this.#meta,
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
      addr: this.#addr,
      href: this.#href,
      data: structuredClone(this.#data),
      schema: structuredClone(this.#schema),
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
    assert(this, href, 'HREF must be provided for registration');
    assert(this, typeof href === 'string', `HREF must be a string, got ${typeof href}`);
    assert(this, href.startsWith('http'), `HREF must be a valid HTTP URL, got: ${href}`);
    // Load schema from registry or create new NTT instance
    Registry.register(`${href}/schema`, NTT.define.bind(NTT, addr), true)
  }
  
  static define(addr, schema) {
  
    const fields = Object.keys(schema.properties || {});
    const className = addr

    // 1. Create a subclass of NTT with dynamic properties
    const SubClass = class extends NTT {
      constructor(opts) {
        super(opts);
      }
    };
    // 1.1 Set the class name dynamically
    Object.defineProperty(SubClass, 'name', { value: className });
    Object.defineProperty(SubClass, 'schema', { value: schema });

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
            throw new Error(`Field '${field}' is read-only`);
          }
          const expectedType = definition.type;
          if (expectedType && !isTypeCompatible(value, expectedType)) {
            throw new TypeError(`Invalid type for '${field}': expected ${expectedType}`);
          }

          // Use static functional evolution for property changes
          //NTT.evolve(this.id, { [field]: value });
        },
      });

      // 2.3 Add labels for UI representation
      if (!SubClass.labels) SubClass.labels = {};
      SubClass.labels[field] = label;
    }
    
    // 3. Add schema methods to the subclass prototype
    // ToDo: When backend is ready, implement remote method calling (RPC) from the prototype

    // 4. Register the subclass in the NTT registry
    NTT.#prototypes.set(addr, SubClass);
    
    return SubClass;
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
  static remove = Registry.unregister.bind(Registry);

  /**
   * Clear all instances and factories
   */
  static clear = Registry.clear.bind(Registry);

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