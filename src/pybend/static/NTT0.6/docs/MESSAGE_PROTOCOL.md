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
  -> child.inbox(tx)       (child is usually a Class: PTT, Component, NTT, etc.)

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

Triggered when a component sets its `model` attribute or when `PTT.get(addr)` is called for an unknown model.

```
Step 1: Component or code triggers PTT lookup
  TX { name: ATTACH, source: <requester>, target: PTT, data: "Product" }
  -> Matrix routes to PTT (static class)
  -> PTT.ATTACH() checks #prototypes

Step 2: PTT not found, create and pull
  new PTT("Product", "http://localhost:8000/Product")
  PTT.pull() sends:
  TX { name: SCHEMA, source: Product, target: http://localhost:8000/Product, meta: {remote:true} }
  -> Matrix can't resolve URL -> NetworkAdapter.send()
  -> HTTP GET http://localhost:8000/Product
  -> Backend returns JSON schema

Step 3: Response routed back
  NetworkAdapter.httpCallback() creates:
  TX { name: SCHEMA, source: http://localhost:8000/Product, target: Product, data: <schema> }
  -> Matrix routes to PTT instance "Product"

Step 4: PTT processes schema
  PTT.SCHEMA(data):
    - this.href = "http://localhost:8000/products"  (from __tablename__)
    - this.value = data  (triggers prototype() class generation)
    - Registers $defs as sub-PTTs
    - signal() fires all pending callbacks

Step 5: Requester notified
  PTT registers watcher -> sends UPDATE to requester
  Or: signal() fires define() callback on the component
```

---

## Protocol: List Rendering

Triggered after schema discovery completes and a List component's `definedCallback()` fires.

```
Step 1: List requests data
  List.definedCallback():
    this.proto.call('READ', {}, {inbox: 'UPDATE'})
  TX { name: READ, source: Product, target: http://localhost:8000/products, meta: {remote:true, inbox:'UPDATE'} }

Step 2: Backend responds
  HTTP GET /products -> returns [{id:1, name:"Keyboard", ...}, ...]
  httpCallback: name becomes 'UPDATE' (from meta.inbox)
  TX { name: UPDATE, source: http://.../products, target: Product, data: [...] }

Step 3: PTT processes response
  Because name is UPDATE, but target resolves to PTT instance:
  PTT.inbox -> Actor._inbox dispatches PTT.READ(data) -- actually the
  routing sends UPDATE but PTT processes via READ since the httpCallback
  swaps and name is set from meta.inbox.

  Note: There is an impedance mismatch here. The meta.inbox='UPDATE'
  changes the response event name, but the PTT handler is READ().
  In practice, PTT.READ() runs when the response targets the PTT addr.

  PTT.READ(data):
    For each item in array:
      - Creates new DynamicClass(item) -> NTT instance
      - Stores in PTT.#instances
    Calls this.notify(childAddresses)
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
  TX { name: ATTACH, source: <item-addr>, target: "Product/1" }

Step 2: Routes to NTT instance
  Matrix -> PTT children? No -> resolves through NTT or dynamic class children
  Eventually reaches the NTT instance with addr "1" (child of dynamic "Product" class)

  NTT.ATTACH(data, tx):
    this.watch(tx.source, false)   // Register item as watcher, no immediate push
    TX { name: DESCRIBE, source: 1, target: <item-addr>,
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
PTT.call('CREATE', entityData)
TX { name: CREATE, source: Product, target: http://localhost:8000/products, data: {...} }
-> NetworkAdapter -> HTTP POST /products
-> Response routed back as TX to PTT
```

### Read (single)

```
ntt.pull()
TX { name: READ, source: <ntt-addr>, target: http://localhost:8000/products/<id> }
-> HTTP GET /products/<id>
-> Response updates NTT instance
```

### Update

```
ntt.call('UPDATE', updatedData)
TX { name: UPDATE, source: <ntt-addr>, target: http://localhost:8000/products/<id>, data: {...} }
-> HTTP PUT /products/<id>
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
// DynamicClass prototype method calls:
TX { name: comment, source: <ntt-addr>, target: http://localhost:8000/products/<id> }
-> NetworkAdapter: unrecognized name -> HTTP POST /products/<id>/comment
```

---

## Message Reference Table

| Name | Direction | Source | Target | Data | Handler |
|------|-----------|--------|--------|------|---------|
| `ATTACH` | Component -> PTT (static) | component addr | `"PTT"` | model name string | `PTT.ATTACH()` |
| `ATTACH` | Component -> NTT instance | component addr | instance addr | - | `NTT.ATTACH()` / `TT.ATTACH()` |
| `SCHEMA` | PTT -> Backend | PTT addr | backend URL | `{}` | NetworkAdapter (HTTP GET) |
| `SCHEMA` | Backend -> PTT | backend URL | PTT addr | JSON schema | `PTT.SCHEMA()` |
| `READ` | PTT -> Backend | PTT addr | backend URL | `{}` | NetworkAdapter (HTTP GET) |
| `READ` | Backend -> PTT | backend URL | PTT addr | array of entities | `PTT.READ()` |
| `UPDATE` | PTT -> watchers | PTT addr | watcher addr | array of child addresses | `List.UPDATE()` / `Item.UPDATE()` |
| `DESCRIBE` | NTT -> Component | NTT addr | component addr | `{proto: schema, data: values}` | `Item.DESCRIBE()` |
| `CONNECT` | Component -> NTT type | component addr | type name | - | `Matrix.connect()` |
| `CREATE` | PTT -> Backend | PTT addr | backend URL | entity data | NetworkAdapter (HTTP POST) |
| `DELETE` | NTT -> Backend | NTT addr | backend URL | - | NetworkAdapter (HTTP DELETE) |
| `ERROR` | NetworkAdapter -> source | backend URL | original source | error details | `TT._error_()` |
