# Messaging reference

[Concepts and runnable example](../../../docs/ACTORS.md) · [Interceptors](interceptors.md)

## TX envelope

TX is mutable, not a validated domain model. Its required fields are `name`,
`source`, `target`; `data` and `meta` default to separate empty dictionaries.
`timestamp` is epoch time and `uuid` defaults to a 12-character UUID hex prefix.
Although annotated `dict`, response data can contain other values.

| Method/property | Contract |
|---|---|
| `reply(data=None, name=None)` | New TX, swapped source/target, inherited metadata plus `req=original.uuid`; default name `<name>_RESPONSE` |
| `error(message, code=500)` | `ERROR`, `{message, code}`, correlated `meta.error=True` |
| `chunk(data, seq)` | `STREAM`, `meta.stream=True`, correlation and sequence; wraps non-dict data as `{chunk: data}` |
| `end(data=None, seq=0)` | `STREAM` with `stream_end=True` |
| `exception(e)` / `TX.from_exception(e, tx)` | Maps structured errors, validation 422, value/type/key 400, permission 403, fallback 500 |
| `is_error` | True for name `ERROR` or truthy `meta.error` |

`stream_chunk` and `stream_end` remain deprecated aliases for `chunk` and `end`.
Reusing a TX across concurrent sends is unsafe: routing can mutate its addresses.
Replies inherit metadata; do not put secrets in metadata assuming it stays local.

## Actor class and instance state

`fullmethod` / `fullproperty` from core descriptors bind to either class or
instance. They are not named `actormethod` / `actorproperty` in the current API.

| State | Class | Instance |
|---|---|---|
| Address | `__addr__` | `_addr` |
| Children | `__children__` | `_children` |
| Parent | `__matrix__` | `_parent` (initially the class) |
| Interceptors | `__interceptors__` | `_interceptors` |

ActorMeta gives every subclass fresh child/interceptor dictionaries. Class
address precedence is explicit `__addr__`, then `__tablename__`, then class name.
Instance precedence is nonempty `addr=`, then `<class addr>/<truthy id>`, then
class address. An address alone does not register an instance or load a DB row.

Auto-registration occurs at class definition against the current root; suppress
it with `class Worker(Actor, auto_register=False)`. The package creates a default
`matrix` at import time. `Matrix()` only becomes root if no root exists.
`register(child)` attaches a child; `spawn(addr, actor_cls, ...)` constructs and
registers, rejecting duplicate addresses. `has(addr)` checks the first segment.

## Dispatch and routing

```text
inbox -> inbox interceptors -> handler -> result wrapping -> send
                                                         |
                              class child / prefix / parent routing
                                                         |
                                    Matrix -> child or adapter
```

Plain Actor `handler()` calls the method named exactly by `tx.name` with
`(data, tx)`. Use classmethods for class actors, instance methods for instances.
ActorModel has different exposed-method dispatch; see [its reference](actor-model.md).

| Handler return | Plain Actor reply |
|---|---|
| TX | Sent unchanged |
| Dictionary | Reply data |
| Other non-None value | `{result: value}` |
| None | Empty reply, except one-way `LIFECYCLE` |
| Raised exception | Error TX |

An explicit `ERROR` handler runs for side effects only; its return is ignored.
Failures while handling an error are dropped. Unhandled errors and `*_RESPONSE`
messages are dropped to avoid reply loops; `ERROR_RESPONSE` is dropped by send.

Class `send()` tries a direct child, then strips its own address prefix for a
child match, otherwise prefixes the source and bubbles to its parent. Instance
`send()` delegates to its parent class's send or parent instance's inbox.
Plain Actor `inbox()` itself dispatches locally; it is not automatic DB instance
resolution. For ActorModel instance actions, target the table with `data.id`.

## Matrix correlation and HTTP aliases

Matrix handles pending `meta.req` correlations before routing/interceptors.
It translates explicitly registered HTTP origins to local model/table addresses,
then tries the target's first segment in children, then the first adapter whose
`can_handle(tx)` succeeds. Unroutable requests produce a 404 error when the
sender can be reached. Self-targets are logged and dropped.

`request(tx, timeout=30.0)` uses a Future; `stream(tx, timeout=120.0)` uses a Queue
and background send task. Stream timeout is per chunk; closing the generator
cleans the pending entry and cancels an unfinished send task. Request timeout
starts waiting **after** the inline send returns, so it is not a total execution
deadline. Always inspect `response.is_error`.

`matrix.add_alias('https://app.example')` accepts an origin only, not a path,
query or fragment. Actor-mode apps expose `app.add_alias(...)`. Aliases affect
local dispatch, not canonical `$id` generation or authorization.

## ActorProxy

`ActorProxy(target, addr='', parent=None)` wraps a local class/object. Explicit
address wins; classes fall back through `__addr__`, `__tablename__`, class name;
instances use `addr`, `_addr`, class name. It supplies `inbox/send`, children,
`register`, `spawn(target, addr='')`, and `has`, satisfying ActorLike.
It does not supply Actor's interceptor API or all its error-loop safeguards.
Register it with a parent before sending. Do not confuse it with RemoteRef.

## Tests and source

Implementation: [actor.py](../src/n3tx_actors/actor.py),
[matrix.py](../src/n3tx_actors/matrix.py), [tx.py](../src/n3tx_actors/tx.py),
[actor_proxy.py](../src/n3tx_actors/actor_proxy.py).
Tests live in [tests](../src/n3tx_actors/tests/), including routing, error-drop
and streaming-shutdown cases. Pydantic instance mocks may need
`object.__setattr__`; restore patched methods and the global root after tests.
