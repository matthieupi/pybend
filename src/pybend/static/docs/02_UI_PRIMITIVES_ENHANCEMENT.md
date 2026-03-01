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
| `src/pybend/core/models/proto_model.py` | Base model class. Generates JSON Schema via `schema()` (delegates to `proto_schema` pipeline). Injects `StorableMixin` for DB ops. `model_response()` adds `$schema`/`$id` metadata via the `proto_dump` pipeline. |
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
| `static/core/NTT.js` | Core entity system. `NTT` class = schema registry + instance manager. `prototype()` factory creates DynamicClasses from schema. |
| `static/core/Matrix.js` | Root actor / message bus. Routes TXs between actors. |
| `static/core/Actor.js` | Actor base. `Actor.subclass(Type)` stamps `send`/`inbox`/`register`/`children` onto any class. |
| `static/core/Observable.js` | Mixin: `signal()`, `observe()`, `notify()` for reactivity. |
| `static/core/TX.js` | Transaction (message) class: `{name, source, target, data, meta}`. |
| `static/core/Component.js` | **Unified base class** (merged HTMLElement + Actor bridge + schema resolution). All components inherit from this. |
| `static/components/NTTElement.js` | **Single entity base class**. Handles UPDATE/DESCRIBE/READ handlers, save(), value auto-render. |
| `static/components/ListElement.js` | **Collection base class**. Handles collection fetch, UPDATE handler, childTag/template resolution. |
| `static/components/ntt-item.js` | Built-in default item (extends NTTElement). Formidable auto-render + edit toggle. |
| `static/components/ntt-list.js` | Built-in default list (extends ListElement). Zero-config grid of children. |
| `static/components/ntt-method.js` | Renders callable methods as buttons. Unchanged. |
| `static/generators/form.js` | Formidable: schema-driven form/field generator. |
| `static/config.js` | `API_URL`, event name constants, logging flags. |

### Example Backend Model

```python
# src/pybend/example/models/product.py
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
- Adaptive display: `displayMode`, `displayBreakpoints`, `displayModeChanged()` via ResizeObserver (§8)
- `observedAttributes`: `['addr', 'hash', 'model', 'ref']`
- Lifecycle: `connectedCallback` (starts ResizeObserver), `disconnectedCallback` (cleanup)
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
| `core/Component.js` | **Rewritten** — merged base + adaptive display (§8) | 317 |
| `components/NTTElement.js` | **New** — entity base extracted from old Item | 107 |
| `components/ListElement.js` | **New** — collection base extracted from old List | 131 |
| `components/ntt-item.js` | **Slimmed** — thin NTTItem default over NTTElement | 115 |
| `components/ntt-list.js` | **Slimmed** — thin NTTList default over ListElement | 19 |
| `components/ntt-element.js` | **Deleted** — absorbed into `core/Component.js` | - |
| `generators/form.js` | **Enhanced** — field_order, widget, groups, validation (§4, §11) | 268 |

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

`core/Matrix.js`, `core/Actor.js`, `core/Observable.js`, `core/TX.js`, `components/ntt-method.js` — the actor system and message infrastructure remain untouched. `core/NTT.js` was modified for SSR pre-loading (§7). `generators/form.js` was enhanced with UI hint consumption, field ordering, widget mapping, grouped rendering (§4, §11), schema-aware relationship rendering (§13), and field-level access control (§12). `utils/Permissions.js` was added for frontend permissions (§12).

---

## 4. Enhancement: Schema UI Extensions (Backend) — DONE

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

### Frontend Consumption — DONE

Formidable (`generators/form.js`) now consumes all three model-level UI hints:

**`field_order`**: `getForm()` renders fields in `schema.ui.field_order` order instead of `Object.keys()` order. Fields not listed in `field_order` are appended at the end (safety net for schema additions).

**`groups`**: When `schema.ui.groups` is defined, fields are wrapped in `<fieldset class="ntt-group ntt-group-{name}">` with `<legend>` per group. Fields not belonging to any group render ungrouped at the end. New helper: `renderGroupedFields(ntt, renderableFields, groups, mode)`.

**`widget`** (per-field): The `ui.widget` hint takes priority over `type` for rendering decisions in `getInput()`:
- `widget: 'textarea'` → `<textarea>` in edit mode, `<div class="text-block">` in display (regardless of `type: 'string'`)
- `widget: 'currency'` → `<input type="number" step="0.01">` with `$` prefix in edit, `$X.XX` formatted in display

**`placeholder`** (per-field): `ui.placeholder` is already consumed via `validationAttrs()` and applied to inputs.

The existing `ui.display: false` check (§9) integrates with field ordering — excluded fields are filtered out before ordering/grouping runs.

### Design Principle

**Hints, not mandates.** The `ui` key is always optional. Models without `__ui__` work exactly as they do today. Formidable falls back to current behavior (iterate properties, skip name/id/description for header).

---

## 5. Enhancement: Slot-Based Child Templates — DONE (in P0)

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

## 6. Enhancement: Schema Renderer Hints — DONE

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

### Implementation — DONE

**Frontend**: `ListElement.childTag` checks `this.schema?.ui?.renderer?.item` at priority level 4 in the resolution chain. Formidable's `getListInput()` also resolves the child tag from `$defs[modelName].ui.renderer.item` when rendering inline ListRef fields.

**Backend**: Product model includes `renderer` in `__ui__`:
```python
__ui__: ClassVar[dict] = {
    'renderer': {
        'item': 'ntt-item',
        'list': 'ntt-list',
    },
    ...
}
```

Backend naming frontend component tags creates coupling. This is acceptable because:
- It's completely optional (no `__ui__` = no coupling)
- It's a hint — any explicit HTML attribute or JS property overrides it
- It solves a real problem: deploying models with custom UI without touching HTML files

---

## 7. Enhancement: SSR Pre-Loading — DONE

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

### Implementation (completed)

Two private static helper methods added to `NTT` class in `core/NTT.js`:

- **`#consumePreloadedSchema(model)`** — Checks `document.querySelector('script[data-ntt-schema="ModelName"]')`. If found, parses JSON, feeds to `NTT.SCHEMA()` directly, removes the script tag (one-shot consumption). Returns `true` if pre-loaded schema was found.
- **`#consumePreloadedData(tablename)`** — Checks `document.querySelector('script[data-ntt-data="tablename"]')`. If found, parses JSON, removes script tag, returns data array. Returns `null` if not found.

**Wired into three bootstrap paths:**

1. `NTT.attach()` — "Never seen" branch: tries `#consumePreloadedSchema(addr)` before sending SCHEMA TX
2. `NTT.ATTACH()` — "Never seen" branch: same pre-load check before network fetch
3. `NTT.SCHEMA()` — After creating DynamicClass: tries `#consumePreloadedData(tablename)` and calls `DC.READ(data)` directly instead of `DC.call('READ')` if found

**Queue-then-consume pattern**: Both `attach()` and `ATTACH()` set up the waiting queue *before* calling `#consumePreloadedSchema()`. This ensures that when `NTT.SCHEMA()` runs synchronously and replays the queue, all pending callbacks/TXs are already queued.

### Backend Support

A FastAPI route that renders an HTML page with pre-loaded data:

```python
@app.get("/app/{model_name}", response_class=HTMLResponse)
async def model_page(model_name: str):
    model_cls = registered_models.get(model_name)
    schema = model_cls.schema()
    records = model_cls.list()
    data = [r.model_response() for r in records]
    return templates.TemplateResponse("page.html", {
        "model_name": model_name,
        "schema_json": json.dumps(schema),
        "data_json": json.dumps(data),
    })
```

### Impact

Eliminates both network round-trips for server-rendered pages. For SPA-style navigation (no server page render), the existing fetch flow works unchanged. Only `core/NTT.js` was modified — no changes to the component layer.

---

## 8. Enhancement: Adaptive Display Modes — DONE (Phase 2 + Phase 2.5)

### Goal

A single component renders differently based on the space its parent allocates, not the screen size. This makes components truly context-aware — the same `<ntt-item>` works in a dashboard grid, a detail page, a sidebar, or an inline mention.

### Size System

Abstract sizes (`xs`–`xl`) with semantic aliases for readability:

| Size | Alias | Breakpoint | NTTItem Default |
|------|-------|-----------|-----------------|
| `xs` | `pill` | 0px+ | Name badge only |
| `sm` | `list-item` | 200px+ | Compact row: name + 2–3 key fields |
| `md` | `card` | 400px+ | Full card: edit + form + methods |
| `lg` | `detail` | 600px+ | Detail (delegates to `md`; future: hidden fields) |
| `xl` | `page` | 800px+ | Page (delegates to `md`; future: metadata) |

### Two Modes of Operation

**Auto mode (default):** ResizeObserver measures the component's content width and resolves to the largest matching breakpoint. No attribute needed.

**Forced mode:** Set the `display` attribute (or property) to lock a specific size:

```html
<ntt-item display="xs"></ntt-item>    <!-- abstract name -->
<ntt-item display="pill"></ntt-item>  <!-- semantic alias -->
<ntt-item display="auto"></ntt-item>  <!-- back to auto -->
```

When forced, the ResizeObserver still runs but its updates are ignored.

### Implementation — Component.js (Phase 2)

Added to `core/Component.js` base class. Every component gets space-awareness for free.

**Static members:**
- `Component.SIZES = ['xs', 'sm', 'md', 'lg', 'xl']`
- `Component.ALIASES = {pill: 'xs', 'list-item': 'sm', card: 'md', detail: 'lg', page: 'xl'}`
- `Component.normalizeDisplay(value)` — resolves abstract or semantic name to abstract size, returns `null` for `'auto'` or unrecognized values

**Private state:**
- `#displayMode = 'md'` — current mode, initialized to `'md'`
- `#resizeObserver = null` — ResizeObserver instance

**Public API:**

- **`get displayBreakpoints()`** — Override in subclass to customize. Returns `{xl: 800, lg: 600, md: 400, sm: 200, xs: 0}`. Evaluated largest-first.
- **`get displayMode()`** — Returns the current abstract size string.
- **`get display()` / `set display(value)`** — Gets/sets the `display` attribute. Accepts abstract or semantic names.
- **`displayModeChanged(oldMode, newMode)`** — Hook called when mode changes. Default: re-renders if schema available.

**Lifecycle wiring:**
- `connectedCallback()` applies forced mode if `display` attribute is set, then starts ResizeObserver.
- `disconnectedCallback()` stops ResizeObserver, cleans up subscriptions.
- `attributeChangedCallback` for `'display'` normalizes value and updates `#displayMode`.

**ResizeObserver guard:**
```js
// Skip if display mode is forced via attribute
if (Component.normalizeDisplay(this.getAttribute('display'))) return;
```

### Implementation — NTTItem Size Methods (Phase 2.5)

Size methods return HTML strings; `render()` dispatches and handles DOM + events.

```js
xs() { return `<span class="pill-label">${name}</span>`; }
sm() { return `<span class="sm-name">${name}</span><span class="sm-fields">...</span>`; }
md() { return editButton + Formidable.getForm(...) + methodButtons; }
lg() { return this.md(); }  // future: more fields
xl() { return this.md(); }  // future: metadata

render() {
  const size = this.displayMode;
  const html = (this[size] || this.md).call(this);
  this.shadowRoot.innerHTML = `<div class="card" data-display="${size}">${html}</div>`;
  this.#bindEvents();
  this[`${size}_mounted`]?.call(this);  // optional post-render hook
}
```

**Heuristic field selection** (`#topFields(count)`): For `sm`, picks the top N visible, non-header, non-array fields using `ui.field_order` if available, otherwise schema property order. Respects `ui.display` and permissions.

**CSS scoping**: `.card[data-display="xs"]`, `.card[data-display="sm"]`, etc. Each size has distinct layout rules in `ntt-item.css`. Host-level: `:host([display="xs"]) { display: inline-block; }`.

### Implementation — ListElement Size Cascade (Phase 2.5)

Children receive a display size from their parent to prevent cards-within-cards:

```js
static SIZE_CASCADE = { xl: 'md', lg: 'sm', md: 'xs', sm: 'xs', xs: 'xs' };

get childDisplay() {
  return this.getAttribute('item-display') || SIZE_CASCADE[this.displayMode] || 'xs';
}
```

`createChild()` stamps `display` on each child element. Nested items in Formidable's `getListInput()` also get `display="xs"`.

Override with `item-display` attribute:
```html
<ntt-list model="Product" item-display="sm"></ntt-list>
```

### Schema Integration (future — Phase 3)

Pairs with §4 (Schema UI Extensions). Schema can define which fields to show per mode:

```python
__ui__: ClassVar[dict] = {
    'display_modes': {
        'xl': {'fields': '*', 'layout': 'full'},
        'md': {'fields': ['name', 'price', 'description'], 'layout': 'card'},
        'sm': {'fields': ['name', 'price'], 'layout': 'inline'},
        'xs': {'fields': ['name'], 'layout': 'chip'},
    }
}
```

When present, `display_modes` overrides the heuristic field selection. This allows Formidable to auto-generate the right HTML for each mode from schema alone. Not yet implemented — the frontend heuristic (`#topFields`) handles field selection for now.

### Developer Experience

```js
// Option A: Override a single size method
class ProductCard extends NTTItem {
  xs() {
    return `<span class="pill-label">${this.value.name} — $${this.value.price}</span>`;
  }
  // sm, md, lg, xl inherited from NTTItem
}

// Option B: Custom breakpoints
class CompactProduct extends NTTElement {
  get displayBreakpoints() {
    return { xl: 600, lg: 400, md: 250, sm: 120, xs: 0 };
  }
}

// Option C: CSS-only mode switch (no re-render)
class StyledProduct extends NTTElement {
  displayModeChanged(oldMode, newMode) {
    this.shadowRoot.host.setAttribute('data-mode', newMode);
  }
}
```

### Decision: Component base (implemented)

**Component base**, not opt-in mixin. The ResizeObserver is cheap. `this.displayMode` is available to every component at zero cost if unused. Components that don't check `displayMode` in `render()` simply ignore it.

---

## 9. Enhancement: Field Exclusion Conventions — DONE

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

## 10. Enhancement: Scaffolding / Template Generation — DONE

### Problem

Today: you either use Formidable's auto-render (zero customization) or write a component from scratch (full effort). There's no middle ground.

### Solution: Generate Starting Templates — Implemented

**Mechanism A — CLI scaffolding**:

```bash
$ cd /workspace/src/pybend/core
$ python -m utils.scaffold Product
  WRITE .../components/product-card.js
  WRITE .../components/product-card.css
  WRITE .../components/product-grid.js
  WRITE .../components/product-grid.css
```

Generates four files: item component (extends NTTElement), list component (extends ListElement), and starter CSS for both. All immediately functional.

**Mechanism B — Dev-mode API endpoint**:

```
GET /Product?scaffold=item       → JS item component source (text/plain)
GET /Product?scaffold=list       → JS list component source
GET /Product?scaffold=css        → Item starter CSS
GET /Product?scaffold=list-css   → List starter CSS
```

Works from the browser or curl — no CLI install needed.

### Implementation Details

**File**: `src/pybend/core/utils/scaffold.py`

The scaffolding reads the model's `schema()` output and generates code:
- Respects `ui.field_order` for field rendering order
- Applies `ui.widget` hints: `currency` → `$X.XX` formatting, `textarea` → `<p>` blocks
- Applies `ui.display: false` → skips hidden fields
- Detects `ListRef` fields via `items.$ref` → renders as nested `<ntt-item>` (or custom tag from renderer hints)
- Generates `<ntt-method>` buttons for schema methods
- Header fields (`name`, `description`) rendered as `<h2>` / `<p>`, body fields with `<label>` + display element
- CSS includes glass morphism base card, field-specific selectors, and stagger animation

**API integration**: `make_get_schema()` in `routes_fastapi.py` checks for `?scaffold=` query parameter. When present, returns `PlainTextResponse` from `scaffold_single()` instead of JSON schema.

**Programmatic use**: `scaffold_single(model_name, kind, schema)` for inline use, `scaffold_model(model_name)` for writing files.

---

## 11. Enhancement: Schema-Driven Validation — DONE

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

## 12. Enhancement: Schema-Driven Permissions — DONE

### Goal

Show/hide/disable fields and actions based on user role, driven by the schema.

### Backend Implementation

**Per-field access** via `json_schema_extra`:

```python
price: float = Field(gt=0, json_schema_extra={
    'ui': {'widget': 'currency'},
    'access': {'view': 'anyone', 'edit': 'admin'}
})

user_owner: User = Field(json_schema_extra={
    'access': {'view': 'authenticated', 'edit': 'owner'}
})
```

**User identity endpoint**: `GET /auth/me` returns `{ user_id, email, role }` from the JWT token. The middleware already decodes the token into `request.state.user`.

**Model-level access** was already serialized via `authorize.schema.access_schema()` into `schema.access`. No changes needed.

### Frontend Implementation

**`utils/Permissions.js`** — Singleton module:
- `permissions.init()` — Fetches `/auth/me` using the JWT from `localStorage['jwtToken']`. Non-blocking; deduplicates.
- `permissions.user` — Current user object or null.
- `permissions.role` — Current role string ('anonymous' if not logged in).
- `permissions.canView(fieldDef)` — Checks `fieldDef.access.view` against user.
- `permissions.canEdit(fieldDef)` — Checks `fieldDef.access.edit` against user.
- `permissions.canAction(accessDict, action)` — Checks model-level `schema.access[action]` against user. Handles composite rules (or/and/not).

**Rule evaluation**:
- `'anyone'` → always true
- `'authenticated'` → true if logged in
- `'owner'` → true if logged in (ownership enforced server-side)
- Any other string → treated as role name, matched against `permissions.role`
- Composite rules: `{op: 'or', rules: [...]}`, `{op: 'and', rules: [...]}`, `{op: 'not', rule: {...}}`

**Formidable integration** (`generators/form.js`):
- `getForm()` filters out fields where `permissions.canView(def)` returns false
- `getInput()` downgrades edit mode to display mode if `permissions.canEdit(def)` returns false

**NTTItem integration** (`components/ntt-item.js`):
- Edit button hidden if `permissions.canAction(schema.access, 'update')` returns false
- `toggleMode()` blocked if user lacks update permission

**Bootstrap**: `permissions.init()` called in `matrix.html` module script. Non-blocking — components degrade gracefully (show everything by default, apply restrictions once identity resolves).

---

## 13. Enhancement: Relationship-Aware Smart Defaults — DONE

### Goal

When Formidable encounters a `ListRef[Comment]` field, auto-render it as a proper nested list component with schema-aware child resolution.

### Implementation

`getListInput()` in `form.js` now provides:

1. **Schema-aware child tag resolution**: Looks up the referenced model's `$defs` entry for `ui.renderer.item`. If `Comment` has `renderer.item: 'comment-bubble'`, the list field stamps `<comment-bubble>` instead of `<ntt-item>`.

2. **Count header**: Renders a `.list-field-header` with model name label and count badge.

3. **Collapse/expand**: Items beyond `VISIBLE_COUNT` (2) are wrapped in `.nested-collapsed` with a show-more button.

```js
// Resolution: $defs[modelName].ui.renderer.item → 'ntt-item' fallback
let childTag = 'ntt-item';
if (modelName && defs[modelName]?.ui?.renderer?.item) {
    childTag = defs[modelName].ui.renderer.item;
}
```

### CSS Support

New CSS classes in `ntt-item.css`:
- `.list-field-header` — flex row with label + count
- `.list-field-label` — uppercase accent-colored model name
- `.list-field-count` — pill badge with item count

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
| ~~**P1**~~ | ~~Field exclusion conventions~~ | ~~§9~~ | **DONE** | ~~`ProtoModel.schema()`~~ |
| ~~**P1**~~ | ~~Schema UI extensions (`__ui__`)~~ | ~~§4~~ | **DONE** | ~~`ProtoModel.schema()`~~ |
| ~~**P1**~~ | ~~Slot-based child templates~~ | ~~§5~~ | **DONE** (in P0) | ~~P0~~ |
| ~~**P2**~~ | ~~Schema renderer hints~~ | ~~§6~~ | **DONE** | ~~§4~~ (done) |
| ~~**P2**~~ | ~~Schema-driven validation~~ | ~~§11~~ | **DONE** | ~~§4, `form.js`~~ |
| ~~**P2**~~ | ~~SSR pre-loading~~ | ~~§7~~ | **DONE** | ~~`NTT.js` change only~~ |
| ~~**P2**~~ | ~~Formidable UI hints (field_order, widget, groups)~~ | ~~§4~~ | **DONE** | ~~§4, `form.js`~~ |
| ~~**P2**~~ | ~~Adaptive display modes (Phase 2: infra)~~ | ~~§8~~ | **DONE** | ~~P0, §4~~ |
| ~~**P2.5**~~ | ~~Adaptive display (Phase 2.5: size methods, cascade, forced mode)~~ | ~~§8~~ | **DONE** | ~~P2~~ |
| ~~**P3**~~ | ~~Scaffolding / template generation~~ | ~~§10~~ | **DONE** | ~~P0, §4~~ (done) |
| ~~**P3**~~ | ~~Relationship-aware defaults~~ | ~~§13~~ | **DONE** | ~~P0~~ (done), `form.js` |
| ~~**P4**~~ | ~~Schema-driven permissions~~ | ~~§12~~ | **DONE** | ~~§4~~ (done), ~~auth system~~ (done) |

### Recommended Implementation Order

1. ~~**P0**: Component refactor~~ — **DONE**
2. ~~**P1 batch**: Field exclusion + `__ui__` schema extensions + slot templates + validation~~ — **DONE**
3. ~~**P2 batch**: Formidable UI hints + SSR pre-loading + adaptive display modes + renderer hints~~ — **DONE**
4. ~~**P3 batch**: Scaffolding + relationship defaults~~ — **DONE**
5. ~~**P4**: Permissions~~ — **DONE**

### All enhancements complete.

---

## 16. Implementation Directives

### General Rules

1. **Schema is the source of truth.** Every enhancement should flow from or integrate with the schema. If it can be driven by the schema, it should be.

2. **Hints, not mandates.** Every schema extension (`ui`, `renderer`, `display_modes`) is optional. The framework must work identically without them. Models without `__ui__` behave exactly as they do today.

3. **Progressive override.** There's always a chain: schema default → framework convention → developer code. Each level can override the one above. Nothing is locked in.

4. **Don't break existing.** `<ntt-list model="Product">` and `<ntt-item>` must continue to work throughout. The built-in defaults (NTTItem, NTTList) are thin shells over the new bases.

5. **Minimize changes to the data layer.** `NTT.js`, `Matrix.js`, `Actor.js`, `Observable.js`, `TX.js` should remain untouched unless absolutely necessary. The only exception so far is the SSR pre-loading check in §7 (two private static helpers + three guard clauses in `NTT.attach()`, `NTT.ATTACH()`, and `NTT.SCHEMA()`).

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
- Test frontend: `http://localhost:5000/static/matrix.html`
- After schema extension changes, verify the JSON output: `curl http://localhost:5000/Product | python3 -m json.tool`
- After component refactor, verify that `<ntt-list model="Product">` still renders correctly in the browser.
