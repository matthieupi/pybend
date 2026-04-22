# Streaming Subsystem: Strategic Improvements

**Audit dimension**: Strategic improvements and propositions
**Date**: 2026-03-26
**Scope**: Full-stack streaming — backend protocol, actor transport, SSE/WS bridging, frontend components
**Audience**: Technical CEO and engineering team deciding investment priorities

---

## Executive Summary

The streaming subsystem works. SSE delivery is progressive (proven by E2E timing tests), actor routing handles async generators correctly, and the agent streaming pipeline produces rich typed events. But the system has grown organically across three packages, and **the same patterns are reimplemented in multiple places with subtle differences**. This report identifies seven concrete improvement dimensions and ranks 12 specific propositions by impact/effort ratio.

The highest-leverage improvements are: (1) extracting duplicated agent rendering logic into a shared mixin, (2) unifying the two SSE wire formats between Level 1/2 and Level 3, and (3) adding a server-side cancellation protocol. Together, these three changes would eliminate ~400 lines of duplicated code, close the biggest consistency gap in the framework, and solve the most requested missing capability.

---

## 1. Mental Model Simplification

### Current Model: Too Many Concepts for the Same Thing

The streaming subsystem requires developers to understand these concepts:

```
Backend:
  @expose_route(stream=True)     — marks method as streaming
  @expose_route(events={...})    — declares event vocabulary
  async generator (yield)        — the actual streaming mechanism
  TX.chunk() / TX.end()          — actor envelope for stream chunks
  meta.stream / meta.stream_end  — stream lifecycle flags in meta
  meta.seq                       — chunk ordering
  meta.req                       — correlation to original request

Transport:
  SSE event types: chunk/done/error           — Level 1/2 wire format
  SSE event types: chunk/done/error (TX wrap)  — Level 3 wire format (full TX envelope)
  NetworkAdapter.stream()                      — Queue-based async gen bridge
  NetworkAdapter._pending (Queue vs Future)    — correlation dispatch

Frontend:
  NTTStream.STREAM()             — unified inbox handler
  NTTStream.callMethod()         — sends TX with meta.stream=true
  Dynamic alias binding          — method-name → STREAM() routing
  HTTP.stream()                  — fetch-based SSE consumer
  NetworkAdapter.send() stream branch — TX routing for SSE
```

That is 15+ concepts. A developer who wants to stream results from a model method must understand at least 5 of them.

### Proposed Simpler Model

The irreducible concepts are:

```
1. async generator (yield)         — the streaming mechanism (Python standard)
2. @expose_route(stream=True)      — declaration
3. event types (text/done/error)   — the wire vocabulary
4. UPPERCASE handlers              — frontend dispatch
5. callMethod() with meta.stream   — trigger
```

Everything else is implementation plumbing that should be invisible. The `TX.chunk()`/`TX.end()` distinction, `meta.seq`, Queue vs Future dispatch, SSE formatting -- these are details that should never surface to application developers.

### What Breaks During Transition

Nothing needs to break. The simplification is about **documentation and defaults**, not API removal. The existing TX-level primitives remain available for advanced use cases (custom network adapters, non-SSE transports). The change is to make the simple path genuinely simple by hiding plumbing behind conventions.

---

## 2. Interface Tightening

### 2.1 TX.chunk() seq Parameter is Caller-Managed Boilerplate

**Current state**: Every call site manually tracks a `seq` counter:

```python
# actor_model.py:154-160
seq = 0
async for chunk in result:
    chunk_data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
    await target.send(tx.chunk(chunk_data, seq))
    seq += 1
await target.send(tx.end(seq=seq))
```

```python
# mixin.py:505,583-584,598-601,609-611 (and more)
seq = 0
# ... every yield increments seq manually
seq += 1
```

The `seq` parameter exists on `TX.chunk()` (`tx.py:47`) and `TX.end()` (`tx.py:56`) but is never used for reordering or deduplication anywhere in the codebase. No consumer reads `meta.seq` for logic -- it is purely diagnostic.

**Problem**: Every streaming call site has identical `seq = 0; seq += 1` boilerplate. This is configuration that should be inferred.

**Proposed change**: Make `seq` auto-incrementing per TX correlation chain:

```python
# tx.py — add a stream helper that manages seq internally
def stream_from(self, gen):
    """Wrap an async generator into chunk/end TX sequence.
    Caller just yields dicts; TX handles seq and termination."""
    seq = 0
    async for item in gen:
        data = item if isinstance(item, dict) else {'chunk': item}
        yield self.chunk(data, seq)
        seq += 1
    yield self.end(seq=seq)
```

Then `actor_model.py:152-164` collapses to:

```python
if inspect.isasyncgen(result):
    async for chunk_tx in tx.stream_from(result):
        await target.send(chunk_tx)
    return
```

**Trade-offs**: +Eliminates boilerplate in every streaming call site. +Centralizes error handling. -Adds one method to TX. -Callers that need custom seq logic must still use chunk/end directly.

**Migration**: Additive. New `stream_from()` method; existing `chunk()`/`end()` unchanged.

### 2.2 Level 1/2 SSE Lacks Stream Declaration Check

**Current state**: `routes_fastapi.py:340-349` detects streaming by inspecting the *return value* at runtime:

```python
result = attr(instance, **parsed_args)
if asyncio.iscoroutine(result):
    result = await result
if inspect.isasyncgen(result):
    async def sse(_gen=result):
        # ...
```

The `stream=True` flag on `@expose_route` is only used for schema emission (`proto_model.py:202`) and Level 3 route registration (`network_api.py:398-403`). Level 1/2 never checks it.

**Problem**: A developer could set `stream=False` (or omit it) on an async generator method and Level 1/2 would still stream it. The declaration and behavior are decoupled — violating "transparent, not magical."

**Proposed change**: In Level 1/2, check `__endpoint__['stream']` before attempting SSE. If a method returns an async generator but is not declared `stream=True`, raise an explicit error rather than silently streaming.

**Migration**: Add a check before the `inspect.isasyncgen()` branch. No breaking change — any method that currently works with `stream=True` continues working. Methods that accidentally stream without the flag get a clear error.

---

## 3. Composability Improvements

### 3.1 Agent Rendering Logic is Copy-Pasted Three Times

**Current state**: The UPPERCASE handler implementations for agent streaming are duplicated across three components:

| Component | File | Lines |
|-----------|------|-------|
| `NTTStreamAgent` | `ntx-stream-agent.js` | 1-353 |
| `NTTAgentLive` | `ntx-agent-live.js` | 1-454 |
| `NTTChat` | `ntx-chat.js` | 1-377 |

All three implement nearly identical versions of:
- `THINKING(data, meta)` — thinking indicator toggle + markdown rendering
- `TOOL_CALL(data, meta)` — tool card creation with spinner
- `TOOL_RESULT(data, meta)` — tool card completion
- `TEXT(data, meta)` — text accumulation + markdown rendering
- `DONE(data, meta)` — usage footer
- `#scheduleRender()`, `#renderMd()`, `#flushRender()` — render scheduling
- `#setThinking()` — thinking state management
- `#toolCards` Map, `#textBuf`/`#thinkBuf` accumulators
- `#esc()` — HTML escaping (duplicated in all three)

The differences between them are purely about **layout/chrome** (where to put the output):
- `NTTStreamAgent`: renders inside a method card (embedded in `ntx-item`)
- `NTTAgentLive`: standalone panel with header/footer/input
- `NTTChat`: slide-out chat panel with message history

**Problem**: This is the biggest composability failure in the streaming subsystem. Adding a new agent event type (e.g., `PROGRESS`) requires editing three files. A bug fix in markdown rendering must be applied three times. This directly violates "primitives, not opinions" — the rendering logic *is* a primitive that should be composed, not copied.

**Proposed change**: Extract an `AgentStreamMixin` (or `AgentEntryRenderer`) class that owns the event-to-DOM logic:

```javascript
// AgentEntryRenderer.js — owns event→DOM, not layout
export class AgentEntryRenderer {
    #toolCards = new Map();
    #textBuf = ''; #textRendered = 0; #textTimer = null;
    #thinkBuf = ''; #thinkRendered = 0; #thinkTimer = null;

    constructor(container, options = {}) {
        this.container = container;  // where to append entries
        this.options = options;      // {useJsonTree: false, maxHeight: 500}
    }

    // Event handlers — called by owning component's UPPERCASE handlers
    thinking(data)    { /* create/update thinking entry */ }
    toolCall(data)    { /* create tool card with spinner */ }
    toolResult(data)  { /* complete tool card */ }
    text(data)        { /* accumulate text, schedule markdown render */ }
    done(data)        { /* render usage footer */ }
    error(data)       { /* render error entry */ }

    reset()           { /* clear all state */ }
    flush()           { /* force pending renders */ }
    destroy()         { /* clear timers */ }

    static styles     // CSS for entries (shared)
}
```

Then each component delegates:

```javascript
class NTTStreamAgent extends NTTStream {
    #renderer;
    callMethod() {
        this.#renderer = new AgentEntryRenderer(this.#output());
        super.callMethod();
    }
    THINKING(data) { this.#renderer.thinking(data); }
    TEXT(data)     { this.#renderer.text(data); }
    // ...
}
```

**Trade-offs**: +Eliminates ~500 lines of duplication. +Single place to fix rendering bugs. +New components (e.g., `ntx-agent-sidebar`) get agent rendering for free. -Adds one new file. -Existing components need refactoring (but behavior is identical).

**Migration**:
1. Create `AgentEntryRenderer.js` with extracted logic
2. Refactor `NTTStreamAgent` to use it (smallest surface area)
3. Refactor `NTTAgentLive` and `NTTChat` in parallel
4. Each refactoring is independently testable — same visual output

### 3.2 NTTStream Dynamic Alias is Fragile

**Current state**: `ntx-stream.js:49-56` binds a dynamic alias so that reply TXs named after the method route to the unified STREAM handler:

```javascript
const name = this.method;
if (this.#boundHandler && this.#boundHandler !== name) {
    delete this[this.#boundHandler];
}
this[name] = (data, tx) => this.STREAM(data, tx);
this.#boundHandler = name;
```

**Problem**: This works but resists composition. If a component has both a streaming method and a non-streaming method with the same name on different models, the alias clobbers. More importantly, it requires understanding the dynamic alias mechanism to debug stream routing issues — violating "transparent, not magical."

**Proposed change**: Instead of dynamic property assignment, use a consistent dispatch pattern in the Component base class. When `meta.stream` is present in an incoming TX, route to `STREAM()` regardless of the TX name. The method name becomes metadata, not routing.

```javascript
// In Component.js or NTTStream
inbox(tx) {
    if (tx.meta?.stream || tx.meta?.stream_end) {
        return this.STREAM(tx.data, tx);
    }
    // ... normal dispatch
}
```

This eliminates the dynamic alias entirely. The `STREAM` handler already does typed dispatch via `data.name.toUpperCase()`, so method-name routing is redundant.

**Trade-offs**: +Eliminates the alias hack. +Stream routing becomes transparent. -Requires `meta.stream` to be present on all stream TXs (it already is: `tx.py:53`). -Non-stream TXs with `meta.stream` would be misrouted (unlikely — this flag is set by `tx.chunk()`).

**Migration**: Remove alias code from `NTTStream.callMethod()`. Add stream dispatch to inbox. Existing UPPERCASE handlers unchanged.

---

## 4. Resilience & Error Recovery

### 4.1 No Server-Side Stream Cancellation

**Current state**: `ntx-stream.js:138-154` sends a `STREAM_CANCEL` TX when the user cancels:

```javascript
cancel() {
    if (!this.#streaming) return;
    this.#cancelled = true;
    this.#streaming = false;
    // ...
    this.send(new TX({
        name: 'STREAM_CANCEL',
        source: this.addr,
        target: target,
        meta: { req: this.#streamReqId },
    }));
    this.STREAM_END({});
}
```

But **no backend handler processes `STREAM_CANCEL`**. The backend async generator runs to completion even after the client disconnects. For agent streams that can run for 30+ seconds with tool calls, this wastes significant compute.

**Problem**: Resource waste. An agent stream invoking multiple tools will continue executing all tool calls even after the user navigates away.

**Proposed change**:

Backend: Add cancellation support to `NetworkAdapter.stream()` and `ActorModel.handler()`:

```python
# network_adapter.py — add cancel flag to pending entries
async def stream(self, tx, timeout=120.0):
    queue = asyncio.Queue()
    cancel_event = asyncio.Event()
    self._pending[tx.uuid] = {'queue': queue, 'cancel': cancel_event}
    # ...

async def inbox(self, tx):
    if tx.name == 'STREAM_CANCEL':
        req = tx.meta.get('req')
        if req in self._pending:
            self._pending[req]['cancel'].set()
        return
    # ... existing logic
```

```python
# actor_model.py — check cancellation between chunks
if inspect.isasyncgen(result):
    cancel = tx.meta.get('_cancel_event')
    seq = 0
    async for chunk in result:
        if cancel and cancel.is_set():
            await target.send(tx.end(seq=seq))
            return
        # ... send chunk
```

For SSE (HTTP), use FastAPI's `Request.is_disconnected()`:

```python
# network_api.py — detect client disconnect
async def _sse_from_stream(adapter, tx, request):
    async for chunk in adapter.stream(tx, timeout=120.0):
        if await request.is_disconnected():
            return  # Client gone, stop streaming
        # ... yield SSE
```

**Trade-offs**: +Stops wasting compute on cancelled streams. +Agent tool calls stop when user navigates away. -Adds complexity to cancellation flow. -Async generators may not support clean interruption (need `GeneratorExit` handling).

**Migration**:
1. Add `is_disconnected()` check to `_sse_from_stream()` (immediate win, no protocol change)
2. Add `STREAM_CANCEL` handler to `NetworkAdapter` / `NetworkWebSocket`
3. Thread cancellation event through to `ActorModel.handler()`

### 4.2 Agent Stream Swallows All Exceptions

**Current state**: `mixin.py:685-691` catches all exceptions and yields a single error chunk:

```python
except Exception as e:
    yield {
        'name': 'error',
        'data': {'message': str(e), 'code': 500},
        'meta': {'stream': True, 'error': True, 'seq': seq},
    }
```

**Problem**: This is the right structure, but `str(e)` often produces unhelpful messages. For `pydantic_ai` errors (rate limits, model errors, validation failures), the exception hierarchy is rich but `str(e)` flattens it. More importantly, there is no retry or partial-result recovery. If the LLM fails on the 5th tool call of an 8-tool chain, all 4 successful results are lost.

**Proposed change**:

1. Map exception types to error categories (like `TX.from_exception` does for CRUD):

```python
except Exception as e:
    code = 500
    category = 'internal'
    if 'rate_limit' in type(e).__name__.lower() or 'RateLimitError' in str(type(e)):
        code = 429
        category = 'rate_limit'
    elif isinstance(e, asyncio.TimeoutError):
        code = 504
        category = 'timeout'
    # ...
    yield {
        'name': 'error',
        'data': {'message': str(e), 'code': code, 'category': category},
        'meta': {'stream': True, 'error': True, 'seq': seq},
    }
```

2. Yield already-accumulated text before the error:

```python
except Exception as e:
    # Yield partial text if we have any
    if streamed_text:
        yield {
            'name': 'partial_done',
            'data': {'text': streamed_text, 'tool_calls': tool_call_count},
            'meta': {'stream': True, 'seq': seq},
        }
        seq += 1
    # Then yield error
    yield { 'name': 'error', ... }
```

**Trade-offs**: +Better error messages for frontend display. +Partial results preserved. -More complex error handling. -`partial_done` is a new event type that frontend must handle.

**Migration**: Backend-only change to `run_stream()`. Frontend can ignore `partial_done` until support is added (it just appears as an unhandled chunk type in NTTStream base).

### 4.3 HTTP.stream() Silently Swallows Partial JSON

**Current state**: `HTTP.js:386`:

```javascript
try {
    const parsed = JSON.parse(line.slice(6));
    // ...
} catch (e) { /* partial JSON, wait for more data */ }
```

**Problem**: If the server sends malformed JSON (not just incomplete), this silently drops it. The comment says "partial JSON, wait for more data" but there is no actual reassembly — the `buffer` mechanism handles line splitting, not JSON fragment reassembly. A genuinely corrupt chunk is silently lost.

**Proposed change**: Distinguish between incomplete and malformed JSON:

```javascript
try {
    const parsed = JSON.parse(line.slice(6));
    // ... dispatch
} catch (e) {
    // If the line looks complete (ends properly), this is corrupt data
    if (line.endsWith('}') || line.endsWith(']') || line.endsWith('"')) {
        console.warn('[HTTP.stream] Corrupt SSE data:', line.slice(6));
    }
    // Otherwise, truly partial — will complete on next buffer fill
}
```

**Trade-offs**: +Surfaces corruption rather than silently swallowing it. -Minor: adds a heuristic that could false-positive on edge cases.

---

## 5. Extensibility Without Modification

### 5.1 Stream Event Types Require Code Changes in Three Places

**Current state**: To add a new agent stream event type (e.g., `PROGRESS`):

1. Backend: Add yield in `mixin.py:run_stream()` with the new event name
2. Frontend: Add handler in `NTTStreamAgent.js` (and `NTTAgentLive.js`, and `NTTChat.js`)
3. Schema: Add event model to `actor.py` and `@expose_route(events={...})`

**Problem**: The event types are declared in schema (`events={}`) but the frontend dispatch is hardcoded. The schema carries the event definitions but the frontend does not use them for dispatch — it relies on class methods.

**Proposed change**: Make `NTTStream.STREAM()` use the schema's `events` declaration for dispatch. Unknown event types get a default renderer rather than being silently ignored:

```javascript
STREAM(data, tx) {
    const name = data?.name?.toUpperCase();

    // Known handler on the component — use it
    if (name && typeof this[name] === 'function') {
        this[name](data.data, data.meta);
        return;
    }

    // Schema-declared event — render with generic handler
    const eventSchema = this.methodSchema?.events?.[data?.name];
    if (eventSchema) {
        this.GENERIC_EVENT(data.name, data.data, eventSchema);
        return;
    }

    // Unknown — fallback to TEXT
    this.TEXT(data);
}

GENERIC_EVENT(name, data, schema) {
    // Render a generic entry using the schema's property definitions
    const label = schema.title || name;
    this.#addEntry('generic', `${label}: ${JSON.stringify(data)}`);
}
```

**Trade-offs**: +New event types work without frontend code changes. +Schema-declared events get automatic rendering. -Generic rendering is less polished than custom handlers. -Small runtime cost for schema lookup on each chunk.

**Migration**: Additive. Existing UPPERCASE handlers take priority. Schema-based dispatch is the fallback.

### 5.2 Level 1/2 and Level 3 SSE Formats Cannot Be Switched

**Current state**: Level 1/2 SSE sends plain data (`routes_fastapi.py:342-344`):

```python
yield f"event: chunk\ndata: {json.dumps(data, default=str)}\n\n"
yield f"event: done\ndata: {{}}\n\n"
```

Level 3 SSE sends full TX envelopes (`network_api.py:477-485`):

```python
tx_dict = asdict(chunk)
yield f"event: chunk\ndata: {json.dumps(tx_dict, default=str)}\n\n"
```

The frontend handles both: `NetworkAdapter.send()` (`NetworkAdapter.js:150-166`) routes stream TXs through `HTTP.stream()` which calls `httpCallback` — and `httpCallback` unwraps the response. For Level 3, the SSE data IS a TX envelope; for Level 1/2, it is plain data.

**Problem**: The test files reveal this divergence clearly. Level 1/2 tests access `e['data']['count']` directly (`examples/core/tests/test_streaming.py:78`). Level 3 tests must unwrap `e['data']['data']['count']` (`examples/actors/tests/test_streaming.py:79-80`). This means frontend code that works with Level 1/2 breaks with Level 3 and vice versa.

**Proposed change**: Unify the wire format. Two options:

**Option A (recommended)**: Level 1/2 wraps in TX-like envelope to match Level 3:

```python
# routes_fastapi.py — unified SSE format
yield f"event: chunk\ndata: {json.dumps({'data': data, 'meta': {'stream': True, 'seq': seq}}, default=str)}\n\n"
yield f"event: done\ndata: {json.dumps({'data': {}, 'meta': {'stream_end': True}}, default=str)}\n\n"
```

**Option B**: Level 3 unwraps TX envelope to match Level 1/2 (simpler frontend, less metadata):

```python
# network_api.py — plain SSE format
yield f"event: chunk\ndata: {json.dumps(chunk.data, default=str)}\n\n"
```

Option A is better because the TX metadata (seq, stream, req) is useful for debugging and the frontend `NTTStream.STREAM()` handler already expects typed data with `data.name` for dispatch.

**Trade-offs**: +Eliminates the Level 1/2 vs Level 3 divergence. +Frontend code works across all routing levels. -Breaking change for Level 1/2 consumers that parse raw SSE data directly.

**Migration**:
1. Update Level 1/2 SSE to wrap in envelope
2. Update Level 1/2 test assertions (plain `data` → `data.data`)
3. Frontend `httpCallback` already handles both shapes — verify and simplify

---

## 6. Convention Over Configuration

### 6.1 @expose_route(stream=True) is Redundant with async Generator

**Current state**: Developers must explicitly declare `stream=True`:

```python
@expose_route('/countdown', methods=['POST'], stream=True, access=ANYONE)
async def countdown(self, n: int):
    for i in range(n, -1, -1):
        yield {'count': i}
```

But the system can detect that a method is an async generator at definition time (or at route registration time). Level 1/2 already does this at runtime (`routes_fastapi.py:340`).

**Problem**: The declaration is redundant with the implementation. If you `yield`, you're streaming. Having to say `stream=True` separately means the declaration can be wrong (say `stream=False` but yield anyway).

**Proposed change**: Infer `stream=True` from function inspection at decorator time:

```python
def expose_route(route, methods=["POST"], access=None, stream=None, events=None):
    def decorator(func):
        # Auto-detect streaming from function type
        _stream = stream
        if _stream is None:
            _stream = inspect.isasyncgenfunction(func)
        # ...
        wrapper.__endpoint__ = {
            'stream': _stream,
            # ...
        }
```

**Trade-offs**: +Zero-config streaming — just yield. +Eliminates a class of declaration errors. -Explicit `stream=True` is still needed for methods that return an async generator created elsewhere. -Slight behavior change: methods that accidentally yield would now be detected as streaming.

**Migration**: Change default of `stream` parameter from `False` to `None` (auto-detect). Existing `stream=True` declarations continue to work. Existing `stream=False` (explicit opt-out) continues to work.

### 6.2 Timeout Values are Hardcoded in Multiple Places

**Current state**: Timeout values are scattered across files with no central configuration:

| Location | Value | Purpose |
|----------|-------|---------|
| `network_adapter.py:79` | 30.0s | `request()` timeout |
| `network_adapter.py:118` | 120.0s | `stream()` timeout |
| `network_api.py:158` | 10.0s | Schema request timeout |
| `network_api.py:186,236,242,269,306,344,363` | 30.0s | CRUD request timeout |
| `network_api.py:477` | 120.0s | SSE stream timeout |
| `network_ws.py:204` | 30.0s | WS request timeout |
| `network_ws.py:214` | 120.0s | WS stream timeout |

**Problem**: No way to tune timeouts without editing source code. Agent streams can legitimately run for 5+ minutes with complex tool chains.

**Proposed change**: Add timeout defaults to `config.py`:

```python
# config.py
REQUEST_TIMEOUT = float(os.getenv('N3TX_REQUEST_TIMEOUT', '30.0'))
STREAM_TIMEOUT = float(os.getenv('N3TX_STREAM_TIMEOUT', '120.0'))
SCHEMA_TIMEOUT = float(os.getenv('N3TX_SCHEMA_TIMEOUT', '10.0'))
```

Then reference `config.STREAM_TIMEOUT` instead of magic numbers.

**Migration**: Replace hardcoded values with config references. No behavior change with default values.

---

## 7. Consistency Gaps

### 7.1 SSE Error Handling Differs Between Levels

**Current state**: When a streaming method targets a nonexistent entity:

- **Level 1/2** (`routes_fastapi.py:310-312`): Returns HTTP 404 before starting the stream. The SSE connection never opens.
- **Level 3** (`network_api.py:515-519`): Returns HTTP 200 with SSE, then sends an error event within the stream. The test at `examples/actors/tests/test_streaming.py:108-125` explicitly documents this.

**Problem**: The same endpoint behaves differently depending on the routing level. Frontend code must handle both "HTTP error before stream" and "error event within stream" patterns. This violates "zero to working, then customize" — switching routing levels changes error semantics.

**Proposed change**: Standardize on Level 3 behavior (error-in-stream) for both levels. This is more correct for SSE — the connection should succeed, and application errors should be conveyed as events.

For Level 1/2, wrap the entity fetch inside the SSE generator:

```python
async def sse(_gen_fn=attr, _instance_id=id, **kwargs):
    try:
        instance = model_class.get(_instance_id)
        if not instance:
            yield f"event: error\ndata: {json.dumps({'message': 'Not found', 'code': 404})}\n\n"
            return
        gen = _gen_fn(instance, **kwargs)
        async for chunk in gen:
            yield f"event: chunk\ndata: {json.dumps(chunk, default=str)}\n\n"
        yield f"event: done\ndata: {{}}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e), 'code': 500})}\n\n"
```

**Trade-offs**: +Consistent behavior across routing levels. +Frontend only needs one error handling path. -Level 1/2 streaming errors no longer return HTTP error codes (always 200).

**Migration**: Update Level 1/2 streaming handler. Update Level 1/2 streaming tests.

### 7.2 Frontend NTTStream Does Not Use Schema Event Definitions

**Current state**: The schema carries typed event definitions via `methods[m].events`:

```json
{
  "agentic_stream": {
    "stream": true,
    "events": {
      "text": {"properties": {"text": {"type": "string"}}},
      "tool_call": {"properties": {"tool": {"type": "string"}, "args": {...}}},
      ...
    }
  }
}
```

But `NTTStream.STREAM()` (`ntx-stream.js:22-35`) dispatches purely by string matching `data.name.toUpperCase()` against component methods. The schema events are never consulted.

**Problem**: The schema is the "single contract between backend and frontend" (per CLAUDE.md), but stream events bypass it entirely. This means there's no validation that incoming events match the declared schema, no auto-discovery of event types, and no default rendering for schema-declared events.

This is covered in section 5.1 above. Noting it here as a consistency gap with the framework's philosophy.

---

## 8. Propositions Summary Table

| # | Proposition | Simplifies | Impact | Effort | Risk | Dependencies |
|---|-------------|-----------|--------|--------|------|--------------|
| P1 | Extract `AgentEntryRenderer` from 3 duplicated components | Frontend dev, bug fixes | **High** | Medium (2-3d) | Low | None |
| P2 | Unify SSE wire format (Level 1/2 = Level 3 envelope) | Frontend consistency | **High** | Medium (1-2d) | Medium | Test updates |
| P3 | Add server-side stream cancellation (`is_disconnected` + `STREAM_CANCEL`) | Resource efficiency | **High** | Medium (2-3d) | Low | None |
| P4 | Auto-detect `stream=True` from async generator | Developer ergonomics | **Medium** | Low (0.5d) | Low | None |
| P5 | Centralize timeout config | Ops/deployment | **Medium** | Low (0.5d) | Low | None |
| P6 | Add `TX.stream_from()` helper | Backend dev | **Medium** | Low (0.5d) | Low | None |
| P7 | Schema-driven event dispatch in NTTStream | Extensibility | **Medium** | Low (1d) | Low | None |
| P8 | Standardize error semantics (error-in-stream for all levels) | Frontend consistency | **Medium** | Medium (1-2d) | Medium | P2 |
| P9 | Typed error categories in agent stream | Error UX | **Low** | Low (0.5d) | Low | None |
| P10 | Remove dynamic alias in NTTStream | Code clarity | **Low** | Low (0.5d) | Medium | Verify routing |
| P11 | Level 1/2 stream declaration check | Correctness | **Low** | Low (0.5d) | Low | None |
| P12 | Partial result preservation on agent error | Data resilience | **Low** | Low (0.5d) | Low | Frontend event |

### Recommended Priority Order (by impact/effort)

**Tier 1 — Do now (high impact, standalone)**:
1. **P4**: Auto-detect `stream=True` — 30 minutes, zero risk, better DX
2. **P5**: Centralize timeouts — 30 minutes, zero risk, ops win
3. **P6**: `TX.stream_from()` — 30 minutes, eliminates boilerplate everywhere

**Tier 2 — Do next (high impact, moderate effort)**:
4. **P1**: `AgentEntryRenderer` extraction — biggest code quality win
5. **P3**: Server-side cancellation — biggest resource efficiency win
6. **P2**: Unified SSE format — biggest consistency win (enables P8)

**Tier 3 — Do when touching adjacent code**:
7. **P7**: Schema-driven event dispatch
8. **P8**: Error semantics standardization (after P2)
9. **P9**: Typed error categories
10. **P10**: Remove dynamic alias (after P7 validates routing)

**Tier 4 — Optional**:
11. **P11**: Stream declaration check
12. **P12**: Partial result preservation

### Dependency Graph

```
P4, P5, P6 — independent, no dependencies
P1 — independent
P3 — independent
P2 → P8 (unified format enables unified error semantics)
P7 → P10 (schema dispatch replaces dynamic alias)
```

No proposition blocks another. P2 and P8 have the strongest synergy — do them together if possible.

---

## Appendix: Data Flow Diagrams

### Current Streaming Architecture (Level 3)

```
User clicks "Run"
  │
  ▼
NTTStream.callMethod()                    [ntx-stream.js:42-67]
  │  sends TX {name: method, meta: {stream: true}}
  │
  ▼
Matrix.dispatch() → NetworkAdapter.send() [NetworkAdapter.js:119-171]
  │  HTTP fallback: meta.stream branch
  │
  ▼
HTTP.stream(url, data, cb, cb, onErr)     [HTTP.js:353-400]
  │  POST with fetch + ReadableStream
  │
  ▼
FastAPI route handler                      [network_api.py:498-540]
  │  returns StreamingResponse(_sse_from_stream())
  │
  ▼
_sse_from_stream(adapter, tx)              [network_api.py:469-485]
  │  async for chunk in adapter.stream(tx)
  │
  ▼
NetworkAdapter.stream(tx)                  [network_adapter.py:118-163]
  │  Queue-based correlation
  │  asyncio.create_task(self.send(tx))
  │
  ▼
Matrix.inbox(tx) → ActorModel.handler(tx) [actor_model.py:70-164]
  │  detects async generator
  │  sends tx.chunk() / tx.end() for each yield
  │
  ▼
Chunks route back: Matrix → adapter.inbox [network_adapter.py:57-76]
  │  Queue receives chunks
  │
  ▼
_sse_from_stream yields SSE text           [network_api.py:477-485]
  │  event: chunk\ndata: {TX envelope}\n\n
  │
  ▼
HTTP.stream() pump() reads SSE             [HTTP.js:371-393]
  │  parses events, calls onChunk/onDone
  │
  ▼
httpCallback → Matrix.dispatch()           [NetworkAdapter.js:37-56]
  │  dispatches to component inbox
  │
  ▼
NTTStream.STREAM() → UPPERCASE handlers   [ntx-stream.js:22-35]
  │  TEXT(), DONE(), STREAM_END(), etc.
```

### Proposed Architecture (after P1, P2, P3, P7)

```
User clicks "Run"
  │
  ▼
NTTStream.callMethod()
  │  sends TX {meta: {stream: true}}
  │
  ▼
NetworkAdapter.send() → HTTP.stream()
  │  POST + ReadableStream
  │
  ▼
FastAPI route → StreamingResponse
  │  _sse_from_stream(adapter, tx, request)     ← P3: request for disconnect check
  │
  ▼
NetworkAdapter.stream() → Queue correlation
  │
  ▼
ActorModel.handler() → tx.stream_from(gen)      ← P6: no manual seq
  │  checks cancel_event between chunks          ← P3: cancellation
  │
  ▼
SSE: event: chunk\ndata: {data, meta}\n\n       ← P2: unified envelope
  │
  ▼
NTTStream.STREAM()
  │  schema-aware dispatch                       ← P7: check events schema
  │  UPPERCASE handler or GENERIC_EVENT()
  │
  ▼
AgentEntryRenderer handles DOM                   ← P1: shared renderer
```

---

## Appendix: Files Referenced

| File | Key references |
|------|---------------|
| `packages/n3tx-actors/src/n3tx_actors/tx.py` | :47-63 (chunk/end), :65-67 (aliases) |
| `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py` | :57-76 (inbox), :79-116 (request), :118-163 (stream) |
| `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` | :469-485 (_sse_from_stream), :488-540 (_add_streaming_handler) |
| `packages/n3tx-actors/src/n3tx_actors/api/network_ws.py` | :207-230 (_stream_to_ws) |
| `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` | :336-349 (isasyncgen detection), :340-349 (Level 1/2 SSE) |
| `packages/n3tx-core/src/n3tx_core/utils/decorators.py` | :13-88 (expose_route) |
| `packages/n3tx-core/src/n3tx_core/models/proto_model.py` | :194-213 (methods schema with stream/events) |
| `packages/n3tx-agents/src/n3tx_agents/mixin.py` | :461-691 (run_stream) |
| `packages/n3tx-agents/src/n3tx_agents/actor.py` | :41-66 (event models), :170-204 (agentic_stream) |
| `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py` | :152-164 (async gen stream dispatch) |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js` | :22-35 (STREAM), :42-67 (callMethod), :138-154 (cancel) |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` | :1-353 (full file) |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` | :1-454 (full file) |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js` | :1-377 (full file) |
| `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js` | :353-400 (stream) |
| `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js` | :119-171 (send with stream routing) |
| `examples/core/tests/test_streaming.py` | :78 (Level 1/2 data access pattern) |
| `examples/actors/tests/test_streaming.py` | :79-80 (Level 3 data access pattern) |
