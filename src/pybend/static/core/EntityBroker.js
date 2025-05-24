import { Event } from './Event.js';
import { transport } from './TransportManager.js';

let API_URL = "http://localhost:8000/api/"

export default class EntityBroker {
  static data = {}
  static store = {}
  static factory = {}
  static prototypes = {}

  static discover(url) {
    const evt = new Event({ name: 'load', source: 'EntityBroker', target: 'api', data: { url }, meta: { type: 'discover' } });
    evt.data.onSuccess = (data) => {
      for (const [key, value] of Object.entries(data.$defs || {})) {
        let prototype = value;
        // Register prototype if needed
      }
      EntityBroker.prototypes = data;
      console.log(data);
    };
    evt.data.onError = (error) => console.log(error);
    transport.send(evt);
  }

  static register(uuid, model, onSuccess, onError, url = API_URL) {
    EntityBroker.factory[uuid] = {
      url: url,
      data: undefined,
      model: model,
      onSuccess: onSuccess,
      onError: onError
    };
  }

  static set(uuid, value) {
    EntityBroker.data[uuid] = value;
    if (EntityBroker.factory[uuid]?.onSuccess) {
      EntityBroker.factory[uuid].onSuccess(value);
    }
  }

  static create(uuid, data) {
    const factory = EntityBroker.factory[uuid];
    const evt = new Event({ name: 'create', source: uuid, target: 'api', data: { url: factory.url, data, onSuccess: factory.onSuccess, onError: factory.onError } });
    transport.send(evt);
  }

  static update(uuid, data, idx = -1) {
    const factory = EntityBroker.factory[uuid];
    const evt = new Event({ name: 'update', source: uuid, target: 'api', data: { url: factory.url, data, onSuccess: (resp) => {
      if (idx === -1) EntityBroker.data[uuid] = resp;
      else EntityBroker.data[uuid][idx] = resp;
      factory.data = resp;
      factory.onSuccess(resp);
    }, onError: factory.onError } });
    transport.send(evt);
  }

  static pull(uuid) {
    const factory = EntityBroker.factory[uuid];
    const evt = new Event({ name: 'load', source: uuid, target: 'api', data: { url: factory.url, onSuccess: (data) => {
      factory.data = data;
      factory.onSuccess(data);
    }, onError: factory.onError } });
    transport.send(evt);
  }

  access(uuid) {
    return EntityBroker.data[uuid];
  }
}

window.EntityBroker = new EntityBroker();