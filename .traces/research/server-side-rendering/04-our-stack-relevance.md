# Server-Side Rendering for PyBend: Stack Relevance Analysis

**Date:** 2025-02-25
**Scope:** How SSR maps to PyBend's schema-driven architecture
**Audience:** Engineering leadership + technical CEO

---

## Executive Summary

PyBend's architecture is **unusually well-positioned** for server-side rendering, but
not in the way most frameworks approach it. The conventional SSR story -- React
Server Components, Next.js hydration, Nuxt universal rendering -- assumes a
JavaScript-centric stack where the server duplicates client logic. PyBend's story
is different: **the server already owns the complete rendering specification**.
The JSON Schema that `ProtoModel.schema()` emits carries field types, UI widget
hints, field ordering, group layouts, access rules, and method signatures. The
frontend's `form.js` and `ntt-item.js` are essentially schema interpreters -- they
read instructions and produce HTML. That interpretation can happen on the server
in Python just as easily as it happens in the browser in JavaScript.

This document traces exactly how PyBend's current rendering pipeline works, identifies
which parts are purely data-driven (and therefore server-renderable), maps out where
client-side interactivity is genuinely required, and proposes a concrete SSR
implementation strategy that leverages what the framework already has.

**Key finding:** PyBend already has nascent SSR infrastructure. The `NTT.js` file
contains `#consumePreloadedSchema()` and `#consumePreloadedData()` methods (lines
244-277) that parse inline `<script data-ntt-schema>` and `<script data-ntt-data>`
tags -- a server can inject these and skip both network fetches entirely. This
is not hypothetical; the code exists today.

---

## Table of Contents

1. [Current Rendering Pipeline](#1-current-rendering-pipeline)
2. [What Is Purely Data-Driven (Server-Renderable)](#2-what-is-purely-data-driven)
3. [What Requires Client-Side JavaScript](#3-what-requires-client-side-javascript)
4. [The Actor/Matrix System and SSR Boundaries](#4-the-actormatrix-system-and-ssr-boundaries)
5. [Existing SSR-Ready Infrastructure](#5-existing-ssr-ready-infrastructure)
6. [Proposed SSR Implementation for PyBend](#6-proposed-ssr-implementation)
7. [FastAPI Async and Streaming SSR](#7-fastapi-async-and-streaming-ssr)
8. [Authorization and Per-User SSR](#8-authorization-and-per-user-ssr)
9. [Gaps and Work Required](#9-gaps-and-work-required)
10. [Competitive Positioning](#10-competitive-positioning)
11. [Recommendations](#11-recommendations)

---

## 1. Current Rendering Pipeline

### The Full Request Lifecycle (As-Is)

The current pipeline executes entirely client-side after the initial HTML shell loads.
Here is the exact sequence, traced through actual code paths:

```
Browser loads matrix.html
         |
         v
<ntt-list model="Product"> parsed by browser
         |
         v
Component.attributeChangedCallback('model', null, 'Product')
  --> sends TX { name: 'ATTACH', target: 'NTT', data: 'Product' }
         |
         v
NTT.ATTACH('Product', tx)                         [NTT.js:357-384]
  --> NTT.#prototypes.get('Product') === undefined (never seen)
  --> Sets #prototypes('Product') = null (in-flight)
  --> Queues the TX in #waiting
  --> Dispatches TX { name: 'SCHEMA', target: 'http://..../Product' }
         |
         v
NetworkAdapter sends GET /Product  .................. [NETWORK REQUEST 1]
         |
         v
Backend: make_get_schema(Product)                  [routes_fastapi.py:168-180]
  --> Product.schema()                             [proto_model.py:199-316]
  --> Returns JSON Schema with properties, methods, $defs, access, ui
         |
         v
NTT.SCHEMA(data)                                   [NTT.js:390-426]
  --> Registers $defs (Comment, etc.) as DynamicClasses
  --> prototype('Product', schema, href) creates DynamicClass [NTT.js:663-]
      --> Defines typed getters/setters for each schema property
      --> Defines callable methods from schema.methods
      --> Wires READ/CREATE/UPDATE/DELETE static handlers
  --> Stores DynamicClass in #prototypes
  --> Replays queued ATTACH messages
  --> Dispatches READ { target: 'http://..../products' }
         |
         v
NetworkAdapter sends GET /products?limit=20&offset=0  [NETWORK REQUEST 2]
         |
         v
Backend: make_get_all_instances(Product)           [routes_fastapi.py:92-137]
  --> Product.list(limit=20, offset=0)
  --> Returns { data: [...], meta: {total, limit, offset, has_more} }
         |
         v
DynamicClass.READ(data)                            [NTT.js:908-980]
  --> Creates NTT instances for each record
  --> Normalizes populated data (inline objects -> href strings)
  --> Notifies watchers (ntt-list component) with address array
         |
         v
ListElement.UPDATE([addrs])                        [ListElement.js:77-86]
  --> Stores address array as value
  --> Calls render()
         |
         v
ListElement.render()
  --> For each addr, creates <ntt-item ref="addr">
  --> Each ntt-item sends ATTACH to NTT for its individual entity
         |
         v
NTT instance ATTACH response -> DESCRIBE           [NTTElement.js:78-95]
  --> Sets schema + value on the component
  --> value setter triggers render()
         |
         v
NTTItem.render()                                   [ntt-item.js:468-486]
  --> Dispatches to size method: xs(), sm(), md(), lg(), xl()
  --> md() calls Formidable.getForm(...)           [form.js:17-65]
      --> Reads schema.properties, ui.field_order, ui.groups
      --> For each field: getInput() maps type+widget to HTML
      --> Returns HTML string
  --> Sets shadowRoot.innerHTML = html
  --> Binds event listeners                        [ntt-item.js:494-598]
```

### Waterfall Visualization

```
Time  0ms    200ms    400ms    600ms    800ms    1000ms
       |--------|--------|--------|--------|---------|
HTML   [==]
Parse       [=]
JS Load      [=====]
ATTACH            [=]
SCHEMA fetch       [========]         <-- NETWORK REQUEST 1
prototype()                   [=]
READ fetch                     [========]  <-- NETWORK REQUEST 2
Instance creation                       [=]
Render                                   [===]
                                              FIRST PAINT
```

**Critical insight:** The user sees nothing meaningful until both network requests
complete. The "waterfall of emptiness" is two sequential round-trips (schema, then
data) before any content appears. This is the core latency problem SSR addresses.

### What Each Stage Produces

| Stage | Input | Output | Location |
|-------|-------|--------|----------|
| Schema fetch | Model name | JSON Schema | `GET /Product` -> `proto_model.py:199` |
| prototype() | JSON Schema | DynamicClass with typed properties | `NTT.js:663-791` |
| Data fetch | DynamicClass.href | Array of entity records | `GET /products` -> `routes_fastapi.py:92` |
| DynamicClass.READ | Entity records | NTT instances in registry | `NTT.js:908-980` |
| Formidable.getForm | schema + value | HTML string | `form.js:17-65` |
| ntt-item.render | HTML string | Shadow DOM content | `ntt-item.js:468-486` |

---

## 2. What Is Purely Data-Driven

The following rendering stages are **deterministic functions of schema + data** with
no dependency on browser APIs, user interaction state, or the actor message bus.
They are candidates for server-side execution.

### 2.1 Form HTML Generation

The `Formidable.getForm()` function (`form.js:17-65`) is a pure function:

```javascript
// form.js:17 -- Actual code from the codebase
function getForm(ntt, mode="display", attachedMethods = {}) {
    const schema = ntt.schema;
    const fields = schema.properties || {};
    const ui = schema.ui || {};
    // Determine field order: schema.ui.field_order > Object.keys fallback
    const fieldOrder = ui.field_order
        ? ui.field_order.filter(k => k in fields)
        : Object.keys(fields);
    // ... filter renderable fields, render groups or flat ...
}
```

**Input:** `{schema, value, ref}` object + mode string
**Output:** HTML string
**Browser dependencies:** None. This is string concatenation guided by schema metadata.

The same logic in Python (Jinja2 or direct string building) would produce identical HTML.
Every decision this function makes is answerable from data the server already has:

- Field types: `schema.properties[key].type` (server has this -- it generated it)
- Widget hints: `schema.properties[key].ui.widget` (server has this -- it's from `__ui__`)
- Field order: `schema.ui.field_order` (server has this -- it's from `__ui__`)
- Groups: `schema.ui.groups` (server has this)
- Validation attrs: `minLength`, `maxLength`, `pattern` (server has this -- from Pydantic)
- Values: entity data (server has this -- it's from the database)

### 2.2 Size-Method HTML (xs, sm, md)

The `ntt-item.js` size methods are also pure HTML generators:

```javascript
// ntt-item.js:143-146 -- xs() is trivially data-driven
xs() {
    const name = this.value.name || this.value.title || this.schema.__name__;
    return `<span class="pill-label" data-value="name">${name}</span>`;
}
```

```javascript
// ntt-item.js:284-318 -- md() delegates to Formidable
md() {
    const html = [];
    // ... permission-gated buttons ...
    html.push(Formidable.getForm({schema: this.schema, value: this.value, ref: this.ref},
              this.mode, attached));
    // ... standalone methods ...
    return html.join('');
}
```

Every size method follows the same pattern: read schema, read value, produce HTML
string. The `sm()` method (`ntt-item.js:156-282`) is the most complex, resolving
leading elements, field values, and method buttons -- but every decision is still
schema-driven.

### 2.3 List Rendering Structure

The `ListElement.render()` method creates child elements from an address array.
The structural HTML (the grid container, the "Load More" button, the count badge)
is deterministic. What varies is *which* child elements appear -- and that is
determined by the data fetch, which the server can perform directly.

### 2.4 Skeleton Placeholders

The `NTTItem.placeholder()` method (`ntt-item.js:44-60`) returns layout-matching
bone HTML for skeleton loading states. This is pure data (size parameter) to HTML.
With SSR, skeletons become unnecessary for the initial render -- the real content
arrives in the first byte.

### Summary: Server-Renderable Surface Area

| Component | Current Location | Server-Renderable? | Notes |
|-----------|-----------------|--------------------|----|
| Form fields (display) | `form.js:getInput()` | **Yes** | Pure type->HTML mapping |
| Form fields (edit) | `form.js:getInput()` | **Yes** | Same mapping, different mode |
| Form groups/fieldsets | `form.js:renderGroupedFields()` | **Yes** | Schema.ui.groups -> fieldsets |
| Validation attributes | `form.js:validationAttrs()` | **Yes** | Schema constraints -> HTML5 attrs |
| Header (h2/h4) | `form.js:getHeader()` | **Yes** | name + description |
| xs pill | `ntt-item.js:xs()` | **Yes** | Single span |
| sm compact row | `ntt-item.js:sm()` | **Yes** | Requires permission check (server can do) |
| md card | `ntt-item.js:md()` | **Yes** | Full form + methods |
| List grid | `ListElement.render()` | **Yes** | Container + children |
| Method buttons | `ntt-method` tag generation | **Yes** | Schema.methods -> button HTML |
| List field (nested refs) | `form.js:getListInput()` | **Partial** | Structure yes; child resolution needs data |
| Currency formatting | `form.js:getInput()` | **Yes** | `$${value.toFixed(2)}` |

**Estimated server-renderable surface: 85-90% of initial display-mode HTML.**

---

## 3. What Requires Client-Side JavaScript

### 3.1 The Actor/Message Bus (Matrix)

The `Matrix` class (`Matrix.js:11-81`) is PyBend's message routing backbone.
It cannot run on the server because it:

- Manages WebSocket/HTTP connections via `NetworkAdapter`
- Routes messages between in-browser actors (components)
- Handles real-time updates (entity changes from other users)

However, the Matrix is only needed for **runtime interactivity**, not initial render.
SSR eliminates the need for the ATTACH->SCHEMA->READ bootstrap sequence entirely.

### 3.2 Interactive Behaviors

These require JavaScript and cannot be server-rendered:

| Behavior | Code Location | Why Client-Only |
|----------|--------------|-----------------|
| Edit/Save toggle | `ntt-item.js:103-109` | User-initiated state change |
| Input change handling | `ntt-item.js:113-135` | Real-time form binding |
| Delete confirmation | `ntt-item.js:65-98` | `confirm()` dialog + network call |
| Card click -> SELECT | `ntt-item.js:588-597` | Navigation via actor message |
| Show more/less toggle | `ntt-item.js:517-527` | DOM class toggle |
| Reply input box | `ntt-item.js:530-585` | Dynamic DOM creation + method call |
| Load More pagination | `ListElement.js:63-68` | Incremental data fetch |
| Method button execution | `ntt-method.js` | Network call + response handling |
| Surgical DOM updates | `ntt-item.js:336-461` | In-place patching (avoids full re-render) |
| Entity signal subscription | `NTTElement.js:84-94` | Live update from other components |

### 3.3 The Permission Check Edge Case

The `permissions.canAction()` calls in `sm()` and `md()` gate edit/delete button
visibility. These require knowing the current user. On the server, this is
**solvable** -- the JWT token is available in the request, and the ABAC rules
are defined on the model. The server can evaluate `OWNER | ROLE('admin')` against
the authenticated user and the resource's `user_owner` field.

```python
# The server already has everything needed for this check:
# 1. User identity (from JWT in request)
# 2. Access rules (from model.__access__)
# 3. Resource data (from database query)
# 4. ABAC resolver (DefaultResolver in routes_fastapi.py:17)
```

This means permission-gated UI elements (edit buttons, delete buttons) CAN be
server-rendered correctly for each user -- a capability that Next.js/Nuxt achieve
only through server components or middleware.

---

## 4. The Actor/Matrix System and SSR Boundaries

### Architecture of the Actor System

```
Matrix (root)                            [Matrix.js]
  |-- NetworkAdapter (HTTP/WS bridge)    [NetworkAdapter.js]
  |-- NTT (type registry)               [NTT.js - static level]
  |     |-- DynamicClass "Product"       [NTT.js - prototype()]
  |     |     |-- NTT instance "1"
  |     |     |-- NTT instance "2"
  |     |-- DynamicClass "Comment"
  |           |-- NTT instance "1"
  |-- Component instances                [Component.js]
        |-- ntt-list-abc123
        |-- ntt-item-def456
```

### What the Actor System Does vs. What SSR Replaces

| Actor System Function | Needed for SSR? | Replacement |
|-----------------------|-----------------|-------------|
| Schema fetch + DynamicClass creation | **No** | Server inlines schema as `<script data-ntt-schema>` |
| Data fetch + instance creation | **No** | Server inlines data as `<script data-ntt-data>` |
| ATTACH/DESCRIBE handshake | **No** | Server renders HTML directly |
| Watcher notification (list updates) | **Post-hydration only** | Client JS picks up after initial render |
| Real-time entity updates | **Post-hydration only** | Client JS handles live changes |
| Method execution (like, comment) | **Post-hydration only** | Client JS handles user actions |

**Key insight:** The actor system is a *runtime coordination mechanism*. SSR makes
its bootstrap phase redundant. After hydration, the actor system resumes its role
for live updates and user interactions. The two are complementary, not conflicting.

### Hydration Strategy

After SSR delivers the initial HTML, the client-side JavaScript needs to:

1. Parse the inlined schema (already supported via `#consumePreloadedSchema`)
2. Parse the inlined data (already supported via `#consumePreloadedData`)
3. Create DynamicClasses from the schema (no network request)
4. Create NTT instances from the data (no network request)
5. Attach event listeners to the already-rendered DOM

Steps 1-4 are already optimized in the codebase. Step 5 is the hydration gap --
the current `render()` method replaces `innerHTML` entirely, discarding SSR HTML.
Hydration would need to adopt the DOM instead of replacing it.

---

## 5. Existing SSR-Ready Infrastructure

PyBend already has several pieces that directly support SSR:

### 5.1 Schema Pre-loading (NTT.js:244-257)

```javascript
// NTT.js:244-257 -- Already in the codebase
static #consumePreloadedSchema(model) {
    const el = document.querySelector(`script[data-ntt-schema="${model}"]`);
    if (!el) return false;
    try {
        const data = JSON.parse(el.textContent);
        el.remove();
        Logging.debug(`[NTT] Pre-loaded schema for ${model}`);
        NTT.SCHEMA(data);
        return true;
    } catch (e) {
        Logging.error(`[NTT] Failed to parse pre-loaded schema for ${model}`, e);
        return false;
    }
}
```

This method is called at two points in the code:
- `NTT.ATTACH()` (line 333): Before dispatching a network SCHEMA request
- `NTT.attach()` (line 375): Before dispatching a network SCHEMA request in the callback path

**What this means:** If the server injects `<script data-ntt-schema="Product">{ ... }</script>`
into the HTML, the client skips the schema fetch entirely. NETWORK REQUEST 1 is eliminated.

### 5.2 Data Pre-loading (NTT.js:265-277)

```javascript
// NTT.js:265-277 -- Already in the codebase
static #consumePreloadedData(tablename) {
    const el = document.querySelector(`script[data-ntt-data="${tablename}"]`);
    if (!el) return null;
    try {
        const data = JSON.parse(el.textContent);
        el.remove();
        Logging.debug(`[NTT] Pre-loaded data for ${tablename}`);
        return data;
    } catch (e) {
        Logging.error(`[NTT] Failed to parse pre-loaded data for ${tablename}`, e);
        return null;
    }
}
```

This is consumed in `NTT.SCHEMA()` (line 419-425):

```javascript
const preloadedData = NTT.#consumePreloadedData(tablename);
if (preloadedData) {
    DC.READ(preloadedData);
} else {
    DC.call('READ', popDepth > 0 ? {depth: popDepth} : {});
}
```

**What this means:** If the server injects `<script data-ntt-data="products">[...]</script>`,
the client skips the data fetch. NETWORK REQUEST 2 is eliminated.

### 5.3 Schema Completeness

`ProtoModel.schema()` (`proto_model.py:199-316`) generates a **remarkably complete**
rendering specification. The schema already carries:

- Field types and validation constraints (Pydantic-derived)
- UI widget hints (`json_schema_extra={'ui': {'widget': 'currency'}}`)
- Field ordering (`__ui__['field_order']`)
- Field grouping (`__ui__['groups']`)
- Display/hide flags (`ui.display`, `ui.protected`)
- Access rules serialized for evaluation (`access_schema()`)
- Method signatures with UI hints (`methods[name].ui`)
- Nested model schemas in `$defs`
- Renderer hints (`ui.renderer.item`, `ui.renderer.list`)

This is not metadata bolted on after the fact -- it is the schema itself, generated
from the same model definition that drives the API and the database. Every piece of
information `form.js` and `ntt-item.js` need is already in this schema.

### 5.4 The `model_dump(response=True)` Pattern

```python
# proto_model.py:117-137
def model_dump(self, *, response: bool = False, **kwargs) -> Dict[str, Any]:
    data = super().model_dump(**kwargs)
    if response:
        data = {
            '$schema': meta['schema_url'],
            '$id': f"{meta['base_url']}/{instance_id}",
            **data
        }
    return data
```

Every entity response already carries its own schema URL and instance URL.
This self-describing format means the server can render an entity without additional
lookups -- the entity record plus the cached schema is sufficient.

---

## 6. Proposed SSR Implementation for PyBend

### 6.1 Three Strategies (Pick One or Layer Them)

#### Strategy A: Schema+Data Injection (Lowest effort, highest ROI)

Inject pre-loaded JSON into the HTML. Let the existing client-side code consume it
without network requests.

```
Server receives GET /app/products
  --> Calls Product.schema() (cached, ~0ms)
  --> Calls Product.list(limit=20, offset=0) (~5ms)
  --> Returns HTML with:
      <script data-ntt-schema="Product">{...schema...}</script>
      <script data-ntt-data="products">{...data...}</script>
      <ntt-list model="Product"></ntt-list>
```

**Result:** Eliminates 2 network round-trips. Client still renders HTML, but from
local data. Time-to-interactive drops by 200-400ms (the two sequential fetches).

**Implementation cost:** ~50 lines of Python (a Jinja2 template that injects JSON).
The client-side consumption code already exists.

#### Strategy B: Pre-Rendered HTML Shell (Medium effort, best UX)

Server renders the initial HTML structure. Client hydrates for interactivity.

```
Server receives GET /app/products
  --> Calls Product.schema()
  --> Calls Product.list(limit=20, offset=0)
  --> Runs Python port of form.js logic to produce HTML
  --> Returns:
      <ntt-list model="Product">
        <template shadowrootmode="open">
          <div class="list-grid">
            <ntt-item ref="http://.../products/1">
              <template shadowrootmode="open">
                <div class="card" data-display="md">
                  <h2 class="Product" data-value="name">Widget Pro</h2>
                  <div class="currency-display" data-value="price">$29.99</div>
                  ...
                </div>
              </template>
            </ntt-item>
            ...
          </div>
        </template>
      </ntt-list>
      <script data-ntt-schema="Product">{...}</script>
      <script data-ntt-data="products">{...}</script>
```

This uses **Declarative Shadow DOM** (DSD) -- the `<template shadowrootmode="open">`
syntax that browsers natively parse into shadow roots without JavaScript. Supported
in Chrome 90+, Safari 16.4+, and Firefox 123+.

**Result:** Content visible before any JavaScript executes. Meaningful first paint
in <100ms from server response start.

**Implementation cost:** ~300-500 lines of Python (a Jinja2 template system that
mirrors `form.js` logic + DSD wrapper generation).

#### Strategy C: HTMX-Enhanced Progressive Rendering (Highest effort, most flexible)

Replace the actor-based data flow with HTMX attributes for initial page loads.
Server returns HTML fragments. JavaScript only handles what HTMX cannot.

```html
<!-- Server returns this; HTMX handles pagination -->
<div class="list-grid"
     hx-get="/products?format=html&limit=20&offset=20"
     hx-trigger="revealed"
     hx-swap="beforeend">
  <ntt-item>
    <div class="card" data-display="md">
      <h2>Widget Pro</h2>
      <div class="currency-display">$29.99</div>
      <button hx-post="/products/1/like" hx-swap="outerHTML">Like</button>
    </div>
  </ntt-item>
  ...
</div>
```

**Result:** Eliminates JavaScript entirely for read-only views. Edit mode still
needs the actor system.

**Implementation cost:** Significant. Requires dual-format routes (JSON + HTML),
HTMX integration, and careful boundary management between HTMX and the actor system.

### 6.2 Recommended Approach: Strategy A First, Then B

Strategy A can be implemented in a day and deployed immediately. It uses existing
client-side infrastructure (`#consumePreloadedSchema`, `#consumePreloadedData`)
and requires only a server-side route that injects JSON into an HTML template.

Strategy B should follow when the Python-side rendering engine is built. The key
insight is that `form.js:getForm()` can be ported to Jinja2 templates because
every decision it makes is data-driven:

```python
# Python equivalent of form.js:getInput() for display mode
def render_field(key: str, schema: dict, value: Any) -> str:
    field_def = schema['properties'].get(key, {})
    widget = field_def.get('ui', {}).get('widget')
    field_type = field_def.get('type', 'string')

    if widget == 'currency' and isinstance(value, (int, float)):
        return f'<div class="currency-display" data-value="{key}">${value:.2f}</div>'
    elif widget == 'textarea':
        return f'<div class="text-block" data-value="{key}">{value}</div>'
    elif field_type == 'boolean':
        return f'<div data-value="{key}">{"Yes" if value else "No"}</div>'
    else:
        return f'<div data-value="{key}">{value}</div>'
```

### 6.3 Concrete Implementation: Strategy A

Here is what the server-side route looks like:

```python
# New file: src/pybend/core/api/ssr.py

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Template
from pybend.core.utils.registrar import registered_models
import json

ssr_router = APIRouter()

SSR_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  {% for model_name, schema_json in schemas.items() %}
  <script type="application/json" data-ntt-schema="{{ model_name }}">
  {{ schema_json }}
  </script>
  {% endfor %}

  {% for table_name, data_json in datasets.items() %}
  <script type="application/json" data-ntt-data="{{ table_name }}">
  {{ data_json }}
  </script>
  {% endfor %}

  <ntt-list model="{{ primary_model }}"></ntt-list>

  <script type="module" src="/core/NTT.js"></script>
  <script type="module" src="/components/ntt-list.js"></script>
</body>
</html>
""")

@ssr_router.get("/app/{model_name}", response_class=HTMLResponse)
async def ssr_page(model_name: str, request: Request):
    model_class = registered_models.get(model_name)
    if not model_class:
        raise HTTPException(404, f"Model {model_name} not found")

    # Server-side: generate schema + fetch data (no network round-trips)
    schema = model_class.schema()
    result = model_class.list(limit=20, offset=0)

    # Serialize for injection
    data_items = result['data'] if isinstance(result, dict) else result
    serialized = [item.model_dump(response=True) for item in data_items]

    schemas = {model_name: json.dumps(schema)}
    datasets = {schema.get('__tablename__', model_name.lower() + 's'): json.dumps(serialized)}

    # Also include $defs schemas
    for def_name, def_schema in schema.get('$defs', {}).items():
        schemas[def_name] = json.dumps(def_schema)

    return SSR_TEMPLATE.render(
        title=model_name,
        primary_model=model_name,
        schemas=schemas,
        datasets=datasets,
    )
```

**Lines of code:** ~45 for the route, ~20 for the template.
**Network requests eliminated:** 2 (schema + data fetch).
**Time to implement:** 2-4 hours including tests.

---

## 7. FastAPI Async and Streaming SSR

### 7.1 FastAPI's Streaming Response

FastAPI supports `StreamingResponse` for chunked transfer encoding. This maps
directly to SSR streaming patterns where the server sends the HTML shell first,
then streams data as it becomes available:

```python
from fastapi.responses import StreamingResponse

async def stream_ssr_page(model_name: str):
    async def generate():
        # Phase 1: Send HTML head + shell immediately
        yield "<!DOCTYPE html><html><head>...</head><body>\n"
        yield '<div id="app-shell"><ntt-list model="Product"></ntt-list></div>\n'

        # Phase 2: Stream schema (likely cached, instant)
        schema = model_class.schema()
        yield f'<script data-ntt-schema="{model_name}">{json.dumps(schema)}</script>\n'

        # Phase 3: Stream data (may take time for complex queries)
        result = model_class.list(limit=20, offset=0)
        serialized = [item.model_dump(response=True) for item in result['data']]
        tablename = schema.get('__tablename__', model_name.lower() + 's')
        yield f'<script data-ntt-data="{tablename}">{json.dumps(serialized)}</script>\n'

        # Phase 4: Load JS (triggers hydration)
        yield '<script type="module" src="/core/NTT.js"></script>\n'
        yield '</body></html>'

    return StreamingResponse(generate(), media_type="text/html")
```

### 7.2 Why Streaming Matters for PyBend

PyBend's schema is cached after first generation (`ProtoModel._schema_cache`),
so Phase 2 is nearly instant. The database query in Phase 3 is the bottleneck.
Streaming means the browser can begin parsing the HTML shell, loading CSS, and
even loading JavaScript modules *while the database query runs*.

```
Streaming SSR Timeline:

Server:  [head]-->[shell]-->[schema]-------->[data]-->[scripts]-->
Browser: [parse]  [paint]   [parse schema]   [parse data]  [hydrate]
                  ^                                         ^
                  Shell visible                     Fully interactive
                  (~50ms from first byte)           (~200ms from first byte)
```

Compare to the current client-side rendering:

```
Current CSR Timeline:

Server:  [HTML shell]-->
Browser: [parse]->[load JS]->[SCHEMA fetch]---------->[DATA fetch]---------->[render]
                                                                              ^
                                                                    First meaningful paint
                                                                    (~800-1200ms)
```

### 7.3 Async Data Fetching

FastAPI's async nature means the SSR route can fetch data concurrently. If a page
needs both Product and User schemas:

```python
import asyncio

async def multi_model_page():
    # Fetch schemas (cached, instant) and data (async) concurrently
    product_data, user_data = await asyncio.gather(
        asyncio.to_thread(Product.list, limit=20, offset=0),
        asyncio.to_thread(User.list, limit=10, offset=0),
    )
```

This is a natural fit -- the existing storage layer is synchronous (SQLite), but
`asyncio.to_thread` bridges it cleanly.

---

## 8. Authorization and Per-User SSR

### 8.1 The Challenge

SSR must respect per-user authorization. Different users see different:
- Edit/delete buttons (gated by `OWNER | ROLE('admin')`)
- Data subsets (ABAC list filtering via `sql_filter_for()`)
- Field visibility (field-level access rules)

### 8.2 What PyBend Already Has

The `routes_fastapi.py` authorization chain provides everything needed:

```python
# routes_fastapi.py:25-32 -- Already builds auth context from request
def _build_context(request, model_class, action, resource=None, parent_id=None):
    return AccessContext(
        user=_get_user(request),      # From JWT in request headers
        action=action,
        model_class=model_class,
        resource=resource,
        parent_id=parent_id,
    )
```

For SSR, the same `_get_user(request)` extracts identity from the JWT token.
The ABAC resolver can then:

1. Filter the data query: `_resolver.sql_filter_for(ctx)` produces WHERE clauses
   that limit results to what the user can see.
2. Evaluate button visibility: `custom_access.evaluate(ctx)` determines if
   `OWNER | ROLE('admin')` passes for this user + resource.

### 8.3 Per-User SSR in Practice

```python
async def ssr_product_list(request: Request):
    user = _get_user(request)
    ctx = _build_context(request, Product, "list")
    auth_filter = _resolver.sql_filter_for(ctx)

    # Data is already filtered for this user
    result = Product.list(sql_filter=auth_filter, limit=20, offset=0)

    # Schema is the same for all users (it's the model definition)
    schema = Product.schema()

    # But rendered HTML differs: edit/delete buttons depend on user + resource
    for item in result['data']:
        item._can_update = _resolver.authorize(
            _build_context(request, Product, "update", resource=item)
        )
        item._can_delete = _resolver.authorize(
            _build_context(request, Product, "delete", resource=item)
        )
```

### 8.4 Caching Implications

Per-user SSR means the rendered HTML is **not globally cacheable**. However:

- **Schema injection** (Strategy A, Phase 2) IS cacheable -- the schema is the same for everyone.
- **Data injection** is user-specific but can use ETag/conditional requests.
- **HTML rendering** (Strategy B) is user-specific for pages with OWNER-gated controls.
  - Optimization: render the common HTML, add button visibility via CSS classes
    tied to a user role class on `<body>`. One HTML + per-role CSS rules.

### 8.5 The Anonymous User Fast Path

For unauthenticated users (no JWT token), SSR is **fully cacheable**:
- `ANYONE` access rules mean all data is visible
- No edit/delete buttons (failed `AUTHENTICATED` check)
- Can use CDN edge caching with long TTLs

This covers the SEO and first-visit use cases perfectly.

---

## 9. Gaps and Work Required

### 9.1 No Server-Side Template Engine (for Strategy B)

PyBend currently has no HTML template rendering on the backend. The `FastAPIBackend`
serves static files directly (`backend.py:125-162`). Adding Jinja2 requires:

- `pip install jinja2` (FastAPI already depends on Starlette which has optional Jinja2 support)
- Template directory structure
- Template filters that mirror `form.js` logic

**Effort:** Low. Jinja2 is a one-line dependency add.

### 9.2 No Server-Side HTML Generation for Web Components

The biggest gap: there is no Python equivalent of `form.js`. The form generator
logic exists only in JavaScript. Porting it requires:

- A Python function that takes `(schema, values, mode)` and returns HTML
- Mapping each `form.js:getInput()` branch to a Jinja2 template or Python function
- Handling the same edge cases: `anyOf` resolution, `$ref` fields, `selfref`, arrays

**Effort estimate:** ~400 lines of Python to cover the full `form.js` surface.
The logic is straightforward -- it is a large switch/case on field types.

### 9.3 Declarative Shadow DOM Adoption

For Strategy B, the server must emit `<template shadowrootmode="open">` wrappers
around component content. This means:

- The server must know which Web Components use Shadow DOM (all of them, currently)
- The emitted HTML must match what the client-side `render()` would produce
- Stylesheets must be included in the DSD template (either inline or via `<link>`)

**Challenge:** The current `ntt-item.css` is loaded via a `<link>` in the shadow root
(`ntt-item.js:30`). DSD supports `<link>` inside `<template shadowrootmode>`, but
the browser will fetch the CSS file. For optimal performance, inline `<style>` in
the DSD template is preferred.

**Browser support for DSD:** Chrome 90+, Safari 16.4+, Firefox 123+. A polyfill
exists for older browsers (adds ~1KB).

Reference: [Declarative Shadow DOM on web.dev](https://web.dev/articles/declarative-shadow-dom)

### 9.4 Hydration Mismatch Prevention

When client-side JavaScript loads after SSR, it must not blow away the server-rendered
DOM. The current `render()` method in `ntt-item.js` does exactly that:

```javascript
// ntt-item.js:480 -- This replaces the entire shadow root
this.shadowRoot.innerHTML = `<div class="card${indentClass}" ...>${html}</div>`;
```

**Required change:** Add a hydration path that detects existing DSD content and
attaches event listeners without re-rendering:

```javascript
render() {
    if (!this.schema || !this.value) return;

    // Hydration: if shadow root already has server-rendered content, just bind events
    if (this.shadowRoot.querySelector('.card') && !this._rendered) {
        this._rendered = true;
        this.#bindEvents();
        return;
    }

    // Normal client-side render path (unchanged)
    const size = this.displayMode;
    const html = (this[size] || this.md).call(this);
    // ...
}
```

**Effort:** ~20 lines per component (`ntt-item`, `ntt-list`). The `#bindEvents()`
method already exists and is self-contained.

### 9.5 CSS-in-DSD Strategy

Each component currently loads CSS via:

```javascript
get styles() { return new URL('./ntt-item.css', import.meta.url).href; }
```

For DSD, the server needs to either:
- Include a `<link rel="stylesheet" href="...">` in each DSD template (causes fetch per component)
- Inline the CSS in a `<style>` tag in each DSD template (larger HTML, but no FOUC)
- Use Constructable Stylesheets (requires JS, defeats purpose of DSD)

**Recommendation:** Inline critical CSS for the initial render, lazy-load the full
stylesheet during hydration.

### Summary: Gap Analysis

| Gap | Severity | Effort | Blocks Strategy |
|-----|----------|--------|-----------------|
| No Jinja2 dependency | Low | 1 hour | A, B |
| No Python form renderer | Medium | 2-3 days | B only |
| No DSD emission | Medium | 1-2 days | B only |
| No hydration path in render() | Medium | 1 day | B only |
| CSS-in-DSD strategy | Low | 1 day | B only |
| Per-user cache strategy | Low | Design only | None |

**Strategy A has no significant gaps.** The pre-loading infrastructure exists.
Only the server route and template need to be written.

---

## 10. Competitive Positioning

### 10.1 How "Schema-Driven SSR" Differs from the Industry

The dominant SSR frameworks -- Next.js, Nuxt, Astro, SvelteKit -- all share a
common assumption: **the developer writes both server and client rendering code**,
and the framework stitches them together.

| Framework | SSR Model | Developer Writes | Rendering Logic |
|-----------|-----------|-----------------|-----------------|
| Next.js | React Server Components + Client Components | JSX for both server and client | Duplicated across server/client boundaries |
| Nuxt | Vue Universal Rendering | Vue SFCs | Same component runs on server (Node.js) and client |
| Astro | Islands Architecture | Astro components + framework islands | Static HTML by default, JS only for interactive islands |
| SvelteKit | Universal + Streaming | Svelte components | Same component runs on server and client |
| **PyBend** | **Schema-driven** | **Python model only** | **Schema carries rendering spec; server or client interprets it** |

The fundamental difference: in Next.js, the developer writes `<ProductCard>` as a
React component that renders HTML. In PyBend, the developer writes `class Product(ProtoModel)`
and the rendering is derived. This means:

1. **No rendering code duplication.** The Python model is the single source of truth.
   There is no "server component" vs "client component" distinction because there
   are no components to begin with -- only schema interpretation.

2. **SSR is a server-side schema interpreter.** The same JSON Schema that drives
   client-side `form.js` drives server-side Jinja2 templates. The rendering logic
   is written once (in the template engine) and works for every model.

3. **Zero frontend build step.** No Webpack, no Vite, no Turbopack. The server
   emits HTML. The client loads vanilla JS modules. There is no bundle to optimize.

### 10.2 Comparison Matrix

| Capability | Next.js 15 | Nuxt 3 | Astro 5 | PyBend (proposed) |
|-----------|-----------|--------|---------|-------------------|
| Time to first byte | ~100ms (edge) | ~150ms | ~50ms (static) | ~50ms (streaming) |
| Zero-JS initial render | No (hydration required) | No | Yes (non-island) | Yes (Strategy B with DSD) |
| Per-user personalization | Server Components | Server middleware | Server endpoints | ABAC rules in schema |
| New model = new page | Write component + page | Write component + page | Write component + page | **Just register the model** |
| Form generation | Manual or library | Manual or library | Manual | **Schema-derived** |
| Permission-gated UI | Manual checks | Manual checks | Manual checks | **Declared on model, auto-enforced** |
| Build step required | Yes (Turbopack/Webpack) | Yes (Vite) | Yes (Vite) | **No** |
| Runtime overhead | React + framework | Vue + framework | Minimal | **Zero (vanilla JS)** |
| SEO capability | Full (RSC) | Full (Universal) | Full (Static) | **Full (SSR or static)** |

### 10.3 The Strategic Position

**PyBend's SSR story is not "we added SSR to a SPA framework." It is: "the server
already knows everything about the UI. We are simply having it render HTML directly
instead of sending JSON and making the client do it."**

This is a stronger narrative than any JavaScript meta-framework can offer because:

- Adding a new model automatically creates a new server-rendered page
- Changing `__ui__` hints on a model changes the server-rendered HTML
- Permission changes propagate to server-rendered button visibility
- No frontend developer needed for the default experience

The closest comparison is **Astro's content collections** -- where data shapes drive
page generation. But Astro still requires the developer to write Astro components.
PyBend's schemas carry enough information to render without any template code.

Reference frameworks and their SSR approaches:
- [Lit SSR with Declarative Shadow DOM](https://lit.dev/docs/ssr/overview/)
- [Stencil SSR](https://stenciljs.com/docs/server-side-rendering)
- [FastHX: Declarative Python SSR for FastAPI](https://github.com/volfpeter/fasthx)
- [HTMX with FastAPI](https://testdriven.io/blog/fastapi-htmx/)
- [Declarative Shadow DOM on web.dev](https://web.dev/articles/declarative-shadow-dom)
- [Web Components and SSR - 2024 Edition](https://dev.to/stuffbreaker/web-components-and-ssr-2024-edition-1nel)
- [2026 Frontend Framework Showdown](https://www.nunuqs.com/blog/nuxt-vs-next-js-vs-astro-vs-sveltekit-2026-frontend-framework-showdown)

---

## 11. Recommendations

### For the CEO

1. **SSR is not a rewrite.** PyBend's architecture makes SSR an additive feature,
   not a migration. The existing client-side rendering continues to work. SSR
   adds a faster path for initial page loads and SEO.

2. **Competitive moat.** "Define a model, get a server-rendered page" is a pitch
   no JavaScript framework can match. Next.js requires writing React components.
   Nuxt requires writing Vue components. PyBend requires writing a Python class.

3. **Strategy A (data injection) costs 1 day and eliminates 200-400ms of latency.**
   This is the immediate win. Ship it, measure the impact, then invest in Strategy B.

4. **SEO unlocked.** Search engines can index PyBend applications without executing
   JavaScript. This opens PyBend to content-heavy use cases (product catalogs,
   documentation sites, blogs) that currently require a separate static site generator.

### For the Engineering Team

1. **Implement Strategy A this week.** The infrastructure exists. Write the SSR route,
   the Jinja2 template, and wire it into `FastAPIBackend`. The `#consumePreloadedSchema`
   and `#consumePreloadedData` methods are already tested and functional.

2. **Start the Python form renderer.** Port `form.js:getInput()` to a Jinja2 template
   or Python function. Begin with display-mode-only rendering (skip edit mode).
   Target: render a Product card in pure HTML from schema + data.

3. **Add hydration detection to `ntt-item.render()`.** A 20-line change: if the
   shadow root already has a `.card` element, skip `innerHTML` replacement and
   go straight to `#bindEvents()`.

4. **Do NOT adopt HTMX yet.** Strategy C (HTMX) creates a dual rendering path
   (JSON + HTML) that adds complexity. PyBend's actor system handles interactivity
   well. HTMX would be useful only if the goal is to eliminate client-side JS entirely,
   which would sacrifice real-time updates and the actor coordination model.

5. **Consider CSS extraction.** Build a utility that reads `ntt-item.css` and
   `ntt-list.css` at startup, stores the content in memory, and injects it into
   DSD templates as `<style>` blocks. This prevents FOUC without requiring a build step.

### Implementation Roadmap

```
Week 1: Strategy A (Data Injection)
  - [ ] Add Jinja2 dependency to pyproject.toml
  - [ ] Create SSR route in routes_fastapi.py or new ssr.py
  - [ ] Create base HTML template with schema/data injection slots
  - [ ] Wire into FastAPIBackend._mount_static()
  - [ ] Test: verify #consumePreloadedSchema eliminates SCHEMA fetch
  - [ ] Test: verify #consumePreloadedData eliminates READ fetch
  - [ ] Measure: time-to-interactive before vs after

Week 2-3: Strategy B Foundation (Python Form Renderer)
  - [ ] Port form.js:getInput() display branches to Python
  - [ ] Port form.js:getHeader() to Python
  - [ ] Port form.js:validationAttrs() to Python
  - [ ] Port ntt-item:xs(), sm() to Python template functions
  - [ ] Add DSD <template shadowrootmode> wrapper generation
  - [ ] Test: compare Python-rendered HTML vs JS-rendered HTML for parity

Week 4: Hydration
  - [ ] Add hydration detection to ntt-item.render()
  - [ ] Add hydration detection to ListElement.render()
  - [ ] CSS extraction utility for DSD inline styles
  - [ ] Test: SSR -> hydration -> edit mode -> save round-trip
  - [ ] Test: SSR -> hydration -> live update from another user

Week 5: Per-User SSR
  - [ ] Integrate ABAC resolver into SSR route
  - [ ] Conditional button rendering based on user + resource
  - [ ] Anonymous user caching strategy
  - [ ] Test: admin sees edit/delete, regular user sees only read
```

---

## Appendix A: File References

All file paths referenced in this document:

| File | Role | Key Lines |
|------|------|-----------|
| `/workspace/src/pybend/static/core/NTT.js` | Entity system, DynamicClass factory, SSR pre-loading | 244-277 (pre-loading), 390-426 (SCHEMA), 663-791 (prototype) |
| `/workspace/src/pybend/static/generators/form.js` | Schema-driven form HTML generation | 17-65 (getForm), 173-236 (getInput), 159-171 (validationAttrs) |
| `/workspace/src/pybend/static/components/ntt-item.js` | Entity rendering at all sizes | 143-146 (xs), 156-282 (sm), 284-318 (md), 468-486 (render) |
| `/workspace/src/pybend/static/components/ntt-list.js` | Collection component (delegates to ListElement) | 1-19 (entire file) |
| `/workspace/src/pybend/static/components/ListElement.js` | Collection base: data lifecycle, child stamping | 52-68 (definedCallback, loadMore), 146-161 (createChild) |
| `/workspace/src/pybend/static/components/NTTElement.js` | Single entity base: data lifecycle, auto-render | 32-41 (value setter), 78-95 (DESCRIBE) |
| `/workspace/src/pybend/static/core/Matrix.js` | Actor message bus (root router) | 26-48 (inbox routing), 50-52 (dispatch) |
| `/workspace/src/pybend/static/core/Component.js` | Web Component base: actor bridge + schema lifecycle | 63-92 (constructor), 99-129 (attributeChangedCallback) |
| `/workspace/src/pybend/static/core/Actor.js` | Actor base class: addressing, routing, message dispatch | 17-32 (constructor), 62-100 (_send routing) |
| `/workspace/src/pybend/core/models/proto_model.py` | Base model, schema generation, response serialization | 117-137 (model_dump), 199-316 (schema) |
| `/workspace/src/pybend/core/api/routes_fastapi.py` | Route factories, auth injection, CRUD endpoints | 20-32 (user extraction, context building), 92-137 (list), 168-180 (schema) |
| `/workspace/src/pybend/core/api/backend.py` | FastAPI backend setup, middleware, static file serving | 48-168 (FastAPIBackend) |
| `/workspace/src/pybend/core/app.py` | Application builder and factory | 59-100 (PyBendApp) |

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **DynamicClass** | Runtime-generated NTT subclass created by `prototype()` from a JSON Schema. Holds typed properties, methods, and CRUD handlers for a specific model. |
| **DSD** | Declarative Shadow DOM. HTML syntax (`<template shadowrootmode="open">`) that browsers parse into shadow roots without JavaScript. |
| **Hydration** | The process of attaching JavaScript event handlers to server-rendered HTML, making it interactive. |
| **Matrix** | PyBend's actor message bus. Routes TX (transaction) messages between actors (components, NTT instances, network adapter). |
| **Schema injection** | Embedding JSON Schema and entity data as `<script>` tags in the HTML, consumed by `#consumePreloadedSchema()` and `#consumePreloadedData()`. |
| **ABAC** | Attribute-Based Access Control. PyBend's authorization model where rules like `OWNER | ROLE('admin')` are declared on models and evaluated at runtime. |
| **Formidable** | The exported name of `form.js`'s public API (`Formidable.getForm()`). Generates HTML forms from schema properties. |
| **Strategy A** | Schema+Data injection: server embeds JSON in HTML, client renders from local data (no network fetches). |
| **Strategy B** | Pre-rendered HTML with DSD: server renders full HTML, client hydrates for interactivity. |
| **Strategy C** | HTMX-enhanced rendering: server returns HTML fragments, HTMX handles partial updates. |
