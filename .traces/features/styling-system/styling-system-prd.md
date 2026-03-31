# Styling System PRD

## Overview

Plan name: `styling-system`

Generated execution plan for a frontend-owned styling system that keeps schema semantic, introduces a stable public token contract, unifies stylesheet loading, exposes CSS parts and host/state attributes, and preserves dark/light compatibility.

## Wave 1

| ID | Title | Files |
|----|-------|-------|
| task-01 | Create public token packs | `styles/tokens/base.css`, `styles/tokens/dark.css`, `styles/tokens/light.css` |
| task-02 | Expand theme runtime API | `utils/theme.js` |
| task-03 | Extract reusable stylesheet loader | `core/stylesheets.js`, `core/Component.js` |

## Wave 2

| ID | Title | Depends On | Files |
|----|-------|------------|-------|
| task-04 | Bridge legacy theme entrypoints to tokens and recipe files | task-01 | `dark-theme.css`, `light-theme.css`, `styles/recipes/glass/global.css` |
| task-05 | Migrate shell components to shared loader | task-03 | `ntx-topbar.js`, `ntx-sidebar.js`, `ntx-profile.js` |
| task-06 | Migrate modal and toast to shared loader | task-03 | `ntx-modal.js`, `Toast.js` |

## Wave 3

| ID | Title | Depends On | Files |
|----|-------|------------|-------|
| task-07 | Add base loading, error, and empty-state hooks | task-03 | `Component.js`, `ntx-element.css` |
| task-08 | Make widget stylesheet adoption explicit | task-03 | `widgets/index.js`, `ntx-item.js`, `ntx-row.js` |

## Wave 4

| ID | Title | Depends On | Files |
|----|-------|------------|-------|
| task-09 | Expose stable styling surfaces on entity components | task-07 | `ntx-item.js`, `ntx-list.js` |
| task-10 | Expose stable styling surfaces on action and stream components | task-07 | `ntx-method.js`, `ntx-stream.js`, `ntx-stream-agent.js` |

## Wave 5

| ID | Title | Depends On | Files |
|----|-------|------------|-------|
| task-11 | Migrate entity and action CSS to semantic tokens | task-01, task-04, task-08, task-09, task-10 | `ntx-item.css`, `ntx-list.css`, `ntx-method.css` |
| task-12 | Migrate widget and shell CSS to semantic tokens | task-01, task-04, task-05, task-08 | `widgets.css`, `ntx-topbar.css`, `ntx-sidebar.css` |
| task-13 | Migrate modal, profile, and toast CSS to semantic tokens | task-01, task-04, task-06 | `ntx-modal.css`, `ntx-profile.css`, `Toast.css` |

## Wave 6

| ID | Title | Depends On | Files |
|----|-------|------------|-------|
| task-14 | Add unit and integration coverage | task-02, task-03, task-04, task-07, task-08 | `theme.test.js`, `Component.test.js`, `stylesheets.test.js` |
| task-15 | Add component and browser coverage for parts and theme compatibility | task-04, task-08, task-09, task-10, task-11, task-12, task-13 | `ntx-item.test.js`, `ntx-method.test.js`, `css-and-theming-unit.spec.js` |
| task-16 | Update styling documentation | task-04, task-07, task-08, task-09, task-10, task-11, task-12, task-13 | `FRONTEND.md`, `packages/n3tx-ui/docs/components.md`, `packages/n3tx-ui/docs/styling.md` |

## Acceptance Criteria

- Apps can keep using `dark-theme.css`, `light-theme.css`, and `theme.js` with no breakage.
- Framework CSS consumes a stable `--ntx-*` token system with legacy alias coverage.
- Standalone shadow components and `Component` share one stylesheet loading path.
- Widgets have an explicit styling contract instead of relying on incidental global CSS.
- Built-ins expose stable styling surfaces through `part` and host/state attributes.
- Tests and docs describe the new customization path clearly enough for follow-up agent execution.

## Execution Notes

- Favor additive compatibility over cleanup in early waves.
- Keep schema semantic; do not add theme palette data to Python model definitions.
- Run targeted frontend tests after each wave, then run the broader frontend suite at the end.
