/**
 * Widget — Base class for all field widgets.
 *
 * Provides default implementations for three render contexts:
 *   - display(value, config, schema) → DOM Node for detail views
 *   - edit(value, config, schema, onChange) → DOM Node for form editing
 *   - list(value, config, schema) → String for table/list cells
 *
 * Built-in widgets override only what differs. App developers extend
 * this class to create custom widgets.
 */
export class Widget {

    /**
     * Render field value for detail/display context.
     * @param {*} value - Field value
     * @param {Object} config - Widget config from schema (ui.config)
     * @param {Object} schema - Field schema definition
     * @returns {Node} DOM node
     */
    display(value, config, schema) {
        return document.createTextNode(value ?? '');
    }

    /**
     * Render field value for edit context.
     * @param {*} value - Current field value
     * @param {Object} config - Widget config from schema
     * @param {Object} schema - Field schema definition
     * @param {Function} onChange - Callback: onChange(newValue)
     * @returns {Node} DOM node (input element)
     */
    edit(value, config, schema, onChange) {
        const input = document.createElement('input');
        input.type = 'text';
        input.setAttribute('value', value ?? '');
        if (onChange) input.addEventListener('input', () => onChange(input.value));
        return input;
    }

    /**
     * Render field value for list/table cell context.
     * @param {*} value - Field value
     * @param {Object} config - Widget config from schema
     * @param {Object} schema - Field schema definition
     * @returns {string} Plain text or simple HTML string
     */
    list(value, config, schema) {
        return String(value ?? '');
    }

    /**
     * Validate a field value. Returns null if valid, or an error message string.
     * Widget subclasses override for type-specific validation.
     * @param {*} value - Field value
     * @param {Object} config - Widget config from schema (ui.config)
     * @param {Object} schema - Field schema definition
     * @returns {string|null} Error message or null
     */
    validate(value, config, schema) {
        return null;
    }

    // ── Shared utilities ────────────────────────────────────────────

    /** Truncate string to maxLen with ellipsis. */
    truncate(str, maxLen = 80) {
        if (!str || str.length <= maxLen) return str || '';
        return str.substring(0, maxLen) + '\u2026';
    }

    /** Escape HTML entities. */
    escape(html) {
        const div = document.createElement('div');
        div.textContent = html;
        return div.innerHTML;
    }

    /**
     * Create a DOM element with attributes and children.
     * @param {string} tag - Tag name
     * @param {Object} attrs - Attributes (class, onclick, href, etc.)
     * @param {Array} children - Child nodes or strings
     * @returns {HTMLElement}
     */
    el(tag, attrs = {}, children = []) {
        const el = document.createElement(tag);
        for (const [k, v] of Object.entries(attrs)) {
            if (k === 'class') el.className = v;
            else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
            else el.setAttribute(k, v);
        }
        for (const c of children) {
            el.append(typeof c === 'string' ? document.createTextNode(c) : c);
        }
        return el;
    }
}
