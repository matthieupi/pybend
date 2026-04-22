# Frontend Router: Architecture & Design Patterns Audit

**Scope**: The "Frontend Router" subsystem spanning `n3tx-core` (Router, Observable, Actor, TX, Matrix) and `n3tx-ui` (NTTRouter, NTTSidebar, ListElement, NTTItem).
**Date**: 2026-03-25
**Auditor**: Claude Opus 4.6

---

## 1. Component Inventory

### Core Infrastructure (n3tx-core/static/core/)

| Class / Export | File:Line | Role |
|---|---|---|
| `Router` | `Router.js:23` | Pure navigation state Actor; manages route stack, hash sync, Observable notifications |
| `getRouter(addr)` | `Router.js:89` | Module-level lookup for Router instances from the global `routers` Map |
| `routers` (Map) | `Router.js:21` | Module-scoped registry mapping router addr strings to Router instances |
| `Actor` | `Actor.js:11` | Base class for all message-passing entities; provides addr, children, send, inbox |
| `Actor.subclass()` | `Actor.js:178` | Metaclass-like wiring: adds static send/inbox/children/register to a target class |
| `Observable` | `Observable.js:20` | Mixin (applied via `Actor.subclass(Target, Observable)`) adding observe/notify/signal |
| `TX` | `TX.js:7` | Message envelope dataclass: name, source, target, data, meta, timestamp |
| `Matrix` | `Matrix.js:11` | Root Actor singleton; message bus routing child dispatches and remote delegation |
| `matrix` | `Matrix.js:81` | Module-level singleton instance of Matrix (`"matrix://root"`) |
| `Component` | `Component.js:23` | HTMLElement + Actor bridge; shadow DOM, styles, schema resolution, display modes |

### View Layer (n3tx-ui/static/components/)

| Class / Export | File:Line | Role |
|---|---|---|
| `NTTRouter` | `ntx-router.js:19` | View container web component; mounts/destroys child components based on Router state |
| `NTTSidebar` | `ntx-sidebar.js:61` | Navigation producer; slide-in panel that dispatches NAVIGATE TXs from model list |
| `ListElement` | `ListElement.js:21` | Collection base class; forwards child SELECT as NAVIGATE to router |
| `NTTItem` | `ntx-item.js:26` | Single entity renderer; dispatches SELECT TX on card click |
| `NTTElement` | `NTTElement.js:21` | Single entity base class; data lifecycle (UPDATE/DESCRIBE/READ), save, error handling |

### CSS

| File | Role |
|---|---|
| `ntx-router.css` | Router chrome: back button, title bar, content area, fade-in animations |
| `ntx-sidebar.css` | Sidebar panel: overlay, slide-in, model sections, accordion, responsive mobile |

---

## 2. Responsibility Map

### Router (Router.js)

**What it does**: Manages a LIFO history stack (`#stack`), a current route pointer (`#current`), optional URL hash synchronization, and Observable notifications on every state transition.

**Why it exists**: Separates navigation **state** from navigation **view**. This is the Single Responsibility split that lets Router be tested without DOM, and lets NTTRouter focus purely on component mounting. Without it, view management and state management would be tangled in one component.

**What breaks if removed**: NTTRouter would need to manage its own stack, hash sync, and observer notifications. ListElement SELECT forwarding would have no target. The sidebar would dispatch TXs into the void. All hash-based deep linking stops working.

### NTTRouter (ntx-router.js)

**What it does**: Observes a Router actor's `'route'` property. On change, resolves route data to a concrete element tag + attributes, creates the element, and mounts it in its shadow DOM. Provides "chrome" (back button + title) when navigated away from home.

**Why it exists**: Router knows nothing about DOM. NTTRouter bridges the state machine to the visual layer. It is the only component that creates and destroys dynamically-navigated views.

**What breaks if removed**: No visual effect from any navigation. The Router would update its state, observers would fire, but nothing would appear on screen. The app would be stuck on the initial slot content forever.

### NTTSidebar (ntx-sidebar.js)

**What it does**: Renders a slide-in navigation panel listing available models. On click, dispatches NAVIGATE TXs to a named Router via Matrix. Supports three entry types (model list, singleton item, href link) and lazy-loads record accordions.

**Why it exists**: Provides the primary navigation surface for model discovery. Reads from the schema system (via `NTT.attach`) to display model names, counts, and record previews.

**What breaks if removed**: No model navigation menu. Users would only see the home view unless they manually type hash URLs. The sidebar is the only navigation producer other than in-list item clicks.

### ListElement (ListElement.js)

**What it does**: Acts as the routing bridge for item clicks. Its `SELECT` handler (line 104) checks for a `router` attribute; if present, forwards the data as a NAVIGATE TX to that router address.

**Why it exists**: Items should not know about routers. The list acts as an intermediary: items emit SELECT to their parent list, the list decides whether to forward as NAVIGATE. This indirection preserves item independence.

**What breaks if removed**: Item clicks would go nowhere. No SELECT-to-NAVIGATE forwarding. The double-hop navigation chain (item -> list -> router) is the only path from user click to detail view.

### Observable (Observable.js)

**What it does**: Mixin applied via `Actor.subclass(Target, Observable)`. Adds `observe(prop, cb)`, `notify(prop, new, old)`, and `signal(cb)` to the target's prototype via `Object.defineProperty`.

**Why it exists**: Decouples the Router (notifier) from NTTRouter (observer). Neither needs to know about the other -- they communicate through the property name `'route'`. This is the same pattern used throughout the entity system for UPDATE notifications.

**What breaks if removed**: NTTRouter would need to poll Router.current or use a different notification mechanism. The clean observer pattern that unifies Router, DynamicClass, and entity updates would fragment.

---

## 3. Design Patterns

### 3.1 Observer Pattern

**Where**: `Observable.js` -> applied to `Router` via `Actor.subclass(Router, Observable)` at `Router.js:93`.

**How it works**: Router calls `this.notify('route', newRoute, oldRoute)` in both NAVIGATE (line 53) and BACK (line 61). NTTRouter subscribes via `router.observe('route', () => this.render())` at `ntx-router.js:43`.

**Why chosen**: Clean separation between state producer (Router) and view consumer (NTTRouter). Multiple consumers could observe the same Router without either knowing about the other. Consistent with how DynamicClasses notify list components via UPDATE.

**Assessment**: Correct choice. The Observer pattern is the natural fit for a state-change-driven reactive system. The API is clean: `observe()` returns an unsubscribe function, `notify()` passes both new and old values. One concern: the `notify` callback signature `(newValue, oldValue, property, source)` differs from standard EventTarget patterns, which could confuse developers expecting `(event)`.

### 3.2 Actor Model (Message Passing)

**Where**: `Actor.js`, `TX.js`, `Matrix.js`. Router extends Actor. All navigation commands flow as TX messages.

**How it works**: NAVIGATE and BACK are TX handler methods on Router (UPPERCASE convention). They are invoked via the Actor inbox dispatch chain: `matrix.inbox(tx)` -> finds child by target addr -> calls `child.inbox(tx)` -> resolves `this[tx.name](tx.data, tx)`.

**Why chosen**: Consistent with the entire N3TX architecture. Every inter-component communication uses TX messages through the Matrix. Routing is not special -- it is just another actor receiving messages.

**Assessment**: Excellent alignment with N3TX philosophy ("transparent, not magical"). The routing system reuses the same primitives as entity CRUD, method invocation, and agent streaming. No routing-specific communication protocol needed. The cost is indirection: a simple "go to Product/3" involves constructing a TX, routing through Matrix, dispatching to Router's inbox, and calling NAVIGATE. But this is the framework's deliberate tradeoff -- uniformity over minimal-path-length.

### 3.3 Mixin Pattern (Prototype Mutation)

**Where**: `Observable.apply(Base)` at `Observable.js:30`. Applied to Router via `Actor.subclass(Router, Observable)` at `Router.js:93`.

**How it works**: `Observable.apply(Base)` directly mutates `Base.prototype` using `Object.defineProperty()`. It adds `_initObservable`, `signal`, `observe`, and `notify` methods. It checks for existing properties before defining (idempotent).

**Why chosen**: Router needs both Actor capabilities (inbox, send, addr) and Observable capabilities (observe, notify). JavaScript doesn't have multiple inheritance; the mixin avoids MI complexity while adding the exact methods needed.

**Assessment**: Pragmatic solution. The mutation approach is explicit (easy to trace) but has two weaknesses: (1) methods are defined on the prototype of the **first** class that calls `apply()`, meaning all subclass instances share them, and (2) the lazy `_initObservable()` call in every method body adds a small overhead per call. These are acceptable tradeoffs for the system's scale.

### 3.4 Strategy Pattern (Route Resolution)

**Where**: `NTTRouter.#mountView()` at `ntx-router.js:81-145`.

**How it works**: Route data is polymorphic. `#mountView()` uses a series of type checks to resolve the tag and attributes:

```
string starting with '#'  -> hash delegation (show slot)
string starting with '@'  -> app route: tag = 'ntx-{name}'
string with '/'           -> entity ref: tag from schema, attrs.ref = data
object with .tag          -> programmatic: use object's tag and attrs
anything else             -> fall back to #showSlot()
```

**Why chosen**: Avoids a separate route configuration DSL. The route data itself encodes the resolution strategy via its type/shape. This is simple and flexible.

**Assessment**: The pattern works but is fragile. There is no formal Route type or schema -- resolution depends on duck-typing (does the string contain '@'? does the object have a `.tag`?). This makes the system hard to extend (adding a new route type means adding another `else if` branch) and hard to validate (a malformed route object silently falls through to `#showSlot()`). A formal parser/resolver function (as proposed in the prior audit's Option D) would be more robust while keeping the "no config" philosophy.

### 3.5 Mediator Pattern (Matrix as Message Bus)

**Where**: `Matrix.js:11`. All TX routing flows through the Matrix singleton.

**How it works**: Matrix's `inbox()` (line 27) resolves the target address, finds the registered child actor, and calls its `inbox()`. If no local child matches, it delegates to the remote NetworkAdapter.

**Assessment**: Standard mediator. For the router subsystem, this means NTTSidebar dispatches NAVIGATE to `matrix.dispatch()` (line 282), Matrix looks up the Router actor by target addr, and delivers the TX. The mediator adds one hop but provides addressability and inspectability.

### 3.6 Slot-Based Default Content

**Where**: `NTTRouter.#showSlot()` at `ntx-router.js:72-78`. When no route is active, the router shows `<slot></slot>`, projecting the light DOM children declared inside `<ntx-router>`.

**How it works**: Slot projection is a native Shadow DOM feature. Children declared in the host element's light DOM (`<ntx-list model="Product">`) are projected into the `<slot>` element without cloning or moving.

**Assessment**: Clean use of the platform. The "home page" is just the declared children. Navigation replaces them with dynamically-created views. Going back restores the slot. This is idiomatic Web Components usage and requires zero framework code.

---

## 4. Data Flow

### 4.1 Primary Navigation Flow (Item Click to Detail View)

```
User clicks card in ntx-item
     |
     v
ntx-item.js:747  card click handler fires
     | Checks: not interactive element, not edit mode
     | Reads: select-target attribute (set by ListElement.createChild)
     v
TX { name:'SELECT', source: item.addr, target: listElement.addr, data: item.ref }
     |
     v [via Actor.send -> Matrix routing -> ListElement.inbox]
     |
ListElement.js:104  SELECT(data, tx) handler
     | Calls: this.toggle(data) for selection state
     | Reads: router attribute on the list element
     v
TX { name:'NAVIGATE', source: list.addr, target: routerAddr, data: "Product/3" }
     |
     v [via Actor.send -> Matrix routing -> Router.inbox]
     |
Router.js:45  NAVIGATE(data, tx) handler
     | Checks: dedup (=== for strings, JSON.stringify for objects)
     | Pushes: old current onto #stack
     | Sets: #current = data
     | If hashSync: writes location.hash
     v
Router.notify('route', "Product/3", null)
     |
     v [via Observable -> registered callbacks]
     |
ntx-router.js:43  observe callback fires -> this.render()
     |
ntx-router.js:62  render() dispatches to #mountView("Product/3")
     |
ntx-router.js:96-100  String route resolution:
     | model = "Product", tag = #resolveTag("Product"), attrs = {ref: "Product/3"}
     |
ntx-router.js:111-144  DOM construction:
     | 1. Build chrome HTML (back button if canGoBack, title)
     | 2. Set shadowRoot.innerHTML
     | 3. document.createElement(tag), set attributes
     | 4. Force display="lg" for detail views
     | 5. Append to .router-content
     v
Detail view visible
```

### 4.2 Sidebar Navigation Flow

```
User clicks model name in ntx-sidebar
     |
     v
ntx-sidebar.js:468  model-name click handler
     |
ntx-sidebar.js:264  #navigateToModel(modelName)
     | Reads: router attribute
     | Reads: route template from #routeTemplates map (or constructs default)
     | Constructs: {tag, attrs: {model, ...template}, title}
     v
ntx-sidebar.js:282  Dynamic import('../core/Matrix.js')
     | (async -- sidebar is not an Actor)
     v
matrix.dispatch({
    name: 'NAVIGATE',
    source: 'sidebar',            <-- hardcoded string, not an actor addr
    target: routerAddr,
    data: {tag:'ntx-list', attrs:{model:'Grant'}, title:'Grant'}
})
     |
     v [Matrix.inbox -> Router.inbox -> NAVIGATE handler]
     |
Router.NAVIGATE({tag:'ntx-list', attrs:{model:'Grant'}, title:'Grant'})
     | Object route: #toHash() silently skips (no hash serialization)
     v
Observable notify -> NTTRouter render -> #mountView(object)
     |
ntx-router.js:101-104  Object route resolution:
     | tag = routeData.tag, attrs = routeData.attrs, title = routeData.title
     v
DOM: <ntx-list model="Grant"> created and mounted
```

### 4.3 Hash Sync Flow (Browser-Initiated)

```
User types URL with hash or uses browser back/forward
     |
     v
window 'hashchange' event fires
     |
     v
Router.js:34  hashchange listener -> #fromHash()
     |
Router.js:74-86  #fromHash()
     | Reads: location.hash.slice(1)
     | If hash differs from current:
     |   push old to stack, set current, notify
     | If hash empty and current is set:
     |   set current = null, notify
     | NOTE: does NOT push old to stack on hash-clear (line 83)
     v
Observable notify -> NTTRouter render
```

### 4.4 Back Navigation Flow

```
User clicks back button in NTTRouter chrome
     |
     v
ntx-router.js:121-123  back-btn click listener
     |
TX { name:'BACK', source: router.addr, target: router.addr }
     |
     v [Actor.send -> Matrix routing -> Router.inbox]
     |
Router.js:56  BACK() handler
     | Guards: canGoBack check
     | Pops: #stack.pop() -> sets as #current
     | If hashSync: writes location.hash (or clears it)
     v
Observable notify -> NTTRouter render
     | If current is null: #showSlot() (restore home content)
     | If current is data: #mountView(data) (show previous view)
```

---

## 5. State Management

### 5.1 State Locations

| State | Location | Type | Mutated By |
|---|---|---|---|
| Current route | `Router.#current` | Instance private field | `NAVIGATE()`, `BACK()`, `#fromHash()` |
| History stack | `Router.#stack` | Instance private array | `NAVIGATE()` (push), `BACK()` (pop), `#fromHash()` (push) |
| Hash sync flag | `Router.#hashSync` | Instance private boolean | Constructor only (immutable after init) |
| Router registry | `routers` (module Map) | Module-level global | `Router` constructor (set), never deleted |
| Current view element | `NTTRouter.#currentView` | Instance private field | `#mountView()` (set), `#showSlot()` (clear) |
| Router actor ref | `NTTRouter.#router` | Instance private field | `connectedCallback()` (set once) |
| Observer unsub | `NTTRouter.#routerUnsub` | Instance private field | `connectedCallback()` (set), `disconnectedCallback()` (called) |
| Sidebar entries | `NTTSidebar.#entries` | Instance private array | `connectedCallback()` (populated from children/attrs) |
| Sidebar route templates | `NTTSidebar.#routeTemplates` | Instance private Map | `connectedCallback()` (populated from children) |
| Sidebar expanded state | `NTTSidebar.#expanded` | Instance private Set | `#toggleSection()` (add/delete) |
| Sidebar dynamic classes | `NTTSidebar.#dynamicClasses` | Instance private object | `#bootstrapModels()` callback |
| URL hash | `location.hash` | Browser global | `Router.#toHash()`, `#fromHash()` |

### 5.2 State Lifecycle

**Router state lifecycle**:

```
Constructor:
  #current = null, #stack = [], #hashSync = arg
  If hashSync: listen for hashchange, read initial hash

Active:
  NAVIGATE -> push old to stack, set current
  BACK     -> pop from stack, set current
  hashchange -> read hash, potentially push/set

Never destroyed:
  Routers are registered in the module-level Map and never removed.
  No unregister/destroy API exists.
```

**NTTRouter state lifecycle**:

```
Constructor:
  #router = null, #currentView = null

connectedCallback:
  Create/retrieve Router actor, subscribe to 'route'
  Auto-wire router attr on child [model] elements

Route change:
  render() -> #mountView() creates new element, sets #currentView
  render() -> #showSlot() removes #currentView, sets null

disconnectedCallback:
  Calls #routerUnsub() to stop observing route changes
  Does NOT destroy the Router actor (Router lives independently)
```

### 5.3 State Consistency Risks

**Risk 1: Internal stack vs browser history divergence**. Router maintains its own `#stack` array independently from the browser's history stack. When hash sync is on, both track navigation, but they can diverge:
- Object routes are pushed to `#stack` but NOT to browser history (no hash written)
- Browser back/forward fires hashchange, which pushes to `#stack` again
- The `#fromHash()` method on line 83 does NOT push old to stack when clearing hash, creating an asymmetry with NAVIGATE's always-push behavior

**Risk 2: Router instances are never cleaned up**. The module-level `routers` Map (Router.js:21) grows monotonically. If a `<ntx-router>` element is removed from the DOM and reconnected with a different name, the old Router instance persists in memory. There is no `unregister()` or `destroy()` method.

**Risk 3: `#fromHash()` creates a stack entry that `BACK()` will pop**. When the user types a URL with a hash, `#fromHash()` pushes `null` (the old current) onto the stack. If the user then clicks the back button, BACK pops `null`, which triggers `#showSlot()`. This is usually correct but creates a phantom stack entry for the initial null state.

---

## 6. Coupling Analysis

### 6.1 Coupling Matrix

| From | To | Type | Strength | Mechanism |
|---|---|---|---|---|
| Router | Actor | Inheritance | Tight | `extends Actor` (Router.js:23) |
| Router | Observable | Mixin | Medium | `Actor.subclass(Router, Observable)` (Router.js:93) |
| Router | Matrix | Registration | Medium | `matrix.register(this)` in constructor (Router.js:31) |
| Router | window | Side effect | Medium | hashchange listener, location.hash writes |
| NTTRouter | Component | Inheritance | Tight | `extends Component` (ntx-router.js:19) |
| NTTRouter | Router | Import + creation | Tight | `import { Router, getRouter }`, creates instances (ntx-router.js:16,38) |
| NTTRouter | TX | Import + construction | Medium | `import TX`, constructs BACK messages (ntx-router.js:17,122) |
| NTTRouter | window.NTT | Runtime lookup | Loose | `window.NTT.get(model)` for tag resolution (ntx-router.js:149-151) |
| NTTSidebar | HTMLElement | Inheritance | Tight | `extends HTMLElement` (ntx-sidebar.js:61) |
| NTTSidebar | Matrix | Dynamic import | Loose | `import('../core/Matrix.js')` for dispatch (ntx-sidebar.js:282) |
| NTTSidebar | NTT | Import | Medium | `import { NTT }` for attach/bootstrap (ntx-sidebar.js:40) |
| ListElement | Component | Inheritance | Tight | `extends Component` (ListElement.js:21) |
| ListElement | TX | Import | Medium | Constructs NAVIGATE TX in SELECT handler |
| ListElement | Router | Attribute | Loose | Reads `router` attribute, no import |
| NTTItem | NTTElement | Inheritance | Tight | `extends NTTElement` (ntx-item.js:26) |
| NTTItem | TX | Import | Medium | Constructs SELECT TX on click |
| NTTItem | ListElement | Attribute | Loose | Reads `select-target` attribute, no import |

### 6.2 Coupling Assessment

**Tight coupling (acceptable)**:
- Router -> Actor: Fundamental. Router IS an Actor. Removing this would mean reimplementing message dispatch.
- NTTRouter -> Router: NTTRouter is the Router's view. It must know how to create, reference, and observe Routers. This is not avoidable.
- NTTRouter -> Component: Standard inheritance for web components.

**Medium coupling (monitor)**:
- NTTRouter -> TX: NTTRouter constructs raw TX objects for the BACK button. This could be simplified by calling `this.#router.BACK()` directly instead of routing through the Actor system. However, the TX approach is consistent with the framework's "everything is a message" philosophy.
- NTTSidebar -> NTT: The sidebar needs schema data for display names and counts. The `NTT.attach()` API is the standard way to get this.

**Loose coupling (good)**:
- ListElement -> Router: ListElement only knows the router's address string (from an attribute). No import, no type dependency. This is exemplary loose coupling.
- NTTItem -> ListElement: Items only know the `select-target` address. They have no idea that a ListElement is on the other end, or that routing is involved.

**Problematic coupling**:
- NTTSidebar -> Matrix (dynamic import): The sidebar dispatches TXs by dynamically importing Matrix and calling `matrix.dispatch()`. This is the ONLY component in the system that does this. Every other component inherits `send()` from Component/Actor. The dynamic import exists because NTTSidebar extends `HTMLElement` directly, not `Component`.

### 6.3 Dependency Direction

```
                    Actor (n3tx-core)
                   /      \
            Router          Component (n3tx-core)
            (n3tx-core)    /          \
               |       NTTElement    ListElement (n3tx-ui)
               |       (n3tx-ui)        |
               |           |         (SELECT -> NAVIGATE)
               |       NTTItem           |
               |       (n3tx-ui)    reads 'router' attr
               |           |             |
               +-----+-----+-----+------+
                     |
                 NTTRouter (n3tx-ui)
                     |
        creates/observes Router instances

   NTTSidebar (n3tx-ui) ---> Matrix (n3tx-core) [dynamic import]
                       \---> NTT (n3tx-core) [static import]
```

Dependencies flow from n3tx-ui to n3tx-core, never the reverse. This respects the package boundary (n3tx-ui depends on n3tx-core, not vice versa).

---

## 7. Cohesion Assessment

### Router.js -- HIGH cohesion

The Router class does exactly one thing: manage navigation state. It has two TX handlers (NAVIGATE, BACK), two private sync methods (#toHash, #fromHash), and two getters (current, canGoBack). Every method directly relates to route state management. The class is 87 lines including comments. There are no mixed concerns.

The module also exports `getRouter()` and maintains a module-level `routers` Map. This registry is closely related to Router's purpose (finding routers by address). Acceptable cohesion.

### NTTRouter (ntx-router.js) -- HIGH cohesion

NTTRouter does one thing: mount views based on route state. It has `render()`, `#mountView()`, `#showSlot()`, and `#resolveTag()`. Every method is about translating route data into DOM. The class is 158 lines. No mixed concerns.

One potential cohesion concern: `#resolveTag()` at line 148 accesses `window.NTT` directly for schema lookup. This is view resolution logic, which arguably belongs here, but the `window.NTT` access pattern is unusual compared to the rest of the codebase (which imports NTT).

### NTTSidebar (ntx-sidebar.js) -- MEDIUM cohesion

The sidebar handles three distinct concerns:
1. **Navigation dispatch** (#navigateToModel, #navigateToItem, #navigateToLink) -- 70 lines
2. **Model bootstrapping & data fetching** (#bootstrapModels, #fetchItemRef, #updateModelHeader, #updateModelCount) -- 90 lines
3. **Rendering & DOM management** (#render, #renderModelEntry, #renderItemEntry, #renderLinkEntry, #bindModelEvents, etc.) -- 130 lines

These are related (the sidebar navigates between models), but the data-fetching concern (fetching singleton items, tracking pagination metadata, subscribing to UPDATE observables) is a significant secondary responsibility. The class is 498 lines -- the largest in the subsystem.

The sidebar is borderline "feature class": it does a lot, but everything it does is in service of one UX concept (the navigation panel). It would benefit from extracting the model-bootstrapping concern into a helper, but it is not a god class.

### ListElement.js -- HIGH cohesion (routing concern is minimal)

ListElement is primarily about collection data lifecycle. Its routing involvement is exactly one method: `SELECT()` at line 104 (7 lines). This is appropriate -- the list's routing role is just forwarding, not managing.

### Observable.js -- HIGH cohesion

Pure mixin. Three methods (observe, notify, signal) and one init helper. All related to the observer pattern. 133 lines.

### Component.js -- MEDIUM cohesion (but not routing-specific)

Component handles multiple concerns (actor identity, schema resolution, ref resolution, value management, stylesheet adoption, adaptive display, resize observation). This is a known tradeoff -- it is the "unified base class" documented in its header comment. The routing-relevant surface is minimal: it has no direct routing code. It just provides the infrastructure (addr, send, shadow DOM) that routing components build on.

---

## 8. Boundary Analysis

### 8.1 Public vs Internal Surface

| Component | Public API | Internal / Private | Enforcement |
|---|---|---|---|
| Router | `current` (getter), `canGoBack` (getter), `NAVIGATE()`, `BACK()` | `#current`, `#stack`, `#hashSync`, `#toHash()`, `#fromHash()` | True private fields (`#`) |
| Router module | `Router` (class), `getRouter()` (function) | `routers` (Map) | ES module scope (not exported) |
| NTTRouter | `render()` (Component override) | `#router`, `#routerUnsub`, `#currentView`, `#mountView()`, `#showSlot()`, `#resolveTag()` | True private fields/methods (`#`) |
| NTTSidebar | `open()`, `close()`, `toggle()` | `#entries`, `#models`, `#routeTemplates`, `#dynamicClasses`, `#itemRefs`, `#expanded`, etc. | True private fields (`#`) |
| Observable | `observe()`, `notify()`, `signal()` | `_initObservable()`, `__signals`, `__observers` | Underscore convention only (not enforced) |
| Component | `addr`, `model`, `proto`, `schema`, `value`, `ref`, `render()`, `prerender()`, `display` | `#addr`, `#hash`, `#href`, `#model`, `#proto`, `#data`, `#displayMode`, etc. | Mix of `#` (private) and underscore |

**Assessment**: Boundaries are well-enforced in the routing-specific classes. Router and NTTRouter use true private fields (`#`) for all internal state. The sidebar follows the same pattern. Observable's `__signals` and `__observers` use double-underscore convention but are not truly private -- they are set on the instance at runtime (necessary because the mixin cannot use `#` private fields, which are lexically scoped to the defining class).

### 8.2 Package Boundaries

The Router/Observable/Actor/TX/Matrix classes live in `n3tx-core/static/core/`. NTTRouter/NTTSidebar/ListElement/NTTItem live in `n3tx-ui/static/components/`. The dependency direction is strictly ui -> core, never reverse.

The one gray area is NTTRouter importing from `../core/Router.js` and `../core/TX.js`. At runtime, these resolve to n3tx-core's served files (the build system merges static directories). The import paths assume a specific directory layout, which is fragile if the static serving strategy changes.

---

## 9. Configuration Surface

### 9.1 Currently Configurable

| Configuration | Where | How | Default |
|---|---|---|---|
| Router address | `<ntx-router name="...">` | HTML attribute | `"router-{generated-id}"` |
| Hash sync | `<ntx-router hash>` | Presence attribute | `false` |
| Router for lists | `<ntx-list router="...">` | HTML attribute | none (clicks swallowed) |
| Sidebar router | `<ntx-sidebar router="...">` | HTML attribute | none (navigation disabled) |
| Sidebar models | `<ntx-sidebar models="...">` | HTML attribute (legacy) | derived from children |
| Sidebar view | `<ntx-sidebar view="grid|table">` | HTML attribute | `"grid"` |
| Detail renderer | `schema.ui.renderer.detail` | Backend model `__ui__` | `'ntx-item'` |
| Item renderer | `schema.ui.renderer.item` | Backend model `__ui__` | `'ntx-item'` |

### 9.2 Hardcoded (Should Be Configurable)

| Hardcoded Value | Location | Impact |
|---|---|---|
| `'ntx-item'` fallback tag | `ntx-router.js:154` | Cannot change the default detail view component without schema |
| `'ntx-'` prefix for `@` routes | `ntx-router.js:94` | App routes must follow `ntx-{name}` naming convention |
| `display="lg"` for detail views | `ntx-router.js:137` | All navigated detail views forced to large display mode |
| Back button SVG icon | `ntx-router.css:36` | Cannot customize the back icon via CSS custom properties |
| `56px` top offset for sidebar | `ntx-sidebar.css:37` | Hardcoded assumption about topbar height |
| `280px` sidebar width | `ntx-sidebar.css:40` | Not configurable via CSS custom property |

### 9.3 Missing Configuration

| Missing | Impact | Severity |
|---|---|---|
| No `ui.renderer.list` schema hint | NTTRouter cannot resolve list-view components from schema; sidebar must send object routes | Medium |
| No route guard/middleware hook | Cannot implement "unsaved changes" confirmation or auth redirects | Medium |
| No view caching/keep-alive option | Every navigation recreates components from scratch | Low-Medium |
| No title customization strategy | Title is derived ad-hoc from route data, not from schema display names | Low |
| No animation/transition configuration | Fade-in animations hardcoded in CSS, no opt-out | Low |

---

## 10. Error Propagation

### 10.1 Error Sources and Handling

| Error Source | Location | Handling | Consequence |
|---|---|---|---|
| Navigate to unknown custom element tag | `ntx-router.js:127` | `document.createElement(tag)` silently creates an `HTMLUnknownElement` | Blank view, no error shown. The element is mounted but renders nothing. |
| `#resolveTag` with no NTT registry | `ntx-router.js:149-151` | Returns `'ntx-item'` fallback | Falls back to default renderer. Silent. Correct behavior. |
| Sidebar fetch for item ref fails | `ntx-sidebar.js:220` | `catch (e) { console.warn(...) }` | Warning logged, sidebar continues with model name instead of item name. Graceful degradation. |
| No router attribute on ListElement | `ListElement.js:106-109` | `if (routerAddr)` guard | SELECT is silently swallowed. Item click does nothing. No error, no feedback. |
| No select-target on NTTItem | `ntx-item.js:749` | `if (target)` guard | Card click does nothing. Silent. |
| Router BACK with empty stack | `Router.js:57` | `if (!this.canGoBack) return` | No-op. Correct behavior. |
| Router NAVIGATE with same data | `Router.js:46-48` | Dedup check, return early | No-op. Correct behavior. |
| Hash sync with object route | `Router.js:67-71` | `if (typeof this.#current === 'string')` -- objects silently skipped | Hash not updated. Refresh loses state. Silent failure with real UX impact. |
| Object dedup via JSON.stringify | `Router.js:48` | `JSON.stringify(data) === JSON.stringify(this.#current)` | Property order-dependent. `{a:1, b:2}` !== `{b:2, a:1}`. Could cause false negatives. |
| Matrix dispatch to unregistered Router | `Matrix.js:44` | `Logging.error(...)`, message dropped | Error logged but navigation silently fails. No feedback to user. |
| NTTRouter not connected (render called early) | `ntx-router.js:63` | `this.#router?.current` null check | Shows slot content (safe default). |

### 10.2 Error Propagation Path

```
Error occurs in component mounting
  -> NTTRouter.#mountView() has NO try/catch
    -> Unhandled exception bubbles to browser
      -> Console error, router may be in inconsistent state

Error occurs in Router.NAVIGATE()
  -> Router.NAVIGATE() has NO try/catch
    -> Matrix.inbox() wraps in try/catch (Matrix.js:39-42)
      -> Logging.error() called, TX returned

Error occurs in sidebar navigation
  -> #navigateToModel() has NO try/catch
    -> Dynamic import().then() chain
      -> Unhandled promise rejection if Matrix import fails
```

### 10.3 Error Handling Assessment

The subsystem follows a "silent fallback" strategy: most error conditions result in a no-op or a default behavior rather than an explicit error. This is consistent with the framework's "degrade gracefully" philosophy but creates debugging challenges:

- **Good**: Router guards against empty stack, duplicate navigation, and missing hash. NTTRouter guards against missing router reference.
- **Bad**: No error is ever surfaced to the user when navigation fails. If a NAVIGATE TX targets a non-existent router, the message is silently dropped by Matrix with only a console log.
- **Concerning**: `#mountView()` has no try/catch. If `document.createElement(tag)` succeeds but the created element throws in its constructor or connectedCallback, the NTTRouter's shadow DOM is left in a partially-built state (chrome rendered, content area empty or broken). There is no recovery path.
- **Concerning**: The `#fromHash()` method at Router.js:83 handles hash-clear by setting `#current = null` but does NOT push old to stack. This means the user cannot use the internal BACK button to return to the pre-hash state. This asymmetry is not documented and appears to be a bug.

---

## 11. Architecture Diagram (Consolidated)

```
                    +---------+
                    |  User   |
                    +----+----+
                         |
              +----------+----------+
              |                     |
         clicks item          clicks sidebar
              |                     |
              v                     v
         +--------+          +-----------+
         |NTTItem |          |NTTSidebar |
         |.card   |          |.model-name|
         +---+----+          +-----+-----+
             |                     |
       TX SELECT              matrix.dispatch
     target=list            NAVIGATE TX (object)
             |                     |
             v                     v
       +-----------+         +----------+
       |ListElement|         |  Matrix  |
       |.SELECT()  |         |  inbox() |
       +-----+-----+         +-----+----+
             |                      |
       TX NAVIGATE            routes to child
     target=router                  |
             |                      |
             +----------+-----------+
                        |
                        v
                   +--------+
                   | Router |  (Actor + Observable)
                   |--------|
                   |#current|  <-- state
                   |#stack  |  <-- history
                   +---+----+
                       |
                 notify('route')
                       |
                       v
                  +---------+
                  |NTTRouter|  (Component)
                  |---------|
                  |render() |  --> #mountView() or #showSlot()
                  +---------+
                       |
                       v
              +------------------+
              | Dynamic Element  |
              | <ntx-item>       |
              | <ntx-list>       |
              | <ntx-profile>    |
              +------------------+
```

---

## 12. Summary of Findings

### Strengths

1. **Clean state/view separation**. Router (state) and NTTRouter (view) are properly separated. Router is pure state with zero DOM knowledge. NTTRouter is pure view with no state management. This is the most important architectural decision in the subsystem, and it is correct.

2. **Consistent use of Actor/TX messaging**. Navigation commands flow through the same TX/Matrix system as all other N3TX communication. No special-case routing protocol. This embodies the "primitives, not opinions" philosophy.

3. **Strong encapsulation**. All three primary classes (Router, NTTRouter, NTTSidebar) use true private fields (`#`). Internal state cannot be accidentally accessed or mutated from outside.

4. **Loose coupling in the navigation chain**. Items know only a `select-target` address. Lists know only a `router` address. Neither knows about the other or about the Router class. This indirection is well-designed and permits flexible composition.

5. **Good test coverage at multiple levels**. Unit tests (Router.test.js, ntx-router.test.js), integration tests (router-navigation.test.js), and E2E tests (ntx-router-unit.spec.js) cover the core flows. The test suite validates string routes, object routes, dedup, stack mechanics, hash sync, and edge cases.

### Weaknesses

1. **Object routes cannot survive hash round-trip** (Router.js:66-71). Sidebar-initiated navigation creates object route data that is silently dropped by `#toHash()`. This means all sidebar navigations are ephemeral: refresh loses them, browser back does not restore them, they cannot be bookmarked. This is the single largest architectural gap.

2. **NTTSidebar is not an Actor** (ntx-sidebar.js:61). It extends `HTMLElement` directly, bypassing the Component/Actor infrastructure. This forces it to use `matrix.dispatch()` via dynamic import with a hardcoded `source: 'sidebar'` string. It is the only component in the system that does this, creating an inconsistency.

3. **No formal route type or parser**. Route resolution in `#mountView()` relies on duck-typing (is it a string? does it start with `@`? does it have a `.tag`?). This makes the system hard to extend, hard to validate, and prone to silent fallthrough to `#showSlot()` on malformed data.

4. **Full DOM rebuild on every navigation** (ntx-router.js:111). No component caching or keep-alive. Every navigation destroys the current view and creates a new one from scratch, triggering fresh schema resolution, data fetch, and render.

5. **Hash sync stack asymmetry**. `#fromHash()` at Router.js:83 does not push old route to stack when hash is cleared, but NAVIGATE always pushes. This creates an inconsistent back-button experience.

6. **No route guards**. There is no mechanism to intercept, cancel, or redirect navigation. The Router's Actor inbox has no interceptor support for NAVIGATE/BACK messages.

### Philosophy Alignment

| Principle | Assessment |
|---|---|
| "The model is the app" | Partially aligned. Entity routes resolve tags from schema `ui.renderer`. But list routes require object data from sidebar because there is no `ui.renderer.list` hint. |
| "Zero to working, then customize" | Aligned. Default behavior works with no config: `<ntx-router hash>` + slot content is all that is needed. |
| "Primitives, not opinions" | Aligned. Router provides composable building blocks (stack, observe, TX), not a rigid routing framework. |
| "Backend is authoritative" | Partially aligned. Schema drives detail tag resolution. But sidebar constructs route objects client-side, bypassing schema authority. |
| "Transparent, not magical" | Aligned for string routes (readable hash URLs). Not aligned for object routes (opaque, not inspectable in URL). |
| "Modular where it simplifies" | Aligned. Router/NTTRouter split is a genuine simplifying boundary. NTTSidebar's non-Actor status is a pragmatic but inconsistent choice. |
