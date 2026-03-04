import { Widget } from './Widget.js';

export class UrlWidget extends Widget {

    display(value, config, schema) {
        if (!value) return document.createTextNode('');
        const url = String(value);
        return this.el('a', {
            href: url,
            target: '_blank',
            rel: 'noopener noreferrer',
            class: 'widget-url-link',
        }, [this.truncate(url, 60)]);
    }

    edit(value, config, schema, onChange) {
        const input = document.createElement('input');
        input.type = 'url';
        input.setAttribute('value', value ?? '');
        input.placeholder = schema?.ui?.placeholder || 'https://...';
        if (onChange) input.addEventListener('input', () => onChange(input.value));
        return input;
    }

    validate(value, config, schema) {
        if (!value) return null;
        try { new URL(value); return null; }
        catch { return 'Please enter a valid URL'; }
    }

    list(value, config, schema) {
        if (!value) return '';
        return this.truncate(String(value), 40);
    }
}
