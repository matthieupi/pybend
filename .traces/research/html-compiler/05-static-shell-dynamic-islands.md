# Static Shell + Dynamic Islands: Architecture Research Brief

## Executive Summary

The **Static Shell + Dynamic Islands** pattern is a web architecture where the majority of a page is delivered as pre-rendered, cacheable static HTML (the "shell"), with isolated pockets of client-side interactivity ("islands") hydrated independently. Unlike SPAs that hydrate the entire page or SSR approaches that ship full-page JavaScript bundles, islands architecture sends JavaScript only for the interactive regions, achieving 60-90% reductions in client-side JavaScript.

The pattern was formalized by **Jason Miller** (Preact creator) in August 2020, building on a concept first coined by **Katie Sylor-Miller** (Etsy frontend architect) in 2019. It has since been adopted by Astro, Fresh (Deno), Marko (eBay), 11ty, and influenced Next.js PPR.

**Key finding for PyBend**: Web Components are _inherently_ island-shaped. Custom elements are encapsulated, self-contained, independently upgradable, and progressively enhanceable. PyBend's existing `<ntt-item>`, `<ntt-list>`, and `<ntt-router>` components already exhibit island characteristics. The Actor/Matrix message bus is a natural island communication layer. The primary adoption work would be generating a static HTML shell server-side and deferring component hydration via the schema bootstrap rather than doing everything client-side.

---

## Table of Contents

1. [What the Pattern Actually Is](#1-what-the-pattern-actually-is)
2. [How Islands Work Mechanically](#2-how-islands-work-mechanically)
3. [Framework Implementations in Detail](#3-framework-implementations-in-detail)
4. [Web Components as Natural Islands](#4-web-components-as-natural-islands)
5. [The Static Shell Concept](#5-the-static-shell-concept)
6. [Island Communication Patterns](#6-island-communication-patterns)
7. [Performance Characteristics](#7-performance-characteristics)
8. [The Island Granularity Question](#8-the-island-granularity-question)
9. [Progressive Enhancement Within Islands](#9-progressive-enhancement-within-islands)
10. [Practical Patterns](#10-practical-patterns)
11. [How This Maps to PyBend](#11-how-this-maps-to-pybend)
12. [Limitations and Anti-Patterns](#12-limitations-and-anti-patterns)
13. [Sources](#13-sources)

---

## 1. What the Pattern Actually Is

### 1.1 The Original Jason Miller Formulation

Jason Miller published the defining document on August 11, 2020. His formulation:

> "The general idea of an 'Islands' architecture is deceptively simple: **render HTML pages on the server, and inject placeholders or slots around highly dynamic regions**. These placeholders/slots contain the server-rendered HTML output from their corresponding widget. They denote regions that can then be 'hydrated' on the client into small self-contained widgets, reusing their server-rendered initial HTML."

The visual metaphor: imagine a page as an ocean of static HTML. Scattered across it are small islands of JavaScript-powered interactivity. The ocean (static content) is immediately visible and usable. The islands (interactive widgets) hydrate independently, each at its own pace, without blocking or depending on each other.

Miller identified several key properties:

- **No top-down rendering requirement.** Unlike progressive hydration (which still requires a root component to initialize before descendants), each island is an isolated unit. A performance issue in one island does not affect the others.
- **Server rendering is fundamental, not bolted on.** The HTML returned contains "a meaningful and immediately renderable representation of the content the user requested." This is not an SEO optimization -- it is the primary delivery mechanism.
- **Each island is independently deliverable.** Islands can be loaded, hydrated, and updated without coordination with other islands on the page.

### 1.2 How It Differs from Other Approaches

| Approach | Static Content | JavaScript Shipped | Hydration Model | Initial Paint | Navigation |
|----------|---------------|-------------------|-----------------|---------------|------------|
| **SPA** | None (client-rendered) | Entire application bundle | Full app bootstrap | Slow (waits for JS) | Client-side routing |
| **SSR** | Server-rendered HTML | Full page JS re-shipped | Full page re-hydration | Fast HTML, then JS | Server round-trip or client routing |
| **SSG** | Pre-built static HTML | Minimal or none | None (pure static) | Very fast | Full page reload |
| **Progressive Hydration** | Server-rendered HTML | Full page JS, loaded progressively | Top-down, deferred | Fast HTML, JS deferred | Depends on framework |
| **Islands** | Server-rendered static | **Only island JS** | Per-island, independent | Very fast | MPA (full page) or hybrid |
| **Server Components (RSC)** | Server-rendered + streamed | Reduced (server-resolved) | Component-level + client routing | Fast with streaming | Client-side (preserves state) |
| **Resumability (Qwik)** | Server-rendered, serialized | Near-zero initial | No hydration (resumes) | Instant | Client-side |

The critical distinction: SSR and progressive hydration still eventually ship and execute JavaScript for the _entire page_. Islands architecture fundamentally reduces the total JavaScript volume by excluding non-interactive regions entirely.

### 1.3 Evolution of the Pattern

The pattern evolved through several stages:

1. **2019**: Katie Sylor-Miller coins "component islands" at Etsy.
2. **2020**: Jason Miller publishes the formal architecture description.
3. **2021**: Astro launches with islands as its core architecture primitive.
4. **2022**: Fresh (Deno) ships with `islands/` convention. 11ty releases `<is-land>`. Marko refines compiler-automated islands.
5. **2023-2024**: Astro introduces **Server Islands** (server-deferred rendering) in Astro 5. Next.js introduces **Partial Pre-Rendering (PPR)** -- a static shell + Suspense streaming approach inspired by islands thinking.
6. **2025-2026**: Islands architecture is widely recognized as the dominant pattern for content-driven sites. Server components and islands begin to converge.

---

## 2. How Islands Work Mechanically

### 2.1 The HTML-Level View

At the HTML level, an islands page looks like this:

```html
<!DOCTYPE html>
<html>
<head>
  <title>Product Page</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <!-- STATIC: Navigation bar (pure HTML, zero JS) -->
  <nav>
    <a href="/">Home</a>
    <a href="/products">Products</a>
  </nav>

  <!-- STATIC: Product info (server-rendered, no hydration) -->
  <main>
    <h1>Widget Pro 3000</h1>
    <p>The finest widget money can buy.</p>
    <span class="price">$49.99</span>
  </main>

  <!-- ISLAND: Interactive image carousel -->
  <image-carousel client:visible>
    <img src="/widget-1.jpg" alt="Widget front view">
    <img src="/widget-2.jpg" alt="Widget side view">
  </image-carousel>

  <!-- ISLAND: Add-to-cart button with quantity selector -->
  <add-to-cart client:load product-id="42">
    <button>Add to Cart</button>  <!-- Fallback: functional without JS -->
  </add-to-cart>

  <!-- STATIC: Product description, specs, etc. -->
  <section class="specs">...</section>

  <!-- ISLAND: Comment section (deferred, heavy) -->
  <comment-section client:idle product-id="42">
    <p>Loading comments...</p>  <!-- Fallback content -->
  </comment-section>

  <!-- STATIC: Footer -->
  <footer>...</footer>
</body>
</html>
```

The browser receives this HTML immediately. The static regions render instantly. The islands begin their hydration lifecycle according to their directives.

### 2.2 Browser Processing Flow

1. **HTML parsing**: The browser parses the entire document. Static regions are painted immediately. Island placeholder elements are in the DOM but not yet interactive.

2. **CSS application**: Styles apply to everything, including island placeholders. The page looks complete even before any JavaScript runs.

3. **Island discovery**: A small coordinator script (or the browser's custom element registry) identifies island boundaries. In Astro, this is a generated script. In 11ty's `<is-land>`, it is the `is-land.js` web component (1.79 KB). In a Web Components approach, it is `customElements.define()`.

4. **Conditional hydration**: Each island evaluates its hydration condition:
   - **load** -- hydrate immediately on page load
   - **idle** -- hydrate when `requestIdleCallback` fires (browser is done with critical work)
   - **visible** -- hydrate when `IntersectionObserver` reports the element is in viewport
   - **media** -- hydrate when a CSS media query matches (e.g., `min-width: 768px`)
   - **interaction** -- hydrate on first user interaction (click, hover, focus)

5. **Independent hydration**: When conditions are met, the island's JavaScript is loaded (potentially via dynamic `import()`), and the component initializes using its server-rendered HTML as the starting state. No other island is affected.

### 2.3 Hydration Directives in Detail

Astro popularized the `client:*` directive syntax. These map directly to browser APIs:

| Directive | Browser API | When to Use |
|-----------|------------|-------------|
| `client:load` | Immediate execution | Critical interactive elements (auth forms, primary CTAs) |
| `client:idle` | `requestIdleCallback()` | Important but not blocking (analytics, secondary UI) |
| `client:visible` | `IntersectionObserver` | Below-the-fold content (comments, related items) |
| `client:media` | `matchMedia()` | Responsive islands (mobile hamburger menu, desktop sidebar) |
| `client:only` | Immediate, no SSR | Client-only components (canvas, WebGL, maps) |

11ty's `<is-land>` adds:

| Condition | Behavior |
|-----------|----------|
| `on:interaction` | Hydrate on click/touch/focus (configurable events) |
| `on:save-data` | Respect the user's data-saver preference |

These conditions can be **combined**: `<is-land on:visible on:idle>` requires _both_ conditions before hydrating, creating very precise loading behavior.

---

## 3. Framework Implementations in Detail

### 3.1 Astro

Astro is the most prominent islands architecture framework. Its core principle: **zero JavaScript by default, opt-in interactivity via `client:*` directives.**

**How `.astro` components compile:**

An `.astro` file has two sections separated by a code fence (`---`):

```astro
---
// Component Script: runs at build time (or request time for SSR)
const products = await fetch('/api/products').then(r => r.json());
---

<!-- Component Template: compiles to static HTML -->
<h1>Products</h1>
<ul>
  {products.map(p => <li>{p.name} - ${p.price}</li>)}
</ul>

<!-- Island: this React component hydrates on the client -->
<SearchBar client:load />
```

The build process:

1. **Static analysis**: Astro analyzes all components to determine which can be rendered at build time and which require client JavaScript.
2. **Server execution**: The frontmatter JavaScript runs, fetching data and processing logic.
3. **HTML generation**: The template compiles to optimized HTML generation code. For static components, this produces pure HTML. For island components, it produces HTML plus a hydration script marker.
4. **JavaScript isolation**: Only components marked with `client:*` have their JavaScript included in the build output. Everything else is discarded after producing HTML.
5. **Output**: The `dist/` directory contains `.html` files, island-specific JS chunks, and CSS. No framework runtime ships for static components.

**Astro Server Islands (Astro 5):**

Server Islands add a second island primitive: **server-deferred rendering**. Instead of deferring JavaScript hydration (client islands), server islands defer _server rendering_ itself.

```astro
---
import UserAvatar from './UserAvatar.astro';
import ProductRecs from './ProductRecs.astro';
---

<!-- Static shell: cached at CDN edge -->
<h1>Welcome back!</h1>

<!-- Server Island: rendered on-demand, fetched after initial load -->
<UserAvatar server:defer>
  <div slot="fallback" class="skeleton-avatar"></div>
</UserAvatar>

<!-- Another server island: personalized recommendations -->
<ProductRecs server:defer user-id={userId}>
  <p slot="fallback">Loading recommendations...</p>
</ProductRecs>
```

How it works:

1. At build time, `server:defer` components are replaced with a small inline script and fallback content.
2. The static shell (everything except the deferred components) is cached at the CDN.
3. On page load, the inline script makes a `GET` request to a special Astro-generated route for each server island.
4. The server renders the component with fresh data and returns HTML.
5. The inline script replaces the fallback with the server-rendered result.

This enables: static shell cached globally at CDN + personalized/dynamic content rendered per-request, without any client-side JavaScript framework.

### 3.2 Fresh (Deno)

Fresh uses a **convention-based** approach: files in the `islands/` directory (or `_islands/` subdirectory in routes) are the only components that ship JavaScript to the client.

```
project/
  routes/
    index.tsx          # Server-rendered, no client JS
    products/[id].tsx  # Server-rendered, no client JS
  islands/
    SearchBar.tsx      # Interactive: JS shipped to client
    AddToCart.tsx       # Interactive: JS shipped to client
  components/
    Header.tsx         # Server-only: no client JS
    Footer.tsx         # Server-only: no client JS
```

Key mechanics:

- **Preact-based**: Islands are Preact components rendered on both server and client.
- **HTML comment markers**: Fresh inserts `<!--FRSH:ComponentName:0-->` comments in server-rendered HTML to mark island boundaries.
- **Client-side revival**: A `revive()` function traverses the DOM using regex to find these markers, then hydrates each island independently with its serialized props.
- **Signals for state sharing**: Fresh uses Preact Signals for cross-island state. Signals can be passed as island props, with the framework serializing signal identity and values during SSR and reconstructing live signals on the client.

```tsx
// islands/Counter.tsx - This ships JS to the client
import { useSignal } from "@preact/signals";

export default function Counter(props: { start: number }) {
  const count = useSignal(props.start);
  return (
    <div>
      <p>{count}</p>
      <button onClick={() => count.value++}>+1</button>
    </div>
  );
}
```

### 3.3 Marko (eBay)

Marko's approach is unique: the **compiler determines island boundaries automatically**. Developers never manually annotate what is interactive and what is static.

How it works:

1. **Analysis pass**: The Marko compiler analyzes all template files, gathering metadata about which components modify state, respond to events, or have side effects.
2. **Boundary determination**: Components that are purely presentational (headers, footers, static text blocks) are excluded from the client bundle entirely. Components with event handlers, state mutations, or dynamic behavior become islands.
3. **Sub-template partial hydration**: Marko can identify interactive regions _within_ a template, not just at the component boundary. If only a button inside a card needs interactivity, only the button's code ships.
4. **Streaming**: HTML streams to the client as it becomes available. Interactive islands hydrate themselves when their code arrives.

This approach eliminates the developer burden of deciding island boundaries. The compiler makes optimal decisions based on static analysis of the reactive dependency graph, achieving 60-84% JavaScript reductions on eBay production pages.

### 3.4 11ty (`<is-land>`)

11ty takes the most framework-agnostic approach with its `<is-land>` web component:

```html
<script type="module" src="/is-land.js"></script>

<!-- Island: hydrate when visible AND browser is idle -->
<is-land on:visible on:idle>
  <template data-island>
    <my-interactive-widget></my-interactive-widget>
    <script type="module" src="/widgets/interactive.js"></script>
  </template>

  <!-- Fallback: shown before hydration -->
  <p>Interactive content will appear here.</p>
</is-land>
```

Key characteristics:

- **Zero dependencies**: `is-land.js` is 1.79 KB compressed.
- **Framework-agnostic**: Works with any JS framework (Alpine, Vue, Preact, Svelte, Lit, vanilla) via pluggable initializers.
- **`<template data-island>`**: Content inside `<template>` is inert (browser does not parse or execute it). When hydration conditions are met, `<is-land>` activates the template, executing scripts and applying styles.
- **Nested islands**: Child `<is-land>` elements inherit parent conditions. All ancestor conditions must be satisfied before a nested island hydrates.
- **`[ready]` attribute**: Added when hydration completes, enabling CSS transitions for progressive appearance.

The `<is-land>` pattern is particularly relevant to PyBend because it demonstrates that islands can be implemented as a web component wrapper around _any_ content, without build tooling or framework lock-in.

### 3.5 Next.js PPR (Partial Pre-Rendering)

Next.js PPR (stable in Next.js 15+, enhanced in Next.js 16) adapts islands thinking to the React Server Components model:

```tsx
import { Suspense } from 'react';

// Static shell: pre-rendered at build time
export default function ProductPage({ params }) {
  return (
    <main>
      <h1>Product Page</h1>
      <StaticProductInfo id={params.id} />  {/* Pre-rendered */}

      {/* Dynamic island: streamed on request */}
      <Suspense fallback={<PriceSkeleton />}>
        <DynamicPrice id={params.id} />
      </Suspense>

      {/* Another dynamic island */}
      <Suspense fallback={<ReviewsSkeleton />}>
        <PersonalizedReviews id={params.id} />
      </Suspense>
    </main>
  );
}
```

How PPR works:

1. **Build time**: Next.js pre-renders a static shell for each route, leaving "holes" where `<Suspense>` boundaries wrap dynamic content. The fallback UI fills these holes.
2. **CDN caching**: The static shell (with fallback content in the holes) is cached at the edge.
3. **Request time**: When a user visits, the static shell is served instantly. Simultaneously, the server begins rendering the dynamic content within each Suspense boundary.
4. **Streaming**: Dynamic content streams into the page via a single HTTP response. Each Suspense boundary resolves independently. Client-side React swaps the fallback with the streamed result.
5. **No extra round-trips**: Unlike Astro's Server Islands (which make separate `GET` requests per island), PPR streams everything in one response.

PPR differs from pure islands in that it uses **client-side routing** and maintains **global React state** across navigations. This adds complexity but preserves SPA-like navigation behavior.

---

## 4. Web Components as Natural Islands

### 4.1 Why Custom Elements Are Inherently Island-Shaped

Web Components (custom elements) exhibit every property that defines an island:

| Island Property | Web Component Equivalent |
|----------------|-------------------------|
| **Encapsulated** | Shadow DOM isolates styles and DOM structure |
| **Self-contained** | Custom elements own their lifecycle, state, and rendering |
| **Independently hydratable** | `customElements.define()` can be called at any time; elements upgrade in place |
| **No top-down dependency** | No framework root required; each element initializes independently |
| **Server-renderable** | Declarative Shadow DOM enables pre-rendered shadow content |
| **Progressive enhancement** | HTML content inside custom elements is visible before JS loads |

The custom element tag itself acts as the island boundary. In a sea of static HTML, a `<my-widget>` tag denotes an island of interactivity. The browser renders the element's light DOM children immediately. When the element's class definition loads (via `customElements.define()`), the element "upgrades" -- its constructor runs, `connectedCallback` fires, and it becomes interactive.

This upgrade process is _exactly_ island hydration:

```html
<!-- Before JS loads: visible, static HTML -->
<product-card>
  <h2>Widget Pro</h2>
  <span class="price">$49.99</span>
  <button>Add to Cart</button>  <!-- Visible but not functional -->
</product-card>

<!-- After customElements.define('product-card', ...): upgraded, interactive -->
<!-- The button now has event listeners, the card can expand/collapse, etc. -->
```

### 4.2 Declarative Shadow DOM and Pre-Rendered Islands

Declarative Shadow DOM (DSD) enables server-rendering the _internal structure_ of a web component:

```html
<product-card>
  <template shadowrootmode="open">
    <style>
      :host { display: block; border: 1px solid #ccc; padding: 1rem; }
      .price { color: green; font-weight: bold; }
    </style>
    <h2><slot name="title"></slot></h2>
    <span class="price"><slot name="price"></slot></span>
    <button><slot name="action">Add to Cart</slot></button>
  </template>
  <span slot="title">Widget Pro</span>
  <span slot="price">$49.99</span>
</product-card>
```

The browser attaches the shadow root during HTML parsing, before any JavaScript runs. The component renders with its full styled layout immediately. When the component class loads later, it can attach event listeners and add dynamic behavior to the already-rendered DOM.

### 4.3 Lit SSR

Lit provides a server-side rendering package (`@lit-labs/ssr`) that renders Lit components to static HTML with Declarative Shadow DOM:

- **No browser DOM emulation**: Lit SSR uses Lit's declarative template format to generate HTML strings directly.
- **Streaming support**: HTML can be streamed as it renders.
- **Client hydration**: The `@lit-labs/ssr-client` package handles upgrading server-rendered Lit elements on the client, reusing the existing DOM.

The `defer-hydration` attribute convention (community-agreed draft standard) enables controlled hydration timing:

```html
<my-element defer-hydration>
  <template shadowrootmode="open">
    <!-- Pre-rendered content -->
  </template>
</my-element>
```

The element checks for `defer-hydration` in `attributeChangedCallback`. It only initializes when the attribute is removed, allowing an orchestrator (like `<is-land>`) to control timing.

### 4.4 The `<is-land>` + Web Component Pattern

11ty's `<is-land>` wrapping a web component creates a powerful composition:

```html
<is-land on:visible>
  <product-card>
    <h2>Widget Pro</h2>
    <span>$49.99</span>
  </product-card>
  <template data-island>
    <script type="module" src="/components/product-card.js"></script>
  </template>
</is-land>
```

Flow:
1. Browser renders `<product-card>` with its light DOM children (visible immediately).
2. `<is-land>` observes visibility via `IntersectionObserver`.
3. When visible, `<is-land>` activates the `<template>`, loading the component's JavaScript.
4. `customElements.define()` fires, upgrading `<product-card>` to an interactive island.
5. `<is-land>` sets `[ready]` on itself, enabling CSS transitions.

---

## 5. The Static Shell Concept

### 5.1 What Constitutes the Shell

The static shell is everything on the page that does **not** require request-time data, user-specific state, or JavaScript interactivity. Typically:

- **Navigation**: Header, sidebar, breadcrumbs, footer links
- **Layout structure**: Page grid, section containers, spacing
- **Branding**: Logo, colors, typography (via CSS)
- **Static content**: Product descriptions, article text, legal text, documentation
- **SEO metadata**: `<title>`, `<meta>`, structured data
- **Loading states**: Skeleton placeholders for dynamic regions

### 5.2 Cacheability

The shell's value comes from its cacheability:

- **CDN edge caching**: The shell HTML can be cached at edge nodes worldwide with long `Cache-Control` max-age values. Every visitor in a region gets the same cached shell.
- **Service Worker caching**: The Application Shell Model (popularized by Google for PWAs) caches the shell in a Service Worker, enabling instant repeat loads and offline access to the shell structure.
- **Browser caching**: With content-hash filenames for CSS/JS, static assets can be cached indefinitely (`immutable` directive).

Cache strategy for a shell:

```
# Shell HTML: cache at edge, revalidate periodically
Cache-Control: public, max-age=3600, s-maxage=86400, stale-while-revalidate=60

# Static assets (CSS, fonts, images): cache indefinitely
Cache-Control: public, max-age=31536000, immutable
```

### 5.3 Shell + Islands Composition

A page composes as:

```
+---------------------------------------------------+
|  STATIC SHELL (cached, instant)                   |
|  +---------------------------------------------+ |
|  | Navigation Bar                               | |
|  +---------------------------------------------+ |
|  |                                               | |
|  |  Page Title (static)                          | |
|  |  Description (static)                         | |
|  |                                               | |
|  |  +------------------+  +-------------------+  | |
|  |  | ISLAND:          |  | ISLAND:           |  | |
|  |  | Image Carousel   |  | Add to Cart       |  | |
|  |  | (client:visible) |  | (client:load)     |  | |
|  |  +------------------+  +-------------------+  | |
|  |                                               | |
|  |  Specifications (static)                      | |
|  |  More description (static)                    | |
|  |                                               | |
|  |  +---------------------------------------+   | |
|  |  | ISLAND: Comments Section              |   | |
|  |  | (client:idle)                         |   | |
|  |  +---------------------------------------+   | |
|  |                                               | |
|  +---------------------------------------------+ |
|  | Footer (static)                               | |
|  +---------------------------------------------+ |
+---------------------------------------------------+
```

The shell renders instantly. Each island hydrates according to its directive, progressively bringing the page to full interactivity without blocking the static content.

---

## 6. Island Communication Patterns

### 6.1 The Challenge

Islands run in isolation. Unlike an SPA where all components share a single React/Vue state tree, islands have no implicit shared context. Cross-island communication must be explicit.

### 6.2 Communication Strategies

#### 6.2.1 Shared Stores (Recommended)

The most robust approach. A store exists outside the component tree; islands subscribe to it.

```javascript
// store.js — shared between islands
import { atom } from "nanostores";

export const $cart = atom([]);

export function addToCart(item) {
  $cart.set([...$cart.get(), item]);
}

export function removeFromCart(id) {
  $cart.set($cart.get().filter(i => i.id !== id));
}
```

```javascript
// Island 1: AddToCart button
import { addToCart } from "./store.js";

class AddToCartButton extends HTMLElement {
  connectedCallback() {
    this.querySelector('button').addEventListener('click', () => {
      addToCart({ id: this.productId, name: this.productName });
    });
  }
}
```

```javascript
// Island 2: Cart badge (shows count)
import { $cart } from "./store.js";

class CartBadge extends HTMLElement {
  connectedCallback() {
    $cart.subscribe(items => {
      this.textContent = items.length;
    });
  }
}
```

**Trade-offs:**
- Single source of truth prevents sync drift.
- Works reliably with lazy hydration (store persists even if island has not loaded yet).
- Adds a dependency (though nanostores is under 1 KB).
- Recommended by Astro, Fresh (via Signals), and most islands frameworks.

#### 6.2.2 Custom Events

Framework-agnostic, zero-dependency communication via DOM events:

```javascript
// Island 1: dispatches event
document.dispatchEvent(new CustomEvent('cart:add', {
  detail: { id: 42, name: 'Widget Pro' }
}));

// Island 2: listens for event
document.addEventListener('cart:add', (e) => {
  updateBadge(e.detail);
});
```

**Trade-offs:**
- No external dependencies.
- Multiple sources of truth -- state can drift.
- **Vulnerable to ordering issues**: if Island 2 hydrates _after_ Island 1 dispatches the event, the event is missed. This is a real problem with lazy hydration directives like `client:visible`.

#### 6.2.3 URL State

For navigation-visible state, encode in URL parameters or hash:

```javascript
// Update URL when filter changes
const url = new URL(window.location);
url.searchParams.set('category', 'electronics');
history.pushState({}, '', url);

// Other islands read from URL on hydration
const category = new URL(window.location).searchParams.get('category');
```

**Trade-offs:**
- Survives page reload and bookmarking.
- Limited to serializable, URL-safe values.
- Good for filter state, pagination, selected tabs.

#### 6.2.4 Parent Element Attributes

A parent HTML element can mediate between child islands via attributes:

```html
<product-page data-selected-variant="blue">
  <variant-selector></variant-selector>  <!-- Sets attribute -->
  <product-gallery></product-gallery>    <!-- Reads attribute -->
</product-page>
```

Using `MutationObserver` or `attributeChangedCallback`, child islands can react to attribute changes on their parent.

### 6.3 How PyBend's Actor/Matrix Maps to This

PyBend's existing communication architecture is _already_ an island communication system:

- **Matrix (message bus)**: Acts as the shared communication backbone. All Components register with Matrix and route messages through it. This is functionally equivalent to a shared store/event bus hybrid.
- **TX (Transfer) messages**: The `TX` class provides typed, structured messages with `name`, `source`, `target`, and `data`. This is more structured than raw DOM events.
- **Actor addressing**: Each component has an `addr` (address) in the Actor tree. Messages route by address, not by direct reference. This decoupling is exactly what islands need.
- **Watchers/Observers**: The `watch()` and `notify()` pattern on `TT` (Transfer Type) enables reactive data propagation between islands without tight coupling.

The Matrix model is superior to raw DOM events for islands because:
1. It is not susceptible to event ordering issues (watchers receive current state on subscription).
2. It provides structured addressing instead of string event names.
3. It supports both push (notify) and pull (READ) patterns.
4. It naturally handles the case where an island hydrates late (watchers get immediate state on registration).

---

## 7. Performance Characteristics

### 7.1 Real-World Benchmark Data

#### Astro 2023 Web Framework Performance Report

Using Chrome's User Experience Report (CrUX) -- real-world data from millions of production websites:

- **Core Web Vitals pass rate**: Astro was the **only framework above 50%** of sites passing Google's CWV assessment. Next.js and Nuxt came in at roughly 1-in-4 and 1-in-5 websites passing, respectively.
- **LCP (Largest Contentful Paint)**: Only Astro and SvelteKit beat the average. Required threshold: 2.5 seconds.
- **CLS (Cumulative Layout Shift)**: Astro, SvelteKit, and Remix scored highest (all >75% passing).
- **FID (First Input Delay)**: Most frameworks pass (>80%), but islands frameworks had the highest scores (>95%).

#### Astro vs Next.js Head-to-Head (2025 benchmarks)

| Metric | Astro | Next.js (SSG) | Delta |
|--------|-------|---------------|-------|
| JavaScript bundle (documentation site) | ~18 KB | ~180 KB | **90% smaller** |
| Lighthouse Performance Score | 98-100 | 80-90 | **+10-20 points** |
| First Contentful Paint | ~0.5s | ~1.0-1.5s | **2-3x faster** |
| Lighthouse Score on Slow 4G | >95 | ~75 | **+20 points** |
| Content site with 100 posts (total JS) | <50 KB | 200+ KB | **75% smaller** |

Source: Multiple independent benchmark comparisons (Senorit.de, EastonDev, ReliaSoftware -- see sources section).

#### Why the Difference

Next.js, even with static export (SSG), bundles:
- React runtime (~40 KB gzipped)
- React DOM (~120 KB gzipped)
- Hydration logic
- Client-side router
- Framework metadata

Astro ships **zero JavaScript** by default. Only components with `client:*` directives contribute to the bundle. For a documentation site with a single search bar island, the total JS is just the search component.

#### eBay/Marko Production Data

Marko's compiler-automated islands achieved **60-84% JavaScript reductions** on eBay production pages, translating directly to improved TTI and conversion metrics.

### 7.2 Theoretical Performance Model

```
Traditional SSR:
  TTFB  ──▶ FCP ──▶ [download full JS bundle] ──▶ [parse + execute] ──▶ TTI
  fast       fast     ████████████████████████████     ██████████████████     slow

Islands:
  TTFB  ──▶ FCP ──▶ [download island JS only] ──▶ [hydrate islands] ──▶ TTI
  fast       fast     ████                             ██                      fast
                      (90% smaller)                    (only interactive parts)
```

The performance advantage is proportional to the ratio of static to interactive content. For a content-heavy page with a few interactive widgets (the common case for content sites, e-commerce, documentation), islands deliver dramatic improvements. For a fully interactive dashboard with no static content, the advantage diminishes.

---

## 8. The Island Granularity Question

### 8.1 When Something Is Too Small to Be an Island

An island has overhead:
- **Runtime cost**: The island coordinator must discover, observe, and hydrate the island.
- **Network cost**: Each island is a separate JavaScript chunk (though bundling can combine related islands).
- **Coordination cost**: If many tiny islands need to share state, the communication overhead exceeds the benefit.

**Too small**: A single toggle button, a tooltip, a "show more" link. The JavaScript for the hydration machinery outweighs the component's own code. Better to handle these with vanilla JavaScript attached to the static HTML, or group them into a larger island.

**Rule of thumb**: If the island's component code is less than ~2 KB, the overhead of island machinery (observer, loader, hydration) exceeds the benefit. Group it with a nearby island or use progressive enhancement (vanilla JS event listener on static HTML).

### 8.2 When Something Is Too Large to Be an Island

If an island encompasses most of the page, you have effectively returned to SPA-style full-page hydration. The "ocean" of static HTML disappears.

**Too large**: An entire page-level layout with navigation, content, and sidebar all in one island. A dashboard where every panel is interactive and interconnected. A complex form wizard where all steps are in one component.

**Rule of thumb**: If the island accounts for more than ~60% of the visible page, you are not benefiting from the pattern. Consider either: (a) decomposing it into smaller islands, or (b) accepting that this particular page is app-like and using a different rendering strategy.

### 8.3 Decision Framework

```
Is this region interactive?
  ├── No  → Static HTML. Not an island.
  └── Yes
       ├── Does it need to hydrate immediately?
       │    ├── Yes → client:load island
       │    └── No
       │         ├── Is it above the fold?
       │         │    ├── Yes → client:idle island
       │         │    └── No → client:visible island
       │         └── Does it only apply to certain viewports?
       │              └── Yes → client:media island
       └── Is it self-contained or does it need state from other islands?
            ├── Self-contained → Independent island
            └── Needs shared state → Use shared store, keep islands separate
```

### 8.4 The "Right" Boundary

The ideal island boundary corresponds to a **user-meaningful interactive unit**:

- A search bar with autocomplete
- An add-to-cart button with quantity selector
- A comment section with reply threads
- An image gallery with zoom and navigation
- A data table with sorting, filtering, and pagination

Each of these is a coherent feature that a user interacts with as a unit. They map naturally to web component boundaries.

---

## 9. Progressive Enhancement Within Islands

### 9.1 The HTML-First Philosophy

Islands architecture aligns deeply with progressive enhancement:

1. **Layer 1 -- HTML**: The static shell delivers all content. Links work. Information is accessible. The page is usable without JavaScript.

2. **Layer 2 -- CSS**: The shell is styled. Layout, typography, and visual design are applied. Still no JavaScript needed.

3. **Layer 3 -- JavaScript (islands)**: Interactive features are added. Forms validate. Carousels animate. Search autocompletes.

If JavaScript fails (network error, script blocked, slow connection), Layers 1 and 2 still work. The user can read content, follow links, and submit forms (if the forms use standard HTML submission).

### 9.2 Graceful Degradation in Practice

```html
<!-- Island: Image carousel -->
<image-carousel>
  <!-- Without JS: all images visible in a stack -->
  <img src="/img1.jpg" alt="Product front">
  <img src="/img2.jpg" alt="Product side">
  <img src="/img3.jpg" alt="Product back">
</image-carousel>

<!-- With JS: carousel with navigation, thumbnails, zoom -->
```

```html
<!-- Island: Add to cart -->
<form action="/cart/add" method="POST">
  <input type="hidden" name="product_id" value="42">
  <input type="number" name="quantity" value="1" min="1">
  <button type="submit">Add to Cart</button>
</form>
<!-- Without JS: standard form submission to server -->
<!-- With JS: AJAX submission, cart badge update, animation -->
```

### 9.3 The `[ready]` Pattern

11ty's `<is-land>` adds a `[ready]` attribute when hydration completes. This enables CSS-based progressive enhancement:

```css
/* Before hydration: show basic static appearance */
is-land image-carousel img {
  display: block;
  margin-bottom: 1rem;
}

/* After hydration: carousel layout with transitions */
is-land[ready] image-carousel img {
  display: none;
}
is-land[ready] image-carousel img.active {
  display: block;
}
```

---

## 10. Practical Patterns

### 10.1 Island-Per-Component vs Island-Per-Feature vs Island-Per-Interaction

**Island-per-component**: Each interactive web component is its own island.
- Example: `<search-bar>`, `<add-to-cart>`, `<like-button>` are each separate islands.
- Pros: Maximum isolation, finest-grained lazy loading.
- Cons: Many small islands; state sharing overhead if components need to coordinate.

**Island-per-feature**: A group of related components forms one island.
- Example: The entire "product actions" area (add-to-cart + wishlist + share buttons) is one island.
- Pros: Shared state stays within the island. Fewer coordination points.
- Cons: Larger island means more JavaScript for the group.

**Island-per-interaction**: An island exists only around the specific DOM region that requires event handling.
- Example: A static product card with only the "favorite" button as an island.
- Pros: Absolute minimum JavaScript.
- Cons: May fragment the component model; harder to maintain.

**Recommendation for PyBend**: Island-per-component aligns best with PyBend's web component architecture. Each `<ntt-item>`, `<ntt-list>`, `<ntt-method>` is a natural island. The Actor/Matrix message bus handles cross-island communication without requiring islands to share a component tree.

### 10.2 Nested Islands

Islands can nest, with important implications:

```html
<ntt-list model="Product">          <!-- Outer island: list -->
  <ntt-item display="sm">           <!-- Inner island: item -->
    <ntt-method action="favorite">  <!-- Innermost island: method button -->
    </ntt-method>
  </ntt-item>
</ntt-list>
```

Rules for nesting:
- **Outer islands hydrate first** (or at least their hydration conditions are met first). In 11ty's `<is-land>`, child islands inherit parent conditions -- they cannot hydrate until the parent does.
- **Inner islands should not depend on outer island state for their initial render.** The server-rendered HTML should be self-sufficient for the initial display.
- **Communication flows through the message bus**, not through direct parent-child references. This maintains isolation.

### 10.3 Shared Islands

Multiple pages may share the same island component (e.g., navigation bar, search, user menu). In a build-time framework like Astro, these are de-duplicated into shared chunks. In a runtime system like PyBend, the component class is loaded once and reused.

### 10.4 Island Lazy-Loading Strategies

| Strategy | Mechanism | When to Use |
|----------|-----------|-------------|
| **Eager** | Load island JS in `<head>` or early `<body>` | Critical-path islands (auth, primary CTA) |
| **Idle** | `requestIdleCallback()` | Important but not blocking (secondary navigation, analytics) |
| **Viewport** | `IntersectionObserver` | Below-fold content (comments, related items, footer widgets) |
| **Interaction** | Event listener (click, hover, focus) | Islands that are static until user engages (expandable sections, dropdowns) |
| **Route-based** | Load on navigation to a specific view | SPAs/MPAs with route-level islands |
| **Media query** | `matchMedia()` | Mobile-only or desktop-only islands |

For PyBend, the most natural strategies are:
- **Viewport**: `<ntt-list>` elements below the fold load when scrolled into view.
- **Idle**: Schema-driven DynamicClass creation happens at idle time.
- **Eager**: The primary content list on the page hydrates immediately.

---

## 11. How This Maps to PyBend

### 11.1 Current Architecture

PyBend's frontend is currently a **fully client-side application**:

1. The browser loads `matrix.html` (or equivalent entry point).
2. JavaScript modules load: `Matrix.js`, `NTT.js`, `Component.js`, component definitions.
3. `<ntt-list model="Product">` in the HTML triggers schema fetch (`GET /Product`).
4. `NTT.SCHEMA()` creates a `DynamicClass` from the schema.
5. `DynamicClass` triggers `READ` to fetch entity data.
6. Components render entirely client-side.

This is closer to an SPA than an islands architecture. The "shell" is minimal HTML with component tags. All rendering happens after JavaScript loads and schemas are fetched.

### 11.2 Which Components Are Natural Islands

| Component | Island Type | Rationale |
|-----------|------------|-----------|
| `<ntt-list>` | **Client island** (viewport/idle) | Interactive: handles pagination, selection, click-to-navigate. Needs schema + data. |
| `<ntt-item>` | **Client island** (viewport) | Interactive: edit toggle, delete, click-to-select. Needs schema + entity data. |
| `<ntt-method>` | **Client island** (visible) | Interactive: button that calls a backend method. Needs schema method definition. |
| `<ntt-router>` | **Client island** (load) | Interactive: handles navigation, view swapping. Core shell interaction. |
| Navigation/header | **Static shell** | Layout chrome: links, branding. Can be pure HTML. |
| Footer | **Static shell** | Static content. |
| Skeleton placeholders | **Static shell** | The `placeholder()` method in `NTTItem` generates bone HTML. This should be server-rendered. |
| Form fields (display mode) | **Static shell** (potentially) | When displaying (not editing) entity data, the rendered HTML is static text. |

### 11.3 How the Schema Informs Island Boundaries

PyBend's schema is the perfect mechanism for determining island boundaries:

```python
__ui__ = {
    'renderer': {
        'item': 'ntt-item',      # → this tag becomes a client island
        'list': 'ntt-list',      # → this tag becomes a client island
        'detail': 'ntt-detail',  # → this tag becomes a client island
    },
}
```

The schema's `ui.renderer` map already identifies which custom elements will be used. The `methods` section identifies which elements need `<ntt-method>` islands. The `access` rules determine whether edit/delete buttons (and their associated JavaScript) are needed for a given user.

A server-side shell generator could:

1. Read the schema at build/request time.
2. Generate static HTML for the layout, navigation, and placeholder content.
3. Emit custom element tags (`<ntt-list>`, `<ntt-item>`) with the necessary attributes (`model`, `display`, `ref`).
4. Include pre-rendered skeleton placeholders inside the custom elements (using the same bone HTML that `NTTItem.placeholder()` currently generates client-side).
5. Include hydration scripts for only the islands that the page needs.

### 11.4 How the Actor/Matrix System Relates

The Actor/Matrix system is PyBend's island communication layer:

- **Matrix** = shared message bus (equivalent to Astro's `nanostores` or Fresh's `signals`)
- **TX** = structured message format (superior to raw `CustomEvent`)
- **Component addresses** = island identifiers (each island has a unique `addr`)
- **Watchers/Observers** = reactive subscriptions (islands react to data changes from other islands)
- **DynamicClass** = shared entity registry (all islands for the same model type share a single DynamicClass, which acts as a shared store)

This architecture already solves the hardest problem in islands: **cross-island state synchronization**. When `<ntt-item>` saves an entity, the `DynamicClass` notifies all watchers (including `<ntt-list>` elements showing that entity), and they update automatically. No manual event coordination needed.

### 11.5 Adoption Path for PyBend

A pragmatic adoption path:

**Phase 1: Static Shell Generation (Server-Side)**
- Generate the HTML document server-side (Python/Jinja2 or direct string generation).
- Emit the layout structure (nav, main, footer) as static HTML.
- Emit `<ntt-list model="Product">` tags with pre-rendered skeleton content inside.
- The JavaScript modules load and upgrade these elements as before, but the user sees a structured page immediately.

**Phase 2: Schema-Aware Pre-Rendering**
- When generating the page, fetch the schema server-side.
- Pre-render entity data into the custom elements as static HTML (display mode only).
- The custom elements upgrade and add interactivity, reusing the pre-rendered DOM where possible.
- This gives FCP with real content, not just skeletons.

**Phase 3: Hydration Directives**
- Implement an `<is-land>`-like wrapper (or integrate `@11ty/is-land` directly) to defer component JS loading.
- Below-fold `<ntt-list>` elements load their JS only when scrolled into view.
- `<ntt-method>` buttons load on interaction (first click).
- The schema's `access` rules determine whether to even include the edit/delete island scripts.

**Phase 4: Server Islands for Personalized Content**
- For authenticated/personalized content (user-specific lists, permission-gated actions), use a server island pattern: render the shell statically, defer personalized regions to server-rendered fragments fetched after page load.

---

## 12. Limitations and Anti-Patterns

### 12.1 When NOT to Use Islands

- **Highly interactive applications**: Social media feeds, real-time collaboration tools, complex dashboards where nearly every pixel is interactive. These would require "thousands of islands," effectively recreating an SPA with extra overhead.
- **Applications requiring client-side routing with state preservation**: Islands are naturally MPA (multi-page app). Adding client-side routing requires bridging that SPAs handle natively. (Next.js PPR addresses this, but at the cost of React's complexity.)
- **Applications with deeply interconnected state**: If every component on the page depends on global state that changes frequently, the island isolation becomes a burden rather than a benefit.

### 12.2 The "Too Many Islands" Problem

If a page has 50+ islands, you encounter:
- **Observer overhead**: Each island registers an `IntersectionObserver` entry. Hundreds of observers are not free.
- **Network waterfalling**: If each island is a separate JS chunk, the browser may make many small requests instead of one large one.
- **Coordination complexity**: Many islands sharing state through a store creates implicit coupling that is harder to debug than explicit component-tree state flow.

**Mitigation**: Bundle related islands into shared chunks. Use `client:idle` or `client:visible` to stagger loading. Group tightly-coupled components into a single larger island.

### 12.3 State Synchronization Complexity

When two islands need to stay in sync:

**Anti-pattern**: Each island fetches its own copy of the data.
```
Island A: fetch('/api/cart') → renders count
Island B: fetch('/api/cart') → renders items
// Two requests, two sources of truth, potential drift
```

**Correct pattern**: Both islands subscribe to a shared store.
```
Store: fetch('/api/cart') once → $cart signal
Island A: subscribe($cart) → renders count
Island B: subscribe($cart) → renders items
// One request, one source of truth
```

In PyBend, this is already handled by the DynamicClass registry. All `<ntt-item>` elements for the same entity subscribe to the same DynamicClass instance, which holds the canonical data.

### 12.4 SEO Edge Cases

- **Server Islands/Deferred Content**: Content rendered via server islands (Astro `server:defer`) is fetched by client-side scripts. Search engine crawlers may or may not execute this JavaScript. Critical SEO content should be in the static shell, not in deferred islands.
- **Client Islands**: Content inside `<template data-island>` is inert and not visible to crawlers. Ensure meaningful fallback content is outside the template for SEO.
- **Declarative Shadow DOM**: As of 2025, major search engines handle DSD inconsistently. Critical content should remain in light DOM, not exclusively in shadow DOM.

### 12.5 Migration Difficulty

Converting an existing SPA to islands architecture is non-trivial:
- Component boundaries must be re-evaluated for island suitability.
- Global state must be decomposed into island-local and shared-store state.
- Client-side routing must be replaced with MPA navigation or a hybrid approach.
- Server rendering infrastructure must be added.

For PyBend, the migration is more tractable because:
- Components are already web components (natural island boundaries).
- State already flows through the Actor/Matrix bus (natural shared store).
- Schema-driven rendering means the server can generate the same structure the client would.
- The primary challenge is adding server-side HTML generation, not restructuring the component model.

---

## 13. Sources

### Primary Sources

- [Islands Architecture -- Jason Miller (jasonformat.com)](https://jasonformat.com/islands-architecture/) -- The original 2020 formulation.
- [Astro Islands Documentation](https://docs.astro.build/en/concepts/islands/) -- Official Astro islands architecture documentation.
- [Astro Server Islands Documentation](https://docs.astro.build/en/guides/server-islands/) -- Server-deferred rendering in Astro 5.
- [Server Islands | Astro Blog](https://astro.build/blog/future-of-astro-server-islands/) -- Astro team's explanation of server islands.
- [Fresh Islands Documentation (Deno)](https://fresh.deno.dev/docs/concepts/islands) -- Official Fresh islands documentation.
- [11ty `<is-land>` GitHub Repository](https://github.com/11ty/is-land) -- Source and documentation for the `<is-land>` web component.
- [11ty Partial Hydration Documentation](https://www.11ty.dev/docs/plugins/is-land/) -- Official 11ty `<is-land>` plugin documentation.

### Framework and Pattern Analysis

- [Islands Architecture -- patterns.dev](https://www.patterns.dev/vanilla/islands-architecture/) -- Comprehensive technical overview and framework comparison.
- [Sharing State with Islands Architecture -- Frontend at Scale](https://frontendatscale.com/blog/islands-architecture-state/) -- Detailed analysis of cross-island communication patterns.
- [Share State Between Islands -- Astro Recipes](https://docs.astro.build/en/recipes/sharing-state-islands/) -- Astro's recommended state sharing with Nano Stores.
- [Fresh State Sharing Between Islands](https://fresh.deno.dev/docs/examples/sharing-state-between-islands) -- Fresh's signal-based state sharing.
- [Islands & Server Components & Resumability, Oh My! -- DEV Community](https://dev.to/this-is-learning/islands-server-components-resumability-oh-my-319d) -- Technical comparison of islands, RSC, and resumability.
- [Marko: Compiling Fine-Grained Reactivity -- DEV Community](https://dev.to/ryansolid/marko-compiling-fine-grained-reactivity-4lk4) -- Marko's compiler-automated islands approach.

### Performance Data

- [2023 Web Framework Performance Report -- Astro](https://astro.build/blog/2023-web-framework-performance-report/) -- Real-world CrUX data comparing framework CWV pass rates.
- [Astro vs Next.js 2025: The Ultimate Framework Comparison -- Senorit.de](https://senorit.de/en/blog/astro-vs-nextjs-2025) -- Head-to-head benchmark data.
- [Astro vs Next.js: The Technical Truth Behind 40% Faster Static Site Performance -- EastonDev](https://eastondev.com/blog/en/posts/dev/20251202-astro-vs-nextjs-comparison/) -- Independent benchmark comparison.
- [Astro vs Next.js: Which Framework is Better in 2025? -- ReliaSoftware](https://reliasoftware.com/blog/astro-vs-next-js) -- Performance and use-case comparison.

### Web Components and SSR

- [Island Architecture with Web Components -- Enhance/DEV Community](https://dev.to/begin/island-architecture-with-web-components-3hnp) -- Web components as natural islands.
- [Server-side rendering (SSR) -- Lit](https://lit.dev/docs/ssr/overview/) -- Lit SSR documentation.
- [Declarative Shadow DOM -- web.dev](https://web.dev/articles/declarative-shadow-dom) -- Declarative Shadow DOM specification and usage.
- [defer-hydration in Web Components -- zachleat.com](https://www.zachleat.com/web/defer-hydration/) -- Community standard for deferred hydration.
- [Enhance vs. Lit vs. WebC -- The Spicy Web](https://www.spicyweb.dev/web-components-ssr-node/) -- Comparison of web component SSR approaches.

### Hydration and Progressive Enhancement

- [Astro Client Directives Reference](https://docs.astro.build/en/reference/directives-reference/) -- Complete directive documentation.
- [Astro's Client Directives: When and Where to Use Each -- DEV Community](https://dev.to/lovestaco/astros-client-directives-when-and-where-to-use-each-165g) -- Practical directive usage guide.
- [Lazy loading Web Components with Intersection Observer -- lamplightdev](https://lamplightdev.com/blog/2020/03/20/lazy-loading-web-components-with-intersection-observer/) -- Web component lazy loading implementation.
- [Application Shell Architecture -- Chrome Developers](https://developer.chrome.com/blog/app-shell) -- Google's app shell model documentation.

### Next.js PPR

- [Partial Prerendering -- Next.js Documentation](https://nextjs.org/docs/15/app/getting-started/partial-prerendering) -- Official PPR documentation.
- [Partial Prerendering with Next.js -- Vercel Blog](https://vercel.com/blog/partial-prerendering-with-next-js-creating-a-new-default-rendering-model) -- Vercel's PPR announcement and technical explanation.
- [Unlocking the Future of Web Performance: Partial Prerendering in Next.js 16 -- Medium](https://medium.com/@sureshdotariya/unlocking-the-future-of-web-performance-partial-prerendering-in-next-js-f3dc0b16bf34) -- PPR in Next.js 16.
