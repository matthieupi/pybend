// components/ntx-method.js
import { Component } from '../core/Component.js';
import { NTT } from '../core/NTT.js';
import Logging from '../utils/Logging.js';
import { iconMarkup } from '../utils/icon-resolver.js';
import './ntx-icon.js';

export class NTTMethod extends Component {
  static baseStyles = `
    fieldset {
      min-width: 0;
    }

    input {
      width: 100%;
      min-width: 0;
      box-sizing: border-box;
    }

    textarea {
      width: 100%;
      min-width: 0;
      box-sizing: border-box;
    }
  `;
  static inlineStyles = 'method-inline method-form-inline';
  static buttonStyles = 'method-btn method-btn-icon';

  constructor() {
    super();  // Component handles shadow DOM, addr, Matrix registration
    Object.defineProperty(this, 'schema', {
      value: null,
      writable: true,
      configurable: true,
    });
    this.value = {};
    this.ntt = null;
    this.methodSchema = null;
    this.response = null;
  }

  get styles() {
    return new URL('./ntx-method.css', import.meta.url).href;
  }

  static get observedAttributes() {
    return ['model', 'method', 'uuid', 'mode', 'label', 'forward',
            'layout', 'placeholder', 'button-label', 'widget',
            'icon', 'count-field'];
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._unsub) { this._unsub(); this._unsub = null; }
  }

  attributeChangedCallback() {
    this.load();
  }

  async load() {
    const modelName = this.getAttribute('model');
    this.method = this.getAttribute('method');
    this.uuid = this.getAttribute('uuid');
    this.mode = this.getAttribute('mode') || 'manual';
    this.label = this.getAttribute('label') || this.method;
    this.forward = this.getAttribute('forward');
    this.layout = this.getAttribute('layout') || 'fieldset';
    this.placeholderText = this.getAttribute('placeholder') || '';
    this.buttonLabel = this.getAttribute('button-label') || 'Run';
    this.widgetOverride = this.getAttribute('widget') || '';
    this.iconName = this.getAttribute('icon') || '';
    this.countField = this.getAttribute('count-field') || '';

    if (modelName) this.model = modelName;

    const proto = NTT.get(this.model);
    if (!proto) return Logging.error(`[ntx-method] Model not found`, this.model);
    // Set proto through Component's define()
    if (proto !== this.proto) this.define(proto);

    // Unsubscribe from previous entity if switching
    if (this._unsub) { this._unsub(); this._unsub = null; }

    if (this.uuid) {
      this.ntt = NTT.get(this.model + '/' + this.uuid);
      if (!this.ntt) return Logging.error(`[ntx-method] Instance not found`, this.uuid);

      // For button layouts with a count field, subscribe to entity value
      // changes so the count badge updates after pull() completes.
      if (this.layout === 'button' && this.countField && this.ntt.signal) {
        this._unsub = this.ntt.signal(() => this.render(), true);
      }
    }

    const methodSchema = this.proto?.schema?.methods?.[this.method];
    if (!methodSchema) return Logging.error(`[ntx-method] Method schema not found`, this.method);
    this.methodSchema = methodSchema;
    this.iconName = this.iconName || this.methodSchema?.ui?.icon || '';
    this.countField = this.countField || this.methodSchema?.ui?.count_field || '';

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
    const caller = this.ntt || this.proto;
    if (!caller?.call) return;

    // Use entity/prototype call() which sets meta.inbox='_response_'
    // so the reply routes back to _response_() → pull() → UI refresh.
    caller.call(this.method, { ...this.value }, { inbox: '_response_' });
    this.response = { status: 'sent' };
    this.#postCall();
  }

  /**
   * Handle method response — reply TX arrives at this component's inbox.
   * Replaces the _response_ on DynamicClass prototype for method components.
   */
  _response_(data, tx) {
    this.response = data;
    // Trigger entity refresh so list/item components update
    if (this.ntt?.pull) this.ntt.pull();
    else if (this.proto?.pull) this.proto.pull();
  }

  #postCall() {
    if (this.layout === 'inline') {
      this.value = {};
      this.response = null;
      this.shadowRoot.querySelectorAll('input, textarea').forEach(el => { el.value = ''; });
    } else {
      this.render();
    }
  }

  render() {
    const schema = this.methodSchema || this.schema;
    if (!schema) return;  // Not loaded yet
    if (this.layout === 'inline') return this.renderInline();
    if (this.layout === 'button') return this.renderButton();
    return this.renderFieldset();
  }

  /** Button layout: compact icon + count pill. */
  renderButton() {
    const icon = iconMarkup(this.iconName, {
      label: this.label,
      className: 'method-icon',
    });
    let count = '';
    if (this.countField) {
      const val = this.ntt?.value ?? this.getRootNode()?.host?.value;
      const raw = val?.[this.countField];
      // Handle both plain arrays and populated wrappers ({data: [...], meta: {total}})
      if (Array.isArray(raw)) {
        count = raw.length;
      } else if (raw && typeof raw === 'object' && Array.isArray(raw.data)) {
        count = raw.meta?.total ?? raw.data.length;
      } else {
        count = 0;
      }
    }

    this.shadowRoot.innerHTML = `
      <button class="method-btn" title="${this.label}">
        ${icon ? `<span class="method-btn-icon">${icon}</span>` : ''}
        ${count !== '' ? `<span class="method-btn-count">${count}</span>` : ''}
      </button>
    `;

    this.shadowRoot.querySelector('.method-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.callMethod();
    });
  }

  /** Default fieldset layout (existing behavior). */
  renderFieldset() {
    const schema = this.methodSchema || this.schema || {};
    const fields = Object.entries(schema.parameters || {});
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
      <fieldset class="method-fieldset">
        <legend>
          <span class="method-legend">${this.#buttonContent(this.label)}</span>
        </legend>
        <form class="method-form">
          ${formInputs}
          ${this.mode === 'manual' ? `<button type="submit">${this.#buttonContent(this.buttonLabel)}</button>` : ''}
        </form>
        ${output}
      </fieldset>
    `;

    this.#bindInputs();
  }

  /** Inline layout: no fieldset, no legend, no labels. Compact textarea/input + button. */
  renderInline() {
    const schema = this.methodSchema || this.schema || {};
    const fields = Object.entries(schema.parameters || {});
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
                <button type="submit">${this.#buttonContent(this.buttonLabel)}</button>
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
              <button type="submit">${this.#buttonContent(this.buttonLabel)}</button>
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
      ? `<div class="actions"><button type="submit">${this.#buttonContent(this.buttonLabel)}</button></div>`
      : '';

    this.shadowRoot.innerHTML = `
      <div class="method-inline">
        <form class="method-form method-form-inline">
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

  #buttonContent(text) {
    const icon = iconMarkup(this.iconName, {
      label: this.label || text,
      className: 'method-icon',
    });
    if (!icon) return text || '';
    const label = text ? `<span class="method-btn-label">${text}</span>` : '';
    return `${icon}${label}`;
  }

}

customElements.define('ntx-method', NTTMethod);
