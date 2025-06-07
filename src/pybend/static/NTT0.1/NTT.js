// NTT.js - Core entity class that orchestrates all components

import { NTTRegistry } from './NTTRegistry.js';
import { NTTBroker } from './NTTBroker.js';
import { NTTFunctional } from './NTTFunctional.js';
import { NTTObserver } from './NTTObserver.js';
import {
  generateId,
  initializeFunctionalState,
  isTypeCompatible,
  serializableMeta
} from './NTTUtils.js';

/**
 * Core NTT (Named Thing) class - Virtual representation of backend entities
 * Orchestrates broker, functional, and observer components
 */
export class NTT {
  #name;
  #addr;
  #href;
  #data;
  #prototype;
  #meta;
  #id;

  constructor({ name, addr, href = null, data = {}, prototype = {}, meta = {}, id = null }) {
    if (!name || !addr) {
      throw new Error('NTT requires at least a name and address');
    }

    this.#name = name;
    this.#addr = addr;
    this.#href = href || addr;
    this.#data = { ...data };
    this.#id = id || generateId();

    // Initialize functional state management in meta
    this.#meta = initializeFunctionalState(meta, data);

    // Register this instance in the global registry
    NTTRegistry.setInstance(this.#id, this);

    // Handle prototype setup
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
    
    // Import notifyAllObservers dynamically to avoid circular dependency
    import('./NTTUtils.js').then(({ notifyAllObservers, deepEqual }) => {
      const oldData = { ...this.#data };
      this.#data = { ...this.#data, ...val };
      this.#meta.localState = { ...this.#data };
      this.#meta.isDirty = !deepEqual(this.#meta.localState, this.#meta.remoteState);
      notifyAllObservers(this, this.#data, oldData);
    });
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

  // Functional state getters (read-only access to internal state)
  get localState() { return { ...this.#meta.localState }; }
  get remoteState() { return { ...this.#meta.remoteState }; }
  get pendingOps() { return [...this.#meta.pendingOps]; }
  get version() { return this.#meta.version; }
  get isDirty() { return this.#meta.isDirty; }
  get isCommitting() { return this.#meta.isCommitting; }

  // Internal access for other NTT components (prefixed with _)
  get _meta() { return this.#meta; }
  get _data() { return this.#data; }
  set _data(val) { this.#data = val; }

  // ------------------ Schema Resolution ------------------

  async resolveAndPromote(url) {
    // Check if we already have the subclass cached
    if (NTTRegistry.hasSubclass(url)) {
      const SubClass = NTTRegistry.getSubclass(url);
      Object.setPrototypeOf(this, SubClass.prototype);
      this.#prototype = NTTRegistry.getPrototype(url);
      return this;
    }

    try {
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error(`Failed to fetch prototype from ${url}`);
      const schema = await res.json();

      const SubClass = NTT.generateSubclass(schema);
      NTTRegistry.setSubclass(url, SubClass);
      NTTRegistry.setPrototype(url, schema);
      
      Object.setPrototypeOf(this, SubClass.prototype);
      this.#prototype = schema;
      
      return this;
    } catch (err) {
      console.error(`[NTT] Failed to resolve and promote prototype from ${url}`, err);
      this.#prototype = {};
      return this;
    }
  }

  // ------------------ Serialization ------------------

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

  // ------------------ Static API - Delegates to Component Classes ------------------

  // Broker methods (API communication)
  static register = NTTBroker.register.bind(NTTBroker);
  static unregister = NTTBroker.unregister.bind(NTTBroker);
  static create = NTTBroker.create.bind(NTTBroker);
  static discover = NTTBroker.discover.bind(NTTBroker);
  static pull = NTTBroker.pull.bind(NTTBroker);

  // Functional methods (state management)
  static evolve = NTTFunctional.evolve.bind(NTTFunctional);
  static commit = NTTFunctional.commit.bind(NTTFunctional);
  static rollback = NTTFunctional.rollback.bind(NTTFunctional);
  static merge = NTTFunctional.merge.bind(NTTFunctional);
  static snapshot = NTTFunctional.snapshot.bind(NTTFunctional);
  static restore = NTTFunctional.restore.bind(NTTFunctional);
  static setConflictResolver = NTTFunctional.setConflictResolver.bind(NTTFunctional);

  // Observer methods (reactive subscriptions)
  static subscribe = NTTObserver.subscribe.bind(NTTObserver);
  static observe = NTTObserver.observe.bind(NTTObserver);
  static observeProperties = NTTObserver.observeProperties.bind(NTTObserver);
  static observeStateTransitions = NTTObserver.observeStateTransitions.bind(NTTObserver);
  static observeCondition = NTTObserver.observeCondition.bind(NTTObserver);
  static observeDebounced = NTTObserver.observeDebounced.bind(NTTObserver);
  static observeThrottled = NTTObserver.observeThrottled.bind(NTTObserver);
  static unsubscribeAll = NTTObserver.unsubscribeAll.bind(NTTObserver);

  // Registry methods (instance management)
  static get(instanceId) {
    return NTTRegistry.getInstance(instanceId);
  }

  static remove(instanceId) {
    // Clean up observers before removing
    NTTObserver.unsubscribeAll(instanceId);
    return NTTRegistry.removeInstance(instanceId);
  }

  static getAllInstances() {
    return NTTRegistry.getAllInstances();
  }

  static clear() {
    // Clean up all observations first
    const instances = NTTRegistry.getAllInstances();
    instances.forEach((instance, id) => NTTObserver.unsubscribeAll(id));
    
    // Clear all registries
    NTTRegistry.clear();
  }

  // Batch operations
  static evolveBatch = NTTFunctional.evolveBatch.bind(NTTFunctional);
  static commitBatch = NTTFunctional.commitBatch.bind(NTTFunctional);
  static rollbackBatch = NTTFunctional.rollbackBatch.bind(NTTFunctional);
  static subscribeBatch = NTTObserver.subscribeBatch.bind(NTTObserver);
  static observePropertyBatch = NTTObserver.observePropertyBatch.bind(NTTObserver);
  static createBatch = NTTBroker.createBatch.bind(NTTBroker);
  static pullBatch = NTTBroker.pullBatch.bind(NTTBroker);

  // Utility/Query methods
  static isDirty = NTTFunctional.isDirty.bind(NTTFunctional);
  static isCommitting = NTTFunctional.isCommitting.bind(NTTFunctional);
  static getVersion = NTTFunctional.getVersion.bind(NTTFunctional);
  static compareStates = NTTFunctional.compareStates.bind(NTTFunctional);
  static validateState = NTTFunctional.validateState.bind(NTTFunctional);
  static findByState = NTTFunctional.findByState.bind(NTTFunctional);
  static getObservationStats = NTTObserver.getObservationStats.bind(NTTObserver);
  static findObservedInstances = NTTObserver.findObservedInstances.bind(NTTObserver);

  // Combined statistics
  static getStats() {
    const registryStats = NTTRegistry.getStats();
    const functionalStats = NTTFunctional.getStats();
    const observerStats = NTTObserver.getGlobalStats();
    const brokerStats = NTTBroker.getStats();

    return {
      registry: registryStats,
      functional: functionalStats,
      observer: observerStats,
      broker: brokerStats,
      combined: {
        totalInstances: registryStats.instances,
        healthScore: this.calculateHealthScore(functionalStats, observerStats),
        timestamp: Date.now()
      }
    };
  }

  static calculateHealthScore(functionalStats, observerStats) {
    // Simple health score calculation
    const { totalInstances, dirtyInstances, committingInstances } = functionalStats;
    const { totalSubscribers } = observerStats;
    
    if (totalInstances === 0) return 1.0;
    
    const cleanRatio = (totalInstances - dirtyInstances) / totalInstances;
    const activeRatio = Math.min(totalSubscribers / totalInstances, 1.0);
    const commitRatio = 1.0 - (committingInstances / totalInstances);
    
    return (cleanRatio * 0.4 + activeRatio * 0.3 + commitRatio * 0.3);
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
   * @param {string} instanceId - NTT instance ID
   * @returns {Object} Instance data
   */
  static access(instanceId) {
    const instance = NTTRegistry.getInstance(instanceId);
    return instance ? instance.data : null;
  }

  // Legacy alias methods for smooth migration if needed
  static set(instanceId, value) {
    console.warn('[NTT] set() is deprecated, use evolve() instead');
    return this.evolve(instanceId, value);
  }

  static update(instanceId, data) {
    console.warn('[NTT] update() is deprecated, use evolve() instead');
    return this.evolve(instanceId, data);
  }

  // ------------------ Advanced Features ------------------

  /**
   * Create a reactive computed property that updates automatically
   * @param {string} instanceId - NTT instance ID
   * @param {string} propertyName - Name of computed property
   * @param {Function} computeFn - Function to compute the value
   * @param {Array} dependencies - Array of property names to watch
   */
  static addComputedProperty(instanceId, propertyName, computeFn, dependencies = []) {
    const instance = NTTRegistry.getInstance(instanceId);
    if (!instance) {
      throw new Error(`No NTT instance found with id: ${instanceId}`);
    }

    // Store computed property definition
    if (!instance._meta.computedProperties) {
      instance._meta.computedProperties = new Map();
    }

    instance._meta.computedProperties.set(propertyName, {
      computeFn,
      dependencies,
      lastValue: undefined
    });

    // Compute initial value
    const initialValue = computeFn(instance.data);
    this.evolve(instanceId, { [propertyName]: initialValue });

    // Set up dependency watchers
    if (dependencies.length > 0) {
      this.observeProperties(instanceId, dependencies, () => {
        const newValue = computeFn(instance.data);
        const computed = instance._meta.computedProperties.get(propertyName);
        
        if (computed.lastValue !== newValue) {
          computed.lastValue = newValue;
          this.evolve(instanceId, { [propertyName]: newValue });
        }
      });
    }
  }

  /**
   * Remove a computed property
   * @param {string} instanceId - NTT instance ID
   * @param {string} propertyName - Name of computed property to remove
   */
  static removeComputedProperty(instanceId, propertyName) {
    const instance = NTTRegistry.getInstance(instanceId);
    if (!instance || !instance._meta.computedProperties) {
      return;
    }

    instance._meta.computedProperties.delete(propertyName);
    
    // Remove the property from data
    const newData = { ...instance.data };
    delete newData[propertyName];
    this.evolve(instanceId, newData);
  }

  /**
   * Create a derived NTT that stays in sync with a source NTT
   * @param {string} sourceInstanceId - Source NTT instance ID
   * @param {Object} options - Derivation options
   * @returns {NTT} Derived NTT instance
   */
  static derive(sourceInstanceId, options = {}) {
    const sourceInstance = NTTRegistry.getInstance(sourceInstanceId);
    if (!sourceInstance) {
      throw new Error(`Source instance not found: ${sourceInstanceId}`);
    }

    const {
      name = `${sourceInstance.name}_derived`,
      addr = `${sourceInstance.addr}/derived`,
      transform = (data) => data,
      filter = () => true
    } = options;

    // Create derived instance
    const derivedData = transform(sourceInstance.data);
    const derived = new NTT({
      name,
      addr,
      data: derivedData
    });

    // Keep derived in sync with source
    this.subscribe(sourceInstanceId, (newData, oldData) => {
      if (filter(newData, oldData)) {
        const transformedData = transform(newData);
        this.evolve(derived.id, transformedData);
      }
    });

    return derived;
  }
}

// Global exposure for backward compatibility
window.NTT = NTT;