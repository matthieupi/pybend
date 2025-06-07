// NTTRegistry.js - Shared state management for all NTT components

/**
 * Centralized registry for NTT instances and configurations
 * Prevents circular dependencies between NTT components
 */
export class NTTRegistry {
  // Instance storage
  static #instances = new Map();        // instanceId -> NTT instance
  static #descriptors = new Map();      // descriptorId -> descriptor config
  static #prototypes = new Map();       // url -> prototype schema
  static #subclasses = new Map();       // url -> generated subclass
  
  // ------------------ Instance Management ------------------
  
  /**
   * Register an NTT instance
   * @param {string} instanceId - Unique instance identifier
   * @param {Object} instance - NTT instance
   */
  static setInstance(instanceId, instance) {
    this.#instances.set(instanceId, instance);
  }
  
  /**
   * Get an NTT instance by ID
   * @param {string} instanceId - Instance identifier
   * @returns {Object|null} NTT instance or null
   */
  static getInstance(instanceId) {
    return this.#instances.get(instanceId) || null;
  }
  
  /**
   * Remove an NTT instance
   * @param {string} instanceId - Instance identifier
   * @returns {boolean} True if instance was removed
   */
  static removeInstance(instanceId) {
    return this.#instances.delete(instanceId);
  }
  
  /**
   * Get all registered instances
   * @returns {Map} Copy of instances map
   */
  static getAllInstances() {
    return new Map(this.#instances);
  }
  
  /**
   * Check if instance exists
   * @param {string} instanceId - Instance identifier
   * @returns {boolean} True if instance exists
   */
  static hasInstance(instanceId) {
    return this.#instances.has(instanceId);
  }
  
  // ------------------ Descriptor Management ------------------
  
  /**
   * Register a descriptor configuration
   * @param {string} descriptorId - Unique descriptor identifier
   * @param {Object} config - Descriptor configuration
   */
  static setDescriptor(descriptorId, config) {
    this.#descriptors.set(descriptorId, config);
  }
  
  /**
   * Get a descriptor configuration
   * @param {string} descriptorId - Descriptor identifier
   * @returns {Object|null} Descriptor config or null
   */
  static getDescriptor(descriptorId) {
    return this.#descriptors.get(descriptorId) || null;
  }
  
  /**
   * Remove a descriptor
   * @param {string} descriptorId - Descriptor identifier
   * @returns {boolean} True if descriptor was removed
   */
  static removeDescriptor(descriptorId) {
    return this.#descriptors.delete(descriptorId);
  }
  
  /**
   * Get all descriptors
   * @returns {Map} Copy of descriptors map
   */
  static getAllDescriptors() {
    return new Map(this.#descriptors);
  }
  
  // ------------------ Prototype Management ------------------
  
  /**
   * Register a prototype schema
   * @param {string} url - Schema URL
   * @param {Object} schema - JSON schema
   */
  static setPrototype(url, schema) {
    this.#prototypes.set(url, schema);
  }
  
  /**
   * Get a prototype schema
   * @param {string} url - Schema URL
   * @returns {Object|null} Schema or null
   */
  static getPrototype(url) {
    return this.#prototypes.get(url) || null;
  }
  
  /**
   * Check if prototype exists
   * @param {string} url - Schema URL
   * @returns {boolean} True if prototype exists
   */
  static hasPrototype(url) {
    return this.#prototypes.has(url);
  }
  
  // ------------------ Subclass Management ------------------
  
  /**
   * Register a generated subclass
   * @param {string} url - Schema URL
   * @param {Function} SubClass - Generated subclass
   */
  static setSubclass(url, SubClass) {
    this.#subclasses.set(url, SubClass);
  }
  
  /**
   * Get a generated subclass
   * @param {string} url - Schema URL
   * @returns {Function|null} Subclass or null
   */
  static getSubclass(url) {
    return this.#subclasses.get(url) || null;
  }
  
  /**
   * Check if subclass exists
   * @param {string} url - Schema URL
   * @returns {boolean} True if subclass exists
   */
  static hasSubclass(url) {
    return this.#subclasses.has(url);
  }
  
  // ------------------ Bulk Operations ------------------
  
  /**
   * Clear all instances
   */
  static clearInstances() {
    this.#instances.clear();
  }
  
  /**
   * Clear all descriptors
   */
  static clearDescriptors() {
    this.#descriptors.clear();
  }
  
  /**
   * Clear all prototypes and subclasses
   */
  static clearSchemas() {
    this.#prototypes.clear();
    this.#subclasses.clear();
  }
  
  /**
   * Clear everything
   */
  static clear() {
    this.clearInstances();
    this.clearDescriptors();
    this.clearSchemas();
  }
  
  // ------------------ Utility Methods ------------------
  
  /**
   * Get registry statistics
   * @returns {Object} Statistics object
   */
  static getStats() {
    return {
      instances: this.#instances.size,
      descriptors: this.#descriptors.size,
      prototypes: this.#prototypes.size,
      subclasses: this.#subclasses.size
    };
  }
  
  /**
   * Find instances by criteria
   * @param {Function} predicate - Filter function
   * @returns {Array} Array of [instanceId, instance] pairs
   */
  static findInstances(predicate) {
    const results = [];
    for (const [id, instance] of this.#instances.entries()) {
      if (predicate(instance, id)) {
        results.push([id, instance]);
      }
    }
    return results;
  }
  
  /**
   * Find descriptor for instance based on URL matching
   * @param {Object} instance - NTT instance
   * @returns {Object|null} Matching descriptor or null
   */
  static findDescriptorForInstance(instance) {
    if (!instance.addr) return null;
    
    for (const [descriptorId, descriptor] of this.#descriptors.entries()) {
      if (instance.addr.includes(descriptor.url)) {
        return descriptor;
      }
    }
    return null;
  }
}