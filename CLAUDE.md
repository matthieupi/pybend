# PyBend Project Guide

## Philosophy

PyBend absorbs the data plumbing — storage, fetching, state, serialization — so developers focus on what makes their app unique. Define a model, get an API, a schema, a working UI. The things that Redux, GraphQL, fetch(), and most of React solve become non-problems.

### Core Principles

**The model is the app.** A Python model definition is the single source of truth for the entire stack: data structure, validation, API endpoints, JSON Schema, access control, UI rendering. Write the model; the framework derives everything else. If the schema can carry it, the developer shouldn't have to repeat it.

**Zero to working, then customize.** Everything works out of the box with no configuration. Customization is additive — override one piece without rebuilding the rest. Use the auto-generated UI as-is, or override `render()`, or drop to raw messages. Each level down gives more control without losing what the levels above provided. The framework should never force a developer to understand the whole stack just to change one thing.

**Primitives, not opinions.** The framework provides composable building blocks — base classes, schema extensions, rendering utilities — not a rigid component library. Developers extend and compose. The framework owns the data lifecycle; developers own presentation and interaction. Think LitElement's approach to Web Components: powerful base, zero dictation.

**Backend is authoritative.** The backend defines models, schemas, access rules, relationships, and UI hints. The frontend reads these at runtime and adapts. Deploying a new model or changing a field propagates to the UI automatically. The frontend never duplicates what the backend already knows.

**Transparent, not magical.** Nothing is hidden behind abstractions you can't see through. Actor messaging, schema resolution, DynamicClass creation — all inspectable, all overridable. The value is not in hiding complexity but in not making you do it by hand. A developer should be able to trace any behavior from the HTML tag to the network request in under a minute.

**Modular where it simplifies, coupled where it must.** Architectural parts that can stand alone should stand alone. The `authorize` package has zero PyBend imports — it works as a generic ABAC library and happens to plug into PyBend. StorableMixin is injected, not inherited. The Actor system knows nothing about HTML. When a boundary is real (auth doesn't need to know about storage, messaging doesn't need to know about DOM), enforce it — separate packages, no cross-imports, clean interfaces. But don't split things that are genuinely one concern into two packages for the sake of modularity. A class with one consumer doesn't need its own file. An abstraction layer that just passes through adds indirection without value. The test: does this boundary make the code easier to read, easier to test, or easier to replace one side without touching the other? If yes, decouple. If it just adds a hop, keep it together.

## Architecture Overview

PyBend is a schema-driven framework where **model definitions are the single source of truth**. Models flow through: Model Definition -> JSON Schema -> API Routes -> Frontend Rendering.

### Backend (Python/FastAPI)

```
models/*.py          Define data models (extend ProtoModel)
     |
     v
ProtoModel           Base class: injects StorableMixin, rewrites FK fields,
                      generates JSON Schema, handles serialization
     |
     +-- schema()              Returns JSON Schema with $schema, $id, $defs, methods
     +-- model_dump()          Plain dict (DB). model_dump(response=True) adds $schema/$id
     +-- __init_subclass__()   Auto-injects StorableMixin for __storable__=True models
     |
     v
register_model()     Registers model with storage backend (main.py)
     |
     v
register_routes()    Auto-generates CRUD routes from registered models (routes_fastapi.py)
     |
     v
FastAPI router       Serves schema at GET /{ClassName}, CRUD at /{tablename}/...
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
| JSON Schema | Field types, validators, `json_schema_extra` | `ProtoModel.schema()` via Pydantic |
| DB table + migrations | `__storable__`, field annotations | `StorableMixin` injection, `sqlite_migration.py` |
| FK hydration (href arrays) | `ListRef[T]` fields, `__fk_models__` | `sqlite_storage.py` on read |
| Access control | `__access__`, `@expose_route(access=...)` | `routes_fastapi.py` auth injection |
| Frontend entity classes | Schema properties, methods | `NTT.SCHEMA()` → `prototype()` → DynamicClass |
| Form rendering | `properties`, `ui.widget`, `ui.placeholder` | `Formidable.getForm()` reads schema |
| Field order + grouping | `ui.field_order`, `ui.groups` | `form.js` renders fieldsets |
| Show/hide fields | `ui.display`, field-level `access` | `form.js` + `Permissions.js` |
| Edit button visibility | `access.update` | `ntt-item.js` checks `permissions.canAction()` |
| Delete button visibility | `access.delete` | `ntt-item.js` checks `permissions.canAction()` |
| Pagination (list endpoints) | `?limit=N&offset=M` query params | `sqlite_storage.py` COUNT + LIMIT/OFFSET |
| Authenticated user injection | `user: User` param on `@expose_route` methods | `_resolve_user()` in `routes_fastapi.py` |
| Method buttons | `schema.methods` | `<ntt-method>` reads method signatures |
| Component tag resolution | `ui.renderer.item`, `ui.renderer.detail` | `ntt-router.js` resolves tags for navigation |
| Adaptive display sizes | Schema properties, field order | `ntt-item.js` size methods (xs/sm/md/lg/xl) |

### The development workflow

1. Define or modify a Python model
2. Restart the server — `ProtoModel.schema()` generates the updated JSON Schema, `register_routes()` creates endpoints, migrations run
3. Open `matrix.html` — the frontend fetches the schema, creates DynamicClasses, renders everything
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
| `properties[field].ui.placeholder` | `form.js` → input attrs | Sets placeholder text on inputs |
| `properties[field].access` | `Permissions.js` → `canView()` | Field-level visibility per user role |
| `ui.field_order` | `form.js` → `getForm()` | Controls field rendering sequence |
| `ui.groups` | `form.js` → `renderGroupedFields()` | Wraps fields in `<fieldset>` groups |
| `ui.renderer.*` | `ntt-router.js` → `#resolveTag()` | Chooses component tag for navigation views |
| `access` | `Permissions.js` → `canAction()` | Shows/hides edit button, method buttons |
| `methods` | `prototype()` + `<ntt-method>` | Creates callable methods + renders action buttons |
| `$defs` | `NTT.SCHEMA()` | Registers nested DynamicClasses (Comment, etc.) |
| `$id` / `$schema` | DynamicClass value getter | Injected into every entity instance for self-description |

### Schema propagation lifecycle

```
1. Model Definition (Python)
   Product(ProtoModel) with fields, __ui__, __access__, @expose_route
                    │
2. Schema Generation (Backend, on GET /Product)
   ProtoModel.schema() → Pydantic JSON Schema + methods + access + ui + $defs
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
   model_dump(response=True) injects $schema + $id into each record
   │  Frontend DynamicClass value getter preserves these for self-description
   │  Any entity can be independently resolved: GET $id → full entity
   │  Collection fields return href arrays: ["http://.../products/1/comments/1", ...]
```

### Why this matters

**Adding a field** to a model automatically: adds a DB column, includes it in API responses, generates a form input, validates on both sides. **Changing `__access__`** propagates to the frontend: the edit button appears or disappears, list queries filter differently. **Adding `@expose_route`** creates an API endpoint and a clickable button in the UI. The schema carries intent, not just structure — the frontend doesn't interpret types, it follows instructions.

---

## Key Files by Area

### Models & Serialization
- `src/pybend/core/models/proto_model.py` - Base model, schema generation, `model_dump(response=True)`, `generate_join_model()`
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

### API / Routes
- `src/pybend/core/api/routes_fastapi.py` - Route factories with authorization injection, pagination, and user resolution bridge (`_resolve_user`)
- `src/pybend/core/utils/decorators.py` - `@expose_route()` for custom method endpoints (supports `access=` parameter)
- `src/pybend/core/utils/registrar.py` - `registered_models` dict, `join_models` dict

### Frontend (NTT 0.6)
- `src/pybend/static/NTT0.6/core/NTT.js` - Core: NTT class, prototype() factory, SCHEMA handler, DynamicClass creation
- `src/pybend/static/NTT0.6/core/Matrix.js` - Message bus / actor system
- `src/pybend/static/NTT0.6/core/Actor.js` - Base actor class
- `src/pybend/static/NTT0.6/core/Router.js` - Navigation state Actor (hash sync, history stack, Observable)
- `src/pybend/static/NTT0.6/components/ntt-item.js` - Item component: size methods (xs–xl), render dispatch, edit toggle, click-to-select
- `src/pybend/static/NTT0.6/components/ntt-list.js` - List component
- `src/pybend/static/NTT0.6/components/ntt-router.js` - Generic view container (loads any component via Router)
- `src/pybend/static/NTT0.6/components/ntt-element.js` - Base component class
- `src/pybend/static/NTT0.6/generators/form.js` - Formidable: schema-driven form generator
- `src/pybend/static/NTT0.6/utils/Permissions.js` - Reads schema access rules for UI permission checks

### Config & Entry
- `src/pybend/core/config.py` - HOST, PORT, API_URL, SQLITE_DB_FILE
- `src/pybend/core/main.py` - App entry: register models, generate docs, start server

### Documentation
- `src/pybend/docs/` - Handwritten API docs + auto-generated model docs
- `src/pybend/static/NTT0.6/docs/` - Frontend component/architecture docs
- `src/pybend/core/utils/generate_docs.py` - Auto-doc generator (runs on startup)

## Key Patterns

### Parent-Child Relationships
```python
# 1. Define parent with ListRef field
class Product(ProtoModel):
    comments: Optional[ListRef[Comment]] = Field(default=[])

# 2. Register join model in main.py
register_model(generate_join_model(Product, Comment), storage=storage_backend)
```
This creates a `ProductComment` join model with auto-generated `product_id` FK column. Routes become `/products/{parent_id}/comments/{id}`.

### API Response Format
All entity responses include JSON Schema instance metadata:
- `$schema`: URL to the model's schema (e.g., `http://localhost:5000/Product`)
- `$id`: URL to the specific instance (e.g., `http://localhost:5000/products/1`)

This is injected by `model_dump(response=True)`. Storage operations use plain `model_dump()` (no metadata).

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

## Directives

### Documentation Updates
After completing any set of implementation tasks, ALWAYS update the relevant documentation:
1. **Auto-generated docs**: Run the server or call `generate_docs()` to refresh `src/pybend/docs/{model}.md`
2. **Handwritten API docs** (`src/pybend/docs/`): Update response examples, endpoint docs, and architecture descriptions
3. **Frontend docs** (`src/pybend/static/NTT0.6/docs/`): Update component docs if frontend behavior changed
4. **This file** (`CLAUDE.md`): Update if architectural patterns or key file locations change

### Working Directory
Always run backend commands from `src/pybend/core/` (that's where `main.py` and `config.py` live).

### Testing Changes
1. Start server: `cd /workspace/src/pybend/core && python3 main.py`
2. Test API (see auth examples below)
3. Test frontend: Open `http://localhost:5000/static/NTT0.6/matrix.html`

### Authentication for Testing
Most endpoints require a JWT token. Schema endpoints (`GET /{ClassName}`) are public.

**Seed users** (created by `python3 seed.py`):
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
