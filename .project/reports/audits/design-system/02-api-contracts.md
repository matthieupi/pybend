# Design-System Audit — API Contracts

## Scope

- This report audits the frontend design-system contract surface across runtime primitives, visual components, forms, widgets, themes, cross-package imports, and the concrete consumer patterns exercised by examples and tests. The audit judges the subsystem against N3TX's stated principles that the backend is authoritative, frontend behavior is schema-driven, zero-config defaults should work, customization should be additive, and boundaries should remain transparent and traceable. `docs/CORE.md:109` `docs/CORE.md:144` `FRONTEND.md:17` `FRONTEND.md:127`
- The audit is code-first but documentation-aware: I read the required architecture/frontend docs, the package docs for components/formidable/widgets/viewable/schema-pipeline/tool-discovery, every core source file requested under `n3tx-core`, `n3tx-ui`, and `n3tx-agents`, and every requested usage/test site. `docs/ARCHITECTURE.md:15` `FRONTEND.md:39` `packages/n3tx-ui/docs/components.md:79` `packages/n3tx-ui/docs/formidable.md:42` `packages/n3tx-ui/docs/widgets.md:37` `packages/n3tx-ui/docs/viewable-mixin.md:69` `packages/n3tx-core/docs/schema-pipeline.md:39` `packages/n3tx-agents/docs/tool-discovery.md:46`

## Files Read

### Documentation and Context

- `docs/ARCHITECTURE.md` for cross-stack architecture, extension points, and mixin/adapter patterns. `docs/ARCHITECTURE.md:15` `docs/ARCHITECTURE.md:597`
- `docs/CORE.md` for the schema contract and frontend consumption map. `docs/CORE.md:109` `docs/CORE.md:144`
- `FRONTEND.md` for runtime-vs-visual split, merged static namespace, and frontend component inventory. `FRONTEND.md:17` `FRONTEND.md:115`
- `packages/n3tx-ui/docs/components.md` for component hierarchy, lifecycle, and public attributes. `packages/n3tx-ui/docs/components.md:11` `packages/n3tx-ui/docs/components.md:135`
- `packages/n3tx-ui/docs/formidable.md` for form generator API and layout cache semantics. `packages/n3tx-ui/docs/formidable.md:11` `packages/n3tx-ui/docs/formidable.md:42`
- `packages/n3tx-ui/docs/widgets.md` for widget API and registry contract. `packages/n3tx-ui/docs/widgets.md:9` `packages/n3tx-ui/docs/widgets.md:37`
- `packages/n3tx-ui/docs/viewable-mixin.md` for `__ui__` / schema `ui` emission rules. `packages/n3tx-ui/docs/viewable-mixin.md:12` `packages/n3tx-ui/docs/viewable-mixin.md:69`
- `packages/n3tx-core/docs/schema-pipeline.md` for pipeline stage ordering and import-time extension mechanics. `packages/n3tx-core/docs/schema-pipeline.md:11` `packages/n3tx-core/docs/schema-pipeline.md:92`
- `packages/n3tx-agents/docs/tool-discovery.md` for tool schema derivation and LLM-clean schema constraints. `packages/n3tx-agents/docs/tool-discovery.md:13` `packages/n3tx-agents/docs/tool-discovery.md:124`

### Core Runtime and Utilities

- `packages/n3tx-core/src/n3tx_core/static/core/Component.js`. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:23`
- `packages/n3tx-core/src/n3tx_core/static/utils/theme.js`. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:8`
- `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js`. `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js:15`
- `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js`. `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:17`
- `packages/n3tx-core/src/n3tx_core/static/utils/Logging.js`. `packages/n3tx-core/src/n3tx_core/static/utils/Logging.js:5`
- `packages/n3tx-core/src/n3tx_core/static/config.js`. `packages/n3tx-core/src/n3tx_core/static/config.js:2`

### Theme / Static HTML / CSS

- `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css`. `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:11`
- `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css`. `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`
- `packages/n3tx-ui/src/n3tx_ui/static/auth.css`. `packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/example.html`. `packages/n3tx-ui/src/n3tx_ui/static/example.html:1`
- `packages/n3tx-ui/src/n3tx_ui/static/login.html`. `packages/n3tx-ui/src/n3tx_ui/static/login.html:1`
- `packages/n3tx-ui/src/n3tx_ui/static/register.html`. `packages/n3tx-ui/src/n3tx_ui/static/register.html:1`

### UI Components — JS

- `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:21`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:21`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:26`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js:13`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js:23`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:21`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:14`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:5`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:15`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:36`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:30`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:63`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:54`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:11`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-user.js`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-user.js:13`

### UI Components — CSS

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-element.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-element.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-user.css`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-user.css:1`

### Form / Widgets

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:12`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:15`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js:19`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/UrlWidget.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/UrlWidget.js:3`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/EmailWidget.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/EmailWidget.js:3`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/DateWidget.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/DateWidget.js:3`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:10`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/ConsoleWidget.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/ConsoleWidget.js:10`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/ReferenceWidget.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/ReferenceWidget.js:10`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/CurrencyWidget.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/CurrencyWidget.js:11`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/TextareaWidget.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/TextareaWidget.js:11`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/JsonTree.js`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/JsonTree.js:28`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:1`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/json-tree.css`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/json-tree.css:1`

### Agent Components — JS

- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:4`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:21`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:25`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js`. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:24`

### Agent Components — CSS

- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css`. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css:1`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css`. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css:1`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.css`. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.css:1`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css`. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css:1`

### Usage / Test Sites

- `examples/core/static/index.html`. `examples/core/static/index.html:7`
- `examples/actors/static/index.html`. `examples/actors/static/index.html:7`
- `examples/grants/static/index.html`. `examples/grants/static/index.html:7`
- `examples/pygentic/static/index.html`. `examples/pygentic/static/index.html:7`
- `apps/veille/static/index.html`. `apps/veille/static/index.html:7`
- `packages/n3tx-core/src/n3tx_core/static/schema.html`. `packages/n3tx-core/src/n3tx_core/static/schema.html:7`
- `tests/frontend/vitest.config.js`. `tests/frontend/vitest.config.js:4`
- `tests/frontend/tests/components/NTTElement.test.js`. `tests/frontend/tests/components/NTTElement.test.js:21`
- `tests/frontend/tests/components/ListElement.test.js`. `tests/frontend/tests/components/ListElement.test.js:21`
- `tests/frontend/tests/components/ntx-item.test.js`. `tests/frontend/tests/components/ntx-item.test.js:32`
- `tests/frontend/tests/components/ntx-method.test.js`. `tests/frontend/tests/components/ntx-method.test.js:27`
- `tests/frontend/tests/components/ntx-ref-picker.test.js`. `tests/frontend/tests/components/ntx-ref-picker.test.js:132`
- `tests/frontend/tests/components/ntx-topbar.test.js`. `tests/frontend/tests/components/ntx-topbar.test.js:30`
- `tests/frontend/tests/components/ntx-sidebar.test.js`. `tests/frontend/tests/components/ntx-sidebar.test.js:98`
- `tests/frontend/tests/generators/form.test.js`. `tests/frontend/tests/generators/form.test.js:20`
- `tests/frontend/tests/integration/form-entity-binding.test.js`. `tests/frontend/tests/integration/form-entity-binding.test.js:23`
- `tests/frontend/tests/e2e/form-rendering-unit.spec.js`. `tests/frontend/tests/e2e/form-rendering-unit.spec.js:14`
- `tests/frontend/tests/e2e/css-and-theming-unit.spec.js`. `tests/frontend/tests/e2e/css-and-theming-unit.spec.js:13`

## Executive Readout

- The subsystem has a strong, coherent center: schema-driven rendering is real, not rhetorical. `Formidable`, `NTTItem`, `ListElement`, `NTTMethod`, `Permissions`, and the examples all consume backend-emitted `schema`, `ui`, `access`, and `methods` metadata directly rather than maintaining a parallel handwritten frontend contract. `docs/CORE.md:109` `docs/CORE.md:144` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:403` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:67` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:82`
- The public component API is broad but discoverable: most visual primitives expose their contract through attributes (`model`, `ref`, `display`, `router`, `method`, `uuid`, `layout`, `allow-create`, `headless`, `item-tag`, `item-display`, `name`, `no-user`, `models`) and pair those with modest imperative methods (`toggle`, `open`, `close`, `loadMore`, `openCreateModal`, `save`, `cancel`, `callMethod`). `packages/n3tx-ui/docs/components.md:135` `packages/n3tx-ui/docs/components.md:145` `packages/n3tx-ui/src/n3tx_ui/static/core/Component.js:112` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:79` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:157`
- The deepest weakness is inconsistency at package boundaries and styling contracts. `n3tx-ui` components uniformly use `Component.styles` + external CSS URLs + constructable stylesheets, but `n3tx-agents` mixes inline `<style>` blocks, runtime-created `CSSStyleSheet`s, and a broken `NTTStreamAgent` style injection path while still shipping unused `.css` files. That inconsistency is visible in source shape, test aliasing, and extension ergonomics. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:91` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:258` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:33` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:31`
- The theme API is functional but under-specified. Runtime behavior assumes a two-file contract (`dark-theme.css` base + `light-theme.css` variable overrides) plus `theme.js` toggling `document.documentElement.dataset.theme`. That contract is relied on in examples, auth pages, kitchen-sink pages, and tests, but documentation never crisply states it as a required page-level integration contract. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:8` `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11` `examples/core/static/index.html:7` `packages/n3tx-ui/src/n3tx_ui/static/login.html:7` `packages/n3tx-core/src/n3tx_core/static/schema.html:7` `FRONTEND.md:88`
- Zero-config mostly works for core entity rendering (`<ntx-list model="Product">`, `<ntx-item ref="Product/1">`, auto-rendered methods/forms), but several edges are “soft contracts” rather than explicit APIs: `forward` on `ntx-method` is parsed but unused, `refInput` and `getArrayInput` are exported but effectively dead, `setTheme()` accepts arbitrary strings, and the merged-static-namespace import illusion is necessary for agent component relative imports to work. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js:13` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:27` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:45` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:16` `FRONTEND.md:23` `tests/frontend/vitest.config.js:18`

## Public API Inventory

### Runtime Base Contracts

| Surface | Public contract | Consumer expectation | Evidence |
|---|---|---|---|
| `Component` | Attributes: `model`, `addr`, `hash`, `ref`, `display` | Every visual component inherits unified actor/entity/bootstrap behavior through attributes instead of bespoke init code | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:112` |
| `Component` | `styles` getter accepts string or array | Subclasses provide stylesheet URLs; base class fetches, caches, and adopts them before scheduled render | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:94` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:262` |
| `Component` | `prerender()`, `render()`, `definedCallback()` hooks | Lifecycle is split into pre-schema structure, schema-ready hook, and final render | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:183` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:436` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:455` |
| `Component` | `displayMode`, `display`, `displayModeChanged()` | Layout-specific components rely on responsive size dispatch without own resize code | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:315` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:330` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:348` |
| `Component` | `attach(addr)` / `subscribe(tt, attribute, callback)` | Schema/data flows through `NTT.attach()` and observable subscriptions, not direct fetches in most components | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:414` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:423` |

### Entity / List Components

| Tag / class | Attribute API | Imperative API | Core output contract | Evidence |
|---|---|---|---|---|
| `<ntx-item>` / `NTTItem` | `display`, `ref`, `model`, `select-target`, `create-mode` | `toggleMode()`, `cancelEdit()`, `deleteItem()`, inherited `save()` | Adaptive entity card/pill/detail/page rendering with form + methods | `packages/n3tx-ui/docs/components.md:135` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:66` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:122` |
| `<ntx-list>` / `NTTList` | `model`, `display`, `router`, `item-tag`, `item-display`, `headless`, `allow-create` | `loadMore()`, `openCreateModal()` | Default collection grid for a model | `packages/n3tx-ui/docs/components.md:145` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:75` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:133` |
| `<ntx-table>` / `NTTTable` | `model`, `allow-create`, inherited list attrs | Inline sorting + inline create flow | Table/grid list with row components and create row | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js:23` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js:130` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js:160` |
| `<ntx-row>` / `NTTRow` | Forced `display="row"` | inline edit/save/cancel inherited from row-specific override | Table row child with same model contract as item | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:28` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:127` |
| `<ntx-user>` / `NTTUser` | same as `ntx-item` | inherited | User-specialized avatar renderer for xs/sm only | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-user.js:13` |
| `<ntx-agent>` / `NtxAgent` | same as `ntx-item` | inherited + custom section renderers | AgentActor-specific rich display | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:24` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:149` |

### Action / Navigation / Utility Components

| Tag / class | Attribute API | Imperative API | Core contract | Evidence |
|---|---|---|---|---|
| `<ntx-method>` / `NTTMethod` | `model`, `method`, `uuid`, `mode`, `label`, `forward`, `layout`, `placeholder`, `button-label`, `widget`, `icon`, `count-field` | `callMethod()` | Loads method schema from model schema and renders fieldset/inline/button variants | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:27` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:47` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:134` |
| `<ntx-stream>` / `NTTStream` | inherits `ntx-method` | `callMethod()`, `cancel()` | Same method contract with `meta.stream=true` and streaming output | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:24` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:43` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:139` |
| `<ntx-stream-agent>` / `NTTStreamAgent` | inherits `ntx-stream` | UPPERCASE event handlers | Agent-event rendering for `thinking`, `tool_call`, `tool_result`, `text`, `done`, `stream_end`, `stream_error` | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:15` |
| `<ntx-agent-live>` | `model`, `ref`, `method` | `callMethod()` via run button | Standalone live activity panel | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:1` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:27` |
| `<ntx-chat>` | `model`, `method`, optional selected instance via dropdown | `callMethod()` | Collapsible chat side-panel with stream or request-response fallback | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:1` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:74` |
| `<ntx-router>` | `name`, `no-hash` | none beyond Router messages | View container that mounts tags resolved from router state | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:7` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:46` |
| `<ntx-sidebar>` | `models`, `router`, `view`, `open`; light-DOM route templates | `toggle()`, `open()`, `close()` | Slide-in navigation, model bootstrap, route template expansion | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:7` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:157` |
| `<ntx-topbar>` | `brand`, `version`, `logo`, `href`, `no-user`; slot `nav` | logout/theme toggle are internal actions | Sticky nav using `/ _meta`, permissions, and theme manager | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:8` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:107` |
| `<ntx-modal>` | no declarative attrs; programmatic `NTTModal.open/prompt` | `close(reason)`; `.body`; callbacks | Reusable modal shell for create/edit flows | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:58` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:105` |
| `<ntx-ref-picker>` | `field`, `model`, `parent-model`, `parent-table`, `parent-id`, `child-table` | internal `_showPicker()`, `_showInlineCreate()`, `_addRef()`, `_submitCreate()` | Add-existing / create-inline contract for ListRef fields | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:11` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:41` |
| `<ntx-profile>` | none | none | Authenticated-user profile panel | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:1` |

### Form / Widget / Theme APIs

| Surface | Public API | Return contract | Evidence |
|---|---|---|---|
| `Formidable` | `getForm`, `getInput`, `getListInput`, `renderGroupedFields`, `formatDisplayValue`, `validateForm`, `validationAttrs`, `clearCache`, plus `refInput` and `getArrayInput` exports | Mostly HTML strings; `validateForm()` returns `[{field,message}]`; `clearCache()` is imperative | `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:607` |
| `Widget` | `display`, `edit`, `list`, `validate`, `truncate`, `escape`, `el` | `display()` and `edit()` return DOM nodes; `list()` returns string; `validate()` returns `string|null` | `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:21` `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:33` `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:48` |
| Widget registry | `registerWidget`, `getWidgetForField`, `hasWidget` | widget lookup returns `{ widget, config }` | `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:22` `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:31` |
| Theme manager | `getTheme()`, `setTheme(theme)`, `toggleTheme()` | localStorage persistence + `dataset.theme` + `theme-change` event | `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:12` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:24` |

## Contract Map vs N3TX Philosophy

### Backend Authoritative / Frontend Adaptive

- The subsystem largely honors “backend authoritative”: `schema.properties`, `schema.ui`, `schema.access`, `schema.methods`, and `$defs` directly drive rendering, permissions, widgets, and navigation without parallel handwritten frontend model metadata. `docs/CORE.md:111` `docs/CORE.md:136` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:252` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:82` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:71`
- `ViewableMixin` and schema pipeline docs explicitly describe `__ui__` as schema-emitted metadata rather than frontend-owned config, and the consuming code follows that contract. `packages/n3tx-ui/docs/viewable-mixin.md:71` `packages/n3tx-core/docs/schema-pipeline.md:23` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:67`
- The strongest example is method rendering: a backend `@expose_route` becomes `schema.methods[...]`, `Formidable` can attach it to a field, and `<ntx-method>` resolves inputs from that schema at runtime. `docs/CORE.md:139` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:90` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:173`
- The weak point is themeing and auth pages: those pages rely on page-authored HTML/CSS/link conventions rather than backend-emitted schema, so the design-system contract there is frontend-authored and only lightly documented. `packages/n3tx-ui/src/n3tx_ui/static/login.html:7` `packages/n3tx-ui/src/n3tx_ui/static/register.html:7` `packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`

### Zero-Config Defaults

- Core entity rendering is zero-config in practice: `<ntx-list model="Product">` is enough to load schemas, read records, stamp child items, and render default cards. Examples rely on exactly that. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js:13` `examples/core/static/index.html:61` `packages/n3tx-core/src/n3tx_core/static/schema.html:84`
- `NTTItem` is the canonical zero-config fallback and dispatches to default size methods plus `Formidable` when not customized. `packages/n3tx-ui/docs/components.md:19` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:380` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:592`
- Widget dispatch is additive rather than mandatory: callers first look for a registered widget and otherwise fall back to type-based rendering. `packages/n3tx-ui/docs/widgets.md:35` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:212`
- The subsystem stops being zero-config at the page shell level. Every example manually includes theme CSS, optional vendor scripts, and a large import/modulepreload set; login/register also manually include both theme files and `theme.js`. That is operationally workable but not “one tag and go” for full shell integration. `examples/core/static/index.html:7` `examples/core/static/index.html:20` `examples/core/static/index.html:24` `packages/n3tx-ui/src/n3tx_ui/static/login.html:7` `packages/n3tx-ui/src/n3tx_ui/static/register.html:7`

### Composable Primitives / Additive Customization

- `Component`, `NTTElement`, `ListElement`, `NTTMethod`, and `Widget` are genuinely composable bases with explicit override points (`render`, `update`, `displayModeChanged`, `childTag`, `childDisplay`, section renderers, widget methods). `packages/n3tx-core/src/n3tx_core/static/core/Component.js:195` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:55` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177` `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:21`
- `ntx-sidebar` route templates are a good additive customization pattern: children with `model` attributes define route templates while legacy `models` still works. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:85` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:122` `packages/n3tx-ui/docs/components.md:193`
- `ntx-item` also supports additive child rendering via schema `ui.renderer.item`, local `$defs` renderer hints, and `<template item-template>` inside lists. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:174` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:198` `packages/n3tx-ui/docs/components.md:181`
- The biggest composability blemish is that agent components do not consistently participate in the same style-loading primitive as the rest of the system, so extending them means learning a second styling contract. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:258` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:33` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:31`

### Transparency / Traceability

- The core lifecycle is traceable from attribute to behavior: `model` triggers `attach()`, then `ATTACH` to `NTT`, then `define()`, then `definedCallback()`, then component-specific reads/renders. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:127` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:183` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:56`
- `NTTElement.ERROR` and `NTTMethod._response_` make network error/success routing inspectable and explicit. `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:134` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117`
- The merged static namespace hides real package boundaries. It simplifies the browser view but makes source-level import tracing less direct, especially for agent components that import `./ntx-stream.js` and expect a merged `/components` namespace that does not exist inside their source package alone. `FRONTEND.md:23` `FRONTEND.md:115` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`

### Modular Boundaries That Simplify Extension

- The core/ui/agents split is conceptually sound and well-documented: runtime lives in `n3tx-core`, visuals in `n3tx-ui`, agent UX in `n3tx-agents`. `FRONTEND.md:19` `FRONTEND.md:103`
- In practice, import boundaries leak through the merged-static illusion and test aliasing. `vitest.config.js` has to map `core`, `utils`, `components`, `widgets`, and a special-case agent component alias, which is evidence that the package split is not fully expressible through normal module resolution in source form. `tests/frontend/vitest.config.js:17` `tests/frontend/vitest.config.js:28`
- The design-system API is therefore modular at runtime but only partially modular in source authoring and test authoring. That weakens extension and standalone reuse. `FRONTEND.md:23` `tests/frontend/vitest.config.js:18`

## Core Invariants and Ordering Requirements

### Component Base Invariants

- `Component` always registers itself with `matrix` in the constructor, so all component instances are addressable actors from birth. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:77` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:79`
- `Component.value` enforces only a top-level `typeof` match against its default value. This protects entity-vs-list shape at a very coarse level but does not validate field-level structure. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:241` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:243`
- `prerender()` always runs in `connectedCallback()` before any schema-dependent `render()`. This ordering is the foundation of skeleton/loading/live panel structures. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:436` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:445`
- `scheduleRender()` waits for stylesheet fetch/adoption when `#styleReady` is present, so subclasses can assume CSS is ready when `render()` fires from that path. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:359` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:369`
- `define()` is idempotent per schema name and clears the cached `schema` getter before calling `definedCallback()`. Consumers rely on this to avoid duplicate bootstraps. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:183` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:187`

### Schema / Entity Invariants

- `NTTElement.UPDATE` requires incoming data to include `$schema`; it asserts that condition before setting value. The component contract therefore assumes entity responses remain self-describing. `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:67` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:69`
- `NTTElement.DESCRIBE` assumes `data.proto` and `data.data` arrive together and then subscribes to the entity signal using `model/id`. `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:85` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:95`
- `ListElement.definedCallback()` assumes the DynamicClass can serve as a collection source, deduplicates reads through `_listReadPending`, and derives populate depth from `schema.ui.populate.depth`. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:56` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:64` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:67`
- `ListElement.UPDATE` only accepts arrays. Non-array collection payloads are warned and ignored. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:89` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:96`

### Render / Edit Mode Invariants

- `NTTItem` size methods return HTML strings, and `render()` wraps them inside a `.card` except for `row` mode. This means custom subclasses overriding a size method must return HTML, not nodes. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:229` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:592` `packages/n3tx-ui/docs/components.md:206`
- `NTTItem.sm()` explicitly delegates to `md()` in edit mode, so compact views do not get a compact editor. That is both a contract and a gotcha documented in `components.md`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:247` `packages/n3tx-ui/docs/components.md:208`
- `NTTRow.connectedCallback()` forces `display='row'` regardless of author input. Consumers cannot meaningfully request another display mode. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:28` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:37`
- `NTTItem` uses `AbortController` per render and rebinds all listeners after every render. Extension code inside subclasses must follow the same pattern or leak listeners. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:631` `packages/n3tx-ui/docs/components.md:212`

### Method / Stream Ordering Invariants

- `NTTMethod.connectedCallback()` always calls `load()`, and every attribute change also calls `load()`. The component contract therefore treats attributes as the source of truth and tolerates reloading. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:33` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:43`
- `NTTMethod.load()` must resolve `model` to a registered DynamicClass via `NTT.get()`, optionally `uuid` to an instance, and then `methodSchema` to `proto.schema.methods[method]` before render. Missing pieces just log errors and stop. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:61` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:64` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:82`
- `NTTStream.callMethod()` binds a dynamic handler named after the method and routes all replies to `STREAM()`. If the method name changes, the old alias is deleted. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:43` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:55`
- `NTTStream.cancel()` is client-side authoritative: it sets `#cancelled`, sends `STREAM_CANCEL`, and then calls `STREAM_END({})` locally. Backends are not required to acknowledge cancel for the UI to stop. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:134` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:146` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:154`

## Public Component Contracts in Detail

### `Component`

- Strength: the class gives the subsystem one clear contract for attribute observation, resize-driven display modes, shadow DOM styling, actor registration, and NTT attachment. That is exactly the sort of primitive N3TX claims to prefer. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:23` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:112` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:309`
- Risk: the public API is documented as “override `styles` to provide a CSS URL,” but the implementation quietly accepts arrays too. That is useful, but under-documented; only `NTTStream` exploits it by extending parent styles. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:94` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:264` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:7`
- Risk: there is no explicit validation of `display` beyond normalization; unknown explicit values survive in `childDisplay` if they are non-normalized explicit strings. That leaks malformed author input deeper into rendering. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:41` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:187`
- Risk: `ref` is the public attribute but the private field is `#href`, and the setter branches differently for URL refs vs NTT addresses vs URL+`data-model` optimization. The contract is powerful but not especially simple. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:202` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:206` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:216`

### `NTTElement`

- Strength: the base entity contract is explicit — `UPDATE`, `DESCRIBE`, `READ`, `ERROR`, `save()`, `onValidationError()`, `update()`. It is small, reusable, and documented. `packages/n3tx-ui/docs/components.md:81` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:63` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:180`
- Strength: `ERROR` understands the actual backend error wire format (`meta.response`) and turns 422 arrays into field-level errors plus inline banner text. That makes backend validation authoritative even after client-side validation. `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:124` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:139`
- Risk: value equality suppression is semantic only after `_rendered`, which is subtle and easy to break in subclasses that manipulate `_rendered` or bypass `render()`. `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:39` `packages/n3tx-ui/docs/components.md:206`

### `ListElement`

- Strength: the list contract is coherent: subscribe once, deduplicate the initial read, expose `selected` management, and provide `createChild()` plus `update()` patching. `packages/n3tx-ui/docs/components.md:109` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:56` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:220`
- Strength: `openCreateModal()` uses the same childTag schema/override chain as list rendering, so creation inherits the same presentation customization. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:141` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177`
- Risk: list header titles default to `${this.model}s`, which is a weak pluralization contract and visibly wrong for irregular model names. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:276`
- Risk: collection payloads are assumed to be arrays of addresses, not objects. Pagination metadata is stored on `proto._paginationMeta` rather than traveling in the list value itself, which is implicit stateful coupling. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:249` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:267`

### `NTTItem`

- Strength: `NTTItem` is the real center of the design system. It expresses zero-config rendering, edit/delete gating, schema-driven forms, method attachments, nested refs, and compact/detail/page layouts in one place. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:2` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:380` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:813`
- Strength: the rendering contract for compact rows is richer than the docs imply. `sm()` prioritizes leading `$ref` avatars, uses `ui.field_order`, respects field permissions, and renders button-layout methods inline. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:239` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:275` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:331`
- Strength: top-level delete and nested unlink are distinct behaviors, which matches N3TX's reference-based data model better than a naïve “delete item everywhere” approach. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:71` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:104`
- Risk: `deleteItem()` uses `confirm()` directly, hard-coding browser modal UX into the public behavior rather than using the framework modal primitive. That is consistent but not composable. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:81` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:106` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:58`
- Risk: inline reply detection is heuristic, based on `ui.layout === 'inline'` and placeholder text containing “reply”. That is a semantic leak from content string to UI behavior. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:349` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:698`
- Risk: `handleInputChange()` mutates `this.value` deeply for array elements before assigning new top-level objects in some other paths, so immutability is inconsistent and patch/update behavior depends on call path. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:218` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:223` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:667`

### `NTTMethod`

- Strength: `NTTMethod` exposes a compact attribute-based surface for a complicated feature — method schema discovery, instance-vs-class method dispatch, three layouts, count badges, and inline form generation. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:27` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:102` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:141`
- Strength: button-layout methods are consistent with schema UI hints (`icon`, `count-field`, `label`) and read populated wrapper counts correctly via `meta.total` fallback. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:145` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:148`
- Risk: `forward` is parsed in `load()` but never used anywhere else. That creates a false public API surface. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:28` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:53`
- Risk: there is no parameter validation beyond native input typing. `callMethod()` simply spreads `this.value` into the outbound payload. `Formidable` is not involved here. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:102` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:108`
- Risk: the implementation defines no `baseStyles`, `inlineStyles`, or `buttonStyles`, but the unit tests still assert those statics exist. That indicates either stale tests or a lost API surface. `tests/frontend/tests/components/ntx-method.test.js:822` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:305`

### `NTTStream` and Agent Stream Surfaces

- Strength: `NTTStream` stays close to the same method API and only extends transport behavior, which makes streaming an additive switch (`schema.methods[m].stream === true`). `FRONTEND.md:221` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:43`
- Strength: event dispatch through UPPERCASE handlers is a clear contract and mirrors backend actor handler naming. `FRONTEND.md:266` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:33`
- Major inconsistency: `NTTStreamAgent` ships a standalone CSS file, but the JS implementation neither returns it from `styles` nor attaches it reliably. `render()` removes `.stream-output` and looks for an inline `<style>` element to append `agentStyles`, yet base `Component` styling is driven by `adoptedStyleSheets`, not inline style tags. In the normal path `style` is absent, so `agentStyles` does not attach. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:119` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:91` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:299` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css:1`
- Major inconsistency: `NTTAgentLive` and `NTTChat` embed inline `<style>${...styles}</style>` strings and never use their adjacent CSS files, while `NtxAgent` constructs a `CSSStyleSheet` from a JS string. The result is three different styling contracts inside one package. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:33` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:39` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:31` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css:1` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css:1` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.css:1`
- Contract leak: `ntx-chat` treats non-streaming results as `{ answer } | { result } | arbitrary JSON.stringify(data)`, so its response contract is intentionally loose and model-specific. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:103`

## Form and Widget Contracts

### `Formidable`

- Strength: the contract is centralized and explicit. `getForm()` delegates to `_getLayout()`, `getHeader()`, grouped/ungrouped rendering, then `getInput()` and `getListInput()`. `packages/n3tx-ui/docs/formidable.md:11` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`
- Strength: renderable fields are filtered once per `schema.__name__:mode:permissions.role` key, which is a solid performance contract for many-item lists. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:7` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:14` `packages/n3tx-ui/docs/formidable.md:143`
- Strength: effective per-field mode downgrading (`protected` or `!canEdit`) keeps backend-owned fields readable while protecting them from edit forms. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:209` `packages/n3tx-ui/docs/formidable.md:147`
- Strength: array/reference rendering is not opaque. `getListInput()` emits a predictable `.list-field` structure with count, visible items, optional `.nested-collapsed`, optional `.show-more-btn`, and optional `<ntx-ref-picker>` in edit mode. Tests rely on that exact DOM shape. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:328` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:359` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:397` `tests/frontend/tests/e2e/form-rendering-unit.spec.js:401`
- Risk: `getInput()` mutates schema definitions in place when resolving `anyOf` via `Object.assign(def, resolveAnyOf(def))`. That is a dynamic typing leak from render pass to schema object identity. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:204` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:206`
- Risk: `validationAttrs()` maps `exclusiveMinimum`/`exclusiveMaximum` to plain HTML `min`/`max`, which cannot represent strictness. Client-side validation therefore only approximates the backend schema in those cases. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:181` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:187` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:189`
- Risk: `refInput()` and `getArrayInput()` are exported but not part of the documented interface, and `refInput()` calls `getForm(schema)` with the wrong argument shape if used literally. They look like leftover surfaces rather than supported APIs. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:45` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:53` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:417` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:607`

### Widget Contract

- Strength: the base widget contract is simple and consistent enough for extension: three render modes plus validation and helpers. `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:21` `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:48` `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:60`
- Strength: registry lookup returns both `widget` and `config`, so widgets remain stateless and schema-configured. `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:31` `packages/n3tx-ui/docs/widgets.md:24`
- Strength: built-in widgets respect graceful degradation for optional third-party libraries (`marked`, `AnsiUp`). `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17` `packages/n3tx-ui/src/n3tx_ui/static/widgets/ConsoleWidget.js:17` `packages/n3tx-ui/docs/widgets.md:163`
- Intentional asymmetry: `display()` and `edit()` return DOM nodes while `list()` returns a string. That is documented, tested in call sites, and architecturally relied upon by `Formidable` and `NTTItem.sm()`. `packages/n3tx-ui/docs/widgets.md:157` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:238` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:314`
- Risk: widget activation requires both registry presence and `def.ui.widget`. This is fine internally but means application authors cannot globally “upgrade” a type without schema changes. That is additive, but not especially ergonomic. `packages/n3tx-ui/docs/widgets.md:159` `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:33`
- Risk: `ReferenceWidget` uses hash-based `href="#/${model}/${value}"`, which is a frontend-local navigation contract distinct from the rest of the system's direct use of `ref`/`$id` URLs and Router route strings. It works, but it is another route grammar. `packages/n3tx-ui/src/n3tx_ui/static/widgets/ReferenceWidget.js:16` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:327`

## Theme API and `light-theme.css` Investigation

### What Exists

- `light-theme.css` exists at `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css` and defines overrides under `[data-theme="light"]`, primarily by replacing CSS custom properties and a handful of scoped body/topbar selectors. `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11` `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:87` `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:115`
- `dark-theme.css` is the base theme file that defines the shared token set on `:root` and global element styles on `body`, headings, buttons, inputs, and layout helpers. `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:11` `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:109` `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:242` `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:294`

### Who References It

- Examples reference both `dark-theme.css` and `light-theme.css` in their page head: `examples/core`, `examples/actors`, `examples/grants`, `examples/pygentic`, app `veille`, and `schema.html` all do so explicitly. `examples/core/static/index.html:7` `examples/actors/static/index.html:7` `examples/grants/static/index.html:7` `examples/pygentic/static/index.html:7` `apps/veille/static/index.html:7` `packages/n3tx-core/src/n3tx_core/static/schema.html:7`
- Auth pages reference both theme files and `theme.js`, including package defaults and app/example copies. `packages/n3tx-ui/src/n3tx_ui/static/login.html:7` `packages/n3tx-ui/src/n3tx_ui/static/register.html:7`
- Documentation references the file as part of the official frontend inventory, which means it is part of the documented API surface, not an incidental artifact. `FRONTEND.md:88` `FRONTEND.md:90`
- `Toast.js` also documents an assumption that both theme files define the variables it uses. `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js:5`

### What the Runtime Assumes

- `theme.js` does not load or unload stylesheets. It only stores `ntx-theme`, sets `document.documentElement.dataset.theme`, and dispatches `theme-change`. That means the page contract is: the relevant CSS files must already be linked, and runtime switching only flips an attribute. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:8` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:20`
- `theme.js` defaults to `dark` and only applies `dataset.theme` eagerly when the saved theme differs from default. This only works because `dark-theme.css` is the base stylesheet, while `light-theme.css` is an override gated by `[data-theme="light"]`. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:9` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:29` `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:3`
- `NTTTopbar` listens for `theme-change` and rerenders the theme toggle label/icon, but the rest of the system relies on CSS variable changes alone. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:75` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:161`

### What This Says About the API Surface

- The real public theme contract is not “call `toggleTheme()`”; it is “include both theme stylesheets, include `theme.js`, and write component CSS against shared variables.” That contract is real, stable, and used everywhere, but under-documented. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `examples/core/static/index.html:7` `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:4`
- Because `setTheme()` accepts any string and does not validate `'dark'|'light'`, the contract is partly implicit. Invalid values silently persist to localStorage and dispatch a theme-change event while matching no light-theme selectors. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:16` `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`
- Tests explicitly verify both dark and light behavior, no CSS 404s, localStorage-driven pre-application, and distinct screenshots. That elevates `light-theme.css` from optional nicety to tested contract. `tests/frontend/tests/e2e/css-and-theming-unit.spec.js:160` `tests/frontend/tests/e2e/css-and-theming-unit.spec.js:454` `tests/frontend/tests/e2e/css-and-theming-unit.spec.js:473`

## Error Handling Contracts

### Good Patterns

- `NTTElement.ERROR` centralizes UI-facing entity errors and converts backend validation errors into actionable field messages. `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:134` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:151`
- `Toast.showToast()` is null-safe on empty messages, injects styles once, and returns the created element for programmatic dismissal. `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js:47` `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js:108` `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js:133`
- `Permissions.init()` deduplicates its fetch and invalidates cached rule evaluation on auth change. `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38` `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:67`
- `NTTStream.STREAM_ERROR()` and `NTTStreamAgent.STREAM_ERROR()` both translate transport errors into visible UI and toasts. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:94` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:102`

### Weak Patterns

- `NTTMethod.load()` handles many failures by logging and returning without rendering any fallback state. Missing model, missing instance, or missing method schema produce silent visual emptiness unless the console is inspected. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:63` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:73` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:83`
- `theme.js` assumes `localStorage`, `document`, and `document.documentElement` are available at import time; there is no guard for restricted environments beyond the browser usage assumption. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:12` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:29`
- `NTTRefPicker._submitCreate()` does no client-side schema validation before sending create requests, unlike list modal create and row create flows that use `Formidable.validateForm()`. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:151` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js:272` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:240`
- `NTTRefPicker` error handling is almost nonexistent; create/add flows optimistically dispatch events and close UI without waiting for backend confirmation. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:232` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:267`

## Type Safety and Dynamic Typing Leaks

- The entire subsystem is runtime-schema-driven, so type safety is intentionally soft on the frontend. That is acceptable, but several places leak that softness into surprising behavior. `docs/CORE.md:109` `FRONTEND.md:127`
- `Component.value` only checks `typeof`, which means any object shape passes for entity mode and any array element shape passes for list mode. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:243`
- `NTTMethod.handleInput()` treats all non-checkbox values as strings and only creates nested objects through dot notation. Numeric coercion does not happen there. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:89` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:95`
- `Formidable.getInput()` mutates schema definitions for `anyOf` fields, which makes future consumers observe narrowed definitions whether they asked for them or not. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:204` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:206`
- `setTheme(theme)` accepts arbitrary strings while JSDoc narrows to `'dark'|'light'`; runtime does not enforce that type contract. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:11` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:16`
- `NTTRefPicker.childTable` falls back to `this.modelName?.toLowerCase() + 's'`, which yields `'undefineds'` when `model` is absent. The unit test codifies that exact bug-shaped contract. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:58` `tests/frontend/tests/components/ntx-ref-picker.test.js:220`
- `ReferenceWidget.display()` emits `#/${model}/${value}` for primitive refs, which assumes the value is an ID and that the app route shape matches this exact pattern; the type system cannot defend against mismatch. `packages/n3tx-ui/src/n3tx_ui/static/widgets/ReferenceWidget.js:14` `packages/n3tx-ui/src/n3tx_ui/static/widgets/ReferenceWidget.js:16`

## Real Usage Patterns Consumers Rely On

### Page Shell Contract

- Consumers routinely include both theme stylesheets, preload component CSS, optionally load vendor libraries, import `theme.js`, and then import a curated set of components in a module script. This is the de facto integration recipe. `examples/core/static/index.html:7` `examples/core/static/index.html:10` `examples/core/static/index.html:20` `examples/core/static/index.html:56` `examples/core/static/index.html:73`
- The page shell commonly combines `<ntx-topbar>`, `<ntx-sidebar router="main">`, and `<ntx-router name="main">` as the application chrome. That trio is the effective design-system layout primitive. `examples/core/static/index.html:60` `examples/grants/static/index.html:65` `examples/pygentic/static/index.html:61` `apps/veille/static/index.html:219`

### Default Entity/List Usage

- Most examples use `<ntx-list model="..."></ntx-list>` and `<ntx-table model="..."></ntx-table>` directly, relying on default renderers, permissions, and forms rather than subclassing. `examples/core/static/index.html:62` `examples/grants/static/index.html:67` `examples/grants/static/index.html:68` `apps/veille/static/index.html:221`
- `schema.html` exercises raw `<ntx-item ref="Product/1" display="xs|sm|md|lg">` usage, confirming that `ref`-based direct mounting is a first-class public contract. `packages/n3tx-core/src/n3tx_core/static/schema.html:42` `packages/n3tx-core/src/n3tx_core/static/schema.html:54` `packages/n3tx-core/src/n3tx_core/static/schema.html:64` `packages/n3tx-core/src/n3tx_core/static/schema.html:73`

### Agent UX Usage

- Agent-facing examples use `<ntx-chat>`, `<ntx-agent-live>`, and custom `item-tag="ntx-agent"` overrides to get richer agent presentation without changing backend models. That is a good additive customization story. `examples/actors/static/index.html:72` `examples/pygentic/static/index.html:64` `examples/pygentic/static/index.html:74` `examples/grants/static/index.html:78`

### Auth and Theme Usage

- Auth pages bypass the component system entirely and use plain forms with `fetch('/users/login')` or `fetch('/users/register')`, localStorage token writes, and redirect flows. They still depend on the theme contract. `packages/n3tx-ui/src/n3tx_ui/static/login.html:132` `packages/n3tx-ui/src/n3tx_ui/static/register.html:136`
- `NTTTopbar` is the only component that integrates directly with `theme-change` and `permissions.init()` to adapt its own UI. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:70` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:75`

### Tests as API Documentation

- Unit tests heavily encode expected DOM shape and API behavior for `ntx-item`, `ntx-method`, `ntx-ref-picker`, `ntx-topbar`, `ntx-sidebar`, and `Formidable`; e2e tests depend on exact CSS class names and structure like `.currency-display`, `.list-field`, `.nested-collapsed`, `.show-more-btn`, `.ntx-group-*`. `tests/frontend/tests/components/ntx-item.test.js:51` `tests/frontend/tests/components/ntx-method.test.js:38` `tests/frontend/tests/components/ntx-ref-picker.test.js:365` `tests/frontend/tests/generators/form.test.js:56` `tests/frontend/tests/e2e/form-rendering-unit.spec.js:21` `tests/frontend/tests/e2e/form-rendering-unit.spec.js:271`
- That means many “internal” CSS class names are already consumer-facing contracts in practice, because test suites and example code depend on them. `tests/frontend/tests/e2e/form-rendering-unit.spec.js:403` `tests/frontend/tests/e2e/form-rendering-unit.spec.js:494`

## Import Contracts Between Packages

### What Works Well

- The merged static namespace is documented and conceptually simple from the browser's perspective: all packages publish into one URL tree, so `./core/...`, `./components/...`, and `./widgets/...` resolve cleanly at runtime. `FRONTEND.md:23` `FRONTEND.md:117`
- Examples capitalize on that by importing core, ui, and agent modules from one flat static root without caring which package supplied them. `examples/actors/static/index.html:84` `examples/actors/static/index.html:94` `examples/pygentic/static/index.html:86` `examples/pygentic/static/index.html:99`

### Where the Contract Leaks

- In source, agent components import sibling `./ntx-stream.js` and `../utils/Toast.js` as if those files live in the same package tree. They do not; those imports only make sense because deployment merges static roots into a synthetic namespace. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:2`
- `vitest.config.js` mirrors that namespace with aliases, but only one exact agent override (`ntx-chat.js`) is defined atop the generic `components/` alias. This is a sign that package-local import semantics are not naturally reproducible in tests. `tests/frontend/vitest.config.js:24` `tests/frontend/vitest.config.js:29`
- The result is a contract that is stable for the browser but brittle for tooling, source inspection, and standalone package development. That is tolerable for internal use, but it is not a clean public package-boundary API. `FRONTEND.md:23` `tests/frontend/vitest.config.js:17`

## Naming Analysis

- The system mixes `NTT*` class names, `ntx-*` custom-element tags, and one divergent `NtxAgent` class name. That divergence is small but unnecessary friction in an otherwise regular naming scheme. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:26` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:24`
- `ref` is the public component attribute, but examples also sometimes think in terms of `href`, `$id`, and `model/id` addresses. The design is powerful, yet the naming surface is not singular. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:202` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:98` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:108`
- `Component.ALIASES` is a nice naming affordance (`pill`, `list-item`, `card`, `detail`, `page`, `row`), but docs and examples mostly use raw size names. That makes the alias API effectively secondary. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:26` `packages/n3tx-ui/docs/components.md:137`
- `forward` on `ntx-method` and `refInput()` in `Formidable` are examples of names that imply meaningful supported behavior while the implementation does not. Those should either become real APIs or disappear. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:28` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:45`

## Parameter Validation and Return Value Contracts

### Validation Strengths

- `Formidable.validateForm()` covers required, string lengths/patterns, numeric ranges, and widget-specific validation, which is a strong frontend preflight relative to many schema-driven systems. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:523` `packages/n3tx-ui/docs/formidable.md:82`
- `CurrencyWidget.validate()`, `UrlWidget.validate()`, `EmailWidget.validate()`, and `DateWidget.validate()` provide specialized checks consistent with schema-driven widget selection. `packages/n3tx-ui/src/n3tx_ui/static/widgets/CurrencyWidget.js:44` `packages/n3tx-ui/src/n3tx_ui/static/widgets/UrlWidget.js:25` `packages/n3tx-ui/src/n3tx_ui/static/widgets/EmailWidget.js:22` `packages/n3tx-ui/src/n3tx_ui/static/widgets/DateWidget.js:44`

### Validation Weaknesses

- `NTTMethod` does no equivalent validation, even though method schemas are present. Inline and fieldset method calls trust DOM values directly. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:89` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:102`
- `NTTRefPicker._submitCreate()` parses booleans/numbers/objects but does not validate required or constrained fields before dispatch. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:240`
- `theme.js.setTheme()` validates nothing. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17`

### Return Value Contracts

- `Formidable.getForm()` / `getInput()` / `getListInput()` return HTML strings, not DOM fragments. Consumers insert them into templates and later bind listeners. `packages/n3tx-ui/docs/formidable.md:45` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`
- `Widget.display()` / `edit()` return DOM nodes, while `Widget.list()` returns plain strings or simple HTML string fragments. This is a genuine API asymmetry that extension authors must learn. `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:21` `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:33` `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:48`
- `NTTMethod._response_()` accepts arbitrary `data` and stores it as `this.response`; only rendering code decides how to display it. There is no typed response contract at the component layer. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117`
- `showToast()` returns the toast element, but most call sites ignore the return value and rely on auto-dismiss. `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js:106` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:149`

## Documentation Gaps

- The docs explain that `light-theme.css` exists, but they do not state the concrete integration requirement that pages must link both `dark-theme.css` and `light-theme.css` for runtime theme switching to work. `FRONTEND.md:88` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `examples/core/static/index.html:7`
- The docs present a clean widget contract, but the exported `Formidable` surface is larger and messier than the docs describe (`refInput`, `getArrayInput`). That mismatch invites accidental use of underspecified helpers. `packages/n3tx-ui/docs/formidable.md:45` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:607`
- The docs do not mention that agent component styling diverges from the `Component.styles` convention and, in one case, is likely broken. `FRONTEND.md:83` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113`
- `components.md` documents `NTTModal`, `NTTRefPicker`, `NTTTopbar`, `NTTSidebar`, `NTTProfile` as standalone components, but their attribute and event contracts are scattered across source comments rather than gathered in one table. `packages/n3tx-ui/docs/components.md:58` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:8` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:7`
- Tests encode important API expectations that the docs do not, including DOM class names and the exact list-field collapse structure. `tests/frontend/tests/e2e/form-rendering-unit.spec.js:401` `packages/n3tx-ui/docs/formidable.md:151`

## Risks and Mismatches

### High-Risk

- `NTTStreamAgent` styling appears miswired: shipped CSS file exists, JS does not load it, and runtime fallback looks for a non-existent inline `<style>`. This is an API inconsistency and a probable presentation bug. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:299` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css:1`
- Package-boundary imports in agents depend on the merged namespace illusion, which complicates source-level reasoning and tooling. `FRONTEND.md:23` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17` `tests/frontend/vitest.config.js:18`
- `NTTMethod` exposes stale/ghost API hints (`forward`, missing static styles expected by tests), which makes the surface look more stable than it is. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:28` `tests/frontend/tests/components/ntx-method.test.js:822`

### Medium-Risk

- `Formidable` mutates schema defs during render and exports leftover helpers, both of which make the module harder to treat as a pure renderer. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:204` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:607`
- Theme switching is under-validated and under-documented. Consumers can accidentally persist unsupported theme values or omit the light stylesheet. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`
- `NTTRefPicker` create/add flows are optimistic and validation-light compared with the rest of the system's create UX. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:232` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:240`

### Low-Risk / Quality-of-Life

- Pluralization via `${this.model}s` is simplistic in list/table headers. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:277`
- Naming is slightly inconsistent (`NtxAgent`). `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:24`
- Browser-native `confirm()` is used for destructive actions instead of `NTTModal`, which is simpler but less design-system-consistent. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:81` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:58`

## Recommendations

### 1. Normalize Styling Contracts Across Packages

- Make every agent component participate in the same `Component.styles` external-sheet contract as `n3tx-ui`, or explicitly standardize on inline `CSSStyleSheet` strings across all packages; the current mixed model is the largest API inconsistency in the subsystem. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:258` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:33` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:31`
- Either wire `ntx-stream-agent.css` through `styles` or remove the dead file and encode a single source of truth. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css:1`

### 2. Tighten the Theme Contract

- Document the page-level requirement explicitly: link `dark-theme.css`, link `light-theme.css`, import `theme.js`, and author component/page CSS against shared variables. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `examples/core/static/index.html:7`
- Validate `setTheme()` inputs and no-op or warn on unsupported values. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:16`

### 3. Trim or Formalize Soft APIs

- Remove or implement `forward` in `NTTMethod`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:28` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:53`
- Remove or document `Formidable.refInput()` and `Formidable.getArrayInput()`; right now they widen the apparent public surface without corresponding guarantees. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:45` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:417` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:607`
- Reconcile `ntx-method` tests with real implementation or restore the missing static style exports. `tests/frontend/tests/components/ntx-method.test.js:822` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:305`

### 4. Make Validation More Uniform

- Reuse `Formidable.validateForm()` or an equivalent schema-based validator inside `NTTMethod` and `NTTRefPicker` before dispatching payloads. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:102` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:240` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:151`

### 5. Clarify Package Import Semantics

- Document the merged-static-namespace import illusion as a first-class build/runtime contract, including how tests emulate it, because it is necessary context for anyone extending agent UI. `FRONTEND.md:23` `tests/frontend/vitest.config.js:18`

## Final Judgment

- The design-system API surface is fundamentally good at the level that matters most to N3TX: schema-driven entity rendering, method invocation, permission adaptation, widget dispatch, and additive component composition all work from backend-authored contracts and are exercised in examples and tests. `docs/CORE.md:109` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:380` `tests/frontend/tests/integration/form-entity-binding.test.js:33`
- The subsystem is weakest where the contract is page-authored or package-boundary-authored instead of schema-authored: themes, auth pages, agent styling, and merged import paths. Those are the places where the public API becomes implicit, inconsistent, or documented only by example. `packages/n3tx-ui/src/n3tx_ui/static/login.html:7` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113` `FRONTEND.md:23`
- In short: the core design-system contracts are strong and aligned with N3TX philosophy; the shell/theme/agent edges need cleanup so the subsystem is as composable and transparent at the boundaries as it already is at the schema-rendering center. `docs/CORE.md:111` `FRONTEND.md:129` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:26` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:24`

## Appendix — Highest-Signal Contract Deltas

| Delta | Why it matters | Evidence |
|---|---|---|
| `NTTStreamAgent` CSS path is inconsistent with `Component.styles` | Extension authors cannot rely on one styling convention across packages | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css:1` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:258` |
| `light-theme.css` is a real public file, not just an implementation detail | Missing it breaks runtime theme switching while `theme.js` still appears to work | `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11` `examples/core/static/index.html:7` |
| `forward` is a parsed but inert attribute on `ntx-method` | Consumers may assume an unsupported routing/forwarding behavior exists | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:28` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:53` |
| `Formidable` exports more than its docs advertise | The effective API surface is wider and less curated than documentation implies | `packages/n3tx-ui/docs/formidable.md:45` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:607` |
| Tests depend on DOM class names and shape, not just visible behavior | CSS class names like `.list-field`, `.nested-collapsed`, `.currency-display`, `.ntx-group-*` are already compatibility surfaces | `tests/frontend/tests/e2e/form-rendering-unit.spec.js:21` `tests/frontend/tests/e2e/form-rendering-unit.spec.js:271` `tests/frontend/tests/e2e/form-rendering-unit.spec.js:401` |
| Merged static namespace is a runtime contract with source-level cost | The browser sees one namespace, but source packages do not; tooling must emulate that | `FRONTEND.md:23` `FRONTEND.md:117` `tests/frontend/vitest.config.js:18` |
