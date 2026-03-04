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

## MANDATORY: Load Domain-Specific Context

Before starting ANY implementation task, you MUST read the appropriate sub-document(s):

- **Backend work** (Python, models, storage, API, auth): Read `claude-back.md` in this directory
- **Frontend work** (JS, Web Components, N3TX, UI): Read `claude-front.md` in this directory
- **Full-stack work** (changes spanning both): Read BOTH files

This is not optional. Do not begin writing code without first loading the relevant context file(s). These files contain key file locations, patterns, and conventions that you must follow.

---

## Development Workflow

### Before Making Changes

Before writing any code, review the area you are about to change. Understand the intent behind the existing implementation — why it was built this way, what patterns it follows, and how it fits into the larger system. Changes must be consistent with the architecture already in place. Do not work around the framework; work with it.

**Consistency is paramount.** N3TX's power comes from a small number of patterns applied uniformly across the entire stack. A single inconsistency — a hand-rolled route bypassing `register_routes()`, a frontend component fetching data outside the schema flow, a model that stores data differently from every other model — creates confusion, breaks assumptions, and compounds into real bugs over time. Every change should reinforce the existing architecture, not erode it. When in doubt, look at how the same thing is done elsewhere in the codebase and follow that pattern.

### Bug Fixes

**Test-Driven Bug Fixing (TDD).** Every bug fix MUST follow the red-green-refactor cycle:

1. **Red — Write a failing test first.** Before touching any production code, write a test that reproduces the reported bug. The test should fail for the same reason the bug manifests. This proves you understand the bug and gives you a clear signal when it's fixed. Place the test in the appropriate test directory (`core/tests/unit/` for framework bugs, `example_api/tests/` or `example_actor/tests/` for integration/app bugs, `static/tests/` for frontend bugs).

2. **Green — Fix the bug.** Make the minimal change needed to turn the failing test green. Do not refactor, do not clean up, do not fix adjacent issues — just make the test pass.

3. **Refactor — Clean up if needed.** Once green, improve the fix if the code can be clearer or more consistent with surrounding patterns. The test ensures you don't regress.

If the bug cannot be reproduced with a test (e.g., environment-specific, timing-dependent), document why in a comment on the fix and describe the manual reproduction steps. But the default is always: **test first, fix second**.

Beyond standard analysis (reproduce, isolate, fix, verify), always ask **why** the bug exists. Most bugs are symptoms of deeper misalignment, not simple typos.

**Root cause categories:**

1. **Misunderstood architecture.** The change works in isolation but conflicts with the system's actual patterns. Fix: understand the correct pattern, rewrite to be consistent. If the same area keeps producing bugs, improve its documentation.

2. **Architecture gap.** The developer understood the system but found no clean way to achieve their goal, so they hacked around it. Fix: don't patch the hack — ask what the architecture should provide so this can be done cleanly, then make that deeper change.

3. **Violated expectations.** The code "works" (no crash) but produces silently wrong behavior — invisible at origin, visible only downstream where it looks like something else.

   **Case study: the 200-OK error.** Model methods returned error strings with HTTP 200. Everything downstream treated it as success — the bug was invisible across three layers (UI → network → database). Root cause: the framework had no mechanism for methods to signal errors with proper HTTP semantics. Fix: (a) `MethodError` exception that the route layer converts to proper HTTP errors, (b) frontend toast notifications with defensive `{"error": ...}` detection in 200 bodies.

   **Watch for:** failure encoded inside success channels — error dicts from data-returning functions, swallowed exceptions returning defaults, logged errors with continued execution. Test: if a consumer only checks status/type, would they know something failed?

**Response framework:** Identify root cause → decide if the fix is a code correction, documentation improvement, or architectural enhancement. Never silence symptoms. For recurring bugs in the same area, the fix must also address the documentation or API surface — not just patch the instance.

## Architecture Overview

N3TX is a schema-driven framework where **model definitions are the single source of truth**. Models flow through: Model Definition → JSON Schema → API Routes → Frontend Rendering.

### Three Levels of Bootstrapping

```python
# Level 1 — One-liner via create_app():
app = create_app(models=[Product, User], storage="sqlite:///app.db")

# Level 2 — Builder via N3TXApp:
pb = N3TXApp(storage="sqlite:///app.db")
pb.model(Product).model(User).join(Product, Comment)
app = pb.build()

# Level 3 — Raw primitives (full manual control, existing main.py pattern):
register_model(Product, storage=storage_backend)
register_routes(registered_models)
```

Level 3 with `routing='actor'` wires `NetworkAPI` adapter + `auth_interceptor` on `request` + routes via `create_api_routes()`. All three levels produce identical API endpoints and responses.

### Backend (Python/FastAPI)

Models extend `ProtoModel` (or `ActorModel` for actor capabilities). `ProtoModel.schema()` orchestrates the schema pipeline (`base → strip_hidden → methods → defs → access → widget → ui → metadata`), `model_response()` runs the dump pipeline. Models are registered via `register_model()` and routes auto-generated via `register_routes()`. See `claude-back.md` for the full backend pipeline diagram and key files.

### Frontend (Vanilla JS Web Components)

The frontend bootstraps by fetching schema from the backend. `N3TX.SCHEMA()` creates DynamicClasses via `prototype()`, which are then rendered by Web Components (`ntx-list`, `ntx-item`, `ntx-element`, `ntx-method`) with forms generated by `Formidable`. See `claude-front.md` for the frontend architecture diagram and key files.

### Data Flow: Request Lifecycle

1. Frontend `<ntx-list model="Product">` triggers schema fetch → `GET /Product`
2. Backend returns JSON Schema with `$schema`, `$id`, `properties`, `$defs`, `methods`
3. Frontend creates DynamicClass from schema, registers nested `$defs` models
4. DynamicClass triggers `READ` → `GET /products?limit=20&offset=0` (paginated)
5. Backend returns `{data: [...], meta: {total, limit, offset, has_more}}` with `$schema`/`$id` on each item
6. Frontend creates instances, renders via `ntx-item` components with "Load More" button if `has_more`

## Schema-Driven Development

Write a Python model, get a working full-stack application. The model definition is the only thing a developer writes. Everything else — API, validation, storage, UI, permissions, navigation — is derived from the schema that model produces. Any project can be transformed into a full stack application by turning a few classes into models.

### Canonical Model Example

```python
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

From this definition, `ProtoModel.schema()` generates a JSON Schema document that carries **everything the frontend needs**.

### What Gets Generated (zero code required)

| Concern | Generated from | Where it happens |
|---------|---------------|-----------------|
| CRUD API endpoints | `__tablename__`, model fields | `register_routes()` in `routes_fastapi.py` |
| JSON Schema | Field types, validators, `json_schema_extra` | `ProtoModel.schema()` via `proto_schema` pipeline |
| Enriched JSON responses | `model_response()`, dump pipeline stages | `proto_dump` pipeline (`base` → `response` → extensions) |
| DB table + migrations | `__storable__`, field annotations | `StorableMixin` injection, `sqlite_migration.py` |
| FK hydration (href arrays) | `ListRef[T]` fields, `__fk_models__` | `sqlite_storage.py` on read |
| Access control | `__access__`, `@expose_route(access=...)` | `routes_fastapi.py` auth injection |
| Frontend entity classes | Schema properties, methods | `N3TX.SCHEMA()` → `prototype()` → DynamicClass |
| Form rendering | `properties`, `ui.widget`, `ui.placeholder` | `Formidable.getForm()` reads schema |
| Field order + grouping | `ui.field_order`, `ui.groups` | `form.js` renders fieldsets |
| Show/hide fields | `ui.display`, field-level `access` | `form.js` + `Permissions.js` |
| Protected fields | `__protected_fields__` | Route layer auto-injects on create, strips on update; `form.js` hides in edit mode |
| Edit button visibility | `access.update` + resource OWNER check | `ntx-item.js` checks `permissions.canAction(access, 'update', value)` |
| Delete button visibility | `access.delete` + resource OWNER check | `ntx-item.js` checks `permissions.canAction(access, 'delete', value)` |
| $defs access rules | Referenced model `__access__` | `proto_schema.access()` injects into `$defs` entries |
| Pagination (list endpoints) | `?limit=N&offset=M` query params | `sqlite_storage.py` COUNT + LIMIT/OFFSET |
| Authenticated user injection | `user: User` param on `@expose_route` methods | `_resolve_user()` in `routes_fastapi.py` |
| Method buttons | `schema.methods` | `<ntx-method>` reads method signatures |
| Component tag resolution | `ui.renderer.item`, `ui.renderer.detail` | `ntx-router.js` resolves tags for navigation |
| Adaptive display sizes | Schema properties, field order | `ntx-item.js` size methods (xs/sm/md/lg/xl) |

### Development Workflow

1. Define or modify a Python model
2. Restart the server — `ProtoModel.schema()` generates the updated JSON Schema, `register_routes()` creates endpoints, migrations run
3. Open `http://localhost:5000/` — the frontend fetches the schema, creates DynamicClasses, renders everything
4. No frontend code changed. No routes added. No forms built. No permissions wired.

To customize, override at any level: swap a widget via `json_schema_extra`, control layout via `__ui__`, change permissions via `__access__`, or write a custom component that extends `NTTElement`.

**Adding a field** to a model automatically: adds a DB column, includes it in API responses, generates a form input, validates on both sides. **Changing `__access__`** propagates to the frontend: the edit button appears or disappears, list queries filter differently. **Adding `@expose_route`** creates an API endpoint and a clickable button in the UI. The schema carries intent, not just structure — the frontend doesn't interpret types, it follows instructions.

### Schema as Universal Contract

The JSON Schema returned by `GET /{ClassName}` is the **single contract between backend and frontend**. It carries the complete specification of how an entity behaves, renders, and is controlled — not just type descriptions. See `claude-front.md` for the full schema anatomy, consumption mapping, and propagation lifecycle.

## Key Files (Cross-Cutting)

### Actor System (v0.8)
- `src/n3tx/core/actors/actor.py` - Base actor class with unified class/instance dispatch via `actormethod`/`actorproperty` descriptors and `ActorMeta` metaclass. Addr, children, parent, inbox, handler, send, register, spawn, `use()` interceptors. Auto-registers with Matrix via metaclass.
- `src/n3tx/core/actors/matrix.py` - Root actor and message router. `has()`, self-send guard, adapter delegation, interceptor support. Module-level `matrix` instance created at import.
- `src/n3tx/core/actors/tx.py` - TX message envelope (dataclass): name, source, target, data, meta, timestamp, uuid. `reply()` swaps source/target with new uuid. `error()` creates ERROR TX. `is_error` property.
- `src/n3tx/core/actors/actor_proxy.py` - `ActorProxy` wrapper: gives any class or instance the actor interface (inbox/handler/send/register/spawn) without inheritance. Used when full Actor MI is not desired.
- `src/n3tx/core/actors/__init__.py` - Re-exports `TX`, `Actor`, `Matrix`, `matrix`

### Example Applications
- `example_api/` - Level 1/2 example (direct routes, `create_app()`)
- `example_actor/` - Level 3 example (actor routing, `routing='actor'`)
- `example_grants/` - Agents example (grants domain, agent CRUD + tool discovery)
- `src/n3tx/example/` - Legacy example app (may delegate to above)

### Documentation
- `src/n3tx/docs/` - Handwritten API docs + auto-generated model docs
- `src/n3tx/static/docs/` - Frontend component/architecture docs
- `src/n3tx/core/utils/generate_docs.py` - Auto-doc generator (runs on startup)

### Tests
- `src/n3tx/core/tests/unit/` - Framework unit tests (models, storage, auth, routes, etc.)
- `example_api/tests/` - Integration tests: CRUD, auth flow, pagination, FK hydration, etc. (Level 1/2)
- `example_actor/tests/` - Integration tests: same coverage as example_api but with actor routing (Level 3)
- `example_grants/tests/` - Integration tests: agents, grants, sources, e2e navigation

## Cross-Cutting Patterns

### Custom Methods
```python
@expose_route('/like', methods=['POST'], access=AUTHENTICATED)
def like(self) -> str:
    ...
```
Appears in schema under `methods`, frontend renders via `<ntx-method>`. The `access=` parameter controls authorization (optional, defaults to model's `__access__` or `AUTHENTICATED`).

### Authenticated User Injection
Custom methods can receive the authenticated user by declaring a `user` parameter:
```python
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment, user: User = None) -> str:
    comment.user_owner = user.id if user else 1
    ...
```
The route layer's `_resolve_user()` bridge resolves the type hint: if it's a `StorableMixin` subclass (e.g., `User`), it fetches the full model instance via `.get(user_id)`. Otherwise it passes the raw JWT dict. The `user` param is never read from the request body — it's injected server-side from the JWT token. This maintains the auth/model boundary: the `authorize` package stays standalone (zero N3TX imports).

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

### ActorModel Pattern
Models that need actor capabilities (messaging, lifecycle events) extend `ActorModel` instead of `ProtoModel`:

```python
from n3tx.core.models.actor_model import ActorModel

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

### Three Levels of N3TX
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

### Widget Pattern (Overview)
Widget fields map Python types to specialized frontend renderers. The `Widget` class hierarchy serves as both a type annotation and a metadata carrier. The `widget` schema pipeline stage (registered `before='ui'`) injects `ui.widget` + `ui.config` into JSON Schema properties. On the frontend, `form.js` and `ntx-item.js` dispatch to registered JS Widget instances (`getWidgetForField()`) before falling through to type-based rendering. See `claude-back.md` for Python widget details and `claude-front.md` for JS widget details.

## Directives

### Documentation Updates
After completing any set of implementation tasks, ALWAYS update the relevant documentation:
1. **Auto-generated docs**: Run the server or call `generate_docs()` to refresh `src/n3tx/docs/{model}.md`
2. **Handwritten API docs** (`src/n3tx/docs/`): Update response examples, endpoint docs, and architecture descriptions
3. **Frontend docs** (`src/n3tx/static/docs/`): Update component docs if frontend behavior changed
4. **This file** (`CLAUDE.md`): Update if architectural patterns or key file locations change. Also update `claude-back.md` or `claude-front.md` as appropriate.

### Working Directory
For the **example app**, run from `src/n3tx/example/` (that's where the example `main.py` lives).
For **framework code**, `src/n3tx/core/` contains `config.py` and the backward-compat `main.py` shim.

### Testing Changes
1. Start server: `cd /workspace/src/n3tx/example && python3 main.py`
   - Alternative: `cd /workspace && python3 -m n3tx.example.main`
   - Legacy: `cd /workspace/src/n3tx/core && python3 main.py` (delegates to example app)
2. Run framework unit tests: `cd /workspace/src/n3tx/core && python3 -m pytest tests/unit/`
3. Run integration tests:
   - `cd /workspace && python3 -m pytest example_api/tests/` (Level 1/2 direct routes)
   - `cd /workspace && python3 -m pytest example_actor/tests/` (Level 3 actor routing)
   - `cd /workspace && python3 -m pytest example_grants/tests/` (grants/agents app)
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

**Seed users** (created by `cd src/n3tx/example && python3 seed.py`):
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
