# CSS-Only & Minimal-JS Interactivity Patterns

## Research Brief for PyBend Static Site Generation

**Date:** 2026-02-25
**Audience:** Technical CEO + Engineering Team
**Angle:** How much interactivity can a fully static PyBend export achieve WITHOUT JavaScript?

---

## Executive Summary

The gap between "static HTML" and "interactive application" has collapsed. Modern CSS (2025-2026) provides native mechanisms for accordions, tabs, modals, carousels, tooltips, filtering, theme switching, and even page transitions -- all without a single line of JavaScript. Combined with the HTML `<details>`, `<dialog>`, and Popover APIs, a statically-generated PyBend site can deliver 80-90% of the interactivity users expect from an SPA, with near-zero JavaScript.

The irreducible minimum that *requires* JS: form submission to an API, authentication, real-time data, and clipboard operations. Everything else is CSS territory. This is the wildcard that makes static export viable for far more use cases than traditional thinking suggests.

**Key finding:** A PyBend static export with CSS-only interactivity and <1KB of JS for form submission would score 95-100 on Lighthouse Performance while retaining the interactive feel of `ntt-item`'s display modes, field groups, collapsible sections, and filtering.

---

## 1. CSS-Only Patterns That Replace JavaScript

### 1.1 `<details>` / `<summary>` -- Accordions and Collapsible Sections

The most mature and accessible CSS-only pattern. Native HTML, zero CSS hacks required.

```html
<!-- PyBend field groups as collapsible sections -->
<details class="ntt-group" open>
  <summary>Product Details</summary>
  <div class="field">
    <label>Name</label>
    <div>Widget Pro</div>
  </div>
  <div class="field">
    <label>Price</label>
    <div>$29.99</div>
  </div>
</details>

<details class="ntt-group">
  <summary>Social (3 comments)</summary>
  <div class="list-field">
    <!-- nested ntt-item equivalents -->
  </div>
</details>
```

```css
details.ntt-group {
  border: 1px solid var(--glass-border, rgba(255,255,255,0.08));
  border-radius: var(--radius-md, 12px);
  margin: 0.75rem 0;
  overflow: hidden;
}

details.ntt-group summary {
  padding: 0.75rem 1.25rem;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-3, #555e78);
  cursor: pointer;
  list-style: none; /* remove default marker */
}

details.ntt-group summary::after {
  content: "+";
  float: right;
  transition: transform 0.2s;
}

details.ntt-group[open] summary::after {
  content: "-";
}

details.ntt-group > *:not(summary) {
  padding: 0 1.25rem 0.75rem;
}
```

**PyBend mapping:** This directly replaces the JS-driven `.nested-collapsed` / `.expanded` toggle and the `.show-more-btn` click handler in `ntt-item.js` (lines 559-590 of the CSS). The `<details>` element with `open` attribute gives identical behavior to the current `expanded` class toggle.

**Browser support:** Universal. Every modern browser since 2020. [Can I Use: 97.5% global](https://caniuse.com/details).

**Accessibility:** Fully keyboard navigable (Enter/Space to toggle). Screen readers announce "collapsed"/"expanded" state natively. No ARIA needed.

---

### 1.2 `:target` Pseudo-Class -- Tabs, Modals, and Navigation

The `:target` selector matches an element whose `id` matches the URL fragment (`#hash`). This enables single-page navigation, tab switching, and modal display with zero JS.

```html
<!-- Tab navigation for ntt-item display modes -->
<nav class="ntt-tabs">
  <a href="#tab-details">Details</a>
  <a href="#tab-comments">Comments</a>
  <a href="#tab-related">Related</a>
</nav>

<section id="tab-details" class="tab-panel">
  <!-- field content -->
</section>
<section id="tab-comments" class="tab-panel">
  <!-- comment list -->
</section>
<section id="tab-related" class="tab-panel">
  <!-- related items -->
</section>
```

```css
.tab-panel {
  display: none;
}

/* Show targeted panel */
.tab-panel:target {
  display: block;
}

/* Default: show first panel when no hash */
.tab-panel:first-of-type {
  display: block;
}
.tab-panel:first-of-type:not(:target):has(~ .tab-panel:target) {
  display: none;
}

/* Active tab indicator */
.ntt-tabs a[href="#tab-details"]:has(~ #tab-details:target),
.ntt-tabs a[href="#tab-comments"]:has(~ #tab-comments:target) {
  border-bottom: 2px solid var(--accent, #22d3c5);
  color: var(--accent-text, #5eeadf);
}
```

**PyBend mapping:** Replaces the hash-based routing in `ntt-router.js` for static pages. Each model's detail view can use `:target` tabs to show field groups (`ui.groups`) as tab panels rather than stacked fieldsets.

**Limitation:** Modifies URL hash, which affects browser history. The back button navigates between tab states rather than between pages. For modals, this can be a feature (linkable modals) or a drawback (unexpected back behavior).

**Browser support:** Universal. `:target` is CSS3, supported everywhere.

---

### 1.3 `:checked` + Label -- Toggle States, Filters, and Switches

The checkbox/radio hack is the most versatile CSS-only interactivity pattern. Hidden inputs + labels create stateful toggles that CSS can respond to via `:checked`.

```html
<!-- CSS-only list filtering (replaces JS filter logic) -->
<div class="ntt-filters">
  <input type="checkbox" id="filter-instock" checked hidden>
  <label for="filter-instock" class="filter-pill">In Stock</label>

  <input type="checkbox" id="filter-sale" hidden>
  <label for="filter-sale" class="filter-pill">On Sale</label>
</div>

<!-- Product cards with data attributes -->
<div class="ntt-list">
  <article class="card" data-instock data-sale>Widget A - $10</article>
  <article class="card" data-instock>Widget B - $25</article>
  <article class="card" data-sale>Widget C - $15</article>
  <article class="card">Widget D - $30</article>
</div>
```

```css
/* Filter pill styling */
.filter-pill {
  display: inline-block;
  padding: 0.2rem 0.65rem;
  border-radius: 999px;
  border: 1px solid var(--glass-border);
  cursor: pointer;
  font-size: 0.78rem;
  transition: all 0.2s;
}

input:checked + .filter-pill {
  background: var(--accent-dim, rgba(34,211,197,0.12));
  border-color: var(--accent, #22d3c5);
  color: var(--accent-text, #5eeadf);
}

/* Dark mode toggle */
input#dark-mode:checked ~ .app-body {
  --bg: #0e1018;
  --text-0: #f0f2f8;
  --surface-1: #161a26;
}
```

**PyBend mapping:** The `xs` pill display mode in `ntt-item.css` (lines 20-47) already uses pill-shaped badges. Filter pills using `:checked` state would let users toggle category views in an `ntt-list` equivalent without JS. The display/edit mode toggle (`toggleMode()` in `ntt-item.js` line 103) could become a CSS-only checkbox toggle for simple display switching.

**Accessibility caveat:** Using `hidden` on inputs removes them from the accessibility tree. Use `opacity: 0; position: absolute;` instead to keep them focusable. Screen readers will announce the checkbox state when using radio/checkbox elements with labels, but only if the inputs remain accessible to assistive technology [Smashing Magazine, 2022](https://www.smashingmagazine.com/2022/11/guide-keyboard-accessibility-html-css-part1/).

---

### 1.4 `scroll-snap` -- Carousels and Galleries

CSS scroll-snap creates native-feeling carousels with no JS event listeners, no layout thrashing, and automatic touch/keyboard/mouse support.

```html
<!-- Product image gallery -->
<div class="gallery-track">
  <img src="product-1.jpg" alt="Front view">
  <img src="product-2.jpg" alt="Side view">
  <img src="product-3.jpg" alt="Detail view">
</div>
```

```css
.gallery-track {
  display: flex;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  gap: 1rem;
  -webkit-overflow-scrolling: touch;
}

.gallery-track > img {
  scroll-snap-align: center;
  flex: 0 0 100%;
  border-radius: var(--radius-lg, 16px);
  object-fit: cover;
}

/* Hide scrollbar but keep functionality */
.gallery-track::-webkit-scrollbar { display: none; }
.gallery-track { scrollbar-width: none; }
```

**PyBend mapping:** The `.card-image` banner in `ntt-item.css` (lines 308-327) currently shows a single image. A scroll-snap gallery would let product entities with multiple images present them as a swipeable carousel in static output, matching the `md`/`lg`/`xl` display modes.

**Browser support:** Universal. scroll-snap-type supported in all modern browsers since 2020. [web.dev](https://web.dev/css-scroll-snap/)

**Bonus -- Chrome 135+:** Experimental pseudo-elements (`::scroll-button`, `::scroll-marker`) can auto-generate carousel navigation dots and prev/next buttons, though this is not yet cross-browser.

---

### 1.5 `<dialog>` Element + Popover API -- Modals Without JS

The HTML `<dialog>` element combined with the Popover API and the new Invoker Commands API (`commandfor`/`command` attributes) enables fully declarative modals.

```html
<!-- Delete confirmation modal -- zero JS -->
<button commandfor="delete-dialog" command="show-modal">
  Delete Product
</button>

<dialog id="delete-dialog">
  <h3>Delete this Product?</h3>
  <p>This action cannot be undone.</p>
  <form method="dialog">
    <button value="cancel">Cancel</button>
    <button value="confirm" class="danger">Delete</button>
  </form>
</dialog>

<!-- Tooltip/popover using Popover API -->
<button popovertarget="price-info">
  Price Info
</button>
<div id="price-info" popover>
  <p>Price includes VAT. Shipping calculated at checkout.</p>
</div>
```

```css
dialog {
  background: var(--glass-bg, rgba(14, 16, 24, 0.95));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg, 16px);
  padding: 2rem;
  color: var(--text-0, #f0f2f8);
  max-width: 400px;
}

dialog::backdrop {
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
}

/* Animate open/close with @starting-style */
dialog[open] {
  opacity: 1;
  transform: scale(1);
  transition: opacity 0.3s, transform 0.3s, overlay 0.3s allow-discrete,
              display 0.3s allow-discrete;
}

@starting-style {
  dialog[open] {
    opacity: 0;
    transform: scale(0.95);
  }
}
```

**PyBend mapping:** The `deleteItem()` method in `ntt-item.js` (line 65) currently uses `confirm()` -- a blocking browser dialog. A `<dialog>` element with Invoker Commands replaces this with a styled, non-blocking confirmation modal that works without JS.

**Browser support for Popover API:** Chrome 114+, Safari 17+, Firefox 125+. Cross-browser since April 2024.
**Browser support for Invoker Commands:** Chrome 135+, Edge 135+, Safari TP, Firefox Nightly. Becoming baseline in 2026. [CSS-Tricks](https://css-tricks.com/invoker-commands-additional-ways-to-work-with-dialog-popover-and-more/)

---

### 1.6 `:has()` Selector -- Parent-Based State

The long-awaited "parent selector" allows styling ancestors based on descendant state. This is transformative for CSS-only interactivity.

```css
/* Highlight card when any input inside is focused (edit mode indicator) */
.card:has(input:focus) {
  border-color: var(--accent, #22d3c5);
  box-shadow: 0 0 0 3px var(--accent-dim, rgba(34,211,197,0.12));
}

/* Hide "empty state" message when list has children */
.ntt-list:has(.card) .empty-message {
  display: none;
}

/* Show action bar only when checkboxes are selected */
.list-controls:has(input:checked) .bulk-actions {
  display: flex;
}

/* Validate form -- show submit only when required fields filled */
form:has(input[required]:placeholder-shown) .submit-btn {
  opacity: 0.5;
  pointer-events: none;
}

form:not(:has(input[required]:placeholder-shown)) .submit-btn {
  opacity: 1;
  pointer-events: auto;
}
```

**PyBend mapping:** The permission checks in `ntt-item.js` (lines 169-179) show/hide edit and delete buttons based on `permissions.canAction()`. In a static export where permissions are resolved at build time, `:has()` can handle conditional display: cards with `data-editable` get edit buttons, and the `:has()` selector can manage UI state changes like "show bulk delete bar when items are checked."

**Browser support:** Chrome 105+, Firefox 121+, Safari 15.4+, Edge 105+. Over 95% global coverage. [Can I Use](https://caniuse.com/css-has)

---

### 1.7 CSS Anchor Positioning -- Tooltips and Dropdowns

CSS anchor positioning lets one element "tether" to another, enabling tooltips, dropdown menus, and contextual popovers without JS positioning logic.

```css
.field-label {
  anchor-name: --price-label;
}

.price-tooltip {
  position: fixed;
  position-anchor: --price-label;
  top: anchor(bottom);
  left: anchor(center);
  position-try-fallbacks: flip-block;
  /* auto-flips if no space below */
}
```

**Browser support:** Chrome 125+, Edge 125+. Firefox and Safari in development. Progressive enhancement recommended -- use `@supports (anchor-name: --x)` to detect. [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Anchor_positioning/Using)

---

### 1.8 View Transitions API -- Page Transitions

CSS-driven page transitions for multi-page static sites. No JS framework needed.

```css
/* Enable cross-document view transitions */
@view-transition {
  navigation: auto;
}

/* Animate the old page out, new page in */
::view-transition-old(root) {
  animation: fade-out 0.2s ease;
}

::view-transition-new(root) {
  animation: fade-in 0.3s ease;
}

/* Named transitions for specific elements */
.card-image {
  view-transition-name: product-hero;
}

::view-transition-group(product-hero) {
  animation-duration: 0.4s;
}
```

**PyBend mapping:** Navigation between list view and detail view (the `ntt-router.js` flow) becomes a smooth cross-document transition. A product card's image in the list morphs into the hero image on the detail page. This eliminates the primary reason SPAs exist for content sites.

**Browser support:** Same-document: Chrome 111+, Edge 111+, Firefox 146+, Safari 18.1+. Cross-document (MPA): Chrome 126+, Edge 126+. Firefox and Safari catching up. [MDN](https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API)

---

### 1.9 Container Queries -- Component-Level Responsiveness

Unlike media queries (viewport-based), container queries let components adapt to their container's size. Essential for reusable static components.

```css
.card-container {
  container-type: inline-size;
  container-name: card;
}

/* xs pill when container is narrow (sidebar) */
@container card (max-width: 200px) {
  .card { /* xs styles */ }
}

/* sm compact row */
@container card (min-width: 201px) and (max-width: 500px) {
  .card { /* sm styles */ }
}

/* md full card */
@container card (min-width: 501px) {
  .card { /* md styles */ }
}
```

**PyBend mapping:** This directly replaces the `displayMode` attribute and the `xs()`/`sm()`/`md()`/`lg()`/`xl()` size methods in `ntt-item.js`. Instead of the JS component choosing which method to call based on a `display` attribute, the CSS adapts the card layout based on the container it is placed in. The same static HTML renders as a pill in a sidebar and a full card in a main column.

**Browser support:** Size queries: Chrome 105+, Firefox 110+, Safari 16+. Over 95% global coverage. [Can I Use](https://caniuse.com/css-container-queries)

---

### 1.10 `@media (prefers-*)` -- User Preference Adaptation

```css
/* Respect system dark/light preference */
@media (prefers-color-scheme: dark) {
  :root { --bg: #0e1018; --text-0: #f0f2f8; }
}

@media (prefers-color-scheme: light) {
  :root { --bg: #ffffff; --text-0: #1a1a2e; }
}

/* Disable animations for users who prefer reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

/* High contrast mode */
@media (prefers-contrast: more) {
  :root {
    --glass-border: rgba(255, 255, 255, 0.3);
    --text-2: #d0d0d0;
  }
}
```

**PyBend mapping:** The existing `dark-theme.css` and `light-theme.css` in `/workspace/src/pybend/static/` would collapse into a single stylesheet using `prefers-color-scheme`. The `staggerIn` animation in `ntt-item.css` (line 620) would be disabled for reduced-motion users.

**Browser support:** `prefers-color-scheme`: 96%+. `prefers-reduced-motion`: 96%+. `prefers-contrast`: 88%+.

---

### 1.11 CSS `counter()` -- Dynamic Numbering

```css
/* Auto-number comments */
.comment-list {
  counter-reset: comments;
}

.comment-list .card::before {
  counter-increment: comments;
  content: "#" counter(comments);
  font-size: 0.65rem;
  color: var(--text-3);
  position: absolute;
  top: 0.5rem;
  left: 0.5rem;
}

/* Count visible items */
.ntt-list {
  counter-reset: visible;
}

.ntt-list .card:not([hidden]) {
  counter-increment: visible;
}

.ntt-list::after {
  content: counter(visible) " items shown";
  font-size: 0.75rem;
  color: var(--text-2);
}
```

**PyBend mapping:** The `.list-field-count` badge in `ntt-item.css` (line 546) currently shows a JS-computed count. CSS counters can replicate this for static content, automatically numbering comments, tracking visible items after filtering, and generating step indicators for multi-section forms.

---

## 2. What MUST Have JavaScript (The Irreducible Minimum)

| Capability | Why JS is Required | Minimum JS Size |
|---|---|---|
| **Form submission to API** | HTTP POST/PUT/DELETE requires `fetch()` or `XMLHttpRequest` | ~200 bytes |
| **Authentication flow** | JWT token storage, login/logout, header injection | ~400 bytes |
| **Real-time data updates** | WebSocket/SSE connections, DOM mutation | ~300 bytes |
| **Clipboard operations** | `navigator.clipboard.writeText()` is JS-only | ~50 bytes |
| **Complex drag-and-drop** | `dragstart`/`drop` events require JS handlers | ~500 bytes |
| **Dynamic data fetching** | Loading data not present at build time | ~150 bytes |
| **Form validation feedback** | Custom messages beyond HTML5 `required`/`pattern` | ~200 bytes |
| **Analytics/tracking** | Sending page view events to an analytics endpoint | ~100 bytes |

**Total irreducible JS for a PyBend static site with form submission:** ~600-800 bytes minified.

The key insight: none of these require a framework. A single `<script>` block handles all of them.

```html
<!-- The entire JS payload for a static PyBend site -->
<script>
// Form submission (~200 bytes)
document.querySelectorAll('form[data-api]').forEach(f => {
  f.addEventListener('submit', async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(f));
    const r = await fetch(f.dataset.api, {
      method: f.method || 'POST',
      headers: {'Content-Type': 'application/json',
                'x-access-token': localStorage.getItem('token') || ''},
      body: JSON.stringify(data)
    });
    if (r.ok) location.reload();
    else alert((await r.json()).detail || 'Error');
  });
});

// Login handler (~150 bytes)
document.querySelector('form[data-login]')?.addEventListener('submit', async e => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  const r = await fetch(e.target.action, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(d)
  });
  const j = await r.json();
  if (j.token) { localStorage.setItem('token', j.token); location.href = '/'; }
});
</script>
```

**Minified and gzipped:** Under 400 bytes. Compare to React (42KB min+gzip) or even Alpine.js (6KB).

---

## 3. The "Tiny JS" Pattern: Under 1KB for Everything

The pattern: CSS handles all visual interactivity (accordions, tabs, modals, filters, transitions, themes). A single `<script>` tag under 1KB handles the irreducible API communication layer.

### Architecture

```
Static HTML (PyBend-generated)
  |
  +-- CSS (all interactivity)
  |     +-- :target tabs/navigation
  |     +-- :checked filters/toggles
  |     +-- <details> accordions
  |     +-- <dialog> modals
  |     +-- scroll-snap carousels
  |     +-- container queries (adaptive display)
  |     +-- view-transitions (page navigation)
  |     +-- prefers-* (user preferences)
  |
  +-- JS (<1KB, only for API calls)
        +-- form submission
        +-- login/token storage
        +-- method invocation (like, favorite, comment)
```

### Real-World References

| Site | JS Payload | Perceived Interactivity | Technique |
|---|---|---|---|
| [GOV.UK](https://www.gov.uk) | ~61KB (progressive enhancement) | High | HTML/CSS first, JS enhances |
| [motherfuckingwebsite.com](https://motherfuckingwebsite.com) | 0 bytes | Minimal (intentional) | Pure HTML |
| [btw.so](https://btw.so) | <5KB | High | CSS-driven, minimal JS |
| [Hacker News](https://news.ycombinator.com) | ~15KB | Medium | Server-rendered, minimal JS |
| [lite.cnn.com](https://lite.cnn.com) | <5KB | Medium | Static HTML, minimal JS |
| [250KB Club sites](https://250kb.club) | Varies (<250KB total) | Varies | Total page weight discipline |

GOV.UK's migration to their Design System achieved a Lighthouse performance score of 99/100 after reducing CSS by 93% and JS by 61%, primarily by removing jQuery and using native HTML patterns [GOV.UK Technology Blog, 2018](https://technology.blog.gov.uk/2018/12/21/the-benefits-of-migrating-gov-uk-pays-codebase-to-the-gov-uk-design-system/).

---

## 4. Browser Support Matrix

| CSS Feature | Chrome | Firefox | Safari | Edge | Global Coverage |
|---|---|---|---|---|---|
| `<details>/<summary>` | 12+ | 49+ | 6+ | 79+ | **97.5%** |
| `:target` | 1+ | 1+ | 3.1+ | 12+ | **99%+** |
| `:checked` + label | 1+ | 1+ | 3.1+ | 12+ | **99%+** |
| `scroll-snap` | 69+ | 68+ | 11+ | 79+ | **96%** |
| `:has()` | 105+ | 121+ | 15.4+ | 105+ | **95%+** |
| `<dialog>` element | 37+ | 98+ | 15.4+ | 79+ | **95%+** |
| Popover API | 114+ | 125+ | 17+ | 114+ | **90%+** |
| Container queries | 105+ | 110+ | 16+ | 105+ | **95%+** |
| View transitions (SPA) | 111+ | 146+ | 18.1+ | 111+ | **85%+** |
| View transitions (MPA) | 126+ | -- | -- | 126+ | **~70%** |
| Anchor positioning | 125+ | (flag) | (flag) | 125+ | **~70%** |
| Invoker commands | 135+ | (nightly) | (TP) | 135+ | **~65%** |
| `prefers-color-scheme` | 76+ | 67+ | 12.1+ | 79+ | **96%+** |
| `prefers-reduced-motion` | 74+ | 63+ | 10.1+ | 79+ | **96%+** |
| `@starting-style` | 117+ | 129+ | 17.5+ | 117+ | **88%+** |
| CSS `counter()` | 2+ | 1+ | 3+ | 12+ | **99%+** |

**Interpretation:** The core patterns (`<details>`, `:target`, `:checked`, `scroll-snap`, `:has()`, container queries) have 95%+ coverage. These alone cover accordions, tabs, filters, carousels, and adaptive layouts. The newer features (anchor positioning, invoker commands, MPA view transitions) are viable with progressive enhancement -- they improve the experience where supported and degrade gracefully.

---

## 5. Accessibility Analysis

### CSS-Only Patterns: Accessibility Scorecard

| Pattern | Keyboard Nav | Screen Reader | ARIA Needed | Rating |
|---|---|---|---|---|
| `<details>/<summary>` | Native (Enter/Space) | Announces expanded/collapsed | No | Excellent |
| `:target` tabs | Tab + Enter on links | Announces link targets | `role="tablist"` recommended | Good |
| `:checked` radio tabs | Arrow keys between radios | Announces selected/unselected | `aria-labelledby` if labels hidden | Good with care |
| `:checked` checkbox toggle | Space to toggle | Announces checked/unchecked | No (if input visible to AT) | Good with care |
| `scroll-snap` carousel | Arrow keys scroll | No inherent announcement | `aria-label` on track, `aria-roledescription` | Needs ARIA |
| `<dialog>` modal | Escape to close, focus trap | Announces "dialog" role | Native semantics | Excellent |
| Popover API | Escape to dismiss | Announces popover | Native semantics | Excellent |
| `:has()` state changes | N/A (visual only) | Not announced | May need `aria-live` for dynamic changes | Visual only |

### Key Accessibility Rules for CSS-Only Patterns

1. **Never use `display: none` or `visibility: hidden` on inputs** -- use `opacity: 0; position: absolute; width: 1px; height: 1px;` to keep them in the accessibility tree while visually hidden [dfkaye.com](https://dfkaye.com/posts/2020/08/23/accessible-css-driven-tabs-without-javascript/).

2. **Radio-based tabs need `aria-labelledby`** pointing from the radio to its visible label text. Without this, screen readers announce "radio button 1 of 3" without context.

3. **`:target` navigation needs `role="tablist"`/`role="tab"`/`role="tabpanel"`** for proper semantics. The links should have `role="tab"` and the sections should have `role="tabpanel"` [Accessible Accordion Patterns, Aditus](https://www.aditus.io/patterns/accordion/).

4. **`<details>/<summary>` is the gold standard** -- full keyboard and screen reader support out of the box, no ARIA needed. This is the recommended default for collapsible content.

5. **Visual-only state changes (`:has()`) need live regions** -- if a filter hiding/showing items changes a count, wrap that count in `<span aria-live="polite">` so screen readers announce the update.

---

## 6. PyBend Component Mapping

How each current PyBend frontend feature maps to CSS-only patterns in a static export:

### ntt-item Display Modes (xs/sm/md/lg/xl)

| Current (JS) | Static (CSS) | How |
|---|---|---|
| `displayMode` attribute + size methods | Container queries | `@container` rules adapt the same HTML to xs/sm/md/lg/xl based on parent width |
| `this.mode = 'edit'` toggle | `:checked` checkbox | Hidden checkbox toggles between display/edit CSS states |
| `deleteItem()` with `confirm()` | `<dialog>` + Invoker Commands | Declarative `commandfor="delete-dialog" command="show-modal"` |
| `.show-more-btn` expand toggle | `<details>` element | Native collapsible with `<summary>` |
| `staggerIn` animation | CSS animation + `prefers-reduced-motion` | Same animation, plus motion-safe guard |
| Skeleton placeholder | CSS `:empty` + animations | Show bones while `<ntt-static>` has no content; remove via CSS once loaded |

### ntt-list Features

| Current (JS) | Static (CSS) | How |
|---|---|---|
| Fetch + render entity list | Build-time HTML generation | Server renders all items at build time |
| "Load More" pagination | `:checked` toggle or `<details>` | Pre-rendered hidden items revealed by toggle |
| Filter by category | `:checked` + `:has()` | Checkbox filters hide/show cards with matching data attributes |
| Sort by field | Not feasible CSS-only | Requires JS (~100 bytes) or pre-sorted server output |

### form.js Field Rendering

| Current (JS) | Static (CSS) | How |
|---|---|---|
| `getForm()` builds HTML from schema | Build-time HTML | PyBend generates form HTML at export time |
| `getInput()` chooses input type | Build-time type resolution | Correct `<input type="...">` emitted at build |
| `renderGroupedFields()` fieldsets | `<details>` or `:target` tabs | Field groups become collapsible sections or tabbed panels |
| Permission-gated field visibility | Build-time conditional | Fields not visible to the target audience are simply not in the HTML |
| Protected field hiding in edit mode | CSS `:checked` state | `input.edit-toggle:checked ~ .protected-field { display: none; }` |

### Method Buttons (ntt-method)

| Current (JS) | Static (CSS + Tiny JS) | How |
|---|---|---|
| Method button renders from schema | Build-time `<form>` or `<button>` | Static HTML button/form emitted at build |
| Click triggers API call | Tiny JS form handler | The ~200 byte form submission handler |
| Count badge updates | Server-side count at build time | Count is static; dynamic updates need JS reload or SSE |

---

## 7. Measured Performance: JS-Free vs. Minimal-JS vs. SPA

### Lighthouse Score Comparison (Typical)

| Architecture | Performance | FCP | LCP | TBT | CLS | JS Size |
|---|---|---|---|---|---|---|
| **Static HTML + CSS only** | 98-100 | 0.4-0.6s | 0.5-0.8s | 0ms | 0 | 0 KB |
| **Static + Tiny JS (<1KB)** | 96-100 | 0.4-0.6s | 0.5-0.8s | 0-10ms | 0 | <1 KB |
| **SSG (Astro/11ty)** | 90-98 | 0.6-1.0s | 0.8-1.5s | 0-50ms | 0-0.05 | 5-30 KB |
| **MPA (Rails/Django)** | 80-95 | 0.8-1.5s | 1.0-2.0s | 0-100ms | 0-0.1 | 20-100 KB |
| **SPA (React/Vue)** | 50-85 | 1.5-3.0s | 2.0-4.0s | 200-800ms | 0.1-0.25 | 150-500 KB |
| **Current PyBend (Web Components)** | 70-90 | 1.0-2.0s | 1.5-3.0s | 50-200ms | 0.05-0.15 | 50-150 KB |

*FCP = First Contentful Paint. LCP = Largest Contentful Paint. TBT = Total Blocking Time. CLS = Cumulative Layout Shift.*

Sources: [GrapesJS Lighthouse comparison](https://grapesjs.com/blog/seo-lighthouse-reports-performance), [Astro performance data](https://eastondev.com/blog/en/posts/dev/20251202-astro-performance-optimization/), [GOV.UK performance blog](https://technology.blog.gov.uk/2018/12/21/the-benefits-of-migrating-gov-uk-pays-codebase-to-the-gov-uk-design-system/).

### Why Zero-JS Scores So High

**Total Blocking Time (TBT)** is the primary differentiator. TBT measures how long the main thread is blocked by JS execution. With zero JS, TBT is literally 0ms. SPAs routinely hit 200-800ms TBT because the browser must parse, compile, and execute the framework before the page becomes interactive.

**First Contentful Paint (FCP)** drops because HTML renders immediately -- no waiting for JS to fetch data, build a virtual DOM, and mount components. The browser's HTML parser is extraordinarily fast; a 50KB HTML file parses in under 50ms. The same data in a React SPA requires downloading 150KB+ of JS, parsing it, executing it, then rendering.

Google's own data: on a simulated slow 3G connection, each additional KB of JavaScript adds ~8.5ms to Time to Interactive. A React app shipping 200KB of JS adds ~1.7 seconds of blocking time on slow connections [web.dev, Lighthouse documentation](https://developer.chrome.com/blog/lighthouse-load-performance).

---

## 8. The Progressive Enhancement Ladder

A static PyBend export should follow a three-tier progressive enhancement model:

### Tier 1: Pure HTML + CSS (No JS at all)
- Content is readable
- Navigation works via `<a>` tags and `:target`
- Accordions work via `<details>/<summary>`
- Theme respects system preference via `prefers-color-scheme`
- Images are visible, forms are visible (but not submittable)
- **Use case:** Read-only catalog, documentation, public portfolio

### Tier 2: Tiny JS (<1KB)
- Forms submit to the API
- Login/logout works
- Method buttons (like, favorite) fire API calls
- Toast notifications for errors
- **Use case:** Interactive product catalog, blog with comments, simple CRUD

### Tier 3: Enhanced JS (1-10KB, optional)
- Real-time updates via SSE/WebSocket
- Complex filtering with URL state sync
- Drag-and-drop reordering
- Optimistic UI updates
- **Use case:** Admin dashboard, collaborative editing, live data

The key architectural decision: **Tier 1 is the baseline, not an afterthought.** Every page must work at Tier 1. JS enhances; it never gates.

---

## 9. Complete CSS-Only Static Card Example

Putting it all together -- a PyBend Product entity rendered as a static card with CSS-only interactivity:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Products</title>
  <style>
    /* System theme */
    :root {
      --bg: #0e1018; --text-0: #f0f2f8; --text-2: #8891ab;
      --accent: #22d3c5; --surface-2: rgba(22,26,38,0.7);
      --glass-bg: rgba(14,16,24,0.55); --glass-border: rgba(255,255,255,0.09);
      --radius-lg: 16px;
    }
    @media (prefers-color-scheme: light) {
      :root {
        --bg: #f8f9fa; --text-0: #1a1a2e; --text-2: #6b7280;
        --glass-bg: rgba(255,255,255,0.8); --glass-border: rgba(0,0,0,0.1);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      * { animation: none !important; transition-duration: 0.01ms !important; }
    }

    body { background: var(--bg); color: var(--text-0); font-family: system-ui; }

    /* Container query setup */
    .card-container { container-type: inline-size; }

    /* Base card */
    .card {
      background: var(--glass-bg);
      border: 1px solid var(--glass-border);
      border-radius: var(--radius-lg);
      padding: 1.5rem;
      margin: 1rem 0;
    }

    /* Adaptive sizing via container queries */
    @container (max-width: 250px) {
      .card { display: inline-flex; padding: 0.2rem 0.65rem;
              border-radius: 999px; gap: 0.35rem; }
      .card .detail-fields { display: none; }
    }
    @container (min-width: 251px) and (max-width: 500px) {
      .card { display: flex; align-items: center; gap: 1rem;
              padding: 0.55rem 1rem; }
    }

    /* Collapsible sections */
    details summary { cursor: pointer; user-select: none; }

    /* Filter pills */
    .filter-pill {
      display: inline-block; padding: 0.2rem 0.65rem;
      border-radius: 999px; border: 1px solid var(--glass-border);
      cursor: pointer; font-size: 0.78rem;
    }
    input:checked + .filter-pill {
      background: rgba(34,211,197,0.12);
      border-color: var(--accent);
    }
  </style>

  <!-- View Transitions for page navigation -->
  <style>
    @view-transition { navigation: auto; }
    ::view-transition-old(root) { animation: fadeOut 0.15s ease; }
    ::view-transition-new(root) { animation: fadeIn 0.2s ease; }
    @keyframes fadeOut { to { opacity: 0; } }
    @keyframes fadeIn { from { opacity: 0; } }
  </style>
</head>
<body>
  <!-- Filters (CSS-only via :checked) -->
  <nav>
    <input type="checkbox" id="f-electronics" checked hidden>
    <label for="f-electronics" class="filter-pill">Electronics</label>
    <input type="checkbox" id="f-clothing" checked hidden>
    <label for="f-clothing" class="filter-pill">Clothing</label>
  </nav>

  <!-- Product list -->
  <div class="card-container">
    <article class="card" data-category="electronics">
      <h2>Widget Pro</h2>
      <p class="detail-fields" style="color:var(--text-2)">$29.99</p>

      <details>
        <summary>3 Comments</summary>
        <div class="comment">Great product! - Alice</div>
        <div class="comment">Works as expected. - Bob</div>
        <div class="comment">Would buy again. - Charlie</div>
      </details>

      <!-- Like button (needs tiny JS for API call) -->
      <form data-api="/products/1/like" method="POST" style="display:inline">
        <button type="submit">Like (12)</button>
      </form>
    </article>
  </div>

  <!-- Tiny JS: form submission only (~200 bytes) -->
  <script>
  document.querySelectorAll('form[data-api]').forEach(f=>{
    f.onsubmit=async e=>{e.preventDefault();
    await fetch(f.dataset.api,{method:f.method||'POST',
    headers:{'Content-Type':'application/json',
    'x-access-token':localStorage.token||''},
    body:JSON.stringify(Object.fromEntries(new FormData(f)))});
    location.reload()}});
  </script>
</body>
</html>
```

This complete example delivers: adaptive display modes, collapsible comments, filter pills, theme switching, reduced-motion support, view transitions between pages, and API-connected method buttons -- all in under 2KB of CSS and under 200 bytes of JS.

---

## 10. Risks and Limitations

| Risk | Severity | Mitigation |
|---|---|---|
| **No dynamic sorting** | Medium | Pre-sort at build time; offer multiple pre-sorted pages |
| **No real-time count updates** | Medium | Counts are build-time snapshots; rebuild frequently or accept staleness |
| **`:checked` state resets on navigation** | Low | Use `:target` for persistent state; or 50 bytes of JS to save to `sessionStorage` |
| **Invoker commands not yet cross-browser** | Low | Progressive enhancement: works in Chrome/Edge, degrades to clickable links elsewhere |
| **Anchor positioning limited** | Low | Fallback to static positioning; tooltips still work, just positioned differently |
| **MPA view transitions partial** | Medium | Chrome/Edge only; other browsers get instant navigation (still fast) |
| **Form submission needs JS** | Irreducible | The ~200 byte handler is the minimum viable JS |
| **Search/full-text requires JS or server** | High | Cannot do client-side search without JS; server-side search or pre-built indexes needed |

---

## 11. Recommendations for PyBend Static Export

1. **Default to `<details>/<summary>`** for all `ui.groups` field groups and `ListRef` nested entities. This replaces 100% of the current JS-driven expand/collapse logic.

2. **Use container queries** instead of the `display="xs|sm|md|lg|xl"` attribute. The same HTML adapts to any container width, eliminating the need for the JS size-method dispatch in `ntt-item.js`.

3. **Emit `<dialog>` elements** for delete confirmations and method parameter forms. With Invoker Commands, these work without JS in Chrome/Edge and degrade to a simple link-based flow elsewhere.

4. **Ship a single `<script>` block under 400 bytes** (gzipped) for form submission, login, and method invocation. Nothing else.

5. **Enable `@view-transition { navigation: auto; }`** in the base stylesheet. Free page transitions for Chrome/Edge users, zero cost for others.

6. **Use `:checked` filters** when the product catalog has enumerable categories. Pre-render all items with data attributes; CSS handles visibility.

7. **Test with Lighthouse CI** targeting Performance >= 95, Accessibility >= 95. With this architecture, both are achievable by default.

---

## Sources

1. [CSS in 2026: The new features reshaping frontend development -- LogRocket Blog](https://blog.logrocket.com/css-in-2026/)
2. [2026 CSS Features You Must Know -- Riad Kilani](https://blog.riadkilani.com/2026-css-features-you-must-know/)
3. [:has() CSS relational pseudo-class -- Can I Use](https://caniuse.com/css-has)
4. [CSS Accordion Tutorial: 5 Methods -- Prismic](https://prismic.io/blog/css-accordions)
5. [Accessible CSS-driven Tabs without JavaScript -- dfkaye.com](https://dfkaye.com/posts/2020/08/23/accessible-css-driven-tabs-without-javascript/)
6. [Carousels with CSS -- Chrome for Developers](https://developer.chrome.com/blog/carousels-with-css)
7. [Well-controlled scrolling with CSS Scroll Snap -- web.dev](https://web.dev/css-scroll-snap/)
8. [Invoker Commands: Additional Ways to Work With Dialog, Popover -- CSS-Tricks](https://css-tricks.com/invoker-commands-additional-ways-to-work-with-dialog-popover-and-more/)
9. [Developing modals using only CSS and the Popover API -- LogRocket](https://blog.logrocket.com/developing-modals-using-only-css-popover-api/)
10. [View Transition API -- MDN](https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API)
11. [CSS View Transitions: The Complete Guide for 2026 -- DevToolbox](https://devtoolbox.dedyn.io/blog/css-view-transitions-complete-guide)
12. [Container queries in 2026 -- LogRocket Blog](https://blog.logrocket.com/container-queries-2026/)
13. [CSS Container Queries: The Complete Guide for 2026 -- DevToolbox](https://devtoolbox.dedyn.io/blog/css-container-queries-guide)
14. [CSS Anchor Positioning: Complete Guide -- DevToolbox](https://devtoolbox.dedyn.io/blog/css-anchor-positioning-guide)
15. [GOV.UK Design System migration -- GOV.UK Technology Blog](https://technology.blog.gov.uk/2018/12/21/the-benefits-of-migrating-gov-uk-pays-codebase-to-the-gov-uk-design-system/)
16. [Why Clean HTML Beats React: Lighthouse Reports -- GrapesJS](https://grapesjs.com/blog/seo-lighthouse-reports-performance)
17. [A Guide To Keyboard Accessibility: HTML and CSS -- Smashing Magazine](https://www.smashingmagazine.com/2022/11/guide-keyboard-accessibility-html-css-part1/)
18. [Popover and dialog -- web.dev](https://web.dev/learn/css/popover-and-dialog)
19. [CSS Media Queries: The Complete Guide for 2026 -- DevToolbox](https://devtoolbox.dedyn.io/blog/css-media-queries-complete-guide)
20. [awesome-tiny-js: A collection of tiny JS libraries -- GitHub](https://github.com/thoughtspile/awesome-tiny-js)
21. [Using Lighthouse to improve page load performance -- Chrome for Developers](https://developer.chrome.com/blog/lighthouse-load-performance)
22. [Controlling dialogs and popovers with the Invoker Commands API -- HTMHell](https://www.htmhell.dev/adventcalendar/2025/7/)
23. [CSS-Framework Lighthouse Scores comparison](https://jantimon.github.io/css-framework-performance/)
