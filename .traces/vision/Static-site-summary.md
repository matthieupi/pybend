# Static Site Generation for PyBend: Executive Summary

> *Full analysis: [static-site-analysis.md](../research/html-compiler/static-site-analysis.md)*

---

## The Question

Should PyBend offer a `pybend export` command that generates a complete, deployable static website -- HTML pages, CSS, pagination, navigation -- directly from schema-driven model definitions, with near-zero JavaScript?

**Answer: Yes.** Build the MVP in 5-7 engineering days. Position it as PyBend's "zero to deployed" capability: define a model, get a website. No server. No JavaScript. No hosting costs.

This extends PyBend's core promise:

> **Today:** _"Define a model, get a working full-stack application."_
> **With static export:** _"Define a model, get a deployable website."_

---

## Key Findings

### The Whitespace Opportunity

No existing framework -- not Hugo, not Astro, not Next.js, not any Python SSG -- generates static HTML from data model definitions. Every one requires handwritten templates or components.

PyBend's JSON Schema already carries **complete rendering instructions**: field types, widget hints, layout groups, field order, access rules, method signatures. The static exporter reads the schema, walks the data, and writes HTML files. **The schema IS the template.** Zero template authoring required.

### The Numbers That Matter

```
PERFORMANCE: CURRENT SPA vs. STATIC EXPORT
================================================================

                 Current PyBend        Static Export        Delta
                 (SPA)                 (Target)
TTFB             200-500ms             20-80ms              3-10x faster
LCP              2-3s                  500ms-1s             2-4x faster
TBT              100-300ms             0ms                  Eliminated
JS shipped       ~150-200KB            0-800 bytes          200x less
Lighthouse       60-85                 95-100               Near-perfect
Page weight      200-400KB             20-50KB              5-10x lighter
```

### The Business Impact of Speed

| Load Time Change | User Impact | Source |
|---|---|---|
| Each 0.1s improvement | +8-10% conversion (e-commerce) | Google/Deloitte |
| 1s to 3s | +32% bounce probability | Google/SOASTA |
| 1s to 5s | +90% bounce probability | Google/SOASTA |
| 2.4s vs 5.7s | 1.9% vs 0.6% conversion (3.2x) | Conductor |
| Pinterest LCP 2.5s to 1.5s | +15% sign-up conversion | Pinterest engineering |

Static export moves pages from the "3-5 second danger zone" into the "sub-1-second fast lane."

### Hosting Economics

| Traffic | Static (CDN) | Dynamic (VPS) | Savings |
|---|---|---|---|
| 100/day | $0/month | $6-20/month | 100% |
| 1K/day | $0/month | $12-50/month | 100% |
| 10K/day | $0-5/month | $24-100/month | 80-100% |
| 100K/day | $5-20/month | $48-200/month | 75-90% |

Free CDN tiers: Cloudflare Pages (unlimited bandwidth), GitHub Pages (100 GB/month), Netlify (100 GB/month). A developer who exports a PyBend site has zero hosting costs.

---

## Industry Context

| Market Signal | Data Point |
|---|---|
| Jamstack market | $8.6B (2025), ~$12B projected (2026) |
| New projects using static-first | 60% (up from 27% in 2020) |
| Headless CMS enterprise adoption | 73% |
| Prerendered sites growth in top 10K | +67% year-over-year |

**Case studies:**
- Smashing Magazine (WordPress to Hugo): **10x faster** load (800ms to 80ms)
- Nour Hammour (fashion): **63% conversion increase**, **128% sales increase**
- L'Oreal Website Factory (3,000 sites): Load **10s to <3s**
- GOV.UK: Lighthouse **99/100**, mandates progressive enhancement

**The Python SSG gap:** Existing Python SSGs (Pelican, MkDocs, Sphinx) expect Markdown input and are blog/docs-focused. None generate HTML from data model schemas. PyBend would be the first.

---

## Where We Stand

### Why PyBend Is Uniquely Positioned

No other framework on the market has a schema that carries complete rendering instructions. Every SSG -- Hugo, Astro, Next.js, Eleventy -- requires handwritten templates. PyBend's `ProtoModel.schema()` already encodes field types, widget hints, layout groups, field order, access rules, and method signatures. The exporter reads the same JSON Schema the frontend reads. It just renders in Python instead of JavaScript.

The schema IS the template specification:

```
Schema Property                    What the Exporter Renders
================================================================
properties.name.type: "string"     <h2>Widget Pro</h2>
properties.price.ui.widget:        <div class="currency">$29.99</div>
  "currency"
ui.field_order                     Fields in specified sequence
ui.groups.main                     <fieldset><legend>Main</legend>...</fieldset>
access.read: ANYONE                Included in public export
methods.comment                    Rendered as description (no invocation)
$defs.Comment                      Nested child entity rendering
```

**What exists and is reused as-is:** `ProtoModel.schema()`, `StorableMixin.list()`, `StorableMixin.get()`, `registered_models`, `__access__` rules, component CSS files.

**What needs to be built:** Jinja2 field-rendering macros (~200 LOC), CSS `:host` transformer (~80 LOC), export orchestrator (~150 LOC), templates (~300 LOC), CLI (~50 LOC), tests (~200 LOC). **Total: ~980 lines, 5-7 days.**

**CSS-only interactivity** covers 80-90% of expected SPA interactions:
- Accordions: `<details>/<summary>` (97.5% support)
- Tabs: `:target` pseudo-class (99%+ support)
- Theme toggle: `prefers-color-scheme` + `:checked` (96%+ support)
- Responsive cards: Container queries (95%+ support)
- Modals: `<dialog>` element (90%+ support)

Irreducible JavaScript for form submission: **~600-800 bytes** (<400 bytes gzipped).

---

## The Numbers

### Investment

| Scope | Cost | Time | What You Get |
|---|---|---|---|
| **Phase 0:** HTTP caching | ~$1K | 1-2 days | 70-80% of speed benefit for dynamic stack |
| **Phase 1:** MVP exporter | $5-7K | 5-7 days | `pybend export` CLI, full rebuild, dark/light theme |
| **Phase 2:** Polish | $20-30K | 2-3 weeks | Incremental builds, images, sitemap, nav |
| **Phase 3:** Advanced | $50-80K | 4-6 weeks | Per-role export, hybrid mode, custom templates |

### Addressable Market

~30% of web projects are fully static-appropriate: product catalogs (8%), documentation (6%), blogs (7%), landing pages (5%), portfolios (4%). Today these use Hugo, Eleventy, or hand-coded HTML. With static export, they could use PyBend.

### 3-Year TCO

| | MVP Only | MVP + Polish | Full Feature |
|---|---|---|---|
| Total investment | $11-19K | $35-60K | $135-225K |
| Per-project monthly savings | $6-50 | $6-50 | $6-50 |
| Break-even (project-months) | 220-317 | 700-1,000 | 2,700-3,750 |

> **The business case is strategic, not cost-driven.** The MVP is cheap enough ($5-7K) to justify on positioning value alone. The full pipeline must be justified by adoption data.

---

## The Recommendation

### Do This

1. **Now (1-2 days):** Add HTTP caching headers to schema and public endpoints. Add template caching `Map` to `form.js`. Benefits every PyBend user immediately.

2. **Next (5-7 days):** Build MVP static exporter. `pybend export` produces a complete website in `dist/`. Deploy to Cloudflare Pages for free.

3. **Measure, then decide:** Track how many users run `pybend export`. If 10+ active users within 3 months, invest in Phase 2 (incremental builds, images, sitemap).

### Do Not Do This

| Avoid | Reason |
|---|---|
| Node.js SSR layer | Violates Python-only philosophy |
| Puppeteer pre-rendering | 300MB-1GB RAM per instance, fragile |
| Building incremental rebuilds in MVP | Over-engineering for <1K pages |
| Making export mandatory | Breaks "zero to working" |
| Full 10-16 week pipeline upfront | No adoption data to justify it |

### Relationship to Template Compiler Analysis

A prior analysis (html-compiler-analysis.md) evaluated **template compilation** -- pre-building HTML templates at server start and injecting data at runtime. That optimizes the dynamic stack. This proposal is complementary: **static site export** writes complete HTML files to disk, eliminating the server entirely. Both share the same schema-to-HTML rendering core. Building one enables the other at marginal cost.

---

## Top 3 Risks

**1. Over-engineering for current scale (High probability, High impact)**
Building the full pipeline without user demand wastes $100K+. Mitigation: MVP is $5-7K. Each phase requires an adoption trigger before proceeding.

**2. Opportunity cost (High probability, Medium impact)**
Engineering time on static export cannot be spent on core framework features. Mitigation: MVP is 5-7 days -- a contained bet. If no traction in 3 months, deprioritize.

**3. Data staleness in production (Medium probability, High impact)**
Users deploy a static site and data changes. Static content becomes stale. Mitigation: Clear documentation of freshness limits. Position for infrequently-changing content only. Webhook-triggered rebuild in Phase 3.

---

## Next Steps

| Step | Owner | Timeline | Deliverable |
|---|---|---|---|
| Implement Cache-Control headers on schema + public endpoints | Backend | This week | Measurable TTFB improvement |
| Add template caching `Map` to `form.js` | Frontend | This week | Eliminate re-generation overhead |
| Build MVP static exporter | Engineering | Next sprint (5-7 days) | `pybend export` CLI |
| Write deployment guide (Cloudflare, GitHub Pages, Netlify) | Docs | With MVP | User-facing documentation |
| Measure adoption (export command usage, user feedback) | Product | Ongoing | Phase 2 decision data |
| Decide on Phase 2 investment | CEO/Product | 3 months post-MVP | Go/no-go based on data |

---

### What This Unlocks Beyond Performance

| Capability | How Static Export Enables It |
|---|---|
| **SEO** | Fully crawlable HTML without JavaScript execution |
| **Security** | Eliminates SQL injection, server XSS, server misconfiguration, DDoS vulnerability |
| **Offline access** | Static files work from browser cache or Service Worker |
| **Snapshot testing** | Exported HTML is a diffable artifact for CI |
| **Global distribution** | CDN edge serving from 300+ locations at <50ms |
| **Zero-ops deployment** | No server to manage, monitor, patch, or scale |

---

> *This summary covers findings from 10 research documents, two research syntheses, and direct codebase analysis. Full technical details, risk register, implementation blueprints, and source references are in the [complete analysis](../research/html-compiler/static-site-analysis.md).*
>
> *Compiled February 2026.*
