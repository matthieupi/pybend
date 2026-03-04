import { Widget } from './Widget.js';

/**
 * ReferenceWidget — Renders a reference to another model entity.
 *
 * Display: clickable link navigating to the referenced entity.
 * Edit: text input (future: autocomplete).
 * List: compact link.
 */
export class ReferenceWidget extends Widget {

    display(value, config, schema) {
        if (!value) return document.createTextNode('');
        const model = config?.model || '';
        const label = typeof value === 'object' ? (value.name || value.title || value.id) : value;
        const href = typeof value === 'object' && value.$id ? `#/${value.$id}` : `#/${model}/${value}`;
        return this.el('a', {
            href: href,
            class: 'widget-reference-link',
        }, [String(label)]);
    }

    edit(value, config, schema, onChange) {
        const input = document.createElement('input');
        input.type = 'text';
        input.setAttribute('value', value ?? '');
        input.placeholder = config?.model ? `${config.model} ID...` : 'Reference ID...';
        if (onChange) input.addEventListener('input', () => onChange(input.value));
        return input;
    }

    list(value, config, schema) {
        if (!value) return '';
        if (typeof value === 'object') return String(value.name || value.title || value.id || '');
        return String(value);
    }
}
