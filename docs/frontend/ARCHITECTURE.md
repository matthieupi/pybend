# N3TX Architecture

## Table of Contents

1. [Overview](#overview)
2. [System Layers](#system-layers)
3. [Class Hierarchy](#class-hierarchy)
4. [Module Map](#module-map)
5. [Initialization Sequence](#initialization-sequence)
6. [Data Flow Summary](#data-flow-summary)
7. [Current Status](#current-status)

---

## Overview

N3TX is a browser-side runtime for building schema-driven UIs on top of the N3TX backend. It uses an **Actor model** for all inter-component communication: every entity in the system (data models, UI components, the network layer) is an Actor with an address, an inbox, and a send method. Messages flow through a central **Matrix** (root actor) that routes locally or forwards to the network.

The key design goals:
- **Schema-driven**: The backend defines models (via Pydantic/OpenAPI). The frontend pulls those schemas at runtime and generates typed entity classes dynamically.
- **Decoupled**: UI components never call HTTP directly. They send messages to data actors, which handle remote calls transparently.
- **Hierarchical routing**: Actors form a tree. Messages route through the tree, bubbling to the Matrix when the target is not a local child.

---

## System Layers

```
+----------------------------------------------------------+
|  UI Layer (Web Components)                               |
|  Component > NTTElement / ListElement > NTTItem, NTTList  |
+-----------------------------+----------------------------+
                              |  TX messages (ATTACH, UPDATE,
                              |  DESCRIBE, CONNECT, READ...)
+-----------------------------v----------------------------+
|  Actor / Matrix Layer                                    |
|  Actor.subclass() wiring, Matrix routing, Observable     |
+-----------------------------+----------------------------+
                              |  TX messages
+-----------------------------v----------------------------+
|  Data Layer (Transfer Types)                             |
|  TT > N3TX (registry + entity base) > DynClass (per type)|
+-----------------------------+----------------------------+
                              |  TX messages with meta.remote
+-----------------------------v----------------------------+
|  Transport Layer                                         |
|  NetworkAdapter > HTTP / Socket                          |
+-----------------------------+----------------------------+
                              |  fetch() / WebSocket
+-----------------------------v----------------------------+
|  N3TX Backend (FastAPI)                                |
|  /ModelName (schema), /tablename (CRUD)                  |
|  /tablename/:id/field/:child_id (nested FK routes)       |
+----------------------------------------------------------+
```

---

## Class Hierarchy

```
Actor                          # Base actor: addr, inbox, send, children, spawn
  |
  +-- Matrix                   # Singleton root actor, message router + network gateway
  |
  +-- Router                   # Navigation state actor (route, history stack, URL sync, Observable)
  |
  +-- TT (Transfer Type)       # Actor with href (remote endpoint) + watcher/notify pattern
  |     |
  |     +-- N3TX                # Type registry (static) + entity base class (instance)
  |           |
  |           +-- [DynClass]   # Runtime-generated subclass per model (e.g. "Product")
  |                 |
  |                 +-- instances  # Per-entity N3TX instances (Product/1, Product/2, ...)
  |
  +-- Component (HTMLElement)  # Unified web component base (Actor + Shadow DOM + schema + adaptive display)
        |
        +-- NTTElement         # Single entity lifecycle (UPDATE, DESCRIBE, READ, save)
        |     |
        |     +-- NTTItem      # Built-in default: Formidable auto-render + edit toggle
        |
        +-- ListElement        # Collection lifecycle (subscribe, UPDATE, SELECT, childTag/template resolution)
        |     |
        |     +-- NTTList      # Built-in default: grid of children (19 lines)
        |
        +-- NTTRouter          # Generic view container ("mini browser"), controlled via Router

Observable                     # Mixin: signal(), observe(), notify() - applied via Actor.subclass()
```

`Actor.subclass(Component)` is called once on Component. All subclasses (NTTElement, ListElement, NTTItem, NTTList, and developer custom components) inherit it. Do not call `Actor.subclass()` on any other component class.

---

## Module Map

```
static/
  config.js                    # API_URL, WS_URL, event name constants (config.E), debug flags
  core/
    Actor.js                   # Actor base class + subclass() metaclass helper
    Matrix.js                  # Root actor singleton, message router
    Router.js                  # Navigation state actor (route stack, URL sync, Observable)
    TX.js                      # Transaction envelope (name, source, target, data, meta, hash)
    Observable.js              # Mixin: signal/observe/notify reactivity
    N3TX.js                     # TT, N3TX classes + prototype() DynClass factory + SSR pre-loading
    Component.js               # Unified base: HTMLElement + Actor + schema + adaptive display + stylesheet hook
    Utils.js                   # generateId, simpleHash, isTypeCompatible, deepEqual, isUrl
    transport/
      NetworkAdapter.js        # Matrix's network bridge (HTTP/WS mode switching)
      HTTP.js                  # Static fetch wrapper (get/post/put/remove)
      Socket.js                # WebSocket client with heartbeat, reconnect, message queue
  components/
    NTTElement.js              # Single entity base (UPDATE, DESCRIBE, READ, save, auto-render)
    ListElement.js             # Collection base (subscribe, UPDATE, SELECT, childTag, createChild, render)
    ntx-item.js                # NTTItem: built-in default entity (Formidable + edit toggle + SELECT click)
    ntx-list.js                # NTTList: built-in default collection (19 lines, styles only)
    ntx-router.js              # NTTRouter: generic view container ("mini browser")
    ntx-router.css             # Router chrome styles (back button, title, content area)
    ntx-method.js              # NTTMethod: renders method invocation form
    ntx-element.css            # Base component styles (loading, error, empty states)
    ntx-item.css               # Item card styles (glass, fields, list-field, nested, groups)
    ntx-list.css               # List grid styles
  generators/
    form.js                    # Formidable: schema-driven HTML/form generator
                               #   field ordering, groups, widgets, validation, relationship rendering
  theme-base.css               # Shared structural theme selectors
  dark-theme.css               # Dark token entrypoint
  light-theme.css              # Light token entrypoint
  utils/
    Assert.js                  # assert(), caution(), inform() with configurable trigger level
    Logging.js                 # Logging with caller detection, styled console output
    theme.js                   # Persisted theme selection + configured theme cycling
    Snippets.js, DateFormat.js, str_utils.js  # General utilities
  docs/                        # This documentation
```

The theme runtime is page-configured: first-party pages statically link `theme-base.css` plus the theme entrypoints, then provide `window.NTX_THEME_CONFIG = { themes: [...] }` before loading `utils/theme.js`. Shell theme controls are manual — pages place `<ntx-theme-button slot="user-menu">` and `<ntx-theme-button slot="footer">` explicitly where needed.

---

## Initialization Sequence

When `index.html` loads:

```
1. Matrix.js executes
   - Actor.subclass(Matrix) wires static/instance methods
   - `new Matrix("matrix://root")` creates the singleton
   - Actor.registerRoot(matrix) sets it as the global message bus
   - Matrix creates a NetworkAdapter(this) for remote calls

2. N3TX.js executes
   - Actor.subclass(TT)
   - Actor.subclass(N3TX, Observable)   -- N3TX gets signal/observe/notify
   - window.N3TX = N3TX exposed globally

3. Component.js executes
   - Actor.subclass(Component)         -- applied ONCE, all subclasses inherit
   - matrix.register(Component)        -- Component class registered as Matrix child

4. NTTElement.js, ListElement.js execute
   - Define base classes (no Actor.subclass, no customElements.define)

5. Router.js executes
   - Actor.subclass(Router, Observable)  -- Router gets send/inbox + signal/observe/notify

6. ntx-item.js, ntx-list.js, ntx-router.js execute
   - customElements.define('ntx-item', NTTItem)     -- extends NTTElement
   - customElements.define('ntx-list', NTTList)      -- extends ListElement
   - customElements.define('ntx-router', NTTRouter)  -- extends Component

7. Browser parses <ntx-router name="main" hash>
   - NTTRouter constructor: Component base (shadow DOM, actor identity)
   - connectedCallback: creates Router("main", {hash:true}), observes 'route'
   - Sets router="main" on child <ntx-list>

8. Browser parses <ntx-list model="Product">
   - NTTList constructor runs:
     - super() -> ListElement -> Component -> HTMLElement
     - Component: attachShadow, actor identity, matrix.register, stylesheet link
     - connectedCallback: starts ResizeObserver for adaptive display
   - attributeChangedCallback fires for model="Product"
     - Sends TX { name: ATTACH, source: <list-addr>, target: N3TX, data: "Product" }
```

---

## Data Flow Summary

See [MESSAGE_PROTOCOL.md](./MESSAGE_PROTOCOL.md) for the full message protocol.
See [ACTORS.md](./ACTORS.md) for detailed per-class documentation.

The primary data flow for rendering a list of entities:

```
<ntx-list model="Product">
  |
  | attributeChangedCallback("model", "Product")
  | TX { ATTACH, source: list-addr, target: N3TX, data: "Product" }
  v
Matrix.inbox() -> routes to N3TX (static)
  |
  | N3TX.ATTACH() - "Product" not in #prototypes (undefined)
  | Sets #prototypes["Product"] = null (schema in flight)
  | Queues the ATTACH TX in #waiting
  | Dispatches: TX { SCHEMA, source: N3TX, target: http://...8000/Product, meta: {remote:true} }
  v
Matrix.inbox() -> target not local -> NetworkAdapter.send()
  |
  | HTTP.get("http://localhost:8000/Product") -> backend returns JSON schema
  v
NetworkAdapter.httpCallback() -> swaps source/target, sets name to SCHEMA
  | TX { SCHEMA, source: http://...8000/Product, target: N3TX, data: <schema> }
  v
Matrix.inbox() -> routes to N3TX (static)
  |
  | N3TX.SCHEMA(data):
  |   - Calls prototype(addr, schema, href) -> creates DynClass "Product"
  |   - Stores DynClass in #prototypes["Product"]
  |   - Registers any $defs models as additional DynClasses
  |   - Replays queued TXs from #waiting (the original ATTACH)
  |   - DynClass.call('READ', {}) triggers data fetch
  v
DynClass "Product" receives replayed ATTACH
  | DynClass.ATTACH() -> adds list as watcher
  |
  | Meanwhile, DynClass.call('READ') sends:
  | TX { READ, source: Product, target: http://...8000/products, meta: {remote:true} }
  v
NetworkAdapter -> HTTP.get(.../products) -> backend returns [{id:1,...}, ...]
  | httpCallback: name stays READ (no meta.inbox override here)
  | TX { READ, source: http://...8000/products, target: Product, data: [...] }
  v
DynClass.READ(data):
  | Creates N3TX instances for each record, stores in DynClass.instances
  | Replays any _pendingAttaches
  | Notifies all watchers (the list)
  | TX { UPDATE, source: Product, target: <list-addr>, data: ["Product/1","Product/2",...] }
  v
ListElement.UPDATE(data):
  | this.value = array of address strings
  | this.render() creates child elements via createChild(addr), sets el.ref = "Product/1"
  |   (child resolution: template > item-tag attr > childTag property > schema hint > 'ntx-item')
  v
NTTItem.ref setter (inherited from Component):
  | TX { ATTACH, source: <item-addr>, target: N3TX, data: "Product/1" }
  v
N3TX.ATTACH() -> "Product" exists in #prototypes -> forwards to DynClass
  | DynClass.ATTACH() -> instance-level -> forwards to N3TX instance
  |
  | N3TX instance ATTACH():
  |   - this.watch(item-addr, false)
  |   - TX { DESCRIBE, source: 1, target: <item-addr>, data: {proto: schema, data: values} }
  v
NTTItem.DESCRIBE(data) (inherited from NTTElement):
  | this.schema = data.proto
  | this.value = data.data
  | this.render() -> Formidable.getForm({schema, value}, mode) -> HTML card
  |   (respects field_order, groups, widget hints, validation, field exclusion)
```

---

## Navigation Flow

When a user clicks a product card to navigate to a detail view:

```
User clicks card (not on interactive element)
  |
  | NTTItem.#bindEvents() click handler fires
  | Reads select-target attribute → list's addr
  | TX { SELECT, source: item-addr, target: list-addr, data: "Product/3" }
  v
ListElement.SELECT(data):
  | this.toggle("Product/3") → adds to #selected Set
  | Reads router attribute → "main"
  | TX { NAVIGATE, source: list-addr, target: "main", data: "Product/3" }
  v
Matrix.inbox() → routes to Router actor "main"
  |
  | Router.NAVIGATE("Product/3"):
  |   - Push current (null) onto #stack
  |   - Set #current = "Product/3"
  |   - Update location.hash = "Product/3"
  |   - notify('route', "Product/3", null)
  v
NTTRouter observes 'route' → render()
  |
  | #mountView("Product/3"):
  |   - Resolve tag: schema.ui.renderer.detail || 'ntx-item'
  |   - Build chrome: back button + title "Product"
  |   - Create <ntx-item ref="Product/3">
  |   - Mount in shadow DOM .router-content
  v
NTTItem resolves ref="Product/3" → ATTACH → DESCRIBE → render()
```

Going back:

```
User clicks back button (or browser back)
  |
  | TX { BACK, source: router-addr, target: "main" }
  v
Router.BACK():
  | Pop #stack → null
  | Set #current = null
  | Clear location.hash
  | notify('route', null, "Product/3")
  v
NTTRouter observes 'route' → render()
  |
  | #showSlot():
  |   - Remove dynamic view element
  |   - Restore <slot></slot>
  |   - Light DOM <ntx-list> re-projects instantly (no re-fetch)
```

---

## Current Status

**Working — Core:**
- Actor base class with subclass() metaclass, hierarchical routing, mixin system
- Matrix as root actor with NetworkAdapter bridge to N3TX backend
- Router: pure navigation state Actor with history stack, hash sync, Observable
- N3TX type registry with null-pointer bootstrap, universal ATTACH router, SSR pre-loading
- DynClass generation via `prototype()` with typed properties and methods
- Observable mixin (signal/observe/notify) applied to N3TX, DynClass, and Router
- TX message envelope with hash, serialization, event type subclasses

**Working — Component Layer (refactored):**
- Unified Component base class: Actor bridge + Shadow DOM + schema resolution + adaptive display (xs–xl) + stylesheet hook
- Adaptive display: abstract sizes (`xs`–`xl`) with semantic aliases (`pill`, `card`, etc.), forced mode via `display` attribute, ResizeObserver auto-mode
- NTTElement (entity base): UPDATE/DESCRIBE/READ handlers, save(), auto-render on value change
- ListElement (collection base): subscribe to proto, UPDATE handler, SELECT handler, selection API (Set-based), child resolution chain, size cascade
- NTTItem (built-in default): size methods (`xs`–`xl`) return HTML, `render()` dispatches + binds events, click-to-select, heuristic field selection via `#topFields()`
- NTTList (built-in default): 19-line thin shell over ListElement
- NTTRouter: generic view container, loads any component dynamically via Router, slot persistence for instant back-navigation

**Working — Schema-Driven Primitives:**
- `__ui__` ClassVar: field ordering, groups, renderer hints injected into schema
- Per-field UI hints via `json_schema_extra`: widget, placeholder, display
- Field exclusion conventions: `*_id`, `id`, timestamps auto-hidden
- Schema-driven validation: HTML5 attrs from minLength/maxLength/min/max/pattern/required
- Widget rendering: textarea, currency (with format), placeholder
- Grouped fields: `<fieldset>` with `<legend>` per schema group
- Relationship rendering: schema-aware child tags, count badge, collapse/expand
- Scaffolding: CLI (`python -m utils.scaffold`) + API (`?scaffold=item`) generates starter components

**Working — SSR Pre-Loading:**
- Inline `<script data-ntx-schema="Model">` consumed before network fetch
- Inline `<script data-ntx-data="tablename">` consumed after DynClass creation
- Eliminates both network round-trips for server-rendered pages

**WIP / Incomplete:**
- N3TX constructor has most initialization commented out (detach, meta, observer setup)
- Adaptive display schema integration (§8 phase 3): backend `__ui__.display_modes` for per-mode field selection — frontend heuristic (`#topFields`) works now, schema override not yet consumed
- `lg` and `xl` size methods delegate to `md` — future: show normally-hidden fields, expanded metadata
- Debug logging throughout (console.warn, console.error) not cleaned up
- example.html references old architecture and is broken against the current version
- No automated tests exist; testing is manual via browser + console

---

## Upcoming: Backend Actor Bridge

<a id="upcoming-backend-actor-bridge"></a>

The v0.8 backend introduces a Python-side Actor/Matrix/TX messaging system that mirrors the frontend's architecture. Backend actors communicate via the same TX message envelope (`name`, `source`, `target`, `data`, `meta`) and route through a backend Matrix.

**Wave 3 (planned):** A WebSocket bridge will connect frontend actors to backend actors, enabling bidirectional real-time messaging across the stack. The frontend `Socket.js` transport and the backend's Actor system will share a common TX protocol, allowing:

- Backend actors to push updates to frontend components without polling
- Frontend actors to send messages to specific backend actors by address
- Cross-stack actor hierarchies where backend and frontend actors participate in the same routing tree

**No frontend changes are needed until Wave 3.** The current HTTP transport continues to work as-is. When the WebSocket bridge ships, `NetworkAdapter` will gain a mode switch to route TX messages over WebSocket instead of HTTP, with automatic fallback. The frontend Actor/Matrix system is already designed for this -- `Socket.js` exists and handles reconnection, heartbeat, and message queuing. The missing piece is the backend-side WebSocket endpoint and the TX serialization bridge between Python and JavaScript actors.
