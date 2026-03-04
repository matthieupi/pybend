import { Widget } from './Widget.js';

/**
 * TextareaWidget — Renders multi-line text content.
 *
 * Migrated from existing inline textarea handling in form.js.
 * Display: block text div.
 * Edit: <textarea>.
 * List: truncated text.
 */
export class TextareaWidget extends Widget {

    display(value, config, schema) {
        if (!value) return document.createTextNode('');
        return this.el('div', { class: 'text-block' }, [String(value)]);
    }

    edit(value, config, schema, onChange) {
        const rows = config?.rows || 4;
        const textarea = document.createElement('textarea');
        textarea.textContent = value ?? '';
        textarea.rows = rows;
        if (schema?.ui?.placeholder) textarea.placeholder = schema.ui.placeholder;
        if (onChange) textarea.addEventListener('input', () => onChange(textarea.value));
        return textarea;
    }

    list(value, config, schema) {
        if (!value) return '';
        return this.truncate(String(value), 80);
    }
}
