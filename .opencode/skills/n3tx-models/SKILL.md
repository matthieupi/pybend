---
name: n3tx-models
description: N3TX model declarations, validation, schema, BaseUser, local relationships and HTTP(S) refs. Use when defining or changing application data contracts.
argument-hint: "<model or data contract>"
---

# N3TX Models

Read [models](../../../docs/MODELS.md), [backend navigation](../../../BACKEND.md)
and the affected package source/tests before changing a contract.

| Need | Mechanism |
|---|---|
| Data/schema/storage | ProtoModel, explicit storage registration |
| Actor-capable entity | ActorModel; direct or actor HTTP is a separate choice |
| Authentication identity | Concrete BaseUser subclass, inherited login/register |
| Stored agent configuration | AgentActor with typed AgentTool records |
| Local model collection | `list[T]`, stored as ordered local IDs and hydrated on read |
| URL identity pointer | `Ref[T]` or `list[Ref[T]]`, absolute HTTP(S) URLs |
| Shared association | Explicit link model; ManyToMany is a legacy helper |

Bare scalar `T` can be rewritten to `Ref[T]` during first StorableMixin injection.
Check the declaration/inheritance case rather than assuming all scalar model
fields remain local. ListRef and generated join-model APIs have been removed.

Keep validation and `__ui__` metadata on models. Import UI/agent mixin packages
before defining flagged classes. Use inherited CRUD for normal updates and
`@expose_route` for genuine domain actions. Do not duplicate schemas in JavaScript.

Use protected ownership fields and explicit access rules, but verify enforcement
on each enabled entrypoint. DEBUG registration grants admin. See
[authorization](../../../docs/AUTHORIZATION.md) and
[operations](../../../docs/OPERATIONS.md).

For JSON, read [JSON fields](../../../docs/JSON_FIELDS.md): replacement is not
deep merge and `default=str` serialization can be lossy. For files, use
[File metadata and byte stores](../../../packages/n3tx-files/docs/file.md),
not blob columns or returned filesystem paths.

Verify schema, persistence, partial updates, response identity and denied access
with isolated storage. Report actual results and unresolved implementation gaps.
