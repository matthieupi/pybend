# Components

> Part of [n3tx-ui](../README.md)

## What This Covers

The component class hierarchy, message handlers, lifecycle hooks, and extension points. Covers `NTTElement`, `ListElement`, and their concrete subclasses. Does not cover the form generator (see [formidable.md](formidable.md)) or the widget system (see [widgets.md](widgets.md)).

## Architecture

```
Component (n3tx-core: shadow DOM, addr, ref, model, proto, define(), scheduleRender())
  |
  +-- NTTElement (NTTElement.js)          -- Single entity base
  |     Message handlers: UPDATE, DESCRIBE, READ, ERROR
  |     Methods: save(), update(prev, next), onValidationError(errors)
  |     Auto-renders on value change when schema is set
  |     |
  |     +-- NTTItem (ntx-item.js)         -- <ntx-item>
  |     |     Size methods: xs(), sm(), md(), lg(), xl(), row()
  |     |     Modes: display / edit (toggleMode, cancelEdit)
  |     |     Validation: showFieldErrors(), client-side via Formidable
  |     |     Event binding: edit, delete, input change, card click -> SELECT
  |     |     |
  |     |     +-- NTTRow (ntx-row.js)     -- <ntx-row>
  |     |     |     Forces display="row", inline edit with collectInputValues
  |     |     |
  |     |     +-- NTTUser (ntx-user.js)   -- <ntx-user>
  |     |           Overrides xs/sm with avatar rendering
  |     |
  |     +-- (custom subclasses extend NTTElement directly for full control)
  |
  +-- ListElement (ListElement.js)        -- Collection base
  |     Message handlers: UPDATE, SELECT
  |     Methods: loadMore(), openCreateModal(), createChild(addr)
  |     Selection API: select/deselect/toggle/clearSelection
  |     Pagination: #pageSize=20, #offset tracking
  |     |
  |     +-- NTTList (ntx-list.js)         -- <ntx-list>
  |     |     Default grid list, stamps childTag per entity
  |     |
  |     +-- NTTTable (ntx-table.js)       -- <ntx-table>
  |           Table with header sort, inline create row, stamps ntx-row
  |
  +-- NTTMethod (ntx-method.js)           -- <ntx-method>
  |     Layouts: fieldset (default), inline, button
  |     Loads method schema, renders input form, calls entity method
  |     |
  |     +-- NTTStream (ntx-stream.js)     -- <ntx-stream>
  |           Overrides callMethod() for streaming via TX meta.stream
  |           Progressive output rendering with cursor animation
  |
  +-- NTTRouter (ntx-router.js)           -- <ntx-router>
        View container. Slot = home. NAVIGATE pushes views, BACK pops.
        Resolves component tags from schema ui.renderer hints.
```

Standalone (no Component base): `NTTModal`, `NTTRefPicker`, `NTTTopbar`, `NTTSidebar`, `NTTProfile`.

## Interface

### NTTElement (single entity base)

```javascript
class NTTElement extends Component {
    // State
    $schema;          // Schema name for CONNECT flow
    error;            // Persistent error message (string|null)

    // Value setter triggers auto-render when schema is available.
    // deepEqual guard prevents infinite loops from signal re-fires.
    set value(data);

    // Message handlers (called by Actor inbox dispatch)
    UPDATE(data);     // Receives entity data push. Requires data.$schema.
    DESCRIBE(data);   // Receives {proto, data}. Subscribes to entity signal.
    READ(data);       // Receives data from URL fetch (ListRef href resolution).
    ERROR(event);     // Handles errors. Extracts validation errors from 422.

    // Override points
    update(prev, next);              // Surgical DOM patch. Return false -> full render().
    onValidationError(errors);       // Hook for structured validation errors.
    render();                        // Override for custom rendering.

    // Actions
    save();           // Sends UPDATE TX to entity ref.
}
```

### ListElement (collection base)

```javascript
class ListElement extends Component {
    // Selection
    get selected();               // Set of selected addresses
    select(addr); deselect(addr); toggle(addr); clearSelection();

    // Data
    definedCallback();            // Called when proto arrives. Triggers READ.
    loadMore();                   // Paginated fetch: offset += pageSize.

    // Message handlers
    UPDATE(data);                 // Receives entity address array.
    SELECT(data, tx);             // Toggle selection, forward NAVIGATE to router.

    // Override points
    get childTag();               // Tag for stamped children. Default: 'ntx-item'.
    get childDisplay();           // Display mode for children. Cascades from parent.
    createChild(addr);            // Create child element. Checks <template item-template>.
    update(prev, next);           // Surgical list patch (add/remove children).
    render();                     // Override for custom collection rendering.
    openCreateModal();            // Opens NTTModal with create form.
}
```

### NTTItem key attributes

| Attribute | Effect |
|-----------|--------|
| `display` | Size mode: xs, sm, md, lg, xl, row |
| `ref` | Entity address (href URL) |
| `model` | Model class name |
| `select-target` | Actor address to send SELECT TX to |
| `create-mode` | Present = create mode (no existing data) |

### ListElement/NTTList key attributes

| Attribute | Effect |
|-----------|--------|
| `model` | Model class name to list |
| `display` | List display size (cascades to children) |
| `router` | Router actor address for SELECT navigation |
| `item-tag` | Override child tag (default from schema) |
| `item-display` | Override child display mode |
| `headless` | Hide the header (title + count) |
| `allow-create` | Show the create button (permission-gated) |

## Usage Patterns

### Custom entity component

Extend NTTElement for full control over rendering:

```javascript
import { NTTElement } from '../components/NTTElement.js';

class ProductCard extends NTTElement {
    get styles() { return new URL('./product-card.css', import.meta.url).href; }

    render() {
        if (!this.schema || !this.value) return;
        this.shadowRoot.innerHTML = `
            <h2>${this.value.name}</h2>
            <p>$${this.value.price}</p>
        `;
        this._rendered = true;
    }
}
customElements.define('product-card', ProductCard);
```

### Templated list children

Use a `<template>` to customize what ListElement stamps per item:

```html
<ntx-list model="Product">
    <template item-template>
        <product-card></product-card>
    </template>
</ntx-list>
```

### Sidebar with route templates

Declarative route templates control what the sidebar navigates to:

```html
<ntx-sidebar router="main">
    <ntx-table model="Grant" allow-create></ntx-table>
    <ntx-list model="Source"></ntx-list>
</ntx-sidebar>
```

## Gotchas

- **NTTElement value setter has a deepEqual guard** that skips re-render if the new value is semantically identical to the previous one. This prevents infinite loops from signal subscriptions but means the initial set (from constructor default `{}`) must bypass the guard. The guard only activates after `_rendered` is true.

- **NTTItem.sm() delegates to md() in edit mode.** If you override sm() but not md(), editing in sm context will use the default md() form. Override md() if you need custom edit forms at compact sizes.

- **ListElement.definedCallback() deduplicates READ calls.** If another list instance for the same model already triggered a READ, `proto._listReadPending` is true and the second list skips the request. Both lists get notified when the READ completes via the UPDATE observable.

- **AbortController for event listeners.** NTTItem and NTTRow create a new AbortController per render and abort the previous one. This prevents listener accumulation. If you extend these classes and add custom listeners, use the same pattern with `{signal}`.

- **NTTStream binds a dynamic handler** named after the method (e.g., `this.GENERATE = (data, tx) => ...`). If the method name changes, the old handler is unbound. The handler dispatches based on `tx.meta`: stream_end -> onDone, error -> onError, else -> onChunk.

- **NTTModal locks body scroll** (`document.body.style.overflow = 'hidden'`) while open and restores on close via the `modal-close` event listener.
