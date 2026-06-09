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
7. [Optional File Resource](#optional-file-resource-n3tx-files)
8. [File Layout](#file-layout)

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
| 2 | `response` | `instance, data` | Injects `$schema` and `$id` for HTTP responses |

The `response` stage caches per-class URL metadata (`_response_meta_cache`)
so it does not rebuild on every serialization.

### Extension Protocol

```python
from n3tx.core.models.proto_dump import dump_extension

@dump_extension(after='response')
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
| `update(id, data)` | classmethod | Partial update |
| `delete(id)` | classmethod | Remove record |

### Pagination

When `limit` is provided, `list()` returns
`{"data": [...], "meta": {"total", "limit", "offset", "has_more"}}`.
Without `limit`, returns a plain list (backward compatible).

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

### Address resolution and materialization

`File.resolve(address)` supports internal addresses:

```text
n3tx://files/{id}
/files/{id}
/File/{id}
```

When `n3tx_files` is imported, it registers a typed argument materializer. A
custom method annotated with `File` receives a resolved `File` instance when the
payload contains one of the supported address strings:

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
    proto_model.py       ProtoModel base class, generate_join_model()
    proto_schema.py      Schema pipeline: 7 composable stages + extension protocol
    proto_dump.py        Dump pipeline: composable stages + extension protocol
    storable_mixin.py    CRUD operations (create/get/list/update/delete)
    base_user.py         Abstract base user with login/register endpoints
    actor_model.py       ActorModel bridge (Actor + ProtoModel)
    ref.py               ListRef[T] type for collection references
```
