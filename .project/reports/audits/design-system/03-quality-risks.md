# Design-System Quality & Risks Audit
## Scope
This audit covers the frontend design-system surface of N3TX:

- CSS/theme correctness.
- import-path fragility.
- component rendering hazards.
- schema/UI contract mismatches.
- form and widget edge cases.
- shell asset availability.
- downstream example/test risk.

The analysis is based on direct inspection of the required source files and usage sites, not on docs alone. Architectural intent was cross-checked against the frontend contract docs in `docs/CORE.md:109`, `FRONTEND.md:127`, and `packages/n3tx-ui/docs/formidable.md:12`.
## Executive Assessment
The subsystem is productive and conceptually strong: backend-owned schema remains the source of truth for most rendering, field grouping, method exposure, and permission-aware display (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`, `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:117`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:412`).

The main quality problem is not absence of capability; it is uneven hardening. Several paths are polished and additive, while adjacent paths still rely on optimistic assumptions, legacy tokens, inline HTML interpolation, or merged-static namespace magic. The result is a subsystem that works well on its happy path but has multiple confirmed failure modes around security, agent UI styling, method responses, picker refresh, and test drift.

Risk level summary:

| Area | Assessment | Basis |
|---|---|---|
| Runtime correctness | Medium-High | confirmed bugs in method response rendering, ref picker refresh, agent stream styling, chat data URL selection (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:111`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:213`) |
| Security | High | widespread unescaped HTML interpolation and unsanitized markdown rendering (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:160`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:235`, `packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:213`) |
| Asset availability | Low current / High blast radius | `light-theme.css` exists at `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`, but many shipped pages depend on it (`examples/core/static/index.html:8`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:8`, `packages/n3tx-core/src/n3tx_core/static/schema.html:8`) |
| Import robustness | Medium-High | agent components depend on merged runtime paths that are not package-local, and test aliasing only special-cases one agent file (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:17`, `tests/frontend/vitest.config.js:28`) |
| Test quality | High risk | many unit tests are stale relative to source behavior, while important bugs are untested (`tests/frontend/tests/components/ntx-topbar.test.js:78`, `tests/frontend/tests/components/ntx-method.test.js:822`, `tests/frontend/tests/integration/duplicate-read-requests.test.js:7`) |
## Method
### Files Read
Core frontend runtime and utils read in full:

- `packages/n3tx-core/src/n3tx_core/static/core/Component.js`
- `packages/n3tx-core/src/n3tx_core/static/utils/theme.js`
- `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js`
- `packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js`
- `packages/n3tx-core/src/n3tx_core/static/utils/Logging.js`
- `packages/n3tx-core/src/n3tx_core/static/config.js`

Design-system assets, components, widgets, and HTML shells read in full:

- `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css`
- `packages/n3tx-ui/src/n3tx_ui/static/auth.css`
- all files under `packages/n3tx-ui/src/n3tx_ui/static/components/`
- all files under `packages/n3tx-ui/src/n3tx_ui/static/widgets/`
- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`
- `packages/n3tx-ui/src/n3tx_ui/static/example.html`
- `packages/n3tx-ui/src/n3tx_ui/static/login.html`
- `packages/n3tx-ui/src/n3tx_ui/static/register.html`

Agent-side visual components read in full:

- all files under `packages/n3tx-agents/src/n3tx_agents/static/components/`

Usage sites and tests read in full as requested:

- `examples/core/static/index.html`
- `examples/actors/static/index.html`
- `examples/grants/static/index.html`
- `examples/pygentic/static/index.html`
- `apps/veille/static/index.html`
- `packages/n3tx-core/src/n3tx_core/static/schema.html`
- `tests/frontend/vitest.config.js`
- the specified frontend component, generator, integration, and e2e tests.
### Audit Lens
I used the project’s own standards as evaluation criteria:

- zero-config paths should work without app-specific glue.
- frontend should consume backend schema, not duplicate backend route knowledge.
- boundaries should remain inspectable and replaceable.
- additive customization should not require hidden coupling.

Those standards are stated in `CLAUDE.md:8`, `CLAUDE.md:15`, `CLAUDE.md:22`, and reinforced for schema-driven frontend behavior in `docs/CORE.md:109` and `FRONTEND.md:133`.
## Confirmed Bugs
### 1. Agent stream styling is effectively broken in `ntx-stream-agent`
`NTTStreamAgent.render()` removes the inherited `.stream-output` node, then tries to append its CSS only if a literal `<style>` element exists in the shadow root (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113`).

That `<style>` element never exists in the current component system because `Component` uses constructable/adopted stylesheets, not inline style tags (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:91`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:299`).

The practical result is:

- agent output markup is created.
- `NTTStreamAgent.agentStyles` is not injected.
- `ntx-stream-agent.css` exists on disk but is never referenced by `get styles()` or injected by the component (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css:1`).

This is a confirmed runtime bug, not just debt.

Evidence:

```js
render() {
    super.render();
    let el = this.shadowRoot.querySelector('.stream-output');
    if (el) el.remove();
    const style = this.shadowRoot.querySelector('style');
    if (style && !style.textContent.includes('entry-thinking')) {
        style.textContent += NTTStreamAgent.agentStyles;
    }
}
```

Source: `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113`.

Severity: High for agent UX.
### 2. `ntx-method` never re-renders real method responses
`callMethod()` sets `this.response = { status: 'sent' }` and immediately calls `#postCall()` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:102`).

When the actual reply arrives, `_response_()` updates `this.response` but does not call `render()` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117`).

So:

- fieldset layout renders the optimistic “sent” state.
- the real response value is stored.
- the UI is not refreshed to show that real response.

That contradicts the component’s own output rendering path in `renderFieldset()` where `this.response` drives the `<pre class="output">...` block (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:200`).

This is a confirmed correctness bug.
### 3. `ntx-ref-picker` does not refresh options after async READ
When a picker opens and the target DynamicClass has no loaded instances, `_showPicker()` triggers `DC.call('READ', {})` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:110`).

But `renderOptions()` is executed immediately from the current `instances` map, and there is no observer subscription or second render after the READ response lands (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:130`).

Failure mode:

1. user opens picker before child records are loaded.
2. picker issues READ.
3. current empty map renders “No items found”.
4. data arrives later.
5. dropdown stays stale until the user closes and reopens.

This is a confirmed UX/data freshness bug.
### 4. `ntx-chat` hardcodes `/api/` in instance discovery
`#loadInstances()` computes `const url = "/api/" + tablename` (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:213`).

That is inconsistent with the schema/CRUD contract used elsewhere in N3TX, where collection endpoints are at `/{tablename}` and model schema endpoints are at `/{ClassName}` (`docs/CORE.md:131`, `docs/CORE.md:163`, `FRONTEND.md:166`).

Because `ntx-chat` bypasses the normal entity/runtime layer and hardcodes a separate path shape, it duplicates backend knowledge and is likely wrong for default zero-config deployments.

This is a confirmed contract mismatch and likely a live bug in example apps using `<ntx-chat>` (`examples/actors/static/index.html:72`, `examples/grants/static/index.html:78`, `examples/pygentic/static/index.html:76`).
### 5. Nested unlink logic in `ntx-item.deleteItem()` fails for populated arrays
The nested unlink path only detects parent membership by checking whether a parent array `includes(this.ref)` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:764`).

That works for string href arrays, but `Formidable.getListInput()` explicitly supports populated object entries with `$id` (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:369`).

So if the parent’s relation array is populated with objects instead of strings:

- `#findParentArrayField()` returns `null`.
- `deleteItem()` falls back to top-level delete behavior.
- a relationship unlink can become an entity delete prompt.

This is a confirmed logic hole with real data-shape mismatch.
### 6. `NTTModal.close()` can hang forever if `animationend` never fires
The modal’s close path depends entirely on an `animationend` listener after adding `.closing` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:109`).

The closing animations are defined only in CSS (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.css:121`).

If the stylesheet fails to load, animations are disabled, or the event is suppressed, the modal never removes itself and never resolves its prompt promise.

That is a confirmed resource/lifecycle bug pattern.
### 7. `theme.js` trusts arbitrary saved values and touches storage on import
`getTheme()` returns `localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME` without validating the saved value (`packages/n3tx-core/src/n3tx_core/static/utils/theme.js:12`).

Then module top-level code reads storage on import and mutates the document (`packages/n3tx-core/src/n3tx_core/static/utils/theme.js:28`).

This is not a browser crash in normal pages, but it is a confirmed robustness weakness:

- unexpected stored values are accepted.
- non-browser or hardened storage contexts will throw at module evaluation time.

Because login/register load this file in `<head>` (`packages/n3tx-ui/src/n3tx_ui/static/login.html:10`, `packages/n3tx-ui/src/n3tx_ui/static/register.html:10`), theme init is now part of the critical path for auth pages.
## High-Confidence Risks
### Security: HTML interpolation and markdown are currently trust-based
This subsystem still interpolates raw values into HTML strings in multiple places.
#### Raw schema/value interpolation in form generation
Examples:

- header edit input injects `value="${name}"` directly (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:160`).
- header display injects `${name}` and `${desc}` directly into HTML (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:165`).
- generic text display injects `${value}` (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:321`).
- object display uses JSON-stringified values inserted into HTML snippets (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:499`).
#### Raw interpolation in item rendering
Examples:

- xs badge inserts raw entity name (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:235`).
- sm name inserts raw value (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:297`).
- reply input placeholder injects backend-provided UI text into HTML (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:706`).
#### Unsanitized markdown rendering
- `MarkdownWidget.display()` assigns `marked.parse(...)` directly to `innerHTML` (`packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17`).
- `NTTStreamAgent` does the same for streamed agent text (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:213`).
- `NTTAgentLive` repeats the same pattern (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:267`).

If backend data or LLM output ever contains unsafe HTML-bearing markdown, the current design system will render it verbatim. This is the single highest-severity security concern in the audited surface.
### Import-path fragility: agent UI depends on merged static namespace magic
Several agent components import files as if they live inside one flat `/components`, `/core`, `/utils`, and `/widgets` tree:

- `ntx-stream-agent.js` imports `./ntx-stream.js` and `../utils/Toast.js` (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1`).
- `ntx-agent-live.js` imports `./ntx-stream.js`, `../core/NTT.js`, and `../widgets/JsonTree.js` (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:17`).
- `ntx-chat.js` imports `./ntx-stream.js`, `../core/NTT.js`, and `../core/transport/HTTP.js` (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`).

That works only because runtime static serving merges multiple packages into one URL namespace, a behavior documented in `FRONTEND.md:115`.

The fragility shows up in local tooling already:

- frontend test aliasing only special-cases `ntx-chat.js`, not the other agent components (`tests/frontend/vitest.config.js:28`).

This means the design system is not package-local inspectable in source form. It is inspectable only after server-side mounting. That weakens modular reasoning and makes bundler/test adoption harder.
### Test drift is masking real regressions
Several tests no longer match the shipped implementation.

Examples:

- `ntx-topbar.test.js` expects a hard-coded default version `v0.6` (`tests/frontend/tests/components/ntx-topbar.test.js:78`), but source derives version from attrs or `/_meta` and otherwise renders nothing (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:91`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:122`).
- the same test expects an automatic Favorites link (`tests/frontend/tests/components/ntx-topbar.test.js:148`), but current topbar only exposes a named slot for nav content (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:135`).
- `ntx-method.test.js` expects `NTTMethod.baseStyles`, `inlineStyles`, and `buttonStyles` (`tests/frontend/tests/components/ntx-method.test.js:822`), but current source ships CSS via `get styles()` and an external CSS file (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:23`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css:1`).
- `display-mode-cascade.test.js` expects exactly five display sizes (`tests/frontend/tests/integration/display-mode-cascade.test.js:157`), while source includes a sixth `row` mode (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:26`).

This is not just noisy maintenance debt. It lowers confidence that failing or passing tests represent current runtime truth.
## Medium-Confidence Risks
### 1. Production pages still ship debug-heavy defaults
The shared frontend config enables `LOGEVENTS`, `LOGSPAWN`, and `DEBUG` by default (`packages/n3tx-core/src/n3tx_core/static/config.js:2`).

Examples then import and render the log panel directly in app HTML:

- `examples/core/static/index.html:71`
- `examples/actors/static/index.html:74`

That means the design system currently normalizes development diagnostics into shipped shells instead of keeping them opt-in. Even if the runtime cost is acceptable today, it increases accidental exposure of internal event names, payloads, and noisy console/dev state.
### 2. Modal body scroll restoration is state-destructive
Opening a modal unconditionally sets `document.body.style.overflow = 'hidden'`, and closing restores it to an empty string (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:169`).

If the page had a pre-existing non-default body overflow policy, the modal loses that state.

This is a classic shell-level side effect bug and becomes more likely as the framework is embedded into more customized apps.
### 3. `Permissions.init()` has no explicit invalidation API
`init()` memoizes the promise forever in `#promise` (`packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js:38`).

That is acceptable for full-page login flows that reload after auth changes (`packages/n3tx-ui/src/n3tx_ui/static/login.html:157`, `packages/n3tx-ui/src/n3tx_ui/static/register.html:162`), but it is brittle for SPA-style auth changes or token refreshes. The design system has no public “re-fetch auth state now” primitive.
### 4. `ListElement.openCreateModal()` assumes `childTag` is edit-capable
Create modals stamp `document.createElement(this.childTag)` and then assume the child supports `.mode`, `.schema`, and `.value` as an edit form (`packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:141`).

If a list uses a custom `item-tag` that is presentation-only, create mode will silently rely on a component contract it never advertised.

This is an additive-customization risk: overriding view tags can accidentally break creation behavior.
### 5. `NTTSidebar` duplicates backend contract and network behavior
Sidebar bootstrap fetches singleton item entries by hand with `fetch(${DC.href}?limit=1)` and manually interprets both `{data: ...}` and raw arrays (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:197`).

That bypasses the actor/runtime abstractions and re-encodes transport/response knowledge inside a visual component, which conflicts with the project’s “frontend should not duplicate backend knowledge” rule.

It is not broken in the common case, but it raises long-term coupling risk.
## CSS & Theme Findings
### Theme architecture is fundamentally sound
The dark theme defines the base variable system on `:root` (`packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:11`).

The light theme works as a pure override layer on `[data-theme="light"]`, leaving component CSS unchanged and variable-driven (`packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`).

That matches the intended additive model:

- one global variable contract.
- light mode as an opt-in override.
- component CSS mostly consuming `var(...)` instead of theme-specific selectors.
### Light theme asset is present; broken-asset risk is not current, but the blast radius is large
The special investigation question has a clear answer:

- `light-theme.css` exists in the shipped package at `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`.
- core and example pages reference it directly from the same static root (`examples/core/static/index.html:8`, `examples/actors/static/index.html:8`, `examples/grants/static/index.html:8`, `examples/pygentic/static/index.html:8`, `apps/veille/static/index.html:8`, `packages/n3tx-core/src/n3tx_core/static/schema.html:8`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:8`, `packages/n3tx-ui/src/n3tx_ui/static/register.html:8`).

So there is no confirmed broken asset in the current tree.

However, the blast radius of a future regression would be high because:

- every major example root page references it.
- auth pages reference it.
- the schema/kitchen-sink shell references it.
- docs explicitly describe it as a shipped asset (`FRONTEND.md:88`).

Coverage for that dependency is weaker than it looks:

- the e2e CSS 404 test only checks the root app page (`tests/frontend/tests/e2e/css-and-theming-unit.spec.js:473`).
- it does not visit login, register, schema, grants, pygentic, or veille pages.

Conclusion:

- current status: not broken.
- operational risk: high blast radius if removed or mount order changes.
- test coverage: partial.
### Legacy token fallbacks still leak a purple visual language into widgets
Several widget styles still use `--accent-primary` with a purple fallback, or related legacy variables:

- `.widget-url-link` falls back to `#6366f1` (`packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:4`).
- `.widget-email-link` falls back to `#6366f1` (`packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:14`).
- markdown blockquotes and links also fall back to `#6366f1` (`packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:64`, `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:75`).
- reference links do the same (`packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css:127`).

The base themes define `--accent`, not `--accent-primary` (`packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:27`, `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:27`).

So the fallback color wins in many widget contexts, producing a design-system drift away from the teal/cyan identity.

This is a confirmed theme correctness issue.
### Theme tokens are split across old and new naming systems
The codebase currently mixes at least three token families:

1. current design tokens like `--surface-*`, `--text-*`, `--accent`, `--glass-*` (`packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:13`).
2. legacy aliases like `--border-color`, `--bg-glass`, `--bg-tertiary`, `--text-primary`, `--text-secondary` (`packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:95`, `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:79`).
3. newer component-local tokens with fallbacks like `--panel-bg`, `--line`, `--card-bg`, `--font-display`, `--button-text` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css:17`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css:16`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css:44`).

The fallback coverage prevents immediate breakage, but it leaves the design system harder to reason about. Different subsystems are effectively drawing from different “eras” of the token vocabulary.
### The font strategy is inconsistent across subsystems
The dark theme globally imports Inter and JetBrains Mono (`packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:3`).

But some newer components assume `--font-display` and `--font-body` while providing fallbacks like `Manrope` or `Inter` that are not always globally defined (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css:4`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.css:3`).

This produces a subtle but real quality issue:

- some screens look intentionally designed.
- other screens fall back to ad hoc typography contracts.

It is not a crash bug, but it is subsystem-level inconsistency.
## Component Rendering Hazards
### `Component.value` only checks `typeof`, which does not distinguish arrays from objects
The base setter rejects mismatched primitive kinds, but both arrays and plain objects have `typeof === 'object'` (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:242`).

That means a collection component can accidentally accept an object payload without failing the guard, and a single-entity component can accept an array payload the same way. Subclasses often protect themselves later, but the base invariant is weaker than it looks.
### `NTTItem` mixes surgical updates with full-render fallbacks in brittle ways
The item update path is ambitious and useful, but some branches are fragile:

- any `$ref` change forces a full re-render (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:474`).
- list-field reconciliation has a placeholder “count bump” line `visibleItems.push(visibleItems)` instead of pushing a moved element (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:540`).
- reply submission refreshes the parent through a fixed `setTimeout(..., 300)` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:731`).

The effect is not catastrophic, but it means subtle timing and nested-reference states are still handled heuristically, not transactionally.
### `NTTMethod` renders invalid HTML input types for string params
Both fieldset and inline rendering use raw schema types directly as input `type` values:

- `renderFieldset()` emits `type="${def.type || 'text'}"` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:194`).
- `renderInline()` does the same for simple params (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:258`).

For schema type `string`, that produces `type="string"`, which is not a valid HTML input type. Browsers degrade it to text, so this is often survivable, but it is still invalid output and a sign that schema-to-HTML coercion is incomplete in this component.
### `NTTTopbar` leaks listeners on remount
`connectedCallback()` registers a `theme-change` listener on `document` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:75`).

There is no corresponding `disconnectedCallback()` to remove it.

That is a modest but confirmed memory/resource leak if topbars are mounted and unmounted dynamically.
### `NTTModal.getSheet()` has no network error handling
The modal CSS fetch path does not check `r.ok` and has no catch path (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js:25`).

Most components using the shared `Component` base at least log stylesheet failures (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:289`). `NTTModal` is a standalone exception.

That makes modal styling failures noisier and harder to debug than normal component styling failures.
## Schema / UI Contract Mismatches
### `ntx-chat` duplicates route knowledge instead of using schema/runtime primitives
This is the clearest contract violation in the audited set:

- list fetching for instance options is built from `schema.__tablename__` plus a hardcoded `/api/` prefix (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:213`).
- the canonical schema/runtime path uses `href` and DynamicClass behavior, not manual URL building (`FRONTEND.md:154`, `docs/CORE.md:163`).

That means one agent component opted out of the framework’s own transport abstraction.
### Sidebar singleton loading duplicates pagination response semantics
`NTTSidebar.#fetchItemRef()` manually interprets a response as `result.data || result` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:205`).

That mirrors backend pagination shape knowledge already centralized elsewhere. It works today, but it is a second source of truth for response envelopes.
### The widget system and form generator overlap on `$ref` handling in confusing ways
There are two parallel approaches to references:

- generic `$ref` handling in `Formidable.getInput()` (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:295`).
- a dedicated `ReferenceWidget` that builds hash links (`packages/n3tx-ui/src/n3tx_ui/static/widgets/ReferenceWidget.js:12`).

The latter is currently not the canonical path for actual relation rendering, and its generated `href` pattern `#/${value.$id}` or `#/${model}/${value}` is not aligned with router examples that use bare `Product/3`-style strings (`packages/n3tx-ui/src/n3tx_ui/static/widgets/ReferenceWidget.js:16`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js:101`).

This is more contract confusion than active bug, but it raises future maintenance risk.
## Form / Widget Edge Cases
### `refInput()` is effectively dead and incorrect
`refInput()` looks up an NTT prototype, then calls `getForm(schema)` with only the schema object (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:45`).

But `getForm()` expects an NTT-like object with `schema` and `value` (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`).

This helper is not used anywhere important in the audited surface, which is good, because it would not work correctly as written.
### `resolveAnyOf()` throws for multi-type schemas instead of degrading gracefully
If a field has multiple non-null `anyOf` variants, `resolveAnyOf()` throws hard (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:453`).

That is consistent with the docs’ “schema design issue” stance (`packages/n3tx-ui/docs/formidable.md:149`), but in runtime UI terms it means one ambiguous backend schema can take down a full render rather than isolating that field.
### `validateForm()` skips arrays and objects entirely
Complex fields are excluded from validation (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:540`).

That keeps validation simple, but it also means:

- object textareas can contain invalid JSON and still pass client validation.
- array edit state is never structurally validated.

The picker and nested components compensate partially, but the design-system form layer is only validating scalar data.
### `NTTRefPicker._submitCreate()` can send `NaN`
For number fields, `_submitCreate()` does `parseFloat(el.value)` and assigns the result directly (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:247`).

Unlike `ListElement.openCreateModal()`, it does not strip `NaN` before sending (`packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:158`).

So the picker’s inline-create path is less robust than the standard create modal path for the same conceptual operation.
### Currency widget symbol configuration is honored in widgets, but not in all legacy paths
`CurrencyWidget` respects `config.symbol` in display, edit, and list rendering (`packages/n3tx-ui/src/n3tx_ui/static/widgets/CurrencyWidget.js:14`, `packages/n3tx-ui/src/n3tx_ui/static/widgets/CurrencyWidget.js:23`, `packages/n3tx-ui/src/n3tx_ui/static/widgets/CurrencyWidget.js:59`).

But the non-widget fallback path in `Formidable.getInput()` hardcodes `$` for currency edit/display rendering (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:268`, `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:291`).

Because widget dispatch usually runs first, this is mostly a legacy fallback issue. Still, it means the subsystem does not have a single authoritative currency rendering path.
## Example / Shell Asset Risk
### Example pages have a mixture of current and legacy assumptions
#### `example.html` is a legacy shell, not a trustworthy design-system consumer
The file imports `PTT`, `registrar`, `registry`, `dispatch`, and `remote` from a runtime structure that does not match the current frontend contract (`packages/n3tx-ui/src/n3tx_ui/static/example.html:265`).

It also uses legacy CSS variables like `--accent-success`, `--accent-error`, `--bg-secondary`, and `--text-muted` that are not part of the current base token set (`packages/n3tx-ui/src/n3tx_ui/static/example.html:57`, `packages/n3tx-ui/src/n3tx_ui/static/example.html:74`, `packages/n3tx-ui/src/n3tx_ui/static/example.html:145`).

This file should be treated as historical debris, not as a reliable smoke-test surface.
#### Example index pages still preload/import components outside the core package surface
`examples/core/static/index.html` and `examples/actors/static/index.html` preload and import `ntx-favorites.js` and `ntx-logs.js` from their own app-local component folders (`examples/core/static/index.html:49`, `examples/core/static/index.html:88`, `examples/actors/static/index.html:49`, `examples/actors/static/index.html:91`).

Those files do not exist in the shared framework static directory and are only present in these specific examples. That is fine for the examples themselves, but it means the example pages exercise a larger shell surface than the framework package alone.
### Auth pages duplicate layout CSS instead of reusing `auth.css`
`auth.css` defines a dedicated auth shell (`packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`).

But `login.html` and `register.html` inline near-duplicate auth-page/auth-card styling in `<style>` blocks instead of importing `auth.css` (`packages/n3tx-ui/src/n3tx_ui/static/login.html:11`, `packages/n3tx-ui/src/n3tx_ui/static/register.html:11`).

This is not a runtime bug, but it is a clear DRY and maintainability issue in the design-system shell layer.
### Example/usage shells rely heavily on preloads but do not validate them broadly
Many app roots preload a large module tree and many component CSS files (`examples/core/static/index.html:10`, `examples/actors/static/index.html:10`, `examples/grants/static/index.html:10`, `examples/pygentic/static/index.html:10`, `apps/veille/static/index.html:10`).

That is a useful startup optimization, but it also increases the number of asset references that can silently drift. The only explicit CSS-404 test covers one page (`tests/frontend/tests/e2e/css-and-theming-unit.spec.js:473`).
## Downstream Risk in Examples and Apps
### `examples/actors` and `examples/grants` are exposed to the `ntx-chat` route bug
Both pages mount `<ntx-chat>` (`examples/actors/static/index.html:72`, `examples/grants/static/index.html:78`).

Because `ntx-chat` currently fetches instance options from `/api/${tablename}` (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:213`), the first user-visible breakage is likely to appear in those examples.
### `examples/pygentic` is exposed to agent-component import and styling fragility
The page preloads and imports all agent-facing components (`examples/pygentic/static/index.html:49`, `examples/pygentic/static/index.html:76`).

So it is the highest-risk downstream page for:

- merged-namespace import fragility.
- `NTTStreamAgent` missing styles.
- duplicate/static agent CSS drift.
### `apps/veille` relies on the widest component surface and will amplify design debt fastest
Veille imports the broadest custom component set and also mixes framework router usage with manual hash routing in page script (`apps/veille/static/index.html:245`, `apps/veille/static/index.html:274`).

That increases the probability of:

- route state inconsistencies.
- theme drift between core framework styles and app-inline styles.
- unnoticed asset regressions because the shell is richer than the standard example pages.
## Test Coverage Analysis
### What is covered reasonably well
There is meaningful coverage for:

- form field rendering and validation permutations (`tests/frontend/tests/generators/form.test.js:56`).
- `ntx-item` behavior across many modes (`tests/frontend/tests/components/ntx-item.test.js:84`).
- ref picker control flow (`tests/frontend/tests/components/ntx-ref-picker.test.js:137`).
- duplicate READ regression at the NTT/bootstrap layer (`tests/frontend/tests/integration/duplicate-read-requests.test.js:77`).
- basic CSS/theming behavior and CSS 404 detection on the root page (`tests/frontend/tests/e2e/css-and-theming-unit.spec.js:13`, `tests/frontend/tests/e2e/css-and-theming-unit.spec.js:473`).
### What is missing or weak
#### Agent component coverage is almost absent
The requested test set does not include targeted tests for:

- `ntx-stream-agent.js`
- `ntx-agent-live.js`
- `ntx-chat.js`
- `ntx-agent.js`

That matters because several confirmed or high-confidence issues live exactly in those files (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:213`).
#### Shell asset coverage is root-page biased
The CSS 404 test visits only `APP_URL = '/'` (`tests/frontend/tests/e2e/css-and-theming-unit.spec.js:10`, `tests/frontend/tests/e2e/css-and-theming-unit.spec.js:473`).

It does not protect:

- login page assets.
- register page assets.
- schema.html assets.
- example-specific modulepreload graphs.
#### Accessibility tests are broad but shallow
They verify general presence of labels, focusability, and text contrast (`tests/frontend/tests/e2e/accessibility-unit.spec.js:78`, `tests/frontend/tests/e2e/accessibility-unit.spec.js:216`), but they do not exercise:

- modal focus trapping.
- dropdown keyboard operation for topbar and sidebar.
- ref picker keyboard navigation.
- router back-button semantics with real screen-reader labels.
#### Legacy/stale unit tests now reduce trust
Tests that assert outdated behavior are worse than missing tests, because they create false signals. Examples already cited:

- topbar default version/favorites expectations (`tests/frontend/tests/components/ntx-topbar.test.js:78`, `tests/frontend/tests/components/ntx-topbar.test.js:148`).
- nonexistent `NTTMethod.baseStyles` API (`tests/frontend/tests/components/ntx-method.test.js:822`).
- outdated display-size count (`tests/frontend/tests/integration/display-mode-cascade.test.js:157`).
## Test Quality Assessment by File
### `NTTElement.test.js`
Very shallow. It validates class presence and a default `update()` return value, but not live behavior, error handling, subscriptions, or save TX routing (`tests/frontend/tests/components/NTTElement.test.js:23`).

Risk: high false confidence.
### `ListElement.test.js`
Also shallow. It mainly checks method existence and static constants (`tests/frontend/tests/components/ListElement.test.js:23`).

It does not verify:

- dedup semantics in real element lifecycles.
- create modal behavior.
- size cascade at runtime.
- update patch correctness.
### `ntx-item.test.js`
This is one of the stronger suites. It covers many rendering branches, error UI, permission gating, and delete behavior (`tests/frontend/tests/components/ntx-item.test.js:162`, `tests/frontend/tests/components/ntx-item.test.js:551`, `tests/frontend/tests/components/ntx-item.test.js:998`).

But it still misses the populated-array unlink bug described earlier, because its nested-delete tests use string refs only (`tests/frontend/tests/components/ntx-item.test.js:672`).
### `ntx-method.test.js`
Mixed quality:

- good breadth across layouts and parameter shapes.
- clear staleness in the static-style assertions (`tests/frontend/tests/components/ntx-method.test.js:822`).

Crucially, it does not catch the real response re-render bug because it never asserts that `_response_()` updates rendered output.
### `ntx-ref-picker.test.js`
Broad but still misses the important async freshness bug. It verifies that `_showPicker()` triggers READ when instances are empty (`tests/frontend/tests/components/ntx-ref-picker.test.js:455`), but it never checks that options update after the async response.
### `ntx-topbar.test.js`
Significant drift from source behavior:

- hard-coded version assumption.
- automatic favorites assumption.
- no assertion around `_meta` fetch defaulting.

Because of that, this suite is more of a migration casualty than a reliable guardrail.
### `ntx-sidebar.test.js`
Decent for shell markup and lifecycle cleanup, but it still reflects a partially outdated understanding of child-template precedence versus `models` attr handling (`tests/frontend/tests/components/ntx-sidebar.test.js:326`). The current source uses child-derived entries first and only falls back to the `models` attr when there are no template entries (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:122`).
### `form.test.js`
Strong at scalar rendering/validation. Weak at security and richer runtime behavior.

It does not test:

- HTML escaping.
- malformed object JSON in edit mode.
- populated `$ref` unlink edge cases.
- widget security semantics.
## Failure Scenarios
### Scenario A: Agent stream renders but looks unstyled
1. App mounts `<ntx-stream-agent>` through an agent UI surface.
2. Base styles from `ntx-stream.css` load via inherited `get styles()` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:7`).
3. Agent output entries render (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:160`).
4. `render()` tries to append agent CSS only if a `<style>` tag exists (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:119`).
5. No `<style>` tag exists because the component system uses adopted stylesheets (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:98`).
6. Result: output is structurally present but visually degraded.
### Scenario B: A user invokes a method and sees only “sent” forever
1. User submits a fieldset method form.
2. `callMethod()` sets optimistic response `{status:'sent'}` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:109`).
3. `renderFieldset()` prints that object in the output panel (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:200`).
4. Actual response arrives in `_response_()` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117`).
5. Component pulls entity data but does not rerender its own output (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:120`).
6. Result: stale method feedback even though the operation succeeded.
### Scenario C: Picker opens empty even though related items exist
1. Parent entity edit form shows `ntx-ref-picker` (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:403`).
2. User opens picker before child DynamicClass instances have loaded.
3. Picker issues `READ` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:111`).
4. Existing empty instance map renders “No items found” (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:153`).
5. No observer updates the dropdown after the async fetch completes.
6. Result: misleading empty picker until reopen.
### Scenario D: Rich markdown content becomes executable markup
1. Backend or LLM returns markdown containing HTML/script-bearing content.
2. Markdown widget or agent component uses `marked.parse()` directly into `innerHTML` (`packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:18`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:214`).
3. Result: untrusted markup enters the DOM without a sanitizer.
## Technical Debt Inventory
### Dead or duplicated assets
| Item | Evidence | Debt |
|---|---|---|
| `ntx-stream-agent.css` | file exists but `NTTStreamAgent` never references it (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css:1`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113`) | likely dead asset / divergence risk |
| `ntx-agent.css` | file exists while `NtxAgent` also ships a large inline `agentStyles` string (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.css:1`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:367`) | dual style sources |
| `auth.css` | packaged shared auth stylesheet exists, but login/register use inline copies (`packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:11`) | duplicated shell styling |
| `refInput()` | helper is exported indirectly and incorrect (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:45`) | dead/unsafe code path |
### Contract duplication
| Duplicate knowledge | Evidence |
|---|---|
| chat list endpoint path | `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:213` |
| sidebar singleton fetch envelope handling | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:205` |
| currency fallback formatting separate from widget | `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:267` |
### Token vocabulary drift
| Token family | Examples |
|---|---|
| current theme tokens | `--surface-0`, `--accent`, `--glass-bg` in `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:13` |
| legacy aliases | `--border-color`, `--bg-tertiary` in `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:95` |
| component-local “new” tokens | `--panel-bg`, `--line`, `--font-display` in `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css:17` |
## Resource / Performance Risks
### Good patterns already present
The subsystem does contain several healthy performance choices:

- stylesheet fetch dedup in `Component` via `_sheetCache` and `_sheetPending` (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:19`).
- render coalescing via `scheduleRender()` (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:362`).
- layout caching in `Formidable` keyed by schema/mode/role (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:10`).
- event listener cleanup in `NTTItem` and `NTTRow` via `AbortController` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:633`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:232`).
### Remaining performance concerns
#### Large preload surfaces make pages asset-fragile and heavy
Every example/app root preloads a wide import tree (`examples/core/static/index.html:22`, `examples/grants/static/index.html:23`, `apps/veille/static/index.html:19`).

That may be fine for internal demos, but it raises the maintenance cost of every added component CSS or JS file and increases the number of ways app shells can drift from the actual component set they use.
#### Logging buffer is bounded, but live listeners still accumulate if misused
The logging system caps entries at 500 (`packages/n3tx-core/src/n3tx_core/static/utils/Logging.js:3`), which is good.

But listeners are plain functions in an array (`packages/n3tx-core/src/n3tx_core/static/utils/Logging.js:8`). Any component that forgets to remove a listener will hold memory and rerender costs until page unload. `NTTTopbar` avoids Logging, but `ntx-logs` itself is careful to unsubscribe (`examples/core/static/components/ntx-logs.js:137`). The broader pattern still depends on component discipline.
## Concurrency / Timing Risks
### Async picker and modal flows are still mostly optimistic
- ref picker add/create dispatches optimistic UI events before confirmed persistence (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:233`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:269`).
- reply flow uses a fixed 300ms delay before refreshing the parent (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:731`).
- table create row assumes additions imply success and closes on any new item arrival (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js:337`).

These are not always wrong, but they are timing-sensitive and can misbehave under slow networks, retries, or concurrent edits.
### The duplicate READ regression is covered, but broader dedup invariants are not
The integration suite explicitly documents and tests the old duplicate READ bug (`tests/frontend/tests/integration/duplicate-read-requests.test.js:7`).

That is good.

What is still untested:

- simultaneous picker READs.
- simultaneous modal creates.
- interleaving of route navigation and list updates.
- agent stream cancel/resume races.
## Recommended Priorities
### Priority 0 — Security hardening
Address first:

- sanitize markdown output before assigning `innerHTML` in `MarkdownWidget`, `NTTStreamAgent`, and `NTTAgentLive` (`packages/n3tx-ui/src/n3tx_ui/static/widgets/MarkdownWidget.js:17`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:213`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:267`).
- escape all plain-string interpolations in `Formidable` and `NTTItem` render strings (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:160`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:235`).
### Priority 1 — Fix confirmed UX/runtime bugs
Address next:

- agent stream stylesheet injection bug (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:113`).
- method response rerender gap (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:117`).
- ref picker async option refresh (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:111`).
- `ntx-chat` `/api/` path bug (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:213`).
### Priority 2 — Reduce hidden coupling
Address soon after:

- make agent components package-local or explicitly alias-safe instead of relying on merged static mount paths (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:17`, `tests/frontend/vitest.config.js:28`).
- move sidebar singleton fetches onto the standard runtime abstractions (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js:197`).
- unify currency and reference rendering paths.
### Priority 3 — Repair trust in tests
Needed cleanup:

- delete or rewrite stale expectations in `ntx-topbar.test.js`, `ntx-method.test.js`, and `display-mode-cascade.test.js` (`tests/frontend/tests/components/ntx-topbar.test.js:78`, `tests/frontend/tests/components/ntx-method.test.js:822`, `tests/frontend/tests/integration/display-mode-cascade.test.js:157`).
- add missing agent-component tests.
- add asset-smoke coverage for login/register/schema/example pages.
## Final Verdict
The N3TX design-system subsystem is architecturally promising and often elegant, especially where it stays schema-first and additive (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`, `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:173`).

Its current risk profile is driven by four things:

1. trust-based HTML/markdown rendering.
2. a few real runtime bugs in agent and method/ref-picker paths.
3. package-boundary fragility hidden by merged static serving.
4. a test suite whose shallow coverage and stale assertions make regression signals unreliable.

The good news is that the problems are concentrated rather than diffuse. The subsystem does not need a conceptual rewrite; it needs a focused hardening pass around security, response/render synchronization, async list freshness, and boundary cleanup.
## Appendix: Light-Theme Asset Blast Radius
### Current State
`light-theme.css` is present and valid at `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`.
### Shipped/used pages that depend on it directly
| Page | Reference |
|---|---|
| framework login | `packages/n3tx-ui/src/n3tx_ui/static/login.html:8` |
| framework register | `packages/n3tx-ui/src/n3tx_ui/static/register.html:8` |
| schema shell | `packages/n3tx-core/src/n3tx_core/static/schema.html:8` |
| core example | `examples/core/static/index.html:8` |
| actors example | `examples/actors/static/index.html:8` |
| grants example | `examples/grants/static/index.html:8` |
| pygentic example | `examples/pygentic/static/index.html:8` |
| veille app | `apps/veille/static/index.html:8` |
### What would break if it disappeared or stopped mounting
- light mode would silently degrade to dark defaults on all pages above because only the dark base theme defines the core variables (`packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:11`, `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`).
- tests that compare dark vs light screenshots would likely fail on the root page (`tests/frontend/tests/e2e/css-and-theming-unit.spec.js:424`).
- login/register and schema shells would lose theme parity, even though current automated checks would probably miss them because those routes are not part of the CSS-404 test coverage (`tests/frontend/tests/e2e/css-and-theming-unit.spec.js:473`).
### Audit Conclusion on the special question
There is no current broken-asset defect around `light-theme.css`.

There is a real high-blast-radius dependency on that file across shipped HTML, and current tests do not cover every consumer route.
