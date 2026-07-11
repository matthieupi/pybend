# N3TX Model Layer

The model layer is the core of N3TX. A Python model definition is the
single source of truth for the entire stack: data structure, validation,
API endpoints, JSON Schema, access control, UI rendering.

---

## Table of Contents

1. [ProtoModel](#protomodel)
2. [Schema Pipeline (proto_schema)](#schema-pipeline-proto_schema)
3. [Dump Pipeline (proto_dump)](#dump-pipeline-proto_dump)
4. [StorableMixin](#storablemixin)
5. [BaseUser](#baseuser)
6. [ActorModel](#actormodel)
7. [References](#references)
8. [Optional File Resource](#optional-file-resource-n3tx-files)
9. [File Layout](#file-layout)

---

## ProtoModel

**File**: `proto_model.py`

Base class for all N3TX models. Extends `PydanticBaseModel`.

### Responsibilities

- Schema generation via `schema()` (delegates to `proto_schema.run_pipeline()`)
- Serialization via `model_response()` (delegates to `proto_dump.run_pipeline()`)
- Optional storage injection via `__storable__` flag (injects `StorableMixin`)
- FK field transformation (`BaseModel` annotations -> `Ref[T]`)
- Method signature collection for API documentation
- Schema caching (per-class, `deepcopy` on read)

### Key Methods

| Method | Purpose |
|--------|---------|
| `schema()` | Returns JSON Schema via the schema pipeline. Cached per class. |
| `model_response()` | Returns enriched dict via the dump pipeline (`$schema`, `$id`). |
| `model_dump()` | Plain Pydantic dict. For storage operations (no metadata). |
| `referenced_json_schema()` | Schema for `$defs` inclusion. Resolves `Ref` to `$ref`. |
| `invalidate_schema_cache()` | Clears cached schema (for tests / dynamic redefinition). |

### Class Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `__storable__` | `bool` | Enable StorableMixin injection and CRUD |
| `__tablename__` | `str` | Database table / API collection path |
| `__fk_models__` | `dict` | Join model cache for FK hydration |
| `__hidden_fields__` | `set` | Fields excluded from schema entirely |
| `__protected_fields__` | `set` | Fields hidden in edit forms, auto-injected on create |
| `__owner_field__` | `str` | Field name used for OWNER rule evaluation |
| `__ui__` | `dict` | UI hints: field_order, groups, renderer |
| `__access__` | `dict` | ABAC access rules (read, create, update, delete) |

### `__init_subclass__` Magic

When `__storable__ = True`:
1. Injects `StorableMixin` into `__bases__`
2. Rewrites `BaseModel` field annotations to `Ref[T]`

---

## Schema Pipeline (proto_schema)

**File**: `proto_schema.py`

Composable `dict -> dict` stages that build the JSON Schema for a model
class. `ProtoModel.schema()` calls `proto_schema.run_pipeline(cls)`.

### Default Stages

| # | Stage | Input | Output |
|---|-------|-------|--------|
| 1 | `base` | `cls` | Pydantic core JSON Schema + `Ref['self']` patches |
| 2 | `strip_hidden` | `cls, schema` | Removes `__hidden_fields__` from properties |
| 3 | `methods` | `cls, schema` | Injects `@expose_route` method signatures + stream event schemas |
| 4 | `defs` | `cls, schema` | Collects referenced models into `$defs` |
| 5 | `access` | `cls, schema` | Serializes ABAC rules (top-level + `$defs`) |
| 6 | `ui` | `cls, schema` | Injects UI hints, protected fields, `__ui__` config |
| 7 | `metadata` | `cls, schema` | Stamps `$schema` and `$id` |

### Extension Protocol

Insert stages into the pipeline without modifying `proto_schema.py`:

```python
from n3tx.core.models.proto_schema import schema_extension

@schema_extension(after='methods')
def federation(cls, schema: dict) -> dict:
    if getattr(cls, '__federated__', False):
        schema['federation'] = {...}
    return schema
```

The function name becomes the stage name. Positioning via `after=` or
`before=` relative to existing named stages.

### Pipeline Introspection

```python
from n3tx.core.models.proto_schema import get_pipeline
get_pipeline()  # ['base', 'strip_hidden', 'methods', 'defs', 'access', 'ui', 'metadata']
```

---

## Dump Pipeline (proto_dump)

**File**: `proto_dump.py`

Composable `dict -> dict` stages that serialize a model instance.
`ProtoModel.model_response()` calls `proto_dump.run_pipeline(instance)`.

Mirrors `proto_schema` -- same pattern, same extension mechanism.

### Default Stages

| # | Stage | Input | Output |
|---|-------|-------|--------|
| 1 | `base` | `instance` | Plain Pydantic `model_dump()` |
| 2 | `relationships` | `instance, data` | Enriches hydrated `T` and `list[T]` children through their dump pipelines |
| 3 | `schema_url` | `instance, data` | Injects the model `$schema` URL |
| 4 | `instance_url` | `instance, data` | Injects the resource `$id` URL |
| 5 | `populate` | `instance, data` | Overlays explicitly populated storage relationships |

The URL stages cache per-class metadata so they do not rebuild URL prefixes on
every serialization.

### Extension Protocol

```python
from n3tx_core.models.proto_dump import dump_extension

@dump_extension(after='instance_url')
def activity(instance, d: dict) -> dict:
    if getattr(instance.__class__, '__federated__', False):
        d['@context'] = 'https://www.w3.org/ns/activitystreams'
        d['type'] = instance.__class__.__name__
    return d
```

### When to Use Which

| Method | Use Case |
|--------|----------|
| `model_dump()` | Storage operations, internal processing |
| `model_response()` | HTTP API responses (includes `$schema`, `$id`, extensions) |

---

## StorableMixin

**File**: `storable_mixin.py`

Provides CRUD operations via dependency injection (Strategy Pattern).
Injected into model `__bases__` by `ProtoModel.__init_subclass__` when
`__storable__ = True`.

### Methods

| Method | Signature | Purpose |
|--------|-----------|---------|
| `create(data)` | classmethod | Insert new record |
| `get(id)` | classmethod | Fetch by primary key |
| `list(sql_filter, limit, offset)` | classmethod | Query with optional pagination |
| `update(id, data)` | classmethod | Validate and persist a partial update |
| `delete(id)` | classmethod | Remove record |

### Pagination

When `limit` is provided, `list()` returns
`{"data": [...], "meta": {"total", "limit", "offset", "has_more"}}`.
Without `limit`, returns a plain list (backward compatible).

`StorableMixin.update(id, data)` and generated direct/actor `PUT` handlers write
only supplied dictionary keys after validating the merged complete entity.
[API CRUD Endpoints](API_CRUD_ENDPOINTS.md#update-resource).

### JSON Fields

Storable models may use embedded JSON fields for data owned entirely by the
parent row:

```python
class AgentConfig(ProtoModel):
    __tablename__ = 'agent_configs'
    __storable__ = True

    tools: list[str] = Field(default=[])
    constraints: dict = Field(default={})
```

`dict`, `Dict[...]`, primitive typed list fields, `list[T]`, and `list[Ref[T]]`
fields are stored as SQLite `TEXT` columns using JSON serialization. They are
deserialized before Pydantic model construction on reads. `list[T]` stores local
child ids and hydrates them into model objects; `list[Ref[T]]` stores pointer
refs. `ManyToMany[T]` is a legacy shared-link helper and should not be used as
the default owned collection primitive.

Use JSON fields for metadata, settings, agent constraints, primitive tags,
ordered local model collections, pointer arrays, and external payload fragments.
Use explicit models and custom methods when nested data needs identity, auth,
pagination, lifecycle events, or independent updates.
See [JSON Fields](JSON_FIELDS.md) for implementation details and tradeoffs.

---

## References

**File**: `models/ref.py`

`Ref[T]` is the typed identity pointer primitive:

```text
Ref[T] means “an absolute HTTP(S) URL for a T identity.”
```

Accepted reference inputs are absolute HTTP(S) entity URLs ending in
`/{ClassName}/{id}`. They are stored and emitted unchanged. Local integer ids
and local paths belong to `T`/`list[T]` relationship storage, not `Ref[T]`.

Local owned collections use `list[T]` and are stored as ordered local ids on the
parent row. Distributed pointer arrays use `list[Ref[T]]`.

Remote dereference is opt-in. Storage with no `reference_resolver` preserves and
returns canonical remote refs without fetching them. Actor-mode bootstrap can
inject a `MatrixReferenceResolver` so populated remote refs resolve through
`RemoteMatrix`. For explicit Python calls to a remote `ActorModel` identity, use
the model-centric handle:

```python
artifact = Artifact.ref('https://storage.example.com/Artifact/42')
result = await artifact.call('process', mode='fast')
```

Reference helpers live with the model primitives in `models/ref.py`:

| Helper | Purpose |
|---|---|
| `Ref.base_url(ref)` | Return the service API base before `/{ClassName}/{id}`. |
| `Ref.schema(ref)` | Return the target class-name segment. |
| `Ref.id(ref)` | Return the target id segment as a string. |
| `Ref.hydrate(...)` | Explicitly dereference through a supplied resolver context. |
| `local_ref_id()` | Extract an id only for current-service local relationship storage. |
| `public_id_url()` | Build the canonical public URL for a local entity id. |

The historical `n3tx_core.utils.typer.Ref` import remains as a compatibility
surface and re-exports `Ref` from `models/ref.py`.

---

## BaseUser

**File**: `base_user.py`

Abstract base user model with built-in authentication. Subclass to get
login, register, and password hashing for free.

```python
class User(BaseUser):
    __tablename__ = 'users'
    __abstract__ = False
    image: Optional[str] = Field(default=None)
```

### Provided Fields

`name`, `email`, `role`, `password_hash` (hidden from schema via
`__hidden_fields__`).

### Provided Endpoints

| Method | Route | Access | Purpose |
|--------|-------|--------|---------|
| `login()` | `POST /login` | `ANYONE` | Returns JWT token + user data |
| `register_user()` | `POST /register` | `ANYONE` | Creates user, returns JWT token |

**Note**: The method is `register_user()` (not `register()`) to avoid
MRO collisions with `Actor.register()` when using `ActorModel`.

### Password Handling

- `register_user()` stashes the plain password as `_plain_password` on
  the instance
- `BaseUser.create()` hashes it before storage via `hash_password()`
- `password_hash` is excluded from schema and responses

---

## ActorModel

**File**: `actor_model.py`

Bridge class: `Actor` (messaging) + `ProtoModel` (data/schema/storage).

```
MRO: Product -> ActorModel -> Actor -> ProtoModel -> PydanticBaseModel
```

### CRUD via Messages

`handler_crud()` adapts TX messages to StorableMixin methods:

| TX name | StorableMixin call |
|---------|-------------------|
| `schema` | `cls.schema()` |
| `create` | `cls.create(cls(**data))` |
| `get` | `cls.get(id)` |
| `list` | `cls.list(limit, offset)` |
| `update` | `cls.update(id, data)` |
| `delete` | `cls.delete(id)` |

Non-CRUD messages fall through to Actor's generic `getattr` dispatch.

### Lifecycle Events

After create/update/delete, `_publish_lifecycle()` sends a `LIFECYCLE`
TX to registered subscribers (fire-and-forget). See the
[actors README](../actors/README.md) for details.

---

## Optional File Resource (`n3tx-files`)

**File**: `packages/n3tx-files/src/n3tx_files/file.py`

`n3tx-files` provides `File(ActorModel)`, an optional model/capability for
addressable files. The model carries authoritative metadata while bytes live in
a separate `FileStore` provider.

```python
from n3tx_files import File, LocalFileStore, configure_file_store

configure_file_store(LocalFileStore('./file-blobs'))
app = create_app(models=[File], storage='sqlite:///app.db')
```

### Fields

| Field | Purpose |
|---|---|
| `filename` | Original/display name |
| `content_type` | MIME type, default `application/octet-stream` |
| `size` | Byte size, protected from user writes |
| `sha256` | Content checksum, protected from user writes |
| `storage_key` | Provider key for blob bytes, protected from user writes |
| `origin` | Optional origin/remote source marker |
| `public` | App-level public/private hint |
| `user_owner` | Owner id for `OWNER` access rules |
| `meta` | Provider/app metadata |

### Byte routes

File byte IO is explicit package-owned API routing, not static-file serving:

| Route | Purpose |
|---|---|
| `POST /files/upload` | Multipart upload with form field `upload`; creates File metadata |
| `GET /files/{id}/download` | Binary download |
| `GET /File/{id}/download` | Class-name download mirror |

Download supports inclusive byte ranges with `Range: bytes=start-end` and
returns `206` plus `Content-Range` for partial reads.

### Reference resolution and materialization

`File.resolve(ref)` accepts the canonical absolute `$id` URL of a File on the
current API, for example `http://localhost:5000/File/1`.

When `n3tx_files` is imported, it registers a typed argument materializer. A
custom method annotated with `File` receives a resolved `File` instance when the
payload contains a canonical File URL:

```python
@expose_route('/transcribe', methods=['POST'])
async def transcribe(audio: File) -> dict:
    local = await audio.ensure_local()
    ...
```

Plain `str` parameters are not materialized. This keeps remote IO explicit and
type-gated.

### Storage boundary

- SQLite/N3TX storage owns metadata only.
- `FileStore` providers own bytes (`LocalFileStore` is the default local provider).
- Dynamic file downloads must not be mounted through the static asset catch-all.
- Remote storage/CDN nodes are provider/deployment strategies behind the same
  `File` contract.

---

## File Layout

```
models/
    __init__.py          Public API: BaseUser, ActorModel
    proto_model.py       ProtoModel base class, schema(), model_response()
    proto_schema.py      Schema pipeline: 7 composable stages + extension protocol
    proto_dump.py        Dump pipeline: composable stages + extension protocol
    storable_mixin.py    CRUD operations (create/get/list/update/delete)
    base_user.py         Abstract base user with login/register endpoints
    actor_model.py       ActorModel bridge (Actor + ProtoModel)
    ref.py               Ref[T] distributed/local reference helpers
```
