# OpenCode Skills Audit: Reorganization Proposal

Audit target: `/workspace/.opencode/skills/`.

Output file: `/workspace/.project/audits/opencode-skills/03-reorganization.md`.

Scope: reorganization proposal only. No skill files were modified.

## Executive Recommendation

The current N3TX OpenCode skill catalog has the right raw material, but it is organized as a flat set of overlapping reference cards. Reorganize it into a small routed catalog:

| Layer | Purpose | Skills |
|---|---|---|
| Router | Select the right skill set and enforce docs-first behavior. | New `n3tx-skill-routing`, keep `n3tx-principles` as philosophy. |
| Workflows | Match task mode: fresh app, established app, framework internals, verification. | `n3tx-build-app`, new `n3tx-change-app`, `n3tx-framework-maintenance`, `n3tx-testing`. |
| Contracts | Own backend authoritative model/API/storage/auth contracts. | `n3tx-models`, `n3tx-methods-routes`, `n3tx-authorization`, `n3tx-storage-relationships`, `n3tx-files`. |
| Capabilities | Own reusable compute, LLM, protocol, streaming, integration boundaries. | `n3tx-actors`, `n3tx-agents`, `n3tx-streaming`, `n3tx-networking`, `n3tx-external-integrations`. |
| UI | Own schema-driven frontend, components, widgets, shell/styling. | `n3tx-ui-schema`, `n3tx-ui-components`, `n3tx-widgets`, new `n3tx-theme-shell`. |
| Guardrails | Escalate boundary smells and extension decisions. | `n3tx-framework-boundaries`, `n3tx-extension-patterns`. |

The key change is not adding more content. It is making skill selection deterministic: descriptions must front-load concrete trigger terms, broad skills must identify themselves as indexes/workflows, and narrow skills must use `Use ONLY when...` to reduce over-triggering.

## Current Catalog Map

### Broad Skills

| Skill | Current role | Evidence | Pain point |
|---|---|---|---|
| `n3tx-principles` | Global philosophy and first-stop guidance. | Description covers any app/model/actor/agent/UI/networking/boundary task, and body says use it first for any N3TX app work (`.opencode/skills/n3tx-principles/SKILL.md:3`, `.opencode/skills/n3tx-principles/SKILL.md:9`). | Valuable, but it competes with every other N3TX skill unless paired with a routing matrix. |
| `n3tx-backend` | Broad backend index. | Description includes models, storage, auth, routes, actors, agents, ManyToMany, files, bootstrap, integrations, and verification (`.opencode/skills/n3tx-backend/SKILL.md:3`). | Too broad for focused implementation; likely to hide narrower guardrails. |
| `n3tx-frontend` | Broad frontend index. | Description covers schema-driven UI, Web Components, routes, forms, widgets, transport, streaming UI, and verification (`.opencode/skills/n3tx-frontend/SKILL.md:3`). | Useful orientation, but overlaps with UI schema, components, widgets, streaming, and missing theme/shell concerns. |
| `n3tx-build-app` | End-to-end app/feature workflow. | Description covers app creation, routing level, models, UI, agents, storage, auth, ManyToMany, files, and verification (`.opencode/skills/n3tx-build-app/SKILL.md:3`). | Correct for fresh vertical slices, but too attractive for established-codebase edits. |
| `n3tx-framework-maintenance` | Framework internals workflow. | Description says use when changing framework packages, docs, architecture, tests, or extension internals (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:3`), and body says not normal app development (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:9`). | Good gate, but description should use uppercase `Use ONLY when` and include `n3tx-files`. |

### Mechanism Skills

| Area | Skills | Current evidence | Reorganization issue |
|---|---|---|---|
| Models/storage | `n3tx-models`, `n3tx-storage-relationships`, `n3tx-json-fields` | Models skill owns base-class choice and data contracts (`.opencode/skills/n3tx-models/SKILL.md:11`); storage skill owns persistence, JSON fields, pagination, ListRef, ManyToMany (`.opencode/skills/n3tx-storage-relationships/SKILL.md:3`); JSON fields skill is focused on `dict`, `list`, typed list, nested payload fields (`.opencode/skills/n3tx-json-fields/SKILL.md:9`). | Keep all three, but demote JSON-field detail out of storage/model examples into a strict focused skill. |
| Routes/auth | `n3tx-methods-routes`, `n3tx-authorization` | Methods/routes says custom behavior belongs in `@expose_route` methods (`.opencode/skills/n3tx-methods-routes/SKILL.md:9`); auth says authorization is backend-owned and schema-exposed (`.opencode/skills/n3tx-authorization/SKILL.md:9`). | Keep separate; add explicit cross-links for user injection and method access. |
| Actors/agents/network | `n3tx-actors`, `n3tx-agents`, `n3tx-networking`, `n3tx-streaming`, `n3tx-external-integrations` | Actors are reusable compute boundaries (`.opencode/skills/n3tx-actors/SKILL.md:9`); agents are actors that reason and actor methods are tools (`.opencode/skills/n3tx-agents/SKILL.md:9`); networking says protocols translate to TX at adapter boundaries (`.opencode/skills/n3tx-networking/SKILL.md:9`); integrations say external IO must be wrapped in reusable N3TX boundaries (`.opencode/skills/n3tx-external-integrations/SKILL.md:9`). | Keep, but clarify routing precedence: integrations for ordinary third-party IO, networking only for transport/protocol adapter work. |
| UI | `n3tx-ui-schema`, `n3tx-ui-components`, `n3tx-widgets`, `n3tx-frontend` | UI schema says backend schema is frontend contract (`.opencode/skills/n3tx-ui-schema/SKILL.md:9`); components says customization composes with schema-driven components (`.opencode/skills/n3tx-ui-components/SKILL.md:9`); widgets customize field rendering while preserving schema (`.opencode/skills/n3tx-widgets/SKILL.md:9`). | Keep three narrow skills; make `n3tx-frontend` an index; add or split out theme/shell. |
| Guardrails/extensions | `n3tx-framework-boundaries`, `n3tx-extension-patterns` | Boundaries skill lists direct SQL, raw fetch, custom routes, file blobs, and ad-hoc tools as avoid paths (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:13`); extension skill says prefer app-level customization before framework extension (`.opencode/skills/n3tx-extension-patterns/SKILL.md:9`). | Keep both; make boundary skill trigger on suspicious words like bypass/workaround/raw/custom route. |

### Missing From The Required Core List

`n3tx-files` should be promoted into the canonical core catalog. It exists, has a focused description for `n3tx-files`, `File`, `FileStore`, upload/download, file addresses, and materialization (`.opencode/skills/n3tx-files/SKILL.md:3`), and it owns unique file routes and materialization contracts (`.opencode/skills/n3tx-files/SKILL.md:30`, `.opencode/skills/n3tx-files/SKILL.md:50`). The package is also first-class in the repo package map and key-file list (`AGENTS.md:119`, `AGENTS.md:369`).

## Pain Points

1. Broad skill collisions are the largest selection failure mode. `n3tx-backend` and `n3tx-build-app` both include models, storage, auth, routes, agents, files, and verification in their descriptions (`.opencode/skills/n3tx-backend/SKILL.md:3`, `.opencode/skills/n3tx-build-app/SKILL.md:3`).

2. The catalog has no explicit router. The prior architecture/API audit proposed a skill routing matrix because current handoffs are implicit (`.project/audits/opencode-skills/01-architecture-api.md:175`, `.project/audits/opencode-skills/01-architecture-api.md:181`).

3. Fresh-codebase guidance and established-codebase guidance are conflated. `n3tx-build-app` correctly gives an end-to-end sequence from domain models through verification (`.opencode/skills/n3tx-build-app/SKILL.md:11`), but established apps often need a smaller change workflow that starts by reading existing models/routes/tests rather than creating a full app slice.

4. Routing-level defaults risk over-building. `n3tx-build-app` recommends `ActorModel` and Level 3 for new serious apps (`.opencode/skills/n3tx-build-app/SKILL.md:32`), while the main guide documents Level 1, Level 2, and Level 3 and says all levels produce identical API endpoints and responses (`AGENTS.md:215`, `AGENTS.md:231`).

5. Route/view grammar is fragmented. Backend route grammar lives in `BACKEND.md` (`BACKEND.md:159`, `BACKEND.md:190`), frontend hash/nested route grammar lives in `FRONTEND.md` (`FRONTEND.md:369`, `FRONTEND.md:409`), while summaries also appear in methods/routes, frontend, and UI-schema skills (`.opencode/skills/n3tx-methods-routes/SKILL.md:51`, `.opencode/skills/n3tx-frontend/SKILL.md:32`, `.opencode/skills/n3tx-ui-schema/SKILL.md:46`).

6. Theme/shell has no focused trigger. `FRONTEND.md` now documents static theme entrypoints, `theme.js`, `ntx-theme-button`, shell placement, and token usage (`FRONTEND.md:107`, `FRONTEND.md:117`, `FRONTEND.md:138`, `FRONTEND.md:176`), but no skill description names theme, shell, topbar, sidebar, or styling as first-class triggers.

7. Source-reading policy is duplicated and weaker than the repository rule. Skills repeat source-inspection one-liners (`.opencode/skills/n3tx-backend/SKILL.md:121`, `.opencode/skills/n3tx-frontend/SKILL.md:81`), while `AGENTS.md` mandates docs-first loading, then domain-specific context, then source only when docs are insufficient (`AGENTS.md:74`, `AGENTS.md:95`, `AGENTS.md:101`).

## Proposed Simplified Taxonomy

### Fresh-Codebase Work

Use this path when the user is creating a new app, example, or feature with no established local pattern.

| Step | Load | Purpose |
|---|---|---|
| 1 | `n3tx-skill-routing` | Pick task mode and concrete mechanism skills. |
| 2 | `n3tx-principles` | Preserve model-first, backend-authoritative, schema-driven invariants. |
| 3 | `n3tx-build-app` | Define vertical-slice workflow and choose routing level. |
| 4 | Narrow skills | Load only the mechanism skills named by the slice: models, auth, storage, routes, agents, UI, files, integrations. |
| 5 | `n3tx-testing` | Verify schema/API/TX/UI contracts. |

Fresh-codebase default should be: start Level 1 for pure CRUD, Level 2 for actor-capable entities on direct HTTP routes, Level 3 only when TX routing, agents, MCP, WebSocket, federation, or protocol adapters are part of the requirement. This preserves zero-to-working simplicity from the project philosophy (`AGENTS.md:58`, `AGENTS.md:62`) and the documented three-level parity (`AGENTS.md:535`, `AGENTS.md:540`, `AGENTS.md:543`).

### Established-Codebase Work

Use this path when modifying an existing app, example, or package consumer.

| Step | Load | Purpose |
|---|---|---|
| 1 | `n3tx-skill-routing` | Determine whether this is app code, framework code, test repair, or a boundary concern. |
| 2 | New `n3tx-change-app` | Read existing models, routes, schemas, tests, and local conventions before editing. |
| 3 | Narrow skills | Load mechanism skills for the exact surface being changed. |
| 4 | `n3tx-framework-boundaries` | Load if the requested change mentions bypassing, custom route, raw fetch, direct SQL, workaround, duplicate schema, or one-off HTTP. |
| 5 | `n3tx-testing` | Run narrow contract checks and adjacent suites. |

`n3tx-change-app` can be a small workflow skill, or `n3tx-build-app` can be renamed/expanded to `n3tx-app-workflow`. I recommend a separate `n3tx-change-app` because established-app edits need conservation and blast-radius mapping, not greenfield assembly.

### Framework Work

Use only when changing `packages/n3tx-*`, framework docs, route/schema/storage internals, extension internals, or first-party test harnesses. `n3tx-framework-maintenance` already contains this gate (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:9`) and workflow (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:31`). It should remain separate and should combine with the specific package-area skill plus `n3tx-testing`.

## Merge, Keep, Split, Rename, Demote

| Skill | Action | Reason |
|---|---|---|
| `n3tx-principles` | Keep, narrow to philosophy plus routing handoff. | It carries core invariants: model-as-app, backend authority, actor/network boundaries, zero-to-working, traceability (`.opencode/skills/n3tx-principles/SKILL.md:13`, `.opencode/skills/n3tx-principles/SKILL.md:23`). |
| New `n3tx-skill-routing` | Add. | Selection logic should be a first-class OpenCode skill because descriptions drive selection and current skills lack a routing matrix. |
| `n3tx-backend` | Keep as backend index, not implementation owner. | It is useful for imports and backend mental model (`.opencode/skills/n3tx-backend/SKILL.md:23`), but description should delegate to narrow skills. |
| `n3tx-frontend` | Keep as frontend index, not implementation owner. | It maps frontend layers (`.opencode/skills/n3tx-frontend/SKILL.md:22`) but should delegate schema/components/widgets/stream/theme. |
| `n3tx-build-app` | Keep for fresh app/vertical slice; remove Level 3 bias. | It has the right sequence (`.opencode/skills/n3tx-build-app/SKILL.md:11`) but should not be selected for tiny established-app edits. |
| New `n3tx-change-app` | Add. | Established codebases need an explicit read-existing-patterns workflow. |
| `n3tx-framework-maintenance` | Keep; tighten `Use ONLY when`. | It is the right framework-internals gate (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:3`). |
| `n3tx-models` | Keep; remove JSON/file deep details into cross-links. | It should own data contract/base class/schema shape, not every storage/file detail. |
| `n3tx-storage-relationships` | Keep; rename in description to relationship/persistence selection. | Current description overlaps JSON fields and auth ownership (`.opencode/skills/n3tx-storage-relationships/SKILL.md:3`). |
| `n3tx-json-fields` | Keep; use `Use ONLY when`. | Its trigger is already focused on `dict`, `list`, typed list, nested payload fields (`.opencode/skills/n3tx-json-fields/SKILL.md:9`). |
| `n3tx-files` | Promote to core. | Dedicated optional package and security/storage boundary (`.opencode/skills/n3tx-files/SKILL.md:9`, `.opencode/skills/n3tx-files/SKILL.md:79`). |
| `n3tx-methods-routes` | Keep; consider absorbing `n3tx-routing-views` only if not adding a new skill. | It owns `@expose_route` and method schema (`.opencode/skills/n3tx-methods-routes/SKILL.md:32`), but route/view grammar may be large enough to split. |
| New `n3tx-routing-views` | Optional split. | Recommended if route/view bugs are common; otherwise add canonical route sections to methods/frontend/UI-schema. |
| `n3tx-authorization` | Keep. | Auth is backend-owned and schema-exposed (`.opencode/skills/n3tx-authorization/SKILL.md:9`). |
| `n3tx-actors` | Keep. | Owns reusable compute/Matrix/TX shape (`.opencode/skills/n3tx-actors/SKILL.md:11`). |
| `n3tx-agents` | Keep. | Owns AgentActor/AgentMixin/tool discovery/import order (`.opencode/skills/n3tx-agents/SKILL.md:11`, `.opencode/skills/n3tx-agents/SKILL.md:58`). |
| `n3tx-streaming` | Keep. | Owns `stream=True`, event schemas, TX/SSE, frontend handlers (`.opencode/skills/n3tx-streaming/SKILL.md:29`, `.opencode/skills/n3tx-streaming/SKILL.md:36`). |
| `n3tx-networking` | Keep, narrow. | Should own protocol/TX adapters, not all third-party API calls (`.opencode/skills/n3tx-networking/SKILL.md:25`). |
| `n3tx-external-integrations` | Keep, narrow. | Should own app/service IO placement, credentials, scraping, webhooks, sync jobs (`.opencode/skills/n3tx-external-integrations/SKILL.md:11`). |
| `n3tx-ui-schema` | Keep. | Owns backend schema as frontend contract (`.opencode/skills/n3tx-ui-schema/SKILL.md:9`). |
| `n3tx-ui-components` | Keep. | Owns Web Component lifecycle/renderers (`.opencode/skills/n3tx-ui-components/SKILL.md:11`). |
| `n3tx-widgets` | Keep. | Owns field-level display/input extension (`.opencode/skills/n3tx-widgets/SKILL.md:47`). |
| New `n3tx-theme-shell` | Add or enrich `n3tx-frontend`. | Theme/shell has enough current behavior to deserve trigger terms (`FRONTEND.md:117`, `FRONTEND.md:138`, `FRONTEND.md:318`). |
| `n3tx-extension-patterns` | Keep as escalation after app-level options. | Its decision tree is useful (`.opencode/skills/n3tx-extension-patterns/SKILL.md:11`). |
| `n3tx-framework-boundaries` | Keep; route suspicious workaround tasks here early. | It has the strongest boundary table (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:13`). |

## Proposed Naming Scheme

Keep existing names for compatibility. Add names only where a missing task mode or large route surface exists.

| Category | Naming pattern | Examples |
|---|---|---|
| Workflow | `n3tx-<verb>-app` or `n3tx-<scope>-maintenance` | `n3tx-build-app`, `n3tx-change-app`, `n3tx-framework-maintenance`. |
| Contract | `n3tx-<contract>` | `n3tx-models`, `n3tx-authorization`, `n3tx-storage-relationships`, `n3tx-methods-routes`. |
| Capability | `n3tx-<capability>` | `n3tx-actors`, `n3tx-agents`, `n3tx-streaming`, `n3tx-networking`. |
| UI | `n3tx-ui-<surface>` except shell/theme | `n3tx-ui-schema`, `n3tx-ui-components`, `n3tx-widgets`, `n3tx-theme-shell`. |
| Meta | `n3tx-skill-<purpose>` | `n3tx-skill-routing`, optional `n3tx-skill-maintenance`. |

Do not rename current skills in place unless there is a strong reason. Renames are expensive because OpenCode selection uses skill names and descriptions. Prefer changing descriptions and adding alias/compatibility stubs.

## Skill-Selection Decision Tree

1. If the task is about `.opencode/skills`, agent files, OpenCode config, skill descriptions, or skill routing, load `customize-opencode` and new `n3tx-skill-maintenance`.

2. If the task is ambiguous N3TX work, load `n3tx-skill-routing` first.

3. If the task asks for a new app, example, or full vertical slice, load `n3tx-principles`, `n3tx-build-app`, and then narrow mechanism skills.

4. If the task modifies an existing app feature, load `n3tx-change-app` and the narrow mechanism skills named by code or user language.

5. If the task changes `packages/n3tx-core`, `packages/n3tx-actors`, `packages/n3tx-ui`, `packages/n3tx-agents`, `packages/n3tx-files`, framework docs, schema/storage/routes/components internals, or test harnesses, load `n3tx-framework-maintenance`.

6. If the task includes `ProtoModel`, `ActorModel`, `BaseUser`, fields, schema output, validation, `__ui__`, or data contract, load `n3tx-models`.

7. If the task includes `dict`, `list`, JSON TEXT, nested payloads, settings, embedded metadata, or lossy JSON serialization, load `n3tx-json-fields`.

8. If the task includes `ListRef`, `ManyToMany`, parent/child, nested routes, pagination, ownership fields, or relationship identity, load `n3tx-storage-relationships`.

9. If the task includes upload, download, blob, attachment, `File`, `FileStore`, `/files/upload`, `/File/{id}/download`, Range, or file argument materialization, load `n3tx-files`.

10. If the task includes JWT, `BaseUser`, `__access__`, OWNER, ROLE, Where, protected fields, user injection, or field access, load `n3tx-authorization`.

11. If the task includes API action, method button, `@expose_route`, custom endpoint, method schema, route mirror, or injected `user`, load `n3tx-methods-routes`.

12. If the task includes route/view grammar, `#Model/@view`, `/ClassName/_`, nested hash routes, renderer fallback, or `@` method/view confusion, load `n3tx-routing-views` if added; otherwise load `n3tx-methods-routes`, `n3tx-frontend`, and `n3tx-ui-schema`.

13. If the task includes TX, Matrix, actor address, lifecycle event, reusable compute, or actor tool, load `n3tx-actors`.

14. If the task includes LLM, agent, `AgentActor`, `__agent__`, tool discovery, TestModel, thread context, or agent streaming, load `n3tx-agents`.

15. If the task includes SSE, streaming method, `stream=True`, event schemas, `NTTStream`, `NTTStreamAgent`, stream cancel, or progressive UI, load `n3tx-streaming`.

16. If the task includes MCP, WebSocket, ActivityPub, NetworkAPI, NetworkAdapter, protocol bridge, adapter streaming, or internal network routing, load `n3tx-networking`.

17. If the task includes third-party APIs, scraping, webhooks, credentials, sync jobs, cloud file providers, or making external capabilities available to agents/UI, load `n3tx-external-integrations`.

18. If the task includes `__ui__`, renderer hints, field order, groups, icon, create label, schema access adaptation, or backend-driven UI metadata, load `n3tx-ui-schema`.

19. If the task includes Web Components, custom renderers, `NTTElement`, `ListElement`, `Component`, lifecycle, Shadow DOM, or router-mounted components, load `n3tx-ui-components`.

20. If the task includes field widget, Formidable input/display, `ui.widget`, backend Widget types, or widget registry, load `n3tx-widgets`.

21. If the task includes theme tokens, `theme-base.css`, dark/light themes, `ntx-theme-button`, topbar, sidebar, profile route, icons, app shell, visual layout, or CSS verification, load `n3tx-theme-shell` if added; otherwise load `n3tx-frontend` and `n3tx-ui-components`.

22. If the task mentions bypass, workaround, direct SQL, custom FastAPI route, raw frontend fetch, duplicate schema/access, file blobs in SQLite/static assets, or ad-hoc LLM tools, load `n3tx-framework-boundaries` before implementing.

23. If the task says normal mechanisms are insufficient or asks for schema/dump extensions, mixins, custom storage, custom auth rules, or new framework extension points, load `n3tx-extension-patterns`.

24. Always end implementation work with `n3tx-testing` or the repository test workflow. The testing skill’s verification order already says narrow behavior first, adjacent tests second, browser/E2E only when needed, and broad suites after narrow checks pass (`.opencode/skills/n3tx-testing/SKILL.md:11`).

## Migration Plan

### Phase 1: Compatibility-Preserving Frontmatter Updates

Update descriptions without renaming folders. This changes selection behavior while preserving existing skill names.

1. Mark broad skills as indexes/workflows: `n3tx-principles`, `n3tx-backend`, `n3tx-frontend`, `n3tx-build-app`.

2. Add `Use ONLY when...` to narrow or high-risk skills: `n3tx-framework-maintenance`, `n3tx-json-fields`, `n3tx-files`, `n3tx-framework-boundaries`, `n3tx-extension-patterns`, optional `n3tx-routing-views`, optional `n3tx-theme-shell`.

3. Front-load concrete trigger keywords in descriptions: filenames, classes, decorators, routes, protocols, packages.

4. Enrich `argument-hint` values with trigger examples instead of generic `<backend feature>` and `<frontend feature>` hints. Current generic hints appear in broad skills (`.opencode/skills/n3tx-backend/SKILL.md:4`, `.opencode/skills/n3tx-frontend/SKILL.md:4`).

### Phase 2: Add Router And Missing Workflow Skills

Add `n3tx-skill-routing` as the OpenCode-facing selection matrix.

Add `n3tx-change-app` unless the team prefers to fold established-codebase behavior into `n3tx-build-app`.

Promote `n3tx-files` into any README/catalog/index even if no new file is needed.

### Phase 3: Add Or Fold Optional Split Skills

Add `n3tx-routing-views` if route/view confusion is recurring. Otherwise enrich `n3tx-methods-routes`, `n3tx-frontend`, and `n3tx-ui-schema` with canonical route references.

Add `n3tx-theme-shell` if visual shell/theme work is common. Otherwise enrich `n3tx-frontend` and `n3tx-ui-components` descriptions with theme/topbar/sidebar/icon terms.

### Phase 4: Standardize Body Template

Apply a common structure to all N3TX project skills:

```markdown
## Trigger
Use this skill when...
Do not use this skill when...

## Read First
Follow AGENTS docs-first order. Read domain docs before source.

## Decision Rules
...

## Canonical Pattern
...

## Combine With
...

## Guardrails
...

## Verification
...

## Drift Anchors
Canonical docs this skill summarizes.
```

### Phase 5: Add Skill Maintenance Validation

Add an optional `n3tx-skill-maintenance` skill or `.opencode/skills/README.md` covering frontmatter conventions, OpenCode restart/reload implications, drift anchors, and compatibility stubs. The prior quality audit already recommended a linter for folder/name match, description existence, trigger front-loading, `Use ONLY when`, command freshness, referenced docs, and mutable defaults (`.project/audits/opencode-skills/02-quality-extensibility.md:315`, `.project/audits/opencode-skills/02-quality-extensibility.md:317`).

## Frontmatter Sketches

### New Router

```yaml
---
name: n3tx-skill-routing
description: "N3TX OpenCode skill routing: choose fresh app, established app, framework maintenance, models, auth, storage, files, routes, actors, agents, UI, streaming, integrations, testing. Use when an N3TX task is ambiguous, spans multiple areas, or needs the right n3tx-* skill set."
argument-hint: "<N3TX task or ambiguous skill-selection question>"
---
```

### Principles As Philosophy, Not Catch-All Implementation

```yaml
---
name: n3tx-principles
description: "N3TX architecture principles: model-first contracts, backend authority, schema-driven frontend, actors/adapters, zero-to-working, boundary discipline. Use for design decisions or before implementation to preserve architectural intent; use n3tx-skill-routing to choose concrete implementation skills."
argument-hint: "<N3TX design or boundary question>"
---
```

### Backend Index

```yaml
---
name: n3tx-backend
description: "N3TX backend index: Python models, generated routes, storage, auth, actors, agents, files, integrations, verification. Use when backend work spans multiple concerns; prefer narrower skills for focused ListRef, FileStore, @expose_route, __access__, AgentActor, or JSON field tasks."
argument-hint: "<backend task: model|route|auth|storage|actor|agent|file|integration>"
---
```

### Frontend Index

```yaml
---
name: n3tx-frontend
description: "N3TX frontend index: runtime schema, DynamicClass, Web Components, routes, forms, widgets, transport, streaming UI, theme/shell, verification. Use when frontend work spans multiple UI concerns; prefer n3tx-ui-schema, n3tx-ui-components, n3tx-widgets, n3tx-streaming, or n3tx-theme-shell for focused work."
argument-hint: "<frontend task: schema|component|widget|route|stream|theme|shell>"
---
```

### Fresh App Workflow

```yaml
---
name: n3tx-build-app
description: "N3TX fresh app and vertical-slice workflow: create_app, N3TXApp, routing Level 1/2/3, models, auth, UI schema, agents, files, integrations, verification. Use when creating a new app/example or complete feature slice; prefer n3tx-change-app for established-codebase modifications."
argument-hint: "<new app, example, or vertical slice>"
---
```

### Established App Workflow

```yaml
---
name: n3tx-change-app
description: "N3TX established-codebase changes: inspect existing models, schemas, routes, UI renderers, tests, and local conventions before editing. Use when modifying an existing N3TX app or feature; combine with narrow mechanism skills for the exact surface."
argument-hint: "<existing app feature or behavior change>"
---
```

### Framework Maintenance

```yaml
---
name: n3tx-framework-maintenance
description: "N3TX framework internals: packages/n3tx-core, n3tx-actors, n3tx-ui, n3tx-agents, n3tx-files, schema/storage/routes/components/tests/docs. Use ONLY when modifying framework packages, public contracts, extension internals, framework docs, or first-party test harnesses."
argument-hint: "<framework package or public contract change>"
---
```

### Files

```yaml
---
name: n3tx-files
description: "N3TX uploads/downloads/blob storage: n3tx-files, File metadata, FileStore, /files/upload, /File/{id}/download, Range, File-typed method args. Use ONLY when adding or debugging user files, attachments, blob providers, upload/download routes, or file argument materialization."
argument-hint: "<file|upload|download|blob|FileStore|attachment task>"
---
```

### Storage Relationships

```yaml
---
name: n3tx-storage-relationships
description: "N3TX persistence and relationship selection: __storable__, pagination, ListRef parent-child routes, ManyToMany shared links, ownership fields, migration-sensitive SQLite behavior. Use when choosing or debugging storage and relationship primitives; use n3tx-json-fields ONLY for embedded dict/list JSON fields."
argument-hint: "<ListRef|ManyToMany|pagination|ownership|relationship task>"
---
```

### JSON Fields

```yaml
---
name: n3tx-json-fields
description: "N3TX dict/list JSON fields: SQLite TEXT serialization, get_json_fields, migrations, embedded metadata/settings/payloads, relationship boundary. Use ONLY when designing, debugging, or changing embedded dict/list/typed-list model fields, not ListRef or ManyToMany relationships."
argument-hint: "<dict|list|JSON TEXT|embedded data task>"
---
```

### Routing Views

```yaml
---
name: n3tx-routing-views
description: "N3TX route/view grammar: /{ClassName}, /{ClassName}/_, nested /Parent/id/Child/id, hash #Model/@view, @ view boundary, renderer fallback, method/action navigation. Use ONLY when changing, debugging, or designing routes, view routes, router behavior, nested identities, or method/view ambiguity."
argument-hint: "<route|view|router|nested identity|@ boundary task>"
---
```

### Theme Shell

```yaml
---
name: n3tx-theme-shell
description: "N3TX theme and app shell: theme-base.css, dark/light themes, theme.js, ntx-theme-button slots, topbar/sidebar/profile, icon registry, visual verification. Use ONLY when changing theme tokens, shell chrome, navigation, profile route, icon rendering, layout CSS, or visual/browser styling behavior."
argument-hint: "<theme|CSS|topbar|sidebar|icon|shell|visual task>"
---
```

### Networking

```yaml
---
name: n3tx-networking
description: "N3TX protocol and transport boundaries: TX, Matrix, NetworkAPI, WebSocket, MCP, ActivityPub, NetworkAdapter, stream correlation, auth interceptors. Use when designing internal actor routing or external protocol bridges; use n3tx-external-integrations for ordinary third-party API clients."
argument-hint: "<TX|Matrix|NetworkAdapter|MCP|WebSocket|protocol task>"
---
```

### External Integrations

```yaml
---
name: n3tx-external-integrations
description: "N3TX third-party integrations: API clients, scraping, webhooks, credentials, sync jobs, cloud file providers, reusable agent/UI tools. Use when app code calls outside services; escalate to n3tx-networking only for protocol adapters or transport bridges."
argument-hint: "<external API|webhook|scraper|credential|sync task>"
---
```

### Framework Boundaries

```yaml
---
name: n3tx-framework-boundaries
description: "N3TX boundary violations: custom FastAPI routes, direct SQL, raw frontend fetch, duplicated schema/access, file blobs in SQLite/static assets, ad-hoc LLM tools, bypass/workaround designs. Use ONLY when a design might bypass N3TX contracts or needs architectural escalation."
argument-hint: "<bypass|workaround|custom route|raw fetch|direct SQL concern>"
---
```

## Compatibility Strategy

1. Preserve all existing folder names and frontmatter `name` values for current skills.

2. Do not rename `n3tx-backend` or `n3tx-frontend`; convert them to index skills through descriptions and body handoffs.

3. Add new skills only for missing task modes or large cross-cutting surfaces: `n3tx-skill-routing`, `n3tx-change-app`, optional `n3tx-routing-views`, optional `n3tx-theme-shell`, optional `n3tx-skill-maintenance`.

4. If a rename is still desired, create a compatibility stub with the old name for one release window. The old skill body should say “prefer `<new-name>`” and contain only routing guidance, not duplicated technical content.

5. After skill edits, tell users to restart OpenCode because running sessions keep already-loaded config/skills. This is an OpenCode behavior constraint and belongs in skill-maintenance guidance.

## Prioritized Roadmap

| Priority | Change | Files | Why |
|---|---|---|---|
| P0 | Add `n3tx-skill-routing` with the decision tree and composition matrix. | New `.opencode/skills/n3tx-skill-routing/SKILL.md`. | Highest leverage; reduces broad-skill collisions without deleting anything. |
| P0 | Rewrite broad skill descriptions as indexes/workflows. | `n3tx-principles`, `n3tx-backend`, `n3tx-frontend`, `n3tx-build-app`. | Current broad descriptions over-trigger (`.opencode/skills/n3tx-backend/SKILL.md:3`, `.opencode/skills/n3tx-build-app/SKILL.md:3`). |
| P0 | Normalize routing-level guidance. | `n3tx-build-app`, `n3tx-models`, `n3tx-app-bootstrap`. | Prevents unnecessary Level 3 actor routing when Level 1/2 satisfies the requirement (`AGENTS.md:231`, `.opencode/skills/n3tx-build-app/SKILL.md:32`). |
| P1 | Promote `n3tx-files` into the canonical core catalog and add `Use ONLY when`. | `n3tx-files`, router/index, backend/build/model cross-links. | Files are first-class and security-sensitive (`AGENTS.md:369`, `.opencode/skills/n3tx-files/SKILL.md:79`). |
| P1 | Add `n3tx-change-app` for established-codebase edits. | New `.opencode/skills/n3tx-change-app/SKILL.md`. | Separates greenfield assembly from conservative app modification. |
| P1 | Add standard `Trigger`, `Read First`, `Combine With`, `Drift Anchors` sections. | All N3TX skills over time. | Makes handoffs explicit and aligns with docs-first mandate (`AGENTS.md:74`, `AGENTS.md:95`). |
| P1 | Add route/view handling. | New `n3tx-routing-views` or enrich `n3tx-methods-routes`, `n3tx-frontend`, `n3tx-ui-schema`. | Route grammar is cross-stack and currently fragmented (`BACKEND.md:159`, `FRONTEND.md:369`). |
| P2 | Add theme/shell handling. | New `n3tx-theme-shell` or enrich frontend/component skills. | Theme/shell docs are substantial but under-triggered (`FRONTEND.md:117`, `FRONTEND.md:138`, `FRONTEND.md:318`). |
| P2 | Add skill-maintenance validation/lint guidance. | New `n3tx-skill-maintenance` or `.opencode/skills/README.md`. | Prevents future drift in frontmatter, commands, docs anchors, and examples. |
| P2 | Demote repeated deep reference content into canonical docs links. | `n3tx-models`, `n3tx-backend`, `n3tx-storage-relationships`, UI route skills. | Keeps skills small and reduces drift against AGENTS/BACKEND/FRONTEND. |

## Top 5 Proposed Catalog Changes

1. Add `n3tx-skill-routing` as the explicit router/index skill.

2. Convert `n3tx-backend`, `n3tx-frontend`, and `n3tx-build-app` descriptions into index/workflow descriptions that delegate to narrow skills.

3. Promote `n3tx-files` into the core catalog and add `Use ONLY when` file/upload/blob trigger gating.

4. Add `n3tx-change-app` for established-codebase modifications so agents stop using fresh-app workflow for small edits.

5. Add either `n3tx-routing-views` and `n3tx-theme-shell`, or explicitly enrich existing frontend/method/UI skills with those trigger terms and canonical doc anchors.
