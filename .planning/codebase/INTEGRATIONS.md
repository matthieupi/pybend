# External Integrations

**Analysis Date:** 2026-03-04

## APIs & External Services

**LLM Providers (via pydantic-ai):**
- Ollama (local) — default LLM backend for agent execution
  - SDK/Client: `pydantic-ai` (`pydantic_ai.Agent`)
  - Auth: None (local server)
  - Default model: `ollama:llama3.1` (configured in `AgentActor.llm` field)
  - Entry point: `src/n3tx/core/agents/mixin.py` → `AgentMixin.agent_run()`

- Anthropic (cloud) — alternative LLM backend
  - SDK/Client: `pydantic-ai` (delegates to `anthropic` package)
  - Auth: `ANTHROPIC_API_KEY` environment variable (handled by pydantic-ai)
  - Model string: `anthropic:claude-sonnet-4-5-20250929` (configured in `example_grants/seed.py`)

- Test model — for automated testing
  - SDK/Client: `pydantic_ai.models.test.TestModel`
  - Usage: `TestModel(call_tools=[])` or `TestModel(call_tools=['tool_name'])`
  - Used in: `example_grants/tests/test_agent_run.py`

**Web Scraping (httpx + BeautifulSoup):**
- httpx — async HTTP client for fetching web pages
  - SDK/Client: `httpx.AsyncClient`
  - Used in: `example_grants/models/web_tools.py` → `WebTools.scrape()`
  - Config: `follow_redirects=True, timeout=30`
  - Response truncated to 50,000 chars
- BeautifulSoup4 — HTML parsing and CSS selector extraction
  - Used in: `example_grants/models/web_tools.py` → `WebTools.extract()`
  - Parser: `html.parser` (stdlib, no lxml dependency)

## Data Storage

**Database:**
- SQLite (stdlib `sqlite3` module)
  - Connection: file path via `N3TX_SQLITE_DB` env var or constructor arg
  - Client: `src/n3tx/core/storage/sqlite_storage.py` → `SQLiteStorage`
  - Interface: `src/n3tx/core/storage/abstract_storage.py` → `AbstractStorage` (ABC)
  - Connection pool: `queue.Queue(maxsize=4)`, `check_same_thread=False`
  - WAL mode: enabled on first connection
  - Grants app DB: `example_grants/grants.db`

**Schema Migrations:**
- Auto-migration: `src/n3tx/core/storage/sqlite_migration.py` → `SQLiteMigration`
  - Runs on model registration — compares existing columns to model fields, adds missing columns
- Manual migrations: `example_grants/migrations/` directory
  - Python scripts executed by `storage._migration.run_migrations()`
  - Example: `20260303_001_set_default_grant_owner.py`

**File Storage:**
- Local filesystem only (static files served via FastAPI `StaticFiles` mount)

**Caching:**
- In-memory schema cache: `ProtoModel._schema_cache` ClassVar per model class
- In-memory MCP tools cache: `NetworkMCP._tools_cache` PrivateAttr
- No external cache service (Redis, Memcached, etc.)

## Authentication & Identity

**Auth Provider:**
- Custom JWT-based authentication (standalone `authorize` package — zero N3TX imports)
  - Package: `src/n3tx/core/authorize/`
  - JWT: PyJWT with HS256 algorithm (`src/n3tx/core/authorize/auth.py`)
  - Password hashing: bcrypt (`src/n3tx/core/authorize/auth.py`)
  - Token payload: `{user_id, email, role, exp, iat}`
  - Token header: `x-access-token` (extracted by `JWTAuthMiddleware` in `src/n3tx/core/api/backend.py`)
  - Token endpoints: `POST /users/login`, `POST /users/register` (from `BaseUser` model)

**Authorization (ABAC):**
- Rule-based access control: `src/n3tx/core/authorize/rules.py`
  - Rules: `ANYONE`, `NEVER`, `AUTHENTICATED`, `OWNER`, `ROLE('admin')`, `Where(field=value)`
  - Composable: `OWNER | ROLE('admin')`, `AUTHENTICATED & ROLE('editor')`
  - Federation rules: `FEDERATED`, `LOCAL`, `FOLLOWER`
- Resolver: `src/n3tx/core/authorize/resolver.py` → `DefaultResolver`
  - Evaluates rules against `AccessContext(user, action, model_class, resource)`
  - Produces SQL filters for list queries (e.g., OWNER → `WHERE user_owner = ?`)
- Model-level: `__access__` ClassVar dict (`{'read': ANYONE, 'create': AUTHENTICATED, ...}`)
- Field-level: `json_schema_extra={'access': {'view': 'anyone', 'edit': 'admin'}}`
- Method-level: `@expose_route('/like', access=AUTHENTICATED)`

**Two-Tier Auth (Level 3 actor routing):**
- Tier 1: `src/n3tx/core/api/auth_interceptor.py` — fast gate at protocol boundary
  - Registered on `NetworkAPI.request()` via `api.use(auth_interceptor, on='request')`
  - Schema: pass-through (always public)
  - List: computes `sql_filter` and injects into `tx.meta`
  - Create: full rule evaluation (no resource instance needed)
  - Read/Update/Delete: identity gate only (OWNER deferred to Tier 2)
- Tier 2: `src/n3tx/core/models/actor_model.py` → `ActorModel._authorize()`
  - Full ABAC with resource instance (handles OWNER checks after DB fetch)

## Internal Integration Points

**Actor System ↔ HTTP Routes:**
- Level 1/2 (direct): `src/n3tx/core/api/routes_fastapi.py` → calls StorableMixin methods directly
- Level 3 (actor): `src/n3tx/core/api/network_api.py` → `NetworkAPI` adapter
  - Every HTTP request → TX message → Matrix routing → ActorModel handler → TX reply → HTTP response
  - Request/response correlation via `asyncio.Future` in `NetworkAdapter._pending` dict
  - TX uuid matching via `meta['in_reply_to']` on reply TXs

**Actor System ↔ Agent System:**
- Agent execution: `src/n3tx/core/agents/mixin.py` → `AgentMixin.agent_run()`
  1. Creates transient `NetworkAdapter` per run (unique address: `_agent_{uuid}`)
  2. Registers adapter with Matrix root
  3. Discovers tools from actor addresses via `src/n3tx/core/agents/tools.py` → `discover_tools()`
  4. Each tool call → TX message → Matrix routing → target ActorModel → TX reply
  5. Cleanup: removes transient adapter on completion
- Tool discovery: reads model schemas, generates CRUD + custom method ToolSpecs
- Tool functions: dynamically generated via `exec()` with typed signatures for pydantic-ai introspection

**Schema Pipeline ↔ Frontend:**
- Pipeline: `src/n3tx/core/models/proto_schema.py` — composable stages
  - Stages: `base` → `strip_hidden` → `methods` → `defs` → `access` → `widget` → `agent` → `ui` → `metadata`
  - Extension mechanism: `@schema_extension(after='methods')` decorator
  - Agent extension: `src/n3tx/core/agents/schema_ext.py` → injects `agent` section
  - Widget extension: `src/n3tx/core/widgets/schema_ext.py` → injects `ui.widget` + `ui.config`
- Frontend consumption: `GET /{ClassName}` returns full JSON Schema
  - `src/n3tx/static/core/N3TX.js` → `N3TX.SCHEMA()` creates DynamicClasses via `prototype()`
  - Schema carries rendering instructions (`ui.widget`, `ui.groups`, `ui.field_order`), access rules, method signatures, and `$defs` for nested models

**Model Registration ↔ Route Generation:**
- Registration flow in `src/n3tx/core/utils/registrar.py`:
  1. `prepare_model(cls, storage)` → pure `RegistrationResult` (no side effects)
  2. `apply_registration(result)` → sets storage, creates table, runs migration, adds to `registered_models` dict
- Route generation:
  - Direct: `FastAPIBackend.register_routes(registered_models)` → `routes_fastapi.py`
  - Actor: `create_api_routes(api_adapter, registered_models)` → `network_api.py`
- Join model generation: `generate_join_model(parent, child)` in `src/n3tx/core/models/proto_model.py`
  - Creates a dynamic class inheriting from parent with `__owner__` reference
  - Used for ListRef collections (e.g., `AgentActor.tools: ListRef[AgentTool]`)

**StorableMixin Injection:**
- `src/n3tx/core/models/storable_mixin.py` → injected into models with `__storable__ = True`
- Provides: `create()`, `get()`, `list()`, `update()`, `delete()`, `save()`, `create_table()`
- Storage backend set via `cls.set_storage(storage)` — class-level ClassVar

**AgentMixin Injection:**
- `src/n3tx/core/agents/mixin.py` → injected into models with `__agent__ = True`
- Provides: `agent_run(prompt, tools, task, user, **kwargs)`
- Only `AgentActor` currently uses this (`src/n3tx/core/agents/actor.py`)

## Protocol Adapters (NetworkAdapter hierarchy)

All adapters extend `src/n3tx/core/api/network_adapter.py` → `NetworkAdapter(Actor)`:

**NetworkAPI** — HTTP REST adapter (`src/n3tx/core/api/network_api.py`)
- Bridges FastAPI routes → Matrix TX messages
- Address: `api`
- Used in Level 3 routing mode

**NetworkWebSocket** — WebSocket adapter (`src/n3tx/core/api/network_ws.py`)
- Persistent connections, real-time lifecycle event broadcasting
- Frontend UPPERCASE event names mapped to backend lowercase
- Address: `ws`
- Enabled via `ws=True` in `create_app()`

**NetworkMCP** — MCP JSON-RPC 2.0 adapter (`src/n3tx/core/api/network_mcp.py`)
- AI agent discovery and tool calling (Claude Desktop, Cursor, GPT, etc.)
- Protocol: JSON-RPC 2.0 over HTTP POST
- Endpoints: `POST /mcp` (JSON-RPC), `GET /mcp/tools` (convenience list)
- Methods: `initialize`, `tools/list`, `tools/call`, `ping`
- Protocol version: `2024-11-05`
- Address: `mcp`
- Schema → MCP tool conversion: CRUD + custom methods per model

**NetworkAP** — ActivityPub federation adapter (`src/n3tx/core/api/network_ap.py`)
- Fediverse federation for models with `__federated__ = True`
- Publish-focused (outbox) in current wave
- Address: `ap`

## Discovery & Interoperability

**Service Discovery:**
- `GET /_meta` — model registry, capabilities, health (`src/n3tx/core/api/discovery.py`)
- `GET /.well-known/agent.json` — A2A Agent Card (Google A2A protocol)
  - Skills generated from registered models (CRUD + custom methods)
  - Authentication scheme: bearer token
  - Input/output: `application/json`

## Monitoring & Observability

**Error Tracking:**
- No external error tracking service
- `MethodError` exception class (`src/n3tx/core/utils/erroring.py`) for custom method errors
- `TX.from_exception()` centralizes exception → error TX mapping with semantic HTTP codes

**Logs:**
- Python `logging` module throughout
- Logger hierarchy: `n3tx.models`, `n3tx.actors`, `n3tx.storage`, `n3tx.agents`, `n3tx.network`, `n3tx.network.api`, `n3tx.network.ws`, `n3tx.network.mcp`, `n3tx.network.ap`, `n3tx.schema`, `n3tx.api`, `n3tx.authorize`
- Default format in grants app: `%(levelname)s %(name)s: %(message)s`

## CI/CD & Deployment

**Hosting:**
- Self-hosted (Uvicorn ASGI server)
- Single-process deployment (SQLite limitation)

**CI Pipeline:**
- Not detected (no `.github/workflows/`, no CI config files found)

## Environment Configuration

**Required env vars (production):**
- `N3TX_JWT_SECRET` — must be changed from default (framework warns if insecure)
- `N3TX_SQLITE_DB` — database file path
- `ANTHROPIC_API_KEY` — if using Anthropic LLM provider for agents

**Optional env vars:**
- `N3TX_HOST`, `N3TX_PORT`, `N3TX_API_URL` — network config
- `N3TX_DEBUG` — controls OpenAPI docs visibility and error detail
- `N3TX_SSR` — server-side rendering mode
- `N3TX_JWT_EXPIRY_HOURS` — token lifetime
- `GENERATE_DOCS` — set to `false` to skip auto-doc generation (used in tests)

**Secrets location:**
- Environment variables (no `.env` file committed)
- Dev defaults in `src/n3tx/core/config.py` and `src/n3tx/core/authorize/auth.py`
- Insecure secret detection: `src/n3tx/core/authorize/auth.py` → `INSECURE_SECRETS` set

## Webhooks & Callbacks

**Incoming:**
- `POST /mcp` — MCP JSON-RPC 2.0 endpoint for AI agent tool calls
- `POST /{tablename}/{id}/inbox` — ActivityPub incoming activities (NetworkAP)

**Outgoing:**
- Agent tool calls route through Matrix → target actor (internal TX, not external HTTP)
- `WebTools.scrape()` makes outbound HTTP requests to arbitrary URLs via httpx
- ActivityPub outbox activities (future — currently publish-focused only)

## Lifecycle Event Broadcasting

**WebSocket Push:**
- `ActorModel._publish_lifecycle()` sends lifecycle events to subscribers
- Subscribers: `['ws']` when WebSocket adapter is enabled
- Events: `after_create`, `after_update`, `after_delete`
- Format: TX messages serialized to JSON, broadcast to all connected WS clients

---

*Integration audit: 2026-03-04*
