# N3TX Core

The backend engine of N3TX. Defines models, generates schemas, serves APIs, enforces access control, and manages storage -- all driven from model definitions.

## Directory Structure

```
core/
|-- main.py              Application entry point (registers models, starts server)
|-- config.py            HOST, PORT, API_URL, SQLITE_DB_FILE
|-- seed.py              Seed data for development/testing
|-- models/              Model definitions and base classes
|   |-- proto_model.py   Base model: schema generation, model_dump, StorableMixin injection
|   |-- storable_mixin.py  CRUD operations (create/get/list/update/delete)
|   |-- ref.py           ListRef[T] type for collection references
|   |-- product_model.py Example: Product with fields, UI hints, access rules, methods
|   |-- comment_model.py Example: Comment with self-referencing (Ref['self'])
|   |-- user_model.py    User model with authentication methods
|   +-- like_model.py    Like model
|-- api/
|   |-- routes_fastapi.py  Auto-generated CRUD routes with auth injection
|   +-- backend.py       API backend adapter
|-- storage/
|   |-- sqlite_storage.py   SQLite backend with FK hydration
|   |-- sqlite_migration.py Auto-migration + Rails-style manual migrations
|   +-- sqlite_helpers.py   FK column detection helpers
|-- authorize/           Standalone auth package (zero N3TX imports)
|   |-- auth.py          JWT: password hashing, token create/decode
|   |-- rules.py         AccessRule base + built-in rules (ANYONE, AUTHENTICATED, OWNER, ROLE, Where)
|   |-- context.py       AccessContext dataclass
|   |-- resolver.py      AuthorizationResolver Protocol
|   |-- schema.py        Serialize access rules to JSON for schema exposure
|   +-- errors.py        AccessDenied exception
|-- utils/
|   |-- decorators.py    @expose_route() for custom method endpoints
|   |-- registrar.py     Model registry (registered_models, join_models)
|   |-- introspection.py Schema introspection, ListRef detection, model collection
|   |-- typer.py         Ref type (Ref[T], Ref['self']), flatten_refs()
|   +-- generate_docs.py Auto-doc generator (runs on startup)
|-- docs/                Auto-generated + handwritten API documentation
+-- tests/               PyTest test suite
```

## Schema-Driven Development

N3TX Core's central principle: **the model is the single source of truth**. A Python model definition generates everything the application needs -- API endpoints, JSON Schema, database tables, access control, and frontend rendering instructions.

### What a model definition carries

```python
class Product(ProtoModel):
    __tablename__ = 'products'        # -> API routes at /products/...
    __storable__ = True               # -> DB table, StorableMixin injection
    __ui__ = {                        # -> Frontend layout instructions
        'field_order': ['name', 'price', 'description', 'comments', 'favorites'],
        'groups': {'main': ['name', 'description', 'price'], 'Social': ['comments', 'favorites']},
        'methods': {
            'comment': {'layout': 'inline', 'attach_to': 'comments', ...},
            'favorite': {'layout': 'button', 'icon': 'star', 'count_field': 'favorites', ...},
        },
        'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
    }
    __access__ = {                    # -> Backend enforcement + frontend UI adaptation
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }

    name: str = Field(min_length=1, max_length=200,
                      json_schema_extra={'ui': {'placeholder': 'Product name...'}})
    price: float = Field(gt=0,
                         json_schema_extra={'ui': {'widget': 'currency'},
                                            'access': {'view': 'anyone', 'edit': 'admin'}})
    description: str = Field(default='',
                             json_schema_extra={'ui': {'widget': 'textarea'}})
    comments: ListRef[Comment] = Field(default=[])
    favorites: ListRef[Like] = Field(default=[], description="Users who favorited")

    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment, user: User = None) -> str: ...

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> str:
        """Toggle — create if not favorited, remove if already favorited."""
        ...
```

### What gets generated

| Concern | Source | Generator |
|---------|--------|-----------|
| CRUD API endpoints | `__tablename__`, fields | `register_routes()` in `routes_fastapi.py` |
| JSON Schema | Field types, validators, extras | `ProtoModel.schema()` via Pydantic |
| DB table + auto-migration | `__storable__`, annotations | `StorableMixin` + `sqlite_migration.py` |
| FK hydration (href arrays) | `ListRef[T]`, `__fk_models__` | `sqlite_storage.py` on read |
| Backend access control | `__access__`, `@expose_route(access=...)` | `routes_fastapi.py` auth middleware |
| Frontend access rules | `__access__` | `authorize/schema.py` serializes to JSON |
| Method endpoints | `@expose_route()` | `routes_fastapi.py` custom route registration |
| Method signatures in schema | `__endpoint__`, type hints | `__n3tx_methods_json_signature__()` |
| UI rendering hints | `__ui__`, `json_schema_extra` | Embedded in schema, read by frontend |
| Method UI hints | `__ui__.methods` (icon, layout, count_field) | Injected into `$defs` method entries |
| Toggle endpoints | `@expose_route` + join table logic | Like/favorite via create/delete on join models |
| Collection routes | Join model `__tablename__` | `GET /products/comments`, `GET /products/likes` |
| Pagination | `?limit=N&offset=M` query params | `sqlite_storage.py` COUNT + LIMIT/OFFSET |
| Protected fields | `__protected_fields__` | Route layer auto-injects on create, strips on update |
| Auto-generated docs | Model + schema | `generate_docs.py` on startup |

## Schema as Universal Contract

`ProtoModel.schema()` produces a JSON Schema that serves as the **complete contract** between backend and frontend. It is not just a type description -- it carries behavior, permissions, UI instructions, and relationship structure.

`ui.icon` is part of that contract. Models and methods can declare a single icon
token and let the frontend decide how to render it. Accepted values are direct
emoji, direct URL/path strings, or lookup keys resolved through the frontend's
shared icon registry.

### Schema generation pipeline

```
ProtoModel.schema()
|
|-- Pydantic model_json_schema()     -> properties, types, validation, $defs
|-- __n3tx_methods_json_signature__()  -> methods with routes, params, returns, access, stream, events
|-- access_schema(cls)               -> ABAC rules serialized to JSON
|-- _apply_field_exclusion()         -> auto-hide id, *_id, timestamps (ui.display=false)
|-- __ui__ injection                 -> field_order, groups, renderer hints
|-- $defs enrichment                 -> nested models get $id, methods, ui, access
|-- Ref['self'] patching             -> selfref fields in schema
+-- $schema / $id injection          -> meta-schema and identity URLs
```

### Schema anatomy

```
GET /Product -> JSON Schema
|-- $schema         -> "http://localhost:5000/Schema"
|-- $id             -> "http://localhost:5000/Product"
|-- __name__        -> "Product"
|-- __tablename__   -> "products"
|-- properties      -> field definitions with types, validation, ui hints, access
|-- ui              -> { field_order, groups, renderer }
|-- access          -> { create, read, update, delete } as serialized ABAC rules
|-- methods         -> { comment: { route, methods, scope, parameters, returns, access, ui, stream, events } }
|-- $defs           -> { Comment: { $id, properties, methods, ui, access }, Like: { ... } }
+-- required        -> required field names
```

### How the frontend consumes each section

| Schema section | Frontend consumer | Effect |
|---------------|------------------|--------|
| `properties` | `prototype()` in N3TX.js | Typed getters/setters on DynamicClass |
| `properties[f].ui.widget` | `form.js` | Widget selection (currency, textarea, ...) |
| `properties[f].ui.display` | `form.js` | Hide internal fields from UI |
| `properties[f].ui.protected` | `form.js` | Hides backend-owned fields in edit mode |
| `properties[f].access` | `Permissions.js` | Field-level visibility per role |
| `ui.field_order` | `form.js` | Field rendering order |
| `ui.groups` | `form.js` | Fieldset grouping |
| `ui.description` | `ListElement.render()` | Optional collection intro copy under the list title |
| `ui.create_label` | `ListElement.render()` | Optional labeled create button for collection headers |
| `ui.renderer.*` | `ntx-router.js` | Component tag for navigation views |
| `access` | `Permissions.js` | Show/hide edit/delete buttons (resource-aware OWNER) |
| `methods` | `prototype()` + `<ntx-method>` | Callable methods + action buttons |
| `methods[m].ui` | `<ntx-method>` | Button layout, icon, count-field for social actions |
| `methods[m].events` | `NTTStreamAgent` UPPERCASE handlers | Declared stream event types (JSON Schema per event) |
| `$defs` | `N3TX.SCHEMA()` | Nested DynamicClass registration |
| `$id` / `$schema` | DynamicClass value getter | Self-describing entity instances |

### Entity response format

Every entity response includes JSON Schema instance metadata via `model_response()` (runs the dump pipeline):

```json
{
  "$schema": "http://localhost:5000/Product",
  "$id": "http://localhost:5000/products/1",
  "id": 1,
  "name": "Wireless Headphones",
  "price": 79.99,
  "comments": [
    "http://localhost:5000/products/1/comments/1",
    "http://localhost:5000/products/1/comments/2"
  ]
}
```

- `$schema` points to the model's schema (the contract)
- `$id` is the instance's canonical URL (self-link, independently resolvable)
- Collection fields (`ListRef[T]`) return href arrays rather than embedded objects

## Key Patterns

### Parent-Child Relationships

```python
# Model defines the relationship
class Product(ProtoModel):
    comments: ListRef[Comment] = Field(default=[])

# main.py registers the join model
register_model(generate_join_model(Product, Comment), storage=storage_backend)
```

This creates a `ProductComment` join model with auto-generated `product_id` FK column. Routes become `/products/{parent_id}/comments/{id}`.

### Authorization (ABAC)

Access rules compose with `|` (OR), `&` (AND), `~` (NOT):

```python
__access__ = {
    'update': OWNER | ROLE('admin'),       # owner OR admin
    'delete': ROLE('admin'),               # admin only
}

@expose_route('/publish', methods=['POST'], access=OWNER & Where(status='draft'))
def publish(self): ...                     # owner AND status is draft
```

Rules produce SQL WHERE clauses for efficient list filtering (SQL pushdown). They serialize to JSON in the schema so the frontend can adapt without duplicating logic.

### Toggle Endpoints (Like/Favorite)

Toggle methods use join tables to track state. Empty body allowed -- no payload needed:

```python
@expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
def favorite(self, user: User = None) -> str:
    """Toggle — create if not favorited, remove if already favorited."""
    ...
```

Returns `{"action": "favorited"}` or `{"action": "unfavorited"}`. The route layer queries the join table (`ProductLike`) and creates or deletes the record.

### Collection Routes

Join models automatically get collection routes that return all records across parents:

```
GET /products/comments    -> all comments across all products
GET /products/likes       -> all likes (favorites) across all products
```

Collection routes are registered in Pass 1 (before CRUD routes) to avoid path conflicts with `{id:int}` segments.

### Custom Methods

```python
@expose_route('/like', methods=['POST'], access=AUTHENTICATED)
def like(self) -> str: ...
```

This creates `POST /products/{id}/like`, appears in `schema.methods`, and the frontend renders it as a clickable `<ntx-method>` button -- all from one decorator. Button-layout methods (like, favorite) render as compact icon + count pills via `__ui__.methods` hints.

## Running

```bash
cd src/n3tx/core
python3 main.py          # Start server on localhost:5000
python3 seed.py          # Seed development data
```

## Testing

```bash
cd src/n3tx/core
pytest tests/                  # Backend unit tests
python3 test_social.py         # Playwright: social features (15 checks)
python3 test_routing.py        # Playwright: URL path correctness
```

Tests cover: CRUD API, schema endpoints, storage, custom methods, social toggles (like/favorite), reply creation, collection routes, and frontend rendering (star/heart/reply buttons, reply indent, favorites navigation).
