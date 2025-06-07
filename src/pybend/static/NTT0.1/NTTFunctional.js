// NTTFunctional.js - Functional state management operations

import { NTTRegistry } from './NTTRegistry.js';
import { NTTBroker } from './NTTBroker.js';
import {
  getInstance,
  validateTransformation,
  applyTransformation,
  createOperation,
  notifyAllObservers,
  defaultConflictResolver,
  detectConflicts,
  deepEqual
} from './NTTUtils.js';

/**
 * Handles functional state management operations for NTT instances
 */
export class NTTFunctional {
  
  // ------------------ Core State Operations ------------------
  
  /**
   * Apply a pure transformation to an NTT instance
   * @param {string} instanceId - NTT instance ID
   * @param {Function|Object} transformation - Function or object to merge
   * @param {Object} metadata - Optional operation metadata
   * @returns {Object} The updated instance
   */
  static evolve(instanceId, transformation, metadata = {}) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    validateTransformation(transformation);

    const operation = createOperation('evolve', transformation, metadata, instance._meta.version);
    const newState = applyTransformation(instance._meta.localState, transformation);

    const oldData = { ...instance._data };
    instance._data = { ...newState };
    instance._meta.localState = { ...newState };
    instance._meta.pendingOps.push(operation);
    instance._meta.isDirty = true;
    instance._meta.version++;

    notifyAllObservers(instance, instance._data, oldData);
    
    return instance;
  }
  
  /**
   * Commit pending changes to the server for an NTT instance
   * @param {string} instanceId - NTT instance ID
   * @param {Object} options - Additional commit options
   * @returns {Promise<Object>} Promise resolving to the instance
   */
  static async commit(instanceId, options = {}) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    
    if (!instance._meta.isDirty || instance._meta.isCommitting) {
      return instance;
    }

    // Delegate to NTTBroker for actual API communication
    return await NTTBroker.push(instanceId, options);
  }
  
  /**
   * Discard pending changes and revert to remote state
   * @param {string} instanceId - NTT instance ID
   * @returns {Object} The instance
   */
  static rollback(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);

    if (!instance._meta.isDirty) {
      return instance;
    }

    const oldData = { ...instance._data };
    instance._data = { ...instance._meta.remoteState };
    instance._meta.localState = { ...instance._meta.remoteState };
    instance._meta.pendingOps = [];
    instance._meta.isDirty = false;

    notifyAllObservers(instance, instance._data, oldData);
    
    return instance;
  }
  
  // ------------------ Advanced State Operations ------------------
  
  /**
   * Merge with another NTT instance, resolving conflicts
   * @param {string} instanceId - Target NTT instance ID
   * @param {string} otherInstanceId - Source NTT instance ID
   * @param {Function} conflictResolver - Optional custom conflict resolver
   * @returns {Object} The merged instance
   */
  static merge(instanceId, otherInstanceId, conflictResolver = null) {
    const instances = NTTRegistry.getAllInstances();
    const instance = getInstance(instances, instanceId);
    const otherInstance = getInstance(instances, otherInstanceId, 'Other NTT instance not found');

    const resolver = conflictResolver || instance._meta.conflictResolver || defaultConflictResolver;
    const conflicts = detectConflicts(
      instance._meta.localState,
      instance._meta.remoteState,
      otherInstance._meta.localState
    );
    
    const mergedState = { ...instance._meta.localState };

    // Apply non-conflicting changes
    for (const [key, otherValue] of Object.entries(otherInstance._meta.localState)) {
      const remoteValue = instance._meta.remoteState[key];
      if (otherValue !== remoteValue && !conflicts.some(c => c.property === key)) {
        mergedState[key] = otherValue;
      }
    }

    // Resolve conflicts
    for (const conflict of conflicts) {
      const resolution = resolver(conflict, instance, otherInstance);
      mergedState[conflict.property] = resolution;
    }

    // Apply merged state using evolve
    this.evolve(instanceId, mergedState, { 
      mergeSource: otherInstanceId, 
      conflicts: conflicts.length,
      type: 'merge'
    });
    
    return instance;
  }
  
  /**
   * Create a snapshot of current state
   * @param {string} instanceId - NTT instance ID
   * @param {string} snapshotName - Optional snapshot name
   * @returns {Object} Snapshot object
   */
  static snapshot(instanceId, snapshotName = null) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    
    const snapshot = {
      id: snapshotName || `snapshot_${Date.now()}`,
      instanceId,
      timestamp: Date.now(),
      localState: { ...instance._meta.localState },
      remoteState: { ...instance._meta.remoteState },
      pendingOps: [...instance._meta.pendingOps],
      version: instance._meta.version,
      isDirty: instance._meta.isDirty
    };
    
    // Store snapshot in instance metadata
    if (!instance._meta.snapshots) {
      instance._meta.snapshots = [];
    }
    instance._meta.snapshots.push(snapshot);
    
    return snapshot;
  }
  
  /**
   * Restore from a snapshot
   * @param {string} instanceId - NTT instance ID
   * @param {string|Object} snapshotIdOrObject - Snapshot ID or snapshot object
   * @returns {Object} The restored instance
   */
  static restore(instanceId, snapshotIdOrObject) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    
    let snapshot;
    if (typeof snapshotIdOrObject === 'string') {
      snapshot = instance._meta.snapshots?.find(s => s.id === snapshotIdOrObject);
      if (!snapshot) {
        throw new Error(`Snapshot not found: ${snapshotIdOrObject}`);
      }
    } else {
      snapshot = snapshotIdOrObject;
    }
    
    const oldData = { ...instance._data };
    instance._data = { ...snapshot.localState };
    instance._meta.localState = { ...snapshot.localState };
    instance._meta.remoteState = { ...snapshot.remoteState };
    instance._meta.pendingOps = [...snapshot.pendingOps];
    instance._meta.version = snapshot.version;
    instance._meta.isDirty = snapshot.isDirty;
    
    notifyAllObservers(instance, instance._data, oldData);
    
    return instance;
  }
  
  // ------------------ Batch Operations ------------------
  
  /**
   * Apply the same transformation to multiple instances
   * @param {Array} instanceIds - Array of instance IDs
   * @param {Function|Object} transformation - Transformation to apply
   * @param {Object} metadata - Optional metadata
   * @returns {Array} Array of updated instances
   */
  static evolveBatch(instanceIds, transformation, metadata = {}) {
    return instanceIds.map(instanceId => {
      try {
        return this.evolve(instanceId, transformation, {
          ...metadata,
          batchOperation: true,
          batchId: metadata.batchId || `batch_${Date.now()}`
        });
      } catch (error) {
        console.error(`[NTTFunctional] Batch evolve failed for ${instanceId}:`, error);
        return null;
      }
    }).filter(Boolean);
  }
  
  /**
   * Commit multiple instances
   * @param {Array} instanceIds - Array of instance IDs
   * @param {Object} options - Commit options
   * @returns {Promise<Array>} Promise resolving to array of committed instances
   */
  static async commitBatch(instanceIds, options = {}) {
    const commitPromises = instanceIds.map(async instanceId => {
      try {
        return await this.commit(instanceId, {
          ...options,
          batchOperation: true
        });
      } catch (error) {
        console.error(`[NTTFunctional] Batch commit failed for ${instanceId}:`, error);
        return null;
      }
    });
    
    const results = await Promise.allSettled(commitPromises);
    return results
      .filter(result => result.status === 'fulfilled' && result.value)
      .map(result => result.value);
  }
  
  /**
   * Rollback multiple instances
   * @param {Array} instanceIds - Array of instance IDs
   * @returns {Array} Array of rolled back instances
   */
  static rollbackBatch(instanceIds) {
    return instanceIds.map(instanceId => {
      try {
        return this.rollback(instanceId);
      } catch (error) {
        console.error(`[NTTFunctional] Batch rollback failed for ${instanceId}:`, error);
        return null;
      }
    }).filter(Boolean);
  }
  
  // ------------------ Conflict Resolution ------------------
  
  /**
   * Set custom conflict resolver for an NTT instance
   * @param {string} instanceId - NTT instance ID
   * @param {Function} resolver - Conflict resolution function
   */
  static setConflictResolver(instanceId, resolver) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    
    if (typeof resolver !== 'function') {
      throw new TypeError('Conflict resolver must be a function');
    }
    
    instance._meta.conflictResolver = resolver;
  }
  
  /**
   * Get conflict resolver for an instance
   * @param {string} instanceId - NTT instance ID
   * @returns {Function} Conflict resolver function
   */
  static getConflictResolver(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    return instance._meta.conflictResolver || defaultConflictResolver;
  }
  
  // ------------------ State Queries ------------------
  
  /**
   * Check if instance has uncommitted changes
   * @param {string} instanceId - NTT instance ID
   * @returns {boolean} True if instance has uncommitted changes
   */
  static isDirty(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    return instance._meta.isDirty;
  }
  
  /**
   * Check if instance is currently committing
   * @param {string} instanceId - NTT instance ID
   * @returns {boolean} True if instance is committing
   */
  static isCommitting(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    return instance._meta.isCommitting;
  }
  
  /**
   * Get pending operations count
   * @param {string} instanceId - NTT instance ID
   * @returns {number} Number of pending operations
   */
  static getPendingOpsCount(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    return instance._meta.pendingOps.length;
  }
  
  /**
   * Get instance version
   * @param {string} instanceId - NTT instance ID
   * @returns {number} Current version number
   */
  static getVersion(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    return instance._meta.version;
  }
  
  /**
   * Compare local and remote states
   * @param {string} instanceId - NTT instance ID
   * @returns {Object} Comparison result with differences
   */
  static compareStates(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    const local = instance._meta.localState;
    const remote = instance._meta.remoteState;
    
    const differences = {};
    const allKeys = new Set([...Object.keys(local), ...Object.keys(remote)]);
    
    for (const key of allKeys) {
      if (!deepEqual(local[key], remote[key])) {
        differences[key] = {
          local: local[key],
          remote: remote[key],
          hasLocal: key in local,
          hasRemote: key in remote
        };
      }
    }
    
    return {
      isDifferent: Object.keys(differences).length > 0,
      differences,
      localOnly: Object.keys(local).filter(k => !(k in remote)),
      remoteOnly: Object.keys(remote).filter(k => !(k in local))
    };
  }
  
  // ------------------ Operation History ------------------
  
  /**
   * Get operation history for an instance
   * @param {string} instanceId - NTT instance ID
   * @param {number} limit - Maximum number of operations to return
   * @returns {Array} Array of operations
   */
  static getOperationHistory(instanceId, limit = 50) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    return instance._meta.pendingOps.slice(-limit);
  }
  
  /**
   * Clear operation history (keeping current state)
   * @param {string} instanceId - NTT instance ID
   * @param {boolean} keepPending - Whether to keep pending operations
   */
  static clearOperationHistory(instanceId, keepPending = true) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    
    if (keepPending) {
      // Keep only uncommitted operations
      instance._meta.pendingOps = instance._meta.pendingOps.filter(op => 
        op.version > (instance._meta.lastCommittedVersion || 0)
      );
    } else {
      instance._meta.pendingOps = [];
    }
  }
  
  // ------------------ Utility Methods ------------------
  
  /**
   * Get functional state statistics
   * @returns {Object} Statistics object
   */
  static getStats() {
    const instances = NTTRegistry.getAllInstances();
    let totalDirty = 0;
    let totalCommitting = 0;
    let totalPendingOps = 0;
    
    for (const instance of instances.values()) {
      if (instance._meta.isDirty) totalDirty++;
      if (instance._meta.isCommitting) totalCommitting++;
      totalPendingOps += instance._meta.pendingOps.length;
    }
    
    return {
      totalInstances: instances.size,
      dirtyInstances: totalDirty,
      committingInstances: totalCommitting,
      totalPendingOperations: totalPendingOps,
      averagePendingOps: instances.size > 0 ? totalPendingOps / instances.size : 0
    };
  }
  
  /**
   * Find instances by state criteria
   * @param {Object} criteria - Search criteria
   * @returns {Array} Array of [instanceId, instance] pairs
   */
  static findByState(criteria = {}) {
    const instances = NTTRegistry.getAllInstances();
    const results = [];
    
    for (const [id, instance] of instances.entries()) {
      let matches = true;
      
      if ('isDirty' in criteria && instance._meta.isDirty !== criteria.isDirty) {
        matches = false;
      }
      
      if ('isCommitting' in criteria && instance._meta.isCommitting !== criteria.isCommitting) {
        matches = false;
      }
      
      if ('minVersion' in criteria && instance._meta.version < criteria.minVersion) {
        matches = false;
      }
      
      if ('maxVersion' in criteria && instance._meta.version > criteria.maxVersion) {
        matches = false;
      }
      
      if ('hasPendingOps' in criteria) {
        const hasPending = instance._meta.pendingOps.length > 0;
        if (hasPending !== criteria.hasPendingOps) {
          matches = false;
        }
      }
      
      if (matches) {
        results.push([id, instance]);
      }
    }
    
    return results;
  }
  
  /**
   * Validate instance state integrity
   * @param {string} instanceId - NTT instance ID
   * @returns {Object} Validation result
   */
  static validateState(instanceId) {
    const instance = getInstance(NTTRegistry.getAllInstances(), instanceId);
    const issues = [];
    
    // Check if local and remote states are consistent with dirty flag
    const statesEqual = deepEqual(instance._meta.localState, instance._meta.remoteState);
    if (instance._meta.isDirty && statesEqual) {
      issues.push('Instance marked as dirty but local and remote states are identical');
    }
    if (!instance._meta.isDirty && !statesEqual) {
      issues.push('Instance not marked as dirty but local and remote states differ');
    }
    
    // Check if data is consistent with localState
    if (!deepEqual(instance._data, instance._meta.localState)) {
      issues.push('Instance data is not consistent with local state');
    }
    
    // Check version consistency
    if (instance._meta.version < 1) {
      issues.push('Invalid version number (must be >= 1)');
    }
    
    // Check pending operations
    if (instance._meta.pendingOps.length > 0 && !instance._meta.isDirty) {
      issues.push('Instance has pending operations but is not marked as dirty');
    }
    
    return {
      isValid: issues.length === 0,
      issues,
      state: {
        version: instance._meta.version,
        isDirty: instance._meta.isDirty,
        isCommitting: instance._meta.isCommitting,
        pendingOpsCount: instance._meta.pendingOps.length
      }
    };
  }
}