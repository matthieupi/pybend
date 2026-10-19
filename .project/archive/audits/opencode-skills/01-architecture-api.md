# Quick Deep Audit: OpenCode N3TX Skills

## Executive Summary

The `.opencode/skills/` subsystem is structurally valid and covers the major N3TX concern areas, but it currently behaves more like a set of compact reference cards than a routed agent operating system. Every inspected project skill uses the expected `SKILL.md` shape with `name`, `description`, and `argument-hint` frontmatter, for example `n3tx-principles` lines 1-5 and `n3tx-app-bootstrap` lines 1-5. The bodies consistently encode N3TX's core invariants: model-as-contract, backend authority, actor/network boundaries, schema-driven UI, docs/source policy, and verification; those invariants are visible in `n3tx-principles` lines 13-23, boundary bullets at lines 43-51, and verification bullets at lines 87-96.

The main architecture/API issue is routing ambiguity. Broad skills such as `n3tx-backend`, `n3tx-build-app`, `n3tx-models`, `n3tx-app-bootstrap`, and `n3tx-storage-relationships` all trigger on overlapping concepts: models, storage, relationships, `ManyToMany`, files, auth, routes, app bootstrap, and verification; the overlap is visible in their descriptions at `n3tx-backend` lines 1-5, `n3tx-build-app` lines 1-5, `n3tx-models` lines 1-5, `n3tx-app-bootstrap` lines 1-5, and `n3tx-storage-relationships` lines 1-5.

The second issue is inconsistent discoverability for narrow skills. The workspace contains an `n3tx-files` project skill with a focused description and file-specific contracts at lines 1-5 and 72-95, but it was omitted from the supplied core-read list even though other skills repeatedly mention `n3tx-files` and file workflows, including `n3tx-backend` lines 79-100, `n3tx-build-app` lines 83-84 and 100-103, `n3tx-models` lines 102-123, and `n3tx-testing` lines 58-68.

The third issue is duplicated boilerplate. Almost every skill repeats the same source-reading policy, for example `n3tx-backend` lines 121-123, `n3tx-frontend` lines 81-83, `n3tx-methods-routes` lines 78-80, `n3tx-widgets` lines 69-71, and `n3tx-files` lines 97-99. Repetition preserves a useful invariant, but it also creates drift risk because the canonical repository policy is richer: `AGENTS.md` requires docs-first loading before implementation at lines 74-105 and says source is only step 3 after docs and domain context at lines 95-105.

## Component Inventory

| Skill document | One-line role | Trigger surface | Primary contract | Evidence |
|---|---|---|---|---|
| `n3tx-principles` | Architectural north-star and first skill for N3TX work. | Any N3TX app/design/boundary task. | Preserve model-as-app, backend authority, actor/network boundaries, and schema traceability. | Frontmatter says use for any app, model/actor/agent/UI/networking choice, or framework boundary at lines 1-4; body says use first for any N3TX app work at line 9; core philosophy is lines 13-23. |
| `n3tx-backend` | Broad backend reference card. | Models, storage, auth, routes, actors, agents, relationships, files, bootstrap, integrations, verification. | Backend owns schema, validation, access, routes, identity, capability discovery; avoid hand-written controllers. | Description lines 1-5; backend authority line 21; public imports lines 23-35; guardrails lines 102-109. |
| `n3tx-frontend` | Broad frontend reference card. | Schema-driven UI, Web Components, routes, forms, widgets, transport, streaming UI, verification. | Frontend adapts to backend schema and does not duplicate backend contracts. | Description lines 1-5; schema-driven statement lines 7-20; frontend boundaries lines 64-70. |
| `n3tx-framework-maintenance` | Framework-internals workflow. | Changes under framework packages, docs, architecture, tests, or extension internals. | Preserve package dependency graph and update docs/tests for public contract changes. | Description lines 1-5; use-only statement line 9; dependency invariant line 14; workflow lines 31-39; documentation requirement lines 53-55. |
| `n3tx-build-app` | End-to-end app/feature assembly workflow. | Creating apps, end-to-end features, routing level choice, models, UI, agents, storage, auth, files, verification. | Start from domain models, choose routing level, wrap reusable/external compute, bootstrap, verify schema/API/UI. | Description lines 1-5; development sequence lines 11-22; routing levels lines 24-32; feature checklist lines 75-89. |
| `n3tx-models` | Model/data-contract design. | Defining or changing N3TX models, fields, base classes, relationships, files, UI metadata, validation. | Models are source of truth; choose `ProtoModel`, `ActorModel`, `BaseUser`, or `AgentActor` deliberately. | Description lines 1-5; source-of-truth line 9; base-class table lines 11-20; schema expectations lines 125-134. |
| `n3tx-actors` | Actor capability design. | Actor-backed capabilities, TX routing, `ActorModel`, lifecycle events. | Reusable compute lives behind actor/message boundaries. | Description lines 1-5; actor concept lines 11-20; `ActorModel` capability example lines 22-38; guardrails lines 63-69. |
| `n3tx-agents` | LLM-powered N3TX feature design. | `AgentActor`, `AgentMixin`, tool discovery, Pydantic AI, actor tools, streaming agents. | Agents reason through actor/model methods exposed with `@expose_route`; import order matters for mixins. | Description lines 1-5; agent/tool statement line 9; import-order lines 11-15; tool discovery lines 58-66; guardrails lines 97-103. |
| `n3tx-authorization` | Auth/authz patterns. | Auth/access work involving `BaseUser`, JWT, ABAC, OWNER, ROLE, Where, field protection. | Authorization is backend-owned and schema-exposed; frontend only adapts. | Description lines 1-5; backend-owned statement line 9; model/method access examples lines 25-46; protected fields lines 60-70. |
| `n3tx-storage-relationships` | Persistence and relationship design. | `StorableMixin`, SQLite JSON fields, pagination, `ListRef`, `ManyToMany`, nested routes, ownership. | Pick storage/relationship primitive by identity, lifecycle, ownership, and routing needs. | Description lines 1-5; storage model lines 9-20; relationship decision table lines 44-54; guardrails lines 126-133. |
| `n3tx-json-fields` | Embedded JSON field persistence. | Dict/list nested field persistence, migrations, storage detection, relationship boundaries. | JSON fields are embedded parent-owned data, not independent resources. | Description lines 1-5; mental model lines 14-23; ownership statement lines 25-26; relationship boundary lines 56-62; implementation map lines 63-72. |
| `n3tx-methods-routes` | Custom methods and route grammar. | Adding API actions, model behavior, `@expose_route`, method schemas, route grammar. | Custom behavior belongs in exposed model/actor methods, not custom app routes. | Description lines 1-5; core statement line 9; generated method routes lines 25-33; route grammar lines 51-62; guardrails lines 64-70. |
| `n3tx-streaming` | Streaming method/UI contracts. | Long-running/realtime output, SSE, TX streams, schema-declared events, `NTTStream`. | Streaming is schema-declared and TX-correlated. | Description lines 1-5; statement line 9; backend streaming example lines 11-34; TX/SSE protocol lines 36-49; frontend handlers lines 51-69. |
| `n3tx-networking` | Network/protocol boundary design. | TX, Matrix, `NetworkAPI`, WebSocket, MCP, ActivityPub, adapters, internal/external network flow. | Protocols translate to TX at adapter boundaries; internal backend code should not call plain HTTP. | Description lines 1-5; network architecture lines 9-23; adapter table lines 25-33; internal rule lines 34-36; external boundary table lines 38-48. |
| `n3tx-ui-schema` | Backend-to-frontend UI schema contract. | `__ui__`, field metadata, renderer hints, access adaptation, route grammar. | Backend schema is the UI contract. | Description lines 1-5; statement line 9; `__ui__` example lines 11-31; consumed schema sections lines 33-44; guardrails lines 55-60. |
| `n3tx-ui-components` | Web Component customization. | Creating/changing components, custom renderers, lifecycle, router-mounted components. | Components compose with schema-driven data and N3TX transport. | Description lines 1-5; component hierarchy lines 11-22; renderer pattern lines 24-46; lifecycle lines 48-53; guardrails lines 64-70. |
| `n3tx-widgets` | Field widget customization. | Custom field display/input behavior, backend Widget types, frontend registry, Formidable. | Use widgets for field-level rendering without duplicating validation or forking forms. | Description lines 1-5; backend hints lines 11-29; registry example lines 31-45; widget-vs-component table lines 47-55; guardrails lines 56-61. |
| `n3tx-testing` | Application verification. | Testing app models, routes, auth, actor routing, agents, components, widgets, streaming, E2E. | Verify narrow contract first, then adjacent tests, then browser/E2E when needed. | Description lines 1-5; scope line 9; verification order lines 11-17; backend checks lines 18-35; frontend checks lines 37-44. |
| `n3tx-extension-patterns` | Extension point selection. | Schema/dump extensions, mixins, custom storage, widgets, components, network adapters, auth rules. | Prefer app-level customization before framework extensions. | Description lines 1-5; first-choice decision tree lines 11-24; schema/dump/mixin examples lines 25-57; guardrails lines 63-69. |
| `n3tx-external-integrations` | Third-party API/service integration. | APIs, scraping, webhooks, credentials, sync jobs, external capabilities for agents/UI. | External IO must live behind reusable actor/adapter/FileStore boundaries. | Description lines 1-5; boundary statement line 9; boundary table lines 11-22; stateless actor example lines 23-40; guardrails lines 70-77. |
| `n3tx-framework-boundaries` | Architecture guardrail escalation skill. | Designs that might bypass schemas, actors, generated routes, transport, auth, or reusable actor capabilities. | Protect N3TX's small set of contracts from entropy and identify missing extension points instead of patching around them. | Description lines 1-5; entropy statement line 9; boundary table lines 11-27; decision test lines 28-38; escalation lines 54-57. |
| `n3tx-app-bootstrap` | Entrypoint and registration wiring. | `create_app`, `N3TXApp`, routing levels, imports, static files, storage, relationships, files, model registration. | Import capability packages before model definitions and use high-level bootstrap APIs unless raw primitives are needed. | Description lines 1-5; import order lines 9-22; Level 1/3 examples lines 23-42; builder style lines 43-51; guardrails lines 101-108. |
| `n3tx-files` | File metadata and byte-store capability. | User files, blob storage, upload/download, file arguments, `FileStore`, file addresses. | Files are N3TX metadata records; bytes live behind a provider; typed file arguments materialize authorized `File` instances. | Description lines 1-5; package split statement lines 9-11; routes and addresses lines 30-49; materialization lines 50-70; guardrails lines 79-87. |

## Skill Taxonomy And Routing Model

The skill set naturally groups into six layers:

```text
Principle layer
  n3tx-principles, n3tx-framework-boundaries

Workflow layer
  n3tx-build-app, n3tx-framework-maintenance, n3tx-testing

Backend/domain layer
  n3tx-backend, n3tx-models, n3tx-app-bootstrap, n3tx-methods-routes,
  n3tx-authorization, n3tx-storage-relationships, n3tx-json-fields, n3tx-files

Actor/agent/network layer
  n3tx-actors, n3tx-agents, n3tx-networking, n3tx-external-integrations,
  n3tx-streaming

Frontend/UI layer
  n3tx-frontend, n3tx-ui-schema, n3tx-ui-components, n3tx-widgets

Extension layer
  n3tx-extension-patterns
```

Routing is crisp where a skill owns a narrow noun and a clear failure mode. `n3tx-json-fields` tells agents to use it for `dict`, `list`, typed list, or nested payload fields at lines 7-10 and distinguishes embedded JSON from relationships at lines 25-26 and 56-62. `n3tx-files` focuses on uploads, downloads, addresses, `FileStore`, and typed materialization at lines 30-77. `n3tx-streaming` focuses on `@expose_route(stream=True)`, event schemas, TX stream meta, SSE, and `NTTStream`/`NTTStreamAgent` at lines 11-69.

Routing is ambiguous where broad and narrow skills share the same trigger vocabulary. `n3tx-backend` explicitly includes models, storage, auth, routes, actors, agents, relationships, files, app bootstrap, integrations, and verification in one description at lines 1-5. `n3tx-build-app` includes routing level, models, UI, agents, storage, auth, `ManyToMany`, files, and verification at lines 1-5. `n3tx-app-bootstrap` includes routing levels, imports, static files, storage, `ManyToMany`, `n3tx-files`, and model registration at lines 1-5. These are all legitimate, but without escalation/delegation text an agent can over-load a broad skill and miss the narrower skill that contains the operational contract.

The current body-level routing model is implicit rather than explicit. `n3tx-build-app` gives a development sequence at lines 11-22 and a checklist at lines 75-89, but it does not tell the agent when to also load `n3tx-models`, `n3tx-app-bootstrap`, `n3tx-authorization`, `n3tx-files`, or `n3tx-testing`. `n3tx-frontend` lists component layers at lines 22-30 and schema controls at lines 48-62, but it does not explicitly delegate field-level work to `n3tx-widgets`, schema-hint work to `n3tx-ui-schema`, or whole-renderer work to `n3tx-ui-components`.

## Responsibility Map

| Skill | Owns | Why it exists | What would be lost if removed |
|---|---|---|---|
| `n3tx-principles` | Global architecture intent and anti-patterns. | It encodes the reason behind model/schema/API/UI flow and actor/network boundaries at lines 13-23 and 43-51. | Agents would lack the cross-cutting decision rules that prevent local fixes from eroding the model-as-contract architecture. |
| `n3tx-framework-boundaries` | Architecture smell detection and escalation. | It turns the principles into a concrete avoid/correct table at lines 11-27 and asks design-test questions at lines 28-38. | Agents would know the ideals but have weaker protection against bypasses such as direct SQL, raw fetch, custom routes, or duplicate contracts. |
| `n3tx-build-app` | End-to-end sequencing. | It sequences domain modeling, routing, relationships, files, auth, methods, actors, app bootstrap, seed data, and verification at lines 11-22. | Agents would have topical references but no vertical-slice feature path. |
| `n3tx-framework-maintenance` | Internal framework change workflow. | It separates framework internals from app development at line 9 and names dependency boundaries at lines 21-29. | Agents could treat framework changes like app changes and miss package-graph or docs/update requirements. |
| `n3tx-testing` | Verification strategy and test command selection. | It defines verification order at lines 11-17 and collects backend/frontend/agent/file/stream checks at lines 18-75. | Other skills would keep local verification bullets, but agents would lack a central testing ladder. |
| `n3tx-backend` | Broad backend index. | It gives public imports and backend feature shape in one place at lines 23-61. | Agents would need to stitch backend basics from many narrower skills. |
| `n3tx-frontend` | Broad frontend index. | It maps runtime/schema/component layers at lines 11-30 and route grammar at lines 32-47. | Agents would miss a compact frontend mental model before choosing UI-schema/components/widgets. |
| `n3tx-models` | Data contract shape. | It covers base-class choice, canonical model, `BaseUser`, relationships, file fields, schema output, and guardrails at lines 11-149. | Agents would scatter model guidance across backend, storage, auth, UI-schema, and files skills. |
| `n3tx-app-bootstrap` | Entrypoint wiring and import order. | It covers import order at lines 9-22, Level 1/3 creation at lines 23-42, builder style at lines 43-51, static-file merge at lines 90-99. | Agents could define good models but wire mixins, routes, static files, or files incorrectly. |
| `n3tx-authorization` | Access/auth semantics. | It covers ABAC composition, model access, method access, user injection, protected fields, and Level 3 auth at lines 11-80. | Agents could duplicate UI auth or omit protected-field handling. |
| `n3tx-storage-relationships` | Persistence, pagination, relationships, ownership. | It distinguishes `ListRef`, `ManyToMany`, JSON fields, pagination, self refs, and ownership at lines 22-124. | Agents could store relationships as JSON arrays or hand-roll SQL. |
| `n3tx-json-fields` | Dict/list storage boundary. | It provides a source/document map at lines 63-72 and lossy/update warnings at lines 74-83. | Embedded data and relationship guidance would blur. |
| `n3tx-files` | File metadata/bytes split. | It owns upload/download routes, address grammar, typed materialization, provider extension points, and file guardrails at lines 30-95. | File guidance would remain duplicated but incomplete across backend/build/models/testing/integrations. |
| `n3tx-methods-routes` | `@expose_route` and method route grammar. | It names table/class mirrors and `@` view reservation at lines 51-62. | Agents could add custom FastAPI routes for model actions. |
| `n3tx-actors` | Actor compute boundary. | It maps TX to Matrix to handlers at lines 11-18 and explains actor shapes at lines 49-58. | Agents would underuse actor-addressable capabilities. |
| `n3tx-agents` | Agent-specific model/actor/tool rules. | It links agents, actors, `@expose_route` tools, import order, dynamic agents, and TestModel at lines 9-95. | Agents could create ad-hoc LLM tool registries or miss mixin import-order hazards. |
| `n3tx-networking` | Protocol-to-TX boundary. | It defines adapter architecture at lines 11-23 and built-in adapters at lines 25-33. | Agents could add one-off protocol bridges or backend-to-backend HTTP calls. |
| `n3tx-external-integrations` | Third-party IO placement. | It maps integration use cases to actors, adapters, FileStore, and domain models at lines 11-22. | External API calls could scatter through model methods, UI, or agents. |
| `n3tx-streaming` | Stream protocol and UI lifecycle. | It covers event schemas, TX meta, SSE, frontend handlers, and cancel/lifecycle at lines 11-88. | Agents could invent non-schema stream protocols or duplicate event shapes in JS. |
| `n3tx-ui-schema` | Schema metadata for UI. | It maps `__ui__`, field hints, schema sections, and route/view semantics at lines 11-53. | Agents could hardcode field order, labels, renderers, or access in frontend code. |
| `n3tx-ui-components` | Custom renderer/components. | It names component hierarchy, renderer selection, lifecycle, router attrs, and guardrails at lines 11-76. | Agents could fork generated UI or wipe `prerender()` DOM in `render()`. |
| `n3tx-widgets` | Field-level rendering extension. | It distinguishes field widgets from entity/list components/actions at lines 47-55. | Agents could fork Formidable or hardcode field widgets in components. |
| `n3tx-extension-patterns` | Extension decision tree. | It tells agents to prefer app-level customization and only extend schema/dump/mixins/storage/auth as needed at lines 9-24. | Agents would jump to framework extensions before exhausting additive app mechanisms. |

## Public API Inventory

Each skill exposes two agent-facing APIs: frontmatter and body structure. Frontmatter is the selection API; the body is the execution API.

Frontmatter quality is mostly consistent. All inspected project skills use `name`, `description`, and `argument-hint`, as shown by representative headers in `n3tx-principles` lines 1-5, `n3tx-backend` lines 1-5, `n3tx-frontend` lines 1-5, `n3tx-framework-maintenance` lines 1-5, and `n3tx-files` lines 1-5. The folder/name contract appears satisfied for the inspected files because each frontmatter `name` equals the folder path segment, for example `.opencode/skills/n3tx-files/SKILL.md` has `name: n3tx-files` at lines 1-4.

Description quality varies by granularity. Narrow descriptions are strong when they front-load concrete vocabulary: `n3tx-json-fields` includes “dict/list model fields, SQLite TEXT serialization, schema/storage detection, migrations” at lines 1-5; `n3tx-streaming` includes “SSE, TX stream protocol, @expose_route(stream=True), schema-declared events, NTTStream, NTTStreamAgent” at lines 1-5; `n3tx-files` includes “File metadata, FileStore providers, multipart upload, binary/range download, file addresses, and File-typed method materialization” at lines 1-5.

Broad descriptions are useful but over-trigger. `n3tx-backend` covers nearly every backend noun at lines 1-5, while `n3tx-build-app` covers a large full-stack slice at lines 1-5. Both are valid index skills, but their descriptions do not say “also load narrower skills when the task includes X,” so skill selection depends on the model inferring the taxonomy from body content.

`argument-hint` is present but underused as an API. Most hints are generic, such as `<backend feature>` in `n3tx-backend` line 4, `<frontend feature>` in `n3tx-frontend` line 4, `<model or data contract>` in `n3tx-models` line 4, and `<test or verification task>` in `n3tx-testing` line 4. The hints do not teach the agent examples of trigger nouns like `ListRef`, `@expose_route`, `FileStore`, `__ui__`, `NTTStream`, or `NetworkAdapter` even though those nouns are the real routing keys.

Body-section quality is strong for “what not to do” contracts. Examples include `n3tx-principles` anti-patterns lines 73-85, `n3tx-backend` guardrails lines 102-109, `n3tx-framework-boundaries` boundary table lines 11-27, `n3tx-storage-relationships` guardrails lines 126-133, and `n3tx-widgets` guardrails lines 56-61. This is valuable because N3TX failure modes are often boundary violations rather than missing syntax.

Body-section quality is weaker for handoffs. `n3tx-extension-patterns` has a good decision tree at lines 11-24, but most other skills do not include an explicit “combine with” or “handoff to” section. For example, `n3tx-agents` says tools are actor/model methods at lines 58-66 but does not explicitly say to combine with `n3tx-actors` for reusable capability shape, `n3tx-streaming` for streaming agent UI, or `n3tx-testing` for TestModel verification.

## Contracts And Invariants

Core contracts are clear and repeated:

| Contract | Current skill support | Drift/duplication risk |
|---|---|---|
| Model is source of truth. | `n3tx-principles` lines 13-15, `n3tx-models` line 9, `n3tx-backend` lines 11-21, and `n3tx-ui-schema` line 9. | Low semantic risk; high repetition. |
| Backend is authoritative. | `n3tx-principles` lines 15-16, `n3tx-authorization` line 9, `n3tx-frontend` lines 7-20. | Low semantic risk; needs one canonical phrasing. |
| Use generated routes/`@expose_route`, not custom routes. | `n3tx-principles` lines 45-48 and 75-76; `n3tx-methods-routes` lines 9 and 64-70; `n3tx-backend` lines 102-109. | Medium; route grammar details can drift between skills. |
| Internal networking uses TX/Matrix/adapters. | `n3tx-principles` lines 17-20; `n3tx-networking` lines 9-23 and 34-48; `n3tx-framework-boundaries` lines 20 and 40-52. | Medium; networking and external integration overlap. |
| Frontend reads runtime schema. | `n3tx-principles` lines 13-16; `n3tx-frontend` lines 11-20 and 48-62; `n3tx-ui-schema` lines 33-44. | Medium; frontend specialization needs stronger handoff rules. |
| Relationships are not arbitrary JSON arrays. | `n3tx-principles` line 77; `n3tx-storage-relationships` lines 44-54 and 126-133; `n3tx-json-fields` lines 40-45 and 56-62. | Low; the split is well explained. |
| Files are metadata plus provider bytes. | `n3tx-files` lines 9-11 and 79-87; `n3tx-backend` lines 79-100; `n3tx-external-integrations` lines 55-68. | Medium; missing core-list inclusion makes the dedicated skill easier to miss. |
| Source-reading policy. | Many skills repeat it, including `n3tx-principles` lines 53-56 and `n3tx-testing` lines 83-85. | High; `AGENTS.md` docs-first order is richer at lines 74-105 than the repeated one-liners. |
| Verification at contract boundary. | `n3tx-principles` lines 87-96, `n3tx-testing` lines 11-75, and package-specific verification sections throughout. | Low; but commands differ between skill and current frontend reference. |

Potential stale guidance appears in frontend verification commands. `n3tx-frontend` recommends `cd /workspace/tests/frontend && npm run test:e2e:fast` at lines 72-77, and `n3tx-testing` repeats the same at lines 37-44. `FRONTEND.md` lists a richer current frontend verification matrix, including `npx vitest run`, `npm run test:e2e:fast`, `npm run test:e2e`, focused Playwright commands, Veille verification, and `python3 scripts/test-frontend.py` at lines 184-196. This is not necessarily wrong, but the skills omit the aggregate runner and focused routes documented in `FRONTEND.md` lines 184-196.

Potential stale or duplicated route grammar exists across backend/frontend/method/UI skills. `n3tx-methods-routes` documents backend route grammar at lines 51-62, `n3tx-frontend` documents hash route grammar at lines 32-47, `n3tx-ui-schema` documents route/view semantics at lines 46-53, `BACKEND.md` has the more complete server route table at lines 159-224, and `FRONTEND.md` has the more complete hash/nested route table at lines 369-440. The skills are correct as compact summaries, but they should point to the canonical route grammar docs to avoid divergence.

## Developer And Agent Experience

An agent can choose the right skill when the user names a concrete N3TX mechanism. Queries mentioning `dict/list persistence` route cleanly to `n3tx-json-fields` because the description and opening lines explicitly name those shapes at lines 1-10. Queries mentioning `FileStore`, uploads, downloads, `/File/{id}`, or `File`-typed method arguments route cleanly to `n3tx-files` because the description and body name those concepts at lines 1-5 and 30-70. Queries mentioning streaming, SSE, or `NTTStreamAgent` route cleanly to `n3tx-streaming` because the description and sections name those mechanisms at lines 1-5 and 36-69.

An agent may choose too broad a skill when the user says “backend feature,” “build app,” “storage,” “routes,” “auth,” or “model.” `n3tx-backend` covers all of those at lines 1-5, and `n3tx-build-app` covers many of the same implementation elements at lines 1-5 and 75-89. That makes broad skills useful for orientation but noisy for execution.

Combining skills is safe in principle because they share the same core invariants: avoid duplicate contracts, keep backend authoritative, use actors/adapters for reusable/external IO, verify generated schema/routes/UI. The safety problem is practical: the skills do not state a composition order. A useful default order would be `n3tx-principles` first, then one workflow skill, then one or two noun skills, then `n3tx-testing`; the basis is that `n3tx-principles` itself says to use it first at line 9, `n3tx-build-app` provides sequencing at lines 11-22, and `n3tx-testing` provides verification order at lines 11-17.

Source inspection guidance is safe but too permissive in isolated skills. Most skills say inspect source only when docs/skills are insufficient, but `AGENTS.md` says implementation tasks must start with `/workspace/docs/`, then domain-specific `BACKEND.md`/`FRONTEND.md`, then code only if docs do not answer the question at lines 74-105. The repeated one-line policy should be replaced or expanded with a canonical “Context loading” block so agents do not skip package docs.

## Naming Analysis

Names are consistent and discoverable because all project skills use the `n3tx-` prefix and lowercase hyphen-separated frontmatter names, visible across representative headers such as `n3tx-principles` lines 1-4, `n3tx-framework-maintenance` lines 1-4, and `n3tx-files` lines 1-4. This is good for avoiding collisions with generic skills like `plan`, `bugfix`, or `deep-audit` listed in `.agents/skills/README.md` lines 21-30.

Granularity is mostly right, with one missing taxonomy cue: `n3tx-backend` and `n3tx-frontend` are broad index skills; `n3tx-models`, `n3tx-methods-routes`, `n3tx-storage-relationships`, `n3tx-json-fields`, `n3tx-files`, `n3tx-ui-schema`, `n3tx-ui-components`, and `n3tx-widgets` are noun/mechanism skills. The descriptions do not explicitly mark index skills as “start here, then delegate,” which causes overlap.

`n3tx-storage-relationships` is semantically broad. It covers `StorableMixin`, JSON fields, pagination, `ListRef`, `ManyToMany`, nested routes, and ownership fields at lines 1-5. Because `n3tx-json-fields` separately owns JSON fields at lines 1-5 and `n3tx-authorization` separately owns ownership/protected fields at lines 60-70, the storage skill should be described as “relationship/persistence selection” rather than “all storage.”

`n3tx-networking` and `n3tx-external-integrations` overlap on external APIs and adapters. `n3tx-networking` says external APIs should be wrapped in actor/adapters at lines 38-48, while `n3tx-external-integrations` maps third-party APIs, scraping, webhooks, credentials, sync jobs, and agent/UI availability at lines 1-22. The difference is architectural layer: networking should own protocol/TX adapters, while external integrations should own app/service IO placement.

## Documentation Gaps

1. Missing explicit skill selection matrix. No skill contains a table like “If user says X, load skill Y,” even though `n3tx-principles` already has default decision rules at lines 57-72 and `n3tx-extension-patterns` has a first-choice decision tree at lines 11-24.

2. Missing `n3tx-files` in the provided core-read list. The repo has `.opencode/skills/n3tx-files/SKILL.md` and it is important because file behavior is a first-class package in `AGENTS.md` lines 119-130 and key files are listed at lines 369-378, but the user-provided core list omitted it while other skills reference files repeatedly.

3. Missing ManyToMany depth. Many skills mention `ManyToMany`, including `n3tx-backend` lines 71-77, `n3tx-build-app` lines 82-84, `n3tx-models` lines 85-100, and `n3tx-app-bootstrap` lines 63-74, but no dedicated `n3tx-many-to-many` skill exists. This may be acceptable if `n3tx-storage-relationships` remains the owner, but the descriptions should route `ManyToMany` explicitly to that skill first.

4. Missing migration guidance. Storage skills mention migrations and SQLite JSON detection in `n3tx-json-fields` lines 63-72 and storage/pagination in `n3tx-storage-relationships` lines 9-42, but there is no concise migration checklist for when schema changes require test DBs, file-based SQLite, or migration assertions. `n3tx-testing` only says file-based SQLite for migration/storage tests at lines 46-57.

5. Missing route grammar handoff to canonical docs. `BACKEND.md` contains a complete route table and semantics at lines 159-224, and `FRONTEND.md` contains the corresponding hash route table and nested route behavior at lines 369-440. Skill summaries should cite those docs instead of becoming parallel sources of truth.

6. Missing frontend styling/theme skill. `FRONTEND.md` documents theme architecture, static token entrypoints, `theme.js`, `ntx-theme-button`, shell slots, and verification at lines 107-182, but no `n3tx-styling` or `n3tx-theme` skill exists. The current `n3tx-frontend` description mentions “frontend verification” but not styling/theme at lines 1-5.

7. Missing review/audit behavior for skill maintenance. `n3tx-framework-maintenance` says to consider updating skills when behavior changes at lines 53-55, but no skill maintenance checklist validates frontmatter, trigger overlap, stale commands, or restart requirements for OpenCode sessions.

## Propositions

### Proposition 1: Add A Skill Selection Matrix To `n3tx-principles`

Use `n3tx-principles` as the router because it already says to use it first at line 9 and already has default decision rules at lines 57-72.

Suggested body addition:

```markdown
## Skill Routing

When a task names a concrete mechanism, load the narrow skill after this one:

| User/task mentions | Load next |
|---|---|
| `create_app`, `N3TXApp`, routing level, import order, static dirs | `n3tx-app-bootstrap` |
| model fields, `ProtoModel`, `ActorModel`, `BaseUser`, schema output | `n3tx-models` |
| `ListRef`, `ManyToMany`, pagination, ownership fields | `n3tx-storage-relationships` |
| `dict`, `list`, JSON TEXT, nested embedded data | `n3tx-json-fields` |
| upload, download, `File`, `FileStore`, blob storage | `n3tx-files` |
| `@expose_route`, custom action, route grammar, user injection | `n3tx-methods-routes` |
| auth, JWT, `__access__`, OWNER, ROLE, protected fields | `n3tx-authorization` |
| actor, TX, Matrix, reusable compute | `n3tx-actors` |
| LLM, agent tools, `AgentActor`, `__agent__`, TestModel | `n3tx-agents` |
| SSE, stream events, `NTTStream`, `NTTStreamAgent` | `n3tx-streaming` |
| external API, webhook, scraper, credentials, sync job | `n3tx-external-integrations` |
| protocol bridge, MCP, WebSocket, ActivityPub, NetworkAdapter | `n3tx-networking` |
| `__ui__`, renderer hints, field metadata | `n3tx-ui-schema` |
| Web Component, custom renderer, lifecycle | `n3tx-ui-components` |
| field widget, Formidable input/display | `n3tx-widgets` |
| app verification, tests, E2E | `n3tx-testing` |
```

### Proposition 2: Mark Broad Skills As Index Skills In Frontmatter

The broad skills should intentionally over-trigger, but they should say they are indexes and delegate. Current broad descriptions include many nouns without delegation, visible in `n3tx-backend` lines 1-5 and `n3tx-frontend` lines 1-5.

Suggested frontmatter sketch:

```yaml
---
name: n3tx-backend
description: Backend index for N3TX Python work. Use when a task spans models, routes, storage, auth, actors, agents, files, integrations, or backend verification; then load narrower skills for concrete mechanisms like ListRef, FileStore, @expose_route, __access__, or AgentActor.
argument-hint: "<backend feature: model|route|auth|storage|actor|agent|file>"
---
```

```yaml
---
name: n3tx-frontend
description: Frontend index for N3TX schema-driven UI work. Use when a task spans Web Components, runtime schema, routes, forms, widgets, transport, streaming UI, styling, or verification; then load n3tx-ui-schema, n3tx-ui-components, n3tx-widgets, or n3tx-streaming for implementation.
argument-hint: "<frontend feature: schema|component|widget|route|stream|theme>"
---
```

### Proposition 3: Add A Standard “Combine With” Section To Every Skill

Most skills lack body-level handoffs. Add a small section after the mental model and before examples.

Template:

```markdown
## Combine With

Load these adjacent skills when the task crosses boundaries:

| If the task also involves | Use |
|---|---|
| auth/access/protected fields | `n3tx-authorization` |
| schema-driven UI hints | `n3tx-ui-schema` |
| custom rendered component | `n3tx-ui-components` |
| verification or failing tests | `n3tx-testing` |
| framework internals under `packages/` | `n3tx-framework-maintenance` |
```

Skill-specific examples: `n3tx-agents` should combine with `n3tx-actors` for tool actors, `n3tx-streaming` for streamed runs, and `n3tx-testing` for `TestModel` because it already documents actor tools at lines 58-79, streaming agents at lines 81-83, and TestModel at lines 85-95. `n3tx-files` should combine with `n3tx-authorization` for authorized materialization and `n3tx-external-integrations` for cloud providers because it documents materialization at lines 50-70 and optional providers at lines 72-78.

### Proposition 4: Centralize Source-Reading Policy

Replace repeated one-line source-reading sections with a canonical block that matches `AGENTS.md` lines 74-105 and then allow local exceptions.

Template:

```markdown
## Context Loading

For implementation tasks, follow the repository order:

1. Read cross-cutting docs in `/workspace/docs/` and relevant package docs.
2. Read `BACKEND.md`, `FRONTEND.md`, or both based on scope.
3. Inspect source only when docs/skills are insufficient or observed behavior contradicts docs.
4. If source inspection reveals a stale contract, update or propose updates to docs and skills.

Local exception: framework-maintenance normally requires source inspection after docs because it changes internals.
```

This preserves the stronger repository rule at `AGENTS.md` lines 74-105 while keeping the framework-maintenance exception already stated in `n3tx-framework-maintenance` lines 40-42.

### Proposition 5: Promote `n3tx-files` Into The Core Skill Set

Treat `n3tx-files` as a core project skill alongside storage, models, backend, integrations, and testing. The package is listed in the repository package graph at `AGENTS.md` lines 119-130, and file package key files are listed at lines 369-378. The skill itself contains unique contracts for upload/download routes and typed materialization at lines 30-70 that are not fully captured elsewhere.

Suggested frontmatter remains good, but add a trigger gate:

```yaml
description: N3TX file capability with n3tx-files, File metadata, FileStore providers, multipart upload, binary/range download, file addresses, and File-typed method materialization. Use ONLY when adding user files, blob storage, uploads, downloads, file arguments, or external byte-store providers.
```

### Proposition 6: Tighten Networking Vs External Integrations

Keep both skills, but split the routing contract clearly:

```yaml
name: n3tx-networking
description: Protocol and transport boundaries in N3TX: TX, Matrix, NetworkAPI, WebSocket, MCP, ActivityPub, NetworkAdapter, stream correlation. Use when designing internal routing or external protocol bridges, not ordinary third-party API clients.
```

```yaml
name: n3tx-external-integrations
description: Third-party service integration in N3TX: API clients, scraping, webhooks, credentials, sync jobs, cloud file providers, and agent/UI reusable tools. Use when app code calls outside services; escalate to n3tx-networking only for protocol adapters.
```

This matches the current split where `n3tx-networking` owns adapter architecture at lines 11-33 and `n3tx-external-integrations` owns app/service IO placement at lines 11-22.

### Proposition 7: Add A Route Grammar Canonical Reference Section

Add this to `n3tx-methods-routes`, `n3tx-frontend`, and `n3tx-ui-schema`:

```markdown
## Canonical Route References

- Backend route grammar: `BACKEND.md` route table and semantics.
- Frontend hash route grammar: `FRONTEND.md` hash route table and nested route behavior.
- This skill is a quick summary; if behavior changes, update the canonical docs first, then the skill summary.
```

This prevents drift across `n3tx-methods-routes` lines 51-62, `n3tx-frontend` lines 32-47, `n3tx-ui-schema` lines 46-53, `BACKEND.md` lines 159-224, and `FRONTEND.md` lines 369-440.

### Proposition 8: Add A Missing Theme/Styling Skill Or Expand `n3tx-frontend`

The frontend reference has substantial styling/theme contracts at `FRONTEND.md` lines 107-182, including static theme CSS entrypoints, `theme.js`, theme-button placement, token contracts, and examples. Current frontend/UI skills do not expose a trigger for theme/token/layout work in their descriptions at `n3tx-frontend` lines 1-5, `n3tx-ui-components` lines 1-5, or `n3tx-ui-schema` lines 1-5.

Option A, new skill:

```yaml
---
name: n3tx-styling
description: N3TX frontend styling, themes, CSS token contracts, theme-base.css, dark/light themes, ntx-theme-button, shell slots, and visual verification. Use when changing theme tokens, component CSS, layout responsiveness, or app shell styling.
argument-hint: "<theme, CSS, layout, or visual verification task>"
---
```

Option B, if avoiding another skill, expand `n3tx-frontend` and `n3tx-ui-components` descriptions to include “styling/theme/token contracts.”

### Proposition 9: Add A Skill Maintenance Checklist

`n3tx-framework-maintenance` already says docs and skills should be updated when behavior changes at lines 53-55. Add a checklist so agents maintain the skills as an API:

```markdown
## Skill Update Checklist

When changing public behavior, update skills if any of these changed:

- New trigger nouns, filenames, decorators, classes, routes, or commands.
- Changed route grammar, schema section, method parameter behavior, or generated response shape.
- Changed package dependency boundary or import-order requirement.
- Changed verification command or test runner.
- New anti-pattern discovered during a bug fix or review.

For skill edits, ensure:

- `name` matches the folder.
- `description` says what the skill does and when to trigger.
- Narrow skills use `Use ONLY when...` if adjacent skills might over-trigger.
- Broad skills identify themselves as indexes and link to narrower skills.
- Running OpenCode sessions must be restarted after skill/config changes.
```

### Proposition 10: Enrich `argument-hint` Values

Replace generic hints with trigger examples. Current hints like `<backend feature>`, `<frontend feature>`, and `<component task>` appear in `n3tx-backend` line 4, `n3tx-frontend` line 4, and `n3tx-ui-components` line 4.

Examples:

```yaml
argument-hint: "<model|ListRef|ManyToMany|File|@expose_route|__access__ task>"
argument-hint: "<__ui__|renderer|widget|Web Component|route|stream UI task>"
argument-hint: "<TX|Matrix|NetworkAdapter|MCP|WebSocket|external protocol task>"
```

This improves discoverability without changing body content.

## Prioritized Fix List

| Priority | Change | Why now | Primary files |
|---|---|---|---|
| P0 | Add skill selection matrix to `n3tx-principles`. | It reduces broad-skill over-trigger and gives agents an explicit composition model. | `.opencode/skills/n3tx-principles/SKILL.md` |
| P0 | Mark `n3tx-backend`, `n3tx-frontend`, and `n3tx-build-app` as index/workflow skills in descriptions. | These are the largest overlap sources, as shown by descriptions at `n3tx-backend` lines 1-5 and `n3tx-build-app` lines 1-5. | `.opencode/skills/n3tx-backend/SKILL.md`, `.opencode/skills/n3tx-frontend/SKILL.md`, `.opencode/skills/n3tx-build-app/SKILL.md` |
| P1 | Promote `n3tx-files` into any canonical core-skill inventory. | It exists and owns unique file contracts at lines 30-95, while other skills reference file workflows. | `.opencode/skills/n3tx-files/SKILL.md`, skill docs/indexes |
| P1 | Standardize context-loading/source-reading block. | Current repeated blocks are shorter than the repository docs-first mandate in `AGENTS.md` lines 74-105. | All `.opencode/skills/n3tx-*/SKILL.md` |
| P1 | Add “Combine With” sections to narrow skills. | It makes skill composition deterministic and safe. | All narrow skill docs |
| P2 | Add route grammar references to canonical docs. | Prevents drift between skill summaries and `BACKEND.md`/`FRONTEND.md` route tables. | `n3tx-methods-routes`, `n3tx-frontend`, `n3tx-ui-schema` |
| P2 | Add or expand theme/styling guidance. | `FRONTEND.md` has a substantial theme contract at lines 107-182 not surfaced by a skill trigger. | New `n3tx-styling` or expanded frontend/component skills |
| P2 | Enrich `argument-hint` values. | Hints currently add little routing information beyond generic task labels. | All skill frontmatter |

## Target State

The ideal skill system should have this shape:

```text
User task
  -> n3tx-principles routes by N3TX mechanism
  -> one workflow skill: build-app OR framework-maintenance OR testing
  -> one to three narrow mechanism skills
  -> explicit verification contract
  -> docs/skills update if public behavior changed
```

This target keeps the current strengths: concise bodies, strong guardrails, valid frontmatter, and good N3TX invariants. It fixes the current weaknesses: broad over-trigger, missing handoffs, stale command risk, route grammar duplication, and insufficient discoverability for `n3tx-files`, theme/styling, and concrete trigger nouns.
