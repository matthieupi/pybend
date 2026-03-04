import { Widget } from './Widget.js';

export class EmailWidget extends Widget {

    display(value, config, schema) {
        if (!value) return document.createTextNode('');
        return this.el('a', {
            href: `mailto:${value}`,
            class: 'widget-email-link',
        }, [String(value)]);
    }

    edit(value, config, schema, onChange) {
        const input = document.createElement('input');
        input.type = 'email';
        input.setAttribute('value', value ?? '');
        input.placeholder = schema?.ui?.placeholder || 'user@example.com';
        if (onChange) input.addEventListener('input', () => onChange(input.value));
        return input;
    }

    validate(value, config, schema) {
        if (!value) return null;
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'Please enter a valid email';
        return null;
    }

    list(value, config, schema) {
        return String(value ?? '');
    }
}
