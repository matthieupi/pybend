# 📋 Server-Side Rendering for PyBend: Strategic Analysis Report

## For: CEO & Engineering Team
## Date: February 2026
## Prepared by: Architecture Team

---

### How to Read This Document

This report serves two audiences simultaneously. **CEO and leadership:** read the plain-English paragraphs at the top of each section -- they explain what matters and why. The tables, diagrams, and code references that follow provide evidence and specifics for the engineering team. You do not need to read the technical depth to make decisions; the opening paragraphs carry the strategic conclusions.

**Engineering team:** the "so what?" paragraphs frame the business context for each technical finding. The technical depth that follows is where you will find architecture diagrams, codebase references, performance benchmarks, and implementation specifics. Appendices contain the full risk register and source citations.

**Notation:**
- `> 💡 **Key Finding:**` -- a boxed finding that matters for both audiences
- File references point to the actual PyBend codebase at `/workspace/src/pybend/`
- Performance numbers cite published industry data (sources in Appendix C)
- "Strategy A/B/C" refers to the three SSR implementation options detailed in Section 7

---

## 📋 Executive Summary

Server-side rendering has become the dominant architecture for public-facing web applications. **59% of JavaScript developers** now use SSR in their projects, and the web frameworks market is projected to reach $1.92B by 2035. The question for PyBend is not whether SSR matters to the industry -- it does -- but whether it matters for *us*, and if so, what the cheapest path to value looks like.

The answer is nuanced. PyBend serves a dual market: authenticated schema-driven applications (dashboards, admin tools, CRUD apps) where SSR provides near-zero value, and public-facing data catalogs (product listings, content sites) where SSR is a competitive requirement. The good news: **PyBend's architecture is unusually well-positioned for SSR**, not because it follows the JavaScript meta-framework playbook, but because the server already owns the complete rendering specification via JSON Schema.

**Three core findings:**

1. **PyBend already has SSR infrastructure.** The `NTT.js` entity system contains `#consumePreloadedSchema()` and `#consumePreloadedData()` methods (lines 244-277) that consume server-injected data without network requests. This is not hypothetical -- the code exists today, ready for a server-side route to feed it.

2. **85-90% of display-mode HTML is server-renderable.** The `form.js` form generator and `ntt-item.js` size methods are pure functions of schema + data with zero browser dependencies. A Python port produces identical HTML.

3. **Strategy A (schema + data injection) eliminates 200-400ms of latency with ~50 lines of Python.** This is a one-day implementation that uses existing client-side infrastructure. No new rendering engine, no new dependencies, no architectural risk.

> 💡 **Key Finding:** The recommended path is not "adopt SSR" in the traditional sense. It is: have the server inject what it already knows (schema + data) into the HTML page, eliminating two sequential network round-trips. Then, if the business requires SEO or first-paint optimization for public pages, layer on server-rendered HTML using Declarative Shadow DOM.

The **recommended hydration strategy** is "Progressive Islands with Embedded Schema" -- leveraging Web Components' natural encapsulation as independent hydration units, prioritized by viewport position and user interaction. This avoids the full-page hydration cost that plagues React-based SSR implementations.

**Investment summary:**

| Phase | Effort | Impact | Risk |
|-------|--------|--------|------|
| Strategy A: Schema+Data injection | 1-2 days | Eliminates 200-400ms FCP delay | Minimal |
| Strategy B: Server-rendered HTML with DSD | 3-5 weeks | FCP < 300ms, SEO-ready | Medium |
| Progressive hydration | 2-3 weeks | TTI -40-60% for interactive pages | Medium |
| Full SSR pipeline + caching | 2-3 weeks | Production-grade SSR with CDN | Low-Medium |

**Total estimated investment:** 8-12 engineering weeks for the full pipeline. Strategy A alone delivers immediate value in under a week.

---

## 1. 🔍 What Is SSR and Why Now?

### The Business Context

When a user visits a PyBend application today, their browser downloads a minimal HTML shell, then makes two sequential network requests -- one for the schema, one for the data -- before rendering anything meaningful. The user stares at a blank page (or skeleton) for 1.5 to 2 seconds. Server-side rendering means the server does this work itself and sends ready-to-display HTML to the browser. The user sees content in 300-500ms instead of 1500-2000ms.

Why does this matter now? Three reasons:

1. **Google ranks faster sites higher.** Core Web Vitals became an official ranking signal in 2021 and their importance has increased. SSR directly improves LCP (Largest Contentful Paint), the most impactful metric.

2. **The industry has moved past "SSR vs SPA."** The 2023-2026 era introduced islands architecture, streaming SSR, partial hydration, and resumability. These approaches deliver SSR's benefits without its historical costs. PyBend's Web Components are natural "islands."

3. **PyBend's architecture makes SSR cheaper than the industry average.** The server already owns the schema, the data, the access rules, and the rendering specification. Other frameworks require duplicating client components on the server. PyBend requires only a Python function that reads the schema it already generated.

### What SSR Actually Changes

```
CURRENT FLOW (Client-Side Rendering):

Browser                          Server
  |                                |
  |-- GET /static/matrix.html --->|  (instant: static file)
  |-- GET /static/core/NTT.js -->|  (JS modules load)
  |-- GET /Product (schema) ---->|  (NETWORK REQUEST 1: ~100-200ms)
  |<-- JSON Schema --------------|
  |   [Build DynamicClass]        |
  |-- GET /products (data) ----->|  (NETWORK REQUEST 2: ~100-200ms)
  |<-- JSON data ----------------|
  |   [Render components]         |
  |   [USER SEES CONTENT]         |  Total: ~1500-2000ms

WITH STRATEGY A (Data Injection):

Browser                          Server
  |                                |
  |-- GET /app/products --------->|
  |                                |-- Product.schema() (cached, ~0ms)
  |                                |-- Product.list()   (~5ms)
  |<-- HTML with embedded --------|  (schema + data in <script> tags)
  |    schema + data              |
  |   [Parse embedded JSON]       |  No network requests needed!
  |   [Render components]         |
  |   [USER SEES CONTENT]         |  Total: ~800-1000ms (-40-50%)

WITH STRATEGY B (Pre-Rendered HTML):

Browser                          Server
  |                                |
  |-- GET /app/products --------->|
  |                                |-- Product.schema() (cached)
  |                                |-- Product.list()
  |                                |-- SchemaRenderer.render_list()
  |<-- Full HTML with DSD --------|  (content visible immediately)
  |   [USER SEES CONTENT]         |  Total: ~300-500ms (-75-85%)
  |   [JS loads in background]    |
  |   [Components hydrate]        |  Interactive: ~800ms
```

> 💡 **Key Finding:** PyBend's current "waterfall of emptiness" -- two sequential network requests before any content appears -- is the core latency problem. SSR eliminates this waterfall entirely, whether through data injection (Strategy A) or full HTML rendering (Strategy B).

*Sources: Research docs 02-technical-deep-dive.md (Section 7.4), 04-our-stack-relevance.md (Section 1)*

---

## 2. 🏢 Industry Landscape

### What the Market Tells Us

SSR adoption increased 41% year-over-year through 2025. The global web frameworks market reached $959.67M in 2025 and is projected to hit $1.92B by 2035 at a 7.2% CAGR. Every major consumer-facing web company either uses SSR or has evaluated it seriously. But the *how* has shifted dramatically.

The important pattern: **most companies do not SSR their entire application.** Netflix only SSRs the logged-out homepage. Airbnb SSRs search results but the authenticated dashboard is client-rendered. Notion SSRs marketing and public pages, not the editor. This selective approach -- SSR for public-facing, SEO-critical surfaces; CSR for authenticated, interactive experiences -- is the dominant real-world strategy.

### Framework Market Position

| Framework | Weekly Downloads | Satisfaction | Rendering Model | Relevance to PyBend |
|-----------|-----------------|-------------|-----------------|---------------------|
| Next.js | ~13.2M | Declining | SSR/SSG/RSC/ISR | Low (React-centric) |
| Nuxt | ~971K | Stable ~85% | SSR/SSG/Hybrid | Low (Vue-centric) |
| **Astro** | ~804K | **94% (highest)** | **Islands/SSG/SSR** | **High (architecture match)** |
| SvelteKit | ~500K est. | ~90% | SSR/SSG/Hybrid | Low (Svelte-centric) |
| Qwik | ~50K est. | Niche | Resumability | Medium (concept applicable) |

> 💡 **Key Finding:** Astro's 94% developer satisfaction -- the highest of any framework -- validates the islands architecture that PyBend's Web Components naturally implement. Astro proves you do not need full SSR hydration to win on performance. Each `<ntt-item>` and `<ntt-list>` is already an independent "island."

### The Satisfaction Paradox

Next.js dominates usage but is losing developer satisfaction. The State of JS 2024 survey reports "a subtle but discernible downturn in user sentiment about meta-frameworks, even while actual usage continues to increase." This mirrors the jQuery pattern of the early 2010s -- ubiquitous but increasingly resented. The market is moving toward lighter-weight, framework-agnostic approaches -- exactly where PyBend sits.

### Measured Business Outcomes

| Company | Metric | Improvement | Business Impact |
|---------|--------|-------------|-----------------|
| Tokopedia | LCP | -55% | +23% session duration, +8% conversions |
| Rakuten 24 | Core Web Vitals | All green | +53% revenue/visitor, +33% conversion |
| Vodafone Italy | LCP | -31% | +8% sales |
| Carpe/Shopify | LCP | -52% | +5% conversion, +15% revenue |
| Netflix | Load time | -50% | 200KB JS savings |
| Yelp | p99 latency | -125ms | Compute costs reduced to 1/3 |

These numbers are most relevant for **e-commerce and content sites** where every visitor is a potential conversion. For internal tools, dashboards, and authenticated SaaS applications -- a significant portion of PyBend's target market -- the SEO argument evaporates and the conversion argument weakens. The performance argument remains, but the ROI threshold is higher.

### Industry Adoption by Application Type

| Application Type | SSR Adoption | Primary Driver |
|------------------|-------------|----------------|
| E-commerce | Very High (~80%) | SEO + conversion |
| Media / Publishing | Very High (~75%) | SEO + ad revenue |
| SaaS (Public-facing) | Moderate (~50%) | Marketing SSR, app CSR |
| **SaaS (App/Dashboard)** | **Low (~15-20%)** | **Performance only** |
| **Internal Tools** | **Very Low (~5%)** | **Almost no benefit** |

*Sources: Research doc 01-industry-landscape.md (Sections 1-5), State of JS 2024, npm trends, web.dev case studies*

---

## 3. ⚡ Technical Architecture Overview

### SSR Pattern Taxonomy

The industry has evolved from a single "SSR" concept into seven distinct rendering strategies. Understanding which pattern applies to which use case prevents the mistake of adopting "SSR" as a monolith.

```
                    RENDERING PATTERN SPECTRUM

    Pure CSR          Hybrid               Pure SSR
    (SPA)             Patterns              (Traditional)
    |                 |                     |
    v                 v                     v
    +---------+   +----------+   +--------+   +---------+
    | Client  |   | Islands  |   | Stream |   | Full    |
    | Side    |   | Arch.    |   | SSR    |   | SSR     |
    | Render  |   +----------+   +--------+   +---------+
    +---------+   | Partial  |   | ISR    |   | Static  |
                  | Pre-     |   +--------+   | Gen     |
                  | render   |   | Resume |   | (SSG)   |
                  +----------+   +--------+   +---------+

    <--- More JS, slower FCP    Faster FCP, less JS --->
    <--- Richer interactivity   Better SEO ----------->
```

### Pattern Comparison

| Pattern | TTFB | FCP | TTI | JS Payload | Best For |
|---------|------|-----|-----|------------|----------|
| Full SSR | 200-500ms | Excellent | Delayed | Full bundle | SEO-critical dynamic pages |
| Streaming SSR | 50-150ms | Excellent | Delayed | Full bundle | Mixed-latency data pages |
| SSG | 20-50ms | Best | Depends | Varies | Static content sites |
| ISR | 20-50ms* | Best* | Depends | Varies | Product catalogs |
| **Islands** | 100-300ms | Great | **Fast** | **Minimal** | **Content with scattered interactivity** |
| Resumability | 100-300ms | Excellent | **Instant** | ~1KB init | Performance-critical sites |

*\* After initial cache fill*

### Why Islands Architecture Is the Right Fit for PyBend

The critical insight is that **Web Components are already islands by nature.** Each `<ntt-item>`, `<ntt-list>`, or `<ntt-method>` component is a self-contained Custom Element with:

- **Isolated rendering** -- Shadow DOM prevents style and DOM leakage
- **Self-contained lifecycle** -- `connectedCallback`, `disconnectedCallback`
- **Independent state** -- each component manages its own data via the Actor system
- **Explicit boundaries** -- the custom element tag *is* the island boundary

An SSR implementation for PyBend would server-render the static HTML shell, and each Web Component would hydrate independently -- no full-page hydration needed. This avoids the "uncanny valley" problem (page looks ready but buttons do not work) that plagues React-based SSR.

```
  +------------------------------------------------------------------+
  |  Static HTML (no JS)                                              |
  |                                                                   |
  |  +------------------+                                             |
  |  | Island: Search   |  <-- Hydrated, interactive                  |
  |  | (JS loaded)      |                                             |
  |  +------------------+                                             |
  |                                                                   |
  |  Product description text (static HTML, zero JS)                  |
  |                                                                   |
  |  +------------------+    +-------------------+                    |
  |  | Island: ntt-item |    | Island: ntt-method|                   |
  |  | (hydrates on     |    | (hydrates on      |                   |
  |  |  visibility)     |    |  interaction)     |                   |
  |  +------------------+    +-------------------+                    |
  |                                                                   |
  |  Footer (static HTML, zero JS)                                    |
  +------------------------------------------------------------------+
```

### Declarative Shadow DOM: The Enabler

Historically, Web Components and SSR were incompatible because Shadow DOM required JavaScript to create. **Declarative Shadow DOM (DSD)** changes this entirely. It allows Shadow DOM to be expressed in static HTML, parsed by the browser during HTML parsing -- no JavaScript needed.

```html
<!-- Server renders this. Browser displays it BEFORE any JS loads. -->
<ntt-item>
  <template shadowrootmode="open">
    <div class="card" data-display="md">
      <h2 data-value="name">Widget Pro</h2>
      <span data-value="price">$29.99</span>
    </div>
  </template>
</ntt-item>
```

**Browser support (February 2026):** Chrome 111+, Edge 111+, Safari 16.4+, Firefox 123+. Global coverage: **94.38%**. This is production-ready.

*Sources: Research docs 02-technical-deep-dive.md (Sections 2-3), 05-hydration-strategies.md (Section 9), web.dev DSD documentation*

---

## 4. 🔍 Our Current Architecture Assessment

### What the Server Already Knows

PyBend's architecture is fundamentally different from React/Vue/Angular applications. The server does not just serve data -- it owns the **complete rendering specification**. The JSON Schema that `ProtoModel.schema()` emits carries:

| Schema Section | What It Carries | Where It Is Used |
|---------------|-----------------|------------------|
| `properties[field].type` | Input widget type | `form.js:getInput()` |
| `properties[field].ui.widget` | Specialized rendering (currency, textarea) | `form.js:getInput()` |
| `properties[field].ui.display` | Field visibility | `form.js` field filtering |
| `properties[field].ui.protected` | Backend-owned fields (hidden in edit) | `form.js` field filtering |
| `ui.field_order` | Field rendering sequence | `form.js:getForm()` |
| `ui.groups` | Fieldset grouping | `form.js:renderGroupedFields()` |
| `access` | ABAC rules (create/read/update/delete) | `Permissions.js`, button visibility |
| `methods` | Callable endpoints with UI hints | `<ntt-method>` rendering |
| `$defs` | Nested model schemas | `NTT.SCHEMA()` registration |

The frontend's `form.js` and `ntt-item.js` are essentially **schema interpreters** -- they read instructions and produce HTML. That interpretation can happen on the server in Python just as easily as it happens in the browser in JavaScript.

### Existing SSR Infrastructure in the Codebase

PyBend already has nascent SSR support that most teams would need to build from scratch.

**1. Schema Pre-loading** (`NTT.js`, lines 244-257):

```javascript
static #consumePreloadedSchema(model) {
    const el = document.querySelector(`script[data-ntt-schema="${model}"]`);
    if (!el) return false;
    try {
        const data = JSON.parse(el.textContent);
        el.remove();
        NTT.SCHEMA(data);
        return true;
    } catch (e) {
        return false;
    }
}
```

This method is called in `NTT.ATTACH()` (line 333) *before* dispatching a network schema request. If the server injects `<script data-ntt-schema="Product">{...}</script>` into the HTML, the client skips the schema fetch entirely. **Network request 1 is eliminated.**

**2. Data Pre-loading** (`NTT.js`, lines 265-277):

```javascript
static #consumePreloadedData(tablename) {
    const el = document.querySelector(`script[data-ntt-data="${tablename}"]`);
    if (!el) return null;
    try {
        const data = JSON.parse(el.textContent);
        el.remove();
        return data;
    } catch (e) {
        return null;
    }
}
```

Consumed in `NTT.SCHEMA()` (lines 419-425): if pre-loaded data exists, `DC.READ(preloadedData)` is called instead of dispatching a network fetch. **Network request 2 is eliminated.**

**3. Schema Completeness** (`proto_model.py`, lines 199-316):

`ProtoModel.schema()` generates a remarkably complete rendering specification. The schema carries field types, validation constraints, UI widget hints, field ordering, field grouping, display/hide flags, access rules, method signatures with UI hints, nested model schemas, and renderer hints. Every piece of information `form.js` and `ntt-item.js` need is in this schema.

**4. Response Self-Description** (`proto_model.py`, lines 117-137):

Every entity response via `model_dump(response=True)` includes `$schema` (the model schema URL) and `$id` (the instance URL). An entity record plus the cached schema is sufficient to render -- no additional lookups needed.

### Server-Renderable Surface Area

The key question: how much of the frontend rendering is a pure function of schema + data (and therefore portable to the server)?

| Component | Location | Server-Renderable? | Notes |
|-----------|----------|--------------------|----|
| Form fields (display) | `form.js:getInput()` | **Yes** | Pure type-to-HTML mapping |
| Form fields (edit) | `form.js:getInput()` | **Yes** | Same mapping, different mode |
| Form groups/fieldsets | `form.js:renderGroupedFields()` | **Yes** | `schema.ui.groups` to fieldsets |
| Header (h2/h4) | `form.js:getHeader()` | **Yes** | name + description |
| xs pill | `ntt-item.js:xs()` | **Yes** | Single span |
| sm compact row | `ntt-item.js:sm()` | **Yes** | Permission check solvable server-side |
| md card | `ntt-item.js:md()` | **Yes** | Full form + methods |
| List grid | `ListElement.render()` | **Yes** | Container + children |
| Method buttons | `ntt-method` tag gen | **Yes** | `schema.methods` to button HTML |
| Currency formatting | `form.js:getInput()` | **Yes** | `$${value.toFixed(2)}` |

> 💡 **Key Finding:** An estimated **85-90% of initial display-mode HTML is server-renderable.** The remaining 10-15% comprises interactive behaviors (edit/save toggle, input change handling, delete confirmation, card click navigation, method execution) that require JavaScript and the Actor/Matrix message bus.

### What Genuinely Requires Client-Side JavaScript

| Behavior | Why Client-Only |
|----------|-----------------|
| Edit/Save toggle | User-initiated state change |
| Input change handling | Real-time form binding |
| Delete confirmation | `confirm()` dialog + network call |
| Card click navigation | Actor message routing |
| Load More pagination | Incremental data fetch |
| Method button execution | Network call + response handling |
| Real-time entity updates | WebSocket/Actor system |
| Surgical DOM updates | In-place patching |

The Actor/Matrix system is needed for **runtime interactivity**, not initial render. SSR eliminates the need for the ATTACH -> SCHEMA -> READ bootstrap sequence. After the server delivers pre-rendered HTML, the actor system resumes its role for live updates and user interactions. The two are complementary, not conflicting.

*Sources: Research doc 04-our-stack-relevance.md (Sections 1-5), codebase files `NTT.js`, `form.js`, `ntt-item.js`, `proto_model.py`*

---

## 5. 📊 Cost-Benefit Analysis

### For the CEO: The Bottom Line

SSR rarely pays for itself below 10 million monthly page views when measured purely on conversion-lift ROI. The math is simple: conservative conversion improvements of +10% relative (e.g., 2.0% to 2.2%) yield ~$12,000/year in additional revenue for a mid-size e-commerce site, against an annual SSR cost of $12,000-$20,000 for selective implementation. At best, this is break-even.

**However**, PyBend's architecture changes this calculus significantly:

1. **Strategy A costs almost nothing.** Injecting pre-loaded schema and data into the HTML requires ~50 lines of Python and uses existing client-side infrastructure. The "SSR cost" for this phase is effectively zero.

2. **The schema-driven approach avoids the biggest cost.** Traditional SSR migrations cost $40,000-$80,000+ because they require duplicating rendering logic across server and client. PyBend's schema is the single source of truth -- the Python renderer reads the same schema the JavaScript renderer reads. No duplication.

3. **SEO is a binary gate, not a gradient.** For PyBend applications that need Google indexability (public catalogs, content sites), SSR is not a "nice to have" -- it is a competitive requirement. Without it, PyBend loses to Next.js for any project where SEO matters.

### Three-Year TCO Comparison

| Line Item | CSR Only (Current) | Strategy A (Data Injection) | Strategy A+B (Full SSR) |
|-----------|--------------------|-----------------------------|--------------------------|
| Infrastructure (Year 1) | $1,200 | $1,200 (no change) | $3,600 |
| Infrastructure (Years 2-3) | $2,400 | $2,400 (no change) | $6,000 |
| Developer setup cost | $0 | $2,000 (1-2 days) | $20,000-$35,000 |
| Ongoing dev overhead/yr | $0 | $1,000 | $5,000-$10,000 |
| Monitoring/tooling | $600 | $600 | $1,800 |
| **3-Year Total** | **$4,200** | **$7,200** | **$46,400-$66,400** |

### Performance Impact Estimates

| Metric | Current (CSR) | Strategy A | Strategy A+B | Industry SSR |
|--------|--------------|------------|--------------|-------------|
| FCP | 1500-2000ms | 800-1000ms | 300-500ms | 500-1800ms |
| TTI (display-only) | ~2000ms | ~1000ms | ~300ms | 1000-2500ms |
| TTI (interactive) | ~2000ms | ~1200ms | ~800ms | 2000-5000ms |
| JS at initial load | 100% | 100% | 0% (DSD) | Varies |
| Network requests before paint | 3 (HTML + schema + data) | 1 (HTML with embedded data) | 1 (HTML with rendered content) | 1-2 |

### Break-Even Analysis

```
SSR ROI = (Conversion Lift x Revenue/Conversion x Monthly Conversions x 12)
        - (Annual SSR Infrastructure + Annual SSR Dev Overhead)

For Strategy A (near-zero cost):
  ROI = Any performance improvement / $1,000 annual cost
  Break-even: Almost immediately

For Strategy A+B (full SSR):
  Scenario: E-commerce site, 50K monthly visitors, 2% conversion, $50 AOV
  Revenue lift (conservative +10% relative): $6,000/year
  SSR cost: $15,000-$22,000/year
  ROI: Negative for first 2 years, positive at scale (>200K visitors/month)
```

> 💡 **Key Finding:** Strategy A (schema + data injection) has near-zero cost and immediate payoff. Strategy B (full HTML rendering) should be pursued only when the business case for SEO or first-paint performance justifies $20K-$35K in initial investment. For most PyBend deployments serving authenticated users, Strategy A is sufficient.

*Sources: Research doc 03-decision-framework.md (Section 5), 01-industry-landscape.md (Section 5)*

---

## 6. 🗺️ Decision Framework

### When SSR Makes Sense for PyBend

```
START: Does search engine indexing matter for this application?
  |
  +-- NO --> Is the content personalized per user?
  |            |
  |            +-- YES --> CSR with Strategy A (embed schema+data)
  |            |
  |            +-- NO --> Is it behind authentication?
  |                        |
  |                        +-- YES --> CSR with Strategy A
  |                        |
  |                        +-- NO --> Strategy A+B (SSR for public pages)
  |
  +-- YES --> Does content change per request or per user?
               |
               +-- YES --> Strategy A+B with short cache TTL (60s + SWR)
               |
               +-- NO --> Does content change daily or less?
                            |
                            +-- YES --> SSG or ISR (pre-render at build time)
                            |
                            +-- NO --> Strategy A+B with edge caching
```

### Quick Decision Matrix

| Application Type | Strategy | SSR? | Effort | Expected Impact |
|------------------|----------|------|--------|-----------------|
| Internal CRUD tool | CSR + Strategy A | No | 1 day | -200-400ms FCP |
| Admin dashboard | CSR + Strategy A | No | 1 day | -200-400ms FCP |
| Authenticated SaaS app | CSR + Strategy A | No | 1 day | -200-400ms FCP |
| **Public product catalog** | **Strategy A+B** | **Yes** | **3-5 weeks** | **FCP < 500ms, SEO-ready** |
| **E-commerce storefront** | **Strategy A+B + caching** | **Yes** | **5-8 weeks** | **FCP < 300ms, conversion lift** |
| Marketing / landing pages | SSG (separate build) | N/A | 1-2 weeks | Optimal performance |

### Anti-Patterns: When SSR Is the Wrong Choice

| Anti-Pattern | Why SSR Hurts |
|-------------|---------------|
| Internal tools / admin panels | No SEO value; adds latency for zero benefit |
| Real-time dashboards | Data changes faster than SSR can render |
| Highly interactive applications | Hydration cost negates first-paint benefit |
| Applications behind authentication | Search engines cannot access the content |
| Prototypes and MVPs | Adds weeks to development time prematurely |

*Sources: Research doc 03-decision-framework.md (Sections 4, 8, 9)*

---

## 7. 💡 Recommendation

### The Three-Strategy Approach

We recommend a layered approach: implement Strategy A immediately, then evaluate the business need for Strategy B before committing to the larger investment.

#### Strategy A: Schema + Data Injection (Ship This Week)

Inject pre-loaded schema and entity data as `<script>` tags in the HTML page. The existing `#consumePreloadedSchema()` and `#consumePreloadedData()` methods in `NTT.js` consume this data without network requests.

**What the server-side route looks like:**

```python
# ~45 lines of Python. No new dependencies beyond Jinja2.
@ssr_router.get("/app/{model_name}", response_class=HTMLResponse)
async def ssr_page(model_name: str, request: Request):
    model_class = registered_models.get(model_name)
    schema = model_class.schema()                    # Cached, ~0ms
    result = model_class.list(limit=20, offset=0)    # ~5ms

    # Inject as <script data-ntt-schema> and <script data-ntt-data>
    return SSR_TEMPLATE.render(
        schemas={model_name: json.dumps(schema)},
        datasets={schema['__tablename__']: json.dumps(serialized)},
    )
```

**Result:** Eliminates 2 network round-trips. Client renders from local data. FCP improves by 200-400ms. Implementation: 2-4 hours including tests.

#### Strategy B: Pre-Rendered HTML with Declarative Shadow DOM (3-5 Weeks)

Build a Python schema renderer that produces the same HTML the frontend would produce, wrapped in Declarative Shadow DOM templates. The server renders `<ntt-item>` and `<ntt-list>` components as complete HTML -- visible before any JavaScript loads.

```html
<!-- Server output: fully visible with zero JavaScript -->
<ntt-list model="Product">
  <template shadowrootmode="open">
    <div class="list-grid">
      <ntt-item ref="http://.../products/1">
        <template shadowrootmode="open">
          <div class="card" data-display="md">
            <h2 data-value="name">Widget Pro</h2>
            <div class="currency-display" data-value="price">$29.99</div>
          </div>
        </template>
      </ntt-item>
    </div>
  </template>
</ntt-list>
```

**Result:** Content visible before any JavaScript executes. FCP < 300ms. SEO-ready.

**Implementation requires:**
- Python form renderer (~400 lines, porting `form.js:getInput()` logic)
- DSD template wrapper generation
- Hydration detection in `ntt-item.render()` (~20 lines per component)
- CSS extraction utility for inline DSD styles

#### Strategy C: HTMX-Enhanced Progressive Rendering (Defer)

Replace the actor-based data flow with HTMX attributes for initial page loads. Server returns HTML fragments. JavaScript handles only what HTMX cannot.

**Recommendation: Do NOT pursue Strategy C now.** It creates a dual rendering path (JSON + HTML) that adds complexity. PyBend's actor system handles interactivity well. HTMX would be useful only if the goal is to eliminate client-side JS entirely, which would sacrifice real-time updates and the actor coordination model.

### Recommended Hydration Strategy: Progressive Islands with Embedded Schema

Based on analysis of all five hydration approaches (full, progressive, selective, partial, resumability), the optimal strategy for PyBend combines:

1. **Islands architecture** -- leveraging Web Components' natural encapsulation as independent hydration units
2. **Progressive hydration** -- prioritized by viewport position and user intent
3. **Embedded schema** -- breaking the DynamicClass circular dependency
4. **Deferred actor initialization** -- Matrix boots fast, Actors load lazily

```
Phase 1: Immediate (0ms)
  - HTML with DSD renders instantly (zero JS)
  - Browser paints full content from server-rendered HTML

Phase 2: Critical Path (< 50ms of JS)
  - Tiny bootstrap script (< 3KB) initializes Matrix
  - Parse embedded schemas, create DynamicClasses
  - Attach root event delegation listener

Phase 3: Component Reconnection (progressive)
  - Above-fold components hydrate immediately
  - Below-fold components hydrate on viewport intersection
  - Method buttons hydrate on hover/focus
  - Priority: P0 (nav, search) -> P1 (visible cards) -> P2 (below-fold) -> P3 (edit forms)

Phase 4: Background Enhancement (idle time)
  - Verify entity data freshness (optional background fetch)
  - Establish WebSocket for real-time updates
  - Pre-load method handlers for visible buttons
```

### Authorization in SSR: Per-User Rendering

A critical design consideration: SSR must respect per-user authorization. Different users see different edit/delete buttons, different data subsets, and different field visibility.

PyBend already has everything needed:

1. **User identity** -- extracted from JWT via `_get_user(request)` in `routes_fastapi.py`
2. **Access rules** -- declared on models via `__access__` and serialized via `access_schema()`
3. **ABAC resolver** -- `DefaultResolver` evaluates rules like `OWNER | ROLE('admin')` against user + resource
4. **SQL filter pushdown** -- `_resolver.sql_filter_for(ctx)` generates WHERE clauses for list filtering

For SSR, the same chain applies:

```python
async def ssr_product_list(request: Request):
    user = _get_user(request)                              # From JWT
    ctx = _build_context(request, Product, "list")
    auth_filter = _resolver.sql_filter_for(ctx)

    result = Product.list(sql_filter=auth_filter, limit=20)  # Filtered for this user
    schema = Product.schema()                                 # Same for all users

    # But rendered HTML differs: buttons depend on user + resource
    for item in result['data']:
        item._can_update = _resolver.authorize(
            _build_context(request, Product, "update", resource=item)
        )
```

**Caching implications:** Per-user SSR means HTML is not globally cacheable. However:

- **Anonymous users (no JWT):** Fully cacheable at CDN edge. All data visible via `ANYONE` rules, no edit/delete buttons. This covers SEO and first-visit use cases perfectly.
- **Authenticated users:** Cache by role (not per-user). One HTML variant for "admin" role, one for "user" role. Button visibility encoded via CSS classes on `<body>` rather than conditional HTML rendering.
- **Schema injection (Strategy A):** Always cacheable -- the schema is identical for all users.

### Breaking the DynamicClass Circular Dependency

A subtle but important challenge: PyBend's DynamicClasses are created at runtime from schema data. The client needs the DynamicClass to hydrate, but the DynamicClass requires the schema, which requires a network request -- a circular dependency.

The embedded schema breaks this cycle:

```
WITHOUT EMBEDDED SCHEMA (circular):
  Hydrate ntt-item -> Need DynamicClass "Product"
    -> Need JSON Schema -> Need network request
      -> Need NetworkAdapter -> Need Matrix initialized
        -> Need hydration complete -> Need DynamicClass (!!!)

WITH EMBEDDED SCHEMA (resolved):
  Parse <script data-ntt-schema="Product"> (local, ~5ms)
    -> Create DynamicClass via prototype() (no network)
      -> Initialize Matrix + register types (< 50ms)
        -> Hydrate ntt-item with existing DynamicClass
```

This is why Strategy A (schema injection) is the foundation for all subsequent SSR work. Without it, the hydration pipeline has no clean starting point.

| Strategy | PyBend Fit | TTI Impact | Risk |
|----------|-----------|------------|------|
| Full hydration | Poor | None | Low |
| Progressive hydration | Excellent | -40-60% | Low |
| Selective hydration | Good | -30-50% | Medium |
| Partial hydration | Medium | -20-40% | Low |
| Islands (DSD) | Excellent | -50-70% | Medium |
| **Progressive Islands (recommended)** | **Excellent** | **-60-80%** | **Medium** |

### Implementation Roadmap

```
Week 1: Strategy A (Data Injection) -- IMMEDIATE WIN
  [x] Add Jinja2 dependency to pyproject.toml
  [x] Create SSR route (new ssr.py or extend routes_fastapi.py)
  [x] Create base HTML template with schema/data injection slots
  [x] Wire into FastAPIBackend
  [x] Test: verify #consumePreloadedSchema eliminates SCHEMA fetch
  [x] Test: verify #consumePreloadedData eliminates READ fetch
  [x] Measure: FCP before vs after

Weeks 2-3: Python Form Renderer
  [ ] Port form.js:getInput() display branches to Python
  [ ] Port form.js:getHeader() to Python
  [ ] Port ntt-item:xs(), sm(), md() to Python template functions
  [ ] Add DSD <template shadowrootmode> wrapper generation
  [ ] Test: compare Python-rendered HTML vs JS-rendered HTML

Week 4: Hydration
  [ ] Add hydration detection to ntt-item.render() (~20 lines)
  [ ] Add hydration detection to ListElement.render()
  [ ] CSS extraction utility for DSD inline styles
  [ ] Test: SSR -> hydration -> edit mode -> save round-trip

Week 5: Per-User SSR + Caching
  [ ] Integrate ABAC resolver into SSR route
  [ ] Conditional button rendering based on user + resource
  [ ] Anonymous user caching strategy (CDN-friendly)
  [ ] Cache-Control headers (stale-while-revalidate)
```

### The Competitive Narrative

**PyBend's SSR story is not "we added SSR to a SPA framework." It is: "the server already knows everything about the UI. We simply have it render HTML directly instead of sending JSON and making the client do it."**

| Capability | Next.js 15 | Nuxt 3 | Astro 5 | PyBend (proposed) |
|-----------|-----------|--------|---------|-------------------|
| Zero-JS initial render | No (hydration required) | No | Yes (non-island) | **Yes (DSD)** |
| New model = new page | Write component + page | Write component + page | Write component + page | **Just register the model** |
| Form generation | Manual or library | Manual or library | Manual | **Schema-derived** |
| Permission-gated UI | Manual checks | Manual checks | Manual checks | **Declared on model, auto-enforced** |
| Build step required | Yes (Turbopack) | Yes (Vite) | Yes (Vite) | **No** |

*Sources: Research docs 04-our-stack-relevance.md (Sections 6, 10, 11), 05-hydration-strategies.md (Section 17), 02-technical-deep-dive.md (Section 10)*

---

## 8. 📊 Performance Benchmarks and Projections

### Current PyBend Performance Profile

Understanding exactly where time is spent in the current rendering pipeline is essential for measuring SSR impact. The current CSR waterfall breaks down as follows:

```
  0ms     50ms    200ms   400ms   800ms   1200ms  1600ms  2000ms
  |       |       |       |       |       |       |       |
  [HTML]  [JS modules load                ]
          [                               ]
          [                 Schema fetch   ]       (~100-200ms RTT)
          [                               [Data fetch        ]  (~100-200ms RTT)
          [                                        [Render   ]
                                                             ^ FCP (~1500-2000ms)
```

The two sequential network requests (schema, then data) account for approximately 400-600ms of the total delay. Module loading accounts for another 200-400ms. Component rendering (DynamicClass creation, `form.js` execution, Shadow DOM population) adds 100-200ms.

### Projected Performance with Strategy A

```
  0ms     50ms    200ms   400ms   800ms   1000ms
  |       |       |       |       |       |
  [HTML with embedded schema + data]
          [JS modules load                ]
          [Parse embedded schema + data   ]  (~10ms, local)
          [                   [Render     ]
                                          ^ FCP (~800-1000ms)
```

The sequential network requests are eliminated entirely. The remaining bottleneck is JavaScript module loading, which can be optimized through preload hints and module bundling.

### Projected Performance with Strategy A+B

```
  0ms     50ms    200ms   300ms   500ms   800ms
  |       |       |       |       |       |
  [HTML with DSD-rendered content ]
          ^ FCP (~200-300ms)
          [JS modules load (background)   ]
          [         Hydrate on interaction ]
                    ^ TTI for display (~300ms)
                                          ^ TTI for interactive (~800ms)
```

Content is visible before any JavaScript executes. The browser paints the server-rendered HTML (with Declarative Shadow DOM) immediately. JavaScript loads in the background and hydrates components progressively.

### Framework SSR Benchmark Context

These industry benchmarks provide context for what SSR achieves in other frameworks, measured on identical content:

| Framework | FCP | TTI | Approach |
|-----------|-----|-----|----------|
| Astro | 0.8s | 0.9s | Islands |
| SvelteKit | 0.9s | 1.0s | Selective hydration |
| Next.js | 0.9s | 1.2s | Full hydration / RSC |
| Nuxt.js | 1.1s | 1.4s | Full hydration |
| **PyBend (projected, Strategy A+B)** | **0.3-0.5s** | **0.8s** | **Progressive Islands** |

PyBend's projected performance compares favorably because:
1. No framework runtime overhead (vanilla JS vs React/Vue/Svelte)
2. No hydration of the full component tree (islands pattern)
3. Schema is pre-loaded (no initial network request for rendering spec)
4. Declarative Shadow DOM renders before any JS parses

*Source: Enterspeed benchmark data, 2024-2025; Research doc 02-technical-deep-dive.md (Section 7)*

### Python-Specific SSR Benchmarks

FastAPI + Jinja2 rendering produces favorable server-side performance characteristics:

| Metric | FastAPI + SSR | React CSR | Delta |
|--------|-------------|-----------|-------|
| FCP | 300-500ms | 1500-3000ms | **3-6x faster** |
| TTI | ~335ms | ~1620ms | **~5x faster** |
| Page weight | 50-100KB | 1.5-3MB | **15-30x smaller** |
| Server throughput | ~1,500 req/s/core | N/A (client) | Efficient |

Jinja2 template rendering adds minimal server overhead: microseconds for simple pages, low single-digit milliseconds for complex pages. Combined with PyBend's schema caching (`ProtoModel._schema_cache`), the rendering cost per request is dominated by the database query, not the HTML generation.

### Caching Strategy and Its Performance Impact

SSR performance at scale depends heavily on caching. PyBend's content profile supports aggressive caching:

| Content Type | Cache Strategy | TTL | Rationale |
|-------------|---------------|-----|-----------|
| Schema responses (`GET /Product`) | CDN + browser | 1 hour + SWR 24h | Schema changes only on deploy |
| List pages (anonymous) | CDN edge | 60s + SWR 5min | Stale-while-revalidate |
| Detail pages (anonymous) | CDN edge | 60s + SWR 5min | Entity changes infrequent |
| Personalized views (authenticated) | No shared cache | 0 | User-specific access rules |
| Static assets (JS/CSS) | CDN + browser | Immutable | Fingerprinted filenames |

For anonymous users (the SEO-relevant audience), cached responses serve from CDN edge with 20-50ms TTFB globally. This means the first visit from any geographic location benefits from near-instant delivery of server-rendered HTML.

### Measuring Success

If SSR is implemented, these metrics must be tracked:

| Metric | Baseline (measure now) | Target | Tool |
|--------|----------------------|--------|------|
| LCP (p75) | Measure current | < 2.5s | Lighthouse, CrUX |
| FCP (p75) | Measure current | < 1.8s (Strategy A), < 0.8s (Strategy B) | PageSpeed Insights |
| TTFB (p75) | ~50ms (static) | < 200ms (SSR) | Server logs, RUM |
| Server render time (p95) | N/A | < 500ms | Custom instrumentation |
| Hydration error rate | N/A | < 0.1% of page loads | Browser error tracking |
| Cache hit ratio | N/A | > 80% | CDN analytics |
| INP (p75) | Measure current | < 200ms | web-vitals library |

*Sources: Research docs 02-technical-deep-dive.md (Section 7), 03-decision-framework.md (Section 10), 01-industry-landscape.md (Section 3)*

---

## 9. 🛡️ Risk Register

### Risk 1: Server/Client Render Divergence

| Attribute | Value |
|-----------|-------|
| **Severity** | High |
| **Likelihood** | High (with Strategy B) |
| **Impact** | UI glitches, hydration errors, silent data corruption |
| **Description** | The Python server renderer and JavaScript client renderer produce different HTML for the same schema + data. This causes hydration mismatches -- the client detects the discrepancy and either re-renders from scratch (negating SSR benefits) or produces corrupted output. |
| **Mitigation** | 1. Schema-driven approach minimizes drift (both renderers read the same spec). 2. Automated parity tests comparing Python vs JS output for identical inputs. 3. Version hash in server-rendered HTML; client checks hash before hydrating. 4. If hash mismatches, client falls back to clean CSR re-render. |

### Risk 2: XSS in Server-Rendered Content

| Attribute | Value |
|-----------|-------|
| **Severity** | Critical |
| **Likelihood** | Medium |
| **Impact** | Stored XSS from any entity field, executing before any CSP or client sanitizer |
| **Description** | SSR templates interpolate entity data into HTML. If data contains malicious scripts and is not escaped, the server pre-injects the attack into the page. This is worse than client-side XSS because it executes before any JavaScript loads. |
| **Mitigation** | 1. Use `markupsafe.escape()` on ALL user data before HTML interpolation. 2. Jinja2 autoescape enabled by default. 3. Never use `| safe` filter on user-controlled data. 4. CSP headers with per-request nonces. 5. DSD-aware sanitization (strip `shadowrootmode` from user content). 6. Automated XSS regression tests in CI. |

### Risk 3: Performance Regression Under Load (SSR Stampede)

| Attribute | Value |
|-----------|-------|
| **Severity** | High |
| **Likelihood** | Medium |
| **Impact** | Site-wide outage; SSR is worse than CSR graceful degradation |
| **Description** | With CSR, traffic spikes affect the API server (JSON responses are cheap). With SSR, traffic spikes hit rendering servers, which do significantly more work per request. A viral page can cause cascading failures. CSR degrades gracefully; SSR fails catastrophically. |
| **Mitigation** | 1. Aggressive CDN caching with `stale-while-revalidate`. 2. Schema response caching (schema rarely changes). 3. Circuit breaker: fall back to CSR if SSR latency exceeds threshold. 4. Rate limiting on SSR endpoints. 5. Anonymous user responses cached at CDN edge. |

### Risk 4: Hydration "Uncanny Valley"

| Attribute | Value |
|-----------|-------|
| **Severity** | Medium |
| **Likelihood** | High (with Strategy B) |
| **Impact** | Users click buttons that do nothing; worse UX than a loading spinner |
| **Description** | SSR pages look ready before they are ready. Method buttons (Like, Favorite) look clickable but do nothing until the Actor is registered and the Matrix can route messages. Edit buttons toggle mode but require the full form generator to be loaded. |
| **Mitigation** | 1. Add `disabled` attributes and subtle loading indicators to interactive elements during SSR rendering. 2. Remove them as each component hydrates. 3. Root event delegation captures clicks during valley. 4. Progressive hydration prioritizes above-fold interactive elements. |

### Risk 5: Declarative Shadow DOM Browser Gaps

| Attribute | Value |
|-----------|-------|
| **Severity** | Medium |
| **Likelihood** | Low (94.38% global support) |
| **Impact** | ~6% of users see empty components until JS loads |
| **Description** | Browsers that do not support DSD will ignore `<template shadowrootmode="open">` and render nothing until JavaScript creates the shadow root. |
| **Mitigation** | 1. Lightweight DSD polyfill (~1KB) for unsupported browsers. 2. Graceful fallback: content still appears after JS loads (same as current CSR behavior). 3. Monitor user agent analytics for unsupported browser share. |

### Risk 6: Maintenance Burden of Dual Rendering Paths

| Attribute | Value |
|-----------|-------|
| **Severity** | Medium |
| **Likelihood** | Medium |
| **Impact** | Feature velocity reduction; every UI change must update two renderers |
| **Description** | Strategy B requires maintaining rendering logic in both Python (server) and JavaScript (client). Changes to `form.js` must be mirrored in the Python renderer. |
| **Mitigation** | 1. Schema-driven approach means both renderers read the same spec, reducing drift. 2. Automated parity tests catch divergence. 3. Server renderer covers only display mode; edit mode stays client-only. 4. Consider shared template format (tagged template literals) usable by both. |

### Risk 7: Per-User SSR Destroys Cache Efficiency

| Attribute | Value |
|-----------|-------|
| **Severity** | Medium |
| **Likelihood** | Medium |
| **Impact** | SSR responses cannot be cached at CDN; server load increases linearly with traffic |
| **Description** | Pages with permission-gated UI elements (edit/delete buttons visible to owners/admins only) produce different HTML per user. This makes responses non-cacheable at the CDN edge. |
| **Mitigation** | 1. Anonymous user responses (no JWT) are fully cacheable -- covers SEO and first-visit use cases. 2. Separate cacheable shell from user-specific elements. 3. Button visibility via CSS classes tied to a user role class on `<body>` (one HTML, per-role CSS rules). |

### Risk 8: Template Injection (SSTI)

| Attribute | Value |
|-----------|-------|
| **Severity** | Critical |
| **Likelihood** | Low |
| **Impact** | Server configuration leakage, remote code execution |
| **Description** | If user input is treated as template code (e.g., Jinja2 expressions), attackers can execute arbitrary Python on the server. |
| **Mitigation** | 1. PyBend's schema-driven approach naturally separates template structure (developer-defined) from data (user-provided). 2. Never construct `Template()` from user input. 3. User data is always interpolated as data values, never as template syntax. 4. Automated SSTI detection in security tests. |

### Risk 9: Streaming SSR Complexity

| Attribute | Value |
|-----------|-------|
| **Severity** | Low |
| **Likelihood** | Low (only if streaming is implemented) |
| **Impact** | Broken chunked responses, partial page renders, CSP nonce challenges |
| **Description** | Streaming SSR sends HTML in chunks. If a chunk fails mid-stream, the user sees a partial page. CSP nonces must be known before the first byte. Error handling is more complex than standard responses. |
| **Mitigation** | 1. Streaming is Phase 4 of the roadmap -- implement only after basic SSR is stable. 2. Generate CSP nonce in middleware before streaming starts. 3. Error boundary: if rendering fails mid-stream, inject an error message and close the response gracefully. |

*Sources: Research docs 02-technical-deep-dive.md (Section 6), 05-hydration-strategies.md (Sections 14-15), 03-decision-framework.md (Section 7)*

---

## 9. 📎 Appendices

### Appendix A: Hydration Strategy Deep Comparison

| Strategy | What Gets Hydrated | When | JS at Load | FCP-TTI Gap | Complexity |
|----------|-------------------|------|------------|-------------|------------|
| **Full Hydration** | Everything | All at once, after JS download | 100% | 1-2.5s | Low |
| **Progressive** | Everything (eventually) | Prioritized: visible first, off-screen on scroll | ~40% initially | ~700ms | Medium |
| **Selective** | Everything (eventually) | Priority-based: user interaction jumps queue | 100% (streaming) | ~500ms | Medium-High |
| **Partial** | Only interactive parts | Only when component has event handlers | 15-40% | ~400ms | Medium |
| **Islands** | Only island components | Per-island, independent timing | 15-30% | ~400ms | Medium |
| **Resumability** | Nothing (serialize instead) | On interaction (lazy-load handler) | ~1KB | ~0ms | High |
| **Progressive Islands (recommended)** | Island components, prioritized | Viewport + interaction triggers | ~10-20% initially | ~200ms | Medium-High |

### Appendix B: PyBend File Reference

| File | Role | SSR-Relevant Lines |
|------|------|-------------------|
| `/workspace/src/pybend/static/core/NTT.js` | Entity system, DynamicClass factory, SSR pre-loading | 244-277 (pre-loading), 390-426 (SCHEMA), 663+ (prototype) |
| `/workspace/src/pybend/static/generators/form.js` | Schema-driven form HTML generation | 17-65 (getForm), 173+ (getInput), 159-171 (validationAttrs) |
| `/workspace/src/pybend/static/components/ntt-item.js` | Entity rendering at all sizes | 143-146 (xs), 156-282 (sm), 284-318 (md), 468-486 (render) |
| `/workspace/src/pybend/static/components/ntt-list.js` | Collection component | 1-19 |
| `/workspace/src/pybend/static/components/NTTElement.js` | Single entity base | 32-41 (value setter), 78-95 (DESCRIBE) |
| `/workspace/src/pybend/static/core/Matrix.js` | Actor message bus | 26-48 (inbox routing) |
| `/workspace/src/pybend/core/models/proto_model.py` | Base model, schema generation | 117-137 (model_dump), 199-316 (schema) |
| `/workspace/src/pybend/core/api/routes_fastapi.py` | Route factories, auth injection | 20-32 (user/context), 92-137 (list), 168-180 (schema) |
| `/workspace/src/pybend/core/api/backend.py` | FastAPI backend setup | 48-168 (FastAPIBackend) |

### Appendix C: Sources

**Industry Data:**
1. [State of JS 2024 Survey](https://2024.stateofjs.com/en-US) -- Framework usage and satisfaction
2. [web.dev: Business Impact of Core Web Vitals](https://web.dev/case-studies/vitals-business-impact) -- Conversion case studies
3. [web.dev: Tokopedia Case Study](https://web.dev/case-studies/tokopedia) -- 55% LCP improvement
4. [web.dev: Rakuten 24 Case Study](https://web.dev/case-studies/rakuten) -- +53% revenue/visitor
5. [Netflix Web Performance Case Study](https://medium.com/dev-channel/a-netflix-web-performance-case-study-c0bcde26a9d9) -- 50% load time reduction
6. [Yelp Engineering: SSR at Scale](https://engineeringblog.yelp.com/2022/02/server-side-rendering-at-scale.html) -- 1/3 compute costs
7. [Shopify Engineering: Hydrogen Storefronts](https://shopify.engineering/high-performance-hydrogen-powered-storefronts) -- Streaming SSR
8. [Market Growth Reports: Web Frameworks Market](https://www.marketgrowthreports.com/market-reports/web-frameworks-software-market-119949) -- $959M-$1.92B projection
9. [npm trends: Framework downloads](https://npmtrends.com/astro-vs-next-vs-nuxt-vs-remix-vs-svelte)
10. [Google Search Central: Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals) -- SEO ranking signal

**Technical References:**
11. [Declarative Shadow DOM](https://web.dev/articles/declarative-shadow-dom) -- Browser standard for SSR Web Components
12. [CanIUse: Declarative Shadow DOM](https://caniuse.com/declarative-shadow-dom) -- 94.38% global support
13. [Lit SSR Documentation](https://lit.dev/docs/ssr/overview/) -- Web Components SSR approach
14. [Stencil SSR](https://stenciljs.com/docs/server-side-rendering) -- Compiler-driven WC SSR
15. [fasthx: FastAPI SSR Library](https://github.com/volfpeter/fasthx) -- Python-native SSR for FastAPI
16. [Builder.io: Resumability vs Hydration](https://www.builder.io/blog/resumability-vs-hydration) -- Qwik architecture
17. [patterns.dev: Islands Architecture](https://www.patterns.dev/vanilla/islands-architecture/)
18. [Enhance: Island Architecture with Web Components](https://enhance.dev/blog/posts/2024-07-09-island-architecture-with-web-components)
19. [Angular Hydration Documentation](https://angular.dev/guide/hydration) -- Event replay
20. [web.dev: Rendering on the Web](https://web.dev/articles/rendering-on-the-web) -- FCP/TTI gap data

**Decision Framework:**
21. [Vercel: Choosing Rendering Strategy](https://vercel.com/blog/how-to-choose-the-best-rendering-strategy-for-your-app)
22. [Shopify: SSR vs CSR](https://www.shopify.com/blog/ssr-vs-csr) -- E-commerce perspective
23. [Google: Mobile Performance Impact](https://www.thinkwithgoogle.com/marketing-strategies/app-and-mobile/mobile-page-speed-conversion-data/)
24. [Enterspeed: JS Framework SSR Benchmarks](https://www.enterspeed.com/blog/we-measured-the-ssr-performance-of-6-js-frameworks-heres-what-we-found)
25. [The Spicy Web: WC SSR Comparison](https://www.spicyweb.dev/web-components-ssr-node/)

**Research Documents (internal):**
- `/workspace/.traces/research/ssr/01-industry-landscape.md`
- `/workspace/.traces/research/ssr/02-technical-deep-dive.md`
- `/workspace/.traces/research/ssr/03-decision-framework.md`
- `/workspace/.traces/research/ssr/04-our-stack-relevance.md`
- `/workspace/.traces/research/ssr/05-hydration-strategies.md`

### Appendix D: Glossary

| Term | Definition |
|------|-----------|
| **CSR** | Client-Side Rendering. The browser downloads JS, fetches data, and renders HTML. PyBend's current model. |
| **SSR** | Server-Side Rendering. The server generates complete HTML and sends it to the browser. |
| **SSG** | Static Site Generation. HTML is pre-built at deploy time, served from CDN. |
| **ISR** | Incremental Static Regeneration. SSG with background revalidation on a timer. |
| **DSD** | Declarative Shadow DOM. HTML syntax (`<template shadowrootmode="open">`) that browsers parse into shadow roots without JavaScript. |
| **FCP** | First Contentful Paint. When the user first sees meaningful content. |
| **TTI** | Time to Interactive. When the page reliably responds to user input. |
| **LCP** | Largest Contentful Paint. When the largest visible element renders. Google ranking signal. |
| **INP** | Interaction to Next Paint. Responsiveness after page load. Google ranking signal. |
| **TTFB** | Time to First Byte. When the browser receives the first byte of the response. |
| **DynamicClass** | Runtime-generated NTT subclass created by `prototype()` from a JSON Schema. |
| **Matrix** | PyBend's actor message bus. Routes TX messages between actors. |
| **Strategy A** | Schema + data injection: server embeds JSON in HTML, client renders from local data. |
| **Strategy B** | Pre-rendered HTML with DSD: server renders full HTML, client hydrates for interactivity. |
| **Strategy C** | HTMX-enhanced rendering: server returns HTML fragments, HTMX handles partial updates. |
| **Islands Architecture** | Static HTML page with isolated interactive "islands" that hydrate independently. |
| **Hydration** | Attaching JavaScript event handlers to server-rendered HTML to make it interactive. |
| **Resumability** | Qwik's approach: serialize state into HTML, lazy-load handlers on interaction, skip hydration. |

---

*Report prepared February 2026. Performance benchmarks reflect published data from 2024-2026. Specific numbers vary by hardware, network conditions, and application complexity. All business outcome figures are as reported by cited sources.*
