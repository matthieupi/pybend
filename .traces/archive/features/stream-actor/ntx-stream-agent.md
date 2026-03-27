# Plan: Unified Streaming Architecture + `<ntx-stream-agent>` (Phase 1)

## Context

`ntx-stream` renders streaming output as plain text. Agent methods yield structured events (thinking, tool_call, tool_result, text, done). The codebase has two competing streaming mechanisms: NTTStream (TX-based, extends NTTMethod) and StreamActor mixin (HTTP.stream-based, extends HTMLElement). This plan unifies them and adds rich agent streaming.

A separate Phase 2 plan exists at `.traces/plans/ntx-stream-phase2.md` for migrating NTTAgentLive/NTTChat.

## Architecture Decision Record

### Problem
Three concerns were conflated across the codebase in incompatible ways:
- **Transport**: NTTStream uses TX via Matrix; StreamActor uses direct HTTP.stream()
- **Dispatch**: NTTStream has untyped `#onChunk/#onDone/#onError`; StreamActor has typed UPPERCASE per event
- **Rendering**: NTTStream accumulates plain text; NTTAgentLive renders rich entries

### Decisions
1. **TX for everything** — All streaming goes through Actor TX messaging. No direct HTTP.stream().
2. **Single hierarchy** — `Component → NTTMethod → NTTStream` (rewritten). No mixin, no MI.
3. **STREAM as inbox handler** — NTTStream has a `STREAM(data, tx)` method. Dynamic alias bridges method-name TXs to it. Dispatches to UPPERCASE sub-handlers (THINKING, TEXT, etc.). Untyped chunks fall through to TEXT() for backward compatibility.
4. **NTTStream stays in n3tx-ui** — The dispatch mechanism is agent-agnostic. Agent-specific subclasses (NTTStreamAgent, NTTAgentLive, NTTChat) live in n3tx-agents.
5. **Class name preserved** — NTTStream keeps its name and tag (`ntx-stream`). Internals rewritten.
6. **Phased delivery** — Phase 1: rewrite NTTStream + build NTTStreamAgent. Phase 2: migrate NTTAgentLive/NTTChat to extend NTTStream.

### Hierarchy (target)
```
Component                              [n3tx-core]  (Actor bridge, shadow DOM, schema lifecycle)
└── NTTMethod                          [n3tx-ui]    (form rendering, callMethod, _response_)
    └── NTTStream                      [n3tx-ui]    (streaming TX + STREAM dispatch + default TEXT)
        ├── NTTStreamAgent             [n3tx-agents] (rich agent output — Phase 1)
        ├── NTTAgentLive               [n3tx-agents] (standalone monitor — Phase 2)
        └── NTTChat                    [n3tx-agents] (chat interface — Phase 2)
```

Same pattern as `Component → NTTElement / ListElement`: parent provides infra, subclasses handle rendering.

---

## Codebase Reference

### Files to modify
| File | Action |
|------|--------|
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js` | REWRITE — replace internals, keep class name + tag |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` | EDIT — two lines for renderer selection |
| `apps/veille/models/grant.py` | EDIT — add `methods` to `__ui__` |
| `apps/veille/static/index.html` | EDIT — add import for ntx-stream-agent.js |

### Files to create
| File | Action |
|------|--------|
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` | CREATE — rich agent streaming component |

### Key reference files (read-only context)
| File | Why |
|------|-----|
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js` | Parent class — NTTStream extends this |
| `packages/n3tx-core/src/n3tx_core/static/core/Component.js` | Grandparent — provides Actor bridge, shadow DOM, Matrix registration |
| `packages/n3tx-core/src/n3tx_core/static/core/TX.js` | TX message envelope — used in callMethod() |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` | Visual reference — NTTStreamAgent copies this rendering style |
| `packages/n3tx-agents/src/n3tx_agents/static/components/StreamActor.js` | OLD mixin — DO NOT use; keep for Phase 1 backward compat |
| `packages/n3tx-ui/src/n3tx_ui/mixin.py` | ViewableMixin — injects `__ui__['methods']` into schema |
| `apps/veille/models/grant.py` | Grant model with analyze() method |
| `apps/veille/static/components/ntx-grant-analyze.js` | Existing veille-specific analyze component (uses old StreamActor pattern) |

### Static file serving
The Veille app uses `ssr='full'` (`create_app(..., ssr='full')`) which merges all package static directories into one URL space. Components from `n3tx-core`, `n3tx-ui`, `n3tx-agents`, and the app's own `static/` directory are all served under the same root. So:
- `import './components/ntx-stream.js'` resolves to n3tx-ui's file
- `import './components/ntx-stream-agent.js'` resolves to n3tx-agents' file
- `import './components/StreamActor.js'` resolves to n3tx-agents' file
- Cross-package imports use relative paths as if all files are co-located

---

## Change 1: Rewrite NTTStream — typed streaming dispatch

**File**: `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js`

### What exists today

NTTStream extends NTTMethod and adds:
- `#chunks` array for text accumulation
- `#bindStreamHandler()` creates `this[method_name]` dynamic handler that routes to `#onChunk/#onDone/#onError`
- `callMethod()` sends TX with `meta: {stream: true}`
- `#renderOutput()` joins all chunk text and displays with cursor animation
- `render()` calls `super.render()` then appends stream CSS

Current code (full file — 130 lines):
```javascript
import { NTTMethod } from './ntx-method.js';
import TX from '../core/TX.js';
import Logging from '../utils/Logging.js';
import { showToast } from '../utils/Toast.js';

export class NTTStream extends NTTMethod {
    #chunks; #streaming; #boundHandler;
    constructor() {
        super();
        this.#chunks = [];
        this.#streaming = false;
    }
    #bindStreamHandler() {
        const name = this.method;
        if (!name) return;
        if (this.#boundHandler && this.#boundHandler !== name) delete this[this.#boundHandler];
        if (this.#boundHandler === name) return;
        this[name] = (data, tx) => {
            if (tx?.meta?.error)       return this.#onError(data);
            if (tx?.meta?.stream_end)  return this.#onDone(data);
            this.#onChunk(data);
        };
        this.#boundHandler = name;
    }
    callMethod() {
        const target = this.ntt?.href || this.proto?.href;
        if (!target) return;
        this.#chunks = []; this.response = null; this.#streaming = true;
        this.#renderOutput(); this.#bindStreamHandler();
        this.send(new TX({ name: this.method, source: this.addr, target, data: { ...this.value }, meta: { stream: true } }));
    }
    // ... #onChunk, #onDone, #onError, #renderOutput, #esc, render, streamStyles
}
customElements.define('ntx-stream', NTTStream);
```

### What to write

Replace the entire file. The new NTTStream:
1. Still extends NTTMethod (same hierarchy)
2. Still sends TX with `meta: {stream: true}` (same transport)
3. NEW: `STREAM(data, tx)` method handles all stream dispatch
4. NEW: Dynamic alias `this[method] = STREAM` bridges method-name TXs
5. NEW: Default `TEXT(data)` handler for backward-compatible text accumulation
6. NEW: Default `STREAM_END(data)` and `STREAM_ERROR(data)` handlers
7. Subclasses override UPPERCASE handlers (THINKING, TOOL_CALL, etc.)

### Full implementation spec

```javascript
import { NTTMethod } from './ntx-method.js';
import TX from '../core/TX.js';
import { showToast } from '../utils/Toast.js';

export class NTTStream extends NTTMethod {

    // ── State ──
    #streaming = false;     // true while stream is active
    #textBuf = '';          // accumulated text from TEXT events
    #boundHandler = null;   // name of currently bound dynamic alias

    constructor() {
        super();
    }

    // ── STREAM inbox handler ──
    // All stream chunks route here via dynamic alias.
    // Dispatches to UPPERCASE sub-handlers by event name.
    // Untyped chunks (no data.name) fall through to TEXT().
    STREAM(data, tx) {
        if (tx?.meta?.error)      return this.STREAM_ERROR(data);
        if (tx?.meta?.stream_end) return this.STREAM_END(data);

        // Typed event dispatch: {name: 'thinking', data: {text: '...'}} → this.THINKING({text: '...'})
        const name = data?.name?.toUpperCase();
        if (name && typeof this[name] === 'function') {
            this[name](data.data, data.meta);
        } else {
            // Untyped fallback — treat entire chunk as text
            this.TEXT(data);
        }
    }

    // ── callMethod override ──
    // Sends TX with meta.stream=true through Actor system.
    // Binds dynamic alias so reply TXs (named after method) route to STREAM().
    callMethod() {
        const target = this.ntt?.href || this.proto?.href;
        if (!target) return;

        this.#reset();
        this.#streaming = true;
        this.#renderOutput();

        // Dynamic alias: reply TX arrives as this[method]() → forwards to STREAM()
        // This bridges method-name TX routing to the unified STREAM handler.
        const name = this.method;
        if (this.#boundHandler && this.#boundHandler !== name) {
            delete this[this.#boundHandler];
        }
        this[name] = (data, tx) => this.STREAM(data, tx);
        this.#boundHandler = name;

        this.send(new TX({
            name: this.method,
            source: this.addr,
            target: target,
            data: { ...this.value },
            meta: { stream: true },
        }));
    }

    // ── Default UPPERCASE handlers ──
    // Subclasses override these for rich rendering.
    // Base NTTStream provides backward-compatible plain text accumulation.

    TEXT(data) {
        // Extract text from various chunk formats
        const text = data?.text || data?.chunk || data?.content || '';
        if (typeof data === 'string') this.#textBuf += data;
        else this.#textBuf += text;
        this.#renderOutput();
    }

    STREAM_END(data) {
        this.#streaming = false;
        this.#renderOutput();
        // Refresh parent entity so list/item components update
        if (this.ntt?.pull) this.ntt.pull();
    }

    STREAM_ERROR(data) {
        this.#streaming = false;
        const msg = (typeof data === 'string') ? data
            : data?.message || data?.detail || data?.error || 'Stream error';
        this.response = { error: msg };
        showToast(msg, 'error');
        this.#renderOutput();
    }

    // ── Rendering ──

    render() {
        super.render();  // NTTMethod renders form (fieldset/inline/button)
        // Append stream CSS if not already present
        const style = this.shadowRoot.querySelector('style');
        if (style && !style.textContent.includes('stream-output')) {
            style.textContent += NTTStream.streamStyles;
        }
    }

    #renderOutput() {
        let el = this.shadowRoot.querySelector('.stream-output');
        if (!el) {
            el = document.createElement('div');
            el.className = 'stream-output';
            this.shadowRoot.appendChild(el);
        }
        if (this.response?.error) {
            el.innerHTML = `<div class="stream-error">${this.#esc(this.response.error)}</div>`;
            return;
        }
        el.innerHTML = `<div class="stream-text">${this.#esc(this.#textBuf)}</div>`
            + (this.#streaming ? '<span class="stream-cursor">|</span>' : '');
    }

    #reset() {
        this.#textBuf = '';
        this.#streaming = false;
        this.response = null;
        const el = this.shadowRoot?.querySelector('.stream-output');
        if (el) el.innerHTML = '';
    }

    #esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    disconnectedCallback() {
        super.disconnectedCallback();
    }

    static streamStyles = `
        .stream-output { margin-top: .75rem; padding: .8rem; background: var(--surface-3);
            border: 1px solid var(--border); border-radius: .5rem; min-height: 2rem;
            max-height: 400px; overflow-y: auto; white-space: pre-wrap; color: var(--text-1); }
        .stream-cursor { animation: blink 1s step-end infinite; color: var(--accent); }
        @keyframes blink { 50% { opacity: 0; } }
        .stream-text { line-height: 1.5; }
        .stream-error { color: var(--error, #f87171); font-style: italic; line-height: 1.5; }
    `;
}

customElements.define('ntx-stream', NTTStream);
```

### Behavioral contract for subclasses

NTTStream provides these overridable UPPERCASE handlers:
- `TEXT(data)` — called for typed `{name:'text', data:{text:'...'}}` events AND for untyped fallback chunks
- `STREAM_END(data)` — called when `tx.meta.stream_end` is true
- `STREAM_ERROR(data)` — called when `tx.meta.error` is true

Subclasses add their own:
- `THINKING(data)` — `{name:'thinking', data:{text:'...'}}`
- `TOOL_CALL(data)` — `{name:'tool_call', data:{tool:'...', args:{...}, call_id:'...'}}`
- `TOOL_RESULT(data)` — `{name:'tool_result', data:{tool:'...', result:'...', call_id:'...'}}`
- `DONE(data)` — `{name:'done', data:{answer:'...', usage:{...}, tool_calls:N}}`

### How TX flow works (for context)

1. User clicks Run → `callMethod()` fires
2. `callMethod()` sends `TX({name: 'analyze', target: 'grants/1', meta: {stream: true}})`
3. TX routes through Matrix → NetworkAdapter → HTTP POST to backend
4. Backend's `Grant.analyze()` is an async generator that yields events
5. Backend wraps each yield as an SSE event: `event: chunk\ndata: {name:'thinking', data:{text:'...'}}\n\n`
6. NetworkAdapter reads SSE, creates reply TXs with `name: 'analyze'` (matching the original method name)
7. Matrix routes reply TX to the component's Actor inbox
8. Actor inbox dispatches to `this.analyze(data, tx)` — the dynamic alias
9. Alias forwards to `this.STREAM(data, tx)` → dispatches to `this.THINKING(data.data)`
10. For `stream_end`: reply TX has `meta: {stream_end: true}` → STREAM routes to `this.STREAM_END()`

---

## Change 2: Create NTTStreamAgent — rich agent output

**File**: `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` (NEW)

### Purpose

Extends NTTStream with rich rendering for agent streaming events. Renders inside an ntx-item method card. Inherits form rendering from NTTMethod (for methods with parameters) and TX streaming from NTTStream.

### Import path

With `ssr='full'`, all package static dirs merge. So:
```javascript
import { NTTStream } from './ntx-stream.js';  // resolves to n3tx-ui's file
```

### Visual reference

Copy the rendering style from NTTAgentLive (`ntx-agent-live.js`). Specifically:

**Entry types and their visual styling:**
- `.entry-thinking` — purple left border (`#a78bfa`), italic, 0.8rem, collapsible
- `.entry-tool-call` — yellow left border (`#f59e0b`), gear icon, spinner, args as JSON tree. On complete: green left border (`#22c55e`)
- `.entry-text-output` — blue left border (`#38bdf8`), markdown rendered, 1.6 line-height
- `.entry-error` — red left border (`#f87171`), red text

**Collapsible entries:**
- Max-height 4.2em when collapsed, "▾ more" indicator
- Click to expand/collapse
- Thinking entries become collapsible when deactivated
- Tool call entries with args are collapsible

**Text buffering (from NTTAgentLive):**
- `#textBuf` / `#thinkBuf` accumulate incrementally
- `#scheduleRender()` renders immediately on newline, debounces 300ms otherwise
- `#renderMd()` uses `marked.parse()` if available, falls back to textContent
- `#flushRender()` forces final render on DONE

**Tool card tracking:**
- `#toolCards` Map keyed by `call_id`
- TOOL_CALL creates entry, stores in map
- TOOL_RESULT finds entry by `call_id`, removes spinner, appends result

### Full implementation spec

```javascript
import { NTTStream } from './ntx-stream.js';
import { showToast } from '../utils/Toast.js';

export class NTTStreamAgent extends NTTStream {

    #toolCards = new Map();
    #textBuf = '';
    #textRendered = 0;
    #textTimer = null;
    #thinkBuf = '';
    #thinkRendered = 0;
    #thinkTimer = null;
    #outputEl = null;

    // ── UPPERCASE handlers ──

    THINKING(data, meta) {
        const text = data?.text || '';
        if (!text) { this.#setThinking(true); return; }

        this.#thinkBuf += text;
        let entry = this.#output().querySelector('.entry-thinking-active');
        if (!entry) {
            entry = this.#addEntry('thinking', '');
            entry.classList.add('entry-thinking-active');
        }
        this.#scheduleRender(entry, 'think');
    }

    TOOL_CALL(data, meta) {
        this.#setThinking(false);
        // Normalize: args may arrive as JSON string from some LLM providers
        if (typeof data.args === 'string') {
            try { data.args = JSON.parse(data.args); } catch { data.args = { raw: data.args }; }
        }
        const argsHtml = data.args && Object.keys(data.args).length
            ? `<div class="tool-json">${this.#esc(JSON.stringify(data.args, null, 2))}</div>` : '';
        const entry = this.#addEntry('tool-call',
            `<span class="entry-icon">\u2699</span> Calling <strong>${this.#esc(data.tool)}</strong>${argsHtml}`);
        const spinner = document.createElement('span');
        spinner.className = 'entry-spin';
        spinner.textContent = ' \u25CF';
        entry.querySelector('.entry-content').appendChild(spinner);
        if (argsHtml) entry.classList.add('collapsible');
        if (data.call_id) this.#toolCards.set(data.call_id, entry);
    }

    TOOL_RESULT(data, meta) {
        const card = data.call_id && this.#toolCards.get(data.call_id);
        if (card) {
            card.querySelector('.entry-spin')?.remove();
            card.classList.add('complete');
            const resultDiv = document.createElement('div');
            resultDiv.className = 'tool-result-text';
            const resultStr = typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2);
            resultDiv.textContent = resultStr.slice(0, 500);
            card.querySelector('.entry-content').appendChild(resultDiv);
        } else {
            this.#addEntry('tool-result',
                `<span class="entry-icon">\u2714</span> ${this.#esc(data.tool || 'Tool')}: result received`);
        }
    }

    TEXT(data, meta) {
        this.#setThinking(false);
        this.#textBuf += (data?.text || '');

        let entry = this.#output().querySelector('.entry-text-output');
        if (!entry) {
            entry = this.#addEntry('text-output', '');
            entry.querySelector('.entry-content').classList.add('entry-text-output-content');
            entry.classList.add('entry-text-output');
        }
        this.#scheduleRender(entry, 'text');
    }

    DONE(data, meta) {
        this.#setThinking(false);
        this.#flushRender();
        const usage = data?.usage;
        if (usage) {
            let footer = this.#output().querySelector('.stream-footer');
            if (!footer) {
                footer = document.createElement('div');
                footer.className = 'stream-footer';
                this.#output().appendChild(footer);
            }
            footer.innerHTML =
                `<span>Tokens: ${usage.input_tokens || 0} in / ${usage.output_tokens || 0} out</span>` +
                (data.tool_calls ? ` &middot; <span>${data.tool_calls} tool calls</span>` : '');
        }
        this.#scrollToBottom();
    }

    STREAM_END(data) {
        this.#setThinking(false);
        this.#flushRender();
        // Refresh parent entity
        if (this.ntt?.pull) this.ntt.pull();
    }

    STREAM_ERROR(data) {
        this.#setThinking(false);
        this.#flushRender();
        const msg = (typeof data === 'string') ? data
            : data?.message || data?.detail || data?.error || 'Stream error';
        this.#addEntry('error', `Error: ${this.#esc(msg)}`);
        showToast(msg, 'error');
    }

    // ── Rendering ──

    render() {
        super.render();  // NTTMethod renders form → NTTStream appends stream CSS
        // Replace NTTStream's simple output with our rich output container
        let el = this.shadowRoot.querySelector('.stream-output');
        if (el) el.remove();
        // Inject agent-specific CSS
        const style = this.shadowRoot.querySelector('style');
        if (style && !style.textContent.includes('entry-thinking')) {
            style.textContent += NTTStreamAgent.agentStyles;
        }
    }

    // Called by callMethod() in NTTStream before sending TX
    // We override to also reset our agent-specific state
    callMethod() {
        this.#toolCards.clear();
        this.#textBuf = ''; this.#textRendered = 0; clearTimeout(this.#textTimer);
        this.#thinkBuf = ''; this.#thinkRendered = 0; clearTimeout(this.#thinkTimer);
        this.#outputEl = null;
        super.callMethod();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        clearTimeout(this.#textTimer);
        clearTimeout(this.#thinkTimer);
    }

    // ── Internal helpers ──

    /** Get or create the output container for agent entries */
    #output() {
        if (this.#outputEl) return this.#outputEl;
        let el = this.shadowRoot.querySelector('.agent-output');
        if (!el) {
            el = document.createElement('div');
            el.className = 'agent-output';
            this.shadowRoot.appendChild(el);

            // Click-to-expand/collapse on collapsible entries (event delegation)
            el.addEventListener('click', (e) => {
                const entry = e.target.closest('.entry.collapsible');
                if (entry) entry.classList.toggle('expanded');
            });
        }
        this.#outputEl = el;
        return el;
    }

    #addEntry(type, html) {
        const el = document.createElement('div');
        el.className = `entry entry-${type}`;
        el.innerHTML = `<div class="entry-content">${html}</div>`;
        this.#output().appendChild(el);
        this.#scrollToBottom();
        return el;
    }

    #setThinking(on) {
        const output = this.#output();
        let el = output.querySelector('.entry-thinking-active');
        if (on && !el) {
            el = this.#addEntry('thinking', '<span class="thinking-anim">Thinking</span>');
            el.classList.add('entry-thinking-active');
        } else if (!on && el) {
            const content = el.querySelector('.entry-content');
            if (content?.querySelector('.thinking-anim')) {
                el.remove();
            } else {
                clearTimeout(this.#thinkTimer);
                this.#renderMd(el, 'think');
                el.classList.remove('entry-thinking-active');
                el.classList.add('collapsible');
                this.#thinkBuf = ''; this.#thinkRendered = 0;
            }
        }
    }

    #scheduleRender(entry, kind) {
        const buf = kind === 'text' ? this.#textBuf : this.#thinkBuf;
        const rendered = kind === 'text' ? this.#textRendered : this.#thinkRendered;
        const fresh = buf.slice(rendered);
        const hasNewline = fresh.includes('\n');

        if (kind === 'text') {
            clearTimeout(this.#textTimer);
            if (hasNewline) this.#renderMd(entry, kind);
            else this.#textTimer = setTimeout(() => this.#renderMd(entry, kind), 300);
        } else {
            clearTimeout(this.#thinkTimer);
            if (hasNewline) this.#renderMd(entry, kind);
            else this.#thinkTimer = setTimeout(() => this.#renderMd(entry, kind), 300);
        }
        this.#scrollToBottom();
    }

    #renderMd(entry, kind) {
        if (!entry) return;
        const buf = kind === 'text' ? this.#textBuf : this.#thinkBuf;
        if (!buf) return;
        const content = entry.querySelector('.entry-text-output-content')
            || entry.querySelector('.entry-content');
        if (typeof marked !== 'undefined' && marked.parse) {
            content.innerHTML = marked.parse(buf);
        } else {
            content.textContent = buf;
        }
        if (kind === 'text') this.#textRendered = buf.length;
        else this.#thinkRendered = buf.length;
        this.#scrollToBottom();
    }

    #flushRender() {
        clearTimeout(this.#textTimer);
        clearTimeout(this.#thinkTimer);
        const output = this.#output();
        const textEntry = output.querySelector('.entry-text-output');
        if (textEntry) this.#renderMd(textEntry, 'text');
        const thinkEntry = output.querySelector('.entry-thinking-active');
        if (thinkEntry) this.#renderMd(thinkEntry, 'think');
    }

    #scrollToBottom() {
        const el = this.#output();
        el.scrollTop = el.scrollHeight;
    }

    #esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    // ── CSS ──
    // Matches ntx-agent-live visual style, adapted for embedded method card context.
    static agentStyles = `
        .agent-output {
            margin-top: .75rem;
            max-height: 500px;
            overflow-y: auto;
            font-size: .85rem;
        }

        .entry { margin-bottom: .4rem; line-height: 1.5; }
        .entry-content { padding: .3rem .5rem; border-radius: .3rem; }

        /* Collapsible entries */
        .entry.collapsible:not(.expanded) .entry-content {
            max-height: 4.2em; overflow: hidden; cursor: pointer;
        }
        .entry.collapsible:not(.expanded)::after {
            content: '\u25BE  more'; display: block; text-align: center;
            font-size: .6rem; letter-spacing: .03em; color: var(--text-2, #aaa);
            cursor: pointer; padding: .1rem 0; opacity: .5;
        }
        .entry.collapsible:not(.expanded):hover::after { opacity: .8; }
        .entry.collapsible.expanded .entry-content { cursor: pointer; }

        /* Thinking */
        .entry-thinking .entry-content {
            background: rgba(167, 139, 250, 0.08);
            border-left: 2px solid var(--thinking, #a78bfa);
            word-break: break-word; line-height: 1.5;
        }
        .entry-thinking p { margin: .3em 0; }
        .entry-thinking code {
            background: rgba(0,0,0,.2); padding: .1em .3em; border-radius: 3px;
            font-size: .85em; font-family: 'SF Mono', Consolas, Monaco, monospace;
        }
        .entry-thinking pre {
            background: rgba(0,0,0,.2); border-radius: .3rem;
            padding: .3rem .5rem; overflow-x: auto; font-size: .8em; margin: .3em 0;
        }
        .entry-thinking pre code { background: none; padding: 0; }
        .entry-thinking-active .entry-content { font-style: italic; opacity: .7; color: var(--thinking, #a78bfa); font-size: .8rem; }

        /* Tool calls */
        .entry-tool-call .entry-content {
            background: var(--surface-3, #0f3460);
            border-left: 2px solid var(--warning, #f59e0b);
        }
        .entry-tool-call.complete .entry-content {
            border-left-color: var(--success, #22c55e);
        }
        .entry-icon { opacity: .6; margin-right: .2rem; }
        .entry-spin { animation: spin 1s linear infinite; color: var(--warning, #fbbf24); font-size: .6rem; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .tool-json {
            margin: .3rem 0 0; padding: .3rem .5rem;
            background: rgba(0,0,0,.2); border-radius: .2rem;
            font-size: .75rem; font-family: 'SF Mono', Consolas, Monaco, monospace;
            overflow: auto; max-height: 200px; white-space: pre-wrap;
        }
        .tool-result-text {
            margin-top: .3rem; font-size: .75rem;
            font-family: 'SF Mono', Consolas, Monaco, monospace;
            overflow: auto; max-height: 200px; white-space: pre-wrap; color: var(--text-2, #aaa);
        }

        /* Text output */
        .entry-text-output .entry-content {
            word-break: break-word;
            border-left: 2px solid var(--text-accent, #38bdf8);
            line-height: 1.6;
        }
        .entry-text-output h1, .entry-text-output h2, .entry-text-output h3 { margin: .6em 0 .3em; font-size: 1.1em; }
        .entry-text-output p { margin: .4em 0; }
        .entry-text-output code {
            background: rgba(0,0,0,.3); padding: .1em .3em; border-radius: 3px;
            font-size: .85em; font-family: 'SF Mono', Consolas, Monaco, monospace;
        }
        .entry-text-output pre {
            background: rgba(0,0,0,.3); border-radius: .3rem;
            padding: .4rem .6rem; overflow-x: auto; font-size: .8em; margin: .4em 0;
        }
        .entry-text-output pre code { background: none; padding: 0; }
        .entry-text-output blockquote {
            border-left: 2px solid var(--text-2, #aaa); margin: .4em 0;
            padding: .2em .8em; opacity: .8;
        }
        .entry-text-output ul, .entry-text-output ol { padding-left: 1.5em; margin: .3em 0; }
        .entry-text-output a { color: var(--accent, #4cc9f0); }

        /* Error */
        .entry-error .entry-content {
            background: rgba(248, 113, 113, 0.1);
            border-left: 2px solid var(--error, #f87171);
            color: var(--error, #f87171);
        }

        /* Thinking animation */
        .thinking-anim::after { content: ''; animation: dots 1.5s steps(3, end) infinite; }
        @keyframes dots { 0% { content: '.'; } 33% { content: '..'; } 66% { content: '...'; } }

        /* Footer (token usage) */
        .stream-footer {
            padding: .3rem .5rem; font-size: .65rem; color: var(--text-2, #aaa);
            border-top: 1px solid var(--border, #333); margin-top: .4rem;
        }
    `;
}

customElements.define('ntx-stream-agent', NTTStreamAgent);
```

---

## Change 3: Update ntx-item.js — renderer selection from schema

**File**: `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`

### What to change

Two locations where the tag is chosen. Add `def.ui?.renderer` check before the default fallback.

**Location 1 — line ~337** (button-layout methods in `sm()` display):
```javascript
// FIND this exact line:
const tag = def.stream ? 'ntx-stream' : 'ntx-method';
// REPLACE with:
const tag = def.ui?.renderer || (def.stream ? 'ntx-stream' : 'ntx-method');
```

**Location 2 — line ~820** (standalone methods in `#standaloneMethodsHtml()`):
```javascript
// FIND this exact line:
const tag = def.stream ? 'ntx-stream' : 'ntx-method';
// REPLACE with:
const tag = def.ui?.renderer || (def.stream ? 'ntx-stream' : 'ntx-method');
```

Also add `ntx-stream-agent` to the click-skip list on line ~750:
```javascript
// FIND:
if (e.target.closest('button, input, textarea, select, a, ntx-method, ntx-stream, .reply-input-box, ntx-ref-picker')) return;
// REPLACE with:
if (e.target.closest('button, input, textarea, select, a, ntx-method, ntx-stream, ntx-stream-agent, .reply-input-box, ntx-ref-picker')) return;
```

### How it works

When ViewableMixin processes Grant's `__ui__['methods']`, it injects:
```json
schema.methods.analyze.ui = { "renderer": "ntx-stream-agent" }
```

ntx-item reads `def.ui?.renderer` → gets `'ntx-stream-agent'` → creates `<ntx-stream-agent>` tag instead of `<ntx-stream>`.

---

## Change 4: Wire Grant.analyze via `__ui__`

**File**: `apps/veille/models/grant.py`

### What to change

Add `'methods'` key to the existing `__ui__` dict:

```python
# FIND (line ~27):
__ui__: ClassVar[dict] = {
    'field_order': [
        'title', 'funder', 'status', 'url', 'source_url',
        'amount_min', 'amount_max', 'deadline',
        'description', 'eligibility_criteria',
        'required_documents', 'application_process',
        'admissibility_score', 'admissibility_reasoning',
    ],
    'groups': {
        'Overview': ['title', 'funder', 'status', 'url', 'source_url'],
        'Funding': ['amount_min', 'amount_max', 'deadline'],
        'Details': ['description', 'eligibility_criteria',
                    'required_documents', 'application_process'],
        'Analysis': ['admissibility_score', 'admissibility_reasoning'],
    },
}

# REPLACE with (add 'methods' key):
__ui__: ClassVar[dict] = {
    'field_order': [
        'title', 'funder', 'status', 'url', 'source_url',
        'amount_min', 'amount_max', 'deadline',
        'description', 'eligibility_criteria',
        'required_documents', 'application_process',
        'admissibility_score', 'admissibility_reasoning',
    ],
    'groups': {
        'Overview': ['title', 'funder', 'status', 'url', 'source_url'],
        'Funding': ['amount_min', 'amount_max', 'deadline'],
        'Details': ['description', 'eligibility_criteria',
                    'required_documents', 'application_process'],
        'Analysis': ['admissibility_score', 'admissibility_reasoning'],
    },
    'methods': {
        'analyze': {'renderer': 'ntx-stream-agent'},
    },
}
```

### How ViewableMixin processes this

In `packages/n3tx-ui/src/n3tx_ui/mixin.py` (lines 36-38):
```python
for method_name, hints in ui_config.get('methods', {}).items():
    if method_name in s.get('methods', {}):
        s['methods'][method_name]['ui'] = dict(hints)
```

This copies `{'renderer': 'ntx-stream-agent'}` into `schema['methods']['analyze']['ui']`. The frontend reads `def.ui.renderer` when choosing the component tag.

---

## Change 5: Add import to Veille index.html

**File**: `apps/veille/static/index.html`

### What to change

Add import for the new component after the existing ntx-stream import (line ~134):

```html
<!-- FIND: -->
import './components/ntx-stream.js';
<!-- ADD AFTER: -->
import './components/ntx-stream-agent.js';
```

With `ssr='full'`, this resolves to `n3tx-agents/static/components/ntx-stream-agent.js`.

---

## Verification

### Backward compatibility
1. Any existing `<ntx-stream>` usage continues to work — simple text accumulation unchanged
2. NTTAgentLive and NTTChat continue working via old StreamActor mixin (not touched in Phase 1)
3. `ntx-grant-analyze.js` (veille-specific component) continues working unchanged

### Rich agent output
1. Start Veille: `cd /workspace/apps/veille && python3 main.py`
2. Log in, navigate to a grant detail view
3. The analyze method should render as `<ntx-stream-agent>` (not `<ntx-stream>`)
4. Click Run → events stream:
   - THINKING → animated "Thinking..." entry with purple border
   - TOOL_CALL → gear icon + tool name + spinner
   - TOOL_RESULT → spinner removed, result appended
   - TEXT → markdown rendered progressively
   - DONE → token usage footer
   - STREAM_END → parent entity refreshes

### Tag selection
1. Fetch Grant schema: `GET /Grant`
2. Verify `schema.methods.analyze.ui.renderer === 'ntx-stream-agent'`
3. Verify ntx-item creates `<ntx-stream-agent>` tag for the analyze method
