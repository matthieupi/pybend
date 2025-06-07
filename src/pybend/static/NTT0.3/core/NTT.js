import { Utils } from './Utils.js';
import assert from "../utils/Assert.js";
import { Registry } from './Registry.js';
//import { NTTFunctional } from './NTTFunctional.js';
//import { NTTReactive } from './NTTReactive.js';

/**
 * NTT (Named Thing) - Core entity class
 * Represents virtual backend entities with functional state management
 */
export default class NTT {
  #name;
  #addr;
  #href;
  #data;        // This IS the localState (simplified)
  #schema;
  #meta;
  #id;
  
  static #transport = window.Remote || null; // Static transport manager for event dispatching
  static #EventClass = undefined
  

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
    this.#id = id || Utils.generateId();

    // Initialize functional state management in meta
    this.#meta = {
      ...meta,
      remoteState: { ...data },          // Last known server state
      pendingOps: [],                    // Uncommitted transformations
      version: 1,                        // Optimistic locking version
      isDirty: false,                    // Has uncommitted changes
      isCommitting: false,               // Currently syncing
      hash: Utils.simpleHash(data),   // Data integrity hash
      subscribers: new Set(),            // Change subscribers
      propertyObservers: new Map(),      // Property-specific observers
      conflictResolver: null             // Custom conflict resolution function
    };

    // Register this instance with EntityRegistry
    Registry.register(href, this.inbox.bind(this));

    // Handle prototype resolution
    if (typeof schema === 'string') {
      // Todo
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
    this.#meta.isDirty = !Utils.deepEqual(this.#data, this.#meta.remoteState);
    this.#meta.hash = Utils.simpleHash(this.#data);
    Utils.notifySubscribers(this, oldData, this.#data);
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

  
  inbox(event) {
    /*
    assert(this,
        event instanceof NTT.Event,
        'Inbox only accepts NTT.Event instances');
     */
    console.info(event)
    console.info(`[NTT] Inbox received event: ${event.name} from ${event.source}`);
    assert(this,
        this[`_${event.name}`] && typeof this[`_${event.name}`] === 'function',
        "Event handler not found for event: " + event.name);
    
    // Dispatch the event to the appropriate method
    this[`_${event.name.split(" ")[0]}`](event);
  }
  
  observe(callback) {
    assert(this,
        callback && typeof callback === 'function',
        'Callback must be a function');
    this.#meta.subscribers.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.#meta.subscribers.delete(callback);
    };
  }
  
  send(event) {
    // Make sure the inbox is set up
    assert(this,
        this.#transport,
        'Transport manager not set. Cannot send event.');
    assert(this,
        event instanceof NTT.Event,
        'Event must be an instance of NTT.Event');
    if (!Registry.get(this.#id)) {
      Registry.add(this); // Ensure instance is registered before sending
    }
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
    this.#meta.hash = Utils.simpleHash(this.#data);
  }

  // ------------------ Instance Methods ------------------

  /**
   * Resolve and promote instance using remote schema
   * @param {string} url - Schema URL
   * @returns {Promise<NTT>} Promise resolving to this instance
   */
  async resolveAndPromote(url) {
    console.log(`[NTT] Resolving prototype from ${url}`)
    // Check if subclass already exists
    await Registry.register(url, this.schema)
      return this;
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
  
  // Static configuration
  
  static get Transport() {
    return this.#transport;
  }
  
  static set Transport(value) {
    assert(this, value,
        'Transport manager cannot be null');
    assert(this, value.prototype.hasOwnProperty("dispatch"),
        `Transport manager must implement dispatch method. Got:\n
        ${Object.getOwnPropertyNames(value.prototype).join(', ')}`);
    assert(typeof value.dispatch === 'function',
        'Transport manager dispatch method must be a function');
    
    this.#transport = value;
  }
  
  static get Event() {
    if (!this.#EventClass) {
      throw new Error('Event class not set. Use NTT.setEventClass() to configure.');
    }
    return this.#EventClass;
  }
  
  static set Event(value) {
    assert(value,
      'Event class cannot be null');
    assert(this, value.prototype, 'Event class must be a constructor function');
    assert(this, value.prototype.dispatch && typeof value.prototype.dispatch === 'function',
      'Event class must implement dispatch method');
    return this.#EventClass = value;
  }
    
  static dispatch(event) {
    assert(this,
        this.#transport,
        'Transport manager not set. Cannot dispatch event.');
    assert(this,
        event instanceof this.Event,
        'Event must be an instance of NTT.Event');
    console.info(`Dispatching event ${event.name} from ${event.source} to ${event.target}`, event.repr());
    this.#transport.send(event);
    }

  // ------------------ Static Methods (Delegated to specialized classes) ------------------

  /* Entity Registry Methods */
  
  /**
   */
  static register(addr, href, callback, ) {
    assert(this, addr, 'Address must be provided for registration');
    assert(this, typeof addr === 'string', `Address must be a string, got ${typeof addr}`);
    assert(this, href, 'HREF must be provided for registration');
    assert(this, typeof href === 'string', `HREF must be a string, got ${typeof href}`);
    assert(this, callback && typeof callback === 'function', 'Callback must be a function');
    
    let ntt;
    
    if (Registry.has(addr)) {
      ntt = Registry.get(addr);
    } else {
        ntt = new NTT({
            name: addr,
            addr: addr,
            href: href
        });
    }
    ntt.observe(callback)
    
    
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