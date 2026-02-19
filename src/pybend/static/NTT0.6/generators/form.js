
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
  
  
  function getForm(ntt, mode="display") {
      const schema = ntt.schema;
      const fields = schema.properties || {};
      const model = ntt.value.name
      // We want to put the name and desc first, and use h2 for name and h4 for desc
      let $header = getHeader(ntt, mode);
      let $fields = Object.keys(fields).map(key => {
          if (['name', 'id', 'description'].includes(key)) return '';
          const def = fields[key];
          const value = ntt.value?.[key] ?? '';
          return getInput(ntt, key, mode);
      }).join('');
      return $header.concat($fields).join('');
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
  
function getInput(ntt, key, mode = 'display') {
    const schema = ntt.schema;
    const def = schema.properties?.[key]
    const model = ntt.name
    const label = def.title || key;
    const value = ntt.value?.[key] ?? '';
    let html = [];
    
    // Handle special cases when the type is a complex type like anyOf : [{...}, {...}, ...]
    if (def.anyOf) {
        Object.assign(def, resolveAnyOf(def));
    }
    
    const type = def.type || 'string';
    
    
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
            html.push(getListInput(ntt, key, mode));
        } else {
            html.push(`<input type="${type}" data-key="${key}" data-type="${type}" value="${value}" id="${key}">`);
        }
    } else {
        if (type === '$ref' || def?.$ref) {
            html.push(`<div>[Reference: ${value?.name || value?.id || JSON.stringify(value)}]</div>`);
        } else if (type === 'array') {
            html.push(getListInput(ntt, key, mode));
        } else {
            html.push(`<div>${value}</div>`);
        }
    }
    
    return html.join('');
}

function getListInput(ntt, key, mode = 'display') {
    const def = ntt.schema.properties?.[key];
    const items = def.items || {};
    const value = ntt.value?.[key] || [];
    let html = [];

    // Extract model name from $ref in items schema
    let modelName = null;
    if (items.$ref) {
        modelName = items.$ref.split('/').pop();
    } else if (items.anyOf) {
        const refEntry = items.anyOf.find(a => a.$ref);
        if (refEntry) modelName = refEntry.$ref.split('/').pop();
    }

    html.push(`<div class="list-field">`);
    html.push(`<label>${def.title || key}</label>`);

    if (Array.isArray(value)) {
        value.forEach(item => {
            if (typeof item === 'string') {
                // href string — render as ntt-item
                html.push(`<ntt-item ref="${item}"${modelName ? ` data-model="${modelName}"` : ''}></ntt-item>`);
            }
        });
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
    html.push(`<ntt-list model="${model}" addr="${addr}" class="array-item"></ntt-list>`);
    
  
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
    refInput,
    getForm,
    getInput,
    getListInput,
    getArrayInput
}