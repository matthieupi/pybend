## Static Site Generation Research (Docs 06-10) -- Condensed

### Key Findings (Top 20 Data Points)

1. Prerendered (fully static) sites are **0.5% of the web** but growing **67% YoY** in the top 10K tier.
2. Median mobile page ships **697 KB of JavaScript** (2025); a zero-JS static page achieves **<50 KB total** (10-35x reduction).
3. Next.js static export carries **583 KB JS** median; Astro **164 KB**; Hugo **210 KB**; true zero-JS is **0 KB**.
4. Static sites are **41% smaller** in transfer size, have **42% fewer requests**, and **66% smaller CSS** than dynamic sites.
5. Only **47% of websites pass all Core Web Vitals**; well-built static sites pass trivially (0ms TBT, near-zero CLS).
6. Page experience signals are **28% of Google's ranking factors**; **53% of users abandon** pages taking >3 seconds; **7% conversion drop per second** of delay.
7. Static hosting costs **$0-5/month** vs dynamic **$32-270/month**. One agency reported **95% cost reduction** ($8K to $400/month) and **90% fewer support tickets**.
8. Cloudflare Pages offers **unlimited bandwidth free** across **300+ CDN locations**.
9. **~30-35% of all websites** could be fully static; **55-65% require dynamic serving**.
10. PyBend static export estimated at **10-16 weeks** (full feature) or **5-7 engineering days** (MVP via Jinja2 templates).
11. **75% of PyBend's frontend rendering** is presentational HTML that can be replicated server-side; 25% is JS-only (actors, live updates, auth).
12. Static CSS bundle from PyBend components: **~1,307 lines, ~35KB unminified, ~8KB gzipped**.
13. CSS-only interactivity covers **80-90%** of expected SPA interactions (accordions, tabs, modals, carousels, filters, theme switching).
14. Irreducible JS for a static PyBend site with form submission: **~600-800 bytes minified** (<400 bytes gzipped).
15. Lighthouse scores: static HTML+CSS = **98-100**; static + tiny JS = **96-100**; current PyBend SPA = **70-90**; React SPA = **50-85**.
16. Hugo builds 64K pages in **~15 seconds**; Gatsby takes **~20 minutes** for the same. Python-based exporter expected in Eleventy/Jekyll range.
17. Smashing Magazine: WordPress to Hugo migration cut load times from **800ms to 80ms** (10x). Nour Hammour (fashion): **63% conversion increase**, **128% sales increase** after headless static build.
18. Headless CMS market projected at **$2.5 billion by 2026**; **73% of enterprises** have adopted headless CMS (up 14% since 2021).
19. Core CSS-only patterns (`<details>`, `:target`, `:checked`, `scroll-snap`, `:has()`, container queries) have **95%+ browser support**.
20. NTT.js already has `consumePreloadedSchema()` / `consumePreloadedData()` infrastructure, enabling a hybrid mode where static HTML loads instantly and NTT hydrates on top.

---

### Static Site Industry Summary

**Market landscape.** SSG ecosystem is bifurcated: content-first generators (Hugo, Eleventy, Jekyll, Pelican) produce pure HTML with minimal JS; framework-first generators (Next.js, Gatsby, Astro) carry JS runtimes. Hugo leads prerendered market at 18%, Next.js at 13%, Astro at 5% (tripled from 2023). Gatsby is declining post-Netlify acquisition -- cautionary tale about build performance mattering more than ecosystem size.

**Growth signals.** 60% of new projects use Jamstack/static-first (up from 27% in 2020). The industry is in a "post-Jamstack" era (2024-present) swinging back to "just markup" and zero-JS defaults. Netlify itself deemphasized the Jamstack term after 2022.

**The no-JS movement.** GOV.UK mandates progressive enhancement (HTML-first, JS is additive). US EPA requires JS-free functionality where possible. Python documentation ecosystem (Django REST, Read the Docs, Python.org) runs almost entirely on static generators with near-zero JS.

**Hosting economics.** For <100K monthly visitors: static on CDN = $0-60/year; dynamic on VPS = $240-720/year; dynamic on managed hosting = $600-2,400/year. Free CDN tiers: Cloudflare Pages (unlimited BW, 500 build min/mo), GitHub Pages (100 GB/mo), Netlify (100 GB/mo, 300 build min/mo).

**Security.** Static sites eliminate SQL injection, server-side XSS, server misconfiguration, plugin exploits, and auth bypass entirely. Attack surface reduces to CDN infrastructure and DNS.

**Who should NOT go static.** Real-time data (stock prices, chat), user-generated content, authenticated/personalized pages, search over large datasets, frequent updates (>100 changes/day), very large sites on slow SSGs (>100K pages except Hugo).

**Python ecosystem gap.** Existing Python SSGs (Pelican, MkDocs, Sphinx, Lektor, Nikola) are blog/docs-focused and expect Markdown/RST input. None generate HTML from schema-driven data models. This is the gap PyBend fills.

---

### Technical Pipeline Summary

**SSG core pipeline:** Collection (read data) -> Transformation (templates) -> Emission (write HTML) -> Deployment. PyBend has Collection solved (StorableMixin.list(), ProtoModel.schema()). The challenge is Transformation: converting schema + data to HTML without hand-written templates.

**Schema-to-HTML rendering.** A `StaticRenderer` walks JSON Schema `properties` in `ui.field_order` sequence (mirroring form.js logic), dispatches on type/widget (`currency`, `textarea`, `boolean`, `array`/$ref, etc.), respects `ui.display`, `ui.protected`, and `ui.groups`, and handles `$defs` recursively for nested models. The schema IS the template.

**CSS generation.** Three strategies: (1) Extract component Shadow DOM styles into a single flattened stylesheet, replacing `:host` with class-scoped selectors; (2) Inline critical CSS (<14KB) in `<head>` for first TCP round-trip, defer the rest; (3) CSS-only interactivity for accordions, tabs, carousels, dark mode. PyBend's estimated static CSS bundle: ~8KB gzipped.

**Build pipeline.** StaticBuilder class: iterates models, fetches all entities, renders list pages (paginated, 20/page) and detail pages, generates CSS, copies assets, post-processes (critical CSS split, fingerprinting, sitemap, minification). IncrementalBuilder extends with content-hash-based rebuild (only changed pages rewritten). Asset fingerprinting enables 1-year CDN cache.

**Output structure.** Nested `index.html` convention (`products/1/index.html` -> `/products/1/`) works universally on all hosting platforms without rewrite rules. URL mapping: `GET /products` -> `products/index.html`, `GET /products/1` -> `products/1/index.html`, pagination -> `products/page/2/index.html`.

**Deployment targets.** Cloudflare Pages (~57ms TTFB, unlimited free BW), GitHub Pages (~80ms), Netlify (~227ms), AWS S3+CloudFront (~50ms). Config examples provided for GitHub Actions, Cloudflare wrangler.toml, S3 sync, and nginx.

**Performance targets.** TTFB <100ms, FCP <500ms, LCP <1.0s, CLS 0.00, TBT 0ms, Lighthouse 100, total weight <50KB. Compared to current dynamic PyBend: 3-10x faster TTFB, 2-4x faster FCP/LCP, TBT eliminated, 5-10x smaller page weight.

**Build time estimates.** 100 entities/3 models: <1s. 1K entities/5 models: 2-5s. 10K entities/10 models: 15-30s. 100K entities/10 models: 2-5 min. Incremental rebuilds: <1s regardless of total site size.

---

### Decision Framework Summary

**When static makes sense.** Content update frequency <1 change/hour, no personalization, no complex forms, no real-time needs, no authentication, <50K pages, high SEO criticality.

**Project type classification.** Fully static fit: product catalogs (~8% of web), documentation (~6%), blogs (~7%), landing pages (~5%), portfolios (~4%). Dynamic required: e-commerce with cart (~12%), SaaS dashboards (~15%), social platforms (~8%), internal tools (~10%).

**Rendering spectrum.** Five positions: Fully Static (0 KB JS, $0-5/mo) -> Static + Islands (<50 KB JS, $0-5/mo) -> ISR/SSG (5-50 KB, $0-20/mo) -> SSR (50-150 KB, $20-500/mo) -> Full SPA (200-500 KB, $20-500/mo). Most PyBend apps are inherently dynamic but a meaningful subset (read-only public sites) would benefit.

**Engineering effort.** Full feature: 10-16 weeks (HTML template engine 3-4wk, file generator 2-3wk, asset pipeline 1-2wk, incremental rebuild 2-3wk, testing 1-2wk, CI/webhook 1-2wk). At ~$10K/week = $100K-$160K investment. Break-even requires 167-1,333 projects depending on savings per project.

**TCO comparison by traffic.** 100 visitors/day: static $0/mo vs dynamic $6/mo. 1K/day: $0 vs $6-12. 10K/day: $0-5 vs $12-24. 100K/day: $5-20 vs $48-96. 1M/day: $20-100 vs $200-1,000.

**Anti-patterns.** (1) Trying to make interactive apps static -- if removing JS makes the core journey impossible, stay dynamic. (2) Over-engineering build pipeline for small sites -- 200 pages rebuild in 1-2 seconds, no incremental needed. (3) Premature static export during rapid model iteration. (4) Hybrid "uncanny valley" -- if >2 features need your own backend, stay dynamic. (5) Rebuilding what CDN caching already solves.

**Recommended phased approach.** Phase 1 (weeks 1-3): Aggressive HTTP caching + CDN edge caching on dynamic stack -- benefits 100% of users, achieves 70-80% of static performance. Phase 2 (months 2-3): Evaluate demand. Phase 3 (if warranted): Minimal static exporter -- full rebuild only, Jinja2 templates, CLI command, skip incremental/search/forms.

**Alternatives to static export.** HTTP caching (2-3 weeks, 70-80% benefit), CDN edge caching (1 week), pre-rendering service (1-2 days, but Google deprecated dynamic rendering in 2024), hybrid static shell + dynamic API (4-6 weeks, most natural PyBend fit).

---

### PyBend Static Export Architecture Summary

**Pipeline replacement.** Current: Model -> Schema -> NTT.js DynamicClass -> Shadow DOM. Static: Model -> Schema -> StorableMixin.list() -> Jinja2 templates -> HTML files. Replaces bottom four JS stages with server-side Python.

**Key source files for replication.** `form.js` (368 lines) is the primary target -- deterministic function of (schema, value). `ntt-item.js` (660 lines) has xs/sm/md/lg/xl size methods, all fully deterministic and pre-computable server-side. `ListElement.js` (244 lines) for list rendering. `Permissions.js` (191 lines) for access filtering.

**form.js replication.** `getForm()` reads schema.properties + schema.ui, determines fieldOrder, generates header (name + description), filters fields (excludes hidden/protected/no-permission), respects groups (fieldsets), and dispatches to `getInput()`. `getInput()` type dispatch: string -> div/input, textarea -> div/textarea, number -> div/input, currency -> formatted div, boolean -> checkbox, $ref -> link, selfref -> parent link, array -> `getListInput()` with nested items. `getListInput()` shows first 2 items, collapses rest with "show more." All translates to a single Jinja2 macro.

**CSS situation.** Component CSS lives in Shadow DOM. Solution: extract all into single flattened stylesheet with `:host` replaced by class selectors. Inventory: dark-theme.css (408 lines), light-theme.css (119), ntt-item.css (669), ntt-list.css (81), ntt-element.css (71 partial). Total: ~1,307 lines, ~35KB unminified, ~8KB gzipped. Google Fonts (Inter, JetBrains Mono) is the only external dependency.

**Authorization strategy.** Recommended: Strategy A (public-only export) -- export what ANYONE can see, filter by `__access__` read rule. Optional: Strategy B (per-role export) -- separate builds per role (`--role=anonymous`, `--role=user`, `--role=admin`). Strategy C (client-side gate) not recommended.

**Proposed module structure.** `src/pybend/core/export/`: `exporter.py` (~150 LOC), `renderer.py` (~200 LOC), `css_compiler.py` (~80 LOC), Jinja2 templates (~300 LOC), CLI (~50 LOC), tests (~200 LOC). Total: **~980 LOC, 5-7 engineering days** for MVP.

**Integration points.** Plugs into PyBendApp with new `.export()` method or `export_static(app, output)` function. Uses same `registered_models`, same storage backend, same `ProtoModel.schema()`, same `StorableMixin.list()/.get()`. Does NOT start FastAPI, register routes, or need JWT middleware.

**Hybrid mode discovery.** NTT.js already has `#consumePreloadedSchema()` and `#consumePreloadedData()` (lines 237-277) that read inline `<script data-ntt-schema>` / `<script data-ntt-data>` tags. Static exporter can generate pages with both pre-rendered HTML (instant display) and inline data (for NTT hydration if JS bundle is included).

**Gap analysis.** No gaps: schema generation, data access. Small gaps: FK hydration (needs full-object mode, not just hrefs), CSS `:host` transform, access filtering in Python. Medium gaps: field rendering (1:1 form.js translation), size-based layouts (1:1 ntt-item.js translation), child entity resolution, CLI command. New code: Jinja2 templates (~200 lines), CSS compiler (~80 lines).

**Implementation order.** Phase 1 (MVP): CSS compiler, field renderer macros, entity template (md), collection template (sm grid), exporter orchestrator, CLI. Phase 2: index page, navigation, image handling, pagination. Phase 3: per-role export, hybrid mode with NTT preloading, custom template overrides, nested entity pages.

---

### CSS-Only Interactivity Summary

**Core finding.** Modern CSS (2025-2026) provides native mechanisms for 80-90% of interactive patterns: accordions (`<details>/<summary>`), tabs (`:target`), modals (`<dialog>` + Popover API), carousels (`scroll-snap`), filters (`:checked` + `:has()`), theme switching (`prefers-color-scheme` + `:checked`), tooltips (anchor positioning + popover), page transitions (View Transitions API), adaptive layouts (container queries).

**Pattern-by-pattern mapping to PyBend:**
- **Field groups** (`ui.groups`): `<details>/<summary>` replaces JS expand/collapse. 97.5% browser support.
- **Display modes** (xs/sm/md/lg/xl): Container queries replace JS size-method dispatch. Same HTML adapts to container width. 95%+ support.
- **Show more/less** for nested entities: `<details>` replaces `.show-more-btn` click handler.
- **Tab navigation** for entity sections: `:target` pseudo-class. 99%+ support.
- **Filters** on list pages: `:checked` checkboxes + `:has()` selectors hide/show cards by data attributes.
- **Dark mode**: `prefers-color-scheme` for system default, `:checked` toggle for manual override.
- **Delete confirmation**: `<dialog>` with Invoker Commands (`commandfor`/`command` attributes). Popover: 90%+ support. Invoker Commands: ~65% (progressive enhancement).
- **Page transitions** (list to detail): View Transitions API. SPA transitions: 85%+. MPA transitions: ~70% (Chrome/Edge).
- **Image carousels**: `scroll-snap` with flex layout. 96% support.

**What absolutely requires JS.** Form submission (POST/PUT/DELETE with auth headers), authentication (token storage, login flow), real-time updates (WebSocket/SSE), clipboard operations, complex drag-and-drop, dynamic data fetching, custom form validation messages, analytics. Total: **~600-800 bytes minified for all of these combined**.

**The "Tiny JS" architecture.** CSS handles all visual interactivity. A single `<script>` block under 400 bytes gzipped handles form submission, login/token storage, and method invocation (like, favorite, comment). Compare: React 42KB, Alpine.js 6KB.

**Accessibility.** `<details>/<summary>` is the gold standard (native keyboard nav, screen reader support, no ARIA needed). `:target` tabs need `role="tablist"`/`role="tab"` for proper semantics. `:checked` inputs must NOT use `display: none` -- use `opacity: 0; position: absolute` to remain in accessibility tree. Visual-only `:has()` state changes need `aria-live` regions.

**Performance comparison.** Static HTML+CSS: Lighthouse 98-100, FCP 0.4-0.6s, TBT 0ms. Static + tiny JS: 96-100, FCP 0.4-0.6s, TBT 0-10ms. Current PyBend SPA: 70-90, FCP 1.0-2.0s, TBT 50-200ms. SPA (React/Vue): 50-85, FCP 1.5-3.0s, TBT 200-800ms. Google data: each additional KB of JS adds ~8.5ms to Time to Interactive on slow 3G.

**Progressive enhancement ladder.** Tier 1 (pure HTML+CSS, no JS): content readable, navigation via links, accordions via `<details>`, theme via `prefers-color-scheme` -- use case: read-only catalogs, docs. Tier 2 (tiny JS <1KB): form submission, login, method buttons -- use case: interactive catalog, blog with comments. Tier 3 (enhanced JS 1-10KB): real-time updates, complex filtering, drag-and-drop -- use case: admin dashboard. **Tier 1 is the baseline, not an afterthought.**

**Key recommendations for PyBend static export.** (1) Default to `<details>/<summary>` for all field groups and nested entities. (2) Use container queries instead of JS size-method dispatch. (3) Emit `<dialog>` for confirmations. (4) Ship single `<script>` under 400 bytes gzipped. (5) Enable `@view-transition { navigation: auto; }` in base stylesheet. (6) Use `:checked` filters for enumerable categories. (7) Target Lighthouse Performance >= 95, Accessibility >= 95.
