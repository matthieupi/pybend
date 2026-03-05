import { Widget } from './Widget.js';

/**
 * MarkdownWidget — Renders markdown content.
 *
 * Display: parsed HTML via marked.js (falls back to <pre> if not loaded).
 * Edit: <textarea> with optional live preview.
 * List: stripped plain text.
 */
export class MarkdownWidget extends Widget {

    display(value, config, schema) {
        if (!value) return document.createTextNode('');
        const div = document.createElement('div');
        div.className = 'widget-markdown';
        // Use marked.js if available, otherwise show as preformatted text
        if (typeof marked !== 'undefined' && marked.parse) {
            div.innerHTML = marked.parse(String(value));
        } else {
            const pre = document.createElement('pre');
            pre.textContent = value;
            div.appendChild(pre);
        }
        return div;
    }

    edit(value, config, schema, onChange) {
        const rows = config?.rows || 8;
        const container = document.createElement('div');
        container.className = 'widget-markdown-editor';

        const textarea = document.createElement('textarea');
        textarea.textContent = value ?? '';
        textarea.rows = rows;
        textarea.className = 'widget-markdown-input';
        textarea.placeholder = schema?.ui?.placeholder || 'Write markdown...';
        container.appendChild(textarea);

        // Live preview pane
        const preview = document.createElement('div');
        preview.className = 'widget-markdown-preview widget-markdown';
        container.appendChild(preview);

        const updatePreview = (text) => {
            if (typeof marked !== 'undefined' && marked.parse) {
                preview.innerHTML = marked.parse(text || '');
            } else {
                preview.textContent = text || '';
            }
        };

        updatePreview(value);
        textarea.addEventListener('input', () => {
            updatePreview(textarea.value);
            if (onChange) onChange(textarea.value);
        });

        return container;
    }

    list(value, config, schema) {
        if (!value) return '';
        // Strip markdown syntax for compact display
        return this.truncate(
            String(value).replace(/[#*_`~\[\]()>!|-]/g, '').replace(/\n+/g, ' ').trim(),
            80
        );
    }
}
