# Decision Framework: Static Site Generation for PyBend

**Document:** 03-decision-framework.md
**Date:** 2026-02-25
**Audience:** Technical CEO + Engineering Team
**Status:** Research Complete

---

## Executive Summary

PyBend is a schema-driven dynamic framework: a Python model definition
produces an API, JSON Schema, storage, and a live web UI at runtime. The
question is whether building a static HTML export capability is worth the
engineering investment, and for which project profiles it would deliver
genuine value.

**The short answer:** a static export feature serves a real but bounded
market segment. Roughly 25-35% of typical web projects (catalogs,
documentation, blogs, portfolios, landing pages) could run as fully
static sites. For those projects, the cost savings at scale are
significant -- up to 10-50x reduction in hosting costs at high traffic.
But the engineering effort to build the export feature is non-trivial
(8-16 weeks), and for 65-75% of projects that need authentication, forms,
or real-time data, the feature adds no value.

The recommended path: invest first in aggressive HTTP caching and CDN
edge caching on the existing dynamic stack (2-3 weeks, benefits all
users), then evaluate static export as a Phase 2 feature based on
adoption data.

---

## 1. When Does Static Make Sense vs. Dynamic?

The decision is not binary. It depends on five measurable criteria:

### 1.1 Decision Criteria Matrix

| Criterion | Static | Dynamic Required |
|-----------|--------|------------------|
| **Content update frequency** | < 1 change/hour | > 1 change/minute |
| **Personalization** | None or cookie-based | Per-user dashboards, feeds |
| **Form complexity** | Contact forms (via external service) | Multi-step forms, transactions |
| **Real-time requirements** | None | Chat, live prices, notifications |
| **Authentication** | None or read-only public | Login, user-specific data |
| **Data volume** | < 50K pages | Unbounded / search-driven |
| **SEO criticality** | High (static wins) | Moderate (SSR equivalent) |

### 1.2 Decision Tree

```
START: Does the site require user authentication for core features?
  |
  YES --> Does every page need personalized content?
  |         |
  |         YES --> FULL DYNAMIC (SPA or SSR)
  |         |
  |         NO  --> HYBRID: static shell + authenticated API calls
  |
  NO  --> Does content change more than once per hour?
            |
            YES --> Does it change more than once per minute?
            |         |
            |         YES --> SSR with CDN edge caching
            |         |
            |         NO  --> ISR (Incremental Static Regeneration)
            |                 or webhook-triggered rebuilds
            |
            NO  --> Are there more than 50,000 distinct pages?
                      |
                      YES --> Static with incremental builds
                      |       (Hugo-class tooling required)
                      |
                      NO  --> FULLY STATIC
                              Best cost/performance profile.
                              Ideal for PyBend static export.
```

### 1.3 Project Type Classification

| Project Type | Update Freq. | Auth? | Forms? | Verdict | % of Web |
|-------------|-------------|-------|--------|---------|----------|
| Product catalog (read-only) | Daily | No | No | **Fully static** | ~8% |
| Documentation site | Weekly | No | No | **Fully static** | ~6% |
| Blog / content site | Daily | No | Minimal | **Fully static** | ~7% |
| Landing pages | Monthly | No | Contact only | **Fully static** | ~5% |
| Portfolio | Monthly | No | No | **Fully static** | ~4% |
| E-commerce (with cart) | Hourly | Yes | Yes | Dynamic | ~12% |
| SaaS dashboard | Real-time | Yes | Yes | Dynamic | ~15% |
| Social platform | Real-time | Yes | Yes | Dynamic | ~8% |
| Internal tools | Varies | Yes | Yes | Dynamic | ~10% |
| Marketplace | Hourly | Yes | Yes | Dynamic | ~6% |
| Other dynamic apps | Varies | Yes | Varies | Dynamic | ~19% |

**Estimated addressable market for fully static: ~30% of web projects.**

This aligns with W3Techs data showing 28.6% of websites globally operate
without a CMS, relying on hand-coded or static solutions [1]. The
trajectory is declining (~3.9% per year since 2011) as CMS adoption
grows, but the absolute number of static-suitable projects remains large.

---

## 2. The Rendering Spectrum

Modern web rendering is not a binary choice. It is a spectrum with five
distinct positions, each with clear tradeoffs:

### 2.1 The Five Positions

```
FULLY STATIC ---- STATIC + JS ISLANDS ---- ISR/SSG ---- SSR ---- FULL SPA
     |                    |                    |           |           |
  0 KB JS           < 50 KB JS          Build-time     Per-req     200+ KB JS
  CDN only          CDN + micro JS      + CDN cache    server      client renders
  Zero server       Zero server          Periodic       Always on   Always on
  No interactivity  Targeted interactivity Stale-OK     Fresh data  Full interactivity
```

### 2.2 Detailed Comparison

| Dimension | Fully Static | Static + Islands | ISR / SSG | SSR | Full SPA |
|-----------|-------------|-----------------|-----------|-----|----------|
| **JS payload** | 0 KB | 5-50 KB | 5-50 KB | 50-150 KB | 200-500 KB |
| **TTFB** | 10-50 ms (CDN) | 10-50 ms (CDN) | 10-50 ms (CDN) | 100-500 ms | 100-500 ms |
| **LCP** | < 500 ms | < 800 ms | < 800 ms | 800-2000 ms | 1500-4000 ms |
| **Server cost** | $0-5/mo | $0-5/mo | $0-20/mo | $20-500/mo | $20-500/mo |
| **Freshness** | Build-time | Build-time + API | Minutes-hours | Real-time | Real-time |
| **Personalization** | None | Per-island | None (global) | Full | Full |
| **SEO** | Perfect | Perfect | Perfect | Good | Requires setup |
| **Complexity** | Low | Medium | Medium | High | High |
| **Offline support** | Trivial | Easy | Moderate | Hard | Moderate |
| **Framework example** | Hugo, 11ty | Astro | Next.js ISR | Next.js SSR | React SPA |

### 2.3 Where PyBend Projects Belong

Given PyBend's architecture -- schema-driven, model-as-source-of-truth,
auto-generated CRUD UI -- most PyBend applications are inherently
dynamic. They rely on:

- Live API calls to fetch entity data
- Authentication for create/update/delete operations
- Real-time schema resolution for UI rendering
- Server-side access control enforcement

**However**, a meaningful subset of PyBend deployments are read-only
public sites: product catalogs, documentation, company directories,
event listings. For these, the dynamic capabilities are overhead. A
static export would:

1. Eliminate the server entirely for production serving
2. Reduce TTFB from ~200ms (FastAPI) to ~20ms (CDN edge)
3. Drop hosting costs from $6-50/month to $0-5/month
4. Improve reliability (no server to crash, no DB to corrupt)

---

## 3. Cost-Benefit Analysis: Building the Feature

### 3.1 Engineering Effort Estimate

Building a static export capability for PyBend requires:

| Component | Effort | Description |
|-----------|--------|-------------|
| **HTML template engine** | 3-4 weeks | Convert NTT.js runtime rendering to server-side HTML generation. Must read the same JSON Schema and produce equivalent markup without JavaScript. |
| **Static file generator** | 2-3 weeks | CLI command (`pybend export --output ./dist`) that iterates all models, fetches all entities, renders pages, writes HTML/CSS. |
| **Asset pipeline** | 1-2 weeks | CSS extraction, image optimization, sitemap.xml, robots.txt generation. |
| **Incremental rebuild** | 2-3 weeks | Content hashing, dependency tracking, rebuild only changed pages. Critical for sites > 1K pages. |
| **Testing + docs** | 1-2 weeks | Verify output matches dynamic rendering. Document configuration. |
| **Webhook/CI integration** | 1-2 weeks | Trigger rebuilds from CMS changes, GitHub Actions template, Netlify/Cloudflare deploy hooks. |
| **Total** | **10-16 weeks** | 1-2 engineers |

### 3.2 Opportunity Cost

Those 10-16 engineering weeks could alternatively fund:

- HTTP caching layer for dynamic PyBend (2-3 weeks, benefits all users)
- Five new framework features from the backlog
- Performance optimization of the existing stack
- Additional storage backends (PostgreSQL, MongoDB)

### 3.3 Feature ROI Model

| Metric | Without Static Export | With Static Export |
|--------|---------------------|-------------------|
| Addressable market | 100% of PyBend users | +30% catalog/docs users |
| Hosting cost for static projects | $6-50/mo (VPS) | $0-5/mo (CDN) |
| Performance (TTFB) | 100-300 ms | 10-50 ms |
| Reliability (uptime) | 99.5-99.9% | 99.99%+ (CDN) |
| Maintenance burden | Server management | Zero (after deploy) |
| Engineering investment | 0 weeks | 10-16 weeks |
| Ongoing maintenance | 0 hrs/month | 2-4 hrs/month |

---

## 4. TCO Comparison: Static on CDN vs. FastAPI Server

### 4.1 Hosting Cost Matrix (Monthly)

The following compares the total monthly cost of serving a PyBend
application as a static site on a CDN versus running it as a dynamic
FastAPI application on a VPS.

**Assumptions:**
- Average page size: 50 KB (static HTML+CSS), 200 KB (dynamic with JS)
- 3 pages per visit average
- FastAPI on Uvicorn, 4 workers, behind nginx

| Visitors/Day | Static (CDN) | Dynamic (VPS) | Savings | Notes |
|-------------|-------------|--------------|---------|-------|
| **100** (3K/mo) | **$0** | **$6** | $6/mo | Free tier covers both. VPS minimum is $4-6. |
| **1,000** (30K/mo) | **$0** | **$6-12** | $6-12/mo | Still within CDN free tiers (Cloudflare Pages, Netlify, GitHub Pages). VPS needs minimum spec. |
| **10,000** (300K/mo) | **$0-5** | **$12-24** | $7-24/mo | ~45 GB/mo transfer for static. CDN free tiers sufficient. VPS needs 2 vCPU/4GB RAM. |
| **100,000** (3M/mo) | **$5-20** | **$48-96** | $28-91/mo | ~450 GB/mo static transfer. May exceed free CDN tier. VPS needs 4 vCPU/8GB+ or horizontal scaling. |
| **1,000,000** (30M/mo) | **$20-100** | **$200-1,000** | $100-980/mo | 4.5 TB/mo. Requires paid CDN. VPS needs load balancer + multiple instances or managed platform. |

### 4.2 Static Hosting Provider Pricing (2026)

| Provider | Free Tier | Pro Plan | Bandwidth (Free) | Build Minutes (Free) |
|----------|-----------|----------|-------------------|---------------------|
| **Cloudflare Pages** | Yes | $20/mo | Unlimited | 500/mo |
| **Netlify** | Yes | $19/user/mo | 100 GB/mo | 300/mo |
| **Vercel** | Yes | $20/user/mo | 100 GB/mo | 6000/mo |
| **GitHub Pages** | Yes | N/A (free) | 100 GB/mo | N/A |
| **DigitalOcean App Platform** | 3 sites | $5+/mo | 1 GB/mo (free) | Varies |
| **Azure Static Web Apps** | Yes | $9/mo | 100 GB/mo | Varies |
| **Surge.sh** | Yes | $30/mo | Unlimited | N/A |

Sources: [2][3][4]

### 4.3 Dynamic Hosting Provider Pricing (2026)

| Provider | Plan | Monthly Cost | Specs | Notes |
|----------|------|-------------|-------|-------|
| **Hetzner CX22** | Shared | $4.50/mo | 2 vCPU, 4 GB RAM | Best price/performance ratio [5] |
| **DigitalOcean** | Basic Droplet | $6/mo | 1 vCPU, 1 GB RAM | Good DX, managed DB add-on [6] |
| **DigitalOcean** | Production | $24/mo | 2 vCPU, 4 GB RAM | Suitable for 10K+ visitors/day |
| **Railway** | Usage-based | $5-50/mo | Auto-scale | No config, pay per use |
| **Render** | Starter | $7/mo | 0.5 vCPU, 512 MB | Auto-deploy from Git |
| **AWS EC2 t3.small** | On-demand | $15/mo | 2 vCPU, 2 GB RAM | + bandwidth costs |

### 4.4 Break-Even Analysis

The static export feature investment (10-16 weeks at ~$10K/week fully
loaded engineering cost) equals **$100K-$160K**. At a per-project savings
of $10-50/month (typical range for the target segment):

| Monthly savings/project | Projects needed to break even (1yr) | Projects needed (2yr) |
|------------------------|-----------------------------------|-----------------------|
| $10/mo | 833-1,333 | 417-667 |
| $25/mo | 333-533 | 167-267 |
| $50/mo | 167-267 | 83-133 |

**Verdict:** The feature pays for itself only if PyBend captures
hundreds of static-site projects. As a framework feature, the value is
strategic (market positioning, competitive differentiation) rather than
direct cost recovery.

---

## 5. Build Time Considerations

### 5.1 Build Time Benchmarks by Generator

Build times vary dramatically by tooling choice. The CSS-Tricks SSG
benchmark study [7] established the canonical comparison:

| Generator | Language | 1K Pages | 4K Pages | 16K Pages | 64K Pages |
|-----------|----------|----------|----------|-----------|-----------|
| **Hugo** | Go | ~0.5s | ~1.5s | ~5s | ~15s |
| **Eleventy** | JS/Node | ~4s | ~15s | ~60s | ~240s |
| **Jekyll** | Ruby | ~3s | ~12s | ~50s | ~200s |
| **Astro** | JS/Node | ~5s | ~18s | ~75s | ~300s |
| **Gatsby** | JS/React | ~30s | ~90s | ~360s | ~1200s |
| **Next.js** | JS/React | ~15s | ~50s | ~200s | ~800s |

*Values are approximate, interpolated from multiple benchmark sources.
Actual times depend on page complexity, template logic, and hardware.*
[7][8][9]

Hugo is 40-250x faster than framework-based generators at scale. For a
hypothetical PyBend static exporter (Python-based), expect performance
in the Eleventy/Jekyll range -- Python template engines (Jinja2) are
comparable to Ruby/Node for this workload.

### 5.2 PyBend-Specific Build Time Estimates

A PyBend static export would need to:

1. Boot the application (load models, connect to storage)
2. Query all entities from SQLite
3. Render each entity to HTML via a template engine
4. Write files to disk

| Page Count | DB Query | Template Render | File I/O | Total (est.) |
|-----------|---------|----------------|---------|-------------|
| **100** | < 0.1s | ~0.5s | < 0.1s | **~1s** |
| **1,000** | ~0.2s | ~4s | ~0.3s | **~5s** |
| **10,000** | ~1s | ~35s | ~2s | **~40s** |
| **100,000** | ~8s | ~350s (~6min) | ~15s | **~6.5min** |

### 5.3 Incremental vs. Full Rebuild

| Strategy | Complexity | Rebuild Time (1K changed / 10K total) | Storage Overhead |
|----------|-----------|--------------------------------------|-----------------|
| **Full rebuild** | Low | 40s (rebuilds all 10K) | None |
| **Content hash** | Medium | ~6s (rebuilds 1K + index pages) | Hash manifest file |
| **Dependency graph** | High | ~4s (rebuilds 1K + dependents only) | Full dep graph |
| **ISR (on-demand)** | Medium | ~0.05s per page (on request) | Requires server |

For PyBend's target use cases (< 10K pages), full rebuilds under 1
minute are acceptable. **Incremental builds add complexity that is
justified only above 10K pages.**

---

## 6. Content Freshness Tradeoffs

### 6.1 Staleness Tolerance by Content Type

| Content Type | Acceptable Staleness | Rebuild Strategy |
|-------------|---------------------|-----------------|
| Documentation | Hours-days | Manual trigger or Git push |
| Blog posts | Minutes-hours | Webhook on publish |
| Product catalog | Minutes-hours | Scheduled (every 15-60 min) |
| Pricing pages | Minutes | Webhook + immediate rebuild |
| Landing pages | Days-weeks | Manual deploy |
| Event listings | Hours | Scheduled (hourly) |
| News / breaking | Seconds-minutes | **Not suitable for static** |
| Stock prices | Real-time | **Not suitable for static** |
| User dashboards | Real-time | **Not suitable for static** |

### 6.2 Rebuild Trigger Strategies

```
CONTENT CHANGE
     |
     +-- Manual trigger (CLI: pybend export)
     |     Best for: Documentation, portfolios
     |     Latency: Developer-initiated
     |
     +-- Git push trigger (CI/CD pipeline)
     |     Best for: Code-alongside-content projects
     |     Latency: 1-5 minutes (CI pipeline)
     |
     +-- Webhook trigger (CMS/API change)
     |     Best for: Product catalogs, blogs
     |     Latency: 30s-3min (build + deploy)
     |
     +-- Scheduled rebuild (cron)
     |     Best for: Aggregated data, periodic updates
     |     Latency: Configurable (5min - 24hr)
     |
     +-- ISR / On-demand revalidation
           Best for: High-page-count sites with frequent changes
           Latency: First request after change (~100ms)
           Requires: Server process (defeats pure-static goal)
```

### 6.3 The Freshness-Cost Tradeoff Curve

```
Freshness        Cost/Complexity
(staleness)
    |
 Real-time -----> $$$$$  Full dynamic server, DB, caching layer
    |
 < 1 minute ----> $$$$   ISR with server process
    |
 < 15 minutes --> $$$    Webhook-triggered rebuild + CDN
    |
 < 1 hour ------> $$     Scheduled rebuilds (cron)
    |
 < 1 day -------> $      Manual or Git-triggered rebuilds
    |
 Weekly+ -------> ~$0    Static files, deploy and forget
```

For the PyBend target segment (catalogs, docs, blogs), 15-minute to
1-hour staleness is typically acceptable, putting the optimal strategy
at **webhook-triggered or scheduled rebuilds** -- the sweet spot of low
cost and adequate freshness.

---

## 7. Migration Effort: Adding Static Export to PyBend

### 7.1 What PyBend Already Has

PyBend's architecture provides several advantages for static export:

| Existing Capability | Static Export Leverage |
|--------------------|----------------------|
| JSON Schema generation (`ProtoModel.schema()`) | Schema defines page structure without runtime resolution |
| `model_dump(response=True)` with `$schema`/`$id` | Each entity is self-describing; can generate canonical URLs |
| `StorableMixin.list()` with pagination | Can iterate all entities for export |
| `__ui__` configuration (field_order, groups, renderer) | Layout instructions are already declarative |
| `form.js` / `Formidable` form generation | Logic exists in JS; needs Python equivalent |
| Access rules in schema | Can filter public-visible fields at export time |
| `FastAPIBackend.register_routes()` | Route structure defines URL hierarchy for static files |

### 7.2 What Needs to Be Built

| Component | Gap | Approach |
|-----------|-----|---------|
| **Server-side HTML renderer** | NTT.js renders in the browser; no Python equivalent | Jinja2 templates that consume the same JSON Schema. Must replicate `ntt-item`, `ntt-list`, `form.js` layout logic. |
| **CSS extraction** | Styles are in JS component files | Extract to standalone `.css` files. Most styles are already in CSS custom properties. |
| **Static file writer** | No CLI export command | New `pybend export` command that boots app, queries all data, renders, writes to `dist/`. |
| **URL mapping** | Dynamic routes (`/{tablename}/{id}`) to file paths | `/{tablename}/{id}` becomes `/{tablename}/{id}/index.html`. Collection pages become `/{tablename}/index.html` with pagination. |
| **Asset handling** | Images/uploads are served dynamically | Copy to `dist/assets/`, rewrite URLs in HTML. |
| **Search** | Dynamic search relies on API | Options: (a) generate a JSON index for client-side search (Lunr.js, Pagefind), (b) skip search, (c) external search service. |
| **Forms** | Dynamic forms POST to API | Replace with external form service (Formspree, Netlify Forms) or remove. |

### 7.3 Migration Complexity Score

| Aspect | Complexity (1-5) | Rationale |
|--------|-----------------|-----------|
| Data extraction | 1 | `StorableMixin.list()` already works |
| Schema interpretation | 2 | JSON Schema is well-structured |
| HTML rendering | 4 | Must replicate all NTT.js display logic in Python |
| CSS pipeline | 2 | Mostly extraction and concatenation |
| URL structure | 2 | Straightforward mapping |
| Pagination (static) | 3 | Generate page-1.html, page-2.html, etc. |
| Search | 4 | Non-trivial; best handled by external tool |
| Forms | 3 | Requires integration with third-party service |
| Incremental builds | 4 | Content hashing and dependency tracking |
| **Overall** | **3/5** | Moderate -- feasible but not trivial |

---

## 8. Anti-Patterns to Avoid

### 8.1 Trying to Make Interactive Apps Static

**The trap:** A team builds a PyBend app with authentication, user
dashboards, and real-time comments, then asks "can we make this static?"

**Why it fails:** Static generation can only capture the public,
unauthenticated view of data. Per-user content, real-time updates, and
form submissions require a server. Attempting to bolt these on with
client-side JavaScript recreates a SPA with extra steps -- worse
performance and more complexity than the original dynamic app.

**The test:** If removing all JavaScript from the page makes the core
user journey impossible, the site cannot be static.

### 8.2 Over-Engineering the Build Pipeline

**The trap:** Building a complex incremental build system, dependency
graph, cache invalidation layer, and multi-stage deployment pipeline
for a 200-page documentation site.

**Why it fails:** At 200 pages, a full rebuild takes 1-2 seconds. The
incremental build system takes weeks to build and introduces bugs that
are harder to diagnose than a slow-but-correct full rebuild.

**The rule:** Build the simplest pipeline that meets the freshness
requirement. Add complexity only when build times exceed 60 seconds
AND the content changes frequently enough to matter.

### 8.3 Premature Static Generation

**The trap:** Starting with static export during initial development,
before the data model is stable.

**Why it fails:** Every model change requires updating both the dynamic
app AND the static export templates. During rapid iteration, this
doubles the maintenance burden with no user-facing benefit.

**The rule:** Build and iterate on the dynamic app first. Add static
export only after the data model is stable and there is a demonstrated
need for static serving.

### 8.4 Ignoring the "Uncanny Valley" of Hybrid

**The trap:** A mostly-static site with 3-4 interactive features
(search, comments, newsletter signup) implemented as JavaScript islands
that each need their own API endpoint.

**Why it fails:** You now maintain a static build pipeline AND a
dynamic API server. The deployment is more complex than either pure
approach. The API server still needs hosting, monitoring, and scaling
-- eliminating most of the cost advantage of static.

**The test:** Count the interactive features. If more than 2 require
your own backend (not a third-party service), stay dynamic.

### 8.5 Rebuilding What CDN Caching Already Solves

**The trap:** Building a static export feature to improve performance,
when adding `Cache-Control: public, max-age=3600` to API responses
would achieve 80% of the benefit.

**Why it fails:** CDN edge caching of dynamic responses provides
near-static performance (20-50ms TTFB) without any code changes. The
static export adds build complexity for marginal improvement.

**This is the most relevant anti-pattern for PyBend.** See Section 10
for the caching-first alternative.

---

## 9. Percentage of Web Apps That Could Be Fully Static

### 9.1 Market Segmentation

Based on W3Techs data [1], HTTP Archive data, and industry surveys:

| Segment | % of All Websites | Could Be Static? | Notes |
|---------|-------------------|-------------------|-------|
| Blogs & content sites | ~15% | **Yes (90%+)** | WordPress powers 43% of the web; most blogs are read-only [10] |
| Documentation | ~5% | **Yes (95%+)** | Already largely static (ReadTheDocs, GitBook, Docusaurus) |
| Landing pages / marketing | ~10% | **Yes (85%+)** | Often already static; forms via third-party |
| Product catalogs (read-only) | ~5% | **Yes (80%+)** | If no cart/checkout |
| Portfolios | ~5% | **Yes (95%+)** | Minimal interactivity |
| E-commerce (with transactions) | ~12% | **No** | Requires cart, checkout, auth |
| SaaS / web apps | ~20% | **No** | Inherently dynamic |
| Social / community | ~8% | **No** | User-generated content, real-time |
| Internal / enterprise tools | ~10% | **No** | Auth, workflows, data entry |
| Other | ~10% | **Mixed** | Case-by-case |

### 9.2 Summary

**~30-35% of all websites could be fully static.** This maps to:
- ~95% of portfolios
- ~90% of blogs
- ~85% of landing pages
- ~80% of read-only catalogs
- ~95% of documentation sites

**~5-10% more could benefit from a hybrid approach** (static pages with
JavaScript islands for search, comments, or analytics).

**~55-65% require dynamic serving** and would not benefit from static
export at all.

For PyBend specifically, the framework's value proposition is
schema-driven dynamic applications. Users who need a static blog are
more likely to reach for Hugo or Astro directly. The PyBend static
export feature targets a narrower segment: **users who build their data
model in PyBend for the authoring/admin experience, then want to publish
the public-facing site as static HTML.**

---

## 10. Alternatives to Static Export

Before building a static export feature, consider these alternatives
that deliver many of the same benefits with less effort:

### 10.1 Aggressive HTTP Caching

**Effort:** 2-3 weeks
**Impact:** 70-80% of the performance benefit of static

Add `Cache-Control` headers to PyBend API responses:

```
# Read-only entity responses
Cache-Control: public, max-age=3600, stale-while-revalidate=86400

# Schema responses (rarely change)
Cache-Control: public, max-age=86400, immutable

# List responses
Cache-Control: public, max-age=300, stale-while-revalidate=3600
```

With a CDN in front (Cloudflare free tier), this reduces origin requests
by 80-95% and delivers TTFB of 20-50ms for cached responses -- matching
static site performance for repeat visitors.

**Pros:** Benefits ALL PyBend users, not just the static segment. Zero
change to development workflow. Works with authentication (vary by token).

**Cons:** First request to each URL still hits origin. Stale content
window is configurable but non-zero.

### 10.2 CDN Edge Caching (Cloudflare, Fastly)

**Effort:** 1 week (configuration only)
**Impact:** Equivalent to static for read-heavy sites

Place the entire PyBend application behind a CDN with aggressive caching
rules. Cloudflare's free tier includes:

- Unlimited bandwidth
- Global edge network (300+ cities)
- Automatic HTML caching with page rules
- Cache purge API (for webhook-triggered invalidation)

For a read-only product catalog, the CDN effectively turns the dynamic
site into a static one -- serving HTML from edge cache with no origin
requests for cached pages.

### 10.3 Pre-Rendering Service (Rendertron / Prerender.io)

**Effort:** 1-2 days (setup only)
**Impact:** SEO parity with static, no code changes

A pre-rendering service intercepts requests from search engine crawlers,
renders the JavaScript-driven page to static HTML, and serves the cached
result. This solves the primary SEO concern without changing the
application architecture.

**However**, Google deprecated its recommendation for dynamic rendering
in 2024, as Googlebot now executes JavaScript reliably [11]. Pre-rendering
services are a legacy solution; modern search engines handle SPAs natively.

### 10.4 Hybrid: Static Shell + Dynamic API

**Effort:** 4-6 weeks
**Impact:** Best of both worlds for the right use case

Generate a static HTML shell (navigation, layout, empty content areas)
at build time. At runtime, the shell loads and makes API calls to fill
in dynamic content. This is essentially the "islands architecture"
pattern:

```html
<!-- Static shell (served from CDN) -->
<html>
  <body>
    <nav>...</nav>  <!-- Static, rendered at build time -->
    <main>
      <ntt-list model="Product"></ntt-list>  <!-- Hydrates from API -->
    </main>
    <footer>...</footer>  <!-- Static -->
  </body>
</html>
```

**This is the most natural fit for PyBend's architecture.** The web
components already fetch data from the API at runtime. The "static
export" is simply pre-rendering the page chrome and letting the
components hydrate normally.

### 10.5 Comparison of Alternatives

| Approach | Effort | TTFB | Server Required? | Freshness | Cost |
|----------|--------|------|-----------------|-----------|------|
| Full static export | 10-16 wks | 10-30ms | No | Build-time | $0-5/mo |
| HTTP caching | 2-3 wks | 20-50ms | Yes | Configurable | $6-50/mo |
| CDN edge caching | 1 wk | 15-40ms | Yes (origin) | Configurable | $6-50/mo |
| Pre-rendering | 1-2 days | 20-50ms | Yes + service | On-crawl | $6-50/mo + service |
| Static shell + API | 4-6 wks | 15-40ms (shell) | Yes (API) | Real-time (data) | $0-5 (shell) + $6-50 (API) |

---

## 11. Recommendation

### 11.1 Phase 1: Caching First (Weeks 1-3)

Implement aggressive HTTP caching in PyBend's route layer:

1. Add `Cache-Control` headers to all read endpoints
2. Add `ETag` support for conditional requests
3. Document CDN setup (Cloudflare free tier) in deployment guide
4. Add cache purge webhook endpoint for on-demand invalidation

**This benefits 100% of PyBend users immediately**, not just the
static-site segment. For read-heavy sites behind a CDN, the
performance will approach static-site levels.

### 11.2 Phase 2: Evaluate (Months 2-3)

Collect usage data:

- How many PyBend projects are read-only / public?
- What is the average page count?
- Are users requesting static export?
- How do sites perform with Phase 1 caching?

If data confirms demand, proceed to Phase 3.

### 11.3 Phase 3: Static Export (If Warranted)

Build the minimal viable static exporter:

1. `pybend export` CLI command
2. Jinja2 templates mirroring NTT.js layout
3. Full rebuild only (skip incremental for v1)
4. Output to `dist/` with deployment docs for Cloudflare Pages / Netlify

Skip: incremental builds, search integration, form handling. Let users
solve those with existing tools (Pagefind for search, Formspree for
forms).

### 11.4 Decision Matrix: When to Choose Each Path

| If your project has... | Recommended approach |
|----------------------|---------------------|
| < 100 visitors/day, any complexity | Stay dynamic (VPS cost is negligible) |
| Auth + personalization | Stay dynamic (static is not applicable) |
| Read-only, < 1K pages, updates < daily | Full static export |
| Read-only, > 10K pages, updates hourly | CDN edge caching on dynamic |
| Mixed read/write, high traffic | HTTP caching + CDN |
| SEO-critical content marketing | Static export or CDN caching |
| Real-time data (prices, chat, feeds) | Stay dynamic, no static path |

---

## 12. Key Takeaways

1. **Static export is a real capability with a bounded market.** ~30% of
   web projects could benefit, but only a subset of PyBend users fit the
   profile (read-only, public, < 10K pages).

2. **The cost savings are real but conditional.** At 100K+ visitors/day,
   static hosting saves $30-900/month versus a VPS. Below 10K
   visitors/day, the savings are under $20/month -- unlikely to justify
   the migration effort.

3. **Build times are manageable.** A Python-based exporter can generate
   10K pages in under a minute. Incremental builds are unnecessary below
   that threshold.

4. **Caching is the 80/20 solution.** HTTP caching + CDN delivers
   70-80% of static site performance benefits with 10-20% of the
   engineering effort, and applies to all project types.

5. **The biggest risk is building for a segment that uses other tools.**
   Developers who need static sites already have Hugo (builds 64K pages
   in 15 seconds), Astro (islands architecture), and Eleventy (Node
   simplicity). PyBend's unique value is the dynamic, schema-driven
   stack. A static exporter is a nice-to-have, not a differentiator.

6. **If you build it, build it minimal.** Full rebuild, Jinja2 templates,
   CLI command. No incremental builds, no build pipeline, no JavaScript.
   Let the ecosystem handle search and forms.

---

## Sources

1. [W3Techs - Usage Statistics of Static Files for Websites (Jan 2026)](https://w3techs.com/technologies/details/pl-static/all/all) -- 28.6% of websites operate without a CMS.

2. [Crystallize - 10 Best Static Website Hosting Providers in 2026](https://crystallize.com/blog/static-hosting) -- Comprehensive pricing comparison of static hosting platforms.

3. [DigitalApplied - Vercel vs Netlify vs Cloudflare Pages: 2025 Comparison](https://www.digitalapplied.com/blog/vercel-vs-netlify-vs-cloudflare-pages-comparison) -- Feature and pricing comparison of major static hosting providers.

4. [Appwrite - 6 Best Free Static Website Hosting Services Compared](https://appwrite.io/blog/post/best-free-static-website-hosting) -- Free tier analysis for static hosting platforms.

5. [VPSBenchmarks - DigitalOcean vs Hetzner Performance Comparison](https://www.vpsbenchmarks.com/compare/docean_vs_hetzner) -- VPS pricing and performance benchmarks.

6. [Menetray - Best VPS: Hetzner vs DigitalOcean vs Linode Pricing](https://menetray.com/en/blog/best-vps-more-less-pricing-hetzner-vs-digitalocean-vs-linode) -- Detailed cost analysis for low-cost VPS providers.

7. [CSS-Tricks - Comparing Static Site Generator Build Times](https://css-tricks.com/comparing-static-site-generator-build-times/) -- Canonical benchmark: Hugo, Eleventy, Jekyll, Gatsby, Next, Nuxt across 1-64K pages.

8. [CloudCannon - Top Five Static Site Generators for 2025](https://cloudcannon.com/blog/the-top-five-static-site-generators-for-2025-and-when-to-use-them/) -- Build performance characteristics and framework selection guide.

9. [Piper Haywood - Benchmarking Eleventy vs Astro Build Times](https://piperhaywood.com/inexactly-benchmarking-eleventy-vs-astro-build-times/) -- Real-world build time comparison with ~2,550 pages.

10. [WPZOOM - WordPress Statistics February 2026](https://www.wpzoom.com/blog/wordpress-statistics/) -- WordPress powers 43.3% of surveyed websites.

11. [CristalCode - Why Dynamic Rendering Is Outdated in 2025](https://cristalcode.net/articles/why-dynamic-rendering-is-outdated-in-2025-and-what-to-use-instead) -- Google deprecated dynamic rendering recommendation; Googlebot executes JS natively.

12. [Smashing Magazine - Jamstack Rendering Patterns: The Evolution](https://www.smashingmagazine.com/2022/04/jamstack-rendering-patterns-evolution/) -- Comprehensive overview of the rendering spectrum from static to dynamic.

13. [Patterns.dev - Islands Architecture](https://www.patterns.dev/vanilla/islands-architecture/) -- Technical explanation of the islands architecture pattern.

14. [Patterns.dev - Incremental Static Regeneration](https://www.patterns.dev/react/incremental-static-rendering/) -- ISR pattern documentation with implementation details.

15. [DebugBear - Understanding Stale-While-Revalidate](https://www.debugbear.com/docs/stale-while-revalidate) -- Cache freshness strategies and SWR implementation guide.

16. [web.dev - Keeping Things Fresh with Stale-While-Revalidate](https://web.dev/articles/stale-while-revalidate) -- Google's guidance on SWR caching patterns.

17. [DevelopersVoice - SPA vs SSR vs SSG and Edge Rendering in 2025](https://developersvoice.com/blog/frontend/rendering-models-react-dotnet/) -- Rendering spectrum analysis with decision criteria.
