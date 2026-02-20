# NTT UI Primitives Enhancement Plan

A comprehensive plan to evolve the NTT frontend component layer into a developer-friendly framework that provides composable, schema-driven primitives — making tools like Redux, fetch(), React, and GraphQL redundant for most use cases.

**Companion document**: `01_UI_SEPARATION_CONCERNS.md` covers the component refactor analysis (P0).
**Changelog**: `changelogs/02_Component_Layer_Refactor.md` documents the completed P0 implementation.

---

## Table of Contents

1. [System Context](#1-system-context)
2. [Current Component Layer (Before)](#2-current-component-layer-before)
3. [Component Refactor (P0 Foundation)](#3-component-refactor-p0-foundation)
4. [Enhancement: Schema UI Extensions (Backend)](#4-enhancement-schema-ui-extensions-backend)
5. [Enhancement: Slot-Based Child Templates](#5-enhancement-slot-based-child-templates)
6. [Enhancement: Schema Renderer Hints](#6-enhancement-schema-renderer-hints)
7. [Enhancement: SSR Pre-Loading](#7-enhancement-ssr-pre-loading)
8. [Enhancement: Adaptive Display Modes](#8-enhancement-adaptive-display-modes)
9. [Enhancement: Field Exclusion Conventions](#9-enhancement-field-exclusion-conventions)
10. [Enhancement: Scaffolding / Template Generation](#10-enhancement-scaffolding--template-generation)
11. [Enhancement: Schema-Driven Validation](#11-enhancement-schema-driven-validation)
12. [Enhancement: Schema-Driven Permissions](#12-enhancement-schema-driven-permissions)
13. [Enhancement: Relationship-Aware Smart Defaults](#13-enhancement-relationship-aware-smart-defaults)
14. [Synthesis: Three Enhancement Layers](#14-synthesis-three-enhancement-layers)
15. [Priority & Sequencing](#15-priority--sequencing)
16. [Implementation Directives](#16-implementation-directives)

---

## 1. System Context

### What PyBend/NTT Is

PyBend is a schema-driven full-stack framework. The backend (Python/FastAPI) defines data models that automatically generate JSON Schemas, API routes, and CRUD operations. The frontend (vanilla JS Web Components) fetches these schemas at runtime, creates typed entity classes, and renders UI components that stay synchronized via a message bus.

The core philosophy: **the model definition is the single source of truth**. Everything flows from it — database schema, API endpoints, JSON Schema, frontend types, and (with this enhancement plan) UI rendering.

### Key Backend Files

| File | Role |
|---|---|
| `src/pybend/core/models/proto_model.py` | Base model class. Generates JSON Schema via `schema()`. Injects `StorableMixin` for DB ops. `model_dump(response=True)` adds `$schema`/`$id` metadata. |
| `src/pybend/core/models/storable_mixin.py` | CRUD operations (create/get/list/update/delete) |
| `src/pybend/core/models/ref.py` | `ListRef[T]` type for collection references |
| `src/pybend/core/utils/typer.py` | `Ref[T]` type for foreign keys, `Ref['self']` for self-referencing |
| `src/pybend/core/utils/decorators.py` | `@expose_route()` marks methods as API endpoints |
| `src/pybend/core/api/routes_fastapi.py` | Auto-generates CRUD routes from registered models |
| `src/pybend/core/config.py` | `HOST`, `PORT`, `API_URL`, `SQLITE_DB_FILE` |
| `src/pybend/core/main.py` | App entry: registers models, starts server |

### Key Frontend Files

| File | Role |
|---|---|
| `static/NTT0.6/core/NTT.js` | Core entity system. `NTT` class = schema registry + instance manager. `prototype()` factory creates DynamicClasses from schema. |
| `static/NTT0.6/core/Matrix.js` | Root actor / message bus. Routes TXs between actors. |
| `static/NTT0.6/core/Actor.js` | Actor base. `Actor.subclass(Type)` stamps `send`/`inbox`/`register`/`children` onto any class. |
| `static/NTT0.6/core/Observable.js` | Mixin: `signal()`, `observe()`, `notify()` for reactivity. |
| `static/NTT0.6/core/TX.js` | Transaction (message) class: `{name, source, target, data, meta}`. |
| `static/NTT0.6/core/Component.js` | **Unified base class** (merged HTMLElement + Actor bridge + schema resolution). All components inherit from this. |
| `static/NTT0.6/components/NTTElement.js` | **Single entity base class**. Handles UPDATE/DESCRIBE/READ handlers, save(), value auto-render. |
| `static/NTT0.6/components/ListElement.js` | **Collection base class**. Handles collection fetch, UPDATE handler, childTag/template resolution. |
| `static/NTT0.6/components/ntt-item.js` | Built-in default item (extends NTTElement). Formidable auto-render + edit toggle. |
| `static/NTT0.6/components/ntt-list.js` | Built-in default list (extends ListElement). Zero-config grid of children. |
| `static/NTT0.6/components/ntt-method.js` | Renders callable methods as buttons. Unchanged. |
| `static/NTT0.6/generators/form.js` | Formidable: schema-driven form/field generator. |
| `static/NTT0.6/config.js` | `API_URL`, event name constants, logging flags. |

### Example Backend Model

```python
# src/pybend/core/models/product_model.py
class Product(ProtoModel):
    __tablename__: ClassVar[str] = 'products'
    __storable__: ClassVar[bool] = True
    name: str
    price: float
    description: str = ''
    comments: Optional[ListRef[Comment]] = Field(default=[], description="List of comments")
    id: Optional[int] = Field(default=None)

    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment) -> str:
        comment.save()
        return comment.model_dump_json()
```

### Schema Output (approximate, from `Product.schema()`)

```json
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Product",
  "__name__": "Product",
  "__tablename__": "products",
  "title": "Product",
  "type": "object",
  "properties": {
    "name": {"type": "string", "title": "Name"},
    "price": {"type": "number", "title": "Price"},
    "description": {"type": "string", "title": "Description", "default": ""},
    "comments": {"type": "array", "items": {"$ref": "#/$defs/Comment"}},
    "id": {"anyOf": [{"type": "integer"}, {"type": "null"}], "title": "Id", "default": null}
  },
  "required": ["name", "price"],
  "methods": {
    "comment": {
      "route": "/comment",
      "methods": ["POST"],
      "scope": "instancemethod",
      "parameters": {"comment": {"$ref": "#/$defs/Comment"}},
      "returns": {"type": "string"}
    }
  },
  "access": { ... },
  "$defs": {
    "Comment": {
      "$id": "http://localhost:5000/Comment",
      "properties": { ... },
      "methods": { ... }
    }
  }
}
```

### Data Flow: Full Request Lifecycle

```
1. <ntt-list model="Product">           Component appears in DOM
2. attributeChangedCallback('model')     Sends ATTACH TX → target: 'NTT'
3. NTT.ATTACH("Product")                Static handler checks #prototypes registry:
   - undefined → first time → set null, send SCHEMA TX to backend
   - null → schema in flight → queue TX
   - DynamicClass → ready → forward TX
4. NetworkAdapter                        GET /Product → receives JSON Schema
5. NTT.SCHEMA(data)                     Creates DynamicClass via prototype()
   - Registers nested $defs models
   - Replays queued ATTACHes
   - Triggers DynamicClass.call('READ')  → GET /products
6. DynamicClass.READ(data)              Creates NTT instances per record
   - Notifies all watchers with instance addresses
7. List.UPDATE([addrs])                 Receives address array, renders grid
8. <ntt-item ref="Product/1">           Stamped per address
9. NTT instance.ATTACH(tx)             Instance responds with DESCRIBE TX
10. Item.DESCRIBE({proto, data})         Sets schema + value, renders
```

### Actor / Message System

Every class that participates in messaging gets `Actor.subclass(Type)` applied. This stamps:
- **Static**: `Type.addr`, `Type.children` (Map), `Type.send(tx)`, `Type.inbox(tx)`, `Type.register(actor)`
- **Instance**: `this.addr`, `this.children`, `this.send(tx)`, `this.inbox(tx)`

Messages are TX objects: `{name, source, target, data, meta}`. Routing: Matrix (root) dispatches to children by address. If a target matches a child, it's delivered directly. If not, NetworkAdapter sends it to the backend.

**Convention**: A method matching the TX name on the target actor becomes the handler. E.g., a TX with `name: 'UPDATE'` arriving at a component calls `component.UPDATE(data, tx)`.

---

## 2. Previous Component Layer (Before P0 — historical)

> **This section documents the state before the P0 refactor, which is now complete.**
> See §3 for the current architecture.

### Old Hierarchy

```
HTMLElement
  └── Component              (core/Component.js, ~70 lines)
        └── NTTElement       (components/ntt-element.js, ~155 lines)
              ├── Item       (components/ntt-item.js, ~165 lines)  → <ntt-item>
              └── List       (components/ntt-list.js, ~72 lines)   → <ntt-list>
```

### Component (`core/Component.js`)

```js
export class Component extends HTMLElement {
  #addr;
  #hash;

  constructor() {
    super();
    this.#hash = this.getAttribute('hash') || generateId();
    this.#addr = this.getAttribute('addr') || `${this.constructor.name}-${this.#hash}`;
    matrix.register(this);
    this.constructor.register(this);
  }

  static get observedAttributes() { return ['addr', 'hash']; }
  connectedCallback() {}
  disconnectedCallback() { console.error(`Component ${this.addr} disconnected.`); }
  render() { throw new Error(`Not implemented`); }
}

Actor.subclass(Component);
matrix.register(Component);
```

**Problem**: Has zero independent consumers — every Component is always an NTTElement. Circular import (line 1: `import '../components/ntt-item.js'`).

### NTTElement (`components/ntt-element.js`)

```js
export class NTTElement extends Component {
  #href; #model; #proto = {}; #data; #defaultValue = {}; #unsubscribe; #detach;

  constructor(defaultValue={}) {
    super();
    this.attachShadow({mode: 'open'});
    this.#model = this.getAttribute('model');
    this.#href = this.getAttribute('href');
    this.#data = defaultValue;
  }

  static get observedAttributes() { return ['model', 'addr', 'hash', 'ref']; }

  // ref setter: sends READ TX (URL) or ATTACH TX (NTT address)
  set ref(href) { ... }

  // Called by NTT core when DynamicClass prototype is ready
  define(ptt) { this.#proto = ptt; this.definedCallback(); }

  // Legacy dual-init path (sets proto AND data, skips definedCallback)
  describe(proto, data) { ... }

  // Trivial wrapper — children override via UPDATE handler anyway
  update(data) { this.value = data; }

  // value setter: auto-renders if this.$schema is truthy (Item-only property!)
  set value(data) {
    this.#data = data;
    if (this.$schema) this.render();
  }

  // Only used by List
  subscribe(tt, attribute, callback) { ... }

  render() { throw new Error(`Not implemented`); }
}
```

**Problems**: `describe()` and `define()` are dual paths to same state. `set value()` depends on `$schema` (defined only on Item). `subscribe()` and `update()` used by one child each. Overrides `observedAttributes` without merging. Re-declares abstract `render()`.

### Item (`components/ntt-item.js`)

Handles single entity: display/edit toggle, schema-driven form rendering via Formidable, input change handling, save via UPDATE TX. Message handlers: `UPDATE(data)`, `READ(data)`, `DESCRIBE(data)`.

### List (`components/ntt-list.js`)

Handles collection: subscribes to DynamicClass watcher, triggers READ, receives address array, stamps `<ntt-item>` per address. Has redundant `Actor.subclass(List)`.

### Identified Issues (Full List)

1. Circular import: Component.js imports ntt-item.js (grandchild)
2. Component has zero independent consumers
3. Redundant `Actor.subclass(List)` (Item doesn't do it either)
4. `observedAttributes` overridden without merging via super
5. Broken `super.disconnectedCallback()` chain (NTTElement never calls super)
6. Duplicate abstract `render()` in Component and NTTElement
7. `define()` vs `describe()` dual lifecycle paths
8. `set value()` depends on subclass-only property (`$schema`)
9. `subscribe()` only used by List
10. `update()` reimplemented by both children via message handlers
11. Edit UX baked into Item (can't extend without inheriting all of it)
12. List hardcodes `<ntt-item>` as child — no customization
13. Double registration (matrix + constructor) — unclear which is canonical
14. Stylesheet setup copy-pasted in each subclass constructor

---

## 3. Component Refactor (P0 Foundation) — COMPLETE

> **Status: Implemented and verified.**
> See `changelogs/02_Component_Layer_Refactor.md` for full details.

### Current Hierarchy

```
HTMLElement
  └── Component              (merged Component + NTTElement)
        ├── NTTElement       (single entity lifecycle)
        │     └── NTTItem    (built-in default: auto-renders via Formidable)
        └── ListElement      (collection lifecycle)
              └── NTTList    (built-in default: grid of children)
```

### Component (new base) — `core/Component.js`

Merges current `Component` + `NTTElement`. Single class, single file.

**Owns:**
- HTMLElement extension + Shadow DOM (`attachShadow`)
- Actor identity: `addr`, `hash`, `matrix.register(this)`, `Actor.subclass(Component)`
- Schema resolution: `model` attr → ATTACH TX → NTT core → `define(proto)` → `definedCallback()`
- Ref resolution: `ref` attr → ATTACH TX (NTT address) or READ TX (URL)
- `value` storage: getter/setter with type guard, **no auto-render**
- Stylesheet hook: `get styles()` returns CSS URL, base handles `<link>` injection
- `observedAttributes`: `['addr', 'hash', 'model', 'ref']`
- Lifecycle: `connectedCallback`, `disconnectedCallback` (cleanup)
- Abstract `render()` (single declaration)

**Removed:**
- `describe()` — dead dual-init path
- `update()` — trivial wrapper, children use message handlers
- Auto-render in `set value()` — children decide when to render

**Kept in Component (available to all subclasses):**
- `subscribe(tt, attribute, callback)` — generic observable subscription helper
- `attach(addr)` — imperative NTT.attach convenience (lazy-imported)

### NTTElement (entity base) — `components/NTTElement.js`

**Owns:**
- Default value: `{}`
- Message handlers: `UPDATE(data)`, `DESCRIBE(data)`, `READ(data)`
- `save()` — sends UPDATE TX with current value to `this.ref`
- Override `set value()` — auto-renders when schema is available

**Does NOT own:**
- Rendering (abstract — NTTItem provides default, devs override)
- Edit UX (mode toggle, input binding — that's NTTItem's concern)

### ListElement (collection base) — `components/ListElement.js`

**Owns:**
- Default value: `[]`
- `definedCallback()` — subscribes to proto, triggers collection READ
- `UPDATE(data)` — receives array of addresses, sets value, renders
- `append(data)` helper
- Default `render()` — stamps `this.childTag` per address
- `get childTag()` — overridable, defaults to `'ntt-item'`

### Built-in Defaults

```js
// components/ntt-item.js — zero-config single entity
class NTTItem extends NTTElement {
  mode = 'display';
  render() { /* Formidable auto-render + edit toggle + methods */ }
}
customElements.define('ntt-item', NTTItem);

// components/ntt-list.js — zero-config collection
class NTTList extends ListElement {}
customElements.define('ntt-list', NTTList);
```

### File Changes (completed)

| File | Action | Lines |
|---|---|---|
| `core/Component.js` | **Rewritten** — merged old Component + old NTTElement | 249 |
| `components/NTTElement.js` | **New** — entity base extracted from old Item | 103 |
| `components/ListElement.js` | **New** — collection base extracted from old List | 129 |
| `components/ntt-item.js` | **Slimmed** — thin NTTItem default over NTTElement | 115 |
| `components/ntt-list.js` | **Slimmed** — thin NTTList default over ListElement | 19 |
| `components/ntt-element.js` | **Deleted** — absorbed into `core/Component.js` | - |

### Issues Resolved

1. Circular import (Component → ntt-item) — **gone**
2. Redundant `Actor.subclass(List)` — **removed**
3. `observedAttributes` override — **single unified list in Component**
4. Broken `disconnectedCallback` chain — **single implementation in Component**
5. Duplicate abstract `render()` — **single declaration in Component**
6. `define()` / `describe()` duality — **`describe()` removed, single lifecycle path**
7. `value` setter depending on `$schema` — **auto-render moved to NTTElement only**
8. Stylesheet boilerplate — **`get styles()` hook in Component base**
9. Hardcoded `<ntt-item>` in List — **`childTag` + `createChild()` + template support in ListElement**

### Unchanged Files

`core/NTT.js`, `core/Matrix.js`, `core/Actor.js`, `core/Observable.js`, `core/TX.js`, `generators/form.js`, `components/ntt-method.js` — the data layer and message infrastructure are untouched.

---

## 4. Enhancement: Schema UI Extensions (Backend)

### Goal

Extend the JSON Schema with optional `ui` hints that default renderers respect and custom components can use or ignore.

### Backend API

**Model-level** via new `__ui__` ClassVar:

```python
class Product(ProtoModel):
    __tablename__: ClassVar[str] = 'products'
    __storable__: ClassVar[bool] = True
    __ui__: ClassVar[dict] = {
        'groups': {
            'main': ['name', 'description'],
            'pricing': ['price'],
            'relations': ['comments'],
        },
        'field_order': ['name', 'price', 'description', 'comments'],
        'exclude_render': ['parent_id'],
    }

    name: str = Field(json_schema_extra={'ui': {'widget': 'text', 'placeholder': 'Product name...'}})
    price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency', 'currency': 'USD'}})
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
```

**Per-field** via Pydantic's existing `json_schema_extra` mechanism (already supported — just needs a convention).

### Schema Output

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name",
      "ui": {"widget": "text", "placeholder": "Product name..."}
    },
    "price": {
      "type": "number",
      "title": "Price",
      "exclusiveMinimum": 0,
      "ui": {"widget": "currency", "currency": "USD"}
    }
  },
  "ui": {
    "groups": {
      "main": ["name", "description"],
      "pricing": ["price"],
      "relations": ["comments"]
    },
    "field_order": ["name", "price", "description", "comments"],
    "exclude_render": ["parent_id"]
  }
}
```

### Implementation

In `ProtoModel.schema()` (proto_model.py), after assembling the schema dict:

```python
# Inject __ui__ into schema
ui_config = getattr(cls, '__ui__', None)
if ui_config:
    schema['ui'] = ui_config
```

Pydantic already passes `json_schema_extra` through to the schema output under each property — no backend work needed for per-field hints. The `ui` key in `json_schema_extra` just becomes a convention.

### Frontend Consumption

Formidable and default renderers read `schema.ui` for layout decisions. Custom components access `this.schema.ui?.groups` etc. if they want the hints, or ignore them entirely.

### Design Principle

**Hints, not mandates.** The `ui` key is always optional. Models without `__ui__` work exactly as they do today. Formidable falls back to current behavior (iterate properties, skip name/id/description for header).

---

## 5. Enhancement: Slot-Based Child Templates

### Goal

Let developers provide the child component for a list via HTML composition, not just via JS `get childTag()`.

### API

```html
<!-- Option A: Template element (inert until cloned) -->
<product-grid model="Product">
  <template item-template>
    <product-card mode="compact" theme="dark"></product-card>
  </template>
</product-grid>

<!-- Option B: Attribute shorthand -->
<product-grid model="Product" item-tag="product-card"></product-grid>

<!-- Option C: No customization (built-in default) -->
<ntt-list model="Product"></ntt-list>
```

### Resolution Chain

When ListElement renders children, it resolves the child element in this priority:

```
1. <template item-template> in light DOM     (most explicit)
2. item-tag="..." HTML attribute              (attribute shorthand)
3. get childTag() JS property                 (subclass override)
4. schema.ui.renderer.item                    (schema hint, see §6)
5. 'ntt-item'                                 (framework default)
```

### Implementation in ListElement

```js
get #resolvedItemFactory() {
  // 1. Template in light DOM
  const template = this.querySelector('template[item-template]');
  if (template) return () => template.content.firstElementChild.cloneNode(true);

  // 2. item-tag attribute
  const itemTag = this.getAttribute('item-tag');
  if (itemTag) return () => document.createElement(itemTag);

  // 3. JS property (subclass override)
  // 4. Schema hint (falls through to childTag getter which checks schema)
  return () => document.createElement(this.childTag);
}

get childTag() {
  return this.schema?.ui?.renderer?.item || 'ntt-item';
}

render() {
  const factory = this.#resolvedItemFactory;
  const grid = document.createElement('div');
  grid.className = 'list-grid';

  this.value.forEach(addr => {
    const el = factory();
    el.setAttribute('ref', addr);
    grid.appendChild(el);
  });

  this.shadowRoot.innerHTML = '';
  this.shadowRoot.appendChild(this.$styles);
  this.shadowRoot.appendChild(grid);
}
```

The `<template>` approach is preferred because the developer can pre-configure the child with attributes, classes, or nested content — and `<template>` stays inert until cloned.

---

## 6. Enhancement: Schema Renderer Hints

### Goal

Backend specifies which component tag to use for rendering, so deploying a new model can include a full custom UI without modifying frontend HTML.

### Backend API

```python
class Product(ProtoModel):
    __ui__: ClassVar[dict] = {
        'renderer': {
            'item': 'product-card',
            'list': 'product-grid',
        }
    }
```

### Schema Output

```json
"ui": {
  "renderer": {
    "item": "product-card",
    "list": "product-grid"
  }
}
```

### Integration

This slots into the child resolution chain from §5 at priority level 4. `ListElement.childTag` checks `this.schema?.ui?.renderer?.item` before falling back to `'ntt-item'`.

It also affects which component `<ntt-list>` itself might delegate to if a schema specifies a custom list renderer — but this is opt-in. `<ntt-list model="Product">` always works with the built-in default regardless of schema hints.

### Concern

Backend naming frontend component tags creates coupling. This is acceptable because:
- It's completely optional (no `__ui__` = no coupling)
- It's a hint — any explicit HTML attribute or JS property overrides it
- It solves a real problem: deploying models with custom UI without touching HTML files

---

## 7. Enhancement: SSR Pre-Loading

### Problem

Two sequential network round-trips before any pixel renders:
1. `GET /Product` (schema) → creates DynamicClass
2. `GET /products` (data) → creates instances, renders

### Solution: Inline Pre-Loading

Server-rendered pages can inline both schema and data as JSON:

```html
<script type="application/json" data-ntt-schema="Product">
  {{ product_schema_json }}
</script>
<script type="application/json" data-ntt-data="products">
  {{ products_json }}
</script>
<ntt-list model="Product"></ntt-list>
```

### NTT Core Change

In `NTT.ATTACH` (or a new bootstrap check), before sending SCHEMA TX over network:

```js
static ATTACH(data, tx) {
  const model = addr.split('/')[0];
  const DC = NTT.#prototypes.get(model);

  if (DC) { /* exists — forward */ }
  else if (DC === null) { /* in flight — queue */ }
  else {
    // Check for pre-loaded schema before network fetch
    const preloaded = document.querySelector(`script[data-ntt-schema="${model}"]`);
    if (preloaded) {
      NTT.SCHEMA(JSON.parse(preloaded.textContent));
      // Also check for pre-loaded data
      const preloadedData = document.querySelector(`script[data-ntt-data="${model.toLowerCase()}s"]`);
      if (preloadedData) {
        const DC = NTT.#prototypes.get(model);
        DC.READ(JSON.parse(preloadedData.textContent));
      }
      return;
    }
    // No pre-load — normal network bootstrap
    NTT.#prototypes.set(model, null);
    NTT.#waiting.set(model, [tx]);
    matrix.dispatch(new TX({ name: 'SCHEMA', source: 'NTT', target: `${config.API_URL}/${model}`, meta: {remote: true} }));
  }
}
```

### Backend Support

A FastAPI route that renders an HTML page with pre-loaded data:

```python
@app.get("/app/{model_name}", response_class=HTMLResponse)
async def model_page(model_name: str):
    model_cls = registered_models.get(model_name)
    schema = model_cls.schema()
    records = model_cls.list()
    data = [r.model_dump(response=True) for r in records]
    return templates.TemplateResponse("page.html", {
        "model_name": model_name,
        "schema_json": json.dumps(schema),
        "data_json": json.dumps(data),
    })
```

### Impact

Eliminates both network round-trips for server-rendered pages. For SPA-style navigation (no server page render), the existing fetch flow works unchanged. No changes to the component layer.

---

## 8. Enhancement: Adaptive Display Modes

### Goal

A single component renders differently (page / card / list-item / chip) based on the space its parent allocates, not the screen size. This makes components truly context-aware — the same `<product-view>` works in a dashboard grid, a detail page, a sidebar, or an inline mention.

### Two Layers

**Layer A — CSS Container Queries** (styling within a fixed structure):

```css
:host { container-type: inline-size; }

@container (min-width: 600px) {
  .fields { display: grid; grid-template-columns: 1fr 1fr; }
}
@container (max-width: 200px) {
  .description, .meta { display: none; }
}
```

**Layer B — JS mode switching** (different HTML structures per mode):

Built into Component base or as a mixin. Uses ResizeObserver to track container width and expose `this.displayMode`:

```js
// In Component (base class) or as opt-in mixin
#displayObserver;
#displayMode = 'card';

get displayBreakpoints() {
  // Override in subclass to customize
  return { page: 800, card: 400, 'list-item': 200, chip: 0 };
}

get displayMode() { return this.#displayMode; }

connectedCallback() {
  super.connectedCallback();
  this.#displayObserver = new ResizeObserver(([entry]) => {
    const width = entry.contentRect.width;
    const bp = this.displayBreakpoints;
    const newMode = Object.entries(bp)
      .sort(([,a], [,b]) => b - a)
      .find(([, min]) => width >= min)?.[0] || 'chip';
    if (newMode !== this.#displayMode) {
      this.#displayMode = newMode;
      this.render();
    }
  });
  this.#displayObserver.observe(this);
}

disconnectedCallback() {
  this.#displayObserver?.disconnect();
  super.disconnectedCallback();
}
```

### Schema Integration

Pairs with §4 (Schema UI Extensions). Schema can define which fields to show per mode:

```python
__ui__: ClassVar[dict] = {
    'display_modes': {
        'page': {'fields': '*', 'layout': 'full'},
        'card': {'fields': ['name', 'price', 'description'], 'layout': 'card'},
        'list-item': {'fields': ['name', 'price'], 'layout': 'inline'},
        'chip': {'fields': ['name'], 'layout': 'chip'},
    }
}
```

This allows Formidable (or a new adaptive renderer) to auto-generate the right HTML for each mode from schema alone — without the developer writing four separate render methods.

### Developer Experience

```js
// Option A: Developer implements per-mode rendering
class ProductView extends NTTElement {
  render() {
    switch (this.displayMode) {
      case 'page':      return this.renderPage();
      case 'card':      return this.renderCard();
      case 'list-item': return this.renderCompact();
      case 'chip':      return this.renderChip();
    }
  }
  renderPage() { /* all fields, full layout */ }
  renderCard() { /* name, price, image */ }
  renderCompact() { /* name + price inline */ }
  renderChip() { /* just name */ }
}

// Option B: Schema-driven adaptive (no render override needed)
// If schema defines display_modes, the default renderer picks fields per mode automatically
class ProductView extends NTTElement {}  // Adaptive rendering comes free from schema
```

### Phasing

- Phase 1: CSS Container Queries support in base styles (low effort, immediate benefit)
- Phase 2: `displayMode` via ResizeObserver in Component (medium effort)
- Phase 3: Schema-driven adaptive rendering with Formidable (high effort, pairs with §4 and §10)

### Decision: Component base vs opt-in mixin

Recommended: **Component base**. The ResizeObserver is cheap. Exposing `this.displayMode` to every component costs nothing if unused. Components that don't override `render()` per mode simply ignore it. This follows the principle that a primitive should be available without requiring opt-in boilerplate.

---

## 9. Enhancement: Field Exclusion Conventions

### Problem

Fields like `parent_id`, `id`, internal timestamps exist in the schema (needed for data operations and relationships) but shouldn't render in default views. Currently Formidable hardcodes skipping `name`, `id`, `description` (they go in the header), but other internal fields still render.

### Three Levels of Field Visibility

| Level | Meaning | Mechanism |
|---|---|---|
| **Hidden** | Never leaves backend | `__hidden_fields__` class-level set (exists today) |
| **Data-only** | In schema + API responses, not rendered by default | `ui.display: false` (new) |
| **Visible** | Rendered in default views | Default behavior |

### Automatic Conventions

Applied by `ProtoModel.schema()` unless explicitly overridden:

- Fields ending in `_id` → `ui.display: false`
- The `id` field → `ui.display: false`
- `created_at`, `updated_at` → `ui.display: false`

### Explicit Override

```python
# Force a _id field to render
product_id: int = Field(json_schema_extra={'ui': {'display': True}})

# Force a normal field to not render
internal_notes: str = Field(json_schema_extra={'ui': {'display': False}})
```

### Frontend Consumption

Formidable checks `field.ui?.display !== false` before rendering:

```js
// In form.js getForm()
Object.keys(fields).map(key => {
  if (['name', 'id', 'description'].includes(key)) return '';
  const def = fields[key];
  if (def.ui?.display === false) return '';  // NEW: respect ui.display hint
  return getInput(ntt, key, mode);
})
```

### Implementation Cost

~10 lines in `ProtoModel.schema()` for conventions, ~3 lines in `form.js` for the check. Quickest win on this list.

---

## 10. Enhancement: Scaffolding / Template Generation

### Problem

Today: you either use Formidable's auto-render (zero customization) or write a component from scratch (full effort). There's no middle ground.

### Solution: Generate Starting Templates

**Mechanism A — CLI scaffolding** (primary):

```bash
$ python -m pybend scaffold Product
Generated:
  static/NTT0.6/components/product-card.js
  static/NTT0.6/components/product-card.css
  static/NTT0.6/components/product-grid.js
```

Where `product-card.js` contains a fully working, explicitly rendered component:

```js
import { NTTElement } from './NTTElement.js';

class ProductCard extends NTTElement {
  get styles() { return new URL('./product-card.css', import.meta.url).href; }

  render() {
    const { name, price, description, comments } = this.value || {};
    this.shadowRoot.innerHTML = `
      <div class="product-card">
        <h2 class="product-name">${name ?? ''}</h2>
        <p class="product-description">${description ?? ''}</p>
        <span class="product-price">${price ?? ''}</span>
        <div class="product-comments">
          ${(comments ?? []).map(c =>
            `<ntt-item ref="${c}"></ntt-item>`
          ).join('')}
        </div>
      </div>
    `;
  }
}

customElements.define('product-card', ProductCard);
```

And `product-card.css` contains a starter stylesheet based on the schema fields.

**Mechanism B — Dev-mode API endpoint**:

```
GET /Product?scaffold=item    → returns JS component source as text
GET /Product?scaffold=list    → returns JS list component source
GET /Product?scaffold=css     → returns starter CSS
```

Works from the browser or curl — no CLI install needed. Good for rapid iteration.

### Implementation

The scaffolding reads the model's `schema()` output and generates code:
- Iterates `properties` → destructures in `render()`
- Checks field types → picks appropriate HTML (input, textarea, checkbox, etc.)
- Checks `ListRef` fields → renders as nested components
- Checks `methods` → generates method button placeholders
- Applies `ui` hints if present (groups, order, widgets)

This can be a Python utility in `src/pybend/core/utils/scaffold.py` that both the CLI and the API endpoint call.

---

## 11. Enhancement: Schema-Driven Validation

### Goal

Auto-apply HTML5 validation attributes from schema constraints. Zero developer effort.

### How It Works

Pydantic validators already emit JSON Schema constraints:

```python
name: str = Field(min_length=3, max_length=100)
price: float = Field(gt=0, le=10000)
email: str = Field(pattern=r'^[\w.-]+@[\w.-]+\.\w+$')
```

Schema output:
```json
"name": {"type": "string", "minLength": 3, "maxLength": 100},
"price": {"type": "number", "exclusiveMinimum": 0, "maximum": 10000},
"email": {"type": "string", "pattern": "^[\\w.-]+@[\\w.-]+\\.\\w+$"}
```

### Formidable Change

When generating `<input>` elements in edit mode, map schema constraints to HTML5 attributes:

```js
function getInput(ntt, key, mode) {
  const def = schema.properties[key];
  // ... existing type logic ...

  if (mode === 'edit') {
    const attrs = [];
    if (def.minLength) attrs.push(`minlength="${def.minLength}"`);
    if (def.maxLength) attrs.push(`maxlength="${def.maxLength}"`);
    if (def.minimum != null) attrs.push(`min="${def.minimum}"`);
    if (def.exclusiveMinimum != null) attrs.push(`min="${def.exclusiveMinimum + 0.01}"`);
    if (def.maximum != null) attrs.push(`max="${def.maximum}"`);
    if (def.pattern) attrs.push(`pattern="${def.pattern}"`);
    if (schema.required?.includes(key)) attrs.push('required');

    html.push(`<input type="${inputType}" ${attrs.join(' ')} data-key="${key}" data-type="${type}" value="${value}">`);
  }
}
```

The browser handles validation natively. No custom validation code needed for standard constraints.

---

## 12. Enhancement: Schema-Driven Permissions

### Goal

Show/hide/disable fields and actions based on user role, driven by the schema.

### Backend API

```python
price: float = Field(json_schema_extra={
    'access': {'view': 'authenticated', 'edit': 'admin'}
})
```

The `access` key in the schema already exists at the model level (from `authorize.schema.access_schema(cls)` in `ProtoModel.schema()`). This extends it to field level.

### Frontend Consumption

The component (or Formidable) checks the current user's role against field-level access rules:
- `view` permission missing → field not rendered at all
- `edit` permission missing → field rendered as read-only even in edit mode

### Dependency

Requires the auth system to expose the current user's roles to the frontend. This is a later enhancement (P4) that builds on the existing `access` schema infrastructure.

---

## 13. Enhancement: Relationship-Aware Smart Defaults

### Goal

When Formidable encounters a `ListRef[Comment]` field, auto-render it as a proper nested list component instead of raw hrefs.

### Current Behavior

`form.js` `getListInput()` already handles this partially — it stamps `<ntt-item ref="...">` for each href string in the array. But it doesn't render as a `<ntt-list>` and doesn't provide the parent context.

### Improved Behavior

For `ListRef` fields (detected via `items.$ref` in the schema), render a scoped list:

```js
function getListInput(ntt, key, mode) {
  const def = ntt.schema.properties[key];
  const items = def.items || {};
  const value = ntt.value[key] || [];

  let modelName = items.$ref?.split('/').pop()
    || items.anyOf?.find(a => a.$ref)?.$ref.split('/').pop();

  if (!modelName) return '<!-- unknown list type -->';

  // Render as a mini-list with proper item components
  const children = value.map(item => {
    if (typeof item === 'string') {
      return `<ntt-item ref="${item}" data-model="${modelName}"></ntt-item>`;
    }
    return '';
  }).join('');

  return `
    <div class="list-field" data-model="${modelName}">
      <div class="list-field-header">
        <span class="list-field-count">${value.length}</span>
      </div>
      ${children}
    </div>
  `;
}
```

This pairs with §6 (schema renderer hints) — if `Comment` has `ui.renderer.item: 'comment-bubble'`, the list field would use that component instead of `<ntt-item>`.

---

## 14. Synthesis: Three Enhancement Layers

All enhancements cluster into three distinct layers:

### Layer 1: Schema Extensions (Backend)

§4 (UI hints), §6 (renderer hints), §9 (field exclusion), §11 (validation), §12 (permissions)

These all extend the schema output. They should ship as a single cohesive feature: the `__ui__` ClassVar + `json_schema_extra` convention + automatic conventions in `ProtoModel.schema()`.

**Single backend implementation point**: `ProtoModel.schema()` in `proto_model.py`.

### Layer 2: Component Primitives (Frontend Framework)

§3 (P0 refactor), §5 (slot templates), §8 (adaptive display modes), §13 (relationship rendering)

These make the base classes more capable. They ship in the new `Component`, `NTTElement`, `ListElement` classes.

**Implementation points**: `core/Component.js`, `components/NTTElement.js`, `components/ListElement.js`, `generators/form.js`.

### Layer 3: Developer Tools

§7 (pre-loading), §10 (scaffolding)

These are tooling that helps developers be productive. They're separate from the runtime framework.

**Implementation points**: `core/NTT.js` (pre-load check), `core/utils/scaffold.py` (CLI + API endpoint).

---

## 15. Priority & Sequencing

| Priority | Enhancement | §  | Status | Depends on |
|---|---|---|---|---|
| ~~**P0**~~ | ~~Component layer refactor~~ | ~~§3~~ | **DONE** | ~~Nothing~~ |
| **P1** | Field exclusion conventions | §9 | Pending | `ProtoModel.schema()` |
| **P1** | Schema UI extensions (`__ui__`) | §4 | Pending | `ProtoModel.schema()` |
| **P1** | Slot-based child templates | §5 | Pending | ~~P0~~ (done) |
| **P2** | Schema renderer hints | §6 | Pending | §4 |
| **P2** | Schema-driven validation | §11 | Pending | §4, `form.js` |
| **P2** | SSR pre-loading | §7 | Pending | `NTT.js` change only |
| **P3** | Scaffolding / template generation | §10 | Pending | ~~P0~~ (done), §4 |
| **P3** | Adaptive display modes | §8 | Pending | ~~P0~~ (done), §4 |
| **P3** | Relationship-aware defaults | §13 | Pending | ~~P0~~ (done), `form.js` |
| **P4** | Schema-driven permissions | §12 | Pending | §4, auth system |

### Recommended Implementation Order

1. ~~**P0**: Component refactor~~ — **DONE**
2. **P1 batch** (next): Field exclusion + `__ui__` schema extensions + slot templates → quick wins that make the framework immediately more useful
3. **P2 batch**: Renderer hints + validation + pre-loading → deeper schema integration and performance
4. **P3 batch**: Scaffolding + adaptive modes + relationship defaults → developer experience and advanced rendering
5. **P4**: Permissions → after auth system is stable

---

## 16. Implementation Directives

### General Rules

1. **Schema is the source of truth.** Every enhancement should flow from or integrate with the schema. If it can be driven by the schema, it should be.

2. **Hints, not mandates.** Every schema extension (`ui`, `renderer`, `display_modes`) is optional. The framework must work identically without them. Models without `__ui__` behave exactly as they do today.

3. **Progressive override.** There's always a chain: schema default → framework convention → developer code. Each level can override the one above. Nothing is locked in.

4. **Don't break existing.** `<ntt-list model="Product">` and `<ntt-item>` must continue to work throughout. The built-in defaults (NTTItem, NTTList) are thin shells over the new bases.

5. **Minimize changes to the data layer.** `NTT.js`, `Matrix.js`, `Actor.js`, `Observable.js`, `TX.js` should remain untouched unless absolutely necessary (the only exception is the pre-loading check in §7, which is a small addition to `NTT.ATTACH`).

### Backend Directives

- All `ui` extensions go through `ProtoModel.schema()` in `proto_model.py`.
- Use Pydantic's existing `json_schema_extra` for per-field hints — do not invent a new mechanism.
- The `__ui__` ClassVar is a plain dict, not a Pydantic model. It's injected into the schema output as-is.
- Field exclusion conventions (§9) are applied in `ProtoModel.schema()` after Pydantic generates the base schema.
- Scaffolding (§10) reads the same `schema()` output — a single codegen utility, callable from CLI and API.

### Frontend Directives

- The Component refactor (§3) is a prerequisite. Do not implement other enhancements on top of the current 4-class hierarchy.
- `Actor.subclass()` is called once on `Component`. NTTElement, ListElement, and all developer subclasses inherit it. Do not call `Actor.subclass()` on any other component class.
- `get styles()` returns a CSS URL. The base Component creates the `<link>` element and manages it. Subclasses only override the getter.
- `displayMode` (§8) lives in Component and is available to all subclasses. The ResizeObserver is created in `connectedCallback` and cleaned up in `disconnectedCallback`.
- Formidable remains a stateless utility (pure functions). It receives schema + value + mode and returns HTML strings. It does not hold state or manage lifecycle.
- Default components (`ntt-item.js`, `ntt-list.js`) are thin. They should be under ~50 lines each, delegating all logic to their base classes.

### Testing

- Start server: `cd /workspace/src/pybend/core && python3 main.py`
- Test API: `curl http://localhost:5000/Product` (schema), `curl http://localhost:5000/products` (data)
- Test frontend: `http://localhost:5000/static/NTT0.6/matrix.html`
- After schema extension changes, verify the JSON output: `curl http://localhost:5000/Product | python3 -m json.tool`
- After component refactor, verify that `<ntt-list model="Product">` still renders correctly in the browser.
