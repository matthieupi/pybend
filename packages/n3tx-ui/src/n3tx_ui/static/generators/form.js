import { permissions } from '../utils/Permissions.js';
import { NTT } from '../core/NTT.js';
import Logging from '../utils/Logging.js';
import { getWidgetForField } from '../widgets/index.js';
import '../components/ntx-ref-picker.js';

  // Layout cache: stores { renderableFields, groups } per schema+mode+role.
  // Eliminates O(n²) field order computation and repeated permission checks
  // across all items sharing the same schema (e.g. 30 Product cards).
  const _layoutCache = new Map();
  const _headerFieldSet = new Set(['name', 'title', 'id', 'description']);

  function _getLayout(schema, mode) {
      const cacheKey = `${schema.__name__ || schema.title || ''}:${mode}:${permissions.role}`;
      const cached = _layoutCache.get(cacheKey);
      if (cached) return cached;

      const fields = schema.properties || {};
      const ui = schema.ui || {};

      // O(n) field order with Set (was O(n²) with Array.includes)
      const fieldOrder = ui.field_order
          ? ui.field_order.filter(k => k in fields)
          : Object.keys(fields);
      const inOrder = new Set(fieldOrder);
      for (const k of Object.keys(fields)) {
          if (!inOrder.has(k)) fieldOrder.push(k);
      }

      // Filter renderable fields — permission checks run once per schema, not per item
      const renderableFields = fieldOrder.filter(key => {
          if (_headerFieldSet.has(key)) return false;
          const def = fields[key];
          if (def?.ui?.display === false) return false;
          if (mode === 'edit' && def?.ui?.protected) return false;
          if (!permissions.canView(def)) return false;
          return true;
      });

      const layout = { renderableFields, groups: ui.groups };
      _layoutCache.set(cacheKey, layout);
      return layout;
  }

  function refInput(ref) {
    const ptt = NTT.get(ref);
    if (!ptt) {
      Logging.error(`[form] No NTT found for reference`, ref);
      return `<input type="text" placeholder="Invalid reference">`;
    }
    // Assuming ptt has a schema with properties
    const schema = ptt.schema || {};
    return getForm(schema);

  }


  function getForm(ntt, mode="display", attachedMethods = {}) {
      const { renderableFields, groups } = _getLayout(ntt.schema, mode);

      let $header = getHeader(ntt, mode);

      // Render with groups if schema.ui.groups is defined
      let $fields;
      if (groups && typeof groups === 'object') {
          $fields = renderGroupedFields(ntt, renderableFields, groups, mode, attachedMethods);
      } else {
          // Ungrouped: render fields, then append attached methods after their target field
          let fieldsHtml = renderableFields.map(key => {
              let html = getInput(ntt, key, mode);
              if (mode !== 'edit') {
                  for (const [methodName, methodDef] of Object.entries(attachedMethods)) {
                      if (methodDef.ui?.attach_to === key) {
                          html += renderAttachedMethod(ntt, methodName, methodDef);
                      }
                  }
              }
              return html;
          }).join('');
          $fields = fieldsHtml;
      }

      return $header.concat($fields).join('');
  }

  /**
   * Render fields organized into fieldset groups.
   * Fields not in any group are appended at the end ungrouped.
   */
  function renderAttachedMethod(ntt, methodName, methodDef) {
      const ui = methodDef.ui || {};
      const tag = methodDef.stream ? 'ntx-stream' : 'ntx-method';
      return `<${tag}
          model="${ntt.schema.__name__}"
          uuid="${ntt.value?.id || ''}"
          method="${methodName}"
          layout="${ui.layout || 'fieldset'}"
          placeholder="${ui.placeholder || ''}"
          button-label="${ui.button_label || 'Run'}"
          widget="${ui.widget || ''}"
          icon="${ui.icon || ''}"
          count-field="${ui.count_field || ''}"
          label="${methodDef.title || methodName}">
      </${tag}>`;
  }

  function renderGroupedFields(ntt, renderableFields, groups, mode, attachedMethods = {}) {
      const grouped = new Set();
      const html = [];

      for (const [groupName, groupFields] of Object.entries(groups)) {
          const fieldsInGroup = groupFields.filter(k => renderableFields.includes(k));
          if (fieldsInGroup.length === 0) continue;
          fieldsInGroup.forEach(k => grouped.add(k));
          html.push(`<fieldset class="ntx-group ntx-group-${groupName}">`);
          html.push(`<legend>${groupName}</legend>`);
          html.push(fieldsInGroup.map(key => getInput(ntt, key, mode)).join(''));

          // Inject attached methods whose attach_to field is in this group
          if (mode !== 'edit') {
              for (const [methodName, methodDef] of Object.entries(attachedMethods)) {
                  const mUi = methodDef.ui || {};
                  if (groupFields.includes(mUi.attach_to)) {
                      html.push(renderAttachedMethod(ntt, methodName, methodDef));
                  }
              }
          }

          html.push(`</fieldset>`);
      }

      // Ungrouped fields + their attached methods
      const ungrouped = renderableFields.filter(k => !grouped.has(k));
      ungrouped.forEach(key => {
          html.push(getInput(ntt, key, mode));
          if (mode !== 'edit') {
              for (const [methodName, methodDef] of Object.entries(attachedMethods)) {
                  if (methodDef.ui?.attach_to === key) {
                      html.push(renderAttachedMethod(ntt, methodName, methodDef));
                  }
              }
          }
      });

      return html.join('');
  }
 
  
  function getHeader(ntt, mode) {
      const schema = ntt.schema || {};
      const val = ntt.value || {};
      // Determine which field provides the heading (title takes priority over name)
      const nameKey = ('title' in val) ? 'title' : 'name';
      const name = val[nameKey] || schema.name || 'Unnamed';
      const desc = val.description || '';

      let headerHtml = [];

      if (mode === 'edit') {
          headerHtml.push(`<input style="font-size: 1.5rem" type="text" id="${nameKey}" data-key="${nameKey}" data-type="string" value="${name}">`);
          if (desc)
              headerHtml.push(`<textarea id="description" data-key="description" data-type="text">${desc}</textarea>`);

      } else {
          headerHtml.push(`<h2 class="${schema.name}" data-value="${nameKey}">${name}</h2>`);
          if (desc) {
              headerHtml.push(`<h4 data-value="description">${desc}</h4>`);
          }
      }

      return headerHtml;

  }
  
/**
 * Build an HTML attribute string from JSON Schema validation constraints.
 * Maps: minLength, maxLength, minimum, maximum, exclusiveMinimum,
 *       exclusiveMaximum, pattern, required → HTML5 validation attrs.
 * Returns a string like ' required minlength="3" maxlength="100"' (leading space).
 */
function validationAttrs(def, isRequired = false) {
    const attrs = [];
    if (isRequired) attrs.push('required');
    if (def.minLength != null) attrs.push(`minlength="${def.minLength}"`);
    if (def.maxLength != null) attrs.push(`maxlength="${def.maxLength}"`);
    if (def.minimum != null) attrs.push(`min="${def.minimum}"`);
    if (def.exclusiveMinimum != null) attrs.push(`min="${def.exclusiveMinimum}"`);
    if (def.maximum != null) attrs.push(`max="${def.maximum}"`);
    if (def.exclusiveMaximum != null) attrs.push(`max="${def.exclusiveMaximum}"`);
    if (def.pattern) attrs.push(`pattern="${def.pattern}"`);
    if (def.ui?.placeholder) attrs.push(`placeholder="${def.ui.placeholder}"`);
    return attrs.length ? ' ' + attrs.join(' ') : '';
}

function wrapDisplayField(label, content, { inline = false, classes = '' } = {}) {
    const className = ['field-row', inline ? 'field-row--inline' : 'field-row--block', classes]
        .filter(Boolean)
        .join(' ');
    return `<div class="${className}"><label>${label}</label>${content}</div>`;
}

function getInput(ntt, key, mode = 'display') {
    const schema = ntt.schema;
    const def = schema.properties?.[key]
    if (!def) return '';

    if (def.anyOf) {
        Object.assign(def, resolveAnyOf(def));
    }

    // Protected fields are always display-only (backend-owned)
    const effectiveMode = (mode === 'edit' && (def.ui?.protected || !permissions.canEdit(def))) ? 'display' : mode;

    if (def.type === 'array') {
        return getListInput(ntt, key, effectiveMode);
    }

    const model = ntt.name
    const label = def.title || key;
    const value = ntt.value?.[key] ?? '';
    const widget = def.ui?.widget;  // Widget hint from schema (takes priority)
    let html = [];
    const showLabel = key !== 'name' && key !== 'id';

    // ── Widget dispatch (takes priority over type-based rendering) ──
    const _wr = getWidgetForField(def);
    if (_wr.widget) {
        if (effectiveMode === 'edit' || effectiveMode === 'create') {
            if (showLabel) {
                html.push(`<label class="${model} ${model}-form-item">${label}</label>`);
            }
            const widgetEl = _wr.widget.edit(value, _wr.config, def, (newVal) => {
                // Propagate data-key/data-type so handleInputChange can process it
                const synthEvent = { target: { dataset: { key, type: def.type || 'string' }, value: newVal } };
                // Direct value propagation via custom event on parent form
            });
            // Stamp data-key/data-type on the editable element so handleInputChange works
            const editable = widgetEl.querySelector('input, textarea, select') || widgetEl;
            editable.dataset.key = key;
            editable.dataset.type = def.type || 'string';
            editable.id = editable.id || key;
            // Wrap DOM node in a container div for consistent HTML string output
            const wrapper = document.createElement('div');
            wrapper.className = 'widget-edit-wrapper';
            wrapper.dataset.key = key;
            wrapper.dataset.widgetType = _wr.name || '';
            wrapper.appendChild(widgetEl);
            html.push(wrapper.outerHTML);
        } else {
            const widgetEl = _wr.widget.display(value, _wr.config, def);
            const wrapper = document.createElement('div');
            wrapper.className = 'widget-display-wrapper';
            wrapper.dataset.value = key;
            wrapper.dataset.widgetType = _wr.name || '';
            wrapper.appendChild(widgetEl);
            if (showLabel) {
                const inlineWidget = _wr.name === 'currency' || _wr.name === 'bool';
                html.push(wrapDisplayField(label, wrapper.outerHTML, {
                    inline: inlineWidget,
                    classes: _wr.name === 'currency' ? 'field-row--numeric' : '',
                }));
            } else {
                html.push(wrapper.outerHTML);
            }
        }
        return html.join('');
    }

    const type = def.type || 'string';

    if (showLabel && effectiveMode === 'edit')
        html.push(`<label class="${model} ${model}-form-item">${label}</label>`);

    if (effectiveMode === 'edit') {
        // Build HTML5 validation attributes from schema constraints
        const v = validationAttrs(def, schema.required?.includes(key));

        // Enum fields → <select> dropdown
        if (def.enum) {
            const options = def.enum.map(opt =>
                `<option value="${opt}"${opt === value ? ' selected' : ''}>${opt}</option>`
            ).join('');
            html.push(`<select id="${key}" data-key="${key}" data-type="string"${v}>${options}</select>`);
        // Widget hint takes priority over type for edit rendering
        } else if (widget === 'textarea' || type === 'text') {
            html.push(`<textarea id="${key}" data-key="${key}" data-type="string"${v}>${value}</textarea>`);
        } else if (widget === 'currency') {
            html.push(`<div class="currency-input"><span class="currency-symbol">$</span><input type="number" step="0.01" id="${key}" data-key="${key}" data-type="number" value="${value}"${v}></div>`);
        } else if (type === 'boolean') {
            html.push(`<input type="checkbox" id="${key}" data-key="${key}" data-type="${type}" ${value ? 'checked' : ''}${v}>`);
        } else if (type === 'string') {
            html.push(`<input type="text" id="${key}" data-key="${key}" data-type="${type}" value="${value}"${v}>`);
        } else if (type === 'number' || type === 'integer') {
            html.push(`<input type="number" id="${key}" data-key="${key}" data-type="${type}" value="${value}"${v}>`);
        } else if (type === 'selfref') {
            html.push(`<input type="number" id="${key}" data-key="${key}" data-type="selfref" value="${value || ''}" placeholder="Parent ID (optional)"${v}>`);
        } else if (type === 'array') {
            html.push(getListInput(ntt, key, mode));
        } else if (type === 'object') {
            const json = (value && typeof value === 'object') ? JSON.stringify(value, null, 2) : (value || '{}');
            html.push(`<textarea id="${key}" data-key="${key}" data-type="object"${v}>${json}</textarea>`);
        } else {
            html.push(`<input type="${type}" data-key="${key}" data-type="${type}" value="${value}" id="${key}"${v}>`);
        }
    } else {
        // Enum fields → styled pill
        if (def.enum) {
            const enumHtml = `<span class="enum-pill" data-value="${key}" data-status="${value}">${value}</span>`;
            html.push(showLabel ? wrapDisplayField(label, enumHtml, { inline: true }) : enumHtml);
        // Widget hint takes priority for display rendering too
        } else if (widget === 'currency') {
            const formatted = typeof value === 'number' ? `$${value.toFixed(2)}` : value;
            const valueHtml = `<div class="currency-display" data-value="${key}">${formatted}</div>`;
            html.push(showLabel ? wrapDisplayField(label, valueHtml, { inline: true, classes: 'field-row--numeric' }) : valueHtml);
        } else if (widget === 'textarea') {
            const valueHtml = `<div class="text-block" data-value="${key}">${value}</div>`;
            html.push(showLabel ? wrapDisplayField(label, valueHtml) : valueHtml);
        } else if (type === '$ref' || def?.$ref) {
            // Render as interactive component if value is an href or object with $id
            let refUrl = null;
            if (typeof value === 'string' && value.startsWith('http')) {
                refUrl = value;
            } else if (value && typeof value === 'object' && value.$id) {
                refUrl = value.$id;
            }
            if (refUrl) {
                const refModel = (def.$ref || '').split('/').pop();
                const defs = schema?.$defs || {};
                let childTag = 'ntx-item';
                if (refModel && defs[refModel]?.ui?.renderer?.item) {
                    childTag = defs[refModel].ui.renderer.item;
                }
                const valueHtml = `<div class="ref-field" data-value="${key}"><${childTag} ref="${refUrl}" display="sm"${refModel ? ` data-model="${refModel}"` : ''}></${childTag}></div>`;
                html.push(showLabel ? wrapDisplayField(label, valueHtml) : valueHtml);
            } else {
                const valueHtml = `<div data-value="${key}">${formatRefDisplay(def, value)}</div>`;
                html.push(showLabel ? wrapDisplayField(label, valueHtml) : valueHtml);
            }
        } else if (type === 'selfref') {
            const valueHtml = `<div data-value="${key}">${value ? `[Parent: #${value}]` : '(top-level)'}</div>`;
            html.push(showLabel ? wrapDisplayField(label, valueHtml, { inline: true }) : valueHtml);
        } else if (type === 'array') {
            html.push(getListInput(ntt, key, mode));
        } else if (type === 'object') {
            const valueHtml = `<div class="object-display" data-value="${key}">${formatObjectDisplay(value)}</div>`;
            html.push(showLabel ? wrapDisplayField(label, valueHtml) : valueHtml);
        } else if (type === 'number' || type === 'integer') {
            const valueHtml = `<div class="number-display" data-value="${key}">${value}</div>`;
            html.push(showLabel ? wrapDisplayField(label, valueHtml, { inline: true, classes: 'field-row--numeric' }) : valueHtml);
        } else {
            const valueHtml = `<div class="text-display" data-value="${key}">${value}</div>`;
            html.push(showLabel ? wrapDisplayField(label, valueHtml, { inline: true }) : valueHtml);
        }
    }

    return html.join('');
}

function getListInput(ntt, key, mode = 'display') {
    const def = ntt.schema.properties?.[key];
    const listFieldSchema = {
        ...def,
        __fieldKey: key,
        ui: { ...(def?.ui || {}), widget: 'list' },
    };
    const { widget, config } = getWidgetForField(listFieldSchema);
    if (!widget) return '';

    const wrapper = document.createElement('div');
    const value = ntt.value?.[key] ?? [];
    const widgetEl = mode === 'edit'
        ? widget.edit(value, config, listFieldSchema, () => {}, ntt)
        : widget.display(value, config, listFieldSchema, ntt);
    wrapper.appendChild(widgetEl);
    return wrapper.innerHTML;
}

function getArrayInput(ntt, def, key, mode = 'display') {
    const label = def.title || key;
    const items = def.items || {};
    const type = def.type || 'array';
    const model = def.items?.$ref.split('/').pop()
    const href = `/${parent}/`
    let value = ntt.value?.[key] || [];
    let html = [];
    
    const addr = `/${ntt.addr}/${ntt.id}/${model}`;
    html.push(`<div class="array-field">`);
    html.push(`<ntx-list model="${model}" addr="${addr}" class="array-item" display="md"></ntx-list>`);
    
  
    if (!Array.isArray(value)) value = [];
  
    value.forEach((item, i) => {
      if (items?.$ref) {
        // Display reference summary
        html.push(`<div class="array-item">[Ref ${i + 1}]: ${item?.name || item?.id} \n ${JSON.stringify(item)}</div>`);
      } else {
        const itemType = items?.type || typeof item;
        if (mode === 'edit') {
          html.push(`
                <input type="${itemType}" id="${key}-${i}" data-key="${key}" data-index="${i}" data-type="${itemType}" value="${item}">
                `);
        } else {
        }
      }
    });
    html.push(`</div>`);
  
    return html.join('');
}


function resolveAnyOf(def) {
    // Check if one of the anyOf definitions is null
    const null_removed = def.anyOf.filter(item => item.type !== "null");
    
    if (null_removed && null_removed.length == 1) {
      return null_removed[0]; // Just return the first one for simplicity
    }
    else {
        throw new Error(`Multiple definitions found in anyOf for ${def.title || def.name || 'unknown'}. Please specify which one to use.`);
    }
  }

/**
 * Format a $ref field value for display. Resolves entity name from NTT registry.
 */
function formatRefDisplay(def, value) {
    if (!value) return '';
    // href string — resolve from NTT registry
    if (typeof value === 'string' && value.startsWith('http')) {
        const parts = value.split('/');
        const id = parts.pop();
        const tablename = parts.pop();
        // Try to find a registered DynamicClass by tablename
        const refModel = (def?.$ref || '').split('/').pop();
        const entity = refModel ? NTT.get(`${refModel}/${id}`) : null;
        if (entity?.value) {
            return entity.value.name || entity.value.title || `${refModel} #${id}`;
        }
        return `${refModel || tablename} #${id}`;
    }
    // Populated object
    if (typeof value === 'object') {
        return value.name || value.title || value.id || JSON.stringify(value);
    }
    return String(value);
}

/**
 * Format an object/dict field value for display as key-value pairs.
 */
function formatObjectDisplay(value) {
    if (!value || typeof value !== 'object') return value == null ? '{}' : String(value);
    const entries = Object.entries(value);
    if (entries.length === 0) return '{}';
    const MAX = 5;
    const shown = entries.slice(0, MAX).map(([k, v]) => {
        const display = typeof v === 'object' ? JSON.stringify(v) : String(v);
        return `<span class="kv-key">${k}</span>: <span class="kv-val">${display}</span>`;
    }).join(', ');
    const more = entries.length > MAX ? ` <span class="kv-more">(+${entries.length - MAX} more)</span>` : '';
    return shown + more;
}

/**
 * Return the formatted display string for a single field value.
 * Mirrors the display branch logic of getInput — used by update() patches.
 */
function formatDisplayValue(def, key, value) {
    const _wr = getWidgetForField(def);
    if (_wr.widget) {
        return _wr.widget.list(value, _wr.config, def);
    }
    const type = def?.type || 'string';
    if (def?.enum) return `<span class="enum-pill" data-status="${value}">${value}</span>`;
    if (type === '$ref' || def?.$ref) return formatRefDisplay(def, value);
    if (type === 'selfref') return value ? `[Parent: #${value}]` : '(top-level)';
    if (type === 'object') return formatObjectDisplay(value);
    return value ?? '';
}

/**
 * Validate all editable fields against schema constraints and widget rules.
 * Returns [{field, message}] — empty array means valid.
 */
function validateForm(ntt) {
    const schema = ntt.schema || {};
    const props = schema.properties || {};
    const required = new Set(schema.required || []);
    const value = ntt.value || {};
    const errors = [];

    for (const key of Object.keys(props)) {
        const def = props[key];
        // Skip hidden, protected, and readOnly fields
        if (def?.ui?.display === false) continue;
        if (def?.ui?.protected) continue;
        if (def?.readOnly) continue;
        // Skip object types (complex fields)
        if (def?.type === 'object') continue;

        const val = value[key];

        if (def?.type === 'array') {
            const arr = Array.isArray(val) ? val : [];
            if (required.has(key) && arr.length === 0) {
                errors.push({ field: key, message: `${def.title || key} is required` });
                continue;
            }
            continue;
        }

        // Required check
        if (required.has(key) && (val === undefined || val === null || val === '')) {
            errors.push({ field: key, message: `${def.title || key} is required` });
            continue;
        }

        // Skip further validation if empty and not required
        if (val === undefined || val === null || val === '') continue;

        // String constraints
        if (typeof val === 'string') {
            if (def.minLength != null && val.length < def.minLength) {
                errors.push({ field: key, message: `Must be at least ${def.minLength} characters` });
                continue;
            }
            if (def.maxLength != null && val.length > def.maxLength) {
                errors.push({ field: key, message: `Must be at most ${def.maxLength} characters` });
                continue;
            }
            if (def.pattern) {
                try {
                    if (!new RegExp(def.pattern).test(val)) {
                        errors.push({ field: key, message: `Does not match required pattern` });
                        continue;
                    }
                } catch { /* invalid regex — skip */ }
            }
        }

        // Number constraints
        if (typeof val === 'number') {
            if (def.minimum != null && val < def.minimum) {
                errors.push({ field: key, message: `Must be at least ${def.minimum}` });
                continue;
            }
            if (def.exclusiveMinimum != null && val <= def.exclusiveMinimum) {
                errors.push({ field: key, message: `Must be greater than ${def.exclusiveMinimum}` });
                continue;
            }
            if (def.maximum != null && val > def.maximum) {
                errors.push({ field: key, message: `Must be at most ${def.maximum}` });
                continue;
            }
            if (def.exclusiveMaximum != null && val >= def.exclusiveMaximum) {
                errors.push({ field: key, message: `Must be less than ${def.exclusiveMaximum}` });
                continue;
            }
        }

        // Widget validation
        const _wr = getWidgetForField(def);
        if (_wr.widget) {
            const widgetError = _wr.widget.validate(val, _wr.config, def);
            if (widgetError) {
                errors.push({ field: key, message: widgetError });
            }
        }
    }

    return errors;
}

export const Formidable = {
    validationAttrs,
    refInput,
    getForm,
    getInput,
    getListInput,
    getArrayInput,
    renderGroupedFields,
    formatDisplayValue,
    validateForm,
    /** Clear layout cache (call on login/logout to refresh permission-dependent layouts). */
    clearCache() { _layoutCache.clear(); }
}
