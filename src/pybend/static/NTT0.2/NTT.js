import { NTTUtils } from './NTTUtils.js';
import { EntityRegistry } from './EntityRegistry.js';
import { NTTFunctional } from './NTTFunctional.js';
import { NTTReactive } from './NTTReactive.js';
import assert from "../utils/Assert.js";

/**
 * NTT (Named Thing) - Core entity class
 * Represents virtual backend entities with functional state management
 */
export class NTT {
  #name;
  #addr;
  #href;
  #data;        // This IS the localState (simplified)
  #schema;
  #meta;
  #id;

  /**
   * Create a new NTT instance
   * @param {Object} config - Configuration object
   * @param {string} config.name - Entity name
   * @param {string} config.addr - Backend address/endpoint
   * @param {string} [config.href] - View URL (defaults to addr)
   * @param {Object} [config.data={}] - Initial data/state
   * @param {Object|string} [config.schema={}] - Schema or URL
   * @param {Object} [config.meta={}] - Additional metadata
   * @param {string} [config.id] - Custom ID (auto-generated if not provided)
   */
  constructor({ name, addr, href = null, data = {}, schema = {}, meta = {}, id = null }) {
    if (!name || !addr) {
      throw new Error('NTT requires at least a name and address');
    }

    this.#name = name;
    this.#addr = addr;
    this.#href = href || addr;
    this.#data = { ...data };
    this.#id = id || NTTUtils.generateId();

    // Initialize functional state management in meta
    this.#meta = {
      ...meta,
      remoteState: { ...data },          // Last known server state
      pendingOps: [],                    // Uncommitted transformations
      version: 1,                        // Optimistic locking version
      isDirty: false,                    // Has uncommitted changes
      isCommitting: false,               // Currently syncing
      hash: NTTUtils.simpleHash(data),   // Data integrity hash
      subscribers: new Set(),            // Change subscribers
      propertyObservers: new Map(),      // Property-specific observers
      conflictResolver: null             // Custom conflict resolution function
    };

    // Register this instance with EntityRegistry
    EntityRegistry.add(this);

    // Handle prototype resolution
    if (typeof schema === 'string') {
      this.resolveAndPromote(schema);
    } else if (typeof schema === 'object') {
      this.#schema = { ...schema };
    } else {
      throw new TypeError('prototype must be an object or a URL string');
    }
  }

  // ------------------ Instance Properties ------------------

  get id() { return this.#id; }
  get name() { return this.#name; }
  set name(val) { this.#name = val; }

  get addr() { return this.#addr; }
  set addr(val) { this.#addr = val; }

  get href() { return this.#href; }
  set href(val) { this.#href = val; }

  /**
   * Get current data state (this IS the localState)
   * @returns {Object} Current data state
   */
  get data() { return { ...this.#data }; }

  /**
   * Set data state with change notification
   * @param {Object} val - New data object
   */
  set data(val) {
    if (typeof val !== 'object') {
      throw new TypeError('data must be an object');
    }
    const oldData = { ...this.#data };
    this.#data = { ...this.#data, ...val };
    this.#meta.isDirty = !NTTUtils.deepEqual(this.#data, this.#meta.remoteState);
    this.#meta.hash = NTTUtils.simpleHash(this.#data);
    NTTUtils.notifySubscribers(this, oldData, this.#data);
  }

  get schema() { return { ...this.#schema }; }
  set schema(val) {
    if (typeof val === 'string') {
      this.resolveAndPromote(val);
    } else if (typeof val === 'object') {
      this.#schema = { ...val };
    } else {
      throw new TypeError('schema must be an object or a URL string');
    }
  }

  // Functional state getters (read-only access to internal state)
  get remoteState() { return { ...this.#meta.remoteState }; }
  get pendingOps() { return [...this.#meta.pendingOps]; }
  get version() { return this.#meta.version; }
  get isDirty() { return this.#meta.isDirty; }
  get isCommitting() { return this.#meta.isCommitting; }
  get hash() { return this.#meta.hash; }

  // Internal meta access (for other NTT classes)
  get _meta() { return this.#meta; }
  get _data() { return this.#data; }
  set _data(val) { 
    this.#data = val;
    this.#meta.hash = NTTUtils.simpleHash(this.#data);
  }

  // ------------------ Instance Methods ------------------

  /**
   * Resolve and promote instance using remote schema
   * @param {string} url - Schema URL
   * @returns {Promise<NTT>} Promise resolving to this instance
   */
  async resolveAndPromote(url) {
    // Check if subclass already exists
    const SubClass = EntityRegistry.getSubclass(url);
    if (SubClass) {
      Object.setPrototypeOf(this, SubClass.prototype);
      this.#schema = EntityRegistry.getPrototype(url);
      return this;
    }

    try {
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error(`Failed to fetch prototype from ${url}`);
      const schema = await res.json();

      const GeneratedSubClass = NTT.generateSubclass(schema);
      EntityRegistry.registerSubclass(url, GeneratedSubClass);
      EntityRegistry.registerPrototype(url, schema);
      
      Object.setPrototypeOf(this, GeneratedSubClass.prototype);
      this.#schema = schema;
      
      return this;
    } catch (err) {
      console.error(`[NTT] Failed to resolve and promote prototype from ${url}`, err);
      this.#schema = {};
      return this;
    }
  }

  /**
   * Serialize NTT instance to JSON
   * @returns {Object} JSON representation
   */
  toJSON() {
    return {
      id: this.#id,
      name: this.#name,
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
      name: this.#name,
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
   * Register a factory configuration for creating NTT instances
   * @param {string} factoryId - Unique identifier for the factory
   * @param {string} model - Model name/type
   * @param {Function} onSuccess - Success callback function
   * @param {Function} onError - Error callback function  
   * @param {string} url - API endpoint URL
   */
  static register = EntityRegistry.register.bind(EntityRegistry);
  
   /**
   * Create a new NTT instance using a registered factory
   * @param {string} factoryId - Factory identifier
   * @param {Object} data - Data for creation
   */
  static create(model, data, callback = null) {
    
    const evt = new Event(
      'create',
      NTTUtils.generateId(),
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
  static get = EntityRegistry.get.bind(EntityRegistry);

  /**
   * Remove NTT instance from registry
   * @param {string} instanceId - Instance identifier
   * @returns {boolean} True if instance was removed
   */
  static remove = EntityRegistry.unregister.bind(EntityRegistry);

  /**
   * Clear all instances and factories
   */
  static clear = EntityRegistry.clear.bind(EntityRegistry);

  /**
   * Discover API schemas and register them
   * @param {string} url - Schema discovery endpoint
   */
  static discover = EntityRegistry.discover.bind(EntityRegistry);

  /* Functional Operations */
  
  /**
   * Apply a pure transformation to an NTT instance's state
   * @param {string} instanceId - NTT instance identifier
   * @param {Function|Object} transformation - Function or object to merge
   * @param {Object} metadata - Optional operation metadata
   * @returns {NTT} The updated NTT instance
   */
  static evolve = NTTFunctional.evolve.bind(NTTFunctional);

  /**
   * Commit pending changes to the server for an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @returns {Promise<NTT>} Promise resolving to the NTT instance
   */
  static commit = NTTFunctional.commit.bind(NTTFunctional);

  /**
   * Discard pending changes and revert to remote state
   * @param {string} instanceId - NTT instance identifier
   * @returns {NTT} The NTT instance
   */
  static rollback = NTTFunctional.rollback.bind(NTTFunctional);

  /**
   * Merge with another NTT instance, resolving conflicts
   * @param {string} instanceId - Target NTT instance identifier
   * @param {string} otherInstanceId - Source NTT instance identifier
   * @param {Function} conflictResolver - Optional custom conflict resolver
   * @returns {NTT} The merged NTT instance
   */
  static merge = NTTFunctional.merge.bind(NTTFunctional);

  /**
   * Pull/refresh data for an NTT instance from server
   * @param {string} instanceId - NTT instance identifier
   */
  static pull = NTTFunctional.pull.bind(NTTFunctional);

  /**
   * Set custom conflict resolver for an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @param {Function} resolver - Conflict resolution function
   */
  static setConflictResolver = NTTFunctional.setConflictResolver.bind(NTTFunctional);

  /* Reactive Operations */
  
  /**
   * Subscribe to all changes on an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @param {Function} callback - Callback function (newData, oldData, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  static subscribe = NTTReactive.subscribe.bind(NTTReactive);

  /**
   * Observe changes to a specific property on an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @param {string} property - Property name to observe
   * @param {Function} callback - Callback function (newValue, oldValue, property, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  static observe = NTTReactive.observe.bind(NTTReactive);

  /**
   * Unsubscribe all observers from an NTT instance
   * @param {string} instanceId - NTT instance identifier
   */
  static unsubscribeAll = NTTReactive.unsubscribeAll.bind(NTTReactive);

  // ------------------ Legacy Compatibility ------------------

  /**
   * Access method for backward compatibility
   * @param {string} instanceId - NTT instance identifier
   * @returns {Object|null} Instance data or null
   */
  static access(instanceId) {
    const instance = EntityRegistry.get(instanceId);
    return instance ? instance.data : null;
  }
}

// Global exposure for backward compatibility
window.NTT = NTT;