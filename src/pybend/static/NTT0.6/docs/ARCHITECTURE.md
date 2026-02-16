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
|  TT > PTT (schema proxy) > NTT (entity instance)        |
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
  |     +-- PTT                # Proto Transfer Type: schema proxy, dynamic class factory
  |     |
  |     +-- NTT                # Named Transfer Type: entity instance with data + proto link
  |           |
  |           +-- [Dynamic]    # Runtime-generated subclass per model (e.g. "Product")
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
- Optional mixin application (e.g., `Actor.subclass(PTT, Observable)`)

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
    NTT.js                   # TT, PTT, NTT classes + prototype() dynamic class factory
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
   - Actor.subclass(PTT, Observable)   -- PTT gets signal/observe/notify
   - Actor.subclass(NTT)
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
     - Sends TX { name: ATTACH, source: <list-addr>, target: PTT, data: "Product" }
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
  | TX { ATTACH, source: list-addr, target: PTT, data: "Product" }
  v
Matrix.inbox() -> routes to PTT (static)
  |
  | PTT.ATTACH() - no prototype exists yet
  | PTT.get("Product") creates new PTT("Product", "http://localhost:8000/Product")
  | PTT.pull() -> TX { SCHEMA, source: Product, target: http://...8000/Product, meta: {remote:true} }
  v
Matrix.inbox() -> target not local -> NetworkAdapter.send()
  |
  | HTTP.get("http://localhost:8000/Product") -> backend returns JSON schema
  v
NetworkAdapter.httpCallback() -> swaps source/target, sets name to SCHEMA
  | TX { SCHEMA, source: http://...8000/Product, target: Product, data: <schema> }
  v
Matrix.inbox() -> routes to PTT instance "Product"
  |
  | PTT.SCHEMA(data):
  |   - Sets this.value = schema
  |   - prototype(this) generates dynamic NTT subclass with typed properties
  |   - Registers any $defs models as PTTs
  |   - signal() fires -> list's define() callback runs
  v
List.definedCallback():
  | Calls this.proto.call('READ', {}, {inbox: 'UPDATE'})
  | TX { READ, source: Product, target: http://...8000/products, meta: {remote:true, inbox:'UPDATE'} }
  v
NetworkAdapter -> HTTP.get(.../products) -> backend returns [{id:1,...}, ...]
  | httpCallback swaps, name becomes UPDATE (from meta.inbox)
  | TX { UPDATE, source: http://...8000/products, target: Product, data: [...] }
  v
PTT.inbox -> PTT.READ(data):
  | Creates NTT instances for each record
  | Calls notify() -> sends UPDATE to all watchers (the list)
  | TX { UPDATE, source: Product, target: <list-addr>, data: ["Product/1","Product/2",...] }
  v
List.UPDATE(data):
  | this.value = array of address strings
  | this.render() creates <ntt-item> for each, sets el.ref = "Product/1"
  v
Item.ref setter:
  | TX { ATTACH, source: <item-addr>, target: "Product/1" }
  v
Matrix routes to NTT instance "1" (child of PTT "Product")
  |
  | NTT.ATTACH():
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
- PTT schema discovery from backend, dynamic class generation via prototype()
- Observable mixin (signal/observe/notify) applied to PTT and NTT
- TX message envelope with hash, serialization, event type subclasses
- Component base class integrated into Actor system
- NTTElement with model/schema/value binding, ref-based ATTACH protocol
- List rendering with UPDATE handler
- Item rendering with DESCRIBE handler and Formidable form generation

**WIP / Incomplete:**
- NTT constructor has most initialization commented out (detach, meta, observer setup)
- `<ntt-method>` rendering is commented out in Item.render()
- Array input rendering is commented out in form.js
- Component.connectedCallback() is empty (initial bootstrapping relies on attributeChangedCallback)
- Debug logging throughout (console.warn, console.error) not cleaned up
- example.html references old registrar architecture and is broken against v0.6
- No automated tests exist; testing is manual via browser + console
