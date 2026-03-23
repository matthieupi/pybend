# N3TX Project Guide

## Philosophy

N3TX absorbs the data plumbing — storage, fetching, state, serialization — so developers focus on what makes their app unique. Define a model, get an API, a schema, a working UI.

**The model is the app.** A Python model definition is the single source of truth for the entire stack — data structure, validation, API endpoints, JSON Schema, access control, UI rendering. The framework derives everything else; if the schema can carry it, the developer shouldn't repeat it.

**Zero to working, then customize.** Everything works with no configuration. Customization is additive — override one piece without rebuilding the rest, at any level from auto-generated UI down to raw messages. The framework should never force a developer to understand the whole stack just to change one thing.

**Primitives, not opinions.** The framework provides composable building blocks — base classes, schema extensions, rendering utilities — not a rigid component library. Developers extend and compose; the framework owns the data lifecycle, developers own presentation and interaction.

**Backend is authoritative.** The backend defines models, schemas, access rules, relationships, and UI hints. The frontend reads these at runtime and adapts — deploying a new model or changing a field propagates to the UI automatically. The frontend never duplicates what the backend already knows.

**Transparent, not magical.** Nothing is hidden behind opaque abstractions. Actor messaging, schema resolution, DynamicClass creation — all inspectable, all overridable. The value is in not making you do it by hand, not in hiding it. A developer should trace any behavior from HTML tag to network request in under a minute.

**Modular where it simplifies, coupled where it must.** Real boundaries get enforced — the `authorize` package has zero N3TX imports, StorableMixin is injected not inherited, the Actor system knows nothing about HTML. But don't split genuinely single concerns for modularity's sake. The test: does this boundary make code easier to read, test, or replace one side? If it just adds a hop, keep it together.

---

## MANDATORY: Documentation-First Context Loading

Before starting ANY implementation task, you MUST follow this order:

### Step 1: Read the Documentation

Start with the **documentation files** to understand the system. These are the authoritative references:

**Cross-cutting docs** (`/workspace/docs/`):
- `ARCHITECTURE.md` — System architecture, data flow, design patterns
- `CORE.md` — Schema-driven development, model definitions, key patterns
- `ACTORS.md` — Actor system, TX messaging, Matrix routing
- `AGENTS.md` — LLM integration, tool discovery, AgentMixin/AgentActor
- `MODELS.md` — Model layer, pipelines, StorableMixin, BaseUser

**Per-package docs** (deep technical reference):
- `packages/n3tx-core/docs/` — app-bootstrap, authorization, schema-pipeline, storage
- `packages/n3tx-actors/docs/` — actor-messaging, actor-model, interceptors, network-adapters
- `packages/n3tx-agents/docs/` — mixin, agent-actor, tool-discovery
- `packages/n3tx-ui/docs/` — components, formidable, widgets

### Step 2: Read Domain-Specific Context

- **Backend work** (Python, models, storage, API, auth): Read `BACKEND.md` in this directory
- **Frontend work** (JS, Web Components, UI): Read `FRONTEND.md` in this directory
- **Full-stack work** (changes spanning both): Read BOTH files

### Step 3: Only Then Read Code

If the documentation does not fully answer your question, go to the source code. The docs should be sufficient for understanding architecture, patterns, and conventions. The code is for implementation details and edge cases.

This order is not optional. Do not begin writing code without first loading the relevant documentation and context files.

---

## Multi-Package Structure

N3TX is split into independently installable packages under `/workspace/packages/`:

```
packages/
├── n3tx-core/       # pip install n3tx-core   (models, storage, auth, API, JS runtime)
├── n3tx-actors/     # pip install n3tx-actors  (actor messaging, network adapters — backend only)
├── n3tx-ui/         # pip install n3tx-ui      (web components, widgets, themes — frontend only)
├── n3tx-agents/     # pip install n3tx-agents  (LLM reasoning, tool discovery)
└── n3tx/            # pip install n3tx         (meta-package — installs all four)
```

**Dependency graph** (acyclic):
```
n3tx-core              ← foundation, no N3TX deps
n3tx-actors            ← depends on n3tx-core
n3tx-ui                ← depends on n3tx-core
n3tx-agents            ← depends on n3tx-core + n3tx-actors
n3tx                   ← meta-package, depends on all four
```

**Import style** (new — clean break from old `n3tx.core.*` paths):
```python
# Core
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.base_user import BaseUser
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.authorize import ANYONE, OWNER, ROLE
from n3tx_core.utils.decorators import expose_route
from n3tx_core.app import create_app, N3TXApp

# Actors
from n3tx_actors import Actor, TX, Matrix, matrix, ActorProxy
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.api import NetworkAPI, NetworkWebSocket

# Agents
from n3tx_agents import AgentMixin, AgentActor, AgentDeps
from n3tx_agents.tools import discover_tools

# UI (Python side — just path helper)
from n3tx_ui import get_static_dir
```

---

## Development Workflow

### Before Making Changes

Before writing any code, review the area you are about to change. Understand the intent behind the existing implementation — why it was built this way, what patterns it follows, and how it fits into the larger system. Changes must be consistent with the architecture already in place. Do not work around the framework; work with it.

**Consistency is paramount.** N3TX's power comes from a small number of patterns applied uniformly across the entire stack. A single inconsistency — a hand-rolled route bypassing `register_routes()`, a frontend component fetching data outside the schema flow, a model that stores data differently from every other model — creates confusion, breaks assumptions, and compounds into real bugs over time. Every change should reinforce the existing architecture, not erode it. When in doubt, look at how the same thing is done elsewhere in the codebase and follow that pattern.

### Bug Fixes

**Test-Driven Bug Fixing (TDD).** Every bug fix MUST follow the red-green-refactor cycle:

1. **Red — Write a failing test first.** Before touching any production code, write a test that reproduces the reported bug. The test should fail for the same reason the bug manifests. This proves you understand the bug and gives you a clear signal when it's fixed. Place the test in the appropriate test directory (see [Tests](#tests) below).

2. **Green — Fix the bug.** Make the minimal change needed to turn the failing test green. Do not refactor, do not clean up, do not fix adjacent issues — just make the test pass.

3. **Refactor — Clean up if needed.** Once green, improve the fix if the code can be clearer or more consistent with surrounding patterns. The test ensures you don't regress.

If the bug cannot be reproduced with a test (e.g., environment-specific, timing-dependent), document why in a comment on the fix and describe the manual reproduction steps. But the default is always: **test first, fix second**.

Beyond standard analysis (reproduce, isolate, fix, verify), always ask **why** the bug exists. Most bugs are symptoms of deeper misalignment, not simple typos.

**Root cause categories:**

1. **Misunderstood architecture.** The change works in isolation but conflicts with the system's actual patterns. Fix: understand the correct pattern, rewrite to be consistent. If the same area keeps producing bugs, improve its documentation.

2. **Architecture gap.** The developer understood the system but found no clean way to achieve their goal, so they hacked around it. Fix: don't patch the hack — ask what the architecture should provide so this can be done cleanly, then make that deeper change.

3. **Violated expectations.** The code "works" (no crash) but produces silently wrong behavior — invisible at origin, visible only downstream where it looks like something else.

**Response framework:** Identify root cause → decide if the fix is a code correction, documentation improvement, or architectural enhancement. Never silence symptoms. For recurring bugs in the same area, the fix must also address the documentation or API surface — not just patch the instance.

## Architecture Overview

N3TX is a schema-driven framework where **model definitions are the single source of truth**. Models flow through: Model Definition → JSON Schema → API Routes → Frontend Rendering.

For full architecture details, read `/workspace/docs/ARCHITECTURE.md`.

### Three Levels of Bootstrapping

```python
# Level 1 — One-liner via create_app():
app = create_app(models=[Product, User], storage="sqlite:///app.db")

# Level 2 — Builder via N3TXApp:
pb = N3TXApp(storage="sqlite:///app.db")
pb.model(Product).model(User).join(Product, Comment)
app = pb.build()

# Level 3 — Raw primitives (full manual control):
register_model(Product, storage=storage_backend)
register_routes(registered_models)
```

Level 3 with `routing='actor'` wires `NetworkAPI` adapter + `auth_interceptor` on `request` + routes via `create_api_routes()`. All three levels produce identical API endpoints and responses.

### Backend (Python/FastAPI)

Models extend `ProtoModel` (or `ActorModel` for actor capabilities). `ProtoModel.schema()` orchestrates the schema pipeline, `model_response()` runs the dump pipeline. Models are registered via `register_model()` and routes auto-generated via `register_routes()`. See `BACKEND.md` for the full backend pipeline diagram and key files.

### Frontend (Vanilla JS Web Components)

The frontend bootstraps by fetching schema from the backend. `N3TX.SCHEMA()` creates DynamicClasses via `prototype()`, which are then rendered by Web Components (`ntx-list`, `ntx-item`, `ntx-method`, `ntx-stream`) with forms generated by `Formidable`. See `FRONTEND.md` for the frontend architecture diagram and key files.

### Data Flow: Request Lifecycle

1. Frontend `<ntx-list model="Product">` triggers schema fetch → `GET /Product`
2. Backend returns JSON Schema with `$schema`, `$id`, `properties`, `$defs`, `methods`
3. Frontend creates DynamicClass from schema, registers nested `$defs` models
4. DynamicClass triggers `READ` → `GET /products?limit=20&offset=0` (paginated)
5. Backend returns `{data: [...], meta: {total, limit, offset, has_more}}` with `$schema`/`$id` on each item
6. Frontend creates instances, renders via `ntx-item` components with "Load More" button if `has_more`

## Schema-Driven Development

Write a Python model, get a working full-stack application. The model definition is the only thing a developer writes. Everything else — API, validation, storage, UI, permissions, navigation — is derived from the schema that model produces. Any project can be transformed into a full stack application by turning a few classes into models.

For full details, read `/workspace/docs/CORE.md`.

### Canonical Model Example

```python
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import ListRef
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE

class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __ui__ = {
        'field_order': ['name', 'price', 'description', 'comments'],
        'groups': {'main': ['name', 'description', 'price'], 'Social': ['comments']},
        'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
    }
    __access__ = {
        'read': ANYONE, 'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'), 'delete': ROLE('admin'),
    }

    name: str = Field(min_length=1, max_length=200,
                      json_schema_extra={'ui': {'placeholder': 'Product name...'}})
    price: float = Field(gt=0,
                         json_schema_extra={'ui': {'widget': 'currency'},
                                            'access': {'view': 'anyone', 'edit': 'admin'}})
    description: str = Field(default='',
                             json_schema_extra={'ui': {'widget': 'textarea'}})
    comments: ListRef[Comment] = Field(default=[])

    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment) -> str: ...
```

### What Gets Generated (zero code required)

| Concern | Generated from | Where it happens |
|---------|---------------|-----------------|
| CRUD API endpoints | `__tablename__`, model fields | `register_routes()` in `routes_fastapi.py` |
| JSON Schema | Field types, validators, `json_schema_extra` | `ProtoModel.schema()` via `proto_schema` pipeline |
| Enriched JSON responses | `model_response()`, dump pipeline stages | `proto_dump` pipeline (`base` → `response` → extensions) |
| DB table + migrations | `__storable__`, field annotations | `StorableMixin` injection, `sqlite_migration.py` |
| JSON field storage | `dict`, `list`, `List[str]` etc. fields | `sqlite_storage.py` auto-serializes to/from JSON TEXT |
| FK hydration (href arrays) | `ListRef[T]` fields, `__fk_models__` | `sqlite_storage.py` on read |
| Access control | `__access__`, `@expose_route(access=...)` | `routes_fastapi.py` auth injection |
| Frontend entity classes | Schema properties, methods | `N3TX.SCHEMA()` → `prototype()` → DynamicClass |
| Form rendering | `properties`, `ui.widget`, `ui.placeholder` | `Formidable.getForm()` reads schema |
| Field order + grouping | `ui.field_order`, `ui.groups` | `form.js` renders fieldsets |
| Show/hide fields | `ui.display`, field-level `access` | `form.js` + `Permissions.js` |
| Protected fields | `__protected_fields__` | Route layer auto-injects on create, strips on update; `form.js` hides in edit mode |
| Edit/Delete button visibility | `access.update`/`access.delete` + OWNER check | `ntx-item.js` checks permissions |
| Pagination (list endpoints) | `?limit=N&offset=M` query params | `sqlite_storage.py` COUNT + LIMIT/OFFSET |
| Authenticated user injection | `user: User` param on `@expose_route` methods | `_resolve_user()` in `routes_fastapi.py` |
| Method buttons | `schema.methods` | `<ntx-method>` reads method signatures |
| Streaming SSE endpoints | `@expose_route(stream=True)` + async generator | `routes_fastapi.py` / `network_api.py` SSE handler |
| Streaming UI component | `schema.methods[m].stream` flag | `<ntx-stream>` reads method schema, renders progressive output |
| Stream event schemas | `@expose_route(events={...})` | `proto_model.py` serializes event ProtoModels into `methods[m].events` |
| Stream event dispatch | `NTTStreamAgent` + UPPERCASE handlers | `NTTStreamAgent` (extends `NTTStream`) dispatches to `this.TEXT()` etc. |

### Schema as Universal Contract

The JSON Schema returned by `GET /{ClassName}` is the **single contract between backend and frontend**. It carries the complete specification of how an entity behaves, renders, and is controlled — not just type descriptions. See `FRONTEND.md` for the full schema anatomy and consumption mapping.

## Key Files by Package

### n3tx-core — Framework Foundation
| File | Purpose |
|------|---------|
| `packages/n3tx-core/src/n3tx_core/app.py` | `N3TXApp` builder + `create_app()` factory |
| `packages/n3tx-core/src/n3tx_core/config.py` | HOST, PORT, API_URL, SQLITE_DB_FILE, AGENT_DEFAULTS |
| `packages/n3tx-core/src/n3tx_core/models/proto_model.py` | Base model, `schema()`, `model_response()`, `generate_join_model()`, `register_mixin()` |
| `packages/n3tx-core/src/n3tx_core/models/proto_schema.py` | Schema pipeline: 7 core stages + external extensions |
| `packages/n3tx-core/src/n3tx_core/models/proto_dump.py` | Dump pipeline for serialization |
| `packages/n3tx-core/src/n3tx_core/models/base_user.py` | Abstract base user with login/register |
| `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py` | CRUD operations, pagination |
| `packages/n3tx-core/src/n3tx_core/models/ref.py` | `ListRef[T]` type |
| `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` | SQLite backend, FK hydration, JSON fields |
| `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py` | Auto-migration + manual migrations |
| `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` | Level 1/2 route generation |
| `packages/n3tx-core/src/n3tx_core/api/backend.py` | FastAPIBackend, static file serving |
| `packages/n3tx-core/src/n3tx_core/authorize/` | Standalone ABAC auth (zero N3TX imports) |
| `packages/n3tx-core/src/n3tx_core/utils/descriptors.py` | `fullmethod`/`fullproperty` descriptors |
| `packages/n3tx-core/src/n3tx_core/utils/decorators.py` | `@expose_route`, `@schema_extension` |
| `packages/n3tx-core/src/n3tx_core/utils/registrar.py` | `register_model()`, `registered_models` |
| `packages/n3tx-core/src/n3tx_core/widgets/` | Widget base class + schema pipeline stage |

### n3tx-actors — Actor Messaging (Backend Only)
| File | Purpose |
|------|---------|
| `packages/n3tx-actors/src/n3tx_actors/actor.py` | Actor base class, `ActorMeta` metaclass |
| `packages/n3tx-actors/src/n3tx_actors/matrix.py` | Root actor, message router, module-level `matrix` |
| `packages/n3tx-actors/src/n3tx_actors/tx.py` | TX message envelope (dataclass) |
| `packages/n3tx-actors/src/n3tx_actors/actor_proxy.py` | ActorProxy wrapper (actor interface without MI) |
| `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py` | `ActorModel(Actor, ProtoModel)` bridge |
| `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py` | Base adapter: `request()`, `stream()`, correlation |
| `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` | HTTP REST bridge (Level 3 routing) |
| `packages/n3tx-actors/src/n3tx_actors/api/network_ws.py` | WebSocket bridge |
| `packages/n3tx-actors/src/n3tx_actors/api/network_mcp.py` | MCP JSON-RPC 2.0 bridge |
| `packages/n3tx-actors/src/n3tx_actors/api/network_ap.py` | ActivityPub federation bridge |
| `packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py` | Tier 1 auth gate |

### n3tx-agents — LLM Reasoning
| File | Purpose |
|------|---------|
| `packages/n3tx-agents/src/n3tx_agents/mixin.py` | AgentMixin: `ctx()`, `tools()`, `agentic()`, `run()`, streaming variants |
| `packages/n3tx-agents/src/n3tx_agents/actor.py` | AgentActor + stream event models (TextChunk, ToolCallEvent, etc.) |
| `packages/n3tx-agents/src/n3tx_agents/deps.py` | AgentDeps dataclass for Pydantic AI |
| `packages/n3tx-agents/src/n3tx_agents/tools.py` | Tool discovery + function generation |
| `packages/n3tx-agents/src/n3tx_agents/schema_ext.py` | Schema pipeline extension for `__agent__` models |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` | `NTTStreamAgent`: rich agent output (entries, markdown, tool cards) |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` | `<ntx-agent-live>` — real-time agent activity view (extends NTTStream) |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js` | `<ntx-chat>` — agent chat panel (extends NTTStream) |

### n3tx-ui — Visual Components (Frontend Only)
| File | Purpose |
|------|---------|
| `packages/n3tx-ui/src/n3tx_ui/mixin.py` | `ViewableMixin` + `viewable` schema stage; registers via `register_mixin()` |
| `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js` | Abstract single-entity base |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js` | Abstract collection base |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` | Single entity renderer |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js` | Collection grid |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js` | Streaming method output |
| `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js` | Formidable: schema-driven forms |
| `packages/n3tx-ui/src/n3tx_ui/static/widgets/` | JS widget registry + built-in widgets |

### Frontend JS Runtime (in n3tx-core — non-visual)
| File | Purpose |
|------|---------|
| `packages/n3tx-core/src/n3tx_core/static/core/NTT.js` | Entity registry, DynamicClass creation |
| `packages/n3tx-core/src/n3tx_core/static/core/Actor.js` | Base actor class (messaging) |
| `packages/n3tx-core/src/n3tx_core/static/core/TX.js` | Message envelope |
| `packages/n3tx-core/src/n3tx_core/static/core/Matrix.js` | Root actor + singleton |
| `packages/n3tx-core/src/n3tx_core/static/core/Component.js` | Abstract HTMLElement + Actor bridge |
| `packages/n3tx-core/src/n3tx_core/static/core/Router.js` | Client-side navigation |
| `packages/n3tx-core/src/n3tx_core/static/core/transport/` | HTTP, Socket, NetworkAdapter |

## Documentation Hierarchy

Documentation lives at three levels:

```
/workspace/docs/                           # Cross-cutting: architecture, getting started, API reference
/workspace/packages/<pkg>/docs/            # Per-package: deep technical reference for that subsystem
/workspace/CLAUDE.md + BACKEND.md + FRONTEND.md  # Agent context files (this file + supplements)
```

The `docs/` directory is for **human and agent consumption** — authoritative reference. The per-package `docs/` directories are for **deep dives** into specific subsystems. The CLAUDE/BACKEND/FRONTEND files are **agent-specific** context for LLM assistants working on the codebase.

`.traces/` contains development artifacts written by and for agents — research, plans, vision docs, audit reports.

## Example Applications

| Directory | Level | What it demonstrates |
|-----------|-------|---------------------|
| `examples/core/` | Level 1/2 | Direct routes, `create_app()`, ProtoModel |
| `examples/actors/` | Level 3 | Actor routing, `routing='actor'`, ActorModel |
| `examples/chat/` | Streaming | Streaming endpoints |
| `examples/grants/` | Agents | `__agent__ = True`, agent CRUD, tool discovery |

## Cross-Cutting Patterns

### Custom Methods
```python
@expose_route('/like', methods=['POST'], access=AUTHENTICATED)
def like(self) -> str:
    ...
```
Appears in schema under `methods`, frontend renders via `<ntx-method>` (or `<ntx-stream>` for streaming methods). The `access=` parameter controls authorization. The `stream=True` parameter marks the method as streaming.

### Streaming Methods
Custom methods can stream progressive results via SSE or WebSocket:

```python
@expose_route('/generate', methods=['POST'], stream=True, access=AUTHENTICATED)
async def generate(self):
    for i in range(5):
        await asyncio.sleep(0.1)
        yield {'chunk': f'Part {i}'}
```

SSE wire format: `event: chunk|done|error`, `data: {json}`. Stream protocol uses `meta: {req, stream: true, seq: N}` for chunk correlation and `meta: {stream_end: true}` for termination.

#### Schema-Declared Stream Events

Streaming methods can declare their event vocabulary with `events=` on `@expose_route`. Event types are non-storable `ProtoModel` subclasses:

```python
class TextChunk(ProtoModel):
    text: str = Field(default='')

@expose_route('/stream', methods=['POST'], stream=True,
              events={'text': TextChunk, 'done': DoneChunk})
async def stream_method(self, task: str):
    yield {'name': 'text', 'data': {'text': 'hello'}}
```

Events appear in schema as `methods[m].events` with full JSON Schema per event type. See `docs/AGENTS.md` → Streaming for the complete pattern.

#### Frontend NTTStreamAgent

`NTTStreamAgent` (`n3tx-agents/static/components/ntx-stream-agent.js`) extends `NTTStream` with rich agent output rendering — typed entries (thinking, tool calls, text), markdown rendering, and tool result cards. Components that need agent-style streaming extend `NTTStreamAgent` and override UPPERCASE handlers:

```javascript
class MyComponent extends NTTStreamAgent {
    TEXT(data, meta)  { /* data.text */ }
    DONE(data, meta)  { /* data.answer */ }
    STREAM_END(data)  { /* cleanup */ }
}
```

For simpler progressive output (plain chunks), extend `NTTStream` directly.

**Component hierarchy**: `Component → NTTMethod → NTTStream → NTTStreamAgent → (app subclasses)`

**prerender()/render() lifecycle**: `prerender()` is called from `connectedCallback()` before schema loads — use it for structural DOM. `render()` is the schema-aware pass — it is additive and should never wipe `prerender()` output.

**UPPERCASE convention**: TX inbox handlers are always UPPERCASE. This mirrors the backend actor handler pattern.

### Authenticated User Injection
Custom methods receive the authenticated user by declaring a `user` parameter:
```python
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment, user: User = None) -> str:
    comment.user_owner = user.id if user else 1
    ...
```
The route layer's `_resolve_user()` resolves the type hint from the JWT token. The `user` param is never read from the request body.

### Actor System
For full details, read `/workspace/docs/ACTORS.md` and `packages/n3tx-actors/docs/`.

**`fullmethod`/`fullproperty` descriptors** (in `n3tx_core/utils/descriptors.py`): Generic descriptors for unified class/instance dispatch. Used by both actors and agents.

**Actor base class** extends PydanticBaseModel via `ActorMeta` metaclass. `send()` three-case routing, `use()` interceptors, class + instance state.

**TX** is a dataclass message envelope: `reply()`, `error()`, `is_error`, `stream_chunk()`, `stream_end()`.

**Matrix** extends Actor: root actor, `has()`, adapter delegation, module-level `matrix` singleton.

**ActorProxy** wraps any class as a routable actor without MI.

### ActorModel Pattern
```python
from n3tx_actors.models.actor_model import ActorModel

class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    ...
```
One import change from ProtoModel. `ActorModel(Actor, ProtoModel)` is the bridge class. CRUD via `handler_crud()`, lifecycle events, generic handler fallback.

### AgentMixin — Self-Aware Models
For full details, read `/workspace/docs/AGENTS.md` and `packages/n3tx-agents/docs/`.

`__agent__ = True` gives a model LLM-powered reasoning. Six `@fullmethod` methods: `ctx()`, `tools()`, `agentic()`, `run()`, `agentic_stream()`, `run_stream()`.

**Config cascade** (3-tier): `config.AGENT_DEFAULTS` < `__agent__` dict < `agentic()` kwargs.

**AgentMixin vs AgentActor**: AgentMixin derives config from model definition; AgentActor stores config in DB fields.

**Import ordering**: `n3tx_agents` (or `import n3tx_agents`) must be imported **before** any model with `__agent__ = True` is defined. `n3tx_agents.__init__` calls `register_mixin('__agent__', AgentMixin)` which populates `proto_model._mixin_registry`. If a model is defined before this call, the mixin is silently not injected.

### Three Levels of N3TX
```python
# Level 1 — ProtoModel + direct routes (no actors)
app = create_app(models=[Product], storage="sqlite:///app.db")

# Level 2 — ActorModel + direct routes (actor capabilities, same HTTP layer)
app = create_app(models=[Product], storage="sqlite:///app.db")

# Level 3 — ActorModel + NetworkAPI (full actor routing)
app = create_app(models=[Product], storage="sqlite:///app.db", routing='actor')
```

### Two-Tier Auth (Level 3)
- **Tier 1**: `auth_interceptor` on `NetworkAPI.request()` — fast gate at protocol boundary
- **Tier 2**: `ActorModel._authorize()` in `handler_crud()` — full ABAC with resource instance

Level 1/2 use `routes_fastapi.py`'s single-pass authorization.

### JSON Fields (dict/list Storage)
`dict` and `list` fields are transparently serialized to JSON TEXT in SQLite. See `packages/n3tx-core/docs/storage.md` for details.

### Widget Pattern
Widget fields map Python types to specialized frontend renderers. See `BACKEND.md` for Python details, `FRONTEND.md` for JS details, `packages/n3tx-ui/docs/widgets.md` for the full widget system.

## Directives

### Documentation Updates
After completing any set of implementation tasks, ALWAYS update the relevant documentation:
1. **Per-package docs** (`packages/<pkg>/docs/`): Update if subsystem behavior changed
2. **Cross-cutting docs** (`docs/`): Update architecture/API docs if needed
3. **This file** (`CLAUDE.md`): Update if architectural patterns or key file locations change. Also update `BACKEND.md` or `FRONTEND.md` as appropriate.

### Working Directory
For **example apps**, run from the example directory (e.g., `examples/core/`).
For **framework code**, the relevant package directory under `packages/`.

### Tests
| Test suite | Command | What it covers |
|-----------|---------|---------------|
| Core unit tests | `cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/` | Models, storage, auth, routes, schema |
| Actor tests | `cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/` | Actor system, interceptors, auth |
| Agent tests | `cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/` | AgentMixin, AgentActor, tools |
| Core example (Level 1/2) | `cd /workspace && python3 -m pytest examples/core/tests/` | CRUD, auth flow, pagination, FK hydration |
| Actors example (Level 3) | `cd /workspace && python3 -m pytest examples/actors/tests/` | Same coverage with actor routing |
| Grants example (Agents) | `cd /workspace && python3 -m pytest examples/grants/tests/` | Agents, grants, sources |

### Starting a Server
```bash
cd /workspace/examples/core && python3 main.py     # Level 1/2
cd /workspace/examples/actors && python3 main.py   # Level 3
cd /workspace/examples/grants && python3 main.py   # Agents
```

### Commit Messages
Format: `type(scope): Description [wave]`

- **type**: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
- **scope** (optional): `core`, `actors`, `agents`, `ui`, `api`, `frontend`, `example`
- **Description**: imperative mood, capitalized
- **[wave]**: current development wave in brackets. Check recent commits for the active wave.

Examples:
```
feat(actors): Add interceptor mechanism and two-tier auth [0.10]
fix(core): Move FastAPI imports to module level in network_api.py [0.10]
docs: Update CLAUDE.md for multi-package structure [0.10]
```

### Authentication for Testing
Most endpoints require a JWT token. Schema endpoints (`GET /{ClassName}`) are public.

**Seed users** (created by `cd examples/core && python3 seed.py`):
| Email | Password | Role |
|---|---|---|
| `alice@example.com` | `alice123` | `user` |
| `bob@example.com` | `bob123` | `user` |
| `charlie@example.com` | `charlie123` | `user` |

**Get a token:**
```bash
TOKEN=$(curl -s -X POST http://localhost:5000/users/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"alice123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
```

**Use it:**
```bash
curl -s http://localhost:5000/products -H "x-access-token: $TOKEN"
curl -s http://localhost:5000/Product  # Schema (no auth needed)
```
