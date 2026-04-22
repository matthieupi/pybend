# HTML Compiler for N3TX: Schema-Driven Pre-Compilation of Entity Templates

**Research Brief 08** | February 2026
**Audience:** Technical CEOs, Engineering Leadership
**Angle:** How N3TX's schema-driven architecture uniquely enables HTML compilation

---

## Executive Summary

N3TX's architecture carries a rare property: **the JSON Schema is a complete specification** of rendering behavior, not just data types. Field types, widget hints, layout groups, display modes, permission rules, and callable methods are all embedded in the schema document that the backend generates at startup. This means a compiler can produce fully-formed HTML templates at build time with **zero ambiguity** about what to render.

This document maps the exact compilation surface, estimates the performance gains, proposes a concrete Python-side compiler that runs on server start (no npm, no Node, no build step), and honestly assesses whether the current rendering is slow enough to justify the investment.

**Key finding:** Form generation and display-size templates are the highest-value compilation targets. A pre-compiled template approach could eliminate ~70% of runtime DOM construction per entity while preserving N3TX's buildless philosophy.

---

## Table of Contents

1. [Why N3TX Is Uniquely Positioned](#1-why-ntx-is-uniquely-positioned)
2. [The Complete Schema Surface Map](#2-the-complete-schema-surface-map)
3. [What Can Be Compiled (Static at Build Time)](#3-what-can-be-compiled)
4. [What Cannot Be Compiled (Requires Runtime)](#4-what-cannot-be-compiled)
5. [The Compilation Pipeline](#5-the-compilation-pipeline)
6. [Runtime Cost Analysis: Where Time Is Spent Today](#6-runtime-cost-analysis)
7. [Hydration Strategy: Shells + Data Injection](#7-hydration-strategy)
8. [Islands Architecture for N3TX](#8-islands-architecture-for-n3tx)
9. [Declarative Shadow DOM Integration](#9-declarative-shadow-dom)
10. [Actor Model Compatibility](#10-actor-model-compatibility)
11. [Concrete Implementation Plan](#11-concrete-implementation-plan)
12. [Performance Impact Estimates](#12-performance-impact-estimates)
13. [Honest Assessment: Is This Worth It?](#13-honest-assessment)
14. [Sources](#14-sources)

---

## 1. Why N3TX Is Uniquely Positioned

Most web frameworks face a fundamental problem with pre-compilation: the rendering logic is scattered across components, configuration files, CSS frameworks, and runtime state. A compiler must understand all of these to produce correct output.

**N3TX has none of this problem.** The schema IS the specification.

```
                     Typical Framework                      N3TX
                     ================                      ======

    Rendering info    Component code                        Schema
    Layout info       CSS framework + component             Schema (ui.groups, ui.field_order)
    Widget choice     Component code                        Schema (ui.widget)
    Permission gates  Middleware + component                 Schema (access)
    Method buttons    Route config + component              Schema (methods)
    Field validation  Validators + component                Schema (minLength, pattern, etc.)
    Display modes     Responsive CSS only                   Schema + size methods (xs-xl)
```

> **Key insight:** In N3TX, `ProtoModel.schema()` (line 199 of `proto_model.py`) generates a JSON document that carries **everything the frontend needs**. No separate configuration, no component-level rendering decisions, no framework opinions. This is the compiler's input and it is **complete**.

### What the Schema Carries

From reading `proto_model.py` (lines 199-316), the schema generation process includes:

| Schema Section | Source | Lines |
|---|---|---|
| Field types & validation | Pydantic model fields | `model_json_schema()` |
| Widget hints | `json_schema_extra={'ui': {'widget': ...}}` | Field definitions |
| Layout groups | `__ui__['groups']` | Lines 283-291 |
| Field order | `__ui__['field_order']` | Lines 283-291 |
| Renderer hints | `__ui__['renderer']` | Lines 283-291 |
| Access rules | `__access__` + `access_schema()` | Lines 255-256 |
| Method signatures | `@expose_route` + `__n3tx_methods_json_signature__` | Lines 140-188 |
| Method UI hints | `__ui__['methods']` | Lines 287-291 |
| Protected fields | `__protected_fields__` | Lines 262-266 |
| Auto-hidden fields | `_apply_field_exclusion()` | Lines 25-41 |
| $defs (nested models) | Referenced model schemas | Lines 222-248 |
| Populate depth | `__ui__['populate']` | Line 48 of product.py |

---

## 2. The Complete Schema Surface Map

Below is a concrete mapping from the Product model schema to every rendering decision currently made at runtime. Each row represents a compile-time opportunity.

```
Schema Property                    Runtime Consumer              Compilable?
===================================================================================================
properties.name.type: "string"     form.js getInput() L207       YES - <input type="text">
properties.name.minLength: 1       form.js validationAttrs()     YES - minlength="1"
properties.name.maxLength: 200     form.js validationAttrs()     YES - maxlength="200"
properties.name.ui.placeholder     form.js validationAttrs()     YES - placeholder="Product name..."
properties.price.type: "number"    form.js getInput() L209       YES - <input type="number">
properties.price.ui.widget:        form.js getInput() L202-203   YES - currency div + symbol
  "currency"
properties.description.ui.widget:  form.js getInput() L200-201   YES - <textarea>
  "textarea"
properties.comments.type: "array"  form.js getListInput()        PARTIAL - structure yes, refs no
properties.favorites.type: "array" form.js getListInput()        PARTIAL - structure yes, refs no
ui.field_order                     form.js getForm() L24-29      YES - render sequence
ui.groups.main                     form.js renderGroupedFields() YES - <fieldset> structure
ui.groups.Social                   form.js renderGroupedFields() YES - <fieldset> structure
access.update: OWNER|ROLE(admin)   ntx-item.js md() L287-288     VARIANT - compile both states
access.delete: ROLE(admin)         ntx-item.js md() L287-288     VARIANT - compile both states
methods.comment                    ntx-item.js L305-317          YES - <ntx-method> element
methods.favorite                   ntx-item.js L305-317          YES - <ntx-method> element
methods.comment.ui.layout          sm() L238-249                 YES - button vs inline placement
methods.comment.ui.attach_to       renderGroupedFields()         YES - placement in fieldset
```

**Result:** Of the ~25 rendering decisions made per entity, ~18 are fully compilable, ~4 are partially compilable (structure known, data slots needed), and only ~3 require runtime (actual values, user identity, collection contents).

---

## 3. What Can Be Compiled

### 3a. Form HTML (Edit Mode)

**Current runtime path** (traced through `form.js`):

```
getForm()                          ~15 function calls per form
  -> getHeader()                   2-3 DOM string concatenations
  -> filter renderableFields       N iterations over field_order
  -> renderGroupedFields()         2 iterations over groups
     -> getInput() per field       5-8 string ops per field
        -> validationAttrs()       3-6 attr checks per field
```

For a Product with 5 rendered fields in 2 groups, this produces approximately:

| Operation | Count | Est. Time |
|---|---|---|
| Function calls | ~25 | ~0.5ms |
| String concatenations | ~60 | ~0.3ms |
| Permission checks (canView/canEdit) | ~10 | ~0.2ms |
| Schema property lookups | ~30 | ~0.1ms |
| **Total per form** | | **~1.1ms** |

**Pre-compiled output:** A single HTML string template with data-binding slots.

```html
<!-- Pre-compiled Product edit form -->
<input style="font-size: 1.5rem" type="text" id="name"
       data-key="name" data-type="string" value="{{name}}"
       minlength="1" maxlength="200" placeholder="Product name..." required>
<fieldset class="ntx-group ntx-group-main">
  <legend>main</legend>
  <label class="Product Product-form-item">Name</label>
  <input type="text" id="name" data-key="name" data-type="string"
         value="{{name}}" minlength="1" maxlength="200"
         placeholder="Product name..." required>
  <label class="Product Product-form-item">Description</label>
  <textarea id="description" data-key="description"
            data-type="string">{{description}}</textarea>
  <label class="Product Product-form-item">Price</label>
  <div class="currency-input">
    <span class="currency-symbol">$</span>
    <input type="number" step="0.01" id="price" data-key="price"
           data-type="number" value="{{price}}" min="0">
  </div>
</fieldset>
<fieldset class="ntx-group ntx-group-Social">
  <legend>Social</legend>
  <!-- Array fields: structure compiled, children are runtime -->
  <div class="list-field" data-model="Comment" data-value="comments">
    <div class="list-field-header">
      <span class="list-field-label">Comment</span>
      <span class="list-field-count">{{comments.length}}</span>
    </div>
    <!-- Child ntx-item elements injected at runtime -->
  </div>
  <ntx-method model="Product" uuid="{{id}}" method="comment"
              layout="inline" placeholder="Add your comment..."
              button-label="Post" widget="textarea" label="comment">
  </ntx-method>
</fieldset>
```

**Savings:** Eliminates ~25 function calls, ~60 string concatenations, and ~10 permission checks per form render. The template is generated once at server start and reused for every Product entity.

### 3b. Display Size Templates (xs / sm / md / lg / xl)

Each display size in `ntx-item.js` produces a known HTML structure determined entirely by schema. Traced from source:

**xs** (pill, line 143-146):
```html
<span class="pill-label" data-value="name">{{name}}</span>
```
Fully compilable. Zero runtime logic except value insertion.

**sm** (compact row, lines 156-282):
The sm() method performs ~40 lines of logic to:
1. Filter fields via `#smFields()` (lines 605-626)
2. Determine leading element (first $ref field)
3. Build name HTML
4. Build up to 3 sm-field elements
5. Build method buttons (layout='button')
6. Build action buttons (edit/delete gated by permissions)

All of this is schema-determined. The compiler can produce:

```html
<!-- Pre-compiled Product sm template (can-edit variant) -->
<span class="sm-name" data-value="name">{{name}}</span>
<span class="sm-fields">
  <span class="sm-field" data-value="price">{{price_formatted}}</span>
  <span class="sm-field" data-value="description">{{description}}</span>
</span>
<span class="sm-methods">
  <ntx-method model="Product" uuid="{{id}}" method="favorite"
              layout="button" icon="star" count-field="favorites"
              label="favorite"></ntx-method>
</span>
<span class="sm-actions">
  <button class="delete-btn" title="Delete"></button>
  <button class="edit-btn mode-display" title="Edit"></button>
</span>
```

**md/lg/xl** (card, lines 285-328):
Delegates to `Formidable.getForm()` plus method buttons. Fully compilable as described in 3a above.

### 3c. Permission-Gated UI Variants

Access rules are known at compile time. The compiler generates **variant templates**:

```
Product_sm_anon.html       (no edit/delete buttons, no method buttons)
Product_sm_auth.html       (method buttons, no edit/delete)
Product_sm_owner.html      (method buttons + edit + delete)
Product_sm_admin.html      (all buttons)
```

At runtime, the component selects the appropriate variant based on `permissions.canAction()` evaluation. This collapses the permission branching from per-render to per-attach.

### 3d. Method Button Groups

From `ntx-item.js` `#standaloneMethodsHtml()` (lines 641-657), each method produces a `<ntx-method>` element. The attributes are entirely schema-derived:

```
methods.comment -> <ntx-method model="Product" method="comment"
                    layout="inline" attach_to="comments" ...>
methods.favorite -> <ntx-method model="Product" method="favorite"
                    layout="button" icon="star" ...>
```

These are static. Compile once.

### 3e. Skeleton Placeholders

The `placeholder()` method in `ntx-item.js` (lines 44-60) returns size-specific bone HTML. These are 100% static strings today. Trivially compilable.

---

## 4. What Cannot Be Compiled

| Element | Why Runtime | Mitigation |
|---|---|---|
| **Entity values** (name, price, etc.) | Data comes from API at runtime | Template slots: `{{name}}`, `{{price}}` |
| **User identity** | JWT decoded at page load | Variant selection: pick pre-compiled variant |
| **Collection contents** | Which entities exist is dynamic | Shell structure compiled, children appended |
| **OWNER evaluation** | Requires comparing `user_owner` to current user | Compile both variants, select at render |
| **Populated child refs** | Array of href strings, dynamic | List container compiled, items appended |
| **Dynamic $ref resolution** | Child entities fetched via ATTACH flow | Child tags compiled, ref attribute set at runtime |

**Key observation:** The things that cannot be compiled are exactly the things that are currently handled by the Actor messaging system (ATTACH/DESCRIBE/UPDATE). The compiled templates produce the **shell**; the actor system fills the **data**. This is a natural boundary.

---

## 5. The Compilation Pipeline

```
                         BUILD TIME (server start)
  ===========================================================================

  Python Models                    ProtoModel.schema()
  ┌──────────┐                    ┌──────────────────────┐
  │ Product   │ ──schema()──>     │ JSON Schema          │
  │ Comment   │                   │ + properties         │
  │ User      │                   │ + ui (groups, order)  │
  │ Like      │                   │ + access (ABAC rules) │
  └──────────┘                   │ + methods             │
                                  └──────────┬───────────┘
                                             │
                                    HTML Compiler (Python)
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
            Form Templates          Size Templates           Method Templates
            ┌────────────┐       ┌──────────────┐          ┌───────────────┐
            │ Product     │       │ Product_xs    │          │ Product       │
            │  _edit.html │       │ Product_sm    │          │  _methods.html│
            │  _display   │       │ Product_md    │          │              │
            │  .html      │       │ Product_lg    │          │ Comment       │
            │             │       │ Product_xl    │          │  _methods.html│
            │ Comment     │       │ Comment_xs    │          └───────────────┘
            │  _edit.html │       │ Comment_sm    │
            │  _display   │       │ Comment_md    │
            │  .html      │       │ etc.          │
            └────────────┘       └──────────────┘

                                  Template Registry
                                  (JSON manifest)
                                  ┌──────────────────┐
                                  │ {                 │
                                  │   "Product": {    │
                                  │     "form_edit":  │
                                  │       "..html",   │
                                  │     "sm": "...",   │
                                  │     "md": "...",   │
                                  │     ...            │
                                  │   }               │
                                  │ }                 │
                                  └──────────────────┘

  ===========================================================================
                           RUNTIME (browser)

  ┌─────────────┐    fetch schema     ┌──────────────────┐
  │ <ntx-list    │ ───────────────>   │ Backend serves    │
  │  model=      │                    │ schema + template │
  │  "Product"> │                    │ registry URL      │
  └─────────────┘                    └──────────────────┘
         │
         │  DynamicClass created (prototype() still runs for                │
         │  typed properties and methods — but NO form generation)
         │
         v
  ┌─────────────┐    load template    ┌──────────────────┐
  │ ntx-item     │ ───────────────>   │ Pre-compiled      │
  │ render()     │                    │ Product_md.html   │
  └─────────────┘                    └──────────────────┘
         │
         │  Hydrate: inject entity values into {{slots}}
         │  Select variant: check permissions → pick template
         │
         v
  ┌─────────────┐
  │ Complete DOM │  (innerHTML = hydrated template)
  └─────────────┘
```

### Fitting N3TX's Buildless Philosophy

> **This is not a build step.** It is a server-start step, analogous to database migrations.

N3TX already runs `register_model()` and `register_routes()` at startup. The HTML compiler slots into the same lifecycle:

```python
# In app.py or create_app()
register_model(Product, storage=storage_backend)
register_model(Comment, storage=storage_backend)
register_routes(registered_models)
compile_templates(registered_models)   # <-- NEW: generates HTML from schemas
```

The compiler is a pure Python function. No Node.js, no npm, no Webpack, no Vite. It reads `model.schema()`, applies the same logic as `form.js` and `ntx-item.js`, and writes HTML strings to a template registry served as static files.

---

## 6. Runtime Cost Analysis: Where Time Is Spent Today

### 6a. prototype() Function (N3TX.js lines 663-1074)

Traced operations per schema:

| Step | Operations | Est. Time |
|---|---|---|
| Create DynamicClass (class extends N3TX) | 1 class creation | ~0.1ms |
| Define field properties (Object.defineProperty per field) | ~6 for Product | ~0.3ms |
| Define method wrappers | ~2 for Product | ~0.1ms |
| Set up static type-level methods (ATTACH, READ, etc.) | ~8 method assignments | ~0.2ms |
| Apply Actor.subclass + Observable mixin | 1 call | ~0.1ms |
| **Total per model** | | **~0.8ms** |

> **Verdict:** `prototype()` is fast and cannot be pre-compiled because it creates runtime class instances with live methods. This stays as-is.

### 6b. Form Generation (form.js)

Traced for a Product entity (5 renderable fields, 2 groups):

| Step | Operations | Est. Time |
|---|---|---|
| getForm() entry, field filtering | ~10 array ops | ~0.1ms |
| getHeader() | 2-3 string concats | ~0.05ms |
| renderGroupedFields() | 2 group iterations | ~0.1ms |
| getInput() x 5 fields | 5 * ~8 ops | ~0.4ms |
| validationAttrs() x 5 | 5 * ~5 checks | ~0.2ms |
| getListInput() x 2 (comments, favorites) | 2 * ~15 ops | ~0.3ms |
| Permission checks (canView, canEdit) | ~10 calls | ~0.2ms |
| renderAttachedMethod() x 2 | 2 * ~5 ops | ~0.1ms |
| **Total per form render** | | **~1.5ms** |

Multiplied across a list of 20 entities at md display:
**~30ms of pure JavaScript form generation** before any DOM insertion.

> **Verdict:** This is the **highest-value compilation target**. Form generation is the most complex runtime path, and it is entirely schema-determined. Eliminating it saves ~1.5ms per entity per render.

### 6c. ntx-item.js render() Dispatch

| Step | Operations | Est. Time |
|---|---|---|
| Size method selection | 1 property lookup | ~0.01ms |
| Size method execution (sm/md) | See 6b for md | ~1.5ms (md) / ~0.5ms (sm) |
| innerHTML assignment | 1 DOM write | ~0.3ms |
| $styles link append | 1 DOM append | ~0.05ms |
| #bindEvents() | ~5 event listener attachments | ~0.2ms |
| **Total per entity render** | | **~2.0ms (md)** |

For a list of 20 md cards: **~40ms of rendering time**.

> **Verdict:** The rendering itself is moderately expensive. Pre-compiled templates would reduce the size-method execution from ~1.5ms to ~0.1ms (template string lookup + slot interpolation), saving ~70% of per-entity render time.

### 6d. DOM Operation Costs

Based on benchmarks from [MeasureThat.net](https://www.measurethat.net/Benchmarks/Show/5430/0/different-ways-template-vanilla-js-innerhtml-to-create):

| Method | Relative Speed |
|---|---|
| `innerHTML` (string) | Baseline (1x) |
| `createElement` + `setAttribute` | ~0.5x - 0.8x slower |
| `template.cloneNode(true)` | ~1.5x - 2x faster |
| Pre-built string via `innerHTML` | ~1.2x - 1.5x faster (no string building) |

N3TX currently uses `innerHTML` with runtime-built strings. Pre-compiled templates skip the string-building step entirely, giving the `innerHTML` assignment a pre-formed string. The `<template>` + `cloneNode` path could be even faster but requires attribute patching instead of slot interpolation.

---

## 7. Hydration Strategy: Shells + Data Injection

The compiler produces **template shells** with named slots. At runtime, the component:

1. Selects the appropriate template (model + size + permission variant)
2. Interpolates entity values into slots
3. Assigns to `shadowRoot.innerHTML`
4. Binds events (unchanged from current `#bindEvents()`)

### Template Slot Syntax

```html
<!-- Product_md_owner.html -->
<div class="card-actions">
  <button class="delete-btn" title="Delete"></button>
  <button class="edit-btn mode-display" title="Edit"></button>
</div>
<img class="card-image" src="{{image}}" alt="{{name}}" />
<h2 class="Product" data-value="name">{{name}}</h2>
<h4 data-value="description">{{description}}</h4>
<fieldset class="ntx-group ntx-group-main">
  <legend>main</legend>
  <label class="Product Product-form-item">Name</label>
  <div data-value="name">{{name}}</div>
  <label class="Product Product-form-item">Description</label>
  <div class="text-block" data-value="description">{{description}}</div>
  <label class="Product Product-form-item">Price</label>
  <div class="currency-display" data-value="price">{{price_currency}}</div>
</fieldset>
<fieldset class="ntx-group ntx-group-Social">
  <legend>Social</legend>
  <div class="list-field" data-model="Comment" data-value="comments">
    <div class="list-field-header">
      <span class="list-field-label">Comment</span>
      <span class="list-field-count">{{comments_count}}</span>
    </div>
    {{comments_children}}
  </div>
  <ntx-method model="Product" uuid="{{id}}" method="comment"
              layout="inline" attach_to="comments"
              placeholder="Add your comment..." button-label="Post"
              widget="textarea" label="comment"></ntx-method>
  <div class="list-field" data-model="Like" data-value="favorites">
    <div class="list-field-header">
      <span class="list-field-label">Like</span>
      <span class="list-field-count">{{favorites_count}}</span>
    </div>
    {{favorites_children}}
  </div>
  <ntx-method model="Product" uuid="{{id}}" method="favorite"
              layout="button" icon="star" count-field="favorites"
              attach_to="favorites" label="favorite"></ntx-method>
</fieldset>
```

### Hydration Function

```javascript
// Runtime hydration — replaces form.js for pre-compiled models
function hydrate(template, entity, schema) {
    let html = template;
    const props = schema.properties || {};

    for (const [key, def] of Object.entries(props)) {
        const val = entity[key] ?? '';
        // Type-aware formatting
        if (def.ui?.widget === 'currency' && typeof val === 'number') {
            html = html.replace(`{{${key}_currency}}`, `$${val.toFixed(2)}`);
        }
        html = html.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), escapeHtml(String(val)));

        // Array fields: count + children
        if (def.type === 'array' && Array.isArray(val)) {
            html = html.replace(`{{${key}_count}}`, String(val.length));
            const childHtml = val.slice(0, 2).map(ref =>
                `<ntx-item ref="${ref}" display="sm"></ntx-item>`
            ).join('');
            html = html.replace(`{{${key}_children}}`, childHtml);
        }
    }

    // Instance-specific slots
    html = html.replace(/\{\{id\}\}/g, String(entity.id || ''));
    return html;
}
```

The hydration function is **dramatically simpler** than the current form generation path. It is a series of string replacements on a pre-formed template, versus the current 25+ function calls with branching logic.

---

## 8. Islands Architecture for N3TX

N3TX's component model naturally maps to [Islands Architecture](https://docs.astro.build/en/concepts/islands/):

```
  ┌──────────────────────────────────────────────────────────┐
  │                   Static HTML Shell                       │
  │                                                          │
  │  ┌─────────────────────────────────────────────────┐     │
  │  │  Pre-compiled list header + grid container       │     │
  │  │  (static from schema: model name, layout CSS)    │     │
  │  │                                                  │     │
  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │     │
  │  │  │ ISLAND   │  │ ISLAND   │  │ ISLAND   │      │     │
  │  │  │ ntx-item │  │ ntx-item │  │ ntx-item │      │     │
  │  │  │          │  │          │  │          │      │     │
  │  │  │ Dynamic: │  │ Dynamic: │  │ Dynamic: │      │     │
  │  │  │ - values │  │ - values │  │ - values │      │     │
  │  │  │ - events │  │ - events │  │ - events │      │     │
  │  │  │ - perms  │  │ - perms  │  │ - perms  │      │     │
  │  │  └──────────┘  └──────────┘  └──────────┘      │     │
  │  │                                                  │     │
  │  │  ┌──────────────────────────────────────────┐   │     │
  │  │  │ ISLAND: Load More button (if has_more)    │   │     │
  │  │  └──────────────────────────────────────────┘   │     │
  │  └─────────────────────────────────────────────────┘     │
  │                                                          │
  │  ┌─────────────────────────────────────────────────┐     │
  │  │  Static: schema inspector, auth panel, etc.      │     │
  │  └─────────────────────────────────────────────────┘     │
  └──────────────────────────────────────────────────────────┘
```

### Island Boundaries in N3TX

| Layer | Static / Dynamic | Compilation? |
|---|---|---|
| Page layout (schema.html) | Static | Already static HTML |
| List shell (header, grid container) | Static from schema | Compilable |
| Item card structure (labels, fieldsets, groups) | Static from schema | Compilable |
| Item data values | Dynamic (API data) | Runtime hydration |
| Method buttons (structure) | Static from schema | Compilable |
| Method button state (count badges) | Dynamic (entity values) | Runtime hydration |
| Edit/delete button visibility | Dynamic (user permissions) | Variant selection |
| Event handlers (click, input) | Dynamic | Runtime binding |

The natural split: **compile the structure, hydrate the data, bind the events**.

This mirrors Astro's approach where "the majority of your website is converted to fast, static HTML and JavaScript is only loaded for the individual components that need it" [(Astro docs)](https://docs.astro.build/en/concepts/islands/). The difference is that N3TX's "build" happens at server start, not in a CI pipeline.

---

## 9. Declarative Shadow DOM

[Declarative Shadow DOM (DSD)](https://developer.mozilla.org/en-US/docs/Web/API/Web_components/Using_shadow_DOM) enables server-rendered shadow roots without JavaScript:

```html
<ntx-item>
  <template shadowrootmode="open">
    <link rel="stylesheet" href="/static/components/ntx-item.css">
    <div class="card" data-display="md">
      <h2 class="Product" data-value="name">Widget Pro</h2>
      <!-- ... pre-rendered content ... -->
    </div>
  </template>
</ntx-item>
```

### DSD Applicability to N3TX

| Factor | Assessment |
|---|---|
| Browser support | Chrome 90+, Edge (Chromium), Firefox 124+, Safari 16.4+ |
| Benefit for initial render | High -- content visible before JS loads |
| Benefit for subsequent renders | None -- JS takes over for reactivity |
| Compatibility with current Component.js | **Requires changes** -- `attachShadow()` in constructor would conflict with DSD |
| SSR page generation | Possible via Python template engine |
| Complexity cost | Moderate -- need to handle both DSD-first and JS-first paths |

> **Verdict:** DSD is valuable for **initial page load** (First Contentful Paint) but does not help with subsequent renders (UPDATE/DESCRIBE cycle). It is a complementary optimization, not a replacement for the template compiler.

### DSD Integration Path

```python
# Server-side: generate full page with DSD pre-rendered entities
def render_page(models, initial_data):
    html = '<!DOCTYPE html><html>...'
    for entity in initial_data:
        schema = entity.__class__.schema()
        template = get_compiled_template(schema, 'md', 'anon')
        hydrated = hydrate(template, entity.model_dump(response=True))
        html += f'''
        <ntx-item>
          <template shadowrootmode="open">
            <link rel="stylesheet" href="/static/components/ntx-item.css">
            <div class="card" data-display="md">{hydrated}</div>
          </template>
        </ntx-item>'''
    html += '</html>'
    return html
```

This would give N3TX **instant rendering** on first page load, before any JavaScript executes. The Actor system then takes over for interactivity.

**Important:** N3TX already has pre-loading infrastructure. N3TX.js lines 244-277 implement `#consumePreloadedSchema()` and `#consumePreloadedData()` which consume inline `<script data-ntx-schema>` and `<script data-ntx-data>` tags. The DSD approach extends this pattern from data pre-loading to DOM pre-rendering.

---

## 10. Actor Model Compatibility

The key question: **do pre-compiled templates break the Matrix/Actor messaging flow?**

### Current Flow

```
Component.connectedCallback()
  -> attributeChangedCallback('model', ...)
    -> send TX(ATTACH, target='N3TX')
      -> N3TX.ATTACH()
        -> fetch schema (or consume pre-loaded)
          -> N3TX.SCHEMA()
            -> prototype() creates DynamicClass
            -> DynamicClass.READ() fetches data
              -> DynamicClass notifies watchers
                -> Component.DESCRIBE({proto, data})
                  -> NTTElement.render()
                    -> size method (sm/md/lg)
                      -> form.js getForm()       <-- THIS IS WHAT WE REPLACE
                        -> innerHTML assignment
```

### With Pre-compiled Templates

```
Component.connectedCallback()
  -> attributeChangedCallback('model', ...)
    -> send TX(ATTACH, target='N3TX')
      -> N3TX.ATTACH()
        -> fetch schema (or consume pre-loaded)
          -> N3TX.SCHEMA()
            -> prototype() creates DynamicClass  (UNCHANGED)
            -> DynamicClass.READ() fetches data  (UNCHANGED)
              -> DynamicClass notifies watchers   (UNCHANGED)
                -> Component.DESCRIBE({proto, data})
                  -> NTTElement.render()
                    -> size method (sm/md/lg)
                      -> templateRegistry.get(model, size, permVariant)  <-- NEW
                        -> hydrate(template, data)                       <-- NEW
                          -> innerHTML assignment   (UNCHANGED)
```

**Only two function calls change.** The Actor messaging, DynamicClass creation, data fetching, and event binding are completely unaffected. The compiler replaces only the **template generation** step inside `render()`.

### Surgical Update Compatibility

`ntx-item.js` already implements surgical DOM updates via the `update()` method (lines 336-373). This method patches individual `[data-value]` and `[data-key]` elements by key. Pre-compiled templates use the same `data-value` and `data-key` attributes, so **surgical updates work unchanged**.

---

## 11. Concrete Implementation Plan

### Phase 1: Python-Side Template Compiler

**File:** `src/n3tx/core/compiler/templates.py`

```python
"""
HTML Template Compiler for N3TX.

Reads model schemas and generates pre-compiled HTML templates
for each model x display-size x permission-variant combination.

Runs at server start, alongside register_routes() and migrations.
No npm. No Node. No build step.
"""

from typing import Dict, Type
from n3tx.core.utils.registrar import registered_models


def compile_templates(models: dict = None) -> dict:
    """Generate all templates for all registered models.

    Returns a registry dict:
    {
        'Product': {
            'xs': '<span class="pill-label" ...>{{name}}</span>',
            'sm_anon': '...',
            'sm_auth': '...',
            'sm_owner': '...',
            'md_edit': '...',
            'md_display_anon': '...',
            'md_display_auth': '...',
            'md_display_owner': '...',
            'skeleton_xs': '...',
            'skeleton_sm': '...',
            'skeleton_md': '...',
            'methods_standalone': '...',
            'methods_attached': { 'comments': '...', 'favorites': '...' },
        },
        'Comment': { ... },
    }
    """
    models = models or registered_models
    registry = {}
    for name, model_cls in models.items():
        schema = model_cls.schema()
        registry[name] = compile_model_templates(schema)
    return registry


def compile_model_templates(schema: dict) -> dict:
    """Compile all template variants for a single model."""
    templates = {}

    # xs: always the same, no permission variants
    templates['xs'] = compile_xs(schema)

    # Skeletons per size
    for size in ['xs', 'sm', 'md']:
        templates[f'skeleton_{size}'] = compile_skeleton(size)

    # sm/md/lg: permission variants
    for size in ['sm', 'md', 'lg', 'xl']:
        for variant in ['anon', 'auth', 'owner', 'admin']:
            templates[f'{size}_display_{variant}'] = compile_display(
                schema, size, variant)
        templates[f'{size}_edit'] = compile_edit_form(schema, size)

    # Methods
    templates['methods_standalone'] = compile_standalone_methods(schema)
    templates['methods_attached'] = compile_attached_methods(schema)

    return templates


def compile_display(schema: dict, size: str, variant: str) -> str:
    """Generate display template for a given size and permission variant."""
    ...

def compile_edit_form(schema: dict, size: str) -> str:
    """Generate edit form template."""
    ...

def compile_xs(schema: dict) -> str:
    """Generate xs pill template."""
    return '<span class="pill-label" data-value="name">{{name}}</span>'

def compile_skeleton(size: str) -> str:
    """Generate skeleton placeholder per size."""
    ...

def compile_standalone_methods(schema: dict) -> str:
    """Generate standalone method button HTML."""
    ...

def compile_attached_methods(schema: dict) -> dict:
    """Generate attached method HTML keyed by attach_to field."""
    ...
```

### Phase 2: Template Registry Endpoint

```python
# In routes_fastapi.py
@router.get("/templates/{model_name}")
async def get_templates(model_name: str):
    """Serve pre-compiled templates for a model."""
    registry = get_template_registry()
    if model_name not in registry:
        raise HTTPException(404, f"No templates for {model_name}")
    return registry[model_name]
```

### Phase 3: Frontend Template Consumer

```javascript
// In N3TX.js — extend SCHEMA handler
static SCHEMA(data, tx) {
    // ... existing DynamicClass creation ...

    // Fetch pre-compiled templates
    fetch(`${config.API_URL}/templates/${addr}`)
        .then(r => r.json())
        .then(templates => {
            DC._templates = templates;
        });
}
```

```javascript
// In ntx-item.js — template-aware render
render() {
    if (!this.schema || !this.value) return;
    const size = this.displayMode;
    const DC = N3TX.get(this.schema.__name__);

    if (DC?._templates) {
        // Pre-compiled path
        const variant = this.#resolveVariant();
        const key = this.mode === 'edit'
            ? `${size}_edit`
            : `${size}_display_${variant}`;
        const template = DC._templates[key];
        if (template) {
            const html = this.#hydrate(template);
            this.shadowRoot.innerHTML =
                `<div class="card" data-display="${size}">${html}</div>`;
            if (this.$styles) this.shadowRoot.appendChild(this.$styles);
            this._rendered = true;
            this.#bindEvents();
            return;
        }
    }

    // Fallback: runtime generation (existing path)
    const html = (this[size] || this.md).call(this);
    this.shadowRoot.innerHTML =
        `<div class="card" data-display="${size}">${html}</div>`;
    if (this.$styles) this.shadowRoot.appendChild(this.$styles);
    this._rendered = true;
    this.#bindEvents();
}
```

### Phase 4: Startup Integration

```python
# In app.py create_app()
def create_app(models, storage, compile=True, **kwargs):
    # ... existing setup ...
    register_routes(registered_models)

    if compile:
        from n3tx.core.compiler.templates import compile_templates
        compile_templates(registered_models)
        logger.info("HTML templates compiled for %d models", len(registered_models))

    return app
```

---

## 12. Performance Impact Estimates

### Before vs. After: 20 Product Cards (md display)

| Metric | Current (Runtime) | Compiled (Templates) | Savings |
|---|---|---|---|
| Form generation per entity | ~1.5ms | ~0ms (pre-compiled) | -1.5ms |
| Template hydration per entity | N/A | ~0.2ms (string replace) | +0.2ms |
| Permission evaluation per entity | ~0.2ms | ~0.05ms (variant select) | -0.15ms |
| innerHTML assignment per entity | ~0.3ms | ~0.3ms (unchanged) | 0ms |
| Event binding per entity | ~0.2ms | ~0.2ms (unchanged) | 0ms |
| **Per-entity total** | **~2.2ms** | **~0.75ms** | **-66%** |
| **20-entity list total** | **~44ms** | **~15ms** | **-29ms** |

### Additional First-Load Savings

| Metric | Current | With DSD | Savings |
|---|---|---|---|
| Time to First Contentful Paint | ~800ms (JS parse + schema fetch + render) | ~200ms (pre-rendered HTML) | -600ms |
| JavaScript parsed before first pixel | ~150KB | ~150KB (but not blocking) | FCP improvement |
| Schema network round-trip | ~50ms | 0ms (inline `<script data-ntx-schema>`) | -50ms |

### Memory Impact

Pre-compiled templates are cached once per model (not per instance). For 5 models with ~10 template variants each:

```
5 models x 10 variants x ~2KB average = ~100KB total template cache
```

Negligible compared to the current per-render string allocations, which generate and discard ~2KB of HTML per entity per render cycle.

### Where This Does NOT Help

| Scenario | Why No Improvement |
|---|---|
| `prototype()` class creation | Cannot be pre-compiled (runtime class semantics) |
| Network fetches (READ/UPDATE) | I/O bound, not CPU bound |
| Actor message dispatch | Already fast (~0.01ms per message) |
| ResizeObserver callbacks | Fires rarely, negligible cost |
| `update()` surgical patches | Already optimized, uses data-value selectors |

---

## 13. Honest Assessment: Is This Worth It?

### When It IS Worth It

**YES** for applications with:
- Large entity lists (50+ items rendered simultaneously)
- Complex schemas (many fields, nested groups, multiple methods)
- Low-powered devices (mobile, embedded browsers)
- First-load performance requirements (SEO, Core Web Vitals)
- Server-side rendering needs (DSD for pre-rendered pages)

### When It Is NOT Worth It

**NO** for applications with:
- Small entity counts (< 10 per page)
- Simple schemas (3-4 fields, no groups)
- Desktop-only deployment with fast hardware
- Rapidly changing schemas during development

### The Numbers

For a typical N3TX page (20 md cards):
- **Current:** ~44ms rendering time after data arrives
- **Compiled:** ~15ms rendering time after data arrives
- **Saving:** ~29ms per render cycle

Is 29ms perceptible? **Barely.** The 60fps threshold is 16.7ms per frame. A 44ms render blocks for ~2.6 frames; a 15ms render fits within one frame. So the improvement IS visible as smoother list loading, but it is not the difference between "slow" and "fast."

### Simpler Wins First

Before building a compiler, there are lower-cost optimizations:

| Optimization | Effort | Impact |
|---|---|---|
| **Template caching in form.js** | Low (add Map cache keyed by model+mode) | Eliminates re-generation for same schema |
| **DocumentFragment batching** | Already done in ListElement.render() | N/A |
| **`<template>` + `cloneNode`** | Medium (create template once, clone per entity) | ~1.5x faster than innerHTML |
| **Lazy rendering** (IntersectionObserver) | Medium | Only render visible items |
| **Virtual scrolling** for large lists | High | Massive win for 100+ items |
| **Web Worker for hydration** | High | Moves string ops off main thread |

> **Recommendation:** Implement template caching in `form.js` first (a 20-line change). If performance is still insufficient for your use case, proceed with the full compiler. The compiler is architecturally sound and N3TX's schema completeness makes it uniquely feasible -- the question is whether you need it yet.

### The Strategic Argument

Beyond raw performance, the compiler provides:

1. **Server-Side Rendering capability** -- pre-rendered pages for SEO and instant load
2. **Offline-first** -- templates can be cached in ServiceWorker, only data needs network
3. **Testing** -- compiled templates are static strings that can be snapshot-tested
4. **Predictability** -- rendering behavior is frozen at compile time, not dependent on runtime JS
5. **Deployment validation** -- schema changes produce new templates; if the template compiles, the UI works

These strategic benefits may justify the compiler even if the raw performance gain is modest.

---

## Appendix A: Comparison Matrix

| Approach | Build Tool? | Runtime Cost | First Paint | SSR? | Complexity |
|---|---|---|---|---|---|
| **Current (runtime form.js)** | None | ~2.2ms/entity | JS-blocked | No | Low |
| **Template cache (form.js Map)** | None | ~0.5ms first, ~0.1ms cached | JS-blocked | No | Very Low |
| **Python compiler (this proposal)** | Python at startup | ~0.75ms/entity | JS-blocked | Possible | Medium |
| **Python compiler + DSD** | Python at startup | ~0.75ms/entity | Instant | Yes | Medium-High |
| **Full SSG (e.g., Astro)** | Node.js build | ~0ms (static) | Instant | Yes | High |

---

## Appendix B: Schema-to-Template Decision Tree

```
                        Schema Property
                              |
                    +---------+---------+
                    |                   |
              type: "string"      type: "array"
                    |                   |
            +-------+-------+     +----+----+
            |               |     |         |
      ui.widget?     no widget    items.$ref?
            |               |     |         |
    +-------+------+   <input     |     <div>
    |              |    type=     model    array
  "currency"  "textarea" "text"> resolved  items
    |              |              |
 <div class=   <textarea>   <div class=
  "currency-     ...</>      "list-field"
   input">                   data-model=
  <span>$</span>             "{model}">
  <input type=                 ...
   "number"                  </div>
   step="0.01">
 </div>

                    +----------+
                    |          |
              access rules  methods
                    |          |
              compile N      compile
              variants:      <ntx-method>
              anon/auth/     elements
              owner/admin    per method
```

---

## Appendix C: Files to Create/Modify

### New Files

| File | Purpose |
|---|---|
| `src/n3tx/core/compiler/__init__.py` | Package init |
| `src/n3tx/core/compiler/templates.py` | Main compiler: schema -> HTML templates |
| `src/n3tx/core/compiler/form_compiler.py` | Port of form.js logic to Python |
| `src/n3tx/core/compiler/size_compiler.py` | Port of xs/sm/md/lg/xl layout logic |
| `src/n3tx/core/compiler/method_compiler.py` | Method button generation |
| `src/n3tx/core/compiler/registry.py` | Template storage and serving |

### Modified Files

| File | Change |
|---|---|
| `src/n3tx/core/app.py` | Add `compile_templates()` to startup |
| `src/n3tx/core/api/routes_fastapi.py` | Add `/templates/{model}` endpoint |
| `src/n3tx/static/components/ntx-item.js` | Add template-aware `render()` path |
| `src/n3tx/static/core/N3TX.js` | Fetch templates on SCHEMA completion |
| `src/n3tx/__init__.py` | Export `compile_templates` |

### Estimated Implementation Effort

| Phase | Lines of Code | Time Estimate |
|---|---|---|
| Phase 1: Python compiler | ~400 LOC | 2-3 days |
| Phase 2: Template registry endpoint | ~50 LOC | 0.5 days |
| Phase 3: Frontend consumer | ~100 LOC | 1 day |
| Phase 4: Startup integration | ~20 LOC | 0.5 days |
| Tests | ~200 LOC | 1-2 days |
| **Total** | **~770 LOC** | **5-7 days** |

---

## 14. Sources

- [Declarative Shadow DOM -- HackerNoon](https://hackernoon.com/declarative-shadow-dom-the-magic-pill-for-server-side-rendering-and-web-components) -- DSD overview and SSR integration patterns
- [MDN: Using Shadow DOM](https://developer.mozilla.org/en-US/docs/Web/API/Web_components/Using_shadow_DOM) -- Reference documentation for Shadow DOM and Declarative Shadow DOM
- [Web Components 2025: Shadow DOM, Lit 4.0, and Browser Compatibility](https://markaicode.com/web-components-2025-shadow-dom-lit-browser-compatibility/) -- Current state of Web Components ecosystem
- [Declarative Shadow DOMs: Bridging the Gap Between Components and Performance](https://calendar.perfplanet.com/2023/declarative-shadow-doms-bridging-the-gap-between-components-and-performance/) -- Performance analysis of DSD approach
- [Astro Islands Architecture](https://docs.astro.build/en/concepts/islands/) -- Islands architecture reference, 83% JS reduction claim
- [Islands Architecture -- patterns.dev](https://www.patterns.dev/vanilla/islands-architecture/) -- Pattern documentation and performance rationale
- [Server Components vs. Islands Architecture](https://blog.logrocket.com/server-components-vs-islands-architecture) -- Comparative performance analysis
- [DOM Benchmark: createElement vs innerHTML vs template](https://www.measurethat.net/Benchmarks/Show/5430/0/different-ways-template-vanilla-js-innerhtml-to-create) -- DOM operation performance data
- [createElement vs cloneNode vs innerHTML](https://www.measurethat.net/Benchmarks/Show/10096/0/createelement-vs-clonenode-vs-innerhtml) -- Additional DOM benchmarks
- [Stencil: SSR with Web Components](https://ionic.io/blog/the-quest-for-ssr-with-web-components-a-stencil-developers-journey) -- Practical SSR challenges with Web Components
- [Building Templates for Custom Elements](https://nathanherald.com/posts/building-templates/) -- Template patterns for custom elements
- [Precompiled Templates Performance](https://github.com/webpro/precompiled-templates) -- Benchmark data for template pre-compilation
- [Custom Elements are NOT for Templating -- INNOQ](https://www.innoq.com/en/blog/2023/01/custom-elements-not-for-templating/) -- Counterpoint: limitations of template-based custom elements
- [SimpleWC: JSON-driven Web Components](https://dev.to/btopro/simplewc-json-driven-web-components-1jd8) -- Precedent for JSON-driven component generation
- [json-schema-forms: JSON Schema to HTML](https://github.com/hblanko/json-schema-forms) -- Existing library for schema-to-form generation
- [WICG Declarative Shadow DOM Proposal](https://github.com/WICG/webcomponents/blob/gh-pages/proposals/Declarative-Shadow-DOM.md) -- W3C community group specification
- [DSD and the Future of Drupal Theming](https://john.albin.net/presentations/2025-09-25/declarative-shadow-dom-and-future-drupal-theming) -- DSD adoption in established CMS platforms

---

*Research compiled February 2026. Source analysis based on N3TX codebase at commit `7550aeb` (profiling branch).*
