# Industry Landscape: Fully Static Website Generation

**Research Date:** February 2026
**Scope:** Static site generators, the no-JS movement, hosting economics, measured outcomes, limitations, and the islands-of-interactivity pattern
**Audience:** Technical CEO + Engineering Team

---

## Executive Summary

The static site generation market is experiencing a structural shift. What began as a niche tool for developer blogs has become a viable architecture for documentation portals, marketing sites, e-commerce storefronts, and government services. The core proposition is simple: **pre-build HTML at deploy time, serve it from a CDN, eliminate the server at runtime.** The result is sub-second page loads, near-zero hosting costs, a drastically reduced attack surface, and SEO advantages that dynamic sites struggle to match.

This document maps the landscape as it exists in early 2026 -- the major tools, who is using them, what the numbers say, and where the boundaries are. The goal is to inform a build-vs-buy decision for N3TX's static export capability: generating fully static HTML + CSS sites from schema-driven Python models, deployable anywhere without a running server.

---

## 1. The Static Site Generator Ecosystem

### 1.1 Major Players

The SSG market is fragmented across languages and philosophies. The table below captures the current state of the most significant generators.

| Generator | Language | GitHub Stars | Build Speed (1K pages) | Key Differentiator |
|-----------|----------|-------------|----------------------|-------------------|
| **Hugo** | Go | ~78K | **<1 second** | Raw speed; compiled binary; no runtime deps |
| **Next.js** | JS/React | ~128K | 10-30s | Hybrid SSG/SSR; Vercel ecosystem; massive community |
| **Astro** | JS | ~48K+ | 3-8s | Islands architecture; zero JS by default; multi-framework |
| **Gatsby** | JS/React | ~56K | 30-120s | GraphQL data layer; plugin ecosystem (declining) |
| **Eleventy (11ty)** | JS | ~17K | 2-5s | Zero-config simplicity; template-language agnostic |
| **Jekyll** | Ruby | ~49K | 30-60s | GitHub Pages native; mature; large theme ecosystem |
| **Pelican** | Python | ~13K | 5-15s | Python-native; Jinja2 templates; blog-focused |
| **MkDocs** | Python | ~20K | 2-5s | Documentation-specific; Material theme dominance |
| **Sphinx** | Python | ~6K | 5-20s | Technical docs; multi-format output (HTML, PDF, ePub) |
| **Zola** | Rust | ~14K | <1 second | Single binary; Rust speed; no dependencies |

> **Key insight:** The market has bifurcated. On one side are **content-first generators** (Hugo, Eleventy, Jekyll, Pelican) that produce pure HTML with minimal or zero JavaScript. On the other are **framework-first generators** (Next.js, Gatsby, Astro) that can produce static output but carry JavaScript runtimes of varying size. N3TX's static export aligns with the content-first camp -- pure HTML + CSS, no JS runtime required.

### 1.2 Market Share Data (2024-2025)

The HTTP Archive Web Almanac (2024 edition) provides the most rigorous measurement of SSG adoption in the wild:

| Architecture | Share of All Websites | Share of Top 1K Sites |
|-------------|----------------------|----------------------|
| **Prerendered (fully static)** | 0.5% | 0.8% |
| **Hybrid (SSG + SSR)** | 5.0% | 11.7% |
| **Dynamic** | 94.5% | 87.5% |

Within the prerendered category, framework market share breaks down as follows:

| SSG Framework | Prerendered Market Share (2024) |
|--------------|-------------------------------|
| Hugo | **18%** |
| Next.js | **13%** |
| Astro | **5%** (3x growth from 2023) |
| Others | 64% (fragmented long tail) |

**Growth trend:** Combined prerendered + hybrid sites in the top 10K grew **67% in 2024**. Astro tripled its share in a single year. Meanwhile, Gatsby's usage has been declining since 2022, with community attention shifting to Astro and Eleventy.

The broader Wappalyzer dataset shows SSGs present on **3.5% of all websites** in 2023 (up from 2.5% in 2022), though this includes detection of any SSG tooling, not just fully static output.

### 1.3 Growth Trajectories

| Signal | Data Point | Source |
|--------|-----------|--------|
| New projects using Jamstack/static-first | **60%** (up from 27% in 2020) | Netlify 2024 Dev Survey |
| Developers reporting 2x+ performance from Jamstack | **44%** | Netlify 2024 Community Survey |
| Teams that moved to Jamstack for faster deployment | **1 in 3** | Netlify 2024 Community Survey |
| Headless CMS market size projection (2026) | **$2.5 billion** | Gartner |
| Enterprise headless CMS adoption | **73%** (up 14% since 2021) | Industry survey |

> **Callout: The Gatsby Decline**
> Gatsby was the darling of static site generation from 2018-2021, peaking at ~55K GitHub stars and becoming synonymous with "Jamstack." Its acquisition by Netlify in 2023 was followed by a significant reduction in maintainer activity. New projects increasingly choose Astro (for content sites) or Next.js (for hybrid apps). Gatsby's GraphQL-heavy architecture and long build times (30-120s for 1K pages vs. Hugo's sub-second) made it vulnerable once faster alternatives matured. This is a cautionary tale: **developer experience and build performance matter more than ecosystem size.**

---

## 2. The "No-JS" / "JS-Free" Movement

### 2.1 The Weight Problem

The HTTP Archive Web Almanac (2025) documents the scale of JavaScript bloat on the modern web:

| Metric | 2024 Value | 2025 Value | Trend |
|--------|-----------|-----------|-------|
| Median JS per mobile page | 558 KB | **697 KB** | +25% YoY |
| Median total mobile page weight | 2.4 MB | **2.6 MB** | +8.4% YoY |
| Median desktop page weight | 2.7 MB | **2.9 MB** | +7.3% YoY |
| Sites passing all Core Web Vitals | -- | **47%** | 53% failing |

The median mobile page now ships **697 KB of JavaScript** -- and that is the median, not the worst case. Framework-driven static sites contribute to this: Next.js prerendered pages carry a median **583 KB of JS** even in static mode. Hugo pages carry **210 KB**. Astro pages carry **164 KB**.

A fully static HTML + CSS site with zero JavaScript can achieve page weights under **50 KB**, often under 20 KB for content pages. That is a 10-35x reduction over framework-generated "static" output.

### 2.2 Who Is Shipping Zero-JS Sites?

The no-JS movement is not theoretical. Real organizations are making this choice deliberately:

**Government Services**

The UK Government Digital Service (GOV.UK) is the highest-profile advocate of progressive enhancement and HTML-first design. Their stated policy: *"Progressive enhancement means building the interface of a website or application in layers. If the user's browser only supports HTML they get content and forms."* GOV.UK components are built to function fully without CSS or JavaScript. The HTML layer is treated as the only required layer; CSS and JS are additive enhancements.

This is mandated by policy: the UK public sector must meet WCAG 2.1 AA, and progressive enhancement is the primary implementation strategy. The US EPA similarly requires that *"all functionality should be available without JavaScript when possible."*

**Documentation Sites**

The Python ecosystem's documentation infrastructure runs almost entirely on static generators:
- **Django REST Framework** uses MkDocs
- **Full Stack Python** uses Pelican
- **Read the Docs** serves Sphinx-generated HTML
- **Python.org** itself uses a static build pipeline

These sites serve millions of developers with near-zero JavaScript.

**Marketing and Content Sites**

Smashing Magazine's migration from WordPress to Hugo + Netlify is the canonical case study:
- Load times dropped from **800ms to 80ms** (10x improvement)
- Build time for 7,500 pages: **13 seconds** with Hugo
- Previously 23-63x slower on Jekyll

**The Mastro Framework (2025)**

A new entrant, Mastro, explicitly champions "zero-JS by default" with browser-native routing instead of client-side SPAs. This signals that the pendulum is swinging: after a decade of ever-heavier JavaScript frameworks, there is now a counter-movement building tools that produce no JavaScript at all.

### 2.3 Why Organizations Choose Zero JS

| Motivation | Detail |
|-----------|--------|
| **Accessibility compliance** | WCAG 2.1 AA is easier to achieve when content works without JS; screen readers handle semantic HTML reliably |
| **Performance on low-end devices** | JS parsing is the bottleneck on budget Android phones; HTML renders instantly |
| **Hostile network conditions** | Government, healthcare, and education users often have unreliable connections; HTML is resilient to partial loads |
| **Reduced maintenance** | No JS framework means no framework upgrades, no security patches for client-side dependencies |
| **Archival and longevity** | Static HTML from 1996 still renders perfectly; React apps from 2018 may not build anymore |

---

## 3. Measured Outcomes: Static vs. Dynamic

### 3.1 Page Weight and Transfer Size

The HTTP Archive (2024) provides direct comparison data across architectures:

| Metric | Prerendered (Static) | Hybrid (SSG+SSR) | Dynamic | Static Advantage |
|--------|---------------------|------------------|---------|-----------------|
| **Median Page Transfer Size** | 1,427 KB | 2,083 KB | 2,434 KB | **41% smaller** than dynamic |
| **Median Total Requests** | 42 | 65 | 72 | **42% fewer** requests |
| **Median CSS Size** | 26 KB | 41 KB | 77 KB | **66% smaller** CSS |
| **Median JS Size** | 330 KB | 674 KB | 574 KB | **42% less** JS than dynamic |
| **Good Core Web Vitals** | **41%** | 31% | 33% | +8pp over dynamic |

Within the prerendered category, framework choice matters enormously:

| Framework | Median Transfer Size | Median JS Size |
|-----------|---------------------|---------------|
| **Astro** | **889 KB** | **164 KB** |
| **Hugo** | 1,174 KB | 210 KB |
| **Next.js** | 1,659 KB | 583 KB |

> **Key takeaway:** "Static" does not automatically mean "lightweight." Next.js static export ships **3.5x more JavaScript** than Astro. A truly zero-JS static export (pure HTML + CSS) would ship **0 KB of JS**, placing it in a category that the HTTP Archive does not even measure separately because so few sites achieve it. This is the category N3TX's static export would target.

### 3.2 Core Web Vitals Performance

Google's Core Web Vitals (2025-2026 thresholds):

| Metric | Good Threshold | What It Measures |
|--------|---------------|-----------------|
| **LCP** (Largest Contentful Paint) | < 2.5 seconds | Loading speed |
| **INP** (Interaction to Next Paint) | < 200 ms | Interactivity responsiveness |
| **CLS** (Cumulative Layout Shift) | < 0.1 | Visual stability |

Static sites have structural advantages on all three:

- **LCP:** Pre-built HTML served from CDN edge has near-zero TTFB. No server rendering, no database queries, no cold starts. CDN deployment reduces TTFB by **60-80%** compared to origin servers.
- **INP:** With zero JavaScript, there is nothing to block the main thread. INP is effectively zero. (43% of all websites fail the 200ms INP threshold in 2026 -- this is exclusively a JavaScript problem.)
- **CLS:** Static HTML with inline or preloaded CSS has no layout shifts from async component loading. CLS is near-zero by construction.

**Only 47% of websites pass all three Core Web Vitals thresholds.** A well-built static site passes all three trivially.

### 3.3 SEO Impact

Page speed is now a confirmed Google ranking factor, and the data is unambiguous:

| Finding | Data |
|---------|------|
| Page experience signals in Google ranking weight | **28%** of ranking factors |
| User abandonment if page takes >3 seconds | **53%** of users |
| Conversion drop per 1-second delay | **7%** per second |
| Mobile-first indexing coverage | **94%** of all Google searches |

Static sites have inherent SEO advantages:
- **Crawlability:** Search engines receive complete HTML on first request; no JS rendering required for indexing
- **Speed signals:** Sub-second LCP meets Google's "good" threshold easily
- **Structured content:** Pre-built HTML can include complete semantic markup, Open Graph tags, and structured data without client-side rendering

> **Callout: The $0 SEO Investment**
> For content-heavy sites (documentation, product catalogs, marketing pages), switching to static generation can improve search rankings without any additional SEO spend. The speed improvement alone -- from 2-4 second dynamic renders to sub-second static serves -- moves the site past Google's Core Web Vitals thresholds, which act as a tie-breaker between pages with similar content quality.

---

## 4. Real Companies Shipping Static Sites from Data-Driven Backends

The pattern of "data lives in a backend, output is static HTML" is now well-established. The technical term is **headless CMS + static generation**, but the pattern applies equally to any data-driven backend that exports static files.

### 4.1 Case Studies

| Company / Site | Stack | Results |
|---------------|-------|---------|
| **Smashing Magazine** | Hugo + Netlify (from WordPress) | Load time: 800ms -> **80ms** (10x). Build: 7,500 pages in 13 seconds. |
| **Spotify.Design** | Gatsby + Contentful | Static pages for design system documentation; content managed in headless CMS |
| **Nour Hammour** (fashion) | Shopify Hydrogen + Oxygen | **63% increase** in conversion rate; **128% increase** in sales YoY after headless static build |
| **Allbirds** | Headless Shopify + custom React | Fast, clean storefront; static product pages with selective hydration |
| **Rachio** | Shopify + GatsbyJS | Content-rich product detail pages; clean content-based landing pages |
| **L'Oreal** ("The Website Factory") | Headless CMS + static build | 3,000 websites managed; load time: 10s -> **<3s**; cloud-based scalability |
| **Full Stack Python** | Pelican | Entire site is static HTML generated from Markdown; serves millions of readers |
| **GOV.UK** | Custom Ruby SSG | Progressive enhancement; HTML-first; WCAG 2.1 AA compliant |

### 4.2 The Headless CMS + SSG Architecture

This is the dominant pattern for data-driven static sites:

```
+-------------------+       Build Step        +------------------+
|                   |  (scheduled or webhook)  |                  |
|  Data Backend     | -----------------------> |  Static Site     |
|  (CMS / API /     |    Fetch data at build   |  Generator       |
|   Database /      |    time, render HTML      |  (Hugo/Astro/    |
|   N3TX model)   |                          |   custom)        |
|                   |                          |                  |
+-------------------+                          +--------+---------+
                                                        |
                                                        | Deploy
                                                        v
                                               +------------------+
                                               |  CDN / Static    |
                                               |  Hosting         |
                                               |  (Cloudflare /   |
                                               |   Netlify / S3)  |
                                               +------------------+
                                                        |
                                                        | Serve
                                                        v
                                               +------------------+
                                               |  End User        |
                                               |  (Browser)       |
                                               +------------------+
```

The headless CMS market is projected to reach **$2.5 billion by 2026** (Gartner), and **73% of enterprises** have adopted headless CMS architectures (up 14% since 2021). Key players include Contentful, Strapi, Sanity, Hygraph, Contentstack, and Builder.io.

**What N3TX adds to this picture:** Most headless CMS + SSG architectures require choosing and integrating separate tools (a CMS for content management, an SSG for rendering, a hosting platform for deployment). N3TX already owns the data model, the schema, and the API. A static export feature would collapse the CMS + SSG into a single tool: define a model, generate HTML. No middleware, no build pipeline to stitch together.

---

## 5. Jamstack Evolution: The Pendulum Swing

### 5.1 The Three Eras

| Era | Period | Philosophy | Characteristic |
|-----|--------|-----------|----------------|
| **Static HTML** | 1991-2000 | Hand-written HTML files | Simple, fast, no tooling |
| **Dynamic Everything** | 2000-2015 | Server renders every page request | WordPress, Rails, Django, PHP |
| **Jamstack v1** | 2015-2021 | "JavaScript, APIs, Markup" -- static output + client-side JS | Gatsby, early Next.js, heavy JS bundles |
| **Jamstack v2** | 2021-2024 | Hybrid -- SSG + SSR + ISR; "use the right tool per page" | Next.js ISR, Nuxt, SvelteKit |
| **Post-Jamstack** | 2024-present | "Just markup" -- back to simplicity; zero JS by default | Astro, Hugo, Eleventy, pure HTML export |

The pendulum is swinging back. After a decade of increasing JavaScript complexity, the industry is rediscovering that **most web pages do not need client-side interactivity**.

Netlify -- which coined "Jamstack" -- has quietly deemphasized the term. The Jamstack Community Survey was last published in 2022. The emphasis has shifted from "JavaScript + APIs + Markup" to simply "pre-built markup served from a CDN."

### 5.2 The "Just HTML" Realization

The Jamstack promise was speed through pre-rendering. But many Jamstack sites shipped **more JavaScript** than the WordPress sites they replaced. A Next.js static export carries 583 KB of JS (median). A WordPress page carries 574 KB (median dynamic site JS). The "static" label was masking a reality: the HTML was pre-built, but the browser still had to download and parse a full React runtime.

The next wave -- represented by Astro (164 KB JS), Hugo (210 KB JS), and truly zero-JS sites -- fulfills the original promise: **fast pages because there is genuinely less to download and parse.**

> **Callout: The 697 KB Problem**
> The median mobile web page in 2025 ships 697 KB of JavaScript. On a budget Android phone with a 3G connection, this means 3-5 seconds just for JS download and parsing, before the page becomes interactive. A zero-JS static page becomes interactive the moment the HTML finishes loading -- typically under 500ms even on slow connections. This is not an incremental improvement; it is a **category change** in user experience.

---

## 6. Hosting Economics

### 6.1 Static Hosting: The $0-5/month Tier

Static sites can be hosted for free or near-free because they require only file serving, not compute. The major platforms:

| Platform | Free Tier | Bandwidth (Free) | Build Minutes (Free) | CDN Locations | Commercial Use |
|----------|----------|------------------|---------------------|---------------|---------------|
| **Cloudflare Pages** | Yes | **Unlimited** | 500/month | **300+** | Yes |
| **GitHub Pages** | Yes | 100 GB/month | N/A (push to deploy) | GitHub CDN | Yes (public repos) |
| **Netlify** | Yes | 100 GB/month | 300/month | Global CDN | **Yes** |
| **Vercel** | Yes | 100 GB/month | 6000 min/month | Global CDN | **No** (free tier) |
| **Kinsta** | Yes | 100 GB/month | 600/month | **260+** | Yes |

Paid tiers for static hosting start at **$5-20/month** and are typically only needed for high-traffic sites (>100 GB/month bandwidth) or teams needing collaboration features.

### 6.2 Dynamic Hosting: The $20-200+/month Tier

Dynamic sites require server compute, databases, and ongoing maintenance:

| Component | Typical Cost | Notes |
|-----------|-------------|-------|
| **VPS / App Server** | $5-40/month | DigitalOcean, Linode, Hetzner |
| **Managed App Hosting** | $20-100/month | Heroku, Railway, Render |
| **Database** | $5-50/month | Managed Postgres, MySQL |
| **CDN** | $0-20/month | Often separate from hosting |
| **SSL/TLS** | $0-10/month | Free via Let's Encrypt, but setup required |
| **Monitoring** | $0-30/month | Uptime, error tracking |
| **Backups** | $2-20/month | Database snapshots |
| **Total** | **$32-270/month** | Minimum viable production setup |

For a small-to-medium site (under 100K monthly visitors), the cost comparison is stark:

| Architecture | Monthly Cost | Annual Cost |
|-------------|-------------|-------------|
| **Static on CDN** | $0-5 | $0-60 |
| **Dynamic on VPS** | $20-60 | $240-720 |
| **Dynamic on managed hosting** | $50-200 | $600-2,400 |

> **Callout: The 95% Cost Reduction**
> One agency reported hosting costs dropping from **$8,000/month to $400/month** (95% reduction) after migrating to a static site stack. Support tickets decreased by **90%**. These are not theoretical projections; they are measured outcomes from production migrations.

### 6.3 The Hidden Costs of Dynamic

Beyond hosting fees, dynamic sites carry ongoing costs that static sites eliminate:

- **Security patching:** Server OS, runtime, framework, and dependency updates (ongoing labor cost)
- **Scaling incidents:** Traffic spikes require scaling policies or manual intervention; static CDN sites scale automatically
- **Uptime monitoring:** Servers go down; CDN-served static files effectively never do
- **Database maintenance:** Backups, migrations, connection pool tuning, query optimization
- **Cold start latency:** Serverless functions and containers have cold start penalties; static files do not

---

## 7. Security Advantages

Static sites have a fundamentally smaller attack surface than dynamic sites:

| Attack Vector | Dynamic Sites | Static Sites |
|--------------|--------------|-------------|
| **SQL Injection** | Vulnerable (database required) | **Impossible** (no database at runtime) |
| **XSS via server-side** | Possible (template injection) | **Impossible** (no server-side rendering at runtime) |
| **Server misconfiguration** | Common (exposed ports, debug modes) | **N/A** (no server to misconfigure) |
| **DDoS** | Requires mitigation infrastructure | **CDN-native** (300+ nodes absorb traffic) |
| **Dependency vulnerabilities** | Server-side deps are attack surface | **Build-time only** (not exposed at runtime) |
| **Plugin exploits** | Common (WordPress plugins, etc.) | **Impossible** (no runtime plugins) |
| **Authentication bypass** | Possible if auth layer has bugs | **N/A** (no auth at runtime for public content) |

Static sites reduce the attack surface to: the CDN provider's infrastructure, the DNS configuration, and any third-party scripts intentionally included. For a zero-JS static site, even the third-party script vector is eliminated.

---

## 8. Who Should NOT Go Static

Static generation is powerful but not universal. The following categories are poor fits:

### 8.1 Hard Limitations

| Requirement | Why Static Fails | Alternative |
|------------|-----------------|------------|
| **Real-time data** (stock prices, live scores, chat) | Static files are snapshots; they cannot update without rebuilding | SSR, WebSockets, or islands architecture |
| **User-generated content** (comments, forums, profiles) | No server to accept POST requests at runtime | Hybrid: static pages + API backend for writes |
| **Authentication / personalized content** | Static files are identical for all users | Server-side rendering or client-side JS for auth state |
| **Search across large datasets** | No server to query at runtime | Pre-built search index (Pagefind, Lunr.js) or external search API |
| **Frequent content updates** (>100 changes/day) | Each change requires a rebuild + deploy cycle | ISR (Incremental Static Regeneration) or dynamic rendering |
| **Very large sites** (>100K pages) | Build times become prohibitive for some SSGs | Hugo handles this (million-page sites); others struggle |

### 8.2 Build Time Scaling

Build times are the practical ceiling for static sites. Benchmarks across generators for 64,000 pages:

| Generator | Relative Speed (vs. Hugo) | Build Time (64K pages, approx.) |
|-----------|--------------------------|-------------------------------|
| **Hugo** | 1x (baseline) | **~30 seconds** |
| **Eleventy** | ~3-5x slower | 2-3 minutes |
| **Jekyll** | ~10-20x slower | 5-10 minutes |
| **Gatsby** | ~40x slower | 15-30 minutes |
| **Next.js** | ~30x slower | 10-20 minutes |

Hugo is the exception that proves static generation can scale: its latest versions (0.155+) include streaming builds that handle million-page sites. For other generators, the practical limit is in the low tens of thousands of pages before build times become disruptive to developer workflows.

### 8.3 Failure Stories and Cautionary Patterns

**The "static e-commerce" trap:** Several teams attempted fully static e-commerce stores and discovered that inventory, pricing, and cart functionality require real-time server interaction. The workaround -- rebuilding the entire site on every inventory change -- created build queues that could not keep up with the rate of change. The successful pattern is a **hybrid:** static product pages with dynamic cart/checkout handled by a thin API layer.

**The content velocity problem:** News organizations and high-frequency publishers found that static builds could not keep pace with editorial workflows. A newsroom publishing 50+ articles per day, each requiring a full site rebuild, experienced deploy queues backing up by hours. These organizations either reverted to dynamic CMS platforms or adopted ISR (Incremental Static Regeneration) to avoid full rebuilds.

**The "1000 contributors" problem:** Large open-source documentation projects discovered that static builds created merge conflicts and slow CI pipelines when dozens of contributors merged PRs simultaneously. The fix was not reverting to dynamic sites but improving the build pipeline (incremental builds, content-addressed caching, parallel builds).

> **The lesson is clear:** static generation fails when the rate of content change exceeds the rate of rebuilds, or when the site requires server-side computation at request time. For everything else -- and that is most of the web -- static generation is the better architecture.

---

## 9. The Islands of Interactivity Pattern

### 9.1 Concept

Islands architecture bridges the gap between fully static and fully dynamic. The idea, popularized by Katie Sylor-Miller and Jason Miller and implemented most prominently by Astro, is:

1. **Render the page as static HTML** (fast, lightweight, SEO-friendly)
2. **Identify small regions that need interactivity** (a search widget, a cart button, a form)
3. **Hydrate only those regions** with JavaScript, independently of each other

The result is a page that is 90-95% static HTML and 5-10% interactive JavaScript "islands."

### 9.2 How Astro Implements It

```html
<!-- This is rendered as static HTML. No JavaScript shipped. -->
<header>
  <h1>Product Catalog</h1>
  <nav>...</nav>
</header>

<!-- This island hydrates only when visible in the viewport -->
<SearchWidget client:visible />

<!-- This island hydrates when the browser is idle -->
<CartButton client:idle />

<!-- This is static HTML again. No JavaScript. -->
<footer>...</footer>
```

Astro's client directives control hydration timing:

| Directive | Behavior |
|-----------|---------|
| `client:load` | Hydrate immediately on page load |
| `client:idle` | Hydrate when browser is idle |
| `client:visible` | Hydrate when component enters viewport |
| `client:media` | Hydrate when a CSS media query matches |
| `client:only` | Skip server render; client-side only |

### 9.3 Performance Impact

The islands pattern explains Astro's strong performance numbers:

| Metric | Astro (Islands) | Next.js (Full Hydration) | Pure Static (Zero JS) |
|--------|----------------|------------------------|--------------------|
| Median JS size | 164 KB | 583 KB | **0 KB** |
| Median transfer size | 889 KB | 1,659 KB | **<100 KB** |
| Time to interactive | ~1-2s | ~3-5s | **Instant** (no JS) |

### 9.4 Relevance to N3TX

For N3TX's static export, the islands pattern offers a graduated approach:

- **Phase 1:** Generate fully static HTML + CSS. Zero JavaScript. Every page is a pre-built file. This covers catalogs, documentation, read-only data views.
- **Phase 2 (optional):** For pages that need light interactivity (search, filtering, forms), inject small, self-contained JS widgets as islands. The surrounding page remains static HTML.

This lets N3TX start with the simplest, most performant output (pure HTML) and add interactivity surgically only where needed -- rather than shipping a full framework runtime for every page.

---

## 10. The Python Ecosystem Gap

### 10.1 Current Python SSGs

The Python ecosystem has SSGs, but they lag behind the JavaScript and Go ecosystems:

| Tool | Focus | Strength | Weakness |
|------|-------|----------|----------|
| **Pelican** | Blogs | Pure Python; Jinja2 templates; easy for Python devs | Blog-centric; limited for non-blog sites |
| **MkDocs** | Documentation | Material theme is excellent; plugin ecosystem | Documentation-only; not general-purpose |
| **Sphinx** | Technical docs | Multi-format output; cross-referencing | Steep learning curve; RST-centric |
| **Lektor** | General | Admin UI; flat-file CMS feel | Small community; slow development |
| **Nikola** | Blogs | Multi-language; IPython notebook support | Niche; small community |

A widely cited observation: *"The world of static site generators has made amazing progress over the past few years and the Python ecosystem hasn't caught up with it."*

### 10.2 The Gap N3TX Can Fill

None of the existing Python SSGs generate HTML from schema-driven data models. They all expect content in Markdown, RST, or similar flat-file formats. The workflow is:

```
Existing Python SSGs:  Markdown/RST files --> Template engine --> HTML
```

What N3TX could offer:

```
N3TX Static Export:  Python model + data --> Schema-driven renderer --> HTML + CSS
```

This is structurally different. The content source is a database or API, not files. The schema carries layout hints, field ordering, grouping, and access rules. The output is not a "blog" or "documentation site" -- it is a **data-driven web application rendered as static files**.

No tool in the Python ecosystem does this today. The closest equivalents are in the JavaScript ecosystem (Next.js `getStaticProps`, Astro data fetching at build time), but those require JavaScript toolchains and produce JS-heavy output.

---

## 11. Build vs. Buy Decision Framework

For a technical CEO evaluating whether to build static export into N3TX, the key questions are:

| Question | If Yes | If No |
|----------|--------|-------|
| Is the primary content read-heavy? (catalogs, docs, listings) | Static is ideal | Consider hybrid |
| Does content change less than daily? | Static works well | Need ISR or dynamic |
| Is SEO a priority? | Static has structural advantages | Less important for internal tools |
| Is hosting cost a concern? | Static is 10-50x cheaper | Less relevant for funded startups |
| Do users need to log in? | Hybrid needed (static + auth layer) | Pure static works |
| Is the audience on low-end devices / slow networks? | Static is dramatically better | Less urgent for desktop-first audiences |
| Does the team already use Python? | N3TX static avoids JS toolchain | JS SSGs are more mature |

---

## 12. Summary: Where the Market Is Heading

1. **Static is growing but not dominant.** Prerendered sites are 0.5% of the web but growing 67% year-over-year in high-traffic tiers. The architectural direction is clear even if the absolute numbers are still small.

2. **"Static" increasingly means "zero JS."** The first wave of static sites (Gatsby, Next.js static export) shipped full JavaScript runtimes. The current wave (Astro, Hugo, Eleventy) is pushing toward minimal or zero JS. The market is rewarding lighter output.

3. **The headless CMS + SSG pattern is mainstream.** 73% of enterprises use headless CMS architectures. The missing piece for many is a simple, integrated tool that goes from data model to static HTML without stitching together 3-4 separate services.

4. **Hosting economics favor static.** Free CDN hosting with unlimited bandwidth (Cloudflare Pages) makes static sites effectively free to operate. Dynamic sites carry $30-270/month in baseline costs.

5. **SEO and Core Web Vitals are forcing the conversation.** With 53% of sites failing Core Web Vitals and page experience now 28% of Google's ranking algorithm, the performance advantages of static sites translate directly into business outcomes.

6. **Python is underserved.** The Python SSG ecosystem is blog-and-docs-focused. There is no Python tool that generates static HTML from schema-driven data models. This is the gap N3TX can fill.

7. **The islands pattern provides a graceful upgrade path.** Starting with zero-JS static output and adding interactivity as islands -- rather than starting with a full framework and trying to slim down -- is architecturally sound and aligned with market direction.

---

## Sources

1. [HTTP Archive Web Almanac 2024 - Jamstack Chapter](https://almanac.httparchive.org/en/2024/jamstack) -- Primary source for SSG market share, architecture distribution, performance metrics
2. [HTTP Archive Web Almanac 2025 - Page Weight](https://almanac.httparchive.org/en/2025/page-weight) -- Median page weight and JavaScript size statistics
3. [HTTP Archive Web Almanac 2024 - JavaScript](https://almanac.httparchive.org/en/2024/javascript) -- JavaScript usage statistics across the web
4. [Netlify - Smashing Magazine Case Study](https://www.netlify.com/customers/smashing/) -- WordPress to Hugo migration results (10x load time improvement)
5. [Smashing Magazine - Migration from WordPress to JAMstack](https://www.smashingmagazine.com/2020/01/migration-from-wordpress-to-jamstack/) -- Detailed migration process and architecture decisions
6. [CloudCannon - Top Five Static Site Generators for 2025](https://cloudcannon.com/blog/the-top-five-static-site-generators-for-2025-and-when-to-use-them/) -- SSG comparison and adoption trends
7. [CSS-Tricks - Comparing Static Site Generator Build Times](https://css-tricks.com/comparing-static-site-generator-build-times/) -- Build speed benchmarks across Hugo, Eleventy, Jekyll, Gatsby, Next.js, Nuxt
8. [Astro Docs - Islands Architecture](https://docs.astro.build/en/concepts/islands/) -- Official documentation on islands architecture and partial hydration
9. [GOV.UK Technology Blog - Why We Use Progressive Enhancement](https://technology.blog.gov.uk/2016/09/19/why-we-use-progressive-enhancement-to-build-gov-uk/) -- UK Government's HTML-first policy and rationale
10. [Wappalyzer - Static Site Generator Market Share](https://www.wappalyzer.com/technologies/static-site-generator/) -- Technology detection data across the web
11. [Contentful - Reducing the Attack Surface with Static Sites](https://www.contentful.com/blog/reducing-the-attack-surface-with-static-sites/) -- Security analysis of static vs. dynamic architectures
12. [SitePoint - 7 Reasons NOT to Use a Static Site Generator](https://www.sitepoint.com/7-reasons-not-use-static-site-generator/) -- Honest assessment of SSG limitations
13. [Hygraph - Top 12 SSGs in 2026](https://hygraph.com/blog/top-12-ssgs) -- Current SSG landscape overview
14. [Vercel vs Netlify vs Cloudflare Pages: 2025 Comparison](https://www.digitalapplied.com/blog/vercel-vs-netlify-vs-cloudflare-pages-comparison) -- Hosting platform feature and pricing comparison
15. [Keen Computer - Research White Paper: Future of Web Architecture (2025-2026)](https://www.keencomputer.com/solutions/software-engineering/880-research-white-paper-the-future-of-web-architecture-jamstack-and-static-site-generators-as-the-foundation-of-agile-digital-transformation-2025-2026) -- Industry analysis of Jamstack trends
16. [DigitalApplied - Site Speed SEO 2026](https://www.digitalapplied.com/blog/site-speed-seo-2026-pagespeed-impact-rankings) -- SEO impact of page speed and Core Web Vitals
17. [Weaverse - 12 Headless Shopify Stores Making Millions](https://weaverse.io/blogs/the-best-headless-shopify-examples) -- E-commerce static/headless case studies
18. [Patterns.dev - Islands Architecture](https://www.patterns.dev/vanilla/islands-architecture) -- Technical deep-dive on the islands pattern
19. [Storieasy - JAMstack in 2025: Still Relevant or Rapidly Evolving?](https://www.storieasy.com/blog/jamstack-in-2025-still-relevant-or-evolving) -- Jamstack evolution and current trajectory
20. [Crystallize - 10 Best Static Website Hosting Providers in 2026](https://crystallize.com/blog/static-hosting) -- Comprehensive hosting comparison with pricing data
