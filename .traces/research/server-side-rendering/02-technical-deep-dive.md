# Server-Side Rendering: Technical Deep Dive

**For PyBend -- a schema-driven Python/FastAPI framework with vanilla JS Web Components**

*Research date: 2026-02-25 | Author: Claude Opus 4.6 | Target: Technical leadership + engineering teams*

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [SSR Architecture Patterns](#2-ssr-architecture-patterns)
3. [SSR and Web Components](#3-ssr-and-web-components)
4. [Python Server-Side Rendering Engines](#4-python-server-side-rendering-engines)
5. [The HTML-to-Interactive Transition](#5-the-html-to-interactive-transition)
6. [Security Considerations](#6-security-considerations)
7. [Performance Characteristics](#7-performance-characteristics)
8. [DevOps Implications](#8-devops-implications)
9. [Testing Strategies](#9-testing-strategies)
10. [PyBend-Specific Analysis](#10-pybend-specific-analysis)
11. [Sources](#11-sources)

---

## 1. Executive Summary

**So what?** Server-side rendering determines how fast your users see content and how quickly they can interact with it. Choosing the wrong pattern costs you 1-3 seconds of load time and measurably hurts conversion rates. For PyBend -- a framework that already generates everything from a Python model definition -- SSR is uniquely positioned: the backend *already owns the schema and the data*, making server-rendered HTML a natural extension of the existing architecture rather than a bolt-on.

This document surveys seven SSR architecture patterns, evaluates their compatibility with Web Components (PyBend's frontend primitive), benchmarks Python rendering engines, and provides concrete recommendations for integrating SSR into PyBend's schema-driven pipeline.

**Key findings:**

| Finding | Implication |
|---------|-------------|
| Streaming SSR reduces perceived load by 40% vs. traditional SSR | PyBend's FastAPI backend already supports `StreamingResponse` |
| Declarative Shadow DOM now ships in Chrome, Safari, Edge | Web Components can finally be SSR'd without hacks |
| FastAPI + Jinja2 achieves FCP in 300-500ms vs. 1500-3000ms for React SPAs | 3-5x improvement with minimal infrastructure |
| Qwik-style resumability ships ~1KB JS vs. React's ~30-60KB for hydration | Relevant pattern for PyBend's zero-framework frontend |
| HTMX + FastAPI produces 50-100KB total page weight vs. 1.5-3MB for React | 15-30x smaller payload |

---

## 2. SSR Architecture Patterns

**So what?** There are seven distinct ways to render HTML on the server. Each trades off initial speed, interactivity latency, infrastructure complexity, and developer experience differently. Understanding these patterns prevents the mistake of adopting "SSR" as a monolith when only a specific slice applies to your use case.

### 2.1 Pattern Taxonomy

```
                        RENDERING PATTERN SPECTRUM

    Pure CSR          Hybrid               Pure SSR
    (SPA)             Patterns              (Traditional)
    |                 |                     |
    v                 v                     v
    +---------+   +----------+   +--------+   +---------+
    | Client  |   | Islands  |   | Stream |   | Full    |
    | Side    |   | Arch.    |   | SSR    |   | SSR     |
    | Render  |   +----------+   +--------+   +---------+
    +---------+   | Partial  |   | ISR    |   | Static  |
                  | Pre-     |   +--------+   | Gen     |
                  | render   |   | Resume |   | (SSG)   |
                  +----------+   +--------+   +---------+

    <--- More JS, slower FCP    Faster FCP, less JS --->
    <--- Richer interactivity   Better SEO ----------->
```

### 2.2 Full SSR (Traditional Server Rendering)

The server generates complete HTML for every request. The browser renders it immediately -- no JavaScript required for initial display.

```
  Client                    Server                  Database
    |                         |                        |
    |--- GET /products ------>|                        |
    |                         |--- SELECT * FROM... -->|
    |                         |<-- rows ---------------|
    |                         |                        |
    |                         | [Render HTML template]  |
    |                         |                        |
    |<-- Full HTML page ------|                        |
    |                         |                        |
    | [Browser paints]        |                        |
    | [Download JS]           |                        |
    | [Hydrate / bind events] |                        |
```

**Characteristics:**
- TTFB: 100-300ms added for server render time
- FCP: Excellent (HTML arrives ready to paint)
- TTI: Delayed until JS downloads and hydrates
- Cacheability: Difficult for personalized content

**When to use:** Content-heavy pages, SEO-critical paths, pages where interactivity is secondary.

### 2.3 Streaming SSR

Instead of waiting for the entire page to render, the server sends HTML in chunks as they become available. The browser begins painting immediately.

```
  Client                         Server
    |                              |
    |--- GET /products ---------->|
    |                              |
    |<-- <head> + nav (chunk 1) --|  (immediate: no DB needed)
    | [Paint header]               |
    |                              |--- DB query -------->
    |                              |<-- results ----------|
    |<-- product list (chunk 2) --|
    | [Paint products]             |
    |                              |--- Slow API call --->
    |                              |<-- recommendations --|
    |<-- sidebar (chunk 3) -------|
    | [Paint sidebar]              |
```

**Key metric:** Streaming SSR reduces perceived load times by up to **40%** compared to traditional SSR because users see content progressively rather than waiting for complete rendering.

> **Technical detail:** In HTTP/1.1, streaming uses chunked transfer encoding (`Transfer-Encoding: chunked`). In HTTP/2 and HTTP/3, streaming is native to the protocol via multiplexed frames -- no special headers needed. FastAPI supports this via `StreamingResponse`.

**When to use:** Pages with mixed-latency data sources, dashboards, any page where the header/nav can ship before the main content.

### 2.4 Static Site Generation (SSG)

HTML is pre-built at deploy time. No server computation at request time.

**Characteristics:**
- TTFB: 20-50ms (CDN edge, no computation)
- FCP: Best possible
- TTI: Depends on JS payload
- Cacheability: Perfect (immutable until next deploy)

**When to use:** Marketing pages, documentation, blogs -- content that changes at deploy cadence, not user cadence.

### 2.5 Incremental Static Regeneration (ISR)

A hybrid: pages are statically generated but can be revalidated in the background on a timer or on-demand trigger.

```
  Request 1 (cache miss):
    Client --> CDN (miss) --> Origin server --> Render + cache --> Client

  Request 2 (cache hit, within revalidation window):
    Client --> CDN (hit) --> Client  [instant, from cache]
                CDN --> Origin server --> Re-render + update cache [background]

  Request 3 (updated cache):
    Client --> CDN (hit, fresh) --> Client
```

**Key concept:** `stale-while-revalidate` -- serve the cached version immediately while regenerating in the background. Users always get a fast response; content freshness is eventual (typically seconds to minutes).

**When to use:** Product catalogs, news feeds -- content that changes frequently but doesn't need per-request freshness.

### 2.6 Partial Prerendering (PPR)

Pioneered by Next.js 15+. A single route contains both a **static shell** (prerendered at build time) and **dynamic holes** (streamed at request time).

```html
<!-- Static shell (cached at CDN edge, instant) -->
<html>
  <head>...</head>
  <body>
    <nav>PyBend Store</nav>      <!-- static -->
    <main>
      <h1>Products</h1>          <!-- static -->

      <!-- Dynamic hole: streamed from server -->
      <Suspense fallback="<div class='skeleton'>...</div>">
        <ProductList />           <!-- dynamic, rendered at request time -->
      </Suspense>

      <!-- Dynamic hole: personalized -->
      <Suspense fallback="<div class='skeleton'>...</div>">
        <UserGreeting />          <!-- dynamic, user-specific -->
      </Suspense>
    </main>
    <footer>...</footer>          <!-- static -->
  </body>
</html>
```

**Why it matters:** PPR gives you SSG-level TTFB for the page shell while still supporting per-request dynamic content. The static parts cache at the CDN; the dynamic parts stream in.

### 2.7 Islands Architecture

The page is mostly static HTML. Only specific interactive "islands" load JavaScript and hydrate.

```
  +------------------------------------------------------------------+
  |  Static HTML (no JS)                                              |
  |                                                                   |
  |  +------------------+                                             |
  |  | Island: Search   |  <-- Hydrated, interactive                  |
  |  | (JS loaded)      |                                             |
  |  +------------------+                                             |
  |                                                                   |
  |  Product description text (static HTML, zero JS)                  |
  |                                                                   |
  |  +------------------+    +-------------------+                    |
  |  | Island: Add to   |    | Island: Reviews   |                   |
  |  | Cart (JS loaded) |    | Widget (JS loaded)|                   |
  |  +------------------+    +-------------------+                    |
  |                                                                   |
  |  Footer (static HTML, zero JS)                                    |
  +------------------------------------------------------------------+
```

**Framework implementations:** Astro (FCP: 0.8s), Fresh (Deno), Marko.

**Key benefit:** Total JS shipped is proportional to interactive surface area, not page size. A page with 3 interactive widgets ships JS for 3 widgets, not the entire page tree.

**PyBend relevance:** HIGH. PyBend's Web Components are already self-contained islands by nature. Each `<ntt-item>` or `<ntt-list>` is an independent component that fetches its own data. This maps directly to the islands pattern.

### 2.8 Resumability

Instead of re-executing the application on the client (hydration), the framework serializes its state into the HTML and *resumes* execution on the client from where the server left off.

```
  HYDRATION (Traditional):                RESUMABILITY (Qwik-style):

  Server:                                 Server:
    Execute app -> HTML                     Execute app -> HTML + serialized state

  Client:                                 Client:
    Download JS (~30-60KB)                  Download HTML
    Parse JS                                [Interactive immediately]
    Re-execute app                          User clicks button ->
    Reconcile with DOM                        Download handler (~1KB)
    NOW interactive                           Execute handler
                                              [No re-execution of app]
```

**Benchmark numbers:**
- Qwik ships ~**1KB** of JS for a complex page initial load
- React requires ~**30-60KB** just to hydrate
- Qwik 2.0 shows **25-40% faster** metrics across the board vs. React SSR + hydration

**The key insight:** Hydration is "executing the application twice" -- once on the server, once on the client. Resumability eliminates the second execution entirely by serializing enough state that the client can pick up exactly where the server stopped.

**PyBend relevance:** MEDIUM-HIGH. PyBend's schema-driven approach already serializes component state (the JSON Schema carries all rendering instructions). A resumability-like approach could serialize the rendered state into the HTML, with Web Components resuming from the server-rendered DOM rather than re-fetching schemas and re-rendering.

### 2.9 Pattern Comparison Matrix

| Pattern | TTFB | FCP | TTI | JS Payload | Cache | Complexity | SEO |
|---------|------|-----|-----|------------|-------|------------|-----|
| Full SSR | 200-500ms | Excellent | Delayed | Full bundle | Hard | Low | Excellent |
| Streaming SSR | 50-150ms | Excellent | Delayed | Full bundle | Hard | Medium | Excellent |
| SSG | 20-50ms | Best | Depends | Varies | Perfect | Low | Excellent |
| ISR | 20-50ms* | Best* | Depends | Varies | Good | Medium | Excellent |
| PPR | 20-50ms shell | Excellent | Partial | Varies | Hybrid | High | Excellent |
| Islands | 100-300ms | Great | Fast** | Minimal | Good | Medium | Excellent |
| Resumability | 100-300ms | Excellent | Instant | ~1KB init | Hard | High | Excellent |

*\* After initial cache fill*
*\*\* Only island JS needs to load*

---

## 3. SSR and Web Components

**So what?** PyBend's entire frontend is built on vanilla Web Components (`NTTElement`, `NTTItem`, `NTTList`, etc.) using Shadow DOM. Historically, Web Components and SSR were incompatible -- Shadow DOM required JavaScript to create. Declarative Shadow DOM changes this equation entirely, making server-rendered Web Components a viable path for the first time.

### 3.1 The Historical Problem

Web Components use Shadow DOM for encapsulation. Shadow DOM could only be created via JavaScript:

```javascript
// This is the ONLY way Shadow DOM worked before DSD
const shadow = element.attachShadow({ mode: 'open' });
shadow.innerHTML = '<p>Content</p>';
```

This meant the server could not produce Shadow DOM markup. Server-rendered HTML would show an empty custom element until JavaScript loaded and executed -- defeating the purpose of SSR.

### 3.2 Declarative Shadow DOM (DSD) -- The Breakthrough

Declarative Shadow DOM allows Shadow DOM to be expressed in static HTML:

```html
<!-- Server can now produce this HTML directly -->
<ntt-item>
  <template shadowrootmode="open">
    <style>
      .card { border: 1px solid var(--border); padding: 1rem; }
    </style>
    <div class="card">
      <h3>Product Name</h3>
      <p class="price">$29.99</p>
      <p>Product description here...</p>
    </div>
  </template>
</ntt-item>
```

The browser's HTML parser detects `<template shadowrootmode="open">` and immediately creates a Shadow Root -- **no JavaScript required**. The element renders with its styles and content before any JS loads.

**Browser support (as of 2025-2026):**

| Browser | `shadowrootmode` | Version |
|---------|-------------------|---------|
| Chrome | Supported | 111+ (full in 124+) |
| Edge | Supported | 111+ (full in 124+) |
| Safari | Supported | 16.4+ |
| Firefox | Supported | 123+ |

> **Note:** The older `shadowroot` attribute (non-standard, Chrome 90-110) has been superseded by the standardized `shadowrootmode` attribute. All major browsers now support the standard form.

### 3.3 SSR Libraries for Web Components

#### Lit SSR (`@lit-labs/ssr`)

Lit's official SSR package renders Lit components to static HTML in Node.js environments.

**How it works:**
- Renders Lit templates and components to strings/streams
- Produces Declarative Shadow DOM markup
- Does NOT fully emulate browser DOM -- uses Lit's declarative template format for performance
- Supports streaming for low TTFB

**Current status (2025):** Still in Lit Labs (experimental). Lit's own website uses server-rendered Web Components sparingly. The package may receive breaking changes.

```javascript
// Lit SSR example
import { render } from '@lit-labs/ssr';
import { html } from 'lit';

const result = render(html`
  <my-element .data=${productData}></my-element>
`);
// result is an iterable of strings (streamable)
```

**PyBend relevance:** LOW. PyBend uses vanilla Web Components, not Lit. Lit SSR is tightly coupled to Lit's template system.

#### Enhance SSR (`@enhance/ssr`)

Enhance takes a different approach: Web Components are defined as pure functions that return HTML strings. No client-side framework needed.

```javascript
// Enhance component definition
export default function MyElement({ html, state }) {
  const { name, price } = state.attrs;
  return html`
    <div class="card">
      <h3>${name}</h3>
      <p>${price}</p>
    </div>
  `;
}
```

**Key insight:** Enhance treats Web Components as *progressive enhancement*. The server renders full HTML; the client optionally upgrades elements with interactivity. No hydration step.

**PyBend relevance:** MEDIUM. The "render as function that returns HTML" pattern maps well to PyBend's schema-driven approach. The server already knows the schema and data -- it could render the HTML directly.

#### Custom SSR (Build Your Own)

For frameworks like PyBend that use vanilla Web Components, a custom SSR solution is the most natural fit:

```python
# Hypothetical PyBend SSR renderer
def render_ntt_item(schema: dict, data: dict, size: str = 'md') -> str:
    """Server-side equivalent of NTTItem.md() -- renders entity card HTML."""
    props = schema.get('properties', {})
    field_order = schema.get('ui', {}).get('field_order', list(props.keys()))

    fields_html = []
    for field in field_order:
        if field not in data or not props.get(field, {}).get('ui', {}).get('display', True):
            continue
        fields_html.append(f'<div class="field"><label>{field}</label><span>{data[field]}</span></div>')

    return f'''<ntt-item model="{schema['__name__']}" addr="{data.get('$id', '')}">
      <template shadowrootmode="open">
        <link rel="stylesheet" href="/static/components/ntt-item.css">
        <div class="card" data-display="{size}">
          <h3>{data.get('name', '')}</h3>
          {''.join(fields_html)}
        </div>
      </template>
    </ntt-item>'''
```

**PyBend relevance:** HIGH. This approach keeps the Python backend as the single source of truth (consistent with PyBend's philosophy) and requires no Node.js dependency.

### 3.4 The "Light DOM" Alternative

Some projects avoid Shadow DOM entirely for SSR compatibility, rendering into the Light DOM (regular DOM):

```html
<!-- Light DOM approach: no shadow, styles are global -->
<ntt-item>
  <div class="ntt-item card">
    <h3>Product Name</h3>
    <p>$29.99</p>
  </div>
</ntt-item>
```

**Tradeoff:** Simpler SSR, but loses style encapsulation. Global CSS can leak into and out of components.

**For PyBend:** Not recommended. PyBend's components already rely on Shadow DOM encapsulation. Switching to Light DOM would be a breaking architectural change.

### 3.5 Web Components SSR Decision Matrix

| Approach | Node Required | Shadow DOM | Hydration | PyBend Fit |
|----------|---------------|------------|-----------|------------|
| Lit SSR | Yes | Yes (DSD) | Lit-specific | Low |
| Enhance SSR | Yes (or WASM) | Optional | None (progressive) | Medium |
| Custom Python SSR | No | Yes (DSD) | Custom | **High** |
| Light DOM | No | No | Simple | Low (breaking) |
| No SSR (current) | No | Yes | N/A (CSR only) | Current state |

---

## 4. Python Server-Side Rendering Engines

**So what?** If PyBend adds SSR, the rendering happens in Python -- not Node.js. This section evaluates what Python offers for HTML generation, from battle-tested template engines to modern hypermedia patterns. The good news: Python's templating ecosystem is mature, fast, and well-suited to schema-driven rendering.

### 4.1 Jinja2 -- The Standard

Jinja2 is the de facto template engine for Python web frameworks. FastAPI/Starlette include first-class integration.

```python
# FastAPI + Jinja2 integration
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/products")
async def list_products(request: Request):
    products = await Product.list(limit=20)
    schema = Product.schema()
    return templates.TemplateResponse("product_list.html", {
        "request": request,
        "products": products,
        "schema": schema,
    })
```

```html
<!-- templates/product_list.html -->
{% for product in products %}
<ntt-item model="Product" addr="{{ product['$id'] }}">
  <template shadowrootmode="open">
    <div class="card" data-display="md">
      {% for field in schema.ui.field_order %}
        {% if product[field] is defined %}
        <div class="field">
          <label>{{ field | title }}</label>
          <span>{{ product[field] }}</span>
        </div>
        {% endif %}
      {% endfor %}
    </div>
  </template>
</ntt-item>
{% endfor %}
```

**Performance:**
- Jinja2 compiles templates to optimized Python bytecode
- Template rendering: microseconds for simple pages, low milliseconds for complex pages
- Supports async rendering (though Jinja2 docs recommend keeping templates I/O-free)

**PyBend fit:** Good for page-level rendering, but Jinja2 templates would duplicate the rendering logic that already exists in JavaScript components. This creates a maintenance burden: every change to `ntt-item.js` must be mirrored in the Jinja2 template.

### 4.2 HTMX -- Hypermedia as the Engine

HTMX is not a template engine but a philosophy: the server returns HTML fragments, not JSON. The browser swaps them into the page.

```html
<!-- HTMX pattern: server returns HTML, not JSON -->
<div id="product-list"
     hx-get="/products?format=html"
     hx-trigger="load"
     hx-swap="innerHTML">
  Loading...
</div>
```

```python
# Server returns HTML fragment
@app.get("/products", response_class=HTMLResponse)
async def list_products(request: Request, format: str = "json"):
    products = await Product.list(limit=20)
    if format == "html":
        return render_product_list(products)  # Returns HTML string
    return {"data": [p.model_dump(response=True) for p in products]}
```

**Performance benchmarks (FastAPI + HTMX vs. React SPA):**

| Metric | FastAPI + HTMX | React SPA | Improvement |
|--------|---------------|-----------|-------------|
| First Contentful Paint | 300-500ms | 1500-3000ms | 3-6x faster |
| Total page weight | 50-100KB | 1.5-3MB | 15-30x smaller |
| Time to Interactive | ~35ms | ~120ms | 3.4x faster |
| Requests/sec/core | 1,500 | N/A (client) | Server efficiency |

> Source: Multiple benchmarks cited by dev.to and johal.in communities, 2025-2026.

**PyBend fit:** MEDIUM-LOW for core architecture. HTMX replaces the client-side actor/messaging system that PyBend's Web Components rely on. However, HTMX *augmentation* is viable -- specific routes could return HTML fragments alongside the existing JSON API.

### 4.3 Mako -- The Alternative

Mako is Python's other major template engine, used by Reddit and SQLAlchemy docs.

```python
from mako.template import Template

tmpl = Template("""
<div class="product-card">
    <h3>${product['name']}</h3>
    <p class="price">${"${:.2f}".format(product['price'])}</p>
</div>
""")
html = tmpl.render(product=product_data)
```

**Mako vs. Jinja2:**
- Mako allows inline Python expressions (more power, more risk)
- Jinja2 has a restricted sandbox (safer for user-facing templates)
- Performance is comparable
- Jinja2 has far larger ecosystem and community

### 4.4 Custom Python HTML Renderer (Schema-Driven)

The most natural SSR approach for PyBend: a Python module that reads the same JSON Schema the frontend reads, and produces the same HTML the frontend would produce.

```python
# Hypothetical: src/pybend/core/ssr/renderer.py
class SchemaRenderer:
    """Renders entities to HTML using JSON Schema --
    the Python equivalent of NTT.js prototype() + NTTItem.render()."""

    @staticmethod
    def render_entity(schema: dict, data: dict, size: str = 'md') -> str:
        """Render a single entity to HTML with Declarative Shadow DOM."""
        props = schema.get('properties', {})
        ui = schema.get('ui', {})
        field_order = ui.get('field_order', [k for k in props if props[k].get('ui', {}).get('display', True)])

        fields = []
        for field in field_order:
            if field not in data:
                continue
            prop = props.get(field, {})
            if not prop.get('ui', {}).get('display', True):
                continue
            widget = prop.get('ui', {}).get('widget', 'text')
            value = SchemaRenderer._render_value(data[field], widget)
            fields.append(f'<div class="field"><label>{field}</label>{value}</div>')

        model_name = schema.get('__name__', 'Unknown')
        instance_id = data.get('$id', '')

        return f'''<ntt-item model="{model_name}" addr="{instance_id}">
          <template shadowrootmode="open">
            <link rel="stylesheet" href="/static/components/ntt-item.css">
            <div class="card" data-display="{size}">
              {''.join(fields)}
            </div>
          </template>
        </ntt-item>'''

    @staticmethod
    def render_list(schema: dict, items: list, size: str = 'sm') -> str:
        """Render a list of entities."""
        rendered = [SchemaRenderer.render_entity(schema, item, size) for item in items]
        model_name = schema.get('__name__', 'Unknown')
        return f'''<ntt-list model="{model_name}">
          <template shadowrootmode="open">
            <link rel="stylesheet" href="/static/components/ntt-list.css">
            <div class="entity-list">
              {''.join(rendered)}
            </div>
          </template>
        </ntt-list>'''

    @staticmethod
    def _render_value(value, widget: str) -> str:
        if widget == 'currency':
            return f'<span class="currency">${value:.2f}</span>'
        if widget == 'textarea':
            return f'<p>{value}</p>'
        return f'<span>{value}</span>'
```

**Advantages:**
- Single source of truth preserved (schema drives both Python and JS rendering)
- No Node.js dependency
- No template duplication
- Consistent with PyBend's "model is the app" philosophy

**Challenges:**
- Must keep parity with JS rendering logic (two implementations of the same rendering)
- Complex widgets (forms, interactive elements) are harder to SSR

### 4.5 Python Rendering Engine Comparison

| Engine | Speed | DSD Support | Schema-Driven | Maintenance | PyBend Fit |
|--------|-------|-------------|---------------|-------------|------------|
| Jinja2 | Fast (bytecode compiled) | Manual | Requires template mapping | Template sync burden | Medium |
| HTMX pattern | N/A (server returns fragments) | Manual | Possible | Replaces client arch | Low |
| Mako | Fast | Manual | Requires template mapping | Template sync burden | Low |
| Custom renderer | Fast (pure Python) | Native | **Yes** | Must mirror JS logic | **High** |

---

## 5. The HTML-to-Interactive Transition

**So what?** Getting HTML to the screen fast is only half the problem. The critical question is: how long until users can actually *click things*? The gap between "I see the page" (FCP) and "I can use the page" (TTI) is where users lose trust. A button that looks clickable but does nothing for 2 seconds is worse than a loading spinner. This section covers the techniques that bridge that gap.

### 5.1 Traditional Hydration

The server renders HTML. The client downloads JavaScript, re-executes the application, attaches event listeners, and makes the page interactive.

```
Timeline:

  0ms        200ms       500ms       1200ms      2000ms
  |-----------|-----------|-----------|-----------|
  [  TTFB  ]
              [ FCP - user sees content ]
              [   Download JS bundle (30-60KB min)   ]
                          [  Parse + Execute JS  ]
                                      [  Reconcile DOM  ]
                                                  [ TTI ]

  "Uncanny Valley": 500ms - 2000ms
  User sees buttons but they don't work yet.
```

**The problem:** Hydration is executing the application twice -- once on the server (for HTML), once on the client (for interactivity). For large applications, this means 1-3 seconds of "uncanny valley" where the page *looks* interactive but *isn't*.

> **Benchmark:** If hydration takes longer than 2 seconds, users will try to interact with non-functional elements, creating frustration. One study found a 12% conversion rate increase on product pages when TTI dropped to 1.4s through progressive hydration techniques.

### 5.2 Progressive Hydration

Instead of hydrating the entire page at once, hydrate components incrementally -- starting with visible, interactive elements.

```
Traditional Hydration:          Progressive Hydration:

[Hydrate entire page]           [Hydrate header + nav]
                                [Hydrate search bar]
                                [Hydrate product cards]   <-- on scroll
                                [Hydrate footer]          <-- on scroll
                                [Hydrate sidebar]         <-- on interaction
```

**Strategies for triggering hydration:**
1. **On visibility** -- hydrate when the component scrolls into view (`IntersectionObserver`)
2. **On interaction** -- hydrate when the user hovers or clicks
3. **On idle** -- hydrate during `requestIdleCallback`
4. **On media query** -- hydrate only on desktop, not mobile

```javascript
// Progressive hydration example for Web Components
class LazyHydrated extends HTMLElement {
  connectedCallback() {
    // Server-rendered content already visible via DSD
    // Only hydrate on first interaction
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        this.hydrate();
        observer.disconnect();
      }
    });
    observer.observe(this);
  }

  async hydrate() {
    const module = await import(this.getAttribute('module'));
    // Upgrade the element with full interactivity
  }
}
```

### 5.3 Selective Hydration

Only hydrate components that *need* interactivity. Static content remains as plain HTML forever.

```html
<!-- This component has a click handler -> needs hydration -->
<ntt-item data-hydrate="true" model="Product">
  <template shadowrootmode="open">
    <div class="card">
      <h3>Product Name</h3>
      <button>Add to Cart</button>  <!-- Interactive -->
    </div>
  </template>
</ntt-item>

<!-- This component is display-only -> NO hydration needed -->
<ntt-item data-hydrate="false" model="Product">
  <template shadowrootmode="open">
    <div class="card">
      <h3>Product Name</h3>
      <p>$29.99</p>             <!-- Static display -->
    </div>
  </template>
</ntt-item>
```

**PyBend opportunity:** The schema's `access` rules already encode whether a user can edit/delete an entity. If `access.update` resolves to `false` for the current user, the component needs no edit-mode hydration. The server can mark it `data-hydrate="false"` and skip shipping edit-related JavaScript entirely.

### 5.4 Partial Hydration (Islands)

The page is a mix of static HTML and interactive islands. Only islands hydrate.

```
  Page Structure:
  +--------------------------------------------------+
  |  <header> (static HTML, 0 JS)                    |
  +--------------------------------------------------+
  |  <ntt-list model="Product">                       |
  |    +------------------------------------------+   |
  |    | Island: Search/Filter (hydrated, ~5KB JS) |  |
  |    +------------------------------------------+   |
  |    | Product 1 (static HTML, 0 JS)             |  |
  |    | Product 2 (static HTML, 0 JS)             |  |
  |    | Product 3 (static HTML, 0 JS)             |  |
  |    +------------------------------------------+   |
  |    | Island: Load More (hydrated, ~2KB JS)     |  |
  |    +------------------------------------------+   |
  |  </ntt-list>                                      |
  +--------------------------------------------------+
  |  <footer> (static HTML, 0 JS)                     |
  +--------------------------------------------------+

  Total JS shipped: ~7KB (vs. full hydration: ~50KB+)
```

### 5.5 Resumability (Zero-Hydration)

As covered in Section 2.8, Qwik eliminates hydration entirely. The key mechanism:

```html
<!-- Server output with serialized state -->
<button on:click="./chunk-abc.js#handleClick[0]"
        q:id="1">
  Like (42)
</button>

<!-- Qwik's global listener (~1KB) intercepts the click -->
<!-- Downloads chunk-abc.js ONLY when the button is clicked -->
<!-- Executes handleClick with the serialized state -->
<!-- No re-execution of the component tree -->
```

**For PyBend's Web Components**, a similar approach is possible:

```html
<ntt-method method="like" href="/products/1/like">
  <template shadowrootmode="open">
    <button data-action="POST /products/1/like">Like (42)</button>
  </template>
</ntt-method>

<script type="module">
// Minimal global handler (~1KB): intercepts data-action clicks,
// makes fetch() call, updates the DOM
document.addEventListener('click', async (e) => {
  const action = e.target.closest('[data-action]');
  if (!action) return;
  const [method, url] = action.dataset.action.split(' ');
  const res = await fetch(url, { method, headers: {'x-access-token': getToken()} });
  if (res.ok) action.textContent = await res.text();
});
</script>
```

### 5.6 Hydration Strategy Comparison

| Strategy | JS Shipped | TTI | Complexity | Web Components Support |
|----------|-----------|-----|------------|----------------------|
| Full hydration | 30-60KB+ | 1-3s | Low | Good (standard upgrade) |
| Progressive | 30-60KB (lazy) | 0.5-1.5s | Medium | Good (lazy upgrade) |
| Selective | 10-30KB | 0.3-1s | Medium | Good (conditional upgrade) |
| Partial (islands) | 5-15KB | 0.2-0.5s | Medium | **Excellent** (natural fit) |
| Resumability | ~1KB init | <100ms | High | Possible (custom impl) |

---

## 6. Security Considerations

**So what?** SSR introduces an entire category of security risks that pure CSR applications avoid. When the server generates HTML from user data, every unescaped variable is a potential XSS vector. For PyBend, where model data flows directly into rendered HTML, getting this wrong means stored XSS from any entity field.

### 6.1 XSS in Server-Rendered HTML

**The core risk:** SSR templates interpolate data into HTML. If that data contains malicious scripts and is not escaped, the server *pre-injects the attack* into the page.

```python
# VULNERABLE: raw interpolation
def render_product(product):
    return f'<h3>{product["name"]}</h3>'  # If name = '<script>alert("xss")</script>'
                                           # Server sends the attack PRE-RENDERED

# SAFE: escaped output
from markupsafe import escape
def render_product(product):
    return f'<h3>{escape(product["name"])}</h3>'
```

**SSR-specific danger:** In a CSR (client-side rendering) application, XSS requires the attacker to inject content that the *client* framework fails to escape. In SSR, the attack is baked into the initial HTML response -- it executes before any JavaScript loads, before any CSP nonce is checked, before any client-side sanitizer runs.

**Jinja2's auto-escaping:**
```python
# Jinja2 auto-escapes by default in HTML mode
env = Environment(autoescape=True)
# {{ product.name }} -> automatically escaped
# {{ product.name | safe }} -> DANGEROUS: bypasses escaping
```

> **Rule:** Never use `| safe` or `Markup()` on user-supplied data. If you need raw HTML (e.g., rich text fields), sanitize it server-side with a library like `bleach` or `nh3` before marking it safe.

### 6.2 Template Injection

Server-Side Template Injection (SSTI) occurs when user input is treated as template code:

```python
# VULNERABLE: user input becomes template
template_string = f"Hello {user_input}"  # If user_input = "{{ config }}"
Template(template_string).render()        # Leaks server config!

# SAFE: user input is data, not template
Template("Hello {{ name }}").render(name=user_input)
```

**PyBend mitigation:** PyBend's schema-driven approach naturally separates template structure (defined by the schema) from data (provided by the model). The template structure is developer-defined; only data values are interpolated. This is inherently safer than ad-hoc template construction.

### 6.3 Content Security Policy (CSP) for SSR

CSP headers tell the browser which resources are allowed to execute. SSR has unique CSP considerations:

```
Strict CSP for SSR:

Content-Security-Policy:
  default-src 'self';
  script-src 'nonce-{random}' 'strict-dynamic';
  style-src 'self' 'unsafe-inline';      # Shadow DOM styles need inline
  img-src 'self' data:;
  connect-src 'self';
  base-uri 'self';
  form-action 'self';
```

**SSR-specific CSP challenges:**

| Challenge | Description | Mitigation |
|-----------|-------------|------------|
| Nonce rotation | Every SSR response needs a unique nonce | Generate per-request in middleware |
| Inline styles | Shadow DOM `<style>` tags are inline | Use `'unsafe-inline'` for style-src (acceptable) or use `<link>` |
| Dynamic scripts | SSR may inject `<script>` tags | Use nonce-based script-src, never `'unsafe-inline'` for scripts |
| Streaming + nonces | Nonce must be known before first byte | Generate nonce in middleware, pass to template context |

```python
# FastAPI middleware for CSP nonces
import secrets

@app.middleware("http")
async def csp_middleware(request: Request, call_next):
    nonce = secrets.token_urlsafe(16)
    request.state.csp_nonce = nonce
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; "
        f"script-src 'nonce-{nonce}' 'strict-dynamic'; "
        f"style-src 'self' 'unsafe-inline'; "
        f"connect-src 'self'"
    )
    return response
```

### 6.4 Declarative Shadow DOM Security

DSD introduces a consideration: the `<template shadowrootmode="open">` element is parsed by the HTML parser before any JavaScript runs. This means:

1. **Attacker-controlled DSD:** If an attacker can inject `<template shadowrootmode="open">` into your page, they can create Shadow Roots on arbitrary elements, potentially hiding malicious content or overriding legitimate shadow content.

2. **Mitigation:** Sanitize user input to strip `<template>` elements with `shadowrootmode` attributes. Standard HTML sanitizers should handle this, but verify.

### 6.5 Security Checklist for PyBend SSR

```
[ ] All user data escaped before HTML interpolation (use markupsafe or Jinja2 autoescape)
[ ] No | safe filter on user-controlled data
[ ] No Template() construction from user input (SSTI prevention)
[ ] CSP headers with per-request nonces for script-src
[ ] DSD-aware sanitization (strip shadowrootmode from user content)
[ ] CSRF tokens in SSR-rendered forms
[ ] Sensitive data (tokens, passwords) never rendered into HTML
[ ] Rate limiting on SSR endpoints (server render is CPU work)
```

---

## 7. Performance Characteristics

**So what?** The three metrics that matter -- TTFB (when the first byte arrives), FCP (when the user sees content), and TTI (when the user can interact) -- behave very differently across SSR approaches. The right choice depends on your pages: a product listing benefits from streaming SSR; an interactive dashboard benefits from islands; a marketing page benefits from SSG.

### 7.1 Metric Definitions

```
  Browser receives            User sees               User can
  first byte                  content                  interact
  |                           |                        |
  v                           v                        v
  TTFB                        FCP                      TTI
  |                           |                        |
  |<-- Network + server -->|  |                        |
  |    render time         |  |<-- Parse + paint -->|  |
  |                           |                     |  |
  |                           |                     |  |<-- JS download +
  |                           |                     |  |    parse + hydrate
  |                           |                     |  |
  [=========================================================================================]
  0ms         100ms      300ms      500ms      1000ms     1500ms     2000ms
```

### 7.2 Framework SSR Benchmark Comparison

Data from Enterspeed's benchmark of 6 JS frameworks (2024-2025), measuring identical content:

| Framework | FCP | TTI | Approach |
|-----------|-----|-----|----------|
| Astro | 0.8s | 0.9s | Islands |
| SvelteKit | 0.9s | 1.0s | Selective hydration |
| Next.js | 0.9s | 1.2s | Full hydration / RSC |
| Nuxt.js | 1.1s | 1.4s | Full hydration |
| Remix | 1.0s | 1.2s | Full hydration |
| Gatsby | 1.0s | 1.3s | SSG + hydration |

**Python-specific benchmarks (FastAPI + HTMX):**

| Metric | FastAPI + SSR | React CSR | Delta |
|--------|-------------|-----------|-------|
| FCP | 300-500ms | 1500-3000ms | **3-6x faster** |
| TTI | ~335ms | ~1620ms | **~5x faster** |
| Page weight | 50-100KB | 1.5-3MB | **15-30x smaller** |
| Server throughput | 1,500 req/s/core | N/A | Efficient |

### 7.3 Rendering Approach Performance Profile

```
                    TTFB        FCP         TTI
                    |           |           |
  SSG + CDN         [==]        [===]       [========]
                    20-50ms     80-150ms    depends on JS

  Full SSR          [========]  [=========] [=================]
                    200-500ms   300-600ms   1000-2500ms

  Streaming SSR     [====]      [======]    [=================]
                    50-150ms    200-400ms   1000-2500ms

  Islands           [========]  [=========] [==========]
                    200-500ms   300-600ms   400-800ms

  Resumability      [========]  [=========] [=========]
                    200-500ms   300-600ms   350-650ms

  PyBend (current)  [==]        [========================================]
  (Pure CSR)        20-50ms*    1500-3000ms (waits for schema + data fetch)

  * Static HTML shell served from filesystem
```

### 7.4 The PyBend Performance Gap

PyBend's current rendering flow:

```
  0ms     50ms    200ms   400ms   800ms   1200ms  1600ms  2000ms
  |       |       |       |       |       |       |       |
  [HTML]  [JS modules load                ]
          [                               ]
          [                 Schema fetch   ]
          [                               [Data fetch        ]
          [                                        [Render   ]
                                                             ^ FCP
```

With SSR, the flow would be:

```
  0ms     50ms    200ms   400ms   800ms
  |       |       |       |       |
  [HTML with server-rendered content]
          ^ FCP (3-4x faster)
          [JS modules load (background)]
          [         Hydrate on interaction]
                    ^ TTI (selective)
```

**Estimated improvement for PyBend:**
- FCP: from ~1500-2000ms to ~300-500ms (3-4x improvement)
- TTI for display-only pages: from ~2000ms to ~300ms (6x improvement)
- TTI for interactive pages: from ~2000ms to ~800ms (2.5x improvement)

---

## 8. DevOps Implications

**So what?** SSR shifts compute from the client to the server. Every page view now costs CPU cycles, memory, and latency on your infrastructure. This section covers how to mitigate that cost through caching, edge rendering, and smart architecture decisions.

### 8.1 Caching Strategies

SSR caching operates at multiple layers:

```
  Client                CDN Edge            Origin Server         Database
    |                     |                     |                    |
    |--- GET /products -->|                     |                    |
    |                     |-- Cache hit? ------>|                    |
    |                     |   YES: serve cached |                    |
    |                     |   NO: forward       |                    |
    |                     |                     |--- Query --------->|
    |                     |                     |<-- Data -----------|
    |                     |                     |-- Render HTML      |
    |                     |<-- HTML + headers --|                    |
    |                     |   Cache response    |                    |
    |<-- HTML ------------|                     |                    |
```

**Cache-Control headers for SSR:**

```python
# Static content (SSG-like): cache aggressively
Cache-Control: public, max-age=31536000, immutable

# Dynamic content (SSR): short cache + background revalidation
Cache-Control: public, s-maxage=60, stale-while-revalidate=300

# Personalized content: no shared cache
Cache-Control: private, no-cache

# Schema endpoints (PyBend): cache until server restart
Cache-Control: public, max-age=3600, stale-while-revalidate=86400
```

**PyBend-specific caching opportunities:**

| Content Type | Cache Strategy | TTL | Rationale |
|-------------|---------------|-----|-----------|
| Schema responses (`GET /Product`) | CDN + browser | 1 hour | Schema changes only on deploy |
| List pages (public) | CDN edge | 60s + SWR 5min | Stale-while-revalidate |
| Detail pages (public) | CDN edge | 60s + SWR 5min | Entity changes are infrequent |
| Personalized views | No shared cache | 0 | User-specific access rules |
| Static assets (JS/CSS) | CDN + browser | Immutable | Fingerprinted filenames |

### 8.2 CDN Edge Rendering

Modern CDNs execute code at edge locations (Points of Presence), reducing latency by rendering closer to users.

```
  Traditional SSR:                    Edge SSR:

  User (Tokyo)                        User (Tokyo)
    |                                   |
    |--- 200ms RTT --->                 |--- 5ms RTT --->
    |   Origin (US-East)                |   CDN Edge (Tokyo)
    |                                   |
    |   Server render: 100ms            |   Edge render: 100ms
    |                                   |
    |<-- 200ms RTT ---                  |<-- 5ms RTT ---
    |                                   |
    Total TTFB: ~500ms                  Total TTFB: ~110ms
```

**Edge SSR performance benchmarks:**

| Platform | Warm TTFB | Cold Start | Runtime |
|----------|-----------|------------|---------|
| Cloudflare Workers | 37-60ms | <5ms | V8 isolates |
| Vercel Edge Functions | 40-80ms | 10-25ms | V8 isolates |
| AWS Lambda@Edge | 50-100ms | 60-250ms | Node.js / Python |
| AWS CloudFront Functions | 10-30ms | <1ms | JS only, limited |

**PyBend consideration:** Edge rendering requires the rendering logic to run at the edge. For Python-based SSR, this limits options:
- **Cloudflare Workers / Vercel Edge:** JavaScript only (no Python)
- **AWS Lambda@Edge:** Supports Python, but cold starts of 60-250ms
- **Alternative:** Cache SSR output at the CDN; render at origin

**Recommended approach for PyBend:** Origin-based SSR with aggressive CDN caching (ISR pattern). The schema rarely changes; entity data changes infrequently. Cache SSR output at the CDN with `stale-while-revalidate`.

### 8.3 Serverless SSR

Running SSR in serverless functions (AWS Lambda, Google Cloud Functions):

**Advantages:**
- Scale to zero when idle (cost efficiency)
- Auto-scale on traffic spikes
- No server management

**Cold start problem:**

```
  First request after idle period:

  0ms          100ms        500ms       1000ms      1500ms
  |             |            |           |           |
  [Container    [Python      [Import     [Render     [Response]
   provision]    startup]     app/deps]   HTML]

  Cold start: 500-1500ms (Python)
  Warm request: 50-200ms
```

**Cold start mitigation:**
1. **Provisioned concurrency** (AWS Lambda): Pre-warm N instances. Cost: $0.0000097/GB-second
2. **Periodic warming** (cron ping): Keep function warm with scheduled invocations
3. **Minimize dependencies**: Smaller deployment package = faster cold start
4. **Use response streaming**: Start sending HTML before full render completes

### 8.4 Infrastructure Decision Matrix

| Factor | Origin SSR | Edge SSR | Serverless SSR | CDN + ISR |
|--------|-----------|----------|---------------|-----------|
| Latency (global) | 100-500ms | 30-100ms | 50-300ms | 20-60ms cached |
| Cold starts | None | <5ms | 60-1500ms | None |
| Python support | Full | Limited | Full | N/A (cache) |
| Cost at scale | Fixed | Per-request | Per-request | Per-request (low) |
| Complexity | Low | High | Medium | Low |
| PyBend fit | **Best** | Poor | Good | **Best** |

---

## 9. Testing Strategies

**So what?** SSR introduces a new class of bugs: hydration mismatches (server HTML differs from client render), template injection, missing escaping, broken streaming. Your test suite must cover the server render, the client upgrade, and the transition between them.

### 9.1 Testing Layers for SSR

```
  +---------------------------------------------------+
  |  Layer 5: End-to-End (Playwright/Cypress)          |
  |  Full browser, verify FCP, TTI, visual correctness |
  +---------------------------------------------------+
  |  Layer 4: Hydration Mismatch Tests                 |
  |  Compare server HTML vs. client-rendered HTML       |
  +---------------------------------------------------+
  |  Layer 3: Integration (API + Render)               |
  |  Verify routes return correct HTML for given data   |
  +---------------------------------------------------+
  |  Layer 2: Component Render Tests                   |
  |  Unit-test individual component SSR output          |
  +---------------------------------------------------+
  |  Layer 1: Schema Render Tests                      |
  |  Verify schema -> HTML mapping is correct           |
  +---------------------------------------------------+
```

### 9.2 Unit Tests: Schema-to-HTML Rendering

```python
# test_ssr_renderer.py
import pytest
from pybend.core.ssr.renderer import SchemaRenderer

def test_render_entity_basic():
    schema = {
        '__name__': 'Product',
        'properties': {
            'name': {'type': 'string', 'ui': {'display': True}},
            'price': {'type': 'number', 'ui': {'widget': 'currency', 'display': True}},
            'id': {'type': 'integer', 'ui': {'display': False}},
        },
        'ui': {'field_order': ['name', 'price']}
    }
    data = {'name': 'Widget', 'price': 29.99, 'id': 1, '$id': '/products/1'}

    html = SchemaRenderer.render_entity(schema, data, size='md')

    assert '<ntt-item model="Product"' in html
    assert 'shadowrootmode="open"' in html
    assert 'Widget' in html
    assert '$29.99' in html
    assert 'id' not in html.split('shadowrootmode')[1]  # id field hidden

def test_render_entity_escapes_xss():
    schema = {
        '__name__': 'Product',
        'properties': {'name': {'type': 'string', 'ui': {'display': True}}},
        'ui': {'field_order': ['name']}
    }
    data = {'name': '<script>alert("xss")</script>'}

    html = SchemaRenderer.render_entity(schema, data)

    assert '<script>' not in html
    assert '&lt;script&gt;' in html
```

### 9.3 Integration Tests: Route-Level SSR

```python
# test_ssr_routes.py
from fastapi.testclient import TestClient

def test_product_list_ssr(client: TestClient, seeded_db):
    response = client.get("/products?format=html", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<ntt-list model="Product">' in response.text
    assert 'shadowrootmode="open"' in response.text
    # Verify all seeded products appear
    assert 'Widget A' in response.text
    assert 'Widget B' in response.text

def test_ssr_response_includes_csp_nonce(client: TestClient):
    response = client.get("/products?format=html")

    csp = response.headers.get("content-security-policy", "")
    assert "nonce-" in csp
    # Verify the nonce in the header matches nonce in the HTML
    import re
    header_nonce = re.search(r"nonce-([A-Za-z0-9_-]+)", csp).group(1)
    html_nonce = re.search(r'nonce="([A-Za-z0-9_-]+)"', response.text)
    assert html_nonce and html_nonce.group(1) == header_nonce
```

### 9.4 Hydration Mismatch Tests

The most SSR-specific test: verify that server-rendered HTML matches what the client would produce.

```python
# Using Playwright to compare server and client renders
# test_hydration_parity.py

async def test_no_hydration_mismatch(page):
    """Verify server HTML matches client-rendered HTML after hydration."""
    # Capture server-rendered HTML before JS runs
    await page.route("**/*.js", lambda route: route.abort())  # Block JS
    await page.goto("/products?format=html")
    server_html = await page.content()

    # Now allow JS and let client hydrate
    await page.unroute("**/*.js")
    await page.goto("/products?format=html")
    await page.wait_for_selector("ntt-item[hydrated]")
    client_html = await page.content()

    # Compare structural equivalence (ignore whitespace, attribute order)
    assert normalize_html(server_html) == normalize_html(client_html)
```

### 9.5 Performance Tests

```python
# test_ssr_performance.py
import time

def test_ssr_ttfb_under_threshold(client: TestClient, seeded_db):
    """TTFB for SSR should be under 500ms for a list of 20 items."""
    start = time.perf_counter()
    response = client.get("/products?format=html&limit=20")
    ttfb = (time.perf_counter() - start) * 1000

    assert response.status_code == 200
    assert ttfb < 500, f"TTFB was {ttfb:.0f}ms, expected < 500ms"

def test_ssr_streaming_sends_head_fast(client: TestClient):
    """Streaming SSR should send the first chunk within 100ms."""
    import httpx

    start = time.perf_counter()
    with httpx.stream("GET", "http://localhost:5000/products?format=html&stream=true") as r:
        first_chunk = next(r.iter_bytes())
        first_chunk_time = (time.perf_counter() - start) * 1000

    assert first_chunk_time < 100, f"First chunk took {first_chunk_time:.0f}ms"
    assert b'<head>' in first_chunk or b'<html>' in first_chunk
```

### 9.6 Security Tests

```python
def test_ssr_escapes_stored_xss(client: TestClient, auth_token):
    """Malicious product name must be escaped in SSR output."""
    # Create product with XSS payload
    client.post("/products", json={
        "name": '<img src=x onerror="alert(1)">',
        "price": 10.0
    }, headers={"x-access-token": auth_token})

    response = client.get("/products?format=html")
    assert '<img src=x' not in response.text
    assert '&lt;img' in response.text

def test_ssr_no_template_injection(client: TestClient, auth_token):
    """Jinja2 syntax in data must not execute."""
    client.post("/products", json={
        "name": "{{ config }}",
        "price": 10.0
    }, headers={"x-access-token": auth_token})

    response = client.get("/products?format=html")
    assert "{{ config }}" in response.text or "&lbrace;" in response.text
    assert "SECRET" not in response.text
```

### 9.7 Test Strategy Matrix

| Test Type | What It Catches | Tool | Frequency |
|-----------|----------------|------|-----------|
| Schema render unit | Wrong HTML for schema | pytest | Every commit |
| XSS/injection | Security vulnerabilities | pytest | Every commit |
| Route integration | Wrong response format/status | pytest + TestClient | Every commit |
| Hydration mismatch | Server/client divergence | Playwright | Nightly |
| Performance (TTFB) | Regression in render time | pytest + timing | Nightly |
| Streaming correctness | Broken chunked responses | httpx streaming | Weekly |
| Visual regression | Layout/style differences | Playwright screenshots | PR gate |

---

## 10. PyBend-Specific Analysis

**So what?** PyBend is not a typical web application. Its schema-driven architecture means the rendering logic is *derived* from the model, not hand-written. This creates a unique opportunity: SSR can be implemented as a schema renderer -- a Python function that reads the same JSON Schema the frontend reads and produces identical HTML. No template duplication, no framework mismatch, no maintenance divergence.

### 10.1 Current Architecture (CSR Only)

```
  Current PyBend Request Flow:

  Browser                    FastAPI                    SQLite
    |                          |                          |
    |-- GET /static/matrix.html (static file, instant)   |
    |-- GET /static/core/NTT.js (+ all JS modules)      |
    |-- GET /Product (schema)-->|                         |
    |<-- JSON Schema -----------|                         |
    |   [NTT.SCHEMA() -> prototype() -> DynamicClass]    |
    |-- GET /products --------->|-- SELECT * FROM... ---->|
    |<-- JSON data -------------|<-- rows ----------------|
    |   [Create instances, render ntt-item components]    |
    |   [User finally sees content]                       |
    |                                                     |
    Timeline: ~1500-2000ms to FCP
```

### 10.2 Proposed SSR Architecture

```
  Proposed PyBend SSR Flow:

  Browser                    FastAPI + SSR Renderer       SQLite
    |                          |                            |
    |-- GET /products -------->|                            |
    |   Accept: text/html      |-- Product.schema() ------>|
    |                          |   (cached in memory)       |
    |                          |-- Product.list(limit=20) ->|
    |                          |<-- rows -------------------|
    |                          |                            |
    |                          |  [SchemaRenderer.render_list()]
    |                          |  Schema + data -> HTML with DSD
    |                          |                            |
    |<-- Full HTML page -------|                            |
    |   [Browser paints immediately]                        |
    |   FCP: ~300-500ms                                    |
    |                                                       |
    |-- GET /static/core/NTT.js (background, non-blocking) |
    |   [Web Components upgrade, attach event listeners]    |
    |   TTI: ~800ms                                        |
```

### 10.3 Content Negotiation Strategy

The same endpoints serve JSON (for the existing Web Component client) and HTML (for SSR):

```python
# In routes_fastapi.py -- content negotiation
async def list_instances(request: Request, limit: int = 20, offset: int = 0):
    # ... existing auth + query logic ...
    instances = model_class.list(limit=limit, offset=offset)

    if "text/html" in request.headers.get("accept", ""):
        # SSR path: return rendered HTML
        schema = model_class.schema()
        html = SchemaRenderer.render_list(schema, [_serialize(i) for i in instances])
        return HTMLResponse(html)

    # JSON path: existing behavior
    return {
        "data": [_serialize(i) for i in instances],
        "meta": {"total": total, "limit": limit, "offset": offset, "has_more": has_more}
    }
```

### 10.4 Schema-Driven SSR: The Natural Fit

PyBend's schema already carries everything needed to render:

```
  JSON Schema                         SSR HTML Output

  properties.name.type: "string"  ->  <input type="text">
  properties.name.ui.widget       ->  <textarea> / <input> / <span>
  properties.name.ui.placeholder  ->  placeholder="..."
  properties.name.ui.display      ->  [skip field if false]
  ui.field_order                  ->  [render fields in this sequence]
  ui.groups                       ->  <fieldset> wrappers
  access.update                   ->  [show/hide edit button]
  access.delete                   ->  [show/hide delete button]
  methods                         ->  <button> elements for each method
```

This means the SSR renderer does NOT need to be told how to render -- it reads the schema and derives the rendering, exactly like the frontend does today. **The schema is the single source of truth for both renders.**

### 10.5 Recommended Implementation Phases

```
  Phase 1: Schema Renderer (2-3 weeks)
  ├── Python module: src/pybend/core/ssr/renderer.py
  ├── Reads JSON Schema, produces HTML with DSD
  ├── Supports: entity display (md size), list display
  ├── Full HTML escaping (markupsafe)
  └── Unit tests for all schema property types

  Phase 2: Route Integration (1-2 weeks)
  ├── Content negotiation on existing routes
  ├── Accept: text/html -> SSR, else JSON
  ├── CSP nonce middleware
  ├── Cache-Control headers
  └── Integration tests

  Phase 3: Client Upgrade Path (2-3 weeks)
  ├── Web Components detect DSD-rendered content
  ├── Skip initial render if DSD content exists
  ├── Attach event listeners to existing DOM
  ├── Selective hydration based on access rules
  └── Hydration mismatch tests (Playwright)

  Phase 4: Streaming + Caching (1-2 weeks)
  ├── StreamingResponse for list pages
  ├── CDN cache headers (stale-while-revalidate)
  ├── Schema response caching
  └── Performance benchmarks + regression tests
```

### 10.6 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Server/client render divergence | High | Medium | Hydration mismatch CI tests |
| XSS in server-rendered content | Medium | Critical | Auto-escaping + security tests |
| Performance regression (server load) | Medium | Medium | Caching + load testing |
| DSD browser incompatibility | Low | High | Polyfill for older browsers |
| Maintenance burden (two renderers) | High | Medium | Schema-driven approach minimizes drift |
| Breaking existing CSR clients | Low | High | Content negotiation preserves JSON API |

---

## 11. Sources

1. [Making Sense of Web Rendering Patterns (SSR, CSR, Static, Islands) -- LogRocket](https://blog.logrocket.com/making-sense-of-web-rendering)
2. [Advanced SSR 2025: Selective Hydration, RSCs, and Edge Rendering](https://blog.madrigan.com/en/blog/202601070853/)
3. [Islands Architecture -- patterns.dev](https://www.patterns.dev/vanilla/islands-architecture/)
4. [Web Components and SSR - 2024 Edition -- DEV Community](https://dev.to/stuffbreaker/web-components-and-ssr-2024-edition-1nel)
5. [Server-side rendering (SSR) -- Lit Documentation](https://lit.dev/docs/ssr/overview/)
6. [Declarative Shadow DOM -- web.dev](https://web.dev/articles/declarative-shadow-dom)
7. [Enhance vs. Lit vs. WebC -- How to Server-Render a Web Component](https://www.spicyweb.dev/web-components-ssr-node/)
8. [Lightweight Python Stack: FastAPI + HTMX + Jinja2 -- DEV Community](https://dev.to/rerere_l_f165d08cdc06148/lightweight-python-stack-for-modern-frontend-fastapi-htmx-jinja2-1f19)
9. [FastHX -- Declarative SSR for FastAPI with HTMX Support](https://github.com/volfpeter/fasthx)
10. [SSR vs CSR: Hydration Performance Compared -- SearchX](https://searchxpro.com/ssr-vs-csr-hydration-performance-compared/)
11. [We Measured the SSR Performance of 6 JS Frameworks -- Enterspeed](https://www.enterspeed.com/blog/we-measured-the-ssr-performance-of-6-js-frameworks-heres-what-we-found)
12. [Progressive Hydration Explained: The Future of Web Performance](https://devtechinsights.com/progressive-hydration-web-performance-2025/)
13. [Streaming SSR: Unlocking Faster TTFB and TTI -- CSTech](https://medium.com/cstech/server-side-rendering-evolved-unlocking-faster-ttfb-and-tti-with-streaming-ssr-800735e37bad)
14. [Resumability vs Hydration -- Builder.io](https://www.builder.io/blog/resumability-vs-hydration)
15. [JavaScript on Demand: How Qwik Differs From React Hydration -- The New Stack](https://thenewstack.io/javascript-on-demand-how-qwik-differs-from-react-hydration/)
16. [Angular vs Qwik vs SolidJS in 2025: Speed and DX Comparison](https://metadesignsolutions.com/angular-vs-qwik-vs-solidjs-in-2025-the-speed-dx-comparison-resumability-ssr-hydration-techniques/)
17. [Partial Prerendering with Next.js -- Vercel](https://vercel.com/blog/partial-prerendering-with-next-js-creating-a-new-default-rendering-model)
18. [Mitigate XSS with Strict CSP -- web.dev](https://web.dev/articles/strict-csp)
19. [Content Security Policy (CSP) -- MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP)
20. [OWASP Content Security Policy Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
21. [Edge vs SSR vs SSG: Real Performance Numbers -- Medium](https://medium.com/better-dev-nextjs-react/edge-vs-ssr-vs-ssg-2025-performance-benchmarks-ttfb-data-meta-description-7b508c572b5f)
22. [Edge Functions vs Serverless: 2025 Performance Battle -- byteiota](https://byteiota.com/edge-functions-vs-serverless-the-2025-performance-battle/)
23. [Improve TTFB and UX with HTTP Streaming -- Web Performance Calendar 2025](https://calendar.perfplanet.com/2025/improve-ttfb-and-ux-with-http-streaming/)
24. [Declarative Shadow DOM -- Can I Use](https://caniuse.com/declarative-shadow-dom)
25. [The Quest for SSR with Web Components: A Stencil Developer's Journey -- Ionic Blog](https://ionic.io/blog/the-quest-for-ssr-with-web-components-a-stencil-developers-journey)
26. [Implementing Your Own SSR Server for Web Components -- Yonatan Kra](https://yonatankra.com/implementing-your-own-ssr-server-for-web-components/)
27. [SSR 2025: Selective Hydration, Streaming, and Edge for Maximum Performance](https://blog.madrigan.com/en/blog/202512041544/)
28. [Server-Side Rendering (SSR) -- The Ultimate Guide -- DebugBear](https://www.debugbear.com/blog/server-side-rendering)
29. [Serverless CDN Solutions: Edge Computing Performance 2025 -- LXD CDN](https://lxdcdn.net/serverless-cdn-solutions/)
30. [HTMX FastAPI Patterns: Hypermedia-Driven SPAs 2025](https://johal.in/htmx-fastapi-patterns-hypermedia-driven-single-page-applications-2025/)

---

*Document generated 2026-02-25. Performance benchmarks reflect published data from 2024-2026. Specific numbers vary by hardware, network conditions, and application complexity.*
