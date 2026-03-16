/**
 * NTTTable — Table collection component.
 *
 * Extends ListElement for data lifecycle (schema, READ, pagination, SELECT).
 * Renders entities as rows in a CSS grid table with aligned columns.
 *
 * Features:
 *   - Column alignment via inherited --table-columns CSS variable
 *   - Click column headers to sort (client-side, toggles asc/desc)
 *   - Inline create: bottom row expands into input form
 *   - Rows support inline edit/delete via NTTRow
 *
 * Usage:
 *   <ntx-table model="Grant" allow-create></ntx-table>
 */
import './ntx-row.js';
import {ListElement} from './ListElement.js';
import {permissions} from '../utils/Permissions.js';
import {NTT} from '../core/NTT.js';
import {Formidable} from '../generators/form.js';


export class NTTTable extends ListElement {

  #sortKey = null;
  #sortDir = 'asc';  // 'asc' | 'desc'
  #eventAC = null;
  #createOpen = false;
  #pendingCreate = false;
  #unsubError = null;

  get styles() { return new URL('./ntx-table.css', import.meta.url).href; }

  get childTag() {
    return this.getAttribute('item-tag') || 'ntx-row';
  }

  get childDisplay() { return 'row'; }

  /**
   * Return ordered renderable field keys for table columns.
   * Same logic as NTTItem's #smFields(): respects field_order,
   * skips id, hidden, array, and selfref fields.
   */
  tableColumns() {
    const schema = this.schema;
    if (!schema?.properties) return [];
    const fields = schema.properties;
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
   * Return ordered field keys for the create row inputs.
   * Extends tableColumns() by additionally filtering out protected
   * and $ref fields (same logic as NTTRow's #rowFields(forEdit=true)).
   */
  createColumns() {
    const schema = this.schema;
    if (!schema?.properties) return [];
    const fields = schema.properties;
    return this.tableColumns().filter(key => {
      const def = fields[key];
      if (def?.ui?.protected) return false;
      if (def?.type === '$ref' || def?.$ref) return false;
      return true;
    });
  }

  /**
   * Build the --table-columns CSS value from the column list.
   * First column (typically name/title) gets 2fr, rest get 1fr.
   */
  #columnsCSS(cols) {
    if (cols.length === 0) return '1fr';
    return cols.map((_, i) => i === 0 ? '2fr' : '1fr').join(' ');
  }

  /**
   * Human-readable header label for a field key.
   */
  #headerLabel(key) {
    const def = this.schema.properties?.[key];
    return def?.title || key.replace(/_/g, ' ');
  }


  /** ─────────────────────────────────────────── **/
  /**         Lifecycle                             **/
  /** ─────────────────────────────────────────── **/

  definedCallback() {
    super.definedCallback();
    // Subscribe to ERROR events from the DynamicClass for create error recovery
    this.#unsubError?.();
    this.#unsubError = this.proto.observe('ERROR', (event) => this.handleCreateError(event));
  }

  disconnectedCallback() {
    this.#unsubError?.();
    this.#eventAC?.abort();
    super.disconnectedCallback?.();
  }


  /** ─────────────────────────────────────────── **/
  /**         Sorting                              **/
  /** ─────────────────────────────────────────── **/

  /**
   * Sort the current value array by a field key.
   * Compares resolved entity values from the NTT registry.
   */
  #sort(key) {
    if (this.#sortKey === key) {
      this.#sortDir = this.#sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      this.#sortKey = key;
      this.#sortDir = 'asc';
    }

    const dir = this.#sortDir === 'asc' ? 1 : -1;
    const modelName = this.schema.__name__;

    // Resolve entity values from the NTT registry for comparison
    const sorted = [...this.value].sort((addrA, addrB) => {
      const entityA = NTT.get(`${modelName}/${addrA.split('/').pop()}`);
      const entityB = NTT.get(`${modelName}/${addrB.split('/').pop()}`);
      const a = entityA?.value?.[key] ?? '';
      const b = entityB?.value?.[key] ?? '';
      if (typeof a === 'number' && typeof b === 'number') return (a - b) * dir;
      return String(a).localeCompare(String(b)) * dir;
    });

    this.value = sorted;
    this.scheduleRender();
  }


  /** ─────────────────────────────────────────── **/
  /**         Inline Create                        **/
  /** ─────────────────────────────────────────── **/

  #toggleCreate() {
    this.#createOpen = !this.#createOpen;
    const row = this.shadowRoot.querySelector('.create-row');
    const btn = this.shadowRoot.querySelector('.create-btn-row');
    if (!row || !btn) return;

    if (this.#createOpen) {
      row.style.display = 'grid';
      btn.style.display = 'none';
      // Focus the first input
      requestAnimationFrame(() => row.querySelector('input')?.focus());
    } else {
      this.#closeCreateRow();
    }
  }

  /**
   * Close the create row: hide it, show the add button, clear inputs and errors.
   */
  #closeCreateRow() {
    const row = this.shadowRoot.querySelector('.create-row');
    const btn = this.shadowRoot.querySelector('.create-btn-row');
    this.#createOpen = false;
    this.#pendingCreate = false;
    if (row) {
      row.style.display = 'none';
      row.classList.remove('loading');
      // Clear inputs and error states
      row.querySelectorAll('input, textarea, select').forEach(el => {
        if (el.tagName === 'SELECT') el.selectedIndex = 0;
        else el.value = '';
        el.disabled = false;
        el.classList.remove('input-error');
      });
      row.querySelectorAll('.cell-error-msg').forEach(el => el.remove());
    }
    if (btn) btn.style.display = 'grid';
  }

  /**
   * Enable/disable all inputs in the create row (loading state).
   */
  #setCreateLoading(loading) {
    const row = this.shadowRoot.querySelector('.create-row');
    if (!row) return;
    if (loading) {
      row.classList.add('loading');
    } else {
      row.classList.remove('loading');
    }
    row.querySelectorAll('input, textarea, select, button').forEach(el => {
      el.disabled = loading;
    });
  }

  /**
   * Show field-level error messages on the create row.
   * Matches NTTRow's #showRowErrors() pattern.
   */
  #showCreateErrors(errors) {
    const row = this.shadowRoot.querySelector('.create-row');
    if (!row) return;
    // Clear previous
    row.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
    row.querySelectorAll('.cell-error-msg').forEach(el => el.remove());

    for (const { field, message } of errors) {
      const input = row.querySelector(`[data-key="${field}"]`);
      if (!input) continue;
      input.classList.add('input-error');
      const msg = document.createElement('span');
      msg.className = 'cell-error-msg';
      msg.textContent = message;
      input.parentElement?.appendChild(msg);
    }
  }

  #submitCreate() {
    const row = this.shadowRoot.querySelector('.create-row');
    if (!row) return;

    // Clear previous error states
    row.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
    row.querySelectorAll('.cell-error-msg').forEach(el => el.remove());

    // Collect data from inputs
    const data = {};
    let hasTypeError = false;

    row.querySelectorAll('[data-key]').forEach(el => {
      const key = el.dataset.key;
      const def = this.schema.properties?.[key];
      const type = def?.type || 'string';

      if (type === 'number' || type === 'integer') {
        if (el.value.trim() === '') return; // Empty optional field — skip
        const num = parseFloat(el.value);
        if (isNaN(num)) {
          el.classList.add('input-error');
          hasTypeError = true;
          return;
        }
        data[key] = num;
      } else if (type === 'boolean') {
        data[key] = el.checked;
      } else {
        if (el.value.trim()) data[key] = el.value.trim();
      }
    });

    if (hasTypeError) return; // Don't submit with invalid number fields

    // Client-side validation via Formidable (required fields, min/max, etc.)
    const nttLike = { schema: this.schema, value: data };
    const errors = Formidable.validateForm(nttLike);
    if (errors.length > 0) {
      this.#showCreateErrors(errors);
      return;
    }

    if (Object.keys(data).length === 0) return;

    // Send CREATE but keep the row open in loading state
    this.proto.call('CREATE', data, { inbox: 'CREATE' });
    this.#pendingCreate = true;
    this.#setCreateLoading(true);
  }

  /**
   * Handle CREATE error — re-enable the create row with data preserved.
   * Called by the ERROR observer on the DynamicClass.
   */
  handleCreateError(event) {
    if (!this.#pendingCreate) return;
    this.#pendingCreate = false;
    this.#setCreateLoading(false);

    // If the error includes field-level validation details, show them
    const detail = event?.data?.detail || event?.data?.errors;
    if (Array.isArray(detail)) {
      this.#showCreateErrors(detail);
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Surgical DOM Update                  **/
  /** ─────────────────────────────────────────── **/

  /** Patch table DOM in-place: remove deletions, append additions. */
  update(prev, next) {
    if (!Array.isArray(prev) || !Array.isArray(next)) return false;
    const body = this.shadowRoot?.querySelector('.table-body');
    if (!body) return false;

    const prevSet = new Set(prev);
    const nextSet = new Set(next);

    // Deletions
    const deletions = prev.filter(addr => !nextSet.has(addr));
    for (const addr of deletions) {
      const el = body.querySelector(`[data-value="${addr}"]`);
      if (el) el.remove();
    }

    // Additions
    const additions = next.filter(addr => !prevSet.has(addr));
    if (additions.length > 0) {
      const fragment = document.createDocumentFragment();
      for (const addr of additions) {
        const child = this.createChild(addr);
        child.setAttribute('data-value', addr);
        fragment.appendChild(child);
      }
      body.appendChild(fragment);
    }

    // If a create was pending and we got new items, close the create row
    if (this.#pendingCreate && additions.length > 0) {
      this.#closeCreateRow();
    }

    // Update count
    const countEl = this.shadowRoot.querySelector('.list-count');
    if (countEl) {
      const meta = this.proto?._paginationMeta;
      const total = meta?.total ?? next.length;
      countEl.textContent = `${next.length}${meta ? ` / ${total}` : ''}`;
    }

    return true;
  }


  /** ─────────────────────────────────────────── **/
  /**         Render                               **/
  /** ─────────────────────────────────────────── **/

  render() {
    if (!this.schema || !Array.isArray(this.value)) return;

    const cols = this.tableColumns();
    if (cols.length === 0) return;

    const meta = this.proto?._paginationMeta;
    const total = meta?.total ?? this.value.length;
    const hasMore = meta?.has_more ?? false;
    const headless = this.hasAttribute('headless');
    const canCreate = this.hasAttribute('allow-create') &&
                      permissions.canAction(this.schema?.access, 'create');

    const columnsCSS = this.#columnsCSS(cols);
    const fullColumns = `${columnsCSS} 3.5rem`;  // data cols + fixed actions col

    // Header cells with sort indicators (arrow in separate span to avoid ellipsis clipping)
    const headerCells = cols.map(key => {
      const label = this.#headerLabel(key);
      const isActive = this.#sortKey === key;
      const arrow = isActive ? `<span class="sort-arrow">${this.#sortDir === 'asc' ? '\u25b2' : '\u25bc'}</span>` : '';
      const activeClass = isActive ? ' sort-active' : '';
      return `<span class="header-cell${activeClass}" data-sort="${key}"><span class="header-label">${label}</span>${arrow}</span>`;
    }).join('');

    // Create row inputs — use createColumns() to exclude protected/$ref fields
    let createRowHtml = '';
    let createBtnHtml = '';
    if (canCreate) {
      const createCols = this.createColumns();
      // Build inputs aligned to the full column grid.
      // For display-only columns (in tableColumns but not createColumns), emit an empty cell.
      const inputs = cols.map(key => {
        if (!createCols.includes(key)) {
          return `<span class="create-cell"></span>`;
        }
        const def = this.schema.properties?.[key];
        const type = def?.type || 'string';
        const widget = def?.ui?.widget;
        const placeholder = def?.ui?.placeholder || this.#headerLabel(key);
        if (def?.enum) {
          const options = def.enum.map(opt =>
            `<option value="${opt}">${opt}</option>`
          ).join('');
          return `<span class="create-cell"><select data-key="${key}" class="cell-input">${options}</select></span>`;
        }
        if (type === 'boolean') {
          return `<span class="create-cell"><input type="checkbox" data-key="${key}"></span>`;
        }
        // Resolve input type: widget hint > schema type > text fallback
        // (same logic as NTTRow's #editCells)
        let inputType = 'text';
        if (widget === 'date') inputType = 'date';
        else if (widget === 'datetime') inputType = 'datetime-local';
        else if (widget === 'url') inputType = 'url';
        else if (widget === 'currency' || type === 'number' || type === 'integer') inputType = 'number';
        const step = (inputType === 'number' && widget === 'currency') ? ' step="0.01"' : '';
        return `<span class="create-cell"><input type="${inputType}" data-key="${key}" placeholder="${placeholder}" class="cell-input"${step}></span>`;
      }).join('');

      createRowHtml = `
        <div class="create-row" style="grid-template-columns: ${fullColumns}; display: none">
          ${inputs}
          <span class="create-actions">
            <button class="save-create-btn" title="Save"></button>
            <button class="cancel-create-btn" title="Cancel"></button>
          </span>
        </div>`;

      createBtnHtml = `
        <div class="create-btn-row" style="grid-template-columns: ${fullColumns}">
          <button class="inline-add-btn" title="Add new">+ Add ${this.schema.__name__}</button>
        </div>`;
    }

    this.shadowRoot.innerHTML = `
      ${headless ? '' : `
      <div class="list-header">
        <h1>${this.model}s</h1>
        <span class="list-count">${this.value.length}${meta ? ` / ${total}` : ''}</span>
      </div>`}
      <div class="table-container" style="--table-columns: ${columnsCSS}">
        <div class="table-header" style="grid-template-columns: ${fullColumns}">
          ${headerCells}
          <span class="header-cell header-actions"></span>
        </div>
        <div class="table-body"></div>
        ${createRowHtml}
        ${createBtnHtml}
      </div>
      ${hasMore ? '<button class="load-more-btn">Load More</button>' : ''}
    `;

    // Stamp row children into table-body
    const body = this.shadowRoot.querySelector('.table-body');
    const fragment = document.createDocumentFragment();
    this.value.forEach((addr, i) => {
      const child = this.createChild(addr);
      child.setAttribute('data-value', addr);
      child.style.setProperty('--stagger-delay', `${i * 30}ms`);
      fragment.appendChild(child);
    });
    body.appendChild(fragment);

    this.#bindTableEvents();
  }

  #bindTableEvents() {
    this.#eventAC?.abort();
    this.#eventAC = new AbortController();
    const {signal} = this.#eventAC;

    // Sort headers
    this.shadowRoot.querySelectorAll('.header-cell[data-sort]').forEach(el => {
      el.addEventListener('click', () => this.#sort(el.dataset.sort), {signal});
    });

    // Load more
    this.shadowRoot.querySelector('.load-more-btn')?.addEventListener('click',
      () => this.loadMore(), {signal});

    // Inline create toggle
    this.shadowRoot.querySelector('.inline-add-btn')?.addEventListener('click',
      () => this.#toggleCreate(), {signal});

    // Create row: save
    this.shadowRoot.querySelector('.save-create-btn')?.addEventListener('click',
      () => this.#submitCreate(), {signal});

    // Create row: cancel
    this.shadowRoot.querySelector('.cancel-create-btn')?.addEventListener('click',
      () => this.#toggleCreate(), {signal});

    // Create row: Enter key submits
    this.shadowRoot.querySelectorAll('.create-row input, .create-row select').forEach(el => {
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); this.#submitCreate(); }
        if (e.key === 'Escape') this.#toggleCreate();
      }, {signal});
    });
  }
}

customElements.define('ntx-table', NTTTable);
