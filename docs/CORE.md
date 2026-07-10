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
|   |-- ref.py           Ref[T], distributed ref helpers
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
|-- authorize/           Standalone auth package (zero N3TX imports)
|   |-- auth.py          JWT: password hashing, token create/decode
|   |-- rules.py         AccessRule base + built-in rules (ANYONE, AUTHENTICATED, OWNER, ROLE, Where)
|   |-- context.py       AccessContext dataclass
|   |-- resolver.py      AuthorizationResolver Protocol
|   |-- schema.py        Serialize access rules to JSON for schema exposure
|   +-- errors.py        AccessDenied exception
|-- utils/
|   |-- decorators.py    @expose_route() for custom method endpoints
|   |-- registrar.py     Model registry (registered_models)
|   |-- introspection.py Schema introspection, list[T]/list[Ref[T]] detection, model collection
|   |-- typer.py         Compatibility re-export for Ref, Ref['self'], flatten_refs()
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
    __access__ = {                    # Optional -> Backend enforcement + frontend UI adaptation
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
    comments: list[Comment] = Field(default=[])
    favorites: list[Like] = Field(default=[], description="Users who favorited")

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
| Class-name read mirror | model class name + `__storable__` | `GET /{ClassName}/{id:int}` delegates to the table-name read path |
| HTML/view entrypoints | `__ui__` / `ViewableMixin` | `GET /{ClassName}/@...` returns frontend shell HTML |
| JSON Schema | Field types, validators, extras | `ProtoModel.schema()` via Pydantic |
| DB table + auto-migration | `__storable__`, annotations | `StorableMixin` + `sqlite_migration.py` |
| JSON TEXT fields | `dict`, `Dict[...]`, primitive lists, `list[T]`, `list[Ref[T]]` | `sqlite_storage.py` serializes/deserializes with `json.dumps`/`json.loads`; see [JSON Fields](JSON_FIELDS.md) |
| Local relationship hydration | `T`, `list[T]` | Stored as local ids and hydrated into model objects on read |
| Backend access control | `__access__`, `@expose_route(access=...)` | `routes_fastapi.py` auth middleware |
| Frontend access rules | `__access__` | `authorize/schema.py` serializes to JSON |
| Method endpoints | `@expose_route()` | `routes_fastapi.py` custom route registration |
| Method signatures in schema | `__endpoint__`, type hints, descriptor scope | `__n3tx_methods_json_signature__()` |
| UI rendering hints | `__ui__`, `json_schema_extra` | Embedded in schema, read by frontend |
| Method UI hints | `__ui__.methods` (icon, layout, count_field) | Injected into `$defs` method entries |
| Toggle endpoints | `@expose_route` + `list[T]` updates | Like/favorite via create/delete child record + parent list replacement |
| Relationship collections | `list[T]` fields | Ordered hydrated object arrays in parent responses |
| Pagination | `?limit=N&offset=M` query params | `sqlite_storage.py` COUNT + LIMIT/OFFSET |
| Protected fields | `__protected_fields__` | Route layer auto-injects on create, strips on update |
| Route view renderers | `__ui__.renderer` | `#Model/@view` and `/Model/@view` resolve semantic views to component tags |
| File metadata + byte storage | Optional `n3tx_files.File` model + `FileStore` | Metadata in N3TX storage, bytes in provider-backed store |
| File-typed method args | `param: File` annotation | `n3tx_files` materializer resolves `/File/{id}` or `n3tx://files/{id}` |
| Auto-generated docs | Model + schema | `generate_docs.py` on startup |

If a model omits `__access__`, schema generation exposes a wildcard fallback
(`access['*']`) that requires authentication for all actions. The Product
example above shows an explicit ownership policy as an illustrative model-level
contract; the shipped `examples/core` Product currently uses the authenticated
wildcard fallback, while Comment declares owner/admin rules and protected
`user_owner` ownership metadata.

Embedded `dict`, primitive lists, `list[T]`, and `list[Ref[T]]` fields are
persisted as JSON TEXT columns. Use them for configuration, metadata, primitive
arrays, local owned model collections, distributed pointer arrays such as
`list[Ref[File]]`, and external payload fragments. Use explicit models and
custom methods when nested data needs identity, authorization, lifecycle events,
or domain-specific append/toggle behavior.
See [JSON Fields](JSON_FIELDS.md) for the full contract and tradeoffs.

`@expose_route` methods publish descriptor-aware scope metadata in schema.
Instance methods (`self`) set `requires_instance: true` and route through
`/{ClassName}/{id}{route}`. Class methods, static methods, and service-style
actor methods without `self`/`cls` set `requires_instance: false` and route
through `/{ClassName}{route}`. Distributed adapters use this schema route and
scope instead of deriving URLs from Python method names.

### Optional File Capability

`n3tx-files` adds a first-class `File(ActorModel)` resource without making core
depend on file storage. A file is represented as normal N3TX metadata plus a
provider-owned byte object:

```python
from n3tx_files import File, LocalFileStore, configure_file_store

configure_file_store(LocalFileStore('./file-blobs'))
app = create_app(models=[File], storage='sqlite:///app.db')
```

Generated and package-owned behavior:

| Concern | Contract |
|---|---|
| Metadata CRUD/schema | Normal `File` model endpoints and `File.schema()` |
| Upload | `POST /files/upload` multipart form field named `upload` |
| Download | `GET /files/{id}/download` and `GET /File/{id}/download` |
| Range reads | `Range: bytes=start-end` returns `206` + `Content-Range` |
| Address resolution | `File.resolve('/File/1')`, `File.resolve('n3tx://files/1')` |
| Typed materialization | Method params annotated as `File` resolve address strings to `File` instances |

Blob bytes are never stored in SQLite and dynamic user files are not served by
the framework static-file catch-all. CDN/object-store/remote-node behavior is a
provider strategy behind `FileStore`, not a separate app concept.

## Schema as Universal Contract

`ProtoModel.schema()` produces a JSON Schema that serves as the **complete contract** between backend and frontend. It is not just a type description -- it carries behavior, permissions, UI instructions, and relationship structure.

`ui.icon` is part of that contract. Models and methods can declare a single icon
token and let the frontend decide how to render it. Accepted values are direct
emoji, direct URL/path strings, or lookup keys resolved through the frontend's
shared icon registry (typically to inline SVG, with image and text fallbacks).

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
  "$id": "http://localhost:5000/Product/1",
  "id": 1,
  "name": "Wireless Headphones",
  "price": 79.99,
  "comments": [
    {
      "$schema": "http://localhost:5000/Comment",
      "$id": "http://localhost:5000/Comment/1",
      "id": 1,
      "name": "Great sound"
    }
  ]
}
```

- `$schema` points to the model's schema (the contract)
- `$id` is the instance's canonical class-name URL (self-link, independently resolvable)
- `list[T]` fields return hydrated child objects with their own `$schema`/`$id`

### Model-Centric Route Grammar

N3TX keeps the original table-name JSON API and adds class-name model routes for
schema, read mirrors, and HTML/view shells:

```text
/{tablename}/...       compatibility JSON API and custom methods
/{ClassName}           JSON Schema/type endpoint
/{ClassName}/_         JSON collection mirror of /{tablename}
/{ClassName}/{id:int}  JSON instance mirror of /{tablename}/{id:int}
/{ClassName}/{id:int}/{method}
                       literal method mirror of /{tablename}/{id:int}/{method}
/{ClassName}/@...      HTML/view entrypoints
#{ClassName}/@...      frontend hash-router view routes
```

The `@` marker is reserved for views. A route such as `Product/1/run` remains a
method/action route, while `Product/1/@run` is a view named `run`. The `_`
marker is reserved for backend JSON collection reads and is not a frontend hash
view route. Class-name create/update/delete mirrors are available. Class-name
method mirrors are registered for literal `@expose_route` declarations only;
there is no generic method catch-all.

`$id` uses class-name identity even when an entity is fetched through a legacy
table-name route:

```json
{
  "$schema": "http://localhost:5000/Product",
  "$id": "http://localhost:5000/Product/1"
}
```

Table-name routes remain available for JSON compatibility while response
identity uses the class-name grammar.

## Key Patterns

### Local Model Collections

```python
# Model defines the relationship
class Product(ProtoModel):
    comments: list[Comment] = Field(default=[])
```

`list[T]` stores an ordered JSON list of local child ids on the parent row and
hydrates those ids into child objects in responses. Domain actions update the
collection through model methods:

```python
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment, user: User = None) -> Comment:
    saved = Comment.create(comment)
    type(self).update(self.id, {'comments': [*self.comments, saved]})
    return saved
```

For shared relationship data, prefer an explicit link model. `ManyToMany[T]` is
a legacy helper for existing shared-link cases, not the default collection
primitive.

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

Toggle methods create/delete the child record and replace the parent `list[T]`.
Empty body allowed -- no payload needed:

```python
@expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
def favorite(self, user: User = None) -> str:
    """Toggle — create if not favorited, remove if already favorited."""
    ...
```

Returns a structured action payload such as `{"action": "favorited", "_field": "favorites", "id": 123, "user": 1}` or `{"action": "unfavorited", "_field": "favorites", "id": 123}`. The `_field` + `id` pair lets the frontend update the affected collection locally without an extra entity fetch.

### Custom Methods

```python
@expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
def favorite(self) -> dict: ...
```

This creates `POST /products/{id}/favorite`, appears in `schema.methods`, and the frontend renders it as a clickable `<ntx-method>` button -- all from one decorator. Button-layout methods (like, favorite) render as compact icon + count pills via `__ui__.methods` hints.

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

Tests cover: CRUD API, schema endpoints, storage, custom methods, social toggles (like/favorite), reply creation, hydrated local collections, and frontend rendering (star/heart/reply buttons, reply indent, favorites navigation).
