# Technical Deep Dive: Fully Static Site Generation from a Schema-Driven Python Framework

**Date:** 2026-02-25
**Audience:** Technical CEO + Engineering Team
**Scope:** Architecture, implementation patterns, and deployment strategies for generating a zero-runtime static site from PyBend model definitions and database content.

---

## Table of Contents

1. [How Static Site Generators Work Internally](#1-how-static-site-generators-work-internally)
2. [Python-Based Static Generation Landscape](#2-python-based-static-generation-landscape)
3. [Schema-to-HTML: Template-Free Rendering from JSON Schema](#3-schema-to-html-template-free-rendering-from-json-schema)
4. [CSS Generation Strategies](#4-css-generation-strategies)
5. [Near-Zero JavaScript Patterns](#5-near-zero-javascript-patterns)
6. [Progressive Enhancement: Identifying the JS Boundary](#6-progressive-enhancement-identifying-the-js-boundary)
7. [Build Pipeline Design](#7-build-pipeline-design)
8. [Output Structure and URL Conventions](#8-output-structure-and-url-conventions)
9. [Deployment Targets](#9-deployment-targets)
10. [Performance Baselines](#10-performance-baselines)
11. [Architecture Recommendation for PyBend](#11-architecture-recommendation-for-pybend)
12. [Sources](#sources)

---

## 1. How Static Site Generators Work Internally

Every static site generator, regardless of language or ecosystem, follows a single core pipeline:

```
 Data Sources         Template Engine        Output Files         Deploy Target
 +-----------+       +---------------+      +--------------+     +-------------+
 | Markdown  |       |               |      |              |     |             |
 | Database  | ----> | Jinja2 / EJS  | ---> | index.html   | --> | CDN / S3    |
 | JSON/YAML |       | Handlebars    |      | products/    |     | Netlify     |
 | API calls |       | Liquid        |      |   1.html     |     | GH Pages    |
 | JSON Schema|      |               |      | styles.css   |     |             |
 +-----------+       +---------------+      +--------------+     +-------------+
       |                    |                      |
   [Collect]           [Transform]            [Emit + Hash]
```

### Phase 1: Collection

The generator reads all input data. For content-oriented generators (Pelican, Hugo, Jekyll), this means parsing Markdown files with YAML frontmatter. For application-oriented generators (Frozen-Flask, custom pipelines), this means querying a database or calling API endpoints.

### Phase 2: Transformation

Data is combined with templates. The template engine resolves inheritance (`{% extends "base.html" %}`), loops (`{% for product in products %}`), and conditionals. This phase is pure computation -- no I/O.

### Phase 3: Emission

Rendered HTML is written to disk. Assets (CSS, images, fonts) are copied or processed (minified, fingerprinted). A manifest may be generated mapping source files to output paths.

### Phase 4: Deployment

The output directory is uploaded to a hosting target. Because files are static, any HTTP server works. No runtime, no database, no application server.

**Key insight for PyBend:** Phases 1 and 2 are where the work lies. PyBend already has Phase 1 solved -- `StorableMixin.list()` returns all entities, and `ProtoModel.schema()` returns the complete JSON Schema. The challenge is Phase 2: converting schema + data into HTML without hand-written templates.

---

## 2. Python-Based Static Generation Landscape

### Comparison of Python SSG Approaches

| Tool | Input | Template Engine | Pipeline | Use Case |
|------|-------|----------------|----------|----------|
| **Pelican** | Markdown + RST | Jinja2 | Content files -> themed HTML | Blogs, documentation |
| **Nikola** | Markdown + RST + Jupyter | Mako / Jinja2 | Content files -> themed HTML | Blogs with code notebooks |
| **Sphinx** | RST + autodoc | Jinja2 (custom) | Directive tree -> HTML/PDF/ePub | Technical documentation |
| **Frozen-Flask** | Flask routes | Jinja2 (via Flask) | WSGI simulation -> static files | Freezing existing Flask apps |
| **staticjinja** | Jinja2 templates | Jinja2 | Direct template render | Minimal sites, < 500 LOC |
| **Custom Jinja2** | Any Python data | Jinja2 | Full control | Schema-driven generation |

### Frozen-Flask: The Closest Analogy

Frozen-Flask is architecturally the closest to what PyBend needs. It works by simulating WSGI requests against a running Flask application and writing the responses to files:

```python
from flask_frozen import Freezer

app = create_flask_app()
freezer = Freezer(app)

@freezer.register_generator
def product_detail():
    for product in Product.list():
        yield {'id': product.id}

freezer.freeze()  # -> build/products/1/index.html, build/products/2/index.html, ...
```

**How it works internally:**

1. Discovers all URL rules from the Flask app
2. Calls registered generator functions to enumerate dynamic URLs
3. Makes internal WSGI requests (no network) for each URL
4. Writes response body to `build/{path}/index.html`

**Limitation for PyBend:** Frozen-Flask assumes you already have Flask routes that return rendered HTML. PyBend's routes return JSON. The generation layer must sit between the data layer and the output -- it must *consume* the schema and data, not *freeze* existing HTML routes.

### Custom Jinja2 Pipeline: The Right Approach

For PyBend, a custom Jinja2 pipeline provides full control over the schema-to-HTML transformation:

```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates/'))

def generate_site(models, output_dir):
    for model_class in models:
        schema = model_class.schema()
        items = model_class.list()

        # List page
        tmpl = env.get_template('list.html')
        html = tmpl.render(schema=schema, items=items)
        write(f"{output_dir}/{schema['__tablename__']}/index.html", html)

        # Detail pages
        tmpl = env.get_template('detail.html')
        for item in items:
            html = tmpl.render(schema=schema, item=item.model_dump())
            write(f"{output_dir}/{schema['__tablename__']}/{item.id}/index.html", html)
```

This is simple, but it still requires hand-written templates. The next section eliminates that requirement.

---

## 3. Schema-to-HTML: Template-Free Rendering from JSON Schema

This is the core technical challenge and the highest-leverage capability. PyBend's JSON Schema carries everything the frontend needs: field types, UI hints, display order, groups, access rules, method signatures. A static generator should consume this schema identically to how `form.js` consumes it at runtime -- but emit static HTML instead of DOM mutations.

### Architecture: Schema-Driven HTML Emitter

```
ProtoModel.schema()          StorableMixin.list()
       |                            |
       v                            v
  JSON Schema                  Entity Data
  (properties,                 (model_dump()
   ui, access,                  for each
   methods, $defs)              instance)
       |                            |
       +----------+    +------------+
                  |    |
                  v    v
          StaticRenderer(schema, data)
                  |
    +-------------+-------------+
    |             |             |
    v             v             v
 list.html    detail.html   schema.html
 (index of    (per-entity   (browsable
  entities)    full page)    schema doc)
```

### The Rendering Algorithm

The renderer walks the JSON Schema `properties` object in `ui.field_order` sequence, exactly as `form.js` does at runtime, but emits static HTML:

```python
def render_field(field_name: str, field_def: dict, value, mode='display') -> str:
    """Convert a single schema field + value into HTML.

    Mirrors the logic in form.js getInput() but outputs static markup.
    """
    ui = field_def.get('ui', {})
    field_type = field_def.get('type', 'string')
    widget = ui.get('widget', None)

    # Skip hidden fields (same logic as form.js line 36-41)
    if ui.get('display') is False:
        return ''
    if ui.get('protected') and mode == 'edit':
        return ''

    # Widget-specific rendering
    if widget == 'currency':
        return f'<span class="field currency">${value:.2f}</span>'
    elif widget == 'textarea':
        return f'<div class="field textarea">{escape(str(value))}</div>'
    elif field_type == 'boolean':
        checked = 'checked' if value else ''
        return f'<span class="field bool" aria-checked="{str(value).lower()}">{value}</span>'
    elif field_type == 'integer' or field_type == 'number':
        return f'<span class="field number">{value}</span>'
    elif field_type == 'array' and '$ref' in field_def.get('items', {}):
        # Collection reference -- render as links
        return render_ref_list(field_name, value)
    else:
        return f'<span class="field text">{escape(str(value))}</span>'


def render_entity(schema: dict, data: dict, mode='display') -> str:
    """Render a full entity to HTML using schema-driven field iteration."""
    props = schema.get('properties', {})
    ui = schema.get('ui', {})
    field_order = ui.get('field_order', list(props.keys()))

    # Respect groups if defined
    groups = ui.get('groups', {})
    if groups:
        return render_grouped(schema, data, groups, field_order, mode)

    html_parts = []
    for field_name in field_order:
        if field_name not in props:
            continue
        field_def = props[field_name]
        value = data.get(field_name, field_def.get('default', ''))
        html_parts.append(render_field(field_name, field_def, value, mode))

    return '\n'.join(html_parts)
```

### Grouped Field Rendering

PyBend schemas support `ui.groups` for organizing fields into fieldsets. The static renderer replicates this:

```python
def render_grouped(schema, data, groups, field_order, mode):
    """Render fields organized by schema-defined groups.

    Produces <fieldset> elements with <legend>, same semantic
    structure as form.js renderGroupedFields().
    """
    props = schema['properties']
    rendered_fields = set()
    html = ''

    for group_name, group_fields in groups.items():
        group_html = f'<fieldset class="field-group">\n<legend>{escape(group_name)}</legend>\n'
        for fname in group_fields:
            if fname in props and fname in field_order:
                fdef = props[fname]
                val = data.get(fname, fdef.get('default', ''))
                group_html += render_field(fname, fdef, val, mode)
                rendered_fields.add(fname)
        group_html += '</fieldset>\n'
        html += group_html

    # Render ungrouped fields
    for fname in field_order:
        if fname not in rendered_fields and fname in props:
            fdef = props[fname]
            val = data.get(fname, fdef.get('default', ''))
            html += render_field(fname, fdef, val, mode)

    return html
```

### Handling $defs (Nested Models)

PyBend schemas include `$defs` for related models (e.g., `Comment` inside `Product`). The static renderer recursively applies the same algorithm:

```python
def render_ref_list(field_name, hrefs, parent_schema):
    """Render a ListRef field as a list of linked items.

    For static generation, we resolve each href to its data at build time
    and render inline, rather than requiring runtime fetches.
    """
    ref_schema_name = extract_ref_name(parent_schema, field_name)
    ref_schema = parent_schema.get('$defs', {}).get(ref_schema_name, {})

    if not ref_schema:
        # Fallback: render as simple links
        return ''.join(f'<a href="{href}">{href}</a>' for href in hrefs)

    # Resolve and render each referenced entity
    items = [resolve_href_to_data(href) for href in hrefs]
    return ''.join(render_entity(ref_schema, item) for item in items)
```

### Why This Is Powerful

The static renderer and the runtime frontend (`form.js`, `ntt-item.js`) share the same contract: the JSON Schema. This means:

1. **Zero template maintenance.** Adding a field to a model updates both the live UI and the static site.
2. **Pixel-identical output.** The same rendering rules produce the same visual structure.
3. **Schema is the template.** The `ui`, `properties`, and `groups` sections of the schema serve the role that Jinja2 templates play in traditional SSGs.

---

## 4. CSS Generation Strategies

### Strategy 1: Extract Component Styles into Static Sheets

PyBend's frontend components (`ntt-item`, `ntt-list`, etc.) use shadow DOM with inline styles. For static generation, these styles are extracted into a single CSS file:

```css
/* Generated from ntt-item.js shadow styles */
.ntt-item { display: block; padding: 1rem; border: 1px solid var(--border); }
.ntt-item .field { margin-bottom: 0.5rem; }
.ntt-item .field.currency::before { content: '$'; }
.ntt-item .header { font-size: 1.25rem; font-weight: 600; }

/* Generated from form.js field type styles */
.field-group { border: 1px solid var(--group-border); padding: 1rem; margin: 1rem 0; }
.field-group legend { font-weight: 600; padding: 0 0.5rem; }
.field.textarea { white-space: pre-wrap; max-height: 200px; overflow-y: auto; }
```

### Strategy 2: Critical CSS Inlining

For maximum performance, inline above-the-fold CSS directly into each HTML file's `<head>`. This eliminates the render-blocking external stylesheet request. The target is under 14KB inlined -- fitting within the first TCP round-trip window.

```html
<head>
  <style>
    /* Critical: layout, typography, above-the-fold component styles */
    :root { --bg: #fff; --text: #111; --border: #e0e0e0; --accent: #2563eb; }
    body { font-family: system-ui, sans-serif; margin: 0; color: var(--text); }
    .page { max-width: 72rem; margin: 0 auto; padding: 1rem; }
    .ntt-list { display: grid; gap: 1rem; }
    .ntt-item { padding: 1rem; border: 1px solid var(--border); border-radius: 0.5rem; }
    /* ... first-screen styles only ... */
  </style>
  <!-- Defer non-critical styles -->
  <link rel="preload" href="/styles.css" as="style" onload="this.rel='stylesheet'">
  <noscript><link rel="stylesheet" href="/styles.css"></noscript>
</head>
```

**Implementation approach:**

```python
def split_critical_css(full_css: str, html: str) -> tuple[str, str]:
    """Split CSS into critical (above-fold) and deferred portions.

    Uses selector matching against the first ~5 elements in the HTML
    to determine which rules are critical.
    """
    # Parse CSS rules
    rules = parse_css_rules(full_css)
    critical = []
    deferred = []

    # Selectors that match elements in the first viewport
    above_fold_selectors = extract_selectors_from_html(html, max_depth=20)

    for rule in rules:
        if rule.selector in above_fold_selectors or rule.selector.startswith(':root'):
            critical.append(rule)
        else:
            deferred.append(rule)

    return (serialize_rules(critical), serialize_rules(deferred))
```

### Strategy 3: CSS-Only Interactivity

Modern CSS provides sufficient interactivity for many common UI patterns without JavaScript. This is the single most important factor in achieving near-zero JS.

#### Technique: `:target` for Navigation and Modals

```html
<!-- Tab navigation using :target -->
<nav>
  <a href="#details">Details</a>
  <a href="#comments">Comments</a>
</nav>

<section id="details" class="tab-panel">
  <h2>Product Details</h2>
  <!-- field content -->
</section>

<section id="comments" class="tab-panel">
  <h2>Comments</h2>
  <!-- comment list -->
</section>

<style>
  .tab-panel { display: none; }
  .tab-panel:target { display: block; }
  /* Show first tab by default */
  .tab-panel:first-of-type { display: block; }
  .tab-panel:first-of-type:not(:target) {
    display: block;
  }
  /* Hide first tab when another is targeted */
  .tab-panel:target ~ .tab-panel:first-of-type { display: none; }
</style>
```

#### Technique: `<details>` for Expandable Sections

```html
<!-- Accordion for field groups, generated from schema ui.groups -->
<details open>
  <summary>Main Information</summary>
  <div class="group-content">
    <span class="field text">Widget Pro</span>
    <span class="field currency">$29.99</span>
  </div>
</details>

<details>
  <summary>Comments (3)</summary>
  <div class="group-content">
    <!-- rendered comment entities -->
  </div>
</details>
```

#### Technique: `:checked` for Toggle States

```html
<!-- Dark mode toggle, no JS -->
<input type="checkbox" id="dark-mode" class="sr-only">
<label for="dark-mode" class="theme-toggle">Toggle dark mode</label>

<div class="page">
  <!-- entire page content -->
</div>

<style>
  #dark-mode:checked ~ .page {
    --bg: #0f172a;
    --text: #e2e8f0;
    --border: #334155;
  }
</style>
```

#### Technique: `scroll-snap` for Carousels

```html
<!-- Image carousel, no JS -->
<div class="carousel">
  <div class="carousel-track">
    <img src="/products/1/img1.jpg" alt="View 1">
    <img src="/products/1/img2.jpg" alt="View 2">
    <img src="/products/1/img3.jpg" alt="View 3">
  </div>
</div>

<style>
  .carousel { overflow-x: auto; scroll-snap-type: x mandatory; }
  .carousel-track { display: flex; gap: 1rem; }
  .carousel-track img { scroll-snap-align: start; flex: 0 0 100%; }
</style>
```

#### 2025/2026 CSS Capabilities That Replace JS

| CSS Feature | Replaces | Browser Support |
|-------------|----------|----------------|
| `:has()` | Parent selection JS, form validation indicators | Baseline 2024 |
| Container queries | ResizeObserver-based responsive components | Baseline 2024 |
| Scroll-driven animations | IntersectionObserver, scroll event handlers | Baseline 2025 |
| `popover` attribute | Custom modal/dropdown JS, focus trap | Baseline Widely Available April 2025 |
| `<dialog>` element | Modal overlay JS, backdrop handling | Baseline 2022 |
| View transitions | Route transition animations | Baseline 2025 |
| `@layer` cascade | Specificity management JS | Baseline 2023 |
| `:target` pseudo-class | Hash router, tab switching JS | Baseline (always) |
| `<details>` / `<summary>` | Accordion/toggle JS | Baseline (always) |
| `scroll-snap` | Carousel/slider JS libraries | Baseline 2022 |
| `@property` (custom properties) | Dynamic theming JS | Baseline 2024 |

---

## 5. Near-Zero JavaScript Patterns

### What Absolutely Requires JavaScript

There is a hard boundary. Some interactions cannot be achieved with HTML + CSS alone:

| Capability | Why JS Is Required | Minimum JS Approach |
|------------|-------------------|---------------------|
| **Form submission** (POST/PUT) | HTML forms can only GET/POST to a URL; no PATCH, no JSON body, no auth headers | `<form action="..." method="POST">` works for basic cases. For auth headers: tiny `fetch()` wrapper (~20 LOC) |
| **Authentication** | Token storage, login flow, header injection | Cookie-based auth eliminates most JS. For JWT: ~50 LOC token manager |
| **Real-time updates** | WebSocket/SSE connections, DOM patching | Not applicable to static sites. Accept staleness or use edge functions. |
| **Search/filter** | Client-side data querying | Pre-generate filtered pages (by category, tag). For free-text: use external search (Algolia, Pagefind) |
| **Pagination beyond static** | Dynamic page loading | Pre-generate all pages. "Load more" requires JS or linked pagination. |

### What Does NOT Require JavaScript

The following are commonly implemented in JS but can be fully static:

- **Navigation:** Anchor links + `:target` CSS
- **Accordions/toggles:** `<details>` + `<summary>`
- **Modals:** `<dialog>` element + `:target` or `popover`
- **Tabs:** `:target` pseudo-class or radio button hack
- **Carousels:** `scroll-snap` CSS
- **Dark mode:** `:checked` pseudo-class on a toggle + CSS custom properties
- **Tooltips:** `popover` attribute (Baseline 2025)
- **Responsive layout changes:** Container queries, media queries
- **Scroll-linked animations:** `animation-timeline: scroll()` CSS
- **Form validation visual feedback:** `:valid`, `:invalid`, `:has()` pseudo-classes
- **Sortable tables:** Pre-generate sorted variants, link between them

### The 20-Line JS Budget

For a "near-zero JS" static site, the practical budget is approximately 20-50 lines of vanilla JavaScript, covering:

```javascript
// Total JS for a near-zero static site (~40 LOC, <1KB gzipped)

// 1. Search integration (if needed)
document.querySelector('.search-input')?.addEventListener('input', (e) => {
  // Delegate to Pagefind or similar pre-indexed search
  window.__pagefind?.search(e.target.value).then(renderResults);
});

// 2. Form submission with auth (if needed)
document.querySelectorAll('form[data-api]').forEach(form => {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const token = document.cookie.match(/token=([^;]+)/)?.[1];
    await fetch(form.dataset.api, {
      method: form.method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? {'x-access-token': token} : {})
      },
      body: JSON.stringify(data)
    });
  });
});

// 3. Copy-to-clipboard (progressive enhancement)
document.querySelectorAll('[data-copy]').forEach(btn => {
  btn.addEventListener('click', () => {
    navigator.clipboard.writeText(btn.dataset.copy);
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 2000);
  });
});
```

---

## 6. Progressive Enhancement: Identifying the Boundary

### The Enhancement Spectrum

```
 Pure Static HTML          CSS Interactivity         Minimal JS            Full JS App
 +------------------+   +-------------------+   +------------------+   +---------------+
 | Content display  |   | Accordions        |   | Form submission  |   | Real-time     |
 | Navigation links |   | Tab panels        |   | Search           |   | WebSocket     |
 | Lists, grids     |   | Modals/dialogs    |   | Auth flows       |   | Complex state |
 | Semantic markup  |   | Dark mode toggle  |   | Lazy loading     |   | Client routing|
 | Images, media    |   | Scroll snap       |   | Clipboard API    |   | Drag & drop   |
 +------------------+   +-------------------+   +------------------+   +---------------+
        Tier 0                 Tier 1                  Tier 2                Tier 3
```

### Decision Framework

For each feature in a PyBend static site, apply this test:

```
1. Can it be a link to another pre-generated page?          -> Tier 0 (pure HTML)
2. Can it be a CSS state change (:target, :checked, etc.)?  -> Tier 1 (CSS only)
3. Does it require sending data to a server?                -> Tier 2 (minimal JS)
4. Does it require persistent client-side state?            -> Tier 3 (full JS)
```

### Applying This to PyBend Entity Pages

| Feature | Current (NTT.js) | Static Tier | Approach |
|---------|------------------|-------------|----------|
| Entity list display | JS fetch + DOM render | Tier 0 | Pre-generated HTML list page |
| Entity detail view | JS fetch + ntt-item render | Tier 0 | Pre-generated HTML detail page |
| Field rendering | form.js schema walk | Tier 0 | Build-time schema walk (Python) |
| Field groups | form.js renderGroupedFields | Tier 1 | `<details>` or `<fieldset>` |
| Pagination | JS "Load More" button | Tier 0 | Pre-generated page-1.html, page-2.html, ... with `<a>` links |
| Navigation | ntt-router hash routing | Tier 0 | Standard `<a>` links between pages |
| Edit form | ntt-item edit toggle | Tier 2 | Progressive: static display, JS for edit |
| Method buttons (like, comment) | ntt-method POST | Tier 2 | `<form action="..." method="POST">` or JS fetch |
| Search | Not implemented | Tier 2 | Pagefind (pre-indexed at build time) |
| Dark mode | Theme.js | Tier 1 | `:checked` toggle + CSS custom properties |
| Access control (hide buttons) | Permissions.js | Tier 0 | Build-time: generate different pages per role, or omit restricted content |

---

## 7. Build Pipeline Design

### Full Pipeline Architecture

```
                    +------------------+
                    | PyBend Models    |
                    | (Python classes) |
                    +--------+---------+
                             |
                    +--------v---------+
                    | schema()         |  model_dump() for all entities
                    | list() per model |
                    +--------+---------+
                             |
                    +--------v---------+
                    | StaticBuilder    |
                    |                  |
                    | - Schema walk    |
                    | - HTML emit      |
                    | - CSS extract    |
                    | - Asset copy     |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v----+  +-----v------+  +----v--------+
     | HTML Files  |  | CSS Files  |  | Asset Files |
     |             |  |            |  |             |
     | index.html  |  | styles.css |  | images/     |
     | products/   |  | critical/  |  | fonts/      |
     |  index.html |  |  *.css     |  |             |
     |  1/         |  |            |  |             |
     |   index.html|  |            |  |             |
     +------+------+  +-----+------+  +------+------+
            |                |               |
            +--------+-------+-------+-------+
                     |
            +--------v---------+
            | Post-Processing  |
            |                  |
            | - Critical CSS   |
            | - Fingerprinting |
            | - Sitemap        |
            | - Minification   |
            +--------+---------+
                     |
            +--------v---------+
            |   build/         |
            |   (deploy-ready) |
            +------------------+
```

### Implementation: The StaticBuilder Class

```python
import hashlib
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from html import escape
from jinja2 import Environment, DictLoader

class StaticBuilder:
    """Generates a static site from PyBend model definitions and data.

    Uses JSON Schema as the sole rendering contract -- no hand-written
    templates for entity pages. Base layout uses a single Jinja2 template
    for the HTML shell (head, nav, footer). Entity content is rendered
    by walking the schema.
    """

    def __init__(self, models: list, output_dir: str = 'build'):
        self.models = models
        self.output_dir = Path(output_dir)
        self.manifest = {}       # source -> fingerprinted path
        self._css_rules = []     # collected CSS rules
        self._pages = []         # (path, html) tuples for post-processing

    def build(self):
        """Execute full build pipeline."""
        start = datetime.now()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._clean()

        # Phase 1: Generate entity pages
        for model_class in self.models:
            schema = model_class.schema()
            tablename = schema.get('__tablename__', model_class.__name__.lower())
            items = model_class.list()

            self._generate_list_page(schema, tablename, items)
            self._generate_detail_pages(schema, tablename, items)

        # Phase 2: Generate CSS
        self._generate_css()

        # Phase 3: Copy static assets
        self._copy_assets()

        # Phase 4: Post-process (critical CSS, fingerprinting, minification)
        self._post_process()

        # Phase 5: Generate sitemap and metadata
        self._generate_sitemap()

        elapsed = (datetime.now() - start).total_seconds()
        print(f"Built {len(self._pages)} pages in {elapsed:.2f}s")

    def _generate_list_page(self, schema, tablename, items):
        """Generate paginated list pages for a model."""
        page_size = 20
        total_pages = max(1, (len(items) + page_size - 1) // page_size)

        for page_num in range(total_pages):
            start_idx = page_num * page_size
            page_items = items[start_idx:start_idx + page_size]

            content = self._render_list(schema, page_items)
            pagination = self._render_pagination(tablename, page_num, total_pages)

            html = self._wrap_in_layout(
                title=f"{schema['__name__']} - Page {page_num + 1}",
                content=content + pagination,
                schema=schema
            )

            if page_num == 0:
                path = f"{tablename}/index.html"
            else:
                path = f"{tablename}/page/{page_num + 1}/index.html"

            self._write_page(path, html)

    def _render_pagination(self, tablename, current, total):
        """Render pagination links -- pure HTML, no JS."""
        if total <= 1:
            return ''
        links = []
        for i in range(total):
            href = f"/{tablename}/" if i == 0 else f"/{tablename}/page/{i + 1}/"
            cls = ' class="current"' if i == current else ''
            links.append(f'<a href="{href}"{cls}>{i + 1}</a>')
        return f'<nav class="pagination" aria-label="Pages">{"".join(links)}</nav>'
```

### Watch Mode and Incremental Builds

For development, a watch mode rebuilds only changed content:

```python
import hashlib
from pathlib import Path

class IncrementalBuilder(StaticBuilder):
    """Extends StaticBuilder with content-hash-based incremental builds."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hash_cache_file = self.output_dir / '.build-hashes.json'
        self.prev_hashes = self._load_hashes()
        self.curr_hashes = {}

    def _needs_rebuild(self, key: str, content: str) -> bool:
        """Check if content has changed since last build."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        self.curr_hashes[key] = content_hash
        return self.prev_hashes.get(key) != content_hash

    def _write_page(self, path: str, html: str):
        """Only write if content changed (skip identical files)."""
        if self._needs_rebuild(path, html):
            super()._write_page(path, html)

    def _save_hashes(self):
        """Persist hash cache for next build."""
        self.hash_cache_file.write_text(json.dumps(self.curr_hashes))

    def _load_hashes(self) -> dict:
        if self.hash_cache_file.exists():
            return json.loads(self.hash_cache_file.read_text())
        return {}
```

### Asset Fingerprinting

Content-based hashing enables aggressive CDN caching with instant cache invalidation:

```python
def fingerprint_asset(file_path: Path) -> str:
    """Generate a fingerprinted filename based on content hash.

    styles.css -> styles.a1b2c3d4.css
    Enables Cache-Control: max-age=31536000 (1 year) on CDN.
    """
    content = file_path.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()[:8]
    stem = file_path.stem
    suffix = file_path.suffix
    return f"{stem}.{content_hash}{suffix}"
```

---

## 8. Output Structure and URL Conventions

### Recommended Structure: Nested Directories with index.html

This convention produces clean URLs on every hosting platform without server-side rewrite rules:

```
build/
  index.html                          # /  (home / model index)
  styles.a1b2c3d4.css                 # fingerprinted CSS
  products/
    index.html                        # /products/  (list, page 1)
    page/
      2/
        index.html                    # /products/page/2/  (list, page 2)
      3/
        index.html                    # /products/page/3/
    1/
      index.html                      # /products/1/  (detail for product ID 1)
    2/
      index.html                      # /products/2/
    schema/
      index.html                      # /products/schema/  (browsable schema doc)
  users/
    index.html                        # /users/
    1/
      index.html                      # /users/1/
  images/
    products/
      1/
        hero.jpg                      # /images/products/1/hero.jpg
  sitemap.xml
  robots.txt
  404.html
```

### URL Mapping to PyBend API

| PyBend API Route | Static File | Clean URL |
|-----------------|-------------|-----------|
| `GET /Product` (schema) | `products/schema/index.html` | `/products/schema/` |
| `GET /products` (list) | `products/index.html` | `/products/` |
| `GET /products?offset=20` | `products/page/2/index.html` | `/products/page/2/` |
| `GET /products/1` (detail) | `products/1/index.html` | `/products/1/` |
| `GET /products/1/comments` | Inline in `products/1/index.html` | `/products/1/#comments` |

### Why Nested index.html Over Flat HTML Files

| Approach | Pros | Cons |
|----------|------|------|
| **Nested** (`products/1/index.html`) | Clean URLs everywhere, no server config, universal | More directories, slightly more inodes |
| **Flat** (`products/1.html`) | Fewer directories, simple | Requires rewrite rules for clean URLs, not all hosts support it |

The nested approach is universally recommended for static sites because it works identically on GitHub Pages, Netlify, Cloudflare Pages, S3, and nginx without any configuration.

---

## 9. Deployment Targets

### Platform Comparison

| Platform | TTFB (Global Median) | Free Tier | Custom Domain | Build Integration | Best For |
|----------|---------------------|-----------|---------------|-------------------|----------|
| **Cloudflare Pages** | ~57ms | Unlimited bandwidth | Yes (+ free SSL) | Git push | Best global performance |
| **GitHub Pages** | ~80ms | 1GB storage, 100GB/mo BW | Yes (CNAME) | GitHub Actions | Open source projects |
| **Netlify** | ~227ms | 100GB/mo BW, 300 build min/mo | Yes | Git push | DX, preview deploys |
| **AWS S3 + CloudFront** | ~50ms | 1TB/mo (first year) | Yes | Manual or CI/CD | Enterprise, full control |
| **Vercel** | ~100ms | 100GB/mo BW | Yes | Git push | Next.js ecosystem |
| **Any nginx** | Depends on hosting | N/A | Yes | rsync / CI/CD | Self-hosted, air-gapped |

*TTFB values are approximate medians from various benchmarks; actual performance varies by region and test methodology.*

### Deployment Configuration Examples

#### GitHub Pages (via GitHub Actions)

```yaml
# .github/workflows/build-static.yml
name: Build Static Site
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e .
      - run: python -m pybend.static_builder --output build/
      - uses: actions/upload-pages-artifact@v3
        with:
          path: build/
      - uses: actions/deploy-pages@v4
```

#### Cloudflare Pages

```toml
# wrangler.toml (or configure in dashboard)
[site]
bucket = "./build"

[build]
command = "python -m pybend.static_builder --output build/"
```

#### S3 + CloudFront

```bash
# Deploy script
aws s3 sync build/ s3://my-bucket/ \
  --delete \
  --cache-control "public, max-age=31536000" \
  --exclude "*.html" \
  --exclude "sitemap.xml"

# HTML files get short cache (for instant updates)
aws s3 sync build/ s3://my-bucket/ \
  --delete \
  --cache-control "public, max-age=60" \
  --include "*.html" \
  --include "sitemap.xml"

# Invalidate CloudFront for HTML only
aws cloudfront create-invalidation \
  --distribution-id $CF_DIST_ID \
  --paths "/*.html" "/*/index.html"
```

#### Nginx (Self-Hosted)

```nginx
server {
    listen 80;
    server_name example.com;
    root /var/www/static-site/build;

    # Clean URLs: try exact match, then directory index
    location / {
        try_files $uri $uri/ $uri/index.html =404;
    }

    # Aggressive caching for fingerprinted assets
    location ~* \.[a-f0-9]{8}\.(css|js|jpg|png|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Short cache for HTML
    location ~* \.html$ {
        expires 60s;
        add_header Cache-Control "public, must-revalidate";
    }

    # Custom 404
    error_page 404 /404.html;
}
```

---

## 10. Performance Baselines

### What a Static Site Should Achieve

A properly built static site served from a CDN should hit these targets consistently:

| Metric | Target | Why |
|--------|--------|-----|
| **TTFB** | < 100ms (from CDN edge) | Pre-built files, no server computation. CDN edge response. |
| **FCP** (First Contentful Paint) | < 500ms | No JS execution required before first paint. |
| **LCP** (Largest Contentful Paint) | < 1.0s | Critical CSS inlined, images optimized. |
| **CLS** (Cumulative Layout Shift) | 0.00 | No dynamically loaded content shifting layout. |
| **TBT** (Total Blocking Time) | 0ms | Near-zero JS means nothing blocks the main thread. |
| **Lighthouse Performance** | 100 | All above metrics combine to perfect score. |
| **Total page weight** | < 50KB (HTML + CSS) | No framework JS bundle. Just content + styles. |
| **Time to Interactive** | = FCP | No hydration step. Page is interactive on first paint. |

### Comparison: Static vs Dynamic PyBend

| Metric | Dynamic PyBend (current) | Static PyBend (target) | Improvement |
|--------|-------------------------|----------------------|-------------|
| TTFB | 200-500ms (server compute) | 20-80ms (CDN edge) | 3-10x faster |
| FCP | 1-2s (fetch schema, render) | 300-500ms (inline CSS, no JS) | 2-4x faster |
| LCP | 2-3s (fetch data, mount components) | 500ms-1s (content in HTML) | 2-4x faster |
| TBT | 100-300ms (JS parsing/exec) | 0ms (no JS) | Eliminated |
| Page weight | 200-400KB (JS + CSS + data) | 20-50KB (HTML + CSS) | 5-10x smaller |
| Lighthouse | 60-85 (typical SPA) | 95-100 (static) | Near-perfect |

### Why These Numbers Are Achievable

1. **No server computation.** TTFB is purely CDN latency (network hop to nearest edge node).
2. **No render-blocking JS.** The browser parses HTML and paints immediately. Critical CSS is inlined.
3. **No layout shift.** Content dimensions are known at build time. No skeleton screens, no loading spinners.
4. **No hydration.** Unlike React SSG (Next.js, Gatsby), there is no JavaScript bundle that must download, parse, and "hydrate" the server-rendered HTML. The HTML is the final product.

---

## 11. Architecture Recommendation for PyBend

### Proposed Module: `pybend.static`

```
src/pybend/static_gen/
    __init__.py              # Public API: StaticBuilder, build_site()
    builder.py               # Core StaticBuilder class
    renderer.py              # Schema-to-HTML rendering (mirrors form.js logic)
    css.py                   # CSS extraction, critical CSS splitting
    assets.py                # Asset copying, fingerprinting, manifest
    sitemap.py               # sitemap.xml generation
    cli.py                   # CLI entry point: python -m pybend.static_gen
    templates/
        base.html            # Single Jinja2 shell (head, nav, footer)
        404.html             # Error page
```

### Integration Point: One Command

```python
# In pybend/__init__.py or as a CLI command
from pybend.static_gen import build_site

# Build static site from existing PyBend app
build_site(
    models=[Product, User, Comment],
    storage=storage_backend,
    output='build/',
    base_url='https://example.com',
    options={
        'inline_critical_css': True,
        'fingerprint_assets': True,
        'generate_sitemap': True,
        'page_size': 20,
    }
)
```

Or from the CLI:

```bash
python -m pybend.static_gen \
    --app pybend.example.main \
    --output build/ \
    --base-url https://example.com
```

### The Key Architectural Insight

The static generator does not replace the dynamic application. It is a **build-time consumer** of the same schema contract that the runtime frontend consumes. This means:

```
                  ProtoModel.schema()
                         |
            +------------+------------+
            |                         |
      Runtime Consumer          Build-time Consumer
      (NTT.js, form.js,        (StaticBuilder,
       ntt-item.js)              renderer.py)
            |                         |
            v                         v
      Dynamic SPA               Static HTML
      (interactive,             (read-only,
       real-time,                CDN-served,
       authenticated)            zero-runtime)
```

Both consumers follow the same rules:
- Read `properties` in `ui.field_order` sequence
- Respect `ui.display`, `ui.protected`, `ui.groups`
- Resolve `$defs` for nested models
- Apply widget-specific rendering for `ui.widget` values

The schema is the template. The model is the app. The static generator is just another rendering target.

### Build Performance Estimates

For a PyBend application with typical data volumes:

| Data Volume | Estimated Build Time | Output Size |
|------------|---------------------|-------------|
| 100 entities, 3 models | < 1s | ~500KB |
| 1,000 entities, 5 models | 2-5s | ~5MB |
| 10,000 entities, 10 models | 15-30s | ~50MB |
| 100,000 entities, 10 models | 2-5 min | ~500MB |

With incremental builds, rebuild time after a single entity change drops to < 1s regardless of total site size.

---

## Sources

- [DigitalOcean: Introduction to Static Site Generators](https://www.digitalocean.com/community/conceptual-articles/introduction-to-static-site-generators)
- [Full Stack Python: Static Site Generators](https://www.fullstackpython.com/static-site-generator.html)
- [Frozen-Flask Documentation](https://frozen-flask.readthedocs.io/)
- [Frozen-Flask GitHub Repository](https://github.com/Frozen-Flask/Frozen-Flask)
- [staticjinja: Minimalist Python Library for Static Sites with Jinja](https://github.com/staticjinja/staticjinja)
- [coveooss/json-schema-for-humans: JSON Schema to HTML Documentation](https://github.com/coveooss/json-schema-for-humans)
- [Cloudflare: JSON-Powered Documentation Generator](https://blog.cloudflare.com/cloudflares-json-powered-documentation-generator/)
- [Building Interactive HTML Components Without JavaScript](https://e-dimensionz.com/devinsights/building-interactive-html-components-without-javascript)
- [The Ultimate 2025 CSS Guide: Build Faster, Write Less JavaScript](https://dev.to/manikandan/the-ultimate-2025-css-guide-build-faster-write-less-javascript-5412)
- [HTMHell: For the Love of details](https://www.htmhell.dev/adventcalendar/2025/23/)
- [MDN: CSS Scroll Snap](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Scroll_snap)
- [HTML Popover API: Native Tooltips Without JavaScript](https://medium.com/@lioradaven/html-popover-api-native-tooltips-without-javascript-2025-d59ad19ade98)
- [Interop 2026 | CSS-Tricks](https://css-tricks.com/interop-2026/)
- [Zero-JavaScript Architecture: When and How to Use It Effectively in 2026](https://sameersabir.dev/blog/zero-javascript-architecture-2026)
- [Progressive Enhancement in 2025, Actually Works](https://medium.com/@Nexumo_/progressive-enhancement-in-2025-actually-works-70213ab06777)
- [Smashing Magazine: Understanding Critical CSS](https://www.smashingmagazine.com/2015/08/understanding-critical-css/)
- [Google: Optimize CSS Delivery](https://developers.google.com/speed/docs/insights/OptimizeCSSDelivery)
- [SitePoint: How and Why You Should Inline Your Critical CSS](https://www.sitepoint.com/how-and-why-you-should-inline-your-critical-css/)
- [Smashing Magazine: Using a Static Site Generator at Scale](https://www.smashingmagazine.com/2016/08/using-a-static-site-generator-at-scale-lessons-learned/)
- [SimplyExplained: Benchmarking Static Website Hosting Providers](https://simplyexplained.com/blog/benchmarking-static-website-hosting-providers/)
- [SpeedVitals: Netlify vs Cloudflare Pages Performance Comparison](https://speedvitals.com/blog/netlify-vs-cloudflare-pages/)
- [DigitalApplied: Vercel vs Netlify vs Cloudflare Pages 2025 Comparison](https://www.digitalapplied.com/blog/vercel-vs-netlify-vs-cloudflare-pages-comparison)
- [Chrome for Developers: Lighthouse Performance Scoring](https://developer.chrome.com/docs/lighthouse/performance/performance-scoring)
- [The HTMX Renaissance -- Rethinking Web Architecture for 2026](https://www.softwareseni.com/the-htmx-renaissance-rethinking-web-architecture-for-2026/)
- [Middleman: Pretty URLs (Directory Indexes)](https://middlemanapp.com/advanced/pretty-urls/)
- [Patterns.dev: Incremental Static Generation](https://www.patterns.dev/react/incremental-static-rendering/)
