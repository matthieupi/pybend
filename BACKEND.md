# N3TX Backend Reference

This document contains backend-specific key files, architecture details, and patterns. It supplements the main `CLAUDE.md` which contains cross-cutting architecture, the actor system, custom methods, and all directives.

## Backend Architecture Detail

```
models/*.py          Define data models (extend ProtoModel / BaseUser / ActorModel)
     |
     v
ProtoModel           Base class: injects StorableMixin, rewrites FK fields,
                      orchestrates schema pipeline, handles serialization
     |
     +-- schema()              Orchestrates proto_schema.* pipeline (base → strip_hidden →
     |                         methods → defs → access → widget → ui → metadata)
     +-- model_dump()          Plain dict (DB). model_response() adds $schema/$id via dump pipeline
     +-- __init_subclass__()   Auto-injects StorableMixin for __storable__=True models
     |
     v
ActorModel           Bridge class (Actor + ProtoModel): models that participate
(optional)           in actor messaging. CRUD via handler_crud(), lifecycle events,
                      same schema/storage as ProtoModel. Use instead of ProtoModel
                      when actor capabilities (messaging, lifecycle events) are needed.
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
                      Signature: async (TX) -> TX. Return error TX to short-circuit.
                      Per-actor, not global. Class + instance chains combine.

NetworkAPI           Level 3: HTTP → TX → Matrix → ActorModel (full actor routing)
(routing='actor')    create_app(routing='actor') wires NetworkAPI + auth interceptor
                      Two-tier auth: Tier 1 (boundary gate) + Tier 2 (handler OWNER check)
```

## Key Files

### Models & Serialization
- `src/n3tx/core/models/proto_model.py` - Base model, `model_response()`, `generate_join_model()`. Schema orchestrator (`schema()` calls `proto_schema.*` pipeline)
- `src/n3tx/core/models/proto_schema.py` - Schema pipeline: 7 composable `dict → dict` stages (`base`, `strip_hidden`, `methods`, `defs`, `access`, `ui`, `metadata`). Extensible via `@schema_extension` decorator.
- `src/n3tx/core/models/proto_dump.py` - Dump pipeline: composable `dict → dict` stages for model serialization (`base`, `response`). Extensible via `@dump_extension` decorator. Powers `model_response()`.
- `src/n3tx/core/models/actor_model.py` - `ActorModel(Actor, ProtoModel)` bridge class. CRUD via `handler_crud()`, lifecycle event publishing, generic Actor handler fallback for custom methods.
- `src/n3tx/core/models/base_user.py` - Abstract base user model with `login()` and `register_user()` endpoints and password hashing
- `src/n3tx/core/models/storable_mixin.py` - CRUD operations (create/get/list/update/delete). `list()` supports `limit`/`offset` pagination.
- `src/n3tx/core/models/ref.py` - `ListRef[T]` type for collection references
- `src/n3tx/core/utils/typer.py` - `Ref` type (`Ref[T]`, `Ref['self']`), `flatten_refs()`

### Storage
- `src/n3tx/core/storage/sqlite_storage.py` - SQLite backend with FK hydration (converts ListRef fields to href arrays), JSON field serialization (`_coerce_value()` + `_deserialize_json_fields()`)
- `src/n3tx/core/storage/sqlite_migration.py` - Auto-migration + Rails-style manual migrations. Distinguishes ListRef/List[BaseModel] (FK join table) from bare list/dict (TEXT column).
- `src/n3tx/core/storage/sqlite_helpers.py` - `get_parent_fk_columns()` for auto FK column detection
- `src/n3tx/core/utils/introspection.py` - `get_json_fields()`, `get_list_fields()`, `get_ref_fields()`, `_unwrap_listref()` — type introspection for storage layer decisions

### Authorization & Authentication
- `src/n3tx/core/authorize/` - Standalone auth package (JWT + ABAC, zero N3TX imports). Configured via `authorize.configure()` in `main.py`
- `src/n3tx/core/authorize/auth.py` - JWT: password hashing, token create/decode, `configure()`
- `src/n3tx/core/authorize/rules.py` - `AccessRule` base class + built-in rules (`ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`, `Where`)
- `src/n3tx/core/authorize/context.py` - `AccessContext` dataclass (user, action, model, resource)
- `src/n3tx/core/authorize/resolver.py` - `AuthorizationResolver` Protocol + `DefaultResolver`
- `src/n3tx/core/authorize/errors.py` - `AccessDenied` exception
- `src/n3tx/core/authorize/schema.py` - Serialize access rules to JSON for schema exposure
- `src/n3tx/docs/AUTHORIZATION.md` - Full authorization system documentation

### API / Routes
- `src/n3tx/core/api/routes_fastapi.py` - Level 1/2 route factories with authorization injection, pagination, and user resolution bridge (`_resolve_user`). DO NOT MODIFY — Level 3 is additive.
- `src/n3tx/core/api/network_adapter.py` - `NetworkAdapter(Actor)` base class for protocol adapters. Provides `request()` for request/response correlation via asyncio.Future, `stream()` for multi-reply streaming via asyncio.Queue, `inbox()` override for correlation interception (handles both Future and Queue). All external protocol interaction flows through a NetworkAdapter.
- `src/n3tx/core/api/network_api.py` - `NetworkAPI` adapter: HTTP REST bridge for Level 3 actor routing. `create_api_routes()` generates FastAPI routes that translate HTTP to TX. Mirrors route paths from `routes_fastapi.py`.
- `src/n3tx/core/api/auth_interceptor.py` - Tier 1 auth interceptor for NetworkAPI. `async (TX) -> TX` function: AUTHENTICATED gate, sql_filter for list, full create check, identity gate for read/update/delete. Registered via `api.use(auth_interceptor, on='request')`.
- `src/n3tx/core/api/network_mcp.py` - `NetworkMCP` adapter: MCP JSON-RPC 2.0 bridge. `handle_tools_list()`, `handle_tools_call()`, `handle_jsonrpc()`. Converts model schemas to MCP tool specs. `create_mcp_routes()` FastAPI route factory.
- `src/n3tx/core/api/network_ap.py` - `NetworkAP` adapter: ActivityPub federation bridge. LIFECYCLE handler, actor documents, outbox, inbox, WebFinger, follow/unfollow. `create_federation_routes()` FastAPI route factory.
- `src/n3tx/core/api/network_ws.py` - `NetworkWebSocket` adapter: WebSocket bridge for frontend Matrix. Translates frontend TX (full URL targets, UPPERCASE names) to backend TX. Lifecycle event broadcast. `create_ws_routes()` FastAPI route factory.
- `src/n3tx/core/utils/decorators.py` - `@expose_route()` for custom method endpoints (supports `access=` and `stream=` parameters)
- `src/n3tx/core/utils/registrar.py` - `registered_models` dict, `join_models` dict

### Widgets (Python)
- `src/n3tx/core/widgets/widget.py` - `Widget` base class, `WidgetMeta` metaclass, built-in field types (Url, Email, Date, DateTime, Markdown, Console, Reference, Currency, Textarea), auto-detection registry
- `src/n3tx/core/widgets/schema_ext.py` - Schema pipeline stage (`@schema_extension(before='ui')`) — injects `ui.widget` + `ui.config` from Widget annotations
- `src/n3tx/core/widgets/__init__.py` - Package init, re-exports, triggers schema_ext registration

### App Bootstrap
- `src/n3tx/core/app.py` - `N3TXApp` builder class + `create_app()` one-liner factory. Supports `routing='direct'` (Level 1/2) and `routing='actor'` (Level 3 via NetworkAPI).
- `src/n3tx/__init__.py` - Public API: re-exports `create_app`, `N3TXApp`, `ProtoModel`, `BaseUser`, `expose_route`, `Actor`, `Matrix`, `TX`, `NetworkAdapter`, `NetworkAPI`, etc.

### Config & Entry
- `src/n3tx/core/config.py` - HOST, PORT, API_URL, SQLITE_DB_FILE
- `src/n3tx/core/main.py` - Backward-compat shim that delegates to `n3tx.example.main`

## Backend Patterns

### BaseUser Pattern
Application user models extend `BaseUser` to get login, register, and password hashing for free:
```python
from n3tx.core.models.base_user import BaseUser

class User(BaseUser):
    __tablename__ = 'users'
    __abstract__ = False          # Mark as concrete (BaseUser is abstract)
    # Add app-specific fields:
    image: Optional[str] = Field(default=None)
```
`BaseUser` provides: `name`, `email`, `role`, `password_hash` fields, plus `login()` and `register_user()` endpoints via `@expose_route`. The registration route is still `POST /register` (unchanged URL). The method was renamed from `register()` to `register_user()` to avoid MRO collision with `Actor.register()` when using ActorModel hierarchies. Subclasses inherit everything and only add their own fields.

### Parent-Child Relationships
```python
# 1. Define parent with ListRef field
class Product(ProtoModel):
    comments: Optional[ListRef[Comment]] = Field(default=[])

# 2. Register join model (or use create_app with join_models=[(Product, Comment)])
register_model(generate_join_model(Product, Comment), storage=storage_backend)
```
This creates a `ProductComment` join model with auto-generated `product_id` FK column. Routes become `/products/{parent_id}/comments/{id}`.

### API Response Format
All entity responses include JSON Schema instance metadata:
- `$schema`: URL to the model's schema (e.g., `http://localhost:5000/Product`)
- `$id`: URL to the specific instance (e.g., `http://localhost:5000/products/1`)

This is injected by `model_response()`, which runs the dump pipeline (`proto_dump`). Storage operations use plain `model_dump()` (no metadata).

### Schema Response Format
Schema responses (`GET /{ClassName}`) include:
- `$schema`: `{API_URL}/Schema`
- `$id`: `{API_URL}/{ClassName}`
- `$defs` entries each get their own `$id`

### Authorization (ABAC)
Access rules are declared on models via `__access__` and on methods via `@expose_route(access=...)`. Rules compose with `|` (OR), `&` (AND), `~` (NOT).

```python
from authorize import ANYONE, AUTHENTICATED, OWNER, ROLE, Where

class Product(ProtoModel):
    __owner_field__ = 'user_owner'
    __access__ = {
        'read':   ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }

    @expose_route('/publish', methods=['POST'], access=OWNER & Where(status='draft'))
    def publish(self): ...
```

No `__access__` → defaults to `AUTHENTICATED` for all actions (backward compatible). The resolver is swappable via the `AuthorizationResolver` Protocol. Rules produce SQL WHERE clauses for efficient list filtering (SQL pushdown). Access rules are serialized into JSON Schema responses for frontend consumption. See `docs/AUTHORIZATION.md` for full documentation.

### Self-Referential Nesting
```python
class Comment(ProtoModel):
    parent_id: Optional[Ref['self']] = Field(default=None, description="Parent comment for nesting")
```
`Ref['self']` emits `{"type": "selfref"}` in JSON Schema. Stored as nullable `INTEGER` column. No join model needed.

### JSON Fields (dict/list in SQLite)
The storage layer transparently handles `dict` and `list` fields as JSON TEXT columns:

```python
class Agent(ActorModel):
    constraints: dict = Field(default={})       # → TEXT column, auto json.dumps/loads
    tags: list = Field(default=[])              # → TEXT column, auto json.dumps/loads
    scores: List[int] = Field(default=[])       # → TEXT column, auto json.dumps/loads
    tools: ListRef[AgentTool] = Field(default=[])  # → FK join table (NOT JSON)
```

Detection: `get_json_fields(model_class)` in `introspection.py` returns field names for JSON storage. It matches `dict`, `Dict[str, Any]`, `Optional[dict]`, `list`, `List[str]`, `List[int]` — but excludes `ListRef[T]` and `List[BaseModel]` (those use FK join tables).

Write path: `_coerce_value()` calls `json.dumps(v, default=str)` for `dict`/`list` values.
Read path: `_deserialize_json_fields(model_class, record)` calls `json.loads()` on string values before model instantiation.
Migration: `create_table()` and `migrate_table()` emit `TEXT` columns for bare list/dict fields.

No model-level boilerplate (`_storage_dict()`, `@model_validator`, `update()` override) is needed.

### FK Column Naming Convention
Parent FK columns: `{parent_class_name_lowercase}_id` (e.g., `product_id`).
Avoid aliasing the `id` field on models to prevent naming clashes with self-referencing relationships.

### Dump Pipeline
The dump pipeline (`proto_dump.py`) mirrors the schema pipeline pattern for model serialization:

```python
data = product.model_response()           # runs dump pipeline (injects $schema, $id)
data = product.model_dump()               # plain dict for storage (no metadata)
```

The pipeline runs composable `dict -> dict` stages:
```python
d = proto_dump.base(instance)       # Plain Pydantic data extraction
d = proto_dump.response(instance, d) # Inject $schema and $id
```

External packages extend via `@dump_extension`:
```python
from n3tx.core.models.proto_dump import dump_extension

@dump_extension(after='response')
def activity(instance, d: dict) -> dict:
    if getattr(instance.__class__, '__federated__', False):
        d['@context'] = 'https://www.w3.org/ns/activitystreams'
        d['type'] = instance.__class__.__name__
    return d
```

### NetworkAdapter Pattern
ALL external protocol interaction flows through a `NetworkAdapter(Actor)`. Each adapter translates between an external protocol and TX messages:

```
External Protocol  →  NetworkAdapter  →  TX  →  Matrix  →  ActorModel
                  ←                  ←  TX  ←          ←
```

The adapter family:

| Adapter | Protocol | Status |
|---------|----------|--------|
| `NetworkMCP` | MCP JSON-RPC 2.0 (AI agents) | v0.8.1 |
| `NetworkAP` | ActivityPub (Fediverse federation) | v0.8.1 |
| `NetworkAPI` | HTTP REST (FastAPI/Flask/Django) | v0.9 |
| `NetworkWebSocket` | WebSocket (frontend Matrix bridge) | v0.8.5 |

All adapters support streaming via `adapter.stream(tx)` — an async generator that yields correlated TX chunks (see [Streaming](#streaming-infrastructure) below).

MCP tool names follow `{tablename}_{action}` (e.g., `products_create`, `products_favorite`). See Key Files for per-adapter API details.

**Usage:**
```python
from n3tx.core.api.network_mcp import NetworkMCP, create_mcp_routes
from n3tx.core.api.network_ap import NetworkAP, create_federation_routes

# Register adapters with Matrix
mcp = NetworkMCP(addr='mcp')
matrix.register(mcp)

ap = NetworkAP(addr='ap', base_url='https://example.com')
matrix.register(ap)

# Mount FastAPI routes
app.include_router(create_mcp_routes(mcp))
app.include_router(create_federation_routes(ap))

# Subscribe federated models to lifecycle events
for model in registered_models.values():
    if getattr(model, '__federated__', False):
        model._subscribers.append('ap')
```

### Widget Pattern (Python)
Widget fields map Python types to specialized frontend renderers. The `Widget` class hierarchy serves as both a type annotation and a metadata carrier:

```python
from n3tx.core.widgets import MarkdownField, UrlField, CurrencyField

class BlogPost(ProtoModel):
    body: MarkdownField                  # bare — validates as str, widget=markdown
    body: MarkdownField(rows=10)         # with config — Annotated[str, MarkdownField(rows=10)]
    website: UrlField                    # validates as AnyHttpUrl, widget=url
    price: CurrencyField                 # validates as float, widget=currency
```

Three detection cases in the `widget` schema pipeline stage:
1. `Annotated[str, <MarkdownField instance>]` — from `MarkdownField(rows=10)` call
2. Bare `MarkdownField` class — `issubclass(annotation, Widget)`
3. Auto-detect: bare `AnyHttpUrl` → check `AUTO_DETECT_MAP`

App developers extend with a single class:
```python
class ColorField(Widget, name='color', base_type=str): pass
```

### Streaming Infrastructure

Streaming lets any `@expose_route` method send progressive results to the client. The developer writes an async generator; the framework handles SSE formatting, WebSocket routing, and stream lifecycle.

#### Defining a Streaming Method

```python
@expose_route('/generate', methods=['POST'], stream=True, access=AUTHENTICATED)
async def generate(self, prompt: str = ''):
    for i in range(10):
        await asyncio.sleep(0.1)
        yield {'chunk': f'Processing step {i}'}
```

The `stream=True` flag adds `"stream": true` to the method's schema entry. The method must be an async generator (use `yield`, not `return`).

#### TX Stream Protocol

TX uses `meta` fields for stream correlation (no TX dataclass changes):

| Message | `meta` fields |
|---------|--------------|
| Chunk | `req: uuid`, `stream: True`, `seq: N` |
| End | `req: uuid`, `stream: True`, `stream_end: True`, `seq: N` |
| Error | Existing `tx.error()` — `is_error` terminates the stream |

Helper methods on TX:
- `tx.stream_chunk(data, seq)` — creates a chunk reply correlated to the original request
- `tx.stream_end(data, seq)` — creates a stream-end reply

#### How It Works at Each Level

**Level 1/2** (`routes_fastapi.py`): After calling the method, `inspect.isasyncgen(result)` detects the async generator. The route returns a `StreamingResponse` that iterates the generator and emits SSE lines:
```
event: chunk
data: {"chunk": "Processing step 0"}

event: chunk
data: {"chunk": "Processing step 1"}

event: done
data: {}
```

**Level 3** (`network_api.py`): `_add_streaming_handler()` creates a dedicated route that sends the TX through `NetworkAdapter.stream()` and converts the yielded TX chunks to SSE via `_sse_from_stream()`.

**ActorModel handler** (`actor_model.py`): When the handler detects `inspect.isasyncgen(result)`, it iterates the generator and sends `tx.stream_chunk()` for each yielded value, followed by `tx.stream_end()`.

**NetworkAdapter.stream()** (`network_adapter.py`): Sends the TX and yields correlated chunks from an `asyncio.Queue`. `inbox()` routes stream replies to the Queue (vs. Future for `request()`). Terminates on `stream_end` or error TX, with configurable timeout.

**WebSocket** (`network_ws.py`): `handle_message()` detects `meta.stream` in the incoming message and runs `_stream_to_ws()` as a background task. Chunks are sent directly to the WS client without blocking the message loop.

#### SSE Wire Format

```
event: chunk|done|error
data: {json}\n\n
```

Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
