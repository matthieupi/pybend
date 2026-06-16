---
name: n3tx-models
description: N3TX model definitions with ProtoModel, ActorModel, BaseUser, schema, Ref/list[Ref] distributed pointers, JSON dict/list fields, ListRef, ManyToMany, File fields, UI metadata, validation, and app data contracts. Use when defining or changing N3TX models.
argument-hint: "<model or data contract>"
---

# N3TX Models

Models are the source of truth for the whole stack.

## Choose a base class

| Base | Use when |
|---|---|
| `ProtoModel` | Data/schema/storage without actor capabilities |
| `ActorModel` | Model should receive TX, expose tools, participate in agents/networking/lifecycle |
| `BaseUser` | User model with login/register/password hashing |
| `AgentActor` | Dynamic persisted agent instances |

Default for new app entities: **`ActorModel`** if the app may use agents, workflows, actor routing, or reusable capabilities.

## Canonical model

```python
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.models.ref import ListRef
from n3tx_core.models.relationships import ManyToMany
from n3tx_core.utils.decorators import expose_route


class Tag(ActorModel):
    __tablename__ = 'tags'
    __storable__ = True
    name: str


class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __owner_field__ = 'user_owner'
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }
    __ui__ = {
        'icon': 'box',
        'field_order': ['name', 'price', 'description', 'comments', 'tags'],
        'groups': {'main': ['name', 'price', 'description'], 'Social': ['comments', 'tags']},
        'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
    }

    name: str = Field(min_length=1, max_length=200, json_schema_extra={'ui': {'placeholder': 'Product name'}})
    price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}})
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    user_owner: int | None = None
    comments: ListRef['Comment'] = Field(default=[])
    tags: ManyToMany[Tag] = Field(default=[])

    @expose_route('/discount', methods=['POST'], access=OWNER | ROLE('admin'))
    def discount(self, percent: float) -> dict:
        return {'new_price': self.price * (1 - percent / 100)}
```

## BaseUser pattern

```python
from typing import Optional
from pydantic import Field
from n3tx_core.models.base_user import BaseUser


class User(BaseUser):
    __tablename__ = 'users'
    __abstract__ = False
    image: Optional[str] = Field(default=None)
```

`BaseUser` provides `name`, `email`, `role`, hidden `password_hash`, `login()`, and `register_user()`.

## Relationship fields

- Use `ListRef[T]` for parent-scoped child collections such as product comments.
- Use `ManyToMany[T]` for shared independent entities such as product tags.
- Use `Ref[T]` for a single local or distributed identity pointer.
- Use `list[Ref[T]]` for JSON-backed local/distributed pointer arrays.
- Do not use `list[T]` or JSON arrays for relationships that need identity,
  nested routes, auth, or lifecycle.

```python
from n3tx_core.models.relationships import ManyToMany

class Product(ActorModel):
    tags: ManyToMany[Tag] = Field(default=[])
```

`create_app()` / `N3TXApp` discover `ManyToMany` fields and generate link models
during bootstrap.

## Distributed refs

`Ref[T]` means “a pointer to a T actor/model identity Matrix can resolve,” not
necessarily an integer FK in this database.

```python
from n3tx_core.models.ref import Ref, ListRef

class Job(ActorModel):
    __tablename__ = 'jobs'
    __storable__ = True

    owner: Ref[User] | None = None       # local or remote identity pointer
    files: list[Ref[File]] = []          # JSON-backed pointer array
    comments: ListRef[Comment] = []      # local owned relationship only
```

Accepted ref inputs include local ids, local class-name paths (`/File/12`),
current-service API URLs, configured remote HTTP URLs, and canonical distributed
refs (`n3tx://storage/File/12`). Configured remote HTTP refs canonicalize to
`n3tx://service/Class/id`; arbitrary HTTP(S) URLs remain external links, not
Matrix refs.

## JSON fields

Use JSON fields for embedded data owned by the parent row. JSON fields are
stored as SQLite `TEXT`, serialized with `json.dumps(value, default=str)` on
write, and deserialized with `json.loads()` on read.

```text
Model annotation
  -> get_json_fields(model_class)
  -> SQLite TEXT column
  -> json.dumps(...) on write
  -> json.loads(...) on read
  -> Pydantic validation / model instance
```

Stored as JSON TEXT:

```python
metadata: dict = Field(default={})
config: dict | None = None
tags: list[str] = Field(default=[])
scores: list[int] = Field(default=[])
payloads: list = Field(default=[])
files: list[Ref[File]] = Field(default=[])  # local/distributed pointer array
```

Not JSON fields:

```python
comments: ListRef[Comment] = Field(default=[])   # parent/child relationship
tags: ManyToMany[Tag] = Field(default=[])        # shared relationship
children: list[Comment] = Field(default=[])      # relationship-style collection
```

Use JSON fields for metadata blobs, agent constraints/config, primitive tag
arrays, external API payload fragments, cache-like embedded data, and settings
that do not need independent identity.

Use relationships instead when values need `$id`, routes, owner/auth rules,
lifecycle events, pagination, hydration, or independent rendering/updating.

## File fields and file-capable methods

Use `n3tx-files` when a model or method needs user files. Files are metadata
records plus bytes in a `FileStore`, not blobs in SQLite.

```python
from n3tx_files import File

class TranscriptJob(ActorModel):
    __tablename__ = 'transcript_jobs'
    __storable__ = True
    source: File | None = None

    @expose_route('/transcribe', methods=['POST'])
    async def transcribe(self, audio: File) -> dict:
        local_path = await audio.ensure_local()
        return {'path': str(local_path)}
```

Importing `n3tx_files` registers typed argument materialization so payloads like
`{"audio": "/File/1"}` resolve to authorized `File` instances for `File`-typed
parameters.

## Schema output to expect

`GET /Product` returns a JSON Schema with:

- `$schema`, `$id`, `__name__`, `__tablename__`
- `properties`, `required`
- `methods` from `@expose_route`
- `access` serialized from `__access__`
- `ui` hints from `__ui__`
- `$defs` for referenced models

## Model guardrails

- Do not put frontend-only duplicate contracts in JS; put them in schema via fields/`__ui__`.
- Do not implement storage manually for storable models.
- Do not turn `ListRef[T]`, `ManyToMany[T]`, or model collections into JSON storage accidentally.
- Do not use `ListRef[T]` for remote pointers; use `list[Ref[T]]`.
- Do not query or mutate SQLite JSON text directly from app feature code.
- Remember JSON-field updates replace the whole field; there is no deep merge.
- Remember `json.dumps(..., default=str)` is lossy for non-JSON-native values.
- Do not store file bytes in model fields; use `n3tx-files` and `FileStore`.
- Do not make model methods call internal HTTP endpoints.
- Do not hide reusable app capabilities in free functions; expose them through actors/model methods.

## Verification

- Check `GET /{ClassName}` schema includes fields, UI, access, and methods.
- Check create/read/update/delete work through generated routes.
- Check `model_response()`-backed responses include `$schema` and `$id`.
- For JSON field changes, run or mirror `test_json_fields.py` and `test_introspection.py` coverage.
- For distributed refs, verify canonical storage/response refs and populate behavior.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs if a gap is found.
