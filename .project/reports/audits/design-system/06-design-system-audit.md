# Design-System -- Deep Audit Report

## Executive Summary
The design-system subsystem is where N3TX's schema-driven backend becomes a working frontend. It takes backend-authored schema, access rules, renderer hints, and methods and turns them into dynamic entities, web components, forms, widgets, themes, and app shells. In broad terms, it succeeds: the backend stays authoritative, the frontend adapts at runtime, and many UI changes can be made by improving schema rather than hand-writing screens. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:179` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`

The subsystem's biggest strength is its structural backbone. `Component` provides a strong shared base for schema attachment, ref resolution, adaptive display, and stylesheet loading, and the higher-level primitives build on that instead of re-implementing transport or bootstrap logic. That gives the engineering team good leverage: once a model schema is sound, much of the UI comes along with it. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:91` `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:63` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:43` `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:22`

Most of the real problems sit at the subsystem's edges. There are confirmed correctness bugs in method response rendering, async ref-picker freshness, and agent chat instance loading. More importantly, there is a serious security issue: several rendering paths still push unescaped values or unsanitized markdown into `innerHTML`, which creates an avoidable XSS surface. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:110` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:218` `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17`

The other major weakness is implicitness. Theme loading, auth-sensitive layout caching, and shell bootstrapping all work, but too much of the contract lives in convention instead of explicit APIs. `light-theme.css` is present and shipped, but pages still depend on authors remembering the right combination of theme assets and boot scripts. `Permissions` and `Formidable` also cache aggressively without a fully explicit invalidation story, which makes the system harder to reason about during login, logout, and role changes. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1` `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`

The top three recommendations are straightforward. First, harden every HTML and markdown rendering path so the design system stops trusting backend and LLM text by default. Second, add explicit invalidation for permission and layout caches so auth changes cannot leave stale UI behind. Third, replace manual shell-level asset choreography with a canonical theme and frontend entrypoint contract. Those three investments would improve resilience, reduce debugging drag, and make the subsystem easier for new engineers to extend safely. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:160` `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38` `examples/core/static/index.html:7`

The strongest forward-looking propositions build on the same theme: make implicit contracts explicit. The highest-value changes are to define a single canonical theme entrypoint, formalize layered stylesheet and import boundaries so source structure matches runtime reality, and split `Formidable` into clearer planning and rendering responsibilities. Together, those changes would lower cognitive load, improve composability, and make the design system more stable as more apps and agent surfaces are added on top. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:28` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:262` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`

## Component Overview
The subsystem spans three frontend layers and one deployment convention:

- `n3tx-core/static/` provides the non-visual runtime: actor transport, `NTT`, `Component`, config, permissions, logging, theme utilities.
- `n3tx-ui/static/` provides the visual system: entity/list/method/router components, forms, widgets, themes, auth shells, default HTML.
- `n3tx-agents/static/` provides agent-specific visual extensions layered on the base stream and item components.
- Runtime static serving merges all three into one URL namespace; tests emulate that merged namespace with aliases in `tests/frontend/vitest.config.js`. `FRONTEND.md:19` `FRONTEND.md:23` `FRONTEND.md:83` `tests/frontend/vitest.config.js:18`

Consolidated component map:

```text
Backend model definitions
  |
  |  ProtoModel.schema() emits: properties, ui, access, methods, $defs
  v
JSON Schema contract
  |
  +--> NTT / DynamicClass bootstrap (`n3tx-core/static/core/NTT.js`)
  |       |
  |       +--> entity instances with $id/$schema
  |       +--> READ/CREATE/UPDATE/DELETE/method calls
  |
  +--> Permissions (`utils/Permissions.js`)
  |       |
  |       +--> field visibility/editability
  |       +--> action gating
  |
  +--> Component (`core/Component.js`)
          |
          +--> NTTElement ------------------------------+
          |       |                                     |
          |       +--> ntx-item                         |
          |       +--> ntx-row                          |
          |       +--> ntx-user                         |
          |                                             |
          +--> ListElement -----------------------------+--> Formidable (`generators/form.js`)
          |       |                                     |       |
          |       +--> ntx-list                         |       +--> widgets registry
          |       +--> ntx-table                        |       +--> ntx-ref-picker
          |                                             |
          +--> ntx-method ------------------------------+
                  |
                  +--> ntx-stream
                          |
                          +--> ntx-stream-agent
                          +--> ntx-agent-live
                          +--> ntx-chat

Standalone shell/UI components
  +--> ntx-topbar
  +--> ntx-sidebar
  +--> ntx-router
  +--> ntx-modal
  +--> ntx-profile

Global style and shell layer
  +--> dark-theme.css
  +--> light-theme.css
  +--> auth.css
  +--> login.html / register.html / schema.html / example app shells

Deployment convention
  +--> merged static namespace at runtime
  +--> Vitest aliases emulate merged namespace in tests
```

Relationship notes:

- `Component` is the subsystem's deepest frontend primitive because it owns both runtime binding and style adoption. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:91`
- `Formidable` is the universal field renderer, but it is tightly coupled to `Permissions`, widgets, and `ntx-ref-picker`. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:1` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:5`
- `NTTStream` is the bridge from generic method invocation to progressive streaming; agent components layer on that rather than bypassing it. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:43` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:4`
- Static namespace merging simplifies browser imports but obscures package ownership in source and tooling. `FRONTEND.md:23` `tests/frontend/vitest.config.js:18`

## Key Findings

### Critical Issues

#### C1. Unescaped HTML and unsanitized markdown create a high-severity XSS surface
- Finding
  The design system still treats backend data and LLM output as trusted in multiple rendering paths. Raw values are interpolated into HTML strings in `Formidable` and `NTTItem`, and markdown is parsed straight into `innerHTML` in both widget and agent UIs.
- Evidence with file:line reference and code snippet

  `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:160`
  ```js
  if (mode === 'edit') {
      headerHtml.push(`<input style="font-size: 1.5rem" type="text" id="${nameKey}" data-key="${nameKey}" data-type="string" value="${name}">`);
  } else {
      headerHtml.push(`<h2 class="${schema.name}" data-value="${nameKey}">${name}</h2>`);
  }
  ```

  `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:233`
  ```js
  xs() {
    const name = this.value.name || this.value.title || this.schema.__name__;
    return `<span class="pill-label" data-value="name">${name}</span>`;
  }
  ```

  `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17`
  ```js
  if (typeof marked !== 'undefined' && marked.parse) {
      div.innerHTML = marked.parse(String(value));
  }
  ```

  `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:214`
  ```js
  if (typeof marked !== 'undefined' && marked.parse) {
      content.innerHTML = marked.parse(buf);
  }
  ```
- Severity
  Critical
- Recommendation
  Introduce one shared safe-render layer: escape all plain text interpolations, sanitize all markdown output, and make unsafe HTML opt-in rather than default. Address this before any major feature work in agent or widget surfaces.

#### C2. Permission and layout cache invalidation is incomplete, leaving stale auth-sensitive UI state
- Finding
  `Permissions` memoizes its fetch promise forever, and `Formidable` caches layout by model name, mode, and role only. There is no production-integrated reset flow when auth state changes, which can leave stale field visibility and layout decisions during long-lived sessions.
- Evidence with file:line reference and code snippet

  `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38`
  ```js
  init() {
    if (this.#promise) return this.#promise;

    this.#promise = this.#fetchUser();
    return this.#promise;
  }
  ```

  `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`
  ```js
  function _getLayout(schema, mode) {
      const cacheKey = `${schema.__name__ || schema.title || ''}:${mode}:${permissions.role}`;
      const cached = _layoutCache.get(cacheKey);
      if (cached) return cached;
  }
  ```
- Severity
  Critical
- Recommendation
  Add explicit `permissions.refresh()` and `permissions.reset()` APIs, include schema identity in layout-cache keys, and call `Formidable.clearCache()` plus permission refresh on login, logout, token refresh, and any in-app auth transition.

#### C3. `ntx-method` stores real responses but does not rerender them
- Finding
  Method calls optimistically render a `sent` state, but when the actual reply arrives `_response_()` only mutates internal state and pulls the entity. The component never rerenders its own response area, so the user can be left staring at stale feedback.
- Evidence with file:line reference and code snippet

  `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:102`
  ```js
  callMethod() {
    caller.call(this.method, { ...this.value }, { inbox: '_response_' });
    this.response = { status: 'sent' };
    this.#postCall();
  }
  ```

  `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117`
  ```js
  _response_(data, tx) {
    this.response = data;
    if (this.ntt?.pull) this.ntt.pull();
    else if (this.proto?.pull) this.proto.pull();
  }
  ```
- Severity
  Critical
- Recommendation
  Call `render()` from `_response_()` for fieldset and button layouts, and preserve the inline-layout special case explicitly rather than relying on side effects from entity refreshes.

#### C4. `ntx-ref-picker` issues async reads but never refreshes options after data arrives
- Finding
  The picker correctly detects an empty instance map and requests `READ`, but then renders immediately from the current empty map and never subscribes for a follow-up refresh. This is a real stale-data UX bug.
- Evidence with file:line reference and code snippet

  `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:110`
  ```js
  if (!DC.instances || DC.instances.size === 0) {
    DC.call('READ', {});
  }
  ```

  `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:130`
  ```js
  const renderOptions = (filter = '') => {
    optionsDiv.innerHTML = '';
    const instances = DC.instances || new Map();
    let count = 0;
    instances.forEach((entity) => {
  ```
- Severity
  Critical
- Recommendation
  Observe the DynamicClass or await the read promise before first render; then rerender the option list when instances change instead of only when the search box changes.

#### C5. `ntx-chat` hardcodes a non-canonical `/api/` endpoint and duplicates transport knowledge
- Finding
  The chat panel bypasses the framework's runtime/entity abstractions and fetches instances directly from `/api/${tablename}`. That duplicates backend contract knowledge, conflicts with the documented route model, and weakens the backend-authoritative principle.
- Evidence with file:line reference and code snippet

  `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:218`
  ```js
  #loadInstances() {
      const tablename = this.schema?.__tablename__ || this.model?.toLowerCase() + 's';
      const url = `/api/${tablename}`;
      HTTP.get(url, (resp) => {
          this.#items = resp.data || resp || [];
  ```
- Severity
  Critical
- Recommendation
  Resolve instances through `NTT`/DynamicClass metadata or through canonical `href`/`schema.__tablename__` paths derived from the existing runtime, not a chat-local hardcoded URL grammar.

#### C6. Theme integration works today, but the contract is implicit and asymmetric
- Finding
  `light-theme.css` is present and correctly shipped; the real gap is that light mode depends on a shell remembering to link both theme files and import `theme.js`, while dark mode acts as the unqualified base. That asymmetry creates avoidable operational fragility and made earlier analysis overestimate the likelihood of a missing-file defect.
- Evidence with file:line reference and code snippet

  `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:28`
  ```js
  // Auto-apply on import — runs before first paint if script is in <head>
  const saved = getTheme();
  if (saved !== DEFAULT_THEME) {
      document.documentElement.dataset.theme = saved;
  }
  ```

  `packages/n3tx-ui/src/n3tx_ui/static/login.html:7`
  ```html
  <link rel="stylesheet" href="./dark-theme.css" />
  <link rel="stylesheet" href="./light-theme.css" />
  <script type="module" src="./utils/theme.js"></script>
  ```
- Severity
  Critical
- Recommendation
  Make theme state explicit for both dark and light, ship a single canonical `theme.css`, and reduce the shell contract to one stylesheet plus one boot module.

### Design Strengths
- `Component` is a deep primitive that solves real cross-cutting problems once: actor identity, schema binding, ref routing, adaptive display, and constructable stylesheet reuse. This is exactly the kind of "primitives, not opinions" module the codebase should preserve. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:91` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:183` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:299`
- Schema consumption is genuine, not decorative. `Formidable`, `NTTItem`, `ListElement`, `NTTMethod`, and `Permissions` all consume schema fields, `ui`, `access`, `methods`, and `$defs` directly. That keeps the backend authoritative and frontend duplication low. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58` `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:134` `docs/CORE.md:144`
- List child customization is unusually strong. Template stamping, `item-tag`, subclass overrides, backend `ui.renderer.item`, and default fallback all compose cleanly. This is one of the subsystem's clearest additive-customization wins. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:173`
- Agent UI is layered on the correct base abstraction. `NTTStreamAgent`, `NTTAgentLive`, `NTTChat`, and `NtxAgent` extend `NTTStream` or `NTTItem` rather than bypassing runtime transport. Current source also shows agent components using external CSS via `get styles()`, resolving an earlier inconsistency reported in some analysis notes. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:6` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:22` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:26` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:26`
- Theme files do exist and follow a variable-driven model. The subsystem does not have a missing `light-theme.css` problem today; it has a contract-clarity problem. That distinction matters and should be preserved in future planning. `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1` `FRONTEND.md:88`

### Design Trade-offs
- Runtime merged static namespace
  - Gained: browser imports are simple and app shells can consume core/ui/agents from one flat URL space.
  - Sacrificed: source-level package ownership is harder to read because imports reflect deployed namespace more than repository layout.
  - Still makes sense: yes at runtime, but not as the only visible import contract. The subsystem now needs explicit virtual import roots so tooling and source reading match deployment intent. `FRONTEND.md:23` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`
- HTML-string rendering in `Formidable` and `NTTItem`
  - Gained: very transparent render flow, easy surgical patching, and low ceremony for generated UI.
  - Sacrificed: safety and composability; escaping discipline becomes manual and easy to miss.
  - Still makes sense: only if wrapped in a mandatory safe-render utility. In its current form the trade-off is no longer acceptable. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:232`
- Manual shell composition
  - Gained: no bundler magic, explicit preloads, very inspectable page startup.
  - Sacrificed: repetition, drift risk, and high hidden knowledge cost for new apps.
  - Still makes sense: partially. The right evolution is a canonical entrypoint plus optional advanced manual composition for expert cases. `examples/core/static/index.html:7`
- Backend-authoritative runtime adaptation
  - Gained: the frontend avoids parallel model definitions and benefits immediately from backend schema improvements.
  - Sacrificed: static typing on the client is intentionally soft, and some runtime checks are necessarily shallow.
  - Still makes sense: absolutely. This is a core N3TX differentiator and should remain intact while its weak spots are hardened. `docs/CORE.md:109` `packages/n3tx-core/src/n3tx_core/static/core/Component.js:243`
- Standalone shell components outside `Component`
  - Gained: simpler implementation for global shell primitives like topbar, modal, and profile.
  - Sacrificed: inconsistent style-loading and lifecycle patterns compared to the main component system.
  - Still makes sense: sometimes, but only if a shared standalone-style utility exists; today the pattern is too ad hoc. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:62` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:122`

### Improvement Opportunities

| # | Improvement | Impact | Effort | Category |
|---|---|---|---|---|
| 1 | Sanitize markdown and escape all HTML-string render paths | High | Medium | Security |
| 2 | Add `permissions.refresh/reset` and schema-sensitive form cache keys | High | Medium | Resilience |
| 3 | Fix `ntx-method` response rerender | High | Small | Correctness |
| 4 | Fix `ntx-ref-picker` async refresh | High | Small | Correctness |
| 5 | Remove `ntx-chat` `/api/` hardcoding | High | Small | Contract hygiene |
| 6 | Ship canonical `theme.css` and explicit theme boot | High | Medium | Shell/theming |
| 7 | Replace manual shell boot graphs with entrypoints/manifests | High | Medium | DX |
| 8 | Formalize `stylesheets` layering API | Medium-High | Small | Component composition |
| 9 | Remove app-specific selectors from `ntx-item.css` | Medium | Medium | Cohesion |
| 10 | Wire `auth.css` into login/register or remove it | Medium | Small | Shell hygiene |
| 11 | Replace stale `example.html` with canonical shell docs/examples | Medium | Small | Documentation |
| 12 | Add asset-smoke and agent-component frontend tests | Medium | Medium | Test resilience |

## Strategic Propositions

### Simplification Propositions

#### P1. Make theme state symmetric and explicit
- Current state with file:line references
  Dark is the implicit base, light is a selector-scoped override, and boot only writes `data-theme` when the saved theme differs from dark. Shells must link both theme files manually. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:8` `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:28` `packages/n3tx-ui/src/n3tx_ui/static/login.html:7`
- Proposed change with code sketches or API signatures

  ```js
  // packages/n3tx-core/src/n3tx_core/static/utils/theme.js
  const THEMES = new Set(['dark', 'light']);
  const STORAGE_KEY = 'ntx-theme';
  const DEFAULT_THEME = 'dark';

  export function resolveTheme() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return THEMES.has(stored) ? stored : DEFAULT_THEME;
  }

  export function applyTheme(theme = resolveTheme()) {
    const next = THEMES.has(theme) ? theme : DEFAULT_THEME;
    document.documentElement.dataset.theme = next;
    localStorage.setItem(STORAGE_KEY, next);
    document.dispatchEvent(new CustomEvent('theme-change', { detail: { theme: next } }));
  }
  ```

  ```css
  /* packages/n3tx-ui/src/n3tx_ui/static/theme.css */
  @import './dark-theme.css';
  @import './light-theme.css';

  /* dark-theme.css */
  [data-theme="dark"] { /* tokens */ }

  /* light-theme.css */
  [data-theme="light"] { /* tokens */ }
  ```

  ```html
  <!-- canonical shell contract -->
  <html data-theme="dark">
    <head>
      <link rel="stylesheet" href="./theme.css">
      <script type="module" src="./utils/theme.js"></script>
    </head>
  </html>
  ```

  ```js
  // optional stricter surface for callers like ntx-topbar
  export function setTheme(theme) {
    if (!THEMES.has(theme)) {
      console.warn(`[theme] Unsupported theme: ${theme}`);
      theme = DEFAULT_THEME;
    }
    applyTheme(theme);
  }
  ```
- What gets simpler
  Theme state becomes visible in devtools, all pages use one stylesheet include, the `light-theme.css` gap is reframed correctly as a contract issue rather than an asset-presence issue, and tests no longer depend on implicit dark defaults.
- Migration path
  1. Add `theme.css` as a non-breaking wrapper over `dark-theme.css` and `light-theme.css`. `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`
  2. Update `theme.js` so `data-theme` is always written on boot, not only for non-default themes. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:28`
  3. Convert dark tokens from `:root` to `[data-theme="dark"]`, but keep legacy aliases like `--border-color` and `--bg-tertiary` during the transition to avoid breaking existing component CSS. `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:45`
  4. Migrate stock shells first: `login.html`, `register.html`, and `schema.html`. `packages/n3tx-ui/src/n3tx_ui/static/login.html:7` `packages/n3tx-core/src/n3tx_core/static/schema.html:7`
  5. Migrate example shells next: `examples/core`, `examples/actors`, `examples/grants`, `examples/pygentic`, `apps/veille`. `examples/core/static/index.html:7`
  6. Only after the shell migration lands, remove the dual-link pattern from docs and examples.
  7. Add route-level smoke tests for all stock shells to verify that both themes render from the same contract.
- Dependency sequencing
  - Do `P1` before `P3` if possible, because the new entrypoints should encode the simplified theme contract rather than the current duplicated one.
  - Coordinate with token cleanup work (`F09`) so the theme-symmetry migration does not freeze the old token surface in place.
  - Do not combine this change with broad visual restyling; keep it contract-focused so regressions are easy to isolate.
- Taskable implementation slices
  - Slice 1: add `theme.css` and make no behavioral changes.
  - Slice 2: validate `setTheme()` input and always write `data-theme`.
  - Slice 3: migrate stock shells.
  - Slice 4: migrate example/app shells.
  - Slice 5: update theme tests and docs.
- Risk
  Medium: screenshot diffs and any app CSS depending on implicit dark defaults will need updates.

#### P2. Add explicit auth/layout invalidation primitives
- Current state with file:line references
  `Permissions.init()` memoizes forever and `Formidable` caches layout using only schema name, mode, and role. `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`
- Proposed change with code sketches or API signatures

  ```js
  // Permissions.js
  refresh() {
    this.#promise = null;
    this.#ready = false;
    this.#ruleCache.clear();
    return this.init();
  }

  reset() {
    this.#promise = null;
    this.#ready = false;
    this.#user = null;
    this.#ruleCache.clear();
  }
  ```

  ```js
  // form.js
  function schemaCacheKey(schema, mode) {
    const shape = JSON.stringify(schema.properties || {});
    return `${schema.__name__}:${mode}:${permissions.role}:${simpleHash(shape)}`;
  }
  ```

  ```js
  // login/register/logout integration points
  import { permissions } from '../utils/Permissions.js';
  import { Formidable } from '../generators/form.js';

  export async function onAuthChanged() {
    await permissions.refresh();
    Formidable.clearCache();
    document.dispatchEvent(new CustomEvent('permissions-change'));
  }
  ```

  ```js
  // optional schema version hook when schema metadata grows
  function schemaVersion(schema) {
    return schema.$id || schema.__name__ || JSON.stringify(schema.required || []);
  }
  ```
- What gets simpler
  Auth transitions become a supported lifecycle instead of a collection of shell-specific assumptions; cache behavior becomes legible; stale layout bugs become much rarer.
- Migration path
  1. Add `permissions.refresh()` and `permissions.reset()` without changing existing callers. `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38`
  2. Update logout flows in shell components and auth pages to call them after token mutation. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:150` `packages/n3tx-ui/src/n3tx_ui/static/login.html:132`
  3. Change `Formidable` to route all cache-key generation through one helper rather than inline string construction. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`
  4. Add schema-shape or schema-version information to the cache key.
  5. Add one integration test for same-session login and one for same-session logout with a model that hides fields by role.
  6. Only then consider more aggressive permission memoization or boot-time prefetching.
- Dependency sequencing
  - This should ship before any SPA-style shell improvements from `P3`, because entrypoints that preserve stale permission state will make the new shell contract feel unreliable.
  - If `P5` lands later, `FormLayout.plan()` should own the cache key rather than `Formidable` directly.
- Taskable implementation slices
  - Slice 1: `permissions.refresh/reset`
  - Slice 2: `Formidable` cache-key helper
  - Slice 3: shell/auth integration
  - Slice 4: regression tests around login/logout in a live session
- Risk
  Low-medium: cached performance characteristics change slightly and some tests will need new setup/teardown discipline.

#### P3. Replace manual shell boot graphs with canonical entrypoints
- Current state with file:line references
  Example and app shells manually list theme links, modulepreloads, CSS preloads, optional vendor scripts, and component imports. `examples/core/static/index.html:7` `examples/grants/static/index.html:10`
- Proposed change with code sketches or API signatures

  ```js
  // static/entrypoints/app-shell.js
  import '../theme.css';
  import '../utils/theme.js';
  import '../widgets/index.js';
  import '../components/ntx-item.js';
  import '../components/ntx-list.js';
  import '../components/ntx-router.js';
  import '../components/ntx-sidebar.js';
  import '../components/ntx-topbar.js';

  export async function boot() {
    const { permissions } = await import('../utils/Permissions.js');
    await permissions.init();
  }
  ```

  ```html
  <script type="module">
    import { boot } from './entrypoints/app-shell.js';
    await boot();
  </script>
  ```

  ```json
  {
    "entrypoints": {
      "app-shell": {
        "scripts": ["./entrypoints/app-shell.js"],
        "styles": ["./theme.css", "./widgets/widgets.css"]
      },
      "agents-shell": {
        "scripts": ["./entrypoints/agents-shell.js"],
        "styles": ["./theme.css", "./widgets/widgets.css"]
      }
    }
  }
  ```

  ```js
  // static/entrypoints/agents-shell.js
  import './app-shell.js';
  import '../components/ntx-stream-agent.js';
  import '../components/ntx-chat.js';
  import '../components/ntx-agent-live.js';
  import '../components/ntx-agent.js';
  ```
- What gets simpler
  New apps start from one documented boot surface, asset drift drops, and the shell becomes closer to "zero to working, then customize" instead of "copy the right 30 lines from another example".
- Migration path
  1. Introduce entrypoints without deleting any current manual shells. `examples/core/static/index.html:73`
  2. Convert `schema.html` first because it is framework-owned and exercises broad component coverage. `packages/n3tx-core/src/n3tx_core/static/schema.html:149`
  3. Convert stock login/register pages so shell boot is consistent even outside the component system. `packages/n3tx-ui/src/n3tx_ui/static/login.html:10`
  4. Convert `examples/core`, then `examples/actors`, then `examples/grants`, then `examples/pygentic`; leave `apps/veille` for last because it mixes framework and app-local shell logic. `apps/veille/static/index.html:245`
  5. Once converted, optionally expose a backend `_meta/frontend` manifest for preload generation rather than hand-authored `modulepreload` lists.
  6. Preserve a documented advanced path for expert apps that want fully manual imports.
- Dependency sequencing
  - Pair this with `P1` so the entrypoint uses the simplified theme contract.
  - `P6` becomes easier after this because entrypoints provide a natural place to expose virtual import roots.
  - `P8` can piggyback on the manifest side if `_meta/frontend` or `_meta/static` endpoints are added.
- Taskable implementation slices
  - Slice 1: `app-shell.js`
  - Slice 2: `agents-shell.js`
  - Slice 3: convert framework-owned shells
  - Slice 4: convert example apps
  - Slice 5: optional manifest endpoint and preload generation
- Risk
  Medium: some example-specific preload tuning will move from page markup into generated or manifest-backed framework code.

### Composability & Extensibility Propositions

#### P4. Formalize layered component CSS as `stylesheets`
- Current friction
  `Component` already accepts one stylesheet or an array through a singular `styles` hook. The behavior is layered, but the API name suggests a single-file contract, which makes inheritance patterns less obvious than they are. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:262` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:6`
- Proposed design with concrete code examples

  ```js
  export class Component extends HTMLElement {
    get stylesheets() { return []; }
    get styles() { return this.stylesheets; } // temporary back-compat bridge
  }

  export class NTTMethod extends Component {
    get stylesheets() {
      return [new URL('./ntx-method.css', import.meta.url).href];
    }
  }

  export class NTTStream extends NTTMethod {
    get stylesheets() {
      return [...super.stylesheets, new URL('./ntx-stream.css', import.meta.url).href];
    }
  }
  ```

  ```js
  export class NTTStreamAgent extends NTTStream {
    get stylesheets() {
      return [...super.stylesheets, new URL('./ntx-stream-agent.css', import.meta.url).href];
    }
  }

  export class NTTAgentLive extends NTTStream {
    get stylesheets() {
      return [
        ...super.stylesheets,
        new URL('./ntx-agent-live.css', import.meta.url).href,
        new URL('../widgets/json-tree.css', import.meta.url).href,
      ];
    }
  }
  ```
- What it enables
  More explicit style layering, easier component inheritance, clearer debugging, and a better story for future standalone/shared style utilities.
- Migration path
  1. Add `stylesheets` as a new API while preserving `styles` as a compatibility bridge. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:262`
  2. Migrate `NTTMethod`, `NTTStream`, and `NTTStreamAgent` first because they already follow layered inheritance.
  3. Migrate agent components next so JSON tree, stream, and panel CSS are expressed as ordered layers instead of ad hoc additions.
  4. Update docs to say "stylesheets layering" rather than implying a single-sheet hook. `packages/n3tx-ui/docs/components.md:181`
- Dependency sequencing
  - Independent of `P1` and `P2`.
  - Helpful for `P5`, because field-renderer decomposition benefits from a clearer component CSS story.
- Taskable implementation slices
  - Slice 1: add alias API
  - Slice 2: migrate stream family
  - Slice 3: migrate agent panels
  - Slice 4: update docs/tests
- Effort estimate
  Small-medium

#### P5. Split `Formidable` into layout planning and field-renderer registries
- Current friction
  `Formidable` mixes layout planning, field rendering, widget dispatch, and direct coordination with concrete components like `ntx-ref-picker`. That makes extension possible but convention-heavy. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:195` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:403`
- Proposed design with concrete code examples

  ```js
  export const FormLayout = {
    plan(schema, { mode, role }) {
      return {
        header: [],
        groups: [],
        fields: [
          { key: 'price', definition: schema.properties.price, effectiveMode: 'edit', renderer: 'widget:currency' }
        ]
      };
    }
  };

  export const FieldRenderers = {
    register(name, renderer) { /* ... */ },
    renderField(ctx, fieldPlan) { /* ... */ }
  };

  FieldRenderers.register('array:ref', {
    display(ctx, field) { /* ... */ },
    edit(ctx, field) { return `<ntx-ref-picker ...></ntx-ref-picker>`; },
    list(ctx, field) { /* ... */ }
  });
  ```

  ```js
  // a more explicit field plan example
  {
    key: 'comments',
    definition: schema.properties.comments,
    effectiveMode: 'edit',
    relation: { kind: 'array-ref', target: 'Comment' },
    ui: schema.properties.comments.ui || {},
    attachedMethods: [{ name: 'comment', layout: 'inline' }]
  }
  ```

  ```js
  // compatibility wrapper during migration
  export const Formidable = {
    getForm(ntt, mode = 'display', attachedMethods = {}) {
      const plan = FormLayout.plan(ntt.schema, { mode, role: permissions.role, attachedMethods });
      return FormRenderer.render(ntt, plan);
    }
  };
  ```
- What it enables
  Safer customization of field families, cleaner test seams, easier widget evolution, and less hidden coupling to `NTTItem.handleInputChange()` dataset conventions.
- Migration path
  1. Extract `_getLayout()` into `FormLayout.plan()` with no behavior change. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`
  2. Introduce `FieldRenderers` while routing all current work through a default legacy renderer.
  3. Move widget dispatch into a registered renderer.
  4. Move array-ref rendering and `ntx-ref-picker` wiring into a registered renderer.
  5. Add renderer-level tests that do not require full `NTTItem` setup.
  6. Only then decide whether widget `list()` should keep returning strings or converge on a richer return type.
- Dependency sequencing
  - Can begin before `P4`, but reads more cleanly after `stylesheets` are formalized.
  - Should happen after `P2`, so layout planning bakes in the improved cache invalidation story.
  - Should not be bundled with shell or import-root work; this refactor deserves a focused track.
- Taskable implementation slices
  - Slice 1: extract layout planner
  - Slice 2: introduce renderer registry and legacy adapter
  - Slice 3: migrate widgets
  - Slice 4: migrate array-ref and object renderers
  - Slice 5: tighten docs and remove accidental helper APIs like `refInput()` if still dead
- Effort estimate
  Large

#### P6. Introduce explicit virtual import roots for merged static layers
- Current friction
  Cross-package imports in agent UI make sense only if the reader already knows the runtime merged static namespace. Tests emulate that with aliases, but the contract is implicit and partial. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17` `tests/frontend/vitest.config.js:18`
- Proposed design with concrete code examples

  ```js
  import { NTTStream } from '@n3tx-ui/components/ntx-stream.js';
  import { showToast } from '@n3tx-core/utils/Toast.js';
  import HTTP from '@n3tx-core/core/transport/HTTP.js';
  ```

  ```text
  @n3tx-core/*   -> core static resolver
  @n3tx-ui/*     -> ui static resolver
  @n3tx-agents/* -> agents static resolver
  ```

  ```js
  // Vitest alias sketch
  resolve: {
    alias: {
      '@n3tx-core/': '/workspace/packages/n3tx-core/src/n3tx_core/static/',
      '@n3tx-ui/': '/workspace/packages/n3tx-ui/src/n3tx_ui/static/',
      '@n3tx-agents/': '/workspace/packages/n3tx-agents/src/n3tx_agents/static/',
    }
  }
  ```
- What it enables
  Source-level clarity, simpler test aliases, better IDE navigation, and a package boundary that is legible without mentally simulating deployment.
- Migration path
  1. Support virtual roots in tests first so import rewriting is easy to validate. `tests/frontend/vitest.config.js:18`
  2. Add backend static-resolution support for these roots without breaking current relative paths.
  3. Migrate cross-package imports in `n3tx-agents` first because that package currently bears most of the cognitive cost. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`
  4. Leave same-package relative imports alone.
  5. Update docs to distinguish physical repo paths from browser import roots.
- Dependency sequencing
  - Easier after `P3` because entrypoints become a natural place to normalize import patterns.
  - Independent of `P5`, but both reduce extension friction and should be presented together in documentation.
- Taskable implementation slices
  - Slice 1: Vitest alias proof
  - Slice 2: backend resolver support
  - Slice 3: migrate agent imports
  - Slice 4: docs and examples
- Effort estimate
  Medium

### Resilience Propositions

#### P7. Add safe-render primitives and markdown sanitization
- Current failure mode
  Any backend field or LLM output carrying HTML-bearing text can become executable DOM because renderers directly interpolate or assign parsed markdown to `innerHTML`. `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:214`
- Proposed improvement with specific patterns

  ```js
  export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text ?? '');
    return div.innerHTML;
  }

  export function renderMarkdownSafe(text) {
    const html = marked.parse(String(text || ''));
    return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
  }
  ```

  ```js
  // usage
  content.innerHTML = renderMarkdownSafe(buf);
  headerHtml.push(`<h2>${escapeHtml(name)}</h2>`);
  ```

  ```js
  // low-risk first step for plain text paths
  export function htmlAttr(text) {
    return escapeHtml(text).replace(/"/g, '&quot;');
  }
  ```
- Blast radius reduction
  Converts subsystem-wide trust assumptions into a single hardened boundary and reduces both exploitability and future reviewer burden.
- Migration path
  1. Add shared utilities and tests first.
  2. Convert `MarkdownWidget`, `NTTStreamAgent`, and `NTTAgentLive` first because those are the highest-risk markdown surfaces. `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:214`
  3. Convert `Formidable.getHeader()`, generic display rendering, and `NTTItem` compact rendering next. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:149` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:232`
  4. Add regression tests using malicious payload strings and markdown fixtures.
- Dependency sequencing
  - This is independent of all structural refactors and should be prioritized ahead of them.
  - Safe-render helpers should be reused by any later `P5` renderer decomposition.
- Taskable implementation slices
  - Slice 1: utility + unit tests
  - Slice 2: markdown surfaces
  - Slice 3: plain text interpolation surfaces
  - Slice 4: e2e regression cases

#### P8. Add component style-failure annotations and fallback stylesheets
- Current failure mode
  `Component` logs stylesheet failures and returns `null`, after which components render with structurally valid but visually broken shadow DOM and no explicit failure state. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:274`
- Proposed improvement with specific patterns

  ```js
  static fallbackStylesheet = new CSSStyleSheet();
  Component.fallbackStylesheet.replaceSync(`
    :host { display:block; }
    :host([data-style-error]) { outline: 1px dashed var(--error, red); }
  `);

  async #loadStylesheet(url) {
    return fetch(url)
      .then(/* ... */)
      .catch(err => {
        this.setAttribute('data-style-error', '');
        this.shadowRoot.adoptedStyleSheets = [Component.fallbackStylesheet];
        return null;
      });
  }
  ```

  ```js
  // optional diagnostics hook for tests and shell health panels
  document.dispatchEvent(new CustomEvent('component-style-error', {
    detail: { tag: this.tagName.toLowerCase(), url }
  }));
  ```
- Blast radius reduction
  Makes style failures visible in tests and production diagnostics instead of silently degrading into mysterious broken layouts.
- Migration path
  1. Add `data-style-error` host annotation first.
  2. Add fallback stylesheet second.
  3. Add optional diagnostics event third.
  4. Only after that add a `_meta/static` manifest if shell validation still feels blind.
- Dependency sequencing
  - Benefits from `P3` if a manifest endpoint is added, but the runtime annotation work stands alone.
  - Complements `P4` because clearer stylesheet layering improves diagnostics quality.
- Taskable implementation slices
  - Slice 1: host annotation
  - Slice 2: fallback stylesheet
  - Slice 3: diagnostics event
  - Slice 4: failure-mode tests

#### P9. Replace timing heuristics with completion-driven refreshes
- Current failure mode
  Several flows depend on optimistic timing assumptions: `ntx-item` reply refresh uses a fixed `setTimeout(..., 300)`, pickers and create flows assume data will appear quickly, and modal close depends solely on animation events. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:731` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:109`
- Proposed improvement with specific patterns

  ```js
  // reply flow
  entity.call(methodName, { text }, {
    inbox: (data) => {
      parent?.pull?.();
      replyBox.remove();
    }
  });

  // modal close
  close(reason = 'cancel') {
    this.classList.add('closing');
    const done = () => { this.remove(); this.dispatchEvent(...); this.#resolve?.({ reason }); };
    this.addEventListener('animationend', done, { once: true });
    setTimeout(done, 250);
  }
  ```

  ```js
  // picker option refresh sketch
  const unsubscribe = DC.observe?.('UPDATE', () => renderOptions(searchInput.value));
  dropdown.addEventListener('remove', () => unsubscribe?.(), { once: true });
  ```
- Blast radius reduction
  Removes fragile timing races and keeps slow network or missing-animation environments from causing stuck UI or stale data.
- Migration path
  1. Fix `ntx-method` and `ntx-ref-picker` first because they are confirmed correctness defects. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:110`
  2. Add modal close fallback.
  3. Replace reply refresh timeout with completion- or response-driven parent refresh.
  4. Add targeted tests around slow async paths and disabled CSS animations.
- Dependency sequencing
  - Independent of larger architecture work.
  - Pairs naturally with security hardening because both touch risky UI surfaces without changing the overall architecture.
- Taskable implementation slices
  - Slice 1: `ntx-method`
  - Slice 2: `ntx-ref-picker`
  - Slice 3: `NTTModal`
  - Slice 4: reply refresh flow in `NTTItem`

### Proposition Priority Matrix

| # | Proposition | Simplifies | Impact | Effort | Risk | Enables |
|---|---|---|---|---|---|---|
| P1 | Symmetric explicit theme contract | Theme mental model, light-theme gap, shell includes | High | Medium | Low | P3, clearer docs, simpler tests |
| P2 | Auth/layout invalidation primitives | Auth transitions, cache correctness | High | Medium | Low-Med | Safer SPA flows, fewer stale UI bugs |
| P3 | Canonical shell entrypoints | Boot flow, shell duplication | High | Medium | Medium | P6, P8, easier app adoption |
| P4 | `stylesheets` layering API | CSS composition | Medium-High | Small | Low | Cleaner component inheritance |
| P5 | Split `Formidable` into planner/renderer | Form customization | High | Large | Medium | Future visual packages, easier tests |
| P6 | Virtual import roots | Package-boundary clarity | High | Medium | Medium | Better tooling, simpler tests |
| P7 | Safe-render primitives | Security boundary | High | Medium | Low | Safer widgets and agent UI |
| P8 | Style-failure fallback state | CSS failure resilience | Medium | Medium | Low | Better diagnostics, stronger smoke tests |
| P9 | Completion-driven refreshes | Async correctness | Medium-High | Small-Med | Low | More reliable picker/modal/reply UX |

Priority notes:

- Quick wins: `P2`, `P4`, `P7`, `P9`
- Strategic investments: `P3`, `P5`, `P6`
- Dependencies: `P3` helps `P6` and `P8`; `P1` simplifies shell changes under `P3`; `P4` is helpful but not required for `P5`

## Downstream Use Guide

### For Bug Hunting
- Known risk areas ranked by probability
  - 1: output rendering and security-sensitive HTML paths (`Formidable`, `NTTItem`, markdown widgets, agent stream rendering). `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:149` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:232`
  - 2: auth-sensitive layout caching (`Permissions` + `Formidable`). `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38` `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`
  - 3: shell integration and theme boot assumptions. `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` `packages/n3tx-ui/src/n3tx_ui/static/login.html:7`
  - 4: cross-package agent UI imports and runtime contract duplication. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17` `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:218`
  - 5: timing-sensitive UI flows such as modal close, reply submission, and async picker loads. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:109` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:731` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:110`
- Untested edge cases with specific scenarios
  - login or logout without full page reload, then reopen the same form/card and verify field visibility changes
  - markdown payload containing HTML tags, script-like attributes, or malformed nested markdown
  - `ntx-chat` mounted against a model whose table is not reachable through `/api/*`
  - picker open before any child entities are loaded, then data arriving while dropdown is already open
  - modal close when animations are disabled or stylesheet loading fails
  - custom `item-tag` that is display-only, then invoking `openCreateModal()` from a list
  - current user changes from anonymous to authenticated while a topbar and multiple cards remain mounted, then edit/delete actions should re-evaluate correctly `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:72` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:258`
  - `exclusiveMinimum`/`exclusiveMaximum` fields should be validated consistently between backend and HTML attributes, especially for method forms and create flows `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:181`
  - mixed array values containing both href strings and populated objects should not trigger wrong delete/unlink behavior `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:720`
  - unsupported stored theme values in localStorage should not leave the DOM in an undefined theme state `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:12`
  - missing CSS file for a component should produce diagnosable state rather than silent visual corruption `packages/n3tx-core/src/n3tx_core/static/core/Component.js:289`
- Suggested test cases to write
  - `ntx-method` should rerender actual response after `_response_()`
  - `ntx-ref-picker` should update options when `DC.instances` changes after first open
  - theme boot should validate unsupported stored theme values and normalize to `dark`
  - markdown rendering should sanitize `<script>` and dangerous attributes
  - shell asset-smoke tests should visit `/login.html`, `/register.html`, and `/schema.html`
  - agent UI tests should mount `ntx-chat`, `ntx-agent-live`, and `ntx-stream-agent` under the Vitest merged-namespace config
  - `NTTModal.close()` should resolve and remove itself even when `animationend` never fires
  - `NTTTopbar` should remove the `theme-change` listener in `disconnectedCallback()` once implemented
  - `openCreateModal()` should fail loudly or degrade cleanly when `item-tag` points to a display-only custom component
  - `Formidable` cache should invalidate after calling `permissions.refresh()` and `Formidable.clearCache()` in the same session
  - widget CSS should resolve canonical accent tokens instead of purple fallbacks under both dark and light themes `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:4`
  - `ntx-chat` should derive its instance list URL from runtime/schema metadata and work identically across default examples
- Suggested bug-hunting workflow
  - Reproduce first in `schema.html` or `examples/core` where possible because those shells minimize app-specific noise. `packages/n3tx-core/src/n3tx_core/static/schema.html:149` `examples/core/static/index.html:60`
  - If the failure involves agent UI, reproduce again in `examples/pygentic` because it exercises the widest agent surface. `examples/pygentic/static/index.html:74`
  - For shell/theme bugs, check `login.html`, `register.html`, and `schema.html` separately because their boot paths differ from the component-heavy app shells. `packages/n3tx-ui/src/n3tx_ui/static/login.html:10`
  - For schema/rendering bugs, inspect whether the defect originates in backend schema, runtime binding (`Component`/`NTT`), or rendering (`Formidable`/component template) before changing code.

### For Feature Development
- Extension points with difficulty ratings and examples
  - Low: add widgets through `registerWidget()` and backend `ui.widget`; example: add `color` or `code` widget. `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:22`
  - Low: change per-model item renderer through `schema.ui.renderer.item` or `item-tag`. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177`
  - Medium: add a new shell view by composing `ntx-topbar`, `ntx-sidebar`, and `ntx-router`. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:126`
  - Medium: create custom stream UI by extending `NTTStream` or `NTTStreamAgent`. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:23`
  - High: customize form behavior beyond widgets today; this usually means touching `Formidable` internals unless `P5` lands.
- Patterns to follow
  - let backend schema drive renderer selection instead of hardcoding frontend routes or field rules
  - prefer extending `Component`/`NTTElement`/`ListElement`/`NTTStream` over introducing new lifecycle systems
  - keep CSS external and layered through component style hooks instead of inlining large JS style strings
  - preserve additive `prerender()` plus `render()` behavior; do not wipe structural DOM created before schema load
- Constraints to know before starting
  - the browser sees a merged static namespace even though source packages are separate
  - many component contracts are class-name and DOM-shape sensitive because tests depend on them
  - `Formidable` currently expects edit widgets to expose a primary input-like element that can receive `data-key` and `data-type`
  - list create flows assume the stamped child tag is edit-capable
  - compact item rendering returns HTML strings, not nodes, so escaping rules matter and extensions must preserve the string-return contract unless `NTTItem.render()` changes `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:229`
  - `NTTMethod` and `NTTStream` use attribute-driven reloads, so changing attributes after mount is part of the public behavior `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:33`
- Common pitfalls
  - hardcoding backend paths in visual components
  - forgetting that auth changes need cache invalidation
  - relying on unescaped HTML-string rendering
  - assuming dark theme defaults without linking light theme and theme boot utilities
  - using app-specific selectors in framework CSS when the change belongs in an app-local component or stylesheet `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:758`
  - adding new optional vendor dependencies in page shells without documenting them as part of the shell contract `examples/grants/static/index.html:20`
- Recommended feature-development sequence
  - start from schema: can the backend express the feature with `ui`, `methods`, `access`, or renderer hints?
  - if yes, prefer a renderer/widget/component extension over a new transport path
  - if shell changes are required, prototype first in a framework-owned shell before spreading the pattern to examples/apps
  - add tests at the same layer as the feature: widget tests for widgets, component tests for lifecycle/render logic, e2e only for shell/theme flows

### For Integration Planning
- Integration boundaries with data contracts
  - backend -> frontend: JSON Schema is the universal contract; use `properties`, `ui`, `access`, `methods`, `$defs`, `$id`, `$schema` as the source of truth. `docs/CORE.md:109`
  - runtime -> visual layer: `Component.define()` and `definedCallback()` are the key boundary. `packages/n3tx-core/src/n3tx_core/static/core/Component.js:183`
  - shell -> component layer: current contract is manual asset inclusion plus component registration/import.
- Dependencies and stability assessment
  - stable: `Component`, `NTTElement`, `ListElement`, widget registry, schema-driven rendering pipeline
  - moderate risk: theme boot contract, topbar/sidebar shell integration, modal lifecycle
  - high risk: current `Formidable` extension ergonomics, agent chat instance loading, merged-namespace source imports
- Impact analysis checklist
  - does the change alter schema fields, `ui`, access, or method metadata?
  - does any shell need new imports, vendor libs, or theme assets?
  - does the change create a new HTML string path that must escape or sanitize content?
  - does it assume auth changes or dynamic role changes without resetting caches?
  - does it add a cross-package import that depends on merged static serving?
- Compatibility considerations
  - DOM class names and shape may already be test-facing compatibility surfaces
  - list/title pluralization and route strings are looser than they look; avoid building new features on those weak assumptions
  - `light-theme.css` is present and public; do not treat it as optional if runtime theme switching matters
  - standalone shell components like `ntx-topbar` and `ntx-modal` do not inherit the full `Component` base, so style and lifecycle integrations may need separate treatment `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:60` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:122`
- Integration checklist by change type
  - Renderer change: verify schema hints, `ListElement.childTag`, and router tag resolution still agree. `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:177` `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:126`
  - Widget change: verify display/edit/list rendering plus wrapper dataset stamping and CSS token usage. `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:225` `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:21`
  - Shell change: verify theme assets, auth flows, and optional vendor libraries across all targeted pages.
  - Agent UI change: verify merged-namespace imports, runtime streaming behavior, and fallback behavior when agent-specific assets fail to load.

### For Refactoring
- Technical debt ranked by severity and coupling risk
  - 1: unsafe HTML/markdown rendering (high severity, high blast radius)
  - 2: auth/layout cache invalidation (high severity, medium coupling)
  - 3: shell/theme implicit contract (medium-high severity, medium coupling)
  - 4: `Formidable` monolith and hidden conventions (medium-high severity, high coupling)
  - 5: merged-namespace source/import ambiguity (medium severity, medium coupling)
  - 6: app-specific selectors in shared CSS and stale `example.html` (medium severity, low-medium coupling)
- Suggested refactoring sequence
  - first: security hardening and correctness bug fixes (`C1`-`C5`)
  - second: cache invalidation and theme contract (`P1`, `P2`)
  - third: shell boot entrypoints and import-root cleanup (`P3`, `P6`)
  - fourth: `stylesheets` formalization (`P4`)
  - fifth: `Formidable` decomposition (`P5`)
- Risk assessment for each proposed change
  - security hardening: low product risk, moderate implementation churn because tests will expose string-render assumptions
  - cache invalidation: moderate behavior churn but low conceptual risk
  - shell/entrypoint standardization: moderate migration risk across examples/apps
  - import-root cleanup: moderate tooling risk, strong long-term payoff
  - `Formidable` split: highest local refactor risk, but best long-term extensibility payoff
  - theme-symmetry work: moderate screenshot churn, low runtime risk if shells are migrated incrementally
  - stylesheets formalization: low runtime risk if compatibility alias is kept during migration
- Before/after sketches for major refactoring candidates

  Before:
  ```text
  theme state = dark implicit + light override + page includes both + JS toggles dataset sometimes
  ```

  After:
  ```text
  theme state = explicit data-theme always + one theme.css + validated theme utility
  ```

  Before:
  ```text
  Formidable = layout cache + renderer dispatch + widget coordination + ref-picker wiring
  ```

  After:
  ```text
  FormLayout.plan() + FieldRenderers registry + widget/ref renderers as plugins
  ```

  Before:
  ```text
  app shell = manual CSS links + manual modulepreloads + manual imports
  ```

  After:
  ```text
  app shell = one canonical entrypoint + optional manifest/preload optimization
  ```

- Suggested refactoring playbook
  - Phase 0: fix critical correctness and security issues without moving architecture boundaries
  - Phase 1: stabilize contracts (`theme.css`, cache invalidation, shell docs)
  - Phase 2: reduce ambiguity (`stylesheets`, virtual import roots, canonical entrypoints)
  - Phase 3: tackle larger internal decomposition (`Formidable` planner/renderer split)
  - Phase 4: remove fossils and leaked app-specific artifacts (`example.html`, auth duplication, app selectors in shared CSS)
- Refactoring checkpoints
  - after each phase, rerun component unit tests plus at least one shell e2e route
  - add one migration note to docs whenever a public or quasi-public frontend contract changes
  - do not combine shell contract changes and deep form-renderer refactors in a single wave; they touch too many user-visible surfaces at once

## Appendix: Complete Finding Index

| ID | Dimension | Type | Severity | Finding/Proposition | File(s) | Status |
|---|---|---|---|---|---|---|
| F01 | Security | Finding | Critical | Raw HTML interpolation in form headers and entity rendering | `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:160`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:233` | Open |
| F02 | Security | Finding | Critical | Unsanitized markdown rendering in widget and agent stream UI | `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:214` | Open |
| F03 | State | Finding | Critical | `Permissions` has no explicit refresh/reset path | `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38` | Open |
| F04 | State | Finding | Critical | `Formidable` cache key is too coarse for auth/schema-sensitive layouts | `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13` | Open |
| F05 | Correctness | Finding | Critical | `ntx-method` never rerenders actual responses | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117` | Open |
| F06 | Correctness | Finding | Critical | `ntx-ref-picker` does not refresh options after async read | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:110` | Open |
| F07 | Contracts | Finding | Critical | `ntx-chat` hardcodes `/api/` and duplicates route knowledge | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:218` | Open |
| F08 | Theming | Finding | High | `light-theme.css` exists; real gap is asymmetric shell/theme contract | `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:28`, `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1` | Open |
| F09 | Tokens | Finding | High | Token vocabulary drift persists in widgets and some component CSS | `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:4`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css:4` | Open |
| F10 | DX | Finding | Medium-High | Manual shell assembly weakens zero-config story | `examples/core/static/index.html:7` | Open |
| F11 | Modularity | Finding | Medium-High | Merged static namespace obscures source-level package ownership | `FRONTEND.md:23`, `tests/frontend/vitest.config.js:18` | Open |
| F12 | Cohesion | Finding | Medium | Shared `ntx-item.css` contains app-specific selectors | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:758` | Open |
| F13 | Shell hygiene | Finding | Medium | `auth.css` exists but stock auth pages inline duplicate styles | `packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:11` | Open |
| F14 | Docs/examples | Finding | Medium | `example.html` is stale and architecturally misleading | `packages/n3tx-ui/src/n3tx_ui/static/example.html:265` | Open |
| F15 | Lifecycle | Finding | Medium | `NTTModal.close()` depends solely on `animationend` | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:109` | Open |
| F16 | Lifecycle | Finding | Low-Med | `NTTTopbar` adds a document listener without cleanup | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:70` | Open |
| F17 | Strength | Finding | Positive | `Component` is a strong deep primitive | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:91` | Preserve |
| F18 | Strength | Finding | Positive | Schema-driven rendering remains the subsystem's core advantage | `docs/CORE.md:144`, `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58` | Preserve |
| F19 | Strength | Finding | Positive | List child renderer resolution is highly additive | `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:173` | Preserve |
| F20 | Contradiction resolved | Finding | Informational | Earlier reports overstated agent CSS breakage; current source shows agent components using external CSS hooks, but boundary cleanup is still needed | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:6`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:26` | Resolved in current tree |
| F21 | Validation | Finding | Medium | `validationAttrs()` cannot represent strict exclusive bounds faithfully in HTML | `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:181` | Open |
| F22 | API drift | Finding | Medium | `forward` on `ntx-method` remains a ghost API surface in reports and tests | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:27` | Open |
| F23 | API drift | Finding | Medium | `Formidable` still carries legacy helper surfaces such as `refInput()` | `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:45` | Open |
| F24 | Correctness | Finding | Medium | `Component.value` only guards on `typeof`, which is too shallow for entity/list shape safety | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:243` | Open |
| F25 | Contract duplication | Finding | Medium | Sidebar duplicates response-envelope knowledge with manual `result.data || result` handling per analysis reports | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:197` | Open |
| F26 | UI contract | Finding | Medium | `ListElement.openCreateModal()` assumes `childTag` is edit-capable | `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:141` | Open |
| F27 | UX | Finding | Medium | List headers use naive pluralization via `${this.model}s` | `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:277` | Open |
| F28 | UX | Finding | Medium | `NTTItem` uses `confirm()` instead of framework modal primitives for delete actions | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:81` | Open |
| F29 | Heuristics | Finding | Medium | Inline reply behavior depends on placeholder text containing “reply” | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:698` | Open |
| F30 | Timing | Finding | Medium | Reply refresh still uses a fixed timeout rather than completion-driven sync | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:731` | Open |
| F31 | Shell discipline | Finding | Medium | Stock auth pages bypass shared `auth.css` despite it being packaged | `packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`, `packages/n3tx-ui/src/n3tx_ui/static/register.html:11` | Open |
| F32 | Token drift | Finding | Medium | Widgets still fall back to purple/indigo accent tokens inconsistent with theme direction | `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:4`, `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:151` | Open |
| F33 | Typography | Finding | Medium | Font contract is split between theme imports and component-local fallback variables | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css:4`, `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:3` | Open |
| F34 | Delivery | Finding | Medium | Shell asset coverage is root-page biased; non-root stock pages lack equivalent smoke protection | `tests/frontend/tests/e2e/css-and-theming-unit.spec.js:473` | Open |
| F35 | Test quality | Finding | Medium | `ntx-method` tests miss the real response rerender defect | `tests/frontend/tests/components/ntx-method.test.js:38`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117` | Open |
| F36 | Test quality | Finding | Medium | `ntx-ref-picker` tests trigger READ but do not assert post-read dropdown freshness | `tests/frontend/tests/components/ntx-ref-picker.test.js:455`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:110` | Open |
| F37 | Test drift | Finding | Medium | `ntx-topbar` tests encode stale behavior like default version/favorites assumptions | `tests/frontend/tests/components/ntx-topbar.test.js:78`, `tests/frontend/tests/components/ntx-topbar.test.js:148` | Open |
| F38 | Test drift | Finding | Medium | display-mode tests and historical assumptions lag current `row` support | `tests/frontend/tests/integration/display-mode-cascade.test.js:157`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:315` | Open |
| F39 | Strength | Finding | Positive | Widget registry remains a clean additive extension seam | `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:22` | Preserve |
| F40 | Strength | Finding | Positive | Theme files are variable-driven and make component CSS largely theme-agnostic | `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css:16` | Preserve |
| F41 | Strength | Finding | Positive | Agent UI is architecturally additive over `NTTStream`/`NTTItem` | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:24`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:21` | Preserve |
| F42 | Strength | Finding | Positive | `Component` stylesheet caching and render deferral are good resilience/perf choices | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:274`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:299` | Preserve |
| F43 | Documentation gap | Finding | Medium | Frontend docs mention `light-theme.css` but underspecify the page-level integration contract | `FRONTEND.md:88`, `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:17` | Open |
| F44 | Documentation gap | Finding | Medium | docs/tests are part of the real extension contract and currently drift from implementation | `packages/n3tx-ui/docs/components.md:157`, `tests/frontend/tests/components/ntx-topbar.test.js:148` | Open |
| P01 | Simplification | Proposition | High | Make theme state symmetric and explicit | `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:28` | Proposed |
| P02 | Simplification | Proposition | High | Add explicit auth/layout invalidation primitives | `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38`, `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13` | Proposed |
| P03 | Simplification | Proposition | High | Replace manual shell boot graphs with canonical entrypoints | `examples/core/static/index.html:7` | Proposed |
| P04 | Composability | Proposition | Medium-High | Formalize layered component CSS as `stylesheets` | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:262` | Proposed |
| P05 | Composability | Proposition | High | Split `Formidable` into layout planner and renderer registry | `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13` | Proposed |
| P06 | Composability | Proposition | High | Introduce explicit virtual import roots | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`, `tests/frontend/vitest.config.js:18` | Proposed |
| P07 | Resilience | Proposition | High | Add safe-render primitives and markdown sanitization | `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17` | Proposed |
| P08 | Resilience | Proposition | Medium | Add style-failure annotation and fallback stylesheets | `packages/n3tx-core/src/n3tx_core/static/core/Component.js:274` | Proposed |
| P09 | Resilience | Proposition | Medium-High | Replace timing heuristics with completion-driven refreshes | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:731`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:109` | Proposed |
| P10 | Simplification | Proposition | Medium | Wire `auth.css` into stock auth pages or remove it | `packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:11` | Proposed |
| P11 | Simplification | Proposition | Medium | Retire or quarantine stale `example.html` from canonical shell guidance | `packages/n3tx-ui/src/n3tx_ui/static/example.html:265` | Proposed |
| P12 | Resilience | Proposition | Medium | Expand shell asset-smoke coverage beyond `/` to login/register/schema and examples | `tests/frontend/tests/e2e/css-and-theming-unit.spec.js:473` | Proposed |
| P13 | Composability | Proposition | Medium | Remove app-specific selectors from shared `ntx-item.css` and relocate them to app-local components | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css:758` | Proposed |
| P14 | Correctness | Proposition | Medium | Normalize `NTTMethod` parameter handling and response validation using schema-aware form helpers | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:89`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:102` | Proposed |
| P15 | Contract hygiene | Proposition | Medium | Remove or formalize ghost/legacy APIs like `forward` and `refInput()` | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:27`, `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:45` | Proposed |
| P16 | Test resilience | Proposition | Medium | Add dedicated agent UI frontend tests for `ntx-chat`, `ntx-agent-live`, and `ntx-stream-agent` | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:25`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:21` | Proposed |
| P17 | UX consistency | Proposition | Medium-Low | Replace naive pluralization and browser-native confirms with design-system-aware helpers | `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:277`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:81` | Proposed |
