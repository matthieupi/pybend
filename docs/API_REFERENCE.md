# N3TX API Reference

Complete reference for all N3TX classes, methods, and decorators.

## Table of Contents

- [Models](#models)
  - [ProtoModel](#protomodel)
  - [StorableMixin](#storablemixin)
  - [ViewableMixin](#viewablemixin)
- [Storage](#storage)
  - [AbstractStorage](#abstractstorage)
  - [SQLiteStorage](#sqlitestorage)
  - [JSONStorage](#jsonstorage)
- [Types](#types)
  - [Ref](#ref)
- [Decorators](#decorators)
  - [@expose_route](#expose_route)
- [Agents](#agents)
  - [AgentMixin](#agentmixin)
  - [AgentActor](#agentactor)
  - [AgentDeps](#agentdeps)
  - [ToolSpec](#toolspec)
- [Backends](#backends)
  - [FastAPIBackend](#fastapibackend)
  - [FlaskBackend](#flaskbackend)
- [Utilities](#utilities)

---

## Models

### ProtoModel

Base class for all N3TX models. Provides schema generation, validation, and optional storage.

**Module**: `models.proto_model`

#### Config

ProtoModel sets `extra='allow'` in its Pydantic Config. This allows extra fields like `$schema` and `$id` to be included in serialized output without being rejected by FastAPI's response model validation.

#### Class Variables

```python
class MyModel(ProtoModel):
    __storable__: ClassVar[bool] = True        # Enable CRUD operations
    __tablename__: ClassVar[str] = 'my_models' # Database table name
```

#### Class Methods

##### `schema() -> Dict[str, Any]`

Returns the complete JSON schema for the model via the composable schema pipeline (`proto_schema.run_pipeline(cls)`). The pipeline consists of 8 stages: `base`, `strip_hidden`, `methods`, `agent`, `defs`, `access`, `ui`, `metadata`. Extensions can insert additional stages via `@schema_extension`.

The schema output includes:
- `$schema` at the top level, pointing to `{API_URL}/Schema`
- `$id` at the top level, pointing to `{API_URL}/{ClassName}`
- `$id` on each entry in `$defs`, pointing to `{API_URL}/{DefClassName}`

**Returns**: Dictionary with OpenAPI-compatible schema

**Example**:
```python
schema = User.schema()
# {
#   "$schema": "http://localhost:8000/Schema",
#   "$id": "http://localhost:8000/User",
#   "type": "object",
#   "properties": {...},
#   "methods": {...},
#   "$defs": {
#     "User": {
#       "$id": "http://localhost:8000/User",
#       ...
#     }
#   }
# }
```

##### `referenced_json_schema() -> Dict[str, Any]`

Returns a schema suitable for inclusion in `$defs`. Resolves Ref fields to `$ref` pointers.

**Returns**: Schema dictionary without circular references

##### `blueprint() -> Dict[str, Any]`

Static method that returns schemas for all registered models.

**Returns**: Dictionary mapping model names to their schemas

**Example**:
```python
blueprint = ProtoModel.blueprint()
# {
#   "users": {...},
#   "products": {...}
# }
```

#### Instance Methods

##### `__init__(**kwargs)`

Initializes a model instance. If `__storable__` is True and only `id` is provided, fetches from storage.

**Parameters**:
- `**kwargs`: Field values

**Example**:
```python
# Create new instance
user = User(name="Alice", email="alice@example.com")

# Load from storage (lazy loading)
user = User(id=1)  # Fetches from database
```

##### `model_dump(**kwargs) -> Dict[str, Any]`

Serializes the model to a plain dictionary (Pydantic standard). Used for storage operations. Does NOT include `$schema` or `$id` metadata.

**Parameters**:
- `**kwargs`: Keyword arguments passed to Pydantic's `model_dump()`

**Returns**: Dictionary of field values.

##### `model_response(**kwargs) -> Dict[str, Any]`

Serializes the model through the composable dump pipeline (`proto_dump`). Used for HTTP API responses.

Runs `proto_dump.run_pipeline(self)` with stages:
1. `base` -- plain Pydantic `model_dump()`
2. `response` -- injects `$schema` and `$id` metadata

Extensions can add stages via `@dump_extension` (e.g., federation, MCP).

**Parameters**:
- `**kwargs`: Passed to the base stage

**Returns**: Dictionary with `$schema` and `$id` prepended, followed by field values.

**Example**:
```python
product = Product.get(1)

# Plain dump (for storage, no metadata)
product.model_dump()
# {"id": 1, "name": "Laptop", "price": 999.99, ...}

# Response dump (for HTTP, with metadata)
product.model_response()
# {
#   "$schema": "http://localhost:8000/Product",
#   "$id": "http://localhost:8000/products/1",
#   "id": 1,
#   "name": "Laptop",
#   "price": 999.99,
#   ...
# }
```

---

### StorableMixin

Provides CRUD operations through dependency injection. Automatically added to models with `__storable__ = True`.

**Module**: `models.storable_mixin`

#### Class Variables

```python
__pk__: ClassVar[str] = 'id'  # Primary key field name
__tablename__: ClassVar[str]   # Required: table name
storage: ClassVar[AbstractStorage] = None  # Injected storage backend
```

#### Class Methods

##### `set_storage(storage: AbstractStorage)`

Injects the storage backend into the model.

**Parameters**:
- `storage`: Instance of AbstractStorage implementation

**Example**:
```python
storage = SQLiteStorage('database.db')
User.set_storage(storage)
```

##### `create_table()`

Delegates table creation to the storage backend.

**Example**:
```python
User.create_table()
```

##### `create(data: Union[BaseModel, Dict]) -> Any`

Creates a new record in storage.

**Parameters**:
- `data`: Model instance or dictionary

**Returns**: Created model instance with ID assigned

**Example**:
```python
user = User.create(User(name="Alice", email="alice@example.com"))
# or
user = User.create({"name": "Alice", "email": "alice@example.com"})
```

##### `list() -> List[Any]`

Retrieves all records from storage.

**Returns**: List of model instances

**Example**:
```python
all_users = User.list()
```

##### `get(id: int, as_dict: bool = False) -> Any`

Retrieves a single record by ID.

**Parameters**:
- `id`: Primary key value
- `as_dict`: If True, return dictionary instead of model instance

**Returns**: Model instance or dictionary, or None if not found

**Example**:
```python
user = User.get(1)
user_dict = User.get(1, as_dict=True)
```

##### `update(id: int, data: Union[BaseModel, Dict]) -> Any`

Updates an existing record.

**Parameters**:
- `id`: Primary key value
- `data`: Model instance or dictionary with fields to update

**Returns**: Updated model instance

**Example**:
```python
User.update(1, {"email": "newemail@example.com"})
# or
User.update(1, User(email="newemail@example.com"))
```

##### `delete(id: int)`

Deletes a record by ID.

**Parameters**:
- `id`: Primary key value

**Example**:
```python
User.delete(1)
```

#### Instance Methods

##### `save() -> Any`

Saves the current instance. Creates if no ID, updates if ID exists.

**Returns**: Saved model instance

**Example**:
```python
user = User(name="Alice", email="alice@example.com")
user = user.save()  # Creates new record

user.email = "alice.new@example.com"
user.save()  # Updates existing record
```

---

### ViewableMixin

Provides UI view support for models.

**Module**: `models.viewable_mixin`

#### Fields

```python
name: str  # Display name
desc: str  # Description
src: str   # Path to resource's inbox for callbacks
```

#### Class Variables

```python
href: ClassVar[str]  # Automatically set to /{modelname}
```

#### Class Methods

##### `view() -> str`

Returns the HTML view component URL for this resource.

**Returns**: URL string

**Decorator**: Automatically exposed as `GET /{model}/view`

**Example**:
```python
url = Product.view()  # Returns "/product/view"
```

---

## Storage

### AbstractStorage

Abstract base class for storage backends.

**Module**: `storage.abstract_storage`

#### Abstract Methods

All methods must be implemented by subclasses.

##### `create_table(model_class: Type[Any])`

Creates the storage structure (table, collection, etc.) for a model.

**Parameters**:
- `model_class`: Model class to create storage for

##### `create(model_class: Type[Any], data: Dict[str, Any]) -> Any`

Persists a new record.

**Parameters**:
- `model_class`: Model class
- `data`: Field values as dictionary

**Returns**: Created model instance

##### `list(model_class: Type[Any]) -> List[Any]`

Retrieves all records.

**Parameters**:
- `model_class`: Model class

**Returns**: List of model instances

##### `get(model_class: Type[Any], id_: int, as_dict: bool = False, **kwargs) -> Any`

Retrieves a single record.

**Parameters**:
- `model_class`: Model class
- `id_`: Primary key value
- `as_dict`: Return as dictionary if True
- `**kwargs`: Additional query parameters

**Returns**: Model instance, dictionary, or None

##### `update(model_class: Type[Any], id_: int, data: Dict[str, Any])`

Updates an existing record.

**Parameters**:
- `model_class`: Model class
- `id_`: Primary key value
- `data`: Fields to update

##### `delete(model_class: Type[Any], id_: int)`

Deletes a record.

**Parameters**:
- `model_class`: Model class
- `id_`: Primary key value

---

### SQLiteStorage

SQLite database storage backend with auto-migration support.

**Module**: `storage.sqlite_storage`

#### Constructor

```python
SQLiteStorage(database: str = 'database.db')
```

**Parameters**:
- `database`: Path to SQLite database file

**Example**:
```python
storage = SQLiteStorage('myapp.db')
```

#### Methods

##### `create_table(model_class: Type[Any])`

Creates SQLite table with appropriate column types.

**Type Mapping**:
- `int` -> `INTEGER`
- `float` -> `REAL`
- `str` -> `TEXT`
- `BaseModel` -> `INTEGER` (foreign key)
- `List[...]` -> `TEXT` (JSON serialized)

##### `migrate_table(model_class: Type[Any])`

Automatically adds missing columns to existing tables.

**Features**:
- Adds new columns with appropriate defaults
- Initializes List fields to `[]`
- Handles foreign keys
- Logs all migration operations

**Note**: Column removal requires manual intervention.

##### `create(model_class: Type[Any], data: Dict[str, Any]) -> Any`

Inserts a new row with auto-increment ID.

##### `get(model_class: Type[Any], id: int, as_dict: bool = False) -> Any`

Fetches a row and hydrates foreign keys as shell objects (ID only).

**Optimization**: Foreign key objects contain only ID, not full data (lazy loading).

##### `update(model_class: Type[Any], id: int, data: Dict[str, Any])`

Updates only the provided fields using parameterized query.

##### `delete(model_class: Type[Any], id: int)`

Deletes the specified row.

---

### JSONStorage

File-based JSON storage backend.

**Module**: `storage.json_storage`

#### Constructor

```python
JSONStorage(directory: str = 'data')
```

**Parameters**:
- `directory`: Directory path for JSON files

**Example**:
```python
storage = JSONStorage('data')
# Creates data/users.json, data/products.json, etc.
```

#### Methods

##### `create_table(model_class: Type[Any])`

Creates empty JSON file if it doesn't exist.

##### `create(model_class: Type[Any], data: Dict[str, Any]) -> Any`

Appends record to JSON array with auto-increment ID.

##### `list(model_class: Type[Any]) -> List[Any]`

Reads entire JSON file and deserializes to model instances.

##### `get(model_class: Type[Any], id: int) -> Any`

Searches JSON array for matching ID.

##### `update(model_class: Type[Any], id: int, data: Dict[str, Any])`

Finds record by ID and updates fields.

##### `delete(model_class: Type[Any], id: int)`

Removes record from JSON array.

---

## Types

### Ref

Generic type-safe wrapper for foreign key relationships.

**Module**: `utils.typer`

#### Constructor

```python
Ref[T](value: Optional[Any] = None)
```

**Parameters**:
- `value`: Can be:
  - `BaseModel` instance: Extracts ID
  - `int`: Stores directly
  - `dict`: Extracts 'id' key

**Example**:
```python
from utils.typer import Ref

class Comment(ProtoModel):
    user: Ref[User]  # Type-safe foreign key
```

#### Methods

##### `__int__() -> int`

Returns the foreign key ID.

**Example**:
```python
comment = Comment(...)
user_id = int(comment.user)  # Extracts ID
```

##### `model_dump() -> int`

Serializes to integer for storage.

#### Schema Generation

`__get_pydantic_json_schema__` outputs `$schema` and `$id` (instead of the old `__url__` and `__type__` fields) when generating the JSON schema for foreign key references:

```python
# Model definition
class Comment(ProtoModel):
    user: Ref[User]

# Generated schema
{
  "type": "object",
  "properties": {
    "user": {
      "type": "$ref",
      "$ref": "#/$defs/User"
    }
  }
}
```

---

## Decorators

### @expose_route

Decorator to expose model methods as API endpoints.

**Module**: `utils.decorators`

#### Signature

```python
@expose_route(route: str, methods: List[str] = ["POST"])
```

**Parameters**:
- `route`: Relative route path (e.g., '/login')
- `methods`: HTTP methods (e.g., ['GET', 'POST'])

#### Usage

##### Static Method

```python
class User(ProtoModel):
    @staticmethod
    @expose_route('/login', methods=['POST'])
    def login(email: str, password: str) -> User:
        # Creates: POST /users/login
        pass
```

##### Class Method

```python
class User(ProtoModel):
    @classmethod
    @expose_route('/search', methods=['GET'])
    def search(cls, query: str) -> List[User]:
        # Creates: GET /users/search
        pass
```

##### Instance Method

```python
class Product(ProtoModel):
    @expose_route('/discount', methods=['POST'])
    def apply_discount(self, percentage: float) -> Product:
        # Creates: POST /products/{id}/discount
        self.price *= (1 - percentage / 100)
        self.save()
        return self
```

#### Route Resolution

| Method Type | Route Pattern | Example |
|-------------|---------------|---------|
| Static | `/{table}{route}` | `/users/login` |
| Class | `/{table}{route}` | `/users/search` |
| Instance | `/{table}/{id}{route}` | `/products/1/discount` |

---

## Agents

LLM-powered reasoning via the actor system. See [`packages/n3tx-agents/README.md`](../../../packages/n3tx-agents/README.md) for full documentation.

### AgentMixin

**Module**: `n3tx_agents.mixin`

Injected into any model with `__agent__ = True` via `ProtoModel.__init_subclass__`. All methods use `@fullmethod` (unified class/instance dispatch).

#### `agentic(target, task: str, **kwargs) -> dict`

Policy layer. Resolves config via 3-tier cascade, delegates to `run()`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `task` | `str` | The user task / query to execute |
| `prompt` | `str` | Override system prompt (kwarg) |
| `tools` | `list[str]` | Override actor addresses (kwarg) |
| `user` | `dict` | JWT user dict for auth context (kwarg) |
| `llm` | `str \| Model` | Override LLM model (kwarg) |
| `constraints` | `dict` | Override constraints (kwarg) |
| `message_history` | `list` | Previous messages for multi-turn (kwarg) |
| `result_type` | `type` | Pydantic model for structured output (kwarg) |

**Returns**: `{"answer": str, "usage": {"input_tokens", "output_tokens", "requests"}, "messages": list, "message_count": int}`

#### `run(target, task, prompt, tools, ...) -> dict`

Engine. No config resolution. Receives fully resolved params. Same return shape as `agentic()`.

#### `agentic_stream(target, task, **kwargs)` -> async generator

Streaming policy layer. Same config cascade as `agentic()`. Yields TX-aligned chunks.

#### `run_stream(target, task, prompt, tools, ...)` -> async generator

Streaming engine. Yields `{"name": "text"|"done"|"error", "data": {...}, "meta": {...}}`.

### AgentActor

**Module**: `n3tx_agents.actor`

Concrete `ActorModel` whose instances ARE agents. Configuration lives in fields (DB-storable).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Human-readable agent name |
| `prompt` | `str` | `''` | System prompt for the LLM |
| `tools` | `ListRef[AgentTool]` | `[]` | Tool references via join table |
| `llm` | `str` | `'ollama:llama3.1'` | Pydantic AI `provider:model` string |
| `constraints` | `dict` | `{}` | Budget/safety limits |

#### `agentic(self, task: str, **kwargs) -> str`

Execute the agent's reasoning loop. Exposed as `POST /agents/{id}/agentic`. Returns JSON string.

### AgentDeps

**Module**: `agents.deps`

Dataclass passed to Pydantic AI tool functions via `RunContext[AgentDeps]`.

| Field | Type | Description |
|-------|------|-------------|
| `adapter` | `NetworkAdapter` | For request/response correlation |
| `user` | `dict \| None` | JWT user dict for auth context |
| `agent_addr` | `str` | Agent's actor address (TX.source) |

### ToolSpec

**Module**: `agents.tools`

Specification for a single discovered tool.

| Field | Type | Description |
|-------|------|-------------|
| `actor_addr` | `str` | Target actor address |
| `method_name` | `str` | Method/action name |
| `tool_name` | `str` | LLM-facing name (e.g., `grants_create`) |
| `description` | `str` | Human-readable description |
| `parameters` | `dict` | JSON Schema for parameters |

#### Related Functions

- `discover_tools(actor_addrs, root, caller_addr=None) -> list[ToolSpec]` — Discover tools from actor addresses
- `create_tool_function(spec) -> async function` — Create typed async function from ToolSpec
- `make_tool(spec) -> pydantic_ai.Tool` — Create Pydantic AI Tool wrapper

---

## Backends

### BaseBackend

Abstract base class for web framework adapters.

**Module**: `api.backend`

#### Fields

```python
name: str         # Backend name
description: str  # Backend description
version: str      # API version
port: int = 8000  # Server port
app: Any = None   # Framework-specific app instance
```

#### Abstract Methods

##### `register_routes(registered_models: Dict[str, Type])`

Registers all routes from registered models.

**Parameters**:
- `registered_models`: Dictionary of model name -> model class

---

### FastAPIBackend

FastAPI adapter with CORS support.

**Module**: `api.backend`

#### Constructor

```python
FastAPIBackend(
    name: str,
    version: str,
    description: str,
    port: int = 8000
)
```

#### Configuration

Automatically adds:
- CORS middleware (all origins allowed)
- OpenAPI/Swagger documentation
- Automatic JSON serialization

#### Route Handlers

All CRUD route handlers in `routes_fastapi.py` call `.model_response()` instead of `.model_dump()` or returning instances directly. This runs the dump pipeline and ensures every response includes `$schema` and `$id` metadata.

#### Example

```python
backend = FastAPIBackend(
    name="My API",
    version="1.0.0",
    description="API built with N3TX",
    port=8000
)
backend.register_routes(registered_models)
app = backend.get_app()
```

---

### FlaskBackend

Flask adapter with Flasgger (Swagger) support.

**Module**: `api.backend`

#### Constructor

```python
FlaskBackend(
    name: str,
    version: str,
    description: str,
    port: int = 8000
)
```

#### Configuration

Includes:
- Flask app with static/template folders
- Flasgger for Swagger UI
- WSGI to ASGI adapter

#### Example

```python
backend = FlaskBackend(
    name="My API",
    version="1.0.0",
    description="API built with N3TX",
    port=8000
)
backend.register_routes(registered_models)
app = backend.get_app()  # Returns WsgiToAsgi wrapped app
```

---

## Utilities

### register_model

Registers a model with N3TX's system.

**Module**: `utils.registrar`

**Signature**:
```python
register_model(
    model_class: Type[Any],
    storage: AbstractStorage = None
)
```

**Parameters**:
- `model_class`: Model to register
- `storage`: Storage backend (required if `__storable__` is True)

**Actions**:
1. Detects join models (has `__owner__`)
2. Sets storage backend
3. Creates table
4. Runs auto-migration
5. Adds to global registry

**Example**:
```python
from utils.registrar import register_model
from storage.sqlite_storage import SQLiteStorage

storage = SQLiteStorage('database.db')
register_model(User, storage=storage)
register_model(Product, storage=storage)
```

### generate_join_model

Programmatically generates a join model for many-to-many relationships.

**Module**: `models.proto_model`

**Signature**:
```python
generate_join_model(
    owner_cls: Type[ProtoModel],
    ref_model: Type[ProtoModel],
    field_name: str = None
) -> Type[ProtoModel]
```

**Parameters**:
- `owner_cls`: Owner model (e.g., Product)
- `ref_model`: Referenced model (e.g., Comment)
- `field_name`: Optional field name

**Returns**: Dynamically created join model class

**Example**:
```python
ProductComment = generate_join_model(Product, Comment)
register_model(ProductComment, storage=storage)

# Creates table: products_comments
# With columns: id, product_id, comment fields...
```

### get_traceback_info

Extracts structured error information from exceptions.

**Module**: `utils.erroring`

**Signature**:
```python
get_traceback_info(e: Exception) -> List[Dict]
```

**Parameters**:
- `e`: Exception to analyze

**Returns**: List of dictionaries with:
- `file`: Source file path
- `line`: Line number
- `function`: Function name
- `code`: Source code line
- `error`: Error message (last frame only)

**Example**:
```python
try:
    user = User.get(999)
except Exception as e:
    trace = get_traceback_info(e)
    # [
    #   {"file": "models.py", "line": 42, "function": "get", "code": "..."},
    #   {"file": "storage.py", "line": 100, "function": "query", "code": "..."},
    #   {"file": "main.py", "line": 10, "function": "main", "code": "...", "error": "Not found"}
    # ]
```

---

## Type Hints

N3TX provides type hints for all public APIs. Use with mypy or pyright for static type checking:

```python
from typing import ClassVar, Optional, List
from models.proto_model import ProtoModel
from storage.abstract_storage import AbstractStorage
from utils.typer import Ref

# All types are properly annotated
storage: AbstractStorage = SQLiteStorage('db.db')
user: User = User.get(1)
users: List[User] = User.list()
```

---

## Configuration

All configuration is in `config.py`:

```python
BACKEND = "fastapi"  # or "flask"
VERSION = "0.5.0"
HOST = "0.0.0.0"
PORT = 8000
SQLITE_DB_FILE = "n3tx.db"
```

---

## Error Handling

All route handlers automatically catch exceptions and return structured errors:

```python
# On error, returns:
{
  "status": 400,
  "detail": [
    {
      "file": "...",
      "line": ...,
      "function": "...",
      "code": "...",
      "error": "Error message"
    }
  ]
}
```

---

## Examples

### Complete API Example

```python
from models.proto_model import ProtoModel
from utils.decorators import expose_route
from utils.typer import Ref
from typing import ClassVar, Optional, List

class Author(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'authors'
    
    id: Optional[int] = None
    name: str
    email: str

class Book(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'books'
    
    id: Optional[int] = None
    title: str
    isbn: str
    author: Ref[Author]
    
    @expose_route('/publish', methods=['POST'])
    def publish(self) -> Book:
        self.published = True
        self.save()
        return self
    
    @classmethod
    @expose_route('/search', methods=['GET'])
    def search(cls, query: str) -> List[Book]:
        # Custom search logic
        return [b for b in cls.list() if query in b.title]
```

### Register and Run

```python
from storage.sqlite_storage import SQLiteStorage
from utils.registrar import register_model
from api.backend import FastAPIBackend

storage = SQLiteStorage('library.db')
register_model(Author, storage=storage)
register_model(Book, storage=storage)

backend = FastAPIBackend(name="Library API", version="1.0.0")
backend.register_routes(registered_models)
app = backend.get_app()

# Now available:
# GET/POST /authors
# GET/POST /books
# POST /books/{id}/publish
# GET /books/search?query=Python
# All GET responses include $schema and $id metadata
```

---

## See Also

- [README.md](./README.md) - Getting started guide
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Architecture overview
- [EXAMPLES.md](./EXAMPLES.md) - More examples
