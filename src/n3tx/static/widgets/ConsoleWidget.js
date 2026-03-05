import { Widget } from './Widget.js';

/**
 * ConsoleWidget — Renders console/terminal output with ANSI color support.
 *
 * Display: <pre> with ANSI colors via ansi_up.js (falls back to plain text).
 * Edit: readonly monospace <textarea>.
 * List: first line as inline <code>.
 */
export class ConsoleWidget extends Widget {

    display(value, config, schema) {
        if (!value) return document.createTextNode('');
        const pre = document.createElement('pre');
        pre.className = 'widget-console';
        // Use ansi_up if available for ANSI color rendering
        if (typeof AnsiUp !== 'undefined') {
            const ansi = new AnsiUp();
            pre.innerHTML = ansi.ansi_to_html(String(value));
        } else {
            pre.textContent = value;
        }
        return pre;
    }

    edit(value, config, schema, onChange) {
        const rows = config?.rows || 15;
        const textarea = document.createElement('textarea');
        textarea.textContent = value ?? '';
        textarea.rows = rows;
        textarea.readOnly = true;
        textarea.className = 'widget-console-textarea';
        return textarea;
    }

    list(value, config, schema) {
        if (!value) return '';
        // Show first line as inline code
        const firstLine = String(value).split('\n')[0];
        return this.truncate(firstLine, 60);
    }
}
