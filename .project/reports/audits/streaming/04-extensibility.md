# Streaming Subsystem Audit: Extensibility & Integration

**Auditor**: Claude Opus 4.6
**Date**: 2026-03-26
**Scope**: Full-stack streaming — backend protocol, actor plumbing, transport bridges, frontend consumers
**Dimension**: Extensibility, integration boundaries, dependency graph, evolution trajectory

---

## Dependency Graph

The streaming subsystem spans four packages. Arrows show "depends on" relationships.

```
                    ┌─────────────────────────────────────────┐
                    │           APPLICATION LAYER              │
                    │  examples/*/models.py                    │
                    │  apps/veille/models/*.py                 │
                    │  @expose_route(stream=True, events={})   │
                    └───────┬──────────────┬──────────────┬────┘
                            │              │              │
          ┌─────────────────▼──┐   ┌───────▼───────┐  ┌──▼──────────────┐
          │    n3tx-agents      │   │  n3tx-actors   │  │    n3tx-ui       │
          │                     │   │                │  │                  │
          │  mixin.py           │   │  tx.py         │  │  ntx-stream.js   │
          │   run_stream()      │   │   chunk()      │  │  ntx-method.js   │
          │   agentic_stream()  │   │   end()        │  │                  │
          │  actor.py           │   │  network_      │  └────────┬─────────┘
          │   AgentActor        │   │   adapter.py   │           │
          │   stream events     │   │   stream()     │           │
          │  ntx-stream-agent.js│   │  network_      │           │
          │  ntx-agent-live.js  │   │   api.py       │           │
          │  ntx-chat.js        │   │   _sse_from_   │           │
          └──────────┬──────────┘   │    stream()    │           │
                     │              │  network_      │           │
                     │              │   ws.py        │           │
                     │              │   _stream_to_  │           │
                     │              │    ws()        │           │
                     │              │  actor_model.py│           │
                     │              │   handler()    │           │
                     └──────┬───────┴───────┬────────┘           │
                            │               │                    │
                    ┌───────▼───────────────▼────────────────────▼──┐
                    │               n3tx-core                        │
                    │  routes_fastapi.py — Level 1/2 SSE             │
                    │  decorators.py     — @expose_route(stream=)    │
                    │  proto_model.py    — schema: methods[m].stream │
                    │  HTTP.js           — HTTP.stream() SSE client   │
                    │  NetworkAdapter.js — send() meta.stream routing │
                    │  Socket.js         — WS transport               │
                    └───────────────────────────────────────────────┘
```

### Inbound dependencies (what streaming depends on)

| Dependency | Used by | Coupling |
|---|---|---|
| `TX` dataclass | `chunk()`, `end()`, correlation via `meta.req` | **Tight** — TX is the message envelope; streaming is TX-native |
| `Actor.send()` | `ActorModel.handler()` sends chunks to Matrix | **Tight** — streaming IS actor messaging |
| `asyncio.Queue` / `asyncio.Future` | `NetworkAdapter.stream()` correlation | **Moderate** — stdlib, no custom abstraction |
| `FastAPI StreamingResponse` | `_sse_from_stream()`, `make_custom_post()` | **Moderate** — SSE wire format depends on FastAPI |
| `@expose_route` decorator | marks methods as `stream=True` | **Tight** — single declaration point |
| `pydantic-ai Agent.iter()` | `run_stream()` graph-based streaming | **Tight** — agent streaming deeply coupled to pydantic-ai |

### Outbound dependencies (what depends on streaming)

| Dependent | What it consumes | Coupling |
|---|---|---|
| Frontend `NTTStream` | UPPERCASE handlers from SSE/WS chunks | **Moderate** — contract is event names + data shapes |
| Frontend `NTTStreamAgent` | Typed events: text, tool_call, tool_result, thinking, done | **Tight** — hardcoded handler names |
| Frontend `NTTChat` | Same typed events as NTTStreamAgent | **Tight** — duplicates handler logic |
| Frontend `NTTAgentLive` | Same typed events | **Tight** — duplicates handler logic |
| Agent `agentic_stream()` | Calls `run_stream()` as async generator | **Tight** — direct function call |
| Schema pipeline | `methods[m].stream` flag, `methods[m].events` | **Loose** — schema carries the flag, consumers read it |

---

## Integration Boundaries

### Boundary 1: Python Method -> Async Generator

**What crosses it**: A Python method decorated with `@expose_route(stream=True)` returns an async generator. The framework detects `inspect.isasyncgen(result)` and iterates it.

**Data format**: Each `yield` produces a `dict` (or any value, wrapped in `{'chunk': value}` by TX.chunk()). No schema validation on individual chunks.

**Coupling**: Loose. The method author yields whatever they want. The framework wraps it.

**Stability**: Stable. This boundary has not changed since v0.9 (`5c06d3d`).

**Location**:
- Level 1/2: `routes_fastapi.py:340-349` (post_with_id) and `:389-397` (post_no_id)
- Level 3: `actor_model.py:152-164` (handler generic fallback)

### Boundary 2: Async Generator -> TX Stream Chunks

**What crosses it**: The `ActorModel.handler()` iterates the async generator and converts each yielded value into a `TX` via `tx.chunk(data, seq)`, then sends `tx.end(seq=N)`.

**Data format**: TX envelope with `meta: {req, stream: true, seq: N}` for chunks, `meta: {req, stream: true, stream_end: true, seq: N}` for termination.

**Coupling**: Tight. TX is the universal envelope. The `chunk()`/`end()` methods on TX are the sole API for constructing stream messages (`tx.py:47-63`).

**Stability**: Stable. `chunk()`/`end()` replaced `stream_chunk()`/`stream_end()` in v0.10 (`9281baa`), with backward-compat aliases at `tx.py:65-67`.

### Boundary 3: TX Stream Chunks -> NetworkAdapter Queue

**What crosses it**: TX chunks with `meta.req` matching a pending UUID route to `asyncio.Queue` entries in `NetworkAdapter.inbox()` (`network_adapter.py:57-77`).

**Data format**: Full TX dataclass instances.

**Coupling**: Moderate. The adapter doesn't know about stream chunk content — it only checks `meta.stream_end` and `is_error` to know when to stop. The Queue/Future type dispatch is a clean abstraction.

**Stability**: Stable. This was designed in v0.9 (`4bc8663`) and has not changed structurally.

### Boundary 4: NetworkAdapter.stream() -> SSE Wire Format

**What crosses it**: `_sse_from_stream()` in `network_api.py:469-485` serializes TX chunks into SSE text lines. The full TX envelope is serialized via `dataclasses.asdict()`.

**Data format**: SSE with `event: chunk|done|error`, `data: {json TX envelope}`.

**Key difference from Level 1/2**: Level 3 serializes the **full TX envelope** (name, source, target, data, meta, timestamp, uuid). Level 1/2 (`routes_fastapi.py:341-345`) serializes only `data` — no TX envelope wrapping. This is a **format inconsistency** between levels.

**Coupling**: Moderate. The SSE format is implicit (no schema). Frontend must know the structure.

**Stability**: Moderate. The Level 1/2 vs Level 3 format difference was partially addressed in test updates (`a3e9a48`) but the core divergence remains.

### Boundary 5: SSE Wire -> Frontend HTTP.stream()

**What crosses it**: `HTTP.stream()` in `HTTP.js:353-400` uses `fetch()` + `ReadableStream` to parse SSE. It dispatches based on `event:` line: chunk -> `onChunk`, done -> `onDone`, error -> `onError`.

**Data format**: Parsed JSON from `data:` lines. No validation.

**Coupling**: Moderate. HTTP.stream() is a generic SSE parser — it doesn't know about TX envelopes. The callback contract (onChunk/onDone/onError) is simple.

**Stability**: Stable. The `_done` guard (`e5ffa90`) was the only significant fix.

### Boundary 6: Frontend HTTP.stream() -> NetworkAdapter.js send()

**What crosses it**: When `meta.stream` is true in the TX, `NetworkAdapter.js:150-166` calls `HTTP.stream()` with a reconstructed URL. The `httpCallback` is used for both `onChunk` and `onDone`.

**Data format**: The httpCallback wraps the response in a reply TX structure with swapped source/target, then dispatches through `matrix.dispatch()`.

**Coupling**: Tight. The URL construction (`${target}/${name.toLowerCase()}`) is convention-dependent. The callback reuse for both chunk and done means the frontend Matrix sees all events through the same path.

**Stability**: Moderate. There's a commented-out `onStreamData` block at line 153-164 suggesting this was redesigned and the old approach abandoned.

### Boundary 7: Matrix Dispatch -> NTTStream UPPERCASE Handlers

**What crosses it**: TX events arrive at the component via its `STREAM()` handler (bound dynamically in `callMethod()`). STREAM() dispatches to `TEXT()`, `TOOL_CALL()`, `DONE()`, etc. based on `data.name`.

**Data format**: Typed event dispatch. The `data.name` field maps to an UPPERCASE method. The `data.data` field contains the event-specific payload.

**Coupling**: Moderate. The dispatch is convention-based (data.name -> method name). Adding a new event type just requires adding a new UPPERCASE method — no framework changes needed.

**Stability**: Stable. The UPPERCASE convention matches the backend Actor handler pattern.

### Boundary 8: WebSocket Stream Bridge

**What crosses it**: `_stream_to_ws()` in `network_ws.py:207-230` iterates `NetworkAdapter.stream()` and sends each chunk as a JSON message over the WebSocket connection.

**Data format**: TX translated to frontend format via `_translate_outgoing()`, with `meta.stream` and `meta.stream_end` added.

**Coupling**: Moderate. Uses the same adapter.stream() as SSE, just a different transport target.

**Stability**: Stable but undertested. No dedicated WS streaming tests exist.

---

## Extension Points

### EP1: New Stream Event Types (Easy)

**Mechanism**: Convention (UPPERCASE method name).

**How to add**:
1. Backend `run_stream()`: yield `{'name': 'progress', 'data': {'percent': 50}, 'meta': {...}}`
2. Frontend component: add `PROGRESS(data, meta) { ... }` method
3. Schema (optional): add `events={'progress': ProgressEvent}` to `@expose_route`

**Difficulty**: Easy. No framework changes required. The dispatch in `NTTStream.STREAM()` at `ntx-stream.js:29` does `this[name](data.data, data.meta)` — any new event name just needs a matching method.

**Example**: Adding a `CITATION` event for agent responses with source references.

### EP2: Custom Stream Consumer Components (Easy)

**Mechanism**: Subclassing `NTTStream` or `NTTStreamAgent`.

**How to add**:
1. Create a new class extending `NTTStream`
2. Override UPPERCASE handlers for custom rendering
3. Register as custom element

**Difficulty**: Easy. The component hierarchy is designed for this:
```
Component -> NTTMethod -> NTTStream -> NTTStreamAgent -> (your component)
```

**Example**: `ntx-agent-live.js` and `ntx-chat.js` both do exactly this.

**Caveat**: The handler logic for THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE is duplicated across `NTTStreamAgent`, `NTTAgentLive`, and `NTTChat`. This is a DRY violation that makes adding new shared event types require changes in 3 places.

### EP3: New Transport Adapters (Moderate)

**Mechanism**: Subclassing `NetworkAdapter`.

**How to add**:
1. Extend `NetworkAdapter` (which provides `stream()` via Queue correlation)
2. Translate protocol-specific messages to/from TX
3. Register with Matrix

**Difficulty**: Moderate. The `stream()` method at `network_adapter.py:118-163` is transport-agnostic — it yields TX chunks from a Queue. Any adapter inheriting from `NetworkAdapter` gets streaming for free. But the SSE serialization in `_sse_from_stream()` is specific to HTTP — other transports need their own serialization.

**Existing adapters**: NetworkAPI (HTTP/SSE), NetworkWebSocket (WS), NetworkMCP, NetworkAP.

### EP4: Custom Stream Event ProtoModels (Easy)

**Mechanism**: `@expose_route(events={name: ProtoModel})`.

**How to add**:
1. Define non-storable `ProtoModel` subclasses for each event type
2. Pass as `events=` dict to `@expose_route`
3. Event schemas appear in `methods[m].events` in the JSON Schema

**Difficulty**: Easy. The pattern is demonstrated by `AgentActor.agentic_stream()` at `actor.py:170-175` with `TextChunk`, `ToolCallEvent`, etc.

**Impact**: Frontend can read `schema.methods[m].events` to auto-discover event types and their structures. Currently no frontend code actually uses this — it's forward-looking infrastructure.

### EP5: Backend Interceptors on Streams (Moderate)

**Mechanism**: `Actor.use()` interceptor API.

**How to add**: Interceptors already run on stream requests. At `network_adapter.py:131-137`, `stream()` runs 'request' interceptors before sending. To add per-chunk interceptors, you would need to modify the `stream()` method's yield loop.

**Difficulty**: Moderate for pre-stream interceptors (already supported). Hard for per-chunk interceptors (would require changes to `stream()` internals).

**Example**: Rate limiting, audit logging, content filtering on stream requests.

### EP6: Stream Cancellation (Moderate — Partial)

**Mechanism**: Client-side `cancel()` method on `NTTStream`.

**Current state**: `NTTStream.cancel()` at `ntx-stream.js:138-154` sets a client-side ignore flag and sends a `STREAM_CANCEL` TX. But there is **no backend handler for STREAM_CANCEL** — the comment at line 148 says "for future backend support". The async generator on the backend continues to run even after cancellation.

**To complete**:
1. Backend: track active stream tasks by correlation ID
2. On receiving STREAM_CANCEL, cancel the asyncio.Task running the generator
3. Properly clean up Queue entries in NetworkAdapter._pending

**Difficulty**: Moderate. The frontend half exists. The backend half requires task tracking infrastructure.

### EP7: Level 1/2 SSE Format Alignment (Moderate)

**Mechanism**: Modify `routes_fastapi.py` SSE generator.

**Current issue**: Level 1/2 SSE at `routes_fastapi.py:341-345` sends `event: chunk\ndata: {chunk_data}\n\n`. Level 3 SSE at `network_api.py:485` sends `event: chunk\ndata: {full TX envelope}\n\n`. The frontend `NetworkAdapter.js:150-166` uses `httpCallback` which handles the Level 1/2 format. If the app switches from Level 1/2 to Level 3, the frontend stream data format changes.

**To fix**: Either wrap Level 1/2 chunks in a TX-like envelope, or unwrap Level 3 chunks to match Level 1/2. This is a breaking change either way.

**Difficulty**: Moderate. Requires coordinating backend and frontend format changes.

### EP8: Custom Rendering Pipeline (Easy)

**Mechanism**: Override `#renderOutput()` or `#renderMd()` in stream components.

**How to add**: Subclass `NTTStreamAgent` and override the rendering methods. The `#scheduleRender()` / `#renderMd()` pipeline at `ntx-stream-agent.js:189-221` controls how text/thinking content is rendered with optional markdown.

**Difficulty**: Easy — pure CSS/DOM override. No protocol changes needed.

---

## Data Contracts at Boundaries

### Explicit Contracts (Typed/Documented)

| Contract | Format | Location | Enforced? |
|---|---|---|---|
| `@expose_route(stream=True)` | Decorator metadata | `decorators.py:77-83` | Yes — framework reads `__endpoint__['stream']` |
| `TX.chunk()` / `TX.end()` | TX dataclass fields | `tx.py:47-63` | Yes — typed dataclass |
| Stream event schemas | `events=` dict of ProtoModels | `actor.py:170-175` | Partial — schema published, not enforced at runtime |
| `schema.methods[m].stream` | Boolean flag in JSON Schema | `proto_model.py:202-203` | Yes — schema pipeline always adds this |
| `schema.methods[m].events` | Dict of event JSON Schemas | `proto_model.py:204-208` | Yes — serialized via `model_json_schema()` |

### Implicit Contracts (Convention-Based)

| Contract | Convention | Risk |
|---|---|---|
| SSE event names | `chunk`, `done`, `error` strings | Medium — no enum, just string matching |
| Chunk data shape | `{'name': str, 'data': dict, 'meta': dict}` for typed events | Medium — run_stream() hardcodes these shapes |
| `data.name` -> UPPERCASE handler | `data.name.toUpperCase()` maps to `this[NAME]()` | Low — well-established convention |
| `meta.stream_end` terminates | Queue cleanup checks this flag | Low — used consistently everywhere |
| `meta.req` correlates | All stream chunks reference original TX UUID | Low — TX methods enforce this |
| `meta.stream: true` in TX | Frontend uses this to route to HTTP.stream() | Medium — frontend and backend must agree |
| Frontend URL construction | `${target}/${name.toLowerCase()}` for stream POST | High — hardcoded in NetworkAdapter.js:166 |

---

## What's Easy to Change (< 1 hour)

1. **Add a new event type to an agent stream** — yield a new dict shape from `run_stream()`, add UPPERCASE handler to frontend component. No framework changes.

2. **Change stream rendering** — override CSS or DOM construction in any NTTStream subclass. All styling is in static properties.

3. **Add stream event schemas** — define a ProtoModel, add to `events={}` dict on `@expose_route`. Schema pipeline handles serialization automatically.

4. **Change stream timeout** — `NetworkAdapter.stream()` takes `timeout` param (default 120s). `NetworkAdapter.request()` has 30s default. Both are per-call configurable.

5. **Add markdown rendering** — NTTStreamAgent already checks `typeof marked !== 'undefined'`. Include the `marked` library and markdown renders automatically.

6. **Add a new transport adapter with streaming** — extend `NetworkAdapter`, get `stream()` for free. Only need to implement protocol-specific serialization.

7. **Change SSE headers** — modify `_add_streaming_handler()` in `network_api.py:517-518`. Headers are explicit: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

---

## What's Hard to Change (Significant Restructuring)

### H1: Level 1/2 vs Level 3 SSE Format Unification

Level 1/2 sends bare chunk data. Level 3 sends full TX envelopes. Unifying requires either:
- Wrapping Level 1/2 in TX envelopes (breaking change for apps at Level 1/2)
- Unwrapping Level 3 to bare data (loses routing metadata)
- Frontend detecting which format and adapting (complexity in NetworkAdapter.js)

**Files affected**: `routes_fastapi.py`, `network_api.py`, `NetworkAdapter.js`, all streaming tests.

### H2: Backend Stream Cancellation

Frontend sends `STREAM_CANCEL` TX but nobody handles it. Implementing requires:
- Task registry keyed by correlation ID
- Cancellation propagation to the async generator
- Cleanup of Queue entries in NetworkAdapter._pending
- Handling CancelledError in the generator chain

**Files affected**: `network_adapter.py`, `actor_model.py`, `network_api.py`, `network_ws.py`.

### H3: Bidirectional Streaming

Current design is unidirectional: client sends request, server streams responses. Adding client-to-server streaming (e.g., progressive file upload) would require:
- New TX meta convention for upstream chunks
- Client-side chunk sending API
- Backend consumer that reads from an upstream Queue
- Bidirectional correlation in NetworkAdapter

**No files currently support this pattern.**

### H4: Multi-Consumer Stream Fanout

Currently each stream has one consumer (the requesting adapter). Adding fanout (multiple consumers for the same stream, e.g., broadcasting an agent's output to multiple clients) would require:
- Pub/sub on stream correlation IDs
- Multiple Queue entries per stream
- Consumer lifecycle management

**Files affected**: `network_adapter.py`, `network_ws.py`.

### H5: Extracting Shared Agent Event Rendering

The THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE handler logic is duplicated across three components:
- `NTTStreamAgent` (`ntx-stream-agent.js`)
- `NTTAgentLive` (`ntx-agent-live.js`)
- `NTTChat` (`ntx-chat.js`)

Refactoring into a shared mixin/base requires reconciling different DOM structures (NTTStreamAgent uses `.agent-output`, NTTAgentLive uses `.live-log`, NTTChat uses `.chat-messages`). The rendering is deeply coupled to each component's DOM layout.

**Files affected**: All three frontend agent components.

---

## Constraints & Limitations

### C1: Single-Request SSE Only

SSE requires an HTTP response body. The current design creates a new `fetch()` request for each stream. There is no persistent SSE connection — each stream is a separate HTTP POST. This means:
- No server-initiated streams (server can't push unsolicited streams)
- Each stream has its own TCP connection (no multiplexing)
- WebSocket transport exists but is a separate code path with different serialization

### C2: No Backpressure

The async generator on the backend yields chunks as fast as it can. There is no mechanism for the client to signal "slow down". If the client is slow to consume (e.g., rendering heavy markdown), chunks pile up in the SSE buffer. At the actor level, `asyncio.Queue` has no size limit in `NetworkAdapter.stream()`.

### C3: No Chunk Acknowledgment

The frontend never acknowledges receipt of individual chunks. The backend fires and forgets. If chunks are lost (network issue), there is no retry mechanism. The `meta.seq` field enables detection of gaps, but no code currently uses it for this purpose.

### C4: Async Generator Lifetime

The async generator in `ActorModel.handler()` runs to completion (or error). There is no timeout on individual chunk production. If the generator blocks indefinitely on one yield, the stream hangs. The timeout in `NetworkAdapter.stream()` applies to the consumer side (waiting for chunks in the Queue), but the producer side (the generator itself) has no timeout.

### C5: No Stream Resumption

If a stream is interrupted (network drop, page navigation), there is no mechanism to resume from where it left off. The `meta.seq` numbers could enable this, but no resume API exists. The client would need to re-invoke the method and start a new stream.

### C6: In-Memory Only Correlation

Stream correlation (Queue in `NetworkAdapter._pending`) is entirely in-memory. If the server process restarts during a stream, all pending correlations are lost. There is no persistence of stream state.

---

## Feature Integration Guide: Adding a New Streaming Feature

### Scenario: Add a "progress" event type to a model's streaming method

**Step 1: Define the event schema (optional but recommended)**

```python
# In your model file or a shared events module
class ProgressEvent(ProtoModel):
    percent: int = Field(default=0, ge=0, le=100)
    stage: str = Field(default='')
```

**Step 2: Update the @expose_route decorator**

```python
@expose_route('/process', methods=['POST'], stream=True,
              events={'progress': ProgressEvent, 'text': TextChunk, 'done': DoneChunk})
async def process(self, task: str):
    for i in range(10):
        yield {'name': 'progress', 'data': {'percent': i * 10, 'stage': f'Step {i}'}, 'meta': {'stream': True, 'seq': i}}
    yield {'name': 'text', 'data': {'text': 'Result here'}, 'meta': {'stream': True, 'seq': 10}}
```

**Step 3: Frontend handler (if using NTTStream subclass)**

```javascript
class MyStreamComponent extends NTTStream {
    PROGRESS(data, meta) {
        // data = {percent: 50, stage: 'Step 5'}
        this.updateProgressBar(data.percent, data.stage);
    }

    TEXT(data, meta) {
        this.appendText(data.text);
    }
}
```

**Step 4: Tests**

- Unit test: Verify the async generator yields correct chunk shapes (mirror `test_streaming.py` TestActorModelStreamHandler)
- Integration test: HTTP client verifies SSE events arrive in order (mirror `examples/core/tests/test_streaming.py`)
- E2E test (optional): Playwright verifies progressive delivery timing (mirror `examples/core/tests/e2e/test_streaming.py`)

**Files to modify**:
- Model file: add `@expose_route(stream=True, events={...})` method
- Frontend component: add UPPERCASE handler (or use `ntx-stream` tag if plain text suffices)
- Test file: add streaming test case

**Files NOT to modify** (the framework handles these automatically):
- `routes_fastapi.py` / `network_api.py` — auto-detect async generators
- `proto_model.py` — schema pipeline auto-serializes `events` dict
- `actor_model.py` — handler auto-iterates async generators
- `network_adapter.py` — stream() auto-correlates chunks

**Watch out for**:
- Level 1/2 vs Level 3 SSE format difference (see Boundary 4 above)
- If using Level 3, chunk data is nested inside TX envelope: `e.data.data.percent`
- If using Level 1/2, chunk data is flat: `e.data.percent`

---

## Comparison with Alternatives

### vs. Standard SSE (EventSource API)

The browser's `EventSource` API only supports GET requests with no body. N3TX uses `fetch()` + `ReadableStream` (`HTTP.stream()` at `HTTP.js:353-400`) which supports POST with JSON body. This is the right choice for streaming methods that need parameters.

**Tradeoff**: No built-in reconnect (EventSource auto-reconnects). N3TX streams are ephemeral — no resume capability.

### vs. WebSocket-Only Streaming

N3TX supports both SSE and WebSocket streaming. SSE is the default (simpler, works through proxies). WebSocket (`_stream_to_ws()`) is available when the WS adapter is registered.

**Tradeoff**: SSE is unidirectional and requires a new connection per stream. WebSocket multiplexes on a single connection but adds complexity (heartbeats, reconnection, protocol translation).

### vs. gRPC Server Streaming

gRPC provides typed streaming with Protocol Buffers, backpressure, and cancellation built-in. N3TX's approach is simpler (JSON over SSE) but lacks:
- Schema enforcement per chunk (N3TX's `events=` is schema-only, not runtime validated)
- Backpressure
- Native cancellation
- Binary efficiency

**Migration cost**: Very high. Would require a protocol change at every layer.

### vs. Async Iterators with Response Streaming (ASGI)

N3TX already uses ASGI (via FastAPI/Uvicorn). The current approach wraps async generators in `StreamingResponse`, which is idiomatic FastAPI. The alternative would be raw ASGI with `send()` calls, but this would lose FastAPI's route infrastructure.

**Assessment**: Current approach is appropriate for the framework's design philosophy.

### vs. RxJS / Observable Pattern (Frontend)

The frontend could use RxJS Observables instead of direct DOM manipulation. This would provide operators for debouncing, mapping, error handling, and composition. Currently, the `#scheduleRender()` / `#renderMd()` pipeline in `NTTStreamAgent` is a manual implementation of debounce + batch rendering.

**Tradeoff**: Adding RxJS would add a dependency. The current approach works and is dependency-free. The manual debounce at `ntx-stream-agent.js:189-205` is adequate for current needs.

---

## Evolution Trajectory

### Phase 1: Foundation (v0.9 — 6 commits)

```
4bc8663 feat(actors): Add streaming support and rename TX meta
45bc1a2 feat(frontend): Add SSE and WS streaming transport
5c06d3d feat(utils): Add debug envelope and stream flag to expose_route
ee70355 fix(api): Convert middleware to pure ASGI to prevent SSE buffering
cb8c14f feat(example): Add countdown streaming demo with tests
6c5c6eb test(example): Add e2e progressive streaming verification
```

Built the infrastructure: TX.chunk()/end(), NetworkAdapter.stream(), HTTP.stream(), SSE wire format, @expose_route(stream=True). The SSE buffering fix (`ee70355`) shows the middleware was initially preventing progressive delivery — a common gotcha with ASGI.

### Phase 2: Agent Streaming (v0.10 — 15+ commits)

```
b9a7181 feat(agents): Add self-aware model API — ctx, tools, run, streaming
1a13a99 feat(agents): Rich streaming with tool/thinking events via agent.iter()
75b22f4 feat(frontend): Add StreamActor mixin for TX-aware stream dispatch
2b23a05 refactor(frontend): Rewrite ntx-method and ntx-stream for actor-routed streaming
55cd002 feat(agents): Add event ProtoModels and events= on agentic_stream
332bd96 fix(agents): Handle TextPart in PartStartEvent for first-token bug
13bc99b refactor(example): Update tests and imports for StreamActor removal
```

Layered agent-specific streaming: run_stream() with pydantic-ai iter() API, typed events (text, tool_call, tool_result, thinking, done), NTTStreamAgent, NTTAgentLive, NTTChat. The first-token bug fix (`332bd96`) shows real-world model differences (OpenAI vs TestModel) required handling PartStartEvent in addition to PartDeltaEvent.

### Phase 3: Application (veille app — ongoing)

```
7c649df feat(02-01): Create Run model with streaming agentic execute() method
05d6296 feat(02-02): Create ntx-run-panel.js StreamActor-based streaming component
f22b6bf feat(03-01): Add __agent__ and analyze() streaming endpoint to Grant model
1406f37 feat(veille): Frontend rewrite with NTTStreamAgent components
```

Application-level usage proving the subsystem works end-to-end for real agent workflows.

### Trajectory Assessment

The trajectory is **healthy but accumulating duplication**:

1. **Infrastructure is stable** — TX, NetworkAdapter, HTTP.stream() haven't needed changes since v0.9
2. **Agent layer is active** — new event types, bug fixes, component variants
3. **Duplication is growing** — three frontend components (NTTStreamAgent, NTTAgentLive, NTTChat) duplicate ~80% of the same handler logic
4. **Level 1/2 vs 3 divergence persists** — no effort to unify SSE formats
5. **Cancellation remains incomplete** — frontend `cancel()` exists since v0.10 but backend support is absent

**Sustainable?** Yes, for the near term. The foundation is solid and the extension points work. But the frontend duplication will become a maintenance burden as more event types are added. The recommended consolidation is extracting shared handler logic into a mixin or shared base, similar to how the backend uses `AgentMixin`.

---

## Cross-Cutting Concerns

### Logging

**Backend**: `logger.error()` calls in `actor_model.py:90,144,161`, `network_api.py:477`, `network_ws.py:222`. Stream errors are logged at ERROR level. Normal stream activity is not logged (no DEBUG-level chunk logging).

**Gap**: No structured logging of stream lifecycle (start, chunk count, duration, end reason). Adding stream telemetry would require instrumenting `NetworkAdapter.stream()` and `ActorModel.handler()`.

### Error Handling

**Backend chain**:
1. Generator `raise` -> caught in `actor_model.py:161-163` -> `tx.exception(e)` -> error TX to consumer
2. `NetworkAdapter.stream()` timeout -> synthetic error TX with code 504 (`network_adapter.py:153-155`)
3. `_sse_from_stream()` serializes error TX as `event: error` SSE frame

**Frontend chain**:
1. `HTTP.stream()` calls `onError` for HTTP errors or `event: error` frames
2. `NTTStream.STREAM_ERROR()` shows toast and updates UI
3. `NTTStreamAgent.STREAM_ERROR()` adds an error entry to the log

**Gap**: Level 1/2 SSE has no error event — if the generator raises after yielding chunks, the SSE stream just ends abruptly. There is no `event: error` frame in `routes_fastapi.py:341-345`. The generator's exception is swallowed and only the `event: done` frame is sent. This is a **bug** at `routes_fastapi.py:344`: the `sse()` inner function has no try/except around the `async for chunk in _gen` loop.

### Configuration

**Timeouts**: Hardcoded defaults scattered across files:
- `NetworkAdapter.request()`: 30s (`network_adapter.py:79`)
- `NetworkAdapter.stream()`: 120s (`network_adapter.py:118`)
- `_sse_from_stream()`: 120s (`network_api.py:477`)
- `_stream_to_ws()`: 120s (`network_ws.py:214`)
- `HTTP.stream()`: no timeout (browser manages)

These are not configurable via `config.py`. To make them configurable, add `STREAM_TIMEOUT` to `n3tx_core/config.py` and reference it from each location.

### Authentication

**Stream requests follow the same auth path as regular requests**:
- Level 1/2: JWTAuthMiddleware sets `request.state.user` before the route handler
- Level 3: `auth_interceptor` runs on `adapter.request()` / `adapter.stream()` before the TX enters the actor system (`network_adapter.py:131-137`)
- WebSocket: JWT validated at connection time (`network_ws.py:287-289`), stored per-connection

**Gap**: Auth is checked once at stream initiation. If a JWT expires during a long-running stream, the stream continues with the original auth context. There is no periodic re-validation.

### Serialization

**Backend TX serialization**: `dataclasses.asdict(chunk)` in `_sse_from_stream()` at `network_api.py:478`. Uses `default=str` for non-serializable types in `json.dumps()`.

**Frontend TX deserialization**: `JSON.parse(line.slice(6))` in `HTTP.stream()` at `HTTP.js:382`. No validation.

**Agent chunk serialization**: `run_stream()` yields plain dicts (not TX objects). These are converted to TX by `actor_model.py:157-158` via `tx.chunk()`.

**Gap**: No runtime validation of chunk data shapes against declared `events` schemas. The `events=` dict on `@expose_route` is documentation-only — the backend does not validate that yielded chunks match the declared event models.

---

## Summary of Key Findings

| Finding | Type | Impact | Location |
|---|---|---|---|
| Level 1/2 vs Level 3 SSE format divergence | Design inconsistency | Medium | `routes_fastapi.py:341` vs `network_api.py:485` |
| Level 1/2 SSE has no error event frame | Bug | Medium | `routes_fastapi.py:341-345` — no try/except |
| Frontend agent handler duplication (3 components) | DRY violation | Low now, growing | `ntx-stream-agent.js`, `ntx-agent-live.js`, `ntx-chat.js` |
| Backend stream cancellation not implemented | Missing feature | Medium | `ntx-stream.js:148` sends TX, no backend handler |
| No backpressure on stream chunks | Limitation | Low | `NetworkAdapter.stream()` Queue unbounded |
| No runtime validation of event schemas | Gap | Low | `events=` is schema-only |
| Stream timeouts not configurable | Configuration gap | Low | Hardcoded in 4 locations |
| WebSocket streaming lacks dedicated tests | Test gap | Medium | `_stream_to_ws()` untested |
| JWT not re-validated during long streams | Auth gap | Low | Auth checked once at initiation |
| `events=` schema not consumed by frontend | Unused infrastructure | Low | Published in schema but no frontend reader |
