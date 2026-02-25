# HTML Compiler for Schema-Driven Frameworks: Decision Framework

> **Audience:** Technical CEOs, Engineering Leadership, Architecture Teams
> **Context:** Evaluating whether to build an HTML compiler for a schema-driven framework (PyBend) that currently renders entirely client-side via Web Components
> **Last Updated:** February 2026

---

## Executive Summary

Static HTML compilation promises sub-100ms page loads by pre-rendering content at build time rather than constructing it in the browser. For a schema-driven framework like PyBend --- where models define the entire stack --- the compiler would walk the schema graph, fetch entity data, and emit ready-to-serve `.html` files.

**The core tension:** PyBend's architecture derives everything from the schema at runtime. An HTML compiler inverts that model, requiring the framework to also derive things at *build* time. This is a fundamental architectural decision, not a performance tweak.

This document provides the decision criteria, cost analysis, risk assessment, and migration strategies to determine **when, whether, and how** to pursue static HTML compilation.

---

## Table of Contents

1. [When Does Static HTML Compilation Deliver ROI?](#1-when-does-static-html-compilation-deliver-roi)
2. [The Staleness Problem](#2-the-staleness-problem)
3. [When Static Generation Does NOT Make Sense](#3-when-static-generation-does-not-make-sense)
4. [Build Time Scaling: Real Numbers](#4-build-time-scaling-real-numbers)
5. [Alternatives to HTML Compilation](#5-alternatives-to-html-compilation)
6. [TCO Analysis](#6-tco-analysis)
7. [The Static Shell + Dynamic Islands Pattern](#7-the-static-shell--dynamic-islands-pattern)
8. [Team and Workflow Impact](#8-team-and-workflow-impact)
9. [Risk Analysis](#9-risk-analysis)
10. [Full Rendering Strategy Comparison](#10-full-rendering-strategy-comparison)
11. [The Compilation Budget](#11-the-compilation-budget)
12. [Migration Strategies](#12-migration-strategies)
13. [Organizational Readiness Checklist](#13-organizational-readiness-checklist)
14. [WebGPU/WebGL Content Considerations](#14-webgpuwebgl-content-considerations)
15. [Decision Tree](#15-decision-tree)
16. [PyBend-Specific Analysis](#16-pybend-specific-analysis)
17. [Recommendations](#17-recommendations)
18. [Sources](#18-sources)

---

## 1. When Does Static HTML Compilation Deliver ROI?

Static HTML compilation is not universally beneficial. ROI depends on the intersection of three axes: **content type**, **read/write ratio**, and **audience authentication model**.

### The ROI Matrix

| Dimension | High ROI for Static | Low ROI for Static |
|-----------|--------------------|--------------------|
| **Content type** | Product catalogs, blogs, docs, marketing | Dashboards, feeds, real-time data |
| **Read/write ratio** | 100:1 or higher (reads dominate) | 1:1 or lower (frequent writes) |
| **Audience** | Public, anonymous, SEO-critical | Authenticated, personalized |
| **Change frequency** | Hours to days between changes | Seconds to minutes |
| **Page count** | 100 -- 50,000 (sweet spot) | < 10 or > 500,000 |
| **SEO importance** | Primary traffic channel | Irrelevant (internal tool) |

### Quantified ROI Signals

> **Conversion impact of performance:**
> - Pinterest saw a **15% increase in sign-up conversions** after improving LCP from 2.5s to 1.5s
> - Vodafone achieved an **8% increase in sales** from similar performance gains
> - These gains come from Core Web Vitals improvements that static HTML delivers by default
>
> *Source: [Chrome User Experience Report, web.dev](https://web.dev/learn/performance/general-html-performance)*

**Cost-per-request comparison (Vercel pricing, 2025):**

| Strategy | Cost per 1M requests | Notes |
|----------|---------------------|-------|
| **SSG** (CDN-served) | ~$2.00 | Edge requests only |
| **ISR** | ~$2.40 + cache ops | $0.40/M reads + $4.00/M writes |
| **SSR** | ~$20--40 | Function invocations + compute |
| **CSR** (API calls) | ~$2.00 (static) + API cost | Shifts cost to API tier |

*Source: [Vercel Pricing](https://vercel.com/pricing), [Vercel ISR Pricing](https://vercel.com/docs/incremental-static-regeneration/limits-and-pricing)*

> **Key insight:** SSG reduces per-request cost by **10--20x** compared to SSR. For a site serving 10M requests/month, that is the difference between ~$20/month and ~$200--400/month on compute alone.

### Decision Heuristic

```
IF   read_write_ratio > 100:1
AND  data_change_frequency > 1 hour
AND  audience_is_mostly_public == true
AND  page_count < 50,000
THEN static HTML compilation likely delivers positive ROI

IF   any of the above conditions fail
THEN evaluate ISR, edge SSR, or client-side rendering first
```

---

## 2. The Staleness Problem

The fundamental question for any static approach: **how fresh does the data need to be?**

### Freshness Tiers

| Tier | Acceptable Staleness | Strategy | Example |
|------|---------------------|----------|---------|
| **Real-time** | < 1 second | SSR / WebSocket / CSR | Stock prices, chat, live scores |
| **Near-real-time** | 1--60 seconds | SSR with edge cache | Shopping cart, inventory count |
| **Periodic** | 1--60 minutes | ISR (revalidate on timer) | Product prices, blog comments |
| **Infrequent** | Hours to days | SSG (full rebuild) | Documentation, marketing pages |
| **Archival** | Weeks to never | SSG (one-time build) | Legal docs, historical data |

### ISR as the Middle Ground

Incremental Static Regeneration (pioneered by Next.js, now adopted broadly) attempts to bridge static and dynamic:

```
Request flow with ISR:

User A ──> CDN ──> [Cache HIT] ──> Serve static HTML (fast)
                        │
                        └── [TTL expired?] ──> YES ──> Background regeneration
                                                            │
                                                            v
                                                    Fetch fresh data
                                                    Render new HTML
                                                    Update CDN cache
                                                            │
User B ──> CDN ──> [Cache HIT] ──> Serve NEW static HTML
```

> **ISR reduces serverless function costs by 20--30%** compared to full SSR, while keeping content freshness within configurable bounds.
>
> *Source: [Vercel ISR Documentation](https://vercel.com/docs/incremental-static-regeneration/limits-and-pricing)*

### The Staleness Decision Criteria

```
┌──────────────────────────────────────────────────────────┐
│         How fresh must the data be?                      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  < 1 second?  ────────────>  SSR + WebSocket / CSR       │
│                                                          │
│  1-60 seconds? ───────────>  SSR with CDN cache-control  │
│                                                          │
│  1-60 minutes? ───────────>  ISR (revalidate: N)         │
│                                                          │
│  Hours+? ─────────────────>  Full SSG                    │
│                                                          │
│  MIXED on same page? ────>  Static shell + islands       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 3. When Static Generation Does NOT Make Sense

Static generation is the **wrong tool** in several well-defined scenarios. Forcing it creates complexity that outweighs any performance gain.

### Hard Contraindications

| Scenario | Why Static Fails | Better Alternative |
|----------|------------------|--------------------|
| **Real-time data** (stock tickers, live chat) | Stale by the time CDN serves it | WebSocket + CSR |
| **Personalized content** (user dashboards) | Every user sees different data; can't pre-render all variants | SSR or CSR with auth |
| **Highly interactive UIs** (editors, drag-and-drop, drawing tools) | HTML is just a shell; all value is in JS | CSR / SPA |
| **Rapidly changing inventory** (e-commerce flash sales) | Staleness = lost revenue | SSR + edge cache (short TTL) |
| **User-generated content with moderation** | Content changes unpredictably | ISR with on-demand revalidation |
| **A/B testing or feature flags** | Different HTML per cohort | Edge middleware + SSR |
| **Large combinatorial pages** (filters x categories x locales) | Combinatorial explosion in build time | On-demand SSR |

### The Personalization Constraint

> **"SSG will not allow for personalization."**
> *Source: [Vercel Rendering Strategy Guide](https://vercel.com/blog/how-to-choose-the-best-rendering-strategy-for-your-app)*

If your page says "Hello, Alice" or shows a shopping cart count, that content cannot be statically generated (without per-user builds, which is impractical). The standard solution is the **static shell + dynamic islands** pattern (see Section 7).

### The Combinatorial Problem

Consider an e-commerce site with:
- 10,000 products
- 50 categories
- 3 sort orders
- 5 filter states
- 4 locales

Naive static generation: `10,000 x 50 x 3 x 5 x 4 = 30,000,000 pages`. Even at 1ms per page, that is **8.3 hours** of build time.

**Solution:** Only statically generate canonical pages. Generate filtered/sorted/localized views on-demand with ISR or client-side.

---

## 4. Build Time Scaling: Real Numbers

Build time is the hidden tax of static generation. It determines deployment velocity, CI costs, and developer experience.

### Benchmark Data (Approximate, from Real Projects)

| Page Count | Hugo | Eleventy | Next.js (SSG) | Gatsby | Astro |
|-----------|------|----------|---------------|--------|-------|
| **1,000** | ~2s | ~5s | ~30s | ~45s | ~8s |
| **10,000** | ~15s | ~50s | ~5 min | ~8 min | ~1 min |
| **50,000** | ~1 min | ~4 min | ~25 min | ~35 min+ | ~5 min |
| **100,000** | ~2 min | ~10 min | ~45 min+ | Unreliable | ~12 min |

*Sources: [CSS-Tricks SSG Build Performance](https://css-tricks.com/comparing-static-site-generator-build-times/), [Hugo Performance Docs](https://gohugo.io/troubleshooting/performance/), [Next.js GitHub Discussion #14122](https://github.com/vercel/next.js/discussions/14122), [Gatsby Scaling Blog](https://www.gatsbyjs.com/blog/how-were-scaling-gatsby-to-millions-of-pages/)*

> **Real-world data point:** A Next.js project rendering ~3,000 SSG pages on Vercel took **30--35 minutes**. After switching to ISR for all but the top 1,000 pages, builds dropped to **~1 minute**.
>
> *Source: [Next.js GitHub Discussion #14122](https://github.com/vercel/next.js/discussions/14122)*

### Why Build Times Differ So Dramatically

| Framework | Language | Architecture | Scaling Factor |
|-----------|----------|-------------|---------------|
| **Hugo** | Go (compiled) | Template-based, no JS runtime | Near-linear, fastest |
| **Astro** | Node.js | Islands, zero-JS default | Efficient, good parallelism |
| **Eleventy** | Node.js | Template-based, minimal JS | Linear, moderate |
| **Next.js** | Node.js + React | Full React render per page | Superlinear (React overhead) |
| **Gatsby** | Node.js + React + GraphQL | Data layer adds overhead | Poor at scale (100K+) |

### The Parallelization Factor

Gatsby documented a key insight: **10K pages with 1 worker = 100K pages with 10 workers = 1M pages with 100 workers** in build time. Parallelization is the escape valve for build time scaling, but it requires CI infrastructure that supports it.

*Source: [Gatsby Scaling Blog](https://www.gatsbyjs.com/blog/how-were-scaling-gatsby-to-millions-of-pages/)*

### Build Time Growth Curve (Conceptual)

```
Build Time
    │
    │                                              ╱ Gatsby
    │                                           ╱
    │                                        ╱
    │                                 ╱── Next.js
    │                              ╱
    │                        ╱── Eleventy
    │                  ╱──
    │           ╱──  ╱── Astro
    │     ╱── ╱──
    │  ╱╱──── Hugo
    │╱──
    └───────────────────────────────────────────── Page Count
         1K      10K      50K     100K     500K
```

---

## 5. Alternatives to HTML Compilation

Before investing in a build-time compiler, evaluate whether cheaper alternatives achieve sufficient performance gains.

### Alternative Strategy Comparison

| Strategy | TTFB Impact | Implementation Cost | Freshness | Complexity |
|----------|------------|--------------------|-----------|-----------:|
| **CDN caching (Cache-Control headers)** | 70--90ms reduction | Low (config only) | TTL-based | Low |
| **Service Worker (cache-first)** | Near-instant repeat visits | Medium (SW code) | Stale-while-revalidate | Medium |
| **Preload/Prefetch hints** | Faster perceived load | Low (HTML tags) | Real-time | Low |
| **Streaming SSR** | First byte in ~45ms | Medium (server infra) | Real-time | Medium |
| **Edge SSR** (Cloudflare Workers, Deno Deploy) | ~50ms TTFB globally | Medium-High | Real-time | High |
| **Static shell + client hydration** | Fast shell, dynamic data | Medium | Real-time | Medium |
| **Full SSG compiler** | ~0ms TTFB (CDN) | High (tooling) | Build-time | High |

### Strategy 1: Aggressive CDN Caching

> CDN caching cuts Time-to-First-Byte by **70--90ms** on typical payloads by scattering cached responses across hundreds of edge POPs.
>
> *Source: [SmartSMS Solutions](https://smartsmssolutions.com/resources/blog/business/cdn-vs-edge-caching-explained)*

For a framework like PyBend that serves JSON schemas and entity data, adding proper `Cache-Control` headers on schema endpoints (`GET /Product`) and list endpoints achieves 80% of the static HTML benefit with 10% of the effort:

```python
# Schema endpoints - cache aggressively (schemas rarely change)
Cache-Control: public, max-age=3600, s-maxage=86400

# List endpoints (public) - short cache, stale-while-revalidate
Cache-Control: public, max-age=60, s-maxage=300, stale-while-revalidate=600

# Authenticated endpoints - no CDN cache
Cache-Control: private, no-cache
```

### Strategy 2: Service Worker Caching

Service Workers provide a **client-side caching layer** that persists across sessions:

```
First visit:     Network ──> Render ──> Cache in SW
Repeat visits:   SW Cache ──> Instant render ──> Background refresh
Offline:         SW Cache ──> Render (stale but functional)
```

> With a Service Worker cache, cached content is much more likely to stay cached compared to HTTP cache. For websites with mostly static content, all critical assets can be pre-cached on the first visit, leading to **near-instantaneous loading on subsequent visits**.
>
> *Source: [web.dev Service Worker Caching](https://web.dev/articles/service-worker-caching-and-http-caching)*

**Applicable caching strategies:**

| Strategy | Best For | Freshness |
|----------|---------|-----------|
| **Cache-first** | Static assets, schemas, images | Stale until SW update |
| **Network-first** | Entity data, API responses | Always fresh when online |
| **Stale-while-revalidate** | List pages, non-critical data | Instant + background refresh |

### Strategy 3: Streaming SSR with React Server Components

> In a streaming SSR comparison, TTFB dropped from **450ms to 45ms** and LCP from **1.2s to 380ms**, with zero JS shipped for server components.
>
> *Source: [SitePoint RSC Streaming Performance Guide 2026](https://www.sitepoint.com/react-server-components-streaming-performance-2026/)*

Streaming SSR delivers content progressively --- the browser starts painting before the server finishes rendering. This is particularly powerful for pages with mixed static and dynamic content.

### Strategy 4: Edge SSR / Edge Rendering

Edge SSR moves rendering to CDN edge nodes, combining the freshness of SSR with geographic proximity of CDN:

```
Traditional SSR:   User ──> CDN (pass-through) ──> Origin (render) ──> User
                   Latency: 200-500ms

Edge SSR:          User ──> Edge Node (render locally) ──> User
                   Latency: 30-80ms
```

> Edge SSR combined with smart caching rules can **approximate static-like performance** while keeping per-request freshness.
>
> *Source: [Vyakymenko, Medium](https://medium.com/@vyakymenko/edge-rendering-vs-static-vs-serverful-trade-offs-8f720d69dc7b)*

### Decision: When to Reach for Alternatives Instead

```
┌─────────────────────────────────────────────────────────────┐
│  Can you get acceptable performance WITHOUT a compiler?     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Add Cache-Control headers              ──> Measure TTFB │
│     (cost: 1 hour)                                         │
│                                                             │
│  2. If TTFB > 200ms: Add Service Worker    ──> Measure      │
│     (cost: 1-2 days)                                       │
│                                                             │
│  3. If still slow: Add prefetch/preload    ──> Measure      │
│     (cost: 2 hours)                                        │
│                                                             │
│  4. If still slow AND public content:                      │
│     Consider static HTML compilation                        │
│     (cost: 2-6 weeks)                                      │
│                                                             │
│  5. If still slow AND dynamic content:                     │
│     Consider edge SSR or streaming SSR                     │
│     (cost: 1-3 weeks)                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. TCO Analysis

Total Cost of Ownership for an HTML compiler extends far beyond the initial build.

### Cost Categories

#### A. Build Infrastructure

| Component | Monthly Cost (10K pages) | Monthly Cost (100K pages) |
|-----------|-------------------------|--------------------------|
| CI compute (GitHub Actions) | ~$15 (30 min/build x 2/day) | ~$150 (5 hrs/build x 2/day) |
| CI compute (CircleCI, large resource) | ~$30 | ~$300 |
| Storage (static files, ~50KB/page) | ~$0.50 (500 MB) | ~$5 (5 GB) |
| CDN bandwidth (10M req/mo) | ~$20 | ~$20 |
| **Subtotal** | **~$65/month** | **~$475/month** |

*Pricing based on: [CircleCI](https://circleci.com/pricing/), [Google Cloud Build](https://cloud.google.com/build) (2,500 free minutes/mo), [Azure DevOps](https://azure.microsoft.com/en-us/pricing/details/devops/azure-devops-services/) (1,800 free minutes/mo)*

#### B. Development Cost (One-Time)

| Task | Estimated Effort | Notes |
|------|-----------------|-------|
| Compiler architecture + core engine | 3--4 weeks | Schema walker, data fetcher, HTML emitter |
| Template system / render pipeline | 1--2 weeks | Mapping schemas to HTML templates |
| Incremental rebuild support | 2--3 weeks | Dependency graph, change detection |
| CI/CD integration | 1 week | Build triggers, deployment pipeline |
| Cache invalidation + webhooks | 1--2 weeks | On-demand regeneration |
| Testing + documentation | 1--2 weeks | Build correctness, regression tests |
| **Total** | **9--14 weeks** | **~$45K--$100K at fully loaded eng cost** |

#### C. Ongoing Maintenance

| Activity | Hours/Month | Cost/Month |
|----------|------------|------------|
| Build failure triage | 2--4 hrs | $200--400 |
| Cache invalidation debugging | 1--3 hrs | $100--300 |
| Template updates for schema changes | 2--5 hrs | $200--500 |
| Infrastructure monitoring | 1--2 hrs | $100--200 |
| **Total** | **6--14 hrs** | **$600--1,400** |

#### D. Opportunity Cost

Every week spent on an HTML compiler is a week not spent on:
- Core framework features
- Developer experience improvements
- Security, auth, storage enhancements
- Customer-facing product features

### TCO Comparison: Compiler vs. Alternatives

| | HTML Compiler | CDN + Service Worker | Edge SSR |
|---|---|---|---|
| **Upfront cost** | $45K--100K | $2K--5K | $10K--25K |
| **Monthly infra** | $65--475 | $20--50 | $50--200 |
| **Monthly maintenance** | $600--1,400 | $100--300 | $200--500 |
| **Time to value** | 3--4 months | 1--2 weeks | 4--6 weeks |
| **TTFB improvement** | ~0ms (CDN) | ~50--100ms | ~30--80ms |
| **Break-even vs. SSR savings** | ~12--18 months | ~1 month | ~3--6 months |

> **Bottom line:** The HTML compiler delivers the best absolute performance, but the CDN + Service Worker approach achieves 80% of the gain at 5% of the cost. Edge SSR sits in between. The compiler only pays for itself at scale (>10M requests/month) or when SEO is a critical business driver.

---

## 7. The Static Shell + Dynamic Islands Pattern

This is the **most promising pattern** for a schema-driven framework like PyBend. It captures the best of both worlds: fast initial paint from static HTML, and full interactivity from client-side hydration.

### Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    Static Shell (Pre-built)                │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │   <header>   │  │  Navigation  │  │  Page Layout     │ │
│  │   (static)   │  │  (static)    │  │  (static grid)   │ │
│  └─────────────┘  └──────────────┘  └──────────────────┘ │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              Content Area                            │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │  │
│  │  │ Product Card │  │ Product Card │  │  [Island]  │  │  │
│  │  │  (static)    │  │  (static)    │  │ User Cart  │  │  │
│  │  │  name, price │  │  name, price │  │ (dynamic)  │  │  │
│  │  │  image       │  │  image       │  │            │  │  │
│  │  │  ┌────────┐  │  │  ┌────────┐  │  └────────────┘  │  │
│  │  │  │[Island]│  │  │  │[Island]│  │                   │  │
│  │  │  │Like btn│  │  │  │Like btn│  │                   │  │
│  │  │  └────────┘  │  │  └────────┘  │                   │  │
│  │  └─────────────┘  └─────────────┘                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────────┐                                          │
│  │   <footer>   │                                         │
│  │   (static)   │                                         │
│  └─────────────┘                                          │
└───────────────────────────────────────────────────────────┘
```

### How It Maps to PyBend

In PyBend's current architecture, `<ntt-list>` and `<ntt-item>` Web Components fetch schema at runtime, create DynamicClasses via `prototype()`, and render entirely client-side. The islands pattern would:

1. **At build time:** Fetch schemas, fetch entity data, render HTML for static portions (product name, price, description, images)
2. **At load time:** Serve pre-built HTML (instant paint). Browser loads Web Component JS.
3. **At hydration:** Interactive islands (`<ntt-method>` buttons, edit toggles, like buttons) hydrate and become functional

### Astro's Server Islands --- The State of the Art

> Astro 5.0 features **Server Islands** --- an evolution of the islands architecture. Server islands combine high-performance static HTML with dynamic server-generated components on the same page. Static portions cache on Edge CDNs indefinitely, while dynamic content generates fresh for each request.
>
> *Source: [Astro 5.0 Blog](https://astro.build/blog/astro-5/), [Astro Islands Docs](https://docs.astro.build/en/concepts/islands/)*

**Performance profile:**
- Astro achieves **Lighthouse Score 100** with **0--5 KB JavaScript bundles** for content sites
- Astro is **2--3x faster and 50--80% cheaper** than equivalent Next.js deployments for content-heavy sites

*Source: [Senorit Benchmarks](https://senorit.de/en/blog/astro-vs-nextjs-2025)*

### Web Component SSR: The Lit Precedent

> Lit SSR renders Lit components and templates to **static HTML markup in non-browser JavaScript environments** like Node, using **Declarative Shadow DOM** to generate HTML that browsers can parse and attach shadow root content **without any JavaScript**.
>
> *Source: [Lit SSR Documentation](https://lit.dev/docs/ssr/overview/)*

This is directly relevant to PyBend's Web Component architecture. A compiler could:
1. Use Lit-style SSR techniques to pre-render `ntt-item` components
2. Emit Declarative Shadow DOM for the static shell
3. Let `ntt-method`, `ntt-list` (pagination), and form components hydrate client-side

### What to Pre-Compile vs. What to Leave Dynamic

| Component | Pre-compile? | Rationale |
|-----------|-------------|-----------|
| Page layout / chrome | **Yes** | Rarely changes, same for all users |
| Navigation (model list) | **Yes** | Derived from schema, stable |
| Entity data (read-only fields) | **Yes** | Name, price, description, images |
| `<ntt-method>` buttons | **No** | Require auth, trigger server calls |
| Edit/delete controls | **No** | Permission-dependent, user-specific |
| Pagination ("Load More") | **No** | Dynamic, depends on scroll position |
| Form rendering | **No** | Interactive, validation state |
| User identity (avatar, cart) | **No** | Personalized |
| `$schema` / `$id` metadata | **Yes** | Static per entity, useful for SEO |

---

## 8. Team and Workflow Impact

An HTML compiler changes how the team develops, tests, and deploys.

### Development Workflow Changes

| Aspect | Before (CSR Only) | After (With Compiler) |
|--------|-------------------|----------------------|
| **Preview a change** | Edit model, restart server, refresh browser | Edit model, wait for rebuild, refresh |
| **Hot reload** | Instant (client-side) | Requires incremental rebuild (seconds to minutes) |
| **Debug rendering** | Browser DevTools only | DevTools + build output inspection |
| **Deploy** | Push code, restart server | Push code, trigger build, wait, deploy artifacts |
| **Schema change** | Restart backend; frontend adapts at runtime | Restart backend + trigger full rebuild |
| **Content update** | API call + cache bust | API call + incremental rebuild OR webhook |
| **New model** | Add Python class, register, done | Add class, register, add to compiler config, rebuild |

### Developer Experience Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Slow feedback loop** | High | Dev mode with file watchers; bypass compiler in dev |
| **"It works locally" failures** | Medium | Compiler output parity with dev mode |
| **Build-only bugs** | Medium | Preview environments per PR |
| **Mental model complexity** | High | Clear documentation on what's static vs. dynamic |
| **Debugging compiled output** | Medium | Source maps or debug annotations in HTML |

### Impact on PyBend's "Zero Config" Promise

PyBend's philosophy is: **define a model, get an API, a schema, a working UI**. An HTML compiler adds a new step between "working UI" and "production-optimized UI." This must be framed as an **additive optimization** --- the runtime-rendered UI remains the default, and the compiler is an opt-in production enhancement.

---

## 9. Risk Analysis

### Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Stale content served to users** | High | Medium | TTL-based expiry, on-demand revalidation webhooks |
| **Build failure blocks deployment** | Medium | High | Fallback to previous build; separate build from deploy |
| **Cache invalidation bugs** | High | High | Purge-all fallback; monitoring for staleness |
| **Schema changes break compiler** | Medium | High | Compiler tests against schema contract |
| **Build time exceeds CI budget** | Medium | Medium | Incremental builds, parallelization |
| **Developer confusion (static vs. dynamic)** | Medium | Medium | Clear conventions, documentation |
| **SEO regression from stale HTML** | Low | High | Sitemap freshness checks, crawler alerts |
| **Edge cases in schema rendering** | High | Low | Progressive enhancement; CSR fallback |

### The Cache Invalidation Problem in Depth

> **"There are only two hard things in Computer Science: cache invalidation and naming things."** --- Phil Karlton

Real-world incidents demonstrate the severity:

> At Meta, operating some of the largest cache deployments in the world, a rare transient error during cache invalidation triggered error handling code that **dropped the item in cache, leaving stale metadata indefinitely**. They improved TAO's cache consistency from 99.9999% to 99.99999999%.
>
> *Source: [Meta Engineering Blog](https://engineering.fb.com/2022/06/08/core-infra/cache-made-consistent/)*

> For static site hosting, slow cache invalidation is a major issue. CDN hosting services make users wait **anywhere from 10 minutes to several hours** for changes to propagate.
>
> *Source: [Netlify Blog](https://www.netlify.com/blog/2015/09/11/instant-cache-invalidation/)*

### Cache Invalidation Strategies for Static Sites

| Strategy | Latency | Complexity | Failure Mode |
|----------|---------|-----------|--------------|
| **Full rebuild on any change** | Minutes to hours | Low | Slow but correct |
| **Incremental rebuild (dependency graph)** | Seconds to minutes | High | Missed dependencies = stale content |
| **On-demand revalidation (webhooks)** | Seconds | Medium | Webhook failures = stale content |
| **TTL-based expiry** | Configurable | Low | Guaranteed staleness window |
| **Generational cache keys** (versioned URLs) | Instant for changed pages | Medium | Orphaned old versions consume storage |

**Recommended combination:** TTL as safety net + on-demand webhooks for critical changes + generational keys for correctness.

---

## 10. Full Rendering Strategy Comparison

### Decision Matrix: 15 Criteria Across 5 Strategies

| Criteria | SSG | ISR | SSR | Streaming SSR | CSR (SPA) |
|----------|-----|-----|-----|---------------|-----------|
| **TTFB** | Fastest (~10ms) | Fast (~10-50ms) | Slow (~200-500ms) | Fast (~45ms) | Fast (static shell) |
| **LCP** | Fastest | Fast | Medium | Fast (~380ms) | Slowest |
| **FCP** | Fastest | Fast | Medium | Fastest (streaming) | Slowest |
| **INP (Interactivity)** | Good (minimal JS) | Good | Good | Good | Best |
| **Data freshness** | Build-time only | Periodic/on-demand | Real-time | Real-time | Real-time |
| **SEO** | Excellent | Excellent | Excellent | Excellent | Poor (without SSR) |
| **Personalization** | None | None (without edge) | Full | Full | Full |
| **Build time** | High (scales with pages) | Low (initial only) | None | None | None |
| **Server cost** | Lowest | Low | Highest | High | Lowest |
| **CDN-friendly** | Perfect | Good | Requires config | Requires config | Perfect |
| **Offline support** | Excellent (with SW) | Good (with SW) | None | None | Good (with SW) |
| **Developer complexity** | Medium | Medium-High | Medium | High | Low |
| **Scalability** | Linear (CDN) | Linear (CDN + lazy) | Vertical (servers) | Vertical | Linear (CDN) |
| **Deployment speed** | Slow (build required) | Fast (lazy pages) | Instant | Instant | Fast |
| **Cache invalidation** | Full rebuild or ISR | Built-in | N/A | N/A | Client-managed |

*Sources: [Vercel Rendering Strategy Guide](https://vercel.com/blog/how-to-choose-the-best-rendering-strategy-for-your-app), [Ramotion Web Rendering Types](https://www.ramotion.com/blog/web-rendering-types-comparison/), [SitePoint RSC Guide](https://www.sitepoint.com/react-server-components-streaming-performance-2026/)*

### Hybrid: The Industry Consensus

> **"The most effective applications often combine rendering methods to optimize different components."**
>
> *Source: [Vercel Blog](https://vercel.com/blog/how-to-choose-the-best-rendering-strategy-for-your-app)*

The recommended pattern for 2026:

```
Marketing / landing pages  ──>  SSG
Product catalog (public)   ──>  ISR (revalidate: 3600)
Product detail             ──>  ISR (revalidate: 300) + client islands
User dashboard             ──>  SSR or CSR
Real-time features         ──>  CSR + WebSocket
Documentation              ──>  SSG
```

---

## 11. The Compilation Budget

How much build time is acceptable before it degrades productivity?

### Industry Standards

> Kent Beck's 10-Minute Build guideline: **"A build that takes longer than ten minutes will be used much less often, missing the opportunity for feedback."**
>
> *Source: [Graphite Blog](https://graphite.com/blog/how-long-should-ci-take)*

### Empirical Data on Build Time vs. Productivity

| CI Time Range | Developer Impact | Recommendation |
|---------------|-----------------|----------------|
| **< 5 min** | Optimal feedback loop | Ideal target |
| **5--10 min** | Acceptable; developer can context-switch | Good |
| **10--15 min** | Noticeable productivity decline | Tolerable |
| **15--30 min** | Highest PR merge rate (counter-intuitive*) | Active optimization recommended |
| **30+ min** | **Danger zone** --- requires DevOps intervention | Unacceptable without incremental builds |
| **45+ min** | Vercel's hard limit per deployment | Architectural problem |

> \* The 15--30 minute range correlating with high PR merge rates reflects mature teams with complex products --- not a recommendation to slow down builds.
>
> **Key finding:** Each additional 5 minutes of CI time increases average time-to-merge by **over 1 hour**, because CI runs multiple times during a PR's lifecycle.
>
> *Source: [Graphite Blog](https://graphite.com/blog/how-long-should-ci-take)*

### Compilation Budget by Application Type

| Application Type | Acceptable Build Time | Page Budget (at ~3ms/page) |
|-----------------|----------------------|---------------------------|
| **Startup / MVP** | < 2 min | ~40,000 pages |
| **Growth-stage SaaS** | < 5 min | ~100,000 pages |
| **Enterprise** | < 15 min | ~300,000 pages |
| **Media / publishing** | < 30 min (with incremental) | ~600,000 pages |

### How to Stay Within Budget

1. **Incremental builds:** Only rebuild pages whose data changed (requires dependency graph)
2. **Parallel workers:** Scale horizontally (Gatsby demonstrated linear scaling with workers)
3. **Priority tiers:** Build top 1,000 pages statically, serve rest via ISR
4. **Deferred generation:** Build pages on first request, cache forever after
5. **Build-time data caching:** Hugo's cache reduces rebuild times by **up to 50%** for unchanged content

*Source: [Hugo Caching Strategies](https://dasroot.net/posts/2025/11/hugo-caching-strategies/)*

---

## 12. Migration Strategies

Adopting static generation does not require a big-bang rewrite. Incremental adoption is the industry-proven approach.

### The Strangler Fig Pattern for Static Migration

```
Phase 0: Current State
┌──────────────────────────────────────────────┐
│ All pages rendered client-side (CSR via       │
│ Web Components fetching schemas at runtime)   │
└──────────────────────────────────────────────┘

Phase 1: Static Shell
┌──────────────────────────────────────────────┐
│ Pre-build page chrome (nav, footer, layout)   │
│ Client-side rendering for all content         │
│ Benefit: Faster FCP, reduced layout shift     │
└──────────────────────────────────────────────┘

Phase 2: Public Content SSG
┌──────────────────────────────────────────────┐
│ Pre-build public entity pages (products, docs)│
│ CSR fallback for authenticated content        │
│ Benefit: SEO, sub-100ms TTFB for public pages │
└──────────────────────────────────────────────┘

Phase 3: ISR for Semi-Dynamic Content
┌──────────────────────────────────────────────┐
│ ISR for frequently-updated public pages       │
│ SSG for stable content                        │
│ CSR for dashboards and authenticated views    │
│ Benefit: Fresh content without full rebuilds  │
└──────────────────────────────────────────────┘

Phase 4: Full Hybrid
┌──────────────────────────────────────────────┐
│ Static shell + server/client islands          │
│ Schema-aware build pipeline                   │
│ On-demand regeneration via webhooks           │
│ CSR-only for real-time interactive features   │
│ Benefit: Optimal per-page rendering strategy  │
└──────────────────────────────────────────────┘
```

### Incremental Adoption Tactics

> **"Incremental migrations minimize risk by reducing the scope of individual migration steps, have a more natural path to rolling back, and allow validating technical implementation and business value substantially earlier."**
>
> *Source: [Vercel Blog on Incremental Migrations](https://vercel.com/blog/incremental-migrations), [Martin Fowler on Incremental Migration](https://martinfowler.com/bliki/IncrementalMigration.html)*

| Tactic | Description | Risk |
|--------|-------------|------|
| **Subpath routing** | Serve `/docs/*` from static build, everything else from dynamic app | Low |
| **Page-by-page migration** | Move one page type at a time (docs first, then products, then lists) | Low |
| **Feature flags** | Toggle between static and dynamic rendering per route | Medium |
| **A/B deployment** | Run static and dynamic in parallel, compare metrics | Low |
| **Fallback chain** | Serve static if available, fall back to dynamic render | Low |

### PyBend-Specific Migration Path

Given PyBend's architecture, the cleanest migration would be:

1. **Phase 1 (Week 1--2):** Add `Cache-Control` headers to schema and public list endpoints
2. **Phase 2 (Week 3--4):** Implement a Service Worker for schema caching and stale-while-revalidate on entity lists
3. **Phase 3 (Week 5--8):** Build a schema-walking pre-renderer that generates static HTML for public entity pages
4. **Phase 4 (Week 9--12):** Add incremental rebuild support triggered by storage write hooks
5. **Phase 5 (ongoing):** Implement islands pattern for interactive elements within pre-rendered pages

---

## 13. Organizational Readiness Checklist

Before building an HTML compiler, ensure these prerequisites are in place.

### Infrastructure Requirements

| Requirement | Status Check | Priority |
|-------------|-------------|----------|
| CI/CD pipeline with adequate compute budget | Do builds complete in < 45 min? | Critical |
| CDN with instant invalidation capability | Can you purge a URL in < 10s? | Critical |
| Staging/preview environments per PR | Can reviewers see compiled output before merge? | High |
| Monitoring for staleness detection | Can you alert on content age > threshold? | High |
| Artifact storage for build outputs | Where do compiled HTML files live? | Medium |
| Webhook infrastructure | Can data changes trigger rebuilds? | Medium |
| Parallel build workers | Can the CI scale horizontally? | Medium |

### Team Readiness

| Requirement | Check | Priority |
|-------------|-------|----------|
| Team understands the static/dynamic boundary | Can they explain what gets compiled vs. hydrated? | Critical |
| Build pipeline expertise | Does someone own CI/CD? | Critical |
| Cache invalidation experience | Has the team debugged stale content before? | High |
| Monitoring/observability maturity | Are there dashboards for build health? | High |
| Schema stability | Are models changing daily or weekly? | Medium |
| Documentation culture | Will the team document the compiler's contract? | Medium |

### Process Requirements

| Requirement | Description | Priority |
|-------------|-------------|----------|
| **Build-deploy separation** | Failed builds must not block rollback to previous version | Critical |
| **Content preview** | Editors/stakeholders can preview compiled pages before publish | High |
| **Incremental rollout** | Can route some traffic to static, some to dynamic | High |
| **Rollback procedure** | One-click revert to previous compiled version | Critical |
| **Build monitoring** | Alerts on build time regression, build failures | High |

---

## 14. WebGPU/WebGL Content Considerations

Can you statically generate canvas-based content?

### Short Answer: No --- But You Can Optimize the Shell

Canvas elements (`<canvas>`), WebGL contexts, and WebGPU pipelines are inherently runtime constructs. They require:
- A GPU or software renderer
- JavaScript execution
- Per-frame rendering loops

None of these can be pre-computed into static HTML.

### What You CAN Do

| Optimization | Description | Benefit |
|-------------|-------------|---------|
| **Static shell around canvas** | Pre-render layout, controls, labels; leave canvas as placeholder | Faster FCP, reduced layout shift |
| **Placeholder image** | Render a screenshot as `<img>` fallback, swap to canvas on hydration | Instant visual; progressive enhancement |
| **Lazy initialization** | `loading="lazy"` pattern for canvas; init only when in viewport | Reduced initial JS payload |
| **Preload GPU resources** | `<link rel="preload">` for shaders, textures, WASM modules | Faster time-to-interactive |
| **SSR metadata** | Pre-render alt text, dimensions, ARIA labels for the canvas region | Accessibility + SEO |

> **WebGPU performance context:** Chrome 124 shows WebGPU handling **10 million-point scatter arrays at >45 FPS** on consumer laptops. The rendering itself is fast; the bottleneck is initialization and JS download, both of which benefit from shell optimization.
>
> *Source: [Toji.dev WebGPU Best Practices](https://toji.dev/webgpu-best-practices/webgl-performance-comparison.html)*

### The Pattern: Static Shell + Canvas Island

```html
<!-- Pre-compiled static shell -->
<div class="visualization-container">
  <h2>Revenue by Region</h2>
  <p class="description">Interactive 3D visualization of Q4 revenue data</p>

  <!-- Placeholder (static) -->
  <img src="/generated/revenue-preview.png"
       alt="Revenue chart showing APAC leading at $4.2M"
       width="800" height="600"
       class="canvas-placeholder" />

  <!-- Canvas island (hydrates on load) -->
  <canvas id="revenue-viz"
          data-src="/api/revenue"
          width="800" height="600"
          style="display: none">
  </canvas>

  <noscript>
    <p>Enable JavaScript for the interactive visualization.</p>
  </noscript>
</div>

<script type="module">
  // Island: only this code runs client-side
  import { initViz } from './revenue-viz.js';
  const canvas = document.getElementById('revenue-viz');
  const placeholder = document.querySelector('.canvas-placeholder');
  await initViz(canvas);
  placeholder.style.display = 'none';
  canvas.style.display = 'block';
</script>
```

---

## 15. Decision Tree

Use this tree to determine the right rendering strategy for each page type in your application.

```
                    ┌──────────────────────────────┐
                    │  What type of content is it?  │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┼───────────────┐
                    │              │               │
                    v              v               v
            ┌──────────┐  ┌───────────┐   ┌──────────────┐
            │  Public   │  │  Auth'd   │   │  Real-time   │
            │  Content  │  │  Content  │   │  Interactive │
            └─────┬────┘  └─────┬─────┘   └──────┬───────┘
                  │             │                  │
                  v             v                  v
          ┌──────────────┐   ┌────────┐    ┌─────────────┐
          │ How often     │   │  SSR   │    │    CSR /     │
          │ does it       │   │  or    │    │  WebSocket   │
          │ change?       │   │  CSR   │    │    SPA       │
          └───────┬──────┘   └────────┘    └─────────────┘
                  │
       ┌──────────┼────────────┐
       │          │            │
       v          v            v
   ┌────────┐ ┌────────┐ ┌──────────┐
   │ Rarely │ │ Hourly │ │ Minutes  │
   │ (days) │ │        │ │ or less  │
   └───┬────┘ └───┬────┘ └────┬─────┘
       │          │            │
       v          v            v
   ┌───────┐  ┌──────┐   ┌─────────────┐
   │  SSG  │  │ ISR  │   │ SSR + edge  │
   │       │  │      │   │ cache (short│
   │       │  │      │   │    TTL)     │
   └───┬───┘  └──┬───┘   └─────────────┘
       │         │
       v         v
   ┌───────────────────────────┐
   │  How many pages?          │
   └───────────┬───────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
    v          v          v
 ┌──────┐  ┌──────┐  ┌──────────┐
 │ <10K │  │10-50K│  │  >50K    │
 └──┬───┘  └──┬───┘  └────┬─────┘
    │         │            │
    v         v            v
 ┌──────┐  ┌──────────┐  ┌─────────────────┐
 │ Full │  │ SSG top  │  │ SSG top 1-5K    │
 │ SSG  │  │ pages +  │  │ ISR for rest    │
 │      │  │ ISR rest │  │ On-demand build │
 └──────┘  └──────────┘  └─────────────────┘
```

### Quick Reference: Strategy Selector

| Your situation | Recommended strategy |
|----------------|---------------------|
| Marketing site, < 500 pages | Full SSG |
| Blog, < 5,000 posts | Full SSG |
| Documentation, < 10,000 pages | Full SSG (Hugo or Astro) |
| E-commerce catalog, < 50,000 products | SSG top 1K + ISR rest |
| E-commerce catalog, > 50,000 products | ISR only (no full SSG) |
| SaaS dashboard | SSR or CSR (no SSG) |
| Social feed / real-time content | CSR + WebSocket |
| Mixed public + auth content | Static shell + dynamic islands |
| Internal tool | CSR / SPA (no SSG benefit) |
| Schema-driven framework (like PyBend) | CDN caching + Service Worker first; then static shell + islands if needed |

---

## 16. PyBend-Specific Analysis

### Current Architecture: Pure CSR

PyBend currently operates as a pure client-side rendered application:

```
Browser loads matrix.html
    │
    v
<ntt-list model="Product"> mounts
    │
    v
Fetch schema: GET /Product ──> JSON Schema
    │
    v
NTT.SCHEMA() ──> prototype() ──> DynamicClass
    │
    v
DynamicClass.READ ──> GET /products?limit=20 ──> JSON
    │
    v
Create instances, render via ntt-item components
    │
    v
User sees content (after all JS + network round-trips)
```

**Current performance profile (estimated):**
- TTFB: ~5ms (just serving static HTML shell)
- FCP: ~200--400ms (JS parse + load)
- LCP: ~800--1500ms (schema fetch + data fetch + render)
- Total JS transferred: Full NTT.js stack

### What an HTML Compiler Would Change

```
Build time:
    Walk registered_models ──> Fetch schemas ──> Fetch entity data
        │
        v
    For each model with __access__.read == ANYONE:
        For each entity:
            Render static HTML (name, price, description, etc.)
            Emit <ntt-method> placeholders for interactive parts
            Write .html file to /compiled/{tablename}/{id}.html
        Render list page: /compiled/{tablename}/index.html

Runtime:
    Browser loads /compiled/products/index.html (pre-rendered)
        │
        v
    FCP: ~50ms (static HTML, no JS needed for initial paint)
        │
        v
    JS loads, hydrates interactive islands (ntt-method, edit, etc.)
        │
        v
    LCP: ~100-200ms (content was already in HTML)
```

### Where PyBend Is Different from Typical SSG Targets

| Factor | Typical SSG Target | PyBend |
|--------|-------------------|--------|
| **Content source** | Markdown files, CMS API | Python model instances via SQL |
| **Schema** | Implicit (component props) | Explicit JSON Schema (single source of truth) |
| **Frontend framework** | React, Vue, Svelte | Vanilla Web Components |
| **Rendering** | Framework-specific SSR | Custom (no existing SSR path) |
| **Data lifecycle** | CMS publish events | Direct DB writes |
| **Auth model** | Token-based, separate layer | ABAC rules embedded in schema |

### The Schema Advantage

PyBend's JSON Schema is **uniquely well-suited** for static generation because:

1. **The schema carries rendering instructions.** `ui.widget`, `ui.field_order`, `ui.groups` --- the compiler has everything it needs to generate HTML.
2. **Access rules are declarative.** The compiler can determine `__access__.read == ANYONE` at build time and only compile public pages.
3. **`$defs` provide the full graph.** Nested models (Product -> Comment) are self-describing; the compiler can recursively generate pages.
4. **`model_dump(response=True)` provides `$schema` and `$id`.** Each entity self-describes its type and location --- perfect for generating linked static pages.

### Recommended PyBend Strategy

Given the analysis across all dimensions, the recommended path for PyBend is:

```
┌─────────────────────────────────────────────────────────────┐
│              PyBend Rendering Optimization Path              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  NOW (Week 1-2):                                           │
│  ├─ Add Cache-Control headers to schema endpoints           │
│  ├─ Add Cache-Control headers to public list endpoints      │
│  └─ Measure TTFB improvement                                │
│                                                             │
│  NEXT (Week 3-4):                                          │
│  ├─ Implement Service Worker for schema caching             │
│  ├─ stale-while-revalidate for entity list data             │
│  └─ Measure repeat-visit performance                        │
│                                                             │
│  LATER (Month 2-3): Only if metrics justify it              │
│  ├─ Build schema-walking HTML pre-renderer                  │
│  ├─ Target: public-access models only                       │
│  ├─ Static shell + Web Component islands                    │
│  └─ Serve from CDN with ISR-style invalidation              │
│                                                             │
│  FUTURE (Month 4+): Only if adoption demands it             │
│  ├─ Incremental rebuild via storage write hooks              │
│  ├─ Lit-style Declarative Shadow DOM for ntt-item            │
│  └─ Full build pipeline with CI/CD integration              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 17. Recommendations

### For Technical Leadership

1. **Do not build an HTML compiler first.** Start with CDN caching and Service Workers. These deliver 80% of the performance gain at 5% of the cost and risk.

2. **Measure before building.** Instrument current TTFB, FCP, and LCP. If TTFB is already < 100ms (likely, since PyBend serves a lightweight HTML shell), the compiler's marginal gain may not justify its cost.

3. **If you proceed, use the islands pattern.** Do not attempt full SSR of Web Components. Pre-render the static shell and entity data; let interactive components hydrate client-side.

4. **Leverage the schema.** PyBend's architecture is uniquely suited for compilation because the schema carries rendering instructions. The compiler should walk the schema graph, not duplicate rendering logic.

5. **Set a compilation budget.** For a schema-driven framework, target < 5 minutes for a full rebuild. If entity count pushes past this, implement incremental builds immediately.

6. **Make it opt-in.** The compiler should be an additive optimization, not a required step. `create_app(compiler=True)` or a separate CLI command. The runtime-rendered UI remains the default.

### Decision Summary

| Question | Answer |
|----------|--------|
| Should we build an HTML compiler? | Not yet. Start with caching. |
| When should we reconsider? | When TTFB > 200ms on public pages after caching |
| What's the right pattern? | Static shell + dynamic islands |
| What's the estimated cost? | $45K--100K + $600--1,400/month maintenance |
| What's the estimated timeline? | 9--14 weeks for full implementation |
| What's the break-even? | ~12--18 months vs. SSR cost savings |
| What's the fastest alternative? | CDN caching (1 hour) + Service Worker (1--2 days) |

---

## 18. Sources

### Rendering Strategy & Architecture
- [Vercel: How to Choose the Best Rendering Strategy](https://vercel.com/blog/how-to-choose-the-best-rendering-strategy-for-your-app)
- [Ramotion: Web Rendering Types Comparison](https://www.ramotion.com/blog/web-rendering-types-comparison/)
- [Shoaibsid: ISR vs SSR vs SSG in 2025](https://www.shoaibsid.dev/blog/incremental-static-regeneration-isr-vs-ssr-vs-ssg-in-2025-real-world-use-cases-with-next-js)
- [Crystallize: Web Rendering Explained](https://crystallize.com/blog/web-rendering)
- [Storyblok: Next.js ISR against SSR & SSG](https://www.storyblok.com/mp/nextjs-incremental-static-regeneration)
- [SitePoint: React Server Components Streaming Performance Guide 2026](https://www.sitepoint.com/react-server-components-streaming-performance-2026/)

### Build Time & SSG Benchmarks
- [CSS-Tricks: Comparing Static Site Generator Build Times](https://css-tricks.com/comparing-static-site-generator-build-times/)
- [Hugo: Build Performance](https://gohugo.io/troubleshooting/performance/)
- [Hugo Caching Strategies for Maximum Performance](https://dasroot.net/posts/2025/11/hugo-caching-strategies/)
- [Gatsby: How We're Scaling to Millions of Pages](https://www.gatsbyjs.com/blog/how-were-scaling-gatsby-to-millions-of-pages/)
- [Next.js Discussion #14122: 30 min for 3K SSG pages](https://github.com/vercel/next.js/discussions/14122)
- [Senorit: Astro vs Next.js 2026 Benchmarks](https://senorit.de/en/blog/astro-vs-nextjs-2025)

### Islands Architecture & Partial Hydration
- [Astro: Islands Architecture](https://docs.astro.build/en/concepts/islands/)
- [Astro 5.0 Release Blog](https://astro.build/blog/astro-5/)
- [Patterns.dev: Islands Architecture](https://www.patterns.dev/vanilla/islands-architecture/)
- [Jason Format: Islands Architecture](https://jasonformat.com/islands-architecture/)
- [Lit SSR Documentation](https://lit.dev/docs/ssr/overview/)
- [Spicy Web: Server-Render a Web Component](https://www.spicyweb.dev/web-components-ssr-node/)

### Caching & CDN
- [web.dev: Service Worker Caching and HTTP Caching](https://web.dev/articles/service-worker-caching-and-http-caching)
- [Chrome Developers: Caching Strategies for Service Workers](https://developer.chrome.com/docs/workbox/caching-strategies-overview)
- [Meta Engineering: Cache Made Consistent](https://engineering.fb.com/2022/06/08/core-infra/cache-made-consistent/)
- [Redis: Cache Invalidation](https://redis.io/glossary/cache-invalidation/)
- [Netlify: Instant Cache Invalidation](https://www.netlify.com/blog/2015/09/11/instant-cache-invalidation/)
- [SmartSMS: CDN vs Edge Caching Explained](https://smartsmssolutions.com/resources/blog/business/cdn-vs-edge-caching-explained)
- [Vyakymenko: Edge Rendering vs Static vs Serverful Trade-offs](https://medium.com/@vyakymenko/edge-rendering-vs-static-vs-serverful-trade-offs-8f720d69dc7b)

### Performance & Core Web Vitals
- [web.dev: General HTML Performance Considerations](https://web.dev/learn/performance/general-html-performance)
- [MDN: HTML Performance Optimization](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Performance/HTML)
- [web.dev: Rendering on the Web](https://web.dev/articles/rendering-on-the-web)
- [Developerway: React Server Components Performance](https://www.developerway.com/posts/react-server-components-performance)

### CI/CD & Build Budgets
- [Graphite: How Long Should Your CI Take?](https://graphite.com/blog/how-long-should-ci-take)
- [CircleCI Pricing](https://circleci.com/pricing/)
- [Google Cloud Build Pricing](https://cloud.google.com/build)
- [Azure DevOps Pricing](https://azure.microsoft.com/en-us/pricing/details/devops/azure-devops-services/)
- [GitLab CI/CD Compute Minutes](https://docs.gitlab.com/ci/pipelines/compute_minutes/)

### Cost Analysis
- [Vercel Pricing](https://vercel.com/pricing)
- [Vercel ISR Limits and Pricing](https://vercel.com/docs/incremental-static-regeneration/limits-and-pricing)
- [Flexprice: Breaking Down Vercel's 2025 Pricing](https://flexprice.io/blog/vercel-pricing-breakdown)
- [Pagepro: How to Lower Vercel Hosting Costs by 35%](https://pagepro.co/blog/vercel-hosting-costs/)

### Migration Strategies
- [Vercel: Why All Migrations Should Be Incremental](https://vercel.com/blog/incremental-migrations)
- [Martin Fowler: Incremental Migration](https://martinfowler.com/bliki/IncrementalMigration.html)
- [Addy Osmani: Incremental Migrations](https://addyosmani.com/blog/incremental-migrations/)
- [Next.js: Incremental Adoption](https://nextjs-ja-translation-docs.vercel.app/docs/migrating/incremental-adoption)

### WebGPU/WebGL
- [Toji.dev: WebGPU/WebGL Performance Comparison](https://toji.dev/webgpu-best-practices/webgl-performance-comparison.html)
- [MDN: WebGPU API](https://developer.mozilla.org/en-US/docs/Web/API/WebGPU_API)
- [ACM: GL2GPU Dynamic API Translation to WebGPU](https://dl.acm.org/doi/10.1145/3696410.3714785)

### SSG Landscape
- [Hygraph: Top 12 SSGs in 2026](https://hygraph.com/blog/top-12-ssgs)
- [CloudCannon: Top 5 SSGs for 2025](https://cloudcannon.com/blog/the-top-five-static-site-generators-for-2025-and-when-to-use-them/)
- [Crystallize: React Static Site Generators in 2025](https://crystallize.com/blog/react-static-site-generators)
