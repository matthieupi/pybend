# Architecture

**Analysis Date:** 2026-03-04

## Pattern Overview

**Overall:** Schema-driven, actor-routed full-stack framework

**Key Characteristics:**
- The Python model definition is the **single source of truth** for the entire stack (data, API, schema, UI, auth)
- Three bootstrapping levels: one-liner (`create_app`), builder (`PyBendApp`), raw primitives
- Actor system (Actor/Matrix/TX) provides uniform class/instance messaging, routing, and interceptors
- Composable pipelines for both schema generation and response serialization
- Frontend consumes JSON Schema at runtime to render UI with zero frontend code changes
- Authorization is ABAC (Attribute-Based Access Control) with algebraic rule composition

## Layers

**Model Layer:**
- Purpose: Define data structures, validation, access control, UI hints, and custom methods
- Location: `src/pybend/core/models/`
- Contains: `ProtoModel`, `ActorModel`, `BaseUser`, `StorableMixin`, `ViewableMixin`, `Ref`, `ListRef`
- Depends on: Pydantic V2, `authorize` package, `utils/decorators.py`, `utils/typer.py`
- Used by: Schema pipeline, dump pipeline, route generation, actor system

**Actor Layer:**
- Purpose: Unified messaging, routing, lifecycle events, and interceptors
- Location: `src/pybend/core/actors/`
- Contains: `Actor`, `Matrix`, `TX`, `ActorProxy`, `ActorMeta`, descriptors (`actormethod`, `actorproperty`)
- Depends on: Pydantic V2 (Actor extends PydanticBaseModel)
- Used by: `ActorModel`, network adapters, agent system

**Storage Layer:**
- Purpose: Persist model data via pluggable backends
- Location: `src/pybend/core/storage/`
- Contains: `AbstractStorage` (interface), `SQLiteStorage` (primary), `JSONStorage` (legacy)
- Depends on: Python sqlite3
- Used by: `StorableMixin` (injected into models with `__storable__ = True`)

**API / Route Layer:**
- Purpose: Expose models as HTTP endpoints (CRUD + custom methods)
- Location: `src/pybend/core/api/`
- Contains: `routes_fastapi.py` (Level 1/2 direct), `network_api.py` (Level 3 actor), `backend.py` (FastAPI setup)
- Depends on: FastAPI, model layer, authorize layer
- Used by: `PyBendApp.build()`, `create_app()`

**Authorization Layer:**
- Purpose: ABAC rules with algebraic composition, zero PyBend imports
- Location: `src/pybend/core/authorize/`
- Contains: `AccessRule` hierarchy (ANYONE, NEVER, AUTHENTICATED, OWNER, ROLE, Where, Federated), `AccessContext`, `DefaultResolver`, JWT auth
- Depends on: PyJWT, bcrypt (no PyBend imports -- fully standalone)
- Used by: Route layer, auth interceptor, model `__access__` declarations

**Agent Layer:**
- Purpose: LLM-powered reasoning via actor system, tool discovery from schemas
- Location: `src/pybend/core/agents/`
- Contains: `AgentMixin`, `AgentActor`, `AgentTool`, `AgentDeps`, `ToolSpec`, tool discovery/generation
- Depends on: pydantic-ai, actor system, network adapter
- Used by: Models with `__agent__ = True`, `example_grants/`

**Widget Layer:**
- Purpose: Map Python types to frontend renderers via schema metadata
- Location: `src/pybend/core/widgets/`
- Contains: `Widget` base (metaclass-driven), built-in fields (Url, Email, Date, Markdown, Currency, Textarea, Console, Reference)
- Depends on: Pydantic types (AnyHttpUrl, EmailStr, date, datetime)
- Used by: Model field annotations, schema pipeline (widget stage), frontend form.js

**SSR Layer:**
- Purpose: Server-side rendering for initial page load optimization
- Location: `src/pybend/core/ssr/`
- Contains: `html.py` (schema/bundle/full injection), `bundler.py` (JS module bundling, CSS discovery)
- Depends on: Model schemas, static file system
- Used by: `FastAPIBackend._mount_ssr_route()`

**Frontend Layer:**
- Purpose: Schema-driven Web Components UI -- no build step
- Location: `src/pybend/static/`
- Contains: Core (Actor.js, Matrix.js, TX.js, NTT.js), Components (ntt-list, ntt-item, ntt-method, etc.), Widgets, Generators (form.js)
- Depends on: Backend JSON Schema API
- Used by: Browser, served as static files

## Model Hierarchy

```
PydanticBaseModel (pydantic)
    |
    +-- ProtoModel (proto_model.py)
    |       |-- schema() via proto_schema pipeline
    |       |-- model_response() via proto_dump pipeline
    |       |-- __init_subclass__: StorableMixin injection (__storable__=True), AgentMixin injection (__agent__=True)
    |       |-- _schema_cache: ClassVar performance cache
    |       |
    |       +-- BaseUser (base_user.py) -- abstract auth base, login/register endpoints
    |       |       +-- User (app-specific) -- concrete user with app fields
    |       |
    |       +-- [App models without actor capabilities]
    |
    +-- Actor (actor.py, metaclass=ActorMeta)
            |-- actormethod: inbox, handler, send, register, spawn, has, use
            |-- actorproperty: addr, children, parent
            |-- ClassVars: __addr__, __children__, __interceptors__, __matrix__
            |-- PrivateAttrs: _addr, _children, _parent, _interceptors
            |
            +-- Matrix (matrix.py) -- root router, adapter registry
            |
            +-- NetworkAdapter (network_adapter.py) -- request/response correlation
            |       +-- NetworkAPI -- HTTP REST adapter (Level 3)
            |       +-- NetworkMCP -- MCP JSON-RPC adapter
            |       +-- NetworkAP -- ActivityPub federation adapter
            |       +-- NetworkWebSocket -- WebSocket bridge adapter
            |
            +-- ActorModel (actor_model.py) -- bridge: Actor + ProtoModel
                    |-- handler_crud(): TX -> StorableMixin CRUD
                    |-- _authorize(): Tier 2 ABAC with resource context
                    |-- _publish_lifecycle(): fire-and-forget lifecycle events
                    |
                    +-- AgentActor (agents/actor.py) -- instances ARE agents (data, not code)
                    |       |-- run(): @expose_route, triggers agent_run()
                    |       |-- _resolve_tool_addrs(): href -> actor address
                    |
                    +-- AgentTool (agents/tool_model.py) -- tool reference record
                    |
                    +-- [App models: Product, Grant, Source, etc.]
```

**Mixin Injection (via __init_subclass__):**
- `__storable__ = True` on any ProtoModel subclass -> injects `StorableMixin` into `__bases__`
- `__agent__ = True` on any model -> injects `AgentMixin` into `__bases__`
- Both follow the same pattern: check ClassVar flag, inject mixin if not already present

## Three Bootstrapping Levels

**Level 1 -- One-liner via `create_app()`** (`src/pybend/core/app.py`):
```python
app = create_app(models=[Product, User], storage="sqlite:///app.db")
```
- Routes via `routes_fastapi.py` (direct FastAPI route factories)
- Models extend `ProtoModel`
- Single-pass auth via `DefaultResolver.authorize(ctx)`

**Level 2 -- Builder via `PyBendApp`** (`src/pybend/core/app.py`):
```python
pb = PyBendApp(storage="sqlite:///app.db")
pb.model(Product).model(User).join(Product, Comment)
app = pb.build()
```
- Same routing as Level 1
- Chainable builder API, supports per-model storage overrides

**Level 3 -- Actor routing** (`routing='actor'`):
```python
app = create_app(models=[Product], storage="sqlite:///app.db", routing='actor')
```
- Routes via `NetworkAPI` adapter + `create_api_routes()`
- Models extend `ActorModel` (Actor + ProtoModel)
- Two-tier auth: Tier 1 interceptor (fast gate) + Tier 2 handler_crud (resource OWNER)
- All requests become TX messages routed through Matrix

**All three levels produce identical API endpoints and HTTP responses.**

## Schema Pipeline

Defined in `src/pybend/core/models/proto_schema.py`. Composable `dict -> dict` stages:

```
1. base(cls)              -- Pydantic model_json_schema() + Ref/ListRef patches
2. strip_hidden(cls, s)   -- Remove __hidden_fields__ from properties
3. methods(cls, s)        -- Inject @expose_route method signatures
4. agent(cls, s)          -- [extension] Inject agent metadata if __agent__=True
5. defs(cls, s)           -- Collect referenced models into $defs with schemas + methods
6. access(cls, s)         -- Serialize ABAC rules (top-level + $defs entries)
7. widget(cls, s)         -- [extension] Inject ui.widget + ui.config from Widget types
8. ui(cls, s)             -- Inject field_order, groups, renderer, protected fields, display hints
9. metadata(cls, s)       -- Stamp $schema and $id URLs
```

**Extension mechanism:** `@schema_extension(after='methods')` registers new stages without modifying core pipeline. Used by `agents/schema_ext.py` (agent stage) and `widgets/schema_ext.py` (widget stage).

**Cache:** `ProtoModel._schema_cache` stores per-class results. Schemas are immutable after server start. `invalidate_schema_cache()` for tests.

## Dump Pipeline

Defined in `src/pybend/core/models/proto_dump.py`. Composable `dict -> dict` stages for response serialization:

```
1. base(instance)             -- Pydantic model_dump()
2. schema_url(instance, d)    -- Inject $schema URL (cached per class)
3. instance_url(instance, d)  -- Inject $id URL (flat or parent-scoped for join models)
```

**Extension mechanism:** `@dump_extension(after='instance_url')` for federation (@context), MCP, etc.

Called via `instance.model_response()`.

## Route Generation

**Level 1/2 (direct):** `src/pybend/core/api/routes_fastapi.py`

1. `register_routes()` iterates `registered_models`
2. **Pass 1:** Register static collection routes for join models (must precede `{id:int}` routes)
3. **Pass 2:** Per model:
   - `GET /{ClassName}` -- schema (public, no auth)
   - `POST /{tablename}` -- create
   - `GET /{tablename}` -- list (paginated: `?limit=N&offset=M`)
   - `GET /{tablename}/{id}` -- read
   - `PUT /{tablename}/{id}` -- update
   - `DELETE /{tablename}/{id}` -- delete
   - Custom `@expose_route` methods (instance methods get `/{id}{route}`)
4. Join models get parent-scoped routes: `/{parent_table}/{parent_id}/{tagname}`

**Level 3 (actor):** `src/pybend/core/api/network_api.py`

Same route structure, but every handler:
1. Creates a `TX(name=action, source='api', target=tablename, data=..., meta={user, model_cls})`
2. Calls `api_adapter.request(tx)` which runs interceptors then sends through Matrix
3. Awaits correlated response via `asyncio.Future`
4. Converts response TX to HTTP result or error

**Registration flow:**
```
create_app() / PyBendApp.build()
    -> prepare_model() per model (pure, no side effects)
    -> generate_join_model() for join pairs
    -> apply_registration() per model (set_storage, create_table, migrate)
    -> backend.register_routes() (Level 1/2) or create_api_routes() (Level 3)
```

## Actor System

### TX Message Envelope (`src/pybend/core/actors/tx.py`)

Dataclass with: `name`, `source`, `target`, `data`, `meta`, `timestamp`, `uuid`.

Key methods:
- `reply(data, name)` -- swap source/target, new uuid, `meta['in_reply_to']`
- `error(message, code)` -- ERROR TX with `meta['error'] = True`
- `exception(e)` -- maps Python exceptions to error TX with semantic HTTP codes
- `is_error` -- property checking name or meta flag

### Actor Base Class (`src/pybend/core/actors/actor.py`)

**Descriptors** (the key innovation):
- `actormethod` -- binds `target = cls or self`, so `Product.inbox(tx)` and `product.inbox(tx)` use the same function
- `actorproperty` -- resolves class-level (`__addr__`, `__children__`) or instance-level (`_addr`, `_children`) state

**Core methods (all via actormethod):**
- `inbox(target, tx)` -- run interceptors, then `handler(tx)`
- `handler(target, tx)` -- `getattr(target, tx.name)` dispatch, wrap result as reply TX
- `send(target, tx)` -- class: route through children or bubble to parent; instance: route through parent chain
- `register(target, child)` -- add child to children dict, set parent
- `spawn(target, addr, actor_cls)` -- create and register child
- `use(target, interceptor, on='inbox')` -- register TX interceptor

**ActorMeta metaclass:**
- Per-class `__children__`, `__interceptors__` dicts
- `__addr__` from `__tablename__` or class name
- Auto-registers with root Matrix (unless `auto_register=False`)

### Matrix (`src/pybend/core/actors/matrix.py`)

Root actor and message router. Module-level `matrix = Matrix()` created at import time.

Routing:
1. Local children first (by first address segment)
2. Network adapters (HTTP, WS, MCP, AP)
3. Error TX back to sender if no route

Self-send prevention: target == own addr -> log error, return.

### ActorProxy (`src/pybend/core/actors/actor_proxy.py`)

Lightweight wrapper using `__slots__`. Gives any class or instance the actor interface (inbox/handler/send/register/spawn) without inheritance. Matrix routes uniformly to Actor and ActorProxy children.

### Interceptors

```python
actor.use(fn, on='inbox')        # Register on inbox
actor.use(fn, on='send')         # Register on send
actor.use(fn, on='request')      # Register on request (NetworkAdapter)
```

Signature: `async (TX) -> TX`. Return error TX to short-circuit. Class + instance interceptors combine (class first, FIFO).

## Two-Tier Authorization (Level 3)

**Tier 1 -- `auth_interceptor`** (`src/pybend/core/api/auth_interceptor.py`):
- Registered on `NetworkAPI.request()` via `api.use(auth_interceptor, on='request')`
- Fast gate at protocol boundary
- schema: pass-through (always public)
- list: compute `sql_filter`, store in `tx.meta['sql_filter']`
- create: full rule check (no resource instance needed)
- read/update/delete: identity gate only (OWNER deferred to Tier 2)
- custom methods: check `@expose_route(access=...)` rules

**Tier 2 -- `ActorModel._authorize()`** (`src/pybend/core/models/actor_model.py`):
- Called inside `handler_crud()` after fetching the resource instance
- Full ABAC evaluation with resource context (enables OWNER rules)
- Internal messages (no `meta.user`) pass through unchecked

**Level 1/2** uses single-pass `DefaultResolver.authorize(ctx)` in `routes_fastapi.py`.

## Agent System

### AgentMixin (`src/pybend/core/agents/mixin.py`)

Injected into models with `__agent__ = True`. Provides `agent_run()`:

1. Creates a transient `NetworkAdapter` per run for request/response correlation
2. Registers adapter with Matrix root
3. Calls `discover_tools(tool_addrs, root)` to find CRUD + custom method tools from actor schemas
4. Creates `pydantic_ai.Agent` with discovered tools
5. Runs the agent with `AgentDeps` context (adapter + user + agent_addr)
6. Tool calls route through Matrix as TX messages
7. Cleans up transient adapter

### AgentActor (`src/pybend/core/agents/actor.py`)

Concrete `ActorModel` whose instances ARE agents. Configuration stored in fields (DB-storable):
- `name`, `prompt`, `llm`, `constraints` (serialized as JSON TEXT)
- `tools`: `ListRef[AgentTool]` -- join table pattern
- `run()`: `@expose_route('/run', methods=['POST'])` -- triggers `agent_run()`

### Tool Discovery (`src/pybend/core/agents/tools.py`)

`discover_tools(actor_addrs, root)`:
- Reads schemas from Matrix children
- CRUD tools for storable models (list, get, create, update, delete)
- Custom method tools from `@expose_route` signatures

`create_tool_function(spec)`:
- Uses `exec()` for dynamic function signatures (same pattern as dataclasses)
- Generated functions route calls through Matrix via `_route_tool_call()`
- Wrapped as `pydantic_ai.Tool` objects with `takes_ctx=True`

### Schema Extension (`src/pybend/core/agents/schema_ext.py`)

`@schema_extension(after='methods')` adds `agent` stage:
```json
{"agent": {"enabled": true, "run_endpoint": "/agents/{id}/run"}}
```

## Frontend Architecture

**Core system** (mirrors backend Actor/Matrix/TX):
- `src/pybend/static/core/Actor.js` -- base actor class
- `src/pybend/static/core/Matrix.js` -- root message router
- `src/pybend/static/core/TX.js` -- message envelope
- `src/pybend/static/core/NTT.js` -- `NTT.SCHEMA()` creates DynamicClasses via `prototype()`
- `src/pybend/static/core/Component.js` -- base Web Component class
- `src/pybend/static/core/Router.js` -- client-side routing
- `src/pybend/static/core/Observable.js` -- reactive data binding

**Components** (Web Components consuming schema):
- `src/pybend/static/components/ntt-list.js` -- list view with pagination
- `src/pybend/static/components/ntt-item.js` -- single entity view with adaptive sizing
- `src/pybend/static/components/ntt-method.js` -- custom method buttons
- `src/pybend/static/components/ntt-router.js` -- navigation and route resolution
- `src/pybend/static/components/ntt-sidebar.js` -- model navigation sidebar
- `src/pybend/static/components/ntt-topbar.js` -- top navigation bar
- `src/pybend/static/components/ntt-modal.js` -- modal dialogs
- `src/pybend/static/components/ntt-table.js` -- table/row view
- `src/pybend/static/components/ntt-user.js` -- user auth UI

**Generators:**
- `src/pybend/static/generators/form.js` -- schema-driven form generation (`Formidable`)

**Widgets (JS side):**
- `src/pybend/static/widgets/Widget.js` -- base widget class
- `src/pybend/static/widgets/registry.js` -- widget registry
- Individual widgets: `UrlWidget.js`, `MarkdownWidget.js`, `CurrencyWidget.js`, etc.

**Transport:**
- `src/pybend/static/core/transport/HTTP.js` -- HTTP adapter
- `src/pybend/static/core/transport/Socket.js` -- WebSocket adapter
- `src/pybend/static/core/transport/NetworkAdapter.js` -- base adapter

## Data Flow: Request Lifecycle

### Schema Fetch (Frontend Bootstrap)

```
Browser: <ntt-list model="Product">
    -> NTT.SCHEMA("Product")
    -> GET /Product (no auth required)
    -> Backend: proto_schema.run_pipeline(Product)
        -> base: model_json_schema()
        -> strip_hidden -> methods -> agent -> defs -> access -> widget -> ui -> metadata
    <- JSON Schema with $schema, $id, properties, methods, access, ui, $defs
    -> Frontend: prototype() creates DynamicClass
    -> DynamicClass registered, $defs models registered
    -> Component triggers READ
```

### CRUD Read (Level 3 Actor Routing)

```
Frontend: GET /products?limit=20&offset=0
    -> FastAPI route handler (network_api.py)
    -> api_adapter.request(TX(name='list', target='products', data={limit:20}, meta={user}))
        -> Tier 1: auth_interceptor(tx)
            -> resolve_rule(Products, 'read')
            -> compute sql_filter, store in tx.meta['sql_filter']
        -> adapter.send(tx) -> Matrix.inbox(tx)
            -> Matrix routes to Products class (child 'products')
            -> Products.inbox(tx)
                -> ActorModel.handler(tx)
                    -> handler_crud(tx)
                        -> Products.list(sql_filter, limit, offset)
                            -> SQLiteStorage.list() with pagination
                        -> [instance.model_response() for each]
                            -> proto_dump.run_pipeline(instance)
                    -> tx.reply(data=result)
            -> reply routes back through Matrix to adapter
        -> adapter.inbox(reply) -> correlates via meta['in_reply_to'] -> Future.set_result()
    <- {data: [...], meta: {total, limit, offset, has_more}}
```

### Custom Method (with user injection)

```
Frontend: POST /products/42/comment {comment: {text: "Nice!"}}
    -> route handler resolves type hints
    -> _resolve_user(User, request): fetch User.get(user_id) from JWT
    -> method(instance, comment=Comment(...), user=User(...))
    <- result (string -> JSON or dict)
```

### Agent Run

```
POST /agents/1/run {"task": "Scan sources for grants"}
    -> AgentActor.run(task)
        -> _resolve_tool_addrs(): href -> ['grants', 'sources', 'web_tools']
        -> agent_run(prompt, tools, task)
            -> Create transient NetworkAdapter, register with Matrix
            -> discover_tools(['grants', 'sources', 'web_tools'], root)
                -> Read schemas, generate ToolSpecs (CRUD + custom methods)
            -> Build pydantic_ai.Agent with tools
            -> Agent.run(task, deps=AgentDeps(adapter, user))
                -> LLM calls tools -> _route_tool_call(ctx, addr, method, data)
                    -> adapter.request(TX(name=method, target=addr, data=data))
                    -> Routes through Matrix to target actor
                    -> Response routes back
                    -> JSON string returned to LLM
            -> Cleanup transient adapter
    <- {answer, usage: {input_tokens, output_tokens, requests}, messages}
```

## Network Adapters

All extend `NetworkAdapter` (`src/pybend/core/api/network_adapter.py`) which extends `Actor`:

| Adapter | File | Protocol | Purpose |
|---------|------|----------|---------|
| `NetworkAPI` | `api/network_api.py` | HTTP REST | Level 3 CRUD + custom methods |
| `NetworkMCP` | `api/network_mcp.py` | MCP JSON-RPC 2.0 | AI agent tool discovery and invocation |
| `NetworkAP` | `api/network_ap.py` | ActivityPub | Fediverse federation |
| `NetworkWebSocket` | `api/network_ws.py` | WebSocket | Real-time frontend Matrix bridge |

**Request/response correlation:** `NetworkAdapter.request()` stores a `Future` keyed by `tx.uuid`. Reply arrives at `inbox()` with `meta['in_reply_to']` matching the uuid. Future is resolved, bypassing normal handler dispatch.

## Discovery Endpoints

Defined in `src/pybend/core/api/discovery.py`:

- `GET /_meta` -- Model registry, capabilities, health (from registered_models)
- `GET /.well-known/agent.json` -- A2A Agent Card for inter-agent discovery

## Error Handling

**Strategy:** Structured error propagation via TX.error() and MethodError exception

**Patterns:**
- `TX.error(message, code)` creates error TX with semantic HTTP code
- `TX.from_exception(e, tx)` maps exception types: MethodError -> custom code, ValidationError -> 422, ValueError -> 400, PermissionError -> 403, KeyError -> 400
- `MethodError` (`src/pybend/core/utils/erroring.py`) carries status_code + message for custom method errors
- Error TXs short-circuit interceptor chains (`tx.is_error` check)
- Handler drops unhandled error/response TXs silently to prevent infinite bounce loops
- `_response_or_raise(response)` in network_api.py converts error TX to `HTTPException`

## Cross-Cutting Concerns

**Logging:** Python `logging` module with `pybend.*` namespace hierarchy (`pybend.actors`, `pybend.models`, `pybend.api`, `pybend.schema`, `pybend.agents`, `pybend.network`, etc.)

**Validation:** Pydantic V2 model validation + `Field()` constraints. Frontend gets constraints from JSON Schema properties.

**Authentication:** JWT via `x-access-token` header. `JWTAuthMiddleware` in `FastAPIBackend` decodes token and sets `request.state.user`. Auth package (`src/pybend/core/authorize/`) is standalone -- zero PyBend imports.

**Configuration:** Module-level `src/pybend/core/config.py` with env var overrides (`PYBEND_*`). Per-app config in `example_*/config.py`.

**Pagination:** `?limit=N&offset=M` query params. Returns `{data: [...], meta: {total, limit, offset, has_more}}` when limit/offset provided; plain array when not.

---

*Architecture analysis: 2026-03-04*
