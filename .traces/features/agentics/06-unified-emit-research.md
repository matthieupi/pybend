# Research: Unified Streaming via `Actor.emit()` Side-Channel

**Status:** Research / Design Exploration
**Date:** 2026-03-18
**Depends on:** 04-mixin-dedup.md (shared helpers)
**Branch:** `v0.10`
**Context:** This document captures a design conversation exploring how to unify streaming and non-streaming method signatures in N3TX's actor system. It documents the problem, design iterations, rejected approaches, and the current recommended direction.

---

## 1. The Problem

Streaming and non-streaming versions of the same operation require two separate methods:

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

### 1.1 Why Python forces the split

A function containing `yield` is **always** an async generator, regardless of whether the yield is reached at runtime. You cannot conditionally return a value:

```python
# ILLEGAL — a function with yield can't return a value
async def ask(self, task, stream=False):
    if stream:
        async for tx in self.agentic_stream(task=task):
            yield tx
    else:
        result = await self.agentic(task=task)
        return result  # SyntaxError in an async generator
```

### 1.2 The deeper issue

**Streaming is a transport concern, not a business logic concern.** The agent always produces intermediate results (tokens, tool calls). Whether the client sees them should be the client's choice, not the method's shape.

### 1.3 The framework-level duplication

AgentMixin has 6 public methods, where 4 exist only because of the streaming split:

| Method | Type | Purpose |
|--------|------|---------|
| `ctx()` | `@fullmethod` | Build LLM context |
| `tools()` | `@fullmethod` | Discover tool addresses |
| `agentic()` | `@fullmethod` | Policy: config cascade → `run()` |
| `agentic_stream()` | `@fullmethod` | **Duplicate of agentic() for streaming** |
| `run()` | instance | Engine: raw LLM loop |
| `run_stream()` | instance | **Duplicate of run() for streaming** |

---

## 2. The Core Idea: `emit()` as Side-Channel

Methods are always regular async functions that return a value. Intermediate results go through the actor system's TX messaging.

```python
# One method, regular async function
@expose_route('/ask', methods=['POST'], stream=True, access=AUTHENTICATED)
async def ask(self, task: str, user: User = None) -> dict:
    return await self.agentic(task=task, user=user)

# Works for custom streams too — same pattern
@expose_route('/countdown', methods=['POST'], stream=True, access=ANYONE)
async def countdown(self, n: int = 5) -> dict:
    for i in range(n, 0, -1):
        await asyncio.sleep(0.3)
        await self.emit({'count': i, 'message': f'Counting down: {i}'})
    return {'count': 0, 'message': 'Done!'}
```

One function shape everywhere. `emit()` = progress. `return` = done. Client decides streaming.

### 2.1 What the actor system already provides

| Need | Existing primitive |
|------|-------------------|
| Who's listening | `tx.source` (the adapter/client that sent the request) |
| Correlation | `tx.uuid` → `tx.chunk()` sets `meta.req` automatically |
| Delivery | `self.send()` routes through Matrix |
| Sequence tracking | `tx.chunk(data, seq)` handles seq numbering |
| Chunk reception | `NetworkAdapter.stream()` creates Queue keyed by `tx.uuid`, `inbox()` matches via `meta['req']` |

**The only missing piece**: the method doesn't have access to the originating TX. The handler does.

---

## 3. Design Iterations

### 3.1 EmitContext + contextvars (REJECTED)

**Idea:** A new `EmitContext` class wraps a callback. Set via `contextvars.ContextVar` before method dispatch. `emit()` reads it.

```python
class EmitContext:
    def __init__(self, callback):
        self._callback = callback
        self._seq = 0
        self._token = None

    async def emit(self, data):
        await self._callback(data, self._seq)
        self._seq += 1

    def __enter__(self):
        self._token = _emit_ctx.set(self)
        return self

    def __exit__(self, *a):
        _emit_ctx.reset(self._token)
```

**Why rejected:** Adds a new class and a new module-level concept. The actor system already has the primitives — this wraps them in unnecessary abstraction.

### 3.2 ContextVar on Actor + set in handler() (IMPROVED)

**Idea:** Single `ContextVar` on Actor class. `handler()` in ActorModel sets it before dispatching custom methods. Two storage paths: instance-level `_current_tx` for instance methods, ContextVar for class methods.

```python
class Actor:
    _current_tx = contextvars.ContextVar('_actor_current_tx', default=None)

    async def emit(self, data):
        tx = getattr(self, '_current_tx', None) or Actor._current_tx.get()
        if not tx:
            return
        seq = getattr(self, '_emit_seq', tx.meta.get('_emit_seq', 0))
        await self.send(tx.chunk(data, seq))
        if hasattr(self, '_emit_seq'):
            object.__setattr__(self, '_emit_seq', seq + 1)
        else:
            tx.meta['_emit_seq'] = seq + 1
```

**Why improved but not final:** Two storage paths (instance attr + ContextVar), two seq tracking paths, dual lookup in `emit()`. Works but not elegant.

### 3.3 ContextVar + set in inbox() (SIMPLER)

**Key insight:** `inbox()` is the true entry point for ALL message processing. Set the ContextVar there instead of in `handler()`. One place, all actors benefit.

```python
# actor.py — inbox() already runs interceptors then calls handler()
@actormethod
async def inbox(target, tx: TX) -> None:
    interceptors = Actor._get_interceptors(target, 'inbox')
    if interceptors:
        tx = await Actor._run_interceptors(interceptors, tx)
        if tx.is_error:
            await target.send(tx)
            return
    token = Actor._current_tx.set(tx)   # NEW — 3 lines
    try:
        await target.handler(tx)
    finally:
        Actor._current_tx.reset(token)
```

Combined with `tx.chunk()` auto-incrementing seq:

```python
# tx.py — make seq optional
def chunk(self, data, seq: int = None) -> 'TX':
    if seq is None:
        seq = self.meta.get('_seq', 0)
        self.meta['_seq'] = seq + 1
    return TX(
        name='STREAM', source=self.target, target=self.source,
        data=data if isinstance(data, dict) else {'chunk': data},
        meta={**self.meta, 'req': self.uuid, 'stream': True, 'seq': seq},
    )
```

Then `emit()` becomes trivial:

```python
@actormethod
async def emit(target, data):
    tx = Actor._current_tx.get()
    if tx:
        await target.send(tx.chunk(data))
```

**Total: ~15 lines across actor.py and tx.py. Zero changes to actor_model.py.**

**Limitation:** Still uses ContextVar, which the user wants to avoid if possible.

### 3.4 Instance-only `_tx` — no ContextVar (SIMPLEST)

**Key insight:** All streaming `@expose_route` methods in the codebase are instance methods (`self` in signature). The handler fetches a **fresh instance per request** from the DB (`cls.get(entity_id)` at `actor_model.py:115`). That instance IS the request scope.

```python
# In handler(), expose_route instance method dispatch:
instance = cls.get(entity_id)
object.__setattr__(instance, '_tx', tx)
result = method(instance, **kwargs)
```

```python
# On Actor:
async def emit(self, data):
    tx = getattr(self, '_tx', None)
    if tx:
        await self.send(tx.chunk(data))
```

**No ContextVar. No new abstractions. The instance IS the context.**

For class methods: they don't emit. No real use case exists — all streaming methods operate on a specific entity instance.

### 3.5 Lifecycle unification exploration (EXPLORED, NOT VIABLE)

**Hypothesis:** The existing `_publish_lifecycle` pattern (broadcast TX to subscribers) could be reused for streaming, killing two birds with one stone and avoiding ContextVar.

**How lifecycle works today** (`actor_model.py:302`):

```python
_subscribers: ClassVar[list] = []

@classmethod
def _publish_lifecycle(cls, event: str, data: dict):
    for subscriber_addr in cls._subscribers:
        asyncio.create_task(cls.send(TX(
            name='LIFECYCLE', source=cls.__addr__,
            target=subscriber_addr,
            data={'event': event, 'entity': data},
        )))
```

**Comparison:**

| Concern | Lifecycle | Streaming |
|---------|-----------|-----------|
| Who sends | `cls.send()` (class-level) | `self.send()` (instance-level) |
| Who receives | Permanent subscribers (WS, AP adapters) | Per-request adapter (`tx.source`) |
| Correlation | None needed (broadcast) | `meta.req` = originating `tx.uuid` |
| Subscription model | App startup, permanent | Per-request, temporary |
| Triggered by | CRUD completion | Method execution |

**Why unification doesn't work:**

1. **No correlation** — Lifecycle doesn't need `meta.req`. Streaming does. The adapter's `inbox()` matches chunks by `meta['req'] == original_tx.uuid`. Without correlation, the adapter can't distinguish chunks from concurrent requests.

2. **Subscriber data differs** — Lifecycle needs just an address. Streaming needs address + request UUID.

3. **Broadcast vs unicast** — Registering the requester as a temporary subscriber on the class would expose streaming chunks to ALL subscribers (WS adapter, AP adapter), not just the requester. Even if the adapter filters by `meta.req`, the chunks would still be routed to every subscriber unnecessarily.

4. **Class vs instance** — Lifecycle publishes at class level. Streaming publishes from a per-request instance. The `_subscribers` ClassVar is shared across all concurrent requests.

**Conclusion:** Lifecycle and streaming share the send primitive (`self.send(TX(...))`) but not the subscription model. Forcing them into one mechanism adds complexity rather than removing it. They are better understood as two applications of the same underlying actor messaging, not as two instances of the same pattern.

---

## 4. Recommended Approach (Current Best)

### Core: `instance._tx` + `tx.chunk()` auto-seq

**Two changes, two files, ~15 lines total:**

**`tx.py`** — Make `seq` optional with auto-increment:

```python
def chunk(self, data, seq: int = None) -> 'TX':
    if seq is None:
        seq = self.meta.get('_seq', 0)
        self.meta['_seq'] = seq + 1
    return TX(
        name='STREAM', source=self.target, target=self.source,
        data=data if isinstance(data, dict) else {'chunk': data},
        meta={**self.meta, 'req': self.uuid, 'stream': True, 'seq': seq},
    )
```

**`actor.py`** — Add `emit()` on Actor:

```python
async def emit(self, data):
    """Emit a progress chunk to the current request's subscriber.

    Sends a correlated TX chunk through the actor system.
    No-op when called outside a request context (no listener).
    """
    tx = getattr(self, '_tx', None)
    if tx:
        await self.send(tx.chunk(data))
```

**`actor_model.py`** — In `handler()`, set `_tx` on instance before dispatch:

```python
# Around line 115-119, instance method dispatch:
instance = cls.get(entity_id)
if not instance:
    await target.send(tx.error(f"{cls.__name__} {entity_id} not found", code=404))
    return
object.__setattr__(instance, '_tx', tx)

result = method(instance, **kwargs)
if asyncio.iscoroutine(result):
    result = await result

# _tx cleanup not strictly necessary (instance is per-request and GC'd),
# but explicit is better
object.__setattr__(instance, '_tx', None)
```

### Impact on AgentMixin

`agentic_stream()` and `run_stream()` collapse into `agentic()` and `run()`:

```python
# run() uses streaming engine internally, emits chunks
async def run(self, task, prompt, tools, llm=None, ...):
    ai_agent, run_kwargs = _setup_agent(...)

    async with ai_agent.run_stream(task, **run_kwargs) as result:
        async for event in result._stream_response:
            # Emit text deltas, thinking, tool calls as they arrive
            if isinstance(event, PartDeltaEvent):
                if isinstance(event.delta, TextPartDelta) and event.delta.content_delta:
                    await self.emit({
                        'name': 'text',
                        'data': {'text': event.delta.content_delta},
                    })
            # ... other event types ...

        output = await result.get_output()
        usage = result.usage()
        return {'answer': str(output), 'usage': {...}, 'messages': result.all_messages()}
```

**API surface: 6 methods → 4 methods** (ctx, tools, agentic, run).

### `stream=True` semantic shift

The decorator flag changes meaning:

| Before | After |
|--------|-------|
| "This function is an async generator" | "This method may emit progress" |
| Implementation constraint | Schema hint for frontend (`<ntx-stream>`) + route hint |

Schema output unchanged: `methods.countdown.stream = true` still tells frontend to use `<ntx-stream>`.

### Route layer impact

**Level 3 (`network_api.py`):** Essentially unchanged. `_add_streaming_handler` already uses `adapter.stream()` which subscribes to correlated TX chunks via `_pending` Queue. Chunks now come from `self.emit()` inside the method instead of from the handler iterating an async generator. The adapter doesn't care about the source.

**Level 1/2 (`routes_fastapi.py`):** Needs a queue bridge since there's no Matrix. The route handler creates a task, bridges emit to a queue, reads from queue for SSE. ~15 lines of code replaces the current `isasyncgen` check.

**Level 1 (ProtoModel):** No actors, no `send()`, no `emit()`. Stays with generators.

### Backward compatibility

The `isasyncgen(result)` check in `handler()` stays during transition. Existing methods using `yield` continue to work. Migration is gradual: `yield` → `await self.emit()` + `return`, at own pace.

---

## 5. Key Files Reference

### Actor system core
- **`src/n3tx/core/actors/actor.py`** — Base Actor class. `inbox()` (line 235) runs interceptors then calls `handler()`. `send()` (line 292) routes TX through Matrix. `emit()` would be added here.
- **`src/n3tx/core/actors/tx.py`** — TX message envelope. `chunk(data, seq)` (line 47) creates stream chunks. `end(data, seq)` (line 56) creates stream-end. `reply()` (line 26) swaps source/target. `meta['req']` stores correlation UUID.
- **`src/n3tx/core/actors/matrix.py`** — Root actor and message router.
- **`src/n3tx/core/actors/actor_proxy.py`** — ActorProxy wrapper for non-MI actors.

### Model and handler
- **`src/n3tx/core/models/actor_model.py`** — `handler()` (line 60) dispatches custom methods. `handler_crud()` (line 206) is sync, handles CRUD. Instance method dispatch at lines 110-119 fetches fresh instance per request. `isasyncgen` streaming path at lines 138-149. `_publish_lifecycle()` at line 302.
- **`src/n3tx/core/models/proto_model.py`** — Base model, schema pipeline, `__n3tx_methods_json_signature__()` generates method schema entries.
- **`src/n3tx/core/utils/decorators.py`** — `@expose_route(route, methods, access, stream)` decorator. `stream=True` stored in `wrapper.__endpoint__['stream']`.

### Agent system
- **`src/n3tx/core/agents/mixin.py`** — AgentMixin with `ctx()`, `tools()`, `agentic()`, `agentic_stream()`, `run()`, `run_stream()`. The streaming/non-streaming split that would collapse.
- **`src/n3tx/core/agents/actor.py`** — AgentActor (concrete model, instances ARE agents).
- **`src/n3tx/core/agents/tools.py`** — Tool discovery and function generation.
- **`src/n3tx/core/agents/schema_ext.py`** — Schema pipeline extension for `__agent__ = True`.

### Route layer
- **`src/n3tx/core/api/network_api.py`** — Level 3 HTTP routes. `_add_streaming_handler()` (line 469) creates SSE routes. `_sse_from_stream()` (line 450) converts `adapter.stream()` to SSE text lines. `_add_custom_handler()` (line 392) creates non-streaming routes.
- **`src/n3tx/core/api/network_adapter.py`** — Base adapter. `request()` (line 79) for single response. `stream()` (line 118) for streaming — creates Queue keyed by `tx.uuid`, `inbox()` matches by `meta['req']`. `_pending` dict is the correlation registry.
- **`src/n3tx/core/api/routes_fastapi.py`** — Level 1/2 direct routes. `isasyncgen` detection at lines 339, 387. SSE wrapping inline.
- **`src/n3tx/core/api/network_ws.py`** — WebSocket adapter. `LIFECYCLE` handler at line 234.

### Example apps
- **`example_actor/models/product.py`** — `ask()` (line 110, streaming agent), `countdown()` (line 81, streaming countdown), `favorite()` (line 88, non-streaming).
- **`example_chat/models/conversation.py`** — Chat streaming methods.

### Existing feature docs
- **`.traces/features/agentics/03-hardening-and-capabilities.md`** — Agent hardening plan (bugs, tests, capabilities).
- **`.traces/features/agentics/04-mixin-dedup.md`** — Extract shared helpers from AgentMixin to eliminate duplication. Prerequisite for this work.

---

## 6. Open Questions for Implementation

### 6.1 `emit()` data shape — raw or TX-shaped?

**Option A (raw):** `await self.emit({'count': i})` — framework wraps in `tx.chunk()`.
**Option B (TX-shaped):** `await self.emit({'name': 'text', 'data': {'text': delta}})` — richer control for agent chunks.

Current recommendation: Raw for custom methods, TX-shaped for agent internals. `emit()` could accept both (detect by presence of `name` key).

### 6.2 `stream_end` TX when method returns

When the method returns, `handler()` sends `tx.reply(result)`. For emit-based streaming methods, the adapter's `stream()` terminates on `stream_end` or reply. Need to verify that `tx.reply()` correctly terminates the adapter's stream Queue (it should — `inbox()` matches by `meta['req']`).

The `reply()` TX has `meta.req` set, so it WILL match the pending Queue. But it won't have `stream_end: True` — it'll just be a regular reply. The adapter's `stream()` loop checks `chunk.is_error or chunk.meta.get('stream_end')` but NOT for regular replies. **This needs fixing**: the stream loop should also terminate on reply TXs (non-STREAM name with matching `meta.req`).

### 6.3 Level 2 queue bridge — worth it?

Level 2 (ActorModel + direct routes) has actors but routes bypass them. The queue bridge adds ~15 lines. Alternative: Level 2 streaming stays with generators; `emit()` is Level 3 only. This simplifies the implementation but creates a capability gap between levels.

**Recommendation:** Implement `emit()` for Level 3 first. Level 2 queue bridge can be added later if needed. Most apps using ActorModel should use Level 3 routing anyway.

### 6.4 Class-level emit

If a future class-level method needs to emit, the `instance._tx` approach won't work. Two fallback options exist:
- Add a ContextVar (the 3.3 approach) as an enhancement
- Inject `tx` as an optional parameter (like `user` injection)

**Recommendation:** Don't build for hypothetical need. All current streaming methods are instance-level. Add class-level support only when a concrete use case emerges.

### 6.5 Agent `run()` emit integration

When `run()` internally uses `run_stream` and calls `self.emit()`, the emit goes through `self.send(tx.chunk())`. But `run()` is called from `agentic()`, which is called from the `@expose_route` method `ask()`. The `_tx` is set on the `instance` in `handler()`, and `self` inside `run()` is the same instance. So the chain works: `handler sets _tx → ask() → agentic() → run() → self.emit() → reads self._tx`.

**Needs verification** that the instance reference is preserved through the `agentic()` → `run()` call chain when `agentic()` uses `@fullmethod` and may create a new instance for class-level calls.

### 6.6 Concurrent safety

Instance-level `_tx` is safe because each request gets a fresh DB instance. But what if two concurrent requests target the same entity ID? Each gets a separate Python object from `cls.get(id)`, so they have separate `_tx`. Safe.

What about `asyncio.create_task()` inside a method? The task shares the instance reference and its `_tx`. If the method returns before the task finishes, `_tx` is set to None. The task's emits would no-op. This is correct behavior — don't emit after the request ends.

---

## 7. Implementation Sequence (When Ready)

**Prerequisites:** Complete `04-mixin-dedup.md` first (shared helpers).

1. **`tx.chunk()` auto-seq** — Make `seq` optional. Backward compatible, benefits all streaming code. (`tx.py`, ~5 lines)

2. **`Actor.emit()`** — Add method to Actor base class. (`actor.py`, ~6 lines)

3. **`handler()` wiring** — Set `instance._tx` before dispatch. (`actor_model.py`, ~3 lines)

4. **Migrate example methods** — Convert `countdown` and `ask` in `product.py`. Verify SSE output matches.

5. **Collapse AgentMixin** — Merge `run_stream()` into `run()` with internal emit. Remove `agentic_stream()`. Update tests.

6. **Verify adapter stream termination** — Ensure `tx.reply()` correctly terminates the adapter's stream Queue (open question 6.2).

7. **Update schema/frontend** — Verify `stream=True` still works as schema hint. Frontend `<ntx-stream>` unchanged.

---

## 8. Summary of Design Evolution

```
v1: EmitContext class + contextvars
    → Rejected: unnecessary abstraction over existing primitives

v2: ContextVar on Actor + set in handler(), dual storage paths
    → Too complex: two paths for instance vs class

v3: ContextVar + set in inbox(), tx.chunk() auto-seq
    → Clean (~15 lines), but ContextVar still felt like extra infrastructure

v4: instance._tx only, no ContextVar
    → Simplest possible: handler sets _tx on per-request instance, emit reads it
    → Class-level emit not supported (no real use case exists)

Lifecycle unification: explored, not viable
    → Lifecycle = broadcast to permanent subscribers
    → Streaming = unicast to per-request client with correlation
    → Different subscription models, same send primitive underneath
```

**Current recommendation: v4** — `instance._tx` + `tx.chunk()` auto-seq. ~15 lines total, zero new abstractions, zero new dependencies. Addresses 100% of real streaming use cases.
