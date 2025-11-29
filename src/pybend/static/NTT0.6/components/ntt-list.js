import './ntt-item.js';
import './ntt-element.js';
import { PTT } from '../core/NTT.js';
import {generateId} from "../core/Utils.js";
import {NTTElement} from "./ntt-element.js";
import Logging from "../utils/Logging.js";

export class List extends NTTElement {
  
  constructor() {
    super([]);
  }
  
  connectedCallback() {
    super.connectedCallback();
  }
  
  definedCallback() {
    this.subscribe(this.proto, 'UPDATE', this.update.bind(this));
    this.proto.call('READ', {}, {inbox: 'UPDATE'});
  }
  
  append(data) {
    console.warn(`Appending data to List: ${data}`);
    if (Array.isArray(data)) {
      super.value = [...this.value, ...data];
    } else {
      console.warn('Data must be an array');
    }
  }
  
  update(data) {
    if (Array.isArray(data)) {
      const valueArray = data.map(item => (this.proto.new(item)))
      Logging.dev(`[NTT-LIST] ${this.schema.__name__} - Updated List value: ${this.value}`, valueArray);
      this.value = valueArray;
    } else {
      console.warn('Data must be an array');
    }
    this.render();
  }
  
  
  render() {
    if (!this.schema || !Array.isArray(this.value)) return;
    
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: grid;
          gap: 1rem;
        }
      </style>
      <h1>List of ${this.model}</h1>
    `;
    
    this.value.forEach(item => {
      const el = document.createElement('ntt-item');
      el.model = this.model;
      Logging.debug(`Describing item with model: ${this.model}`, [typeof item, item.addr, item]);
      el.describe(this.proto, item);
      this.shadowRoot.appendChild(el);
    });
  }
}

customElements.define('ntt-list', List);
