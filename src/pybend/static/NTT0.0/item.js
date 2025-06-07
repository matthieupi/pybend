export class UCPItem extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.mode = 'display';
    this.schema = {};
    this.data = {};
  }

  static get observedAttributes() {
    return ['mode'];
  }

  set value(obj) {
    this.data = obj;
    this.render();
  }

  set prototype(proto) {
    this.schema = proto;
    this.render();
  }

  connectedCallback() {
    this.render();
  }

  toggleMode() {
    this.mode = this.mode === 'edit' ? 'display' : 'edit';
    this.render();
  }

  render() {
    const styles = `
      <style>
        .card { background: #2c2f4a; border-radius: 1rem; padding: 1rem; color: #fff; position: relative; }
        .edit-btn {
          position: absolute; top: 10px; right: 10px;
          cursor: pointer; background: none; border: none;
          font-size: 1.2em; color: #aaa;
        }
        label { font-weight: bold; display: block; margin-top: .5rem; }
        input, textarea {
          width: 100%; padding: .3rem; margin-bottom: .5rem;
          background: #1e1e2f; border: 1px solid #444; color: white;
        }
      </style>
    `;

    const fields = this.schema?.properties || {};
    const html = [];

    html.push(`<button class="edit-btn" title="Toggle Edit">✏️</button>`);

    for (const key in fields) {
      const def = fields[key];
      const label = def.title || key;
      const type = def.type || 'string';
      const value = this.data[key] ?? '';

      if (this.mode === 'edit') {
        if (type === 'boolean') {
          html.push(`
            <label>${label}</label>
            <input type="checkbox" id="${key}" ${value ? 'checked' : ''}>
          `);
        } else {
          html.push(`
            <label>${label}</label>
            <input type="${type === 'number' ? 'number' : 'text'}" id="${key}" value="${value}">
          `);
        }
      } else {
        html.push(`
          <label>${label}</label>
          <div>${value}</div>
        `);
      }
    }

    this.shadowRoot.innerHTML = `${styles}<div class="card">${html.join('')}</div>`;
    this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', () => this.toggleMode());
  }
}

customElements.define('ucp-item', UCPItem);
