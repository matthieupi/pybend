/**
 * NTTItem — Built-in default single entity component.
 *
 * Provides zero-config rendering for any model:
 *   - Schema-driven form via Formidable
 *   - Display / edit mode toggle
 *   - Method buttons via <ntt-method>
 *   - Adaptive display: xs (pill), sm (compact), md (card), lg/xl (detail)
 *
 * Size methods (xs, sm, md, lg, xl) return HTML strings.
 * render() dispatches to the current size method, commits DOM, and binds events.
 *
 * For custom rendering, extend NTTElement directly instead.
 */
import {NTTElement} from './NTTElement.js';
import {Formidable} from '../generators/form.js';
import {permissions} from '../utils/Permissions.js';
import TX from '../core/TX.js';
import './ntt-method.js';


export class NTTItem extends NTTElement {

  mode = 'display';

  get styles() { return new URL('./ntt-item.css', import.meta.url).href; }

  connectedCallback() {
    super.connectedCallback();
    // Show placeholder only if no schema has been set yet (via define() or DESCRIBE)
    if (!this.schema?.__name__) {
      this.shadowRoot.innerHTML = `
        <div class="card">
          <button class="edit-btn mode-display" title="Edit"></button>
          <h1>${this.model ? this.model : "Item"} Placeholder</h1>
          <h4>Mode: ${this.mode}</h4>
          <div class="content"></div>
        </div>
      `;
    }
  }

  /** ── Edit / Save toggle ── **/

  toggleMode() {
    if (!permissions.canAction(this.schema?.access, 'update')) return;
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


  /** ─────────────────────────────────────────── **/
  /**         Size Methods (return HTML strings)   **/
  /** ─────────────────────────────────────────── **/

  /** xs — Pill: entity name as a compact badge. */
  xs() {
    const name = this.value.name || this.value.title || this.schema.__name__;
    return `<span class="pill-label">${name}</span>`;
  }

  /** sm — Compact row: thumbnail + name + 2–3 key field values inline (no labels). */
  sm() {
    const name = this.value.name || this.value.title || this.schema.__name__;
    const fields = this.#topFields(3);
    const fieldHtml = fields.map(([key, def]) => {
      const val = this.value[key] ?? '';
      if ((def?.type === '$ref' || def?.$ref) && typeof val === 'string' && val.startsWith('http')) {
        const refModel = (def.$ref || '').split('/').pop();
        return `<span class="sm-field sm-ref"><ntt-item ref="${val}" display="xs" data-model="${refModel}"></ntt-item></span>`;
      }
      const display = def.ui?.widget === 'currency' && typeof val === 'number'
        ? `$${val.toFixed(2)}` : val;
      return `<span class="sm-field">${display}</span>`;
    }).join('');

    const thumb = this.value.image
      ? `<img class="sm-thumb" src="${this.value.image}" alt="" />`
      : '';
    return `
      ${thumb}
      <span class="sm-name">${name}</span>
      <span class="sm-fields">${fieldHtml}</span>
    `;
  }

  /** md — Card: image + edit button + full form + methods (current default). */
  md() {
    const html = [];
    const canUpdate = permissions.canAction(this.schema.access, 'update');
    if (canUpdate) {
      const modeClass = this.mode === 'edit' ? 'mode-edit' : 'mode-display';
      html.push(`<button class="edit-btn ${modeClass}" title="${this.mode === 'edit' ? 'Save' : 'Edit'}"></button>`);
    }
    if (this.value.image) {
      html.push(`<img class="card-image" src="${this.value.image}" alt="${this.value.name || ''}" />`);
    }

    // Split methods: attached go into form groups, standalone go at bottom
    const methods = this.schema.methods || {};
    const attached = {};
    const standalone = {};
    for (const [name, def] of Object.entries(methods)) {
      if (def.ui?.attach_to) attached[name] = def;
      else standalone[name] = def;
    }

    html.push(Formidable.getForm({schema: this.schema, value: this.value}, this.mode, attached));
    if (this.mode !== 'edit') {
      html.push(this.#standaloneMethodsHtml(standalone));
    }
    return html.join('');
  }

  /** lg — Detail: same as card (future: show normally-hidden fields). */
  lg() {
    return this.md();
  }

  /** xl — Page: same as card (future: full metadata, expanded children). */
  xl() {
    return this.md();
  }


  /** ─────────────────────────────────────────── **/
  /**         Render Dispatch                      **/
  /** ─────────────────────────────────────────── **/

  render() {
    if (!this.schema || !this.value) return;

    const size = this.displayMode;
    const html = (this[size] || this.md).call(this);

    this.shadowRoot.innerHTML = `<div class="card" data-display="${size}">${html}</div>`;
    if (this.$styles) this.shadowRoot.appendChild(this.$styles);

    this.#bindEvents();
    this[`${size}_mounted`]?.call(this);
  }


  /** ─────────────────────────────────────────── **/
  /**         Private Helpers                      **/
  /** ─────────────────────────────────────────── **/

  /** Bind event listeners to current shadow DOM contents. */
  #bindEvents() {
    // Edit button
    this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', () => this.toggleMode());

    // Input changes
    this.shadowRoot.querySelectorAll('input, textarea').forEach(el => {
      const event = (el.type === 'checkbox') ? 'change' : 'input';
      el.addEventListener(event, e => this.handleInputChange(e));
    });

    // Show-more toggle
    this.shadowRoot.querySelectorAll('.show-more-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const collapsed = btn.previousElementSibling;
        if (collapsed?.classList.contains('nested-collapsed')) {
          collapsed.classList.toggle('expanded');
          const count = collapsed.children.length;
          btn.textContent = collapsed.classList.contains('expanded')
            ? 'Show less' : `Show ${count} more`;
        }
      });
    });

    // Card click → SELECT (skip interactive elements and edit mode)
    if (this.mode !== 'edit') {
      this.shadowRoot.querySelector('.card')?.addEventListener('click', (e) => {
        if (e.target.closest('button, input, textarea, select, a, ntt-method')) return;
        const target = this.getAttribute('select-target');
        if (target) {
          this.send(new TX({
            name: 'SELECT', source: this.addr, target: target, data: this.ref
          }));
        }
      });
    }
  }

  /**
   * Return the top N visible, non-header, non-array fields as [key, def] pairs.
   * Respects ui.field_order and ui.display.
   */
  #topFields(count) {
    const schema = this.schema;
    const fields = schema.properties || {};
    const ui = schema.ui || {};
    const skip = new Set(['name', 'id']);

    const order = ui.field_order
      ? ui.field_order.filter(k => k in fields)
      : Object.keys(fields);
    // Safety: include any fields not in field_order
    for (const k of Object.keys(fields)) {
      if (!order.includes(k)) order.push(k);
    }

    return order
      .filter(key => {
        if (skip.has(key)) return false;
        const def = fields[key];
        if (def?.ui?.display === false) return false;
        if (def?.type === 'array') return false;
        if (def?.type === 'selfref') return false;
        if (!permissions.canView(def)) return false;
        return true;
      })
      .slice(0, count)
      .map(key => [key, fields[key]]);
  }

  /** Build HTML for standalone method buttons (those without ui.attach_to). */
  #standaloneMethodsHtml(methods) {
    return Object.entries(methods).map(([name, def]) => {
      const label = def.title || name;
      return `
        <ntt-method
          model="${this.schema?.__name__ || ''}"
          uuid="${this.value?.id || ''}"
          method="${name}"
          label="${label}">
        </ntt-method>
      `;
    }).join('');
  }
}

customElements.define('ntt-item', NTTItem);
