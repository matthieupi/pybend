/**
 * JsonTree — Collapsible, syntax-highlighted JSON renderer.
 *
 * Extracted from ntx-logs.js for reuse across components.
 *
 * Usage:
 *   import { renderJson, jsonTreeCSS, initJsonToggle } from '../widgets/JsonTree.js';
 *
 *   el.innerHTML = renderJson(someObject);
 *   initJsonToggle(this.shadowRoot);   // wire collapsible clicks
 *
 * The CSS string should be included in the component's <style> block.
 */

const MAX_DEPTH = 8;

function esc(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * Render a value as a collapsible, syntax-highlighted JSON tree (HTML string).
 *
 * @param {*} value - Any JSON-serializable value, or a JSON string
 * @param {number} [depth=0] - Current nesting depth (used for auto-collapse)
 * @returns {string} HTML string
 */
export function renderJson(value, depth = 0) {
    // Auto-parse JSON strings
    if (typeof value === 'string') {
        const trimmed = value.trim();
        if ((trimmed.startsWith('{') || trimmed.startsWith('[')) && trimmed.length > 2) {
            try { value = JSON.parse(trimmed); } catch { /* render as string */ }
        }
    }

    if (depth > MAX_DEPTH) return '<span class="jt-str">"[max depth]"</span>';
    if (value === null || value === undefined) return '<span class="jt-null">null</span>';
    if (typeof value === 'boolean') return `<span class="jt-bool">${value}</span>`;
    if (typeof value === 'number') return `<span class="jt-num">${value}</span>`;
    if (typeof value === 'string') return `<span class="jt-str">"${esc(value)}"</span>`;

    if (Array.isArray(value)) {
        if (value.length === 0) return '<span class="jt-bracket">[]</span>';
        const items = value.map(v =>
            `<div class="jt-item">${renderJson(v, depth + 1)}</div>`
        ).join('');
        const collapsed = depth > 0 ? ' collapsed' : '';
        return `<span class="jt-node${collapsed}"><span class="jt-toggle jt-bracket">[${value.length}]</span><div class="jt-children">${items}</div></span>`;
    }

    if (typeof value === 'object') {
        const keys = Object.keys(value);
        if (keys.length === 0) return '<span class="jt-bracket">{}</span>';
        const items = keys.map(k =>
            `<div class="jt-item"><span class="jt-key">${esc(k)}</span>: ${renderJson(value[k], depth + 1)}</div>`
        ).join('');
        const preview = keys.slice(0, 3).join(', ') + (keys.length > 3 ? ', \u2026' : '');
        const collapsed = depth > 0 ? ' collapsed' : '';
        return `<span class="jt-node${collapsed}"><span class="jt-toggle jt-bracket">{${esc(preview)}}</span><div class="jt-children">${items}</div></span>`;
    }

    return esc(String(value));
}

/**
 * Wire click-to-toggle on collapsible JSON nodes within a root element.
 * Call once per shadow root (uses event delegation).
 *
 * @param {Element} root - Element to listen on (e.g., shadowRoot or container)
 */
export function initJsonToggle(root) {
    root.addEventListener('click', (e) => {
        const toggle = e.target.closest('.jt-toggle');
        if (!toggle) return;
        const node = toggle.closest('.jt-node');
        if (node) node.classList.toggle('collapsed');
    });
}

/**
 * CSS for the JSON tree. Include in your component's <style> block.
 */
export const jsonTreeCSS = `
    .jt-node { display: inline; }
    .jt-children {
        display: block;
        padding-left: 1rem;
        border-left: 1px solid var(--ntx-border-default, rgba(255,255,255,0.08));
        margin-left: 2px;
    }
    .jt-node.collapsed > .jt-children { display: none; }
    .jt-toggle { cursor: pointer; user-select: none; }
    .jt-toggle:hover { opacity: 0.8; }
    .jt-item { line-height: 1.5; }
    .jt-bracket { color: var(--ntx-color-text-subtle, #555e78); }
    .jt-key { color: var(--ntx-color-accent-text, #5eeadf); }
    .jt-str { color: #f1fa8c; }
    .jt-num { color: #bd93f9; }
    .jt-bool { color: #ff79c6; }
    .jt-null { color: var(--ntx-color-text-subtle, #555e78); font-style: italic; }
`;
