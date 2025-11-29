import './ntt-item.js';
import {PTT} from '../core/NTT.js';
import {isEmpty, generateId} from "../core/Utils.js";
import Logging from "../utils/Logging.js";
import {matrix} from "../core/Matrix.js";



export class NTTElement extends HTMLElement {
  
  #addr;
  #href;
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
    this.#hash = this.getAttribute('hash') || generateId();
    this.#addr = this.getAttribute('addr') || `${this.#model}-${this.#hash}`;
    this.#href = this.getAttribute('href') || undefined;
    this.#data = defaultValue;
    this.#defaultValue = defaultValue;
    
    this.describe = this.describe.bind(this);
    this.define = this.define.bind(this);
    matrix.register(this);
  }
  
  static get observedAttributes() {
    return ['model', 'addr', 'hash'];
  }
  
  get addr() { return this.#addr; }
  set addr(addr) {
    if (!this.#addr)
      this.#addr = addr;
    else if (this.#addr === addr)
      return;
    else
      throw new Error(`[NTT-${this.#addr}] Address is already set to ${this.#addr} and cannot be changed to ${addr}.`);
    
  }
  
  inbox(event) {
    throw new Error(`Not implemented error: Inbox method must be implemented in ${this.constructor.name} class.`);
  }
  
  connectedCallback() {
    Logging.debug(`[NTT-ELEMENT-${this.#hash}]`,`Connected with model: ${this.model}, addr: ${this.#addr}, hash: ${this.#hash}`)
    if (this.href){
        console.warn(`[NTT-ELEMENT] Detaching from previous href: ${this.#href}`);
        this.#detach?.();
        this.#detach = NTT.attach(this.href, this.define);
    }
    else if (this.model){
      this.#detach?.()
      this.#detach = PTT.attach(this.model, this.define);
    }
  }
  
  definedCallback() {
    console.log("PARENT DEFINEDCALLBACK")
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
    if (typeof data !== typeof this.#defaultValue) {
        Logging.dev(`Data type mismatch: Expected ${typeof this.#defaultValue}, got ${typeof data} in ${this.constructor.name}.`);
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
    Logging.debug(`[NTT-ELEMENT] ${this.model} - Defining Element with `, ptt);
    if (!ptt.schema || ptt.schema.__name__ === this.#proto?.schema?.__name__) return;
    if (!this.model) {this.model = ptt.schema.__name__;}
    this.#proto = ptt;
    this.definedCallback();
  }
  
  describe(proto, data) {
    if (!proto.schema) return
    // Clean up previous subscription if it exists
    if (!this.#model) { this.#model = proto.schema.__name__ }
    this.#proto = proto;
    this.value = data || this.#defaultValue;
  }
  
  update(data) {
    console.error(isEmpty(this.value), isEmpty(this.#data))
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
