# UI Components Reference

Documentation for the web component layer that renders NTT data in the browser.

## Table of Contents

1. [Component (base)](#component)
2. [NTTElement](#nttelement)
3. [List](#list)
4. [Item](#item)
5. [NTTMethod](#nttmethod)
6. [Formidable (form generator)](#formidable)

---

## Component

**File:** `core/Component.js`
**Tag:** Not registered as a custom element (abstract base class)

Base class for all NTT web components. Extends `HTMLElement` and integrates with the Actor system.

### Constructor

```javascript
constructor() {
  super();
  this.#hash = this.getAttribute('hash') || generateId();
  this.#addr = this.getAttribute('addr') || `${this.constructor.name}-${this.#hash}`;
  matrix.register(this);                 // Register in Matrix children
  this.constructor.register(this);       // Register in class-level children (e.g., Component.children)
}
```

### Actor Integration

```javascript
Actor.subclass(Component);
matrix.register(Component);  // Component CLASS is a Matrix child
```

This means:
- `Component.send(tx)` routes through Actor._send in Component's context
- `Component.inbox(tx)` dispatches to Component's static/instance handlers
- Individual component instances are registered in `Component.children`

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `addr` | `string` | Unique address. Set once in constructor, immutable. |
| `hash` | (via attribute) | Optional hash for deterministic addressing. |

### Observed Attributes

`['addr', 'hash']`

### Lifecycle

| Callback | Behavior |
|----------|----------|
| `connectedCallback()` | Empty (override in subclass). |
| `disconnectedCallback()` | Logs disconnect. |
| `render()` | Throws not-implemented error (must override). |

---

## NTTElement

**File:** `components/ntt-element.js`
**Tag:** `<ntt-element>`

Extends Component with model/schema/value binding. The primary bridge between the Actor messaging system and the DOM.

### Constructor

```javascript
constructor(defaultValue={}) {
  super();
  this.attachShadow({mode: 'open'});
  this.#model = this.getAttribute('model');
  this.#href = this.getAttribute('href');
  this.#data = defaultValue;
}
```

### Observed Attributes

`['model', 'addr', 'hash', 'ref']`

### Key Properties

| Property | Type | Description |
|----------|------|-------------|
| `model` | `string` | Model name (e.g., "Product"). |
| `ref` | `string` | Reference address. Setting this sends ATTACH to that address. |
| `proto` | `PTT` | The PTT prototype (set via `define()`). |
| `schema` | `object` | JSON schema from proto. Cached in `_schema`. |
| `value` | `object` | Current entity data. Setting triggers `render()` if `_type` is set. |

### Attribute Change Behavior

```javascript
attributeChangedCallback(name, oldVal, newVal) {
  if (name === 'model') {
    // Send ATTACH to PTT class with model name as data
    TX { name: ATTACH, source: this.addr, target: 'PTT', data: newVal }
  }
  if (name === 'ref') {
    // Send ATTACH to the referenced address
    this.ref = newVal;  // triggers ref setter -> TX { ATTACH ... }
  }
}
```

### Methods

| Method | Description |
|--------|-------------|
| `define(ptt)` | Called when PTT schema is ready. Stores proto, calls `definedCallback()`. |
| `describe(proto, data)` | Sets proto + value in one call. |
| `update(data)` | Sets value if data is provided. |
| `subscribe(tt, attribute, callback)` | Observes a property on a TT instance. |
| `attach(addr)` | Calls `PTT.attach(addr, this.define)`. |
| `render()` | Abstract - must be overridden by subclasses. |

### Lifecycle Hook

| Hook | Description |
|------|-------------|
| `definedCallback()` | Called by `define()` after proto is set. Override in subclasses to trigger data loading. |

---

## List

**File:** `components/ntt-list.js`
**Tag:** `<ntt-list>`

Renders a list of `<ntt-item>` elements for a given model.

### Usage

```html
<ntt-list model="Product"></ntt-list>
```

### Lifecycle

```
1. Constructor -> super() (NTTElement -> Component)
2. connectedCallback -> super.connectedCallback()
3. attributeChangedCallback("model", "Product")
   -> Sends ATTACH to PTT with "Product"
4. PTT resolves, fires signal -> define() -> definedCallback()
5. definedCallback():
   - subscribe(this.proto, 'UPDATE', this.update)
   - this.proto.call('READ', {}, {inbox: 'UPDATE'})
6. Backend responds -> PTT.READ creates instances -> PTT.notify()
   -> List.UPDATE(data) with array of address strings
7. render() creates <ntt-item ref="addr"> per entry
```

### Actor Message Handlers

| Handler | Trigger | Behavior |
|---------|---------|----------|
| `UPDATE(data)` | PTT notifies with child addresses | Sets value to address array, calls render(). |

### Render

```javascript
render() {
  // Creates shadowRoot with grid layout + h1 header
  // For each address string in this.value:
  //   const el = document.createElement('ntt-item')
  //   el.ref = address   // triggers Item ATTACH protocol
  //   shadowRoot.appendChild(el)
}
```

### Actor Integration

```javascript
Actor.subclass(List);  // After class definition
```

---

## Item

**File:** `components/ntt-item.js`
**Tag:** `<ntt-item>`

Renders a single entity as a card with editable form fields.

### Usage

Created programmatically by List:

```javascript
const el = document.createElement('ntt-item');
el.ref = "Product/1";  // Triggers ATTACH protocol
```

### Constructor

```javascript
constructor() {
  super({});  // NTTElement with empty object as default value
  this.mode = this.getAttribute('mode') || 'display';
  // Attaches ntt-item.css stylesheet to shadow DOM
  this._type = undefined;  // Guards render() until type is known
}
```

### Actor Message Handlers

| Handler | Trigger | Behavior |
|---------|---------|----------|
| `UPDATE(data)` | TT watcher notification | Validates `@type` field exists. Sets value. If type changed, sends CONNECT to the new type. |
| `DESCRIBE(data)` | NTT responds to ATTACH | Sets `this.schema = data.proto`, `this.value = data.data`, calls `render()`. |

### Render

```javascript
render() {
  // Builds HTML:
  // 1. Edit/Save button
  // 2. Formidable.getForm({schema: this.schema, value: this.value}, this.mode)
  //    - Header (h2 name, h4 description)
  //    - Form fields per schema property
  // 3. (ntt-method rendering currently commented out)
  //
  // Sets innerHTML on shadow DOM
  // Attaches event listeners for edit toggle and input changes
}
```

### Edit Mode

| Mode | Behavior |
|------|----------|
| `display` | Shows values as text, edit button shows pencil icon. |
| `edit` | Shows inputs/textareas, button shows save icon. |

Toggle via `toggleMode()`:
- On save: calls `this.value.call('UPDATE', this.value.value)` or `this.proto.call('UPDATE', ...)`.
- Switches mode and re-renders.

### Input Handling

`handleInputChange(e)` reads `data-key`, `data-type`, `data-index` from the input element and updates `this.value` accordingly. Supports scalars, checkboxes, and array items.

---

## NTTMethod

**File:** `components/ntt-method.js`
**Tag:** `<ntt-method>`

Renders a form for invoking a custom method on a model or instance.

**Note:** Currently commented out in Item.render() — not actively used in the v0.6 WIP flow.

### Usage

```html
<ntt-method model="Product" uuid="1" method="comment" label="Add Comment"></ntt-method>
```

### Attributes

| Attribute | Description |
|-----------|-------------|
| `model` | Model name for PTT lookup. |
| `method` | Method name from schema.methods. |
| `uuid` | Instance ID (for instance methods). |
| `mode` | `"manual"` (button submit) or `"auto"` (submit on input). |
| `label` | Display label for the fieldset. |
| `forward` | Optional PTT address to forward results to. |

### Behavior

1. `load()`: Resolves PTT, optionally resolves NTT instance, reads method schema.
2. `render()`: Generates form inputs from `schema.parameters`.
3. `callMethod()`: Calls `target.call(method, payload)` on the NTT instance or PTT.
4. Displays response as JSON in the component.

---

## Formidable

**File:** `generators/form.js`

Schema-driven HTML form generator. Produces HTML strings (not DOM elements) from a schema + value pair.

### API

```javascript
import { Formidable } from '../generators/form.js';

// Main entry point:
Formidable.getForm({ schema: jsonSchema, value: entityData }, mode);
// Returns: HTML string

// Individual field:
Formidable.getInput(ntt, key, mode);

// Reference input (uses PTT lookup):
Formidable.refInput(refName);
```

### getForm({schema, value}, mode)

1. Extracts `schema.properties` and `value.name`.
2. Generates header via `getHeader()`:
   - `display` mode: `<h2>name</h2>` + `<h4>description</h4>`
   - `edit` mode: `<input>` for name + `<textarea>` for description
3. Iterates remaining fields (skipping `name`, `id`, `description`).
4. Calls `getInput()` per field.
5. Returns concatenated HTML string.

### getInput(ntt, key, mode)

Generates appropriate input based on schema type:

| Schema Type | Edit Mode | Display Mode |
|-------------|-----------|--------------|
| `string` | `<input type="text">` | `<div>value</div>` |
| `number` | `<input type="number">` | `<div>value</div>` |
| `boolean` | `<input type="checkbox">` | `<div>value</div>` |
| `text` | `<textarea>` | `<div>value</div>` |
| `$ref` | - | `[Reference: name or id]` |
| `array` | (commented out) | (commented out) |

Handles `anyOf` schemas (Pydantic Optional fields) by stripping the null type via `resolveAnyOf()`.

All inputs include `data-key` and `data-type` attributes for the Item's `handleInputChange()` to read.

### getArrayInput (commented out)

Would render a `<ntt-list>` sub-component for array fields with `$ref` items. Currently disabled.
