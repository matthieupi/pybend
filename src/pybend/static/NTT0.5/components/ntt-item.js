import { PTT } from '../core/NTT.js';
export class Item extends HTMLElement {
  
  #model = "";
  #proto = {};
  #hash = "";
  #data = {};
  
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.mode = this.getAttribute('mode') || 'display';
    this.#model = this.getAttribute('model') || undefined;
    this.#hash = this.getAttribute('hash') || undefined;
    // Register to get schema eventually
    //NTT.attach(this.#model, this.#hash, this.update.bind(this))
    
  }
  
  static get observedAttributes() {
    return ['mode', 'model', 'hash'];
  }
  
  static get observedProperties() {}

  connectedCallback() {
    if (!this.#proto) {
      // Set placeholder content
      this.shadowRoot.innerHTML = `
        <h1>${this.model ? this.model : "Item"} Placeholder</h1>
        <div class="card">
            <button class="edit-btn" title="Toggle Edit">✏️</button>
        </div>
        <h4>Mode: ${this.mode}</h4>
        <div class="content"></div>
        `;
    }
    
  }

  get value() { return this.#data; }
  set value(obj) {
    this.#data = obj;
    console.log(`Setting value in Item:`, obj);
    this.render();
  }

  get model() { return this.#model; }
  set model(model) {
    if (model !== this.#model) {
      this.#model = model;
      this.render();
    }
  }
  
  get schema() { return this.#proto?.schema; }
  
  inbox(event) {
    if (this.hasAttribute(event.name) && typeof this[event.name] === 'function') {
      console.warn(`Event ${event.name} received in Item:`, event);
      this[event.name](event.data);
    }
  }
  
  describe(proto, data={}) {
    if (!this.#model) { this.#model = proto.__name__}
    this.#proto = proto;
    this.value = data;
  }
  
  update(data) { this.value = data; }

  toggleMode() {
    this.mode = this.mode === 'edit' ? 'display' : 'edit';
    this.render();
  }

  render() {
    const styles = `
      <style>
        .card { background: #2c2f4a; border-radius: 1rem; padding: 1rem; color: #fff; position: relative; }
        .edit-btn {
          position: absolute; top: 10px; right: 10px;
          cursor: pointer; background: none; border: none;
          font-size: 1.2em; color: #aaa;
        }
        label { font-weight: bold; display: block; margin-top: .5rem; }
        input, textarea {
          width: 100%; padding: .3rem; margin-bottom: .5rem;
          background: #1e1e2f; border: 1px solid #444; color: white;
        }
      </style>
    `;
  
    const fields = this.schema?.properties || {};
    const html = [];

    html.push(`<button class="edit-btn" title="Toggle Edit">✏️</button>`);
    console.warn(`Rendering ${this.#model} item: ${this.value?.name}`);

    for (const key in fields) {
      const def = fields[key];
      const label = def.title || key;
      const type = def.type || 'string';
      const value = this.value?.[key] ?? '';

      if (this.mode === 'edit') {
        if (type === 'boolean') {
          html.push(`
            <label>${label}</label>
            <input type="checkbox" id="${key}" ${value ? 'checked' : ''}>
          `);
        } else {
          html.push(`
            <label>${label}</label>
            <input type="${type === 'number' ? 'number' : 'text'}" id="${key}" value="${value}">
          `);
        }
      } else {
        html.push(`
          <label>${label}</label>
          <div>${value}</div>
        `);
      }
    }

    this.shadowRoot.innerHTML = `${styles}<div class="card">${html.join('')}</div>`;
    this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', () => this.toggleMode());
  }
}

customElements.define('ntt-item', Item);
