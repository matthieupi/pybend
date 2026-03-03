# PyBend Frontend Performance Audit

**Date**: 2026-03-02
**Branch**: v0.8
**Tools**: Lighthouse (Puppeteer), Playwright CDP, Static Code Analysis
**Target**: `http://localhost:5000/matrix.html`

## Lighthouse Score: 59/100

| Metric | Value | Score |
|--------|-------|-------|
| First Contentful Paint | 0.3s | 1.0 |
| **Largest Contentful Paint** | **5.5s** | **0.06** |
| **Total Blocking Time** | **360ms** | **0.48** |
| Cumulative Layout Shift | 0.023 | 1.0 |
| Speed Index | 1.5s | 0.82 |
| **Time to Interactive** | **5.5s** | **0.33** |

FCP is fast (0.3s) — HTML shell loads quickly thanks to modulepreloads. But **LCP at 5.5s and TTI at 5.5s** are the killers.

## Runtime Metrics (Playwright CDP)

| Metric | Value | Assessment |
|--------|-------|------------|
| Total requests | **57** | High (28 scripts, 8 stylesheets, 14 images) |
| Page load (networkidle) | **2067ms** | Moderate |
| **DOM Nodes** | **224,396** | Extreme (28x recommended max of ~8,000) |
| **JS Event Listeners** | **1,555** | Very high |
| Layout Duration | 160ms | High |
| Style Recalc Duration | 111ms | High |
| Script Duration | 780ms | High |
| Total Task Duration | 1264ms | High |
| JS Heap Used | 2.73MB | Acceptable |
| Long Tasks (>50ms) | **4 tasks totaling 857ms** | Critical |

## Main Thread Breakdown

| Category | Time |
|----------|------|
| **Script Evaluation** | **582ms** |
| Other | 371ms |
| **Style & Layout** | **194ms** |
| Rendering | 136ms |
| Parse HTML & CSS | 105ms |

### Top Script Bootup Times

| File | Total | Scripting |
|------|-------|-----------|
| **Component.js** | **496ms** | **322ms** |
| **ntt-logs.js** | **204ms** | **179ms** |
| ntt-router.js | 78ms | 78ms |

## Long Tasks Causing Jank

4 long tasks block the main thread for **857ms total**:

```
[185ms → 395ms]  210ms  Schema fetch + DynamicClass creation (prototype())
[396ms → 663ms]  267ms  Entity render: ntt-list → 20× ntt-item innerHTML
[673ms → 878ms]  205ms  Nested entity population (comments, likes via depth=2)
[917ms → 1092ms] 175ms  External image loads + layout shifts
```

## Total Payload: 487 KiB

| Resource | Size | Notes |
|----------|------|-------|
| Inter font (woff2) | 47.3KB | External Google Fonts |
| `products?depth=2` | 40.0KB | Populated data — biggest API response |
| **NTT.js** | **39.9KB** | Unminified — biggest JS file |
| JetBrains Mono font | 30.6KB | External Google Fonts |
| ntt-item.js | 25.7KB | Unminified |
| **ntt-item.css** | **20.7KB** | 19KB unused per Lighthouse |
| form.js | 15.7KB | Unminified |
| ntt-logs.js | 15.6KB | 179ms scripting — dev tool loaded in prod |

### Minification Savings (Lighthouse estimate)

- **JS**: ~78KB (NTT.js, ntt-item.js, Actor.js, Component.js, form.js)
- **CSS**: ~14KB (ntt-item.css, ntt-topbar.css, dark-theme.css)
- **Total**: ~92KB

---

## Top 8 Bottlenecks (Prioritized)

### 1. CRITICAL — Unminified JS/CSS (78KB JS + 14KB CSS savings)

All JS and CSS is served raw. No bundling, no minification, no tree-shaking. 28 individual script requests, 8 stylesheet requests.

- **Location**: All files in `src/pybend/static/`
- **Fix**: Add esbuild bundler (SSR module already has esbuild). Bundle all JS into 1-2 files, minify CSS.
- **Expected impact**: -92KB transfer, -100ms parse time

### 2. CRITICAL — 224K DOM Nodes from Shadow DOM + Populated Data

Each ntt-item creates a full shadow DOM tree with CSS link, forms, buttons, nested comment components. With `depth=2` data, a single Product card can spawn Comment and Like sub-components.

- **Location**: `Component.js:86-92` (shadow DOM init), `ntt-item.js:484-486` (innerHTML full replacement)
- **Fix**: Use `depth=0` for list views, only `depth=2` for detail. Virtual scrolling for visible items only.
- **Expected impact**: 10x reduction in DOM nodes, -500ms layout time

### 3. HIGH — CSS Parsed 20x (once per shadow root)

Every ntt-item creates a `<link>` to ntt-item.css in its shadow root. Browser caches the file but parses the stylesheet 20 separate times.

- **Location**: `Component.js:86-92`
- **Fix**: Constructable Stylesheets (`new CSSStyleSheet()` + `adoptedStyleSheets`). Parse once, share.
- **Expected impact**: 80-90% reduction in CSS parse time (~100ms saved)

### 4. HIGH — Component.js 496ms Boot Time

Dominates script execution at 496ms. Sets up ResizeObserver, shadow DOM, Observable subscriptions for every component. ResizeObserver causes layout thrashing on resize.

- **Location**: `Component.js:318-336`
- **Fix**: Batch ResizeObserver reads, defer writes to next rAF. Lazy-init when in viewport.
- **Expected impact**: 30-50% reduction in Component.js init time

### 5. HIGH — No Request Deduplication

Two components referencing the same entity fire two identical GET requests. No in-flight request tracking.

- **Location**: `NetworkAdapter.js:110-143`
- **Fix**: `#pending = new Map()` keyed by URL; return same Promise for concurrent requests.
- **Expected impact**: 50-70% fewer network requests on entity-heavy pages

### 6. MEDIUM — DynamicClass.instances Never Evicted (Memory Leak)

Every entity ever fetched stays in `DynamicClass.instances` forever. Browse 1000 products = 2-5MB retained.

- **Location**: `NTT.js:681`
- **Fix**: LRU eviction when `instances.size > 500`, or `dispose()` from `disconnectedCallback()`
- **Expected impact**: Caps memory at ~1-2MB

### 7. MEDIUM — Matrix.children Never Cleaned Up

Components register with Matrix but never unregister on disconnect. Dead references accumulate.

- **Location**: `Actor.js:25,158`
- **Fix**: Add `unregister()` method, call from `disconnectedCallback()`
- **Expected impact**: Prevents unbounded Actor reference growth

### 8. MEDIUM — ntt-logs.js Costs 204ms Despite Being a Dev Tool

15.6KB, 179ms scripting. Loaded unconditionally in matrix.html.

- **Location**: `ntt-logs.js`
- **Fix**: Lazy-load behind debug flag, or exclude from production builds
- **Expected impact**: -179ms scripting, -15.6KB transfer

---

## Quick Wins (Implement First)

1. **Bundle + minify** with esbuild (-92KB, -100ms parse)
2. **Constructable Stylesheets** (~20 lines in Component.js, -100ms)
3. **Use `depth=0`** for list views (reduce 40KB API response to ~6KB)
4. **Lazy-load ntt-logs.js** behind a flag (-179ms, -15.6KB)
5. **Request dedup** in NetworkAdapter (~30 lines of code)

These 5 changes should improve Lighthouse from 59 to ~80-85 and cut TTI from 5.5s to ~2s.

---

## Source Data

- `lighthouse.txt` — Full Lighthouse report
- `playwright.txt` — Full Playwright CDP profiling (8 phases)
- `static-analysis.txt` — 26-issue code analysis with severity ratings

## Issue Cross-Reference

| # | Severity | Area | File | Description |
|---|----------|------|------|-------------|
| 1 | HIGH | DOM | ntt-item.js:484 | innerHTML full replacement on every render |
| 2 | MEDIUM | DOM | ListElement.js:235 | ListElement batches but NTTItem doesn't |
| 3 | LOW | DOM | form.js:55 | HTML string concatenation in getForm() |
| 4 | MEDIUM | DOM | Component.js:318 | Layout thrashing in ResizeObserver |
| 5 | NONE | Events | ntt-item.js:499 | AbortController used correctly |
| 6 | NONE | Events | Component.js:385 | disconnectedCallback cleans up properly |
| 7 | LOW | Events | Component.js:338 | ResizeObserver edge case on DOM move |
| 8 | MEDIUM | Events | ntt-item.js:508 | No event delegation (per-item listeners) |
| 9 | HIGH | Network | NetworkAdapter.js:110 | No request deduplication |
| 10 | NONE | Network | NTT.js:399 | $defs handling is correct |
| 11 | MEDIUM | Network | ListElement.js:64 | Pagination meta overwritten |
| 12 | MEDIUM | Network | HTTP.js | No HTTP response caching |
| 13 | HIGH | Render | NTT.js:671 | prototype() re-runs on every schema fetch |
| 14 | MEDIUM | Render | form.js:4 | Layout cache grows unbounded |
| 15 | LOW | Render | form.js:28 | Permission checks on cache miss |
| 17 | MEDIUM | Memory | NTT.js:681 | instances Map never evicted |
| 18 | MEDIUM | Memory | Observable.js:44 | Signal closures can retain dead components |
| 19 | MEDIUM | Memory | Actor.js:25 | Matrix children never cleaned up |
| 20 | HIGH | Assets | Component.js:86 | CSS parsed per shadow root instance |
| 21 | NONE | Assets | matrix.html:16 | Modulepreload correctly implemented |
| 22 | LOW | Assets | matrix.html:11 | CSS preload unused until shadow DOM |
| 23 | NONE | Schema | NTT.js:732 | defineProperty is already optimal |
| 24 | MEDIUM | Schema | NTT.js:622 | normalizePopulated scales with depth |
| 25 | NONE | Actor | Matrix.js:26 | Profiling overhead is opt-in |
| 26 | LOW | Actor | Matrix.js | No message queue throttling |
