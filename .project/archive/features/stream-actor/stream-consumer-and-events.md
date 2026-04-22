# Plan: Schema-Declared Stream Events + StreamActor Mixin

## Context

The agentic streaming stack has a display bug: Level 3 (actor routing) wraps every stream chunk in a `TX(name='STREAM', data={name:'text', ...})` envelope. `_sse_from_stream` serializes the full envelope to SSE. Frontend components do `switch(chunk.name)` — see `'STREAM'` — no matching case — nothing renders.

**TX nesting is correct.** The full envelope carries routing context for multi-hop actor systems. The backend is not broken — the frontend is. The fix is purely frontend: teach components to unwrap the STREAM envelope and dispatch by the inner event name.

Alongside the fix, we're introducing:
- **Schema-declared stream events** via `events=` on `@expose_route`, using non-storable ProtoModel subclasses for type safety and schema visibility
- **`StreamActor` mixin** that unwraps the TX envelope and dispatches to UPPERCASE handler methods (actor inbox pattern)

TXStream (multi-listener EventTarget) is deferred as a future improvement.

---

## SSE Wire Format (unchanged)

Understanding what each routing level sends — the StreamActor mixin must handle both.

**Level 3** (actor routing via `_sse_from_stream` — `asdict(chunk)`):
```
event: chunk
data: {"name":"STREAM","source":"...","target":"...","data":{"name":"text","data":{"text":"hello"},"meta":{...}},"meta":{...},"timestamp":"...","uuid":"..."}

event: done
data: {"name":"STREAM",...,"meta":{"stream_end":true,...}}
```

**Level 1/2** (direct routes — generator yields TX-aligned dicts):
```
event: chunk
data: {"name":"text","data":{"text":"hello"},"meta":{...}}

event: done
data: {}
```

**No backend changes.** Both formats are valid. The StreamActor mixin handles both by unwrapping one level of STREAM envelope when present.

---

## Changes

### 1. Stream Event Models — `packages/n3tx-agents/src/n3tx_agents/actor.py`

Define non-storable ProtoModel subclasses at the top of the file. One class per event type. Export them so developers can reuse or extend.

```python
from n3tx_core.models.proto_model import ProtoModel

class TextChunk(ProtoModel):
    text: str = Field(default='')

class ToolCall(ProtoModel):
    tool: str = Field(default='')
    args: dict = Field(default={})
    call_id: str = Field(default='')

class ToolResult(ProtoModel):
    tool: str = Field(default='')
    result: str = Field(default='')
    call_id: str = Field(default='')

class ThinkingChunk(ProtoModel):
    text: str = Field(default='')

class DoneChunk(ProtoModel):
    answer: str = Field(default='')
    usage: dict = Field(default={})
    tool_calls: int = Field(default=0)
```

Update `agentic_stream` decorator:
```python
@expose_route('/agentic_stream', methods=['POST'], stream=True,
              events={
                  'text': TextChunk, 'tool_call': ToolCall,
                  'tool_result': ToolResult, 'thinking': ThinkingChunk,
                  'done': DoneChunk,
              })
async def agentic_stream(self, task: str, **kwargs): ...
```

### 2. `@expose_route` — `packages/n3tx-core/src/n3tx_core/utils/decorators.py`

Add `events=None` parameter. Store in `__endpoint__`:
```python
def expose_route(route, methods=["POST"], access=None, stream=False, events=None):
    ...
    wrapper.__endpoint__ = {
        'route': route, 'methods': methods,
        'access': access, 'stream': stream, 'events': events,
    }
```

### 3. Schema Pipeline — `packages/n3tx-core/src/n3tx_core/models/proto_model.py`

In `__n3tx_methods_json_signature__`, after the `stream` flag injection:
```python
if endpoint_info.get('events'):
    method_entry['events'] = {
        name: cls.model_json_schema()
        for name, cls in endpoint_info['events'].items()
    }
```

This produces per-event inline JSON Schema visible to the frontend via `GET /AgentActor`.

### 4. `HTTP.stream()` done guard — `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js`

Add single-done guard to prevent double `onDone` callback when the stream body closes after `event: done` has already been processed:

```javascript
// Line ~368: add guard
let _done = false;

function pump() {
    reader.read().then(({ done, value }) => {
        if (done) { if (!_done) onDone({}); return; }
        ...
        // Line ~383: existing done branch
        else if (eventType === 'done') { _done = true; onDone(parsed); }
        ...
    });
}
```

No other changes to HTTP.js. `onChunk` signature stays `(parsed)` — the mixin reads event names from the data, not from SSE event types.

### 5. `StreamActor` mixin — NEW `packages/n3tx-agents/src/n3tx_agents/static/components/StreamActor.js`

Mixin function that adds stream dispatch to any base class. Unwraps the STREAM envelope, dispatches to UPPERCASE handler methods — the actor inbox pattern applied to frontend components.

**UPPERCASE convention**: All TX message handlers are UPPERCASE. This creates a clear namespace: uppercase = inbox (called by the framework in response to TX events), lowercase/camelCase = internal component logic. Same pattern as backend actor `handler_*` methods, adapted for JS conventions.

```javascript
import HTTP from '../core/transport/HTTP.js';

export const StreamActor = (Base) => class extends Base {
    #handle = null;

    /**
     * Open a streaming connection. Chunks are dispatched to UPPERCASE handlers.
     * @param {string} url - SSE endpoint URL
     * @param {object} payload - POST body
     */
    stream(url, payload = {}) {
        this.#handle?.cancel();
        this.#handle = HTTP.stream(url, payload,
            (data) => this.#dispatch(data),
            (data) => { this.#handle = null; this.STREAM_END?.(data); },
            (err)  => { this.#handle = null; this.STREAM_ERROR?.(err); },
        );
    }

    /**
     * Cancel an active stream.
     */
    streamClose() {
        this.#handle?.cancel();
        this.#handle = null;
    }

    /**
     * Unwrap STREAM envelope and dispatch to UPPERCASE handler.
     *
     * Level 3: {name:'STREAM', data:{name:'text', data:{text:'hello'}}}
     *   → unwrap → inner = {name:'text', data:{text:'hello'}}
     *   → this.TEXT({text:'hello'})
     *
     * Level 1/2: {name:'text', data:{text:'hello'}}
     *   → no unwrap needed
     *   → this.TEXT({text:'hello'})
     */
    #dispatch(data) {
        let inner = data;
        if (inner?.name === 'STREAM') inner = inner.data;

        const name = inner?.name?.toUpperCase();
        if (name && typeof this[name] === 'function') {
            this[name](inner.data, inner.meta);
        }
    }

    /**
     * Schema-aware validation: warn if declared events have no handler.
     * Call after schema loads.
     */
    _validateStreamHandlers(schema, methodName) {
        const events = schema?.methods?.[methodName]?.events ?? {};
        for (const name of Object.keys(events)) {
            if (typeof this[name.toUpperCase()] !== 'function') {
                console.warn(`[${this.tagName}] No handler for stream event '${name.toUpperCase()}'`);
            }
        }
    }
};
```

### 6. Refactor `ntx-agent-live.js` — `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`

- `extends StreamActor(HTMLElement)` (import from `./StreamActor.js`)
- Replace all `_` private fields with `#` (`#schema`, `#tablename`, `#toolCards`, `#els`)
- Replace `_run()` body: calls `this.stream(url, {task})` instead of `HTTP.stream()`
- Replace `_onChunk` switch with UPPERCASE handler methods:
  ```javascript
  THINKING(data, meta)    { this.#setThinking(true); }
  TOOL_CALL(data, meta)   { this.#setThinking(false); /* render card */ }
  TOOL_RESULT(data, meta) { /* complete card */ }
  TEXT(data, meta)         { this.#appendText(data.text); }
  DONE(data, meta)        { this.#showFooter(data); }
  STREAM_END(data)        { this.#onStreamEnd(); }
  STREAM_ERROR(err)       { this.#onStreamError(err); }
  ```
- Add `_validateStreamHandlers(schema, 'agentic_stream')` in `_loadSchema()` callback
- `disconnectedCallback()` calls `this.streamClose()`

### 7. Refactor `ntx-chat.js` — `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`

- `extends StreamActor(HTMLElement)` (import from `./StreamActor.js`)
- Replace all `_` private fields with `#` (`#items`, `#schema`, `#tablename`, `#isStreaming`, `#selectedId`, `#messages`, `#open`, `#els`, `#toolCards`, `#currentMsgEl`, `#currentTextEl`, `#currentText`)
- Replace `_sendStream()` body: calls `this.stream(url, payload)` instead of `HTTP.stream()`
- Replace inline `onChunk` switch with UPPERCASE handler methods:
  ```javascript
  THINKING(data, meta)    { /* add thinking indicator to current msg */ }
  TOOL_CALL(data, meta)   { /* remove thinking, add tool card */ }
  TOOL_RESULT(data, meta) { /* complete tool card */ }
  TEXT(data, meta)         { /* append text progressively */ }
  DONE(data, meta)        { /* fill answer if empty, show stats */ }
  STREAM_END(data)        { /* cleanup: enable send, remove cursor */ }
  STREAM_ERROR(err)       { /* cleanup + error message */ }
  ```
- Chat-specific state (`#currentMsgEl`, `#currentTextEl`, `#currentText`) set in `_send()` before calling `this.stream()`, read by UPPERCASE handlers
- `disconnectedCallback()` calls `this.streamClose()`

### 8. Update `index.html` preload list — `examples/pygentic/static/index.html`

Add `StreamActor.js` modulepreload before `ntx-agent-live.js` and `ntx-chat.js`:
```html
<link rel="modulepreload" href="./components/StreamActor.js">
```

### 9. Tests

**Update existing SSE tests** — `examples/pygentic/tests/test_streaming_display.py`

The 3 existing tests validate the SSE wire format. Since the wire format is unchanged (STREAM envelope stays), update them to validate the correct structure:
- `test_agentic_stream_chunks_have_name_at_top_level` — assert STREAM chunks carry inner events at `data.name` (i.e., `chunk['data']['name']` is `'text'`, `'done'`, etc.)
- `test_agentic_stream_text_chunk_has_data_with_text_key` — assert text is accessible at `chunk['data']['data']['text']` (the inner TX-aligned dict path)
- `test_agentic_stream_done_chunk_carries_answer` — assert done data is at `chunk['data']['data']['answer']`

**Add schema events test** — new test class:
```python
class TestStreamEventSchema:
    def test_agentic_stream_method_has_events_in_schema(self, client):
        schema = client.get('/AgentActor').json()
        events = schema['methods']['agentic_stream'].get('events', {})
        assert set(events.keys()) == {'text', 'tool_call', 'tool_result', 'thinking', 'done'}
        assert 'properties' in events['text']
        assert 'text' in events['text']['properties']
```

---

## Critical Files

| File | Change |
|------|--------|
| `packages/n3tx-agents/src/n3tx_agents/actor.py` | Add event models + `events=` on `agentic_stream` |
| `packages/n3tx-core/src/n3tx_core/utils/decorators.py` | Add `events=None` param to `expose_route` |
| `packages/n3tx-core/src/n3tx_core/models/proto_model.py` | Inject `events` into method schema |
| `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js` | Add done guard (lines ~370–383) |
| `packages/n3tx-agents/src/n3tx_agents/static/components/StreamActor.js` | **NEW** mixin |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` | Extend StreamActor; UPPERCASE handlers; `#` fields |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js` | Extend StreamActor; UPPERCASE handlers; `#` fields |
| `examples/pygentic/static/index.html` | Add StreamActor.js modulepreload |
| `examples/pygentic/tests/test_streaming_display.py` | Update + extend tests |

**Not modified:**
| File | Why |
|------|-----|
| `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` | SSE wire format unchanged — full TX envelope is correct |
| `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` | Level 1/2 SSE already correct — passes TX-aligned dicts through |

---

## Reusable Patterns

- **UPPERCASE inbox convention**: TX handler methods are UPPERCASE on components, matching backend actor `handler_*` pattern. Lowercase = internal, uppercase = message inbox.
- **Mixin function pattern**: `StreamActor(Base)` — composable, works with any base class (`HTMLElement`, `NTTElement`, future bases).
- **STREAM envelope unwrap**: Single `if (inner?.name === 'STREAM') inner = inner.data` — handles Level 3 wrapping transparently, passes Level 1/2 through unchanged.
- `NTT.attach(model, callback)` — existing schema subscription, reused for `_validateStreamHandlers()`.

---

## Verification

```bash
# 1. Run the SSE + schema tests
cd /workspace && python3 -m pytest examples/pygentic/tests/test_streaming_display.py -v

# 2. Run full pygentic test suite — no regressions
cd /workspace && python3 -m pytest examples/pygentic/tests/ -v

# 3. Run core tests — no regressions
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/ -v

# 4. Run actor tests
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/ -v

# 5. Run agent tests
cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/ -v

# 6. Manual end-to-end: start server, open browser, send message via ntx-agent-live
cd /workspace/examples/pygentic && python3 main.py
# → Navigate to agent, send a task, verify streaming text appears in Activity panel
```
