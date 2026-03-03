/**
 * NTTRow — Table row entity component.
 *
 * Extends NTTItem to inherit entity lifecycle + row() size method.
 * Forces display="row" and wraps the raw cells in a styled row container
 * with action buttons. Designed to be stamped by NTTTable.
 *
 * Features:
 *   - Inline edit: edit button transforms cells into inputs
 *   - Delete with confirmation
 *   - Click row to navigate (SELECT TX)
 *   - Column alignment via inherited --table-columns CSS variable
 */
import {NTTItem} from './ntt-item.js';
import {Formidable} from '../generators/form.js';
import {permissions} from '../utils/Permissions.js';
import TX from '../core/TX.js';


export class NTTRow extends NTTItem {

  /** AbortController for row-level event listeners. */
  #rowAC = null;

  get styles() { return new URL('./ntt-row.css', import.meta.url).href; }

  connectedCallback() {
    super.connectedCallback();
    // Force row display mode regardless of attribute or resize
    if (this.displayMode !== 'row') {
      this.display = 'row';
    }
  }

  /** Skip resize-based mode changes — always row. */
  displayModeChanged(oldMode, newMode) {
    if (newMode !== 'row') return;
    super.displayModeChanged(oldMode, newMode);
  }

  /** Return skeleton cells matching the row layout. */
  placeholder(size) {
    return `<div class="row skeleton">
      <span class="bone" style="width:60%;height:0.7rem"></span>
      <span class="bone" style="width:40%;height:0.7rem"></span>
      <span class="bone" style="width:30%;height:0.7rem"></span>
    </div>`;
  }

  /**
   * Build inline edit cells — one input per renderable field.
   */
  #editCells() {
    const schema = this.schema;
    const props = schema.properties || {};
    const renderable = this.#rowFields();
    const cells = [];
    for (const key of renderable) {
      const def = props[key];
      const val = this.value[key] ?? '';
      const type = def?.type || 'string';
      if (type === 'boolean') {
        const checked = val ? ' checked' : '';
        cells.push(`<span class="cell edit-cell"><input type="checkbox" data-key="${key}"${checked}></span>`);
      } else {
        const inputType = (type === 'number' || type === 'integer') ? 'number' : 'text';
        cells.push(`<span class="cell edit-cell"><input type="${inputType}" data-key="${key}" value="${val}" class="cell-input"></span>`);
      }
    }
    return cells.join('');
  }

  /**
   * Return renderable field keys for this row.
   * Uses the same logic as NTTItem's #smFields() (inherited via row()).
   */
  #rowFields() {
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

  /** Override toggleMode for inline edit. */
  toggleMode() {
    if (!permissions.canAction(this.schema?.access, 'update', this.value)) return;
    const isEdit = this.mode === 'edit';
    if (isEdit) this.#saveInline();
    this.mode = isEdit ? 'display' : 'edit';
    this.render();
  }

  /** Collect values from inline inputs and save. */
  #saveInline() {
    const inputs = this.shadowRoot.querySelectorAll('[data-key]');
    const updated = { ...this.value };
    inputs.forEach(el => {
      const key = el.dataset.key;
      const def = this.schema.properties?.[key];
      const type = def?.type || 'string';
      if (type === 'boolean' || el.type === 'checkbox') {
        updated[key] = el.checked;
      } else if (type === 'number' || type === 'integer') {
        const num = parseFloat(el.value);
        if (!isNaN(num)) updated[key] = num;
      } else {
        updated[key] = el.value;
      }
    });
    this.value = updated;
    this.save();
  }

  render() {
    if (!this.schema || !this.value) return;

    const isEdit = this.mode === 'edit';
    const cellsHtml = isEdit ? this.#editCells() : this.row();

    // Action buttons (edit/delete) gated by permissions
    const canUpdate = permissions.canAction(this.schema.access, 'update', this.value);
    const canDelete = permissions.canAction(this.schema.access, 'delete', this.value);
    let actionsHtml = '<span class="row-actions">';
    if (canDelete) {
      actionsHtml += '<button class="delete-btn" title="Delete"></button>';
    }
    if (canUpdate) {
      const modeClass = isEdit ? 'mode-edit' : 'mode-display';
      actionsHtml += `<button class="edit-btn ${modeClass}" title="${isEdit ? 'Save' : 'Edit'}"></button>`;
    }
    if (isEdit) {
      actionsHtml += '<button class="cancel-btn" title="Cancel"></button>';
    }
    actionsHtml += '</span>';

    const editClass = isEdit ? ' editing' : '';
    this.shadowRoot.innerHTML = `
      <div class="row${editClass}" data-display="row">
        ${cellsHtml}
        ${actionsHtml}
      </div>
    `;
    this._rendered = true;

    this.#bindRowEvents();
  }

  /** Bind row-specific event listeners. */
  #bindRowEvents() {
    this.#rowAC?.abort();
    this.#rowAC = new AbortController();
    const {signal} = this.#rowAC;

    // Edit button
    this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleMode();
    }, {signal});

    // Cancel button (edit mode)
    this.shadowRoot.querySelector('.cancel-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.mode = 'display';
      this.render();
    }, {signal});

    // Delete button
    this.shadowRoot.querySelector('.delete-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.deleteItem();
    }, {signal});

    // Edit mode: Enter saves, Escape cancels
    if (this.mode === 'edit') {
      this.shadowRoot.querySelectorAll('input').forEach(el => {
        el.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') { e.preventDefault(); this.toggleMode(); }
          if (e.key === 'Escape') { this.mode = 'display'; this.render(); }
        }, {signal});
      });
    }

    // Row click → SELECT (not in edit mode)
    if (this.mode !== 'edit') {
      this.shadowRoot.querySelector('.row')?.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        const target = this.getAttribute('select-target');
        if (target) {
          this.send(new TX({
            name: 'SELECT', source: this.addr, target: target, data: this.ref
          }));
        }
      }, {signal});
    }
  }
}

customElements.define('ntt-row', NTTRow);
