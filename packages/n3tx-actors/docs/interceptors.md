# Interceptors

[Messaging](actor-messaging.md) · [Authorization boundaries](actor-model.md)

`actor.use(fn, on='inbox')` registers a synchronous or async TX-to-TX function.
It also supports decorator form. Return the incoming/transformed TX to continue,
or an error TX to reject. Exceptions are not caught by the chain runner.

```text
class chain (FIFO) -> instance chain (FIFO) -> intercepted operation
                        error -> short circuit
```

Each Actor subclass gets a fresh class interceptor dictionary; parent-class
registrations are not inherited by subclasses. Class registrations apply to
instances of that class. Chains are per actor, not global middleware.

## Interception points

| Owner / point | Error result |
|---|---|
| Actor `inbox` | Sends rejection back and skips handler |
| Actor `send` | Drops rejected outbound TX; no routing |
| NetworkAdapter `request` | Returns rejection directly before dispatch |
| NetworkAdapter `stream` | Uses the **request** chain; yields rejection then ends |
| Matrix `inbox` | Drops interceptor rejection; pending replies are correlated before interception |

Matrix's `request()` is its own implementation and does not run a NetworkAdapter
request chain. Matrix overrides send as well. Registering a function under an
arbitrary point name does not cause a method to invoke it.

## Runnable registration example

Prerequisites: installed `n3tx-actors`. This only constructs an adapter and
registers a policy function; it performs no requests or external IO.

```python
from n3tx_actors import TX
from n3tx_actors.api.network_api import NetworkAPI
from n3tx_actors.api.auth_interceptor import auth_interceptor

api = NetworkAPI()
api.use(auth_interceptor, on='request')

@api.use(on='request')
def require_trace(tx: TX) -> TX:
    if not tx.meta.get('trace_id'):
        return tx.error('trace_id required', code=400)
    return tx
```

To route calls, register the adapter with the intended Matrix and provide trusted
model/caller metadata. Prefer application bootstrap for standard actor HTTP
wiring; do not mount a second duplicate NetworkAPI router.

## Auth interceptor requirements

`auth_interceptor` requires `meta.model_cls`; without it, it passes through.
It reads the verified caller from `meta.user`, computes a list `sql_filter`,
checks create and class action rules, and defers resource-aware instance decisions
to ActorModel. Anonymous denials return 401; authenticated denials return 403.
Schemas pass through. Custom methods without explicit `access=` default to an
authenticated boundary check, not an inferred domain ownership rule.

This is why merely attaching it to MCP or a custom adapter is insufficient:
that ingress must supply trustworthy model/caller metadata and restrict dispatch.
Do not log full TX payloads or caller tokens in a diagnostic interceptor.

Source: [actor.py](../src/n3tx_actors/actor.py),
[network_adapter.py](../src/n3tx_actors/api/network_adapter.py),
[auth_interceptor.py](../src/n3tx_actors/api/auth_interceptor.py).
Tests: [test_interceptors.py](../src/n3tx_actors/tests/test_interceptors.py).
