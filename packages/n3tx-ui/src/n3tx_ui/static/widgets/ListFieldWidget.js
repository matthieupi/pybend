import { Widget } from './Widget.js';
import '../components/ntx-list-field.js';

function encodeJson(value) {
  return encodeURIComponent(JSON.stringify(value ?? null));
}

export class ListFieldWidget extends Widget {
  #element(value, schema, mode = 'display', host = null) {
    const el = document.createElement('ntx-list-field');
    el.setAttribute('field', schema.__fieldKey || '');
    el.setAttribute('mode', mode);
    el.setAttribute('schema', encodeJson(schema));
    el.setAttribute('defs', encodeJson(host?.schema?.$defs || {}));
    el.setAttribute('value', encodeJson(value));
    if (schema?.ui?.visible_count !== undefined) {
      el.setAttribute('visible-count', schema.ui.visible_count);
    } else if (schema?.ui?.visibleCount !== undefined) {
      el.setAttribute('visible-count', schema.ui.visibleCount);
    }
    el.setAttribute('parent-model', host?.schema?.__name__ || '');
    el.setAttribute('parent-table', host?.schema?.__tablename__ || '');
    el.setAttribute('parent-id', host?.value?.id || '');
    return el;
  }

  display(value, config, schema, host) {
    return this.#element(value, schema, 'display', host);
  }

  edit(value, config, schema, onChange, host) {
    const el = this.#element(value, schema, 'edit', host);
    if (onChange) {
      el.addEventListener('field-change', (e) => onChange(e.detail.value));
    }
    return el;
  }

  list(value) {
    return Array.isArray(value) ? String(value.length) : '0';
  }
}
