# ROADMAP-B: Actor-Unified Architecture

> **One system. Actors all the way down.**
> From a web framework with an actor frontend to a unified actor platform
> where agents, federation, and microservices are routing configurations, not features.

**Generated**: 2026-02-26
**Branch**: `v0.7.0`
**Status**: Strategic architecture roadmap. Parallel work exists in `ROADMAP-A.md`.

---

## Table of Contents

1. [Context: The Architectural Asymmetry](#1-context-the-architectural-asymmetry)
2. [Strategic Thesis](#2-strategic-thesis)
3. [Research Foundations](#3-research-foundations)
4. [The Unification Insight](#4-the-unification-insight)
5. [Priority Themes and the Reinforcing Triangle](#5-priority-themes-and-the-reinforcing-triangle)
6. [Wave 0: Actor/Matrix/TX Backend + Schema Architecture](#wave-0-actormatrixtx-backend--schema-architecture)
7. [Wave 1: Agent + Federation Capabilities](#wave-1-agent--federation-capabilities)
8. [Wave 2: Actor Infrastructure Actors](#wave-2-actor-infrastructure-actors)
9. [Wave 3: Unification + Deepening](#wave-3-unification--deepening)
10. [Wave 4+: Demand-Gated Capabilities](#wave-4-demand-gated-capabilities)
10. [Cross-Cutting Impact Matrix](#10-cross-cutting-impact-matrix)
11. [Risk and Decision Framework](#11-risk-and-decision-framework)
12. [Success Metrics](#12-success-metrics)
13. [File Index](#13-file-index)

---

## 1. Context: The Architectural Asymmetry

### What PyBend Is Today

PyBend is a schema-driven Python/FastAPI framework where **model definitions are the single source of truth** for the entire application stack. A developer writes a Python model; the framework derives storage, API, validation, permissions, forms, and navigation:

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

From this single definition, the framework generates:

| Concern | How It's Derived |
|---------|-----------------|
| **Database table + migrations** | `__storable__` triggers `StorableMixin` injection via `__init_subclass__()` |
| **CRUD API endpoints** | `register_routes()` reads `__tablename__` and field types |
| **JSON Schema** | `ProtoModel.schema()` via Pydantic, enriched with `methods`, `access`, `ui`, `$defs` |
| **Frontend entity classes** | `NTT.SCHEMA()` -> `prototype()` -> DynamicClass with typed getters/setters |
| **Form rendering** | `form.js` reads `schema.properties`, `ui.widget`, `ui.field_order`, `ui.groups` |
| **Access control** | `__access__` rules composed with `|`/`&`/`~`, serialized to schema, enforced at route layer + frontend |
| **Custom method buttons** | `@expose_route` appears in `schema.methods`, rendered by `<ntt-method>` |
| **Entity self-description** | `model_dump(response=True)` injects `$schema` (schema URL) and `$id` (instance URL) |

### The Frontend: Already an Actor System

The frontend is built on a proven Actor/Matrix/TX message-passing architecture:

**Actor** (`src/pybend/static/core/Actor.js`): Base class with private `#addr`, `#parent`, `#children`. Each actor has an `inbox()` method that receives TX messages and a `send()` method that routes through the Matrix. Actors form a hierarchy — child actors register with their parent, and unresolvable messages bubble up to the root.

**Matrix** (`src/pybend/static/core/Matrix.js`): The root actor and message bus. Extends Actor. Routes TX messages to registered child actors by address. If a target isn't local, delegates to `NetworkAdapter` for remote delivery (HTTP or WebSocket). Matrix is a singleton — there is exactly one per application.

**TX** (`src/pybend/static/core/TX.js`): The message envelope. Every message in the system is a TX with: `name` (event type: SCHEMA, READ, CREATE, UPDATE, DELETE, CONNECT, DESCRIBE, ERROR), `source` (sender address), `target` (recipient address), `data` (payload), `meta` (routing metadata), `tst` (timestamp), `hash` (content hash).

**NetworkAdapter** (`src/pybend/static/core/transport/NetworkAdapter.js`): Bridges the Matrix to the network. Translates TX messages to HTTP requests (or WebSocket frames). When a response arrives, it's wrapped back into a TX and dispatched through the Matrix to the original sender. Error responses produce TX messages with `name: "ERROR"`.

**How the frontend works today:**
```
User clicks product → ntt-item sends TX(name='DESCRIBE', target='Product/42')
  → Matrix routes to NTT actor
    → NTT actor sends TX(name='READ', target='Product/42')
      → Matrix can't resolve locally → NetworkAdapter sends GET /products/42
        → Response arrives → NetworkAdapter wraps in TX → Matrix routes back to NTT
          → NTT triggers DynamicClass update → ntt-item re-renders
```

Every interaction is a TX message routed through the Matrix. Components don't call functions — they send messages to addresses. This provides isolation, composability, and location transparency.

### The Backend: Direct Function Calls

The backend is the opposite. It uses direct function calls, global mutable state, and synchronous execution:

```
HTTP request arrives at FastAPI route handler
  → Handler calls StorableMixin.get(id) directly
    → StorableMixin calls SQLiteStorage.get() directly
      → SQLiteStorage queries the database directly
        → Result returned up the synchronous call stack
          → Handler calls model_dump(response=True) directly
            → Response returned to client
```

**No messages.** No routing. No isolation. No location transparency. The backend is a stack of direct function calls with globally shared state (`registered_models` dict, `config` module, SQLite connection).

### The Asymmetry Problem

This asymmetry means:

1. **Every new capability requires building its own communication system.** Federation needs an outbox queue, a delivery system, an inbox handler. Agents need a message bus, task dispatch, state management. Microservices need an event system, service discovery, health checks. These are all the SAME thing — message routing — but they'd each be built from scratch because the backend has no message infrastructure.

2. **The frontend and backend speak different languages.** The frontend sends TX messages; the backend receives HTTP requests. Every interaction crosses a paradigm boundary (actors → HTTP → function calls → HTTP → actors). Real-time updates require a separate WebSocket system that doesn't exist yet.

3. **Testing and isolation are harder.** You can't test a backend component in isolation without starting FastAPI, because components are wired together via direct imports and global state. The frontend's actor isolation doesn't extend to the backend.

4. **Schema generation is a monolith.** `ProtoModel.schema()` is a 118-line method that does everything in one pass. Every new schema consumer (agents, federation, polymorphism) must modify this monolith or work around it. There's no pipeline, no extension point, no composability.

---

## 2. Strategic Thesis

> **Port the backend to Actor/Matrix/TX. Build the schema pipeline INTO it.
> Then agents, federation, and microservices become routing configurations — not features.**

The insight: the frontend's Actor/Matrix/TX already solves the communication problem for UI components. The backend needs the same solution for backend components. And critically, **the schema pipeline should be built as part of the actor system**, not as a separate concern layered on top — because schema IS how an actor describes itself.

**What "actors all the way down" means:**

```
BEFORE (two paradigms):
  Frontend: Actor/Matrix/TX ──HTTP──> FastAPI routes → direct calls → SQLite

AFTER (one paradigm):
  Frontend Matrix ←──WebSocket──→ Backend Matrix
       │                              │
   Frontend Actors              Backend Actors
   (NTT, Router,               (ActorModel, StorageActor,
    Item, List...)               AuthActor, RouteActor...)
       │                              │
       └──── Same TX envelope ────────┘
       └──── Same addressing ─────────┘
       └──── Same routing ────────────┘
```

And then federation extends this naturally:

```
Server A Matrix ←──ActivityPub──→ Server B Matrix
       │                              │
   Local Actors                  Remote Actors
   (Product, User...)           (Product, User...)
       │                              │
       └──── Same TX (serialized as Activity) ────┘
       └──── Same addressing (Actor URI = $id) ───┘
       └──── Same routing (NetworkAdapter speaks AP) ─┘
```

**Federation IS location-transparent actor messaging.** An ActivityPub Actor has an inbox and outbox. A PyBend Actor has `inbox()` and `send()`. An ActivityPub Activity is a message describing an action. A PyBend TX is a message with `name` (action), `source`, `target`, `data`. The structural mapping is not an analogy — it's identity.

**Agents ARE actors with LLM brains.** An agent receives a task TX, calls an LLM, sends tool-call TXs to model actors, receives results, and sends a final response TX. The Matrix routes everything. Supervision restarts crashed agents.

**Microservices ARE actors in separate processes.** Moving an ActorModel from one Matrix to another is microservice extraction. Location transparency means the calling code doesn't change.

---

## 3. Research Foundations

This roadmap synthesizes findings from 13 research explorations conducted in `.traces/research/`. Each explored a technology domain through the lens of PyBend's schema-driven architecture.

### Research Inventory

| # | Theme | Core Finding | Roadmap Impact |
|---|-------|-------------|----------------|
| 1 | **Category Theory** | PyBend embodies categorical structures (functors, algebras, adjunctions) with 8 "impurities." Three high-priority ones cause real bugs. | Wave 0: schema pipeline, Result type, model_dump split are CT fixes applied as the backend is built |
| 2 | **AI Agents** | AI ecosystem converged on JSON Schema as universal tool definition format. PyBend has 65% of agent infrastructure. | Wave 1: MCP tools, A2A Agent Card — both are NetworkAdapter protocols on the actor system |
| 3 | **Schema-Agentic Systems** | 9 direct architectural parallels between PyBend's frontend actors and agent patterns. `@expose_route` = tool definition. `AccessRule` = agent permission scoping. | Wave 0: backend actors mirror these patterns; Wave 1: MCP is a thin adapter |
| 4 | **Schema-Driven Agents** | "Define a model, get an agent" is a genuine market differentiator. No framework offers built-in ABAC + auto-generated API + auto-generated UI from a single agent definition. | Wave 4+: AgentMixin builds on Wave 0 actor infrastructure |
| 5 | **Decentralized Protocols** | PyBend's self-describing entities (`$schema`/`$id`) are 60-70% convergent with federation protocols. ActivityPub Actor ≡ PyBend Actor (structurally identical). | Wave 0: actors enable federation; Wave 1: AP is a NetworkAdapter |
| 6 | **Polymorphic Systems** | `__discriminator__` ClassVar enables STI with automatic `oneOf` + discriminator JSON Schema. Agent types and Activity types are natural polymorphic subtypes. | Wave 3: schema extension on actor pipeline |
| 7 | **Microservices** | PyBend is already a modular monolith. `create_app()` is a service factory. Schema contract is identical in monolith or service mode. | Wave 0: actors make extraction mechanical (move actor to another Matrix) |
| 8 | **CLI/TUI** | PyBend is 70% done with CLI, zero code written. The missing piece is `setup()` — bootstrapping models without HTTP. | Wave 4+: CLI is a schema consumer that talks to actors |
| 9 | **GraphQL** | Decisive "no." PyBend's JSON Schema delivers 70-80% of GraphQL's value. Schema-carries-UI is the moat GraphQL can't replicate. | Sparse fieldsets (`?fields=`) as a minor enhancement |
| 10 | **SSR** | Strategy A (embed schema+data as `<script>` tags) eliminates 400-600ms waterfall with ~50 lines. Already has `#consumePreloadedSchema()`. | Wave 3: quick win (2-4 hours), not architectural |
| 11 | **HTML Compiler** | Schema-compiled templates yield 3-8x FCP improvement. ~770 LOC pure Python compiler. | Wave 4+: schema consumer actor, triggered by performance need |
| 12 | **WebAssembly** | PyBend is I/O-bound (84% network, 12% DOM, 3% CPU). Wasm optimizes the wrong bottleneck. | Deferred. Revisit at >1,000 entities/page |
| 13 | **Micro-Frontends** | 70% of MFE infrastructure exists (Actor model, schema discovery, Web Components). Industry converging on PyBend's stack. | Wave 4+: organizational trigger (15+ frontend devs) |

### Why Three Themes Were Prioritized

**AI/Agentic**: The AI agent market is projected at $52.6B by 2030 (46.3% CAGR). Every major LLM provider converged on JSON Schema for tool definitions. PyBend's schema IS the tool definition. MCP has 97M+ monthly SDK downloads and was donated to the Linux Foundation. This is the fastest-growing ecosystem PyBend can access, and the gap is a thin adapter layer, not an architectural change.

**Category Theory**: CT is not a feature — it's the discipline of building everything else correctly. The CT research identified 8 "impurities" that cause real bugs (200-OK errors, schema pipeline inflexibility, storage round-trip inconsistency). Fixing these makes agents and federation work correctly by construction. CT is the "how," not the "what."

**Decentralization**: EU DMA review (May 2026) may mandate interoperability. eIDAS 2.0 (November 2026) mandates digital identity wallets. Bluesky has 40M+ users. The Fediverse has 12M+ registered users. And the structural insight — ActivityPub Actor = PyBend Actor — means federation is not a new feature but a natural extension of the actor architecture.

---

## 4. The Unification Insight

### Why Actor Backend + Schema Pipeline Must Be Built Together

The original ROADMAP-A treated the schema pipeline and the actor backend as separate phases:
- Wave 1: Decompose schema pipeline (CT foundation)
- Wave 3: Port Actor/Matrix/TX to Python (agent + federation infrastructure)

ROADMAP-B combines them into a single Wave 0. Here's why:

**The schema pipeline IS an actor concern.** In the actor model, when you ask "what can this actor do?", the answer is the schema. Schema generation is how an ActorModel handles a `SCHEMA` message. Pipeline stages are internal to the actor — they don't need to be separate actors (that would be over-engineering), but they ARE actor behavior.

**Building separately means building twice.** If you decompose the schema pipeline first (as functions on ProtoModel), then port to actors second, you must re-integrate the pipeline into the actor system. If you build them together, the pipeline is actor-native from day one.

**TX already carries success/failure.** The Result type (CT recommendation) maps naturally to TX response messages. A successful operation returns a TX with data. A failed operation returns a TX with `name: "ERROR"`. No separate Result class needed — it's designed into the message envelope. This only works if you design TX and Result together.

**Events are free.** In the function-call backend, lifecycle events (after_create, after_update) require building a separate event system. In the actor backend, events are just TX messages that the ActorModel publishes to subscribers. No separate system needed — it's intrinsic to the architecture.

**model_dump variants are message types.** Instead of `model_dump(response=True)` (a boolean flag bifurcating one function), you have different TX message types:
- `TX(name='DUMP')` → plain data (for storage, for agents)
- `TX(name='DUMP_RESPONSE')` → data + `$schema`/`$id` (for HTTP responses)
- `TX(name='DUMP_ACTIVITY')` → data + ActivityStreams context (for federation)

Each is a distinct message with distinct handling. The CT impurity (bifurcated morphism) is eliminated by construction.

### What This Eliminates

Building Wave 0 as a combined actor + schema effort eliminates what was previously a separate Wave 1:

| ROADMAP-A Item | ROADMAP-B Status |
|---|---|
| W1.1: Schema Pipeline Decomposition | Wave 0a — first task, before any Actor work |
| W1.2: model_dump_response() Split | TX message types in Wave 0 |
| W1.3: Result Type | TX success/error pattern in Wave 0 |
| W1.4: setup() Extraction | Actor bootstrap replaces build() |
| W1.7: AccessRule Algebra Tests | Moved to Wave 1 (verify before extending) |
| W1.8: NEVER Bottom Element | Moved to Wave 1 |
| W1.9: Storage Adjunction Tests | Moved to Wave 3 |

**Net result:** Same total effort (~8-10 weeks), but capabilities ship in every wave. No "pure infrastructure" wave that delivers zero external value.

---

## 5. Priority Themes and the Reinforcing Triangle

The three priority themes form a mutually reinforcing system:

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
        - Actor/Matrix/TX (THE foundation)
        - Schema as actor self-description
        - TX as universal message envelope
        - NetworkAdapter per protocol
        - Composable ABAC rules
        - Event sourcing via TX history
        - Discovery at well-known URLs
```

### How the Actor Backend Serves All Three

**Category Theory**: Actors with message passing form a proper category. Messages are morphisms. Actor composition is functor composition. The schema pipeline (composable stages within an actor) consists of endofunctors. The system is categorically pure by construction — not by discipline applied after the fact.

**AI/Agentic**: MCP is JSON-RPC over stdio/HTTP. Translating TX ↔ MCP is protocol adaptation at the boundary:
```
MCP tools/list  →  TX(name='SCHEMA', target='Matrix')  →  list all ActorModels
MCP tools/call  →  TX(name=method, target='Product/42') →  route to ActorModel
MCP response    ←  TX response from actor
```
Every registered model is automatically an MCP tool provider. Zero new business logic — just protocol translation.

**Decentralization**: ActivityPub is HTTP-based actor messaging. The mapping is structural:
```
AP POST /inbox   →  TX(name='CREATE', source='remote_actor', target='Product')
AP GET /outbox   →  TX(name='LIST', target='Product/outbox')
TX(after_create) →  AP POST to followers' inboxes (delivery = remote send)
```
WebFinger resolves actor addresses (already have `$id` on every entity). ActivityPub inbox IS Actor.inbox(). ActivityPub outbox IS Actor.send().

---

## Wave 0: Actor/Matrix/TX Backend + Schema Architecture

**Duration**: ~4-5 weeks
**Risk**: Medium — significant refactor, but external API (URLs, responses) unchanged
**Purpose**: Rebuild the backend on Actor/Matrix/TX with schema pipeline built in. Everything after this is dramatically simpler.

### Motivation

This is the highest-leverage change in the entire roadmap because it transforms every subsequent capability from "new subsystem to build" into "NetworkAdapter to plug in" or "new Actor type to register."

Without Wave 0, each of Waves 1-3 requires building its own communication, routing, event, and state infrastructure. With Wave 0, they share one — the same one the frontend already proves works.

### 0a. Schema Pipeline Decomposition (~2-3 days)

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

This is a **pure refactor** with zero external behavior change. All existing tests must pass identically. It unblocks everything that follows — the Actor system, MCP, federation, polymorphism — because they all need to extend the schema.

### 0b. Python Actor/Matrix/TX Core (~1 week)

Port the frontend's proven patterns to Python, adapted for server-side concerns.

**Key design decision (resolved after research):** Python's multiple inheritance IS the
equivalent of JS's `Actor.subclass()`. In JS, `Actor.subclass(DynamicClass)` hot-patches
actor methods onto a class because JS can't do true MI. In Python, `class X(Actor, ProtoModel)`
achieves the same result natively. The `__init__` chain works because each class calls
`super().__init__()`, just like ProtoModel already does with PydanticBaseModel today.

**Class hierarchy:**
```
Actor                       # Base: addr, children, inbox, handler, send, register, spawn
├── Matrix(Actor)           # Root router, singleton, NetworkAdapters
└── ActorModel(Actor, ProtoModel)  # Models that are actors (Wave 0)
    ├── Product(ActorModel)
    ├── User(ActorModel)     # (via BaseUser → ActorModel)
    └── Comment(ActorModel)

# Wave 2 additions:
├── StorageActor(Actor)     # CRUD against a storage backend
├── AuthActor(Actor)        # ABAC message interceptor
├── RouteActor(Actor)       # HTTP ↔ TX bridge

ProtoModel(PydanticBaseModel)  # Unchanged — pure data, schema, serialization
StorableMixin                   # Unchanged — CRUD methods (create, get, list, update, delete)
```

**Three classes, three concerns:**
- `Actor` — messaging (addr, children, inbox, handler, send, register, spawn)
- `ProtoModel` — data (fields, validation, schema, model_dump)
- `ActorModel(Actor, ProtoModel)` — the bridge: models that participate in messaging

ProtoModel is **unchanged**. StorableMixin is **unchanged**. CRUD methods stay in
StorableMixin. Routes stay unchanged in Wave 0 — RouteActor bridge comes in Wave 2.

**Actor base class** (`src/pybend/core/actors/actor.py`):
```python
class Actor:
    """Base actor with address, parent, children, inbox, handler, send.

    Direct port of frontend Actor.js. Python MI replaces JS Actor.subclass().

    Design constraints:
    - No __slots__ (must be compatible with Pydantic BaseModel via MI)
    - __init__ calls super().__init__() for MRO chaining
    - Uses __root__ / __children__ as annotated class variables
    """

    __root__: ClassVar[Optional['Actor']] = None    # Root actor (Matrix), like JS ROOT_ACTOR
    __children__: ClassVar[dict[str, 'Actor']] = {} # Class-level children registry

    def __init__(self, *args, addr: str = '', **kwargs):
        # Actor state — set BEFORE calling super() so Pydantic __init__ runs after
        self._actor_addr = addr or getattr(self.__class__, '__tablename__', self.__class__.__name__)
        self._actor_children = {}        # Instance-level children
        self._actor_parent = None        # Parent actor reference
        super().__init__(*args, **kwargs)

    @property
    def addr(self) -> str:
        return self._actor_addr

    @property
    def children(self) -> dict:
        return self._actor_children

    async def inbox(self, tx: 'TX') -> None:
        """Receive a message. Fire-and-forget — does NOT return.
        Calls handler() which dispatches to the local method and sends the reply."""
        await self.handler(tx)

    async def handler(self, tx: 'TX') -> None:
        """Look up local method by tx.name, execute it, wrap return in TX, dispatch.

        e.g. TX(name='like') → self.like(tx.data, tx) → wrap result → send reply TX
        Methods can return:
        - dict/value → handler wraps in tx.reply() and dispatches
        - tx.error() → handler dispatches directly (already a TX)
        - None → handler dispatches tx.reply() with empty data
        If no matching method, sends an error TX back to source.
        """
        method = getattr(self, tx.name, None)
        if method and callable(method):
            result = await method(tx.data, tx) if asyncio.iscoroutinefunction(method) else method(tx.data, tx)
            # If method returned a TX directly (e.g. tx.error()), dispatch as-is
            if isinstance(result, TX):
                await self.send(result)
            else:
                # Wrap return value in a reply TX and dispatch back to sender
                reply = tx.reply(data=result if isinstance(result, dict) else {'result': result})
                await self.send(reply)
        else:
            await self.send(tx.error(f"Unhandled message: {tx.name}"))

    async def send(self, tx: 'TX') -> None:
        """Send message through parent for routing. Fire-and-forget.
        Mirrors JS: instance.send() → constructor.send() → parent → Matrix."""
        if self._actor_parent:
            await self._actor_parent.inbox(tx)
        elif Actor.__root__:
            await Actor.__root__.inbox(tx)
        else:
            raise RuntimeError("No root actor registered. Initialize Matrix first.")

    def register(self, child: 'Actor') -> 'Actor':
        """Register a child actor (instance-level)."""
        child._actor_parent = self
        self._actor_children[child.addr] = child
        return child

    def spawn(self, addr: str, actor_cls: type, *args, **kwargs) -> 'Actor':
        """Spawn and register a child actor."""
        child = actor_cls(*args, addr=addr, **kwargs)
        return self.register(child)

    # ── Class-level methods (mirror JS static send/inbox/children) ──

    @classmethod
    async def send_cls(cls, tx: 'TX') -> None:
        """Static send — mirrors Actor._send() in JS.
        Route to class children first, then bubble to root."""
        target_addr = tx.target.split('/')[0]
        if target_addr in cls.__children__:
            await cls.__children__[target_addr].inbox(tx)
        elif Actor.__root__:
            await Actor.__root__.inbox(tx)

    @classmethod
    def register_cls(cls, child: 'Actor'):
        """Register into the class-level children registry."""
        cls.__children__[child.addr] = child

    @classmethod
    def register_root(cls, actor: 'Actor'):
        """Register the root actor (Matrix). Mirrors JS Actor.registerRoot()."""
        cls.__root__ = actor

    async def on_start(self): ...
    async def on_stop(self): ...
```

**Class-level vs instance-level children (reconciliation):**

The frontend has the same dual-level pattern. The Python mapping:

| JS Frontend | Python Backend | Purpose |
|---|---|---|
| `Actor.subclass(X)` sets `X.children` (static Map) | `Actor.__children__` (ClassVar dict) | Type registry: Matrix knows all registered actor types |
| `this.#children` (private instance Map) | `self._actor_children` (instance dict) | Instance children: an actor's spawned sub-actors |
| `ROOT_ACTOR` (module-level singleton) | `Actor.__root__` (ClassVar) | Root reference for message bubbling |

Class-level children hold registered TYPES (Matrix registers Product, User, etc.).
Instance-level children hold spawned SUB-ACTORS (a Product actor might spawn
per-instance child actors for real-time subscriptions).

Both use the same `register()` / `children` interface — the difference is
where state lives (ClassVar vs instance attr).

**Matrix message bus** (`src/pybend/core/actors/matrix.py`):
```python
class Matrix(Actor):
    """Root actor and message router. One per application.
    Mirrors Matrix.js — routes to local children or remote via NetworkAdapter."""

    def __init__(self):
        super().__init__(addr='matrix://root')
        Actor.register_root(self)      # Same as JS: Actor.registerRoot(this)
        self.remote = None             # NetworkAdapter, like JS this.remote
        self._network_adapters: list[NetworkAdapter] = []

    async def inbox(self, tx: TX) -> None:
        """Route message to target actor or network. Fire-and-forget.
        Mirrors JS Matrix.inbox(): children first, then remote."""
        target_root = tx.target.split('/')[0]

        # Local children first (mirrors JS: this.children.has(targetAddr))
        if target_root in self._actor_children:
            await self._actor_children[target_root].inbox(tx)

        # Try network adapters (HTTP, WebSocket, ActivityPub, MCP...)
        elif any(a.can_handle(tx) for a in self._network_adapters):
            for adapter in self._network_adapters:
                if adapter.can_handle(tx):
                    await adapter.send(tx)
                    break

        else:
            # No route — send error back to source
            await self.send(tx.error(f"No route to {tx.target}"))

    def register_adapter(self, adapter: 'NetworkAdapter'):
        """Add a protocol adapter (HTTP, WS, AP, MCP, ATProto...)."""
        self._network_adapters.append(adapter)

# Required initialization — mirrors JS: Actor.subclass(Matrix)
# In Python this is automatic via MI, but we still create the singleton:
matrix = Matrix()  # Root instance, like JS: export const matrix = new Matrix("matrix://root")
```

**TX message envelope** (`src/pybend/core/actors/tx.py`):
```python
@dataclass
class TX:
    """Message envelope. Same semantics as frontend TX.js."""
    name: str          # Event type: SCHEMA, READ, CREATE, UPDATE, DELETE, ERROR...
    source: str        # Sender address
    target: str        # Recipient address
    data: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = field(default_factory=lambda: uuid4().hex[:12])

    def reply(self, **kwargs) -> 'TX':
        """Create a response TX with source/target swapped."""
        return TX(
            name=kwargs.get('name', f'{self.name}_RESPONSE'),
            source=self.target,
            target=self.source,
            data=kwargs.get('data', {}),
            meta={**self.meta, 'in_reply_to': self.correlation_id},
            correlation_id=self.correlation_id,
        )

    def error(self, message: str, code: int = 500) -> 'TX':
        """Create an error response TX.

        This IS the Result type. Success = reply(). Failure = error().
        The 200-OK anti-pattern is eliminated by construction:
        model methods return tx.reply() or tx.error(), never ambiguous strings.
        """
        return TX(
            name='ERROR',
            source=self.target,
            target=self.source,
            data={'message': message, 'code': code},
            meta={**self.meta, 'in_reply_to': self.correlation_id, 'error': True},
            correlation_id=self.correlation_id,
        )

    @property
    def is_error(self) -> bool:
        return self.name == 'ERROR' or self.meta.get('error', False)
```

**Design decisions informed by experience:**
- Built on `asyncio` — lightweight, no heavy framework dependency
- Avoid `ask()` from within handlers — causes deadlocks (documented Pyctor lesson). Use `send()` and correlation IDs for request/response patterns
- Don't `auto_start` actors — set attributes first, then start (documented Pyctor race condition)
- Pipeline stages within actors are synchronous callables, NOT separate actors (avoids unnecessary message-passing overhead for internal transformations)

### 0c. Schema Extension Protocol (~2-3 days)

The pipeline from 0a makes extensions trivial. New capabilities register additional
stages without modifying ProtoModel core.

**ActorModel delegates to ProtoModel.schema():**
```python
class ActorModel(Actor, ProtoModel):
    @classmethod
    def SCHEMA(cls, data, tx: 'TX'):
        """Actor self-description = schema generation.
        Returns data; handler() wraps in tx.reply() and dispatches."""
        return cls.schema()  # ProtoModel.schema() — composable pipeline
```

**Schema extension protocol** — `@schema_extension` registers new pipeline stages:

```python
def schema_extension(after: str = None, before: str = None):
    """Decorator that registers a schema pipeline stage on ProtoModel.

    This is how __federated__, __agent__, __discriminator__, and any future
    ClassVar-driven feature plugs in without touching ProtoModel.

    Example (in a federation package, zero core imports needed):

        @schema_extension(after='_schema_methods')
        def _schema_federation(cls, schema: dict) -> dict:
            if getattr(cls, '__federated__', False):
                schema['federation'] = {
                    'actor_url': f'{API_URL}/{cls.__name__}',
                    'inbox': f'{API_URL}/{cls.__tablename__}/inbox',
                    'outbox': f'{API_URL}/{cls.__tablename__}/outbox',
                }
            return schema

    Example (in an agent package):

        @schema_extension(after='_schema_methods')
        def _schema_agent_tools(cls, schema: dict) -> dict:
            if getattr(cls, '__agent__', False):
                schema['tools'] = convert_methods_to_mcp_tools(schema.get('methods', {}))
            return schema
    """
    def decorator(func):
        func._schema_extension = True
        func._after = after
        func._before = before
        return func
    return decorator
```

Each stage is:
- **Independently testable**: `stage(input_dict)` → `output_dict`
- **Independently overridable**: subclass ProtoModel, override one stage
- **Composable**: stages run in order, each receiving previous output
- **Extensible**: `@schema_extension` adds stages without modifying the list

**Why this is categorically pure:** Each stage is an endofunctor on the category of schema dicts. The pipeline is their composition. Extensions are natural transformations that compose with the pipeline. This isn't CT vocabulary for its own sake — it's a structural guarantee that stages don't interfere with each other.

### 0d. ActorModel — Models That Are Actors (~3-5 days)

The centerpiece. `ActorModel(Actor, ProtoModel)` is the bridge class that makes
models first-class actors. This is the Python equivalent of the frontend's
`Actor.subclass(DynamicClass)`.

**Key insight from research:** Direct inheritance works. ProtoModel already proves
custom `__init__` works with Pydantic (`super().__init__()` chains properly). Actor's
`__init__` follows the same pattern. No `__slots__` needed — just regular attributes.
No mixin injection, no decorators, no metaclass hacks. Plain Python MI.

```python
class ActorModel(Actor, ProtoModel):
    """A model that IS an actor. The bridge class.

    Inherits from Actor (messaging) and ProtoModel (data/schema/validation).
    Concrete models inherit from this instead of ProtoModel directly.

    MRO: Product → ActorModel → Actor → ProtoModel → PydanticBaseModel → object
    __init__ chain: Actor.__init__ (sets actor state) → ProtoModel.__init__
                    (storable check) → PydanticBaseModel.__init__ (validates fields)

    Handles:
    - SCHEMA: runs pipeline, returns capability manifest
    - READ/CREATE/UPDATE/DELETE: delegates to StorableMixin (unchanged)
    - Custom methods (comment, like, favorite): dispatched by name
    - Lifecycle events: publishes TX messages to subscribers
    """

    _subscribers: ClassVar[list[str]] = []  # Actors subscribed to lifecycle events

    @property
    def addr(self) -> str:
        """Instance addr = tablename/id (mirrors JS DynamicClass instance addr)."""
        tablename = getattr(self.__class__, '__tablename__', self.__class__.__name__.lower())
        return f"{tablename}/{self.id}" if self.id else f"{tablename}/new"

    # ── CRUD handlers — delegate to StorableMixin (which is UNCHANGED) ──
    # Each method returns data. handler() wraps in tx.reply() and dispatches.
    # For errors, raise MethodError (or return tx.error() — TBD).

    @classmethod
    def CREATE(cls, data, tx: 'TX'):
        """Create via StorableMixin, then publish lifecycle event."""
        instance = cls(**data)
        result = cls.create(instance)  # StorableMixin.create() — unchanged
        if result:
            cls._publish_lifecycle('after_create', result.model_dump(response=True))
        return result.model_dump(response=True)

    @classmethod
    def READ(cls, data, tx: 'TX'):
        """Read via StorableMixin."""
        entity_id = data.get('id')
        if entity_id:
            result = cls.get(entity_id)  # StorableMixin.get() — unchanged
            if not result:
                return tx.error(f"{cls.__name__} {entity_id} not found", code=404)
            return result.model_dump(response=True)
        else:
            limit = data.get('limit', 20)
            offset = data.get('offset', 0)
            return cls.list(limit=limit, offset=offset)  # StorableMixin.list()

    @classmethod
    def SCHEMA(cls, data, tx: 'TX'):
        """Actor self-description = schema generation via composable pipeline."""
        return cls.schema()  # ProtoModel.schema() — unchanged

    def UPDATE(self, data, tx: 'TX'):
        result = self.__class__.update(self.id, data)  # StorableMixin.update()
        if result:
            self.__class__._publish_lifecycle('after_update', result.model_dump(response=True))
        return result.model_dump(response=True)

    def DELETE(self, data, tx: 'TX'):
        self.__class__.delete(self.id)  # StorableMixin.delete()
        self.__class__._publish_lifecycle('after_delete', {'id': self.id})
        return {'deleted': self.id}

    # ── Lifecycle events (FREE — just TX messages) ──

    @classmethod
    def _publish_lifecycle(cls, event: str, data: dict):
        """Publish lifecycle event to all subscribers. Fire-and-forget.

        Federation: subscriber is OutboxActor → queues AP Create activity
        Agents: subscriber is MonitorActor → triggers analysis
        Audit: subscriber is AuditActor → logs event
        Real-time: subscriber is WebSocketBridge → pushes to frontend
        """
        for subscriber_addr in cls._subscribers:
            asyncio.create_task(cls.send_cls(TX(
                name='LIFECYCLE',
                source=cls.__name__,
                target=subscriber_addr,
                data={'event': event, 'entity': data},
            )))  # Fire-and-forget via event loop
```

**What the developer writes (minimal change from today):**
```python
# Before (v0.7.0):
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> str: ...

# After (v0.8.0):
class Product(ActorModel):          # ← Only change: ProtoModel → ActorModel
    __tablename__ = 'products'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> str: ...
```

One import change, zero other changes. Product is now an actor that can receive TX
messages, participate in the Matrix, publish lifecycle events, and be addressed by
federation and agent systems — all while keeping the exact same CRUD and schema behavior.

**Join models stay on ProtoModel** — they don't need actor behavior:
```python
# generate_join_model() continues to create:
# class ProductComment(Comment): ...  ← inherits from Comment(ActorModel)
# Join models inherit actor behavior but that's harmless — lightweight methods
# that are never called if not addressed. No registration cost.
```

**Model registration becomes actor registration:**
```python
# Before:
register_model(Product, storage=sqlite_backend)
register_routes(registered_models)

# After:
def register_model(model_cls, storage):
    model_cls.set_storage(storage)          # StorableMixin — unchanged
    model_cls.create_table()                 # StorableMixin — unchanged
    matrix.register(model_cls)               # NEW: register in actor tree
    registered_models[model_cls.__tablename__] = model_cls  # unchanged

# Routes unchanged for now — RouteActor bridge deferred to Wave 2
```

**Schema served as actor self-description (Wave 0 — routes unchanged):**
```
GET /Product → route handler calls Product.schema() directly (as today)
            → ProtoModel.schema() runs composable pipeline (0a)
            → Returns schema dict → HTTP JSON response
```
**After Wave 2 (RouteActor bridge):**
```
GET /Product → RouteActor sends TX(name='SCHEMA', target='Product')
            → Matrix routes to Product (which IS an ActorModel)
            → handler() calls Product.SCHEMA() → wraps in tx.reply() → dispatches
            → RouteActor awaits reply → translates to HTTP JSON response
```

### 0e. model_dump as TX Message Types (~1-2 days)

Instead of `model_dump(response=True)` (boolean flag), different message types:

```python
class ActorModel(Actor, ProtoModel):
    def DUMP(self, data, tx: TX):
        """Plain data extraction. For storage, agents, internal use.
        Returns data; handler() wraps in tx.reply() and dispatches."""
        return self.model_dump()  # No metadata

    def DUMP_RESPONSE(self, data, tx: TX):
        """Data + $schema/$id. For HTTP API responses."""
        return self.model_dump(response=True)  # Existing method

    def DUMP_ACTIVITY(self, data, tx: TX):
        """Data + ActivityStreams context. For federation."""
        d = self.model_dump()
        d['@context'] = 'https://www.w3.org/ns/activitystreams'
        d['type'] = self.__class__.__name__
        d['id'] = f"{API_URL}/{self.__class__.__tablename__}/{self.id}"
        return d
```

**CT alignment:** Three distinct morphisms, not one bifurcated morphism. Each is independently testable and composable.

### 0f. Comprehensive Testing (~3-5 days)

The new Actor system and schema pipeline must be proven correct before anything builds
on top. This is not a "write a few smoke tests" task — it's full-coverage verification
of the foundation everything else depends on.

**Actor system unit tests** (`test_actor_system.py`):
```python
# Actor base class
- test_actor_init_sets_addr_and_children
- test_actor_addr_defaults_to_classname
- test_actor_addr_uses_tablename_when_available
- test_actor_register_child_sets_parent
- test_actor_register_child_adds_to_children
- test_actor_spawn_creates_and_registers
- test_actor_register_cls_adds_to_class_children
- test_actor_register_root_sets_class_root
- test_actor_send_routes_to_parent
- test_actor_send_routes_to_root_when_no_parent
- test_actor_send_raises_when_no_root

# inbox / handler flow
- test_inbox_calls_handler
- test_inbox_is_fire_and_forget_returns_none
- test_handler_dispatches_to_named_method
- test_handler_wraps_dict_return_in_tx_reply
- test_handler_wraps_scalar_return_in_tx_reply
- test_handler_passes_tx_error_through_directly
- test_handler_sends_error_for_unhandled_message
- test_handler_supports_sync_methods
- test_handler_supports_async_methods

# Matrix
- test_matrix_is_singleton_root
- test_matrix_routes_to_local_children
- test_matrix_sends_error_for_unknown_target
- test_matrix_delegates_to_network_adapter
- test_matrix_register_adapter

# TX envelope
- test_tx_creation_with_defaults
- test_tx_reply_swaps_source_target
- test_tx_reply_preserves_correlation_id
- test_tx_error_sets_error_name_and_meta
- test_tx_is_error_property
- test_tx_from_dict_roundtrip
```

**Schema pipeline unit tests** (`test_schema_pipeline.py`):
```python
# Each stage independently
- test_schema_base_produces_pydantic_json_schema
- test_schema_strip_hidden_removes_display_false_fields
- test_schema_methods_injects_expose_route_signatures
- test_schema_defs_processes_nested_models
- test_schema_defs_injects_access_on_each_def
- test_schema_access_serializes_abac_rules
- test_schema_ui_injects_field_order_groups_renderer
- test_schema_metadata_adds_schema_id_name_tablename

# Composability
- test_pipeline_output_matches_current_monolithic_schema  # CRITICAL: zero regression
- test_stages_are_independently_callable
- test_stage_order_matters_for_metadata  # metadata must be last
- test_custom_stage_can_override_via_subclass

# Schema extension protocol
- test_schema_extension_registers_after_stage
- test_schema_extension_registers_before_stage
- test_multiple_extensions_compose_in_order
- test_extension_receives_schema_dict_and_returns_schema_dict
```

**ActorModel integration tests** (`test_actor_model.py`):
```python
# CRUD via actor messaging
- test_actormodel_create_via_handler
- test_actormodel_read_by_id_via_handler
- test_actormodel_read_list_via_handler
- test_actormodel_update_via_handler
- test_actormodel_delete_via_handler
- test_actormodel_schema_via_handler

# Lifecycle events
- test_create_publishes_after_create_lifecycle
- test_update_publishes_after_update_lifecycle
- test_delete_publishes_after_delete_lifecycle
- test_lifecycle_event_reaches_subscriber

# Custom methods dispatched by name
- test_custom_method_dispatched_via_handler  # e.g. TX(name='favorite')
- test_custom_method_return_wrapped_in_reply

# Error handling
- test_read_nonexistent_returns_tx_error_404
- test_unhandled_message_returns_tx_error
- test_handler_error_does_not_crash_actor

# model_dump TX types
- test_dump_returns_plain_data
- test_dump_response_returns_data_with_schema_id
- test_dump_activity_returns_data_with_activitystreams_context
```

**Regression tests** — existing tests must pass unchanged:
```python
# Run ALL existing test suites after Wave 0:
# - src/pybend/core/tests/unit/        (framework unit tests)
# - src/pybend/example/tests/           (integration tests: CRUD, auth, pagination, FK hydration)
#
# If any existing test fails, the refactor is wrong — not the test.
# Zero tolerance for regression.
```

**Edge cases and error conditions:**
```python
- test_actor_with_no_methods_returns_error_for_all_messages
- test_matrix_with_no_children_returns_error
- test_tx_error_code_propagates_correctly
- test_concurrent_inbox_calls_dont_corrupt_state
- test_circular_parent_child_prevented
- test_actor_init_chaining_with_pydantic_fields  # MI + Pydantic validation
- test_actormodel_without_storable_mixin_raises
- test_schema_pipeline_with_empty_model
- test_schema_pipeline_with_all_field_types
- test_lifecycle_publish_with_no_subscribers_is_noop
```

### Wave 0 Deliverable

Backend runs on Actor/Matrix/TX with schema pipeline built in. **Same external API** — all URLs, responses, and behavior unchanged. Existing tests pass. But internally:

- Communication is message-based (TX envelopes routed by Matrix)
- Schema is composable (pipeline stages within ProtoModel, served by ActorModel)
- Schema is extensible (`@schema_extension` adds stages without core changes)
- Events are free (lifecycle TX messages to subscribers)
- Errors are typed (TX.error() — not exception-based, not 200-OK strings)
- model_dump variants are distinct message types (not boolean flags)
- Models are actors (ActorModel) with inbox, handler, send — same patterns as frontend
- Routes and storage unchanged — existing FastAPI routes call StorableMixin directly (as today)

**What Wave 0 makes possible:**
- MCP = new NetworkAdapter that speaks JSON-RPC
- ActivityPub = new NetworkAdapter that speaks HTTP Signatures + JSON-LD
- WebSocket real-time = new NetworkAdapter that bridges to frontend Matrix
- Microservice extraction = move actor to remote Matrix
- Agent = Actor subclass that calls LLM in its message handler

---

## Wave 1: Agent + Federation Capabilities

**Duration**: ~2.5 weeks
**Depends on**: Wave 0 (Actor/Matrix/TX + schema pipeline)
**Purpose**: Ship working capabilities for both priority themes. Every item delivers real value.

### Motivation

With Wave 0 complete, both MCP and ActivityPub become **protocol adapters** rather than new subsystems. The actor architecture provides routing, messaging, lifecycle events, and typed responses. We only need to translate between TX messages and protocol-specific wire formats.

### 1a. MCP NetworkAdapter (~3-5 days)

MCP (Model Context Protocol) is JSON-RPC 2.0 over stdio or SSE. The adapter translates between MCP messages and TX messages.

```python
class MCPAdapter(NetworkAdapter):
    """Translates MCP JSON-RPC ↔ TX messages."""

    async def handle_tools_list(self) -> list[dict]:
        """MCP tools/list → ask each ActorModel for its schema.
        Uses request() which awaits reply by correlation_id."""
        tools = []
        for actor in self.matrix.children.values():
            if isinstance(actor, ActorModel):
                response = await self.request(TX(name='SCHEMA', source='mcp', target=actor.addr))
                tools.extend(self._schema_to_mcp_tools(response.data))
        return tools

    async def handle_tools_call(self, tool_name: str, arguments: dict) -> dict:
        """MCP tools/call → route TX to appropriate ActorModel.
        Uses request() which awaits reply by correlation_id."""
        model_name, action = self._parse_tool_name(tool_name)
        tx = TX(name=action.upper(), source='mcp', target=model_name, data=arguments)
        response = await self.request(tx)  # Await reply via correlation_id
        if response.is_error:
            return {"error": response.data}
        return response.data

    def _schema_to_mcp_tools(self, schema: dict) -> list[dict]:
        """Mechanical conversion: ~20-30 lines.

        Each CRUD operation + each @expose_route method becomes a tool.
        Schema carries: method name, parameters with types, description, access rules.
        MCP needs: tool name, inputSchema (JSON Schema), description.
        The translation is reformatting, not transformation.
        """
        tools = []
        tablename = schema.get('__tablename__', '')
        # CRUD tools
        for action in ['list', 'get', 'create', 'update', 'delete']:
            tools.append({
                'name': f'{tablename}_{action}',
                'description': f'{action.title()} {schema.get("__name__", "")}',
                'inputSchema': self._crud_input_schema(action, schema),
            })
        # Custom method tools
        for name, method in schema.get('methods', {}).items():
            tools.append({
                'name': f'{tablename}_{name}',
                'description': method.get('description', name),
                'inputSchema': {
                    'type': 'object',
                    'properties': method.get('parameters', {}),
                },
            })
        return tools
```

**Integration:**
```python
app = create_app(models=[Product, User, Comment], storage=storage, mcp=True)
# ^^^ registers MCPAdapter on the Matrix alongside HTTPAdapter
```

The day this ships, every PyBend app is accessible to Claude Desktop, Cursor, GPT, and 10,000+ MCP clients.

### 1b. Federation NetworkAdapter (~4-5 days)

ActivityPub is HTTP-based actor messaging. The structural mapping:

| ActivityPub | PyBend Actor |
|---|---|
| Actor with inbox/outbox | Actor with `inbox()` / `send()` |
| Activity (Create, Update, Delete) | TX with `name` (CREATE, UPDATE, DELETE) |
| Actor URI | Actor `addr` / entity `$id` |
| HTTP Signature | Authentication at network boundary |
| WebFinger | Actor address resolution |

```python
class ActivityPubAdapter(NetworkAdapter):
    """Translates ActivityPub ↔ TX messages."""

    async def handle_inbox(self, activity: dict, request: Request) -> None:
        """POST /users/{id}/inbox → validate signature → TX to ActorModel."""
        if not await self._verify_http_signature(request):
            return  # HTTP 401 returned at route level

        # Map AP activity to TX and dispatch into Matrix (fire-and-forget)
        action = activity['type'].upper()  # Create → CREATE
        target_model = self._resolve_model(activity['object']['type'])
        tx = TX(
            name=action,
            source=activity['actor'],  # Remote actor URI
            target=target_model,
            data=activity['object'],
            meta={'federated': True, 'actor': activity['actor']},
        )
        await self.matrix.inbox(tx)  # Fire-and-forget

    async def handle_outbox(self, model_name: str, tx: TX):
        """Lifecycle event → serialize as AP Activity → deliver to followers."""
        activity = {
            '@context': 'https://www.w3.org/ns/activitystreams',
            'type': tx.data['event'].replace('after_', '').title(),  # after_create → Create
            'actor': f'{API_URL}/{model_name}',
            'object': tx.data['entity'],
            'published': datetime.utcnow().isoformat() + 'Z',
        }
        # Deliver to followers (async, with retry)
        for follower_inbox in await self._get_follower_inboxes(model_name):
            await self._deliver(activity, follower_inbox)
```

**WebFinger** (actor address resolution):
```python
# GET /.well-known/webfinger?resource=acct:alice@example.com
# Returns links to the actor's AP Actor document and PyBend schema
```

**What ships:** Models with `__federated__ = True` produce valid ActivityPub Actor documents. WebFinger makes them discoverable. Lifecycle events (CREATE, UPDATE, DELETE via TX messages) are serialized as Activities and delivered to followers. Inbound activities from the Fediverse are validated and routed through the Matrix to ActorModels.

### 1c. Agent + Federation Access Rules (~2-3 days)

New `AccessRule` subclasses for both ecosystems. Zero authorization engine changes — these are purely additive leaf classes.

```python
# Agent-specific rules:
class Budget(AccessRule):
    """Allow if agent has remaining budget above threshold."""
    def __init__(self, min_remaining: float = 0): ...
    def evaluate(self, ctx: AccessContext) -> bool: ...

class DelegationDepth(AccessRule):
    """Allow if agent delegation chain hasn't exceeded depth."""
    def __init__(self, max_depth: int = 3): ...

# Federation-specific rules:
class Federated(AccessRule):
    """Allow only federated (non-local) actors."""
    def evaluate(self, ctx: AccessContext) -> bool:
        return ctx.meta.get('federated', False)

class Local(AccessRule):
    """Allow only local (non-federated) users."""
    def evaluate(self, ctx: AccessContext) -> bool:
        return not ctx.meta.get('federated', False)

class Follower(AccessRule):
    """Allow only users who follow this entity's owner."""
    def evaluate(self, ctx: AccessContext) -> bool: ...
```

They compose with existing rules using the standard `|`/`&`/`~` operators:
```python
__access__ = {
    'read': ANYONE,
    'create': LOCAL & AUTHENTICATED,
    'update': OWNER | (FEDERATED & FOLLOWER),
    'invoke': AUTHENTICATED & Budget(min_remaining=0.10),
}
```

### 1d. Discovery Endpoints (~2-3 days)

Three endpoints, one pattern, two ecosystems unlocked:

```
GET /_meta                     → Model registry, capabilities, health
GET /.well-known/agent.json    → A2A Agent Card (agent discovery)
GET /.well-known/webfinger     → WebFinger (federation discovery)
```

All generated from the Matrix's actor registry — "ask the Matrix for its registered actors and their capabilities."

### 1e. AccessRule Algebra Verification (~2-3 days)

Before extending the algebra with agent and federation rules, verify it's sound:

```python
# test_access_algebra.py — property-based tests:
# Commutativity: A | B == B | A
# Associativity: (A | B) | C == A | (B | C)
# Distributivity: A & (B | C) == (A & B) | (A & C)
# De Morgan: ~(A | B) == ~A & ~B
# Identity: A | NEVER == A, A & ANYONE == A
# Annihilation: A & NEVER == NEVER, A | ANYONE == ANYONE
```

Add `NEVER` bottom element (complement to `ANYONE`) — needed for agent deny-by-default patterns.

### Wave 1 Deliverable

- Working MCP server: any AI agent can discover and call PyBend model methods
- Working ActivityPub: models with `__federated__` produce AP Actors discoverable via WebFinger
- A2A Agent Card at `/.well-known/agent.json`
- Algebraically verified access control extended for agents + federation
- All from protocol adapters on the actor architecture — minimal new code

---

## Wave 2: Actor Infrastructure Actors

**Duration**: ~1.5-2 weeks
**Depends on**: Wave 1 (MCP + federation capabilities)
**Purpose**: Wrap storage, routing, and authorization behind actor messaging. Routes become thin TX bridges.

### Motivation

Wave 0 established the Actor/Matrix/TX core and ActorModel. Routes and storage still use
direct function calls (unchanged from v0.7.0). Wave 2 completes the actor transition by
making storage, routing, and authorization actor-based — enabling testability, swappability,
and the microservice extraction path.

### 2a. StorageActor (~3-5 days)

Wrap storage behind actor messaging. CRUD operations become TX messages.

```python
class StorageActor(Actor):
    """Handles CRUD messages against a storage backend."""

    def __init__(self, addr: str, backend: AbstractStorage):
        super().__init__(addr=addr)
        self.backend = backend

    def CREATE(self, data, tx: TX):
        model_cls = tx.meta['model_cls']
        instance = model_cls(**data)
        result = self.backend.create(instance)
        return result.model_dump()

    def READ(self, data, tx: TX):
        model_cls = tx.meta['model_cls']
        entity_id = data.get('id')
        if entity_id:
            result = self.backend.get(model_cls, entity_id)
            if not result:
                return tx.error(f"{model_cls.__name__} {entity_id} not found", code=404)
            return result.model_dump()
        else:
            limit = data.get('limit', 20)
            offset = data.get('offset', 0)
            results, total = self.backend.list(model_cls, limit=limit, offset=offset)
            return {
                'data': [r.model_dump() for r in results],
                'meta': {'total': total, 'limit': limit, 'offset': offset}
            }

    def UPDATE(self, data, tx: TX): ...
    def DELETE(self, data, tx: TX): ...
```

**Why actor-based storage matters:**
- **Transaction isolation**: Actor processes messages sequentially — no concurrent mutation bugs
- **Multiple backends**: Different StorageActor instances for different storage backends
- **Testability**: Replace StorageActor with InMemoryStorageActor for tests — no DB needed
- **Microservice path**: Replace local StorageActor with RemoteStorageActor — no code changes
- **CT alignment**: Store/Retrieve adjunction formalized as TX round-trip

### 2b. RouteActor Bridge (~3-5 days)

Bridge HTTP requests to TX messages. FastAPI route handlers become thin translators.

```python
class RouteActor(Actor):
    """Bridges HTTP ↔ Actor messaging."""

    def __init__(self, addr: str = 'routes'):
        super().__init__(addr=addr)
```

**FastAPI integration:**
```python
# In routes_fastapi.py, the route factory creates TX and sends to Matrix.
# Since inbox is fire-and-forget, RouteActor uses correlation_id + Future
# to await the response asynchronously.
async def get_product(id: int, request: Request):
    tx = TX(name='READ', source='routes/products', target='Product', data={'id': id})
    response = await route_actor.request(tx)  # Awaits reply by correlation_id
    if response.is_error:
        raise HTTPException(response.data['code'], response.data['message'])
    return response.data
```

### 2c. AuthActor (~2-3 days)

Authorization becomes a message interceptor in the routing chain:

```python
class AuthActor(Actor):
    """Intercepts TX messages and evaluates ABAC rules before forwarding."""

    def handler(self, tx: TX):
        user = tx.meta.get('user')
        action = tx.name.lower()  # 'create', 'read', 'update', 'delete'
        model_cls = tx.meta.get('model_cls')

        if model_cls and hasattr(model_cls, '__access__'):
            rule = model_cls.__access__.get(action)
            if rule and not rule.evaluate(AccessContext(user=user, action=action)):
                return tx.error("Access denied", code=403)

        # Forward to actual target
        self.send(tx)
```

### Wave 2 Deliverable

- Storage behind actor messaging (swappable, mockable, remotable)
- Routes as thin TX bridges (HTTP → TX → Actor → TX → HTTP)
- Authorization as message interceptor (not hardwired into route handlers)
- All existing tests still pass — same external API, actor-based internally

---

## Wave 3: Unification + Deepening

**Duration**: ~2 weeks
**Depends on**: Wave 2 (infrastructure actors)
**Purpose**: Complete the frontend/backend unification. Deepen CT verification. Add polymorphism.

### 3a. WebSocket Bridge (~3-5 days)

Connect frontend Matrix to backend Matrix. TX messages flow transparently.

```
Frontend Matrix ←──WebSocket──→ Backend Matrix
```

- Frontend actor sends TX to `Product/42` → Matrix routes through WebSocket → backend ActorModel handles it
- Backend ActorModel publishes lifecycle event → Matrix routes through WebSocket → frontend actor receives update
- **Real-time updates are free.** No separate pub/sub system needed.

### 3b. Polymorphic Actor Types (~3-4 days)

`__discriminator__` as schema extension + storage behavior:

```python
class Content(ActorModel):
    __tablename__ = 'content'
    __discriminator__ = '_type'  # Adds _type column, enables STI
    title: str

class Article(Content):
    body: str

class Video(Content):
    video_url: str
    duration: int
```

Auto-generates:
- `_type TEXT NOT NULL` column in storage
- `Article.list()` adds `WHERE _type = 'article'`; `Content.list()` returns all
- Schema output with `oneOf` + `discriminator` + per-subtype `$defs`
- Frontend `NTT.SCHEMA()` creates per-subtype DynamicClasses

**Why here:** Agent types (ResearchAgent, TriageAgent) and federation activity types (Create, Update, Delete) are natural polymorphic hierarchies.

### 3c. Storage Adjunction + Functor Law Verification (~2-3 days)

CT verification to ensure correctness before scaling:

- **Storage adjunction**: `get(create(m)).scalar_fields == m.scalar_fields` for all storable types
- **DynamicClass functor**: schema properties → getters/setters, methods → callables, $defs → nested classes
- Document known asymmetries (collections, FK hydration, defaults)

### 3d. SSR Data Pre-loading (~2-4 hours)

Quick win: server injects schema + data into HTML. The frontend already has `#consumePreloadedSchema()` and `#consumePreloadedData()` in NTT.js (lines 244-277). This eliminates 400-600ms of waterfall latency.

```html
<script type="application/json" data-ntt-schema>{"Product": ...}</script>
<script type="application/json" data-ntt-data>{"products": [...]}</script>
```

### Wave 3 Deliverable

Full-stack unification (frontend ↔ backend Matrix via WebSocket), polymorphic type hierarchies, verified storage and functor laws, and 400-600ms latency elimination.

---

## Wave 4+: Demand-Gated Capabilities

Each item has a **trigger** — the measurable condition that justifies building it. No speculative investment.

| Item | Trigger | Builds On | Effort |
|---|---|---|---|
| **AgentMixin + LLMClient** | MCP tools validated with real agent consumers | Wave 0 actors + Wave 1 MCP | 3-4 weeks |
| **AgentMemory** | Agent state management need in production | Wave 0 StorageActor | 1 week |
| **Full AP bidirectional** | External federation demand | Wave 1 AP adapter | 6-10 weeks |
| **ATProtocol adapter** | Bluesky ecosystem reaches critical mass | Wave 0 NetworkAdapter | 10-16 weeks |
| **DID-based identity** | eIDAS 2.0 mandate (Nov 2026) or federation demand | Wave 1 federation | 2-3 weeks |
| **CLI entry point** | Developer community grows | Wave 0 schema pipeline | 2-3 weeks |
| **Template compiler** | FCP >500ms on mobile after caching | Wave 0 schema consumer | 3-5 weeks |
| **TUI dashboard** | SSH administration demand | Wave 0 schema pipeline | 3-4 weeks |
| **RemoteStorage** | Team >10, service extraction needed | Wave 0 StorageActor | 1-2 weeks |
| **VC_CLAIM rule** | eIDAS 2.0 wallet mandate (Nov 2026) | Wave 1 ABAC rules | 1 week |
| **Multi-agent orchestration** | Single agents stable 2+ months | Wave 4+ AgentMixin | 4-8 weeks |
| **Static site export** | Content hosting cost matters | Wave 0 schema consumer | 1-2 weeks |

**Pattern:** Every item is either a new Actor type, a new NetworkAdapter, a new schema extension, or a new schema consumer. The Wave 0 architecture makes each one a bounded, predictable effort.

---

## 10. Cross-Cutting Impact Matrix

This matrix shows which of the 13 research themes benefit from each Wave 0-2 change.

| Change | AI Agents | Schema-Agentic | Schema-Agents | Federation | Micro-services | Polymorphic | Cat Theory | CLI | HTML Compiler | SSR | Micro-FE | GraphQL | Wasm |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **0a. Schema pipeline decomp** | X | X | X | X | X | X | X | X | X | X | | X | |
| **0b. Actor/Matrix/TX core** | X | X | X | X | X | | X | | | | X | | |
| **0c. Schema extension proto** | X | X | X | X | X | X | X | X | X | X | | X | |
| **0d. ActorModel** | X | X | X | X | X | X | X | X | | | | | |
| **0e. model_dump TX types** | X | X | | X | X | | X | | X | X | | | |
| **0f. Comprehensive testing** | X | X | X | X | X | X | X | X | X | X | X | X | |
| **1a. MCP adapter** | X | X | X | | X | | | X | | | | | |
| **1b. Federation adapter** | | | | X | | | | | | | | | |
| **1c. Agent+Fed ABAC rules** | X | X | | X | | | X | | | | | | |
| **1d. Discovery endpoints** | X | X | X | X | X | | | X | | | | | |
| **1e. ABAC algebra verification** | X | X | | X | | X | X | | | | | | |
| **2a. StorageActor** | X | X | X | X | X | | X | | | | | | |
| **2b. RouteActor bridge** | X | | | X | X | | X | | | X | | | |
| **2c. AuthActor** | X | X | | X | X | | X | | | | | | |
| **3a. WebSocket bridge** | X | | | X | | | | | | X | X | | |
| **3b. Polymorphic types** | X | X | | X | X | X | | | | | | X | |
| **3c. CT verification** | X | | | X | | | X | | | | | | |
| **3d. SSR pre-loading** | | | | | | | | | X | X | X | | |

**Legend:** X = directly enables or benefits the theme.

**Key observation:** Wave 0 items (the actor architecture) hit 7-10 themes each. Wave 1 items (protocol adapters) hit 2-5 themes each. This confirms the thesis: the actor architecture is the highest-leverage investment.

---

## 11. Risk and Decision Framework

### Architectural Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Actor refactor breaks existing API** | Medium | High | Integration tests: all URLs, responses, and behavior unchanged. RouteActor produces identical HTTP output. |
| **Async migration complexity** | Medium | Medium | FastAPI already async. StorableMixin wraps sync SQLite calls in `run_in_executor`. Gradual migration. |
| **Over-engineering the actor system** | Medium | Medium | Strict scope: message routing + lifecycle + pipeline. No supervision trees, no distributed consensus, no event sourcing in Wave 0. |
| **MCP protocol evolves** | Low | Low | Thin adapter (~200 LOC) is cheap to update. No deep coupling. |
| **ActivityPub compatibility** | Medium | Medium | Start with publish-only (outbox). Full bidirectional is Wave 4+ and demand-gated. |
| **Performance overhead of message passing** | Low | Medium | Benchmark: if actor overhead exceeds 5ms per request, optimize hot paths. Pipeline stages are sync callables (not separate actors). |
| **Schema pipeline extension conflicts** | Low | Medium | Extensions are ordered (after/before constraints). Test: composed schema matches expected output. |

### Decision Heuristics

1. **"Is this a new Actor, a new NetworkAdapter, or a new schema extension?"** If yes, it fits the architecture. If it requires modifying the Matrix or TX core, reconsider.

2. **"Does the external API change?"** Wave 0 must preserve all existing URLs, responses, and behavior. The refactor is internal. If a test fails, the refactor is wrong, not the test.

3. **"Would this be simpler as a direct function call?"** Not every internal operation needs to be a TX message. Pipeline stages within ProtoModel are direct function calls. Actor boundaries should be at meaningful isolation points (Model, Storage, Auth), not at every method.

4. **"Does this serve 2+ of the priority themes?"** Changes serving AI + Federation + CT come first. Single-theme changes are demand-gated.

---

## 12. Success Metrics

### Wave 0 (Foundation)
- [ ] All existing tests pass (zero regression)
- [ ] All existing URLs return identical responses
- [ ] Schema pipeline: each stage independently testable with >=90% coverage
- [ ] TX message round-trip: send → route → handler → dispatch < 1ms overhead
- [ ] ActorModel handles SCHEMA, READ, CREATE, UPDATE, DELETE via handler()
- [ ] inbox() is fire-and-forget (no return value)
- [ ] handler() looks up method, executes, wraps return in tx.reply(), dispatches via send()
- [ ] Lifecycle events: ActorModel publishes after_create/update/delete TX messages
- [ ] Schema extension: `@schema_extension` adds stage without modifying ProtoModel
- [ ] No `model_dump(response=True)` calls remain — all converted to TX message types
- [ ] All Wave 0 tests pass: actor system, schema pipeline, ActorModel, regression
- [ ] Edge cases covered: no methods, no children, error propagation, concurrent access
- [ ] All existing tests pass unchanged (zero regression)

### Wave 1 (Capabilities)
- [ ] MCP adapter: `tools/list` returns all registered model tools
- [ ] MCP adapter: `tools/call` successfully executes CRUD + custom methods
- [ ] At least one external MCP client (Claude Desktop or Cursor) calls a PyBend tool
- [ ] A2A Agent Card at `/.well-known/agent.json` validates against A2A schema
- [ ] WebFinger at `/.well-known/webfinger` resolves user to AP Actor URL
- [ ] Federation adapter: `__federated__` model produces valid AP Actor document
- [ ] Agent + Federation ABAC rules compose correctly (algebra test suite)
- [ ] `NEVER` rule passes identity/annihilation tests

### Wave 2 (Infrastructure Actors)
- [ ] StorageActor passes existing storage tests via TX interface
- [ ] RouteActor produces identical HTTP responses to current route handlers
- [ ] AuthActor intercepts and evaluates ABAC rules via TX messages
- [ ] All existing tests still pass — same external API, actor-based internally

### Wave 3 (Unification)
- [ ] WebSocket bridge: frontend TX reaches backend ActorModel and vice versa
- [ ] Real-time: backend CREATE → frontend update without polling
- [ ] Polymorphic: `Content.list()` returns mixed subtypes with correct `_type`
- [ ] Polymorphic schema: `oneOf` + `discriminator` in JSON Schema output
- [ ] Storage adjunction: round-trip test passes for all field types
- [ ] SSR pre-loading: page load < 1000ms (from ~1500-2000ms current)

---

## 13. File Index

### Existing Files (Modified by This Roadmap)

| File | Role | Waves |
|------|------|:-----:|
| `src/pybend/core/models/proto_model.py` | Base model, schema generation → pipeline decomposed into composable stages | W0 |
| `src/pybend/core/models/base_user.py` | User model → gains DID fields (Wave 4+) | W3+ |
| `src/pybend/core/models/storable_mixin.py` | CRUD ops — **unchanged**, ActorModel delegates to these methods | W0 |
| `src/pybend/core/api/routes_fastapi.py` | Route factories → delegate to RouteActor bridge | W2, W1 |
| `src/pybend/core/authorize/rules.py` | AccessRule hierarchy → gains agent/federation subclasses | W1 |
| `src/pybend/core/storage/sqlite_storage.py` | SQLite backend → wrapped by StorageActor | W2 |
| `src/pybend/core/storage/sqlite_migration.py` | Auto-migration → gains `_type` column for polymorphism | W3 |
| `src/pybend/core/app.py` | PyBendApp builder → spawns actors on Matrix | W0 |
| `src/pybend/core/utils/decorators.py` | `@expose_route` → methods become actor message handlers | W0 |
| `src/pybend/core/utils/registrar.py` | `registered_models` → replaced by Matrix actor registry | W0 |
| `src/pybend/__init__.py` | Public API re-exports | W0, W1 |
| `src/pybend/static/core/NTT.js` | Entity system → consumes preloaded data (W3d) | W3 |
| `src/pybend/static/core/Matrix.js` | Frontend message bus → bridges to backend Matrix | W3 |
| `src/pybend/static/generators/form.js` | Form generator | W3 |

### New Files (Created by This Roadmap)

| File | Wave | Purpose |
|------|:----:|---------|
| `src/pybend/core/actors/__init__.py` | W0 | Actor system package |
| `src/pybend/core/actors/actor.py` | W0 | Base Actor class |
| `src/pybend/core/actors/matrix.py` | W0 | Matrix message bus |
| `src/pybend/core/actors/tx.py` | W0 | TX message envelope |
| `src/pybend/core/actors/actor_model.py` | W0 | ActorModel(Actor, ProtoModel) — bridge class (CRUD + lifecycle) |
| `src/pybend/core/actors/storage_actor.py` | W2 | StorageActor (CRUD behind messages) |
| `src/pybend/core/actors/route_actor.py` | W2 | RouteActor (HTTP ↔ TX bridge) |
| `src/pybend/core/actors/auth_actor.py` | W2 | AuthActor (ABAC message interceptor) |
| `src/pybend/core/actors/schema_ext.py` | W0 | `@schema_extension` decorator + ProtoModel pipeline stage registry |
| `src/pybend/core/actors/adapters/__init__.py` | W1 | NetworkAdapter package |
| `src/pybend/core/actors/adapters/mcp_adapter.py` | W1 | MCP JSON-RPC ↔ TX |
| `src/pybend/core/actors/adapters/ap_adapter.py` | W1 | ActivityPub ↔ TX |
| `src/pybend/core/actors/adapters/ws_adapter.py` | W3 | WebSocket bridge (frontend ↔ backend Matrix) |
| `src/pybend/core/api/discovery.py` | W1 | `/_meta`, `/.well-known/agent.json`, `/.well-known/webfinger` |
| `src/pybend/core/tests/unit/test_access_algebra.py` | W1 | Boolean algebra law tests |
| `src/pybend/core/tests/unit/test_storage_adjunction.py` | W3 | Storage round-trip tests |
| `src/pybend/core/tests/unit/test_actor_system.py` | W0 | Actor/Matrix/TX unit tests (inbox, handler, send, register, routing) |
| `src/pybend/core/tests/unit/test_schema_pipeline.py` | W0 | Schema pipeline stage tests (each stage + composition + regression) |
| `src/pybend/core/tests/unit/test_actor_model.py` | W0 | ActorModel integration tests (CRUD, lifecycle, custom methods, errors) |
| `src/pybend/core/tests/integration/test_mcp.py` | W1 | MCP adapter integration tests |
| `src/pybend/core/tests/integration/test_federation.py` | W1 | Federation adapter integration tests |

---

## Appendix A: How ROADMAP-B Differs from ROADMAP-A

| Dimension | ROADMAP-A | ROADMAP-B |
|---|---|---|
| **Foundation** | Schema pipeline decomposition (refactor existing code) | Actor/Matrix/TX backend + schema pipeline built INTO actors |
| **Waves** | 4 waves (CT → Agents → Shared Infra → Demand-gated) | 5 waves (Actors+Schema → Agents+Federation → Infra Actors → Unification → Demand-gated) |
| **Actor system** | Wave 3 (separate from schema) | Wave 0 (combined with schema) |
| **Result type** | Separate `Ok[T]`/`Err[E]` class | TX `reply()`/`error()` pattern (built into message envelope) |
| **Events/hooks** | Separate system to build | Free — TX lifecycle messages on actors |
| **model_dump split** | Separate `model_dump_response()` method | TX message types (DUMP, DUMP_RESPONSE, DUMP_ACTIVITY) |
| **Schema extensions** | Pipeline stages on ProtoModel | `@schema_extension` on ProtoModel (served via ActorModel) |
| **Federation** | FederationAdapter Protocol + separate routes | NetworkAdapter on Matrix (same pattern as HTTP) |
| **MCP** | Separate `mcp.py` module | MCPAdapter NetworkAdapter on Matrix |
| **Key bet** | Schema composability enables everything | Actor unification enables everything |
| **Risk profile** | Lower risk (incremental refactors) | Higher risk (significant refactor) but higher leverage |

Both roadmaps converge on the same capabilities (MCP, federation, polymorphism, CLI, CT verification). They differ on the foundational architecture. ROADMAP-A treats the actor system as one of many capabilities. ROADMAP-B treats it as THE foundation that makes all other capabilities cheaper.

---

## Appendix B: Frontend Actor/Matrix/TX Reference

The Python backend actor system is modeled after the existing proven frontend implementation. Key reference files:

- **Actor.js** (`src/pybend/static/core/Actor.js`): Base class with `#addr`, `#parent`, `#children` private fields. `inbox()` receives TX messages. `send()` routes through parent. `static _send()` provides hierarchical routing — local children first, then bubble to root Matrix.

- **Matrix.js** (`src/pybend/static/core/Matrix.js`): Root actor singleton. `inbox()` routes by target address prefix — local children via `this.children.has(targetAddr)`, otherwise `this.remote.send(tx)` to NetworkAdapter. `connect()` handles actor-to-actor connection setup.

- **TX.js** (`src/pybend/static/core/TX.js`): Message envelope with `name`, `source`, `target`, `data`, `meta`, `tst` (timestamp), `hash` (content hash). Subclasses: ConnectEvent, ReadEvent, etc. `repr()` serializes to plain object. Event types defined in `config.E`: SCHEMA, READ, CREATE, UPDATE, DELETE, CONNECT, DESCRIBE, ERROR.

- **NetworkAdapter.js** (`src/pybend/static/core/transport/NetworkAdapter.js`): HTTP bridge. `send()` translates TX to HTTP request. `httpCallback()` wraps response in TX and dispatches back through Matrix. `onError()` creates ERROR TX. Supports HTTP and WebSocket modes.

The Python port follows the same patterns but adds:
- `asyncio` for non-blocking message handling (vs. synchronous JS)
- Correlation IDs on TX for request/response matching (vs. callback-based JS)
- Schema pipeline as actor behavior (unique to backend)
- `@schema_extension` registration (unique to backend)

---

*This roadmap is a living document. Each Wave's completion should trigger a review of the next Wave's priorities and triggers. The research that informed this roadmap lives in `.traces/research/`. ROADMAP-A provides an alternative approach that can be compared for risk/reward tradeoffs.*
