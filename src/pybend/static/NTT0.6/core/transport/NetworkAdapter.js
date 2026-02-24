import HTTP from './HTTP.js';
import assert from "../../utils/Assert.js";
import {Utils} from "../Utils.js";
import {config} from "../../config.js";
import Logging from "../../utils/Logging.js";

export class NetworkAdapter {
  
  constructor(matrix, url="", mode = 'http') {
    this.matrix = matrix;
    this.mode = mode;
    this.socket = null;
    this.url = url || config.API_URL;
    if (mode === 'ws') {
      import('./Socket.js').then(({ default: Socket }) => {
        this.socket = new Socket("localhost:8765");
      });
    }
    this.send = this.send.bind(this);
  }
 
  httpCallback(event, response) {
    
    assert(this, event && event.target, `Event must have a target property.`);
    assert(this, this.matrix.has(event.source), `No callback registered for target: ${event.source}`);
    // Updater the event with the response data
    if (event.meta['inbox'])
      event.name = event.meta['inbox']; // Use inbox as the event name if provided
    let source = event.source, target = event.target
    event.source = target;
    event.target = source
    event.data = response; // Assuming response is the data we want to send back
    // Dispatch the event through the system layer
    this.matrix.dispatch(event)
  }
  
  /**
   * Error handler for transport events.
   *
   * @param event (Event) - The event that triggered the error.
   * @param response (Object) - The response object containing error details.
   */
  onError(event, response) {
    Logging.error(`[NetworkAdapter] Remote error on ${event.name}`, response);
    let {name, data, meta, source, target, id, timestamp} = event;
    let errorCallback = {
        'name': "ERROR",
        'id': id,
        'source': target,
        'target': source,
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
   * Emit an event to the registered callback.
   * This method will invoke the callback registered for the event's target.
   *
   * @param {object} event - The event object containing properties like target, name, data, etc.
   */
  emit(event) {
    assert(this, event && event.target, `Event must have a target property.`);
    assert(this, event && event.name, `Event must have a name property.`);
    //assert(this, registry.has(event.target), `No callback registered for target: ${event.target}`);
    //const callback = registry.get(event.target);
    assert(this, typeof callback === 'function', `Callback for ${event.target} is not a function.`);
    try {
      callback(event);
    } catch (error) {
      Logging.error(`[NetworkAdapter] Callback error for ${event.target}`, error);
    }
  }
  
  pull(target, callback = null) {
    Logging.dev(`Pulling data from target: ${target}`, callback ? `with callback: ${callback.name}` : 'without callback')
    assert(this, target, `Target must be provided for pull operation.`);
    assert(this, typeof target === 'string', `Target must be a string, got ${typeof target}`);
    assert(this, !callback || typeof callback === 'function', `Callback must be a function, got ${typeof callback}`);
    
    if (callback) {
      //registry.set(target, callback);
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
    let {name, data, meta, source, target, id, timestamp} = event;
    let callback = this.httpCallback.bind(this, event);
    let onError = this.onError.bind(this, event);
    
    if (this.mode === 'http') {
      if (name.toUpperCase() === config.E.load) HTTP.get(target, callback, onError);
      else if (name.toUpperCase() === 'READ') {
        let url = target;
        if (data && typeof data === 'object' && !Array.isArray(data)) {
          const params = new URLSearchParams();
          for (const [k, v] of Object.entries(data)) {
            if (v != null) params.set(k, v);
          }
          const qs = params.toString();
          if (qs) url += (url.includes('?') ? '&' : '?') + qs;
        }
        HTTP.get(url, callback, onError);
      }
      else if (name.toUpperCase() === 'SCHEMA') HTTP.get(`${target}`, callback, onError);
      else if (name.toUpperCase() === 'CREATE') HTTP.post(target, data, callback, onError);
      else if (name.toUpperCase() === 'UPDATE') HTTP.put(target, data, callback, onError);
      else if (name.toUpperCase() === 'DELETE') HTTP.remove(target, callback, onError);
      else if (name.toUpperCase() === 'TEST') HTTP.get(target, data, callback, onError);
      else {
        HTTP.post(`${target}/${name.toLowerCase()}`, data, callback, onError);
      }
      //else throw new Error(`Unsupported event name: ${name}. Supported names are: LOAD, READ, SCHEMA, CREATE, UPDATE, DELETE.`)
    }
    
    if (this.mode === 'ws' && this.socket) {
      this.socket.sendEvent(event);
    }
  }
  
}


export const remote = new NetworkAdapter('http');
Logging.dev(`[NetworkAdapter] Registered remote transport`, remote.mode);
window.remote = remote;