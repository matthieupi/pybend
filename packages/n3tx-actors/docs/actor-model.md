# ActorModel and Two-Tier Auth

> Part of [n3tx-actors](../README.md)

## What This Covers

The `ActorModel` bridge class that makes models into actors: CRUD message handling via `handler_crud()`, custom method dispatch with `@expose_route`, streaming async generators, lifecycle event publishing, and the two-tier authorization flow. Does not cover the base Actor messaging system (see [actor-messaging.md](actor-messaging.md)).

## Architecture

```
TX arrives at ActorModel.handler(target, tx)
    |
    v
handler_crud(tx)  -- checks if tx.name in {schema, create, get, list, update, delete}
    |
    +-- CRUD match: adapt TX to StorableMixin calls
    |     schema  -> cls.schema()
    |     create  -> Tier 2 auth -> cls(**data) -> cls.create(instance)
    |     get     -> cls.get(id) -> Tier 2 auth (with resource) -> model_response()
    |     list    -> cls.list(sql_filter=meta['sql_filter']) -> serialize
    |     update  -> cls.get(id) -> Tier 2 auth -> cls.update(id, data)
    |     delete  -> cls.get(id) -> Tier 2 auth -> cls.delete(id)
    |     lifecycle events published after create/update/delete
    |
    +-- NOT_HANDLED: fall through to generic dispatch
          getattr(target, tx.name) -> method
          |
          +-- has __endpoint__ (@expose_route):
          |     Tier 2 auth check on method-level access
          |     resolve 'self' from data['id'] if instance method
          |     inject 'user' from tx.meta if declared
          |     call method(**kwargs)
          |     if async generator -> stream chunks via tx.chunk()/tx.end()
          |
          +-- no __endpoint__: original (data, tx) signature
```

### Two-Tier Authorization

```
Tier 1: auth_interceptor on NetworkAdapter.request()
    - Runs BEFORE TX enters actor system
    - schema: always pass
    - list: compute sql_filter (WHERE clause for OWNER rules)
    - create: full rule check (no resource needed)
    - read/update/delete: identity gate (has user_id?)
    - custom methods: check @expose_route access= param

Tier 2: ActorModel._authorize() inside handler_crud()
    - Runs AFTER resource instance is fetched from storage
    - Evaluates __access__ rules WITH resource context
    - Enables OWNER checks (user_owner == current user)
    - Internal messages (no meta.user) pass unchecked
```

Both tiers are required for correct authorization. Tier 1 is fast rejection at the boundary. Tier 2 handles resource-dependent rules that Tier 1 cannot evaluate.

## Interface

### ActorModel

```python
class ActorModel(Actor, ProtoModel):
    # MRO: YourModel -> ActorModel -> Actor -> ProtoModel -> PydanticBaseModel

    @fullmethod
    async def handler(target, tx: TX) -> None: ...  # CRUD adapter + generic fallback

    @classmethod
    def handler_crud(cls, tx: TX): ...  # returns result or _NOT_HANDLED sentinel

    @classmethod
    def _authorize(cls, action, tx, resource=None): ...  # Tier 2 auth guard

    @classmethod
    def _publish_lifecycle(cls, event, data): ...  # fire-and-forget to subscribers
```

### handler_crud TX-to-StorableMixin mapping

| TX name | StorableMixin call | Auth |
|---------|--------------------|------|
| `schema` | `cls.schema()` | None |
| `create` | `cls.create(cls(**data))` | Tier 2 create |
| `get` | `cls.get(id)` | Tier 2 read (with resource) |
| `list` | `cls.list(sql_filter=...)` | Tier 1 sql_filter |
| `update` | `cls.update(id, data)` | Tier 2 update (with resource) |
| `delete` | `cls.delete(id)` | Tier 2 delete (with resource) |

### Lifecycle Events

After successful create/update/delete, `_publish_lifecycle(event, data)` fires TX to subscriber addresses:

```python
TX(name='LIFECYCLE', source=cls.__addr__, target=subscriber_addr,
   data={'event': 'after_create', 'entity': result.model_response()})
```

Subscribers are future consumers (federation, agents, audit, WebSocket broadcast). Registered via `cls._subscribers.append('ws')`.

## Usage Patterns

### Basic ActorModel

```python
from n3tx_actors.models.actor_model import ActorModel
from pydantic import Field

class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED, 'update': OWNER, 'delete': ROLE('admin')}
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
```

One import change from `ProtoModel`. CRUD messages handled automatically. Auto-registered with Matrix at `addr='products'`.

### Streaming custom method

```python
@expose_route('/generate', methods=['POST'], stream=True, access=AUTHENTICATED)
async def generate(self):
    for i in range(5):
        await asyncio.sleep(0.1)
        yield {'chunk': f'Part {i}'}
```

The handler detects async generators, sends `tx.chunk()` for each yielded value, then `tx.end()` when the generator completes.

### Lifecycle subscriber wiring

```python
ws = NetworkWebSocket()
matrix.register(ws)
Product._subscribers.append('ws')  # lifecycle events broadcast to WS clients
```

## Gotchas

- **`handler_crud` is a `@classmethod`, not a `@fullmethod`.** It always operates on the class, even when the handler is invoked on an instance. CRUD operations are always class-level (create, get, list, etc.).
- **`_NOT_HANDLED` sentinel distinguishes "not CRUD" from "CRUD returned None".** The handler checks `result is not _NOT_HANDLED`, not truthiness. Do not return `None` from custom code paths that should indicate "not handled".
- **Custom `@expose_route` methods on ActorModel use kwargs dispatch**, not `(data, tx)`. The handler unpacks `tx.data` as keyword arguments, resolves `self` from `data['id']`, and injects `user` from `tx.meta`. This differs from plain Actor handler methods which receive `(data, tx)`.
- **Streaming error handling**: if an async generator raises mid-stream, the handler catches the exception and sends `tx.exception(e)`. The client receives the error as a stream event, not a clean stream-end.
- **`_authorize` returns `None` for internal messages** (no `tx.meta['user']`). This means actor-to-actor messages bypass auth. If you route external input without setting `meta.user`, it will pass Tier 2 unchecked.
- **Lifecycle `_publish_lifecycle` uses `asyncio.create_task`** -- fire-and-forget. Failures in subscriber delivery are not propagated back to the CRUD operation.
