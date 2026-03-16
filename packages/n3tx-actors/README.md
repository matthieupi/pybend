# 🎭 n3tx-actors

> Your models don't just sit there — they talk, route, and respond. Actor-based messaging, routing, and protocol adapters for the N3TX framework.

## 🌐 Overview

n3tx-actors gives your models a voice. It's the Actor/Matrix/TX messaging system that powers Level 3 routing in N3TX — where models become routable actors, external protocols (HTTP, WebSocket, MCP, ActivityPub) bridge into the actor tree through NetworkAdapters, and interceptors give you composable middleware at any routing point.

Need message-driven CRUD? Lifecycle events? Real-time WebSocket push? Multi-protocol support? This is your package.

## 📦 Installation

```bash
pip install n3tx-actors           # standalone
pip install n3tx[actors]          # via meta-package
pip install -e packages/n3tx-actors  # editable dev install
```

Requires `n3tx-core>=0.10.0` and `pydantic>=2.7,<3.0`.

## 🚀 Quick Start

Here's the whole thing — define a model, wire it up, send a message. Four steps, you're routing.

```python
from n3tx_actors import TX, Actor, Matrix, matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.api.network_api import NetworkAPI, create_api_routes
from n3tx_actors.api.auth_interceptor import auth_interceptor
from pydantic import Field

# 1. Define a model that IS an actor
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)

# 2. Product auto-registers with the module-level matrix at addr='products'
# 3. Wire HTTP adapter with auth
api = NetworkAPI()
matrix.register(api)
api.use(auth_interceptor, on='request')

# 4. Route a message through the actor system
tx = TX(name='schema', source='api', target='products')
response = await api.request(tx)  # returns schema TX
```

That's it. Your model is an actor now. Let's dig into what that means.

## 🧩 Core Concepts

### TX -- Message Envelope

Every message in the system is a TX. Think of it as a little envelope with a `name`, `source`, `target`, `data`, `meta`, `timestamp`, and `uuid`. You send it, the system routes it, and you get a reply back.

Responses use `tx.reply()` (swaps source/target, stores correlation in `meta['req']`). Errors use `tx.error()` (sets `name='ERROR'`, `meta['error']=True`). Streaming uses `tx.chunk()` and `tx.end()`.

```python
tx = TX(name='create', source='api', target='products', data={'name': 'Widget'})
reply = tx.reply(data={'id': 1, 'name': 'Widget'})   # name='create_RESPONSE'
error = tx.error("Not found", code=404)                # name='ERROR', is_error=True
chunk = tx.chunk({'part': 1}, seq=0)                   # name='STREAM', streaming chunk
```

### 🎯 Actor -- Unified Class/Instance Dispatch

Here's where it gets fun. Actors use `fullmethod`/`fullproperty` descriptors so that `Product.inbox(tx)` and `product.inbox(tx)` both work with the same code. No separate class methods vs instance methods — just one unified API. Class-level state lives in `__addr__`, `__children__`, `__interceptors__`; instance-level in `_addr`, `_children`, `_interceptors` (Pydantic PrivateAttr).

```python
Product.addr          # 'products' (from __addr__)
product.addr          # 'products' (from _addr)
Product.register(child)  # into __children__
product.register(child)  # into _children, sets child._parent
await Product.inbox(tx)  # class-level dispatch
await product.inbox(tx)  # instance-level dispatch
```

### 🌳 Matrix -- Root Router

One Matrix per actor tree. It routes TX to local children first, then tries registered NetworkAdapters. Self-send is blocked (no infinite loops on your watch). A module-level `matrix` instance is created at import time so subclass auto-registration always has a root.

### 🔗 ActorModel -- The Bridge Class

This is where the magic lives. `ActorModel(Actor, ProtoModel)` gives your models actor capabilities without changing anything else. CRUD messages (`schema`, `create`, `get`, `list`, `update`, `delete`) are handled by `handler_crud()`. Non-CRUD messages dispatch via `getattr`. Lifecycle events (`after_create`, `after_update`, `after_delete`) are published to subscribers.

One import change. Zero other changes. Your model just became an actor.

### 🛡️ Interceptors -- Composable Middleware

TX interceptors registered via `actor.use(fn, on='inbox')`. They run before the method body. Return an error TX to short-circuit. Class + instance chains combine (class first, FIFO). Targets: `inbox`, `send`, `request`.

```python
api.use(auth_interceptor, on='request')

@actor.use(on='inbox')
async def log_messages(tx: TX) -> TX:
    print(f"Received: {tx.name}")
    return tx
```

Simple, composable, and you can stack as many as you need.

## 📖 API Reference

| Export | Type | Purpose |
|--------|------|---------|
| `TX` | dataclass | Message envelope with reply/error/chunk/end methods |
| `Actor` | class | Base actor with unified class/instance messaging |
| `Matrix` | class | Root actor and message router |
| `matrix` | instance | Module-level default Matrix (created at import) |
| `ActorProxy` | class | Wraps any class/instance as a routable actor without inheritance |

### Subpackage: `n3tx_actors.models`

| Export | Type | Purpose |
|--------|------|---------|
| `ActorModel` | class | Bridge class: `Actor` + `ProtoModel` with CRUD handling |

### Subpackage: `n3tx_actors.api`

| Export | Type | Purpose |
|--------|------|---------|
| `NetworkAdapter` | class | Base class for protocol adapters (request/response bridging) |
| `NetworkAPI` | class | HTTP adapter (FastAPI routes to Matrix) |
| `NetworkWebSocket` | class | WebSocket adapter (persistent connections, lifecycle broadcast) |
| `NetworkMCP` | class | MCP JSON-RPC 2.0 adapter (AI agent tool discovery) |
| `NetworkAP` | class | ActivityPub federation adapter (outbox, inbox, WebFinger) |
| `auth_interceptor` | function | Tier 1 auth gate for NetworkAdapter.request() |
| `create_api_routes()` | function | Generate FastAPI CRUD + custom method routes via actor TX |
| `create_ws_routes()` | function | Generate FastAPI WebSocket endpoint |
| `create_mcp_routes()` | function | Generate FastAPI MCP JSON-RPC endpoint |
| `create_federation_routes()` | function | Generate FastAPI ActivityPub endpoints |

### `TX`

```python
@dataclass
class TX:
    name: str; source: str; target: str
    data: dict = {}; meta: dict = {}
    timestamp: float = ...; uuid: str = ...

    def reply(self, data=None, name=None) -> TX: ...
    def error(self, message: str, code: int = 500) -> TX: ...
    def chunk(self, data, seq: int) -> TX: ...
    def end(self, data=None, seq: int = 0) -> TX: ...
    def exception(self, e: Exception) -> TX: ...
    @property
    def is_error(self) -> bool: ...
```

### `Actor`

```python
class Actor(PydanticBaseModel, metaclass=ActorMeta):
    addr: fullproperty       # class __addr__ or instance _addr
    children: fullproperty   # class __children__ or instance _children
    parent: fullproperty     # class __matrix__ or instance _parent

    async def inbox(target, tx: TX) -> None: ...   # fullmethod
    async def handler(target, tx: TX) -> None: ...  # fullmethod
    async def send(target, tx: TX) -> None: ...     # fullmethod
    def register(target, child) -> Actor: ...        # fullmethod
    def spawn(target, addr, actor_cls, ...) -> Actor: ...  # fullmethod
    def has(target, addr: str) -> bool: ...          # fullmethod
    def use(target, interceptor=None, *, on='inbox'): ...  # fullmethod
    @classmethod
    def root(cls, actor=None): ...  # get/set Matrix
```

### `NetworkAdapter`

```python
class NetworkAdapter(Actor, auto_register=False):
    async def inbox(self, tx: TX) -> None: ...          # correlation check + fallback
    async def request(self, tx: TX, timeout=30.0) -> TX: ...  # send + await reply
    async def stream(self, tx: TX, timeout=120.0): ...  # send + yield chunks
```

## 💡 Patterns and Conventions

A few things that'll save you a headache:

1. **Always initialize a Matrix before defining Actor subclasses.** `ActorMeta` auto-registers subclasses with the root Matrix. Without one, classes silently skip registration. The module-level `matrix` handles this for typical usage, but if you're creating an isolated tree, construct Matrix first.

2. **Use `auto_register=False` for abstract or adapter classes.** Any class that shouldn't appear in the Matrix routing table needs `auto_register=False` in its class definition. All NetworkAdapter subclasses do this already.

3. **Pydantic mock patching requires `object.__setattr__`.** Pydantic's `__setattr__`/`__delattr__` prevent normal mock patching on Actor instances. You'll want the `mock_method()` context manager pattern:
   ```python
   object.__setattr__(instance, 'inbox', mock_fn)
   ```

4. **Two-tier auth for Level 3 routing.** Tier 1 (`auth_interceptor` on `request`) gates at the protocol boundary -- fast reject, sql_filter computation. Tier 2 (`ActorModel._authorize` in `handler_crud`) checks resource-level OWNER rules after fetching the entity. Both tiers are required for correct authorization.

5. **Error/response TX silently dropped by handler.** When `handler()` receives a TX with `is_error=True` or name ending in `_RESPONSE` and has no matching method, it drops silently instead of sending an error reply. This prevents infinite bounce loops between actors. It's intentional, not a bug.

## 🏗️ Package Ecosystem

Here's how everything fits together:

```
n3tx-core          <-- n3tx-actors depends on this
  (models, storage,     (actor system, network adapters,
   schema, auth)         ActorModel bridge, interceptors)
       |                       |
       +-------+-------+------+
               |
          n3tx-agents   <-- depends on n3tx-actors
          (AgentMixin, tool discovery, LLM integration)
```

n3tx-actors extends n3tx-core with messaging. It imports `ProtoModel`, `StorableMixin`, `fullmethod`/`fullproperty` descriptors, and `authorize` from n3tx-core. It does not depend on n3tx-agents.

## 📚 Deep Dives

Want to go deeper? Each of these docs covers a specific area in detail:

| Topic | File | When to read |
|-------|------|--------------|
| Actor Messaging and Routing | [docs/actor-messaging.md](docs/actor-messaging.md) | Understanding message flow, routing rules, handler dispatch |
| Interceptor Pattern | [docs/interceptors.md](docs/interceptors.md) | Adding middleware, auth gates, TX transformation |
| Network Adapters | [docs/network-adapters.md](docs/network-adapters.md) | HTTP, WebSocket, MCP, ActivityPub protocol bridging |
| ActorModel and Two-Tier Auth | [docs/actor-model.md](docs/actor-model.md) | CRUD handling, lifecycle events, authorization flow |

---

Happy routing! Your models have a lot to say. 🎭
