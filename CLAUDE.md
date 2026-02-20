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
ntt-item.js          <ntt-item> - renders single entity card with edit mode
ntt-element.js       Base web component class for all NTT elements
ntt-method.js        Renders callable methods as buttons
form.js              Formidable generator - builds forms from schema properties
```

### Data Flow: Request Lifecycle

1. Frontend `<ntt-list model="Product">` triggers schema fetch -> `GET /Product`
2. Backend returns JSON Schema with `$schema`, `$id`, `properties`, `$defs`, `methods`
3. Frontend creates DynamicClass from schema, registers nested `$defs` models
4. DynamicClass triggers `READ` -> `GET /products`
5. Backend returns list of dicts with `$schema` and `$id` (via `model_dump(response=True)`)
6. Frontend creates instances, renders via `ntt-item` components

## Key Files by Area

### Models & Serialization
- `src/pybend/core/models/proto_model.py` - Base model, schema generation, `model_dump(response=True)`, `generate_join_model()`
- `src/pybend/core/models/storable_mixin.py` - CRUD operations (create/get/list/update/delete)
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
- `src/pybend/core/api/routes_fastapi.py` - Route factories with authorization injection (make_create_instance, etc.)
- `src/pybend/core/utils/decorators.py` - `@expose_route()` for custom method endpoints (supports `access=` parameter)
- `src/pybend/core/utils/registrar.py` - `registered_models` dict, `join_models` dict

### Frontend (NTT 0.6)
- `src/pybend/static/NTT0.6/core/NTT.js` - Core: NTT class, prototype() factory, SCHEMA handler
- `src/pybend/static/NTT0.6/core/Matrix.js` - Message bus / actor system
- `src/pybend/static/NTT0.6/core/Actor.js` - Base actor class
- `src/pybend/static/NTT0.6/components/ntt-item.js` - Item component (display/edit)
- `src/pybend/static/NTT0.6/components/ntt-list.js` - List component
- `src/pybend/static/NTT0.6/components/ntt-element.js` - Base component class
- `src/pybend/static/NTT0.6/generators/form.js` - Formidable form generator

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
2. Test API: `curl http://localhost:5000/products` (list), `curl http://localhost:5000/Product` (schema)
3. Test frontend: Open `http://localhost:5000/static/NTT0.6/matrix.html`
