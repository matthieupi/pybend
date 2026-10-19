# Streaming Subsystem: Architecture & Design Patterns Audit

**Audit date:** 2026-03-26
**Scope:** Every component, pattern, data flow, and coupling relationship in the N3TX streaming subsystem.
**Method:** Full source read of all 22 core files listed in the audit brief.

---

## 1. Component Inventory

### 1.1 Backend Components

| Component | Location | Role |
|-----------|----------|------|
| `TX.chunk()` | `n3tx-actors/tx.py:47-54` | Creates a STREAM chunk reply TX with `meta.stream=True`, `meta.seq=N`, `meta.req=original_uuid` |
| `TX.end()` | `n3tx-actors/tx.py:56-63` | Creates a STREAM end reply TX with `meta.stream_end=True` |
| `TX.stream_chunk` / `TX.stream_end` | `n3tx-actors/tx.py:65-67` | Deprecated aliases for `chunk()` / `end()` |
| `TX.exception()` | `n3tx-actors/tx.py:69-71` | Maps exceptions to error TX (used by stream error paths) |
| `NetworkAdapter` | `n3tx-actors/api/network_adapter.py:36` | Base protocol bridge actor; provides `request()` (Future) and `stream()` (Queue) correlation |
| `NetworkAdapter.inbox()` | `n3tx-actors/api/network_adapter.py:57-77` | Dispatches correlated replies to Future (request) or Queue (stream) |
| `NetworkAdapter.stream()` | `n3tx-actors/api/network_adapter.py:118-163` | Async generator; creates Queue, launches send as task, yields chunks until `stream_end`/error/timeout |
| `NetworkAPI` | `n3tx-actors/api/network_api.py:35-40` | HTTP API adapter for Level 3; subclass of NetworkAdapter |
| `_sse_from_stream()` | `n3tx-actors/api/network_api.py:469-485` | Converts `NetworkAdapter.stream()` chunks to SSE text frames (event: chunk/done/error) |
| `_add_streaming_handler()` | `n3tx-actors/api/network_api.py:488-540` | Creates FastAPI route for streaming `@expose_route` methods; returns `StreamingResponse` |
| `NetworkWebSocket` | `n3tx-actors/api/network_ws.py:52-270` | WebSocket adapter; bridges WS connections to Matrix |
| `NetworkWebSocket._stream_to_ws()` | `n3tx-actors/api/network_ws.py:207-230` | Streams chunks from `adapter.stream()` directly to a WS client as JSON |
| `routes_fastapi.make_custom_post()` | `n3tx-core/api/routes_fastapi.py:283-402` | Level 1/2 custom method handler; detects `isasyncgen` and returns SSE `StreamingResponse` |
| `@expose_route` | `n3tx-core/utils/decorators.py:13-88` | Decorator marking methods as endpoints; `stream=True` and `events={}` params control streaming |
| `ProtoModel.__n3tx_methods_json_signature__()` | `n3tx-core/models/proto_model.py:154-213` | Builds method schema entries; emits `stream: true` and `events: {...}` when present |
| `ActorModel.handler()` | `n3tx-actors/models/actor_model.py:70-195` | Generic message handler; detects async generators (line 153) and dispatches `tx.chunk()`/`tx.end()` |
| `AgentMixin.run_stream()` | `n3tx-agents/mixin.py:461-691` | Streaming LLM engine; iterates pydantic-ai graph nodes, yields TX-aligned chunk dicts |
| `AgentMixin.agentic_stream()` | `n3tx-agents/mixin.py:423-459` | Streaming policy layer; resolves config, delegates to `run_stream()` |
| `AgentActor.agentic_stream()` | `n3tx-agents/actor.py:170-204` | Override for DB-configured agents; calls `AgentMixin.run_stream()` directly |
| `TextChunk`, `ToolCallEvent`, `ToolResultEvent`, `ThinkingChunk`, `DoneChunk` | `n3tx-agents/actor.py:41-65` | Non-storable ProtoModel subclasses defining stream event schemas |

### 1.2 Frontend Components

| Component | Location | Role |
|-----------|----------|------|
| `NTTMethod` | `n3tx-ui/static/components/ntx-method.js:14` | Base custom method component; renders form, handles `callMethod()` via entity `.call()` |
| `NTTStream` | `n3tx-ui/static/components/ntx-stream.js:5` | Streaming method base; extends NTTMethod with STREAM inbox handler, UPPERCASE dispatch, cancel support |
| `NTTStreamAgent` | `n3tx-agents/static/components/ntx-stream-agent.js:4` | Rich agent output; extends NTTStream with typed entries, markdown, tool cards, thinking animation |
| `NTTAgentLive` | `n3tx-agents/static/components/ntx-agent-live.js:21` | Standalone agent activity view; extends NTTStream with full panel UI (input, log, footer) |
| `NTTChat` | `n3tx-agents/static/components/ntx-chat.js:25` | Collapsible chat panel; extends NTTStream with instance selector, message history, floating tab |
| `HTTP.stream()` | `n3tx-core/static/core/transport/HTTP.js:353-400` | Fetch-based SSE client; POST + ReadableStream pump with abort controller |
| `NetworkAdapter.send()` | `n3tx-core/static/core/transport/NetworkAdapter.js:119-171` | Frontend transport dispatcher; `meta.stream` branch calls `HTTP.stream()` |
| `Socket` | `n3tx-core/static/core/transport/Socket.js:21` | WebSocket transport; sends TX as JSON, dispatches incoming messages to Matrix |

---

## 2. Responsibility Map

### 2.1 What Each Component Does and Why It Exists

**TX.chunk() / TX.end()** -- The stream protocol primitives. They encode streaming semantics directly in the TX envelope via `meta.stream`, `meta.seq`, `meta.stream_end`, and `meta.req`. Without them, the actor system has no way to distinguish stream fragments from regular replies, and no way to correlate them back to the originating request.

**NetworkAdapter.stream()** -- The bridge between fire-and-forget actor messaging and streaming protocols (SSE, WS). The actor system is inherently asynchronous -- `send()` returns immediately. `stream()` creates an `asyncio.Queue` as a rendezvous point, launches `send()` as a background task, and yields from the queue. Without this, there is no way to consume progressive actor output through a synchronous protocol. If removed: Level 3 SSE and WS streaming would be impossible.

**NetworkAdapter.inbox()** -- The correlation dispatcher. It examines `meta.req` on incoming TXs and routes them to either a Future (single-response `request()`) or a Queue (multi-response `stream()`). This is the single-point implementation of request/response semantics over fire-and-forget messaging. If removed: no request/response or streaming correlation.

**_sse_from_stream()** -- The SSE wire format serializer for Level 3. It iterates `NetworkAdapter.stream()`, serializing each TX chunk to `event: chunk/done/error\ndata: {json}\n\n`. It serializes the **full TX envelope** (routing, meta, data), not just chunk data. If removed: Level 3 HTTP streaming stops working.

**ActorModel.handler() stream detection** -- Lines 152-164 of `actor_model.py`. When a custom method returns an async generator, the handler iterates it, wrapping each yielded value in `tx.chunk()` and emitting `tx.end()` at completion. This is the actor-side producer. If removed: async generator methods would be treated as non-streaming (the generator object would be sent as a single reply).

**make_custom_post() stream detection** -- Lines 340-349 and 389-398 of `routes_fastapi.py`. Level 1/2 equivalent -- detects `isasyncgen` on the result of calling a custom method and wraps it in SSE `StreamingResponse`. If removed: Level 1/2 streaming stops working.

**@expose_route(stream=True)** -- The declaration mechanism. Marks a method as streaming in the schema and in route registration. The `stream` flag gates whether `_add_streaming_handler()` or `_add_custom_handler()` is used in Level 3 (line 398-408 of `network_api.py`). The `events={}` param embeds event schemas in the method signature. If removed: routes wouldn't know to use SSE.

**NTTStream** -- The frontend streaming base. Overrides `callMethod()` to send TX with `meta.stream=true`, binds a dynamic alias so reply TXs route to `STREAM()`, dispatches to UPPERCASE handlers. Provides cancel(), disconnectedCallback cleanup, and plain-text accumulation. If removed: all frontend streaming components lose their foundation.

**NTTStreamAgent** -- The rich rendering layer. Replaces NTTStream's simple text buffer with typed entries (thinking, tool calls, tool results, text output), markdown rendering via `marked`, tool call correlation via `#toolCards` Map, and debounced rendering. If removed: agent output degrades to plain text.

**HTTP.stream()** -- The browser-side SSE transport. Issues a POST with `fetch()`, reads the response body as a ReadableStream, parses SSE frames, and dispatches to onChunk/onDone/onError callbacks. Returns a cancel handle. If removed: SSE streaming in the browser stops working.

### 2.2 Component Dependency Summary

```
         Who breaks if removed?
TX.chunk/end     → ActorModel.handler, NetworkAdapter.stream, _sse_from_stream, all tests
NetworkAdapter   → NetworkAPI, NetworkWebSocket, all Level 3 streaming
_sse_from_stream → Level 3 HTTP SSE endpoints
make_custom_post → Level 1/2 SSE endpoints
NTTStream        → NTTStreamAgent, NTTAgentLive, NTTChat
HTTP.stream      → Frontend SSE (HTTP mode)
Socket           → Frontend WS streaming
```

---

## 3. Design Patterns

### 3.1 Pattern Catalog

| Pattern | Where Applied | Why Chosen | Assessment |
|---------|--------------|------------|------------|
| **Envelope / Message** | `TX` dataclass | Uniform message format across entire system. Stream chunks, errors, replies all use the same shape. | Correct choice. Eliminates special-casing across protocol boundaries. |
| **Adapter** | `NetworkAdapter`, `NetworkAPI`, `NetworkWebSocket` | Translates external protocols (HTTP, WS, MCP) to internal TX messaging. | Textbook adapter pattern. Well-applied -- each adapter is an Actor, receiving replies through normal routing. |
| **Async Queue as Rendezvous** | `NetworkAdapter.stream()` | Bridges fire-and-forget actor messaging with streaming consumer protocols. The Queue acts as a synchronization point between concurrent producer (actor handler) and consumer (SSE serializer). | Excellent choice for this problem. Alternative (callback registration) would be more complex. |
| **Correlation ID** | `meta.req` in TX, `_pending` dict in NetworkAdapter | Maps async replies back to their originating request. Used by both `request()` (Future) and `stream()` (Queue). | Standard pattern for request/response over message-passing. Correctly applied. |
| **Template Method** | `NTTStream.STREAM()` dispatching to `TEXT()`, `STREAM_END()`, etc. | Base class defines the dispatch skeleton; subclasses override UPPERCASE handlers. | Good fit. Allows NTTStreamAgent to override rendering without changing dispatch logic. |
| **Dynamic Method Alias** | `NTTStream.callMethod()` binding `this[name] = (data, tx) => this.STREAM(data, tx)` | Reply TXs arrive with the method name (e.g., `agentic_stream`), but all stream chunks need to route to `STREAM()`. Dynamic alias bridges the naming gap. | Clever but fragile. See coupling analysis. |
| **Mixin Injection** | `AgentMixin` injected via `__agent__ = True` | Adds `run_stream()` and `agentic_stream()` to any model without multiple inheritance boilerplate. Same pattern as `StorableMixin`. | Consistent with framework philosophy. |
| **@fullmethod Descriptor** | `agentic_stream()`, `run_stream()` in AgentMixin | Enables unified class/instance dispatch (`Product.run_stream()` and `product.run_stream()`). | Right choice for the agent layer where both class-level and instance-level invocation are needed. |
| **Strategy** | `@expose_route(stream=True)` controlling route registration path | The `stream` flag selects between `_add_streaming_handler()` and `_add_custom_handler()` in Level 3. | Simple boolean strategy. Appropriate for a two-path choice. |
| **Observer / Pub-Sub** | `ActorModel._publish_lifecycle()` and `NetworkWebSocket.LIFECYCLE()` | Lifecycle events (create/update/delete) are broadcast to subscribers. WS adapter forwards them to connected clients. | Pattern is in place but `_subscribers` is always empty (line 66 of actor_model.py: `_subscribers: ClassVar[list] = []`). WS receives LIFECYCLE events through direct actor routing, not through the subscriber list. |
| **Sentinel / Type Discrimination** | `_NOT_HANDLED` in `actor_model.py:33` | Distinguishes "not a CRUD message" from legitimate `None` returns in `handler_crud()`. | Correct. A return-value sentinel is the right approach when `None` is a valid return. |

### 3.2 Pattern Assessment

The streaming subsystem uses patterns that are well-suited to its constraints. The Async Queue Rendezvous pattern (NetworkAdapter.stream) is particularly well-designed -- it solves the fundamental impedance mismatch between fire-and-forget actors and streaming consumers with minimal complexity.

The Dynamic Method Alias pattern in NTTStream is the most unusual choice. It works but creates an implicit contract: reply TXs MUST arrive with a `name` that matches the method name used in `callMethod()`. This is fragile if the backend ever renames the response event.

---

## 4. Data Flow

### 4.1 Level 1/2 SSE Flow (Direct Routes)

```
Frontend                          FastAPI (routes_fastapi.py)         Model Method
--------                          -------------------------          ------------

HTTP.stream(url, data, ...)       make_custom_post()                @expose_route(stream=True)
  |                                 |                                async def countdown(self, n):
  | POST /products/1/countdown      | attr(instance, **args)            yield {count: 3}
  |------------------------------>  |------------------------------>    yield {count: 2}
  |                                 | isasyncgen(result)? Yes           yield {count: 1}
  |                                 | SSE wrapper:                      yield {count: 0}
  |  event: chunk                   |   async for chunk in gen:
  |  data: {count:3}                |     yield f"event: chunk\n
  |<------  -------  --------  --   |            data: {json}\n\n"
  |  event: chunk                   |
  |  data: {count:2}                |   yield "event: done\n
  |<------  -------  --------  --   |          data: {}\n\n"
  |  event: done                    |
  |  data: {}                       | return StreamingResponse(sse())
  |<------  -------  --------  --   |
```

**Key observation:** Level 1/2 SSE data is **raw chunk data** (the dict yielded by the generator). There is no TX envelope wrapping.

### 4.2 Level 3 SSE Flow (Actor Routing)

```
Frontend              NetworkAPI       Matrix        ActorModel.handler()     Model Method
--------              ----------       ------        --------------------     ------------

HTTP.stream(...)      _add_streaming   adapter       handler() generic        @expose_route(stream=True)
  |                   _handler()       .stream(tx)   dispatch:                async def countdown(self, n):
  | POST              |                |             |                           yield {count: 3}
  |-----------------> | TX(meta:       | Queue        | isasyncgen?               yield {count: 2}
  |                   |  stream:true)  | rendezvous   |   Yes:                    yield {count: 1}
  |                   |--------------->|              |   for chunk in gen:
  |                   |                | send_task    |     tx.chunk(data, seq)
  |                   |                |<-------------|<---  tx sent to Matrix
  |                   |                | queue.put()  |       → adapter.inbox()
  |                   |                |              |       → queue.put(chunk_tx)
  |  event: chunk     | _sse_from_     |              |
  |  data: {full TX}  | stream():     | queue.get()  |   tx.end(seq=N)
  |<--  ------------- | serialize TX  |<-------------|<---  stream_end
  |  event: done      | as SSE        |              |
  |  data: {full TX}  |               |              |
  |<--  ------------- |               |              |
```

**Key observation:** Level 3 SSE data is the **full TX envelope** (`_sse_from_stream` at line 478 does `asdict(chunk)`). This means the frontend receives `{name, source, target, data, meta, timestamp, uuid}` -- not just the inner data. This is a deliberate design choice (documented in the `_sse_from_stream` docstring at line 469-473).

### 4.3 WebSocket Stream Flow

```
Frontend              NetworkWebSocket    Matrix        ActorModel.handler()
--------              ----------------    ------        --------------------

Socket.send(tx)       handle_message()
  | {meta:stream}     |
  |------------------>| _translate_incoming()
  |                   | asyncio.create_task(_stream_to_ws(ws, tx))
  |                   |                    adapter.stream(tx)
  |                   |                    |
  |                   |                    | Queue rendezvous
  |                   |                    |<----------- tx.chunk(...)
  |                   | _translate_outgoing(chunk)
  | {name, source,    | ws.send_json(response)
  |  target, data,    |
  |  meta:{stream:T}} |
  |<------------------|
  |                   |                    |<----------- tx.end(...)
  | {meta:stream_end} | ws.send_json(response)
  |<------------------|
```

**Key observation:** WS streaming runs as a background task (`asyncio.create_task` at line 201) so the WS message loop stays responsive. The `handle_message()` returns `None` for streaming requests (line 202-203), preventing the main loop from sending a duplicate response.

### 4.4 Agent Streaming Flow

```
AgentActor.agentic_stream()    AgentMixin.run_stream()         pydantic-ai
--------------------------     -----------------------         -----------

@expose_route(stream=True)     async for node in agent_run:    LLM API
  |                              |                               |
  | resolve tool addrs           | ModelRequestNode:              |
  | call run_stream_fn()         |   stream(ctx):                |
  |--------------------------->  |     PartStartEvent(TextPart)  |
  |                              |       → yield {name:'text'}  |<--- SSE/WS
  |                              |     PartDeltaEvent(TextDelta) |
  |                              |       → yield {name:'text'}  |<---
  |                              |     PartStartEvent(ToolCall)  |
  |                              |       → yield {name:'tool_call'}
  |                              |                               |
  |                              | CallToolsNode:                |
  |                              |   stream(ctx):                |
  |                              |     FunctionToolResultEvent   |
  |                              |       → yield {name:'tool_result'}
  |                              |                               |
  |                              | End:                          |
  |                              |   yield {name:'done', meta:{stream_end:true}}
  |<--------------------------   |
  |                              |
  | ActorModel.handler()         |
  |   detects isasyncgen         |
  |   wraps in tx.chunk()/end()  |
```

**Key observation:** `run_stream()` yields plain dicts (not TX objects). The `ActorModel.handler()` at lines 152-164 wraps them in `tx.chunk()` / `tx.end()`. This is a clean separation -- the agent layer doesn't need to know about TX envelopes.

### 4.5 Frontend Dispatch Flow

```
HTTP.stream()          NetworkAdapter.send()    NTTStream            NTTStreamAgent
-------------          --------------------     --------             --------------

onChunk(parsed)  --->  httpCallback(event,      callMethod()         callMethod()
                       response)                  |                    |
                         |                        | send(TX{           | super.callMethod()
                         | matrix.dispatch(       |   meta.stream})    |
                         |   {name, source,       |                    |
                         |    target, data})      | this[method] =     |
                         |                        |   (d,t) =>         |
                         |   Component inbox      |     STREAM(d,t)    |
                         |   → this[method]()     |                    |
                         |   → STREAM(data, tx)   |                    |
                         |                        | STREAM():          | STREAM() inherited
                         |                        |   name.toUpper()   |   → TEXT(data.data)
                         |                        |   → this[NAME]()   |   → TOOL_CALL(data.data)
                         |                        |   fallback: TEXT() |   → THINKING(data.data)
                         |                        |                    |   → DONE(data.data)
```

---

## 5. State Management

### 5.1 Backend State

| State | Location | Lifecycle | Mutation |
|-------|----------|-----------|----------|
| `_pending` dict | `NetworkAdapter` (PrivateAttr) | Per-adapter instance | `request()`: add Future by uuid, remove on resolve/timeout. `stream()`: add Queue by uuid, remove on `stream_end`/error/timeout (in `inbox()` or `finally` block). |
| `_connections` dict | `NetworkWebSocket` (PrivateAttr) | Per-adapter instance | Add on WS connect (`create_ws_routes`), remove on disconnect or dead client detection. |
| `seq` counter | `ActorModel.handler()` local | Per-stream invocation | Incremented by 1 for each chunk yielded. Starts at 0. |
| `seq` counter | `AgentMixin.run_stream()` local | Per-stream invocation | Same pattern. |
| `send_task` | `NetworkAdapter.stream()` local | Per-stream invocation | Created via `asyncio.create_task()`, cancelled in `finally` block if not done. |

**Risk: `_pending` leak.** If `inbox()` never receives `stream_end` or error (e.g., the backend crashes mid-stream), the Queue stays in `_pending` until `stream()` times out. The timeout default is 120s for `stream()` -- during that window, the Queue and its accumulated chunks consume memory. The `finally` block in `stream()` (line 160) ensures cleanup eventually happens, but a crashed backend could cause 2-minute memory holds per active stream.

### 5.2 Frontend State

| State | Location | Lifecycle | Mutation |
|-------|----------|-----------|----------|
| `#streaming` | `NTTStream` (private field) | Per-component | Set true in `callMethod()`, false in `STREAM_END`/`STREAM_ERROR`/`cancel()`. |
| `#textBuf` | `NTTStream` (private field) | Per-component | Appended in `TEXT()`, reset in `#reset()`. |
| `#cancelled` | `NTTStream` (private field) | Per-component | Set in `cancel()`, checked in `STREAM()` to ignore late chunks. |
| `#streamReqId` | `NTTStream` (private field) | Per-component | Set in `callMethod()`, used in cancel TX. |
| `#boundHandler` | `NTTStream` (private field) | Per-component | Tracks the current dynamic alias name for cleanup. |
| `#toolCards` Map | `NTTStreamAgent`, `NTTAgentLive`, `NTTChat` | Per-component | Maps `call_id` to DOM element for tool result correlation. Cleared on `callMethod()`. |
| `#textBuf`, `#textRendered`, `#textTimer` | `NTTStreamAgent`, `NTTAgentLive` | Per-component | Buffered text for debounced markdown rendering. |
| `#thinkBuf`, `#thinkRendered`, `#thinkTimer` | `NTTStreamAgent`, `NTTAgentLive` | Per-component | Buffered thinking text for debounced markdown rendering. |
| `_done` flag | `HTTP.stream()` closure | Per-request | Prevents `onDone({})` from firing when the reader ends after a done event was already dispatched. |
| `controller` | `HTTP.stream()` return value | Per-request | AbortController for cancellation. |

---

## 6. Coupling Analysis

### 6.1 Tight Coupling (Concrete References)

| From | To | Nature | Rating |
|------|----|--------|--------|
| `_sse_from_stream()` | `NetworkAdapter.stream()` | Direct call to `adapter.stream(tx)` | **Acceptable** -- same package, same concern |
| `_add_streaming_handler()` | `_sse_from_stream()` | Direct call | **Acceptable** -- helper function in same module |
| `ActorModel.handler()` | `TX.chunk()`, `TX.end()` | Direct call to stream primitives | **Acceptable** -- TX is the universal envelope |
| `NTTStream` | `NTTMethod` | Extends via class hierarchy | **Acceptable** -- designed inheritance |
| `NTTStreamAgent` | `NTTStream` | Extends via class hierarchy | **Acceptable** -- designed inheritance |
| `NTTAgentLive` | `NTTStream` | Extends via class hierarchy | **Acceptable** but duplicates NTTStreamAgent rendering logic (see cohesion) |
| `NTTChat` | `NTTStream` | Extends via class hierarchy | **Acceptable** -- designed inheritance |
| `AgentActor.agentic_stream()` | `AgentMixin.__dict__['run_stream'].fn` | Reaches into descriptor internals | **Problematic** -- bypasses the fullmethod dispatch. If run_stream's descriptor changes, this breaks silently. |
| `NetworkAdapter.send()` (frontend) | `HTTP.stream()` | Direct call when `meta.stream` is true | **Acceptable** -- transport layer coordination |
| `HTTP.stream()` | SSE wire format | Parses `event: ` and `data: ` prefixes | **Wire protocol coupling** -- must match backend SSE format exactly |

### 6.2 Loose Coupling (Protocols, Events, DI)

| From | To | Mechanism | Rating |
|------|----|-----------|--------|
| `@expose_route(stream=True)` | Route registration | `__endpoint__` dict on function | **Good** -- declarative metadata, no import dependency |
| `NTTStream.STREAM()` | Subclass handlers | UPPERCASE name dispatch via `this[name]()` | **Good** -- convention-based, extensible without code changes |
| `ActorModel.handler()` | Stream methods | `inspect.isasyncgen(result)` | **Good** -- duck typing, no marker interface needed |
| `run_stream()` chunk format | `NTTStreamAgent` handlers | `{name, data, meta}` dict shape | **Good** -- simple contract, no shared type dependency |
| `_publish_lifecycle()` | `NetworkWebSocket.LIFECYCLE()` | TX messaging through Matrix | **Good** -- fully decoupled via actor routing |
| Schema `methods[m].events` | Frontend event rendering | JSON Schema per event type | **Good** -- schema as contract |
| `meta.stream`, `meta.stream_end`, `meta.req` | All streaming components | Convention in TX meta dict | **Moderate** -- convention-coupled, not enforced by types |

### 6.3 Coupling Risk Summary

The most concerning coupling is `AgentActor.agentic_stream()` reaching into `AgentMixin.__dict__['run_stream'].fn` (actor.py:192). This bypasses the `@fullmethod` descriptor to avoid MRO collision (AgentActor overrides `agentic_stream` but needs to call the mixin's `run_stream` directly). A safer approach would be to call `AgentMixin.run_stream.__func__` or use `super()` dispatch, but the current approach works as long as the descriptor implementation stays stable.

---

## 7. Cohesion Assessment

### 7.1 Well-Cohesive Modules

**TX (tx.py)** -- Single responsibility: message envelope. Stream methods (`chunk`, `end`) are natural extensions of `reply` and `error`. High cohesion.

**NetworkAdapter (network_adapter.py)** -- Single responsibility: protocol bridging with request/response correlation. `request()`, `stream()`, and `inbox()` are all aspects of the same concern. High cohesion.

**NTTStream (ntx-stream.js)** -- Single responsibility: streaming method UI base. `callMethod()`, `STREAM()`, `cancel()`, `TEXT()`, `STREAM_END()` are all parts of a coherent streaming component. High cohesion.

**HTTP.stream() (HTTP.js:353-400)** -- Well-focused function: SSE transport via fetch. Does one thing well.

### 7.2 Moderate Cohesion

**routes_fastapi.py** -- Mixed: CRUD route generation AND streaming SSE detection AND custom method dispatch. The streaming detection (`isasyncgen` check, `sse()` inner function) is inline within `make_custom_post()` rather than extracted. Lines 340-349 and 389-398 contain duplicated SSE wrapping code for instance vs. class methods. Could extract a shared `_wrap_asyncgen_as_sse()`.

**network_api.py** -- Two concerns: route registration (`create_api_routes`) and SSE serialization (`_sse_from_stream`). These are related but distinct. Acceptable for a single module.

### 7.3 Code Duplication (Cohesion Anti-Pattern)

**NTTStreamAgent vs NTTAgentLive** -- These two components contain near-identical rendering code:

- `THINKING()` handler: ~identical logic (compare `ntx-stream-agent.js:17-27` with `ntx-agent-live.js:100-111`)
- `TOOL_CALL()` handler: ~identical logic (compare `ntx-stream-agent.js:30-46` with `ntx-agent-live.js:113-128`)
- `TOOL_RESULT()` handler: ~identical logic (compare `ntx-stream-agent.js:48-62` with `ntx-agent-live.js:130-142`)
- `TEXT()` handler: ~identical logic
- `#scheduleRender()`, `#renderMd()`, `#flushRender()`, `#scrollToBottom()`, `#esc()`: duplicated private methods
- CSS for entry types: duplicated (`.entry-thinking`, `.entry-tool-call`, etc.)

NTTAgentLive extends NTTStream directly instead of NTTStreamAgent, so it re-implements all the rich rendering. This is the most significant code duplication in the streaming subsystem. NTTAgentLive should extend NTTStreamAgent and only add its own panel UI (`prerender()`, `callMethod()` override, status tracking).

**make_custom_post() SSE wrapper** -- The SSE wrapping code is duplicated between `post_with_id` (lines 340-349) and `post_no_id` (lines 389-398) in `routes_fastapi.py`. Both contain identical inner `sse()` functions.

---

## 8. Boundary Analysis

### 8.1 Public Surface vs Internal Implementation

| Module | Public Surface | Internal | Enforcement |
|--------|---------------|----------|-------------|
| `TX` | `chunk()`, `end()`, `reply()`, `error()`, `exception()`, `is_error` | `from_exception()` | Convention only (no `__all__`, no underscore) |
| `NetworkAdapter` | `request()`, `stream()`, `inbox()` | `_pending` dict | Underscore convention + `PrivateAttr` |
| `NetworkAPI` | `create_api_routes()` | `_sse_from_stream()`, `_add_streaming_handler()`, `_add_custom_handler()`, `_parse_method_args()` | Underscore prefix |
| `NetworkWebSocket` | `create_ws_routes()`, `handle_message()` | `_stream_to_ws()`, `_translate_incoming()`, `_translate_outgoing()`, `_connections` | Underscore prefix + `PrivateAttr` |
| `routes_fastapi` | `register_routes()`, `register_route()`, `router` | `make_custom_post()` and others | `__all__` defined (line 532) but only exports `router`, `register_routes`, `register_route` |
| `@expose_route` | The decorator itself | `__endpoint__` dict on wrapped function | Convention (`__endpoint__` is inspected by route registration) |
| `NTTStream` | `STREAM()`, `TEXT()`, `STREAM_END()`, `STREAM_ERROR()`, `callMethod()`, `cancel()` | `#streaming`, `#textBuf`, `#cancelled`, `#streamReqId`, `#boundHandler`, `#reset()`, `#renderOutput()`, `#esc()` | JS private fields (`#`) -- truly private |
| `NTTStreamAgent` | UPPERCASE handlers, `callMethod()`, `agentStyles` | All `#` private fields and methods | JS private fields |
| `HTTP.stream()` | The static method itself | `_done` flag, `controller`, `pump()` inner function | Closure scope |

**Assessment:** Boundaries are enforced through a mix of underscore convention (Python), `PrivateAttr` (Pydantic), `__all__` (Python modules), JS private fields (`#`), and closure scope. The enforcement is reasonable. The weakest boundary is the `__endpoint__` dict attached to decorated functions -- it's inspected by multiple modules (`routes_fastapi.py`, `network_api.py`, `actor_model.py`) without a formal interface. However, the dict shape is simple and stable.

---

## 9. Configuration Surface

### 9.1 What Is Configurable

| Setting | Where | Default | How Changed |
|---------|-------|---------|-------------|
| `stream=True` on `@expose_route` | Decorator arg | `False` | Per-method declaration |
| `events={...}` on `@expose_route` | Decorator arg | `None` | Per-method declaration |
| `timeout` on `NetworkAdapter.request()` | Method arg | `30.0` seconds | Caller passes different value |
| `timeout` on `NetworkAdapter.stream()` | Method arg | `120.0` seconds | Caller passes different value |
| `timeout` on `_sse_from_stream()` | Hardcoded in call | `120.0` seconds | Not configurable without code change |
| `timeout` on `_stream_to_ws()` | Hardcoded in call | `120.0` seconds | Not configurable without code change |
| Stream meta markers (`stream`, `stream_end`, `seq`, `req`) | Hardcoded convention | n/a | Not configurable (by design) |
| SSE event names (`chunk`, `done`, `error`) | Hardcoded in `_sse_from_stream` | n/a | Not configurable |
| Debounce interval for markdown rendering | `NTTStreamAgent.#scheduleRender()` | `300ms` | Hardcoded |
| Auto-scroll threshold | `NTTStreamAgent.#scrollToBottom()` | `10px` | Hardcoded |
| `RECONNECT_BASE`, `RECONNECT_MAX`, `HEARTBEAT_INTERVAL` | `Socket.js` constants | 2s, 30s, 30s | Hardcoded |

### 9.2 What Should Be Configurable But Is Not

**Stream timeout** -- The 120-second timeout in `_sse_from_stream()` and `_stream_to_ws()` is hardcoded. For LLM agent tasks that may take minutes, this could cause premature termination. It should be configurable per-method (perhaps via `@expose_route(stream=True, timeout=300)`), per-model, or via global config.

**SSE heartbeat** -- There is no SSE keepalive mechanism. The HTTP SSE connection has no heartbeat, so intermediate proxies (nginx, load balancers) may close idle connections if the backend takes time between chunks (e.g., during LLM tool calls). The WS transport has heartbeats (Socket.js line 148), but HTTP SSE does not. An SSE comment line (`: keepalive\n\n`) every 15-30 seconds would solve this.

**Max output buffer size** -- There is no limit on how much text `#textBuf` in NTTStreamAgent or `#textBuf` in NTTStream can accumulate. Very long streams could cause memory issues in the browser. A configurable max buffer with truncation or windowed display would be safer.

---

## 10. Error Propagation

### 10.1 Error Flow Map

```
Error Origin             Catch Point                 Transformation              Consumer
------------             -----------                 --------------              --------

Model method throws      ActorModel.handler()        tx.exception(e)             → adapter.inbox()
(line 143-145)           try/except                  → TX(name=ERROR, ...)         → _pending Queue
                                                                                    → _sse_from_stream
                                                                                    → event: error

Async gen raises         ActorModel.handler()        tx.exception(e)             Same as above
(line 161-163)           try/except in stream loop   (no stream_end sent)

NetworkAdapter.stream()  stream() timeout            tx.error(msg, code=504)     Yielded to consumer
times out (line 152-155) asyncio.TimeoutError        (per-chunk timeout)

_sse_from_stream()       No catch                    Propagates to FastAPI       HTTP 500 from ASGI
raises (e.g., JSON err)

WS _stream_to_ws()       try/except (line 221)       ws.send_json(error)         Client WS message
raises (line 221-230)    Catches Exception           + logger.error              (best-effort)

run_stream() LLM error   try/except (line 685-691)   yield {name:'error',        → ActorModel.handler()
                         Catches Exception            data:{message:str(e)}}       → tx.chunk() (!)

Level 1/2 missing field  make_custom_post()          HTTPException(400)          HTTP 400 response
(line 322-323)           raise in arg parsing

Level 1/2 instance       make_custom_post()          HTTPException(404)          HTTP 404 response
not found (line 312)     if not instance

Frontend stream error    HTTP.stream() catch         onError(parsed) or          → STREAM_ERROR()
(line 390-396)           .catch() on reader/fetch    onError(e)                  → toast
```

### 10.2 Error Propagation Issues

**Issue 1: run_stream() error yielded as chunk, not as error TX.**
In `mixin.py:685-691`, when `run_stream()` catches an exception, it yields an error dict:
```python
yield {
    'name': 'error',
    'data': {'message': str(e), 'code': 500},
    'meta': {'stream': True, 'error': True, 'seq': seq},
}
```
This dict is then wrapped by `ActorModel.handler()` (line 157-158) as `tx.chunk(chunk_data, seq)`. The chunk has `data.name == 'error'` and `data.meta.error == True`, but the TX envelope itself is a STREAM chunk (not an ERROR TX). On the consumer side, `_sse_from_stream()` checks `chunk.is_error` (line 479) which looks at `tx.name == 'ERROR' or tx.meta.get('error')`. Since the **outer TX** does not have `meta.error=True` (the error metadata is nested inside `data.meta`), the error is serialized as `event: chunk` rather than `event: error`.

However, a closer look shows that `ActorModel.handler()` wraps the chunk as `tx.chunk(chunk_data, seq)` where `chunk_data` is `{'name': 'error', 'data': {'message': ..., 'code': 500}, 'meta': {'stream': True, 'error': True, 'seq': seq}}`. The outer TX chunk has `meta.stream=True` from `tx.chunk()` but does NOT copy the inner `meta.error`. The `is_error` check at line 479 would fail. The frontend receives this as a regular `event: chunk` whose data payload contains the error information. `NTTStream.STREAM()` then dispatches to `this.ERROR()` if it exists, or to `TEXT()` by fallback. Effectively, the error works because NTTStreamAgent defines no `ERROR()` handler but the `done` chunk that follows (or doesn't follow, since run_stream yields error and stops) triggers `STREAM_END`. The error message is lost in the stream -- it appears as a text chunk, not as an error notification.

**Recommendation:** `run_stream()` should raise the exception instead of yielding a dict, letting `ActorModel.handler()`'s existing error handling (line 161-163) produce a proper error TX via `tx.exception(e)`.

**Issue 2: No stream_end after error in ActorModel.handler().**
When the async generator raises (line 161-163), `tx.exception(e)` is sent but `tx.end()` is NOT sent. The consumer side (`NetworkAdapter.stream()`) will terminate correctly because `inbox()` removes the Queue on error TX (line 74-75). However, the SSE consumer sees `event: error` but never `event: done`. The frontend `NTTStream.STREAM()` handler calls `STREAM_ERROR()` which sets `#streaming = false`, so this works. But any consumer expecting both error and done events would be surprised.

**Issue 3: Silent JSON parse failure in HTTP.stream().**
At `HTTP.js:386`, `JSON.parse` failures are silently caught (`/* partial JSON, wait for more data */`). This is intentional for handling partial SSE frames, but it also silently swallows legitimately malformed JSON from the server. There is no logging or error reporting for these cases.

**Issue 4: Level 1/2 SSE has no error event mechanism.**
In `routes_fastapi.py`, the `sse()` inner function (lines 341-345, 390-394) does not handle exceptions from the async generator. If the generator raises, the exception propagates to FastAPI/Starlette's `StreamingResponse` handler, which may or may not send meaningful error information to the client. Level 3 handles this via `ActorModel.handler()`'s try/except (line 161-163) producing an error TX, but Level 1/2 has no equivalent -- the stream just breaks.

**Recommendation:** Wrap the `async for chunk in _gen` loop in Level 1/2 `sse()` with try/except, yielding `event: error\ndata: {json}\n\n` on exception.

### 10.3 Error Handling Strengths

- **TX.from_exception()** (`tx.py:73-96`) is a well-designed centralized exception-to-HTTP-code mapper. It handles MethodError, HTTPException, ValidationError, ValueError/TypeError, PermissionError, and KeyError with appropriate status codes.
- **NetworkAdapter.stream() finally block** (`network_adapter.py:159-162`) ensures cleanup even on timeout, error, or cancellation.
- **NTTStream.cancel()** (`ntx-stream.js:138-154`) provides graceful client-side stream termination with a STREAM_CANCEL TX (for future backend support) and immediate UI cleanup.
- **NTTStream.disconnectedCallback()** (`ntx-stream.js:156-159`) automatically cancels streams when the component is removed from the DOM.

---

## 11. Summary of Findings

### 11.1 Architectural Strengths

1. **TX envelope as universal contract.** Stream chunks, errors, and termination signals all use the same TX shape. This eliminates protocol-specific handling across the codebase.

2. **Queue-based rendezvous in NetworkAdapter.stream().** Elegantly bridges fire-and-forget actor messaging with streaming consumers. The `asyncio.create_task(self.send(tx))` + Queue pattern (lines 147-162) prevents the progressive delivery deadlock described in the comment at lines 142-146.

3. **Three-level consistency.** Level 1/2 (direct SSE), Level 3 (actor-routed SSE), and WebSocket all produce streaming output from the same `@expose_route(stream=True)` declaration. A developer declares once; the framework delivers across all transports.

4. **Frontend component hierarchy.** `NTTMethod -> NTTStream -> NTTStreamAgent -> (NTTAgentLive, NTTChat)` is a clean Template Method hierarchy. Each level adds capability without breaking the parent contract.

5. **Clean agent/actor separation.** `run_stream()` yields plain dicts; `ActorModel.handler()` wraps them in TX envelopes. The agent layer has no TX dependency in its output format.

### 11.2 Architectural Risks

1. **Code duplication between NTTStreamAgent and NTTAgentLive.** Both implement identical UPPERCASE handlers, rendering logic, and CSS. NTTAgentLive should extend NTTStreamAgent, not NTTStream.

2. **Level 1/2 SSE lacks error events.** `make_custom_post()`'s `sse()` inner function has no try/except around the generator loop. Generator errors crash the SSE stream ungracefully.

3. **run_stream() error dict escapes as a stream chunk, not an error TX.** The error metadata is nested inside `data`, so `_sse_from_stream()`'s `chunk.is_error` check fails.

4. **No SSE keepalive.** Long-running agent streams may be killed by proxies during tool call pauses. WS has heartbeats; SSE does not.

5. **Hardcoded 120s stream timeout.** Not configurable per-method. Agent tasks that involve complex multi-step tool usage may exceed this.

6. **Level 1/2 vs Level 3 SSE data format divergence.** Level 1/2 sends raw chunk data; Level 3 sends full TX envelopes. Frontend components consuming these need to handle both formats, or the format must be standardized.

### 11.3 Design Pattern Consistency

The streaming subsystem follows the project's core philosophy closely:

- **"The model is the app"** -- streaming is declared on the model (`@expose_route(stream=True)`), and everything else is derived.
- **"Transparent, not magical"** -- the TX envelope, Queue correlation, and SSE serialization are all inspectable.
- **"Zero to working, then customize"** -- NTTStream works with no configuration; NTTStreamAgent adds rich rendering without requiring the developer to understand the streaming protocol.
- **"Primitives, not opinions"** -- UPPERCASE handler dispatch is a convention that can be overridden at any level.

The main deviation from "Modular where it simplifies, coupled where it must" is the NTTStreamAgent/NTTAgentLive duplication -- this is a boundary that should be collapsed since NTTAgentLive is genuinely just NTTStreamAgent with panel chrome.
