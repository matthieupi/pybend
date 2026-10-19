/**
 * tx-detail.js — Request chain drill-down panel.
 *
 * Shows all TXs with the same trace_id, ordered by timestamp.
 * Displays time offset from root TX, badges, and total duration.
 * Each entry is clickable to expand an inline JSON data viewer.
 */

import { buildJsonTree, hasData, JSON_TREE_CSS } from './json-tree.js';

class TxDetail extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
    }

    connectedCallback() {
        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: none;
                    flex-direction: column;
                    background: #1c2128;
                    overflow: hidden;
                    min-height: 80px;
                    font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
                    font-size: 12px;
                    color: #e6edf3;
                }
                :host(.visible) { display: flex; }
                .header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 8px 12px;
                    border-bottom: 1px solid #30363d;
                    position: sticky;
                    top: 0;
                    background: #1c2128;
                    z-index: 1;
                }
                .header h4 {
                    font-size: 12px;
                    font-weight: 600;
                    color: #58a6ff;
                }
                .header-actions {
                    display: flex;
                    align-items: center;
                    gap: 4px;
                }
                .header-btn {
                    background: none;
                    border: none;
                    color: #8b949e;
                    cursor: pointer;
                    font-size: 13px;
                    padding: 2px 5px;
                    line-height: 1;
                    border-radius: 3px;
                }
                .header-btn:hover { color: #e6edf3; background: rgba(88, 166, 255, 0.1); }
                .header-btn.copied { color: #3fb950; }
                .close-btn {
                    background: none;
                    border: none;
                    color: #8b949e;
                    cursor: pointer;
                    font-size: 16px;
                    padding: 0 4px;
                    line-height: 1;
                }
                .close-btn:hover { color: #e6edf3; }
                .chain-list { flex: 1; overflow-y: auto; }
                .chain-item {
                    border-bottom: 1px solid rgba(48, 54, 61, 0.5);
                }
                .chain-entry {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 4px 12px;
                    font-size: 11px;
                    cursor: pointer;
                    transition: background 0.1s;
                }
                .chain-entry:hover {
                    background: rgba(88, 166, 255, 0.08);
                }
                .chain-entry.expanded {
                    background: rgba(88, 166, 255, 0.06);
                    border-bottom: 1px solid rgba(48, 54, 61, 0.3);
                }
                .offset {
                    color: #6e7681;
                    min-width: 55px;
                    text-align: right;
                }
                .chain-name { font-weight: 500; }
                .chain-name.error { color: #f85149; }
                .chain-name.stream { color: #39d4c5; }
                .chain-route {
                    color: #8b949e;
                    flex: 1;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .arrow { color: #6e7681; margin: 0 2px; }
                .badge {
                    font-size: 9px;
                    padding: 1px 4px;
                    border-radius: 3px;
                    text-transform: uppercase;
                    font-weight: 600;
                }
                .badge-root { background: rgba(88, 166, 255, 0.2); color: #58a6ff; }
                .badge-response { background: rgba(63, 185, 80, 0.2); color: #3fb950; }
                .badge-error { background: rgba(248, 81, 73, 0.2); color: #f85149; }
                .badge-stream { background: rgba(57, 212, 197, 0.2); color: #39d4c5; }
                .copy-entry-btn {
                    background: none;
                    border: none;
                    color: #30363d;
                    cursor: pointer;
                    font-size: 11px;
                    padding: 0 3px;
                    line-height: 1;
                    flex-shrink: 0;
                    transition: color 0.15s;
                }
                .copy-entry-btn:hover { color: #8b949e; }
                .copy-entry-btn.copied { color: #3fb950; }
                .data-toggle {
                    color: #6e7681;
                    font-size: 10px;
                    flex-shrink: 0;
                    margin-left: 2px;
                }
                .chain-data {
                    display: none;
                    background: rgba(13, 17, 23, 0.5);
                    border-bottom: 1px solid rgba(48, 54, 61, 0.3);
                    padding: 2px 0;
                }
                .chain-data.open { display: block; }
                .stream-chunk {
                    padding-left: 24px;
                    font-size: 10px;
                    opacity: 0.8;
                }
                .stream-chunk:hover { opacity: 1; }
                .sub-group {
                    border-bottom: 1px solid rgba(48, 54, 61, 0.2);
                }
                .sub-group-header {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 3px 12px 3px 20px;
                    font-size: 10px;
                    cursor: pointer;
                    transition: background 0.1s;
                }
                .sub-group-header:hover {
                    background: rgba(88, 166, 255, 0.05);
                }
                .sub-group-name {
                    font-weight: 600;
                    text-transform: uppercase;
                }
                .sub-group-name.thinking { color: #d2a8ff; }
                .sub-group-name.text { color: #39d4c5; }
                .sub-group-name.tool_call { color: #d29922; }
                .sub-group-name.tool_result { color: #d29922; }
                .sub-group-name.done { color: #3fb950; }
                .sub-group-name.error { color: #f85149; }
                .sub-group-preview {
                    color: #6e7681;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    flex: 1;
                    font-style: italic;
                }
                .accumulated-text {
                    padding: 6px 12px 6px 32px;
                    font-size: 11px;
                    color: #c9d1d9;
                    white-space: pre-wrap;
                    word-break: break-word;
                    max-height: 300px;
                    overflow-y: auto;
                    border-left: 2px solid rgba(57, 212, 197, 0.3);
                    margin-left: 20px;
                    line-height: 1.5;
                }
                .no-data {
                    padding: 4px 12px;
                    font-size: 10px;
                    color: #484f58;
                    font-style: italic;
                }
                .duration {
                    padding: 6px 12px;
                    font-size: 11px;
                    color: #8b949e;
                    border-top: 1px solid #30363d;
                    position: sticky;
                    bottom: 0;
                    background: #1c2128;
                }
                ${JSON_TREE_CSS}
            </style>
            <div class="header">
                <h4>Request Chain</h4>
                <div class="header-actions">
                    <button class="header-btn copy-chain-btn" title="Copy chain as JSON">&#x2398;</button>
                    <button class="close-btn">x</button>
                </div>
            </div>
            <div class="chain-list"></div>
            <div class="duration"></div>
        `;

        this._listEl = this.shadowRoot.querySelector('.chain-list');
        this._durationEl = this.shadowRoot.querySelector('.duration');

        this.shadowRoot.querySelector('.close-btn').addEventListener('click', () => {
            this.hide();
            this.dispatchEvent(new CustomEvent('detail-close', { bubbles: true }));
        });

        this.shadowRoot.querySelector('.copy-chain-btn').addEventListener('click', () => {
            this._copyToClipboard(this._entries, this.shadowRoot.querySelector('.copy-chain-btn'));
        });
    }

    _copyToClipboard(data, btn) {
        const json = JSON.stringify(data, null, 2);
        navigator.clipboard.writeText(json).then(() => {
            const orig = btn.innerHTML;
            btn.textContent = '\u2713';
            btn.classList.add('copied');
            setTimeout(() => { btn.innerHTML = orig; btn.classList.remove('copied'); }, 1500);
        });
    }

    show(entries) {
        if (!entries.length) {
            this.hide();
            return;
        }

        this.classList.add('visible');
        this._listEl.innerHTML = '';

        // Sort by timestamp and store for copy
        const sorted = [...entries].sort((a, b) => a.timestamp - b.timestamp);
        this._entries = sorted;
        const rootTs = sorted[0].timestamp;

        // Group consecutive stream entries, render everything else individually
        let i = 0;
        while (i < sorted.length) {
            const entry = sorted[i];

            if (entry.is_stream) {
                // Collect consecutive stream entries
                const start = i;
                while (i < sorted.length && sorted[i].is_stream) i++;
                const group = sorted.slice(start, i);

                if (group.length > 1) {
                    this._renderStreamGroup(group, rootTs);
                } else {
                    this._renderChainEntry(group[0], rootTs);
                }
            } else {
                this._renderChainEntry(entry, rootTs);
                i++;
            }
        }

        // Duration
        const duration = ((sorted[sorted.length - 1].timestamp - rootTs) * 1000).toFixed(1);
        this._durationEl.textContent = `Chain: ${sorted.length} TXs, ${duration}ms total`;
    }

    _renderChainEntry(entry, rootTs) {
        const item = document.createElement('div');
        item.className = 'chain-item';

        const el = document.createElement('div');
        el.className = 'chain-entry';

        const offset = ((entry.timestamp - rootTs) * 1000).toFixed(1);

        let nameClass = 'chain-name';
        if (entry.is_error || entry.name === 'ERROR') nameClass += ' error';
        else if (entry.is_stream) nameClass += ' stream';

        // Badges
        let badges = '';
        if (entry.timestamp === rootTs && !entry.req) {
            badges += '<span class="badge badge-root">root</span> ';
        }
        if (entry.req && !entry.is_error && !entry.is_stream) {
            badges += '<span class="badge badge-response">resp</span> ';
        }
        if (entry.is_error) {
            badges += '<span class="badge badge-error">err</span> ';
        }
        if (entry.is_stream) {
            badges += `<span class="badge badge-stream">stream${entry.seq ? ' #' + entry.seq : ''}</span> `;
        }

        const hasEntryData = hasData(entry.data);
        const dataToggle = hasEntryData
            ? '<span class="data-toggle">\u25B8</span>'
            : '';

        el.innerHTML = `
            ${dataToggle}
            <span class="offset">+${offset}ms</span>
            <span class="${nameClass}">${entry.name}</span>
            <span class="chain-route">
                ${entry.source}<span class="arrow"> \u2192 </span>${entry.target}
            </span>
            ${badges}
            <button class="copy-entry-btn" title="Copy TX as JSON">&#x2398;</button>
        `;

        el.querySelector('.copy-entry-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            this._copyToClipboard(entry, e.currentTarget);
        });

        // Data panel (hidden until toggled)
        const dataPanel = document.createElement('div');
        dataPanel.className = 'chain-data';
        let dataBuilt = false;

        el.addEventListener('mouseenter', () => {
            this.dispatchEvent(new CustomEvent('tx-hover', {
                bubbles: true, detail: { entry }
            }));
        });

        el.addEventListener('mouseleave', () => {
            this.dispatchEvent(new CustomEvent('tx-hover-end', {
                bubbles: true
            }));
        });

        el.addEventListener('click', (e) => {
            if (hasEntryData) {
                const isOpen = dataPanel.classList.contains('open');
                if (isOpen) {
                    dataPanel.classList.remove('open');
                    el.classList.remove('expanded');
                    const tog = el.querySelector('.data-toggle');
                    if (tog) tog.textContent = '\u25B8';
                } else {
                    if (!dataBuilt) {
                        const tree = document.createElement('div');
                        buildJsonTree(tree, entry.data);
                        dataPanel.appendChild(tree);
                        dataBuilt = true;
                    }
                    dataPanel.classList.add('open');
                    el.classList.add('expanded');
                    const tog = el.querySelector('.data-toggle');
                    if (tog) tog.textContent = '\u25BE';
                }
            }

            this.dispatchEvent(new CustomEvent('tx-inspect', {
                bubbles: true, detail: { entry }
            }));
        });

        item.appendChild(el);
        item.appendChild(dataPanel);
        this._listEl.appendChild(item);
    }

    /** Extract inner event type from a stream TX's data payload. */
    _getEventName(entry) {
        if (entry.data && typeof entry.data === 'object' && entry.data.name) {
            return entry.data.name;
        }
        return 'chunk';
    }

    /** Group stream entries by consecutive inner event type, accumulating text.
     *  Breaks on event name change OR inner seq reset to 0 (new sub-sequence). */
    _buildSubGroups(streamEntries) {
        const groups = [];
        let current = null;

        for (const entry of streamEntries) {
            const eventName = this._getEventName(entry);
            const innerSeq = entry.data?.meta?.seq ?? 0;

            // New group when: name changes OR inner seq resets to 0 (separate call)
            const nameChanged = !current || current.eventName !== eventName;
            const seqReset = !nameChanged && innerSeq === 0 && current.entries.length > 0;

            if (nameChanged || seqReset) {
                current = { eventName, entries: [], text: '' };
                groups.push(current);
            }

            current.entries.push(entry);

            // Accumulate text for text-based events
            const isTextEvent = eventName === 'text' || eventName === 'thinking';
            if (isTextEvent) {
                const chunk = entry.data?.data?.text ?? '';
                current.text += chunk;
            }
        }

        return groups;
    }

    _renderStreamGroup(streamEntries, rootTs) {
        const first = streamEntries[0];
        const last = streamEntries[streamEntries.length - 1];
        const offset = ((first.timestamp - rootTs) * 1000).toFixed(1);
        const groupDuration = ((last.timestamp - first.timestamp) * 1000).toFixed(1);

        const item = document.createElement('div');
        item.className = 'chain-item';

        const el = document.createElement('div');
        el.className = 'chain-entry';

        el.innerHTML = `
            <span class="data-toggle">\u25B8</span>
            <span class="offset">+${offset}ms</span>
            <span class="chain-name stream">${first.name}</span>
            <span class="chain-route">
                ${first.source}<span class="arrow"> \u2192 </span>${first.target}
            </span>
            <span class="badge badge-stream">${streamEntries.length} chunks, ${groupDuration}ms</span>
        `;

        const expandPanel = document.createElement('div');
        expandPanel.className = 'chain-data';
        let expanded = false;

        el.addEventListener('mouseenter', () => {
            this.dispatchEvent(new CustomEvent('tx-hover', {
                bubbles: true, detail: { entry: first }
            }));
        });

        el.addEventListener('mouseleave', () => {
            this.dispatchEvent(new CustomEvent('tx-hover-end', { bubbles: true }));
        });

        el.addEventListener('click', () => {
            const isOpen = expandPanel.classList.contains('open');
            const tog = el.querySelector('.data-toggle');

            if (isOpen) {
                expandPanel.classList.remove('open');
                el.classList.remove('expanded');
                if (tog) tog.textContent = '\u25B8';
            } else {
                if (!expanded) {
                    this._renderSubGroups(expandPanel, streamEntries, rootTs);
                    expanded = true;
                }
                expandPanel.classList.add('open');
                el.classList.add('expanded');
                if (tog) tog.textContent = '\u25BE';
            }
        });

        item.appendChild(el);
        item.appendChild(expandPanel);
        this._listEl.appendChild(item);
    }

    _renderSubGroups(container, streamEntries, rootTs) {
        const subGroups = this._buildSubGroups(streamEntries);

        for (const group of subGroups) {
            const subEl = document.createElement('div');
            subEl.className = 'sub-group';

            const header = document.createElement('div');
            header.className = 'sub-group-header';

            const isTextBased = group.eventName === 'text' || group.eventName === 'thinking';
            const nameClass = `sub-group-name ${group.eventName}`;
            const countBadge = group.entries.length > 1
                ? `<span class="badge badge-stream">${group.entries.length}</span>`
                : '';

            // Build a preview snippet for the header line
            let preview = '';
            if (isTextBased && group.text) {
                const snippet = group.text.replace(/\s+/g, ' ').substring(0, 80);
                preview = `<span class="sub-group-preview">${this._escapeHtml(snippet)}${group.text.length > 80 ? '\u2026' : ''}</span>`;
            } else if (group.eventName === 'tool_call' && group.entries[0]?.data?.data) {
                const d = group.entries[0].data.data;
                preview = `<span class="sub-group-preview">${this._escapeHtml(d.tool || '')}</span>`;
            } else if (group.eventName === 'tool_result' && group.entries[0]?.data?.data) {
                const d = group.entries[0].data.data;
                const r = String(d.result || '').substring(0, 60);
                preview = `<span class="sub-group-preview">${this._escapeHtml(r)}</span>`;
            } else if (group.eventName === 'done' && group.entries[0]?.data?.data?.usage) {
                const u = group.entries[0].data.data.usage;
                preview = `<span class="sub-group-preview">${u.input_tokens}\u2192${u.output_tokens} tokens</span>`;
            }

            const hasContent = (isTextBased && group.text) || hasData(group.entries[0]?.data);
            const toggle = hasContent ? '<span class="data-toggle">\u25B8</span>' : '';

            header.innerHTML = `
                ${toggle}
                <span class="${nameClass}">${group.eventName}</span>
                ${countBadge}
                ${preview}
            `;

            subEl.appendChild(header);

            // Build the expandable content panel
            if (hasContent) {
                const contentPanel = document.createElement('div');
                contentPanel.className = 'chain-data';
                let built = false;

                header.addEventListener('click', () => {
                    const isOpen = contentPanel.classList.contains('open');
                    const tog = header.querySelector('.data-toggle');

                    if (isOpen) {
                        contentPanel.classList.remove('open');
                        if (tog) tog.textContent = '\u25B8';
                    } else {
                        if (!built) {
                            if (isTextBased && group.text) {
                                const textBlock = document.createElement('div');
                                textBlock.className = 'accumulated-text';
                                textBlock.textContent = group.text;
                                contentPanel.appendChild(textBlock);
                            } else {
                                // JSON tree for non-text events
                                const tree = document.createElement('div');
                                buildJsonTree(tree, group.entries[0].data);
                                contentPanel.appendChild(tree);
                            }
                            built = true;
                        }
                        contentPanel.classList.add('open');
                        if (tog) tog.textContent = '\u25BE';
                    }
                });

                subEl.appendChild(contentPanel);
            }

            container.appendChild(subEl);
        }
    }

    _escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    hide() {
        this.classList.remove('visible');
    }
}

customElements.define('tx-detail', TxDetail);
