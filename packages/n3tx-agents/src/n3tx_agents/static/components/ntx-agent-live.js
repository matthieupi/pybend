/**
 * <ntx-agent-live> — Real-time agent activity view.
 *
 * Shows structured activity log with typed events:
 * thinking, tool calls, tool results, text generation.
 *
 * Attributes:
 *   model  — Class name (e.g., 'AgentActor')
 *   ref    — Entity ref (e.g., 'agents/1')
 *   method — Streaming method name (default: 'agentic_stream')
 *
 * Usage:
 *   <ntx-agent-live model="AgentActor" ref="agents/1"></ntx-agent-live>
 */
import HTTP from '../core/transport/HTTP.js';
import { config } from '../config.js';
import { NTT } from '../core/NTT.js';

class NTTAgentLive extends HTMLElement {
    connectedCallback() {
        this._model = this.getAttribute('model');
        this._ref = this.getAttribute('ref');
        this._method = this.getAttribute('method') || 'agentic_stream';
        this._streamHandle = null;
        this._schema = null;
        this._tablename = null;
        this._toolCards = new Map();

        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `<style>${NTTAgentLive.styles}</style>
            <div class="live-panel">
                <div class="live-header">
                    <span class="live-title">${this._model} &middot; Live</span>
                    <span class="live-status" id="status">idle</span>
                </div>
                <div class="live-input">
                    <textarea placeholder="Enter task..." rows="2"></textarea>
                    <button class="run-btn">Run</button>
                </div>
                <div class="live-log" id="log"></div>
                <div class="live-footer" id="footer"></div>
            </div>`;

        this._els = {
            status: this.shadowRoot.getElementById('status'),
            log: this.shadowRoot.getElementById('log'),
            footer: this.shadowRoot.getElementById('footer'),
            textarea: this.shadowRoot.querySelector('textarea'),
            runBtn: this.shadowRoot.querySelector('.run-btn'),
        };

        this._els.runBtn.addEventListener('click', () => this._run());
        this._els.textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._run(); }
        });

        this._loadSchema();
    }

    disconnectedCallback() {
        if (this._streamHandle) { this._streamHandle.cancel(); this._streamHandle = null; }
    }

    _loadSchema() {
        NTT.attach(this._model, (DC) => {
            this._schema = DC._schema;
            this._tablename = this._schema.__tablename__ || this._model.toLowerCase() + 's';
        });
    }

    _run() {
        const task = this._els.textarea.value.trim();
        if (!task || !this._tablename) return;

        this._els.textarea.value = '';
        this._els.log.innerHTML = '';
        this._els.footer.innerHTML = '';
        this._toolCards.clear();
        this._els.status.textContent = 'running';
        this._els.status.className = 'live-status running';
        this._els.runBtn.disabled = true;

        // Resolve entity ref for URL
        const ref = this._ref || '';
        const id = ref.includes('/') ? ref.split('/').pop() : ref;
        const url = id
            ? `${config.API_URL}/${this._tablename}/${id}/${this._method}`
            : `${config.API_URL}/${this._tablename}/${this._method}`;

        this._addEntry('task', `Task: ${task}`);

        this._streamHandle = HTTP.stream(url, { task },
            (chunk) => this._onChunk(chunk),
            () => this._onDone(),
            (err) => this._onError(err),
        );
    }

    _onChunk(chunk) {
        switch (chunk.name) {
            case 'thinking': {
                this._setThinking(true);
                break;
            }
            case 'tool_call': {
                this._setThinking(false);
                const entry = this._addEntry('tool-call',
                    `<span class="entry-icon">\u2699</span> Calling <strong>${this._esc(chunk.data.tool)}</strong>` +
                    (chunk.data.args ? `<pre class="tool-args">${this._esc(JSON.stringify(chunk.data.args, null, 2))}</pre>` : ''));
                const spinner = document.createElement('span');
                spinner.className = 'entry-spin';
                spinner.textContent = ' \u25CF';
                entry.querySelector('.entry-content').appendChild(spinner);
                if (chunk.data.call_id) this._toolCards.set(chunk.data.call_id, entry);
                break;
            }
            case 'tool_result': {
                const card = chunk.data.call_id && this._toolCards.get(chunk.data.call_id);
                if (card) {
                    card.querySelector('.entry-spin')?.remove();
                    card.classList.add('complete');
                    const resultDiv = document.createElement('div');
                    resultDiv.className = 'tool-result-text';
                    const preview = (chunk.data.result || '').slice(0, 200);
                    resultDiv.textContent = preview + (chunk.data.result?.length > 200 ? '...' : '');
                    card.querySelector('.entry-content').appendChild(resultDiv);
                } else {
                    this._addEntry('tool-result',
                        `<span class="entry-icon">\u2714</span> ${this._esc(chunk.data.tool)}: ${this._esc((chunk.data.result || '').slice(0, 200))}`);
                }
                break;
            }
            case 'text': {
                this._setThinking(false);
                let textEl = this._els.log.querySelector('.entry-text-output');
                if (!textEl) {
                    const entry = this._addEntry('text-output', '');
                    textEl = entry.querySelector('.entry-content');
                    textEl.classList.add('entry-text-output-content');
                    entry.classList.add('entry-text-output');
                }
                const content = textEl.querySelector('.entry-text-output-content') || textEl;
                content.textContent += (chunk.data?.text || '');
                break;
            }
            case 'done': {
                this._setThinking(false);
                const usage = chunk.data?.usage;
                if (usage) {
                    this._els.footer.innerHTML =
                        `<span>Tokens: ${usage.input_tokens || 0} in / ${usage.output_tokens || 0} out</span>` +
                        (chunk.data.tool_calls ? ` &middot; <span>${chunk.data.tool_calls} tool calls</span>` : '');
                }
                break;
            }
        }
        this._scrollToBottom();
    }

    _onDone() {
        this._streamHandle = null;
        this._els.status.textContent = 'done';
        this._els.status.className = 'live-status done';
        this._els.runBtn.disabled = false;
        this._setThinking(false);
    }

    _onError(err) {
        this._streamHandle = null;
        this._els.status.textContent = 'error';
        this._els.status.className = 'live-status error';
        this._els.runBtn.disabled = false;
        this._addEntry('error', `Error: ${err?.message || err?.detail || err}`);
    }

    _addEntry(type, html) {
        const el = document.createElement('div');
        el.className = `entry entry-${type}`;
        el.innerHTML = `<div class="entry-content">${html}</div>`;
        this._els.log.appendChild(el);
        this._scrollToBottom();
        return el;
    }

    _setThinking(on) {
        let el = this._els.log.querySelector('.entry-thinking-active');
        if (on && !el) {
            el = this._addEntry('thinking', '<span class="thinking-anim">Thinking</span>');
            el.classList.add('entry-thinking-active');
        } else if (!on && el) {
            el.remove();
        }
    }

    _scrollToBottom() {
        this._els.log.scrollTop = this._els.log.scrollHeight;
    }

    _esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    static styles = `
        :host { display: block; font-family: system-ui, -apple-system, sans-serif; font-size: .85rem; }

        .live-panel {
            border: 1px solid var(--border, #333); border-radius: .5rem;
            background: var(--surface-1, #1a1a2e);
            display: flex; flex-direction: column; max-height: 600px;
        }

        .live-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: .5rem .75rem;
            border-bottom: 1px solid var(--border, #333);
            background: var(--surface-2, #16213e);
            border-radius: .5rem .5rem 0 0;
        }
        .live-title { font-weight: 600; font-size: .7rem; text-transform: uppercase; letter-spacing: .05em; color: var(--text-2, #aaa); }
        .live-status {
            font-size: .65rem; font-weight: 600; text-transform: uppercase;
            padding: .15rem .4rem; border-radius: .2rem;
            background: var(--surface-3, #0f3460); color: var(--text-2, #aaa);
        }
        .live-status.running { background: var(--accent, #4cc9f0); color: #000; }
        .live-status.done { background: var(--success, #4ade80); color: #000; }
        .live-status.error { background: var(--error, #f87171); color: #000; }

        .live-input {
            display: flex; gap: .4rem; padding: .5rem .75rem;
            border-bottom: 1px solid var(--border, #333);
        }
        .live-input textarea {
            flex: 1; resize: none; padding: .4rem .5rem; border-radius: .3rem;
            background: var(--surface-3, #0f3460); color: var(--text-1, #eee);
            border: 1px solid var(--border, #333); font-family: inherit; font-size: .8rem;
            box-sizing: border-box;
        }
        .live-input textarea:focus { outline: 1px solid var(--accent, #4cc9f0); }
        .run-btn {
            padding: .4rem .8rem; border-radius: .3rem; border: none;
            background: var(--accent, #4cc9f0); color: #000; cursor: pointer;
            font-weight: 600; font-size: .8rem;
        }
        .run-btn:hover { filter: brightness(1.1); }
        .run-btn:disabled { opacity: .4; cursor: not-allowed; }

        .live-log {
            flex: 1; overflow-y: auto; padding: .5rem .75rem;
            min-height: 150px; max-height: 400px;
        }

        .entry { margin-bottom: .4rem; line-height: 1.5; }
        .entry-content { padding: .3rem .5rem; border-radius: .3rem; }

        .entry-task .entry-content {
            background: var(--surface-3, #0f3460); font-weight: 600;
            border-left: 2px solid var(--accent, #4cc9f0);
        }
        .entry-tool-call .entry-content {
            background: var(--surface-3, #0f3460);
            border-left: 2px solid var(--warning, #fbbf24);
        }
        .entry-tool-call.complete .entry-content {
            border-left-color: var(--success, #4ade80);
        }
        .entry-text-output .entry-content {
            white-space: pre-wrap; word-break: break-word;
        }
        .entry-error .entry-content {
            background: rgba(248, 113, 113, 0.1);
            border-left: 2px solid var(--error, #f87171);
            color: var(--error, #f87171);
        }
        .entry-icon { opacity: .6; margin-right: .2rem; }
        .entry-spin { animation: spin 1s linear infinite; color: var(--warning, #fbbf24); font-size: .6rem; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .tool-args {
            margin: .2rem 0 0; padding: .2rem .4rem;
            background: rgba(0,0,0,.2); border-radius: .2rem;
            font-size: .7rem; overflow-x: auto; max-height: 80px;
        }
        .tool-result-text {
            margin-top: .2rem; font-size: .75rem; opacity: .7;
            word-break: break-word;
        }

        .thinking-anim::after { content: ''; animation: dots 1.5s steps(3, end) infinite; }
        @keyframes dots { 0% { content: '.'; } 33% { content: '..'; } 66% { content: '...'; } }
        .entry-thinking-active { opacity: .5; font-style: italic; }

        .live-footer {
            padding: .3rem .75rem; font-size: .65rem; color: var(--text-2, #aaa);
            border-top: 1px solid var(--border, #333);
            min-height: 1.2rem;
        }
    `;
}

customElements.define('ntx-agent-live', NTTAgentLive);
export { NTTAgentLive };
