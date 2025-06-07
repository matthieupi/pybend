// NTTUtils.js - Collection of pure utility functions

/**
 * Generate a unique identifier
 * @returns {string} Unique ID
 */
export function generateId() {
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

/**
 * Deep equality check for objects
 * @param {any} obj1 - First object
 * @param {any} obj2 - Second object
 * @returns {boolean} True if objects are deeply equal
 */
export function deepEqual(obj1, obj2) {
  if (obj1 === obj2) return true;
  if (obj1 == null || obj2 == null) return false;
  if (typeof obj1 !== 'object' || typeof obj2 !== 'object') return obj1 === obj2;
  
  const keys1 = Object.keys(obj1);
  const keys2 = Object.keys(obj2);
  
  if (keys1.length !== keys2.length) return false;
  
  for (let key of keys1) {
    if (!keys2.includes(key)) return false;
    if (!deepEqual(obj1[key], obj2[key])) return false;
  }
  
  return true;
}

/**
 * Create an operation object for functional state management
 * @param {string} type - Operation type
 * @param {Function|Object} transformation - Transformation to apply
 * @param {Object} metadata - Optional metadata
 * @param {number} version - Current version
 * @returns {Object} Operation object
 */
export function createOperation(type, transformation, metadata = {}, version = 1) {
  return {
    id: generateId(),
    type,
    transformation,
    timestamp: Date.now(),
    version,
    metadata
  };
}

/**
 * Get an instance from a Map with error handling
 * @param {Map} instances - Instance registry
 * @param {string} instanceId - Instance ID to retrieve
 * @param {string} errorMsg - Custom error message
 * @returns {Object} The instance
 * @throws {Error} If instance not found
 */
export function getInstance(instances, instanceId, errorMsg = 'Instance not found') {
  const instance = instances.get(instanceId);
  if (!instance) {
    throw new Error(`${errorMsg}: ${instanceId}`);
  }
  return instance;
}

/**
 * Validate transformation parameter
 * @param {Function|Object} transformation - Transformation to validate
 * @throws {TypeError} If transformation is invalid
 */
export function validateTransformation(transformation) {
  if (typeof transformation !== 'function' && typeof transformation !== 'object') {
    throw new TypeError('Transformation must be a function or object');
  }
  if (transformation === null) {
    throw new TypeError('Transformation cannot be null');
  }
}

/**
 * Apply transformation to state
 * @param {Object} currentState - Current state object
 * @param {Function|Object} transformation - Transformation to apply
 * @returns {Object} New state after transformation
 * @throws {Error} If transformation returns invalid state
 */
export function applyTransformation(currentState, transformation) {
  let newState;
  
  if (typeof transformation === 'function') {
    newState = transformation(currentState);
  } else {
    newState = { ...currentState, ...transformation };
  }

  if (typeof newState !== 'object' || newState === null) {
    throw new Error('Transformation must return an object');
  }

  return newState;
}

/**
 * Notify all subscribers of state changes
 * @param {Set} subscribers - Set of subscriber callbacks
 * @param {Object} newData - New state data
 * @param {Object} oldData - Previous state data
 * @param {Object} instance - NTT instance
 */
export function notifySubscribers(subscribers, newData, oldData, instance) {
  subscribers.forEach(callback => {
    try {
      callback(newData, oldData, instance);
    } catch (error) {
      console.error('[NTT] Subscriber error:', error);
    }
  });
}

/**
 * Notify property observers of specific property changes
 * @param {Map} propertyObservers - Map of property -> Set of callbacks
 * @param {Object} newData - New state data
 * @param {Object} oldData - Previous state data
 * @param {Object} instance - NTT instance
 */
export function notifyPropertyObservers(propertyObservers, newData, oldData, instance) {
  propertyObservers.forEach((callbacks, property) => {
    if (oldData[property] !== newData[property]) {
      callbacks.forEach(callback => {
        try {
          callback(newData[property], oldData[property], property, instance);
        } catch (error) {
          console.error(`[NTT] Property observer error for ${property}:`, error);
        }
      });
    }
  });
}

/**
 * Notify all observers (subscribers + property observers)
 * @param {Object} instance - NTT instance with meta.subscribers and meta.propertyObservers
 * @param {Object} newData - New state data
 * @param {Object} oldData - Previous state data
 */
export function notifyAllObservers(instance, newData, oldData) {
  notifySubscribers(instance._meta.subscribers, newData, oldData, instance);
  notifyPropertyObservers(instance._meta.propertyObservers, newData, oldData, instance);
}

/**
 * Initialize functional state in meta object
 * @param {Object} meta - Meta object to initialize
 * @param {Object} data - Initial data
 * @returns {Object} Updated meta object
 */
export function initializeFunctionalState(meta, data) {
  return {
    ...meta,
    localState: { ...data },
    remoteState: { ...data },
    pendingOps: [],
    version: 1,
    isDirty: false,
    isCommitting: false,
    subscribers: new Set(),
    propertyObservers: new Map(),
    conflictResolver: null
  };
}

/**
 * Check if value is compatible with expected JSON Schema type
 * @param {any} value - Value to check
 * @param {string} expectedType - Expected JSON Schema type
 * @returns {boolean} True if compatible
 */
export function isTypeCompatible(value, expectedType) {
  const jsType = typeof value;
  switch (expectedType) {
    case 'string': return jsType === 'string';
    case 'number': return jsType === 'number';
    case 'integer': return Number.isInteger(value);
    case 'boolean': return jsType === 'boolean';
    case 'object': return value && jsType === 'object' && !Array.isArray(value);
    case 'array': return Array.isArray(value);
    default: return true; // fallback: accept anything
  }
}

/**
 * Create an Event object for API communication
 * @param {string} name - Event name
 * @param {string} source - Event source
 * @param {string} target - Event target
 * @param {Object} data - Event data
 * @param {Object} meta - Event metadata
 * @returns {Object} Event-like object
 */
export function createApiEvent(name, source, target, data = {}, meta = {}) {
  return {
    name,
    source,
    target,
    data,
    meta,
    timestamp: Date.now(),
    id: generateId()
  };
}

/**
 * Find factory configuration for an instance
 * @param {Map} factories - Factory registry
 * @param {Object} instance - NTT instance
 * @returns {Object|null} Factory configuration or null
 */
export function findFactoryForInstance(factories, instance) {
  for (const [factoryId, factoryConfig] of factories.entries()) {
    if (instance.addr && instance.addr.includes(factoryConfig.url)) {
      return factoryConfig;
    }
  }
  return null;
}

/**
 * Default conflict resolver for merge operations
 * @param {Object} conflict - Conflict object with localValue, remoteValue, otherValue
 * @param {Object} localNTT - Local NTT instance
 * @param {Object} otherNTT - Other NTT instance
 * @returns {any} Resolved value
 */
export function defaultConflictResolver(conflict, localNTT, otherNTT) {
  // Default: prefer the most recent version
  return otherNTT.version > localNTT.version ? conflict.otherValue : conflict.localValue;
}

/**
 * Detect conflicts between two state objects
 * @param {Object} localState - Local state
 * @param {Object} remoteState - Remote state  
 * @param {Object} otherState - Other state to merge
 * @returns {Array} Array of conflict objects
 */
export function detectConflicts(localState, remoteState, otherState) {
  const conflicts = [];
  
  for (const [key, otherValue] of Object.entries(otherState)) {
    const localValue = localState[key];
    const remoteValue = remoteState[key];
    
    // Conflict exists if all three values are different
    if (localValue !== remoteValue && localValue !== otherValue && remoteValue !== otherValue) {
      conflicts.push({
        property: key,
        localValue,
        remoteValue,
        otherValue
      });
    }
  }
  
  return conflicts;
}

/**
 * Clean up serializable meta object (remove non-serializable items)
 * @param {Object} meta - Meta object to clean
 * @returns {Object} Cleaned meta object
 */
export function serializableMeta(meta) {
  return {
    ...meta,
    subscribers: undefined,
    propertyObservers: undefined,
    conflictResolver: undefined
  };
}

/**
 * Validate callback function parameter
 * @param {Function} callback - Callback to validate
 * @param {string} paramName - Parameter name for error message
 * @throws {TypeError} If callback is not a function
 */
export function validateCallback(callback, paramName = 'callback') {
  if (typeof callback !== 'function') {
    throw new TypeError(`${paramName} must be a function`);
  }
}

/**
 * Validate string parameter
 * @param {string} value - Value to validate
 * @param {string} paramName - Parameter name for error message
 * @throws {TypeError} If value is not a string
 */
export function validateString(value, paramName = 'parameter') {
  if (typeof value !== 'string') {
    throw new TypeError(`${paramName} must be a string`);
  }
}