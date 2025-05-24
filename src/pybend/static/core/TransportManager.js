import HTTP from './HTTP.js';
import Socket from './Socket.js';
import { Event } from './Event.js';

export class TransportManager {
  constructor(mode = 'http') {
    this.mode = mode;
    this.socket = null;
    if (mode === 'ws') {
      this.socket = new Socket("localhost:8765");
    }
  }

  async send(event) {
    const { name, data, meta, source, target, id, timestamp } = event;
    if (this.mode === 'http') {
      if (name === 'load') return HTTP.get(data.url, data.onSuccess, data.onError);
      if (name === 'create') return HTTP.post(data.url, data.data, data.onSuccess, data.onError);
      if (name === 'update') return HTTP.put(data.url, data.data, data.onSuccess, data.onError);
      if (name === 'delete') return HTTP.remove(data.url, data.onSuccess, data.onError);
    }

    if (this.mode === 'ws' && this.socket) {
      this.socket.sendEvent(event);
    }
  }
}

export const transport = new TransportManager('http');
window.TransportManager = transport;