import { Utils } from './Utils.js';
import assert from "../utils/Assert.js";
import { remote } from './Remote.js';
import { config } from '../config.js';

const DEFAULT_API_URL = config.API_URL

/**
 * Manages a registry of key value pairs linked with callbacks
 *
 * The registry handles fetching and updating data from a remote server and provides
 * a backbone for state management.
 * Handles CRUD operations and instance lifecycle management
 */
export class Registry {
  static #registry = new Map();     // key -> NTT instance
  static #callbacks = new Map(); // key -> callback for this address
  static #prototypes = new Map(); // key -> connection info
  static #remote = remote; // Remote instance for API communication

  /**
   * Register a factory configuration for creating NTT instances
   * @param {string} key - Enbdpoint key
   * @param {string} href - API endpoint URL
   */
  static register(key, callback, href="") {
    //assert(this, !Registry.#registry.has(key), `KEY '${key}': is already registered in schema.`);
    //assert(this, typeof href === 'string' && href.startsWith('http') || href === "local",
    //    `Invalid URL: ${href}. Must be a valid HTTP URL.`);
    assert(this, typeof key === 'string' && key.length > 0, `ID must be a non-empty string.`);
    assert(this, typeof callback === 'function', `Callback must be a function, got ${typeof callback}.`);
    console.info(`[Registry] Registering key: ${key} with callback: ${typeof callback}`)
    // Add new callback to list of callbacks
    let callbacks = Registry.#callbacks.get(key) || [];
    callbacks.push(callback);
    Registry.#callbacks.set(key, callbacks);
    // Callback with record if it exist
    if (Registry.#registry.has(key) && Registry.#registry.get(key) !== undefined) {
      console.info(`[Registry] Key ${key} already exists, calling back with existing instance.`);
      console.info(`[Registry] Current instance:`, Registry.#registry.get(key));
      callback(Registry.get(key));
    } else {
      // If not, register to registry and pull data from remote
      Registry.#registry.set(key, undefined)
      Registry.pull(key)
    }
  }
  
  
  
  /**
   * Unregister a factory configuration by ID
   * @param {string} key - Key of the factory configuration to unregister
   */
  static unregister(key) {
    assert(this, key, `Id must be provided for unregistration.`);
    assert(this, Registry.#registry.has(key), `Id '${key}' is not registered in schema.`);
    Registry.#registry.delete(key);
  }
  
  /**
   * Add NTT instance to registry
   * @param {Object} instance - NTT instance to register
   */
  static add(instance) {
    assert(this,
        instance && instance.key,
        `Instance must have a key property.`);
    assert(this,
        !Registry.#registry.has(instance.key),
        `Registry: Adding instance with key '${instance.key}' is already registered.`)
    Registry.#registry.set(instance.key, instance);
  }
  
  /**
   * Update callback for remote
   * @param key
   * @param data
   */
  static update(key, data = null) {
    assert(this,
        data && key,
        `Instance must have a data and key property. Got ${key} : ${data}`);
    Registry.#registry.set(key, data);
    // Notify observers of the update
    
    const callbacks = Registry.#callbacks.get(key) || [];
    const oldData = Registry.#registry.get(key);
    console.warn("Calling back", key, callbacks)
    if (![]){
      console.warn(`[Registry] on Update: No observers registered for key: ${data.key}`);
    }
    callbacks.forEach(callback => {
      try {
        console.info(`[Registry] Calling observer for key: ${key} with data:`, data, "and oldData:", oldData);
        callback(data, oldData);
      } catch (error) {
        console.error(`[Registry] Observer error for ${data.key}:`, error);
      }
    });
  }
  
  /**
   * Has key in registry
   * @param {string} key - Instance identifier
   * @param {string} errorMsg - Custom error message
   * @return {Object} NTT instancef
   */
    static has(key, errorMsg = 'Instance not found') {
    assert(this, key && typeof key === 'string',
        `Key must be a non-empty string.`);
    return Registry.#registry.has(key);
  }

  /**
   * Get NTT instance from registry with error handling
   * @param {string} key - Instance identifier
   * @param {string} errorMsg - Custom error message
   * @returns {Object} NTT instance
   * @throws {Error} If instance not found
   */
  static get(key, errorMsg = 'Instance not found') {
    assert(this, key && Registry.#registry.has(key),
        `Trying to get instance with key '${key}': does not exist in registry.`)
    const instance = Registry.#registry.get(key);
    if (!instance) {
      throw new Error(`${errorMsg}: ${key}`);
    }
    return instance;
}
  
  /**
   * Pull data from remote server for a specific key
   * @param key
   * @param remote
   */
  static pull(key, remote=Registry.#remote) {
    assert(this, remote && remote.pull, `Remote must have a pull method.`);
    assert(this, typeof key === 'string' && key.length > 0, `Key must be a non-empty string.`);
    assert(this, typeof remote.pull === 'function', `Remote pull must be a function, got ${typeof remote.pull}.`);
    assert(this, Registry.#callbacks.has(key), `Trying to pull with no callback registered for key: ${key}.`);
    remote.pull(`${config.API_URL}/${key}`, this.update.bind(this, key))
  }
  
  /**
   * Observe changes to a specific key in the registry
   * @param {string} key - NTT instance ID
   * @param {Function} callback - Callback function (newValue, oldValue, property, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  static observe(key, callback) {
    assert(this, !!callback,
        `Callback must be provided for observing instance ${key}.`);
    assert(this, typeof callback === 'function',
        `Callback must be a function, got ${typeof callback}.`);
    assert(this, key && Registry.#registry.has(key),
        `Trying to observe instance with key '${key}';\nDoes not exist in registry.`);
  
    return Registry.unobserve.bind(this, key, callback);
  }
  
   /**
   * Remove an observer on a key
   * @param {string} key - NTT instance ID
   * @param {Function} callback - Callback function (newValue, oldValue, property, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  static unobserve(key, callback) {
    assert(this,
        key && Registry.#registry.has(key),
        `Trying to unobserve instance with key '${key}';\nDoes not exist in registry.`);
    assert(this,
        !!callback,
        `Callback must be provided for unobserving instance ${key}.`);
    assert(this,
        typeof callback === 'function',
        `Callback must be a function, got ${typeof callback}.`);
    
    let callbacks = Registry.#callbacks.get(key) || [];
    callbacks = callbacks.filter(cb => cb !== callback);
    Registry.#callbacks.set(key, callbacks);
  }
  
  /**
   * Clear all instances and factories
   */
  static clear() {
    Registry.#registry.clear();
    Registry.#callbacks.clear();
  }

}

window.Registry = Registry;