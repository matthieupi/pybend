# 🛠️ N3TX: Define a Model, Get a Full-Stack App

Welcome to N3TX! This isn't your typical API framework -- it's a schema-driven powerhouse where **one Python model** gives you a working API, a database, forms, permissions, and a frontend. No boilerplate. No busywork. You define the model, N3TX handles the rest.

Write a Python class, get CRUD endpoints, a JSON Schema, auth, a UI, and everything in between. Seriously.

---

## 📚 Table of Contents

1. [Features](#-features)
2. [Installation](#-installation)
3. [Quick Start](#-quick-start)
4. [Package Landscape](#-package-landscape)
5. [Schema-Driven Development](#-schema-driven-development)
6. [Schema Architecture](#-schema-architecture)
7. [Configuration](#-configuration)
8. [Running the Application](#-running-the-application)
9. [Model Relationships](#-model-relationships)
10. [Usage Examples](#-usage-examples)
11. [Agents](#-agents)
12. [Re-export Map](#-re-export-map)
13. [Extending the Application](#-extending-the-application)
14. [Testing](#-testing)
15. [Per-Package Documentation](#-per-package-documentation)
16. [License](#-license)

---

## ⚙️ Features

Here's what you get out of the box -- no assembly required:

- FastAPI and Flask backend support with adapter architecture
- Model auto-registration with dynamic CRUD + custom endpoint generation via `@expose_route`
- Automatic join model generation for relationships with FK hydration (href arrays)
- Integrated OpenAPI (Swagger) docs
- Pluggable storage backends (SQLite, JSON) with auto-migration
- Schema introspection at runtime via `GET /ModelName`
- ABAC access control with composable rules (`ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`)
- Toggle endpoints (like/favorite) with join table lookups
- Collection routes for join models (`GET /products/comments`)
- Pagination with `?limit=N&offset=M` on list endpoints
- Typed end-to-end using Pydantic v2
- Actor/Matrix/TX messaging system with multi-protocol adapters (HTTP, WS, MCP, ActivityPub)
- LLM-powered agents via Pydantic AI -- dynamic agents as data, any model method can be agentic
- Actor-backed file resources with metadata CRUD, byte stores, upload/download, and typed materialization
- Streaming SSE endpoints with progressive frontend rendering
- Schema-driven frontend Web Components (zero frontend code required)
- Built-in tests via PyTest + Playwright frontend tests

---

## 🚀 Installation

Getting started is quick. Pick your path.

### Prerequisites

- Python 3.10+
- Docker (optional)

### Install from PyPI

The simplest route -- one command, full stack:

```bash
pip install n3tx
```

### Install from Source (Development)

If you want to hack on N3TX itself:

```bash
# Automated (recommended)
./install-dev.sh

# Or manually (editable installs)
pip install -e packages/n3tx-core \
            -e packages/n3tx-actors \
            -e packages/n3tx-ui \
            -e packages/n3tx-agents \
            -e packages/n3tx-files \
            -e packages/n3tx
```

---

## ⚡ Quick Start

Here's your "zero to working app" moment. Define two models, call `create_app`, and you're live:

```python
from n3tx_core.app import create_app
from n3tx_meta import ProtoModel, BaseUser, expose_route, ListRef
from pydantic import Field

class User(BaseUser):
    __tablename__ = 'users'
    __abstract__ = False

class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)

    @expose_route('/discount', methods=['POST'])
    def discount(self, percent: float) -> str:
        self.price *= (1 - percent / 100)
        self.save()
        return f"New price: {self.price}"

# One line: CRUD API + JSON Schema + auth + frontend
app = create_app(models=[User, Product], storage="sqlite:///app.db")
```

Run with `uvicorn main:app --reload`. Visit `/Product` for the auto-generated JSON Schema, `/products` for data, or `/` for the schema-driven frontend.

That's it. You didn't write a single route, form, or migration. They just exist.

---

## 📦 Package Landscape

N3TX is split into focused packages with clean dependency boundaries. Use what you need, ignore what you don't:

```
n3tx (meta-package) <-- THIS PACKAGE
  |
  +-- n3tx-core        Foundation: models, storage, auth, API routes,
  |                    schema pipeline, JS runtime
  |
  +-- n3tx-actors      Actor/Matrix/TX messaging system, ActorModel
  |   (depends on      bridge, NetworkAdapter (HTTP, WS, MCP, AP)
  |    n3tx-core)
  |
  +-- n3tx-agents      AgentMixin, AgentActor, tool discovery,
  |   (depends on      LLM integration via pydantic-ai
  |    n3tx-core,
  |    n3tx-actors)
  |
  +-- n3tx-ui          Frontend Web Components, form generators,
  |   (depends on      widgets, themes (served as static assets)
  |    n3tx-core)
  |
  +-- n3tx-files       File metadata model, byte stores, upload/download,
      (depends on      typed File materialization
       n3tx-core,
       n3tx-actors)
```

### When to use which package

Not sure what you need? This table has you covered:

| Goal | Package | Key exports |
|------|---------|-------------|
| Define models, storage, CRUD APIs | `n3tx-core` | `ProtoModel`, `BaseUser`, `SQLiteStorage`, `expose_route`, `create_app` |
| Add actor messaging and routing | `n3tx-actors` | `Actor`, `Matrix`, `TX`, `ActorProxy`, `ActorModel` |
| Add LLM-powered agent reasoning | `n3tx-agents` | `AgentMixin`, `AgentActor`, `AgentTool`, `discover_tools` |
| Serve schema-driven frontend | `n3tx-ui` | Static assets (auto-discovered by the backend) |
| Add file metadata and byte storage | `n3tx-files` | `File`, `FileStore`, `LocalFileStore`, `configure_file_store` |
| Get everything at once | `n3tx` | Re-exports all of the above |

### Three bootstrapping levels

You choose how much control you want. All three produce identical API endpoints:

```python
# Level 1 -- One-liner (ProtoModel + direct routes)
app = create_app(models=[Product, User], storage="sqlite:///app.db")

# Level 2 -- Builder (chainable configuration)
from n3tx_core.app import N3TXApp
pb = N3TXApp(storage="sqlite:///app.db")
pb.model(Product).model(User).join(Product, Comment)
app = pb.build()

# Level 3 -- Actor routing (full messaging via Matrix)
app = create_app(models=[Product], storage="sqlite:///app.db", routing='actor')
```

Level 3 adds TX-based messaging and two-tier authorization on top of the same endpoints.

---

## 🧠 Schema-Driven Development

This is the big idea. Your Python model **is** your application. Everything else is derived.

A single model class encodes the entire application concern:

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __ui__ = {
        'field_order': ['name', 'price', 'description', 'comments', 'favorites'],
        'groups': {'main': ['name', 'description', 'price'], 'Social': ['comments', 'favorites']},
        'methods': {
            'comment': {'layout': 'inline', 'attach_to': 'comments'},
            'favorite': {'layout': 'button', 'icon': 'star', 'count_field': 'favorites'},
        },
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
    favorites: ListRef[Like] = Field(default=[], description="Users who favorited this product")

    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment, user: User = None) -> str: ...

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> str: ...
```

From this definition, `ProtoModel.schema()` generates a JSON Schema carrying everything the frontend needs. No glue code. No wiring. It just works.

### What gets generated automatically

Here's the fun part -- you wrote one class, and you got all of this for free:

| Concern | Generated from | How |
|---------|---------------|-----|
| CRUD API endpoints | `__tablename__`, model fields | Routes auto-registered |
| JSON Schema | Field types, validators, `json_schema_extra` | Pydantic generates it |
| DB table + migrations | `__storable__`, field annotations | SQLite auto-migrates |
| FK hydration (href arrays) | `ListRef[T]` fields | Storage resolves on read |
| Access control (backend) | `__access__`, `@expose_route(access=...)` | Middleware enforces |
| Access control (frontend) | `access` in schema | UI hides/shows controls |
| Frontend entity classes | Schema properties, methods | DynamicClass created at runtime |
| Form rendering | `properties`, `ui.widget`, `ui.placeholder` | Form generator reads schema |
| Field ordering + grouping | `ui.field_order`, `ui.groups` | Fieldsets rendered automatically |
| Edit/delete button visibility | `access.update`, `access.delete` | Permissions checked from schema |
| Method action buttons | `schema.methods` | `<ntx-method>` renders them |
| Toggle endpoints | `@expose_route` + join table logic | Like/favorite via join models |
| Collection routes | Join model `__tablename__` | `GET /products/comments` across all parents |
| Component tag resolution | `ui.renderer.item`, `ui.renderer.detail` | Router resolves on navigation |

### The workflow

Your daily loop looks like this:

1. Define or modify a Python model
2. Restart the server
3. Open the frontend -- it fetches the schema, creates entity classes, renders everything
4. No frontend code changed. No routes added. No forms built. No permissions wired.

Add a field? It shows up everywhere. Change permissions? The UI adapts. Add `@expose_route`? A button appears. You stay in Python, the framework handles the rest.

---

## 🗺️ Schema Architecture

The JSON Schema served at `GET /{ClassName}` is the universal contract between your backend and frontend. It carries not just types, but the complete specification of how an entity behaves, renders, and is controlled.

```
GET /Product -> JSON Schema
|-- $schema         -> meta-schema URL
|-- $id             -> this schema's URL (http://localhost:5000/Product)
|-- __name__        -> "Product" (class name)
|-- __tablename__   -> "products" (API collection path)
|-- properties      -> field definitions
|   +-- each field:
|       |-- type, format, validation constraints (Pydantic standard)
|       |-- ui.widget       -> rendering hint (currency, textarea, ...)
|       |-- ui.placeholder  -> input placeholder text
|       |-- ui.display      -> false to hide from UI
|       +-- access          -> field-level permission rules
|-- ui              -> model-level UI configuration
|   |-- field_order -> render fields in this sequence
|   |-- groups      -> group fields into fieldsets
|   +-- renderer    -> { item, list, detail } component tags
|-- access          -> model-level ABAC rules (serialized to JSON)
|-- methods         -> callable endpoints with signatures, access rules, and UI hints
|-- $defs           -> nested/related model schemas (each with $id, methods, ui, access)
+-- required        -> required field names
```

### How it flows through the stack

Here's the full journey, from Python class to rendered UI:

```
1. Model Definition (Python)
   Product(ProtoModel) with fields, __ui__, __access__, @expose_route
                    |
2. Schema Generation (Backend)
   ProtoModel.schema() -> Pydantic JSON Schema + methods + access + ui + $defs
                    |
3. Schema Endpoint
   GET /Product -> JSON response (public, no auth required)
                    |
4. Frontend Bootstrap
   N3TX.SCHEMA(data) -> prototype() -> DynamicClass
   |  Creates typed class with getters, setters, callable methods
   |  Registers nested $defs as additional DynamicClasses
                    |
5. Component Rendering
   |  form.js reads schema.properties -> builds form HTML
   |  Permissions.js reads schema.access -> shows/hides controls
   |  <ntx-method> reads schema.methods -> renders action buttons
   |  ntx-router reads schema.ui.renderer -> resolves navigation targets
                    |
6. Entity Responses
   model_response() injects $schema + $id per record (via proto_dump pipeline)
   |  Every entity is self-describing and independently resolvable
   |  Collection fields return href arrays for lazy resolution
```

---

## 🔧 Configuration

You can configure N3TX through environment variables or programmatically. Your call.

Environment variables:

```env
BACKEND=fastapi
STORAGE_BACKEND=sqlite
```

Programmatic configuration:

```python
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.storage.json_storage import JSONStorage

storage_backend = SQLiteStorage("database.db")
# or
storage_backend = JSONStorage(directory="data")
```

Register models with `create_app()` (recommended) or go manual if you need full control:

```python
# Recommended: one-liner
app = create_app(
    models=[User, Product],
    join_models=[(Product, Comment), (Comment, Like), (Product, Like)],
    storage="sqlite:///app.db",
)

# Or manual registration (Level 3):
from n3tx_core import register_model, generate_join_model

register_model(Product, storage=storage_backend)
register_model(User, storage=storage_backend)
register_model(generate_join_model(Product, Comment), storage=storage_backend)
```

---

## ▶️ Running the Application

Pick your favorite way to start things up:

```bash
# Run the example app
cd src/n3tx/example && python3 main.py

# Or as a module
python3 -m n3tx.example.main

# Or with uvicorn directly
uvicorn n3tx.example.main:app --reload

# Or with Docker
docker-compose up --build
```

API documentation is available at:
- FastAPI: `http://localhost:5000/docs`
- Flask: `http://localhost:5000/apidocs/`

---

## 🔗 Model Relationships

N3TX makes relationships between models effortless. Define the link, register the join model, and you're done:

- `ListRef[T]` for collection fields (stored in join tables, serialized as href arrays)
- `Ref[T]` for single FK fields (stored as int, serialized as href URL)
- `generate_join_model(Parent, Child)` creates the bridge model automatically

```python
class Product(ProtoModel):
    __storable__ = True
    __tablename__ = 'products'
    comments: ListRef[Comment] = Field(default=[])

class Comment(ProtoModel):
    __storable__ = True
    __tablename__ = 'comments'
    text: str = Field(min_length=1)

# Register the join model
register_model(generate_join_model(Product, Comment), storage=backend)
```

That's it -- `GET /products/1` now returns comments as href arrays, and `GET /products/comments` gives you a collection route across all products.

---

## 📡 Usage Examples

Here's a taste of what your API looks like once models are registered:

```http
POST /users                              # Create a user
POST /users/login                        # Login (returns JWT token)
GET  /products                           # List products (paginated)
GET  /products/1                         # Get product by ID
POST /products                           # Create product (auth required)
POST /products/1/comment                 # Comment on product
POST /products/1/favorite                # Toggle favorite
POST /products/1/comments/3/like         # Toggle like on comment
POST /products/1/comments/3/reply        # Reply to comment
GET  /products/comments                  # Collection route: all comments across products
GET  /Product                            # Schema endpoint (no auth)
```

Toggle endpoints return `{"action": "favorited"}` or `{"action": "unfavorited"}`.

Pagination: `GET /products?limit=20&offset=0` returns `{data: [...], meta: {total, limit, offset, has_more}}`.

---

## 🤖 Agents

N3TX ships with an LLM-powered agent system built on [Pydantic AI](https://ai.pydantic.dev/). The idea is simple: every Actor with `@expose_route` methods is a tool collection, and an Agent is an Actor that reasons.

### Dynamic Agents (primary path)

Agents are instances of `AgentActor` -- configuration is data, not code. Create them in Python, via API, or store them in your database:

```python
from n3tx_agents import AgentActor

scanner = AgentActor(
    name="Grant Scanner",
    prompt="You find government grants...",
    tools=["grants", "web_tools"],
    llm="anthropic:claude-sonnet-4-5-20250929",
    constraints={"max_iterations": 30},
)

result = await scanner.agentic(task="Find grants about renewable energy")
```

Agents can be created via API (`POST /agents`), stored in the database, and triggered via `POST /agents/{id}/agentic`.

### Agentic Model Methods (secondary path)

Any model with `__agent__ = True` gains LLM reasoning capabilities. It's one flag and your model can think:

```python
class Product(ActorModel):
    __agent__ = True

# Class-level: reasons about the schema
result = await Product.agentic(task='What fields does Product have?')

# Instance-level: reasons about schema + this specific record
product = Product.get(1)
result = await product.agentic(task='Is this product priced competitively?')

# Streaming
async for chunk in product.agentic_stream(task='Describe this product'):
    print(chunk['data'], end='', flush=True)
```

Tool calls route through Matrix as TX messages, preserving auth and interceptors. It's agents all the way down.

---

## 🗃️ Re-export Map

The meta-package's `n3tx_meta` module re-exports from all sub-packages via star-import, so you can grab most things from one place:

```python
from n3tx_core import *      # always
from n3tx_actors import *    # always
from n3tx_files import *     # always
from n3tx_agents import *    # optional (skipped if pydantic-ai not installed)
```

### Directly available via `from n3tx_meta import ...`

| Export | Source | Type | Purpose |
|--------|--------|------|---------|
| `ProtoModel` | n3tx-core | class | Base model class, schema pipeline, dump pipeline |
| `BaseUser` | n3tx-core | class | User model with auth (login, register, JWT) |
| `StorableMixin` | n3tx-core | class | Injected when `__storable__ = True` (save/get/list/delete) |
| `ViewableMixin` | n3tx-core | class | View count tracking mixin |
| `ListRef` | n3tx-core | type | FK reference type (`ListRef[Comment]`) |
| `Ref` | n3tx-core | type | Single FK reference type |
| `generate_join_model` | n3tx-core | function | Create join table model from parent/child pair |
| `expose_route` | n3tx-core | decorator | Declare custom API endpoints on models |
| `register_model` | n3tx-core | function | Register model with storage and route generation |
| `registered_models` | n3tx-core | dict | Global registry of all registered models |
| `AbstractStorage` | n3tx-core | class | Storage backend interface |
| `SQLiteStorage` | n3tx-core | class | SQLite storage with auto-migration |
| `JSONStorage` | n3tx-core | class | JSON file storage backend |
| `FastAPIBackend` | n3tx-core | class | FastAPI application wrapper |
| `TX` | n3tx-actors | dataclass | Message envelope (name, source, target, data, meta) |
| `Actor` | n3tx-actors | class | Base actor with inbox/handler/send/register/spawn |
| `Matrix` | n3tx-actors | class | Root actor and message router |
| `matrix` | n3tx-actors | instance | Module-level Matrix singleton |
| `ActorProxy` | n3tx-actors | class | Actor interface wrapper (no inheritance required) |
| `File` | n3tx-files | class | Actor-backed file metadata model with byte-store methods |
| `FileStore` | n3tx-files | protocol | Byte storage provider contract |
| `FileStat` | n3tx-files | dataclass | Provider byte metadata such as size, checksum, and MIME type |
| `LocalFileStore` | n3tx-files | class | Local filesystem byte provider |
| `configure_file_store` | n3tx-files | function | Set the process-wide file byte provider |
| `get_file_store` | n3tx-files | function | Resolve the active file byte provider |
| `AgentMixin` | n3tx-agents | class | Injected via `__agent__ = True` (ctx/tools/agentic/run) |
| `AgentActor` | n3tx-agents | class | Concrete agent model (config in DB fields) |
| `AgentTool` | n3tx-agents | class | Tool registration model |
| `AgentDeps` | n3tx-agents | dataclass | Dependency injection for pydantic-ai RunContext |
| `ToolSpec` | n3tx-agents | dataclass | Specification for a discovered tool |
| `discover_tools` | n3tx-agents | function | Build tool set from actor addresses |
| `make_tool` | n3tx-agents | function | Create a pydantic-ai tool from a ToolSpec |

### Requires sub-package import

These aren't star-exported, so you'll need to import them from the sub-package directly:

```python
from n3tx_core.app import create_app, N3TXApp
from n3tx_core import config
from n3tx_core import authorize
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.widgets import CurrencyField, TextareaField, UrlField, DateField
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.api.network_api import NetworkAPI
```

---

## 🛠️ Extending the Application

N3TX is built to be extended. Here's how you grow your app.

### Add a New Model

1. Subclass `ProtoModel` (or `ActorModel` for actor capabilities)
2. Set `__storable__ = True` for persistence
3. Use `@expose_route()` for custom API endpoints
4. Register with `register_model(...)` or pass to `create_app(models=[...])`

### Add Relationships

```python
register_model(generate_join_model(OwnerModel, SubModel), storage=backend)
```

### Add a Storage Backend

1. Implement `AbstractStorage` methods (`create_table`, `create`, `get`, `list`, `update`, `delete`)
2. Inject via `set_storage()` or pass to `register_model()`

---

## 🧪 Testing

N3TX comes with a thorough test suite. Run what you need:

```bash
# Framework unit tests
cd packages/n3tx-core && python3 -m pytest src/n3tx_core/tests/unit/

# Integration tests (Level 1/2 direct routes)
python3 -m pytest example_api/tests/

# Integration tests (Level 3 actor routing)
python3 -m pytest example_actor/tests/

# Integration tests (agents/grants app)
python3 -m pytest example_grants/tests/

# Frontend tests
cd src/n3tx/static && npm test
```

Test coverage includes: CRUD APIs, schema endpoints, storage backends, custom methods, authorization, social features (like/favorite/toggle), pagination, collection routes, agent system (mixin, tool discovery, CRUD, LLM execution), and frontend components.

---

## 📚 Per-Package Documentation

Each sub-package has its own README with API reference, patterns, and deep-dive links:

| Package | README | Focus |
|---------|--------|-------|
| n3tx-core | [packages/n3tx-core/README.md](packages/n3tx-core/README.md) | Models, storage, schema pipeline, auth, app bootstrap |
| n3tx-actors | [packages/n3tx-actors/README.md](packages/n3tx-actors/README.md) | Actor/Matrix/TX, ActorModel, interceptors, network adapters |
| n3tx-agents | [packages/n3tx-agents/README.md](packages/n3tx-agents/README.md) | AgentMixin, AgentActor, tool discovery, LLM integration |
| n3tx-ui | [packages/n3tx-ui/README.md](packages/n3tx-ui/README.md) | Web Components, form generators, widgets, themes |
| n3tx-files | [packages/n3tx-files/README.md](packages/n3tx-files/README.md) | File metadata, byte stores, upload/download, typed materialization |

For project-level architecture, conventions, and development workflow, see [CLAUDE.md](CLAUDE.md) at the repository root.

---

## 📜 License

MIT

---

Happy building! 🛠️
