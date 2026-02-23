import { permissions } from '../utils/Permissions.js';

  function refInput(ref) {
    const ptt = NTT.get(ref);
    if (!ptt) {
      console.error(`No NTT found for reference: ${ref}`);
      return `<input type="text" placeholder="Invalid reference">`;
    }
    // Assuming ptt has a schema with properties
    const schema = ptt.schema || {};
    return getForm(schema);
    
  }
  
  
  function getForm(ntt, mode="display", attachedMethods = {}) {
      const schema = ntt.schema;
      const fields = schema.properties || {};
      const ui = schema.ui || {};
      const headerFields = ['name', 'id', 'description'];

      // Determine field order: schema.ui.field_order > Object.keys fallback
      const fieldOrder = ui.field_order
          ? ui.field_order.filter(k => k in fields)
          : Object.keys(fields);
      // Add any fields not in field_order (safety net)
      for (const k of Object.keys(fields)) {
          if (!fieldOrder.includes(k)) fieldOrder.push(k);
      }

      let $header = getHeader(ntt, mode);

      // Filter renderable fields (exclude header fields, ui.display=false, and access-denied)
      const renderableFields = fieldOrder.filter(key => {
          if (headerFields.includes(key)) return false;
          const def = fields[key];
          if (def?.ui?.display === false) return false;
          if (mode === 'edit' && def?.ui?.protected) return false;
          if (!permissions.canView(def)) return false;
          return true;
      });

      // Render with groups if schema.ui.groups is defined
      let $fields;
      if (ui.groups && typeof ui.groups === 'object') {
          $fields = renderGroupedFields(ntt, renderableFields, ui.groups, mode, attachedMethods);
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
      return `<ntt-method
          model="${ntt.schema.__name__}"
          uuid="${ntt.value?.id || ''}"
          method="${methodName}"
          layout="${ui.layout || 'fieldset'}"
          placeholder="${ui.placeholder || ''}"
          button-label="${ui.button_label || 'Run'}"
          widget="${ui.widget || ''}"
          label="${methodDef.title || methodName}">
      </ntt-method>`;
  }

  function renderGroupedFields(ntt, renderableFields, groups, mode, attachedMethods = {}) {
      const grouped = new Set();
      const html = [];

      for (const [groupName, groupFields] of Object.entries(groups)) {
          const fieldsInGroup = groupFields.filter(k => renderableFields.includes(k));
          if (fieldsInGroup.length === 0) continue;
          fieldsInGroup.forEach(k => grouped.add(k));
          html.push(`<fieldset class="ntt-group ntt-group-${groupName}">`);
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
      ntt = ntt.value || {};
      const name = ntt.title || ntt.name || schema.name || 'Unnamed';
      const desc = ntt.description || '';
    
      let headerHtml = [];
    
      if (mode === 'edit') {
          headerHtml.push(`<input style="font-size: 1.5rem" type="text" id="name" data-key="name" data-type="string" value="${name}">`);
          if (desc)
              headerHtml.push(`<textarea id="description" data-key="description" data-type="text">${desc}</textarea>`);
        
      } else {
          headerHtml.push(`<h2 class="${schema.name}">${name}</h2>`);
          if (desc) {
              headerHtml.push(`<h4>${desc}</h4>`);
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

function getInput(ntt, key, mode = 'display') {
    const schema = ntt.schema;
    const def = schema.properties?.[key]
    const model = ntt.name
    const label = def.title || key;
    const value = ntt.value?.[key] ?? '';
    const widget = def.ui?.widget;  // Widget hint from schema (takes priority)
    let html = [];

    // Handle special cases when the type is a complex type like anyOf : [{...}, {...}, ...]
    if (def.anyOf) {
        Object.assign(def, resolveAnyOf(def));
    }

    // Protected fields are always display-only (backend-owned)
    const effectiveMode = (mode === 'edit' && (def.ui?.protected || !permissions.canEdit(def))) ? 'display' : mode;

    const type = def.type || 'string';

    if (key !== 'name' && key !== 'id' && type !== 'array')
        html.push(`<label class="${model} ${model}-form-item">${label}</label>`);

    if (effectiveMode === 'edit') {
        // Build HTML5 validation attributes from schema constraints
        const v = validationAttrs(def, schema.required?.includes(key));

        // Widget hint takes priority over type for edit rendering
        if (widget === 'textarea' || type === 'text') {
            html.push(`<textarea id="${key}" data-key="${key}" data-type="string"${v}>${value}</textarea>`);
        } else if (widget === 'currency') {
            html.push(`<div class="currency-input"><span class="currency-symbol">$</span><input type="number" step="0.01" id="${key}" data-key="${key}" data-type="number" value="${value}"${v}></div>`);
        } else if (type === 'boolean') {
            html.push(`<input type="checkbox" id="${key}" data-key="${key}" data-type="${type}" ${value ? 'checked' : ''}${v}>`);
        } else if (type === 'string') {
            html.push(`<input type="text" id="${key}" data-key="${key}" data-type="${type}" value="${value}"${v}>`);
        } else if (type === 'number') {
            html.push(`<input type="number" id="${key}" data-key="${key}" data-type="${type}" value="${value}"${v}>`);
        } else if (type === 'selfref') {
            html.push(`<input type="number" id="${key}" data-key="${key}" data-type="selfref" value="${value || ''}" placeholder="Parent ID (optional)"${v}>`);
        } else if (type === 'array') {
            html.push(getListInput(ntt, key, mode));
        } else {
            html.push(`<input type="${type}" data-key="${key}" data-type="${type}" value="${value}" id="${key}"${v}>`);
        }
    } else {
        // Widget hint takes priority for display rendering too
        if (widget === 'currency') {
            const formatted = typeof value === 'number' ? `$${value.toFixed(2)}` : value;
            html.push(`<div class="currency-display">${formatted}</div>`);
        } else if (widget === 'textarea') {
            html.push(`<div class="text-block">${value}</div>`);
        } else if (type === '$ref' || def?.$ref) {
            html.push(`<div>[Reference: ${value?.name || value?.id || JSON.stringify(value)}]</div>`);
        } else if (type === 'selfref') {
            html.push(`<div>${value ? `[Parent: #${value}]` : '(top-level)'}</div>`);
        } else if (type === 'array') {
            html.push(getListInput(ntt, key, mode));
        } else {
            html.push(`<div>${value}</div>`);
        }
    }

    return html.join('');
}

function getListInput(ntt, key, mode = 'display') {
    const VISIBLE_COUNT = 2;
    const def = ntt.schema.properties?.[key];
    const items = def.items || {};
    const value = ntt.value?.[key] || [];
    const defs = ntt.schema?.$defs || {};
    let html = [];

    // Extract model name from $ref in items schema
    let modelName = null;
    if (items.$ref) {
        modelName = items.$ref.split('/').pop();
    } else if (items.anyOf) {
        const refEntry = items.anyOf.find(a => a.$ref);
        if (refEntry) modelName = refEntry.$ref.split('/').pop();
    }

    // Resolve child component tag from referenced model's renderer hints
    let childTag = 'ntt-item';
    if (modelName && defs[modelName]?.ui?.renderer?.item) {
        childTag = defs[modelName].ui.renderer.item;
    }

    const count = Array.isArray(value) ? value.filter(v => typeof v === 'string').length : 0;

    html.push(`<div class="list-field" data-model="${modelName || ''}">`);
    html.push(`<div class="list-field-header">`);
    html.push(`<span class="list-field-label">${def.title || modelName || key}</span>`);
    html.push(`<span class="list-field-count">${count}</span>`);
    html.push(`</div>`);

    if (Array.isArray(value)) {
        value.forEach((item, i) => {
            if (typeof item === 'string') {
                if (i === VISIBLE_COUNT) {
                    html.push(`<div class="nested-collapsed">`);
                }
                html.push(`<${childTag} ref="${item}" display="sm"${modelName ? ` data-model="${modelName}"` : ''}></${childTag}>`);
            }
        });
        if (count > VISIBLE_COUNT) {
            html.push(`</div>`);
            html.push(`<button type="button" class="show-more-btn">Show ${count - VISIBLE_COUNT} more</button>`);
        }
    }

    html.push(`</div>`);
    return html.join('');
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
    html.push(`<ntt-list model="${model}" addr="${addr}" class="array-item" display="md"></ntt-list>`);
    
  
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

export const Formidable = {
    validationAttrs,
    refInput,
    getForm,
    getInput,
    getListInput,
    getArrayInput,
    renderGroupedFields
}