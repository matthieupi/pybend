# N3TXTX Frontend Change Log

# 0.7.0 (2026-02)

## Core
- **N3TX.js** — Instance `href` derived from entity `$id` when available (correct nested CRUD path for join entities)
- **N3TX.js** — ATTACH handler updates `href` from `tx.meta.href` when component provides a more specific URL
- **N3TX.js** — Instance `READ` handler runs `normalizePopulated()` on pull responses (converts `{data, meta}` wrappers to href arrays)
- **N3TX.js** — `DynamicClass.CREATE` static handler: registers new instances in registry, notifies list watchers
- **N3TX.js** — Instance `READ` handler for `pull()` responses (updates entity data in-place)
- **N3TX.js** — Instance `_response_` handler: auto-pulls entity after method calls (e.g., comment)
- **N3TX.js** — Pagination meta storage (`_paginationMeta`) on DynamicClass
- **N3TX.js** — READ handler detects paginated response format `{data, meta}`
- **N3TX.js** — DELETE handler removes instances and notifies watchers
- **N3TX.js** — ATTACH fetches individual entities when instance doesn't exist in registry
- **N3TX.js** — Pending ATTACH queue replayed after READ completes
- **NTTElement.js** — `DESCRIBE()` subscribes to entity signal for live updates; components auto-refresh on data changes
- **NTTElement.js** — `disconnectedCallback()` cleans up entity signal subscriptions
- **Component.js** — `ref` setter routes URL refs through ATTACH when `data-model` is present (caching/dedup)
- **NetworkAdapter.js** — Fixed DELETE to not send request body (`HTTP.remove(target, callback, onError)`)
- **NetworkAdapter.js** — Encodes `tx.data` objects as URL query params for READ transactions
- **Permissions.js** — `canAction()` accepts resource data for resource-aware OWNER evaluation
- **Permissions.js** — `#evaluateOwner()` compares resource owner field to current user ID; handles FK-hydrated hrefs

## Components
- **`<ntx-method>`** — New "button" layout: compact icon + count pill for social actions (like, favorite)
  - SVG icon library (heart, star, reply, default) with hover/active transitions
  - `count-field` attribute reads collection length from entity data; handles populated wrappers (`{data, meta}`)
  - `renderButton()` alongside existing `renderFieldset()` / `renderInline()`
  - `#postCall()` extracted for shared post-invoke logic across all layouts
  - Observes new attributes: `icon`, `count-field`
- **`<ntx-item>`** — sm() renders button-layout methods (like/favorite) and reply button inline
  - Reply button toggles inline input box with submit (Enter key or click); parent auto-refreshes
  - `reply-indent` CSS class for comments with `parent_id` (selfref) — left border + margin indent
  - Handles populated `$ref` fields: extracts `$id` from objects for avatar rendering (no more `[object Object]`)
  - `#patchListField()` normalizes populated wrappers for correct diff comparison
  - Passes `ref` to `Formidable.getForm()` context
  - Standalone methods receive `layout`, `icon`, `count-field` attributes from schema UI hints
- **`<ntx-favorites>`** — New page component for `#@favorites` route; wraps `<ntx-list model="ProductLike">`
- **`<ntx-topbar>`** — Favorites nav link for authenticated users; `topbar-nav` CSS block
- **`<ntx-logs>`** — Depth guard (max 8) on JSON renderer to prevent stack overflow
- **`<ntx-user>`** — New component extending NTTItem with circular avatar rendering (xs/sm sizes)
  - Fallback to ui-avatars.com when no image is set
  - Wired automatically via User model `__ui__.renderer` config
- **`<ntx-item>`** — Resource-aware permission checks: passes entity data to `canAction()` for real OWNER evaluation
  - Delete routes through DynamicClass for proper registry cleanup; uses `ref` URL for nested entities
  - sm size: edit/delete action buttons with hover reveal and CSS transitions
  - sm edit mode delegates to md() for full form experience
  - Layout size adjusts when editing in compact sizes (sm/xs → md layout)
  - Delete button with confirmation dialog in md/lg/xl sizes (ABAC-gated)
  - Edit/delete buttons grouped in `card-actions` container
  - sm display: respects `field_order`, renders `$ref` fields as leading avatars
  - Replaced `#topFields()` with `#smFields()` for better field selection
  - Added `#resolveChildTag()` for schema-driven child component lookup
- **`ListElement`** — Pagination with `loadMore()`, page tracking, "Load More" button
  - Count display shows "current / total" when paginated
- **`<ntx-topbar>`** — Minor style refinements
- **`<ntx-method>`** — Removed manual `setTimeout` pull(); entity signal handles post-method updates
- **Formidable (`form.js`)** — Passes `icon` and `count-field` attributes to `<ntx-method>` for button layout
  - Normalizes populated wrappers in `getListInput()` (`{data: [...], meta: {...}}` → plain array)
  - Handles populated objects' `$id` as refs alongside plain href strings
- **Formidable (`form.js`)** — Protected fields (`ui.protected`) hidden in edit mode, forced to display-only

## Pages
- **schema.html** — Complete rewrite as kitchen sink demo page
  - Hero with brand, version badge, live auth status
  - Adaptive display sizes: xs pill, sm row, md card, lg detail (Product + User)
  - Live `<ntx-list>` + `<ntx-router>` with hash-sync navigation
  - Collapsible JSON schema inspector with syntax-colored values
  - ABAC permission check panel with allowed/denied badges
  - Glass morphism sections, `ks-` prefixed CSS, responsive grid
- **index.html** — Added ntx-user import

## Pages
- **index.html** — Added `ntx-favorites.js` import (modulepreload + module)

## Tests
- **test_routing.py** — Playwright test verifying like/reply/favorite POST to correct nested API paths
- **test_social.py** — Playwright test suite: schema validation, toggle actions, reply, collection routes, frontend rendering (15 checks)

## Documentation
- Updated COMPONENTS.md with ntx-user, delete, and pagination docs
- Updated MESSAGE_PROTOCOL.md with DELETE handling and paginated READ format
- Updated TRANSPORT.md with query parameter encoding
