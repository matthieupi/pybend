// NTTBroker.js - API communication and backend integration

import { Event } from './Event.js';
import { transport } from './TransportManager.js';
import { NTTRegistry } from './NTTRegistry.js';
import { generateId } from './NTTUtils.js';

const DEFAULT_API_URL = "http://localhost:8000/api/";

/**
 * Handles all API communication and backend integration for NTT instances
 */
export class NTTBroker {
  
  // ------------------ Descriptor Management ------------------
  
  /**
   * Register a descriptor configuration for NTT instances
   * @param {string} id - Unique identifier for the descriptor
   * @param {string} model - Model name/type
   * @param {Function} onSuccess - Success callback
   * @param {Function} onError - Error callback  
   * @param {string} url - API endpoint URL
   */
  static register(id, model, onSuccess, onError, url = DEFAULT_API_URL) {
    const descriptor = {
      id,
      url,
      model,
      onSuccess: onSuccess || (() => {}),
      onError: onError || ((err) => console.error('[NTTBroker]', err))
    };
    
    NTTRegistry.setDescriptor(id, descriptor);
    console.log(`[NTTBroker] Registered descriptor: ${id} -> ${url}`);
  }
  
  /**
   * Unregister a descriptor
   * @param {string} id - Descriptor identifier
   * @returns {boolean} True if descriptor was removed
   */
  static unregister(id) {
    const removed = NTTRegistry.removeDescriptor(id);
    if (removed) {
      console.log(`[NTTBroker] Unregistered descriptor: ${id}`);
    }
    return removed;
  }
  
  /**
   * Get all registered descriptors
   * @returns {Map} Copy of descriptors map
   */
  static getDescriptors() {
    return NTTRegistry.getAllDescriptors();
  }
  
  // ------------------ Instance Creation ------------------
  
  /**
   * Create a new NTT instance via API
   * @param {string} descriptorId - Descriptor identifier
   * @param {Object} data - Data to create
   * @param {Object} options - Additional options
   */
  static create(descriptorId, data, options = {}) {
    const descriptor = NTTRegistry.getDescriptor(descriptorId);
    if (!descriptor) {
      throw new Error(`[NTTBroker] No descriptor registered for id: ${descriptorId}`);
    }

    const eventData = {
      url: descriptor.url,
      data,
      ...options,
      onSuccess: (response) => {
        try {
          // Import NTT dynamically to avoid circular dependency
          import('./NTT.js').then(({ NTT }) => {
            const ntt = new NTT({
              name: `${descriptor.model}_${response.id || Date.now()}`,
              addr: `${descriptor.url}/${response.id}`,
              data: response
            });
            
            // Set remote state to match initial server response
            ntt._meta.remoteState = { ...response };
            ntt._meta.localState = { ...response };
            ntt._meta.isDirty = false;
            
            descriptor.onSuccess(ntt);
          });
        } catch (error) {
          console.error('[NTTBroker] Create success handler error:', error);
          descriptor.onError(error);
        }
      },
      onError: (error) => {
        console.error(`[NTTBroker] Create failed for ${descriptorId}:`, error);
        descriptor.onError(error);
      }
    };

    const evt = new Event({ 
      name: 'create', 
      source: descriptorId, 
      target: 'api', 
      data: eventData
    });
    
    transport.send(evt);
  }
  
  // ------------------ Data Synchronization ------------------
  
  /**
   * Pull/refresh data for an NTT instance from server
   * @param {string} instanceId - NTT instance ID
   * @param {Object} options - Additional options
   */
  static pull(instanceId, options = {}) {
    const instance = NTTRegistry.getInstance(instanceId);
    if (!instance) {
      throw new Error(`[NTTBroker] No NTT instance found with id: ${instanceId}`);
    }

    const descriptor = NTTRegistry.findDescriptorForInstance(instance);

    const eventData = {
      url: instance.addr,
      ...options,
      onSuccess: (response) => {
        try {
          // Update remote state and reconcile with local changes
          instance._meta.remoteState = { ...response };
          
          if (!instance._meta.isDirty) {
            // No local changes - safe to update everything
            const oldData = { ...instance._data };
            instance._data = { ...response };
            instance._meta.localState = { ...response };
            
            // Import notifyAllObservers dynamically
            import('./NTTUtils.js').then(({ notifyAllObservers }) => {
              notifyAllObservers(instance, instance._data, oldData);
            });
          } else {
            console.warn(`[NTTBroker] Instance ${instanceId} has uncommitted changes during pull`);
          }
          
          if (descriptor?.onSuccess) {
            descriptor.onSuccess(instance);
          }
        } catch (error) {
          console.error('[NTTBroker] Pull success handler error:', error);
          if (descriptor?.onError) {
            descriptor.onError(error);
          }
        }
      },
      onError: (error) => {
        console.error(`[NTTBroker] Pull failed for ${instanceId}:`, error);
        if (descriptor?.onError) {
          descriptor.onError(error);
        }
      }
    };

    const evt = new Event({ 
      name: 'load', 
      source: instanceId, 
      target: 'api', 
      data: eventData
    });
    
    transport.send(evt);
  }
  
  /**
   * Push/commit data for an NTT instance to server
   * @param {string} instanceId - NTT instance ID
   * @param {Object} options - Additional options
   * @returns {Promise<Object>} Promise resolving to the instance
   */
  static async push(instanceId, options = {}) {
    const instance = NTTRegistry.getInstance(instanceId);
    if (!instance) {
      throw new Error(`[NTTBroker] No NTT instance found with id: ${instanceId}`);
    }

    if (!instance._meta.isDirty || instance._meta.isCommitting) {
      return instance;
    }

    instance._meta.isCommitting = true;
    const descriptor = NTTRegistry.findDescriptorForInstance(instance);

    try {
      const pushPromise = new Promise((resolve, reject) => {
        const eventData = {
          url: instance.addr,
          data: instance._meta.localState,
          version: instance._meta.version,
          ...options,
          onSuccess: (response) => {
            try {
              // Successful commit - update remote state
              instance._meta.remoteState = { ...response };
              instance._meta.localState = { ...response };
              instance._data = { ...response };
              instance._meta.pendingOps = [];
              instance._meta.isDirty = false;
              instance._meta.isCommitting = false;
              
              if (descriptor?.onSuccess) {
                descriptor.onSuccess(instance);
              }
              
              resolve(instance);
            } catch (error) {
              instance._meta.isCommitting = false;
              console.error('[NTTBroker] Push success handler error:', error);
              reject(error);
            }
          },
          onError: (error) => {
            instance._meta.isCommitting = false;
            console.error(`[NTTBroker] Push failed for ${instanceId}:`, error);
            if (descriptor?.onError) {
              descriptor.onError(error);
            }
            reject(error);
          }
        };

        const evt = new Event({ 
          name: 'update', 
          source: instanceId, 
          target: 'api', 
          data: eventData
        });
        
        transport.send(evt);
      });

      return await pushPromise;
    } catch (error) {
      instance._meta.isCommitting = false;
      throw error;
    }
  }
  
  // ------------------ Schema Discovery ------------------
  
  /**
   * Discover API schemas and register prototypes
   * @param {string} url - Schema discovery endpoint
   * @param {Object} options - Additional options
   */
  static async discover(url, options = {}) {
    try {
      const eventData = {
        url,
        ...options,
        onSuccess: (data) => {
          // Register discovered prototypes
          for (const [key, value] of Object.entries(data.$defs || {})) {
            NTTRegistry.setPrototype(key, value);
          }
          console.log('[NTTBroker] Discovered schemas:', Object.keys(data.$defs || {}));
          
          if (options.onSuccess) {
            options.onSuccess(data);
          }
        },
        onError: (error) => {
          console.error('[NTTBroker] Discovery failed:', error);
          if (options.onError) {
            options.onError(error);
          }
        }
      };

      const evt = new Event({ 
        name: 'load', 
        source: 'NTTBroker', 
        target: 'api', 
        data: eventData,
        meta: { type: 'discover' } 
      });
      
      transport.send(evt);
    } catch (error) {
      console.error('[NTTBroker] Discovery error:', error);
      if (options.onError) {
        options.onError(error);
      }
    }
  }
  
  // ------------------ Batch Operations ------------------
  
  /**
   * Create multiple instances in batch
   * @param {string} descriptorId - Descriptor identifier
   * @param {Array} dataArray - Array of data objects to create
   * @param {Object} options - Additional options
   * @returns {Promise<Array>} Promise resolving to array of created instances
   */
  static async createBatch(descriptorId, dataArray, options = {}) {
    const promises = dataArray.map(data => {
      return new Promise((resolve, reject) => {
        const originalOnSuccess = options.onSuccess;
        const originalOnError = options.onError;
        
        this.create(descriptorId, data, {
          ...options,
          onSuccess: (ntt) => {
            if (originalOnSuccess) originalOnSuccess(ntt);
            resolve(ntt);
          },
          onError: (error) => {
            if (originalOnError) originalOnError(error);
            reject(error);
          }
        });
      });
    });
    
    return Promise.all(promises);
  }
  
  /**
   * Pull multiple instances in batch
   * @param {Array} instanceIds - Array of instance IDs
   * @param {Object} options - Additional options
   */
  static pullBatch(instanceIds, options = {}) {
    instanceIds.forEach(instanceId => {
      this.pull(instanceId, options);
    });
  }
  
  // ------------------ Utility Methods ------------------
  
  /**
   * Get broker statistics
   * @returns {Object} Statistics object
   */
  static getStats() {
    const registryStats = NTTRegistry.getStats();
    return {
      ...registryStats,
      descriptors: registryStats.descriptors, // Alias for compatibility
      timestamp: Date.now()
    };
  }
  
  /**
   * Test connection to a descriptor endpoint
   * @param {string} descriptorId - Descriptor identifier
   * @returns {Promise<boolean>} Promise resolving to connection status
   */
  static async testConnection(descriptorId) {
    const descriptor = NTTRegistry.getDescriptor(descriptorId);
    if (!descriptor) {
      throw new Error(`[NTTBroker] No descriptor found: ${descriptorId}`);
    }
    
    try {
      const response = await fetch(descriptor.url, { 
        method: 'HEAD',
        headers: { 'Accept': 'application/json' }
      });
      return response.ok;
    } catch (error) {
      console.error(`[NTTBroker] Connection test failed for ${descriptorId}:`, error);
      return false;
    }
  }
}