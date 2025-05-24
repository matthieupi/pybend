export class EventBus {
  constructor() {
    this.listeners = {};
  }

  subscribe(type, callback) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(callback);
  }

  unsubscribe(type, callback) {
    if (this.listeners[type])
      this.listeners[type] = this.listeners[type].filter(cb => cb !== callback);
  }

  emit(type, payload) {
    (this.listeners[type] || []).forEach(cb => cb(payload));
  }
}

export const eventBus = new EventBus();