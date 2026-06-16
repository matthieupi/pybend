---
name: n3tx-storage-relationships
description: N3TX storage, StorableMixin, SQLite JSON fields, Ref/list[Ref] distributed pointers, pagination, ListRef parent-child relationships, ManyToMany shared relationships, nested routes, and ownership fields. Use when designing or debugging persistence and relationships.
argument-hint: "<storage or relationship task>"
---

# N3TX Storage and Relationships

## Storage model

Set `__storable__ = True` to inject CRUD behavior and register a database table.

```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str
```

CRUD methods are provided by `StorableMixin`: `create`, `get`, `list`, `update`, `delete`.

## JSON fields

`dict`, `list`, typed list fields, and `list[Ref[T]]` pointer arrays are stored
as JSON TEXT in SQLite and deserialized on read.
Use the dedicated `n3tx-json-fields` skill and `docs/JSON_FIELDS.md` when
designing, debugging, or changing embedded JSON field behavior.

```python
class AgentConfig(ActorModel):
    __tablename__ = 'agent_configs'
    __storable__ = True
    tools: list[str] = []
    constraints: dict = {}
```

## Pagination

When `limit` is provided, list returns:

```json
{"data": [], "meta": {"total": 0, "limit": 20, "offset": 0, "has_more": false}}
```

Without `limit`, list returns a plain list for compatibility.

## Relationship primitives

Use the relationship primitive that matches ownership and lifecycle:

| Domain shape | Field type | Generated behavior |
|---|---|---|
| Parent owns or scopes child records | `ListRef[T]` | Nested routes, FK/join model hydration, parent-scoped identity |
| Shared collection between two entities | `ManyToMany[T]` | Generated link model/table from the field declaration |
| Local or distributed identity pointer | `Ref[T]` | Local id or canonical `n3tx://service/Class/id` ref |
| Local/distributed pointer array | `list[Ref[T]]` | JSON TEXT array, optional best-effort populate |

Do not use a plain JSON list for records that need independent identity, auth,
routes, or lifecycle.

`ListRef[T]` remains local-owned relationship semantics only. Do not overload it
for remote/distributed pointers; use `list[Ref[T]]` when the parent stores
identity addresses such as `n3tx://storage/File/12`.

## Parent-child relationships with ListRef

Use `ListRef[T]` on the parent:

```python
from n3tx_core.models.ref import ListRef

class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    comments: ListRef['Comment'] = []
```

N3TX generates a join model such as `ProductComment` with FK columns. Public nested identity uses semantic class names:

```text
Legacy:    /products/1/comments/2
Canonical: /Product/1/Comment/2
```

## Shared many-to-many relationships

Use `ManyToMany[T]` when both sides are independent entities and the field
represents membership/association rather than parent ownership:

```python
from pydantic import Field
from n3tx_core.models.relationships import ManyToMany


class Tag(ActorModel):
    __tablename__ = 'tags'
    __storable__ = True
    name: str


class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    tags: ManyToMany[Tag] = Field(default=[])
```

`create_app()` / `N3TXApp` discover `ManyToMany` declarations and generate the
relationship link model during bootstrap. For lower-level/raw registration flows,
use the relationship helpers deliberately rather than hand-rolling SQL tables.

## Self references

```python
from n3tx_core.utils.typer import Ref

class Comment(ActorModel):
    __tablename__ = 'comments'
    __storable__ = True
    parent_id: Ref['self'] | None = None
```

## Distributed ref storage

Single `Ref[T]` fields preserve local behavior while accepting distributed refs:

```text
local id / /File/12 / current API URL -> local id / local href response
configured remote HTTP URL            -> n3tx://service/Class/id
n3tx://service/Class/id               -> preserved canonical ref
```

Remote dereference is opt-in through storage injection:

```python
SQLiteStorage(reference_resolver=None)                       # local-only
SQLiteStorage(reference_resolver=MatrixReferenceResolver(m))  # remote populate
```

Keep the boundary clean: core storage accepts an injected resolver; it must not
import actors directly.

## Ownership fields

For OWNER auth:

```python
class Comment(ActorModel):
    __owner_field__ = 'user_owner'
    __protected_fields__ = {'user_owner'}
    user_owner: int | None = None
```

Protected fields are backend-owned: injected on create and hidden/stripped in edit/update flows.

## Guardrails

- Do not query or mutate SQLite directly from app features.
- Do not store relationships as duplicated arbitrary arrays if `ListRef` or `ManyToMany` represents the domain relationship.
- Do not confuse `ListRef[T]` local ownership with `list[Ref[T]]` pointer arrays.
- Do not confuse embedded JSON arrays with relationship fields: JSON fields have
  no child `$id`, href hydration, owner/auth boundary, lifecycle events, or
  independent update route.
- Do not expose generated join model names as the semantic public concept.
- Do not treat `ManyToMany[T]` as a JSON field; it is relationship metadata.
- Avoid `:memory:` SQLite for tests involving migrations; use a file database.

## Verification

- CRUD works for parent and child.
- Relationship fields appear in schema and responses as href arrays.
- `ManyToMany` fields generate deterministic link models/tables during app bootstrap.
- `Ref[T]` and `list[Ref[T]]` remote inputs canonicalize to `n3tx://...`.
- Remote populate failures do not break parent reads; they report per-ref errors where supported.
- Nested routes resolve correctly.
- Pagination metadata is correct when `limit` is used.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
