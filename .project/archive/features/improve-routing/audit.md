# NTX Router — Deep Architecture Audit

## System Overview

The routing system has two layers, split across packages:

| Layer | File | Package | Responsibility |
|-------|------|---------|----------------|
| **Router** (state machine) | `static/core/Router.js` | n3tx-core | Pure state: history stack, hash sync, Observable notifications |
| **NTTRouter** (view container) | `static/components/ntx-router.js` | n3tx-ui | DOM: mounts/unmounts components in response to route changes |

Communication is fully TX-based through the Matrix actor system. No direct method calls between components.

### Interaction Map

```
Producers (send NAVIGATE/BACK)          State Machine       Consumer (renders)
──────────────────────────────          ─────────────       ──────────────────
ntx-sidebar → NAVIGATE TX ───┐
                              ├──→ Router Actor ──observe──→ NTTRouter
ListElement → NAVIGATE TX ───┤     (#stack + #current)       (#mountView)
                              │     hash ↔ location.hash
ntx-router back btn → BACK ──┘
```

### Route Data Shapes (Current)

Route data is polymorphic — three different shapes flow through the same channel:

```javascript
// 1. Entity ref (string) — from ListElement SELECT → NAVIGATE
"Product/3"

// 2. App route (string) — convention: @ prefix
"@profile"

// 3. Programmatic route (object) — from ntx-sidebar
{ tag: 'ntx-table', attrs: { model: 'Grant', 'allow-create': '' }, title: 'Grant' }
```

### Navigation Flow (End-to-End)

```
User clicks item in ntx-list
  → ntx-item #bindEvents() sends SELECT TX to select-target (ListElement addr)
    → ListElement.SELECT() forwards as NAVIGATE TX to router attr address
      → Router.NAVIGATE() pushes to stack, updates hash, notifies observers
        → NTTRouter render() calls #mountView(routeData)
          → Resolves tag from schema ui.renderer or convention
          → Creates element, sets attrs, mounts in shadow DOM
```

```
User clicks model name in ntx-sidebar
  → #navigateToModel() constructs {tag, attrs, title} object
    → Dynamic import('../core/Matrix.js') → matrix.dispatch(NAVIGATE TX)
      → Router.NAVIGATE() ... (same as above)
```

---

## Component Inventory

### Router.js (n3tx-core/static/core/Router.js)

**What it is**: Pure Actor + Observable state machine. No DOM. No view logic.

**State**:
- `#current` — active route data (string | object | null)
- `#stack` — history array (LIFO)
- `#hashSync` — boolean, controls URL hash binding

**TX Handlers**:
- `NAVIGATE(data)` — dedup check → push old to stack → set current → update hash → notify
- `BACK()` — pop from stack → set current → update hash → notify

**Hash sync**:
- `#toHash()` — writes `location.hash` (strings only, objects silently skip)
- `#fromHash()` — reads `location.hash`, pushes to stack, notifies

**Global registry**: Module-level `const routers = new Map()` + `getRouter(addr)` export.

**Observable mixin**: Applied via `Actor.subclass(Router, Observable)`. Fires `notify('route', newRoute, oldRoute)` on every state change.

**Deduplication**:
- Strings: `===` equality
- Objects: `JSON.stringify()` comparison (order-dependent, fragile)

### NTTRouter (n3tx-ui/static/components/ntx-router.js)

**What it is**: View container web component. Creates/destroys child components when the Router state changes.

**Attributes**:
- `name` — Router actor address (default: `router-{addr}`)
- `hash` — Enable hash sync (presence attribute)

**Key methods**:
- `connectedCallback()` — creates or retrieves Router actor, observes `'route'` property, auto-wires `router` attr on child `[model]` elements
- `render()` — dispatches to `#mountView()` or `#showSlot()` based on Router.current
- `#showSlot()` — destroys current view, shows `<slot>` (home page content)
- `#mountView(routeData)` — resolves route → tag + attrs, builds chrome (back btn + title), creates and mounts element
- `#resolveTag(model)` — checks schema `ui.renderer.detail` → `ui.renderer.item` → fallback `'ntx-item'`

**Route resolution logic** (in `#mountView`):

| Route shape | Example | Resolved tag | Attrs |
|------------|---------|-------------|-------|
| `@name` string | `@profile` | `ntx-{name}` | none |
| Plain string | `Product/3` | Schema `ui.renderer.detail` or `ntx-item` | `ref: "Product/3"` |
| Object with `tag` | `{tag:'ntx-table', attrs:{model:'Grant'}}` | Object's `tag` | Object's `attrs` |
| Anything else | — | Falls back to `#showSlot()` | — |

### ntx-sidebar.js (n3tx-ui/static/components/ntx-sidebar.js)

**NOT an Actor** — extends plain `HTMLElement`, not Component. Uses `matrix.dispatch()` via dynamic import to send TX messages.

**Route template system**: Children with `model` attribute serve as declarative route templates. Three entry types:
- `model` (ntx-list/ntx-table child) — expandable accordion, click name → navigate to list view
- `item` (ntx-item child) — singleton nav, click → navigate to item detail
- `link` (anchor child) — raw href navigation

**Navigation methods** (all three do: get router addr → construct route data → dispatch NAVIGATE TX → close sidebar):

| Method | Route data shape | Hash-serializable? |
|--------|-----------------|-------------------|
| `#navigateToModel(name)` | `{tag, attrs: {model, ...template}, title}` | No |
| `#navigateToItem(name)` | `{tag, attrs: {ref, model, ...template}, title}` | No |
| `#navigateToLink(href)` | Raw href string | Yes |

### ListElement.js (n3tx-ui/static/components/ListElement.js)

**Router interaction**: `SELECT` handler (line 104-110):
```javascript
SELECT(data, tx) {
    this.toggle(data);
    const routerAddr = this.getAttribute('router');
    if (routerAddr) {
        this.send(new TX({ name: 'NAVIGATE', source: this.addr, target: routerAddr, data: data }));
    }
}
```

The `router` attribute is set:
1. Automatically by NTTRouter's `connectedCallback()` on slot children
2. By ntx-sidebar's `#ensureList()` when lazy-creating accordion lists
3. Manually in HTML

### ntx-item.js — SELECT Dispatch

Items don't know the router. They send `SELECT` to their `select-target` (the parent ListElement):

```javascript
// Card click → SELECT TX to parent list
this.shadowRoot.querySelector('.card')?.addEventListener('click', (e) => {
    if (e.target.closest('button, input, ...')) return; // skip interactive elements
    const target = this.getAttribute('select-target');
    if (target) {
        this.send(new TX({ name: 'SELECT', source: this.addr, target, data: this.ref }));
    }
});
```

The `select-target` attribute is set by `ListElement.createChild()`.

### Component.js — Router Attribute Handling

Component does NOT directly interact with Router. It:
- Accepts `router` as a pass-through attribute (not in `observedAttributes`)
- Components read it via `getAttribute('router')` when needed
- `connectedCallback()` does NOT auto-wire router — that's NTTRouter's job

### Observable.js — Notification Pattern

Router extends Actor + Observable mixin. The observe/notify pattern:
```javascript
// Producer (Router)
this.notify('route', newRoute, oldRoute);

// Consumer (NTTRouter)
router.observe('route', () => this.render());
// Callback receives: (newValue, oldValue, property, source)
```

---

## Issues Found

### Issue 1: Dual Routing Authority in Veille App (Critical)

**File**: `apps/veille/static/index.html` (lines 276-309)

The veille app has both `<ntx-router name="main">` AND a manual `handleRoute()` function:

```javascript
function handleRoute() {
    const hash = window.location.hash.replace('#', '') || '';
    const panels = ['run-panel', 'source-panel', 'analyze-panel', 'report-panel'];
    panels.forEach(id => { document.getElementById(id).style.display = 'none'; });
    if (hash === 'sources') { ... }
    else if (hash.startsWith('analyze/')) { ... }
}
window.addEventListener('hashchange', handleRoute);
```

**Why this exists**: The Router can't handle parameterized routes (`analyze/123`, `report/456`) or multi-panel tab-like views. The app needed these, so it bypassed the framework entirely.

**Consequences**:
- Two systems fight over the same hash
- Router's `#fromHash()` fires alongside `handleRoute()`, causing undefined behavior
- NTTRouter chrome (back button, title) appears for Router-managed routes but not for manual ones
- Sidebar navigation (object routes) doesn't sync with hash, so refresh loses state while manual routes do persist

### Issue 2: Object Routes Don't Survive Hash Round-Trip (Major)

**Files**: `Router.js:66-70`, `ntx-sidebar.js:282-289`

Sidebar navigation sends object route data: `{ tag: 'ntx-table', attrs: { model: 'Grant' }, title: 'Grant' }`. Router's `#toHash()`:

```javascript
#toHash() {
    if (typeof this.#current === 'string') {
        location.hash = this.#current;  // ✓ Works
    } else if (this.#current === null) {
        history.replaceState(null, '', ...);
    }
    // Object routes: silently ignored — hash not updated
}
```

**Impact**: All sidebar-initiated navigation is ephemeral. Refresh → lost. Browser back → doesn't work. Can't bookmark or share.

### Issue 3: No Parameterized Routes (Major)

**Files**: `Router.js`, `ntx-router.js:81-100`

Route matching is purely by shape detection (string with `/`, string with `@`, object with `tag`). There's no concept of:
- Path parameters: `Product/:id/comments`
- Query parameters: `Product?view=table&sort=price`
- Nested routes: `Grant/3/analyze`

This forces apps to either bypass the Router (veille's `handleRoute()`) or flatten all views to entity refs.

### Issue 4: Sidebar is Not an Actor (Design Inconsistency)

**File**: `ntx-sidebar.js:61`

```javascript
class NTTSidebar extends HTMLElement { ... }  // NOT Component, NOT Actor
```

Every other interactive component in N3TX extends Component (which mixes in Actor). The sidebar dynamically imports Matrix to dispatch TXs:

```javascript
import('../core/Matrix.js').then(({ matrix }) => {
    matrix.dispatch({ name: 'NAVIGATE', source: 'sidebar', target: routerAddr, data: ... });
});
```

This is the only component in the system that uses `matrix.dispatch()` directly instead of `this.send()`.

**Why it matters**: The sidebar can't be an interceptor target, can't receive TX messages, and uses a hardcoded `source: 'sidebar'` string instead of a real actor address.

### Issue 5: Full DOM Rebuild on Every Navigation (Performance)

**File**: `ntx-router.js:81-138`

`#mountView()` completely rebuilds the shadow DOM on every route change:

```javascript
this.shadowRoot.innerHTML = `
    <div class="router-chrome">...</div>
    <div class="router-content"></div>
`;
const el = document.createElement(tag);
...
this.shadowRoot.querySelector('.router-content').appendChild(el);
```

No keep-alive, no component caching. Navigating back to a previously-visited list means:
- Fresh component construction
- Fresh schema resolution
- Fresh READ from backend
- Full re-render

### Issue 6: No Route Guards or Middleware (Missing Feature)

**Files**: `Router.js`

The Actor system has interceptors (`use()`) but Router doesn't support them for navigation. There's no way to:
- Prevent navigation (unsaved changes guard)
- Redirect (auth check, permission gate)
- Transform route data before view mount
- Run async checks before navigation commits

### Issue 7: Title Resolution is Ad Hoc (Minor)

**File**: `ntx-router.js:84-98`

Title comes from three different sources:
- `@profile` → `"Profile"` (capitalize routine name)
- `"Product/3"` → `"Product"` (split on `/`, take first)
- `{tag, attrs, title}` → object's `title` field

Schema display names, entity names (`value.name`), and `__name__` are all ignored. There's no consistent "what should the page title be" strategy.

### Issue 8: Double-Hop Navigation (Item → List → Router) (Minor)

**Files**: `ntx-item.js:746-755`, `ListElement.js:104-110`

Items send SELECT to their parent list, which forwards as NAVIGATE to the router. This exists because items don't know the router address — only the list does (via `router` attribute).

The double hop is architecturally clean (items shouldn't know about routing) but means:
- Extra TX message per navigation
- `select-target` attribute must be wired on every child (done in `createChild()`)
- If a list has no `router` attribute, clicks are silently swallowed

### Issue 9: Hash Sync is One-Way for Object Routes (Major)

**File**: `Router.js:66-86`

- `#toHash()`: Only serializes strings. Objects are silently dropped.
- `#fromHash()`: Only produces strings. No way to reconstruct object routes.

This means:
- Browser back button works for entity refs but not sidebar model views
- History API `popstate` is never used
- The stack in memory diverges from browser history

### Issue 10: `#showSlot()` Destroys and Recreates Slot

**File**: `ntx-router.js:72-78`

```javascript
#showSlot() {
    if (this.#currentView) {
        this.#currentView.remove();
        this.#currentView = null;
    }
    this.shadowRoot.innerHTML = '<slot></slot>';
}
```

This wipes the shadow DOM and re-creates the slot element. The slotted light DOM children survive (they live in the host), but any state inside the shadow DOM (scroll position, expanded sections) is lost.

---

## Improvement Options

### Option A: Flat Route Strings (Minimal Change)

Standardize ALL routes as hash-serializable strings with conventions:

```
Product         → model list view
Product/3       → entity detail view
@profile        → app-level view
@settings       → app-level view
```

**Changes needed**:
- Sidebar constructs strings instead of objects: `"Product"` not `{tag:'ntx-list', attrs:{model:'Product'}}`
- NTTRouter resolves list component from schema `ui.renderer.list` (new hint) or defaults to `ntx-list`
- All routes now round-trip through hash
- Remove object route branch from `#mountView()`

**What this fixes**: Issues 2, 9 (hash round-trip), partially 7 (title from schema)
**What this doesn't fix**: Issues 1, 3, 5, 6, 8

**Pros**: Very small change surface, backwards compatible
**Cons**: No parameterized routes, no query params, limited expressiveness for apps like veille

### Option B: URI Path Routes (Medium Change)

Adopt a URL-path scheme for all routes:

```
Product                    → list view
Product/3                  → detail view
Product/3/analyze          → method/action view
@profile                   → app view
Source?view=table          → list with presentation override
Grant?sort=deadline        → list with query params
```

**Route parsing**:
```javascript
// Parse: model[/id[/action]][?params]
function parseRoute(route) {
    if (route.startsWith('@')) return { type: 'app', name: route.slice(1) };
    const [path, query] = route.split('?');
    const parts = path.split('/');
    const params = new URLSearchParams(query || '');
    return {
        type: 'entity',
        model: parts[0],
        id: parts[1] || null,
        action: parts[2] || null,
        params: Object.fromEntries(params),
    };
}
```

**Component resolution**:
```javascript
function resolveComponent(parsed, schema) {
    if (parsed.type === 'app') return { tag: `ntx-${parsed.name}`, attrs: {} };
    if (parsed.action) return resolveActionComponent(parsed, schema);  // schema.methods[action]
    if (parsed.id) return { tag: schema.ui?.renderer?.detail || 'ntx-item', attrs: { ref: `${parsed.model}/${parsed.id}` } };
    return { tag: schema.ui?.renderer?.list || 'ntx-list', attrs: { model: parsed.model } };
}
```

**Changes needed**:
- Add `parseRoute()` + `resolveComponent()` to Router or NTTRouter
- Sidebar constructs path strings: `"Source"` with `?view=table` for overrides
- Router serializes/deserializes all routes to hash (everything is a string)
- NTTRouter uses parsed route + schema to resolve component
- Add `ui.renderer.list` schema hint for list-level component selection

**What this fixes**: Issues 1, 2, 3, 7, 9
**What this doesn't fix**: Issues 5, 6, 8 (separate concerns)

**Pros**: Familiar URL semantics, deep-linkable, bookmarkable, solves veille's needs
**Cons**: More parsing complexity, need conventions for query params

### Option C: Declarative Route Config (Large Change)

Add a route definition layer via HTML or schema:

```html
<ntx-router name="main" hash>
    <ntx-route path="Product" component="ntx-list"></ntx-route>
    <ntx-route path="Product/:id" component="ntx-item"></ntx-route>
    <ntx-route path="Product/:id/analyze" component="ntx-analyze"></ntx-route>
    <ntx-route path="@profile" component="ntx-profile"></ntx-route>
    <ntx-route default>
        <ntx-run-panel></ntx-run-panel>
    </ntx-route>
</ntx-router>
```

Or driven by schema:
```python
__ui__ = {
    'routes': {
        'list': {'component': 'ntx-table', 'attrs': {'allow-create': True}},
        'detail': {'component': 'ntx-grant-item'},
        'analyze': {'component': 'ntx-grant-analyze'},
    }
}
```

**What this fixes**: Issues 1, 2, 3, 5 (with keep-alive attr), 6 (with guard attrs), 7, 9
**What this doesn't fix**: Issue 8 (separate concern)

**Pros**: Most flexible, explicit, supports guards/middleware, familiar from frameworks
**Cons**: Largest change, introduces a route config DSL, may conflict with "schema is the source of truth" philosophy

### Option D: URI Routes + Schema Resolution (Recommended)

Hybrid approach. Routes are always URI strings (Option B), but component resolution stays schema-driven (N3TX philosophy). Adds targeted fixes for keep-alive and guards.

**Core principle**: The route is a string that identifies WHAT to show. The SCHEMA determines HOW to show it. No route config needed — the model IS the config.

**Route grammar**:
```
route     = app_route | entity_route
app_route = "@" name                           → @profile, @settings
entity_route = model ["/" id ["/" action]] ["?" params]
model     = ClassName                          → Product, Grant, Source
id        = integer                            → 3, 42
action    = method_name                        → analyze, generate
params    = key "=" value ["&" key "=" value]* → view=table&sort=name
```

**Schema-driven resolution** (extends current `ui.renderer`):
```python
__ui__ = {
    'renderer': {
        'item': 'ntx-grant-item',    # existing — used for sm/xs in lists
        'detail': 'ntx-grant-item',  # existing — used for entity detail view
        'list': 'ntx-table',         # NEW — used for model list view
    },
}
```

**Router changes**:
1. All routes are strings → all survive hash round-trip
2. `parseRoute(string)` extracts structured data
3. NTTRouter resolves component from parsed route + schema `ui.renderer`
4. Query params pass through as attributes (e.g., `?view=table` → `display` attr override)

**NTTRouter changes**:
1. Component resolution via `#resolveComponent(parsedRoute)` instead of shape detection
2. Optional keep-alive: cache last N components, hide instead of destroy
3. Route guard hook: `beforeNavigate(from, to)` → return false to cancel

**Sidebar changes**:
1. Construct URI strings: `"Grant"` not `{tag:'ntx-list', attrs:{model:'Grant'}}`
2. `?view=table` for presentation overrides from templates
3. Item entries: `"Organization/1"` (already a string pattern)

**What this fixes**: All 10 issues
**What it preserves**: Schema as source of truth, TX-based messaging, Actor architecture

**Migration path**:
1. Add `parseRoute()` to Router.js (backwards compatible — strings still work)
2. Update NTTRouter `#mountView()` to use parsed routes + schema resolution
3. Update sidebar to emit URI strings instead of objects
4. Add `ui.renderer.list` to models that want non-default list views
5. (Later) Add keep-alive caching
6. (Later) Add route guards

---

## Recommendation

**Option D (URI Routes + Schema Resolution)** aligns best with N3TX's philosophy:

- **"The model is the app"** — routing stays schema-driven, no separate config
- **"Zero to working, then customize"** — default resolution works with no config; `ui.renderer.list` is additive
- **"Transparent, not magical"** — route strings are readable, parseable, inspectable
- **"Backend is authoritative"** — schema `ui.renderer` controls presentation, frontend adapts

The change is medium-sized but highly targeted. The route grammar is simple (no regex, no path-to-regexp). Schema resolution is an extension of existing `ui.renderer` (not a new concept). And the migration is incremental — current string routes (`"Product/3"`) continue to work unchanged.

---

## Files That Need Changes

| File | Change | Scope |
|------|--------|-------|
| `packages/n3tx-core/src/n3tx_core/static/core/Router.js` | Add `parseRoute()`, ensure all routes serialize to hash | Small |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js` | Replace shape detection with `parseRoute()` + schema resolution, add `ui.renderer.list` support | Medium |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js` | Emit URI strings instead of objects | Small |
| `apps/veille/static/index.html` | Remove manual `handleRoute()`, rely on framework router | Small |
| `apps/veille/models/*.py` | Add `ui.renderer.list` where needed | Tiny |
| `docs/frontend/ROUTING.md` | New doc: route grammar, schema resolution, migration guide | New |
| `tests/frontend/tests/core/Router.test.js` | Add parseRoute tests, update navigation tests | Medium |
| `tests/frontend/tests/components/ntx-router.test.js` | Update for new resolution logic | Medium |

### Files That Stay Unchanged

- `Component.js` — no router-specific changes needed
- `NTTElement.js` — entity lifecycle unaffected
- `ListElement.js` — SELECT handler already sends string data
- `ntx-item.js` — click → SELECT flow unchanged
- `Observable.js` — notification pattern unchanged
- `Actor.js`, `Matrix.js`, `TX.js` — actor system untouched
