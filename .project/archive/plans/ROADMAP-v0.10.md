# ROADMAP v0.10: Platform Expansion

> **Theme:** From framework to platform.
> Connect N3TX to the agentic ecosystem, the Fediverse, and the static web.
> Every new capability is a protocol adapter or schema consumer — not a rewrite.

**Generated**: 2026-03-02
**Branch**: `v0.10` (from `v0.9`)
**Status**: Planning
**Depends on**: v0.9 (polymorphic types, CLI, REST enhancements, MCP deepening, CT verification)

---

## Table of Contents

1. [What v0.9 Delivered](#1-what-v09-delivered)
2. [Strategic Direction for v0.10](#2-strategic-direction-for-v010)
3. [Architecture Context](#3-architecture-context)
4. [Wave 1 — Schema Agentic System](#wave-1--schema-agentic-system)
5. [Wave 2 — ActivityPub Federation](#wave-2--activitypub-federation)
6. [Wave 3 — Static Site Export](#wave-3--static-site-export)
7. [Wave 4 — SSR Strategy B + HTML Compiler Foundations](#wave-4--ssr-strategy-b--html-compiler-foundations)
8. [Wave 5 — Real-Time (WebSocket/SSE)](#wave-5--real-time-websocketsse)
9. [Wave C — Conditional Features](#wave-c--conditional-features)
10. [Decision Points & Success Criteria](#10-decision-points--success-criteria)
11. [Risk Framework](#11-risk-framework)
12. [File Index](#12-file-index)

---

## 1. What v0.9 Delivered

v0.9 deepened the schema and developer experience built on v0.8's actor infrastructure:

| Capability | Status |
|-----------|--------|
| **Security fixes** (field-level access enforcement) | Complete |
| **SSR Strategy A** (data pre-loading, -200-400ms FCP) | Complete |
| **Polymorphic Phases 1-2** (`__discriminator__`, STI, `oneOf` schema) | Complete |
| **CLI Phases 1-3** (14 commands: run, models, describe, CRUD, generate, shell) | Complete |
| **REST Enhancements** (`?fields=`, `?sort=`, `?filter[field][op]=value`) | Complete |
| **MCP Bridge Enhancement** (streaming, resources, prompts, notifications) | Complete |
| **Category Theory P0+P1** (value getter immutability, pure registration, storage adjunction, functor laws) | Complete |

**Test baseline**: Expected ~2,000+ tests (building on v0.8's 1,704).

---

## 2. Strategic Direction for v0.10

v0.10 expands N3TX from a schema-driven web framework into a schema-driven platform that connects to:

1. **The agentic ecosystem** — Full agent capabilities: LLM integration, planning loops, multi-agent coordination. "Define a model, get an agent."

2. **The Fediverse** — Full bidirectional ActivityPub federation. N3TX content appears on Mastodon, Lemmy, WordPress. Remote interactions flow back.

3. **The static web** — `n3tx export` generates deployable static websites from schema. Zero server. Zero JavaScript. Zero hosting costs.

4. **Real-time** — WebSocket bridge connecting frontend Matrix to backend Matrix. Lifecycle events push instantly to connected clients.

**Research backing:**
- Schema-Agentic research: 65% of agent infrastructure exists, 10-14 weeks for MCP-compatible single-agent system
- Decentralized Protocols research: 60-70% ready for ActivityPub, 6-10 weeks for full bidirectional federation
- Static Site research: MVP in 5-7 days, unique whitespace (no framework generates HTML from data schemas)
- SSR research: Strategy B delivers <300ms FCP, 8-12 weeks, justified only for SEO/public pages
- HTML Compiler research: 3-8x FCP improvement, ~770 LOC Python compiler, Declarative Shadow DOM ready

**The common pattern:** Every v0.10 feature is either a new NetworkAdapter, a new schema consumer, or a new Actor type — built on the infrastructure v0.8 and v0.9 established.

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

From this definition: database table, CRUD API, JSON Schema, frontend entity classes, form rendering, access control, method buttons, entity self-description, CLI commands, MCP tools, polymorphic storage (if `__discriminator__` set), federation endpoints (if `__federated__` set), and static site pages (if exported).

### Key Files (with full paths)

**Models & Serialization:**
- `src/n3tx/core/models/proto_model.py` — Base model. Schema orchestrator (`schema()` calls `proto_schema.*` pipeline). `model_response()` calls `proto_dump.*` pipeline. `__init_subclass__()` auto-injects `StorableMixin`, registers polymorphic subtypes.
- `src/n3tx/core/models/proto_schema.py` — Schema pipeline: 7+ composable `dict -> dict` stages (`base`, `strip_hidden`, `methods`, `defs`, `access`, `ui`, `metadata`, plus extensions like `polymorphic`). Register new stages via `@schema_extension(after='methods')`.
- `src/n3tx/core/models/proto_dump.py` — Dump pipeline: composable `dict -> dict` stages (`base`, `response`, plus extensions). Register via `@dump_extension(after='response')`.
- `src/n3tx/core/models/actor_model.py` — `ActorModel(Actor, ProtoModel)` bridge. CRUD via `handler_crud()`, lifecycle events, generic handler for custom methods.
- `src/n3tx/core/models/base_user.py` — Abstract base user model with `login()` and `register_user()`.
- `src/n3tx/core/models/storable_mixin.py` — CRUD operations. `list()` supports `limit`/`offset` pagination, `sort`, `filter`, `fields`.

**Actor System:**
- `src/n3tx/core/actors/actor.py` — Base actor: `actormethod`/`actorproperty` descriptors, `ActorMeta` metaclass, `use()` interceptors. Class/instance dual dispatch. `auto_register=False` kwarg available.
- `src/n3tx/core/actors/matrix.py` — Root actor and message router. Module-level `matrix` singleton. `register_adapter()` for protocol adapters.
- `src/n3tx/core/actors/tx.py` — TX message envelope: `name`, `source`, `target`, `data`, `meta`, `timestamp`, `uuid`. `reply()`, `error()`, `is_error`.
- `src/n3tx/core/actors/actor_proxy.py` — Actor interface wrapper without MI.

**API / Routes:**
- `src/n3tx/core/api/routes_fastapi.py` — Level 1/2 route factories with auth injection, pagination, `?fields`, `?sort`, `?filter`.
- `src/n3tx/core/api/network_adapter.py` — `NetworkAdapter(Actor)` base: `request()` for req/resp correlation, interceptor support.
- `src/n3tx/core/api/network_api.py` — `NetworkAPI`: HTTP REST bridge (Level 3).
- `src/n3tx/core/api/network_mcp.py` — `NetworkMCP`: MCP JSON-RPC 2.0 bridge (tools, resources, prompts, notifications).
- `src/n3tx/core/api/network_ap.py` — `NetworkAP`: ActivityPub federation bridge (outbox, inbox, WebFinger, Actor documents).
- `src/n3tx/core/api/auth_interceptor.py` — Tier 1 auth interceptor.
- `src/n3tx/core/api/discovery.py` — `/_meta`, `/.well-known/agent.json`.

**Authorization:**
- `src/n3tx/core/authorize/rules.py` — `AccessRule` base + rules: `ANYONE`, `NEVER`, `AUTHENTICATED`, `OWNER`, `ROLE`, `Where`, `FEDERATED`, `LOCAL`, `FOLLOWER`. Compose with `|`/`&`/`~`. `sql_filter()` for SQL pushdown.
- `src/n3tx/core/authorize/auth.py` — JWT: password hashing, token create/decode, `configure()`.
- `src/n3tx/core/authorize/schema.py` — Serialize access rules to JSON for schema exposure.

**Storage:**
- `src/n3tx/core/storage/sqlite_storage.py` — SQLite backend with FK hydration, `_type` discriminator queries.
- `src/n3tx/core/storage/sqlite_migration.py` — Auto-migration + Rails-style manual migrations.

**SSR:**
- `src/n3tx/core/ssr/html.py` — Schema injection, data pre-loading, CSS preloads, bundle mode.

**CLI:**
- `src/n3tx/cli/__init__.py` — Typer app entry point.
- `src/n3tx/cli/commands/*.py` — 14 commands: run, models, describe, CRUD, migrate, seed, scaffold, model, shell, docs.

**Frontend:**
- `src/n3tx/static/core/N3TX.js` — Core entity: `prototype()`, `SCHEMA()`, DynamicClass, preloaded schema/data consumption.
- `src/n3tx/static/core/Matrix.js` — Message bus / actor system.
- `src/n3tx/static/core/Actor.js` — Base actor class.
- `src/n3tx/static/components/ntx-item.js` — Item component: size methods (xs-xl).
- `src/n3tx/static/components/ntx-list.js` — List component.
- `src/n3tx/static/generators/form.js` — Formidable: schema-driven form generator.
- `src/n3tx/static/utils/Permissions.js` — Schema access rules for UI permission checks.

**App Bootstrap:**
- `src/n3tx/core/app.py` — `N3TXApp` builder + `create_app()`. `routing='direct'` or `routing='actor'`. `setup()` for CLI (no HTTP server).
- `src/n3tx/__init__.py` — Public API re-exports.

### Extension Points

1. **Schema pipeline** — `@schema_extension(after='methods')` in `proto_schema.py`.
2. **Dump pipeline** — `@dump_extension(after='response')` in `proto_dump.py`.
3. **Interceptors** — `actor.use(fn, on='inbox')` on any Actor.
4. **NetworkAdapter** — Subclass for new protocols.
5. **AccessRule** — Subclass for new auth primitives.
6. **`__init_subclass__`** — Fires for every new ProtoModel subclass.
7. **CLI** — New Typer commands in `cli/commands/`.
8. **Lifecycle events** — ActorModel publishes `after_create`/`after_update`/`after_delete` to `_subscribers`.

### Three Levels of N3TX

```python
# Level 1 — ProtoModel + direct routes
app = create_app(models=[Product], storage="sqlite:///app.db")

# Level 2 — ActorModel + direct routes
app = create_app(models=[Product], storage="sqlite:///app.db")

# Level 3 — ActorModel + NetworkAPI (full actor routing)
app = create_app(models=[Product], storage="sqlite:///app.db", routing='actor')
```

### Data Flow

```
Model Definition (Python)
    -> ProtoModel.schema()        [proto_schema pipeline: base -> strip_hidden -> methods -> defs -> access -> ui -> metadata -> polymorphic]
    -> GET /{ClassName}           [JSON Schema with everything]
    -> N3TX.SCHEMA(data)           [prototype() -> DynamicClass]
    -> <ntx-list>, <ntx-item>     [Schema-driven rendering]

MCP: schema.methods -> MCP tools/list -> AI agent calls tools/call -> TX -> ActorModel
AP:  lifecycle event -> TX -> NetworkAP -> ActivityPub Create/Update/Delete -> followers
CLI: n3tx describe Product -> N3TXApp.setup() -> Product.schema() -> Rich table
```

### Test Commands

```bash
cd /workspace/src/n3tx/core && pytest tests/unit/
cd /workspace/src/n3tx/core && pytest actors/tests/
cd /workspace/src/n3tx/core && pytest ../example/tests/
cd /workspace/src/n3tx/example && python3 main.py
```

---

## Wave 1 — Schema Agentic System

**Duration**: 10-14 weeks
**Risk**: Medium-High
**Purpose**: "Define a model, get an agent." Auto-generate MCP-compatible agents from model definitions. Full LLM integration, planning loops, and multi-agent coordination.

### Research Backing

- AI agent market: $10.9B (2026) -> $52.6B (2030), 46.3% CAGR
- 65% of agent infrastructure already exists in N3TX (Actor messaging, schema generation, ABAC, DynamicClass)
- MCP has 97M+ monthly SDK downloads, adopted by all major providers
- JSON Schema is the universal agent contract — same format N3TX produces
- Average ROI on agent investments: 171% (Google Cloud Study)
- 40% of projects canceled by 2027 — scope discipline is survival
- "Adopt for orchestration, build for integration" — our moat is the schema bridge

### Phase 0: Schema-to-Agent Card (~1 week)

Already partially done in v0.8 (`/.well-known/agent.json`). Deepen to full A2A Agent Card spec:

**Files to modify:**
- `src/n3tx/core/api/discovery.py` — Full A2A v0.4+ Agent Card generation from registered models.
- `src/n3tx/core/models/proto_schema.py` — New `@schema_extension` stage that adds agent-relevant metadata (capabilities, cost hints, reliability data).

### Phase 1: LLM Integration (~3-4 weeks)

**New files:**
- `src/n3tx/core/agents/__init__.py` — Agent system package.
- `src/n3tx/core/agents/llm_client.py` — `LLMClient` class: provider abstraction (OpenAI, Anthropic, Google). Uses `httpx` for HTTP calls. Structured output via JSON Schema constraint. Streaming support. Token counting and cost tracking.
- `src/n3tx/core/agents/agent_mixin.py` — `AgentMixin` for models: `__agent__ = True`, `__prompt__` dict (like `__ui__`), `__tools__` list. Adds `run()` method that executes a ReAct loop.

**Key pattern:** `AgentMixin` mirrors `StorableMixin` — it's injected by `__init_subclass__()` when `__agent__ = True`.

```python
class SupportAgent(ActorModel):
    __tablename__ = 'support_agents'
    __storable__ = True
    __agent__ = True
    __prompt__ = {
        'system': 'You are a support agent for an e-commerce platform.',
        'tools': ['products_list', 'products_get', 'users_get'],
    }

    name: str
    status: str = Field(default='idle')
```

### Phase 2: Agent Memory + Context (~2-3 weeks)

**New files:**
- `src/n3tx/core/agents/memory.py` — `AgentMemory(ProtoModel)`: short-term (conversation), medium-term (session), long-term (persistent). Stored via `StorableMixin`.
- `src/n3tx/core/agents/context.py` — `AgentContext`: manages tool results, conversation history, token budgets. Pruning strategies (FIFO, relevance-based, summary).

### Phase 3: Multi-Agent Coordination (~3-4 weeks)

**New files:**
- `src/n3tx/core/agents/orchestrator.py` — `AgentOrchestrator(Actor)`: routes tasks to specialized agents. Supervision: restart crashed agents. Budget enforcement: per-agent and total cost caps.
- `src/n3tx/core/agents/delegation.py` — A2A delegation support: agents discover and delegate to other agents via Agent Cards.

**Interceptors for agent safety:**
```python
@orchestrator.use(on='send')
async def cost_guard(tx: TX) -> TX:
    if tx.meta.get('cost_total', 0) > MAX_BUDGET:
        return tx.error("Budget exceeded", code=429)
    return tx
```

### Phase 4: Observability (~1-2 weeks)

**New files:**
- `src/n3tx/core/agents/trace.py` — `AgentTrace(ProtoModel)`: records every TX in an agent workflow. Stored via `StorableMixin`. Queryable via CLI (`n3tx agent:trace <id>`).
- `src/n3tx/core/agents/dashboard.py` — Agent monitoring: active agents, task completion rates, cost per task, error rates.

### Tests

- LLM client: mock provider, structured output validation, streaming, error handling
- Agent mixin: ReAct loop with mock LLM, tool call routing via Matrix, budget enforcement
- Memory: short/medium/long-term storage and retrieval, context pruning
- Multi-agent: task routing, delegation, supervision (crash recovery), cost caps
- Observability: trace recording, dashboard queries
- Integration: full agent workflow end-to-end with mock LLM

### Wave 1 Deliverable

- `__agent__ = True` on any model creates an MCP-compatible agent
- LLM integration with provider abstraction (OpenAI, Anthropic, Google)
- ReAct planning loop with tool calls routed through Matrix
- Agent memory (short/medium/long-term) via StorableMixin
- Multi-agent orchestration with supervision and cost caps
- Full observability: traces, dashboard, cost tracking
- A2A Agent Card at `/.well-known/agent.json`

---

## Wave 2 — ActivityPub Federation

**Duration**: 6-10 weeks
**Risk**: Medium
**Purpose**: Full bidirectional ActivityPub federation. N3TX apps participate in the Fediverse — content published on Mastodon, interactions flow back.

### Research Backing

- N3TX is 60-70% ready for federation (schema, self-describing entities, ABAC, Actor system)
- No framework offers model-driven federation — `__federated__ = True` is unique
- Bluesky: 40M+ users. Fediverse: 12M+ registered users.
- EU DMA review May 2026 may mandate social network interoperability
- eIDAS 2.0 November 2026 mandates digital identity wallets
- Ghost, WordPress, Flipboard shipping ActivityPub in production
- NetworkAP adapter exists in v0.8 — v0.10 completes it

### Phase 1: Publish-Only (~2-3 weeks)

**Files to modify:**
- `src/n3tx/core/api/network_ap.py` — Complete outbox delivery. ActivityStreams serialization for all CRUD lifecycle events. HTTP Signature on outgoing requests.
- `src/n3tx/core/models/proto_dump.py` — `@dump_extension` for ActivityStreams context injection (already partially implemented).

**New files:**
- `src/n3tx/core/federation/signatures.py` — HTTP Signature creation and verification (RSA-SHA256).
- `src/n3tx/core/federation/delivery.py` — Async delivery queue with retry (exponential backoff).
- `src/n3tx/core/federation/keys.py` — Per-actor RSA key generation and management.

**What ships:** Models with `__federated__ = True` produce valid ActivityPub Actor documents. Lifecycle events (create/update/delete) are serialized as Activities and delivered to followers. WebFinger makes actors discoverable. Other servers can follow N3TX users.

### Phase 2: Full Bidirectional (~3-4 weeks)

**Files to modify:**
- `src/n3tx/core/api/network_ap.py` — Complete inbox handler. Verify incoming HTTP Signatures. Process Follow/Unfollow/Create/Update/Delete activities.
- `src/n3tx/core/authorize/rules.py` — `FOLLOWER` rule evaluates against follower list.

**New files:**
- `src/n3tx/core/federation/inbox_processor.py` — Validate, authorize, and route inbound activities to ActorModels.
- `src/n3tx/core/federation/followers.py` — Follower list management (accept/reject, storage).

**What ships:** Remote Fediverse users can interact with N3TX content. Follows, likes, comments from Mastodon/Lemma/etc. are received, validated, and processed. `FOLLOWER` access rule works with real follower data.

### Phase 3: Interoperability Testing (~1-2 weeks)

**Verify against:**
- Mastodon (most popular AP server)
- Lemmy (link aggregation)
- Ghost (publishing)
- WordPress ActivityPub plugin

**Use:** [ActivityPub Rocks](https://activitypub.rocks/) test suite + custom interop tests.

### Phase 4: DID Support (~1-2 weeks, demand-gated)

**Trigger:** eIDAS 2.0 mandate (November 2026) or federation demand.

**New files:**
- `src/n3tx/core/federation/did.py` — DID document generation and resolution.
- `src/n3tx/core/models/base_user.py` — Add `did` field to BaseUser.

### Tests

- HTTP Signature: creation, verification, key rotation
- Delivery queue: retry, exponential backoff, dead letter
- ActivityStreams serialization: all activity types, JSON-LD context
- Inbox processing: signature verification, activity routing, error handling
- Follower management: follow/unfollow, follower list, FOLLOWER rule evaluation
- Interoperability: Mastodon, Lemmy, Ghost, WordPress
- Security: rate limiting, input validation, signature replay prevention

### Wave 2 Deliverable

- `__federated__ = True` produces full ActivityPub federation
- Publish-only: content appears on Mastodon, followers receive updates
- Full bidirectional: inbound follows, likes, comments processed
- HTTP Signature security on all federated requests
- Async delivery queue with retry
- WebFinger discovery
- Interoperability verified against 4+ servers
- FOLLOWER access rule evaluates against real follower data

---

## Wave 3 — Static Site Export

**Duration**: 5-7 days
**Risk**: Low
**Purpose**: `n3tx export` generates a complete, deployable static website from schema + data. Zero server. Zero JavaScript. Zero hosting costs.

### Research Backing

- No framework generates static HTML from data model definitions (whitespace opportunity)
- Static sites: 3-10x faster than SPA, zero hosting costs on Cloudflare/GitHub/Netlify
- Each 0.1s faster = 8-10% more conversions in e-commerce
- N3TX's schema carries complete rendering instructions (field types, widgets, groups, access rules)
- MVP: ~980 lines of code, 5-7 engineering days
- Jamstack market: $8.6B (2025), 60% of new projects use static-first

### Implementation

**New files:**
- `src/n3tx/cli/commands/export.py` — `n3tx export` CLI command. Orchestrates the export pipeline.
- `src/n3tx/core/export/__init__.py` — Export package.
- `src/n3tx/core/export/renderer.py` — Schema-to-HTML renderer. Reads schema properties, widget hints, groups, field order. Generates HTML using Jinja2 macros. ~200 LOC.
- `src/n3tx/core/export/css.py` — CSS `:host` transformer for Web Component styles -> static styles. ~80 LOC.
- `src/n3tx/core/export/orchestrator.py` — Export pipeline: enumerate models, query data, render pages, write files. ~150 LOC.
- `src/n3tx/core/export/templates/` — Base HTML template, list template, detail template. ~300 LOC.

**Schema-to-HTML mapping:**
```
Schema Property                    HTML Output
=============                      ===========
properties.name.type: "string"     <h2>Widget Pro</h2>
properties.price.ui.widget:        <div class="currency">$29.99</div>
  "currency"
ui.field_order                     Fields in specified sequence
ui.groups.main                     <fieldset><legend>Main</legend>...</fieldset>
access.read: ANYONE                Included in public export
methods.comment                    Rendered as description (no invocation)
$defs.Comment                      Nested child entity rendering
```

**CSS-only interactivity (no JavaScript):**
- Accordions: `<details>/<summary>`
- Tabs: `:target` pseudo-class
- Theme toggle: `prefers-color-scheme` + `:checked`
- Responsive cards: Container queries
- Modals: `<dialog>` element

**Irreducible JavaScript:** ~600-800 bytes for form submission (<400 bytes gzipped).

**Output:**
```
dist/
  index.html          # Home page with model listing
  products/
    index.html        # Product list (paginated)
    1.html            # Product detail
    2.html
  users/
    index.html
  styles.css          # Extracted component styles
  sitemap.xml         # Auto-generated
```

### Tests

- Export pipeline: end-to-end (models -> dist/ files)
- Schema rendering: each widget type, field order, groups
- CSS transformation: `:host` to class selectors
- Pagination: correct page counts, prev/next links
- Access rules: only `read: ANYONE` models exported
- Lighthouse: target 95-100 on exported pages
- Deployability: verify on Cloudflare Pages / GitHub Pages

### Wave 3 Deliverable

- `n3tx export` generates a complete static website
- Schema-driven HTML rendering (no templates to write)
- CSS-only interactivity (zero JavaScript for most interactions)
- Dark/light theme support
- Sitemap and pagination
- Deployable to any CDN for free
- Lighthouse score 95-100

---

## Wave 4 — SSR Strategy B + HTML Compiler Foundations

**Duration**: 2-4 weeks
**Risk**: Medium
**Purpose**: Server-side HTML rendering for SEO and sub-300ms FCP on public pages. The HTML compiler pre-generates templates at server startup.

### Research Backing

- Strategy B: FCP < 300ms, full SEO capability, content visible with zero JavaScript
- Schema-compiled templates yield 3-8x FCP improvement
- ~770 LOC pure Python compiler, runs at server startup
- Declarative Shadow DOM: 94.38% browser support
- 70% of per-entity render cost is compilable at build time
- Islands architecture (Astro pattern) = highest dev satisfaction

### 4a. Python Schema Renderer (~2-3 weeks)

**New files:**
- `src/n3tx/core/ssr/renderer.py` — Python schema-to-HTML renderer. Reads same schema properties as `form.js`. Generates display-mode HTML. ~300 LOC.
- `src/n3tx/core/ssr/compiler.py` — Template compiler: at server start, generates HTML template strings with `{{slot}}` markers for each model x size x permission variant. ~250 LOC.
- `src/n3tx/core/ssr/dsd.py` — Declarative Shadow DOM wrapper. Wraps compiled templates in `<template shadowrootmode="open">`. ~100 LOC.

**Key design:** The compiler generates **templates** (structure), not **pages** (data). Data is injected at runtime. Templates are cached and reused across requests. This gives SSG-like speed with CSR-like freshness.

**Variant templates:** For each model + size (xs/sm/md/lg/xl), generate permission variants (anon, auth, owner, admin). The component selects the right variant based on user permissions.

### 4b. Hydration Support (~1 week)

**Files to modify:**
- `src/n3tx/static/components/ntx-item.js` — Add `hydrate()` method that detects server-rendered HTML in Shadow DOM and attaches event listeners without re-rendering.

**Hydration strategy:** Progressive Islands with Embedded Schema.
1. Server renders HTML with Declarative Shadow DOM (instant paint, zero JS)
2. Tiny bootstrap (~3KB) initializes actor system and parses embedded schemas
3. Above-fold components hydrate immediately
4. Below-fold components hydrate on scroll (IntersectionObserver)
5. Method buttons hydrate on hover/focus
6. Edit forms hydrate on user interaction

### Tests

- Renderer parity: compare Python output to JavaScript output for same schema + data
- Compiler: verify template generation for all widget types, sizes, permission variants
- DSD: valid Declarative Shadow DOM output
- Hydration: server-rendered HTML preserved, JS enhances without re-render
- Performance: FCP < 300ms on target mobile devices
- XSS: all user data properly escaped (markupsafe)

### Wave 4 Deliverable

- Python schema renderer produces same HTML as JavaScript frontend
- Template compiler pre-generates permission-variant templates at startup
- Declarative Shadow DOM for instant first paint
- Progressive hydration: above-fold first, below-fold on scroll
- FCP < 300ms for public pages
- SEO: fully crawlable HTML with zero JavaScript

---

## Wave 5 — Real-Time (WebSocket/SSE)

**Duration**: 1-2 weeks
**Risk**: Low-Medium
**Purpose**: Connect frontend Matrix to backend Matrix. Lifecycle events push instantly to connected clients.

### Research Backing

- Frontend Matrix already routes TX messages
- Backend Matrix already routes TX messages
- The gap: they don't talk to each other (only via HTTP request/response)
- WebSocket bridge = real-time updates are free (no separate pub/sub system)
- SSE fallback for environments where WebSocket is blocked

### Implementation

**New files:**
- `src/n3tx/core/api/network_ws.py` — `NetworkWebSocket(NetworkAdapter)`: WebSocket bridge. Serializes/deserializes TX messages. Manages connected clients. Broadcasts lifecycle events.
- `src/n3tx/static/core/transport/WebSocketAdapter.js` — Frontend WebSocket adapter. Replaces/augments HTTP NetworkAdapter for real-time connections.

**Files to modify:**
- `src/n3tx/core/app.py` — `create_app(realtime=True)` wires WebSocket endpoint and registers `NetworkWebSocket` adapter.
- `src/n3tx/static/core/Matrix.js` — Auto-connect to WebSocket when available. Fall back to HTTP.

**Message flow:**
```
Backend ActorModel publishes lifecycle event
    -> TX to subscribers
    -> NetworkWebSocket broadcasts to connected clients
    -> Frontend Matrix receives TX
    -> Routes to affected N3TX actors
    -> Components re-render with new data
```

**Security:** WebSocket connections authenticated via JWT token in initial handshake. Per-connection access scoping (only receive events for models the user can read).

### Tests

- WebSocket connection: authenticate, maintain, reconnect on disconnect
- TX serialization: round-trip (Python TX -> JSON -> JS TX -> JSON -> Python TX)
- Lifecycle broadcast: create/update/delete events reach connected clients
- Access scoping: user only receives events for readable models
- SSE fallback: verify same functionality over SSE
- Concurrent connections: 100+ clients receiving real-time updates

### Wave 5 Deliverable

- Frontend Matrix ↔ Backend Matrix via WebSocket
- Real-time updates: entity changes push instantly to connected clients
- Authentication on WebSocket connections
- Per-connection access scoping
- SSE fallback for restricted environments
- `create_app(realtime=True)` one-liner to enable

---

## Wave C — Conditional Features

These features proceed only when specific trigger conditions are met.

### C1. Polymorphic Phases 3-4 (5-7 days + 3-5 days)

**Trigger:** Concrete use case requiring mixed-type frontend lists or unified polymorphic API endpoints.

**Phase 3:** Mixed-type frontend rendering, type-aware forms, type selector in create forms.
**Phase 4:** Polymorphic routes (`GET /content` returns all types), per-subtype auth composition.

**Files:** `src/n3tx/static/components/ntx-item.js`, `src/n3tx/static/components/ntx-list.js`, `src/n3tx/static/generators/form.js`, `src/n3tx/core/api/routes_fastapi.py`.

### C2. Category Theory P2 (11-15 days)

**Trigger:** 3+ bugs from message-type/data-shape mismatches (typed actor messages), OR config-mutation bugs (configuration monoid), OR test isolation pain >1 hour/week (pure registration phase 2).

**Items:**
- Typed actor messages (TX with generic payload types)
- Configuration monoid (immutable config composition)
- Pure registration phase 2 (eliminate all global mutable state)

### C3. CLI Phase 4 — TUI Dashboard (~20 hours)

**Trigger:** SSH-based server administration demand, OR 100+ external users.

**New file:** `src/n3tx/cli/commands/admin.py` — `n3tx admin` launches a Textual-based TUI dashboard. Entity browsing, CRUD, migration management, server monitoring.

### C4. ATProtocol Support (10-16 weeks)

**Trigger:** Bluesky ecosystem reaches critical mass, OR AT governance risk settles.

**New files:** `src/n3tx/core/federation/atproto/` — Lexicon generation, DID integration, XRPC endpoints, Merkle Search Tree storage.

### C5. DID-based Identity (2-3 weeks)

**Trigger:** eIDAS 2.0 mandate (November 2026) or federation demand.

---

## 10. Decision Points & Success Criteria

### Decision Points

| After Wave | Question | If Yes | If No |
|-----------|---------|--------|-------|
| Wave 1 Ph0 | Are 3+ internal users querying via MCP? | Proceed to Phase 1 (LLM). | Investigate adoption blockers. |
| Wave 1 Ph1 | Task completion rate > 90%? Cost per task < $0.15? | Proceed to Phase 2 (multi-agent). | Iterate on single agent. |
| Wave 2 Ph1 | Does content appear correctly on Mastodon? | Proceed to Phase 2 (bidirectional). | Fix interop issues. |
| Wave 3 | Do 10+ users run `n3tx export` within 3 months? | Invest in Phase 2 (incremental builds, images). | Deprioritize. |
| Wave 4 | Does the business require SEO or sub-500ms FCP? | Complete renderer + compiler. | Strategy A from v0.9 is sufficient. |
| Wave 5 | Is there demand for real-time updates? | Ship. | Defer. |

### Success Criteria

| Metric | Target |
|--------|--------|
| All existing tests pass | Zero regression |
| MCP tools discoverable by Claude/Cursor | Verified with real client |
| Agent task completion | > 90% on constrained domain |
| Agent cost per task | < $0.15 |
| ActivityPub interop | Verified with Mastodon + 1 other server |
| Static export Lighthouse | 95-100 |
| SSR Strategy B FCP | < 300ms on mobile |
| WebSocket latency | < 50ms for lifecycle event delivery |

---

## 11. Risk Framework

| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|-----------|
| **LLM cost runaway** | High | Critical | Per-task token budgets, max iteration limits, circuit breakers, per-agent cost caps. Phase 0 has zero LLM cost. |
| **Agent hallucination** | High | Critical | Strict JSON Schema mode (100% compliance). ABAC enforced at route layer, not prompt. Validate all outputs. |
| **40% agent project cancelation rate** | High | High | Phased approach with metric-based triggers. Each phase delivers standalone value. |
| **ActivityPub compatibility issues** | Medium | Medium | Start publish-only. Test against 4+ servers. Interop test suite in CI. |
| **Federation security surface** | Medium | Critical | All endpoints rate-limited. HTTP Signature verification. Input validation. Security audit budget ($5-20K). |
| **ATProtocol governance** (single company) | Medium | Critical | Start with ActivityPub (multi-stakeholder W3C). ATProto behind abstraction layer. |
| **Static export data staleness** | Medium | High | Position for infrequently-changing content. Clear freshness docs. Webhook rebuild in future. |
| **SSR server/client render divergence** | High | High | Schema-driven renders same spec. Parity tests in CI. Version hash + CSR fallback. |
| **XSS in SSR content** | Medium | Critical | `markupsafe.escape()`, Jinja2 autoescape, CSP headers, never `| safe` on user data. |
| **Over-engineering** | Medium | Medium | Each wave has a trigger condition. No speculative investment. Monthly cost reviews. |

---

## 12. File Index

### Existing Files (Modified in v0.10)

| File | Waves |
|------|:-----:|
| `src/n3tx/core/api/network_ap.py` | W2 |
| `src/n3tx/core/api/network_mcp.py` | W1 |
| `src/n3tx/core/api/discovery.py` | W1 |
| `src/n3tx/core/authorize/rules.py` | W2 |
| `src/n3tx/core/models/actor_model.py` | W1, W5 |
| `src/n3tx/core/models/base_user.py` | W2 (C5) |
| `src/n3tx/core/app.py` | W5 |
| `src/n3tx/static/core/Matrix.js` | W5 |
| `src/n3tx/static/components/ntx-item.js` | W4 |
| `src/n3tx/core/ssr/html.py` | W4 |

### New Files (Created in v0.10)

| File | Wave | Purpose |
|------|:----:|---------|
| `src/n3tx/core/agents/__init__.py` | W1 | Agent system package |
| `src/n3tx/core/agents/llm_client.py` | W1 | LLM provider abstraction |
| `src/n3tx/core/agents/agent_mixin.py` | W1 | `__agent__ = True` mixin |
| `src/n3tx/core/agents/memory.py` | W1 | Short/medium/long-term memory |
| `src/n3tx/core/agents/context.py` | W1 | Context management, token budgets |
| `src/n3tx/core/agents/orchestrator.py` | W1 | Multi-agent coordination |
| `src/n3tx/core/agents/delegation.py` | W1 | A2A agent delegation |
| `src/n3tx/core/agents/trace.py` | W1 | Agent observability |
| `src/n3tx/core/federation/signatures.py` | W2 | HTTP Signature creation/verification |
| `src/n3tx/core/federation/delivery.py` | W2 | Async delivery queue with retry |
| `src/n3tx/core/federation/keys.py` | W2 | RSA key generation/management |
| `src/n3tx/core/federation/inbox_processor.py` | W2 | Inbound activity processing |
| `src/n3tx/core/federation/followers.py` | W2 | Follower list management |
| `src/n3tx/core/export/__init__.py` | W3 | Static export package |
| `src/n3tx/core/export/renderer.py` | W3 | Schema-to-HTML renderer |
| `src/n3tx/core/export/css.py` | W3 | CSS :host transformer |
| `src/n3tx/core/export/orchestrator.py` | W3 | Export pipeline orchestrator |
| `src/n3tx/core/export/templates/` | W3 | HTML templates |
| `src/n3tx/cli/commands/export.py` | W3 | `n3tx export` CLI command |
| `src/n3tx/core/ssr/renderer.py` | W4 | Python schema-to-HTML renderer |
| `src/n3tx/core/ssr/compiler.py` | W4 | Template compiler (server startup) |
| `src/n3tx/core/ssr/dsd.py` | W4 | Declarative Shadow DOM wrapper |
| `src/n3tx/core/api/network_ws.py` | W5 | WebSocket bridge adapter |
| `src/n3tx/static/core/transport/WebSocketAdapter.js` | W5 | Frontend WebSocket adapter |

---

## Appendix A: Version Progression

```
v0.7  — Schema-driven web framework (ProtoModel, CRUD, JSON Schema, frontend)
v0.8  — Actor unification (Actor/Matrix/TX, NetworkAdapters, MCP, AP skeleton, two-tier auth)
v0.9  — Schema deepening (polymorphism, CLI, REST enhancements, MCP bridge, CT verification)
v0.10 — Platform expansion (agents, federation, static export, SSR compiler, real-time)
```

Each version builds on the last. v0.10 features are protocol adapters and schema consumers that plug into the infrastructure established in v0.8 and deepened in v0.9.

## Appendix B: Effort Summary

| Wave | Feature | Effort | Dependency |
|------|---------|--------|-----------|
| 1 | Schema Agentic System | 10-14 weeks | v0.9 MCP bridge |
| 2 | ActivityPub Federation | 6-10 weeks | v0.8 NetworkAP |
| 3 | Static Site Export | 5-7 days | v0.9 CLI |
| 4 | SSR Strategy B + HTML Compiler | 2-4 weeks | v0.9 SSR Strategy A |
| 5 | Real-Time (WebSocket/SSE) | 1-2 weeks | v0.8 Actor/Matrix |
| C | Conditional features | Variable | Various triggers |

**Total for Waves 1-5**: ~22-32 weeks (assumes sequential; parallelizable).
**Critical path**: Wave 1 (agents) is longest; Waves 3 and 5 can run in parallel with Wave 2.

---

*This roadmap is self-contained for clean-context agents. All file paths reference the actual codebase. Research documents are in `.traces/research/` and `.traces/vision/`. The v0.8 roadmap (`ROADMAP-v0.8.md`) and v0.9 roadmap (`ROADMAP-v0.9.md`) provide foundational context.*
