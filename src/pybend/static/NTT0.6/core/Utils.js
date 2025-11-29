/**
 * Utility functions for NTT system
 * Provides common functionality used across NTT components
 */

/**
 * Deep equality check for objects
 * @param {any} obj1 - First object
 * @param {any} obj2 - Second object
 * @returns {boolean} True if objects are deeply equal
 */
function deepEqual(obj1, obj2) {
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
 * Generate unique identifier
 * @returns {string} Unique ID string
 */
function generateId() {
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

/**
 * Create operation record for state transitions
 * @param {string} type - Operation type
 * @param {Function|Object} transformation - Transformation applied
 * @param {Object} metadata - Additional operation metadata
 * @param {number} version - Operation version
 * @returns {Object} Operation record
 */
function createOperation(type, transformation, metadata = {}, version = 1) {
  return {
    type,
    id: generateId(),
    transformation,
    timestamp: Date.now(),
    version,
    metadata
  };
}

/**
 * Notify all subscribers of state changes
 * @param {Object} instance - NTT instance
 * @param {Object} oldData - Previous state
 * @param {Object} newData - New state
 */
function notifySubscribers(instance, oldData, newData) {
  // Notify general subscribers
  instance._meta.subscribers.forEach(callback => {
    try {
      callback(newData, oldData, instance);
    } catch (error) {
      console.error('[NTT] Subscriber error:', error);
    }
  });

  // Notify property observers
  instance._meta.propertyObservers.forEach((callbacks, property) => {
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
 * Simple hash function for data integrity
 * @param {Object} data - Data to hash
 * @returns {string} Hash string
 */
function simpleHash(data) {
  const str = JSON.stringify(data, Object.keys(data).sort());
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return hash.toString(36);
}

/**
 * Type compatibility checker for schema validation
 * @param {any} value - Value to check
 * @param {string} expectedType - Expected type string
 * @returns {boolean} True if compatible
 */
function isTypeCompatible(value, expectedType) {
  const jsType = typeof value;
  switch (expectedType) {
    case 'string': return jsType === 'string';
    case 'number': return jsType === 'number';
    case 'integer': return Number.isInteger(value);
    case 'boolean': return jsType === 'boolean';
    case 'object': return value && jsType === 'object' && !Array.isArray(value);
    case 'array': return Array.isArray(value);
    default: return true;
  }
}

/**
 * Default conflict resolver for merge operations
 * @param {Object} conflict - Conflict description
 * @param {Object} localNTT - Local NTT instance
 * @param {Object} otherNTT - Other NTT instance
 * @returns {any} Resolved value
 */
function defaultConflictResolver(conflict, localNTT, otherNTT) {
  // Default: prefer the most recent version
  return otherNTT._meta.version > localNTT._meta.version ? conflict.otherValue : conflict.localValue;
}

  // ------------------ Dynamic Class Generation ------------------

  /**
   * Generate a subclass with dynamic properties from schema
   * @param {Object} schema - JSON schema definition
   * @param {string} [className] - Optional class name
   * @returns {Function} Generated subclass constructor
   */
function generateClassFromSchema(schema, className = null) {
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
          if (expectedType && !Utils.isTypeCompatible(value, expectedType)) {
            throw new TypeError(`Invalid type for '${field}': expected ${expectedType}`);
          }
        
          // Use static functional evolution for property changes
          NTT.evolve(this.id, {[field]: value});
        },
        enumerable: !hidden,
        configurable: true,
      });
    
      if (!SubClass.labels) SubClass.labels = {};
      SubClass.labels[field] = label;
    }
  
    Object.defineProperty(SubClass, 'name', {value: classTitle});
    return SubClass;
  }
  
function isUrl(str) {
  try {
    new URL(str);
    return true;
  } catch (e) {
    return false;
  }
}

function isEmpty(obj) {
  if (typeof obj !== 'object') {
    for (const prop in obj) {
      if (Object.hasOwn(obj, prop)) {
        return false;
      }
    }
  return true;
  }
  else if (Array.isArray(obj)) {
    return obj.length === 0;
  }
  else {
    return !!obj
  }
}

export {
  isUrl,
  isEmpty,
  deepEqual,
  generateId,
  createOperation,
  notifySubscribers,
  simpleHash,
  isTypeCompatible,
  defaultConflictResolver,
  generateClassFromSchema
};

export const Utils ={
  deepEqual,
  generateId,
  createOperation,
  notifySubscribers,
  simpleHash,
  isTypeCompatible,
  defaultConflictResolver
};
