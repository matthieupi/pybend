/**
 * NTTItem — Built-in default single entity component.
 *
 * Provides zero-config rendering for any model:
 *   - Schema-driven form via Formidable
 *   - Display / edit mode toggle
 *   - Method buttons via <ntt-method>
 *
 * For custom rendering, extend NTTElement directly instead.
 */
import {NTTElement} from './NTTElement.js';
import {Formidable} from '../generators/form.js';
import './ntt-method.js';


export class NTTItem extends NTTElement {

  mode = 'display';

  get styles() { return new URL('./ntt-item.css', import.meta.url).href; }

  connectedCallback() {
    super.connectedCallback();
    if (!this.proto?.schema) {
      this.shadowRoot.innerHTML = `
        <div class="card">
          <button class="edit-btn" title="Toggle Edit">&#9999;&#65039;</button>
          <h1>${this.model ? this.model : "Item"} Placeholder</h1>
          <h4>Mode: ${this.mode}</h4>
          <div class="content"></div>
        </div>
      `;
    }
  }

  /** ── Edit / Save toggle ── **/

  toggleMode() {
    const isEdit = this.mode === 'edit';
    if (isEdit) this.save();
    this.mode = isEdit ? 'display' : 'edit';
    this.render();
  }

  /** ── Input change handler ── **/

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
      const idx = parseInt(index);
      if (!Array.isArray(this.value[key])) this.value[key] = [];
      this.value[key][idx] = newValue;
    } else {
      this.value[key] = newValue;
    }
  }

  /** ── Render ── **/

  render() {
    if (!this.schema || !this.value) return;

    const methods = this.schema.methods || {};
    const html = [];

    // Edit / save button
    const icon = this.mode === 'edit' ? '\u{1F4BE}' : '\u{270F}\u{FE0F}';
    html.push(`<button class="edit-btn" title="${this.mode === 'edit' ? 'Save' : 'Edit'}">${icon}</button>`);

    // Schema-driven form
    html.push(Formidable.getForm({schema: this.schema, value: this.value}, this.mode));

    // Method buttons (display mode only)
    if (this.mode !== 'edit') {
      for (const methodName in methods) {
        const methodSchema = methods[methodName];
        const label = methodSchema.title || methodName;
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

    // Commit to shadow DOM
    this.shadowRoot.innerHTML = `<div class="card">${html.join('')}</div>`;
    if (this.$styles) this.shadowRoot.appendChild(this.$styles);

    // Bind events
    this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', () => this.toggleMode());
    this.shadowRoot.querySelectorAll('input, textarea').forEach(el => {
      const event = (el.type === 'checkbox') ? 'change' : 'input';
      el.addEventListener(event, e => this.handleInputChange(e));
    });
  }
}

customElements.define('ntt-item', NTTItem);
