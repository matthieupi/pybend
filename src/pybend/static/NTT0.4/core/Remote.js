import HTTP from './HTTP.js';
import Socket from './Socket.js';
import assert from "../utils/Assert.js";
import {Utils} from "./Utils.js";

export class Remote {
  
  static #callbacks = new Map(); // key -> callback for this address
  
  constructor(mode = 'http') {
    this.mode = mode;
    this.socket = null;
    if (mode === 'ws') {
      this.socket = new Socket("localhost:8765");
    }
  }
  
  httpCallback(event, response) {
    assert(this, event && event.target, `Event must have a target property.`);
    assert(this, Remote.#callbacks.has(event.target), `No callback registered for target: ${event.target}`);
    // Create an event object from the response, inversing source and target
    const callback = Remote.#callbacks.get(event.target);
    assert(this, typeof callback === 'function', `Callback for ${event.target} is not a function.`);
    try {
      // If response is successful, invoke the callback with the event
      callback(response);
    } catch (error) {
      console.error(`Error in callback for ${event.target}:`, error);
    }
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
    let eventCallback = {
        'name': "error",
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
    this.emit(eventCallback)
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
    assert(this, Remote.#callbacks.has(event.target), `No callback registered for target: ${event.target}`);
    const callback = Remote.#callbacks.get(event.target);
    assert(this, typeof callback === 'function', `Callback for ${event.target} is not a function.`);
    try {
      callback(event);
    } catch (error) {
      console.error(`Error in callback for ${event.target}:`, error);
    }
  }
  
  pull(target, callback = null) {
    assert(this, target, `Target must be provided for pull operation.`);
    assert(this, typeof target === 'string', `Target must be a string, got ${typeof target}`);
    assert(this, Remote.#callbacks.has(target) || callback , `No callback registered, and no callback provided for target: ${target}`)
    assert(this, !callback || typeof callback === 'function', `Callback must be a function, got ${typeof callback}`);
    
    if (callback) {
      Remote.#callbacks.set(target, callback);
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
    
    console.log(`Sending event: ${event.name} from ${event.source} to ${event.target}`, event)
    const {name, data, meta, source, target, id, timestamp} = event;
    let callback = this.httpCallback.bind(this, event);
    let onError = this.onError.bind(this, event);
    
    if (this.mode === 'http') {
      if (name.toUpperCase() === 'LOAD') HTTP.get(target, callback, onError);
      else if (name.toUpperCase() === 'READ') HTTP.get(target, callback, onError);
      else if (name.toUpperCase() === 'SCHEMA') HTTP.get(target, callback, onError);
      else if (name.toUpperCase() === 'CREATE') HTTP.post(target, data, callback, onError);
      else if (name.toUpperCase() === 'UPDATE') HTTP.put(target, data, callback, onError);
      else if (name.toUpperCase() === 'DELETE') HTTP.remove(target, data, callback, onError);
      else throw new Error(`Unsupported event name: ${name}. Supported names are: LOAD, READ, SCHEMA, CREATE, UPDATE, DELETE.`)
    }
    
    if (this.mode === 'ws' && this.socket) {
      this.socket.sendEvent(event);
    }
  }
  
}


export const remote = new Remote('http');
console.log(`Registering remote transport manager to window: `, remote.mode, remote.socket ? remote.socket.url : 'No socket available');
window.Remote = remote;