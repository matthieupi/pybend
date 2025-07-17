import {registry} from '../core/registrar.js';
import './ntt-item.js';
import {PTT} from '../core/NTT.js';
import {isEmpty, generateId} from "../core/Utils.js";

export class NTTElement extends HTMLElement {
  
  #addr;
  #model;
  #proto = {};
  #hash;
  #data;
  #defaultValue = {};
  #unsubscribe = undefined;
  #detach = undefined;
  
  constructor(defaultValue={}) {
    super();
    this.attachShadow({mode: 'open'});
    this.#model = this.getAttribute('model') || undefined;
    this.#hash = this.getAttribute('hash') || undefined;
    this.#addr = this.getAttribute('addr') || `${generateId()}-${this.#model}`;
    this.#data = defaultValue;
    this.#defaultValue = defaultValue;
    
    this.describe = this.describe.bind(this);
    this.define = this.define.bind(this);
    //this.inbox = this.inbox.bind(this);
    
    registry.set(this.#addr, this);
  }
  
  static get observedAttributes() {
    return ['model', 'addr', 'hash'];
  }
  
  connectedCallback() {
    if (this.model){
      this.#detach?.()
      this.#detach = PTT.attach(this.model, this.define);
    }
  }
  
  definedCallback() {
    // This method should be implemented in subclasses to handle specific initialization logic
  }
  
  attributeChangedCallback(name, oldVal, newVal) {
    if (oldVal === newVal) return; // No change, no need to update
    
    if (name === 'model') {
      this.model = newVal;
      // Detach and reattach to the new model
      this.#detach?.();
      this.#detach = PTT.attach(newVal, this.define);
    } else {
      this[name] = newVal;
    }
  }
  
  disconnectedCallback() {
    this.#detach?.();
    this.#unsubscribe?.();
  }
  
  get schema() { return this.#proto?.schema || {}; }
  
  get proto() { return this.#proto; }
  
  get value() { return this.#data || this.#defaultValue; }
  set value(data) {
    console.log(`Setting value in ${this.constructor.name}:`, data)
    if (typeof data !== typeof this.#defaultValue) {
        console.warn(`Data type mismatch: Expected ${typeof this.#defaultValue}, got ${typeof data} in ${this.constructor.name}.`);
        return;
    }
    if (data !== this.value){
      this.#data = data;
      this.render();
    }
  }
  
  get model() { return this.#model; }
  set model(model_name) {
    this.#model = model_name;
  }
  
  //inbox(event) {
  //  let event_method = `_${event.name}_`;
  //  if (this.hasAttribute(event.name) && typeof this[event_method] === 'function') {
  //    console.warn(`Event ${event.name} received in Element:`, event);
  //    this[event_method](event.data);
  //  } else {
  //    console.warn(`No handler for event ${event.name} in List`);
  //  }
  //}
  
  define(ptt) {
    console.warn(`Defining Element with model: ${this.#model}`, ptt);
    if (!ptt.schema || ptt.schema.__name__ === this.#proto?.schema?.__name__) return;
    if (!this.model) {this.model = ptt.schema.__name__;}
    this.#proto = ptt;
    this.definedCallback();
  }
  
  describe(proto, data) {
    console.warn(`Describing List with model: ${this.#model}`, proto);
    if (!proto.schema) return
    // Clean up previous subscription if it exists
    if (!this.#model) { this.#model = proto.schema.__name__ }
    this.#proto = proto;
    this.value = data || this.#defaultValue;
  }
  
  update(data) {
    if (!data) return
    this.value = data;
  }
  
  subscribe(tt, attribute, callback) {
    this.#unsubscribe?.();
    this.#unsubscribe = tt.observe(attribute, callback);
  }
  
  attach(addr) {
    this.#detach?.();
    this.#detach = PTT.attach(addr, this.define);
  }
  
  render() {
    throw new Error(`Not implemented error: Render method must be implemented in ${this.constructor.name} class.`);
  }
}

customElements.define('ntt-element', NTTElement);
