# Backend Architecture Deepening Opportunities

Date: 2026-04-30  
Scope: N3TX backend architecture and backend tests  
Status: candidate RFC material, no implementation yet

## Executive Summary

This report expands the initial architecture exploration into a more complete
set of refactor candidates. The lens is **module deepening**: create smaller,
more stable interfaces that hide larger, internally cohesive implementation
details.

The strongest opportunities are not places where the code is obviously broken.
They are places where a single runtime concept is spread across several shallow
modules, so understanding or testing behavior requires bouncing through many
files.

Recommended investigation order:

| Rank | Candidate | Why first |
|---:|---|---|
| 1 | Route/auth parity boundary | Highest user-visible risk; direct and actor routing duplicate the same API contract. |
| 2 | Storage relationship boundary | Deepest backend complexity; locally testable with SQLite; many bug-prone seams. |
| 3 | Schema contract boundary | Central to “the model is the app”; currently split across pipeline stages and side effects. |
| 4 | App bootstrap transaction | Global state and registration ordering are fragile in tests and runtime reloads. |
| 5 | Authorization policy path | Same policy crosses direct HTTP, actor HTTP, ActorModel, and agent tools. |
| 6 | Agent run lifecycle | Large lifecycle concept spans tools, threads, Matrix, streaming, and Pydantic AI. |

No code changes are proposed here as final designs. Each candidate includes
multiple possible solution directions to support follow-up RFC selection.

---

## Architectural Lens: “Deep Module”

A deep module has a compact interface that hides substantial implementation.
In this codebase, deepening usually means moving from tests like:

```text
test helper A
test helper B
test helper C
hope the composed behavior works
```

to tests like:

```text
given model + request/config
when public boundary is exercised
then observable schema/API/storage behavior is correct
```

Deepening is especially valuable where:

- a concept has multiple entrypoints but one intended contract
- modules duplicate logic to preserve parity
- tests mock implementation details rather than verifying behavior
- correctness depends on global registries, import ordering, or hidden mutation
- a future AI agent must inspect many small helpers to understand one behavior

Dependency categories used below:

| Category | Meaning | Testing shape |
|---|---|---|
| In-process | Pure computation or memory state | Test directly through public boundary. |
| Local-substitutable | I/O with local stand-in | Use local SQLite/temp files/in-memory adapters. |
| Remote but owned | Network boundary to owned system | Define a port; use in-memory adapter in tests. |
| True external | Third-party dependency | Mock at boundary. |

---

## Candidate 1: Route Contract Parity — Direct FastAPI vs Actor HTTP

### Cluster

| Area | Files |
|---|---|
| Direct HTTP routes | `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` |
| Actor HTTP routes | `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` |
| Actor CRUD handling | `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py` |
| Tier-1 auth | `packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py` |
| Tests | `test_routes.py`, `test_network_api.py`, `test_auth_interceptor.py`, examples tests |

### Current Flow

```text
                 same model definitions, same public API contract

  Level 1/2 direct routing                    Level 3 actor routing
  ------------------------                    ---------------------

  FastAPI route handler                       FastAPI route handler
        |                                           |
        | direct function call                      | TX(name, target, data, meta)
        v                                           v
  StorableMixin / custom method              NetworkAPI.request()
        |                                           |
        v                                           v
  model_response()                           Matrix -> ActorModel.handler_crud()
        |                                           |
        v                                           v
  HTTP response                              TX reply -> HTTP response
```

The architecture intentionally supports three levels of routing. The issue is
that Level 1/2 and Level 3 preserve parity by duplicating route behavior rather
than sharing a deeper API-contract module.

### Current-State Snippets

Direct route create logic owns auth, FK injection, protected-field injection,
storage write, serialization, and HTTP error conversion:

```python
# routes_fastapi.py
async def create_instance(request: Request, data: param_class, parent_id: int = None) -> model_class:
    ctx = _build_context(request, model_class, "create", parent_id=parent_id)
    _resolver.authorize(ctx)

    data_dict = flatten_refs(data)
    if parent_id:
        fk_field = f"{model_class.__owner__.__name__.lower()}_id"
        data_dict[fk_field] = parent_id

    protected = getattr(model_class, '__protected_fields__', None) or \
                getattr(param_class, '__protected_fields__', set())
    if 'user_owner' in protected:
        user = _get_user(request)
        if user and user.get('user_id'):
            data_dict['user_owner'] = user['user_id']

    instance = model_class(**data_dict)
    result = model_class.create(instance)
    return result.model_response() if result else result
```

Actor route create logic mirrors the request-shaping side, then sends TX:

```python
# network_api.py
async def create_instance(request: Request, data: param_class, parent_id: int = None, ...):
    user = _get_user(request)
    data_dict = flatten_refs(data)

    if parent_id and has_parent:
        fk_field = f"{_cls.__owner__.__name__.lower()}_id"
        data_dict[fk_field] = parent_id

    protected = getattr(_cls, '__protected_fields__', None) or \
                getattr(_param_cls, '__protected_fields__', set())
    if 'user_owner' in protected and user and user.get('user_id'):
        data_dict['user_owner'] = user['user_id']

    response = await api_adapter.request(
        TX(name='create', source=api_adapter.addr, target=_addr,
           data=data_dict, meta={'user': user, 'model_cls': _cls}),
        timeout=30.0,
    )
    return _response_or_raise(response)
```

The actor path also contains explicit comments that it mirrors direct behavior:

```python
# network_api.py
# Post-filter by parent FK (mirrors Level 1/2 routes_fastapi.py behavior)
if parent_id and _has_parent:
    fk_field = f"{_cls.__owner__.__name__.lower()}_id"
    ...
```

Tests currently validate helpers and route construction more than parity:

```python
# test_routes.py
class TestGetUser:
    def test_extracts_user(self): ...

class TestBuildContext:
    def test_returns_access_context(self): ...

class TestRegisterRoute:
    def test_get(self): ...
```

```python
# test_network_api.py
# UNIT TESTS — behavior validation
#   - test_get_user_extracts_from_request_state
#   - test_response_or_raise_returns_data_on_success
#   - test_parse_method_args_extracts_simple_params
#
# INTEGRATION TESTS (partial) — route generation
#   - test_create_route_sends_create_tx
#   - test_update_route_strips_protected_fields
```

### Friction Signal

To understand whether `POST /products/{id}/comment` behaves the same in direct
and actor routing, one must inspect:

1. direct custom route generation
2. actor custom route generation
3. argument parsing in both route modules
4. auth resolver vs interceptor vs `ActorModel._authorize()`
5. model method execution
6. storage response serialization
7. SSE conversion if streaming

That is too much surface area for one public API concept.

### Coupling Analysis

| Shared concept | Direct owner today | Actor owner today | Risk |
|---|---|---|---|
| CRUD path shape | `register_routes()` | `create_api_routes()` | Route drift. |
| Request body parsing | route factories | `_parse_method_args()` | Different validation/error behavior. |
| `user_owner` injection | direct create route | actor create route | Ownership bugs. |
| Parent FK injection | direct create/update/list | actor create/update/list | Parent-child parity drift. |
| Custom method `user` injection | `_resolve_user()` | `_parse_method_args()` | Tool/direct/actor user mismatch. |
| SSE format | `_sse_frame()` direct | `_sse_frame()` actor | Frontend stream incompatibility. |
| Error conversion | `HTTPException` locally | `_response_or_raise()` | Different status/detail body. |

### Dependency Category

**Remote but owned / Ports & Adapters** conceptually: Level 3 is an HTTP → TX
adapter over an owned Matrix boundary. It is still locally testable with
FastAPI `TestClient`, file-backed SQLite, and in-process Matrix.

### Test Impact

Boundary tests should replace or reduce helper tests whose only value is
protecting duplicated implementation details.

| Current tests | Keep? | Replacement direction |
|---|---:|---|
| `_get_user`, `_build_context`, `_response_or_raise` helper tests | Some | Keep only edge cases; move primary confidence to route boundary. |
| “route sends TX” tests | Reduce | Assert final HTTP behavior instead of TX shape unless TX shape is itself public. |
| direct route factory tests | Reduce | Use direct-vs-actor parity suite. |
| auth interceptor unit tests | Keep core policy edge cases | Add cross-entrypoint auth behavior tests. |

### Proposed Solution Directions

#### Option A — API Operation Compiler

Create one in-process module that compiles model metadata into an operation
description. Direct and actor routes both consume this description.

```python
@dataclass(frozen=True)
class ApiOperation:
    action: str
    path: str
    method: str
    model_class: type
    requires_id: bool = False
    has_parent: bool = False
    stream: bool = False

class ApiContract:
    def operations_for(self, models: dict[str, type]) -> list[ApiOperation]: ...
    def parse_request(self, operation, request, body, path_params) -> OperationInput: ...
```

Direct route:

```python
op_input = contract.parse_request(op, request, data, path_params)
result = direct_executor.execute(op, op_input)
return response_adapter.http(result)
```

Actor route:

```python
op_input = contract.parse_request(op, request, data, path_params)
tx = tx_adapter.to_tx(op, op_input)
result = await api.request(tx)
return response_adapter.http(result)
```

Pros:

- Highest parity guarantee.
- Route shape and request semantics become one source of truth.
- Boundary tests can exercise `ApiContract` once and both adapters separately.

Cons:

- Moderate migration cost.
- Needs careful FastAPI integration for dynamic signatures/response models.

#### Option B — Parity Test Harness First

Do not refactor production code immediately. Build a test harness that creates
the same app twice: once direct, once actor.

```python
def build_pair(models, joins, db_factory):
    direct = create_app(models=models, join_models=joins, storage=db_factory("direct"))
    actor = create_app(models=models, join_models=joins, storage=db_factory("actor"), routing="actor")
    return TestClient(direct), TestClient(actor)

@pytest.mark.parametrize("method,path,body", [...])
def test_direct_actor_parity(method, path, body):
    direct_resp = request(direct, method, path, body)
    actor_resp = request(actor, method, path, body)
    assert normalize(direct_resp) == normalize(actor_resp)
```

Pros:

- Lowest risk; exposes current drift before refactor.
- Can guide future extraction.
- Produces immediate confidence for backend behavior.

Cons:

- Does not reduce duplication by itself.
- Test normalization can hide meaningful differences if not designed carefully.

#### Option C — Shared Request Normalizer + Separate Executors

Extract only the duplicated request-shaping concerns:

```python
class RequestNormalizer:
    def crud_payload(self, model_class, action, body, *, user, parent_id=None) -> dict: ...
    def method_payload(self, method, body, query, *, user) -> dict: ...
```

Direct routes still call storage/methods directly. Actor routes still send TX.
But parent FK injection, protected-field stripping, argument parsing, and user
resolution are shared.

Pros:

- Smaller change than full operation compiler.
- Addresses the most obvious duplicated logic.

Cons:

- Route shape, status conversion, and stream parity remain split.
- May become another shallow helper if not paired with boundary tests.

### Recommendation

Start with **Option B** to establish the behavioral boundary, then evolve toward
**Option A** if parity tests reveal meaningful duplication pressure. Avoid Option
C unless the team wants a deliberately incremental first extraction; it risks
creating one more helper without fully deepening the API module.

---

## Candidate 2: Storage Relationships, Hydration, Populate, and Migration

### Cluster

| Area | Files |
|---|---|
| Storage CRUD/hydration | `sqlite_storage.py` |
| Schema/table generation | `sqlite_migration.py` |
| Model storage facade | `storable_mixin.py` |
| Relationship model generation | `proto_model.generate_join_model()` |
| Type/field discovery | `utils/introspection.py`, `models/ref.py` |
| Populate parsing/traversal | `utils/populate.py`, `SQLiteStorage._populate_fields()` |
| Tests | `test_sqlite_storage.py`, `test_populate.py`, `test_introspection.py`, `test_sqlite_helpers.py` |

### Current Flow

```text
Model annotations
  |  Ref[T], ListRef[T], __fk_models__, __owner__, __tagname__
  v
generate_join_model() + register_model()
  |  creates join model and tables
  v
SQLiteMigration
  |  decides physical columns
  v
SQLiteStorage.create/list/get/update
  |  serializes JSON, rewrites refs, builds href arrays
  v
Populate overlay
  |  replaces href fields with {data, meta} or object payloads
  v
model_response()
```

The behavior is cohesive — “persist and retrieve model relationships” — but
the implementation responsibility is spread across storage, migration,
introspection, model generation, and URL conventions.

### Current-State Snippets

`list()` handles SQL filtering, pagination, row hydration, JSON fields, Ref href
conversion, ListRef href arrays, and populate:

```python
# sqlite_storage.py
def list(self, model_class, sql_filter=None, limit=None, offset=None,
         populate=None, ids=None):
    table_name = _validate_identifier(model_class.__tablename__)
    list_fields = get_list_fields(model_class)
    ref_fields = get_ref_fields(model_class)

    select_sql = f"SELECT * FROM {table_name}"
    ...
    cursor.execute(select_sql, paginated_params)
    rows = cursor.fetchall()

    for row in rows:
        record = dict(zip(columns, row))
        _deserialize_json_fields(model_class, record)

        for field_name, target_cls in ref_fields:
            val = record.get(field_name)
            if val is not None:
                target_table = getattr(target_cls, '__tablename__', target_cls.__name__.lower())
                record[field_name] = f"{config.API_URL}/{target_table}/{val}"

    if list_fields:
        # Batch-hydrate collection fields
        ...

    results = [model_class(**record) for record in records]

    if populate and not populate.is_empty:
        self._populate_fields(model_class, results, populate, conn)
```

`get()` repeats similar hydration logic with different control flow:

```python
# sqlite_storage.py
for field_name, target_cls in get_ref_fields(model_class):
    val = data.get(field_name)
    if val is not None:
        target_table = getattr(target_cls, '__tablename__', target_cls.__name__.lower())
        data[field_name] = f"{config.API_URL}/{target_table}/{val}"

for field_name, child_class in get_list_fields(model_class):
    effective_cls = getattr(model_class, '__fk_models__', {}).get(field_name, child_class)
    child_table = _validate_identifier(effective_cls.__tablename__)
    ...
    data[field_name] = [
        f"{config.API_URL}/{model_class.__tablename__}/{id}/{field_name}/{row[0]}"
        for row in child_rows
    ]
```

Populate adds another relationship traversal implementation:

```python
# sqlite_storage.py
def _populate_fields(self, model_class, instances, populate, conn, _visited=None):
    list_fields = get_list_fields(model_class)
    ref_fields = get_ref_fields(model_class)

    for field_name, child_class in list_fields:
        if not populate.should_populate(field_name):
            continue
        effective_cls = getattr(model_class, '__fk_models__', {}).get(field_name, child_class)
        ...
        cursor.execute(
            f"SELECT * FROM {child_table} WHERE {fk_col} IN ({placeholders})",
            parent_ids,
        )
        ...
        inst.__dict__['_populated'][field_name] = populated_wrapper
```

Existing storage tests are valuable but mostly operation-specific:

```python
# test_sqlite_storage.py
class TestCreate:
    def test_simple_create(self, storage, tmp_db): ...

class TestList:
    def test_pagination(self, storage, tmp_db): ...

class TestGet:
    def test_as_dict(self, storage, tmp_db): ...

class TestMigrateTable:
    def test_adds_missing_column(self, storage, tmp_db): ...
```

### Friction Signal

Relationship semantics are not visible from one boundary. A change to how a
`ListRef[Comment]` field behaves may require touching:

- model annotation handling
- join model generation
- registration metadata
- migration columns
- storage insert filtering
- storage read hydration
- populate recursion
- response URL generation
- frontend path assumptions

This is exactly the kind of seam where local unit tests pass while integrated
relationship behavior regresses.

### Coupling Analysis

| Relationship concern | Current owner(s) | Why coupled |
|---|---|---|
| `Ref[T]` storage format | `ProtoModel`, `SQLiteMigration`, `SQLiteStorage` | Annotation must match physical column and response href. |
| `ListRef[T]` collection field | `introspection`, generated join model, storage hydration | Field is not a column but affects reads/routes. |
| Join model parent FK | `generate_join_model`, registrar, migration, storage | FK naming convention must match everywhere. |
| Populate | `utils.populate`, storage, dump pipeline | Parse/tree/depth affects storage queries and response overlay. |
| JSON list/dict fields | introspection, storage serialization, migration | Need same field detection on write/read/table creation. |

### Dependency Category

**Local-substitutable**. SQLite file databases under `tmp_path` are already the
right test substitute. Avoid `:memory:` for tests that touch migration because
the migration layer opens its own connections.

### Test Impact

| Current tests | Keep? | Replacement direction |
|---|---:|---|
| Simple CRUD tests | Keep a few smoke tests | Boundary suite should cover CRUD as part of relationship roundtrip. |
| `test_populate.py` parser/unit tests | Reduce | Keep parser edge cases; move traversal confidence to storage boundary. |
| `test_introspection.py` type helper tests | Reduce | Keep exotic typing cases; test normal behavior via model roundtrip. |
| `test_sqlite_helpers.py` FK helper tests | Reduce | Assert generated join relationships through actual table + read. |

### Proposed Solution Directions

#### Option A — RelationshipMapper Owned by Storage

Create a deep internal component that owns all relationship metadata decisions
for SQLite storage.

```python
class RelationshipMapper:
    def inspect(self, model_class: type) -> RelationshipPlan: ...
    def storage_fields(self, model_class: type) -> list[str]: ...
    def hydrate_record(self, model_class: type, record: dict) -> dict: ...
    def collection_query(self, parent_cls, field_name) -> CollectionQuery: ...
```

Storage usage:

```python
plan = self.relationships.inspect(model_class)
fields = plan.storage_fields
record = plan.hydrate_row(row)
collections = plan.load_collections(conn, parent_ids)
```

Pros:

- Keeps SQLiteStorage as the deep module boundary while simplifying internals.
- Makes migration/storage decisions share one relationship plan.
- Retains current public `StorageInterface`.

Cons:

- Still SQLite-specific unless generalized carefully.
- Needs careful migration path to avoid splitting relationship logic again.

#### Option B — Repository Boundary per Model Graph

Introduce a higher-level repository that treats a model plus its relationships
as the unit of persistence.

```python
class ModelRepository:
    def create(self, model_class, data) -> ProtoModel: ...
    def list(self, model_class, query: QuerySpec) -> Page | list[ProtoModel]: ...
    def get(self, model_class, id: int, query: QuerySpec) -> ProtoModel | None: ...
```

SQLite becomes an adapter under the repository:

```text
StorableMixin -> ModelRepository -> SQLiteUnitOfWork -> SQL tables
```

Pros:

- Deepest conceptual boundary: callers no longer know about hydration/populate.
- Opens future path for alternate backends to implement the same graph behavior.

Cons:

- Larger refactor.
- Risks duplicating `AbstractStorage` unless storage abstraction is retired or reshaped.

#### Option C — Boundary Tests First, Minimal Internal Consolidation

Add a `test_relationship_storage_boundary.py` suite with one canonical graph:

```python
class User(ProtoModel): ...
class Product(ProtoModel):
    owner: Ref[User]
    comments: ListRef[Comment] = Field(default=[])
    metadata: dict = Field(default={})

class Comment(ProtoModel):
    parent_id: Optional[Ref['self']] = None
```

Exercise:

| Behavior | Assertion |
|---|---|
| migration | tables contain expected scalar/FK/JSON columns |
| create/read | JSON fields roundtrip as Python values |
| `Ref` | response emits canonical href |
| `ListRef` | response emits parent-scoped href array |
| populate | response overlays `{data, meta}` correctly |
| nested populate | respects depth and cycle prevention |

Pros:

- Immediate safety net.
- Clarifies the actual desired contract before extraction.

Cons:

- Does not by itself reduce code duplication in `list()`, `get()`, populate.

### Recommendation

Use **Option C** first to lock the relationship contract, then implement
**Option A**. Option B is attractive long-term, but it is a larger storage API
redesign and should wait until the boundary tests reveal whether the existing
`AbstractStorage` interface is fundamentally too shallow.

---

## Candidate 3: Schema Generation Pipeline and Metadata Side Effects

### Cluster

| Area | Files |
|---|---|
| Model base/schema cache | `proto_model.py` |
| Schema stages | `proto_schema.py` |
| Type/reference introspection | `utils/introspection.py` |
| Access serialization | `authorize/schema.py` |
| Widget extension | `widgets/schema_ext.py` |
| UI/agent schema extensions | `n3tx_ui/mixin.py`, `n3tx_agents/schema_ext.py` |
| Tests | `test_proto_schema.py`, widget schema tests, agent schema tests |

### Current Flow

```text
ProtoModel.schema()
  |
  v
proto_schema.run_pipeline(cls)
  |
  +-- base          Pydantic schema + Ref/selfref patching
  +-- strip_hidden  remove hidden fields
  +-- methods       inspect @expose_route methods
  +-- defs          collect referenced models and mutate $defs
  +-- access        serialize ABAC rules
  +-- widget        external package stage
  +-- ui            field and model UI metadata
  +-- agent/view    external package stages if imported
  +-- metadata      $schema, $id, __name__, __tablename__
  |
  v
cached deep copy
```

### Current-State Snippets

`ProtoModel.schema()` looks small, but hides global pipeline state and class
side effects:

```python
# proto_model.py
@classmethod
def schema(cls) -> Dict[str, Any]:
    if cls in ProtoModel._schema_cache:
        return copy.deepcopy(ProtoModel._schema_cache[cls])

    s = proto_schema.run_pipeline(cls)

    ProtoModel._schema_cache[cls] = s
    return copy.deepcopy(s)
```

Method schema generation lives on `ProtoModel` and records referenced models as
a side effect:

```python
# proto_model.py
def __n3tx_methods_json_signature__(cls) -> dict:
    for method_name in dir(cls):
        method = getattr(cls, method_name)
        if not (callable(method) and hasattr(method, '__endpoint__')):
            continue

        sig = inspect.signature(method)
        type_hints = get_type_hints(method, globalns=method.__globals__, localns=locals())
        ...
        parameters[name] = pydantic_schema_for_type(ptype)
        record_model_type(cls, ptype)
```

The pipeline is extensible and testable, but the public schema contract emerges
from multiple stages:

```python
# proto_schema.py
def run_pipeline(cls, pipeline: str = 'default') -> dict:
    stages = _pipelines.get(pipeline)
    _, seed_fn = stages[0]
    s = seed_fn(cls)
    for _, stage_fn in stages[1:]:
        s = stage_fn(cls, s)
    return s
```

Existing tests intentionally test stages independently:

```python
# test_proto_schema.py
"""
Each stage is tested independently as a pure dict -> dict function,
then the full pipeline is verified against ProtoModel.schema() output.
"""

class TestBase:
    def test_selfref_patched(self): ...

class TestMethods:
    def test_exposed_method_present(self): ...

class TestDefs:
    def test_adds_defs_for_referenced_model(self): ...
```

### Friction Signal

The pipeline decomposition looks clean locally, but the real schema contract is
not each stage. The contract is what the frontend, API, tools, and agents see
from `GET /{ClassName}`. Bugs are likely to happen in interactions:

- method signature records a referenced model
- `$defs` collection reads that side effect
- access/ui/widget extensions mutate the same properties
- external packages must be imported before model classes for mixin/schema stages
- cached schemas can outlive dynamic test model changes

### Coupling Analysis

| Schema concern | Current owner(s) | Risk |
|---|---|---|
| Method signature | `ProtoModel.__n3tx_methods_json_signature__` | Coupled to tools, routes, frontend method buttons. |
| Referenced models | `introspection`, `ProtoModel._referenced_models`, `defs` stage | Hidden side effects affect `$defs`. |
| Extension ordering | `proto_schema._pipelines`, import-time decorators | Import order changes output. |
| Field UI/access metadata | core stage + widgets + UI package | Multiple stages mutate same field definitions. |
| Cache | `ProtoModel._schema_cache` | Tests/dynamic model definitions can see stale contract. |

### Dependency Category

**In-process**.

### Test Impact

| Current tests | Keep? | Replacement direction |
|---|---:|---|
| Stage unit tests | Reduce | Keep only pipeline extension insertion/error edge cases. |
| Widget/agent extension tests | Keep focused package tests | Add full schema-contract tests including all imported extensions. |
| Method signature tests | Move upward | Assert complete method entries in final schema. |

### Proposed Solution Directions

#### Option A — SchemaCompiler Deep Module

Wrap the pipeline, method extraction, referenced model collection, extension
ordering, and cache behind one explicit compiler.

```python
class SchemaCompiler:
    def compile(self, model_class: type, *, profile: str = "frontend") -> dict: ...
    def invalidate(self, model_class: type | None = None) -> None: ...
    def describe_pipeline(self, profile: str = "frontend") -> list[str]: ...
```

`ProtoModel.schema()` becomes a small facade:

```python
@classmethod
def schema(cls):
    return default_schema_compiler.compile(cls)
```

Pros:

- Gives the schema system a named owner.
- Centralizes cache invalidation and extension profiles.
- Creates an obvious boundary for schema contract tests.

Cons:

- Needs migration from module-level `proto_schema` functions.
- Must preserve extension API compatibility.

#### Option B — Contract Snapshot Harness

Keep pipeline internals for now, but define canonical model fixtures and assert
their full schema output shape.

```python
def assert_schema_contract(schema):
    assert schema["$id"].endswith("/Product")
    assert schema["methods"]["comment"]["parameters"]["comment"]
    assert schema["$defs"]["Comment"]["access"]
    assert schema["properties"]["price"]["ui"]["widget"] == "currency"
```

Pros:

- Fastest path to behavior confidence.
- Avoids premature redesign of extension API.

Cons:

- Does not solve hidden side effects or global cache complexity.

#### Option C — Schema Profiles with Explicit Inputs

Instead of one global default pipeline, define named profiles with explicit
consumers:

```python
schema = SchemaProfile.frontend().compile(Product)
schema = SchemaProfile.llm_tools().compile(Product)
schema = SchemaProfile.openapi().compile(Product)
```

Pros:

- Clarifies why stages exist.
- Prevents frontend-only metadata from leaking into LLM/tool schemas if not wanted.

Cons:

- Larger conceptual shift.
- Could add complexity if the only real profile today is frontend schema.

### Recommendation

Start with **Option B** to define the schema boundary tests, then adopt **Option
A** if schema complexity continues to grow. Avoid Option C until there are at
least two consumers with genuinely different schema needs.

---

## Candidate 4: App Bootstrap, Registration, Global Registries, and Matrix Sync

### Cluster

| Area | Files |
|---|---|
| App builder | `app.py` |
| Registration | `utils/registrar.py` |
| Join model generation | `proto_model.generate_join_model()` |
| Actor registry | `n3tx_actors.matrix`, `ActorModel` auto-registration |
| Route backend | `api/backend.py`, `routes_fastapi.py`, `network_api.py` |
| Tests | registrar tests, app bootstrap tests, examples tests |

### Current Flow

```text
N3TXApp(...)
  |
  +-- collect models and join pairs
  +-- resolve storage
  +-- detect agent infrastructure models
  +-- prepare_model() for each model
  +-- generate_join_model() for each join
  +-- clear global registered_models and join_models
  +-- apply_registration() side effects
  +-- maybe provision app agent
  +-- create FastAPIBackend
  +-- direct: backend.register_routes(registered_models)
  +-- actor: sync Matrix children, register NetworkAPI, include actor routes
```

### Current-State Snippets

`app.py` explicitly splits preparation and registration:

```python
# app.py
preparations = []
for model_class, per_model_storage in self._models:
    effective_storage = _resolve_storage(per_model_storage) if per_model_storage else self._storage
    preparations.append(prepare_model(model_class, storage=effective_storage))

for parent, child in self._join_pairs:
    join_model = generate_join_model(parent, child)
    preparations.append(prepare_model(join_model, storage=self._storage))

registered_models.clear()
join_models.clear()
for result in preparations:
    apply_registration(result)
```

The registrar has a clean-looking interface but performs crucial global side
effects:

```python
# registrar.py
registered_models: Dict[str, Type[Any]] = {}
join_models: Dict[tuple[str, str], Type[Any]] = {}

def apply_registration(result: RegistrationResult) -> None:
    model = result.model_class
    if result.is_join and result.join_key:
        join_models[result.join_key] = model

    if result.is_storable:
        model.set_storage(result.storage)
        model.create_table()
        if hasattr(result.storage, 'migrate_table'):
            result.storage.migrate_table(model)

    registered_models[result.tablename] = model
```

Actor routing has a Matrix re-sync step because classes can auto-register before
storage is attached:

```python
# app.py
for model_cls in registered_models.values():
    if isinstance(model_cls, type) and issubclass(model_cls, Actor):
        matrix.register(model_cls)

api = NetworkAPI()
matrix.register(api)
api.use(auth_interceptor, on='request')
backend.app.include_router(create_api_routes(api, registered_models))
```

### Friction Signal

Bootstrap correctness is transactional, but current tests often validate pieces:
preparation, registration, route creation, Matrix behavior. The real guarantee
is: after `create_app()`, what are the live classes, tables, routes, Matrix
children, and agent infrastructure?

Global mutable state makes this hard to reason about in tests:

- `registered_models`
- `join_models`
- Matrix children
- schema caches
- package import-time mixin/actor registration

### Dependency Category

**Local-substitutable** for SQLite; **In-process** for registries and Matrix.

### Test Impact

| Current tests | Keep? | Replacement direction |
|---|---:|---|
| registrar helper tests | Reduce | Test app build as the public transaction. |
| Matrix registration tests | Keep actor-specific edge cases | Add actor app bootstrap assertions. |
| examples tests | Keep | Add narrower bootstrap boundary tests for fast feedback. |

### Proposed Solution Directions

#### Option A — AppManifest Build Artifact

Make `N3TXApp.build()` produce and use an explicit manifest describing the full
application before side effects are applied.

```python
@dataclass
class AppManifest:
    models: dict[str, type]
    join_models: dict[tuple[str, str], type]
    storage_by_model: dict[type, AbstractStorage]
    routing: Literal["direct", "actor"]
    agent_models: list[type]

class AppBuilder:
    def plan(self) -> AppManifest: ...
    def apply(self, manifest: AppManifest) -> BuiltApp: ...
```

Pros:

- Makes bootstrap inspectable and testable before side effects.
- Gives AI/devs a single object to understand “what will be live.”

Cons:

- Still must apply global state for backward compatibility.

#### Option B — AppRuntime Owns Registries Instead of Globals

Move registries into an app runtime object and keep globals as compatibility
views.

```python
class AppRuntime:
    registered_models: dict[str, type]
    join_models: dict[tuple[str, str], type]
    matrix: Matrix
    storage: AbstractStorage
```

Pros:

- Strong test isolation.
- Enables multiple apps in one process more safely.

Cons:

- Larger breaking-risk area; many modules import global registries today.

#### Option C — Bootstrap Boundary Tests + State Reset Fixture

Keep production code mostly unchanged, but define a canonical fixture that resets
all known global state and asserts built runtime behavior.

```python
def test_actor_bootstrap_uses_registered_storage_classes(tmp_path):
    app = create_app(models=[Product, User], storage=f"sqlite:///{tmp_path}/x.db", routing="actor")
    assert registered_models["products"].storage is not None
    assert matrix.has("products")
```

Pros:

- Immediate safety without redesign.
- Documents global-state cleanup requirements.

Cons:

- Does not reduce global-state coupling.

### Recommendation

Prefer **Option A** as the eventual deepening target. It gives the app bootstrap
process a clear inspectable boundary without immediately requiring removal of
global registries. Pair it with **Option C** tests first.

---

## Candidate 5: Authorization as One Policy Path Across Direct, Actor, and Tools

### Cluster

| Area | Files |
|---|---|
| Core policy | `packages/n3tx-core/src/n3tx_core/authorize/*` |
| Direct HTTP auth | `routes_fastapi.py` |
| Actor Tier 1 | `auth_interceptor.py` |
| Actor Tier 2 | `ActorModel._authorize()` / `handler_crud()` |
| Agent tools | `n3tx_agents/tools.py`, `AgentMixin` |
| Tests | core auth tests, actor auth tests, tool call auth tests |

### Current Flow

```text
Same __access__ rules
      |
      +-- direct HTTP route -> DefaultResolver.authorize/sql_filter_for
      |
      +-- actor HTTP route -> auth_interceptor -> ActorModel._authorize
      |
      +-- agent tool call -> generated tool function -> TX meta user -> ActorModel
```

### Current-State Snippets

Direct route list computes an auth SQL filter before storage:

```python
# routes_fastapi.py
ctx = _build_context(request, model_class, "list", parent_id=parent_id)
try:
    auth_filter = _resolver.sql_filter_for(ctx)
except AccessDenied as e:
    raise HTTPException(status_code=403, detail=str(e))

result = target_cls.list(sql_filter=auth_filter, limit=limit, offset=offset, populate=pop_spec)
```

Custom direct methods either use method-level access or model resolver:

```python
# routes_fastapi.py
def _check_access(request, model_class, action, resource=None):
    ctx = _build_context(request, model_class, action, resource=resource)
    if custom_access:
        if not custom_access.evaluate(ctx):
            raise AccessDenied(...)
    else:
        _resolver.authorize(ctx)
```

Actor routes preserve user data in TX metadata:

```python
# network_api.py
TX(
    name='update', source=api_adapter.addr, target=_addr,
    data=data_dict,
    meta={'user': user, 'model_cls': _cls},
)
```

### Friction Signal

The two-tier actor design is documented and intentional. The friction is that
the same policy result must be preserved through multiple transports and action
mappings. It is not obvious from one test whether `OWNER | ROLE('admin')` works
identically for:

- direct `PUT /comments/1`
- actor `PUT /comments/1`
- agent tool `comments_update(id=1, ...)`
- custom method with `access=...`

### Dependency Category

**In-process**.

### Test Impact

| Current tests | Keep? | Replacement direction |
|---|---:|---|
| rule composition tests | Keep | These are true unit tests for policy primitives. |
| route/interceptor per-layer tests | Reduce | Add cross-entrypoint policy matrix tests. |
| tool auth tests | Keep targeted LLM/tool behavior | Share policy fixture with direct/actor tests. |

### Proposed Solution Directions

#### Option A — Authorization Gateway

Centralize action mapping, context creation, SQL filter generation, and error
conversion into one module consumed by direct, actor, and tools.

```python
class AuthorizationGateway:
    def context(self, *, user, action, model_class, resource=None, parent_id=None) -> AccessContext: ...
    def authorize(self, context: AccessContext, override: AccessRule | None = None) -> None: ...
    def list_filter(self, context: AccessContext) -> tuple[str, list] | None: ...
```

Pros:

- Keeps `authorize` package pure while centralizing N3TX integration.
- Reduces duplicated context/user/action mapping.

Cons:

- Must respect current separation: `authorize` itself has zero N3TX imports.

#### Option B — Policy Parity Matrix Tests

Define a canonical model and assert the same access rules through all entrypoints.

| Rule | Direct | Actor | Tool |
|---|---:|---:|---:|
| ANYONE read | pass | pass | pass |
| AUTHENTICATED create | pass with token, fail anonymous | same | same |
| OWNER update | owner pass, other fail | same | same |
| ROLE admin delete | admin pass, user fail | same | same |
| custom method access | pass/fail | same | same |

Pros:

- Reveals parity drift without redesign.
- Provides safety net for route/auth refactors.

Cons:

- Does not simplify call paths by itself.

#### Option C — Treat Authorization as Part of API Operation Compiler

If Candidate 1 adopts an API operation compiler, auth context and policy could
be part of that operation pipeline rather than a standalone gateway.

Pros:

- Avoids another separate boundary.
- API request semantics and auth semantics are often inseparable.

Cons:

- Agent tool calls are not always HTTP API operations, so the abstraction must
  still support TX/tool entrypoints.

### Recommendation

Implement **Option B** first. If Candidate 1 proceeds, fold this into the same
boundary. If not, use **Option A** as a focused deepening step.

---

## Candidate 6: Agent Run Lifecycle — Tools, Threads, Matrix, and Pydantic AI

### Cluster

| Area | Files |
|---|---|
| Agent lifecycle | `packages/n3tx-agents/src/n3tx_agents/mixin.py` |
| Tool discovery/execution | `packages/n3tx-agents/src/n3tx_agents/tools.py` |
| Agent model | `packages/n3tx-agents/src/n3tx_agents/actor.py` |
| Thread persistence | `packages/n3tx-agents/src/n3tx_agents/thread.py` |
| Actor transport | `Actor.root()`, Matrix request/stream |
| External engine | Pydantic AI |
| Tests | `test_mixin.py`, `test_agent_actor.py`, `test_thread.py`, streaming tool tests |

### Current Flow

```text
AgentActor.run(task)
  |
  v
AgentMixin.run/agentic
  |
  +-- resolve LLM/config/constraints
  +-- load thread history if thread_id
  +-- discover_tools(actor addresses, root)
  +-- create dynamic Pydantic AI tool functions
  +-- run Pydantic AI agent loop
  +-- route tool calls through Matrix TX request/stream
  +-- persist thread messages
  +-- return answer/usage/messages
```

### Friction Signal

The runtime concept is one “agent run,” but understanding it requires following
configuration cascade, tool schema discovery, dynamic function generation,
Matrix request correlation, auth metadata, streaming collapse, thread CRUD, and
Pydantic AI behavior.

### Dependency Category

**True external / Mock** for real LLM providers. Tests should continue using
Pydantic AI `TestModel` or explicit model doubles.

### Test Impact

| Current tests | Keep? | Replacement direction |
|---|---:|---|
| ToolSpec/function generation unit tests | Keep for dynamic signature edge cases | Reduce repeated integration assertions. |
| AgentActor CRUD tests | Keep model/storage basics | Add full run boundary with tools/thread. |
| Thread tests | Keep thread model contract | Assert thread behavior through agent run. |
| Streaming tool tests | Keep protocol edge cases | Add one end-to-end stream boundary test. |

### Proposed Solution Directions

#### Option A — AgentRunEngine

Introduce a single lifecycle object responsible for one agent execution.

```python
@dataclass
class AgentRunRequest:
    task: str
    prompt: str
    tools: list[str]
    user: dict | None = None
    thread_id: str | None = None
    llm: Any = None
    constraints: dict = field(default_factory=dict)

class AgentRunEngine:
    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...
    async def stream(self, request: AgentRunRequest) -> AsyncIterator[AgentEvent]: ...
```

Pros:

- Makes lifecycle explicit and testable.
- `AgentMixin` becomes a facade/config adapter.

Cons:

- Requires careful compatibility with existing `agentic()`, `run()`, streaming methods.

#### Option B — Ports Around Pydantic AI and Matrix

Define ports for external-ish dependencies:

```python
class LLMRunner(Protocol):
    async def run(self, task, prompt, tools, deps, limits): ...

class ToolRouter(Protocol):
    async def call(self, target, method, data, user): ...
    async def stream(self, target, method, data, user): ...
```

Pros:

- Makes Pydantic AI and Matrix substitutable in tests.
- Strong if future agent execution needs alternative engines.

Cons:

- More abstraction; may be premature if Pydantic AI remains the only engine.

#### Option C — Boundary Tests with Existing Internals

Keep internals, but test full lifecycle:

```python
async def test_agent_run_calls_tool_and_persists_thread(test_model, tmp_db):
    # app with AgentActor + Grant tool model + Thread
    # TestModel calls grants_list
    # assert answer, usage, tool result, and thread messages are persisted
```

Pros:

- Low risk.
- Clarifies desired lifecycle before extraction.

Cons:

- Does not reduce navigational complexity.

### Recommendation

Start with **Option C**. Move to **Option A** when agent behavior expands again.
Use **Option B** only for seams that prove painful in tests; avoid abstracting
Pydantic AI too early.

---

## Cross-Candidate Testing Strategy

The main testing shift should be **replace, don’t layer**.

```text
Current shape in several areas:

  helper tests
      + helper tests
          + route construction tests
              + some example integration tests

Recommended shape:

  small primitive tests where behavior is genuinely isolated
      + boundary tests at the public module contract
          + examples/e2e only for full application confidence
```

### Proposed Boundary Test Suites

| Suite | Boundary | Uses |
|---|---|---|
| `test_api_contract_parity.py` | direct app vs actor app HTTP behavior | `TestClient`, tmp SQLite, same model graph |
| `test_relationship_storage_boundary.py` | model graph persistence and response hydration | tmp SQLite, generated join model |
| `test_schema_contract.py` | complete schema from canonical model definitions | in-process models, imported extensions |
| `test_app_bootstrap_boundary.py` | built app runtime state | tmp SQLite, direct/actor modes, Matrix |
| `test_authorization_policy_matrix.py` | same rules across direct/actor/tool | tmp SQLite, JWT users, TestModel if needed |
| `test_agent_run_boundary.py` | agent run/stream with tools and thread | Pydantic AI TestModel, Matrix, tmp SQLite |

### Boundary Fixture Sketch

```python
@pytest.fixture
def canonical_blog_models():
    class User(BaseUser): ...

    class Comment(ActorModel):
        __tablename__ = "comments"
        __storable__ = True
        __owner_field__ = "user_owner"
        parent_id: Optional[Ref['self']] = None

    class Product(ActorModel):
        __tablename__ = "products"
        __storable__ = True
        owner: Optional[Ref[User]] = None
        comments: ListRef[Comment] = Field(default=[])
        metadata: dict = Field(default={})

        @expose_route('/comment', methods=['POST'], access=AUTHENTICATED)
        def comment(self, comment: Comment, user: User = None) -> Comment: ...

    return User, Product, Comment
```

Use the same graph across API, storage, schema, and auth tests so failures map
to real framework behavior rather than synthetic helper fixtures.

---

## RFC Creation Recommendations

When turning these into GitHub issues, create separate RFCs in this order:

1. **RFC: Add direct-vs-actor API parity boundary tests**
2. **RFC: Deepen SQLite relationship storage around a RelationshipMapper**
3. **RFC: Add canonical schema contract tests and evaluate SchemaCompiler**
4. **RFC: Introduce AppManifest for inspectable app bootstrap**
5. **RFC: Add authorization policy matrix across direct, actor, and tools**
6. **RFC: Define AgentRunEngine boundary for agent lifecycle**

Each RFC should include:

- problem statement
- chosen interface or boundary
- dependency strategy
- new boundary tests
- old shallow tests to remove or reduce
- migration steps
- compatibility risks

---

## Suggested Next Step

Pick one candidate to explore with competing interface designs. My recommended
first pick is **Candidate 1: Route Contract Parity**, because it protects the
public API contract and will also clarify authorization parity requirements.
