# PyBend Project Guide

## Philosophy

PyBend absorbs the data plumbing — storage, fetching, state,
serialization — so developers focus on what makes their app unique.
Define a model, get an API, a schema, a working UI. The things that
Redux, GraphQL, fetch(), and most of React solve become non-problems.

### Core Principles

**The model is the app.** A Python model definition is the single
source of truth for the entire stack: data structure, validation, API
endpoints, JSON Schema, access control, UI rendering. Write the model;
the framework derives everything else. If the schema can carry it, the
developer shouldn't have to repeat it.

**Zero to working, then customize.** Everything works out of the box
with no configuration. Customization is additive — override one piece
without rebuilding the rest. Use the auto-generated UI as-is, or
override `render()`, or drop to raw messages. Each level down gives
more control without losing what the levels above provided. The
framework should never force a developer to understand the whole stack
just to change one thing.

**Primitives, not opinions.** The framework provides composable
building blocks — base classes, schema extensions, rendering
utilities — not a rigid component library. Developers extend and
compose. The framework owns the data lifecycle; developers own
presentation and interaction. Think LitElement's approach to Web
Components: powerful base, zero dictation.

**Backend is authoritative.** The backend defines models, schemas,
access rules, relationships, and UI hints. The frontend reads these at
runtime and adapts. Deploying a new model or changing a field
propagates to the UI automatically. The frontend never duplicates what
the backend already knows.

**Transparent, not magical.** Nothing is hidden behind abstractions
you can't see through. Actor messaging, schema resolution, DynamicClass
creation — all inspectable, all overridable. The value is not in hiding
complexity but in not making you do it by hand. A developer should be
able to trace any behavior from the HTML tag to the network request in
under a minute.

**Modular where it simplifies, coupled where it must.** Architectural
parts that can stand alone should stand alone. The `authorize` package
has zero PyBend imports — it works as a generic ABAC library and
happens to plug into PyBend. StorableMixin is injected, not inherited.
The Actor system knows nothing about HTML. When a boundary is real
(auth doesn't need to know about storage, messaging doesn't need to
know about DOM), enforce it — separate packages, no cross-imports,
clean interfaces. But don't split things that are genuinely one concern
into two packages for the sake of modularity. A class with one consumer
doesn't need its own file. An abstraction layer that just passes
through adds indirection without value. The test: does this boundary
make the code easier to read, easier to test, or easier to replace one
side without touching the other? If yes, decouple. If it just adds a
hop, keep it together.

## Development Workflow

### Before Making Changes

Before writing any code, review the area you are about to change.
Understand the intent behind the existing implementation — why it was
built this way, what patterns it follows, and how it fits into the
larger system. Changes must be consistent with the architecture already
in place. Do not work around the framework; work with it.

**Consistency is paramount.** PyBend's power comes from a small number
of patterns applied uniformly across the entire stack. A single
inconsistency — a hand-rolled route bypassing `register_routes()`, a
frontend component fetching data outside the schema flow, a model that
stores data differently from every other model — creates confusion,
breaks assumptions, and compounds into real bugs over time. Every
change should reinforce the existing architecture, not erode it. When
in doubt, look at how the same thing is done elsewhere in the codebase
and follow that pattern.

### Bug Fixes

Standard bug fix procedure applies: reproduce, isolate, fix, verify.
But before jumping to a fix, ask **why** the bug exists in the first
place.

Most bugs introduced by developers are not simple typos — they are
symptoms of a deeper misalignment. There are typically two root causes:

1. **The developer didn't understand the architecture.** They built
   something that works in isolation but conflicts with how the system
   actually operates. The fix here is not just patching the symptom —
   it's understanding the correct pattern and rewriting the change to
   be consistent with the architecture. If this keeps happening in the
   same area, the documentation needs to be improved so the intent is
   clearer.

2. **The architecture doesn't support what they're trying to do.** The
   developer understood the system but found no clean way to achieve
   their goal, so they hacked around it. The fix here is not to patch
   the hack — it's to step back and ask: what should the architecture
   provide so this can be done simply, elegantly, while preserving the 
   intent of the architecture and keeping it consistent? Then make that deeper 
   change.

3. **The system violates reasonable expectations.** The code does what
   the developer wrote, but what they wrote violates what any
   reasonable consumer — human or machine — would expect. The system
   "works" in the narrow sense (no crash, no exception) but produces
   behavior that is silently wrong, making the bug invisible at the
   point of origin and visible only downstream, where it looks like
   something else entirely.

   **Case study: the 200-OK error.** Custom model methods like
   `Product.favorite()` returned `'{"error": "authentication
   required"}'` as a plain string with HTTP 200. The backend logged
   "200 OK", the frontend received a successful response, the
   `_response_` handler called `pull()` to refresh the entity — and
   everything appeared to work. But the like was never created. The
   user saw no error, the count didn't change, and the favorite didn't
   appear on the favorites page. Debugging started at the UI (wrong
   count), moved to the network layer (response looks fine), then to
   the database (no record) — a three-layer wild goose chase caused by
   a single violation: **an error was returned as a success**.

   The root cause was not a typo or a misunderstanding. It was a
   missing contract: the framework had no mechanism for model methods
   to signal errors with proper HTTP semantics, so the developer did
   the only thing available — returned an error string. The fix was
   two-fold: (a) provide `MethodError`, a framework-level exception
   that model methods can raise and the route layer catches and
   converts to a proper HTTP error response, and (b) add frontend
   toast notifications that surface errors visually, including
   defensive detection of `{"error": ...}` in 200 bodies.

   **The pattern to watch for:** any place where a failure is encoded
   inside a success channel. Common forms: returning error dicts from
   functions that normally return data, logging errors but continuing
   as if nothing happened, swallowing exceptions and returning
   defaults. The test: if a consumer ignores the content and only
   checks the status/type, would they correctly know something went
   wrong? If not, the contract is broken regardless of whether the
   code "works."

In all three cases, the response to a bug is: first identify its root
cause, then decide whether the fix is a code correction, a
documentation improvement, or an architectural enhancement. Never just
silence the symptom.

## Architecture Overview

PyBend is a schema-driven framework where **model definitions are the single source of truth**. Models flow through: Model Definition -> JSON Schema -> API Routes -> Frontend Rendering.

### Backend (Python/FastAPI)

Three levels of bootstrapping (pick one):

```
# Level 1 — One-liner via create_app():
app = create_app(models=[Product, User], storage="sqlite:///app.db")

# Level 2 — Builder via PyBendApp:
pb = PyBendApp(storage="sqlite:///app.db")
pb.model(Product).model(User).join(Product, Comment)
app = pb.build()

# Level 3 — Raw primitives (full manual control, existing main.py pattern):
register_model(Product, storage=storage_backend)
register_routes(registered_models)
```

Regardless of which level, the underlying flow is:

```
models/*.py          Define data models (extend ProtoModel / BaseUser / ActorModel)
     |
     v
ProtoModel           Base class: injects StorableMixin, rewrites FK fields,
                      orchestrates schema pipeline, handles serialization
     |
     +-- schema()              Orchestrates proto_schema.* pipeline (base → strip_hidden →
     |                         methods → defs → access → ui → metadata)
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

Actor/Matrix/TX      Backend actor system (mirrors frontend pattern):
                      Actor — base class with addr, children, inbox, handler, send
                      Matrix — root actor and message router (singleton per tree)
                      TX — message envelope (name, source, target, data, meta)

Interceptors         use() on any Actor — register TX interceptors on inbox/send/request
                      Signature: async (TX) -> TX. Return error TX to short-circuit.
                      Per-actor, not global. Class + instance chains combine.

NetworkAPI           Level 3: HTTP → TX → Matrix → ActorModel (full actor routing)
(routing='actor')    create_app(routing='actor') wires NetworkAPI + auth interceptor
                      Two-tier auth: Tier 1 (boundary gate) + Tier 2 (handler OWNER check)
```

### Frontend (Vanilla JS Web Components)

```
NTT.js               Core entity system. Bootstraps by fetching schema from backend.
  |
  +-- SCHEMA()        Receives schema, creates DynamicClass via prototype()
  +-- prototype()     Builds class with typed properties, methods, value getter
  |                   Value getter injects $schema (schema URL) and $id (instance URL)
  |
  v
ntt-list.js          <ntt-list model="Product"> - fetches and renders entity list
ntt-item.js          <ntt-item> - adaptive entity rendering (xs pill → xl page)
ntt-element.js       Base web component class for all NTT elements
ntt-method.js        Renders callable methods as buttons
form.js              Formidable generator - builds forms from schema properties
```

### Data Flow: Request Lifecycle

1. Frontend `<ntt-list model="Product">` triggers schema fetch -> `GET /Product`
2. Backend returns JSON Schema with `$schema`, `$id`, `properties`, `$defs`, `methods`
3. Frontend creates DynamicClass from schema, registers nested `$defs` models
4. DynamicClass triggers `READ` -> `GET /products?limit=20&offset=0` (paginated)
5. Backend returns `{data: [...], meta: {total, limit, offset, has_more}}` with `$schema`/`$id` on each item
6. Frontend creates instances, renders via `ntt-item` components with "Load More" button if `has_more`

## Schema-Driven Development

PyBend's core idea: **write a Python model, get a working full-stack application**. The model definition is the only thing a developer writes. Everything else — API, validation, storage, UI, permissions, navigation — is derived from the schema that model produces.
This also means that any project can be transformed into aa full stack 
application, just by turning a few classes into models!

### What a model definition carries

A single model class encodes the entire application concern:

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __ui__ = {
        'field_order': ['name', 'price', 'description', 'comments'],
        'groups': {'main': ['name', 'description', 'price'], 'Social': ['comments']},
        'renderer': {'item': 'ntt-item', 'list': 'ntt-list'},
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

From this definition, `ProtoModel.schema()` generates a JSON Schema document that carries **everything the frontend needs** — no separate API documentation, no frontend config files, no component wiring.

### What gets generated (zero code required)

| Concern | Generated from | Where it happens |
|---------|---------------|-----------------|
| CRUD API endpoints | `__tablename__`, model fields | `register_routes()` in `routes_fastapi.py` |
| JSON Schema | Field types, validators, `json_schema_extra` | `ProtoModel.schema()` via `proto_schema` pipeline |
| Enriched JSON responses | `model_response()`, dump pipeline stages | `proto_dump` pipeline (`base` → `response` → extensions) |
| DB table + migrations | `__storable__`, field annotations | `StorableMixin` injection, `sqlite_migration.py` |
| FK hydration (href arrays) | `ListRef[T]` fields, `__fk_models__` | `sqlite_storage.py` on read |
| Access control | `__access__`, `@expose_route(access=...)` | `routes_fastapi.py` auth injection |
| Frontend entity classes | Schema properties, methods | `NTT.SCHEMA()` → `prototype()` → DynamicClass |
| Form rendering | `properties`, `ui.widget`, `ui.placeholder` | `Formidable.getForm()` reads schema |
| Field order + grouping | `ui.field_order`, `ui.groups` | `form.js` renders fieldsets |
| Show/hide fields | `ui.display`, field-level `access` | `form.js` + `Permissions.js` |
| Protected fields | `__protected_fields__` | Route layer auto-injects on create, strips on update; `form.js` hides in edit mode |
| Edit button visibility | `access.update` + resource OWNER check | `ntt-item.js` checks `permissions.canAction(access, 'update', value)` |
| Delete button visibility | `access.delete` + resource OWNER check | `ntt-item.js` checks `permissions.canAction(access, 'delete', value)` |
| $defs access rules | Referenced model `__access__` | `proto_schema.access()` injects into `$defs` entries |
| Pagination (list endpoints) | `?limit=N&offset=M` query params | `sqlite_storage.py` COUNT + LIMIT/OFFSET |
| Authenticated user injection | `user: User` param on `@expose_route` methods | `_resolve_user()` in `routes_fastapi.py` |
| Method buttons | `schema.methods` | `<ntt-method>` reads method signatures |
| Component tag resolution | `ui.renderer.item`, `ui.renderer.detail` | `ntt-router.js` resolves tags for navigation |
| Adaptive display sizes | Schema properties, field order | `ntt-item.js` size methods (xs/sm/md/lg/xl) |

### The development workflow

1. Define or modify a Python model
2. Restart the server — `ProtoModel.schema()` generates the updated JSON Schema, `register_routes()` creates endpoints, migrations run
3. Open `http://localhost:5000/` — the frontend fetches the schema, creates DynamicClasses, renders everything
4. No frontend code changed. No routes added. No forms built. No permissions wired.

To customize, override at any level: swap a widget via `json_schema_extra`, control layout via `__ui__`, change permissions via `__access__`, or write a custom component that extends `NTTElement`.

---

## Schema as Universal Contract

The JSON Schema returned by `GET /{ClassName}` is the **single contract between backend and frontend**. It is not just a type description — it is the complete specification of how an entity behaves, renders, and is controlled.

### Schema anatomy

```
GET /Product → JSON Schema
├── $schema         → "http://localhost:5000/Schema"          (meta-schema URL)
├── $id             → "http://localhost:5000/Product"         (this schema's URL)
├── __name__        → "Product"                               (class name)
├── __tablename__   → "products"                              (API collection path)
├── properties      → { name: {type, minLength, ui, ...}, ...}  (field definitions)
│   └── each field carries:
│       ├── type, format, validation (Pydantic standard)
│       ├── ui.widget       → rendering hint (currency, textarea, ...)
│       ├── ui.placeholder  → input placeholder text
│       ├── ui.display      → false to hide from UI
│       ├── ui.protected    → true for backend-owned fields (hidden in edit forms)
│       └── access          → field-level permission rules
├── ui              → model-level UI configuration
│   ├── field_order → render fields in this sequence
│   ├── groups      → group fields into fieldsets
│   └── renderer    → { item: 'ntt-item', list: 'ntt-list', detail: '...' }
├── access          → model-level ABAC rules (serialized)
│   ├── create      → { rule: "authenticated" }
│   ├── read        → { rule: "anyone" }
│   ├── update      → { op: "or", rules: [{rule: "owner"}, {rule: "role", roles: ["admin"]}] }
│   └── delete      → { rule: "role", roles: ["admin"] }
├── methods         → callable endpoints
│   └── comment     → { route, methods, scope, parameters, returns, access }
├── $defs           → nested/related model schemas
│   └── Comment     → { $id, properties, methods, ui, access, ... }
└── required        → required field names
```

### How each schema section is consumed

**Frontend reads schema once, adapts everything at runtime:**

| Schema section | Frontend consumer | What it controls |
|---------------|------------------|-----------------|
| `properties` | `prototype()` in NTT.js | Creates typed getters/setters on DynamicClass |
| `properties[field].type` | `form.js` → `getInput()` | Chooses input type (text, number, checkbox, ...) |
| `properties[field].ui.widget` | `form.js` → `getInput()` | Specialized rendering (currency prefix, textarea) |
| `properties[field].ui.display` | `form.js` → field filtering | Hides internal fields (IDs, timestamps, FKs) |
| `properties[field].ui.protected` | `form.js` → field filtering | Hides backend-owned fields in edit mode (display-only) |
| `properties[field].ui.placeholder` | `form.js` → input attrs | Sets placeholder text on inputs |
| `properties[field].access` | `Permissions.js` → `canView()` | Field-level visibility per user role |
| `ui.field_order` | `form.js` → `getForm()` | Controls field rendering sequence |
| `ui.groups` | `form.js` → `renderGroupedFields()` | Wraps fields in `<fieldset>` groups |
| `ui.renderer.*` | `ntt-router.js` → `#resolveTag()` | Chooses component tag for navigation views |
| `access` | `Permissions.js` → `canAction(access, action, resource)` | Shows/hides edit/delete buttons with resource-aware OWNER evaluation |
| `methods` | `prototype()` + `<ntt-method>` | Creates callable methods + renders action buttons |
| `$defs` | `NTT.SCHEMA()` | Registers nested DynamicClasses (Comment, etc.) |
| `$id` / `$schema` | DynamicClass value getter | Injected into every entity instance for self-description |

### Schema propagation lifecycle

```
1. Model Definition (Python)
   Product(ProtoModel) with fields, __ui__, __access__, @expose_route
                    │
2. Schema Generation (Backend, on GET /Product)
   ProtoModel.schema() → proto_schema pipeline (base → strip_hidden → methods → defs → access → ui → metadata)
                    │
3. Network Transport
   HTTP GET /Product → JSON response
                    │
4. Schema Bootstrap (Frontend)
   NTT.SCHEMA(data) → prototype(addr, schema, href) → DynamicClass
   │  Creates typed class with getters, setters, methods from schema
   │  Registers nested $defs as additional DynamicClasses
                    │
5. Component Rendering (Frontend)
   NTTItem.DESCRIBE() receives { proto: schema, data: values }
   │  form.js reads schema.properties → builds form HTML
   │  Permissions.js reads schema.access → shows/hides controls
   │  ntt-method reads schema.methods → renders action buttons
   │  ntt-router reads schema.ui.renderer → resolves navigation targets
                    │
6. Entity Responses (Backend, on GET /products)
   model_response() runs dump pipeline → injects $schema + $id into each record
   │  Frontend DynamicClass value getter preserves these for self-description
   │  Any entity can be independently resolved: GET $id → full entity
   │  Collection fields return href arrays: ["http://.../products/1/comments/1", ...]
```

### Why this matters

**Adding a field** to a model automatically: adds a DB column, includes it in API responses, generates a form input, validates on both sides. **Changing `__access__`** propagates to the frontend: the edit button appears or disappears, list queries filter differently. **Adding `@expose_route`** creates an API endpoint and a clickable button in the UI. The schema carries intent, not just structure — the frontend doesn't interpret types, it follows instructions.

---

## Key Files by Area

### Models & Serialization
- `src/pybend/core/models/proto_model.py` - Base model, `model_response()`, `generate_join_model()`. Schema orchestrator (`schema()` calls `proto_schema.*` pipeline)
- `src/pybend/core/models/proto_schema.py` - Schema pipeline: 7 composable `dict → dict` stages (`base`, `strip_hidden`, `methods`, `defs`, `access`, `ui`, `metadata`). Extensible via `@schema_extension` decorator.
- `src/pybend/core/models/proto_dump.py` - Dump pipeline: composable `dict → dict` stages for model serialization (`base`, `response`). Extensible via `@dump_extension` decorator. Powers `model_response()`.
- `src/pybend/core/models/actor_model.py` - `ActorModel(Actor, ProtoModel)` bridge class. CRUD via `handler_crud()`, lifecycle event publishing, generic Actor handler fallback for custom methods.
- `src/pybend/core/models/base_user.py` - Abstract base user model with `login()` and `register_user()` endpoints and password hashing
- `src/pybend/core/models/storable_mixin.py` - CRUD operations (create/get/list/update/delete). `list()` supports `limit`/`offset` pagination.
- `src/pybend/core/models/ref.py` - `ListRef[T]` type for collection references
- `src/pybend/core/utils/typer.py` - `Ref` type (`Ref[T]`, `Ref['self']`), `flatten_refs()`

### Storage
- `src/pybend/core/storage/sqlite_storage.py` - SQLite backend with FK hydration (converts ListRef fields to href arrays)
- `src/pybend/core/storage/sqlite_migration.py` - Auto-migration + Rails-style manual migrations
- `src/pybend/core/storage/sqlite_helpers.py` - `get_parent_fk_columns()` for auto FK column detection

### Authorization & Authentication
- `src/pybend/core/authorize/` - Standalone auth package (JWT + ABAC, zero PyBend imports). Configured via `authorize.configure()` in `main.py`
- `src/pybend/core/authorize/auth.py` - JWT: password hashing, token create/decode, `configure()`
- `src/pybend/core/authorize/rules.py` - `AccessRule` base class + built-in rules (`ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`, `Where`)
- `src/pybend/core/authorize/context.py` - `AccessContext` dataclass (user, action, model, resource)
- `src/pybend/core/authorize/resolver.py` - `AuthorizationResolver` Protocol + `DefaultResolver`
- `src/pybend/core/authorize/errors.py` - `AccessDenied` exception
- `src/pybend/core/authorize/schema.py` - Serialize access rules to JSON for schema exposure
- `src/pybend/docs/AUTHORIZATION.md` - Full authorization system documentation

### Actor System (v0.8)
- `src/pybend/core/actors/actor.py` - Base actor class with unified class/instance dispatch via `actormethod`/`actorproperty` descriptors and `ActorMeta` metaclass. Addr, children, parent, inbox, handler, send, register, spawn, `use()` interceptors. Auto-registers with Matrix via metaclass.
- `src/pybend/core/actors/matrix.py` - Root actor and message router. `has()`, self-send guard, adapter delegation, interceptor support. Module-level `matrix` instance created at import.
- `src/pybend/core/actors/tx.py` - TX message envelope (dataclass): name, source, target, data, meta, timestamp, uuid. `reply()` swaps source/target with new uuid. `error()` creates ERROR TX. `is_error` property.
- `src/pybend/core/actors/actor_proxy.py` - `ActorProxy` wrapper: gives any class or instance the actor interface (inbox/handler/send/register/spawn) without inheritance. Used when full Actor MI is not desired.
- `src/pybend/core/actors/__init__.py` - Re-exports `TX`, `Actor`, `Matrix`, `matrix`

### API / Routes
- `src/pybend/core/api/routes_fastapi.py` - Level 1/2 route factories with authorization injection, pagination, and user resolution bridge (`_resolve_user`). DO NOT MODIFY — Level 3 is additive.
- `src/pybend/core/api/network_adapter.py` - `NetworkAdapter(Actor)` base class for protocol adapters. Provides `request()` for request/response correlation via asyncio.Future with interceptor support, `inbox()` override for correlation interception. All external protocol interaction flows through a NetworkAdapter.
- `src/pybend/core/api/network_api.py` - `NetworkAPI` adapter: HTTP REST bridge for Level 3 actor routing. `create_api_routes()` generates FastAPI routes that translate HTTP to TX. Mirrors route paths from `routes_fastapi.py`.
- `src/pybend/core/api/auth_interceptor.py` - Tier 1 auth interceptor for NetworkAPI. `async (TX) -> TX` function: AUTHENTICATED gate, sql_filter for list, full create check, identity gate for read/update/delete. Registered via `api.use(auth_interceptor, on='request')`.
- `src/pybend/core/api/network_mcp.py` - `NetworkMCP` adapter: MCP JSON-RPC 2.0 bridge. `handle_tools_list()`, `handle_tools_call()`, `handle_jsonrpc()`. Converts model schemas to MCP tool specs. `create_mcp_routes()` FastAPI route factory.
- `src/pybend/core/api/network_ap.py` - `NetworkAP` adapter: ActivityPub federation bridge. LIFECYCLE handler, actor documents, outbox, inbox, WebFinger, follow/unfollow. `create_federation_routes()` FastAPI route factory.
- `src/pybend/core/api/network_ws.py` - `NetworkWebSocket` adapter: WebSocket bridge for frontend Matrix. Translates frontend TX (full URL targets, UPPERCASE names) to backend TX. Lifecycle event broadcast. `create_ws_routes()` FastAPI route factory.
- `src/pybend/core/utils/decorators.py` - `@expose_route()` for custom method endpoints (supports `access=` parameter)
- `src/pybend/core/utils/registrar.py` - `registered_models` dict, `join_models` dict

### Frontend (NTT)
- `src/pybend/static/core/NTT.js` - Core: NTT class, prototype() factory, SCHEMA handler, DynamicClass creation
- `src/pybend/static/core/Matrix.js` - Message bus / actor system
- `src/pybend/static/core/Actor.js` - Base actor class
- `src/pybend/static/core/Router.js` - Navigation state Actor (hash sync, history stack, Observable)
- `src/pybend/static/components/ntt-item.js` - Item component: size methods (xs–xl), render dispatch, edit toggle, click-to-select
- `src/pybend/static/components/ntt-list.js` - List component
- `src/pybend/static/components/ntt-router.js` - Generic view container (loads any component via Router)
- `src/pybend/static/components/ntt-element.js` - Base component class
- `src/pybend/static/generators/form.js` - Formidable: schema-driven form generator
- `src/pybend/static/utils/Permissions.js` - Reads schema access rules for UI permission checks

### App Bootstrap
- `src/pybend/core/app.py` - `PyBendApp` builder class + `create_app()` one-liner factory. Supports `routing='direct'` (Level 1/2) and `routing='actor'` (Level 3 via NetworkAPI).
- `src/pybend/__init__.py` - Public API: re-exports `create_app`, `PyBendApp`, `ProtoModel`, `BaseUser`, `expose_route`, `Actor`, `Matrix`, `TX`, `NetworkAdapter`, `NetworkAPI`, etc.

### Config & Entry
- `src/pybend/core/config.py` - HOST, PORT, API_URL, SQLITE_DB_FILE
- `src/pybend/core/main.py` - Backward-compat shim that delegates to `pybend.example.main`

### Example Application
- `src/pybend/example/main.py` - Example app entry point using `create_app()`
- `src/pybend/example/models/` - Example models: `User`, `Product`, `Comment`, `Like`
- `src/pybend/example/seed.py` - Seed data script (creates sample users, products, etc.)
- `src/pybend/example/tests/` - Integration tests for the example app

### Documentation
- `src/pybend/docs/` - Handwritten API docs + auto-generated model docs
- `src/pybend/static/docs/` - Frontend component/architecture docs
- `src/pybend/core/utils/generate_docs.py` - Auto-doc generator (runs on startup)

### Tests
- `src/pybend/core/tests/unit/` - Framework unit tests (models, storage, auth, routes, etc.)
- `src/pybend/example/tests/` - Integration tests (CRUD, auth flow, pagination, FK hydration, etc.)

## Key Patterns

### BaseUser Pattern
Application user models extend `BaseUser` to get login, register, and password hashing for free:
```python
from pybend.core.models.base_user import BaseUser

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

### Custom Methods
```python
@expose_route('/like', methods=['POST'], access=AUTHENTICATED)
def like(self) -> str:
    ...
```
Appears in schema under `methods`, frontend renders via `<ntt-method>`. The `access=` parameter controls authorization (optional, defaults to model's `__access__` or `AUTHENTICATED`).

### Authenticated User Injection
Custom methods can receive the authenticated user by declaring a `user` parameter:
```python
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment, user: User = None) -> str:
    comment.user_owner = user.id if user else 1
    ...
```
The route layer's `_resolve_user()` bridge resolves the type hint: if it's a `StorableMixin` subclass (e.g., `User`), it fetches the full model instance via `.get(user_id)`. Otherwise it passes the raw JWT dict. The `user` param is never read from the request body — it's injected server-side from the JWT token. This maintains the auth/model boundary: the `authorize` package stays standalone (zero PyBend imports).

### Self-Referential Nesting
```python
class Comment(ProtoModel):
    parent_id: Optional[Ref['self']] = Field(default=None, description="Parent comment for nesting")
```
`Ref['self']` emits `{"type": "selfref"}` in JSON Schema. Stored as nullable `INTEGER` column. No join model needed.

### FK Column Naming Convention
Parent FK columns: `{parent_class_name_lowercase}_id` (e.g., `product_id`).
Avoid aliasing the `id` field on models to prevent naming clashes with self-referencing relationships.

### Actor System (v0.8)
The backend actor system mirrors the frontend's Actor/Matrix/TX pattern. Everything works identically on classes and instances via two custom descriptors.

**Actor base class** extends PydanticBaseModel via `ActorMeta` metaclass:
- `actormethod` descriptor: binds target = cls or self (one function, one implementation). Used for `inbox`, `handler`, `send`, `register`, `spawn`, `has`.
- `actorproperty` descriptor: resolves class or instance state. Used for `addr`, `children`, `parent`.
- Class-level state: `__addr__`, `__children__`, `__matrix__` (managed by `ActorMeta.__new__`)
- Instance-level state: `_addr`, `_children`, `_parent` as PrivateAttr (compatible with Pydantic V2 MI)
- `_parent` defaults to `self.__class__` (mirrors JS `this.#parent = this.constructor`)
- `ActorMeta` creates per-class `__children__` dict and `__interceptors__` dict, sets `__addr__` from `__tablename__` or class name, auto-registers with root Matrix if available
- `auto_register=False` kwarg on subclass skips Matrix registration
- `Actor.root()` getter/setter for `__matrix__` ClassVar
- `send()` three-case routing: (1) direct child match, (2) strip prefix + route, (3) prefix source + bubble to root
- `use(fn, on='inbox')` registers interceptors on inbox/send/request. Decorator forms supported.
- `inbox()` and `send()` run their interceptors before processing. Error TX short-circuits.
- `_interceptors` PrivateAttr for instance-level, `__interceptors__` ClassVar for class-level

**Matrix** extends Actor:
- Auto-registers as root if no root exists (`Actor.root(self)` in `__init__`)
- `has(addr)` checks child by first address segment
- Self-send prevention (target == own addr -> log error, return)
- `register_adapter()` for protocol adapters (HTTP, WS, MCP, AP)
- Module-level `matrix` instance created at import time

**TX** is a dataclass message envelope:
- `reply(data, name)` swaps source/target, new uuid, stores original in `meta['in_reply_to']`
- `error(message, code)` creates ERROR TX with `meta['error'] = True`
- `is_error` property checks name or meta flag

**ActorProxy** wraps any class or instance as a routable actor without MI:
- Useful when Actor multiple inheritance is not desired or not compatible
- Provides the same interface: `inbox`, `handler`, `send`, `register`, `spawn`, `has`
- Matrix can route to ActorProxy and Actor children uniformly

**Testing actors** — Pydantic's `__setattr__` prevents mock patching on instances. Use `object.__setattr__(instance, name, mock)` via the `mock_method()` context manager in `test_actor_system.py`.

### Dump Pipeline
The dump pipeline (`proto_dump.py`) mirrors the schema pipeline pattern for model serialization. Instead of `model_dump(response=True)`, use `model_response()`:

```python
# Before (v0.7):
data = product.model_dump(response=True)  # boolean flag bifurcation

# After (v0.8):
data = product.model_response()           # runs dump pipeline
data = product.model_dump()               # plain dict for storage (unchanged)
```

The pipeline runs composable `dict -> dict` stages:
```python
d = proto_dump.base(instance)       # Plain Pydantic data extraction
d = proto_dump.response(instance, d) # Inject $schema and $id
```

External packages extend via `@dump_extension`:
```python
from pybend.core.models.proto_dump import dump_extension

@dump_extension(after='response')
def activity(instance, d: dict) -> dict:
    if getattr(instance.__class__, '__federated__', False):
        d['@context'] = 'https://www.w3.org/ns/activitystreams'
        d['type'] = instance.__class__.__name__
    return d
```

### ActorModel Pattern
Models that need actor capabilities (messaging, lifecycle events) extend `ActorModel` instead of `ProtoModel`:

```python
from pybend.core.models.actor_model import ActorModel

class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> str: ...
```

One import change, zero other changes. `ActorModel(Actor, ProtoModel)` is the bridge class:
- MRO: `Product -> ActorModel -> Actor -> ProtoModel -> PydanticBaseModel`
- CRUD messages (`schema`, `create`, `get`, `list`, `update`, `delete`) are handled by `handler_crud()` which delegates to StorableMixin
- Non-CRUD messages fall through to Actor's generic handler (getattr dispatch)
- Lifecycle events (`after_create`, `after_update`, `after_delete`) are published as TX messages to subscribers

Models that do not need actor capabilities continue to extend `ProtoModel` directly. Join models generated by `generate_join_model()` inherit from their parent class.

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
| `NetworkAPI` | HTTP REST (FastAPI/Flask/Django) | Planned |
| `NetworkWebSocket` | WebSocket (frontend Matrix bridge) | v0.8.5 |

**Base class** (`NetworkAdapter`):
- Extends `Actor` with `auto_register=False` (needs manual `matrix.register()`)
- `request(tx, timeout)` — bridges synchronous protocols to fire-and-forget actor messaging via asyncio.Future correlation
- `inbox()` override — intercepts correlated replies (matching `meta['in_reply_to']` to pending Futures) before falling through to normal handler dispatch
- Runs `request` interceptors before sending (e.g., auth, rate limiting)

**Usage:**
```python
from pybend.core.api.network_mcp import NetworkMCP, create_mcp_routes
from pybend.core.api.network_ap import NetworkAP, create_federation_routes

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

**MCP adapter** converts model schemas to MCP tools. Tool names follow `{tablename}_{action}` (e.g., `products_create`, `products_favorite`). JSON-RPC methods: `initialize`, `ping`, `tools/list`, `tools/call`.

**AP adapter** receives LIFECYCLE TXs from ActorModel subscribers, converts to ActivityPub Activities (Create/Update/Delete), stores in outbox. Handles inbound Follow/Unfollow. Provides WebFinger actor discovery.

### Interceptor Pattern (`use()`)
Universal TX interceptors on any Actor method. Registered via `use()`, run before the method body.

```python
# Plain call
adapter.use(auth_interceptor, on='request')

# Decorator
@actor.use(on='inbox')
async def log_messages(tx: TX) -> TX:
    print(f"Received: {tx.name}")
    return tx

# Error TX short-circuits the chain
async def reject_all(tx: TX) -> TX:
    return tx.error("Rejected", code=403)
```

Class + instance interceptors combine (class first). `_get_interceptors(target, method_name)` returns the combined chain. `_run_interceptors(interceptors, tx)` runs FIFO, stops on `is_error`.

### Three Levels of PyBend
```python
# Level 1 — ProtoModel + direct routes (no actors)
app = create_app(models=[Product], storage="sqlite:///app.db")

# Level 2 — ActorModel + direct routes (actor capabilities, same HTTP layer)
# Just change ProtoModel → ActorModel in model definitions
app = create_app(models=[Product], storage="sqlite:///app.db")

# Level 3 — ActorModel + NetworkAPI (full actor routing)
app = create_app(models=[Product], storage="sqlite:///app.db", routing='actor')
```

Level 3 wires: `NetworkAPI` adapter + `auth_interceptor` on `request` + routes via `create_api_routes()`. All three levels produce identical API endpoints and responses.

### Two-Tier Auth (Level 3)
When `routing='actor'`, authorization is split:
- **Tier 1**: `auth_interceptor` on `NetworkAPI.request()` — fast gate at protocol boundary. Handles schema pass-through, sql_filter for list, full check for create, identity gate for read/update/delete.
- **Tier 2**: `ActorModel._authorize()` in `handler_crud()` — full ABAC with resource instance. Evaluates OWNER rules after fetching the entity.

Level 1/2 use `routes_fastapi.py`'s single-pass `_resolver.authorize(ctx)` — unchanged.

## Directives

### Documentation Updates
After completing any set of implementation tasks, ALWAYS update the relevant documentation:
1. **Auto-generated docs**: Run the server or call `generate_docs()` to refresh `src/pybend/docs/{model}.md`
2. **Handwritten API docs** (`src/pybend/docs/`): Update response examples, endpoint docs, and architecture descriptions
3. **Frontend docs** (`src/pybend/static/docs/`): Update component docs if frontend behavior changed
4. **This file** (`CLAUDE.md`): Update if architectural patterns or key file locations change

### Working Directory
For the **example app**, run from `src/pybend/example/` (that's where the example `main.py` lives).
For **framework code**, `src/pybend/core/` contains `config.py` and the backward-compat `main.py` shim.

### Testing Changes
1. Start server: `cd /workspace/src/pybend/example && python3 main.py`
   - Alternative: `cd /workspace && python3 -m pybend.example.main`
   - Legacy: `cd /workspace/src/pybend/core && python3 main.py` (delegates to example app)
2. Run framework unit tests: `cd /workspace/src/pybend/core && pytest tests/unit/`
3. Run integration tests: `cd /workspace/src/pybend/core && pytest ../example/tests/`
4. Test API (see auth examples below)
5. Test frontend: Open `http://localhost:5000/`

### Commit Messages
Format: `type(scope): Description [wave]`

- **type**: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
- **scope** (optional): area of codebase — `models`, `actors`, `api`, `ssr`, `frontend`, `schema`, `example`
- **Description**: imperative mood, capitalized (e.g., "Add", "Fix", not "Added", "Fixes")
- **[wave]**: current development wave in brackets (e.g., `[0.8.3]`). Check recent commits for the active wave.

Examples:
```
feat(actors): Add interceptor mechanism and two-tier auth [0.8.2]
fix(api): Move FastAPI imports to module level in network_api.py [0.8.2]
test(ssr): Add comprehensive tests for SSR modes and bundler [0.8.3]
docs: Update documentation for Wave 2 [0.8.2]
```

### Authentication for Testing
Most endpoints require a JWT token. Schema endpoints (`GET /{ClassName}`) are public.

**Seed users** (created by `cd src/pybend/example && python3 seed.py`):
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
# Authenticated request
curl -s http://localhost:5000/products -H "x-access-token: $TOKEN"

# Schema (no auth needed)
curl -s http://localhost:5000/Product
```
