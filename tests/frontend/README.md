# N3TXTX Framework — Quickstart & Developer Guide

> **Build schema-driven UIs with zero boilerplate.**
> Drop a `<ntx-list>` tag, point it at a model, and the framework handles
> schema discovery, data fetching, rendering, and CRUD — all via actors.

---

## TL;DR — From Zero to Rendered List

```html
<ntx-list model="Product"></ntx-list>

<script type="module">
    import { Matrix, matrix } from './core/Matrix.js';
    import { N3TX } from './core/N3TX.js';
    import { config } from './config.js';
    import './components/ntx-item.js';
    import './components/ntx-list.js';
</script>
```

That's it. The list auto-discovers the schema, fetches records, and renders
editable cards. **Everything below explains _why_ that works.**

---

## Table of Contents

1. [Mental Model — The Big Picture](#1-mental-model--the-big-picture)
2. [Setup](#2-setup)
3. [Your First Page](#3-your-first-page)
4. [Core Concepts](#4-core-concepts)
5. [The Actor System — How Messages Flow](#5-the-actor-system--how-messages-flow)
6. [Dataflow — Render Lifecycle (Step by Step)](#6-dataflow--render-lifecycle-step-by-step)
7. [CRUD Operations](#7-crud-operations)
8. [FK Hydration — Collection Fields as Hrefs](#8-fk-hydration--collection-fields-as-hrefs)
9. [Web Components API](#9-web-components-api)
10. [Custom Methods](#10-custom-methods)
11. [Building a Complete App](#11-building-a-complete-app)
12. [Message Protocol Cheat Sheet](#12-message-protocol-cheat-sheet)
13. [Configuration Reference](#13-configuration-reference)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Mental Model — The Big Picture

N3TXTX is an **actor-based** frontend runtime. Think of it as a post office
inside the browser: every piece of data, every UI component, and the network
layer are all **actors** with mailboxes. They communicate by sending
**TX messages** through a central router called the **Matrix**.

```
+-------------------------------------------------------------------+
|                        BROWSER                                     |
|                                                                    |
|   +-----------+     TX Messages     +-----------------------+      |
|   |   UI      | <=================> |      MATRIX           |      |
|   |  Layer    |   (ATTACH, UPDATE,  |   (Root Actor /       |      |
|   |           |    DESCRIBE, ...)   |    Message Router)     |      |
|   | <ntx-list |                     |                       |      |
|   | <ntx-item |                     |   children:           |      |
|   +-----------+                     |   +- N3TX (registry)   |      |
|                                     |   +- Product (DynClass)|     |
|                                     |   +- Component (UI)   |      |
|                                     |   +- ...              |      |
|                                     +----------+------------+      |
|                                                |                   |
|                                     +----------v-----------+       |
|                                     | NetworkAdapter       |       |
|                                     | (HTTP / WebSocket)   |       |
|                                     +----------+-----------+       |
+------------------------------------+-----------+-------------------+
                                     |  fetch() / WS
                                     +----------v-----------+
                                     |   N3TX Backend     |
                                     |   (FastAPI)          |
                                     |                      |
                                     |  GET /Product        | -> JSON Schema
                                     |  GET /products       | -> [{...}, ...]
                                     |  PUT /products/1     | -> Updated record
                                     +----------------------+
```

### Key Insight: Components Never Talk to the Network Directly

A `<ntx-item>` doesn't call `fetch()`. It sends a TX message to its N3TX actor,
which routes through the Matrix, hits the NetworkAdapter, and the response
flows back the same way. This decouples UI from transport entirely.

---

## 2. Setup

### 2.1 Backend

You need a N3TX backend running. The default port is `5000`:

```bash
cd your-project/
python3 main.py          # Starts FastAPI on http://localhost:5000
```

The backend auto-generates endpoints from your Pydantic models:

| Endpoint | Purpose |
|----------|---------|
| `GET /ModelName` | Returns JSON schema for the model |
| `GET /tablename` | Lists all records |
| `GET /tablename/:id` | Gets a single record |
| `POST /tablename` | Creates a record |
| `PUT /tablename/:id` | Updates a record |
| `DELETE /tablename/:id` | Deletes a record |
| `GET /tablename/:id/field/:child_id` | Gets a nested child record (FK hydration) |
| `GET /tablename/childtable` | Collection route — all children across parents |
| `POST /tablename/:id/method` | Custom method (toggle, comment, reply, etc.) |

> **Convention:** `/Product` (PascalCase) = schema. `/products` (lowercase plural from `__tablename__`) = CRUD.

### 2.2 Frontend Config

Edit `config.js` to point at your backend:

```js
export const config = {
    API_URL: 'http://localhost:5000',   // Backend base URL
    WS_URL:  'ws://localhost:8765',     // WebSocket (if using WS transport)
    LOGGING: 3,                         // 0=off, 1=errors, 2=warnings, 3=verbose
    DEBUG:   true,                      // Enable debug output
    // ...
};
```

### 2.3 Required Imports

Every N3TXTX page needs these module imports:

```js
import { Matrix, matrix } from './core/Matrix.js';  // Root actor (auto-initializes)
import { N3TX }            from './core/N3TX.js';      // Type registry + entity classes
import { config }         from './config.js';         // Configuration
import './components/ntx-item.js';                    // <ntx-item> web component
import './components/ntx-list.js';                    // <ntx-list> web component
```

> **Order matters.** Matrix must be imported first — it creates the singleton
> root actor that all other actors register into.

---

## 3. Your First Page

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>My N3TXTX App</title>
    <link rel="stylesheet" href="./dark-theme.css">
    <link rel="icon" type="image/svg+xml" href="./favicon.svg">
</head>
<body>

    <h1>Products</h1>
    <ntx-list model="Product"></ntx-list>

    <h1>Users</h1>
    <ntx-list model="User"></ntx-list>

    <script type="module">
        import { Matrix, matrix } from './core/Matrix.js';
        import { N3TX }            from './core/N3TX.js';
        import { config }         from './config.js';
        import './components/ntx-item.js';
        import './components/ntx-list.js';
    </script>

</body>
</html>
```

Each `<ntx-list>` independently:
1. Asks the backend for the model's JSON schema
2. Discovers the CRUD endpoint from `__tablename__`
3. Fetches all records
4. Renders editable `<ntx-item>` cards in a grid

---

## 4. Core Concepts

### The Four Pillars

```
+---------+    +-----------+    +---------+    +-------------+
|  Matrix  |    |    N3TX    |    |   TX    |    |  Component  |
|          |    |           |    |         |    |             |
|  Root    |    | Registry  |    | Message |    | Web Comp.   |
|  Actor   |    | + Entity  |    |Envelope |    | = Actor     |
|  Router  |    | Base      |    |         |    |             |
|          |    |           |    |         |    |             |
+---------+    +-----------+    +---------+    +-------------+
```

| Concept | What it is | Analogy |
|---------|-----------|---------|
| **Matrix** | Singleton root actor. Routes every TX message to the right place, or sends it to the backend. | The post office |
| **N3TX** | Named Transfer Type. Static level: type registry + universal ATTACH router. Instance level: per-entity data with `href` pointing at its backend URL. | A registry + data holder |
| **DynClass** | DynamicClass. One per model (e.g., `Product`). Runtime-generated N3TX subclass. Holds the JSON schema, manages entity instances, handles CRUD. Born complete — never half-initialized. | A typed class factory |
| **TX** | Transaction message. `{name, source, target, data, meta}`. Every interaction is a TX. | A letter in an envelope |
| **Component** | Web component base class that is also an Actor. Has `send()` and `inbox()`. | A mailbox-enabled HTML element |

### Actor Hierarchy

```
Matrix (root)
 +-- N3TX (class — type registry)
 +-- Product (DynClass — runtime-generated)
 |    +-- 1 (N3TX instance — Product/1)
 |    +-- 2 (N3TX instance — Product/2)
 |    +-- ...
 +-- User (DynClass)
 |    +-- ...
 +-- Component (class)
 |    +-- List-abc123 (instance)
 |    +-- Item-def456 (instance)
 |    +-- ...
 +-- TT (class)
```

Every actor has:
- An **address** (`addr`) — e.g., `"Product"`, `"Product/1"`, `"Item-abc123"`
- An **inbox** — receives TX messages, dispatches to `this[tx.name](tx.data, tx)`
- A **send** method — routes TX to target (local child, or bubble to Matrix)
- **Children** — a map of child actors

### Address Resolution

TX messages route through the tree using `/`-separated addresses:

```
Target: "Product/1"

Matrix receives TX
  +-- "Product" in children? YES -> DynClass "Product"
  |     +-- "1" in children? YES -> N3TX instance
  |     |     +-- Delivered to N3TX inbox
```

If the target is a URL (e.g., `http://localhost:5000/products`), Matrix
can't resolve it locally -> forwards to `NetworkAdapter.send()` -> HTTP request.

---

## 5. The Actor System — How Messages Flow

### Sending a Message

```js
// From any actor (component, N3TX, DynClass...):
this.send(new TX({
    name:   'UPDATE',           // Method to invoke on the target
    source: this.addr,          // Sender's address
    target: 'Product/1',       // Recipient's address
    data:   { price: 29.99 }   // Payload
}));
```

### Routing Algorithm

```
Actor.send(tx)
  |
  +-- Is target a direct child?
  |     YES -> child.inbox(tx)
  |
  +-- Does target start with my addr?
  |     YES -> strip prefix, route to children
  |
  +-- Neither?
        -> Prefix source with my addr
        -> Bubble up to Matrix.inbox(tx)
              |
              +-- Is first segment of target in Matrix children?
              |     YES -> forward to that class/DynClass
              |
              +-- Unknown target?
                    -> NetworkAdapter.send(tx) -> HTTP/WS
```

### Receiving a Message

When a TX arrives at an actor's inbox:

```js
// Actor._inbox dispatches by event name:
this[tx.name](tx.data, tx)

// Example: N3TX instance receives UPDATE
// -> calls this.UPDATE(data, event)
```

**Convention:** Handler names are UPPERCASE and match the TX `name` field exactly.

---

## 6. Dataflow — Render Lifecycle (Step by Step)

This is the complete flow when `<ntx-list model="Product">` appears on a page.
Follow each step — this is how the framework wires everything together.

```
  BROWSER                                           BACKEND
  =======                                           =======

  +----------------------+
  | <ntx-list model=     |
  |   "Product">         |
  |                      |
  | 1. constructor()     |
  |   registers in Matrix|
  |                      |
  | 2. attributeChanged  |
  |   model="Product"    |
  +----------+-----------+
             |
             |  TX { ATTACH, src: List-xxx, target: N3TX, data: "Product" }
             v
  +----------------------+
  | N3TX (static class)   |
  |                      |
  | 3. N3TX.ATTACH()      |
  |   "Product" not in   |
  |   #prototypes ->     |
  |   null pointer       |
  |   bootstrap:         |
  |   set null, queue TX |
  |                      |
  | 4. Dispatch SCHEMA   |
  +----------+-----------+
             |
             |  TX { SCHEMA, src: N3TX, target: http://.../Product }
             |  (target is a URL -> Matrix can't resolve -> NetworkAdapter)
             v
  +----------------------+        GET /Product
  | NetworkAdapter       | --------------------------->  +--------------+
  |                      |                               | Returns JSON |
  | 5. HTTP GET          | <---------------------------  | Schema       |
  |                      |        { properties:          | { __name__:  |
  | 6. httpCallback()    |          { name: {type:       |   "Product", |
  |   swaps src/target   |            "string"}, ...     |  __tablename_|
  |   name stays SCHEMA  |          }                    |  : "products"|
  +----------+-----------+        }                      +--------------+
             |
             |  TX { SCHEMA, src: http://.../Product, target: N3TX }
             v
  +----------------------+
  | N3TX.SCHEMA(data)     |
  |                      |
  | 7. prototype() creates DynClass "Product"
  |   - Stores in #prototypes
  |   - Registers $defs as additional DynClasses
  |   - Replays queued TXs (the original ATTACH)
  |   - DynClass.call('READ') triggers data fetch
  +----------+-----------+
             |
             | DynClass receives replayed ATTACH -> adds List as watcher
             |
             | DynClass.call('READ'):
             |  TX { READ, src: Product, target: http://.../products }
             v
  +----------------------+        GET /products
  | NetworkAdapter       | --------------------------->  +--------------+
  |                      |                               | Returns      |
  | 8. HTTP GET          | <---------------------------  | [{id:1,      |
  |                      |                               |   name:"KB"},|
  | 9. httpCallback()    |                               |  {id:2, ...}]|
  +----------+-----------+                               +--------------+
             |
             |  TX { READ, src: http://.../products, target: Product }
             v
  +----------------------+
  | DynClass.READ(data)  |
  |                      |
  | 10. For each record: |
  |   new Product(item)  |  <- DynClass instances
  |   stored in          |
  |   DynClass.instances |
  |                      |
  | 11. notify() ->      |
  |   sends UPDATE to    |
  |   all watchers       |
  +----------+-----------+
             |
             |  TX { UPDATE, src: Product, target: List-xxx,
             |       data: ["Product/1", "Product/2", ...] }
             v
  +----------------------+
  | List.UPDATE(data)    |
  |                      |
  | 12. this.value = addrs|
  |    this.render()     |
  |                      |
  | For each address:    |     For each <ntx-item>:
  |  createElement       |     +----------------------+
  |  ('ntx-item')        |     | 13. Item.ref setter  |
  |  el.ref = addr  -----+---->|                      |
  |                      |     | TX { ATTACH, src:     |
  +----------------------+     |   Item-yyy, target:   |
                               |   N3TX, data:          |
                               |   "Product/1" }       |
                               +----------+------------+
                                          |
                                          v
                               +----------------------+
                               | N3TX.ATTACH ->        |
                               | DynClass.ATTACH ->   |
                               | N3TX instance         |
                               | "Product/1"          |
                               |                      |
                               | 14. N3TX.ATTACH()     |
                               |   watch(Item-yyy)    |
                               |   sends DESCRIBE back|
                               +----------+-----------+
                                          |
                                          |  TX { DESCRIBE, data: {
                                          |    proto: schema,
                                          |    data: { id:1, name:"KB", ... }
                                          |  }}
                                          v
                               +----------------------+
                               | Item.DESCRIBE(data)   |
                               |                       |
                               | 15. this.schema = proto|
                               |    this.value = data  |
                               |    this.render()      |
                               |                       |
                               | -> Formidable generates|
                               |   HTML form from      |
                               |   schema + values     |
                               +-----------------------+
                                          |
                                          v
                               +-----------------------+
                               |  Rendered Card         |
                               |  +-----------------+  |
                               |  | Keyboard         |  |
                               |  | Price: $49.99   |  |
                               |  | In stock: true  |  |
                               |  +-----------------+  |
                               +-----------------------+
```

### Summary of Steps

| # | What happens | TX name | Direction |
|---|-------------|---------|-----------|
| 1-2 | List registers, triggers model lookup | `ATTACH` | List -> N3TX |
| 3-4 | Null pointer bootstrap, schema request | `SCHEMA` | N3TX -> Backend |
| 5-6 | HTTP GET, response routed back | `SCHEMA` | Backend -> N3TX |
| 7 | DynClass created, queue replayed, READ triggered | (internal) | — |
| 8-9 | HTTP GET records, response routed back | `READ` | Backend -> DynClass |
| 10-11 | N3TX instances created, watchers notified | `UPDATE` | DynClass -> List |
| 12 | List renders `<ntx-item>` elements | (DOM) | — |
| 13 | Items send ATTACH through N3TX | `ATTACH` | Item -> N3TX -> DynClass -> instance |
| 14 | N3TX responds with DESCRIBE | `DESCRIBE` | N3TX -> Item |
| 15 | Item renders form from schema + data | (DOM) | — |

---

## 7. CRUD Operations

### Read (List)

Automatic when using `<ntx-list>`. Or manually:

```js
N3TX.attach('Product', (dynClass) => {
    // DynClass is ready (schema loaded, initial READ done)
    console.log('Schema:', dynClass.schema);
    console.log('Instances:', dynClass.instances);
});
```

### Read (Single)

```html
<ntx-item ref="Product/4"></ntx-item>
```

The item ATTACHes to `Product/4`, receives DESCRIBE with the entity data.

### Create

```js
// Get the DynClass for a model, then call CREATE
const Product = N3TX.get('Product');
Product.call('CREATE', {
    name: 'New Widget',
    price: 19.99,
    description: 'A shiny new widget'
});
```

This sends: `TX { CREATE, target: http://.../products, data: {...} }`
-> HTTP POST -> Backend creates record.

### Update

When a user edits an `<ntx-item>` and clicks save:

```
Item.save()
  -> TX { UPDATE, src: Item-xxx, target: N3TX, data: "Product/1" }
  -> Routes to N3TX instance "Product/1"
  -> N3TX.UPDATE(): optimistically updates local data, forwards to backend
  -> TX { UPDATE, target: http://.../products/1, data: {...} }
  -> HTTP PUT /products/1
```

### Delete

```js
// Get an entity instance and call DELETE
const product = N3TX.get('Product/1');
product.call('DELETE', {});
// -> HTTP DELETE /products/1
```

### How TX Names Map to HTTP Methods

| TX `name` | HTTP Method | URL Pattern |
|-----------|-------------|-------------|
| `SCHEMA` | GET | `{API_URL}/ModelName` |
| `READ` | GET | `{API_URL}/tablename` |
| `CREATE` | POST | `{API_URL}/tablename` |
| `UPDATE` | PUT | `{API_URL}/tablename/id` |
| `DELETE` | DELETE | `{API_URL}/tablename/id` |
| `(custom)` | POST | `{API_URL}/tablename/id/methodname` |
| `_response_` | (internal) | Auto-pulls entity after method call |

---

## 8. Local Relationship Hydration — Collection Fields as Objects

When a model has a local owned collection field (for example
`Product.comments: list[Comment]`), SQLite stores an ordered JSON array of child
ids on the parent row. On read, the backend hydrates those ids into
self-describing child objects. The frontend can render the relationship directly
while each child still carries its own flat class-name identity URL.

### What the Data Looks Like

```json
{
  "id": 1,
  "name": "Keyboard",
  "price": 49.99,
  "comments": [
    {
      "$schema": "http://localhost:5000/Comment",
      "$id": "http://localhost:5000/Comment/1",
      "id": 1,
      "name": "Great!",
      "description": "Love it"
    },
    {
      "$schema": "http://localhost:5000/Comment",
      "$id": "http://localhost:5000/Comment/2",
      "id": 2,
      "name": "Useful",
      "description": "Bought one too"
    }
  ]
}
```

Each child object has the same identity shape as a top-level entity:

```
{API_URL}/{ChildClassName}/{child_id}
```

| Segment | Source | Example |
|---------|--------|---------|
| `API_URL` | `config.API_URL` | `http://localhost:5000` |
| `ChildClassName` | Child model class name | `Comment` |
| `child_id` | Child record ID | `2` |

### Resolving Child Objects

Each child's `$id` is a standard class-name URL. Fetching it returns the full
child object:

```
GET /Comment/1
-> { "$schema": "http://localhost:5000/Comment", "$id": "http://localhost:5000/Comment/1", "id": 1, "name": "Great!" }
```

No generated nested routes are needed. Relationship ownership is represented by
the model field and storage contract, not by a parent-scoped URL segment.

### Why Hydrated Objects

- **Schema-driven rendering** — relationship values already include `$schema` and `$id` metadata.
- **Flat identity** — every entity resolves through `/{ClassName}/{id}` regardless of where it appears.
- **Simpler storage** — owned local collection order is the parent row's JSON id array.
- **Model-first behavior** — app-specific append/toggle rules live in `@expose_route` methods.

### Backend Type: `list[T]`

On the backend, local owned collection fields use normal Python list typing:

```python
class Product(ProtoModel):
    comments: list[Comment] = Field(default=[])
```

`list[T]` stores local child ids in SQLite and hydrates them into `T` instances
when the parent is read. Use `list[Ref[T]]` instead when the field is a pointer
array that may include distributed references.

### Schema Representation

The JSON schema for a local `list[T]` field is an array of the child schema:

```json
{
  "comments": {
    "type": "array",
    "items": { "$ref": "#/$defs/Comment" }
  }
}
```

This tells the frontend that `comments` values are child objects. The backend
keeps those objects self-describing in API responses.

---

## 9. Web Components API

### `<ntx-list>`

Renders all records for a model as a grid of `<ntx-item>` cards.

```html
<ntx-list model="Product"></ntx-list>
```

| Attribute | Required | Description |
|-----------|----------|-------------|
| `model` | Yes | Backend model name (PascalCase, e.g. `Product`, `User`) |

**Lifecycle:**
1. Sends ATTACH to N3TX with model name
2. N3TX bootstraps schema, creates DynClass
3. DynClass.call('READ') fetches records
4. List receives UPDATE with array of N3TX addresses
5. Renders `<ntx-item ref="addr">` for each

**Message handlers:**

| Handler | Data | Behavior |
|---------|------|----------|
| `UPDATE(data)` | `["Product/1", "Product/2", ...]` | Stores addresses, re-renders |

### `<ntx-item>`

Renders a single entity as an editable card with form fields.

```html
<!-- Created automatically by ntx-list, or standalone: -->
<ntx-item ref="Product/4"></ntx-item>
```

| Attribute | Required | Description |
|-----------|----------|-------------|
| `ref` | Yes | N3TX address (`ModelName/id`) |
| `mode` | No | `"display"` (default) or `"edit"` |

**Lifecycle:**
1. Setting `ref` sends ATTACH to N3TX (routed to DynClass then to instance)
2. N3TX instance responds with DESCRIBE (schema + data)
3. Item renders using `Formidable.getForm()`
4. Click pencil -> edit mode (inputs). Click save -> sends UPDATE to N3TX.

**Message handlers:**

| Handler | Data | Behavior |
|---------|------|----------|
| `DESCRIBE(data)` | `{proto: schema, data: entity}` | Sets schema + value, renders |
| `UPDATE(data)` | Entity data with `$schema` | Updates value, re-renders |

**Modes:**

| Mode | Display | Button |
|------|---------|--------|
| `display` | Read-only text | Pencil icon (edit) |
| `edit` | Input fields | Floppy icon (save) |

### `<ntx-element>` (base class)

Not used directly — extended by List and Item. Provides:

| Property | Description |
|----------|-------------|
| `model` | Model name string |
| `ref` | N3TX address (setting sends ATTACH) |
| `proto` | DynClass reference (set via `define()`) |
| `schema` | JSON schema from proto |
| `value` | Current entity data |
| `addr` | Unique actor address |

| Method | Description |
|--------|-------------|
| `define(dynClass)` | Links to a DynClass, calls `definedCallback()` |
| `send(tx)` | Sends a TX message through the actor system |
| `definedCallback()` | Override — called when schema is ready |

---

## 10. Custom Methods

If your backend model defines custom methods (e.g., `comment` on Product),
they appear in the JSON schema under `methods` and are auto-generated as
methods on the DynClass prototype:

```
Backend schema:
{
  "methods": {
    "comment": {
      "parameters": {
        "name":        { "type": "string" },
        "description": { "type": "string" }
      }
    }
  }
}
```

```js
// Call from code:
const product = N3TX.get('Product/1');
product.comment({ name: "Great!", description: "Love this product" });

// Under the hood:
// TX { name: 'comment', target: http://.../products/1 }
// -> NetworkAdapter maps unknown name -> POST /products/1/comment
```

---

## 11. Building a Complete App

### Multi-Model Dashboard

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Admin Dashboard</title>
    <link rel="stylesheet" href="./dark-theme.css">
    <link rel="icon" type="image/svg+xml" href="./favicon.svg">
    <style>
        .dashboard { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; padding: 2rem; }
        h1 { text-align: center; color: #eee; }
    </style>
</head>
<body>

    <h1>Admin Dashboard</h1>

    <div class="dashboard">
        <section>
            <h2>Products</h2>
            <ntx-list model="Product"></ntx-list>
        </section>
        <section>
            <h2>Users</h2>
            <ntx-list model="User"></ntx-list>
        </section>
    </div>

    <script type="module">
        import { Matrix, matrix } from './core/Matrix.js';
        import { N3TX }            from './core/N3TX.js';
        import { config }         from './config.js';
        import './components/ntx-item.js';
        import './components/ntx-list.js';
    </script>

</body>
</html>
```

### Single Entity View

```html
<!-- Show just one product by ID -->
<ntx-item ref="Product/4"></ntx-item>

<script type="module">
    import { Matrix, matrix } from './core/Matrix.js';
    import { N3TX }            from './core/N3TX.js';
    import { config }         from './config.js';
    import './components/ntx-item.js';
    import './components/ntx-list.js';
</script>
```

### Programmatic Access

```js
// Wait for a DynClass to be ready, then work with entities
N3TX.attach('Product', (dynClass) => {
    console.log('Schema:', dynClass.schema);
    console.log('CRUD endpoint:', dynClass.href);

    // Access all loaded instances
    for (const [id, ntt] of dynClass.children) {
        console.log(`${ntt.addr}: ${ntt.value.name} -- $${ntt.value.price}`);
    }
});
```

---

## 12. Message Protocol Cheat Sheet

### TX Message Format

```js
{
  name:   "EVENT_NAME",       // Handler method to invoke (UPPERCASE)
  source: "sender-address",   // Who sent this
  target: "receiver-address", // Who should receive this (addr or URL)
  data:   { ... },            // Payload
  meta:   { ... },            // Metadata: { remote, inbox, ... }
  tst:    1702000000000,      // Timestamp
  hash:   "abc123"            // Content hash
}
```

### Key `meta` Fields

| Field | Type | Effect |
|-------|------|--------|
| `remote` | `bool` | Marks message for/from network transport |
| `inbox` | `string` | Overrides the response event name (e.g., response arrives as UPDATE instead of READ) |

### Complete Message Reference

| Name | Direction | Purpose |
|------|-----------|---------|
| `ATTACH` | Component -> N3TX -> DynClass/instance | "I want to connect to this model/entity" |
| `SCHEMA` | N3TX <-> Backend | Fetch/receive JSON schema |
| `READ` | DynClass -> Backend | Fetch all records |
| `DESCRIBE` | N3TX instance -> Component | "Here's my schema and current data" |
| `UPDATE` | Any <-> Any | Update entity data (local or remote) |
| `CREATE` | DynClass -> Backend | Create a new record |
| `DELETE` | N3TX instance -> Backend | Delete a record |
| `CONNECT` | Component -> Matrix | Connect to a type (theme/role routing) |
| `ERROR` | NetworkAdapter -> Source | Network error response |

### Response Flow (meta.inbox)

The `meta.inbox` pattern lets you control what event name the response arrives as:

```
Request:  { name: READ, meta: { inbox: 'UPDATE' } }
                                          |
Response: { name: UPDATE }  <-------------+
                  (not READ)
```

This is how DynClass gets list data back as an UPDATE event to trigger re-rendering.

---

## 13. Configuration Reference

All settings in `config.js`:

| Key | Default | Description |
|-----|---------|-------------|
| `API_URL` | `http://localhost:5000` | Backend base URL. All schema and CRUD calls use this. |
| `WS_URL` | `ws://localhost:8765` | WebSocket URL (when using WS transport mode) |
| `LOGGING` | `3` | Log verbosity: 0=off, 1=errors, 2=warnings, 3=verbose |
| `LOGEVENTS` | `true` | Log all TX messages to console |
| `LOGSPAWN` | `true` | Log actor creation |
| `DEBUG` | `true` | Enable debug output throughout |
| `DEFAULT_HEADERS` | `{Content-Type, Accept: json}` | Default headers for HTTP requests |
| `TIMEOUT` | `5000` | Request timeout in ms |
| `RETRY_LIMIT` | `3` | Max retries for failed requests |
| `E` | `{...}` | Event name constants (CONNECT, UPDATE, READ, etc.) |

---

## 14. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| List is empty / no cards | Backend not running or wrong `API_URL` | Check `config.js` API_URL matches backend port |
| "CORS error" in console | Backend doesn't allow frontend origin | Add CORS middleware to FastAPI backend |
| Cards render but show "Placeholder" | Schema loaded but READ failed | Check backend `/tablename` endpoint returns an array |
| Edit + Save does nothing | N3TX update flow not connected | Check browser console for TX routing errors |
| `$schema` assertion error on save | Response bypassing N3TX, going directly to Item | Hard-refresh browser (Ctrl+Shift+R) to clear cached JS |

### Debugging Tips

1. **Enable verbose logging** — set `LOGGING: 3` and `LOGEVENTS: true` in config.js
2. **Watch TX flow** — every message logs to console with source -> target
3. **Inspect actor tree** — `matrix.children` in console shows all registered classes
4. **Check N3TX state** — `N3TX.get('Product')` returns the DynClass, `.schema` for schema, `.children` for instances

---

## Module Map

```
static/
  config.js                     <- Configuration (API_URL, events, flags)
  dark-theme.css                <- Default dark theme
  favicon.svg                   <- App icon
  core/
    Actor.js                    <- Base actor + subclass() metaclass
    Matrix.js                   <- Root actor singleton, message router
    TX.js                       <- Message envelope (name, src, target, data, meta)
    Observable.js               <- Mixin: signal/observe/notify reactivity
    N3TX.js                      <- TT, N3TX + prototype() DynClass factory
    Component.js                <- HTMLElement + Actor base for web components
    Utils.js                    <- generateId, simpleHash, deepEqual, isUrl
    transport/
      NetworkAdapter.js         <- Matrix <-> Backend bridge (HTTP/WS)
      HTTP.js                   <- fetch() wrapper with JWT auth
      Socket.js                 <- WebSocket client (heartbeat, reconnect)
  components/
    ntx-element.js              <- NTTElement: base with model/schema/value
    ntx-list.js                 <- <ntx-list>: renders entity grid
    ntx-item.js                 <- <ntx-item>: renders entity card + form
    ntx-method.js               <- <ntx-method>: custom method invocation (fieldset/inline/button)
    ntx-favorites.js            <- <ntx-favorites>: favorites page (wraps ProductLike list)
    ntx-topbar.js               <- <ntx-topbar>: navigation bar with auth + favorites link
    ntx-user.js                 <- <ntx-user>: circular avatar rendering (xs/sm)
    *.css                       <- Component styles (shadow DOM)
  generators/
    form.js                     <- Formidable: schema -> HTML form generator
  utils/
    Assert.js                   <- assert/caution/inform helpers
    Logging.js                  <- Styled console logging with caller detection
    Snippets.js                 <- General utilities
  docs/                         <- Full documentation
```

---

## Further Reading

| Document | What You'll Learn |
|----------|------------------|
| `docs/ARCHITECTURE.md` | System layers, class hierarchy, initialization sequence |
| `docs/ACTORS.md` | Deep dive into Actor, Matrix, TT, N3TX, DynClass |
| `docs/COMPONENTS.md` | Web component API, Formidable form generator |
| `docs/MESSAGE_PROTOCOL.md` | Every TX message type with routing examples |
| `docs/TRANSPORT.md` | NetworkAdapter, HTTP, WebSocket internals |
