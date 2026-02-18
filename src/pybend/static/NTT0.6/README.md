# NTTTX Framework — Quickstart & Developer Guide

> **Build schema-driven UIs with zero boilerplate.**
> Drop a `<ntt-list>` tag, point it at a model, and the framework handles
> schema discovery, data fetching, rendering, and CRUD — all via actors.

---

## TL;DR — From Zero to Rendered List

```html
<ntt-list model="Product"></ntt-list>

<script type="module">
    import { Matrix, matrix } from './core/Matrix.js';
    import { PTT } from './core/NTT.js';
    import { config } from './config.js';
    import './components/ntt-item.js';
    import './components/ntt-list.js';
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
8. [Web Components API](#8-web-components-api)
9. [Custom Methods](#9-custom-methods)
10. [Building a Complete App](#10-building-a-complete-app)
11. [Message Protocol Cheat Sheet](#11-message-protocol-cheat-sheet)
12. [Configuration Reference](#12-configuration-reference)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Mental Model — The Big Picture

NTTTX is an **actor-based** frontend runtime. Think of it as a post office
inside the browser: every piece of data, every UI component, and the network
layer are all **actors** with mailboxes. They communicate by sending
**TX messages** through a central router called the **Matrix**.

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER                                  │
│                                                                 │
│   ┌──────────┐     TX Messages    ┌──────────────────────┐     │
│   │   UI     │ ◄═══════════════► │      MATRIX          │     │
│   │  Layer   │   (ATTACH, UPDATE, │   (Root Actor /      │     │
│   │          │    DESCRIBE, ...)  │    Message Router)    │     │
│   │ <ntt-list│                    │                      │     │
│   │ <ntt-item│                    │   children:          │     │
│   └──────────┘                    │   ├─ PTT (schemas)   │     │
│                                   │   ├─ NTT (entities)  │     │
│                                   │   ├─ Component (UI)  │     │
│                                   │   └─ ...             │     │
│                                   └─────────┬────────────┘     │
│                                             │                   │
│                                    ┌────────▼─────────┐        │
│                                    │ NetworkAdapter    │        │
│                                    │ (HTTP / WebSocket)│        │
│                                    └────────┬─────────┘        │
└─────────────────────────────────────────────┼──────────────────┘
                                              │  fetch() / WS
                                    ┌─────────▼─────────┐
                                    │   PyBend Backend   │
                                    │   (FastAPI)        │
                                    │                    │
                                    │  GET /Product      │ → JSON Schema
                                    │  GET /products     │ → [{...}, ...]
                                    │  PUT /products/1   │ → Updated record
                                    └────────────────────┘
```

### Key Insight: Components Never Talk to the Network Directly

A `<ntt-item>` doesn't call `fetch()`. It sends a TX message to its NTT actor,
which routes through the Matrix, hits the NetworkAdapter, and the response
flows back the same way. This decouples UI from transport entirely.

---

## 2. Setup

### 2.1 Backend

You need a PyBend backend running. The default port is `5000`:

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

Every NTTTX page needs these module imports:

```js
import { Matrix, matrix } from './core/Matrix.js';  // Root actor (auto-initializes)
import { PTT }            from './core/NTT.js';      // Schema proxy + entity classes
import { config }         from './config.js';         // Configuration
import './components/ntt-item.js';                    // <ntt-item> web component
import './components/ntt-list.js';                    // <ntt-list> web component
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
    <title>My NTTTX App</title>
    <link rel="stylesheet" href="./dark-theme.css">
    <link rel="icon" type="image/svg+xml" href="./favicon.svg">
</head>
<body>

    <h1>Products</h1>
    <ntt-list model="Product"></ntt-list>

    <h1>Users</h1>
    <ntt-list model="User"></ntt-list>

    <script type="module">
        import { Matrix, matrix } from './core/Matrix.js';
        import { PTT }            from './core/NTT.js';
        import { config }         from './config.js';
        import './components/ntt-item.js';
        import './components/ntt-list.js';
    </script>

</body>
</html>
```

Each `<ntt-list>` independently:
1. Asks the backend for the model's JSON schema
2. Discovers the CRUD endpoint from `__tablename__`
3. Fetches all records
4. Renders editable `<ntt-item>` cards in a grid

---

## 4. Core Concepts

### The Five Pillars

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────────┐
│  Matrix  │    │   PTT   │    │   NTT   │    │   TX    │    │  Component  │
│          │    │         │    │         │    │         │    │             │
│  Root    │    │ Schema  │    │ Entity  │    │ Message │    │ Web Comp.   │
│  Actor   │    │ Proxy   │    │Instance │    │Envelope │    │ = Actor     │
│  Router  │    │ + Class │    │ + Data  │    │         │    │             │
│          │    │ Factory │    │         │    │         │    │             │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────────┘
```

| Concept | What it is | Analogy |
|---------|-----------|---------|
| **Matrix** | Singleton root actor. Routes every TX message to the right place, or sends it to the backend. | The post office |
| **PTT** | Proto Transfer Type. One per model (e.g., `Product`). Holds the JSON schema, generates a dynamic NTT subclass, manages entity instances. | A class definition / factory |
| **NTT** | Named Transfer Type. One per entity (e.g., `Product/4`). Holds the actual data. Has an `href` pointing at its backend URL. | An object instance |
| **TX** | Transaction message. `{name, source, target, data, meta}`. Every interaction is a TX. | A letter in an envelope |
| **Component** | Web component base class that is also an Actor. Has `send()` and `inbox()`. | A mailbox-enabled HTML element |

### Actor Hierarchy

```
Matrix (root)
 ├── PTT (class)
 │    ├── Product (PTT instance)
 │    │    ├── 1 (NTT instance — Product/1)
 │    │    ├── 2 (NTT instance — Product/2)
 │    │    └── ...
 │    └── User (PTT instance)
 │         └── ...
 ├── Component (class)
 │    ├── List-abc123 (instance)
 │    ├── Item-def456 (instance)
 │    └── ...
 ├── NTT (class)
 └── TT (class)
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
  ├── "Product" in children? YES → PTT class
  │     ├── "Product" in children? YES → PTT instance
  │     │     ├── "1" in children? YES → NTT instance
  │     │     │     └── Delivered to NTT inbox
```

If the target is a URL (e.g., `http://localhost:5000/products`), Matrix
can't resolve it locally → forwards to `NetworkAdapter.send()` → HTTP request.

---

## 5. The Actor System — How Messages Flow

### Sending a Message

```js
// From any actor (component, NTT, PTT...):
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
  │
  ├── Is target a direct child?
  │     YES → child.inbox(tx)
  │
  ├── Does target start with my addr?
  │     YES → strip prefix, route to children
  │
  └── Neither?
        → Prefix source with my addr
        → Bubble up to Matrix.inbox(tx)
              │
              ├── Is first segment of target in Matrix children?
              │     YES → forward to that class
              │
              └── Unknown target?
                    → NetworkAdapter.send(tx) → HTTP/WS
```

### Receiving a Message

When a TX arrives at an actor's inbox:

```js
// Actor._inbox dispatches by event name:
this[tx.name](tx.data, tx)

// Example: NTT instance receives UPDATE
// → calls this.UPDATE(data, event)
```

**Convention:** Handler names are UPPERCASE and match the TX `name` field exactly.

---

## 6. Dataflow — Render Lifecycle (Step by Step)

This is the complete flow when `<ntt-list model="Product">` appears on a page.
Follow each step — this is how the framework wires everything together.

```
  BROWSER                                           BACKEND
  ═══════                                           ═══════

  ┌──────────────────────┐
  │ <ntt-list model=     │
  │   "Product">         │
  │                      │
  │ 1. constructor()     │
  │   registers in Matrix│
  │                      │
  │ 2. attributeChanged  │
  │   model="Product"    │
  └──────────┬───────────┘
             │
             │  TX { ATTACH, src: List-xxx, target: PTT, data: "Product" }
             ▼
  ┌──────────────────────┐
  │ PTT (static class)   │
  │                      │
  │ 3. PTT.ATTACH()      │
  │   No "Product" PTT   │
  │   exists yet → create│
  │   new PTT("Product") │
  │                      │
  │ 4. PTT.pull()        │
  └──────────┬───────────┘
             │
             │  TX { SCHEMA, src: Product, target: http://.../Product }
             │  (target is a URL → Matrix can't resolve → NetworkAdapter)
             ▼
  ┌──────────────────────┐        GET /Product
  │ NetworkAdapter       │ ──────────────────────►  ┌──────────────┐
  │                      │                          │ Returns JSON │
  │ 5. HTTP GET          │ ◄──────────────────────  │ Schema       │
  │                      │        { properties:     │ { __name__:  │
  │ 6. httpCallback()    │          { name: {type:  │   "Product", │
  │   swaps src/target   │            "string"}, ...│  __tablename_│
  │   name stays SCHEMA  │          }               │  : "products"│
  └──────────┬───────────┘        }                 └──────────────┘
             │
             │  TX { SCHEMA, src: http://.../Product, target: Product }
             ▼
  ┌──────────────────────┐
  │ PTT instance         │
  │ "Product"            │
  │                      │
  │ 7. PTT.SCHEMA(data)  │
  │   - href = .../products (from __tablename__)
  │   - prototype() generates dynamic NTT subclass
  │   - signal() fires → List.define() callback
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ List.definedCallback()│
  │                      │
  │ 8. proto.call('READ')│
  └──────────┬───────────┘
             │
             │  TX { READ, src: Product, target: http://.../products,
             │       meta: { inbox: 'UPDATE' } }
             ▼
  ┌──────────────────────┐        GET /products
  │ NetworkAdapter       │ ──────────────────────►  ┌──────────────┐
  │                      │                          │ Returns      │
  │ 9. HTTP GET          │ ◄──────────────────────  │ [{id:1,      │
  │                      │                          │   name:"KB"},│
  │ 10. httpCallback()   │                          │  {id:2, ...}]│
  │   name = 'UPDATE'    │                          └──────────────┘
  │   (from meta.inbox)  │
  └──────────┬───────────┘
             │
             │  TX { UPDATE, src: http://.../products, target: Product }
             ▼
  ┌──────────────────────┐
  │ PTT.READ(data)       │
  │                      │
  │ 11. For each record: │
  │   new Product(item)  │  ← Dynamic NTT subclass
  │   stored in          │
  │   PTT.#instances     │
  │                      │
  │ 12. notify() →       │
  │   sends UPDATE to    │
  │   all watchers       │
  └──────────┬───────────┘
             │
             │  TX { UPDATE, src: Product, target: List-xxx,
             │       data: ["Product/1", "Product/2", ...] }
             ▼
  ┌──────────────────────┐
  │ List.UPDATE(data)    │
  │                      │
  │ 13. this.value = addrs│
  │    this.render()     │
  │                      │
  │ For each address:    │     For each <ntt-item>:
  │  createElement       │     ┌──────────────────────┐
  │  ('ntt-item')        │     │ 14. Item.ref setter  │
  │  el.ref = addr  ─────┼────►│                      │
  │                      │     │ TX { ATTACH, src:     │
  └──────────────────────┘     │   Item-yyy, target:   │
                               │   "Product/1" }       │
                               └──────────┬────────────┘
                                          │
                                          ▼
                               ┌──────────────────────┐
                               │ NTT instance          │
                               │ "Product/1"           │
                               │                       │
                               │ 15. NTT.ATTACH()      │
                               │   watch(Item-yyy)     │
                               │   sends DESCRIBE back │
                               └──────────┬────────────┘
                                          │
                                          │  TX { DESCRIBE, data: {
                                          │    proto: schema,
                                          │    data: { id:1, name:"KB", ... }
                                          │  }}
                                          ▼
                               ┌──────────────────────┐
                               │ Item.DESCRIBE(data)   │
                               │                       │
                               │ 16. this.schema = proto│
                               │    this.value = data  │
                               │    this.render()      │
                               │                       │
                               │ → Formidable generates│
                               │   HTML form from      │
                               │   schema + values     │
                               └───────────────────────┘
                                          │
                                          ▼
                               ┌───────────────────────┐
                               │  Rendered Card         │
                               │  ┌─────────────────┐  │
                               │  │ Keyboard         │  │
                               │  │ Price: $49.99   │  │
                               │  │ In stock: true  │  │
                               │  └─────────────────┘  │
                               └───────────────────────┘
```

### Summary of the 16 Steps

| # | What happens | TX name | Direction |
|---|-------------|---------|-----------|
| 1-2 | List registers, triggers model lookup | `ATTACH` | List → PTT |
| 3-4 | PTT created, pulls schema from backend | `SCHEMA` | PTT → Backend |
| 5-6 | HTTP GET, response routed back | `SCHEMA` | Backend → PTT |
| 7 | Schema processed, dynamic class generated | (internal) | — |
| 8 | List requests data | `READ` | PTT → Backend |
| 9-10 | HTTP GET, response renamed to UPDATE | `UPDATE` | Backend → PTT |
| 11-12 | NTT instances created, watchers notified | `UPDATE` | PTT → List |
| 13 | List renders `<ntt-item>` elements | (DOM) | — |
| 14 | Items send ATTACH to their NTT | `ATTACH` | Item → NTT |
| 15 | NTT responds with DESCRIBE | `DESCRIBE` | NTT → Item |
| 16 | Item renders form from schema + data | (DOM) | — |

---

## 7. CRUD Operations

### Read (List)

Automatic when using `<ntt-list>`. Or manually:

```js
const ptt = PTT.get('Product');
ptt.signal(() => {
    // PTT is ready (schema loaded)
    ptt.call('READ', {}, { inbox: 'UPDATE' });
});
```

### Read (Single)

```html
<ntt-item ref="Product/4"></ntt-item>
```

The item ATTACHes to `Product/4`, receives DESCRIBE with the entity data.

### Create

```js
// Send a CREATE message through the PTT
NTT.create('Product', {
    name: 'New Widget',
    price: 19.99,
    description: 'A shiny new widget'
});
```

This sends: `TX { CREATE, target: http://.../products, data: {...} }`
→ HTTP POST → Backend creates record.

### Update

When a user edits an `<ntt-item>` and clicks save:

```
Item.save()
  → TX { UPDATE, src: Item-xxx, target: Product/1, data: { price: 29.99 } }
  → Routes to NTT instance "Product/1"
  → NTT.UPDATE(): optimistically updates local data, forwards to backend
  → TX { UPDATE, target: http://.../products/1, data: {...} }
  → HTTP PUT /products/1
```

### Delete

```js
// From code, get a reference to the NTT and call DELETE
const ntt = PTT.get('Product').get('1');
ntt.call('DELETE', {});
// → HTTP DELETE /products/1
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

---

## 8. Web Components API

### `<ntt-list>`

Renders all records for a model as a grid of `<ntt-item>` cards.

```html
<ntt-list model="Product"></ntt-list>
```

| Attribute | Required | Description |
|-----------|----------|-------------|
| `model` | Yes | Backend model name (PascalCase, e.g. `Product`, `User`) |

**Lifecycle:**
1. Sends ATTACH to PTT with model name
2. Waits for schema (define callback)
3. Calls `proto.call('READ')` to fetch records
4. Receives UPDATE with array of NTT addresses
5. Renders `<ntt-item ref="addr">` for each

**Message handlers:**

| Handler | Data | Behavior |
|---------|------|----------|
| `UPDATE(data)` | `["Product/1", "Product/2", ...]` | Stores addresses, re-renders |

### `<ntt-item>`

Renders a single entity as an editable card with form fields.

```html
<!-- Created automatically by ntt-list, or standalone: -->
<ntt-item ref="Product/4"></ntt-item>
```

| Attribute | Required | Description |
|-----------|----------|-------------|
| `ref` | Yes | NTT address (`ModelName/id`) |
| `mode` | No | `"display"` (default) or `"edit"` |

**Lifecycle:**
1. Setting `ref` sends ATTACH to the NTT instance
2. NTT responds with DESCRIBE (schema + data)
3. Item renders using `Formidable.getForm()`
4. Click pencil → edit mode (inputs). Click save → sends UPDATE to NTT.

**Message handlers:**

| Handler | Data | Behavior |
|---------|------|----------|
| `DESCRIBE(data)` | `{proto: schema, data: entity}` | Sets schema + value, renders |
| `UPDATE(data)` | Entity data with `@type` | Updates value, re-renders |

**Modes:**

| Mode | Display | Button |
|------|---------|--------|
| `display` | Read-only text | Pencil icon (edit) |
| `edit` | Input fields | Floppy icon (save) |

### `<ntt-element>` (base class)

Not used directly — extended by List and Item. Provides:

| Property | Description |
|----------|-------------|
| `model` | Model name string |
| `ref` | NTT address (setting sends ATTACH) |
| `proto` | PTT reference (set via `define()`) |
| `schema` | JSON schema from proto |
| `value` | Current entity data |
| `addr` | Unique actor address |

| Method | Description |
|--------|-------------|
| `define(ptt)` | Links to a PTT, calls `definedCallback()` |
| `send(tx)` | Sends a TX message through the actor system |
| `definedCallback()` | Override — called when schema is ready |

---

## 9. Custom Methods

If your backend model defines custom methods (e.g., `comment` on Product),
they appear in the JSON schema under `methods` and are auto-generated as
methods on the dynamic NTT subclass:

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
const product = PTT.get('Product').get('1');
product.comment({ name: "Great!", description: "Love this product" });

// Under the hood:
// TX { name: 'comment', target: http://.../products/1 }
// → NetworkAdapter maps unknown name → POST /products/1/comment
```

---

## 10. Building a Complete App

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
            <ntt-list model="Product"></ntt-list>
        </section>
        <section>
            <h2>Users</h2>
            <ntt-list model="User"></ntt-list>
        </section>
    </div>

    <script type="module">
        import { Matrix, matrix } from './core/Matrix.js';
        import { PTT }            from './core/NTT.js';
        import { config }         from './config.js';
        import './components/ntt-item.js';
        import './components/ntt-list.js';
    </script>

</body>
</html>
```

### Single Entity View

```html
<!-- Show just one product by ID -->
<ntt-item ref="Product/4"></ntt-item>

<script type="module">
    import { Matrix, matrix } from './core/Matrix.js';
    import { PTT }            from './core/NTT.js';
    import { config }         from './config.js';
    import './components/ntt-item.js';
    import './components/ntt-list.js';
</script>
```

### Programmatic Access

```js
// Wait for a PTT to be ready, then work with entities
PTT.attach('Product', (ptt) => {
    console.log('Schema:', ptt.schema);
    console.log('CRUD endpoint:', ptt.href);

    // Access all loaded instances
    for (const [id, ntt] of ptt.children) {
        console.log(`${ntt.addr}: ${ntt.value.name} — $${ntt.value.price}`);
    }
});
```

---

## 11. Message Protocol Cheat Sheet

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
| `ATTACH` | Component → PTT/NTT | "I want to connect to this model/entity" |
| `SCHEMA` | PTT ↔ Backend | Fetch/receive JSON schema |
| `READ` | PTT → Backend | Fetch all records |
| `DESCRIBE` | NTT → Component | "Here's my schema and current data" |
| `UPDATE` | Any ↔ Any | Update entity data (local or remote) |
| `CREATE` | PTT → Backend | Create a new record |
| `DELETE` | NTT → Backend | Delete a record |
| `CONNECT` | Component → Matrix | Connect to a type (theme/role routing) |
| `ERROR` | NetworkAdapter → Source | Network error response |

### Response Flow (meta.inbox)

The `meta.inbox` pattern lets you control what event name the response arrives as:

```
Request:  { name: READ, meta: { inbox: 'UPDATE' } }
                                          │
Response: { name: UPDATE }  ◄─────────────┘
                  (not READ)
```

This is how PTT gets list data back as an UPDATE event to trigger re-rendering.

---

## 12. Configuration Reference

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

## 13. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| List is empty / no cards | Backend not running or wrong `API_URL` | Check `config.js` API_URL matches backend port |
| "CORS error" in console | Backend doesn't allow frontend origin | Add CORS middleware to FastAPI backend |
| Cards render but show "Placeholder" | Schema loaded but READ failed | Check backend `/tablename` endpoint returns an array |
| Edit + Save does nothing | NTT update flow not connected | Check browser console for TX routing errors |
| `@type` assertion error on save | Response bypassing NTT, going directly to Item | Hard-refresh browser (Ctrl+Shift+R) to clear cached JS |

### Debugging Tips

1. **Enable verbose logging** — set `LOGGING: 3` and `LOGEVENTS: true` in config.js
2. **Watch TX flow** — every message logs to console with source → target
3. **Inspect actor tree** — `matrix.children` in console shows all registered classes
4. **Check PTT state** — `PTT.get('Product')` returns the PTT instance, `.schema` for schema, `.children` for instances

---

## Module Map

```
NTT0.6/
  config.js                     ← Configuration (API_URL, events, flags)
  dark-theme.css                ← Default dark theme
  favicon.svg                   ← App icon
  core/
    Actor.js                    ← Base actor + subclass() metaclass
    Matrix.js                   ← Root actor singleton, message router
    TX.js                       ← Message envelope (name, src, target, data, meta)
    Observable.js               ← Mixin: signal/observe/notify reactivity
    NTT.js                      ← TT, PTT, NTT + prototype() class factory
    Component.js                ← HTMLElement + Actor base for web components
    Utils.js                    ← generateId, simpleHash, deepEqual, isUrl
    transport/
      NetworkAdapter.js         ← Matrix ↔ Backend bridge (HTTP/WS)
      HTTP.js                   ← fetch() wrapper with JWT auth
      Socket.js                 ← WebSocket client (heartbeat, reconnect)
  components/
    ntt-element.js              ← NTTElement: base with model/schema/value
    ntt-list.js                 ← <ntt-list>: renders entity grid
    ntt-item.js                 ← <ntt-item>: renders entity card + form
    ntt-method.js               ← <ntt-method>: custom method invocation
    *.css                       ← Component styles (shadow DOM)
  generators/
    form.js                     ← Formidable: schema → HTML form generator
  utils/
    Assert.js                   ← assert/caution/inform helpers
    Logging.js                  ← Styled console logging with caller detection
    Snippets.js                 ← General utilities
  docs/                         ← Full documentation
```

---

## Further Reading

| Document | What You'll Learn |
|----------|------------------|
| `docs/ARCHITECTURE.md` | System layers, class hierarchy, initialization sequence |
| `docs/ACTORS.md` | Deep dive into Actor, Matrix, TT, PTT, NTT, prototype() |
| `docs/COMPONENTS.md` | Web component API, Formidable form generator |
| `docs/MESSAGE_PROTOCOL.md` | Every TX message type with routing examples |
| `docs/TRANSPORT.md` | NetworkAdapter, HTTP, WebSocket internals |
