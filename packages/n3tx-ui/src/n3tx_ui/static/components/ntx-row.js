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
import {NTTItem} from './ntx-item.js';
import {Formidable} from '../generators/form.js';
import {permissions} from '../utils/Permissions.js';
import {getWidgetForField} from '../widgets/index.js';
import TX from '../core/TX.js';


export class NTTRow extends NTTItem {

  get usesCustomEditLayout() { return true; }

  /** AbortController for row-level event listeners. */
  #rowAC = null;

  get styles() { return new URL('./ntx-row.css', import.meta.url).href; }

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
   * Uses widget-aware input types (date, url, etc.) when available.
   */
  #editCells() {
    const schema = this.schema;
    const props = schema.properties || {};
    const renderable = this.#rowFields(true);
    const cells = [];
    for (const key of renderable) {
      const def = props[key];
      const val = this.value[key] ?? '';
      const type = def?.type || 'string';
      const widget = def?.ui?.widget;

      if (def?.enum) {
        const options = def.enum.map(opt =>
          `<option value="${opt}"${opt === val ? ' selected' : ''}>${opt}</option>`
        ).join('');
        cells.push(`<span class="cell edit-cell"><select data-key="${key}" data-type="string" class="cell-input">${options}</select></span>`);
      } else if (type === 'boolean') {
        const checked = val ? ' checked' : '';
        cells.push(`<span class="cell edit-cell"><input type="checkbox" data-key="${key}" data-type="boolean"${checked}></span>`);
      } else {
        // Resolve input type: widget hint > schema type > text fallback
        let inputType = 'text';
        if (widget === 'date') inputType = 'date';
        else if (widget === 'datetime') inputType = 'datetime-local';
        else if (widget === 'url') inputType = 'url';
        else if (widget === 'currency' || type === 'number' || type === 'integer') inputType = 'number';

        let inputVal = val;
        // Normalize date values for input[type=date]
        if (inputType === 'date' && val) {
          try {
            const d = new Date(val);
            if (!isNaN(d.getTime())) inputVal = d.toISOString().split('T')[0];
          } catch { /* use raw value */ }
        }
        const step = (inputType === 'number' && widget === 'currency') ? ' step="0.01"' : '';
        cells.push(`<span class="cell edit-cell"><input type="${inputType}" data-key="${key}" data-type="${type}" value="${inputVal}" class="cell-input"${step}></span>`);
      }
    }
    return cells.join('');
  }

  /**
   * Return renderable field keys for this row.
   * Uses the same logic as NTTItem's #smFields() (inherited via row()).
   * In edit mode, additionally filters out protected and $ref fields.
   */
  #rowFields(forEdit = false) {
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
      if (forEdit) {
        if (def?.ui?.protected) return false;
        if (def?.type === '$ref' || def?.$ref) return false;
      }
      return true;
    });
  }

  /** Override toggleMode for inline edit with validation. */
  toggleMode() {
    if (!permissions.canAction(this.schema?.access, 'update', this.value)) return;
    const isEdit = this.mode === 'edit';
    if (isEdit) {
      // Collect values from inputs before validating
      this.#collectInputValues();
      // Client-side validation before save
      const errors = Formidable.validateForm({
        schema: this.schema,
        value: this.value,
        ref: this.ref,
        name: this.name,
      });
      if (errors.length > 0) {
        this.#showRowErrors(errors);
        return;
      }
      this.save();
    }
    this.mode = isEdit ? 'display' : 'edit';
    this.render();
  }

  /** Collect values from inline inputs into this.value (without saving). */
  #collectInputValues() {
    const inputs = this.shadowRoot.querySelectorAll('[data-key]');
    const updated = { ...this.value };
    inputs.forEach(el => {
      const key = el.dataset.key;
      const def = this.schema.properties?.[key];
      const type = def?.type || 'string';
      if (type === 'boolean' || el.type === 'checkbox') {
        updated[key] = el.checked;
      } else if (type === 'number' || type === 'integer') {
        if (el.value.trim() === '') { updated[key] = null; }
        else {
          const num = parseFloat(el.value);
          updated[key] = isNaN(num) ? null : num;
        }
      } else {
        updated[key] = el.value;
      }
    });
    this.value = updated;
  }

  /**
   * Highlight invalid fields in the row with error messages.
   * Clears previous errors before showing new ones.
   */
  #showRowErrors(errors) {
    const root = this.shadowRoot;
    // Clear previous error indicators
    root.querySelectorAll('.field-error').forEach(el => el.classList.remove('field-error'));
    root.querySelectorAll('.cell-error-msg').forEach(el => el.remove());

    for (const { field, message } of errors) {
      const input = root.querySelector(`[data-key="${field}"]`);
      if (!input) continue;
      input.classList.add('field-error');
      const msg = document.createElement('span');
      msg.className = 'cell-error-msg';
      msg.textContent = message;
      input.parentElement?.appendChild(msg);
    }
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

    // Error banner — persistent, dismissible
    const errorHtml = this.error
      ? `<div class="ntx-error"><span class="ntx-error-msg">${this.error}</span><button class="ntx-error-dismiss" title="Dismiss">&times;</button></div>`
      : '';

    const editClass = isEdit ? ' editing' : '';
    this.shadowRoot.innerHTML = `
      ${errorHtml}
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

    // Error dismiss button
    this.shadowRoot.querySelector('.ntx-error-dismiss')?.addEventListener('click', () => {
      this.error = null;
      this.shadowRoot.querySelector('.ntx-error')?.remove();
    }, {signal});

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
      this.shadowRoot.querySelectorAll('input, select').forEach(el => {
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

customElements.define('ntx-row', NTTRow);
