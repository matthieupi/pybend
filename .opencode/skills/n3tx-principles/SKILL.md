---
name: n3tx-principles
description: N3TX principles, philosophy, and architectural intent. Use when building any N3TX app, choosing between models, actors, agents, UI, networking, or preserving framework boundaries.
argument-hint: "<N3TX task or design question>"
---

# N3TX Principles

Use this skill first for any N3TX application work. It explains **why** N3TX is shaped this way so implementation decisions preserve the framework's intent.

## Core philosophy

**The model is the app.** A Python model definition is the single source of truth for data structure, validation, API endpoints, JSON Schema, access control, and UI rendering. If the backend schema can carry a contract, do not duplicate it elsewhere.

**Backend is authoritative.** The backend defines models, schemas, access rules, relationships, methods, and UI hints. The frontend adapts at runtime from `GET /{ClassName}` schema responses.

**Actors are reusable compute boundaries.** If a capability performs work that should be reused by UI, agents, MCP, workflows, or other components, put it behind an `Actor`, `ActorModel`, `@expose_route` method, or `NetworkAdapter`. Do not hide reusable compute in random free functions or one-off HTTP handlers.

**Networking goes through the actor system.** Internal N3TX networking should flow through TX messages, Matrix routing, and network adapters. If an external API must be called, wrap it in a dedicated actor or adapter so the capability is inspectable, addressable, reusable, and tool-discoverable.

**Zero to working, then customize.** Define models first. Let N3TX generate storage, API, schema, and UI. Customize additively through `__ui__`, widgets, custom web components, `@expose_route`, actors, agents, schema/dump extensions, or network adapters.

**Transparent, not magical.** The framework removes plumbing, not accountability. Behavior should be traceable from model definition -> schema -> route/TX -> storage/actor -> frontend rendering.

## Architectural boundaries

```text
Model definition
   |
   v
JSON Schema contract  ---> Frontend DynamicClass + components
   |
   v
Generated API / TX messages
   |
   v
Actor / ActorModel capability boundary
   |
   v
Storage, agents, external adapters, or business logic
```

Keep work inside these boundaries:

- Data and validation belong in models.
- App behavior belongs in model methods or actors.
- API exposure belongs in `@expose_route` or generated CRUD routes.
- Access rules belong in `__access__` and `access=` decorators.
- UI rendering hints belong in schema metadata and renderer/widget extension points.
- Agent tools are actor/model methods exposed with `@expose_route`.
- External protocols belong behind dedicated actors or `NetworkAdapter`s.

## Source-reading policy

Prefer docs, skills, public API, and generated schemas. **Inspect framework source only when documentation is insufficient, does not cover the intended implementation, or observed behavior contradicts docs.** If source inspection reveals a missing or stale contract, update docs/skills or propose that update after the implementation.

## Default decision rules

| Need | Default N3TX mechanism | Why |
|---|---|---|
| Data entity | `ProtoModel` or `ActorModel` | Model remains single source of truth |
| Persistence | `__storable__ = True` | Storage and migration derive from schema |
| Auth | `__access__` / `access=` | Backend authoritative, frontend adapts |
| Parent-child relationship | `ListRef[T]` | Parent-scoped relationship appears in schema and nested routes |
| Shared relationship | `ManyToMany[T]` | Field-declared association generates link model/table during bootstrap |
| Files | `n3tx-files` `File` + `FileStore` | Metadata stays in N3TX; bytes stay in a provider |
| Custom action | `@expose_route` method | Same method becomes API, UI action, agent tool |
| Reusable compute | Actor / non-storable `ActorModel` | Addressable and reusable through Matrix |
| External API | Dedicated actor or `NetworkAdapter` | Keeps IO inspectable and reusable |
| Frontend UI | Schema hints, widgets, custom elements | Avoid duplicating backend contract |
| LLM capability | `AgentActor` or `__agent__ = True` | Agents use same actor/tool system |

## Anti-patterns

- Custom FastAPI routes for app behavior that should be `@expose_route`.
- Direct database access from application features instead of model CRUD/storage.
- Treating relationship fields (`ListRef[T]`, `ManyToMany[T]`) as arbitrary JSON arrays.
- Storing file bytes in SQLite or serving dynamic user uploads through static assets.
- Internal plain HTTP calls between N3TX components.
- Frontend `fetch()` for N3TX entities/actions when runtime transport/entity methods apply.
- Duplicating backend schema, access rules, or field metadata in frontend code.
- Defining agent tools with a separate tool decorator instead of actor methods.
- Reusable compute hidden in free functions rather than actor-addressable capabilities.
- External API calls scattered through app code instead of wrapped in actors/adapters.
- Forking generated UI when schema hints, widgets, renderers, or custom components are enough.

## Verification mindset

Verify at the framework contract boundary:

- `GET /{ClassName}` returns the expected schema, methods, access, `$defs`, and `ui` hints.
- CRUD and custom methods use generated routes or actor routing.
- Entity responses include `$schema` and `$id`.
- Frontend renders from schema, not duplicated knowledge.
- Actors/tools are discoverable and callable through TX/Matrix.
- External IO is behind a named actor or adapter.
