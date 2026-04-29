import './ntx-ref-picker.js';
import { NTT } from '../core/NTT.js';
import TX from '../core/TX.js';

const STYLES_URL = new URL('./ntx-list-field.css', import.meta.url).href;
const DEFAULT_VISIBLE_COUNT = 8;

function encodeJson(value) {
  return encodeURIComponent(JSON.stringify(value ?? null));
}

function decodeJson(value, fallback) {
  if (!value) return fallback;
  try {
    return JSON.parse(decodeURIComponent(value));
  } catch {
    return fallback;
  }
}

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = String(value ?? '');
  return div.innerHTML;
}

export class NTTListField extends HTMLElement {
  static get observedAttributes() {
    return ['field', 'mode', 'schema', 'value', 'defs', 'parent-model', 'parent-table', 'parent-id', 'visible-count'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.render();
  }

  attributeChangedCallback() {
    if (this.isConnected) this.render();
  }

  get field() { return this.getAttribute('field') || ''; }
  get mode() { return this.getAttribute('mode') || 'display'; }
  get schema() { return decodeJson(this.getAttribute('schema'), {}); }
  get defs() { return decodeJson(this.getAttribute('defs'), {}); }
  get visibleCount() {
    const raw = this.getAttribute('visible-count')
      ?? this.schema?.ui?.visible_count
      ?? this.schema?.ui?.visibleCount
      ?? DEFAULT_VISIBLE_COUNT;
    if (raw === 'all' || raw === 'none' || raw === false) return Infinity;
    const parsed = Number(raw);
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : Infinity;
  }
  get value() {
    const raw = decodeJson(this.getAttribute('value'), []);
    if (!Array.isArray(raw) && raw && typeof raw === 'object' && Array.isArray(raw.data)) return raw.data;
    return Array.isArray(raw) ? raw : [];
  }

  render() {
    const def = this.schema;
    const value = this.value;
    const mode = this.mode;
    const modelName = this.#modelName(def);
    const childTag = this.#childTag(modelName);
    const count = value.length;

    const html = [];
    html.push(`<link rel="stylesheet" href="${STYLES_URL}">`);
    html.push(`<div class="list-field" data-model="${modelName || ''}" data-value="${this.field}" data-mode="${mode}">`);
    html.push(`<div class="list-field-header">`);
    html.push(`<span class="list-field-label">${escapeHtml(def.title || modelName || this.field)}</span>`);
    html.push(`<span class="list-field-count">${count}</span>`);
    html.push(`</div>`);

    if (modelName) {
      const rows = value.map((item) => {
        const ref = typeof item === 'string' ? item : item?.$id;
        if (!ref) return '';
        const removeBtn = mode === 'edit'
          ? `<button type="button" class="list-field-remove" data-array-action="remove-ref" data-ref="${escapeHtml(ref)}">Remove</button>`
          : '';
        return `<div class="list-field-ref-row"><${childTag} ref="${escapeHtml(ref)}" display="sm" data-model="${escapeHtml(modelName)}"></${childTag}>${removeBtn}</div>`;
      }).filter(Boolean);

      if (mode === 'display' && Number.isFinite(this.visibleCount) && rows.length > this.visibleCount) {
        const visibleRows = rows.slice(0, this.visibleCount);
        const collapsedRows = rows.slice(this.visibleCount);
        html.push(...visibleRows);
        html.push(`<div class="nested-collapsed">${collapsedRows.join('')}</div>`);
        html.push(`<button type="button" class="show-more-btn">Show ${collapsedRows.length} more</button>`);
      } else {
        html.push(...rows);
      }

      if (mode === 'edit') {
        const childTable = this.defs?.[modelName]?.__tablename__ || `${modelName.toLowerCase()}s`;
        html.push(`<ntx-ref-picker field="${escapeHtml(this.field)}" model="${escapeHtml(modelName)}" parent-model="${escapeHtml(this.getAttribute('parent-model') || '')}" parent-table="${escapeHtml(this.getAttribute('parent-table') || '')}" parent-id="${escapeHtml(this.getAttribute('parent-id') || '')}" child-table="${escapeHtml(childTable)}"></ntx-ref-picker>`);
      }
    } else {
      value.forEach((item, index) => html.push(this.#renderScalarItem(def, item, index, mode)));
      if (mode === 'edit') {
        html.push(`<button type="button" class="list-field-add" data-array-action="add-scalar">Add item</button>`);
      }
    }

    html.push(`</div>`);
    this.shadowRoot.innerHTML = html.join('');
    this.#bindEvents();
  }

  #bindEvents() {
    this.shadowRoot.querySelectorAll('input, textarea, select').forEach((el) => {
      const event = (el.type === 'checkbox' || el.tagName === 'SELECT') ? 'change' : 'input';
      el.addEventListener(event, () => this.#syncScalarValue());
    });

    this.shadowRoot.querySelector('[data-array-action="add-scalar"]')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.#dispatchValue([...this.value, this.#defaultScalarValue()]);
    });

    this.shadowRoot.querySelectorAll('[data-array-action="remove-scalar"]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const next = [...this.value];
        next.splice(parseInt(btn.dataset.index, 10), 1);
        this.#dispatchValue(next);
      });
    });

    this.shadowRoot.querySelectorAll('[data-array-action="remove-ref"]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const ref = btn.dataset.ref;
        const next = this.value.filter((item) => {
          const itemRef = typeof item === 'string' ? item : item?.$id;
          return itemRef !== ref;
        });
        this.#removeRef(ref);
        this.#dispatchValue(next);
      });
    });

    this.shadowRoot.querySelector('ntx-ref-picker')?.addEventListener('ref-added', (e) => {
      e.stopPropagation();
      const next = [...this.value];
      if (!next.some((item) => (typeof item === 'string' ? item : item?.$id) === e.detail.ref)) {
        next.push(e.detail.ref);
        this.#dispatchValue(next);
      }
    });

    this.shadowRoot.querySelector('.show-more-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      const btn = e.currentTarget;
      const collapsed = btn.previousElementSibling;
      if (!collapsed?.classList.contains('nested-collapsed')) return;
      collapsed.classList.toggle('expanded');
      const count = collapsed.children.length;
      btn.textContent = collapsed.classList.contains('expanded')
        ? 'Show less'
        : `Show ${count} more`;
    });
  }

  #dispatchValue(next) {
    this.setAttribute('value', encodeJson(next));
    this.dispatchEvent(new CustomEvent('field-change', {
      bubbles: true,
      composed: true,
      detail: { field: this.field, value: next },
    }));
    this.render();
  }

  #removeRef(ref) {
    const parentModel = this.getAttribute('parent-model') || '';
    const parentId = this.getAttribute('parent-id') || '';
    const parentEntity = (parentModel && parentId) ? NTT.get(`${parentModel}/${parentId}`) : null;
    if (!parentEntity || !ref) return;

    parentEntity.send(new TX({
      name: 'DELETE',
      source: parentEntity.addr,
      target: ref,
      meta: { inbox: '_response_' },
    }));
  }

  #syncScalarValue() {
    const next = this.value.map((item, index) => {
      const input = this.shadowRoot.querySelector(`[data-index="${index}"]`);
      if (!input) return item;
      if (input.dataset.type === 'boolean' || input.type === 'checkbox') return !!input.checked;
      if (input.dataset.type === 'number') {
        if (input.value.trim() === '') return null;
        const value = parseFloat(input.value);
        return Number.isNaN(value) ? null : value;
      }
      if (input.dataset.type === 'integer') {
        if (input.value.trim() === '') return null;
        const value = parseInt(input.value, 10);
        return Number.isNaN(value) ? null : value;
      }
      return input.value;
    });
    this.dispatchEvent(new CustomEvent('field-change', {
      bubbles: true,
      composed: true,
      detail: { field: this.field, value: next },
    }));
  }

  #renderScalarItem(def, item, index, mode) {
    if (mode !== 'edit') {
      return `<div class="list-field-item">${escapeHtml(item)}</div>`;
    }
    const itemDef = this.#itemDef(def);
    const itemType = itemDef?.type || 'string';
    let control = '';
    if (itemType === 'boolean') {
      control = `<input type="checkbox" data-index="${index}" data-type="boolean" ${item ? 'checked' : ''}>`;
    } else if (itemDef?.ui?.widget === 'textarea') {
      control = `<textarea data-index="${index}" data-type="string">${escapeHtml(item ?? '')}</textarea>`;
    } else {
      const inputType = (itemType === 'number' || itemType === 'integer') ? 'number' : 'text';
      control = `<input type="${inputType}" data-index="${index}" data-type="${itemType}" value="${escapeHtml(item ?? '')}">`;
    }
    return `<div class="list-field-edit-row">${control}<button type="button" class="list-field-remove" data-array-action="remove-scalar" data-index="${index}">Remove</button></div>`;
  }

  #itemDef(def) {
    const items = def?.items || {};
    if (items.anyOf) return items.anyOf.find((item) => item.type !== 'null' && !item.$ref) || items.anyOf[0] || {};
    return items;
  }

  #defaultScalarValue() {
    const itemDef = this.#itemDef(this.schema);
    if (itemDef?.type === 'boolean') return false;
    if (itemDef?.type === 'number' || itemDef?.type === 'integer') return null;
    return '';
  }

  #modelName(def) {
    const items = def?.items || {};
    if (items.$ref) return items.$ref.split('/').pop();
    if (items.anyOf) {
      const refEntry = items.anyOf.find((item) => item.$ref);
      if (refEntry) return refEntry.$ref.split('/').pop();
    }
    return null;
  }

  #childTag(modelName) {
    if (!modelName) return 'ntx-item';
    return this.defs?.[modelName]?.ui?.renderer?.item || 'ntx-item';
  }
}

customElements.define('ntx-list-field', NTTListField);
