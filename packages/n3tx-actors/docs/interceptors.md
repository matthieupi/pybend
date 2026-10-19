# Interceptor Pattern

> Part of [n3tx-actors](../README.md)

## What This Covers

The `use()` interceptor mechanism: registration, chain execution, class/instance combination, and the `auth_interceptor` as a concrete example. Covers the `inbox`, `send`, and `request` interception points. Does not cover the full two-tier auth flow (see [actor-model.md](actor-model.md)).

## Architecture

```
actor.use(fn, on='inbox')   -->  stored in _interceptors['inbox'] (instance)
                                  or __interceptors__['inbox'] (class)

actor.inbox(tx):
    interceptors = class.__interceptors__['inbox'] + instance._interceptors['inbox']
    for fn in interceptors:        # FIFO order
        tx = await fn(tx)          # or fn(tx) for sync
        if tx.is_error: break      # short-circuit
    if tx.is_error:
        await actor.send(tx)       # route error back
        return                     # skip handler
    await actor.handler(tx)        # proceed normally

actor.send(tx):
    interceptors = ... (same retrieval)
    for fn in interceptors:
        tx = await fn(tx)
        if tx.is_error: break
    if tx.is_error: return         # DROP silently (don't route rejected outbound)
    ... normal routing ...
```

Key difference: `inbox` error -> sends error TX back to source. `send` error -> drops silently (no routing).

## Interface

### Registration

```python
# Plain call (default on='inbox')
actor.use(my_interceptor)
actor.use(my_interceptor, on='send')
actor.use(my_interceptor, on='request')  # NetworkAdapter only

# Decorator form
@actor.use
async def my_interceptor(tx: TX) -> TX: ...

# Decorator with target
@actor.use(on='request')
async def rate_limit(tx: TX) -> TX: ...

# Class-level
MyActor.use(class_interceptor, on='inbox')

# Instance-level
instance.use(instance_interceptor, on='inbox')
```

### Interceptor Signature

```python
async def interceptor(tx: TX) -> TX:
    # Inspect/modify tx
    # Return tx to continue chain
    # Return tx.error(...) to short-circuit
    return tx
```

Both sync and async interceptors are supported. Mixed chains work. Return the TX (possibly modified) to continue. Return an error TX to stop the chain.

### Chain Resolution

`Actor._get_interceptors(target, method_name)` returns:
- **Class target**: `cls.__interceptors__[method_name]`
- **Instance target**: `cls.__interceptors__[method_name] + instance._interceptors[method_name]`

Class interceptors always run first. Within each level, FIFO order (registration order).

### Interception Points

| Point | Method | Error behavior |
|-------|--------|----------------|
| `inbox` | `Actor.inbox()` | Error TX sent back via `send()`, handler skipped |
| `send` | `Actor.send()` | Error TX dropped silently (no routing) |
| `request` | `NetworkAdapter.request()` | Error TX returned directly to caller (never enters actor system) |

## Usage Patterns

### Auth interceptor on NetworkAPI (Tier 1)

```python
from n3tx_actors.api.auth_interceptor import auth_interceptor

api = NetworkAPI()
matrix.register(api)
api.use(auth_interceptor, on='request')
```

The `auth_interceptor` reads `tx.meta['model_cls']` and `tx.meta['user']`, checks `__access__` rules, computes `sql_filter` for list operations, and returns error TX for unauthorized requests. Schema requests always pass through.

For custom `@expose_route` methods, the interceptor is a boundary precheck, not always the final authority. Class/static methods have no resource, so their explicit `access=` rule can be evaluated at Tier 1. Instance methods may use resource-dependent rules such as `OWNER`, `Where(...)`, or composed rules; authenticated requests for those methods pass through to `ActorModel.handler()`, which loads the target instance and evaluates final method access with `AccessContext(resource=instance)`. Anonymous requests are still rejected at Tier 1 when the rule cannot allow anonymous access.

### Logging interceptor

```python
@api.use(on='request')
async def log_requests(tx: TX) -> TX:
    logger.info(f"{tx.name} -> {tx.target} from user={tx.meta.get('user', {}).get('email')}")
    return tx
```

### TX enrichment

```python
def add_trace_id(tx: TX) -> TX:
    tx.meta['trace_id'] = uuid4().hex
    return tx

actor.use(add_trace_id, on='inbox')
```

## Gotchas

- **Interceptors are per-actor, not global.** There is no "register on all actors" mechanism. Register on the specific actor or class where interception is needed.
- **Class interceptors leak to all instances of that class.** If you register on `MyActor` (the class), every instance of `MyActor` will run those interceptors. This is by design but can cause unexpected behavior if registering during tests without cleanup.
- **`_run_interceptors` does not catch exceptions.** If an interceptor raises, the exception propagates up. Interceptors should catch their own errors and return `tx.error(...)` instead.
- **`on='request'` only works on NetworkAdapter subclasses.** The `request()` method is defined on `NetworkAdapter`, not `Actor`. Regular actors only support `inbox` and `send`.
- **`use()` with a non-callable argument raises `TypeError`.** The error message is: "Expected callable or None, got {type}".
- **Each subclass gets its own `__interceptors__` dict** (set by `ActorMeta.__new__`). Interceptors registered on a parent class are NOT inherited by subclasses. Register on each class independently.
