# Theme Ownership Overhaul - Implementation Plan

## Purpose

This document is written for a memoryless implementation agent.

Its job is to capture the current N3TX frontend theme architecture, the agreed design decisions, the exact scope of the overhaul, and the implementation sequence required to make theme entrypoints first-class owners of theme-specific style.

This plan is not the industrial visual transfer itself.

This plan is the prerequisite refactor that makes future themes such as `industrial-theme.css` viable without rewriting the framework every time.

Note: the repository convention is `.traces/`, not `traces/`. This file intentionally lives at `.traces/features/theme-overhaul/plan.md`.

---

## Required Reading Order

Before making code changes, read these files in this order:

1. `/workspace/docs/ARCHITECTURE.md`
2. `/workspace/FRONTEND.md`
3. `/workspace/packages/n3tx-ui/docs/components.md`
4. `/workspace/.traces/features/styling-system/styling-system.md`
5. `/workspace/packages/n3tx-core/src/n3tx_core/static/utils/theme.js`
6. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css`
7. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/light-theme.css`
8. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js`
9. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css`
10. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js`
11. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css`
12. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css`
13. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.css`
14. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.css`
15. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css`
16. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/auth.css`
17. `/workspace/packages/n3tx-core/src/n3tx_core/api/backend.py`
18. `/workspace/packages/n3tx-core/src/n3tx_core/ssr/bundler.py`

Then inspect the app surfaces and current HTML contracts:

19. `/workspace/apps/veille/static/index.html`
20. `/workspace/apps/veille/static/login.html`
21. `/workspace/apps/veille/static/register.html`
22. `/workspace/apps/veille/static/veille.css`
23. `/workspace/apps/veille/static/components/ntx-run-output.css`
24. `/workspace/apps/veille/static/components/ntx-run-report.css`
25. `/workspace/tests/frontend/tests/utils/theme.test.js`
26. `/workspace/tests/frontend/tests/e2e/theme-toggle.spec.js`
27. `/workspace/tests/frontend/tests/e2e/css-and-theming-unit.spec.js`

Do not start by rewriting component CSS blindly. Understand the current theme contract, static delivery model, and tests first.

---

## What Problem This Solves

The current theme architecture is asymmetric:

- `dark-theme.css` is both a theme file and the global structural base.
- `light-theme.css` is mostly an override layer on top of `dark-theme.css`.
- many component and app CSS files still encode theme-colored literals (`rgba(...)`, gradients, fallback hex values)
- topbar theme UI is currently binary and hardcoded to dark/light
- shipped pages manually link theme files, but the contract is duplicated and partly implicit

This blocks clean introduction of additional themes such as `industrial-theme.css`, because too many visual decisions still live outside theme entrypoints.

---

## Agreed Design Decisions

These decisions were explicitly resolved with the user and must be treated as fixed for this implementation unless they later change them.

| Topic | Decision |
|------|----------|
| Base/theme split | Add `theme-base.css`; theme files only own theme-specific values |
| HTML contract | Normalize all shipped pages and examples to the same stylesheet contract |
| Runtime toggle model | Use a fully generic theme cycle, not a binary dark/light-only toggle |
| Theme list source | Themes are declared in `index.html` via global inline config |
| Theme list shape | Use a global inline config with an array of strings |
| Theme CSS loading | Use static `<link>` tags, not dynamic JS injection |
| Theme control ownership | Build a reusable framework component in `n3tx-ui` |
| Theme control placement | Show the button in both sidebar and topbar on shell pages |
| Topbar placement | Inside the authenticated user dropdown |
| Logged-out pages | No theme switcher when logged out; those pages only honor persisted theme |
| Placement mode | Manual placement only; shell components must not auto-render the control based on config |
| Token strategy | Introduce canonical `--ntx-*` tokens now |
| Legacy variable policy | Remove legacy tokens aggressively after first-party consumers are migrated |
| Compatibility boundary | Migrate framework + Veille + first-party examples before dropping legacy names |
| Migration scope | Migrate major framework surfaces and Veille hotspots in this implementation |
| Status styling | Global default status tokens with app-specific overrides allowed |
| Theme ownership scope | Theme owns the scale system and color system |
| Effects ownership | Partial only: page atmosphere, shell effects, shadow scale, shared CTA treatment, shared status fills |
| Icon theming | Leave icon URI/color refactors for later unless one blocks this overhaul |
| Test contract | Test canonical tokens only |

Any implementation detail that conflicts with this table is wrong.

---

## Current State Summary

### Theme files

| File | Current role | Why it must change |
|------|--------------|--------------------|
| `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css` | Defines dark tokens and global selectors | Dark theme is incorrectly acting as the structural base |
| `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css` | Mostly scoped overrides | Depends on dark theme being loaded first |
| `packages/n3tx-core/src/n3tx_core/static/utils/theme.js` | localStorage + `data-theme` + `toggleTheme()` | UI/runtime contract is binary and does not reflect the new generic cycle model |

### Static delivery model

Important behavior already exists and should be reused, not reinvented:

- `packages/n3tx-core/src/n3tx_core/api/backend.py` discovers static dirs from `n3tx-agents`, `n3tx-ui`, and `n3tx-core`, then mounts them in cascading order.
- app statics are routed explicitly first, so app HTML and app CSS can override framework files.
- `packages/n3tx-core/src/n3tx_core/ssr/bundler.py` merges framework + app static dirs into one temporary namespace for SSR.

Implication: adding `theme-base.css` and future theme files is safe as long as the pages link them. The serving layer already supports that architecture.

### HTML contract today

Most pages explicitly load both `dark-theme.css` and `light-theme.css`, but not all. At least these pages are dark-only today:

- `packages/n3tx-ui/src/n3tx_ui/static/example.html`
- `examples/chat/static/index.html`

That inconsistency must be removed.

### Topbar and sidebar constraints

Current component constraints matter because the user chose manual placement:

- `ntx-topbar` currently has only a `nav` slot and renders the theme toggle internally as a hardcoded dropdown item.
- `ntx-sidebar` currently has no footer slot and no generic custom-action placement.

Because the chosen design is manual placement rather than auto-rendering, shell APIs must be expanded to support manual placement cleanly.

### Styling debt hotspots

The first migration sweep should target at least:

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css`
- `packages/n3tx-ui/src/n3tx_ui/static/auth.css`
- `apps/veille/static/veille.css`
- `apps/veille/static/components/ntx-run-output.css`
- `apps/veille/static/components/ntx-run-report.css`

---

## Architectural Invariants

These rules must hold after the migration:

1. Theme files own theme-specific values.
2. Shared structural selectors live outside theme files.
3. Components own structure and markup-specific styling, not palette policy.
4. The only public token contract after the overhaul is canonical `--ntx-*` tokens.
5. Legacy variables are transitional at most; final first-party code should not depend on them.
6. All first-party framework surfaces, Veille, and first-party examples must use the canonical token system before legacy names are dropped.
7. Theme button rendering is manual, not implicit.
8. Generic theme cycling order comes from inline page config, not hardcoded topbar logic.

---

## Target Architecture

## 1. Stylesheet ownership model

### Base stylesheet

Add:

- `packages/n3tx-ui/src/n3tx_ui/static/theme-base.css`

Responsibilities:

- global element selectors (`html`, `body`, headings, links, buttons, form controls)
- shared layout helpers (`.page`, shell spacing wrappers, responsive base spacing)
- selector structure for page atmosphere, selection, scrollbars, and base input/button behavior
- recipe defaults expressed only through tokens

This file must not define theme-specific colors or theme-specific recipe values directly.

### Theme entrypoint files

Files:

- `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css`
- `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css`
- future `packages/n3tx-ui/src/n3tx_ui/static/industrial-theme.css`

Responsibilities:

- define theme-owned token values only
- define canonical `--ntx-*` values
- define theme-owned recipe variables for shared effects that the user explicitly wants theme-owned

Recommended selector pattern:

```css
:root,
html[data-theme="dark"] {
  /* dark canonical tokens */
}

html[data-theme="light"] {
  /* light canonical tokens */
}

html[data-theme="industrial"] {
  /* industrial canonical tokens */
}
```

Dark stays the default fallback via `:root`.

### Shared component CSS

Files under:

- `packages/n3tx-ui/src/n3tx_ui/static/components/*.css`
- `packages/n3tx-ui/src/n3tx_ui/static/auth.css`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css`

Responsibilities:

- own component structure and selector layout
- consume canonical tokens only
- avoid legacy vars in final state
- avoid theme-specific color literals for migrated surfaces

### App CSS

Files under:

- `apps/veille/static/*.css`
- `apps/veille/static/components/*.css`

Responsibilities:

- own app-specific layout and domain composition
- consume framework canonical tokens
- allow narrow app-specific overrides when necessary (`--veille-*`)

### Runtime theme API

File:

- `packages/n3tx-core/src/n3tx_core/static/utils/theme.js`

Responsibilities:

- persist current theme name
- apply `document.documentElement.dataset.theme`
- expose generic theme cycling
- dispatch `theme-change`

---

## 2. Theme list and page-level config contract

The source of truth for available themes is page-provided global inline config in HTML.

Required shape:

```html
<script>
  window.NTX_THEME_CONFIG = {
    themes: ['dark', 'light', 'industrial']
  };
</script>
```

Important notes:

- order matters: the theme button cycles through the array order
- keep it as an array of strings; do not introduce object metadata in this overhaul
- the theme button reads this config
- runtime helpers may also read it for generic toggle/cycle behavior

### Page stylesheet contract

All shipped HTML entrypoints and first-party examples should normalize to:

```html
<link rel="stylesheet" href="./theme-base.css" />
<link rel="stylesheet" href="./dark-theme.css" />
<link rel="stylesheet" href="./light-theme.css" />
<!-- and future extra themes, statically linked -->
```

Static linking is required. Do not dynamically inject theme stylesheets in JS.

### Logged-out pages

The user explicitly chose not to expose a theme switcher when logged out.

That means:

- login/register pages may still link all supported stylesheets
- they still honor the persisted theme in `localStorage`
- but they do not need to render the theme control

Config can still be present on those pages for consistency, but the switcher must not be rendered there.

---

## 3. Theme control architecture

### Component ownership

Add a reusable framework component in `n3tx-ui`, likely:

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-theme-button.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-theme-button.css`

Responsibilities:

- read `window.NTX_THEME_CONFIG.themes`
- determine current theme
- cycle to the next theme in the configured order
- reflect current theme in its label/icon/state if appropriate
- listen to `theme-change` and re-render when multiple instances exist

### Placement model

The user chose manual placement only.

This means shell components must not auto-render a theme button simply because config exists.

Instead, pages manually place it in shell-supported regions.

### Authenticated shell placement

The user explicitly chose both placements on shell pages:

- bottom of the sidebar
- inside the authenticated user dropdown in the topbar

Therefore two instances may exist on the same page and must stay synchronized through `theme-change`.

### Logged-out placement

No theme switcher when logged out.

Do not add a visible topbar theme control to auth pages in this overhaul.

---

## 4. Shell API consequences of manual placement

These are implementation consequences of the chosen design, not optional ideas.

### `ntx-topbar`

Current state:

- only `nav` slot exists
- theme toggle is hardcoded as a binary dropdown item

Required change:

- remove hardcoded binary theme toggle logic
- add a manual insertion point inside the authenticated user dropdown, e.g. a slot like `slot="user-menu"` or equivalent structured insertion point

Goal:

- page authors can manually place `<ntx-theme-button slot="user-menu"></ntx-theme-button>`
- the topbar stops owning the theme toggle behavior directly

### `ntx-sidebar`

Current state:

- no footer slot exists
- light DOM parsing focuses on model templates and links

Required change:

- add a footer insertion point for manual placement, e.g. `slot="footer"`

Goal:

- page authors can manually place `<ntx-theme-button slot="footer"></ntx-theme-button>` at the bottom of the sidebar

### Important constraint

Do not make shell components auto-render theme UI from the config. The page must place the component explicitly.

---

## Canonical Token Contract

The final public contract should use canonical `--ntx-*` tokens.

Tests and docs should target canonical names only.

Legacy names such as `--surface-0`, `--text-0`, `--accent`, and `--border` may exist briefly during migration commits, but must not remain as the final first-party contract.

## 1. Foundation tokens

### Typography

- `--ntx-font-display`
- `--ntx-font-body`
- `--ntx-font-mono`

### Scale and geometry

The user wants theme ownership over the scale system and color system.

That means theme should own:

- `--ntx-space-1`
- `--ntx-space-2`
- `--ntx-space-3`
- `--ntx-space-4`
- `--ntx-space-5`
- `--ntx-radius-xs`
- `--ntx-radius-sm`
- `--ntx-radius-md`
- `--ntx-radius-lg`
- `--ntx-radius-xl`
- `--ntx-border-width`
- `--ntx-layout-topbar-height`
- `--ntx-layout-sidebar-width`
- `--ntx-layout-page-gutter`

### Motion and shadow scale

- `--ntx-duration-fast`
- `--ntx-duration-normal`
- `--ntx-duration-slow`
- `--ntx-ease`
- `--ntx-ease-out`
- `--ntx-shadow-xs`
- `--ntx-shadow-sm`
- `--ntx-shadow-md`
- `--ntx-shadow-lg`
- `--ntx-shadow-xl`

## 2. Semantic color/surface tokens

- `--ntx-color-page`
- `--ntx-color-surface-1`
- `--ntx-color-surface-2`
- `--ntx-color-surface-3`
- `--ntx-color-surface-4`
- `--ntx-color-overlay`
- `--ntx-color-text-strong`
- `--ntx-color-text`
- `--ntx-color-text-muted`
- `--ntx-color-text-subtle`
- `--ntx-color-accent`
- `--ntx-color-accent-strong`
- `--ntx-color-accent-text`
- `--ntx-color-success`
- `--ntx-color-warning`
- `--ntx-color-error`
- `--ntx-border-subtle`
- `--ntx-border-default`
- `--ntx-border-strong`
- `--ntx-border-interactive`
- `--ntx-line-subtle`
- `--ntx-focus-ring`
- `--ntx-backdrop-scrim`

## 3. Recipe tokens

### Buttons and inputs

- `--ntx-button-primary-bg`
- `--ntx-button-primary-fg`
- `--ntx-button-primary-border`
- `--ntx-button-primary-hover-bg`
- `--ntx-button-secondary-bg`
- `--ntx-button-secondary-fg`
- `--ntx-button-secondary-border`
- `--ntx-button-secondary-hover-bg`
- `--ntx-input-bg`
- `--ntx-input-fg`
- `--ntx-input-border`
- `--ntx-input-placeholder`
- `--ntx-input-focus-border`
- `--ntx-input-focus-ring`

### Cards and shell

- `--ntx-card-bg`
- `--ntx-card-hover-bg`
- `--ntx-panel-bg`
- `--ntx-panel-strong-bg`
- `--ntx-topbar-bg`
- `--ntx-topbar-border`
- `--ntx-topbar-shadow`
- `--ntx-sidebar-bg`
- `--ntx-sidebar-border`
- `--ntx-sidebar-overlay-bg`

### Status tokens

The user wants global defaults with app-specific overrides allowed.

Define:

- `--ntx-status-neutral-fg`
- `--ntx-status-neutral-bg`
- `--ntx-status-neutral-border`
- `--ntx-status-accent-fg`
- `--ntx-status-accent-bg`
- `--ntx-status-accent-border`
- `--ntx-status-success-fg`
- `--ntx-status-success-bg`
- `--ntx-status-success-border`
- `--ntx-status-warning-fg`
- `--ntx-status-warning-bg`
- `--ntx-status-warning-border`
- `--ntx-status-error-fg`
- `--ntx-status-error-bg`
- `--ntx-status-error-border`

App-level overrides such as `--veille-*` are allowed only when the app needs a more specific semantic on top of the global defaults.

## 4. Effects the theme must own

The user chose partial, not total, effect ownership.

Theme-owned effect families must include:

- page atmosphere/background treatment
- shell effects
- shadow scale
- shared CTA treatment
- shared status fills

Theme-owned effect tokens should include at least:

- `--ntx-page-background`
- `--ntx-page-atmosphere`
- `--ntx-page-grid`
- `--ntx-shadow-*`
- `--ntx-button-primary-*`
- status background/border tokens

Do not over-tokenize every decorative one-off flourish in the codebase.

---

## Runtime API Contract

Current `theme.js` exports:

- `getTheme()`
- `setTheme(theme)`
- `toggleTheme()`

That API should remain, but behavior changes.

## Required behavior after the overhaul

### `getTheme()`

- returns the persisted theme or default fallback

### `setTheme(theme)`

- writes `localStorage['ntx-theme']`
- writes `document.documentElement.dataset.theme`
- dispatches `theme-change`

### `toggleTheme()`

No longer binary.

It should cycle through the configured themes from `window.NTX_THEME_CONFIG.themes` in order.

If the current theme is not present in the configured list, choose a deterministic fallback, preferably the first configured theme or `'dark'` if config is missing.

### Suggested helpers

The implementation will likely benefit from helpers such as:

- `getConfiguredThemes()`
- `getNextTheme()`
- `hasThemeConfig()`

The exact helper names are flexible, but the runtime behavior is not.

---

## Implementation Phases

## Phase 0 - Baseline and contract audit

### Goal

Verify current theme assumptions and catalog affected first-party consumers.

### Tasks

- confirm all HTML entrypoints/examples that load themes
- confirm all first-party components and app CSS still using legacy vars or literals
- confirm test files that must be updated to canonical tokens only

### Output

- a concrete migration list of framework + Veille + examples

### Acceptance criteria

- the agent can explain which files are being migrated before legacy tokens are dropped

---

## Phase 1 - Split base selectors from theme files

### Goal

Create `theme-base.css` and strip theme files down to token ownership.

### Files

- add `packages/n3tx-ui/src/n3tx_ui/static/theme-base.css`
- modify `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css`
- modify `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css`

### Tasks

- move shared selectors out of `dark-theme.css`
- rewrite selector bodies so they depend on canonical `--ntx-*` tokens
- make `dark-theme.css` and `light-theme.css` token-only entrypoints
- do not preserve legacy token names as the final public contract

### Acceptance criteria

- shared selectors are no longer owned by `dark-theme.css`
- theme files define canonical tokens only, or canonical tokens plus temporary transitional internals during the implementation
- final first-party consumers are not expected to use legacy variable names

---

## Phase 2 - Update runtime theme API and page contracts

### Goal

Shift from binary toggle to generic configured theme cycling and normalize HTML contracts.

### Files

- `packages/n3tx-core/src/n3tx_core/static/utils/theme.js`
- all first-party HTML entrypoints and examples that currently load themes

This includes at least:

- `packages/n3tx-ui/src/n3tx_ui/static/login.html`
- `packages/n3tx-ui/src/n3tx_ui/static/register.html`
- `packages/n3tx-ui/src/n3tx_ui/static/example.html`
- `packages/n3tx-core/src/n3tx_core/static/schema.html`
- `apps/veille/static/index.html`
- `apps/veille/static/login.html`
- `apps/veille/static/register.html`
- `examples/core/static/index.html`
- `examples/core/static/login.html`
- `examples/core/static/register.html`
- `examples/actors/static/index.html`
- `examples/actors/static/login.html`
- `examples/actors/static/register.html`
- `examples/grants/static/index.html`
- `examples/grants/static/login.html`
- `examples/grants/static/register.html`
- `examples/pygentic/static/index.html`
- `examples/chat/static/index.html`
- `examples/chat/static/login.html`
- `examples/chat/static/register.html`

### Tasks

- add `theme-base.css` to all relevant pages
- normalize all first-party theme pages to static link tags for supported themes
- introduce `window.NTX_THEME_CONFIG = { themes: [...] }` where needed
- update `toggleTheme()` to use configured theme order rather than binary flip

### Acceptance criteria

- all first-party theme pages follow one explicit contract
- generic theme cycling works against the configured array order
- no dynamic theme CSS injection is used

---

## Phase 3 - Add the framework theme button and shell insertion points

### Goal

Replace hardcoded binary theme UI with a reusable, manually placed component.

### Files

- add `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-theme-button.js`
- add `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-theme-button.css`
- modify `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js`
- modify `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css`
- modify `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js`
- modify `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css`

### Tasks

#### `ntx-theme-button`

- read `window.NTX_THEME_CONFIG.themes`
- cycle themes in configured order
- listen to `theme-change`
- render correctly in both sidebar footer and topbar dropdown contexts

#### `ntx-topbar`

- remove the hardcoded binary theme-toggle button behavior
- add a manual insertion point inside the authenticated user dropdown
- ensure no switcher is shown when logged out

#### `ntx-sidebar`

- add footer placement support for manual theme button insertion
- keep existing model/link template behavior intact

### Important constraint

Shell components must not auto-render a theme button based on config.

The page must place the button explicitly.

### Acceptance criteria

- page authors can manually place the button in the sidebar footer and topbar dropdown
- multiple instances stay synchronized
- logged-out pages do not show a switcher

---

## Phase 4 - Migrate major framework CSS to canonical tokens

### Goal

Eliminate theme-coupled literals from the core migrated framework surfaces.

### Files

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css`
- `packages/n3tx-ui/src/n3tx_ui/static/auth.css`
- other directly affected framework CSS if migration exposes additional first-party legacy dependencies

### Tasks

- replace legacy variable usage with canonical `--ntx-*`
- replace repeated status literals with canonical status tokens
- move shared shell/page/button effects into theme-owned recipe tokens
- keep icon data URI cleanup deferred unless a migrated surface cannot work without it

### Acceptance criteria

- the migrated framework surfaces use canonical tokens only
- topbar/sidebar/item/list/table/method/auth visuals are theme-driven through the new contract

---

## Phase 5 - Migrate Veille and examples to canonical tokens

### Goal

Complete the user-approved compatibility boundary before dropping legacy names.

### Files

- `apps/veille/static/veille.css`
- `apps/veille/static/components/ntx-run-output.css`
- `apps/veille/static/components/ntx-run-report.css`
- example CSS/HTML surfaces that still depend on legacy theme names or assumptions

### Tasks

- replace legacy vars with canonical vars in Veille CSS
- use global default status tokens plus narrow app overrides only where needed
- ensure first-party examples follow the same canonical theme contract

### Acceptance criteria

- framework + Veille + first-party examples all work on the canonical token contract

---

## Phase 6 - Remove legacy variables aggressively

### Goal

Finish the migration by making canonical tokens the only first-party contract.

### Tasks

- remove legacy variable definitions from theme files once first-party consumers are migrated
- remove first-party CSS usages of `--surface-*`, `--text-*`, `--accent`, `--border`, etc.
- update docs and tests so legacy names are no longer treated as public or supported

### Acceptance criteria

- first-party code no longer relies on legacy variable names
- canonical tokens are the only documented/tested public contract

---

## Phase 7 - Update tests and docs

### Goal

Lock the new contract in and prevent regression.

### Files

- `FRONTEND.md`
- `packages/n3tx-ui/docs/components.md`
- add `packages/n3tx-ui/docs/styling.md`
- `tests/frontend/tests/utils/theme.test.js`
- `tests/frontend/tests/e2e/theme-toggle.spec.js`
- `tests/frontend/tests/e2e/css-and-theming-unit.spec.js`
- any framework component tests affected by new shell slots or theme-button component behavior

### Required documentation updates

Document:

- `theme-base.css` vs `<theme>-theme.css`
- static link tag requirement
- global inline `window.NTX_THEME_CONFIG = { themes: [...] }` contract
- manual placement of `ntx-theme-button`
- canonical `--ntx-*` token contract only

### Required test updates

Tests must now assert canonical tokens only.

At minimum verify:

- `--ntx-*` variables resolve correctly
- generic theme cycling works across configured themes
- persisted theme applies before paint
- sidebar and topbar theme buttons stay synchronized when both are rendered
- logged-out pages do not expose the switcher
- canonical token values differ correctly between dark and light themes

Do not preserve tests that treat legacy tokens as the public contract.

---

## Optional Follow-Up - Add `industrial-theme.css`

This overhaul prepares the system for it, but the theme file itself can be added after the architecture is stable.

### File

- `packages/n3tx-ui/src/n3tx_ui/static/industrial-theme.css`

### Expectations

- define canonical theme tokens and recipe variables for the industrial look
- rely on the new framework/app token contract rather than bespoke shared CSS rewrites

---

## Explicitly Deferred Work

These items are intentionally not first-wave requirements unless they block implementation:

- comprehensive icon URI to `currentColor` refactors
- richer theme metadata objects in config
- logged-out theme controls
- dynamic theme stylesheet loading
- backend/schema involvement in theme values

---

## Risks and Watchouts

### 1. Manual placement requires shell API changes

Because auto-rendering was rejected, shell components need real placement points. Do not fake this with brittle DOM post-processing.

### 2. Generic toggle changes public behavior

Existing tests and component logic assume binary dark/light toggling. `toggleTheme()` becoming a generic cycle will require coordinated code and test updates.

### 3. Aggressive alias removal increases required scope

Since the user wants legacy names removed aggressively, incomplete migration of examples or Veille is not acceptable.

### 4. Two button instances must stay in sync

Sidebar and topbar both show the button on shell pages. Synchronization must be event-driven and reliable.

### 5. Effects are only partially theme-owned

Do not over-tokenize decorative details. Only move page, shell, shadow, shared CTA, and shared status effects into the theme contract.

---

## Suggested Commit Slices

1. add `theme-base.css` and strip theme files to canonical token ownership
2. update runtime theme API and page-level HTML contracts
3. add `ntx-theme-button` and shell insertion points
4. migrate major framework CSS hotspots to canonical tokens
5. migrate Veille and examples to canonical tokens
6. remove legacy variables aggressively
7. update tests and docs
8. optional: add `industrial-theme.css`

---

## Verification Commands

Run at least:

```bash
cd /workspace/tests/frontend && npx vitest run
cd /workspace/tests/frontend && npx playwright test tests/e2e/theme-toggle.spec.js
cd /workspace/tests/frontend && npx playwright test tests/e2e/css-and-theming-unit.spec.js
```

If shell slot behavior or theme-button behavior gets its own unit tests, include those too.

---

## Done Definition

This plan is fully implemented when all of the following are true:

1. `theme-base.css` owns shared selectors and theme files own theme-specific values.
2. first-party pages/examples use a normalized static stylesheet contract.
3. `window.NTX_THEME_CONFIG = { themes: [...] }` is the page-level source for theme cycling order.
4. `toggleTheme()` cycles generically through configured themes.
5. `ntx-theme-button` exists as a framework component and is manually placed where needed.
6. authenticated shell pages can show the button in both sidebar footer and topbar dropdown.
7. logged-out pages honor the persisted theme but do not expose the switcher.
8. major framework CSS hotspots, Veille, and first-party examples use canonical `--ntx-*` tokens.
9. legacy theme variable names are no longer the first-party contract.
10. tests and docs describe and verify the new canonical contract.
