# N3TX Package Architecture

Module boundaries, dependency analysis, and packaging strategy for the N3TX frontend framework and its N3TX backend.

**Related:** `UI_SEPARATION_CONCERNS.md` covers the component-layer refactor in detail. This document focuses on the broader question of how the entire system should be organized into distributable units.

---

## 1. System Overview

### What N3TX Is

N3TX (Named Transfer Type) is a schema-driven frontend framework built on vanilla JS Web Components. It pairs with a Python/FastAPI backend (N3TX) where **model definitions are the single source of truth**. The backend publishes JSON Schemas for every model. The frontend fetches these schemas at runtime, creates typed entity classes, and renders UI components that stay in sync via a message bus.

The framework's goal is to make storage, fetching, state management, and rendering automatic — replacing the need for Redux, fetch(), React, GraphQL, and similar tools. Developers define models on the backend and get a working UI with minimal frontend code.

### Architecture Layers

The system has five distinct functional layers, listed from lowest (no dependencies) to highest (depends on everything below):

```
┌─────────────────────────────────────────────┐
│  Kit: NTTItem, NTTList, NTTMethod,          │  Zero-config defaults
│       Formidable form generator             │  "Drop in HTML, it works"
├─────────────────────────────────────────────┤
│  Components: Component, NTTElement,         │  Web Component base classes
│              ListElement                    │  Developer extends these
├─────────────────────────────────────────────┤
│  Core: N3TX, TT, DynamicClass,              │  Schema-driven data layer
│        Transport (HTTP, WebSocket)          │  Framework-agnostic
├─────────────────────────────────────────────┤
│  Actor: Actor, Matrix, TX, Observable       │  Message-passing infrastructure
│                                             │  General-purpose, no DOM
├─────────────────────────────────────────────┤
│  Utils: Assert, Logging, Utils, config      │  Pure utilities
└─────────────────────────────────────────────┘
```

### Backend (N3TX)

```
N3TX (Python/FastAPI)
  models/proto_model.py    ProtoModel base class, schema generation (via proto_schema pipeline), model_response()
  models/storable_mixin.py CRUD operations (create/get/list/update/delete)
  models/*_model.py        Domain models (Product, Comment, Like, etc.)
  storage/                 SQLite backend with FK hydration, migrations
  api/routes_fastapi.py    Auto-generated CRUD routes from registered models
  utils/decorators.py      @expose_route() for custom method endpoints
  utils/registrar.py       Model registry
  config.py                HOST, PORT, API_URL
  main.py                  App entry point
```

---

## 2. Current File Structure and Import Graph

### Frontend Files

```
static/
  config.js                     Configuration (API_URL, event constants)

  core/
    Actor.js                    Actor base class, subclass(), message routing
    Matrix.js                   Root actor, message bus, dispatch
    N3TX.js                      TT + N3TX + DynamicClass factory (prototype())
    TX.js                       Transaction/event format
    Observable.js               Signal/observe mixin
    Component.js                HTMLElement + Actor bridge (to be merged)
    Utils.js                    Pure utility functions
    transport/
      HTTP.js                   HTTP client (GET/POST/PUT/DELETE)
      Socket.js                 WebSocket client with reconnect
      NetworkAdapter.js         Transport abstraction layer

  components/
    ntx-element.js              Entity-aware base component (to be merged with Component)
    ntx-item.js                 Single entity display/edit (<ntx-item>)
    ntx-list.js                 Collection display (<ntx-list>)
    ntx-method.js               Method invocation buttons (<ntx-method>)

  generators/
    form.js                     Formidable: schema-to-HTML form generator

  utils/
    Assert.js                   Runtime assertions
    Logging.js                  Styled console logging
    registrar.js                Legacy callback registry (unused in v0.8)
```

### Dependency Graph

Arrows mean "imports from". No arrow means no dependency.

```
config.js ──────────────────────────────────────── (imported by everything)

Utils.js ───────────────────────────────────────── (no imports)
Assert.js ← config
Logging.js ← config

TX.js ← Assert, Utils, config

Actor.js ← Assert, Logging, TX

Observable.js ← Actor, Assert

Matrix.js ← Actor, TX, NetworkAdapter, Assert, Logging, config
  └── NetworkAdapter.js ← HTTP.js, Socket.js, Assert, Utils, config, Logging
        ├── HTTP.js ─────────────────────────────── (no imports)
        └── Socket.js ← Logging

N3TX.js ← Actor, Matrix, TX, Observable, NetworkAdapter, Assert, Utils, Logging, config
  └── prototype() creates DynamicClass (extends N3TX, applies Actor.subclass + Observable)

Component.js ← Actor, Matrix, TX, Utils, Logging, [ntx-item.js ← CIRCULAR]

ntx-element.js ← Component, N3TX, TX, Matrix, Utils, Logging, [ntx-item.js ← CIRCULAR]

ntx-item.js ← ntx-element, N3TX, ntx-method, Formidable, TX, Assert, Logging
ntx-list.js ← ntx-element, ntx-item, Observable, Actor, Utils, Logging
ntx-method.js ← N3TX

form.js ← (no explicit imports, uses global N3TX — missing import bug)
```

### Circular Dependencies

1. **Component.js ↔ ntx-item.js**: Component.js has `import '../components/ntx-item.js'` (side-effect import for `customElements.define`). ntx-item.js imports Component.js through ntx-element.js. Managed by JS module system but architecturally wrong — a base class importing a grandchild. **Resolved by the component refactor** (see UI_SEPARATION_CONCERNS.md).

2. **form.js → N3TX (implicit global)**: Formidable calls `N3TX.get()` without importing N3TX. Works because `window.N3TX = N3TX` is set in N3TX.js, but fragile. Needs an explicit import.

---

## 3. Natural Package Boundaries

The dependency graph reveals four clean tiers with no upward imports between them. Each tier could be an independent package.

### Tier 1: `@ntt/actor` — General-Purpose Actor System

**Files:**
```
Actor.js, Matrix.js, TX.js, Observable.js
+ Utils.js, Assert.js, Logging.js, config.js (shared utilities)
```

**What it provides:**
- Actor base class with address-based identity
- `Actor.subclass(Type)` stamps messaging capabilities onto any class
- Matrix: root actor, message routing (local children → parent hierarchy → root)
- TX: typed transaction format (name, source, target, data, meta)
- Observable: mixin adding signal/observe/notify to any Actor
- No DOM dependency, no schema knowledge, no HTTP/WebSocket

**Who would use this alone:**
- Developers wanting a message-passing actor model in the browser
- Game developers, real-time collaborative UIs, event-driven architectures
- Could run in Node/Deno (Matrix doesn't assume browser APIs)

**Independent value: HIGH.** Actor model implementations in vanilla JS are rare. This is a genuinely reusable library.

**Dependency: None** (only shared utils).

### Tier 2: `@ntt/core` — Schema-Driven Data Layer

**Files:**
```
N3TX.js (TT, N3TX, prototype()/DynamicClass factory)
transport/HTTP.js, transport/Socket.js, transport/NetworkAdapter.js
```

**What it provides:**
- TT (Transfer Type): base entity class with href, watch/notify, remote call()
- N3TX: global schema registry, ATTACH/SCHEMA protocol, DynamicClass lifecycle
- `prototype()`: factory that creates a typed DynamicClass from a JSON Schema
  - Property accessors with type checking from schema
  - Method proxies for schema-defined methods
  - Instance management (create/update/track)
  - Watcher pattern (components subscribe, get notified on data changes)
- Transport: HTTP client, WebSocket client, NetworkAdapter abstraction
- No DOM dependency, no rendering knowledge

**Who would use this alone (with `@ntt/actor`):**
- React/Vue/Svelte developers with a N3TX backend who want schema-driven data without N3TX's web components
- Anyone wanting automatic entity management from JSON Schema

**Example standalone usage:**
```js
import { N3TX } from '@ntt/core';
import { matrix } from '@ntt/actor';

// React component using N3TX data layer
function ProductList() {
  const [products, setProducts] = useState([]);

  useEffect(() => {
    N3TX.attach('Product', (DynamicClass) => {
      DynamicClass.observe('UPDATE', (data) => setProducts(data));
      DynamicClass.call('READ', {});
    });
  }, []);

  return products.map(p => <div key={p.id}>{p.name}</div>);
}
```

**Independent value: MEDIUM-HIGH.** The "schema from backend, typed data just works" story is valuable regardless of rendering framework. This is the part that replaces Redux + fetch + GraphQL.

**Dependency:** `@ntt/actor`

### Tier 3: `@ntt/components` — Web Component Base Classes

**Files (after component refactor):**
```
Component.js     — Merged base: HTMLElement + Actor + schema resolution
NTTElement.js    — Single entity base class
ListElement.js   — Collection base class
```

**What it provides:**
- Component: the bridge between HTMLElement and the N3TX data layer
  - Shadow DOM setup with stylesheet hook (`get styles()`)
  - Actor identity (addr, hash, Matrix registration)
  - Schema resolution: `model` attribute → ATTACH TX → N3TX core → `define(proto)` → `definedCallback()`
  - Ref resolution: `ref` attribute → ATTACH/READ TX
  - Value storage (getter/setter)
  - Display mode via ResizeObserver (`displayMode` property for adaptive rendering)
  - Abstract `render()` contract
- NTTElement: single entity lifecycle
  - Default value: `{}` (object)
  - Message handlers: UPDATE, DESCRIBE, READ
  - `save()` sends UPDATE TX back to backend
  - Auto-render on value change when schema is ready
- ListElement: collection lifecycle
  - Default value: `[]` (array)
  - Triggers collection READ on proto definition
  - Stamps child components per item
  - `get childTag()` hook, slot-based template support
  - `item-tag` attribute for HTML-level customization

**Who would use this:**
- Developers building custom web components for their domain with N3TX
- The primary "developer API" of the framework

**Example usage:**
```js
import { NTTElement } from '@ntt/components';

class InvoiceCard extends NTTElement {
  get styles() { return './invoice-card.css'; }
  render() {
    const { number, total, status } = this.value;
    this.shadowRoot.innerHTML = `
      <div class="invoice">
        <h2>#${number}</h2>
        <span class="total">$${total}</span>
        <span class="status ${status}">${status}</span>
      </div>
    `;
  }
}
customElements.define('invoice-card', InvoiceCard);
```

**Independent value: HIGH within the N3TX ecosystem.** This is the layer most developers interact with.

**Dependency:** `@ntt/core`

### Tier 4: `@ntt/kit` — Batteries-Included Defaults

**Files:**
```
ntx-item.js      — Zero-config entity component (auto-renders via Formidable)
ntx-list.js      — Zero-config collection component
ntx-method.js    — Method invocation buttons
Formidable.js    — Schema-to-HTML form generator (renamed from form.js)
```

**What it provides:**
- NTTItem: extends NTTElement with Formidable-powered auto-rendering, edit/save toggle, input binding, method button rendering. Registered as `<ntx-item>`.
- NTTList: extends ListElement with zero configuration. Registered as `<ntx-list>`.
- NTTMethod: renders callable methods from schema as buttons with parameter forms. Registered as `<ntx-method>`.
- Formidable: schema-to-HTML generator
  - `getForm(ntt, mode)` — full form from schema properties
  - `getInput(ntt, key, mode)` — individual field rendering
  - `getListInput()` — array/reference field rendering
  - Support for text, number, boolean, checkbox, textarea, array, $ref, selfref types

**Who would use this:**
- Rapid prototyping, admin panels, internal tools
- Getting started with N3TX (zero frontend code needed)
- Reference implementations for developers building custom components

**Example usage (HTML-only, zero JS):**
```html
<ntx-list model="Product"></ntx-list>
<!-- That's it. Schema fetched, data loaded, list rendered, items editable. -->
```

**Independent value: MEDIUM.** Essential for the "wow" demo and rapid development. Most production apps override pieces of it with custom components.

**Dependency:** `@ntt/components`

### Tier 5: Add-ons (Optional)

**`@ntt/preload`** — SSR/Pre-loading:
- Patches N3TX.ATTACH to check for inline `<script type="application/json" data-ntx-schema="...">` before making network requests
- Eliminates the two round-trips (schema fetch + data fetch) for server-rendered pages
- Backend renders HTML with pre-loaded JSON; frontend hydrates instantly
- **Dependency:** `@ntt/core` (patches N3TX behavior)

**`@ntt/scaffold`** — Code Generation:
- CLI tool or API endpoint that reads a model's schema and generates starter component files
- Produces a working component with explicit render() that the developer customizes
- Dev-time only, never shipped to production
- **Dependency:** `@ntt/core` (reads schema), file system access

---

## 4. What Should vs Should Not Be Split

### Split (clear independent value):

| Boundary | Why separate | Standalone consumer? |
|---|---|---|
| `@ntt/actor` | General-purpose actor model, no schema/DOM coupling | Game devs, event architectures, any message-passing app |
| `@ntt/core` | Schema-driven data layer, rendering-framework-agnostic | React/Vue/Svelte developers using N3TX backend |
| `@ntt/components` | DOM-specific base classes developers extend | N3TX web component developers |
| `@ntt/kit` | Opinionated defaults that shouldn't be in the base | Rapid prototyping, admin panels |
| `@ntt/preload` | Deploy-time optimization, not universally needed | Server-rendered N3TX apps |
| `@ntt/scaffold` | Dev-time tooling, never shipped to production | Developers generating starter components |

### Do NOT split (too coupled or too small):

| What | Why keep together |
|---|---|
| Adaptive rendering + `@ntt/components` | `displayMode` belongs on Component base. ResizeObserver is cheap; every component benefits; costs nothing if unused. |
| Transport + `@ntt/core` | NetworkAdapter only speaks N3TX's TX protocol. Useless without N3TX. |
| Formidable + `@ntt/kit` | Formidable only exists to serve NTTItem's auto-render. No standalone consumer. |
| Backend UI schema extensions + N3TX | ~30-40 lines in ProtoModel.schema(). Not worth a package boundary. |
| Observable + `@ntt/actor` | Tightly integrated mixin applied via Actor.subclass(). No value alone. |
| Utils/Assert/Logging + any tier | Shared utilities. Duplicating them across packages adds bloat. Ship as internal shared dependency or include in `@ntt/actor` (lowest tier). |

---

## 5. The Backend: Don't Split

All backend enhancements belong in the existing `n3tx` package:

**Schema UI extensions** (`__ui__` class variable, `json_schema_extra` ui keys):
- Adds ~30 lines to `ProtoModel.schema()` method
- Too small for its own package
- Tightly coupled to schema generation which is core to ProtoModel

**Scaffolding** (code generation from schema):
- Reads models from the same codebase it's scaffolding for
- Best as a CLI subcommand: `python -m n3tx scaffold Product`
- Or a dev-mode API endpoint: `GET /Product?scaffold=item`

**Schema pre-loading helper** (server-side template rendering):
- A FastAPI utility that inlines schema + data into HTML responses
- Lives alongside the existing route factories in `api/`

The backend is a single coherent unit. Its models, storage, routes, and schema generation are tightly coupled by design — the schema IS the model.

---

## 6. Dependency Rules

Each package tier may only import from tiers below it. Never upward.

```
@ntt/kit        → @ntt/components, @ntt/core, @ntt/actor
@ntt/components → @ntt/core, @ntt/actor
@ntt/core       → @ntt/actor
@ntt/actor      → (nothing)
@ntt/preload    → @ntt/core
@ntt/scaffold   → @ntt/core (reads schema)
```

**Violations in current code (to fix during refactor):**
1. `Component.js` imports `ntx-item.js` (tier 3 importing tier 4) — dies in refactor
2. `form.js` uses global `window.N3TX` without import — needs explicit import from `@ntt/core`
3. `ntx-list.js` calls `Actor.subclass(List)` directly (tier 4 reaching into tier 1 internals) — unnecessary, inherited through Component

---

## 7. Practical Strategy: Monorepo with Clean Boundaries

**Don't publish 5+ npm packages today.** Instead, organize as if they're separate packages — clean directory boundaries, barrel exports, enforced dependency direction — and ship as one until there's demand for independent use.

### Target Directory Structure

```
ntt/
  actor/                    ← @ntt/actor boundary
    index.js                  Barrel: exports Actor, Matrix, TX, Observable
    Actor.js
    Matrix.js
    TX.js
    Observable.js

  core/                     ← @ntt/core boundary
    index.js                  Barrel: exports N3TX, TT
    N3TX.js
    transport/
      index.js
      HTTP.js
      Socket.js
      NetworkAdapter.js

  components/               ← @ntt/components boundary
    index.js                  Barrel: exports Component, NTTElement, ListElement
    Component.js              Merged base (HTMLElement + Actor + schema)
    NTTElement.js             Single entity base class
    ListElement.js            Collection base class

  kit/                      ← @ntt/kit boundary
    index.js                  Barrel: exports NTTItem, NTTList, NTTMethod, Formidable
    ntx-item.js               Zero-config entity component
    ntx-list.js               Zero-config list component
    ntx-method.js             Method buttons
    Formidable.js             Schema-to-HTML generator

  addons/
    preload.js              ← @ntt/preload
    adaptive.js             ← Mixin for display mode (may move to components/)

  utils/                    ← Shared internals (not a public package)
    Assert.js
    Logging.js
    Utils.js

  config.js
```

### Barrel Exports

Each directory exposes a clean public API:

```js
// actor/index.js
export { default as Actor } from './Actor.js';
export { Matrix, matrix } from './Matrix.js';
export { default as TX } from './TX.js';
export { default as Observable } from './Observable.js';

// core/index.js
export { N3TX } from './N3TX.js';
export { NetworkAdapter } from './transport/NetworkAdapter.js';

// components/index.js
export { Component } from './Component.js';
export { NTTElement } from './NTTElement.js';
export { ListElement } from './ListElement.js';

// kit/index.js
export { NTTItem } from './ntx-item.js';
export { NTTList } from './ntx-list.js';
export { NTTMethod } from './ntx-method.js';
export { Formidable } from './Formidable.js';
```

### Entry Points

HTML files import from barrel exports:

```html
<!-- Minimal: just the data layer (for React/Vue integration) -->
<script type="module">
  import { N3TX } from './core/index.js';
</script>

<!-- Standard: custom components -->
<script type="module">
  import { NTTElement, ListElement } from './components/index.js';
</script>

<!-- Full: zero-config defaults -->
<script type="module">
  import './kit/index.js';  // Registers <ntx-item>, <ntx-list>, <ntx-method>
</script>
<ntx-list model="Product"></ntx-list>
```

### When to Extract to Actual Packages

Extract a tier to its own npm package when:
1. **An external consumer appears** — someone wants `@ntt/actor` without the rest
2. **Version cadence diverges** — actor system stabilizes while components iterate rapidly
3. **Bundle size matters** — tree-shaking isn't enough and consumers need to avoid loading unused tiers

Until then, the directory structure IS the package boundary. Extraction is mechanical: move directory, add `package.json`, publish. No code changes needed because imports already respect the boundary.

---

## 8. Enhancement Features by Package

The following enhancements are planned (see UI_SEPARATION_CONCERNS.md for component-level detail). Each belongs to a specific package tier:

| Enhancement | Package | Description |
|---|---|---|
| UI hints in schema | Backend (n3tx) | `__ui__` class variable and `json_schema_extra` ui keys on fields. Schema emits `ui` section with groups, field_order, widget types, display modes. |
| Slot-based list templates | `@ntt/components` (ListElement) | `<template item-template>` in light DOM provides child element template. Resolution chain: template > `item-tag` attr > `childTag` property > schema hint > `'ntx-item'` fallback. |
| Schema renderer hint | `@ntt/components` + backend | Schema `ui.renderer.item` / `ui.renderer.list` suggests which component tag to use. Part of the slot resolution chain. |
| Schema pre-loading | `@ntt/preload` addon | N3TX.ATTACH checks for inline `<script data-ntx-schema>` before network fetch. Eliminates async bootstrap latency. |
| Adaptive rendering | `@ntt/components` (Component) | ResizeObserver on Component base exposes `displayMode` (page/card/list-item/chip). Schema `ui.display_modes` defines which fields per mode. |
| Field exclusion | Backend + `@ntt/kit` (Formidable) | Schema `ui.display: false` per field + conventions (`*_id`, `id`, timestamps). Formidable checks before rendering. |
| Template scaffolding | `@ntt/scaffold` CLI tool | Generates starter component files from schema. Dev customizes from working code instead of writing from scratch. |
| Schema-driven validation | `@ntt/kit` (Formidable) | Auto-applies HTML5 validation attributes (required, min, max, pattern) from schema constraints. |
| Field-level permissions | `@ntt/components` + backend | Schema `access` per field. Component disables/hides fields based on user role. |
| Relationship rendering | `@ntt/kit` (Formidable) | ListRef fields auto-render as nested `<ntx-list>` scoped to parent. |

---

## 9. The One Split to Do Now

Before the full directory reorganization, make one structural change: **separate `actor/` from `core/`**.

This is the highest-value boundary because:

1. **The Actor system has genuine independent utility** beyond N3TX and N3TX
2. **It's the only layer with zero DOM dependency** — could run server-side
3. **It forces clean interfaces** between messaging infrastructure and schema concerns
4. **N3TX.js currently imports Actor, Matrix, TX, Observable directly** — moving these to `actor/` makes the dependency explicit via an import path change

Everything else can remain as directory boundaries within the existing structure, to be reorganized when the component refactor (UI_SEPARATION_CONCERNS.md) is implemented.
