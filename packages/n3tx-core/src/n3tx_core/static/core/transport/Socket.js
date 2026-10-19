import Logging from "../../utils/Logging.js";

const RECONNECT_BASE = 2000;
const RECONNECT_MAX = 30000;
const HEARTBEAT_INTERVAL = 30000;

/**
 * TX-native WebSocket transport.
 *
 * Manages a persistent WebSocket connection with:
 * - Auto-reconnect with exponential backoff
 * - Message queue during disconnect (flushed on reconnect)
 * - Heartbeat keep-alive every 30s
 * - JWT auth via query parameter
 *
 * Usage:
 *   const socket = new Socket('ws://localhost:5000/ws');
 *   socket.onmessage = (data) => matrix.dispatch(data);
 *   socket.connect(token);
 */
export default class Socket {

  constructor(url) {
    this.url = url;
    this.ws = null;
    this.ready = false;
    this.onmessage = null;
    this._queue = [];
    this._reconnectDelay = RECONNECT_BASE;
    this._reconnectTimer = null;
    this._heartbeatTimer = null;
    this._closed = false;
  }

  /**
   * Open the WebSocket connection.
   * @param {string} [token] - JWT token for authentication
   */
  connect(token) {
    this._closed = false;
    let url = this.url;
    if (token) {
      url += (url.includes('?') ? '&' : '?') + `token=${encodeURIComponent(token)}`;
    }
    this._token = token;

    try {
      this.ws = new WebSocket(url);
    } catch (e) {
      Logging.error('[Socket] Failed to create WebSocket', e);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      Logging.dev('[Socket] Connected');
      this.ready = true;
      this._reconnectDelay = RECONNECT_BASE;
      this._flush();
      this._startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (e) {
        Logging.error('[Socket] Failed to parse message', e);
        return;
      }
      // Heartbeat response — ignore
      if (data.heartbeat) return;

      // All messages flow through actor system — no stream interception
      if (this.onmessage) this.onmessage(data);
    };

    this.ws.onclose = (event) => {
      Logging.warn('[Socket] Disconnected', `code=${event.code}`);
      this.ready = false;
      this._stopHeartbeat();
      if (!this._closed) this._scheduleReconnect();
    };

    this.ws.onerror = (event) => {
      Logging.error('[Socket] Error');
    };
  }

  /**
   * Send a TX over the WebSocket.
   * If not connected, the message is queued and sent on reconnect.
   * @param {TX|object} tx - TX instance or plain object with repr()
   */
  send(tx) {
    const payload = tx && typeof tx.repr === 'function' ? tx.repr() : tx;
    if (this.ready && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    } else {
      this._queue.push(payload);
      Logging.dev('[Socket] Queued message (disconnected)');
    }
  }

  /**
   * Close the connection. No auto-reconnect.
   */
  close() {
    this._closed = true;
    this._stopHeartbeat();
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close(1000, 'Client closing');
      this.ws = null;
    }
    this.ready = false;
  }

  // ── Internal ──

  _flush() {
    while (this._queue.length > 0) {
      const msg = this._queue.shift();
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(msg));
      } else {
        this._queue.unshift(msg);
        break;
      }
    }
  }

  _scheduleReconnect() {
    if (this._closed) return;
    Logging.dev(`[Socket] Reconnecting in ${this._reconnectDelay}ms`);
    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      this.connect(this._token);
    }, this._reconnectDelay);
    this._reconnectDelay = Math.min(this._reconnectDelay * 2, RECONNECT_MAX);
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this._heartbeatTimer = setInterval(() => {
      if (this.ready && this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ heartbeat: true }));
      }
    }, HEARTBEAT_INTERVAL);
  }

  _stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
  }
}
