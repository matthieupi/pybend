import './ntt-item.js';
import './ntt-element.js';
import { PTT } from '../core/NTT.js';
import {generateId} from "../core/Utils.js";
import {NTTElement} from "./ntt-element.js";

export class List extends NTTElement {
  
  constructor() {
    super([]);
  }
  
  definedCallback() {
    this.subscribe(this.proto, 'UPDATE', this.update.bind(this));
    this.proto.call('READ', {inbox: 'UPDATE'});
  }
  
  append(data) {
    console.warn(`Appending data to List: ${data}`);
    if (Array.isArray(data)) {
      super.value = [...this.value, ...data];
    } else {
      console.warn('Data must be an array');
    }
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
      console.log(`Describing item with model: ${this.model}`, item);
      el.describe(this.proto, item);
      this.shadowRoot.appendChild(el);
    });
  }
}

customElements.define('ntt-list', List);
