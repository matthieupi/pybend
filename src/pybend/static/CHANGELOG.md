# NTTTX Frontend Change Log

# 0.7.0 (2026-02)

## Core
- **NTT.js** — `DynamicClass.CREATE` static handler: registers new instances in registry, notifies list watchers
- **NTT.js** — Instance `READ` handler for `pull()` responses (updates entity data in-place)
- **NTT.js** — Instance `_response_` handler: auto-pulls entity after method calls (e.g., comment)
- **NTT.js** — Pagination meta storage (`_paginationMeta`) on DynamicClass
- **NTT.js** — READ handler detects paginated response format `{data, meta}`
- **NTT.js** — DELETE handler removes instances and notifies watchers
- **NTT.js** — ATTACH fetches individual entities when instance doesn't exist in registry
- **NTT.js** — Pending ATTACH queue replayed after READ completes
- **NTTElement.js** — `DESCRIBE()` subscribes to entity signal for live updates; components auto-refresh on data changes
- **NTTElement.js** — `disconnectedCallback()` cleans up entity signal subscriptions
- **Component.js** — `ref` setter routes URL refs through ATTACH when `data-model` is present (caching/dedup)
- **NetworkAdapter.js** — Fixed DELETE to not send request body (`HTTP.remove(target, callback, onError)`)
- **NetworkAdapter.js** — Encodes `tx.data` objects as URL query params for READ transactions
- **Permissions.js** — `canAction()` accepts resource data for resource-aware OWNER evaluation
- **Permissions.js** — `#evaluateOwner()` compares resource owner field to current user ID; handles FK-hydrated hrefs

## Components
- **`<ntt-user>`** — New component extending NTTItem with circular avatar rendering (xs/sm sizes)
  - Fallback to ui-avatars.com when no image is set
  - Wired automatically via User model `__ui__.renderer` config
- **`<ntt-item>`** — Resource-aware permission checks: passes entity data to `canAction()` for real OWNER evaluation
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
- **`<ntt-topbar>`** — Minor style refinements
- **`<ntt-method>`** — Removed manual `setTimeout` pull(); entity signal handles post-method updates
- **Formidable (`form.js`)** — Protected fields (`ui.protected`) hidden in edit mode, forced to display-only

## Pages
- **schema.html** — Complete rewrite as kitchen sink demo page
  - Hero with brand, version badge, live auth status
  - Adaptive display sizes: xs pill, sm row, md card, lg detail (Product + User)
  - Live `<ntt-list>` + `<ntt-router>` with hash-sync navigation
  - Collapsible JSON schema inspector with syntax-colored values
  - ABAC permission check panel with allowed/denied badges
  - Glass morphism sections, `ks-` prefixed CSS, responsive grid
- **matrix.html** — Added ntt-user import

## Documentation
- Updated COMPONENTS.md with ntt-user, delete, and pagination docs
- Updated MESSAGE_PROTOCOL.md with DELETE handling and paginated READ format
- Updated TRANSPORT.md with query parameter encoding
