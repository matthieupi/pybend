// NTTObserver.js - Reactive subscriptions and event handling

import { NTTRegistry } from './NTTRegistry.js';
import { getInstance, validateCallback, validateString } from './NTTUtils.js';

/**
 * Handles reactive subscriptions and observations for NTT instances
 */
export class NTTObserver {
  
  // ------------------ Subscription Management ------------------
  
  /**
   * Subscribe to all changes on an NTT instance
   * @param {string} instanceId - NTT instance ID
   * @param {Function} callback - Callback function (newData, oldData, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  static subscribe(instanceId, callback) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    validateCallback(callback);

    instance._meta.subscribers.add(callback);
    
    console.log(`[NTTObserver] Subscribed to instance: ${instanceId}`);
    
    return () => {
      instance._meta.subscribers.delete(callback);
      console.log(`[NTTObserver] Unsubscribed from instance: ${instanceId}`);
    };
  }

  /**
   * Observe changes to a specific property on an NTT instance
   * @param {string} instanceId - NTT instance ID
   * @param {string} property - Property name to observe
   * @param {Function} callback - Callback function (newValue, oldValue, property, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  static observe(instanceId, property, callback) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    validateString(property, 'property');
    validateCallback(callback);

    if (!instance._meta.propertyObservers.has(property)) {
      instance._meta.propertyObservers.set(property, new Set());
    }
    
    instance._meta.propertyObservers.get(property).add(callback);
    
    console.log(`[NTTObserver] Observing property '${property}' on instance: ${instanceId}`);
    
    return () => {
      const observers = instance._meta.propertyObservers.get(property);
      if (observers) {
        observers.delete(callback);
        if (observers.size === 0) {
          instance._meta.propertyObservers.delete(property);
        }
      }
      console.log(`[NTTObserver] Stopped observing property '${property}' on instance: ${instanceId}`);
    };
  }

  /**
   * Observe multiple properties with a single callback
   * @param {string} instanceId - NTT instance ID
   * @param {Array} properties - Array of property names to observe
   * @param {Function} callback - Callback function (changes, ntt) => void
   * @returns {Function} Unsubscribe function for all properties
   */
  static observeProperties(instanceId, properties, callback) {
    validateCallback(callback);
    
    const unsubscribeFunctions = properties.map(property => {
      return this.observe(instanceId, property, (newValue, oldValue, prop, ntt) => {
        callback({ [prop]: { newValue, oldValue, property: prop } }, ntt);
      });
    });
    
    return () => {
      unsubscribeFunctions.forEach(unsub => unsub());
    };
  }

  /**
   * Unsubscribe all observers from an NTT instance
   * @param {string} instanceId - NTT instance ID
   */
  static unsubscribeAll(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    
    const subscriberCount = instance._meta.subscribers.size;
    const propertyObserverCount = instance._meta.propertyObservers.size;
    
    instance._meta.subscribers.clear();
    instance._meta.propertyObservers.clear();
    
    console.log(`[NTTObserver] Unsubscribed all observers from ${instanceId}: ${subscriberCount} general, ${propertyObserverCount} property observers`);
  }

  // ------------------ Advanced Observation Patterns ------------------

  /**
   * Observe state transitions (dirty -> clean, clean -> dirty)
   * @param {string} instanceId - NTT instance ID
   * @param {Function} callback - Callback function (transition, ntt) => void
   * @returns {Function} Unsubscribe function
   */
  static observeStateTransitions(instanceId, callback) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    validateCallback(callback);
    
    let lastDirtyState = instance._meta.isDirty;
    let lastCommittingState = instance._meta.isCommitting;
    
    return this.subscribe(instanceId, (newData, oldData, ntt) => {
      const currentDirtyState = ntt._meta.isDirty;
      const currentCommittingState = ntt._meta.isCommitting;
      
      // Detect dirty state transitions
      if (lastDirtyState !== currentDirtyState) {
        callback({
          type: 'dirty',
          from: lastDirtyState,
          to: currentDirtyState,
          timestamp: Date.now()
        }, ntt);
        lastDirtyState = currentDirtyState;
      }
      
      // Detect committing state transitions
      if (lastCommittingState !== currentCommittingState) {
        callback({
          type: 'committing',
          from: lastCommittingState,
          to: currentCommittingState,
          timestamp: Date.now()
        }, ntt);
        lastCommittingState = currentCommittingState;
      }
    });
  }

  /**
   * Observe when specific conditions are met
   * @param {string} instanceId - NTT instance ID
   * @param {Function} condition - Condition function (ntt) => boolean
   * @param {Function} callback - Callback function (ntt) => void
   * @param {Object} options - Options {once: boolean, immediate: boolean}
   * @returns {Function} Unsubscribe function
   */
  static observeCondition(instanceId, condition, callback, options = {}) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    validateCallback(condition, 'condition');
    validateCallback(callback);
    
    const { once = false, immediate = false } = options;
    let hasTriggered = false;
    
    // Check immediately if requested
    if (immediate && condition(instance)) {
      callback(instance);
      if (once) return () => {}; // No need to subscribe
      hasTriggered = true;
    }
    
    return this.subscribe(instanceId, (newData, oldData, ntt) => {
      if (once && hasTriggered) return;
      
      if (condition(ntt)) {
        callback(ntt);
        if (once) hasTriggered = true;
      }
    });
  }

  /**
   * Debounce observations to prevent excessive callback calls
   * @param {string} instanceId - NTT instance ID
   * @param {Function} callback - Callback function
   * @param {number} delay - Debounce delay in milliseconds
   * @returns {Function} Unsubscribe function
   */
  static observeDebounced(instanceId, callback, delay = 300) {
    validateCallback(callback);
    
    let timeoutId = null;
    
    const unsubscribe = this.subscribe(instanceId, (newData, oldData, ntt) => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      
      timeoutId = setTimeout(() => {
        callback(newData, oldData, ntt);
        timeoutId = null;
      }, delay);
    });
    
    // Return enhanced unsubscribe that also clears timeout
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      unsubscribe();
    };
  }

  /**
   * Throttle observations to limit callback frequency
   * @param {string} instanceId - NTT instance ID
   * @param {Function} callback - Callback function
   * @param {number} interval - Throttle interval in milliseconds
   * @returns {Function} Unsubscribe function
   */
  static observeThrottled(instanceId, callback, interval = 100) {
    validateCallback(callback);
    
    let lastCall = 0;
    let timeoutId = null;
    let lastArgs = null;
    
    const unsubscribe = this.subscribe(instanceId, (newData, oldData, ntt) => {
      const now = Date.now();
      lastArgs = [newData, oldData, ntt];
      
      if (now - lastCall >= interval) {
        callback(...lastArgs);
        lastCall = now;
      } else if (!timeoutId) {
        timeoutId = setTimeout(() => {
          callback(...lastArgs);
          lastCall = Date.now();
          timeoutId = null;
        }, interval - (now - lastCall));
      }
    });
    
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      unsubscribe();
    };
  }

  // ------------------ Batch Observations ------------------

  /**
   * Subscribe to multiple instances with a single callback
   * @param {Array} instanceIds - Array of instance IDs
   * @param {Function} callback - Callback function (instanceId, newData, oldData, ntt) => void
   * @returns {Function} Unsubscribe function for all instances
   */
  static subscribeBatch(instanceIds, callback) {
    validateCallback(callback);
    
    const unsubscribeFunctions = instanceIds.map(instanceId => {
      return this.subscribe(instanceId, (newData, oldData, ntt) => {
        callback(instanceId, newData, oldData, ntt);
      });
    });
    
    return () => {
      unsubscribeFunctions.forEach(unsub => unsub());
    };
  }

  /**
   * Observe the same property across multiple instances
   * @param {Array} instanceIds - Array of instance IDs
   * @param {string} property - Property to observe
   * @param {Function} callback - Callback function (instanceId, newValue, oldValue, property, ntt) => void
   * @returns {Function} Unsubscribe function for all observations
   */
  static observePropertyBatch(instanceIds, property, callback) {
    validateString(property, 'property');
    validateCallback(callback);
    
    const unsubscribeFunctions = instanceIds.map(instanceId => {
      return this.observe(instanceId, property, (newValue, oldValue, prop, ntt) => {
        callback(instanceId, newValue, oldValue, prop, ntt);
      });
    });
    
    return () => {
      unsubscribeFunctions.forEach(unsub => unsub());
    };
  }

  // ------------------ Event Aggregation ------------------

  /**
   * Aggregate events from multiple instances
   * @param {Array} instanceIds - Array of instance IDs
   * @param {Function} aggregator - Aggregation function (events) => aggregatedResult
   * @param {Function} callback - Callback function (aggregatedResult) => void
   * @param {number} windowSize - Time window for aggregation in milliseconds
   * @returns {Function} Unsubscribe function
   */
  static aggregateEvents(instanceIds, aggregator, callback, windowSize = 1000) {
    validateCallback(aggregator, 'aggregator');
    validateCallback(callback);
    
    const events = [];
    let timeoutId = null;
    
    const processEvents = () => {
      if (events.length > 0) {
        const result = aggregator([...events]);
        callback(result);
        events.length = 0; // Clear events
      }
      timeoutId = null;
    };
    
    const unsubscribe = this.subscribeBatch(instanceIds, (instanceId, newData, oldData, ntt) => {
      events.push({
        instanceId,
        newData,
        oldData,
        ntt,
        timestamp: Date.now()
      });
      
      if (!timeoutId) {
        timeoutId = setTimeout(processEvents, windowSize);
      }
    });
    
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      unsubscribe();
    };
  }

  // ------------------ Utility Methods ------------------

  /**
   * Get observation statistics for an instance
   * @param {string} instanceId - NTT instance ID
   * @returns {Object} Statistics object
   */
  static getObservationStats(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    
    let totalPropertyObservers = 0;
    const propertyObserverCounts = {};
    
    for (const [property, observers] of instance._meta.propertyObservers.entries()) {
      const count = observers.size;
      propertyObserverCounts[property] = count;
      totalPropertyObservers += count;
    }
    
    return {
      instanceId,
      subscribers: instance._meta.subscribers.size,
      propertyObservers: totalPropertyObservers,
      observedProperties: instance._meta.propertyObservers.size,
      propertyObserverCounts
    };
  }

  /**
   * Get global observation statistics
   * @returns {Object} Global statistics
   */
  static getGlobalStats() {
    const instances = NTTRegistry.getAllInstances();
    let totalSubscribers = 0;
    let totalPropertyObservers = 0;
    let totalObservedProperties = 0;
    
    for (const instance of instances.values()) {
      totalSubscribers += instance._meta.subscribers.size;
      totalObservedProperties += instance._meta.propertyObservers.size;
      
      for (const observers of instance._meta.propertyObservers.values()) {
        totalPropertyObservers += observers.size;
      }
    }
    
    return {
      totalInstances: instances.size,
      totalSubscribers,
      totalPropertyObservers,
      totalObservedProperties,
      averageSubscribersPerInstance: instances.size > 0 ? totalSubscribers / instances.size : 0,
      averagePropertyObserversPerInstance: instances.size > 0 ? totalPropertyObservers / instances.size : 0
    };
  }

  /**
   * Find instances with active observations
   * @param {Object} criteria - Search criteria
   * @returns {Array} Array of [instanceId, stats] pairs
   */
  static findObservedInstances(criteria = {}) {
    const instances = NTTRegistry.getAllInstances();
    const results = [];
    
    for (const [instanceId, instance] of instances.entries()) {
      const stats = this.getObservationStats(instanceId);
      let matches = true;
      
      if ('hasSubscribers' in criteria && (stats.subscribers > 0) !== criteria.hasSubscribers) {
        matches = false;
      }
      
      if ('hasPropertyObservers' in criteria && (stats.propertyObservers > 0) !== criteria.hasPropertyObservers) {
        matches = false;
      }
      
      if ('minSubscribers' in criteria && stats.subscribers < criteria.minSubscribers) {
        matches = false;
      }
      
      if ('minPropertyObservers' in criteria && stats.propertyObservers < criteria.minPropertyObservers) {
        matches = false;
      }
      
      if (matches) {
        results.push([instanceId, stats]);
      }
    }
    
    return results;
  }

  /**
   * Test if a callback is properly subscribed to an instance
   * @param {string} instanceId - NTT instance ID
   * @param {Function} callback - Callback function to test
   * @returns {Object} Test result
   */
  static testSubscription(instanceId, callback) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    
    const isSubscribed = instance._meta.subscribers.has(callback);
    const propertySubscriptions = [];
    
    for (const [property, observers] of instance._meta.propertyObservers.entries()) {
      if (observers.has(callback)) {
        propertySubscriptions.push(property);
      }
    }
    
    return {
      isGeneralSubscriber: isSubscribed,
      propertySubscriptions,
      hasAnySubscription: isSubscribed || propertySubscriptions.length > 0
    };
  }
}