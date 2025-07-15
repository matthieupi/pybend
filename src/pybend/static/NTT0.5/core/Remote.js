import HTTP from './HTTP.js';
import Socket from './Socket.js';
import assert from "../utils/Assert.js";
import {Utils} from "./Utils.js";
import {registrar, registry, dispatch} from "./registrar.js";
import {config} from "../config.js";

export class Remote {
  
  static #callbacks = new Map(); // key -> callback for this address
  
  constructor(mode = 'http') {
    this.mode = mode;
    this.socket = null;
    if (mode === 'ws') {
      this.socket = new Socket("localhost:8765");
    }
    this.send = this.send.bind(this);
  }
 
  httpCallback(event, response) {
    assert(this, event && event.target, `Event must have a target property.`);
    assert(this, registry.has(event.target), `No callback registered for target: ${event.target}`);
    // Updater the event with the response data
    if (event.data['inbox'])
      event.name = event.data['inbox']; // Use inbox as the event name if provided
    let source = event.source, target = event.target
    event.source = target;
    event.target = source
    event.data = response; // Assuming response is the data we want to send back
    // Dispatch the event through the system layer
    dispatch(event.target, event)
  }
  
  /**
   * Error handler for transport events.
   *
   * @param event (Event) - The event that triggered the error.
   * @param response (Object) - The response object containing error details.
   */
  onError(event, response) {
    console.group()
    console.error(`Remote error on event:`, event);
    console.error(`Error Response:\n${response}`);
    console.groupEnd()
    let {name, data, meta, source, target, id, timestamp} = event;
    let errorCallback = {
        'name': "ERROR",
        'id': id,
        'source': source,
        'target': target,
        'data': event,
        'timestamp': Date.now(),
        'meta': {
          'remote': true,
          'error': true,
          'response': response
        }
    }
    this.emit(errorCallback)
  }
  
  /**
   * Dispatch an event through the system layer.
   *
   * @param {Event} event  - The event to dispatch.
   * @returns {Promise<void>}
   */
  dispatch(event) {
    // TODO: Check if the event is local or remote and dispatch appropriately
  }
  
  /**
   * Emit an event to the registered callback.
   * This method will invoke the callback registered for the event's target.
   *
   * @param {object} event - The event object containing properties like target, name, data, etc.
   */
  emit(event) {
    assert(this, event && event.target, `Event must have a target property.`);
    assert(this, event && event.name, `Event must have a name property.`);
    assert(this, registry.has(event.target), `No callback registered for target: ${event.target}`);
    const callback = registry.get(event.target);
    assert(this, typeof callback === 'function', `Callback for ${event.target} is not a function.`);
    try {
      callback(event);
    } catch (error) {
      console.error(`Error in callback for ${event.target}:`, error);
    }
  }
  
  pull(target, callback = null) {
    console.log(`Pulling data from target: ${target}`, callback ? `with callback: ${callback.name}` : 'without callback')
    assert(this, target, `Target must be provided for pull operation.`);
    assert(this, typeof target === 'string', `Target must be a string, got ${typeof target}`);
    assert(this, !callback || typeof callback === 'function', `Callback must be a function, got ${typeof callback}`);
    
    if (callback) {
      registry.set(target, callback);
    }
    const event = {
      'name': 'read',
      'id': Utils.generateId(),
      'source': 'remote',
      'target': target,
      'data': null,
      'timestamp': Date.now(),
      'meta': {
        'remote': true
      }
    }
    this.send(event);
  }
  
  
  /**
   * Send an event through the transport layer.
   * @param event
   * @returns {void}
   */
  send(event) {
    const {name, data, meta, source, target, id, timestamp} = event;
    let callback = this.httpCallback.bind(this, event);
    let onError = this.onError.bind(this, event);
    
    if (this.mode === 'http') {
      if (name.toUpperCase() === config.E.load) HTTP.get(target, callback, onError);
      else if (name.toUpperCase() === 'READ') HTTP.get(target, callback, onError);
      else if (name.toUpperCase() === 'SCHEMA') HTTP.get(`${target}`, callback, onError);
      else if (name.toUpperCase() === 'CREATE') HTTP.post(target, data, callback, onError);
      else if (name.toUpperCase() === 'UPDATE') HTTP.put(target, data, callback, onError);
      else if (name.toUpperCase() === 'DELETE') HTTP.remove(target, data, callback, onError);
      else if (name.toUpperCase() === 'TEST') HTTP.get(target, data, callback, onError);
      else throw new Error(`Unsupported event name: ${name}. Supported names are: LOAD, READ, SCHEMA, CREATE, UPDATE, DELETE.`)
    }
    
    if (this.mode === 'ws' && this.socket) {
      this.socket.sendEvent(event);
    }
  }
  
}


export const remote = new Remote('http');
console.log(`Registering remote transport manager to window: `, remote.mode, remote.socket ? remote.socket.url : 'No socket available');
window.remote = remote;