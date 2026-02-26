# Microservice Patterns and PyBend: Architecture Relevance Analysis

> Research document for technical leadership and engineering teams.
> Analyzes how PyBend's schema-driven architecture maps to microservice
> patterns, where the framework already provides microservice primitives,
> and what would need to change for a full decomposition.

---

## Executive Summary

PyBend is not a microservice framework. It is a **modular monolith** with
unusually clean boundaries between its constituent parts. The interesting
finding is that those boundaries align almost exactly with the seams where
a microservice architecture would split. This document maps the alignment
concretely -- citing actual code, actual data flows, and actual gaps --
so that the team can make an informed decision about if and when to cross
from modular monolith to distributed services.

The short version:

- **What PyBend already has:** Self-contained app builder, per-model
  storage isolation, auto-generated API contracts (JSON Schema), model-
  level access control, pluggable backend adapters, and a model registry
  that tracks every registered entity.
- **What is missing:** Service discovery, inter-service communication
  (event bus, gRPC), distributed tracing, health checks, circuit
  breakers, configuration management per service, and deployment
  orchestration.
- **The strategic position:** PyBend sits at the "modular monolith"
  sweet spot. It can be decomposed into microservices when load or
  organizational boundaries demand it, but the monolith is the correct
  default for most stages of growth.

---

## 1. Model-to-Service Mapping

### 1.1 The `create_app()` Primitive Is Already a Service Factory

The single most relevant piece of code is in
`/workspace/src/pybend/core/app.py`. The `create_app()` function takes a
list of models and produces a fully operational ASGI application:

```python
# From /workspace/src/pybend/core/app.py, lines 180-227
def create_app(
    models=None,
    join_models=None,
    storage=None,
    static_dir=None,
    jwt_secret=None,
    jwt_expiry_hours=24,
    cors_origins=None,
    debug=False,
    name="PyBend",
    version="1.0.0",
    description="",
    **kwargs,
):
    builder = PyBendApp(
        storage=storage,
        jwt_secret=jwt_secret,
        jwt_expiry_hours=jwt_expiry_hours,
        cors_origins=cors_origins,
        debug=debug,
    )
    for m in (models or []):
        builder.model(m)
    for parent, child in (join_models or []):
        builder.join(parent, child)
    if static_dir:
        builder.static(static_dir)
    return builder.build(name=name, version=version, description=description)
```

This means you can already do:

```python
# Product service -- standalone, self-contained
product_app = create_app(
    models=[Product],
    storage="sqlite:///product.db",
    name="Product Service",
    version="1.0.0",
)

# User service -- completely independent
user_app = create_app(
    models=[User],
    storage="sqlite:///user.db",
    name="User Service",
    version="1.0.0",
)
```

Each call produces an independent FastAPI application with its own
storage, routes, middleware, and schema endpoints. These could be
deployed to separate processes, containers, or machines today.

### 1.2 Per-Model Storage Isolation

The `PyBendApp` builder already supports per-model storage overrides.
From `/workspace/src/pybend/core/app.py`, lines 98-107:

```python
def model(self, model_class: Type, storage=None) -> "PyBendApp":
    """Register a model.  Returns ``self`` for chaining.

    Args:
        model_class: A ``ProtoModel`` subclass to register.
        storage: Optional per-model storage override.  If ``None``,
            the builder-level storage is used.
    """
    self._models.append((model_class, storage))
    return self
```

And during build, from lines 148-154:

```python
for model_class, per_model_storage in self._models:
    effective_storage = (
        _resolve_storage(per_model_storage)
        if per_model_storage is not None
        else self._storage
    )
    register_model(model_class, storage=effective_storage)
```

This means even within a single process, each model can have its own
database -- a key microservice principle (database-per-service) is
already supported at the framework level.

### 1.3 The Mapping Table

| Microservice Concept | PyBend Equivalent | Status |
|---|---|---|
| Service boundary | `create_app(models=[...])` | Ready |
| Database per service | Per-model `storage=` parameter | Ready |
| API contract | `ProtoModel.schema()` JSON Schema | Ready |
| Service identity | `name`, `version` in `PyBendApp` | Ready |
| Authentication | JWT middleware, per-app configurable | Ready |
| Authorization | ABAC rules on model `__access__` | Ready |
| Service registry | `registered_models` dict | Partial |
| Service discovery | Not implemented | Missing |
| Inter-service calls | HTTP only (manual) | Partial |
| Event-driven communication | Not implemented | Missing |
| Health checks | Not implemented | Missing |
| Configuration management | `config.py` + env vars, global | Partial |

---

## 2. Auto-Generated API Contracts vs. OpenAPI

### 2.1 What `ProtoModel.schema()` Produces

Every model generates a complete JSON Schema document. From
`/workspace/src/pybend/core/models/proto_model.py`, the `schema()`
classmethod (lines 197-300) produces:

```
GET /Product --> JSON Schema
  $schema    --> meta-schema URL
  $id        --> this schema's canonical URL
  properties --> typed fields with validation, UI hints, access rules
  methods    --> callable endpoints with parameters and return types
  access     --> ABAC rules serialized for frontend consumption
  ui         --> layout hints (field order, groups, renderers)
  $defs      --> nested/related model schemas
```

This is richer than a standard OpenAPI spec in some ways (UI hints,
access rules, method signatures with parameter schemas) but narrower
in others (no request/response examples, no error schemas, no
server/path metadata).

### 2.2 Comparison: JSON Schema vs. OpenAPI

| Capability | PyBend JSON Schema | OpenAPI 3.x |
|---|---|---|
| Type definitions | Full (via Pydantic) | Full |
| Validation rules | Full (min/max, patterns) | Full |
| Endpoint paths | Implicit from `__tablename__` | Explicit |
| HTTP methods | Implicit (CRUD convention) | Explicit |
| Request bodies | Implicit (model properties) | Explicit |
| Response shapes | Implicit (`model_dump`) | Explicit |
| Error responses | Not specified | Specifiable |
| Authentication schemes | Not in schema | Specifiable |
| UI rendering hints | Full (`ui.*` extensions) | Not applicable |
| Access control rules | Full (`access.*`) | Not standard |
| Method parameters | Full (`methods.*`) | Via parameters |
| Nested models | Full (`$defs`) | Via `$ref` |
| Versioning | Via `$id` URL | Via `info.version` |

### 2.3 The Bridge: FastAPI Already Generates OpenAPI

Because PyBend uses FastAPI as its backend, OpenAPI specs are already
generated automatically. From `/workspace/src/pybend/core/api/backend.py`,
lines 64-67:

```python
self.app = FastAPI(
    title=self.name,
    version=self.version,
    description=self.description
)
```

FastAPI generates OpenAPI at `/openapi.json` and Swagger UI at `/docs`
for free. This means PyBend actually has **two** contract formats:

1. **JSON Schema** (PyBend-native) -- consumed by the NTT frontend
   system for dynamic class creation, form generation, and permission
   checks.
2. **OpenAPI** (FastAPI-native) -- consumable by any standard API client,
   SDK generator, or service mesh.

For microservice communication, the OpenAPI spec is the interoperable
standard. The JSON Schema is the richer internal contract.

### 2.4 What a Contract-First Microservice Architecture Would Need

The gap is not in schema generation but in schema **consumption across
service boundaries**. Today, the JSON Schema is consumed by one client:
the NTT frontend. For service-to-service communication, services would
need to:

1. Fetch another service's schema at `GET /{ModelName}`
2. Validate payloads against it
3. Generate typed client stubs from it

This is solvable with existing tooling (JSON Schema validators, OpenAPI
code generators) but is not wired up in the framework today.

---

## 3. The Registry Pattern

### 3.1 Current Implementation

From `/workspace/src/pybend/core/utils/registrar.py`:

```python
registered_models: Dict[str, Type[Any]] = {}
join_models: Dict[tuple[str, str], Type[Any]] = {}

def register_model(model_class: Type[Any], storage: StorageInterface = None):
    logger.info("Registering model: %s", model_class.__name__)

    if hasattr(model_class, '__owner__'):
        parent = model_class.__owner__
        base = model_class.__bases__[-1]
        join_models[(parent.__name__, base.__name__)] = model_class

    if hasattr(model_class, '__storable__') and model_class.__storable__:
        if storage is None:
            raise ValueError(
                f"Storage backend must be provided for model '{model_class.__name__}'"
            )
        model_class.set_storage(storage)
        model_class.create_table()
        if hasattr(storage, 'migrate_table'):
            storage.migrate_table(model_class)
    registered_models[model_class.__tablename__] = model_class
```

This is a **local** model registry: an in-process dictionary that maps
table names to model classes. It serves the same conceptual purpose as
a service registry (Consul, etcd, Eureka) but operates at module scope
within a single Python process.

### 3.2 From Model Registry to Service Registry

The `registered_models` dictionary already knows:
- What models exist (keys)
- What class implements each model (values)
- What storage backend each model uses (`model_class.storage`)
- What routes each model exposes (via `register_routes()`)
- What schema each model provides (via `model_class.schema()`)

A service registry would need to additionally know:
- **Where** each model's service is running (host:port)
- **Health status** of each service
- **Version** of the schema each service implements
- **Dependencies** between services (which models reference which)

The upgrade path is relatively clean:

```
Current:
  registered_models["products"] = <class Product>
  Product.storage = SQLiteStorage("product.db")

Service registry:
  service_registry["products"] = {
      "class": <class Product>,
      "host": "product-service.internal",
      "port": 5001,
      "schema_url": "http://product-service.internal:5001/Product",
      "health_url": "http://product-service.internal:5001/health",
      "version": "1.0.0",
      "status": "healthy",
      "dependencies": ["users", "comments"],
  }
```

### 3.3 Dependency Graph from Model References

PyBend already tracks model dependencies through `ListRef` and `Ref`
fields and the `__fk_models__` class variable. From the example models:

```
Product
  +-- comments: ListRef[Comment]  --> depends on Comment service
  +-- favorites: ListRef[Like]    --> depends on Like service

Comment
  +-- user_owner: User            --> depends on User service
  +-- likes: ListRef[Like]        --> depends on Like service
  +-- parent_id: Ref['self']      --> self-referential
```

This dependency graph is already implicit in the model definitions. A
service decomposition tool could extract it programmatically by
inspecting `collect_all_referenced_models()` (used during schema
generation in `proto_model.py`, line 208).

---

## 4. Authorization Across Service Boundaries

### 4.1 The Current ABAC System

PyBend's authorization is model-level and already modular. From
`/workspace/src/pybend/core/authorize/rules.py`, the rule system is
purely composable:

```python
class AccessRule(ABC):
    @abstractmethod
    def evaluate(self, ctx: AccessContext) -> bool: ...

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]: ...

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]: ...

    def __or__(self, other): return OrRule(self, other)
    def __and__(self, other): return AndRule(self, other)
    def __invert__(self): return NotRule(self)
```

From `/workspace/src/pybend/core/authorize/context.py`, the evaluation
context is a simple immutable dataclass:

```python
@dataclass(frozen=True)
class AccessContext:
    user: Dict[str, Any]
    action: str
    model_class: Type[Any]
    resource: Optional[Any] = None
    parent_id: Optional[int] = None
```

The `authorize` package has **zero PyBend imports** -- it is already a
standalone library. This is noted in CLAUDE.md and verified in the code:
the rules, context, resolver, and errors modules import only from each
other and from Python stdlib/typing.

### 4.2 Cross-Service Authorization Patterns

In a microservice architecture, authorization must work across service
boundaries. There are three standard patterns:

**Pattern 1: Token-Forwarding (Simplest, Already Supported)**

Each service validates the JWT independently. The JWT carries identity
claims (user_id, email, role). Each service has its own `__access__`
rules and evaluates them locally.

```
Client --> Product Service (JWT in header)
              |
              +--> Validates JWT (already implemented in JWTAuthMiddleware)
              +--> Evaluates __access__ rules against user claims
              +--> Returns 200 or 403
```

This pattern works today with no changes. Each `create_app()` call
configures `authorize.configure(jwt_secret=...)` identically, so the
same JWT is valid across all services.

**Pattern 2: Centralized Auth Service**

A dedicated auth service issues tokens. Other services validate against
it. PyBend's `BaseUser` model with `login()` and `register()` endpoints
is the natural candidate for this service.

```python
# Auth service
auth_app = create_app(
    models=[User],
    storage="sqlite:///auth.db",
    name="Auth Service",
)

# Product service -- validates tokens but does not issue them
product_app = create_app(
    models=[Product],
    storage="sqlite:///product.db",
    jwt_secret=SHARED_SECRET,  # same secret as auth service
    name="Product Service",
)
```

**Pattern 3: Policy-as-Data**

The access rules are already serializable to JSON via `to_dict()`. This
means they could be stored in a central policy store and fetched by each
service at startup. The `AuthorizationResolver` protocol (from
`/workspace/src/pybend/core/authorize/resolver.py`) makes this swappable:

```python
@runtime_checkable
class AuthorizationResolver(Protocol):
    def resolve_rule(self, model_class, action) -> AccessRule: ...
    def authorize(self, ctx: AccessContext) -> None: ...
    def sql_filter_for(self, ctx: AccessContext) -> Optional[Tuple]: ...
```

A `RemotePolicyResolver` could fetch rules from a central policy service
instead of reading them from `model_class.__access__`.

### 4.3 The OWNER Rule Challenge

The `OWNER` rule (lines 142-150 in rules.py) checks whether the
requesting user owns the resource:

```python
class _Owner(AccessRule):
    def evaluate(self, ctx: AccessContext) -> bool:
        # checks ctx.resource.user_owner == ctx.user_id
```

This requires access to the **resource itself** -- which means the
service evaluating the rule must have the resource in its database. In
a microservice architecture where Product and User are in different
services, an OWNER check on a Product requires that the Product service
stores the `user_owner` field. This is fine as long as the foreign key
is a plain integer (which it is), not a live reference to the User
service.

The `sql_filter` method on OWNER rules pushes the check to SQL:

```sql
WHERE user_owner = ?  -- params: [user_id]
```

This works independently of whether the User model is in the same
database. The Product service only needs to know the user_id from the
JWT, not the full User record.

---

## 5. Inter-Service Communication

### 5.1 What Exists Today: REST Only

PyBend auto-generates REST endpoints. From
`/workspace/src/pybend/core/api/routes_fastapi.py`, the `register_routes()`
function (lines 387-497) creates:

```
GET  /{ModelName}              --> schema
POST /{tablename}              --> create
GET  /{tablename}              --> list (paginated)
GET  /{tablename}/{id}         --> read
PUT  /{tablename}/{id}         --> update
DELETE /{tablename}/{id}       --> delete
POST /{tablename}/{id}/{method} --> custom method
```

For inter-service communication, one service could call another's REST
API using standard HTTP. But this is manual -- there is no built-in
service client.

### 5.2 The Frontend Actor System as a Pattern

The NTT frontend uses an actor/message-bus pattern. From
`/workspace/src/pybend/static/core/Matrix.js`:

```javascript
export class Matrix extends Actor {
    constructor(addr, url="") {
        super(addr);
        if (!Actor.root){
            Actor.registerRoot(this);
        }
        this.remote = new NetworkAdapter(this, url)
    }

    inbox(event) {
        let tx = event instanceof TX ? event : new TX(event);
        let targetAddr = tx.target.split('/')[0];

        if (this.children.has(targetAddr)) {
            tx = this.children.get(targetAddr).inbox(tx.repr());
        } else {
            tx = this.remote.send(tx);
        }
        return tx;
    }
}
```

The Matrix routes messages: local children get direct delivery, unknown
targets go to the network. This is conceptually identical to a service
mesh sidecar: local calls are fast, remote calls are transparently
routed.

A backend equivalent would be:

```
Incoming request for Product.comment()
  |
  +--> Product service handles locally
  +--> Needs to validate user? Forward to User service
  +--> Needs to notify subscribers? Publish event to bus
```

### 5.3 Communication Patterns Needed

| Pattern | Use Case | Complexity |
|---|---|---|
| Synchronous REST | Service A calls Service B and waits | Low (already possible) |
| Async events | "Product created" notifies Notification service | Medium |
| Request-reply | Product asks User service "is this user valid?" | Medium |
| Saga/choreography | Create order spanning Product + Payment + Inventory | High |
| CQRS | Read-optimized views across services | High |

### 5.4 What an Event System Would Look Like

Given PyBend's existing patterns, the most natural event system would
hook into `StorableMixin` lifecycle methods:

```
StorableMixin.create()  --> emit "model.created"   event
StorableMixin.update()  --> emit "model.updated"   event
StorableMixin.delete()  --> emit "model.deleted"   event
@expose_route methods   --> emit "model.{method}"  event
```

The `register_model()` function is the natural hook point. It already
runs at startup for every model. Adding event wiring there keeps the
pattern consistent:

```python
# Hypothetical extension to registrar.py
def register_model(model_class, storage=None, event_bus=None):
    # ... existing code ...
    if event_bus:
        model_class._event_bus = event_bus
        # Wrap create/update/delete to emit events
```

---

## 6. Storage Backend as Service Boundary

### 6.1 The AbstractStorage Interface

From `/workspace/src/pybend/core/storage/abstract_storage.py`:

```python
class AbstractStorage(ABC):
    @abstractmethod
    def create_table(self, model_class): ...
    @abstractmethod
    def create(self, model_class, data) -> Any: ...
    @abstractmethod
    def list(self, model_class, sql_filter=None, limit=None, offset=None, populate=None) -> List: ...
    @abstractmethod
    def get(self, model_class, id_=None, as_dict=False, populate=None, **kwargs) -> Any: ...
    @abstractmethod
    def update(self, model_class, id_, data): ...
    @abstractmethod
    def delete(self, model_class, id_): ...
```

This interface is the seam where storage technology can change without
affecting model logic. PyBend ships with two implementations:

1. **SQLiteStorage** (`sqlite_storage.py`) -- connection pool, WAL mode,
   FK hydration, batch collection loading, auto-migration.
2. **JSONStorage** (`json_storage.py`) -- file-based, suitable for
   prototyping.

### 6.2 Remote Storage: The Missing Adapter

For true microservice decomposition, a third storage adapter would be
needed -- one that delegates CRUD operations to a remote service's REST
API instead of a local database:

```python
class RemoteStorage(AbstractStorage):
    """Storage backend that delegates to a remote PyBend service."""

    def __init__(self, base_url: str):
        self.base_url = base_url  # e.g., "http://product-service:5001"

    def create(self, model_class, data):
        tablename = model_class.__tablename__
        response = httpx.post(f"{self.base_url}/{tablename}", json=data)
        return model_class(**response.json())

    def get(self, model_class, id_, **kwargs):
        tablename = model_class.__tablename__
        response = httpx.get(f"{self.base_url}/{tablename}/{id_}")
        return model_class(**response.json())

    # ... list, update, delete similarly
```

This adapter would allow a service to treat a remote model as if it
were local:

```python
# Product service needs User data for OWNER checks
# Instead of importing User model, register a remote stub:
user_app = create_app(
    models=[UserStub],
    storage=RemoteStorage("http://user-service:5002"),
)
```

### 6.3 The FK Hydration Problem

SQLiteStorage already converts foreign key references into URLs (href
hydration). From `sqlite_storage.py`, lines 174-179:

```python
# Hydrate Ref[T] fields as href URLs
for field_name, target_cls in ref_fields:
    val = record.get(field_name)
    if val is not None:
        target_table = getattr(target_cls, '__tablename__', target_cls.__name__.lower())
        record[field_name] = f"{config.API_URL}/{target_table}/{val}"
```

In a microservice world, `config.API_URL` would need to resolve to
the correct remote service. The URL becomes a cross-service reference:

```
Monolith:    http://localhost:5000/users/42
Microservice: http://user-service:5002/users/42
```

This is a configuration change, not an architectural one. The framework
already produces URLs instead of raw IDs, which is the correct pattern
for distributed systems (HATEOAS).

---

## 7. Configuration and Environment

### 7.1 Current Configuration Model

From `/workspace/src/pybend/core/config.py`:

```python
BACKEND = "fastapi"
VERSION = "0.7.0"
HOST = "0.0.0.0"
PORT = 5000
API_URL = f"http://localhost:{PORT}"
SQLITE_DB_FILE = "pybend.db"
JWT_SECRET = os.getenv("PYBEND_JWT_SECRET", "pybend-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.getenv("PYBEND_JWT_EXPIRY_HOURS", "24"))
DEBUG = os.getenv("PYBEND_DEBUG", "true").lower() in ("1", "true")
```

Environment variables override defaults (`PYBEND_PORT`, `PYBEND_API_URL`,
etc.), and `config.configure()` allows programmatic overrides.

### 7.2 Per-Service Configuration Needs

In a microservice deployment, each service needs its own:

| Config | Monolith (shared) | Microservice (per-service) |
|---|---|---|
| `PORT` | Single (5000) | Different per service |
| `API_URL` | `localhost:5000` | Service-specific URL |
| `SQLITE_DB_FILE` | One shared DB | One DB per service |
| `JWT_SECRET` | One secret | Shared across all services |
| `DEBUG` | Global | Per-service |

The `config.configure()` function already supports this:

```python
# Product service
config.configure(port=5001, api_url="http://product-service:5001")

# User service
config.configure(port=5002, api_url="http://user-service:5002")
```

But `config.py` uses module-level globals, so multiple services in the
same process would share state. This is fine for deployment (one service
per process) but problematic for testing (multiple services in one test).

---

## 8. Gap Analysis: What Is Missing

### 8.1 Infrastructure Gaps

```
+-------------------------------------------------------------------+
|                    MICROSERVICE INFRASTRUCTURE                     |
+-------------------------------------------------------------------+
|                                                                   |
|  +------------------+    +------------------+    +--------------+ |
|  | Service Discovery|    | Load Balancing   |    | API Gateway  | |
|  |                  |    |                  |    |              | |
|  | - Consul/etcd    |    | - Round-robin    |    | - Routing    | |
|  | - DNS-based      |    | - Health-aware   |    | - Rate limit | |
|  | - Self-register  |    | - Session sticky |    | - Auth       | |
|  |                  |    |                  |    |              | |
|  | STATUS: MISSING  |    | STATUS: MISSING  |    | STATUS: N/A  | |
|  +------------------+    +------------------+    +--------------+ |
|                                                                   |
|  +------------------+    +------------------+    +--------------+ |
|  | Health Checks    |    | Circuit Breakers |    | Dist. Tracing| |
|  |                  |    |                  |    |              | |
|  | - /health        |    | - Retry logic    |    | - Request ID | |
|  | - Readiness      |    | - Fallbacks      |    | - Span trace | |
|  | - Liveness       |    | - Timeout        |    | - Correlation| |
|  |                  |    |                  |    |              | |
|  | STATUS: MISSING  |    | STATUS: MISSING  |    | STATUS: N/A  | |
|  +------------------+    +------------------+    +--------------+ |
|                                                                   |
|  +------------------+    +------------------+    +--------------+ |
|  | Event Bus        |    | Config Mgmt      |    | Deployment   | |
|  |                  |    |                  |    |              | |
|  | - Pub/sub        |    | - Per-service    |    | - Containers | |
|  | - Event store    |    | - Hot reload     |    | - Orchestrate| |
|  | - Dead letter    |    | - Secrets mgmt   |    | - Scale      | |
|  |                  |    |                  |    |              | |
|  | STATUS: MISSING  |    | STATUS: PARTIAL  |    | STATUS: N/A  | |
|  +------------------+    +------------------+    +--------------+ |
+-------------------------------------------------------------------+
```

### 8.2 Detailed Gap Table

| Capability | Current State | Gap Size | Effort to Close |
|---|---|---|---|
| **Service factory** | `create_app()` builds standalone apps | None | -- |
| **API contracts** | JSON Schema + OpenAPI auto-generated | None | -- |
| **Per-service DB** | `storage=` parameter per model | None | -- |
| **Auth/AuthZ** | JWT + ABAC, standalone package | None | -- |
| **Model registry** | `registered_models` dict, in-process | Small | Add network endpoint |
| **Health endpoint** | Not implemented | Small | Add `/health` route |
| **Schema versioning** | `$id` URL but no version field | Small | Add version to schema |
| **Service client** | No built-in HTTP client for service calls | Medium | Build `RemoteStorage` |
| **Event system** | No pub/sub or event emission | Medium | Hook into StorableMixin |
| **Config per service** | Module globals, env var overrides | Medium | Namespace config |
| **Service discovery** | Not implemented | Large | Integrate Consul/DNS |
| **Circuit breakers** | Not implemented | Large | Add retry/fallback |
| **Distributed tracing** | Not implemented | Large | Add OpenTelemetry |
| **Saga orchestration** | Not implemented | Large | Design transaction protocol |

### 8.3 Effort Estimates by Phase

**Phase 0 -- Quick Wins (days, not weeks):**
- Health check endpoint: `GET /health` returning service metadata
- Schema versioning: add `version` field to `ProtoModel.schema()` output
- Service metadata: expose registered models at `GET /_meta/models`

**Phase 1 -- Service Communication (1-2 weeks):**
- `RemoteStorage` adapter for cross-service model access
- Service client generation from JSON Schema
- Request correlation IDs through middleware

**Phase 2 -- Event System (2-4 weeks):**
- Event emission hooks in `StorableMixin` lifecycle
- Event bus abstraction (Redis Pub/Sub, NATS, or simple HTTP webhooks)
- Event replay and dead-letter handling

**Phase 3 -- Production Infrastructure (4-8 weeks):**
- Service discovery integration
- Circuit breaker middleware
- OpenTelemetry instrumentation
- Container deployment templates (Dockerfile per service)

---

## 9. The Modular Monolith Sweet Spot

### 9.1 Why Not Decompose Today

PyBend's current architecture gives most of the benefits of microservices
without the operational cost:

```
MONOLITH BENEFITS (PyBend has these):
  + Single deployment artifact
  + Shared-memory function calls (no network latency)
  + Transactional consistency (single SQLite DB)
  + Simple debugging (single process, single log stream)
  + No service mesh, no container orchestration, no distributed tracing

MICROSERVICE BENEFITS (PyBend partially has these):
  + Independent deployment per model        --> YES (create_app per model)
  + Independent scaling per model           --> YES (if deployed separately)
  + Technology diversity per model           --> YES (pluggable storage)
  + Fault isolation per model               --> NO  (shared process)
  + Independent team ownership per model    --> PARTIAL (clean boundaries)
```

### 9.2 When to Decompose

The standard triggers for microservice decomposition:

| Trigger | Threshold | PyBend Signal |
|---|---|---|
| Team size | > 8-10 engineers on same codebase | Multiple teams modifying `models/` |
| Deploy frequency | Different models need different deploy cadences | One model changes hourly, others weekly |
| Scale requirements | One model needs 100x more capacity | Product reads >> User writes |
| Fault isolation | One model's failure must not affect others | Comment DB corruption takes down Product |
| Technology fit | One model needs a different DB engine | Product needs Elasticsearch, User needs Postgres |

### 9.3 The Decomposition Path

Because PyBend's boundaries are already clean, the decomposition path
is mechanical, not architectural:

```
Step 1: Identify the model(s) to extract
  - Which model has different scaling / deployment / team ownership needs?

Step 2: Create a new main.py for the extracted service
  - create_app(models=[ExtractedModel], storage="sqlite:///extracted.db")

Step 3: Replace local references with remote ones
  - Where other models reference the extracted model via ListRef/Ref,
    change the storage to RemoteStorage or change href URLs to point
    to the new service.

Step 4: Handle cross-cutting concerns
  - Share JWT secret across services
  - Configure API_URL to point to the correct service
  - Add health checks and service discovery if needed

Step 5: Deploy independently
  - Separate container / process / machine for the extracted service
```

### 9.4 Architecture Diagram: Current vs. Decomposed

```
CURRENT: Modular Monolith
+------------------------------------------------------+
|                    Single Process                      |
|                                                        |
|  create_app(models=[User, Product], ...)              |
|                                                        |
|  +----------+  +----------+  +----------+             |
|  |   User   |  | Product  |  | Comment  |  shared    |
|  |  model   |  |  model   |  |  model   |  SQLite DB |
|  +----------+  +----------+  +----------+             |
|       |              |             |                   |
|       v              v             v                   |
|  +-------------------------------------------------+  |
|  |            registered_models{}                   |  |
|  +-------------------------------------------------+  |
|       |              |             |                   |
|       v              v             v                   |
|  +-------------------------------------------------+  |
|  |           FastAPI Router (auto-generated)        |  |
|  +-------------------------------------------------+  |
|       |                                                |
|       v                                                |
|  +-------------------------------------------------+  |
|  |         JWTAuthMiddleware + ABAC Resolver        |  |
|  +-------------------------------------------------+  |
+------------------------------------------------------+


DECOMPOSED: Microservices
+------------------+  +--------------------+  +-------------------+
|  User Service    |  |  Product Service   |  |  Comment Service  |
|                  |  |                    |  |                   |
| create_app(      |  | create_app(        |  | create_app(       |
|   models=[User]) |  |   models=[Product])|  |   models=[Comment]|
|                  |  |                    |  |   )               |
| SQLite: user.db  |  | SQLite: product.db |  | SQLite: comment.db|
| Port: 5001       |  | Port: 5002         |  | Port: 5003        |
|                  |  |                    |  |                   |
| GET /User        |  | GET /Product       |  | GET /Comment      |
| GET /users       |  | GET /products      |  | GET /comments     |
| POST /users/login|  | POST /products     |  | POST /comments    |
+------------------+  +--------------------+  +-------------------+
         |                      |                       |
         v                      v                       v
+--------------------------------------------------------------+
|                     API Gateway / Load Balancer               |
|  Routes: /users/* -> :5001, /products/* -> :5002, etc.       |
+--------------------------------------------------------------+
         |
         v
+--------------------------------------------------------------+
|                    Frontend (NTT.js)                          |
|  Fetches schemas from gateway, renders dynamically           |
+--------------------------------------------------------------+
```

---

## 10. Proposed CLI Extension

A natural extension of PyBend's tooling would be a CLI command to
extract a service:

```bash
# Spin up a microservice for specific models
pybend service Product Comment --port 5001 --db product.db

# This would internally do:
# 1. Import the specified models
# 2. create_app(models=[Product], join_models=[(Product, Comment)])
# 3. Configure port, storage, JWT
# 4. Run uvicorn
```

The implementation would be straightforward given `create_app()`:

```python
# Hypothetical pybend/cli.py
import importlib
import sys

def service_command(model_names, port, db, jwt_secret):
    """Run a PyBend microservice for the specified models."""
    from pybend.core.app import create_app
    from pybend.core import config

    config.configure(port=port, api_url=f"http://localhost:{port}")

    # Dynamic model import
    models = []
    for name in model_names:
        module_path, class_name = name.rsplit('.', 1)
        module = importlib.import_module(module_path)
        models.append(getattr(module, class_name))

    app = create_app(
        models=models,
        storage=f"sqlite:///{db}",
        jwt_secret=jwt_secret,
    )

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
```

---

## 11. Comparison with Established Microservice Frameworks

### 11.1 PyBend vs. Microservice Frameworks

| Feature | PyBend | Spring Boot | NestJS | FastAPI (raw) |
|---|---|---|---|---|
| Model-driven CRUD | Automatic | Manual/JPA | Manual/TypeORM | Manual |
| API contract generation | JSON Schema + OpenAPI | OpenAPI | OpenAPI (Swagger) | OpenAPI |
| Schema-driven UI | Built-in (NTT.js) | None | None | None |
| Auth/AuthZ | Built-in (ABAC) | Spring Security | Guards/Passport | Manual |
| Service factory | `create_app()` | `@SpringBootApplication` | `NestFactory.create()` | Manual |
| Service discovery | None | Eureka/Consul | None (manual) | None |
| Event bus | None | Spring Cloud Stream | CQRS module | None |
| Circuit breakers | None | Resilience4j | None (manual) | None |
| Health checks | None | Actuator | Terminus | None |

### 11.2 PyBend's Unique Advantage

No framework in the comparison table generates a **working UI** from
model definitions. This is PyBend's differentiator. In a microservice
context, this means:

- Each service automatically has an admin interface
- Schema changes propagate to the UI without frontend deployments
- Service teams get a functional dashboard for free

This reduces the "microservice tax" (the overhead of managing many
services) because each service is immediately observable and
interactable through its auto-generated interface.

---

## 12. Recommendations

### 12.1 Short-Term (Keep the Monolith, Harden Boundaries)

1. **Add health check endpoints.** Trivial to implement, useful even in
   monolith mode for load balancer health probes.

2. **Add a `/_meta` endpoint** exposing registered models, their
   schemas, and dependency graph. This becomes the service registry
   when decomposition happens.

3. **Namespace the config module** so multiple `create_app()` calls in
   the same process do not share state. This enables multi-service
   testing.

4. **Add request correlation IDs** in the JWT middleware. Even in a
   monolith, these help with debugging and become essential in
   distributed systems.

### 12.2 Medium-Term (Prepare for Decomposition)

5. **Build `RemoteStorage`** -- an `AbstractStorage` implementation that
   delegates to a remote PyBend service's REST API. This is the key
   enabler: it lets one service treat another service's models as if
   they were local.

6. **Add lifecycle event hooks** to `StorableMixin`. Even without a full
   event bus, emitting events on create/update/delete enables plugins,
   audit logging, and cache invalidation.

7. **Generate typed client libraries** from JSON Schema. When Service A
   calls Service B, it should use a generated client, not raw HTTP.

### 12.3 Long-Term (Decompose When Needed)

8. **Do not decompose preemptively.** Wait for a concrete trigger (team
   scaling, deployment cadence mismatch, or scaling requirement).

9. **When decomposing, extract one service at a time.** Start with the
   model that has the clearest independent lifecycle (e.g., User/Auth
   is almost always the first extraction).

10. **Use PyBend's existing patterns** for the decomposed services. The
    `create_app()` factory, JSON Schema contracts, and ABAC rules work
    identically whether the service is a module in a monolith or a
    standalone process.

---

## 13. Conclusion

PyBend is architecturally closer to microservice-ready than most
frameworks at its stage. The key primitives -- self-contained app
factory, pluggable storage, auto-generated contracts, model-level auth,
and a clean model registry -- map directly to microservice patterns.
The gaps (service discovery, event bus, circuit breakers) are
infrastructure concerns that belong outside the application framework
and can be filled incrementally.

The strategic recommendation is to **stay monolithic** while **hardening
the seams**. Add health checks, correlation IDs, and the `RemoteStorage`
adapter. These investments pay off immediately (better observability,
better testing) and position the codebase for mechanical decomposition
when a business trigger demands it.

The worst outcome would be to decompose prematurely, paying the
distributed systems tax (network latency, partial failures, eventual
consistency) before the organization needs the benefits (independent
deployment, independent scaling, fault isolation).

PyBend's architecture makes that choice reversible. And that is its
strongest microservice property.

---

## Appendix A: Key Source File References

| File | Relevance |
|---|---|
| `/workspace/src/pybend/core/app.py` | Service factory (`create_app`, `PyBendApp`) |
| `/workspace/src/pybend/core/models/proto_model.py` | Schema generation, model lifecycle |
| `/workspace/src/pybend/core/api/routes_fastapi.py` | Auto-generated CRUD routes |
| `/workspace/src/pybend/core/api/backend.py` | FastAPI backend adapter, JWT middleware |
| `/workspace/src/pybend/core/utils/registrar.py` | Model registry (`registered_models`) |
| `/workspace/src/pybend/core/utils/decorators.py` | `@expose_route` for custom methods |
| `/workspace/src/pybend/core/storage/abstract_storage.py` | Storage interface (pluggable) |
| `/workspace/src/pybend/core/storage/sqlite_storage.py` | SQLite backend with FK hydration |
| `/workspace/src/pybend/core/authorize/rules.py` | ABAC rules (composable, serializable) |
| `/workspace/src/pybend/core/authorize/resolver.py` | Authorization resolver protocol |
| `/workspace/src/pybend/core/authorize/context.py` | Immutable access context |
| `/workspace/src/pybend/core/config.py` | Configuration (env vars, `configure()`) |
| `/workspace/src/pybend/core/models/storable_mixin.py` | CRUD operations, lifecycle hooks |
| `/workspace/src/pybend/static/core/Matrix.js` | Frontend actor/message bus |
| `/workspace/src/pybend/static/core/NTT.js` | Frontend entity system, schema bootstrap |
| `/workspace/src/pybend/example/main.py` | Example app using `create_app()` |
| `/workspace/src/pybend/example/models/product.py` | Example model with relationships |

## Appendix B: Glossary

| Term | Definition |
|---|---|
| **ProtoModel** | Base model class. Generates JSON Schema, injects StorableMixin, handles serialization. |
| **StorableMixin** | CRUD mixin injected into models with `__storable__ = True`. |
| **AbstractStorage** | Interface for storage backends (SQLite, JSON, or custom). |
| **registered_models** | In-process dict mapping tablenames to model classes. |
| **JSON Schema** | The contract returned by `GET /{ModelName}`. Carries types, validation, UI hints, access rules, methods. |
| **ABAC** | Attribute-Based Access Control. Rules compose with `|`, `&`, `~`. |
| **NTT** | Frontend entity system. Creates DynamicClasses from backend schemas. |
| **Matrix** | Frontend actor/message bus. Routes messages to local children or remote services. |
| **create_app()** | One-liner factory that produces a complete ASGI application from a list of models. |
| **@expose_route** | Decorator that turns a model method into an API endpoint. |
| **ListRef[T]** | Type annotation for collection relationships (parent-child via join model). |
| **Ref[T]** | Type annotation for foreign key references. |
| **HATEOAS** | Hypermedia as the Engine of Application State. PyBend's FK hydration produces URLs, not raw IDs. |
