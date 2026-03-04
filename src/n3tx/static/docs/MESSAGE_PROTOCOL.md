# Message Protocol Reference

All communication in N3TX happens via TX messages routed through the Actor hierarchy. This document describes every message type, who sends it, who handles it, and what happens.

## Table of Contents

1. [Message Format](#message-format)
2. [Routing Rules](#routing-rules)
3. [Protocol: Schema Discovery](#protocol-schema-discovery)
4. [Protocol: List Rendering](#protocol-list-rendering)
5. [Protocol: Item Rendering](#protocol-item-rendering)
6. [Protocol: Entity CRUD](#protocol-entity-crud)
7. [Message Reference Table](#message-reference-table)

---

## Message Format

Every message is a TX object (or plain object with the same fields):

```javascript
{
  name:   "EVENT_NAME",       // Method to invoke on the target
  source: "sender-address",   // Who sent this
  target: "receiver-address", // Who should receive this
  data:   { ... },            // Payload (any type)
  meta:   { ... },            // Metadata (remote flag, inbox override, etc.)
  tst:    1702000000000,      // Timestamp
  hash:   "abc123"            // Deterministic content hash
}
```

### Key meta fields

| Field | Type | Description |
|-------|------|-------------|
| `remote` | `bool` | If true, NetworkAdapter originated this or should send it remotely. |
| `inbox` | `string` | Override: when the response comes back, use this as the event name instead of the original. |

---

## Routing Rules

Messages flow through a hierarchy. Each actor's `send()` tries to resolve the target locally, then bubbles up.

### 1. Actor static routing (`Actor._send`)

```
Parse target into segments: [parent, child, ...]

IF parent is in this.children:
  -> child.inbox(tx)

ELSE IF parent === this.addr:
  -> Look up children[child].inbox(tx)

ELSE:
  -> Prefix source with this.addr
  -> ROOT_ACTOR.inbox(tx)   (bubble to Matrix)
```

### 2. Matrix routing (`Matrix.inbox`)

```
IF name === CONNECT:
  -> matrix.connect(source, target)

ELSE IF first segment of target is in matrix.children:
  -> child.inbox(tx)       (child is usually a Class: N3TX, Component, DynClass, etc.)

ELSE:
  -> matrix.remote.send(tx)  (forward to backend via NetworkAdapter)
```

### 3. NetworkAdapter routing (`NetworkAdapter.send`)

Maps event names to HTTP methods:

| TX name | HTTP method | URL |
|---------|-------------|-----|
| SCHEMA | GET | `{target}` |
| READ | GET | `{target}` |
| CREATE | POST | `{target}` |
| UPDATE | PUT | `{target}` |
| DELETE | DELETE | `{target}` |
| (other) | POST | `{target}/{name}` |

On response: swaps source/target, sets `name = meta.inbox || original name`, dispatches back through `matrix.dispatch()`.

---

## Protocol: Schema Discovery

Triggered when a component sets its `model` attribute or when `N3TX.attach(addr, callback)` is called for an unknown model.

```
Step 1: Component or code triggers N3TX lookup
  TX { name: ATTACH, source: <requester>, target: N3TX, data: "Product" }
  -> Matrix routes to N3TX (static class)
  -> N3TX.ATTACH() checks #prototypes

Step 2: Model never seen (undefined) — null pointer bootstrap
  N3TX.#prototypes.set("Product", null)     // Mark as "schema in flight"
  N3TX.#waiting.set("Product", [tx])        // Queue the original TX
  Dispatches:
  TX { name: SCHEMA, source: N3TX, target: http://localhost:8000/Product, meta: {remote:true} }
  -> Matrix can't resolve URL -> NetworkAdapter.send()
  -> HTTP GET http://localhost:8000/Product
  -> Backend returns JSON schema

Step 3: Response routed back
  NetworkAdapter.httpCallback() creates:
  TX { name: SCHEMA, source: http://localhost:8000/Product, target: N3TX, data: <schema> }
  -> Matrix routes to N3TX (static)

Step 4: N3TX processes schema — DynClass created
  N3TX.SCHEMA(data):
    - Registers any $defs nested schemas as additional DynClasses
    - Calls prototype(addr, schema, href) -> creates DynClass "Product"
    - Stores DynClass in #prototypes["Product"]
    - Replays all queued TXs and callbacks from #waiting["Product"]
    - Calls DynClass.call('READ', {}) to trigger initial data fetch

Step 5: Requester receives the replayed ATTACH
  The original ATTACH TX is replayed to DynClass.ATTACH()
  -> DynClass adds requester as a watcher
  -> If using N3TX.attach() with callback, DynClass.signal(callback) fires
```

---

## Protocol: List Rendering

Triggered after schema discovery completes and a List component's watcher/callback kicks in.

```
Step 1: DynClass fetches data (paginated)
  DynClass.call('READ', { limit: 20, offset: 0 }, { inbox: 'UPDATE' })
  TX { name: READ, source: Product, target: http://localhost:8000/products,
       data: { limit: 20, offset: 0 }, meta: { inbox: 'UPDATE' } }

Step 2: NetworkAdapter encodes data as query params for READ
  HTTP GET /products?limit=20&offset=0
  Backend returns: { data: [{id:1, ...}, ...], meta: { total, limit, offset, has_more } }

Step 3: httpCallback swaps source/target, uses meta.inbox as event name
  TX { name: UPDATE, source: http://.../products, target: Product,
       data: { data: [...], meta: {...} } }

Step 4: DynClass processes response
  DynClass.READ(data):
    Detects paginated shape: { data: Array, meta: Object }
      -> Stores meta as DynClass._paginationMeta
      -> Extracts data array for processing
    For each item in array:
      - Creates new DynClass(item) -> N3TX instance
      - Stores in DynClass.instances
    Replays any _pendingAttaches (instance ATTACHes that arrived before READ)
    Notifies all watchers with instance addresses:
    TX { name: UPDATE, source: Product, target: <list-addr>, data: ["Product/1","Product/2",...] }

Step 5: List renders
  List.UPDATE(data):
    this.value = data (array of address strings)
    this.render():
      Reads this.proto._paginationMeta for count/total display
      For each address string:
        const el = document.createElement('ntx-item')
        el.ref = address
        shadowRoot.appendChild(el)
      If has_more: renders "Load More" button → loadMore() → READ with offset += pageSize
```

---

## Protocol: Item Rendering

Triggered when a List sets `el.ref` on an `<ntx-item>`.

```
Step 1: Item sends ATTACH
  Item.ref setter:
  TX { name: ATTACH, source: <item-addr>, target: N3TX, data: "Product/1" }

Step 2: Routes through N3TX to DynClass to instance
  N3TX.ATTACH() -> "Product" exists in #prototypes -> forwards to DynClass
  DynClass.ATTACH() -> addr contains "/" -> instance-level
    -> Looks up instance "1" in DynClass.children
    -> Forwards TX to instance inbox

  N3TX instance ATTACH(data, tx):
    this.watch(tx.source, false)   // Register item as watcher, no immediate push
    TX { name: DESCRIBE, source: this.addr, target: <item-addr>,
         data: { proto: this.constructor._schema, data: this.value } }

Step 3: Item receives DESCRIBE
  Item.DESCRIBE(data):
    this.schema = data.proto    // JSON schema
    this.value = data.data      // Entity data {id, name, price, ...}
    // value setter auto-renders when schema is available
```

---

## Protocol: Entity CRUD

### Create

```
DynClass.call('CREATE', entityData)
TX { name: CREATE, source: Product, target: http://localhost:8000/products, data: {...} }
-> NetworkAdapter -> HTTP POST /products
-> Response routed back to DynClass

DynClass.CREATE(data):
  If instance doesn't exist → creates new DynClass(data), adds to instances map
  If instance exists → updates with new data
  Re-notifies all watchers with updated address list
  → Lists automatically show the new entity
```

### Read (single)

```
ntt.pull()
TX { name: READ, source: <ntx-addr>, target: http://localhost:8000/products/<id> }
-> HTTP GET /products/<id>
-> Response updates N3TX instance
```

**Note: FK Hydration.** Read responses may contain collection fields as href
arrays instead of embedded objects. For example, a Product's `comments` field
returns `["http://localhost:5000/products/1/comments/1", ...]` rather than
inline Comment objects. Each href is independently resolvable via GET.

### Update

```
ntt.call('UPDATE', updatedData)
TX { name: UPDATE, source: <ntx-addr>, target: http://localhost:8000/products/<id>, data: {...} }
-> HTTP PUT /products/<id>
```

Or via optimistic update flow (from UI save):
```
Item sends: TX { UPDATE, target: "Product/1", data: {...} }
-> Routes to N3TX instance
-> N3TX.UPDATE(): updates local data, then forwards to backend
-> TX { UPDATE, target: http://.../products/1, data: {...} }
-> HTTP PUT
```

### Delete

```
Step 1: NTTItem sends DELETE TX (routed through DynClass)
  Item.deleteItem():
    Checks permissions.canAction(schema.access, 'delete', this.value)  ← resource-aware OWNER check
    Shows confirm() dialog
    Resolves target: uses ref (API endpoint URL) for nested entities, falls back to $id
    Routes through DynClass (not directly to backend):
    DC.send(TX { name: DELETE, target: <api-url>, meta: { inbox: 'DELETE' } })

Step 2: NetworkAdapter sends HTTP DELETE
  HTTP DELETE /products/<id>  (no request body)
  Backend returns: { message: "Deleted successfully" }

Step 3: httpCallback routes response back to DynClass
  TX { name: DELETE, source: <api-url>, target: DynClass,
       data: { message: "Deleted successfully" } }

Step 4: DynClass.DELETE handler cleans up
  DynClass.DELETE(data, tx):
    Parses entity ID from tx.source URL → removes from DynClass.instances
    Re-notifies all watchers with updated address list:
    TX { name: UPDATE, source: Product, target: <list-addr>, data: [remaining addresses] }

Step 5: ListElement re-renders
  List.UPDATE() → render() — deleted item no longer in list
```

### Custom Method (e.g., comment)

```
ntt.comment({name: "Great!", description: "..."})
// DynClass prototype method calls:
TX { name: comment, source: <ntx-addr>, target: http://localhost:8000/products/<id>,
     meta: { inbox: '_response_' } }
-> NetworkAdapter: unrecognized name -> HTTP POST /products/<id>/comment
-> Response routed back to N3TX instance

Instance._response_(data):
  this.pull()  → re-fetches entity from backend
  → Entity signal fires → watching NTTElement components auto-update
  → No manual setTimeout needed
```

---

## Protocol: Navigation

Triggered when a user clicks an item in a list that has a `router` attribute.

```
Step 1: User clicks a product card
  NTTItem.#bindEvents() click handler fires
  Reads select-target attribute → list's addr
  TX { name: SELECT, source: <item-addr>, target: <list-addr>, data: "Product/3" }

Step 2: List handles selection and forwards to Router
  ListElement.SELECT("Product/3"):
    this.toggle("Product/3") → adds to #selected Set
    Reads router attribute → "main"
  TX { name: NAVIGATE, source: <list-addr>, target: "main", data: "Product/3" }

Step 3: Matrix routes to Router actor
  Router.NAVIGATE("Product/3"):
    Push current (null) onto #stack
    Set #current = "Product/3"
    Update location.hash = "Product/3"
    notify('route', "Product/3", null)

Step 4: NTTRouter observes route change
  NTTRouter.render():
    #mountView("Product/3"):
      Resolve tag from schema → 'ntx-item'
      Build chrome (back button + title "Product")
      Create <ntx-item ref="Product/3">
      Mount in shadow DOM .router-content

Step 5: Mounted item resolves data
  NTTItem ref="Product/3" → ATTACH → DESCRIBE → render()
```

### Going Back

```
Step 1: User clicks back button (or browser back)
  TX { name: BACK, source: <router-component-addr>, target: "main" }

Step 2: Router pops stack
  Router.BACK():
    Pop #stack → null
    Set #current = null
    Clear location.hash
    notify('route', null, "Product/3")

Step 3: NTTRouter restores slot
  NTTRouter.render():
    #showSlot():
      Remove dynamic view element
      Restore <slot></slot>
      Light DOM <ntx-list> re-projects instantly (no re-fetch)
```

---

## Message Reference Table

| Name | Direction | Source | Target | Data | Handler |
|------|-----------|--------|--------|------|---------|
| `ATTACH` | Component -> N3TX (static) | component addr | `"N3TX"` | model name string (e.g., `"Product"`) or instance addr (e.g., `"Product/1"`) | `N3TX.ATTACH()` -> forwards to DynClass |
| `ATTACH` | N3TX -> DynClass | (forwarded) | DynClass addr | model or instance addr | `DynClass.ATTACH()` |
| `ATTACH` | DynClass -> N3TX instance | (forwarded) | instance addr | - | `N3TX.ATTACH()` (instance method) |
| `SCHEMA` | N3TX -> Backend | `"N3TX"` | backend URL | `{}` | NetworkAdapter (HTTP GET) |
| `SCHEMA` | Backend -> N3TX | backend URL | `"N3TX"` | JSON schema | `N3TX.SCHEMA()` |
| `READ` | DynClass -> Backend | DynClass addr | backend URL | `{}` | NetworkAdapter (HTTP GET) |
| `READ` | Backend -> DynClass | backend URL | DynClass addr | array of entities | `DynClass.READ()` |
| `UPDATE` | DynClass -> watchers | DynClass addr | watcher addr | array of child addresses | `List.UPDATE()` / `Item.UPDATE()` |
| `DESCRIBE` | N3TX instance -> Component | N3TX addr | component addr | `{proto: schema, data: values}` | `Item.DESCRIBE()` |
| `CONNECT` | Component -> Matrix | component addr | type name | - | `Matrix.connect()` |
| `CREATE` | DynClass -> Backend | DynClass addr | backend URL | entity data | NetworkAdapter (HTTP POST) |
| `CREATE` | Backend -> DynClass | backend URL | DynClass addr | created entity | `DynClass.CREATE()` — registers instance, notifies watchers |
| `UPDATE` | N3TX instance -> Backend | N3TX addr | backend URL | entity data | NetworkAdapter (HTTP PUT) |
| `DELETE` | NTTItem -> DynClass | DynClass addr | entity API URL (via `ref`) | - | Routed through DynClass to NetworkAdapter (HTTP DELETE, no body) |
| `DELETE` | Backend -> DynClass | entity URL | DynClass addr | `{message}` | `DynClass.DELETE()` — removes instance, re-notifies watchers |
| `_response_` | Backend -> N3TX instance | backend URL | instance addr | method result | `instance._response_()` — triggers `pull()` for live update |
| `SELECT` | NTTItem -> ListElement | item addr | list addr (via `select-target` attribute) | entity ref string (e.g., `"Product/3"`) | `ListElement.SELECT()` |
| `NAVIGATE` | ListElement -> Router | list addr | router addr (via `router` attribute) | route data (string or object) | `Router.NAVIGATE()` |
| `BACK` | NTTRouter -> Router | router component addr | router actor addr | (ignored) | `Router.BACK()` |
| `ERROR` | NetworkAdapter -> source | backend URL | original source | error details | `TT._error_()` |
