---
name: n3tx-app-bootstrap
description: N3TX create_app and N3TXApp setup, optional imports, model registration, storage, routing and static assets. Use when wiring an application entrypoint.
argument-hint: "<app bootstrap task>"
---

# N3TX App Bootstrap

Read [bootstrap](../../../packages/n3tx-core/docs/app-bootstrap.md) and
[getting started](../../../docs/GETTING_STARTED.md) for complete examples.

1. Set process configuration before importing model modules.
2. Import optional UI/agent mixin packages before flagged model definitions;
   import n3tx_files when using File argument materialization.
3. Register every concrete storable model, including related models.
4. Choose factory, builder or raw construction independently of direct/actor
   routing. ActorModel can be used with direct HTTP. Agents do not intrinsically
   require actor HTTP, but their runtime needs registered actors and storage.
5. Configure temporary development storage and explicit permissions before testing.

ListRef, generated join models and builder join APIs are removed. Use local
`list[T]` collections and explicit shared-link models; ManyToMany is legacy.
Remote Ref identities are absolute HTTP(S) URLs, not service-name addresses.
Remote calls/populate require explicit adapter/resolver wiring; normal reads do
not imply remote I/O.

Native static discovery merges app, agents, UI and core assets into one namespace.
Custom elements still need imports. Configure File byte storage separately from
SQLite and do not mount dynamic uploads as static assets.

Verify schema, generated routes, authentication, static delivery and package
hooks independently. Do not promise direct/actor parity. Consult
[operations](../../../docs/OPERATIONS.md) for DEBUG persistence, CORS forwarding,
secrets, migrations and production limitations. Use
[contributor commands](../../../AGENTS.md), not a fixed checkout directory.
