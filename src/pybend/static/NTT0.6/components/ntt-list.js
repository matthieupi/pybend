import './ntt-item.js';
import './ntt-element.js';
import {generateId} from "../core/Utils.js";
import {NTTElement} from "./ntt-element.js";
import Logging from "../utils/Logging.js";
import Observable from "../core/Observable.js";
import Actor from "../core/Actor.js";

export class List extends NTTElement {

  constructor() {
    super();
    const $link = document.createElement('link');
    $link.setAttribute('rel', 'stylesheet');
    $link.setAttribute('href', new URL('./ntt-list.css', import.meta.url));
    this.shadowRoot.appendChild($link);
    this.$styles = $link;
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
  
  UPDATE(data){
    Logging.dev(`[NTT-LIST] ${this.schema.__name__} - Updated List value: ${this.value}`, data);
    if (Array.isArray(data)) {
      this.value = data;
      this.render();
    } else {
      console.warn('Data must be an array');
    }
  }
  
  render(children) {
    if (!this.schema || !Array.isArray(this.value)) return;
    console.warn(`Rendering List of ${this.model} with ${this.value.length} items.`)
    
    this.shadowRoot.innerHTML = `
      <div class="list-header">
        <h1>${this.model}s</h1>
        <span class="list-count">${this.value.length}</span>
      </div>
      <div class="list-grid"></div>
    `;
    this.shadowRoot.appendChild(this.$styles);

    const grid = this.shadowRoot.querySelector('.list-grid');
    this.value.forEach(item => {
      const el = document.createElement('ntt-item');
      Logging.debug(`Describing item with model: ${this.model}`, [typeof item, item.addr, item]);
      el.ref = item;
      grid.appendChild(el);
    });
  }
}

Actor.subclass(List);
customElements.define('ntt-list', List);
