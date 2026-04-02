/**
 * NTTRefPicker — Dropdown picker + inline create for ref list fields.
 *
 * Renders an "Add" button that opens a dropdown with:
 *   - Search input to filter existing instances
 *   - Clickable options from the NTT registry
 *   - "Create New" button that opens an inline form
 *
 * Used by form.js getListInput() in edit mode for array fields with $ref items.
 *
 * Attributes:
 *   field       — parent field key (e.g. "tools", "comments")
 *   model       — child model name (e.g. "AgentTool", "Comment")
 *   parent-model — parent schema __name__ (e.g. "AgentActor")
 *   parent-table — parent schema __tablename__ (e.g. "agent_actors")
 *   parent-id   — parent entity ID
 *   child-table — child schema __tablename__ (e.g. "agent_tools")
 *
 * Events:
 *   ref-added   — dispatched after an item is added (detail: {field, ref, data})
 *   ref-created — dispatched after inline create submits (detail: {field, data})
 */
import { NTT } from '../core/NTT.js';
import { config } from '../config.js';
import { Formidable } from '../generators/form.js';
import TX from '../core/TX.js';

const STYLES_URL = new URL('./ntx-ref-picker.css', import.meta.url).href;

export class NTTRefPicker extends HTMLElement {

  #open = false;
  #mode = 'closed'; // 'closed' | 'picker' | 'create'

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._onOutsideClick = this._onOutsideClick.bind(this);
  }

  static get observedAttributes() {
    return ['field', 'model', 'parent-model', 'parent-table', 'parent-id', 'child-table'];
  }

  connectedCallback() {
    this._render();
  }

  disconnectedCallback() {
    document.removeEventListener('click', this._onOutsideClick);
  }

  get field()       { return this.getAttribute('field'); }
  get modelName()   { return this.getAttribute('model'); }
  get parentModel() { return this.getAttribute('parent-model'); }
  get parentTable() { return this.getAttribute('parent-table'); }
  get parentId()    { return this.getAttribute('parent-id'); }
  get childTable()  { return this.getAttribute('child-table') || (this.modelName?.toLowerCase() + 's'); }
  get deferSave()   { return this.getAttribute('defer-save') === 'true'; }

  /** Collect current refs from the parent ntx-item to filter duplicates. */
  get currentRefs() {
    const refs = new Set();
    // Walk up to the host (ntx-item shadow root → ntx-item)
    const host = this.getRootNode()?.host;
    if (!host?.value) return refs;
    const arr = host.value[this.field];
    if (Array.isArray(arr)) {
      arr.forEach(item => {
        const ref = typeof item === 'string' ? item : item?.$id;
        if (ref) refs.add(ref);
      });
    }
    return refs;
  }

  /** Get the child schema from the parent's $defs. */
  get childSchema() {
    const host = this.getRootNode()?.host;
    return host?.schema?.$defs?.[this.modelName] || null;
  }

  // ── Rendering ──

  _render() {
    this.shadowRoot.innerHTML = `
      <link rel="stylesheet" href="${STYLES_URL}">
      <div class="ref-picker-shell">
        <button type="button" class="add-btn">+ Add ${this.modelName || 'Item'}</button>
        <div class="dropdown-anchor"></div>
      </div>
    `;

    this.shadowRoot.querySelector('.add-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      if (this.#mode === 'closed') {
        this._showPicker();
      } else {
        this._close();
      }
    });
  }

  _showPicker() {
    this._close();
    this.#mode = 'picker';

    const DC = NTT.get(this.modelName);
    if (!DC) return;

    // Trigger a READ if no instances loaded yet
    if (!DC.instances || DC.instances.size === 0) {
      DC.call('READ', {});
    }

    const currentRefs = this.currentRefs;
    const anchor = this.shadowRoot.querySelector('.dropdown-anchor');

    const dropdown = document.createElement('div');
    dropdown.className = 'picker-dropdown';
    dropdown.innerHTML = `
      <input type="text" class="picker-search" placeholder="Search ${this.modelName}..." />
      <div class="picker-options"></div>
      <button type="button" class="picker-create-btn">+ Create New ${this.modelName}</button>
    `;
    anchor.appendChild(dropdown);

    const optionsDiv = dropdown.querySelector('.picker-options');
    const searchInput = dropdown.querySelector('.picker-search');

    const renderOptions = (filter = '') => {
      optionsDiv.innerHTML = '';
      const lowerFilter = filter.toLowerCase();
      const instances = DC.instances || new Map();
      let count = 0;
      instances.forEach((entity) => {
        const val = entity.value || entity;
        const href = val.$id || `${config.API_URL}/${this.childTable}/${val.id}`;
        if (currentRefs.has(href)) return;
        const name = val.name || val.title || `${this.modelName} #${val.id}`;
        if (lowerFilter && !name.toLowerCase().includes(lowerFilter)) return;
        const opt = document.createElement('div');
        opt.className = 'picker-option';
        opt.textContent = name;
        opt.addEventListener('click', (e) => {
          e.stopPropagation();
          this._addRef(val.id, val);
          this._close();
        });
        optionsDiv.appendChild(opt);
        count++;
      });
      if (count === 0) {
        optionsDiv.innerHTML = `<div class="picker-empty">No items found</div>`;
      }
    };

    renderOptions();
    searchInput.focus();
    searchInput.addEventListener('input', () => renderOptions(searchInput.value));
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this._close();
    });

    dropdown.querySelector('.picker-create-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this._close();
      this._showInlineCreate();
    });

    // Close on outside click
    setTimeout(() => document.addEventListener('click', this._onOutsideClick), 0);
  }

  _showInlineCreate() {
    this._close();
    this.#mode = 'create';

    const childSchema = this.childSchema;
    if (!childSchema) return;

    const anchor = this.shadowRoot.querySelector('.dropdown-anchor');
    const form = document.createElement('div');
    form.className = 'inline-create';
    form.innerHTML = `
      <div class="inline-create-header">New ${this.modelName}</div>
      <div class="inline-create-body">
        ${Formidable.getForm({ schema: childSchema, value: {}, name: this.modelName }, 'edit')}
      </div>
      <div class="inline-create-footer">
        <button type="button" class="inline-create-cancel">Cancel</button>
        <button type="button" class="inline-create-submit">Create</button>
      </div>
    `;
    anchor.appendChild(form);

    const firstInput = form.querySelector('input, textarea');
    if (firstInput) firstInput.focus();

    form.querySelector('.inline-create-cancel').addEventListener('click', (e) => {
      e.stopPropagation();
      this._close();
    });

    form.querySelector('.inline-create-submit').addEventListener('click', (e) => {
      e.stopPropagation();
      this._submitCreate(form);
    });

    form.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { this._close(); return; }
      if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        this._submitCreate(form);
      }
    });
  }

  // ── Actions ──

  _addRef(id, entity) {
    if (!this.deferSave) {
      const url = `${config.API_URL}/${this.parentTable}/${this.parentId}/${this.childTable}`;
      const DC = NTT.get(this.modelName);
      if (DC) {
        DC.send(new TX({
          name: 'CREATE',
          target: url,
          data: entity,
          meta: { inbox: '_response_' }
        }));
      }
    }

    // Optimistic update on parent
    const href = entity.$id || `${config.API_URL}/${this.childTable}/${id}`;
    this.dispatchEvent(new CustomEvent('ref-added', {
      bubbles: true, composed: true,
      detail: { field: this.field, ref: href, data: entity }
    }));
  }

  _submitCreate(form) {
    const data = {};
    form.querySelectorAll('[data-key]').forEach(el => {
      const key = el.dataset.key;
      const type = el.dataset.type;
      if (type === 'boolean' || el.type === 'checkbox') {
        data[key] = el.checked;
      } else if (type === 'number') {
        data[key] = parseFloat(el.value);
      } else if (type === 'object') {
        try { data[key] = JSON.parse(el.value); } catch { data[key] = el.value; }
      } else {
        data[key] = el.value;
      }
    });

    const url = `${config.API_URL}/${this.parentTable}/${this.parentId}/${this.childTable}`;
    const DC = NTT.get(this.modelName);
    if (DC) {
      DC.send(new TX({
        name: 'CREATE',
        target: url,
        data: data,
        meta: { inbox: '_response_' }
      }));
    }

    this._close();

    this.dispatchEvent(new CustomEvent('ref-created', {
      bubbles: true, composed: true,
      detail: { field: this.field, data }
    }));

    // Refresh parent entity to pick up the new child
    const parentEntity = NTT.get(`${this.parentModel}/${this.parentId}`);
    if (parentEntity?.pull) {
      setTimeout(() => parentEntity.pull(), 300);
    }
  }

  // ── Lifecycle helpers ──

  _close() {
    this.#mode = 'closed';
    const anchor = this.shadowRoot.querySelector('.dropdown-anchor');
    if (anchor) anchor.innerHTML = '';
    document.removeEventListener('click', this._onOutsideClick);
  }

  _onOutsideClick(e) {
    if (!this.contains(e.target) && !this.shadowRoot.contains(e.target)) {
      this._close();
    }
  }
}

customElements.define('ntx-ref-picker', NTTRefPicker);
