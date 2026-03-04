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
      <style>${NTTRefPicker.styles}</style>
      <button type="button" class="add-btn">+ Add ${this.modelName || 'Item'}</button>
      <div class="dropdown-anchor"></div>
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

  // ── Styles ──

  static styles = `
    :host {
      display: block;
      position: relative;
    }

    .add-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      padding: 0.3rem 0.75rem;
      font-size: 0.75rem;
      font-weight: 500;
      font-family: inherit;
      color: var(--accent-text, #5eeadf);
      background: var(--accent-dim, rgba(34,211,197,0.12));
      border: 1px solid rgba(34, 211, 197, 0.15);
      border-radius: 100px;
      cursor: pointer;
      transition: all 0.2s;
      box-shadow: none;
    }
    .add-btn:hover {
      background: rgba(34, 211, 197, 0.18);
      border-color: rgba(34, 211, 197, 0.30);
    }

    .dropdown-anchor {
      position: relative;
    }

    /* ── Picker dropdown ── */
    .picker-dropdown {
      margin-top: 0.5rem;
      background: var(--glass-bg, rgba(14, 16, 24, 0.92));
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
      border: 1px solid var(--glass-border, rgba(255,255,255,0.09));
      border-radius: 12px;
      padding: 0.5rem;
      max-height: 300px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      box-shadow: 0 12px 40px rgba(0,0,0,.45);
      animation: fadeIn 0.2s ease both;
      z-index: 10;
    }

    .picker-search {
      width: 100%;
      padding: 0.45rem 0.65rem;
      font-size: 0.8rem;
      font-family: inherit;
      color: var(--text-0, #f0f2f8);
      background: var(--surface-1, #0e1018);
      border: 1px solid var(--border, rgba(255,255,255,0.06));
      border-radius: 6px;
      outline: none;
      margin-bottom: 0.35rem;
      transition: border-color 0.2s;
      box-sizing: border-box;
    }
    .picker-search:focus {
      border-color: var(--accent, #22d3c5);
      box-shadow: 0 0 0 2px rgba(34,211,197,0.12);
    }

    .picker-options {
      overflow-y: auto;
      max-height: 200px;
      display: flex;
      flex-direction: column;
      gap: 1px;
    }

    .picker-option {
      padding: 0.4rem 0.6rem;
      font-size: 0.8rem;
      color: var(--text-1, #c4c9da);
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.15s;
    }
    .picker-option:hover {
      background: rgba(34,211,197,0.12);
      color: var(--text-0, #f0f2f8);
    }

    .picker-empty {
      padding: 0.6rem;
      font-size: 0.78rem;
      color: var(--text-3, #555e78);
      text-align: center;
      font-style: italic;
    }

    .picker-create-btn {
      margin-top: 0.35rem;
      padding: 0.45rem 0.65rem;
      font-size: 0.78rem;
      font-weight: 500;
      font-family: inherit;
      color: var(--accent-text, #5eeadf);
      background: transparent;
      border: none;
      border-top: 1px solid var(--border, rgba(255,255,255,0.06));
      cursor: pointer;
      text-align: left;
      transition: background 0.15s;
      border-radius: 0 0 8px 8px;
    }
    .picker-create-btn:hover {
      background: rgba(34,211,197,0.08);
    }

    /* ── Inline create form ── */
    .inline-create {
      margin-top: 0.5rem;
      background: var(--glass-bg-light, rgba(22, 26, 38, 0.65));
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border: 1px solid rgba(34,211,197,0.20);
      border-radius: 12px;
      padding: 1rem;
      animation: fadeIn 0.25s ease both;
    }

    .inline-create-header {
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--accent-text, #5eeadf);
      margin-bottom: 0.5rem;
    }

    .inline-create-footer {
      display: flex;
      justify-content: flex-end;
      gap: 0.5rem;
      margin-top: 0.75rem;
      padding-top: 0.5rem;
      border-top: 1px solid var(--border, rgba(255,255,255,0.06));
    }

    .inline-create-cancel {
      padding: 0.35rem 0.8rem;
      font-size: 0.75rem;
      font-weight: 500;
      font-family: inherit;
      color: var(--text-2, #9ba3bd);
      background: var(--surface-3, #1c2030);
      border: 1px solid var(--border, rgba(255,255,255,0.06));
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .inline-create-cancel:hover {
      border-color: rgba(255,255,255,0.14);
      color: var(--text-1, #c4c9da);
    }

    .inline-create-submit {
      padding: 0.35rem 0.8rem;
      font-size: 0.75rem;
      font-weight: 600;
      font-family: inherit;
      color: white;
      background: linear-gradient(135deg, #22d3c5, #1a9e94);
      border: none;
      border-radius: 6px;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    .inline-create-submit:hover {
      opacity: 0.85;
    }

    /* ── Inline create form inputs (inherited theme) ── */
    .inline-create-body input,
    .inline-create-body textarea {
      width: 100%;
      padding: 0.55rem 0.75rem;
      font-size: 0.875rem;
      font-family: inherit;
      color: var(--text-0, #f0f2f8);
      background: var(--surface-1, #0e1018);
      border: 1px solid var(--border, rgba(255,255,255,0.06));
      border-radius: 8px;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
      box-sizing: border-box;
    }
    .inline-create-body input:focus,
    .inline-create-body textarea:focus {
      border-color: var(--accent, #22d3c5);
      box-shadow: 0 0 0 3px rgba(34,211,197,0.12);
    }
    .inline-create-body textarea {
      min-height: 72px;
      resize: vertical;
    }
    .inline-create-body label {
      display: block;
      margin: 0.9rem 0 0.3rem;
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--text-3, #555e78);
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to   { opacity: 1; transform: translateY(0); }
    }
  `;
}

customElements.define('ntx-ref-picker', NTTRefPicker);
