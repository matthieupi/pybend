// components/ntt-method.js
import { NTT } from '../core/NTT.js';

export class NTTMethod extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.value = {};
    this.schema = null;
    this.proto = null;
    this.ntt = null;
    this.response = null;
  }

  static get observedAttributes() {
    return ['model', 'method', 'uuid', 'mode', 'label', 'forward'];
  }

  connectedCallback() {
    this.load();
  }

  attributeChangedCallback() {
    this.load();
  }

  async load() {
    this.model = this.getAttribute('model');
    this.method = this.getAttribute('method');
    this.uuid = this.getAttribute('uuid');
    this.mode = this.getAttribute('mode') || 'manual';
    this.label = this.getAttribute('label') || this.method;
    this.forward = this.getAttribute('forward');

    this.proto = NTT.get(this.model);
    if (!this.proto) return console.error(`[ntt-method] Model not found: ${this.model}`);

    if (this.uuid) {
      this.ntt = NTT.get(this.model + '/' + this.uuid);
      if (!this.ntt) return console.error(`[ntt-method] Instance not found: ${this.uuid}`);
    }

    const methodSchema = this.proto.schema?.methods?.[this.method];
    if (!methodSchema) return console.error(`[ntt-method] Method schema not found for ${this.method}`);
    this.schema = methodSchema;

    this.render();
  }

  handleInput(e) {
    const name = e.target.name;
    let val = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    if (name.includes('.')) {
      const [param, field] = name.split('.');
      if (!this.value[param]) this.value[param] = {};
      this.value[param][field] = val;
    } else {
      this.value[name] = val;
    }
    if (this.mode === 'auto') this.callMethod();
  }

  callMethod() {
    const payload = { ...this.value };
    const target = this.schema.scope === 'instancemethod' ? this.ntt : this.proto;
    if (!target || !target.call) return console.warn(`[ntt-method] Invalid call target.`);

    target.call(this.method, payload, { inbox: '_response_' });
    this.response = { status: 'sent' };
    this.render();
  }

  render() {
    const fields = Object.entries(this.schema.parameters || {});
    const defs = this.proto?.schema?.$defs || {};
    const formInputs = fields.map(([key, def]) => {
      if (def.type === '$ref' && def.$ref) {
        const refName = def.$ref.replace('#/$defs/', '');
        const refSchema = defs[refName];
        if (!refSchema?.properties) return `<label>${key} (unresolved)</label>`;
        const required = refSchema.required || [];
        return Object.entries(refSchema.properties)
          .filter(([k]) => required.includes(k))
          .map(([k, p]) => `
            <label>${p.title || k}</label>
            <input name="${key}.${k}" type="${p.type === 'number' ? 'number' : 'text'}" value="${this.value?.[key]?.[k] || ''}" />
          `).join('');
      }
      return `
        <label>${def.title || key}</label>
        <input name="${key}" type="${def.type || 'text'}" value="${this.value[key] || ''}" />
      `;
    }).join('');

    const output = this.response
      ? `<pre class="output">${JSON.stringify(this.response, null, 2)}</pre>`
      : '';

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; margin: 1rem 0; }
        fieldset {
          border: 1px solid var(--border-color);
          border-radius: 1rem;
          padding: 1rem;
          background: var(--bg-glass);
        }
        legend { font-weight: bold; padding: 0 0.5rem; }
        label { display: block; margin-top: 1rem; color: var(--text-secondary); font-size: 0.9rem; }
        input {
          width: 100%; padding: 0.5rem 0.8rem;
          background: var(--bg-tertiary);
          color: var(--text-primary);
          border: 1px solid var(--border-color);
          border-radius: 8px;
        }
        button {
          margin-top: 1rem;
          background: var(--gradient-accent);
          border: none;
          border-radius: 8px;
          padding: 0.6rem 1.2rem;
          color: white;
          cursor: pointer;
        }
        .output {
          margin-top: 1rem;
          font-family: monospace;
          background: var(--bg-tertiary);
          padding: 0.8rem;
          border-radius: 0.5rem;
          border: 1px solid var(--border-color);
        }
      </style>
      <fieldset>
        <legend>${this.label}</legend>
        <form>
          ${formInputs}
          ${this.mode === 'manual' ? '<button type="submit">Run</button>' : ''}
        </form>
        ${output}
      </fieldset>
    `;

    this.shadowRoot.querySelectorAll('input').forEach(el => {
      el.addEventListener('input', e => this.handleInput(e));
    });

    const form = this.shadowRoot.querySelector('form');
    if (form && this.mode === 'manual') {
      form.onsubmit = e => {
        e.preventDefault();
        this.callMethod();
      }
    }
  }
}

customElements.define('ntt-method', NTTMethod);
