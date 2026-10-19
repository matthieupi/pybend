# Streaming Subsystem Audit: API Surface & Contracts

**Auditor:** Claude Opus 4.6
**Date:** 2026-03-26
**Scope:** Every public API in the streaming subsystem -- parameters, return types, contracts, error handling, type safety, naming, and usage patterns across 22 core files.

---

## 1. Public API Inventory

### 1.1 Backend: TX Envelope (Stream Methods)

| Method | Signature | Returns | Side Effects |
|--------|-----------|---------|-------------|
| `TX.chunk(data, seq)` | `data: Any, seq: int` -> `TX` | New TX with `name='STREAM'`, `meta.stream=True`, `meta.seq=seq`, `meta.req=self.uuid` | None |
| `TX.end(data, seq)` | `data: Any=None, seq: int=0` -> `TX` | New TX with `meta.stream_end=True`, `meta.stream=True` | None |
| `TX.stream_chunk` | Alias for `chunk` (deprecated) | Same as `chunk` | None |
| `TX.stream_end` | Alias for `end` (deprecated) | Same as `end` | None |

**Source:** `packages/n3tx-actors/src/n3tx_actors/tx.py:47-67`

### 1.2 Backend: NetworkAdapter (Stream Infrastructure)

| Method | Signature | Returns | Side Effects |
|--------|-----------|---------|-------------|
| `NetworkAdapter.stream(tx, timeout)` | `tx: TX, timeout: float=120.0` -> `AsyncGenerator[TX]` | Yields TX chunks; terminates on `stream_end`, error, or timeout | Creates `asyncio.Queue` in `_pending`, launches `send_task` via `create_task` |
| `NetworkAdapter.inbox(tx)` | `tx: TX` -> `None` | None (dispatches to pending Future/Queue or super) | Puts TX into Queue for stream correlation; resolves Future for request correlation |
| `NetworkAdapter.request(tx, timeout)` | `tx: TX, timeout: float=30.0` -> `TX` | Single response TX | Creates `asyncio.Future` in `_pending` |

**Source:** `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py:57-163`

### 1.3 Backend: NetworkAPI (Level 3 SSE)

| Function | Signature | Returns | Side Effects |
|----------|-----------|---------|-------------|
| `_sse_from_stream(adapter, tx)` | `adapter: NetworkAdapter, tx: TX` -> `AsyncGenerator[str]` | SSE-formatted text lines (`event: chunk\ndata: {...}\n\n`) | None |
| `_add_streaming_handler(...)` | 10 params (router, adapter, model, attr, ...) | Registers FastAPI route returning `StreamingResponse` | Modifies `router` |
| `create_api_routes(api_adapter, models_dict)` | `api_adapter: NetworkAPI, models_dict: dict` -> `APIRouter` | FastAPI router with all CRUD + custom routes | None |

**Source:** `packages/n3tx-actors/src/n3tx_actors/api/network_api.py:469-540`

### 1.4 Backend: NetworkWebSocket (WS Streaming)

| Method | Signature | Returns | Side Effects |
|--------|-----------|---------|-------------|
| `NetworkWebSocket.handle_message(client_id, msg)` | `client_id: str, msg: dict` -> `dict \| None` | Response dict or None (stream goes via background task) | Spawns `_stream_to_ws` via `create_task` for stream requests |
| `NetworkWebSocket._stream_to_ws(ws, tx)` | `ws: WebSocket, tx: TX` -> `None` | None | Sends translated chunks to WebSocket client; sends error JSON on failure |

**Source:** `packages/n3tx-actors/src/n3tx_actors/api/network_ws.py:185-230`

### 1.5 Backend: routes_fastapi.py (Level 1/2 SSE)

| Function | Signature | Returns | Side Effects |
|----------|-----------|---------|-------------|
| `make_custom_post(attr, model_class, route_path)` | attr callable, model class, route string | FastAPI endpoint function | Detects `isasyncgen(result)` and wraps in `StreamingResponse` |

**Source:** `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py:283-402`

### 1.6 Backend: @expose_route Decorator

| Function | Signature | Returns |
|----------|-----------|---------|
| `expose_route(route, methods, access, stream, events)` | `route: str, methods: list=['POST'], access=None, stream: bool=False, events: dict=None` | Decorator that sets `__endpoint__` dict on the wrapped function |

**Source:** `packages/n3tx-core/src/n3tx_core/utils/decorators.py:13-88`

### 1.7 Backend: AgentMixin (Streaming Engine)

| Method | Signature | Returns |
|--------|-----------|---------|
| `AgentMixin.agentic_stream(target, task, **kwargs)` | `@fullmethod` async generator | Yields TX-aligned chunk dicts |
| `AgentMixin.run_stream(target, task, prompt, tools, ...)` | `@fullmethod` async generator | Yields dicts: `{name, data, meta}` |

**Source:** `packages/n3tx-agents/src/n3tx_agents/mixin.py:423-691`

### 1.8 Backend: AgentActor (Streaming Override)

| Method | Signature | Returns |
|--------|-----------|---------|
| `AgentActor.agentic_stream(self, task, **kwargs)` | `@expose_route('/agentic_stream', stream=True, events={...})` | Async generator of TX-aligned dicts |

**Source:** `packages/n3tx-agents/src/n3tx_agents/actor.py:170-204`

### 1.9 Backend: ActorModel.handler (Stream Dispatch)

| Method | Signature | Returns |
|--------|-----------|---------|
| `ActorModel.handler(target, tx)` | `@fullmethod` async | None -- sends TX via `target.send()` |

Stream-relevant logic at `actor_model.py:152-164`: detects `isasyncgen(result)`, iterates with `seq`, sends `tx.chunk()` and `tx.end()`.

### 1.10 Frontend: HTTP.stream()

| Method | Signature | Returns |
|--------|-----------|---------|
| `HTTP.stream(url, data, onChunk, onDone, onError)` | `url: string, data: Object, onChunk: Function, onDone: Function, onError: Function` | `{ cancel: Function }` |

**Source:** `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js:353-400`

### 1.11 Frontend: NetworkAdapter.send() (Stream Routing)

| Method | Signature | Returns |
|--------|-----------|---------|
| `NetworkAdapter.send(event)` | `event: Object` | `void` |

Stream-relevant: when `meta.stream` is truthy, calls `HTTP.stream()` instead of `HTTP.post()`.

**Source:** `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js:119-171`

### 1.12 Frontend: NTTStream Component

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `NTTStream.STREAM(data, tx)` | `data: Object, tx: Object` | void | Dispatches to UPPERCASE handlers by `data.name` |
| `NTTStream.callMethod()` | none | void | Sends TX with `meta.stream=true`, binds dynamic alias |
| `NTTStream.TEXT(data)` | `data: Object` | void | Accumulates text in buffer, renders |
| `NTTStream.STREAM_END(data)` | `data: Object` | void | Marks stream complete, refreshes parent entity |
| `NTTStream.STREAM_ERROR(data)` | `data: Object` | void | Shows toast error, marks stream failed |
| `NTTStream.cancel()` | none | void | Sets cancelled flag, sends `STREAM_CANCEL` TX |

**Source:** `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:1-173`

### 1.13 Frontend: NTTStreamAgent Component

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `NTTStreamAgent.THINKING(data, meta)` | Object, Object | void | Renders thinking entry with animation |
| `NTTStreamAgent.TOOL_CALL(data, meta)` | Object, Object | void | Renders tool call card with spinner |
| `NTTStreamAgent.TOOL_RESULT(data, meta)` | Object, Object | void | Updates tool card with result |
| `NTTStreamAgent.TEXT(data, meta)` | Object, Object | void | Rich text with markdown rendering |
| `NTTStreamAgent.DONE(data, meta)` | Object, Object | void | Shows usage footer |
| `NTTStreamAgent.STREAM_END(data)` | Object | void | Flushes pending renders |
| `NTTStreamAgent.STREAM_ERROR(data)` | Object | void | Shows error entry + toast |

**Source:** `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1-353`

---

## 2. Contracts & Invariants

### 2.1 TX Stream Envelope Invariants

**INV-1: Every chunk TX has `name='STREAM'`.**
Both `chunk()` and `end()` produce TXs with `name='STREAM'` (`tx.py:49,59`). This is critical: `NetworkAdapter.inbox()` does NOT check `name` for correlation -- it checks `meta.req`. The STREAM name is used only at the SSE layer for event type mapping.

**INV-2: Every chunk TX carries `meta.req = original_tx.uuid`.**
Verified at `tx.py:53,62`. This is the correlation key that `NetworkAdapter.inbox()` uses at `network_adapter.py:66-67` to route chunks back to the correct Queue.

**INV-3: `meta.stream=True` is present on every chunk and end TX.**
Set at `tx.py:53,62`. This flag serves two purposes: (a) frontend `NetworkAdapter.send()` uses it to route through `HTTP.stream()` (`NetworkAdapter.js:150`), (b) `_sse_from_stream()` uses it as implicit state.

**INV-4: `meta.stream_end=True` is the only termination signal.**
`NetworkAdapter.inbox()` checks `tx.meta.get('stream_end')` at line 74 to remove the Queue from `_pending`. `stream()` checks the same at line 157. An error TX also terminates via `chunk.is_error` check.

**INV-5: Source/target are swapped in chunk/end TXs.**
Both `chunk()` and `end()` set `source=self.target, target=self.source` (`tx.py:50-51,59-60`), matching `reply()` semantics. This ensures reply routing works through the Matrix.

### 2.2 NetworkAdapter.stream() Contracts

**PRE-1:** `tx.source` should be the adapter's addr (docstring, `network_adapter.py:125`). Not enforced at runtime.

**PRE-2:** A Matrix must be initialized (required for `send()` to work). Not validated -- would fail at `self.send(tx)` with an AttributeError if no Matrix exists.

**POST-1:** On normal completion, `_pending[tx.uuid]` is cleaned up. Guaranteed by `finally` block at line 160.

**POST-2:** On timeout, yields exactly one error TX with `code=504`, then returns. (`network_adapter.py:154`)

**POST-3:** `send_task` is cancelled if still running when the generator exits. (`network_adapter.py:161-162`)

**INVARIANT:** The Queue is always removed from `_pending` on exit (stream_end, error, timeout, or consumer cancellation). The `finally` block at line 160 ensures this. Verified by tests at `test_streaming.py:342-392`.

### 2.3 Level 1/2 SSE Contract (routes_fastapi.py)

**PRE:** The decorated method must be an async generator (detected via `inspect.isasyncgen(result)` at `routes_fastapi.py:340,388`).

**POST:** SSE format: `event: chunk\ndata: {json}\n\n` for each yield, then `event: done\ndata: {}\n\n` after exhaustion.

**BUG: No error event on generator exception.** If the async generator raises during iteration, the `sse()` inner function at lines 341-345 does not have a try/except. The exception propagates to FastAPI's StreamingResponse, which silently closes the connection. The client receives a truncated stream with no error event. This contrasts with Level 3, which catches exceptions in `ActorModel.handler()` at line 161 and sends an error TX.

### 2.4 Level 3 SSE Contract (network_api.py)

**POST:** SSE events use the full TX envelope: `event: chunk|done|error\ndata: {tx_dict}\n\n`. The `_sse_from_stream()` function at line 469-485 serializes the entire TX via `dataclasses.asdict()`.

**IMPORTANT DIFFERENCE FROM LEVEL 1/2:** Level 3 wraps chunk data in the full TX envelope, meaning the data payload is nested: `{name, source, target, data: {actual_data}, meta, ...}`. Level 1/2 sends the raw chunk data directly. This creates a **wire format inconsistency** between levels:

- Level 1/2 SSE chunk data: `{"count": 3, "message": "..."}`
- Level 3 SSE chunk data: `{"name": "STREAM", "source": "products", "target": "api", "data": {"count": 3, "message": "..."}, "meta": {...}}`

The actor tests at `examples/actors/tests/test_streaming.py:79-80` access `e['data']['data']['count']`, confirming the nesting. Core tests at `examples/core/tests/test_streaming.py:77` access `e['data']['count']` directly. The frontend must handle both formats.

### 2.5 Agent Streaming Contract (run_stream)

**PRE:** Matrix must be initialized (`Actor.root()` must return non-None). Raises `RuntimeError` if not (`mixin.py:499-503`).

**POST:** Yields a sequence of dicts with guaranteed structure:

```
Intermediate: {'name': str, 'data': dict, 'meta': {'stream': True, 'seq': int}}
Terminal:     {'name': 'done', 'data': {...}, 'meta': {'stream': True, 'stream_end': True, 'seq': int}}
Error:        {'name': 'error', 'data': {'message': str, 'code': int}, 'meta': {'stream': True, 'error': True, 'seq': int}}
```

**INVARIANT:** Exactly one terminal event (done or error) is always emitted. The try/except at `mixin.py:506-691` ensures that on exception, an error chunk is yielded. On success, a done chunk is always yielded at line 675-683.

**INVARIANT:** `seq` is monotonically increasing, starting at 0.

### 2.6 Frontend STREAM Dispatch Contract

**PRE:** `NTTStream.callMethod()` must be called to initiate a stream. It binds a dynamic alias (`this[method] = (data, tx) => this.STREAM(data, tx)`) so reply TXs route to `STREAM()`.

**POST:** `STREAM()` dispatches to `this[data.name.toUpperCase()]` if the handler exists, otherwise falls through to `TEXT()`.

**INVARIANT:** `STREAM_END` and `STREAM_ERROR` always set `this.#streaming = false`.

---

## 3. Error Handling Contracts

### 3.1 Error Type Taxonomy

| Layer | Error Mechanism | Error Shape | Consumer Sees |
|-------|----------------|-------------|--------------|
| TX.chunk/end | N/A (cannot fail) | N/A | N/A |
| TX.error() | Returns error TX | `{name:'ERROR', data:{message,code}, meta:{error:True}}` | TX with `is_error=True` |
| TX.from_exception() | Maps exceptions | Same, code varies by exception type | Semantic HTTP codes |
| NetworkAdapter.stream() | Timeout | `tx.error(msg, code=504)` | Error TX yielded from generator |
| NetworkAdapter.stream() | Interceptor rejection | Error TX yielded, generator returns | Single error TX |
| _sse_from_stream() | Error chunk | `event: error\ndata: {tx_dict}\n\n` | SSE error event |
| Level 1/2 SSE | Generator exception | **Silent connection close** | Truncated stream |
| Level 3 SSE | Actor handler exception | Error TX via `tx.exception(e)` | SSE error event |
| run_stream() | Any exception | `{'name':'error','data':{'message':...,'code':500}}` | Error dict yielded |
| Frontend STREAM | Error from backend | `STREAM_ERROR(data)` called | Toast + error UI |
| Frontend HTTP.stream | HTTP error (non-200) | `response.json().then(onError)` | onError callback |
| Frontend HTTP.stream | AbortError | Silenced (`e.name !== 'AbortError'`) | Nothing |

### 3.2 Error Handling Gaps

**GAP-1: Level 1/2 SSE has no error event on generator exception.**
At `routes_fastapi.py:341-345`, the `sse()` inner function iterates the async generator with no try/except:
```python
async def sse(_gen=result):
    async for chunk in _gen:
        data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
        yield f"event: chunk\ndata: {json.dumps(data, default=str)}\n\n"
    yield f"event: done\ndata: {{}}\n\n"
```
If `_gen` raises, FastAPI's StreamingResponse catches and closes the connection. The client sees a truncated stream with no done or error event. Level 3 handles this correctly through `ActorModel.handler()` at `actor_model.py:161-163`.

**GAP-2: _stream_to_ws exception handling is catch-all.**
At `network_ws.py:221-230`, `_stream_to_ws()` catches all exceptions and tries to send a JSON error to the WebSocket. If the WebSocket itself is broken, the inner exception is silently swallowed.

**GAP-3: run_stream() catches ALL exceptions including KeyboardInterrupt.**
At `mixin.py:685`, `except Exception as e:` is broad but correctly excludes BaseException subclasses like KeyboardInterrupt. However, an `asyncio.CancelledError` (which IS a subclass of BaseException in Python 3.9+) would propagate without yielding an error chunk. This is actually correct behavior for cancellation.

### 3.3 Error Code Consistency

`TX.from_exception()` (`tx.py:73-96`) provides consistent error code mapping:

| Exception Type | HTTP Code |
|---------------|-----------|
| MethodError (duck-typed) | `e.status_code` |
| HTTPException (duck-typed) | `e.status_code` |
| ValidationError | 422 |
| ValueError, TypeError | 400 |
| PermissionError | 403 |
| KeyError | 400 |
| All other | 500 |

This mapping is used consistently across `ActorModel.handler()` and `handler_crud()`. The Level 1/2 routes use direct HTTPException raising instead, so the same exception type may produce different error formats depending on the routing level.

---

## 4. Type Safety Analysis

### 4.1 Strong Typing

| Location | Type Enforcement | Mechanism |
|----------|-----------------|-----------|
| `TX` dataclass | All fields typed | Python dataclass + runtime |
| `TX.chunk(data, seq)` | `data: Any` -- duck-typed | `isinstance(data, dict)` check at line 52 |
| `NetworkAdapter.stream()` | Return type `AsyncGenerator[TX]` | Implicit (Python generator) |
| `AgentMixin.run_stream()` yield shape | Dict with `name`, `data`, `meta` keys | Convention only -- no runtime validation |
| `@expose_route` parameters | `stream: bool`, `events: dict` | No runtime enforcement |

### 4.2 Weak/Missing Typing

**WEAK-1: `TX.data` is `dict` (untyped values).**
Stream chunks carry arbitrary dicts. `TX.chunk()` wraps non-dict data in `{'chunk': data}` (`tx.py:52`), but the dict values are untyped. There is no schema validation of chunk content.

**WEAK-2: `run_stream()` yield shape is convention-only.**
The docstring at `mixin.py:472-478` specifies the chunk format, but there is no runtime validation that yielded dicts match the documented shape. A malformed chunk (e.g., missing `name` key) would propagate silently to the frontend.

**WEAK-3: `_sse_from_stream()` uses `dataclasses.asdict()` with `default=str`.**
At `network_api.py:478-485`, `json.dumps(tx_dict, default=str)` silently converts non-serializable values to strings. This is a safety net but masks serialization bugs -- a datetime or complex object becomes an opaque string.

**WEAK-4: Frontend `STREAM()` handler trusts `data.name` from the server.**
At `ntx-stream.js:29`, `const name = data?.name?.toUpperCase()` is used to dynamically dispatch to `this[name]()`. If the server sends a chunk with `name: 'constructor'` or any built-in method name, it would call that method. The `typeof this[name] === 'function'` check prevents non-function access but does not filter prototype methods. In practice, an attacker controlling the SSE stream could invoke `STREAM`, `TEXT`, `STREAM_END`, etc., but not arbitrary object methods since custom element prototypes are well-defined.

**WEAK-5: AgentActor.agentic_stream uses `**kwargs` without validation.**
At `actor.py:176`, `**kwargs` is passed through to `AgentMixin.run_stream()`. Unknown kwargs are silently accepted via `**kwargs` at `mixin.py:462`.

### 4.3 Type Leaks

**LEAK-1: `meta.model_cls` carries a Python class reference.**
Throughout `network_api.py` and `network_ws.py`, TX meta contains `model_cls` which is a Python type object. This is explicitly stripped before wire serialization in `_translate_outgoing()` at `network_ws.py:168-171` (via `_NON_SERIALIZABLE_META`), but `_sse_from_stream()` at `network_api.py:478` uses `dataclasses.asdict()` on the full TX including meta. If `model_cls` is present, `json.dumps` would fail without `default=str`, which converts it to `"<class 'Product'>"`. This is handled by the `default=str` safety net but produces garbage in the wire format.

---

## 5. Usage Patterns in the Codebase

### 5.1 Pattern: Declaring a Streaming Endpoint

```python
# Level 1/2: auto-detected by isasyncgen
@expose_route('/countdown', methods=['POST'], stream=True, access=ANYONE)
async def countdown(self, n: int):
    for i in range(n, -1, -1):
        await asyncio.sleep(0.3)
        yield {'count': i, 'message': f'Counting: {i}'}
```

The `stream=True` parameter on `@expose_route` is used in two places:
1. **Schema generation** (`proto_model.py:202-203`): adds `stream: True` to the method's schema entry.
2. **Level 3 routing** (`network_api.py:398-399`): selects `_add_streaming_handler()` instead of `_add_custom_handler()`.

For Level 1/2 (`routes_fastapi.py`), `stream=True` is **not consulted** at the routing layer. Instead, `make_custom_post()` calls the method and checks `inspect.isasyncgen(result)` at runtime (`routes_fastapi.py:340`). This means a method could declare `stream=False` but return an async generator, and Level 1/2 would still stream it. Level 3 would not.

### 5.2 Pattern: Agent Streaming (Complete Chain)

```
AgentActor.agentic_stream(task='...')           # actor.py:170
  -> AgentMixin.run_stream(task, prompt, ...)   # mixin.py:462
    -> pydantic_ai agent.iter(task)             # mixin.py:559
      -> yields {name, data, meta} dicts        # mixin.py:575-683
  -> ActorModel.handler detects isasyncgen      # actor_model.py:153
    -> tx.chunk(chunk_data, seq)                # actor_model.py:158
      -> NetworkAdapter.inbox puts in Queue     # network_adapter.py:72-73
        -> NetworkAdapter.stream yields chunk   # network_adapter.py:156
          -> _sse_from_stream formats SSE       # network_api.py:477-485
            -> StreamingResponse sends to client
```

### 5.3 Pattern: Frontend Stream Consumption (HTTP)

```
NTTStream.callMethod()                          # ntx-stream.js:40-67
  -> Actor.send(TX with meta.stream=true)       # Component.js (inherited)
    -> Matrix.dispatch(tx)                      # Matrix.js
      -> NetworkAdapter.send(event)             # NetworkAdapter.js:119
        -> meta.stream check at line 150        # NetworkAdapter.js:150
          -> HTTP.stream(url, data, cb, cb, err)  # HTTP.js:353
            -> fetch + ReadableStream parsing     # HTTP.js:361-397
              -> onChunk callback                 # HTTP.js:385
                -> NetworkAdapter.httpCallback    # NetworkAdapter.js:37
                  -> Matrix.dispatch(reply)       # NetworkAdapter.js:55
                    -> NTTStream.STREAM(data, tx) # ntx-stream.js:22
```

### 5.4 Anti-Pattern: Dual SSE Format

The most significant usage issue is the inconsistent wire format between Level 1/2 and Level 3.

**Level 1/2** (`routes_fastapi.py:342-344`):
```
event: chunk
data: {"count": 3, "message": "Counting: 3"}
```

**Level 3** (`network_api.py:485`):
```
event: chunk
data: {"name": "STREAM", "source": "products", "target": "api", "data": {"count": 3, "message": "..."}, "meta": {"req": "abc123", "stream": true, "seq": 0}, ...}
```

The frontend `NetworkAdapter.httpCallback()` at `NetworkAdapter.js:37-55` unwraps the debug envelope but does NOT unwrap the TX envelope. The commented-out `onStreamData` block at lines 153-164 shows an attempt to handle this, but it is disabled. Currently, Level 3 SSE chunks arrive at the frontend component with `data` being the full TX envelope, not the inner chunk data.

For the `NTTStream.STREAM()` handler at `ntx-stream.js:22-35`, this means:
- Level 1/2: `data = {count: 3, message: '...'}` -- `data.name` is undefined, falls to `TEXT(data)`
- Level 3: `data = {name: 'STREAM', source: '...', data: {count: 3, ...}, ...}` -- `data.name.toUpperCase()` = `'STREAM'`, dispatches to `this.STREAM()` recursively (caught by handler existing), though `data.data` has the actual content

This duality is functional but confusing. The frontend handles both through different code paths.

---

## 6. Developer Experience

### 6.1 Intuitive Aspects

1. **Declaring a streaming method is simple.** Add `stream=True` to `@expose_route` and make the method an async generator. Zero boilerplate.
2. **TX.chunk()/end() API is clean.** Mirrors reply()/error() semantics. The `seq` parameter enforces ordering consciousness.
3. **NetworkAdapter.stream() is a natural extension of request().** Same interface pattern but yielding instead of returning.
4. **Frontend component hierarchy is logical.** NTTMethod -> NTTStream -> NTTStreamAgent follows clear specialization.

### 6.2 Surprising or Confusing Aspects

**SURPRISE-1: `stream=True` on @expose_route is optional for Level 1/2.**
A developer could omit `stream=True` and their async generator would still stream correctly via Level 1/2. But it would break Level 3 routing and the schema would not include the `stream` flag. This creates a subtle bug when switching from Level 1/2 to Level 3.

**SURPRISE-2: Level 3 SSE wraps chunks in TX envelope, Level 1/2 does not.**
A developer writing frontend code for a Level 1/2 app will find that upgrading to Level 3 changes the shape of every SSE chunk. There is no documentation warning about this.

**SURPRISE-3: `NTTStream.cancel()` sends a TX but the backend ignores it.**
`cancel()` at `ntx-stream.js:138-154` sends a `STREAM_CANCEL` TX, but there is no handler for this message anywhere in the backend. The docstring says "for future backend support." Meanwhile, the cancelled stream continues sending chunks that the frontend ignores via the `#cancelled` flag. This wastes server resources.

**SURPRISE-4: `run_stream()` chunks are dicts, not TXs.**
`run_stream()` yields plain dicts (`{name, data, meta}`), not TX dataclass instances. These dicts are then wrapped in TX by `ActorModel.handler()`. A developer reading the code might expect TX objects throughout.

**SURPRISE-5: `events={}` on @expose_route only affects schema, not runtime.**
The events dict at `decorators.py:82` is serialized into the schema via `proto_model.py:205-208`, but there is no runtime validation that yielded chunks match the declared event types. A method could declare `events={'text': TextChunk}` but yield `{'name': 'foo', 'data': {'bar': 1}}` and no error would occur.

**SURPRISE-6: The `NetworkAdapter.sendStream()` method is deprecated but still exists.**
At `NetworkAdapter.js:177-181`, `sendStream()` is marked deprecated in favor of `send()` with `meta.stream`. It is not used anywhere in the codebase but remains as a public API.

### 6.3 Discoverability

The streaming API is spread across 7+ files with no single reference document. A developer would need to read:
1. `decorators.py` for the `@expose_route` signature
2. `proto_model.py` for schema generation
3. `routes_fastapi.py` for Level 1/2 behavior
4. `network_api.py` for Level 3 behavior
5. `tx.py` for the chunk/end protocol
6. `network_adapter.py` for Queue-based correlation
7. `ntx-stream.js` for frontend consumption

The CLAUDE.md file provides a good overview but does not cover the wire format differences between levels or the `events={}` schema-only nature.

---

## 7. Naming Analysis

### 7.1 Naming Consistency Audit

| Name | Convention | Consistent? | Notes |
|------|-----------|-------------|-------|
| `TX.chunk()` / `TX.end()` | Verb-noun | Yes | Clean, mirrors `reply()`/`error()` |
| `TX.stream_chunk` / `TX.stream_end` | Deprecated aliases | N/A | Correctly marked deprecated |
| `NetworkAdapter.stream()` | Verb | Yes | Parallels `request()` |
| `_sse_from_stream()` | Private helper | Yes | Clear purpose |
| `_add_streaming_handler()` | Private helper | Yes | Parallels `_add_custom_handler()` |
| `NTTStream` | Class convention | Yes | Matches NTTMethod, NTTItem pattern |
| `STREAM()` | UPPERCASE handler | Yes | TX inbox convention |
| `STREAM_END` / `STREAM_ERROR` | UPPERCASE handler | Yes | Clear semantics |
| `run_stream()` | Parallels `run()` | Yes | Consistent split |
| `agentic_stream()` | Parallels `agentic()` | Yes | Consistent split |
| `meta.stream` | Boolean flag | Ambiguous | Could mean "is streaming" or "stream ID" |
| `meta.stream_end` | Boolean flag | Yes | Clear termination signal |
| `meta.req` | Correlation ID | Yes | Matches `reply()` pattern |
| `#streaming` | Private field | Yes | Standard JS convention |
| `#cancelled` | Private field | Yes | Clear semantics |

### 7.2 Naming Issues

**ISSUE-1: `chunk()` vs `stream_chunk` naming transition.**
`chunk()` and `end()` are the current API. `stream_chunk` and `stream_end` are backward-compat aliases. But the deprecated names are more descriptive -- `chunk()` alone does not convey "stream chunk" without context. The migration is reasonable but could confuse someone reading code that uses the old names.

**ISSUE-2: `STREAM` as both TX name and handler name.**
Backend uses `name='STREAM'` for all chunk/end TXs. Frontend `NTTStream.STREAM()` is the inbox handler. When `STREAM()` dispatches to `this[data.name.toUpperCase()]`, and `data.name` happens to be `'STREAM'` (from a Level 3 TX envelope), it would recursively call `this.STREAM()`. This is caught by the dispatch logic but creates a confusing naming collision.

**ISSUE-3: `_sse_from_stream` uses "stream" to mean the adapter method, not SSE.**
The function converts `NetworkAdapter.stream()` output to SSE text. The name is technically accurate but could be clearer: `_adapter_stream_to_sse()` or `_format_sse_events()`.

---

## 8. Parameter Validation

### 8.1 Boundary Validation

| API | Parameter | Validated? | How |
|-----|-----------|-----------|-----|
| `TX.chunk(data, seq)` | `data` | Partial | `isinstance(data, dict)` check wraps non-dict in `{'chunk': data}` |
| `TX.chunk(data, seq)` | `seq` | No | Any value accepted; no range check |
| `NetworkAdapter.stream(tx, timeout)` | `timeout` | No | Passed to `asyncio.wait_for`; negative values would cause immediate timeout |
| `NetworkAdapter.stream(tx, timeout)` | `tx` | No | No validation that `tx.source == self.addr` |
| `HTTP.stream(url, data, ...)` | All callbacks | No | `onChunk`/`onDone`/`onError` could be `null` causing runtime error |
| `expose_route(stream=True)` | `stream` | No | Truthy check only at `network_api.py:398` |
| `expose_route(events={...})` | `events` | No | Values should be ProtoModel subclasses but not checked |
| `run_stream(tools=[])` | `tools` | Implicit | Empty list is valid; `discover_tools` returns [] |
| `NTTStream.callMethod()` | `this.method` | Partial | Checked via `methodSchema` existence in `load()` |

### 8.2 Missing Validation

**MISSING-1: `TX.chunk()` does not validate `seq` type or value.**
Negative or float `seq` values are silently accepted. The `seq` field is used for ordering but never checked.

**MISSING-2: `NetworkAdapter.stream()` does not validate `tx.source`.**
The docstring says "`tx.source` should be this adapter's addr" but there is no runtime check. A mismatched source would cause reply TXs to route to the wrong actor.

**MISSING-3: `HTTP.stream()` does not validate callback types.**
If `onDone` is `null`, line 373 (`if (!_done) onDone({})`) would throw `TypeError: onDone is not a function`.

**MISSING-4: `@expose_route(events=...)` values are not validated.**
The `events` dict maps names to classes. If a value is not a ProtoModel subclass, `model_json_schema()` at `proto_model.py:207` would fail at schema generation time, not at decoration time. The error would be confusing.

---

## 9. Return Value Contracts

### 9.1 Shape Consistency Analysis

**TX.chunk() / TX.end():** Always returns a TX dataclass. Consistent.

**NetworkAdapter.stream():** Always yields TX instances. The terminal TX is either a stream_end, error, or timeout error. Consistent.

**_sse_from_stream():** Always yields strings in SSE format. Three formats: `event: chunk`, `event: done`, `event: error`. Consistent.

**run_stream():** Yields dicts. Shape varies by event type:

| Event | Required Keys | Shape |
|-------|--------------|-------|
| `text` | `name, data.text, meta.stream, meta.seq` | `{'name': 'text', 'data': {'text': str}, 'meta': {'stream': True, 'seq': int}}` |
| `tool_call` | `name, data.tool, data.args, data.call_id, meta.stream, meta.seq` | Full tool call info |
| `tool_result` | `name, data.tool, data.result, data.call_id, meta.stream, meta.seq` | Full tool result info |
| `thinking` | `name, data.text, meta.stream, meta.seq` | Thinking text |
| `done` | `name, data.answer, data.usage, data.tool_calls, meta.stream_end` | Terminal with stats |
| `error` | `name, data.message, data.code, meta.error` | Error with code |

All share the `{name, data, meta}` top-level shape. **Consistent within the subsystem.**

**Level 1/2 SSE chunk data:** Shape of the yielded dict from the async generator. **Varies by method** -- no guaranteed shape. The framework wraps non-dict chunks in `{'chunk': value}` (`routes_fastapi.py:343`).

**Level 3 SSE chunk data:** Full TX envelope dict. **Always consistent shape** (name, source, target, data, meta, timestamp, uuid).

### 9.2 Contract Violations

**VIOLATION-1: `AgentActor.agentic()` returns `json.dumps(result, default=str)` (a string), but `agentic_stream()` yields dicts.**
At `actor.py:168`, the non-streaming `agentic()` returns a JSON string. The streaming variant yields raw dicts. This inconsistency means the handler dispatch path in `ActorModel.handler()` at line 172-178 parses the JSON string back into a dict for the reply TX. Not a bug, but architecturally surprising.

---

## 10. Lifecycle & Ordering

### 10.1 Required Initialization Sequence

```
1. Matrix()                           # Creates root actor
2. matrix.register(NetworkAPI/WS)     # Register adapter as child
3. adapter.use(auth_interceptor)      # Install interceptors
4. create_api_routes(adapter, models) # Create FastAPI routes
5. app.include_router(router)         # Mount on FastAPI
```

If step 2 is skipped, `adapter.send()` has no Matrix to route through. If step 3 is after step 4, auth won't be enforced.

### 10.2 Stream Lifecycle (Backend)

```
1. HTTP request arrives at FastAPI route
2. _add_streaming_handler creates TX with meta.stream=True
3. StreamingResponse starts; _sse_from_stream called
4. adapter.stream(tx) called:
   a. Interceptors run (auth check)
   b. Queue created in _pending
   c. send_task launched via create_task
   d. send_task delivers TX to actor via Matrix
5. ActorModel.handler detects async generator
6. For each yield: tx.chunk() sent through Matrix -> adapter.inbox -> Queue
7. adapter.stream yields from Queue -> _sse_from_stream formats SSE
8. Generator exhausted: tx.end() sent -> Queue -> stream terminates
9. _pending cleanup (finally block)
10. StreamingResponse closes connection
```

### 10.3 Stream Lifecycle (Frontend)

```
1. NTTStream.callMethod() called (user interaction or programmatic)
2. Dynamic alias bound: this[method] = STREAM handler
3. TX sent with meta.stream=true
4. NetworkAdapter.send() detects meta.stream, calls HTTP.stream()
5. fetch() opens SSE connection
6. pump() reads ReadableStream chunks
7. SSE events parsed, onChunk/onDone called
8. httpCallback wraps as reply, dispatches through Matrix
9. Component's STREAM() handler dispatches to UPPERCASE handlers
10. On STREAM_END/STREAM_ERROR: streaming flag cleared, entity refreshed
```

### 10.4 Cleanup Requirements

| Resource | Cleaned Up By | When |
|----------|--------------|------|
| `_pending[tx.uuid]` (Queue) | `finally` in `stream()` | Always on exit |
| `send_task` | `finally` in `stream()` | Cancelled if not done |
| `AbortController` (frontend) | `HTTP.stream().cancel()` | Called by `NTTStream.cancel()` or `disconnectedCallback()` |
| Dynamic alias (`this[method]`) | Not cleaned up | **LEAK**: persists on the component instance |
| `#textTimer` / `#thinkTimer` (NTTStreamAgent) | `disconnectedCallback()` + `callMethod()` | On unmount or new stream |

**LEAK: Dynamic alias not cleaned up.** At `ntx-stream.js:55`, `this[name] = (data, tx) => this.STREAM(data, tx)` is set on `callMethod()`. If `callMethod()` is called with a different method name, the old alias is deleted at line 53. But if the component is reused with the same method, or if `STREAM_END` fires, the alias persists. This is harmless but untidy.

---

## 11. Documentation Gaps

### 11.1 Undocumented

1. **Wire format difference between Level 1/2 and Level 3 SSE.** The nesting of chunk data in the TX envelope is not documented anywhere. A developer writing frontend code would discover this through debugging.

2. **`STREAM_CANCEL` TX is not implemented on the backend.** The frontend sends it but nothing handles it. The docstring in `ntx-stream.js:133-136` says "for future backend support" but this is not mentioned in any architecture doc.

3. **`events={}` is schema-only, no runtime validation.** The `@expose_route` docstring at `decorators.py:23-25` explains what it does for schema but does not say "this does not validate yielded chunks at runtime."

4. **How `run_stream()` yields differ from `run()` returns.** `run()` returns `{answer, usage, messages, message_count}`. `run_stream()` yields progressive events but the done event shape is `{answer, usage, tool_calls}` -- `messages` and `message_count` are absent from the done event. Not documented.

5. **Frontend NTTStreamAgent requires `marked` library for markdown.** At `ntx-stream-agent.js:213`, `typeof marked !== 'undefined'` is checked. If `marked` is not loaded, text renders as plain text without markdown. This dependency is implicit and undocumented.

### 11.2 Documented But Potentially Stale

1. **`TX.stream_chunk` / `TX.stream_end` aliases.** Marked deprecated but still referenced in test code (`test_streaming_shutdown.py:77`). The test uses `stream_end()` instead of `end()`.

2. **`NetworkAdapter.sendStream()` on the frontend.** Marked deprecated at `NetworkAdapter.js:176` but the deprecation notice is only in a JSDoc comment. No console warning is emitted.

### 11.3 Documentation Correctness Issues

**ISSUE: CLAUDE.md says "SSE wire format: `event: chunk|done|error`"** -- this is correct for both levels, but the `data:` payload shape differs significantly between levels. The documentation should clarify:
- Level 1/2: `data` is the raw chunk dict from the generator
- Level 3: `data` is the full TX envelope dict

---

## 12. Summary of Findings

### 12.1 Critical Issues (Functional Impact)

| ID | Issue | Location | Impact |
|----|-------|----------|--------|
| BUG-1 | Level 1/2 SSE has no error event on generator exception | `routes_fastapi.py:341-345` | Client sees truncated stream with no error signal |
| BUG-2 | Wire format inconsistency between Level 1/2 and Level 3 | Multiple files | Frontend must handle two different chunk data shapes |

### 12.2 Moderate Issues (Developer Experience)

| ID | Issue | Location | Impact |
|----|-------|----------|--------|
| DX-1 | `stream=True` is not required for Level 1/2 streaming | `routes_fastapi.py:340` | Silent misbehavior when upgrading to Level 3 |
| DX-2 | `events={}` has no runtime validation | `decorators.py:82`, `proto_model.py:205` | Schema promises that runtime does not enforce |
| DX-3 | `STREAM_CANCEL` TX sent but never handled | `ntx-stream.js:145-151` | Wasted server resources on cancelled streams |
| DX-4 | No single reference doc for streaming API | Cross-cutting | High onboarding cost |

### 12.3 Minor Issues (Code Quality)

| ID | Issue | Location | Impact |
|----|-------|----------|--------|
| QA-1 | Dynamic handler alias not cleaned up on STREAM_END | `ntx-stream.js:55` | Memory leak (minor, same-method reuse is common) |
| QA-2 | `HTTP.stream()` does not validate callbacks | `HTTP.js:353` | Would crash if onDone/onError is null |
| QA-3 | `meta.model_cls` leaks into TX envelope on Level 3 SSE | `network_api.py:512-513` | Produces `"<class 'Product'>"` in JSON; harmless but noisy |
| QA-4 | Code duplication in NTTStreamAgent and NTTAgentLive | Both files | Nearly identical UPPERCASE handlers (~150 lines duplicated) |
| QA-5 | `test_streaming_shutdown.py:77` uses deprecated `stream_end()` alias | `test_streaming_shutdown.py:77` | Tests should use current API |
