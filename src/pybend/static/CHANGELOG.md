# NTTTX Frontend Change Log

# 0.7.0 (2026-02)

## Core
- **NTT.js** — Pagination meta storage (`_paginationMeta`) on DynamicClass
- **NTT.js** — READ handler detects paginated response format `{data, meta}`
- **NTT.js** — DELETE handler removes instances and notifies watchers
- **NTT.js** — ATTACH fetches individual entities when instance doesn't exist in registry
- **NTT.js** — Pending ATTACH queue replayed after READ completes
- **Component.js** — `ref` setter routes URL refs through ATTACH when `data-model` is present (caching/dedup)
- **NetworkAdapter.js** — Encodes `tx.data` objects as URL query params for READ transactions

## Components
- **`<ntt-user>`** — New component extending NTTItem with circular avatar rendering (xs/sm sizes)
  - Fallback to ui-avatars.com when no image is set
  - Wired automatically via User model `__ui__.renderer` config
- **`<ntt-item>`** — Delete button with confirmation dialog in md/lg/xl sizes (ABAC-gated)
  - Edit/delete buttons grouped in `card-actions` container
  - sm display: respects `field_order`, renders `$ref` fields as leading avatars
  - Replaced `#topFields()` with `#smFields()` for better field selection
  - Added `#resolveChildTag()` for schema-driven child component lookup
- **`ListElement`** — Pagination with `loadMore()`, page tracking, "Load More" button
  - Count display shows "current / total" when paginated
- **`<ntt-topbar>`** — Minor style refinements
- **`<ntt-method>`** — Minor formatting adjustment

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
