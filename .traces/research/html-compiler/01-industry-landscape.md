# 🏢 Industry Landscape: Static HTML Generation & Pre-Rendering in Production

> **Who compiles HTML at build time, who renders at runtime, and what measurable results do they see?**
>
> Research brief for engineering leadership evaluating an HTML compiler for a schema-driven framework (N3TX).
> February 2026

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [The Rendering Spectrum](#the-rendering-spectrum)
3. [Framework Landscape: Who Offers What](#framework-landscape)
4. [Performance Data: Core Web Vitals by Rendering Strategy](#performance-data)
5. [The Islands Architecture Movement](#islands-architecture)
6. [Qwik's Resumability: Killing Hydration](#qwik-resumability)
7. [Partial & Progressive Hydration](#partial-progressive-hydration)
8. [Case Studies: SPA to Static/Hybrid Migrations](#case-studies)
9. [Google's Research: Speed and Business Metrics](#google-speed-research)
10. [Edge Rendering: The CDN Becomes the Server](#edge-rendering)
11. [Prerendering at Scale: Puppeteer, Rendertron, Prerender.io](#prerendering-at-scale)
12. [Schema-Driven Static Generation: The Emerging Pattern](#schema-driven-generation)
13. [Jamstack Evolution & Post-Jamstack](#jamstack-evolution)
14. [The Static Shell + Dynamic Islands Pattern](#static-shell-pattern)
15. [Build-Time vs Runtime Rendering: Hard Numbers](#build-vs-runtime)
16. [Strategic Implications for N3TX](#strategic-implications)
17. [Sources](#sources)

---

## Executive Summary

The web industry has spent 2020-2026 systematically proving one thesis: **the less JavaScript you ship and the earlier you deliver HTML, the better every metric gets** -- performance, SEO, conversion, bounce rate, and developer experience.

**Key findings:**

- **Static HTML pages achieve TTFB under 50ms** from CDN edge, compared to 200-800ms for server-rendered and 1-3s for client-rendered SPAs
- **Build-time rendering eliminates 200-500ms of hydration overhead** that traditional SSR frameworks impose on every page load ([Web Almanac 2024](https://almanac.httparchive.org/))
- **A 0.1s improvement in load time increases conversions 8-10%** in e-commerce ([Google/Deloitte research](https://business.google.com/ca-en/think/marketing-strategies/mobile-page-speed-new-industry-benchmarks/))
- **Astro (islands architecture) scores 99.2/100 Lighthouse**, the highest of any JS framework benchmarked ([Enterspeed 2025](https://www.enterspeed.com/blog/we-measured-the-ssr-performance-of-6-js-frameworks-heres-what-we-found))
- **The Jamstack market grew from $1.8B (2020) to $8.6B (2025)**, with 35% of developers identifying as Jamstack-aligned
- **Netflix cut Time-to-Interactive by 50%** by replacing React SPA with server-rendered HTML + vanilla JS ([Addy Osmani, Chrome team](https://medium.com/dev-channel/a-netflix-web-performance-case-study-c0bcde26a9d9))
- **No existing framework compiles from a data schema to static HTML** the way N3TX could -- this is a genuine whitespace opportunity

> 💡 **Bottom line:** The industry has converged on hybrid rendering (static shell + dynamic islands) as the 2025-2026 best practice. A schema-driven framework that can compile models directly to optimized HTML would leapfrog the current generation by eliminating both the template layer and the hydration cost.

---

## The Rendering Spectrum

The industry has moved from a binary SSR-vs-SPA debate to a **spectrum of rendering strategies**, each with distinct performance profiles and trade-offs.

| Strategy | TTFB | LCP | TTI | JS Shipped | When Content Updates | Best For |
|----------|------|-----|-----|------------|---------------------|----------|
| **Fully Static (SSG)** | ⚡ <50ms | ⚡ 0.3-0.5s | ⚡ 0.3-0.5s | Zero to minimal | Build time only | Blogs, docs, marketing |
| **ISR (Incremental Static)** | ⚡ <50ms (cached) | ⚡ 0.4-0.8s | ⚡ 0.4-0.8s | Minimal | Background revalidation | E-commerce catalogs |
| **Streaming SSR** | 🟡 30-50ms shell | 🟡 0.5-1.2s | 🟡 0.8-2.0s | Moderate | Every request | Dashboards, feeds |
| **SSR (Traditional)** | 🟠 100-500ms | 🟠 0.8-2.0s | 🟠 1.5-3.0s | Heavy | Every request | Dynamic apps |
| **SPA (Client-Side)** | ❌ 50-200ms (empty shell) | ❌ 1.5-4.0s | ❌ 2.0-5.0s+ | Very heavy | Client-side fetch | Highly interactive apps |

> ⚠️ **The critical insight:** Moving left on this spectrum (toward static) improves every user-facing metric. The question is not "should we go static?" but "how much of the page can be static?"

**The hybrid consensus (2025-2026):** No single approach fits all needs. The industry standard is now **hybrid rendering** -- frameworks that let you mix strategies per-page or even per-component. Next.js, Nuxt, SvelteKit, and Astro all support this. [Sparkbox rendering comparison](https://sparkbox.com/foundry/ui_rendering_frameworks_next.js_astro_qwik_rendering_strategies_tested_time_to_interactive_total_blocking_time_largest_contentful_paint_measured)

---

## Framework Landscape

### Who Offers What

| Framework | SSG | ISR | SSR | Streaming | Islands | Resumability | Edge | Schema-Driven |
|-----------|-----|-----|-----|-----------|---------|-------------|------|---------------|
| **Next.js** | ✅ | ✅ | ✅ | ✅ | ✅ (PPR) | ❌ | ✅ | ❌ |
| **Astro** | ✅ | ❌ | ✅ | ✅ | ✅ (native) | ❌ | ✅ | ❌ |
| **Qwik** | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ (native) | ✅ | ❌ |
| **SvelteKit** | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| **Nuxt 3** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| **Gatsby** | ✅ | ❌ | ✅ | ❌ | ✅ (partial) | ❌ | ❌ | ❌ (GraphQL layer) |
| **Eleventy** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Remix** | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| **Fresh (Deno)** | ❌ | ❌ | ✅ | ✅ | ✅ (native) | ❌ | ✅ | ❌ |
| **Marko (eBay)** | ❌ | ❌ | ✅ | ✅ (native) | ✅ | ❌ | ❌ | ❌ |
| **Hugo** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **N3TX (proposed)** | 🎯 | 🎯 | ✅ | ❌ | 🎯 | ❌ | ❌ | ✅ (unique) |

> 💡 **The gap:** No framework in the table above generates HTML from a data schema definition. Every framework requires developers to write templates, components, or pages. **N3TX's schema-driven approach would be unique in the landscape** -- the model IS the template.

### Framework-by-Framework Analysis

**Next.js** -- The market leader (40% adoption among SSR frameworks). Introduced **Partial Pre-Rendering (PPR)** in 2024, which renders a static shell immediately from edge cache while streaming dynamic components via Suspense boundaries. This hybrid approach means "instant" page loads even with live data. ISR revalidates cached pages in the background on configurable intervals. [Next.js docs](https://nextjs.org/docs/pages/building-your-application/rendering/static-site-generation) | [Prateeksha comparison](https://prateeksha.com/blog/ssr-vs-ssg-vs-isr-nextjs-rendering-modes)

**Astro** -- The performance champion (18% adoption, growing fast). Ships **zero JavaScript by default** and only hydrates interactive "islands." Achieved the highest Lighthouse score (99.2) among benchmarked frameworks. GitHub stars grew from 500 (2020) to 40,000+ (2024). Introduced **Server Islands** in 2024, allowing individual components to render on the server while the rest of the page is static. [Enterspeed benchmark](https://www.enterspeed.com/blog/we-measured-the-ssr-performance-of-6-js-frameworks-heres-what-we-found) | [Astro docs](https://docs.astro.build/en/concepts/islands/)

**Qwik** -- The radical rethink. Eliminates hydration entirely via **resumability** (see dedicated section below). Achieves near-instant TTI regardless of application size. Adoption is small but growing among performance-obsessed teams. [Qwik docs](https://qwik.dev/docs/concepts/resumable/) | [Builder.io benchmarks](https://github.com/BuilderIO/framework-benchmarks)

**SvelteKit** -- Compiler-first approach. Svelte compiles components to vanilla JS at build time, shipping 20-40% smaller bundles than React equivalents. Hits ~90/100 Lighthouse scores. Pre-render support via `adapter-static`. [CloudCannon SSG comparison](https://cloudcannon.com/blog/the-top-five-static-site-generators-for-2025-and-when-to-use-them/)

**Nuxt 3** -- Vue's answer to Next.js. Built on the Nitro engine, supports hybrid rendering. Scored 98.8 in Enterspeed benchmarks. `nuxt generate` exports fully static sites. ISR support via `routeRules`. [Enterspeed benchmark](https://www.enterspeed.com/blog/we-measured-the-ssr-performance-of-6-js-frameworks-heres-what-we-found)

**Gatsby** -- Pioneer of GraphQL-powered SSG. Sites average 7-10 Lighthouse points higher than Next.js/Nuxt on mobile. Added partial hydration support. However, adoption has declined since 2023, and Netlify (acquirer) has deprioritized development. [Gatsby performance comparison](https://www.gatsbyjs.com/blog/comparing-website-performance-gatsby-vs-next-vs-nuxt/)

**Eleventy (11ty)** -- The simplest SSG. No bundler, no framework lock-in, pure HTML output. Fastest build times for small-to-medium sites. Top Lighthouse scores through progressive enhancement. [CloudCannon review](https://cloudcannon.com/blog/eleventy-11ty-vs-gatsby-in-2023-which-ssg-is-best-for-you/)

**Remix** -- SSR-only by design (no built-in SSG). Achieves CDN-like speed through aggressive `Cache-Control` headers and `stale-while-revalidate`. Scored 98.8 Lighthouse with 136ms TTFB. Now merging with React Router and adding RSC support. [Remix docs](https://remix.run/blog/react-server-components)

**Fresh (Deno)** -- Islands architecture with zero client JS by default. Renders on the server at the edge via Deno Deploy. Ahead-of-time compilation caches client assets. Deno's HTTP throughput ~61% higher than Node.js. [Fresh docs](https://oneuptime.com/blog/post/2026-01-31-deno-fresh-framework/view)

**Marko (eBay)** -- Powers all of eBay.com (~20,000 UI components). Streams HTML as data becomes available. Compiler generates optimal code for both server and browser. eBay credits Marko with reaching their performance goals at massive scale. [eBay engineering](https://innovation.ebayinc.com/tech/engineering/the-future-of-marko/) | [InfoQ interview](https://www.infoq.com/articles/ebay-marko-performance-reactivity-model/)

---

## Performance Data

### Core Web Vitals by Framework (Benchmarked 2025)

Data from the [Enterspeed benchmark study](https://www.enterspeed.com/blog/we-measured-the-ssr-performance-of-6-js-frameworks-heres-what-we-found) and [Sparkbox rendering comparison](https://sparkbox.com/foundry/ui_rendering_frameworks_next.js_astro_qwik_rendering_strategies_tested_time_to_interactive_total_blocking_time_largest_contentful_paint_measured):

| Framework | Lighthouse Score | TTI | TBT | LCP | TTFB |
|-----------|-----------------|-----|-----|-----|------|
| **Astro (SSG)** | **99.2** | **0.3s** | **0s** | **0.4s** | <50ms |
| **Qwik (resumable)** | 100 | 0.5s | 0s | 0.5s | ~100ms |
| **Nuxt 3 (SSG)** | 98.8 | 0.6s | ~10ms | 0.6s | ~80ms |
| **Remix (SSR)** | 98.8 | 0.7s | ~20ms | 0.7s | 136ms |
| **SvelteKit (SSG)** | ~90 | 0.7s | ~30ms | 0.7s | ~90ms |
| **Next.js (SSG)** | ~95 | 1.6s | 180ms | 1.7s | ~60ms |
| **Next.js (SSR)** | ~88 | 2.0s | 200ms+ | 2.0s | 200-400ms |
| **React SPA (CSR)** | ~70 | 3.0s+ | 500ms+ | 2.5s+ | 50ms (empty) |

> 📊 **The static advantage is stark.** Astro's build-time rendering achieves 0.3s TTI and 0s TBT. The same component in Next.js SSR shows 180ms TBT and 1.7s LCP -- a **4x penalty** on LCP just from the rendering strategy. [Sparkbox benchmark](https://sparkbox.com/foundry/ui_rendering_frameworks_next.js_astro_qwik_rendering_strategies_tested_time_to_interactive_total_blocking_time_largest_contentful_paint_measured)

### Academic Benchmark (2025)

A peer-reviewed study from [Universitas Negeri Surabaya](https://ejournal.unesa.ac.id/index.php/JEISBI/article/download/64283/49659) tested Astro, Next.js, Nuxt, and SvelteKit across 21 scenarios:

- **Best FCP:** Nuxt won 11/21 scenarios, followed by Astro
- **Best TBT:** Astro won 11/21 scenarios, followed by Next.js
- **Key takeaway:** Build-time rendering (Astro) dominates Total Blocking Time; streaming SSR (Nuxt) dominates First Contentful Paint

### Chrome UX Report (CrUX) Real-World Data

As of 2025, from [DebugBear's annual review](https://www.debugbear.com/blog/2025-in-web-performance):

- **57.1%** of desktop sites pass Core Web Vitals assessment
- **49.7%** of mobile sites pass
- **LCP cannot be faster than TTFB** -- if your server responds in 800ms, your LCP floor is 800ms before any resource loading begins
- Static sites served from CDN edge achieve **near-zero TTFB**, giving LCP a massive head start

---

## Islands Architecture

### The Movement

**Islands architecture** is a pattern where a web page is mostly **static HTML** with isolated **"islands" of interactivity** that hydrate independently. Coined by [Jason Miller (Preact creator)](https://jasonformat.com/islands-architecture/) in 2019, it became the defining architecture of 2023-2025.

> 💡 **Core idea:** Render HTML pages on the server. Inject placeholders around dynamic regions. Hydrate those regions independently as small self-contained widgets, reusing their server-rendered HTML. The rest of the page is pure static HTML -- **zero JavaScript, instant render.**

### Who Implements It

| Framework | Islands Approach | Maturity |
|-----------|-----------------|----------|
| **Astro** | First-class. `client:load`, `client:visible`, `client:idle` directives | Production-ready, 40k+ GitHub stars |
| **Fresh (Deno)** | Native. Components in `islands/` directory auto-hydrate | Production-ready |
| **Marko (eBay)** | Native. Compiler determines island boundaries automatically | Battle-tested at eBay scale |
| **Astro Server Islands** | New (2024). Individual components SSR while page is static | Released, innovative |
| **Next.js PPR** | Emerging. Static shell + streaming dynamic Suspense boundaries | Stable in v15 |
| **11ty (Eleventy)** | Via `<is-land>` web component wrapper | Community plugin |
| **Web Components** | Natural fit. Each custom element is inherently an island | Framework-agnostic |

### Adoption Statistics

- **Astro:** 18% adoption among developers surveyed (2025), up from ~5% in 2022 ([State of JS](https://dev.to/fahim_shahrier_4a003786e0/the-rise-of-astrojs-in-2025-m4k))
- **Astro GitHub stars:** 500 (2020) -> 40,000+ (2024) -- **80x growth in 4 years** ([Dev.to analysis](https://dev.to/fahim_shahrier_4a003786e0/the-rise-of-astrojs-in-2025-m4k))
- **Developer satisfaction:** Astro experienced the **highest positive satisfaction change** from 2022-2023 of any SSG ([Strapi comparison](https://strapi.io/blog/astro-vs-gatsby-performance-comparison))
- **Lighthouse impact:** Islands sites routinely score 95-100 on Lighthouse, vs 70-85 for traditional SPAs

### Why It Matters for N3TX

N3TX's web components (`ntx-item`, `ntx-list`, `ntx-element`) are **already islands**. Each custom element is a self-contained unit that hydrates independently. An HTML compiler for N3TX would naturally produce a **static shell** (the page layout, navigation, static content) with **dynamic islands** (the N3TX components that need interactivity). This is architecturally aligned with the industry's direction.

---

## Qwik Resumability

### Killing Hydration

Traditional SSR frameworks have a dirty secret: **hydration**. The server renders HTML, sends it to the browser, then the browser downloads, parses, and re-executes JavaScript to make the page interactive. This process adds **200-500ms to first interaction** on average ([Web Almanac 2024](https://almanac.httparchive.org/)).

**Qwik eliminates hydration entirely** through **resumability**:

1. Server renders HTML and **serializes application state** into the HTML
2. Browser receives fully interactive HTML -- **no re-execution needed**
3. JavaScript loads **lazily, per-interaction** -- click a button, only that button's handler downloads
4. The application **resumes** exactly where the server left off

> ⚡ **The result:** Qwik applications are interactive in **<100ms** regardless of application complexity. A 10MB app and a 10KB app have the same startup time. [Qwik resumability docs](https://qwik.dev/docs/concepts/resumable/) | [Builder.io comparison](https://www.builder.io/blog/resumability-vs-hydration)

### Benchmarks vs Hydration-Based Frameworks

| Metric | Qwik (Resumable) | Next.js (Hydration) | React SPA | Improvement |
|--------|-------------------|---------------------|-----------|-------------|
| TTI | 0.5s | 1.6s | 3.0s+ | **3-6x faster** |
| TBT | 0s | 180ms | 500ms+ | **Eliminated** |
| JS on first load | ~1KB (loader only) | 200-500KB | 500KB-2MB | **99% less** |
| Scales with app size | No (O(1)) | Yes (O(n)) | Yes (O(n)) | **Constant time** |

> 📊 **2024 Web Almanac finding:** Hydration adds 200-500ms to first interaction on average across the web. Qwik's zero-hydration approach eliminates this entirely. For startup performance, Qwik remains unmatched in 2025. [Java Code Geeks analysis](https://www.javacodegeeks.com/2025/06/qwik-vs-react-vs-solidjs-the-future-of-web-performance.html)

### Real-World Performance Positioning

- **Qwik excels** in TTI for SSR + large application scenarios
- **SolidJS leads** in high-frequency update performance and memory efficiency
- **Astro leads** in purely static content with minimal interactivity
- **Qwik's sweet spot:** Content-heavy sites and e-commerce where fast initial load is critical and the app has significant JS complexity

### Relevance to N3TX

Qwik's insight is profound: **if the server already computed the state, don't recompute it on the client.** N3TX's schema already carries all the state the frontend needs. An HTML compiler could serialize N3TX's schema resolution and entity state directly into the HTML, achieving resumability-like behavior without Qwik's framework -- because the schema IS the state.

---

## Partial & Progressive Hydration

### Definitions

- **Progressive hydration:** Hydrate components **incrementally** (one by one, region by region) rather than the entire page at once
- **Partial hydration:** Hydrate **only interactive components**, leaving static regions as pure HTML forever

### Who Uses It

| Company/Framework | Approach | Measured Benefit |
|-------------------|----------|-----------------|
| **Astro** | Partial hydration (islands) | 0s TBT, 99.2 Lighthouse |
| **Shopify (Hydrogen)** | Progressive via React Suspense streaming | Routes saw load time **cut in half** |
| **Stripe** | Splitting hydration around checkout flows | Improved checkout interaction times |
| **Shopify** | Partial hydration on product pages | Reduced JS concurrency, faster checkout |
| **Gatsby** | Partial hydration (experimental) | ~33% less code during hydration |
| **Angular** | Progressive hydration (Angular 17+) | Reduced TTI for large apps |
| **React 19** | Partial hydration via Server Components | Reduced client-side JS |

> 📊 **Measured:** In real-world implementations with similar component weights, approximately **33% less code runs during hydration** at page load when using partial hydration. [Gatsby docs](https://www.gatsbyjs.com/docs/conceptual/partial-hydration/) | [Babbel engineering](https://www.babbel.com/en/magazine/exploring-web-rendering-progressive-hydration)

### Shopify Hydrogen: A Production Case Study

Shopify's Hydrogen framework, built on React Server Components, demonstrates production-grade progressive hydration:

- **Streaming SSR** outputs the page shell immediately while data fetches resolve
- **Fast TTFB** because the HTML shell streams without blocking on data
- React **progressively hydrates** each component as its data arrives
- **No extra client round trips** -- data streams within the HTML response
- Some routes in the Hydrogen demo store saw their **load time cut in half**

[Shopify engineering blog](https://shopify.engineering/high-performance-hydrogen-powered-storefronts) | [Hydrogen React Server Components](https://shopify.engineering/react-server-components-best-practices-hydrogen)

---

## Case Studies

### Netflix: SPA to Static, 50% Faster

**Before:** Netflix's logged-out homepage was a React SPA. Full client-side rendering with a large JS bundle.

**After:** Replaced React with server-rendered HTML + vanilla JavaScript.

**Results:**
- ⚡ **50% decrease** in loading time and time-to-interactive
- ⚡ **200KB reduction** in JavaScript bundle size
- ⚡ Prefetching during landing page idle time prepared React bundle for the signup flow

**Key insight from Addy Osmani (Chrome team):** "Simple static pages benefit from being server-rendered with minimal JavaScript, while libraries can provide great value for complex pages when used with care."

[Netflix Web Performance Case Study](https://medium.com/dev-channel/a-netflix-web-performance-case-study-c0bcde26a9d9)

---

### eBay: Streaming HTML at Scale

**Scale:** ~20,000 UI components, one of the highest-traffic e-commerce sites globally.

**Approach:** eBay built Marko, a compiler-based framework that streams HTML to users as data becomes available.

**Results:**
- Server-side streaming via Node.js async primitives
- HTML, assets, and images load as soon as possible
- Asynchronous content loads without blocking the page
- Compiler generates optimal code for both server and browser
- eBay credits Marko with **reaching their performance goals** at their massive scale

**Key insight:** eBay doesn't just use SSR -- they **stream** HTML. Content arrives progressively, and the page becomes interactive in pieces rather than all-at-once.

[eBay engineering](https://innovation.ebayinc.com/tech/engineering/the-future-of-marko/) | [InfoQ](https://www.infoq.com/articles/ebay-marko-performance-reactivity-model/)

---

### E-commerce: Speed = Money

Multiple e-commerce migration studies show direct performance-to-revenue correlation:

| Migration | Metric | Result |
|-----------|--------|--------|
| Page load 2.4s vs 5.7s | Conversion rate | **1.9% vs 0.6%** (3.2x higher) |
| SEO migration (SSR-optimized) | Organic traffic | **91.7K to 152.3K** monthly visits (+66%) |
| SEO migration (SSR-optimized) | Top-3 keywords | **898 to 1,523** keywords (+70%) |
| Mobile optimization | Bounce rate | **53% abandon** if load >3 seconds |

[Conductor case studies](https://www.conductor.com/academy/page-speed-resources/) | [Netrocket e-commerce case study](https://netrocket.pro/case-studies/e-commerce-website-migration-case-study/)

---

### Shopify Hydrogen: React Server Components in E-Commerce

Shopify's headless commerce framework demonstrates the hybrid approach:

- **Streaming SSR** with React Suspense for immediate shell delivery
- **Progressive hydration** reduces client JS and main thread pressure
- Improved **LCP** through streaming key content first
- Improved **INP** through RSC reducing client-side workload
- Specific routes saw **load time cut in half** through GraphQL query optimization

[Shopify engineering](https://shopify.engineering/high-performance-hydrogen-powered-storefronts)

---

## Google's Research: Speed and Business Metrics

Google's research, conducted with a neural network achieving **90% prediction accuracy**, quantifies the business impact of page speed:

### Bounce Rate Impact

| Load Time | Bounce Probability Increase |
|-----------|---------------------------|
| 1s -> 3s | **+32%** |
| 1s -> 5s | **+90%** |
| 1s -> 6s | **+106%** |
| 1s -> 10s | **+123%** |

[Google/SOASTA research](https://business.google.com/ca-en/think/marketing-strategies/mobile-page-speed-new-industry-benchmarks/)

### Conversion Rate Impact

| Improvement | Conversion Lift |
|-------------|----------------|
| 0.1s faster load | **+10.1%** (travel) |
| 0.1s faster load | **+8.4%** (e-commerce) |
| 0.1s faster load | **+3.6%** (luxury) |
| Each additional second (0-5s) | **-4.42%** conversion |

[Deloitte/Google research](https://nitropack.io/blog/how-page-speed-affects-conversion/) | [Abralytics](https://abralytics.com/how-website-performance-affects-conversions/)

### Page Complexity Impact

> ⚠️ As page elements (text, images, titles) increase from **400 to 6,000**, conversion probability drops **95%**. This directly argues for static HTML with minimal JS -- fewer elements to parse, faster to interactive.

### Mobile Reality Check

- **70%** of mobile landing pages take **>5 seconds** to display above-the-fold content
- **53%** of mobile visits are abandoned if load exceeds **3 seconds**
- The median mobile page takes **>7 seconds** to fully load

> 💡 **For N3TX:** If a schema-compiled HTML page achieves <1s LCP (which static HTML routinely does), that's a **3-10x improvement** over typical dynamic pages. At Google's measured conversion rates, this translates to **8-10% more conversions per page** in e-commerce scenarios.

---

## Edge Rendering

### The CDN Becomes the Server

Edge rendering moves server-side logic from centralized data centers to **CDN edge nodes** (200+ global locations), dramatically reducing latency.

### Platform Comparison (2025)

| Platform | Cold Start | Architecture | SSR Support | Key Metric |
|----------|-----------|--------------|-------------|------------|
| **Cloudflare Workers** | **1-5ms** | V8 Isolates | Full | Fastest cold starts |
| **Vercel Edge** | ~25ms | V8 + Fluid Compute | Full (Next.js) | 2.55x faster than Workers (SSR) |
| **Deno Deploy** | 40-80ms | Deno runtime | Full (Fresh) | Web standards native |
| **Netlify Edge** | ~50ms | Deno-based | Full | Integrated with Netlify CDN |

### Key Benchmarks

- **Vercel Fluid Compute** averaged **2.55x faster** than Cloudflare Workers for server rendering workloads ([Vercel blog](https://vercel.com/blog/fluid-compute-benchmark-results))
- After improvements, **Cloudflare now performs on par** with Vercel except for Next.js-specific workloads ([Cloudflare blog](https://blog.cloudflare.com/unpacking-cloudflare-workers-cpu-performance-benchmarks/))
- Cloudflare achieved **5x speed improvement** re-architecting services with Workers + Durable Objects
- Vercel **Edge Functions are 9x faster** during cold starts vs traditional Serverless Functions ([Vercel blog](https://vercel.com/blog/fluid-compute-benchmark-results))

### Static + Edge = Best of Both Worlds

The optimal architecture for 2025-2026:
1. **Build time:** Compile static HTML (SSG/ISR)
2. **Deploy:** Push to CDN edge (200+ locations)
3. **Request:** Serve static HTML from nearest edge node (~50ms TTFB globally)
4. **Dynamic parts:** Edge functions handle personalization, auth, real-time data

> 💡 **For N3TX:** Schema-compiled HTML deployed to a CDN achieves near-zero TTFB. Dynamic N3TX components can hydrate on the client. This is the exact architecture the industry is converging on, but N3TX would generate it from models instead of handwritten templates.

---

## Prerendering at Scale

### When You Can't Rewrite: Prerendering Services

For SPAs that can't migrate to SSG/SSR, prerendering services use headless browsers to generate HTML snapshots. This is a **band-aid, not a cure** -- but widely used.

### Tools Comparison

| Tool | Type | Scale | Cost | Maintenance |
|------|------|-------|------|-------------|
| **Prerender.io** | Managed SaaS | 1.5M+ pages (enterprise) | $9-599+/mo | Zero |
| **Rendertron** | Self-hosted (Google) | Depends on infra | Free (+ hosting) | High |
| **Puppeteer** | Self-hosted library | ~500K pages/day (Kubernetes) | Infrastructure | Very high |
| **LovableHTML** | Managed alternative | Enterprise-scale | Varies | Low |

### Production Realities

- **Prerender.io** is recommended by **Microsoft Bing** for JavaScript-heavy sites. Handles 1.5M+ pages across enterprise deployments. [Prerender.io](https://prerender.io/blog/puppeteer-vs-prerender-for-javascript-rendering/)
- **Rendertron** (Google Chrome team) is open source but requires managing your own infrastructure, scaling, and maintenance. [Rendertron GitHub](https://github.com/GoogleChrome/rendertron)
- **Puppeteer** at scale: one team processed **~500,000 pages/day** using Kubernetes autoscaling. Each headless Chrome instance consumes **300MB-1GB RAM** and **70-90% of a CPU core**. [Prerender.io comparison](https://prerender.io/blog/puppeteer-vs-prerender-for-javascript-rendering/)

> ⚠️ **The problem with prerendering:** It's computationally expensive (running full browsers), adds caching complexity, and produces stale snapshots. **Build-time compilation from a schema is orders of magnitude more efficient** -- you generate HTML from structured data, not by rendering a browser.

---

## Schema-Driven Static Generation

### The Whitespace Opportunity

After extensive research, **no existing framework compiles directly from a data schema to static HTML** in the way N3TX could. The closest approaches:

| Approach | What It Does | How It Differs from Schema-to-HTML |
|----------|-------------|-------------------------------------|
| **Gatsby + GraphQL** | Queries data at build time, feeds to React templates | Still requires handwritten React components |
| **Blurry SSG** | Maps Markdown frontmatter to Schema.org types | Content-focused, not application-focused |
| **Hugo** | Compiles Markdown + templates to HTML | Template-driven, not schema-driven |
| **Strapi + Astro** | Headless CMS feeds data to Astro components | Two systems; still requires component code |
| **JSON Schema Form generators** | Generates forms from JSON Schema at runtime | Runtime, not compile-time; forms only |

### What N3TX Could Do Differently

The unique insight: **if the schema carries rendering hints (`ui.widget`, `ui.field_order`, `ui.groups`, `ui.renderer`), the compiler has everything it needs to produce HTML without templates.**

```
Traditional SSG pipeline:
  Data Source -> Template Engine -> HTML

N3TX compiler pipeline:
  Model Definition -> JSON Schema (with UI hints) -> HTML Compiler -> Static HTML + Islands
```

**No template layer needed.** The schema IS the template specification. This eliminates an entire category of code that every other framework requires.

### Analogies in Other Domains

- **Protocol Buffers / gRPC:** Schema defines wire format, code is generated
- **GraphQL Code Generators:** Schema produces typed client/server code
- **OpenAPI / Swagger Codegen:** API schema generates client SDKs and server stubs
- **Prisma:** Schema generates database client, migrations, and types

These all prove the pattern: **when you have a rich enough schema, you can generate the implementation.** N3TX's JSON Schema (with `ui`, `access`, `methods` extensions) is rich enough to generate HTML.

---

## Jamstack Evolution

### Market Growth

| Year | Jamstack Market Value | Key Milestone |
|------|----------------------|---------------|
| 2020 | $1.8B | Gatsby peak, Netlify growth |
| 2022 | ~$4B | Next.js ISR, Astro launch |
| 2023 | ~$6B | Netlify redefines Jamstack as "composable" |
| 2025 | **$8.6B** | Edge computing, AI integration, hybrid rendering |
| 2026 (proj.) | ~$12B | 75% enterprise data at edge (Gartner) |

[KeenComputer white paper](https://www.keencomputer.com/solutions/software-engineering/880-research-white-paper-the-future-of-web-architecture-jamstack-and-static-site-generators-as-the-foundation-of-agile-digital-transformation-2025-2026) | [eSparkInfo analysis](https://www.esparkinfo.com/blog/pros-and-cons-of-jamstack)

### The "Post-Jamstack" Shift

The term "Jamstack" has evolved from a specific architecture (JavaScript + APIs + Markup) to a **philosophy:**

> **"Flexibility, scalability, performance, and maintainability"** -- Netlify's 2023 redefinition

Key trends in the post-Jamstack era:

1. **Hybrid rendering is default.** No framework ships SSG-only anymore. Every major SSG added SSR, streaming, or ISR.

2. **Edge-first.** Gartner predicts **75% of enterprise-generated data** will be processed at the edge by 2026. Jamstack tools are moving compute to the CDN.

3. **Headless CMS explosion.** The headless CMS market is growing **>25% annually**. Content decoupled from presentation. [Jamstack trends](https://www.jamstackexperts.com/blog/jamstack-trends-how-will-we-develop-in-2024/)

4. **AI integration.** Netlify, Vercel, and Cloudflare all offer AI-powered edge functions. Content personalization at the edge without origin roundtrips.

5. **Composable architecture.** The monolithic framework is dead. Teams assemble best-of-breed tools (headless CMS + SSG + edge functions + CDN). [Storieasy analysis](https://www.storieasy.com/blog/jamstack-in-2025-still-relevant-or-evolving)

### Developer Adoption

- **Netlify** hosts **5.5M+ sites**
- **35% of developers** identify their primary stack as Jamstack-inspired
- Next.js leads with **40% framework adoption**, followed by Astro (18%), Nuxt (12%)

---

## The Static Shell + Dynamic Islands Pattern

### The Industry's Convergence Point

The 2025-2026 consensus architecture for web applications (not just blogs) is:

```
┌──────────────────────────────────────────┐
│           STATIC SHELL (CDN)             │
│  Navigation, layout, static content      │
│  Served instantly from edge (~50ms)       │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Island 1 │  │ Island 2 │  │Island 3│ │
│  │ (search) │  │ (cart)   │  │(auth)  │ │
│  │ hydrates │  │ hydrates │  │hydrates│ │
│  │ on focus │  │ on load  │  │on load │ │
│  └──────────┘  └──────────┘  └────────┘ │
│                                          │
│  ┌──────────────────────────────────────┐│
│  │        Island 4 (product list)       ││
│  │      hydrates on scroll/visible      ││
│  └──────────────────────────────────────┘│
└──────────────────────────────────────────┘
```

### Framework Implementations

- **Astro:** `client:load`, `client:visible`, `client:idle` directives control when each island hydrates
- **Astro Server Islands (2024):** Individual components render on the server while the page is static
- **Next.js PPR:** Static shell from edge cache + streaming dynamic Suspense boundaries
- **Fresh:** `islands/` directory convention auto-identifies interactive components
- **Marko:** Compiler automatically determines island boundaries

### Why This Pattern Wins

| Aspect | Pure SPA | Pure SSR | Static Shell + Islands |
|--------|----------|----------|----------------------|
| TTFB | 50ms (empty) | 200-500ms | **<50ms (real content)** |
| LCP | 1.5-4s | 0.8-2s | **0.3-0.8s** |
| TTI | 2-5s | 1.5-3s | **0.3-1s** |
| JS shipped | 500KB-2MB | 200-500KB | **<50KB** (islands only) |
| SEO | Poor | Good | **Excellent** |
| CDN-cacheable | Shell only | No | **Entire page** |
| Personalization | Client-side | Server-side | **Island-level** |

> 💡 **For N3TX:** This is the exact pattern N3TX should target. The HTML compiler generates the **static shell** (layout, navigation, entity display in read-only mode). N3TX web components become the **islands** (forms, methods, interactive elements). The schema tells the compiler which parts are static (display) and which are dynamic (interactive).

---

## Build-Time vs Runtime: Hard Numbers

### Direct Comparison (Same Component, Different Strategy)

From the [Sparkbox rendering comparison](https://sparkbox.com/foundry/ui_rendering_frameworks_next.js_astro_qwik_rendering_strategies_tested_time_to_interactive_total_blocking_time_largest_contentful_paint_measured):

| Metric | Build-Time (Astro SSG) | Runtime (Next.js SSR) | Difference |
|--------|----------------------|---------------------|------------|
| Performance Score | 100 | ~88 | **+12 points** |
| TTI | 0.3s | 2.0s | **6.7x faster** |
| TBT | 0s | 180ms | **Eliminated** |
| LCP | 0.4s | 1.7s | **4.3x faster** |
| JS Loaded | ~0KB | ~200KB | **~200KB less** |

### When Each Strategy Wins

| Scenario | Best Strategy | Why |
|----------|--------------|-----|
| Marketing pages | **SSG** | Content rarely changes, maximum speed |
| Blog / docs | **SSG** | Build once, serve forever |
| E-commerce catalog | **ISR** | Products change, but can be stale for 60s |
| E-commerce checkout | **Streaming SSR** | Needs real-time cart, auth, pricing |
| Social feed | **Streaming SSR** | Always-fresh, personalized content |
| Dashboard | **SSR or SPA** | Highly interactive, real-time data |
| Landing pages | **SSG** | Every ms of load time = conversions |
| Admin panel | **SPA** | Heavy interactivity, auth-gated anyway |

### The Build-Time Advantage for Schema-Driven Apps

Schema-driven applications have a **unique advantage** for build-time rendering:

1. **The schema is known at build time.** Field types, UI widgets, validation rules, access permissions -- all defined in the model.
2. **Entity data can be pre-fetched.** For catalog-style apps (products, articles, profiles), data exists before the user requests it.
3. **Forms can be pre-compiled.** Instead of `form.js` building forms at runtime from schema properties, the compiler generates the HTML `<form>` with all inputs, labels, groups, and fieldsets at build time.
4. **Permissions can be pre-evaluated.** For public-facing pages, access rules are known. The compiler can generate different HTML variants per role.

> 📊 **Estimated impact for N3TX:** If the current frontend (SPA-style, schema-fetched-at-runtime) achieves ~70 Lighthouse score (typical for SPAs), a compiled HTML version should achieve **95-100** -- based on Astro's demonstrated scores for similar static-with-islands architectures.

---

## Strategic Implications for N3TX

### The Opportunity

N3TX sits at a unique intersection:

```
        Schema-Driven ──────────── N3TX is HERE
              │                         │
              │    No one else is here   │
              │                         │
              ▼                         ▼
     Static Generation          Runtime Generation
     (Astro, Next SSG,          (Current N3TX,
      Eleventy, Hugo)            React SPAs)
              │                         │
              │                         │
              ▼                         ▼
     Templates Required          Templates Required
     (developers write           (developers write
      components/pages)           components/pages)
```

**N3TX's proposed HTML compiler would be the first framework to generate static HTML directly from data model definitions** -- no templates, no component code, no page files. The schema carries the intent; the compiler produces the artifact.

### Recommended Architecture

Based on industry evidence:

| Layer | Strategy | Rationale |
|-------|----------|-----------|
| **Entity list pages** | SSG at build time | Schema + data known ahead of time |
| **Entity detail pages** | ISR (revalidate on write) | Data changes, but stale-while-revalidate is fine |
| **Forms (create/edit)** | Static HTML + island hydration | Form structure from schema; validation JS loads on interaction |
| **Methods (buttons)** | Island hydration on visible | Static button HTML; JS loads when scrolled into view |
| **Auth-dependent UI** | Server Islands or client islands | Different HTML per auth state |
| **Real-time features** | Client-side islands | WebSocket/polling in isolated components |

### Expected Performance Gains

| Metric | Current (SPA) | After Compiler (Projected) | Improvement |
|--------|---------------|---------------------------|-------------|
| Lighthouse Score | ~70 | 95-100 | +25-30 points |
| TTFB | 50ms (empty shell) | <50ms (real content) | Content arrives immediately |
| LCP | 2-4s | 0.3-0.8s | **3-10x faster** |
| TTI | 3-5s | 0.5-1.5s | **3-5x faster** |
| TBT | 300-500ms | <50ms | **10x reduction** |
| JS shipped | 200KB+ | <50KB (islands only) | **75-90% reduction** |
| SEO | Poor (SPA) | Excellent (static HTML) | Searchable content |

### Competitive Positioning

| Claim | Evidence |
|-------|----------|
| "Zero-template static generation" | No existing framework does this |
| "Schema-to-HTML compilation" | Analogous to protobuf/OpenAPI codegen, proven pattern |
| "Islands architecture by default" | Web components are natural islands; aligns with Astro/Fresh/Marko |
| "Sub-second LCP for data apps" | Astro proves 0.3-0.4s LCP is achievable for static+islands |
| "10x less JavaScript than SPAs" | Industry benchmarks confirm: static ships <50KB vs SPA 500KB+ |

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Dynamic data staleness | Medium | ISR pattern: revalidate on write, serve cached HTML |
| Personalized content | Medium | Server Islands or client-side islands for auth-dependent UI |
| Build time at scale | Low | Incremental builds; only regenerate changed entities |
| Developer experience | Low | Schema-driven means less code, not more; DX should improve |
| Interactivity gaps | Medium | Islands pattern preserves all current N3TX interactivity |

---

## Sources

### Benchmarks & Performance Data
- [Enterspeed: SSR Performance of 6 JS Frameworks](https://www.enterspeed.com/blog/we-measured-the-ssr-performance-of-6-js-frameworks-heres-what-we-found)
- [Sparkbox: UI Rendering Frameworks Comparison](https://sparkbox.com/foundry/ui_rendering_frameworks_next.js_astro_qwik_rendering_strategies_tested_time_to_interactive_total_blocking_time_largest_contentful_paint_measured)
- [Builder.io: Framework Benchmarks (GitHub)](https://github.com/BuilderIO/framework-benchmarks)
- [Universitas Negeri Surabaya: Rendering Performance Analysis](https://ejournal.unesa.ac.id/index.php/JEISBI/article/download/64283/49659)
- [DebugBear: 2025 In Review - Web Performance](https://www.debugbear.com/blog/2025-in-web-performance)

### Business Impact Research
- [Google/SOASTA: Mobile Page Speed Industry Benchmarks](https://business.google.com/ca-en/think/marketing-strategies/mobile-page-speed-new-industry-benchmarks/)
- [NitroPack: How Page Speed Affects Conversion](https://nitropack.io/blog/how-page-speed-affects-conversion/)
- [Conductor: Page Speed Case Studies](https://www.conductor.com/academy/page-speed-resources/)
- [Abralytics: How Website Performance Affects Conversions](https://abralytics.com/how-website-performance-affects-conversions/)
- [ShopLift: Page Speed for E-Commerce](https://www.shoplift.ai/post/why-page-speed-is-the-make-or-break-factor-for-e-commerce-success-and-how-a-b-testing-tools-are-either-helping-or-hurting)

### Case Studies
- [Addy Osmani: Netflix Web Performance Case Study](https://medium.com/dev-channel/a-netflix-web-performance-case-study-c0bcde26a9d9)
- [eBay: The Future of Marko](https://innovation.ebayinc.com/tech/engineering/the-future-of-marko/)
- [InfoQ: eBay Marko Performance & Reactivity](https://www.infoq.com/articles/ebay-marko-performance-reactivity-model/)
- [Shopify: High Performance Hydrogen Storefronts](https://shopify.engineering/high-performance-hydrogen-powered-storefronts)
- [Shopify: RSC Best Practices in Hydrogen](https://shopify.engineering/react-server-components-best-practices-hydrogen)
- [Netrocket: E-Commerce Migration Case Study](https://netrocket.pro/case-studies/e-commerce-website-migration-case-study/)

### Framework Documentation & Analysis
- [Next.js: Static Site Generation](https://nextjs.org/docs/pages/building-your-application/rendering/static-site-generation)
- [Astro: Islands Architecture](https://docs.astro.build/en/concepts/islands/)
- [Astro: Server Islands](https://docs.astro.build/en/guides/server-islands/)
- [Qwik: Resumability Concepts](https://qwik.dev/docs/concepts/resumable/)
- [Builder.io: Resumability vs Hydration](https://www.builder.io/blog/resumability-vs-hydration)
- [Remix: React Server Components](https://remix.run/blog/react-server-components)
- [Fresh Framework Guide (Deno)](https://oneuptime.com/blog/post/2026-01-31-deno-fresh-framework/view)
- [Jason Miller: Islands Architecture](https://jasonformat.com/islands-architecture/)
- [Patterns.dev: Islands Architecture](https://www.patterns.dev/vanilla/islands-architecture/)

### Edge Computing
- [Vercel: Fluid Compute Benchmark Results](https://vercel.com/blog/fluid-compute-benchmark-results)
- [Cloudflare: Workers CPU Performance Benchmarks](https://blog.cloudflare.com/unpacking-cloudflare-workers-cpu-performance-benchmarks/)
- [Dev.to: Cloudflare vs Vercel vs Netlify Edge Performance 2026](https://dev.to/dataformathub/cloudflare-vs-vercel-vs-netlify-the-truth-about-edge-performance-2026-50h0)
- [Railway: Server Rendering Benchmarks](https://blog.railway.com/p/server-rendering-benchmarks-railway-vs-cloudflare-vs-vercel)

### Hydration & Rendering Strategies
- [The New Stack: Progressive Hydration](https://thenewstack.io/mastering-progressive-hydration-for-enhanced-web-performance/)
- [Dev Tech Insights: Progressive Hydration 2025](https://devtechinsights.com/progressive-hydration-web-performance-2025/)
- [Gatsby: Partial Hydration](https://www.gatsbyjs.com/docs/conceptual/partial-hydration/)
- [Babbel: Exploring Web Rendering Progressive Hydration](https://www.babbel.com/en/magazine/exploring-web-rendering-progressive-hydration)
- [SitePoint: RSC Streaming Performance Guide 2026](https://www.sitepoint.com/react-server-components-streaming-performance-2026/)
- [Sparkbox: The React Rendering Landscape in 2025](https://sparkbox.com/foundry/the_react_rendering_landcape_in_2025)

### Jamstack & Market Trends
- [KeenComputer: Jamstack & SSGs as Foundation for Digital Transformation 2025-2026](https://www.keencomputer.com/solutions/software-engineering/880-research-white-paper-the-future-of-web-architecture-jamstack-and-static-site-generators-as-the-foundation-of-agile-digital-transformation-2025-2026)
- [Medium: Jamstack in 2025 - Is It Still Relevant?](https://medium.com/@harzeno/jamstack-in-2025-is-it-still-relevant-9bce6d29c287)
- [Storieasy: Jamstack in 2025 - Still Relevant or Evolving?](https://www.storieasy.com/blog/jamstack-in-2025-still-relevant-or-evolving)
- [eSparkInfo: Pros and Cons of Jamstack 2026](https://www.esparkinfo.com/blog/pros-and-cons-of-jamstack)
- [Hygraph: Top 12 SSGs in 2026](https://hygraph.com/blog/top-12-ssgs)

### Prerendering
- [Prerender.io: Puppeteer vs Prerender](https://prerender.io/blog/puppeteer-vs-prerender-for-javascript-rendering/)
- [Prerender.io: Alternatives to Rendertron](https://prerender.io/blog/alternatives-to-rendertron-for-dynamic-rendering/)
- [Rendertron (GitHub)](https://github.com/GoogleChrome/rendertron)
- [Mercari Engineering: Dynamic Rendering Service](https://engineering.mercari.com/en/blog/entry/20220119-implement-the-dynamic-rendering-service/)

### Framework Comparisons
- [CloudCannon: Top 5 Static Site Generators 2025](https://cloudcannon.com/blog/the-top-five-static-site-generators-for-2025-and-when-to-use-them/)
- [Senorit: Astro vs Next.js 2026 Benchmarks](https://senorit.de/en/blog/astro-vs-nextjs-2025)
- [Dev.to: Rise of Astro in 2025](https://dev.to/fahim_shahrier_4a003786e0/the-rise-of-astrojs-in-2025-m4k)
- [Strapi: Astro vs Gatsby Performance](https://strapi.io/blog/astro-vs-gatsby-performance-comparison)
- [Java Code Geeks: Qwik vs React vs SolidJS 2025](https://www.javacodegeeks.com/2025/06/qwik-vs-react-vs-solidjs-the-future-of-web-performance.html)
- [web.dev: Optimize LCP](https://web.dev/articles/optimize-lcp)

---

*Research compiled February 2026. Data points sourced from published benchmarks, engineering blogs, academic papers, and industry reports. All performance numbers are approximate and vary by implementation, hardware, and network conditions.*
