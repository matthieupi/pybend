import { NTTUtils } from './NTTUtils.js';
import { Event } from './Event.js';
import assert from "../utils/Assert.js";

const DEFAULT_API_URL = "http://localhost:8000";

/**
 * EntityRegistry manages NTT instances and factory configurations
 * Handles CRUD operations and instance lifecycle management
 */
export class EntityRegistry {
  static #registry = new Map();     // instanceId -> NTT instance

  /**
   * Register a factory configuration for creating NTT instances
   * @param {string} id - Model name/type
   * @param {string} url - API endpoint URL
   */
  static register(id, url = DEFAULT_API_URL) {
    assert(!EntityRegistry.#registry.has(id), `Id '${id}' is already registered in schema.`);
    assert(typeof url === 'string' && url.startsWith('http'), `Invalid URL: ${url}. Must be a valid HTTP URL.`);
    assert(typeof id === 'string' && id.length > 0, `ID must be a non-empty string.`);
    
    EntityRegistry.#registry.set(id, transport.schema(`${DEFAULT_API_URL}/${id}`))
  }
  
  static unregister(id) {
    assert(id, `Id must be provided for unregistration.`);
    assert(EntityRegistry.#registry.has(id), `Id '${id}' is not registered in schema.`);
    
    EntityRegistry.#registry.delete(id);
  }
  
 

  /**
   * Add NTT instance to registry
   * @param {Object} instance - NTT instance to register
   */
  static add(instance) {
    EntityRegistry.#registry.set(instance.id, instance);
  }

/**
 * Get NTT instance from registry with error handling
 * @param {Map} registry - Instance registry
 * @param {string} instanceId - Instance identifier
 * @param {string} errorMsg - Custom error message
 * @returns {Object} NTT instance
 * @throws {Error} If instance not found
 */
  static get(instanceId, errorMsg = 'Instance not found') {
    const instance = EntityRegistry.#registry.get(instanceId);
    if (!instance) {
      throw new Error(`${errorMsg}: ${instanceId}`);
    }
    return instance;
}

  /**
   * Clear all instances and factories
   */
  static clear() {
    EntityRegistry.#registry.clear();
  }

  /**
   * Discover API schemas and register prototypes
   * @param {string} url - Schema discovery endpoint
   */
  static discover(url) {
    const evt = new Event(
      'discover',
      NTTUtils.generateId(),
      'EntityRegistry',
      `${DEFAULT_API_URL}`,
      { url },
      { type: 'discover' }
    );
    
    evt.dispatch();
  }

}