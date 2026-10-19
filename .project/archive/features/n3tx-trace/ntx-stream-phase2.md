# Plan: Phase 2 — Unified Streaming Migration + App Decomposition

## Context

Phase 1 rewrote NTTStream (in `n3tx-ui`) with a `STREAM()` inbox handler and typed UPPERCASE dispatch, and created NTTStreamAgent for rich agent output. Phase 2 migrates all remaining StreamActor consumers to the NTTStream hierarchy, decomposes veille's monolithic components into proper framework compositions, and deletes StreamActor.

### Current state (after Phase 1)
```
Component → NTTMethod → NTTStream (rewritten, STREAM handler, typed dispatch)  [n3tx-ui]
                            └── NTTStreamAgent (rich agent output)              [n3tx-agents]

StreamActor(HTMLElement) ← NTTAgentLive       (standalone monitor)             [n3tx-agents]
StreamActor(HTMLElement) ← NTTChat            (chat interface)                 [n3tx-agents]
StreamActor(HTMLElement) ← NTXGrantAnalyze    (grant analysis full-page)       [apps/veille]
StreamActor(HTMLElement) ← NTXRunPanel        (scraping run execution)         [apps/veille]
```

### Target state (after Phase 2)
```
Component (+ prerender() hook)               [n3tx-core]
├── NTTElement                               [n3tx-ui]
│   └── NTTItem                              [n3tx-ui]
│       ├── NTXGrantItem                     [apps/veille]  (custom grant card)
│       └── NTXRunItem                       [apps/veille]  (custom run layout)
└── NTTMethod                                [n3tx-ui]
    └── NTTStream (+ cancel())               [n3tx-ui]
        ├── NTTStreamAgent                   [n3tx-agents]
        │   └── NTXGrantAnalyze              [apps/veille]  (custom TOOL_CALL labels)
        ├── NTTAgentLive                     [n3tx-agents]
        └── NTTChat                          [n3tx-agents]

Run.__ui__['methods']['execute']['renderer'] = 'ntx-stream-agent'  (generic, no custom subclass)

StreamActor.js — DELETED
ntx-run-panel.js — DELETED (replaced by ntx-run-item + generic ntx-stream-agent)
```

---

## Architecture Decisions (from design review)

### D1: Two-Phase Rendering — `prerender()` + `render()`

**Problem**: NTTMethod gates `render()` on `this.methodSchema` — nothing renders until schema loads. Components like NTTAgentLive have schema-independent structural UI (textarea, buttons, log area) that should appear immediately.

**Decision**: Add `prerender()` no-op hook to **Component** (base class). Called in `connectedCallback()` before schema loads. `render()` becomes the schema-aware enhancement pass, called after `definedCallback()`.

**Contract**:
- `prerender()` — Structural UI: DOM skeleton, event listeners, cached element refs. Called once on connect. Default: no-op on Component.
- `render()` — Schema-aware enhancements. Additive — NEVER wipes innerHTML from prerender(). Called after schema loads.
- NTTItem's existing skeleton rendering (`placeholder(size)`) moves into its `prerender()` override — unifying the pattern.

### D2: Stream Cancellation — `NTTStream.cancel()`

**Problem**: TX-based streaming has no cancellation mechanism. StreamActor had `streamClose()` which called `controller.abort()` on the fetch. After migration, there's no open HTTP connection to abort.

**Decision**: Dual-layer cancellation:
- **Client-side (immediate)**: `cancel()` sets an ignore flag. `STREAM()` handler checks it and silently drops incoming chunks. UI resets immediately.
- **Backend signal (protocol)**: `cancel()` also sends a cancel TX `{name: 'STREAM_CANCEL', target: entity.href, meta: {req: originalReqId}}`. Backend doesn't handle this yet — the TX defines the wire protocol for future implementation.
- **Auto-cancel**: `disconnectedCallback()` calls `this.cancel()` so streams don't orphan when components leave the DOM.

### D3: NTTAgentLive keeps `ref` attribute

**Problem**: NTTMethod uses `uuid` attribute. NTTAgentLive currently uses `ref="agents/1"` (slash-ref format). Renaming to `uuid` breaks consuming HTML and loses the ability to work with any entity type.

**Decision**: Keep `ref` attribute. Let Component's existing `ref` setter fire — it sends an ATTACH TX which registers the component as a watcher (useful for entity updates). NTTAgentLive extracts the uuid from ref lazily in `callMethod()` when needed for the TX target. Both resolution paths (Component's ref ATTACH + NTTMethod's uuid) fire without conflict.

### D4: NTTChat eliminates HTTP.post() fallback

**Problem**: NTTChat has a non-streaming fallback using `HTTP.post()` directly for methods without `stream: true`.

**Decision**: Use NTTMethod's standard `callMethod()` (which sends via `caller.call()`) for non-streaming methods. Override `_response_(data, tx)` to display the reply as a chat bubble. This works because `caller.call()` is already used by every NTTMethod in the framework. Eliminates the HTTP import entirely.

### D5: NTTChat sets `display="md"` to skip ResizeObserver

**Problem**: NTTChat is `position: fixed` — Component's ResizeObserver fires uselessly.

**Decision**: Set `display="md"` attribute. Component's ResizeObserver checks for forced display and skips (line 369 of Component.js: `if (Component.normalizeDisplay(this.getAttribute('display'))) return;`). Zero overhead, uses existing machinery.

### D6: NTTChat instance loading in `definedCallback()`

**Problem**: `#loadInstances()` needs `__tablename__` from schema. Currently fires in `#loadSchema()` callback.

**Decision**: Move to `definedCallback()`. Fires once when schema arrives — perfect trigger for a one-time data fetch. The fetch callback populates the already-rendered select element (which `prerender()` created). No guard needed.

### D7: Veille app decomposition — composition over monoliths

**Problem**: `ntx-grant-analyze` (766 lines) and `ntx-run-panel` are monolithic components that duplicate framework functionality: entity loading, field rendering, streaming dispatch, and schema resolution — all manually wired.

**Decision**: Decompose into framework compositions with app-level custom renderers:

| Monolith | Entity renderer | Method renderer |
|---|---|---|
| `ntx-grant-analyze` | `ntx-grant-item` (extends NTTItem) — custom grant card with score color coding, status pills, justification truncation | `ntx-grant-analyze` (extends NTTStreamAgent) — custom TOOL_CALL with friendly tool descriptions |
| `ntx-run-panel` | `ntx-run-item` (extends NTTItem) — custom run layout with execute controls | Generic `ntx-stream-agent` — no custom subclass needed |

Wired via `__ui__`:
```python
class Grant(ActorModel):
    __ui__ = {
        'renderer': {'item': 'ntx-grant-item'},
        'methods': {'analyze': {'renderer': 'ntx-grant-analyze'}},
        ...
    }

class Run(ActorModel):
    __ui__ = {
        'renderer': {'item': 'ntx-run-item'},
        'methods': {'execute': {'renderer': 'ntx-stream-agent'}},
        ...
    }
```

### D8: Shared rendering — leave duplicated

NTTStreamAgent, NTTAgentLive, and NTTChat share rendering helpers (`#addEntry()`, `#esc()`, `#scheduleRender()`, `#toolCards` Map, etc.). Leave duplicated for Phase 2. The rendering is similar but not identical — entries in a log, entries in a method card, chat bubbles. Let them evolve independently. If a clear shared abstraction emerges, extract it later.

---

## Wave Execution Plan

### Wave 1: Base Class Changes

Two independent edits — can be done in parallel.

#### 1a. Add `prerender()` to Component

**File**: `packages/n3tx-core/src/n3tx_core/static/core/Component.js`

Add no-op default method and call it from `connectedCallback()`:

```javascript
// Add method (near render(), ~line 441)
/**
 * Pre-schema structural UI. Called once from connectedCallback().
 * Override in subclasses to render DOM skeleton before schema loads.
 * Default: no-op.
 */
prerender() {}

// Edit connectedCallback() (~line 421)
connectedCallback() {
    // Apply forced display mode if set before connect
    const forced = Component.normalizeDisplay(this.getAttribute('display'));
    if (forced && forced !== this.#displayMode) {
      const old = this.#displayMode;
      this.#displayMode = forced;
      this.displayModeChanged(old, forced);
    }
    this.#startResizeObserver();
    this.prerender();  // ← ADD: structural UI before schema
}
```

Also migrate NTTItem's existing skeleton to `prerender()`:

**File**: `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`

Move the skeleton rendering from `connectedCallback()` into `prerender()`:

```javascript
// Current connectedCallback (~line 38):
connectedCallback() {
    super.connectedCallback();
    if (!this.schema?.__name__) {
      const size = this.displayMode;
      this.shadowRoot.innerHTML =
        `<div class="card skeleton" data-display="${size}">${this.placeholder(size)}</div>`;
    }
}

// After:
connectedCallback() {
    super.connectedCallback();  // Component.connectedCallback() now calls prerender()
}

prerender() {
    if (!this.schema?.__name__) {
      const size = this.displayMode;
      this.shadowRoot.innerHTML =
        `<div class="card skeleton" data-display="${size}">${this.placeholder(size)}</div>`;
    }
}
```

#### 1b. Add `cancel()` to NTTStream

**File**: `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js`

```javascript
export class NTTStream extends NTTMethod {

    // ── State ──
    #streaming = false;
    #textBuf = '';
    #boundHandler = null;
    #cancelled = false;    // ← ADD: ignore flag for cancelled streams
    #streamReqId = null;   // ← ADD: correlation ID for cancel TX

    // ── STREAM inbox handler ──
    STREAM(data, tx) {
        if (this.#cancelled) return;  // ← ADD: silently drop chunks after cancel
        if (tx?.meta?.error)      return this.STREAM_ERROR(data);
        if (tx?.meta?.stream_end) return this.STREAM_END(data);

        const name = data?.name?.toUpperCase();
        if (name && typeof this[name] === 'function') {
            this[name](data.data, data.meta);
        } else {
            this.TEXT(data);
        }
    }

    // ── callMethod override ──
    callMethod() {
        const target = this.ntt?.href || this.proto?.href;
        if (!target) return;

        this.#reset();
        this.#streaming = true;
        this.#cancelled = false;   // ← ADD: clear cancel flag on new stream
        this.#renderOutput();

        const name = this.method;
        if (this.#boundHandler && this.#boundHandler !== name) {
            delete this[this.#boundHandler];
        }
        this[name] = (data, tx) => this.STREAM(data, tx);
        this.#boundHandler = name;

        // Generate correlation ID for cancel tracking
        this.#streamReqId = `${this.addr}-${Date.now()}`;

        this.send(new TX({
            name: this.method,
            source: this.addr,
            target: target,
            data: { ...this.value },
            meta: { stream: true, req: this.#streamReqId },
        }));
    }

    /**
     * Cancel the active stream.
     * - Immediately: sets ignore flag, drops incoming chunks, resets UI state.
     * - Protocol: sends STREAM_CANCEL TX for future backend support.
     */
    cancel() {
        if (!this.#streaming) return;
        this.#cancelled = true;
        this.#streaming = false;

        // Send cancel TX (backend doesn't handle yet — defines the wire protocol)
        const target = this.ntt?.href || this.proto?.href;
        if (target && this.#streamReqId) {
            this.send(new TX({
                name: 'STREAM_CANCEL',
                source: this.addr,
                target: target,
                meta: { req: this.#streamReqId },
            }));
        }

        this.STREAM_END({});
    }

    // ── disconnectedCallback ──
    disconnectedCallback() {
        this.cancel();  // ← Auto-cancel on disconnect
        super.disconnectedCallback();
    }

    // ... rest unchanged
}
```

---

### Wave 2: Framework Component Migrations (parallel)

#### 2a. Migrate NTTAgentLive to extend NTTStream

**File**: `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`

**Attributes**: Keep `model`, `ref`, `method` (default `'agentic_stream'`). `ref` stays — Component's ref setter fires ATTACH (useful). UUID extracted lazily from ref in `callMethod()`.

**Import change**:
```javascript
// Before:
import { StreamActor } from './StreamActor.js';
import { config } from '../config.js';
import { NTT } from '../core/NTT.js';

// After:
import { NTTStream } from './ntx-stream.js';
import TX from '../core/TX.js';
```

**Class declaration**:
```javascript
// Before:
class NTTAgentLive extends StreamActor(HTMLElement) {

// After:
class NTTAgentLive extends NTTStream {
```

**Remove private fields**: `#model`, `#ref`, `#method`, `#schema`, `#tablename` — all provided by NTTMethod/Component (`this.model`, `this.method`, `this.proto`, `this.schema`).

**Keep private fields**: `#toolCards`, `#els`, `#textBuf`, `#textRendered`, `#textTimer`, `#thinkBuf`, `#thinkRendered`, `#thinkTimer`.

**prerender()** — structural UI (textarea, log, buttons, event listeners):
```javascript
prerender() {
    this.shadowRoot.innerHTML = `
        <style>${NTTAgentLive.styles}</style>
        <div class="live-panel">
            <div class="live-header">
                <span class="live-title">${this.getAttribute('model') || ''} &middot; Live</span>
                <span class="live-status" id="status">idle</span>
            </div>
            <div class="live-input">
                <textarea placeholder="Enter task..." rows="2"></textarea>
                <button class="run-btn">Run</button>
            </div>
            <div class="live-log" id="log"></div>
            <div class="live-footer" id="footer"></div>
        </div>`;

    this.#cacheEls();
    this.#bindListeners();
    initJsonToggle(this.shadowRoot);

    // Click-to-expand/collapse on collapsible entries
    this.#els.log.addEventListener('click', (e) => {
        if (e.target.closest('.jt-toggle') || e.target.closest('a')) return;
        const entry = e.target.closest('.entry.collapsible');
        if (entry) entry.classList.toggle('expanded');
    });
}
```

**render()** — schema-aware enhancements (additive, never wipes innerHTML):
```javascript
render() {
    // Update title with resolved model name (may differ from attribute)
    if (this.#els && this.model) {
        const title = this.shadowRoot.querySelector('.live-title');
        if (title) title.textContent = `${this.model} · Live`;
    }
}
```

**connectedCallback()**:
```javascript
connectedCallback() {
    if (!this.getAttribute('method')) this.setAttribute('method', 'agentic_stream');
    super.connectedCallback();  // Component.connectedCallback() → prerender() + NTTMethod.load()
    this.addEventListener('click', (e) => e.stopPropagation());
}
```

**callMethod()** — extracts uuid from ref lazily:
```javascript
callMethod() {
    const task = this.#els.textarea.value.trim();
    if (!task) return;

    // Extract uuid from ref attribute if needed
    const ref = this.getAttribute('ref') || '';
    if (ref && !this.uuid) {
        const id = ref.includes('/') ? ref.split('/').pop() : ref;
        this.uuid = id;
        // Resolve entity for TX target
        const { NTT } = await import('../core/NTT.js');
        this.ntt = NTT.get(this.model + '/' + id);
    }

    this.#els.textarea.value = '';
    this.#reset();
    this.#els.status.textContent = 'running';
    this.#els.status.className = 'live-status running';
    this.#els.runBtn.disabled = true;
    this.#addEntry('task', `Task: ${task}`);

    this.value = { task };
    super.callMethod();  // NTTStream sends TX with meta: {stream: true}
}
```

**disconnectedCallback()**:
```javascript
disconnectedCallback() {
    super.disconnectedCallback();  // NTTStream.cancel() + Component cleanup
    clearTimeout(this.#textTimer);
    clearTimeout(this.#thinkTimer);
}
```

**UPPERCASE handlers**: UNCHANGED — `THINKING()`, `TOOL_CALL()`, `TOOL_RESULT()`, `TEXT()`, `DONE()`, `STREAM_END()`, `STREAM_ERROR()` stay exactly as they are. They get called by NTTStream's `STREAM()` handler instead of StreamActor's `#dispatch()`.

**Private helpers**: UNCHANGED — `#addEntry()`, `#setThinking()`, `#scheduleRender()`, `#renderMd()`, `#flushRender()`, `#scrollToBottom()`, `#esc()`, `#cacheEls()`, `#bindListeners()`.

**Static styles**: UNCHANGED.

**Removed code**:
- `#loadSchema()` — NTTMethod `load()` handles this
- `#run()` — replaced by `callMethod()` override
- `StreamActor` import
- `HTTP.stream()` / `streamClose()` calls
- Manual `NTT.attach()` / `attachShadow()`
- `#model`, `#ref`, `#method`, `#schema`, `#tablename` private fields

**HTML updates** — `examples/pygentic/static/index.html`:
No HTML changes needed — `ref="agents/1"` stays, Component's ref setter handles it.

---

#### 2b. Migrate NTTChat to extend NTTStream

**File**: `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`

**Attributes**: `model`, `method`, `display="md"` (forced — skips ResizeObserver for fixed-position panel).

**Import change**:
```javascript
// Before:
import { StreamActor } from './StreamActor.js';
import HTTP from '../core/transport/HTTP.js';
import { config } from '../config.js';
import { NTT } from '../core/NTT.js';

// After:
import { NTTStream } from './ntx-stream.js';
import { NTT } from '../core/NTT.js';
import HTTP from '../core/transport/HTTP.js';  // Keep for #loadInstances() — one-time GET
```

**Class declaration**:
```javascript
// Before:
class NTTChat extends StreamActor(HTMLElement) {

// After:
class NTTChat extends NTTStream {
```

**Remove private fields**: `#model`, `#method`, `#schema`, `#tablename` — provided by NTTMethod.

**Keep private fields**: `#items`, `#isStream`, `#isStreaming`, `#selectedId`, `#messages`, `#open`, `#els`, `#toolCards`, `#currentMsgEl`, `#currentTextEl`, `#currentText`.

**prerender()** — structural UI (floating tab + panel + event listeners):
```javascript
prerender() {
    this.shadowRoot.innerHTML = `
        <style>${NTTChat.styles}</style>
        <button class="chat-tab" aria-label="Open chat">${ICON_CHAT}</button>
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">${this.getAttribute('model') || ''} &middot; ${this.getAttribute('method') || ''}</span>
                <button class="panel-close" aria-label="Close">${ICON_CLOSE}</button>
            </div>
            <div class="panel-controls">
                <select class="instance-select"><option value="">Loading...</option></select>
            </div>
            <div class="chat-messages"></div>
            <div class="chat-input">
                <textarea placeholder="Type your message..." rows="2"></textarea>
                <button class="send-btn" aria-label="Send">${ICON_SEND}</button>
            </div>
        </div>`;

    this.#cacheEls();
    this.#bindListeners();
}
```

**render()** — schema-aware enhancements (additive):
```javascript
render() {
    // Update title with resolved model/method names
    if (this.#els) {
        const title = this.shadowRoot.querySelector('.panel-title');
        if (title) title.textContent = `${this.model} · ${this.method}`;
    }
}
```

**connectedCallback()**:
```javascript
connectedCallback() {
    if (!this.getAttribute('display')) this.setAttribute('display', 'md');  // Skip ResizeObserver
    super.connectedCallback();  // Component.connectedCallback() → prerender() + NTTMethod.load()
}
```

**definedCallback()** — fires once when schema arrives:
```javascript
definedCallback() {
    super.definedCallback();
    this.#isStream = !!this.methodSchema?.stream;
    if (!this.uuid) this.#loadInstances();
}
```

**callMethod()** — streaming via TX, non-streaming via inherited NTTMethod path:
```javascript
callMethod() {
    const task = this.#els.textarea.value.trim();
    if (!task || !this.#selectedId) return;

    this.#appendMsg('user', task);
    this.#els.textarea.value = '';

    // Set uuid + entity for TX targeting
    this.uuid = this.#selectedId;
    this.ntt = NTT.get(this.model + '/' + this.#selectedId);
    this.value = { task };

    if (this.#isStream) {
        this.#isStreaming = true;
        this.#els.send.disabled = true;
        this.#currentText = '';
        this.#currentMsgEl = this.#appendMsg('assistant', '');
        this.#currentTextEl = this.#currentMsgEl.querySelector('.msg-text');
        this.#toolCards = new Map();
        super.callMethod();  // NTTStream sends TX with meta: {stream: true}
    } else {
        // Non-streaming: use NTTMethod's standard callMethod path
        // Response arrives at _response_() override below
        this.#els.send.disabled = true;
        const caller = this.ntt || this.proto;
        if (caller?.call) {
            caller.call(this.method, { ...this.value }, { inbox: '_response_' });
        }
    }
}
```

**_response_()** — replaces HTTP.post() fallback for non-streaming:
```javascript
_response_(data, tx) {
    this.#els.send.disabled = false;
    const answer = data?.answer || data?.result || JSON.stringify(data);
    this.#appendMsg('assistant', answer);
}
```

**UPPERCASE handlers**: UNCHANGED — `THINKING()`, `TOOL_CALL()`, `TOOL_RESULT()`, `TEXT()`, `DONE()`, `STREAM_END()`, `STREAM_ERROR()`.

**Private helpers**: UNCHANGED — `#appendMsg()`, `#toggle()`, `#scrollToBottom()`, `#esc()`, `#cacheEls()`, `#bindListeners()`.

**Remove**: `#loadSchema()`, `#sendPost()`, `#clear()` (replace with `this.cancel()`), `StreamActor` import, `this.stream()` / `this.streamClose()` calls, manual `NTT.attach()` / `attachShadow()`.

**#loadInstances()** — stays largely the same, uses HTTP.get():
```javascript
#loadInstances() {
    const tablename = this.schema?.__tablename__ || this.model?.toLowerCase() + 's';
    const url = `/api/${tablename}`;
    HTTP.get(url, (resp) => {
        this.#items = resp.data || resp || [];
        const sel = this.#els.select;
        sel.innerHTML = this.#items.map(item => {
            const label = item.name || item.title || `#${item.id}`;
            return `<option value="${item.id}">${label}</option>`;
        }).join('');
        if (this.#items.length) this.#selectedId = this.#items[0].id;
        sel.addEventListener('change', () => { this.#selectedId = sel.value; });
    }, (err) => {
        this.#els.select.innerHTML = '<option value="">No instances</option>';
    });
}
```

**Static styles**: UNCHANGED.

**HTML updates**: No changes to consuming HTML — attributes stay the same.

---

### Wave 3: Veille App Decomposition (parallel)

#### 3a. Create `ntx-grant-item` — custom Grant card renderer

**File**: `apps/veille/static/components/ntx-grant-item.js` (NEW)

Extends NTTItem. Renders grant-specific fields: score with color coding, status pill, funder, deadline, amount, justification truncation, URL link.

Extracts the grant info rendering from current `ntx-grant-analyze.js` lines 139-187 (`#renderGrantInfo()`, `#statusClass()`, `#scoreClass()`) and lines 447-616 (grant info CSS).

```javascript
import { NTTItem } from './ntx-item.js';

class NTXGrantItem extends NTTItem {

    // Override render to provide grant-specific card layout
    render() {
        const g = this.value;
        if (!g || !g.id) return super.render();  // Fallback to generic

        const score = g.score != null ? `${Math.round(g.score * 100)}%` : 'N/A';
        // ... grant-specific card HTML with score color, status pill, etc.
        // Extracted from ntx-grant-analyze.js #renderGrantInfo()
    }

    // Grant-specific helpers
    #statusClass(status) { /* admissible/inadmissible/new/analyzing/error */ }
    #scoreClass(score)   { /* score-high/score-mid/score-low */ }

    static styles = `/* Extracted from ntx-grant-analyze.js — grant info CSS */`;
}

customElements.define('ntx-grant-item', NTXGrantItem);
export { NTXGrantItem };
```

**Wire via model** — `apps/veille/models/grant.py`:
```python
class Grant(ActorModel):
    __ui__ = {
        # ... existing config ...
        'renderer': {'item': 'ntx-grant-item'},
        'methods': {'analyze': {'renderer': 'ntx-grant-analyze'}},
    }
```

**Import** — `apps/veille/static/index.html`:
```html
<link rel="modulepreload" href="./components/ntx-grant-item.js">
<!-- in script: -->
import './components/ntx-grant-item.js';
```

#### 3b. Rewrite `ntx-grant-analyze` to extend NTTStreamAgent

**File**: `apps/veille/static/components/ntx-grant-analyze.js` (REWRITE)

Before: 766-line monolith extending `StreamActor(HTMLElement)` with grant info card + streaming log + manual schema/entity loading.

After: Thin subclass of NTTStreamAgent. Overrides `TOOL_CALL()` for friendly tool descriptions. Overrides `STREAM_END()` to trigger entity refresh. All entry-based rendering, text buffering, thinking animation, tool card tracking inherited from NTTStreamAgent.

```javascript
import { NTTStreamAgent } from './ntx-stream-agent.js';

class NTXGrantAnalyze extends NTTStreamAgent {

    // Custom tool descriptions for grant analysis context
    TOOL_CALL(data, meta) {
        const tool = data?.tool || '';
        // Map tool names to friendly descriptions
        if (tool.includes('organizations_read')) {
            data = { ...data, tool: 'Reading organisation profile' };
        } else if (tool.includes('grants_update')) {
            data = { ...data, tool: `Saving analysis results` };
        } else if (tool.includes('scrape')) {
            data = { ...data, tool: `Fetching: ${data.args?.url || ''}` };
        }
        // Delegate to NTTStreamAgent's TOOL_CALL for rendering
        super.TOOL_CALL(data, meta);
    }

    // Refresh parent entity on stream completion
    STREAM_END(data) {
        super.STREAM_END(data);
        // Entity pull already happens in NTTStream.STREAM_END via this.ntt.pull()
        // Grant card (ntx-grant-item) will re-render with updated score/status
    }
}

customElements.define('ntx-grant-analyze', NTXGrantAnalyze);
export { NTXGrantAnalyze };
```

**Size reduction**: ~766 lines → ~40 lines. All rendering, buffering, dispatch, lifecycle inherited.

#### 3c. Create `ntx-run-item` — custom Run layout renderer

**File**: `apps/veille/static/components/ntx-run-item.js` (NEW)

Extends NTTItem. Renders run-specific layout with execution controls. The `execute` method is a streaming instance method on Run with one optional parameter (`adhoc_url`), rendered by the generic `ntx-stream-agent` via `__ui__['methods']`.

```javascript
import { NTTItem } from './ntx-item.js';

class NTXRunItem extends NTTItem {

    // Override render for run-specific layout
    render() {
        const run = this.value;
        if (!run || !run.id) return super.render();
        // Custom run card layout
        // The execute method renders automatically as ntx-stream-agent
        // because of Run.__ui__['methods']['execute']['renderer']
    }

    static styles = `/* Run-specific card styles */`;
}

customElements.define('ntx-run-item', NTXRunItem);
export { NTXRunItem };
```

**Wire via model** — `apps/veille/models/run.py`:
```python
class Run(ActorModel):
    __ui__ = {
        # ... existing config ...
        'renderer': {'item': 'ntx-run-item'},
        'methods': {'execute': {'renderer': 'ntx-stream-agent'}},
    }
```

**Import** — `apps/veille/static/index.html`:
```html
<link rel="modulepreload" href="./components/ntx-run-item.js">
<!-- in script: -->
import './components/ntx-run-item.js';
```

---

### Wave 4: Cleanup

#### 4a. Delete `ntx-run-panel.js`

**File**: `apps/veille/static/components/ntx-run-panel.js` — DELETE

Replaced by `ntx-run-item` + generic `ntx-stream-agent`. Remove all references:
- `apps/veille/static/index.html`: remove import, modulepreload, and `<ntx-run-panel>` element
- Update hash routing in index.html to use new component composition

#### 4b. Delete `StreamActor.js`

**File**: `packages/n3tx-agents/src/n3tx_agents/static/components/StreamActor.js` — DELETE

Verify zero remaining consumers:
```bash
grep -r "StreamActor" packages/n3tx-agents/src/
grep -r "StreamActor" packages/n3tx-ui/src/
grep -r "StreamActor" apps/
grep -r "StreamActor" examples/
```

Remove any re-exports or references in `n3tx-agents` package.

#### 4c. Update HTML files

**`examples/pygentic/static/index.html`**: Update imports if needed (ntx-agent-live import path may change).

**`examples/grants/static/index.html`**: ntx-chat — no HTML changes needed.

**`examples/actors/static/index.html`**: ntx-chat — no HTML changes needed.

**`apps/veille/static/index.html`**:
- Remove ntx-run-panel references
- Add ntx-grant-item, ntx-run-item imports
- Update hash routing for `#analyze/{id}` to work with new composition

#### 4d. Update documentation

- `docs/AGENTS.md` — Remove StreamActor section, document NTTStream hierarchy
- `packages/n3tx-agents/docs/` — Update component docs
- `CLAUDE.md` — Update hierarchy diagram, streaming section, remove "StreamActor Mixin" references
- `FRONTEND.md` — Update component hierarchy, add prerender() lifecycle docs

---

## Migration Checklist

### Wave 1: Base Classes
- [ ] Add `prerender()` no-op to Component
- [ ] Call `this.prerender()` in Component's `connectedCallback()`
- [ ] Migrate NTTItem skeleton to `prerender()` override
- [ ] Add `#cancelled`, `#streamReqId` state to NTTStream
- [ ] Add `cancel()` method to NTTStream
- [ ] Add cancel check to `STREAM()` handler
- [ ] Add `this.cancel()` to NTTStream `disconnectedCallback()`
- [ ] Store `req` correlation ID in `callMethod()` TX meta

### Wave 2: Framework Components
#### NTTAgentLive
- [ ] Change `extends StreamActor(HTMLElement)` → `extends NTTStream`
- [ ] Update imports (remove StreamActor, add NTTStream + TX)
- [ ] Remove `#model`, `#ref`, `#method`, `#schema`, `#tablename` private fields
- [ ] Remove `#loadSchema()`, `#run()`, `attachShadow()`
- [ ] Add `prerender()` — structural UI (textarea + log + footer + event listeners)
- [ ] Add `render()` — additive schema-aware updates (title)
- [ ] Add `callMethod()` — extract uuid from ref, set value, call super
- [ ] Update `connectedCallback()` — set default method, call super
- [ ] Update `disconnectedCallback()` — call super (handles cancel), clear timers
- [ ] Keep all UPPERCASE handlers unchanged
- [ ] Keep all private rendering helpers unchanged
- [ ] Keep `ref` attribute — no HTML changes needed

#### NTTChat
- [ ] Change `extends StreamActor(HTMLElement)` → `extends NTTStream`
- [ ] Update imports (remove StreamActor, add NTTStream; keep HTTP for loadInstances)
- [ ] Remove `#model`, `#method`, `#schema`, `#tablename` private fields
- [ ] Remove `#loadSchema()`, `#sendPost()`, `attachShadow()`
- [ ] Add `prerender()` — floating tab + panel + event listeners
- [ ] Add `render()` — additive title update
- [ ] Add `connectedCallback()` — set `display="md"`, call super
- [ ] Add `definedCallback()` — detect stream support, load instances
- [ ] Add `callMethod()` — set uuid from selector, branch stream/non-stream
- [ ] Add `_response_()` — display non-streaming reply as chat bubble
- [ ] Replace `#clear()` internals with `this.cancel()`
- [ ] Keep all UPPERCASE handlers unchanged
- [ ] Keep floating panel CSS unchanged

### Wave 3: App Components
#### ntx-grant-item (NEW)
- [ ] Create `apps/veille/static/components/ntx-grant-item.js`
- [ ] Extract grant info rendering from ntx-grant-analyze.js
- [ ] Extract grant info CSS from ntx-grant-analyze.js
- [ ] Wire via `Grant.__ui__['renderer']['item'] = 'ntx-grant-item'`
- [ ] Add import + modulepreload to index.html

#### ntx-grant-analyze (REWRITE)
- [ ] Rewrite to extend NTTStreamAgent
- [ ] Override `TOOL_CALL()` for friendly tool descriptions
- [ ] Override `STREAM_END()` if extra refresh logic needed
- [ ] Wire via `Grant.__ui__['methods']['analyze']['renderer'] = 'ntx-grant-analyze'`
- [ ] Verify ~40 lines vs current 766

#### ntx-run-item (NEW)
- [ ] Create `apps/veille/static/components/ntx-run-item.js`
- [ ] Custom run layout with execute controls
- [ ] Wire via `Run.__ui__['renderer']['item'] = 'ntx-run-item'`
- [ ] Wire via `Run.__ui__['methods']['execute']['renderer'] = 'ntx-stream-agent'`
- [ ] Add import + modulepreload to index.html

### Wave 4: Cleanup
- [ ] Delete `ntx-run-panel.js`
- [ ] Delete `StreamActor.js`
- [ ] Verify `grep -r "StreamActor"` returns zero hits
- [ ] Update index.html (remove old refs, add new imports, update routing)
- [ ] Update docs (AGENTS.md, CLAUDE.md, FRONTEND.md, n3tx-agents/docs/)

---

## Verification

1. **Component.prerender()**: Any component extending Component can override `prerender()` and see structural UI before schema loads. NTTItem shows skeleton bones immediately.
2. **NTTStream.cancel()**: Call `cancel()` mid-stream → UI resets, further chunks silently dropped, cancel TX sent.
3. **NTTAgentLive**: `<ntx-agent-live model="AgentActor" ref="agents/1">` → structural UI appears immediately, schema loads, enter task, click Run → THINKING/TOOL_CALL/TEXT/DONE render in activity log. Token stats in footer.
4. **NTTChat**: Click chat tab → panel opens. Select instance → send message. Streaming response renders progressively. Non-streaming methods respond via `_response_()`. `display="md"` prevents ResizeObserver overhead.
5. **ntx-grant-item**: Grant cards render with score color coding, status pills, justification. Schema-driven via `__ui__['renderer']`.
6. **ntx-grant-analyze**: Inside grant detail, analyze method renders as NTTStreamAgent with friendly tool labels. ~40 lines vs 766.
7. **ntx-run-item**: Run cards render with custom layout. Execute method renders as generic ntx-stream-agent. adhoc_url input from method schema parameters.
8. **Backward compat**: `<ntx-stream>` still works for simple streaming. `<ntx-stream-agent>` still works for agent methods. `ref` attribute still works on ntx-agent-live.
9. **No StreamActor references**: `grep -r "StreamActor"` returns zero hits outside of git history and .traces/.planning docs.
10. **No ntx-run-panel references**: Fully replaced by ntx-run-item + ntx-stream-agent composition.
