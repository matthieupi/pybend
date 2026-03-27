# Frontend Router — Strategic Improvements & Propositions

## Context

This report analyzes the N3TX frontend routing subsystem and proposes concrete improvements grounded in the current codebase. Each proposition includes the current state with file:line references, the problem it addresses, a proposed design, trade-offs, and a migration path.

The prior audit (`.traces/features/improve-routing/audit.md`) identified 10 issues and 4 improvement options. This report builds on that foundation, focusing on what to actually build and in what order.

---

## 1. Mental Model Simplification

### Current Mental Model

A developer working with routing today must hold these concepts simultaneously:

```
┌──────────────────────────────────────────────────────────────────┐
│  CURRENT CONCEPTS (8)                                            │
│                                                                  │
│  Router          — Actor state machine with Observable mixin     │
│  NTTRouter       — View container web component                  │
│  routers Map     — Module-level global registry                  │
│  Route data      — Polymorphic: string | @string | {tag,attrs}   │
│  Hash sync       — Opt-in string-only URL binding                │
│  SELECT          — Item click TX (item → list)                   │
│  NAVIGATE        — Navigation TX (list/sidebar → router)         │
│  BACK            — Back navigation TX (chrome btn → router)      │
│                                                                  │
│  Route shapes:                                                   │
│    "Product/3"           (entity ref, hash-safe)                 │
│    "@profile"            (app route, hash-safe)                  │
│    {tag, attrs, title}   (programmatic, NOT hash-safe)           │
│    "#settings"           (hash redirect, special-cased)          │
└──────────────────────────────────────────────────────────────────┘
```

The critical complexity is **route data polymorphism**. Three shapes flow through the same channel with different serialization rules, different resolution logic in `#mountView()` (ntx-router.js:81-107), and different hash behavior in `#toHash()` (Router.js:66-72).

### Proposed Simpler Model

```
┌──────────────────────────────────────────────────────────────────┐
│  PROPOSED CONCEPTS (6)                                           │
│                                                                  │
│  Router          — Actor state machine (unchanged)               │
│  NTTRouter       — View container web component (unchanged)      │
│  routers Map     — Module-level registry (unchanged)             │
│  Route string    — ALWAYS a string. Grammar:                     │
│                      Model[/id[/action]][?params]                │
│                      @appRoute                                   │
│  SELECT          — Unchanged                                     │
│  NAVIGATE/BACK   — Unchanged, but data is always a string       │
│                                                                  │
│  Resolution:                                                     │
│    String → parseRoute() → {type, model, id, action, params}    │
│    Parsed route + schema ui.renderer → component tag + attrs    │
└──────────────────────────────────────────────────────────────────┘
```

**Eliminated concepts**: Object route data, hash-redirect special case (`#settings`), the "some routes survive refresh, some don't" dichotomy.

**Merged concepts**: Route data shapes collapse into one grammar. The sidebar currently constructs `{tag, attrs, title}` objects (ntx-sidebar.js:282-289) — it would instead construct strings like `"Grant?view=table"`. Hash sync becomes total (all routes round-trip) instead of partial.

### What Breaks During Transition

1. **Sidebar navigation dispatch**: `#navigateToModel()` (ntx-sidebar.js:264-291) currently sends object data. Must change to string construction. Low risk — the method is self-contained.

2. **Object route deduplication**: Router.js:47-48 uses `JSON.stringify()` for object comparison. Becomes unnecessary (strings use `===`). The fragile JSON comparison can be deleted.

3. **Veille's hash-redirect routes**: ntx-router.js:85-89 special-cases `routeData.startsWith('#')`. The veille app uses `#sources`, `#analyze/123`, `#report/456` (veille/index.html:275-303). These must migrate to the new grammar — they become `@sources`, `Source?panel=analyze&id=123`, etc. This is the hardest migration step.

---

## 2. Interface Tightening

### 2.1 Router Constructor Options

**Current interface** (Router.js:29-38):
```javascript
constructor(addr, { hash = false } = {})
```

**Problem**: The `hash` flag is the only option, and it defaults to `false`. But every real usage sets it to `true` — core example (index.html:66), grants example (index.html:73). The only exception is veille (index.html:227), which intentionally avoids hash sync because it runs a parallel manual router.

**Proposed**: Default `hash` to `true`. Apps that want no hash sync explicitly opt out.

```javascript
constructor(addr, { hash = true } = {})
```

**Callers affected**: 0 breakage in examples (all either pass `hash: true` or rely on NTTRouter which reads the `hash` attribute). Veille would need `<ntx-router name="main" no-hash>` instead of omitting `hash`. The NTTRouter's `connectedCallback()` (ntx-router.js:38) passes `hash: this.hasAttribute('hash')` — this would invert to `hash: !this.hasAttribute('no-hash')`.

**Migration**: Change default, update NTTRouter attribute check, update veille HTML. One commit.

### 2.2 NTTRouter Name Generation

**Current interface** (ntx-router.js:35):
```javascript
const name = this.getAttribute('name') || `router-${this.addr}`;
```

The fallback `router-${this.addr}` generates an unpredictable name that no other component can reference. Every real usage sets `name` explicitly: `name="main"` in all three example apps.

**Proposed**: Require `name` attribute. Throw a clear error if missing during `connectedCallback()`:

```javascript
const name = this.getAttribute('name');
if (!name) throw new Error(`<ntx-router> requires a "name" attribute for actor addressing.`);
```

**Callers affected**: None — all existing usage provides `name`. This prevents silent failures where a sidebar's `router="main"` can't find a nameless router.

### 2.3 Route Data — Eliminate Object Shape

**Current interface**: Route data accepts three shapes (Router.js:45-54, ntx-router.js:81-107).

**Proposed**: Route data is always a string. The `NAVIGATE` handler rejects non-strings:

```javascript
NAVIGATE(data, tx) {
    if (typeof data !== 'string') {
        console.warn(`[Router] NAVIGATE data must be a string, got ${typeof data}. Ignoring.`);
        return;
    }
    // ... existing logic, minus JSON.stringify dedup
}
```

**Callers affected**:
- `ntx-sidebar.js`: `#navigateToModel()` (line 264), `#navigateToItem()` (line 293) — must change from object to string construction. See Proposition 4.
- `ListElement.js`: `SELECT()` (line 108) — already sends strings. No change.
- Test files: `Router.test.js` tests for object routes (lines 89-96, 106-110) must be updated.

### 2.4 The `#resolveTag()` Fallback Chain

**Current** (ntx-router.js:148-155):
```javascript
#resolveTag(model) {
    const NTT = window.NTT;
    if (!NTT) return 'ntx-item';
    const DC = NTT.get(model);
    return DC?.schema?.ui?.renderer?.detail
        || DC?.schema?.ui?.renderer?.item
        || 'ntx-item';
}
```

**Problem**: Uses `window.NTT` global instead of importing NTT. This is the only place in the UI package that accesses `window.NTT` directly. Every other component uses `import { NTT } from '../core/NTT.js'`.

**Proposed**: Import NTT properly and extend resolution to support `ui.renderer.list`:

```javascript
#resolveComponent(parsed) {
    const DC = NTT.get(parsed.model);
    const renderer = DC?.schema?.ui?.renderer || {};
    if (parsed.id) {
        // Detail view
        return { tag: renderer.detail || renderer.item || 'ntx-item', attrs: { ref: `${parsed.model}/${parsed.id}` } };
    } else {
        // List view
        return { tag: renderer.list || 'ntx-list', attrs: { model: parsed.model } };
    }
}
```

---

## 3. Composability Improvements

### 3.1 Sidebar-Router Coupling via Dynamic Import

**Current state**: The sidebar (ntx-sidebar.js:282-289, 309-319, 328-335) uses dynamic `import('../core/Matrix.js')` to dispatch TXs because it's not an Actor:

```javascript
import('../core/Matrix.js').then(({ matrix }) => {
    matrix.dispatch({
        name: 'NAVIGATE', source: 'sidebar', target: routerAddr,
        data: { tag, attrs, title: modelName },
    });
});
```

**Problem**: This creates an async gap between user click and navigation. More importantly, the hardcoded `source: 'sidebar'` string means the sidebar can't participate in the actor system for interceptors, logging, or debugging. The sidebar is the only component that calls `matrix.dispatch()` directly.

**Proposed**: Import Matrix statically at module top (it's already loaded before sidebar — see modulepreload order in all index.html files). The sidebar is already importing `NTT` statically (ntx-sidebar.js:40), so there's no circular dependency concern:

```javascript
// Top of ntx-sidebar.js
import { matrix } from '../core/Matrix.js';

// In navigation methods (synchronous now)
#navigateToModel(modelName) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;
    const route = this.#buildRoute(modelName);
    matrix.dispatch({ name: 'NAVIGATE', source: 'sidebar', target: routerAddr, data: route });
    this.close();
}
```

**What this enables**: Synchronous navigation dispatch eliminates the async gap. Combined with string-only routes, the entire navigate-dispatch-render chain becomes synchronous and predictable.

### 3.2 Route Construction is Scattered

**Current state**: Three different components construct route data in three different ways:
- ListElement.SELECT() (ListElement.js:108) sends raw entity refs: `"Product/3"`
- ntx-sidebar.js `#navigateToModel()` (line 264) builds `{tag, attrs, title}` objects
- ntx-sidebar.js `#navigateToLink()` (line 324) sends raw href strings

**Proposed**: Centralize route construction in a `buildRoute()` utility function, co-located with `parseRoute()` in Router.js:

```javascript
// In Router.js — exported utility
export function buildRoute(model, { id, action, params } = {}) {
    let route = model;
    if (id) route += `/${id}`;
    if (action) route += `/${action}`;
    if (params && Object.keys(params).length) {
        route += '?' + new URLSearchParams(params).toString();
    }
    return route;
}
```

Callers become:
```javascript
// Sidebar
import { buildRoute } from '../core/Router.js';
#navigateToModel(modelName) {
    const template = this.#routeTemplates.get(modelName);
    const params = template ? { view: template.tag.replace('ntx-', '') } : {};
    const route = buildRoute(modelName, { params });
    // ... dispatch
}

// ListElement stays the same — it already sends "Product/3" strings
```

### 3.3 Router as Composable Primitive

**Current state**: The Router actor is instantiated by NTTRouter's `connectedCallback()` (ntx-router.js:36-39). Only NTTRouter can create routers because only it knows when to create vs. reuse (via `getRouter()`).

**Problem**: An app that wants routing behavior without the NTTRouter chrome (back button, title bar) — like a tab panel, a wizard, or veille's manual panel switching — can't use the Router actor at all.

**Proposed**: Router creation stays simple and independent. Apps can use the Router actor directly without NTTRouter. This already works architecturally (Router has no DOM dependency), but there's no documentation or example showing this pattern. The fix is documentation + one small API addition:

```javascript
// Router.js — add a static factory that's easier to discover
export function createRouter(addr, opts) {
    const existing = getRouter(addr);
    if (existing) return existing;
    return new Router(addr, opts);
}
```

This makes Router a true composable primitive that any component (not just NTTRouter) can use.

---

## 4. Resilience & Error Recovery

### 4.1 Unknown Custom Element Tag

**Current state** (ntx-router.js:127):
```javascript
const el = document.createElement(tag);
```

If `tag` is an unregistered custom element (e.g., `@unknown` resolves to `ntx-unknown`), `createElement` succeeds but creates an `HTMLElement` that renders nothing. The e2e test (ntx-router-unit.spec.js:210-226) verifies no crash, but the user sees a blank page with a back button.

**Proposed**: Check custom element registration and show a fallback:

```javascript
#mountView(routeData) {
    // ... resolve tag ...

    if (!customElements.get(tag)) {
        console.warn(`[ntx-router] Unknown component <${tag}> for route "${routeData}". Showing fallback.`);
        this.shadowRoot.innerHTML = `
            <div class="router-chrome">
                ${showBack ? '<button class="back-btn" title="Back"></button>' : ''}
                <h1 class="router-title">${title}</h1>
            </div>
            <div class="router-content">
                <div class="router-error">Component &lt;${tag}&gt; is not registered.</div>
            </div>
        `;
        // Still bind back button
        if (showBack) { /* ... */ }
        return;
    }
    // ... existing createElement + mount ...
}
```

### 4.2 Stack Grows Unbounded

**Current state** (Router.js:25-26): `#stack = []` has no size limit. Deep navigation chains (user clicking through many entities) grow the stack indefinitely.

**Impact**: Low for typical usage, but in apps with automated navigation or long sessions, memory grows linearly with navigation count.

**Proposed**: Cap the stack at a reasonable depth (e.g., 50). When exceeded, drop the oldest entries:

```javascript
NAVIGATE(data, tx) {
    // ... dedup check ...
    const old = this.#current;
    this.#stack.push(old);
    if (this.#stack.length > 50) this.#stack.shift();  // Drop oldest
    this.#current = data;
    // ...
}
```

This is a one-line change with zero API impact.

### 4.3 Hash Sync Race with Browser Navigation

**Current state** (Router.js:74-86): `#fromHash()` fires on `hashchange`. But if the Router also calls `#toHash()` during NAVIGATE, the resulting `hashchange` event from the browser re-enters `#fromHash()`, which would double-push to the stack.

The code prevents infinite loops via the `hash !== this.#current` check (line 76), but there's a subtle issue: when BACK pops to null, `#toHash()` calls `history.replaceState()` (line 70), which does NOT fire `hashchange`. But manual hash clearing by the user (typing in URL bar) DOES fire `hashchange`, which clears the internal stack silently (line 82-85) without preserving the history.

**Proposed**: Add a guard flag to prevent re-entrant hash processing:

```javascript
#suppressHash = false;

#toHash() {
    this.#suppressHash = true;
    if (typeof this.#current === 'string') {
        location.hash = this.#current;
    } else if (this.#current === null) {
        history.replaceState(null, '', location.pathname + location.search);
    }
    // Allow next tick for browser to fire hashchange
    requestAnimationFrame(() => { this.#suppressHash = false; });
}

#fromHash() {
    if (this.#suppressHash) return;
    // ... existing logic ...
}
```

### 4.4 NTTRouter Shadow DOM Wipe

**Current state** (ntx-router.js:77):
```javascript
this.shadowRoot.innerHTML = '<slot></slot>';
```

This wipes the entire shadow DOM. If styles were adopted via `adoptedStyleSheets` (Component.js:98), they survive because `adoptedStyleSheets` is a separate property. But if any shadow DOM state existed (scroll position in `.router-content`, animation state), it's lost.

More critically, `#mountView()` (line 111) also does `this.shadowRoot.innerHTML = ...`, which destroys the previous view without any cleanup callback. Components removed this way get their `disconnectedCallback` fired by the DOM, but there's no route-level lifecycle hook for "you're about to be navigated away from."

**Proposed**: Separate the chrome (persistent) from the content (swapped):

```javascript
prerender() {
    // Called once — persistent chrome
    this.shadowRoot.innerHTML = `
        <div class="router-chrome" hidden></div>
        <div class="router-content"><slot></slot></div>
    `;
}

#mountView(routeData) {
    // ... resolve tag, attrs ...
    const chrome = this.shadowRoot.querySelector('.router-chrome');
    const content = this.shadowRoot.querySelector('.router-content');

    // Update chrome
    chrome.hidden = false;
    chrome.innerHTML = `
        ${showBack ? '<button class="back-btn" title="Back"></button>' : ''}
        <h1 class="router-title">${title}</h1>
    `;

    // Swap content
    if (this.#currentView) this.#currentView.remove();
    content.innerHTML = '';  // Clear slot

    const el = document.createElement(tag);
    // ... set attrs ...
    this.#currentView = el;
    content.appendChild(el);
}

#showSlot() {
    const chrome = this.shadowRoot.querySelector('.router-chrome');
    const content = this.shadowRoot.querySelector('.router-content');
    chrome.hidden = true;
    if (this.#currentView) {
        this.#currentView.remove();
        this.#currentView = null;
    }
    // Re-add slot if removed
    if (!content.querySelector('slot')) {
        content.innerHTML = '<slot></slot>';
    }
}
```

This eliminates the full shadow DOM rebuild on every navigation.

---

## 5. Extensibility Without Modification

### 5.1 Route Resolution Registry

**Current state**: Component resolution is hardcoded in `#mountView()` (ntx-router.js:81-107) with three `if` branches for three route shapes. Adding a new route type (e.g., `Grant/3/analyze`) requires modifying this method.

**Proposed**: A resolver registry pattern where route resolution is pluggable:

```javascript
// Router.js — exported, extensible
const _resolvers = [];

export function addRouteResolver(resolver) {
    _resolvers.push(resolver);
}

export function resolveRoute(routeString) {
    // Built-in parsing
    const parsed = parseRoute(routeString);

    // Let custom resolvers override or augment
    for (const resolver of _resolvers) {
        const result = resolver(parsed, routeString);
        if (result) return result;
    }

    // Default resolution
    return defaultResolve(parsed);
}

// Default: schema-driven resolution
function defaultResolve(parsed) {
    if (parsed.type === 'app') {
        return { tag: `ntx-${parsed.name}`, attrs: {} };
    }
    const DC = NTT.get(parsed.model);
    const renderer = DC?.schema?.ui?.renderer || {};
    if (parsed.action) {
        // Action routes: check schema methods for renderer hints
        const methodDef = DC?.schema?.methods?.[parsed.action];
        const tag = methodDef?.ui?.renderer || (methodDef?.stream ? 'ntx-stream' : 'ntx-method');
        return { tag, attrs: { model: parsed.model, uuid: parsed.id, method: parsed.action } };
    }
    if (parsed.id) {
        return { tag: renderer.detail || renderer.item || 'ntx-item', attrs: { ref: `${parsed.model}/${parsed.id}` } };
    }
    return { tag: renderer.list || 'ntx-list', attrs: { model: parsed.model } };
}
```

**Veille migration**: Instead of a manual `handleRoute()` function (veille/index.html:275-303), veille registers a custom resolver:

```javascript
import { addRouteResolver } from './core/Router.js';

addRouteResolver((parsed) => {
    if (parsed.type === 'app' && parsed.name === 'sources') {
        return { tag: 'ntx-table', attrs: { model: 'Source', 'allow-create': '' } };
    }
    if (parsed.action === 'analyze') {
        return { tag: 'ntx-grant-analyze', attrs: { model: 'Grant', uuid: parsed.id, method: 'analyze' } };
    }
    if (parsed.action === 'report') {
        return { tag: 'ntx-run-report', attrs: { 'run-id': parsed.id } };
    }
    return null; // Fall through to default resolution
});
```

### 5.2 Route Guard Protocol

**Current state**: No route guards exist. Navigation always commits immediately (Router.js:45-54). There's no way to prevent navigation (e.g., unsaved changes), redirect, or run async checks.

**Proposed**: A `beforeNavigate` hook on NTTRouter using the same Observable pattern:

```javascript
// NTTRouter — add guard support
#guards = [];

guard(fn) {
    this.#guards.push(fn);
    return () => { this.#guards = this.#guards.filter(g => g !== fn); };
}

async #canNavigate(from, to) {
    for (const guard of this.#guards) {
        const result = await guard(from, to);
        if (result === false) return false;
        if (typeof result === 'string') {
            // Redirect
            this.#router.NAVIGATE(result);
            return false;
        }
    }
    return true;
}
```

Usage:
```javascript
// Unsaved changes guard
const router = document.querySelector('ntx-router');
router.guard((from, to) => {
    if (hasUnsavedChanges()) {
        return confirm('Discard unsaved changes?');
    }
    return true;
});

// Auth guard
router.guard(async (from, to) => {
    if (to.startsWith('@admin') && !isAdmin()) {
        return '@login'; // redirect
    }
    return true;
});
```

Guards live on NTTRouter (not Router) because they are a view-layer concern. Router stays pure state. This respects the existing separation.

---

## 6. Convention Over Configuration

### 6.1 Schema `ui.renderer.list` Default

**Current state**: When the sidebar navigates to a model list, it constructs an object route with the specific tag from the template child or a `view` attribute default (ntx-sidebar.js:274-278). But NTTRouter's `#resolveTag()` (ntx-router.js:148-155) only handles `detail` and `item` renderers — there's no `list` renderer in the schema.

**Problem**: If a model wants `ntx-table` as its list view, every consumer must know this and specify it. The schema doesn't carry this information.

**Proposed**: Add `ui.renderer.list` to the schema convention:

```python
# In model definition
__ui__ = {
    'renderer': {
        'item': 'ntx-grant-item',   # existing
        'detail': 'ntx-grant-item', # existing
        'list': 'ntx-table',        # NEW
    },
}
```

Default (when not specified): `'ntx-list'`. This is already the implicit default in multiple places.

The resolution chain becomes:
```
list view:    schema.ui.renderer.list → 'ntx-list'
detail view:  schema.ui.renderer.detail → schema.ui.renderer.item → 'ntx-item'
```

### 6.2 `display` Mode for Routed Views

**Current state** (ntx-router.js:136-138):
```javascript
if (attrs.ref && !el.hasAttribute('display')) {
    el.setAttribute('display', 'lg');
}
```

Only entity detail views (those with `ref`) get forced to `lg` display. List views routed via sidebar get no display hint — they default to `auto` and use ResizeObserver.

**Problem**: Inconsistent. A list routed to the main content area should get `lg` or `xl` display, matching the available space. Instead, it starts at `md` until ResizeObserver fires.

**Proposed**: All routed views get `display` set based on their context:

```javascript
// Default display for routed views (not forced — ResizeObserver can override)
if (!el.hasAttribute('display')) {
    el.setAttribute('display', attrs.ref ? 'lg' : 'xl');
}
```

### 6.3 Title Resolution from Schema

**Current state** (ntx-router.js:93-104): Title resolution is ad hoc — `@profile` becomes `"Profile"`, `"Product/3"` becomes `"Product"`, objects carry their own `title`.

**Proposed**: Use schema `__name__` for entity routes, and check for `schema.title` (a standard JSON Schema field) for richer display names:

```javascript
#resolveTitle(parsed) {
    if (parsed.type === 'app') {
        return parsed.name.charAt(0).toUpperCase() + parsed.name.slice(1);
    }
    const DC = NTT.get(parsed.model);
    const schemaTitle = DC?.schema?.title || DC?.schema?.__name__ || parsed.model;
    if (parsed.id) {
        // Could enhance: fetch entity name for "Product: Widget X" title
        return schemaTitle;
    }
    return schemaTitle + 's'; // Pluralize for list views
}
```

---

## 7. Consistency Gaps

### 7.1 Sidebar Is Not an Actor

**Current state** (ntx-sidebar.js:61):
```javascript
class NTTSidebar extends HTMLElement { ... }
```

Every other interactive component extends `Component` (which extends `HTMLElement` and mixes in Actor). The sidebar is the sole exception. It can't receive TX messages, can't participate in interceptors, and uses `matrix.dispatch()` directly instead of `this.send()`.

**Evidence**: Compare with NTTRouter (ntx-router.js:19) which extends `Component`. The sidebar sends TXs via `matrix.dispatch()` (ntx-sidebar.js:283) while every other component uses `this.send()` (e.g., ListElement.js:108, ntx-item.js:751).

**Proposed**: The sidebar should extend `Component`. The main concern is that Component's constructor expects a `defaultValue` parameter and sets up schema/model lifecycle machinery that the sidebar doesn't need. But this is fine — Component's constructor defaults to `{}` (Component.js:70), and the sidebar simply never calls `define()` or `attach()`.

Migration sketch:
```javascript
// Before
class NTTSidebar extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        // ...
    }
}

// After
class NTTSidebar extends Component {
    constructor() {
        super({});  // Component handles shadow DOM
        // ... (remove manual attachShadow)
    }

    // Navigation now uses this.send() instead of matrix.dispatch()
    #navigateToModel(modelName) {
        const routerAddr = this.getAttribute('router');
        if (!routerAddr) return;
        const route = buildRoute(modelName);
        this.send(new TX({ name: 'NAVIGATE', source: this.addr, target: routerAddr, data: route }));
        this.close();
    }
}
```

**Trade-offs**: The sidebar gains an actor address, children map, ResizeObserver, and other Component machinery it doesn't strictly need. The memory overhead is negligible (a few properties per instance — there's only one sidebar). The benefit is full actor system participation.

### 7.2 Hash Route Special Case in #mountView

**Current state** (ntx-router.js:85-89):
```javascript
if (typeof routeData === 'string' && routeData.startsWith('#')) {
    window.location.hash = routeData.slice(1);
    this.#showSlot();
    return;
}
```

This is the only place where NTTRouter directly manipulates `window.location.hash`. It's a bypass mechanism for hash-based routing that doesn't go through the Router actor at all.

**Problem**: Violates the "Router is the single source of navigation truth" principle. If a sidebar link dispatches `#sources` as route data, NTTRouter silently redirects to a hash change, which may or may not trigger Router's `#fromHash()`, creating a race condition.

**Proposed**: Eliminate this special case. Hash links from the sidebar should either:
1. Be app routes: `@sources` instead of `#sources`
2. Or be entity routes: `Source` (which resolves to a list view)

The sidebar's `#navigateToLink()` (ntx-sidebar.js:324-336) would construct proper route strings instead of raw hrefs.

### 7.3 Observer Callback Signature Inconsistency

**Current state**: Router notifies with `notify('route', newRoute, oldRoute)` (Router.js:53). Observable's `notify()` calls callbacks with `(newValue, oldValue, property, source)` (Observable.js:126). But NTTRouter observes with `router.observe('route', () => this.render())` (ntx-router.js:43) — ignoring all arguments.

**Problem**: The observation callback discards all context. When NTTRouter calls `this.render()`, render reads `this.#router?.current` (ntx-router.js:63), duplicating the information that was already passed in the callback. This works but is wasteful — the Observable pattern exists precisely to deliver the new value.

**Proposed**: Use the callback arguments:

```javascript
// Current
this.#routerUnsub = router.observe('route', () => this.render());

// Proposed
this.#routerUnsub = router.observe('route', (route) => this.#onRouteChange(route));

#onRouteChange(route) {
    if (route) {
        this.#mountView(route);
    } else {
        this.#showSlot();
    }
}
```

This removes the need for `render()` to re-read `this.#router?.current`, making the data flow explicit.

---

## 8. Propositions Summary Table

| # | Proposition | Simplifies | Impact | Effort | Risk | Dependencies |
|---|-------------|------------|--------|--------|------|--------------|
| P1 | **String-only route data** | Eliminates object routes, unifies hash sync | High | Low | Low | Enables P2, P4, P5 |
| P2 | **`parseRoute()` + `buildRoute()` utilities** | Centralized route grammar | High | Low | Low | Requires P1 |
| P3 | **Schema `ui.renderer.list`** | Convention-driven list resolution | Med | Low | None | Independent |
| P4 | **Schema-driven `resolveRoute()`** | Replaces shape-detection branching | High | Med | Low | Requires P1, P2 |
| P5 | **Sidebar emits route strings** | Eliminates object construction, enables hash round-trip | High | Low | Low | Requires P1, P2 |
| P6 | **Sidebar extends Component** | Consistency with all other components | Med | Med | Low | Independent |
| P7 | **Persistent chrome in NTTRouter** | Eliminates full shadow DOM rebuild | Med | Low | Low | Independent |
| P8 | **Route resolver registry** | Extensibility for app-specific routes | High | Med | Low | Requires P2 |
| P9 | **Route guards** | Unsaved-changes, auth redirects | Med | Med | Med | Requires P4 |
| P10 | **Stack depth cap** | Prevents unbounded memory growth | Low | Trivial | None | Independent |
| P11 | **Hash sync race guard** | Prevents re-entrant stack corruption | Low | Low | None | Independent |
| P12 | **Unknown element fallback** | User-visible error instead of blank page | Med | Low | None | Independent |
| P13 | **Default `hash: true`** | Convention over configuration | Low | Trivial | Low | Independent |
| P14 | **Title from schema** | Consistent, richer page titles | Low | Low | None | Requires P2 |
| P15 | **Eliminate hash-redirect special case** | Remove bypass mechanism | Low | Low | Low | Requires P1 |

### Priority Ranking (Impact/Effort Ratio)

**Tier 1 — High impact, low effort (do first):**
1. **P1** — String-only routes. The foundation everything else builds on.
2. **P2** — `parseRoute()` / `buildRoute()`. Small utility, huge leverage.
3. **P5** — Sidebar string routes. Direct consequence of P1+P2.
4. **P10** — Stack cap. One line, zero risk.
5. **P12** — Unknown element fallback. Small resilience win.

**Tier 2 — High impact, medium effort (do next):**
6. **P4** — Schema-driven resolution. The big payoff from P1+P2.
7. **P3** — `ui.renderer.list`. Backend convention, frontend reads it.
8. **P8** — Route resolver registry. Enables veille migration.
9. **P7** — Persistent chrome. Performance improvement.

**Tier 3 — Medium impact, medium effort (invest when ready):**
10. **P6** — Sidebar as Component. Consistency improvement.
11. **P9** — Route guards. Feature addition.
12. **P11** — Hash sync guard. Defensive fix.

**Tier 4 — Low impact, clean up at leisure:**
13. **P13** — Default hash:true.
14. **P14** — Schema-driven titles.
15. **P15** — Remove hash-redirect.

### Dependency Graph

```
Independent:  P3, P6, P7, P10, P11, P12, P13

P1 (string-only routes)
 ├── P2 (parseRoute + buildRoute)
 │    ├── P4 (schema-driven resolution)
 │    │    └── P9 (route guards)
 │    ├── P5 (sidebar string routes)
 │    ├── P8 (resolver registry)
 │    └── P14 (title from schema)
 └── P15 (eliminate hash-redirect)
```

---

## Detailed Designs for Tier 1 Propositions

### P1 + P2: String Routes with Parse/Build Utilities

**Current Router.js additions** (in `packages/n3tx-core/src/n3tx_core/static/core/Router.js`):

```javascript
/**
 * Parse a route string into structured data.
 * Grammar: @appName | Model[/id[/action]][?params]
 */
export function parseRoute(route) {
    if (!route || typeof route !== 'string') return null;
    if (route.startsWith('@')) {
        return { type: 'app', name: route.slice(1) };
    }
    const [path, query] = route.split('?');
    const parts = path.split('/');
    return {
        type: 'entity',
        model: parts[0],
        id: parts[1] || null,
        action: parts[2] || null,
        params: query ? Object.fromEntries(new URLSearchParams(query)) : {},
    };
}

/**
 * Build a route string from structured components.
 */
export function buildRoute(model, { id, action, params } = {}) {
    let route = model;
    if (id) route += `/${id}`;
    if (action) route += `/${action}`;
    if (params && Object.keys(params).length) {
        route += '?' + new URLSearchParams(params).toString();
    }
    return route;
}
```

**Changes to NAVIGATE handler** (Router.js:45-54):

```javascript
NAVIGATE(data, tx) {
    if (typeof data !== 'string') {
        // Backward compat: stringify object routes during migration
        if (typeof data === 'object' && data.tag) {
            console.warn('[Router] Object route data is deprecated. Use string routes.');
            // Best-effort: extract model from attrs
            const model = data.attrs?.model;
            if (model) data = model;
            else return;
        } else {
            return;
        }
    }
    if (data === this.#current) return;
    const old = this.#current;
    this.#stack.push(old);
    this.#current = data;
    if (this.#hashSync) this.#toHash();
    this.notify('route', this.#current, old);
}
```

The backward compat path means existing sidebar code continues to work during migration, with a deprecation warning.

### P5: Sidebar String Route Emission

**Changes to ntx-sidebar.js:**

```javascript
import { buildRoute } from '../core/Router.js';
import { matrix } from '../core/Matrix.js';

// Replace #navigateToModel (lines 264-291)
#navigateToModel(modelName) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    const template = this.#routeTemplates.get(modelName);
    const params = {};
    if (template) {
        // Carry presentation overrides as query params
        if (template.tag !== 'ntx-list') {
            params.view = template.tag.replace('ntx-', '');
        }
        // Forward template attrs (e.g., allow-create) as params
        for (const [k, v] of Object.entries(template.attrs)) {
            params[k] = v || 'true';
        }
    }

    const route = buildRoute(modelName, { params });
    matrix.dispatch({ name: 'NAVIGATE', source: 'sidebar', target: routerAddr, data: route });
    this.close();
}

// Replace #navigateToItem (lines 293-322)
#navigateToItem(modelName) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    const itemRef = this.#itemRefs[modelName];
    if (!itemRef) {
        this.#navigateToModel(modelName);
        return;
    }
    // itemRef is already "Organization/1" — a valid route string
    matrix.dispatch({ name: 'NAVIGATE', source: 'sidebar', target: routerAddr, data: itemRef });
    this.close();
}

// Replace #navigateToLink (lines 324-337)
#navigateToLink(href) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    // Convert hash links to app routes
    const route = href.startsWith('#') ? `@${href.slice(1)}` : href;
    matrix.dispatch({ name: 'NAVIGATE', source: 'sidebar', target: routerAddr, data: route });
    this.close();
}
```

### P10: Stack Depth Cap

**One-line change** in Router.js NAVIGATE handler:

```javascript
NAVIGATE(data, tx) {
    if (data === this.#current) return;
    const old = this.#current;
    this.#stack.push(old);
    if (this.#stack.length > 50) this.#stack.shift();  // ADD THIS LINE
    this.#current = data;
    if (this.#hashSync) this.#toHash();
    this.notify('route', this.#current, old);
}
```

---

## Migration Path: From Current to Target

### Phase 1: Foundation (P1 + P2 + P10 + P12)

**Scope**: Router.js only. No breaking changes.

1. Add `parseRoute()` and `buildRoute()` exports to Router.js
2. Add stack depth cap (one line)
3. Add backward-compat deprecation warning for object routes in NAVIGATE
4. Add unknown element fallback in NTTRouter
5. Update Router.test.js and router-navigation.test.js with parseRoute tests

**Risk**: Zero. Additive only. All existing code continues to work.

### Phase 2: Sidebar Migration (P5 + P15)

**Scope**: ntx-sidebar.js, all index.html files.

1. Change sidebar to emit string routes via `buildRoute()`
2. Switch sidebar to static Matrix import
3. Remove hash-redirect special case from NTTRouter
4. Update sidebar links from `#hash` to `@appRoute` format
5. Update ntx-sidebar.test.js

**Risk**: Low. Sidebar is the only producer of object routes. After this phase, all routes are strings.

### Phase 3: Schema Resolution (P3 + P4 + P14)

**Scope**: ntx-router.js, backend model definitions.

1. Add `ui.renderer.list` convention to schema pipeline
2. Replace `#mountView()` shape detection with `resolveRoute()` + schema lookup
3. Add schema-driven title resolution
4. Update veille models with `ui.renderer` entries
5. Remove veille's manual `handleRoute()` function
6. Update ntx-router.test.js and e2e tests

**Risk**: Medium. This changes how views are resolved. Must verify all existing routes still work.

### Phase 4: Refinement (P6 + P7 + P8 + P9)

**Scope**: ntx-sidebar.js, ntx-router.js.

1. Sidebar extends Component
2. Persistent chrome in NTTRouter
3. Route resolver registry
4. Route guard support

**Risk**: Medium. These are structural changes that improve the system but require careful testing.

---

## Veille Migration: Concrete Plan

The veille app (apps/veille/static/index.html) is the hardest migration because it has a parallel routing system (lines 275-303). Here's the specific migration:

**Current manual routes and their new equivalents:**

| Current | New Route String | Resolved Component |
|---------|-----------------|-------------------|
| `#sources` | `@sources` or `Source` | `ntx-table` (via `ui.renderer.list`) |
| `#analyze/123` | `Grant/123/analyze` | `ntx-grant-analyze` (via method resolver) |
| `#report/456` | `Run/456/report` | `ntx-run-report` (via resolver registry) |
| (default) | (no hash = slot content) | `ntx-run-panel` (slot default) |

After migration, the 30-line `handleRoute()` function and its `hashchange` listener are deleted. The veille app registers a custom resolver (P8) for `report` routes, and everything else works through schema conventions.

---

## Summary

The routing subsystem is architecturally sound but operationally inconsistent. The core split (Router as state, NTTRouter as view) follows N3TX's primitive-not-opinions philosophy well. The main problems are:

1. **Route data polymorphism** creates a "some routes work, some don't" experience (hash sync, dedup, serialization all behave differently by shape)
2. **Missing conventions** (`ui.renderer.list`) force apps to bypass the framework
3. **Sidebar inconsistency** (not an Actor, dynamic imports, object routes) creates a friction point between the navigation producer and consumer

The fix is straightforward: standardize on string routes, add `parseRoute()`/`buildRoute()` utilities, extend schema conventions, and provide extensibility hooks. The migration is incremental and backward-compatible at each phase. Total estimate: ~400 lines changed across 6 files, spread over 4 phases that can be shipped independently.
