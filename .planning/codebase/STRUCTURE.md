# Codebase Structure

**Analysis Date:** 2026-03-04

## Directory Layout

```
/workspace/
├── src/n3tx/                # Framework source
│   ├── core/                  # Core framework (all backend logic)
│   │   ├── actors/            # Actor system (Actor, Matrix, TX, ActorProxy)
│   │   ├── agents/            # Agent system (AgentMixin, AgentActor, tools, schema ext)
│   │   ├── api/               # Route generation, network adapters, auth interceptor
│   │   ├── authorize/         # ABAC authorization (standalone, zero N3TX imports)
│   │   ├── models/            # ProtoModel, ActorModel, BaseUser, mixins, pipelines
│   │   ├── storage/           # Storage backends (SQLite, JSON, abstract interface)
│   │   ├── ssr/               # Server-side rendering (schema injection, JS bundling)
│   │   ├── swagger/           # Swagger/OpenAPI setup
│   │   ├── utils/             # Decorators, registrar, introspection, scaffolding
│   │   ├── widgets/           # Widget type system (field -> renderer mapping)
│   │   ├── tests/             # Framework unit tests
│   │   ├── app.py             # N3TXApp builder + create_app() factory
│   │   ├── config.py          # Framework configuration (env vars, defaults)
│   │   ├── conftest.py        # Shared pytest fixtures for core tests
│   │   └── __init__.py        # Public API re-exports
│   ├── static/                # Frontend (vanilla JS, Web Components)
│   │   ├── core/              # Core JS: Actor.js, Matrix.js, TX.js, N3TX.js, Router.js
│   │   ├── components/        # Web Components: ntx-list, ntx-item, ntx-method, etc.
│   │   ├── generators/        # form.js (Formidable schema-driven form generation)
│   │   ├── widgets/           # JS widget renderers (Markdown, Url, Currency, etc.)
│   │   ├── utils/             # JS utilities (Permissions, Toast, DateFormat, etc.)
│   │   ├── docs/              # Frontend architecture docs
│   │   └── tests/             # Frontend unit tests (Vitest)
│   ├── docs/                  # Handwritten API docs + auto-generated model docs
│   └── example/               # Legacy example app (delegates to example_api)
├── example_api/               # Level 1/2 example (direct routes, ProtoModel)
│   ├── models/                # Product, Comment, Like, User, Bot
│   ├── tests/                 # Integration tests for direct routing
│   ├── static/                # App-specific HTML/CSS overrides
│   ├── main.py                # App entry point
│   ├── config.py              # App config
│   └── seed.py                # Seed data generator
├── example_actor/             # Level 3 example (actor routing, ActorModel)
│   ├── models/                # Same models as example_api (but ActorModel)
│   ├── tests/                 # Integration tests for actor routing
│   ├── static/                # App-specific HTML/CSS overrides
│   ├── main.py                # App entry point (routing='actor')
│   ├── config.py              # App config
│   └── seed.py                # Seed data generator
├── example_grants/            # Agentic app (grant discovery, agents, tools)
│   ├── models/                # Grant, Source, WebTools, User
│   ├── tests/                 # Integration + e2e tests
│   ├── utils/                 # URL validator (SSRF protection)
│   ├── migrations/            # Manual SQL migrations
│   ├── static/                # App-specific static files
│   ├── main.py                # App entry point (routing='actor', agents)
│   ├── config.py              # App config
│   └── seed.py                # Seed data + agent setup
├── CLAUDE.md                  # Project guide (root)
├── claude-back.md             # Backend conventions and patterns
├── claude-front.md            # Frontend conventions and patterns
├── pyproject.toml             # Package metadata, dependencies
├── requirements.txt           # Pinned dev dependencies
└── .planning/                 # GSD planning documents
```

## Directory Purposes

**`src/n3tx/core/actors/`**
- Purpose: Actor system -- the messaging backbone for Level 3 routing and agents
- Contains: Actor base, Matrix root, TX message envelope, ActorProxy, legacy actor
- Key files:
  - `actor.py`: `Actor` class, `ActorMeta` metaclass, `actormethod`/`actorproperty` descriptors
  - `matrix.py`: `Matrix` root actor, module-level `matrix` singleton
  - `tx.py`: `TX` dataclass (name, source, target, data, meta, uuid), reply/error/exception
  - `actor_proxy.py`: `ActorProxy` lightweight wrapper for non-Actor classes
  - `__init__.py`: Re-exports TX, Actor, Matrix, matrix
  - `tests/`: Actor-specific unit tests (actor, matrix, tx, interceptors, auth_interceptor, integration)

**`src/n3tx/core/agents/`**
- Purpose: LLM-powered agent system built on the actor layer
- Contains: AgentMixin (runtime injection), AgentActor (data-driven agents), tool discovery, schema extension
- Key files:
  - `mixin.py`: `AgentMixin` -- injected via `__agent__ = True`, provides `agent_run()`
  - `actor.py`: `AgentActor` -- concrete model, instances ARE agents (storable, DB-backed)
  - `tool_model.py`: `AgentTool` -- actor address reference, linked via ListRef join table
  - `tools.py`: `discover_tools()`, `create_tool_function()`, `make_tool()`, `ToolSpec`
  - `deps.py`: `AgentDeps` dataclass (adapter, user, agent_addr) for pydantic-ai RunContext
  - `schema_ext.py`: `@schema_extension(after='methods')` adds `agent` stage to pipeline
  - `__init__.py`: Re-exports + registers schema extension via side-effect import
  - `tests/`: Agent unit tests (mixin, actor, tools)

**`src/n3tx/core/api/`**
- Purpose: HTTP/protocol layer -- route generation, network adapters, auth
- Contains: Two route systems (direct + actor), four network adapters, auth middleware
- Key files:
  - `routes_fastapi.py`: Level 1/2 direct route factories (`register_routes()`, `make_create_instance()`, etc.)
  - `network_api.py`: Level 3 `NetworkAPI` adapter + `create_api_routes()`, bridges HTTP to Matrix TX
  - `network_adapter.py`: `NetworkAdapter` base class with `request()` correlation via asyncio.Future
  - `auth_interceptor.py`: Tier 1 auth interceptor for Level 3 (schema pass-through, sql_filter, identity gate)
  - `backend.py`: `FastAPIBackend` (CORS, JWT middleware, SSR mounting, static files), `FlaskBackend`
  - `network_mcp.py`: `NetworkMCP` -- MCP JSON-RPC 2.0 adapter for AI agents
  - `network_ap.py`: `NetworkAP` -- ActivityPub federation adapter
  - `network_ws.py`: `NetworkWebSocket` -- WebSocket bridge for frontend real-time
  - `discovery.py`: `GET /_meta` and `GET /.well-known/agent.json` discovery endpoints
  - `tests/`: Network adapter unit tests

**`src/n3tx/core/authorize/`**
- Purpose: Standalone ABAC authorization (zero N3TX imports)
- Contains: Rule algebra, access context, resolver, JWT auth, error types
- Key files:
  - `rules.py`: `AccessRule` ABC + concrete rules: `ANYONE`, `NEVER`, `AUTHENTICATED`, `OWNER`, `ROLE(name)`, `Where(clause)`, `Federated`, `Local`, `Follower`. Compose with `|` (OR), `&` (AND), `~` (NOT)
  - `context.py`: `AccessContext` dataclass (user, action, model_class, resource, parent_id)
  - `resolver.py`: `DefaultResolver` -- reads `__access__` from model, falls back to AUTHENTICATED
  - `auth.py`: `configure()`, `hash_password()`, `verify_password()`, `create_token()`, `decode_token()`
  - `schema.py`: `access_schema()` -- serializes rules to JSON-compatible dict for schema exposure
  - `errors.py`: `AccessDenied` exception
  - `__init__.py`: Re-exports all public API

**`src/n3tx/core/models/`**
- Purpose: Model definitions, schema/dump pipelines, mixins, type system
- Contains: The model hierarchy and both composable pipelines
- Key files:
  - `proto_model.py`: `ProtoModel` -- base model, `__init_subclass__` mixin injection, `schema()`, `model_response()`, `generate_join_model()`
  - `actor_model.py`: `ActorModel(Actor, ProtoModel)` -- bridge class, `handler_crud()`, `_authorize()`, `_publish_lifecycle()`
  - `proto_schema.py`: Schema pipeline engine + default stages (base, strip_hidden, methods, defs, access, ui, metadata)
  - `proto_dump.py`: Dump pipeline engine + default stages (base, schema_url, instance_url)
  - `base_user.py`: `BaseUser(ProtoModel)` -- abstract auth base with login/register endpoints
  - `storable_mixin.py`: `StorableMixin` -- CRUD methods delegating to storage backend
  - `viewable_mixin.py`: `ViewableMixin` -- UI view URL generation (early/experimental)
  - `ref.py`: `ListRef[T]` type alias factory for collection reference fields
  - `__init__.py`: Empty (imports are in `core/__init__.py`)

**`src/n3tx/core/storage/`**
- Purpose: Pluggable storage backends
- Contains: Abstract interface + SQLite implementation + JSON fallback
- Key files:
  - `abstract_storage.py`: `AbstractStorage` ABC -- create_table, create, list, get, update, delete
  - `sqlite_storage.py`: `SQLiteStorage` -- full SQLite backend with pagination, FK hydration, populate (eager loading)
  - `sqlite_migration.py`: Auto-migration (ALTER TABLE ADD COLUMN) + manual migration runner
  - `sqlite_helpers.py`: SQLite type mapping utilities
  - `json_storage.py`: `JSONStorage` -- legacy JSON file storage

**`src/n3tx/core/widgets/`**
- Purpose: Field-type-aware rendering system
- Contains: Widget metaclass, built-in field types, schema pipeline extension
- Key files:
  - `widget.py`: `Widget` base (WidgetMeta metaclass), built-in types: `UrlField`, `EmailField`, `DateField`, `DateTimeField`, `MarkdownField`, `ConsoleField`, `ReferenceField`, `CurrencyField`, `TextareaField`
  - `schema_ext.py`: `@schema_extension(before='ui')` -- injects `ui.widget` + `ui.config` into schema properties
  - `__init__.py`: Re-exports + registers schema extension

**`src/n3tx/core/ssr/`**
- Purpose: Server-side rendering for initial page load optimization
- Contains: HTML injection + JS module bundling
- Key files:
  - `html.py`: `inject_schemas()`, `inject_bundle()`, `inject_full()`, `inject_css_preloads()`
  - `bundler.py`: `build_bundle()` (resolve ES module imports into single script), `discover_css_deps()`
  - `__init__.py`: Re-exports injection functions

**`src/n3tx/core/utils/`**
- Purpose: Cross-cutting utilities
- Contains: Decorators, model registration, introspection, scaffolding, error types
- Key files:
  - `registrar.py`: `register_model()`, `prepare_model()`, `apply_registration()`, `registered_models` global dict, `join_models` global dict
  - `decorators.py`: `expose_route()` decorator -- marks methods as API endpoints
  - `introspection.py`: `pydantic_schema_for_type()`, `collect_all_referenced_models()`, `record_model_type()`
  - `typer.py`: `Ref[T]` generic FK type, `flatten_refs()`, `_SelfRefMarker`
  - `erroring.py`: `MethodError` exception with status_code + message, `get_traceback_info()`
  - `populate.py`: `parse_populate()` -- query param to PopulateSpec for eager loading
  - `scaffold.py`: `scaffold_single()` -- generate boilerplate code from schema
  - `generate_docs.py`: Auto-generate model documentation from schemas
  - `modeling.py`: Model utility functions

**`src/n3tx/core/tests/`**
- Purpose: Framework-level unit tests
- Location: `src/n3tx/core/tests/unit/`
- Contains: 40+ test files covering models, storage, auth, routes, actors, schema, widgets
- Key files:
  - `conftest.py`: Shared fixtures (temp storage, model factories, auth tokens)
  - `helpers.py`: Test helper utilities
  - `unit/test_proto_model.py`: ProtoModel behavior
  - `unit/test_proto_schema.py`: Schema pipeline stages
  - `unit/test_proto_dump.py`: Dump pipeline stages
  - `unit/test_actor_system.py`: Actor/Matrix/TX integration
  - `unit/test_actor_model_crud.py`: ActorModel CRUD handler
  - `unit/test_actor_model_authorize.py`: Tier 2 authorization
  - `unit/test_auth.py`: JWT auth utilities
  - `unit/test_sqlite_storage.py`: SQLite backend
  - `unit/test_schema_ext.py`: Agent schema extension
  - `unit/widgets/`: Widget-specific tests

**`src/n3tx/static/`**
- Purpose: Frontend -- schema-driven Web Components, no build step required
- Contains: Core JS framework, Web Components, form generator, widgets, utilities
- Key subdirectories:
  - `core/`: Actor.js, Matrix.js, TX.js, N3TX.js (DynamicClass), Component.js, Router.js, Observable.js, Utils.js
  - `core/transport/`: HTTP.js, Socket.js, NetworkAdapter.js
  - `components/`: ntx-list.js, ntx-item.js, ntx-method.js, ntx-router.js, ntx-sidebar.js, ntx-topbar.js, ntx-modal.js, ntx-table.js, ntx-row.js, ntx-user.js, ntx-profile.js, ntx-ref-picker.js, NTTElement.js (base), ListElement.js (base)
  - `generators/`: form.js (Formidable -- renders forms from schema)
  - `widgets/`: Widget.js (base), registry.js, index.js, MarkdownWidget.js, UrlWidget.js, CurrencyWidget.js, etc.
  - `utils/`: Permissions.js, Toast.js, DateFormat.js, Logging.js, str_utils.js, Snippets.js, theme.js, registrar.js
  - `tests/`: Vitest unit tests for frontend
  - `docs/`: ARCHITECTURE.md, COMPONENTS.md, ACTORS.md, TRANSPORT.md

## Key File Locations

**Entry Points:**
- `src/n3tx/core/app.py`: `create_app()` factory and `N3TXApp` builder
- `src/n3tx/core/__init__.py`: Public framework API re-exports
- `src/n3tx/core/config.py`: Framework configuration (env vars)
- `src/n3tx/core/main.py`: Legacy main.py shim (delegates to example app)
- `example_api/main.py`: Level 1/2 example app entry point
- `example_actor/main.py`: Level 3 example app entry point
- `example_grants/main.py`: Agentic app entry point

**Configuration:**
- `src/n3tx/core/config.py`: Framework defaults + N3TX_* env overrides
- `example_api/config.py`: App-specific config (JWT secret, DB path, host/port)
- `example_actor/config.py`: App-specific config
- `example_grants/config.py`: App-specific config
- `pyproject.toml`: Package metadata, dependencies, build config

**Core Logic:**
- `src/n3tx/core/models/proto_model.py`: ProtoModel + generate_join_model
- `src/n3tx/core/models/actor_model.py`: ActorModel bridge class
- `src/n3tx/core/models/proto_schema.py`: Schema pipeline engine
- `src/n3tx/core/models/proto_dump.py`: Dump pipeline engine
- `src/n3tx/core/actors/actor.py`: Actor system foundation
- `src/n3tx/core/actors/matrix.py`: Matrix root + module-level singleton
- `src/n3tx/core/api/routes_fastapi.py`: Level 1/2 route generation
- `src/n3tx/core/api/network_api.py`: Level 3 route generation
- `src/n3tx/core/api/backend.py`: FastAPI app setup (CORS, JWT, static)
- `src/n3tx/core/utils/registrar.py`: Model registration (global dicts)

**Testing:**
- `src/n3tx/core/tests/unit/`: Framework unit tests (40+ files)
- `src/n3tx/core/actors/tests/`: Actor system unit tests
- `src/n3tx/core/agents/tests/`: Agent system unit tests
- `src/n3tx/core/api/tests/`: Network adapter unit tests
- `example_api/tests/`: Integration tests (Level 1/2)
- `example_actor/tests/`: Integration tests (Level 3)
- `example_grants/tests/`: Integration + e2e tests (agents, grants)
- `src/n3tx/static/tests/`: Frontend Vitest tests

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `proto_model.py`, `actor_model.py`, `auth_interceptor.py`)
- Test files: `test_{module}.py` (e.g., `test_proto_schema.py`, `test_actor_system.py`)
- JS files: `PascalCase.js` for core classes (e.g., `Actor.js`, `N3TX.js`), `kebab-case.js` for components (e.g., `ntx-list.js`), `PascalCase.js` for widgets (e.g., `MarkdownWidget.js`)
- CSS files: `kebab-case.css` matching component names (e.g., `ntx-item.css`)

**Directories:**
- Python packages: `snake_case` (e.g., `actors`, `models`, `authorize`)
- Test directories: `tests/` with `unit/` subdirectory for framework, flat for apps
- Frontend: `core/`, `components/`, `generators/`, `widgets/`, `utils/`

## Where to Add New Code

**New Model (app-level):**
- Define in `example_*/models/{model_name}.py`
- Export from `example_*/models/__init__.py`
- Register in `example_*/main.py` via `create_app(models=[...])`
- Tests in `example_*/tests/test_{model_name}_crud.py`

**New Framework Model Feature (core):**
- Model behavior: `src/n3tx/core/models/`
- Schema pipeline stage: `@schema_extension()` in a new file, import from `__init__.py` for side-effect registration
- Dump pipeline stage: `@dump_extension()` in a new file
- Tests: `src/n3tx/core/tests/unit/test_{feature}.py`

**New Network Adapter:**
- Implementation: `src/n3tx/core/api/network_{protocol}.py`
- Extend `NetworkAdapter` from `src/n3tx/core/api/network_adapter.py`
- Use `auto_register=False`, manual registration via `matrix.register()`
- Tests: `src/n3tx/core/api/tests/test_network_{protocol}.py`

**New Authorization Rule:**
- Add to `src/n3tx/core/authorize/rules.py`
- Export from `src/n3tx/core/authorize/__init__.py`
- Tests: `src/n3tx/core/tests/unit/test_rules.py`

**New Widget Type (Python):**
- Define in `src/n3tx/core/widgets/widget.py` (or a separate file)
- Export from `src/n3tx/core/widgets/__init__.py`
- The schema pipeline extension in `widgets/schema_ext.py` auto-detects Widget subclasses

**New Widget Type (JS Frontend):**
- Create `src/n3tx/static/widgets/{Name}Widget.js`
- Register in `src/n3tx/static/widgets/index.js`

**New Web Component:**
- Create `src/n3tx/static/components/ntx-{name}.js` + `.css`
- Components auto-register via `customElements.define()`

**New Utility:**
- Backend: `src/n3tx/core/utils/{name}.py`
- Frontend: `src/n3tx/static/utils/{Name}.js`

## Special Directories

**`src/n3tx/core/actors/legacy/`**
- Purpose: Deprecated actor implementation (pre-ActorMeta refactor)
- Generated: No
- Committed: Yes (historical reference)

**`src/n3tx/core/tests/profiling/`**
- Purpose: Performance profiling tools (middleware, seed data, comparison)
- Generated: No
- Committed: Yes
- Activated via `N3TX_PROFILING=1` env var

**`example_grants/migrations/`**
- Purpose: Manual SQL migrations for the grants app
- Generated: No (hand-written)
- Committed: Yes
- Format: `{date}_{seq}_{description}.py`

**`src/n3tx/core/docs/`**
- Purpose: Auto-generated model documentation + changelogs
- Generated: Partially (model docs auto-generated by `generate_docs.py`)
- Committed: Yes

**`src/n3tx/static/vendor/`**
- Purpose: Third-party JS libraries (marked.min.js, ansi_up.min.js)
- Generated: No (vendored)
- Committed: Yes

**`src/n3tx/static/node_modules/`**
- Purpose: Vitest test dependencies
- Generated: Yes (npm install)
- Committed: Partially (present in repo)

## Module Boundaries and Dependencies

```
authorize/          # ZERO N3TX imports (standalone ABAC package)
    |
actors/             # Depends on: Pydantic (BaseModel), actors/tx.py only
    |
models/             # Depends on: actors/, authorize/, utils/, storage/ (abstract)
    |
storage/            # Depends on: nothing (abstract), sqlite3 (implementation)
    |
api/                # Depends on: models/, actors/, authorize/, utils/
    |
agents/             # Depends on: actors/, models/, api/network_adapter, pydantic-ai
    |
widgets/            # Depends on: models/proto_schema (extension mechanism), Pydantic types
    |
ssr/                # Depends on: models/ (schemas), filesystem
    |
app.py              # Depends on: EVERYTHING (orchestration point)
```

**Enforced boundaries:**
- `authorize/` has zero N3TX imports -- can be extracted as standalone package
- `StorableMixin` is injected, not inherited -- models don't import storage directly
- `AgentMixin` is injected, not inherited -- models don't import agents directly
- Actor system knows nothing about HTML, storage, or auth
- Network adapters are children of Matrix, registered manually (not auto-registered)

---

*Structure analysis: 2026-03-04*
