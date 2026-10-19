# OpenCode N3TX Skills Audit: Selection Ergonomics

Audit target: `/workspace/.opencode/skills/`.

Audit mode: focused read-only audit of skill selection behavior. Source files were not modified.

## Executive Summary

The current N3TX skill catalog has strong technical content, but its selection API is under-designed. OpenCode primarily chooses skills from the frontmatter `description`; the current descriptions often state broad domains instead of routing precedence. This creates avoidable failures when a user gives an ambiguous task such as "add uploads", "make this model agentic", "fix a route", "build dashboard UI", or "call this API from an agent".

The highest-leverage fix is not more skill prose. It is a compact routing layer plus rewritten descriptions that classify each skill as one of four roles: principles, workflow, broad index, or narrow mechanism. `n3tx-principles` already says to use it first for N3TX application work (`.opencode/skills/n3tx-principles/SKILL.md:9`) and already contains default mechanism choices (`.opencode/skills/n3tx-principles/SKILL.md:57`). It is the natural place for a shared selection preamble or routing index.

The strongest current collision is broad skills suppressing narrow skills. `n3tx-backend` covers models, storage, auth, routes, actors, agents, ManyToMany, files, bootstrap, integrations, and verification in one description (`.opencode/skills/n3tx-backend/SKILL.md:3`). `n3tx-build-app` covers creating apps, routing, models, UI, agents, storage, auth, ManyToMany, files, and verification (`.opencode/skills/n3tx-build-app/SKILL.md:3`). `n3tx-frontend` similarly covers schema UI, components, routes, forms, widgets, transport, streaming, and verification (`.opencode/skills/n3tx-frontend/SKILL.md:3`). These are useful index/workflow skills, but they need explicit "then load narrower skills" language.

The best narrow descriptions already show the target shape: `n3tx-json-fields` front-loads `dict/list`, SQLite TEXT, schema/storage detection, migrations, and relationship boundaries (`.opencode/skills/n3tx-json-fields/SKILL.md:3`); `n3tx-streaming` front-loads SSE, TX stream protocol, `@expose_route(stream=True)`, event schemas, `NTTStream`, and `NTTStreamAgent` (`.opencode/skills/n3tx-streaming/SKILL.md:3`); `n3tx-files` front-loads `File`, `FileStore`, upload/download, addresses, and materialization (`.opencode/skills/n3tx-files/SKILL.md:3`). Extend this pattern across every narrow skill and add `Use ONLY when...` where collisions are likely.

## Selection Failure Modes

| Failure mode | Current cause | Example impact | Evidence | Fix |
|---|---|---|---|---|
| Wrong broad skill chosen | Broad descriptions include too many trigger nouns. | "Add file upload" loads `n3tx-backend` or `n3tx-build-app` but misses `n3tx-files`. | `n3tx-backend` includes `n3tx-files` in its broad description (`.opencode/skills/n3tx-backend/SKILL.md:3`), while file-specific contracts live in `n3tx-files` routes/materialization (`.opencode/skills/n3tx-files/SKILL.md:30`, `.opencode/skills/n3tx-files/SKILL.md:50`). | Mark broad skills as indexes and delegate on concrete nouns. |
| Too many skills loaded | Descriptions overlap without precedence. | Agent loads backend, build-app, models, storage, auth, bootstrap, testing for a one-field model change. | `n3tx-models` includes JSON fields, `ListRef`, `ManyToMany`, files, UI metadata, and validation (`.opencode/skills/n3tx-models/SKILL.md:3`); `n3tx-storage-relationships` overlaps storage, JSON fields, pagination, relationships, nested routes, and ownership (`.opencode/skills/n3tx-storage-relationships/SKILL.md:3`). | Add a routing rule: one workflow skill plus one to three narrow mechanism skills. |
| Missing prerequisite skill | Narrow skills do not say what must be loaded first. | `__agent__ = True` model added without import-order/bootstrap awareness. | `n3tx-agents` warns to import `n3tx_agents` before `__agent__` model definitions (`.opencode/skills/n3tx-agents/SKILL.md:11`); `n3tx-app-bootstrap` centralizes package import order (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:9`). | Add "Requires/Combine With" sections. |
| Broad skill suppresses narrow skill | Broad skill bodies contain enough local guidance to appear sufficient. | Backend file guidance gets used without full FileStore/range/materialization checks. | `n3tx-backend` summarizes file routes and materialization (`.opencode/skills/n3tx-backend/SKILL.md:79`), but `n3tx-files` contains the complete file boundary and verification (`.opencode/skills/n3tx-files/SKILL.md:72`, `.opencode/skills/n3tx-files/SKILL.md:88`). | Broad skills should name narrow owners, not duplicate full contracts. |
| Source-reading confusion | Repeated source-reading blocks are shorter than the repo policy. | Agent reads source before docs/package docs when a skill is loaded standalone. | Skills repeat "inspect source only when docs insufficient" (`.opencode/skills/n3tx-backend/SKILL.md:121`, `.opencode/skills/n3tx-frontend/SKILL.md:81`), while `AGENTS.md` mandates docs-first, domain context, then source (`AGENTS.md:74`, `AGENTS.md:95`, `AGENTS.md:101`). | Replace repeated source blocks with a shared context-loading preamble. |
| Boundary skill loaded too late | Anti-pattern triggers are buried in body rather than description keywords. | User asks for "custom endpoint" and agent loads backend, not boundaries/methods. | `n3tx-framework-boundaries` lists custom FastAPI routes, direct SQL, raw fetch, and duplicated auth as avoid cases (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:13`), but the description is generic (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:3`). | Front-load bypass keywords in description. |
| Test skill loaded only at the end | Implementation skills have local verification snippets, so selection may skip `n3tx-testing`. | Feature lands with one command but not the right contract-specific checks. | `n3tx-testing` has the intended verification order (`.opencode/skills/n3tx-testing/SKILL.md:11`), but build-app/backend have their own short verification sections (`.opencode/skills/n3tx-build-app/SKILL.md:111`, `.opencode/skills/n3tx-backend/SKILL.md:111`). | Treat `n3tx-testing` as mandatory secondary for bugfix, feature, and first-test workflows. |

## Fresh Codebase Workflows

Fresh work should optimize for N3TX's "zero to working, then customize" principle (`AGENTS.md:62`) and model-first data flow (`AGENTS.md:58`, `AGENTS.md:60`, `AGENTS.md:250`). The selection sequence should minimize machinery first, then add mechanisms only when the requirement names them.

| User intent | Load sequence | Why | Do not load initially |
|---|---|---|---|
| "Create a new N3TX app" | `n3tx-principles` -> `n3tx-build-app` -> `n3tx-app-bootstrap` -> `n3tx-models` -> `n3tx-testing` | Principles set model-first boundaries; build-app supplies vertical sequence (`.opencode/skills/n3tx-build-app/SKILL.md:11`); bootstrap owns `create_app`/imports (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:23`); models own schema contracts. | `n3tx-framework-maintenance`, `n3tx-extension-patterns`, `n3tx-networking` unless requirements demand them. |
| "Add the first model" | `n3tx-principles` -> `n3tx-models` -> `n3tx-storage-relationships` if relationships -> `n3tx-ui-schema` if UI hints -> `n3tx-testing` | Model is source of truth (`.opencode/skills/n3tx-models/SKILL.md:9`); relationship primitive selection belongs to storage (`.opencode/skills/n3tx-storage-relationships/SKILL.md:46`). | `n3tx-backend` if the task is only model fields; `n3tx-framework-maintenance`. |
| "Add JSON config/settings field" | `n3tx-json-fields` -> `n3tx-models` -> `n3tx-testing` | JSON skill has the exact dict/list persistence contract (`.opencode/skills/n3tx-json-fields/SKILL.md:9`, `.opencode/skills/n3tx-json-fields/SKILL.md:25`). | `n3tx-storage-relationships` unless the user is choosing between embedded data and resources. |
| "Add first UI" | `n3tx-principles` -> `n3tx-frontend` -> `n3tx-ui-schema` -> `n3tx-ui-components` or `n3tx-widgets` -> `n3tx-testing` | Frontend adapts from schema (`.opencode/skills/n3tx-frontend/SKILL.md:9`); `__ui__` is backend-owned UI contract (`.opencode/skills/n3tx-ui-schema/SKILL.md:11`). | `n3tx-backend` unless backend schema changes are needed; `n3tx-extension-patterns` until schema/widgets/components fail. |
| "Add field widget" | `n3tx-widgets` -> `n3tx-ui-schema` -> `n3tx-testing` | Widgets customize field rendering while preserving schema (`.opencode/skills/n3tx-widgets/SKILL.md:9`); widget-vs-component distinction is explicit (`.opencode/skills/n3tx-widgets/SKILL.md:47`). | `n3tx-ui-components` unless whole-entity layout is changing. |
| "Add external API integration" | `n3tx-external-integrations` -> `n3tx-actors` -> `n3tx-methods-routes` -> `n3tx-authorization` if user-specific -> `n3tx-testing` | External IO must be wrapped in reusable boundary (`.opencode/skills/n3tx-external-integrations/SKILL.md:9`); actor tool shape is canonical (`.opencode/skills/n3tx-external-integrations/SKILL.md:11`). | `n3tx-networking` unless a protocol adapter such as MCP/WebSocket/ActivityPub is required. |
| "Add agent capability" | `n3tx-agents` -> `n3tx-actors` -> `n3tx-app-bootstrap` -> `n3tx-streaming` if realtime -> `n3tx-testing` | Agents are actors and tools are `@expose_route` methods (`.opencode/skills/n3tx-agents/SKILL.md:9`); import order is critical (`.opencode/skills/n3tx-agents/SKILL.md:11`). | `n3tx-networking` unless protocol clients are involved. |
| "Write first tests" | `n3tx-testing` -> relevant mechanism skill | Test skill owns verification order (`.opencode/skills/n3tx-testing/SKILL.md:11`) and current backend/frontend contract checks (`.opencode/skills/n3tx-testing/SKILL.md:18`, `.opencode/skills/n3tx-testing/SKILL.md:37`). | `n3tx-framework-maintenance` unless testing framework internals. |

Fresh codebase routing note: `n3tx-build-app` currently recommends `ActorModel` and Level 3 for "new serious N3TX apps" (`.opencode/skills/n3tx-build-app/SKILL.md:32`), but the main guide presents Level 1, Level 2, and Level 3 as separate choices and says all produce identical API endpoints and responses (`AGENTS.md:215`, `AGENTS.md:231`, `AGENTS.md:535`). Selection guidance should therefore say: load `n3tx-app-bootstrap` for routing-level choice and choose the lowest level that satisfies the requirement.

## Established Codebase Workflows

Established work should optimize for preserving existing contracts, avoiding boundary violations, and choosing the smallest relevant mechanism skill.

| User intent | Load sequence | Why | Do not load initially |
|---|---|---|---|
| Bugfix in app behavior | Generic `bugfix` or `tdd` workflow if available -> `n3tx-principles` -> relevant narrow skill -> `n3tx-testing` | Repository bug policy requires failing test first (`AGENTS.md:185`); N3TX tests should verify contract boundaries (`.opencode/skills/n3tx-testing/SKILL.md:11`). | `n3tx-framework-maintenance` unless framework package files are touched. |
| Feature addition | `n3tx-principles` -> one workflow skill (`n3tx-build-app` for vertical slice or area skill for local change) -> narrow skills -> `n3tx-testing` | Build-app is appropriate only for complete app/features (`.opencode/skills/n3tx-build-app/SKILL.md:9`), not every localized edit. | Broad backend/frontend if a narrower mechanism skill is enough. |
| Refactor app code | `n3tx-principles` -> relevant area skill -> `n3tx-framework-boundaries` if any bypass/workaround is involved -> `n3tx-testing` | Boundaries skill is for designs that might bypass schemas, actors, routes, transport, auth, or reusable capabilities (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:3`). | `n3tx-extension-patterns` unless an extension point is truly needed. |
| Framework maintenance | `n3tx-framework-maintenance` -> relevant package skill -> `n3tx-testing` -> docs/skill update check | Maintenance skill is explicitly only for N3TX internals (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:9`) and owns docs/tests workflow (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:31`). | `n3tx-build-app` unless validating with an example app. |
| Docs update | `n3tx-principles` -> area skill whose contract is documented -> `n3tx-framework-maintenance` if framework docs/public APIs | Docs are authoritative in the repo (`AGENTS.md:80`, `AGENTS.md:408`); behavior changes require docs updates (`AGENTS.md:561`). | Implementation-only skills if no behavior contract is changing. |
| Fix frontend component/rendering | `n3tx-frontend` -> `n3tx-ui-schema` or `n3tx-ui-components` or `n3tx-widgets` -> `n3tx-testing` | Frontend splits into runtime vs visual packages (`FRONTEND.md:20`, `FRONTEND.md:264`); component skill owns lifecycle and renderer mounting (`.opencode/skills/n3tx-ui-components/SKILL.md:48`, `.opencode/skills/n3tx-ui-components/SKILL.md:55`). | `n3tx-backend` unless schema hints must change. |
| Fix route/view issue | `n3tx-methods-routes` for backend method/data routes -> `n3tx-frontend` or `n3tx-ui-schema` for hash/view routes -> `n3tx-framework-boundaries` if adding custom routes | Backend route grammar is summarized in methods skill (`.opencode/skills/n3tx-methods-routes/SKILL.md:51`); frontend hash grammar is deeper in docs (`FRONTEND.md:369`). | `n3tx-networking` unless Level 3 adapter routing is the issue. |
| Add integration to existing agent | `n3tx-external-integrations` -> `n3tx-agents` -> `n3tx-actors` -> `n3tx-testing` | External APIs used by agents must be wrapped in tool actors/adapters (`.opencode/skills/n3tx-agents/SKILL.md:101`); integration boundaries are explicit (`.opencode/skills/n3tx-external-integrations/SKILL.md:11`). | `n3tx-networking` unless protocol translation is required. |

## Proposed Routing Matrix

| User says / files touched | Primary skill | Secondary skills | Do not load |
|---|---|---|---|
| `create_app`, `N3TXApp`, `main.py`, app entrypoint, static dirs, routing level, package imports | `n3tx-app-bootstrap` | `n3tx-build-app`, `n3tx-models`, `n3tx-testing` | `n3tx-framework-maintenance` unless framework packages are edited |
| New complete app or full vertical feature | `n3tx-build-app` | `n3tx-app-bootstrap`, `n3tx-models`, `n3tx-ui-schema`, `n3tx-testing` | `n3tx-extension-patterns` until normal customization fails |
| `ProtoModel`, `ActorModel`, `BaseUser`, fields, Pydantic validation, schema output | `n3tx-models` | `n3tx-storage-relationships`, `n3tx-json-fields`, `n3tx-authorization`, `n3tx-ui-schema` | `n3tx-backend` if the task is only a model contract |
| `dict`, `list`, `list[str]`, JSON TEXT, settings/config/payloads | `n3tx-json-fields` | `n3tx-models`, `n3tx-testing` | `n3tx-storage-relationships` unless deciding relationship vs embedded data |
| `ListRef`, parent/child, nested routes, `ManyToMany`, pagination, owner FK | `n3tx-storage-relationships` | `n3tx-models`, `n3tx-authorization`, `n3tx-testing` | `n3tx-json-fields` unless embedded dict/list fields exist |
| Upload, download, blob, attachment, `File`, `FileStore`, `/files/upload`, `/File/{id}` | `n3tx-files` | `n3tx-app-bootstrap`, `n3tx-authorization`, `n3tx-testing`, `n3tx-external-integrations` for cloud providers | `n3tx-backend` as primary |
| `__access__`, JWT, `OWNER`, `ROLE`, `Where`, protected fields, login/register | `n3tx-authorization` | `n3tx-models`, `n3tx-methods-routes`, `n3tx-testing` | `n3tx-frontend` as authority for access |
| `@expose_route`, custom action, method schema, user injection, endpoint/action | `n3tx-methods-routes` | `n3tx-authorization`, `n3tx-streaming`, `n3tx-framework-boundaries`, `n3tx-testing` | Custom FastAPI route patterns |
| SSE, `stream=True`, event schemas, chunks, `NTTStream`, `ntx-chat`, progressive UI | `n3tx-streaming` | `n3tx-methods-routes`, `n3tx-agents`, `n3tx-ui-components`, `n3tx-testing` | `n3tx-networking` unless transport adapter is changing |
| Actor, TX, Matrix, reusable compute, lifecycle, tool actor | `n3tx-actors` | `n3tx-methods-routes`, `n3tx-agents`, `n3tx-networking` | `n3tx-build-app` unless building a vertical slice |
| Agent, LLM, `AgentActor`, `__agent__`, tool discovery, Pydantic AI, TestModel | `n3tx-agents` | `n3tx-actors`, `n3tx-app-bootstrap`, `n3tx-streaming`, `n3tx-testing` | `n3tx-external-integrations` unless calling external services |
| WebSocket, MCP, ActivityPub, `NetworkAPI`, `NetworkAdapter`, protocol bridge | `n3tx-networking` | `n3tx-actors`, `n3tx-streaming`, `n3tx-authorization` | `n3tx-external-integrations` for ordinary API clients |
| External API, scraper, webhook, credentials, sync job, cloud file provider | `n3tx-external-integrations` | `n3tx-actors`, `n3tx-authorization`, `n3tx-files`, `n3tx-agents` | `n3tx-networking` unless building protocol translation |
| `__ui__`, field order, groups, renderer hints, `ui.icon`, access adaptation | `n3tx-ui-schema` | `n3tx-models`, `n3tx-frontend`, `n3tx-widgets`, `n3tx-ui-components` | `n3tx-ui-components` if schema hints suffice |
| Web Component, custom renderer, `NTTElement`, `ListElement`, router-mounted attrs | `n3tx-ui-components` | `n3tx-ui-schema`, `n3tx-streaming`, `n3tx-testing` | `n3tx-widgets` unless field-level only |
| Field widget, Formidable input/display, backend Widget type | `n3tx-widgets` | `n3tx-ui-schema`, `n3tx-testing` | `n3tx-ui-components` unless whole entity/collection layout changes |
| Failing tests, first tests, verification, E2E, Playwright, Vitest | `n3tx-testing` | relevant mechanism skill | `n3tx-framework-maintenance` unless framework internals |
| `packages/n3tx-core`, `packages/n3tx-actors`, `packages/n3tx-ui`, `packages/n3tx-agents`, framework docs/tests | `n3tx-framework-maintenance` | relevant area skill, `n3tx-testing` | `n3tx-build-app` as primary |
| bypass, workaround, custom route, direct SQL, raw fetch, duplicate schema/access | `n3tx-framework-boundaries` | relevant mechanism skill | Proceeding with implementation before resolving boundary |
| schema/dump extension, mixin, custom storage, custom auth rule, extension point | `n3tx-extension-patterns` | `n3tx-framework-maintenance` if framework internals, relevant area skill | Use before checking normal model/UI/actor mechanisms |

## Description Rewrite Patterns

OpenCode selection improves when descriptions start with concrete trigger terms, not abstract domain labels. The current narrow skills mostly start with broad category names; rewrite them to put filenames/classes/decorators/routes first.

| Current pattern | Better pattern | Why |
|---|---|---|
| `Broad N3TX backend application development...` | `N3TX backend index: ProtoModel, ActorModel, storage, routes, auth, files, agents. Use when backend scope spans multiple mechanisms; prefer narrower skills for concrete ListRef/FileStore/@expose_route/__access__ work.` | Identifies broad skill as index and prevents suppression. |
| `N3TX Web Components... Use when creating or changing N3TX UI components.` | `N3TX custom Web Components and renderers: Component, NTTElement, ListElement, router attrs, prerender/render lifecycle. Use ONLY when creating/changing whole entity, collection, route-mounted, or streaming components.` | Front-loads mechanisms and narrows away widget/schema tasks. |
| `N3TX extension patterns... Use when normal model/UI/actor customization is not enough.` | `N3TX extension points: schema_extension, dump_extension, register_mixin, custom storage, Widget, NetworkAdapter, AccessRule. Use ONLY after __ui__, widgets, @expose_route, actors, or app-level config cannot express the need.` | Adds concrete extension terms and protects against premature extension. |
| `N3TX framework boundary guardrails and anti-patterns...` | `N3TX boundary violation guardrails: custom FastAPI route, direct SQL, raw fetch, duplicate schema/access, JSON relationship arrays, blobs in SQLite/static assets, internal HTTP. Use when a design may bypass N3TX contracts.` | Makes anti-pattern words selectable. |
| `N3TX networking through TX... internal/external network flows.` | `N3TX protocol routing: TX, Matrix, NetworkAPI, NetworkAdapter, WebSocket, MCP, ActivityPub. Use ONLY for internal actor routing or external protocol bridges; use n3tx-external-integrations for ordinary third-party API clients.` | Splits protocol adapters from app API clients. |

Rules for rewriting:

1. Start the description with 3 to 8 high-signal tokens: class names, decorators, routes, package names, file paths, or user-visible nouns.
2. Broad skills must say `index` or `workflow` and include "prefer/load narrower skills for...".
3. Narrow skills should say `Use ONLY when...` when adjacent skills contain the same trigger nouns.
4. Include negative routing when a neighboring skill is commonly confused, for example "not ordinary third-party API clients" for networking.
5. Put prerequisite cues in the description when the prerequisite is easy to miss, for example `n3tx_agents import order`, `n3tx_files materialization`, or `create_app/N3TXApp bootstrap`.

## Shared Preamble Or Routing Index Pattern

The catalog should avoid duplicating the same source-reading and routing policy in every skill. A compact shared preamble can preserve self-containment while reducing drift.

Recommended placement: add to `n3tx-principles` or a new `.opencode/skills/README.md`. If OpenCode does not load READMEs as skills, add a dedicated `n3tx-skill-routing` skill. Existing audits already proposed this direction (`.project/audits/opencode-skills/01-architecture-api.md:175`, `.project/audits/opencode-skills/02-quality-extensibility.md:435`).

Recommended shared preamble:

```markdown
## N3TX Skill Routing Preamble

For ambiguous N3TX implementation tasks:

1. Load `n3tx-principles` first for architecture and boundary defaults.
2. Load exactly one workflow/index skill when useful: `n3tx-build-app`, `n3tx-backend`, `n3tx-frontend`, or `n3tx-framework-maintenance`.
3. Load narrow mechanism skills for concrete nouns: `ListRef`, `FileStore`, `@expose_route`, `__access__`, `NTTStream`, `Widget`, `NetworkAdapter`, `AgentActor`.
4. Load `n3tx-testing` for bugfixes, features, new apps, first tests, or any behavior change.
5. If the task mentions bypass/workaround/custom route/direct SQL/raw fetch/duplicate contract, load `n3tx-framework-boundaries` before editing.

Context loading for implementation tasks:

1. Read `/workspace/docs/` and relevant package docs.
2. Read `BACKEND.md`, `FRONTEND.md`, or both by scope.
3. Inspect source only after docs/skills are insufficient or behavior contradicts docs.
```

This aligns with repository context-loading rules (`AGENTS.md:74`, `AGENTS.md:95`, `AGENTS.md:101`) and with the existing principle skill's source-reading policy (`.opencode/skills/n3tx-principles/SKILL.md:53`).

## Concrete Before/After Examples

### `n3tx-backend`

Before:

```yaml
description: Broad N3TX backend application development. Use for models, storage, auth, routes, actors, agents, ManyToMany relationships, n3tx-files, app bootstrap, external integrations, and backend verification without framework source lookup.
```

After:

```yaml
description: N3TX backend index: ProtoModel, ActorModel, storage, routes, auth, actors, agents, files, integrations. Use when a backend task spans multiple mechanisms; prefer narrower skills for concrete ListRef, dict/list JSON, FileStore, @expose_route, __access__, AgentActor, or create_app work.
```

### `n3tx-app-bootstrap`

Before:

```yaml
description: N3TX application bootstrap with create_app, N3TXApp, routing levels, package imports, static files, storage, ManyToMany relationship generation, n3tx-files, and model registration. Use when creating or wiring an N3TX app entrypoint.
```

After:

```yaml
description: N3TX app entrypoints: create_app, N3TXApp, Level 1/2/3 routing, import order for n3tx_ui/n3tx_agents/n3tx_files, static dirs, model registration. Use ONLY when creating or wiring app bootstrap/main.py, not for ordinary model fields.
```

### `n3tx-framework-boundaries`

Before:

```yaml
description: N3TX framework boundary guardrails and anti-patterns. Use when a design might bypass schemas, actors, generated routes, N3TX transport, authorization, or reusable actor capabilities.
```

After:

```yaml
description: N3TX boundary violations: custom FastAPI routes, direct SQL, raw fetch, duplicated schema/access, JSON relationship arrays, blobs in SQLite/static assets, internal HTTP, ad-hoc LLM tools. Use when a design might bypass N3TX contracts.
```

### `n3tx-ui-components`

Before:

```yaml
description: N3TX Web Components, custom renderers, Component/NTTElement/ListElement lifecycle, router-mounted components, and frontend customization. Use when creating or changing N3TX UI components.
```

After:

```yaml
description: N3TX custom Web Components and renderers: Component, NTTElement, ListElement, NTTStream, router attrs, prerender/render lifecycle. Use ONLY when changing whole entity, collection, route-mounted, or streaming UI components; use n3tx-widgets for field inputs.
```

### `n3tx-external-integrations`

Before:

```yaml
description: N3TX external API and service integration patterns. Use when calling third-party APIs, scraping, webhooks, protocol bridges, credentials, sync jobs, or making capabilities available to agents/UI.
```

After:

```yaml
description: N3TX third-party service integrations: API clients, scrapers, webhooks, credentials, sync jobs, FileStore providers, agent/UI tools. Use when app code calls outside services; use n3tx-networking only for protocol adapters like MCP/WebSocket/ActivityPub.
```

## Task-To-Skill Flow Examples

| Ambiguous user task | Current likely selection | Better selection flow |
|---|---|---|
| "Add uploads to grants" | `n3tx-backend`, maybe `n3tx-build-app` | `n3tx-files` -> `n3tx-app-bootstrap` -> `n3tx-authorization` -> `n3tx-testing` |
| "Make products searchable by an LLM" | `n3tx-agents`, maybe `n3tx-backend` | `n3tx-agents` -> `n3tx-actors` for tool boundary -> `n3tx-methods-routes` for exposed search action -> `n3tx-testing` |
| "Add a custom endpoint to publish" | `n3tx-backend` | `n3tx-methods-routes` -> `n3tx-authorization` -> `n3tx-framework-boundaries` if user insists on custom FastAPI -> `n3tx-testing` |
| "Show price as currency" | `n3tx-frontend` | `n3tx-widgets` -> `n3tx-ui-schema` -> `n3tx-testing` |
| "New dashboard cards" | `n3tx-frontend` | `n3tx-ui-schema` first for renderer hints -> `n3tx-ui-components` only if whole-card component needed -> `n3tx-testing` |
| "Call GitHub from an agent" | `n3tx-agents` or `n3tx-networking` | `n3tx-external-integrations` -> `n3tx-actors` -> `n3tx-agents` -> `n3tx-testing` |
| "Fix route #Product/1/@chat" | `n3tx-frontend` | `n3tx-frontend` -> `n3tx-ui-schema` -> `n3tx-ui-components`; use `n3tx-methods-routes` only if backend route/method mirror changes |
| "Refactor direct SQL" | `n3tx-backend` | `n3tx-framework-boundaries` -> `n3tx-storage-relationships` or `n3tx-models` -> `n3tx-testing` |

## Validation Strategy

Selection changes should be tested like an API. A practical validation stack has four layers.

### Manual Scenario Suite

Create 30 to 50 short user prompts and record expected skills. Include fresh and established codebase cases.

Example fixtures:

| Prompt | Expected primary | Expected secondary | Must not load |
|---|---|---|---|
| "Create a simple product catalog app" | `n3tx-build-app` | `n3tx-app-bootstrap`, `n3tx-models`, `n3tx-testing` | `n3tx-framework-maintenance` |
| "Add `metadata: dict` to Product and persist it" | `n3tx-json-fields` | `n3tx-models`, `n3tx-testing` | `n3tx-storage-relationships` as primary |
| "Add comments to products" | `n3tx-storage-relationships` | `n3tx-models`, `n3tx-testing` | `n3tx-json-fields` |
| "Upload a PDF and pass it to summarize()" | `n3tx-files` | `n3tx-methods-routes`, `n3tx-authorization`, `n3tx-testing` | `n3tx-backend` as primary |
| "Add a GitHub webhook receiver" | `n3tx-external-integrations` | `n3tx-actors`, `n3tx-methods-routes`, maybe `n3tx-networking` if protocol semantics matter | `n3tx-frontend` |
| "Custom route for publish button" | `n3tx-methods-routes` | `n3tx-framework-boundaries`, `n3tx-authorization` | raw custom route implementation |
| "Fix packages/n3tx-core schema pipeline" | `n3tx-framework-maintenance` | `n3tx-models`, `n3tx-testing` | `n3tx-build-app` |

### Frontmatter Lint Checks

Add a skill lint rule that enforces:

1. Frontmatter has `name`, `description`, and `argument-hint`.
2. `name` matches the parent directory.
3. Description first 12 words include at least one high-signal token for narrow skills.
4. Broad skills include `index` or `workflow` and "prefer/load narrower" language.
5. Narrow collision-prone skills include `Use ONLY when`.
6. Descriptions for neighboring pairs include disambiguators: networking vs external integrations, widgets vs components, UI schema vs frontend, JSON fields vs relationships, app bootstrap vs build app.

This extends the linter direction proposed in the quality audit (`.project/audits/opencode-skills/02-quality-extensibility.md:315`).

### Selection Fixture Checks

Maintain a JSON or YAML fixture file such as `.opencode/skills/selection-fixtures.json`:

```json
[
  {
    "prompt": "Add file upload to Product and pass it to transcribe",
    "primary": "n3tx-files",
    "secondary": ["n3tx-methods-routes", "n3tx-authorization", "n3tx-testing"],
    "do_not_load": ["n3tx-framework-maintenance"]
  }
]
```

Run it manually during skill updates: present each prompt to a fresh OpenCode session and record selected skills. Because skill edits may not affect already-loaded sessions, validation should restart or use fresh sessions after frontmatter changes.

### Drift Checks

Add drift anchors for duplicated facts. The most important anchors are:

| Duplicated fact | Anchor |
|---|---|
| Docs-first context loading | `AGENTS.md:74`, `AGENTS.md:95`, `AGENTS.md:101` |
| Model/schema/UI contract | `AGENTS.md:58`, `AGENTS.md:60`, `AGENTS.md:290`, `FRONTEND.md:288` |
| Three routing levels | `AGENTS.md:215`, `AGENTS.md:231`, `AGENTS.md:535` |
| Backend route grammar | `BACKEND.md:159` |
| Frontend route grammar | `FRONTEND.md:369` |
| Frontend verification lanes | `FRONTEND.md:184` |
| Backend test runner | `AGENTS.md:571` |
| File package contract | `AGENTS.md:369`, `.opencode/skills/n3tx-files/SKILL.md:9` |

## Top Selection Improvements

1. Add a routing preamble/index and make `n3tx-principles` or a new `n3tx-skill-routing` the first-stop selector for ambiguous N3TX work.
2. Rewrite broad descriptions to say `index` or `workflow`, then explicitly delegate to narrow mechanism skills.
3. Add `Use ONLY when...` and negative routing clauses to collision-prone narrow skills: `n3tx-framework-maintenance`, `n3tx-extension-patterns`, `n3tx-networking`, `n3tx-ui-components`, `n3tx-widgets`, `n3tx-json-fields`, `n3tx-files`, and `n3tx-framework-boundaries`.
4. Add `Combine With` / `Requires` sections so prerequisites are not missed: agents require app-bootstrap import order, files require bootstrap/authorization/testing, streaming requires methods-routes/UI/testing, external integrations require actors/auth/testing.
5. Validate selection with prompt fixtures and lint checks, not subjective review alone.

## Final Recommendation

Treat `.opencode/skills/` as an agent-facing router, not only as documentation. Preserve the current concise skill bodies, but move selection intelligence into descriptions, a compact routing index, and validation fixtures. This will make agents more reliable on both fresh N3TX apps and established codebases without requiring them to load every skill or inspect framework source prematurely.
