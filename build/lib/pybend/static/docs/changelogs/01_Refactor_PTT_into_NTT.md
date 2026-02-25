# PTT → NTT Merge — Architecture Report

> **Status:** Complete and verified.
> **Scope:** The `PTT` class has been deleted. Its responsibilities are now split
> between `NTT` (static registry + universal router) and `DynamicClass` (per-type
> behavior: schema, instances, CRUD, Observable).

---

## Table of Contents

1. [Summary](#1-summary)
2. [What Changed](#2-what-changed)
3. [New Mental Model](#3-new-mental-model)
4. [The Null Pointer Bootstrap](#4-the-null-pointer-bootstrap)
5. [NTT as Universal ATTACH Router](#5-ntt-as-universal-attach-router)
6. [DynamicClass — The Promoted Type Actor](#6-dynamicclass--the-promoted-type-actor)
7. [prototype() Refactor](#7-prototype-refactor)
8. [File-by-File Changes](#8-file-by-file-changes)
9. [Bugs Encountered & Fixed](#9-bugs-encountered--fixed)
10. [Key Design Decisions](#10-key-design-decisions)
11. [Gotchas & Things to Know](#11-gotchas--things-to-know)

---

## 1. Summary

The PTT (Proto Transfer Type) class was a schema proxy that fetched JSON schemas
from the backend, generated `DynamicClass` subclasses of NTT, and managed entity
instance pools. But DynamicClass already held 70% of PTT's functionality
(`_schema`, `instances`, Observable mixin). This created three overlapping concepts
where two would do.

**The merge promoted DynamicClass to a full type actor, absorbed PTT's remaining
responsibilities into NTT static, and deleted PTT entirely.**

### Before (3 concepts)

```
PTT      = "the idea of a Product" (schema proxy + class factory)
NTT      = "abstract entity base" (never used directly)
Dynamic  = "the actual Product class" (generated, hidden detail)
```

### After (2 concepts)

```
NTT          = "the entity system" (registry + router + base class)
Product      = "the Product type" (a DynamicClass — type + instances)
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| Classes | 3 (PTT + NTT + DynamicClass) | 2 (NTT + DynamicClass) |
| Lines in NTT.js | ~748 | ~810 (net gain from statics, but ~190 lines of PTT deleted) |
| Schema sources of truth | 2 (PTT `#data` + DC `_schema`) | 1 (`DC._schema`) |
| Instance pools | 2 (PTT `#instances` + DC `instances`) | 1 (`DC.instances`) |
| ATTACH entry points | 2 (PTT for type, direct for instance) | 1 (`NTT.ATTACH` for both) |
| Files changed | — | 9 |

---

## 2. What Changed

### Deleted

- **`PTT` class** (~190 lines): constructor, `#instances`, `#data`, `#cls`,
  `pull()`, `SCHEMA()`, `READ()`, `UPDATE()`, `has()`, `get()`, `factory()`,
  static `ATTACH()`, static `attach()`, static `get()`, static `has()`.
- **`Actor.subclass(PTT, Observable)`** registration line.
- **`export { PTT }`** — no longer exported from NTT.js.

### Added to NTT static

| Method | Purpose |
|--------|---------|
| `#prototypes` Map | `addr → DynamicClass \| null` — the type registry |
| `#waiting` Map | `addr → TX[]` — message queue during bootstrap |
| `has(addr)` | Check if a DynamicClass exists |
| `get(addr)` | Dual lookup: `"Product"` → DC, `"Product/1"` → NTT instance |
| `attach(addr, cb)` | Imperative attach with callback (replaces `PTT.attach`) |
| `ATTACH(data, tx)` | Universal router — both type-level and instance-level |
| `SCHEMA(data, tx)` | Bootstrap completion — creates DC, replays queue, triggers READ |
| `#replayWaiting(addr, DC)` | Private helper to replay queued TXs + callbacks |

### Added to DynamicClass (inside `prototype()`)

| Method/Property | Purpose |
|-----------------|---------|
| `href` (static) | CRUD endpoint URL (e.g., `/products`) |
| `schema` (static getter) | Returns `DynamicClass._schema` |
| `_watchers` (Set) | Addresses of components watching this type |
| `_pendingAttaches` (Array) | Instance ATTACHes queued before READ completes |
| `__signals` (Set) | Static Observable signal callbacks |
| `__observers` (Map) | Static Observable observe callbacks |
| `call(method, data, meta)` | Static TX sender (no source → Actor._send assigns className) |
| `signal(callback, wait)` | Static Observable: register/fire callbacks |
| `observe(property, callback)` | Static Observable for `subscribe(this.proto, ...)` |
| `ATTACH(data, tx)` | Type-level adds watcher, instance-level forwards to child |
| `READ(data)` | Creates instances, replays pending ATTACHes, notifies watchers |
| `UPDATE(data, tx)` | Delegates to `READ` |

### Changed on NTT instance

| Area | Before | After |
|------|--------|-------|
| `ATTACH` handler | Sent DESCRIBE with `this.proto ? proto.schema() : constructor._schema` | Always uses `this.constructor._schema` |
| `set value()` | Had `if (this.#proto) {} else { this.signal() }` branch | Always calls `this.signal()` |
| `get schema()` | `return this.#proto?.schema` | `return this.constructor._schema` |
| `define(proto)` | `this.href = proto.href/hash` | Guards with `if (proto && proto.href)` |
| Registration | `Actor.subclass(NTT)` (no Observable) | `Actor.subclass(NTT, Observable)` |

---

## 3. New Mental Model

### Architecture Diagram

```
Matrix (root actor)
 ├── NTT (class) ← global registry + universal ATTACH router
 │    ├── Product (DynamicClass) ← WAS a PTT instance
 │    │    ├── static: _schema, instances, href, labels, _watchers
 │    │    ├── static: ATTACH(), READ(), UPDATE(), call(), signal(), observe()
 │    │    │
 │    │    ├── 1 (NTT instance — Product/1)
 │    │    ├── 2 (NTT instance — Product/2)
 │    │    └── ...
 │    │
 │    └── User (DynamicClass)
 │         └── ...
 │
 ├── Component (class)
 │    └── List, Item, ...
 │
 └── TT (class)
```

### How to Think About It

- **NTT** = the entity system. Global singleton with static methods.
  - "Give me the Product type" → `NTT.get("Product")` → returns DynamicClass
  - "Give me Product #1" → `NTT.get("Product/1")` → returns NTT instance
  - "Tell me when Product is ready" → `NTT.attach("Product", callback)`
  - All entity ATTACHes route through `NTT.ATTACH()`

- **DynamicClass** = the type. One per backend model. Born complete.
  - IS a class that extends NTT
  - Static level = type behavior (schema, CRUD, instance pool)
  - Instance level = entity data (per-record)

- **There is no PTT.** Stop thinking about it.

### For Documentation / AI Agents

> "NTT is the entity base class and global type registry. When you reference a
> model like 'Product', NTT fetches its schema and generates a Product class
> (extending NTT) with typed properties and methods. `NTT.get('Product')` returns
> the Product class. Product instances hold entity data."

---

## 4. The Null Pointer Bootstrap

The core innovation that makes PTT deletion possible.

### The Problem It Solves

PTT existed *before* the schema arrived — it was created synchronously, then
fetched the schema async. DynamicClass only exists *after* the schema arrives
(it needs the schema to generate typed properties and methods). If DynamicClass
IS the type, what represents the type during the async gap?

### The Solution: `null` + Message Queue

A `null` in the `#prototypes` map marks "schema is being fetched." Any TX
messages that arrive during the gap are queued and replayed once the DynamicClass
exists.

```js
static #prototypes = new Map();   // addr → DynamicClass | null
static #waiting = new Map();      // addr → TX[] | {_attachCallback}[]
```

**Three states for any model name:**

| `#prototypes.get(addr)` | Meaning | Behavior |
|--------------------------|---------|----------|
| `undefined` (not in map) | Never requested | Bootstrap: set `null`, fetch schema, queue TX |
| `null` | Schema in flight | Queue TX in `#waiting` |
| `DynamicClass` | Ready | Forward TX to DynamicClass |

### The Flow

```
Component                 NTT (static)                          Backend
─────────                 ────────────                          ───────

ATTACH "Product" ────────► ATTACH()
                             │
                             ├─ #prototypes.set("Product", null)
                             ├─ #waiting.set("Product", [tx])
                             │
                             ├─ TX {SCHEMA, source:"NTT", target: URL} ──► GET /Product
                             │
                             │  ... async gap (null in map, TXs queued) ...
                             │
                             ◄── TX {SCHEMA, target:"NTT", data: schema} ◄─ schema JSON
                             │
                             ├─ NTT.SCHEMA():
                             │   addr = data.__name__
                             │   href = config.API_URL + "/" + data.__tablename__
                             │   DC = prototype(addr, schema, href)
                             │   #prototypes.set("Product", DC)
                             │   #replayWaiting("Product", DC)
                             │   DC.call('READ', {})
                             │
                             └── DC.READ() ──────────────────────────────► GET /products
                                                                            │
                             ◄── DC.READ(data) ◄──────────────────────────── [{...}, ...]
                             │
                             ├─ Creates NTT instances
                             ├─ Replays _pendingAttaches
                             └─ Notifies _watchers → UPDATE to List

◄── UPDATE ["Product/1", "Product/2", ...]
```

### Why It Works

- **No intermediate object.** Two Map entries replace an entire TT subclass instance.
- **DynamicClass born complete.** Never half-initialized. When `prototype()` runs,
  the class has its full schema, typed properties, methods, href.
- **Schema self-identifies.** SCHEMA response routes to `NTT` (static). NTT reads
  `data.__name__` to know which model. No `meta` hacks or URL parsing.
- **Dedup is free.** Second ATTACH for same model sees `null` → just queues.
  Only one SCHEMA fetch happens.

---

## 5. NTT as Universal ATTACH Router

### Before: Split Routing

```
<ntt-list model="Product">
  → TX { ATTACH, target: "PTT", data: "Product" }      ← type-level → PTT

<ntt-item ref="Product/1">
  → TX { ATTACH, target: "Product/1" }                  ← instance-level → Matrix → DC → NTT
```

### After: Single Entry Point

```
<ntt-list model="Product">
  → TX { ATTACH, target: "NTT", data: "Product" }       ← type-level

<ntt-item ref="Product/1">
  → TX { ATTACH, target: "NTT", data: "Product/1" }     ← instance-level
```

Both route to `NTT.ATTACH()`, which extracts the model from the `data` field
(`addr.split('/')[0]`), performs the three-state dispatch, and either forwards
to the DynamicClass immediately or queues for later.

### Why This Matters

- **Components don't know about bootstrapping.** They send ATTACH to NTT. If the
  type is ready, it routes instantly. If not, it queues transparently.
- **TX replay is uniform.** Same queue, same replay for both `"Product"` and
  `"Product/1"`.
- **Preserves actor model.** NTT is the channel for entity messages. Matrix
  doesn't need special-casing.

---

## 6. DynamicClass — The Promoted Type Actor

DynamicClass was previously a "hidden detail" — a generated class that components
interacted with indirectly through PTT. Now it IS the type.

### What It Holds (Static Level)

```js
DynamicClass "Product" extends NTT {
    // ── Identity ──
    static name = "Product"           // set via Object.defineProperty
    static href = "/products"         // CRUD endpoint
    static addr = "Product"           // actor address (via Actor.subclass)

    // ── Schema ──
    static _schema = {...}            // JSON schema from backend
    static get schema() { ... }       // getter alias

    // ── Instance Pool ──
    static instances = new Map()      // id → NTT instance
    static children = new Map()       // id → NTT instance (Actor registry)

    // ── Watchers ──
    static _watchers = new Set()      // component addresses watching this type
    static _pendingAttaches = []      // instance ATTACHes waiting for READ

    // ── Observable (manual, not via mixin) ──
    static __signals = new Set()      // signal callbacks
    static __observers = new Map()    // observe callbacks

    // ── Handlers ──
    static ATTACH(data, tx)           // type vs instance routing
    static READ(data)                 // create instances, replay, notify
    static UPDATE(data, tx)           // → delegates to READ

    // ── Utilities ──
    static call(method, data, meta)   // send TX from type level
    static signal(callback, wait)     // register/fire schema-ready callbacks
    static observe(property, callback)// register property watchers
}
```

### Why Observable Is Manual at Static Level

`Observable.apply(Base)` (from `Observable.js`) adds `signal()`, `observe()`,
`notify()` to `Base.prototype` — the **instance** level. DynamicClass instances
get these automatically.

But components use the DynamicClass *itself* as `this.proto` and call
`this.proto.signal(callback)` and `this.subscribe(this.proto, 'UPDATE', ...)`.
These are static-level calls. So `signal`, `observe` must exist as own properties
on the DynamicClass function object — added manually in `prototype()`.

### DynamicClass.call() — No Source on Purpose

```js
DynamicClass.call = function(method, data = {}, meta = {}) {
    DynamicClass.send(new TX({
        name: method,
        target: DynamicClass.href,    // e.g., "http://.../products"
        data: data,
        meta: meta,
    }));
};
```

Note: **no `source` field**. This is intentional.

When `Actor._send()` processes the TX, it doesn't find `target` as a direct child
(it's a URL, not an address), so it hits Case 3 (bubble to ROOT_ACTOR) and assigns
`source = DynamicClass.addr` (e.g., `"Product"`). If we set `source: DynamicClass.addr`
ourselves, the bubble would *prefix* it again → `"Product/Product"`. Omitting
source lets the routing assign it correctly.

---

## 7. prototype() Refactor

### Signature Change

```js
// Before:
function prototype(ptt) { ... }

// After:
function prototype(addr, schema, href) { ... }
```

No longer receives a PTT instance. Receives the raw pieces directly from
`NTT.SCHEMA()`.

### Key Internal Changes

| Area | Before | After |
|------|--------|-------|
| Constructor | `this.href = ptt.href / this.id` | `this.href = ${href}/${this.id}` |
| Class name | `DynamicClass.name` set, + `DynamicClass.proto = ptt` | `DynamicClass.name` set, + `DynamicClass.href = href` |
| Logging | `console.error(...)` | `console.log(...)` |
| Static methods | None | `call`, `signal`, `observe`, `ATTACH`, `READ`, `UPDATE` |
| Static state | None | `_watchers`, `_pendingAttaches`, `__signals`, `__observers` |

### What Stays the Same

- Field loop (typed getters/setters per schema property)
- Method loop (backend RPC methods per schema method)
- `Actor.subclass(DynamicClass, Observable)` at the end
- Instance-level `value` getter/setter with `@context`/`@type` injection

---

## 8. File-by-File Changes

### `core/NTT.js` — The Big One

- TT class: untouched (whitespace only)
- PTT class: **deleted entirely** (~190 lines)
- NTT class: expanded with static registry + handlers (~100 lines added)
- `prototype()`: refactored signature + ~140 lines of static methods added
- Registration: `Actor.subclass(PTT, Observable)` → removed;
  `Actor.subclass(NTT)` → `Actor.subclass(NTT, Observable)`

### `components/ntt-element.js`

| Change | Detail |
|--------|--------|
| Import | `{PTT}` → `{NTT}` |
| `ref` setter | `target: href` → `target: 'NTT', data: href` |
| `attributeChangedCallback` | `target: 'PTT'` → `target: 'NTT'` |
| `attach()` method | `PTT.attach(addr, ...)` → `NTT.attach(addr, ...)` |

### `components/ntt-list.js`

Removed unused `import { PTT } from '../core/NTT.js'`.

### `components/ntt-item.js`

Removed unused `import { PTT } from '../core/NTT.js'`.

### `components/ntt-method.js`

| Change | Detail |
|--------|--------|
| Import | `{PTT}` → `{NTT}` |
| Line 35 | `PTT.get(this.model)` → `NTT.get(this.model)` |
| Line 68 | `PTT.get(this.forward)` → `NTT.get(this.forward)` |

### `generators/form.js`

| Change | Detail |
|--------|--------|
| Line 3 | `PTT.get(ref)` → `NTT.get(ref)` |
| Error msg | `"No PTT found"` → `"No NTT found"` |

### `core/Component.js`

Removed unused `import {PTT} from './NTT.js'`.

### `matrix.html`

`import { PTT }` → `import { NTT }`. Updated commented-out code references.

### `schema.html`

| Change | Detail |
|--------|--------|
| Import | `{PTT}` → `{NTT}` |
| Line 124 | `PTT.attach(addr, ...)` → `NTT.attach(addr, ...)` |

### Not Changed

- **`example.html`** — old standalone test page with extensive PTT usage. Not part
  of the active framework. Left as-is.
- **`Actor.js`**, **`Observable.js`**, **`Matrix.js`**, **`TX.js`** — no changes needed.

---

## 9. Bugs Encountered & Fixed

### Bug 1: Watcher Address Corruption During Queue Replay

**Symptom:** `[Actor.Product_send] Cannot route message to target: List. No such child actor.`

**Root Cause:** In `#replayWaiting`, queued TXs still had `target: "NTT"` (the
original routing target). When `DC.inbox` received them, the target didn't match
`DC.addr` ("Product"), so the TX bubbled back through `DC._send` → ROOT_ACTOR.
During the bubble, `Actor._send` Case 3 prefixed the source with `"Product/"`,
turning `"List/List-xxx"` into `"Product/List/List-xxx"`. Later, when `DC.READ`
sent UPDATE to this corrupted watcher address, `DC._send` tried to route via
Case 2 (prefix match) and failed because `"List"` is not a child of Product.

**Fix:** In `#replayWaiting`, rewrite the TX `target` before replay:

```js
repr.target = typeof repr.data === 'string' ? repr.data : addr;
```

This ensures `DC.inbox` dispatches locally instead of bouncing.

### Bug 2: $defs Double-Create

**Symptom:** `prototype()` called twice for "Product", creating duplicate DynamicClasses.

**Root Cause:** Backend schema `$defs` includes "Product" as a sub-entry alongside
the main "Product" schema. Without a guard, the $defs loop would call `prototype()`
for the same model that NTT.SCHEMA was about to create.

**Fix:** Added `if (key === addr) continue;` in the $defs loop to skip the main model.

---

## 10. Key Design Decisions

### 1. Null Pointer Over Pending Objects

A `null` in the map + a TX array is simpler than callback registries, pending
entry objects, or stub classes. The actor system's own message passing handles
notification via TX replay.

### 2. Universal ATTACH Router

Making NTT handle both type-level and instance-level ATTACHes eliminates the
split routing and ensures all entity lookups are queued during the bootstrap
gap — including standalone `<ntt-item>` elements that request specific instances.

### 3. DynamicClass Born Complete

By moving schema fetch and bootstrap to NTT static, DynamicClass never exists in
a half-initialized state. When `prototype()` runs, the class has everything it
needs from the start.

### 4. Static Observable (Manual)

Observable.apply only targets `Base.prototype` (instances). The DynamicClass needs
static-level `signal`/`observe`/`call` for when components use it as `this.proto`.
These are added as own properties on the class function object inside `prototype()`.

### 5. DynamicClass.call() Without Source

If `source` were set to `DynamicClass.addr`, Actor._send's Case 3 bubble would
prefix it again → `"Product/Product"`. Leaving `source` unset lets the routing
assign it correctly during the bubble.

### 6. Two Queues, Two Purposes

- `NTT.#waiting` — queues TXs *before* the DynamicClass exists (during SCHEMA fetch).
  Replayed by `NTT.SCHEMA` → `#replayWaiting`.
- `DynamicClass._pendingAttaches` — queues instance-level ATTACHes *after* the DC
  exists but *before* READ returns instances. Replayed inside `DynamicClass.READ`.

---

## 11. Gotchas & Things to Know

### NTT.get() Is Dual-Purpose

```js
NTT.get("Product")    // → DynamicClass (the type)
NTT.get("Product/1")  // → NTT instance (splits on '/', looks up in DC.children)
```

This replaces both `PTT.get(addr)` (type lookup) and `ptt.get(id)` (instance lookup).

### DynamicClass Has Two Instance Maps

Both `DynamicClass.instances` and `DynamicClass.children` hold NTT instances:
- `instances` — business-level map, keyed by entity ID
- `children` — actor-level map (from `Actor.subclass`), also keyed by entity ID

These are populated by different paths (`READ` sets `instances`, `Actor.register`
sets `children` in the constructor). They should stay in sync but are separate maps.

### Schema Response Routes to NTT, Not to a Model

The SCHEMA fetch TX has `target: URL` (routed via NetworkAdapter) and
`source: "NTT"`. The response comes back as `TX { target: "NTT", name: "SCHEMA" }`.
NTT.SCHEMA reads `data.__name__` to determine which model it's for. No URL
parsing or meta-routing needed.

### Pre-existing Issue: NTT Instance `#data` vs DynamicClass `_data`

NTT base class has private `#data`. DynamicClass overrides with public `_data`.
The `update()` method on NTT reads `this.#data` (the NTT private field), but
DynamicClass instances store data in `_data`. This was pre-existing and was
intentionally left unfixed to avoid scope creep. Functionally it works because
DynamicClass overrides the `value` getter/setter to use `_data`.

### `example.html` Still Has PTT References

The file `example.html` is an old standalone test page, not part of the active
framework. It was intentionally left unchanged. If it needs to work again, its
PTT references will need updating.
