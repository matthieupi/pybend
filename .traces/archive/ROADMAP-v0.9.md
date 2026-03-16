# ROADMAP v0.9: Schema Deepening & Developer Experience

> **Theme:** Harden the foundation, unlock the developer.
> Make the schema pipeline richer, the access rules provably correct,
> the CLI ergonomic, and the REST surface production-grade.

**Generated**: 2026-03-02
**Branch**: `v0.9` (from `v0.8`)
**Status**: Planning
**Depends on**: v0.8 (actor system, schema/dump pipelines, NetworkAPI/MCP adapters, two-tier auth, SSR infrastructure)

---

## Table of Contents

1. [What v0.8 Delivered](#1-what-v08-delivered)
2. [Strategic Direction for v0.9](#2-strategic-direction-for-v09)
3. [Architecture Context](#3-architecture-context)
4. [Wave 1 — Security Fixes + SSR Strategy A](#wave-1--security-fixes--ssr-strategy-a)
5. [Wave 2 — Polymorphic System Phases 1-2](#wave-2--polymorphic-system-phases-1-2)
6. [Wave 3 — CLI Phases 1-3](#wave-3--cli-phases-1-3)
7. [Wave 4 — REST Enhancements](#wave-4--rest-enhancements)
8. [Wave 5 — MCP Bridge Enhancement](#wave-5--mcp-bridge-enhancement)
9. [Wave 6 — Category Theory P0+P1](#wave-6--category-theory-p0p1)
10. [Decision Points & Success Criteria](#10-decision-points--success-criteria)
11. [Risk Framework](#11-risk-framework)
12. [File Index](#12-file-index)

---

## 1. What v0.8 Delivered

v0.8 transformed N3TX from a framework with an actor frontend into a unified actor platform:

| Capability | Key Files | Status |
|-----------|-----------|--------|
| **Actor/Matrix/TX backend** | `actors/actor.py`, `actors/matrix.py`, `actors/tx.py` | Complete |
| **Schema pipeline** (7 composable stages) | `models/proto_schema.py` | Complete |
| **Dump pipeline** (composable serialization) | `models/proto_dump.py` | Complete |
| **ActorModel** (Actor + ProtoModel bridge) | `models/actor_model.py` | Complete |
| **ActorProxy** (actor interface without MI) | `actors/actor_proxy.py` | Complete |
| **Interceptor mechanism** (`use()`) | `actors/actor.py` | Complete |
| **NetworkAdapter** base class | `api/network_adapter.py` | Complete |
| **NetworkAPI** (HTTP REST Level 3) | `api/network_api.py` | Complete |
| **NetworkMCP** (MCP JSON-RPC 2.0) | `api/network_mcp.py` | Complete |
| **NetworkAP** (ActivityPub federation) | `api/network_ap.py` | Complete |
| **Two-tier auth** (boundary + handler) | `api/auth_interceptor.py` | Complete |
| **SSR infrastructure** (schema injection, bundler) | `ssr/html.py` | Complete |
| **Federation access rules** (NEVER, FEDERATED, LOCAL, FOLLOWER) | `authorize/rules.py` | Complete |
| **Discovery endpoints** (`/_meta`, `/.well-known/agent.json`) | `api/discovery.py` | Complete |
| **AccessRule algebra** (107 verified laws) | `tests/unit/test_access_algebra.py` | Complete |

**Test baseline**: 1,704 tests pass (1,074 unit + 242 actor + 388 integration).

---

## 2. Strategic Direction for v0.9

v0.8 built the actor infrastructure. v0.9 deepens the schema and developer experience so that the infrastructure is **usable, production-ready, and provably correct**.

**Three pillars:**

1. **Schema Richness** — Polymorphic types, richer REST surface, enhanced MCP tooling. The schema carries more intent, which means agents, federation, and frontend derive more behavior automatically.

2. **Developer Experience** — CLI entry point, SSR quick-win, security fixes. The time from `pip install` to working application drops from 8-10 minutes to under 5 minutes.

3. **Correctness Guarantees** — Category theory P0+P1 fixes and verification. AccessRule algebra tests, storage adjunction, DynamicClass functor laws. The schema pipeline is provably correct, not just tested.

**Research backing:**
- Polymorphic research: 60-70% of machinery exists, Phases 1-2 deliver core differentiator in 5-7 days
- CLI research: N3TX is 70% done with zero code, Typer is the clear choice (66M monthly downloads)
- Category theory research: 8 impurities identified, P0+P1 capture 80% of value in 12-19 days
- SSR research: Strategy A costs ~50 lines and eliminates 200-400ms waterfall
- GraphQL research: Decisive "no" — sparse fieldsets (`?fields=`) capture 70-80% of GraphQL's value

---

## 3. Architecture Context

> This section is standalone — it provides everything a clean-context agent needs
> to understand N3TX's architecture without reading CLAUDE.md or prior conversations.

### Core Principle

**The model is the app.** A Python model definition is the single source of truth for the entire stack:

```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __access__ = {
        'read': ANYONE, 'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'), 'delete': ROLE('admin'),
    }
    __ui__ = {
        'field_order': ['name', 'price', 'description'],
        'groups': {'main': ['name', 'description', 'price']},
    }

    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}})
    description: str = Field(default='')
    comments: Optional[ListRef[Comment]] = Field(default=[])

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> str: ...
```

From this single definition, the framework derives: database table, CRUD API endpoints, JSON Schema, frontend entity classes, form rendering, access control, method buttons, entity self-description, pagination, and navigation.

### Key Files (with full paths)

**Models & Serialization:**
- `src/n3tx/core/models/proto_model.py` — Base model. Schema orchestrator calls `proto_schema.*` pipeline. `model_response()` calls `proto_dump.*` pipeline.
- `src/n3tx/core/models/proto_schema.py` — Schema pipeline: 7 composable `dict -> dict` stages (`base`, `strip_hidden`, `methods`, `defs`, `access`, `ui`, `metadata`). Extensible via `@schema_extension`.
- `src/n3tx/core/models/proto_dump.py` — Dump pipeline: composable `dict -> dict` stages (`base`, `response`). Extensible via `@dump_extension`.
- `src/n3tx/core/models/actor_model.py` — `ActorModel(Actor, ProtoModel)` bridge. CRUD via `handler_crud()`.
- `src/n3tx/core/models/base_user.py` — Abstract base user model with `login()` and `register_user()`.
- `src/n3tx/core/models/storable_mixin.py` — CRUD operations. `list()` supports `limit`/`offset` pagination.
- `src/n3tx/core/models/ref.py` — `ListRef[T]` type for collection references.

**Actor System:**
- `src/n3tx/core/actors/actor.py` — Base actor: `actormethod`/`actorproperty` descriptors, `ActorMeta` metaclass, `use()` interceptors. Class/instance dual dispatch.
- `src/n3tx/core/actors/matrix.py` — Root actor and message router. Module-level `matrix` singleton.
- `src/n3tx/core/actors/tx.py` — TX message envelope: `name`, `source`, `target`, `data`, `meta`, `timestamp`, `uuid`. `reply()`, `error()`, `is_error`.
- `src/n3tx/core/actors/actor_proxy.py` — Actor interface wrapper without MI.

**API / Routes:**
- `src/n3tx/core/api/routes_fastapi.py` — Level 1/2 route factories with auth injection and pagination.
- `src/n3tx/core/api/network_adapter.py` — `NetworkAdapter(Actor)` base: `request()` for req/resp correlation via Future.
- `src/n3tx/core/api/network_api.py` — `NetworkAPI`: HTTP REST bridge (Level 3 actor routing).
- `src/n3tx/core/api/network_mcp.py` — `NetworkMCP`: MCP JSON-RPC 2.0 bridge.
- `src/n3tx/core/api/network_ap.py` — `NetworkAP`: ActivityPub federation bridge.
- `src/n3tx/core/api/auth_interceptor.py` — Tier 1 auth interceptor for NetworkAPI.
- `src/n3tx/core/api/discovery.py` — `/_meta`, `/.well-known/agent.json` endpoints.

**Authorization:**
- `src/n3tx/core/authorize/rules.py` — `AccessRule` base + rules: `ANYONE`, `NEVER`, `AUTHENTICATED`, `OWNER`, `ROLE`, `Where`, `FEDERATED`, `LOCAL`, `FOLLOWER`.
- `src/n3tx/core/authorize/auth.py` — JWT: password hashing, token create/decode.
- `src/n3tx/core/authorize/schema.py` — Serialize access rules to JSON for schema exposure.

**Storage:**
- `src/n3tx/core/storage/sqlite_storage.py` — SQLite backend with FK hydration.
- `src/n3tx/core/storage/sqlite_migration.py` — Auto-migration + Rails-style manual migrations.

**SSR:**
- `src/n3tx/core/ssr/html.py` — Schema injection, CSS preloads, bundle mode.

**Frontend:**
- `src/n3tx/static/core/N3TX.js` — Core entity: `prototype()` factory, `SCHEMA()`, DynamicClass.
- `src/n3tx/static/core/Matrix.js` — Message bus / actor system.
- `src/n3tx/static/core/Actor.js` — Base actor class.
- `src/n3tx/static/components/ntx-item.js` — Item component: size methods (xs-xl), render dispatch.
- `src/n3tx/static/components/ntx-list.js` — List component.
- `src/n3tx/static/generators/form.js` — Formidable: schema-driven form generator.
- `src/n3tx/static/utils/Permissions.js` — Reads schema access rules for UI permission checks.

**App Bootstrap:**
- `src/n3tx/core/app.py` — `N3TXApp` builder + `create_app()` one-liner. `routing='direct'` (Level 1/2) or `routing='actor'` (Level 3).
- `src/n3tx/__init__.py` — Public API re-exports.

### Extension Points

1. **Schema pipeline** — `@schema_extension(after='methods')` registers new `dict -> dict` stages in `proto_schema.py`.
2. **Dump pipeline** — `@dump_extension(after='response')` registers new serialization stages in `proto_dump.py`.
3. **Interceptors** — `actor.use(fn, on='inbox')` registers TX interceptors on any Actor method.
4. **NetworkAdapter** — Subclass `NetworkAdapter` for new protocols (HTTP, WS, MCP, AP).
5. **AccessRule** — Subclass `AccessRule` for new authorization primitives.
6. **`__init_subclass__`** — ProtoModel's hook fires for every new model subclass.

### Three Levels of N3TX

```python
# Level 1 — ProtoModel + direct routes (no actors)
app = create_app(models=[Product], storage="sqlite:///app.db")

# Level 2 — ActorModel + direct routes (actor capabilities, same HTTP layer)
app = create_app(models=[Product], storage="sqlite:///app.db")

# Level 3 — ActorModel + NetworkAPI (full actor routing)
app = create_app(models=[Product], storage="sqlite:///app.db", routing='actor')
```

### Data Flow

```
Model Definition (Python)
    -> ProtoModel.schema()        [proto_schema pipeline: base -> strip_hidden -> methods -> defs -> access -> ui -> metadata]
    -> GET /{ClassName}           [JSON Schema with $schema, $id, properties, methods, access, ui, $defs]
    -> N3TX.SCHEMA(data)           [prototype() -> DynamicClass with typed getters/setters/methods]
    -> <ntx-list>, <ntx-item>     [Schema-driven rendering: forms, permissions, method buttons]
```

### Test Commands

```bash
# Framework unit tests
cd /workspace/src/n3tx/core && pytest tests/unit/

# Actor system tests
cd /workspace/src/n3tx/core && pytest actors/tests/

# Integration tests
cd /workspace/src/n3tx/core && pytest ../example/tests/

# Start server
cd /workspace/src/n3tx/example && python3 main.py
```

---

## Wave 1 — Security Fixes + SSR Strategy A

**Duration**: 3-5 days
**Risk**: Low
**Purpose**: Fix known security gaps and eliminate 200-400ms of loading latency.

### Motivation

The frontend performance audit identified security vulnerabilities in the permission system and the SSR infrastructure is ready to deliver immediate latency improvements.

### 1a. Frontend Security Fixes (~2-3 days)

**Problem**: `Permissions.js` evaluates access rules client-side without proper backend enforcement for field-level visibility. An attacker can modify the JavaScript to bypass UI permission checks.

**Files to modify:**
- `src/n3tx/static/utils/Permissions.js` — Ensure `canView()` and `canAction()` properly evaluate `OWNER` rules against the current user.
- `src/n3tx/static/components/ntx-item.js` — Verify edit/delete button visibility uses both schema `access` and resource `user_owner`.
- `src/n3tx/core/api/routes_fastapi.py` — Add server-side field stripping for fields where `access.view` denies the current user.

**Spec:**
- Field-level `access.view` enforcement must happen server-side (defense in depth)
- Protected fields (`__protected_fields__`) must never appear in edit forms
- Error responses must never leak field values the user cannot see

### 1b. SSR Strategy A — Data Pre-loading (~1-2 days)

**Problem**: The frontend makes 2 sequential network requests (schema + data) before rendering. The server already has both.

**Research**: SSR Strategy A costs ~50 lines of Python and eliminates 200-400ms of waterfall latency. The frontend already has `#consumePreloadedSchema()` and `#consumePreloadedData()` in N3TX.js.

**Files to modify:**
- `src/n3tx/core/ssr/html.py` — Already has `build_schema_tags()` and injection functions. Wire data pre-loading for the initial page entities.
- `src/n3tx/core/app.py` — Ensure `create_app()` serves the SSR-enhanced HTML with embedded schemas.
- `src/n3tx/static/core/N3TX.js` — Verify `#consumePreloadedSchema()` and `#consumePreloadedData()` work with the injected data.

**Spec:**
- Server injects `<script type="application/json" data-ntx-schema="{Model}">{schema}</script>` for each registered model
- Server injects `<script type="application/json" data-ntx-data="{tablename}">{data}</script>` for initial list data
- Frontend detects pre-loaded data and skips network requests
- FCP improves by 200-400ms (measured before/after)

**Expected result:**
```
BEFORE: HTML -> JS -> Schema fetch (200ms) -> Data fetch (200ms) -> Render
AFTER:  HTML (with embedded schema+data) -> JS -> Render
```

### Wave 1 Deliverable

- Server-side field-level access enforcement (defense in depth)
- SSR data pre-loading eliminates 200-400ms waterfall
- All existing tests pass

---

## Wave 2 — Polymorphic System Phases 1-2

**Duration**: 5-7 days
**Risk**: Low-Medium
**Purpose**: Add STI discriminator storage and `oneOf` schema generation. The core differentiator: no other framework generates discriminated union JSON Schema from model definitions.

### Research Backing

- 60-70% of machinery exists (ProtoModel inheritance, `__init_subclass__`, `$defs`, DynamicClass, per-model access rules)
- Industry standard: Stripe (`PaymentMethod.type`), WordPress (`post_type` = STI powering 43% of web), Notion (50+ block types)
- Pydantic v2 natively supports `Annotated[Union[...], Discriminator('type')]`
- Adding a new type: 5 minutes (1 file) vs. 2 hours (9-14 files) in manual approach
- Competitive position: no framework offers schema-propagated polymorphism

### Phase 1: Storage Layer (~2-3 days)

**Files to modify:**
- `src/n3tx/core/models/proto_model.py` — In `__init_subclass__()`, detect `__discriminator__` ClassVar, register subtypes in `__subtypes__` dict on the base class.
- `src/n3tx/core/storage/sqlite_migration.py` — When model has `__discriminator__`, add `_type TEXT NOT NULL DEFAULT '{classname}'` column.
- `src/n3tx/core/storage/sqlite_storage.py` — `list()` and `get()` add `WHERE _type = ?` for subtype queries. `create()` sets `_type = model_class.__name__` before INSERT.

**What the developer writes:**
```python
class Content(ActorModel):
    __tablename__ = 'content'
    __storable__ = True
    __discriminator__ = '_type'

    title: str
    author: str

class Article(Content):
    body: str

class Video(Content):
    video_url: str
    duration: int = 0
```

**What they get:**
- `content` table with `_type TEXT NOT NULL` column
- `Article.list()` returns only articles (WHERE _type = 'Article')
- `Content.list()` returns everything
- `Article.create(...)` auto-sets `_type = 'Article'`

### Phase 2: Schema Layer (~3-4 days)

**Files to modify:**
- `src/n3tx/core/models/proto_schema.py` — New `polymorphic()` stage (via `@schema_extension`): when `__discriminator__` is set, wrap subtype schemas in `oneOf` with `discriminator` mapping.
- `src/n3tx/static/core/N3TX.js` — `SCHEMA()` recognizes `oneOf` + `discriminator`, creates per-subtype DynamicClasses from `$defs`.

**Schema output format:**
```json
{
  "$id": "http://localhost:5000/Content",
  "oneOf": [
    {"$ref": "#/$defs/Article"},
    {"$ref": "#/$defs/Video"}
  ],
  "discriminator": {
    "propertyName": "_type",
    "mapping": {
      "Article": "#/$defs/Article",
      "Video": "#/$defs/Video"
    }
  },
  "$defs": {
    "Article": {"$id": "...", "properties": {...}, "access": {...}},
    "Video": {"$id": "...", "properties": {...}, "access": {...}}
  }
}
```

### Tests

- STI CRUD: create, read, list (all types), list (single type), update, delete
- Schema output: `oneOf` + `discriminator` presence, `$defs` per subtype
- Frontend: `N3TX.SCHEMA()` creates per-subtype DynamicClasses
- Regression: all existing schema tests unchanged
- Edge cases: empty subtypes, base-only queries, access rules per subtype

### Wave 2 Deliverable

- `__discriminator__` ClassVar enables STI with zero boilerplate
- `oneOf` + `discriminator` JSON Schema output (unique in the market)
- Frontend creates per-subtype DynamicClasses automatically
- All existing tests pass

---

## Wave 3 — CLI Phases 1-3

**Duration**: ~3 days
**Risk**: Low
**Purpose**: Ship a focused CLI that makes N3TX accessible from the terminal. The 5-minute test: `pip install n3tx[cli]` to running app with data in under 5 minutes.

### Research Backing

- Frameworks with strong CLIs see 25-40% faster onboarding; 63% of developers consider DX for retention
- N3TX is ~70% done with zero code (model registry, schema generation, CRUD layer, migration system exist)
- Typer: 19K stars, 66M monthly PyPI downloads, same author as FastAPI
- Top 5 commands account for ~80% of usage across all frameworks
- Annual maintenance: 15-20% of initial build (scope discipline critical)

### Phase 1: Foundation (~1 day)

**New files:**
- `src/n3tx/cli/__init__.py` — Typer app entry point
- `src/n3tx/cli/commands/run.py` — `n3tx run` (wraps server start)
- `src/n3tx/cli/commands/models.py` — `n3tx models` (list registered models)
- `src/n3tx/cli/commands/describe.py` — `n3tx describe <Model>` (print schema)
- `src/n3tx/cli/commands/migrate.py` — `n3tx migrate:status` (migration status)

**Prerequisites:**
- Extract `N3TXApp.setup()` from `build()` in `src/n3tx/core/app.py`. The first ~12 lines of `build()` (auth configure, register models, set up storage) must work without creating FastAPI routes. This unblocks all CLI commands.

**Key pattern:** CLI commands are thin wrappers (~5-10 lines each) calling existing functions. No business logic in CLI commands.

### Phase 2: Daily Operations (~1 day)

**New files:**
- `src/n3tx/cli/commands/crud.py` — `n3tx list <table>`, `n3tx get <table> <id>`, `n3tx create <Model>`, `n3tx update <table> <id>`, `n3tx delete <table> <id>`
- `src/n3tx/cli/commands/seed.py` — `n3tx seed` (run seed script)

**Schema-driven prompts:** The `create` command generates interactive prompts from schema properties — required fields, validation constraints, widget hints. No other framework CLI does this.

### Phase 3: Generation + Shell (~1 day)

**New files:**
- `src/n3tx/cli/commands/scaffold.py` — `n3tx scaffold <Model>` (generate files from schema)
- `src/n3tx/cli/commands/model.py` — `n3tx model <Name> field:type` (generate model file)
- `src/n3tx/cli/commands/shell.py` — `n3tx shell` (REPL with models pre-imported)
- `src/n3tx/cli/commands/docs.py` — `n3tx docs` (generate/serve docs)

**Integration:**
- Add `[project.scripts] n3tx = "n3tx.cli:app"` to `pyproject.toml`
- Add `[cli]` extras: `pip install n3tx[cli]` installs Typer + Rich

### Tests

- CliRunner tests for each command
- The 5-minute test: new developer installs and creates running app
- Schema-driven prompt validation matches Pydantic constraints

### Wave 3 Deliverable

- 14 CLI commands covering serve, inspect, CRUD, migrate, generate, shell
- Schema-driven interactive create prompts (unique feature)
- Thin wrapper architecture (zero business logic in CLI)
- `n3tx run` as primary server start command

---

## Wave 4 — REST Enhancements

**Duration**: 5-7 days
**Risk**: Low
**Purpose**: Make the REST API production-grade with sparse fieldsets, sorting, filtering, and pagination improvements.

### Research Backing

- GraphQL research: "decisive no" — but sparse fieldsets (`?fields=`) capture 30-50% payload reduction
- REST still powers 83% of web services; 61.5% of orgs run GraphQL but mostly alongside REST
- `?fields=` is ~50 lines of code for 70-80% of GraphQL's field selection value

### 4a. Sparse Fieldsets (~2-3 days)

**Files to modify:**
- `src/n3tx/core/api/routes_fastapi.py` — Parse `?fields=name,price,id` query param. Strip unlisted fields from response dict.
- `src/n3tx/core/api/network_api.py` — Mirror `?fields=` support for Level 3 routes.
- `src/n3tx/core/storage/sqlite_storage.py` — Optional: SELECT only requested columns for DB-level optimization.

**Spec:**
```bash
GET /products?fields=name,price,id
# Returns: [{"name": "Widget", "price": 29.99, "id": 1, "$schema": "...", "$id": "..."}]
# $schema and $id are always included (self-description is non-negotiable)
```

### 4b. Sorting (~1-2 days)

**Files to modify:**
- `src/n3tx/core/api/routes_fastapi.py` — Parse `?sort=price` or `?sort=-created_at` (prefix `-` for DESC).
- `src/n3tx/core/storage/sqlite_storage.py` — Add `ORDER BY` clause to list queries.

**Spec:**
```bash
GET /products?sort=-price        # Price descending
GET /products?sort=name,-price   # Name ascending, then price descending
```

### 4c. Filtering (~2-3 days)

**Files to modify:**
- `src/n3tx/core/api/routes_fastapi.py` — Parse `?filter[price][gt]=50&filter[name][contains]=Widget`.
- `src/n3tx/core/storage/sqlite_storage.py` — Translate filters to parameterized WHERE clauses.

**Operators:** `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`, `starts_with`, `in`.

**Spec:**
```bash
GET /products?filter[price][gt]=50&filter[name][contains]=Pro
# WHERE price > 50 AND name LIKE '%Pro%'
```

**Security:** All filter values are parameterized (SQL injection prevention). Only allow filtering on fields present in schema properties.

### 4d. Pagination Improvements (~1 day)

**Files to modify:**
- `src/n3tx/core/api/routes_fastapi.py` — Add `Link` header with `rel="next"`, `rel="prev"` for discoverability.

### Tests

- Sparse fieldsets: verify only requested fields returned, `$schema`/`$id` always present
- Sorting: ascending, descending, multi-field, invalid field name
- Filtering: each operator, SQL injection prevention, non-existent fields rejected
- Pagination Link headers: presence, correctness, boundary conditions

### Wave 4 Deliverable

- `?fields=` for 30-50% payload reduction
- `?sort=` for flexible ordering
- `?filter[field][op]=value` for server-side filtering
- Link headers for pagination discoverability
- All query parameters compose: `?fields=name,price&sort=-price&filter[price][gt]=50&limit=10`

---

## Wave 5 — MCP Bridge Enhancement

**Duration**: 2-3 weeks
**Risk**: Medium
**Purpose**: Evolve the MCP adapter from basic tool exposure to a production-grade bridge with streaming, resource exposure, and prompt templates.

### Research Backing

- MCP hit 97M+ monthly SDK downloads, adopted by OpenAI, Google, Microsoft
- N3TX's schema IS the tool definition — the gap is protocol features, not architecture
- Agent market: $10.9B in 2026, 46.3% CAGR to $52.6B by 2030
- Phase 0 (basic MCP) complete in v0.8; v0.9 deepens it

### 5a. MCP Streaming Support (~3-5 days)

**Files to modify:**
- `src/n3tx/core/api/network_mcp.py` — Add SSE streaming for `tools/call` responses. Support `stream: true` in tool call arguments.
- `src/n3tx/core/api/network_adapter.py` — Add streaming correlation support to `request()`.

### 5b. MCP Resources (~3-5 days)

**Files to modify:**
- `src/n3tx/core/api/network_mcp.py` — Implement `resources/list` and `resources/read`. Map registered models to MCP resources. Entity instances are resource URIs.

**Spec:**
```json
{"jsonrpc": "2.0", "method": "resources/list", "id": 1}
// Returns: resources for each model (schema, entity list)

{"jsonrpc": "2.0", "method": "resources/read",
 "params": {"uri": "n3tx://products/42"}, "id": 2}
// Returns: entity data as MCP resource content
```

### 5c. MCP Prompt Templates (~2-3 days)

**Files to modify:**
- `src/n3tx/core/api/network_mcp.py` — Implement `prompts/list` and `prompts/get`. Auto-generate prompt templates from model schemas (e.g., "Create a new Product with the following fields...").

### 5d. MCP Notifications + Change Tracking (~3-5 days)

**Files to modify:**
- `src/n3tx/core/api/network_mcp.py` — Implement `notifications/resources/updated` when entities change (via ActorModel lifecycle events).
- `src/n3tx/core/models/actor_model.py` — Wire lifecycle events to MCP notification dispatch.

### Tests

- Streaming: verify SSE format, partial response delivery, timeout handling
- Resources: verify resource listing, entity reading, URI format
- Prompt templates: verify generation from schema, parameter substitution
- Notifications: verify lifecycle event triggers notification

### Wave 5 Deliverable

- MCP streaming for long-running tool calls
- MCP resources: models and entities as discoverable resources
- MCP prompt templates auto-generated from schemas
- MCP notifications: real-time change tracking for AI agents
- Full MCP spec compliance (tools, resources, prompts, notifications)

---

## Wave 6 — Category Theory P0+P1

**Duration**: 12-19 days
**Risk**: Low-Medium
**Purpose**: Fix the 3 highest-priority impurities identified by CT analysis and add algebraic verification tests. This captures 80% of the CT value.

### Research Backing

- 8 identifiable impurities break categorical laws in N3TX
- P0+P1 yield 40-60% reduction in integration test surface area
- Industry validation: Jane Street, Meta, Standard Chartered, Elm, Redux all use CT structures under plain-English names
- The Elm model: CT correctness internally, simple interfaces externally

### P0: Fix Now (8-12 days)

#### 6a. Value Getter Immutability (~2-3 days)

**Problem**: The value getter in `N3TX.js` `prototype()` mutates `_data` in-place when injecting `$schema` and `$id`. This violates referential transparency.

**Files to modify:**
- `src/n3tx/static/core/N3TX.js` — Value getter returns a new object with `$schema`/`$id` spread in, rather than mutating `_data`.

#### 6b. Pure Registration (~2-3 days)

**Problem**: `register_model()` has global side effects (mutates `registered_models` dict, calls `create_table()`). This makes tests order-dependent and prevents isolated testing.

**Files to modify:**
- `src/n3tx/core/utils/registrar.py` — Return registration results instead of mutating globals. `N3TXApp.build()` collects results and applies them.
- `src/n3tx/core/app.py` — Use pure registration in `build()`.

#### 6c. Exception-to-TX Error Mapping (~2-3 days)

**Problem**: Some code paths raise exceptions that bypass the TX error channel, breaking composition chains.

**Files to modify:**
- `src/n3tx/core/models/actor_model.py` — Ensure `handler_crud()` catches all exceptions and returns `tx.error()`.
- `src/n3tx/core/api/network_api.py` — Map HTTP exceptions to TX error responses.

#### 6d. sql_filter Completeness (~1-2 days)

**Problem**: `sql_filter()` returns `None` for some rule combinations, which absorbs into nothing rather than propagating correctly.

**Files to modify:**
- `src/n3tx/core/authorize/rules.py` — Ensure all rules return a valid SQL fragment or explicit `1=1` / `1=0` for ANYONE/NEVER.

### P1: Verify (4-7 days)

#### 6e. Storage Adjunction Tests (~2-3 days)

**Purpose**: Verify `get(create(m)).scalar_fields == m.scalar_fields` for all storable field types.

**New file:**
- `src/n3tx/core/tests/unit/test_storage_adjunction.py` — Round-trip tests for every field type (str, int, float, bool, Optional, Ref, ListRef).

#### 6f. DynamicClass Functor Tests (~2-3 days)

**Purpose**: Verify the `Schema -> DynamicClass` transformation preserves structure.

**New file:**
- `src/n3tx/static/tests/unit/test_dynamicclass_functor.js` — Verify: schema properties -> getters/setters, methods -> callables, $defs -> nested classes, type validation preserved.

### Wave 6 Deliverable

- Value getter is referentially transparent (no mutation)
- Registration is pure (no global side effects in the function)
- All code paths return TX errors (no exception bypass)
- `sql_filter()` is complete (no None absorption)
- Storage round-trip verified for all field types
- DynamicClass functor laws verified
- CT vocabulary stays internal — zero changes to public API or user-facing docs

---

## 10. Decision Points & Success Criteria

### Decision Points

| After Wave | Question | If Yes | If No |
|-----------|---------|--------|-------|
| Wave 1 | Is FCP < 1000ms after SSR Strategy A? | Proceed. Defer Strategy B to v0.10. | Investigate root cause; may need Strategy B sooner. |
| Wave 2 | Is there a concrete use case for mixed-type frontend lists? | Proceed to Phases 3-4 in v0.10. | Ship Phases 1-2, gather feedback. |
| Wave 3 | Does the 5-minute test pass for a new developer? | Ship. | Fix top 3 friction points. |
| Wave 5 | Are MCP clients actually using the enhanced features? | Continue deepening. | Focus on core tools/list + tools/call. |
| Wave 6 | Did integration test surface decrease by 40-60%? | P1 validated. P2 deferred to demand-gated. | Investigate why; adjust approach. |

### Success Criteria

| Metric | Target |
|--------|--------|
| All existing tests pass | Zero regression |
| FCP (with SSR Strategy A) | < 1000ms (from ~1500-2000ms) |
| Polymorphic schema output | Valid `oneOf` + `discriminator` |
| CLI 5-minute test | New developer: install to running app < 5 min |
| `?fields=` payload reduction | 30-50% on typical endpoints |
| MCP spec compliance | tools + resources + prompts + notifications |
| CT: storage round-trip | All field types pass adjunction test |
| CT: AccessRule algebra | All 12 algebraic laws verified |

---

## 11. Risk Framework

| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|-----------|
| Polymorphic STI table bloat | Low | Medium | Document max 5-8 subtypes. N3TX targets sub-100K rows. CTI migration path documented. |
| CLI scope creep beyond 15 commands | Medium | Medium | Strict rule: no business logic in CLI commands. Each command is a thin wrapper. |
| REST filter SQL injection | Low | Critical | All filter values parameterized. Only allow filtering on schema-declared fields. |
| MCP protocol spec changes | Low | Low | Thin adapter (~300 LOC). Cheap to update. |
| CT over-engineering creep | Medium | Medium | Any CT-inspired change must cite a specific bug class it prevents. |
| SSR data pre-loading XSS | Medium | Critical | `markupsafe.escape()` on all user data. CSP headers. |

---

## 12. File Index

### Existing Files (Modified in v0.9)

| File | Waves |
|------|:-----:|
| `src/n3tx/core/models/proto_model.py` | W2 |
| `src/n3tx/core/models/proto_schema.py` | W2 |
| `src/n3tx/core/models/actor_model.py` | W5, W6 |
| `src/n3tx/core/api/routes_fastapi.py` | W1, W4 |
| `src/n3tx/core/api/network_api.py` | W4 |
| `src/n3tx/core/api/network_mcp.py` | W5 |
| `src/n3tx/core/api/network_adapter.py` | W5 |
| `src/n3tx/core/authorize/rules.py` | W6 |
| `src/n3tx/core/storage/sqlite_storage.py` | W2, W4 |
| `src/n3tx/core/storage/sqlite_migration.py` | W2 |
| `src/n3tx/core/ssr/html.py` | W1 |
| `src/n3tx/core/app.py` | W1, W3, W6 |
| `src/n3tx/core/utils/registrar.py` | W6 |
| `src/n3tx/static/core/N3TX.js` | W2, W6 |
| `src/n3tx/static/utils/Permissions.js` | W1 |
| `src/n3tx/static/components/ntx-item.js` | W1 |

### New Files (Created in v0.9)

| File | Wave | Purpose |
|------|:----:|---------|
| `src/n3tx/cli/__init__.py` | W3 | CLI entry point (Typer app) |
| `src/n3tx/cli/commands/*.py` | W3 | CLI commands (run, models, describe, crud, etc.) |
| `src/n3tx/core/tests/unit/test_polymorphic.py` | W2 | Polymorphic storage + schema tests |
| `src/n3tx/core/tests/unit/test_storage_adjunction.py` | W6 | Storage round-trip verification |
| `src/n3tx/core/tests/unit/test_rest_enhancements.py` | W4 | Sparse fieldsets, sorting, filtering tests |
| `src/n3tx/static/tests/unit/test_dynamicclass_functor.js` | W6 | DynamicClass functor law tests |

---

*This roadmap is self-contained for clean-context agents. All file paths reference the actual codebase. Research documents are in `.traces/research/` and `.traces/vision/`. The v0.8 roadmap (`ROADMAP-v0.8.md`) provides foundational context.*
