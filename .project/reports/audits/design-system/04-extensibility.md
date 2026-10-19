# Design System Extensibility Audit

## Scope

This audit covers the N3TX frontend design-system subsystem as defined in the prompt:

- extension points for custom components, widgets, themes, and agent UI;
- package/import boundaries between `n3tx-core`, `n3tx-ui`, and `n3tx-agents`;
- runtime-vs-visual separation;
- HTML shell composition and static namespace assumptions;
- how new frontend features plug into the current architecture;
- sustainability signals from recent git history.

Methodology:

- read the required cross-cutting docs first, then the frontend docs, then every listed core file and usage site; citations below reference exact file lines;
- inspected recent history with `git log --follow` on representative files and the frontend/static subtree;
- did not modify any source files.

## Executive Assessment

The subsystem has a strong architectural center: `n3tx-core` owns the non-visual runtime, `Component` is the shared substrate, `n3tx-ui` layers visual primitives on top, and `n3tx-agents` adds agent-specific visual extensions without changing the runtime contract. That core split is explicitly documented and mostly reflected in the codebase, especially around schema-driven rendering, `Component` lifecycle hooks, `ListElement` child resolution, widget registration, and stream subclassing. [`/workspace/FRONTEND.md:19`](../FRONTEND.md#L19) [`/workspace/FRONTEND.md:103`](../FRONTEND.md#L103) [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:179`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L179) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:173`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L173) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:22`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js#L22) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:15`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L15)

The design-system is therefore extensible in the additive sense that N3TX values: many customizations are hooks, registrations, schema hints, or subclass overrides rather than forks. [`/workspace/docs/CORE.md:109`](../docs/CORE.md#L109) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L58) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:100`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js#L100)

But the integration model is also materially brittle in four places:

- package-local import paths are not actually self-contained; many files assume the production merged static namespace rather than resolvable package-local relative imports, especially in `n3tx-agents`; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L1) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js#L17) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L17) [`/workspace/FRONTEND.md:23`](../FRONTEND.md#L23)
- HTML shells must remember to include both theme CSS files, optional vendor scripts, and the theme utility module; the runtime does not enforce that contract; [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17`](../packages/n3tx-core/src/n3tx_core/static/utils/theme.js#L17) [`/workspace/examples/core/static/index.html:7`](../examples/core/static/index.html#L7) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/login.html:7`](../packages/n3tx-ui/src/n3tx_ui/static/login.html#L7)
- several framework files contain app-specific styling or duplicated styling payloads, weakening runtime/visual purity and increasing maintenance cost; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:758`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css#L758) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:367`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js#L367) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.css:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.css#L1)
- docs, examples, and tests are not fully aligned with the current implementation, which makes extension safer for maintainers who already know the system than for newcomers tracing boundaries for the first time. [`/workspace/docs/frontend/ARCHITECTURE.md:357`](../docs/frontend/ARCHITECTURE.md#L357) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/example.html:265`](../packages/n3tx-ui/src/n3tx_ui/static/example.html#L265) [`/workspace/tests/frontend/tests/components/ntx-topbar.test.js:148`](../tests/frontend/tests/components/ntx-topbar.test.js#L148) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:135`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js#L135)

Overall judgment:

| Dimension | Score | Notes |
|---|---:|---|
| Additive customization | 8/10 | Strong hook surfaces in `Component`, `ListElement`, `Formidable`, widget registry, router tag resolution, and stream subclassing. [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:191`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L191) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L177) |
| Boundary traceability | 6/10 | Conceptually clear in docs, but obscured by merged-static-path assumptions and duplicated CSS/embed patterns. [`/workspace/FRONTEND.md:103`](../FRONTEND.md#L103) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L17) |
| Package hygiene | 5/10 | Dependency graph is acyclic on paper, but source imports are not package-local enough to be self-explanatory. [`/workspace/FRONTEND.md:108`](../FRONTEND.md#L108) [`/workspace/tests/frontend/vitest.config.js:18`](../tests/frontend/vitest.config.js#L18) |
| Theme extensibility | 6/10 | Token-based and variable-driven, but shell wiring is manual and duplicated. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`](../packages/n3tx-ui/src/n3tx_ui/static/light-theme.css#L1) [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/theme.js:8`](../packages/n3tx-core/src/n3tx_core/static/utils/theme.js#L8) |
| Sustainability | 6/10 | Recent history trends positive, but current drift between docs/examples/tests raises long-term entropy risk. [`/workspace/tests/frontend/vitest.config.js:18`](../tests/frontend/vitest.config.js#L18) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/example.html:1`](../packages/n3tx-ui/src/n3tx_ui/static/example.html#L1) |

## Reading Inventory

### Core docs loaded first

| File | Why it matters |
|---|---|
| `/workspace/docs/ARCHITECTURE.md` | Core extension philosophy, mixin/extensibility model, overall separation rules. [`/workspace/docs/ARCHITECTURE.md:746`](../docs/ARCHITECTURE.md#L746) |
| `/workspace/docs/CORE.md` | Schema contract from backend to frontend and `__ui__` propagation. [`/workspace/docs/CORE.md:109`](../docs/CORE.md#L109) |
| `/workspace/FRONTEND.md` | Explicit runtime-vs-visual split and static namespace merge model. [`/workspace/FRONTEND.md:19`](../FRONTEND.md#L19) [`/workspace/FRONTEND.md:115`](../FRONTEND.md#L115) |
| `/workspace/docs/frontend/ARCHITECTURE.md` | Frontend runtime layering and current-status caveats. [`/workspace/docs/frontend/ARCHITECTURE.md:17`](../docs/frontend/ARCHITECTURE.md#L17) [`/workspace/docs/frontend/ARCHITECTURE.md:352`](../docs/frontend/ARCHITECTURE.md#L352) |
| `/workspace/docs/frontend/COMPONENTS.md` | Component hierarchy and extension semantics. [`/workspace/docs/frontend/COMPONENTS.md:21`](../docs/frontend/COMPONENTS.md#L21) |
| `packages/n3tx-ui/docs/components.md` | Concrete extension points and gotchas. [`/workspace/packages/n3tx-ui/docs/components.md:157`](../packages/n3tx-ui/docs/components.md#L157) |
| `packages/n3tx-ui/docs/formidable.md` | Form layout cache, attached methods, and widget contracts. [`/workspace/packages/n3tx-ui/docs/formidable.md:15`](../packages/n3tx-ui/docs/formidable.md#L15) |
| `packages/n3tx-ui/docs/widgets.md` | Widget registry contract and extension API. [`/workspace/packages/n3tx-ui/docs/widgets.md:37`](../packages/n3tx-ui/docs/widgets.md#L37) |

### Core files audited

All prompt-listed core files were read, including every file under the listed `components/*` and `widgets/*` globs.

| Area | Files reviewed |
|---|---|
| Runtime base | `Component.js`, `theme.js`, `Toast.js`, `Permissions.js`, `Logging.js`, `config.js` |
| Themes & shell assets | `dark-theme.css`, `light-theme.css`, `auth.css`, `example.html`, `login.html`, `register.html` |
| UI components | `NTTElement.js`, `ListElement.js`, `ntx-item.js`, `ntx-list.js`, `ntx-table.js`, `ntx-row.js`, `ntx-method.js`, `ntx-stream.js`, `ntx-router.js`, `ntx-modal.js`, `ntx-ref-picker.js`, `ntx-sidebar.js`, `ntx-topbar.js`, `ntx-profile.js`, `ntx-user.js`, and all listed CSS files |
| Widgets | `Widget.js`, `registry.js`, `index.js`, all built-ins, `JsonTree.js`, `widgets.css`, `json-tree.css` |
| Agent UI | `ntx-stream-agent.js`, `ntx-agent-live.js`, `ntx-chat.js`, `ntx-agent.js`, and all listed CSS files |

### Usage sites and tests reviewed

| Category | Files reviewed |
|---|---|
| Example/app shells | `examples/core/static/index.html`, `examples/actors/static/index.html`, `examples/grants/static/index.html`, `examples/pygentic/static/index.html`, `apps/veille/static/index.html`, `packages/n3tx-core/src/n3tx_core/static/schema.html` |
| Frontend tests | `tests/frontend/vitest.config.js`, `tests/frontend/tests/components/ntx-item.test.js`, `ntx-topbar.test.js`, `ntx-sidebar.test.js`, `tests/frontend/tests/generators/form.test.js`, `tests/frontend/tests/integration/form-entity-binding.test.js`, `tests/frontend/tests/e2e/form-rendering-unit.spec.js`, `tests/frontend/tests/e2e/css-and-theming-unit.spec.js` |

## Architectural Baseline

### Intended split

The intended split is explicit:

- `n3tx-core` owns runtime, transport, entity registry, `Component`, and shared utils; [`/workspace/FRONTEND.md:19`](../FRONTEND.md#L19) [`/workspace/FRONTEND.md:41`](../FRONTEND.md#L41)
- `n3tx-ui` owns visual components, forms, widgets, and themes; [`/workspace/FRONTEND.md:21`](../FRONTEND.md#L21) [`/workspace/FRONTEND.md:56`](../FRONTEND.md#L56)
- `n3tx-agents` owns agent-specific visual extensions; [`/workspace/FRONTEND.md:83`](../FRONTEND.md#L83)
- runtime static directories are merged into one browser-visible namespace, so the browser does not see package boundaries directly. [`/workspace/FRONTEND.md:23`](../FRONTEND.md#L23) [`/workspace/FRONTEND.md:115`](../FRONTEND.md#L115)

ASCII dependency model:

```text
Python/backend schema contract
        |
        v
n3tx-core/static/core
  - Actor / Matrix / TX
  - NTT dynamic classes
  - Component base
  - config + utils
        |
        +--------------------+
        |                    |
        v                    v
n3tx-ui/static          n3tx-agents/static
  - visual components     - agent visual extensions
  - forms                 - richer stream renderers
  - widgets               - chat / live panels / agent item
  - themes
```

That matches the repository-level philosophy that the frontend should consume backend contracts dynamically, and that packages should remain acyclic. [`/workspace/docs/CORE.md:109`](../docs/CORE.md#L109) [`/workspace/FRONTEND.md:108`](../FRONTEND.md#L108)

### Actual substrate

The actual substrate is also coherent:

- `Component` centralizes actor identity, schema/proto binding, ref resolution, adaptive display, stylesheet adoption, and the `prerender()`/`render()` split. [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:46`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L46) [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:309`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L309) [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:454`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L454)
- `NTTElement` and `ListElement` are the primary visual extension seams over that runtime base. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:21`](../packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js#L21) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:21`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L21)
- `Formidable` reads schema once and turns it into forms, labels, widgets, nested lists, and attached methods. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L58) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:195`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L195)
- `NTTStream` and `NTTStreamAgent` extend method invocation into progressive streaming and typed agent event rendering. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:24`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js#L24) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:15`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L15)

This is the subsystem's strongest design property: almost every extensibility point is a small surface over a stable shared runtime.

## Dependency Graph and Boundary Quality

### What is clean
`Component` is a good boundary root because it exposes exactly the concerns that visual subclasses need and little else:

- schema binding through `define()` and `definedCallback()`; [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:179`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L179)
- reactive display switching through `displayModeChanged()` and `scheduleRender()`; [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:341`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L341) [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:362`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L362)
- pre-schema DOM via `prerender()`; [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:445`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L445)
- stylesheet sharing via constructable sheet caching; [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:17`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L17) [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:270`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L270)

That means new visual features usually do not need new runtime APIs; they subclass, override, or compose.

`ListElement` is especially strong as an additive boundary:

- it resolves child tags in a cascading order: template, attribute, subclass override, schema renderer hint, then framework default; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:173`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L173) [`/workspace/docs/frontend/COMPONENTS.md:307`](../docs/frontend/COMPONENTS.md#L307)
- it separately resolves child display size, so changing layout does not require changing data flow; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:183`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L183)
- it opens create flows by stamping the same child tag inside `NTTModal`, preserving one rendering primitive for both browsing and creation. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:133`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L133)

`NTTRouter` is also well-factored:

- shells can declaratively mount a home view via slots; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:27`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js#L27)
- runtime navigation mounts an arbitrary resolved tag and attrs; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:71`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js#L71) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:100`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js#L100)
- route resolution ultimately depends on backend schema `ui.renderer` hints, keeping backend authoritative. [`/workspace/docs/CORE.md:144`](../docs/CORE.md#L144) [`/workspace/docs/frontend/COMPONENTS.md:758`](../docs/frontend/COMPONENTS.md#L758)

### What is not clean
The biggest boundary weakness is import locality.

In `n3tx-agents`, multiple files import as if they live in the unified static root rather than the package-local filesystem:

```javascript
import { NTTStream } from './ntx-stream.js';
import { showToast } from '../utils/Toast.js';
```

[`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L1) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:2`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L2)

The same pattern recurs in other agent UI files:

- `ntx-agent-live.js` imports `./ntx-stream.js`, `../core/NTT.js`, and `../widgets/JsonTree.js`; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js#L17) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:19`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js#L19)
- `ntx-chat.js` imports `./ntx-stream.js`, `../core/NTT.js`, and `../core/transport/HTTP.js`; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L17) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:19`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L19)
- `ntx-agent.js` imports `./ntx-item.js` and `../utils/Permissions.js`; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:19`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js#L19) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:20`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js#L20)

Those relative imports do not describe the package boundary. They describe the post-merge URL namespace that the docs say is created at runtime. [`/workspace/FRONTEND.md:23`](../FRONTEND.md#L23) [`/workspace/FRONTEND.md:125`](../FRONTEND.md#L125)

That makes the package graph understandable only if the reader already knows the deployment trick.

### Test harness evidence of boundary leakage

The Vitest config confirms this. It has to emulate the merged namespace with alias rewrites from test-relative imports into separate package static directories. [`/workspace/tests/frontend/vitest.config.js:4`](../tests/frontend/vitest.config.js#L4) [`/workspace/tests/frontend/vitest.config.js:18`](../tests/frontend/vitest.config.js#L18)

But the alias layer is also partial:

- it aliases generic `core/`, `utils/`, `components/`, `widgets/`, `generators/`, and `vendor/`; [`/workspace/tests/frontend/vitest.config.js:19`](../tests/frontend/vitest.config.js#L19) [`/workspace/tests/frontend/vitest.config.js:27`](../tests/frontend/vitest.config.js#L27)
- then adds only one agent-specific exception for `components/ntx-chat.js`. [`/workspace/tests/frontend/vitest.config.js:28`](../tests/frontend/vitest.config.js#L28) [`/workspace/tests/frontend/vitest.config.js:29`](../tests/frontend/vitest.config.js#L29)

That is not a stable abstraction. It is a compatibility shim around a source layout whose imports are already speaking in merged-root language.

### Resulting boundary score

The package DAG is acyclic in intent and in docs, but the source-level mental model is weaker than it should be:

```text
Desired: package-local imports reflect package-local ownership
Actual: source imports often reflect deployed merged-static layout
Effect: readers must understand runtime mounting to understand source boundaries
```

That is manageable for framework maintainers, but it is a real barrier for external extension authors.

## Runtime vs Visual Separation

### Where separation works well

The runtime-vs-visual split is real and valuable.

`n3tx-core` contains the non-visual substrate:
- `config.js` defines API URLs, debug switches, and the event constant table; [`/workspace/packages/n3tx-core/src/n3tx_core/static/config.js:2`](../packages/n3tx-core/src/n3tx_core/static/config.js#L2)
- `Permissions.js` is policy evaluation against schema access contracts, not a UI component; [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:17`](../packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js#L17)
- `Toast.js` is UI-adjacent but still global infra, not entity rendering; [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Toast.js:21`](../packages/n3tx-core/src/n3tx_core/static/utils/Toast.js#L21)
- `Component.js` does not know about fields, widgets, or specific models; it knows about rendering lifecycle and actor identity. [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:67`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L67) [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:454`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L454)

`n3tx-ui` layers visible opinions:

- `NTTElement` adds entity-oriented rendering and validation surfacing; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:63`](../packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js#L63) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:134`](../packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js#L134)
- `NTTItem` adds visual size methods, card actions, reply UI, and display templates; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:228`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js#L228) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:592`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js#L592)
- `Formidable` owns HTML form generation and list field rendering; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L58)
- widgets own specialized field display/edit/list behavior; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:14`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js#L14)

`n3tx-agents` then adds vertical specializations without redefining the runtime:

- `NTTStreamAgent` is just `NTTStream` plus richer event handlers; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:4`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L4)
- `NTTAgentLive` and `NTTChat` are streaming panels rather than new data transport systems; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:21`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js#L21) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:25`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L25)
- `NtxAgent` is an `NTTItem` specialization, not a special-case runtime path. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:24`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js#L24)

That is exactly the kind of additive vertical extension the project principles ask for.

### Where separation blurs

Two patterns weaken the split.

First, framework CSS contains app-specific content.

`ntx-item.css` includes a large block of `.grant-*` and `.run-*` styles for app-specific subclasses inside the shared framework stylesheet. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:758`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css#L758) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:913`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css#L913)

That is design-system leakage in the wrong direction: the framework is carrying application visual baggage.

Second, several agent components duplicate styling between inline JS strings and standalone CSS files:

- `ntx-stream-agent.js` contains `agentStyles`; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:244`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L244)
- `ntx-stream-agent.css` contains the same visual domain in stylesheet form; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css#L1)
- `ntx-agent-live.js` embeds a full `styles` string; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:292`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js#L292)
- `ntx-agent-live.css` separately defines the same component domain; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css#L1)
- `ntx-chat.js` and `ntx-agent.js` do the same. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:244`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L244) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:367`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js#L367)

That style duplication is sustainable only while a small number of maintainers remember which source is authoritative.

## Extension Points

### 1. Component subclassing

The component extension story is strong.

Primary hooks:

- override `styles`; [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:258`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L258)
- override `prerender()` for stable shell DOM before schema arrival; [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:454`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L454)
- override `render()` or narrower methods like `xs()`, `sm()`, `md()` in `NTTItem`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:232`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js#L232) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:380`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js#L380)
- override `update(prev,next)` for surgical DOM patching; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:55`](../packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js#L55) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:220`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L220)
- override `definedCallback()` for schema-ready startup behavior. [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:191`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L191)

The best proof is `NtxAgent`: it extends `NTTItem`, overrides only size/section renderers, and reuses the base event binding because it keeps the same `.edit-btn`, `.delete-btn`, and `.cancel-btn` class contract. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:24`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js#L24) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:149`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js#L149)

That is a notably good extensibility pattern: structure changes, event semantics stay inherited.

### 2. List child customization

`ListElement.createChild()` is a major extension seam because it lets custom list compositions choose rendering granularity without touching data loading. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:193`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L193)

Options, from most explicit to most implicit:

| Mechanism | Where defined | Why it is good |
|---|---|---|
| `<template item-template>` | Host HTML | Full control in shell composition. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:199`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L199) |
| `item-tag="..."` | Host HTML | Fast override with no subclass. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L177) |
| `childTag` getter | JS subclass | Good for reusable custom lists. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js:34`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js#L34) |
| `schema.ui.renderer.item` | Backend schema | Keeps backend authoritative. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L177) |
| framework default `ntx-item` | Built-in fallback | Zero-config baseline. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:180`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L180) |

This is one of the subsystem's clearest successes.

### 3. Widget registration

The widget system is intentionally composable.

Registry contract:

- `registerWidget(name, instance)` stores by `ui.widget`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:22`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js#L22)
- `getWidgetForField(fieldSchema)` returns `{widget, config}`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:31`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js#L31)
- `index.js` registers built-ins but also re-exports the extension API. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js:19`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js#L19) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js:33`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js#L33)

`Formidable` then dispatches widget-first before type fallback, so custom renderers stay additive rather than invasive. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:212`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L212) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:289`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L289)

The widget base class also separates three contexts cleanly:

- `display()` returns DOM nodes for detail contexts; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:15`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js#L15)
- `edit()` returns DOM nodes for forms; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:25`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js#L25)
- `list()` returns strings for compact list/table rendering. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:42`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js#L42)

That split is unusually practical because it maps directly onto N3TX's three major visual contexts.

### 4. Theme extension

Theme extension is variable-based rather than component-override-based.

- `dark-theme.css` defines the global token set, resets, typography, base controls, and global ambient layout; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:11`](../packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css#L11) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:109`](../packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css#L109)
- `light-theme.css` overrides only CSS custom properties under `[data-theme="light"]`, so component CSS continues to work through `var()` references; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`](../packages/n3tx-ui/src/n3tx_ui/static/light-theme.css#L1) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`](../packages/n3tx-ui/src/n3tx_ui/static/light-theme.css#L11)
- `theme.js` only flips `document.documentElement.dataset.theme` and persists to localStorage. [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17`](../packages/n3tx-core/src/n3tx_core/static/utils/theme.js#L17)

That is a good additive model because a new theme can be mostly token override.

The limitation is distribution: every shell must include both theme files manually. More on that below.

### 5. Agent stream extension

`NTTStreamAgent` is a strong extensibility seam because it converts generic stream envelopes into semantic UPPERCASE hooks.

Handlers include:

- `THINKING`; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L17)
- `TOOL_CALL`; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:30`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L30)
- `TOOL_RESULT`; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:48`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L48)
- `TEXT`; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:63`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L63)
- `DONE`, `STREAM_END`, and `STREAM_ERROR`. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:77`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L77) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:95`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L95) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:102`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L102)

This lets downstream agent views customize semantics without re-implementing transport or schema loading.

## Data Contracts at Boundaries

### Backend-to-frontend contract

The contract remains schema-first, which is the subsystem's central strength.

`Formidable`, `NTTItem`, `ListElement`, and `NTTRouter` all derive behavior from schema fields rather than local config copies:

- `Formidable` uses `schema.properties`, `ui.field_order`, `ui.groups`, field widgets, and attached method metadata; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L13) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:107`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L107)
- `ListElement` uses `schema.ui.renderer.item`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L177)
- `NTTMethod` uses `schema.methods[method]`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:82`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js#L82)
- `NTTStream` relies on streaming metadata and method names; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:43`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js#L43)
- `Permissions.canAction()` evaluates serialized ABAC rules from schema access objects, including composite rules and OWNER checks. [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:99`](../packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js#L99) [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:157`](../packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js#L157)

This means frontend features are usually plugged in by enriching schema rather than duplicating config in JS.

### HTML shell-to-runtime contract

There is also a second, less formal contract: the HTML shell must import the right static assets.

Most shells manually include:

- `dark-theme.css`; [`/workspace/examples/core/static/index.html:7`](../examples/core/static/index.html#L7)
- `light-theme.css`; [`/workspace/examples/core/static/index.html:8`](../examples/core/static/index.html#L8)
- optional vendor scripts like `marked.min.js` and `ansi_up.min.js`; [`/workspace/examples/core/static/index.html:20`](../examples/core/static/index.html#L20) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js#L17) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/ConsoleWidget.js:17`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/ConsoleWidget.js#L17)
- `utils/theme.js`; [`/workspace/examples/core/static/index.html:56`](../examples/core/static/index.html#L56)
- module imports for the components actually used on the page. [`/workspace/examples/core/static/index.html:81`](../examples/core/static/index.html#L81)

That shell contract is powerful but fragile because it is manual.

### Component-internal contracts

Some extension contracts are implicit rather than formalized:

- `NTTItem`'s event binding expects specific class names like `.edit-btn`, `.cancel-btn`, `.delete-btn`, `.show-more-btn`, and `.reply-input-box`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:629`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js#L629)
- widgets in edit mode must expose an editable node that can carry `data-key` and `data-type`; `Formidable` stamps those attributes onto the first input-like element. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:225`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L225)
- `NTTMethod` layout variants are driven by `layout`, `icon`, `count-field`, and `button-label` attributes, whether they came from schema or ad hoc markup. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:27`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js#L27) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:141`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js#L141)

These implicit contracts work, but they are more discoverable in source than in docs.

## HTML Shell Composition

### Good patterns

Production/example shells are compositional and declarative.

Typical structure:

```html
<ntx-topbar></ntx-topbar>
<ntx-sidebar router="main">...</ntx-sidebar>
<div class="page">
  <ntx-router name="main" hash>
    <ntx-list model="Product" allow-create></ntx-list>
  </ntx-router>
</div>
```

[`/workspace/examples/core/static/index.html:60`](../examples/core/static/index.html#L60) [`/workspace/examples/core/static/index.html:66`](../examples/core/static/index.html#L66)

This is a good shell API:

- the topbar is standalone and optional; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:54`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js#L54)
- the sidebar can derive navigation from child templates; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:85`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js#L85)
- the router can hold arbitrary home content and mount arbitrary dynamic views. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:27`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js#L27) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:100`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js#L100)

The shells in `examples/grants`, `examples/pygentic`, and `apps/veille` demonstrate that the same primitives can support very different product surfaces without changing the framework core. [`/workspace/examples/grants/static/index.html:65`](../examples/grants/static/index.html#L65) [`/workspace/examples/pygentic/static/index.html:61`](../examples/pygentic/static/index.html#L61) [`/workspace/apps/veille/static/index.html:219`](../apps/veille/static/index.html#L219)

### Weak patterns

The shell contract is still too manual.

Evidence:

- every shell repeats long `modulepreload` lists; [`/workspace/examples/core/static/index.html:24`](../examples/core/static/index.html#L24) [`/workspace/examples/grants/static/index.html:25`](../examples/grants/static/index.html#L25)
- every shell repeats CSS preload lists; [`/workspace/examples/core/static/index.html:10`](../examples/core/static/index.html#L10) [`/workspace/examples/pygentic/static/index.html:10`](../examples/pygentic/static/index.html#L10)
- every shell repeats component imports in module scripts; [`/workspace/examples/core/static/index.html:81`](../examples/core/static/index.html#L81) [`/workspace/examples/actors/static/index.html:84`](../examples/actors/static/index.html#L84)

This makes customization possible, but it also makes shells easy to drift.

The sharpest example is `example.html`, which is explicitly listed in the prompt and clearly represents an obsolete architecture:

- it brands itself `NTTTX Framework - Demo v2.1.0`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/example.html:7`](../packages/n3tx-ui/src/n3tx_ui/static/example.html#L7) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/example.html:154`](../packages/n3tx-ui/src/n3tx_ui/static/example.html#L154)
- it imports `./core/registrar.js`, `PTT`, and `remote`, which are not part of the current documented split model; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/example.html:265`](../packages/n3tx-ui/src/n3tx_ui/static/example.html#L265) [`/workspace/docs/frontend/ARCHITECTURE.md:357`](../docs/frontend/ARCHITECTURE.md#L357)
- frontend docs already warn that `example.html` is broken against the current architecture. [`/workspace/docs/frontend/ARCHITECTURE.md:357`](../docs/frontend/ARCHITECTURE.md#L357)

So the subsystem ships both a modern shell pattern and a stale shell artifact inside the shared UI package.

## Theme System and the `light-theme.css` Investigation

### What exists today

`light-theme.css` does exist. It is not missing from the repository.

Evidence:

- the file is present and defines light-theme token overrides. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`](../packages/n3tx-ui/src/n3tx_ui/static/light-theme.css#L1)
- core/example shells include it. [`/workspace/examples/core/static/index.html:8`](../examples/core/static/index.html#L8) [`/workspace/examples/actors/static/index.html:8`](../examples/actors/static/index.html#L8) [`/workspace/examples/grants/static/index.html:8`](../examples/grants/static/index.html#L8) [`/workspace/examples/pygentic/static/index.html:8`](../examples/pygentic/static/index.html#L8) [`/workspace/apps/veille/static/index.html:8`](../apps/veille/static/index.html#L8)
- auth pages include it too. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/login.html:8`](../packages/n3tx-ui/src/n3tx_ui/static/login.html#L8) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/register.html:8`](../packages/n3tx-ui/src/n3tx_ui/static/register.html#L8)
- `schema.html` includes it. [`/workspace/packages/n3tx-core/src/n3tx_core/static/schema.html:8`](../packages/n3tx-core/src/n3tx_core/static/schema.html#L8)

So the narrow hypothesis “there is no `light-theme.css`” is false.

### Why the integration still feels brittle

The real issue is distribution, not existence.

`theme.js` does not inject stylesheets. It only stores a theme name and flips `document.documentElement.dataset.theme`. [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17`](../packages/n3tx-core/src/n3tx_core/static/utils/theme.js#L17) [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/theme.js:28`](../packages/n3tx-core/src/n3tx_core/static/utils/theme.js#L28)

Therefore a light theme only works if the shell remembered to load both:

- `dark-theme.css`; and
- `light-theme.css`.

Nothing in the runtime validates that requirement.

That means the effective contract is:

```text
Theme toggle works only if shell authors include:
1. dark-theme.css
2. light-theme.css
3. utils/theme.js
```

The subsystem already contains a counterexample. `example.html` loads only `dark-theme.css` and no `light-theme.css`, and it does not import `utils/theme.js`. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/example.html:8`](../packages/n3tx-ui/src/n3tx_ui/static/example.html#L8) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/example.html:261`](../packages/n3tx-ui/src/n3tx_ui/static/example.html#L261)

So the theme system is functional but shell-fragile.

### Additional theme-system findings

- `dark-theme.css` is the authoritative base theme and includes resets, fonts, base controls, and layout primitives, not just tokens. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:3`](../packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css#L3) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:103`](../packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css#L103)
- `light-theme.css` is purely override-oriented and therefore depends on `dark-theme.css` being loaded first. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`](../packages/n3tx-ui/src/n3tx_ui/static/light-theme.css#L1)
- component CSS consistently references variables, which is good for future theming. Example: topbar, modal, list, table, and agent CSS all defer to tokens. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css:16`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css#L16) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.css:28`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.css#L28) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css:11`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css#L11)

Net: the theming architecture is good, the shell integration is brittle.

## Agent UI Extension Model

### The good news

Agent UI is architecturally additive.

It does not replace existing components; it stacks on top of them:

- `NTTStream` handles transport and generic stream lifecycle; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:43`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js#L43)
- `NTTStreamAgent` adds semantic event rendering; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:15`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L15)
- `NTTAgentLive` builds a live activity monitor over that; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:21`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js#L21)
- `NTTChat` builds a conversational shell over that; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:25`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L25)
- `NtxAgent` specializes item rendering and embeds `ntx-agent-live` in its own activity section. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:304`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js#L304)

This is the right vertical layering.

### The bad news

The import and style strategies are not equally mature.

Problems:

- source imports assume merged-root resolution rather than package-local ownership; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L17)
- CSS exists both inline and in separate files; [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:244`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L244) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css#L1)
- agent docs are slightly inconsistent about scope: `FRONTEND.md` first says `n3tx-agents` owns `ntx-chat.js` only, then later documents `ntx-stream-agent` and `ntx-agent-live` as first-class agent UI pieces. [`/workspace/FRONTEND.md:104`](../FRONTEND.md#L104) [`/workspace/FRONTEND.md:229`](../FRONTEND.md#L229)

So agent UI is conceptually additive, but operationally less polished than the base UI layer.

## What Is Easy to Change

| Easy change | Why |
|---|---|
| Swap entity item renderer | Use `item-tag`, `childTag`, template stamping, or `schema.ui.renderer.item`. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L177) |
| Change per-model detail view | Set `schema.ui.renderer.detail`, let router mount a different tag. [`/workspace/docs/frontend/COMPONENTS.md:758`](../docs/frontend/COMPONENTS.md#L758) |
| Add a field widget | `registerWidget()` and add `ui.widget` in schema. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:22`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js#L22) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:212`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L212) |
| Add a custom method UI | Expose backend method, let `NTTMethod` or `NTTStream` render from schema; attach via `ui.attach_to` if needed. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:47`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js#L47) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:90`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L90) |
| Add agent-specific stream view | Subclass `NTTStreamAgent` and implement UPPERCASE handlers. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:15`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L15) |
| Create shell-level navigation | Compose `ntx-topbar`, `ntx-sidebar`, `ntx-router`, and route templates. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:13`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js#L13) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:27`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js#L27) |
| Add a light/dark token variant | Extend CSS variable overrides, no component rewrite needed. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`](../packages/n3tx-ui/src/n3tx_ui/static/light-theme.css#L11) |

## What Is Hard to Change

| Hard change | Why it is hard |
|---|---|
| Make packages independently consumable in source form | Current imports assume merged static paths, especially in `n3tx-agents`. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js#L17) |
| Ship a new shell without missing a dependency | Shells must manually include theme CSS, theme utility, optional vendor scripts, and used modules. [`/workspace/examples/core/static/index.html:7`](../examples/core/static/index.html#L7) [`/workspace/examples/core/static/index.html:20`](../examples/core/static/index.html#L20) [`/workspace/examples/core/static/index.html:81`](../examples/core/static/index.html#L81) |
| Re-theme auth flows consistently | reusable `auth.css` exists, but shells currently duplicate styles inline. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`](../packages/n3tx-ui/src/n3tx_ui/static/auth.css#L1) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/login.html:11`](../packages/n3tx-ui/src/n3tx_ui/static/login.html#L11) |
| Keep agent visual styles consistent | inline JS styles and standalone CSS files duplicate responsibility. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:292`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js#L292) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css#L1) |
| Remove application leakage from the design system | shared CSS already contains grant/run-specific selectors. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:758`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css#L758) |
| Trust docs/tests as extension guides | multiple docs/tests lag or conflict with implementation. [`/workspace/tests/frontend/tests/components/ntx-topbar.test.js:148`](../tests/frontend/tests/components/ntx-topbar.test.js#L148) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:135`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js#L135) |

## Special Investigation: Import Paths and Brittle Integration

### Finding

Yes: the current import-path model is brittle.

Not because `light-theme.css` is absent, but because source imports, app shells, docs, and tests all rely on a runtime/static merge trick that is only partially encoded in each place.

### Evidence chain

1. Docs say production merges static dirs into one namespace. [`/workspace/FRONTEND.md:23`](../FRONTEND.md#L23) [`/workspace/FRONTEND.md:117`](../FRONTEND.md#L117)

2. Agent component imports assume that merged namespace rather than package-local structure. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L17) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L1)

3. Example shells also import from the merged root, e.g. `./components/...`, `./core/...`, `./widgets/...`, regardless of package ownership. [`/workspace/examples/grants/static/index.html:43`](../examples/grants/static/index.html#L43) [`/workspace/examples/grants/static/index.html:58`](../examples/grants/static/index.html#L58)

4. Tests emulate this with alias rewrites rather than consuming a package-local public import surface. [`/workspace/tests/frontend/vitest.config.js:18`](../tests/frontend/vitest.config.js#L18)

5. The alias file itself exposes that not all cases are symmetrical, because agent component routing needs a special case. [`/workspace/tests/frontend/vitest.config.js:28`](../tests/frontend/vitest.config.js#L28)

### Consequence

This means new extension authors have to understand three import topologies at once:

- physical repository paths;
- merged static URL paths at runtime;
- test-time alias rewrites.

That is more cognitive load than the subsystem should impose.

### Related brittle points

- `example.html` is stale enough to teach the wrong import model entirely. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/example.html:265`](../packages/n3tx-ui/src/n3tx_ui/static/example.html#L265)
- `schema.html` consumes the same merged-static shell convention, reinforcing that the shell contract is implicit and repeated rather than encapsulated. [`/workspace/packages/n3tx-core/src/n3tx_core/static/schema.html:7`](../packages/n3tx-core/src/n3tx_core/static/schema.html#L7) [`/workspace/packages/n3tx-core/src/n3tx_core/static/schema.html:149`](../packages/n3tx-core/src/n3tx_core/static/schema.html#L149)

## Feature Integration Guide

### Adding a new visual component

Recommended path:

1. decide whether the feature is entity-shaped, list-shaped, method-shaped, or standalone shell UI;
2. if entity-shaped, extend `NTTElement` or `NTTItem`; if list-shaped, extend `ListElement`; if stream-shaped, extend `NTTStream` or `NTTStreamAgent`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:21`](../packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js#L21) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:21`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L21) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:5`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js#L5)
3. provide a `styles` getter and optional `prerender()` shell; [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:258`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L258) [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:454`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L454)
4. wire it into backend schema via `ui.renderer.item` or `ui.renderer.detail` if it should be selected dynamically; [`/workspace/docs/CORE.md:153`](../docs/CORE.md#L153) [`/workspace/docs/frontend/COMPONENTS.md:760`](../docs/frontend/COMPONENTS.md#L760)
5. import it in the shell that uses it and preload its CSS if desired; [`/workspace/examples/pygentic/static/index.html:49`](../examples/pygentic/static/index.html#L49) [`/workspace/examples/pygentic/static/index.html:98`](../examples/pygentic/static/index.html#L98)
6. add Vitest alias support if the component crosses package boundaries in tests. [`/workspace/tests/frontend/vitest.config.js:18`](../tests/frontend/vitest.config.js#L18)

### Adding a new widget

1. implement `display`, `edit`, `list`, and optional `validate`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:21`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js#L21)
2. register it via `registerWidget`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:22`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js#L22)
3. emit `ui.widget` and optional `ui.config` from backend schema; [`/workspace/packages/n3tx-ui/docs/widgets.md:123`](../packages/n3tx-ui/docs/widgets.md#L123)
4. ensure the edit DOM exposes a primary input-like element so `Formidable` can stamp `data-key`/`data-type`. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:225`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L225)

### Adding a new themed shell

1. include both theme CSS files; [`/workspace/examples/core/static/index.html:7`](../examples/core/static/index.html#L7)
2. include `utils/theme.js`; [`/workspace/examples/core/static/index.html:56`](../examples/core/static/index.html#L56)
3. use token references in any shell-local CSS instead of hardcoded colors. `apps/veille` mostly does this correctly. [`/workspace/apps/veille/static/index.html:61`](../apps/veille/static/index.html#L61) [`/workspace/apps/veille/static/index.html:97`](../apps/veille/static/index.html#L97)

### Adding a new agent interaction

1. expose a streaming backend method with structured events;
2. surface it through schema `methods` and `events`;
3. extend `NTTStreamAgent` if the view needs thinking/tool-call semantics; otherwise use `NTTStream`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:24`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js#L24) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:15`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L15)
4. mount the new component via shell or `ui.renderer`. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:100`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js#L100)

## Comparison With Alternatives

### Compared with a static component registry

N3TX's schema-driven renderer selection is more additive:

- renderer tags can come from backend schema; [`/workspace/docs/CORE.md:153`](../docs/CORE.md#L153)
- child tags can be selected dynamically from `$defs`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:351`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L351)
- router can mount arbitrary resolved tags from route data. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:101`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js#L101)

That aligns well with backend-authoritative contracts.

### Compared with package-local strict imports

N3TX is worse.

If packages exposed explicit public browser entrypoints and imported through those, the acyclic package graph would also be visible in source form. Today it is visible only after reading docs. [`/workspace/FRONTEND.md:108`](../FRONTEND.md#L108) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L17)

So the architecture beats monoliths on composability, but loses to stricter package-local import systems on source clarity.

## Cross-Cutting Concerns

### Permissions

The permission story is well integrated across runtime and UI:

- field visibility via `canView`; [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:71`](../packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js#L71)
- field editability via `canEdit`; [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:88`](../packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js#L88)
- model actions via `canAction`; [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:99`](../packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js#L99)
- render caching in `Formidable` keys by role, so permission-dependent layouts cache safely. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L13)

This is a positive extensibility story because security-aware UIs are derived from the same schema, not duplicated.

### Performance

The subsystem has several good low-level extensibility/sustainability choices:

- constructable stylesheet caching in `Component`; [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:17`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L17)
- render coalescing via `scheduleRender()`; [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:355`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L355)
- layout caching in `Formidable`; [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:7`](../packages/n3tx-ui/src/n3tx_ui/static/generators/form.js#L7)
- document fragments in list/table rendering. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:285`](../packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js#L285) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js:451`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js#L451)

These are good signals for extensibility because they reduce the performance tax of adding more components.

### Observability

`Logging` and `Toast` are available globally but not deeply integrated into component extension docs. [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Logging.js:30`](../packages/n3tx-core/src/n3tx_core/static/utils/Logging.js#L30) [`/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Toast.js:108`](../packages/n3tx-core/src/n3tx_core/static/utils/Toast.js#L108)

The practical result is that components use them opportunistically rather than through a shared observability contract. `NTTElement.ERROR()` is a good example. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:134`](../packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js#L134)

## Docs, Tests, and Example Alignment

### Positive alignment

The tests do cover many real extension points:

- `ntx-item.test.js` covers size methods, nested delete behavior, reply UI, and validation surfacing; [`/workspace/tests/frontend/tests/components/ntx-item.test.js:162`](../tests/frontend/tests/components/ntx-item.test.js#L162) [`/workspace/tests/frontend/tests/components/ntx-item.test.js:574`](../tests/frontend/tests/components/ntx-item.test.js#L574)
- `form.test.js` covers groups, widgets, protected fields, and list-field rendering; [`/workspace/tests/frontend/tests/generators/form.test.js:56`](../tests/frontend/tests/generators/form.test.js#L56) [`/workspace/tests/frontend/tests/generators/form.test.js:164`](../tests/frontend/tests/generators/form.test.js#L164)
- Playwright tests cover CSS variables and theme switching with both dark and light themes. [`/workspace/tests/frontend/tests/e2e/css-and-theming-unit.spec.js:13`](../tests/frontend/tests/e2e/css-and-theming-unit.spec.js#L13) [`/workspace/tests/frontend/tests/e2e/css-and-theming-unit.spec.js:160`](../tests/frontend/tests/e2e/css-and-theming-unit.spec.js#L160)

### Misalignment issues

But there is also clear drift.

The strongest example is `ntx-topbar`.

The current component renders only:

- brand;
- slot-based nav;
- auth actions.

[`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:126`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js#L126) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:139`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js#L139)

But the unit test still expects an automatic “Favorites” nav link for authenticated users. [`/workspace/tests/frontend/tests/components/ntx-topbar.test.js:148`](../tests/frontend/tests/components/ntx-topbar.test.js#L148)

That mismatch matters because tests are part of the subsystem's extension guide.

There is a similar doc inconsistency inside `FRONTEND.md`:

- one section says `n3tx-agents` owns agent-specific UI and “`ntx-chat.js` only”; [`/workspace/FRONTEND.md:104`](../FRONTEND.md#L104)
- later sections document `NTTStreamAgent`, `ntx-agent-live`, and `ntx-chat` as a broader hierarchy. [`/workspace/FRONTEND.md:229`](../FRONTEND.md#L229)

That is small drift, but it is exactly the kind of drift that makes extension boundaries harder to trace.

## Evolution Trajectory

### What recent history says

Recent history shows meaningful investment in extensibility and package separation.

| Commit | Signal | Interpretation |
|---|---|---|
| `0ff8581` | moved core Python and JS runtime to `n3tx-core` | formalized runtime ownership. |
| `de131b3` | moved UI components, widgets, and themes to `n3tx-ui` | formalized visual ownership. |
| `1f5842e` | moved agent system to `n3tx-agents` | formalized agent vertical slice. |
| `844401e` | added multi-package path aliases to Vitest | tests adapted to the package split, but via alias shims. |
| `0e0463d` | added `prerender()` to `Component` | improved extension ergonomics for shell-first components. |
| `4cf06e3` | replaced StreamActor mixin with `NTTStream/NTTStreamAgent` hierarchy | simplified stream extension around clearer UI primitives. |
| `463081c` | added string route resolution and sidebar nav | strengthened shell composition and dynamic routing. |

History source: `git log` over frontend/static directories and `--follow` on representative files. [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:445`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L445) [`/workspace/tests/frontend/vitest.config.js:18`](../tests/frontend/vitest.config.js#L18)

### File-specific trajectories

`Component.js` history is encouraging:

- performance work landed before or alongside extensibility work; `constructable stylesheets` and `render coalescing` appear in history before `prerender()`. This indicates deliberate maturation rather than random growth.

`form.js` history is similarly positive:

- widgets, object display, ref picker, enum support, stream delegation, and list-value rendering were layered onto one form generator rather than scattered into per-component logic.

`ntx-item.js` history shows healthy additive growth:

- nested delete, validation, cancel-edit, enum support, and prerender all arrived as focused incremental steps instead of rewrites.

`ntx-sidebar.js` history shows the shell system becoming more declarative:

- initial addition in `dc76046`, then route-template support in `3205d98`, then string route resolution in `463081c`.

`ntx-chat.js` and `ntx-stream-agent.js` show a more turbulent evolution:

- `ntx-chat` was added, then package-moved, then upgraded with richer tool cards, then re-based on `NTTStream/NTTStreamAgent`. That is productive churn, but still churn. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:25`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L25)

### Sustainability reading

The trajectory is sustainable if the team finishes the package-split cleanup it started.

The package move commits show the system is still in the middle phase where architecture has improved faster than shell/import ergonomics.

## Risks and Limitations

### High risk

- merged-static import assumptions hide real package boundaries; extending across packages requires hidden context. [`/workspace/FRONTEND.md:23`](../FRONTEND.md#L23) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L17)
- duplicated style sources in agent components increase drift risk. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:244`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js#L244) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css#L1)
- stale demo/example artifacts can teach obsolete architecture. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/example.html:265`](../packages/n3tx-ui/src/n3tx_ui/static/example.html#L265)

### Medium risk

- shell composition requires long manual asset lists, so features can fail by omission rather than type errors. [`/workspace/examples/core/static/index.html:10`](../examples/core/static/index.html#L10) [`/workspace/examples/core/static/index.html:24`](../examples/core/static/index.html#L24)
- framework CSS contains product-specific rules, making general-purpose cleanup harder over time. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:758`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css#L758)
- auth pages ignore reusable `auth.css`, signalling weak shell discipline. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`](../packages/n3tx-ui/src/n3tx_ui/static/auth.css#L1) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/login.html:11`](../packages/n3tx-ui/src/n3tx_ui/static/login.html#L11)

### Low risk

- token-based theme system itself is sound; the main issue is distribution. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`](../packages/n3tx-ui/src/n3tx_ui/static/light-theme.css#L11)
- core lifecycle and widget abstractions are stable and composable. [`/workspace/packages/n3tx-core/src/n3tx_core/static/core/Component.js:191`](../packages/n3tx-core/src/n3tx_core/static/core/Component.js#L191) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:12`](../packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js#L12)

## Recommendations

### 1. Make source imports reflect package ownership

Priority: highest.

Reason:

- the docs promise an understandable acyclic split; source imports should reinforce that rather than hide it behind merged-root assumptions. [`/workspace/FRONTEND.md:108`](../FRONTEND.md#L108)

Desired outcome:

- package-local browser entrypoints or explicit aliasable import roots, so package code can be read without mentally simulating the deployment merger.

### 2. Collapse duplicate CSS authorities in agent UI

Priority: high.

Reason:

- `ntx-stream-agent`, `ntx-agent-live`, `ntx-chat`, and `ntx-agent` each split style authority between JS strings and external CSS. [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:244`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js#L244) [`/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css:1`](../packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css#L1)

Desired outcome:

- one styling authority per component family.

### 3. Turn shell composition into a reusable primitive

Priority: high.

Reason:

- current shells repeat the same preload and import choreography. [`/workspace/examples/core/static/index.html:10`](../examples/core/static/index.html#L10) [`/workspace/examples/grants/static/index.html:23`](../examples/grants/static/index.html#L23)

Desired outcome:

- a canonical app shell template or generated shell manifest.

### 4. Remove application-specific CSS from framework files

Priority: medium-high.

Reason:

- grant/run selectors inside `ntx-item.css` are subsystem entropy. [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:758`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css#L758)

Desired outcome:

- app-specific component styles live with app-specific components.

### 5. Align docs and tests with current topbar/sidebar behavior

Priority: medium.

Reason:

- stale tests and mixed docs reduce extension confidence. [`/workspace/tests/frontend/tests/components/ntx-topbar.test.js:148`](../tests/frontend/tests/components/ntx-topbar.test.js#L148) [`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:135`](../packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js#L135)

Desired outcome:

- docs/tests become trustworthy extension maps instead of partial archaeology.

## Final Judgment

The N3TX design-system subsystem is architecturally promising and already quite extensible where it matters most:

- schema-driven component selection is additive;
- the runtime/visual split is conceptually correct;
- widgets, list child resolution, and stream subclassing are genuinely composable;
- recent history shows the team moving toward clearer packages and better lifecycle hooks.

But extensibility currently depends too much on insider knowledge of the merged static namespace and too little on explicit, package-local contracts.

If the team finishes the split it has already started by cleaning up imports, consolidating CSS authorities, and reducing shell duplication, this subsystem can become one of the clearest parts of N3TX.

Right now it is good at additive customization for maintainers, but only moderately good at being obvious, portable, and self-explanatory for new extension authors.
