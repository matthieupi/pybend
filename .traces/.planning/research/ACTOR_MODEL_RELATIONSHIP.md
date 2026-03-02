# Research: Actor-Model Relationship in PyBend

**Domain:** Schema-driven framework: Actor messaging system + Pydantic data model integration
**Researched:** 2026-02-26
**Overall Confidence:** HIGH (existing codebase analysis) / MEDIUM (external patterns)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Context: What We Already Have](#2-context-what-we-already-have)
3. [The Six Approaches](#3-the-six-approaches)
   - [Approach 1: Direct Multiple Inheritance](#approach-1-direct-multiple-inheritance)
   - [Approach 2: Mixin Injection via __init_subclass__](#approach-2-mixin-injection-via-__init_subclass__)
   - [Approach 3: Composition (ModelActor wraps ProtoModel)](#approach-3-composition-modelactor-wraps-protomodel)
   - [Approach 4: Protocol/Structural Typing](#approach-4-protocolstructural-typing)
   - [Approach 5: Class Decorator (Actor.subclass pattern)](#approach-5-class-decorator-actorsubclass-pattern)
   - [Approach 6: Descriptor-Based Actor Proxy](#approach-6-descriptor-based-actor-proxy)
4. [Comparison Matrix](#4-comparison-matrix)
5. [External Precedents](#5-external-precedents)
6. [Category Theory Analysis](#6-category-theory-analysis)
7. [Pydantic Compatibility Deep Dive](#7-pydantic-compatibility-deep-dive)
8. [Recommendation](#8-recommendation)
9. [Implementation Sketch](#9-implementation-sketch)
10. [Sources](#10-sources)

---

## 1. Executive Summary

After analyzing the existing PyBend codebase (both the JS frontend Actor/Matrix/TX system and the Python backend ProtoModel/StorableMixin system), researching Pydantic's metaclass constraints, and studying external actor frameworks (Akka, Erlang/OTP, Orleans, Dapr, Proto.Actor, Ray, Thespian), I recommend **Approach 5: Class Decorator (the Python equivalent of `Actor.subclass()`)** as the primary architecture, with **Approach 2 (Mixin Injection)** as a complementary mechanism for opt-in enrichment.

The core insight: **Actor and Model are orthogonal concerns that should be composable, not fused.** A model describes data shape and validation. An actor describes messaging behavior and lifecycle. The JS codebase already solved this correctly with `Actor.subclass(DynamicClass, Observable)` -- it does not make DynamicClass inherit from Actor. It hot-patches actor capabilities onto an existing class. The Python port should follow the same pattern, adapted for Python's stronger type system.

The critical constraint is Pydantic's `ModelMetaclass`. It controls `__init__` generation, field resolution, validation, and serialization. Any approach that fights this metaclass will break. The safest approaches are those that add behavior *around* the Pydantic model without touching its core metaclass machinery.

**Key findings:**
- Direct multiple inheritance (Approach 1) will break due to Pydantic's `ModelMetaclass` `__slots__` conflicts and MRO issues. **Do not attempt.**
- Mixin injection (Approach 2) already works in PyBend for StorableMixin. It can work for ActorMixin too, but has the same `__init_subclass__` timing limitations already navigated.
- Composition (Approach 3) is the cleanest from a category theory perspective but creates indirection that violates PyBend's "transparent, not magical" principle.
- Protocol typing (Approach 4) is elegant but provides no implementation -- just a contract.
- **Class decorator / `Actor.subclass()` equivalent (Approach 5) is the clear winner.** It mirrors the existing JS pattern, avoids metaclass conflicts, works with `__pydantic_init_subclass__`, and preserves the "model is the app" philosophy.
- Descriptor-based proxy (Approach 6) is a novel approach worth noting but over-engineered for this use case.

---

## 2. Context: What We Already Have

### Frontend Actor System (JavaScript)

The JS codebase implements a sophisticated dual-level actor system:

**Type-level actors** (static): Each class (e.g., `Product`) acts as an actor with:
- `static addr` -- class name as address
- `static children` -- Map of instances
- `static send()` / `static inbox()` -- class-level message routing
- `static register()` -- register instances in the class's children map

**Instance-level actors**: Each entity (e.g., `Product/1`) acts as an actor with:
- `this.addr` -- entity ID
- `this.children` -- Map of child actors
- `this.send()` / `this.inbox()` -- instance-level message routing

**The key mechanism**: `Actor.subclass(ChildClass, ...Mixins)` hot-patches actor capabilities onto any class. It:
1. Defines static `addr`, `children`, `send`, `inbox`, `register` on the class
2. Defines instance-level `send`, `inbox`, `children` on the prototype
3. Applies mixins via `Mixin.apply(Type)` (e.g., Observable)
4. Marks the class with `__TypeActor = true`

This is **not** inheritance. It is behavior injection via monkey-patching. The `DynamicClass` created by `prototype()` extends `NTT` (which extends `TT` which extends `Actor`), but this inheritance is for the *entity instances*. The class-level actor behavior is separately injected via `Actor.subclass()`.

### Backend Model System (Python)

The Python backend already uses a similar pattern:

**ProtoModel.__init_subclass__** performs behavior injection:
```python
def __init_subclass__(cls, **kwargs):
    __storable__ = getattr(cls, '__storable__', False)
    if __storable__:
        if not issubclass(cls, StorableMixin):
            cls.__bases__ = (StorableMixin,) + cls.__bases__
```

This injects `StorableMixin` into the class's bases at class creation time, giving it `create()`, `get()`, `list()`, `update()`, `delete()` without explicit inheritance.

**Proven pattern**: The `cls.__bases__` injection trick already works in production with Pydantic V2. This is the precedent to follow.

### TX Message Envelope

The JS `TX` is: `{name, source, target, data, meta, tst, hash}`. The Python equivalent should be a Pydantic model itself:

```python
class TX(BaseModel):
    name: str
    source: str
    target: str
    data: Any = {}
    meta: dict = {}
    tst: float = Field(default_factory=time.time)
    hash: Optional[str] = None
```

---

## 3. The Six Approaches

### Approach 1: Direct Multiple Inheritance

```python
class Actor:
    addr: str
    children: dict
    def inbox(self, tx): ...
    def send(self, tx): ...

class Product(ProtoModel, Actor):
    __tablename__ = 'products'
    name: str
    price: float
```

#### Pydantic Compatibility: BROKEN

**Confidence: HIGH** (verified via multiple Pydantic GitHub issues)

Pydantic V2 uses `ModelMetaclass` which controls:
- `__init__` generation (replaces any custom `__init__`)
- `__slots__` creation for private attributes
- Field resolution via `model_fields`
- Validation schema compilation via `pydantic-core`

Multiple inheritance from `BaseModel` + non-trivial class with its own `__init__`, `__slots__`, or descriptors causes:

1. **`__slots__` conflict**: If `Actor` uses `__slots__` for `addr`, `children`, etc., Python raises `TypeError: multiple bases have instance lay-out conflict`. This is a CPython limitation, not a Pydantic one.

2. **`__init__` override**: Pydantic generates `__init__` from field annotations. If `Actor.__init__` sets `self.addr`, this conflicts with Pydantic's generated `__init__`. One stomps the other.

3. **MRO complexity**: `ModelMetaclass` has specific expectations about the class hierarchy. Adding `Actor` to the MRO introduces unpredictable field resolution behavior. Known Pydantic issues #11700, #9992, #2568 document MRO problems with even simple multiple inheritance.

4. **Private attribute conflicts**: If either class uses `PrivateAttr`, the `__slots__` conflict becomes unavoidable.

#### Tradeoffs

| Gain | Lose |
|------|------|
| Clean `isinstance(product, Actor)` checks | Pydantic compatibility |
| Single class definition | Predictable `__init__` behavior |
| Conceptual simplicity | Private attribute support |

#### Unforeseen Advantages
- None that survive the implementation attempt.

#### Unforeseen Disadvantages
- Every Pydantic version upgrade becomes a minefield.
- Error messages from metaclass conflicts are cryptic and hard to debug.
- Cannot use `PrivateAttr` anywhere in the hierarchy.

#### Developer Experience
- Looks clean on paper: `class Product(ProtoModel, Actor)`
- Falls apart the moment you try to instantiate: cryptic metaclass errors.

#### Mental Model Complexity
- Appears simple (just add Actor to bases) but hides impossible-to-resolve conflicts.

#### Extensibility
- Dead end. Cannot extend without fighting the metaclass.

#### Composability
- Cannot opt out of being an actor without changing the class definition.
- Cannot have actors without models (Actor needs its own hierarchy).

#### Integration Hurdles
- `ModelMetaclass.__new__` runs before `Actor.__init_subclass__`, creating ordering dependencies.
- Pydantic's `model_rebuild()` may not account for non-Pydantic bases.

#### Verdict: **REJECT. Do not attempt.**

---

### Approach 2: Mixin Injection via __init_subclass__

```python
class ActorMixin:
    """Non-Pydantic mixin providing actor behavior."""
    _actor_addr: ClassVar[str] = ''
    _actor_children: ClassVar[dict] = {}

    @classmethod
    def actor_send(cls, tx): ...

    @classmethod
    def actor_inbox(cls, tx): ...

    def send(self, tx): ...
    def inbox(self, tx): ...

class ProtoModel(PydanticBaseModel):
    def __init_subclass__(cls, **kwargs):
        __actor__ = getattr(cls, '__actor__', False)
        if __actor__:
            if not issubclass(cls, ActorMixin):
                cls.__bases__ = (ActorMixin,) + cls.__bases__
        super().__init_subclass__(**kwargs)

class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __actor__ = True  # Opt-in
    name: str
    price: float
```

#### Pydantic Compatibility: WORKS (with caveats)

**Confidence: HIGH** (this is exactly how StorableMixin already works in PyBend)

The `cls.__bases__` injection happens during `__init_subclass__`, which runs *after* the metaclass creates the class but *before* the class is fully available. Pydantic's `ModelMetaclass` has already processed fields by this point.

**Critical caveat**: The mixin must NOT define any Pydantic fields (no `Field()` annotations). It can only add methods and ClassVars. This is exactly how `StorableMixin` works -- it adds `create()`, `get()`, `list()`, etc. as classmethods without adding any Pydantic fields.

**Timing issue**: In `__init_subclass__`, `model_fields` is not yet populated. But `__pydantic_init_subclass__` IS called after field resolution. If actor initialization needs field information, use `__pydantic_init_subclass__` instead.

#### Tradeoffs

| Gain | Lose |
|------|------|
| Consistent with existing StorableMixin pattern | `isinstance(x, ActorMixin)` checks work but feel implicit |
| Opt-in via `__actor__ = True` | Mixin cannot define Pydantic fields |
| No metaclass conflicts | Two ClassVars to declare (`__storable__`, `__actor__`) |
| Transparent -- developers can see the bases injection | Mixin methods must not conflict with Pydantic methods |

#### Unforeseen Advantages
- **Already proven in production**: StorableMixin uses this exact pattern. Zero risk of architectural surprises.
- **`issubclass` checks work**: After injection, `issubclass(Product, ActorMixin)` returns `True`.
- **Graceful degradation**: Models without `__actor__ = True` are plain data models. No actor overhead.
- **Works with `register_model()`**: The existing registration flow doesn't need changes.

#### Unforeseen Disadvantages
- **Method name collisions**: If ActorMixin defines `send()` and a model defines a custom method called `send()`, the model's method silently wins (or vice versa depending on MRO). No compile-time warning.
- **Inspection confusion**: `type(product).__bases__` shows `(ActorMixin, StorableMixin, ProtoModel)` which may confuse developers examining the class hierarchy.
- **Double injection ordering**: Both `StorableMixin` and `ActorMixin` are injected via `__init_subclass__`. The order matters: `cls.__bases__ = (ActorMixin, StorableMixin,) + cls.__bases__` vs `cls.__bases__ = (StorableMixin, ActorMixin,) + cls.__bases__`. This affects MRO.
- **Testing complexity**: Mocking actor behavior requires understanding the bases injection timing.

#### Developer Experience
```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __actor__ = True
    name: str
    price: float
```
Clean. One extra ClassVar to enable actor behavior. Consistent with the existing `__storable__` pattern.

#### Mental Model Complexity
- "Set `__actor__ = True` and your model becomes an actor" -- simple.
- But understanding *how* it works requires knowing about bases injection, which is a PyBend-specific pattern.

#### Extensibility
- New actor behaviors = new methods on ActorMixin. Simple.
- But ActorMixin becomes a grab-bag of methods over time.

#### Composability
- Opt-in via ClassVar: models can be actors or not.
- But actors always require a model. Pure actors (without data) need a separate mechanism.

#### Integration Hurdles
- Method naming discipline required (prefix with `actor_` or use a namespace pattern).
- Must coordinate injection order with StorableMixin.

#### Verdict: **VIABLE. Proven pattern. Good fallback.**

---

### Approach 3: Composition (ModelActor wraps ProtoModel)

```python
class ModelActor(Actor):
    """Actor that wraps a ProtoModel class."""
    def __init__(self, model_class: Type[ProtoModel]):
        self.model_class = model_class
        self.addr = model_class.__name__
        self.children = {}

    def inbox(self, tx):
        if tx.name == 'CREATE':
            instance = self.model_class.create(self.model_class(**tx.data))
            return instance
        elif tx.name == 'READ':
            return self.model_class.list()
        # ...

class InstanceActor(Actor):
    """Actor that wraps a ProtoModel instance."""
    def __init__(self, instance: ProtoModel):
        self.instance = instance
        self.addr = str(instance.id)

    def inbox(self, tx):
        if tx.name == 'UPDATE':
            self.instance = self.instance.__class__.update(self.instance.id, tx.data)
            return self.instance
        # ...

# Usage
product_actor = ModelActor(Product)
matrix.register(product_actor)
```

#### Pydantic Compatibility: PERFECT

**Confidence: HIGH**

No inheritance relationship between Actor and ProtoModel at all. They are separate class hierarchies connected by composition. Zero risk of metaclass conflict.

#### Tradeoffs

| Gain | Lose |
|------|------|
| Complete separation of concerns | Two objects per model (actor + model class) |
| No metaclass conflicts ever | Indirection: `product_actor.model_class.create()` |
| Actor can exist without model | Developers must understand actor-model mapping |
| Model can exist without actor | Registration becomes two-step |
| Testable independently | Every model method needs an actor handler |

#### Unforeseen Advantages
- **Clean testability**: Test the model without any actor system. Test the actor without any real model (mock it).
- **Symmetric with JS**: The JS `DynamicClass` is essentially a composition wrapper around schema data + NTT actor behavior.
- **Pluggable actors**: Different model types could have different actor behaviors. A `CachedModelActor` vs `StreamingModelActor` etc.
- **Future-proof**: If PyBend ever needs to support non-Pydantic models (e.g., SQLAlchemy), the actor layer doesn't change.

#### Unforeseen Disadvantages
- **Registration bloat**: Every model needs `register_model()` AND `register_actor()`. The "zero config" promise erodes.
- **Semantic gap**: In the JS system, a `Product` IS both data and actor simultaneously. In composition, `product_actor` and `Product` are different objects. Which one does the developer interact with?
- **State synchronization**: If someone mutates a model instance directly (bypassing the actor), the actor doesn't know. This is the classic "two sources of truth" problem.
- **Violates "model is the app"**: The model is now half the app. The actor is the other half. The mental model splits.
- **Schema exposure**: How does the schema communicate that this model is actor-capable? The actor wrapper is invisible to the schema system.

#### Developer Experience
```python
# Define model (unchanged)
class Product(ProtoModel):
    __tablename__ = 'products'
    name: str
    price: float

# Separately register as actor
product_actor = ModelActor(Product)
matrix.register(product_actor)
```
More explicit but more verbose. Two concepts to learn. Two registrations to remember.

#### Mental Model Complexity
- "A model describes data. An actor provides messaging. ModelActor connects them."
- Three concepts instead of one. Violates "the model is the app."

#### Extensibility
- Excellent. New actor types don't touch models. New model features don't touch actors.

#### Composability
- Best in class. Models and actors are fully independent. Mix and match freely.

#### Integration Hurdles
- `register_routes()` needs to know about actors to route messages.
- Schema generation needs to include actor capabilities (methods become messages).
- The `@expose_route` decorator needs to bridge to actor `inbox()`.

#### Verdict: **VIABLE but creates semantic gap. Best for systems where Actor and Model are genuinely independent concerns. Not ideal for PyBend where "model is the app."**

---

### Approach 4: Protocol/Structural Typing

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ActorProtocol(Protocol):
    addr: str
    children: dict

    def inbox(self, tx: TX) -> Any: ...
    def send(self, tx: TX) -> Any: ...

    @classmethod
    def actor_inbox(cls, tx: TX) -> Any: ...

    @classmethod
    def actor_send(cls, tx: TX) -> Any: ...

# ProtoModel satisfies ActorProtocol if it implements the required methods
class ProtoModel(PydanticBaseModel):
    # ... existing fields ...

    @property
    def addr(self) -> str:
        return str(self.id)

    @property
    def children(self) -> dict:
        return getattr(self, '_children', {})

    def inbox(self, tx: TX) -> Any:
        handler = getattr(self, tx.name, None)
        if handler:
            return handler(tx.data, tx)
        raise ValueError(f"No handler for {tx.name}")

    def send(self, tx: TX) -> Any:
        return self.__class__.actor_send(tx)

# Type checking: Product satisfies ActorProtocol
def route_message(actor: ActorProtocol, tx: TX):
    actor.inbox(tx)
```

#### Pydantic Compatibility: PERFECT (protocol is just a type contract)

**Confidence: HIGH**

Protocols don't affect runtime behavior. They are purely a type-checking mechanism. No metaclass involvement.

**However**: Pydantic issue #7808 documents that `class MyModel(BaseModel, Protocol)` raises `TypeError: metaclass conflict`. The solution is to NOT inherit from Protocol -- instead, use `@runtime_checkable` Protocol as a separate type hint. The model satisfies the protocol structurally, not via inheritance.

#### Tradeoffs

| Gain | Lose |
|------|------|
| Zero metaclass conflict | No implementation sharing -- every model must implement all methods |
| Clean type checking | Boilerplate: each model must define `inbox`, `send`, `addr`, etc. |
| `isinstance` checks work with @runtime_checkable | Protocol violation detected at type-check time, not class definition time |
| No inheritance coupling | No central place to modify actor behavior |

#### Unforeseen Advantages
- **Gradual adoption**: Any existing model can become actor-compatible by adding the right methods. No base class changes needed.
- **IDE support**: Type checkers (mypy, pyright) verify protocol satisfaction at write-time.
- **Documentation-as-code**: The Protocol IS the specification. It documents exactly what an actor needs.

#### Unforeseen Disadvantages
- **No implementation reuse**: Every model that wants to be an actor must implement `inbox()`, `send()`, `addr`, `children` from scratch. There's no "base implementation" to inherit.
- **Drift risk**: Without shared implementation, different models may implement actor methods inconsistently.
- **False confidence**: `isinstance(product, ActorProtocol)` returns `True` if the methods exist, even if they're broken implementations.

#### Developer Experience
```python
class Product(ProtoModel):
    __tablename__ = 'products'
    name: str

    @property
    def addr(self) -> str: return str(self.id)

    @property
    def children(self) -> dict: return {}

    def inbox(self, tx): ...
    def send(self, tx): ...

    @classmethod
    def actor_inbox(cls, tx): ...

    @classmethod
    def actor_send(cls, tx): ...
```
Heavy boilerplate per model. Every model repeats the same actor plumbing.

#### Mental Model Complexity
- "A model that implements these methods is an actor" -- ducktyping is natural in Python.
- But: "Why do I have to write all these methods? Can't the framework do it?"

#### Extensibility
- Adding to the protocol is a breaking change (all implementors must update).

#### Composability
- Perfect opt-in: only models that implement the protocol are actors.
- But the cost of opting in is high (many methods to implement).

#### Verdict: **VIABLE as a type contract layer but insufficient as sole strategy. Best combined with another approach that provides implementation.**

---

### Approach 5: Class Decorator (Actor.subclass() Pattern)

```python
def actorize(cls=None, *, addr=None):
    """
    Python equivalent of JS Actor.subclass().
    Hot-patches actor behavior onto any class without changing its inheritance.
    """
    def decorator(cls):
        # Skip if already actorized
        if getattr(cls, '__actor__', False):
            return cls

        # --- Class-level (type actor) ---
        cls._actor_addr = addr or cls.__name__
        cls._actor_children = {}
        cls._actor_watchers = set()

        @classmethod
        def actor_send(kls, tx):
            """Route message: children first, then bubble to Matrix."""
            # ... routing logic ...
            pass

        @classmethod
        def actor_inbox(kls, tx):
            """Dispatch message to handler method."""
            handler = getattr(kls, tx.name, None)
            if handler:
                return handler(tx.data, tx)
            # Bubble up
            kls.actor_send(tx)

        @classmethod
        def actor_register(kls, actor):
            """Register a child actor."""
            kls._actor_children[actor._actor_addr] = actor

        cls.actor_send = actor_send
        cls.actor_inbox = actor_inbox
        cls.actor_register = actor_register

        # --- Instance-level ---
        original_init = cls.__init__

        # Don't wrap __init__ for Pydantic models -- use __init_subclass__ or post_init
        # Instead, provide instance methods that work with existing instances

        def instance_send(self, tx):
            return self.__class__.actor_send(tx)

        def instance_inbox(self, tx):
            handler = getattr(self, tx.name, None)
            if handler and callable(handler):
                return handler(tx.data, tx)
            return self.__class__.actor_inbox(tx)

        cls.send = instance_send
        cls.inbox = instance_inbox

        # --- Instance addr via property ---
        if not hasattr(cls, 'addr') or isinstance(getattr(cls, 'addr', None), property):
            cls.addr = property(
                lambda self: f"{self.__class__._actor_addr}/{self.id}"
                if hasattr(self, 'id') else self.__class__._actor_addr
            )

        # Mark as actorized
        cls.__actor__ = True

        return cls

    if cls is not None:
        return decorator(cls)
    return decorator

# Usage option A: explicit decorator
@actorize
class Product(ProtoModel):
    __tablename__ = 'products'
    name: str
    price: float

# Usage option B: auto-injection via __init_subclass__
class ProtoModel(PydanticBaseModel):
    def __init_subclass__(cls, **kwargs):
        if getattr(cls, '__actor__', True):  # Default ON
            actorize(cls)
        super().__init_subclass__(**kwargs)
```

#### Pydantic Compatibility: EXCELLENT

**Confidence: HIGH**

The decorator runs AFTER class creation. It does not modify the class's metaclass, `__init__`, or field definitions. It only adds new methods and class attributes. Pydantic's `ModelMetaclass` has already completed its work by the time the decorator runs.

**Key insight**: Unlike `__init_subclass__` which runs during class creation (when Pydantic is still setting up), a decorator runs after the class is fully constructed. This sidesteps all timing issues.

When used via `__init_subclass__`, the decorator still works because it only adds attributes/methods -- it doesn't modify the class's bases or metaclass. The `cls.__bases__` trick used by StorableMixin is NOT needed here.

#### Tradeoffs

| Gain | Lose |
|------|------|
| Mirrors the JS `Actor.subclass()` pattern exactly | Methods are added dynamically (less IDE autocompletion) |
| No metaclass conflict | `isinstance(x, Actor)` doesn't work (no Actor base class) |
| No bases modification needed | Type checkers may not see injected methods |
| Works with any class, not just ProtoModel | Debugging: methods don't appear in class definition |
| Can be combined with Protocol for type safety | |

#### Unforeseen Advantages

1. **Symmetry with JS frontend**: The Python `actorize()` is the exact equivalent of `Actor.subclass()`. Same pattern, same semantics, different language. This makes the codebase conceptually unified across frontend and backend.

2. **Works with `generate_join_model()`**: Join models created via `type(class_name, (ref_model,), fields)` can be actorized after creation: `actorize(join_model)`. No special handling needed.

3. **Can be combined with Protocol**: Define `ActorProtocol` for type checking, use `actorize()` for implementation. The decorator ensures the class satisfies the protocol.

4. **Mixin-compatible**: `Observable` from JS can become a Python mixin applied via the same decorator: `actorize(cls, mixins=[ObservableMixin])`.

5. **Zero-cost opt-out**: `__actor__ = False` on a model class skips the decorator. The model remains a pure data model.

6. **Schema-aware**: The decorator can inspect `model_fields` (which ARE available after class creation) and auto-generate actor handlers for CRUD operations.

7. **Testable**: Mock the decorator or replace injected methods individually. No base class to mock.

8. **Incremental migration**: Can actorize existing models one by one without changing any base class.

#### Unforeseen Disadvantages

1. **IDE type inference**: Injected methods won't appear in autocomplete unless we also provide type stubs or use `if TYPE_CHECKING` patterns. Partial mitigation: combine with Protocol.

2. **Method collision risk**: If a Pydantic model defines a method called `send` or `inbox`, the decorator would silently overwrite it. Need a collision check.

3. **Serialization blindness**: Pydantic's `model_dump()` won't include actor state (`_actor_children`, `_actor_watchers`). This is actually desirable (actor state is runtime, not data) but could confuse developers expecting actors to be serializable.

4. **Debugging stack traces**: When an actor method raises an exception, the traceback shows the injected function, not the class definition. This can be confusing.

5. **Decorator ordering**: If other decorators are applied (e.g., `@dataclass`, `@register`), the order matters. `@actorize` should be outermost (applied last, runs first after class creation).

#### Developer Experience

**Option A -- Explicit decorator:**
```python
@actorize
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str
    price: float

    def LIKE(self, data, tx):
        """Custom actor message handler"""
        # ... handle LIKE message ...
```

**Option B -- Auto (via __init_subclass__, default on):**
```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str
    price: float

    # Automatically an actor. Define handlers as methods:
    def LIKE(self, data, tx):
        """Handles LIKE messages"""
        pass

class RawDataModel(ProtoModel):
    __actor__ = False  # Opt-out
    # Pure data model, no actor behavior
```

**Option B is more consistent with PyBend's philosophy** ("works out of the box, customize additively"). The model IS the app, and being an actor is part of being an app entity.

#### Mental Model Complexity
- "Every model is an actor by default. It can receive messages and handle them via methods."
- "To handle a message named FOO, define a method called FOO on your model."
- This is remarkably simple and consistent with the JS system.

#### Extensibility
- New message types = new handler methods on the model. No framework changes.
- New actor behaviors = extend the decorator (add more injected methods).
- New mixins = `actorize(cls, mixins=[NewMixin])`.

#### Composability
- Models are actors by default, opt-out via `__actor__ = False`.
- Actors without models: use `@actorize` on any class, not just ProtoModel.
- Mix and match: some models are actors, some aren't.

#### Integration Hurdles
- Must decide: are CRUD operations (create/get/list/update/delete) actor messages? If yes, `StorableMixin` methods become message handlers. If no, CRUD stays as direct method calls and only custom methods go through the actor system.
- Must integrate with `register_routes()`: when a model is actorized, should `@expose_route` methods automatically become actor message handlers?
- The Matrix/routing system needs a Python implementation.

#### Verdict: **RECOMMENDED. Best balance of consistency with JS, Pydantic compatibility, and PyBend philosophy.**

---

### Approach 6: Descriptor-Based Actor Proxy

```python
class ActorDescriptor:
    """Descriptor that provides actor behavior as a namespace."""

    def __set_name__(self, owner, name):
        self._name = name
        self._class_proxy = ClassActorProxy(owner)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self._class_proxy  # Class-level: Product.actor.send(tx)
        return InstanceActorProxy(obj)  # Instance-level: product.actor.send(tx)

class ClassActorProxy:
    def __init__(self, cls):
        self.cls = cls
        self.children = {}
        self.watchers = set()

    @property
    def addr(self):
        return self.cls.__name__

    def send(self, tx): ...
    def inbox(self, tx): ...

class InstanceActorProxy:
    def __init__(self, instance):
        self.instance = instance

    @property
    def addr(self):
        return f"{self.instance.__class__.__name__}/{self.instance.id}"

    def send(self, tx): ...
    def inbox(self, tx): ...

class ProtoModel(PydanticBaseModel):
    actor = ActorDescriptor()  # Namespace for actor behavior

    # Usage:
    # Product.actor.send(tx)       -- class-level
    # product.actor.inbox(tx)      -- instance-level
    # product.actor.addr           -- "Product/1"
```

#### Pydantic Compatibility: GOOD (with caveats)

**Confidence: MEDIUM**

Descriptors on Pydantic models work if they don't conflict with field names. Since `actor` is not a Pydantic field (it's a descriptor on the class), it should be fine. However, Pydantic's `model_fields` introspection might be confused by descriptors, and `model_dump()` might try to serialize the descriptor.

**Mitigation**: Mark the descriptor with `__get_pydantic_core_schema__` to tell Pydantic to ignore it, or use `model_config = ConfigDict(arbitrary_types_allowed=True)`.

#### Tradeoffs

| Gain | Lose |
|------|------|
| Clean namespace separation (`model.actor.send()` vs `model.send()`) | Extra indirection |
| No method collision risk | `product.actor.send(tx)` is more verbose than `product.send(tx)` |
| Actor behavior is encapsulated in proxy | Pydantic may try to serialize the descriptor |
| Self-documenting API | Two objects per interaction (instance + proxy) |

#### Unforeseen Advantages
- **Zero collision risk**: Actor methods live in a separate namespace. No risk of `send()` conflicting with a model method called `send`.
- **Clean separation**: `product.name` is data. `product.actor.send()` is messaging. Crystal clear.
- **Introspectable**: `Product.actor` returns the class proxy with all actor state visible.

#### Unforeseen Disadvantages
- **Breaks "model is the app"**: The model delegates to a proxy for messaging. The model itself isn't the actor -- it has an actor.
- **Performance overhead**: Every `.actor` access creates a new proxy object (unless cached).
- **Not how the JS system works**: The JS system makes the class itself the actor. This creates an asymmetry.
- **Pydantic serialization gotcha**: Must explicitly exclude `actor` from serialization.

#### Verdict: **INTERESTING but over-engineered. The namespace separation is a solution to a problem (method collision) better solved by naming conventions.**

---

## 4. Comparison Matrix

| Criterion | 1: Inheritance | 2: Mixin | 3: Composition | 4: Protocol | 5: Decorator | 6: Descriptor |
|-----------|---------------|---------|----------------|------------|-------------|--------------|
| **Pydantic compat** | BROKEN | WORKS | PERFECT | PERFECT | EXCELLENT | GOOD |
| **MRO safety** | FAILS | OK (careful) | N/A | N/A | N/A | N/A |
| **JS symmetry** | Low | Medium | Medium | Low | HIGH | Low |
| **"Model is the app"** | Attempts | Good | Broken | OK | BEST | Broken |
| **Zero-config** | N/A | Good | Poor | Poor | BEST | Medium |
| **Opt-in/out** | No | Yes | Yes | Yes | Yes | Yes |
| **IDE support** | Good | Good | Good | Best | Medium* | Good |
| **Testability** | Poor | Good | Best | Good | Good | Good |
| **Method collision** | High risk | Medium risk | None | None | Medium risk | None |
| **Extensibility** | Dead end | Good | Best | Good | Good | Good |
| **DX simplicity** | Looks simple | Simple | Verbose | Verbose | SIMPLEST | Verbose |
| **Implementation cost** | N/A | Low | High | Low | Medium | Medium |
| **Mental model** | 1 concept (broken) | 2 concepts | 3 concepts | 2 concepts | 1 concept | 2 concepts |

\* IDE support for Approach 5 can be improved to "Good" by combining with Protocol type stubs.

---

## 5. External Precedents

### Akka (JVM/Scala) -- Inheritance Model

**Pattern**: `AbstractActor` or `AbstractBehavior[T]` base class. Actor state is managed by returning new behaviors (functional) or mutable fields.

**Relationship to data models**: Akka actors typically *contain* data models, not *are* data models. The `Behavior[T]` pattern parameterizes actors by message type `T`, which is often a sealed trait (protocol/union type). Entity state is a separate concept managed within the actor.

**Akka Persistence Typed**: Defines Commands, Events, and State as separate types. The actor processes Commands, emits Events, and derives State. This is a composition pattern -- the actor wraps the state model.

**Lesson for PyBend**: Akka's separation of message types (Commands) from state (State) from behavior (EventHandler) is clean but verbose. PyBend's philosophy ("zero to working") suggests collapsing these into the model itself. An Akka-style separation would be Approach 3. **Confidence: HIGH** (well-documented in Akka docs).

### Erlang/OTP (GenServer) -- Behavior Callback Pattern

**Pattern**: GenServer is a *behavior* -- a generic process framework. You implement callbacks (`handle_call`, `handle_cast`, `init`, `terminate`) in a *callback module*. The behavior provides the process lifecycle; the module provides the specific logic.

**Relationship to data models**: GenServer state is an arbitrary Erlang term (often a record or map). The state is passed to every callback as an argument and returned (potentially modified) from every callback. There is no ORM or data model system -- the state IS the model, implicitly.

**Lesson for PyBend**: The GenServer pattern is essentially "a process that manages state via callbacks." The model IS the state, and the process IS the actor. This maps closest to Approach 5, where the model class IS the actor and message handlers ARE methods on the model. **Confidence: HIGH** (fundamental Erlang/OTP pattern).

### Microsoft Orleans (Virtual Actors / Grains)

**Pattern**: A Grain (virtual actor) is an interface + implementation class. The grain encapsulates state + behavior. Grains are "always exist virtually" -- they're automatically instantiated when messaged and reclaimed when idle.

**Key insight -- grain identity**: A grain has an identity (typically a string or GUID). When you send a message to grain "Product/42", Orleans instantiates or locates the grain, loads its state, processes the message, and optionally persists the state. The grain IS the entity.

**Relationship to data models**: Grain state is typically a POCO (Plain Old CLR Object) -- a simple data class. The grain holds a reference to its state object. State persistence is handled by the runtime via `GrainStorage`. This is a composition pattern (grain wraps state), but with the crucial detail that **the grain identity maps to the entity identity**.

**The "virtual" insight**: Grains always exist. You never "create" or "destroy" them -- you just send messages to them. If the grain isn't in memory, Orleans activates it. This is extremely relevant to PyBend where entities "always exist" in the database.

**Lesson for PyBend**: Orleans validates the idea that "entity identity = actor identity." `Product/42` is both a database entity and an actor address. This is exactly what PyBend's JS system does (`NTT` instances have `addr` = entity ID and `href` = API URL). The Python port should maintain this identity fusion. **Confidence: HIGH** (Orleans is well-documented by Microsoft).

### Dapr (Sidecar Actor Pattern)

**Pattern**: Actor definitions inherit from `Actor` base class. State management uses a separate `ActorStateManager` with `set_state()` / `get_state()` methods. A Pydantic class is used for the state data structure.

**Relationship to data models**: The actor and the data model are separate classes. The actor holds the state manager, the state manager holds the data. This is classic composition (Approach 3).

**Lesson for PyBend**: Dapr's separation makes sense for distributed systems where actor state must be explicitly persisted to a state store. PyBend already has `StorableMixin` for persistence, so the actor doesn't need its own state management -- it delegates to the model's existing CRUD methods. **Confidence: MEDIUM** (Dapr Python SDK documentation is limited).

### Ray (Decorator Actor Pattern)

**Pattern**: `@ray.remote` decorator turns any Python class into a remote actor. The decorator wraps the class, giving it `.remote()` invocation, `.options()` configuration, and automatic distribution across workers.

**Relationship to data models**: Ray actors ARE the class. The decorator doesn't change the class's behavior -- it adds remote invocation capabilities. The class's methods become remotely callable. State is the class's instance variables.

**This is Approach 5.** Ray uses a decorator to inject actor capabilities onto any class. The class itself doesn't change. It just gains new capabilities.

**Lesson for PyBend**: Ray validates the decorator approach. `@ray.remote` is essentially `@actorize`. The key difference: Ray actors are distributed across processes; PyBend actors are local (for now) with potential for distribution via WebSocket/Matrix. **Confidence: HIGH** (Ray is production-proven at massive scale).

### Proto.Actor (Unified Actor Framework)

**Pattern**: Proto.Actor unifies classical Erlang-style actors with Orleans-style virtual actors (grains) under one framework. Supports Go, C#, Java/Kotlin, and Python (limited).

**Python support**: Proto.Actor's Python SDK (`protoactor-python`) exists but is limited and not well-maintained. It uses a message-handling approach similar to Thespian.

**Lesson for PyBend**: Proto.Actor's unification of classical and virtual actors is conceptually relevant. PyBend models are like virtual actors (always exist as database entities), while WebSocket connections are like classical actors (created/destroyed dynamically). The Python port should support both patterns. **Confidence: MEDIUM** (Python SDK is limited).

### Entity Component System (ECS) Pattern

**Pattern**: Entities are IDs. Components are data. Systems process entities with matching components. Pure composition -- no inheritance.

**Relationship to this problem**: ECS separates identity (entity), data (component), and behavior (system) into three independent concepts. In PyBend terms: the entity ID is the actor address, the model fields are the components, and the actor message handlers are the systems.

**Lesson for PyBend**: ECS validates extreme composition. But ECS is designed for game engines with millions of entities and tight performance loops. PyBend has hundreds-to-thousands of entities with rich behavior. ECS would be over-decomposed for this use case. However, the ECS insight -- that behavior and data should be independently composable -- supports Approach 5 (behavior injected, data defined by model). **Confidence: MEDIUM** (conceptual parallel, not direct precedent).

---

## 6. Category Theory Analysis

Analyzing the relationship between Actor and Model through category theory provides insights into which approach has the cleanest mathematical structure.

### The Two Categories

**Cat_Model**: The category of Pydantic models.
- Objects: Model classes (Product, User, Comment, ...)
- Morphisms: Model relationships (ForeignKey, ListRef, inheritance)
- Identity: Each model's identity morphism is its schema

**Cat_Actor**: The category of Actors.
- Objects: Actor instances (Product/1, User/3, Matrix, ...)
- Morphisms: Messages (TX envelopes routed between actors)
- Identity: Each actor's identity morphism is a self-addressed noop message

### The Functor Question

The question "what is the relationship between Actor and Model?" becomes: **what functor connects Cat_Model and Cat_Actor?**

#### Approach 1 (Inheritance): Product (Identity Functor Attempt)

Tries to make Cat_Model = Cat_Actor. This is the identity functor -- claiming the categories are the same. But they're NOT the same (models have validation/serialization, actors have messaging/routing). The identity functor doesn't exist here.

#### Approach 3 (Composition): Functor F: Cat_Model -> Cat_Actor

A functor `ModelActor(-)` maps:
- Each model M to an actor F(M) = ModelActor(M)
- Each model relationship to an actor message route

This is a proper functor. It preserves composition: if Product -> Comment (FK), then ModelActor(Product) -> ModelActor(Comment) (message route).

The inverse functor G: Cat_Actor -> Cat_Model maps each actor back to its wrapped model.

**F and G form an adjunction** (but not an equivalence): `F(G(A))` gives you a ModelActor wrapping the model extracted from actor A, which is isomorphic to A but not identical. This is the "round trip" problem of composition.

#### Approach 5 (Decorator): Natural Transformation eta: Id -> Actor(-)

The decorator `actorize(-)` is a **natural transformation** from the identity functor on Cat_Model to the "actorized model" functor. It transforms each model M into an actorized version of itself, preserving all model structure while adding actor structure.

This is the cleanest mathematical structure because:
1. The transformation is **natural** -- it commutes with model morphisms. If Product -> Comment (FK), then actorize(Product) -> actorize(Comment) preserves the relationship.
2. It is **idempotent** -- actorize(actorize(M)) = actorize(M).
3. It preserves **limits** (inheritance hierarchies) and **colimits** (join models).
4. The original model is a **retract** of the actorized model -- you can always "forget" the actor structure and get the model back.

#### Approach 2 (Mixin): Coproduct / Pushout

Mixin injection computes the **coproduct** (disjoint union) of ActorMixin and Model in the category of Python classes. The `__bases__` manipulation is literally computing a pushout over the common base (object).

This works but is less clean than the natural transformation because the coproduct changes the object itself (new bases), rather than enriching it.

### Verdict from Category Theory

**Approach 5 (Decorator/Natural Transformation) has the cleanest mathematical structure.** It enriches objects without changing their identity, preserves all existing structure, and commutes with all existing morphisms. This is the mathematical formalization of "add behavior without breaking anything."

---

## 7. Pydantic Compatibility Deep Dive

### ModelMetaclass Internals (Pydantic V2)

**Confidence: HIGH** (verified against Pydantic source and GitHub discussions)

Pydantic V2's `ModelMetaclass.__new__` performs these operations during class creation:

1. Collects field annotations from the class and its bases
2. Resolves forward references
3. Generates `__init__` signature from fields
4. Creates `__pydantic_core_schema__` for validation
5. Sets up `__private_attributes__` and `__slots__`
6. Calls `__init_subclass__` on parent classes
7. Calls `__pydantic_init_subclass__` (Pydantic-specific hook)

**Key timing facts:**

| Hook | Fields available? | Bases modifiable? | Safe for actor injection? |
|------|-------------------|-------------------|---------------------------|
| `__init_subclass__` | NO (`model_fields` empty) | YES (cls.__bases__) | YES for methods, NO for fields |
| `__pydantic_init_subclass__` | YES | Risky | YES for methods |
| Class decorator | YES | YES (but after metaclass) | YES for everything |
| `__init_subclass__` + `__bases__` mod | Methods only | YES (proven by StorableMixin) | YES for methods |

### Safe Operations on Pydantic Models

These are SAFE to do after class creation (via decorator or `__init_subclass__`):

- Add classmethods: `cls.actor_send = classmethod(fn)`
- Add instance methods: `cls.inbox = fn`
- Add class attributes: `cls._actor_children = {}`
- Add properties: `cls.addr = property(fn)`
- Add ClassVars (non-field): `cls.__actor__ = True`

These are UNSAFE:

- Modify `__init__`: Pydantic regenerates it; your changes will be lost
- Add fields: `model_fields` is already sealed
- Modify `__slots__`: CPython doesn't allow post-creation `__slots__` modification
- Add `PrivateAttr` instances: These rely on `__slots__` created at class definition time
- Change metaclass: `type(cls)` is fixed after creation

### The `__pydantic_init_subclass__` Hook

Discovered during research: Pydantic V2 provides `__pydantic_init_subclass__`, which is called AFTER `model_fields` is populated. This is the correct hook for actor initialization that needs field information.

```python
class ProtoModel(PydanticBaseModel):
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        # model_fields is available here!
        if getattr(cls, '__actor__', True):
            actorize(cls)
```

**Confidence: MEDIUM** (documented in Pydantic V2, verified via GitHub discussion #7177, but not extensively tested with bases modification).

---

## 8. Recommendation

### Primary: Approach 5 (Decorator / actorize()) with auto-injection via __pydantic_init_subclass__

**Architecture:**

```
Model Definition (Python)
    |
    v
ProtoModel.__pydantic_init_subclass__()
    |
    +-- StorableMixin injection (if __storable__)  [existing]
    +-- actorize() decorator (if __actor__ != False) [new]
    |       |
    |       +-- Injects: actor_send, actor_inbox, actor_register (class-level)
    |       +-- Injects: send, inbox, addr (instance-level)
    |       +-- Injects: _actor_children, _actor_watchers (state)
    |       +-- Registers with Matrix
    |
    v
Fully enriched model: data + storage + actor
```

**Why this approach:**

1. **Mirrors the JS system exactly**: `Actor.subclass(DynamicClass)` in JS = `actorize(Product)` in Python.
2. **Proven Pydantic compatibility**: Methods-only injection is safe. No metaclass conflicts.
3. **Consistent with existing pattern**: StorableMixin injection via `__init_subclass__` is the same concept.
4. **"Model is the app" preserved**: The model IS the actor. One class, one concept.
5. **Zero-config by default**: Models are actors automatically. `__actor__ = False` to opt out.
6. **Cleanest mathematical structure**: Natural transformation on the model category.
7. **Testable**: Mock `actorize` or individual injected methods.
8. **Extensible**: New behaviors via mixins parameter: `actorize(cls, mixins=[Observable])`.

### Secondary: ActorProtocol for Type Safety

Combine the decorator with a Protocol for IDE support:

```python
@runtime_checkable
class ActorProtocol(Protocol):
    _actor_addr: str
    _actor_children: dict

    def send(self, tx: TX) -> Any: ...
    def inbox(self, tx: TX) -> Any: ...

    @classmethod
    def actor_send(cls, tx: TX) -> Any: ...

    @classmethod
    def actor_inbox(cls, tx: TX) -> Any: ...

# After actorize(), Product satisfies ActorProtocol
assert isinstance(Product, ActorProtocol)  # Works with @runtime_checkable
```

### Tertiary: Composition for Non-Model Actors

Some actors are not models (e.g., Matrix, Router, WebSocket handler). For these, use a standalone `Actor` base class:

```python
class Actor:
    """Base class for non-model actors."""
    def __init__(self, addr: str):
        self._actor_addr = addr
        self._actor_children = {}

    def inbox(self, tx): ...
    def send(self, tx): ...

class Matrix(Actor):
    """Root actor / message router."""
    def __init__(self):
        super().__init__("matrix://root")
        self.remote = NetworkAdapter(self)

    def inbox(self, tx):
        # Route to children or remote
        ...
```

This gives us the full spectrum:
- **Model actors**: ProtoModel subclasses auto-actorized via decorator
- **Non-model actors**: Actor subclasses for infrastructure (Matrix, Router, WebSocket)
- **Non-actor models**: ProtoModel subclasses with `__actor__ = False` for pure data

---

## 9. Implementation Sketch

### Phase 1: Core Actor Infrastructure

```python
# src/pybend/core/actor/tx.py
class TX(BaseModel):
    """Message envelope -- Python equivalent of JS TX."""
    name: str
    source: str = ''
    target: str = ''
    data: Any = {}
    meta: dict = Field(default_factory=dict)
    tst: float = Field(default_factory=time.time)
    hash: Optional[str] = None

# src/pybend/core/actor/actor.py
class Actor:
    """Base class for non-model actors (Matrix, Router, etc.)."""
    _actor_addr: str
    _actor_children: dict
    _actor_watchers: set

    def __init__(self, addr: str):
        self._actor_addr = addr
        self._actor_children = {}
        self._actor_watchers = set()

    @property
    def addr(self): return self._actor_addr

    def inbox(self, tx: TX) -> Any: ...
    def send(self, tx: TX) -> Any: ...
    def register(self, child): ...
    def spawn(self, addr, cls, *args): ...

# src/pybend/core/actor/matrix.py
class Matrix(Actor):
    """Root actor -- routes messages between actors."""
    _instance = None

    def __init__(self):
        super().__init__("matrix://root")
        Matrix._instance = self

    def inbox(self, tx: TX):
        target_addr = tx.target.split('/')[0]
        if target_addr in self._actor_children:
            return self._actor_children[target_addr].inbox(tx)
        # Remote routing...

    @classmethod
    def get(cls) -> 'Matrix':
        if not cls._instance:
            cls._instance = Matrix()
        return cls._instance

# src/pybend/core/actor/actorize.py
def actorize(cls=None, *, addr=None, mixins=None):
    """Inject actor behavior onto any class. Python equivalent of Actor.subclass()."""
    def decorator(cls):
        if getattr(cls, '__actor__', False) is True:
            return cls  # Already actorized

        # Class-level actor state
        cls._actor_addr = addr or getattr(cls, '__name__', str(id(cls)))
        cls._actor_children = {}
        cls._actor_watchers = set()

        # Class-level methods
        if not hasattr(cls, 'actor_send') or cls.actor_send is None:
            @classmethod
            def actor_send(kls, tx):
                matrix = Matrix.get()
                if isinstance(tx, dict):
                    tx = TX(**tx)
                return matrix.inbox(tx)
            cls.actor_send = actor_send

        if not hasattr(cls, 'actor_inbox') or cls.actor_inbox is None:
            @classmethod
            def actor_inbox(kls, tx):
                if isinstance(tx, dict):
                    tx = TX(**tx)
                handler = getattr(kls, tx.name, None)
                if handler and callable(handler):
                    return handler(tx.data, tx)
                # Bubble to matrix
                kls.actor_send(tx)
            cls.actor_inbox = actor_inbox

        # Instance-level methods
        def instance_inbox(self, tx):
            if isinstance(tx, dict):
                tx = TX(**tx)
            handler = getattr(self, tx.name, None)
            if handler and callable(handler):
                return handler(tx.data, tx)
            return self.__class__.actor_inbox(tx)
        cls.inbox = instance_inbox

        def instance_send(self, tx):
            return self.__class__.actor_send(tx)
        cls.send = instance_send

        # Instance addr property
        if 'addr' not in cls.__dict__:
            cls.addr = property(
                lambda self: f"{self.__class__._actor_addr}/{self.id}"
                if hasattr(self, 'id') else self.__class__._actor_addr
            )

        # Apply mixins
        if mixins:
            for mixin in mixins:
                if hasattr(mixin, 'apply'):
                    mixin.apply(cls)

        # Register with Matrix
        matrix = Matrix.get()
        matrix.register_type(cls)

        cls.__actor__ = True
        return cls

    if cls is not None:
        return decorator(cls)
    return decorator
```

### Phase 2: Integration with ProtoModel

```python
# In proto_model.py, add to __init_subclass__ or __pydantic_init_subclass__:
class ProtoModel(PydanticBaseModel):
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        # Auto-actorize unless opted out
        if getattr(cls, '__actor__', None) is not False:
            from pybend.core.actor.actorize import actorize
            actorize(cls)
```

### Phase 3: Message Routing Integration

```python
# In routes_fastapi.py or a new websocket handler:
# Actor messages from frontend TX are routed to model actor_inbox
# CRUD operations can optionally go through actor messaging

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        tx = TX(**data)
        matrix = Matrix.get()
        result = matrix.inbox(tx)
        await websocket.send_json(result)
```

---

## 10. Sources

### Pydantic Multiple Inheritance Issues

- [Pydantic #11700: Private attributes in multiple inheritance doesn't respect MRO](https://github.com/pydantic/pydantic/issues/11700) -- HIGH confidence
- [Pydantic #9992: Model config in inheritance doesn't respect MRO](https://github.com/pydantic/pydantic/issues/9992) -- HIGH confidence
- [Pydantic #7808: BaseModel + Protocol metaclass conflict](https://github.com/pydantic/pydantic/issues/7808) -- HIGH confidence
- [Pydantic #5974: Conventions for multiple inheritance](https://github.com/pydantic/pydantic/discussions/5974) -- HIGH confidence
- [Pydantic #7177: __init_subclass__ and model_fields in v2](https://github.com/pydantic/pydantic/discussions/7177) -- HIGH confidence
- [Pydantic #1590: Mixing pydantic model with existing classes](https://github.com/samuelcolvin/pydantic/issues/1590) -- HIGH confidence
- [Pydantic #10100: Fix mro of generic subclass](https://github.com/pydantic/pydantic/pull/10100) -- MEDIUM confidence

### Actor Framework Precedents

- [Microsoft Orleans Overview](https://learn.microsoft.com/en-us/dotnet/orleans/overview) -- HIGH confidence
- [Orleans Grain Model (DeepWiki)](https://deepwiki.com/dotnet/orleans/3-grain-model) -- MEDIUM confidence
- [Akka Typed Actors Introduction](https://doc.akka.io/docs/akka/current/typed/actors.html) -- HIGH confidence
- [Akka Typed: Stateful and Stateless (Rock the JVM)](https://rockthejvm.com/articles/akka-typed-actors-stateful-and-stateless) -- MEDIUM confidence
- [Lagom: Domain Modelling with Akka Persistence Typed](https://www.lagomframework.com/documentation/1.6.x/scala/UsingAkkaPersistenceTyped.html) -- HIGH confidence
- [Erlang GenServer documentation](https://www.erlang.org/doc/apps/stdlib/gen_server.html) -- HIGH confidence
- [Proto.Actor Documentation](https://proto.actor/) -- MEDIUM confidence
- [Proto.Actor Python SDK (GitHub)](https://github.com/asynkron/protoactor-python) -- LOW confidence (limited maintenance)

### Python Actor Frameworks

- [Thespian Python Actor Library (GitHub)](https://github.com/thespianpy/Thespian) -- MEDIUM confidence
- [Dapr Actors in Python (dev.to)](https://dev.to/aaronblondeau/distributed-actors-in-python-with-dapr-4856) -- MEDIUM confidence
- [Dapr Python Actor SDK](https://docs.dapr.io/developing-applications/sdks/python/python-actor/) -- MEDIUM confidence
- [Ray Actors documentation](https://docs.ray.io/en/latest/ray-core/actors.html) -- HIGH confidence
- [Actor Model - Abilian Innovation Lab](https://lab.abilian.com/Tech/Python/Useful%20Libraries/Actor%20Model/) -- LOW confidence

### Architecture Patterns

- [Introduction to Software Architecture with Actors](https://github.com/denyspoltorak/metapatterns/blob/main/IntroductionToSoftwareArchitectureWithActors/Part1/README.md) -- MEDIUM confidence
- [Composition over Inheritance (Wikipedia)](https://en.wikipedia.org/wiki/Composition_over_inheritance) -- HIGH confidence
- [Entity Component System (Wikipedia)](https://en.wikipedia.org/wiki/Entity_component_system) -- HIGH confidence
- [Python Descriptor Guide (docs.python.org)](https://docs.python.org/3/howto/descriptor.html) -- HIGH confidence

### Category Theory

- [Adjoint Functors (Wikipedia)](https://en.wikipedia.org/wiki/Adjoint_functors) -- HIGH confidence (mathematical theory)
- [What is an Adjunction? (math3ma)](https://www.math3ma.com/blog/what-is-an-adjunction-part-1) -- MEDIUM confidence

---

## Appendix A: Decision Tree for Implementors

```
Does the class need both data fields AND messaging?
    |
    YES --> Is it a ProtoModel subclass?
    |           |
    |           YES --> Use actorize() (auto via __pydantic_init_subclass__)
    |           |       Define message handlers as methods: def LIKE(self, data, tx)
    |           |
    |           NO --> Does it need Pydantic validation?
    |                   |
    |                   YES --> Subclass ProtoModel (gets actorized automatically)
    |                   NO  --> Subclass Actor directly
    |
    NO --> Is it a pure data model?
    |           |
    |           YES --> ProtoModel with __actor__ = False
    |
    NO --> Is it a pure infrastructure actor (Matrix, Router)?
                |
                YES --> Subclass Actor directly
```

## Appendix B: Message Handler Convention

Following the JS system's convention, message handlers are methods whose name matches the TX.name field:

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    name: str
    price: float

    # CRUD handlers (auto-generated if __storable__)
    # READ, CREATE, UPDATE, DELETE are handled by StorableMixin

    # Custom handlers
    def LIKE(self, data, tx):
        """Handle LIKE message for this product instance."""
        # data = message payload
        # tx = full TX envelope
        return {"liked": True}

    @classmethod
    def SEARCH(cls, data, tx):
        """Handle SEARCH message at the class level."""
        query = data.get('query', '')
        return cls.list(sql_filter=("name LIKE ?", [f"%{query}%"]))

    def DESCRIBE(self, data, tx):
        """Handle DESCRIBE -- return schema + data."""
        return {
            "proto": self.__class__.schema(),
            "data": self.model_dump(response=True),
        }
```

This convention means:
- Instance methods handle instance-level messages (addressed to `Product/42`)
- Class methods handle type-level messages (addressed to `Product`)
- The `@expose_route` decorator creates HTTP endpoints that can ALSO be actor message handlers
- Unknown messages bubble to the Matrix for routing

## Appendix C: Open Questions for Phase-Specific Research

1. **CRUD as messages**: Should `CREATE`, `READ`, `UPDATE`, `DELETE` go through actor messaging? Or remain direct method calls? The JS system routes them through actors (via TX). The Python system currently uses direct method calls (via StorableMixin). Bridging this gap requires a design decision.

2. **WebSocket transport**: The JS Matrix uses NetworkAdapter for remote messaging. The Python equivalent needs a WebSocket server (FastAPI supports this) and a message routing protocol. Research needed on: async message handling, connection management, authentication per WebSocket.

3. **Observable pattern**: The JS system uses `Observable.apply(DynamicClass)` for reactive updates. The Python equivalent could use: (a) Python descriptors with `__set__` hooks, (b) a signal/slot library, (c) asyncio Futures/Events, (d) a custom observable mixin. Research needed.

4. **Concurrency model**: JS actors are single-threaded (event loop). Python has GIL + asyncio + threading. Should actors be async (use `async def inbox`)? Should they run on a thread pool? This affects the entire API surface.

5. **Actor persistence**: Should actor state (children, watchers) be persisted? The JS system keeps this in memory. For multi-process Python deployments, in-memory state won't work. Options: Redis, database, shared memory. Research needed.
