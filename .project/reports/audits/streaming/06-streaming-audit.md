# Streaming -- Deep Audit Report

**Auditor:** Claude Opus 4.6
**Date:** 2026-03-26
**Scope:** Full-stack streaming subsystem -- backend protocol, actor transport, SSE/WS bridging, frontend components
**Method:** Synthesis of five dimension reports covering architecture, API contracts, quality/risks, extensibility, and strategic improvements

---

## Executive Summary

The N3TX streaming subsystem delivers progressive data from backend Python async generators to browser consumers via SSE and WebSocket transports. It spans four packages (`n3tx-core`, `n3tx-actors`, `n3tx-agents`, `n3tx-ui`) and 22 core files, handling three routing levels (Level 1/2 direct, Level 3 actor-routed) and three domain layers (raw streaming, agent streaming, chat). The subsystem is architecturally sound: the TX envelope provides a universal message format, the Queue-based rendezvous in `NetworkAdapter.stream()` elegantly bridges fire-and-forget actors with streaming consumers, and the `@expose_route(stream=True)` declaration makes streaming a zero-boilerplate concern for application developers.

However, the system has accumulated inconsistencies as it grew organically. The most significant issue is the **SSE wire format divergence** between Level 1/2 (bare chunk data) and Level 3 (full TX envelope), which means frontend code that works at one routing level breaks silently at another. This directly violates the framework's "zero to working, then customize" philosophy. The second major issue is a **bug in Level 1/2 error handling**: the SSE generator wrapper has no try/except, so mid-stream exceptions produce truncated streams with no error signal. Level 3 handles this correctly via `ActorModel.handler()`. The third is **massive code duplication** across three frontend agent components (`NTTStreamAgent`, `NTTAgentLive`, `NTTChat`) that implement near-identical UPPERCASE handlers and rendering logic.

**Top 3 recommendations** (immediate action):
1. **Add try/except to Level 1/2 SSE wrapper** (`routes_fastapi.py:341-345`). This is a bug with a one-line fix that prevents silent stream truncation.
2. **Centralize timeout configuration** by adding `STREAM_TIMEOUT` and `REQUEST_TIMEOUT` to `config.py`. Seven hardcoded timeout values across four files become configurable with zero behavior change.
3. **Auto-detect `stream=True`** from async generator function inspection in `@expose_route`. Eliminates a class of declaration errors in under 30 minutes.

**Top 3 strategic improvement propositions:**
1. **Extract `AgentEntryRenderer`** from the three duplicated frontend components. Eliminates ~500 lines of copy-pasted rendering logic and makes agent event handling a composable primitive. High impact, medium effort (2-3 days).
2. **Unify SSE wire format** so Level 1/2 and Level 3 produce the same envelope shape. Closes the biggest consistency gap and enables frontend code to work across routing levels. High impact, medium effort (1-2 days).
3. **Implement server-side stream cancellation** by handling the `STREAM_CANCEL` TX that the frontend already sends. Stops wasting compute on cancelled agent streams. High impact, medium effort (2-3 days).

---

## Component Overview

### Consolidated Component Map

```
                         APPLICATION LAYER
         ┌─────────────────────────────────────────────────┐
         │  @expose_route(stream=True, events={...})       │
         │  async def method(self): yield {...}             │
         └──────┬────────────────┬───────────────┬─────────┘
                │                │               │
    ┌───────────▼──────┐  ┌─────▼─────────┐  ┌──▼──────────────┐
    │   n3tx-agents     │  │  n3tx-actors   │  │    n3tx-ui       │
    │                   │  │                │  │                  │
    │ AgentMixin        │  │ TX             │  │ NTTStream        │
    │  .run_stream()    │  │  .chunk()      │  │  .STREAM()       │
    │  .agentic_stream()│  │  .end()        │  │  .callMethod()   │
    │                   │  │                │  │  .cancel()       │
    │ AgentActor        │  │ NetworkAdapter │  │                  │
    │  .agentic_stream()│  │  .stream()     │  │ NTTMethod        │
    │                   │  │  .inbox()      │  │  (base class)    │
    │ Event Models      │  │                │  │                  │
    │  TextChunk        │  │ NetworkAPI     │  └───────┬──────────┘
    │  ToolCallEvent    │  │  _sse_from_    │          │
    │  DoneChunk ...    │  │   stream()     │          │
    │                   │  │  _add_stream_  │          │
    │ NTTStreamAgent    │  │   handler()    │          │
    │ NTTAgentLive      │  │                │          │
    │ NTTChat           │  │ NetworkWS      │          │
    └────────┬──────────┘  │  _stream_to_   │          │
             │             │   ws()         │          │
             │             │                │          │
             │             │ ActorModel     │          │
             │             │  .handler()    │          │
             └──────┬──────┴───────┬────────┘          │
                    │              │                    │
         ┌──────────▼──────────────▼────────────────────▼──────┐
         │                   n3tx-core                          │
         │                                                     │
         │  BACKEND:                   FRONTEND:               │
         │  routes_fastapi.py          HTTP.stream()            │
         │    Level 1/2 SSE            NetworkAdapter.send()    │
         │  decorators.py              Socket (WS transport)    │
         │    @expose_route            Matrix (dispatch)        │
         │  proto_model.py                                     │
         │    schema: methods[m]                               │
         └─────────────────────────────────────────────────────┘
```

### Data Flow: Level 3 (Actor-Routed SSE)

```
Browser click → NTTStream.callMethod() → TX{meta.stream:true}
  → NetworkAdapter.send() → HTTP.stream(POST) → FastAPI route
    → _sse_from_stream() → adapter.stream(tx) → Queue + create_task(send)
      → Matrix → ActorModel.handler() detects isasyncgen
        → for each yield: tx.chunk(data, seq) → Matrix → adapter.inbox()
          → Queue.put(chunk_tx) → _sse_from_stream yields SSE text
            → event: chunk\ndata: {TX envelope}\n\n
              → HTTP.stream() pump() → onChunk → httpCallback
                → Matrix.dispatch → NTTStream.STREAM() → UPPERCASE handlers
```

### State Management

**Backend state per stream:**

| State | Location | Lifecycle |
|-------|----------|-----------|
| `_pending[tx.uuid]` (Queue) | `NetworkAdapter` PrivateAttr | Created on `stream()` call, removed in `finally` block on exit |
| `seq` counter | Local variable in `handler()` / `run_stream()` | Per-stream invocation, not persisted |
| `send_task` | Local in `NetworkAdapter.stream()` | Created via `create_task`, cancelled in `finally` if not done |
| `_connections` dict | `NetworkWebSocket` PrivateAttr | Per-WS-adapter lifetime; entries added on connect, removed on disconnect |

**Frontend state per stream:**

| State | Location | Lifecycle |
|-------|----------|-----------|
| `#streaming` boolean | `NTTStream` private field | True during active stream, false on end/error/cancel |
| `#cancelled` boolean | `NTTStream` private field | Set by `cancel()`, checked by `STREAM()` to ignore late chunks |
| `#streamReqId` | `NTTStream` private field | Set on `callMethod()`, used for cancel TX correlation |
| `#textBuf` / `#thinkBuf` | `NTTStreamAgent` private fields | Accumulate text between debounced renders, reset on new stream |
| `#toolCards` Map | `NTTStreamAgent` private field | Maps `call_id` to DOM element for tool result correlation |
| `_done` flag | `HTTP.stream()` closure | Prevents duplicate done callbacks |
| `controller` | `HTTP.stream()` return | `AbortController` for fetch cancellation |

**Risk: `_pending` leak on backend crash.** If `inbox()` never receives `stream_end` or error (e.g., the backend handler crashes without sending `tx.end()`), the Queue stays in `_pending` until `stream()` times out at 120 seconds. During that window, accumulated chunks consume memory. The `finally` block at `network_adapter.py:160` ensures eventual cleanup.

### Architecture Constraints

| Constraint | Description | Impact |
|------------|-------------|--------|
| **Unidirectional only** | Client sends request, server streams responses. No client-to-server streaming. | Cannot do progressive file uploads or bidirectional chat without WS |
| **No backpressure** | Queue is unbounded. Producer yields as fast as it can. | Batch-processing streams could accumulate significant memory |
| **No chunk acknowledgment** | Frontend never confirms receipt. Backend fires and forgets. | Lost chunks are undetectable despite `meta.seq` enabling gap detection |
| **No stream resumption** | Interrupted streams cannot be resumed from last `meta.seq` | Network drop requires complete re-invocation |
| **Single consumer** | Each stream has one consumer (requesting adapter) | No fanout/broadcast without custom pub/sub |
| **In-memory correlation** | `_pending` dict is per-process, not persisted | Server restart loses all active stream state |
| **Per-chunk timeout only** | `NetworkAdapter.stream()` timeout applies per-chunk wait, not total stream duration | A stream yielding chunks every 119s never times out |

---

## Key Findings

### Critical Issues

**F1: Level 1/2 SSE has no error handling for generator exceptions**
- **Evidence:** `routes_fastapi.py:341-345` -- the `sse()` inner function iterates the async generator with no try/except:
  ```python
  async def sse(_gen=result):
      async for chunk in _gen:
          data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
          yield f"event: chunk\ndata: {json.dumps(data, default=str)}\n\n"
      yield f"event: done\ndata: {{}}\n\n"
  ```
  If the generator raises, FastAPI's `StreamingResponse` terminates the connection silently. The client sees a truncated stream with no error or done event. Level 3 handles this correctly via `actor_model.py:161-163`.
- **Severity:** Critical
- **Recommendation:** Wrap the `async for` in try/except, yielding `event: error\ndata: {json}\n\n` on exception. The same duplication exists at lines 389-393 for `post_no_id`.

**F2: SSE wire format divergence between Level 1/2 and Level 3**
- **Evidence:** Level 1/2 (`routes_fastapi.py:343`) sends `data: {"count": 3}`. Level 3 (`network_api.py:478-485`) sends `data: {"name": "STREAM", "source": "...", "data": {"count": 3}, "meta": {...}}`. Integration tests confirm: Level 1/2 accesses `e['data']['count']` (`examples/core/tests/test_streaming.py:78`); Level 3 accesses `e['data']['data']['count']` (`examples/actors/tests/test_streaming.py:79-80`).
- **Severity:** High
- **Recommendation:** Unify format. Level 1/2 should wrap chunks in a minimal envelope: `{"data": chunk_data, "meta": {"stream": true, "seq": N}}` to match Level 3 shape.

**F3: `run_stream()` error yields a dict that escapes as a stream chunk, not an error TX**
- **Evidence:** `mixin.py:685-691` yields `{'name': 'error', 'data': {'message': str(e), 'code': 500}, 'meta': {'stream': True, 'error': True, 'seq': seq}}`. This dict is wrapped by `ActorModel.handler()` at line 157-158 via `tx.chunk(chunk_data, seq)`. The outer TX chunk does NOT have `meta.error=True` (the error flag is nested inside `data.meta`), so `_sse_from_stream()`'s `chunk.is_error` check at `network_api.py:479` fails. The error is serialized as `event: chunk` rather than `event: error`.
- **Severity:** High
- **Recommendation:** `run_stream()` should raise the exception instead of yielding a dict, letting `ActorModel.handler()`'s existing error handling (`tx.exception(e)` at line 161-163) produce a proper error TX.

**F4: `_parse_method_args` treats all parameters as required in Level 1/2**
- **Evidence:** `routes_fastapi.py:316-322` -- every parameter not named `self`, `cls`, or `user` raises `HTTPException(400, "Missing field: {name}")` if absent. Parameters with default values (e.g., `n: int = 5`) still trigger 400 errors. Level 3 has the opposite bug: `network_api.py:559` silently skips all missing params with `if raw is None: continue`.
- **Severity:** High
- **Recommendation:** Check `param.default is not inspect.Parameter.empty` before raising. Apply consistently across both levels.

### Design Strengths

**S1: TX envelope as universal contract.**
`TX.chunk()` and `TX.end()` at `tx.py:47-63` encode streaming semantics directly in the TX envelope via `meta.stream`, `meta.seq`, `meta.stream_end`, and `meta.req`. Stream chunks, errors, and termination all use the same shape. This eliminates protocol-specific handling across the codebase and enables transport-agnostic streaming.

**S2: Queue-based rendezvous in `NetworkAdapter.stream()`.**
The async Queue pattern at `network_adapter.py:139-162` elegantly bridges fire-and-forget actor messaging with streaming consumers. The `asyncio.create_task(self.send(tx))` launch prevents progressive delivery deadlock (documented in the comment at lines 142-146). The `finally` block guarantees cleanup of `_pending` entries.

**S3: Clean agent/actor separation.**
`run_stream()` yields plain dicts (not TX objects). `ActorModel.handler()` wraps them in TX envelopes. The agent layer has no TX dependency in its output format, maintaining clean separation of concerns.

**S4: Frontend component hierarchy.**
`NTTMethod -> NTTStream -> NTTStreamAgent -> (NTTAgentLive, NTTChat)` is a clean Template Method hierarchy. `NTTStream.STREAM()` provides the dispatch skeleton; subclasses override UPPERCASE handlers for custom rendering. Convention-based (`data.name.toUpperCase()`), extensible without code changes.

**S5: `@expose_route(stream=True)` as single declaration point.**
One decorator marks a method as streaming, controls schema emission (`proto_model.py:202-203`), route registration (`network_api.py:398-403`), and Level 1/2 detection. The `events={}` parameter further declares stream event vocabulary with full JSON Schema per event type.

**S6: Frontend cleanup discipline.**
`NTTStream.disconnectedCallback()` at `ntx-stream.js:156-159` automatically cancels streams when the component is removed from the DOM. All three streaming components properly clear timers on disconnect. The `finally` block in `NetworkAdapter.stream()` ensures backend cleanup.

### Design Trade-offs

**T1: Full TX envelope in Level 3 SSE vs. bare data in Level 1/2.**
Level 3 sends the full TX envelope (name, source, target, data, meta, timestamp, uuid) because it preserves routing metadata useful for debugging and for the frontend Matrix dispatch. Level 1/2 sends bare data because it has no actor layer. This was a deliberate design choice (documented in `_sse_from_stream()` docstring at `network_api.py:469-473`), but it creates a consistency gap that makes frontend code level-dependent. The trade-off no longer makes sense: the complexity cost exceeds the debugging benefit, and unification is feasible. **Addressed by P8.**

**T2: `NTTAgentLive` extends `NTTStream` instead of `NTTStreamAgent`.**
`NTTAgentLive` has a distinct panel UI (header, input, footer) that differs from `NTTStreamAgent`'s inline method-card rendering. It was likely easier to start from `NTTStream` and copy the rendering logic than to refactor `NTTStreamAgent` for composition. This trade-off sacrificed DRY for development speed. With three components now sharing ~80% identical code, the maintenance cost has grown to where extraction is clearly warranted. **Addressed by P4.**

**T3: Async generator detection at runtime vs. declaration.**
Level 1/2 detects streaming by inspecting the return value (`inspect.isasyncgen(result)` at `routes_fastapi.py:340`) rather than checking the `stream=True` declaration. This means a method can omit `stream=True` and still work at Level 1/2 -- but fail silently at Level 3 where the declaration gates route registration. The trade-off was convenience over correctness. Auto-detection from function inspection at decorator time would resolve this. **Addressed by P1.**

**T4: SSE over POST via `fetch()` instead of `EventSource`.**
The browser's `EventSource` API only supports GET requests. Since streaming methods need POST with JSON body, N3TX uses `fetch()` + `ReadableStream` (`HTTP.js:353-400`). This loses `EventSource`'s built-in reconnection but is the correct choice for the use case. No SSE keepalive/heartbeat compensates for the lost auto-reconnection. **Related to F8.**

**T5: Dicts over TX in `run_stream()` yield.**
`run_stream()` yields plain dicts (`{name, data, meta}`), not TX dataclass instances. `ActorModel.handler()` wraps them in TX envelopes. This keeps the agent layer independent of the actor system -- good for testability and portability. However, it means the error path is inconsistent: `run_stream()` yields an error dict that `handler()` wraps as a normal chunk TX, losing the error semantics. The trade-off is clean separation at the cost of error fidelity. **Related to F3.**

**T6: `events={}` as schema-only vs. runtime-validated.**
The `events` parameter on `@expose_route` generates JSON Schema entries in `methods[m].events` but does not validate that yielded chunks match the declared event models. This was an intentional design decision: validation adds overhead per chunk and the schema is primarily for frontend discovery. The trade-off is permissiveness over strictness -- a method can declare event types it never yields, or yield types it never declared, with no error. **Related to F12.**

### Improvement Opportunities

| # | Improvement | Impact | Effort | Category |
|---|-------------|--------|--------|----------|
| 1 | Auto-detect `stream=True` from async generator inspection | Medium | Low (0.5d) | DX |
| 2 | Centralize timeout config in `config.py` | Medium | Low (0.5d) | Ops |
| 3 | Add `TX.stream_from()` helper to eliminate seq boilerplate | Medium | Low (0.5d) | DX |
| 4 | Add SSE keepalive comments for proxy compatibility | Medium | Low (0.5d) | Resilience |
| 5 | Remove deprecated `sendStream()` from `NetworkAdapter.js:177-181` | Low | Low (0.5h) | Cleanup |
| 6 | Remove dead `custom_method` code in `routes_fastapi.py:488-518` | Low | Low (0.5h) | Cleanup |
| 7 | Replace deprecated `parse_obj` with `model_validate` at `routes_fastapi.py:325` | Low | Low (0.5h) | Compat |
| 8 | Incremental markdown rendering in `NTTStreamAgent` | Medium | Medium (1d) | Perf |
| 9 | Schema-driven event dispatch fallback in `NTTStream.STREAM()` | Medium | Low (1d) | Extensibility |
| 10 | Add WS streaming integration tests | High | Low (1d) | Coverage |

---

## Strategic Propositions

### Simplification Propositions

#### P1: Auto-Detect `stream=True` from Async Generator Inspection

- **Current state:** `decorators.py:13-88` requires explicit `stream=True`. Level 1/2 ignores it and detects at runtime (`routes_fastapi.py:340`). Level 3 requires it for route registration (`network_api.py:398`). A method can work at Level 1/2 without `stream=True` but break at Level 3.
- **Proposed change:**
  ```python
  # decorators.py — infer stream from function type
  def expose_route(route, methods=["POST"], access=None, stream=None, events=None):
      def decorator(func):
          _stream = stream
          if _stream is None:
              _stream = inspect.isasyncgenfunction(func)
          wrapper.__endpoint__ = {'stream': _stream, ...}
  ```
- **What gets simpler:** One fewer declaration for every streaming method. Eliminates the Level 1/2 vs Level 3 declaration mismatch. Developers just `yield` and it works.
- **Migration path:** Change `stream` default from `False` to `None`. Existing `stream=True` continues working. Existing `stream=False` (explicit opt-out) continues working. No breaking change.
- **Risk:** Low. A method that accidentally yields would now be detected as streaming -- but async generators are always intentional.

#### P2: `TX.stream_from()` Helper

- **Current state:** Every streaming call site manually tracks a `seq` counter. `actor_model.py:154-160` and `mixin.py:505+` both have identical `seq = 0; seq += 1` boilerplate. No consumer reads `meta.seq` for ordering -- it is purely diagnostic.
- **Proposed change:**
  ```python
  # tx.py — async generator wrapper
  async def stream_from(self, gen):
      """Wrap an async generator into chunk/end TX sequence."""
      seq = 0
      try:
          async for item in gen:
              data = item if isinstance(item, dict) else {'chunk': item}
              yield self.chunk(data, seq)
              seq += 1
      except Exception as e:
          yield self.exception(e)
          return
      yield self.end(seq=seq)
  ```
  Then `actor_model.py:152-164` collapses to:
  ```python
  if inspect.isasyncgen(result):
      async for chunk_tx in tx.stream_from(result):
          await target.send(chunk_tx)
      return
  ```
- **What gets simpler:** Eliminates seq boilerplate in every streaming call site. Centralizes error handling for generator exceptions.
- **Migration path:** Additive -- new method on TX; existing `chunk()`/`end()` unchanged. Callers that need custom seq logic continue using them directly.
- **Risk:** Low. The helper is a convenience wrapper, not a behavioral change.

#### P3: Remove Dynamic Handler Alias in NTTStream

- **Current state:** `ntx-stream.js:49-56` binds a dynamic property `this[methodName] = (data, tx) => this.STREAM(data, tx)` so reply TXs named after the method route to the unified STREAM handler.
- **Proposed change:** Route based on `meta.stream` flag rather than method name:
  ```javascript
  // In Component.js or NTTStream inbox override
  inbox(tx) {
      if (tx.meta?.stream || tx.meta?.stream_end) {
          return this.STREAM(tx.data, tx);
      }
      // ... normal dispatch
  }
  ```
- **What gets simpler:** Eliminates the alias hack, the `#boundHandler` tracking, and the cleanup logic. Stream routing becomes transparent.
- **Migration path:** Remove alias code from `callMethod()`. Add stream check to inbox. All UPPERCASE handlers unchanged.
- **Risk:** Medium. Requires `meta.stream` to be present on all stream TXs (it already is via `tx.chunk()` at `tx.py:53`). Needs careful testing of both HTTP and WS paths.

### Composability & Extensibility Propositions

#### P4: Extract `AgentEntryRenderer` from Three Duplicated Components

- **Current friction:** Adding a new agent event type (e.g., `PROGRESS`) requires editing three files (`ntx-stream-agent.js`, `ntx-agent-live.js`, `ntx-chat.js`). A bug fix in markdown rendering must be applied three times. The components share ~80% identical handler code but differ in DOM layout (`.agent-output` vs `.live-log` vs `.chat-messages`).
- **Proposed design:**
  ```javascript
  // AgentEntryRenderer.js — owns event-to-DOM, not layout
  export class AgentEntryRenderer {
      #toolCards = new Map();
      #textBuf = ''; #textRendered = 0; #textTimer = null;
      #thinkBuf = ''; #thinkRendered = 0; #thinkTimer = null;

      constructor(container, options = {}) {
          this.container = container;  // DOM element to append entries into
      }

      thinking(data)    { /* create/update thinking entry */ }
      toolCall(data)    { /* create tool card with spinner */ }
      toolResult(data)  { /* complete tool card */ }
      text(data)        { /* accumulate text, schedule markdown render */ }
      done(data)        { /* render usage footer */ }
      error(data)       { /* render error entry */ }
      reset()           { /* clear all state */ }
      flush()           { /* force pending renders */ }
      destroy()         { /* clear timers */ }

      static styles     // Shared CSS for entries
  }
  ```
  Components become thin wrappers:
  ```javascript
  class NTTStreamAgent extends NTTStream {
      #renderer;
      callMethod() {
          this.#renderer = new AgentEntryRenderer(this.querySelector('.agent-output'));
          super.callMethod();
      }
      THINKING(data) { this.#renderer.thinking(data); }
      TEXT(data)     { this.#renderer.text(data); }
      DONE(data)     { this.#renderer.done(data); }
      // ...
  }
  ```
- **What it enables:** New agent UI components (e.g., `ntx-agent-sidebar`) get rich agent rendering for free. New event types require changes in one file. Bug fixes propagate automatically.
- **Effort estimate:** Medium (2-3 days). Extract, refactor NTTStreamAgent first (smallest surface), then NTTAgentLive and NTTChat in parallel.

#### P5: Schema-Driven Event Dispatch in NTTStream

- **Current friction:** Stream event dispatch is purely method-based (`this[name](data.data, data.meta)` at `ntx-stream.js:29`). The schema carries typed event definitions in `methods[m].events` but the frontend never reads them. Unknown events fall through to `TEXT()` silently.
- **Proposed design:**
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
      const label = schema.title || name;
      this.#addEntry('generic', `${label}: ${JSON.stringify(data)}`);
  }
  ```
- **What it enables:** New event types declared via `events={}` on `@expose_route` get automatic rendering without frontend code changes. The schema becomes the true contract for stream events, not just documentation.
- **Effort estimate:** Small (1 day). Additive change -- existing UPPERCASE handlers take priority.

### Configuration Propositions

#### P9: Centralize Timeout Configuration

- **Current state:** Timeout values are hardcoded in seven locations across four files:
  | Location | Value | Purpose |
  |----------|-------|---------|
  | `network_adapter.py:79` | 30.0s | `request()` timeout |
  | `network_adapter.py:118` | 120.0s | `stream()` timeout |
  | `network_api.py:158` | 10.0s | Schema request timeout |
  | `network_api.py:186,236,269,306,344` | 30.0s | CRUD request timeout |
  | `network_api.py:477` | 120.0s | SSE stream timeout |
  | `network_ws.py:204` | 30.0s | WS request timeout |
  | `network_ws.py:214` | 120.0s | WS stream timeout |
- **Proposed change:**
  ```python
  # config.py — add timeout defaults
  REQUEST_TIMEOUT = float(os.getenv('N3TX_REQUEST_TIMEOUT', '30.0'))
  STREAM_TIMEOUT = float(os.getenv('N3TX_STREAM_TIMEOUT', '120.0'))
  SCHEMA_TIMEOUT = float(os.getenv('N3TX_SCHEMA_TIMEOUT', '10.0'))
  ```
  Then reference `config.STREAM_TIMEOUT` instead of magic numbers. Addresses F9.
- **Migration path:** Replace hardcoded values with config references. No behavior change with default values. Environment variables enable runtime tuning for different deployments (e.g., `N3TX_STREAM_TIMEOUT=300` for complex agent workloads).
- **Risk:** Very low. Default values preserve current behavior.

#### P10: SSE Keepalive Comments

- **Current state:** No heartbeat mechanism for HTTP SSE connections. The WS transport has heartbeats (`Socket.js:148`), but SSE does not. Intermediate proxies (nginx, load balancers) may close idle connections during long pauses (e.g., during LLM tool calls that take 10-30 seconds).
- **Proposed change:**
  ```python
  # network_api.py — add keepalive to _sse_from_stream
  async def _sse_from_stream(adapter, tx, timeout=120.0):
      async for chunk in adapter.stream(tx, timeout=timeout):
          yield f"event: chunk\ndata: {json.dumps(asdict(chunk), default=str)}\n\n"
          # ... existing logic
      # Between chunks, emit SSE comment as keepalive:
      # yield ": keepalive\n\n"
  ```
  SSE comments (lines starting with `:`) are ignored by SSE parsers but keep the TCP connection alive.
- **Risk:** Very low. SSE comments are part of the spec and explicitly ignored by clients.

### Resilience Propositions

#### P6: Server-Side Stream Cancellation

- **Current failure mode:** `NTTStream.cancel()` at `ntx-stream.js:138-154` sends a `STREAM_CANCEL` TX, but no backend handler processes it. The backend async generator runs to completion. For agent streams with multi-step tool calls, this wastes 30+ seconds of compute.
- **Proposed improvement:**
  Phase 1 -- SSE disconnect detection (immediate win, no protocol change):
  ```python
  # network_api.py — detect client disconnect in _sse_from_stream
  async def _sse_from_stream(adapter, tx, request):
      async for chunk in adapter.stream(tx, timeout=120.0):
          if await request.is_disconnected():
              return  # Client gone, stop streaming
          # ... yield SSE
  ```
  Phase 2 -- STREAM_CANCEL handler:
  ```python
  # network_adapter.py — handle cancellation TX
  async def inbox(self, tx):
      if tx.name == 'STREAM_CANCEL':
          req = tx.meta.get('req')
          if req in self._pending:
              cancel_event = self._pending[req].get('cancel')
              if cancel_event:
                  cancel_event.set()
          return
      # ... existing correlation logic
  ```
  Phase 3 -- Thread cancellation to generator:
  ```python
  # actor_model.py — check cancellation between chunks
  if inspect.isasyncgen(result):
      cancel = tx.meta.get('_cancel_event')
      seq = 0
      async for chunk in result:
          if cancel and cancel.is_set():
              await target.send(tx.end(seq=seq))
              return
          await target.send(tx.chunk(chunk, seq))
          seq += 1
  ```
- **Blast radius reduction:** Phase 1 alone stops wasted SSE serialization. Phase 2+3 stops wasted compute from the generator itself. Each phase is independently deployable.

#### P7: Level 1/2 SSE Error Event

- **Current failure mode:** Generator exception in Level 1/2 terminates the SSE connection with no error signal. Client sees truncated stream.
- **Proposed improvement:**
  ```python
  # routes_fastapi.py — wrap generator with error handling
  async def sse(_gen=result):
      try:
          async for chunk in _gen:
              data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
              yield f"event: chunk\ndata: {json.dumps(data, default=str)}\n\n"
          yield f"event: done\ndata: {{}}\n\n"
      except Exception as e:
          err = {'message': str(e), 'code': 500}
          yield f"event: error\ndata: {json.dumps(err)}\n\n"
  ```
- **Blast radius reduction:** Errors become visible to the frontend. `NTTStream.STREAM_ERROR()` can display them. The fix is identical for both `post_with_id` (line 341) and `post_no_id` (line 389).

#### P8: Unified SSE Wire Format

- **Current failure mode:** Frontend code written for Level 1/2 accesses `data.count` directly. The same code at Level 3 must access `data.data.count`. Switching routing levels silently breaks data access patterns.
- **Proposed improvement:** Level 1/2 wraps chunks in a minimal envelope:
  ```python
  # routes_fastapi.py — unified format
  seq = 0
  async def sse(_gen=result):
      nonlocal seq
      try:
          async for chunk in _gen:
              data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
              envelope = {'data': data, 'meta': {'stream': True, 'seq': seq}}
              yield f"event: chunk\ndata: {json.dumps(envelope, default=str)}\n\n"
              seq += 1
          yield f"event: done\ndata: {json.dumps({'data': {}, 'meta': {'stream_end': True}})}\n\n"
      except Exception as e:
          err = {'data': {'message': str(e), 'code': 500}, 'meta': {'error': True}}
          yield f"event: error\ndata: {json.dumps(err)}\n\n"
  ```
- **Blast radius reduction:** Frontend components work identically across all routing levels. Level 1/2 tests update from `e['data']['count']` to `e['data']['data']['count']` -- matching Level 3. The `httpCallback` in `NetworkAdapter.js` can be simplified to one code path.

### Proposition Priority Matrix

| # | Proposition | Simplifies | Impact | Effort | Risk | Enables | Dependencies |
|---|-------------|-----------|--------|--------|------|---------|--------------|
| P1 | Auto-detect `stream=True` | DX, declaration | Medium | Low (0.5d) | Low | Fewer bugs | None |
| P2 | `TX.stream_from()` helper | Backend boilerplate | Medium | Low (0.5d) | Low | Cleaner handlers | None |
| P3 | Remove dynamic alias | Frontend routing | Low | Low (0.5d) | Medium | Cleaner dispatch | Verify w/ P5 |
| P4 | `AgentEntryRenderer` extraction | Frontend DRY | **High** | Medium (2-3d) | Low | New agent UIs | None |
| P5 | Schema-driven event dispatch | Extensibility | Medium | Low (1d) | Low | Auto-rendering | None |
| P6 | Server-side cancellation | Resource waste | **High** | Medium (2-3d) | Low | Efficient agents | None |
| P7 | Level 1/2 SSE error event | Error visibility | **High** | Low (0.5d) | Low | Proper errors | None |
| P8 | Unified SSE wire format | Level consistency | **High** | Medium (1-2d) | Medium | Frontend compat | Test updates |
| P9 | Centralize timeout config | Ops, deployment | Medium | Low (0.5d) | Low | Tunable timeouts | None |
| P10 | SSE keepalive comments | Proxy resilience | Medium | Low (0.5d) | Low | Reliable long streams | None |

**Quick wins** (high impact, low effort): P7, P1, P2, P9, P10
**Strategic investments** (high impact, high effort, unlocks future work): P4, P6, P8
**Dependency chain:** P7 + P8 are best combined into single `_wrap_asyncgen_as_sse()` refactor. P5 validates P3 (schema dispatch replaces alias). P4 is fully independent. P9 and P10 are independent quick wins.
**Recommended sequence:** P7 -> P9 -> P10 -> P1 -> P2 -> P4 -> P6 -> P8 -> P5 -> P3

---

## Downstream Use Guide

### For Bug Hunting

**Known risk areas ranked by probability:**

1. **Level 1/2 streaming with failing generators** -- `routes_fastapi.py:341-345`. Any streaming method that queries external APIs (LLM, HTTP) can throw. The missing try/except means errors are invisible. Test: make a streaming method raise mid-stream and verify client behavior.

2. **Optional parameters on `@expose_route` methods** -- `routes_fastapi.py:316-322`. Methods with default values (e.g., `limit: int = 10`) will get spurious 400 errors at Level 1/2. Test: call a streaming method with optional params omitted.

3. **Agent stream error propagation** -- `mixin.py:685-691`. The error dict is wrapped as `tx.chunk()`, not recognized as an error by `_sse_from_stream()`. Test: trigger an LLM error during agent streaming and verify the frontend shows it as an error, not a text chunk.

4. **Concurrent stream requests** -- `ntx-stream.js:42-67`. Double-clicking a stream button creates orphaned backend tasks. Test: rapid double-click and check `_pending` dict size after both complete.

5. **WS stream tasks surviving client disconnect** -- `network_ws.py:201`. Background `_stream_to_ws()` tasks are fire-and-forget. If client disconnects, the task continues until adapter timeout or generator completion. Test: start WS stream, close connection, verify task terminates within reasonable time.

6. **`model_cls` in TX meta during Level 3 SSE** -- `network_api.py:513`. The `model_cls` class reference is included in TX meta and serialized via `dataclasses.asdict()`. With `default=str`, it becomes `"<class 'Product'>"` in the JSON output. Test: verify Level 3 SSE chunks do not contain class reference strings.

**Untested edge cases:**
- WebSocket streaming end-to-end (zero tests for `_stream_to_ws()`)
- Level 1/2 SSE with mid-stream exception
- Concurrent streams on the same adapter
- Stream with auth interceptor rejection
- Frontend behavior on backend timeout (120s)
- `model_cls` class reference leaking into Level 3 SSE JSON output

**Suggested test cases (with verification details):**

```python
# 1. Level 1/2 SSE error propagation (addresses F1)
# File: examples/core/tests/test_streaming.py
async def test_level12_sse_error_propagation(client):
    """Generator raises ValueError mid-stream; verify event: error is sent."""
    # Setup: streaming method that yields 2 chunks then raises
    response = client.post("/products/1/failing_stream", json={})
    events = parse_sse_events(response.text)
    assert len([e for e in events if e['event'] == 'chunk']) == 2
    error_events = [e for e in events if e['event'] == 'error']
    assert len(error_events) == 1
    assert 'message' in error_events[0]['data']

# 2. WebSocket streaming integration (addresses F5)
# File: packages/n3tx-actors/src/n3tx_actors/tests/test_ws_streaming.py
async def test_ws_streaming_chunk_delivery():
    """Exercise _stream_to_ws() with chunk/end/error scenarios."""
    # Create mock WebSocket, send stream TX, verify chunks arrive
    # Verify _translate_outgoing() adds meta.stream flags
    # Verify stream_end terminates the background task

# 3. Stream with auth interceptor (addresses F14)
# File: packages/n3tx-actors/src/n3tx_actors/tests/test_streaming.py
async def test_stream_with_auth_interceptor():
    """Verify unauthorized streaming request rejected before SSE starts."""
    # Setup: adapter with auth_interceptor, send stream TX without user
    # Verify: single error TX yielded, no Queue leak in _pending

# 4. Concurrent stream cleanup
# File: packages/n3tx-actors/src/n3tx_actors/tests/test_streaming.py
async def test_concurrent_stream_cleanup():
    """Two streams in rapid succession; verify _pending dict empty after both."""
    # Start stream A, immediately start stream B
    # Consume both to completion
    # Assert adapter._pending is empty

# 5. Optional params on streaming method (addresses F4)
# File: examples/core/tests/test_streaming.py
async def test_optional_params_streaming(client):
    """Call streaming method with optional params omitted; verify no 400."""
    # Method signature: async def stream(self, n: int = 5)
    response = client.post("/products/1/stream", json={})
    assert response.status_code == 200  # not 400

# 6. Agent stream error as error event (addresses F3)
# File: packages/n3tx-agents/src/n3tx_agents/tests/test_run_stream_error.py
async def test_agent_stream_error_is_error_event():
    """Verify LLM error in run_stream() produces event: error, not event: chunk."""
    # Setup: TestModel that raises on invocation
    # Verify: the error TX has is_error=True, not chunk wrapping
```

### For Feature Development

**Extension points with difficulty ratings:**

| Extension Point | Difficulty | Pattern to Follow |
|----------------|-----------|------------------|
| New stream event type | Easy | Yield `{'name': 'progress', 'data': {...}}` from generator; add `PROGRESS(data, meta)` handler to frontend component |
| Custom stream consumer component | Easy | Extend `NTTStream`; override UPPERCASE handlers. Template: `ntx-stream-agent.js` |
| New transport adapter with streaming | Moderate | Extend `NetworkAdapter`; get `stream()` for free. Template: `network_ws.py` |
| Custom stream event ProtoModels | Easy | Define non-storable ProtoModel; add to `events={}` on `@expose_route`. Template: `actor.py:41-65` |
| Per-chunk interceptors | Hard | Currently only pre-stream interceptors supported. Would require modifying `NetworkAdapter.stream()` yield loop |
| Bidirectional streaming | Hard | No current support. Requires new TX meta conventions and upstream Queue infrastructure |

**Patterns to follow (with file references):**

*Backend streaming method (simplest pattern):*
```python
# Template from examples/core/models/product.py
@expose_route('/countdown', methods=['POST'], stream=True, access=ANYONE)
async def countdown(self, n: int):
    for i in range(n, -1, -1):
        await asyncio.sleep(0.3)
        yield {'count': i, 'message': f'Counting: {i}'}
```
Key: method is an async generator, `stream=True` declared, each `yield` becomes an SSE chunk.

*Agent streaming method (typed events pattern):*

```python
# Template from n3tx-agents/actor.py:170-204
@expose_route('/agentic_stream', methods=['POST'], stream=True,
              events={'text': TextChunk, 'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent, 'done': DoneChunk})
async def agentic_stream(self, task: str, **kwargs):
    # Delegates to run_stream() which yields {name, data, meta} dicts
    async for chunk in self.call_stream(task=task, ...):
        yield chunk
```
Key: `events={}` declares vocabulary, `run_stream()` handles LLM iteration, each dict has `name` for dispatch.

*Frontend stream consumer (rich rendering pattern):*
```javascript
// Template from ntx-stream-agent.js
class MyStreamComponent extends NTTStream {
    THINKING(data, meta) { /* thinking indicator */ }
    TOOL_CALL(data, meta) { /* tool card with spinner */ }
    TEXT(data, meta) { /* text accumulation */ }
    DONE(data, meta) { /* final result */ }
    STREAM_END(data) { /* cleanup */ }
}
customElements.define('my-stream', MyStreamComponent);
```
Key: UPPERCASE methods match `data.name` from backend. Unknown names fall through to `TEXT()`.

**Constraints to be aware of before starting:**
- **No backpressure.** The `asyncio.Queue` in `NetworkAdapter.stream()` is unbounded. If your generator produces chunks faster than the client can consume them, memory grows without limit. For batch-processing streams, add explicit `asyncio.sleep()` or process in bounded batches.
- **No stream resumption.** If the SSE connection drops mid-stream, there is no way to resume from the last received `meta.seq`. The client must re-invoke the method. The `meta.seq` numbers could enable resume logic, but no infrastructure exists for it.
- **120-second default timeout.** `NetworkAdapter.stream()` times out after 120 seconds of idle time (no chunks). Agent streams with complex multi-tool chains can exceed this. Currently not configurable without code changes (see F9).
- **Single consumer per stream.** Each stream has exactly one consumer (the requesting adapter). There is no fanout/broadcast mechanism. If you need multiple clients to observe the same stream, you must implement pub/sub on top.
- **In-memory correlation only.** Stream correlation (`_pending` dict in `NetworkAdapter`) is entirely in-memory. Server restart loses all active stream state.
- **Auth checked once at stream initiation.** JWT is validated when the stream request arrives. If the token expires during a long-running stream, the stream continues with the original auth context (`network_ws.py:287-292`).

**Common pitfalls:**
- Forgetting `stream=True` on `@expose_route` -- works at Level 1/2, breaks at Level 3 (F11)
- Accessing SSE data differently per level -- `data.count` vs `data.data.count` (F2)
- Not handling the `done` event -- stream appears to hang
- Using `events={}` and expecting runtime validation -- it is schema-only (F12)
- Double-clicking stream buttons without UI disabling -- creates orphaned backend tasks (F13)
- Expecting `cancel()` to stop backend processing -- it only stops frontend consumption (F7)
- Using `param: int = 5` with Level 1/2 routes -- optional params trigger 400 errors (F4)

### For Integration Planning

**Integration boundaries with data contracts:**

| Boundary | Direction | Data Contract | Stability |
|----------|-----------|---------------|-----------|
| Python method -> async generator | Backend-internal | `yield dict \| any` | Stable |
| Async generator -> TX chunks | Backend-internal | `TX.chunk(data, seq)` -> TX dataclass | Stable |
| TX chunks -> Queue correlation | Backend-internal | `meta.req` maps to `_pending[uuid]` | Stable |
| Queue -> SSE wire format | Backend -> Frontend | `event: chunk\|done\|error`, `data: JSON` | **Unstable** (format differs by level) |
| SSE wire -> `HTTP.stream()` | Transport | `onChunk(parsed)`, `onDone(parsed)`, `onError(parsed)` | Stable |
| Matrix dispatch -> UPPERCASE handlers | Frontend-internal | `data.name.toUpperCase()` -> `this[NAME]()` | Stable |
| WS stream bridge | Backend -> Frontend | TX translated via `_translate_outgoing()` | Stable but undertested |

**Dependencies and stability assessment:**

| Dependency | Package | Stability | Risk if Changed |
|------------|---------|-----------|----------------|
| `TX` dataclass | n3tx-actors | Very stable (unchanged since v0.9) | High -- all streaming components depend on it |
| `asyncio.Queue` / `asyncio.Future` | stdlib | Stable | None |
| `FastAPI StreamingResponse` | n3tx-core (via FastAPI) | Stable | Low -- standard ASGI pattern |
| `pydantic-ai Agent.iter()` | n3tx-agents (via pydantic-ai) | Active development | Medium -- API changes could break `run_stream()` |
| `fetch() + ReadableStream` | Browser APIs | Stable (Web standard) | None |
| `marked` library (optional) | n3tx-agents (implicit) | Stable | Low -- graceful fallback to plain text |

**Impact analysis checklist when changing this subsystem:**
- [ ] Does the change affect SSE wire format? If so, update both Level 1/2 and Level 3
- [ ] Does the change add a new event type? Update all three agent components (or `AgentEntryRenderer` after P4)
- [ ] Does the change modify `TX.chunk()` or `TX.end()`? Check `ActorModel.handler()`, `run_stream()`, and all streaming tests
- [ ] Does the change affect `NetworkAdapter.stream()`? Check SSE (`_sse_from_stream`), WS (`_stream_to_ws`), and all adapter tests
- [ ] Does the change affect `@expose_route`? Check both `routes_fastapi.py` and `network_api.py` route registration
- [ ] Does the change touch frontend stream dispatch? Verify with both HTTP (SSE) and WebSocket transports
- [ ] Does the change affect error handling? Test both generator exceptions and external API failures

**Compatibility considerations for connecting new subsystems:**
- New transport adapters (e.g., gRPC, MQTT) get streaming for free by extending `NetworkAdapter` -- the `stream()` method is transport-agnostic. Only the serialization step (equivalent to `_sse_from_stream`) needs per-transport implementation.
- New frontend frameworks (React, Vue) consuming streams need only implement the SSE parsing from `HTTP.stream()`. The `onChunk`/`onDone`/`onError` callback contract is simple and framework-agnostic.
- The `meta.stream`, `meta.stream_end`, `meta.seq`, and `meta.req` conventions in TX meta are the integration contract. Any system that reads and writes these correctly can participate in streaming.
- **Warning:** If connecting at the SSE wire level, be aware of the Level 1/2 vs Level 3 format divergence (F2). Until P8 is implemented, consumers must handle both bare data and TX envelope formats.

**Complete integration example: Adding SSE streaming to a new transport (e.g., Server-Side Events over HTTP/2):**

```python
# 1. Backend: Extend NetworkAdapter (get stream() for free)
class NetworkHTTP2(NetworkAdapter):
    async def _send_stream_to_client(self, request, tx):
        async for chunk in self.stream(tx, timeout=config.STREAM_TIMEOUT):
            if chunk.is_error:
                yield self._format_error(chunk)
                return
            if chunk.meta.get('stream_end'):
                yield self._format_done(chunk)
                return
            yield self._format_chunk(chunk)

# 2. Frontend: Implement SSE parsing (follow HTTP.stream() pattern)
# Parse event:/data: lines, call onChunk/onDone/onError callbacks

# 3. Register adapter with Matrix
# matrix.register(NetworkHTTP2(addr='http2_api'))
```

The key integration points are: (a) `NetworkAdapter.stream()` yields TX chunks, (b) the consumer decides serialization format, (c) `meta.stream_end` and `is_error` control termination.

### For Refactoring

**Technical debt items ranked by severity and coupling risk:**

| # | Debt Item | Severity | Coupling | Suggested Fix |
|---|-----------|----------|----------|--------------|
| 1 | Code duplication across 3 agent components | High | Low (frontend-only) | Extract `AgentEntryRenderer` (P4) |
| 2 | Two SSE wire formats | High | High (spans backend + frontend + tests) | Unify envelope (P8) |
| 3 | Level 1/2 SSE wrapper duplication (`post_with_id` / `post_no_id`) | Medium | Low | Extract `_wrap_asyncgen_as_sse()` helper |
| 4 | Dead `custom_method` code in `routes_fastapi.py:488-518` | Low | None | Delete |
| 5 | Deprecated `sendStream()` in `NetworkAdapter.js:177-181` | Low | None | Delete |
| 6 | Deprecated `parse_obj` usage at `routes_fastapi.py:325` | Low | None | Replace with `model_validate` |
| 7 | `test_streaming_shutdown.py:77` uses deprecated `stream_end()` alias | Low | None | Replace with `end()` |

**Suggested refactoring sequence (dependency order):**
1. **P7**: Add error handling to Level 1/2 SSE (standalone, no deps) -- Risk: Low, confined to `routes_fastapi.py`
2. **Extract `_wrap_asyncgen_as_sse()`** to deduplicate SSE wrapper in `routes_fastapi.py` -- Risk: Low, behavior-preserving refactor
3. **P8**: Unify SSE wire format (depends on step 2 for clean implementation) -- Risk: Medium, requires Level 1/2 test assertion updates and frontend verification
4. **P4**: Extract `AgentEntryRenderer` (independent, can parallel with steps 1-3) -- Risk: Low, behavior-preserving extraction
5. **P2**: Add `TX.stream_from()` and refactor `ActorModel.handler()` to use it -- Risk: Low, new method on TX, opt-in usage
6. **P6**: Server-side cancellation (depends on P2 for cleaner implementation) -- Risk: Low for Phase 1 (disconnect detection), Medium for Phase 2-3 (cancellation protocol)
7. **Cleanup**: Delete dead code, deprecated aliases, update tests -- Risk: Very low

**Before/after sketch for major candidate -- Level 1/2 SSE wrapper:**

Before (`routes_fastapi.py:340-349`):
```python
if inspect.isasyncgen(result):
    async def sse(_gen=result):
        async for chunk in _gen:
            data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
            yield f"event: chunk\ndata: {json.dumps(data, default=str)}\n\n"
        yield f"event: done\ndata: {{}}\n\n"
    return StreamingResponse(sse(), ...)
```

After:
```python
if inspect.isasyncgen(result):
    return StreamingResponse(
        _wrap_asyncgen_as_sse(result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# Extracted helper (used by both post_with_id and post_no_id)
async def _wrap_asyncgen_as_sse(gen):
    seq = 0
    try:
        async for chunk in gen:
            data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
            envelope = {'data': data, 'meta': {'stream': True, 'seq': seq}}
            yield f"event: chunk\ndata: {json.dumps(envelope, default=str)}\n\n"
            seq += 1
        yield f"event: done\ndata: {json.dumps({'data': {}, 'meta': {'stream_end': True}})}\n\n"
    except Exception as e:
        err = {'data': {'message': str(e), 'code': 500}, 'meta': {'error': True}}
        yield f"event: error\ndata: {json.dumps(err)}\n\n"
```

This single refactoring addresses F1 (error handling), F2 (wire format), and the SSE wrapper duplication -- three findings with one change.

**Before/after sketch for major candidate -- AgentEntryRenderer extraction (P4):**

Before (`ntx-stream-agent.js` -- one of three files with near-identical code):
```javascript
class NTTStreamAgent extends NTTStream {
    #toolCards = new Map();
    #textBuf = ''; #textRendered = 0; #textTimer = null;
    #thinkBuf = ''; #thinkRendered = 0; #thinkTimer = null;

    THINKING(data, meta) {
        // ~15 lines of thinking entry creation/update
    }
    TOOL_CALL(data, meta) {
        // ~20 lines of tool card creation
    }
    TOOL_RESULT(data, meta) {
        // ~15 lines of tool card completion
    }
    TEXT(data, meta) {
        // ~15 lines of text accumulation + render scheduling
    }
    DONE(data, meta) {
        // ~10 lines of usage footer
    }
    #scheduleRender(kind) { /* debounce logic */ }
    #renderMd(entry, kind) { /* marked.parse() call */ }
    #flushRender() { /* force pending renders */ }
    #addEntry(type, html) { /* DOM entry creation */ }
    #setThinking(active) { /* thinking toggle */ }
    #esc(str) { /* HTML escaping */ }
    // Total: ~350 lines, ~250 of which are duplicated in NTTAgentLive and NTTChat
}
```

After:
```javascript
// AgentEntryRenderer.js — shared rendering primitive (~200 lines)
export class AgentEntryRenderer {
    #toolCards = new Map();
    #textBuf = ''; #textRendered = 0; #textTimer = null;
    #thinkBuf = ''; #thinkRendered = 0; #thinkTimer = null;
    #container;

    constructor(container) { this.#container = container; }

    thinking(data) { /* extracted from NTTStreamAgent.THINKING */ }
    toolCall(data) { /* extracted from NTTStreamAgent.TOOL_CALL */ }
    toolResult(data) { /* extracted from NTTStreamAgent.TOOL_RESULT */ }
    text(data) { /* extracted from NTTStreamAgent.TEXT */ }
    done(data) { /* extracted from NTTStreamAgent.DONE */ }
    reset() { /* clear all state and DOM */ }
    flush() { /* force pending renders */ }
    destroy() { /* clear timers */ }

    static get styles() { /* shared CSS for entries */ }
}

// ntx-stream-agent.js — thin wrapper (~50 lines)
class NTTStreamAgent extends NTTStream {
    #renderer;
    callMethod() {
        const output = this.querySelector('.agent-output') || this.#createOutput();
        this.#renderer = new AgentEntryRenderer(output);
        super.callMethod();
    }
    THINKING(data) { this.#renderer.thinking(data); }
    TOOL_CALL(data) { this.#renderer.toolCall(data); }
    TOOL_RESULT(data) { this.#renderer.toolResult(data); }
    TEXT(data) { this.#renderer.text(data); }
    DONE(data) { this.#renderer.done(data); }
    STREAM_END(data) { this.#renderer.flush(); super.STREAM_END(data); }
    disconnectedCallback() { this.#renderer?.destroy(); super.disconnectedCallback(); }
}

// ntx-agent-live.js — thin wrapper + panel chrome (~100 lines)
class NTTAgentLive extends NTTStream {
    #renderer;
    prerender() {
        // Panel UI: header, input, log area, footer
        this.#renderer = new AgentEntryRenderer(this.querySelector('.live-log'));
    }
    THINKING(data) { this.#renderer.thinking(data); }
    // ... same thin delegation
}
```

Net effect: ~500 lines of duplicated code become ~200 lines of shared renderer + ~150 lines across three thin wrappers. New agent UI components get rendering for free by instantiating `AgentEntryRenderer` with their own container DOM element.

**Before/after sketch for `TX.stream_from()` (P2):**

Before (`actor_model.py:152-164`):
```python
if inspect.isasyncgen(result):
    seq = 0
    try:
        async for chunk in result:
            chunk_data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
            await target.send(tx.chunk(chunk_data, seq))
            seq += 1
    except Exception as e:
        await target.send(tx.exception(e))
        return
    await target.send(tx.end(seq=seq))
    return
```

After:
```python
if inspect.isasyncgen(result):
    async for chunk_tx in tx.stream_from(result):
        await target.send(chunk_tx)
    return
```

The `stream_from()` method encapsulates seq tracking, error handling, and termination in a single reusable primitive on `TX`.

---

## Appendix: Error Propagation Chain

Understanding how errors flow through the streaming subsystem is critical for debugging. This is the consolidated error propagation map across all levels.

```
Error Origin             Backend Handler              Wire Format                Frontend Handler
─────────────           ─────────────────            ────────────              ─────────────────

Model method throws     ActorModel.handler()          tx.exception(e)           event: error
(L3: actor_model:143)   try/except → error TX         → _sse_from_stream()     → STREAM_ERROR()
                                                      → event: error\ndata:{TX}  → toast

Model method throws     routes_fastapi.py             **NO ERROR EVENT**        Truncated stream
(L1/2: routes:341)      **NO try/except** (BUG F1)    Stream ends abruptly      No notification

Async gen raises        ActorModel.handler()          tx.exception(e)           event: error
(L3: actor_model:161)   try/except in stream loop     **No tx.end() sent**      → STREAM_ERROR()

run_stream() LLM err    mixin.py:685 catches          yield error dict          event: chunk (!)
                        Yields {name:'error',...}      → tx.chunk() wraps it     Not recognized as
                        **BUG: not raised (F3)**       → event: chunk            error by frontend

NetworkAdapter timeout  stream() timeout handler      tx.error(msg, code=504)   event: error
(adapter:152-155)       asyncio.TimeoutError           → _sse_from_stream()     → STREAM_ERROR()

_sse_from_stream()      **No catch**                  Propagates to ASGI        HTTP 500
JSON serialization err  (network_api:478)              FastAPI closes response   Truncated stream

WS _stream_to_ws()      try/except (ws:221-230)       ws.send_json(error)       WS error message
raises                  Catches Exception              Best-effort delivery      May be lost

Frontend fetch error    HTTP.stream() catch            N/A                       onError callback
(HTTP.js:390-396)       .catch() on reader/fetch                                → STREAM_ERROR()
```

**Key insight:** The error propagation is robust for Level 3 (actor-routed) but has two significant gaps:
1. Level 1/2 has no mid-stream error event (F1) -- the stream truncates silently
2. Agent stream errors escape as chunks instead of error TXs (F3) -- the error is not recognized as such by the SSE serializer

Both are addressed by propositions P7 (Level 1/2 error handling) and P2/F3 fix (raise instead of yield in `run_stream()`).

---

## Appendix: Cross-Reference Matrix

### Findings Addressed by Propositions

| Finding | Addressed by | How |
|---------|-------------|-----|
| F1 (L1/2 SSE no error handling) | **P7** | Adds try/except to SSE wrapper |
| F2 (SSE wire format divergence) | **P8** | Unifies envelope shape |
| F3 (run_stream error as chunk) | **P2** (partial) | `stream_from()` centralizes error handling |
| F6 (frontend duplication) | **P4** | Extracts shared renderer |
| F7 (STREAM_CANCEL unhandled) | **P6** | Implements server-side cancellation |
| F9 (hardcoded timeouts) | Improvement #2 | Centralize in `config.py` |
| F11 (stream=True optional) | **P1** | Auto-detect from function type |
| F13 (double-invocation) | P4 side-effect | Renderer reset handles state cleanup |

### Propositions That Address Multiple Findings

| Proposition | Findings Addressed | Synergy Notes |
|-------------|-------------------|---------------|
| P7 + P8 combined | F1, F2, SSE wrapper duplication | Implement as single `_wrap_asyncgen_as_sse()` refactor |
| P4 | F6, F10 | Extraction fixes duplication and enables incremental markdown fix in one place |
| P2 | F3 (partial), seq boilerplate | Centralizes error-to-TX conversion |

---

## Appendix: Complete Finding Index

| ID | Dimension | Type | Severity | Finding/Proposition | File(s) | Status |
|----|-----------|------|----------|---------------------|---------|--------|
| F1 | Quality, API | Finding | Critical | Level 1/2 SSE has no error handling for generator exceptions | `routes_fastapi.py:341-345` | Open |
| F2 | Architecture, API | Finding | High | SSE wire format diverges between Level 1/2 and Level 3 | `routes_fastapi.py:343` vs `network_api.py:478-485` | Open |
| F3 | Architecture, Quality | Finding | High | `run_stream()` error dict escapes as chunk, not error TX | `mixin.py:685-691`, `actor_model.py:157-158` | Open |
| F4 | API, Quality | Finding | High | `_parse_method_args` treats all params as required (L1/2) | `routes_fastapi.py:316-322` | Open |
| F5 | Quality | Finding | Medium | WebSocket streaming has zero test coverage | `network_ws.py:207-230` | Open |
| F6 | Architecture | Finding | Medium | Code duplication across 3 frontend agent components | `ntx-stream-agent.js`, `ntx-agent-live.js`, `ntx-chat.js` | Open |
| F7 | Extensibility | Finding | Medium | `STREAM_CANCEL` TX sent by frontend, no backend handler | `ntx-stream.js:145-151` | Open |
| F8 | Quality | Finding | Medium | No SSE keepalive; proxies may kill idle connections | `network_api.py:517-518` (headers, no heartbeat) | Open |
| F9 | Quality | Finding | Medium | Hardcoded 120s stream timeout in 4 locations | `network_adapter.py:118`, `network_api.py:477`, `network_ws.py:214` | Open |
| F10 | Quality | Finding | Medium | O(n^2) markdown re-parsing on every text chunk | `ntx-stream-agent.js:207-221`, `ntx-agent-live.js:261-275` | Open |
| F11 | API | Finding | Medium | `stream=True` optional for Level 1/2, required for Level 3 | `routes_fastapi.py:340` vs `network_api.py:398` | Open |
| F12 | API | Finding | Medium | `events={}` is schema-only, no runtime validation | `decorators.py:82`, `proto_model.py:205-208` | Open |
| F13 | Quality | Finding | Medium | Frontend `callMethod()` has no guard against double-invocation | `ntx-stream.js:42-67` | Open |
| F14 | Security | Finding | Medium | Level 3 streaming methods without `access=` skip Tier 2 auth | `actor_model.py:100-115` | Open |
| F15 | API | Finding | Low | `HTTP.stream()` silently swallows malformed JSON | `HTTP.js:386` | Open |
| F16 | Quality | Finding | Low | `send_task` exception silently swallowed in `stream()` | `network_adapter.py:147` | Open |
| F17 | Quality | Finding | Low | `meta.model_cls` leaks class reference into Level 3 SSE | `network_api.py:513` | Open |
| F18 | Quality | Finding | Low | WS stream tasks not cancelled on client disconnect | `network_ws.py:201` | Open |
| F19 | Quality | Finding | Low | `dataclasses.asdict()` deep-copies every TX in Level 3 SSE | `network_api.py:478` | Open |
| F20 | API | Finding | Low | Deprecated `sendStream()` still exists | `NetworkAdapter.js:177-181` | Open |
| F21 | API | Finding | Low | `AgentActor.agentic_stream` reaches into descriptor internals | `actor.py:192` | Open |
| F22 | Quality | Finding | Low | `parse_obj` deprecated in Pydantic V2 | `routes_fastapi.py:325` | Open |
| F23 | Security | Finding | Low | Internal exception messages exposed via SSE error events | `routes_fastapi.py:351`, `mixin.py:689` | Open |
| P1 | Simplification | Proposition | -- | Auto-detect `stream=True` from async generator | `decorators.py:13-88` | Proposed |
| P2 | Simplification | Proposition | -- | `TX.stream_from()` helper | `tx.py:47-63` | Proposed |
| P3 | Simplification | Proposition | -- | Remove dynamic handler alias | `ntx-stream.js:49-56` | Proposed |
| P4 | Composability | Proposition | -- | Extract `AgentEntryRenderer` | 3 JS component files | Proposed |
| P5 | Composability | Proposition | -- | Schema-driven event dispatch | `ntx-stream.js:22-35` | Proposed |
| P6 | Resilience | Proposition | -- | Server-side stream cancellation | `network_adapter.py`, `actor_model.py` | Proposed |
| P7 | Resilience | Proposition | -- | Level 1/2 SSE error event | `routes_fastapi.py:341-345` | Proposed |
| P8 | Resilience | Proposition | -- | Unified SSE wire format | `routes_fastapi.py`, `network_api.py` | Proposed |
| P9 | Configuration | Proposition | -- | Centralize timeout config | `config.py`, 4 consumer files | Proposed |
| P10 | Resilience | Proposition | -- | SSE keepalive comments | `network_api.py`, `routes_fastapi.py` | Proposed |
