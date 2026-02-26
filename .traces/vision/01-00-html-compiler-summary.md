# HTML Compiler for PyBend: Executive Summary

> *Standalone summary. Full analysis: [../research/html-compiler/html-compiler-analysis.md](../research/html-compiler/06-html-compiler-analysis.md)*

---

## The Question

**Should PyBend build a system that pre-compiles JSON Schema definitions into static HTML, eliminating the runtime overhead of constructing UI from schema on every page load?**

PyBend's architecture currently works like this: a user loads a page, the browser downloads JavaScript, the JavaScript fetches a JSON Schema from the backend, interprets that schema to determine what HTML to produce (field types, widgets, layout groups, permissions), constructs the HTML, and inserts it into the page. This happens for every entity on every page load. It works, but the user stares at a blank screen for 2-4 seconds while all of that processing happens.

An HTML compiler would shift that work to the server. At server startup, a Python module would read each model's schema and pre-generate the HTML templates -- the same HTML that JavaScript currently constructs on the fly. The browser would receive finished HTML instead of instructions for building HTML. The result: content appears 3-10x faster.

**The unique opportunity:** No framework in the market today generates HTML directly from a data schema. Every competitor (Next.js, Astro, Nuxt, Hugo, Eleventy) requires developers to write templates or components. PyBend's schema already carries everything a compiler needs -- field types, widget hints, layout groups, permission rules, method signatures. The model IS the template. This is a genuine whitespace in a market growing at 35% annually to $8.6B.

**The honest answer:** Not yet. The performance improvement is real but the investment is significant. Start with low-cost caching ($2K-5K) that delivers 80% of the gain. Build the compiler only when measured metrics or business needs (SEO, mobile, scale) justify the full investment ($15K-25K for core compiler, $45K-100K for the complete system).

> **The strategic framing:** This is not just a performance optimization. It is an architectural capability that would make PyBend the first framework to generate production HTML directly from data model definitions. The compiler transforms PyBend's greatest strength (everything derived from schema) into a compilation advantage that no competitor currently offers.

---

## Key Findings at a Glance

| # | Finding | Evidence |
|---|---|---|
| 1 | **Static HTML loads 3-10x faster** than client-rendered SPAs | Astro SSG: 0.4s LCP vs React SPA: 2.5s+ (Sparkbox benchmarks) |
| 2 | **PyBend's schema is a complete compiler input** -- no templates needed | `proto_model.py` carries field types, widgets, groups, access rules, methods |
| 3 | **70% of per-entity render cost is compilable** at build time | Code tracing of form.js + ntt-item.js: 18 of 25 rendering decisions are schema-static |
| 4 | **No competitor compiles from data schema to HTML** | Research across all major SSG/SSR frameworks -- whitespace opportunity |
| 5 | **80% of the gain comes from caching alone** | CDN headers + Service Worker costs $2K-5K vs $45K-100K for full compiler |
| 6 | **Each 0.1s faster = 8-10% more conversions** in e-commerce | Google/Deloitte research with 90% prediction accuracy |
| 7 | **The compiler fits PyBend's philosophy** | Runs at server start (like migrations), pure Python, no npm/Node/build step |
| 8 | **Declarative Shadow DOM** enables instant Web Component rendering | All major browsers support DSD since 2023 |

---

## The Rendering Spectrum

Understanding the landscape requires seeing where different approaches fall:

```
RENDERING APPROACHES: SPEED vs. FRESHNESS
================================================================

Fastest Load                                          Freshest Data
     |                                                      |
     v                                                      v
+--------+    +--------+    +--------+    +--------+    +--------+
|  Full  |    |  ISR   |    |  Edge  |    |  SSR   |    |  CSR   |
|  SSG   |    | (cache |    |  SSR   |    | (per-  |    | (SPA)  |
| (build |    |  + re- |    | (near  |    | request|    | Current|
|  time) |    | valid.)|    |  user) |    | render)|    | PyBend |
+--------+    +--------+    +--------+    +--------+    +--------+
 TTFB:         TTFB:         TTFB:         TTFB:         TTFB:
 <50ms         <50ms         30-80ms       100-500ms     50ms
 LCP:          LCP:          LCP:          LCP:          LCP:
 0.3-0.5s      0.4-0.8s      0.5-1.0s      0.8-2.0s      2.0-4.0s
```

The proposed PyBend compiler targets a unique position: **schema-compiled templates** that give SSG-like speed for structure with CSR-like freshness for data. Templates are pre-built (fast structure), data is injected at runtime (always fresh).

## What the Industry Tells Us

The web industry has spent 2020-2026 converging on one conclusion: **ship less JavaScript, deliver HTML earlier, measure everything.**

**The winners:**

| Company | What They Did | Result |
|---|---|---|
| **Netflix** | Replaced React SPA with server-rendered HTML + vanilla JS | **50% faster** loading, 200KB less JS |
| **eBay** | Built Marko (compiler-based streaming HTML) for 20K+ components | Met performance goals at massive scale |
| **Shopify** | React Server Components + streaming SSR (Hydrogen) | Routes loaded **2x faster** |
| **E-commerce (general)** | Improved page load from 5.7s to 2.4s | Conversion **3.2x higher** (1.9% vs 0.6%) |

**The market:** The Jamstack/static-first market grew from $1.8B (2020) to $8.6B (2025). 35% of developers identify as Jamstack-aligned. Astro (islands architecture, zero-JS-by-default) grew from 500 to 40,000+ GitHub stars in 4 years. The direction is clear.

**The pattern everyone is adopting:** Static shell (page layout, navigation, content structure served instantly from CDN) + dynamic islands (interactive components like buttons, forms, auth-dependent UI that load JavaScript only when needed). This is what Astro, Fresh, Marko, and Next.js PPR all implement. PyBend's Web Components are natural islands -- each `ntt-item`, `ntt-list`, `ntt-method` is already a self-contained unit.

**The gap:** Every framework in the market requires developers to write templates, components, or pages. PyBend would be the first to generate static HTML directly from data model definitions. The schema carries rendering instructions (`ui.widget`, `ui.field_order`, `ui.groups`, `access`, `methods`). No template layer needed.

---

## Where We Stand Today

**Our strength:** PyBend's JSON Schema is uniquely complete as a compiler input. Reading through `proto_model.py`, `form.js`, and `ntt-item.js`, the schema carries:

- **Field types** that map to HTML elements (`string` -> `<input type="text">`, `number` -> `<input type="number">`)
- **Widget hints** that control rendering (`currency` -> dollar sign + number input, `textarea` -> `<textarea>`)
- **Layout groups** that produce fieldsets (`ui.groups` -> `<fieldset>` with `<legend>`)
- **Field order** that controls sequence (`ui.field_order` -> render order in the form)
- **Access rules** that gate visibility (`access.update: OWNER` -> show/hide edit button)
- **Method signatures** that produce action buttons (`methods.like` -> `<ntt-method>` element)

Of the ~25 rendering decisions made per entity, **18 are fully compilable** at build time. Only 3 truly require runtime: actual data values, user identity, and collection contents.

**Our gap:** Everything is currently client-side. There is no SSR, no build pipeline, no CDN integration, no incremental invalidation. But the proposed approach (Python-side compilation at server start) requires none of these -- it slots into the existing startup lifecycle alongside `register_routes()` and database migrations.

**Existing infrastructure we can leverage:** NTT.js already has `#consumePreloadedSchema()` and `#consumePreloadedData()` for inline data preloading. The Actor messaging system provides a clean boundary -- the compiler replaces only the template generation step inside `render()`, leaving ATTACH/SCHEMA/READ/DESCRIBE/UPDATE flows completely untouched.

---

## The Numbers

### Performance Impact

| Metric | Current | After Caching (Phase 0-1) | After Compiler (Phase 2-3) |
|---|---|---|---|
| **Lighthouse Score** | ~70 | ~75 | **95-100** |
| **First Contentful Paint** | ~800ms | ~600ms | **~200ms** |
| **Largest Contentful Paint** | 2-4s | 1.5-3s | **0.3-0.8s** |
| **Time to Interactive** | 3-5s | 2.5-4s | **0.5-1.5s** |
| **Per-entity render time** | ~2.2ms | ~1.5ms (cached) | **~0.75ms** |
| **20-card list render** | ~44ms | ~30ms | **~15ms** |

### Cost

| Phase | Investment | Monthly Cost | Time to Value |
|---|---|---|---|
| Phase 0: Cache headers | ~$500 | $0 | 1 day |
| Phase 1: Service Worker | $2K-5K | $100-300 | 1-2 weeks |
| Phase 2: Schema compiler | $15K-25K | $200-500 | 2-3 weeks |
| Phase 3: DSD + Islands | $10K-20K | $200-400 | 1-3 weeks |
| Phase 4: Edge + streaming | $20K-50K | $200-600 | 3-4 weeks |
| **Full system** | **$45K-100K** | **$600-1,400** | **9-14 weeks** |

### Business Case

| Scenario | Impact | Source |
|---|---|---|
| 0.1s faster page load | **+8-10% conversions** (e-commerce) | Google/Deloitte |
| Load time under 3s (from 5s+) | **-90% bounce probability** | Google/SOASTA |
| Static HTML (crawlable) | **+50-70% organic traffic** (vs SPA) | Conductor/Netrocket |
| Lighthouse 95+ (from 70) | **Improved search ranking** | Google Core Web Vitals |

---

## The Recommendation

**Do not build the compiler today.** Start with the cheapest optimizations and measure the impact. Build the compiler only when the numbers or business needs justify it.

### Phase 0: Now (1-2 weeks, ~$500)

Add `Cache-Control` headers to schema endpoints and public list endpoints. Add a template caching `Map` in `form.js` (a 20-line change that eliminates re-generation for the same schema). Measure TTFB before and after.

### Phase 1: When Phase 0 is exhausted (1-2 weeks, $2K-5K)

Implement a Service Worker for schema caching and stale-while-revalidate on entity lists. This enables near-instant repeat visits and basic offline read access.

### Phase 2: When metrics or business justify ($15K-25K)

Build the Python-side schema template compiler. This is the core innovation:
- Pure Python module, runs at server start -- no npm, no Node, no build pipeline
- Generates HTML template strings with `{{slot}}` markers for each model x size x permission variant
- ~770 lines of code, 5-7 days of engineering work
- Frontend gets template-aware `render()` with automatic fallback to runtime generation

**Trigger:** First-visit FCP > 500ms on target mobile devices, OR SEO becomes a business priority.

### Phase 3: When Phase 2 proves value ($10K-20K)

Add Declarative Shadow DOM for instant first paint (content visible before any JavaScript loads) and islands-style selective hydration (only load JavaScript for interactive components like `ntt-method` buttons and edit toggles).

**Trigger:** Target Lighthouse score > 95, OR crawlability audit reveals SEO gaps.

### What NOT to do

- **Do not add Node.js for SSR** -- violates PyBend's Python-only philosophy
- **Do not use headless browser pre-rendering** -- 300MB+ RAM per instance, fragile, expensive
- **Do not compile data into HTML** -- data changes constantly; compile templates (structure), inject data at runtime
- **Do not make the compiler mandatory** -- it should be opt-in (`compile=True` in `create_app()`)

---

## What Competitors Would Have to Do

If a competitor wanted to replicate PyBend's schema-to-HTML compilation:

| Competitor | What They Would Need | Difficulty |
|---|---|---|
| **Next.js** | A schema layer that carries UI hints, access rules, and methods. They have none. | Would require architectural redesign |
| **Astro** | Data model definitions with rendering metadata. Astro reads from CMSes and APIs, not schemas. | Would need a schema standard |
| **Django/Rails** | Their model systems describe data, not UI. No `ui.widget`, no `ui.groups`, no `access` rules in schema. | Would need PyBend-like schema extensions |
| **Strapi/Contentful** | CMS schemas carry content structure, not rendering instructions. Still need frontend components. | Partial overlap, but missing rendering layer |

PyBend's advantage is structural: the schema is the single source of truth for data, API, UI, permissions, and rendering. This completeness is what makes compilation possible without templates. Competitors would need to redesign their schema layers to match.

---

## Top 3 Risks

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| **1** | **Over-engineering for current scale.** Building the compiler before measuring whether caching is sufficient wastes $15K-100K and 2-14 weeks of engineering time on a problem that may not exist. | High | High | Phase 0 and 1 first. Only proceed when measured metrics justify investment. Each phase delivers standalone value. |
| **2** | **Opportunity cost.** Every week on the compiler is a week not spent on core framework features, customer-facing product work, or developer experience improvements. The compiler has no value until PyBend has users who need the performance. | High | High | Strict phase gates with metric-based triggers. Compiler work pauses if business priorities shift. CEO reviews quarterly. |
| **3** | **Cache invalidation complexity.** Pre-compiled templates introduce a new cache layer that can serve stale content. Stale HTML is worse than slow HTML -- users see incorrect information. | Medium | High | Templates compiled from schema structure (not entity data) -- only stale on missed deployment. Version with schema hash. Runtime fallback always available. Monitor for staleness. |

---

## Next Steps

| Step | Who | When | Deliverable |
|---|---|---|---|
| Add `Cache-Control` headers to schema and public endpoints | Backend engineer | This week | Headers in `routes_fastapi.py` |
| Add template caching `Map` in `form.js` | Frontend engineer | This week | 20-line change, PR ready |
| Measure current TTFB, FCP, LCP, TTI on target devices | QA / DevOps | Next week | Baseline performance report |
| Measure post-caching performance | QA / DevOps | Week 3 | Delta report: did caching solve the problem? |
| Decision gate: proceed to Service Worker? | CEO + Engineering | Week 3 | Go/no-go based on metrics |
| Quarterly review: re-evaluate compiler timeline | Architecture team | Every 3 months | Updated priority assessment |

---

## Frequently Asked Questions

**Q: Is the current rendering actually slow?**
A: Not catastrophically. A 44ms render for 20 entity cards is competitive. But First Contentful Paint (~800ms) and LCP (2-4s) are well above the thresholds where Google measures conversion impact. The compiler's primary value is FCP and LCP improvement, not per-entity render speed.

**Q: Does this break PyBend's "zero config" philosophy?**
A: No. The compiler is opt-in (`compile=True` in `create_app()`). The runtime-rendered UI remains the default. The compiler runs at server start alongside `register_routes()` and migrations -- no npm, no Node, no external build step.

**Q: What about personalized content (logged-in users)?**
A: The compiler generates **variant templates** (anon, auth, owner, admin). At runtime, the component selects the right variant based on the user's permissions. Personalized data values are always injected at runtime via `{{slot}}` replacement.

**Q: How does this differ from server-side rendering (SSR)?**
A: SSR renders a complete page per request, requiring server compute on every visit. Schema template compilation generates templates once at startup and serves them as static files. Data is injected client-side. The server load is near-zero after startup.

**Q: What is the single cheapest thing we can do right now?**
A: Add a template caching `Map` to `form.js` (a 20-line change). This eliminates re-generation of the same form structure for repeated renders of the same model. Estimated time: 2 hours. Estimated impact: eliminates ~30ms of redundant work when scrolling a list of 20 items.

---

> **Bottom line:** PyBend has a genuine competitive advantage -- its schema is rich enough to compile HTML without templates, something no other framework does. The question is not *if* but *when*. Start with caching. Measure. Build the compiler when the business demands it. The architecture is ready; the market is aligned; the timing should follow the metrics.

---

*Summary prepared February 2026. Based on analysis of 4 research documents, 70+ external sources, and direct codebase review. Full analysis available in [html-compiler-analysis.md](../research/html-compiler/06-html-compiler-analysis.md).*
