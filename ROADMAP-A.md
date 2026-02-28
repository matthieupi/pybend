# ROADMAP-A: Strategic Evolution of PyBend

> **Schema as Capability Manifest**
> From rendering framework to agent-accessible, federatable, algebraically-verified platform.

**Generated**: 2026-02-26
**Branch**: `v0.7.0`
**Status**: Strategic vision roadmap. Parallel work exists in `ROADMAP-B.md`.

---

## Table of Contents

1. [Context: What PyBend Is Today](#1-context-what-pybend-is-today)
2. [Strategic Thesis](#2-strategic-thesis)
3. [Research Foundations](#3-research-foundations)
4. [The Reinforcing Triangle](#4-the-reinforcing-triangle)
5. [Five Cross-Cutting Primitives](#5-five-cross-cutting-primitives)
6. [Wave 1: Category-Theoretic Foundation](#wave-1-category-theoretic-foundation)
7. [Wave 2: Schema as Agent Protocol](#wave-2-schema-as-agent-protocol)
8. [Wave 3: Decentralized + Agentic Shared Infrastructure](#wave-3-decentralized--agentic-shared-infrastructure)
9. [Wave 4: Ecosystem Maturation](#wave-4-ecosystem-maturation-demand-gated)
10. [Deferred Themes](#10-deferred-themes)
11. [Theme Cross-Reference Matrix](#11-theme-cross-reference-matrix)
12. [Risk and Decision Framework](#12-risk-and-decision-framework)
13. [Success Metrics](#13-success-metrics)

---

## 1. Context: What PyBend Is Today

PyBend is a schema-driven Python/FastAPI framework where **model definitions are the single source of truth** for the entire application stack. A developer writes a Python model class; the framework derives everything else:

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
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

From this single definition, PyBend generates:

| Concern | How It's Derived |
|---------|-----------------|
| **Database table + migrations** | `__storable__` triggers `StorableMixin` injection via `__init_subclass__()` |
| **CRUD API endpoints** | `register_routes()` reads `__tablename__` and field types |
| **JSON Schema** | `ProtoModel.schema()` via Pydantic, enriched with `methods`, `access`, `ui`, `$defs` |
| **Frontend entity classes** | `NTT.SCHEMA()` -> `prototype()` -> DynamicClass with typed getters/setters |
| **Form rendering** | `form.js` reads `schema.properties`, `ui.widget`, `ui.field_order`, `ui.groups` |
| **Access control** | `__access__` rules composed with `\|`/`&`/`~`, serialized to JSON Schema, enforced at route layer + frontend |
| **Custom method buttons** | `@expose_route` appears in `schema.methods`, rendered by `<ntt-method>` |
| **Entity self-description** | `model_dump(response=True)` injects `$schema` (schema URL) and `$id` (instance URL) |

### Key Architecture Components

- **Backend**: Python/FastAPI. Models in `src/pybend/core/models/`, routes in `src/pybend/core/api/`, storage in `src/pybend/core/storage/`, auth in `src/pybend/core/authorize/` (standalone package, zero PyBend imports).
- **Frontend**: Vanilla JS Web Components. Core in `src/pybend/static/core/` (NTT.js, Matrix.js, Actor.js, Router.js, TX.js), components in `src/pybend/static/components/` (ntt-item, ntt-list, ntt-router, ntt-element, ntt-method), form generation in `src/pybend/static/generators/form.js`.
- **Bootstrap**: Three levels: `create_app()` (one-liner), `PyBendApp` (builder), raw primitives (`register_model` + `register_routes`).
- **Message Bus**: Actor model via Matrix.js. Actors communicate through TX message envelopes. The frontend is essentially a message-passing system where components react to SCHEMA, READ, DESCRIBE, UPDATE, ATTACH messages.

### What the JSON Schema Carries

A `GET /Product` response returns a JSON Schema document that is far richer than standard JSON Schema:

```
GET /Product -> JSON Schema
  $schema    -> meta-schema URL
  $id        -> this schema's URL
  properties -> field definitions with type, validation, ui.widget, ui.placeholder, access
  ui         -> field_order, groups, renderer (component tags)
  access     -> model-level ABAC rules (serialized)
  methods    -> callable endpoints with route, parameters, returns, access
  $defs      -> nested/related model schemas (each with their own access, ui, methods)
```

**This richness is the strategic asset.** The schema doesn't just describe types -- it carries behavioral metadata: how to render, who can access, what actions exist, how entities relate. This is what makes the evolution described in this roadmap possible.

---

## 2. Strategic Thesis

> **PyBend's schema is not a rendering specification -- it is a capability manifest.**

Today, the schema drives one consumer: the browser frontend. But the same schema carries everything needed to:

| Consumer | What It Reads From Schema |
|----------|--------------------------|
| **AI Agent (MCP/OpenAI)** | `methods` -> tool definitions, `properties` -> parameter types, `access` -> permission boundaries |
| **Federated Peer (ActivityPub)** | `$id` -> globally resolvable entity, `properties` -> object shape, `methods` -> interaction verbs |
| **Terminal CLI/TUI** | `properties` -> form fields, `ui.widget` -> widget hints, `ui.groups` -> layout |
| **Static Site Generator** | `properties` -> page content, `ui.field_order` -> display sequence, `access` -> public/private filter |
| **Microservice Peer** | `$schema` -> service contract, `methods` -> available operations, `access` -> authorization requirements |

The strategic evolution is to make the schema **composable** (via Category Theory), **machine-accessible** (via AI/Agentic protocols), and **portable** (via Decentralized identity and federation). These three concerns form a reinforcing triangle where investment in any one accelerates the other two.

### What We Are NOT Building

This roadmap explicitly avoids:

- **A general-purpose AI agent framework.** LangGraph has $260M funding and 127K GitHub stars. We don't compete with orchestration -- we provide the schema infrastructure that agents consume.
- **A full ActivityPub/AT Protocol server.** Federation is a capability layer, not a rewrite. `__federated__ = True` is opt-in per model.
- **A rendering performance framework.** SSR, HTML compilation, and static site generation are valuable but are rendering concerns, not protocol concerns. They come after the strategic core.
- **A GraphQL migration.** The research concluded decisively against it. PyBend's JSON Schema already delivers 70-80% of GraphQL's value. The remaining gap is closed with `?fields=` and enhanced `?populate=`.

---

## 3. Research Foundations

This roadmap is built on extensive research across 10 themes. Each theme was analyzed for proposed capabilities, primitives touched, cross-cutting impact, and implementation effort. The full research lives in `.traces/vision/` and `.traces/research/`.

### Theme Inventory

| # | Theme | Research Files | Core Finding |
|---|-------|---------------|--------------|
| 1 | **Category Theory** | `Category-theory-summary.md`, `Category-theory-propositions.md`, `Category-theory-whitepaper.md`, `05-category-theory-analysis.md`, `05-improving-purity.md` | PyBend already embodies categorical structures (functors, algebras, adjunctions) but has 8 "impurities" that cause silent-failure bugs. Fixing 3 high-priority ones eliminates an entire bug class and makes the schema pipeline composable. |
| 2 | **AI Agents** | `AI-agents-summary.md`, `05-ai-agents-analysis.md`, `05-schema-as-agent-contract.md` | The AI ecosystem converged on JSON Schema as the universal tool definition format. PyBend's schema already carries 65% of what agent frameworks need. The gap is a mechanical translation layer (~200 LOC), not an architectural change. |
| 3 | **Schema-Agentic System** | `Schema-agentic-system-summary.md`, `Schema-agentic-system-propositions.md`, `Schema-agentic-system-whitepaper.md`, `05-schema-agentic-system-analysis.md`, `05-schema-as-agent-protocol.md`, `05-schema-driven-agents-analysis.md` | Deep analysis of how PyBend's existing Actor/Matrix/TX messaging maps to agent communication, how `@expose_route` maps to tool declaration, and how the ABAC system maps to agent permission scoping. Proposes `AgentMixin`, `@expose_tool`, and Python Actor/Matrix port. |
| 4 | **Decentralized Protocols** | `Decentralized-protocols-summary.md`, `Decentralized-protocols-propositions.md`, `Decentralized-protocols-whitepaper.md`, `05-decentralized-protocols-analysis.md`, `05-identity-data-portability.md` | PyBend's self-describing entities (`$schema`/`$id`) are 60-70% convergent with federation protocols. `FederationAdapter` Protocol, DID identity, WebFinger, event sourcing, and schema translation enable federation as an additive layer. EU regulatory tailwinds (DMA May 2026, eIDAS Nov 2026). |
| 5 | **Polymorphic System** | `Polymorphic-system-summary.md`, `05-polymorphic-system-analysis.md`, `05-schema-evolution-strategy.md` | `__discriminator__` ClassVar enables Single Table Inheritance with automatic `oneOf` + discriminator JSON Schema output. No competing framework offers schema-propagated polymorphism. Agent types are natural polymorphic subtypes. |
| 6 | **Microservices** | `Microservices-summary.md`, `05-microservices-analysis.md`, `05-schema-as-service-contract.md` | PyBend is already closer to microservice-ready than most frameworks. `create_app()` is a service factory; JSON Schema eliminates schema drift. Schema versioning, RemoteStorage adapter, and CloudEvents are the key additions. |
| 7 | **CLI/TUI** | `CLI-TUI-summary.md`, `CLI-TUI-propositions.md`, `CLI-TUI-whitepaper.md`, `05-cli-tui-analysis.md`, `05-schema-driven-tui-rendering.md` | PyBend is 70% of the way to a complete CLI with zero new code. The critical unlock is `PyBendApp.setup()` -- decoupling model registration from HTTP server creation. No Python library generates TUI forms from JSON Schema (greenfield opportunity). |
| 8 | **HTML Compiler** | `HTML-compiler-summary.md`, `html-compiler-report.md`, `05-html-compiler-analysis.md`, `05-static-shell-dynamic-islands.md` | 70% of rendering decisions are deterministic at build time. A Python-side schema template compiler could pre-generate HTML, but this is a rendering optimization -- strategically deferred. |
| 9 | **SSR** | `SSR-summary.md`, `05-ssr-analysis.md`, `05-hydration-strategies.md` | Strategy A (embed schema+data as `<script>` tags) eliminates 200-400ms latency with ~50 lines of code. Strategy B (full Python renderer + Declarative Shadow DOM) provides SEO. Both are rendering concerns -- strategically deferred. |
| 10 | **Static Site Generation** | `Static-site-summary.md`, `05-static-site-analysis.md` | `pybend export` CLI command generating static HTML from schema. First SSG that generates pages from a data model schema. Rendering concern -- strategically deferred. |
| 11 | **GraphQL** | `05-graphql-analysis.md`, `05-migration-patterns.md` | Decisive "no" to GraphQL adoption. PyBend's JSON Schema already delivers 70-80% of GraphQL's value. Targeted REST enhancements (`?fields=`, enhanced `?populate=`) close the gap at 5% of the cost. |
| 12 | **Micro-Frontend** | `05-micro-frontend-analysis.md` | PyBend's Web Components + Actor model = 70% micro-frontend ready. Phase 0 (import maps, modulepreload) is free. Full MFE architecture is an organizational scaling concern, triggered by team growth thresholds. |

### Revised Strategic Priority Scores

The three priority themes (AI/Agentic, Category Theory, Decentralization) form the strategic core. Other themes are scored by how much they serve or depend on this core:

| Theme | Cross-Cut Score | Strategic Value | Rationale |
|-------|:-:|:-:|---|
| **Category Theory** | 9/10 | **10** | Foundation for everything. Every CT fix makes AI + Decentralized work better. Composable pipeline is the single most enabling change. |
| **AI Agents + Schema-Agentic** | 9/10 | **10** | Primary value driver. Makes PyBend relevant to the largest ecosystem shift in software (AI agents). |
| **Decentralized Protocols** | 8/10 | **9** | Shares 5+ primitives with AI/Agentic. Regulatory tailwind. Portable identity benefits agents too. |
| **Polymorphic System** | 8/10 | **8** | Agent types ARE polymorphic. Schema unions enable protocol-level type discrimination. |
| **CLI/TUI** | 8/10 | **7** | `setup()` extraction is critical for agents. CLI is how agents introspect models. TUI is deferred. |
| **Microservices** | 8/10 | **7** | Schema versioning serves agents and federation. RemoteStorage is demand-gated. |
| **HTML Compiler** | 8/10 | **5** | Rendering optimization. Not strategic for AI/Decentralized. Deferred. |
| **SSR** | 7/10 | **5** | Rendering concern. Strategy A (50 lines) is trivial when needed. Deferred. |
| **Static Site** | 7/10 | **4** | Rendering concern. Lowest strategic alignment. Deferred. |
| **GraphQL** | 6/10 | **4** | Research said "no." Sparse fieldsets are a nice-to-have. |
| **Micro-Frontend** | 6/10 | **4** | Organizational scaling concern. Phase 0 is free; rest waits for team growth. |

---

## 4. The Reinforcing Triangle

The three priority themes are not independent -- they form a mutually reinforcing system where investment in any vertex accelerates the other two:

```
              CATEGORY THEORY
             (structural purity)
            /                    \
      composable               algebraic
      schema pipeline          ABAC guarantees
          /                          \
   AI / AGENTIC    <-------->    DECENTRALIZED
   (schema as                    (schema as
    tool contract)                federation contract)
          \                          /
        shared infrastructure:
        - Schema translation protocol
        - Python Actor/Matrix port
        - Event sourcing / audit trail
        - Schema versioning
        - DID-based portable identity
        - Discovery at well-known URLs
```

### How Each Edge Works

**Category Theory -> AI/Agentic:**
- The composable schema pipeline means adding an MCP translation step is "append one function to a list" -- not "modify a 118-line monolith."
- The `Result[T,E]` type makes agent tool call responses structurally unambiguous -- agents never see a "success" that's actually an error (the 200-OK bug class).
- Boolean algebra law tests on AccessRule guarantee that agent-specific rules like `BUDGET(remaining__gt=0) & DELEGATION_DEPTH(max=3)` compose correctly with existing rules like `OWNER | ROLE('admin')`.

**Category Theory -> Decentralized:**
- The composable pipeline means adding an ActivityStreams translation step is the same pattern as adding MCP.
- The `Result` type makes federation message delivery structurally sound -- a failed delivery is an `Err`, not a swallowed exception.
- The storage adjunction round-trip tests guarantee data fidelity for federated entity sync.

**AI/Agentic <-> Decentralized (shared primitives):**

| Shared Primitive | Agent Use | Federation Use |
|-----------------|-----------|---------------|
| **Python Actor/Matrix** | Backend agent-to-agent messaging with supervision and durable state | Federation delivery queues and protocol message routing |
| **SchemaTranslator Protocol** | Schema -> MCP tool definitions | Schema -> ActivityStreams JSON-LD or AT Protocol Lexicon |
| **Event sourcing (`__auditable__`)** | Agent reasoning traces, cost tracking audit trail | Hash-chained mutation events for tamper detection |
| **`$hash` on entity responses** | Agent data verification (was the tool call result intact?) | Content-addressable sync, cache invalidation |
| **Schema versioning** | Tool definition stability (agents don't break when models update) | Protocol compatibility across federation peers |
| **DID identity** | Agents get portable, verifiable identity across systems | Cross-deployment auth without centralized user DB |
| **Well-known discovery** | `/.well-known/agent.json` (A2A Agent Card) | `/.well-known/webfinger` (Fediverse actor discovery) |
| **`@expose_tool` / `@expose_route`** | Tool metadata (cost, timeout, destructive hints) | Federation method exposure |
| **Composable ABAC rules** | `BUDGET`, `RATE_LIMIT`, `DELEGATION_DEPTH` | `LOCAL`, `FEDERATED`, `FOLLOWER`, `LABELED`, `DID_OWNER` |

---

## 5. Five Cross-Cutting Primitives

Analysis across all 10 themes reveals that **the same 5 foundational changes appear repeatedly** as prerequisites. These are the highest-ROI investments because each one unblocks multiple themes simultaneously.

### 5.1 Schema Pipeline Decomposition
**Source**: Category Theory research
**Effort**: ~5 days
**Themes Unblocked**: 7 of 10

**The Problem**: `ProtoModel.schema()` is a 118-line monolithic classmethod that generates the entire JSON Schema in one pass. Every theme that needs to transform the schema (compile to HTML, translate to MCP tools, generate GraphQL SDL, add federation metadata, inject polymorphic `oneOf`) must work around this monolith.

**The Fix**: Decompose into 7 composable classmethods, each a `Dict -> Dict` endomorphism:

```python
# Current: one monolithic method
@classmethod
def schema(cls) -> dict:
    # 118 lines of interleaved concerns...

# Proposed: composable pipeline
@classmethod
def schema(cls) -> dict:
    s = cls._schema_base()           # Pydantic core schema
    s = cls._schema_strip_hidden(s)  # Remove display=False fields
    s = cls._schema_methods(s)       # Inject @expose_route methods
    s = cls._schema_defs(s)          # Process $defs (nested models)
    s = cls._schema_access(s)        # Serialize ABAC rules
    s = cls._schema_ui(s)            # Inject __ui__ configuration
    s = cls._schema_metadata(s)      # Add $schema, $id, __name__, __tablename__
    return s
```

**Why It Matters**: Once the pipeline is decomposed, adding a new transformation is trivial:

```python
# MCP translation: just append one step
s = cls._schema_mcp_tools(s)  # Add MCP-compatible tool definitions

# Federation metadata: append one step
s = cls._schema_federation(s)  # Add ActivityStreams @context mapping

# Polymorphic unions: append one step
s = cls._schema_discriminator(s)  # Wrap subtypes in oneOf + discriminator
```

Each step is independently testable, independently overridable by subclasses, and independently documentable. The pipeline is just a list -- themes don't compete for space in a monolith.

### 5.2 `PyBendApp.setup()` Extraction
**Source**: CLI/TUI research
**Effort**: ~4 hours
**Themes Unblocked**: 6 of 10

**The Problem**: Currently, `PyBendApp.build()` (lines 141-159 of `app.py`) performs model registration, storage configuration, auth setup, AND FastAPI route creation in one method. You cannot bootstrap PyBend models without starting a web server.

**The Fix**: Extract lines 141-159 into a `setup()` method:

```python
class PyBendApp:
    def setup(self):
        """Configure auth, register models, setup storage. No HTTP."""
        authorize.configure(...)
        for model in self._models:
            register_model(model, storage=self._storage)
        # ... migrations, joins, etc.

    def build(self) -> FastAPI:
        """Full HTTP app. Calls setup() first."""
        self.setup()
        register_routes(registered_models)
        return self._app
```

**Why It Matters**: Every non-browser consumer needs models without HTTP:

| Consumer | Why It Needs `setup()` |
|----------|----------------------|
| **MCP Server** | Reads `registered_models` to generate tool definitions. Doesn't need FastAPI routes. |
| **CLI** (`pybend describe Product`) | Reads `ProtoModel.schema()` to display model info. Doesn't need HTTP. |
| **Static Site Exporter** | Calls `StorableMixin.list()` to fetch data. Doesn't need routes. |
| **Agent Runtime** | Uses `StorableMixin` CRUD for agent state. May run its own protocol (MCP JSON-RPC, not HTTP REST). |
| **Test Harness** | Needs models + storage without starting uvicorn. |
| **Federation Worker** | Processes inbox deliveries. Needs models but may use its own transport. |

### 5.3 `model_dump()` / `model_dump_response()` Split + Result Type
**Source**: Category Theory research
**Effort**: ~4 days
**Themes Unblocked**: 5 of 10

**The Problem (model_dump)**: `model_dump(response=True)` is a boolean-flag bifurcation. The same function does two different things depending on a boolean: plain dict (for storage) vs. dict + `$schema`/`$id` metadata (for API responses). This is called from 6 sites in `routes_fastapi.py` and `sqlite_storage.py`, and the dual behavior makes it easy to pass the wrong variant to the wrong consumer.

**The Fix**: Two named methods:

```python
def model_dump(self) -> dict:
    """Pure data extraction. For storage, internal use."""
    return super().model_dump(...)

def model_dump_response(self) -> dict:
    """Data + $schema/$id metadata. For API responses, federation, agents."""
    data = self.model_dump()
    data['$schema'] = f"{API_URL}/{self.__class__.__name__}"
    data['$id'] = f"{API_URL}/{self.__tablename__}/{self.id}"
    return data
```

**The Problem (Result)**: Model methods like `Product.favorite()` return error messages as plain strings with HTTP 200. The frontend sees "success," calls `pull()` to refresh -- and nothing happened. The error is invisible at the point of origin and manifests as a mysterious "stale data" bug downstream.

**The Fix**: A lightweight Result type:

```python
# In core/utils/result.py (~60 lines)
@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    def map(self, f): return Ok(f(self.value))
    def flat_map(self, f): return f(self.value)

@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
    def map(self, f): return self  # errors propagate unchanged
    def flat_map(self, f): return self

Result = Ok[T] | Err[E]
```

**Why It Matters for Agents**: When an AI agent calls a tool and receives a Result, the success/failure channel is structurally unambiguous. The agent doesn't need to parse a string to figure out if the operation worked. The route layer converts `Ok` to HTTP 200 with data and `Err` to HTTP 4xx with error details -- the agent (or MCP client) sees proper error semantics.

**Why It Matters for Federation**: When a federated peer delivers an activity and receives a Result, delivery success/failure is structurally distinct. No silent drops.

### 5.4 MCP Tool Auto-Generation
**Source**: AI Agents + Schema-Agentic research
**Effort**: ~2-4 weeks
**Themes Unblocked**: 5 of 10

**The Problem**: PyBend generates JSON Schema that carries method signatures, parameter types, access rules, and validation constraints -- exactly what AI agent protocols (MCP, OpenAI function calling, A2A) need for tool definitions. But there's no translation layer, so no AI agent can discover or call PyBend model methods.

**The Fix**: A `schema_to_mcp_tools()` function (~200 LOC) that mechanically converts schema output to MCP tool definitions:

```python
def schema_to_mcp_tools(schema: dict) -> list[dict]:
    """Convert a PyBend model schema to MCP tool definitions.

    Each CRUD operation + each @expose_route method becomes a tool.
    """
    tools = []
    # CRUD tools
    tools.append({
        "name": f"{schema['__tablename__']}_list",
        "description": f"List all {schema['__name__']} entities",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}, "offset": {"type": "integer"}}},
    })
    # ... create, get, update, delete

    # Custom method tools (from schema['methods'])
    for name, method in schema.get('methods', {}).items():
        tools.append({
            "name": f"{schema['__tablename__']}_{name}",
            "description": method.get('description', name),
            "inputSchema": method.get('parameters', {}),
        })
    return tools
```

**Why It Matters**: The day this ships, every PyBend application is instantly accessible to Claude Desktop, GPT, Cursor, and 300+ MCP clients. A developer adds `mcp=True` to `create_app()` and every model method becomes a callable tool with typed parameters and permission boundaries.

**Example**: An e-commerce app with `Product`, `User`, `Comment` models would auto-generate ~18 MCP tools (5 CRUD x 3 models + custom methods like `favorite`, `comment`, `like`) with zero additional code.

### 5.5 Python Actor/Matrix Port
**Source**: Schema-Agentic + Decentralized research (convergent)
**Effort**: ~3 weeks
**Themes Unblocked**: 4 of 10

**The Problem**: PyBend's frontend has a powerful actor-model message bus (Matrix.js, Actor.js, TX.js) that enables decoupled, typed communication between components. But the backend has no equivalent. Agent-to-agent messaging and federation message routing both need a backend message bus with supervision, durable state, and typed envelopes.

**The Fix**: A Python port of the frontend Actor/Matrix/TX system using asyncio:

```python
# Conceptual API
class AgentActor(Actor):
    async def on_message(self, tx: TX):
        if tx.action == 'TASK':
            result = await self.run(tx.data['task'])
            self.send(TX(to=tx.sender, action='RESULT', data=result))

matrix = Matrix()
matrix.register(AgentActor('planner'))
matrix.register(AgentActor('executor'))
matrix.send(TX(to='planner', action='TASK', data={'task': 'analyze data'}))
```

**Why It Matters for Agents**: Backend agents communicate through typed TX messages with supervision (restart failed agents), durable persistence (messages survive crashes via StorableMixin), and routing (Matrix knows which actor handles which message type).

**Why It Matters for Federation**: Federation inbox/outbox processing is message routing. A `FederationActor` receives inbound ActivityPub activities as TX messages, validates them, and dispatches to the appropriate model actor. Outbound activities are queued as TX messages with retry semantics.

**Why It Matters Architecturally**: The frontend already proves this pattern works. The backend port means the same conceptual architecture (actors communicating via typed messages through a routing bus) spans the entire stack, with a WebSocket bridge connecting frontend Matrix to backend Matrix for real-time sync.

---

## Wave 1: Category-Theoretic Foundation

**Duration**: 2-3 weeks
**Risk**: Zero -- internal refactors with no public API breakage
**Purpose**: Make the system structurally sound. Every subsequent wave benefits.

### Motivation

Category Theory research identified 8 "impurities" in PyBend's architecture -- places where the implicit categorical structures break. Three are high-priority because they cause real bugs or block real work:

1. **`model_dump(response=True)` bifurcation**: A boolean flag makes one function do two things. The storage layer and API layer call the same method with different flags, creating a class of bugs where the wrong variant reaches the wrong consumer.

2. **Exception-based errors masquerading as successes**: The "200-OK error" pattern. Model methods return error strings as HTTP 200. The frontend sees success, the user sees stale data, and debugging starts three layers away from the cause.

3. **Monolithic schema pipeline**: One 118-line method generates the entire schema. Every new consumer (agents, federation, polymorphism) must modify this monolith or work around it.

The CT research frames these as impurities in mathematical structures (a bifurcated morphism, a missing coproduct, a non-composable endomorphism) -- but the fixes are concrete, practical code changes that any engineer can implement.

### Tasks

#### W1.1: Schema Pipeline Decomposition
**File**: `src/pybend/core/models/proto_model.py`
**Change**: Replace the monolithic `schema()` classmethod with 7 composable steps.

Each step is a `classmethod` that takes a dict and returns a dict:
- `_schema_base()`: Call Pydantic's `model_json_schema()`, set initial structure
- `_schema_strip_hidden()`: Remove fields with `ui.display: false`
- `_schema_methods()`: Inject `@expose_route` method signatures
- `_schema_defs()`: Process `$defs` entries (nested models), inject their access/ui
- `_schema_access()`: Serialize `__access__` rules via `authorize.schema`
- `_schema_ui()`: Inject `__ui__` configuration (field_order, groups, renderer)
- `_schema_metadata()`: Add `$schema`, `$id`, `__name__`, `__tablename__`

The public `schema()` method becomes a simple pipeline:

```python
@classmethod
def schema(cls) -> dict:
    pipeline = [
        cls._schema_base, cls._schema_strip_hidden, cls._schema_methods,
        cls._schema_defs, cls._schema_access, cls._schema_ui, cls._schema_metadata,
    ]
    s = {}
    for step in pipeline:
        s = step(s)
    return s
```

**Why This Ordering**: Each step can be individually overridden by subclasses. Themes add their own steps by overriding `schema()` and inserting into the pipeline list. This is the key enabler for Waves 2-3.

**Tests**: Each step gets its own unit test. The integration test verifies that the composed output matches the current schema output (backward compatibility).

#### W1.2: `model_dump_response()` Split
**File**: `src/pybend/core/models/proto_model.py`
**Change**: Create a new `model_dump_response()` method. Migrate 6 call sites in `routes_fastapi.py` from `model_dump(response=True)` to `model_dump_response()`. The `response=True` flag is deprecated but still works (backward compat).

**Call sites to migrate**:
1. `create_route_factory()` response
2. `read_route_factory()` response
3. `read_one_route_factory()` response
4. `update_route_factory()` response
5. Custom method route handler response
6. Any place `response=True` appears in `routes_fastapi.py`

#### W1.3: Result Type
**New file**: `src/pybend/core/utils/result.py` (~60 lines)
**Change**: Frozen dataclasses `Ok[T]` and `Err[E]` with `map()` and `flat_map()`. The route layer in `routes_fastapi.py` dispatches on `Ok`/`Err` alongside existing `MethodError` handling (backward compatible -- methods that return plain strings still work).

**Example migration** (not required in Wave 1, but shows the intent):
```python
# Before (model method):
@expose_route('/favorite', methods=['POST'])
def favorite(self, user: User = None) -> str:
    if not user:
        return '{"error": "authentication required"}'  # 200 OK with error!
    # ...
    return '{"ok": true}'

# After:
@expose_route('/favorite', methods=['POST'])
def favorite(self, user: User = None) -> Result:
    if not user:
        return Err("authentication required")  # Route layer -> 401
    # ...
    return Ok({"favorited": True})  # Route layer -> 200
```

#### W1.4: `setup()` Extraction
**File**: `src/pybend/core/app.py`
**Change**: Extract model registration + storage + auth configuration from `build()` into `setup()`. The `build()` method calls `setup()` first, then creates routes. This is a ~4 hour refactor with zero behavior change for existing users.

**Public API addition**: `PyBendApp.setup()` and standalone `setup_app()` function added to `pybend/__init__.py`.

#### W1.5: Cache-Control Headers
**File**: `src/pybend/core/api/routes_fastapi.py`
**Change**: Add `Cache-Control: public, max-age=3600, s-maxage=86400` to `GET /{ClassName}` schema endpoints. Add `Cache-Control` to public list endpoints.

#### W1.6: Template Caching Map in form.js
**File**: `src/pybend/static/generators/form.js`
**Change**: Add a `Map` that caches generated form HTML by schema hash. Eliminates redundant re-generation for repeated renders of the same model. ~20 lines.

#### W1.7: AccessRule Boolean Algebra Law Tests
**New file**: `src/pybend/core/tests/unit/test_access_algebra.py`
**Change**: Parametric tests verifying idempotence (`A | A == A`), commutativity (`A | B == B | A`), associativity (`(A | B) | C == A | (B | C)`), distributivity, double negation (`~~A == A`), and De Morgan's laws across all rule types and contexts.

**Why This Matters**: Agent-specific rules (Wave 2) and federation rules (Wave 3) will compose with existing rules. If the algebra is broken, compositions produce wrong answers silently. Prove correctness now, before building on it.

#### W1.8: `NEVER` Bottom Element
**File**: `src/pybend/core/authorize/rules.py`
**Change**: Add `NEVER` access rule (~10 lines) that always denies. Completes the Boolean lattice (`ANYONE` = top, `NEVER` = bottom). Needed for agent deny-by-default patterns and identity-element tests.

#### W1.9: Storage Adjunction Round-Trip Tests
**New file**: `src/pybend/core/tests/unit/test_storage_adjunction.py`
**Change**: Verify `get(create(m)).scalar_fields == m.scalar_fields` for all storable field types. Document known asymmetries (collections, FK hydration, defaults) in `AbstractStorage`.

**Why This Matters**: Agent CRUD and federated entity sync depend on storage round-trip fidelity. If `create` then `get` produces different scalar values, agents and federation peers see inconsistent data.

### Wave 1 Deliverable

A structurally pure, tested, composable schema pipeline that any downstream consumer can extend with one function. No user-visible changes. No new features. Just a foundation that makes Waves 2-4 dramatically easier to build correctly.

---

## Wave 2: Schema as Agent Protocol

**Duration**: 3-4 weeks
**Depends on**: Wave 1 (composable schema pipeline, `setup()`, Result type)
**Purpose**: Make every PyBend app instantly accessible to AI agents.

### Motivation

The AI agent ecosystem has converged on a critical fact: **JSON Schema is the universal tool definition format.** Every major provider independently adopted it:

- **OpenAI**: Function calling uses `{ type: "function", function: { parameters: <JSON Schema> } }`
- **Anthropic**: Tool use uses `{ input_schema: <JSON Schema> }`
- **Google**: Gemini function declarations use JSON Schema
- **MCP (Model Context Protocol)**: Tool definitions are `{ inputSchema: <JSON Schema> }`
- **A2A (Agent-to-Agent Protocol)**: Agent Cards describe capabilities in JSON Schema

PyBend already generates richer JSON Schema than any of these protocols require. The schema carries field types, validation constraints, method signatures, access rules, UI hints, and entity relationships. The translation from PyBend schema to MCP tool definitions is mechanical -- it's a formatting exercise, not an architectural change.

The research estimates that PyBend already has **65% of what agent frameworks need**:

| Agent Need | PyBend Has | Gap |
|-----------|-----------|-----|
| Tool definitions | `schema().methods` + `@expose_route` | Format translation only |
| Typed parameters | `schema().properties` with Pydantic validation | Format translation only |
| Permission scoping | `__access__` ABAC rules | New agent-specific rules |
| Entity CRUD | `StorableMixin.create/get/list/update/delete` | Already callable |
| Messaging | `Matrix.js` + `Actor.js` (frontend only) | Python port needed (Wave 3) |
| State persistence | `StorableMixin` + `SQLiteStorage` | Already works |
| Planning loop | None | `AgentMixin` (Wave 4) |
| LLM integration | None | `LLMClient` (Wave 4) |

### Tasks

#### W2.1: MCP Tool Auto-Generation
**New file**: `src/pybend/core/api/mcp.py` (~200-400 lines)
**Change**: Implement `schema_to_mcp_tools(schema: dict) -> list[dict]` and a JSON-RPC handler for `tools/list` and `tools/call`.

The MCP server reads `registered_models`, converts each model's schema to tool definitions, and serves them via JSON-RPC (stdio or SSE transport). Tool calls are dispatched to existing route handler logic.

**What gets auto-generated per model**:
- `{tablename}_list` tool (→ `StorableMixin.list()`)
- `{tablename}_get` tool (→ `StorableMixin.get()`)
- `{tablename}_create` tool (→ `StorableMixin.create()`)
- `{tablename}_update` tool (→ `StorableMixin.update()`)
- `{tablename}_delete` tool (→ `StorableMixin.delete()`)
- One tool per `@expose_route` method (→ existing route handler)

**Access control**: Each tool definition includes the model's `__access__` rules serialized as MCP annotations (`readOnlyHint`, `destructiveHint`). The tool call handler evaluates ABAC rules against the agent's identity before executing.

**Integration point**:
```python
app = create_app(models=[Product, User, Comment], storage=storage, mcp=True)
# ^^^ also starts MCP server alongside FastAPI
```

#### W2.2: A2A Agent Card
**File**: `src/pybend/core/api/routes_fastapi.py` (or new `discovery.py`)
**Change**: Add `GET /.well-known/agent.json` endpoint that generates an Agent Card from `ProtoModel.blueprint()` (the aggregated schema of all registered models).

The Agent Card includes:
- `name`: Application name from config
- `description`: Auto-generated from registered models
- `url`: Application URL
- `skills`: One skill per registered model, with input/output schemas
- `authentication`: JWT token auth specification
- `capabilities`: CRUD operations, custom methods, access rule summary

**Why A2A alongside MCP**: MCP defines how agents USE tools. A2A defines how agents DISCOVER each other. Both are needed for a complete agent integration story. The A2A Agent Card enables multi-agent orchestration where agents discover each other's capabilities.

#### W2.3: `@expose_tool()` Decorator
**File**: `src/pybend/core/utils/decorators.py`
**Change**: New decorator that is a superset of `@expose_route()`:

```python
@expose_tool(
    description="Mark a product as favorite for the current user",
    cost={'estimated_tokens': 50, 'price_per_call_usd': 0.001},
    timeout=5000,
    destructive=False,
)
@expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
def favorite(self, user: User = None) -> Result: ...
```

`@expose_tool` sets `func.__tool__` attribute alongside `func.__endpoint__`. The MCP server reads `__tool__` for richer metadata. Methods with only `@expose_route` still work as MCP tools (with auto-generated descriptions).

#### W2.4: Agent-Specific ABAC Rules
**File**: `src/pybend/core/authorize/rules.py`
**Change**: New `AccessRule` leaf subclasses:

```python
class Budget(AccessRule):
    """Allow if agent has remaining budget above threshold."""
    def __init__(self, min_remaining: float): ...
    def evaluate(self, context: AccessContext) -> bool: ...
    def sql_filter(self, context: AccessContext) -> tuple[str, list]: ...

class RateLimit(AccessRule):
    """Allow if agent hasn't exceeded request rate."""
    def __init__(self, requests_per_minute: int): ...

class DelegationDepth(AccessRule):
    """Allow if agent delegation chain hasn't exceeded depth."""
    def __init__(self, max_depth: int): ...
```

These compose with existing rules using the standard `|`/`&`/`~` operators:

```python
__access__ = {
    'create': AUTHENTICATED & Budget(min_remaining=0.10),
    'update': (OWNER | ROLE('admin')) & RateLimit(requests_per_minute=60),
    'delete': ROLE('admin') & DelegationDepth(max_depth=1),  # No delegation allowed for deletes
}
```

**Zero engine changes.** The `evaluate()` → `bool` and `sql_filter()` → `(str, list)` contract is already defined by `AccessRule`. These are purely additive subclasses.

#### W2.5: `__guardrails__` Class-Level Dict
**File**: `src/pybend/core/models/proto_model.py`
**Change**: New class-level configuration dict (parallel to `__ui__` and `__access__`):

```python
class Product(ProtoModel):
    __guardrails__ = {
        'input': {
            'max_tokens': 1000,
            'required_fields': ['name', 'price'],
        },
        'output': {
            'format': 'json',
            'max_tokens': 2000,
        },
        'behavioral': {
            'max_tool_calls': 10,
            'delegation_depth': 2,
            'timeout_ms': 30000,
            'human_approval': ['delete', 'update'],  # These actions need human confirmation
        },
    }
```

Serialized into the schema output via a new `_schema_guardrails()` pipeline step (enabled by Wave 1's pipeline decomposition). MCP tool definitions include guardrail annotations. The route/tool layer enforces guardrails at execution time.

#### W2.6: `pybend` CLI Phase 1
**New package**: `src/pybend/cli/` with Typer-based commands.
**Commands**:
- `pybend run` -- wrap uvicorn with config
- `pybend models` -- Rich table listing all registered models
- `pybend describe <Model>` -- full schema visualization (fields, constraints, access, methods, routes)
- `pybend describe <Model> --json` -- raw JSON Schema output (for agent consumption)

**Depends on**: W1.4 (`setup()` extraction) -- the CLI calls `setup()` to populate `registered_models` without starting HTTP.

### Wave 2 Deliverable

Any PyBend application is instantly MCP-compatible:

```python
app = create_app(models=[Product, User, Comment], storage=storage, mcp=True)
```

This single line creates:
- A FastAPI server with CRUD routes (existing)
- An MCP server with typed tools for every model method (new)
- An A2A Agent Card at `/.well-known/agent.json` (new)
- ABAC-enforced permission boundaries for agent tool calls (new)
- Schema-carried guardrails for agent safety (new)

A developer who has never heard of MCP, A2A, or agent protocols gets full AI agent integration by adding one keyword argument.

---

## Wave 3: Decentralized + Agentic Shared Infrastructure

**Duration**: 4-6 weeks
**Depends on**: Wave 1 (composable pipeline, Result type), Wave 2 (agent rules, `@expose_tool`)
**Purpose**: Build the primitives that serve BOTH agent orchestration and federation protocols.

### Motivation

The research revealed that AI/Agentic and Decentralized themes share more infrastructure than any other pair of themes. Building them separately would duplicate 5+ systems. Building the shared primitives once serves both directions.

The EU regulatory environment creates a time-sensitive opportunity:
- **EU DMA review (May 2026)**: May mandate interoperability for large platforms
- **eIDAS 2.0 wallet mandate (November 2026)**: Requires EU Digital Identity Wallet acceptance
- **GDPR Article 20**: Already mandates data portability (the export endpoint)

### Tasks

#### W3.1: Python Actor/Matrix Port
**New package**: `src/pybend/core/actors/` (~500-700 lines)
**Components**:
- `matrix.py`: Message router using asyncio. Routes TX messages to registered actors.
- `actor.py`: Base actor class with `on_message()`, `on_start()`, `on_stop()` lifecycle.
- `tx.py`: Typed message envelope with `to`, `from_`, `action`, `data`, `correlation_id`.
- `supervisor.py`: Supervision strategies (restart, stop, escalate) for failed actors.
- `persistence.py`: Durable message persistence via StorableMixin (messages survive crashes).

**Design principle**: The Python Matrix is a port, not a copy. It follows the same conceptual model as the frontend (actors communicate via typed TX messages through a routing bus) but uses asyncio instead of synchronous dispatch, and adds supervision and persistence that the frontend doesn't need.

**Agent use**: Backend agents are actors. A planner agent sends a TX(action='PLAN') to an executor agent. The executor sends TX(action='RESULT') back. Matrix routes messages. Supervisor restarts crashed agents.

**Federation use**: An `InboxActor` receives inbound ActivityPub activities, validates HTTP signatures, deserializes via `SchemaTranslator`, and dispatches to the appropriate model actor. An `OutboxActor` queues outbound activities with retry semantics.

**Bridge**: A WebSocket bridge connects backend Matrix to frontend Matrix, enabling real-time sync. An agent's action on the backend (e.g., creating a product) triggers a TX message that propagates to the frontend, updating the UI without polling.

#### W3.2: `SchemaTranslator` Protocol
**New file**: `src/pybend/core/protocols/schema_translator.py` (~50 lines for Protocol, ~150 per implementation)

```python
from typing import Protocol

class SchemaTranslator(Protocol):
    """Converts PyBend JSON Schema to a target format."""

    def translate_type(self, schema: dict) -> dict:
        """Translate a model schema to the target format."""
        ...

    def translate_instance(self, instance: dict, schema: dict) -> dict:
        """Translate an entity instance to the target format."""
        ...
```

**Implementations**:
- `ActivityStreamsTranslator`: Schema → JSON-LD ActivityStreams vocabulary. `Product` → `Object` with `type: "Product"`, properties mapped to AS properties.
- `LexiconTranslator` (deferred to Wave 4): Schema → AT Protocol Lexicon.
- `MCPToolTranslator`: Already built in Wave 2, formalized under this Protocol.

**Why a Protocol**: The pattern is general. Any future format (GraphQL SDL, OpenAPI 3.1, AsyncAPI) is another implementation. The Protocol boundary keeps PyBend core clean.

#### W3.3: Event-Sourced Mutation Logging
**Files**: `src/pybend/core/models/proto_model.py`, `src/pybend/core/storage/sqlite_storage.py`
**Change**: When a model declares `__auditable__ = True`, every CRUD mutation is logged to an `_events` table:

```python
class Product(ProtoModel):
    __auditable__ = True  # Enable event sourcing
```

Event schema:
```sql
CREATE TABLE _events (
    id INTEGER PRIMARY KEY,
    model TEXT NOT NULL,         -- "Product"
    entity_id INTEGER NOT NULL,  -- 42
    action TEXT NOT NULL,        -- "create" | "update" | "delete"
    data_hash TEXT NOT NULL,     -- SHA-256 of entity data
    user_id INTEGER,             -- Who performed the action
    timestamp TEXT NOT NULL,     -- ISO 8601
    prev_hash TEXT               -- Hash of previous event (chain)
);
```

**Agent use**: Agent reasoning traces. Every tool call that mutates state produces an auditable event. `AgentTrace` models (Wave 4) build on this.

**Federation use**: Hash-chained events enable tamper detection. A federated peer can verify that the event history is consistent. The `prev_hash` chain is a lightweight Merkle-like integrity guarantee.

#### W3.4: `$hash` on Entity Responses
**File**: `src/pybend/core/models/proto_model.py`
**Change**: `model_dump_response()` (created in W1.2) also computes and injects a `$hash` field:

```python
def model_dump_response(self) -> dict:
    data = self.model_dump()
    data['$schema'] = f"{API_URL}/{self.__class__.__name__}"
    data['$id'] = f"{API_URL}/{self.__tablename__}/{self.id}"
    data['$hash'] = hashlib.sha256(
        json.dumps(data, sort_keys=True).encode()
    ).hexdigest()
    return data
```

Entities are now self-describing (`$schema`), self-addressed (`$id`), AND self-verifying (`$hash`).

**Agent use**: An agent can verify that data received from a tool call hasn't been tampered with in transit.
**Federation use**: Content-addressable sync. Peers compare `$hash` values to detect changes without comparing full payloads.

#### W3.5: Schema Versioning
**File**: `src/pybend/core/models/proto_model.py`
**Change**: Add `$version` to schema output, computed as a hash of the schema's structural content (excluding metadata like URLs):

```python
@classmethod
def _schema_metadata(cls, s: dict) -> dict:
    # ... existing $schema, $id, __name__, __tablename__
    s['$version'] = hashlib.sha256(
        json.dumps(s.get('properties', {}), sort_keys=True).encode()
    ).hexdigest()[:12]
    return s
```

**Agent use**: MCP `listChanged` notifications. When the schema version changes (model was modified, server restarted with new fields), connected agents are notified to re-fetch tool definitions.

**Federation use**: Protocol compatibility. A federated peer checks `$version` before processing; version mismatch triggers schema re-fetch.

#### W3.6: `FederationAdapter` Protocol
**New file**: `src/pybend/core/protocols/federation_adapter.py` (~80 lines)

```python
class FederationAdapter(Protocol):
    """Boundary between PyBend core and any federation protocol."""

    def serialize_object(self, instance: dict, schema: dict) -> dict:
        """Convert a PyBend entity to a federation object."""
        ...

    def serialize_activity(self, action: str, instance: dict, actor: dict) -> dict:
        """Wrap a mutation as a federation activity (Create, Update, Delete)."""
        ...

    def deserialize_activity(self, activity: dict) -> tuple[str, dict]:
        """Parse an inbound federation activity into (action, data)."""
        ...

    def verify_request(self, request: Request) -> bool:
        """Verify the cryptographic signature of an inbound request."""
        ...

    def discovery_endpoint(self, user: dict) -> dict:
        """Generate a discovery response for a user (WebFinger, Actor doc)."""
        ...
```

**Design principle**: Modeled after the existing `AuthorizationResolver` Protocol in the authorize package. The Protocol defines the boundary; concrete implementations (`ActivityPubAdapter`, `ATProtoAdapter`) live in separate packages. PyBend core never imports federation-specific code.

#### W3.7: WebFinger Endpoint
**File**: `src/pybend/core/api/routes_fastapi.py` (or new `discovery.py`)
**Change**: Add `GET /.well-known/webfinger` endpoint that resolves `acct:user@domain` queries:

```json
{
  "subject": "acct:alice@example.com",
  "links": [
    {
      "rel": "self",
      "type": "application/activity+json",
      "href": "https://example.com/users/1"
    },
    {
      "rel": "describedby",
      "type": "application/schema+json",
      "href": "https://example.com/User"
    }
  ]
}
```

This makes PyBend users discoverable by any Fediverse server (Mastodon, Pleroma, etc.) without implementing full ActivityPub. It's the lowest-cost federation primitive.

#### W3.8: DID-Aware Identity
**File**: `src/pybend/core/models/base_user.py`
**Change**: Add optional DID fields:

```python
class BaseUser(ProtoModel):
    # ... existing fields (name, email, role, password_hash)
    did: Optional[str] = Field(default=None, description="Decentralized Identifier")
    did_public_key: Optional[str] = Field(default=None, json_schema_extra={'ui': {'display': False}})
    did_method: Optional[str] = Field(default=None)  # "web", "key", "pkh"
```

Plus a `login_did` endpoint:

```python
@expose_route('/login_did', methods=['POST'])
def login_did(self, did: str, challenge: str, signature: str) -> str:
    """Authenticate via DID challenge-response. Returns standard JWT."""
    # Verify signature against did_public_key
    # If valid, issue JWT (same as password login)
    # All downstream code (routes, ABAC, _resolve_user()) unaware of auth method
```

**Why `did:web`**: The `did:web` method resolves to `/.well-known/did.json` -- a static JSON file served by the same server. No blockchain, no external infrastructure. A PyBend app at `example.com` has DID `did:web:example.com`. Users have DIDs like `did:web:example.com:users:1`.

**Agent use**: An agent running on Server A can authenticate to Server B using its DID. No shared user database needed. The agent's identity is portable across all PyBend instances.

**Federation use**: Cross-deployment authorization. A user on Server A can prove ownership of an entity on Server B using their DID, without Server B having a copy of Server A's user table.

#### W3.9: Federation + Agent ABAC Rules
**File**: `src/pybend/core/authorize/rules.py`
**Change**: New access rule subclasses:

```python
class DID_OWNER(AccessRule):
    """Ownership evaluated against DID string, not local integer ID."""
    def evaluate(self, context: AccessContext) -> bool:
        return context.resource.get('owner_did') == context.user_did

class LABELED(AccessRule):
    """Evaluate trust labels from external issuers."""
    def __init__(self, label: str, source: str = None): ...
    # E.g., LABELED('verified') & AUTHENTICATED

class LOCAL(AccessRule):
    """Allow only local (non-federated) users."""

class FEDERATED(AccessRule):
    """Allow only federated (non-local) users."""

class FOLLOWER(AccessRule):
    """Allow only users who follow this entity's owner."""
```

All compose with existing rules:

```python
__access__ = {
    'read': ANYONE,
    'create': LOCAL & AUTHENTICATED,  # Only local users can create
    'update': DID_OWNER | ROLE('admin'),  # DID-based ownership
    'delete': ROLE('admin') & ~FEDERATED,  # No federated admins
}
```

#### W3.10: Polymorphic System (Phase 1-2)
**Files**: `proto_model.py`, `sqlite_storage.py`, `sqlite_migration.py`, `NTT.js`
**Change**: `__discriminator__` ClassVar enables Single Table Inheritance:

```python
class Content(ProtoModel):
    __tablename__ = 'content'
    __discriminator__ = '_type'  # Enables polymorphism

class Article(Content):
    body: str = Field(default='')
    word_count: int = Field(default=0)

class Video(Content):
    url: str = Field(default='')
    duration: int = Field(default=0)
```

This auto-generates:
- A `_type TEXT NOT NULL` column in the `content` table
- `Article.list()` appends `WHERE _type = 'article'`; `Content.list()` returns all subtypes
- Schema output with `oneOf` + `discriminator` + per-subtype `$defs`
- Frontend `NTT.SCHEMA()` creates per-subtype DynamicClasses

**Why in Wave 3**: Agent types are natural polymorphic subtypes:

```python
class Agent(ProtoModel):
    __discriminator__ = '_type'
    __agent__ = True  # Wave 4

class PlannerAgent(Agent):
    __guardrails__ = {'behavioral': {'max_tool_calls': 5}}

class ExecutorAgent(Agent):
    __guardrails__ = {'behavioral': {'max_tool_calls': 50}}
```

Federation message types are also polymorphic (Create, Update, Delete, Follow activities sharing a base Activity model).

### Wave 3 Deliverable

A Python-native actor system with durable messaging, DID identity, event sourcing, and schema translation -- serving both agent orchestration and federation protocols from the same primitives.

The `Product` model from the introduction now:
- Is an MCP tool (Wave 2)
- Has an Agent Card (Wave 2)
- Has verifiable identity via DID (Wave 3)
- Produces auditable events (Wave 3)
- Has content-hash-verified responses (Wave 3)
- Is discoverable via WebFinger (Wave 3)
- Can participate in polymorphic type hierarchies (Wave 3)

All from the same model definition. No additional code.

---

## Wave 4: Ecosystem Maturation (Demand-Gated)

**Duration**: 6-12 weeks total, but each item is independently triggered
**Depends on**: Waves 1-3
**Purpose**: Build only when measurable triggers fire. No speculative investment.

### Demand-Gated Items

Each item lists its **trigger** -- the measurable condition that justifies building it.

#### W4.1: `AgentMixin` + `LLMClient`
**Trigger**: MCP tools validated in production with real agent consumers.
**What**: A mixin injected via `__init_subclass__()` when `__agent__ = True`:

```python
class ResearchAgent(ProtoModel):
    __agent__ = True
    __llm__ = {'provider': 'anthropic', 'model': 'claude-sonnet-4-5-20250929'}
    __prompt__ = "You are a research assistant..."
```

`AgentMixin` adds `run(task)` (ReAct loop), `think()`, tool dispatch, and LLM client integration. `LLMClient` is a provider-agnostic wrapper around anthropic-sdk and openai-sdk with streaming, cost tracking, and circuit breakers.

**Intent**: "Define a model, get an agent" -- the same pattern as "define a model, get an API."

#### W4.2: `AgentMemory` ProtoModel
**Trigger**: Agent state management need in production.
**What**: A ProtoModel for structured agent memory:

```python
class AgentMemory(ProtoModel):
    __tablename__ = 'agent_memories'
    __storable__ = True
    agent_id: int
    memory_type: str  # "working" | "semantic" | "episodic" | "procedural"
    content: str
    embedding: Optional[str] = None  # For semantic search
```

Connected to agents via existing `ListRef` pattern: `memories: ListRef[AgentMemory]`.

#### W4.3: ActivityPub Server-to-Server Federation
**Trigger**: External federation demand from users or partners.
**What**: Complete bidirectional ActivityPub federation using the `FederationAdapter` Protocol from Wave 3. WebFinger (already done) + Actor endpoints + Outbox (publish-only first) + Inbox + delivery queue + Follow/Accept flow.
**Effort**: 6-10 weeks.

#### W4.4: AT Protocol PDS Support
**Trigger**: Bluesky ecosystem growth reaching critical mass for the application domain.
**What**: Lexicon generation from `ProtoModel.schema()` via `LexiconTranslator`, DID registration/resolution, XRPC endpoint mapping.
**Effort**: 10-16 weeks.

#### W4.5: `create_agent_proxy(schema)` -- Backend DynamicClass
**Trigger**: Multi-agent orchestration need.
**What**: Python port of the frontend `prototype()` pattern. Fetch a remote Agent Card, dynamically create a typed Python class with validated methods:

```python
# One-liner integration with external agent
partner = create_agent_proxy("https://partner.com/.well-known/agent.json")
result = partner.analyze(data={"query": "market trends"})  # Typed, validated
```

#### W4.6: Pub/Sub Channels in Matrix.js
**Trigger**: Frontend event decoupling need (3+ components subscribing to same events).
**What**: Named channels with glob-pattern matching in the frontend Matrix:

```javascript
matrix.subscribe('product.*', (tx) => { /* handle any product event */ });
matrix.publish('product.created', { id: 42, name: 'Widget' });
```

#### W4.7: `VC_CLAIM` Access Rule (Verifiable Credentials)
**Trigger**: eIDAS 2.0 wallet mandate (November 2026).
**What**: An access rule that evaluates presented Verifiable Credentials:

```python
__access__ = {
    'create': VC_CLAIM(type='ProofOfAge', issuer='did:web:gov.eu'),
}
```

#### W4.8: `RemoteStorage` Adapter
**Trigger**: Team exceeds 10 engineers, service extraction needed.
**What**: An `AbstractStorage` implementation that delegates CRUD over HTTP to a remote PyBend service. A model switches from local to remote by changing `storage=`:

```python
# Local:
register_model(Product, storage=sqlite_storage)
# Remote:
register_model(Product, storage=RemoteStorage("https://product-service.internal"))
```

#### W4.9: Python Schema Renderer + SSR
**Trigger**: SEO metrics demand (Lighthouse scores below acceptable threshold on critical pages).
**What**: Python-side port of `form.js` display logic (~400 lines). Enables Strategy A (embed schema+data as `<script>` tags, ~50 lines, near-zero cost) and Strategy B (full server-rendered HTML with Declarative Shadow DOM).

#### W4.10: `pybend export` Static Site
**Trigger**: Content site use case where hosting cost matters.
**What**: CLI command that generates static HTML from registered models. Uses the Python Schema Renderer from W4.9.

#### W4.11: TUI Admin Dashboard
**Trigger**: Developer experience demand from CLI-heavy users.
**What**: Textual-based terminal admin interface with model sidebar, DataTable entity listing, schema-driven CRUD forms.

---

## 10. Deferred Themes

These themes were researched but are explicitly deferred. They are not forgotten -- they are demand-gated with specific triggers.

### SSR / HTML Compiler / Static Site Generation
**Status**: Deferred to Wave 4 (W4.9, W4.10)
**Why deferred**: These are rendering optimizations. They make the existing browser frontend faster or enable non-browser HTML output. They don't expand the schema's reach to new protocol ecosystems (agents, federation). When SEO or hosting cost becomes a measurable concern, Wave 4 items activate.

**What's preserved**: The Python Schema Renderer proposed by all three themes is the same component. Building it once (when triggered) serves all three.

### GraphQL
**Status**: Strategically rejected by research.
**Why rejected**: PyBend's JSON Schema already delivers 70-80% of GraphQL's value. Full GraphQL adoption would cost 3-6 months and introduce a parallel type system. Targeted REST enhancements (`?fields=`, enhanced `?populate=`) close the remaining gap at ~5% of the cost.
**Quick wins preserved**: `?fields=` sparse fieldsets (~50 LOC, 1-2 days) can be added anytime as a standalone improvement.

### Micro-Frontend
**Status**: Phase 0 is free (import maps, modulepreload). Everything else waits for team growth.
**Why deferred**: Micro-frontend architecture solves organizational scaling problems (independent team deployment). PyBend's current team size doesn't justify the complexity. The research provides measurable triggers (merge conflicts/week, deployment coordination hours, team count) for when to proceed.

---

## 11. Theme Cross-Reference Matrix

This matrix shows which themes benefit from which Wave 1-3 changes. A cell marked with a checkmark means the change directly enables or accelerates that theme.

| Change (Wave.Task) | AI/Agents | Decentralized | Cat Theory | Polymorphic | CLI/TUI | Microservices | SSR | Static | HTML Comp | GraphQL | Micro-FE |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| W1.1 Schema pipeline | X | X | X | X | | X | X | X | X | X | |
| W1.2 model_dump_response | X | X | X | | | X | X | X | | | |
| W1.3 Result type | X | X | X | | | X | | | | | |
| W1.4 setup() extraction | X | X | | | X | | X | X | | | |
| W1.5 Cache-Control | | | | | | | X | X | X | | |
| W1.7 ABAC algebra tests | X | X | X | X | | | | | | | |
| W1.8 NEVER rule | X | X | X | | | | | | | | |
| W2.1 MCP tools | X | | | | X | X | | | | | |
| W2.2 Agent Card | X | X | | | | X | | | | | |
| W2.3 @expose_tool | X | | | | | | | | | | |
| W2.4 Agent ABAC rules | X | | X | | | | | | | | |
| W2.5 __guardrails__ | X | | | | | | | | | | |
| W3.1 Python Actor/Matrix | X | X | | | | X | | | | | |
| W3.2 SchemaTranslator | X | X | | | | | | | | X | |
| W3.3 Event sourcing | X | X | | | | X | | | | | |
| W3.4 $hash | X | X | | | | | | | | | |
| W3.5 Schema versioning | X | X | | | | X | | | | | |
| W3.6 FederationAdapter | | X | | | | | | | | | |
| W3.7 WebFinger | | X | | | | | | | | | |
| W3.8 DID identity | X | X | | | | | | | | | |
| W3.9 Fed+Agent ABAC | X | X | X | | | | | | | | |
| W3.10 Polymorphic STI | X | X | | X | | X | X | X | | X | |

---

## 12. Risk and Decision Framework

### Architectural Risks

| Risk | Mitigation | Trigger to Re-Evaluate |
|------|-----------|----------------------|
| **Schema pipeline decomposition breaks backward compat** | Integration test: composed output must match current output byte-for-byte | Test fails |
| **MCP protocol evolves rapidly** | Thin translation layer (~200 LOC) is cheap to update. No deep coupling. | MCP spec breaking change |
| **A2A protocol not yet stable** | Agent Card is a simple JSON file. Re-generating it is trivial. | A2A spec breaking change |
| **Python Actor/Matrix becomes overengineered** | Strict scope: message routing + supervision + persistence. No planning loops, no LLM integration. | Actor system used by <2 consumers after 6 months |
| **DID ecosystem fragmentation** | Start with `did:web` (simplest, server-controlled). Other methods are additive. | `did:web` deprecated or superseded |
| **Federation complexity spiral** | `FederationAdapter` Protocol is the firewall. Core never imports federation code. | Adapter implementations exceed 1000 LOC each |
| **Agent ABAC rules add complexity** | They're leaf subclasses. Removing them removes the capability. Zero engine changes. | Rules unused after 6 months |

### Decision Heuristics

1. **"Does this change make the schema carry more or less?"** Changes that enrich the schema (more metadata, more consumers) align with the thesis. Changes that bypass the schema (hand-rolled routes, custom protocols) don't.

2. **"Is this a Protocol or an Implementation?"** PyBend should own Protocols (boundaries). Implementations are interchangeable. `FederationAdapter` is a Protocol; `ActivityPubAdapter` is an implementation. `SchemaTranslator` is a Protocol; `MCPToolTranslator` is an implementation.

3. **"Does this serve 2+ themes?"** Cross-cutting changes come first. Single-theme changes are demand-gated. The Python Actor/Matrix port serves AI + Decentralized + Microservices. A TUI dashboard serves only CLI/TUI.

4. **"Can I add this without modifying existing code?"** Additive changes (new subclasses, new pipeline steps, new endpoints) are safe. Changes that modify existing behavior carry risk. All Wave 2-3 agent/federation changes are additive -- they extend existing patterns rather than replacing them.

---

## 13. Success Metrics

### Wave 1 (Foundation)
- [ ] All existing tests pass (zero regression)
- [ ] Schema pipeline: each step independently testable with >=90% coverage
- [ ] `model_dump_response()`: zero remaining `model_dump(response=True)` calls in routes
- [ ] Result type: `MethodError` and `Result` both handled by route layer
- [ ] ABAC algebra: all 7 law families pass for all rule combinations
- [ ] Storage adjunction: round-trip test passes for all storable field types
- [ ] `setup()`: models bootstrap without HTTP in test harness

### Wave 2 (Agent Protocol)
- [ ] MCP server passes MCP compliance test suite
- [ ] Agent Card serves valid A2A Agent Card JSON
- [ ] `@expose_tool` methods appear in both MCP tool list and REST routes
- [ ] Agent ABAC rules compose with existing rules (tested via algebra suite from W1)
- [ ] `pybend describe Product --json` outputs valid JSON Schema
- [ ] At least one external MCP client (Claude Desktop or Cursor) successfully calls a PyBend tool

### Wave 3 (Shared Infrastructure)
- [ ] Python Actor/Matrix: message delivery test with 3+ actors
- [ ] SchemaTranslator: round-trip test (translate + re-parse = equivalent structure)
- [ ] Event sourcing: audit log correctly records create/update/delete for `__auditable__` models
- [ ] `$hash`: verification test (tamper data → hash mismatch detected)
- [ ] Schema versioning: version changes when properties change, stable when unchanged
- [ ] WebFinger: resolves `acct:user@domain` to correct actor URL
- [ ] DID login: challenge-response produces valid JWT accepted by existing routes
- [ ] Polymorphic: `Content.list()` returns mixed subtypes; `Article.list()` returns only articles

### Wave 4 (Demand-Gated)
- Success metrics defined per item when triggered. No speculative measurement.

---

## Appendix: File Index

Key files referenced in this roadmap, with their roles:

### Backend (Python)
| File | Role | Waves Touching It |
|------|------|:-:|
| `src/pybend/core/models/proto_model.py` | Base model, schema generation, model_dump | W1, W2, W3 |
| `src/pybend/core/models/base_user.py` | User model with login/register | W3 |
| `src/pybend/core/models/storable_mixin.py` | CRUD operations | W3 |
| `src/pybend/core/api/routes_fastapi.py` | Route factories, auth injection | W1, W2, W3 |
| `src/pybend/core/authorize/rules.py` | AccessRule hierarchy | W1, W2, W3 |
| `src/pybend/core/authorize/context.py` | AccessContext dataclass | W3 |
| `src/pybend/core/authorize/schema.py` | Rule serialization to JSON | W2, W3 |
| `src/pybend/core/storage/sqlite_storage.py` | SQLite backend with FK hydration | W3 |
| `src/pybend/core/storage/sqlite_migration.py` | Auto-migration | W3 |
| `src/pybend/core/app.py` | PyBendApp builder + create_app() | W1, W2 |
| `src/pybend/core/config.py` | Configuration | W2 |
| `src/pybend/core/utils/decorators.py` | @expose_route | W2 |
| `src/pybend/core/utils/registrar.py` | registered_models dict | W2, W3 |
| `src/pybend/__init__.py` | Public API re-exports | W1, W2 |

### Frontend (JavaScript)
| File | Role | Waves Touching It |
|------|------|:-:|
| `src/pybend/static/core/NTT.js` | Core entity system, prototype(), DynamicClass | W3 |
| `src/pybend/static/core/Matrix.js` | Message bus / actor system | - |
| `src/pybend/static/core/Actor.js` | Base actor class | - |
| `src/pybend/static/core/TX.js` | Message envelope | - |
| `src/pybend/static/generators/form.js` | Schema-driven form generator | W1 |
| `src/pybend/static/components/ntt-item.js` | Item component (size methods) | - |
| `src/pybend/static/components/ntt-list.js` | List component | W3 |
| `src/pybend/static/utils/Permissions.js` | Frontend permission checks | - |

### New Files (Created by This Roadmap)
| File | Wave | Purpose |
|------|:----:|---------|
| `src/pybend/core/utils/result.py` | W1 | `Ok[T]` / `Err[E]` Result type |
| `src/pybend/core/tests/unit/test_access_algebra.py` | W1 | Boolean algebra law tests |
| `src/pybend/core/tests/unit/test_storage_adjunction.py` | W1 | Storage round-trip tests |
| `src/pybend/core/api/mcp.py` | W2 | MCP server + tool generation |
| `src/pybend/core/api/discovery.py` | W2/W3 | Agent Card + WebFinger endpoints |
| `src/pybend/cli/__init__.py` | W2 | Typer CLI entry point |
| `src/pybend/cli/commands/` | W2 | CLI command modules |
| `src/pybend/core/actors/matrix.py` | W3 | Python Actor/Matrix port |
| `src/pybend/core/actors/actor.py` | W3 | Base actor class |
| `src/pybend/core/actors/tx.py` | W3 | Typed message envelope |
| `src/pybend/core/actors/supervisor.py` | W3 | Actor supervision |
| `src/pybend/core/protocols/schema_translator.py` | W3 | SchemaTranslator Protocol |
| `src/pybend/core/protocols/federation_adapter.py` | W3 | FederationAdapter Protocol |

---

*This roadmap is a living document. Each Wave's completion should trigger a review of the next Wave's priorities and triggers. The research that informed this roadmap lives in `.traces/vision/` and `.traces/research/`.*
