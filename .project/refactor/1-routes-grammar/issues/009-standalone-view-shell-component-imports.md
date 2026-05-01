# 009 — Standalone view shell imports resolved renderer modules

## Problem

Backend HTML/view routes can mount schema-resolved custom elements, such as
`<ntx-grant-item ref="Grant/6">`, while only importing the first-party base
component module. In a standalone backend response, the app shell has not loaded
Veille's custom component bundle, so the browser leaves the custom element
unupgraded and the page appears empty.

## Implementation

- Add a small helper in `n3tx_ui.mixin` to map a validated custom-element tag to
  the conventional static module URL: `/components/{tag}.js`.
- Render de-duplicated module imports for the base component plus the resolved
  renderer tag:
  - collection routes: `ntx-list`, resolved collection tag
  - member routes: `ntx-item`, resolved member tag
- Keep existing renderer-tag validation before inserting tags or module URLs
  into HTML.

## Verification

- `test_viewable_mixin.py` asserts custom collection/member renderers include
  their module scripts.
- Default `ntx-list` / `ntx-item` shell imports remain de-duplicated.
- Veille `/Grant/6/@` includes `/components/ntx-grant-item.js`.
