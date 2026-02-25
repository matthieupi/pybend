# Navigation & Selection Primitives

> **Status:** Complete.
> **Scope:** Added client-side navigation (Router actor + ntt-router view container), collection selection API, and fixed duplicate network requests.

---

## Table of Contents

1. [Summary](#1-summary)
2. [Router Actor](#2-router-actor)
3. [NTTRouter Component](#3-nttrouter-component)
4. [SELECT Primitive](#4-select-primitive)
5. [Bug Fixes](#5-bug-fixes)
6. [File-by-File Changes](#6-file-by-file-changes)
7. [Verification](#7-verification)

---

## 1. Summary

Three composable primitives that enable client-side navigation without hardcoding any view types:

1. **SELECT** — general-purpose collection selection on ListElement (Set-based, multi-select ready)
2. **Router** (`core/Router.js`) — pure state Actor for navigation (route, history stack, hash sync, Observable)
3. **ntt-router** (`components/ntt-router.js`) — generic view container ("mini browser") that loads any component dynamically

### Navigation Flow

```
User clicks product card
  -> NTTItem sends TX { SELECT } to ListElement
  -> ListElement toggles selection, sends TX { NAVIGATE } to Router
  -> Router pushes stack, updates hash, notifies observers
  -> NTTRouter observes route change, mounts detail view
  -> Back button sends TX { BACK } to Router
  -> Router pops stack, NTTRouter restores slot content
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| Client-side navigation | None | Hash-synced, history-aware |
| View container | None | Generic ntt-router (loads any component) |
| Collection selection | None | Set-based API on ListElement |
| Comment network requests | 4x per comment | 1x per comment |
| Files to edit for new views | N/A | 0 (ntt-router is generic) |

---

## 2. Router Actor

**File:** `core/Router.js`

Pure navigation state — no DOM, no view management. Stores route data (string or object), manages a history stack, and optionally syncs with `location.hash`.

### Construction

```javascript
Actor.subclass(Router, Observable)
```

Router is an Actor with Observable mixin, registered with the Matrix via `matrix.register(this)` in the constructor. A module-level `Map` (`routers`) allows lookup by address via `getRouter(addr)`.

### State

| Property | Type | Description |
|----------|------|-------------|
| `#current` | `string\|object\|null` | Current route. `null` = home. |
| `#stack` | `Array` | History stack (previous routes). |
| `#hashSync` | `boolean` | Whether to sync string routes to `location.hash`. |

### TX Handlers

| Handler | Data | Behavior |
|---------|------|----------|
| `NAVIGATE(data)` | `string` or `object` | Dedup check, push old route to stack, set new route, update hash, `notify('route', new, old)`. |
| `BACK(data)` | (ignored) | Guard `canGoBack`, pop stack, update hash, `notify('route', new, old)`. |

### Hash Sync

- String routes serialize to `location.hash` (e.g., `#Product/3`).
- Object routes are programmatic-only (no hash representation).
- `null` route clears the hash via `history.replaceState`.
- `hashchange` events trigger `#fromHash()`, which updates Router state and notifies observers.

### Deduplication

NAVIGATE checks for identity (`data === this.#current`) and deep equality for objects (`JSON.stringify` comparison) before pushing.

---

## 3. NTTRouter Component

**File:** `components/ntt-router.js`
**CSS:** `components/ntt-router.css`
**Tag:** `<ntt-router>`

Generic view container — a "mini browser" controlled via its Router actor. Loads any component dynamically. Never needs editing to support new views.

### Usage

```html
<ntt-router name="main" hash>
    <ntt-list model="Product"></ntt-list>
</ntt-router>
```

### Attributes

| Attribute | Description |
|-----------|-------------|
| `name` | Router actor address. Auto-generated if omitted. |
| `hash` | Presence enables hash sync on the Router actor. |

### Lifecycle

1. **`connectedCallback`**: Creates or retrieves Router actor, subscribes to `observe('route')`, auto-sets `router` attribute on child `[model]` elements, calls initial `render()`.
2. **`disconnectedCallback`**: Unsubscribes from Router observer.

### Render Logic

```
route === null       -> #showSlot()     (restore <slot>, remove dynamic view)
route === string     -> #mountView()    (resolve tag from schema, set ref attr)
route === object     -> #mountView()    (use tag/attrs/title directly)
```

### Slot Persistence

When ntt-router shows a dynamic view, the `<slot>` is removed from shadow DOM but light DOM children (`<ntt-list>`) stay alive — they keep data, subscriptions, and state. Going back restores the `<slot>`, and the list re-projects instantly. No re-fetch, no re-render.

### Tag Resolution (String Routes)

For `"Product/3"`, resolves the component tag:

```
1. schema.ui.renderer.detail    (model-specific detail tag)
2. schema.ui.renderer.item      (model-specific item tag)
3. 'ntt-item'                   (framework default)
```

Uses `window.NTT.get(model)` for lazy access to avoid circular deps.

### Chrome

Only shown when a dynamic view is active:
- **Back button**: SVG left arrow, glass morphism style, sends `BACK` TX to Router.
- **Title**: Model name (string routes) or `routeData.title` (object routes).

---

## 4. SELECT Primitive

### ListElement Selection API

**File:** `components/ListElement.js`

Set-based multi-select primitive on the collection base class:

| Method | Description |
|--------|-------------|
| `selected` | `Set` of selected addresses (getter). |
| `select(addr)` | Add to selection. |
| `deselect(addr)` | Remove from selection. |
| `toggle(addr)` | Toggle in/out. |
| `clearSelection()` | Clear all. |

### SELECT TX Handler

```javascript
SELECT(data, tx) {
    this.toggle(data);
    const routerAddr = this.getAttribute('router');
    if (routerAddr) {
        this.send(new TX({ name: 'NAVIGATE', source: this.addr, target: routerAddr, data }));
    }
}
```

When a child item sends SELECT, the list toggles selection and optionally forwards as NAVIGATE.

### NTTItem Click-to-Select

**File:** `components/ntt-item.js`

Card click handler added in `#bindEvents()`:

- Fires on `.card` click (non-edit mode only).
- Skips interactive elements: `button, input, textarea, select, a, ntt-method`.
- Reads `select-target` attribute to find the parent list's address.
- Sends `TX { SELECT, data: this.ref }` to the list.

### select-target Wiring

`ListElement.createChild()` sets `select-target` on every child element, pointing back to the list's actor address. This works for both template-based and childTag-based children.

### CSS

`cursor: pointer` added to `.card[data-display="xs"]`, `.card[data-display="sm"]`, and `.card[data-display="md"]` in `ntt-item.css`.

### config.js

Three new event names in `config.E`:

```javascript
SELECT: "SELECT",
NAVIGATE: "NAVIGATE",
BACK: "BACK",
```

---

## 5. Bug Fixes

### Double ref setter in attributeChangedCallback

**File:** `core/Component.js`

**Before:** When `name === 'ref'`, `attributeChangedCallback` called `this.ref = newVal` (line 123) then fell through to `this[name] = newVal` (line 125), which called the ref setter a **second time**. Each call sent a READ TX, doubling network requests.

**Fix:** Added `return` after the `ref` handler (and `model` handler) to prevent fall-through to the generic `this[name] = newVal` assignment.

### Double render in NTTElement.DESCRIBE

**File:** `components/NTTElement.js`

**Before:** `DESCRIBE` set `this.value = data.data` (which auto-renders via the value setter when schema is available) and then called `this.render()` explicitly — rendering **twice** per DESCRIBE.

**Fix:** Removed the explicit `this.render()` call. The value setter already handles rendering.

### Combined effect

Each product card re-rendered twice (DESCRIBE double-render), and each render created comment `ntt-item` elements that each fired 2 READ requests (double ref setter). Total: **4x network requests per comment**. After fix: **1x**.

---

## 6. File-by-File Changes

### New Files

| File | Purpose | Lines |
|------|---------|-------|
| `core/Router.js` | Navigation state Actor (hash sync, history stack, Observable) | ~93 |
| `components/ntt-router.js` | Generic view container (slot, mount, back) | ~141 |
| `components/ntt-router.css` | Router chrome styles (back button, title, content area) | ~59 |

### Modified Files

| File | Changes |
|------|---------|
| `components/ListElement.js` | Added: `#selected` Set, selection API, `SELECT` handler, `select-target` on children |
| `components/ntt-item.js` | Added: TX import, card click handler in `#bindEvents()` |
| `components/ntt-item.css` | Added: `cursor: pointer` on xs, sm, md cards |
| `components/NTTElement.js` | Fixed: removed redundant `render()` call in DESCRIBE |
| `core/Component.js` | Fixed: `attributeChangedCallback` early returns for `ref` and `model` handlers |
| `config.js` | Added: `SELECT`, `NAVIGATE`, `BACK` to event enum |
| `matrix.html` | Wrapped `<ntt-list>` in `<ntt-router name="main" hash>`, added router import |
| `docs/COMPONENTS.md` | Added: Router, NTTRouter sections, ListElement selection API |
| `docs/ARCHITECTURE.md` | Added: Router in hierarchy + module map, navigation flow, updated status |

---

## 7. Verification

1. Open `matrix.html` — product list renders normally (ntt-router shows slot, no chrome)
2. Click a product card — back button + title + detail view appears
3. URL changes to `#Product/3`
4. Click back button — list restores instantly (slot, no re-fetch)
5. URL clears (hash removed)
6. Browser back/forward buttons work
7. Clicking edit button / inputs / methods does NOT trigger navigation
8. Page load with `#Product/2` in URL — detail view shown directly
9. Console: `matrix.children.get('main')` returns the Router actor
10. Network tab: each comment fetched exactly once (not 4x)
