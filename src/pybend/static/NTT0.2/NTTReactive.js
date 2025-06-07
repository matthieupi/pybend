import { EntityRegistry } from './EntityRegistry.js';

/**
 * NTTReactive provides reactive subscription capabilities
 * Handles subscribe, observe, and unsubscribe operations
 */
export class NTTReactive {

  /**
   * Subscribe to all changes on an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @param {Function} callback - Callback function (newData, oldData, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  static subscribe(instanceId, callback) {
    const instance = EntityRegistry._getInstance(instanceId);

    if (typeof callback !== 'function') {
      throw new TypeError('Callback must be a function');
    }

    instance._meta.subscribers.add(callback);
    
    return () => {
      instance._meta.subscribers.delete(callback);
    };
  }

  /**
   * Observe changes to a specific property on an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @param {string} property - Property name to observe
   * @param {Function} callback - Callback function (newValue, oldValue, property, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  static observe(instanceId, property, callback) {
    const instance = EntityRegistry._getInstance(instanceId);

    if (typeof property !== 'string') {
      throw new TypeError('Property must be a string');
    }
    if (typeof callback !== 'function') {
      throw new TypeError('Callback must be a function');
    }

    if (!instance._meta.propertyObservers.has(property)) {
      instance._meta.propertyObservers.set(property, new Set());
    }
    
    instance._meta.propertyObservers.get(property).add(callback);
    
    return () => {
      const observers = instance._meta.propertyObservers.get(property);
      if (observers) {
        observers.delete(callback);
        if (observers.size === 0) {
          instance._meta.propertyObservers.delete(property);
        }
      }
    };
  }

  /**
   * Unsubscribe all observers from an NTT instance
   * @param {string} instanceId - NTT instance identifier
   */
  static unsubscribeAll(instanceId) {
    const instance = EntityRegistry._getInstance(instanceId);

    instance._meta.subscribers.clear();
    instance._meta.propertyObservers.clear();
  }
}