---
name: n3tx-storage-relationships
description: N3TX storage, StorableMixin, SQLite JSON fields, pagination, ListRef relationships, join models, nested routes, and ownership fields. Use for persistence and relationship design.
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

`dict`, `list`, and typed list fields are stored as JSON TEXT in SQLite and deserialized on read.

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

## Parent-child relationships

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

## Self references

```python
from n3tx_core.utils.typer import Ref

class Comment(ActorModel):
    __tablename__ = 'comments'
    __storable__ = True
    parent_id: Ref['self'] | None = None
```

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
- Do not store relationships as duplicated arbitrary arrays if `ListRef` represents the domain relationship.
- Do not expose generated join model names as the semantic public concept.
- Avoid `:memory:` SQLite for tests involving migrations; use a file database.

## Verification

- CRUD works for parent and child.
- Relationship fields appear in schema and responses as href arrays.
- Nested routes resolve correctly.
- Pagination metadata is correct when `limit` is used.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
