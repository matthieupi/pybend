# Proposition 1: Reactive — Compose Like Functors, Execute Like Actors

**Motto:** *Compose like functors, execute like actors.*
**Core metaphor:** Railroad tracks
**The program is:** The composed pipeline
**Primary operator:** `>>` (compose)

---

## The Core Insight

An Actor's `handler` IS a functor's `__exec__`. A TX IS a monad. Composition
IS routing. They're the same thing viewed from different angles.

Today in pyrofunc:
```python
result = Monad(5) | Add(3) >> Multiply(2)   # type-safe, composable
```

Today in actors:
```python
await matrix.inbox(TX(name='CREATE', target='products', data={...}))  # routable, async
```

Neither is complete. What if an Actor IS a Functor, and a TX IS a Monad?

## The Three Systems Side by Side

**Same task: "Process a product creation request"**

### Pyrofunc Alone

```python
result = Monad(data) | Validate >> Persist(db) >> Respond
#  composable  type-safe
#  no routing  no async  no errors  no identity  no lifecycle
```

### Actor Alone

```python
class Product(ActorModel):
    async def handler(target, tx):
        if tx.name == 'CREATE':
            try:
                validated = validate(tx.data)
                stored = await db.create(validated)
                await target.send(tx.reply(stored))
            except ValidationError as e:
                await target.send(tx.error(str(e)))
# monolithic  no composition  no type safety
# routable  async  identity  lifecycle
```

### Unified: Reactive

```python
# Define stages as actor-functors
# Each is BOTH an actor (routable, async, lifecycle)
# AND a functor (typed, composable, reusable)

class Validate(Reactive):
    """TX[RawRequest] -> TX[ValidRequest]"""
    async def __exec__(self, tx: TX) -> TX:
        schema = tx.meta.get('schema')
        errors = schema.validate(tx.data)
        if errors:
            return tx.error(f"Validation failed: {errors}", code=422)
        return tx

class Authorize(Reactive):
    """TX[any] -> TX[any] (gate -- same type in and out)"""
    def __init__(self, policy): self.policy = policy
    async def __exec__(self, tx: TX) -> TX:
        if not self.policy.allows(tx.meta.get('user'), tx.name):
            return tx.error("Forbidden", code=403)
        return tx

class Persist(Reactive):
    """TX[ValidRequest] -> TX[StoredEntity]"""
    async def __exec__(self, tx: TX) -> TX:
        entity = await self.storage.create(tx.data)
        return tx.evolve(data=entity, dtype='StoredEntity')

class Notify(Reactive):
    """TX[StoredEntity] -> TX[StoredEntity] (side-effect, passthrough)"""
    async def __exec__(self, tx: TX) -> TX:
        await self.bus.publish('entity.created', tx.data)
        return tx


# Compose -- >> validates types at composition time
# The result is an Actor with an address, children, lifecycle
create_flow = Validate >> Authorize(admin_policy) >> Persist >> Notify

# It's an actor -- register it, route to it
matrix.register(create_flow, addr='products/create')
await matrix.inbox(TX(name='CREATE', target='products/create', data={...}))

# It's a functor -- apply directly
result = await (TX(data={...}) | create_flow)

# It composes further
full_flow = RateLimit >> create_flow >> AuditLog

# Reuse stages across different flows
update_flow = Validate >> Authorize(owner_policy) >> Merge >> Persist >> Notify
delete_flow = Authorize(admin_policy) >> Delete >> Notify
read_flow   = Authorize(anyone_policy) >> Fetch >> Format
```

## What Only the Reactive Has

### 1. Railway-Oriented Error Handling

Pyrofunc has no error track. Actors check `is_error` manually in every
interceptor and handler. The unified system makes error handling structural:

```
TX flows on two tracks:

  +-- Validate --> Authorize --> Persist --> Notify --> Respond --+
  |            happy track (>>)                                   | success
  |                                                               v
TX +                                                            result
  |                                                               ^
  |            error track (automatic)                            | error
  +-- Validate -X --------------------------------------------> Error --+
               |
        returns tx.error() -> all remaining stages bypassed
                              error auto-routes to sender
```

Zero error-checking boilerplate in happy-path stages. A stage either returns
`tx` (continue) or `tx.error()` (short-circuit). The pipeline handles the rest.

### 2. Type-Safe Message Routing

Actors route by string address -- wrong destination is a runtime 404. With
typed composition:

```python
class ParseJSON(Reactive):
    async def __exec__(self, tx: TX) -> TX:   # TX[bytes] -> TX[dict]
        ...

class ValidateProduct(Reactive):
    async def __exec__(self, tx: TX) -> TX:   # TX[dict] -> TX[Product]
        ...

class StoreProduct(Reactive):
    async def __exec__(self, tx: TX) -> TX:   # TX[Product] -> TX[StoredProduct]
        ...

# Composes fine -- types align
ok = ParseJSON >> ValidateProduct >> StoreProduct

# Fails AT DEFINITION TIME -- StoreProduct expects TX[Product], not TX[bytes]
bad = ParseJSON >> StoreProduct  # TypeError: expected Product, got dict
```

Wiring errors caught when you **define** the pipeline, not when a message
arrives at 3 AM.

### 3. Pipeline-as-Actor (First-Class Pipelines)

A composed pipeline isn't a dead data structure -- it's a living actor:

```python
create_flow = Validate >> Persist >> Notify

# It has an address
create_flow.addr           # 'Validate.Persist.Notify' (auto-generated)

# It has children -- each stage is a child actor
create_flow.children       # {'Validate': ..., 'Persist': ..., 'Notify': ...}
create_flow.stages         # [Validate, Persist, Notify]

# It accepts interceptors -- apply to the WHOLE pipeline
create_flow.use(rate_limit, on='inbox')

# It has lifecycle
await create_flow.on_start()   # initializes all stages
await create_flow.on_stop()    # tears down all stages

# It's introspectable
create_flow.signature      # TX -> TX -> TX -> TX
create_flow.describe()     # "Validate -> Persist -> Notify"
```

### 4. Pipeline Algebra -- Reusable Building Blocks

```python
# Common concern blocks (functors)
secure    = Auth >> RateLimit >> Log
validated = ParseBody >> ValidateSchema

# Domain-specific stage blocks
write  = Persist >> IndexSearch >> InvalidateCache
notify = EmailOwner >> WebhookFire >> AuditLog

# Assemble different flows from the same blocks
create = secure >> validated >> write >> notify
read   = secure >> Fetch >> Format
update = secure >> validated >> Merge >> write >> notify
delete = secure >> Authorize(ADMIN) >> Delete >> notify

# Register all flows under one actor
class ProductAPI(Reactive):
    flows = {'CREATE': create, 'READ': read, 'UPDATE': update, 'DELETE': delete}
```

A new flow is assembled from existing pieces. A change to `secure` propagates
to every flow that uses it. Impossible with standalone actors (monolithic
handlers) and impossible with standalone pyrofunc (no routing).

### 5. Hot-Swappable Stages

Because each stage in a pipeline is an addressable actor:

```python
# Replace a stage at runtime
create_flow.replace('Persist', NewPersistStage)

# The pipeline type-checks the replacement:
# NewPersistStage must accept TX[ValidRequest] and produce TX[StoredEntity]
# If it doesn't, TypeError at replacement time
```

### 6. Fan-Out and Convergence

```python
# Fan-out: one input, multiple parallel outputs
after_persist = Notify & IndexSearch & InvalidateCache
#              all three receive the same TX, run concurrently

create_flow = Validate >> Persist >> after_persist >> Respond

# Conditional branching
class Router(Reactive):
    async def __exec__(self, tx: TX) -> TX:
        if tx.data.get('priority') == 'high':
            return tx.evolve(route='fast-track')
        return tx.evolve(route='standard')

flow = Router >> {'fast-track': FastPersist, 'standard': BatchPersist} >> Respond
```

## The Unified Primitive: Reactive

```
Reactive = Actor + Functor

            Actor gives it:              Functor gives it:
            ---------------              -----------------
            addr (identity)              __exec__ (typed transform)
            inbox/send (messaging)       >> (composition)
            children (hierarchy)         | (application)
            use() (interceptors)         __validate__ (type checking)
            on_start/on_stop (lifecycle) CompositeFunctor (pipeline)
            Matrix routing               Railway error track
```

```python
class Reactive(Actor, Functor):
    """An Actor that transforms TX messages as a typed Functor.

    - Define __exec__ for the transformation logic
    - Compose with >> for type-safe pipelines
    - Apply with | for direct execution
    - Route via Matrix for distributed execution
    - Pipeline results are themselves Reactive actors
    """

    async def __exec__(self, tx: TX) -> TX:
        """Override this. Your typed transformation."""
        return await self.handler(tx)

    def __rshift__(self, other):
        """Compose two reactive actors into a pipeline."""
        return Pipeline(self, other)   # Pipeline IS a Reactive IS an Actor

    async def __call__(self, tx: TX) -> TX:
        """Apply this reactive to a TX (functor application)."""
        if tx.is_error:
            return tx                  # railway: skip on error
        return await self.__exec__(tx)


class Pipeline(Reactive):
    """A composed chain of Reactive actors. Itself a Reactive actor."""
    stages: list[Reactive]

    async def __exec__(self, tx: TX) -> TX:
        for stage in self.stages:
            tx = await stage(tx)       # railway: stage() checks is_error
            if tx.is_error:
                break
        return tx

    def __rshift__(self, other):
        """Extend the pipeline."""
        return Pipeline(*self.stages, other)
```

And TX gains monad semantics:

```python
class TX:
    # ... existing fields ...

    def evolve(self, **updates) -> 'TX':
        """Create a new TX with updated fields (monad bind)."""
        return TX(**{**self.__dict__, **updates})

    async def __or__(self, reactive: Reactive) -> 'TX':
        """Apply a Reactive pipeline: tx | pipeline"""
        return await reactive(self)

    @property
    def __dtype__(self):
        """Type tag for functor validation."""
        return self.name

    @property
    def __value__(self):
        """Monad value access."""
        return self.data
```

## Limitations

- Linear composition only -- can't express graphs, branches, or shared nodes
- No message-level history -- the pipeline knows its structure, the TX doesn't record its journey
- No sender-side control -- the receiver defines the pipeline, not the message
- No topology-level reasoning -- can't analyze the full system graph

These limitations are addressed by Propositions 2 (Journey) and 3 (Mesh).
