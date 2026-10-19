# N3TX Python API Reference

This is a symbol/navigation map, not a second copy of every package API. Use
package-qualified imports. For HTTP behavior, see [API index](API_INDEX.md).

## Models

### ProtoModel

`n3tx_core.models.proto_model.ProtoModel`: fields, validation, `schema()`,
`referenced_json_schema()`, `blueprint()`, `invalidate_schema_cache()` and
`model_response()`. [Model contract](MODELS.md#protomodel).

### StorableMixin

`n3tx_core.models.storable_mixin.StorableMixin`: injected by `__storable__`.
Create expects a model instance; update accepts a patch and validates merged
state. [Operations and signatures](MODELS.md#storablemixin),
[storage boundary](../packages/n3tx-core/docs/storage.md#update-boundary-contract).

### BaseUser

`n3tx_core.models.base_user.BaseUser`: inherit registration/login, hashing and
identity fields. [Configuration and security limits](MODELS.md#baseuser).

### ViewableMixin

`n3tx_ui.mixin.ViewableMixin`, not core: UI schema metadata and HTML shell route
hooks. [UI reference](../packages/n3tx-ui/docs/viewable-mixin.md).

## Storage

### AbstractStorage

`n3tx_core.storage.abstract_storage.AbstractStorage`: create_table/create/list/get/
update/delete interface. Implement the complete current signatures including
filter, pagination and populate arguments. [Storage API](../packages/n3tx-core/docs/storage.md).

### SQLiteStorage

`n3tx_core.storage.sqlite_storage.SQLiteStorage(database='database.db',
pool_size=4, reference_resolver=None)`: file-backed SQLite, JSON serialization,
local hydration, optional explicit ref population and migrations.
[Limits and migration behavior](../packages/n3tx-core/docs/storage.md).

### JSONStorage

`n3tx_core.storage.json_storage.JSONStorage` is a legacy implementation. It
implements `get_all`/`get_by_id`, not AbstractStorage's current `list`/`get`, and
cannot be instantiated as a complete concrete backend in this checkout. It is
not a supported drop-in tutorial alternative. No PostgreSQL backend is implied.

## Types

### Ref

`n3tx_core.models.ref.Ref`: immutable HTTP(S) identity URL with base_url/schema/id
helpers and explicit hydrate. `n3tx_core.utils.typer` is a compatibility re-export.
[Local versus URL contract](MODELS.md#references).

## Decorators

### expose_route

`n3tx_core.utils.decorators.expose_route(route, methods=['POST'], access=None,
stream=False, events=None)`. [Scope, parsing, caller and errors](API_CUSTOM_ENDPOINTS.md).

Schema and dump extension decorators live in `models.proto_schema` and
`models.proto_dump`, respectively. [Extension reference](../packages/n3tx-core/docs/schema-pipeline.md).

## Agents

### AgentMixin

`n3tx_agents.AgentMixin`: policy-level `agentic`/`agentic_stream` and lower-level
runtime `run`/`run_stream`, plus context/tool discovery. Import agents before
declaring `__agent__`. [Mixin API](../packages/n3tx-agents/docs/mixin.md).

### AgentActor

`n3tx_agents.AgentActor`: data-backed agent configuration. Its exposed execution
method is `/agentic`, not historical `/run`. [AgentActor reference](../packages/n3tx-agents/docs/agent-actor.md).

### AgentDeps and ToolSpec

Use the [tool-discovery reference](../packages/n3tx-agents/docs/tool-discovery.md)
for current dependency context, explicit addresses and generated tool behavior;
do not copy the obsolete adapter-bearing AgentDeps shape from older snapshots.

## Files (optional n3tx-files)

### File

`n3tx_files.File`: metadata resource, canonical local identity resolution and
typed argument materialization. Fields include filename, content_type, size,
sha256, storage_key, user_owner, origin, public and meta.

### LocalFileStore

`n3tx_files.LocalFileStore`: byte provider with put_stream, open_stream, stat and
delete. `configure_file_store` selects the provider. See the
[File guide](../packages/n3tx-files/docs/file.md) for exact async signatures,
range semantics, authorization and byte/metadata lifecycle. Bytes are not SQL rows.

## Backends

### FastAPIBackend

`n3tx_core.api.backend.FastAPIBackend`: HTTP app, identity middleware, CORS and
merged static serving. Prefer `n3tx_core.app.create_app` or N3TXApp for ordinary
local apps. [Bootstrap reference](../packages/n3tx-core/docs/app-bootstrap.md)
documents raw setup and the factory's current CORS forwarding gap.

### FlaskBackend

Legacy adapter in `api.backend`; not selected by create_app and not verified for
current FastAPI feature parity. Flask dependencies are optional. Do not switch
backends expecting unchanged auth, streaming and model view behavior.

## Utilities

`n3tx_core.utils.registrar.register_model` prepares/applies storage registration;
`registered_models` maps table names to classes. Registration may migrate tables.
`n3tx_core.utils.erroring.MethodError(message, status_code=400)` expresses a
domain HTTP error through native routing. `get_traceback_info` extracts structured
trace frames for debugging; those details are not safe public error content.

## Configuration

Set environment before import; use [Operations](OPERATIONS.md) for actual
defaults and limitations rather than editing installed framework config files.
