import assert from "../utils/Assert.js";
import { caution } from "../utils/Assert.js";
import { config } from '../config.js';

export const registry = new Map();
export const connectors = new Map();


/**
 * Registers a model in the model registry.
 * @param key {string} - The unique key for the model.
 * @param callback {Function} - The callback dispatch function for this address.
 */
export function registrar(key, callback) {
    assert(this, key, 'Key must be defined');
    caution(this, callback, `Callback undefined, will unregister ${key}`);
    caution(this, registry.has(key), `Overwriting existing registry entry for ${key}`)
    if (!callback){
        if (registry.has(key)) { registry.delete(key); }
        else { console.warn(`No entry found for ${key} to unregister.`); }
    } else {
        registry.set(key, callback);
    }
    // Return unregister function to remove the entry
    return () => {
        if (registry.has(key)) {
            registry.delete(key);
        } else {
            console.warn(`No entry found for ${key} to unregister.`);
        }
    };
}

/**
 * Retrieves a registrar callback function by its key.
 * @param key {string} - The unique key for the model.
 * @returns {Function} - The callback function associated with the key.
 */
export function getRegistrar(key) {
    assert(this, key, 'Name must be defined');
    assert(this, !registry.has(key), `No entry found when trying to get registrar for ${key}`);
    
    return registry.get(key);
}


/**
 * Executes the callback function associated with the given key in the registry with specified data.
 * @param key {string} - The unique key for the model.
 * @param data {any} - The data to be dispatched.
 * @param meta {Object} - Additional metadata for the request. Todo: UNUSED REF - Analyze if should pe kept for future impl.
 * @returns {void}
 */
export function dispatch(key, data, meta = {}) {
    // Log all the type of the keys in the registry
    assert(this, key, 'Key must be defined');
    assert(this, registry.has(key), `No entry found when trying to get registrar for ${key}`);
    assert(this, typeof registry.get(key) === 'function', `Callback for ${key} is not a function.`);
    
    const callback = registry.get(key);
    try { callback(data); }
    catch (error) { console.error(`Error in registrar callback for ${key}:`, error); }
}

