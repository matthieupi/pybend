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
     |                         methods → defs → access → widget → ui → [viewable] → [agent] → metadata)
     |                         [ ] = registered by external packages at import time
     +-- model_dump()          Plain dict (DB). model_response() runs base → relationships →
     |                         schema_url → instance_url → populate
     +-- __init_subclass__()   Auto-injects StorableMixin for __storable__=True models;
     |                         loops _mixin_registry for external mixins (ViewableMixin, AgentMixin)
     +-- register_mixin()      Module-level API — external packages register mixins at import time
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
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py` - Base model, `model_response()`, local relationship hydration, `register_mixin()`. Schema orchestrator (`schema()` calls `proto_schema.*` pipeline)
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py` - Schema pipeline: 7 core stages + external extensions. Extensible via `@schema_extension` and `register_mixin()`.
- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py` - Dump pipeline for serialization. Extensible via `@dump_extension` decorator.
- `packages/n3tx-core/src/n3tx_core/models/base_user.py` - Abstract base user with `login()` and `register_user()` endpoints
- `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py` - CRUD operations. `list()` supports `limit`/`offset` pagination.
- `packages/n3tx-core/src/n3tx_core/models/ref.py` - Canonical HTTP(S) `Ref[T]` value and URL-part helpers
- `packages/n3tx-core/src/n3tx_core/utils/typer.py` - Compatibility re-export for historical `Ref`, `_SelfRefMarker`, and `flatten_refs()` imports

### Storage (n3tx-core)
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` - SQLite backend with Ref hydration, JSON/list field serialization (`_coerce_value()` + `_deserialize_json_fields()`)
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py` - Auto-migration + Rails-style manual migrations
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py` - `get_json_fields()`, `get_fk_list_fields()`, `get_ref_fields()`, `get_ref_list_fields()`

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
- `packages/n3tx-core/src/n3tx_core/utils/registrar.py` - `registered_models` registry and model registration helpers

### Network Adapters (n3tx-actors)
- `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py` - `NetworkAdapter(Actor)` base class. `request()` for req/resp correlation, `stream()` for multi-reply streaming.
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` - `NetworkAPI`: HTTP REST bridge for Level 3 actor routing. `create_api_routes()` generates FastAPI routes.
- `packages/n3tx-actors/src/n3tx_actors/api/remote_matrix.py` - `RemoteMatrix`: direct HTTP(S) REST adapter and `MatrixReferenceResolver` for explicit storage populate.
- `packages/n3tx-actors/src/n3tx_actors/remote_proxy.py` - `RemoteRef`: explicit HTTP(S) remote handle returned by `ActorModel.ref()`.
- `packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py` - Tier 1 auth interceptor. `async (TX) -> TX` function.
- `packages/n3tx-actors/src/n3tx_actors/api/network_ws.py` - `NetworkWebSocket`: WebSocket bridge for frontend Matrix.
- `packages/n3tx-actors/src/n3tx_actors/api/network_mcp.py` - `NetworkMCP`: MCP JSON-RPC 2.0 bridge.
- `packages/n3tx-actors/src/n3tx_actors/api/network_ap.py` - `NetworkAP`: ActivityPub federation bridge.

### Widgets (n3tx-core)
- `packages/n3tx-core/src/n3tx_core/widgets/widget.py` - `Widget` base class, `WidgetMeta`, built-in field types, auto-detection registry
- `packages/n3tx-core/src/n3tx_core/widgets/schema_ext.py` - Schema pipeline stage (`@schema_extension(before='ui')`)

### App Bootstrap (n3tx-core)
 - `packages/n3tx-core/src/n3tx_core/app.py` - `N3TXApp` builder + `create_app()` factory. Supports `routing='direct'` and `routing='actor'`. In actor mode, re-syncs Matrix children to the finalized registered actor model classes after storage registration.
- `packages/n3tx-core/src/n3tx_core/__init__.py` - Public API re-exports
- `packages/n3tx-core/src/n3tx_core/config.py` - HOST, PORT, API_URL, SQLITE_DB_FILE, AGENT_DEFAULTS, SERVICE_NAME, SERVICE_TOKEN, REMOTES

### Agents (n3tx-agents)
- `packages/n3tx-agents/src/n3tx_agents/mixin.py` - AgentMixin: `ctx()`, `tools()`, `agentic()`, `run()`, streaming variants
- `packages/n3tx-agents/src/n3tx_agents/actor.py` - AgentActor: concrete model, instances ARE agents
- `packages/n3tx-agents/src/n3tx_agents/deps.py` - `AgentDeps` dataclass for Pydantic AI
- `packages/n3tx-agents/src/n3tx_agents/tools.py` - Tool discovery + function generation
- `packages/n3tx-agents/src/n3tx_agents/schema_ext.py` - Schema extension for `__agent__` models
- `packages/n3tx-agents/src/n3tx_agents/__init__.py` - Calls `register_mixin('__agent__', AgentMixin)` **before** importing AgentActor (import ordering requirement)

### Files (n3tx-files)
- `packages/n3tx-files/src/n3tx_files/file.py` - `File(ActorModel)` metadata resource; bytes live in a `FileStore`
- `packages/n3tx-files/src/n3tx_files/store.py` - `FileStore` protocol and `LocalFileStore` filesystem byte provider
- `packages/n3tx-files/src/n3tx_files/address.py` - Canonical local File `$id` validation and id extraction
- `packages/n3tx-files/src/n3tx_files/materialize.py` - Registers `File`-typed method argument materialization when `n3tx_files` is imported
- `packages/n3tx-files/src/n3tx_files/routes.py` - Package-local multipart upload and binary/range download adapters
- `packages/n3tx-files/src/n3tx_files/config.py` - File package configuration such as `N3TX_FILE_STORE_DIR`
- `packages/n3tx-files/docs/file.md` - File capability architecture and guardrails

### UI Mixin (n3tx-ui)
- `packages/n3tx-ui/src/n3tx_ui/mixin.py` - `ViewableMixin` + `viewable` schema stage. Registers `__viewable__`/`__ui__` triggers via `register_mixin()`. **Must be imported before model files with `__ui__`.**

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

### Local Model Collections
```python
class Product(ProtoModel):
    comments: list[Comment] = Field(default=[])
```

`list[T]` stores an ordered JSON list of local child ids on the parent row and
hydrates those ids into self-describing child objects in responses. Use custom
methods such as `Product.comment(...)` for domain-specific append/toggle actions.
For shared relationships, prefer an explicit link model; `ManyToMany[T]` remains
a legacy helper for existing shared-link use cases.

### Custom Method Return Types
`@expose_route` methods may return any import-resolvable model type, including a
different `ProtoModel` than the route owner. With `from __future__ import
annotations`, route registration resolves return annotations through
`typing.get_type_hints()` before passing them to FastAPI's `response_model`, so
patterns such as `Product.comment(...) -> Comment` remain valid and validated.

### Custom Method Scope

`@expose_route` method scope is descriptor-aware and published in schema as both
`scope` and `requires_instance`. Route generation, actor dispatch, tool
discovery, and remote streaming should use `requires_instance` for routing
decisions:

| Python declaration | Schema `scope` | `requires_instance` | Route shape |
|---|---|---:|---|
| `def action(self, ...)` | `instancemethod` | `true` | `POST /{ClassName}/{id}/{route}` |
| `@classmethod def action(cls, ...)` | `classmethod` | `false` | `POST /{ClassName}/{route}` |
| `@staticmethod def action(...)` | `staticmethod` | `false` | `POST /{ClassName}/{route}` |
| `def action(...)` with no `self`/`cls` | `actormethod` | `false` | `POST /{ClassName}/{route}` |

For decorator order, prefer the normal Python descriptor shape:

```python
@staticmethod
@expose_route('/upload-to-splat', methods=['POST'], stream=True)
async def upload_to_splat(...):
    ...

@classmethod
@expose_route('/rebuild', methods=['POST'])
def rebuild(cls):
    ...
```

The schema-declared route path is authoritative for distributed calls. For
example, `RemoteMatrix.stream()` resolves `POST /ComputePipeline/upload-to-splat`
from schema metadata instead of synthesizing `/ComputePipeline/0/upload_to_splat`
when `requires_instance` is false.

### API Response Format
All entity responses include `$schema` (schema URL) and `$id` (instance URL), injected by `model_response()` via the dump pipeline.

### Route Grammar and Hypermedia View Entrypoints

N3TX exposes an additive dual route grammar. Table-name routes remain the
compatibility JSON API; class-name routes provide schema, read mirrors, and
HTML/view entrypoints.

| Route | Layer | Response | Notes |
|---|---|---|---|
| `GET /{ClassName}` | schema/type | JSON Schema | Existing schema endpoint |
| `GET /{tablename}` | data API | JSON list | Existing table-name API |
| `POST /{tablename}` | data API | JSON entity | Existing create route |
| `GET /{tablename}/{id:int}` | data API | JSON entity | Existing canonical read route |
| `PUT /{tablename}/{id:int}` | data API | JSON entity | Existing update route |
| `DELETE /{tablename}/{id:int}` | data API | JSON status/payload | Existing delete route |
| `POST /{tablename}/{id:int}/{method}` | method API | JSON/SSE | Existing `@expose_route` instance methods |
| `GET /{ClassName}/_` | class-name mirror | JSON list | Explicit `_` collection marker |
| `POST /{ClassName}` | class-name mirror | JSON entity | Create mirror; `GET /{ClassName}` stays schema |
| `GET /{ClassName}/{id:int}` | class-name mirror | JSON entity | Read mirror of table-name read |
| `PUT /{ClassName}/{id:int}` | class-name mirror | JSON entity | Update mirror |
| `DELETE /{ClassName}/{id:int}` | class-name mirror | JSON status/payload | Delete mirror |
| `POST /{ClassName}/{id:int}/{method}` | class-name mirror | JSON/SSE | Literal `@expose_route` method mirror |
| `GET /{ClassName}/@` | view/html | HTML | Collection default view shell |
| `GET /{ClassName}/@{view}` | view/html | HTML | Collection named view shell |
| `GET /{ClassName}/{id:int}/@` | view/html | HTML | Member default view shell |
| `GET /{ClassName}/{id:int}/@{view}` | view/html | HTML | Member named view shell |

The class-name JSON mirrors intentionally reuse the same handlers as the
table-name routes in direct FastAPI routing. `GET /{ClassName}` remains schema;
`GET /{ClassName}/_` is the explicit JSON collection marker. Actor routing
dispatches equivalent TXs to the table-name actor address. In both modes, auth,
population query parameters, missing-record behavior, and serialization stay
aligned with the table-name route.

Response identity is class-name based: a response fetched through either
`GET /products/1` or `GET /Product/1` has `$schema` ending in `/Product` and
`$id` ending in `/Product/1`. Method mirrors are registered only for literal
`@expose_route` declarations; there is no generic class-name method catch-all.

#### Partial update contract

Generated `PUT /{tablename}/{id}` and `PUT /{ClassName}/{id}` handlers in direct
and actor routing preserve the supplied JSON patch. `StorableMixin.update()`
merges it with the current entity, validates the complete result through the
original model, and sends only supplied fields to storage. This is the same
contract used by direct backend calls and raw TX updates:

```python
Product.update(product.id, {'name': 'Renamed'})  # patch; other fields unchanged
TX(name='update', target='products', data={'id': product.id, 'name': 'Renamed'})
```

Omitted fields remain unchanged. Supplied collections are replaced as a whole
and writes are last-write-wins; use domain-specific `@expose_route` methods for
append/remove/toggle operations where concurrent mutation matters.
Canonical details: `docs/API_CRUD_ENDPOINTS.md#update-resource` and
`packages/n3tx-core/docs/storage.md#update-boundary-contract`.

Local owned collections are declared as `list[T]` fields on the parent. SQLite
stores an ordered JSON list of child ids and hydrates those ids into
self-describing child objects on read. Public child identity remains flat and
class-name based, e.g. `$id=/Comment/2`; nested route identity is not a storage
primitive. If a parent has multiple relationships to the same child class, for
example `comments: list[Comment]` and `reviews: list[Comment]`, the relationship
field name remains local schema/UI metadata on the parent while the child model
continues to own its flat CRUD route and identity.

HTML/view routes are owned by optional model capability hooks such as
`ViewableMixin.register_view_routes()` from `n3tx-ui`. Core and actor routing
delegate to that hook when present, so the core and actors packages do not
hard-import UI code. View routes are hidden from OpenAPI and return a minimal
HTML shell that mounts the normal frontend custom element runtime; they are not
a separate server-side component renderer. The `@` segment always means
view/html, never JSON data or method invocation.

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

### Distributed Ref Configuration

Distributed backend-to-backend reference helpers read process config by default:

```text
N3TX_SERVICE_NAME=api
N3TX_SERVICE_TOKEN=...
N3TX_REMOTES={"storage":{"url":"http://storage:7100","token":"..."}}
```

Apps can override deployment defaults during bootstrap:

```python
app = create_app(
    models=[Job],
    routing='actor',
    remotes={'storage': {'url': 'http://storage:7100', 'token': '...'}},
    service_name='api',
    service_token='...',
)
```

`Ref[T]` accepts local ids, local class-name paths such as `/File/12`, current
API URLs, configured remote HTTP URLs, and canonical `n3tx://service/Class/id`
refs. Configured remote HTTP refs canonicalize to `n3tx://...`; unconfigured
HTTP(S) URLs are external links, not Matrix refs.

Remote dereference/populate is opt-in. `SQLiteStorage(reference_resolver=None)`
preserves local-only behavior. Actor routing with configured `remotes` registers
`RemoteMatrix` and injects `MatrixReferenceResolver` into compatible storage
backends. For explicit Python calls to a remote model identity, use:

```python
artifact = Artifact.ref('n3tx://storage/Artifact/42')
result = await artifact.call('process', mode='fast')
```

`RemoteMatrix` sends `Authorization: Bearer <token>`, `X-N3TX-Service`, and
optional `X-N3TX-User` headers. A receiving N3TX backend accepts service calls
when the bearer token matches its configured `SERVICE_TOKEN`; forwarded user JSON
is installed as `request.state.user` so existing route and ActorModel ABAC
behavior remains authoritative. Remote HTTP `$id` values are canonicalized back
to `n3tx://service/Class/id` before returning through Matrix/populate.

### JSON Fields (dict/list in SQLite)
The storage layer transparently handles `dict`, `Dict[...]`, `list`, primitive
typed list fields, local owned `list[T]` id arrays, and `list[Ref[T]]` pointer
arrays as JSON TEXT columns. Write paths serialize with `json.dumps(value,
default=str)`; read paths deserialize with `json.loads()` before Pydantic model
construction and hydrate local `list[T]` ids into objects.

Use JSON fields for parent-owned embedded data such as metadata, settings,
agent constraints, primitive tags, external payload fragments, distributed
pointer arrays, and local owned relationship id lists. Model children that need
independent auth, lifecycle, or row-level updates as first-class storable models
and point to them from parent `list[T]` fields.

Full guide: `docs/JSON_FIELDS.md`. Package mechanism reference:
`packages/n3tx-core/docs/storage.md`.

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

#### Schema-Declared Stream Events (`events=`)

Streaming methods can declare their event vocabulary via the `events=` parameter. Event types are non-storable `ProtoModel` subclasses — pure Pydantic models for validation and JSON Schema generation:

```python
class TextChunk(ProtoModel):
    text: str = Field(default='')

class DoneChunk(ProtoModel):
    answer: str = Field(default='')
    usage: dict = Field(default={})

@expose_route('/agentic_stream', methods=['POST'], stream=True,
              events={'text': TextChunk, 'done': DoneChunk})
async def agentic_stream(self, task: str, **kwargs):
    yield {'name': 'text', 'data': {'text': 'hello'}, 'meta': {'stream': True, 'seq': 0}}
```

The `methods` stage in `proto_model.py` serializes `events` into the method schema:

```json
{
  "methods": {
    "agentic_stream": {
      "stream": true,
      "events": {
        "text": {"type": "object", "properties": {"text": {"type": "string"}}},
        "done": {"type": "object", "properties": {"answer": {...}, "usage": {...}}}
      }
    }
  }
}
```

The `n3tx-agents` package ships five built-in event models in `actor.py`: `TextChunk`, `ToolCallEvent`, `ToolResultEvent`, `ThinkingChunk`, `DoneChunk`. These are used by `AgentActor.agentic_stream()`. Custom streaming methods can define their own event models.

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
