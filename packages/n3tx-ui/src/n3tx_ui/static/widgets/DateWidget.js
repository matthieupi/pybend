import { Widget } from './Widget.js';

export class DateWidget extends Widget {

    display(value, config, schema) {
        if (!value) return document.createTextNode('');
        try {
            const d = new Date(value);
            if (isNaN(d.getTime())) return document.createTextNode(String(value));
            const formatted = d.toLocaleDateString(undefined, {
                year: 'numeric', month: 'short', day: 'numeric',
            });
            return this.el('time', { datetime: value, class: 'widget-date' }, [formatted]);
        } catch {
            return document.createTextNode(String(value));
        }
    }

    edit(value, config, schema, onChange) {
        const input = document.createElement('input');
        // Use datetime-local for datetime widget, date for date widget
        const widgetName = schema?.ui?.widget;
        input.type = widgetName === 'datetime' ? 'datetime-local' : 'date';
        // Normalize value for input (YYYY-MM-DD or YYYY-MM-DDTHH:mm)
        if (value) {
            try {
                const d = new Date(value);
                if (!isNaN(d.getTime())) {
                    const normalized = input.type === 'date'
                        ? d.toISOString().split('T')[0]
                        : d.toISOString().slice(0, 16);
                    input.setAttribute('value', normalized);
                } else {
                    input.setAttribute('value', value);
                }
            } catch {
                input.setAttribute('value', value);
            }
        }
        if (onChange) input.addEventListener('change', () => onChange(input.value));
        return input;
    }

    validate(value, config, schema) {
        if (!value) return null;
        const d = new Date(value);
        if (isNaN(d.getTime())) return 'Please enter a valid date';
        return null;
    }

    list(value, config, schema) {
        if (!value) return '';
        try {
            const d = new Date(value);
            if (isNaN(d.getTime())) return String(value);
            return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
        } catch {
            return String(value);
        }
    }
}
