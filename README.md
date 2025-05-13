---

# **PyBend Documentation**

## **Table of Contents**

1. [Introduction](#introduction)
2. [Features](#features)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Switching API Backends](#switching-api-backends)
7. [Switching Storage Backends](#switching-storage-backends)
8. [API Documentation](#api-documentation)
9. [Usage Examples](#usage-examples)
10. [Schema Endpoint Responses](#schema-endpoint-responses)
11. [Extending the Application](#extending-the-application)
12. [Why PyBend?](#why-pybend)
13. [Testing](#testing)

---

## **Introduction**

PyBend is a modular, extensible backend framework built with Python. It supports both **FastAPI** and **Flask** backends, dynamically switchable at runtime. It enables model-driven CRUD APIs, custom endpoints via decorators, and plug-and-play persistence with pluggable storage backends.

---

## **Features**

* ✅ FastAPI **and** Flask backend support
* ⚐ Adapter architecture to switch backends easily
* 🧠 Dynamic Model Registration + Schema Introspection
* ⚙️ Auto-generated CRUD + custom routes via `@expose_route`
* 📃 Integrated OpenAPI (Swagger) documentation
* 📄 Optional storage via SQLite or JSON
* 🔍 Fully typed with Pydantic
* ✅ Integrated testing with PyTest

---

## **Installation**

### Prerequisites

* Python 3.10+
* Docker & Docker Compose (optional)

### Clone the Repo

```bash
git clone https://github.com/<your_repo>.git
cd <your_repo>
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## **Configuration**

Use these environment variables or set directly in `main.py`:

```bash
BACKEND=fastapi        # or flask
STORAGE_BACKEND=sqlite # or json
```

To define storage:

```python
from storage.sqlite_storage import SQLiteStorage
from storage.json_storage import JSONStorage

storage_backend = SQLiteStorage("database.db")
# or
storage_backend = JSONStorage(directory="data")
```

Register models:

```python
from models.user_model import User
from models.product_model import Product
from utils.registrar import register_model

register_model(User, storage=storage_backend)
register_model(Product, storage=storage_backend)
```

---

## **Running the Application**

### Locally

```bash
python main.py
```

### With Uvicorn

```bash
uvicorn main:app --reload
```

### With Docker

```bash
docker-compose up --build
```

---

## **Switching API Backends**

PyBend uses an adapter pattern to switch between Flask and FastAPI:

```python
# In main.py
BACKEND = "flask"  # or "fastapi"
```

* FastAPI: `routes_fastapi.py`
* Flask: `routes_flask.py`
* Automatically registers routes and schema

---

## **Switching Storage Backends**

To change the storage backend:

```python
from storage.sqlite_storage import SQLiteStorage
from storage.json_storage import JSONStorage

storage_backend = SQLiteStorage("database.db")
# or
storage_backend = JSONStorage(directory="data")
```

Registered models will use the new backend if injected properly.

---

## **API Documentation**

* FastAPI: [http://localhost:8000/docs](http://localhost:8000/docs)
* Flask: [http://localhost:8000/apidocs/](http://localhost:8000/apidocs/)

---

## **Usage Examples**

### Create a User

```http
POST /users
Content-Type: application/json
{
  "name": "Alice",
  "email": "alice@example.com",
  "age": 30
}
```

### Login a User

```http
POST /users/login
{
  "email": "alice@example.com"
}
Response:
{
  "message": "Login successful"
}
```

### List Products

```http
GET /products/list
Response:
[
  {
    "id": 1,
    "name": "Product A",
    "price": 10.0,
    "description": "Description A"
  },
  {
    "id": 2,
    "name": "Product B",
    "price": 20.0,
    "description": "Description B"
  }
]
```

---

## **Schema Endpoint Responses**

### Product Schema

```http
GET /products/schema
Response:
{
  "title": "Product",
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "price": { "type": "number" },
    "description": { "type": "string" },
    "id": { "type": "integer" }
  },
  "required": ["name", "price"]
}
```

---

## **Extending the Application**

### Add New Model

1. Create a new class inheriting `ProtoModel`
2. Optionally set `storable = True`
3. Use `@expose_route` to define custom methods
4. Register with a storage backend

### Add New Storage Backend

1. Implement all abstract methods in `AbstractStorage`
2. Inject into models with `set_storage()`

---

## **Why PyBend?**

* 🔄 Unified data interface via model schema
* 🚀 Easy onboarding with FastAPI or Flask
* ⚖️ Consistent CRUD + custom endpoint structure
* ⚙️ Backend/storage agnostic
* 🔬 Designed for frontend-to-backend portability (UCP-ready!)

---

## **Testing**

Run all tests:

```bash
pytest
```

Tests include:

* API endpoints
* Schema generation
* Storage persistence logic

---

## **License**

MIT

## **Contact**

* Email: [you@example.com](mailto:you@example.com)
* GitHub: [yourusername/yourrepository](https://github.com/yourusername/yourrepository)

---
