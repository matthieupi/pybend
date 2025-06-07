// ntt-list.js - NTT List Component

import { NTTElement } from './ntt-element.js';
import './ntt-item.js';

// HTML Templates
const LIST_TEMPLATE = `
  <div class="list-container">
    <div class="list-header">
      <div class="list-title">
        <span class="title-text">Items</span>
        <span class="list-count">0</span>
      </div>
      <div class="list-actions">
        <button class="refresh-btn" title="Refresh">🔄</button>
        <button class="add-btn" style="display: none;">+ Add</button>
      </div>
    </div>
    <div class="list-content"></div>
  </div>
`;

export class NTTList extends NTTElement {
  constructor() {
    super('ntt-list');
    this.loadListStyles();
  }

  async loadListStyles() {
    try {
      const response = await fetch('./ntt-list.css');
      const css = await response.text();
      const style = document.createElement('style');
      style.textContent = css;
      this.shadowRoot.appendChild(style);
    } catch (error) {
      console.warn('Could not load ntt-list.css');
    }
  }

  // Override parent methods
  onDataChanged() {
    this.render();
  }

  onInstancesCreated() {
    this.render();
  }

  onNTTChanged(nttInstance, newData, oldData) {
    this.render();
  }

  // List-specific methods
  refresh() {
    if (this.href) {
      this.fetchData();
    }
  }

  addItem() {
    this.dispatchNTTEvent('add-item', { 
      factoryId: this.factoryId, 
      schema: this.prototype 
    });
  }

  render() {
    if (!this.shadowRoot.querySelector('style')) return;
    
    // Handle loading/error states
    if (this.isLoading) {
      const container = document.createElement('div');
      container.innerHTML = LIST_TEMPLATE;
      container.querySelector('.list-content').innerHTML = this.renderLoadingState();
      this.replaceContent(container.firstElementChild);
      return;
    }
    
    if (this.hasError) {
      const container = document.createElement('div');
      container.innerHTML = LIST_TEMPLATE;
      container.querySelector('.list-content').innerHTML = this.renderErrorState();
      this.replaceContent(container.firstElementChild);
      return;
    }
    
    // Render list
    const container = document.createElement('div');
    container.innerHTML = LIST_TEMPLATE;
    
    // Update title and count
    const titleText = container.querySelector('.title-text');
    const countBadge = container.querySelector('.list-count');
    const addBtn = container.querySelector('.add-btn');
    const content = container.querySelector('.list-content');
    
    titleText.textContent = this.prototype.title || 'Items';
    countBadge.textContent = this.getInstanceCount();
    
    // Show add button if factory-id is set
    if (this.factoryId) {
      addBtn.style.display = 'flex';
    }
    
    // Render content
    if (this.isEmpty()) {
      content.innerHTML = this.renderEmptyState('📦', 'No items found');
    } else {
      content.innerHTML = '';
      
      // Render each item
      Array.from(this.nttInstances.values()).forEach(ntt => {
        const el = document.createElement('ntt-item');
        el.setAttribute('ntt-id', ntt.id);
        if (this.hasAttribute('auto-commit')) {
          el.setAttribute('auto-commit', '');
        }
        content.appendChild(el);
      });
    }
    
    this.replaceContent(container.firstElementChild);
    this.attachEventListeners();
  }

  replaceContent(newContent) {
    const existingContainer = this.shadowRoot.querySelector('.list-container');
    if (existingContainer) {
      this.shadowRoot.replaceChild(newContent, existingContainer);
    } else {
      this.shadowRoot.appendChild(newContent);
    }
  }

  attachEventListeners() {
    this.shadowRoot.querySelector('.refresh-btn')?.addEventListener('click', () => this.refresh());
    this.shadowRoot.querySelector('.add-btn')?.addEventListener('click', () => this.addItem());
  }
}

customElements.define('ntt-list', NTTList);