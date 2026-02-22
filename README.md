# **PyBend Documentation**

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
15. [Why PyBend?](#why-pybend)
16. [Testing](#testing)

---

## **Introduction**

PyBend is a modular, extensible backend framework built with Python. It supports both **FastAPI** and **Flask** backends, dynamically switchable at runtime. It enables model-driven CRUD APIs, schema discovery, join model inference, and custom routes via decorators. Storage backends are pluggable with auto-migration support.

---

## **Features**

* ✅ FastAPI **and** Flask backend support
* ⚙️ Adapter architecture to switch between backends
* 🧠 Model auto-registration with dynamic route generation
* 🔄 Auto-generated CRUD + custom endpoints using `@expose_route`
* 🔗 Automatic Join Model Generation for relationships
* 🧩 ForeignKey support with schema resolution
* 📃 Integrated OpenAPI (Swagger) docs
* 🛢️ Pluggable storage backends (SQLite, JSON)
* 🚀 Schema introspection at runtime via `/ModelName`
* 🧪 Auto-migrating storage schema (SQLite)
* 📄 Schema includes full method metadata and $defs resolution
* ✅ Typed end-to-end using Pydantic v2
* 🧪 Built-in tests via PyTest

---

## **Installation**

### Prerequisites

* Python 3.10+
* Docker (optional)

### Clone and Install

```bash
git clone https://github.com/<your_repo>.git
cd <your_repo>
pip install -r requirements.txt
```

---

## **Configuration**

Environment variables or `main.py` can control configuration:

```env
BACKEND=fastapi
STORAGE_BACKEND=sqlite
```

You can also configure programmatically:

```python
from storage.sqlite_storage import SQLiteStorage
from storage.json_storage import JSONStorage

storage_backend = SQLiteStorage("database.db")
# or
storage_backend = JSONStorage(directory="data")
```

Register your models with:

```python
from models.product_model import Product
from models.user_model import User
from models.comment_model import Comment
from utils.registrar import register_model
from models.proto_model import generate_join_model

register_model(Product, storage=storage_backend)
register_model(User, storage=storage_backend)
register_model(generate_join_model(Product, Comment), storage=storage_backend)
```

---

## **Running the Application**

```bash
python main.py
# or
uvicorn main:app --reload
# or
docker-compose up --build
```

---

## **Switching API Backends**

PyBend uses an adapter pattern. Set in `main.py` or environment:

```python
BACKEND = "fastapi"  # or "flask"
```

Routes are automatically registered via `register_routes()`.

---

## **Switching Storage Backends**

```python
from storage.sqlite_storage import SQLiteStorage
from storage.json_storage import JSONStorage

storage_backend = SQLiteStorage("db.sqlite")
register_model(MyModel, storage=storage_backend)
```

SQLite includes auto-migration of fields on boot.

---

## **Model Relationships**

PyBend provides dynamic join model generation and foreign key resolution between models:

* Use `ForeignKey[Model]` in your fields — injected automatically when `__storable__ = True`.
* PyBend generates join models via `generate_join_model(Product, Comment)`.
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
  "name": "Nice product",
  "description": "Really liked this!"
}
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

PyBend's core idea: **write a Python model, get a working full-stack application**. The model definition is the only thing a developer writes. Everything else — API, validation, storage, UI, permissions, navigation — is derived from the JSON Schema that model produces.

### The model is the app

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
| Method action buttons | `schema.methods` | `<ntt-method>` renders them |
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
|-- methods         -> callable endpoints with signatures and access rules
|-- $defs           -> nested/related model schemas (each with their own $id)
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
   NTT.SCHEMA(data) -> prototype() -> DynamicClass
   |  Creates typed class with getters, setters, callable methods
   |  Registers nested $defs as additional DynamicClasses
                    |
5. Component Rendering
   |  form.js reads schema.properties -> builds form HTML
   |  Permissions.js reads schema.access -> shows/hides controls
   |  <ntt-method> reads schema.methods -> renders action buttons
   |  ntt-router reads schema.ui.renderer -> resolves navigation targets
                    |
6. Entity Responses
   model_dump(response=True) injects $schema + $id per record
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

## **Why PyBend?**

* 🧠 Self-discoverable data models and APIs
* 🔗 Schema-driven architecture
* 🧬 Foreign key resolution + join modeling built-in
* 🧱 Modular for switching backend/storage
* 📐 Fully typed runtime behavior with schema traceability
* 🔍 Frontend-ready API schema via OpenAPI and custom metadata

---

## **Testing**

Run with:

```bash
pytest
```

Tests include:

* CRUD API coverage
* Schema endpoint behavior
* Storage backend logic
* Custom method invocation

---

## **License**

MIT

## **Contact**

* Email: [you@example.com](mailto:you@example.com)
* GitHub: [yourusername/yourrepository](https://github.com/yourusername/yourrepository)


---

Let me know if you'd like this committed to your project file directly or exported elsewhere.
