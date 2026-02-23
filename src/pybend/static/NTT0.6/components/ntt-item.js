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
import {NTT} from '../core/NTT.js';
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

  /** ── Delete ── **/

  deleteItem() {
    if (!permissions.canAction(this.schema?.access, 'delete', this.value)) return;
    if (!confirm(`Delete this ${this.schema.__name__}?`)) return;
    // Use ref (the actual API endpoint URL) when available, otherwise fall back
    // to value.$id. For nested entities (e.g. comments inside products), ref holds
    // the correct CRUD path while $id may point to the schema-derived DynamicClass URL.
    const target = (this.ref && this.ref.startsWith('http')) ? this.ref : this.value.$id;
    // Route through DynamicClass so the response triggers DC.DELETE,
    // which removes the instance from the registry and notifies list watchers.
    const DC = NTT.get(this.schema.__name__);
    if (DC) {
      DC.send(new TX({
        name: 'DELETE',
        target: target,
        meta: { inbox: 'DELETE' },
      }));
    }
  }

  /** ── Edit / Save toggle ── **/

  toggleMode() {
    if (!permissions.canAction(this.schema?.access, 'update', this.value)) return;
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

  /**
   * sm — Compact row: leading element + name + inline field values.
   *
   * Respects field_order. If the first renderable field is a $ref,
   * it renders as a leading avatar/pill. Otherwise falls back to
   * the entity's image thumbnail. 'name' renders as the identity text.
   * Remaining fields fill the right side (up to 3 total).
   */
  sm() {
    // In edit mode, delegate to md() for the full form experience
    if (this.mode === 'edit') return this.md();

    const schema = this.schema;
    const props = schema.properties || {};
    const renderable = this.#smFields();

    let leadingHtml = '';
    let nameHtml = '';
    const smFields = [];

    // Action buttons (edit/delete) gated by permissions (resource-aware OWNER check)
    const canUpdate = permissions.canAction(schema.access, 'update', this.value);
    const canDelete = permissions.canAction(schema.access, 'delete', this.value);
    let actionsHtml = '';
    if (canUpdate || canDelete) {
      let btns = '';
      if (canDelete) btns += '<button class="delete-btn" title="Delete"></button>';
      if (canUpdate) {
        const modeClass = this.mode === 'edit' ? 'mode-edit' : 'mode-display';
        btns += `<button class="edit-btn ${modeClass}" title="${this.mode === 'edit' ? 'Save' : 'Edit'}"></button>`;
      }
      actionsHtml = `<span class="sm-actions">${btns}</span>`;
    }

    for (const key of renderable) {
      const def = props[key];
      const val = this.value[key] ?? '';

      // First $ref field → leading avatar (thumb position)
      if (!leadingHtml && (def?.type === '$ref' || def?.$ref)
          && typeof val === 'string' && val.startsWith('http')) {
        const refModel = (def.$ref || '').split('/').pop();
        const childTag = this.#resolveChildTag(refModel);
        leadingHtml = `<${childTag} ref="${val}" display="xs" data-model="${refModel}"></${childTag}>`;
        continue;
      }

      // 'name' field → sm-name identity text
      if (key === 'name' && !nameHtml) {
        nameHtml = `<span class="sm-name">${val || schema.__name__}</span>`;
        continue;
      }

      // Everything else → sm-field
      if (smFields.length >= 3) break;
      if ((def?.type === '$ref' || def?.$ref) && typeof val === 'string' && val.startsWith('http')) {
        const refModel = (def.$ref || '').split('/').pop();
        const childTag = this.#resolveChildTag(refModel);
        smFields.push(`<span class="sm-field sm-ref"><${childTag} ref="${val}" display="xs" data-model="${refModel}"></${childTag}></span>`);
      } else {
        const display = def?.ui?.widget === 'currency' && typeof val === 'number'
          ? `$${val.toFixed(2)}` : val;
        smFields.push(`<span class="sm-field">${display}</span>`);
      }
    }

    // Fallbacks
    if (!leadingHtml && this.value.image) {
      leadingHtml = `<img class="sm-thumb" src="${this.value.image}" alt="" />`;
    }
    if (!nameHtml) {
      const name = this.value.name || this.value.title || schema.__name__;
      nameHtml = `<span class="sm-name">${name}</span>`;
    }

    // When a $ref leads, stack name + fields vertically beside it
    if (leadingHtml && leadingHtml.includes('display="xs"')) {
      return `
        ${leadingHtml}
        <div class="sm-body">
          ${nameHtml}
          <span class="sm-fields">${smFields.join('')}</span>
        </div>
        ${actionsHtml}
      `;
    }
    return `
      ${leadingHtml}
      ${nameHtml}
      <span class="sm-fields">${smFields.join('')}</span>
      ${actionsHtml}
    `;
  }

  /** md — Card: image + edit/delete buttons + full form + methods (current default). */
  md() {
    const html = [];
    const canUpdate = permissions.canAction(this.schema.access, 'update', this.value);
    const canDelete = permissions.canAction(this.schema.access, 'delete', this.value);
    if (canUpdate || canDelete) {
      html.push('<div class="card-actions">');
      if (canDelete) {
        html.push('<button class="delete-btn" title="Delete"></button>');
      }
      if (canUpdate) {
        const modeClass = this.mode === 'edit' ? 'mode-edit' : 'mode-display';
        html.push(`<button class="edit-btn ${modeClass}" title="${this.mode === 'edit' ? 'Save' : 'Edit'}"></button>`);
      }
      html.push('</div>');
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

    // When editing in compact sizes, sm() delegates to md() for the full form.
    // Match the card layout so CSS styles apply correctly.
    const layoutSize = (this.mode === 'edit' && (size === 'sm' || size === 'xs')) ? 'md' : size;
    this.shadowRoot.innerHTML = `<div class="card" data-display="${layoutSize}">${html}</div>`;
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

    // Delete button
    this.shadowRoot.querySelector('.delete-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.deleteItem();
    });

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
   * Return ordered renderable field keys for sm() display.
   * Respects ui.field_order. Skips only id, hidden, array, and selfref fields.
   */
  #smFields() {
    const schema = this.schema;
    const fields = schema.properties || {};
    const ui = schema.ui || {};

    const order = ui.field_order
      ? ui.field_order.filter(k => k in fields)
      : Object.keys(fields);
    for (const k of Object.keys(fields)) {
      if (!order.includes(k)) order.push(k);
    }

    return order.filter(key => {
      if (key === 'id') return false;
      const def = fields[key];
      if (def?.ui?.display === false) return false;
      if (def?.type === 'array') return false;
      if (def?.type === 'selfref') return false;
      if (!permissions.canView(def)) return false;
      return true;
    });
  }

  /**
   * Resolve the child component tag for a $ref model.
   * Checks local $defs first, falls back to NTT registry.
   */
  #resolveChildTag(refModel) {
    const defs = this.schema?.$defs || {};
    const fromDefs = defs[refModel]?.ui?.renderer?.item;
    if (fromDefs) return fromDefs;
    const DC = NTT.get(refModel);
    return DC?.schema?.ui?.renderer?.item || 'ntt-item';
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
