# Frontend Router Audit: Extensibility & Integration

**Subsystem**: Router (n3tx-core) + NTTRouter (n3tx-ui) + ntx-sidebar (n3tx-ui)
**Date**: 2026-03-25
**Scope**: Extension points, integration boundaries, dependency graph, data contracts, change analysis, limitations, and evolution trajectory.

---

## 1. Extension Points

The routing subsystem provides several mechanisms for adding functionality without modifying existing code. Each is listed below with its mechanism, difficulty, and a concrete example.

### 1.1 Route Data Polymorphism (Config, Easy)

**Mechanism**: The route data channel accepts three shapes — string entity refs, `@`-prefixed app routes, and `{tag, attrs, title}` objects. Any new route type can be expressed as one of these without changing Router or NTTRouter code.

**Difficulty**: Easy (under 10 minutes).

**Example**: Adding a `@settings` page requires only:
1. Create `<ntx-settings>` web component.
2. Navigate via hash: `location.hash = '@settings'`.
3. NTTRouter resolves `@settings` to `<ntx-settings>` automatically (ntx-router.js:91-95).

**Limitations**: String routes cannot carry complex parameters (no query string parsing). Object routes don't survive hash round-trips (Router.js:66-70 — only strings are serialized to `location.hash`).

### 1.2 Schema `ui.renderer` Overrides (Config, Easy)

**Mechanism**: NTTRouter resolves the component tag for entity routes via `#resolveTag(model)` (ntx-router.js:148-155), which reads `DC.schema.ui.renderer.detail` then `DC.schema.ui.renderer.item`. A backend model can control which frontend component renders its detail view by setting `__ui__['renderer']['detail']`.

**Difficulty**: Easy (backend-only change, no frontend code).

**Example**: Override the default `ntx-item` for Grant detail views:
```python
class Grant(ProtoModel):
    __ui__ = {'renderer': {'detail': 'ntx-grant-item', 'item': 'ntx-grant-item'}}
```
NTTRouter will create `<ntx-grant-item ref="Grant/3">` instead of `<ntx-item ref="Grant/3">`.

**Gap**: There is no `ui.renderer.list` hint. NTTRouter's `#resolveTag()` only handles single-entity routes. Model-level list views (e.g., navigating to "all Grants") bypass `#resolveTag()` entirely — the sidebar sends the tag directly as an object route. This means list component selection cannot be schema-driven today.

### 1.3 Sidebar Route Templates (Config, Easy)

**Mechanism**: ntx-sidebar reads child elements as declarative route templates (ntx-sidebar.js:88-111). Children with `model` attributes define what component and attributes to use when navigating to that model.

**Difficulty**: Easy (HTML-only change).

**Example**: Switch Grant list from grid to table view:
```html
<ntx-sidebar router="main">
    <ntx-table model="Grant" allow-create></ntx-table>
</ntx-sidebar>
```
The sidebar extracts `{tag: 'ntx-table', attrs: {'allow-create': ''}}` and dispatches it as route data on model name click (ntx-sidebar.js:267-278).

Three entry types are supported:
| Entry type | Child element | Navigation behavior |
|-----------|--------------|-------------------|
| `model` | `<ntx-list model="X">`, `<ntx-table model="X">` | Navigates to list/table view |
| `item` | `<ntx-item model="X">` | Navigates to singleton detail |
| `link` | `<a href="#hash">Label</a>` | Dispatches raw string route |

### 1.4 Custom Component Subclassing (Subclass, Moderate)

**Mechanism**: NTTRouter extends Component. Custom routers can extend NTTRouter and override `render()` or `#mountView()` (the latter is private, so override requires full replacement). Similarly, new navigation producers can extend ListElement and override `SELECT()` to change navigation behavior.

**Difficulty**: Moderate. NTTRouter uses private fields (`#router`, `#currentView`, `#routerUnsub`) which cannot be accessed from subclasses. A subclass would need to override `render()` entirely rather than hooking into specific steps.

**Example**: A tabbed router that shows multiple views simultaneously:
```javascript
class NTTTabbedRouter extends NTTRouter {
    render() {
        // Custom render that maintains tab state
        // Cannot access #router (private) — must re-implement
    }
}
```

**Assessment**: The heavy use of private fields makes subclassing impractical for anything beyond cosmetic changes. This is a deliberate design choice (encapsulation) but limits composability.

### 1.5 Observable `route` Property (Hook, Easy)

**Mechanism**: Router extends Actor + Observable mixin. Any code with a reference to a Router instance can `observe('route', callback)` to react to navigation changes (Observable.js:78-108). The callback receives `(newValue, oldValue, 'route', routerInstance)`.

**Difficulty**: Easy.

**Example**: Analytics tracking:
```javascript
const router = getRouter('main');
router.observe('route', (newRoute, oldRoute) => {
    analytics.track('navigation', { from: oldRoute, to: newRoute });
});
```

**Note**: This is observation only — there is no way to intercept or cancel navigation from an observer callback. The notification fires after the state has already changed (Router.js:49-53 — state is mutated before `notify()`).

### 1.6 TX Message Interception (Hook, Hard)

**Mechanism**: The Actor system supports interceptors via `use()`, and Router is a full Actor registered in the Matrix. In theory, a NAVIGATE TX could be intercepted before it reaches the Router's handler.

**Difficulty**: Hard. The Actor interceptor mechanism exists on the backend (Python) side and is referenced in `packages/n3tx-actors/docs/`, but the frontend Actor.js (Actor.js:1-337) does not implement `use()` or any interceptor chain. TX messages are dispatched directly to handlers via `_inbox()` (Actor.js:126-148). Adding frontend interceptors would require modifying Actor.js — a core foundation class.

**Current workaround**: None that doesn't involve modifying Router.js. This is the biggest extensibility gap.

### 1.7 Router Global Registry (Plugin, Easy)

**Mechanism**: The module-level `routers` Map and `getRouter(addr)` export (Router.js:21, 89-91) allow any code to retrieve a Router by address. This enables decentralized navigation — any component can look up a router and dispatch TX messages to it.

**Difficulty**: Easy.

**Example**: A floating action button that navigates to a create view:
```javascript
import { getRouter } from './core/Router.js';
import TX from './core/TX.js';

const router = getRouter('main');
router.inbox(new TX({ name: 'NAVIGATE', data: '@create-wizard', target: router.addr }));
```

---

## 2. Integration Boundaries

### 2.1 Router <-> NTTRouter (State -> View)

| Aspect | Detail |
|--------|--------|
| **What crosses** | Route data (string or object) via Observable `notify('route', new, old)` |
| **Protocol** | Observable pattern — NTTRouter subscribes via `router.observe('route', callback)` (ntx-router.js:43) |
| **Coupling** | Moderate. NTTRouter creates the Router instance and holds a direct reference (`#router`). It also imports `Router` and `getRouter` from n3tx-core. |
| **Stability** | Stable. The Observable contract (`observe`/`notify`) is simple and well-defined. |
| **Data format** | Polymorphic: `string | {tag: string, attrs: object, title: string} | null`. Implicit contract — no TypeScript interface, no validation. |

NTTRouter is the sole consumer of Router state in production. The binding is created in `connectedCallback()` (ntx-router.js:37-43) and cleaned up in `disconnectedCallback()` via the unsubscribe function (ntx-router.js:57).

### 2.2 Navigation Producers <-> Router (TX Messaging)

| Aspect | Detail |
|--------|--------|
| **What crosses** | TX messages with `name: 'NAVIGATE'` or `name: 'BACK'`, targeting the Router's actor address |
| **Protocol** | TX-based Actor messaging through the Matrix |
| **Coupling** | Loose. Producers only need to know the Router's address string (obtained from `router` HTML attribute). No import of Router class required. |
| **Stability** | Stable. TX names (`NAVIGATE`, `BACK`) are the only API contract. |

**Producers identified in codebase:**

| Producer | File | How it sends | Source addr |
|----------|------|-------------|-------------|
| ListElement | ListElement.js:108 | `this.send(new TX({...}))` — via Actor system | Component's `this.addr` |
| ntx-sidebar | ntx-sidebar.js:282-289 | `matrix.dispatch({...})` — direct Matrix call | Hardcoded `'sidebar'` |
| NTTRouter (back btn) | ntx-router.js:122 | `this.send(new TX({...}))` — via Actor system | Component's `this.addr` |

The sidebar's use of `matrix.dispatch()` with a hardcoded source `'sidebar'` is the only boundary violation. All other producers use the standard Actor `send()` path.

### 2.3 NTTRouter <-> NTT Registry (Schema Resolution)

| Aspect | Detail |
|--------|--------|
| **What crosses** | Model name string in, DynamicClass (with `schema.ui.renderer`) out |
| **Protocol** | Direct function call: `window.NTT.get(model)` (ntx-router.js:150-151) |
| **Coupling** | Moderate. NTTRouter accesses `window.NTT` global and reads `DC.schema.ui.renderer.detail` and `DC.schema.ui.renderer.item`. |
| **Stability** | Fragile. Relies on `window.NTT` being populated before navigation occurs. If schema hasn't loaded yet, falls back to `'ntx-item'` (ntx-router.js:154). |

### 2.4 NTTRouter <-> Component Base Class

| Aspect | Detail |
|--------|--------|
| **What crosses** | Lifecycle methods (`connectedCallback`, `disconnectedCallback`, `render`), Actor identity (`addr`, `send`), shadow DOM |
| **Protocol** | Class inheritance: `NTTRouter extends Component` |
| **Coupling** | Tight. NTTRouter inherits all of Component's machinery (Actor registration, stylesheet loading, ResizeObserver, display modes). |
| **Stability** | Stable but heavy. Component provides 450+ lines of infrastructure. NTTRouter uses only: shadow DOM, `send()`, `connectedCallback`/`disconnectedCallback`, `styles` getter, and `render()`. It does not use: display modes, schema/proto/value, ref resolution, or attach. |

Component's constructor calls `matrix.register(this)` (Component.js:79) and `this.constructor.register(this)` (Component.js:80), which means every NTTRouter instance is registered as an Actor in the Matrix. This is necessary for the back button's `this.send()` to work, but represents overhead for what is primarily a view container.

### 2.5 ntx-sidebar <-> NTT System (Schema Bootstrap)

| Aspect | Detail |
|--------|--------|
| **What crosses** | Model names in, DynamicClass instances out, via `NTT.attach(modelName, callback)` |
| **Protocol** | `NTT.attach()` API (ntx-sidebar.js:177) — registers a callback that fires when the DynamicClass prototype is ready |
| **Coupling** | Moderate. Sidebar imports `NTT` from core and calls `attach()`, `observe('UPDATE')`. Also reads `DC._paginationMeta`, `DC._schema`, `DC.instances`, `DC.href` — all internal/semi-private properties. |
| **Stability** | Fragile for internal properties. `_paginationMeta`, `_schema` prefix conventions suggest these are not public API, but the sidebar depends on them for counts and display names. |

### 2.6 Router <-> Browser History API

| Aspect | Detail |
|--------|--------|
| **What crosses** | Hash strings via `location.hash` reads/writes; `hashchange` events |
| **Protocol** | DOM API: `window.addEventListener('hashchange', ...)`, `location.hash = ...`, `history.replaceState(...)` |
| **Coupling** | Moderate. Router writes `location.hash` for string routes (Router.js:67-68), reads it in `#fromHash()` (Router.js:74-86), and uses `history.replaceState` to clear the hash on null routes (Router.js:70). |
| **Stability** | Problematic. Two systems can fight over the hash: Router's `hashchange` listener and any app-level hash routing (as seen in veille's `handleRoute()` at apps/veille/static/index.html:275-304). No coordination mechanism exists. |

### 2.7 ntx-sidebar <-> Document Events

| Aspect | Detail |
|--------|--------|
| **What crosses** | Custom events (`sidebar-toggle`) and keyboard events (`Escape`) |
| **Protocol** | `document.addEventListener('sidebar-toggle', ...)` (ntx-sidebar.js:134), `document.addEventListener('keydown', ...)` (ntx-sidebar.js:138), `window.addEventListener('hashchange', ...)` (ntx-sidebar.js:144) |
| **Coupling** | Loose. Standard DOM event pattern. |
| **Stability** | Stable. The `sidebar-toggle` custom event is dispatched by ntx-topbar's hamburger button. |

---

## 3. Dependency Graph

```
                         ┌─────────────────────────────┐
                         │     Browser APIs             │
                         │  location.hash               │
                         │  hashchange event             │
                         │  history.replaceState         │
                         │  customElements.define        │
                         └──────────┬──────────────────┘
                                    │
    ┌───────────────────────────────┼───────────────────────────────┐
    │                    n3tx-core  │                               │
    │  ┌─────────┐    ┌─────────┐  │  ┌──────────┐  ┌──────────┐  │
    │  │ Actor.js │◄───│ Matrix.js│  │  │Observable│  │  TX.js   │  │
    │  └────┬────┘    └────┬────┘  │  └─────┬────┘  └────┬─────┘  │
    │       │              │       │        │             │         │
    │       │    ┌─────────┴──┐    │        │             │         │
    │       └───►│ Router.js  │◄───┼────────┘             │         │
    │            └─────┬──────┘    │                      │         │
    │                  │           │  ┌───────────┐       │         │
    │                  │           │  │Component.js│◄──────┘         │
    │                  │           │  └─────┬─────┘                 │
    │                  │           │        │ ┌────────┐            │
    │                  │           │        │ │ NTT.js │            │
    │                  │           │        │ └───┬────┘            │
    └──────────────────┼───────────┼────────┼─────┼────────────────┘
                       │           │        │     │
    ┌──────────────────┼───────────┼────────┼─────┼────────────────┐
    │                  │  n3tx-ui  │        │     │                 │
    │            ┌─────▼──────┐   │  ┌─────▼─────▼──┐             │
    │            │ntx-router.js│  │  │ ListElement.js│             │
    │            │ (NTTRouter)  │  │  └──────┬───────┘             │
    │            └──────────────┘  │         │                     │
    │                              │  ┌──────▼─────┐              │
    │  ┌──────────────┐           │  │ ntx-item.js │              │
    │  │ntx-sidebar.js│           │  │ ntx-row.js  │              │
    │  │ (NTTSidebar)  │           │  └─────────────┘              │
    │  └──────────────┘           │                                │
    └──────────────────────────────┴────────────────────────────────┘

Arrows show "depends on" / "imports from".
```

### Inbound Dependencies (what this subsystem depends on)

| Dependency | Imported by | Purpose |
|-----------|------------|---------|
| `Actor.js` | Router.js | Base class — Actor identity, `send()`, `inbox()`, `register()` |
| `Observable.js` | Router.js (via `Actor.subclass(Router, Observable)`) | `observe()`/`notify()` pattern for route changes |
| `Matrix.js` | Router.js (constructor calls `matrix.register(this)`), ntx-sidebar.js (dynamic import for `dispatch`) | Actor registration, message bus |
| `TX.js` | ntx-router.js (back button TX), ntx-sidebar.js (NAVIGATE dispatch), ListElement.js (NAVIGATE forwarding) | Message envelope |
| `Component.js` | ntx-router.js | Base class for NTTRouter — shadow DOM, Actor bridge, stylesheets |
| `NTT.js` | ntx-router.js (`window.NTT.get()` for schema), ntx-sidebar.js (`NTT.attach()` for bootstrap) | Entity registry, schema access |
| `window.location` | Router.js | Hash read/write |
| `window.addEventListener` | Router.js, ntx-sidebar.js | `hashchange`, `sidebar-toggle`, `keydown` |

### Outbound Dependencies (what depends on this subsystem)

| Dependent | How it uses Router | Coupling |
|----------|-------------------|---------|
| ListElement.js | Reads `router` attribute, sends NAVIGATE TX to router address | Attribute-based (loose) |
| ntx-item.js | Sends SELECT to `select-target` (which ListElement forwards to router) | Indirect (via ListElement) |
| ntx-row.js | Same SELECT pattern as ntx-item.js | Indirect (via ListElement) |
| ntx-sidebar.js | Reads `router` attribute, dispatches NAVIGATE to router address | Attribute-based (loose) |
| apps/veille/static/index.html | Competes with Router for `hashchange` events | Conflicting |
| examples/core/static/index.html | Declares `<ntx-router name="main" hash>` | Declarative (loose) |
| examples/grants/static/index.html | Declares `<ntx-router name="main" hash>` | Declarative (loose) |

---

## 4. Data Contracts at Boundaries

### 4.1 Route Data Contract (Implicit)

The central data contract is the shape of route data flowing through the system. It is entirely implicit — no schema, no TypeScript interface, no validation.

```
RouteData = string                          // Entity ref: "Product/3"
          | string starting with "@"        // App route: "@profile"
          | string starting with "#"        // Hash redirect (ntx-router.js:85-89)
          | { tag: string,                  // Programmatic route
              attrs?: Record<string, any>,
              title?: string }
          | null                            // No route (home/slot view)
```

**Where this contract is consumed:**

| Consumer | File:Line | How it interprets route data |
|----------|-----------|---------------------------|
| Router.NAVIGATE | Router.js:46-48 | Dedup via `===` (strings) or `JSON.stringify` (objects) |
| Router.#toHash | Router.js:66-71 | Writes string routes to `location.hash`; ignores objects |
| NTTRouter.#mountView | ntx-router.js:81-107 | Shape-detects: `#` prefix, `@` prefix, contains `/`, has `.tag` property |
| NTTRouter.render | ntx-router.js:62-69 | Truthy → `#mountView()`, falsy → `#showSlot()` |

**Risk**: Because the contract is implicit, nothing prevents a producer from sending malformed route data. For example, `{tag: null}` would pass the object branch check at ntx-router.js:101 but fail at `document.createElement(null)` (ntx-router.js:127).

### 4.2 TX Message Contract

Navigation uses standard TX messages with specific `name` values:

| TX name | Data payload | Source | Target |
|---------|-------------|--------|--------|
| `NAVIGATE` | RouteData (any of the shapes above) | Producer's actor addr or `'sidebar'` | Router's actor addr |
| `BACK` | (ignored) | NTTRouter's actor addr | Router's actor addr |
| `SELECT` | Entity ref string (e.g., `"Product/3"`) | ntx-item/ntx-row addr | ListElement addr |

The SELECT -> NAVIGATE promotion is the only transformation: ListElement receives `SELECT` with an entity ref and forwards it as `NAVIGATE` with the same data (ListElement.js:104-109).

### 4.3 Observable Callback Contract

```javascript
router.observe('route', (newValue, oldValue, propertyName, source) => { ... });
```

Parameters (from Observable.js:126):
- `newValue` — the new route data (same shape as RouteData above)
- `oldValue` — the previous route data
- `propertyName` — always `'route'`
- `source` — the Router instance

NTTRouter ignores all parameters in its callback and simply calls `this.render()` (ntx-router.js:43), relying on `this.#router.current` for the current route.

### 4.4 Schema Resolution Contract

NTTRouter reads schema through `window.NTT.get(model)` which returns a DynamicClass (or undefined). The expected shape:

```javascript
DC.schema.ui.renderer.detail  // string: custom element tag name
DC.schema.ui.renderer.item    // string: fallback tag name
```

Both are optional. The fallback chain is: `renderer.detail` -> `renderer.item` -> `'ntx-item'` (ntx-router.js:152-154).

---

## 5. What's Easy to Change

These modifications are naturally supported by the current design and can be completed in under an hour:

### 5.1 Add a New App Route
Create a web component (e.g., `<ntx-dashboard>`), navigate via `location.hash = '@dashboard'`. NTTRouter resolves it automatically. No framework changes needed.

### 5.2 Change Which Component Renders a Model's Detail View
Set `__ui__['renderer']['detail']` on the Python model. The schema propagates to the frontend; NTTRouter picks it up in `#resolveTag()`.

### 5.3 Add a New Model to the Sidebar
Add a child element to `<ntx-sidebar>`. The route template system handles the rest.

### 5.4 Add a New Observer on Route Changes
Call `getRouter('name').observe('route', callback)`. The Observable mixin supports unlimited subscribers with proper cleanup via returned unsubscribe functions.

### 5.5 Multiple Independent Routers
Create `<ntx-router name="panel-a">` and `<ntx-router name="panel-b">`. Each creates its own Router actor with an independent stack and hash can only be bound to one (or neither). This is demonstrated implicitly by the global `routers` Map (Router.js:21).

### 5.6 Custom Back Button Behavior
Override or replace the back button click handler by subclassing NTTRouter. Or externally: send a BACK TX from any actor to the Router's address.

### 5.7 Style Customization
The CSS uses CSS custom properties throughout (ntx-router.css: `--glass-border`, `--text-1`, `--surface-3`, `--accent-dim`, `--radius-sm`, `--ease`). All visual aspects can be themed without touching the component.

---

## 6. What's Hard to Change

These modifications fight the current architecture and require significant restructuring:

### 6.1 Parameterized Routes
**Difficulty**: Hard. The entire route resolution pipeline assumes flat strings or opaque objects. Adding `Product/:id/comments` requires:
- A route parser in Router.js or NTTRouter.js
- Pattern matching logic (currently none — only shape detection)
- Parameter extraction and forwarding to mounted components
- Hash serialization that preserves parameters

The prior audit (`.traces/features/improve-routing/audit.md`) identifies this as Issue 3 and proposes Option D (URI Routes + Schema Resolution) as the solution.

### 6.2 Route Guards / Navigation Prevention
**Difficulty**: Hard. Router.NAVIGATE() mutates state immediately (Router.js:49-51) with no hook point for interception. Adding guards requires:
- A `beforeNavigate(from, to)` hook that can cancel or redirect
- Async guard support (e.g., checking unsaved changes with a confirmation dialog)
- Modification of Router.js's NAVIGATE handler to call guards before state mutation

The frontend Actor system lacks interceptors (unlike the Python-side `auth_interceptor`), so there is no infrastructure to build on.

### 6.3 Keep-Alive / Component Caching
**Difficulty**: Hard. NTTRouter destroys the current view on every navigation (`this.#currentView.remove()` is called implicitly when `shadowRoot.innerHTML` is reassigned at ntx-router.js:111). Adding caching requires:
- A component pool managed by NTTRouter
- Hide/show instead of create/destroy
- Cache eviction policy (LRU, max count)
- Handling stale data (when should a cached component re-fetch?)

### 6.4 Nested / Hierarchical Routes
**Difficulty**: Hard. The system supports only one level of routing per Router instance. A route like `Grant/3/analyze` would need:
- Route parsing to extract segments
- Nested Router instances that handle sub-paths
- Parent-child Router coordination
- URL update that reflects the full hierarchy

### 6.5 Making NTTRouter Subclass-Friendly
**Difficulty**: Hard. All meaningful state is in private fields (`#router`, `#currentView`, `#routerUnsub`). JavaScript private fields cannot be accessed by subclasses. Options:
- Convert to WeakMap-based privacy (allows inheritance but breaks encapsulation intent)
- Add protected hooks (e.g., `beforeMount(routeData)`, `afterMount(element)`) without exposing internals
- Accept that NTTRouter is a leaf class, not a base class

### 6.6 Replacing Hash Routing with History API
**Difficulty**: Moderate-to-Hard. Router.js uses `location.hash` exclusively. Switching to `history.pushState` / `popstate` requires:
- Replace `#toHash()` with `pushState()` calls
- Replace `hashchange` listener with `popstate` listener
- Server-side catch-all route (all paths → index.html)
- Update all hash references across examples and apps

---

## 7. Constraints & Limitations

### 7.1 Single Hash Namespace
Only one Router can sync with `location.hash` at a time. If two Routers have `hash: true`, they will fight over the hash value. The constructor (Router.js:29-37) does not check for this conflict.

### 7.2 No Serialization for Object Routes
Object routes (`{tag, attrs, title}`) cannot be serialized to the URL hash (Router.js:66-70). This means:
- Page refresh loses sidebar-initiated navigation
- Browser back/forward doesn't work for object routes
- No deep linking or bookmarking for model list views

This is the most impactful limitation, identified as Issue 2 in the prior audit.

### 7.3 Synchronous State Mutation
Router.NAVIGATE() is synchronous and does not support async operations (Router.js:45-54). There is no way to:
- Wait for a component to finish loading before committing navigation
- Run async validation (e.g., "do you want to save changes?")
- Cancel navigation after inspection

### 7.4 No Route Matching / Patterns
Route resolution in NTTRouter is shape-based, not pattern-based (ntx-router.js:81-107). There is no route table, no wildcard matching, no fallback chain beyond the final `#showSlot()`.

### 7.5 Stack-Only History Model
The Router uses a simple array stack (`#stack`, Router.js:26). It does not support:
- Forward navigation (after going back, you can navigate forward in browsers)
- History replacement (navigating to a corrected URL without adding a stack entry)
- Stack manipulation (inserting, removing, or reordering entries)

The `#fromHash()` handler (Router.js:74-86) pushes to the stack on every hash change, which means the internal stack grows monotonically and can diverge from the browser's history.

### 7.6 No Transition Animations Between Views
NTTRouter replaces shadow DOM contents on every navigation. There is no lifecycle hook for enter/exit animations. The CSS `fadeIn` animation (ntx-router.css:57-60) only applies to the new view; the old view is instantly removed.

### 7.7 Memory Leak Risk in Router Registry
The module-level `routers` Map (Router.js:21) holds strong references to Router instances. If a Router is created and its NTTRouter host is disconnected from the DOM, the Router instance remains in the Map. There is no `destroy()` or cleanup method on Router, and `disconnectedCallback()` on NTTRouter only unsubscribes from the observable — it does not remove the Router from the global Map (ntx-router.js:55-58).

---

## 8. Feature Integration Guide

### Adding a New Feature: "Breadcrumb Navigation"

A breadcrumb trail showing the current navigation path. This touches the Router subsystem without requiring modifications to Router.js itself.

**Step 1: Create the Component**

Create `ntx-breadcrumb.js` in `packages/n3tx-ui/src/n3tx_ui/static/components/`:
```javascript
import { Component } from '../core/Component.js';
import { getRouter } from '../core/Router.js';

export class NTTBreadcrumb extends Component {
    #router = null;
    #unsub = null;

    connectedCallback() {
        super.connectedCallback();
        const name = this.getAttribute('router');
        this.#router = getRouter(name);
        if (this.#router) {
            this.#unsub = this.#router.observe('route', () => this.render());
        }
        this.render();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        this.#unsub?.();
    }

    render() {
        // Read router.current to build breadcrumb
    }
}
customElements.define('ntx-breadcrumb', NTTBreadcrumb);
```

**Step 2: Wire to Router**

Use the `router` attribute (same pattern as NTTRouter):
```html
<ntx-breadcrumb router="main"></ntx-breadcrumb>
<ntx-router name="main" hash>...</ntx-router>
```

**Step 3: Access Stack Data**

**Problem**: Router.#stack is private. Breadcrumbs need the full path, not just the current route. Options:
- Add a public `stack` getter to Router.js (requires modifying core file)
- Build the breadcrumb from route observations over time (fragile — misses entries from before the breadcrumb was mounted)
- Read `location.hash` history directly (only works for hash-synced string routes)

This illustrates the encapsulation tension: private fields protect invariants but block legitimate read-only access patterns.

**Step 4: Add Tests**

Add to `tests/frontend/tests/components/ntx-breadcrumb.test.js`:
- Unit tests: verify render output for various route states
- Integration tests: verify breadcrumb updates on NAVIGATE/BACK

**Step 5: Register in Example Apps**

Add `<link rel="modulepreload" href="./components/ntx-breadcrumb.js">` and `import './components/ntx-breadcrumb.js'` to index.html files.

**Watch out for:**
- Router's private `#stack` — you cannot access it from outside
- Race condition: Router may have already navigated before the breadcrumb connects
- Hash-only sync — object routes won't appear in breadcrumbs if you rely on `location.hash`

---

## 9. Comparison with Alternatives

### 9.1 vs. Standard Client-Side Routers (e.g., vaadin-router, page.js, navigo)

| Aspect | N3TX Router | Standard Routers |
|--------|-------------|-----------------|
| Route definitions | Implicit (shape detection) | Explicit (route table with patterns) |
| Path parameters | Not supported | Core feature (`/user/:id`) |
| Query parameters | Not supported | Core feature (`?sort=name`) |
| Guards/middleware | Not supported | Common feature (`beforeEnter`, `canActivate`) |
| History API | Hash only | pushState + hash modes |
| Nested routes | Not supported | Common feature |
| Transitions | Not supported | Animation hooks |
| Bundle size | ~90 lines (Router.js) | 2-15 KB |

**Assessment**: The N3TX Router is dramatically simpler than conventional routers. This is appropriate for its current scope (entity detail navigation in schema-driven apps) but insufficient for apps like veille that need parameterized routes.

### 9.2 vs. Web Component Routers (e.g., lit-element router patterns)

Lit ecosystem typically uses `@vaadin/router` or `@lit-labs/router`, which:
- Define routes as a flat or nested config array
- Support URL path parameters with named groups
- Integrate with `lit-html` for rendering

N3TX's approach differs fundamentally: routes are not declared, they are inferred from the route data shape. This aligns with the "schema is the source of truth" philosophy — the model definition (via `ui.renderer`) controls how things render, not a route config.

**The tradeoff**: Zero-config for simple cases (navigating to `Product/3` just works) at the cost of no support for complex routing patterns.

### 9.3 What a Migration Would Look Like

If the project were to adopt Option D from the prior audit (URI Routes + Schema Resolution):

1. **Phase 1** (non-breaking): Add `parseRoute(string)` utility function. Does not change existing behavior — just makes structured data available.

2. **Phase 2** (behavioral change): Update NTTRouter's `#mountView()` to use `parseRoute()` + schema `ui.renderer.list` for list views. Sidebar emits string routes instead of objects.

3. **Phase 3** (new feature): Add `?key=value` query param support to `parseRoute()`. Pass params as component attributes.

4. **Phase 4** (optional): Add route guards via a `beforeNavigate` hook on Router.

Each phase is independently deployable. The critical design decision: keep routes as strings (serializable, bookmarkable, inspectable) and use schema for component resolution (consistent with N3TX philosophy).

---

## 10. Evolution Trajectory

### Git History Analysis

| Commit | Date | Change |
|--------|------|--------|
| `7550aeb` | Early | Initial Router implementation with tests |
| `b81403f` | v0.9 | Rename: PyBend -> N3TX. Tags `ntt-*` -> `ntx-*` |
| `1b0f3f9` | v0.9 | Constructable stylesheets, render coalescing |
| `dc76046` | v0.9 | Sidebar and topbar added (navigation producers) |
| `3205d98` | v0.9 | Sidebar route templates, table validation |
| `0ff8581` | v0.10 | Move to n3tx-core package |
| `de131b3` | v0.10 | Move to n3tx-ui package |

**Pattern**: Router.js has been stable since initial implementation. All changes have been in the surrounding system (sidebar, component refactoring, package splits). The Router's core logic (~90 lines) has not changed meaningfully — the same NAVIGATE/BACK/hash sync code has persisted through two major refactors.

### Direction

The prior audit (`.traces/features/improve-routing/audit.md`) establishes a clear direction: Option D (URI Routes + Schema Resolution). This is explicitly framed in the project's `improve-routing` feature trace.

The trajectory is:
1. **Current** (v0.9): Shape-based routing sufficient for single-model apps
2. **Near-term** (planned): URI string routes with `parseRoute()` + schema resolution
3. **Future**: Route guards, keep-alive caching, transition animations

### Sustainability Assessment

The current design is sustainable for apps with one or two models (examples/core, examples/grants). It has already proven insufficient for the veille app, which bypasses the Router entirely with manual hash handling (apps/veille/static/index.html:275-304).

The planned URI routes migration (Option D) should restore sustainability for medium-complexity apps. However, the lack of frontend Actor interceptors means route guards will require a Router-specific mechanism rather than reusing existing infrastructure.

The split between n3tx-core (Router.js) and n3tx-ui (ntx-router.js) is clean and should survive further evolution. The dependency direction is correct (UI depends on core, not vice versa).

---

## 11. Cross-Cutting Concerns

### 11.1 Logging

Router.js does not log anything. NTTRouter inherits from Component but does not call any logging functions directly. The Actor base class logs via `Logging.dev()` on message routing (Actor.js:64), so NAVIGATE/BACK messages produce dev-level log output.

ntx-sidebar logs only on fetch failure: `console.warn('[ntx-sidebar] Failed to fetch item...')` (ntx-sidebar.js:221).

**Assessment**: Under-instrumented. Route changes are significant application events that should be logged at a higher level than `dev`.

### 11.2 Error Handling

Router.js has no error handling. If `notify()` throws in an observer callback, the error propagates uncaught from NAVIGATE/BACK handlers.

NTTRouter's `#mountView()` does not catch `document.createElement()` failures. An invalid tag name (e.g., from a malformed `@` route like `@123`) would throw an uncaught DOMException.

ntx-sidebar wraps its fetch call in try/catch (ntx-sidebar.js:220-222) but silently swallows errors with `console.warn`.

**Assessment**: Error handling is minimal. Navigation failures produce uncaught exceptions rather than graceful degradation.

### 11.3 Configuration

Router accepts one configuration option: `hash: boolean` (Router.js:29). NTTRouter reads `name` and `hash` HTML attributes (ntx-router.js:35-38). ntx-sidebar reads `models`, `router`, `view`, and `open` attributes (ntx-sidebar.js:7-12).

All configuration is declarative via HTML attributes. There is no programmatic configuration API beyond the constructor options.

### 11.4 Authentication

The routing subsystem has no direct interaction with authentication. However:

- ntx-sidebar reads `localStorage.getItem('jwtToken')` for authenticated API calls (ntx-sidebar.js:196-198).
- There are no route guards to prevent navigation to auth-required views. Authentication is enforced at the API level (backend returns 401/403), not at the routing level.
- The veille app implements its own auth redirect: `if (!user) { window.location.href = '/login.html'; }` (apps/veille/static/index.html:268-270). This is outside the Router subsystem entirely.

**Assessment**: Authentication is orthogonal to routing, which is appropriate for the current architecture. Route-level auth guards would be a valuable addition (see Section 6.2).

### 11.5 Serialization

Route data serialization occurs only in Router's hash sync:
- **Serialize**: `location.hash = this.#current` for strings (Router.js:68)
- **Deserialize**: `location.hash.slice(1)` for the hash value (Router.js:75)
- **Not serialized**: Object routes, null (Router.js:66-71)

The deduplication check uses `JSON.stringify()` for objects (Router.js:48), which is order-dependent: `{a:1, b:2}` and `{b:2, a:1}` would be considered different routes despite being semantically identical.

---

## Summary Table

| Dimension | Rating | Key Finding |
|-----------|--------|-------------|
| Extension via configuration | Good | Route templates, schema renderers, HTML attributes |
| Extension via subclassing | Poor | Private fields block meaningful subclassing |
| Extension via hooks | Moderate | Observable route changes (read-only); no interception |
| Integration coupling | Appropriate | Loose (TX-based) between producers and Router; tight (inheritance) between NTTRouter and Component |
| Data contracts | Implicit | No typed interfaces; polymorphic route data is convention-only |
| Change-friendliness (simple) | Excellent | New routes, new models, new observers — all easy |
| Change-friendliness (complex) | Poor | Parameterized routes, guards, caching — all hard |
| Evolution trajectory | Planned | Clear direction (Option D) but not yet implemented |
| Error resilience | Poor | Minimal error handling; failures propagate as uncaught exceptions |
| Cross-cutting integration | Minimal | No auth, minimal logging, no config API |
