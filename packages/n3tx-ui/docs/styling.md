# Themes and component styling

## Ownership

| Layer | Owns | Does not own |
|---|---|---|
| `theme-base.css` | Global defaults, page layout, shared structural selectors | Theme palettes |
| `dark-theme.css`, `light-theme.css` | Canonical `--ntx-*` token values | Component registration |
| Core `utils/theme.js` | Persisted selection and cycling order | Loading theme stylesheets |
| Component stylesheet | Shadow DOM layout and token consumption | Global application layout |
| App stylesheet/theme | App-specific composition and token overrides | Copies of framework component CSS |

## Page setup

Place these in the app page head; URLs refer to the native combined namespace.

```html
<link rel="stylesheet" href="/theme-base.css">
<link rel="stylesheet" href="/dark-theme.css">
<link rel="stylesheet" href="/light-theme.css">
<script>window.NTX_THEME_CONFIG = {themes: ['dark', 'light']};</script>
<script type="module" src="/utils/theme.js"></script>
```

Theme selection is applied on module execution. Loading in the head reduces
flashing, but module/network timing is not a universal before-first-paint guarantee.

| Runtime function | Behavior |
|---|---|
| `getTheme()` | Stored `ntx-theme`, otherwise first configured theme (default dark) |
| `getConfiguredThemes()` | Trimmed, deduplicated configured names; defaults dark/light |
| `getNextTheme(currentTheme=getTheme())` | Next configured name; unknown names fall back to first |
| `setTheme(theme)` | Stores name, sets `html.dataset.theme`, dispatches document `theme-change` |
| `toggleTheme()` | Selects the next configured theme |

A persisted name is not automatically rejected because a page lacks its CSS.
Keep theme files/config consistent across login, app and standalone pages.

## Controls are explicit

After importing the used component modules:

```html
<ntx-topbar brand="Issues">
  <ntx-theme-button slot="user-menu"></ntx-theme-button>
</ntx-topbar>
<ntx-sidebar router="main">
  <ntx-list model="Issue"></ntx-list>
  <ntx-theme-button slot="footer"></ntx-theme-button>
</ntx-sidebar>
```

Import `/components/ntx-topbar.js`, `/components/ntx-sidebar.js`,
`/components/ntx-list.js`, and `/components/ntx-theme-button.js` in the shell.
Topbar's user-menu slot is in the authenticated dropdown. Multiple controls
synchronize through `theme-change`. Logged-out first-party pages honor persisted
theme without showing the switcher. Configuration alone does not insert controls.

## Custom theme

For a small variation, retain the linked dark token defaults and add an app file
`static/ocean-theme.css` after the framework styles:

```css
html[data-theme="ocean"] {
  color-scheme: dark;
  --ntx-color-accent: #70d6ff;
  --ntx-color-accent-strong: #38bdf8;
  --ntx-color-accent-text: #bae6fd;
  --ntx-card-bg: #102334;
}
```

Link `/ocean-theme.css` and configure `themes: ['dark', 'light', 'ocean']`.
This is a partial palette override, not a complete theme: other recipe tokens
(buttons, status treatments, gradients) retain their declared defaults. For a
complete palette, review all tokens in the [dark](../src/n3tx_ui/static/dark-theme.css)
and [light](../src/n3tx_ui/static/light-theme.css) entrypoints. The app's
[industrial theme](../../../apps/veille/static/industrial-theme.css) demonstrates
a broader token-only theme.

| Token family | Examples |
|---|---|
| Typography | `--ntx-font-body`, `--ntx-font-display`, `--ntx-font-mono` |
| Geometry | `--ntx-space-4`, `--ntx-radius-md`, `--ntx-layout-sidebar-width` |
| Colors | `--ntx-color-text`, `--ntx-color-text-muted`, `--ntx-color-surface-1` |
| Components | `--ntx-card-bg`, `--ntx-input-bg`, `--ntx-button-primary-bg` |
| Status | `--ntx-status-error-fg/bg/border`, corresponding success/warning/accent tokens |
| Motion/shadow | `--ntx-duration-fast`, `--ntx-ease`, `--ntx-shadow-md` |
| Native icon | `--icon-stroke-width` |

`ntx-icon` SVGs inherit `--icon-stroke-width` from their host or an ancestor.
When unset, each SVG keeps its resolved registry `strokeWidth`, falling back to
`2`. An icon SVG's own `stroke-width` presentation attribute takes precedence
for the paths that declare it, so the token does not override explicit
per-path stroke widths.

The native icon registry includes `search` and `download` SVG icons, alongside
`dashboard`, `heart`, `star`, `reply`, `upload` and `user`. Use these shared names
with `<ntx-icon value="search" decorative>` instead of relying on optional emoji
fonts. This is registry data, not a separate renderer or application icon layer.

Use canonical tokens, not old aliases such as `--surface-*`, `--text-*`, or
`--accent`. Keep app-only styling out of shared `ntx-item.css`.

## Shadow DOM styles

For an `NTTItem` subclass stored in `static/components/`, preserve inherited CSS
and add a sibling app stylesheet through this getter:

```javascript
get styles() {
  const parent = super.styles;
  return [
    ...(Array.isArray(parent) ? parent : parent ? [parent] : []),
    new URL('./issue-card.css', import.meta.url).href,
  ];
}
```

```css
/* static/components/issue-card.css */
:host { display: block; }
.issue-title {
  color: var(--ntx-color-text-strong);
  font-family: var(--ntx-font-display);
  margin-block: 0 var(--ntx-space-4);
}
```

`Component` fetches CSS and shares constructable stylesheets across shadow roots.
Do not append a legacy `$styles` node. Global theme variables inherit through
shadow boundaries; global selectors do not. Standalone HTMLElement components may
use different stylesheet plumbing—inspect their source before extending them.

## Verification

Use the [test harness](../../../tests/frontend/README.md). Unit theme tests cover
persistence and cycling; real-browser checks are needed for computed CSS,
responsive containers, contrast, keyboard focus and overflow. Check both themes,
logged-in/out shells, multiple switchers, forced/automatic display sizes and a
narrow viewport. Do not infer mobile/accessibility correctness from token tests.

Sources: [theme runtime](../../n3tx-core/src/n3tx_core/static/utils/theme.js),
[base CSS](../src/n3tx_ui/static/theme-base.css),
[theme button](../src/n3tx_ui/static/components/ntx-theme-button.js).

## Changelog

- 2026-11-12: Document generic Search/Download vectors in the native registry;
  no new renderer or application icon mechanism.
