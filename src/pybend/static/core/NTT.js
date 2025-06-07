import { Event } from './Event.js';
import { transport } from './TransportManager.js';
import {
  generateId,
  deepEqual,
  createOperation,
  getInstance,
  validateTransformation,
  applyTransformation,
  notifyAllObservers,
  initializeFunctionalState,
  isTypeCompatible,
  createApiEvent,
  findFactoryForInstance,
  defaultConflictResolver,
  detectConflicts,
  serializableMeta,
  validateCallback,
  validateString
} from './NTTUtils.js';

const DEFAULT_API_URL = "http://localhost:8000/api/";

export class NTT {
  #name;
  #addr;
  #href;
  #data;
  #schema;
  #prototype;
  #meta;
  #id; // Unique instance identifier

  // Static storage for EntityBroker functionality
  static #instances = new Map();        // id -> NTT instance
  static #factories = new Map();        // id -> factory config
  static #prototypes = new Map();       // url -> prototype schema
  static #subclasses = new Map();       // url -> generated subclass
  
  static handler = {};

  constructor({ name, addr, href = null, data = {}, prototype = {}, meta = {}, id = null }) {
    if (!name || !addr) throw new Error('NTT requires at least a name and address');

    this.#name = name;
    this.#addr = addr;
    this.#href = href || addr;
    this.#data = { ...data };
    this.#id = id || generateId();

    // Initialize functional state management in meta
    this.#meta = initializeFunctionalState(meta, data);

    // Register this instance
    NTT.#instances.set(this.#id, this);

    if (typeof prototype === 'string') {
      this.resolveAndPromote(prototype);
    } else if (prototype instanceof NTT) {
      this.#prototype = prototype;
    } else if (typeof prototype === 'object') {
      this.#prototype = { ...prototype };
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

  get data() { return { ...this.#data }; }
  set data(val) {
    if (typeof val !== 'object') throw new TypeError('data must be an object');
    const oldData = { ...this.#data };
    this.#data = { ...this.#data, ...val };
    this.#meta.localState = { ...this.#data };
    this.#meta.isDirty = !deepEqual(this.#meta.localState, this.#meta.remoteState);
    notifyAllObservers(this, this.#data, oldData);
  }

  get prototype() { return { ...this.#prototype }; }
  set prototype(val) {
    if (typeof val === 'string') {
      this.resolveAndPromote(val);
    } else if (typeof val === 'object') {
      this.#prototype = { ...val };
    } else {
      throw new TypeError('prototype must be an object or a URL string');
    }
  }

  get meta() { return { ...this.#meta }; }
  set meta(val) {
    if (typeof val !== 'object') throw new TypeError('meta must be an object');
    this.#meta = { ...this.#meta, ...val };
  }

  // Functional state getters
  get localState() { return { ...this.#meta.localState }; }
  get remoteState() { return { ...this.#meta.remoteState }; }
  get pendingOps() { return [...this.#meta.pendingOps]; }
  get version() { return this.#meta.version; }
  get isDirty() { return this.#meta.isDirty; }
  get isCommitting() { return this.#meta.isCommitting; }

  // ------------------ Instance Methods ------------------

  async resolveAndPromote(url) {
    if (NTT.#subclasses.has(url)) {
      const SubClass = NTT.#subclasses.get(url);
      Object.setPrototypeOf(this, SubClass.prototype);
      this.#prototype = NTT.#prototypes.get(url);
      return this;
    }

    try {
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error(`Failed to fetch prototype from ${url}`);
      const schema = await res.json();

      const SubClass = NTT.generateSubclass(schema);
      NTT.#subclasses.set(url, SubClass);
      NTT.#prototypes.set(url, schema);
      
      Object.setPrototypeOf(this, SubClass.prototype);
      this.#prototype = schema;
      
      return this;
    } catch (err) {
      console.error(`[NTT] Failed to resolve and promote prototype from ${url}`, err);
      this.#prototype = {};
      return this;
    }
  }

  toJSON() {
    return {
      id: this.#id,
      name: this.#name,
      addr: this.#addr,
      href: this.#href,
      data: this.#data,
      prototype: this.#prototype,
      meta: serializableMeta(this.#meta)
    };
  }

  clone() {
    const Ctor = Object.getPrototypeOf(this).constructor;
    const cloned = new Ctor({
      name: this.#name,
      addr: this.#addr,
      href: this.#href,
      data: structuredClone(this.#data),
      prototype: structuredClone(this.#prototype),
      meta: {
        ...structuredClone(this.#meta),
        // Reset functional state for clone
        subscribers: new Set(),
        propertyObservers: new Map(),
        conflictResolver: this.#meta.conflictResolver
      }
    });
    
    return cloned;
  }

  // ------------------ Static Factory Methods ------------------

  /**
   * Register a factory configuration for NTT instances
   */
  static register(id, model, onSuccess, onError, url = DEFAULT_API_URL) {
    NTT.#factories.set(id, {
      url: url,
      model: model,
      onSuccess: onSuccess || (() => {}),
      onError: onError || ((err) => console.error(err))
    });
  }

  /**
   * Create a new NTT instance via API
   */
  static create(id, data) {
    const factory = NTT.#factories.get(id);
    if (!factory) {
      throw new Error(`No factory registered for id: ${id}`);
    }

    const evt = new Event({ 
      name: 'create', 
      source: id, 
      target: 'api', 
      data: { 
        url: factory.url, 
        data, 
        onSuccess: (response) => {
          const ntt = new NTT({
            name: `${factory.model}_${response.id || Date.now()}`,
            addr: `${factory.url}/${response.id}`,
            data: response
          });
          
          // Set remote state to match initial server response
          ntt.#meta.remoteState = { ...response };
          ntt.#meta.localState = { ...response };
          ntt.#meta.isDirty = false;
          
          factory.onSuccess(ntt);
          return ntt;
        }, 
        onError: factory.onError 
      } 
    });
    
    transport.send(evt);
  }

  /**
   * Get an NTT instance by ID
   */
  static get(instanceId) {
    return NTT.#instances.get(instanceId) || null;
  }

  /**
   * Discover API schemas and register prototypes
   */
  static async discover(url) {
    try {
      const evt = new Event({ 
        name: 'load', 
        source: 'NTT', 
        target: 'api', 
        data: { 
          url, 
          onSuccess: (data) => {
            for (const [key, value] of Object.entries(data.$defs || {})) {
              NTT.#prototypes.set(key, value);
            }
            console.log('[NTT] Discovered schemas:', Object.keys(data.$defs || {}));
          },
          onError: (error) => console.error('[NTT] Discovery failed:', error)
        }, 
        meta: { type: 'discover' } 
      });
      
      transport.send(evt);
    } catch (error) {
      console.error('[NTT] Discovery error:', error);
    }
  }

  /**
   * Remove an NTT instance from registry
   */
  static remove(instanceId) {
    const instance = NTT.#instances.get(instanceId);
    if (instance) {
      NTT.unsubscribeAll(instanceId);
    }
    return NTT.#instances.delete(instanceId);
  }

  /**
   * Get all registered NTT instances
   */
  static getAllInstances() {
    return new Map(NTT.#instances);
  }

  /**
   * Clear all instances and factories
   */
  static clear() {
    // Clean up all subscriptions
    NTT.#instances.forEach((instance, id) => NTT.unsubscribeAll(id));
    NTT.#instances.clear();
    NTT.#factories.clear();
  }

  // ------------------ Static Functional Operations ------------------

  /**
   * Apply a pure transformation to an NTT instance
   */
  static evolve(instanceId, transformation, metadata = {}) {
    const instance = getInstance(NTT.#instances, instanceId);
    validateTransformation(transformation);

    const operation = createOperation('evolve', transformation, metadata, instance.#meta.version);
    const newState = applyTransformation(instance.#meta.localState, transformation);

    const oldData = { ...instance.#data };
    instance.#data = { ...newState };
    instance.#meta.localState = { ...newState };
    instance.#meta.pendingOps.push(operation);
    instance.#meta.isDirty = true;
    instance.#meta.version++;

    notifyAllObservers(instance, instance.#data, oldData);
    
    return instance;
  }

  /**
   * Commit pending changes to the server for an NTT instance
   */
  static async commit(instanceId) {
    const instance = getInstance(NTT.#instances, instanceId);

    if (!instance.#meta.isDirty || instance.#meta.isCommitting) {
      return instance;
    }

    instance.#meta.isCommitting = true;

    try {
      const factory = findFactoryForInstance(NTT.#factories, instance);

      const updatePromise = new Promise((resolve, reject) => {
        const evt = new Event({ 
          name: 'update', 
          source: instanceId, 
          target: 'api', 
          data: { 
            url: instance.addr, 
            data: instance.#meta.localState,
            version: instance.#meta.version,
            onSuccess: (response) => {
              // Successful commit - update remote state
              instance.#meta.remoteState = { ...response };
              instance.#meta.localState = { ...response };
              instance.#data = { ...response };
              instance.#meta.pendingOps = [];
              instance.#meta.isDirty = false;
              instance.#meta.isCommitting = false;
              
              if (factory?.onSuccess) {
                factory.onSuccess(instance);
              }
              
              resolve(instance);
            }, 
            onError: (error) => {
              instance.#meta.isCommitting = false;
              if (factory?.onError) {
                factory.onError(error);
              }
              reject(error);
            }
          } 
        });
        
        transport.send(evt);
      });

      return await updatePromise;
    } catch (error) {
      instance.#meta.isCommitting = false;
      throw error;
    }
  }

  /**
   * Discard pending changes and revert to remote state
   */
  static rollback(instanceId) {
    const instance = getInstance(NTT.#instances, instanceId);

    if (!instance.#meta.isDirty) {
      return instance;
    }

    const oldData = { ...instance.#data };
    instance.#data = { ...instance.#meta.remoteState };
    instance.#meta.localState = { ...instance.#meta.remoteState };
    instance.#meta.pendingOps = [];
    instance.#meta.isDirty = false;

    notifyAllObservers(instance, instance.#data, oldData);
    
    return instance;
  }

  /**
   * Merge with another NTT instance, resolving conflicts
   */
  static merge(instanceId, otherInstanceId, conflictResolver = null) {
    const instance = getInstance(NTT.#instances, instanceId);
    const otherInstance = getInstance(NTT.#instances, otherInstanceId, 'Other NTT instance not found');

    const resolver = conflictResolver || instance.#meta.conflictResolver || defaultConflictResolver;
    const conflicts = detectConflicts(
      instance.#meta.localState,
      instance.#meta.remoteState,
      otherInstance.#meta.localState
    );
    
    const mergedState = { ...instance.#meta.localState };

    // Apply non-conflicting changes
    for (const [key, otherValue] of Object.entries(otherInstance.#meta.localState)) {
      const remoteValue = instance.#meta.remoteState[key];
      if (otherValue !== remoteValue && !conflicts.some(c => c.property === key)) {
        mergedState[key] = otherValue;
      }
    }

    // Resolve conflicts
    for (const conflict of conflicts) {
      const resolution = resolver(conflict, instance, otherInstance);
      mergedState[conflict.property] = resolution;
    }

    // Apply merged state
    NTT.evolve(instanceId, mergedState, { mergeSource: otherInstanceId, conflicts: conflicts.length });
    
    return instance;
  }

  /**
   * Pull/refresh data for an NTT instance from server
   */
  static pull(instanceId) {
    const instance = getInstance(NTT.#instances, instanceId);
    const factory = findFactoryForInstance(NTT.#factories, instance);

    const evt = new Event({ 
      name: 'load', 
      source: instanceId, 
      target: 'api', 
      data: { 
        url: instance.addr, 
        onSuccess: (response) => {
          // Update remote state and reconcile with local changes
          instance.#meta.remoteState = { ...response };
          
          if (!instance.#meta.isDirty) {
            // No local changes - safe to update everything
            const oldData = { ...instance.#data };
            instance.#data = { ...response };
            instance.#meta.localState = { ...response };
            notifyAllObservers(instance, instance.#data, oldData);
          } else {
            console.warn(`[NTT] Instance ${instanceId} has uncommitted changes during pull`);
          }
          
          if (factory?.onSuccess) {
            factory.onSuccess(instance);
          }
          return instance;
        }, 
        onError: factory?.onError || ((err) => console.error(err))
      } 
    });
    
    transport.send(evt);
  }

  // ------------------ Static Reactive Subscriptions ------------------

  /**
   * Subscribe to all changes on an NTT instance
   */
  static subscribe(instanceId, callback) {
    const instance = getInstance(NTT.#instances, instanceId);
    validateCallback(callback);

    instance.#meta.subscribers.add(callback);
    
    return () => {
      instance.#meta.subscribers.delete(callback);
    };
  }

  /**
   * Observe changes to a specific property on an NTT instance
   */
  static observe(instanceId, property, callback) {
    const instance = getInstance(NTT.#instances, instanceId);
    validateString(property, 'property');
    validateCallback(callback);

    if (!instance.#meta.propertyObservers.has(property)) {
      instance.#meta.propertyObservers.set(property, new Set());
    }
    
    instance.#meta.propertyObservers.get(property).add(callback);
    
    return () => {
      const observers = instance.#meta.propertyObservers.get(property);
      if (observers) {
        observers.delete(callback);
        if (observers.size === 0) {
          instance.#meta.propertyObservers.delete(property);
        }
      }
    };
  }

  /**
   * Unsubscribe all observers from an NTT instance
   */
  static unsubscribeAll(instanceId) {
    const instance = getInstance(NTT.#instances, instanceId);
    instance.#meta.subscribers.clear();
    instance.#meta.propertyObservers.clear();
  }

  /**
   * Set custom conflict resolver for an NTT instance
   */
  static setConflictResolver(instanceId, resolver) {
    const instance = getInstance(NTT.#instances, instanceId);
    validateCallback(resolver, 'resolver');
    instance.#meta.conflictResolver = resolver;
  }

  // ------------------ Dynamic Class Generation ------------------

  static generateSubclass(schema, className = null) {
    const fields = Object.keys(schema.properties || {});
    const classTitle = className || schema.title || 'DynamicNTT';

    const SubClass = class extends NTT {
      constructor(opts) {
        super(opts);
      }
    };

    for (const field of fields) {
      const definition = schema.properties[field];
      const isReadonly = definition.readOnly === true;
      const label = definition.title || field;
      const hidden = definition.extra && definition.extra.hidden;

      Object.defineProperty(SubClass.prototype, field, {
        get() {
          return this.data[field];
        },
        set(value) {
          if (isReadonly) {
            throw new Error(`Field '${field}' is read-only`);
          }

          const expectedType = definition.type;
          if (expectedType && !isTypeCompatible(value, expectedType)) {
            throw new TypeError(`Invalid type for '${field}': expected ${expectedType}`);
          }

          // Use static functional evolution for property changes
          NTT.evolve(this.id, { [field]: value });
        },
        enumerable: !hidden,
        configurable: true,
      });

      if (!SubClass.labels) SubClass.labels = {};
      SubClass.labels[field] = label;
    }

    Object.defineProperty(SubClass, 'name', { value: classTitle });
    return SubClass;
  }

  // ------------------ Legacy Compatibility ------------------

  /**
   * Access method for backward compatibility
   */
  static access(instanceId) {
    const instance = NTT.#instances.get(instanceId);
    return instance ? instance.data : null;
  }
}

// Global exposure for backward compatibility
window.NTT = NTT;