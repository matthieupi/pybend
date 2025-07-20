import { PTT } from '../core/NTT.js';
import { NTTElement} from "./ntt-element.js";
import {NTTMethod} from "./ntt-method.js";
import {Formidable} from '../generators/form.js';

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
       // Save triggered
       if (this.value?.call && typeof this.value.call === 'function') {
         console.warn(`[ntt-item] Dispatching update for`, this.value);
         this.value.call('UPDATE', this.value.value);
       } else if (this.proto?.call) {
         this.proto.call('UPDATE', this.value.value);
       } else {
         console.warn(`[ntt-item] No update method found for`, this.value);
       }
     }
  
     this.mode = isEdit ? 'display' : 'edit';
     this.render();
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
  
    console.warn(`[ntt-item] Updated "${key}" →`, newValue, 'Current state:', this.value);
  }


render() {
  console.log(`Rendering Item: ${this.model}, Mode: ${this.mode}`, this.value, this.schema, this.proto);

  if (this.value?.name) console.warn(`Rendering ${this.model} item: ${this.value?.name}`);

  const fields = this.schema?.properties || {};
  const methods = this.schema?.methods || {};
  const html = [];

  const icon = this.mode === 'edit' ? '💾' : '✏️';
  html.push(`<button class="edit-btn" title="${this.mode === 'edit' ? 'Save' : 'Edit'}">${icon}</button>`);

  html.push(Formidable.getForm(this.value, this.mode));

  for (const methodName in methods) {
    const methodSchema = methods[methodName];
    const label = methodSchema.title || methodName;

    if (this.mode !== 'edit') {
      html.push(`
        <ntt-method
          model="${this.model}"
          uuid="${this.value?.addr || ''}"
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
