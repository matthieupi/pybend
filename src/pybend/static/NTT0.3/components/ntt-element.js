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
  
  #addr;
  #ntt;
  
  constructor(component = 'ntt-element') {
    super();
    this.attachShadow({ mode: 'open' });
    
    // Component identification
    this.component = component;
    this.#addr = randomUUID();
    this.#ntt = {};
    // Component state
    this.isLoading = true;
    this.hasError = false;
    this.errorMessage = '';
    this.subscriptions = [];
    // Load base styles
    let _ = this.loadStyles();
  }

  static get observedAttributes() {
    return ['href', 'addr', 'href', 'data', 'schema']
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
    if (newVal !== oldVal) {
      this[name] = newVal;
    }
  }

  get ntt() {
    return this.#ntt;
  }
  
  set ntt(ntt) {
    this.#ntt = ntt;
  }
  
  set href(url) {
    this.#ntt.href = url;
    this.connect();
  }

  get href() {
    return this._href;
  }

  get data() {
    return this.#ntt.data;
  }
  
  set data(val) {
    this.#ntt.data = val;
    this.onDataChanged();
  }
  
  set schema(schema) {
    this._schema = schema;
    this.onSchemaChanged();
  }

  get schema() {
    return this.#ntt.schema;
  }
  
  update(ntt) {
    this.#ntt = ntt
    this.refresh()
  }

  connect() {
    if (!this._href) return;
    NTT.register(this.#addr, this.href, this.update.bind(this))
    this.setLoadingState(true);
    this.clearError();
  }

  disconnectedCallback() {
    this.subscriptions.forEach(unsubscribe => unsubscribe());
    this.subscriptions = [];
    NTT.unregister(this.#addr);
  }

  // State Management
  setLoadingState(loading) {
    this.isLoading = loading;
    this.render();
  }

  setError(message) {
    this.hasError = true;
    this.errorMessage = message;
    this.render();
  }

  clearError() {
    this.hasError = false;
    this.errorMessage = '';
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
    
    else if (this.isEmpty()) {
      this.shadowRoot.innerHTML += this.renderEmptyState();
      return;
    }
    
    // Default empty render - subclasses should override
    console.warn(`${this.componentName}: render() method should be overridden`);
  }
  
  refresh() { }

  // Utility Methods
  isEmpty() {
    if (Array.isArray(this._value)) {
      return this._value.length === 0;
    }
    return !this._value;
  }

}