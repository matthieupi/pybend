# OpenCode N3TX Skills — Quick Audit Report

## Executive Summary

The `.opencode/skills/` subsystem is an agent-facing operating layer for N3TX work. Its job is to help OpenCode select the right architectural context before implementation: principles, workflow, backend contracts, UI schema, actors, agents, networking, storage, files, testing, and framework maintenance. The current catalog succeeds at encoding the most important N3TX invariants: model definitions are the source of truth, the backend is authoritative, frontend behavior adapts from runtime schema, reusable compute belongs behind actors or model methods, and framework work must preserve package boundaries. These invariants are explicit in `n3tx-principles` (`.opencode/skills/n3tx-principles/SKILL.md:13`, `.opencode/skills/n3tx-principles/SKILL.md:15`, `.opencode/skills/n3tx-principles/SKILL.md:17`, `.opencode/skills/n3tx-principles/SKILL.md:21`) and match the repository guide (`AGENTS.md:58`, `AGENTS.md:60`, `AGENTS.md:66`, `AGENTS.md:70`).

The subsystem’s main weakness is not technical correctness inside the individual skills. It is selection ergonomics. The reports converge on the same finding: broad skills over-trigger, narrow skills are not always gated, and cross-skill handoffs are implicit instead of operational. `n3tx-backend` currently claims models, storage, auth, routes, actors, agents, ManyToMany, files, bootstrap, integrations, and verification in one description (`.opencode/skills/n3tx-backend/SKILL.md:3`), while `n3tx-build-app` claims a similarly wide end-to-end surface (`.opencode/skills/n3tx-build-app/SKILL.md:3`) and `n3tx-frontend` spans schema UI, components, routes, forms, widgets, transport, streaming, and verification (`.opencode/skills/n3tx-frontend/SKILL.md:3`). The selection audit names this as the strongest collision pattern (`.project/audits/opencode-skills/04-selection-ergonomics.md:13`) and the architecture/API audit reaches the same conclusion (`.project/audits/opencode-skills/01-architecture-api.md:67`, `.project/audits/opencode-skills/01-architecture-api.md:69`).

The highest-leverage strategic change is to treat skills as a routed catalog, not a flat folder of reference cards. Add a dedicated `n3tx-skill-routing` skill or move an explicit routing matrix into `n3tx-principles`. Then convert `n3tx-backend`, `n3tx-frontend`, and `n3tx-build-app` into explicit index/workflow skills that delegate to narrow mechanism skills. This aligns with the reorganization report’s recommended layered catalog (`.project/audits/opencode-skills/03-reorganization.md:11`, `.project/audits/opencode-skills/03-reorganization.md:15`) and the selection report’s recommendation to classify skills as principles, workflow, broad index, or narrow mechanism (`.project/audits/opencode-skills/04-selection-ergonomics.md:11`).

The second high-leverage change is maintainability: add shared composition sections, drift anchors, linting, and prompt fixtures. The current catalog repeats source-reading policy in many skills, but the repeated one-liners are weaker than the mandatory repository context-loading order in `AGENTS.md` (`AGENTS.md:74`, `AGENTS.md:95`, `AGENTS.md:101`). The quality report calls for a linter that checks frontmatter, trigger terms, duplicate claims, command freshness, referenced docs, package boundaries, and mutable defaults (`.project/audits/opencode-skills/02-quality-extensibility.md:315`, `.project/audits/opencode-skills/02-quality-extensibility.md:317`). This would reduce agent mistakes, lower maintenance cost, and make future skill edits safer.

Resolved position: keep the existing catalog, do not rename existing folders by default, and improve it in-place with a router, selection descriptions, shared sections, and validation. Add only a small number of missing workflow/specialist skills where the reports show recurring complexity: `n3tx-change-app`, `n3tx-routing-views`, `n3tx-theme-shell`, and optionally `n3tx-skill-maintenance`. Promote `n3tx-files` into the canonical skill map because it already exists, owns unique file/security contracts, and is first-class in the package graph (`.opencode/skills/n3tx-files/SKILL.md:3`, `.opencode/skills/n3tx-files/SKILL.md:9`, `AGENTS.md:119`, `AGENTS.md:369`).

## Component Overview

The user prompt refers to 22 skills, but the project-local N3TX catalog includes `n3tx-files` as an additional first-class skill. The prior architecture report includes it in the component inventory (`.project/audits/opencode-skills/01-architecture-api.md:39`), the reorganization report says it should be promoted into the canonical core catalog (`.project/audits/opencode-skills/03-reorganization.md:46`, `.project/audits/opencode-skills/03-reorganization.md:48`), and the skill file exists with file-specific frontmatter and body contracts (`.opencode/skills/n3tx-files/SKILL.md:1`, `.opencode/skills/n3tx-files/SKILL.md:30`, `.opencode/skills/n3tx-files/SKILL.md:50`). This audit treats the current catalog as 23 N3TX project skills.

| Role | Current skills | Current value | Selection risk |
|---|---|---|---|
| Principles | `n3tx-principles` | Encodes model-as-app, backend authority, actors, networking, zero-to-working, traceability (`.opencode/skills/n3tx-principles/SKILL.md:13`, `.opencode/skills/n3tx-principles/SKILL.md:23`). | Says to use first for any N3TX app work, so it needs a routing handoff (`.opencode/skills/n3tx-principles/SKILL.md:9`). |
| Guardrail escalation | `n3tx-framework-boundaries` | Converts architecture principles into concrete avoid/correct rules (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:13`, `.opencode/skills/n3tx-framework-boundaries/SKILL.md:54`). | Anti-pattern trigger words are mostly body text, not front-loaded in description (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:3`). |
| Broad backend index | `n3tx-backend` | Useful imports, mental model, guardrails, and feature shape (`.opencode/skills/n3tx-backend/SKILL.md:23`, `.opencode/skills/n3tx-backend/SKILL.md:102`). | Over-broad description competes with narrow skills (`.opencode/skills/n3tx-backend/SKILL.md:3`). |
| Broad frontend index | `n3tx-frontend` | Schema-driven frontend mental model and raw-fetch guardrails (`.opencode/skills/n3tx-frontend/SKILL.md:9`, `.opencode/skills/n3tx-frontend/SKILL.md:64`). | Does not surface theme/shell/sidebar/profile/icon complexity from `FRONTEND.md` (`FRONTEND.md:107`, `FRONTEND.md:138`, `FRONTEND.md:318`). |
| Fresh app workflow | `n3tx-build-app` | Strong vertical-slice sequence from domain models through verification (`.opencode/skills/n3tx-build-app/SKILL.md:11`). | Conflates fresh apps and established-codebase edits; has Level 3 bias (`.opencode/skills/n3tx-build-app/SKILL.md:32`). |
| Framework workflow | `n3tx-framework-maintenance` | Correctly gates framework internals and docs/test workflow (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:9`, `.opencode/skills/n3tx-framework-maintenance/SKILL.md:31`). | Omits `n3tx-files` from package boundary table even though it is a first-class package (`AGENTS.md:119`, `.opencode/skills/n3tx-framework-maintenance/SKILL.md:21`). |
| Verification workflow | `n3tx-testing` | Central verification order and contract-first checks (`.opencode/skills/n3tx-testing/SKILL.md:11`, `.opencode/skills/n3tx-testing/SKILL.md:18`). | Frontend command set is shallower than `FRONTEND.md` (`.opencode/skills/n3tx-testing/SKILL.md:37`, `FRONTEND.md:184`). |
| Model contracts | `n3tx-models` | Base-class choice, canonical model, schema expectations, relationships, files, JSON fields (`.opencode/skills/n3tx-models/SKILL.md:11`, `.opencode/skills/n3tx-models/SKILL.md:22`). | Overlaps with storage/files/JSON/UI skills; defaults to `ActorModel` too broadly (`.opencode/skills/n3tx-models/SKILL.md:20`). |
| App bootstrap | `n3tx-app-bootstrap` | Import order, `create_app`, `N3TXApp`, static merge, files, relationships (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:9`, `.opencode/skills/n3tx-app-bootstrap/SKILL.md:90`). | Has Level 1 and Level 3 headings but no Level 2 heading (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:23`, `.opencode/skills/n3tx-app-bootstrap/SKILL.md:31`, `AGENTS.md:540`). |
| Storage/relationships | `n3tx-storage-relationships`, `n3tx-json-fields`, `n3tx-files` | Covers storage, relationship primitives, embedded JSON, and file metadata/bytes split (`.opencode/skills/n3tx-storage-relationships/SKILL.md:46`, `.opencode/skills/n3tx-json-fields/SKILL.md:25`, `.opencode/skills/n3tx-files/SKILL.md:9`). | Storage skill overlaps with JSON fields, and file skill discoverability is weaker than its importance (`.project/audits/opencode-skills/01-architecture-api.md:9`). |
| Routes/auth | `n3tx-methods-routes`, `n3tx-authorization` | Owns `@expose_route`, method schema, route grammar, `__access__`, user injection, protected fields (`.opencode/skills/n3tx-methods-routes/SKILL.md:9`, `.opencode/skills/n3tx-authorization/SKILL.md:9`). | Route grammar is fragmented across backend/frontend/method/UI skills (`.project/audits/opencode-skills/02-quality-extensibility.md:119`, `BACKEND.md:159`, `FRONTEND.md:369`). |
| Actors/agents/capabilities | `n3tx-actors`, `n3tx-agents`, `n3tx-streaming` | Owns TX/Matrix, AgentActor/AgentMixin, tool discovery, streaming contracts (`.opencode/skills/n3tx-actors/SKILL.md:11`, `.opencode/skills/n3tx-agents/SKILL.md:58`, `.opencode/skills/n3tx-streaming/SKILL.md:36`). | Needs more explicit composition: agents with app-bootstrap, actors, streaming, testing (`.project/audits/opencode-skills/01-architecture-api.md:115`). |
| Network/integration | `n3tx-networking`, `n3tx-external-integrations` | Keeps protocols behind adapters and third-party IO behind reusable N3TX boundaries (`.opencode/skills/n3tx-networking/SKILL.md:9`, `.opencode/skills/n3tx-external-integrations/SKILL.md:9`). | Overlap on external APIs and protocol bridges; descriptions need negative routing (`.project/audits/opencode-skills/03-reorganization.md:42`). |
| UI specialists | `n3tx-ui-schema`, `n3tx-ui-components`, `n3tx-widgets` | Separates backend UI contract, whole components/renderers, and field widgets (`.opencode/skills/n3tx-ui-schema/SKILL.md:9`, `.opencode/skills/n3tx-ui-components/SKILL.md:24`, `.opencode/skills/n3tx-widgets/SKILL.md:47`). | Needs sharper trigger boundaries and theme/shell handling (`.project/audits/opencode-skills/04-selection-ergonomics.md:78`, `.project/audits/opencode-skills/04-selection-ergonomics.md:80`). |
| Extension selection | `n3tx-extension-patterns` | Strong decision tree for choosing app-level mechanisms before framework extensions (`.opencode/skills/n3tx-extension-patterns/SKILL.md:11`). | Description should say `Use ONLY after...` to prevent premature extension (`.project/audits/opencode-skills/04-selection-ergonomics.md:94`). |

### Current Skill Relationships

```text
User task
  |
  +--> n3tx-principles  (says use first for any N3TX app work)
  |
  +--> broad skills compete for common nouns
  |      |
  |      +--> n3tx-backend: models + storage + auth + routes + actors + agents + files
  |      +--> n3tx-frontend: schema + components + routes + widgets + streaming
  |      +--> n3tx-build-app: app + feature + routing + models + UI + agents + files
  |
  +--> narrow mechanism skills selected only when prompt names exact noun
         |
         +--> ListRef / ManyToMany      -> n3tx-storage-relationships
         +--> dict / list JSON          -> n3tx-json-fields
         +--> File / FileStore / upload -> n3tx-files
         +--> @expose_route             -> n3tx-methods-routes
         +--> __access__ / OWNER        -> n3tx-authorization
         +--> TX / Matrix               -> n3tx-actors
         +--> AgentActor / __agent__    -> n3tx-agents
         +--> NTTStream / SSE           -> n3tx-streaming
         +--> Widget                    -> n3tx-widgets
```

### Proposed Skill Relationships

```text
User task
  |
  +--> n3tx-skill-routing
       |
       +--> n3tx-principles for architecture and boundary defaults
       |
       +--> exactly one workflow/index when useful
       |      |
       |      +--> n3tx-build-app        fresh app / vertical slice
       |      +--> n3tx-change-app       established-codebase change
       |      +--> n3tx-backend          broad backend index only
       |      +--> n3tx-frontend         broad frontend index only
       |      +--> n3tx-framework-maintenance framework internals only
       |
       +--> one to three narrow mechanism skills
       |      |
       |      +--> models / storage / files / methods / auth
       |      +--> actors / agents / streaming / networking / integrations
       |      +--> ui-schema / ui-components / widgets / theme-shell
       |
       +--> n3tx-framework-boundaries if workaround/bypass/custom route/raw fetch appears
       |
       +--> n3tx-testing for verification of behavior changes
```

## Key Findings

### Critical / High-Leverage Issues

| Finding | Evidence | Severity | Recommendation |
|---|---|---|---|
| Broad skills over-trigger and can suppress narrower contracts. | `n3tx-backend` and `n3tx-build-app` both claim models, storage, auth, routes, agents, files, and verification (`.opencode/skills/n3tx-backend/SKILL.md:3`, `.opencode/skills/n3tx-build-app/SKILL.md:3`). Reports identify this as the largest selection failure mode (`.project/audits/opencode-skills/03-reorganization.md:52`, `.project/audits/opencode-skills/04-selection-ergonomics.md:21`). | Critical | Rewrite broad descriptions as `index` or `workflow` descriptions and require delegation to narrow skills. |
| No explicit router/index skill exists. | Prior audits proposed a selection matrix because handoffs are implicit (`.project/audits/opencode-skills/01-architecture-api.md:159`, `.project/audits/opencode-skills/03-reorganization.md:54`, `.project/audits/opencode-skills/04-selection-ergonomics.md:106`). | Critical | Add `n3tx-skill-routing` or embed a routing matrix in `n3tx-principles`. Prefer a new skill for selection API clarity. |
| Level selection defaults can over-build simple apps. | `n3tx-build-app` recommends `ActorModel` and Level 3 for new serious apps (`.opencode/skills/n3tx-build-app/SKILL.md:32`), while `AGENTS.md` documents Level 1/2/3 and says all three produce identical API endpoints and responses (`AGENTS.md:215`, `AGENTS.md:231`, `AGENTS.md:535`). | High | Standardize on lowest-sufficient level: Level 1 for pure CRUD, Level 2 for actor-capable direct routes, Level 3 for TX/protocol/agent routing. |
| `n3tx-files` is present but under-indexed. | The file skill owns routes, addresses, materialization, and verification (`.opencode/skills/n3tx-files/SKILL.md:30`, `.opencode/skills/n3tx-files/SKILL.md:50`, `.opencode/skills/n3tx-files/SKILL.md:88`), and the package is first-class in `AGENTS.md` (`AGENTS.md:119`, `AGENTS.md:369`). Reports call out omission from core lists (`.project/audits/opencode-skills/01-architecture-api.md:9`, `.project/audits/opencode-skills/03-reorganization.md:48`). | High | Promote `n3tx-files` into every router/catalog table and add `Use ONLY when...` file/blob/upload gating. |
| Source-reading policy is duplicated and weaker than repository policy. | Many skills repeat local source-reading one-liners (`.opencode/skills/n3tx-backend/SKILL.md:121`, `.opencode/skills/n3tx-frontend/SKILL.md:81`, `.opencode/skills/n3tx-files/SKILL.md:97`), while `AGENTS.md` mandates docs-first, domain context, then source (`AGENTS.md:74`, `AGENTS.md:95`, `AGENTS.md:101`). | High | Replace repeated one-liners with shared `Read First` / `Escalate To Source When` sections anchored to `AGENTS.md`. |
| Route/view grammar is fragmented across skills and docs. | Methods skill summarizes class/table routes (`.opencode/skills/n3tx-methods-routes/SKILL.md:51`), frontend skill summarizes hash routes (`.opencode/skills/n3tx-frontend/SKILL.md:32`), UI schema summarizes `@` semantics (`.opencode/skills/n3tx-ui-schema/SKILL.md:46`), while canonical backend/frontend docs are deeper (`BACKEND.md:159`, `BACKEND.md:211`, `FRONTEND.md:369`, `FRONTEND.md:409`). | High | Add `n3tx-routing-views` or add canonical route sections to methods/frontend/UI-schema with doc anchors. |
| Theme/shell work has no focused trigger. | `FRONTEND.md` documents theme entrypoints, theme runtime, shell slots, sidebar routes, profile route, icons, and token contracts (`FRONTEND.md:107`, `FRONTEND.md:117`, `FRONTEND.md:138`, `FRONTEND.md:176`, `FRONTEND.md:318`), but frontend skill description omits theme/shell (`.opencode/skills/n3tx-frontend/SKILL.md:3`). | Medium/High | Add `n3tx-theme-shell` if theme/shell work is common; otherwise enrich `n3tx-frontend` and `n3tx-ui-components`. |
| No skill linting or drift detection exists. | Quality audit recommends validation for frontmatter, triggers, duplicated docs, commands, package graph, referenced docs, and mutable defaults (`.project/audits/opencode-skills/02-quality-extensibility.md:315`, `.project/audits/opencode-skills/02-quality-extensibility.md:621`). | High | Add `.opencode/scripts/lint-skills.mjs`, drift anchors, and prompt-selection fixtures. |
| Skill examples teach mutable default patterns. | Examples use `= []`, `= {}`, or `Field(default=[])` in backend/model/storage/JSON examples (`.opencode/skills/n3tx-backend/SKILL.md:71`, `.opencode/skills/n3tx-models/SKILL.md:61`, `.opencode/skills/n3tx-json-fields/SKILL.md:33`, `.opencode/skills/n3tx-storage-relationships/SKILL.md:97`). | Medium | Prefer `Field(default_factory=list)` and `Field(default_factory=dict)` in examples unless intentionally documenting framework behavior. |
| External integration secrets need clearer architecture. | Integration skill says not to expose secrets in schema/responses (`.opencode/skills/n3tx-external-integrations/SKILL.md:72`) and recommends storable integration config (`.opencode/skills/n3tx-external-integrations/SKILL.md:15`), but lacks a credential boundary section. | Medium | Add a `Credentials and Secrets` section with environment/secret-handle/protected-field guidance. |

### Design Strengths

| Strength | Evidence | Preserve by |
|---|---|---|
| Strong architectural north star. | `n3tx-principles` concisely covers model source of truth, backend authority, actors, networking, zero-to-working, and traceability (`.opencode/skills/n3tx-principles/SKILL.md:13`, `.opencode/skills/n3tx-principles/SKILL.md:23`). | Keep it as philosophy and boundary intent, but add routing handoff. |
| Good “what not to do” guardrails. | Boundary and backend skills prohibit custom app routes, direct SQL, raw fetch, duplicate auth, file bytes in SQLite, and ad-hoc tools (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:13`, `.opencode/skills/n3tx-backend/SKILL.md:102`). | Preserve guardrail tables in narrow skills and add trigger words in descriptions. |
| Narrow skills are effective when they front-load concrete mechanisms. | `n3tx-json-fields`, `n3tx-streaming`, and `n3tx-files` descriptions name concrete terms like dict/list, SQLite TEXT, SSE, `stream=True`, `FileStore`, upload/download, and materialization (`.opencode/skills/n3tx-json-fields/SKILL.md:3`, `.opencode/skills/n3tx-streaming/SKILL.md:3`, `.opencode/skills/n3tx-files/SKILL.md:3`). | Extend the same pattern to all narrow skills. |
| Verification mindset is contract-oriented. | `n3tx-testing` starts with narrow behavior/schema/API checks before broad suites (`.opencode/skills/n3tx-testing/SKILL.md:11`), matching repository verification values (`AGENTS.md:22`). | Make `n3tx-testing` a standard companion for behavior-changing tasks. |
| Package boundaries are recognized. | Framework maintenance preserves acyclic dependencies (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:14`), matching the package graph (`AGENTS.md:123`). | Update package table to include `n3tx-files` and enforce graph linting. |
| Skills are compact and easy to scan. | Most skills use short mental model, pattern, guardrails, verification, and source-reading sections, e.g. widgets (`.opencode/skills/n3tx-widgets/SKILL.md:9`, `.opencode/skills/n3tx-widgets/SKILL.md:47`, `.opencode/skills/n3tx-widgets/SKILL.md:56`). | Add shared sections without expanding every skill into full docs. |

### Design Trade-offs

| Trade-off | Position |
|---|---|
| Broad skills vs narrow skills | Keep broad skills, but make them indexes/workflows. Broad skills are valuable when the user asks for a vertical slice or broad backend/frontend orientation, but they should delegate concrete nouns to narrow skills. |
| Self-contained guidance vs centralized routing | Keep skills self-contained enough to execute, but centralize selection rules in `n3tx-skill-routing` and duplicate only short `Combine With` sections. This reduces drift without making narrow skills unusable alone. |
| Docs-first vs source-reading | Preserve docs-first as mandatory for implementation (`AGENTS.md:74`), but allow framework maintenance to inspect source after docs because it changes internals (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:40`). |
| Add missing skills vs catalog sprawl | Add only router/workflow/specialist skills that solve selection failures. `n3tx-skill-routing` and `n3tx-change-app` are high-value. `n3tx-routing-views` and `n3tx-theme-shell` are warranted if route/theme work is frequent; otherwise enrich existing skills. |
| Duplicate route/theme summaries vs canonical docs | Skills should summarize and route; `BACKEND.md` and `FRONTEND.md` remain canonical for route/theme grammar (`BACKEND.md:159`, `FRONTEND.md:369`, `FRONTEND.md:107`). Add anchors rather than copying every rule. |
| Lowest-level app default vs actor-first default | Choose the lowest routing level that satisfies requirements. This preserves N3TX’s zero-to-working philosophy (`AGENTS.md:62`) and avoids overbuilding while still supporting actor/agent/protocol apps. |

### Improvement Opportunities

| Rank | Improvement | Impact | Effort | Category |
|---|---|---:|---:|---|
| 1 | Add `n3tx-skill-routing` with trigger matrix, composition rules, and fresh/established flows. | Very high | Medium | Selection |
| 2 | Rewrite broad frontmatter descriptions as indexes/workflows. | Very high | Low | Selection |
| 3 | Add `Use ONLY when...` and negative routing clauses to narrow collision-prone skills. | High | Medium | Trigger quality |
| 4 | Normalize Level 1/2/3 guidance across build/models/bootstrap. | High | Low | Correctness |
| 5 | Promote `n3tx-files` in the catalog and file workflows. | High | Low | Coverage |
| 6 | Add shared `Use First`, `Combine With`, `Do Not Use For`, `Verification`, `Escalate To Source When`. | High | Medium | Composition |
| 7 | Add skill linting and selection fixtures. | High | Medium | Maintainability |
| 8 | Add `n3tx-change-app` established-codebase workflow. | Medium/High | Medium | Workflow |
| 9 | Add or enrich route/view grammar guidance. | Medium/High | Medium | Coverage |
| 10 | Add or enrich theme/shell guidance. | Medium | Medium | Coverage |
| 11 | Replace mutable defaults in examples. | Medium | Low | Quality |
| 12 | Add credentials/secrets section to integrations. | Medium | Low | Security |
| 13 | Enrich frontend verification lane selection. | Medium | Low | Verification |
| 14 | Add drift anchors for duplicated docs claims. | Medium | Medium | Maintainability |

## Strategic Propositions

### P1: Add an N3TX Skill Router / Selection Index

Current state: the catalog has no explicit router, and prior reports independently recommend one (`.project/audits/opencode-skills/01-architecture-api.md:175`, `.project/audits/opencode-skills/02-quality-extensibility.md:435`, `.project/audits/opencode-skills/03-reorganization.md:105`, `.project/audits/opencode-skills/04-selection-ergonomics.md:106`). `n3tx-principles` already says to use it first (`.opencode/skills/n3tx-principles/SKILL.md:9`), but it is currently philosophy plus default mechanisms, not a full selection index.

Proposed new skill:

```markdown
---
name: n3tx-skill-routing
description: N3TX OpenCode skill routing: choose fresh app, established app, framework maintenance, models, auth, storage, files, routes, actors, agents, UI, streaming, integrations, testing. Use when an N3TX task is ambiguous, spans multiple areas, or needs the right n3tx-* skill set.
argument-hint: "<N3TX task or ambiguous skill-selection question>"
---

# N3TX Skill Routing

## Use First

Use this skill before implementation when the user asks for N3TX work and the
right skill set is not obvious from one concrete mechanism.

## Selection Rules

1. Load `n3tx-principles` for architecture and boundary defaults.
2. Load exactly one workflow/index when useful: `n3tx-build-app`, `n3tx-change-app`, `n3tx-backend`, `n3tx-frontend`, or `n3tx-framework-maintenance`.
3. Load one to three narrow mechanism skills for concrete nouns.
4. Load `n3tx-framework-boundaries` before editing when the task mentions bypass, workaround, custom route, direct SQL, raw fetch, duplicate schema/access, internal HTTP, or blobs in SQLite/static assets.
5. Load `n3tx-testing` for bugfixes, features, first tests, or behavior changes.

## Router Matrix

| User says / files touched | Primary | Secondary | Avoid |
|---|---|---|---|
| `create_app`, `N3TXApp`, `main.py`, routing level | `n3tx-app-bootstrap` | `n3tx-build-app`, `n3tx-models`, `n3tx-testing` | `n3tx-framework-maintenance` unless packages are edited |
| New app or vertical slice | `n3tx-build-app` | `n3tx-app-bootstrap`, `n3tx-models`, `n3tx-testing` | `n3tx-extension-patterns` until normal mechanisms fail |
| Existing app change | `n3tx-change-app` | Exact mechanism skill, `n3tx-testing` | `n3tx-build-app` unless full slice |
| `ProtoModel`, `ActorModel`, fields, schema | `n3tx-models` | storage, auth, UI schema | `n3tx-backend` as primary for one model |
| `dict`, `list`, JSON TEXT | `n3tx-json-fields` | `n3tx-models`, `n3tx-testing` | relationships as primary |
| `ListRef`, `ManyToMany`, nested routes | `n3tx-storage-relationships` | `n3tx-models`, `n3tx-authorization` | JSON fields unless embedded data |
| upload, download, blob, `FileStore`, attachment | `n3tx-files` | auth, testing, external integrations | backend as primary |
| `@expose_route`, action, method schema | `n3tx-methods-routes` | auth, streaming, boundaries | custom FastAPI route |
| JWT, OWNER, ROLE, protected fields | `n3tx-authorization` | methods, models, testing | frontend as authority |
| TX, Matrix, reusable compute | `n3tx-actors` | methods, agents, networking | build-app unless vertical slice |
| `AgentActor`, `__agent__`, tool discovery | `n3tx-agents` | actors, bootstrap, streaming, testing | external integrations unless API calls |
| SSE, `stream=True`, `NTTStream` | `n3tx-streaming` | methods, agents, UI components | networking unless adapter changes |
| MCP, WebSocket, ActivityPub, adapter | `n3tx-networking` | actors, streaming, auth | external integrations for ordinary API clients |
| third-party API, webhook, scraper, credentials | `n3tx-external-integrations` | actors, auth, files, agents | networking unless protocol bridge |
| `__ui__`, field order, renderer hints | `n3tx-ui-schema` | models, widgets, components | components if schema hints suffice |
| Web Component, `NTTElement`, renderer lifecycle | `n3tx-ui-components` | ui-schema, streaming, testing | widgets unless field-level |
| Formidable widget, `ui.widget` | `n3tx-widgets` | ui-schema, testing | components unless whole entity |
| theme tokens, topbar, sidebar, profile, icons | `n3tx-theme-shell` | frontend, components, testing | backend unless schema changes |
| framework packages or docs internals | `n3tx-framework-maintenance` | relevant area skill, testing | build-app as primary |
```

What gets simpler: broad skills can shrink into indexes, narrow skills can stop carrying implicit routing logic, and agents get a deterministic composition order. This addresses selection failures in ambiguous prompts like “add uploads,” “make this model agentic,” and “fix route view” (`.project/audits/opencode-skills/04-selection-ergonomics.md:206`).

Migration path: add the new skill first without modifying existing skills, then update `n3tx-principles` to say “use `n3tx-skill-routing` for concrete skill selection.” Next, rewrite frontmatter descriptions to align with the router. Finally, validate with prompt fixtures.

Risk: a new router adds one more skill. Mitigation: keep it short, selection-focused, and avoid duplicating implementation details. OpenCode skills require restart after edits because running sessions keep already-loaded skill/config state, per the OpenCode customization constraints loaded for this task.

### P2: Convert Broad Skills into Workflow/Index Skills

Current state: `n3tx-backend`, `n3tx-frontend`, and `n3tx-build-app` are useful but over-claim concrete mechanisms (`.opencode/skills/n3tx-backend/SKILL.md:3`, `.opencode/skills/n3tx-frontend/SKILL.md:3`, `.opencode/skills/n3tx-build-app/SKILL.md:3`). Reports recommend marking them as index/workflow skills (`.project/audits/opencode-skills/01-architecture-api.md:206`, `.project/audits/opencode-skills/03-reorganization.md:200`, `.project/audits/opencode-skills/04-selection-ergonomics.md:286`).

Proposed `n3tx-backend` frontmatter:

```yaml
---
name: n3tx-backend
description: N3TX backend index: ProtoModel, ActorModel, generated routes, storage, auth, actors, agents, files, integrations, verification. Use when backend work spans multiple mechanisms; prefer narrower skills for focused ListRef, dict/list JSON, FileStore, @expose_route, __access__, AgentActor, or create_app work.
argument-hint: "<backend task: model|route|auth|storage|actor|agent|file|integration>"
---
```

Proposed `n3tx-frontend` frontmatter:

```yaml
---
name: n3tx-frontend
description: N3TX frontend index: runtime schema, DynamicClass, Web Components, routes, forms, widgets, transport, streaming UI, theme/shell, verification. Use when frontend work spans multiple UI concerns; prefer n3tx-ui-schema, n3tx-ui-components, n3tx-widgets, n3tx-streaming, or n3tx-theme-shell for focused work.
argument-hint: "<frontend task: schema|component|widget|route|stream|theme|shell>"
---
```

Proposed `n3tx-build-app` frontmatter:

```yaml
---
name: n3tx-build-app
description: N3TX fresh app and vertical-slice workflow: create_app, N3TXApp, routing Level 1/2/3, models, auth, UI schema, agents, files, integrations, verification. Use when creating a new app/example or complete feature slice; prefer n3tx-change-app for established-codebase modifications.
argument-hint: "<new app, example, or vertical slice>"
---
```

Before: broad skills contain enough snippets to appear sufficient for focused work. After: broad skills orient and delegate. For example, file work moves from backend summary to `n3tx-files`, where upload/download routes and typed materialization are complete (`.opencode/skills/n3tx-backend/SKILL.md:79`, `.opencode/skills/n3tx-files/SKILL.md:30`, `.opencode/skills/n3tx-files/SKILL.md:50`).

Body sketch for broad skills:

```markdown
## Role

This is an index/workflow skill, not the owner of every mechanism it mentions.

## Delegate To

| If the task includes | Load |
|---|---|
| model fields, base classes, schema shape | `n3tx-models` |
| relationships or pagination | `n3tx-storage-relationships` |
| dict/list embedded fields | `n3tx-json-fields` |
| files, uploads, downloads, FileStore | `n3tx-files` |
| custom actions or route grammar | `n3tx-methods-routes` |
| auth/access/protected fields | `n3tx-authorization` |
| verification or tests | `n3tx-testing` |
```

### P3: Tighten Narrow Skill Trigger Descriptions

Current state: the strongest narrow skills already front-load concrete terms (`.opencode/skills/n3tx-json-fields/SKILL.md:3`, `.opencode/skills/n3tx-streaming/SKILL.md:3`, `.opencode/skills/n3tx-files/SKILL.md:3`), but many descriptions lack `Use ONLY when...` and negative routing clauses (`.project/audits/opencode-skills/02-quality-extensibility.md:197`, `.project/audits/opencode-skills/04-selection-ergonomics.md:98`).

Recommended pattern:

```yaml
description: "HIGH-SIGNAL TERMS: classes, files, routes, decorators. Use ONLY when <narrow condition>; use <neighbor skill> for <adjacent condition>."
```

Actors:

```yaml
description: "N3TX actor capabilities: ActorModel, Actor, TX, Matrix, ActorProxy, lifecycle events, reusable compute, tool actors. Use ONLY when designing actor-backed capabilities or actor routing; use n3tx-models for ordinary schema fields and n3tx-networking for protocol adapters."
```

Networking:

```yaml
description: "N3TX protocol routing: TX, Matrix, NetworkAPI, NetworkAdapter, WebSocket, MCP, ActivityPub, stream correlation, auth interceptors. Use ONLY for internal actor routing or external protocol bridges; use n3tx-external-integrations for ordinary third-party API clients."
```

Widgets:

```yaml
description: "N3TX field widgets: ui.widget, backend Widget types, Formidable, registerWidget, display/edit/list rendering. Use ONLY when customizing one field's input/display behavior; use n3tx-ui-components for whole entity or collection renderers."
```

UI schema:

```yaml
description: "N3TX backend-driven UI schema: __ui__, field_order, groups, renderer hints, ui.icon, ui.create_label, access adaptation, route/view metadata. Use ONLY when shaping UI through backend model schema; use n3tx-ui-components for custom Web Components."
```

Extension patterns:

```yaml
description: "N3TX extension points: schema_extension, dump_extension, register_mixin, custom storage, Widget, NetworkAdapter, AccessRule. Use ONLY after __ui__, widgets, @expose_route, actors, or app-level configuration cannot express the need."
```

Files:

```yaml
description: "N3TX uploads/downloads/blob storage: n3tx-files, File metadata, FileStore, /files/upload, /File/{id}/download, Range, File-typed method args. Use ONLY when adding or debugging user files, attachments, blob providers, upload/download routes, or file argument materialization."
```

Framework boundaries:

```yaml
description: "N3TX boundary violations: custom FastAPI routes, direct SQL, raw fetch, duplicated schema/access, JSON relationship arrays, blobs in SQLite/static assets, internal HTTP, ad-hoc LLM tools. Use ONLY when a design might bypass N3TX contracts or needs architectural escalation."
```

### P4: Reorganize / Merge / Add Missing Skills

Position: do not merge away most current skills. The current separation is mostly useful; the failure is routing. Keep names for compatibility, rewrite descriptions, and add only missing workflow/specialist skills.

Concrete recommendations:

| Skill | Action | Reason |
|---|---|---|
| `n3tx-principles` | Keep, narrow to philosophy plus router handoff. | It carries core intent (`.opencode/skills/n3tx-principles/SKILL.md:11`). |
| `n3tx-skill-routing` | Add. | Explicit selection matrix is the top recommendation across reports (`.project/audits/opencode-skills/04-selection-ergonomics.md:286`). |
| `n3tx-backend` | Keep as index. | Useful public imports and guardrails (`.opencode/skills/n3tx-backend/SKILL.md:23`, `.opencode/skills/n3tx-backend/SKILL.md:102`). |
| `n3tx-frontend` | Keep as index. | Useful schema-driven frontend mental model (`.opencode/skills/n3tx-frontend/SKILL.md:11`). |
| `n3tx-build-app` | Keep for fresh apps/vertical slices. | Good sequence (`.opencode/skills/n3tx-build-app/SKILL.md:11`); remove Level 3 bias. |
| `n3tx-change-app` | Add. | Established codebases need conservative read-existing-patterns workflow (`.project/audits/opencode-skills/03-reorganization.md:82`, `.project/audits/opencode-skills/03-reorganization.md:94`). |
| `n3tx-framework-maintenance` | Keep, tighten. | Correct internals gate (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:9`). |
| `n3tx-models` | Keep, demote deep file/JSON details to cross-links. | It should own data contract/base-class/schema decisions. |
| `n3tx-storage-relationships` | Keep, reframe as relationship/persistence selection. | Current description overlaps JSON fields (`.opencode/skills/n3tx-storage-relationships/SKILL.md:3`, `.opencode/skills/n3tx-json-fields/SKILL.md:3`). |
| `n3tx-json-fields` | Keep, tighten. | Focused embedded-data boundary (`.opencode/skills/n3tx-json-fields/SKILL.md:25`). |
| `n3tx-files` | Promote to core. | First-class package and security boundary (`AGENTS.md:119`, `.opencode/skills/n3tx-files/SKILL.md:79`). |
| `n3tx-methods-routes` | Keep. | Owns model actions and route method mirrors (`.opencode/skills/n3tx-methods-routes/SKILL.md:25`). |
| `n3tx-routing-views` | Add or enrich existing skills. | Route/view grammar is cross-stack and complex (`BACKEND.md:159`, `FRONTEND.md:369`). |
| `n3tx-authorization` | Keep. | Backend-owned auth and schema exposure (`.opencode/skills/n3tx-authorization/SKILL.md:9`). |
| `n3tx-actors` | Keep. | Reusable compute/TX boundary (`.opencode/skills/n3tx-actors/SKILL.md:9`). |
| `n3tx-agents` | Keep. | Import order, tool discovery, TestModel (`.opencode/skills/n3tx-agents/SKILL.md:11`, `.opencode/skills/n3tx-agents/SKILL.md:85`). |
| `n3tx-streaming` | Keep. | Schema-declared stream contract (`.opencode/skills/n3tx-streaming/SKILL.md:9`). |
| `n3tx-networking` | Keep, narrow. | Protocol adapter owner (`.opencode/skills/n3tx-networking/SKILL.md:25`). |
| `n3tx-external-integrations` | Keep, narrow. | App/service IO placement owner (`.opencode/skills/n3tx-external-integrations/SKILL.md:11`). |
| `n3tx-ui-schema` | Keep. | Backend schema as frontend contract (`.opencode/skills/n3tx-ui-schema/SKILL.md:9`). |
| `n3tx-ui-components` | Keep. | Whole component/renderer lifecycle (`.opencode/skills/n3tx-ui-components/SKILL.md:48`). |
| `n3tx-widgets` | Keep. | Field-level rendering distinction (`.opencode/skills/n3tx-widgets/SKILL.md:47`). |
| `n3tx-theme-shell` | Add if shell/theme changes are common. | Theme/shell docs are substantial (`FRONTEND.md:107`, `FRONTEND.md:138`, `FRONTEND.md:176`). |
| `n3tx-extension-patterns` | Keep as escalation. | Decision tree is valuable (`.opencode/skills/n3tx-extension-patterns/SKILL.md:11`). |
| `n3tx-framework-boundaries` | Keep, front-load suspicious terms. | Best boundary violation table (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:13`). |
| `n3tx-skill-maintenance` | Optional add or README. | Needed for `.opencode/skills` process, linting, restart note, drift anchors (`.project/audits/opencode-skills/02-quality-extensibility.md:609`). |

### P5: Add Shared Skill Sections for Composition

Current state: most bodies contain mental models, guardrails, verification, and source-reading policy, but few contain explicit handoffs. Architecture/API audit calls body handoff quality weak (`.project/audits/opencode-skills/01-architecture-api.md:115`), and selection audit recommends `Combine With` / `Requires` sections (`.project/audits/opencode-skills/04-selection-ergonomics.md:289`).

Template:

```markdown
## Use First

Use this skill when the task mentions: `<keywords>`.

## Do Not Use For

Use another skill instead when:

| Task shape | Use |
|---|---|
| <adjacent task> | `<neighbor-skill>` |

## Combine With

Load these adjacent skills when the task crosses boundaries:

| If the task also involves | Use |
|---|---|
| auth/access/protected fields | `n3tx-authorization` |
| schema-driven UI hints | `n3tx-ui-schema` |
| custom rendered component | `n3tx-ui-components` |
| verification or failing tests | `n3tx-testing` |
| framework internals under `packages/n3tx-*` | `n3tx-framework-maintenance` |

## Verification

Verify the narrow contract first, then adjacent suites, then broad suites.

## Escalate To Source When

Follow repository context loading first:

1. Read `/workspace/docs/` and relevant package docs.
2. Read `BACKEND.md`, `FRONTEND.md`, or both by scope.
3. Inspect source only when docs/skills are insufficient or observed behavior contradicts docs.
4. If source reveals a stale contract, update or propose docs/skills changes.
```

Skill-specific composition examples:

| Skill | Add `Combine With` rules |
|---|---|
| `n3tx-agents` | `n3tx-app-bootstrap` for import order, `n3tx-actors` for tool actor shape, `n3tx-streaming` for live output, `n3tx-testing` for `TestModel` (`.opencode/skills/n3tx-agents/SKILL.md:11`, `.opencode/skills/n3tx-agents/SKILL.md:58`, `.opencode/skills/n3tx-agents/SKILL.md:85`). |
| `n3tx-files` | `n3tx-app-bootstrap` for registration, `n3tx-authorization` for authorized materialization, `n3tx-testing` for upload/download/range checks, `n3tx-external-integrations` for cloud providers (`.opencode/skills/n3tx-files/SKILL.md:50`, `.opencode/skills/n3tx-files/SKILL.md:72`). |
| `n3tx-streaming` | `n3tx-methods-routes` for `@expose_route(stream=True)`, `n3tx-ui-components` for custom stream UI, `n3tx-agents` for agent event vocabularies, `n3tx-testing` for chunk order and lifecycle (`.opencode/skills/n3tx-streaming/SKILL.md:29`, `.opencode/skills/n3tx-streaming/SKILL.md:51`). |
| `n3tx-external-integrations` | `n3tx-actors` for reusable boundaries, `n3tx-authorization` for user-specific credentials, `n3tx-files` for byte providers, `n3tx-networking` only for protocol adapters (`.opencode/skills/n3tx-external-integrations/SKILL.md:11`). |
| `n3tx-ui-components` | `n3tx-ui-schema` for renderer hints, `n3tx-widgets` for field-level needs, `n3tx-streaming` for streaming components, `n3tx-testing` for DOM/browser checks (`.opencode/skills/n3tx-ui-components/SKILL.md:24`, `.opencode/skills/n3tx-ui-components/SKILL.md:71`). |

### P6: Add Skill Linting and Drift Detection

Current state: the quality report identifies no project-local skill gate despite duplicated facts across `AGENTS.md`, `BACKEND.md`, `FRONTEND.md`, and skills (`.project/audits/opencode-skills/02-quality-extensibility.md:13`, `.project/audits/opencode-skills/02-quality-extensibility.md:315`).

Validation checks:

| Check | Rule | Evidence basis |
|---|---|---|
| Frontmatter exists | Every skill has `name`, `description`, `argument-hint`. | Current examples show this shape (`.opencode/skills/n3tx-principles/SKILL.md:1`, `.opencode/skills/n3tx-backend/SKILL.md:1`). |
| Folder/name match | `frontmatter.name == parent directory`. | OpenCode skill shape requires stable skill names; report cites this as validation basis (`.project/audits/opencode-skills/02-quality-extensibility.md:321`). |
| Trigger front-loading | First 12 words include concrete keywords for narrow skills. | Selection audit recommends high-signal tokens (`.project/audits/opencode-skills/04-selection-ergonomics.md:98`). |
| Broad role marker | Broad skills include `index` or `workflow` and delegation language. | Selection audit rule (`.project/audits/opencode-skills/04-selection-ergonomics.md:100`). |
| Narrow gating | Collision-prone narrow skills include `Use ONLY when...`. | Selection audit rule (`.project/audits/opencode-skills/04-selection-ergonomics.md:102`). |
| Negative routing | Neighboring pairs include disambiguators. | Networking/integrations overlap identified in architecture report (`.project/audits/opencode-skills/01-architecture-api.md:155`). |
| Mutable defaults | Flag `= []`, `= {}`, `Field(default=[])`, `Field(default={})` in examples. | Existing examples contain them (`.opencode/skills/n3tx-json-fields/SKILL.md:33`, `.opencode/skills/n3tx-storage-relationships/SKILL.md:97`). |
| Doc anchors | Duplicated claims include `Drift Anchors`. | Docs are authoritative (`AGENTS.md:408`). |
| Command freshness | Commands in skills appear in `AGENTS.md`/`FRONTEND.md`. | Backend and frontend commands are canonical (`AGENTS.md:571`, `FRONTEND.md:184`). |
| Package graph | Imports/examples do not violate graph. | Package graph is documented (`AGENTS.md:123`). |
| Referenced docs exist | Every referenced `docs/*.md` exists. | JSON skill references `docs/JSON_FIELDS.md` (`.opencode/skills/n3tx-json-fields/SKILL.md:12`). |
| Restart note | Skill/config edits tell maintainers to restart OpenCode. | OpenCode skill loading is config-time behavior per customization constraints for this task. |

Script sketch:

```javascript
// .opencode/scripts/lint-skills.mjs
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve('.opencode/skills');
const broad = new Set(['n3tx-backend', 'n3tx-frontend', 'n3tx-build-app']);
const narrowOnly = new Set([
  'n3tx-files',
  'n3tx-json-fields',
  'n3tx-framework-boundaries',
  'n3tx-extension-patterns',
  'n3tx-networking',
  'n3tx-ui-components',
  'n3tx-widgets',
]);

for (const dir of fs.readdirSync(root).sort()) {
  const file = path.join(root, dir, 'SKILL.md');
  if (!fs.existsSync(file)) continue;
  const text = fs.readFileSync(file, 'utf8');
  const fm = text.match(/^---\n([\s\S]*?)\n---/);
  if (!fm) throw new Error(`${dir}: missing frontmatter`);

  const name = fm[1].match(/^name:\s*(.+)$/m)?.[1]?.trim();
  const desc = fm[1].match(/^description:\s*(.+)$/m)?.[1]?.trim();
  const hint = fm[1].match(/^argument-hint:\s*(.+)$/m)?.[1]?.trim();

  if (name !== dir) throw new Error(`${dir}: name mismatch: ${name}`);
  if (!desc) throw new Error(`${dir}: missing description`);
  if (!hint) throw new Error(`${dir}: missing argument-hint`);
  if (broad.has(dir) && !/(index|workflow).test(desc)) {
    throw new Error(`${dir}: broad skill must say index or workflow`);
  }
  if (narrowOnly.has(dir) && !/Use ONLY when/.test(desc)) {
    throw new Error(`${dir}: collision-prone narrow skill needs Use ONLY when`);
  }
  if (/= \[\]|= \{\}|Field\(default=\[\]\)|Field\(default=\{\}\)/.test(text)) {
    throw new Error(`${dir}: mutable default in example`);
  }
}
```

Prompt fixture sketch:

```json
[
  {
    "prompt": "Upload a PDF and pass it to summarize()",
    "primary": "n3tx-files",
    "secondary": ["n3tx-methods-routes", "n3tx-authorization", "n3tx-testing"],
    "do_not_load": ["n3tx-backend"]
  },
  {
    "prompt": "Custom route for publish button",
    "primary": "n3tx-methods-routes",
    "secondary": ["n3tx-framework-boundaries", "n3tx-authorization"],
    "do_not_load": ["custom FastAPI route implementation"]
  }
]
```

### Proposition Priority Matrix

| Proposition | Impact | Effort | Dependencies | Quick win |
|---|---:|---:|---|---|
| P1 Router/index | Very high | Medium | None | Add new `n3tx-skill-routing` first. |
| P2 Broad index/workflow rewrite | Very high | Low | P1 preferred | Rewrite three frontmatter descriptions. |
| P3 Narrow trigger tightening | High | Medium | P1/P2 | Start with files/networking/widgets/boundaries. |
| P4 Reorganize/add missing skills | High | Medium | P1 | Add `n3tx-change-app`; promote `n3tx-files`. |
| P5 Shared composition sections | High | Medium | P1/P2 | Add to broad skills and top collision skills first. |
| P6 Lint/drift detection | High | Medium | P2/P3 definitions | Start with frontmatter/name/mutable-default checks. |

## Proposed Target Catalog

| Skill name | Type | Trigger description summary | Status | Primary companions |
|---|---|---|---|---|
| `n3tx-skill-routing` | router | Choose the right N3TX skill set for ambiguous or multi-area work. | Add | principles, testing, boundaries |
| `n3tx-principles` | reference | Architecture principles, model-first contracts, backend authority, schema frontend, actors/adapters. | Keep/rewrite | skill-routing, boundaries |
| `n3tx-build-app` | workflow | Fresh app or complete vertical slice; routing level; model/UI/auth/files/agents verification. | Keep/rewrite | app-bootstrap, models, testing |
| `n3tx-change-app` | workflow | Established-codebase changes; inspect existing models/routes/UI/tests before editing. | Add | exact mechanism skills, testing |
| `n3tx-framework-maintenance` | workflow | Framework internals under `packages/n3tx-*`, public contracts, docs/tests. | Keep/rewrite | area skill, testing |
| `n3tx-testing` | workflow | Contract verification, backend/frontend/agent/file/stream tests. | Keep/enrich | all implementation skills |
| `n3tx-backend` | index | Broad backend index only; delegates concrete mechanisms. | Keep/rewrite | models, methods, auth, storage, files |
| `n3tx-frontend` | index | Broad frontend index only; delegates schema/components/widgets/stream/theme. | Keep/rewrite | ui-schema, components, widgets, theme-shell |
| `n3tx-models` | domain | ProtoModel, ActorModel, BaseUser, fields, schema, validation, data contract. | Keep/tighten | storage, auth, ui-schema |
| `n3tx-app-bootstrap` | specialist | `create_app`, `N3TXApp`, routing Level 1/2/3, import order, static dirs. | Keep/enrich | build-app, agents, files |
| `n3tx-storage-relationships` | domain | StorableMixin, pagination, ListRef, ManyToMany, ownership, relationship identity. | Keep/tighten | models, auth, testing |
| `n3tx-json-fields` | specialist | Dict/list embedded fields, SQLite JSON TEXT, migrations, relationship boundary. | Keep/tighten | models, testing |
| `n3tx-files` | specialist | File metadata, FileStore, upload/download, range, materialization. | Keep/promote | auth, app-bootstrap, testing, integrations |
| `n3tx-methods-routes` | domain | `@expose_route`, custom actions, method schemas, route grammar, user injection. | Keep/enrich | auth, streaming, routing-views |
| `n3tx-routing-views` | specialist | Backend/frontend route and view grammar, class mirrors, nested routes, `@` boundary. | Add optional | methods, frontend, ui-schema |
| `n3tx-authorization` | domain | BaseUser, JWT, ABAC, OWNER, ROLE, Where, protected fields. | Keep/enrich | models, methods, testing |
| `n3tx-actors` | domain | ActorModel, TX, Matrix, lifecycle, reusable compute. | Keep/tighten | agents, methods, networking |
| `n3tx-agents` | domain | AgentActor, AgentMixin, tool discovery, Pydantic AI, thread context. | Keep/enrich | actors, bootstrap, streaming, testing |
| `n3tx-streaming` | specialist | `stream=True`, SSE, TX stream protocol, event schemas, NTTStream. | Keep/enrich | methods, agents, UI components |
| `n3tx-networking` | specialist | TX/Matrix/NetworkAdapter/WebSocket/MCP/ActivityPub protocol routing. | Keep/narrow | actors, streaming, auth |
| `n3tx-external-integrations` | domain | Third-party APIs, webhooks, scraping, credentials, sync jobs, FileStore providers. | Keep/narrow | actors, auth, files, agents |
| `n3tx-ui-schema` | domain | `__ui__`, field metadata, renderer hints, access adaptation, route metadata. | Keep/enrich | models, widgets, components |
| `n3tx-ui-components` | specialist | Web Components, custom renderers, lifecycle, router-mounted components. | Keep/tighten | ui-schema, widgets, streaming |
| `n3tx-widgets` | specialist | Field widgets, backend Widget types, Formidable registry, field display/input. | Keep/tighten | ui-schema, testing |
| `n3tx-theme-shell` | specialist | Theme tokens, `theme.js`, topbar/sidebar/profile, icons, shell CSS. | Add optional | frontend, components, testing |
| `n3tx-extension-patterns` | specialist | Schema/dump extensions, mixins, custom storage, widgets, adapters, auth rules. | Keep/tighten | framework-maintenance when internals |
| `n3tx-framework-boundaries` | guardrail | Bypass/workaround/custom route/direct SQL/raw fetch/duplicate contract escalation. | Keep/rewrite | exact mechanism skill |
| `n3tx-skill-maintenance` | reference/workflow | Maintain `.opencode/skills`: frontmatter, lint, drift anchors, restart constraints. | Add optional | customize-opencode |

## Skill Selection Flows

### Fresh N3TX Codebase

| Flow | Load sequence | Notes |
|---|---|---|
| Create app | `n3tx-skill-routing` -> `n3tx-principles` -> `n3tx-build-app` -> `n3tx-app-bootstrap` -> `n3tx-models` -> `n3tx-testing` | Start with lowest routing level that satisfies requirements (`AGENTS.md:535`, `AGENTS.md:540`, `AGENTS.md:543`). |
| Add model | `n3tx-principles` -> `n3tx-models` -> `n3tx-storage-relationships` if relationships -> `n3tx-ui-schema` if UI hints -> `n3tx-testing` | Model is source of truth (`.opencode/skills/n3tx-models/SKILL.md:9`). |
| Add UI | `n3tx-principles` -> `n3tx-frontend` -> `n3tx-ui-schema` -> `n3tx-ui-components` or `n3tx-widgets` -> `n3tx-testing` | Frontend adapts from schema (`.opencode/skills/n3tx-frontend/SKILL.md:9`). |
| Add auth | `n3tx-authorization` -> `n3tx-models` -> `n3tx-methods-routes` if method access -> `n3tx-testing` | Backend is authority (`.opencode/skills/n3tx-authorization/SKILL.md:9`). |
| Add storage relationship | `n3tx-storage-relationships` -> `n3tx-models` -> `n3tx-authorization` if ownership -> `n3tx-testing` | Relationship primitive selection belongs here (`.opencode/skills/n3tx-storage-relationships/SKILL.md:46`). |
| Add agent | `n3tx-agents` -> `n3tx-actors` -> `n3tx-app-bootstrap` -> `n3tx-streaming` if realtime -> `n3tx-testing` | Import order matters for mixins (`.opencode/skills/n3tx-agents/SKILL.md:11`). |
| Add external integration | `n3tx-external-integrations` -> `n3tx-actors` -> `n3tx-methods-routes` -> `n3tx-authorization` if user-specific -> `n3tx-testing` | Use networking only for protocol adapters (`.opencode/skills/n3tx-networking/SKILL.md:25`). |
| Add tests | `n3tx-testing` -> relevant mechanism skill | Verification order is narrow-first (`.opencode/skills/n3tx-testing/SKILL.md:11`). |

### Established N3TX Codebase

| Flow | Load sequence | Notes |
|---|---|---|
| Feature addition | `n3tx-skill-routing` -> `n3tx-change-app` -> exact mechanism skills -> `n3tx-testing` | Established apps need conservation and blast-radius mapping, not fresh app assembly (`.project/audits/opencode-skills/03-reorganization.md:82`). |
| Bugfix | generic `bugfix`/`tdd` if applicable -> `n3tx-principles` -> exact mechanism skill -> `n3tx-testing` | Repository bug policy requires failing test first (`AGENTS.md:185`). |
| Refactor | `n3tx-principles` -> exact area skill -> `n3tx-framework-boundaries` if bypass risk -> `n3tx-testing` | Boundary skill handles inconsistency escalation (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:54`). |
| Framework maintenance | `n3tx-framework-maintenance` -> relevant package/domain skill -> `n3tx-testing` -> docs/skill update check | Framework skill owns internals workflow (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:31`). |
| Frontend customization | `n3tx-frontend` -> `n3tx-ui-schema` or `n3tx-ui-components` or `n3tx-widgets` -> `n3tx-testing` | Runtime/visual split is documented (`FRONTEND.md:20`, `FRONTEND.md:264`). |
| Integration change | `n3tx-external-integrations` -> `n3tx-actors` -> `n3tx-authorization`/`n3tx-files` if needed -> `n3tx-testing` | External IO must be reusable boundary (`.opencode/skills/n3tx-external-integrations/SKILL.md:9`). |
| Docs update | `n3tx-principles` -> area skill -> `n3tx-framework-maintenance` if public framework docs/API | Docs updates are mandatory when behavior changes (`AGENTS.md:561`). |

### Routing Matrix

| User intent / keywords / files touched | Primary skill | Secondary skills | Avoid |
|---|---|---|---|
| `create_app`, `N3TXApp`, `main.py`, app entrypoint, static dirs | `n3tx-app-bootstrap` | `n3tx-build-app`, `n3tx-models`, `n3tx-testing` | framework-maintenance unless packages edited |
| `ProtoModel`, `ActorModel`, `BaseUser`, fields, schema output | `n3tx-models` | storage, auth, ui-schema | backend as primary for one model |
| `dict`, `list`, `list[str]`, JSON TEXT | `n3tx-json-fields` | models, testing | storage relationships as primary |
| `ListRef`, parent/child, nested routes, `ManyToMany`, pagination | `n3tx-storage-relationships` | models, auth, testing | JSON fields unless embedded data |
| upload, download, blob, attachment, `File`, `FileStore`, `/files/upload` | `n3tx-files` | bootstrap, auth, testing, integrations | backend as primary |
| `__access__`, JWT, `OWNER`, `ROLE`, `Where`, protected fields | `n3tx-authorization` | models, methods, testing | frontend as authority |
| `@expose_route`, custom action, method schema, endpoint/action | `n3tx-methods-routes` | auth, streaming, boundaries, testing | custom FastAPI route |
| route/view grammar, `#Model/@view`, `/ClassName/_`, nested identity | `n3tx-routing-views` | methods, frontend, ui-schema | networking unless transport issue |
| Actor, TX, Matrix, lifecycle, reusable compute | `n3tx-actors` | methods, agents, networking | build-app unless vertical slice |
| Agent, LLM, `AgentActor`, `__agent__`, tool discovery | `n3tx-agents` | actors, bootstrap, streaming, testing | external integrations unless outside services |
| SSE, `stream=True`, event schemas, `NTTStream`, progressive UI | `n3tx-streaming` | methods, agents, UI components, testing | networking unless adapter changing |
| WebSocket, MCP, ActivityPub, `NetworkAPI`, `NetworkAdapter` | `n3tx-networking` | actors, streaming, auth | external integrations for normal API clients |
| external API, scraper, webhook, credentials, sync job | `n3tx-external-integrations` | actors, auth, files, agents | networking unless protocol bridge |
| `__ui__`, renderer hints, `ui.icon`, access adaptation | `n3tx-ui-schema` | models, frontend, widgets, components | components if schema hints enough |
| Web Component, custom renderer, `NTTElement`, `ListElement` | `n3tx-ui-components` | ui-schema, streaming, testing | widgets unless field-level |
| field widget, Formidable, backend Widget type | `n3tx-widgets` | ui-schema, testing | components unless whole entity |
| theme tokens, `theme-base.css`, topbar/sidebar/profile/icons | `n3tx-theme-shell` | frontend, components, testing | backend unless schema changes |
| failing tests, first tests, E2E, Playwright, Vitest | `n3tx-testing` | relevant mechanism skill | framework-maintenance unless internals |
| `packages/n3tx-core`, `packages/n3tx-actors`, `packages/n3tx-ui`, `packages/n3tx-agents`, `packages/n3tx-files` | `n3tx-framework-maintenance` | area skill, testing | build-app as primary |
| bypass, workaround, custom route, direct SQL, raw fetch, duplicate schema/access | `n3tx-framework-boundaries` | exact mechanism skill | implementation before resolving boundary |
| schema/dump extension, mixin, custom storage, custom auth rule | `n3tx-extension-patterns` | framework-maintenance if internals | extension before normal mechanisms |

## Downstream Implementation Plan

### 1. Add router/index skill or enrich principles

Files to edit: add `.opencode/skills/n3tx-skill-routing/SKILL.md`; update `.opencode/skills/n3tx-principles/SKILL.md` only to point to it.

Representative snippet:

```yaml
---
name: n3tx-skill-routing
description: N3TX OpenCode skill routing: choose fresh app, established app, framework maintenance, models, auth, storage, files, routes, actors, agents, UI, streaming, integrations, testing. Use when an N3TX task is ambiguous, spans multiple areas, or needs the right n3tx-* skill set.
argument-hint: "<N3TX task or ambiguous skill-selection question>"
---
```

Tests/checks: manually run 10 selection fixtures in a fresh OpenCode session; verify ambiguous prompts choose narrow primary skills.

Risks: another skill could add catalog noise. Mitigate by keeping it selection-only and short.

### 2. Rewrite frontmatter descriptions

Files to edit: all `.opencode/skills/n3tx-*/SKILL.md`, prioritizing `n3tx-backend`, `n3tx-frontend`, `n3tx-build-app`, `n3tx-framework-boundaries`, `n3tx-files`, `n3tx-networking`, `n3tx-external-integrations`, `n3tx-ui-components`, `n3tx-widgets`, `n3tx-extension-patterns`.

Representative rewrite rule:

```text
Broad: include "index" or "workflow" and "prefer/load narrower skills".
Narrow: include concrete keywords and "Use ONLY when...".
Neighbor pairs: include negative routing clauses.
```

Tests/checks: linter enforces broad/narrow wording; prompt fixture review checks expected primary/secondary skills.

Risks: descriptions become too long. Mitigate by front-loading high-signal terms and keeping body handoff tables concise.

### 3. Add shared composition sections

Files to edit: add `Use First`, `Do Not Use For`, `Combine With`, `Verification`, and `Escalate To Source When` to broad skills and collision-prone narrow skills first.

Representative snippet:

```markdown
## Combine With

| If the task also involves | Use |
|---|---|
| auth/access/protected fields | `n3tx-authorization` |
| method/action routes | `n3tx-methods-routes` |
| UI schema hints | `n3tx-ui-schema` |
| verification | `n3tx-testing` |
```

Tests/checks: lint required sections on a subset first; do not require all sections globally until migration is complete.

Risks: duplicate tables drift. Mitigate with a central router and skill-specific small tables only.

### 4. Merge/demote duplicate content

Files to edit: `n3tx-backend`, `n3tx-models`, `n3tx-storage-relationships`, `n3tx-frontend`, `n3tx-methods-routes`, `n3tx-ui-schema`.

Action: replace deep duplicate file/JSON/route/theme content in broad skills with owner links and canonical doc anchors.

Representative snippet:

```markdown
For file uploads/downloads, load `n3tx-files`. This backend index only names the boundary; the file skill owns routes, FileStore providers, range downloads, and File-typed materialization.
```

Tests/checks: no technical owner is removed without an owner skill or canonical doc anchor.

Risks: skills become too dependent on the router. Mitigate by leaving a one-paragraph summary in broad skills.

### 5. Add missing skills

Files to add: `.opencode/skills/n3tx-change-app/SKILL.md`; optional `.opencode/skills/n3tx-routing-views/SKILL.md`; optional `.opencode/skills/n3tx-theme-shell/SKILL.md`; optional `.opencode/skills/n3tx-skill-maintenance/SKILL.md`.

Representative `n3tx-change-app` snippet:

```yaml
---
name: n3tx-change-app
description: N3TX established-codebase changes: inspect existing models, schemas, routes, UI renderers, tests, and local conventions before editing. Use when modifying an existing N3TX app or feature; combine with narrow mechanism skills for the exact surface.
argument-hint: "<existing app feature or behavior change>"
---
```

Tests/checks: prompt fixtures distinguish fresh app vs established app.

Risks: optional skills may fragment the catalog. Mitigate by adding route/theme skills only if route/theme prompt fixtures are common or failures recur.

### 6. Add lint/fixture validation

Files to add: `.opencode/scripts/lint-skills.mjs`, `.opencode/skills/selection-fixtures.json`, optional package script under `.opencode/package.json` if that file is source-controlled.

Representative checks: frontmatter, folder/name match, broad/narrow wording, mutable defaults, referenced docs, command freshness, package graph, drift anchors.

Tests/checks: run `node .opencode/scripts/lint-skills.mjs`; manually validate selection fixtures in a restarted OpenCode session.

Risks: linter too strict during migration. Mitigate with phased warnings, then errors after cleanup.

### 7. Restart OpenCode and manually validate selection

Files to edit: none.

Action: after skill/config changes, restart OpenCode so changed skills are reloaded.

Manual validation prompts:

| Prompt | Expected primary | Expected secondary |
|---|---|---|
| Add file upload to Product and pass it to transcribe. | `n3tx-files` | methods, auth, testing |
| Make Product agentic with a streaming summarize method. | `n3tx-agents` | actors, app-bootstrap, streaming, testing |
| Fix `#Product/1/@chat` route rendering. | `n3tx-routing-views` or frontend/UI schema | UI components, testing |
| Add custom endpoint for publish button. | `n3tx-methods-routes` | boundaries, auth, testing |
| Refactor direct SQL in an app feature. | `n3tx-framework-boundaries` | storage/models, testing |

Risks: selection behavior is probabilistic. Mitigate with repeated fixture runs and description tightening when wrong skills load.

## Appendix: Finding and Proposition Index

| ID | Item | Severity/status | Primary files |
|---|---|---|---|
| F1 | Broad skill collision suppresses narrow skills. | Critical | `n3tx-backend`, `n3tx-frontend`, `n3tx-build-app` |
| F2 | No explicit router/index. | Critical | new `n3tx-skill-routing`, `n3tx-principles` |
| F3 | Level 3/ActorModel default overbuild risk. | High | `n3tx-build-app`, `n3tx-models`, `n3tx-app-bootstrap` |
| F4 | `n3tx-files` under-indexed despite first-class package. | High | `n3tx-files`, router, backend/model/testing links |
| F5 | Source-reading policy duplicated and weaker than `AGENTS.md`. | High | all implementation skills |
| F6 | Route/view grammar fragmented. | High | `n3tx-methods-routes`, `n3tx-frontend`, `n3tx-ui-schema`, optional `n3tx-routing-views` |
| F7 | Theme/shell lacks trigger. | Medium/High | `n3tx-frontend`, `n3tx-ui-components`, optional `n3tx-theme-shell` |
| F8 | No skill linter/drift detector. | High | `.opencode/scripts/lint-skills.mjs`, selection fixtures |
| F9 | Mutable defaults in examples. | Medium | backend/models/storage/json skills |
| F10 | External integration secret handling too shallow. | Medium | `n3tx-external-integrations`, `n3tx-authorization` |
| P1 | Add N3TX Skill Router / Selection Index. | Recommended P0 | new `n3tx-skill-routing` |
| P2 | Convert broad skills into workflow/index skills. | Recommended P0 | backend/frontend/build-app |
| P3 | Tighten narrow skill trigger descriptions. | Recommended P0/P1 | all narrow collision-prone skills |
| P4 | Reorganize/merge/add missing skills. | Recommended P1 | files/change-app/routing/theme/maintenance |
| P5 | Add shared composition sections. | Recommended P1 | all skills over time |
| P6 | Add linting and drift detection. | Recommended P1 | scripts/fixtures/checklists |

Final position: the catalog is fundamentally sound, but it should become a routed, validated skill system. The fastest reliability win is frontmatter and router work, not rewriting all technical content. The biggest correctness win is standardizing level selection and boundary triggers. The biggest maintainability win is linting plus drift anchors.
