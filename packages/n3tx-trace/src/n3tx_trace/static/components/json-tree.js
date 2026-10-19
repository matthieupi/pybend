/**
 * json-tree.js — Shared interactive JSON tree builder.
 *
 * Renders a collapsible JSON tree into a container element.
 * First depth level is expanded, subsequent levels collapsed (lazy-built).
 *
 * Usage:
 *   import { buildJsonTree, JSON_TREE_CSS } from './json-tree.js';
 *   buildJsonTree(containerEl, data, { expanded: true });
 */

/** CSS rules for the JSON tree — include in Shadow DOM styles. */
export const JSON_TREE_CSS = `
    .json-tree {
        padding: 0 0 4px 0;
        font-size: 11px;
        line-height: 1.5;
    }
    .json-node {
        padding-left: 16px;
    }
    .json-line {
        display: flex;
        align-items: baseline;
        padding: 0 12px 0 0;
        min-height: 18px;
        cursor: default;
    }
    .json-line.collapsible {
        cursor: pointer;
    }
    .json-line:hover {
        background: rgba(88, 166, 255, 0.05);
    }
    .json-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 14px;
        height: 14px;
        cursor: pointer;
        color: #6e7681;
        font-size: 10px;
        flex-shrink: 0;
        user-select: none;
        margin-right: 2px;
    }
    .json-toggle:hover { color: #e6edf3; }
    .json-toggle.leaf { visibility: hidden; }
    .json-key { color: #bc8cff; margin-right: 4px; }
    .json-colon { color: #6e7681; margin-right: 6px; }
    .json-string { color: #a5d6ff; }
    .json-number { color: #79c0ff; }
    .json-bool { color: #ff7b72; }
    .json-null { color: #6e7681; font-style: italic; }
    .json-bracket { color: #6e7681; }
    .json-preview { color: #484f58; font-style: italic; }
    .json-comma { color: #6e7681; }
`;

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function preview(value, isArray, count) {
    if (isArray) return `${count} item${count !== 1 ? 's' : ''}`;
    // Show id and name values inline when collapsed
    const highlights = [];
    if (value.id != null) highlights.push(`id: ${JSON.stringify(value.id)}`);
    if (value.name != null) highlights.push(`name: ${JSON.stringify(value.name)}`);
    if (highlights.length) {
        const rest = count - highlights.length;
        const suffix = rest > 0 ? `, \u2026${rest} more` : '';
        return highlights.join(', ') + suffix;
    }
    const keys = Object.keys(value).slice(0, 3);
    const suffix = count > 3 ? ', \u2026' : '';
    return keys.join(', ') + suffix;
}

function leafLine(key, valueHtml, isLast, pad) {
    const el = document.createElement('div');
    el.className = 'json-line';
    el.style.paddingLeft = pad + 'px';
    const keyHtml = key != null
        ? `<span class="json-key">"${escapeHtml(String(key))}"</span><span class="json-colon">:</span> `
        : '';
    const comma = isLast ? '' : '<span class="json-comma">,</span>';
    el.innerHTML = `<span class="json-toggle leaf"></span>${keyHtml}${valueHtml}${comma}`;
    return el;
}

function buildNode(container, value, depth, expanded, key, isLast) {
    const pad = depth * 16 + 12;

    if (value === null || value === undefined) {
        container.appendChild(leafLine(key, '<span class="json-null">null</span>', isLast, pad));
        return;
    }
    if (typeof value === 'string') {
        const html = value.length > 300
            ? `<span class="json-string">"${escapeHtml(value.slice(0, 300))}\u2026"</span>`
            : `<span class="json-string">"${escapeHtml(value)}"</span>`;
        container.appendChild(leafLine(key, html, isLast, pad));
        return;
    }
    if (typeof value === 'number') {
        container.appendChild(leafLine(key, `<span class="json-number">${value}</span>`, isLast, pad));
        return;
    }
    if (typeof value === 'boolean') {
        container.appendChild(leafLine(key, `<span class="json-bool">${value}</span>`, isLast, pad));
        return;
    }

    const isArray = Array.isArray(value);
    const entries = isArray ? value.map((v, i) => [i, v]) : Object.entries(value);
    const open = isArray ? '[' : '{';
    const close = isArray ? ']' : '}';
    const comma = isLast ? '' : '<span class="json-comma">,</span>';

    if (entries.length === 0) {
        container.appendChild(leafLine(key, `<span class="json-bracket">${open}${close}</span>`, isLast, pad));
        return;
    }

    // Collapsible node
    const line = document.createElement('div');
    line.className = 'json-line collapsible';
    line.style.paddingLeft = pad + 'px';

    const toggle = document.createElement('span');
    toggle.className = 'json-toggle';
    toggle.textContent = expanded ? '\u25BE' : '\u25B8';

    const keyHtml = key != null
        ? `<span class="json-key">"${escapeHtml(String(key))}"</span><span class="json-colon">:</span> `
        : '';

    const openSpan = document.createElement('span');
    openSpan.innerHTML = `${keyHtml}<span class="json-bracket">${open}</span>`;

    const previewSpan = document.createElement('span');
    previewSpan.className = 'json-preview';
    previewSpan.innerHTML = ` ${preview(value, isArray, entries.length)} `;

    const closeSpan = document.createElement('span');
    closeSpan.innerHTML = `<span class="json-bracket">${close}</span>${comma}`;

    const childContainer = document.createElement('div');
    childContainer.className = 'json-node';

    line.appendChild(toggle);
    line.appendChild(openSpan);

    if (expanded) {
        previewSpan.style.display = 'none';
        closeSpan.style.display = 'none';
        entries.forEach(([k, v], i) => {
            buildNode(childContainer, v, depth + 1, false, isArray ? null : k, i === entries.length - 1);
        });
    } else {
        childContainer.style.display = 'none';
    }

    line.appendChild(previewSpan);
    line.appendChild(closeSpan);

    const closeLine = document.createElement('div');
    closeLine.className = 'json-line';
    closeLine.style.paddingLeft = (pad + 16) + 'px';
    closeLine.innerHTML = `<span class="json-bracket">${close}</span>${comma}`;
    if (!expanded) closeLine.style.display = 'none';

    line.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = childContainer.style.display !== 'none';
        if (isOpen) {
            childContainer.style.display = 'none';
            closeLine.style.display = 'none';
            previewSpan.style.display = '';
            closeSpan.style.display = '';
            toggle.textContent = '\u25B8';
        } else {
            if (childContainer.children.length === 0) {
                entries.forEach(([k, v], i) => {
                    buildNode(childContainer, v, depth + 1, false, isArray ? null : k, i === entries.length - 1);
                });
            }
            childContainer.style.display = '';
            closeLine.style.display = '';
            previewSpan.style.display = 'none';
            closeSpan.style.display = 'none';
            toggle.textContent = '\u25BE';
        }
    });

    container.appendChild(line);
    container.appendChild(childContainer);
    container.appendChild(closeLine);
}

/**
 * Build an interactive JSON tree into a container element.
 * @param {HTMLElement} container
 * @param {*} data — JSON-serializable value
 * @param {object} [opts]
 * @param {boolean} [opts.expanded=true] — expand first level
 */
export function buildJsonTree(container, data, opts = {}) {
    const expanded = opts.expanded !== false;
    container.innerHTML = '';
    container.classList.add('json-tree');
    buildNode(container, data, 0, expanded, undefined, true);
}

/**
 * Check if data has displayable content.
 */
export function hasData(data) {
    if (data == null || data === '') return false;
    if (typeof data === 'object' && Object.keys(data).length === 0) return false;
    return true;
}
