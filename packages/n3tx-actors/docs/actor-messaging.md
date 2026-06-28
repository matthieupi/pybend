# Actor Messaging and Routing

> Part of [n3tx-actors](../README.md)

## What This Covers

The Actor messaging lifecycle: how TX messages are created, dispatched through `inbox()`, handled by `handler()`, and routed via `send()`. Covers class-level vs instance-level dispatch, the `ActorMeta` metaclass, address resolution, and the routing algorithm at each level (instance, class, Matrix). Does not cover interceptors (see [interceptors.md](interceptors.md)) or network adapters (see [network-adapters.md](network-adapters.md)).

## Architecture

```
TX created (name, source, target, data, meta)
    |
    v
actor.inbox(tx)
    |-- run 'inbox' interceptors (if any)
    |-- if error TX: send error back, skip handler
    v
actor.handler(tx)
    |-- getattr(target, tx.name) -> method
    |-- call method(data, tx) or method(tx.data, tx)
    |-- wrap return: dict -> reply, TX -> send direct, scalar -> {result: val}
    |-- exception -> tx.exception(e) -> error TX
    v
actor.send(reply_tx)
    |-- run 'send' interceptors (if any)
    |-- INSTANCE: route through parent chain
    |-- CLASS: 3-case routing:
    |     1. direct child match (seg_first in children)
    |     2. strip own prefix, route to child (seg_first == addr)
    |     3. prefix source, bubble to parent (Matrix)
    v
Matrix.inbox(tx)
    |-- self-send prevention (target == 'matrix' -> blocked)
    |-- local child match -> child.inbox(tx)
    |-- no local match -> try adapters -> _route_error()
```

## Interface

### TX Construction

```python
TX(name='create', source='api', target='products', data={'name': 'W'}, meta={'user': {...}})
```

Required: `name`, `source`, `target`. Optional: `data` (default `{}`), `meta` (default `{}`). Auto-generated: `timestamp` (float), `uuid` (12-char hex).

### TX Methods

| Method | Returns | Behavior |
|--------|---------|----------|
| `reply(data, name)` | TX | Swaps source/target, new uuid, stores original in `meta['req']`, default name=`{name}_RESPONSE` |
| `error(msg, code)` | TX | name=`ERROR`, `meta['error']=True`, data=`{message, code}` |
| `chunk(data, seq)` | TX | name=`STREAM`, `meta['stream']=True`, correlates via `meta['req']` |
| `end(data, seq)` | TX | name=`STREAM`, `meta['stream_end']=True` |
| `exception(e)` | TX | Maps exception type to semantic HTTP code (ValidationError->422, ValueError->400, etc.) |

### Handler Return Wrapping

| Return type | Wrapped as |
|-------------|------------|
| `TX` | Sent directly (no wrapping) |
| `dict` | `tx.reply(data=result)` |
| Scalar (int, str, etc.) | `tx.reply(data={'result': value})` |
| `None` | `tx.reply()` (empty data) |
| Exception raised | `tx.exception(e)` (error TX) |

Unhandled messages (no matching method) produce `tx.error("Unhandled message: {name}")`. Exception: error TXs and `*_RESPONSE` TXs with no handler are silently dropped to prevent infinite bounce loops.

`ERROR` remains a normal routable message when the target actor explicitly
implements an `ERROR(data, tx)` handler. That lets fire-and-forget messages
still bubble failures back to their issuer. The terminal rule is narrower: if
an `ERROR` handler itself raises, the framework logs and drops that failure
instead of synthesizing another `ERROR` in response to an `ERROR`.

### Address Resolution

`ActorMeta.__new__` sets `__addr__` on each subclass:
1. Explicit `__addr__` in namespace -- used as-is
2. `__tablename__` attribute -- used if present
3. Class `__name__` -- fallback

Instance `_addr` resolution follows this order:
1. explicit `addr=` kwarg
2. `f"{__addr__}/{id}"` when the instance has a truthy persisted `id`
3. class `__addr__`

This means hydrated `ActorModel` records such as `Product.get(1)` identify
themselves as `products/1`, while unsaved instances still default to the
class namespace `products`.

### Class-Level Send Routing (3 cases)

```python
segments = tx.target.split('/')
# Case 1: segments[0] in children -> children[segments[0]].inbox(tx)
# Case 2: segments[0] == own addr and segments[1] in children -> strip prefix, route
# Case 3: no match -> prefix source with own addr, bubble to parent (Matrix)
```

## Usage Patterns

### Class actor with classmethod handler

```python
class Product(Actor):
    __tablename__ = 'products'

    @classmethod
    def SCHEMA(cls, data, tx):
        return {'schema': cls.addr}

# Product auto-registers with matrix at addr='products'
await matrix.inbox(TX(name='SCHEMA', source='client', target='products'))
```

### Instance actor with instance method handler

```python
worker = Actor(addr='worker')
matrix.register(worker)

class TaskWorker(Actor, auto_register=False):
    def PROCESS(self, data, tx):
        return {'result': data['input'] * 2}

w = TaskWorker(addr='task-1')
matrix.register(w)
```

### ActorProxy for non-Actor classes

```python
class LegacyService:
    def HEALTH(self, data, tx):
        return {'status': 'ok'}

proxy = ActorProxy(LegacyService(), addr='health')
matrix.register(proxy)
# matrix routes TX(target='health') to proxy.inbox() -> proxy.handler() -> LegacyService.HEALTH()
```

## Gotchas

- **Auto-registration happens at class definition time**, not instantiation. If no Matrix exists when the class is defined, the class is not registered. The module-level `matrix` created at `n3tx_actors.matrix` import handles this for typical usage.
- **`fullmethod` descriptors must be declared in the class body**, not assigned dynamically. Pydantic's `model_config = ConfigDict(ignored_types=(fullmethod, fullproperty))` prevents them from being treated as model fields.
- **Actor extends `PydanticBaseModel`**, so instances have Pydantic's `__setattr__` protection. Use `object.__setattr__()` to monkey-patch methods in tests. See `mock_method()` context manager in `tests/conftest.py`.
- **`spawn()` raises `ValueError` if the addr already exists** in the parent's children dict. Check with `has()` first if unsure.
- **Matrix blocks self-send** (target == own addr) silently with a log error. This prevents routing loops.
- **Instance `_parent` defaults to `self.__class__`**, mirroring the JS pattern. This means unregistered instances bubble messages to their class, which then routes to Matrix.
