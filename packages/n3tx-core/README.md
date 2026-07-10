# 🧱 n3tx-core — The Foundation That Does the Heavy Lifting

> Define a Python model, get a full-stack application. Storage, API, schema, auth, frontend rendering — all derived automatically. You write the model, we handle the plumbing.

## 🌐 Overview

n3tx-core is the beating heart of the N3TX ecosystem. It gives you `ProtoModel` — the base class that turns your Python model definitions into database tables, CRUD endpoints, JSON Schema contracts, authorization rules, and frontend rendering instructions. All at once. No repetition.

Everything above it — actors, agents, UI components — depends on this package and extends its pipelines. If N3TX is the building, this is the foundation, the plumbing, and the electrical all in one.

## 📦 Installation

```bash
# Standalone
pip install n3tx-core

# Full ecosystem (includes actors, agents, UI)
pip install n3tx

# Editable dev install
pip install -e "packages/n3tx-core[dev]"
```

## 🚀 Quick Start

Here's the fun part — you write a couple of classes and get a working API with auth, relationships, and custom endpoints:

```python
from n3tx_core import ProtoModel, expose_route, register_model, SQLiteStorage
from n3tx_core.app import create_app
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from pydantic import Field

class Comment(ProtoModel):
    __tablename__ = 'comments'
    __storable__ = True
    text: str = Field(min_length=1)

class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED, 'update': OWNER, 'delete': ROLE('admin')}
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    comments: list[Comment] = Field(default=[])

    @expose_route('/like', methods=['POST'], access=AUTHENTICATED)
    def like(self, user=None) -> str:
        return f"Liked by user {user['user_id']}"

# One-liner: creates storage, registers models, generates routes, returns ASGI app
app = create_app(
    models=[Product, Comment],
    storage="sqlite:///app.db",
)
```

That's it. You've got a database, REST endpoints, access control, and a schema the frontend can consume. Go grab a coffee.

## 🧠 Core Concepts

### The Model is the App

A `ProtoModel` subclass with `__storable__ = True` gets: a database table, CRUD API endpoints, a JSON Schema, authorization, and frontend rendering. `__init_subclass__` injects `StorableMixin` into the class hierarchy automatically. You don't wire anything up — it just works.

### Schema Pipeline

`ProtoModel.schema()` runs a composable pipeline of `dict -> dict` stages: `base -> strip_hidden -> methods -> defs -> access -> widget -> ui -> metadata`. Each stage enriches the JSON Schema. External packages insert stages via `@schema_extension(after='methods')` without modifying core. Want to add your own stage? Slot it in wherever you need it.

### Dump Pipeline

`instance.model_response()` runs a parallel pipeline for serialization: `base -> relationships -> schema_url -> instance_url -> populate`. The `relationships` stage enriches hydrated `T` and `list[T]` children through their own dump pipelines; the URL stages inject `$schema` and `$id`. Extended via `@dump_extension`. Same composable pattern, different direction — schema describes the shape, dump fills it with data.

### 🔐 Authorization (ABAC)

The `authorize` subpackage is standalone (zero N3TX imports). Rules compose algebraically — and honestly, this is one of the coolest parts: `OWNER | ROLE('admin')`, `AUTHENTICATED & Where(status='published')`. Rules produce SQL WHERE clauses for list-level pushdown. Declared on models via `__access__` dict, on methods via `@expose_route(access=...)`.

### 🔗 References and Relationships

Your models don't exist in isolation — they talk to each other:

`Ref[T]` for pointer fields (stored as local ids or canonical distributed refs, serialized as resolvable refs). `list[T]` for owned local collections (stored as ordered local ids, hydrated as child objects). `Ref['self']` for self-referential nesting. For shared relationship data, prefer explicit link models; `ManyToMany[T]` is a legacy helper for existing shared-link cases.

## 📋 API Reference

Here's everything n3tx-core exports — your toolkit for building schema-driven apps:

| Export | Type | Purpose |
|--------|------|---------|
| `ProtoModel` | class | Base model — schema generation, serialization, FK rewriting, StorableMixin injection |
| `StorableMixin` | class | CRUD operations: `create`, `get`, `list`, `update`, `delete`, `save` |
| `ViewableMixin` | class | UI resource mixin with `name`, `desc`, `src`, `href` |
| `BaseUser` | class | Abstract user model with login, register, password hashing |
| `Ref` | type alias | `Ref[T]` — single FK reference; `Ref['self']` for self-ref |
| `AbstractStorage` | ABC | Storage interface: `create_table`, `create`, `get`, `list`, `update`, `delete` |
| `JSONStorage` | class | JSON file storage backend |
| `SQLiteStorage` | class | SQLite storage with connection pooling, WAL mode, JSON field handling, FK hydration |
| `FastAPIBackend` | class | FastAPI app builder with JWT middleware, CORS, SSR, static file mounting |
| `expose_route` | decorator | Mark a method as an API endpoint with route, methods, access, stream |
| `register_model` | function | Register a model with storage, create table, run migrations |
| `registered_models` | dict | Global registry: `{tablename: model_class}` |

### `ProtoModel`

The class you'll subclass for everything. Schema generation, serialization, the whole deal:

```python
class ProtoModel(PydanticBaseModel):
    id: int = Field(default=0)
    image: str = Field(default='')

    def model_response(self, **kwargs) -> dict: ...   # Enriched dict via dump pipeline
    @classmethod
    def schema(cls) -> dict: ...                       # Full JSON Schema via schema pipeline
    @classmethod
    def invalidate_schema_cache(cls): ...              # Clear cached schema (tests)
    @classmethod
    def referenced_json_schema(cls) -> dict: ...       # Schema for $defs inclusion
    @staticmethod
    def blueprint() -> dict: ...                       # All registered model schemas
```

### `StorableMixin` (injected when `__storable__ = True`)

You never import this directly — it gets injected into your model's class hierarchy when you set `__storable__ = True`. But here's what you get:

```python
class StorableMixin:
    @classmethod
    def create(cls, data) -> Any: ...
    @classmethod
    def get(cls, id: int, as_dict=False, populate=None) -> Any: ...
    @classmethod
    def list(cls, sql_filter=None, limit=None, offset=None, populate=None, ids=None): ...
    @classmethod
    def update(cls, id: int, data) -> Any: ...
    @classmethod
    def delete(cls, id: int): ...
    def save(self): ...
    @classmethod
    def set_storage(cls, storage): ...
```

`Model.update(id, data)` is patch-oriented, but generated direct and actor HTTP
`PUT` routes currently validate complete model bodies. HTTP callers must send
all required writable fields and preserve current defaulted collections/JSON
values; omitted defaults may be materialized and persisted. See
[storage update boundaries](docs/storage.md#update-boundary-contract).

### `BaseUser`

Need users? Subclass this and you're off to the races:

```python
class BaseUser(ProtoModel):
    # Fields: name, email, role, password_hash
    # Endpoints: POST /login, POST /register
    # Set __tablename__ and __abstract__ = False in subclass
```

## 📐 Patterns and Conventions

A few things worth knowing before you dive deeper:

1. **Always set `__tablename__`** on storable models. It determines the API path (`/{tablename}`) and DB table name. Omitting it causes schema `$id` to fall back to the lowercase class name.

2. **`model_dump()` for storage, `model_response()` for API.** `model_dump()` produces a plain dict. `model_response()` adds `$schema` and `$id` metadata via the dump pipeline. Never use `model_response()` data for storage writes.

3. **Register every storable model.** `list[T]` collections store child ids, so both parent and child models need storage-backed registration.

```python
register_model(Product, storage=db)
register_model(Comment, storage=db)
```

4. **Storable models require a storage backend.** Calling `register_model(M)` on a `__storable__ = True` model without passing `storage=` raises `ValueError`. Non-storable models can be registered without storage.

5. **The authorize package has zero N3TX imports.** Do not add N3TX-specific logic to `authorize/`. The boundary is enforced by design. The route layer bridges auth to models via `_resolve_user()`.

## 🏗️ Package Ecosystem

Here's how everything fits together — n3tx-core is the foundation everything else builds on:

```
n3tx (meta-package)
  |
  +-- n3tx-core  <-- THIS PACKAGE (foundation)
  |     Models, storage, auth, API routes, schema pipeline, JS runtime
  |
  +-- n3tx-actors  (depends on n3tx-core)
  |     Actor system, Matrix, TX messaging, NetworkAdapter
  |
  +-- n3tx-agents  (depends on n3tx-core, n3tx-actors)
  |     AgentMixin, AgentActor, tool discovery, LLM integration
  |
  +-- n3tx-ui  (depends on n3tx-core)
        Frontend components, extended UI widgets
```

## 📖 Deep Dives

Want to go deeper? Each of these docs covers a specific subsystem in detail:

| Topic | File | When to read |
|-------|------|--------------|
| Schema Pipeline | [docs/schema-pipeline.md](docs/schema-pipeline.md) | Extending schema generation, adding pipeline stages |
| Storage Layer | [docs/storage.md](docs/storage.md) | Custom storage backends, SQLite internals, JSON fields, FK hydration |
| Authorization | [docs/authorization.md](docs/authorization.md) | Access rules, ABAC patterns, custom resolvers, SQL pushdown |
| App Bootstrap | [docs/app-bootstrap.md](docs/app-bootstrap.md) | create_app, N3TXApp builder, routing modes, SSR, config |

---

Now go build something cool. The model is the app — you bring the idea, n3tx-core handles the rest. 🛠️
