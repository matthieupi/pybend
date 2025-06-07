import HTTP from './HTTP.js';
import Socket from '../Socket.js';
import { Event } from './Event.js';

export class TransportManager {
  constructor(mode = 'http') {
    this.mode = mode;
    this.socket = null;
    if (mode === 'ws') {
      this.socket = new Socket("localhost:8765");
    }
  }
  
  callback(json) {
    console.log(`TransportManager Callback: ${json}`); // eslint-disable-line no-console
  }
  
  
  onError(event) {
    console.error(`TransportManager Error: ${event}`);
  }

  async send(event) {
    
    const { name, data, meta, source, target, id, timestamp, callback } = event;
    if (this.mode === 'http') {
      if (name === 'load') return HTTP.get(target, callback, this.onError);
      if (name === 'schema') return HTTP.get(target, callback, this.onError);
      if (name === 'create') return await HTTP.post(target, data, callback, this.onError);
      if (name === 'update') return await HTTP.put(target, data, callback, this.onError);
      if (name === 'delete') return await HTTP.remove(target, data, callback, this.onError);
    }

    if (this.mode === 'ws' && this.socket) {
      this.socket.sendEvent(event);
    }
  }
  
  
  schema(target) {
    let model_endpoint = HTTP.baseURL('schema');
    if (this.mode === 'http') {
      return HTTP.get(target, this.callback, this.onError);
    }
  
  }
}

export const transport = new TransportManager('http');
console.log(`Registering transport manager to window: `, transport.mode, transport.socket ? transport.socket.url : 'No socket available');
window.TransportManager = transport;