# UI Components Reference

Documentation for the web component layer that renders NTT data in the browser.

## Table of Contents

1. [Component (base)](#component)
2. [NTTElement (entity base)](#nttelement)
3. [ListElement (collection base)](#listelement)
4. [NTTItem (built-in default item)](#nttitem)
5. [NTTList (built-in default list)](#nttlist)
6. [NTTMethod](#nttmethod)
7. [Router (navigation actor)](#router)
8. [NTTRouter (view container)](#nttrouter)
9. [Formidable (form generator)](#formidable)
10. [Scaffolding](#scaffolding)

---

## Component

**File:** `core/Component.js`
**Tag:** Not registered as a custom element (abstract base class)

Unified base class for all NTT web components. Merges Actor bridge, Shadow DOM, schema resolution, adaptive display, and stylesheet management into a single class.

### Class Hierarchy

```
HTMLElement
  └── Component              (core/Component.js, ~317 lines)
        ├── NTTElement       (components/NTTElement.js — entity lifecycle)
        │     └── NTTItem    (components/ntt-item.js — built-in default)
        └── ListElement      (components/ListElement.js — collection lifecycle)
              └── NTTList    (components/ntt-list.js — built-in default)
```

### Constructor

```javascript
constructor(defaultValue = {}) {
  super();
  this.attachShadow({mode: 'open'});
  // Actor identity
  this.#hash = this.getAttribute('hash') || generateId();
  this.#addr = this.getAttribute('addr') || `${this.constructor.name}-${this.#hash}`;
  matrix.register(this);
  this.constructor.register(this);
  // Entity state
  this.#model = this.getAttribute('model') || undefined;
  this.#data = defaultValue;
  // Stylesheet hook
  if (this.styles) { /* creates <link> in shadowRoot */ }
}
```

### Actor Integration

```javascript
Actor.subclass(Component);    // Applied ONCE — all subclasses inherit
matrix.register(Component);   // Component CLASS is a Matrix child
```

`Actor.subclass()` is called only on Component. NTTElement, ListElement, NTTItem, NTTList — all inherit it. Do not call `Actor.subclass()` on any other component class.

### Observed Attributes

`['model', 'addr', 'hash', 'ref', 'display']`

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `addr` | `string` | Unique actor address. Set once, immutable. |
| `model` | `string` | Model name (e.g., `"Product"`). Setting triggers ATTACH TX to NTT. |
| `ref` | `string` | Entity reference. URL → READ TX. NTT address → ATTACH TX. |
| `proto` | `DynamicClass` | The DynamicClass prototype (set via `define()`). |
| `schema` | `object` | JSON Schema from proto. Cached in `_schema`. |
| `value` | `object\|array` | Current data. **No auto-render** — subclasses decide. |
| `defaultValue` | `object\|array` | The default passed to constructor (`{}` or `[]`). |
| `displayMode` | `string` | Current adaptive display mode (`'xs'`, `'sm'`, `'md'`, `'lg'`, `'xl'`). |
| `display` | `string` | The `display` attribute value, or `'auto'`. Set to force a display mode. |

### Static Members

| Member | Type | Description |
|--------|------|-------------|
| `SIZES` | `string[]` | `['xs', 'sm', 'md', 'lg', 'xl']` — valid abstract size names. |
| `ALIASES` | `object` | Semantic name → size mapping: `{pill: 'xs', 'list-item': 'sm', card: 'md', detail: 'lg', page: 'xl'}`. |
| `normalizeDisplay(value)` | `function` | Resolves a display value (abstract or semantic) to an abstract size. Returns `null` for `'auto'` or unrecognized values. |

### Stylesheet Hook

```javascript
// Override in subclass:
get styles() { return new URL('./my-component.css', import.meta.url).href; }
```

The base Component creates a `<link rel="stylesheet">` element in the constructor if `styles` returns a non-null URL. The `$styles` property holds the link element for re-appending after innerHTML rewrites.

### Adaptive Display Mode

Every component gets space-awareness via ResizeObserver. Sizes use abstract names (`xs`–`xl`) with optional semantic aliases (`pill`, `card`, etc.).

**Sizes:**

| Size | Alias | Default Breakpoint | NTTItem Rendering |
|------|-------|--------------------|-------------------|
| `xs` | `pill` | 0px+ | Name badge only |
| `sm` | `list-item` | 200px+ | Compact row: name + 2–3 key fields |
| `md` | `card` | 400px+ | Full card: edit + form + methods |
| `lg` | `detail` | 600px+ | Detail view (future: normally-hidden fields) |
| `xl` | `page` | 800px+ | Page view (future: full metadata) |

**Auto mode (default):** ResizeObserver measures component width and resolves to the largest matching breakpoint.

**Forced mode:** Set the `display` attribute to lock a specific size, bypassing ResizeObserver:

```html
<!-- Abstract size -->
<ntt-item display="sm"></ntt-item>

<!-- Semantic alias -->
<ntt-item display="pill"></ntt-item>

<!-- Programmatic -->
<script>
  document.querySelector('ntt-item').display = 'lg';
</script>

<!-- Back to auto -->
<ntt-item display="auto"></ntt-item>
```

**Override breakpoints:**

```javascript
get displayBreakpoints() {
  return { xl: 800, lg: 600, md: 400, sm: 200, xs: 0 };
}
```

**Hook on mode change:**

```javascript
displayModeChanged(oldMode, newMode) {
  // Default: re-renders if schema available
  // Override for CSS-only mode switching:
  this.shadowRoot.host.setAttribute('data-mode', newMode);
}
```

### Schema Resolution Flow

```
1. model="Product" attribute set
2. attributeChangedCallback sends ATTACH TX → target: 'NTT'
3. NTT bootstraps DynamicClass (fetch schema, create prototype)
4. NTT.attach callback calls component.define(DynamicClass)
5. define() stores proto, calls definedCallback()
6. Subclass overrides definedCallback() for type-specific setup
```

### Subscription Helpers

| Method | Description |
|--------|-------------|
| `subscribe(tt, attribute, callback)` | Subscribe to an observable property on a TT/DynamicClass. Auto-cleans previous subscription. |
| `attach(addr)` | Imperative `NTT.attach(addr, this.define)`. Lazy-imports NTT to avoid circular deps. |

### Lifecycle

| Callback | Behavior |
|----------|----------|
| `connectedCallback()` | Applies forced display mode if set, starts ResizeObserver. |
| `disconnectedCallback()` | Stops ResizeObserver, cleans up subscriptions. |
| `definedCallback()` | Hook called after `define()`. Override in subclasses. |
| `render()` | Abstract — throws if not overridden. |

---

## NTTElement

**File:** `components/NTTElement.js`
**Tag:** Not registered (abstract base — use `NTTItem` or extend directly)

Single entity base class. Handles the data lifecycle for one entity instance.

### Constructor

```javascript
constructor() {
  super({});  // Default value: single entity object
}
```

### Value Override

```javascript
set value(data) {
  super.value = data;
  // Auto-renders when schema + data are both available
  if (this.schema && this.schema.__name__) {
    this.render();
  }
}
```

### Message Handlers

| Handler | Trigger | Behavior |
|---------|---------|----------|
| `UPDATE(data)` | TT watcher notification | Validates `$schema` field, sets value. If schema source changed, sends CONNECT. |
| `DESCRIBE(data)` | NTT instance ATTACH response | Sets `schema = data.proto`, `value = data.data`, renders. |
| `READ(data)` | Direct URL fetch response | Looks up DynamicClass from `data-model` attribute, sets schema + value. |

### Save

```javascript
save() {
  // Sends UPDATE TX with current value to this.ref
  this.send(new TX({ name: 'UPDATE', source: this.addr, target: this.ref, data: this.value }));
}
```

### Developer Pattern

```javascript
import { NTTElement } from './NTTElement.js';

class ProductCard extends NTTElement {
  get styles() { return new URL('./product-card.css', import.meta.url).href; }

  render() {
    if (!this.schema || !this.value) return;
    const { name, price, description } = this.value;
    this.shadowRoot.innerHTML = `
      <div class="product-card">
        <h2>${name}</h2>
        <p>${description}</p>
        <span>$${price?.toFixed(2)}</span>
      </div>
    `;
    if (this.$styles) this.shadowRoot.appendChild(this.$styles);
  }
}
customElements.define('product-card', ProductCard);
```

---

## ListElement

**File:** `components/ListElement.js`
**Tag:** Not registered (abstract base — use `NTTList` or extend directly)

Collection base class. Handles the data lifecycle for a list of entities.

### Constructor

```javascript
constructor() {
  super([]);  // Default value: array
}
```

### Lifecycle

```
1. model="Product" → Component.attributeChangedCallback → ATTACH TX
2. NTT resolves DynamicClass → Component.define(DC) → definedCallback()
3. definedCallback():
   - subscribe(this.proto, 'UPDATE', this.update)
   - this.proto.call('READ', {}, {inbox: 'UPDATE'})
4. Backend responds → DynClass.READ → creates instances → notifies watchers
5. ListElement.UPDATE(["Product/1", "Product/2", ...])
6. render() stamps child elements per address
```

### Message Handlers

| Handler | Trigger | Behavior |
|---------|---------|----------|
| `UPDATE(data)` | DynamicClass watcher notification | Expects array of addresses. Sets value, renders. |

### Child Resolution Chain

When rendering children, `createChild(addr)` resolves the child element to stamp:

```
1. <template item-template> in light DOM     (most explicit)
2. item-tag="..." HTML attribute              (attribute shorthand)
3. get childTag() JS property                 (subclass override)
4. schema.ui.renderer.item                    (schema hint from backend)
5. 'ntt-item'                                 (framework default)
```

### Size Cascade

Children automatically receive a display size based on their parent's current size. This prevents cards-within-cards — a list at `md` renders its children as `xs` pills.

| Parent Size | Child Size |
|-------------|------------|
| `xl` | `md` |
| `lg` | `sm` |
| `md` | `xs` |
| `sm` | `xs` |
| `xs` | `xs` |

Override with the `item-display` attribute:

```html
<!-- Auto cascade (parent md → children xs) -->
<ntt-list model="Product"></ntt-list>

<!-- Force children to sm regardless of parent size -->
<ntt-list model="Product" item-display="sm"></ntt-list>

<!-- Semantic alias works too -->
<ntt-list model="Product" item-display="card"></ntt-list>
```

The `childDisplay` getter resolves: `item-display` attribute > `SIZE_CASCADE[this.displayMode]`.

### Selection API

ListElement includes a Set-based multi-select primitive. Selection state is local to the list and can be read/mutated programmatically.

| Method | Description |
|--------|-------------|
| `selected` | `Set` of selected addresses (read-only getter). |
| `select(addr)` | Add an address to the selection. |
| `deselect(addr)` | Remove an address from the selection. |
| `toggle(addr)` | Toggle an address in/out of the selection. |
| `clearSelection()` | Clear all selections. |

### SELECT TX Handler

When a child item sends a `SELECT` TX to the list:

1. The list calls `toggle(data)` to update selection state.
2. If the list has a `router` attribute, it forwards as a `NAVIGATE` TX to the Router actor.

```html
<!-- router attribute auto-set by ntt-router, or set manually -->
<ntt-list model="Product" router="main"></ntt-list>
```

Children receive a `select-target` attribute (set automatically by `createChild()`) pointing back to the list's address.

### Default Render

```javascript
render() {
  this.shadowRoot.innerHTML = `
    <div class="list-header">
      <h1>${this.model}s</h1>
      <span class="list-count">${this.value.length}</span>
    </div>
    <div class="list-grid"></div>
  `;
  const grid = this.shadowRoot.querySelector('.list-grid');
  this.value.forEach((addr, i) => {
    const child = this.createChild(addr);
    child.style.setProperty('--stagger-delay', `${i * 50}ms`);
    grid.appendChild(child);
  });
}
```

### Developer Pattern

```javascript
import { ListElement } from './ListElement.js';
import './product-card.js';

class ProductGrid extends ListElement {
  get styles() { return new URL('./product-grid.css', import.meta.url).href; }
  get childTag() { return 'product-card'; }
}
customElements.define('product-grid', ProductGrid);
```

Or via HTML composition:

```html
<product-grid model="Product">
  <template item-template>
    <product-card mode="compact"></product-card>
  </template>
</product-grid>
```

---

## NTTItem

**File:** `components/ntt-item.js`
**Tag:** `<ntt-item>`

Built-in zero-config single entity component. Extends NTTElement with adaptive size rendering, Formidable auto-rendering, edit/display toggle, and method buttons.

### Usage

```html
<!-- Default (auto-sized by ResizeObserver) -->
<ntt-item ref="Product/1"></ntt-item>

<!-- Forced size -->
<ntt-item ref="Product/1" display="xs"></ntt-item>
<ntt-item ref="Product/1" display="pill"></ntt-item>
```

### Features

- **Adaptive display**: Size methods (`xs`, `sm`, `md`, `lg`, `xl`) return HTML strings; `render()` dispatches and binds events.
- **Schema-driven form**: Uses `Formidable.getForm()` for `md`/`lg`/`xl` — field ordering, groups, widgets, validation, field exclusion all automatic.
- **Edit/display toggle**: Click edit button → inputs, click save → sends UPDATE TX (md+ sizes only).
- **Method buttons**: Renders `<ntt-method>` for each method in schema (md+ sizes only).
- **Show-more toggle**: Nested ListRef fields collapse after 2 items with expand button.

### Size Methods

Each method returns an HTML string. `render()` dispatches to the current `displayMode` method, commits the HTML to shadow DOM, then binds events via `#bindEvents()`.

| Method | Rendering |
|--------|-----------|
| `xs()` | Pill — entity name as a compact badge (`<span class="pill-label">`). |
| `sm()` | Compact row — name + top 2–3 fields inline. Uses `#topFields(3)` heuristic. |
| `md()` | Card — edit button + `Formidable.getForm()` + method buttons. The current default. |
| `lg()` | Detail — delegates to `md()`. Future: show normally-hidden fields. |
| `xl()` | Page — delegates to `md()`. Future: full metadata, expanded children. |

Override any size method in a subclass to customize just that size:

```javascript
class ProductCard extends NTTItem {
  xs() {
    return `<span class="pill-label">${this.value.name} — $${this.value.price}</span>`;
  }
}
```

### Render Dispatch

```javascript
render() {
  const size = this.displayMode;                    // e.g. 'md'
  const html = (this[size] || this.md).call(this);  // call size method
  this.shadowRoot.innerHTML = `<div class="card" data-display="${size}">${html}</div>`;
  this.#bindEvents();                               // generic event wiring
  this[`${size}_mounted`]?.call(this);              // optional post-render hook
}
```

The `data-display` attribute on `.card` drives CSS scoping (e.g. `.card[data-display="xs"]`).

### Private Helpers

| Helper | Description |
|--------|-------------|
| `#bindEvents()` | Binds edit button click, input/textarea change, show-more toggle. Selector-based — tolerant of missing elements. |
| `#topFields(count)` | Returns the top N visible, non-header, non-array fields as `[key, def]` pairs. Respects `ui.field_order`, `ui.display`, and permissions. |
| `#methodsHtml()` | Generates `<ntt-method>` HTML for all schema methods. |

### Input Handling

`handleInputChange(e)` reads `data-key`, `data-type`, `data-index` from the input element and updates `this.value`. Supports strings, numbers, booleans (checkbox), and array items.

---

## NTTList

**File:** `components/ntt-list.js`
**Tag:** `<ntt-list>`

Built-in zero-config collection component. Extends ListElement with a stylesheet.

### Usage

```html
<ntt-list model="Product"></ntt-list>
```

### Implementation

```javascript
class NTTList extends ListElement {
  get styles() { return new URL('./ntt-list.css', import.meta.url).href; }
}
customElements.define('ntt-list', NTTList);
```

All logic (fetch, render, child stamping) is inherited from ListElement. This is 19 lines — the thinnest possible shell.

---

## NTTMethod

**File:** `components/ntt-method.js`
**Tag:** `<ntt-method>`

Renders a form for invoking a custom method on a model or instance.

### Usage

```html
<ntt-method model="Product" uuid="1" method="comment" label="Add Comment"></ntt-method>
```

### Attributes

| Attribute | Description |
|-----------|-------------|
| `model` | Model name for NTT lookup. |
| `method` | Method name from `schema.methods`. |
| `uuid` | Instance ID (for instance methods). |
| `mode` | `"manual"` (button submit) or `"auto"` (submit on input). |
| `label` | Display label for the fieldset. |
| `forward` | Optional DynamicClass address to forward results to. |

### Behavior

1. `load()`: Resolves DynamicClass via `NTT.get(this.model)`, optionally resolves NTT instance, reads method schema.
2. `render()`: Generates form inputs from `schema.parameters`. Resolves `$ref` parameters via `$defs`.
3. `callMethod()`: Calls `target.call(method, payload)` on the NTT instance or DynamicClass.
4. Displays response as JSON pre block.

---

## Router

**File:** `core/Router.js`
**Type:** Actor (not a web component)

Pure navigation state Actor. Manages route state, a history stack, and optional hash sync. No DOM — view management is the ntt-router's responsibility.

### Constructor

```javascript
import { Router, getRouter } from './core/Router.js';

const router = new Router('main', { hash: true });
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `addr` | `string` | required | Actor address (also the key in the router registry). |
| `hash` | `boolean` | `false` | Enable `location.hash` sync for string routes. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `current` | `string\|object\|null` | Current route data. `null` = home (slot). |
| `canGoBack` | `boolean` | Whether the history stack has entries. |

### TX Handlers

| Handler | Data | Behavior |
|---------|------|----------|
| `NAVIGATE(data)` | `string` or `object` | Push current to stack, set new route, update hash, notify observers. |
| `BACK(data)` | (ignored) | Pop stack, update hash, notify observers. |

### Observable

```javascript
router.observe('route', (newRoute, oldRoute) => {
  console.log('Navigated from', oldRoute, 'to', newRoute);
});
```

### NAVIGATE Data Formats

| Form | Example | Description |
|------|---------|-------------|
| **String** (entity ref) | `"Product/3"` | ntt-router resolves tag from schema. Serialized to `location.hash`. |
| **Object** (explicit spec) | `{ tag: 'ntt-list', attrs: { model: 'Comment' }, title: 'Comments' }` | ntt-router creates the exact element. No hash representation. |

### Hash Sync

When `hash: true`:
- String routes serialize to `location.hash` (e.g., `#Product/3`).
- Object routes are programmatic-only (no hash).
- `null` route clears the hash.
- Browser back/forward triggers `hashchange`, which updates Router state.

### Registry

```javascript
import { getRouter } from './core/Router.js';

const router = getRouter('main');  // Retrieve by addr
```

---

## NTTRouter

**File:** `components/ntt-router.js`
**Tag:** `<ntt-router>`
**CSS:** `components/ntt-router.css`

Generic view container — a "mini browser" controlled via TX. Loads any component dynamically. Never needs editing to support new views.

### Usage

```html
<ntt-router name="main" hash>
    <ntt-list model="Product"></ntt-list>
</ntt-router>
```

### Attributes

| Attribute | Description |
|-----------|-------------|
| `name` | Router actor address. Auto-generated if omitted. |
| `hash` | Presence enables hash sync on the Router actor. |

### Behavior

1. **Slot content = home page**: Declared children are the default view (shown when `route === null`).
2. **NAVIGATE pushes a view**: Hides slot, creates the requested component, mounts it in shadow DOM.
3. **BACK pops the view**: Destroys current view, restores slot (light DOM children stay alive — no re-fetch).
4. **Back button**: Shown when history stack has entries. Sends `BACK` TX to Router.
5. **Auto-configure**: Sets `router` attribute on child `[model]` elements in `connectedCallback`.

### Slot Persistence

When ntt-router shows a dynamic view, the `<slot>` is removed from shadow DOM. But the light DOM children (`<ntt-list>`) stay alive — they keep their data, subscriptions, and state. Going back restores the `<slot>`, and the list re-projects instantly with no re-fetch or re-render.

### Tag Resolution (String Routes)

For string routes like `"Product/3"`, ntt-router resolves the component tag:

```
1. schema.ui.renderer.detail    (model-specific detail tag)
2. schema.ui.renderer.item      (model-specific item tag)
3. 'ntt-item'                   (framework default)
```

The resolved element receives a `ref` attribute with the full route string.

### Chrome

The router chrome (back button + title) only appears when a dynamic view is active:

- **Back button**: Left arrow SVG, sends `BACK` TX.
- **Title**: Model name (string route) or `routeData.title` (object route).

---

## Formidable

**File:** `generators/form.js`

Stateless schema-driven HTML generator. Produces HTML strings (not DOM elements) from a schema + value pair. Used by NTTItem for zero-config rendering, but also available to any custom component.

### API

```javascript
import { Formidable } from '../generators/form.js';

// Full form with header + fields:
Formidable.getForm({ schema: jsonSchema, value: entityData }, 'display');
Formidable.getForm({ schema: jsonSchema, value: entityData }, 'edit');

// Single field:
Formidable.getInput(ntt, 'fieldName', 'edit');

// List/relationship field:
Formidable.getListInput(ntt, 'comments', 'display');

// Validation attributes string:
Formidable.validationAttrs(fieldDef, isRequired);

// Grouped field rendering:
Formidable.renderGroupedFields(ntt, fields, groups, 'display');
```

### Field Ordering

If `schema.ui.field_order` exists, fields render in that order. Fields not in the list are appended at the end (safety net for schema additions).

### Field Groups

When `schema.ui.groups` is defined:

```json
"ui": {
  "groups": {
    "main": ["name", "description"],
    "pricing": ["price"]
  }
}
```

Fields are wrapped in `<fieldset class="ntt-group ntt-group-{name}">` with `<legend>` per group. Ungrouped fields render after all groups.

### Widget Hints

`ui.widget` on a field definition takes priority over `type`:

| Widget | Edit Mode | Display Mode |
|--------|-----------|--------------|
| `textarea` | `<textarea>` | `<div class="text-block">` |
| `currency` | `<input type="number" step="0.01">` + `$` prefix | `$X.XX` formatted |

### Schema-Driven Validation

`validationAttrs(def, isRequired)` maps JSON Schema constraints to HTML5 validation attributes:

| Schema | HTML Attribute |
|--------|---------------|
| `minLength` | `minlength` |
| `maxLength` | `maxlength` |
| `minimum` / `exclusiveMinimum` | `min` |
| `maximum` / `exclusiveMaximum` | `max` |
| `pattern` | `pattern` |
| `schema.required` includes field | `required` |
| `ui.placeholder` | `placeholder` |

### Field Exclusion

Fields with `ui.display === false` are skipped. Applied automatically by backend conventions (`*_id`, `id`, timestamps) or explicitly via `json_schema_extra`.

### Relationship Rendering

`getListInput()` handles `ListRef` array fields:

- Extracts referenced model name from `items.$ref`
- Resolves child tag from `$defs[model].ui.renderer.item` (falls back to `ntt-item`)
- Renders header with model label + count badge
- Collapses items beyond VISIBLE_COUNT (2) with show-more button

### Type Resolution

| Schema Type | Edit Mode | Display Mode |
|-------------|-----------|--------------|
| `string` | `<input type="text">` | `<div>value</div>` |
| `number` | `<input type="number">` | `<div>value</div>` |
| `boolean` | `<input type="checkbox">` | `<div>value</div>` |
| `text` | `<textarea>` | `<div>value</div>` |
| `selfref` | `<input type="number" placeholder="Parent ID">` | `[Parent: #id]` or `(top-level)` |
| `$ref` | — | `[Reference: name or id]` |
| `array` | `getListInput()` | `getListInput()` |

Handles `anyOf` schemas (Pydantic Optional fields) by stripping the null type via `resolveAnyOf()`.

---

## Scaffolding

**File:** `src/pybend/core/utils/scaffold.py`

Generates starter component files from a model's schema, bridging the gap between zero-config Formidable rendering and fully custom components.

### CLI

```bash
cd /workspace/src/pybend/core
python -m utils.scaffold Product
# Generates:
#   components/product-card.js    (extends NTTElement)
#   components/product-card.css   (glass morphism starter)
#   components/product-grid.js    (extends ListElement)
#   components/product-grid.css   (grid layout starter)
```

### API Endpoint

```
GET /Product?scaffold=item       → JS item component (text/plain)
GET /Product?scaffold=list       → JS list component
GET /Product?scaffold=css        → Item CSS
GET /Product?scaffold=list-css   → List CSS
```

### What Gets Generated

**Item component**: NTTElement subclass with:
- Explicit `render()` with destructured fields from schema
- Header fields (`name`, `description`) as `<h2>` / `<p>`
- Widget-aware display (currency → `$X.XX`, textarea → `<p>`)
- ListRef fields → nested `<ntt-item>` components
- `<ntt-method>` buttons for schema methods
- `get styles()` pointing to companion CSS

**List component**: ListElement subclass with:
- `get childTag()` returning the item tag
- `get styles()` pointing to companion CSS

**CSS files**: Glass morphism card, field-specific selectors, stagger animation.

### Programmatic Use

```python
from utils.scaffold import scaffold_item, scaffold_single, scaffold_model

# Generate source string
js = scaffold_single('Product', kind='item')

# Write all files
scaffold_model('Product', output_dir=Path('./my-components'))
```
