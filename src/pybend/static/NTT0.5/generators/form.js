
  function refInput(ref) {
    const ptt = PTT.get(ref);
    if (!ptt) {
      console.warn(`No PTT found for reference: ${ref}`);
      return `<input type="text" placeholder="Invalid reference">`;
    }
    // Assuming ptt has a schema with properties
    const schema = ptt.schema || {};
    return getForm(schema);
    
  }
  
  
  function getForm(ntt, mode="display") {
    const schema = ntt.schema;
    const fields = schema.properties || {};
    const model = ntt.name
    return Object.keys(fields).map(key => {
      const def = fields[key];
      const value = ntt.value?.[key] ?? '';
      return getInput(model, mode, def, key, value);
    }).join('');
  }
 
  
  
function getInput(model, mode, def, key, value) {
  const label = def.title || key;
  const type = def.type || 'string';
  let html = [];
  
  if (key !== 'name' && key !== 'id')
    html.push(`<label class="${model} ${model}-form-item">${label}</label>`);
  
  if (mode === 'edit') {
    if (type === 'boolean') {
      html.push(`<input type="checkbox" id="${key}" data-key="${key}" data-type="${type}"  ${value ? 'checked' : ''}>`);
    } else if (type === 'string') {
      html.push(`<input type="text" id="${key}" data-key="${key}" data-type="${type}" value="${value}">`);
    } else if (type === 'text') {
      html.push(`<textarea id="${key}" data-key="${key}" data-type="${type}">${value}</textarea>`);
    } else if (type === 'number') {
      html.push(`<input type="number" id="${key}" data-key="${key}" data-type="${type}" value="${value}">`);
    } else if (type === 'array') {
      html.push(getArrayInput(def, key, value));
    } else {
      html.push(`<input type="${type}" data-key="${key}" data-type="${type}" value="${value}" id="${key}">`);
    }
  } else {
    if (type === '$ref' || def?.$ref) {
      html.push(`<div>[Reference: ${value?.name || value?.id || JSON.stringify(value)}]</div>`);
    } else if (type === 'array') {
      html.push(getArrayInput(def, key, value));
    } else {
      html.push(`<div>${value}</div>`);
    }
  }
  
  return html.join('');
}

function getArrayInput(def, key, value) {
    const label = def.title || key;
    const items = def.items || {};
    const type = def.type || 'array';
    let html = [];
  
    if (!Array.isArray(value)) value = [];
  
    html.push(`<div class="array-field">`);
    value.forEach((item, i) => {
      if (items?.$ref) {
        // Display reference summary
        html.push(`<div class="array-item">[Ref ${i + 1}]: ${item?.name || item?.id} \n ${JSON.stringify(item)}</div>`);
      } else {
        const itemType = items?.type || typeof item;
        if (this.mode === 'edit') {
          html.push(`
                <input type="${itemType}" id="${key}-${i}" data-key="${key}" data-index="${i}" data-type="${itemType}" value="${item}">
                `);
        } else {
          html.push(`<div class="array-item">${item}</div>`);
        }
      }
    });
    html.push(`</div>`);
  
    return html.join('');
}

export const Formidable = {
    refInput,
    getForm,
    getInput,
    getArrayInput
}