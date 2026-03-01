# 0d ActorModel — Design Review

> Models that are actors. The bridge class.

**Date**: 2026-03-01
**Status**: Implemented
**Prereqs**: 0a (schema pipeline), 0b (Actor/Matrix/TX), 0c (schema extension protocol)

## Implementation Summary

**Files changed:**
- `src/pybend/core/models/base_user.py` — renamed `register()` → `register_user()` (route stays `/register`)
- `src/pybend/core/models/actor_model.py` — NEW: `ActorModel(Actor, ProtoModel)` bridge class
- `src/pybend/core/models/__init__.py` — export ActorModel
- `src/pybend/example/tests/test_user_model.py` — updated `User.register` → `User.register_user` refs
- `src/pybend/example/tests/test_schema_endpoints.py` — updated schema method name check

**Decisions resolved:**
- MI approach: confirmed working. MRO: `Product → ActorModel → Actor → ProtoModel → BaseModel`
- BaseUser.register renamed (not Actor.register) — Actor keeps `register()`
- handler_crud() is a classmethod adapter: translates TX → StorableMixin signatures
- handler() is @actormethod: tries handler_crud first, falls back to generic getattr dispatch
- ActorModel lives in `models/` not `actors/` — keeps actors package independent
- ProtoModel stays standalone — ActorModel is additive
- model_dump TX types deferred to 0e

**Tests:** 647 unit + 386 integration — zero regression

---

## The Central Question: MI vs ActorProxy

The roadmap proposed `class ActorModel(Actor, ProtoModel)` with MI. The actual Actor
implementation (0b) evolved into a descriptor-based system (`actormethod`/`actorproperty`)
with `ActorMeta` metaclass rather than simple MI. We need to verify this still composes.

### MI Viability

```
         PydanticBaseModel
          /            \
       Actor         ProtoModel
       (ActorMeta)   (ModelMetaclass)
          \            /
          ActorModel
              |
           Product
```

**Why MI works:**

1. **Metaclass compatible** — `ActorMeta` extends `_PydanticMeta = type(PydanticBaseModel)`.
   When Python resolves the metaclass for `ActorModel(Actor, ProtoModel)`, `ActorMeta` is
   the most derived and satisfies both bases.

2. **`__init__` chains correctly** — Actor.__init__ pops `addr` from kwargs, calls
   `super().__init__()` which chains to ProtoModel.__init__, which handles storable
   retrieval, then chains to PydanticBaseModel.__init__ for field validation.

3. **`__init_subclass__` and `ActorMeta.__new__` are orthogonal** —
   ProtoModel.__init_subclass__ injects StorableMixin for `__storable__=True` classes.
   ActorMeta.__new__ sets up `__children__`, `__addr__`, and auto-registers with Matrix.
   These don't interfere.

4. **PrivateAttr coexists** — Actor defines `_addr`, `_children`, `_parent` as PrivateAttr.
   ProtoModel has no PrivateAttr. Pydantic's `__pydantic_private__` dict merges all
   PrivateAttr from across the MRO.

### vs ActorProxy

ActorProxy wraps any target as a routable actor without inheritance changes.

| Dimension | MI (ActorModel) | ActorProxy |
|-----------|-----------------|------------|
| Developer change | `ProtoModel` → `ActorModel` | None |
| Models are actors | Yes — inbox/handler/send on class | No — wrapped by proxy |
| Auto-registration | Via ActorMeta.__new__ | Manual: `matrix.register(ActorProxy(Product))` |
| Indirection | None | Proxy → getattr → target |
| MI risk | Config merging, name collisions | None |
| Architectural vision | Matches roadmap: "actors all the way down" | Pragmatic but weaker |

**Decision: MI is the right call.** It's cleaner, matches the vision, and the technical
risks are addressable. But we verify with a minimal test before building out.

---

## Issue #1: `register()` Name Collision — BLOCKER

**The problem:**

- `Actor.register(target, child)` — actormethod for registering child actors (`actor.py:318`)
- `BaseUser.register(cls, name, email, password)` — `@expose_route('/register')` for user
  registration (`base_user.py:112`)

When `User(BaseUser)` inherits from BaseUser which inherits from ActorModel, the MRO
makes `Actor.register` (an `actormethod` descriptor) shadow `BaseUser.register` (a
classmethod with `@expose_route`). The user registration endpoint breaks.

**Fix:** Rename `Actor.register()` → `Actor.register_child()`. Update all call sites:
- `actor.py` — definition + internal calls
- `matrix.py` — if any
- `actor_proxy.py` — its own `register()` method (rename for consistency)
- All tests referencing `.register()`

This is a prerequisite before ActorModel can be created. The rename is mechanical —
search-and-replace with test verification.

---

## Issue #2: All CRUD Handlers Must Be Classmethods

**The problem:**

The roadmap shows `UPDATE` and `DELETE` as instance methods:
```python
def UPDATE(self, data, tx): ...
def DELETE(self, data, tx): ...
```

But in the backend, the **class** is the actor registered with Matrix, not instances.
When Matrix receives `TX(target='products')`, it calls `Product.inbox(tx)` on the CLASS.
There's no long-lived `Product(id=42)` instance sitting in memory — entities are retrieved
from storage on demand, used, then discarded.

**Fix:** All CRUD handlers are classmethods. Entity IDs come via `tx.data`:

```python
@classmethod
def CREATE(cls, data, tx):
    instance = cls(**data)
    result = cls.create(instance)
    cls._publish_lifecycle('after_create', result.model_dump(response=True))
    return result.model_dump(response=True)

@classmethod
def READ(cls, data, tx):
    entity_id = data.get('id')
    if entity_id:
        result = cls.get(entity_id)
        if not result:
            return tx.error(f"{cls.__name__} {entity_id} not found", code=404)
        return result.model_dump(response=True)
    else:
        limit = data.get('limit', 20)
        offset = data.get('offset', 0)
        return cls.list(limit=limit, offset=offset)

@classmethod
def SCHEMA(cls, data, tx):
    return cls.schema()

@classmethod
def UPDATE(cls, data, tx):
    entity_id = data.get('id')
    result = cls.update(entity_id, data)
    if result:
        cls._publish_lifecycle('after_update', result.model_dump(response=True))
    return result.model_dump(response=True)

@classmethod
def DELETE(cls, data, tx):
    entity_id = data.get('id')
    cls.delete(entity_id)
    cls._publish_lifecycle('after_delete', {'id': entity_id})
    return {'deleted': entity_id}
```

Instance-targeted messaging (`products/42/favorite`) deferred to Wave 2 (RouteActor).

---

## Issue #3: model_config Merging

**The problem:**

Actor has:
```python
model_config = ConfigDict(ignored_types=(actormethod, actorproperty))
```

ProtoModel has:
```python
class Config:
    arbitrary_types_allowed = True
    extra = 'allow'
```

Pydantic V2 merges configs from bases, but the mix of old-style `class Config` and
new-style `model_config = ConfigDict(...)` may not merge cleanly.

**Fix:** Explicit merged config on ActorModel:

```python
class ActorModel(Actor, ProtoModel):
    model_config = ConfigDict(
        ignored_types=(actormethod, actorproperty),
        arbitrary_types_allowed=True,
        extra='allow',
    )
```

This overrides both parent configs with the union of their settings.

---

## Issue #4: Custom Method Dispatch (Wave 0 Scope)

**The roadmap says:** "Routes stay unchanged in Wave 0."

Custom methods like `favorite()`, `comment()` still go through FastAPI route handlers
directly — NOT through the actor system. `routes_fastapi.py` retrieves instances and
calls methods as it does today.

**In Wave 0, ActorModel handles these message types only:**

| Message | Handler | Delegates To |
|---------|---------|-------------|
| `SCHEMA` | `cls.SCHEMA(data, tx)` | `ProtoModel.schema()` via pipeline |
| `CREATE` | `cls.CREATE(data, tx)` | `StorableMixin.create()` |
| `READ` | `cls.READ(data, tx)` | `StorableMixin.get()` or `.list()` |
| `UPDATE` | `cls.UPDATE(data, tx)` | `StorableMixin.update()` |
| `DELETE` | `cls.DELETE(data, tx)` | `StorableMixin.delete()` |

Plus lifecycle event publishing after CUD operations.

Custom method dispatch via actor messaging is a Wave 2 concern (RouteActor retrieves
instance, calls method, wraps response in TX).

---

## Issue #5: Registration Timing

**The situation:**

`ActorMeta.__new__` auto-registers classes with the root Matrix at class definition time:

```python
# ActorMeta.__new__
root = getattr(cls, '__matrix__', None)
if auto_register and root and name != 'Actor':
    root._children[cls.__addr__] = cls
```

`register_model()` in `registrar.py` runs later at app startup:

```python
def register_model(model_cls, storage):
    model_cls.set_storage(storage)
    model_cls.create_table()
    registered_models[model_cls.__tablename__] = model_cls
```

**Potential issues:**

1. Auto-registration happens before storage is set — the model is in the Matrix but
   can't handle CRUD messages yet (no storage backend). This is fine as long as no TX
   messages are sent before `register_model()` completes.

2. `register_model()` should verify the model is already in the Matrix (from
   auto-registration) rather than re-registering. Or: auto-registration handles Matrix,
   `register_model()` handles storage — clean separation.

**Decision:** Keep both. ActorMeta auto-registers with Matrix (routing). `register_model()`
sets storage (persistence). They're complementary. Add a guard in `register_model()` to
skip Matrix registration if already present.

---

## Lifecycle Events

Lifecycle events are TX messages published to subscribers after CUD operations.
This is "free" in the actor system — just send a TX.

```python
class ActorModel(Actor, ProtoModel):
    _subscribers: ClassVar[list[str]] = []

    @classmethod
    def _publish_lifecycle(cls, event: str, data: dict):
        """Publish lifecycle event to all subscribers. Fire-and-forget."""
        for subscriber_addr in cls._subscribers:
            asyncio.create_task(cls.send(TX(
                name='LIFECYCLE',
                source=cls.__addr__,
                target=subscriber_addr,
                data={'event': event, 'entity': data},
            )))
```

**Subscribers are future consumers:**
- Federation: OutboxActor queues AP Create activity
- Agents: MonitorActor triggers analysis
- Audit: AuditActor logs event
- Real-time: WebSocketBridge pushes to frontend

In Wave 0, `_subscribers` is empty — the infrastructure exists but no consumers yet.

---

## Developer Experience

**Before (v0.7.0):**
```python
from pybend.core.models.proto_model import ProtoModel

class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> str: ...
```

**After (v0.8.0):**
```python
from pybend.core.actors import ActorModel  # ← changed import

class Product(ActorModel):                 # ← changed base class
    __tablename__ = 'products'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> str: ...
```

One import change, one base class change, zero other changes. Product is now an actor
that can receive TX messages, participate in the Matrix, and publish lifecycle events —
all while keeping the exact same CRUD, schema, and route behavior.

---

## Implementation Order

1. **Rename `Actor.register()` → `Actor.register_child()`** — prereq, mechanical
2. **Create `ActorModel` class** — MI bridge with merged config
3. **Add CRUD classmethods** — SCHEMA, CREATE, READ, UPDATE, DELETE
4. **Add lifecycle publishing** — `_publish_lifecycle()` with empty subscribers
5. **Verify MI** — minimal test: `class TestModel(ActorModel)` with storable
6. **Update example models** — Product, Comment, Like → ActorModel base
7. **Update BaseUser** — extend ActorModel instead of ProtoModel
8. **Run ALL existing tests** — zero regression tolerance
9. **Write ActorModel-specific tests** — CRUD via handler, lifecycle events, error cases

---

## Open Questions

1. **Should ProtoModel continue to work standalone?** Or do we migrate everything to
   ActorModel? The roadmap implies ActorModel replaces ProtoModel for user-facing models,
   but ProtoModel stays as the data-only base. Join models inherit from their parent
   (which is now ActorModel), so they get actor behavior for free.

2. **Should `model_dump(response=True)` become TX message types now (0e)?** Or keep
   the boolean flag in Wave 0 and convert in 0e as a separate step? Recommend: separate
   step (0e) to keep 0d focused.

3. **Auto-register vs explicit register?** ActorMeta auto-registers at class definition.
   But models defined before the Matrix exists won't be registered. Is import order a
   concern? The default `matrix = Matrix()` in `matrix.py` creates the root at import
   time, so as long as `actors` is imported before models, it works.
