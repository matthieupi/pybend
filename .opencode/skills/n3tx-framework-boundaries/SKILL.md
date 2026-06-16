---
name: n3tx-framework-boundaries
description: N3TX framework boundary guardrails and anti-patterns. Use ONLY when a design might bypass schemas, actors, generated routes, N3TX transport, authorization, files, or reusable actor capabilities.
argument-hint: "<design or implementation concern>"
---

# N3TX Framework Boundaries

This skill protects the architecture from entropy. N3TX works because a small set of contracts are applied everywhere.

## Boundary rules

| Boundary | Correct path | Avoid |
|---|---|---|
| Data contract | `ProtoModel`/`ActorModel` fields and schema | Hand-maintained frontend/backend duplicates |
| Persistence | `__storable__`, model CRUD, storage backend | Direct SQL in app feature code |
| Relationships | `ListRef[T]` or `ManyToMany[T]` | JSON arrays or hand-maintained link tables |
| Distributed refs | `Ref[T]`, `list[Ref[T]]`, Matrix, `RemoteMatrix` | Ad hoc URL fields/fetches or remote `ListRef` |
| Files | `n3tx-files` `File` metadata + `FileStore` bytes | Blobs in SQLite or static upload folders |
| API actions | `@expose_route` | Custom FastAPI routes for normal app behavior |
| Internal networking | TX -> Matrix -> Actor/Adapter | Backend-to-backend plain HTTP calls |
| Frontend entity IO | N3TX entity/transport layer | Raw `fetch()` for CRUD/actions |
| Auth | `__access__`, `access=`, backend enforcement | UI-only or duplicated checks |
| Compute | Actor or model method | Hidden free function if reusable |
| Agent tools | Actor/model methods exposed by schema | Separate ad-hoc tool registry |
| External IO | Dedicated actor or `NetworkAdapter` | Scattered direct client calls |
| UI customization | schema hints/widgets/renderers/components | Forked generated UI or duplicated schema |

## Decision test

Before adding code, ask:

1. Does this belong in the model contract?
2. Should another component, agent, MCP client, workflow, or UI reuse it?
3. Should it be visible in schema?
4. Should it be addressable through Matrix/TX?
5. Is this duplicating information the backend already knows?

If yes, stay inside N3TX boundaries.

## External HTTP rule

External APIs are allowed only behind a boundary:

```text
External API client code
   belongs inside
Dedicated ActorModel / Actor / NetworkAdapter
   exposed through
@expose_route or adapter protocol
   reused by
UI, agents, workflows, MCP, other actors
```

## Distributed ref boundary rule

Distributed N3TX refs are still model/actor contracts:

```text
Model field (`Ref[T]` / `list[Ref[T]]`)
  -> canonical `n3tx://service/Class/id`
  -> Matrix adapter fallback
  -> RemoteMatrix class-name REST call
  -> normal remote generated routes + ABAC
```

Keep package boundaries acyclic: core may store/canonicalize refs and accept an
injected `reference_resolver`; core must not import actors. Actor/app bootstrap
wires `RemoteMatrix` and `MatrixReferenceResolver` when remote resolution is
enabled.

## Escalation

If a feature cannot fit cleanly into these boundaries, do not patch around N3TX. Identify what extension point is missing: model schema metadata, actor capability, adapter, widget, component, or auth rule.

## File boundary rule

Dynamic files are not static assets and not JSON/blob fields. Use `n3tx-files`:

```text
File metadata model  -> normal N3TX schema/storage/auth/routes
FileStore provider   -> local/object/remote bytes
File-typed parameter -> authorized address materialization
```

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. If source reveals a missing contract, update or propose docs/skills.
