---
name: n3tx-storage-relationships
description: N3TX storage, local model relationships, HTTP(S) Ref pointers, pagination, partial updates and ownership. Use when designing or debugging persistence.
argument-hint: "<storage or relationship task>"
---

# N3TX Storage And Relationships

Read [storage](../../../packages/n3tx-core/docs/storage.md),
[models](../../../docs/MODELS.md), [JSON fields](../../../docs/JSON_FIELDS.md)
and [CRUD](../../../docs/API_CRUD_ENDPOINTS.md).

`__storable__` injects CRUD; bootstrap/registration attaches storage. Register
parent and child models explicitly. `create` takes a model instance; `update`
validates a merged entity and persists supplied keys. Direct Python CRUD is not
an HTTP authorization boundary.

| Shape | Stored representation | Important limit |
|---|---|---|
| Embedded dict/primitive list | JSON TEXT | Whole-field replacement; no deep merge |
| `list[T]` | Ordered local child IDs in JSON TEXT | Hydrated child objects; no generated nested routes |
| Scalar `T` | Depends on annotation/inheritance | First mixin injection may rewrite bare T to Ref |
| `Ref[T]`, `list[Ref[T]]` | Absolute HTTP(S) URL strings | No integer, relative path or n3tx scheme; dereference is explicit |
| Shared association | Explicit link model | Do not introduce removed generated joins |

ManyToMany and `Ref['self']` are legacy special cases, not the default new
relationship design. Read their current limits before extending existing use.

Population needs an explicit resolver; core storage must not import actors.
Remote authorization, URL destination and credential forwarding require separate
review. A relationship field does not establish child privacy or cascade deletion.
Verify unlink versus record deletion, including UI behavior.

Pagination returns data/meta when a limit is supplied; no-limit calls return a
list. Verify filters independently: unrestricted SQL is not denial. Collection
replacement is last-write-wins; domain methods need deliberate concurrency design.

Use temporary file databases for migration tests. Check create/read/update/delete,
omitted fields, replacement, invalid relationships, identity, ordering and denied
access. Use [contributor commands](../../../AGENTS.md); do not edit live data.
