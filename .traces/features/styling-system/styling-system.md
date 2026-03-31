# Styling System - Execution Plan

## Summary

Design and implement a frontend-owned styling system for N3TX that gives the framework strong default visuals while making deep customization predictable, layered, and incremental. The schema keeps owning semantic rendering hints such as field order, groups, renderer choice, widget choice, and display density; the frontend owns tokens, recipes, stylesheet loading, widget styling, component parts, and theme/runtime APIs.

This plan intentionally avoids pushing visual decisions into Python model schema. The implementation stays primarily in `packages/n3tx-core/src/n3tx_core/static/`, `packages/n3tx-ui/src/n3tx_ui/static/`, `packages/n3tx-agents/src/n3tx_agents/static/`, and the frontend test/docs suite.

## Product Boundary

- Schema owns structure and semantics: `renderer`, `field_order`, `groups`, method layout, widget selection, and future display-mode semantics.
- Frontend owns appearance: token vocabulary, typography, color, spacing, motion, component recipes, shell chrome, widget styling, and theme switching.
- Applications customize in this order: token override -> recipe swap -> component replacement.

## Goals

1. Introduce a stable public token contract under `--ntx-*`.
2. Preserve current `dark-theme.css` and `light-theme.css` entrypoints for compatibility.
3. Separate token packs from opinionated recipe styling.
4. Unify shadow stylesheet loading around one reusable loader.
5. Expose stable styling surfaces for built-ins via `part` and host/state attributes.
6. Make widget styling explicit instead of accidental.
7. Add first-class loading, error, and empty-state styling hooks.
8. Keep current theme toggle behavior working while expanding the runtime API.
9. Ship tests and docs alongside the implementation.

## Non-Goals

- No backend-driven theme palette or raw visual config in schema.
- No CSS-in-schema fields.
- No destructive rewrite of built-in components.
- No removal of legacy token names in the first migration.
- No forceful redesign of example apps beyond adapting to the new contracts.

## Design Contract

### 1. Public Token Layer

Create a semantic token vocabulary under `packages/n3tx-ui/src/n3tx_ui/static/styles/tokens/`.

Core families:

- Color: `--ntx-color-bg`, `--ntx-color-surface-1..4`, `--ntx-color-text-strong`, `--ntx-color-text`, `--ntx-color-text-muted`, `--ntx-color-accent`, `--ntx-color-success`, `--ntx-color-warning`, `--ntx-color-error`
- Border and glass: `--ntx-border-subtle`, `--ntx-border-strong`, `--ntx-glass-bg`, `--ntx-glass-border`, `--ntx-glass-blur`
- Type: `--ntx-font-body`, `--ntx-font-display`, `--ntx-font-mono`
- Space and radius: `--ntx-space-*`, `--ntx-radius-*`
- Shadow and motion: `--ntx-shadow-*`, `--ntx-duration-*`, `--ntx-ease-*`

Legacy names such as `--surface-0`, `--text-0`, `--accent`, `--border`, `--radius-sm`, and `--shadow-sm` stay alive as aliases during the migration.

### 2. Recipe Layer

Themes become composition, not a single monolithic CSS file:

- Token packs set semantic values.
- Recipe files provide the framework default look.
- The first recipe is `glass`, extracted from the current visual language.

Compatibility rule: `dark-theme.css` and `light-theme.css` stay as the public files loaded by app HTML, but they become thin bridges that import tokens plus the default recipe.

### 3. Stylesheet Loader Contract

`Component` already centralizes adopted stylesheet loading. The new system extracts that logic into a reusable utility so standalone elements such as `ntx-topbar`, `ntx-sidebar`, `ntx-profile`, `ntx-modal`, and `Toast` can use the same cache and adoption path.

One loader contract means:

- one cache for fetched CSS
- one way to adopt single or multiple stylesheet URLs
- consistent no-FOUC behavior
- no custom one-off `<link>` injection paths in framework code

### 4. Stable Styling Surfaces

Built-ins expose stable styling surfaces so apps do not need brittle internal selectors:

- host attributes for semantic state: `display`, `mode`, `data-state`
- `part` names for key internal nodes

Initial public parts:

- `ntx-item`: `container`, `header`, `title`, `subtitle`, `fields`, `field`, `field-label`, `field-value`, `methods`, `actions`, `empty`, `error`, `loading`
- `ntx-list`: `container`, `header`, `title`, `count`, `actions`, `items`, `empty`, `load-more`
- `ntx-method` and `ntx-stream`: `container`, `legend`, `form`, `label`, `input`, `button`, `output`
- `ntx-stream-agent`: `container`, `entries`, `entry`, `entry-content`, `footer`

### 5. Widget Styling Contract

Widgets remain the field-level rendering extension point, but widget CSS must become explicit:

- widget modules export shared stylesheet URLs
- components that render widgets adopt those styles intentionally
- widget classes shift to semantic tokens instead of ad hoc colors

### 6. Runtime Theme API

`theme.js` grows from a dark/light toggle helper into a small registry while preserving current behavior:

- keep `getTheme()`, `setTheme()`, `toggleTheme()`
- keep `localStorage['ntx-theme']`
- keep `document.documentElement.dataset.theme`
- add registration and token-patching APIs for apps

## Compatibility Rules

1. Existing apps that load `dark-theme.css`, `light-theme.css`, and `theme.js` must keep working.
2. Existing CSS variables remain readable through alias mapping during the migration.
3. Existing custom components that override `get styles()` remain valid.
4. Schema contracts stay semantic; no migration is required in Python models.
5. Built-in visuals can change internally, but stable tag names and new `part` contracts become the supported customization API.

## Execution Waves

### Wave 1 - Foundations

- `task-01` Create public token packs
- `task-02` Expand the theme runtime API
- `task-03` Extract a reusable stylesheet loader and wire `Component` to it

### Wave 2 - Bridge and Loader Adoption

- `task-04` Rewire legacy theme entrypoints into tokens plus the default recipe
- `task-05` Migrate shell components to the shared stylesheet loader
- `task-06` Migrate modal and toast to the shared stylesheet loader

### Wave 3 - State and Widget Contracts

- `task-07` Add base loading, error, and empty-state hooks
- `task-08` Make widget stylesheet adoption explicit

### Wave 4 - Public Styling Surfaces

- `task-09` Add stable `part` and host/state attributes to entity components
- `task-10` Add stable `part` and host/state attributes to action and stream components

### Wave 5 - Token Migration

- `task-11` Migrate entity and action CSS to semantic/component tokens
- `task-12` Migrate widget and shell CSS to semantic/component tokens
- `task-13` Migrate modal, profile, and toast CSS to semantic/component tokens

### Wave 6 - Verification and Documentation

- `task-14` Add unit and integration tests for the new contracts
- `task-15` Add component and browser coverage for parts, themes, and compatibility
- `task-16` Update frontend and UI docs with the new styling system

## File and Package Targets

### New frontend files

- `packages/n3tx-ui/src/n3tx_ui/static/styles/tokens/base.css`
- `packages/n3tx-ui/src/n3tx_ui/static/styles/tokens/dark.css`
- `packages/n3tx-ui/src/n3tx_ui/static/styles/tokens/light.css`
- `packages/n3tx-ui/src/n3tx_ui/static/styles/recipes/glass/global.css`
- `packages/n3tx-core/src/n3tx_core/static/core/stylesheets.js`
- `packages/n3tx-ui/docs/styling.md`
- `tests/frontend/tests/core/stylesheets.test.js`

### Core runtime files

- `packages/n3tx-core/src/n3tx_core/static/core/Component.js`
- `packages/n3tx-core/src/n3tx_core/static/utils/theme.js`
- `packages/n3tx-core/src/n3tx_core/static/utils/Toast.js`
- `packages/n3tx-core/src/n3tx_core/static/utils/Toast.css`

### UI component files

- `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css`
- `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-element.css`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css`

### Agent UI files

- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`

### Test and docs files

- `tests/frontend/tests/utils/theme.test.js`
- `tests/frontend/tests/core/Component.test.js`
- `tests/frontend/tests/components/ntx-item.test.js`
- `tests/frontend/tests/components/ntx-method.test.js`
- `tests/frontend/tests/e2e/css-and-theming-unit.spec.js`
- `FRONTEND.md`
- `packages/n3tx-ui/docs/components.md`

## Agent Guidance

- Keep schema semantic. Do not add backend-owned theme values to `__ui__`.
- Prefer additive compatibility layers over flag-day rewrites.
- Do not delete legacy variables until all framework CSS consumes `--ntx-*` or explicit component aliases.
- When exposing `part`, choose names that describe roles rather than current markup shape.
- When adding state hooks, ensure loading and error paths remain minimal defaults that apps can override.
- When moving stylesheet loading, preserve current component behavior and avoid flashes of unstyled shadow content.

## Verification Strategy

- Frontend unit tests: `cd /workspace/tests/frontend && npx vitest run`
- Targeted browser coverage: `cd /workspace/tests/frontend && npx playwright test tests/e2e/css-and-theming-unit.spec.js`
- Existing theme-toggle coverage: `cd /workspace/tests/frontend && npx playwright test tests/e2e/theme-toggle.spec.js`

## Deliverables

1. A stable public styling contract for apps and future custom components.
2. A compatibility bridge that preserves current theme loading and token names.
3. A unified stylesheet loader for both Component-based and standalone elements.
4. Stable `part` and host/state attributes for core built-ins.
5. Test coverage and documentation describing the new customization path.
