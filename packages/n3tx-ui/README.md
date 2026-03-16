# 🎨 n3tx-ui: Your Schema Paints the Screen

> Schema-driven Web Components that render any N3TX model with zero frontend code. Define a Python model, get a full UI -- lists, cards, forms, tables, streaming output -- all wired up for you.

## 🌐 Overview

n3tx-ui is the visual layer of the N3TX stack. You hand it a JSON Schema from the backend and it handles everything the user sees -- lists, cards, tables, forms, method buttons, streaming output. All derived from the schema at runtime. You define Python models; this package takes care of the pixels.

It builds on top of `n3tx-core` (which provides the core JS: NTT, Component, Actor, Matrix, TX, Router). This package adds what your users actually interact with: components, form generators, widgets, and themes.

---

## 📦 Installation

Getting started is one line:

```bash
pip install n3tx-ui            # standalone
pip install n3tx[all]           # full framework meta-package
pip install -e packages/n3tx-ui # editable dev install
```

## 🚀 Quick Start

The Python export is a single function -- the real magic lives in the static JS files it serves:

```python
from n3tx_ui import get_static_dir

# Returns Path to static/ directory containing components/, generators/, widgets/
static_path = get_static_dir()

# In a FastAPI app, mount it:
app.mount("/static/ui", StaticFiles(directory=get_static_dir()), name="ui-static")
```

Then in your HTML, just drop in the components. They self-register via `customElements.define` -- no build step, no bundler dance:

```html
<link rel="stylesheet" href="/static/ui/dark-theme.css">
<script type="module" src="/static/core/NTT.js"></script>
<script type="module" src="/static/ui/components/ntx-list.js"></script>

<ntx-topbar brand="My App"></ntx-topbar>
<ntx-router name="main" hash>
  <ntx-list model="Product" allow-create router="main"></ntx-list>
</ntx-router>
```

That's it. Your Product model is now a working UI.

---

## 🧱 Core Concepts

Here's where it gets fun. Let's walk through the building blocks.

### 🏗️ Component Hierarchy

Two base classes, two built-in concrete classes per base. You extend these to build your own:

```
Component (n3tx-core)
  |
  +-- NTTElement       Single entity lifecycle (UPDATE/DESCRIBE/READ/ERROR/save)
  |     +-- NTTItem    Zero-config entity renderer (ntx-item) -- xs/sm/md/lg/xl sizes
  |     +-- NTTRow     Table row variant (ntx-row) -- inline edit
  |     +-- NTTUser    User entity with avatar (ntx-user)
  |
  +-- ListElement      Collection lifecycle (READ/UPDATE/SELECT/pagination)
        +-- NTTList    Grid list renderer (ntx-list)
        +-- NTTTable   Table renderer with sortable columns (ntx-table)
```

### 📐 Display Modes

NTTItem adapts its rendering based on a `display` attribute. Each size is a method returning an HTML string -- from a tiny pill to a full page:

| Mode | Tag attribute | Renders as |
|------|--------------|------------|
| `xs` | `display="xs"` | Pill badge (name only) |
| `sm` | `display="sm"` | Compact row (avatar + name + 3 fields) |
| `md` | `display="md"` | Card with full form + methods |
| `lg` | `display="lg"` | Detail view (same as md, future: expanded) |
| `xl` | `display="xl"` | Full page (same as md, future: all metadata) |
| `row`| `display="row"` | Table row (raw cells for ntx-table) |

### 📝 Formidable (Form Generator)

This is where the zero-config magic really kicks in. `Formidable` reads your schema properties and generates HTML forms. Field ordering, grouping, permission filtering, widget dispatch, validation, display formatting -- all handled. One module, no configuration:

```javascript
import { Formidable } from '../generators/form.js';
// Generate form HTML from schema
const html = Formidable.getForm({schema, value, ref}, 'edit', attachedMethods);
// Validate against schema constraints
const errors = Formidable.validateForm({schema, value});
```

### 🎛️ Widget System

Widgets map `ui.widget` schema hints to specialized renderers. You get three contexts: `display()` (DOM node), `edit()` (DOM node), `list()` (string). The schema drives everything:

```python
# Backend: annotate the field
price: float = Field(json_schema_extra={'ui': {'widget': 'currency'}})
```

```javascript
// Frontend: widget auto-dispatches via registry
import { Widget, registerWidget } from '../widgets/index.js';
class ColorWidget extends Widget {
    display(value, config, schema) { /* return DOM node */ }
}
registerWidget('color', new ColorWidget());
```

### 🔄 Schema-Driven Rendering

This is the core idea: everything flows from the JSON Schema. No hardcoded field names, no model-specific templates. Your schema is the blueprint and the UI follows instructions:

```
Schema.properties        --> form fields (type, validation, placeholder)
Schema.ui.field_order    --> field rendering sequence
Schema.ui.groups         --> fieldset grouping
Schema.ui.renderer       --> component tag resolution
Schema.access            --> edit/delete button visibility
Schema.methods           --> ntx-method / ntx-stream buttons
Schema.$defs             --> nested model registration
```

---

## 📖 API Reference

Here's the full surface area. Everything you can import, mount, and use.

### Python API

| Export | Type | Purpose |
|--------|------|---------|
| `get_static_dir()` | function | Returns `Path` to the static directory |

### 🧩 Web Components (Custom Elements)

These are your building blocks. Drop them in HTML and they just work:

| Tag | JS Class | Base | Purpose |
|-----|----------|------|---------|
| `ntx-item` | `NTTItem` | `NTTElement` | Adaptive entity card (xs-xl sizes) |
| `ntx-list` | `NTTList` | `ListElement` | Grid collection with pagination |
| `ntx-table` | `NTTTable` | `ListElement` | Table collection with sort + inline create |
| `ntx-row` | `NTTRow` | `NTTItem` | Table row with inline edit |
| `ntx-user` | `NTTUser` | `NTTItem` | User entity with avatar |
| `ntx-method` | `NTTMethod` | `Component` | Method invocation button/form |
| `ntx-stream` | `NTTStream` | `NTTMethod` | Streaming method with progressive output |
| `ntx-router` | `NTTRouter` | `Component` | View container with navigation stack |
| `ntx-modal` | `NTTModal` | `HTMLElement` | Overlay dialog (programmatic API) |
| `ntx-ref-picker` | `NTTRefPicker` | `HTMLElement` | Reference field picker + inline create |
| `ntx-topbar` | `NTTTopbar` | `HTMLElement` | Sticky navigation bar with user menu |
| `ntx-sidebar` | `NTTSidebar` | `HTMLElement` | Model navigation sidebar |
| `ntx-profile` | `NTTProfile` | `HTMLElement` | User profile page |

### 🏭 Generators

| Export | Type | Purpose |
|--------|------|---------|
| `Formidable.getForm(ntt, mode, attached)` | function | Generate form HTML from schema |
| `Formidable.getInput(ntt, key, mode)` | function | Generate single field input |
| `Formidable.validateForm(ntt)` | function | Client-side validation against schema |
| `Formidable.formatDisplayValue(def, key, val)` | function | Format value for display |
| `Formidable.clearCache()` | function | Clear layout cache (call on login/logout) |

### 🎛️ Widget System

| Export | Type | Purpose |
|--------|------|---------|
| `Widget` | class | Base class for custom widgets |
| `registerWidget(name, instance)` | function | Register a widget by name |
| `getWidgetForField(fieldSchema)` | function | Look up widget for a field schema |
| `hasWidget(name)` | function | Check if widget is registered |

Built-in widgets: `url`, `email`, `date`, `datetime`, `markdown`, `console`, `reference`, `currency`, `textarea`.

---

## 💡 Patterns and Conventions

A few things that'll save you time as you build with n3tx-ui:

1. **Components never import models.** All rendering is schema-driven. Components read `schema.properties`, `schema.ui`, `schema.access`, and `schema.methods` -- never specific field names (except `name`, `title`, `id` for headers).

2. **Display vs edit mode.** NTTItem has a `mode` property (`'display'` or `'edit'`). In edit mode, `sm` delegates to `md` for the full form. Protected fields (`ui.protected`) are always display-only. Permission checks gate the edit button.

3. **Widget dispatch priority.** `getWidgetForField()` checks `fieldSchema.ui.widget` against the registry. If found, the widget handles all three contexts (display/edit/list). If not found, Formidable falls through to type-based rendering. Fields without `ui.widget` render identically to pre-widget behavior.

4. **Surgical DOM updates.** Both NTTItem and ListElement implement `update(prev, next)` which patches the DOM in-place without full re-render. Returns `true` if patched, `false` to trigger full `render()`. Always check if `update()` handles your case before adding render logic.

5. **Layout cache in Formidable.** Field ordering, permission filtering, and group computation are cached per `schema+mode+role` key. Call `Formidable.clearCache()` on login/logout to refresh permission-dependent layouts.

---

## 🗺️ Package Ecosystem

Here's how n3tx-ui fits into the bigger picture:

```
n3tx-core  <---  n3tx-ui  (this package)
  |                |
  |  JS core:      |  JS UI:
  |  NTT, Actor,   |  ntx-item, ntx-list, ntx-table,
  |  Matrix, TX,   |  Formidable, Widget system,
  |  Component,    |  themes, ntx-router, ntx-modal
  |  Router        |
```

`n3tx-ui` depends on `n3tx-core` for the core JS runtime (NTT.js, Component.js, Actor.js, Matrix.js, TX.js, Router.js). All UI imports reference `../core/` which resolves to n3tx-core's static directory at runtime (served by the framework's static mount).

---

## 🔬 Deep Dives

Want to go deeper? These docs have you covered:

| Topic | File | When to read |
|-------|------|--------------|
| Components | [docs/components.md](docs/components.md) | Building custom components, understanding NTTElement/ListElement lifecycle |
| Formidable & Forms | [docs/formidable.md](docs/formidable.md) | Customizing form generation, field rendering, validation |
| Widget System | [docs/widgets.md](docs/widgets.md) | Creating custom widgets, understanding the registry and rendering contexts |

---

Now go build something your users will love. Your schema's already doing the heavy lifting. 🛠️
