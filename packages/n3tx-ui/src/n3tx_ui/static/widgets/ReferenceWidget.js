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
        const model = config?.model || schema?.['x-ref'] || '';
        const href = typeof value === 'object' ? value.$id : String(value);
        const id = this.#id(href);
        const label = typeof value === 'object'
            ? (value.name || value.title || value.id || href)
            : (model && id ? `${model} #${id}` : href);
        return this.el('a', {
            href: href,
            class: 'widget-reference-link',
            'data-ref-model': model,
        }, [String(label)]);
    }

    edit(value, config, schema, onChange) {
        const input = document.createElement('input');
        input.type = 'url';
        input.setAttribute('value', value ?? '');
        const model = config?.model || schema?.['x-ref'];
        input.placeholder = model ? `${model} URL...` : 'Entity URL...';
        if (onChange) input.addEventListener('input', () => onChange(input.value));
        return input;
    }

    list(value, config, schema) {
        if (!value) return '';
        if (typeof value === 'object') return String(value.name || value.title || value.id || '');
        return String(value);
    }

    #id(value) {
        if (!value) return '';
        try {
            const parts = new URL(value).pathname.split('/').filter(Boolean);
            return decodeURIComponent(parts.at(-1) || '');
        } catch {
            return '';
        }
    }
}
