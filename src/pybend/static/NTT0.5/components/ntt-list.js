import './ntt-item.js';
import './ntt-elem.js';
import { PTT } from '../core/NTT.js';
import {generateId} from "../core/Utils.js";

export class List extends HTMLElement {
  
  #addr;
  #model;
  #proto= {};
  #hash;
  #data = [];
  #unsubscribe = undefined;
  #detach = undefined;
  
  constructor() {
    super();
    this.attachShadow({mode: 'open'});
    this.#model = this.getAttribute('model') || undefined;
    this.#hash = this.getAttribute('hash') || undefined;
    this.#addr = this.getAttribute('addr') || `${generateId()}-${this.#model}-list`;
    this.describe = this.describe.bind(this);
  }
  
  static get observedAttributes() {
    return ['model', 'hash'];
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
  
  set value(items) {
    if (!Array.isArray(items)) {
      console.warn('Value must be an array');
      return;
    }
    this.#data = items;
    this.render();
  }
  
  get model() {
    return this.#model;
  }
  
  set model(ptt) {
    this.#model = ptt;
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
  
  append(data) {
    console.warn(`Appending data to List: ${data}`);
    if (Array.isArray(data)) {
      this.value = [...this.value, ...data];
    } else {
      console.warn('Data must be an array');
    }
  }
  
  render() {
    if (!this.#proto || !Array.isArray(this.value)) return;
    
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: grid;
          gap: 1rem;
        }
      </style>
      <h1>List of ${this.#model}</h1>
    `;
    
    this.value.forEach(item => {
      const el = document.createElement('ntt-item');
      el.model = this.#model;
      el.describe(this.#proto, item);
      this.shadowRoot.appendChild(el);
    });
  }
}

customElements.define('ntt-list', List);
