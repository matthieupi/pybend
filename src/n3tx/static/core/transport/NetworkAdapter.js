import HTTP from './HTTP.js';
import assert from "../../utils/Assert.js";
import {Utils} from "../Utils.js";
import {config} from "../../config.js";
import Logging from "../../utils/Logging.js";
import TX from "../TX.js";

export class NetworkAdapter {

  constructor(matrix, url="", mode = 'http') {
    this.matrix = matrix;
    this.mode = mode;
    this.socket = null;
    this.url = url || config.API_URL;
    if (mode === 'ws') {
      this._initWebSocket();
    }
    this.send = this.send.bind(this);
  }

  _initWebSocket() {
    import('./Socket.js').then(({ default: Socket }) => {
      const wsUrl = config.WS_URL || `${this.url.replace(/^http/, 'ws')}/ws`;
      this.socket = new Socket(wsUrl);
      this.socket.onmessage = (data) => {
        // Server-push messages (lifecycle events) and request responses
        // both arrive here. Dispatch through Matrix.
        this.matrix.dispatch(data);
      };
      // Connect with JWT if available
      const token = window.localStorage ? window.localStorage.getItem('jwtToken') : null;
      this.socket.connect(token || undefined);
      Logging.dev('[NetworkAdapter] WebSocket transport initialized');
    });
  }

  httpCallback(event, response) {

    assert(this, event && event.target, `Event must have a target property.`);
    assert(this, this.matrix.has(event.source), `No callback registered for target: ${event.source}`);
    // Create a reply with swapped source/target (don't mutate the original event)
    let reply = {
      name: event.meta?.['inbox'] || event.name,
      id: event.id,
      source: event.target,
      target: event.source,
      data: response,
      meta: event.meta || {},
      timestamp: Date.now()
    };
    this.matrix.dispatch(reply)
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
    const errorMeta = {
      'remote': true,
      'error': true,
      'response': response,
    };
    // Attach structured validation errors when available (Pydantic 422)
    const validationErrors = HTTP._extractValidationErrors(response);
    if (validationErrors) {
      errorMeta.validationErrors = validationErrors;
    }
    let errorCallback = {
        'name': "ERROR",
        'id': id,
        'source': target,
        'target': source,
        'data': event,
        'timestamp': Date.now(),
        'meta': errorMeta,
    }
    this.matrix.dispatch(errorCallback)
  }

  pull(target, callback = null) {
    Logging.dev(`Pulling data from target: ${target}`, callback ? `with callback: ${callback.name}` : 'without callback')
    assert(this, target, `Target must be provided for pull operation.`);
    assert(this, typeof target === 'string', `Target must be a string, got ${typeof target}`);
    assert(this, !callback || typeof callback === 'function', `Callback must be a function, got ${typeof callback}`);

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
   *
   * When WebSocket is connected, sends over WS (primary).
   * Falls back to HTTP when WS is unavailable.
   *
   * @param event
   * @returns {void}
   */
  send(event) {
    // WebSocket primary when available
    if (this.socket && this.socket.ready) {
      const tx = event instanceof TX ? event : new TX(event);
      this.socket.send(tx);
      return;
    }

    // HTTP fallback
    let {name, data, meta, source, target, id, timestamp} = event;
    let callback = this.httpCallback.bind(this, event);
    let onError = this.onError.bind(this, event);

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
  }

  /**
   * Send a streaming request. Works over both WS and HTTP (SSE).
   *
   * When WebSocket is connected, sends a TX with stream metadata and
   * registers a stream handler on Socket for correlated chunk routing.
   * Falls back to HTTP SSE (via HTTP.stream()) when WS is unavailable.
   *
   * @param {TX|Object} event - The TX to send
   * @param {Function} onChunk - Called for each streamed chunk
   * @param {Function} onDone - Called when stream completes
   * @param {Function} onError - Called on error
   * @returns {{ cancel: Function }} - Call cancel() to abort the stream
   */
  sendStream(event, onChunk, onDone, onError) {
    if (this.socket && this.socket.ready) {
      const tx = event instanceof TX ? event : new TX(event);
      tx.meta = { ...(tx.meta || {}), stream: true };
      const reqId = tx._hash || tx.meta._reqId || Date.now().toString(36);
      tx.meta._reqId = reqId;
      const cancel = this.socket.registerStream(reqId, onChunk, onDone, onError);
      this.socket.send(tx);
      return { cancel };
    }
    // HTTP SSE fallback
    const { name, data, target } = event;
    const url = `${target}/${name.toLowerCase()}`;
    return HTTP.stream(url, data, onChunk, onDone, onError);
  }

}
