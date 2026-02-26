# Hydration Strategies for Server-Side Rendering

**Research Document -- PyBend SSR Analysis, Part 5**
**Date:** 2026-02-25 | **Audience:** Technical CEO + Engineering Leadership

---

## Executive Summary

Hydration is the process of making server-rendered HTML interactive by attaching
JavaScript event listeners, restoring application state, and reconnecting
component logic on the client. It is the single most consequential performance
challenge in any SSR implementation. Get it right and users see content instantly
that *also* responds instantly. Get it wrong and you create what the industry
calls the **"uncanny valley"** -- a page that *looks* ready but silently ignores
every click, scroll, and keystroke for hundreds of milliseconds to several
seconds.

For PyBend specifically, hydration is uniquely challenging because:

1. **DynamicClasses are created at runtime from schema** -- there is no static
   class definition the server can reference ahead of time.
2. **The Actor/Matrix message bus** must be re-initialized and reconnected
   before any component can send or receive messages.
3. **Web Components with Shadow DOM** require Declarative Shadow DOM (DSD) for
   SSR, a standard that only reached baseline browser support in February 2024.

This document maps every major hydration strategy against PyBend's architecture,
quantifies the performance costs involved, and identifies the path that best
fits PyBend's schema-driven, actor-based design.

> **Bottom line for the CEO:** Hydration is where SSR projects either deliver
> their promised performance gains or silently erase them. The wrong strategy
> can make your SSR investment produce pages that are *slower* to interact with
> than a pure client-rendered app. The right strategy -- likely progressive
> hydration with an islands-inspired approach -- can cut Time to Interactive
> by 40-60% while preserving PyBend's zero-configuration developer experience.

---

## Table of Contents

1. [What Is Hydration and Why Does It Matter?](#1-what-is-hydration-and-why-does-it-matter)
2. [The Hydration Strategy Landscape](#2-the-hydration-strategy-landscape)
3. [Traditional (Full) Hydration](#3-traditional-full-hydration)
4. [Progressive Hydration](#4-progressive-hydration)
5. [Selective Hydration](#5-selective-hydration)
6. [Partial Hydration](#6-partial-hydration)
7. [Resumability (Qwik's Approach)](#7-resumability-qwiks-approach)
8. [Islands Architecture (Astro's Approach)](#8-islands-architecture-astros-approach)
9. [Declarative Shadow DOM -- The SSR Enabler for Web Components](#9-declarative-shadow-dom----the-ssr-enabler-for-web-components)
10. [How Existing Libraries Handle Web Component Hydration](#10-how-existing-libraries-handle-web-component-hydration)
11. [Hydrating an Actor-Based System (Matrix Message Bus)](#11-hydrating-an-actor-based-system-matrix-message-bus)
12. [Event Replay vs Event Delegation During Hydration](#12-event-replay-vs-event-delegation-during-hydration)
13. [Measuring Hydration Cost](#13-measuring-hydration-cost)
14. [The Uncanny Valley Problem](#14-the-uncanny-valley-problem)
15. [Hydration Errors and Mismatches](#15-hydration-errors-and-mismatches)
16. [PyBend's DynamicClass System and Hydration](#16-pybends-dynamicclass-system-and-hydration)
17. [Recommendation for PyBend](#17-recommendation-for-pybend)
18. [Sources](#18-sources)

---

## 1. What Is Hydration and Why Does It Matter?

### The Core Problem

SSR sends fully-rendered HTML to the browser, which the browser can paint
immediately. This produces an excellent **First Contentful Paint (FCP)** -- the
user sees content fast. But that content is *dead*. Buttons do not respond.
Forms do not submit. Navigation does not work. The HTML is a photograph of
an application, not the application itself.

**Hydration** is the process of turning that photograph into a living
application. It involves:

```
 SERVER-RENDERED HTML (static, non-interactive)
         |
         v
 +--------------------------+
 |       HYDRATION          |
 |                          |
 |  1. Download JS bundle   |
 |  2. Parse & execute JS   |
 |  3. Recreate component   |
 |     tree in memory       |
 |  4. Walk the DOM to      |
 |     match components     |
 |     to existing nodes    |
 |  5. Attach event          |
 |     listeners            |
 |  6. Restore application  |
 |     state                |
 |  7. Reconnect data       |
 |     subscriptions        |
 +--------------------------+
         |
         v
 INTERACTIVE APPLICATION (responds to user input)
```

### Why Hydration Is the Biggest SSR Bottleneck

Hydration is expensive because it duplicates much of the work the server
already did. The server rendered the component tree once. The client must
reconstruct that tree *again* -- not to produce HTML (the HTML already exists)
but to build the in-memory data structures that make interactivity possible.

Key cost drivers:

| Cost Factor | Impact |
|---|---|
| **JS bundle download** | Entire framework + app code must arrive before hydration starts |
| **JS parse + compile** | V8/SpiderMonkey must parse every byte of JavaScript |
| **Component tree reconstruction** | Framework walks the full tree, instantiating every component |
| **DOM reconciliation** | Framework compares its virtual tree against the actual DOM |
| **Event listener attachment** | Every interactive element gets listeners bound |
| **State restoration** | Application state must be deserialized and injected |
| **Main thread blocking** | All of the above happens on the main thread, blocking user interaction |

The result: SSR can *improve* FCP while *worsening* Time to Interactive (TTI)
compared to pure client-side rendering. The page appears faster but becomes
usable slower. Research from Google shows that hydration commonly creates a
**200ms-2000ms+ gap between FCP and TTI** depending on application complexity
and device capability ([web.dev, "Rendering on the Web"](https://web.dev/articles/rendering-on-the-web)).

> **For the CEO:** Think of SSR without good hydration like a restaurant that
> seats you immediately (great first impression) but then makes you wait 30
> minutes for a menu. The customer can *see* the restaurant is open, but they
> cannot *do* anything. Hydration strategy determines how long that wait is.

---

## 2. The Hydration Strategy Landscape

The industry has developed multiple strategies to address hydration's cost.
They differ along two axes: **what** gets hydrated and **when** it gets
hydrated.

```
                        WHAT gets hydrated?
                 Everything ◄──────────► Only interactive parts
                     |                         |
              ┌──────┴──────┐           ┌──────┴──────┐
    WHEN?     │  Traditional │           │   Partial    │
    All at    │  Hydration   │           │   Hydration  │
    once      │  (React 17)  │           │   (Astro)    │
              └─────────────┘           └──────────────┘
                     |                         |
              ┌──────┴──────┐           ┌──────┴──────┐
    WHEN?     │  Selective   │           │   Islands    │
    Priori-   │  Hydration   │           │   Arch.      │
    tized     │  (React 18)  │           │              │
              └─────────────┘           └──────────────┘
                     |                         |
              ┌──────┴──────┐           ┌──────┴──────┐
    WHEN?     │  Progressive │           │  Resumable   │
    Deferred  │  Hydration   │           │  (Qwik)      │
    /lazy     │              │           │  [No hydra-  │
              └─────────────┘           │   tion at    │
                                        │   all]       │
                                        └──────────────┘
```

The conceptual distinction is critical:

- **Progressive hydration** is about the **WHEN** -- deferring hydration of
  less-important components along a time axis.
- **Partial hydration** is about the **WHAT** -- skipping hydration entirely
  for components that never need interactivity.
- **Selective hydration** is about **PRIORITY** -- hydrating what the user is
  actively interacting with first.
- **Resumability** is about **ELIMINATION** -- avoiding hydration altogether
  by serializing enough state into the HTML that the application can resume
  where the server left off.

([DEV Community, "The difference between progressive and partial hydration"](https://dev.to/theiaz/-the-difference-between-progressive-and-partial-hydration-18dd))

---

## 3. Traditional (Full) Hydration

### How It Works

The client downloads the full JavaScript bundle, executes it, reconstructs the
entire component tree, walks the existing DOM to reconcile it with the virtual
tree, and attaches all event listeners at once.

```
Timeline:
  0ms     200ms    500ms    800ms   1200ms   1800ms   2500ms
  |--------|--------|--------|--------|--------|--------|
  FCP                                              TTI
  [paint]  [download JS............][parse][hydrate all]
           ◄──────── UNCANNY VALLEY ────────────────►
           Page visible but non-interactive
```

### Characteristics

| Aspect | Assessment |
|---|---|
| **Implementation complexity** | Low -- standard in React 17, Vue 2 |
| **FCP** | Excellent (full HTML from server) |
| **TTI** | Poor -- entire app must hydrate before anything works |
| **JS bundle size** | Full bundle required upfront |
| **Main thread blocking** | Severe -- single long task |
| **Suitability for PyBend** | Poor -- every DynamicClass would need to hydrate |

### Why It Fails at Scale

On a PyBend product listing page with 20 products, each containing comments
with nested methods (like, favorite), full hydration means:

- Instantiate `NTT` type registry
- Fetch and process schema for `Product`, `Comment`, `Like`
- Create DynamicClasses for each type
- Initialize the Matrix message bus + NetworkAdapter
- Register every Actor (each product, each comment)
- Attach listeners to every edit button, delete button, method button
- All of this **before any single button responds to a click**

---

## 4. Progressive Hydration

### How It Works

Instead of hydrating the entire page at once, progressive hydration defers
hydration of non-critical components. Components are hydrated based on triggers:

- **Viewport visibility** -- hydrate when the user scrolls to the component
- **Idle time** -- hydrate during `requestIdleCallback` windows
- **User interaction** -- hydrate when the user hovers over or clicks near
- **Timer** -- hydrate after a fixed delay

```
Timeline:
  0ms     200ms    500ms    800ms   1200ms   1800ms
  |--------|--------|--------|--------|--------|
  FCP     TTI(above fold)         TTI(below fold)
  [paint]  [hydrate header+nav]
                    [hydrate product cards]
                              [idle: hydrate sidebar]
                                        [scroll: hydrate comments]
```

### Measured Benefits

Developer reports indicate **TTI reductions of 500-800ms on mobile** when
switching from full to progressive hydration on marketplace applications
([The New Stack, "Mastering Progressive Hydration"](https://thenewstack.io/mastering-progressive-hydration-for-enhanced-web-performance/)).
Next.js 17 reported **up to 50% TTI reduction** for e-commerce applications
through hydration improvements
([Markaicode, "Next.js 17 Hydration Overhaul"](https://markaicode.com/nextjs-17-hydration-performance-ecommerce/)).

### PyBend Applicability

**High.** Progressive hydration maps well to PyBend's component hierarchy:

| Priority | Component | Trigger |
|---|---|---|
| **P0 (immediate)** | Navigation, auth status, search | Page load |
| **P1 (fast)** | `ntt-list` above fold, primary `ntt-item` cards | Load + idle |
| **P2 (deferred)** | Below-fold items, `ntt-method` buttons | Viewport or hover |
| **P3 (lazy)** | Edit forms, comments, nested entities | User interaction |

The challenge: PyBend's `ntt-item` components currently render via `connectedCallback()`,
which fires as soon as the element enters the DOM. Progressive hydration would
require a mechanism to defer this callback or replace it with a hydration-aware
lifecycle.

---

## 5. Selective Hydration

### How It Works

Introduced in React 18, selective hydration combines streaming SSR with
priority-based hydration. The key innovation: **if a user interacts with a
component that has not yet been hydrated, that component jumps to the front
of the hydration queue.**

```
  User clicks "Add to Cart" on Product #3
         |
         v
  ┌──────────────────────────────────────────┐
  │  Hydration scheduler detects interaction  │
  │  on un-hydrated component                │
  │                                           │
  │  1. Pause current hydration work          │
  │  2. Synchronously hydrate Product #3      │
  │  3. Replay the click event                │
  │  4. Resume background hydration           │
  └──────────────────────────────────────────┘
```

### Characteristics

| Aspect | Assessment |
|---|---|
| **Implementation complexity** | Medium-high (requires Suspense boundaries) |
| **Perceived interactivity** | Excellent -- user's action always gets response |
| **JS bundle** | Still full bundle, but streaming allows earlier start |
| **Framework dependency** | React 18+ specific; not directly available for vanilla JS |

([React Working Group, "New in 18: Selective Hydration"](https://github.com/reactwg/react-18/discussions/130))

### PyBend Applicability

**Medium.** The core insight -- prioritize hydration of what the user is
touching -- is framework-agnostic and can be implemented in PyBend's Actor
system. When the Matrix receives an event targeting an un-hydrated component,
it could trigger that component's hydration before dispatching the event.

---

## 6. Partial Hydration

### How It Works

Partial hydration takes a fundamentally different approach: **static components
never receive JavaScript at all.** The build system or framework analyzes the
component tree and classifies each component as either interactive (needs JS)
or static (HTML only, zero JS shipped).

```
  ┌──────────────────────────────────────────────────────┐
  │                    PAGE                               │
  │                                                       │
  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │
  │  │   HEADER    │  │  PRODUCT    │  │   SIDEBAR    │ │
  │  │  (static)   │  │   CARD      │  │  (static)    │ │
  │  │  0 KB JS    │  │ (interactive)│  │  0 KB JS     │ │
  │  │             │  │  12 KB JS   │  │              │ │
  │  └─────────────┘  └─────────────┘  └──────────────┘ │
  │                                                       │
  │  ┌─────────────┐  ┌─────────────┐                    │
  │  │ DESCRIPTION │  │  COMMENTS   │                    │
  │  │  (static)   │  │ (interactive)│                    │
  │  │  0 KB JS    │  │  8 KB JS    │                    │
  │  └─────────────┘  └─────────────┘                    │
  │                                                       │
  │  Total JS: 20 KB (vs 85 KB with full hydration)      │
  └──────────────────────────────────────────────────────┘
```

### Measured Benefits

Gatsby's implementation of partial hydration demonstrated **up to 83% reduction
in client-side JavaScript** for content-heavy pages
([Gatsby, "Partial Hydration"](https://www.gatsbyjs.com/docs/conceptual/partial-hydration/)).

### PyBend Applicability

**Medium-Low.** PyBend's components are generally all interactive -- even
display-mode `ntt-item` elements have click handlers for navigation. However,
the concept applies to specific contexts: product descriptions, static
metadata fields, and read-only comment text do not need JavaScript.

---

## 7. Resumability (Qwik's Approach)

### How It Works

Resumability eliminates hydration entirely. Instead of the client re-executing
the application to reconstruct state, Qwik **serializes everything into the
HTML itself**: component boundaries, event listener locations, application
state, and even closure references.

```
 TRADITIONAL HYDRATION                   RESUMABILITY (QWIK)
 ========================                ========================

 Server renders HTML                     Server renders HTML
        |                                       |
        v                                       v
 Client downloads JS (all)               Client downloads 0 JS
        |                                       |
        v                                       v
 Client re-executes app                  User clicks a button
        |                                       |
        v                                       v
 Client attaches listeners               Browser loads ONLY the
        |                                handler for that button
        v                                       |
 Page interactive (all)                         v
                                          Handler executes
                                          (rest of page untouched)
```

The key mechanism is serialization into HTML:

```html
<!-- Qwik serializes event bindings directly into HTML attributes -->
<button on:click="./chunk-abc.js#handleClick[0]"
        q:id="3">
  Add to Cart
</button>

<!-- State is serialized as JSON in a script tag -->
<script type="qwik/json">
  {"objs": [{"count": 5, "product": "Widget"}], "refs": {"3": "0"}}
</script>
```

When the user clicks the button, Qwik's tiny (< 1KB) event listener intercepts
the click, lazy-loads `chunk-abc.js`, deserializes the associated state, and
executes `handleClick`. No other component is touched.

### Measured Benefits

- **Near-zero JavaScript execution at startup** -- TTI approximately equals FCP
- **Sub-100ms interactivity** for initial actions on complex apps
- **O(1) startup time** regardless of application complexity (vs O(n) for hydration)

([Builder.io, "Resumability vs Hydration"](https://www.builder.io/blog/resumability-vs-hydration);
[Qwik Documentation, "Resumable"](https://qwik.dev/docs/concepts/resumable/))

### Applicability to Web Components

Qwik's resumability model is tightly coupled to Qwik's own component system
and compiler. It cannot be directly applied to vanilla Web Components because:

1. **Qwik's compiler** performs static analysis to extract event handlers and
   generate lazy-loadable chunks. Vanilla Web Components have no such compiler.
2. **Qwik's serialization format** encodes Qwik-specific internal structures
   (signal graphs, component boundaries) that do not exist in the Custom
   Elements API.
3. **DynamicClass creation** in PyBend happens at runtime from schema data --
   there is no compile-time class definition for a compiler to analyze.

However, the **principle** of resumability -- serialize state into HTML and
lazy-load handlers on interaction -- can be partially adopted:

> **Applicable pattern for PyBend:** Serialize entity data and schema URLs
> into `data-*` attributes or `<script type="application/json">` blocks within
> each `<ntt-item>`. On interaction, load only the specific handler needed.
> This avoids full hydration while preserving the schema-driven model.

---

## 8. Islands Architecture (Astro's Approach)

### How It Works

Islands architecture treats the page as a sea of static HTML with isolated
"islands" of interactivity. Each island hydrates independently, with its own
JavaScript, its own timing, and its own state. Static content between islands
ships zero JavaScript.

```
  ┌──────────────────────────────────────────────────────────┐
  │                   STATIC HTML (0 KB JS)                  │
  │                                                          │
  │    ┌────────────┐         ┌──────────────────────────┐  │
  │    │ SEARCH BAR │         │     PRODUCT CAROUSEL     │  │
  │    │  Island    │         │       Island              │  │
  │    │ client:load│         │    client:visible         │  │
  │    │  3 KB JS   │         │      15 KB JS             │  │
  │    └────────────┘         └──────────────────────────┘  │
  │                                                          │
  │    Product Description (static HTML, 0 KB JS)            │
  │                                                          │
  │    ┌──────────────┐    ┌──────────────────────────────┐ │
  │    │ ADD TO CART  │    │        REVIEWS               │ │
  │    │   Island     │    │         Island                │ │
  │    │ client:idle  │    │      client:visible           │ │
  │    │   5 KB JS    │    │        12 KB JS               │ │
  │    └──────────────┘    └──────────────────────────────┘ │
  │                                                          │
  └──────────────────────────────────────────────────────────┘
```

### Why Web Components Are Natural Islands

This is a critical insight for PyBend: **Web Components are already islands.**

Every `<ntt-item>`, `<ntt-list>`, `<ntt-method>` is a Custom Element with
Shadow DOM encapsulation. They have:

- **Isolated rendering** -- Shadow DOM prevents style and DOM leakage
- **Self-contained lifecycle** -- `connectedCallback`, `disconnectedCallback`
- **Independent state** -- each component manages its own data
- **Explicit boundaries** -- the custom element tag *is* the island boundary

The mapping is natural:

| Islands Concept | PyBend Equivalent |
|---|---|
| Island boundary | Custom Element tag (`<ntt-item>`, `<ntt-list>`) |
| Island JavaScript | Component module (`ntt-item.js`, `ntt-list.js`) |
| Static HTML sea | Server-rendered entity data between components |
| `client:load` directive | `connectedCallback()` triggers immediately |
| `client:visible` directive | IntersectionObserver triggers hydration |
| `client:idle` directive | `requestIdleCallback` triggers hydration |

([Enhance, "Island Architecture with Web Components"](https://enhance.dev/blog/posts/2024-07-09-island-architecture-with-web-components);
[patterns.dev, "Islands Architecture"](https://www.patterns.dev/vanilla/islands-architecture/))

### PyBend Applicability

**Very High.** This is the most natural fit for PyBend's existing architecture.
The framework already organizes the UI as isolated Web Components. An SSR
implementation could:

1. Server-render each `<ntt-item>` as static HTML with Declarative Shadow DOM
2. Include entity data in `data-*` attributes or inline `<script>` blocks
3. Add hydration directives (e.g., `hydrate="visible"`) to control when each
   component's JavaScript activates
4. Let each component self-hydrate independently via its existing
   `connectedCallback` lifecycle

---

## 9. Declarative Shadow DOM -- The SSR Enabler for Web Components

### What It Is

Declarative Shadow DOM (DSD) allows Shadow DOM to be defined in HTML without
JavaScript. This is the critical missing piece that historically made Web
Components incompatible with SSR.

**Before DSD:** Shadow DOM required JavaScript to create:
```javascript
// This only works client-side
const shadow = this.attachShadow({ mode: 'open' });
shadow.innerHTML = '<p>Content</p>';
```

**With DSD:** Shadow DOM can be declared in HTML:
```html
<!-- This works server-side, no JavaScript needed -->
<ntt-item>
  <template shadowrootmode="open">
    <style>:host { display: block; }</style>
    <div class="card">
      <h3>Widget Pro</h3>
      <span class="price">$29.99</span>
    </div>
  </template>
</ntt-item>
```

The browser parses the `<template shadowrootmode="open">` and attaches a
shadow root **during HTML parsing**, before any JavaScript executes.

### Browser Support (as of February 2026)

| Browser | Version | Support |
|---|---|---|
| **Chrome** | 111+ (full), 90-110 (partial) | Full |
| **Edge** | 111+ (full) | Full |
| **Safari** | 16.4+ | Full |
| **Firefox** | 123+ | Full |
| **Global support** | **94.38%** | Baseline (Feb 2024) |

([CanIUse, "Declarative Shadow DOM"](https://caniuse.com/declarative-shadow-dom))

At 94.38% global coverage, DSD is viable for production use. The remaining
~6% can be handled with a lightweight polyfill or by falling back to
client-side rendering for unsupported browsers.

### Implications for PyBend

DSD means PyBend can server-render `<ntt-item>` components as complete HTML
with Shadow DOM attached -- no JavaScript needed for initial paint. The
server would:

1. Fetch entity data from the database
2. Run the equivalent of `ntt-item.render()` server-side (likely via a
   Node.js rendering service or Python template)
3. Emit `<template shadowrootmode="open">` with the rendered HTML
4. Include entity data as a serialized JSON block for client hydration

```html
<!-- Server-rendered ntt-item with Declarative Shadow DOM -->
<ntt-item data-schema="Product" data-id="42">
  <template shadowrootmode="open">
    <link rel="stylesheet" href="/static/components/ntt-item.css">
    <div class="card" data-display="md">
      <h3 data-value="name">Widget Pro</h3>
      <span data-value="price">$29.99</span>
      <p data-value="description">A professional-grade widget.</p>
      <div class="methods">
        <ntt-method data-method="like">Like</ntt-method>
        <ntt-method data-method="favorite">Favorite</ntt-method>
      </div>
    </div>
  </template>
  <script type="application/json">
    {"name":"Widget Pro","price":29.99,"description":"A professional-grade widget.",
     "$schema":"http://localhost:5000/Product","$id":"http://localhost:5000/products/42"}
  </script>
</ntt-item>
```

([web.dev, "Declarative Shadow DOM"](https://web.dev/articles/declarative-shadow-dom);
[Smashing Magazine, "Web Components: Working With Shadow DOM"](https://www.smashingmagazine.com/2025/07/web-components-working-with-shadow-dom/))

---

## 10. How Existing Libraries Handle Web Component Hydration

### Lit SSR

Lit provides an official SSR package (`@lit-labs/ssr`) that renders Lit
components to HTML strings on the server using a lightweight environment
that does not fully emulate the DOM.

**Hydration approach:**
- Server renders component to static HTML with Declarative Shadow DOM
- Client loads `@lit-labs/ssr-client` which provides a `hydrate()` function
- `hydrate()` walks the existing DOM, re-associates Lit template expressions
  with their corresponding DOM nodes, and attaches event listeners
- Lit explicitly avoids re-rendering: the existing DOM is preserved, only
  bindings are reconnected

**Key constraint:** Lit SSR requires components to be written with Lit's
template system (`html` tagged template literals). Vanilla Web Components
without Lit templates cannot use this directly.

([Lit Documentation, "SSR Client Usage"](https://lit.dev/docs/ssr/client-usage/))

### Stencil Hydrate

Stencil takes a compiler-driven approach:

- A `hydrate` output target generates a Node.js module (`hydrate/index.mjs`)
- This module uses `MockDoc` -- a lightweight virtual DOM environment --
  to run components on the server
- The server-rendered HTML includes annotations (class names, data attributes)
  that the client-side Stencil runtime uses to reconnect
- Stencil 4.x+ supports Declarative Shadow DOM output
- For frameworks like Next.js or Nuxt, Stencil operates as a Vite plugin
  that intercepts custom element tags during build

([Stencil Documentation, "Hydrate App"](https://stenciljs.com/docs/hydrate-app);
[Ionic Blog, "The Quest for SSR with Web Components"](https://ionic.io/blog/the-quest-for-ssr-with-web-components-a-stencil-developers-journey))

### Enhance SSR

Enhance takes the simplest approach: **pure server-side expansion, zero
client hydration by default.**

- Components are defined as pure functions of state that return HTML strings
- The server "expands" custom element tags by calling their render function
  and inserting the output
- No Shadow DOM is used by default (components use light DOM)
- Interactive behavior is added progressively via standard `<script>` tags
- The expansion algorithm is under 500 lines of code with minimal dependencies

**Philosophy:** Start with 0 KB of JavaScript. Add interactivity only where
explicitly needed.

([Enhance, "Portable Server Rendered Web Components"](https://enhance.dev/blog/posts/2024-05-03-portable-ssr-components);
[The Spicy Web, "Enhance vs. Lit vs. WebC"](https://www.spicyweb.dev/web-components-ssr-node/))

### Comparison for PyBend

| Library | Shadow DOM SSR | Hydration Strategy | Compiler Required | Vanilla WC Compatible |
|---|---|---|---|---|
| **Lit SSR** | DSD | Template-aware reconnection | No (runtime) | Lit templates only |
| **Stencil** | DSD or scoped | Annotation-based reconnection | Yes (Stencil compiler) | Stencil components only |
| **Enhance** | Light DOM | No hydration (expansion only) | No | Yes (pure functions) |

**For PyBend:** None of these are directly usable because PyBend's components
are vanilla Custom Elements (not Lit, not Stencil). However, PyBend can adopt
concepts from each:

- **From Lit:** The pattern of walking existing DOM to reconnect bindings
  rather than re-rendering
- **From Stencil:** Using annotations in server HTML to guide client reconnection
- **From Enhance:** The "expand on server, enhance on client" philosophy

---

## 11. Hydrating an Actor-Based System (Matrix Message Bus)

### The Unique Challenge

PyBend's frontend is not just a component tree -- it is an **actor system**.
Every entity instance is an `Actor` with an address. Components communicate
via the `Matrix` message bus using `TX` (transaction) messages. Hydration must
restore not just DOM bindings but the entire messaging infrastructure.

```
  ACTOR SYSTEM STATE THAT MUST BE RESTORED:
  ==========================================

  Matrix (root actor)
    |
    +-- NetworkAdapter (remote message routing)
    |
    +-- NTT (type registry)
    |     +-- Product (DynamicClass)
    |     |     +-- Product/42 (instance actor)
    |     |     +-- Product/43 (instance actor)
    |     +-- Comment (DynamicClass)
    |           +-- Comment/101 (instance actor)
    |           +-- Comment/102 (instance actor)
    |
    +-- Router (navigation state)
    |
    +-- Component registry
          +-- ntt-list/products (list component actor)
          +-- ntt-item/product-42 (item component actor)
          +-- ntt-item/product-43 (item component actor)
```

### Hydration Steps for the Actor System

Traditional hydration for PyBend's actor system would require:

1. **Matrix initialization** -- Create the root `Matrix` actor, register it
   via `Actor.registerRoot(this)`, initialize `NetworkAdapter`
2. **Schema fetching** -- `NTT.SCHEMA()` must fetch schemas from backend to
   create DynamicClasses via `prototype()`
3. **Type registration** -- Each DynamicClass registers in `NTT.#prototypes`
4. **Instance creation** -- Entity instances are created as Actors with
   addresses in the `children` map
5. **Component binding** -- Each Web Component (e.g., `ntt-item`) connects to
   its corresponding entity Actor via `watch()` / `ATTACH()`
6. **Watcher reconnection** -- The `#watchers` Set on each `TT` instance must
   be rebuilt so that data updates propagate to the correct components

### Optimized Approach: Deferred Actor Initialization

Instead of fully reconstructing the actor system during hydration, PyBend
could adopt a **lazy actor initialization** pattern:

```
Phase 1: Immediate (0ms)
  - Create Matrix root actor (singleton, minimal cost)
  - Create NetworkAdapter (for future remote calls)
  - Register component custom elements (already done via module imports)

Phase 2: On Schema Cache Hit (50-100ms)
  - If schemas are cached (Service Worker or localStorage), create
    DynamicClasses without network round-trip
  - Register types in NTT registry

Phase 3: On Component Interaction (lazy, per-component)
  - When user interacts with an <ntt-item>, create the Actor instance
  - Deserialize entity data from embedded JSON
  - Establish watcher connections only for the active component
  - Send initial ATTACH message to connect component to entity

Phase 4: Background (idle time)
  - Hydrate remaining components during requestIdleCallback
  - Pre-populate the #watchers graph for anticipated interactions
```

This approach means the Matrix message bus is functional within ~100ms, but
most entity Actors are not instantiated until needed. Since the server-rendered
HTML already shows the correct data, no messages need to flow until the user
interacts.

---

## 12. Event Replay vs Event Delegation During Hydration

### The Problem

During the gap between FCP and full hydration, users may click buttons, type
in inputs, or trigger other events. These events fire against server-rendered
HTML that has no event listeners attached. Without mitigation, these
interactions are silently lost.

### Event Replay

Event replay captures events during the pre-hydration window and replays them
after hydration completes.

**How it works (as implemented in Angular):**

1. A tiny global event dispatcher script (~2KB) is inlined in the HTML `<head>`
2. This script listens for DOM events (clicks, keypresses, focusin) at the
   document root using event delegation
3. Events are buffered in memory with their targets and event objects
4. Once hydration completes for a component, its buffered events are replayed
   through the newly-attached listeners

([Angular Documentation, "Hydration"](https://angular.dev/guide/hydration))

**Trade-offs:**

| Pro | Con |
|---|---|
| User actions are never lost | Replayed events may be stale (e.g., double-click) |
| Seamless perceived experience | Complex to implement correctly |
| Works with any hydration timing | Event order must be preserved |
| | Replayed events may trigger state changes that conflict with server state |

### Event Delegation

Event delegation attaches a single listener at the document or component root
that routes events to the appropriate handler based on the event target. This
naturally works during hydration because:

- Only one listener needs to be attached (at the root)
- That listener can be attached immediately as part of Phase 1 hydration
- Individual component handlers are resolved lazily on event dispatch

**For PyBend:** The Matrix message bus *already functions as an event delegation
system*. The Matrix's `inbox()` method receives all messages and routes them
to the appropriate Actor. A hydration-aware Matrix could:

1. Attach a single DOM event listener at the document root immediately
2. Map DOM events to `TX` messages based on `data-*` attributes on elements
3. If the target Actor is not yet hydrated, either:
   - Buffer the TX and replay after hydration (event replay)
   - Trigger immediate hydration of that Actor, then dispatch (selective)

---

## 13. Measuring Hydration Cost

### Key Metrics

| Metric | What It Measures | Target |
|---|---|---|
| **FCP** (First Contentful Paint) | When user first sees content | < 1.8s |
| **TTI** (Time to Interactive) | When page responds to input reliably | < 3.8s |
| **TBT** (Total Blocking Time) | Sum of long task time between FCP and TTI | < 200ms |
| **FCP-to-TTI gap** | The "uncanny valley" duration | < 500ms |
| **Hydration time** | JS execution time for hydration specifically | < 200ms |
| **INP** (Interaction to Next Paint) | Responsiveness after hydration | < 200ms |

### How to Measure

```javascript
// Mark hydration start/end with Performance API
performance.mark('hydration-start');

// ... hydration code ...

performance.mark('hydration-end');
performance.measure('hydration', 'hydration-start', 'hydration-end');

// Per-component hydration timing
performance.mark(`hydrate-${componentName}-start`);
// ... component hydration ...
performance.mark(`hydrate-${componentName}-end`);
performance.measure(
  `hydrate-${componentName}`,
  `hydrate-${componentName}-start`,
  `hydrate-${componentName}-end`
);
```

### Hydration Cost by Strategy (Industry Benchmarks)

These numbers represent typical measurements from industry reports on
medium-complexity applications (20-50 components, mobile 4G):

| Strategy | FCP | TTI | FCP-TTI Gap | JS at Load | Source |
|---|---|---|---|---|---|
| **CSR (no SSR)** | ~2.5s | ~2.5s | 0ms | 100% | Baseline |
| **SSR + Full Hydration** | ~0.8s | ~2.8s | ~2000ms | 100% | web.dev |
| **SSR + Progressive** | ~0.8s | ~1.5s | ~700ms | ~40% initial | The New Stack |
| **SSR + Partial** | ~0.8s | ~1.2s | ~400ms | ~20-40% | Gatsby |
| **SSR + Islands** | ~0.6s | ~1.0s | ~400ms | ~15-30% | Astro benchmarks |
| **Resumability (Qwik)** | ~0.5s | ~0.5s | ~0ms | ~1KB | Builder.io |

Note: These are representative ranges from various published benchmarks, not
controlled comparisons. Actual numbers depend heavily on application complexity,
device capability, and network conditions.

### Tools for Measurement

- **Lighthouse** -- Lab-based metrics (FCP, TTI, TBT, CLS)
- **Chrome DevTools Performance tab** -- Flame charts showing hydration tasks
- **Web Vitals library** -- Field metrics from real users
- **Custom Performance API marks** -- Framework-specific hydration timing
- **WebPageTest** -- Filmstrip view showing visual vs interactive states

([web.dev, "Rendering on the Web"](https://web.dev/articles/rendering-on-the-web))

---

## 14. The Uncanny Valley Problem

### What It Is

The uncanny valley in web performance is the period between when a page
*looks* ready and when it *is* ready. The user sees a fully-rendered page --
product images, prices, buttons, forms -- and naturally tries to interact.
Nothing happens. Clicks are lost. Scroll handlers do not fire. Form
submissions silently fail.

```
  USER EXPERIENCE TIMELINE:
  ==========================

  0.0s  [blank screen]         User: "Loading..."
  0.4s  [FCP - content paint]  User: "Oh, it's loaded!"
  0.5s  [user clicks button]   User: "..." (nothing happens)
  0.8s  [user clicks again]    User: "Is this broken?"
  1.2s  [user scrolls away]    User: "Let me try something else"
  1.5s  [hydration completes]  App: "Ready!" (user has moved on)
        ▲                      ▲
        |                      |
        UNCANNY VALLEY         TOO LATE
```

This problem is **worse** than a blank loading screen because:

1. A loading screen sets expectations ("wait, it's loading")
2. The uncanny valley *violates* expectations ("it looks ready but ignores me")
3. Users blame themselves or the content, not the loading process
4. Rage clicks generate duplicate events that replay badly after hydration

### Impact Data

Research from the e-commerce sector shows:

- **53% of mobile users** abandon sites that take more than 3 seconds to
  become interactive ([Google, Web Vitals](https://web.dev/articles/rendering-on-the-web))
- **A 500-800ms TTI improvement** from progressive hydration correlated with
  **5.2% higher conversion rates** in tested e-commerce applications
  ([Markaicode](https://markaicode.com/nextjs-17-hydration-performance-ecommerce/))

### Mitigation Strategies

| Strategy | How It Helps | Complexity |
|---|---|---|
| **Loading indicators on interactive elements** | Sets expectations ("this button is loading") | Low |
| **Event replay** | Captures clicks during valley, replays after hydration | Medium |
| **Selective hydration** | Hydrates what user touches first | Medium-High |
| **Resumability** | Eliminates the valley entirely | High |
| **CSS-only interactions** | Hover states, focus rings work without JS | Low |
| **Progressive enhancement** | Basic forms work via HTML `action`; JS enhances | Medium |

### PyBend-Specific Uncanny Valley

PyBend's uncanny valley is particularly noticeable on entity pages because:

- `ntt-method` buttons (Like, Favorite) look clickable but do nothing until
  the Actor is registered and the Matrix can route the TX message
- `ntt-item` edit buttons toggle mode but require the full Formidable form
  generator to be loaded
- `ntt-list` pagination ("Load More") requires the NetworkAdapter to be
  initialized for API calls

**Recommended mitigation:** Add `disabled` attributes and subtle loading
indicators to interactive elements during SSR rendering. Remove them as each
component completes hydration. This is honest UI -- it tells the user "this
will be ready in a moment" rather than lying by omission.

---

## 15. Hydration Errors and Mismatches

### What They Are

A hydration mismatch occurs when the HTML the client expects to produce
differs from the HTML the server actually sent. The framework detects the
discrepancy and either throws an error, silently re-renders (destroying
the server HTML), or produces corrupted output.

### Common Causes

| Cause | Example | Why It Happens |
|---|---|---|
| **Browser API usage during SSR** | `window.innerWidth`, `document.cookie` | These APIs do not exist on the server |
| **Date/time rendering** | `new Date().toLocaleString()` | Server and client may be in different timezones; time passes between render and hydrate |
| **Random values** | `Math.random()` for keys/IDs | Different values on server vs client |
| **Conditional rendering** | `if (isLoggedIn)` where auth state differs | Server may not have the same auth context |
| **Browser extensions** | Ad blockers modify DOM | Extensions inject/remove elements between server render and hydration |
| **Third-party scripts** | Analytics, chat widgets | Modify DOM before hydration runs |
| **CSS-in-JS class names** | Styled-components generates different hashes | Server and client may use different hash seeds |
| **HTML normalization** | Browser auto-corrects invalid HTML | `<p><div>` becomes `<p></p><div>` in browser |

([Next.js Documentation, "Hydration Error"](https://nextjs.org/docs/messages/react-hydration-error);
[LogRocket, "Resolving hydration mismatch errors in Next.js"](https://blog.logrocket.com/resolving-hydration-mismatch-errors-next-js/);
[PropelAuth, "Understanding Hydration Errors"](https://www.propelauth.com/post/understanding-hydration-errors))

### PyBend-Specific Mismatch Risks

| Risk Area | Why It Matters |
|---|---|
| **Schema-derived rendering** | If the server renders with a cached schema and the backend schema has changed, field order or available fields may differ |
| **DynamicClass properties** | DynamicClasses add getters/setters at runtime; server-rendered HTML may not reflect the same property set |
| **Permission-dependent UI** | `permissions.canAction()` checks may evaluate differently on server vs client if auth tokens differ |
| **Entity $id and $schema URLs** | These contain the server hostname; if the client accesses via a different hostname (CDN, proxy), URLs mismatch |
| **Skeleton placeholders** | `ntt-item.connectedCallback()` renders a skeleton if no schema exists; if DSD provides content, the skeleton would conflict |

### Debugging Strategies

1. **Enable development mode warnings** -- React, Vue, and Angular all
   produce detailed mismatch warnings in development builds
2. **Diff server and client HTML** -- Capture the server-rendered HTML before
   hydration (`document.documentElement.innerHTML`) and compare with the
   hydrated output
3. **Use `suppressHydrationWarning`** (React-specific) -- For intentional
   differences (timestamps, random IDs), suppress per-element
4. **Render timestamps as relative** -- Use "2 hours ago" instead of
   "14:32:05" to reduce time-based mismatches
5. **Deterministic IDs** -- Use content-based hashes instead of `Math.random()`
6. **Two-pass rendering** -- First pass matches server exactly; second pass
   (after hydration) adds client-specific content

### Prevention Pattern for PyBend

```
  SERVER RENDER                          CLIENT HYDRATE
  =============                          ===============

  1. Render with schema v42              1. Check embedded schema version
  2. Render with entity data             2. Compare with live entity data
  3. Render with access rules            3. Compare with client auth context
  4. Embed version hash in               4. If hash matches: reconnect
     data-render-hash="abc123"              (no re-render needed)
                                         5. If hash differs: re-render
                                            (accept mismatch, update)
```

The version-hash approach lets PyBend detect mismatches early and choose
between preserving server HTML (when safe) or triggering a clean client
re-render (when necessary) instead of silently producing corrupted output.

---

## 16. PyBend's DynamicClass System and Hydration

### The Core Challenge

PyBend creates entity classes at runtime from JSON Schema:

```javascript
// NTT.js -- prototype() factory
// This creates a DynamicClass with typed properties, methods, and a value
// getter that injects $schema and $id.
//
// The class DOES NOT EXIST until the schema is fetched from the backend.
```

In a traditional SSR hydration flow, the client needs to know the class
definition *before* it can hydrate instances of that class. But in PyBend,
the class definition comes FROM the server, at runtime, after a network
request. This creates a circular dependency:

```
  CIRCULAR DEPENDENCY:
  ====================

  To hydrate <ntt-item> for Product #42:
    -> Need DynamicClass "Product"
      -> Need JSON Schema for Product
        -> Need network request to GET /Product
          -> Need NetworkAdapter initialized
            -> Need Matrix actor system running
              -> Need hydration to be complete
                -> Need DynamicClass "Product" (!!!)
```

### Breaking the Cycle

The solution is to **embed the schema in the server-rendered HTML** so that
DynamicClass creation does not require a network round-trip:

```html
<!-- Server embeds schema inline during SSR -->
<script type="application/schema+json" data-model="Product">
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Product",
  "__name__": "Product",
  "__tablename__": "products",
  "properties": {
    "name": {"type": "string", "minLength": 1},
    "price": {"type": "number", "exclusiveMinimum": 0},
    "description": {"type": "string"}
  },
  "methods": {
    "like": {"route": "/like", "methods": ["POST"]},
    "favorite": {"route": "/favorite", "methods": ["POST"]}
  },
  "access": {
    "read": {"rule": "anyone"},
    "update": {"op": "or", "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin"]}]}
  }
}
</script>
```

### Hydration-Aware DynamicClass Lifecycle

```
  PROPOSED HYDRATION FLOW:
  ========================

  Phase 0: Server Render (Python/FastAPI)
    - Render page HTML with DSD for each <ntt-item>
    - Embed JSON Schemas as <script type="application/schema+json">
    - Embed entity data as <script type="application/json"> per component
    - No JavaScript executes

  Phase 1: Critical Path (< 50ms of JS)
    - Load tiny bootstrap script (< 3KB)
    - Parse embedded schemas, create DynamicClasses via prototype()
    - Register classes in NTT.#prototypes
    - Initialize Matrix root actor + NetworkAdapter
    - Attach root event delegation listener

  Phase 2: Component Reconnection (progressive, per-component)
    - For each <ntt-item> with DSD content:
      a. Read entity data from embedded JSON
      b. Create entity Actor with correct address
      c. Reconnect Shadow DOM event listeners (not re-render)
      d. Mark component as "hydrated"
    - Priority: above-fold first, below-fold on visibility

  Phase 3: Background Enhancement (idle time)
    - Verify entity data freshness (optional background fetch)
    - Pre-load method handlers for visible <ntt-method> buttons
    - Establish WebSocket or long-poll for real-time updates
```

### State Serialization Strategy

Each `ntt-item` in PyBend currently maintains state through its `value`
property (set via `DESCRIBE` messages from the Actor system). For SSR
hydration, this state must be serialized and restored:

```
  SERIALIZATION MAP:
  ==================

  NTTItem component state:
    .value      -> <script type="application/json"> inside the element
    .schema     -> reference to DynamicClass (from embedded schema)
    .mode       -> data-mode="display" attribute on host element
    .displayMode-> data-display="md" attribute on card div
    .ref        -> data-ref="http://..." attribute on host element

  TT (Transfer Type) actor state:
    #href       -> data-href attribute on host element
    #watchers   -> rebuilt during Phase 2 when components connect

  NTT type registry:
    #prototypes -> rebuilt in Phase 1 from embedded schemas
    .children   -> rebuilt as entity Actors are created in Phase 2
```

---

## 17. Recommendation for PyBend

### Recommended Strategy: Progressive Islands with Embedded Schema

Based on this analysis, the optimal hydration strategy for PyBend combines:

1. **Islands architecture** (leveraging Web Components' natural encapsulation)
2. **Progressive hydration** (prioritized by viewport position and user intent)
3. **Embedded schema** (breaking the DynamicClass circular dependency)
4. **Deferred actor initialization** (Matrix boots fast, Actors load lazily)

### Implementation Phases

```
  PHASE 1: Foundation (DSD + Embedded Data)
  ─────────────────────────────────────────
  - Add DSD rendering capability to the Python backend
  - Server-render ntt-item/ntt-list components as DSD HTML
  - Embed schemas and entity data inline
  - Result: instant FCP with full content, 0 JS on initial paint

  PHASE 2: Smart Hydration (Progressive + Priority)
  ──────────────────────────────────────────────────
  - Tiny bootstrap script (< 3KB) initializes Matrix + parses schemas
  - Above-fold components hydrate immediately
  - Below-fold components hydrate on intersection (IntersectionObserver)
  - Method buttons (like, favorite) hydrate on hover/focus
  - Result: TTI for visible content < 500ms

  PHASE 3: Interaction-Driven Loading (Selective)
  ────────────────────────────────────────────────
  - Root event delegation captures all DOM events
  - Un-hydrated component interactions trigger immediate hydration
  - Event is replayed after hydration completes
  - Result: no lost interactions during uncanny valley

  PHASE 4: Optimization (Partial + Cache)
  ────────────────────────────────────────
  - Service Worker caches schemas for instant Phase 1 on repeat visits
  - Static components (descriptions, metadata) skip hydration entirely
  - Bundle splitting: each component type is a separate chunk
  - Result: near-zero JS for return visitors viewing cached content
```

### Decision Matrix

| Strategy | PyBend Fit | Effort | TTI Impact | Risk |
|---|---|---|---|---|
| **Full hydration** | Poor | Low | None | Low |
| **Progressive hydration** | Excellent | Medium | -40-60% | Low |
| **Selective hydration** | Good | Medium-High | -30-50% | Medium |
| **Partial hydration** | Medium | Medium | -20-40% | Low |
| **Islands (DSD)** | Excellent | Medium | -50-70% | Medium |
| **Resumability** | Low (requires compiler) | Very High | -90%+ | High |
| **Progressive Islands (recommended)** | Excellent | Medium-High | -60-80% | Medium |

### Key Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| DSD browser support gaps (~6%) | Some users get no SSR benefit | Polyfill + CSR fallback for unsupported browsers |
| Schema version mismatch | Hydration errors, stale UI | Version hash in embedded schema; force re-render on mismatch |
| Actor system initialization delay | Brief window of non-functional buttons | Event buffering in root delegation listener; loading indicators |
| DynamicClass property mismatch | JS errors during hydration | Schema validation before DynamicClass creation; error boundary |
| Dual rendering logic maintenance | Server and client renderers diverge | Single template system (tagged template literals) used by both |

---

## 18. Sources

1. [web.dev -- "Rendering on the Web" (Performance strategies overview)](https://web.dev/articles/rendering-on-the-web)
2. [web.dev -- "Declarative Shadow DOM" (DSD specification and usage)](https://web.dev/articles/declarative-shadow-dom)
3. [CanIUse -- "Declarative Shadow DOM" (Browser support data: 94.38% global)](https://caniuse.com/declarative-shadow-dom)
4. [Builder.io -- "Resumability vs Hydration" (Qwik architecture deep dive)](https://www.builder.io/blog/resumability-vs-hydration)
5. [Qwik Documentation -- "Resumable" (Serialization and state restoration)](https://qwik.dev/docs/concepts/resumable/)
6. [React 18 Working Group -- "New in 18: Selective Hydration" (Priority-based hydration)](https://github.com/reactwg/react-18/discussions/130)
7. [patterns.dev -- "Islands Architecture" (Pattern definition and benefits)](https://www.patterns.dev/vanilla/islands-architecture/)
8. [Enhance -- "Island Architecture with Web Components" (WC as natural islands)](https://enhance.dev/blog/posts/2024-07-09-island-architecture-with-web-components)
9. [Lit Documentation -- "SSR Client Usage" (Lit hydration mechanism)](https://lit.dev/docs/ssr/client-usage/)
10. [Stencil Documentation -- "Hydrate App" (Compiler-driven WC SSR)](https://stenciljs.com/docs/hydrate-app)
11. [Ionic Blog -- "The Quest for SSR with Web Components" (Stencil SSR journey)](https://ionic.io/blog/the-quest-for-ssr-with-web-components-a-stencil-developers-journey)
12. [Angular Documentation -- "Hydration" (Event replay implementation)](https://angular.dev/guide/hydration)
13. [The New Stack -- "Mastering Progressive Hydration" (Performance strategies)](https://thenewstack.io/mastering-progressive-hydration-for-enhanced-web-performance/)
14. [Markaicode -- "Next.js 17 Hydration Overhaul" (50% TTI reduction data)](https://markaicode.com/nextjs-17-hydration-performance-ecommerce/)
15. [DEV Community -- "Progressive vs Partial Hydration" (Strategy taxonomy)](https://dev.to/theiaz/-the-difference-between-progressive-and-partial-hydration-18dd)
16. [Gatsby -- "Partial Hydration" (83% JS reduction data)](https://www.gatsbyjs.com/docs/conceptual/partial-hydration/)
17. [Smashing Magazine -- "Web Components: Working With Shadow DOM" (DSD usage)](https://www.smashingmagazine.com/2025/07/web-components-working-with-shadow-dom/)
18. [Next.js Documentation -- "Hydration Error" (Mismatch debugging)](https://nextjs.org/docs/messages/react-hydration-error)
19. [LogRocket -- "Resolving hydration mismatch errors in Next.js" (Prevention patterns)](https://blog.logrocket.com/resolving-hydration-mismatch-errors-next-js/)
20. [The Spicy Web -- "Enhance vs. Lit vs. WebC" (SSR library comparison)](https://www.spicyweb.dev/web-components-ssr-node/)
21. [DEV Community -- "Why Efficient Hydration Is So Challenging" (Technical analysis)](https://dev.to/this-is-learning/why-efficient-hydration-in-javascript-frameworks-is-so-challenging-1ca3)
22. [Syncfusion -- "Incremental Hydration in Angular" (Event replay details)](https://www.syncfusion.com/blogs/post/incremental-hydration-in-angular-apps)
23. [Enhance -- "Portable Server Rendered Web Components" (0KB JS philosophy)](https://enhance.dev/blog/posts/2024-05-03-portable-ssr-components)
24. [Madrigan Blog -- "Advanced SSR 2025: Selective Hydration, RSCs, and Edge Rendering"](https://blog.madrigan.com/en/blog/202601070853/)
25. [arxiv.org -- "Improving Front-end Performance through MRAH in React Applications" (Academic research)](https://arxiv.org/html/2504.03884v1)

---

*Document generated 2026-02-25. Research conducted across 12+ searches spanning
hydration strategies, Web Component SSR, Declarative Shadow DOM, actor model
patterns, and performance benchmarking data.*
