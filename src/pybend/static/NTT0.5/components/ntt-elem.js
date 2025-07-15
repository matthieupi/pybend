import {registry} from '../core/registrar.js';
import './ntt-item.js';
import {PTT} from '../core/NTT.js';
import {generateId} from "../core/Utils.js";

export class NTTElement extends HTMLElement {
  
  #addr;
  #model;
  #proto= {};
  #hash;
  #data;
  #unsubscribe = undefined;
  #detach = undefined;
  
  constructor() {
    super();
    this.attachShadow({mode: 'open'});
    
    this.#model = this.getAttribute('model') || undefined;
    this.#hash = this.getAttribute('hash') || undefined;
    this.#addr = this.getAttribute('addr') || `${generateId()}-${this.#model}`;
    
    this.describe = this.describe.bind(this);
    this.inbox = this.inbox.bind(this);
    
    registry.set(this.#addr, this);
  }
  
  static get observedAttributes() {
    //throw new Error(`Not implemented error: observedAttributes must be defined in ${this.name} class.`);
  }
  
  connectedCallback() {
    this.#detach?.()
    this.#detach = PTT.attach(this.model, this.describe);
  }
  
  attributeChangedCallback(name, oldVal, newVal) {
    if (oldVal === newVal) return; // No change, no need to update
    
    if (name === 'model') {
      this.model = newVal;
      // Detach and reattach to the new model
      this.#detach?.();
      this.#detach = PTT.attach(newVal, this.describe);
    } else {
      this[name] = newVal;
    }
  }
  
  get value() {
    return this.#data || [];
  }
  
  set value(data) {
    this.#data = data;
    this.render();
  }
  
  get model() {
    return this.#model;
  }
  
  set model(model_name) {
    this.#model = model_name;
  }
  
  inbox(event) {
    let event_method = `_${event.name}_`;
    if (this.hasAttribute(event.name) && typeof this[event_method] === 'function') {
      console.warn(`Event ${event.name} received in List:`, event);
      this[event_method](event.data);
    } else {
      console.warn(`No handler for event ${event.name} in List`);
    }
  }
  
  describe(ptt) {
    if (!ptt.schema) return
    // Clean up previous subscription if it exists
    console.warn(`Describing List with model: ${this.#model}`, ptt);
    this.#proto = ptt;
    this.#unsubscribe?.();
    this.#unsubscribe = ptt.observe('UPDATE', this.update.bind(this));
    ptt.call('READ', {inbox: 'UPDATE'});
    this.render();
  }
  
  update(data) {
    console.warn(`Updating List with data: ${data}`);
    console.log(data);
    if (Array.isArray(data)) {
      this.value = data;
    } else {
      console.warn('Data must be an array');
    }
  }
  
  
  render() {
    throw new Error(`Not implemented error: Render method must be implemented in ${this.constructor.name} class.`);
  }
}

customElements.define('ntt-element', NTTElement);
