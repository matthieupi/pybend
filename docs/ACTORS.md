# Actors, TX, and Matrix

Actors add message dispatch to N3TX models. They do not replace model schemas,
storage, or exposed domain actions, and are not a durable queue or scheduler.

## Three independent decisions

| Decision | Choices | Meaning |
|---|---|---|
| Application construction | `create_app`, `N3TXApp`, raw primitives | How registration and configuration are assembled |
| Model capability | ProtoModel or ActorModel | Whether the model also participates in actor messaging |
| HTTP routing | `routing='direct'` or `'actor'` | Direct model invocation or NetworkAPI/TX dispatch |

ActorModel can use direct HTTP routes while still serving internal TX calls.
Both factory and builder can select actor routing. Avoid “level 3” as a synonym
for either manual construction or actor routing: they are different choices.

```text
Direct HTTP -> generated route ---------------------> model/storage
Actor HTTP  -> NetworkAPI -> TX -> Matrix -> ActorModel -> model/storage
Internal caller -----------------> Matrix -----^
                                      |
                                outbound adapter
```

## Primitives

| Primitive | Responsibility |
|---|---|
| `TX` | Mutable dataclass envelope: name, source, target, data, meta, timestamp, uuid |
| `Actor` | Named handler dispatch and class/instance routing state |
| `Matrix` | Root child lookup, adapter selection, request/stream correlation |
| `ActorModel` | Actor + ProtoModel; adapts CRUD and exposed methods |
| `ActorProxy` | Wraps a local object/class without Actor inheritance |
| `RemoteRef` | Explicit async handle for an HTTP(S) model identity; not a local proxy |

Model fields and `@expose_route` signatures remain authoritative. Use ordinary
CRUD for field changes and exposed methods for domain operations; do not add a
second command schema merely to use actors.

## Runnable local messaging example

Prerequisites: Python 3.10+ and installed `n3tx-actors` (which depends on core).
Run as a script in a fresh process. No storage, HTTP server, credentials or
external service is required.

```python
import asyncio
from n3tx_actors import Actor, Matrix, TX

async def main():
    root = Matrix(addr='demo')

    class Worker(Actor, auto_register=False):
        def DOUBLE(self, data, tx):
            return {'value': data['value'] * 2}

    root.register(Worker(addr='worker'))
    response = await root.request(TX(
        name='DOUBLE', source=root.addr, target='worker', data={'value': 21},
    ))
    assert not response.is_error, response.data
    assert response.data == {'value': 42}
    print(response.data)

asyncio.run(main())
```

This explicitly registered instance uses its parent Matrix. Constructing another
Matrix does not replace an existing `Actor.root()`; class auto-registration and
agent runtime use that process-wide root. For an isolated class-based tree, set
`Actor.root(root)` before class declarations and restore it after tests.

## Trust boundaries

Actor routing is not automatically equivalent to HTTP authorization. The
generated actor HTTP path installs a boundary interceptor with model/caller
metadata. Internal Matrix calls bypass that interceptor; ActorModel treats
`meta.user=None` as trusted internal execution. List authorization depends on a
boundary-computed SQL filter. Plain Actor handlers are not restricted to exposed
model methods.

Do not pass arbitrary client TXs into Matrix as trusted messages. Validate caller,
allowed target/action and metadata at each enabled protocol boundary. See
[ActorModel enforcement](../packages/n3tx-actors/docs/actor-model.md) and
[adapter limits](../packages/n3tx-actors/docs/network-adapters.md).

No blanket parity is promised across direct HTTP, actor HTTP, raw TX, WebSocket,
MCP, ActivityPub or agent tools. Test actual payloads, authorization, errors and
cancellation on the paths the application exposes.

## Reference map

| Guide | Detail |
|---|---|
| [Package](../packages/n3tx-actors/README.md) | Dependencies and integration choice |
| [Messaging](../packages/n3tx-actors/docs/actor-messaging.md) | TX, dispatch, addresses, proxy and correlation |
| [ActorModel](../packages/n3tx-actors/docs/actor-model.md) | CRUD, methods, auth and lifecycle events |
| [Interceptors](../packages/n3tx-actors/docs/interceptors.md) | Registration, ordering and rejection behavior |
| [Adapters](../packages/n3tx-actors/docs/network-adapters.md) | HTTP, WS, MCP, AP and remote HTTP refs |
| [Agents](AGENTS.md) | Optional reasoning over actor tools |
