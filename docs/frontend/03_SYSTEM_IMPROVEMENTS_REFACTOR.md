# N3TX Enhancement Plan: Review & Corrections

Critical review of the UI Primitives Enhancement Plan (`02_UI_PRIMITIVES_ENHANCEMENT.md`). Each section identifies a gap or design flaw, explains why it matters, and proposes a concrete fix. These corrections should be applied before implementation begins.

**Companion documents**: `01_UI_SEPARATION_CONCERNS.md` (component analysis), `02_UI_PRIMITIVES_ENHANCEMENT.md` (enhancement plan).

---

## Table of Contents

1. [Typed UI Configuration](#1-typed-ui-configuration)
2. [Child Resolution Chain Simplification](#2-child-resolution-chain-simplification)
3. [ResizeObserver as Opt-In, Not Default](#3-resizeobserver-as-opt-in-not-default)
4. [SSR Pre-Loading Naming Convention](#4-ssr-pre-loading-naming-convention)
5. [Field Exclusion: Convention Discovery](#5-field-exclusion-convention-discovery)
6. [Scaffolding XSS Prevention](#6-scaffolding-xss-prevention)
7. [Renderer Hints: Convention Over Configuration](#7-renderer-hints-convention-over-configuration)
8. [Parallel Sequencing: Backend and Frontend](#8-parallel-sequencing-backend-and-frontend)
9. [Loading and Error States](#9-loading-and-error-states)
10. [Migration Path](#10-migration-path)

---

## 1. Typed UI Configuration

### What 02 Proposes

> The `__ui__` ClassVar is a plain dict, not a Pydantic model. It's injected into the schema output as-is.

### The Problem

An untyped dict means:
- No IDE autocomplete when writing `__ui__` configs
- No validation — a typo like `'feild_order'` silently passes through
- No documentation of valid keys without reading the enhancement doc
- Contradicts N3TX's "transparent, not magical" principle — the framework's most developer-facing config surface has zero guardrails

### The Fix

Define a `TypedDict` (or a simple dataclass) for the `__ui__` structure. This adds zero runtime overhead while giving static analysis, autocomplete, and validation.

```python
from typing import TypedDict, NotRequired

class UIRendererConfig(TypedDict, total=False):
    item: str       # Custom element tag for single entity rendering
    list: str       # Custom element tag for collection rendering

class UIDisplayModeConfig(TypedDict, total=False):
    fields: list[str] | str   # '*' for all, or explicit list
    layout: str                # 'full', 'card', 'inline', 'chip'

class UIConfig(TypedDict, total=False):
    groups: dict[str, list[str]]
    field_order: list[str]
    exclude_render: list[str]
    renderer: UIRendererConfig
    display_modes: dict[str, UIDisplayModeConfig]
```

Usage stays identical:

```python
class Product(ProtoModel):
    __ui__: ClassVar[UIConfig] = {
        'groups': {'main': ['name', 'description']},
        'field_order': ['name', 'price', 'description'],
    }
```

The difference: IDEs now autocomplete keys, type checkers catch typos, and developers can cmd-click `UIConfig` to see every valid option.

### Injection in `ProtoModel.schema()`

No change needed. `TypedDict` instances are regular dicts at runtime — `schema['ui'] = ui_config` works as-is.

---

## 2. Child Resolution Chain Simplification

### What 02 Proposes (§5)

A 5-level resolution chain for which child component a list renders:

```
1. <template item-template>        (light DOM template)
2. item-tag="..." attribute         (HTML attribute)
3. get childTag() JS property       (subclass override)
4. schema.ui.renderer.item          (schema hint)
5. 'ntx-item'                       (framework default)
```

### The Problem

Five levels of override create debugging nightmares. When a list renders the wrong child, the developer has to mentally evaluate all five levels in priority order. The JS property override (level 3) is particularly problematic — it sits between two declarative mechanisms (attribute and schema) and can only be discovered by reading source code.

### The Fix

Collapse to three levels:

```
1. Explicit (template or attribute)    Developer chose this in HTML — highest priority
2. Schema hint                         Backend suggested this — respected unless overridden
3. 'ntx-item'                          Framework default
```

**Remove the `get childTag()` JS override.** Subclasses that need fully custom child rendering should override `render()` directly — that's the right extension point for structural changes. A getter that returns a tag string is a half-measure that creates an invisible override point.

### Implementation

```js
get #resolvedItemFactory() {
  // 1. Explicit: template in light DOM
  const template = this.querySelector('template[item-template]');
  if (template) return () => template.content.firstElementChild.cloneNode(true);

  // 1. Explicit: item-tag attribute
  const itemTag = this.getAttribute('item-tag');
  if (itemTag) return () => document.createElement(itemTag);

  // 2. Schema hint
  const schemaTag = this.schema?.ui?.renderer?.item;
  if (schemaTag) return () => document.createElement(schemaTag);

  // 3. Framework default
  return () => document.createElement('ntx-item');
}
```

Three levels. One declarative, one schema-driven, one default. No hidden JS property to discover.

---

## 3. ResizeObserver as Opt-In, Not Default

### What 02 Proposes (§8)

> Recommended: **Component base**. The ResizeObserver is cheap. Exposing `this.displayMode` to every component costs nothing if unused.

### The Problem

A `ResizeObserver` per component instance is not cheap at scale. A list of 100 items creates 100 observers. Each fires on initial layout, on scroll-triggered reflows, on container resize. The browser's layout engine must report geometry for each observed element separately.

The plan also contradicts itself: §8 is marked **P3** (advanced, "transformative but complex") in the priority table, yet the recommendation is to bake it into the **P0** base class. If it's P3 complexity, it shouldn't be P0 infrastructure.

### The Fix

Make `displayMode` opt-in via a static flag or by detecting whether the subclass uses it.

**Option A — Static flag:**

```js
class Component extends HTMLElement {
  static adaptive = false;  // Subclasses set true to enable

  connectedCallback() {
    super.connectedCallback();
    if (this.constructor.adaptive) {
      this.#initDisplayObserver();
    }
  }
}

// Usage
class ProductCard extends NTTElement {
  static adaptive = true;
  get displayBreakpoints() { return { page: 800, card: 400, chip: 0 }; }
}
```

**Option B — Auto-detect via breakpoints override:**

```js
connectedCallback() {
  super.connectedCallback();
  // Only observe if subclass defines custom breakpoints
  if (this.constructor.prototype.hasOwnProperty('displayBreakpoints')) {
    this.#initDisplayObserver();
  }
}
```

Option A is more explicit. Option B is more "zero-config" but relies on prototype inspection. Either way, the 99% of components that don't use adaptive display pay zero cost.

### What Stays in the Base

The `displayMode` getter and `#initDisplayObserver()` method still live in `Component` — they're available to every subclass. But the observer only activates when requested.

---

## 4. SSR Pre-Loading Naming Convention

### What 02 Proposes (§7)

```html
<script type="application/json" data-ntx-schema="Product">...</script>
<script type="application/json" data-ntx-data="products">...</script>
```

### The Problem

The schema uses the class name (`Product`) but the data uses the table name (`products`). This leaks a backend convention (`__tablename__`) into the HTML template. The developer writing the template needs to know both the model name AND the pluralized table name — and they might not match (`Category` → `categories`, `Person` → `people`, or custom tablenames).

### The Fix

Use the model name for both:

```html
<script type="application/json" data-ntx-schema="Product">...</script>
<script type="application/json" data-ntx-data="Product">...</script>
```

In `N3TX.ATTACH`, look up both by model name:

```js
const preloadedSchema = document.querySelector(`script[data-ntx-schema="${model}"]`);
const preloadedData = document.querySelector(`script[data-ntx-data="${model}"]`);
```

The N3TX core already knows how to map model name → API endpoint (it's in the schema's `$id`). The HTML template shouldn't need to duplicate that knowledge.

### Backend Template

```python
return templates.TemplateResponse("page.html", {
    "model_name": model_name,           # "Product" — used for both attributes
    "schema_json": json.dumps(schema),
    "data_json": json.dumps(data),
})
```

---

## 5. Field Exclusion: Convention Discovery

### What 02 Proposes (§9)

Automatic conventions applied by `ProtoModel.schema()`:
- Fields ending in `_id` → `ui.display: false`
- The `id` field → `ui.display: false`
- `created_at`, `updated_at` → `ui.display: false`

### The Problem

Invisible conventions that hide fields will surprise developers. A `category_id` or `tracking_id` might be meaningful to display. When a field doesn't render and the developer can't see why — no error, no warning, no visible config — they waste time debugging an absence.

The plan provides an explicit override (`json_schema_extra={'ui': {'display': True}}`), but that requires knowing the convention exists in the first place.

### The Fix: Convention + Discoverability

Keep the conventions but make them discoverable through two mechanisms:

**A. Mark convention-hidden fields in the schema output:**

```json
"parent_id": {
  "type": "integer",
  "ui": {
    "display": false,
    "display_reason": "convention:suffix_id"
  }
}
```

The `display_reason` key lets frontend dev tools (and Formidable's debug mode) explain WHY a field is hidden. It costs one extra key per hidden field.

**B. Log in dev mode:**

When `ProtoModel.schema()` applies a convention, emit a debug log:

```python
if field_name.endswith('_id') and not explicit_ui_display:
    logger.debug(f"{cls.__name__}.{field_name}: hidden by convention (suffix_id)")
    prop['ui'] = {'display': False, 'display_reason': 'convention:suffix_id'}
```

This means: conventions work silently in production, but developers running locally can see exactly which fields were auto-hidden and why.

**C. Document the conventions in schema metadata:**

Add a `ui_conventions` key to the schema root (dev mode only) that lists active conventions:

```json
"ui_conventions": [
  {"pattern": "*_id", "effect": "display: false", "override": "json_schema_extra={'ui': {'display': True}}"},
  {"pattern": "id", "effect": "display: false"},
  {"pattern": "created_at|updated_at", "effect": "display: false"}
]
```

This makes the framework self-documenting — a developer inspecting the schema can see what conventions are in play without reading docs.

---

## 6. Scaffolding XSS Prevention

### What 02 Proposes (§10)

Generated scaffold code:

```js
render() {
  const { name, price, description } = this.value || {};
  this.shadowRoot.innerHTML = `
    <h2 class="product-name">${name ?? ''}</h2>
    <p class="product-description">${description ?? ''}</p>
    <span class="product-price">${price ?? ''}</span>
  `;
}
```

### The Problem

This is textbook XSS. If `name` contains `<script>alert('xss')</script>` or `<img onerror="...">`, it executes. Scaffold-generated code is the first thing a developer sees and copies — it should model safe patterns, not teach unsafe ones.

### The Fix

The scaffold should generate DOM-API code, not innerHTML with interpolation:

```js
render() {
  const { name, price, description } = this.value || {};

  const card = document.createElement('div');
  card.className = 'product-card';

  const h2 = document.createElement('h2');
  h2.className = 'product-name';
  h2.textContent = name ?? '';
  card.appendChild(h2);

  const desc = document.createElement('p');
  desc.className = 'product-description';
  desc.textContent = description ?? '';
  card.appendChild(desc);

  const priceEl = document.createElement('span');
  priceEl.className = 'product-price';
  priceEl.textContent = price ?? '';
  card.appendChild(priceEl);

  this.shadowRoot.replaceChildren(this.$styles, card);
}
```

`textContent` is safe by default — it cannot execute HTML. The scaffold teaches the right pattern from day one.

**Alternative**: If `innerHTML` is preferred for readability, the scaffold should generate code using an escape helper:

```js
import { esc } from '../utils/escape.js';

render() {
  const { name, price, description } = this.value || {};
  this.shadowRoot.innerHTML = `
    <h2 class="product-name">${esc(name)}</h2>
    <p class="product-description">${esc(description)}</p>
  `;
}
```

Where `escape.js` is a simple utility:

```js
export function esc(str) {
  const el = document.createElement('span');
  el.textContent = str ?? '';
  return el.innerHTML;
}
```

Either approach works. The generated code must not contain raw interpolation into innerHTML.

---

## 7. Renderer Hints: Convention Over Configuration

### What 02 Proposes (§6)

Backend specifies frontend component tags explicitly:

```python
__ui__: ClassVar[dict] = {
    'renderer': {
        'item': 'product-card',
        'list': 'product-grid',
    }
}
```

### The Problem

This creates tight coupling between backend model definitions and frontend component names. Renaming `product-card` to `product-view` in the frontend requires updating the Python model. The backend must know which custom elements exist in the frontend — a knowledge direction that violates "backend is authoritative" (backend should push schema, not pull frontend component names).

### The Fix: Convention-Based Discovery

Instead of explicit configuration, use a naming convention. The frontend auto-discovers components by model name:

```
Model "Product" → look for <product-item> and <product-list>
Model "Comment" → look for <comment-item> and <comment-list>
```

**Resolution in ListElement:**

```js
get #resolvedItemFactory() {
  // 1. Explicit (template or attribute) — as in §2
  // ...

  // 2. Convention: check if a model-specific element is registered
  const modelName = this.schema?.__name__?.toLowerCase();
  if (modelName) {
    const conventionTag = `${modelName}-item`;
    if (customElements.get(conventionTag)) {
      return () => document.createElement(conventionTag);
    }
  }

  // 3. Framework default
  return () => document.createElement('ntx-item');
}
```

**Benefits:**
- Zero backend configuration needed
- Frontend owns its component names — renaming doesn't touch Python
- Follows existing Web Component conventions (dash-separated tag names)
- Still overridable via explicit attribute or template (level 1)

**When explicit config IS needed**: Keep `ui.renderer` as an escape hatch for cases where the naming convention doesn't fit (e.g., a shared `media-card` component used by both `Photo` and `Video` models). But it should be the exception, not the primary mechanism.

### Updated Resolution Chain

Combining this with §2:

```
1. Explicit (template or attribute)       Developer chose in HTML
2. Convention (model-name-item)           Auto-discovered if registered
3. Schema hint (ui.renderer.item)         Backend override (escape hatch)
4. 'ntx-item'                             Framework default
```

Convention sits above schema hint because it represents an intentional frontend decision (the developer registered a component with that name). Schema hint is the backend's suggestion when no frontend convention exists.

---

## 8. Parallel Sequencing: Backend and Frontend

### What 02 Proposes (§15)

A strictly sequential implementation order:

```
P0 (component refactor) → P1 batch → P2 batch → P3 batch → P4
```

With the P1 batch (field exclusion + `__ui__` schema extensions + slot templates) treated as a single sequential unit after P0.

### The Problem

The backend schema extensions (§4 `__ui__`, §9 field exclusion) touch only `proto_model.py`. They have zero dependency on the frontend component refactor (P0). Blocking them on P0 wastes time — they could ship today and provide immediate value.

### The Fix: Two Parallel Tracks

```
Track A (Backend):                Track B (Frontend):
  §9 Field exclusion                P0 Component refactor
  §4 __ui__ schema extensions       §5 Slot templates
  §11 Validation attributes         §8 Adaptive display (opt-in)
  §6 Renderer hints (schema side)   §13 Relationship rendering
  §7 SSR pre-loading (backend)      §7 SSR pre-loading (N3TX.js)
  §10 Scaffolding                   §6 Renderer hints (frontend)
                                    §12 Permissions (frontend)
```

**Backend Track A** can start immediately. Each item touches `proto_model.py` and/or adds a new utility — no frontend dependency.

**Frontend Track B** starts with P0, then builds on the new class hierarchy. It can consume backend schema extensions as they land.

**Merge points** (items that need both tracks):
- §7 SSR pre-loading: backend template + N3TX.js check (ship backend first, frontend second)
- §6 Renderer hints: schema output (backend) + `#resolvedItemFactory` (frontend)
- §10 Scaffolding: reads `schema()` output (backend) to generate component code (uses frontend API)

This roughly halves the wall-clock time to full implementation.

---

## 9. Loading and Error States

### What 02 Proposes

Nothing. The entire plan covers the happy path exclusively.

### The Problem

Real applications encounter:
- Network failures (`GET /Product` returns 500)
- Slow connections (schema fetch takes 3 seconds)
- Missing models (typo in `<ntx-list model="Prodcut">`)
- Partial data (schema loads, data fetch fails)
- Auth failures (401/403 on data fetch)

Without framework-level handling, every developer must solve these independently — or more likely, won't, and users see blank screens.

### The Fix: Lifecycle Hooks in Component Base

Add three optional hooks to `Component`:

```js
class Component extends HTMLElement {
  // Default implementations — override to customize
  renderLoading() {
    this.shadowRoot.replaceChildren(this.$styles);
    const loader = document.createElement('div');
    loader.className = 'ntx-loading';
    loader.textContent = 'Loading...';
    this.shadowRoot.appendChild(loader);
  }

  renderError(error) {
    this.shadowRoot.replaceChildren(this.$styles);
    const errEl = document.createElement('div');
    errEl.className = 'ntx-error';
    errEl.textContent = error?.message || 'Something went wrong';
    this.shadowRoot.appendChild(errEl);
  }

  renderEmpty() {
    this.shadowRoot.replaceChildren(this.$styles);
    const empty = document.createElement('div');
    empty.className = 'ntx-empty';
    empty.textContent = 'No data';
    this.shadowRoot.appendChild(empty);
  }
}
```

**Integration points:**

| Event | Hook Called | Where |
|---|---|---|
| Component connected, schema not yet loaded | `renderLoading()` | `connectedCallback()` |
| Schema fetch fails | `renderError(err)` | N3TX.ATTACH error path |
| Data fetch fails | `renderError(err)` | DynamicClass.READ error path |
| List receives empty array | `renderEmpty()` | `ListElement.UPDATE()` |
| Auth failure (401/403) | `renderError(err)` | NetworkAdapter response handler |

**Design principle**: These are defaults with zero config. They render minimal, unstyled feedback. Developers override one or all of them. The framework never shows a blank screen when it could show a reason.

### CSS

The base stylesheet provides minimal styling for these states:

```css
.ntx-loading, .ntx-error, .ntx-empty {
  padding: 1rem;
  text-align: center;
  color: var(--ntx-muted, #666);
}
.ntx-error { color: var(--ntx-error, #c00); }
```

---

## 10. Migration Path

### What 02 Proposes

> "Don't break existing."

With no concrete plan for how.

### The Problem

The P0 refactor changes:
- **File locations**: `components/ntx-element.js` is deleted, replaced by `components/NTTElement.js`
- **Class hierarchy**: `NTTElement` moves from `Component` child to `Component` grandchild (with new `NTTElement` base in between)
- **Import paths**: Any code importing from old paths breaks
- **Behavior**: `set value()` no longer auto-renders (moved to NTTElement subclass)

Existing pages using `<ntx-item>` and `<ntx-list>` will work (the custom element tags don't change), but any code that imports or extends the old classes will break.

### The Fix: Explicit Migration Plan

**Phase 1: Parallel availability (during P0)**

Ship new files alongside old ones. Old files become thin re-exports:

```js
// components/ntx-element.js (OLD — becomes shim)
export { NTTElement } from './NTTElement.js';
console.warn('ntx-element.js is deprecated. Import from NTTElement.js instead.');
```

**Phase 2: Deprecation warnings (P1 timeframe)**

Old import paths still work but warn in dev mode. This gives developers a migration window.

**Phase 3: Removal (P2 timeframe)**

Delete the shim files. By this point, any code using old paths has had two priority batches to migrate.

### Custom Element Tag Stability

`<ntx-item>` and `<ntx-list>` tags NEVER change. They are the public API surface. Internal class names and file locations can change; tag names are permanent.

### What Must Be Documented

Before P0 ships, publish a migration checklist:

1. `import { NTTElement } from './ntx-element.js'` → `import { NTTElement } from './NTTElement.js'`
2. `extends Component` (for entity components) → `extends NTTElement`
3. `extends Component` (for collection components) → `extends ListElement`
4. If you relied on `set value()` auto-rendering: add `render()` call in your value handler
5. If you called `describe()`: remove it, use `define()` + `UPDATE()` message handler
6. If you called `Actor.subclass()` on your component: remove it, inherited from Component

---

## Summary: Corrected Priority Table

| Priority | Enhancement | Track | Change from 02 |
|---|---|---|---|
| **P0-A** | `__ui__` TypedDict + field exclusion conventions | Backend | Moved ahead — no frontend dependency |
| **P0-B** | Component layer refactor | Frontend | Unchanged — still the foundation |
| **P0-B** | Loading/error/empty states | Frontend | **New** — built into P0 base classes |
| **P0-B** | Migration shims | Frontend | **New** — ships with P0 |
| **P1-A** | Schema validation attributes | Backend | Unchanged |
| **P1-B** | Slot-based child templates (3-level) | Frontend | Simplified from 5 levels |
| **P2-A** | Renderer hints (schema side) | Backend | Convention-first approach |
| **P2-A** | SSR pre-loading (backend template) | Backend | Fixed naming convention |
| **P2-B** | Convention-based component discovery | Frontend | **New** — replaces explicit renderer config as primary |
| **P2-B** | SSR pre-loading (N3TX.js) | Frontend | Fixed naming convention |
| **P3-A** | Scaffolding (safe codegen) | Backend | XSS-safe output |
| **P3-B** | Adaptive display modes (opt-in) | Frontend | Changed from default to opt-in |
| **P3-B** | Relationship-aware defaults | Frontend | Unchanged |
| **P4** | Schema-driven permissions | Both | Unchanged |
