# Design-System Architecture Audit

## Scope

- Audit target: the frontend design-system subsystem across `n3tx-core`, `n3tx-ui`, and `n3tx-agents`, including CSS architecture, token flow, styling boundaries, form/widget rendering, HTML shell composition, and runtime/visual separation.
- Audit standard: N3TX's own principles — model-driven UI, additive customization, primitives over opinions, transparent traceability, and modularity where it simplifies.
- Audit method: documentation-first review, then direct source inspection of every requested file, plus relevant usage sites and tests.

## Sources Reviewed

- Cross-cutting docs: `docs/ARCHITECTURE.md:13`, `docs/CORE.md:44`, `FRONTEND.md:17`, `docs/frontend/ARCHITECTURE.md:15`, `docs/frontend/COMPONENTS.md:21`.
- Package docs: `packages/n3tx-ui/docs/components.md:9`, `packages/n3tx-ui/docs/formidable.md:9`, `packages/n3tx-ui/docs/widgets.md:9`.
- Core runtime and utils: `packages/n3tx-core/src/n3tx_core/static/core/Component.js:23`, `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:1`, `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js:1`, `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:1`, `packages/n3tx-core/src/n3tx_core/static/utils/Logging.js:1`, `packages/n3tx-core/src/n3tx_core/static/config.js:2`.
- UI layer: all requested component, CSS, generator, widget, and HTML files under `packages/n3tx-ui/src/n3tx_ui/static/`.
- Agent UI layer: all requested component and CSS files under `packages/n3tx-agents/src/n3tx_agents/static/components/`.
- Usage sites: requested example/app HTML shells, `schema.html`, Vitest config, unit/integration/e2e tests.

## Executive Assessment

- The subsystem has a strong architectural spine: runtime and visual concerns are deliberately split, the schema is genuinely the contract, and most rendering behavior can be traced from schema field to DOM node to transport call without hidden state machines (`FRONTEND.md:19`, `FRONTEND.md:127`, `Component.js:179`, `NTTElement.js:89`, `form.js:195`).
- The best structural decision is `Component`'s constructable stylesheet cache plus additive `prerender()`/`render()` lifecycle, which creates a credible base for shared Shadow DOM styling with minimal FOUC (`Component.js:17`, `Component.js:91`, `Component.js:359`, `Component.js:455`).
- The weakest structural area is token and stylesheet discipline: the theme files define one token vocabulary, but many component and widget styles use a second vocabulary with fallback literals, causing inconsistent theming and leakage of ad hoc design decisions into component CSS (`dark-theme.css:11`, `light-theme.css:11`, `ntx-method.css:4`, `widgets.css:4`).
- A second weak area is styling boundary consistency: some components fully use external CSS files through `Component.styles`, some standalone components inject `<link>` tags, and several agent components bypass both patterns with inline CSS strings or constructable sheets, fragmenting the design-system contract (`Component.js:94`, `ntx-profile.js:9`, `ntx-agent.js:31`, `ntx-agent-live.js:34`, `ntx-chat.js:39`).
- The schema-driven form and widget pipeline is conceptually coherent and mostly aligned with the philosophy, but its caching and permission invalidation story is incomplete; layout cache keys are coarse, and there is no production caller for `Formidable.clearCache()` even though the code and docs require auth-sensitive invalidation (`form.js:13`, `form.js:617`, `Permissions.js:38`, `packages/n3tx-ui/docs/formidable.md:143`).
- HTML shells are functional but high-ceremony: every app manually composes theme links, vendor scripts, CSS preloads, and modulepreloads, which works but weakens the "zero to working, then customize" story by making shell composition verbose and repetitive (`examples/core/static/index.html:7`, `examples/actors/static/index.html:7`, `examples/grants/static/index.html:7`, `apps/veille/static/index.html:7`).
- Special investigation result: `light-theme.css` is present and non-empty at `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`; it is referenced correctly by multiple HTML shells such as `packages/n3tx-ui/src/n3tx_ui/static/login.html:8`, `examples/core/static/index.html:8`, and `packages/n3tx-core/src/n3tx_core/static/schema.html:8`, so the current problem space is not file absence but theme/token consistency.

## Overall Scorecard

| Dimension | Assessment | Notes |
|---|---|---|
| Runtime vs visual split | Strong | `n3tx-core` owns runtime; `n3tx-ui` owns visuals; agents layer is additive (`FRONTEND.md:19`, `FRONTEND.md:103`). |
| Schema-driven rendering | Strong | Forms, methods, lists, permissions, and widget dispatch all derive from schema (`docs/CORE.md:109`, `form.js:58`, `ntx-item.js:412`). |
| Token consistency | Weak | Core theme tokens and component/widget token usage diverge (`dark-theme.css:11`, `widgets.css:4`, `ntx-method.css:17`). |
| Styling boundary clarity | Mixed | `Component.styles` is clean, but agent UI and some standalone components bypass it (`Component.js:262`, `ntx-agent-live.js:34`, `ntx-chat.js:39`). |
| HTML shell ergonomics | Mixed | Explicit and transparent, but repetitive and manually curated (`examples/core/static/index.html:10`, `examples/grants/static/index.html:23`). |
| Test coverage for design system | Mixed | Good on forms/components/theme basics; weaker on agent styling and shell composition (`vitest.config.js:8`, `css-and-theming-unit.spec.js:13`). |
| Traceability | Strong | Tag -> component -> schema -> TX path remains understandable (`Component.js:183`, `NTTElement.js:89`, `ntx-method.js:102`). |
| Additive customization | Mixed-positive | Strong for custom components/widgets; weaker for shell/theming due duplicated styles and token drift (`packages/n3tx-ui/docs/components.md:159`, `packages/n3tx-ui/docs/widgets.md:84`). |

## Architecture Map

### Layering

```text
Python model
  -> JSON Schema contract
    -> NTT DynamicClass bootstrap
      -> Component / NTTElement / ListElement runtime
        -> Formidable / widgets / ntx-item / ntx-list visual renderers
          -> ntx-method / ntx-stream / agent UI specializations
```

- The contract edge is explicit: backend schema is the frontend's universal source of types, access, UI hints, renderers, and methods (`docs/CORE.md:109`, `FRONTEND.md:127`).
- The runtime edge is explicit: `Component` owns actor identity, proto resolution, ref attachment, adaptive display, and stylesheet adoption (`Component.js:46`, `Component.js:167`, `Component.js:202`, `Component.js:309`).
- The visual edge is explicit: `NTTElement`, `ListElement`, `NTTItem`, `NTTTable`, `NTTRouter`, `Formidable`, and widgets consume schema and runtime state to create HTML and subcomponents (`NTTElement.js:63`, `ListElement.js:56`, `ntx-item.js:592`, `ntx-table.js:358`, `ntx-router.js:71`, `form.js:58`).

### Import Topology

```text
n3tx-core/static/core/*
  <- imported by n3tx-ui/static/components/*
  <- imported by n3tx-agents/static/components/*

n3tx-ui/static/components/*
  <- imported by app/example HTML shells

n3tx-agents/static/components/*
  <- import core runtime directly
  <- in some cases import merged-namespace UI files by relative path
```

- The intended package dependency direction is clean: `ui` depends on `core`, `agents` depends on `core`, and there are no reverse imports documented in frontend docs (`FRONTEND.md:108`).
- The browser-level dependency model depends on merged static namespaces, not package-local file trees; agent components import `./ntx-stream.js` and `../core/NTT.js`, which only work because the server exposes a single merged `/components`, `/core`, and `/utils` namespace (`FRONTEND.md:23`, `examples/pygentic/static/index.html:49`).
- The test harness simulates that merged namespace with path aliases for core, utils, config, components, widgets, generators, and one explicit agent alias, which is enough for current tests but only partially models the full agents asset graph (`vitest.config.js:4`, `vitest.config.js:18`).

## Component Inventory

### Runtime and Shell Primitives

| Element / module | Responsibility | Structural comment |
|---|---|---|
| `Component` | Actor bridge, schema attach, ref resolution, adaptive display, stylesheet adoption | Best cross-cutting primitive in the subsystem (`Component.js:23`). |
| `theme.js` | Theme persistence and `theme-change` event | Minimal and global; assumes browser-only import context (`theme.js:8`). |
| `Toast.js` | Global feedback overlays | Theme-aware but bypasses component boundaries with injected global CSS (`Toast.js:47`, `Toast.js:52`). |
| `Permissions.js` | User identity and rule evaluation | Correctly centralizes frontend auth/view logic, but caches aggressively (`Permissions.js:17`, `Permissions.js:38`). |
| `Logging.js` | In-memory log sink | Diagnostic state is globally mutable and enabled by shipped config (`Logging.js:7`, `config.js:2`). |
| `config.js` | Frontend defaults and event constants | Production-facing defaults are dev-heavy (`config.js:2`). |

### Visual Entity Components

| Component | Responsibility | Structural comment |
|---|---|---|
| `NTTElement` | Single-entity lifecycle | Cohesive bridge from runtime updates to render hooks (`NTTElement.js:21`). |
| `ListElement` | Collection lifecycle and pagination | Good list primitive; owns create modal and selection (`ListElement.js:21`, `ListElement.js:133`). |
| `ntx-item` | Default entity renderer | Large but still centered on one concern: schema-driven entity presentation (`ntx-item.js:26`). |
| `ntx-list` | Thin list shell | Strong example of additive customization through composition (`ntx-list.js:13`). |
| `ntx-table` | Grid/table collection renderer | More complex; mixes table view, sort, inline create, and error recovery (`ntx-table.js:23`). |
| `ntx-row` | Table row renderer | Focused adapter over `NTTItem.row()` (`ntx-row.js:21`). |
| `ntx-user` | User-specific item skin | Proper model-specific visual override (`ntx-user.js:13`). |

### Interaction Components

| Component | Responsibility | Structural comment |
|---|---|---|
| `ntx-method` | Render and invoke custom methods | Clear schema-to-form-to-call pipeline (`ntx-method.js:47`, `ntx-method.js:102`). |
| `ntx-stream` | Streaming method adapter | Clean extension of `ntx-method`, though still text-centric by default (`ntx-stream.js:24`, `ntx-stream.js:43`). |
| `ntx-router` | View container | Good boundary: Router owns state, component owns DOM (`ntx-router.js:27`, `ntx-router.js:71`). |
| `ntx-modal` | Global overlay dialog | Standalone, reusable, but outside `Component` style/cache model (`ntx-modal.js:36`). |
| `ntx-ref-picker` | Add existing/create new reference entries | Strong schema/form integration, but style loading differs from `Component` (`ntx-ref-picker.js:30`, `ntx-ref-picker.js:85`). |

### App Shell Components

| Component | Responsibility | Structural comment |
|---|---|---|
| `ntx-topbar` | Brand, auth, theme toggle, nav shell | Central shell element with direct fetch and permission coupling (`ntx-topbar.js:44`, `ntx-topbar.js:107`). |
| `ntx-sidebar` | Model navigation shell | Useful but coupled to NTT bootstrapping and router route building (`ntx-sidebar.js:40`, `ntx-sidebar.js:174`, `ntx-sidebar.js:266`). |
| `ntx-profile` | Authenticated profile page | Lightweight and consistent with shell concerns (`ntx-profile.js:11`, `ntx-profile.js:26`). |

### Agent Components

| Component | Responsibility | Structural comment |
|---|---|---|
| `ntx-stream-agent` | Rich agent stream rendering | Good specialization, but duplicates CSS strategy (`ntx-stream-agent.js:4`, `ntx-stream-agent.js:246`). |
| `ntx-agent` | Agent item renderer | Rich visual specialization; bypasses external CSS file with inline constructable sheet (`ntx-agent.js:31`, `ntx-agent.js:367`). |
| `ntx-agent-live` | Standalone live activity console | Functionally strong, style-boundary inconsistent (`ntx-agent-live.js:34`, `ntx-agent-live.js:292`). |
| `ntx-chat` | Floating chat shell | Strong self-contained UX, but same CSS duplication pattern (`ntx-chat.js:39`, `ntx-chat.js:244`). |

## Structural Strengths

### 1. `Component` is a deep, useful primitive

- `Component` combines actor identity, dynamic schema binding, ref routing, adaptive display, and stylesheet adoption, so downstream components inherit real behavior instead of boilerplate (`Component.js:46`, `Component.js:167`, `Component.js:202`, `Component.js:309`).
- Styles are normalized as one or many URLs, fetched once, and reused through shared `CSSStyleSheet` objects, which is exactly the kind of primitive the project philosophy calls for (`Component.js:17`, `Component.js:94`, `Component.js:274`).
- Render coalescing is explicit and tied to stylesheet readiness, which improves correctness without hiding behavior (`Component.js:355`, `Component.js:369`).

### 2. Schema consumption is real, not cosmetic

- `Formidable` computes field order, permissions, group layout, widget dispatch, and attached methods from schema rather than hard-coded component lists (`form.js:13`, `form.js:58`, `form.js:107`, `form.js:212`).
- `NTTItem` splits attached vs standalone methods and renders them from `schema.methods`, preserving backend authority over method surface and UI metadata (`ntx-item.js:403`, `ntx-item.js:813`).
- `$ref` and array rendering use `$defs` renderer hints when present, so backend model UI hints genuinely steer nested frontend presentation (`form.js:303`, `form.js:351`, `ntx-item.js:805`).

### 3. Runtime/visual separation is mostly coherent

- Core runtime files are non-visual and reusable across UI layers, while `n3tx-ui` files focus on rendering, forms, and widgets (`FRONTEND.md:19`, `FRONTEND.md:56`).
- Agent UI is additive: `ntx-stream-agent` extends `ntx-stream`, and `ntx-agent-live` / `ntx-chat` extend streaming behavior rather than reimplementing transport (`FRONTEND.md:83`, `ntx-stream.js:5`, `ntx-stream-agent.js:4`).
- The merged namespace model is transparent in docs and mirrored in tests, which avoids magical bundler-only behavior (`FRONTEND.md:23`, `vitest.config.js:18`).

## Design Patterns in Use

### Pattern Map

| Pattern | Where used | Assessment |
|---|---|---|
| Base-class primitive | `Component`, `NTTElement`, `ListElement` | Strong; deep modules, not thin wrappers (`Component.js:23`, `NTTElement.js:21`, `ListElement.js:21`). |
| Schema-driven factory | `Formidable`, widgets, `ntx-method` | Strong; additive customization without forking runtime (`form.js:58`, `registry.js:31`, `ntx-method.js:82`). |
| Constructable stylesheet cache | `Component` | Strong for performance and Shadow DOM reuse (`Component.js:17`, `Component.js:299`). |
| Wrapper specialization | `ntx-list`, `ntx-user`, `ntx-row` | Strong when thin and focused (`ntx-list.js:13`, `ntx-user.js:13`, `ntx-row.js:21`). |
| Standalone shell component | `ntx-topbar`, `ntx-sidebar`, `ntx-modal`, `ntx-profile` | Mixed; appropriate for app shell, but style strategy diverges (`ntx-topbar.js:54`, `ntx-sidebar.js:63`, `ntx-modal.js:36`, `ntx-profile.js:11`). |
| Inline style module | agent components and some shell components | Weakest pattern; duplicates CSS boundary logic and bypasses file-based design-system composition (`ntx-agent.js:31`, `ntx-agent-live.js:34`, `ntx-chat.js:39`). |

## Token and Theme Flow

### Current flow

```text
dark-theme.css defines base tokens on :root
  + light-theme.css overrides a subset under [data-theme="light"]
    + theme.js flips document.documentElement.dataset.theme
      + components consume vars(...) inside shadow DOM CSS
```

- The base theme surface is rich and mostly coherent: surface, text, accent, semantic, border, shadow, radius, timing, glass, and gradient tokens are all defined in `dark-theme.css` (`dark-theme.css:11`).
- The light theme follows the intended override pattern by redefining only custom properties under `[data-theme="light"]`, which is structurally sound (`light-theme.css:11`, `light-theme.css:87`).
- `theme.js` is intentionally small: it reads `localStorage`, sets `document.documentElement.dataset.theme`, and broadcasts `theme-change` (`theme.js:8`, `theme.js:17`, `theme.js:29`).

### Strengths

- The `light-theme.css` investigation checks out: the file exists, is wired, and uses the right scope override model rather than redefining component CSS wholesale (`light-theme.css:1`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:8`, `packages/n3tx-core/src/n3tx_core/static/schema.html:8`).
- Components that use the canonical token family (`--surface-*`, `--text-*`, `--accent`, `--glass-*`, `--radius-*`) theme correctly under both dark and light modes (`ntx-item.css:27`, `ntx-list.css:29`, `ntx-topbar.css:16`).

### Structural weaknesses

- Several component and widget styles rely on a second token vocabulary — `--font-body`, `--font-display`, `--panel-bg`, `--panel-bg-strong`, `--line`, `--button-text`, `--accent-primary`, `--accent-strong`, `--font-mono` — that is not defined in either theme file, forcing fallback literals and weakening theme coherence (`ntx-method.css:4`, `ntx-method.css:17`, `widgets.css:4`, `widgets.css:65`, `widgets.css:101`, `dark-theme.css:11`, `light-theme.css:11`).
- `widgets.css` is the clearest example of token drift: links and blockquote accents use `--accent-primary` with hard-coded indigo fallbacks, which reintroduces a color language that the core theme explicitly replaced with teal/cyan (`widgets.css:4`, `widgets.css:65`, `widgets.css:128`, `widgets.css:151`, `dark-theme.css:27`).
- Some components fall back to typography tokens that the theme never publishes, so the real typography system is split between global Google font imports in `dark-theme.css` and local fallback stacks in components (`dark-theme.css:3`, `dark-theme.css:109`, `ntx-method.css:4`, `ntx-agent.css:7`).

### Consequence

- The design system is not token-authoritative yet; it is token-assisted. The main theme establishes direction, but many components can silently drift because they are using fallback literals instead of a closed token surface.

## Styling Boundary Analysis

### Boundary modes currently present

| Mode | Examples | Consequence |
|---|---|---|
| `Component.styles` external CSS | `ntx-item`, `ntx-list`, `ntx-table`, `ntx-row`, `ntx-router`, `ntx-method`, `ntx-stream`, `ntx-topbar`, `ntx-sidebar`, `ntx-user` | Best path; reusable, cacheable, explicit (`ntx-item.js:36`, `ntx-topbar.js:30`). |
| Standalone `<link>` injection inside shadow DOM | `ntx-profile`, `ntx-ref-picker` | Works, but bypasses constructable stylesheet cache (`ntx-profile.js:31`, `ntx-ref-picker.js:85`). |
| Standalone constructable sheet singleton | `ntx-modal` | Efficient, but separate from shared `Component` policy (`ntx-modal.js:17`, `ntx-modal.js:22`, `ntx-modal.js:123`). |
| Inline string stylesheet / local sheet | `ntx-agent`, `ntx-agent-live`, `ntx-chat` | Fragmented and duplicative; hardest to maintain (`ntx-agent.js:31`, `ntx-agent-live.js:34`, `ntx-chat.js:39`). |
| Hybrid external + inline styles | `ntx-stream-agent` | Duplicates responsibility and risks divergence (`ntx-stream-agent.js:7`, `ntx-stream-agent.js:119`, `ntx-stream-agent.js:246`). |

### What is good

- The dominant `Component.styles` path is a good architectural default because it makes per-component CSS explicit and reusable via shared `adoptedStyleSheets` (`Component.js:94`, `Component.js:299`).
- `ntx-profile` and `ntx-ref-picker` at least keep styles file-based and inspectable even though they do not extend `Component` (`ntx-profile.js:9`, `ntx-ref-picker.js:28`).

### What is bad

- `ntx-stream-agent` claims the external stylesheet via `styles()` but then appends a second inline CSS block at render time if it does not detect `.entry-thinking`, creating two styling authorities for one component (`ntx-stream-agent.js:7`, `ntx-stream-agent.js:119`, `ntx-stream-agent.js:246`).
- `ntx-agent`, `ntx-agent-live`, and `ntx-chat` each ship external `.css` files but do not import or adopt them anywhere; instead, they embed large static CSS strings in JS, making the checked-in CSS files effectively dead assets from the runtime's perspective (`ntx-agent.js:31`, `ntx-agent.js:367`, `ntx-agent.css:1`, `ntx-agent-live.js:34`, `ntx-agent-live.css:1`, `ntx-chat.js:39`, `ntx-chat.css:1`).
- This violates the subsystem's own split axis: style definitions leak back into runtime JS for agent UI, reducing inspectability and making styling changes less additive.

### Recommendation

- Standardize on one of two allowed boundaries: `Component.styles` for `Component` subclasses, or `<link rel="stylesheet">`/shared constructable sheet for standalone elements. Eliminate hybrid and inline-string-only paths.

## Form and Widget Rendering Architecture

### Strengths

- `Formidable` is stateless at the call boundary and turns schema + value into HTML strings, which preserves traceability and makes it easy for custom components to reuse (`form.js:58`, `packages/n3tx-ui/docs/formidable.md:44`).
- Widget dispatch is clean: registry lookup returns `{ widget, config }`, and the caller decides whether to use widget or type fallback (`registry.js:31`, `form.js:213`).
- Attached methods are elegantly additive: backend schema can specify `ui.attach_to`, and the renderer injects a method control after the target field without special-case component code (`form.js:69`, `form.js:90`, `packages/n3tx-ui/docs/formidable.md:130`).

### Risks and issues

- Layout cache keys are too coarse. `_getLayout()` keys only on `schema.__name__`, `mode`, and `permissions.role`, so different schema objects sharing the same model name can reuse stale layouts; the test suite explicitly clears cache between tests to prevent this exact issue (`form.js:13`, `tests/frontend/tests/generators/form.test.js:25`).
- `Permissions.init()` caches its promise forever and has no public reset API, while `Formidable.clearCache()` is only invoked in tests, not in app code, so auth changes inside a long-lived SPA session can leave stale field visibility/layout decisions (`Permissions.js:38`, `Permissions.js:67`, `form.js:617`, `functions.grep` evidence reflected by `form.js:618` and test-only callers in `tests/frontend/tests/generators/form.test.js:28`).
- `getInput()` mutates `def` when resolving `anyOf` by calling `Object.assign(def, resolveAnyOf(def))`, which means rendering can mutate schema definitions in place instead of treating them as immutable contracts (`form.js:204`, `form.js:206`).
- `getArrayInput()` is effectively dead or unfinished code: it references undefined symbols like `parent` and is not part of the primary rendering path, suggesting leftover architectural debris (`form.js:417`, `form.js:422`).

### Widget-system observations

- The widget base class is intentionally small and extensible (`Widget.js:12`).
- Built-ins cover common cases without hardcoding widget logic into `Formidable` or `NTTItem`, which aligns with the primitives philosophy (`index.js:22`, `index.js:33`).
- Markdown and console widgets degrade gracefully when optional vendor libraries are absent, which is a good boundary behavior (`MarkdownWidget.js:17`, `ConsoleWidget.js:17`).
- `JsonTree.js` is a useful shared renderer, but it duplicates the existence of `json-tree.css` by exporting `jsonTreeCSS` inline, another small example of styling responsibility splitting across JS and CSS (`JsonTree.js:81`, `json-tree.css:1`).

## HTML Shell Composition

### Current pattern

- Example and app shells explicitly load `dark-theme.css`, `light-theme.css`, favicon, optional vendor scripts, CSS preloads, modulepreloads, then import components in a final module script (`examples/core/static/index.html:7`, `examples/core/static/index.html:10`, `examples/core/static/index.html:24`, `examples/core/static/index.html:73`).
- This is transparent and consistent with the merged namespace model, but it is also verbose and manually synchronized across apps (`examples/actors/static/index.html:10`, `examples/grants/static/index.html:10`, `examples/pygentic/static/index.html:10`, `apps/veille/static/index.html:10`).

### Benefits

- The shell is inspectable; there is no bundler-only magic hiding where CSS or component code comes from.
- Performance intent is explicit through preloads and modulepreloads (`examples/core/static/index.html:10`, `examples/core/static/index.html:22`).

### Drawbacks

- Shell duplication is high; the same preload and import topology is repeated across examples with small variations, increasing drift risk and raising the cost of system-wide changes.
- `auth.css` exists as a shared auth stylesheet but is not actually used by the stock login/register pages, which instead inline near-duplicate auth styling directly in HTML (`auth.css:1`, `login.html:11`, `register.html:11`).
- `example.html` is a stale architecture fossil: it imports `PTT`, `registrar`, and `remote` from paths and abstractions that no longer define the live design-system boundary, so it weakens architectural trust and should not be treated as a current example (`example.html:1`, `example.html:265`, `example.html:266`, `docs/frontend/ARCHITECTURE.md:317`).

## State Management and Data Flow

### Entity render flow

```text
Component attribute -> attach/ATTACH
  -> DynamicClass resolve
    -> DESCRIBE { proto, data }
      -> NTTElement.value setter
        -> update(prev,next) or scheduleRender()
          -> Formidable / component-specific HTML
```

- `Component.define()` is the proto boundary (`Component.js:183`).
- `NTTElement.DESCRIBE()` binds schema and value, then subscribes to the entity signal for live updates (`NTTElement.js:89`, `NTTElement.js:94`).
- `NTTItem.render()` dispatches by display mode, writes shadow DOM, then binds events against the new markup (`ntx-item.js:592`, `ntx-item.js:620`).

### Collection flow

```text
ListElement.definedCallback()
  -> proto.observe('UPDATE')
  -> proto.call('READ', { limit, offset })
  -> UPDATE(addresses)
  -> render() / update()
  -> createChild(ref) per entity
```

- Pagination state is local to `ListElement` and `NTTTable`, while total/meta state is stored on the dynamic class (`ListElement.js:34`, `ListElement.js:67`, `ntx-table.js:364`).
- This is a reasonable split, but it also means visual components are coupled to dynamic-class side channels like `_paginationMeta` and `_listReadPending` (`ListElement.js:64`, `ListElement.js:267`).

### Method and stream flow

```text
method schema -> ntx-method / ntx-stream
  -> target.call(method, payload)
    -> _response_ or STREAM handlers
      -> entity pull / visual update
```

- `ntx-method` relies on entity/prototype `.call()` and then updates local response state while the entity refreshes itself (`ntx-method.js:102`, `ntx-method.js:117`).
- `ntx-stream` adds dynamic aliasing to route method-name TX replies into a unified `STREAM()` dispatcher (`ntx-stream.js:43`, `ntx-stream.js:57`).
- Agent streaming layers keep the same mental model while introducing richer typed event handling (`ntx-stream-agent.js:15`, `ntx-agent-live.js:98`, `ntx-chat.js:109`).

## Error Propagation

### Good parts

- Entity validation errors are translated into structured field-level feedback by `NTTElement.ERROR()` and `NTTItem.onValidationError()` (`NTTElement.js:134`, `NTTElement.js:140`, `ntx-item.js:160`).
- `Toast` provides global feedback but does not hide inline state; `NTTItem` still keeps persistent `error` rendering in the card (`NTTElement.js:158`, `ntx-item.js:598`).

### Weak parts

- `Toast` globally injects CSS and a shared container into `document.body`, which is pragmatic but outside the component model and difficult to theme/test with the same discipline as normal components (`Toast.js:25`, `Toast.js:47`, `Toast.js:52`).
- `config.js` ships with `LOGGING: 3`, `LOGEVENTS: true`, `LOGSPAWN: true`, and `DEBUG: true`, so the default browser behavior is noisy and potentially exposes internal event topology even outside deliberate debug sessions (`config.js:2`).

## Coupling Analysis

### Healthy couplings

- `NTTItem` -> `Formidable` -> widgets is an appropriate visual coupling because it preserves a single schema-driven rendering chain (`ntx-item.js:17`, `form.js:58`, `index.js:22`).
- `ntx-router` -> `Router` is a clean DOM/state split (`ntx-router.js:12`, `ntx-router.js:46`).
- `ntx-topbar` -> `theme.js` and `Permissions` is appropriate shell coupling (`ntx-topbar.js:26`, `ntx-topbar.js:27`).

### Tight or problematic couplings

- `ntx-sidebar` reaches into `NTT`, `matrix`, and `buildRoute` directly; it is a shell component, but it also performs model bootstrap, list expansion, route generation, and hash navigation, which makes it a high-coupling hub (`ntx-sidebar.js:40`, `ntx-sidebar.js:42`, `ntx-sidebar.js:174`, `ntx-sidebar.js:287`).
- `ListElement` depends on dynamic-class internals such as `_listReadPending` and `_paginationMeta`, which are runtime side channels rather than public contracts (`ListElement.js:64`, `ListElement.js:267`).
- Agent components depend on optional globals like `marked`, and because they render `marked.parse(buf)` into `innerHTML`, they couple visual richness to undeclared runtime globals and to HTML injection paths (`ntx-stream-agent.js:213`, `ntx-agent-live.js:267`, `examples/grants/static/index.html:21`).

## Cohesion Assessment

### High cohesion

- `Component` is highly cohesive: all responsibilities revolve around being a runtime-aware web component base (`Component.js:23`).
- `Permissions` is cohesive within its domain even though it needs a reset story (`Permissions.js:17`).
- `registry.js` and `Widget.js` are both tight, single-purpose modules (`registry.js:15`, `Widget.js:12`).

### Medium cohesion

- `ntx-item` is large but still cohesive around one job: rendering and editing one entity (`ntx-item.js:26`).
- `ntx-table` is borderline; sort, inline create, error recovery, and row rendering are all table-centric, but it is the most likely candidate for future extraction (`ntx-table.js:23`).

### Low or split cohesion

- `example.html` is low-cohesion and no longer aligned with current architecture, blending demo UI, old runtime concepts, and registrar internals (`example.html:1`, `example.html:261`).
- Agent CSS responsibility is split across JS and CSS files, reducing cohesion of each module pair (`ntx-agent.js:367`, `ntx-agent.css:1`, `ntx-chat.js:244`, `ntx-chat.css:1`).

## Testing Assessment

### What is covered well

- Base entity/list component contracts are unit-tested (`NTTElement.test.js:23`, `ListElement.test.js:23`).
- `ntx-item` has extensive tests around rendering, validation, delete paths, permission gating, and error presentation (`ntx-item.test.js:84`).
- `ntx-table` covers inline create behavior and sort indicator structure (`ntx-table.test.js:69`).
- `Formidable` has deep unit coverage around widgets, groups, refs, validation, and edge cases (`form.test.js:22`).
- Playwright theme tests validate CSS variable resolution, dark/light switching, screenshots, responsive shells, and missing CSS 404s (`css-and-theming-unit.spec.js:13`, `css-and-theming-unit.spec.js:473`).

### What is under-covered

- Agent components have no comparable frontend tests in the reviewed suite despite carrying some of the most inconsistent styling-boundary logic.
- There are no tests asserting that agent CSS files are actually used or that inline agent CSS stays in sync with checked-in `.css` siblings.
- There are no tests asserting auth cache invalidation across login/logout or `Formidable` layout cache refresh in app code; the only explicit `Formidable.clearCache()` calls are in tests (`form.test.js:28`, `ntx-item.test.js:1273`).

## Key Findings

### F1. The core design-system primitive is strong and should remain the default

- `Component` already solves the right hard problems — style adoption, adaptive display, ref routing, and schema attach — in one place (`Component.js:91`, `Component.js:179`, `Component.js:309`).
- This is the correct architectural center for future design-system work.

### F2. Token vocabulary is fragmented

- Theme files publish `--surface-*`, `--text-*`, `--accent`, `--glass-*`, `--radius-*`, and legacy aliases only (`dark-theme.css:11`, `dark-theme.css:95`, `light-theme.css:79`).
- Many component/widget files instead depend on `--panel-bg`, `--line`, `--font-display`, `--accent-primary`, or similar vars with hard-coded fallbacks (`ntx-method.css:4`, `ntx-method.css:17`, `widgets.css:4`, `widgets.css:65`, `ntx-chat.css:18`).
- Result: theme coherence depends on fallback literals more than on shared tokens.

### F3. Agent UI breaks the preferred styling boundary

- `ntx-agent`, `ntx-agent-live`, and `ntx-chat` define their actual runtime styles inside JS strings (`ntx-agent.js:31`, `ntx-agent-live.js:34`, `ntx-chat.js:39`).
- Their sibling CSS files exist but are not imported by those runtime components (`ntx-agent.css:1`, `ntx-agent-live.css:1`, `ntx-chat.css:1`).
- This makes design changes less additive and less traceable.

### F4. `ntx-stream-agent` is a hybrid with two styling authorities

- It inherits and appends `ntx-stream-agent.css` through `styles()` (`ntx-stream-agent.js:7`).
- It also injects `agentStyles` inline at render time (`ntx-stream-agent.js:119`, `ntx-stream-agent.js:246`).
- The system should pick one authority.

### F5. Auth shell styling is duplicated instead of shared

- `auth.css` exists as a reusable auth stylesheet (`auth.css:1`).
- `login.html` and `register.html` each inline their own full auth style blocks instead of using it (`login.html:11`, `register.html:11`).
- This is direct design-system drift.

### F6. Form layout caching is structurally brittle

- Cache key = `schema.__name__:mode:permissions.role`, not schema identity or version (`form.js:13`).
- Tests already need explicit cache clearing to avoid stale layout reuse (`tests/frontend/tests/generators/form.test.js:25`).
- This is a real architectural smell, not just a test quirk.

### F7. Permissions and form cache invalidation are not integrated in production

- `Permissions.init()` memoizes the promise and only clears its private rule cache after a fetch (`Permissions.js:38`, `Permissions.js:67`).
- `Formidable.clearCache()` exists but is not called by any production code reviewed (`form.js:617`, `tests/frontend/tests/generators/form.test.js:28`).
- Same-session auth state changes can leave stale layout decisions.

### F8. `example.html` is architectural debt inside the design-system surface

- It still references `PTT`, `registrar`, `dispatch`, and an older framework narrative (`example.html:1`, `example.html:265`, `example.html:266`).
- Since this file lives inside the shipped static package, it blurs which examples are authoritative.

### F9. HTML shells are transparent but repetitive

- Each shell manually enumerates theme links, preloads, vendor scripts, and module graph roots (`examples/core/static/index.html:7`, `examples/grants/static/index.html:10`, `apps/veille/static/index.html:18`).
- This is not hidden magic, which is good, but it also means customization is not very additive at the shell layer.

### F10. The special light-theme investigation reveals a documentation/problem-statement mismatch, not a missing asset

- `light-theme.css` exists and is referenced by stock shells (`light-theme.css:1`, `examples/core/static/index.html:8`, `login.html:8`).
- The real issue is uneven token usage across components and widgets, not missing theme files.

## Recommendations

### Priority 1 — Unify style boundaries

- Move agent components onto the same file-based stylesheet contract used by `Component`, or give all standalone components a single shared standalone-style utility.
- Remove inline CSS strings where matching `.css` files already exist.

### Priority 2 — Close the token surface

- Define one canonical frontend token vocabulary.
- Map `panel`, `line`, typography, button, and accent aliases into the main theme or refactor component CSS to use existing tokens.
- Remove indigo/purple fallback bias from `widgets.css` in favor of canonical accent tokens (`widgets.css:4`, `widgets.css:151`, `dark-theme.css:27`).

### Priority 3 — Repair cache invalidation

- Add an explicit `permissions.refresh()` / `permissions.reset()` API.
- Couple login/logout/theme/auth shell flows to `Formidable.clearCache()` and permission refresh.
- Change `_getLayout()` cache key to include a schema identity/version hash rather than just `__name__`.

### Priority 4 — Reduce shell duplication

- Introduce a default shell manifest or helper HTML partial for modulepreloads and CSS preloads.
- Preserve transparency, but remove repeated low-level boilerplate from every app shell.

### Priority 5 — Retire stale artifacts

- Either modernize `example.html` to current architecture or remove it from the live static package to avoid mixed signals.

## Appendix A — Core File Inventory

### `n3tx-core`

- `packages/n3tx-core/src/n3tx_core/static/core/Component.js` — unified runtime component base, style cache, adaptive display, schema/ref attach (`Component.js:23`).
- `packages/n3tx-core/src/n3tx_core/static/utils/theme.js` — theme persistence and global dataset switching (`theme.js:8`).
- `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js` — global feedback overlay with injected CSS (`Toast.js:25`, `Toast.js:52`).
- `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js` — identity fetch and frontend rule evaluation (`Permissions.js:17`, `Permissions.js:45`).
- `packages/n3tx-core/src/n3tx_core/static/utils/Logging.js` — global in-memory logging sink (`Logging.js:5`).
- `packages/n3tx-core/src/n3tx_core/static/config.js` — frontend config and event constants (`config.js:2`).

## Appendix B — Theme and Global CSS Inventory

- `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css` — primary token definition and base document chrome (`dark-theme.css:11`, `dark-theme.css:109`).
- `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css` — verified light override token layer (`light-theme.css:11`).
- `packages/n3tx-ui/src/n3tx_ui/static/auth.css` — shared auth styling asset that is currently bypassed by stock auth pages (`auth.css:1`).

## Appendix C — UI Component JS Inventory

- `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js` — single-entity lifecycle bridge (`NTTElement.js:21`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js` — collection lifecycle, pagination, modal create (`ListElement.js:21`, `ListElement.js:133`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` — default item renderer, edit/delete/methods, display modes (`ntx-item.js:26`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js` — thin collection wrapper over `ListElement` (`ntx-list.js:13`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js` — table renderer with client sort and inline create (`ntx-table.js:23`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js` — row-mode specialization of `NTTItem` (`ntx-row.js:21`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js` — schema-driven method form and invocation surface (`ntx-method.js:14`, `ntx-method.js:134`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js` — streaming method specialization (`ntx-stream.js:5`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js` — view container over router state (`ntx-router.js:15`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js` — standalone modal with constructable sheet singleton (`ntx-modal.js:17`, `ntx-modal.js:36`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js` — ref chooser and inline create shell (`ntx-ref-picker.js:30`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js` — profile shell component using external CSS link (`ntx-profile.js:9`, `ntx-profile.js:31`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js` — model navigation shell (`ntx-sidebar.js:63`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js` — top navigation shell with auth and theme toggle (`ntx-topbar.js:54`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-user.js` — user-specific item renderer (`ntx-user.js:13`).

## Appendix D — UI Component CSS Inventory

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-element.css` — base loading/error/empty visuals (`ntx-element.css:3`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css` — core entity card system plus app-specific subclasses in one file (`ntx-item.css:1`, `ntx-item.css:763`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.css` — list header, grid, add/load-more controls (`ntx-list.css:8`, `ntx-list.css:37`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.css` — table shell, inline create row, sort headers (`ntx-table.css:43`, `ntx-table.css:141`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.css` — row display/edit styling (`ntx-row.css:10`, `ntx-row.css:54`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css` — method fieldset/inline/button layouts using secondary token vocabulary (`ntx-method.css:1`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.css` — basic streaming output presentation (`ntx-stream.css:1`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.css` — router chrome and content transitions (`ntx-router.css:6`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.css` — modal overlay/panel and close animations (`ntx-modal.css:3`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css` — dropdown and inline-create visuals (`ntx-ref-picker.css:35`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.css` — profile page styling consumed by `ntx-profile.js` (`ntx-profile.css:1`, `ntx-profile.js:9`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css` — sidebar shell, accordion sections, overlay (`ntx-sidebar.css:35`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css` — sticky topbar, nav, user dropdown, hamburger (`ntx-topbar.css:10`).
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-user.css` — avatar-oriented user item visuals (`ntx-user.css:15`).

## Appendix E — Generator and Widget Inventory

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js` — schema-driven HTML generator, layout cache, validation, attached methods, ref lists (`form.js:58`, `form.js:527`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js` — widget base class (`Widget.js:12`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js` — widget registry lookup and config pass-through (`registry.js:15`, `registry.js:31`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js` — built-in widget registration (`index.js:22`, `index.js:33`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/UrlWidget.js` — URL link widget (`UrlWidget.js:3`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/EmailWidget.js` — email link widget (`EmailWidget.js:3`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/DateWidget.js` — date/datetime widget (`DateWidget.js:3`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js` — markdown widget with optional `marked` (`MarkdownWidget.js:10`, `MarkdownWidget.js:17`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/ConsoleWidget.js` — ANSI-aware console widget with optional `AnsiUp` (`ConsoleWidget.js:10`, `ConsoleWidget.js:17`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/ReferenceWidget.js` — simple reference display/edit widget (`ReferenceWidget.js:10`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/CurrencyWidget.js` — currency widget (`CurrencyWidget.js:11`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/TextareaWidget.js` — multiline text widget (`TextareaWidget.js:11`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/JsonTree.js` — inline JS JSON tree renderer plus embedded CSS string (`JsonTree.js:28`, `JsonTree.js:84`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css` — widget presentation layer using mixed token vocabulary (`widgets.css:1`).
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/json-tree.css` — separate CSS file for JSON tree, partially duplicating `JsonTree.js` styles (`json-tree.css:1`).

## Appendix F — Static HTML Inventory

- `packages/n3tx-ui/src/n3tx_ui/static/example.html` — stale demo page tied to old registrar/PTT architecture (`example.html:1`, `example.html:265`).
- `packages/n3tx-ui/src/n3tx_ui/static/login.html` — stock login shell, inline auth styling, theme links, `theme.js` import (`login.html:7`, `login.html:10`, `login.html:11`, `login.html:144`).
- `packages/n3tx-ui/src/n3tx_ui/static/register.html` — stock register shell, same duplicated auth styling pattern (`register.html:7`, `register.html:10`, `register.html:11`, `register.html:149`).

## Appendix G — Agent UI Inventory

- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` — rich stream specialization with hybrid CSS strategy and markdown rendering (`ntx-stream-agent.js:4`, `ntx-stream-agent.js:213`, `ntx-stream-agent.js:246`).
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css` — external stylesheet sibling, partially duplicated by inline `agentStyles` (`ntx-stream-agent.css:1`).
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js` — agent entity renderer with constructable inline sheet, external CSS file unused by runtime (`ntx-agent.js:31`, `ntx-agent.js:367`).
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.css` — checked-in CSS sibling for `ntx-agent` (`ntx-agent.css:1`).
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` — live activity panel using inline `<style>` block and markdown rendering (`ntx-agent-live.js:34`, `ntx-agent-live.js:267`, `ntx-agent-live.js:292`).
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css` — external CSS sibling not used by runtime component (`ntx-agent-live.css:1`).
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js` — floating chat shell using inline `<style>` block (`ntx-chat.js:39`, `ntx-chat.js:244`).
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css` — external CSS sibling not used by runtime component (`ntx-chat.css:1`).

## Appendix H — Usage Site Inventory

- `examples/core/static/index.html` — baseline shell with topbar/sidebar/router/list composition and manual preload topology (`examples/core/static/index.html:7`, `examples/core/static/index.html:10`, `examples/core/static/index.html:60`, `examples/core/static/index.html:73`).
- `examples/actors/static/index.html` — same shell plus `ntx-chat`, showing merged-namespace agent UI adoption (`examples/actors/static/index.html:7`, `examples/actors/static/index.html:72`).
- `examples/grants/static/index.html` — shell using table/list/sidebar/chat composition with optional vendor scripts (`examples/grants/static/index.html:7`, `examples/grants/static/index.html:65`, `examples/grants/static/index.html:78`).
- `examples/pygentic/static/index.html` — shell loading agent live/chat plus `ntx-agent` item-tag override (`examples/pygentic/static/index.html:61`, `examples/pygentic/static/index.html:64`, `examples/pygentic/static/index.html:74`, `examples/pygentic/static/index.html:76`).
- `apps/veille/static/index.html` — most complex shell, mixing framework components with app-specific inline sections and custom components (`apps/veille/static/index.html:7`, `apps/veille/static/index.html:56`, `apps/veille/static/index.html:219`, `apps/veille/static/index.html:245`).
- `packages/n3tx-core/src/n3tx_core/static/schema.html` — kitchen-sink shell demonstrating topbar/router/items/schema inspector and auth panel (`schema.html:7`, `schema.html:15`, `schema.html:149`).

## Appendix I — Test Inventory

- `tests/frontend/vitest.config.js` — merged-namespace alias simulation for core/ui and partial agents (`vitest.config.js:4`, `vitest.config.js:18`).
- `tests/frontend/tests/components/NTTElement.test.js` — basic `NTTElement` contract coverage (`NTTElement.test.js:23`).
- `tests/frontend/tests/components/ListElement.test.js` — selection API and cascade constants coverage (`ListElement.test.js:23`).
- `tests/frontend/tests/components/ntx-item.test.js` — large behavioral suite around rendering, permissions, errors, and delete flows (`ntx-item.test.js:84`).
- `tests/frontend/tests/components/ntx-table.test.js` — inline create, validation, sort indicator coverage (`ntx-table.test.js:69`).
- `tests/frontend/tests/components/ntx-topbar.test.js` — auth/theme toggle/dropdown behavior coverage (`ntx-topbar.test.js:33`).
- `tests/frontend/tests/components/ntx-sidebar.test.js` — shell parsing, events, cleanup, NTT bootstrapping coverage (`ntx-sidebar.test.js:100`).
- `tests/frontend/tests/generators/form.test.js` — detailed `Formidable` behavior and cache edge-case coverage (`form.test.js:22`, `form.test.js:25`).
- `tests/frontend/tests/integration/form-entity-binding.test.js` — form/widget/rendering integration coverage (`form-entity-binding.test.js:33`).
- `tests/frontend/tests/integration/display-mode-cascade.test.js` — display-mode normalization and cascade integration coverage (`display-mode-cascade.test.js:26`).
- `tests/frontend/tests/e2e/css-and-theming-unit.spec.js` — theme token, screenshot, responsive, and CSS loading coverage (`css-and-theming-unit.spec.js:13`, `css-and-theming-unit.spec.js:473`).

## Closing Judgment

- The design-system subsystem is architecturally promising because the hard part — schema-driven runtime/visual composition — is already in place and mostly aligned with N3TX's philosophy (`docs/CORE.md:109`, `Component.js:23`, `form.js:58`).
- The next maturity step is not inventing a new design system; it is tightening the one that already exists by making tokens canonical, stylesheet boundaries uniform, cache invalidation explicit, and shell composition less repetitive.
