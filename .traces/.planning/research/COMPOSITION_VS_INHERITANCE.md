# Design Pattern Analysis: Composition vs Inheritance vs Mixin vs Protocol

**Project:** N3TX -- Adding Actor behavior to ProtoModel
**Researched:** 2026-02-26
**Overall confidence:** HIGH (based on codebase analysis, Pydantic docs, community discussions, real-world precedent)

---

## Context

N3TX has two orthogonal concerns to combine:

1. **Data modeling** -- fields, validation, serialization, schema generation (ProtoModel extends PydanticBaseModel)
2. **Actor messaging** -- address, children, inbox, send, message routing (to be ported from JavaScript Actor.js)

A third concern is already solved:

3. **Persistence** -- CRUD operations (StorableMixin, injected dynamically via `__init_subclass__` when `__storable__ = True`)

The question: what pattern should combine (1) and (2)?

### What Actor.js Actually Does

From reading `src/n3tx/static/core/Actor.js`, the JS Actor provides:

- **Identity**: `#addr` (private, set at construction)
- **Hierarchy**: `#parent`, `#children` (Map of child actors)
- **Messaging**: `inbox(event)` receives messages, `send(event)` dispatches them
- **Routing**: static `_send()` with 3-case routing (local child, prefixed child, bubble to root)
- **Lifecycle**: `spawn(addr, ActorClass)` creates child actors
- **Registration**: `register(actor)` adds to children map
- **Class transformation**: `Actor.subclass(ChildClass, ...Mixins)` -- a decorator-like static method that adds actor capabilities to any class without inheritance

The JS `Actor.subclass()` pattern is **Pattern E in Python terms** -- it transforms a class by adding static/instance properties and methods. This is NOT inheritance in JS either.

### What StorableMixin Actually Does

From reading `src/n3tx/core/models/storable_mixin.py`:

- **Class-level**: `storage` (ClassVar, injected), `__pk__`, `__tablename__`
- **Instance**: `save()`, `_storage_dict()`
- **Class methods**: `create()`, `list()`, `get()`, `update()`, `delete()`, `set_storage()`, `create_table()`
- **Injection mechanism**: `ProtoModel.__init_subclass__` checks `__storable__` flag, then mutates `cls.__bases__` to include StorableMixin

Key observation: StorableMixin is a **pure method bag**. It has no `__init__`, no private state, no metaclass. It adds class methods and instance methods that operate on a class-level `storage` attribute. This is why the injection pattern works cleanly with Pydantic.

### Why This Decision Matters

Actor behavior is fundamentally different from StorableMixin:

| Property | StorableMixin | Actor |
|----------|--------------|-------|
| Has instance state | No (class-level storage only) | Yes (addr, children, parent) |
| Has `__init__` | No | Yes (addr generation, registration) |
| Interacts with Pydantic fields | No (operates on model_dump output) | Maybe (addr could be a field, or not) |
| Has class-level state | Yes (storage ClassVar) | Yes (children Map, root reference) |
| Has lifecycle hooks | No | Yes (spawn, register) |
| Needs construction order | No | Yes (addr before registration) |

This means: **whatever worked for StorableMixin may NOT work for Actor**. The Actor has richer requirements.

---

## Pattern A: Direct Multiple Inheritance

### What the developer writes

```python
# Option A1: Actor baked into ProtoModel
class ProtoModel(PydanticBaseModel, Actor):
    """Every model is automatically an actor."""
    ...

class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str
    price: float
```

```python
# Option A2: Selective inheritance
class Product(ProtoModel, Actor):
    __tablename__ = 'products'
    __storable__ = True
    name: str
    price: float
```

### Mental model

"A Product IS-A data model AND IS-A actor."

Concepts to understand: 1 (it's just inheritance). But the developer must understand MRO implications, and that Pydantic's `__init__` must play nicely with Actor's `__init__`.

### The "5 operations" test

```python
# 1. Define a model
class Product(ProtoModel):  # Actor is in ProtoModel's bases
    name: str
    price: float

# 2. Send it a message
product = Product(name="Widget", price=9.99)
product.send({"name": "price_update", "target": "Product", "data": {"price": 12.99}})

# 3. Handle a message
class Product(ProtoModel):
    name: str
    price: float

    def price_update(self, data):
        self.price = data["price"]

# 4. Extend with custom behavior
class AuditProduct(Product):
    audit_log: list = []

    def price_update(self, data):
        self.audit_log.append({"old": self.price, "new": data["price"]})
        super().price_update(data)

# 5. Test in isolation
def test_product_messaging():
    p = Product(name="Widget", price=9.99)  # But Actor.__init__ needs addr...
    # PROBLEM: Pydantic's __init__ and Actor's __init__ conflict
```

### Composability

| Question | Answer |
|----------|--------|
| Actor that isn't a model? | NO -- Actor is welded to ProtoModel |
| Model that isn't an actor? | NO (A1) or YES with separate base (A2) |
| Model + actor + storable? | YES (all three in bases) |
| Add new concern (cacheable)? | Add to ProtoModel's bases -- affects ALL models |

### The "join model" problem

```python
join_model = type("ProductComment", (Comment,), fields)
# Comment inherits from ProtoModel which inherits from Actor
# So ProductComment IS an actor with addr, children, inbox
# But it's an auto-generated intermediate model -- it should NOT be an actor
# No way to opt out in A1. In A2, Comment would need to also inherit Actor.
```

**Verdict**: A1 forces actor behavior on ALL models including join models. A2 requires every model that wants actor behavior to explicitly inherit from Actor, which is error-prone and verbose.

### The "custom method" problem

```python
@expose_route('/like', methods=['POST'])
def like(self, user: User = None) -> str:
    ...

# In actor world, this could also be triggered by a message:
# product.inbox({"name": "like", "data": {"user_id": 42}})
# But the route system and actor system are two separate dispatch mechanisms
# pointing at the same method. Who wins? How do they compose?
```

The `@expose_route` decorator stores metadata on the function. The actor inbox dispatches by message name. These are **two independent dispatch tables** that could conflict.

### Debugging story

```
Traceback:
  File "proto_model.py", line 112, in __init__
    super().__init__(*args, **params)
  File "pydantic/main.py", line 171, in __init__
    ...
TypeError: Actor.__init__() got unexpected keyword arguments: 'name', 'price'
```

The problem: Pydantic's `__init__` processes field kwargs. Actor's `__init__` expects `(addr)`. Multiple inheritance means Python's MRO calls both, and they disagree on what `__init__` parameters mean.

### Migration path

**Breaking changes**: Every existing model suddenly has Actor behavior. Actor's `__init__` signature conflicts with Pydantic's generated `__init__`. This is not a migration -- it's a rewrite of ProtoModel's initialization.

**Effort**: HIGH. Must reconcile two `__init__` signatures, handle MRO for all existing models, potentially break Pydantic's schema generation if Actor has its own fields.

### Unforeseen implications

1. **Pydantic's metaclass vs Actor initialization**: Pydantic v2 uses `ModelMetaclass` internally. Adding a class with its own metaclass (or complex `__init__`) to the bases creates unpredictable interactions. [Pydantic issue #7808](https://github.com/pydantic/pydantic/issues/7808) documents metaclass conflicts when combining BaseModel with Protocol; Actor would face similar issues.

2. **Schema pollution**: If Actor has any public attributes (addr, children), Pydantic will try to include them in the JSON Schema. You'd need to mark them all as `exclude=True` or use private attributes with `__` prefix.

3. **Serialization breakage**: `model_dump()` would try to serialize Actor state (children map, parent references), creating circular references.

4. **The `id` vs `addr` identity crisis**: ProtoModel already has `id: int`. Actor has `addr: str`. Which is the identity? Both? Now every model has two identities that must stay in sync.

### Category theory assessment

Multiple inheritance attempts to form a **product** in the category of Python classes, where `Product = ProtoModel x Actor`. But products require projection morphisms (you can always extract the ProtoModel part or the Actor part independently). With Python MI, the two concerns are fused -- you cannot extract one without the other. This is a **non-commutative join in a lattice**, not a clean product. The diamond problem in MRO makes this a partial order with ambiguous meets.

**Verdict**: Mathematically impure. Practically dangerous.

### RECOMMENDATION: REJECT

**Why**: The `__init__` conflict between Pydantic and Actor is a fundamental incompatibility. Pydantic generates `__init__` from field definitions. Actor needs `__init__` for addr/registration. These are irreconcilable without significant hacks. Schema pollution and serialization issues compound the problem. The JS frontend Actor.js itself doesn't use inheritance for this -- it uses `Actor.subclass()`, which is a class transformer.

---

## Pattern B: Mixin Injection (StorableMixin pattern)

### What the developer writes

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __actor__ = True          # <-- new flag

    name: str
    price: float

    def on_message(self, event):
        """Custom message handler."""
        if event.name == 'price_update':
            self.price = event.data['price']
```

ProtoModel's `__init_subclass__` would inject ActorMixin:

```python
def __init_subclass__(cls, **kwargs):
    if getattr(cls, '__storable__', False):
        if not issubclass(cls, StorableMixin):
            cls.__bases__ = (StorableMixin,) + cls.__bases__

    if getattr(cls, '__actor__', False):
        if not issubclass(cls, ActorMixin):
            cls.__bases__ = (ActorMixin,) + cls.__bases__

    super().__init_subclass__(**kwargs)
```

### Mental model

"Set `__actor__ = True` and your model gets messaging superpowers, just like `__storable__ = True` gives it persistence."

Concepts to understand: 2 (flags system, what each mixin provides). The developer doesn't need to know HOW the injection works.

### The "5 operations" test

```python
# 1. Define a model
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __actor__ = True
    name: str
    price: float

# 2. Send it a message
product = Product(name="Widget", price=9.99)
product.send({"name": "price_update", "target": "products/1", "data": {"price": 12.99}})

# 3. Handle a message
class Product(ProtoModel):
    __actor__ = True
    name: str
    price: float

    def price_update(self, data):
        self.price = data["price"]

# 4. Extend with custom behavior
class AuditProduct(Product):
    def price_update(self, data):
        log_audit(self.id, "price", data)
        super().price_update(data)

# 5. Test in isolation
def test_product_messaging():
    p = Product(name="Widget", price=9.99)
    # ActorMixin methods are available
    p.inbox({"name": "price_update", "data": {"price": 12.99}})
    assert p.price == 12.99
```

### Composability

| Question | Answer |
|----------|--------|
| Actor that isn't a model? | NO -- ActorMixin is injected into ProtoModel subclasses |
| Model that isn't an actor? | YES -- just don't set `__actor__ = True` |
| Model + actor + storable? | YES -- set both flags |
| Add new concern (cacheable)? | Add `__cacheable__` flag + CacheableMixin -- consistent pattern |

### The "join model" problem

```python
# generate_join_model creates:
join_model = type("ProductComment", (Comment,), {
    "__tablename__": "products_comments",
    "__storable__": True,
    # __actor__ is NOT set -- join model is NOT an actor
})
```

**This works perfectly.** Join models inherit `__storable__` because their parent (Comment) has it. But `__actor__` would NOT propagate unless explicitly set, because `generate_join_model` controls exactly what class attributes are set.

Wait -- actually, if Comment has `__actor__ = True`, then ProductComment inherits it. We'd need `__actor__ = False` in the join model fields dict, or check for `__owner__` (join models have it, regular models don't).

```python
def __init_subclass__(cls, **kwargs):
    # Don't inject actor into join models
    is_join = hasattr(cls, '__owner__')
    if getattr(cls, '__actor__', False) and not is_join:
        if not issubclass(cls, ActorMixin):
            cls.__bases__ = (ActorMixin,) + cls.__bases__
```

### The "custom method" problem

```python
@expose_route('/like', methods=['POST'])
def like(self, user: User = None) -> str:
    ...

# ActorMixin.inbox could dispatch to this same method:
def inbox(self, event):
    handler = getattr(self, event.name, None)
    if handler:
        return handler(**event.data)
```

Both `@expose_route` and `inbox` dispatch to the same method by name. This is actually elegant -- the HTTP route and the actor message are two entry points to the same logic. But we need to ensure the `user` parameter injection works for both paths.

### Debugging story

```
# Developer sees unexpected behavior
product.inbox({"name": "like", "data": {"user_id": 42}})
# Traceback:
#   File "actor_mixin.py", line 15, in inbox
#     return handler(**event.data)
#   File "product.py", line 45, in like
#     if not user:
# TypeError: like() got an unexpected keyword argument 'user_id'

# The issue is clear: the message data keys don't match the method signature.
# The developer can trace: inbox -> getattr -> like()
# Fix: either normalize message data or add a message adapter
```

The debugging story is **decent**. The call chain is `inbox -> getattr -> method`. Stack traces show exactly where the dispatch happens. But the mixin injection itself is "magical" -- `cls.__bases__` mutation is not something developers expect.

### Migration path

**Breaking changes**: None. Existing models don't have `__actor__` set, so nothing changes. Models opt in.

**Effort**: LOW. Add `__actor__ = True` to models that need actor behavior. Write ActorMixin. Modify `__init_subclass__` to handle the new flag.

### Unforeseen implications

1. **The `__init__` problem remains (softened)**: ActorMixin needs instance state (addr, children). But if ActorMixin has an `__init__`, it must cooperate with Pydantic's `__init__`. StorableMixin avoided this by having NO `__init__`. ActorMixin NEEDS one for addr generation.

   **Mitigation**: Use `__init_subclass__` to add addr as a Pydantic field with a default factory, or use `model_post_init` to set up actor state.

2. **Base mutation is fragile**: `cls.__bases__ = (ActorMixin,) + cls.__bases__` is the same pattern used for StorableMixin, so it's proven in this codebase. But it's still a Python anti-pattern that can confuse type checkers and IDE autocompletion.

3. **Inheritance of `__actor__`**: If Product has `__actor__ = True` and Comment does not, but ProductComment inherits from Comment, the behavior is correct. But if Comment DOES have `__actor__ = True`, ProductComment inherits it. The `is_join` guard handles this.

4. **Testing requires the mixin to be present**: You can't test a model's methods in isolation from the mixin without carefully constructing the class hierarchy.

### Category theory assessment

This is a **conditional functor** from the category of class definitions to the category of actor-enabled classes. The flag `__actor__` acts as a predicate that gates the functor's application. This is clean from a categorical perspective -- it's a filtered endofunctor on the category of ProtoModel subclasses. The injection is a **natural transformation** from the identity functor to the ActorMixin-augmented functor, conditioned on the flag.

**Verdict**: Consistent with existing codebase patterns. The `__init__` problem is the key risk.

### RECOMMENDATION: VIABLE with caveats

**Why**: Consistent with StorableMixin pattern. Opt-in. Clean join model story. But the `__init__` requirement for Actor state means this is harder than StorableMixin was. Requires careful design of how actor state initializes without conflicting with Pydantic's `__init__`.

---

## Pattern C: Composition with Auto-wrap

### What the developer writes

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __actor__ = True

    name: str
    price: float

# Behind the scenes, register_model() creates:
# ProductActor(Actor) that WRAPS Product
# product_actor.model is the Product instance
# product_actor.inbox(...) dispatches to product_actor.model methods
```

Developer accesses it through the actor system:

```python
# Actor system manages the wrapper
actor = ActorSystem.get("products/1")
actor.send({"name": "price_update", "data": {"price": 12.99}})
# Internally: actor.model.price = 12.99
```

### Mental model

"Models are data. Actors wrap models and give them messaging. They're separate things that work together."

Concepts to understand: 3 (models, actors, the wrapping relationship).

### The "5 operations" test

```python
# 1. Define a model
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str
    price: float

# 2. Send it a message
# Must go through actor system, not the model directly
ActorSystem.send("products/1", {"name": "price_update", "data": {"price": 12.99}})

# 3. Handle a message
class Product(ProtoModel):
    name: str
    price: float

    def price_update(self, data):
        self.price = data["price"]

    # OR: handler is on the wrapper
    # class ProductActor(ModelActor):
    #     def price_update(self, data):
    #         self.model.price = data["price"]

# 4. Extend with custom behavior
# This gets confusing -- do you extend the model or the wrapper?
class AuditProduct(Product):
    def price_update(self, data):
        ...  # extends model
# vs
class AuditProductActor(ProductActor):
    def price_update(self, data):
        ...  # extends wrapper

# 5. Test in isolation
def test_product_data():
    p = Product(name="Widget", price=9.99)
    # Pure data, no actor. Easy to test.

def test_product_actor():
    p = Product(name="Widget", price=9.99)
    actor = ModelActor(model=p)
    actor.inbox({"name": "price_update", "data": {"price": 12.99}})
    assert p.price == 12.99
```

### Composability

| Question | Answer |
|----------|--------|
| Actor that isn't a model? | YES -- Actor stands alone |
| Model that isn't an actor? | YES -- just a ProtoModel |
| Model + actor + storable? | YES -- storable model wrapped in actor |
| Add new concern (cacheable)? | Add CacheableWrapper or CacheableMixin -- unclear pattern |

### The "join model" problem

```python
join_model = generate_join_model(Product, Comment)
# register_model sees __actor__ is not set (or is_join), skips actor wrapping
# ProductComment is pure data + storage. Perfect.
```

**Clean separation.** The wrapper is created at registration time, not at class definition time. Join models are registered without wrappers.

### The "custom method" problem

```python
@expose_route('/like', methods=['POST'])
def like(self, user: User = None) -> str:
    ...

# In the wrapper model:
# The actor wrapper needs to know about @expose_route methods
# to dispatch messages to them. This requires introspecting the model.
# Two options:
#   1. Actor dispatches to model.like() -- simple delegation
#   2. Actor has its own like() that wraps model.like() -- duplication
```

Option 1 is straightforward: the wrapper's `inbox` does `getattr(self.model, event.name)(**event.data)`. But `user` injection becomes tricky because the actor system doesn't have HTTP request context.

### Debugging story

```
# Developer sees:
actor.inbox({"name": "like", "data": {}})
# Traceback:
#   File "model_actor.py", line 30, in inbox
#     handler = getattr(self.model, event.name)
#   File "model_actor.py", line 32, in inbox
#     return handler(**event.data)
#   File "product.py", line 45, in like
#     if not user:
# TypeError: ...

# The developer must understand:
# 1. There's an actor wrapping their model
# 2. The actor dispatches to the model
# 3. The method is on the model, not the actor
# This is ONE extra layer of indirection.
```

### Migration path

**Breaking changes**: None. Models stay the same. Actor wrapping is additive at registration time.

**Effort**: MEDIUM. Must build the wrapping/registration infrastructure. Existing code unchanged.

### Unforeseen implications

1. **Identity split**: The model has `id: int` and the actor has `addr: str`. Two identities for the same logical entity. Which do you use where? The `addr` is likely `"{tablename}/{id}"` but now you're maintaining a mapping.

2. **State synchronization**: If someone modifies the model directly (`product.price = 12.99`), the actor wrapper doesn't know. If the actor modifies the model, the persistence layer doesn't know. You need hooks or observers, which adds complexity.

3. **The "which object do I have?" problem**: In HTTP routes, you have the model. In the actor system, you have the wrapper. Passing objects between systems requires unwrapping/wrapping. `product.send(...)` doesn't work -- you need `actor.send(...)`.

4. **Lifecycle mismatch**: Models are created per-request (Pydantic instances are cheap). Actors are long-lived (they hold state, have addresses). When does a ModelActor get created? When does it get garbage collected? This is a fundamental impedance mismatch.

### Category theory assessment

Composition is a **functor** from the category of ProtoModel subclasses to the category of Actors: `F: Model -> ModelActor(Model)`. This is clean -- it preserves the structure of models while mapping them into a new category. The wrapping relationship is a natural transformation between the identity functor (models as themselves) and the actor functor (models wrapped in actors).

**However**: the functor is not faithful (information about the model's internal dispatch is partially lost in the wrapping) and not full (the actor has capabilities the model doesn't).

**Verdict**: Categorically clean but practically introduces the "two objects for one thing" problem.

### RECOMMENDATION: VIABLE for standalone actor system, POOR for "model IS actor"

**Why**: Clean separation of concerns. No Pydantic conflicts. But the impedance mismatch between short-lived model instances and long-lived actors creates a fundamental design tension. Good if actors and models are genuinely separate things. Bad if "the model IS the actor" is the goal.

---

## Pattern D: Protocol + Default Implementation

### What the developer writes

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ActorProtocol(Protocol):
    """Any object that can participate in the actor system."""
    addr: str

    def inbox(self, event: dict) -> Any: ...
    def send(self, event: dict) -> Any: ...

class ActorBehavior:
    """Default implementation of ActorProtocol. Mix in or use standalone."""
    _addr: str = ""
    _children: dict = {}

    @property
    def addr(self) -> str:
        return self._addr or f"{self.__class__.__name__}/{getattr(self, 'id', 0)}"

    def inbox(self, event):
        handler = getattr(self, event.get('name', ''), None)
        if handler:
            return handler(event.get('data', {}))
        raise ValueError(f"No handler for {event.get('name')}")

    def send(self, event):
        ActorSystem.route(event)

# Developer usage:
class Product(ProtoModel, ActorBehavior):
    __tablename__ = 'products'
    __storable__ = True
    name: str
    price: float
```

### Mental model

"ActorProtocol defines what actors can do. ActorBehavior provides a default implementation. Mix in ActorBehavior to make your model an actor."

Concepts to understand: 3 (protocol, default implementation, opt-in mixing).

### The "5 operations" test

```python
# 1. Define a model
class Product(ProtoModel, ActorBehavior):
    __tablename__ = 'products'
    __storable__ = True
    name: str
    price: float

# 2. Send a message
product = Product(name="Widget", price=9.99)
product.send({"name": "price_update", "target": "products/1", "data": {"price": 12.99}})

# 3. Handle a message
class Product(ProtoModel, ActorBehavior):
    name: str
    price: float

    def price_update(self, data):
        self.price = data["price"]

# 4. Extend with custom behavior
class AuditProduct(Product):
    def price_update(self, data):
        log_audit(self.id, data)
        super().price_update(data)

# 5. Test in isolation
def test_product_messaging():
    p = Product(name="Widget", price=9.99)
    p.inbox({"name": "price_update", "data": {"price": 12.99}})
    assert p.price == 12.99

def test_actor_protocol_conformance():
    p = Product(name="Widget", price=9.99)
    assert isinstance(p, ActorProtocol)  # structural check
```

### Composability

| Question | Answer |
|----------|--------|
| Actor that isn't a model? | YES -- any class can implement ActorProtocol or mix in ActorBehavior |
| Model that isn't an actor? | YES -- just don't include ActorBehavior |
| Model + actor + storable? | YES -- `class Product(ProtoModel, ActorBehavior):` with `__storable__ = True` |
| Add new concern (cacheable)? | Define CacheableProtocol + CacheableBehavior -- consistent pattern |

### The "join model" problem

```python
# generate_join_model:
join_model = type("ProductComment", (Comment,), fields)
# If Comment extends ActorBehavior, ProductComment inherits it.
# Unlike Pattern B, there's no flag to conditionally skip injection.
# But: ActorBehavior has NO __init__, so it doesn't break anything.
# The join model just has dormant actor methods it never uses.
```

Not ideal -- join models carry dead code. But since ActorBehavior is a pure method bag (like StorableMixin), the dead methods are harmless. They add no overhead unless called.

### The "custom method" problem

```python
@expose_route('/like', methods=['POST'])
def like(self, user: User = None) -> str:
    ...

# ActorBehavior.inbox dispatches to self.like() by name.
# @expose_route metadata coexists peacefully -- it's on the same method.
# HTTP route -> like(user=resolved_user)
# Actor message -> inbox({"name": "like"}) -> like(data_from_message)
# Same method, two entry points. Works if parameter shapes align.
```

### Debugging story

```python
# isinstance checks work at runtime:
assert isinstance(product, ActorProtocol)  # True

# Type checkers verify protocol conformance:
# mypy will flag if Product is missing inbox() or send()

# Stack traces are clean -- no magic injection:
#   File "product.py", line 12, in price_update
#   File "actor_behavior.py", line 15, in inbox
# Developer sees: inbox called my method. Clear.
```

**Best debugging story of all patterns so far.** No metaclass magic, no base mutation, no wrappers. The developer explicitly mixed in ActorBehavior and can see it in the class definition.

### Migration path

**Breaking changes**: Existing models that want actor behavior must add `, ActorBehavior` to their class definition. That's it.

**Effort**: LOW. Write ActorProtocol + ActorBehavior. Modify target models to include ActorBehavior in bases.

BUT: Pydantic's [known issues with multiple inheritance](https://github.com/pydantic/pydantic/discussions/5974) apply. If ActorBehavior has any attributes that look like Pydantic fields, schema generation may break. The key is: ActorBehavior must NOT inherit from BaseModel, and must use private attributes (`_addr`, `_children`) with underscore prefix so Pydantic ignores them.

### Unforeseen implications

1. **Pydantic field detection**: Pydantic v2 introspects ALL bases for field-like attributes. If ActorBehavior has `addr: str` as a class attribute, Pydantic will try to include it as a model field. Must use `_addr` with property accessor, or `__addr` with name mangling.

2. **Protocol + BaseModel metaclass conflict**: [Pydantic issue #7808](https://github.com/pydantic/pydantic/issues/7808) documents that inheriting from both BaseModel and Protocol causes `TypeError: metaclass conflict`. ActorBehavior must NOT inherit from ActorProtocol. The protocol is for type checking only; the behavior class is for runtime.

3. **No automatic opt-in/opt-out**: Unlike Pattern B's flag system, developers must remember to include ActorBehavior in their bases. This is more explicit (good) but more verbose (bad) and easy to forget.

4. **MRO with StorableMixin**: With `__storable__` injecting StorableMixin AND ActorBehavior mixed in manually, the class has: `Product -> ActorBehavior -> StorableMixin -> ProtoModel -> PydanticBaseModel`. MRO works, but it's a 5-deep chain.

### Category theory assessment

Protocol defines a **type class** (in Haskell terms) or a **morphism specification** in the category of Python types. ActorBehavior provides a **default instance** of that type class. This is the cleanest categorical structure: the protocol is a functor interface, the behavior is a natural transformation providing a default implementation.

The relationship `ActorBehavior satisfies ActorProtocol` is an **adjunction** between the category of actor interfaces and the category of actor implementations. The protocol is the free construction; the behavior is the forgetful functor's right adjoint.

**Verdict**: Categorically the purest pattern. Type theory approves.

### RECOMMENDATION: STRONG CANDIDATE

**Why**: Explicit, composable, testable, debuggable. No metaclass conflicts (if ActorBehavior is a plain class). Protocol provides type safety. Consistent with Python typing ecosystem. The main risk is Pydantic field detection on ActorBehavior attributes, which is manageable with private naming.

---

## Pattern E: Decorator / Class Transformer

### What the developer writes

```python
@actor
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str
    price: float

    def price_update(self, data):
        self.price = data["price"]
```

The `@actor` decorator:

```python
def actor(cls):
    """Transform a ProtoModel subclass into an actor participant."""

    # Add actor address property
    original_init = cls.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        tablename = getattr(self.__class__, '__tablename__', self.__class__.__name__.lower())
        self._actor_addr = f"{tablename}/{self.id}" if self.id else f"{tablename}/new"
        self._actor_children = {}

    cls.__init__ = new_init

    # Add addr property
    cls.addr = property(lambda self: self._actor_addr)

    # Add inbox
    def inbox(self, event):
        if isinstance(event, dict):
            name = event.get('name', '')
            data = event.get('data', {})
        else:
            name, data = event.name, event.data
        handler = getattr(self, name, None)
        if handler and callable(handler):
            return handler(data)
        raise ValueError(f"No handler for '{name}' on {self.__class__.__name__}")
    cls.inbox = inbox

    # Add send
    def send(self, event):
        from n3tx.core.actor import ActorSystem
        ActorSystem.route(event)
    cls.send = send

    # Mark as actor
    cls.__actor__ = True

    return cls
```

This mirrors the JS `Actor.subclass()` pattern directly.

### Mental model

"Decorate your model with `@actor` and it becomes an actor participant."

Concepts to understand: 1.5 (decorators are familiar; what the decorator adds is implicit).

### The "5 operations" test

```python
# 1. Define a model
@actor
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str
    price: float

# 2. Send a message
product = Product(name="Widget", price=9.99)
product.send({"name": "price_update", "target": "products/1", "data": {"price": 12.99}})

# 3. Handle a message
@actor
class Product(ProtoModel):
    name: str
    price: float

    def price_update(self, data):
        self.price = data["price"]

# 4. Extend with custom behavior -- THIS IS THE PROBLEM
class AuditProduct(Product):
    # Product was decorated, so AuditProduct inherits the monkey-patched methods.
    # But if AuditProduct also needs @actor... applying it again is idempotent?
    def price_update(self, data):
        log_audit(self.id, data)
        super().price_update(data)

# 5. Test in isolation
def test_product():
    p = Product(name="Widget", price=9.99)
    p.inbox({"name": "price_update", "data": {"price": 12.99}})
    assert p.price == 12.99
```

### Composability

| Question | Answer |
|----------|--------|
| Actor that isn't a model? | YES -- `@actor` can be applied to any class (with adaptation) |
| Model that isn't an actor? | YES -- just don't apply `@actor` |
| Model + actor + storable? | YES -- decorator + `__storable__` flag |
| Add new concern (cacheable)? | Add `@cacheable` decorator -- consistent pattern |

### The "join model" problem

```python
# generate_join_model creates class dynamically with type()
join_model = type("ProductComment", (Comment,), fields)
# If Comment has @actor applied, ProductComment inherits the monkey-patched methods.
# Similar to Pattern D -- dormant methods on join models.
# But: @actor wraps __init__, so ProductComment's __init__ includes actor setup.
# This is MORE problematic than Pattern D because __init__ is actively modified.
```

**Issue**: The decorator modifies `__init__`, so all subclasses (including join models) get actor initialization code running. We'd need either:
- A guard in the decorator's `new_init` that checks for join models
- Apply `@actor` AFTER class hierarchy is finalized (but decorators run at class definition time)

### The "custom method" problem

Same as Pattern D -- `inbox` dispatches to `self.{method_name}`. Works with `@expose_route` methods.

### Debugging story

```python
# Developer inspects the class:
print(Product.__init__)  # <function actor.<locals>.new_init at 0x...>
# "Where did my __init__ go?" -- it's wrapped.
# Less transparent than Pattern D where the bases are visible.

# Stack trace:
#   File "decorators.py", line 12, in new_init
#     original_init(self, *args, **kwargs)
#   File "pydantic/main.py", line 171, in __init__
#     ...
# Developer sees the decorator's wrapper in the trace.
```

Debugging story is GOOD but not as clean as Pattern D. The `__init__` wrapping adds one frame to every construction stack trace. Type checkers and IDEs may not see the added methods (`inbox`, `send`, `addr`) because they're dynamically monkey-patched.

### Migration path

**Breaking changes**: None. Add `@actor` to models that need it.

**Effort**: LOW. Write the decorator. Apply it to target models.

### Unforeseen implications

1. **`__init__` wrapping with Pydantic**: Pydantic v2 generates `__init__` via its metaclass. The decorator wraps it. But Pydantic may regenerate `__init__` during `model_rebuild()` or schema generation, OVERWRITING the decorator's wrapper. This is the **3am bug**: everything works until `model_rebuild()` is called (which happens for forward references), and then actor initialization silently stops working.

2. **Decorator ordering with `__init_subclass__`**: StorableMixin is injected via `__init_subclass__`. The `@actor` decorator runs AFTER class creation. Order:
   - Class body is evaluated
   - `__init_subclass__` runs (injects StorableMixin)
   - `@actor` decorator runs (wraps `__init__`, adds methods)
   - This order is correct. But if `__init_subclass__` is re-triggered (e.g., by metaclass), the decorator's changes survive only if `__init__` wasn't regenerated.

3. **IDE/type-checker blindness**: `product.inbox(...)` won't autocomplete. `mypy` won't know about it. Type stubs could help, but they're maintenance overhead.

4. **Inheritance of decorated methods**: If Product is `@actor` and AuditProduct extends Product, AuditProduct inherits the monkey-patched methods. Applying `@actor` again to AuditProduct would double-wrap `__init__`. The decorator must be idempotent.

### Category theory assessment

The decorator is an **endofunctor** on the category of classes: `D: Class -> Class`. It preserves the identity (class is still the same class, with the same name and bases) and adds structure. This is a **monad** -- the decorator is the unit (wrapping), and composition of decorators should be associative and have an identity.

The issue: `D(D(cls))` must equal `D(cls)` (idempotency). If the decorator isn't idempotent, it breaks the monad laws.

**Verdict**: Categorically sound if idempotent. The endofunctor is the most direct Python translation of the JS `Actor.subclass()` pattern.

### RECOMMENDATION: VIABLE but fragile

**Why**: Closest to the JS pattern. Explicit opt-in. But the `__init__` wrapping + Pydantic `__init__` regeneration is a real risk. IDE/type-checker support is poor. The `model_rebuild()` 3am bug is a showstopper unless carefully guarded.

---

## Pattern F: Metaclass Unification

### What the developer writes

```python
class Product(ProtoModel):  # ProtoModel uses unified metaclass
    __tablename__ = 'products'
    __storable__ = True
    __actor__ = True
    name: str
    price: float
```

Behind the scenes:

```python
from pydantic._internal._model_construction import ModelMetaclass

class N3TXMetaclass(ModelMetaclass):
    """Unified metaclass that handles Pydantic fields AND actor setup."""

    def __new__(mcs, name, bases, namespace, **kwargs):
        # Let Pydantic do its thing first
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Actor injection
        if namespace.get('__actor__', False) or any(
            getattr(b, '__actor__', False) for b in bases
        ):
            if not hasattr(cls, '_actor_initialized'):
                cls._setup_actor()
                cls._actor_initialized = True

        return cls

    @staticmethod
    def _setup_actor(cls):
        # Add actor methods to cls
        cls.inbox = _default_inbox
        cls.send = _default_send
        cls.addr = property(_compute_addr)
        ...

class ProtoModel(PydanticBaseModel, metaclass=N3TXMetaclass):
    ...
```

### Mental model

"ProtoModel's metaclass handles everything -- data fields, storage, actor behavior. Just set flags."

Concepts to understand: 1 (flags). But MAINTAINING the metaclass requires understanding Pydantic internals deeply.

### The "5 operations" test

```python
# 1. Define a model
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __actor__ = True
    name: str
    price: float

# 2. Send a message
product = Product(name="Widget", price=9.99)
product.send({"name": "price_update", "data": {"price": 12.99}})

# 3-5: Same as Pattern B -- the surface DX is identical
```

### Composability

Same as Pattern B. Flag-based opt-in.

### The "join model" problem

Same as Pattern B. The metaclass checks flags and can inspect `__owner__` to skip actor setup for join models.

### The "custom method" problem

Same as Patterns B and D.

### Debugging story

```python
# When something goes wrong in class creation:
# Traceback:
#   File "ntx_metaclass.py", line 15, in __new__
#     cls = super().__new__(mcs, name, bases, namespace, **kwargs)
#   File "pydantic/_internal/_model_construction.py", line 85, in __new__
#     ...
# "What is N3TXMetaclass?" -- developer must understand metaclasses.
# This is the MOST opaque debugging story.
```

### Migration path

**Breaking changes**: ProtoModel's metaclass changes. This is invisible to consumers IF the metaclass is backwards compatible.

**Effort**: HIGH. Must understand and extend Pydantic's `ModelMetaclass`. Must track Pydantic version changes that modify `ModelMetaclass` internals.

### Unforeseen implications

1. **Coupling to Pydantic internals**: `ModelMetaclass` is in `pydantic._internal`. The underscore prefix means it's NOT part of the public API. Pydantic can change it in any minor version. [SQLModel learned this the hard way](https://github.com/fastapi/sqlmodel/issues/1623) -- Pydantic 2.12.0 broke SQLModel's metaclass-based integration.

2. **Maintenance burden**: Every Pydantic upgrade requires verifying the metaclass still works. This is a permanent tax on the project.

3. **Single point of failure**: If the metaclass breaks, ALL models break. Not just actor-enabled ones.

4. **Testing metaclasses is hard**: Metaclass behavior happens at class DEFINITION time, not instance creation time. You can't easily mock or isolate it in tests.

### Category theory assessment

The metaclass is a **higher-order functor** -- it operates on the class creation process itself, not on instances. This is the most powerful construct but also the most dangerous. In category theory terms, it's modifying the **category itself** (the rules by which objects are created), not just the objects or morphisms within it.

This is an **end** (in the enriched category sense) -- it's the universal construction that all other patterns can be expressed in terms of. But universality doesn't mean suitability.

**Verdict**: Maximum power, maximum coupling, maximum risk. The "nuclear option."

### RECOMMENDATION: REJECT

**Why**: Coupling to Pydantic's private `ModelMetaclass` API is a maintenance nightmare. SQLModel's ongoing struggles are a cautionary tale. The DX is identical to Pattern B, but the implementation risk is orders of magnitude higher. No benefit justifies the cost.

---

## Comparative Summary

### Surface DX Comparison

| Pattern | Model Definition | Message Send | Message Handle |
|---------|-----------------|-------------|----------------|
| A: MI | `class Product(ProtoModel):` (automatic) | `product.send(...)` | `def handler(self, data):` |
| B: Mixin | `__actor__ = True` | `product.send(...)` | `def handler(self, data):` |
| C: Wrap | `__actor__ = True` (at registration) | `ActorSystem.send(...)` | `def handler(self, data):` |
| D: Protocol | `class Product(ProtoModel, ActorBehavior):` | `product.send(...)` | `def handler(self, data):` |
| E: Decorator | `@actor class Product(ProtoModel):` | `product.send(...)` | `def handler(self, data):` |
| F: Metaclass | `__actor__ = True` | `product.send(...)` | `def handler(self, data):` |

### Risk Matrix

| Pattern | `__init__` conflict | Pydantic coupling | IDE support | Type safety | Migration | Maintenance |
|---------|-------------------|-------------------|-------------|-------------|-----------|-------------|
| A: MI | FATAL | HIGH | OK | OK | HIGH | MEDIUM |
| B: Mixin | MODERATE | LOW | POOR | POOR | LOW | LOW |
| C: Wrap | NONE | NONE | OK | GOOD | MEDIUM | MEDIUM |
| D: Protocol | LOW | LOW | GOOD | BEST | LOW | LOW |
| E: Decorator | HIGH | MEDIUM | POOR | POOR | LOW | MEDIUM |
| F: Metaclass | NONE | FATAL | OK | OK | HIGH | HIGH |

### The "5 Dimensions" Verdict

| Dimension | Winner | Runner-up | Rationale |
|-----------|--------|-----------|-----------|
| **DX simplicity** | B (Mixin) / F (Meta) | E (Decorator) | Just set a flag -- same pattern as `__storable__` |
| **Composability** | D (Protocol) | C (Composition) | Protocol enables standalone actors, mixed models, everything |
| **Safety** | D (Protocol) | C (Composition) | No metaclass hacks, no `__init__` conflicts, type-checked |
| **Consistency** | B (Mixin) | F (Metaclass) | Same pattern as existing `__storable__` -- users already know it |
| **Debuggability** | D (Protocol) | E (Decorator) | Explicit bases, no magic injection, clean traces |

---

## The Recommendation: Hybrid of B + D

**Pattern D (Protocol + Default Implementation) for the INTERFACE, Pattern B (Mixin Injection) for the MECHANISM.**

Here is why this is the right answer for N3TX, and the concrete design:

### The Design

```python
# --- Protocol (for type checking, testing, interop) ---
from typing import Protocol, runtime_checkable

@runtime_checkable
class ActorProtocol(Protocol):
    """Structural type for anything that participates in the actor system."""
    @property
    def addr(self) -> str: ...
    def inbox(self, event: dict) -> Any: ...
    def send(self, event: dict) -> Any: ...


# --- Default implementation (the mixin) ---
class ActorMixin:
    """
    Default actor behavior. Injected by ProtoModel when __actor__ = True.
    Can also be used standalone for non-model actors.

    NOTE: No __init__. Actor state is initialized via model_post_init
    (for Pydantic models) or __init_subclass__ class-level setup.
    """
    _actor_children: dict = {}  # Private-by-convention, Pydantic ignores underscore

    @property
    def addr(self) -> str:
        """Actor address derived from tablename/id."""
        tablename = getattr(self.__class__, '__tablename__', self.__class__.__name__.lower())
        instance_id = getattr(self, 'id', 0)
        return f"{tablename}/{instance_id}" if instance_id else f"{tablename}/new"

    def model_post_init(self, __context) -> None:
        """Pydantic v2 hook -- runs after __init__ completes."""
        super().model_post_init(__context)
        self._actor_children = {}

    def inbox(self, event: dict) -> Any:
        """Receive and dispatch a message."""
        name = event.get('name', '') if isinstance(event, dict) else event.name
        data = event.get('data', {}) if isinstance(event, dict) else event.data
        handler = getattr(self, name, None)
        if handler and callable(handler):
            return handler(data) if not isinstance(data, dict) else handler(**data)
        raise ValueError(f"No handler for '{name}' on {self.__class__.__name__}")

    def send(self, event: dict) -> Any:
        """Send a message through the actor system."""
        from n3tx.core.actor import ActorSystem
        return ActorSystem.route(event)


# --- Injection in ProtoModel (Pattern B mechanism) ---
class ProtoModel(PydanticBaseModel):
    def __init_subclass__(cls, **kwargs):
        # Existing StorableMixin injection
        if getattr(cls, '__storable__', False):
            if not issubclass(cls, StorableMixin):
                cls.__bases__ = (StorableMixin,) + cls.__bases__

        # New: ActorMixin injection (skip join models)
        is_join = hasattr(cls, '__owner__')
        if getattr(cls, '__actor__', False) and not is_join:
            if not issubclass(cls, ActorMixin):
                cls.__bases__ = (ActorMixin,) + cls.__bases__

        super().__init_subclass__(**kwargs)
```

### Why Hybrid B+D

1. **Consistency with codebase**: `__actor__ = True` is the same pattern as `__storable__ = True`. Zero new concepts for existing developers.

2. **No `__init__` conflict**: ActorMixin has NO `__init__`. It uses `model_post_init` (Pydantic v2's official post-initialization hook) to set up actor state. This is the KEY insight that makes Pattern B viable for Actor despite the `__init__` concern.

3. **Type safety via Protocol**: `ActorProtocol` lets code verify actor compliance without requiring inheritance. Functions can declare `def broadcast(target: ActorProtocol)` and accept ANY object that has `addr`, `inbox`, `send`.

4. **Standalone actors possible**: `class Scheduler(ActorMixin):` -- no ProtoModel needed. The mixin works independently.

5. **Join models handled**: The `is_join` guard prevents actor injection into auto-generated join models.

6. **`@expose_route` integration**: Actor `inbox` dispatches to `self.{method_name}`, which is the same method that `@expose_route` points HTTP routes at. Two entry points, one handler. No conflict.

7. **`addr` derived from existing identity**: `addr = "{tablename}/{id}"` reuses ProtoModel's existing identity system. No new identity to manage.

8. **Clean debugging**: Developer sees `ActorMixin` in `cls.__bases__` (or checks `isinstance(product, ActorProtocol)`). Stack traces show `ActorMixin.inbox -> Product.handler`. No metaclass magic.

### The Critical `model_post_init` Solution

The biggest risk with Pattern B was the `__init__` conflict. Here is how `model_post_init` solves it:

```python
# Pydantic v2 calls model_post_init AFTER __init__ completes.
# This is the official extension point for post-construction logic.
#
# Flow:
#   1. Product.__init__(name="Widget", price=9.99)  -- Pydantic handles this
#   2. Pydantic calls model_post_init(__context)     -- our hook
#   3. ActorMixin.model_post_init sets up _actor_children
#
# No __init__ conflict. No wrapping. No metaclass.
```

This is **verified** in [Pydantic v2 documentation](https://docs.pydantic.dev/latest/concepts/models/) as the supported way to run logic after model initialization.

### What the Developer Writes (Final DX)

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __actor__ = True

    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)

    # Message handlers are just methods:
    def price_update(self, data):
        self.price = data["price"]
        self.save()

    # @expose_route methods work as both HTTP endpoints AND message handlers:
    @expose_route('/like', methods=['POST'])
    def like(self, user: User = None) -> str:
        ...
```

```python
# Sending messages:
product = Product.get(1)
product.send({"name": "price_update", "target": "products/1", "data": {"price": 12.99}})

# Receiving messages:
product.inbox({"name": "price_update", "data": {"price": 12.99}})

# Type checking:
def notify_all(actors: list[ActorProtocol]):
    for actor in actors:
        actor.send({"name": "refresh", "target": actor.addr})
```

### Open Questions for Implementation

1. **Class-level actor registration**: The JS Actor.js registers actor CLASSES (not just instances) in a hierarchy. Should the Python ActorMixin also maintain a class-level registry? Probably yes, in `__init_subclass__`.

2. **Message format**: Should Python messages be dicts (flexible) or TX-like dataclasses (typed)? Recommend starting with dicts and adding a TX dataclass later.

3. **Actor System / Root Actor**: The JS has Matrix as root. Python needs an equivalent singleton. This is an implementation detail, not a pattern choice.

4. **Async inbox**: Should `inbox` be async? FastAPI is async. Actor message handling might need to be async. This affects the mixin's method signatures.

5. **`model_post_init` and non-Pydantic actors**: If ActorMixin is used standalone (without ProtoModel), `model_post_init` won't be called. The mixin needs a fallback initialization path -- either a lazy init in `inbox`/`send` or an explicit `init_actor()` method.

---

## Sources

### Primary (HIGH confidence)
- N3TX codebase: `proto_model.py`, `storable_mixin.py`, `Actor.js`, `Matrix.js`, `TX.js`
- [Pydantic v2 Models documentation](https://docs.pydantic.dev/latest/concepts/models/)
- [Pydantic multiple inheritance discussion #5974](https://github.com/pydantic/pydantic/discussions/5974)
- [Pydantic BaseModel + Protocol metaclass conflict #7808](https://github.com/pydantic/pydantic/issues/7808)

### Secondary (MEDIUM confidence)
- [SQLModel metaclass architecture (DeepWiki)](https://deepwiki.com/fastapi/sqlmodel/2.1-sqlmodel-class)
- [SQLModel Pydantic 2.12.0 breakage #1623](https://github.com/fastapi/sqlmodel/issues/1623)
- [Python Protocols: Leveraging Structural Subtyping (Real Python)](https://realpython.com/python-protocol/)
- [PEP 544: Protocols](https://peps.python.org/pep-0544/)

### Tertiary (LOW confidence -- community patterns)
- [Pydantic __init_subclass__ discussion #7177](https://github.com/pydantic/pydantic/discussions/7177)
- [Python class decorators as mixin alternative](https://code.activestate.com/recipes/577824-mixins-by-inheritance-vs-by-decoratorlets-try-deco/)
- [Aggregate, Delegate, Mixin, and Decorate patterns](https://www.qtrac.eu/pyagg.html)
