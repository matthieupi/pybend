# **N3TX Documentation**

## **Table of Contents**

1. [Introduction](#introduction)
2. [Features](#features)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Switching API Backends](#switching-api-backends)
7. [Switching Storage Backends](#switching-storage-backends)
8. [Model Relationships](#model-relationships)
9. [API Documentation](#api-documentation)
10. [Usage Examples](#usage-examples)
11. [Schema Endpoint Responses](#schema-endpoint-responses)
12. [Schema-Driven Development](#schema-driven-development)
13. [Schema-Driven Architecture](#schema-driven-architecture)
14. [Extending the Application](#extending-the-application)
15. [Why N3TX?](#why-n3tx)
16. [Testing](#testing)

---

## **Introduction**

N3TX is a modular, extensible backend framework built with Python. It supports both **FastAPI** and **Flask** backends, dynamically switchable at runtime. It enables model-driven CRUD APIs, schema discovery, join model inference, and custom routes via decorators. Storage backends are pluggable with auto-migration support.

---

## **Features**

* ✅ FastAPI **and** Flask backend support
* ⚙️ Adapter architecture to switch between backends
* 🧠 Model auto-registration with dynamic route generation
* 🔄 Auto-generated CRUD + custom endpoints using `@expose_route`
* 🔗 Automatic Join Model Generation for relationships
* 🧩 ForeignKey support with schema resolution and FK hydration (href arrays)
* 📃 Integrated OpenAPI (Swagger) docs
* 🛢️ Pluggable storage backends (SQLite, JSON)
* 🚀 Schema introspection at runtime via `/ModelName`
* 🧪 Auto-migrating storage schema (SQLite)
* 📄 Schema includes full method metadata, UI hints, and $defs resolution
* 🔐 ABAC (Attribute-Based Access Control) with composable rules (`ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`)
* 🔁 Toggle endpoints (like/favorite) with join table lookups
* 📂 Collection routes for join models (`GET /products/comments`, `GET /products/likes`)
* 📄 Pagination with `?limit=N&offset=M` on list endpoints
* ✅ Typed end-to-end using Pydantic v2
* 🤖 LLM-powered agents via Pydantic AI — dynamic agents as data, any model method can be agentic
* 🧪 Built-in tests via PyTest + Playwright frontend tests

---

## **Installation**

### Prerequisites

* Python 3.10+
* Docker (optional)

### Install from Source (Development)

```bash
git clone https://github.com/<your_repo>.git
cd <your_repo>
pip install -e ".[dev]"     # editable install with dev dependencies
```

### Install from PyPI (when published)

```bash
pip install n3tx
```

### Project Structure

```
src/n3tx/
    core/           Framework (models, storage, API, auth, actors, app builder)
    core/agents/    LLM agent system (AgentMixin, AgentActor, tool discovery)
    example/        Demo application (product catalog with comments/likes)
    static/         Frontend components (JS/CSS web components)
```

---

## **Quickstart**

The fastest way to get a working app:

```python
from n3tx import create_app, ProtoModel, expose_route
from n3tx.core.models.base_user import BaseUser
from pydantic import Field

class User(BaseUser):
    __tablename__ = 'users'
    __abstract__ = False

class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str = Field(min_length=1)
    price: float = Field(gt=0)

app = create_app(models=[User, Product], storage="sqlite:///app.db")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
```

See `src/n3tx/example/` for a full working application with:
- Product catalog with comments and likes
- User authentication (login/register)
- Schema-driven frontend

## **Configuration**

Environment variables or `main.py` can control configuration:

```env
BACKEND=fastapi
STORAGE_BACKEND=sqlite
```

You can also configure programmatically:

```python
from n3tx.core.storage.sqlite_storage import SQLiteStorage
from n3tx.core.storage.json_storage import JSONStorage

storage_backend = SQLiteStorage("database.db")
# or
storage_backend = JSONStorage(directory="data")
```

Register your models with `create_app()` (recommended) or manually:

```python
from n3tx import create_app

# Recommended: one-liner
app = create_app(
    models=[User, Product],
    join_models=[(Product, Comment), (Comment, Like), (Product, Like)],
    storage="sqlite:///app.db",
)

# Or manual registration (Level 3):
from n3tx.core.utils.registrar import register_model
from n3tx.core.models.proto_model import generate_join_model

register_model(Product, storage=storage_backend)
register_model(User, storage=storage_backend)
register_model(generate_join_model(Product, Comment), storage=storage_backend)
register_model(generate_join_model(Comment, Like), storage=storage_backend)
register_model(generate_join_model(Product, Like), storage=storage_backend)
```

---

## **Running the Application**

```bash
# Run the example app:
cd src/n3tx/example && python3 main.py

# Or as a module:
python3 -m n3tx.example.main

# Or with uvicorn directly:
uvicorn n3tx.example.main:app --reload

# Or with Docker:
docker-compose up --build
```

---

## **Switching API Backends**

N3TX uses an adapter pattern. Set in `main.py` or environment:

```python
BACKEND = "fastapi"  # or "flask"
```

Routes are automatically registered via `register_routes()`.

---

## **Switching Storage Backends**

```python
from n3tx.core.storage.sqlite_storage import SQLiteStorage
from n3tx.core.storage.json_storage import JSONStorage

storage_backend = SQLiteStorage("db.sqlite")
register_model(MyModel, storage=storage_backend)
```

SQLite includes auto-migration of fields on boot.

---

## **Model Relationships**

N3TX provides dynamic join model generation and foreign key resolution between models:

* Use `ForeignKey[Model]` in your fields — injected automatically when `__storable__ = True`.
* N3TX generates join models via `generate_join_model(Product, Comment)`.
* Related objects are persisted and filtered via join tables.
* Foreign keys serialize to primitive types in storage but expose full schemas in OpenAPI.

Example:

```python
class Product(ProtoModel):
    __storable__ = True
    __tablename__ = 'products'
    comments: List[Comment]

class Comment(ProtoModel):
    __storable__ = True
    user_owner: User
```

Join model:

```python
register_model(generate_join_model(Product, Comment), storage=backend)
```

---

## **API Documentation**

* FastAPI: [http://localhost:8000/docs](http://localhost:8000/docs)
* Flask: [http://localhost:8000/apidocs/](http://localhost:8000/apidocs/)

---

## **Usage Examples**

### Create a User

```http
POST /users
{
  "name": "Alice",
  "email": "alice@example.com"
}
```

### Login a User

```http
POST /users/login
{
  "email": "alice@example.com"
}
```

### List Products

```http
GET /products/list
```

### Comment on a Product

```http
POST /products/1/comment
{
  "comment": {"name": "Nice product", "description": "Really liked this!"}
}
```

### Toggle Favorite on a Product

```http
POST /products/1/favorite
{}
```

Returns `{"action": "favorited"}` or `{"action": "unfavorited"}`.

### Toggle Like on a Comment

```http
POST /products/1/comments/3/like
{}
```

Returns `{"action": "liked"}` or `{"action": "unliked"}`.

### Reply to a Comment

```http
POST /products/1/comments/3/reply
{"text": "I agree, great product!"}
```

### List All Comments Across Products (Collection Route)

```http
GET /products/comments
```

---

## **Schema Endpoint Responses**

Each model is introspectable via:

```http
GET /Product
GET /Comment
```

Returns:

* JSON schema
* Referenced types via `$defs`
* Custom method metadata (`/comment`, `/login`, etc.)

---

## **Schema-Driven Development**

N3TX's core idea: **write a Python model, get a working full-stack application**. The model definition is the only thing a developer writes. Everything else — API, validation, storage, UI, permissions, navigation — is derived from the JSON Schema that model produces.

### The model is the app

A single model class encodes the entire application concern:

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __ui__ = {
        'field_order': ['name', 'price', 'description', 'comments', 'favorites'],
        'groups': {'main': ['name', 'description', 'price'], 'Social': ['comments', 'favorites']},
        'methods': {
            'comment': {'layout': 'inline', 'attach_to': 'comments', ...},
            'favorite': {'layout': 'button', 'icon': 'star', 'count_field': 'favorites', ...},
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
    def favorite(self, user: User = None) -> str:
        """Toggle favorite — add if not favorited, remove if already favorited."""
        ...
```

From this single definition, `ProtoModel.schema()` generates a JSON Schema that carries **everything the frontend needs**: field types, validation rules, UI rendering hints, access control policies, callable methods, and relationship structure.

### What gets generated automatically

| Concern | Generated from | No code required |
|---------|---------------|-----------------|
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
| Method action buttons | `schema.methods` | `<ntx-method>` renders them (fieldset, inline, or button layout) |
| Method UI hints | `__ui__.methods` (icon, layout, count_field) | Button-layout methods (like, favorite) render as icon+count pills |
| Toggle endpoints | `@expose_route` + join table logic | Like/favorite toggle via create/delete on join models |
| Collection routes | Join model `__tablename__` | `GET /products/comments`, `GET /products/likes` across all parents |
| Component tag resolution | `ui.renderer.item`, `ui.renderer.detail` | Router resolves on navigation |

### The workflow

1. Define or modify a Python model
2. Restart the server
3. Open the frontend — it fetches the schema, creates entity classes, renders everything
4. No frontend code changed. No routes added. No forms built. No permissions wired.

---

## **Schema-Driven Architecture**

The JSON Schema served at `GET /{ClassName}` is the **universal contract** between backend and frontend. It carries not just type information but the complete specification of how an entity behaves, renders, and is controlled.

### Schema anatomy

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

### Why this matters

**Adding a field** to a model automatically adds a DB column, includes it in API responses, generates a form input, and validates on both sides. **Changing `__access__`** propagates to the frontend: the edit button appears or disappears, list queries filter differently. **Adding `@expose_route`** creates an API endpoint and a clickable button in the UI. The schema carries intent, not just structure.

---

## **Extending the Application**

### Add a New Model

1. Subclass `ProtoModel`
2. Set `__storable__ = True` for persistence
3. Use `@expose_route()` for custom API endpoints
4. Register with `register_model(...)`

### Add Relationships

```python
register_model(generate_join_model(OwnerModel, SubModel))
```

### Add a Storage Backend

1. Implement `AbstractStorage` methods
2. Inject via `set_storage()`

---

## **Agents**

N3TX includes an LLM-powered agent system built on [Pydantic AI](https://ai.pydantic.dev/). The core idea: **every Actor with `@expose_route` methods is a tool collection, and an Agent is an Actor that reasons**.

### Dynamic Agents (primary path)

Agents are instances of `AgentActor` — configuration is data, not code:

```python
from n3tx import AgentActor

scanner = AgentActor(
    name="Grant Scanner",
    prompt="You find government grants...",
    tools=["grants", "web_tools"],       # actor addresses = tool sets
    llm="anthropic:claude-sonnet-4-5-20250929",
    constraints={"max_iterations": 30},
)

result = await scanner.run(task="Find grants about renewable energy")
```

Agents can be created via API (`POST /agents`), stored in the database, and triggered via `POST /agents/{id}/run`.

### Agentic Model Methods (secondary path)

Any model with `__agent__ = True` gets `agent_run()` injected. Methods can use LLM reasoning internally — callers don't need to know:

```python
class Product(ActorModel):
    __agent__ = True

    @expose_route('/create_from_text', methods=['POST'])
    async def create_from_text(self, text: str, tools: list = []) -> str:
        result = await self.agent_run(
            prompt="Parse freeform text into a Product.",
            tools=["products"] + tools,
            task=text,
        )
        return result['answer']
```

Tool calls route through Matrix as TX messages, preserving auth and interceptors. See [`src/n3tx/core/agents/README.md`](src/n3tx/core/agents/README.md) for full documentation.

---

## **Why N3TX?**

* 🧠 Self-discoverable data models and APIs
* 🔗 Schema-driven architecture
* 🧬 Foreign key resolution + join modeling built-in
* 🧱 Modular for switching backend/storage
* 📐 Fully typed runtime behavior with schema traceability
* 🔍 Frontend-ready API schema via OpenAPI and custom metadata

---

## **Testing**

### Framework Unit Tests

```bash
cd src/n3tx/core
pytest tests/unit/
```

### Integration Tests (Example App)

```bash
cd src/n3tx/core
pytest ../example/tests/
```

### Frontend (Jest)

```bash
cd src/n3tx/static
npm test
```

Tests include:

* CRUD API coverage
* Schema endpoint behavior
* Storage backend logic
* Custom method invocation
* Authorization and access control
* Social feature toggle actions (like/favorite)
* Reply creation with parent_id nesting
* Collection routes (`/products/comments`, `/products/likes`)
* Pagination
* Agent system (mixin injection, tool discovery, agent CRUD, LLM execution)
* Frontend component unit tests

---

## **License**

MIT

## **Contact**

* Email: [you@example.com](mailto:you@example.com)
* GitHub: [yourusername/yourrepository](https://github.com/yourusername/yourrepository)


---
