# N3TX Backend Reference

This document contains backend-specific key files, architecture details, and patterns. It supplements the main `CLAUDE.md` which contains cross-cutting architecture, the multi-package structure, and all directives.

**Before reading this file**, check the documentation in `/workspace/docs/` and per-package `docs/` directories first. See `CLAUDE.md` → "Documentation-First Context Loading" for the required order.

Relevant docs:
- `/workspace/docs/CORE.md` — Schema-driven development, model patterns
- `/workspace/docs/MODELS.md` — Model layer, pipelines, StorableMixin
- `/workspace/docs/ACTORS.md` — Actor system, TX messaging
- `/workspace/docs/AGENTS.md` — LLM integration, tool discovery
- `/workspace/docs/AUTHORIZATION.md` — Full authorization system
- `packages/n3tx-core/docs/` — app-bootstrap, authorization, schema-pipeline, storage
- `packages/n3tx-actors/docs/` — actor-messaging, actor-model, interceptors, network-adapters
- `packages/n3tx-agents/docs/` — mixin, agent-actor, tool-discovery

## Backend Architecture Detail

```
models/*.py          Define data models (extend ProtoModel / BaseUser / ActorModel)
     |
     v
ProtoModel           Base class: injects StorableMixin, rewrites FK fields,
(n3tx-core)          orchestrates schema pipeline, handles serialization
     |
     +-- schema()              Orchestrates proto_schema.* pipeline (base → strip_hidden →
     |                         methods → defs → access → widget → ui → metadata)
     +-- model_dump()          Plain dict (DB). model_response() adds $schema/$id via dump pipeline
     +-- __init_subclass__()   Auto-injects StorableMixin for __storable__=True models
     |
     v
ActorModel           Bridge class (Actor + ProtoModel): models that participate
(n3tx-actors)        in actor messaging. CRUD via handler_crud(), lifecycle events,
                      same schema/storage as ProtoModel.
     |
     v
register_model()     Registers model with storage backend
     |
     v
register_routes()    Auto-generates CRUD routes from registered models (routes_fastapi.py)
     |
     v
FastAPI router       Serves schema at GET /{ClassName}, CRUD at /{tablename}/...

Interceptors         use() on any Actor — register TX interceptors on inbox/send/request
(n3tx-actors)        Signature: async (TX) -> TX. Return error TX to short-circuit.

NetworkAPI           Level 3: HTTP → TX → Matrix → ActorModel (full actor routing)
(n3tx-actors)        create_app(routing='actor') wires NetworkAPI + auth interceptor
                      Two-tier auth: Tier 1 (boundary gate) + Tier 2 (handler OWNER check)
```

## Key Files

### Models & Serialization (n3tx-core)
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py` - Base model, `model_response()`, `generate_join_model()`. Schema orchestrator (`schema()` calls `proto_schema.*` pipeline)
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py` - Schema pipeline: 8 composable stages. Extensible via `@schema_extension` decorator.
- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py` - Dump pipeline for serialization. Extensible via `@dump_extension` decorator.
- `packages/n3tx-core/src/n3tx_core/models/base_user.py` - Abstract base user with `login()` and `register_user()` endpoints
- `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py` - CRUD operations. `list()` supports `limit`/`offset` pagination.
- `packages/n3tx-core/src/n3tx_core/models/ref.py` - `ListRef[T]` type for collection references
- `packages/n3tx-core/src/n3tx_core/utils/typer.py` - `Ref` type (`Ref[T]`, `Ref['self']`), `flatten_refs()`

### Storage (n3tx-core)
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` - SQLite backend with FK hydration, JSON field serialization (`_coerce_value()` + `_deserialize_json_fields()`)
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py` - Auto-migration + Rails-style manual migrations
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_helpers.py` - `get_parent_fk_columns()` for auto FK column detection
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py` - `get_json_fields()`, `get_list_fields()`, `get_ref_fields()`, `_unwrap_listref()`

### Authorization & Authentication (n3tx-core)
- `packages/n3tx-core/src/n3tx_core/authorize/` - Standalone auth package (JWT + ABAC, zero N3TX imports)
- `packages/n3tx-core/src/n3tx_core/authorize/auth.py` - JWT: password hashing, token create/decode, `configure()`
- `packages/n3tx-core/src/n3tx_core/authorize/rules.py` - `AccessRule` base + built-ins (`ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`, `Where`)
- `packages/n3tx-core/src/n3tx_core/authorize/context.py` - `AccessContext` dataclass
- `packages/n3tx-core/src/n3tx_core/authorize/resolver.py` - `AuthorizationResolver` Protocol + `DefaultResolver`
- `packages/n3tx-core/src/n3tx_core/authorize/errors.py` - `AccessDenied` exception
- `packages/n3tx-core/src/n3tx_core/authorize/schema.py` - Serialize access rules to JSON

### API / Routes (n3tx-core)
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` - Level 1/2 route factories with authorization, pagination, and user resolution (`_resolve_user`)
- `packages/n3tx-core/src/n3tx_core/api/backend.py` - `FastAPIBackend`, static file serving, `_discover_static_dirs()` for multi-package static merge
- `packages/n3tx-core/src/n3tx_core/api/routes_flask.py` - Flask alternative
- `packages/n3tx-core/src/n3tx_core/api/discovery.py` - `/_meta`, `/.well-known/agent.json`
- `packages/n3tx-core/src/n3tx_core/utils/decorators.py` - `@expose_route()` for custom method endpoints
- `packages/n3tx-core/src/n3tx_core/utils/registrar.py` - `registered_models` dict, `join_models` dict

### Network Adapters (n3tx-actors)
- `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py` - `NetworkAdapter(Actor)` base class. `request()` for req/resp correlation, `stream()` for multi-reply streaming.
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` - `NetworkAPI`: HTTP REST bridge for Level 3 actor routing. `create_api_routes()` generates FastAPI routes.
- `packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py` - Tier 1 auth interceptor. `async (TX) -> TX` function.
- `packages/n3tx-actors/src/n3tx_actors/api/network_ws.py` - `NetworkWebSocket`: WebSocket bridge for frontend Matrix.
- `packages/n3tx-actors/src/n3tx_actors/api/network_mcp.py` - `NetworkMCP`: MCP JSON-RPC 2.0 bridge.
- `packages/n3tx-actors/src/n3tx_actors/api/network_ap.py` - `NetworkAP`: ActivityPub federation bridge.

### Widgets (n3tx-core)
- `packages/n3tx-core/src/n3tx_core/widgets/widget.py` - `Widget` base class, `WidgetMeta`, built-in field types, auto-detection registry
- `packages/n3tx-core/src/n3tx_core/widgets/schema_ext.py` - Schema pipeline stage (`@schema_extension(before='ui')`)

### App Bootstrap (n3tx-core)
- `packages/n3tx-core/src/n3tx_core/app.py` - `N3TXApp` builder + `create_app()` factory. Supports `routing='direct'` and `routing='actor'`.
- `packages/n3tx-core/src/n3tx_core/__init__.py` - Public API re-exports
- `packages/n3tx-core/src/n3tx_core/config.py` - HOST, PORT, API_URL, SQLITE_DB_FILE, AGENT_DEFAULTS

### Agents (n3tx-agents)
- `packages/n3tx-agents/src/n3tx_agents/mixin.py` - AgentMixin: `ctx()`, `tools()`, `agentic()`, `run()`, streaming variants
- `packages/n3tx-agents/src/n3tx_agents/actor.py` - AgentActor: concrete model, instances ARE agents
- `packages/n3tx-agents/src/n3tx_agents/deps.py` - `AgentDeps` dataclass for Pydantic AI
- `packages/n3tx-agents/src/n3tx_agents/tools.py` - Tool discovery + function generation
- `packages/n3tx-agents/src/n3tx_agents/schema_ext.py` - Schema extension for `__agent__` models

## Backend Patterns

### BaseUser Pattern
```python
from n3tx_core.models.base_user import BaseUser

class User(BaseUser):
    __tablename__ = 'users'
    __abstract__ = False
    image: Optional[str] = Field(default=None)
```
`BaseUser` provides: `name`, `email`, `role`, `password_hash`, plus `login()` and `register_user()` endpoints. The method was renamed from `register()` to `register_user()` to avoid MRO collision with `Actor.register()`.

### Parent-Child Relationships
```python
class Product(ProtoModel):
    comments: Optional[ListRef[Comment]] = Field(default=[])

register_model(generate_join_model(Product, Comment), storage=storage_backend)
```
Creates a `ProductComment` join model with auto-generated FK column. Routes become `/products/{parent_id}/comments/{id}`.

### API Response Format
All entity responses include `$schema` (schema URL) and `$id` (instance URL), injected by `model_response()` via the dump pipeline.

### Authorization (ABAC)
```python
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE, Where

class Product(ProtoModel):
    __owner_field__ = 'user_owner'
    __access__ = {
        'read':   ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }
```
Rules compose with `|` (OR), `&` (AND), `~` (NOT). See `packages/n3tx-core/docs/authorization.md` for full details.

### Self-Referential Nesting
```python
class Comment(ProtoModel):
    parent_id: Optional[Ref['self']] = Field(default=None)
```
`Ref['self']` emits `{"type": "selfref"}` in JSON Schema. Stored as nullable `INTEGER` column.

### JSON Fields (dict/list in SQLite)
The storage layer transparently handles `dict` and `list` fields as JSON TEXT columns. See `packages/n3tx-core/docs/storage.md` for the full mechanism.

### Dump Pipeline
```python
data = product.model_response()    # runs dump pipeline (injects $schema, $id)
data = product.model_dump()        # plain dict for storage (no metadata)
```

External packages extend via `@dump_extension`:
```python
from n3tx_core.models.proto_dump import dump_extension

@dump_extension(after='response')
def activity(instance, d: dict) -> dict:
    ...
```

### NetworkAdapter Pattern
ALL external protocol interaction flows through a `NetworkAdapter(Actor)`. Each adapter translates between an external protocol and TX messages. See `packages/n3tx-actors/docs/network-adapters.md`.

```python
from n3tx_actors.api.network_mcp import NetworkMCP, create_mcp_routes
from n3tx_actors.api.network_ap import NetworkAP, create_federation_routes

mcp = NetworkMCP(addr='mcp')
matrix.register(mcp)
app.include_router(create_mcp_routes(mcp))
```

### Widget Pattern (Python)
```python
from n3tx_core.widgets import MarkdownField, UrlField, CurrencyField

class BlogPost(ProtoModel):
    body: MarkdownField(rows=10)    # Annotated[str, MarkdownField(rows=10)]
    website: UrlField               # validates as AnyHttpUrl, widget=url
    price: CurrencyField            # validates as float, widget=currency
```

Three detection cases in the `widget` schema pipeline stage:
1. `Annotated[str, <MarkdownField instance>]` — from `MarkdownField(rows=10)` call
2. Bare `MarkdownField` class — `issubclass(annotation, Widget)`
3. Auto-detect: bare `AnyHttpUrl` → check `AUTO_DETECT_MAP`

### Streaming Infrastructure
For the full streaming mechanism, see `packages/n3tx-actors/docs/network-adapters.md` (adapter streaming) and `packages/n3tx-core/docs/app-bootstrap.md` (route-level streaming).

#### Defining a Streaming Method
```python
@expose_route('/generate', methods=['POST'], stream=True, access=AUTHENTICATED)
async def generate(self, prompt: str = ''):
    for i in range(10):
        await asyncio.sleep(0.1)
        yield {'chunk': f'Processing step {i}'}
```

#### TX Stream Protocol
TX uses `meta` fields for stream correlation:

| Message | `meta` fields |
|---------|--------------|
| Chunk | `req: uuid`, `stream: True`, `seq: N` |
| End | `req: uuid`, `stream: True`, `stream_end: True`, `seq: N` |
| Error | Existing `tx.error()` — `is_error` terminates the stream |

Helper methods: `tx.stream_chunk(data, seq)`, `tx.stream_end(data, seq)`.

#### SSE Wire Format
```
event: chunk|done|error
data: {json}\n\n
```
Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
