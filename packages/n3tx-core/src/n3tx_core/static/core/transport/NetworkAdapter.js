/** Route native transactions through HTTP/WS with correlated replies.
 * API: NetworkAdapter.send maps native operations to network requests;
 * httpCallback and onError return correlated messages through the Matrix.
 * READ serializes native where objects for collection GETs. Backend model
 * validation and policy remain authoritative; this is not a query engine.
 * Integration: construct with the native Matrix and configured API URL. */
import HTTP from './HTTP.js';
import assert from "../../utils/Assert.js";
import {Utils} from "../Utils.js";
import {config} from "../../config.js";
import Logging from "../../utils/Logging.js";
import TX from "../TX.js";

/** Preserve native message routing across browser network transports. */
export class NetworkAdapter {

  /** Configure the browser transport.
   * @param {Object} matrix Native message router.
   * @param {string} [url=""] API URL; empty uses configured API_URL.
   * @param {string} [mode='http'] HTTP or WebSocket transport mode. */
  constructor(matrix, url="", mode = 'http') {
    // 0. Establish transport state and bind the dispatch entrypoint.
    this.matrix = matrix;
    this.mode = mode;
    this.socket = null;
    this.url = url || config.API_URL;
    if (mode === 'ws') {
      this._initWebSocket();
    }
    this.send = this.send.bind(this);
  }

  /** Initialize the optional authenticated WebSocket transport.
   * @returns {void} */
  _initWebSocket() {
    // 0. Load the socket implementation only for WebSocket mode.
    import('./Socket.js').then(({ default: Socket }) => {
      const wsUrl = config.WS_URL || `${this.url.replace(/^http/, 'ws')}/ws`;
      this.socket = new Socket(wsUrl);
      this.socket.onmessage = (data) => {
        // Server-push messages (lifecycle events) and request responses
        // both arrive here. Dispatch through Matrix.
        this.matrix.dispatch(data);
      };
      // Connect with JWT if available
      const token = window.localStorage
        ? window.localStorage.getItem('jwtToken') : null;
      this.socket.connect(token || undefined);
      Logging.dev('[NetworkAdapter] WebSocket transport initialized');
    });
  }

  /** Dispatch an HTTP response to its originating native component.
   * @param {Object} event Original transaction.
   * @param {*} response Parsed server response.
   * @returns {void} */
  httpCallback(event, response) {
    // 0. Validate routing before adapting the server response.
    assert(this, event && event.target, `Event must have a target property.`);
    assert(this, this.matrix.has(event.source),
      `No callback registered for target: ${event.source}`);
    // Unwrap optional model-action debug envelopes.
    if (response && response._debug && 'data' in response) {
      response = response.data;
    }
    // 1. Reply without mutating the original transaction.
    let reply = {
      name: event.meta?.['inbox'] || event.name,
      id: event.id,
      source: event.target,
      target: event.source,
      data: response,
      meta: event.meta || {},
      timestamp: Date.now()
    };
    this.matrix.dispatch(reply);
  }

  /** Dispatch a correlated transport failure.
   * @param {Object} event Original transaction.
   * @param {Object} response Server or transport error details.
   * @returns {void} */
  onError(event, response) {
    // 0. Preserve the failed request for native response-correlation checks.
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
    };
    this.matrix.dispatch(errorCallback);
  }

  /** Request a remote entity through the native transport.
   * @param {string} target Remote entity URL.
   * @param {Function|null} [callback=null] Legacy diagnostic callback.
   * @returns {void} */
  pull(target, callback = null) {
    // 0. Validate the target and legacy callback shape.
    Logging.dev(`Pulling data from target: ${target}`,
      callback ? `with callback: ${callback.name}` : 'without callback');
    assert(this, target, `Target must be provided for pull operation.`);
    assert(this, typeof target === 'string',
      `Target must be a string, got ${typeof target}`);
    assert(this, !callback || typeof callback === 'function',
      `Callback must be a function, got ${typeof callback}`);
    // 1. Send a native read transaction.
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
    };
    this.send(event);
  }


  /** Send a transaction over WebSocket when ready, otherwise HTTP.
   * @param {Object} event Native transaction to dispatch.
   * @returns {void} */
  send(event) {
    // 0. Prefer a connected WebSocket without changing its payload shape.
    if (this.socket && this.socket.ready) {
      const tx = event instanceof TX ? event : new TX(event);
      this.socket.send(tx);
      return;
    }
    // 1. Adapt the native operation to HTTP and preserve reply correlation.
    let {name, data, meta, source, target, id, timestamp} = event;
    let callback = this.httpCallback.bind(this, event);
    let onError = this.onError.bind(this, event);

    if (name.toUpperCase() === config.E.load) {
      HTTP.get(target, callback, onError);
    }
    else if (name.toUpperCase() === 'READ') {
      let url = target;
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        const params = new URLSearchParams();
        for (const [k, v] of Object.entries(data)) {
          if (v != null) {
            params.set(k, k === 'where' ? JSON.stringify(v) : v);
          }
        }
        const qs = params.toString();
        if (qs) url += (url.includes('?') ? '&' : '?') + qs;
      }
      HTTP.get(url, callback, onError);
    }
    else if (name.toUpperCase() === 'SCHEMA') {
      HTTP.get(target, callback, onError);
    }
    else if (name.toUpperCase() === 'CREATE') {
      HTTP.post(collectionWriteTarget(target), data, callback, onError);
    }
    else if (name.toUpperCase() === 'UPDATE') {
      HTTP.put(target, data, callback, onError);
    }
    else if (name.toUpperCase() === 'DELETE') {
      HTTP.remove(target, callback, onError);
    }
    else if (name.toUpperCase() === 'TEST') {
      HTTP.get(target, data, callback, onError);
    }
    else if (meta?.stream) {
      HTTP.stream(`${collectionWriteTarget(target)}/${name.toLowerCase()}`,
        data, callback, callback, onError);
    }
    else {
      HTTP.post(`${collectionWriteTarget(target)}/${name.toLowerCase()}`,
        data, callback, onError);
    }
  }

  /** Stream through the legacy callback interface.
   * @deprecated Use send() with meta.stream for native message routing.
   * @param {Object} event Native transaction.
   * @param {Function} onChunk Chunk callback.
   * @param {Function} onDone Completion callback.
   * @param {Function} onError Failure callback.
   * @returns {*} Native HTTP stream result. */
  sendStream(event, onChunk, onDone, onError) {
    const { name, data, target } = event;
    const url = `${target}/${name.toLowerCase()}`;
    return HTTP.stream(url, data, onChunk, onDone, onError);
  }

}

/** Remove the collection-read suffix for mutation/action requests.
 * @param {*} target Native target address.
 * @returns {*} The corresponding collection-write address. */
function collectionWriteTarget(target) {
  return typeof target === 'string' && target.endsWith('/_')
    ? target.slice(0, -2)
    : target;
}

/* Changelog
 * - 2026-11-10: Restore serialization of native where predicates.
 * - 2026-11-02: Serialize native where objects in collection READ requests. */
