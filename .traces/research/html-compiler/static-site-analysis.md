# Fully Static Website Generation for PyBend: Strategic Analysis

## For: CEO & Engineering Team
## Date: February 2026
## Prepared by: Architecture Team

---

### How to Read This Document

| Time Available | What to Read | What You'll Know |
|---|---|---|
| **5 minutes** | Executive Summary only | The core question, the answer, the dollar figures |
| **15 minutes** | Executive Summary + Section 6 (Cost-Benefit) + Section 8 (Recommendation) | Whether to invest, phased plan, what NOT to do |
| **30 minutes** | Add Sections 1-4 (SSG basics, Industry, Architecture, CSS-only) | Full technical and market context |
| **45 minutes** | Full document including Risk Register and Appendices | Complete strategic and technical understanding |

Each section opens with a plain-English summary ("So What?"), then goes deep. Read at whatever depth serves your role.

**Scope distinction:** A prior analysis (html-compiler-analysis.md) evaluated **template compilation** -- pre-building HTML templates at server start and injecting data at runtime. This document evaluates a different, complementary capability: **fully static site generation** -- exporting complete HTML + CSS pages with near-zero JavaScript, deployable to any CDN or static host without a running server. The two are not mutually exclusive; the static exporter builds on the same schema-to-HTML pipeline the template compiler would use.

---

## Executive Summary

**The question:** Should PyBend offer a `pybend export` command that generates a complete, deployable static website -- HTML pages, CSS, pagination, navigation -- directly from schema-driven model definitions, with near-zero JavaScript?

**The short answer:** Yes, but as a phased investment. Start with HTTP caching on the dynamic stack (1-2 weeks, benefits everyone). Build the static exporter as a second step (5-7 engineering days for MVP), targeting the ~30% of web projects that are fully static-appropriate. Position it as PyBend's "zero to deployed" story: define a model, get a website. No server required.

**Why this matters:**

> _"Define a model, get a working full-stack application"_ is PyBend's current promise. Static export extends it to: _"Define a model, get a deployable website. No server. No JavaScript. No hosting costs."_

No existing framework -- not Hugo, not Astro, not Next.js, not any Python SSG -- generates static HTML from data model definitions. Every one requires handwritten templates. PyBend's JSON Schema carries complete rendering instructions (field types, widgets, groups, access rules, methods). The exporter reads the schema, walks the data, and writes HTML files. The schema IS the template. This is a genuine whitespace opportunity.

### Key Numbers

| Metric | Value | Source |
|---|---|---|
| Static site TTFB from CDN | <50ms | Cloudflare/AWS benchmarks |
| Current PyBend SPA LCP | 2-4 seconds | Internal measurement |
| Static HTML LCP | 0.3-0.8 seconds | Sparkbox benchmarks |
| Hosting cost (static on CDN) | $0-5/month | Cloudflare Pages, GitHub Pages |
| Hosting cost (dynamic server) | $32-270/month | VPS/managed hosting |
| JS shipped (static) | <1KB (or zero) | CSS-only interactivity research |
| JS shipped (current SPA) | ~150-200KB | Internal measurement |
| MVP engineering effort | 5-7 days, ~980 LOC | Architecture estimate |
| Full feature effort | 10-16 weeks, $100-160K | Full pipeline with incremental builds |
| Addressable market (fully static) | ~30% of web projects | W3Techs, HTTP Archive |
| Conversion impact per 0.1s faster | +8-10% | Google/Deloitte research |

### The Recommendation

1. **Now (1-2 weeks):** Add HTTP caching headers to schema and public endpoints. Benefits 100% of users immediately.
2. **Next (5-7 days):** Build MVP static exporter -- `pybend export` CLI, Jinja2 templates, full rebuild, dark/light theme, output to `dist/`. Skip incremental builds, search, forms.
3. **Later (if warranted):** Incremental builds, per-role export, hybrid mode with NTT hydration, custom template overrides.
4. **Do not:** Build a Node.js SSR layer, use headless browser pre-rendering, or make the exporter mandatory.

---

## 1. What Is Static Site Generation?

### So What?

Static site generation (SSG) means building all your HTML pages ahead of time -- before any user visits -- and deploying them as plain files to a web server or CDN. There is no application server processing requests, no database queries on page load, no JavaScript constructing the page in the browser. The HTML is ready. The browser parses it and paints it. Done.

This is the original web. Before PHP, before Rails, before React, websites were collections of HTML files. The industry spent 15 years adding complexity (SPAs, client-side rendering, virtual DOMs, hydration) and is now spending the last 5 years removing it again. The consensus in 2026: ship HTML when you can, ship JavaScript only when you must.

### How It Works

```
STATIC SITE GENERATION PIPELINE
================================================================

  Data Source        Template Engine       Output Files         Deployment
  +-----------+     +-----------+        +-----------+        +-----------+
  | Database  |     | Jinja2 /  |        | /products/|        | CDN Edge  |
  | JSON API  | --> | Nunjucks/ | -----> | index.html|  ----> | (300+     |
  | Markdown  |     | Go tmpl   |        | /products/|        |  locations)|
  | Model data|     |           |        | 1/index.. |        |           |
  +-----------+     +-----------+        +-----------+        +-----------+
       ^                                      |
       |                                      v
  Runs ONCE at                         Served as plain
  build time                           files forever
  (seconds to                          (until next build)
  minutes)
```

For PyBend, the pipeline is:

```
PyBend Models         ProtoModel.schema()       StaticRenderer        HTML Files
+-----------+        +-----------+             +-----------+         +-----------+
| Product   |        | JSON      |             | Walks     |         | products/ |
| Comment   | -----> | Schema    | ----------> | schema    | ------> | index.html|
| User      |        | + fields  |             | fields,   |         | products/ |
| Like      |        | + ui      |             | renders   |         | 1/index.. |
+-----------+        | + access  |             | HTML per  |         | styles.css|
      |              | + methods |             | entity    |         | index.html|
      |              +-----------+             +-----------+         +-----------+
      |                                              ^
      v                                              |
StorableMixin                                  Jinja2 macros
  .list()                                      replicate
  .get()                                       form.js logic
```

The critical insight: **PyBend already has everything a static site generator needs except the template engine.** The schema carries field types, widgets, groups, access rules. `StorableMixin` provides data access. The exporter just connects them with Jinja2 (Python's standard template engine) instead of with JavaScript.

### How SSG Differs from Other Approaches

| Strategy | TTFB | LCP | JS Shipped | Server? |
|---|---|---|---|---|
| Full SSG | <50ms | 0.3-0.5s | Zero-minimal | No (CDN only) |
| ISR | <50ms cached | 0.4-0.8s | Minimal | Edge functions |
| SSR | 100-500ms | 0.8-2.0s | Moderate | Yes |
| CSR/SPA | 50-200ms empty | 1.5-4.0s | Heavy | API only |
| Current PyBend | 50ms empty | 2-4s | ~150-200KB | Yes (FastAPI) |

Source: CONDENSED-01-05.md, Sparkbox benchmarks, Enterspeed SSR benchmarks.

### What SSG Cannot Do

SSG has hard limits: real-time data, personalized content, authenticated pages, highly interactive UIs, rapidly changing inventory, and search over large datasets. These are architectural boundaries, not soft limits.

**PyBend's position:** The static exporter targets the **read-only, public-facing** slice of an application. The dynamic FastAPI stack remains for everything else. This is not a replacement; it is an additional deployment option.

---

## 2. Industry Landscape

### So What?

Static site generation is a mature, growing market. The Jamstack ecosystem reached $8.6 billion in 2025 and is projected at ~$12 billion by 2026. 60% of new projects use a static-first approach. Major companies (Smashing Magazine, L'Oreal, Nour Hammour) report 10x speed improvements and 63-128% conversion increases after migrating to static. The Python SSG ecosystem (Pelican, MkDocs, Sphinx) is blog/docs-focused and cannot generate HTML from data models. This is PyBend's opening.

### Market Size and Growth

| Indicator | 2020 | 2025-2026 | Trend |
|---|---|---|---|
| Jamstack market value | $1.8B | $8.6-12B | 4.8x in 5 years |
| Developer static-first adoption | ~15% | 35%+ | Doubling |
| New projects using Jamstack | 27% | 60% | Mainstream |
| Prerendered sites in top 10K | ~0.3% | ~0.5% | +67% YoY |
| Headless CMS market | - | $2.5B (projected) | 73% enterprise adoption |

Sources: CONDENSED-01-05.md (Jamstack market data), CONDENSED-06-10.md (prerendered site statistics, headless CMS data), KeenComputer white paper, eSparkInfo industry reports.

### SSG Framework Landscape

| Generator | Type | 1K-Page Build | Stars | Schema-Driven? |
|---|---|---|---|---|
| Hugo (Go) | Content-first | <1s | ~78K | No |
| Eleventy (JS) | Content-first | 2-5s | ~17K | No |
| Pelican (Python) | Content-first | 5-15s | ~13K | No |
| Next.js (React) | Framework-first | 10-30s | ~128K | No |
| Astro (JS) | Framework-first | 3-8s | ~48K+ | No |
| Gatsby (React) | Framework-first | 30-120s | ~56K | No |
| **PyBend (proposed)** | **Schema-driven** | **2-5s (est.)** | - | **Yes (unique)** |

Source: CONDENSED-06-10.md (SSG ecosystem table), HTTP Archive 2025.

> **The gap:** Every generator requires handwritten templates. Not one generates HTML from a data schema. PyBend would be the first where `Model definition -> Deployable website` requires zero template authoring.

### The Python Ecosystem Gap

Existing Python SSGs -- Pelican, MkDocs, Sphinx, Lektor, Nikola -- expect Markdown or reStructuredText input. They are designed for blogs and documentation. None can:

1. Read a JSON Schema with UI hints, field order, groups, and access rules
2. Generate HTML pages for entity lists and detail views
3. Handle parent-child relationships (Product -> Comments)
4. Produce paginated collection pages
5. Apply theme-aware styling from component CSS

Frozen-Flask is the closest analogy (it simulates WSGI requests and writes responses to files), but it assumes Flask routes returning HTML. PyBend routes return JSON. A custom Jinja2 pipeline provides full control.

Source: CONDENSED-06-10.md (Python SSG landscape).

### Case Studies with Hard Numbers

**Smashing Magazine** (WordPress to Hugo + Netlify):
- Load time: 800ms to 80ms (10x improvement)
- 7,500 pages build in 13 seconds
- Source: CONDENSED-06-10.md, Smashing Magazine engineering blog

**Nour Hammour** (Fashion e-commerce, headless static build):
- Conversion increase: 63%
- Sales increase: 128% year-over-year
- Source: CONDENSED-06-10.md, Nour Hammour case study

**L'Oreal "Website Factory"** (3,000 managed sites):
- Load time: 10+ seconds to <3 seconds
- Source: CONDENSED-06-10.md

**GOV.UK** (Custom Ruby SSG, progressive enhancement):
- Lighthouse: 99/100
- Mandates HTML-first, JS is additive
- WCAG 2.1 AA compliance
- Reduced CSS by 93% and JS by 61% migrating to Design System
- Source: CONDENSED-06-10.md

**Full Stack Python** (Pelican, entirely static):
- Serves millions of readers
- Zero JavaScript
- Zero hosting cost on GitHub Pages
- Source: CONDENSED-06-10.md

### The Speed-to-Revenue Connection

Google's research with neural network models (90% prediction accuracy):

```
LOAD TIME VS. BOUNCE PROBABILITY
================================================================

Bounce
Probability
Increase
  ^
  |                                              +123%
  |                                         /
  |                                    /
  |                               /
  |                          +90%
  |                     /
  |                /
  |           +32%
  |      /
  | /
  +--+--------+--------+--------+--------+---------> Load Time
     1s       2s       3s       4s       5s       10s
```

| Load Time Change | Bounce Impact | Conversion Impact |
|---|---|---|
| Each 0.1s improvement | - | +8-10% (e-commerce) |
| 1s to 3s | +32% bounce | ~-13% conversion |
| 1s to 5s | +90% bounce | ~-22% conversion |
| 1s to 10s | +123% bounce | Catastrophic |
| 2.4s vs 5.7s | - | 1.9% vs 0.6% (3.2x) |
| LCP 2.5s to 1.5s (Pinterest) | - | +15% sign-up conversion |

Sources: CONDENSED-01-05.md (Google/SOASTA research, Deloitte study, Pinterest/Vodafone case studies).

A static PyBend export targeting <1s LCP (achievable with CDN-served HTML) moves pages from the "3-5s danger zone" into the "sub-1s fast lane." For any PyBend user with e-commerce or lead-gen use cases, this is a revenue-impacting capability.

### Hosting Economics and Security

Static hosting is effectively free: Cloudflare Pages (unlimited bandwidth), GitHub Pages (100 GB/month), Netlify (100 GB/month). At 10K daily visitors, static costs $0-5/month vs $24-100/month for dynamic. A developer who defines three models, seeds 100 entities, and runs `pybend export` gets a deployable website with zero hosting cost.

Static sites also eliminate entire classes of runtime vulnerability: SQL injection (no database), server-side XSS (no server rendering), server misconfiguration (no server), DDoS (CDN-absorbed across 300+ nodes), and dependency exploits (build-time only). The attack surface reduces to CDN infrastructure and DNS.

Source: CONDENSED-06-10.md (hosting economics, security advantages).

---

## 3. Technical Architecture: Schema-to-Jinja2-to-HTML Pipeline

### So What?

The static exporter replaces the bottom four stages of PyBend's current rendering pipeline (NTT.js DynamicClass, form.js, ntt-item.js, Shadow DOM) with a Python-side Jinja2 template pipeline. The schema is the same. The data access is the same. Only the rendering engine changes: JavaScript in the browser becomes Python on the developer's machine. The output is plain HTML files that work anywhere.

### Current vs. Proposed Pipeline

```
CURRENT:  Model -> schema() -> FastAPI -> Browser JS -> Shadow DOM -> User sees content
PROPOSED: Model -> schema() -> list()  -> Jinja2     -> HTML files -> User sees content
                   (SAME)      (SAME)     (NEW)        (NEW)         (immediate, 0 JS)
```

**Nothing changes upstream of the renderer.** Same models, same schema generation, same storage backend. The exporter is a consumer of existing PyBend infrastructure, not a replacement for any of it.

### The Rendering Algorithm

The static renderer is a 1:1 port of `form.js` `getForm()` and `getInput()`. It reads `schema.properties` and `schema.ui`, determines field order, filters renderable fields (excluding headers, `ui.display=false`, `ui.protected`, and access-denied fields), generates the header (name as `<h2>`, description as `<h4>`), renders grouped or flat fields, and dispatches per field on type/widget: string to `<div>`, currency to `<div class="currency-display">$X.XX</div>`, textarea to `<div class="text-block">`, arrays with `$ref` to recursive child rendering. The Jinja2 macro equivalent is ~200 lines vs form.js at 368, because static export eliminates edit mode, event binding, and permission checking.

Source: CONDENSED-06-10.md, form.js lines 17-64.

### Template Structure

Jinja2 macros mirror the JavaScript pipeline 1:1: `field.html.j2` replaces `form.js getInput()`, `header.html.j2` replaces `getHeader()`, `card_sm/md.html.j2` replaces `ntt-item.js sm()/md()`, `list_field.html.j2` replaces `getListInput()`, and `pagination.html.j2` replaces `ntt-list.js` load-more. Base layout, collection page, entity page, and index page templates complete the hierarchy.

### Output File Structure

The exporter uses the nested `index.html` convention (e.g., `dist/products/index.html` for `/products/`, `dist/products/1/index.html` for `/products/1/`). This works universally on GitHub Pages, Cloudflare Pages, Netlify, S3, and nginx without URL rewrite rules. The structure maps directly to PyBend's API URL patterns. A combined `styles.css` (~8KB gzipped) and optional self-hosted fonts complete the output.

Source: CONDENSED-06-10.md (output structure section).

### CSS Pipeline

Component CSS today lives inside Shadow DOM. The static exporter concatenates and transforms it into a single external stylesheet:

| CSS Source | Lines | Transformation |
|---|---|---|
| `dark-theme.css` | 408 | Full inclusion (design tokens, layout) |
| `light-theme.css` | 119 | Full inclusion (theme overrides) |
| `ntt-item.css` | 669 | Transform `:host` to `.ntt-item` class selector |
| `ntt-list.css` | 81 | Transform `:host` to `.ntt-list` class selector |
| `ntt-element.css` | 71 | Partial (error/empty states only) |
| **Total** | **~1,307** | **~35KB unminified, ~8KB gzipped** |

The `:host` to class-selector transformation is straightforward regex:
- `:host { ... }` becomes `.ntt-item { ... }`
- `:host(.editing) { ... }` becomes `.ntt-item.editing { ... }`
- `:host > .content` becomes `.ntt-item > .content`

External dependency: Google Fonts (Inter, JetBrains Mono). The exporter offers two options: include `<link>` tag (default, requires internet) or self-host fonts (add `--self-host-fonts` flag, downloads to `dist/assets/fonts/`).

Source: CONDENSED-06-10.md (CSS extraction table).

### Build Performance Estimates

Build times are I/O-dominated (database reads, file writes), not computation. No AST parsing or dependency resolution.

| Scale | Entities | Est. Build Time | Output Size |
|---|---|---|---|
| Small (100 entities, 3 models) | 100 | <1 second | ~500KB |
| Medium (1K entities, 5 models) | 1,000 | 2-5 seconds | ~5MB |
| Large (10K entities, 10 models) | 10,000 | 15-30 seconds | ~50MB |
| Incremental (1 entity change) | 1 | <1 second | 1 file |

Performance lands in the Eleventy/Jekyll range (faster than Gatsby, slower than Hugo). The input is pre-parsed JSON with no Markdown processing.

Source: CONDENSED-01-05.md, CONDENSED-06-10.md.

### Authorization Strategy

**Recommended: Public-only export.** Export only what the `ANYONE` access rule permits. Filter models by `__access__.read`, fields by field-level `access.view`. Zero auth complexity. Optional: `pybend export --role=user` for per-role builds (Phase 3). Do not attempt client-side JS auth gates -- that defeats the zero-JS goal.

Source: CONDENSED-06-10.md (authorization strategies).

### Hybrid Mode: Static + NTT Hydration

`NTT.js` (lines 237-277) already has `consumePreloadedSchema()` and `consumePreloadedData()` infrastructure, reading inline `<script data-ntt-schema>` and `<script data-ntt-data>` tags. The exporter can emit both pre-rendered HTML (instant zero-JS display) and inline data tags (for progressive NTT hydration if JS is included). Pages load instantly as static HTML; adding JS makes them interactive. The static site works either way.

Source: CONDENSED-06-10.md (hybrid mode discovery).

---

## 4. CSS-Only Interactivity: The Near-Zero JS Angle

### So What?

Modern CSS (2025-2026) provides native mechanisms for 80-90% of interactive patterns users expect from an SPA. Accordions, tabs, modals, filters, carousels, theme switching, tooltips -- all achievable with CSS and HTML alone, zero JavaScript. The irreducible JavaScript for a static PyBend site with form submission is **~600-800 bytes minified** (<400 bytes gzipped). Compare: React 42KB, Alpine.js 6KB, current PyBend SPA ~150-200KB.

### CSS-Only Pattern Inventory

| Pattern | HTML/CSS Mechanism | Browser Support | Replaces |
|---|---|---|---|
| Accordions | `<details>/<summary>` | 97.5% | JS `.show-more-btn` handler |
| Tabs / navigation | `:target` pseudo-class | 99%+ | JS tab switching logic |
| Filters | `:checked` + `:has()` | 95%+ | JS filter functions |
| Theme switching | `prefers-color-scheme` + `:checked` | 96%+ | JS theme toggle |
| Modals | `<dialog>` + Popover API | 90%+ | JS modal open/close |
| Carousels | `scroll-snap` | 96% | JS slider libraries |
| Responsive layouts | Container queries | 95%+ | JS resize observers |
| Page transitions | View Transitions API | 70-85% | JS route animations |
| Tooltips | Popover API + anchor positioning | Progressive | JS tooltip libraries |
| Auto-numbering | CSS `counter()` | 99%+ | JS count computation |
| Parent-based state | `:has()` selector | 95%+ | JS parent class toggling |

Source: CONDENSED-06-10.md (CSS-only interactivity section, pattern-by-pattern mapping).

### Mapping to PyBend Components

| PyBend Feature | JS Implementation | CSS-Only Replacement |
|---|---|---|
| Nested entity lists | "Show N more" button | `<details>/<summary>` -- native keyboard, screen reader support |
| Field groups (ui.groups) | `<fieldset>` with JS | `:target` tabs with `:has()` default-first fallback |
| Adaptive sizes (xs-xl) | JS size method dispatch | Container queries: `@container card (max-width: 200px)` etc. |
| Delete confirmation | `window.confirm()` | `<dialog>` element -- native focus trap, Escape to close |
| Theme switching | JS toggle | `prefers-color-scheme` + `:checked` checkbox |
| Item counting | JS `.list-field-count` | CSS `counter()` |

Each replacement produces accessible HTML with native keyboard navigation and zero JavaScript.

### What Absolutely Requires JavaScript

| Capability | Min JS (minified) | Why |
|---|---|---|
| Form submission to API | ~200 bytes | `fetch()` with auth headers |
| Authentication (JWT) | ~400 bytes | Token storage, login/logout |
| Real-time updates (SSE/WS) | ~300 bytes | EventSource/WebSocket |
| Clipboard operations | ~50 bytes | `navigator.clipboard` |
| Complex drag-and-drop | ~500 bytes | Pointer events |
| Dynamic data fetching | ~150 bytes | `fetch()` on interaction |
| Custom form validation | ~200 bytes | Beyond HTML5 validation |

**Total for a static PyBend site with form submission: ~600-800 bytes minified, <400 bytes gzipped.**

The form handler is ~200 bytes: `querySelectorAll('form[data-api]')` + `fetch()` + auth header injection. This is the entire JavaScript footprint for a site that submits data.

Source: CONDENSED-06-10.md (irreducible JS analysis, tiny JS architecture).

### Progressive Enhancement Tiers

```
TIER ARCHITECTURE
================================================================

Tier 1: Pure HTML+CSS (0 bytes JS)
  - Content readable
  - Navigation via <a> + :target
  - Accordions via <details>
  - Theme via prefers-color-scheme
  - Forms visible but NOT submittable
  USE: Read-only catalogs, documentation, portfolios

Tier 2: Tiny JS (<1KB)
  - Form submission
  - Login/logout
  - Method invocation buttons
  - Toast notifications
  USE: Interactive catalog, blog with comments

Tier 3: Enhanced JS (1-10KB)
  - Real-time SSE/WebSocket
  - Complex filtering with URL state
  - Drag-and-drop
  - Optimistic UI updates
  USE: Admin dashboard, collaborative editing
```

**Tier 1 is the baseline, not an afterthought.** Every page must work at Tier 1. JavaScript enhances; it never gates. The static exporter targets Tier 1 output with optional Tier 2 enhancement via a single `<script>` tag.

Source: CONDENSED-06-10.md (progressive enhancement ladder).

### Lighthouse Performance Projections

| Architecture | Performance | FCP | LCP | TBT | CLS |
|---|---|---|---|---|---|
| Static HTML+CSS (target) | 98-100 | 0.4-0.6s | 0.5-0.8s | 0ms | 0 |
| Static + tiny JS | 96-100 | 0.4-0.6s | 0.5-0.8s | 0-10ms | 0 |
| SSG (Astro/11ty) | 90-98 | 0.6-1.0s | 0.8-1.5s | 0-50ms | 0-0.05 |
| Current PyBend SPA | 70-90 | 1.0-2.0s | 1.5-3.0s | 50-200ms | 0.05-0.15 |
| Typical React SPA | 50-85 | 1.5-3.0s | 2.0-4.0s | 200-800ms | 0.1-0.25 |

A static PyBend export should score 96-100 on Lighthouse Performance, compared to 70-90 for the current SPA. The improvement comes entirely from eliminating JavaScript from the critical rendering path.

Source: CONDENSED-06-10.md (Lighthouse comparison table).

---

## 5. Our Current Architecture Assessment

### So What?

PyBend is uniquely positioned for static export because the JSON Schema generated by `ProtoModel.schema()` IS the complete rendering specification. No other framework has this. The schema carries field types, widget hints, layout groups, field order, access rules, and method signatures. The exporter reads the same schema the frontend reads -- it just renders it in Python instead of JavaScript. The existing `StorableMixin.list()` and `.get()` provide all data access. The gap is narrow: a Jinja2 template engine (~200 LOC), a CSS transformer (~80 LOC), and an orchestrator (~150 LOC).

### Schema Completeness Inventory

From `proto_model.py` (lines 44-150) and the `schema()` method, the JSON Schema carries:

| Schema Section | Available? | Exporter Usage |
|---|---|---|
| `properties` (field types) | Yes | Field type dispatch (string, number, boolean, array) |
| `properties[].ui.widget` | Yes | Widget specialization (currency, textarea) |
| `properties[].ui.display` | Yes | Field visibility filtering |
| `properties[].ui.protected` | Yes | Protected field filtering |
| `properties[].ui.placeholder` | Yes | Not needed for display mode |
| `ui.field_order` | Yes | Field rendering sequence |
| `ui.groups` | Yes | Fieldset grouping |
| `ui.renderer` | Yes | Component tag selection (not needed for static) |
| `access` (ABAC rules) | Yes | Filter exported content by access level |
| `methods` | Yes | Render method descriptions (no invocation in static) |
| `$defs` (nested schemas) | Yes | Recursive child entity rendering |
| `$id` / `$schema` | Yes | Generate canonical URLs |
| `__tablename__` | Yes | URL path structure |
| `__name__` | Yes | Page titles, navigation labels |

**Verdict: 100% of the schema surface needed for static rendering is already available.** No schema extensions required.

### form.js and ntt-item.js Replication

`form.js` (368 lines) is the primary target. Its logic is deterministic: given (schema, value, mode), it produces HTML. Of the 368 lines, ~180 are display-mode relevant (field dispatch, grouping, headers, list rendering). The remaining ~188 are edit-mode, validation, and event binding -- inapplicable to static export. **~200 lines of Jinja2 replicate the display-mode subset.**

`ntt-item.js` (660 lines) has five size methods (xs/sm/md/lg/xl), all fully pre-computable from schema + data. The exporter uses `sm` for list pages (card grid) and `md` for detail pages (full entity view), matching the dynamic UI's presentation.

### Gap Analysis

The gaps are narrow. Medium-effort items: Jinja2 field rendering (2-3 days), nested entity resolution (1 day). Small-effort items: CSS `:host` transform (0.5 day), pagination macro (0.5 day), CLI (0.5 day), circular reference depth limit (0.5 day). Zero-gap items: FK hydration, access rule evaluation, and data access are all existing infrastructure.

**Total new code: ~980 lines. Estimated: 5-7 engineering days for MVP.**

Source: CONDENSED-06-10.md.

### What Already Exists

The exporter does not start from zero. These PyBend systems are reused as-is:

1. **`ProtoModel.schema()`** -- Full JSON Schema with all UI hints and access rules. Cached (line 56 of proto_model.py).
2. **`StorableMixin.list(limit, offset)`** -- Paginated entity retrieval with FK hydration.
3. **`StorableMixin.get(id)`** -- Single entity retrieval.
4. **`registered_models`** -- Registry of all models in the application.
5. **`_apply_field_exclusion()`** -- Auto-hide convention for internal fields (line 25 of proto_model.py).
6. **`__access__`** rules -- ABAC evaluation for export filtering.
7. **CSS files** -- Component styles already exist in `src/pybend/static/`.

---

## 6. Cost-Benefit Analysis

### So What?

The static exporter's value is strategic, not primarily cost-driven. Infrastructure savings ($5-50/month per project) will never recoup the development investment through direct cost reduction alone. The value is in: (a) a unique market position ("schema to website, zero code"), (b) dramatically better Lighthouse scores for PyBend users, (c) opening the ~30% of web projects that are fully-static-appropriate, and (d) the "zero to deployed" story for marketing and developer adoption.

### Investment Breakdown

**MVP (5-7 days, ~$5K-7K at senior eng rate):**

| Component | LOC | Days | What It Delivers |
|---|---|---|---|
| `renderer.py` -- schema-to-HTML | ~200 | 2-3 | Field rendering, groups, headers |
| `css_compiler.py` -- CSS transformation | ~80 | 0.5 | Single stylesheet from Shadow DOM CSS |
| `exporter.py` -- orchestrator | ~150 | 1 | Model iteration, file writing, pagination |
| Jinja2 templates | ~300 | 1 | base, collection, entity, macros |
| CLI entry point | ~50 | 0.5 | `pybend export` command |
| Tests | ~200 | 1-2 | Rendering correctness, CSS output |
| **Total** | **~980** | **5-7** | **Complete MVP** |

**Full feature (10-16 weeks, $100-160K):**

| Feature | Weeks | What It Adds |
|---|---|---|
| MVP (above) | 1 | Core functionality |
| Incremental rebuild (SHA-256 hashing) | 2-3 | <1s rebuild on single entity change |
| Asset pipeline (images, fonts, sitemap) | 1-2 | Production-ready output |
| Per-role export | 1-2 | Intranet/authenticated site generation |
| Hybrid mode (NTT preloading) | 2-3 | Static + progressive enhancement |
| Custom template overrides | 1-2 | User-provided Jinja2 templates |
| Webhook/CI integration | 1-2 | Auto-rebuild on data change |
| Search (client-side index) | 1-2 | Lunr.js or Pagefind integration |
| Testing + documentation | 1-2 | Full coverage, user docs |

### Return on Investment

**Direct cost savings per project:**

| Hosting Scenario | Dynamic Cost | Static Cost | Monthly Savings |
|---|---|---|---|
| Small (100/day traffic) | $6-20/month | $0/month | $6-20 |
| Medium (1K/day) | $12-50/month | $0/month | $12-50 |
| Large (10K/day) | $24-100/month | $0-5/month | $19-100 |

At $25/month average savings, MVP break-even ($5-7K) requires 200-280 project-months. That is 20 projects running for 1 year, or 200 projects for 1 month. **Direct cost recovery is viable only at scale.**

**Strategic value (harder to quantify, larger impact):**

| Value Driver | Mechanism | Potential Impact |
|---|---|---|
| Unique market position | "Schema to website" -- no competitor offers this | Developer mindshare, press coverage |
| Lighthouse scores | 70-90 to 96-100 | Marketing material, client confidence |
| New use cases | Static catalogs, documentation, portfolios | Addressable market expansion (~30% of web) |
| "Zero to deployed" story | `define model -> export -> deploy to Cloudflare` | Developer adoption, tutorial content |
| SEO capability | Crawlable HTML without JavaScript | Opens SEO-dependent verticals |

### Total Cost of Ownership

**3-Year TCO:** MVP only: $11-19K. MVP + polish: $35-60K. Full feature: $135-225K. At $25/month average savings per project, MVP break-even is ~250 project-months (25 projects for 1 year). **The MVP is cheap enough to justify on strategic value alone.** The full pipeline must be justified by adoption data.

### Comparison with Alternatives

| Approach | Effort | TTFB | Server? | Monthly Cost |
|---|---|---|---|---|
| **Static export (proposed)** | 5-7 days | 10-30ms | No | $0-5 |
| HTTP caching on dynamic stack | 2-3 days | 20-50ms | Yes | $6-50 |
| CDN edge caching | 1 week | 15-40ms | Yes | $6-50 |
| Full SSG with incremental | 10-16 weeks | 10-30ms | No | $0-5 |

Source: CONDENSED-06-10.md.

---

## 7. Decision Framework

### So What?

Not every PyBend application should use static export. The decision depends on three factors: content freshness requirements, audience type (public vs. authenticated), and whether SEO drives revenue. The static exporter is a deployment option, not a mandate. Users who need it will know they need it. Users who do not will continue using the dynamic stack.

### When Static Export Makes Sense

```
DECISION MATRIX
================================================================

                       Content updates     Content updates     Content updates
                       rarely              hourly              constantly
                       (days-weeks)        (minutes-hours)     (seconds)

Public audience        STRONG FIT          GOOD FIT            NOT A FIT
                       Full static         Scheduled rebuild   Use dynamic stack
                       export              (cron or webhook)   with CDN caching

Auth required          CONDITIONAL         NOT A FIT           NOT A FIT
for core features      Static for public   Dynamic stack       Dynamic stack
                       pages only          with caching        with WebSocket

SEO critical           STRONG FIT          GOOD FIT            Streaming SSR
                       regardless of       Any approach that   (not static)
                       other factors       produces crawlable
                                           HTML
```

### Project Type Addressability

| Project Type | % of Web | Static Fit? | Example |
|---|---|---|---|
| Product catalogs | ~8% | Strong | Browse products, no cart |
| Documentation | ~6% | Strong | API docs, guides |
| Blogs / content | ~7% | Strong | Articles, news |
| Landing pages | ~5% | Strong | Marketing pages |
| Portfolios | ~4% | Strong | Personal sites |
| **Subtotal: fully static** | **~30%** | **Yes** | - |
| E-commerce (with cart) | ~12% | Partial (catalog yes, cart no) | Shopify-like |
| SaaS dashboards | ~15% | No | Personalized data |
| Social platforms | ~8% | No | User-generated content |
| Internal tools | ~10% | No | Auth-gated |
| Marketplaces | ~6% | Partial | Listings yes, transactions no |
| Other dynamic | ~19% | No | - |

Source: CONDENSED-06-10.md (project type addressability), W3Techs 2025.

> **The ~30% static-appropriate segment is PyBend's expansion opportunity.** Today, these projects use Hugo, Eleventy, or hand-coded HTML. With static export, they could use PyBend -- getting the full schema-driven development workflow plus zero-cost deployment.

### Content Freshness Guide

| Content Type | Update Frequency | Rebuild Strategy | Latency |
|---|---|---|---|
| Documentation | Hours to days | Manual trigger / `pybend export` | Minutes |
| Blog posts | Minutes to hours | Webhook on CMS save | Minutes |
| Product catalog | Minutes to hours | Scheduled (every 15-60 min) | Up to 1 hour |
| Pricing | Minutes | Webhook + immediate rebuild | Minutes |
| Landing pages | Days to weeks | Manual trigger | Minutes |
| **Breaking news** | **Seconds** | **NOT SUITABLE for static** | - |
| **Live scores** | **Seconds** | **NOT SUITABLE for static** | - |
| **Chat / messaging** | **Real-time** | **NOT SUITABLE for static** | - |

Source: CONDENSED-06-10.md (content freshness table).

### Anti-Patterns

1. **Making interactive apps static.** If removing JavaScript breaks the core user journey, the project is not static-appropriate. Test: can the user accomplish their primary goal with zero JS? If not, do not export.

2. **Over-engineering the build pipeline.** At <1K pages, full rebuild takes seconds. Incremental builds add complexity for minimal gain. Build that feature when someone actually has 10K+ pages.

3. **Premature export during rapid model iteration.** During active development, models change frequently. Static export adds a rebuild step. Wait until the model stabilizes.

4. **The hybrid "uncanny valley."** If more than 2 features on a page need their own backend call, the page is not static -- it is dynamic with a static shell. Use CDN caching on the dynamic stack instead.

5. **Rebuilding what CDN caching solves.** Adding `Cache-Control` headers to the existing dynamic stack achieves 70-80% of the performance benefit for 10-20% of the effort. Always try this first.

Source: CONDENSED-06-10.md (anti-patterns section).

### Decision Tree

```
Does the project need a running server for its core features?
                    |
         +----------+----------+
         |                     |
        YES                    NO
         |                     |
  Use dynamic stack     Is content mostly public?
  (maybe add CDN              |
   caching)            +-------+-------+
                       |               |
                      YES              NO
                       |               |
                Is SEO important?   Use dynamic stack
                       |            (static export
                +------+------+      won't help)
                |             |
               YES            NO
                |             |
         Static export    Static export is
         is a strong      nice-to-have.
         fit. Build it.   Consider after
                          caching.
```

---

## 8. Recommendation

### So What?

Build the MVP static exporter as a 5-7 day project, but only after implementing HTTP caching on the dynamic stack (1-2 days). The caching work benefits every PyBend user immediately. The exporter benefits the ~30% of projects that are static-appropriate. Together, they cover the full performance spectrum: caching for dynamic, export for static, and the same schema-driven development workflow for both.

### Phased Plan

**Phase 0: HTTP Caching (Now, 1-2 days)**

| Task | Effort | Impact |
|---|---|---|
| Add `Cache-Control: public, max-age=3600` to schema endpoints | 1 hour | Schema served from browser cache |
| Add `Cache-Control: public, max-age=60, stale-while-revalidate=600` to public list endpoints | 1 hour | CDN-friendly list caching |
| Add template caching `Map` in `form.js` | 2 hours | Eliminate re-generation for same schema |
| Document CDN setup (Cloudflare, AWS) for PyBend users | 1 day | Users can front their app with CDN |

**Trigger for Phase 1:** User requests for static export, OR SEO becomes a documented use case.

**Phase 1: MVP Static Exporter (5-7 days)**

| Task | Effort | Deliverable |
|---|---|---|
| `renderer.py` -- schema field dispatch | 2-3 days | Python equivalent of form.js |
| `css_compiler.py` -- CSS concatenation + `:host` transform | 0.5 day | Single `styles.css` |
| Jinja2 templates (base, collection, entity, macros) | 1 day | Complete template set |
| `exporter.py` -- orchestrator (iterate models, paginate, write) | 1 day | File generation pipeline |
| CLI entry point (`pybend export`) | 0.5 day | User-facing command |
| Tests (rendering correctness, CSS, pagination) | 1-2 days | CI-verifiable quality |

**Integration API (three levels):**

```python
# Level 1: One-liner
from pybend import export_static
export_static(app, output="./dist")

# Level 2: Builder
pb = PyBendApp(storage="sqlite:///app.db")
pb.model(Product).model(User)
pb.export(output="./dist", theme="dark")

# Level 3: CLI
pybend export --static --db sqlite:///app.db --output ./dist
```

**Trigger for Phase 2:** 10+ users actively using `pybend export`, OR a specific customer requirement.

**Phase 2: Polish (2-3 weeks, when warranted)**

| Feature | Effort | Value |
|---|---|---|
| Incremental rebuild (SHA-256 content hashing) | 2-3 days | <1s rebuild for single entity change |
| Image download + URL rewriting | 1-2 days | Self-contained output |
| Navigation / breadcrumbs | 1 day | Better user experience |
| Index page (model directory) | 0.5 day | Landing page |
| Sitemap generation | 0.5 day | SEO completeness |
| Asset fingerprinting (`styles.a1b2c3.css`) | 0.5 day | Long-term caching |

**Phase 3: Advanced (4-6 weeks, when scale demands)**

| Feature | Effort | Value |
|---|---|---|
| Per-role export (`--role=user`) | 1-2 weeks | Intranet / authenticated sites |
| Hybrid mode (NTT preloading) | 2-3 weeks | Progressive enhancement |
| Custom Jinja2 template overrides | 1-2 weeks | User customization |
| Search integration (Pagefind / Lunr.js) | 1-2 weeks | Client-side full-text search |

### Module Structure

```
src/pybend/core/export/
    __init__.py                 Public API: export_static()
    exporter.py     (~150 LOC) Main orchestrator
    renderer.py     (~200 LOC) Schema-to-HTML (port of form.js)
    css_compiler.py  (~80 LOC) CSS aggregation + :host transform
    templates/
        base.html.j2            Base layout
        collection.html.j2      List page with pagination
        entity.html.j2          Detail page
        index.html.j2           Model directory
        macros/
            field.html.j2       Per-field type dispatch
            header.html.j2      Entity header
            card_sm.html.j2     Small card (list view)
            card_md.html.j2     Medium card (detail view)
            list_field.html.j2  Nested entity list
            pagination.html.j2  Page navigation
    cli.py           (~50 LOC) Click/Typer entry point
    tests/
        test_renderer.py        Field rendering tests
        test_css.py             CSS transformation tests
        test_exporter.py        Integration tests
```

### What NOT to Do

| Do NOT | Why Not | What Instead |
|---|---|---|
| Build a Node.js SSR layer | Violates Python-only philosophy | Python-side Jinja2 rendering |
| Use Puppeteer/Playwright pre-rendering | 300MB-1GB RAM per instance, fragile | Schema compiler on structured data |
| Make export mandatory | Breaks "zero to working" philosophy | Opt-in CLI command |
| Build incremental rebuilds in MVP | Over-engineering for <1K pages | Full rebuild in MVP (<5s) |
| Export authenticated content by default | Security risk, complexity | Public-only default, `--role` flag optional |
| Compile data into templates at build time | Creates staleness | Templates + data separate |
| Add search in MVP | Requires client-side JS index | Defer to Phase 3 |

### Success Metrics

| Phase | Metric | Target |
|---|---|---|
| Phase 0 | Schema endpoint TTFB (repeat visit) | <50ms |
| Phase 0 | Public list endpoint TTFB (CDN-cached) | <100ms |
| Phase 1 | Export build time (100 entities, 3 models) | <2 seconds |
| Phase 1 | Lighthouse Performance (exported site) | >95 |
| Phase 1 | Total JS shipped (Tier 1 export) | 0 bytes |
| Phase 1 | Output correctness (field rendering match) | 100% of form.js display output |
| Phase 2 | Incremental rebuild time (1 entity change) | <1 second |
| Phase 2 | Active users of `pybend export` | 10+ |
| Phase 3 | Hybrid page FCP | <500ms |

---

## 9. Risk Register

### So What?

The risks fall into two categories: timing risks (building too much too soon or too late) and technical risks (rendering correctness, CSS compatibility, data staleness). The timing risks are higher-impact and higher-probability. The technical risks are well-understood and have standard mitigations.

### Probability-Impact Matrix

```
RISK PROBABILITY-IMPACT MATRIX
================================================================

Impact
  ^
  |                    [R3]         [R1]
  |  High              Data        Over-engineering
  |                    staleness   for current
  |                    in prod     scale
  |                                [R2]
  |                                Opportunity
  |                                cost
  |
  |                    [R5]         [R6]
  |  Medium            Rendered    Schema changes
  |                    HTML        break export
  |                    diverges
  |                    from SPA    [R8]
  |                                FK hydration
  |                                gaps
  |
  |     [R4]           [R7]
  |  Low  CSS compat   Large
  |       issues       dataset
  |                    build time
  |
  +------+-------------+------------+----------->
         Low           Medium       High
                    Probability
```

### Detailed Risk Assessment

**R1: Over-engineering for current scale**
- **Probability:** High
- **Impact:** High
- **Description:** Building full-feature static export (incremental builds, search, hybrid mode) before any user requests it wastes 10-16 weeks of engineering time.
- **Mitigation:** Start with MVP only (5-7 days). Measure adoption before building Phase 2-3. Each phase requires a trigger metric.
- **Owner:** Product/CEO

**R2: Opportunity cost -- exporter displaces higher-value work**
- **Probability:** High
- **Impact:** Medium-High
- **Description:** Engineering time spent on static export cannot be spent on core framework features, customer requests, or bug fixes.
- **Mitigation:** MVP is 5-7 days -- a contained bet. If it does not gain traction in 3 months, deprioritize. Do not commit to Phase 2-3 without adoption data.
- **Owner:** Product/CEO

**R3: Data staleness in production**
- **Probability:** Medium
- **Impact:** High
- **Description:** Users export a site, deploy it, and data changes. The static site shows stale information. If the content is pricing or inventory, staleness has direct revenue impact.
- **Mitigation:** Documentation clearly states freshness limitations. CLI outputs timestamp of last export. Webhook integration (Phase 3) enables auto-rebuild. Position static export for infrequently-changing content only.
- **Owner:** Documentation/Engineering

**R4: CSS compatibility issues**
- **Probability:** Low
- **Impact:** Low
- **Description:** The `:host` to class-selector CSS transformation may miss edge cases, producing visual differences between static export and dynamic SPA.
- **Mitigation:** Snapshot visual testing of exported pages against SPA rendering. The CSS transformation is simple regex -- edge cases are enumerable and testable.
- **Owner:** Frontend

**R5: Rendered HTML diverges from SPA rendering**
- **Probability:** Medium
- **Impact:** Medium
- **Description:** The Jinja2 renderer produces HTML that looks different from what `form.js` + `ntt-item.js` produce. Users expect visual parity.
- **Mitigation:** Side-by-side snapshot testing. The renderer mirrors form.js logic exactly (same field dispatch, same group handling, same header structure). Discrepancies are bugs to fix, not fundamental issues.
- **Owner:** QA/Engineering

**R6: Schema changes break export output**
- **Probability:** Medium-High
- **Impact:** Medium
- **Description:** Adding a new field type, widget, or UI hint to the schema that the exporter does not handle produces broken or incomplete HTML.
- **Mitigation:** Exporter tests run against all registered models in CI. Unknown field types fall back to `<div>value</div>` (safe default). CI fails if any model produces rendering errors.
- **Owner:** Engineering

**R7: Large dataset build times**
- **Probability:** Low (most PyBend apps are <1K entities)
- **Impact:** Low
- **Description:** At 100K+ entities, full rebuild takes 2-5 minutes. This is acceptable for scheduled rebuilds but frustrating for development.
- **Mitigation:** Incremental rebuild (Phase 2) reduces to <1s for single entity change. Full rebuild is a production concern, not a development concern.
- **Owner:** Engineering

**R8: FK hydration gaps**
- **Probability:** Medium
- **Impact:** Medium
- **Description:** `StorableMixin.list()` returns hrefs (URLs) for FK fields, not objects. The exporter needs actual entity data to render child entities.
- **Mitigation:** Use `StorableMixin.get()` per parent entity (fetches hydrated objects), or add a `populate=True` mode to `list()`. The data access pattern is different from API serving but not architecturally complex.
- **Owner:** Engineering

### Risk Mitigation Summary

The highest risks are organizational (R1, R2), not technical. The primary mitigation is disciplined phasing: build the MVP, measure adoption, decide on further investment based on data. The technical risks (R3-R8) are all well-understood problems with standard solutions.

The single most dangerous scenario is: **building the full 10-16 week pipeline with zero user demand.** The MVP approach ($5-7K, 5-7 days) makes this a $5K bet, not a $100K bet.

---

## 10. Appendices

### Appendix A: Glossary

| Term | Definition |
|---|---|
| **CDN** | Content Delivery Network. Distributed servers caching content near users. |
| **CLS** | Cumulative Layout Shift. Visual stability metric (Core Web Vital). |
| **Core Web Vitals** | Google's three metrics: LCP, INP, CLS. Affect search ranking. |
| **DSD** | Declarative Shadow DOM. HTML-only shadow roots without JavaScript. |
| **FCP** | First Contentful Paint. Time until first content renders. |
| **Hydration** | Making server-rendered HTML interactive by attaching JS event handlers. |
| **ISR** | Incremental Static Regeneration. Cached static HTML regenerated on schedule. |
| **Jamstack** | Architecture pattern: JavaScript + APIs + Markup. Pre-rendered sites with API backends. |
| **Jinja2** | Python's standard template engine. Used by Flask, Django (as DTL), Ansible. |
| **LCP** | Largest Contentful Paint. Time until largest visible element renders (Core Web Vital). |
| **SSG** | Static Site Generation. Building HTML at build time, not request time. |
| **SSR** | Server-Side Rendering. Building HTML on each request. |
| **SWR** | Stale-While-Revalidate. Cache strategy: serve stale, fetch fresh in background. |
| **TBT** | Total Blocking Time. Main thread blocking between FCP and TTI. |
| **TTFB** | Time to First Byte. Time from request to first response byte. |
| **TTI** | Time to Interactive. Time until page responds to user input. |

### Appendix B: Deployment Targets

| Platform | TTFB | Free Tier | Deploy Method |
|---|---|---|---|
| Cloudflare Pages | ~57ms | Unlimited BW, 500 build min/mo | Git push or wrangler CLI |
| AWS S3 + CloudFront | ~50ms | 1TB free (first year) | aws s3 sync |
| GitHub Pages | ~80ms | 100GB/mo (public repos) | Git push |
| Vercel | ~100ms | 100GB/mo | Git push |
| Netlify | ~227ms | 100GB/mo, 300 build min/mo | Git push or CLI |
| Any nginx | Varies | Full control | rsync or CI |

Source: CONDENSED-06-10.md (deployment targets table).

### Appendix C: Implementation Blueprint

**New files (~980 LOC total):** `src/pybend/core/export/` package containing `exporter.py` (orchestrator, ~150 LOC), `renderer.py` (schema-to-HTML port of form.js, ~200 LOC), `css_compiler.py` (CSS aggregation + `:host` transform, ~80 LOC), `cli.py` (CLI entry point, ~50 LOC), Jinja2 templates (base, collection, entity, index + macros for field, header, cards, pagination, ~300 LOC), and tests (~200 LOC).

**Modified files:** `src/pybend/__init__.py` (export `export_static`), `src/pybend/core/app.py` (add `export()` to `PyBendApp`), `pyproject.toml` (Jinja2 dependency, CLI entry point).

**Relationship to prior analysis:** html-compiler-analysis.md evaluated template compilation (pre-building templates at server start for faster dynamic serving). This document evaluates full static site export (writing HTML files to disk, eliminating the server). Both share the same schema-to-HTML rendering core.

### Appendix F: Source References

**Research Documents:**
- CONDENSED-01-05.md -- HTML compiler research synthesis (industry landscape, technical approaches, decision framework, PyBend architecture fit, static shell + islands)
- CONDENSED-06-10.md -- Static site research synthesis (SSG industry, technical pipeline, decision framework, PyBend export architecture, CSS-only interactivity)
- html-compiler-analysis.md -- Prior analysis of template compilation approach

**Underlying Research (10 documents):**
- 01-industry-landscape.md -- Market data, framework comparison, case studies
- 02-technical-deep-dive.md -- Compilation strategies, hydration, DSD
- 03-decision-framework.md -- ROI, TCO, migration strategies
- 04-our-stack-relevance.md -- PyBend schema surface map, runtime cost analysis
- 05-static-shell-dynamic-islands.md -- Islands architecture, Web Component mapping
- 06-static-industry-landscape.md -- SSG market, case studies, hosting economics
- 07-static-technical-deep-dive.md -- SSG pipeline, CSS generation, build systems
- 08-static-decision-framework.md -- Static decision criteria, anti-patterns
- 09-static-pybend-architecture.md -- PyBend export architecture, gap analysis
- 10-css-only-interactivity.md -- CSS patterns, progressive enhancement, minimal JS

**Codebase Files Analyzed:**
- `src/pybend/core/models/proto_model.py` -- Schema generation, field exclusion, response metadata
- `src/pybend/static/generators/form.js` -- Schema-driven form rendering (primary replication target)
- `src/pybend/static/components/ntt-item.js` -- Size methods, render dispatch
- `src/pybend/static/core/NTT.js` -- DynamicClass creation, preload infrastructure

**Key External Sources:**
- [Sparkbox: UI Rendering Frameworks Comparison](https://sparkbox.com/foundry/ui_rendering_frameworks_next.js_astro_qwik_rendering_strategies_tested_time_to_interactive_total_blocking_time_largest_contentful_paint_measured)
- [Google/Deloitte: Mobile Page Speed Industry Benchmarks](https://business.google.com/ca-en/think/marketing-strategies/mobile-page-speed-new-industry-benchmarks/)
- [KeenComputer: Jamstack & SSGs 2025-2026](https://www.keencomputer.com/solutions/software-engineering/880-research-white-paper-the-future-of-web-architecture-jamstack-and-static-site-generators-as-the-foundation-of-agile-digital-transformation-2025-2026)
- [Cloudflare Pages Pricing](https://pages.cloudflare.com/)
- [Enterspeed: SSR Performance of 6 JS Frameworks](https://www.enterspeed.com/blog/we-measured-the-ssr-performance-of-6-js-frameworks-heres-what-we-found)
- [Netflix Web Performance Case Study](https://medium.com/dev-channel/a-netflix-web-performance-case-study-c0bcde26a9d9)
- [eBay: The Future of Marko](https://innovation.ebayinc.com/tech/engineering/the-future-of-marko/)

---

*Analysis compiled February 2026. Based on 10 research documents covering 70+ external sources, two research syntheses, and direct codebase analysis of PyBend's rendering pipeline. Performance estimates are projections based on industry benchmarks applied to PyBend's architecture; actual results will vary based on implementation, deployment infrastructure, and usage patterns.*
