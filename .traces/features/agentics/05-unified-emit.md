# Unified Streaming: `Actor.emit()` Side-Channel

**Status:** Proposal
**Date:** 2026-03-14
**Depends on:** 04-mixin-dedup.md (shared helpers)
**Branch:** `v0.10`

---

## Problem

Streaming and non-streaming versions of the same operation require two methods:

```python
# Today: two methods, two signatures, two decorator configs
@expose_route('/ask', methods=['POST'], stream=True, access=AUTHENTICATED)
async def ask(self, task: str, user: User = None) -> AsyncGenerator[TX, Any]:
    async for tx in self.agentic_stream(task=task, user=user):
        yield tx

@expose_route('/ask-sync', methods=['POST'], access=AUTHENTICATED)
async def ask_sync(self, task: str, user: User = None) -> str:
    result = await self.agentic(task=task, user=user)
    return json.dumps(result)
```

This is a Python language constraint: a function with `yield` is always an async generator. You can't conditionally `return value` from one. So the method signature dictates the transport behavior.

The deeper issue: **streaming is a transport concern, not a business logic concern.** The agent always produces intermediate results (tokens, tool calls). Whether the client sees them should be the client's choice, not the method's shape.

---

## Design: `emit()` as Actor Side-Channel

Methods are always regular async functions that return a value. Intermediate results go through the actor system's TX messaging via `self.emit(data)`.

```python
# Proposed: one method, regular async function
@expose_route('/ask', methods=['POST'], stream=True, access=AUTHENTICATED)
async def ask(self, task: str, user: User = None) -> dict:
    return await self.agentic(task=task, user=user)
```

```python
# Works for custom streams too
@expose_route('/countdown', methods=['POST'], stream=True, access=ANYONE)
async def countdown(self, n: int = 5) -> dict:
    for i in range(n, 0, -1):
        await asyncio.sleep(0.3)
        await self.emit({'count': i, 'message': f'Counting down: {i}'})
    return {'count': 0, 'message': 'Done!'}
```

One function shape. `emit()` = progress. `return` = done. Client decides if it wants to see progress.

---

## Why the Actor IS the Context

No new infrastructure needed. The actor system already provides everything:

| Need | Existing primitive |
|------|-------------------|
| Who's listening | `tx.source` (the adapter/client that sent the request) |
| Correlation | `tx.uuid` → `tx.chunk()` sets `meta.req` automatically |
| Delivery | `self.send()` routes through Matrix |
| Sequence tracking | `tx.chunk(data, seq)` already handles seq numbering |

The only missing piece: the method doesn't have access to the originating TX. The handler does.

---

## Implementation

### Where to wire: `handler()`, not `handler_crud`

`handler_crud` (line 206 of `actor_model.py`) is a sync `@classmethod` — it handles CRUD operations and returns values. Custom `@expose_route` methods are dispatched in `handler()` (line 60), which is async and has the TX.

The wiring point is `handler()`'s expose_route dispatch block (lines 110-121).

### Instance methods: `_current_tx` on the instance

For instance methods, the instance is fetched fresh from the DB per request (`cls.get(entity_id)` at line 115). It's naturally per-request scoped — no shared state.

```python
# In handler(), instance method dispatch (around line 115-119):
instance = cls.get(entity_id)
if not instance:
    await target.send(tx.error(...))
    return

# Set TX context on the per-request instance
object.__setattr__(instance, '_current_tx', tx)
object.__setattr__(instance, '_emit_seq', 0)

result = method(instance, **kwargs)
if asyncio.iscoroutine(result):
    result = await result

object.__setattr__(instance, '_current_tx', None)
```

### Class methods: ContextVar (one line)

For class methods (no `self` in signature), the class is shared — concurrent requests would overwrite `_current_tx`. Since asyncio coroutines interleave at `await` points, a single ContextVar on Actor provides per-coroutine isolation:

```python
import contextvars

class Actor:
    _current_tx: ClassVar = contextvars.ContextVar('_actor_current_tx', default=None)
```

In `handler()`, class method dispatch (around line 120-121):

```python
token = Actor._current_tx.set(tx)
try:
    result = method(**kwargs)
    if asyncio.iscoroutine(result):
        result = await result
finally:
    Actor._current_tx.reset(token)
```

This isn't new infrastructure — it's "which TX am I currently processing," a natural actor concept stored with a standard Python primitive.

### `emit()` on Actor

Checks instance-level `_current_tx` first (fast path for instance methods), falls back to ContextVar (class methods):

```python
class Actor:
    async def emit(self, data):
        """Emit a progress chunk to the current request's subscriber.

        Sends a correlated TX chunk through the actor system.
        No-op when called outside a request context (no listener).
        """
        tx = getattr(self, '_current_tx', None) or Actor._current_tx.get()
        if not tx:
            return
        seq = getattr(self, '_emit_seq', tx.meta.get('_emit_seq', 0))
        await self.send(tx.chunk(data, seq))
        # Track seq — instance attr for instance methods, tx.meta for class methods
        if hasattr(self, '_emit_seq'):
            object.__setattr__(self, '_emit_seq', seq + 1)
        else:
            tx.meta['_emit_seq'] = seq + 1
```

### `stream=True` becomes a capability declaration

The decorator flag shifts meaning:

| Before | After |
|--------|-------|
| "This function is an async generator" | "This method may emit progress" |
| Implementation constraint | Schema hint + route hint |
| Frontend: use `<ntx-stream>` | Frontend: use `<ntx-stream>` (unchanged) |
| Route: use `_add_streaming_handler` | Route: set up emit context, be prepared to stream |

The schema output is unchanged: `methods.countdown.stream = true` tells the frontend to use `<ntx-stream>`.

---

## Impact on AgentMixin

### `agentic()` unification

With `emit()`, `agentic()` always uses the streaming LLM engine internally and emits chunks as it works. The split between `agentic()` and `agentic_stream()` collapses:

```python
@fullmethod
async def agentic(target, task: str, **kwargs) -> dict:
    """Single entry point for agent reasoning. Always returns final result.

    Intermediate results (LLM tokens, tool calls) are emitted as TX
    chunks via self.emit(). Clients that want streaming subscribe to
    the chunks; others just get the return value.
    """
    conf = _resolve_config(target, task, **kwargs)
    adapter, root = _create_adapter()
    try:
        instance = target if not isinstance(target, type) else target()
        return await instance.run(task=task, adapter=adapter, **conf)
    finally:
        root._children.pop(adapter._addr, None)
```

### `run()` uses streaming engine + emit

```python
async def run(self, task, prompt, tools, llm=None, ...):
    ai_agent, run_kwargs = _setup_agent(...)

    async with ai_agent.run_stream(task, **run_kwargs) as result:
        async for event in result._stream_response:
            if isinstance(event, PartDeltaEvent):
                if isinstance(event.delta, TextPartDelta) and event.delta.content_delta:
                    await self.emit({
                        'name': 'text',
                        'data': {'text': event.delta.content_delta},
                    })
            # ... other event types (thinking, tool_call) ...

        output = await result.get_output()
        usage = result.usage()
        return {
            'answer': str(output),
            'usage': {...},
            'messages': result.all_messages(),
        }
```

### Methods that collapse

| Before | After |
|--------|-------|
| `agentic()` | `agentic()` (unchanged API, uses streaming engine internally) |
| `agentic_stream()` | **removed** — `agentic()` emits via side-channel |
| `run()` | `run()` (uses `run_stream` internally, emits chunks) |
| `run_stream()` | **removed** — `run()` emits via side-channel |

API surface: 6 methods (ctx, tools, agentic, agentic_stream, run, run_stream) shrinks to 4 (ctx, tools, agentic, run). The split that existed because of Python's generator constraint disappears.

---

## Route Layer Changes

### Level 3: `network_api.py`

The streaming handler in `_add_streaming_handler` currently expects the method to return an async generator. Under the new model, the handler subscribes to TX chunks emitted by the actor during execution:

```python
# Conceptual — streaming handler for emit-based methods
async def stream_with_id(request, id, data, ...):
    user = _get_user(request)
    payload = _parse_method_args(...)
    payload['id'] = id

    tx = TX(
        name=attr_name, source=api_adapter.addr, target=addr,
        data=payload,
        meta={'user': user, 'model_cls': cls, 'stream': True},
    )

    # adapter.stream() already subscribes to correlated chunks
    return StreamingResponse(
        _sse_from_stream(api_adapter, tx),
        media_type="text/event-stream",
    )
```

This is essentially **unchanged** — `_sse_from_stream` already reads chunks from `adapter.stream()`, which subscribes to correlated TX replies. The difference is that chunks now come from `self.emit()` inside the method, not from the handler iterating an async generator. The transport layer doesn't care about the source.

### Level 1/2: `routes_fastapi.py`

Level 1/2 routes call methods directly (no actor routing). For `stream=True` methods, the route handler uses a queue bridge:

```python
# In routes_fastapi.py, for stream=True methods:
async def handle_streaming(instance, method, parsed_args):
    queue = asyncio.Queue()

    # Bridge: emit() → queue (since there's no Matrix in Level 1/2)
    original_emit = instance.emit
    async def queue_emit(data):
        await queue.put(('chunk', data))
    object.__setattr__(instance, 'emit', queue_emit)

    async def run():
        try:
            result = method(instance, **parsed_args)
            if asyncio.iscoroutine(result):
                result = await result
            await queue.put(('done', result))
        except Exception as e:
            await queue.put(('error', str(e)))
        finally:
            object.__setattr__(instance, 'emit', original_emit)

    asyncio.create_task(run())

    async def sse():
        while True:
            kind, data = await queue.get()
            if kind == 'chunk':
                payload = data if isinstance(data, dict) else {'chunk': data}
                yield f"event: chunk\ndata: {json.dumps(payload, default=str)}\n\n"
            elif kind == 'done':
                yield f"event: done\ndata: {json.dumps(data, default=str)}\n\n"
                break
            elif kind == 'error':
                yield f"event: error\ndata: {json.dumps({'message': data})}\n\n"
                break

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
```

### Non-streaming clients

If `stream=True` is not on the decorator, or the client doesn't want streaming: no emit context is set, `emit()` is a no-op, the return value is the response. Zero overhead.

---

## Backward Compatibility

### Async generators still work (transition period)

The `isasyncgen(result)` check in `handler()` (line 138) stays during the transition. Existing methods that use `yield` continue to work. The handler processes them the same way:

```python
# In handler(), after method call:
if inspect.isasyncgen(result):
    # Legacy path — existing streaming methods
    seq = 0
    async for chunk in result:
        chunk_data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
        await target.send(tx.chunk(chunk_data, seq))
        seq += 1
    await target.send(tx.end(seq=seq))
    return
```

Migration is gradual: convert `yield` → `await self.emit()` + `return` at your own pace. Both patterns work simultaneously.

### `agentic_stream()` deprecation

Keep `agentic_stream()` as a thin wrapper that calls `agentic()` and subscribes to the TX chunks. Mark deprecated. Remove in next major version.

---

## Applicability by Level

| Level | Actor system | `emit()` works via | Notes |
|-------|-------------|-------------------|-------|
| Level 1 (ProtoModel) | No | N/A | No actors, no `send()`. Use generators or upgrade to ActorModel. |
| Level 2 (ActorModel + direct routes) | Yes | Queue bridge in routes_fastapi.py | `emit()` → queue → SSE |
| Level 3 (ActorModel + NetworkAPI) | Yes | TX chunks through Matrix | `emit()` → `self.send(tx.chunk())` → adapter → SSE |

Level 1 stays with generators. `emit()` is an ActorModel capability — if you want it, you're choosing Level 2+. One import change: `ProtoModel` → `ActorModel`.

---

## Files Changed

| File | Change |
|------|--------|
| `src/n3tx/core/actors/actor.py` | Add `_current_tx` ContextVar, `emit()` method |
| `src/n3tx/core/models/actor_model.py` | Wire `_current_tx` in `handler()` dispatch |
| `src/n3tx/core/agents/mixin.py` | Collapse `agentic_stream()` → `agentic()`, `run_stream()` → `run()` with internal emit |
| `src/n3tx/core/api/network_api.py` | Streaming handler unchanged (already reads TX chunks from adapter) |
| `src/n3tx/core/api/routes_fastapi.py` | Add queue bridge for Level 2 emit-based streaming |
| `example_actor/models/product.py` | Migrate `countdown` and `ask` to emit pattern |
| `example_chat/models/conversation.py` | Migrate streaming methods to emit pattern |

---

## What This Unlocks

1. **One method per operation** — no more ask/ask_sync pairs
2. **Agent streaming for free** — `agentic()` emits during LLM execution, no separate `agentic_stream()`
3. **Client-driven streaming** — same endpoint, client chooses SSE or final-result-only
4. **Simpler mental model** — `emit()` = progress, `return` = done
5. **Actor-native** — streaming uses the same TX messaging as everything else
6. **4 public methods instead of 6** on AgentMixin (ctx, tools, agentic, run)

---

## Open Questions

1. **Should `emit()` data be TX-shaped or raw?** Current proposal: raw dicts, the framework wraps in `tx.chunk()`. Alternative: developer passes TX-shaped `{name, data, meta}` for richer control.

2. **Level 2 queue bridge complexity** — Is the queue bridge in routes_fastapi.py worth it, or should Level 2 stick with generators and only Level 3 gets `emit()`?

3. **`stream_end` TX** — When the method returns, should `handler()` automatically send `tx.end()`? Currently the handler sends `tx.reply(result)` for regular returns. For emit-based methods, the final reply IS the end signal. Need to verify `_sse_from_stream` handles this correctly.

4. **Concurrent emit safety** — Instance-level `_emit_seq` is safe (per-request instance). Class-level ContextVar is safe (per-coroutine). But what about methods that spawn background tasks internally? Those tasks inherit the ContextVar but may outlive the request. Needs investigation.

---

## Verification

1. **Unit tests:** Emit on instance method, emit on class method, emit with no listener (no-op), emit sequence numbering
2. **Integration (Level 3):** Product.countdown using emit, verify SSE output matches current generator-based output
3. **Integration (Level 2):** Same test via routes_fastapi.py queue bridge
4. **Agent integration:** Product.ask using single `agentic()`, verify streaming chunks arrive via SSE
5. **Backward compat:** Existing generator-based methods still work unchanged
6. **Schema:** `methods.countdown.stream = true` still present, frontend unchanged
