// ntt-element.js - Base NTT Element Component

import { NTT } from './NTT.js';

// HTML Templates
const LOADING_TEMPLATE = `
  <div class="loading-state">
    <div class="loading-spinner"></div>
    <div>Loading...</div>
  </div>
`;

const ERROR_TEMPLATE = (message) => `
  <div class="error-state">
    <div class="error-icon">❌</div>
    <div>Error: ${message}</div>
    <button class="retry-btn">Retry</button>
  </div>
`;

const EMPTY_TEMPLATE = (icon = '📦', message = 'No data available') => `
  <div class="empty-state">
    <div class="empty-icon">${icon}</div>
    <div>${message}</div>
  </div>
`;

export class NTTElement extends HTMLElement {
  constructor(componentName = 'ntt-element') {
    super();
    this.attachShadow({ mode: 'open' });
    
    // Component identification
    this.componentName = componentName;
    
    // NTT state
    this._addr = randomUUID();
    this._href = null;
    this._value = null;
    this._schema = {};
    this.subscriptions = [];
    
    // Component state
    this.isLoading = false;
    this.hasError = false;
    this.errorMessage = '';
    
    // Load base styles
    this.loadStyles();
  }

  static get observedAttributes() {
    return ['href', 'ntt-id', 'auto-commit'];
  }

  async loadStyles() {
    try {
      const response = await fetch('./ntt-element.css');
      const css = await response.text();
      const style = document.createElement('style');
      style.textContent = css;
      this.shadowRoot.appendChild(style);
    } catch (error) {
      console.warn('Could not load ntt-element.css');
    }
  }

  attributeChangedCallback(name, oldVal, newVal) {
    if (name === 'href' && newVal !== oldVal) {
      this.href = newVal;
    }
    if (name === 'ntt-id' && newVal !== oldVal) {
      this.connectToNTT(newVal);
    }
    if (name === 'factory-id' && newVal !== oldVal) {
      this.factoryId = newVal;
    }
  }

  // Properties
  set href(url) {
    this._href = url;
    this.fetchData();
  }

  get href() {
    return this._href;
  }

  set value(val) {
    this._value = val;
    this.createNTTInstances();
    this.onDataChanged();
  }
  
  get value() {
    return this._value;
  }
  
  set schema(schema) {
    this._schema = schema;
    this.onSchemaChanged();
  }

  get schema() {
    return this._schema;
  }
  
  update(obj) {
    this.value = {...this._value, ...obj};
  }

  describe(schema) {
    // Todo: Add validatiation to schema obj
    this.schema = { ...this._schema, ...obj}
    }
    
  update(property, value) {
    if (property === "schema"){
        this.schema = value;
    } else if (property === "value") {
        this.value = value;
    }
  }

  // NTT Data Management
  async connect() {
    if (!this._href) return;
    this._schema = NTT.schema(this._href);
    this._value =
    
    this.setLoadingState(true);
    this.clearError();
    
    try {
      // Get schema first
      const schemaUrl = this.getSchemaUrl(this._href);
      const schemaRes = await fetch(schemaUrl);
      if (schemaRes.ok) {
        this._schema = await schemaRes.json();
        this.onSchemaChanged();
      }
      
      // Get data
      const res = await fetch(this._href);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      
      const data = await res.json();
      this.value = data;
      
    } catch (error) {
      this.setError(`Failed to load data: ${error.message}`);
    } finally {
      this.setLoadingState(false);
    }
  }

  getSchemaUrl(href) {
    return href.replace(/\/\d+$/, '').replace(/\/?$/, '/schema');
  }

  createNTTInstances() {
    // Clear existing instances
    this.disconnectFromNTT();
    
    if (!this._value) return;
    
    // Handle single item vs array
    const items = Array.isArray(this._value) ? this._value : [this._value];
    
    items.forEach((item, index) => {
      const ntt = new NTT({
        name: `${this.componentName}_${index}`,
        addr: `${this._href}/${item.id || index}`,
        data: item,
        schema: this._schema
      });
      
      this.nttInstances.set(ntt.id, ntt);
      
      // Subscribe to changes
      const unsubscribe = NTT.subscribe(ntt.id, (newData, oldData, nttInstance) => {
        this.onNTTChanged(nttInstance, newData, oldData);
      });
      this.subscriptions.push(unsubscribe);
    });
    
    this.onInstancesCreated();
  }

  connectToNTT(nttId) {
    this.disconnectFromNTT();
    
    const nttInstance = NTT.get(nttId);
    if (nttInstance) {
      this._value = nttInstance.data;
      this._schema = nttInstance.schema;
      this.nttInstances.set(nttId, nttInstance);
      
      const unsubscribe = NTT.subscribe(nttId, (newData, oldData, ntt) => {
        this._value = newData;
        this.onNTTChanged(ntt, newData, oldData);
      });
      this.subscriptions.push(unsubscribe);
      
      this.onDataChanged();
    }
  }

  disconnectFromNTT() {
    this.subscriptions.forEach(unsubscribe => unsubscribe());
    this.subscriptions = [];
    this.nttInstances.clear();
  }

  disconnectedCallback() {
    this.disconnectFromNTT();
  }

  // State Management
  setLoadingState(loading) {
    this.isLoading = loading;
    this.onStateChanged();
  }

  setError(message) {
    this.hasError = true;
    this.errorMessage = message;
    this.onStateChanged();
  }

  clearError() {
    this.hasError = false;
    this.errorMessage = '';
  }

  retry() {
    this.clearError();
    if (this._href) {
      this.fetchData();
    }
  }

  // NTT Operations
  async commitNTT(nttId) {
    const ntt = this.nttInstances.get(nttId);
    if (!ntt || !ntt.isDirty) return;
    
    try {
      await NTT.commit(nttId);
      this.dispatchNTTEvent('ntt-committed', { nttId, ntt });
    } catch (error) {
      this.dispatchNTTEvent('ntt-error', { nttId, ntt, error });
    }
  }

  async commitAllNTT() {
    const dirtyInstances = Array.from(this.nttInstances.values()).filter(ntt => ntt.isDirty);
    
    for (const ntt of dirtyInstances) {
      await this.commitNTT(ntt.id);
    }
  }

  rollbackNTT(nttId) {
    NTT.rollback(nttId);
    const ntt = this.nttInstances.get(nttId);
    this.dispatchNTTEvent('ntt-rolled-back', { nttId, ntt });
  }

  pullNTT(nttId) {
    NTT.pull(nttId);
    const ntt = this.nttInstances.get(nttId);
    this.dispatchNTTEvent('ntt-pulled', { nttId, ntt });
  }

  evolveNTT(nttId, changes) {
    NTT.evolve(nttId, changes);
    const ntt = this.nttInstances.get(nttId);
    this.dispatchNTTEvent('ntt-evolved', { nttId, ntt, changes });
  }

  // Factory Operations
  createViaFactory(data) {
    if (!this.factoryId) {
      console.warn('No factory-id specified');
      return;
    }
    
    NTT.create(this.factoryId, data);
    this.dispatchNTTEvent('factory-create', { factoryId: this.factoryId, data });
  }

  // Event Management
  dispatchNTTEvent(eventName, detail) {
    this.dispatchEvent(new CustomEvent(eventName, {
      detail,
      bubbles: true
    }));
  }

  // Template Helpers
  renderLoadingState() {
    return LOADING_TEMPLATE;
  }

  renderErrorState() {
    const container = document.createElement('div');
    container.innerHTML = ERROR_TEMPLATE(this.errorMessage);
    container.querySelector('.retry-btn')?.addEventListener('click', () => this.retry());
    return container.innerHTML;
  }

  renderEmptyState(icon, message) {
    return EMPTY_TEMPLATE(icon, message);
  }

  // Lifecycle Hooks (to be overridden by subclasses)
  onDataChanged() {
    // Override in subclasses
    this.render();
  }

  onSchemaChanged() {
    // Override in subclasses
    this.render();
  }

  onInstancesCreated() {
    // Override in subclasses
    this.render();
  }

  onNTTChanged(nttInstance, newData, oldData) {
    // Override in subclasses
    this.render();
  }

  onStateChanged() {
    // Override in subclasses
    this.render(); 
  }

  // Base render method (to be overridden)
  render() {
    if (!this.shadowRoot.querySelector('style')) return;
    
    if (this.isLoading) {
      this.shadowRoot.innerHTML += this.renderLoadingState();
      return;
    }
    
    if (this.hasError) {
      this.shadowRoot.innerHTML += this.renderErrorState();
      return;
    }
    
    // Default empty render - subclasses should override
    console.warn(`${this.componentName}: render() method should be overridden`);
  }

  // Utility Methods
  isEmpty() {
    if (Array.isArray(this._value)) {
      return this._value.length === 0;
    }
    return !this._value;
  }

  hasDirtyInstances() {
    return Array.from(this.nttInstances.values()).some(ntt => ntt.isDirty);
  }

  getDirtyInstances() {
    return Array.from(this.nttInstances.values()).filter(ntt => ntt.isDirty);
  }

  getInstanceCount() {
    return this.nttInstances.size;
  }
}