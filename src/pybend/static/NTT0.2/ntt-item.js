// ntt-item.js - NTT Item Component

import { NTTElement } from './ntt-element.js';

// HTML Templates
const CARD_TEMPLATE = `
  <div class="card">
    <div class="controls">
      <button class="btn edit-btn" title="Toggle Edit">✏️</button>
      <span class="dirty-indicator" title="Has unsaved changes" style="display: none;">●</span>
    </div>
    <div class="content"></div>
    <div class="form-actions" style="display: none;">
      <button type="button" class="save-btn">💾 Save</button>
      <button type="button" class="cancel-btn">✕ Cancel</button>
    </div>
  </div>
`;

const FIELD_DISPLAY_TEMPLATE = (key, label, value) => `
  <div class="field-group">
    <label>${label}</label>
    <div class="display-value">${formatValue(value)}</div>
  </div>
`;

const FIELD_INPUT_TEMPLATE = (key, label, value, type = 'text') => `
  <div class="field-group">
    <label for="${key}">${label}</label>
    <input type="${type}" id="${key}" name="${key}" value="${value || ''}">
  </div>
`;

const FIELD_TEXTAREA_TEMPLATE = (key, label, value) => `
  <div class="field-group">
    <label for="${key}">${label}</label>
    <textarea id="${key}" name="${key}">${value || ''}</textarea>
  </div>
`;

const FIELD_CHECKBOX_TEMPLATE = (key, label, value) => `
  <div class="field-group">
    <label><input type="checkbox" name="${key}" ${value ? 'checked' : ''}>${label}</label>
  </div>
`;

// Helper functions
function formatValue(value) {
  if (value === null || value === undefined) return '<em>null</em>';
  if (typeof value === 'boolean') return value ? '✅ True' : '❌ False';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function getInputType(definition) {
  if (definition.type === 'number' || definition.type === 'integer') return 'number';
  if (definition.format === 'email') return 'email';
  return 'text';
}

export class NTTItem extends NTTElement {
  constructor() {
    super('ntt-item');
    this.mode = 'display';
    this.loadItemStyles();
  }

  async loadItemStyles() {
    try {
      const response = await fetch('./ntt-item.css');
      const css = await response.text();
      const style = document.createElement('style');
      style.textContent = css;
      this.shadowRoot.appendChild(style);
    } catch (error) {
      console.warn('Could not load ntt-item.css');
    }
  }

  static get observedAttributes() {
    return [...super.observedAttributes, 'mode'];
  }

  attributeChangedCallback(name, oldVal, newVal) {
    super.attributeChangedCallback(name, oldVal, newVal);
    
    if (name === 'mode' && newVal !== oldVal) {
      this.mode = newVal;
      this.render();
    }
  }

  // Override parent methods
  onDataChanged() {
    this.render();
  }

  onNTTChanged(nttInstance, newData, oldData) {
    this.value = newData;
    this.render();
  }

  // Item-specific methods
  toggleMode() {
    this.mode = this.mode === 'edit' ? 'display' : 'edit';
    this.render();
  }

  async saveChanges() {
    const nttInstance = Array.from(this.nttInstances.values())[0];
    if (!nttInstance) return;
    
    const form = this.shadowRoot.querySelector('.content');
    const inputs = form.querySelectorAll('input, textarea');
    const changes = {};
    
    inputs.forEach(input => {
      const key = input.name;
      const fieldDef = this.prototype.properties?.[key];
      
      if (input.type === 'checkbox') {
        changes[key] = input.checked;
      } else if (fieldDef?.type === 'number') {
        changes[key] = parseFloat(input.value) || 0;
      } else {
        changes[key] = input.value;
      }
    });
    
    this.evolveNTT(nttInstance.id, changes);
    
    if (this.hasAttribute('auto-commit')) {
      await this.commitNTT(nttInstance.id);
    }
    
    this.mode = 'display';
    this.render();
  }

  cancelEdit() {
    this.mode = 'display';
    this.render();
  }

  render() {
    if (!this.shadowRoot.querySelector('style')) return;
    
    // Handle loading/error states
    if (this.isLoading) {
      this.shadowRoot.innerHTML = this.renderLoadingState();
      return;
    }
    
    if (this.hasError) {
      this.shadowRoot.innerHTML = this.renderErrorState();
      return;
    }
    
    if (this.isEmpty()) {
      this.shadowRoot.innerHTML = this.renderEmptyState('📄', 'No item data');
      return;
    }
    
    // Render item card
    const container = document.createElement('div');
    container.innerHTML = CARD_TEMPLATE;
    
    // Update dirty indicator
    if (this.hasDirtyInstances()) {
      container.querySelector('.dirty-indicator').style.display = 'inline';
    }
    
    // Render fields
    const content = container.querySelector('.content');
    const fields = this.prototype?.properties || {};
    
    for (const key in fields) {
      const definition = fields[key];
      const label = definition.title || key;
      const value = this.value[key];
      
      if (this.mode === 'edit' && !definition.readOnly) {
        if (definition.type === 'boolean') {
          content.innerHTML += FIELD_CHECKBOX_TEMPLATE(key, label, value);
        } else if (definition.format === 'textarea') {
          content.innerHTML += FIELD_TEXTAREA_TEMPLATE(key, label, value);
        } else {
          const inputType = getInputType(definition);
          content.innerHTML += FIELD_INPUT_TEMPLATE(key, label, value, inputType);
        }
      } else {
        content.innerHTML += FIELD_DISPLAY_TEMPLATE(key, label, value);
      }
    }
    
    // Show form actions in edit mode
    if (this.mode === 'edit') {
      container.querySelector('.form-actions').style.display = 'flex';
    }
    
    // Replace content
    const existingCard = this.shadowRoot.querySelector('.card');
    if (existingCard) {
      this.shadowRoot.replaceChild(container.firstElementChild, existingCard);
    } else {
      this.shadowRoot.appendChild(container.firstElementChild);
    }
    
    // Add event listeners
    this.attachEventListeners();
  }

  attachEventListeners() {
    this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', () => this.toggleMode());
    this.shadowRoot.querySelector('.save-btn')?.addEventListener('click', () => this.saveChanges());
    this.shadowRoot.querySelector('.cancel-btn')?.addEventListener('click', () => this.cancelEdit());
  }
}

customElements.define('ntt-item', NTTItem);