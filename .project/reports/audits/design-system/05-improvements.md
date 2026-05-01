# Design System Improvements Audit

## Scope and Framing

This report audits the frontend design-system subsystem with a strategic-improvements lens.
The goal is not to redesign N3TX into a generic component library.
The goal is to make the existing schema-driven frontend easier to understand,
more additive to extend,
more resilient under imperfect asset delivery,
and more explicit about where runtime ends and visual policy begins.

The subsystem already reflects several project principles well.
The runtime/visual split is explicit in docs and in package structure,
with `n3tx-core` carrying the non-visual substrate and `n3tx-ui` carrying visual components and themes (`FRONTEND.md:19`, `FRONTEND.md:23`, `FRONTEND.md:103`).
Static directories intentionally collapse into one namespace at runtime,
which keeps app HTML simple when everything is mounted by the backend (`FRONTEND.md:23`, `packages/n3tx-core/docs/app-bootstrap.md:143`, `packages/n3tx-core/docs/app-bootstrap.md:152`).
Schema-driven rendering is real rather than aspirational:
`Component` resolves models and refs,
`ListElement` and `NTTElement` consume that runtime layer,
and `Formidable` uses schema order, groups, access, and widget hints without a second contract (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:183`, `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js:56`, `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js:89`, `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`).

The main issues are not in raw capability.
They are in the mental model:
themes are implemented asymmetrically,
stylesheet layering exists but is expressed through a singular `styles` interface,
merged static namespaces leak into package-local imports,
forms/widgets/components share state through conventions that are powerful but narrow,
and example HTML pages pay a high tax in manual imports, preloads, and duplicated auth styling (`packages/n3tx-core/src/n3tx_core/static/utils/theme.js:8`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:94`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:7`, `examples/core/static/index.html:10`).

The special investigation around the “likely absence” of `light-theme.css` is revealing.
The file is present,
implemented,
and referenced by multiple HTML entry points (`packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:8`, `examples/core/static/index.html:8`, `packages/n3tx-core/src/n3tx_core/static/schema.html:8`).
The fact that it is easy to assume it is missing means the current theme model is not self-evident.
Dark theme is the unqualified base in `:root` (`packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:11`),
light theme is only an override selector (`packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`),
and the JS theme manager only writes `data-theme` for non-default themes on boot (`packages/n3tx-core/src/n3tx_core/static/utils/theme.js:9`, `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:29`).
That asymmetry is the first and most important simplification target.

## High-Level Improvement Themes

### What Is Already Strong

- `Component` centralizes actor identity,
schema attach,
ref resolution,
adaptive display,
and constructable stylesheet adoption,
which gives every visual component the same runtime substrate (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:70`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:183`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:362`).
- `Formidable` already separates layout planning from field rendering enough to support field order,
groups,
permissions,
widgets,
and attached methods without per-model code (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`, `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:58`, `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:107`).
- The widget system is intentionally additive;
backend schema hints decide activation,
and frontend registries keep extension out of framework conditionals (`packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js:22`, `packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js:32`, `packages/n3tx-ui/docs/widgets.md:35`).
- The agent stream stack already discovered the right CSS layering shape by having `NTTStream` inherit `NTTMethod` styles and append stream styles,
then having `NTTStreamAgent` append agent styles on top (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:7`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:6`).

### Where Cognitive Load Spikes

- Theme state is split between CSS file order,
DOM dataset state,
and localStorage state (`packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:11`, `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`, `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:13`).
- Entry HTML pages hand-assemble a large static graph of CSS preloads,
modulepreloads,
component registrations,
and optional vendor libraries,
which means “zero to working” depends on hidden copy-paste knowledge (`examples/core/static/index.html:10`, `examples/grants/static/index.html:10`, `apps/veille/static/index.html:10`).
- Package boundaries disappear in production by design,
but several imports now depend on that merged namespace in a way that is invisible when reading files in isolation (`FRONTEND.md:23`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`).
- Forms,
widgets,
and items coordinate through dataset stamping and mode downgrades that are clever but fragile to extend (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:225`, `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:210`, `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:33`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:197`).
- Test and documentation expectations have drifted from the actual interface surface,
which indicates the subsystem contract is not tight enough to stay legible over time (`tests/frontend/tests/components/ntx-topbar.test.js:84`, `tests/frontend/tests/components/ntx-method.test.js:822`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:135`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js:14`).

## Proposition 1 — Make Theme State Symmetric and Explicit

### Current State

The dark theme defines the base token set directly on `:root` (`packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css:11`).
The light theme is a selector-scoped override that only activates when `data-theme="light"` is present (`packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:11`).
The theme manager defaults to `dark` in storage logic,
returns `dark` when nothing is stored,
and only auto-applies a dataset when the saved theme is not the default (`packages/n3tx-core/src/n3tx_core/static/utils/theme.js:9`, `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:12`, `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:29`).
Entry pages load both theme stylesheets manually (`examples/core/static/index.html:7`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:7`, `packages/n3tx-core/src/n3tx_core/static/schema.html:7`).

### Problem

The actual mental model today is:

1. dark theme is “ambient base CSS”,
2. light theme is “conditional override CSS”,
3. `theme.js` is mostly a localStorage and dataset helper,
4. HTML pages are responsible for linking both files.

That is functional,
but it violates “transparent, not magical” because the active theme is not represented symmetrically in the DOM.
`data-theme` is authoritative for light,
but absence of `data-theme` means dark by implication rather than by explicit state (`packages/n3tx-core/src/n3tx_core/static/utils/theme.js:29`).
The special-investigation clue matters here:
the easy assumption that `light-theme.css` is missing is exactly what happens when one theme feels first-class and the other feels like a patch.

It also weakens resilience.
If a page forgets to include `light-theme.css`,
theme toggling still updates localStorage and `data-theme`,
but nothing visual changes.
The contract between HTML shell and theme system is implicit and unverified.

### Proposed Change

Introduce a single explicit theme contract:

- always set `document.documentElement.dataset.theme` on boot,
- add a canonical `theme.css` entry that imports or concatenates both token layers,
- treat `dark` and `light` as symmetric token namespaces,
- move HTML pages to a single theme stylesheet include.

Suggested API:

```js
// packages/n3tx-core/src/n3tx_core/static/utils/theme.js
const STORAGE_KEY = 'ntx-theme';
const DEFAULT_THEME = 'dark';

export function resolveTheme() {
  return localStorage.getItem(STORAGE_KEY)
    || document.documentElement.dataset.theme
    || DEFAULT_THEME;
}

export function applyTheme(theme = resolveTheme()) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(STORAGE_KEY, theme);
  document.dispatchEvent(new CustomEvent('theme-change', { detail: { theme } }));
}

applyTheme();
```

Suggested CSS shell:

```css
/* packages/n3tx-ui/src/n3tx_ui/static/theme.css */
@import './dark-theme.css';
@import './light-theme.css';
```

Suggested token structure:

```css
/* dark-theme.css */
[data-theme="dark"] { ...tokens... }

/* light-theme.css */
[data-theme="light"] { ...tokens... }
```

Data flow after change:

```text
HTML -> load theme.css once
boot -> applyTheme(resolveTheme())
DOM -> <html data-theme="dark|light">
components -> consume tokens only through CSS vars
```

### Trade-Offs

Benefits:

- clearer mental model,
- easier debugging in devtools,
- more robust SSR and tests,
- less risk of “dark by accident, light by selector”.

Costs:

- dark-theme.css must stop acting as unconditional global base,
- a few tests and screenshots may need updates,
- any app CSS that depended on the old implicit dark default will need a selector update.

### Migration Path

1. Add `theme.css` without removing existing files.
2. Update `theme.js` to always set `data-theme`.
3. Convert `dark-theme.css` from `:root` to `[data-theme="dark"]` while keeping legacy aliases intact.
4. Change framework and example HTML pages from two theme links to one.
5. Add one smoke test that asserts both themes render after page load without depending on file-order side effects.

## Proposition 2 — Replace Manual HTML Import Assemblies With Canonical Entrypoints

### Current State

Example pages preload long lists of component CSS,
modulepreload a large JS tree,
and then manually import/register components again in a page-local module block (`examples/core/static/index.html:10`, `examples/core/static/index.html:23`, `examples/core/static/index.html:73`).
The grants,
actors,
pygentic,
and veille apps repeat the pattern with local variation (`examples/actors/static/index.html:10`, `examples/grants/static/index.html:10`, `examples/pygentic/static/index.html:10`, `apps/veille/static/index.html:10`).
The docs explicitly explain that static dirs merge into one namespace in production,
so the browser does not know package boundaries (`FRONTEND.md:23`, `FRONTEND.md:117`).

### Problem

The system is trying to be “zero to working, then customize”,
but current HTML shells require a maintainer to know:

- which CSS files should preload,
- which modules should modulepreload,
- which components must be imported just for registration side effects,
- which vendor libraries are optional,
- which agent components live in another package but still import from the same merged namespace.

This is a configuration burden masquerading as static optimization.
It also creates package-boundary confusion.
The HTML files make the merged namespace real,
but the source tree still looks split by package,
so developers have to think in both models at once.

### Proposed Change

Ship explicit frontend entrypoints and a generated preload manifest.

Suggested entrypoints:

```js
// /static/entrypoints/app-shell.js
import '../utils/theme.js';
import '../components/ntx-item.js';
import '../components/ntx-list.js';
import '../components/ntx-router.js';
import '../components/ntx-topbar.js';
import '../components/ntx-sidebar.js';
import '../components/ntx-profile.js';
import '../components/ntx-stream.js';
import '../widgets/index.js';

export async function boot({ initPermissions = true } = {}) {
  if (initPermissions) {
    const { permissions } = await import('../utils/Permissions.js');
    permissions.init();
  }
}
```

```js
// /static/entrypoints/agents-shell.js
import './app-shell.js';
import '../components/ntx-stream-agent.js';
import '../components/ntx-chat.js';
import '../components/ntx-agent-live.js';
import '../components/ntx-agent.js';
```

Suggested HTML:

```html
<link rel="stylesheet" href="./theme.css">
<script type="module">
  import { boot } from './entrypoints/app-shell.js';
  await boot();
</script>
```

If preload optimization is still desired,
the backend can expose a stable manifest from the merged static set:

```json
GET /_meta/frontend
{
  "entrypoints": {
    "app-shell": ["./config.js", "./core/NTT.js", "./components/ntx-item.js"],
    "agents-shell": ["./components/ntx-stream-agent.js", "./components/ntx-chat.js"]
  },
  "styles": ["./theme.css", "./widgets/widgets.css"]
}
```

### Trade-Offs

Benefits:

- fewer moving parts in each app shell,
- more consistent boot behavior,
- easier optimization later because there is one authoritative dependency list,
- clearer distinction between framework boot and app composition.

Costs:

- custom apps lose some page-local “I only import exactly what I see” control,
- build or manifest generation adds one more backend concern.

### Migration Path

1. Add `app-shell.js` and `agents-shell.js` without touching existing pages.
2. Convert `packages/n3tx-ui/src/n3tx_ui/static/example.html` first,
because it is already marked outdated by docs and carries the highest entropy (`docs/frontend/ARCHITECTURE.md:357`).
3. Convert example apps next.
4. Add optional manifest-driven preload generation later,
only if performance data still justifies it.

## Proposition 3 — Rename and Formalize Stylesheet Layering as `stylesheets`

### Current State

`Component` exposes a singular `styles` getter,
but it already accepts either a single URL or an array of URLs,
normalizes them internally,
and loads them in order (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:262`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:264`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:299`).
Most components return one file,
but `NTTStream` layers stream CSS on top of `NTTMethod` CSS by returning an array (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:7`).
`NTTStreamAgent` continues that pattern by inheriting parent styles and appending `ntx-stream-agent.css` (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:6`).
At the same time,
other agent components bypass the pattern and inject CSS text inline in JS (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:34`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:39`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js:31`).

### Problem

The code has already discovered the right abstraction,
but the API name hides it.
A singular `styles` property suggests “one stylesheet per component”,
while actual behavior is “ordered stylesheet layers”.
That mismatch creates unnecessary special cases:

- `NTTStream` and `NTTStreamAgent` use array layering,
- `NtxAgent` manually appends a constructable stylesheet in `render()`,
- `NTTAgentLive` and `NTTChat` keep large CSS strings in JS files despite having parallel CSS assets in the same directory.

This directly hurts composability.
The design system wants method -> stream -> agent stacking,
but the naming and component conventions still look like one-off exceptions.

### Proposed Change

Make stylesheet layering a first-class interface.

Suggested API:

```js
export class Component extends HTMLElement {
  get stylesheets() { return []; }
  get styles() {
    // temporary back-compat bridge
    return this.stylesheets;
  }
}
```

Then express composition explicitly:

```js
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

export class NTTStreamAgent extends NTTStream {
  get stylesheets() {
    return [...super.stylesheets, new URL('./ntx-stream-agent.css', import.meta.url).href];
  }
}
```

Then remove inline CSS strings from agent components in favor of real files:

```js
export class NTTAgentLive extends NTTStream {
  get stylesheets() {
    return [...super.stylesheets, new URL('./ntx-agent-live.css', import.meta.url).href];
  }
}
```

### Trade-Offs

Benefits:

- matches the intended “layered CSS” mental model,
- easier debugging because every layer is inspectable and cacheable,
- less JS bloat from large embedded CSS strings,
- easier per-layer reuse.

Costs:

- a few components need migration from inline styles,
- some tests may need to stop assuming CSS is injected as `<style>` text.

### Migration Path

1. Add `stylesheets` while preserving `styles` as a compatibility alias.
2. Migrate `NTTMethod`, `NTTStream`, `NTTStreamAgent` first,
because they already follow the pattern.
3. Move `ntx-agent-live`, `ntx-chat`, and `ntx-agent` to external CSS files.
4. Update docs to use “stylesheets layering” everywhere instead of “stylesheet hook” when multiple layers are involved.

## Proposition 4 — Split Formidable Into a Layout Planner and Field Renderer Registry

### Current State

`Formidable` does three jobs at once:

- layout planning and caching (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:13`),
- field rendering across display/edit/list contexts (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:195`),
- coordination with concrete UI components such as `ntx-ref-picker` (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:5`, `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:403`).

Widgets are additive,
but the widget contract itself is asymmetric:
`display()` and `edit()` return DOM nodes,
while `list()` returns a string (`packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:21`, `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:33`, `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:48`).
`Formidable` works around this by creating wrappers,
stamping `data-key` and `data-type` manually,
and relying on `NTTItem.handleInputChange()` to interpret the dataset later (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:225`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:197`).

### Problem

This is the biggest composability bottleneck in the subsystem.
Today,
you can extend forms,
but only if you know hidden coordination rules:

- header fields are filtered out by a private header set (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:11`),
- protected fields downgrade effective mode per field (`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:210`),
- widgets must produce a primary input that can be decorated after the fact,
- ref arrays are special because `Formidable` knows about `ntx-ref-picker` directly.

That is still “primitives, not opinions” at the schema level,
but not at the renderer level.
The renderer is opinionated in code shape,
and extension points are narrower than they look.

### Proposed Change

Keep schema-driven behavior,
but split the subsystem into two layers:

1. `FormLayout.plan(schema, mode, role)` -> returns ordered field descriptors.
2. `FieldRenderers.render(context, fieldPlan)` -> dispatches to registered renderers.

Suggested interfaces:

```js
export const FormLayout = {
  plan(schema, { mode, role }) {
    return {
      header: [...],
      groups: [...],
      fields: [
        {
          key: 'price',
          definition: schema.properties.price,
          effectiveMode: 'edit',
          renderer: 'widget:currency'
        }
      ]
    };
  }
};
```

```js
export const FieldRenderers = {
  register(name, renderer) { ... },
  renderField(ctx, fieldPlan) { ... }
};
```

```js
FieldRenderers.register('array:ref', {
  display(ctx, field) { ... },
  edit(ctx, field) { return `<ntx-ref-picker ...></ntx-ref-picker>`; },
  list(ctx, field) { ... }
});
```

This keeps backend-authoritative schema intact,
but makes additive frontend extension real:

- apps can replace just array-ref editing,
- widgets can migrate toward a more uniform render-result contract,
- future visual packages can override field renderers without forking `form.js`.

### Trade-Offs

Benefits:

- tighter separation of concerns,
- better testability,
- easier custom field families,
- less hidden coupling to `NTTItem` dataset conventions.

Costs:

- short-term refactor complexity,
- slightly more indirection when debugging render output.

### Migration Path

1. Extract `_getLayout()` into a named `FormLayout` module first.
2. Add a small renderer registry while leaving `getInput()` as the default renderer.
3. Migrate array-ref handling and widget handling into registered renderers.
4. Only after that,
decide whether widget `list()` should remain string-based or move to a unified node/result type.

## Proposition 5 — Harden Asset Delivery and Style Failure Recovery

### Current State

`Component` caches constructable stylesheets,
deduplicates fetches,
and defers rendering until styles are ready (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:17`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:274`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:369`).
When CSS loading fails,
it logs a warning and returns `null` (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:289`).
The e2e theme test explicitly asserts that CSS files do not 404 (`tests/frontend/tests/e2e/css-and-theming-unit.spec.js:473`).
Many pages also preload CSS manually to avoid flashes (`examples/core/static/index.html:10`, `examples/grants/static/index.html:10`).

### Problem

The current recovery model is binary:

- success -> render with styles,
- CSS fetch failure -> log warning and continue.

That is not enough for a design system that depends heavily on shadow-root styling.
If CSS misses,
the component still renders markup,
but now it is structurally correct and visually broken.
There is no host-level state,
no fallback sheet,
no error surface for tests or app shells,
and no manifest-level sanity check tying HTML preloads to actual static mounts.

### Proposed Change

Add a two-layer resilience model:

1. runtime fallback styles for component survivability,
2. static-manifest validation for deployment correctness.

Suggested runtime hook:

```js
// Component.js
static fallbackStylesheet = new CSSStyleSheet();
Component.fallbackStylesheet.replaceSync(`
  :host { display:block; }
  [data-style-error] { outline: 1px dashed var(--error, red); }
`);

async #loadStylesheet(url) {
  ...
  .catch(err => {
    this.setAttribute('data-style-error', '');
    this.shadowRoot.adoptedStyleSheets = [Component.fallbackStylesheet];
    Logging.warn(...);
    return null;
  })
}
```

Suggested backend manifest endpoint:

```json
GET /_meta/static
{
  "files": {
    "./theme.css": true,
    "./components/ntx-item.css": true,
    "./widgets/widgets.css": true
  }
}
```

App shells and tests can then assert existence before rendering complex screens.

### Trade-Offs

Benefits:

- style failures become visible and diagnosable,
- production mounts become easier to validate,
- tests can assert degraded-but-usable states instead of only perfect success.

Costs:

- minor added complexity in `Component`,
- one more `_meta` surface to maintain.

### Migration Path

1. Add `data-style-error` host annotation first.
2. Add a tiny fallback stylesheet second.
3. Add manifest endpoint third.
4. Extend `css-and-theming-unit.spec.js` with one controlled failure case rather than only 404 absence checks.

## Proposition 6 — Remove Dead and Duplicated Visual Shells

### Current State

`auth.css` exists as a reusable auth-page stylesheet (`packages/n3tx-ui/src/n3tx_ui/static/auth.css:1`).
The default `login.html` and `register.html` do not import it;
they import theme files,
then inline their auth styles directly (`packages/n3tx-ui/src/n3tx_ui/static/login.html:7`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:11`, `packages/n3tx-ui/src/n3tx_ui/static/register.html:7`, `packages/n3tx-ui/src/n3tx_ui/static/register.html:11`).
`example.html` is still a large legacy demo tied to an older mental model and architecture (`packages/n3tx-ui/src/n3tx_ui/static/example.html:1`).
The frontend architecture doc already calls it broken against the current version (`docs/frontend/ARCHITECTURE.md:357`).

### Problem

This creates two kinds of confusion:

- dead assets that look canonical but are not actually used,
- living example pages that teach outdated concepts.

For a subsystem audit focused on mental-model simplification,
this matters more than cosmetic cleanup.
A developer reading `auth.css` naturally assumes it is the shared auth shell,
but real pages bypass it.
A developer reading `example.html` sees registrar-era concepts that no longer define the runtime.

### Proposed Change

Make the shell layer opinionated by convention and explicit by file purpose:

- rename `auth.css` to `auth-shell.css` or wire it into login/register,
- retire `example.html` in favor of `schema.html` plus small focused examples,
- add a `static/README.md` or doc section describing which HTML files are canonical,
legacy,
or app-local.

Suggested convention:

```text
static/
  theme.css
  auth-shell.css
  shell-app.html
  shell-login.html
  shell-register.html
  schema.html
  legacy/example.html   // clearly marked or removed
```

### Trade-Offs

Benefits:

- less ambiguity,
- easier onboarding,
- fewer dead-end files in the default visual package.

Costs:

- a small amount of file renaming and doc churn,
- any outside references to old paths must be updated.

### Migration Path

1. Decide whether `auth.css` is canonical or disposable.
2. If canonical,
replace inline login/register styles with it.
3. Move `example.html` behind a `legacy/` folder or delete it after confirming no downstream user relies on it.
4. Document canonical shells in `packages/n3tx-ui/docs/components.md` or a new `shells.md`.

## Proposition 7 — Tighten Package-Boundary Contracts Around the Merged Static Namespace

### Current State

The docs say static dirs are intentionally merged into one URL namespace (`FRONTEND.md:23`, `packages/n3tx-core/docs/app-bootstrap.md:145`).
Tests emulate that behavior with Vitest aliases (`tests/frontend/vitest.config.js:18`).
Agent UI components import `./ntx-stream.js` from their local directory even though the base file actually lives in the UI package path in source (`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:1`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js:17`, `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js:17`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js:1`).

### Problem

This is one of the clearest cases of package-boundary confusion.
At runtime,
the import works because the URL namespace is flattened.
At source level,
the file looks like it imports a sibling that does not exist.
That is tolerable once understood,
but it is not transparent,
and it weakens the intentional runtime/visual split by making package-local reading misleading.

It also leaks into test infrastructure,
where alias rules must recreate the production illusion manually (`tests/frontend/vitest.config.js:19`, `tests/frontend/vitest.config.js:29`).

### Proposed Change

Introduce explicit virtual import roots for merged static layers.

Suggested browser-facing imports:

```js
import { NTTStream } from '@n3tx-ui/components/ntx-stream.js';
import { showToast } from '@n3tx-core/utils/Toast.js';
```

Suggested serving rule:

```text
@n3tx-core/*   -> merged static resolver -> core static dir
@n3tx-ui/*     -> merged static resolver -> ui static dir
@n3tx-agents/* -> merged static resolver -> agents static dir
```

This keeps the merged production namespace,
but makes source intent legible and tooling-friendly.
It also gives tests one contract to emulate instead of regex-based relative-path aliases.

### Trade-Offs

Benefits:

- clearer source-level boundaries,
- simpler import reasoning,
- better IDE and test alignment.

Costs:

- import paths become less “just relative files”,
- backend static resolver and test alias setup need one coordinated update.

### Migration Path

1. Support virtual roots in tests first.
2. Add backend resolver support for virtual roots next.
3. Migrate cross-package imports in agent components.
4. Leave same-package relative imports alone.

## Light Theme Evidence Trail

### What The “Likely Absence” Signal Actually Reveals

The investigation does not show a missing file.
It shows a missing mental model.

Evidence:

- `light-theme.css` exists and is substantial (`packages/n3tx-ui/src/n3tx_ui/static/light-theme.css:1`).
- Multiple pages already link it (`examples/core/static/index.html:8`, `packages/n3tx-ui/src/n3tx_ui/static/login.html:8`).
- The theme manager persists `ntx-theme` and dispatches `theme-change` (`packages/n3tx-core/src/n3tx_core/static/utils/theme.js:8`, `packages/n3tx-core/src/n3tx_core/static/utils/theme.js:20`).
- Topbar re-renders on `theme-change` and uses `getTheme()` to label its toggle (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:76`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js:161`).
- E2E tests assume a working light theme and compare dark/light screenshots (`tests/frontend/tests/e2e/css-and-theming-unit.spec.js:160`, `tests/frontend/tests/e2e/css-and-theming-unit.spec.js:424`).

The ambiguity comes from asymmetry,
not absence:

- dark is encoded as unconditional `:root`,
- light is encoded as a conditional override,
- boot only sets `data-theme` for the non-default path,
- HTML must remember to link both theme files.

That makes the subsystem look like it has one “real” theme and one “optional” theme.
It also explains why the wrong audit hypothesis is plausible.
The right improvement is not “add light-theme.css”.
It is “make the theme contract impossible to misunderstand”.

## Proposition Summary Table

| # | Proposition | Simplifies | Impact | Effort | Risk | Dependencies |
|---|-------------|------------|--------|--------|------|--------------|
| P1 | Make theme state symmetric and explicit | theme mental model, light/dark debugging, shell includes | High | Medium | Low | none |
| P2 | Replace manual HTML import assemblies with canonical entrypoints | app boot, package-boundary understanding, startup consistency | High | Medium | Medium | none |
| P3 | Formalize stylesheet layering as `stylesheets` | component composition, method/stream/agent CSS layering | High | Small | Low | none |
| P4 | Split Formidable into layout planner + field renderer registry | forms/widgets composition, extension without edits | High | Large | Medium | P3 helpful but not required |
| P5 | Harden asset delivery and style failure recovery | CSS delivery resilience, diagnosability | Medium | Medium | Low | P2 helpful for manifest usage |
| P6 | Remove dead and duplicated visual shells | shell conventions, onboarding clarity | Medium | Small | Low | none |
| P7 | Tighten merged-namespace imports with virtual roots | package-boundary clarity, test/tooling alignment | High | Medium | Medium | P2 helpful |

## Final Assessment

The design-system subsystem is already powerful.
It can render arbitrary schema-driven entities,
compose widgets,
layer streaming interfaces,
and run across merged static packages with surprisingly little code.
The main opportunity is not a visual redesign.
It is to turn implicit knowledge into explicit contracts.

The most valuable simplifications are:

- make theme state symmetric,
- make stylesheet layering first-class,
- make boot and imports canonical,
- make form composition extensible without editing `form.js`.

If those changes land,
the subsystem becomes much more aligned with the stated philosophy:
zero to working gets cheaper,
customization becomes more additive,
and the package split stays real without becoming confusing.
