# PyBend Actor System

A message-passing actor framework built on Pydantic, designed for
transparent class/instance dispatch. Define a class, get an actor.
Define an instance, get the same actor. One API, no dual paths.

---

## Table of Contents

1. [Core Idea](#core-idea)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [TX — Message Envelope](#tx--message-envelope)
5. [Actor — Unified Dispatch](#actor--unified-dispatch)
6. [Matrix — Root Router](#matrix--root-router)
7. [ActorProxy — Wrapper for Anything](#actorproxy--wrapper-for-anything)
8. [Descriptors](#descriptors)
9. [Message Flow](#message-flow)
10. [File Layout](#file-layout)
11. [Testing](#testing)

---

## Core Idea

Most actor systems force you to choose: work with classes or work
with instances. PyBend's actor system doesn't. Every operation —
`inbox`, `handler`, `send`, `register`, `addr`, `children` — works
identically on both:

```python
Product.addr             # 'products'
product.addr             # 'products/1'

Product.children         # class-level children dict
product.children         # instance-level children dict

Product.register(child)  # into class children
product.register(child)  # into instance children

await Product.inbox(tx)  # dispatches via class
await product.inbox(tx)  # dispatches via instance
```

Two descriptors (`actormethod` and `actorproperty`) make this
possible. The method implementation is written once. The descriptor
resolves whether `target` is the class or the instance. No
`if/else`, no `_cls` suffix, no wrapper layer.

---

## Quick Start

```python
from pybend.core.actors import Actor, Matrix, TX

# 1. Create the root router
m = Matrix()

# 2. Define an actor class (auto-registers with Matrix)
class Product(Actor):
    __tablename__ = 'products'

    @classmethod
    def SCHEMA(cls, data, tx):
        return {'name': cls.addr, 'fields': ['name', 'price']}

# 3. Send a message
tx = TX(name='SCHEMA', source='client', target='products')
await m.inbox(tx)
# -> Product.SCHEMA is called, reply routes back through Matrix
```

Instance actors work the same way:

```python
class Worker(Actor, auto_register=False):
    name: str = Field(default='')

    def PROCESS(self, data, tx):
        return {'processed_by': self.name, 'item': data.get('item')}

w = Worker(name='Alpha', addr='worker-1')
m.register(w)

tx = TX(name='PROCESS', source='client', target='worker-1', data={'item': 42})
await m.inbox(tx)
# -> w.PROCESS is called, reply routes back through Matrix
```

---

## Architecture

```
TX              Immutable message envelope (name, source, target, data, meta)
  |
Actor           Base class — unified dispatch via actormethod/actorproperty
  |             Extends PydanticBaseModel. Works as both class and instance.
  |
Matrix          Root actor — message router, adapter registry
  |             Routes by first segment of target address.
  |
ActorProxy      Lightweight wrapper — gives any object the actor interface
                Slots-based, no Pydantic overhead. Isomorphic external API.
```

The system is deliberately minimal. Four files, no threads, no
queues, no event loop management. Messages route through parent
chains synchronously (async/await, not background tasks). The
framework owns the plumbing; you own the handlers.

---

## TX -- Message Envelope

A dataclass with six fields:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Message type (`SCHEMA`, `CREATE`, `PING`, ...) |
| `source` | `str` | Sender address |
| `target` | `str` | Recipient address (slash-delimited path) |
| `data` | `dict` | Payload |
| `meta` | `dict` | Metadata (timestamps, correlation IDs, error flags) |
| `uuid` | `str` | Auto-generated unique ID |

### Reply and Error

```python
# Reply swaps source/target, generates new uuid, stores original in meta
reply = tx.reply(data={'count': 42})
reply.name     # 'SCHEMA_RESPONSE'
reply.source   # original target
reply.target   # original source

# Error creates an ERROR message
err = tx.error("Not found", code=404)
err.name       # 'ERROR'
err.is_error   # True
err.data       # {'message': 'Not found', 'code': 404}
```

TX is intentionally a plain dataclass — no Pydantic, no validation
overhead. It's a wire format, not a domain object.

---

## Actor -- Unified Dispatch

### State

Actors carry state at two levels:

| Level | Address | Children | Parent |
|-------|---------|----------|--------|
| Class | `__addr__` (ClassVar) | `__children__` (ClassVar) | `__matrix__` (ClassVar) |
| Instance | `_addr` (PrivateAttr) | `_children` (PrivateAttr) | `_parent` (PrivateAttr) |

The descriptors (`actorproperty`) resolve which level to read:

```python
Product.addr      # reads __addr__       -> 'products'
product.addr      # reads _addr          -> 'products/1'

Product.parent    # reads __matrix__     -> Matrix instance
product.parent    # reads _parent        -> parent actor/class
```

### Handler Dispatch

When a message arrives at `handler()`, it dispatches to a method
matching `tx.name`:

```python
class Product(Actor):
    __tablename__ = 'products'

    @classmethod
    def SCHEMA(cls, data, tx):     # Class-level: Matrix routes here
        return cls.schema()

    def DUMP(self, data, tx):      # Instance-level: parent routes here
        return self.model_dump()
```

The handler automatically wraps return values:
- `dict` -> `tx.reply(data=result)`
- `TX` -> passed through as-is
- `None` -> `tx.reply()` (empty response)
- Other -> `tx.reply(data={'result': value})`
- Exception -> `tx.error(str(e))`

### Send Routing

`send()` adapts to context:

**Class-level** (three-case routing):
1. Direct child match — first segment of target matches a child
2. Prefixed target — target starts with class addr, strip and route
3. Bubble to root — prefix source with class addr, send to Matrix

**Instance-level** (parent chain):
1. If parent is a class -> `parent.send(tx)` (enters class routing)
2. If parent is an instance -> `parent.inbox(tx)`
3. No parent, no root -> `RuntimeError`

### Child Management

```python
# Register — works on classes and instances
Product.register(child)      # adds to Product.__children__
product.register(child)      # adds to product._children, sets child._parent

# Spawn — create + register in one call
worker = product.spawn('w1', Worker, name='Alpha')

# Check existence
product.has('w1')            # True
product.has('w1/subtask')    # True (checks first segment)
```

### Auto-Registration

When a class is defined with `auto_register=True` (the default),
it auto-registers with the current root Matrix:

```python
m = Matrix()                 # becomes root

class Product(Actor):        # auto-registers as m._children['Product']
    __tablename__ = 'products'  # addr = 'products'
```

Skip registration with `auto_register=False`:

```python
class Worker(Actor, auto_register=False):
    pass
```

### Pydantic Compatibility

Actor extends `PydanticBaseModel`. Instance state uses `PrivateAttr`
to stay out of `model_dump()`:

```python
class Item(Actor, auto_register=False):
    name: str = Field(default='')
    price: float = Field(default=0.0)

item = Item(name='Widget', price=9.99, addr='item/1')
item.model_dump()   # {'name': 'Widget', 'price': 9.99}
                    # No addr, _children, _parent leaked
```

---

## Matrix -- Root Router

Matrix is the top-level actor. It receives all messages that bubble
up from children and routes them back down (or out to adapters).

### Routing Logic

```python
await m.inbox(tx)
```

1. **Self-send guard** — if `tx.target == m.addr`, log error and return
2. **Local child** — if first segment of target matches a child, route there
3. **Adapter** — iterate registered adapters; first `can_handle()` gets it
4. **No route** — log warning

### Adapters

Adapters extend routing beyond the local actor tree:

```python
class WebSocketAdapter:
    def can_handle(self, tx):
        return tx.target.startswith('ws/')

    async def send(self, tx):
        await self.ws.send_json(tx.data)

m.register_adapter(WebSocketAdapter())
```

### Module-Level Instance

A default Matrix is created at import time:

```python
from pybend.core.actors.matrix import matrix

# `matrix` is a ready-to-use Matrix instance
matrix.register(my_actor)
```

---

## ActorProxy -- Wrapper for Anything

ActorProxy gives any Python object the actor interface without
requiring inheritance:

```python
from pybend.core.actors.actor_proxy import ActorProxy

class Calculator:
    def ADD(self, data, tx):
        return {'sum': data['a'] + data['b']}

proxy = ActorProxy(Calculator(), addr='calc')
m.register(proxy)

await m.inbox(TX(name='ADD', source='client', target='calc',
                  data={'a': 3, 'b': 4}))
# -> Calculator.ADD called, reply sent back
```

### When to Use

- Wrapping third-party classes that can't extend Actor
- Wrapping plain objects that don't need Pydantic
- Building trees from heterogeneous components

### Address Resolution

ActorProxy resolves `addr` from multiple sources (in priority order):
1. Explicit `addr=` kwarg
2. Target's `__addr__` attribute
3. Target's `__tablename__` attribute
4. Target's `.addr` property (for instances)
5. Target's class name

### ActorLike Protocol

Both `Actor` and `ActorProxy` satisfy the `ActorLike` runtime
protocol:

```python
from pybend.core.actors.actor_proxy import ActorLike

isinstance(Actor(addr='a'), ActorLike)       # True
isinstance(ActorProxy("x", addr='p'), ActorLike)  # True
```

---

## Descriptors

The two descriptors that make unified dispatch work:

### actormethod

A non-data descriptor that binds `target = cls or self`:

```python
@actormethod
async def inbox(target, tx):
    await target.handler(tx)
```

- `Product.inbox` -> `MethodType(fn, Product)` -> `target = Product`
- `product.inbox` -> `MethodType(fn, product)` -> `target = product`

One function, one implementation. No class/instance split.

### actorproperty

Same idea but returns a value directly (not a callable):

```python
@actorproperty
def children(target):
    if isinstance(target, type):
        return target.__children__
    return target._children
```

- `Product.children` -> `fn(Product)` -> `Product.__children__`
- `product.children` -> `fn(product)` -> `product._children`

### IDE Support

Under `TYPE_CHECKING`, both descriptors are transparent identity
functions. IDEs see the original function signatures — proper
autocomplete, type hints, go-to-definition all work.

---

## Message Flow

### Class Actor (Matrix -> Class)

```
Client sends TX(name='SCHEMA', target='products')
    |
    v
Matrix.inbox(tx)
    |  target_root = 'products'
    |  found in _children -> Product (class)
    v
Product.inbox(tx)           # actormethod: target = Product
    |
    v
Product.handler(tx)         # actormethod: target = Product
    |  getattr(Product, 'SCHEMA') -> bound classmethod
    |  result = Product.SCHEMA(data, tx)
    v
Product.send(reply_tx)      # actormethod: target = Product
    |  class routing: no child match -> bubble to Matrix
    v
Matrix.inbox(reply_tx)      # reply arrives at root for delivery
```

### Instance Actor (Matrix -> Parent -> Instance)

```
Client sends TX(name='DUMP', target='products/1')
    |
    v
Matrix.inbox(tx)
    |  target_root = 'products'
    |  found in _children -> Product (class)
    v
Product.inbox(tx)           # strips 'products/' prefix
    |  remaining target = '1'
    |  found in __children__ -> product instance
    v
product.inbox(tx)           # actormethod: target = product
    |
    v
product.handler(tx)         # dispatches to product.DUMP(data, tx)
    |
    v
product.send(reply_tx)      # instance routing: parent = Product (class)
    v
Product.send(reply_tx)      # class routing: bubble to Matrix
    v
Matrix.inbox(reply_tx)
```

---

## File Layout

```
actors/
    __init__.py          Public API: TX, Actor, Matrix, matrix
    actor.py             Actor class, ActorMeta, actormethod, actorproperty
    actor_proxy.py       ActorProxy wrapper, ActorLike Protocol
    matrix.py            Matrix root actor, adapter registry
    tx.py                TX message envelope (dataclass)
    legacy/
        actor_legacy.py  Previous __init_subclass__ implementation (reference)
    tests/
        conftest.py      Fixtures: reset_actor_state, mock_method, make_tx
        test_tx.py       TX creation, reply, error, is_error
        test_actor.py    Unified dispatch, routing, child management
        test_matrix.py   Root routing, adapters, self-send guard
        test_actor_proxy.py   Proxy dispatch, address resolution, ActorLike
        test_integration.py   E2E routing, class/instance coexistence
```

---

## Testing

```bash
# Run actor tests
cd src/pybend/core && python3 -m pytest actors/tests/ -v

# Run all framework unit tests (includes actor tests from tests/unit/)
cd src/pybend/core && python3 -m pytest tests/unit/ -q
```

### Test Coverage

| Module | Tests | Covers |
|--------|-------|--------|
| `test_tx.py` | 27 | Creation, reply, error, `is_error`, edge cases |
| `test_actor.py` | 62 | Descriptors, init, meta, routing, handler, send, register, spawn |
| `test_matrix.py` | 19 | Init, `has()`, inbox routing, adapters, module-level instance |
| `test_actor_proxy.py` | 22 | Address resolution, dispatch, inbox routing, `ActorLike` |
| `test_integration.py` | 8 | E2E routing, class+instance coexistence, Pydantic compat |

### Pydantic Mock Patching

Pydantic's `__setattr__` prevents standard mock patching on Actor
instances. Use `object.__setattr__` directly or the `mock_method`
context manager from `conftest.py`:

```python
from pybend.core.actors.tests.conftest import mock_method

async def capture(tx):
    captured.append(tx)

with mock_method(actor_instance, 'inbox', capture):
    await actor_instance.inbox(tx)
```

---

## License

MIT
