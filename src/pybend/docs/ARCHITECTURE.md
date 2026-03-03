# PyBend Architecture Overview

This document provides a detailed explanation of PyBend's internal architecture, design patterns, and component interactions.

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Design Patterns](#design-patterns)
- [Extension Points](#extension-points)

## High-Level Architecture

PyBend follows a layered architecture with dependency injection for maximum flexibility:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
│       HTTP    │    MCP (AI)    │  ActivityPub  │  WebSocket     │
└───────┬───────┴───────┬────────┴──────┬────────┴───────┬────────┘
        │               │               │                │
┌───────▼───────────────▼───────────────▼────────────────▼────────┐
│                   Network Adapter Layer                          │
│          (Protocol → TX → Matrix → TX → Protocol)               │
│  • NetworkAPI (HTTP)    • NetworkMCP (JSON-RPC 2.0)             │
│  • NetworkAP (ActivityPub)  • NetworkWebSocket (WS)             │
└────────────────────────────┬────────────────────────────────────┘
                             │  TX messages
┌────────────────────────────▼────────────────────────────────────┐
│                     Actor System (Matrix)                        │
│              Message routing, Actor dispatch                     │
│  • Actor / ActorModel     • Handler dispatch                    │
│  • Class + Instance actors  • Lifecycle events                  │
└────────┬───────────────────────────────────────┬────────────────┘
         │                                       │
┌────────▼────────────────────────┐  ┌───────────▼───────────────┐
│      Business Logic Layer       │  │       Agent Layer          │
│      (Model Definitions)        │  │    (LLM-powered reasoning) │
│  • ProtoModel (Base)            │  │  • AgentMixin (agent_run)  │
│  • Schema Generation            │  │  • AgentActor (data agents)│
│  • Custom Methods               │  │  • Tool Discovery          │
│  • Validation / Foreign Keys    │  │  • Pydantic AI binding     │
└────────────────┬────────────────┘  └───────────┬───────────────┘
                 │                                │
                 └──────────────┬─────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                      Persistence Layer                          │
│              (StorableMixin + Storage Backends)                 │
│  • CRUD Operations          • Transaction Management            │
│  • Auto-Migration           • Query Execution                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                         Data Layer                              │
│                  (SQLite / JSON / Custom)                       │
│  • Physical Storage         • Data Persistence                  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. ProtoModel

**Location**: `models/proto_model.py`

The foundation of PyBend's model system. All models inherit from `ProtoModel`.

**Responsibilities**:
- Base class for all data models
- Schema generation and introspection
- Optional storage injection via `__storable__` flag
- Foreign key field transformation
- Method signature collection for API documentation

**Key Features**:

```python
class ProtoModel(PydanticBaseModel):
    class Config:
        extra = 'allow'  # Allow $schema and $id to survive FastAPI validation
    
    # Automatic storage injection
    def __init_subclass__(cls, **kwargs):
        if cls.__storable__:
            # Inject StorableMixin
            cls.__bases__ = (StorableMixin,) + cls.__bases__
            # Transform Pydantic models to Ref
            # Register with storage backend
    
    # Schema generation via composable pipeline (proto_schema)
    @classmethod
    def schema(cls) -> Dict[str, Any]:
        # Runs proto_schema.run_pipeline(cls) — 8 composable stages:
        # base -> strip_hidden -> methods -> agent -> defs -> access -> ui -> metadata
        # Extensions add stages via @schema_extension
        # Returns complete JSON schema including:
        # - $schema (pointing to {API_URL}/Schema)
        # - $id (pointing to {API_URL}/{ClassName})
        # - Fields (from Pydantic)
        # - Methods (from @expose_route)
        # - Referenced models in $defs (each with $id)

    # Enriched serialization via composable pipeline (proto_dump)
    def model_response(self, **kwargs) -> dict:
        # Runs proto_dump.run_pipeline(self) — stages:
        # base (plain Pydantic) -> response ($schema/$id)
        # Extensions add stages via @dump_extension
        # Injects:
        # - $schema: URL to model's JSON Schema
        # - $id: URL to this specific instance
```

**Design Decisions**:
- Uses `__init_subclass__` for automatic mixin injection
- Leverages Pydantic for validation and schema generation
- Separate `schema()` from `referenced_json_schema()` to avoid circular references
- Config `extra='allow'` permits `$schema` and `$id` metadata fields to pass through FastAPI response validation
- `model_response()` provides JSON-LD style self-describing responses via the composable dump pipeline (`proto_dump`)

### 2. StorableMixin

**Location**: `models/storable_mixin.py`

Provides CRUD operations through dependency injection.

**Pattern**: Strategy Pattern (storage backend is injected)

```python
class StorableMixin:
    storage: ClassVar[StorageInterface] = None  # Injected

    @classmethod
    def create(cls, data: Any) -> Any:
        return cls.storage.create(cls, data)

    @classmethod
    def list(cls, sql_filter=None, limit=None, offset=None):
        return cls.storage.list(cls, sql_filter=sql_filter, limit=limit, offset=offset)

    # ... other CRUD methods
```

**Pagination**: When `limit` is provided, `list()` returns `{"data": [...], "meta": {"total", "limit", "offset", "has_more"}}`. When omitted, returns a plain list (backward compatible).

**Key Features**:
- Storage backend agnostic
- Automatic join model support
- Foreign key unwrapping before persistence
- Lazy loading optimization
- Optional pagination with total count

### 3. AbstractStorage

**Location**: `storage/abstract_storage.py`

Interface for storage backends (Strategy Pattern).

```python
class AbstractStorage(ABC):
    @abstractmethod
    def create_table(self, model_class: Type[Any]): pass
    
    @abstractmethod
    def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any: pass
    
    @abstractmethod
    def list(self, model_class: Type[Any]) -> List[Any]: pass
    
    # ... other CRUD operations
```

**Implementations**:

#### SQLiteStorage
- Automatic schema migration
- Foreign key handling
- JSON serialization for complex types

#### JSONStorage
- File-based storage
- Auto-incrementing IDs
- Human-readable format

### 4. Ref Type

**Location**: `utils/typer.py`

Type-safe foreign key wrapper with OpenAPI schema generation.

```python
class Ref(Generic[T]):
    def __init__(self, value: Optional[Any] = None):
        if isinstance(value, BaseModel):
            self.id = value.id
            self._model = value
        elif isinstance(value, int):
            self.id = value
            self._model = None
    
    # Custom Pydantic schema for OpenAPI
    @classmethod
    def __get_pydantic_json_schema__(cls, ...):
        # Outputs $schema and $id instead of the old __url__ and __type__
        return {
            "type": "$ref",
            "$ref": f"#/$defs/{target.__name__}"
        }
```

**Purpose**:
- Maintains type safety in the model layer
- Generates proper `$ref` in OpenAPI schemas
- Serializes as integer for storage

### 5. Model Registry

**Location**: `utils/registrar.py`

Central registry for models and join tables.

```python
registered_models: Dict[str, Type[Any]] = {}
join_models: Dict[tuple[str, str], Type[Any]] = {}

def register_model(model_class: Type[Any], storage: StorageInterface = None):
    # 1. Detect join models (has __owner__)
    # 2. Set storage backend
    # 3. Create table
    # 4. Run migrations
    # 5. Add to registry
```

**Pattern**: Registry Pattern

### 6. Network Adapters

**Location**: `api/network_adapter.py`, `api/network_mcp.py`, `api/network_ap.py`

ALL external protocol interaction flows through a `NetworkAdapter(Actor)`. Each adapter translates between an external protocol and TX messages routed through the Matrix.

```python
class NetworkAdapter(Actor, auto_register=False):
    """Base class — request/response correlation via asyncio.Future."""

    async def request(self, tx: TX, timeout: float = 30.0) -> TX:
        # Sends TX, awaits correlated reply via Future matching

    async def inbox(self, tx: TX) -> None:
        # Intercepts correlated replies before normal handler dispatch

class NetworkMCP(NetworkAdapter):    # MCP JSON-RPC 2.0
class NetworkAP(NetworkAdapter):     # ActivityPub federation
class NetworkAPI(NetworkAdapter):    # HTTP REST (Level 3 actor routing)
class NetworkWebSocket(NetworkAdapter): # Frontend Matrix bridge
# Transient adapters created per agent_run() for tool call correlation
```

**Pattern**: Adapter Pattern (protocol translation) + Correlation Pattern (request/response over async messaging)

**Key Design Decision**: The HTTP API itself is a NetworkAdapter (`NetworkAPI`), meaning ALL external interaction — REST, MCP, ActivityPub, WebSocket — flows through the same architecture. No protocol is special.

### 6b. Interceptors (`use()`)

**Location**: `actors/actor.py` (base mechanism), `api/auth_interceptor.py` (auth implementation)

Every Actor can register TX interceptors on any of its TX-handling methods via `use()`:

```python
# Register on specific method targets
actor.use(auth_check, on='inbox')      # before inbox processes
actor.use(rate_limit, on='send')       # before send routes
adapter.use(jwt_auth, on='request')    # before request sends+awaits

# Decorator forms
@actor.use                             # defaults to on='inbox'
async def log_all(tx: TX) -> TX: ...

@adapter.use(on='request')
async def authenticate(tx: TX) -> TX: ...
```

**Interceptor signature**: `async (TX) -> TX`. Return error TX to short-circuit the chain.

**Chain behavior**:
- Class-level interceptors run first, then instance-level (combined via `_get_interceptors`)
- Chain stops on first error TX (`tx.is_error`)
- `inbox()` error: sends error TX back via `send()` (caller gets rejection)
- `send()` error: drops silently (outbound message never routed)
- `request()` error: returns error TX immediately (never enters actor system)

**Per-adapter, not global**: Each adapter registers its own interceptors. Authentication is protocol-specific (JWT for HTTP, API key for MCP, HTTP signatures for AP). Universal authorization is handled by Tier 2 handler guard in ActorModel.

### 6c. Two-Tier Authorization

When using Level 3 actor routing (NetworkAPI), authorization is split into two tiers:

```
HTTP Request → NetworkAPI.request(tx)
                   │
                   ├── Tier 1: 'request' interceptor (auth_interceptor)
                   │   Fast gate at protocol boundary:
                   │   • schema: pass-through (always public)
                   │   • list: compute sql_filter, store in tx.meta
                   │   • create: full rule check (no resource needed)
                   │   • read/update/delete: identity gate only
                   │
                   ▼
              Matrix routing → ActorModel.handler_crud(tx)
                   │
                   ├── Tier 2: _authorize() handler guard
                   │   Full ABAC with resource instance:
                   │   • Evaluates OWNER rules (needs fetched entity)
                   │   • Defense-in-depth for anything Tier 1 missed
                   │
                   ▼
              StorableMixin CRUD → result → tx.reply() → Future resolved
```

**Why two tiers?** OWNER-based rules need the resource instance. Tier 1 runs before the handler fetches it. Tier 2 runs after. Natural split: identity/role checks at the boundary, resource-dependent checks at the handler.

### 7. Three Levels of PyBend

PyBend supports three routing levels — developers choose based on their needs:

```
Level 1: ProtoModel  + routes_fastapi.py   → plain HTTP, no actors
Level 2: ActorModel  + routes_fastapi.py   → actor capabilities, same HTTP layer
Level 3: ActorModel  + NetworkAPI adapter   → actors all the way down
```

Each level is one change from the previous. Model base class swap for Level 2, `routing='actor'` flag for Level 3.

```python
# Level 1 — Plain HTTP (default)
app = create_app(models=[Product, User], storage="sqlite:///app.db")

# Level 2 — Actor capabilities, same HTTP routes
# Just change ProtoModel → ActorModel in your models
app = create_app(models=[Product, User], storage="sqlite:///app.db")

# Level 3 — Full actor routing through Matrix
app = create_app(models=[Product, User], storage="sqlite:///app.db", routing='actor')
```

**Level 1/2** use `routes_fastapi.py` route factories (direct StorableMixin calls).
**Level 3** uses `NetworkAPI` adapter (HTTP → TX → Matrix → ActorModel → StorableMixin).

`routes_fastapi.py` is never modified — Level 3 is purely additive.

### 8. Agent System

**Location**: `agents/mixin.py`, `agents/actor.py`, `agents/tools.py`, `agents/deps.py`, `agents/schema_ext.py`

LLM-powered agents built on [Pydantic AI](https://ai.pydantic.dev/). PyBend provides only the binding layer — tool discovery from actor schemas, TX routing for tool calls, and agent state persistence.

**Core insight**: Every Actor with `@expose_route` methods is a tool collection. An Agent is an Actor that reasons.

```python
# AgentMixin — injected when __agent__ = True (same pattern as StorableMixin)
class AgentMixin:
    async def agent_run(self, prompt, tools, task, user=None, **kwargs) -> dict:
        # 1. Create transient NetworkAdapter for request/response correlation
        # 2. discover_tools(tools, root) — read schemas, build ToolSpecs
        # 3. Create Pydantic AI Agent with generated tool functions
        # 4. Run agent loop — tool calls route through Matrix as TX
        # 5. Cleanup transient adapter
        # Returns: {answer, usage: {input_tokens, output_tokens, requests}, messages}

# AgentActor — concrete model whose instances ARE agents (data, not code)
class AgentActor(ActorModel):
    __agent__ = True        # gets AgentMixin
    __storable__ = True     # stored in DB

    name: str               # Human-readable name
    prompt: str             # System prompt
    tools: list             # Actor addresses = tool sets
    llm: str                # Pydantic AI provider:model string
    constraints: dict       # {max_iterations, ...}

    @expose_route('/run', methods=['POST'])
    async def run(self, task: str, **kwargs) -> str: ...
```

**Two paths, one mechanism**:
- **Path A**: `AgentActor` instances (dynamic agents — created via API/DB/code)
- **Path B**: Any model with `__agent__ = True` (agentic methods — `self.agent_run()`)

**Tool discovery**: `discover_tools(actor_addrs, root)` reads `schema.methods` from Matrix children. Storable models get CRUD tools (list, get, create, update, delete). All `@expose_route` methods become tools. Tool functions use `exec()` for dynamic typed signatures (same as dataclasses).

**Tool call routing**: Generated tool functions create TX messages and send them through `NetworkAdapter.request()` for Future-based correlation. Error TXs raise `ModelRetry` (Pydantic AI retries the LLM).

**Schema extension**: `@schema_extension(after='methods')` adds `agent: {enabled, run_endpoint}` to JSON Schema output for agent-capable models.

See [`src/pybend/core/agents/README.md`](../agents/README.md) for full documentation.

### 9. Backend Adapters

**Location**: `api/backend.py`

Abstract interface for web frameworks.

```python
class BaseBackend(ABC, BaseModel):
    @abstractmethod
    def register_routes(self, registered_models: dict): pass

class FastAPIBackend(BaseBackend):
    # FastAPI-specific implementation

class FlaskBackend(BaseBackend):
    # Flask-specific implementation
```

**Purpose**:
- Framework-agnostic model definitions
- Easy switching between FastAPI/Flask
- Extensible to other frameworks (Django, Sanic, etc.)

### 7. Route Registration

**Location**: `api/routes_fastapi.py`

Dynamically generates routes from model definitions.

**Route Factories**:

All route factories call `.model_response()` to include `$schema` and `$id` metadata in responses. This runs the dump pipeline (`proto_dump.run_pipeline()`), which is extensible via `@dump_extension`:

```python
def make_create_instance(model_class):
    # Returns async function for POST /model
    # Auto-injects user_owner from JWT for models with __protected_fields__
    # Calls .model_response()

def make_get_all_instances(model_class):
    # Returns async function for GET /model?limit=N&offset=M
    # Supports optional pagination via query params
    # Returns plain array (no params) or {data, meta} (with limit)
    # Calls .model_response() on each instance

def make_get_instance(model_class):
    # Returns async function for GET /model/{id}
    # Calls .model_response()

# ... etc
```

**Collection Route Factory**:

```python
def make_collection_list(model_class, child_model):
    # Returns async function for GET /parent_table/child_table
    # Lists all child records across all parents
    # Supports auth, pagination, and populate
    # Registered in Pass 1 (before CRUD routes) to avoid {id:int} path conflict
```

**Custom Routes**:

```python
def make_custom_post(attr, model_class, route_path):
    # Inspects method signature
    # Generates appropriate async function
    # Handles parameter parsing and validation
    # Auto-injects authenticated user for methods with `user` parameter
    # Supports Body(default={}) for empty-body toggle endpoints
```

**User Resolution Bridge** (`_resolve_user`):

Bridges the auth layer (JWT dicts) to the model layer (entity instances). When a custom method declares a `user` parameter:
- If the type hint is a `StorableMixin` subclass (e.g., `User`), fetches the full model instance via `.get(user_id)`
- Otherwise, passes the raw JWT dict `{"user_id", "email", "role"}`

This keeps the `authorize` package (zero PyBend imports) decoupled from model definitions.

## Data Flow

### 1. Model Registration Flow

```
┌─────────────────┐
│ Define Model    │
│ (ProtoModel)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ __init_subclass │
│ • Check __storable__
│ • Inject StorableMixin
│ • Transform FKs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ register_model  │
│ • Set storage   │
│ • Create table  │
│ • Run migration │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ register_routes │
│ • CRUD routes   │
│ • Custom routes │
└─────────────────┘
```

### 2. Request Handling Flow (Read)

```
HTTP GET /users/1
      │
      ▼
┌─────────────────┐
│ FastAPI Router  │
│ (make_get_instance)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ User.get(1)     │
│ (StorableMixin) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ storage.get()   │
│ (SQLiteStorage) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Execute Query   │
│ SELECT * FROM users WHERE id=1
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Hydrate Model   │
│ User(**data)    │
└────────┬────────┘
         │
         ▼
┌──────────────────────────┐
│ Serialize JSON           │
│ model.model_response()   │
│ (injects $schema, $id)  │
└────────────┬─────────────┘
         │
         ▼
    HTTP 200 OK
```

### 3. Foreign Key Resolution Flow

```
┌─────────────────┐
│ Model Definition│
│ user: User      │ (Pydantic model reference)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ __init_subclass │
│ Detects BaseModel
│ → user: Ref[User]
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Storage Layer   │
│ Stores: user_id=123
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Retrieval       │
│ Creates shell:  │
│ User(id=123)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Lazy Loading    │
│ (if accessed)   │
│ Full fetch from DB
└─────────────────┘
```

## Design Patterns

### 1. Mixin Pattern

**StorableMixin**, **ViewableMixin**, and **AgentMixin** are dynamically injected into models via `__init_subclass__`:

```python
# Before
class User(ProtoModel):
    __storable__: ClassVar[bool] = True

# After __init_subclass__
class User(StorableMixin, ProtoModel):
    # Now has .save(), .create(), .list(), etc.

# Agent injection (same pattern)
class Scanner(ActorModel):
    __agent__ = True

# After __init_subclass__
class Scanner(AgentMixin, ActorModel):
    # Now has .agent_run()
```

**Benefits**:
- Opt-in functionality
- Keeps concerns separated
- No inheritance pollution

### 2. Strategy Pattern

Storage backends implement a common interface:

```python
storage: AbstractStorage = SQLiteStorage('db.db')  # or JSONStorage

model.set_storage(storage)
model.create_table()
```

**Benefits**:
- Swap backends without code changes
- Easy testing with mock storage
- Custom storage implementations

### 3. Registry Pattern

Central model registry for route generation:

```python
registered_models: Dict[str, Type[Any]] = {}

# During registration
registered_models['users'] = User

# During route generation
for model_name, model_cls in registered_models.items():
    register_crud_routes(model_name, model_cls)
```

### 4. Factory Pattern

Route handlers are generated via factory functions:

```python
def make_create_instance(model_class):
    async def create_instance(data: model_class):
        return model_class.create(data)
    return create_instance

router.post('/users', make_create_instance(User))
```

### 5. Decorator Pattern

`@expose_route` adds metadata to methods:

```python
@expose_route('/login', methods=['POST'])
def login(email: str, password: str):
    pass

# Adds: method.__endpoint__ = {'route': '/login', 'methods': ['POST']}
```

### 6. Two-Pass Route Registration

Routes are registered in two passes to avoid path conflicts:

```
Pass 1: Collection routes (static segments)
  /products/comments     (GET — all comments across products)
  /products/likes        (GET — all favorites across products)

Pass 2: CRUD routes (parameterized segments)
  /products/{id}         (GET/PUT/DELETE)
  /products/{parent_id}/comments/{id}  (nested CRUD)
```

This ensures `/products/comments` is matched as a collection route, not as `/products/{id}` with `id="comments"`.

### 7. Adapter Pattern

Backend adapters translate between frameworks:

```python
class BaseBackend(ABC):
    @abstractmethod
    def register_routes(self): pass

class FastAPIBackend(BaseBackend):
    def register_routes(self):
        # FastAPI-specific logic

class FlaskBackend(BaseBackend):
    def register_routes(self):
        # Flask-specific logic
```

## Extension Points

### 1. Custom Storage Backend

```python
class RedisStorage(AbstractStorage):
    def create_table(self, model_class):
        # Redis doesn't need tables
        pass
    
    def create(self, model_class, data):
        key = f"{model_class.__tablename__}:{data['id']}"
        self.redis.set(key, json.dumps(data))
        return model_class(**data)
    
    # ... implement other methods
```

### 2. Custom Backend Adapter

```python
class DjangoBackend(BaseBackend):
    def __init__(self, **data):
        super().__init__(**data)
        from django.conf import settings
        # Django setup
    
    def register_routes(self, registered_models):
        # Generate Django URL patterns
        pass
```

### 3. Custom Mixin

```python
class AuditableMixin:
    created_at: datetime
    updated_at: datetime
    
    def save(self):
        self.updated_at = datetime.now()
        return super().save()

class User(ProtoModel):
    __storable__: ClassVar[bool] = True
    __bases__ = (AuditableMixin,) + ProtoModel.__bases__
```

### 4. Custom Field Types

```python
class EncryptedString(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        # Custom validation/serialization
        pass

class User(ProtoModel):
    password: EncryptedString  # Automatically encrypted
```

### 5. Middleware/Hooks

```python
# In backend.py
class FastAPIBackend(BaseBackend):
    def register_routes(self, registered_models):
        @self.app.middleware("http")
        async def log_requests(request, call_next):
            # Custom logging
            response = await call_next(request)
            return response
        
        # Then register routes
        super().register_routes(registered_models)
```

## Performance Considerations

### 1. Lazy Loading

Foreign keys load as shells (ID only) and fetch on demand:

```python
user = User.get(1)
print(user.id)           # No DB query
print(user.posts[0].id)  # Triggers DB query for posts
```

### 2. Schema Caching

Schemas are generated once per model class:

```python
@classmethod
@lru_cache(maxsize=None)  # Could be added
def schema(cls):
    # Expensive introspection
    return computed_schema
```

### 3. Batch Operations

```python
# Future enhancement
class StorableMixin:
    @classmethod
    def bulk_create(cls, items: List[Any]):
        # Single transaction for multiple inserts
        pass
```

## Security Considerations

### 1. SQL Injection Prevention

All storage backends use parameterized queries:

```python
cursor.execute(
    "SELECT * FROM users WHERE id = ?",
    (user_id,)  # Parameterized
)
```

### 2. Field Validation

Pydantic validates all inputs:

```python
class User(ProtoModel):
    email: EmailStr  # Automatic email validation
    age: conint(ge=0, le=120)  # Constrained integer
```

### 3. Sensitive Data

```python
class User(ProtoModel):
    password: str = Field(..., exclude=True)  # Never in responses
```

## Testing Architecture

```python
# Mock storage for testing
class MockStorage(AbstractStorage):
    def __init__(self):
        self.data = {}
    
    def create(self, model_class, data):
        self.data[data['id']] = data
        return model_class(**data)

# In tests
storage = MockStorage()
register_model(User, storage=storage)
```

## Social Feature Patterns

### Toggle Endpoints

Like/favorite actions use a toggle pattern: POST with empty body creates or deletes a join table record.

```python
@expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
def favorite(self, user: User = None) -> str:
    # Query join table for existing record
    # If exists → delete → return {"action": "unfavorited"}
    # If not → create → return {"action": "favorited"}
```

The route layer uses `join_models` registry to resolve the correct join model (e.g., `ProductLike`), queries by parent + user, and creates/deletes accordingly. `Body(default={})` allows empty POST bodies.

### Self-Referential Nesting (Replies)

Comments support nesting via `parent_id: Ref['self']`. The `reply()` method creates a child comment with `parent_id` set, resolves the product parent for join table insertion, and restricts access to `AUTHENTICATED` users.

## Future Enhancements

1. **Query Builder**: Fluent API for complex queries
2. **Async Storage**: Async/await for I/O operations
3. **Caching Layer**: Redis/Memcached integration
4. ~~**Event System**: Pre/post save hooks~~ — Implemented via ActorModel lifecycle events (v0.8)
5. **Migrations**: Version-controlled schema changes
6. **GraphQL**: Automatic GraphQL schema generation
7. ~~**WebSockets**: Real-time updates~~ — Planned as `NetworkWebSocket` adapter
8. ~~**NetworkAPI**: HTTP REST adapter~~ — Implemented (v0.8.2). Level 3 routing via `create_app(routing='actor')`
9. **MCP Integration**: ~~Planned~~ Implemented via `NetworkMCP` adapter (v0.8.1)
10. **ActivityPub Federation**: ~~Planned~~ Implemented via `NetworkAP` adapter (v0.8.1)
11. ~~**Interceptors**: Universal middleware for actors~~ — Implemented via `use()` (v0.8.2)
12. ~~**Two-Tier Auth**: Protocol-boundary + handler-level authorization~~ — Implemented (v0.8.2)
13. ~~**Agent System**: LLM-powered agents~~ — Implemented via `AgentMixin` + `AgentActor` (v0.10)
14. **Agent Traces**: Run history, step log, cost tracking (planned Phase 2)
15. **Agent Streaming**: Pydantic AI `run_stream()` + SSE (planned Phase 3)

## Conclusion

PyBend's architecture prioritizes:
- **Modularity**: Swappable components at every layer
- **Declarative**: Models define behavior, not implementation
- **Type Safety**: Pydantic + Ref for compile-time checks
- **Extensibility**: Clear extension points for customization
- **Simplicity**: Minimal boilerplate for common cases
