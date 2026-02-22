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
    return ['model', 'method', 'uuid', 'mode', 'label', 'forward',
            'layout', 'placeholder', 'button-label', 'widget'];
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
    this.layout = this.getAttribute('layout') || 'fieldset';
    this.placeholderText = this.getAttribute('placeholder') || '';
    this.buttonLabel = this.getAttribute('button-label') || 'Run';
    this.widgetOverride = this.getAttribute('widget') || '';

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

    // For inline layout: clear inputs after submit instead of showing response
    if (this.layout === 'inline') {
      this.value = {};
      this.response = null;
      this.shadowRoot.querySelectorAll('input, textarea').forEach(el => { el.value = ''; });
      // Re-fetch the parent entity so the list updates
      if (this.ntt) setTimeout(() => this.ntt.pull(), 300);
    } else {
      this.render();
    }
  }

  render() {
    if (this.layout === 'inline') return this.renderInline();
    return this.renderFieldset();
  }

  /** Default fieldset layout (existing behavior). */
  renderFieldset() {
    const fields = Object.entries(this.schema.parameters || {});
    const defs = this.proto?.schema?.$defs || {};
    const formInputs = fields.map(([key, def]) => {
      if (def.type === 'selfref') {
        return `
          <label>${def.title || key}</label>
          <input name="${key}" type="number" value="${this.value[key] || ''}" placeholder="Parent ID (optional)" />
        `;
      }
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
      <style>${NTTMethod.baseStyles}</style>
      <fieldset>
        <legend>${this.label}</legend>
        <form>
          ${formInputs}
          ${this.mode === 'manual' ? `<button type="submit">${this.buttonLabel}</button>` : ''}
        </form>
        ${output}
      </fieldset>
    `;

    this.#bindInputs();
  }

  /** Inline layout: no fieldset, no legend, no labels. Compact textarea/input + button. */
  renderInline() {
    const fields = Object.entries(this.schema.parameters || {});
    const defs = this.proto?.schema?.$defs || {};
    const placeholder = this.placeholderText;
    const useTextarea = this.widgetOverride === 'textarea';
    let formInputs = '';

    // Build inputs — for $ref params, render only required fields from referenced schema
    if (fields.length === 1) {
      const [key, def] = fields[0];
      if (def.type === '$ref' && def.$ref) {
        const refName = def.$ref.replace('#/$defs/', '');
        const refSchema = defs[refName];
        if (refSchema?.properties) {
          const required = refSchema.required || [];
          const reqFields = Object.entries(refSchema.properties).filter(([k]) => required.includes(k));
          if (reqFields.length === 1 || useTextarea) {
            // Single required field or textarea mode: render one input
            const [fk] = reqFields[0];
            if (useTextarea) {
              formInputs = `<textarea name="${key}.${fk}" placeholder="${placeholder}">${this.value?.[key]?.[fk] || ''}</textarea>`;
            } else {
              formInputs = `<div class="method-inline-row">
                <input name="${key}.${fk}" type="text" value="${this.value?.[key]?.[fk] || ''}" placeholder="${placeholder}" />
                <button type="submit">${this.buttonLabel}</button>
              </div>`;
            }
          } else {
            // Multiple required fields: stacked inputs with placeholders
            formInputs = reqFields.map(([fk, fp]) =>
              `<input name="${key}.${fk}" type="${fp.type === 'number' ? 'number' : 'text'}" value="${this.value?.[key]?.[fk] || ''}" placeholder="${fp.title || fk}" />`
            ).join('');
          }
        }
      } else {
        // Simple param
        if (useTextarea) {
          formInputs = `<textarea name="${key}" placeholder="${placeholder}">${this.value[key] || ''}</textarea>`;
        } else {
          formInputs = `<div class="method-inline-row">
            <input name="${key}" type="${def.type || 'text'}" value="${this.value[key] || ''}" placeholder="${placeholder}" />
            <button type="submit">${this.buttonLabel}</button>
          </div>`;
        }
      }
    } else {
      // Multiple params: stacked
      formInputs = fields.map(([key, def]) =>
        `<input name="${key}" type="${def.type || 'text'}" value="${this.value[key] || ''}" placeholder="${def.title || key}" />`
      ).join('');
    }

    // For textarea or multi-field, put button below
    const needsExternalButton = useTextarea || fields.length > 1 ||
      (fields.length === 1 && fields[0][1].type === '$ref' && !formInputs.includes('method-inline-row'));
    const buttonHtml = needsExternalButton
      ? `<div class="actions"><button type="submit">${this.buttonLabel}</button></div>`
      : '';

    this.shadowRoot.innerHTML = `
      <style>${NTTMethod.baseStyles}${NTTMethod.inlineStyles}</style>
      <div class="method-inline">
        <form>
          ${formInputs}
          ${buttonHtml}
        </form>
      </div>
    `;

    this.#bindInputs();
  }

  /** Bind input listeners and form submit. */
  #bindInputs() {
    this.shadowRoot.querySelectorAll('input, textarea').forEach(el => {
      el.addEventListener('input', e => this.handleInput(e));
    });

    const form = this.shadowRoot.querySelector('form');
    if (form) {
      form.onsubmit = e => {
        e.preventDefault();
        this.callMethod();
      };
    }
  }

  static baseStyles = `
    :host { display: block; margin: 1rem 0; }
    fieldset {
      border: 1px solid var(--border);
      border-radius: 1rem;
      padding: 1rem;
      background: var(--glass-bg);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
    }
    legend { font-weight: bold; padding: 0 0.5rem; color: var(--text-0); }
    label { display: block; margin-top: 1rem; color: var(--text-2); font-size: 0.9rem; }
    input {
      width: 100%; padding: 0.5rem 0.8rem;
      background: var(--surface-3);
      color: var(--text-0);
      border: 1px solid var(--border);
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
      background: var(--surface-3);
      padding: 0.8rem;
      border-radius: 0.5rem;
      border: 1px solid var(--border);
      color: var(--text-1);
    }
  `;

  static inlineStyles = `
    .method-inline {
      margin-top: 0.75rem;
    }
    .method-inline textarea {
      width: 100%;
      min-height: 80px;
      resize: vertical;
      padding: 0.6rem 0.8rem;
      background: var(--surface-3);
      color: var(--text-0);
      border: 1px solid var(--border);
      border-radius: 8px;
      font-family: inherit;
      font-size: 0.85rem;
      box-sizing: border-box;
    }
    .method-inline textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-dim);
    }
    .method-inline .actions {
      display: flex;
      justify-content: flex-end;
      margin-top: 0.5rem;
    }
    .method-inline button {
      background: var(--gradient-accent);
      border: none;
      border-radius: 8px;
      padding: 0.5rem 1.2rem;
      color: white;
      cursor: pointer;
      font-size: 0.8rem;
      font-weight: 600;
      margin-top: 0;
    }
    .method-inline-row {
      display: flex;
      gap: 0.5rem;
      align-items: center;
    }
    .method-inline-row input {
      flex: 1;
    }
    .method-inline-row button {
      margin-top: 0;
    }
  `;
}

customElements.define('ntt-method', NTTMethod);
