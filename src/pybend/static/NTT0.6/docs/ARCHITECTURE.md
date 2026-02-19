# NTT 0.6 Architecture

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

NTT 0.6 is a browser-side runtime for building schema-driven UIs on top of the PyBend backend. It uses an **Actor model** for all inter-component communication: every entity in the system (data models, UI components, the network layer) is an Actor with an address, an inbox, and a send method. Messages flow through a central **Matrix** (root actor) that routes locally or forwards to the network.

The key design goals:
- **Schema-driven**: The backend defines models (via Pydantic/OpenAPI). The frontend pulls those schemas at runtime and generates typed entity classes dynamically.
- **Decoupled**: UI components never call HTTP directly. They send messages to data actors, which handle remote calls transparently.
- **Hierarchical routing**: Actors form a tree. Messages route through the tree, bubbling to the Matrix when the target is not a local child.

---

## System Layers

```
+----------------------------------------------------------+
|  UI Layer (Web Components)                               |
|  Component > NTTElement > List, Item, NTTMethod           |
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
|  TT > NTT (registry + entity base) > DynClass (per type)|
+-----------------------------+----------------------------+
                              |  TX messages with meta.remote
+-----------------------------v----------------------------+
|  Transport Layer                                         |
|  NetworkAdapter > HTTP / Socket                          |
+-----------------------------+----------------------------+
                              |  fetch() / WebSocket
+-----------------------------v----------------------------+
|  PyBend Backend (FastAPI)                                |
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
  +-- TT (Transfer Type)       # Actor with href (remote endpoint) + watcher/notify pattern
  |     |
  |     +-- NTT                # Type registry (static) + entity base class (instance)
  |           |
  |           +-- [DynClass]   # Runtime-generated subclass per model (e.g. "Product")
  |                 |
  |                 +-- instances  # Per-entity NTT instances (Product/1, Product/2, ...)
  |
  +-- Component (HTMLElement)  # Web component base, registered in Matrix
        |
        +-- NTTElement         # Component with model/schema/value binding
              |
              +-- List         # Renders a list of <ntt-item> elements
              |
              +-- Item         # Renders a single entity card with form fields

Observable                     # Mixin: signal(), observe(), notify() - applied via Actor.subclass()
```

All classes with `Actor.subclass(Class)` at the bottom of their module get:
- Static `addr`, `children`, `send`, `inbox`, `register`
- Instance `children`, `send`, `inbox`
- Optional mixin application (e.g., `Actor.subclass(NTT, Observable)`)

---

## Module Map

```
NTT0.6/
  config.js                  # API_URL, WS_URL, event name constants (config.E), debug flags
  core/
    Actor.js                 # Actor base class + subclass() metaclass helper
    Matrix.js                # Root actor singleton, message router
    TX.js                    # Transaction envelope (name, source, target, data, meta, hash)
    Observable.js            # Mixin: signal/observe/notify reactivity
    NTT.js                   # TT, NTT classes + prototype() DynClass factory
    Component.js             # HTMLElement + Actor base for web components
    Utils.js                 # generateId, simpleHash, isTypeCompatible, deepEqual, isUrl
    transport/
      NetworkAdapter.js      # Matrix's network bridge (HTTP/WS mode switching)
      HTTP.js                # Static fetch wrapper (get/post/put/remove)
      Socket.js              # WebSocket client with heartbeat, reconnect, message queue
  components/
    ntt-element.js           # NTTElement: base component with model/schema/value
    ntt-list.js              # List: renders <ntt-item> per entity
    ntt-item.js              # Item: renders entity card with form
    ntt-method.js            # NTTMethod: renders method invocation form
    *.css                    # Component styles
  generators/
    form.js                  # Formidable: schema-driven HTML form generator
  utils/
    Assert.js                # assert(), caution(), inform() with configurable trigger level
    Logging.js               # Logging with caller detection, styled console output
    Snippets.js, DateFormat.js, str_utils.js  # General utilities
  docs/                      # This documentation
```

---

## Initialization Sequence

When `matrix.html` loads:

```
1. Matrix.js executes
   - Actor.subclass(Matrix) wires static/instance methods
   - `new Matrix("matrix://root")` creates the singleton
   - Actor.registerRoot(matrix) sets it as the global message bus
   - Matrix creates a NetworkAdapter(this) for remote calls

2. NTT.js executes
   - Actor.subclass(TT)
   - Actor.subclass(NTT, Observable)   -- NTT gets signal/observe/notify
   - window.NTT = NTT exposed globally

3. Component.js executes
   - Actor.subclass(Component)
   - matrix.register(Component)  -- Component class registered as Matrix child

4. ntt-element.js, ntt-list.js, ntt-item.js execute
   - Actor.subclass(List)
   - customElements.define('ntt-list', List)
   - customElements.define('ntt-item', Item)
   - customElements.define('ntt-element', NTTElement)

5. Browser parses <ntt-list model="Product">
   - List constructor runs:
     - super() -> NTTElement -> Component -> HTMLElement
     - Component registers itself in Matrix and in Component.children
   - attributeChangedCallback fires for model="Product"
     - Sends TX { name: ATTACH, source: <list-addr>, target: NTT, data: "Product" }
```

---

## Data Flow Summary

See [MESSAGE_PROTOCOL.md](./MESSAGE_PROTOCOL.md) for the full message protocol.
See [ACTORS.md](./ACTORS.md) for detailed per-class documentation.

The primary data flow for rendering a list of entities:

```
<ntt-list model="Product">
  |
  | attributeChangedCallback("model", "Product")
  | TX { ATTACH, source: list-addr, target: NTT, data: "Product" }
  v
Matrix.inbox() -> routes to NTT (static)
  |
  | NTT.ATTACH() - "Product" not in #prototypes (undefined)
  | Sets #prototypes["Product"] = null (schema in flight)
  | Queues the ATTACH TX in #waiting
  | Dispatches: TX { SCHEMA, source: NTT, target: http://...8000/Product, meta: {remote:true} }
  v
Matrix.inbox() -> target not local -> NetworkAdapter.send()
  |
  | HTTP.get("http://localhost:8000/Product") -> backend returns JSON schema
  v
NetworkAdapter.httpCallback() -> swaps source/target, sets name to SCHEMA
  | TX { SCHEMA, source: http://...8000/Product, target: NTT, data: <schema> }
  v
Matrix.inbox() -> routes to NTT (static)
  |
  | NTT.SCHEMA(data):
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
  | Creates NTT instances for each record, stores in DynClass.instances
  | Replays any _pendingAttaches
  | Notifies all watchers (the list)
  | TX { UPDATE, source: Product, target: <list-addr>, data: ["Product/1","Product/2",...] }
  v
List.UPDATE(data):
  | this.value = array of address strings
  | this.render() creates <ntt-item> for each, sets el.ref = "Product/1"
  v
Item.ref setter:
  | TX { ATTACH, source: <item-addr>, target: NTT, data: "Product/1" }
  v
NTT.ATTACH() -> "Product" exists in #prototypes -> forwards to DynClass
  | DynClass.ATTACH() -> instance-level -> forwards to NTT instance
  |
  | NTT instance ATTACH():
  |   - this.watch(item-addr, false)
  |   - TX { DESCRIBE, source: 1, target: <item-addr>, data: {proto: schema, data: values} }
  v
Item.DESCRIBE(data):
  | this.schema = data.proto
  | this.value = data.data
  | this.render() -> Formidable.getForm({schema, value}) -> HTML card
```

---

## Current Status

**Working:**
- Actor base class with subclass() metaclass, hierarchical routing, mixin system
- Matrix as root actor with NetworkAdapter bridge to PyBend backend
- NTT type registry with null-pointer bootstrap and universal ATTACH router
- DynClass generation via `prototype()` with typed properties and methods
- Observable mixin (signal/observe/notify) applied to NTT and DynClass (both instance and static level)
- TX message envelope with hash, serialization, event type subclasses
- Component base class integrated into Actor system
- NTTElement with model/schema/value binding, ref-based ATTACH protocol
- List rendering with UPDATE handler
- Item rendering with DESCRIBE handler and Formidable form generation
- FK Hydration: collection fields (e.g., `comments`) return href arrays instead of embedded objects. Each href is independently resolvable via nested routes (`/tablename/:id/field/:child_id`).

**WIP / Incomplete:**
- NTT constructor has most initialization commented out (detach, meta, observer setup)
- `<ntt-method>` rendering is commented out in Item.render()
- Array input rendering is commented out in form.js
- Component.connectedCallback() is empty (initial bootstrapping relies on attributeChangedCallback)
- Debug logging throughout (console.warn, console.error) not cleaned up
- example.html references old architecture and is broken against v0.6
- No automated tests exist; testing is manual via browser + console
