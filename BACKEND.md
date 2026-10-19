# N3TX Backend Navigation

Read [AGENTS.md](AGENTS.md) and [README](README.md) first. This page maps backend
work to canonical guides and implementation owners; it does not duplicate their
signatures, route tables or examples.

## Contract Map

| Concern | Canonical guide | Implementation owner |
|---|---|---|
| Models and serialization | [Models](docs/MODELS.md) | `packages/n3tx-core/src/n3tx_core/models/` |
| Schema extensions and cache | [Schema pipeline](packages/n3tx-core/docs/schema-pipeline.md) | Core `models/proto_schema.py`, `models/proto_dump.py` |
| Storage, local relationships and migrations | [Storage](packages/n3tx-core/docs/storage.md), [JSON fields](docs/JSON_FIELDS.md) | Core `storage/`, `models/storable_mixin.py`, `models/ref.py` |
| Factory, builder and optional packages | [Bootstrap](packages/n3tx-core/docs/app-bootstrap.md) | Core `app.py`, `utils/registrar.py` |
| CRUD and partial updates | [CRUD](docs/API_CRUD_ENDPOINTS.md) | Core `api/routes_fastapi.py` |
| Domain methods, caller injection and SSE | [Custom endpoints](docs/API_CUSTOM_ENDPOINTS.md) | Core `utils/decorators.py`, `api/routes_fastapi.py` |
| Authentication and authorization | [Enforcement](docs/AUTHORIZATION.md), [rule API](packages/n3tx-core/docs/authorization.md) | Core `authorize/`, `models/base_user.py`, `api/backend.py` |
| Actor dispatch and lifecycle | [Actor model](packages/n3tx-actors/docs/actor-model.md), [messaging](packages/n3tx-actors/docs/actor-messaging.md) | `packages/n3tx-actors/src/n3tx_actors/` |
| Adapters, remote refs and stream correlation | [Network adapters](packages/n3tx-actors/docs/network-adapters.md), [interceptors](packages/n3tx-actors/docs/interceptors.md) | Actor package `api/`, `remote_proxy.py` |
| Model reasoning and stored agents | [Agents](docs/AGENTS.md), [mixin](packages/n3tx-agents/docs/mixin.md), [tools](packages/n3tx-agents/docs/tool-discovery.md) | `packages/n3tx-agents/src/n3tx_agents/{mixin,actor,agent,tools}.py` |
| File metadata, bytes and materialization | [Files](packages/n3tx-files/docs/file.md) | `packages/n3tx-files/src/n3tx_files/` |
| View hooks and widget hints | [ViewableMixin](packages/n3tx-ui/docs/viewable-mixin.md), [widgets](packages/n3tx-ui/docs/widgets.md) | UI `mixin.py`, core `widgets/` |

## Before Changing A Contract

Trace declaration -> registration -> schema -> dispatch -> storage -> response.
Check both successful and denied/invalid calls through the actual enabled route.
For cross-stack changes also read [FRONTEND.md](FRONTEND.md).

- Ordinary field edits use CRUD. Domain actions may coordinate work but require
  their own concurrency/transaction design; a method name does not supply it.
- Local `T`/`list[T]` relationships and URL `Ref[T]` pointers differ. The first
  storage-mixin injection can rewrite bare scalar annotations; consult the model
  guide before assuming scalar behavior. Do not revive generated joins or ListRef.
- Constructor choice and transport choice are independent. Do not describe actor
  routing as a third bootstrap level or promise HTTP/raw-TX permission parity.
- Model/schema hints do not prove authorization. Verify list SQL filters, resource
  checks, reserved caller injection and tool execution separately.
- Agent policy and runtime belong to `mixin.py`, `actor.py` and `agent.py`;
  `AgentDeps` is in `agent.py`, not a separate `deps.py` module.
- File privacy is not established by a descriptive `public` field. Typed argument
  materialization, download policy and byte-store lifecycle have separate limits.
- Stream event vocabulary differs from transport completion. Cancellation and
  durable delivery guarantees must be demonstrated, not inferred from SSE/TX.

Use the portable test workflow in [AGENTS.md](AGENTS.md) and the environment,
debug/auth, CORS and migration cautions in [operations](docs/OPERATIONS.md).
