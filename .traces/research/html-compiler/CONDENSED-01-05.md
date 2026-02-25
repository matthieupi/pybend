## HTML Compiler Research (Docs 01-05) -- Condensed

### Key Findings (Top 20 Data Points)

1. **Static HTML pages achieve TTFB under 50ms** from CDN edge vs 200-800ms for SSR and 1-3s for CSR SPAs.
2. **A 0.1s load improvement increases conversions 8-10%** in e-commerce (Google/Deloitte research).
3. **Astro scores 99.2/100 Lighthouse** -- highest of any JS framework benchmarked (Enterspeed 2025).
4. **Netflix cut TTI by 50%** replacing React SPA with server-rendered HTML + vanilla JS, reducing JS by 200KB.
5. **Jamstack market: $1.8B (2020) to $8.6B (2025)**, projected ~$12B by 2026. 35% of developers identify as Jamstack-aligned.
6. **No existing framework compiles from a data schema to static HTML** -- PyBend's proposed compiler is a genuine whitespace opportunity.
7. **Hydration adds 200-500ms to first interaction** on average (Web Almanac 2024). Qwik eliminates it entirely via resumability.
8. **Build-time rendering (Astro SSG) is 6.7x faster on TTI** and 4.3x faster on LCP than Next.js SSR for the same component (Sparkbox).
9. **eBay's Marko achieves 60-84% JavaScript reductions** on production pages via compiler-automated partial hydration across ~20,000 UI components.
10. **Bounce probability increases 32% when load goes from 1s to 3s**, 90% at 5s, 123% at 10s (Google/SOASTA).
11. **SSG costs ~$2/1M requests vs SSR at $20-40/1M** -- a 10-20x cost advantage (Vercel pricing 2025).
12. **Declarative Shadow DOM now supported in all major browsers**: Chrome 111+, Edge 111+, Safari 16.4+, Firefox 123+.
13. **Svelte 5 updates 1,000 list items in 8ms** vs React 19 at 47ms and Vue 4 at 23ms -- compiler-optimized code is categorically faster.
14. **Lit template compiler achieves 45% faster first render** by pre-computing template metadata at build time.
15. **For a 20-entity PyBend list at md display, current rendering takes ~44ms; compiled templates would take ~15ms** -- a 66% reduction.
16. **ISR reduces serverless costs 20-30%** vs full SSR while keeping content fresh within configurable bounds.
17. **Pinterest: 15% sign-up conversion increase** from improving LCP 2.5s to 1.5s. Vodafone: 8% sales increase from similar gains.
18. **Compiler dev cost estimated at $45K-100K** (9-14 weeks); CDN+SW alternative achieves 80% of gains at 5% of cost in 1-2 weeks.
19. **PyBend's form generation: ~25 function calls, ~60 string concatenations, ~10 permission checks per entity** -- entirely schema-determined and fully compilable.
20. **Of ~25 rendering decisions per PyBend entity, ~18 are fully compilable**, ~4 partially compilable, only ~3 require runtime (values, user identity, collection contents).

---

### Industry Landscape Summary

**Rendering Spectrum (performance ordered):**

| Strategy | TTFB | LCP | TTI | JS Shipped |
|----------|------|-----|-----|------------|
| Fully Static (SSG) | <50ms | 0.3-0.5s | 0.3-0.5s | Zero to minimal |
| ISR | <50ms cached | 0.4-0.8s | 0.4-0.8s | Minimal |
| Streaming SSR | 30-50ms shell | 0.5-1.2s | 0.8-2.0s | Moderate |
| Traditional SSR | 100-500ms | 0.8-2.0s | 1.5-3.0s | Heavy |
| SPA (CSR) | 50-200ms empty | 1.5-4.0s | 2.0-5.0s+ | Very heavy |

**Framework Capabilities (2025-2026):**
- **Next.js**: Market leader (40% adoption). Has SSG, ISR, SSR, streaming, PPR. Introduced Partial Pre-Rendering in 2024.
- **Astro**: Performance champion (18% adoption, growing). Zero JS by default, native islands. 40K+ GitHub stars (80x growth since 2020). Server Islands added in 2024.
- **Qwik**: Eliminates hydration via resumability. ~1KB loader on first load. TTI is O(1) regardless of app size.
- **SvelteKit**: Compiler-first, 20-40% smaller bundles than React. ~90/100 Lighthouse.
- **Nuxt 3**: 98.8 Lighthouse. Hybrid rendering via Nitro engine.
- **Marko (eBay)**: Powers ~20,000 UI components. Compiler auto-determines island boundaries. Out-of-order streaming SSR.
- **Fresh (Deno)**: Islands via `islands/` directory convention. Deno HTTP throughput ~61% higher than Node.js.
- **None** offer schema-driven generation -- all require handwritten templates/components.

**Business Impact of Speed:**
- Each additional second (0-5s) costs -4.42% conversion.
- Page load 2.4s vs 5.7s: conversion 1.9% vs 0.6% (3.2x higher).
- SEO migration to SSR-optimized: organic traffic +66% (91.7K to 152.3K monthly), top-3 keywords +70%.
- 70% of mobile pages take >5s to display above-fold; 53% abandon if load >3s.

**Edge Platform Performance:**
- Cloudflare Workers: 1-5ms cold start (V8 Isolates).
- Vercel Fluid Compute: 2.55x faster than Workers for SSR; 9x faster cold starts vs traditional serverless.
- Optimal 2025-2026 architecture: build-time SSG + CDN edge + edge functions for dynamic parts.

**Prerendering (headless browser) is the wrong approach for PyBend**: Puppeteer uses 300MB-1GB RAM per instance, processes ~500K pages/day at scale. Schema compilation is orders of magnitude cheaper (string operations on structured data).

---

### Technical Approaches Summary

**Four Compilation Strategies for Schema-Driven Frameworks:**

| Strategy | When | Freshness | Best For |
|----------|------|-----------|----------|
| AOT/SSG | Build time | Stale until rebuild | Marketing, docs, catalogs |
| SSR | Request time | Always fresh | Dashboards, personalized |
| ISR/Edge | First request + cache | Tunable staleness | E-commerce, semi-dynamic |
| Schema-Compiled Templates | Schema change | Fresh templates, data injected later | PyBend's sweet spot |

The fourth strategy is unique to schema-driven architectures: compile structure once (on deployment), inject data at runtime. Gets 90% of compilation benefit with none of the staleness problems.

**How Modern Framework Compilers Work:**
- **Astro**: `client:load/idle/visible/media/only` directives control per-island hydration timing. Zero JS by default. 2-3x faster than Next.js for content sites.
- **Qwik**: `$()` boundaries tell the optimizer to extract functions into lazy-loadable chunks. State serialized into HTML. ~1KB QwikLoader intercepts interactions and fetches handlers on demand.
- **Marko**: Compiler automatically analyzes templates to determine static vs interactive regions. No developer annotation needed. Sub-template partial hydration.
- **Svelte**: Compiles components to surgical imperative DOM updates. No virtual DOM. Bundle: 3KB simple app vs React 42KB. Memory: ~0.5KB/component vs React ~2.4KB.

**Declarative Shadow DOM (DSD) -- the key enabler for PyBend:**
- Allows server-rendered shadow roots without JavaScript.
- Browser attaches shadow root during HTML parsing (before JS).
- When component JS loads, `attachShadow()` detects existing declarative root and adopts it -- zero re-render, zero layout shift.
- Full browser support (Chrome 111+, Edge 111+, Safari 16.4+, Firefox 123+).
- Streaming compatible: parsed during HTML streaming.

**Hydration Solutions Spectrum (more JS to less JS):**
- Full Hydration (React 18): 100% JS loaded
- Progressive Hydration (Angular 19): 80% JS, top-down deferred
- Selective Hydration (React 19): 50% JS, interaction-driven
- Islands (Astro): 10-30% JS, only marked islands
- Resumability (Qwik): ~1KB loader, zero hydration

**Schema-to-HTML Compilation Pipeline:**
1. Schema Analyzer: extract fields, resolve $defs, map UI hints, evaluate access, identify islands
2. Template Generator: HTML skeleton with data slots marked by `{{field}}`
3. Style Generator: scoped CSS for DSD
4. Island Manifest: which parts need JS and which modules to lazy-load
5. HTML Assembler: combines into DSD `<template shadowrootmode="open">`

**Build Pipeline Performance:**
- Vite incremental: <50ms. Turbopack: 10-50ms. Webpack 5: 200-500ms.
- Schema-to-HTML compiler should be faster (JSON input, HTML string output, flat dependency graph).
- Expected: <10ms per model change for PyBend.

---

### Decision Framework Summary

**When Static Compilation Delivers ROI:**
- Read/write ratio >100:1
- Data changes less frequently than hourly
- Audience is mostly public/anonymous
- Page count 100-50,000 (sweet spot)
- SEO is a primary traffic channel

**When Static DOES NOT Make Sense:**
- Real-time data (stock tickers, chat, live scores)
- Personalized dashboards (every user sees different data)
- Highly interactive UIs (editors, drag-and-drop)
- Rapidly changing inventory (flash sales)
- Large combinatorial pages (10K products x 50 categories x 3 sorts x 5 filters x 4 locales = 30M pages)

**Freshness Tiers:**
- Real-time (<1s): SSR + WebSocket/CSR
- Near-real-time (1-60s): SSR + edge cache
- Periodic (1-60 min): ISR with revalidation
- Infrequent (hours+): Full SSG
- Mixed on same page: Static shell + islands

**Build Time Scaling (real project data):**

| Pages | Hugo | Astro | Next.js SSG | Gatsby |
|-------|------|-------|-------------|--------|
| 1K | ~2s | ~8s | ~30s | ~45s |
| 10K | ~15s | ~1min | ~5min | ~8min |
| 50K | ~1min | ~5min | ~25min | ~35min+ |
| 100K | ~2min | ~12min | ~45min+ | Unreliable |

Key data point: Next.js project with ~3,000 SSG pages took 30-35 min on Vercel; switching to ISR for all but top 1,000 pages dropped builds to ~1 min.

**Build Budget Guidelines (Kent Beck's 10-min rule):**
- <5 min: optimal feedback loop
- 5-10 min: acceptable
- 10-15 min: noticeable decline
- 30+ min: danger zone
- Each additional 5 min of CI time adds >1 hour to average time-to-merge

**TCO Comparison:**

| | HTML Compiler | CDN + Service Worker | Edge SSR |
|---|---|---|---|
| Upfront cost | $45K-100K | $2K-5K | $10K-25K |
| Monthly infra | $65-475 | $20-50 | $50-200 |
| Monthly maintenance | $600-1,400 | $100-300 | $200-500 |
| Time to value | 3-4 months | 1-2 weeks | 4-6 weeks |
| Break-even vs SSR | 12-18 months | ~1 month | 3-6 months |

**Alternatives to Evaluate First (cheapest to most expensive):**
1. CDN caching via Cache-Control headers (1 hour effort, 70-90ms TTFB reduction)
2. Service Worker cache-first for schemas + stale-while-revalidate for data (1-2 days)
3. Prefetch/preload hints (2 hours)
4. Streaming SSR (1-3 weeks)
5. Edge SSR (1-3 weeks, ~50ms TTFB globally)
6. Full SSG compiler (2-6 weeks)

**Decision: CDN + Service Worker achieves 80% of the gain at 5% of the cost.**

---

### PyBend Architecture Fit Summary

**Why PyBend Is Uniquely Positioned:**
- The JSON Schema IS the complete rendering specification: field types, widget hints, layout groups, display modes, permission rules, methods -- all in one document.
- No other framework has this. Every SSG/SSR framework requires handwritten templates.
- `ProtoModel.schema()` generates everything `form.js` and `ntt-item.js` evaluate at runtime.
- Analogous to protobuf/OpenAPI/Prisma: when the schema is rich enough, you can generate the implementation.

**Complete Schema Surface Map (Product model):**
- 25 rendering decisions made per entity at runtime
- 18 are fully compilable (field types, widgets, groups, field order, methods, placeholders)
- 4 are partially compilable (array field structures known, ref contents dynamic)
- 3 require runtime (entity values, user identity, collection contents)

**Runtime Cost Analysis (current):**
- `prototype()` per model: ~0.8ms -- fast, cannot be pre-compiled, stays as-is
- Form generation per entity (5 fields, 2 groups): ~1.5ms (~25 function calls, ~60 string concats, ~10 permission checks)
- `ntt-item.render()` per entity at md: ~2.0ms
- 20 md cards total rendering: ~44ms (blocks for ~2.6 frames at 60fps)

**Projected Performance After Compilation:**
- Per-entity total: 2.2ms --> 0.75ms (66% reduction)
- 20-entity list: 44ms --> 15ms (fits within single 16.7ms frame)
- FCP with DSD: ~800ms --> ~200ms (pre-rendered HTML before JS)

**Expected Overall Performance Gains:**

| Metric | Current (SPA) | Compiled (Projected) |
|--------|---------------|---------------------|
| Lighthouse Score | ~70 | 95-100 |
| TTFB | 50ms empty shell | <50ms real content |
| LCP | 2-4s | 0.3-0.8s |
| TTI | 3-5s | 0.5-1.5s |
| TBT | 300-500ms | <50ms |
| JS shipped | 200KB+ | <50KB (islands only) |

**Actor Model Compatibility:**
- Only two function calls change in the render path.
- Actor messaging, DynamicClass creation, data fetching, event binding are completely unaffected.
- Compiler replaces only the template generation step inside `render()`.
- Surgical DOM updates via `update()` work unchanged (same `data-value`/`data-key` attributes).

**Buildless Philosophy Fit:**
- Compiler runs at server start, alongside `register_routes()` and migrations -- NOT a build step.
- Pure Python: no Node, no npm, no Webpack, no Vite.
- `compile_templates(registered_models)` reads `model.schema()`, writes HTML strings to a template registry.
- Opt-in: `create_app(compile=True)` or separate CLI command. Runtime rendering remains default.

**Concrete Implementation Estimate:**
- Phase 1 (Python compiler): ~400 LOC, 2-3 days
- Phase 2 (Template endpoint): ~50 LOC, 0.5 days
- Phase 3 (Frontend consumer): ~100 LOC, 1 day
- Phase 4 (Startup integration): ~20 LOC, 0.5 days
- Tests: ~200 LOC, 1-2 days
- **Total: ~770 LOC, 5-7 days**

**Permission Variant Templates:**
The compiler generates variants per access level: `Product_sm_anon.html`, `Product_sm_auth.html`, `Product_sm_owner.html`, `Product_sm_admin.html`. At runtime, component selects the right variant via `permissions.canAction()`.

**Files to Create:**
- `src/pybend/core/compiler/__init__.py`
- `src/pybend/core/compiler/templates.py` (main compiler)
- `src/pybend/core/compiler/form_compiler.py` (port of form.js)
- `src/pybend/core/compiler/size_compiler.py` (xs/sm/md/lg/xl)
- `src/pybend/core/compiler/method_compiler.py`
- `src/pybend/core/compiler/registry.py`

**Files to Modify:**
- `src/pybend/core/app.py` -- add `compile_templates()` to startup
- `src/pybend/core/api/routes_fastapi.py` -- add `/templates/{model}` endpoint
- `src/pybend/static/components/ntt-item.js` -- template-aware `render()` path
- `src/pybend/static/core/NTT.js` -- fetch templates on SCHEMA completion

**Simpler Wins to Try First:**
1. Template caching in form.js (20-line change, Map keyed by model+mode)
2. `<template>` + `cloneNode` instead of innerHTML (~1.5x faster)
3. Lazy rendering via IntersectionObserver (only render visible items)
4. Virtual scrolling for 100+ item lists

---

### Static Shell + Islands Summary

**Pattern Definition:**
Server-rendered static HTML (shell) with isolated interactive components (islands) that hydrate independently. Coined by Katie Sylor-Miller (Etsy, 2019), formalized by Jason Miller (Preact, 2020).

**Key Properties:**
- No top-down rendering requirement -- each island is independent
- Server rendering is the primary delivery, not an SEO bolt-on
- Each island is independently deliverable, loadable, hydratable
- 60-90% reduction in client-side JavaScript vs SPA

**Framework Implementations:**
- **Astro**: `client:load/idle/visible/media/only` directives. Server Islands (Astro 5) defer server rendering per-component.
- **Fresh (Deno)**: `islands/` directory convention. HTML comment markers for boundaries. Preact Signals for state sharing.
- **Marko (eBay)**: Compiler auto-determines boundaries via static analysis. No developer annotation. Sub-template partial hydration.
- **11ty `<is-land>`**: Framework-agnostic web component wrapper (1.79 KB). Combines conditions: `on:visible on:idle`. `[ready]` attribute for CSS transitions.
- **Next.js PPR**: Static shell from edge + Suspense streaming in single HTTP response. Client routing preserved.

**Web Components Are Natural Islands:**
- Encapsulated (Shadow DOM isolates styles/DOM)
- Self-contained (own lifecycle, state, rendering)
- Independently hydratable (`customElements.define()` at any time; elements upgrade in place)
- No framework root required
- Server-renderable (via Declarative Shadow DOM)
- Progressively enhanceable (light DOM children visible before JS loads)

**Island Granularity Rules:**
- Too small (<2KB component code): overhead of hydration machinery exceeds benefit. Use vanilla JS instead.
- Too large (>60% of page): effectively SPA again; decompose into smaller islands or accept different strategy.
- Ideal: user-meaningful interactive units (search bar, add-to-cart, comment section, data table).

**Island Communication Strategies (best to worst):**
1. **Shared stores** (nanostores, signals): single source of truth, works with lazy hydration. Recommended.
2. **Custom DOM events**: zero dependencies, but vulnerable to ordering issues with lazy hydration.
3. **URL state**: survives reload/bookmarking, limited to serializable values.
4. **Parent element attributes**: via MutationObserver.

**PyBend's Actor/Matrix IS an island communication system:**
- Matrix = shared message bus (equivalent to nanostores/signals)
- TX = structured messages (superior to raw CustomEvent)
- Component addresses = island identifiers
- Watchers/Observers = reactive subscriptions
- DynamicClass = shared entity registry (all ntt-items for same entity share canonical data)
- Solves the hardest islands problem (cross-island state sync) out of the box

**How PyBend Components Map:**

| Component | Type | Hydration |
|-----------|------|-----------|
| Navigation/header/footer | Static shell | None |
| Skeleton placeholders | Static shell | None |
| Form fields (display mode) | Static shell (potentially) | None |
| `<ntt-list>` | Client island | viewport/idle |
| `<ntt-item>` | Client island | viewport |
| `<ntt-method>` | Client island | visible/interaction |
| `<ntt-router>` | Client island | load (critical) |

**Adoption Path:**
1. **Phase 1 (Week 1-2)**: Cache-Control headers on schema + public list endpoints
2. **Phase 2 (Week 3-4)**: Service Worker for schema caching, stale-while-revalidate for entities
3. **Phase 3 (Month 2-3)**: Schema-walking HTML pre-renderer targeting public-access models. Static shell + Web Component islands. CDN with ISR-style invalidation.
4. **Phase 4 (Month 4+)**: Incremental rebuild via storage write hooks. DSD for ntt-item. Full build pipeline.

**Anti-Patterns to Avoid:**
- Do not adopt Qwik wholesale (migration cost unjustified for PyBend's scale)
- Do not add a Node.js SSR layer (violates Python-framework philosophy)
- Do not use headless browser pre-rendering (resource cost unacceptable with schema available)
- Do not compile data into HTML at build time (compile templates/structure; inject data at request/client time)
- Do not create 50+ islands per page (observer overhead, network waterfalling)
- Do not have separate data fetches per island for same data (use shared store/DynamicClass)

**Bottom-Line Recommendation:**
Start with CDN caching + Service Workers (1-2 weeks, 80% of benefit at 5% cost). Measure TTFB/FCP/LCP. If still >200ms TTFB on public pages after caching, proceed with the schema-walking compiler. The compiler is architecturally sound, uniquely enabled by PyBend's schema completeness (~770 LOC, 5-7 days for PyBend-specific implementation), and produces the Static Shell + Dynamic Islands pattern the industry has converged on. Make it opt-in: runtime rendering remains default.
