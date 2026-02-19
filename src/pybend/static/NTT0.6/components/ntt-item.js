import { NTTElement} from "./ntt-element.js";
import {NTT} from '../core/NTT.js';
import {NTTMethod} from "./ntt-method.js";
import {Formidable} from '../generators/form.js';
import Logging from "../utils/Logging.js";
import assert from "../utils/Assert.js";
import TX from "../core/TX.js";

export class Item extends NTTElement {
  
  
  constructor() {
    super({});
    this.mode = this.getAttribute('mode') || 'display';
    //NTT.attach(this.#model, this.#hash, this.update.bind(this))
    const $link = document.createElement('link');
    $link.setAttribute('rel', 'stylesheet');
    $link.setAttribute('href', new URL('./ntt-item.css', import.meta.url));
    this.shadowRoot.appendChild($link);
    this.$styles = $link
    this.$schema = undefined

  }
  
  UPDATE(data) {
    console.warn(`Received UPDATE for Item: ${this.model}`)
    console.error(data)
    console.log(this)
    assert(this, "$schema" in data, "UPDATE data missing $schema field");
    Logging.dev(`[NTT-ITEM] ${this.schema.__name__} - Updated Item value: ${this.value}`, data);
    this.value = data;
    const schemaName = data['$schema']?.split('/').pop();
    if (this.$schema !== schemaName){
        this.$schema = schemaName;
        this.send(new TX({
            name: 'CONNECT',
            source: this.addr,
            target: this.$schema
        }))
    }
  }
  
  READ(data) {
    // Response from direct URL href fetch (ListRef resolution)
    const modelName = this.getAttribute('data-model');
    const DynClass = modelName ? NTT.get(modelName) : null;
    if (DynClass) {
        this.schema = DynClass._schema;
        this.value = data;
        this.render();
    }
  }

  DESCRIBE(data) {
    Logging.dev(`[NTT-ITEM ${this.model}] Received DESCRIBE`, data);
    this.schema = data.proto
    this.value = data.data
    this.render()
  }
  
  connectedCallback() {
    super.connectedCallback();
    // Set placeholder content
    if (!this.proto) {
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
  
   toggleMode() {
     const isEdit = this.mode === 'edit';
     if (isEdit) {
       this.save()
     }
     this.mode = isEdit ? 'display' : 'edit';
     this.render();
   }
   
   save() {
        this.send(new TX({
         name: 'UPDATE',
         source: this.addr,
         target: this.ref,
         data: this.value
       }));
   }

  handleInputChange(e) {
    const el = e.target;
    const key = el.dataset.key;
    const index = el.dataset.index;
    const type = el.dataset.type;
  
    let newValue;
    if (type === 'boolean' || el.type === 'checkbox') {
      newValue = el.checked;
    } else if (type === 'number') {
      newValue = parseFloat(el.value);
    } else {
      newValue = el.value;
    }
  
    if (index !== undefined) {
      // Array update
      const idx = parseInt(index);
      if (!Array.isArray(this.value[key])) this.value[key] = [];
      this.value[key][idx] = newValue;
    } else {
      // Scalar update
      this.value[key] = newValue;
    }
  }


render() {
  
  console.warn(`Rendering Item: ${this.addr}`)
  if (this.value?.name) Logging.debug(`Rendering ${this.model} item: ${this.value?.name}`);
  
  const fields = this.schema?.properties || {};
  const methods = this.schema?.methods || {};
  const html = [];
  
  const icon = this.mode === 'edit' ? '💾' : '✏️';
  html.push(`<button class="edit-btn" title="${this.mode === 'edit' ? 'Save' : 'Edit'}">${icon}</button>`);
  
  html.push(Formidable.getForm({schema: this.schema, value: this.value}, this.mode));
  
  for (const methodName in methods) {
    const methodSchema = methods[methodName];
    const label = methodSchema.title || methodName;
    
    if (this.mode !== 'edit') {
      html.push(`
        <ntt-method
          model="${this.schema?.__name__ || ''}"
          uuid="${this.value?.id || ''}"
          method="${methodName}"
          label="${label}">
        </ntt-method>
      `);
    }
  }
  
  this.shadowRoot.innerHTML = `<div class="card">${html.join('')}</div>`;
  this.shadowRoot.appendChild(this.$styles);
  
  this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', () => this.toggleMode());
  
  this.shadowRoot.querySelectorAll('input, textarea').forEach(el => {
    const type = el.type;
    const event = (type === 'checkbox') ? 'change' : 'input';
    el.addEventListener(event, e => this.handleInputChange(e));
  });
}

}

customElements.define('ntt-item', Item);
