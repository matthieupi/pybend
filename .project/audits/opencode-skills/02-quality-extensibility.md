# OpenCode Skills Audit: Quality, Extensibility, Resilience

Audit target: `/workspace/.opencode/skills/`.

Audit mode: quick deep audit, read-only except this report.

## Executive Findings

| Rank | Finding | Evidence | Risk | Proposal |
|---|---|---|---|---|
| P0 | Skill selection is useful but too collision-prone: broad skills overlap heavily and descriptions do not consistently front-load trigger keywords or narrow routing rules. | `n3tx-backend` covers models, storage, auth, routes, actors, agents, ManyToMany, files, app bootstrap, integrations, and verification in one trigger surface (`.opencode/skills/n3tx-backend/SKILL.md:3`); `n3tx-build-app` also covers routing, models, UI, agents, storage, auth, ManyToMany, files, and verification (`.opencode/skills/n3tx-build-app/SKILL.md:3`); `n3tx-principles` says to use itself first for any N3TX application work (`.opencode/skills/n3tx-principles/SKILL.md:9`). | Agents can load a broad skill and miss the sharper skill that contains the precise guardrail, especially under ambiguous tasks like "add upload", "make app agentic", or "wire dashboard". | Add a routing matrix skill/index, tighten descriptions with concrete keywords, and mark narrow skills with `Use ONLY when...` where appropriate. |
| P0 | Default architecture guidance drifts toward `ActorModel`/Level 3 in some skills, while the main guide presents Level 1/2/3 as separate choices with identical endpoint/response behavior. | `n3tx-build-app` recommends new serious apps use `ActorModel` and Level 3 unless simpler is justified (`.opencode/skills/n3tx-build-app/SKILL.md:32`); `n3tx-models` says new app entities should default to `ActorModel` if apps may use agents/workflows/routing/reuse (`.opencode/skills/n3tx-models/SKILL.md:20`); `AGENTS.md` presents Level 1, Level 2, and Level 3 and says all three levels produce identical API endpoints and responses (`AGENTS.md:215`, `AGENTS.md:231`); `n3tx-app-bootstrap` says use Level 3 when actor/network/agent integration matters (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:41`). | Agents may over-build simple apps with Level 3 actor routing, increasing moving parts and hiding the "zero to working" path. | Standardize defaulting language: "start Level 1 for pure CRUD, choose `ActorModel`/Level 2 for reusable actor capabilities, choose Level 3 only when network/agent/protocol routing matters." |
| P0 | There is no project-local skill quality gate, linter, or drift detector despite a large skill catalog that duplicates authoritative facts from AGENTS/BACKEND/FRONTEND. | `.agents/skills/README.md` requires skill frontmatter `name:` to match the immediate parent directory (`.agents/skills/README.md:61`); the project catalog uses required `name` and `description` frontmatter in every required file, for example `n3tx-principles` (`.opencode/skills/n3tx-principles/SKILL.md:1`); docs are explicitly authoritative and skills should be updated when source inspection reveals missing contracts (`.opencode/skills/n3tx-principles/SKILL.md:55`); AGENTS requires docs and skills be updated after behavior changes (`AGENTS.md:561`). | Skill drift becomes invisible until agents make wrong implementation choices. | Add a `skills-lint` script/checklist that validates frontmatter, folder/name match, trigger terms, cited docs, package-boundary claims, command freshness, and duplicate/conflicting guidance. |
| P1 | Coverage is broad but uneven: core/model/backend/frontend/actors/agents/auth/storage/routes/streaming/networking/widgets/testing/extensions/integrations/bootstrap are covered, while files are present but omitted from the user's core list, and several newer framework surfaces are only shallowly captured. | Full catalog includes `n3tx-files` (`.opencode/skills/n3tx-files/SKILL.md:1`); required skills reference file workflows in backend/model/bootstrap/testing (`.opencode/skills/n3tx-backend/SKILL.md:79`, `.opencode/skills/n3tx-models/SKILL.md:102`, `.opencode/skills/n3tx-app-bootstrap/SKILL.md:76`, `.opencode/skills/n3tx-testing/SKILL.md:58`); frontend docs cover theme architecture, sidebar routing, profile import, icon registry, and E2E harness details (`FRONTEND.md:76`, `FRONTEND.md:117`, `FRONTEND.md:143`, `FRONTEND.md:184`, `FRONTEND.md:318`). | Agents can perform older generic N3TX work well but miss high-value details for files, route grammar, app shell/theme, ManyToMany, browser verification, and project-specific agent UI. | Promote `n3tx-files` into the core catalog list, add `n3tx-routing-views`, `n3tx-theme-shell`, and `n3tx-many-to-many` or enrich existing skills with deeper sections. |
| P1 | Skills include many correct guardrails, but they lack an error-recovery playbook for when agents detect boundary violations mid-implementation. | `AGENTS.md` says if an inconsistency is spotted, stop and explain the problem for review (`AGENTS.md:167`, `AGENTS.md:175`); `n3tx-framework-boundaries` says if a feature cannot fit cleanly, identify the missing extension point instead of patching around N3TX (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:54`). | Agents may recognize a boundary issue but continue with local edits because no recovery sequence says what to inspect, what to pause, and how to propose the deeper fix. | Add a shared "boundary violation recovery" section used by all implementation skills. |
| P1 | Integration boundaries between `.opencode/skills`, `.agents/skills`, `.agents/prompts`, and `.pi` aliases are implicit, not operationalized in the project skill docs. | `.agents/skills/README.md` says prompts live in `.agents/prompts`, heavyweight skills live in `.agents/skills`, and OpenCode commands symlink into `.agents/commands` (`.agents/skills/README.md:3`, `.agents/skills/README.md:15`, `.agents/skills/README.md:18`); `.pi` alias tests derive nested path aliases from skill paths (`.pi/extensions/skill-path-aliases/skill-aliases.test.mjs:35`, `.pi/extensions/skill-path-aliases/skill-aliases.test.mjs:50`); `.opencode/.gitignore` ignores `package.json` even though a package file exists (`.opencode/.gitignore:1`, `.opencode/package.json:1`). | Skill maintainers can add or move skills without understanding cross-harness discovery, alias behavior, and ignored local tooling files. | Add a project `n3tx-opencode-skills` maintenance skill or README explaining catalog ownership, reload constraints, validation, and cross-harness boundaries. |

## System Context That Matters

N3TX's central contract is schema-first: model definitions generate API, JSON Schema, storage, access, and UI behavior (`AGENTS.md:58`, `AGENTS.md:60`, `AGENTS.md:290`).

The frontend must adapt from backend runtime schema, not duplicate backend knowledge (`AGENTS.md:66`, `FRONTEND.md:288`, `FRONTEND.md:296`).

Framework behavior is intended to be traceable from model definition to schema, route/TX, storage/actor, and frontend rendering (`AGENTS.md:68`, `.opencode/skills/n3tx-principles/SKILL.md:23`).

The package graph is a hard invariant: `n3tx-core` is foundational, actors and UI depend on core, agents depend on core and actors, files depend on core and actors, and the meta-package depends on all installable packages (`AGENTS.md:123`).

The skill catalog correctly encodes this invariant in framework maintenance by requiring acyclic dependencies `core <- actors/ui <- agents` (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:13`).

The catalog also correctly recognizes boundary rules: data in models, behavior in methods or actors, API exposure in generated routes or `@expose_route`, access in `__access__`, and external protocols behind actors/adapters (`.opencode/skills/n3tx-principles/SKILL.md:43`).

Documentation-first workflow is mandatory before implementation (`AGENTS.md:74`, `AGENTS.md:95`, `AGENTS.md:101`).

Several skills repeat a source-reading policy that prefers docs/skills/public APIs and inspects source only when docs are insufficient or observed behavior contradicts docs (`.opencode/skills/n3tx-principles/SKILL.md:53`, `.opencode/skills/n3tx-backend/SKILL.md:121`, `.opencode/skills/n3tx-frontend/SKILL.md:81`).

OpenCode session behavior matters because skill edits are not necessarily reflected in already-loaded running sessions; the user's prompt states loaded skills persist until OpenCode restart, and the catalog has no visible project-local warning section for this reload constraint.

## Catalog Inventory

| Skill | Primary role | Strongest content | Main risk |
|---|---|---|---|
| `n3tx-principles` | Architectural philosophy and boundary defaults. | Strong single-source-of-truth and anti-pattern framing (`.opencode/skills/n3tx-principles/SKILL.md:11`, `.opencode/skills/n3tx-principles/SKILL.md:73`). | "Use first for any N3TX application work" may collide with every implementation skill (`.opencode/skills/n3tx-principles/SKILL.md:9`). |
| `n3tx-backend` | Broad backend development. | Good public imports and backend guardrails (`.opencode/skills/n3tx-backend/SKILL.md:23`, `.opencode/skills/n3tx-backend/SKILL.md:102`). | Over-broad description competes with specialized skills (`.opencode/skills/n3tx-backend/SKILL.md:3`). |
| `n3tx-frontend` | Broad frontend development. | Clear schema consumption and raw-fetch guardrails (`.opencode/skills/n3tx-frontend/SKILL.md:11`, `.opencode/skills/n3tx-frontend/SKILL.md:64`). | Too shallow for theme/app-shell/sidebar/profile/icon workflows now documented in `FRONTEND.md` (`FRONTEND.md:76`, `FRONTEND.md:138`, `FRONTEND.md:318`). |
| `n3tx-framework-maintenance` | Framework internals. | Correct package-boundary and docs/test workflow (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:11`, `.opencode/skills/n3tx-framework-maintenance/SKILL.md:31`). | Needs stronger `Use ONLY when` and direct warnings against app-code usage in description/body (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:3`, `.opencode/skills/n3tx-framework-maintenance/SKILL.md:9`). |
| `n3tx-build-app` | End-to-end app feature construction. | Good sequence from models to verification (`.opencode/skills/n3tx-build-app/SKILL.md:11`). | Biases toward Level 3 for serious apps (`.opencode/skills/n3tx-build-app/SKILL.md:32`). |
| `n3tx-models` | Model definitions and contracts. | Strong canonical model and schema expectations (`.opencode/skills/n3tx-models/SKILL.md:22`, `.opencode/skills/n3tx-models/SKILL.md:125`). | Uses mutable default examples such as `comments: ListRef['Comment'] = Field(default=[])` and `tags: ManyToMany[Tag] = Field(default=[])`; if Pydantic handles these safely, the skill should still prefer `default_factory=list` to avoid teaching a Python anti-pattern (`.opencode/skills/n3tx-models/SKILL.md:61`, `.opencode/skills/n3tx-models/SKILL.md:62`). |
| `n3tx-actors` | Actor-backed capabilities. | Simple TX mental model and actor shape decision table (`.opencode/skills/n3tx-actors/SKILL.md:11`, `.opencode/skills/n3tx-actors/SKILL.md:49`). | Under-specifies interceptors, `fullmethod`, lifecycle payload details, and actor-auth interplay compared with AGENTS/BACKEND (`AGENTS.md:500`, `BACKEND.md:48`). |
| `n3tx-agents` | LLM-powered features. | Correct import-order warning and tool discovery (`.opencode/skills/n3tx-agents/SKILL.md:11`, `.opencode/skills/n3tx-agents/SKILL.md:58`). | Example uses a dated/fixed model ID string; if stale, agents may copy it blindly (`.opencode/skills/n3tx-agents/SKILL.md:26`). |
| `n3tx-authorization` | Auth/access. | Good backend-owned auth and two-tier actor routing summary (`.opencode/skills/n3tx-authorization/SKILL.md:9`, `.opencode/skills/n3tx-authorization/SKILL.md:71`). | Does not mention route mirror auth parity and class-name route behavior from BACKEND (`BACKEND.md:190`). |
| `n3tx-storage-relationships` | Storage, JSON fields, ListRef, ManyToMany. | Good relationship primitive distinction (`.opencode/skills/n3tx-storage-relationships/SKILL.md:44`). | Overlaps heavily with `n3tx-json-fields` and `n3tx-models`; missing routing ambiguity rule for duplicate parent-to-child relationships from BACKEND (`BACKEND.md:211`). |
| `n3tx-json-fields` | JSON field persistence. | Strong relationship-vs-embedded-data boundary (`.opencode/skills/n3tx-json-fields/SKILL.md:25`, `.opencode/skills/n3tx-json-fields/SKILL.md:56`). | Points to `docs/JSON_FIELDS.md` but the audit did not verify that file; add a lint check that referenced docs exist (`.opencode/skills/n3tx-json-fields/SKILL.md:12`). |
| `n3tx-methods-routes` | Custom methods and generated routes. | Correct table/class method mirrors and `@` boundary (`.opencode/skills/n3tx-methods-routes/SKILL.md:25`, `.opencode/skills/n3tx-methods-routes/SKILL.md:51`). | Does not include the full nested class-name grammar or ambiguity rule present in BACKEND (`BACKEND.md:180`, `BACKEND.md:211`). |
| `n3tx-streaming` | Streaming methods and UI. | Good event schema and lifecycle guidance (`.opencode/skills/n3tx-streaming/SKILL.md:29`, `.opencode/skills/n3tx-streaming/SKILL.md:71`). | Frontend docs say `ntx-chat` and `ntx-agent-live` extend `NTTStream` directly, while the skill's component table may imply all rich agent output should use `NTTStreamAgent` without capturing that nuance (`FRONTEND.md:501`, `FRONTEND.md:547`). |
| `n3tx-networking` | TX/network adapters. | Strong external protocol boundary (`.opencode/skills/n3tx-networking/SKILL.md:11`, `.opencode/skills/n3tx-networking/SKILL.md:38`). | External integration guidance duplicates `n3tx-external-integrations`; routing needs clearer "which skill wins" criteria. |
| `n3tx-ui-schema` | Backend UI contract. | Clear map of schema sections to frontend behavior (`.opencode/skills/n3tx-ui-schema/SKILL.md:33`). | Missing modern schema-consuming details such as `ui.description`, `ui.create_label`, icons, and route renderer fallback from FRONTEND (`FRONTEND.md:309`, `FRONTEND.md:311`, `FRONTEND.md:396`). |
| `n3tx-ui-components` | Web components/custom renderers. | Good lifecycle and router attrs (`.opencode/skills/n3tx-ui-components/SKILL.md:48`, `.opencode/skills/n3tx-ui-components/SKILL.md:55`). | Example import path is context-sensitive (`./components/NTTElement.js`) and may mislead across package/app static roots (`.opencode/skills/n3tx-ui-components/SKILL.md:36`, `FRONTEND.md:276`). |
| `n3tx-widgets` | Field widgets. | Good widget-vs-component distinction (`.opencode/skills/n3tx-widgets/SKILL.md:47`). | Does not mention boolean auto-widget behavior documented in FRONTEND (`FRONTEND.md:91`). |
| `n3tx-testing` | App verification. | Good verification order and contract-first testing (`.opencode/skills/n3tx-testing/SKILL.md:11`, `.opencode/skills/n3tx-testing/SKILL.md:76`). | Understates rich frontend runner options and readiness-helper rules from FRONTEND (`FRONTEND.md:184`, `FRONTEND.md:218`, `FRONTEND.md:250`). |
| `n3tx-extension-patterns` | Extension points. | Strong decision tree and guardrails (`.opencode/skills/n3tx-extension-patterns/SKILL.md:11`, `.opencode/skills/n3tx-extension-patterns/SKILL.md:63`). | Needs a stronger "do not extend before checking app-level mechanism" trigger in frontmatter. |
| `n3tx-external-integrations` | Third-party APIs/services. | Good actor/adaptor/file boundary table (`.opencode/skills/n3tx-external-integrations/SKILL.md:11`). | Needs explicit secret storage guidance; it only says not to expose secrets in schema/responses (`.opencode/skills/n3tx-external-integrations/SKILL.md:72`). |
| `n3tx-framework-boundaries` | Anti-pattern guardrails. | Strong entropy framing and decision test (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:9`, `.opencode/skills/n3tx-framework-boundaries/SKILL.md:28`). | Should be trigger-routed before implementation when words like "custom route", "direct SQL", "fetch", "bypass", or "workaround" appear. |
| `n3tx-app-bootstrap` | App entrypoint wiring. | Strong import-order and static-file ordering (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:9`, `.opencode/skills/n3tx-app-bootstrap/SKILL.md:90`). | Omits Level 2 heading even though AGENTS explicitly documents Level 2 (`AGENTS.md:221`, `AGENTS.md:540`). |
| `n3tx-files` | File metadata and byte stores. | Strong FileStore/materialization guardrails (`.opencode/skills/n3tx-files/SKILL.md:9`, `.opencode/skills/n3tx-files/SKILL.md:50`). | It exists in the catalog but was not included in the user's core list, suggesting catalog/index discoverability is already weak. |

## Quality Risks

### Q1. Broad skills can hide more precise guardrails

`n3tx-backend` is framed as broad backend application development and includes models, storage, auth, routes, actors, agents, ManyToMany, files, bootstrap, integrations, and verification in one description (`.opencode/skills/n3tx-backend/SKILL.md:3`).

`n3tx-build-app` similarly covers creating an app, routing level, models, UI, agents, storage, auth, ManyToMany, files, and verification (`.opencode/skills/n3tx-build-app/SKILL.md:3`).

`n3tx-principles` says to use itself first for any N3TX application work (`.opencode/skills/n3tx-principles/SKILL.md:9`).

This makes the selection layer underspecified for tasks like "add a file upload to an agent workflow", which could require `n3tx-files`, `n3tx-agents`, `n3tx-methods-routes`, `n3tx-authorization`, and `n3tx-testing`.

The current catalog has no skill routing matrix or parent index that tells an agent the precedence among broad and narrow skills.

Concrete fix: add `.opencode/skills/n3tx-skill-routing/SKILL.md` or `.opencode/skills/README.md` with trigger precedence and composition rules.

### Q2. Defaulting to ActorModel/Level 3 may overfit advanced apps

`n3tx-build-app` explicitly recommends `ActorModel` and Level 3 for new serious apps unless there is a reason to stay simpler (`.opencode/skills/n3tx-build-app/SKILL.md:32`).

`n3tx-models` says default new app entities to `ActorModel` if the app may use agents, workflows, actor routing, or reusable capabilities (`.opencode/skills/n3tx-models/SKILL.md:20`).

The main guide documents Level 1 one-liner `create_app`, Level 2 builder, and Level 3 raw primitives (`AGENTS.md:215`).

The same guide says all three levels produce identical API endpoints and responses (`AGENTS.md:231`).

`n3tx-app-bootstrap` gives a narrower rule: use Level 3 when actor/network/agent integration matters (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:41`).

Quality risk: a code agent might make every app an actor-routed app even when pure schema-driven CRUD would be enough.

Concrete fix: replace "new serious apps" language with a decision table that preserves zero-to-working simplicity.

Preferred language:

```markdown
Default by need:
- Use `ProtoModel` + direct routing for simple CRUD/schema-driven apps.
- Use `ActorModel` + direct routing when entities need actor capabilities but HTTP direct routes are enough.
- Use `ActorModel` + `routing='actor'` when TX routing, agents, MCP, WebSocket, federation, or protocol adapters are part of the requirement.
```

### Q3. Some examples teach Python mutable defaults

`n3tx-backend` shows `comments: ListRef['Comment'] = []` and `tags: ManyToMany[Tag] = []` (`.opencode/skills/n3tx-backend/SKILL.md:71`).

`n3tx-storage-relationships` shows `comments: ListRef['Comment'] = []` and `tags: ManyToMany[Tag] = Field(default=[])` (`.opencode/skills/n3tx-storage-relationships/SKILL.md:66`, `.opencode/skills/n3tx-storage-relationships/SKILL.md:95`).

`n3tx-json-fields` shows `metadata: dict = {}` and `payloads: list = []` (`.opencode/skills/n3tx-json-fields/SKILL.md:33`, `.opencode/skills/n3tx-json-fields/SKILL.md:37`).

Even if Pydantic copies defaults safely, skills are teaching general-purpose Python patterns to agents.

Concrete fix: prefer `Field(default_factory=list)` and `Field(default_factory=dict)` in every skill example unless the framework intentionally requires otherwise.

### Q4. Route grammar is correct but fragmented

`n3tx-methods-routes` covers table-name routes, schema endpoint, class-name mirrors, method mirrors, and view `@` semantics (`.opencode/skills/n3tx-methods-routes/SKILL.md:51`).

`n3tx-frontend` covers hash route examples and `@` boundary semantics (`.opencode/skills/n3tx-frontend/SKILL.md:32`, `.opencode/skills/n3tx-frontend/SKILL.md:46`).

BACKEND contains much deeper route grammar including class-name JSON mirrors, nested mirrors, HTML view routes, and method mirror constraints (`BACKEND.md:161`, `BACKEND.md:190`).

FRONTEND contains nested hash route grammar and semantic model/cache behavior (`FRONTEND.md:375`, `FRONTEND.md:409`, `FRONTEND.md:436`).

Risk: an agent might implement a route/view change using a shallow route model and miss nested-route ambiguity or renderer fallback behavior.

Concrete fix: add `n3tx-routing-views` or enrich `n3tx-methods-routes` and `n3tx-frontend` with the nested route and ambiguity rules.

### Q5. Agent skill example may freeze a stale LLM identifier

`n3tx-agents` shows `llm='anthropic:claude-sonnet-4-5-20250929'` in the dynamic agent example (`.opencode/skills/n3tx-agents/SKILL.md:26`).

The backend docs describe a configuration cascade for agents (`AGENTS.md:529`).

Risk: agents copy a hard-coded model ID rather than using config defaults or test models.

Concrete fix: use `llm=None` or a placeholder such as `llm='provider:model'`, then point to `AGENT_DEFAULTS` or task-specific config.

### Q6. External integration skill lacks secret-handling architecture

`n3tx-external-integrations` says not to expose secrets in schema or responses (`.opencode/skills/n3tx-external-integrations/SKILL.md:72`).

The same skill recommends storable `ActorModel` for API clients with saved credentials/config (`.opencode/skills/n3tx-external-integrations/SKILL.md:15`).

Risk: an agent may store API keys directly in normal fields that appear in schema/entity responses.

Concrete fix: add a credential boundary section: use environment references, encrypted/secret stores, protected fields, or provider-specific secret handles; never normal response-visible fields.

### Q7. Source-reading policy is good but not enforceable

`AGENTS.md` mandates documentation-first context loading before implementation (`AGENTS.md:74`).

Several skills repeat source-reading policies (`.opencode/skills/n3tx-principles/SKILL.md:53`, `.opencode/skills/n3tx-framework-maintenance/SKILL.md:40`).

Risk: agents can still jump to source if a skill is selected without AGENTS context.

Concrete fix: add a standard `Before Editing` block to every implementation skill with explicit doc files to read and a "do not edit before" checklist.

## Coverage Analysis

| Workflow | Coverage | Evidence | Gap | Highest-value enrichment |
|---|---|---|---|---|
| Core principles | Strong | `n3tx-principles` covers model-as-app, backend authority, actors, networking, zero-to-working, transparency (`.opencode/skills/n3tx-principles/SKILL.md:11`). | No routing matrix. | Add one-page skill index. |
| Backend CRUD/modeling | Strong | `n3tx-backend` and `n3tx-models` provide imports and canonical examples (`.opencode/skills/n3tx-backend/SKILL.md:23`, `.opencode/skills/n3tx-models/SKILL.md:22`). | Mutable default examples. | Normalize examples. |
| App bootstrap | Strong | `n3tx-app-bootstrap` covers import order, Level 1, Level 3, builder, static merge, files (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:9`, `.opencode/skills/n3tx-app-bootstrap/SKILL.md:23`, `.opencode/skills/n3tx-app-bootstrap/SKILL.md:31`, `.opencode/skills/n3tx-app-bootstrap/SKILL.md:90`). | Level 2 missing as heading. | Add Level 2 and default decision table. |
| Relationships | Moderate/strong | `ListRef`, `ManyToMany`, ownership, self-ref covered (`.opencode/skills/n3tx-storage-relationships/SKILL.md:44`, `.opencode/skills/n3tx-storage-relationships/SKILL.md:102`). | Duplicate same child class ambiguity missing. | Add ambiguous class-name nested route rule. |
| JSON fields | Strong | Dedicated skill explains embedded data vs resources (`.opencode/skills/n3tx-json-fields/SKILL.md:25`, `.opencode/skills/n3tx-json-fields/SKILL.md:47`). | Referenced docs existence should be linted. | Add docs-reference checker. |
| Authorization | Moderate/strong | `n3tx-authorization` covers ABAC, user injection, protected fields, two-tier auth (`.opencode/skills/n3tx-authorization/SKILL.md:11`, `.opencode/skills/n3tx-authorization/SKILL.md:48`, `.opencode/skills/n3tx-authorization/SKILL.md:60`, `.opencode/skills/n3tx-authorization/SKILL.md:71`). | Field-level access and mirror route parity need deeper coverage. | Add route parity and schema access examples. |
| Methods/routes | Moderate | `n3tx-methods-routes` captures basic `@expose_route` and route grammar (`.opencode/skills/n3tx-methods-routes/SKILL.md:11`, `.opencode/skills/n3tx-methods-routes/SKILL.md:51`). | Nested class-name grammar under-covered. | Add route/view/nested skill. |
| Streaming | Moderate/strong | Backend event schemas, TX protocol, frontend components, lifecycle covered (`.opencode/skills/n3tx-streaming/SKILL.md:11`, `.opencode/skills/n3tx-streaming/SKILL.md:36`, `.opencode/skills/n3tx-streaming/SKILL.md:51`, `.opencode/skills/n3tx-streaming/SKILL.md:71`). | Agent stream component hierarchy nuance. | Align with latest FRONTEND. |
| Frontend schema/UI | Moderate | `n3tx-frontend`, `n3tx-ui-schema`, `n3tx-ui-components`, `n3tx-widgets` cover schema-driven UI, components, widgets (`.opencode/skills/n3tx-frontend/SKILL.md:48`, `.opencode/skills/n3tx-ui-components/SKILL.md:11`, `.opencode/skills/n3tx-widgets/SKILL.md:11`). | Themes, shell slots, icon registry, sidebar routing, profile import under-covered. | Add `n3tx-theme-shell` or enrich frontend skill. |
| Actors/networking | Moderate | Actor and networking skills cover TX/Matrix/adapters (`.opencode/skills/n3tx-actors/SKILL.md:11`, `.opencode/skills/n3tx-networking/SKILL.md:11`). | Interceptors and actor auth details shallow. | Add interceptor/auth subsection. |
| Agents | Moderate | Agent import order, tool discovery, TestModel covered (`.opencode/skills/n3tx-agents/SKILL.md:11`, `.opencode/skills/n3tx-agents/SKILL.md:58`, `.opencode/skills/n3tx-agents/SKILL.md:85`). | Config cascade, thread context, agent UI details shallow. | Enrich with config cascade and `ntx-chat` contracts. |
| Files | Strong but discoverability weak | `n3tx-files` covers metadata, FileStore, upload/download, addresses, materialization (`.opencode/skills/n3tx-files/SKILL.md:9`, `.opencode/skills/n3tx-files/SKILL.md:30`, `.opencode/skills/n3tx-files/SKILL.md:50`). | Not included in user's core list despite catalog existence. | Add catalog index and cross-links. |
| Testing | Moderate | Testing skill covers contract order and backend/frontend/agent/file/stream checks (`.opencode/skills/n3tx-testing/SKILL.md:11`, `.opencode/skills/n3tx-testing/SKILL.md:18`, `.opencode/skills/n3tx-testing/SKILL.md:37`, `.opencode/skills/n3tx-testing/SKILL.md:46`). | Frontend runner richness and readiness helpers missing. | Add current test matrix from FRONTEND. |
| Framework maintenance | Strong baseline | Maintenance skill covers package boundaries, docs/tests, source inspection (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:11`, `.opencode/skills/n3tx-framework-maintenance/SKILL.md:31`, `.opencode/skills/n3tx-framework-maintenance/SKILL.md:40`). | Skill/docs maintenance not operationalized. | Add skill-maintenance checklist/linter. |

## Consistency and Drift Analysis

| Drift area | Skill text | Authoritative context | Risk | Fix |
|---|---|---|---|---|
| Routing default | Level 3 for new serious apps (`.opencode/skills/n3tx-build-app/SKILL.md:32`). | Three levels are separately documented and equivalent at endpoint/response level (`AGENTS.md:215`, `AGENTS.md:231`). | Over-engineering. | Use need-based default table. |
| Level 2 bootstrap | `n3tx-app-bootstrap` has Level 1 and Level 3 headings but no Level 2 heading (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:23`, `.opencode/skills/n3tx-app-bootstrap/SKILL.md:31`). | AGENTS documents Level 2 as `ActorModel` + direct routes (`AGENTS.md:540`). | Agents may think only Level 1 and Level 3 exist. | Add Level 2 section. |
| Stream component hierarchy | Skill lists `NTTStreamAgent` as rich agent output base (`.opencode/skills/n3tx-streaming/SKILL.md:57`). | FRONTEND says `ntx-agent-live` and `ntx-chat` extend `NTTStream` directly, even while `NTTStreamAgent` exists for rich output (`FRONTEND.md:501`, `FRONTEND.md:547`). | Agents may subclass wrong base or duplicate rendering. | Clarify current hierarchy and when to use each. |
| UI schema fields | Skill lists core UI fields (`.opencode/skills/n3tx-ui-schema/SKILL.md:33`). | FRONTEND includes `ui.description`, `ui.create_label`, `ui.icon`, renderer resolution/fallbacks (`FRONTEND.md:309`, `FRONTEND.md:310`, `FRONTEND.md:311`, `FRONTEND.md:396`). | Agents miss newer UI affordances. | Update UI schema skill. |
| Widget behavior | Widget skill covers explicit hints and registry (`.opencode/skills/n3tx-widgets/SKILL.md:11`, `.opencode/skills/n3tx-widgets/SKILL.md:31`). | FRONTEND states boolean fields auto-resolve to `bool` widget without explicit hint (`FRONTEND.md:91`). | Agents may add unnecessary hints or custom widgets. | Add bool auto-widget rule. |
| Test commands | `n3tx-testing` lists backend runner and two frontend commands (`.opencode/skills/n3tx-testing/SKILL.md:29`, `.opencode/skills/n3tx-testing/SKILL.md:37`). | FRONTEND lists aggregate runner and multiple E2E lanes (`FRONTEND.md:184`, `FRONTEND.md:250`). | Agents run too broad, too slow, or wrong suite. | Add decision table for test lane selection. |
| Static file nuance | Bootstrap says static dirs merge with app, agents, UI, core priority (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:90`). | FRONTEND explains all static dirs merge into one URL namespace and app examples override `index.html` (`FRONTEND.md:276`, `FRONTEND.md:286`). | Component import examples may be copied incorrectly. | Add static import path guidance. |
| Relationship ambiguity | Storage skill says canonical nested identity uses `/Product/1/Comment/2` (`.opencode/skills/n3tx-storage-relationships/SKILL.md:69`). | BACKEND says duplicate relationships from one parent to same child class must fail or skip ambiguous class-name mirror (`BACKEND.md:211`). | Agents may create ambiguous schema/routes. | Add ambiguity guardrail. |

## Trigger and Selection Risks

OpenCode skill descriptions should front-load concrete trigger keywords and filenames per the user's project context.

Most current descriptions are noun-heavy but not keyword-front-loaded; for example `n3tx-framework-boundaries` starts "N3TX framework boundary guardrails and anti-patterns" before listing bypass concepts (`.opencode/skills/n3tx-framework-boundaries/SKILL.md:3`).

Narrow skills rarely use `Use ONLY when...`; `n3tx-framework-maintenance` uses "Use only when" in sentence case (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:3`), but other narrow skills such as `n3tx-json-fields`, `n3tx-files`, and `n3tx-extension-patterns` do not (`.opencode/skills/n3tx-json-fields/SKILL.md:3`, `.opencode/skills/n3tx-files/SKILL.md:3`, `.opencode/skills/n3tx-extension-patterns/SKILL.md:3`).

High-collision trigger pairs:

| Task phrase | Likely collisions | Better routing |
|---|---|---|
| "Add upload" | `n3tx-backend`, `n3tx-build-app`, `n3tx-files`, `n3tx-external-integrations`, `n3tx-testing`. | Load `n3tx-files` first, then `n3tx-authorization` and `n3tx-testing`; use backend/build-app only for full feature wiring. |
| "Make model agentic" | `n3tx-models`, `n3tx-agents`, `n3tx-actors`, `n3tx-app-bootstrap`. | Load `n3tx-agents` and `n3tx-app-bootstrap`; use `n3tx-models` for field/schema changes. |
| "Custom API endpoint" | `n3tx-methods-routes`, `n3tx-backend`, `n3tx-framework-boundaries`. | Load `n3tx-methods-routes`; load `n3tx-framework-boundaries` if user asks for FastAPI/custom route/bypass. |
| "Frontend card layout" | `n3tx-frontend`, `n3tx-ui-schema`, `n3tx-ui-components`, `n3tx-widgets`. | Load `n3tx-ui-schema` first for backend renderer hints; use components only when whole-entity layout is needed; widgets only for field rendering. |
| "Call external API from agent" | `n3tx-agents`, `n3tx-external-integrations`, `n3tx-networking`, `n3tx-actors`. | Load `n3tx-external-integrations`; add `n3tx-agents` for tool discovery and `n3tx-networking` only for protocol adapter work. |
| "Fix route view" | `n3tx-frontend`, `n3tx-methods-routes`, `n3tx-ui-schema`, missing `n3tx-routing-views`. | Add routing skill or enrich all three with routing matrix. |

Recommended description pattern:

```yaml
description: "N3TX file uploads/downloads, FileStore, File metadata, /files/upload, /File/{id}/download, File-typed method args. Use ONLY when adding or debugging user files, blob storage, upload/download routes, range requests, or file argument materialization."
```

Recommended broad-skill pattern:

```yaml
description: "N3TX backend models/routes/storage/auth at a broad application level. Use when a backend task spans multiple model, storage, auth, route, actor, or verification concerns; prefer narrower n3tx-* skills for focused work."
```

## Failure Modes

| Failure mode | Why current skills allow it | Impact | Guardrail to add |
|---|---|---|---|
| Agent adds a custom FastAPI route for model behavior. | Many skills say not to do this (`.opencode/skills/n3tx-backend/SKILL.md:104`, `.opencode/skills/n3tx-methods-routes/SKILL.md:66`), but no trigger says "custom endpoint" must load methods/boundaries. | Duplicate API path and schema/tool invisibility. | Trigger matrix: custom endpoint/action -> `n3tx-methods-routes` + `n3tx-framework-boundaries`. |
| Agent stores file bytes in a model or static dir. | Multiple guardrails prohibit it (`.opencode/skills/n3tx-files/SKILL.md:81`, `.opencode/skills/n3tx-app-bootstrap/SKILL.md:107`), but file skill discoverability is weak. | Security, auth, and storage boundary violation. | Promote `n3tx-files` and add trigger terms `upload`, `download`, `blob`, `attachment`, `FileStore`. |
| Agent duplicates access checks in JS. | Frontend/auth skills prohibit it (`.opencode/skills/n3tx-frontend/SKILL.md:67`, `.opencode/skills/n3tx-authorization/SKILL.md:84`). | UI drift and false security. | Add "schema access first" verification to frontend component skill. |
| Agent uses JSON arrays for relationships. | JSON/storage skills prohibit it (`.opencode/skills/n3tx-json-fields/SKILL.md:56`, `.opencode/skills/n3tx-storage-relationships/SKILL.md:53`). | Missing identity, routes, auth, lifecycle. | Add examples of when primitive `list[str]` is okay vs `ListRef`/`ManyToMany`. |
| Agent uses raw frontend `fetch()` for entity actions. | Multiple skills prohibit it (`.opencode/skills/n3tx-frontend/SKILL.md:68`, `.opencode/skills/n3tx-framework-boundaries/SKILL.md:21`). | Bypasses transport, auth adaptation, entity cache. | Add "if raw fetch appears in diff, justify or refactor" checklist. |
| Agent creates external API call inside a random model method. | Integration skill says external IO must be wrapped in reusable boundary (`.opencode/skills/n3tx-external-integrations/SKILL.md:9`). | Non-reusable, hard-to-test IO. | Add boundary examples for one-off private integrations vs shared tool actors. |
| Agent misses package import order for mixins. | Bootstrap and agents skills warn about import order (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:9`, `.opencode/skills/n3tx-agents/SKILL.md:11`). | `__agent__` or `__ui__` mixin silently not injected. | Add import-order assertion/verification checklist. |
| Agent loosens tests to pass. | Testing skill says not to loosen tests without intended contract (`.opencode/skills/n3tx-testing/SKILL.md:80`). | Regression hidden. | Add bugfix/test-fix cross-skill routing to load TDD/fix-test workflows. |

## Extensibility Analysis

The skills are easy to add structurally because each project skill is a folder containing `SKILL.md` with frontmatter (`.opencode/skills/n3tx-principles/SKILL.md:1`).

The shared `.agents/skills` README states a real skill must live in its own directory with `SKILL.md` and frontmatter `name:` matching the parent directory exactly (`.agents/skills/README.md:61`).

The current `.opencode/skills` catalog follows lowercase hyphenated folder names and matching `name` values, for example `n3tx-app-bootstrap` (`.opencode/skills/n3tx-app-bootstrap/SKILL.md:1`).

Extensibility weakness: shared policy is copied by prose into every skill rather than factored into a canonical include or validated checklist.

Extensibility weakness: cross-skill relationships are implicit; no file says `n3tx-files` should compose with `n3tx-authorization`, `n3tx-methods-routes`, and `n3tx-testing` for upload workflows.

Extensibility weakness: no generated catalog index is present in `.opencode/skills`, even though a full catalog exists and includes skills outside the user's core list (`.opencode/skills/n3tx-files/SKILL.md:1`).

Extensibility weakness: no drift test checks duplicated claims such as route grammar, package graph, static mount order, test commands, or current component hierarchy against docs.

Extensibility opportunity: skills can become a stable agent interface for N3TX if each skill follows a common structure:

```markdown
---
name: n3tx-<area>
description: "<front-loaded trigger terms>. Use ONLY when <narrow condition>."
argument-hint: "<task>"
---

# N3TX <Area>

## Trigger
Use when...
Do not use when...

## Read First
- `AGENTS.md` lines/section
- area docs
- package docs

## Decision Rules
...

## Canonical Pattern
...

## Guardrails
...

## Verification
...

## Drift Anchors
- Source docs this skill duplicates.
```

## Integration Boundaries

`.opencode/skills` is the project-local OpenCode skill catalog under review.

`.agents/skills` is a shared skill tree for heavyweight specialized capabilities, while `.agents/prompts` contains lightweight explicitly invoked workflows (`.agents/skills/README.md:3`).

OpenCode commands are wired to `.agents/commands`, which points to prompts (`.agents/skills/README.md:15`, `.agents/skills/README.md:18`).

Claude/OpenCode/pi skills continue to read from `.agents/skills` through discovery paths or symlinks (`.agents/skills/README.md:19`).

The `.pi` skill alias extension derives nested folder aliases from skill paths ending in `SKILL.md` (`.pi/extensions/skill-path-aliases/skill-aliases.test.mjs:35`).

The `.pi` extension rewrites nested aliases such as `/skill:architecture:deep-audit` to canonical skill commands (`.pi/extensions/skill-path-aliases/skill-aliases.test.mjs:60`).

The extension also waits until session start to register nested aliases after runtime readiness (`.pi/extensions/skill-path-aliases/index.test.mjs:38`).

Boundary risk: project `.opencode/skills` and shared `.agents/skills` have different roles, but the current project skills do not explain that relationship.

Boundary risk: `.opencode/.gitignore` ignores `package.json`, while `.opencode/package.json` exists and declares `@opencode-ai/plugin` (`.opencode/.gitignore:2`, `.opencode/package.json:1`).

This may be intentional local tooling hygiene, but a skill-maintenance README should explain whether `.opencode/package.json` is source-controlled or local-only.

## Resilience Propositions

### R1. Skill Linting

Add a lint script with these checks:

| Check | Rule | Evidence basis |
|---|---|---|
| Folder/name match | `frontmatter.name == parent folder`. | `.agents/skills/README.md:61`. |
| Name format | Lowercase hyphen-separated and <=64 chars. | User-provided OpenCode constraint. |
| Description exists | Non-empty and includes what/when. | User-provided OpenCode constraint. |
| Trigger front-loading | First 12 words include concrete keywords or filenames. | User-provided OpenCode constraint. |
| Narrow wording | Skills with `framework-maintenance`, `json-fields`, `files`, `extension-patterns`, `framework-boundaries` should say `Use ONLY when...`. | `n3tx-framework-maintenance` already narrows usage (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:9`). |
| Source anchors | Every duplicated technical claim has a docs anchor in a `Drift Anchors` block. | Docs are authoritative (`AGENTS.md:80`). |
| Mutable defaults | Flag `= []`, `= {}`, `Field(default=[])`, `Field(default={})` in examples. | Existing examples contain these (`.opencode/skills/n3tx-json-fields/SKILL.md:33`, `.opencode/skills/n3tx-storage-relationships/SKILL.md:95`). |
| Command freshness | Test commands in skills exist in AGENTS/BACKEND/FRONTEND. | AGENTS lists backend runner commands (`AGENTS.md:571`); FRONTEND lists frontend runner commands (`FRONTEND.md:184`). |
| Package boundary | Flag imports in examples that violate graph. | AGENTS documents graph (`AGENTS.md:123`). |
| Referenced docs exist | Every `docs/*.md` path in skills exists. | `n3tx-json-fields` references `docs/JSON_FIELDS.md` (`.opencode/skills/n3tx-json-fields/SKILL.md:12`). |

Sketch:

```javascript
// .opencode/scripts/lint-skills.mjs
import fs from 'node:fs';
import path from 'node:path';

const root = '/workspace/.opencode/skills';
const requiredSections = ['## Trigger', '## Guardrails', '## Verification'];

for (const dir of fs.readdirSync(root)) {
  const file = path.join(root, dir, 'SKILL.md');
  if (!fs.existsSync(file)) continue;
  const text = fs.readFileSync(file, 'utf8');
  const fm = text.match(/^---\n([\s\S]*?)\n---/);
  if (!fm) throw new Error(`${dir}: missing frontmatter`);
  const name = fm[1].match(/^name:\s*(.+)$/m)?.[1]?.trim();
  const desc = fm[1].match(/^description:\s*(.+)$/m)?.[1]?.trim();
  if (name !== dir) throw new Error(`${dir}: name mismatch ${name}`);
  if (!desc) throw new Error(`${dir}: missing description`);
  if (/= \[\]|= \{}|default=\[\]|default=\{\}/.test(text)) {
    throw new Error(`${dir}: mutable default in example`);
  }
}
```

### R2. Drift Detection Matrix

Maintain a table mapping each skill to authoritative docs:

| Skill | Drift anchors |
|---|---|
| `n3tx-principles` | `AGENTS.md:56`, `AGENTS.md:209`, `AGENTS.md:431`. |
| `n3tx-backend` | `BACKEND.md:17`, `BACKEND.md:56`, `BACKEND.md:127`. |
| `n3tx-frontend` | `FRONTEND.md:18`, `FRONTEND.md:288`, `FRONTEND.md:367`. |
| `n3tx-framework-maintenance` | `AGENTS.md:109`, `AGENTS.md:559`. |
| `n3tx-app-bootstrap` | `AGENTS.md:215`, `BACKEND.md:102`, `FRONTEND.md:276`. |
| `n3tx-methods-routes` | `BACKEND.md:159`, `AGENTS.md:433`. |
| `n3tx-streaming` | `AGENTS.md:441`, `BACKEND.md:293`, `FRONTEND.md:466`. |
| `n3tx-testing` | `AGENTS.md:571`, `FRONTEND.md:184`. |

Drift check behavior:

```text
For each skill:
  1. Parse Drift Anchors.
  2. Verify referenced files exist.
  3. Verify key tokens still appear near anchor section.
  4. Flag stale commands or routes not present in docs.
  5. Require manual review when anchors move significantly.
```

### R3. Shared Skill Template

Adopt this template for all N3TX project skills:

```markdown
---
name: n3tx-AREA
description: "KEYWORDS: file/path, route, class, decorator. Use ONLY when..."
argument-hint: "<task>"
---

# N3TX Area

## Trigger
Use this skill when the task mentions: ...
Do not use this skill for: ...

## Read First
- `/workspace/AGENTS.md` section ...
- `/workspace/BACKEND.md` section ...
- `/workspace/FRONTEND.md` section ...

## Decision Rules
| Need | Use | Avoid |

## Canonical Pattern
```python
...
```

## Guardrails
- ...

## Verification
- Narrow contract check
- Adjacent tests
- Full suite only when needed

## Failure Recovery
If the current implementation violates an N3TX boundary:
1. Stop editing.
2. Name the violated boundary.
3. Identify the correct N3TX extension point.
4. Propose the smallest aligned change.

## Drift Anchors
- `AGENTS.md:<line>`
- `BACKEND.md:<line>`
- `FRONTEND.md:<line>`
```

### R4. Cross-Skill Routing Matrix

Create `.opencode/skills/n3tx-skill-routing/SKILL.md` or `.opencode/skills/README.md`:

```markdown
# N3TX Skill Routing

| If user asks for | Load first | Then consider |
|---|---|---|
| app from scratch | `n3tx-build-app` | `n3tx-app-bootstrap`, `n3tx-models`, `n3tx-testing` |
| model field/schema | `n3tx-models` | `n3tx-json-fields`, `n3tx-storage-relationships`, `n3tx-ui-schema` |
| upload/download/blob | `n3tx-files` | `n3tx-authorization`, `n3tx-testing` |
| custom route/action | `n3tx-methods-routes` | `n3tx-framework-boundaries`, `n3tx-authorization` |
| frontend renderer | `n3tx-ui-schema` | `n3tx-ui-components`, `n3tx-widgets`, `n3tx-frontend` |
| external API | `n3tx-external-integrations` | `n3tx-networking`, `n3tx-agents` |
| framework internals | `n3tx-framework-maintenance` | area-specific skill + `n3tx-testing` |
| suspicious workaround | `n3tx-framework-boundaries` | relevant implementation skill |
```

### R5. Boundary Violation Recovery Block

Add to implementation skills:

```markdown
## Boundary Violation Recovery

Stop and reassess if the planned change includes:
- custom FastAPI route for normal app behavior
- direct SQL from feature code
- frontend raw `fetch()` for N3TX entities/actions
- duplicated schema/access/field metadata in JS
- file bytes in SQLite/static assets
- external API calls outside actor/adapter boundaries
- ad-hoc LLM tools outside actor/model methods

Recovery:
1. Name the violated boundary.
2. Identify the canonical N3TX mechanism.
3. Replace the workaround with the smallest schema/model/actor/widget/adapter change.
4. Verify at schema/API/TX/UI contract boundary.
```

This block is justified by AGENTS consistency rules and stop-on-inconsistency guidance (`AGENTS.md:167`, `AGENTS.md:175`).

### R6. Skill Enrichment Backlog

| Priority | Work item | Files | Why |
|---|---|---|---|
| P0 | Add routing matrix/index. | `.opencode/skills/README.md` or new `n3tx-skill-routing`. | Reduces trigger collisions across broad/narrow skills. |
| P0 | Normalize Level 1/2/3 guidance. | `n3tx-build-app`, `n3tx-models`, `n3tx-app-bootstrap`. | Prevents overuse of Level 3. |
| P0 | Add skill linter. | `.opencode/scripts/lint-skills.mjs`, package script if appropriate. | Catches frontmatter, drift, and example quality. |
| P1 | Promote/enrich file workflows. | `n3tx-files`, `n3tx-backend`, `n3tx-testing`. | Files are a distinct package and security boundary (`.opencode/skills/n3tx-files/SKILL.md:9`). |
| P1 | Add route/view/nested grammar skill. | New `n3tx-routing-views` or enrich `n3tx-methods-routes`/`n3tx-frontend`. | Route grammar is complex and cross-stack (`BACKEND.md:159`, `FRONTEND.md:369`). |
| P1 | Add theme/shell/frontend runtime enrichment. | `n3tx-frontend`, maybe new `n3tx-theme-shell`. | Theme, sidebar, profile, icons, and E2E behavior are now substantial (`FRONTEND.md:107`, `FRONTEND.md:143`, `FRONTEND.md:318`). |
| P1 | Replace mutable defaults in examples. | All skills. | Avoid teaching unsafe Python patterns. |
| P1 | Add secret handling guidance. | `n3tx-external-integrations`, `n3tx-authorization`. | Current text only warns not to expose secrets (`.opencode/skills/n3tx-external-integrations/SKILL.md:72`). |
| P2 | Add drift anchors section to every skill. | All skills. | Makes maintenance explicit. |
| P2 | Add cross-harness maintenance README. | `.opencode/skills/README.md`. | Clarifies `.opencode`, `.agents`, `.pi` boundaries (`.agents/skills/README.md:13`). |

## Concrete Skill Improvements

### Improved `n3tx-build-app` Description

```yaml
description: "N3TX end-to-end app features: create_app, N3TXApp, routing Level 1/2/3, models, auth, UI schema, agents, files, verification. Use when building a complete vertical slice; prefer narrower n3tx-* skills for isolated model, route, UI, file, or test tasks."
```

### Improved `n3tx-framework-maintenance` Description

```yaml
description: "N3TX framework internals: packages/n3tx-core, n3tx-actors, n3tx-ui, n3tx-agents, n3tx-files, schema/storage/routes/components/tests/docs. Use ONLY when modifying framework packages, public contracts, extension internals, or framework documentation."
```

This adds `n3tx-files`, which exists in AGENTS package structure (`AGENTS.md:119`) and has a project skill (`.opencode/skills/n3tx-files/SKILL.md:1`).

### Improved `n3tx-files` Description

```yaml
description: "N3TX uploads/downloads/blob storage: n3tx-files, File metadata, FileStore, /files/upload, /File/{id}/download, Range, File-typed method args. Use ONLY when adding or debugging user files, attachments, blob providers, upload/download routes, or file argument materialization."
```

### Improved Level Selection Block

```markdown
## Choose Routing Level

| Need | Use | Avoid |
|---|---|---|
| Simple schema-driven CRUD | `ProtoModel` + direct `create_app()` | Level 3 unless actor routing is needed |
| Entity with reusable actor behavior | `ActorModel` + direct routes | Custom HTTP handlers |
| Protocol routing, agents, MCP, WebSocket, federation | `ActorModel` + `routing='actor'` | Backend-to-backend HTTP |

All levels should preserve the same public API/schema behavior; choose the lowest level that satisfies the integration boundary.
```

This aligns with AGENTS three-level documentation and endpoint parity (`AGENTS.md:215`, `AGENTS.md:231`).

### Improved Relationship Example

```python
from pydantic import Field
from n3tx_core.models.ref import ListRef
from n3tx_core.models.relationships import ManyToMany

class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True

    comments: ListRef['Comment'] = Field(default_factory=list)
    tags: ManyToMany[Tag] = Field(default_factory=list)
```

### Improved JSON Field Example

```python
from pydantic import Field

class AgentConfig(ActorModel):
    __tablename__ = 'agent_configs'
    __storable__ = True

    tools: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
```

### Improved Secret Boundary Block

```markdown
## Credentials and Secrets

- Do not store raw API keys in normal schema-visible fields.
- Prefer environment-backed secret references, encrypted stores, or provider-owned credential handles.
- If a credential reference must be persisted, mark ownership/protection explicitly and verify it is absent from schema/entity responses.
- Agent tools should receive only the minimal non-secret arguments needed for the task.
```

This extends the current external integration warning that secrets must not leak in schema or responses (`.opencode/skills/n3tx-external-integrations/SKILL.md:72`).

## Proposed New Skills

### `n3tx-skill-routing`

Purpose: one router/index skill that chooses the right N3TX skill set.

Trigger description:

```yaml
description: "N3TX skill routing matrix for OpenCode: choose between n3tx-principles, backend, frontend, models, files, routes, agents, actors, testing, framework-maintenance. Use when an N3TX task is ambiguous or spans multiple skills."
```

### `n3tx-routing-views`

Purpose: route grammar, class-name mirrors, nested routes, hash routes, view `@` boundary, renderer fallback, and ambiguity rules.

Why: backend and frontend route semantics span many files and are too detailed for generic frontend/method skills (`BACKEND.md:159`, `FRONTEND.md:369`).

Trigger description:

```yaml
description: "N3TX route/view grammar: /{ClassName}, /{ClassName}/_, nested /Parent/id/Child/id, hash #Model/@view, @ view boundary, renderer fallback. Use ONLY when changing, debugging, or designing routes, view routes, router behavior, nested identities, or method/action navigation."
```

### `n3tx-theme-shell`

Purpose: theme tokens, shell slots, topbar/sidebar/profile/imports, icon registry, visual verification.

Why: frontend docs contain enough theme/shell behavior to justify a focused skill (`FRONTEND.md:107`, `FRONTEND.md:138`, `FRONTEND.md:176`, `FRONTEND.md:318`).

Trigger description:

```yaml
description: "N3TX theme and app shell: theme-base.css, dark/light themes, ntx-theme-button slots, topbar/sidebar/profile, icon registry, shell imports. Use ONLY when changing visual theme tokens, shell chrome, navigation sidebar/topbar, profile route, or icon rendering."
```

### `n3tx-skill-maintenance`

Purpose: maintain `.opencode/skills` itself.

Why: this audit target needs an explicit local process, and OpenCode configuration work has constraints around skill shape and loaded-session behavior from the user's context.

Trigger description:

```yaml
description: "N3TX OpenCode skill maintenance: .opencode/skills/*/SKILL.md, skill frontmatter, descriptions, trigger routing, drift anchors, lints, reload constraints. Use ONLY when creating, editing, auditing, or validating N3TX project skills."
```

## Validation Checklist

Before merging skill updates:

1. Every `SKILL.md` has frontmatter `name`, `description`, and `argument-hint`.
2. `name` exactly matches the parent folder.
3. Descriptions start with concrete trigger keywords, filenames, decorators, routes, or package names.
4. Narrow skills use `Use ONLY when...`.
5. Broad skills say when to prefer narrower skills.
6. Examples use current public imports from AGENTS import style (`AGENTS.md:133`).
7. Examples avoid mutable defaults unless intentionally demonstrating framework behavior.
8. Skills that duplicate route grammar cite BACKEND/FRONTEND anchors.
9. Skills that duplicate test commands cite AGENTS/FRONTEND anchors.
10. Skills that mention package internals preserve dependency graph boundaries (`AGENTS.md:123`).
11. Skills that change public N3TX behavior include docs-update reminders (`AGENTS.md:561`).
12. Skills that guide implementation include verification at schema/API/TX/UI boundaries (`.opencode/skills/n3tx-principles/SKILL.md:87`).
13. File workflows mention `FileStore`, upload/download routes, class-name download mirror, range support, and materialization (`.opencode/skills/n3tx-files/SKILL.md:30`, `.opencode/skills/n3tx-files/SKILL.md:50`, `.opencode/skills/n3tx-files/SKILL.md:88`).
14. Agent workflows mention import order and TestModel (`.opencode/skills/n3tx-agents/SKILL.md:11`, `.opencode/skills/n3tx-agents/SKILL.md:85`).
15. Frontend workflows mention schema authority and raw-fetch guardrails (`.opencode/skills/n3tx-frontend/SKILL.md:9`, `.opencode/skills/n3tx-frontend/SKILL.md:68`).
16. Framework-maintenance workflows mention docs-first, tests, package docs, and source inspection (`.opencode/skills/n3tx-framework-maintenance/SKILL.md:31`, `.opencode/skills/n3tx-framework-maintenance/SKILL.md:40`).
17. Skill updates remind maintainers that running OpenCode sessions may need restart to reload changed skills, per the user's OpenCode constraints.

## Final Propositions

1. Add an explicit skill routing/index layer first; it will improve agent performance more than adding more isolated skill content.
2. Normalize Level 1/2/3 and `ProtoModel`/`ActorModel` defaults to preserve N3TX's "zero to working, then customize" principle (`AGENTS.md:62`).
3. Treat skill files as generated/validated knowledge artifacts, not hand-maintained notes: lint them, anchor them to docs, and review drift when AGENTS/BACKEND/FRONTEND changes.
4. Promote `n3tx-files` in the catalog because files are now a first-class optional package and a security/storage boundary (`AGENTS.md:119`, `.opencode/skills/n3tx-files/SKILL.md:9`).
5. Add dedicated routing/views and theme/shell skills or significantly enrich existing frontend/method skills because those areas have become complex enough to cause implementation mistakes (`BACKEND.md:159`, `FRONTEND.md:107`, `FRONTEND.md:369`).
6. Add a shared boundary-violation recovery block so agents stop and re-align instead of patching around N3TX when encountering direct SQL, custom routes, raw fetches, or duplicated contracts.
7. Use `default_factory` in skill examples to avoid propagating Python mutable-default anti-patterns.
8. Add a secret-handling section to external integration guidance so agents do not persist provider credentials in schema-visible fields.
