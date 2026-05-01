# N3TX

**N3TX** is a lightweight, declarative Python framework for building REST APIs with automatic CRUD operations, schema generation, and flexible storage backends. Define your data models once, and N3TX handles the routing, validation, database operations, and API documentation.

## Features

- **Declarative Model Definition** - Define models using Pydantic with automatic API generation
- **Automatic CRUD Operations** - GET, POST, PUT, DELETE endpoints generated automatically
- **Flexible Storage Backends** - SQLite, JSON, or implement your own
- **Foreign Key Support** - Type-safe relationships between models
- **Auto-Generated Documentation** - OpenAPI/Swagger compatible schemas
- **Custom Endpoints** - Easily add custom business logic with decorators
- **Multiple Backend Support** - FastAPI or Flask (with easy extensibility)
- **Auto-Migration** - Database schema updates automatically
- **JSON-LD Style Responses** - All responses include `$schema` and `$id` metadata for self-describing resources

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/n3tx.git
cd n3tx

# Install dependencies
pip install pydantic fastapi uvicorn sqlite3
```

### Basic Example

```python
# models/user_model.py
from models.proto_model import ProtoModel
from typing import ClassVar, Optional

class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    
    id: Optional[int] = None
    name: str
    email: str
    age: Optional[int] = None
```

```python
# main.py
from storage.sqlite_storage import SQLiteStorage
from utils.registrar import register_model
from api.backend import FastAPIBackend
import config

# Set up storage
storage = SQLiteStorage('database.db')

# Register your model
register_model(User, storage=storage)

# Create backend
backend = FastAPIBackend(
    name="My API",
    version="1.0.0",
    description="API built with N3TX"
)
backend.register_routes(registered_models)
app = backend.get_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

Run your API:

```bash
python main.py
```

Your API now has:
- `GET /users` - List all users
- `POST /users` - Create a user
- `GET /users/{id}` - Get a specific user
- `PUT /users/{id}` - Update a user
- `DELETE /users/{id}` - Delete a user
- `GET /User` - Get the JSON schema for the User model

All CRUD responses include `$schema` and `$id` metadata:

```json
{
  "$schema": "http://localhost:8000/User",
  "$id": "http://localhost:8000/users/1",
  "id": 1,
  "name": "Alice Johnson",
  "email": "alice@example.com",
  "age": 28
}
```

## Core Concepts

### Models

N3TX models inherit from `ProtoModel` and use class variables to configure behavior:

```python
class Product(ProtoModel):
    __storable__: ClassVar[bool] = True      # Enable storage/CRUD
    __tablename__: ClassVar[str] = 'products'  # Database table name
    
    id: Optional[int] = None
    name: str
    price: float
    description: str = ''
```

ProtoModel's Config sets `extra='allow'` so that metadata fields like `$schema` and `$id` survive FastAPI's response model validation.

### Response Metadata

All CRUD route handlers call `.model_response()` to include self-describing metadata in every response:

- `$schema` - URL pointing to this model's JSON Schema (e.g., `http://localhost:8000/Product`)
- `$id` - URL pointing to this specific resource instance (e.g., `http://localhost:8000/products/1`)

This enables clients to discover the schema for any resource directly from the response payload.

### Storage Backends

N3TX supports multiple storage backends:

#### SQLite Storage

```python
from storage.sqlite_storage import SQLiteStorage

storage = SQLiteStorage('database.db')
register_model(Product, storage=storage)
```

#### JSON Storage

```python
from storage.json_storage import JSONStorage

storage = JSONStorage(directory='data')
register_model(Product, storage=storage)
```

#### Custom Storage

Implement the `AbstractStorage` interface:

```python
from storage.abstract_storage import AbstractStorage

class MyStorage(AbstractStorage):
    def create_table(self, model_class): ...
    def create(self, model_class, data): ...
    def list(self, model_class): ...
    def get(self, model_class, id_, as_dict=False, **kwargs): ...
    def update(self, model_class, id_, data): ...
    def delete(self, model_class, id_): ...
```

### Foreign Keys

N3TX automatically handles relationships between models:

```python
from utils.typer import Ref

class Comment(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'comments'
    
    id: Optional[int] = None
    text: str
    user: Ref[User]  # Type-safe foreign key
```

When `__storable__` is True, N3TX automatically converts Pydantic model references to `Ref` types.

### Custom Endpoints

Add custom business logic with the `@expose_route` decorator:

```python
from utils.decorators import expose_route

class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    
    name: str
    email: str
    
    @staticmethod
    @expose_route('/login', methods=['POST'])
    def login(email: str, password: str) -> User:
        """Custom login endpoint"""
        users = User.list()
        return next((u for u in users if u.email == email), None)
```

This creates a `POST /users/login` endpoint automatically.

### Join Models (Many-to-Many)

N3TX can automatically generate join tables for many-to-many relationships:

```python
from models.proto_model import generate_join_model

# Product has many Comments
class Product(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'products'
    
    comments: Optional[List[Comment]] = []

# Generate join model
ProductComment = generate_join_model(Product, Comment)
register_model(ProductComment, storage=storage)
```

This creates a `products_comments` table with proper foreign keys.

## Architecture

N3TX follows a modular architecture with clear separation of concerns:

```
+---------------------------------------------------------+
|                   API Layer                              |
|  (FastAPI/Flask Backend)                                 |
|  - Route Registration                                    |
|  - Request/Response Handling (model_response())           |
+--------------------------+------------------------------+
                           |
+--------------------------v------------------------------+
|                Model Layer                               |
|  (ProtoModel + Mixins)                                   |
|  - Schema Generation ($schema, $id)                      |
|  - Validation (Pydantic)                                 |
|  - Business Logic                                        |
+--------------------------+------------------------------+
                           |
+--------------------------v------------------------------+
|              Storage Layer                                |
|  (StorableMixin + AbstractStorage)                       |
|  - CRUD Operations                                       |
|  - Data Persistence                                      |
|  - Auto-Migration                                        |
+---------------------------------------------------------+
```

### Key Components

- **ProtoModel**: Base model with schema generation, optional storage, and `model_response()` for metadata injection via the dump pipeline
- **StorableMixin**: Provides CRUD operations via dependency injection
- **AbstractStorage**: Interface for storage backends (SQLite, JSON, etc.)
- **Registrar**: Central registry for models and join tables
- **Backend Adapters**: FastAPI/Flask integration layer
- **Ref**: Type-safe foreign key wrapper with schema generation

## Configuration

Edit `config.py` to configure your application:

```python
# Backend framework
BACKEND = "fastapi"  # or "flask"

# API Settings
VERSION = "0.5.0"
HOST = "0.0.0.0"
PORT = 8000

# Database
SQLITE_DB_FILE = "n3tx.db"
```

## API Documentation

N3TX automatically generates OpenAPI-compatible schemas for all models and endpoints.

### Schema Endpoint

Each model exposes its schema at `GET /{ModelName}`:

```bash
curl http://localhost:8000/User
```

Response:
```json
{
  "$schema": "http://localhost:8000/Schema",
  "$id": "http://localhost:8000/User",
  "type": "object",
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string"},
    "email": {"type": "string"}
  },
  "methods": {
    "login": {
      "route": "/login",
      "methods": ["POST"],
      "parameters": {
        "email": {"type": "string"},
        "password": {"type": "string"}
      },
      "returns": {"$ref": "#/$defs/User"}
    }
  },
  "$defs": {
    "User": {
      "$id": "http://localhost:8000/User"
    }
  }
}
```

The `schema()` method adds `$schema` (pointing to `{API_URL}/Schema`) and `$id` (pointing to `{API_URL}/{ClassName}`) to the top-level schema dict, and `$id` to each `$defs` entry.

Storable entities keep their canonical `$id` on the table-name API path (for
example `/users/1`), even when read through the class-name mirror
`GET /User/1`. Class-name routes are additive: `GET /User` remains schema,
`GET /User/1` mirrors reads, and `GET /User/@...` is reserved for HTML/view
entrypoints.

### Generate Markdown Docs

N3TX includes a documentation generator:

```bash
python -m utils.generate_docs
```

This creates `/docs/{model_name}.md` files with complete API documentation.

## Advanced Usage

### Instance Methods on Models

```python
class Product(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'products'
    
    name: str
    price: float
    
    @expose_route('/discount', methods=['POST'])
    def apply_discount(self, percentage: float) -> Product:
        """Apply a discount to this product"""
        self.price = self.price * (1 - percentage / 100)
        self.save()
        return self
```

This creates `POST /products/{id}/discount` endpoint.

### Custom Validation

Use Pydantic's validation features:

```python
from pydantic import field_validator

class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'users'
    
    email: str
    
    @field_validator('email')
    @classmethod
    def lowercase_email(cls, v):
        return v.lower()
```

### Error Handling

N3TX includes automatic error handling with stack traces:

```python
from utils.erroring import get_traceback_info

try:
    # Your code
    pass
except Exception as e:
    trace_info = get_traceback_info(e)
    # Returns structured error with file, line, function, code
```

## Project Structure

```
n3tx/
├── api/
│   ├── backend.py              # Backend adapters (FastAPI/Flask)
│   └── routes_fastapi.py       # Route registration logic
├── models/
│   ├── proto_model.py          # Base model with schema generation
│   ├── storable_mixin.py       # CRUD operations mixin
│   ├── viewable_mixin.py       # UI view support
│   ├── user_model.py           # Example: User model
│   ├── product_model.py        # Example: Product model
│   └── comment_model.py        # Example: Comment model
├── storage/
│   ├── abstract_storage.py     # Storage interface
│   ├── sqlite_storage.py       # SQLite implementation
│   └── json_storage.py         # JSON file implementation
├── utils/
│   ├── decorators.py           # @expose_route decorator
│   ├── registrar.py            # Model registration
│   ├── typer.py                # Ref type wrapper
│   ├── introspection.py        # Schema introspection
│   ├── erroring.py             # Error handling utilities
│   └── generate_docs.py        # Documentation generator
├── config.py                   # Configuration
└── main.py                     # Application entry point
```

## Examples

### Complete CRUD Example

```python
# 1. Define model
class Article(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'articles'
    
    id: Optional[int] = None
    title: str
    content: str
    author: Ref[User]
    published: bool = False

# 2. Register model
storage = SQLiteStorage('blog.db')
register_model(Article, storage=storage)

# 3. Use the API
# POST /articles - Create article
# GET /articles - List all articles
# GET /articles/1 - Get article by ID (response includes $schema and $id)
# PUT /articles/1 - Update article
# DELETE /articles/1 - Delete article
```

### Nested Resources

```python
class Product(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'products'
    
    name: str
    reviews: Optional[List[Review]] = []

# Creates endpoints:
# POST /products/{parent_id}/reviews
# GET /products/{parent_id}/reviews
# GET /products/{parent_id}/reviews/{id}
```

## Development

### Running Tests

```bash
pytest tests/
```

### Running with Auto-Reload

```bash
python main.py
# Or with uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Generating Documentation

```bash
GENERATE_DOCS=true python main.py
```

## Troubleshooting

### Database Migration Issues

If you encounter migration errors:

```python
# In sqlite_storage.py, the migrate_table method automatically
# adds missing columns. Check logs for migration status.
```

### Foreign Key Serialization

Foreign keys are automatically serialized as integers:

```python
# This is handled automatically
product = Product.get(1)
# product.user will be an integer ID, not a User object
```

### Circular Imports

Use forward references:

```python
from __future__ import annotations

class User(ProtoModel):
    posts: Optional[List['Post']] = []

# At the end of the file
User.update_forward_refs()
```

## Roadmap

- [ ] PostgreSQL storage backend
- [ ] MongoDB storage backend
- [ ] GraphQL support
- [ ] WebSocket support
- [ ] Built-in authentication/authorization
- [ ] Async storage operations
- [ ] Query builder / filtering
- [ ] Pagination support
- [ ] Rate limiting
- [ ] Caching layer

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [Pydantic](https://pydantic-docs.helpmanual.io/) for data validation
- Supports [FastAPI](https://fastapi.tiangolo.com/) and [Flask](https://flask.palletsprojects.com/)
- Inspired by Django ORM and SQLAlchemy

## Support

- Email: support@n3tx.dev
- Issues: [GitHub Issues](https://github.com/yourusername/n3tx/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/n3tx/discussions)
