# n3tx-actors

Actor/TX/Matrix messaging, the ActorModel bridge, and protocol adapters for N3TX.
The backend package depends on `n3tx-core`; it does not require `n3tx-agents`.
See [dependency metadata](pyproject.toml) for supported versions.

Install `n3tx-actors` in your application environment (Python 3.10+), then run
the [local messaging example](../../docs/ACTORS.md#runnable-local-messaging-example).
It needs no database or server.

## Integration choice

| Need | Use |
|---|---|
| Schema/storage/HTTP only | Core ProtoModel and direct routes |
| Models callable through internal TX | ActorModel; direct HTTP remains an option |
| Generated HTTP requests traversing Matrix | ActorModel plus `routing='actor'` |
| Wrap a local non-model service | ActorProxy |
| Call an HTTP(S) model identity | ActorModel.ref / RemoteRef and RemoteMatrix |

Factory, builder and raw setup are construction APIs, not routing modes.
For application setup prefer core's
[bootstrap guide](../n3tx-core/docs/app-bootstrap.md); manual adapter wiring is
an advanced integration choice, not a prerequisite for ordinary actor HTTP.

```text
TX -> Matrix -> ActorModel -> native schema / CRUD / exposed method
        |
        +----> configured outbound adapter
```

## Reference

| Guide | Owns |
|---|---|
| [Messaging](docs/actor-messaging.md) | TX, Actor, Matrix, ActorProxy |
| [ActorModel](docs/actor-model.md) | CRUD/action dispatch and authorization boundaries |
| [Interceptors](docs/interceptors.md) | `use()` chains |
| [Adapters](docs/network-adapters.md) | Protocol-specific behavior and remote refs |

The package exports `Actor`, `TX`, `Matrix`, `matrix`, `ActorProxy`.
Import ActorModel from `n3tx_actors.models.actor_model` and adapters from their
`n3tx_actors.api` modules. The module-level Matrix supports class auto-registration,
but storage registration is still required for persistent model operations.

**Security:** Matrix is an internal trust boundary, not an authenticated ingress.
Missing caller context can bypass handler policy; list filters and method caller
injection differ by path. WS lifecycle broadcasts are not per-user filtered,
and stock MCP/AP ingress is not equivalent to generated HTTP authorization.
Review the adapter reference before enabling these protocols.
