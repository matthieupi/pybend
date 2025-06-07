export class UCPTable extends HTMLElement {
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
    this._value = Array.isArray(items) ? items : [];
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
      this._value = await res.json();
      this.render();
    } catch (err) {
      this.shadowRoot.innerHTML = `<div style="color:red">❌ Failed to fetch data</div>`;
    }
  }

  render() {
    if (!this._schema || !Array.isArray(this._value)) return;

    const fields = Object.entries(this._schema.properties || {});
    const headers = fields.map(([k, v]) => `<th>${v.title || k}</th>`).join('');
    const rows = this._value.map(item => {
      const cells = fields.map(([k]) => `<td>${item[k] ?? ''}</td>`).join('');
      return `<tr>${cells}</tr>`;
    }).join('');

    this.shadowRoot.innerHTML = `
      <style>
        table {
          width: 100%;
          border-collapse: collapse;
          background: #1a1b2e;
          color: #f8f9fa;
        }
        th, td {
          border: 1px solid #444;
          padding: 0.5rem 1rem;
        }
        th {
          background-color: #333955;
        }
      </style>
      <table>
        <thead><tr>${headers}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }
}

customElements.define('ucp-table', UCPTable);
