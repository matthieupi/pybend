// components/ntx-method.js
import { Component } from '../core/Component.js';
import { NTT } from '../core/NTT.js';
import { Formidable } from '../generators/form.js';
import Logging from '../utils/Logging.js';
import { iconMarkup } from '../utils/icon-resolver.js';
import { permissions } from '../utils/Permissions.js';
import './ntx-icon.js';

function humanizeMethodName(name = '') {
  return String(name).replace(/_/g, ' ');
}

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
    this.optionalExpanded = false;
  }

  get styles() {
    return new URL('./ntx-method.css', import.meta.url).href;
  }

  static get observedAttributes() {
    return ['model', 'method', 'uuid', 'mode', 'label', 'forward',
            'layout', 'placeholder', 'button-label', 'widget',
            'icon', 'count-field', 'show-label'];
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
    this.#readAttrs();
    if (!this.#resolveProto()) return;
    this.#clearSubscription();
    if (!this.#resolveInstance()) return;
    if (!this.#resolveMethodSchema()) return;
    this.#setupCountSubscription();
    this.render();
  }

  handleInput(e) {
    if (this.mode === 'auto') this.callMethod();
  }

  callMethod() {
    const caller = this.ntt || this.proto;
    if (!caller?.call) return;

    const formLike = this.#formLike();
    const nextValue = this.#hasRenderedInputs()
      ? Formidable.readFormValue(this.shadowRoot, formLike)
      : { ...(this.value || {}) };
    const errors = Formidable.validateForm({ ...formLike, value: nextValue });
    if (errors.length > 0) {
      Formidable.showFieldErrors(this.shadowRoot, errors);
      return;
    }
    this.value = nextValue;

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
      this.optionalExpanded = false;
      this.render();
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
    const visibleLabel = this.showLabel ? (this.buttonLabel || this.label || this.method) : '';
    const buttonClass = this.showLabel ? 'method-btn method-btn--labeled' : 'method-btn';

    this.shadowRoot.innerHTML = `
      <button class="${buttonClass}" title="${this.label}">
        ${icon ? `<span class="method-btn-icon">${icon}</span>` : ''}
        ${visibleLabel ? `<span class="method-btn-text">${visibleLabel}</span>` : ''}
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
    this.#renderFormShell({ inline: false });
  }

  /** Inline layout: no fieldset, no legend, no labels. Compact textarea/input + button. */
  renderInline() {
    this.#renderFormShell({ inline: true });
  }

  /** Bind input listeners and form submit. */
  #bindInputs() {
    this.#bindActionButtons();
    this.shadowRoot.querySelectorAll('input, textarea, select').forEach(el => {
      el.addEventListener('input', e => this.handleInput(e));
      el.addEventListener('change', e => this.handleInput(e));
    });
    this.shadowRoot.querySelectorAll('ntx-list-field').forEach(el => {
      el.addEventListener('field-change', e => this.handleInput(e));
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

  #readAttrs() {
    const modelName = this.getAttribute('model');
    this.method = this.getAttribute('method');
    this.uuid = this.getAttribute('uuid');
    this.mode = this.getAttribute('mode') || 'manual';
    this.label = this.getAttribute('label') || humanizeMethodName(this.method);
    this.forward = this.getAttribute('forward');
    this.layout = this.getAttribute('layout') || 'fieldset';
    this.placeholderText = this.getAttribute('placeholder') || '';
    this.buttonLabel = this.getAttribute('button-label') || 'Run';
    this.widgetOverride = this.getAttribute('widget') || '';
    this.iconName = this.getAttribute('icon') || '';
    this.countField = this.getAttribute('count-field') || '';
    this.showLabel = this.hasAttribute('show-label');
    this.optionalExpanded = false;
    if (modelName) this.model = modelName;
  }

  #resolveProto() {
    const proto = NTT.get(this.model);
    if (!proto) {
      Logging.error(`[ntx-method] Model not found`, this.model);
      return false;
    }
    if (proto !== this.proto) this.define(proto);
    return true;
  }

  #clearSubscription() {
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
  }

  #resolveInstance() {
    this.ntt = null;
    if (!this.uuid) return true;
    this.ntt = NTT.get(this.model + '/' + this.uuid);
    if (!this.ntt) {
      Logging.error(`[ntx-method] Instance not found`, this.uuid);
      return false;
    }
    return true;
  }

  #resolveMethodSchema() {
    const methodSchema = this.proto?.schema?.methods?.[this.method];
    if (!methodSchema) {
      Logging.error(`[ntx-method] Method schema not found`, this.method);
      return false;
    }
    this.methodSchema = methodSchema;
    this.iconName = this.iconName || methodSchema?.ui?.icon || '';
    this.countField = this.countField || methodSchema?.ui?.count_field || '';
    return true;
  }

  #setupCountSubscription() {
    if (this.layout === 'button' && this.countField && this.ntt?.signal) {
      this._unsub = this.ntt.signal(() => this.render(), true);
    }
  }

  #renderFormShell({ inline = false } = {}) {
    const mode = this.mode || 'manual';
    const { primaryFields, optionalFields } = this.#partitionFields();
    const hasPrimary = primaryFields.length > 0;
    const hasOptional = optionalFields.length > 0;
    const collapsedActionOnly = !hasPrimary && hasOptional && !this.optionalExpanded;
    const compactInline = inline && !this.optionalExpanded && this.#isCompactInlineMethod(primaryFields);
    const submitButton = mode === 'manual'
      ? `<button type="submit">${this.#buttonContent(this.buttonLabel)}</button>`
      : '';
    const output = !inline && this.response
      ? `<pre class="output">${JSON.stringify(this.response, null, 2)}</pre>`
      : '';

    if (collapsedActionOnly) {
      const actionButton = `<button type="button" class="method-btn method-btn--labeled" data-action="call-method">${this.#buttonContent(this.#displayLabel())}</button>`;
      const toggleButton = this.#optionalToggleButton();

      if (inline) {
        this.shadowRoot.innerHTML = `
          <div class="method-inline method-collapsed-actions">
            ${actionButton}
            ${toggleButton}
          </div>
        `;
      } else {
        this.shadowRoot.innerHTML = `
          <fieldset class="method-fieldset">
            <legend>
              <span class="method-legend">${this.#buttonContent(this.#displayLabel())}</span>
            </legend>
            <div class="method-collapsed-actions">
              ${actionButton}
              ${toggleButton}
            </div>
            ${output}
          </fieldset>
        `;
      }

      this.#bindInputs();
      return;
    }

    const primaryHtml = compactInline
      ? this.#renderCompactInlineBody(primaryFields)
      : this.#renderFields(primaryFields, { inline });
    const optionalHtml = this.optionalExpanded
      ? this.#renderFields(optionalFields, { inline })
      : '';
    const optionalToggle = hasOptional ? `
      <div class="method-optional-toggle-row">
        ${this.#optionalToggleButton()}
      </div>
    ` : '';
    const optionalPanel = hasOptional && this.optionalExpanded
      ? `<div class="method-optional-panel">${optionalHtml}</div>`
      : '';

    if (inline) {
      const actionHtml = compactInline ? '' : (submitButton ? `<div class="actions">${submitButton}</div>` : '');
      this.shadowRoot.innerHTML = `
        <div class="method-inline">
          <form class="method-form method-form-inline">
            ${compactInline ? primaryHtml + submitButton : primaryHtml + optionalToggle + optionalPanel + actionHtml}
          </form>
          ${compactInline ? optionalToggle + optionalPanel : ''}
        </div>
      `;
    } else {
      this.shadowRoot.innerHTML = `
        <fieldset class="method-fieldset">
          <legend>
            <span class="method-legend">${this.#buttonContent(this.label)}</span>
          </legend>
          <form class="method-form">
            ${primaryHtml}
            ${optionalToggle}
            ${optionalPanel}
            ${submitButton}
          </form>
          ${output}
        </fieldset>
      `;
    }

    this.#bindInputs();
  }

  #isCompactInlineMethod(keys = []) {
    if (keys.length !== 1) return false;
    if (String(keys[0]).includes('.')) return false;
    if (this.widgetOverride === 'textarea') return false;
    const def = this.#normalizedMethodSchema()?.properties?.[keys[0]] || {};
    const type = def?.type || 'string';
    return !def?.$ref && type !== 'array' && type !== 'object';
  }

  #renderCompactInlineBody(keys = []) {
    const [key] = keys;
    const inputHtml = Formidable.getInput(this.#renderFormLike({ inline: true, compact: true }), key, 'edit');
    return `<div class="method-inline-row">${inputHtml}</div>`;
  }

  #renderFields(keys = [], { inline = false } = {}) {
    if (!keys.length) return '';
    const formLike = this.#renderFormLike({ inline });
    return keys.map((key) => Formidable.getInput(formLike, key, 'edit')).join('');
  }

  #renderFormLike({ inline = false, compact = false } = {}) {
    const rawSchema = this.methodSchema || this.schema || {};
    const normalized = this.#normalizedMethodSchema();
    const rawFieldCount = Object.keys(rawSchema.parameters || rawSchema.properties || {}).length;
    const properties = Object.fromEntries(Object.entries(normalized.properties || {}).map(([key, def]) => {
      const ui = { ...(def.ui || {}) };
      const keyFallback = String(key).split('.').pop();
      if (inline) {
        ui.placeholder = this.placeholderText || ui.placeholder || def.title || keyFallback;
      }
      if (compact) {
        ui.label = false;
      }
      if (this.widgetOverride === 'textarea' && rawFieldCount === 1) {
        ui.widget = 'textarea';
      }
      return [key, { ...def, ui }];
    }));

    return {
      schema: {
        ...normalized,
        properties,
      },
      value: this.value,
      name: this.method || this.#displayLabel() || 'method',
    };
  }

  #normalizedMethodSchema() {
    return Formidable.normalizeSchema(this.#formLike().schema || {});
  }

  #partitionFields() {
    const normalized = this.#normalizedMethodSchema();
    const fields = normalized?.properties || {};
    const ui = normalized?.ui || {};
    const explicitOrder = Array.isArray(ui.field_order) ? ui.field_order.filter((key) => key in fields) : [];
    const ordered = [...explicitOrder];
    for (const key of Object.keys(fields)) {
      if (!ordered.includes(key)) ordered.push(key);
    }
    const renderable = ordered.filter((key) => {
      const def = fields[key];
      if (def?.ui?.display === false) return false;
      if (def?.ui?.protected) return false;
      if (!permissions.canView(def)) return false;
      return true;
    });
    const required = new Set(normalized?.required || []);
    return {
      primaryFields: renderable.filter((key) => required.has(key)),
      optionalFields: renderable.filter((key) => !required.has(key)),
    };
  }

  #optionalToggleButton() {
    const text = this.optionalExpanded ? 'Hide options' : 'Show options';
    return `<button type="button" class="method-optional-toggle" data-action="toggle-optional">${text}</button>`;
  }

  #displayLabel() {
    return this.label || humanizeMethodName(this.method);
  }

  #hasRenderedInputs() {
    return !!this.shadowRoot.querySelector('[data-key], ntx-list-field');
  }

  #formLike(value = this.value, { inline = false, compact = false } = {}) {
    const schema = this.methodSchema || this.schema || {};
    const paramKeys = Object.keys(schema.parameters || schema.properties || {}).join(',');
    const schemaName = schema.__name__ || `${this.model || 'method'}.${this.method || this.label || 'call'}:${paramKeys}`;
    const fields = Object.fromEntries(Object.entries(schema.parameters || schema.properties || {}).map(([key, def]) => {
      const ui = { ...(def.ui || {}) };
      if (inline) {
        ui.placeholder = this.placeholderText || ui.placeholder || def.title || key;
      }
      if (compact) {
        ui.label = false;
      }
      if (this.widgetOverride === 'textarea' && Object.keys(schema.parameters || {}).length === 1) {
        ui.widget = 'textarea';
      }
      return [key, { ...def, ui }];
    }));
    return {
      schema: {
        ...schema,
        __name__: schemaName,
        parameters: schema.parameters ? fields : undefined,
        properties: schema.properties ? fields : undefined,
        $defs: schema.$defs || this.proto?.schema?.$defs || {},
      },
      value,
      name: this.method || this.#displayLabel() || 'method',
    };
  }

  #bindActionButtons() {
    this.shadowRoot.querySelectorAll('[data-action="toggle-optional"]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        this.optionalExpanded = !this.optionalExpanded;
        this.render();
      });
    });

    this.shadowRoot.querySelectorAll('[data-action="call-method"]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        this.callMethod();
      });
    });
  }

}

customElements.define('ntx-method', NTTMethod);
