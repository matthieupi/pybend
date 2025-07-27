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
12. [Extending the Application](#extending-the-application)
13. [Why PyBend?](#why-pybend)
14. [Testing](#testing)

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
