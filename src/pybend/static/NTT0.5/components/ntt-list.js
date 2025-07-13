import './ntt-item.js';
import { PTT } from '../core/NTT.js';

export class List extends HTMLElement {
  
    #model = "";
    #proto = {};
    #hash = "";
    #data = [];
    
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.#model = this.getAttribute('model') || undefined;
    this.#hash = this.getAttribute('hash') || undefined;
  }

  static get observedAttributes() {
    return ['model', 'hash'];
  }
  
    connectedCallback() {
    console.warn(`List component connected with model: ${this.#model}, hash: ${this.#hash}`);
    PTT.attach(this.model, this.describe.bind(this));
    
    }

  attributeChangedCallback(name, oldVal, newVal) {
    this[name] = newVal;
    // Todo - Ensure rerenders happens correctly in setter
  }


  get value() { return this.#data || []; }
  set value(items) {
    if (!Array.isArray(items)) {
      console.warn('Value must be an array');
      return;
    }
    this.#data = items;
    this.render();
  }

  get model() { return this.#model; }
  set model(ptt) { this.#model = ptt; }
  
  describe(ptt) {
    console.warn(`Describing List with model: ${ptt}`)
    console.log(ptt)
    this.#proto = ptt;
    ptt.observe('UPDATE', this.update.bind(this));
    ptt.call('READ', {inbox: 'UPDATE'} );
    // TODO - Pull the list
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
    console.log()

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
      console.log(`Describing item with model: ${this.#model}`, item);
      el.describe(this.#proto, item);
      this.shadowRoot.appendChild(el);
    });
  }
}

customElements.define('ntt-list', List);
