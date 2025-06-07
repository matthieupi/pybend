import { NTTUtils } from './NTTUtils.js';
import { EntityRegistry } from './EntityRegistry.js';
import { Event } from './Event.js';

/**
 * NTTFunctional provides functional state management operations
 * Handles evolve, commit, rollback, merge, and pull operations
 */
export class NTTFunctional {

  /**
   * Apply a pure transformation to an NTT instance's state
   * @param {string} instanceId - NTT instance identifier
   * @param {Function|Object} transformation - Function or object to merge
   * @param {Object} metadata - Optional operation metadata
   * @returns {Object} The updated NTT instance
   */
  static evolve(instanceId, transformation, metadata = {}) {
    const instance = EntityRegistry._getInstance(instanceId);

    const operation = NTTUtils.createOperation('evolve', transformation, metadata, instance._meta.version);
    
    let newState;
    if (typeof transformation === 'function') {
      newState = transformation(instance.data);
    } else if (typeof transformation === 'object') {
      newState = { ...instance.data, ...transformation };
    } else {
      throw new TypeError('Transformation must be a function or object');
    }

    if (typeof newState !== 'object') {
      throw new Error('Transformation must return an object');
    }

    const oldData = { ...instance.data };
    instance._data = { ...newState };
    instance._meta.pendingOps.push(operation);
    instance._meta.isDirty = true;
    instance._meta.version++;
    instance._meta.hash = NTTUtils.simpleHash(instance._data);

    NTTUtils.notifySubscribers(instance, oldData, instance._data);
    
    return instance;
  }

  /**
   * Commit pending changes to the server for an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @returns {Promise<Object>} Promise resolving to the NTT instance
   */
  static async commit(instanceId) {
    const instance = EntityRegistry._getInstance(instanceId);

    if (!instance._meta.isDirty || instance._meta.isCommitting) {
      return instance;
    }

    instance._meta.isCommitting = true;

    try {
      // Find associated factory for API communication
      let factory = null;
      for (const [factoryId, factoryConfig] of EntityRegistry.getAllInstances()) {
        if (instance.addr.includes(factoryConfig.url)) {
          factory = factoryConfig;
          break;
        }
      }

      const evt = new Event(
        'update',
        NTTUtils.generateId(),
        instanceId,
        'api',
        instance.data, // Only send the actual data
        { 
          instanceId,
          url: instance.addr,
          version: instance._meta.version
        }
      );

      evt.dispatch();

      // Return promise that resolves when commit is complete
      // Note: In a real implementation, this would be handled by the event system
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          instance._meta.isCommitting = false;
          reject(new Error('Commit timeout'));
        }, 5000);

        // This would be called by the event handler when response comes back
        instance._meta.commitResolver = (response, error) => {
          clearTimeout(timeout);
          instance._meta.isCommitting = false;
          
          if (error) {
            reject(error);
          } else {
            // Successful commit - update remote state
            instance._meta.remoteState = { ...response };
            instance._data = { ...response };
            instance._meta.pendingOps = [];
            instance._meta.isDirty = false;
            instance._meta.hash = NTTUtils.simpleHash(instance._data);
            
            resolve(instance);
          }
        };
      });
    } catch (error) {
      instance._meta.isCommitting = false;
      throw error;
    }
  }

  /**
   * Discard pending changes and revert to remote state
   * @param {string} instanceId - NTT instance identifier
   * @returns {Object} The NTT instance
   */
  static rollback(instanceId) {
    const instance = EntityRegistry._getInstance(instanceId);

    if (!instance._meta.isDirty) {
      return instance;
    }

    const oldData = { ...instance.data };
    instance._data = { ...instance._meta.remoteState };
    instance._meta.pendingOps = [];
    instance._meta.isDirty = false;
    instance._meta.hash = NTTUtils.simpleHash(instance._data);

    NTTUtils.notifySubscribers(instance, oldData, instance._data);
    
    return instance;
  }

  /**
   * Merge with another NTT instance, resolving conflicts
   * @param {string} instanceId - Target NTT instance identifier
   * @param {string} otherInstanceId - Source NTT instance identifier
   * @param {Function} conflictResolver - Optional custom conflict resolver
   * @returns {Object} The merged NTT instance
   */
  static merge(instanceId, otherInstanceId, conflictResolver = null) {
    const instance = EntityRegistry._getInstance(instanceId);
    const otherInstance = EntityRegistry._getInstance(otherInstanceId);

    const resolver = conflictResolver || instance._meta.conflictResolver || NTTUtils.defaultConflictResolver;
    const conflicts = [];
    const mergedState = { ...instance.data };

    // Detect conflicts
    for (const [key, otherValue] of Object.entries(otherInstance.data)) {
      const localValue = instance.data[key];
      const remoteValue = instance._meta.remoteState[key];
      
      if (localValue !== remoteValue && localValue !== otherValue && remoteValue !== otherValue) {
        conflicts.push({
          property: key,
          localValue,
          remoteValue,
          otherValue
        });
      } else if (otherValue !== remoteValue) {
        mergedState[key] = otherValue;
      }
    }

    // Resolve conflicts
    for (const conflict of conflicts) {
      const resolution = resolver(conflict, instance, otherInstance);
      mergedState[conflict.property] = resolution;
    }

    // Apply merged state
    NTTFunctional.evolve(instanceId, mergedState, { 
      mergeSource: otherInstanceId, 
      conflicts: conflicts.length 
    });
    
    return instance;
  }

  /**
   * Pull/refresh data for an NTT instance from server
   * @param {string} instanceId - NTT instance identifier
   */
  static pull(instanceId) {
    const instance = EntityRegistry._getInstance(instanceId);

    const evt = new Event(
        'load',
        NTTUtils.generateId(),
        instanceId,
        instance.href
    );
    
    evt.dispatch();
  }

  /**
   * Set custom conflict resolver for an NTT instance
   * @param {string} instanceId - NTT instance identifier
   * @param {Function} resolver - Conflict resolution function
   */
  static setConflictResolver(instanceId, resolver) {
    const instance = EntityRegistry._getInstance(instanceId);

    if (typeof resolver !== 'function') {
      throw new TypeError('Conflict resolver must be a function');
    }
    
    instance._meta.conflictResolver = resolver;
  }
}