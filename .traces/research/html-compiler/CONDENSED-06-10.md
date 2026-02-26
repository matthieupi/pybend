## Static Site Generation Research (Docs 06-10) -- Condensed

### Key Findings (Top 20 Data Points)

1. Prerendered (fully static) sites are **0.5% of the web** but growing
   **67% YoY** in the top 10K tier.
2. Median mobile page ships **697 KB of JavaScript** (2025); a zero-JS
   static page achieves **<50 KB total** -- a 10-35x reduction.
3. Next.js static export carries **583 KB JS** median; Astro **164 KB**;
   Hugo **210 KB**; true zero-JS is **0 KB**.
4. Static sites are **41% smaller** in transfer size, have **42% fewer
   requests**, and **66% smaller CSS** than dynamic sites (HTTP Archive).
5. Only **47% of websites pass all Core Web Vitals**; well-built static
   sites pass trivially (0ms TBT, near-zero CLS).
6. Page experience signals are **28% of Google's ranking factors**;
   **53% of users abandon** pages >3 seconds; **7% conversion drop
   per second** of delay. Mobile-first indexing covers **94%** of
   Google searches.
7. Static hosting costs **$0-5/month** vs dynamic **$32-270/month**.
   One agency reported **95% cost reduction** ($8K to $400/month) and
   **90% fewer support tickets**.
8. Cloudflare Pages offers **unlimited bandwidth free** across **300+
   CDN locations**. GitHub Pages: 100 GB/mo. Netlify: 100 GB/mo + 300
   build min/mo.
9. **~30-35% of all websites** could be fully static; **55-65%
   require dynamic serving**; **5-10%** benefit from hybrid.
10. PyBend static export estimated at **10-16 weeks** (full feature)
    or **5-7 engineering days** (MVP via Jinja2 templates, ~980 LOC).
11. **75% of PyBend's frontend rendering** is presentational HTML
    replicable server-side; 25% is JS-only (actors, live updates, auth).
12. Static CSS bundle from PyBend components: **~1,307 lines, ~35KB
    unminified, ~8KB gzipped**.
13. CSS-only interactivity covers **80-90%** of expected SPA
    interactions (accordions, tabs, modals, carousels, filters, themes).
14. Irreducible JS for a static PyBend site with form submission:
    **~600-800 bytes minified** (<400 bytes gzipped). Compare: React
    42KB, Alpine.js 6KB.
15. Lighthouse scores: static HTML+CSS = **98-100**; static + tiny
    JS = **96-100**; current PyBend SPA = **70-90**; React SPA =
    **50-85**.
16. Hugo builds 64K pages in **~15 seconds**; Gatsby takes **~20
    minutes** for the same. Python exporter expected in Eleventy/Jekyll
    range (~4s for 1K pages).
17. Smashing Magazine: WordPress to Hugo = **800ms to 80ms** (10x),
    7,500 pages in 13 seconds. Nour Hammour (fashion): **63%
    conversion increase**, **128% sales increase** YoY.
18. Headless CMS market projected at **$2.5 billion by 2026**; **73%
    of enterprises** adopted headless CMS (up 14% since 2021).
19. Core CSS-only patterns (`<details>`, `:target`, `:checked`,
    `scroll-snap`, `:has()`, container queries) have **95%+ browser
    support** globally.
20. NTT.js already has `consumePreloadedSchema()` /
    `consumePreloadedData()` infrastructure enabling hybrid mode where
    static HTML loads instantly and NTT hydrates on top.

---

### Static Site Industry Summary

**SSG ecosystem.** Content-first generators produce pure HTML with
minimal JS; framework-first generators carry JS runtimes. Key players:

| Generator | Stars | 1K-Page Build | Key Differentiator |
|-----------|-------|---------------|---------------------|
| Hugo (Go) | ~78K | <1s | Raw speed, compiled binary, no deps |
| Next.js (React) | ~128K | 10-30s | Hybrid SSG/SSR, Vercel ecosystem |
| Astro (JS) | ~48K+ | 3-8s | Islands architecture, zero JS default |
| Gatsby (React) | ~56K | 30-120s | GraphQL layer, declining since 2022 |
| Eleventy (JS) | ~17K | 2-5s | Zero-config simplicity, template agnostic |
| Jekyll (Ruby) | ~49K | 30-60s | GitHub Pages native, mature themes |
| Pelican (Python) | ~13K | 5-15s | Python-native, Jinja2, blog-focused |
| MkDocs (Python) | ~20K | 2-5s | Docs-specific, Material theme dominance |
| Zola (Rust) | ~14K | <1s | Single binary, Rust speed |

Hugo leads prerendered market at 18%, Next.js at 13%, Astro at 5%
(3x growth from 2023). Gatsby declining post-Netlify acquisition --
cautionary tale: build speed and DX matter more than ecosystem size.
Wappalyzer: SSGs present on 3.5% of all websites in 2023 (up from
2.5% in 2022).

**Growth signals.** 60% of new projects use Jamstack/static-first (up
from 27% in 2020). 44% report 2x+ performance. 1 in 3 teams moved for
faster deployment. Industry in "post-Jamstack" era -- many Jamstack
sites shipped MORE JS than WordPress they replaced (Next.js static:
583 KB vs WordPress dynamic: 574 KB).

**The no-JS movement.** GOV.UK mandates progressive enhancement for
WCAG 2.1 AA. US EPA requires JS-free where possible. Python docs
(Django REST on MkDocs, Read the Docs on Sphinx, Python.org) runs
near-zero JS. Mastro framework (2025): "zero-JS by default." Static
HTML from 1996 renders; React apps from 2018 may not build.

**Hosting economics.** Free CDN tiers:
- Cloudflare Pages: unlimited BW, 500 build min/mo, 300+ CDN nodes
- GitHub Pages: 100 GB/mo BW, push-to-deploy, public repos
- Netlify: 100 GB/mo BW, 300 build min/mo, preview deploys
- Vercel: 100 GB/mo BW, 6000 build min/mo (no commercial free tier)
- Kinsta: 100 GB/mo BW, 600 build min/mo, 260+ CDN nodes

Dynamic hosting: VPS $5-40/mo + DB $5-50/mo + CDN + SSL + monitoring +
backups = $32-270/mo. For <100K monthly visitors: static $0-60/year
vs dynamic VPS $240-720/year vs managed $600-2,400/year.

**Security.** Static eliminates at runtime: SQL injection (no DB),
server-side XSS (no server rendering), server misconfiguration (no
server), DDoS (CDN-native across 300+ nodes), dependency vulns
(build-time only), plugin exploits (no runtime plugins), auth bypass
(no auth layer for public content).

**Case studies.** Smashing Magazine: 800ms->80ms (10x), 7,500 pages in
13s. L'Oreal: 3,000 sites, 10s-><3s. Nour Hammour: 63% conversion,
128% sales. Allbirds: headless Shopify, selective hydration.
Spotify.Design: Gatsby+Contentful. GOV.UK: custom SSG, WCAG 2.1 AA.
Full Stack Python: Pelican, serves millions.

**Who should NOT go static.** Real-time data, user-generated content
requiring POST, auth/personalized pages, large dataset search, >100
changes/day, >100K pages on slow SSGs. At 64K pages: Hugo ~30s,
Eleventy 2-3min, Jekyll 5-10min, Gatsby 15-30min. Failures: e-commerce
inventory sync impossible, newsrooms with 50+/day backing up queues.

**Python ecosystem gap.** Pelican, MkDocs, Sphinx, Lektor, Nikola are
blog/docs-focused (Markdown/RST). None generate HTML from schema-driven
models. PyBend fills this: model + data -> schema renderer -> HTML+CSS.

**Islands architecture.** Astro: static HTML + hydrate small JS regions
(90-95% static, 5-10% JS). Directives: `client:load/idle/visible/
media/only`. Explains 164KB JS vs Next.js 583KB. PyBend: Phase 1 =
zero JS; Phase 2 = islands where needed.

---

### Technical Pipeline Summary

**SSG core pipeline.** Collection (read data) -> Transformation
(templates) -> Emission (write HTML+assets) -> Deployment (upload).
PyBend has Collection solved (`StorableMixin.list()`,
`ProtoModel.schema()`). Transformation is the challenge.

**Python SSG reference.** Frozen-Flask is the closest analogy
(simulates WSGI requests, writes responses) but assumes Flask routes
returning HTML; PyBend routes return JSON. Custom Jinja2 pipeline
provides full control. staticjinja is minimal (<500 LOC).

**Schema-to-HTML rendering.** `StaticRenderer` walks schema properties
in `ui.field_order` sequence (mirroring form.js). Per-field dispatch:
string, currency, textarea, boolean, number, array/$ref (recursive via
$defs). Respects `ui.display=false`, `ui.protected`, `ui.groups`. The
schema IS the template -- adding a model field updates both live UI and
static site automatically.

**CSS generation.** Three strategies: (1) Extract Shadow DOM styles
into flattened stylesheet, `:host` -> class selectors (`.ntt-item`,
`.ntt-list`). (2) Critical CSS inlining: above-fold CSS (<14KB) in
`<head>` for first TCP round-trip; defer rest via `<link preload>`.
(3) CSS-only interactivity for tabs, accordions, dark mode.

CSS replacing JS: `:has()`, container queries, scroll-driven
animations, popover, `<dialog>`, view transitions, `@layer`, `:target`,
`scroll-snap`, `@property` -- all Baseline 2022-2025.

**Build pipeline.** `StaticBuilder`: models -> schema()+list() ->
paginated lists (20/page) -> detail pages -> CSS -> assets -> post-
process (critical CSS, fingerprinting, sitemap, minify).
`IncrementalBuilder` adds SHA-256 hashing for skip-unchanged.

**Output structure.** Nested `index.html` (`products/1/index.html` ->
`/products/1/`). Works on all platforms without rewrite rules.

**Deployment TTFB.** Cloudflare ~57ms, S3+CloudFront ~50ms, GitHub
Pages ~80ms, Vercel ~100ms, Netlify ~227ms.

**Performance: static vs dynamic PyBend.**

| Metric | Dynamic (current) | Static (target) | Gain |
|--------|-------------------|-----------------|------|
| TTFB | 200-500ms | 20-80ms | 3-10x |
| FCP | 1-2s | 300-500ms | 2-4x |
| LCP | 2-3s | 500ms-1s | 2-4x |
| TBT | 100-300ms | 0ms | Eliminated |
| Page weight | 200-400KB | 20-50KB | 5-10x |
| Lighthouse | 60-85 | 95-100 | Near-perfect |

**Build time estimates.**
- 100 entities / 3 models: <1s, ~500KB output
- 1,000 entities / 5 models: 2-5s, ~5MB output
- 10,000 entities / 10 models: 15-30s, ~50MB output
- 100,000 entities / 10 models: 2-5 min, ~500MB output
- Incremental rebuild after single change: <1s at any scale

---

### Decision Framework Summary

**Decision tree.** Auth + all personalized = Full Dynamic. Auth + some
public = Hybrid. No auth + changes >1/min = SSR+CDN. >1/hour =
ISR/webhooks. >50K pages = static+incremental. <50K = **Fully Static**
(PyBend target).

**Project type addressability.**

| Type | % of Web | Static? |
|------|----------|---------|
| Product catalogs (read-only) | ~8% | Yes |
| Documentation | ~6% | Yes |
| Blogs / content | ~7% | Yes |
| Landing pages | ~5% | Yes |
| Portfolios | ~4% | Yes |
| E-commerce (with cart) | ~12% | No (dynamic) |
| SaaS dashboards | ~15% | No |
| Social platforms | ~8% | No |
| Internal tools | ~10% | No |
| Other dynamic | ~25% | No |

~30% fully static fit. W3Techs: 28.6% without CMS (declining 3.9%/yr).
WordPress: 43.3% of all websites.

**Engineering effort.** 10-16 weeks total ($100K-$160K at $10K/week).
Break-even: 167-1,333 projects at $50-10/mo savings. Strategic value.

**TCO by traffic (monthly).** 100/day: $0 vs $6. 1K/day: $0 vs $6-12.
10K/day: $0-5 vs $12-24. 100K/day: $5-20 vs $48-96. 1M/day: $20-100
vs $200-1,000.

**Content freshness.** Docs: hours-days. Blogs: minutes-hours. Catalog:
15-60min scheduled. Pricing: minutes (webhook). Landing: days-weeks.
News/live data: NOT suitable.

**Anti-patterns.** (1) Making interactive apps static. (2) Over-
engineering builds for <1K pages. (3) Premature export during rapid
iteration. (4) Hybrid uncanny valley (>2 features needing backend).
(5) Rebuilding what CDN caching solves (70-80% of benefit, 10-20%
effort).

**Recommended phases.** Phase 1 (wk 1-3): HTTP caching + CDN (benefits
100% of users). Phase 2 (mo 2-3): evaluate demand. Phase 3: minimal
exporter (CLI, Jinja2, full rebuild, skip incremental/search/forms).

**Alternatives.**

| Approach | Effort | TTFB | Server? | Cost/mo |
|----------|--------|------|---------|---------|
| Full static | 10-16wk | 10-30ms | No | $0-5 |
| HTTP caching | 2-3wk | 20-50ms | Yes | $6-50 |
| CDN edge | 1wk | 15-40ms | Yes | $6-50 |
| Static shell+API | 4-6wk | 15-40ms | Yes(API) | $6-55 |

---

### PyBend Static Export Architecture Summary

**Pipeline.** Current: Model -> Schema -> NTT.js DynamicClass -> Shadow
DOM. Static: Model -> Schema -> StorableMixin.list() -> Jinja2 -> HTML.
Replaces bottom four JS stages with server-side Python.

**Source files to replicate.** `form.js` (368 lines): deterministic
(schema, value)->HTML, primary target. `ntt-item.js` (660 lines):
xs/sm/md/lg/xl sizes, all deterministic. `ListElement.js` (244 lines):
list render. `Permissions.js` (191 lines): access filtering. All five
size methods pre-computable: xs = value.name; sm = name + image + 3
fields + id; md/lg/xl = full Formidable.getForm().

**form.js replication.** `getForm()`: read schema.properties + ui ->
fieldOrder -> header (name h2, description h4) -> filter (exclude
hidden/protected/no-permission) -> grouped fieldsets or flat list.
`getInput()` dispatch: string->`<div>`, textarea->`text-block div`,
currency->`$X.XX div`, boolean->`<div>`, $ref->link, selfref->parent
link, array->`getListInput()` (2 visible, rest collapsed). Single
Jinja2 macro replaces entire dispatch.

**CSS extraction.** Shadow DOM -> single flattened file, `:host` ->
class selectors. Inventory:

| CSS File | Lines | Include |
|----------|-------|---------|
| dark-theme.css | 408 | Full (tokens, layout, typography) |
| light-theme.css | 119 | Full (theme overrides) |
| ntt-item.css | 669 | Full (transform :host) |
| ntt-list.css | 81 | Full (transform :host) |
| ntt-element.css | 71 | Partial (error/empty states) |
| **Total** | **~1,307** | **~35KB unminified, ~8KB gzipped** |

External: Google Fonts (Inter, JetBrains Mono) -- optional self-host.

**Authorization.** Strategy A (recommended): public-only, export
ANYONE-visible content. Strategy B (optional): per-role builds
(`--role=anonymous/user/admin`). Strategy C: client-side JS gate
(not recommended -- defeats zero-JS goal).

**Module: `src/pybend/core/export/`.** exporter.py (~150 LOC),
renderer.py (~200 LOC), css_compiler.py (~80 LOC), templates/ (~300
LOC for base, collection, entity, macros), CLI (~50 LOC), tests (~200
LOC). **Total: ~980 LOC, 5-7 engineering days.**

**Integration (three levels).** `export_static(app, output="./build")`
or `pb.export(output, theme="dark")` or `pybend export --static
--output ./build`. Uses same registered_models, storage, schema(),
list(). Does NOT start FastAPI or require JWT.

**Hybrid mode.** NTT.js lines 237-277 have `#consumePreloadedSchema()`
and `#consumePreloadedData()` reading `<script data-ntt-schema>` tags.
Exporter can emit pre-rendered HTML + inline data for progressive
hydration. Instant static load, full NTT hydrates if JS included.

**Gaps.** None: schema gen, data access. Small: FK hydration (needs
as_objects), :host transform, access filtering. Medium: field rendering,
size layouts, child resolution, CLI. Risks: FK href-not-object, circular
refs (depth limit), >10K entities (pagination).

**Implementation.** Phase 1 MVP: CSS compiler, field macros, entity
template (md), collection template (sm grid), orchestrator, CLI.
Phase 2: index, nav, images, pagination. Phase 3: per-role export,
hybrid NTT preloading, custom templates, nested entity pages.

---

### CSS-Only Interactivity Summary

**Core finding.** Modern CSS provides native mechanisms for 80-90% of
SPA interactions. A static PyBend export with CSS-only + <1KB JS scores
95-100 Lighthouse while retaining interactive feel.

**12 patterns mapped to PyBend:**

1. **Accordions** -- `<details>/<summary>`. Replaces JS show-more/less.
   97.5% support. Excellent accessibility (native keyboard, screen
   reader, no ARIA needed).

2. **Tabs** -- `:target` pseudo-class. Field groups as tab panels.
   Default via `:first-of-type` + `:has()`. 99%+. Caveat: modifies
   browser history.

3. **Filters** -- `:checked` + `:has()`. Hidden checkboxes + label
   pills toggle card visibility by data attributes. Use `opacity:0;
   position:absolute` (not `display:none`) for accessibility.

4. **Theme switching** -- `prefers-color-scheme` + `:checked` toggle.
   CSS custom properties resolve without JS. 96%+.

5. **Modals** -- `<dialog>` + Popover API + Invoker Commands
   (`commandfor`/`command`). Replaces `confirm()`. Animated via
   `@starting-style`. Popover 90%+. Invoker ~65% (progressive).

6. **Carousels** -- `scroll-snap` + flex. Touch/keyboard/mouse. Chrome
   135+ adds `::scroll-button`/`::scroll-marker`. 96%.

7. **Adaptive display** -- Container queries replace xs/sm/md/lg/xl
   JS dispatch. `@container card (max-width:200px)` = xs pill;
   `(min-width:501px)` = md card. 95%+.

8. **Page transitions** -- View Transitions API.
   `@view-transition { navigation: auto; }`. Image morphs list->detail.
   MPA: ~70% (Chrome/Edge). Zero cost when unsupported.

9. **Tooltips** -- CSS anchor positioning + popover. Chrome/Edge 125+.
   Use `@supports (anchor-name: --x)` for progressive enhancement.

10. **User preferences** -- `prefers-reduced-motion` disables
    animations. `prefers-contrast: more` for high contrast. 96%+.

11. **Auto-numbering** -- CSS `counter()` for comments, visible item
    counts. Replaces JS `.list-field-count` badge. 99%+.

12. **Parent state** -- `:has()`. Card highlight on focus, hide empty
    state when list has children, disable submit when fields empty. 95%+.

**Irreducible JS (per capability).** Form submission ~200 bytes, auth
~400, real-time ~300, clipboard ~50, drag-drop ~500, data fetch ~150,
validation ~200, analytics ~100. **Total for PyBend with forms:
~600-800 bytes, <400 gzipped.** React: 42KB. Alpine.js: 6KB.

**Lighthouse comparison.**

| Architecture | Score | FCP | TBT | JS Size |
|---|---|---|---|---|
| Static HTML+CSS | 98-100 | 0.4-0.6s | 0ms | 0 KB |
| Static + tiny JS | 96-100 | 0.4-0.6s | 0-10ms | <1 KB |
| SSG (Astro/11ty) | 90-98 | 0.6-1.0s | 0-50ms | 5-30 KB |
| Current PyBend | 70-90 | 1.0-2.0s | 50-200ms | 50-150 KB |
| SPA (React/Vue) | 50-85 | 1.5-3.0s | 200-800ms | 150-500 KB |

Google: each KB of JS adds ~8.5ms to TTI on slow 3G. A 200KB React app
= ~1.7s of blocking time on slow connections.

**Real-world references.** GOV.UK: ~61KB JS, Lighthouse 99/100 (reduced
CSS 93%, JS 61%). lite.cnn.com: <5KB. Hacker News: ~15KB.

**Accessibility.** `<details>`: Excellent (native, no ARIA). `:target`
tabs: add tablist/tab/tabpanel roles. `:checked`: never display:none.
`scroll-snap`: needs ARIA. `<dialog>`: Excellent. `:has()`: visual
only (need aria-live).

**Progressive enhancement.** Tier 1 (0 JS): content, nav, accordions,
theme. Tier 2 (<1KB): forms, login, method buttons. Tier 3 (1-10KB):
real-time, complex filter, drag-drop. **Tier 1 is baseline.**

**Seven recommendations.** (1) `<details>/<summary>` default for all
ui.groups + nested entities. (2) Container queries for adaptive sizing.
(3) `<dialog>` for confirmations. (4) Single `<script>` under 400 bytes
gzipped. (5) `@view-transition { navigation: auto; }` in base CSS.
(6) `:checked` filters for categories. (7) Target Lighthouse
Performance >= 95, Accessibility >= 95.
