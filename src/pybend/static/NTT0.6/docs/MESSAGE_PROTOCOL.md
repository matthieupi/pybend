# Message Protocol Reference

All communication in NTT 0.6 happens via TX messages routed through the Actor hierarchy. This document describes every message type, who sends it, who handles it, and what happens.

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
  -> child.inbox(tx)       (child is usually a Class: NTT, Component, DynClass, etc.)

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

Triggered when a component sets its `model` attribute or when `NTT.attach(addr, callback)` is called for an unknown model.

```
Step 1: Component or code triggers NTT lookup
  TX { name: ATTACH, source: <requester>, target: NTT, data: "Product" }
  -> Matrix routes to NTT (static class)
  -> NTT.ATTACH() checks #prototypes

Step 2: Model never seen (undefined) — null pointer bootstrap
  NTT.#prototypes.set("Product", null)     // Mark as "schema in flight"
  NTT.#waiting.set("Product", [tx])        // Queue the original TX
  Dispatches:
  TX { name: SCHEMA, source: NTT, target: http://localhost:8000/Product, meta: {remote:true} }
  -> Matrix can't resolve URL -> NetworkAdapter.send()
  -> HTTP GET http://localhost:8000/Product
  -> Backend returns JSON schema

Step 3: Response routed back
  NetworkAdapter.httpCallback() creates:
  TX { name: SCHEMA, source: http://localhost:8000/Product, target: NTT, data: <schema> }
  -> Matrix routes to NTT (static)

Step 4: NTT processes schema — DynClass created
  NTT.SCHEMA(data):
    - Registers any $defs nested schemas as additional DynClasses
    - Calls prototype(addr, schema, href) -> creates DynClass "Product"
    - Stores DynClass in #prototypes["Product"]
    - Replays all queued TXs and callbacks from #waiting["Product"]
    - Calls DynClass.call('READ', {}) to trigger initial data fetch

Step 5: Requester receives the replayed ATTACH
  The original ATTACH TX is replayed to DynClass.ATTACH()
  -> DynClass adds requester as a watcher
  -> If using NTT.attach() with callback, DynClass.signal(callback) fires
```

---

## Protocol: List Rendering

Triggered after schema discovery completes and a List component's watcher/callback kicks in.

```
Step 1: DynClass fetches data
  DynClass.call('READ', {})
  TX { name: READ, source: Product, target: http://localhost:8000/products }

Step 2: Backend responds
  HTTP GET /products -> returns [{id:1, name:"Keyboard", ...}, ...]
  httpCallback: swaps source/target
  TX { name: READ, source: http://.../products, target: Product, data: [...] }

Step 3: DynClass processes response
  DynClass.READ(data):
    For each item in array:
      - Creates new DynClass(item) -> NTT instance
      - Stores in DynClass.instances
    Replays any _pendingAttaches (instance ATTACHes that arrived before READ)
    Notifies all watchers with instance addresses:
    TX { name: UPDATE, source: Product, target: <list-addr>, data: ["Product/1","Product/2",...] }

Step 4: List renders
  List.UPDATE(data):
    this.value = data (array of address strings)
    this.render():
      For each address string:
        const el = document.createElement('ntt-item')
        el.ref = address
        shadowRoot.appendChild(el)
```

---

## Protocol: Item Rendering

Triggered when a List sets `el.ref` on an `<ntt-item>`.

```
Step 1: Item sends ATTACH
  Item.ref setter:
  TX { name: ATTACH, source: <item-addr>, target: NTT, data: "Product/1" }

Step 2: Routes through NTT to DynClass to instance
  NTT.ATTACH() -> "Product" exists in #prototypes -> forwards to DynClass
  DynClass.ATTACH() -> addr contains "/" -> instance-level
    -> Looks up instance "1" in DynClass.children
    -> Forwards TX to instance inbox

  NTT instance ATTACH(data, tx):
    this.watch(tx.source, false)   // Register item as watcher, no immediate push
    TX { name: DESCRIBE, source: this.addr, target: <item-addr>,
         data: { proto: this.constructor._schema, data: this.value } }

Step 3: Item receives DESCRIBE
  Item.DESCRIBE(data):
    this.schema = data.proto    // JSON schema
    this.value = data.data      // Entity data {id, name, price, ...}
    this.render()               // Formidable generates HTML form
```

---

## Protocol: Entity CRUD

### Create

```
DynClass.call('CREATE', entityData)
TX { name: CREATE, source: Product, target: http://localhost:8000/products, data: {...} }
-> NetworkAdapter -> HTTP POST /products
-> Response routed back to DynClass
```

### Read (single)

```
ntt.pull()
TX { name: READ, source: <ntt-addr>, target: http://localhost:8000/products/<id> }
-> HTTP GET /products/<id>
-> Response updates NTT instance
```

**Note: FK Hydration.** Read responses may contain collection fields as href
arrays instead of embedded objects. For example, a Product's `comments` field
returns `["http://localhost:5000/products/1/comments/1", ...]` rather than
inline Comment objects. Each href is independently resolvable via GET.

### Update

```
ntt.call('UPDATE', updatedData)
TX { name: UPDATE, source: <ntt-addr>, target: http://localhost:8000/products/<id>, data: {...} }
-> HTTP PUT /products/<id>
```

Or via optimistic update flow (from UI save):
```
Item sends: TX { UPDATE, target: "Product/1", data: {...} }
-> Routes to NTT instance
-> NTT.UPDATE(): updates local data, then forwards to backend
-> TX { UPDATE, target: http://.../products/1, data: {...} }
-> HTTP PUT
```

### Delete

```
ntt.call('DELETE', {})
TX { name: DELETE, source: <ntt-addr>, target: http://localhost:8000/products/<id> }
-> HTTP DELETE /products/<id>
```

### Custom Method (e.g., comment)

```
ntt.comment({name: "Great!", description: "..."})
// DynClass prototype method calls:
TX { name: comment, source: <ntt-addr>, target: http://localhost:8000/products/<id> }
-> NetworkAdapter: unrecognized name -> HTTP POST /products/<id>/comment
```

---

## Message Reference Table

| Name | Direction | Source | Target | Data | Handler |
|------|-----------|--------|--------|------|---------|
| `ATTACH` | Component -> NTT (static) | component addr | `"NTT"` | model name string (e.g., `"Product"`) or instance addr (e.g., `"Product/1"`) | `NTT.ATTACH()` -> forwards to DynClass |
| `ATTACH` | NTT -> DynClass | (forwarded) | DynClass addr | model or instance addr | `DynClass.ATTACH()` |
| `ATTACH` | DynClass -> NTT instance | (forwarded) | instance addr | - | `NTT.ATTACH()` (instance method) |
| `SCHEMA` | NTT -> Backend | `"NTT"` | backend URL | `{}` | NetworkAdapter (HTTP GET) |
| `SCHEMA` | Backend -> NTT | backend URL | `"NTT"` | JSON schema | `NTT.SCHEMA()` |
| `READ` | DynClass -> Backend | DynClass addr | backend URL | `{}` | NetworkAdapter (HTTP GET) |
| `READ` | Backend -> DynClass | backend URL | DynClass addr | array of entities | `DynClass.READ()` |
| `UPDATE` | DynClass -> watchers | DynClass addr | watcher addr | array of child addresses | `List.UPDATE()` / `Item.UPDATE()` |
| `DESCRIBE` | NTT instance -> Component | NTT addr | component addr | `{proto: schema, data: values}` | `Item.DESCRIBE()` |
| `CONNECT` | Component -> Matrix | component addr | type name | - | `Matrix.connect()` |
| `CREATE` | DynClass -> Backend | DynClass addr | backend URL | entity data | NetworkAdapter (HTTP POST) |
| `UPDATE` | NTT instance -> Backend | NTT addr | backend URL | entity data | NetworkAdapter (HTTP PUT) |
| `DELETE` | NTT instance -> Backend | NTT addr | backend URL | - | NetworkAdapter (HTTP DELETE) |
| `ERROR` | NetworkAdapter -> source | backend URL | original source | error details | `TT._error_()` |
