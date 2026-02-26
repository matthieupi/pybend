# Web Components as a Micro-Frontend Strategy: Actor-Model Communication and Schema-Driven Architectures

**Research Date:** February 2026
**Context:** PyBend framework -- vanilla JS Web Components, actor-based message bus (Matrix/Actor/TX), schema-driven DynamicClass creation from backend JSON Schema, no build step (raw ES modules).

---

## Table of Contents

1. [Web Components State of the Art (2025-2026)](#1-web-components-state-of-the-art-2025-2026)
2. [Actor Model in Frontend Architecture](#2-actor-model-in-frontend-architecture)
3. [Schema-Driven UI Architecture](#3-schema-driven-ui-architecture)
4. [The Buildless / No-Bundler Approach](#4-the-buildless--no-bundler-approach)
5. [Native Federation (ES Modules + Import Maps as MFE Infrastructure)](#5-native-federation-es-modules--import-maps-as-mfe-infrastructure)
6. [Performance Optimization for Buildless MFE](#6-performance-optimization-for-buildless-mfe)
7. [Relevance to PyBend](#7-relevance-to-pybend)

---

## 1. Web Components State of the Art (2025-2026)

### 1.1 Browser Support Status

Web Components have moved from experimental to mainstream. As of early 2026, browser support stands at approximately **98% global coverage** across the core specifications:

| Specification | Chrome | Firefox | Safari | Edge |
|---|---|---|---|---|
| Custom Elements v1 | 67+ | 63+ | 10.1+ | 79+ |
| Shadow DOM v1 | 53+ | 63+ | 10+ | 79+ |
| HTML Templates | 26+ | 22+ | 8+ | 13+ |
| ES Modules | 61+ | 60+ | 10.1+ | 79+ |
| Constructable Stylesheets | 73+ | 101+ | 16.4+ | 79+ |
| Declarative Shadow DOM | 90+ | 128+ | 16.4+ | 90+ |

No polyfills are required for any modern browser. Enterprise adoption increased 156% from 2023 to 2025, with 73% of Fortune 500 companies implementing Web Components in their design systems.

**Sources:**
- [Web Components 2025: Shadow DOM, Lit 4.0, and Browser Compatibility](https://markaicode.com/web-components-2025-shadow-dom-lit-browser-compatibility/)
- [Web Components in 2026: Why Native UI Is Back in Demand](https://talent500.com/blog/web-components-comeback-modern-frontend/)
- [A Complete Introduction to Web Components in 2026](https://kinsta.com/blog/web-components/)

### 1.2 Shadow DOM: Benefits, Pitfalls, and the "Styling Problem"

Shadow DOM provides true CSS encapsulation -- styles inside a shadow root do not leak out, and external styles do not bleed in. This is the single most important property for micro-frontend composition, because it eliminates the CSS collision problem that plagues iframe-less MFE approaches.

**Benefits:**
- CSS selectors stay simple; no BEM, no CSS modules, no naming conventions needed for collision avoidance.
- DOM encapsulation prevents scripts from accidentally (or maliciously) reaching into component internals.
- Event retargeting provides clean event boundaries between micro-frontends.

**Pitfalls (the "styling problem"):**
- **Global styles do not penetrate.** A `<link rel="stylesheet" href="bootstrap.css">` in the document has zero effect inside a shadow root. Design systems that rely on global class-based styling (Bootstrap, Tailwind) require explicit adoption inside each shadow root.
- **The deprecated `::shadow` and `/deep/` selectors are gone.** There is no CSS-only way to force styles into a shadow root from the outside.
- **Theming requires intent.** The component author must deliberately expose styling hooks (CSS custom properties, `::part()`, or `adoptedStyleSheets`). If they do not, consumers cannot theme the component.
- **Slots lose style context.** Slotted content is styled by the outer document, not the shadow root. This causes surprising visual inconsistencies when mixing shadow-internal and slotted elements.

**The current consensus (2026):** Shadow DOM is worth the tradeoff for component libraries and micro-frontends where isolation is essential. For application-internal components where a single team controls all styles, `mode: "open"` with Constructable Stylesheets provides the best balance. Some teams skip Shadow DOM entirely for leaf-node components and only apply it at the MFE boundary.

**Sources:**
- [Web Components: Working With Shadow DOM -- Smashing Magazine](https://www.smashingmagazine.com/2025/07/web-components-working-with-shadow-dom/)
- [8 Ways to Style the Shadow DOM](https://jordanbrennan.hashnode.dev/8-ways-to-style-the-shadow-dom)
- [Shadow DOM: Building Perfectly Encapsulated Web Components](https://dev.to/mukhilpadmanabhan/shadow-dom-building-perfectly-encapsulated-web-components-441f)

### 1.3 Constructable Stylesheets and adoptedStyleSheets

Constructable Stylesheets solve the Shadow DOM styling problem efficiently. Instead of creating `<style>` elements inside every shadow root (duplicating the CSS text in memory), you construct a `CSSStyleSheet` once and share it across many shadow roots:

```javascript
const sheet = new CSSStyleSheet();
sheet.replaceSync(`
  :host { display: block; }
  .container { padding: var(--spacing-md, 1rem); }
`);

class MyElement extends HTMLElement {
  constructor() {
    super();
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.adoptedStyleSheets = [sheet];
  }
}
```

**Key properties:**
- **Shared across shadow roots.** A single `CSSStyleSheet` object can be adopted by hundreds of shadow roots simultaneously, with zero memory duplication of the CSS text.
- **Dynamically mutable.** Call `sheet.replaceSync(newCSS)` or `sheet.insertRule()` and every adopting shadow root reflects the change instantly. This enables runtime theme switching.
- **Composable.** `adoptedStyleSheets` is an array. A component can adopt a base design-token sheet, a component-specific sheet, and an optional consumer-provided override sheet: `shadow.adoptedStyleSheets = [tokens, componentStyles, overrides]`.
- **Browser support:** Chrome 73+, Firefox 101+, Safari 16.4+, Edge 79+. The `construct-style-sheets` polyfill covers older browsers.

This is the foundation for a scalable design system in a Web Components architecture. Define your tokens once in a shared `CSSStyleSheet`, adopt it in every component, and theme changes propagate automatically.

**Sources:**
- [Constructable Stylesheets | web.dev](https://web.dev/articles/constructable-stylesheets)
- [Document: adoptedStyleSheets property | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Document/adoptedStyleSheets)
- [Composable Adopted Stylesheets -- David Bushell](https://dbushell.com/2025/08/02/composable-adopted-stylesheets/)

### 1.4 CSS Custom Properties as the Shadow DOM Bridge

CSS custom properties (CSS variables) are the **only** CSS values that pierce the Shadow DOM boundary by inheritance. This makes them the canonical mechanism for design tokens in Web Component architectures:

```css
/* Document-level (or :root) */
:root {
  --brand-primary: #2563eb;
  --spacing-md: 1rem;
  --font-body: 'Inter', sans-serif;
}

/* Inside shadow root -- these inherit automatically */
:host {
  color: var(--text-color, #333);
  font-family: var(--font-body, sans-serif);
}
.button {
  background: var(--brand-primary, blue);
  padding: var(--spacing-md, 1rem);
}
```

**Rules for component authors (per Nordhealth's production Web Component design system):**
1. **USE, do not DEFINE** token values inside shadow DOM. Let globally-defined tokens inherit.
2. **Set defaults only in `:host`** so consumers can override from outside by setting the property on the host element or any ancestor.
3. **Expose public custom properties** as a documented API surface. These are the component's "style API."
4. **Avoid setting custom properties deeper than `:host`** -- this can prevent outside overrides from taking effect due to CSS specificity.

The Nordhealth team reports that custom properties are the single most effective tool for maintaining a consistent design system across a large Web Component library, specifically because they cross shadow boundaries without any explicit opt-in from the component author.

**Sources:**
- [How Nordhealth uses Custom Properties in Web Components | web.dev](https://web.dev/articles/custom-properties-web-components)
- [Public CSS Custom Properties in the Shadow DOM](https://michaelwarren.dev/blog/css-variables-in-wc/)
- [Customizing -- Shoelace](https://shoelace.style/getting-started/customizing)

### 1.5 Declarative Shadow DOM (Server-Rendering)

Declarative Shadow DOM (DSD) closes the last major gap in Web Components: server-side rendering. Traditionally, a custom element's shadow DOM could only be created via JavaScript (`this.attachShadow()`), meaning the component content was invisible until JS loaded and executed. DSD allows shadow roots to be expressed in pure HTML:

```html
<my-component>
  <template shadowrootmode="open">
    <style>:host { display: block; }</style>
    <slot></slot>
  </template>
  <p>This content is visible immediately, before JS loads.</p>
</my-component>
```

The HTML parser converts the `<template shadowrootmode>` into a real shadow root during parsing -- no JavaScript required. The `shadowrootmode` attribute accepts `"open"` or `"closed"`, matching `attachShadow()` semantics.

**Browser support (early 2026):** Chrome 90+, Edge 90+, Firefox 128+, Safari 16.4+. The long Firefox holdout was resolved in mid-2024, making DSD a viable cross-browser production feature.

**Implications for MFE:**
- Web Component micro-frontends can be server-rendered by any backend (Python, Go, Rust, Node) that outputs HTML.
- First Contentful Paint (FCP) no longer depends on JavaScript download and execution for Web Component content.
- Streaming SSR (chunked transfer encoding) works naturally with DSD -- the browser renders shadow roots as the HTML stream arrives.

**Limitations:**
- React's reconciler does not yet fully support DSD during hydration (experimental support exists but causes hydration mismatches in some cases).
- Lit's SSR support is ahead of the ecosystem, providing `@lit-labs/ssr` for rendering Lit components on the server with DSD output.

**Sources:**
- [Declarative Shadow DOM | web.dev](https://web.dev/articles/declarative-shadow-dom)
- [Web Components & Declarative Shadow DOM: A New Era for Reusable UI](https://dev.to/martinrojas/web-components-declarative-shadow-dom-a-new-era-for-reusable-ui-28m6)
- [Declarative Shadow DOM | Can I use](https://caniuse.com/declarative-shadow-dom)
- [Declarative Shadow DOM and the future of Drupal Theming](https://john.albin.net/presentations/2025-11-18/declarative-shadow-dom-and-future-drupal-theming)

### 1.6 Custom Element Lifecycle as MFE Lifecycle

The Custom Elements API provides a lifecycle that maps directly to micro-frontend concerns:

| Lifecycle Callback | When It Fires | MFE Analog |
|---|---|---|
| `constructor()` | Element created (not yet in DOM) | MFE module loaded, class instantiated |
| `connectedCallback()` | Element added to DOM | MFE mounted, initialize, render, subscribe |
| `disconnectedCallback()` | Element removed from DOM | MFE unmounted, cleanup, unsubscribe |
| `attributeChangedCallback()` | Observed attribute changed | MFE receives new configuration/props |
| `adoptedCallback()` | Element moved to new document | MFE migrated between contexts (rare) |

**Best practices for MFE lifecycle:**
- **Defer work to `connectedCallback()`.** The constructor runs before the element is in the DOM and before attributes are set. Do initialization, rendering, event listener setup, and data fetching in `connectedCallback()`.
- **Clean up in `disconnectedCallback()`.** Remove event listeners, cancel pending fetches, disconnect observers. This prevents memory leaks when micro-frontends are dynamically swapped.
- **`connectedCallback()` can fire multiple times.** If an element is removed and re-inserted (e.g., during DOM reparenting), the callback fires again. Guard against double-initialization.
- **Use `isConnected` checks** for async operations that complete after the element may have been removed.

The callback-based lifecycle eliminates the need for a micro-frontend framework's mount/unmount hooks (e.g., single-spa's `bootstrap`, `mount`, `unmount`). The browser itself manages the lifecycle through standard DOM operations.

**Sources:**
- [Lifecycle Reference -- Web Components Guide](https://webcomponents.guide/learn/components/lifecycle-reference/)
- [Custom Elements Lifecycle: connectedCallback, disconnectedCallback Guide](https://web-components.tech/en/guide/custom-elements/lifecycle)
- [The life and times of a web component](https://plainvanillaweb.com/blog/articles/2024-09-16-life-and-times-of-a-custom-element/)

### 1.7 Ecosystem: Lit, FAST Element, Stencil

**Lit (currently at 3.x / 4.0 preview)**
Lit is the leading Web Components library, maintained by the Google Chrome team. It adds reactive properties, declarative templates (tagged template literals), and scoped styles on top of standard Custom Elements. Key characteristics:
- Tiny footprint (~5KB minified+gzipped).
- No virtual DOM; uses `lit-html` for efficient targeted DOM updates.
- Declarative Shadow DOM support via `@lit-labs/ssr`.
- Framework-agnostic: produces standard Custom Elements that work anywhere.
- Used in production by Google (YouTube, Google Workspace), Adobe, Salesforce.

**FAST Element (Microsoft)**
Microsoft's Web Components foundation, powering Fluent UI Web Components. FAST provides a base element class (`FASTElement`) with reactive attributes, a template system, and a design-token system. The project continues active maintenance (issues and releases through early 2025), but the community is smaller than Lit's. FAST is primarily positioned for Microsoft ecosystem integration (Teams, Office, Azure DevOps).

**Stencil (Ionic)**
Stencil is a Web Components compiler that takes TypeScript + JSX input and outputs optimized Custom Elements. Version 4.40.0 was released in December 2025 with CSS improvements and SSR support for React and Vue environments. Stencil's primary consumer is the Ionic Framework component library. It occupies a niche for teams that want JSX authoring with Web Component output.

**Where vanilla JS fits:** All three libraries produce standard Custom Elements. If you already have a working system of vanilla Custom Elements (as PyBend does), introducing a library adds dependency weight and API surface without necessarily adding capability. Libraries become valuable when you need their specific features: Lit's declarative templates, FAST's design token system, or Stencil's JSX compilation. If your components are primarily data-driven (rendered from schema), the template abstraction is less useful because the rendering logic is already dynamic.

**Sources:**
- [Lit](https://lit.dev/)
- [FAST](https://fast.design/)
- [Stencil](https://stenciljs.com/)
- [The Modern 2025 Web Components Tech Stack](https://dev.to/matsuuu/the-modern-2025-web-components-tech-stack-1l00)
- [Web Components 2025: Lit 3.0 vs Stencil 4.0](https://markaicode.com/web-components-2025-lit-stencil-enterprise/)
- [The future of FAST Components -- GitHub Issue #5849](https://github.com/microsoft/fast/issues/5849)

### 1.8 The "Going Buildless" Movement

Max Böck's 2024 article "Going Buildless" crystallized a sentiment that had been growing in the Web Components community: the files in your editor should be the same files delivered to the browser. No compilation, no node process, no build step.

The movement is enabled by three browser capabilities reaching maturity simultaneously:
1. **ES Modules** -- native `import`/`export` with `<script type="module">`.
2. **Import Maps** -- bare specifier resolution without a bundler.
3. **Constructable Stylesheets** -- CSS-in-JS without a build step for CSS.

Open Web Components (open-wc.org) published a comprehensive "Going Buildless" guide that has become the reference for this approach. Modern Web (modern-web.dev) provides tooling designed for buildless-first development with optional build for production.

The consensus (early 2026): buildless is production-viable for Web Component-based applications and component libraries. It is not viable for React/Vue/Angular applications that depend on JSX compilation, template compilation, or framework-specific optimizations. The buildless approach is therefore a natural fit for micro-frontend architectures where each MFE is a Custom Element.

**Sources:**
- [Going Buildless | Max Böck](https://mxb.dev/blog/buildless/)
- [Developing Without a Build: Introduction | open-wc](https://dev.to/open-wc/developing-without-a-build-1-introduction-26ao)
- [Going Buildless: Getting Started | Modern Web](https://modern-web.dev/guides/going-buildless/getting-started/)
- [A Real "Buildless" Modern Web Development Workflow | The Spicy Web](https://www.spicyweb.dev/buildless-modern-development-workflows-are-this-close-to-a-reality/)

---

## 2. Actor Model in Frontend Architecture

### 2.1 Origins: Erlang, Akka, and the Core Concepts

The Actor Model was formulated by Carl Hewitt, Peter Bishop, and Richard Steiger in 1973 as a mathematical model of concurrent computation. Its core principle: **everything is an actor**. An actor is an entity that:

1. **Receives messages** via a mailbox (inbox).
2. **Processes messages sequentially** (one at a time, eliminating internal concurrency issues).
3. **Can send messages** to other actors it knows about.
4. **Can create new actors** (child actors).
5. **Can change its own internal state** in response to a message.

Erlang (1986) and its OTP framework made the actor model practical for building fault-tolerant distributed systems. The BEAM VM runs millions of lightweight processes (actors) with preemptive scheduling and per-process garbage collection. Akka (2010) brought the same model to the JVM.

Key properties that transfer to frontend architecture:
- **Isolation:** Each actor's state is private. No shared mutable state.
- **Location transparency:** A message send looks the same whether the target is local or remote.
- **Supervision:** Parent actors manage child actor failures (let-it-crash + restart).
- **Mailbox ordering:** Messages to a single actor are processed in order.

### 2.2 Adaptation to Frontend: The Surma Model

Surma (former Google Chrome developer advocate) wrote the seminal article "An Actor, a model and an architect walk onto the web..." proposing Web Workers as frontend actors. In this model:

- The **main thread** is the "UI actor" -- it owns the DOM and only handles high-level semantic UI operations ("show loading spinner," "slide out nav").
- **Web Workers** are general-purpose actors that handle computation, state management, and network I/O.
- Communication uses `postMessage()`, which is inherently message-passing (no shared state between threads).

**Comlink** (Google Chrome Labs, ~1.1KB) abstracts `postMessage()` into a transparent RPC-style API:

```javascript
// worker.js
import { expose } from 'comlink';

const api = {
  async fetchProducts() { /* ... */ },
  calculateTotal(items) { /* ... */ }
};
expose(api);

// main.js
import { wrap } from 'comlink';
const api = wrap(new Worker('./worker.js', { type: 'module' }));
const products = await api.fetchProducts();
```

Comlink was used in production for Google's PROXX and Squoosh applications, demonstrating that the actor model via Web Workers is viable for real applications.

**Sources:**
- [An Actor, a model and an architect walk onto the web -- surma.dev](https://surma.dev/things/actormodel/)
- [When should you be using Web Workers? -- surma.dev](https://surma.dev/things/when-workers/index.html)
- [Comlink -- GitHub](https://github.com/GoogleChromeLabs/comlink)

### 2.3 Comparison: Actor Model vs Redux vs Signals vs Event Bus

| Dimension | Actor Model | Redux | Signals | Event Bus |
|---|---|---|---|---|
| **State ownership** | Per-actor (private) | Single global store | Per-signal (granular) | None (stateless conduit) |
| **Communication** | Typed messages (TX) | Actions dispatched to reducers | Reactive subscriptions | Arbitrary events |
| **Coupling** | Actors know addresses, not implementations | Reducers know action types | Producers and consumers share signal references | Publishers and subscribers share event names |
| **Concurrency** | Natural (one message at a time per actor) | N/A (single-threaded) | N/A (synchronous reactions) | N/A (synchronous dispatch) |
| **Debugging** | Message trace (inspectable mailbox) | Action log (Redux DevTools) | Dependency graph | Event log |
| **Isolation** | Strong (actors cannot access each other's state) | Weak (any component can read any slice) | Moderate (signals are shared references) | None (events are fire-and-forget) |
| **MFE suitability** | Excellent (address-based routing, location transparency) | Poor (requires shared store across MFEs) | Moderate (signals must be shared across boundaries) | Good (decoupled, but no delivery guarantees) |

**When to choose the actor model for frontends:**
- When micro-frontends must be truly independent (no shared state store).
- When communication needs to be both local and remote (same message, different transport).
- When you need supervision trees (parent component manages child component failures).
- When message ordering guarantees matter.
- When the architecture needs to scale from in-browser to distributed (Web Workers, Service Workers, network).

**When other approaches are simpler:**
- Signals are better for fine-grained reactivity within a single component tree.
- Redux is better when a single team owns the entire state and needs time-travel debugging.
- Event bus is sufficient for loose, fire-and-forget notifications between sibling components.

**Sources:**
- [React State Management in 2025: Context, Redux, or Signals](https://medium.com/@premchandak_11/react-state-management-in-2025-context-redux-or-signals-what-devs-actually-use-a4cbb4bfa87f)
- [XState: The Redux Alternative for Complex Application Logic](https://medium.com/@melekcharradi/xstate-the-redux-alternative-for-complex-application-logic-9747262861d1)
- [Redux in 2025: A reliable choice for complex React projects](https://stefvanwijchen.com/react-and-redux-in-2025/)

### 2.4 XState: State Machines as Actors

XState (v5.28, January 2026) has fully embraced the actor model. Every state machine in XState v5 is an actor:

```javascript
import { createMachine, createActor } from 'xstate';

const productMachine = createMachine({
  id: 'product',
  initial: 'idle',
  states: {
    idle: { on: { FETCH: 'loading' } },
    loading: {
      invoke: {
        src: 'fetchProducts',
        onDone: { target: 'loaded', actions: 'assignProducts' },
        onError: 'error'
      }
    },
    loaded: { on: { REFRESH: 'loading' } },
    error: { on: { RETRY: 'loading' } }
  }
});

const actor = createActor(productMachine);
actor.subscribe(snapshot => console.log(snapshot.value));
actor.start();
actor.send({ type: 'FETCH' });
```

XState actors can spawn child actors, send messages between actors, and model complex multi-step workflows. Framework integrations exist for React (`@xstate/react`), Vue (`@xstate/vue`), Svelte (`@xstate/svelte`), and Solid (`@xstate/solid`).

XState validates the actor model's applicability to frontend development, but it is primarily focused on state machine formalism rather than general-purpose actor communication. It excels at modeling complex UI state (multi-step forms, media players, authentication flows) but is not designed as a message bus between micro-frontends.

**Sources:**
- [XState -- GitHub](https://github.com/statelyai/xstate)
- [XState Documentation](https://stately.ai/docs/xstate)
- [Actor Model Overview -- Frontend Masters](https://frontendmasters.com/courses/xstate-v2/actor-model-overview/)

### 2.5 Actor Model for Micro-Frontend Communication

The actor model maps naturally to micro-frontend boundaries:

**Actor = MFE boundary.** Each micro-frontend is an actor with a unique address. It has private state, a public message interface (inbox), and communicates with other MFEs exclusively through messages.

**Matrix = message bus.** A root actor (the application shell) routes messages between MFE actors. Local MFEs receive messages directly; remote MFEs receive messages via network transport (WebSocket, HTTP, postMessage).

**Address space = MFE discovery.** Actors are addressed by name (e.g., `"Product"`, `"Cart"`, `"User"`). The address space provides a uniform namespace for MFE discovery without requiring compile-time knowledge of what MFEs exist.

**Message protocol = MFE contract.** The message format (`TX` in PyBend's case: `{name, source, target, data, meta, timestamp}`) is the only shared contract. MFEs do not share types, state, or function signatures.

**Supervision = MFE resilience.** If a child MFE crashes, the parent can restart it without affecting siblings. This is significantly harder to achieve with shared-state architectures.

```
                        +-----------+
                        |  Matrix   |  (Root Actor / Message Bus)
                        +-----+-----+
                              |
              +---------------+---------------+
              |               |               |
        +-----+-----+  +-----+-----+  +------+----+
        |  Product   |  |   Cart    |  |   User    |  (MFE Actors)
        |  MFE       |  |   MFE     |  |   MFE     |
        +-----+------+  +-----------+  +-----------+
              |
      +-------+-------+
      |               |
  +---+---+       +---+---+
  |Comment|       | Like  |  (Child Actors)
  | MFE   |       | MFE   |
  +-------+       +-------+
```

### 2.6 Actor Addressing and MFE Boundaries

A well-designed actor address scheme provides:

1. **Hierarchical addressing** -- `Product/42/Comment/7` naturally expresses the MFE containment hierarchy.
2. **Type-level and instance-level resolution** -- `Product` resolves to the DynamicClass (type actor); `Product/42` resolves to a specific instance.
3. **Location transparency** -- whether `Product` runs in the same document, a Web Worker, or a remote server, the message send looks the same.
4. **Wildcard/broadcast capability** -- sending to `Product/*` notifies all Product instances (watch/notify pattern).

This is exactly the addressing scheme PyBend implements: the `NTT` class maintains a static registry (`#prototypes` Map), the `Matrix` routes messages between top-level actor types, and each `DynamicClass` manages its own instance-level children.

**Sources:**
- [Unleashing the Power of Actors in Frontend Application Development](https://dev.to/ibrocodes/unleashing-the-power-of-actors-in-frontend-application-development-a9b)
- [Complete Micro Frontend Architecture Guide 2025](https://www.altersquare.io/micro-frontend-guide/)
- [Micro Frontends -- Martin Fowler](https://martinfowler.com/articles/micro-frontends.html)

---

## 3. Schema-Driven UI Architecture

### 3.1 JSON Schema as UI Contract

JSON Schema (RFC draft, currently at Draft 2020-12) was designed for data validation, but its extensibility mechanism (`json_schema_extra` in Pydantic, `x-` extensions in OpenAPI) makes it capable of carrying UI semantics:

```json
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Product",
  "properties": {
    "price": {
      "type": "number",
      "exclusiveMinimum": 0,
      "ui": {
        "widget": "currency",
        "placeholder": "0.00"
      },
      "access": {
        "view": "anyone",
        "edit": "admin"
      }
    }
  },
  "ui": {
    "field_order": ["name", "price", "description"],
    "groups": { "main": ["name", "price"], "details": ["description"] }
  },
  "access": {
    "create": { "rule": "authenticated" },
    "read": { "rule": "anyone" }
  },
  "methods": {
    "like": { "route": "/like", "methods": ["POST"], "access": { "rule": "authenticated" } }
  }
}
```

**What makes JSON Schema superior to ad-hoc JSON contracts for SDUI:**
- **Validation is built in.** The same schema that drives UI rendering also validates user input (type, minimum, maximum, pattern, required).
- **$defs for composition.** Related models (e.g., Comment inside Product) can be inlined via `$defs` and `$ref`, giving the frontend a complete view of the data graph in a single fetch.
- **Self-describing.** `$schema` and `$id` provide URLs that identify what the data is and where to find its definition. Every entity response carries its own schema reference.
- **Ecosystem tooling.** JSON Schema validators exist in every language. The schema can be used for backend validation, frontend validation, documentation generation, and test data generation.

### 3.2 Server-Driven UI (SDUI) Patterns

Server-Driven UI is an architectural pattern where the server controls not just the data but the **presentation structure** of the client application. The server sends a JSON payload that describes which components to render, in what order, and with what data.

**Three levels of server-driven UI:**

| Level | Server Controls | Client Controls | Example |
|---|---|---|---|
| **Data-driven** | Data only | Layout, components, interaction | Traditional REST API + SPA |
| **Schema-driven** | Data + field types + validation + UI hints + permissions | Component rendering, styling, interaction | PyBend, JSON Schema-based systems |
| **Layout-driven** | Data + complete layout tree + component types + actions | Component implementation only | Airbnb Ghost Platform, DivKit |

PyBend operates at Level 2 (schema-driven). The server provides everything except the actual rendering implementation: field types, widget hints, field ordering, grouping, access control, and callable methods. The frontend reads these instructions and renders accordingly, but owns the component implementations.

### 3.3 Airbnb Ghost Platform (Case Study)

Airbnb's Ghost Platform (GP) is the most widely documented production SDUI system. It powers the entire Airbnb experience across web, iOS, and Android.

**Architecture:**
- **Sections**: Independent groups of related UI components (e.g., a hero image section, a price breakdown section).
- **Screens**: Define where and how sections appear on a page.
- **Actions**: Handle user interactions (navigate, submit, dismiss).
- **Viaduct**: GraphQL-based data layer that provides strongly-typed models across all platforms.

**Key design decisions:**
1. The server returns a **component tree**, not raw data. The tree specifies component types by name (`"HeroImage"`, `"PriceBreakdown"`), and each client platform has a native implementation of each component type.
2. A/B tests, personalization, and feature flags are resolved **server-side**. The client never evaluates conditions; it simply renders what the server sends.
3. New features can ship by deploying a backend change, without waiting for app store review cycles.

**Relevance to PyBend:** PyBend's schema approach is structurally similar to Ghost Platform's Sections model. A `Product` schema with `ui.groups` and `ui.field_order` is a declarative description of what to render and how to organize it. The difference is granularity: Ghost Platform specifies exact component types and layouts; PyBend specifies field semantics and lets the frontend choose the rendering.

**Sources:**
- [A Deep Dive into Airbnb's Server-Driven UI System](https://medium.com/airbnb-engineering/a-deep-dive-into-airbnbs-server-driven-ui-system-842244c5f5)
- [Airbnb's Server-Driven UI Platform -- InfoQ](https://www.infoq.com/news/2021/07/airbnb-server-driven-ui/)
- [Server-Driven UI: What Airbnb, Netflix, and Lyft Learned](https://medium.com/@aubreyhaskett/server-driven-ui-what-airbnb-netflix-and-lyft-learned-building-dynamic-mobile-experiences-20e346265305)

### 3.4 Schema as Micro-Frontend Discovery Mechanism

In traditional MFE architectures, discovery is a solved-but-complex problem: a manifest file, a service registry, or Module Federation's remoteEntry.js. Schema-driven architectures offer a different approach:

**The schema IS the discovery mechanism.**

1. Frontend requests `GET /Product` -- receives the complete schema.
2. Schema contains `$defs` with all related models (Comment, Like, etc.).
3. Schema contains `methods` with callable endpoints.
4. Schema contains `ui.renderer` hints specifying which component to use.
5. Each entity response contains `$schema` (pointing to its schema) and `$id` (pointing to itself).

No separate registry, no manifest, no build-time configuration. The schema tells the frontend everything it needs to know: what data exists, how it is structured, what operations are available, who can perform them, and how to render it.

This is the pattern PyBend implements: `NTT.SCHEMA(data)` receives a schema, calls `prototype()` to create a DynamicClass, registers nested `$defs` models, and triggers an initial `READ`. The entire MFE bootstrap is a single HTTP GET.

### 3.5 Runtime Component Generation from Schema

PyBend's `prototype()` function is a runtime class factory that creates a DynamicClass from a JSON Schema:

```javascript
function prototype(addr, schema, href) {
    const fields = Object.keys(schema.properties || {});
    const methods = Object.keys(schema.methods || {});

    const DynamicClass = class extends NTT {
        static _schema = schema;
        // ... typed getters/setters for each field
        // ... method stubs for each schema method
    };

    // Add typed properties with validation
    for (const field of fields) {
        Object.defineProperty(DynamicClass.prototype, field, {
            get() { return this.value?.[field]; },
            set(value) {
                // Type checking against schema definition
                // ...
            }
        });
    }

    // Add callable methods
    for (const method of methods) {
        DynamicClass.prototype[method] = function(...args) {
            this.call(method, ...args);
        };
    }

    return DynamicClass;
}
```

This is a rare approach in frontend architecture. Most SDUI systems use a fixed set of component types and select between them based on server instructions. PyBend goes further: it **generates the entity class itself** from the schema, including typed properties with validation, callable methods, and lifecycle hooks. The component (`ntt-item`, `ntt-list`) is generic; the entity class is schema-specific.

### 3.6 Comparison: Schema-Driven vs GraphQL-Driven vs OpenAPI-Driven vs HATEOAS

| Approach | Schema Source | Discovery | UI Semantics | Runtime Adaptation |
|---|---|---|---|---|
| **JSON Schema (PyBend)** | Backend model -> JSON Schema | Schema endpoint per model (`GET /Product`) | Embedded (`ui`, `access`, `methods`) | Full (DynamicClass from schema) |
| **GraphQL SDUI** | GraphQL schema + query responses | Introspection query | Union types for component variants | Moderate (component selection by type) |
| **OpenAPI-Driven** | OpenAPI spec (YAML/JSON) | Spec endpoint (`/openapi.json`) | Limited (`x-` extensions) | Code generation (build-time, not runtime) |
| **HATEOAS** | Hypermedia links in responses | Link relations in each response | None (links describe transitions, not UI) | Navigation only (follow links) |

**JSON Schema approach (PyBend's choice):**
- Strengths: Self-contained (one fetch = complete UI contract), extensible (json_schema_extra carries arbitrary UI metadata), runtime-first (no code generation step).
- Weaknesses: No standard for UI extensions (every system invents its own `ui` object), schema size grows with model complexity.

**GraphQL SDUI (Airbnb's choice):**
- Strengths: Strongly-typed, proven at scale, query flexibility (request only needed fields), tooling ecosystem (Apollo, Relay).
- Weaknesses: Requires a GraphQL server, client-side query management, schema stitching complexity for MFEs.

**OpenAPI-Driven:**
- Strengths: Industry standard for REST APIs, excellent code generation (openapi-generator supports 50+ languages), documentation (Swagger UI).
- Weaknesses: Build-time code generation (not runtime adaptive), UI semantics require custom extensions, spec is API-focused not UI-focused.

**HATEOAS:**
- Strengths: Maximum decoupling (client discovers everything via link relations), self-documenting (follow links, no hardcoded URLs).
- Weaknesses: No UI semantics (links describe state transitions, not presentation), verbose payloads, limited adoption outside Spring ecosystem.
- **HTMX resurgence (2025-2026):** HTMX implements HATEOAS by returning HTML fragments. It added 16.8K GitHub stars in 2024, beating React in the "Front-end Frameworks" category of JavaScript Rising Stars. HTMX represents a return to server-rendered hypermedia but is orthogonal to the Web Components + JSON Schema approach.

**Sources:**
- [Server-Driven UI Schema Design -- Apollo GraphQL](https://www.apollographql.com/docs/graphos/schema-design/guides/sdui/schema-design)
- [HATEOAS: Building Self-Documenting REST APIs That Scale](https://pradeepl.com/blog/rest/hateoas/)
- [The HTMX Renaissance -- Rethinking Web Architecture for 2026](https://www.softwareseni.com/the-htmx-renaissance-rethinking-web-architecture-for-2026/)
- [OpenAPI and Frontend](https://dev.to/gin_mitch/openapi-and-frontend-3gnb)
- [Schema-Driven UI Components: Revolutionizing Headless ERP with GraphQL -- GraphQLConf 2024](https://graphql.org/conf/2024/schedule/b43e5c894796be3b0b0f0d0b662d4a5a/)
- [Server-Driven UI with GraphQL & WebAssembly -- IEEE Computer Society](https://www.computer.org/publications/tech-news/trends/server-driven-ui)

---

## 4. The Buildless / No-Bundler Approach

### 4.1 Import Maps as the Foundation

Import maps are the key enabler for buildless JavaScript. They allow the browser to resolve bare module specifiers (like `import { html } from 'lit'`) without a bundler:

```html
<script type="importmap">
{
  "imports": {
    "lit": "https://esm.sh/lit@3.1.0",
    "@shoelace/": "https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.12.0/dist/",
    "./config.js": "./config.production.js"
  },
  "scopes": {
    "/vendor/legacy/": {
      "lodash": "https://esm.sh/lodash@4.17.21"
    }
  }
}
</script>
<script type="module" src="./app.js"></script>
```

**Key capabilities:**
- **Bare specifier resolution:** `import 'lit'` resolves to the URL specified in the import map, exactly like a bundler's `node_modules` resolution but at runtime.
- **Scoped resolution:** Different parts of the application can use different versions of the same package via `scopes`.
- **Aliasing:** `"./config.js": "./config.production.js"` redirects imports for environment-specific configuration.
- **Browser support:** Chrome 89+, Edge 89+, Firefox 108+, Safari 16.4+. The `es-module-shims` polyfill provides support for older browsers.

Import maps are specified once in the HTML document and apply to all `<script type="module">` on the page. They cannot be dynamically added after the first module has loaded (this is a specified limitation), though there are proposals for dynamic import map injection.

### 4.2 HTTP/2 Multiplexing Negating the Need for Bundling

The original motivation for bundling JavaScript was HTTP/1.1's limitation: browsers opened a maximum of 6 TCP connections per origin, and each request required a full round-trip. Bundling 100 modules into 1 file was a necessary optimization.

HTTP/2 changes this equation:
- **Multiplexing:** Unlimited requests can share a single TCP connection, interleaved at the frame level.
- **Header compression (HPACK):** Repeated headers are compressed to near-zero overhead.
- **Stream prioritization:** The browser can signal which resources are most important.
- **Server push (deprecated in Chrome, replaced by 103 Early Hints):** The server can proactively send resources.

With HTTP/2, the cost of 100 separate module requests is approximately equal to 1 bundled request in terms of network overhead. The main remaining cost is **connection latency** (if modules are loaded in dependency-chain order, each level adds a round-trip).

**When HTTP/2 does NOT eliminate the need for bundling:**
- **Deep dependency chains.** If module A imports B, B imports C, C imports D, each level requires a round-trip to discover the next dependency. Flat dependency structures work well; deep trees do not.
- **Many small files.** While HTTP/2 multiplexing handles concurrency, each file still requires processing overhead (parsing, compilation). Bundling amortizes this.
- **Cross-origin dependencies.** Each origin requires a separate TLS handshake. Import maps pointing to multiple CDNs create connection overhead.

**Sources:**
- [The Role of HTTP/2 in Web Performance Optimization](https://blog.pixelfreestudio.com/the-role-of-http-2-in-web-performance-optimization/)
- [JavaScript Modules in 2025: ESM, Import Maps & Best Practices](https://siddsr0015.medium.com/javascript-modules-in-2025-esm-import-maps-best-practices-7b6996fa8ea3)

### 4.3 Development vs Production Tradeoffs

| Concern | Buildless (Dev) | Bundled (Prod) | Impact |
|---|---|---|---|
| **Iteration speed** | Instant (save -> refresh) | Seconds (build -> refresh) | Developer experience |
| **Module count** | Many small files | Few bundles | Network overhead vs cache granularity |
| **Tree shaking** | Not possible | Effective | Bundle size (20-50% reduction for libraries) |
| **Minification** | None | Aggressive | File size (30-50% reduction) |
| **Source maps** | Unnecessary (source IS production) | Required for debugging | Debugging experience |
| **Cache invalidation** | Per-file (unchanged modules stay cached) | Per-bundle (any change invalidates the entire bundle) | Cache efficiency |
| **Dead code** | Loaded but potentially unused | Eliminated | Bandwidth waste vs build complexity |

The practical recommendation (2026): **buildless in development, optional light build for production.**

The "light build" is not webpack-style transformation. It is:
1. **Minification** via `esbuild` (fast, no config).
2. **Compression** (Brotli/gzip, handled by the server or CDN).
3. Optionally, **bundling critical-path modules** into a small number of chunks.

This preserves the buildless development experience while addressing the real-world performance gaps.

### 4.4 ESM CDNs

ESM CDNs serve npm packages as ES Modules, enabling imports directly in the browser without a local `node_modules`:

| CDN | URL Pattern | Strengths | Caveats |
|---|---|---|---|
| **esm.sh** | `https://esm.sh/lit@3.1.0` | Deno-native, esbuild-powered, TypeScript support | First-request compilation latency |
| **Skypack** | `https://cdn.skypack.dev/lit@3.1.0` | Auto ESM conversion, minification, TypeScript types via headers | Some packages fail conversion |
| **jspm.io** | `https://ga.jspm.io/npm:lit@3.1.0/...` | Import map-aware, generates import maps via API | More complex URL structure |
| **jsdelivr** | `https://cdn.jsdelivr.net/npm/lit@3.1.0/+esm` | Largest CDN, `+esm` suffix for ESM output | Not all packages support ESM |
| **unpkg** | `https://unpkg.com/lit@3.1.0?module` | Simple, npm mirror | `?module` flag unreliable for complex packages |

**For production use:** esm.sh and jspm.io are the most reliable for complex packages. Skypack excels for prototyping. jsdelivr is best for popular, well-maintained packages that already ship ESM.

**For PyBend's buildless architecture:** These CDNs enable the use of third-party libraries (e.g., a Markdown renderer, a date formatting library) without any build step. An import map in the HTML entry point resolves bare imports to the CDN:

```html
<script type="importmap">
{
  "imports": {
    "marked": "https://esm.sh/marked@12.0.0"
  }
}
</script>
```

**Sources:**
- [Choose the Best JS CDN -- Compare NPM Alternatives](https://blog.blazingcdn.com/en-us/choose-best-js-cdn-compare-npm-alternatives-skypack-jsdelivr-unpkg)
- [Buildless workflow through import maps](https://dev.to/matsuuu/buildless-workflow-through-import-maps-featuring-lit-shoelace-and-more-4ill)
- [ES Modules + Importmaps: a modern JS stack](https://www.stevendcoffey.com/blog/esmodules-importmaps-modern-js-stack/)

### 4.5 When a Build Step Is Still Necessary

Despite the buildless movement, certain scenarios still require a build step:

1. **TypeScript.** Browsers do not execute `.ts` files. TypeScript requires compilation to `.js`. (PyBend avoids this by using vanilla JS.)
2. **JSX.** React's JSX requires transformation to `React.createElement()` or `jsx()` calls. (PyBend uses template literals, no JSX.)
3. **Tree shaking large libraries.** Importing `lodash` without tree shaking pulls in the entire library (~70KB minified). A bundler can reduce this to only the functions used.
4. **CSS preprocessing.** Sass, Less, PostCSS, and Tailwind all require a build step to produce browser-compatible CSS.
5. **Image optimization.** Responsive images, WebP/AVIF conversion, and sprite generation are build-time operations.
6. **Minification and compression.** While not strictly "building," production deployment benefits from minification (esbuild) and pre-compression (Brotli).

### 4.6 The Optional Build Step Pattern

The recommended pattern for buildless-first development:

```
Development:
  browser -> ES modules -> import map -> local files
  (No build. Save and refresh.)

Production:
  esbuild -> minify -> Brotli compress -> serve
  (30 seconds. No config. Same source files.)
```

This is the approach advocated by modern-web.dev and open-wc.org. The build step is:
- **Optional** (the app works without it).
- **Additive** (it optimizes, it does not transform).
- **Fast** (esbuild processes thousands of modules in under a second).
- **Configurable per-module** (critical path modules can be bundled; rarely-used modules stay separate for cache efficiency).

**Sources:**
- [Modern web apps without JavaScript bundling or transpiling -- DHH](https://world.hey.com/dhh/modern-web-apps-without-javascript-bundling-or-transpiling-a20f2755)
- [Writing Modern JavaScript without a Bundler](https://playfulprogramming.com/posts/modern-js-bundleless/)
- [Developing Without a Build: Introduction](https://dev.to/open-wc/developing-without-a-build-1-introduction-26ao)

---

## 5. Native Federation (ES Modules + Import Maps as MFE Infrastructure)

### 5.1 How Native Federation Differs from Module Federation

**Module Federation (webpack 5):**
- Webpack-specific. Requires webpack on both the host and the remote.
- Uses webpack's runtime to resolve and load remote modules.
- Shared dependencies are managed by webpack's shared scope, which negotiates versions at runtime.
- The `remoteEntry.js` file is a webpack-generated bootstrap that exposes modules.

**Native Federation:**
- Uses browser-native ES Modules and Import Maps.
- Works with any build tool (esbuild, Rollup, Vite, or no build tool at all).
- Shared dependencies are managed via Import Map scopes.
- Metadata is stored in `federation.json` (a plain JSON manifest), not a webpack-specific bootstrap.

The key insight: Module Federation solved a real problem (runtime module sharing between independently deployed applications), but it solved it with webpack-specific machinery. Native Federation achieves the same result using web standards that browsers already support.

```
Module Federation:                  Native Federation:
webpack runtime -> remoteEntry.js   browser -> import map -> ES module
(webpack-specific)                  (web standard)
```

### 5.2 Angular Architects' Native Federation Implementation

Manfred Steyer and the Angular Architects team created `@softarc/native-federation` (framework-agnostic) and `@angular-architects/native-federation` (Angular-specific) as a bridge from Module Federation to web standards.

**How it works:**
1. Each micro-frontend's build produces: an ESM bundle, a `federation.json` manifest, and static assets.
2. The host application generates an Import Map from the collected `federation.json` files of all remotes.
3. The browser resolves modules using the Import Map. No webpack runtime, no special module format.
4. Shared dependencies (e.g., Angular core, RxJS) appear in the Import Map's `scopes` section, enabling version isolation.

**Configuration (conceptual):**
```javascript
// federation.config.js (remote)
module.exports = {
  name: 'product-mfe',
  exposes: {
    './ProductList': './src/product-list.component.js'
  },
  shared: {
    '@angular/core': { singleton: true, requiredVersion: '^17.0.0' }
  }
};
```

The build produces a standard ES module and a `federation.json`:
```json
{
  "name": "product-mfe",
  "exposes": {
    "./ProductList": "./product-list-abc123.js"
  },
  "shared": {
    "@angular/core": { "version": "17.1.0", "singleton": true }
  }
}
```

The host reads these manifests and generates an Import Map dynamically.

**Sources:**
- [Import Maps - The Next Evolution Step for Micro Frontends?](https://www.angulararchitects.io/en/blog/import-maps-the-next-evolution-step-for-micro-frontends-article/)
- [@angular-architects/native-federation -- npm](https://www.npmjs.com/package/@angular-architects/native-federation)
- [Micro Frontends with Native Federation](https://dev.to/florianrappl/micro-frontends-with-native-federation-56j4)
- [Micro-frontends in Angular with Native Federation (2025)](https://medium.com/@ramalakshmanan1497/micro-frontends-in-angular-with-native-federation-2025-a-practical-end-to-end-guide-22c6815325f4)

### 5.3 The Mercedes-Benz.io Approach

Mercedes-Benz.io published a detailed architecture for orchestrating micro-frontends with Import Maps, arguing "You Might Not Need Module Federation."

**Architecture:**

```
+--------------------+      +-------------------+
|  Team A            |      |  Team B           |
|  (React MFE)       |      |  (Vue MFE)        |
|                    |      |                   |
|  Build produces:   |      |  Build produces:  |
|  - ESM bundle      |      |  - ESM bundle     |
|  - Manifest        |      |  - Manifest       |
|  - Static assets   |      |  - Static assets  |
+--------+-----------+      +--------+----------+
         |                           |
         v                           v
+---------------------------------------------+
|  Import Map Resolver (Nest.js server)       |
|  - Stores/updates import map entries        |
|  - Accepts JS asset submissions from CI/CD  |
|  - Generates runtime import map             |
+---------------------------------------------+
         |
         v
+---------------------------------------------+
|  Host Application                           |
|  <script type="importmap">                  |
|    { "imports": {                           |
|        "team-a/product": "/mfe/product.js", |
|        "team-b/cart": "/mfe/cart.js"        |
|    }}                                       |
|  </script>                                  |
+---------------------------------------------+
```

**Key design decisions:**
1. **Each team has full autonomy** over tech stack, build tools, and CI/CD. The only constraint: produce an ESM bundle and a manifest.
2. **The Import Map Resolver** is a lightweight Nest.js server that aggregates manifests and generates the runtime import map.
3. **Dependency inversion via the import map.** The host application depends on abstract names (`"team-a/product"`), not concrete URLs. Updating a micro-frontend is as simple as updating the import map entry -- takes seconds, no host rebuild.
4. **No vendor lock-in.** Unlike Module Federation (webpack-only), this approach works with any build tool or no build tool.

**Sources:**
- [You Might Not Need Module Federation -- Mercedes-Benz.io](https://www.mercedes-benz.io/2023/01/05/you-might-not-need-module-federation-orchestrate-your-microfrontends-at-runtime-with-import-maps/)
- [MO360 Frontend Toolkit](https://mercedes-benz.github.io/mo360-ftk/docs/content/what-is-ftk.html)

### 5.4 Using Scopes for Version Isolation

Import Map `scopes` are the mechanism for running different versions of the same dependency in different micro-frontends:

```html
<script type="importmap">
{
  "imports": {
    "lodash": "https://esm.sh/lodash@4.17.21"
  },
  "scopes": {
    "/mfe/legacy-dashboard/": {
      "lodash": "https://esm.sh/lodash@3.10.1"
    },
    "/mfe/new-checkout/": {
      "lodash": "https://esm.sh/lodash-es@4.17.21"
    }
  }
}
```

When code loaded from `/mfe/legacy-dashboard/` imports `"lodash"`, it gets version 3.10.1. Code from `/mfe/new-checkout/` gets `lodash-es@4.17.21`. All other code gets the default `4.17.21`.

This provides the same capability as Module Federation's `shared` scope negotiation, but using a browser-native mechanism with no runtime overhead.

### 5.5 Dynamic Import Map Generation by the Server

For PyBend-style architectures where the backend is authoritative, the server can generate the import map dynamically:

```python
# Conceptual: backend generates import map based on registered models
@app.get("/importmap.json")
def get_import_map():
    imports = {}
    for model_name, model_class in registered_models.items():
        # If the model has a custom frontend component, register it
        if hasattr(model_class, '__ui__') and 'component' in model_class.__ui__:
            imports[f"components/{model_name}"] = model_class.__ui__['component']
    return {"imports": imports}
```

The HTML page loads the import map from the server:
```html
<script type="importmap" src="/importmap.json"></script>
```

Note: As of early 2026, external import maps (via `src` attribute) are not yet standardized. The current workaround is to inline the import map via a `<script>` tag, either statically in the HTML template or dynamically injected before any module `<script>` tags load. There is an active proposal (Import Map Integrity) to support external import maps with integrity checking.

---

## 6. Performance Optimization for Buildless MFE

### 6.1 `<link rel="modulepreload">` for Critical Paths

`modulepreload` is the ES Module equivalent of `preload`, but it goes further: it not only downloads the file but **parses and compiles it**, storing the result in the module map ready for immediate execution.

```html
<!-- Preload the critical module chain -->
<link rel="modulepreload" href="/static/core/NTT.js">
<link rel="modulepreload" href="/static/core/Actor.js">
<link rel="modulepreload" href="/static/core/Matrix.js">
<link rel="modulepreload" href="/static/core/TX.js">
<link rel="modulepreload" href="/static/core/Observable.js">

<!-- Application entry point -->
<script type="module" src="/static/app.js"></script>
```

**Why this matters for buildless architectures:**
Without `modulepreload`, the browser discovers dependencies one level at a time:
1. Parse `app.js` -> discover it imports `NTT.js`.
2. Fetch and parse `NTT.js` -> discover it imports `Actor.js`, `Matrix.js`, `TX.js`.
3. Fetch and parse those -> discover their dependencies.

Each level adds a network round-trip. With 4 levels of imports, that is 4 sequential round-trips before any code executes.

`modulepreload` flattens this: all modules are fetched in parallel on page load, parsed, and compiled. When `app.js` executes and imports `NTT.js`, it is already compiled and ready in the module map. Zero waterfall.

**Practical guidance:**
- Preload your critical path (the modules that must load for first render).
- Do NOT preload everything (that defeats the purpose of lazy loading).
- Generate modulepreload hints automatically from your module dependency graph.

**Sources:**
- [rel="modulepreload" | MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/modulepreload)
- [Browser Resource Hints: preload, prefetch, and preconnect](https://www.debugbear.com/blog/resource-hints-rel-preload-prefetch-preconnect)
- [Frontend Performance Checklist 2025](https://strapi.io/blog/frontend-performance-checklist)

### 6.2 Service Worker Caching Strategies

Service Workers provide programmable caching that is particularly powerful for buildless MFE architectures where individual modules are separate files:

**Strategy mapping for MFE resources:**

| Resource Type | Strategy | Rationale |
|---|---|---|
| Schema responses (`GET /Product`) | **Stale-While-Revalidate** | Show cached schema instantly; update in background. Schema changes are rare. |
| Static JS modules | **Cache-First** | ES modules are immutable at a given URL (add version hash to URL for invalidation). |
| Entity data (`GET /products`) | **Network-First** | Data changes frequently; show fresh data when online, cached data when offline. |
| CDN dependencies | **Cache-First** | Versioned URLs (e.g., `esm.sh/lit@3.1.0`) are immutable. Cache forever. |
| HTML entry point | **Network-First** | Must reflect latest import map and modulepreload hints. |

**Implementation pattern for buildless MFE:**

```javascript
// service-worker.js
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (url.pathname.endsWith('.js')) {
    // Cache-First for JS modules
    event.respondWith(
      caches.match(event.request).then(cached =>
        cached || fetch(event.request).then(response => {
          const cache = await caches.open('modules-v1');
          cache.put(event.request, response.clone());
          return response;
        })
      )
    );
  } else if (url.pathname.match(/^\/[A-Z]/)) {
    // Stale-While-Revalidate for schema endpoints
    event.respondWith(
      caches.match(event.request).then(cached => {
        const fetched = fetch(event.request).then(response => {
          const cache = await caches.open('schemas-v1');
          cache.put(event.request, response.clone());
          return response;
        });
        return cached || fetched;
      })
    );
  }
});
```

**Key benefit for MFE:** When a micro-frontend is updated, only its specific module files are re-fetched. All other MFE modules remain cached. This granular cache invalidation is a significant advantage over bundled approaches where any change invalidates the entire bundle.

**Sources:**
- [Caching -- Progressive web apps | MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Caching)
- [Micro-frontends and Service Workers](https://microfrontend.dev/web-standards/micro-frontends-service-workers/)
- [Optimizing Frontend Caching with Service Workers and Cache Strategies](https://medium.com/@ddylanlinn/optimizing-frontend-caching-with-service-worker-and-cache-strategy-4131ae1d9aa8)
- [Module Federation and Angular Service Workers (PWA)](https://www.bitovi.com/blog/module-federation-and-angular-service-workers-pwa)

### 6.3 HTTP/2 Server Push / 103 Early Hints

HTTP/2 Server Push has been deprecated in Chrome (removed in Chrome 106). The replacement is **103 Early Hints**, which provides the same performance benefit with better semantics:

**How 103 Early Hints works:**
1. Browser requests `GET /static/matrix.html`.
2. Server immediately sends `HTTP/1.1 103 Early Hints` with `Link` headers, before generating the full response.
3. Browser begins fetching the hinted resources in parallel.
4. Server sends the final `200 OK` response with the full HTML.

```http
HTTP/1.1 103 Early Hints
Link: </static/core/NTT.js>; rel=modulepreload
Link: </static/core/Actor.js>; rel=modulepreload
Link: </static/core/Matrix.js>; rel=modulepreload
Link: <https://fonts.googleapis.com>; rel=preconnect

HTTP/1.1 200 OK
Content-Type: text/html
...
```

The browser starts fetching `NTT.js`, `Actor.js`, and `Matrix.js` while the server is still generating the HTML response. This can save 100-500ms on initial page load.

**Requirements:**
- HTTP/2 or HTTP/3 connection (most browsers only accept 103 over these protocols).
- Server support: Nginx 1.25.3+, Cloudflare (automatic), Fastly, Netlify.
- Python/FastAPI: Requires a reverse proxy (Nginx, Caddy) in front to send the 103 response, as ASGI servers do not natively support informational responses.

**Sources:**
- [103 Early Hints | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/103)
- [Faster page loads using server think-time with Early Hints | Chrome Developers](https://developer.chrome.com/docs/web-platform/early-hints)
- [How To Improve Page Speed With 103 Early Hints](https://www.debugbear.com/blog/103-early-hints)
- [Implementing Early Hints (103)](https://dohost.us/index.php/2025/12/31/implementing-early-hints-103-telling-the-browser-what-to-fetch-before-the-page-loads/)

### 6.4 Preconnect and DNS Prefetch for Cross-Origin MFEs

When micro-frontends load resources from multiple origins (CDNs, API servers, other MFE hosts), connection setup overhead becomes significant:

```html
<!-- DNS resolution + TCP connection + TLS handshake to API server -->
<link rel="preconnect" href="https://api.example.com">

<!-- DNS resolution only (cheaper, useful for less-critical origins) -->
<link rel="dns-prefetch" href="https://esm.sh">
<link rel="dns-prefetch" href="https://cdn.jsdelivr.net">

<!-- Cross-origin font/asset CDN -->
<link rel="preconnect" href="https://fonts.googleapis.com" crossorigin>
```

**Cost of each step:**
- DNS lookup: 20-120ms (varies by ISP, caching, geography).
- TCP handshake: 1 RTT (round-trip time, typically 10-100ms).
- TLS handshake: 1-2 RTTs (10-200ms).

For a buildless MFE using esm.sh for dependencies and a separate API server, `preconnect` to both origins can save 100-400ms on the critical path.

**Best practice:** Limit `preconnect` to 2-4 origins. Each preconnection consumes a TCP socket. Too many preconnections compete with actual resource fetches.

### 6.5 Module Preloading Based on Route Prediction

For multi-page MFE applications (or SPAs with multiple views), preloading modules for likely-next routes reduces navigation latency:

**Strategies:**

1. **Static route hints.** The current page declares which routes are likely next:
```html
<!-- On the product list page, prefetch the product detail module -->
<link rel="modulepreload" href="/static/components/ntt-detail.js">
```

2. **Idle-time preloading.** Use `requestIdleCallback` to preload secondary modules after the main content renders:
```javascript
requestIdleCallback(() => {
  // Preload modules for routes the user might navigate to
  import('/static/components/ntt-detail.js');
  import('/static/components/ntt-form.js');
});
```

3. **Hover-based preloading.** Start loading a route's modules when the user hovers over a link:
```javascript
document.querySelectorAll('[data-route]').forEach(link => {
  link.addEventListener('mouseenter', () => {
    const route = link.dataset.route;
    import(`/static/routes/${route}.js`);
  }, { once: true });
});
```

4. **Schema-based prediction.** In PyBend's architecture, the schema contains the information needed for prediction. When the Product schema includes `$defs.Comment`, the frontend knows Comment rendering will be needed soon:
```javascript
// After receiving Product schema, preload Comment's component
if (schema.$defs?.Comment) {
  import('/static/components/ntt-item.js');
  // The Comment DynamicClass will be created from schema,
  // but its rendering component should be warm in the module cache.
}
```

**Sources:**
- [Prefetching, prerendering, and service worker precaching | web.dev](https://web.dev/learn/performance/prefetching-prerendering-precaching)
- [10 Micro-Frontend Performance Rules That Won't Backfire](https://medium.com/@ThinkingLoop/10-micro-frontend-performance-rules-that-wont-backfire-d227c6a1c382)
- [Frontend Performance Checklist For 2025](https://crystallize.com/blog/frontend-performance-checklist)
- [The Front-End Performance Optimization Handbook](https://www.freecodecamp.org/news/the-front-end-performance-optimization-handbook/)

---

## 7. Relevance to PyBend

### 7.1 What PyBend Already Does Right

PyBend's architecture aligns with several emerging best practices documented in this research:

**Actor-based message bus.** The `Matrix` -> `Actor` -> `TX` system implements the actor model for component communication. The `NTT` class serves as both a type registry and an actor, with hierarchical addressing (`Product/42/Comment/7`) that maps naturally to REST resource paths. This is architecturally superior to event bus or shared-state approaches for MFE isolation.

**Schema as single source of truth.** The `NTT.SCHEMA()` -> `prototype()` -> DynamicClass pipeline is a runtime implementation of schema-driven UI. The backend model definition generates the JSON Schema, the schema generates the frontend entity class, and the generic components (`ntt-item`, `ntt-list`) render based on schema instructions. This matches the Level 2 (schema-driven) SDUI pattern described in Section 3.2.

**Buildless by default.** PyBend serves raw ES Modules with no build step. This is exactly the approach advocated by the open-wc community and the "going buildless" movement. The architecture is production-viable for the component-based, non-framework approach PyBend uses.

**Custom Elements as MFE boundaries.** Each `ntt-*` component is a standard Custom Element with lifecycle management via `connectedCallback`/`disconnectedCallback`. This provides natural MFE lifecycle management without external frameworks like single-spa.

### 7.2 Opportunities Identified by This Research

**Constructable Stylesheets.** PyBend could benefit from shared `CSSStyleSheet` objects for design tokens, adopted across all `ntt-*` component shadow roots. This would provide efficient theming without style duplication.

**Import maps for dependency management.** If PyBend ever needs third-party frontend dependencies, an import map provides resolution without a build step. The server could generate the import map dynamically based on registered models' requirements.

**`modulepreload` for critical path.** Adding `<link rel="modulepreload">` hints for `NTT.js`, `Actor.js`, `Matrix.js`, and `TX.js` in the HTML entry point would eliminate the module discovery waterfall and improve initial load performance.

**Service Worker caching.** A Service Worker with Cache-First for static JS modules and Stale-While-Revalidate for schema responses would provide near-instant subsequent loads and offline capability.

**103 Early Hints.** With a reverse proxy (Nginx/Caddy) in front of the FastAPI server, 103 Early Hints could push critical module files to the browser before the HTML response is generated.

**Declarative Shadow DOM for SSR.** If PyBend adds server-side rendering support, DSD enables Web Component content to appear before JavaScript loads, improving First Contentful Paint.

### 7.3 Architecture Validation

This research validates PyBend's architectural choices:

1. **Vanilla Web Components (no framework)** is a mainstream, well-supported approach in 2026, not a niche decision.
2. **Actor model for frontend communication** has theoretical grounding (Erlang/Akka) and practical validation (Surma's architecture, XState v5, Comlink).
3. **Schema-driven UI** is proven at scale (Airbnb Ghost Platform, Apollo SDUI, DivKit) and PyBend's implementation is a clean instance of this pattern.
4. **Buildless development** is viable for Web Component architectures and is actively advocated by the open-wc community.
5. **ES Modules + Import Maps** are the emerging standard for micro-frontend infrastructure, replacing webpack-specific solutions.

The architecture is not just viable -- it is aligned with the direction the web platform is moving. The standards PyBend builds on (Custom Elements, ES Modules, JSON Schema) are stable, widely supported, and actively evolving in directions that benefit this approach.
