import './item.js';

export class UCPList extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._href = null;
    this._value = [];
    this._schema = {};
  }

  static get observedAttributes() {
    return ['href'];
  }

  attributeChangedCallback(name, oldVal, newVal) {
    if (name === 'href' && newVal !== oldVal) {
      this.href = newVal;
    }
  }

  set href(url) {
    this._href = url;
    this.fetchData();
  }

  get href() {
    return this._href;
  }

  set value(items) {
    if (!Array.isArray(items)) {
      console.warn('Value must be an array');
      return;
    }
    this._value = items;
    this.render();
  }

  set prototype(schema) {
    this._schema = schema;
    this.render();
  }

  async fetchData() {
    if (!this._href) return;
    try {
      const res = await fetch(this._href);
      const data = await res.json();
      this._value = data;
      this.render();
    } catch (e) {
      console.error(`Failed to fetch from ${this._href}`, e);
      this.shadowRoot.innerHTML = `<div style="color: red">❌ Failed to load data</div>`;
    }
  }

  render() {
    if (!this._schema || !Array.isArray(this._value)) return;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: grid;
          gap: 1rem;
        }
      </style>
    `;

    this._value.forEach(item => {
      const el = document.createElement('ucp-item');
      el.value = item;
      el.prototype = this._schema;
      this.shadowRoot.appendChild(el);
    });
  }
}

customElements.define('ucp-list', UCPList);
