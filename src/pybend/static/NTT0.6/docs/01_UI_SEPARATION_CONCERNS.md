# NTT Component Layer: Separation of Concerns

Architectural analysis and refactoring plan for the NTT frontend component hierarchy.

---

## 1. System Context

NTT is a schema-driven frontend framework built on vanilla JS Web Components. The backend (PyBend/FastAPI) publishes JSON Schemas for every model. The frontend fetches these schemas at runtime, creates DynamicClasses (typed NTT instances), and renders UI components that stay in sync via a message bus (Matrix/Actor system).

### The Data Layer (NTT Core — unchanged by this refactor)

The data layer lives in `core/NTT.js` and is separate from the component layer. It handles:

- **Schema registry**: `NTT.ATTACH` bootstraps models on first reference — fetches schema from backend, creates a `DynamicClass` via `prototype()`, stores it in a global `#prototypes` map.
- **DynamicClass**: A runtime NTT subclass per model (e.g., "Product"). Holds the schema, typed property accessors, instance map, CRUD methods, watcher set. Created by the `prototype()` factory function.
- **Instance management**: Each backend record becomes a `DynamicClass` instance (an NTT actor) with its own address, href, value, and signal/observe reactivity.
- **Watcher pattern**: Components ATTACH to a DynamicClass. The class tracks watchers and sends UPDATE TXs when data arrives or changes.
- **Message routing**: `Matrix` is the root Actor. All TXs flow through it. `Actor.subclass()` stamps static/instance `send`/`inbox`/`register` onto any class.

**Key point**: The data layer works independently of any rendering. Components are consumers of TXs — they receive data and decide what to do with it.

### Request Lifecycle

```
1. <ntt-list model="Product">         Component appears in DOM
2. attributeChangedCallback            Sends ATTACH TX to NTT
3. NTT.ATTACH("Product")              Checks registry:
   - Unknown model? Fetch schema       SCHEMA TX -> NetworkAdapter -> GET /Product
   - Schema in flight? Queue TX
   - DynamicClass ready? Forward TX
4. NTT.SCHEMA(data)                   Creates DynamicClass via prototype()
   - Replays queued ATTACHes
   - Triggers DynamicClass.call('READ') -> GET /products
5. DynamicClass.READ(data)            Creates NTT instances per record
   - Notifies all watchers with instance addresses
6. List.UPDATE([addrs])               Receives address array, renders grid
7. <ntt-item ref="Product/1">         Stamps child per address
8. NTTElement sends ATTACH TX          For specific instance
9. NTT instance.ATTACH                Responds with DESCRIBE TX (proto + data)
10. Item.DESCRIBE({proto, data})       Sets schema + value, renders
```

---

## 2. Current Component Hierarchy

```
HTMLElement
  └── Component              (core/Component.js)
        └── NTTElement       (components/ntt-element.js)
              ├── Item       (components/ntt-item.js)     -> <ntt-item>
              └── List       (components/ntt-list.js)     -> <ntt-list>
```

### Component (`core/Component.js`, ~70 lines)

Extends HTMLElement, gets `Actor.subclass(Component)` applied.

**Owns:**
- `addr` and `hash` assignment in constructor
- Dual registration: `matrix.register(this)` + `this.constructor.register(this)`
- `observedAttributes`: `['addr', 'hash']`
- Empty `connectedCallback`, logging-only `disconnectedCallback`
- Abstract `render()` (throws NotImplementedError)

**Problems:**
- Circular import: line 1 imports `'../components/ntt-item.js'` (a grandchild)
- Zero independent consumers — every Component is an NTTElement
- ~15 lines of real logic wrapped in a class + file + import chain

### NTTElement (`components/ntt-element.js`, ~155 lines)

Extends Component. The "entity-aware base".

**Owns:**
- Shadow DOM setup (`attachShadow`)
- Schema/proto resolution: `model` attr -> ATTACH TX -> `define(proto)` -> `definedCallback()`
- Ref resolution: `ref` attr -> READ TX (URL) or ATTACH TX (NTT address)
- `value` getter/setter with type checking and auto-render (when `this.$schema` is truthy)
- `describe(proto, data)` — legacy dual-init path alongside `define()`
- `update(data)` — trivial `value = data` wrapper
- `subscribe(tt, attribute, callback)` — Observable subscription helper
- `attach(addr)` — NTT.attach wrapper
- Re-declares `observedAttributes`: `['model', 'addr', 'hash', 'ref']` (overrides parent's)
- Re-declares abstract `render()` (duplicate of Component's)

**Problems:**
- `observedAttributes` silently overrides Component's (works by coincidence, not by merging)
- `disconnectedCallback` never calls `super` — Component's logging is dead code
- `describe()` and `define()` are two paths to the same state with different side effects
- `set value()` auto-renders based on `this.$schema` — a property only defined on Item
- `subscribe()` only used by List; `update()` reimplemented by both children
- Duplicate abstract `render()` declaration

### Item (`components/ntt-item.js`, ~165 lines)

Extends NTTElement. Registered as `<ntt-item>`.

**Owns:**
- Default value: `{}` (single entity)
- Message handlers: `UPDATE(data)`, `READ(data)`, `DESCRIBE(data)`
- Display/edit toggle: `mode` property, pencil/save button
- Rendering: delegates to `Formidable.getForm()` for schema-driven form
- Method rendering: iterates `schema.methods`, stamps `<ntt-method>` elements
- Input handling: `handleInputChange(e)` mutates value from form inputs
- Save: `save()` sends UPDATE TX with current value

**Problems:**
- Tightly couples data lifecycle (UPDATE/DESCRIBE handlers) with rendering (Formidable)
- Edit UX (mode toggle, input binding, save) is baked in — can't extend Item without inheriting all of it
- `$schema` property used by parent's `set value()` but only defined here

### List (`components/ntt-list.js`, ~72 lines)

Extends NTTElement. Registered as `<ntt-list>`.

**Owns:**
- Default value: `[]` (collection)
- `definedCallback()`: subscribes to proto UPDATE, triggers collection READ
- `UPDATE(data)`: receives array of addresses, sets value, renders
- `append(data)`: pushes to array
- Rendering: header with model name + count, stamps `<ntt-item>` per address

**Problems:**
- Hardcodes `<ntt-item>` as child element — no way to customize
- Has `Actor.subclass(List)` at module level (redundant — already inherited through Component)

---

## 3. Identified Issues Summary

| # | Issue | Where | Impact |
|---|---|---|---|
| 1 | Circular import | Component.js:1 imports ntt-item.js | Module loading fragility |
| 2 | Component has zero independent consumers | Component.js | Unnecessary abstraction layer |
| 3 | Double `Actor.subclass` | ntt-list.js:71 | Inconsistent (Item doesn't do it) |
| 4 | `observedAttributes` overridden without merge | NTTElement | Fragile if Component's list changes |
| 5 | Broken `super.disconnectedCallback()` chain | NTTElement | Component's cleanup is dead code |
| 6 | Duplicate abstract `render()` | Component + NTTElement | Redundant, confusing |
| 7 | `define()` vs `describe()` dual lifecycle | NTTElement | Two paths to same state |
| 8 | `set value()` depends on subclass state (`$schema`) | NTTElement | Base depends on child's property |
| 9 | `subscribe()` only used by List | NTTElement | Base method for one child |
| 10 | `update()` reimplemented by both children | NTTElement | Dead base method |
| 11 | Edit UX baked into Item | ntt-item.js | Can't extend without inheriting edit toggle |
| 12 | List hardcodes `<ntt-item>` children | ntt-list.js | No customization |
| 13 | Double registration (matrix + constructor) | Component | Unclear which is canonical |
| 14 | Stylesheet setup repeated in each subclass | Item, List constructors | Boilerplate |

---

## 4. Proposed Architecture

```
HTMLElement
  └── Component                 (merged Component + NTTElement)
        ├── NTTElement          (single entity lifecycle)
        │     └── NTTItem       (built-in default: schema-driven auto-render)
        └── ListElement         (collection lifecycle)
              └── NTTList       (built-in default: grid of <ntt-item>)
```

Three layers. Each adds exactly one concern. No layer reaches into another's job.

### Component — "I exist on the Matrix and I know my schema"

Merges current `Component` + `NTTElement`. Single file: `core/Component.js`.

**Owns:**
- HTMLElement extension + Shadow DOM setup
- Actor identity: `addr`, `hash`, `matrix.register(this)`, `Actor.subclass(Component)`
- Schema resolution: `model` attr -> ATTACH TX -> NTT core -> `define(proto)` -> `definedCallback()`
- Ref resolution: `ref` attr -> ATTACH TX (NTT address) or READ TX (URL)
- `value` storage: getter/setter with type checking, **no auto-render** (children decide)
- Stylesheet hook: `get styles()` returns CSS URL, base handles `<link>` injection
- `observedAttributes`: `['addr', 'hash', 'model', 'ref']`
- Lifecycle: `connectedCallback`, `disconnectedCallback` (cleanup detach/unsubscribe)
- Abstract `render()` contract (single declaration)

**Does NOT own:**
- Data fetching strategy (pull vs push)
- Save/update cycle
- Collection management
- How anything looks

**Removed from current NTTElement:**
- `describe(proto, data)` — dead legacy path; children use message handlers
- `update(data)` — trivial wrapper; children override via `UPDATE` handler
- Auto-render in `set value()` — moved to NTTElement's override
- `subscribe()` — moved to ListElement (only consumer)

### NTTElement — "I am one entity"

Extends Component. File: `components/NTTElement.js`.

**Owns:**
- Default value: `{}`
- Message handlers:
  - `UPDATE(data)` — receives entity data, resolves `$schema`, triggers render
  - `DESCRIBE(data)` — receives proto + data together (from NTT instance ATTACH response)
  - `READ(data)` — handles direct URL fetch response
- `save()` — sends UPDATE TX with current value back to `this.ref`
- Override `set value()` — auto-renders when schema is available
- Value accessors with `$schema`/`$id` injection

**Does NOT own:**
- Rendering (abstract — subclass must implement or use default)
- Edit UX (mode toggle, input binding, button placement)
- Styles

### ListElement — "I am a collection"

Extends Component. File: `components/ListElement.js`.

**Owns:**
- Default value: `[]`
- `definedCallback()` — subscribes to proto, triggers collection READ
- `UPDATE(data)` — receives array of instance addresses, sets value, renders
- `append(data)` — adds to collection
- Default `render()` — iterates value, stamps `this.childTag` per address
- `get childTag()` — overridable hook, defaults to `'ntt-item'`

**Does NOT own:**
- How individual items look (that's the child component's job)
- Grid layout details (that's CSS)
- Item-level data management

### Built-in Defaults — zero-config components

These provide the "just put it in HTML and it works" experience:

```js
// components/ntt-item.js
class NTTItem extends NTTElement {
  mode = 'display';

  render() {
    const icon = this.mode === 'edit' ? '\u{1F4BE}' : '\u{270F}\u{FE0F}';
    this.shadowRoot.innerHTML = `<div class="card">
      <button class="edit-btn">${icon}</button>
      ${Formidable.getForm({schema: this.schema, value: this.value}, this.mode)}
      ${this.renderMethods()}
    </div>`;
    this.bindEvents();
  }

  // ... edit toggle, input handling, method rendering
}
customElements.define('ntt-item', NTTItem);
```

```js
// components/ntt-list.js
class NTTList extends ListElement {}
customElements.define('ntt-list', NTTList);
```

---

## 5. Developer Experience

### Minimum item component

```js
import { NTTElement } from './NTTElement.js';

class ProductCard extends NTTElement {
  get styles() { return './product-card.css'; }

  render() {
    const { name, price, description } = this.value;
    this.shadowRoot.innerHTML = `
      <h2>${name}</h2>
      <p>${description}</p>
      <span class="price">$${price}</span>
    `;
  }
}
customElements.define('product-card', ProductCard);
```

No fetch, no Redux, no state management, no schema parsing. The developer writes a template — the framework handles everything else.

### Minimum list component

```js
import { ListElement } from './ListElement.js';

class ProductGrid extends ListElement {
  get styles() { return './product-grid.css'; }
  get childTag() { return 'product-card'; }
}
customElements.define('product-grid', ProductGrid);
```

Or with a fully custom render:

```js
class ProductGrid extends ListElement {
  render() {
    this.shadowRoot.innerHTML = `
      <h1>Products (${this.value.length})</h1>
      <div class="masonry">
        ${this.value.map(addr =>
          `<product-card ref="${addr}"></product-card>`
        ).join('')}
      </div>
    `;
  }
}
```

### Usage in HTML

```html
<!-- Zero-config (built-in defaults) -->
<ntt-list model="Product"></ntt-list>

<!-- Custom components -->
<product-grid model="Product"></product-grid>
```

### Item with save support

```js
class EditableProduct extends NTTElement {
  #mode = 'display';

  render() {
    if (this.#mode === 'edit') {
      this.shadowRoot.innerHTML = `
        <input type="text" value="${this.value.name}" data-key="name">
        <button class="save">Save</button>
      `;
      this.shadowRoot.querySelector('.save')
        .addEventListener('click', () => { this.save(); this.#mode = 'display'; this.render(); });
    } else {
      this.shadowRoot.innerHTML = `
        <h2>${this.value.name}</h2>
        <button class="edit">Edit</button>
      `;
      this.shadowRoot.querySelector('.edit')
        .addEventListener('click', () => { this.#mode = 'edit'; this.render(); });
    }
  }
}
```

`this.save()` is provided by NTTElement — it sends an UPDATE TX. The developer only handles the UX around when to call it.

---

## 6. What Developers Must Always Handle

These are responsibilities the framework intentionally leaves to the developer:

| Responsibility | Why it's theirs |
|---|---|
| `render()` | Rendering is where opinion and design live. Framework provides a default via NTTItem, but real apps override. |
| Styles (CSS) | Shadow DOM requires explicit stylesheets. `get styles()` hook reduces boilerplate, but design is the dev's domain. |
| `customElements.define()` | Browser API requirement. Cannot be abstracted away. |
| Custom interactions | Click handlers, drag-and-drop, animations, form validation beyond schema types. The framework gives you data; user gestures are yours. |
| Composition & layout | Which components go where on the page, routing between views, responsive layout. |
| Edit UX | The framework provides `save()`. The developer decides *when* and *how* to call it — inline edit, modal, separate page, etc. |

---

## 7. What the Framework Handles (no developer involvement)

| Concern | How |
|---|---|
| Schema fetching & parsing | NTT.ATTACH -> SCHEMA TX -> DynamicClass creation |
| Data fetching (CRUD) | DynamicClass.call('READ') via NetworkAdapter |
| Instance lifecycle | DynamicClass.READ creates/updates NTT instances |
| Reactivity | Value changes -> signal/observe -> component re-render |
| Collection management | ListElement subscribes to DynamicClass, receives address arrays |
| Network transport | Matrix -> NetworkAdapter -> HTTP/WebSocket |
| Type system | DynamicClass properties are typed from schema, with runtime checks |

---

## 8. Tradeoffs & Downsides

### Two base classes instead of one

LitElement has ONE base class. We have two (NTTElement + ListElement) because collections and entities have fundamentally different data lifecycles:

| | NTTElement | ListElement |
|---|---|---|
| Data shape | `{}` single object | `[]` array of addresses |
| Fetch trigger | Receives push (DESCRIBE from NTT instance) | Actively pulls (triggers collection READ) |
| Mutation | Can save (sends UPDATE TX) | Read-only (creates children that mutate) |
| Children | Leaf node (renders fields) | Container (stamps child components) |

A single base with mode flags would be a god class. Two bases is honest about a real domain distinction.

**Mitigation:** Component is the shared parent. A developer who never builds a list never sees ListElement.

### Schema dependency = async bootstrap

Components can't render until the schema arrives from the backend. There's always a loading phase. LitElement renders immediately because properties are declared statically.

This is the tradeoff for not having to manually declare properties. The backend schema IS the property definition.

**Mitigation:** `connectedCallback` can set placeholder content. Could add a `renderLoading()` hook that Component calls before the schema arrives.

### Actor/Matrix coupling

Developers inherit the TX message system. For basic use they never see it — `render()` just reads `this.value`. But for inter-component communication or custom data flows, they'd need to understand `send(new TX({...}))`.

**Mitigation:** For common operations, provide sugar methods:
- `this.save()` — already provided by NTTElement
- `this.dispatch(name, data)` — could wrap TX construction
- Advanced users get the full TX system; basic users never touch it.

### Edit/save entanglement (resolved)

Today, Item bakes in display/edit toggle, input binding, mode tracking, and save. In the refactored architecture, this is cleanly split:

- **NTTElement** provides `save()` (one-line TX send) — mechanical, unopinionated
- **NTTItem** (built-in default) provides the full edit UX as a reference implementation
- **Custom components** handle edit UX however they want, call `this.save()` when ready

### Formidable coupling (resolved)

Today `Item.render()` calls `Formidable.getForm()` directly. After refactor, Formidable is a utility that NTTItem (the default) uses. Custom components that override `render()` never import or see Formidable.

---

## 9. Migration Assessment

### What changes

| Current file | Becomes | Work |
|---|---|---|
| `core/Component.js` | **Deleted** — merged into new Component | Mechanical |
| `components/ntt-element.js` | `core/Component.js` (new base) | Remove `describe()`, `update()`, auto-render from setter. Add `get styles()` hook. Absorb old Component.js internals. |
| `components/ntt-item.js` | Split: `components/NTTElement.js` (entity base) + `components/ntt-item.js` (default) | Data handlers -> NTTElement. Formidable + edit UX -> NTTItem. |
| `components/ntt-list.js` | Split: `components/ListElement.js` (collection base) + `components/ntt-list.js` (default) | Add `get childTag()`. NTTList becomes a thin shell. |

### What does NOT change

- `core/NTT.js` — Data layer, DynamicClass, schema registry. Untouched.
- `core/Matrix.js` — Message routing. Untouched.
- `core/Actor.js` — Actor system. Untouched.
- `core/Observable.js` — Mixin. Untouched.
- `core/TX.js` — Transaction format. Untouched.
- `generators/form.js` — Formidable. Untouched (just consumed differently).
- `components/ntt-method.js` — Method buttons. Untouched.

### Cleanup included in migration

- Remove circular import (Component.js -> ntt-item.js)
- Remove redundant `Actor.subclass(List)`
- Merge `observedAttributes` properly (spread from parent)
- Fix `disconnectedCallback` super chain
- Remove `describe()` / `update()` dead paths from base
- Move `subscribe()` to ListElement (only consumer)
- Remove duplicate abstract `render()` declaration

### Estimated scope

The NTT core and message infrastructure are already clean and separate. The refactor is contained entirely within the component layer — roughly 4 files touched, ~400 lines total across all files. The hardest part is getting the lifecycle timing right: `define -> definedCallback -> first render` must work reliably for both NTTElement and ListElement.

---

## 10. File Structure (After)

```
core/
  Component.js        NEW - merged base (HTMLElement + Actor + schema)
  Actor.js            unchanged
  Matrix.js           unchanged
  NTT.js              unchanged
  Observable.js       unchanged
  TX.js               unchanged
  Utils.js            unchanged

components/
  NTTElement.js       NEW - single entity base class
  ListElement.js      NEW - collection base class
  ntt-item.js         REFACTORED - thin default (extends NTTElement)
  ntt-list.js         REFACTORED - thin default (extends ListElement)
  ntt-element.js      DELETED - absorbed into core/Component.js
  ntt-method.js       unchanged

generators/
  form.js             unchanged (Formidable, consumed by ntt-item.js)
```
