# Micro-Frontend Architecture: Technical Deep Dive

> A comprehensive technical analysis of micro-frontend architecture patterns, their
> evolution from 2016 to 2026, and current best practices for building scalable,
> independently deployable frontend systems.

---

## Table of Contents

1. [Historical Evolution](#1-historical-evolution)
2. [Architecture Patterns Deep Dive](#2-architecture-patterns-deep-dive)
3. [The Module Federation Era (2020-2024)](#3-the-module-federation-era-2020-2024)
4. [The Native Federation / Import Maps Era (2024-2026)](#4-the-native-federation--import-maps-era-2024-2026)
5. [Communication Patterns](#5-communication-patterns)
6. [Testing Strategies for MFEs](#6-testing-strategies-for-mfes)
7. [DevOps and CI/CD for MFEs](#7-devops-and-cicd-for-mfes)
8. [Security Considerations](#8-security-considerations)

---

## 1. Historical Evolution

### 1.1 Origins: The ThoughtWorks Technology Radar (2016)

The term "micro frontends" first appeared in the [ThoughtWorks Technology Radar](https://www.thoughtworks.com/radar/techniques/micro-frontends) in November 2016 (Volume 15). It was listed in the **Assess** ring, signaling an emerging technique worth investigating. The concept addressed a concrete and growing pain: backend architectures had largely migrated to microservices, but browser-side code remained a monolithic artifact -- a single, brittle SPA owned by one team, built with one framework, deployed as one unit.

The core idea was deceptively simple: extend microservice principles to the frontend. Each feature of a web application would be owned end-to-end -- frontend through backend -- by an independent team, developed with independent tooling, tested independently, and deployed independently.

**Radar progression:**

| Year | Ring | Signal |
|------|------|--------|
| Nov 2016 | Assess | "Worth exploring with the goal of understanding how it will affect your enterprise" |
| 2017-2018 | Trial | "Worth pursuing. Important to understand how to build up this capability" |
| Apr 2019 | Adopt | "We feel strongly that the industry should be adopting these items" |

By 2019, ThoughtWorks moved micro frontends to **Adopt** -- their strongest endorsement -- reflecting real-world success at companies like Zalando, IKEA, Spotify, and DAZN.

### 1.2 The iframe Era (Pre-2016)

Before the term existed, the pattern did. Organizations had been composing web pages from independent sources since the early web:

- **Framesets (1990s):** HTML `<frameset>` tags divided the browser window into independent document regions, each with its own URL. Framesets were deprecated in HTML5 but established the mental model of "independent pages composing a single view."

- **iframes (2000s):** The `<iframe>` element survived HTML5's purge and became the de facto integration mechanism for embedding third-party content (payment forms, chat widgets, advertising). Portals like iGoogle and Netvibes used iframes to compose dashboards from independent widget providers. The isolation was strong -- separate documents, separate JS contexts, separate stylesheets -- but the cost was severe: no shared styling, no shared navigation, communication limited to `window.postMessage`, SEO invisibility, and performance overhead from loading multiple complete documents.

### 1.3 Server-Side Composition (2014-2018)

E-commerce companies discovered that iframes were unsuitable for their page-assembly needs. Amazon's product pages, for example, were already composed from dozens of independent services on the server side. This led to formalized server-side composition:

- **SSI (Server Side Includes):** Nginx and Apache supported `<!--#include virtual="/header" -->` directives, allowing a web server to fetch HTML fragments from separate upstream services and stitch them into a single response. Simple but limited -- no streaming, no error handling for individual fragments.

- **ESI (Edge Side Includes):** Varnish, Akamai, and Fastly supported `<esi:include src="/fragment" />` tags processed at the CDN layer. This moved composition closer to the user, reducing latency, but added CDN complexity and limited dynamic capabilities.

- **Zalando's Project Mosaic (2015-2016):** The online fashion retailer open-sourced [Tailor.js](https://www.mosaic9.org/), a Node.js layout service inspired by Facebook's BigPipe. Tailor asynchronously fetched multiple fragments, assembled their response streams, and piped the final response to the client -- achieving impressive Time to First Byte (TTFB) by streaming as soon as the first fragment responded.

- **Podium (2018):** Finn.no (Norwegian classifieds) released [Podium](https://podium-lib.io/), a structured approach with "podlets" (fragments) and "layouts" (composers). Podlets exposed standardized endpoints for HTML content and assets; layouts fetched, composed, and returned the assembled page.

### 1.4 Client-Side Composition and Single-SPA (2018-2019)

As SPAs dominated, server-side composition became insufficient -- it could stitch HTML but could not orchestrate client-side JavaScript lifecycle. The need for a client-side orchestrator produced [Single-SPA](https://single-spa.js.org/) (originally created in 2015, but maturing significantly in 2018-2019):

- A root application registers micro frontends with route-matching predicates
- Each micro frontend exposes lifecycle hooks: `bootstrap()`, `mount()`, `unmount()`
- Single-SPA manages activation/deactivation as the user navigates
- Framework-specific adapters (`single-spa-react`, `single-spa-vue`, `single-spa-angular`) bridge lifecycle hooks to framework-specific mount/unmount behavior

Single-SPA proved that multiple frameworks could coexist in a single page, but it left unsolved the critical question: **how do you load the micro frontend code in the first place?**

### 1.5 Martin Fowler's Seminal Article (June 2019)

[Cam Jackson's article on martinfowler.com](https://martinfowler.com/articles/micro-frontends.html) -- published in June 2019 under Martin Fowler's editorial oversight -- became the definitive reference. The article's influence was substantial for several reasons:

1. **Legitimacy:** Publishing on martinfowler.com lent architectural credibility to a technique that many dismissed as over-engineering.

2. **Comprehensiveness:** The article covered integration approaches (server-side, build-time, runtime via iframes, runtime via JavaScript), cross-cutting concerns (styling, communication, testing), and real-world tradeoffs with working code examples.

3. **Principle articulation:** The article crystallized core principles that remain relevant:
   - "Be technology agnostic" -- teams choose their own frameworks
   - "Isolate team code" -- no shared runtime state, no shared variables
   - "Establish team prefixes" -- CSS class prefixes, event naming conventions
   - "Favor native browser features over custom APIs"
   - "Build a resilient site" -- each micro frontend should function independently

4. **Organizational framing:** The article explicitly connected micro frontends to Conway's Law, arguing that the architecture enables organizational autonomy rather than being purely a technical decision.

The article has been cited in hundreds of conference talks and technical documents and remains the starting point for most teams evaluating micro frontends.

### 1.6 Module Federation Changes the Game (2020)

Webpack 5's Module Federation, authored by Zack Jackson, solved the loading problem that Single-SPA left open. Rather than requiring a separate mechanism to resolve and load remote code, Module Federation embedded this capability directly in the build tool. This was a watershed moment -- see [Section 3](#3-the-module-federation-era-2020-2024) for full analysis.

### 1.7 The Standards-Based Shift (2023-2026)

By 2023, the industry began questioning whether build-tool-specific solutions were the right foundation. Import maps reached universal browser support. Web Components matured. Edge computing platforms offered new composition primitives. The result: a gradual shift toward platform-native solutions -- see [Section 4](#4-the-native-federation--import-maps-era-2024-2026).

### 1.8 What the Industry Has Learned

After a decade of experimentation, several hard-won lessons have emerged:

1. **Micro frontends solve organizational problems, not technical ones.** If a single team owns the entire frontend, the coordination overhead of micro frontends outweighs any benefit. The pattern shines when 3+ teams need to ship independently on the same domain.

2. **Start simple, adopt incrementally.** Teams that begin with Module Federation or Single-SPA on day one often regret it. The recommended path: monolith first, extract when the organizational pain justifies the architectural complexity.

3. **Shared dependencies are the hardest problem.** Not routing, not communication, not deployment -- dependency version management across independently deployed artifacts is where most teams spend their debugging time.

4. **Performance requires active management.** Naive micro frontend architectures easily produce 2-5x larger bundle sizes through dependency duplication. Shared dependency negotiation, tree-shaking, and lazy loading are not optional.

5. **"Micro frontend anarchy" is a real anti-pattern.** ThoughtWorks itself added "micro frontend anarchy" to the Technology Radar's Hold ring, warning against teams using the architecture as an excuse to adopt different frameworks, state management libraries, and design systems with no coordination.

---

## 2. Architecture Patterns Deep Dive

### 2.1 Build-Time Integration (npm Packages, Monorepo)

**How it works:**

Each micro frontend is published as an npm package (or workspace package in a monorepo). A host application declares them as dependencies in `package.json` and imports them at build time. The final artifact is a single, unified bundle.

**Flow:**

```
Team A develops MFE-A --> publishes @company/mfe-a@2.3.1 to npm registry
Team B develops MFE-B --> publishes @company/mfe-b@1.7.0 to npm registry
                              |
                              v
Host application: package.json
  "@company/mfe-a": "^2.3.0"
  "@company/mfe-b": "^1.7.0"
                              |
                              v
         npm install --> webpack/vite build --> single bundle.js
                              |
                              v
                    Deploy single artifact to CDN
```

**Strengths:**
- Simplest mental model -- familiar npm workflows, no runtime orchestration
- Best performance -- single bundle, tree-shaking across boundaries, no duplicate dependencies
- Compile-time type checking across micro frontends (TypeScript project references)
- Works with any framework, any build tool
- Monorepo tooling (Nx, Turborepo, Lerna) provides task orchestration, caching, and affected-detection

**Weaknesses:**
- **No independent deployment.** Changing MFE-A requires rebuilding and redeploying the host application. This is the fundamental tradeoff -- you gain performance but lose deployment independence.
- **Lockstep releases.** All teams must coordinate on a release cadence. A blocking bug in one micro frontend blocks all others.
- **Version conflicts.** Diamond dependency problems are common. If MFE-A depends on lodash@4 and MFE-B depends on lodash@3, the host must resolve this at install time.
- **Build times scale with team count.** As the monorepo grows, CI times increase. Nx and Turborepo mitigate this with caching but cannot eliminate it.

**When to use:**
- Small to medium teams (2-5) with frequent cross-cutting changes
- Performance-critical applications where bundle size must be minimized
- Organizations already using a monorepo with shared tooling
- When deployment independence is not a requirement (e.g., a single release train is acceptable)

---

### 2.2 Server-Side Composition (SSI, ESI, Tailor.js, Podium)

**How it works:**

A server (or edge/CDN layer) receives the browser request, determines which page regions map to which micro frontend services, fetches HTML fragments from each, stitches them into a single response document, and returns it to the browser. Each micro frontend service is an independent HTTP endpoint that returns an HTML fragment.

**Flow:**

```
Browser request: GET /product/42
         |
         v
Layout Server (Tailor/Podium/Nginx+SSI)
  |--- Fetch /header-service/render          --> <header>...</header>
  |--- Fetch /product-service/render/42      --> <main>...</main>
  |--- Fetch /recommendations-service/render --> <aside>...</aside>
  |--- Fetch /footer-service/render          --> <footer>...</footer>
         |
         v
Compose into single HTML document
         |
         v
Stream to browser as single HTTP response
```

**Technology-specific details:**

| Technology | Composition Layer | Streaming | Error Handling | Complexity |
|-----------|------------------|-----------|----------------|-----------|
| SSI (Nginx/Apache) | Web server | No | Basic (fallback HTML) | Low |
| ESI (Varnish/Akamai) | CDN/reverse proxy | No | Timeouts + fallback | Medium |
| Tailor.js | Node.js service | Yes (BigPipe-style) | Per-fragment timeouts | Medium |
| Podium | Node.js framework | Yes | Structured fallbacks | Higher |

**Strengths:**
- Excellent SEO -- the browser receives a complete HTML document
- Good Time to First Byte -- streaming composition (Tailor/Podium) sends content as it arrives
- Technology agnostic -- each fragment is just HTML over HTTP
- Independent deployment -- update a fragment service without touching the layout server
- Works without JavaScript -- graceful degradation is built-in

**Weaknesses:**
- Client-side interactivity requires additional JavaScript loading per fragment ("hydration islands")
- Fragment-to-fragment communication on the client side is not solved by the composition layer
- Layout changes require updating the layout server
- Additional network hops (layout server to fragment services) add latency
- Debugging is harder -- errors may originate in any fragment service

**When to use:**
- Content-heavy sites (e-commerce, news, publishing) where SEO is critical
- Applications where server-side rendering is a hard requirement
- Organizations already running microservices with HTTP-based fragment endpoints
- When you need progressive enhancement (works without JS)

---

### 2.3 Run-Time Integration via iframes

**How it works:**

Each micro frontend is a complete, independently deployed web application. The host page embeds them using `<iframe>` elements with the `src` attribute pointing to the micro frontend's URL. Communication between the host and iframed applications uses the `window.postMessage()` API.

**Flow:**

```
Host page (https://app.example.com)
  |
  +-- <iframe src="https://team-a.example.com/widget" />
  |     |-- Complete HTML document
  |     |-- Own CSS, own JS runtime
  |     |-- Own Content-Security-Policy
  |     \-- Communicates via postMessage
  |
  +-- <iframe src="https://team-b.example.com/dashboard" />
  |     |-- Complete HTML document
  |     \-- ...
  |
  \-- Host JavaScript
        |-- Listens for postMessage events
        |-- Coordinates iframe sizing (ResizeObserver + postMessage)
        \-- Manages shared authentication (token passing via postMessage)
```

**Strengths:**
- **Strongest isolation.** Each iframe is a separate browsing context with its own DOM, CSS scope, JavaScript global, and CSP. A crash in one iframe cannot affect the host or other iframes.
- **Zero dependency conflicts.** Each iframe loads its own versions of everything. React 16 in one, Vue 3 in another -- no negotiation needed.
- **Security boundaries.** The `sandbox` attribute restricts capabilities (scripts, forms, popups, navigation). Cross-origin iframes enforce the Same-Origin Policy, preventing access to the host's DOM.
- **Legacy integration.** An iframe can wrap a 15-year-old jQuery application alongside a modern React micro frontend without any adaptation.
- **Independent CSP.** Each iframed application can enforce its own Content-Security-Policy, and a compromised micro frontend cannot read cookies or storage from the host origin.

**Weaknesses:**
- **Performance.** Each iframe initiates a full document load: DNS, TCP, TLS, HTML fetch, CSS parse, JS execute. For N iframes, the browser performs N complete page loads.
- **Communication friction.** `postMessage` is asynchronous, untyped, and requires manual serialization. Complex interactions (shared state, two-way data binding) become cumbersome.
- **Layout challenges.** iframes do not participate in the host's layout flow. Auto-sizing an iframe to its content requires JavaScript coordination (the iframe measures its content height and postMessages it to the host).
- **No URL integration.** Navigation within an iframe is invisible to the host's address bar. Users cannot bookmark or share deep links into iframed content without explicit coordination.
- **SEO invisibility.** Content inside iframes is generally not indexed by search engines, making it unsuitable for SEO-sensitive content.
- **Accessibility gaps.** Screen readers may struggle with iframe boundaries. Focus management across iframe boundaries requires careful implementation.

**When to use:**
- Embedding untrusted or third-party content (payment forms, chat widgets)
- Wrapping legacy applications that cannot be modified or rebuilt
- Environments requiring strict security isolation between tenants
- When the overhead of full-page loads per iframe is acceptable (few iframes, not performance-critical)

---

### 2.4 Run-Time Integration via JavaScript (Single-SPA, Module Federation, Import Maps)

**How it works:**

The host application loads micro frontend JavaScript bundles at runtime and integrates them into the same DOM. The micro frontends share the browser's JavaScript context (same `window`, same DOM tree), and an orchestration layer manages their lifecycle. Three primary sub-patterns exist:

#### 2.4.1 Single-SPA Orchestration

```javascript
// Root config (host application)
import { registerApplication, start } from 'single-spa';

registerApplication({
  name: '@company/navbar',
  app: () => System.import('@company/navbar'),
  activeWhen: '/',
});

registerApplication({
  name: '@company/products',
  app: () => System.import('@company/products'),
  activeWhen: '/products',
});

start();
```

Each micro frontend exports lifecycle functions:

```javascript
// @company/products micro frontend
export function bootstrap(props) { /* one-time init */ }
export function mount(props) { /* render to DOM */ }
export function unmount(props) { /* clean up DOM */ }
```

Single-SPA handles route matching and lifecycle management. Module loading is delegated to SystemJS, import maps, or Module Federation.

#### 2.4.2 Webpack Module Federation

See [Section 3](#3-the-module-federation-era-2020-2024) for comprehensive coverage.

#### 2.4.3 Import Maps

See [Section 4](#4-the-native-federation--import-maps-era-2024-2026) for comprehensive coverage.

**Strengths:**
- **True independent deployment.** Each micro frontend is a separately deployed JavaScript bundle. Updating one does not require rebuilding or redeploying others.
- **Shared DOM.** Micro frontends render into the same document, enabling shared styling, unified accessibility tree, and natural layout flow.
- **Shared dependencies.** Libraries like React can be loaded once and shared across all micro frontends (with version negotiation in Module Federation, or scoped resolution in import maps).
- **Good developer experience.** Local development can run a single micro frontend against mocked or remote peers.

**Weaknesses:**
- **No isolation.** A global CSS rule, a global variable, or an unhandled exception in one micro frontend affects all others. Isolation must be enforced through conventions (CSS prefixes, scoped styles) rather than platform boundaries.
- **Dependency hell.** Multiple versions of the same library in the same page cause bundle bloat and potential runtime conflicts. Version negotiation (Module Federation) or scoped resolution (import maps) mitigate but do not eliminate this.
- **Orchestration complexity.** Someone must manage the loading, error handling, and lifecycle of multiple remote JavaScript bundles -- this is non-trivial infrastructure.
- **Framework coupling (Module Federation).** Module Federation is webpack-specific (or Rspack). Moving to Vite or Turbopack requires re-architecting the federation layer.

**When to use:**
- Teams that need independent deployment with a cohesive user experience
- SPAs where server-side composition is impractical
- Organizations willing to invest in orchestration infrastructure
- When shared dependencies (React, design system) must be deduplicated

---

### 2.5 Web Components (Custom Elements as Boundaries)

**How it works:**

Each micro frontend exposes one or more [Custom Elements](https://developer.mozilla.org/en-US/docs/Web/API/Web_components). The host application uses these elements declaratively in HTML. Shadow DOM provides style encapsulation. The Custom Elements API provides lifecycle callbacks. Communication happens through DOM attributes, properties, and CustomEvents.

**Flow:**

```html
<!-- Host application -->
<script type="module" src="https://team-a.example.com/product-card.js"></script>
<script type="module" src="https://team-b.example.com/shopping-cart.js"></script>

<product-card product-id="42"></product-card>
<shopping-cart></shopping-cart>
```

Each micro frontend defines a Custom Element:

```javascript
// team-a/product-card.js
class ProductCard extends HTMLElement {
  static get observedAttributes() { return ['product-id']; }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() { this.render(); }
  attributeChangedCallback(name, oldVal, newVal) { this.render(); }

  render() {
    const id = this.getAttribute('product-id');
    this.shadowRoot.innerHTML = `
      <style>/* Scoped styles, cannot leak */</style>
      <div class="card">...</div>
    `;
  }
}
customElements.define('product-card', ProductCard);
```

**Strengths:**
- **Framework agnostic by design.** Custom Elements are a browser standard. A React team, a Vue team, and a vanilla JS team all produce the same interface: an HTML tag with attributes, properties, and events.
- **Style encapsulation via Shadow DOM.** Styles inside a Shadow Root do not leak out, and host styles do not bleed in (with the exception of CSS custom properties, which deliberately pierce the shadow boundary for theming).
- **Standard lifecycle.** `connectedCallback`, `disconnectedCallback`, `attributeChangedCallback` provide a universal lifecycle without orchestration frameworks.
- **Declarative integration.** The host application uses standard HTML syntax. No JavaScript API calls to mount/unmount.
- **Declarative Shadow DOM (2024+).** Server-side rendering of shadow roots is now possible via `<template shadowrootmode="open">`, enabling SSR-compatible Web Component micro frontends.

**Weaknesses:**
- **Shadow DOM complexity.** Form participation (e.g., getting a Custom Element's value submitted with a form), focus management, and accessibility across shadow boundaries require careful implementation. The `ElementInternals` API (now widely supported) addresses form participation but adds complexity.
- **Attribute serialization.** HTML attributes are strings. Passing complex objects requires JSON serialization in attributes or using JavaScript properties, breaking the purely declarative model.
- **No built-in routing.** Web Components do not provide routing or lifecycle orchestration. Teams must add this separately (e.g., with a router component or Single-SPA).
- **Ecosystem maturity.** While standards are solid, tooling for building large-scale applications with Web Components (testing, dev tools, SSR) lags behind React/Vue/Angular ecosystems.
- **CSS custom property leakage is intentional but surprising.** Host-level `--color-primary: red` applies inside shadow roots, which is by design for theming but can cause unintended style coupling.

**When to use:**
- Polyglot environments where teams use different frameworks
- Design system distribution (publish a component library that works everywhere)
- When long-term framework independence is a priority
- PyBend-style architectures where the framework owns the component model (PyBend's `NTTElement` extends `HTMLElement` and uses this exact pattern)

---

### 2.6 Edge-Side Composition (Cloudflare Workers, Lambda@Edge)

**How it works:**

Composition happens at the CDN edge -- geographically close to the user, before the response reaches the browser. Edge functions (Cloudflare Workers, AWS Lambda@Edge, Deno Deploy) act as reverse proxies that fetch HTML from different micro frontend services, rewrite paths, inject shared assets, and return a composed response.

**Flow (Cloudflare Vertical Microfrontends, 2026):**

```
Browser: GET https://app.example.com/docs/installation
                    |
                    v
        Cloudflare Edge (nearest PoP)
        Router Worker receives request
                    |
    Route matching: /docs/* --> DOCS service binding
                    |
                    v
        worker_docs (independent Cloudflare Worker)
        Framework: Astro, Next.js, SvelteKit, etc.
        Returns HTML for /installation
                    |
                    v
        Router Worker post-processing:
        1. HTMLRewriter: rewrite asset paths (/logo.png --> /docs/logo.png)
        2. Inject View Transitions CSS for smooth navigation
        3. Inject Speculation Rules for preloading adjacent routes
                    |
                    v
        Browser receives composed, enhanced HTML
```

**Cloudflare's Router Worker configuration:**

```json
{
  "smoothTransitions": true,
  "routes": [
    { "binding": "HOME", "path": "/", "preload": true },
    { "binding": "DOCS", "path": "/docs", "preload": true },
    { "binding": "DASH", "path": "/dashboard" }
  ]
}
```

Service bindings connect Workers without public HTTP overhead:

```json
{
  "name": "router",
  "services": [
    { "binding": "HOME", "service": "worker_marketing" },
    { "binding": "DOCS", "service": "worker_docs" },
    { "binding": "DASH", "service": "worker_dash" }
  ]
}
```

**Performance characteristics:**

| Platform | Cold Start | Global PoPs | Runtime |
|----------|-----------|-------------|---------|
| Cloudflare Workers | 100-500 microseconds | 300+ | V8 isolates |
| AWS Lambda@Edge | 100-1000+ ms | 40+ (CloudFront) | Node.js/Python |
| AWS CloudFront Functions | Sub-millisecond | 400+ | JavaScript (limited) |
| Deno Deploy | <100ms | 35+ | Deno/V8 isolates |

**Strengths:**
- **Lowest latency composition.** Edge PoPs are geographically close to users. Composition adds microseconds, not milliseconds.
- **No composition server to manage.** The CDN edge IS the composition layer. No additional infrastructure to provision, scale, or monitor.
- **Team autonomy.** Each team deploys their own Worker with their own framework. The Router Worker's configuration is the only coordination point.
- **Progressive enhancement built-in.** View Transitions API provides smooth cross-microfrontend navigation. Speculation Rules API prefetches adjacent routes. Both are injected automatically by the Router Worker's HTMLRewriter.
- **Vertical ownership.** Unlike horizontal composition (where fragments compose a single page), vertical microfrontends assign entire URL paths to teams. Team A owns `/docs/*`, Team B owns `/dashboard/*`. This is a cleaner ownership model for many organizations.

**Weaknesses:**
- **Platform lock-in.** Cloudflare Workers, Lambda@Edge, and Deno Deploy have different APIs, limits, and pricing. Migration between platforms is non-trivial.
- **Limited runtime.** Edge functions have CPU time limits (e.g., 10-50ms on Cloudflare's free plan), memory limits, and restricted API access (no filesystem, limited network).
- **Vertical-only composition (Cloudflare VMFE).** The Cloudflare template composes at the route level, not the component level. Two teams cannot own different parts of the same page without reverting to client-side composition.
- **Debugging complexity.** Distributed edge execution is harder to trace than a single server. Logs are distributed across hundreds of PoPs.
- **Cold start variability (Lambda@Edge).** AWS Lambda@Edge cold starts can exceed 1 second, introducing unpredictable latency spikes.

**When to use:**
- Applications where TTFB is critical and composition latency must be minimized
- Organizations already on a CDN platform with edge compute capabilities
- Vertical microfrontend architectures where teams own entire route subtrees
- When SEO requirements demand server-rendered HTML but server-side infrastructure is undesirable

---

## 3. The Module Federation Era (2020-2024)

### 3.1 Webpack 5 Module Federation Explained

Module Federation, introduced in Webpack 5 (October 2020) by Zack Jackson, is a webpack plugin that allows a JavaScript application to dynamically load code from another separately built and deployed application at runtime, while sharing dependencies between them.

**Core concepts:**

| Term | Definition |
|------|-----------|
| **Host** | The application that loads remote modules at runtime |
| **Remote** | The application that exposes modules for consumption by hosts |
| **Exposed module** | A specific module (component, utility, etc.) that a remote makes available |
| **Shared module** | A dependency (React, lodash, etc.) that multiple applications agree to load once and share |
| **Container** | The webpack runtime that manages loading and sharing for a given application |
| **remoteEntry.js** | The manifest file that describes what a remote exposes and what it needs |

Every application can be both a host and a remote simultaneously -- this is "omnidirectional" federation.

**Configuration example:**

```javascript
// Remote: team-a's webpack.config.js
const { ModuleFederationPlugin } = require('webpack').container;

module.exports = {
  plugins: [
    new ModuleFederationPlugin({
      name: 'teamA',
      filename: 'remoteEntry.js',
      exposes: {
        './ProductCard': './src/components/ProductCard',
        './utils': './src/utils/index',
      },
      shared: {
        react: { singleton: true, requiredVersion: '^18.0.0' },
        'react-dom': { singleton: true, requiredVersion: '^18.0.0' },
        lodash: { requiredVersion: '^4.17.0' },
      },
    }),
  ],
};
```

```javascript
// Host: shell application's webpack.config.js
module.exports = {
  plugins: [
    new ModuleFederationPlugin({
      name: 'shell',
      remotes: {
        teamA: 'teamA@https://team-a.example.com/remoteEntry.js',
      },
      shared: {
        react: { singleton: true, requiredVersion: '^18.0.0' },
        'react-dom': { singleton: true, requiredVersion: '^18.0.0' },
        lodash: { requiredVersion: '^4.17.0' },
      },
    }),
  ],
};
```

```javascript
// Host: consuming a remote module
const ProductCard = React.lazy(() => import('teamA/ProductCard'));

function App() {
  return (
    <React.Suspense fallback={<div>Loading...</div>}>
      <ProductCard id={42} />
    </React.Suspense>
  );
}
```

### 3.2 How Shared Dependencies Work

Module Federation's shared dependency system is its most sophisticated -- and most misunderstood -- feature. The mechanism works through a multi-step negotiation process:

**Step 1: Declaration.** Each federated application declares shared modules with version requirements:

```javascript
shared: {
  react: {
    singleton: true,          // Only one instance allowed
    requiredVersion: '^18.2.0', // semver range this app needs
    eager: false,             // Load asynchronously (default)
    strictVersion: false,     // Warn (not error) on mismatch
  }
}
```

**Step 2: Initialization.** When the host loads, it initializes a shared scope. Each remote's `remoteEntry.js` is loaded, and the container runtime registers what it can provide and what it needs.

**Step 3: Negotiation.** The webpack runtime compares all registered versions and requirements:

- Among all federated builds, the **highest available version** that satisfies all `requiredVersion` constraints is selected.
- If `singleton: true`, only one instance loads. If the highest version does not satisfy a consumer's `requiredVersion`, the behavior depends on `strictVersion`:
  - `strictVersion: false` (default): A console warning is emitted, and the singleton is used anyway.
  - `strictVersion: true`: A runtime error is thrown.

**Step 4: Loading.** The selected version is loaded once. All consumers receive the same module reference.

### 3.3 Version Negotiation and Singleton Enforcement

The version negotiation algorithm follows these rules:

1. Collect all provided versions from all containers
2. Collect all required version ranges from all consumers
3. Select the highest version that satisfies all ranges (semver comparison)
4. If no single version satisfies all ranges:
   - **Non-singleton:** Load multiple versions (one per incompatible range)
   - **Singleton:** Load the highest version, warn or error per `strictVersion`

**Common pitfalls:**

- **The "eager" trap.** Setting `eager: true` includes the shared module in the initial bundle, preventing async negotiation. This means the first application to load wins, regardless of version. The webpack documentation recommends keeping `eager: false` and using an async boundary (dynamic import) at the application entry point.

- **The "packageName" ambiguity.** The `packageName` option determines which `package.json` version to read for `requiredVersion` auto-inference. If micro frontends use different package managers or monorepo layouts, the inferred version may be wrong.

- **Transitive dependency hell.** If MFE-A shares `react@18.2.0` and MFE-B shares a library that internally depends on `react@17.0.0`, the nested dependency is not automatically included in version negotiation. Teams must explicitly declare all dependencies that need sharing.

### 3.4 Module Federation v2 (Enhanced API, Rspack Support)

Module Federation 2.0 (released 2024, via `@module-federation/enhanced`) introduced significant architectural changes:

**Runtime SDK extraction:**

The runtime capabilities that were embedded in Webpack have been extracted into a standalone SDK. This allows:
- Dynamic registration and loading of remotes without build-tool involvement
- Runtime-only federation (no webpack required for the host)
- Cross-platform compatibility (works with Rspack, webpack, and potentially other bundlers)

**Key v2 features:**

| Feature | Description |
|---------|-------------|
| **Runtime plugins** | Extensible hook system for customizing load/share behavior |
| **TypeScript type hints** | Automatic generation and synchronization of TypeScript declarations for remote modules |
| **Chrome DevTools** | Dedicated DevTools extension for inspecting federation topology |
| **mf-manifest.json** | Standardized manifest protocol for deployment platform integration |
| **Preloading** | Declarative preload hints for remote entry files |
| **Rspack compatibility** | Shared interfaces between webpack and Rspack implementations |

**Rspack performance gains:**

Rspack (a Rust-based webpack replacement by ByteDance) implements the same Module Federation plugin API. Migration is a configuration change, not a rewrite. Observed improvements:

- 5-10x faster build times for federated applications
- Development cold starts typically under 150ms
- Hot module replacement latency reduced by 3-5x

```javascript
// Rspack configuration (nearly identical to webpack)
const { ModuleFederationPlugin } = require('@module-federation/enhanced/rspack');

module.exports = {
  plugins: [
    new ModuleFederationPlugin({
      name: 'teamA',
      filename: 'remoteEntry.js',
      exposes: { './Widget': './src/Widget' },
      shared: { react: { singleton: true } },
    }),
  ],
};
```

### 3.5 Limitations and Pain Points Teams Discovered

By 2024, organizations running Module Federation in production had accumulated a substantial list of pain points:

1. **Webpack lock-in.** Module Federation is a Webpack/Rspack-specific feature. Teams using Vite, Rollup, esbuild, or Turbopack could not participate. This forced entire organizations onto Webpack, even if individual teams preferred other tools.

2. **Version negotiation failures at scale.** With 10+ federated applications, the combinatorial explosion of shared dependency versions produced hard-to-debug runtime errors. A new deployment of one MFE could break others by changing the negotiated version.

3. **Remote entry availability.** If `remoteEntry.js` for any remote is unreachable (CDN outage, deployment in progress), the host application may crash or show a loading spinner indefinitely. Robust error boundaries and fallback UIs are essential but not provided by default.

4. **Opaque runtime behavior.** When version negotiation selected an unexpected version, or when a shared module loaded twice, debugging required understanding Webpack's internal container runtime -- a module system within a module system. The v2 DevTools extension helps but does not eliminate the complexity.

5. **Testing difficulty.** Unit testing a federated module in isolation (without the federation runtime) requires mocking the entire container API. Integration testing requires running multiple development servers simultaneously.

6. **SSR complexity.** Server-side rendering with Module Federation is technically possible but requires careful coordination of module loading on the server, where the browser's async loading model does not apply.

7. **Security model.** Module Federation's `remoteEntry.js` is loaded as a script tag. There is no built-in integrity verification (no SRI hashes), no sandboxing, and no permission model. A compromised remote entry has full access to the host's DOM, cookies, and JavaScript context.

---

## 4. The Native Federation / Import Maps Era (2024-2026)

### 4.1 The Shift Away from Bundler-Specific Solutions

By 2023-2024, a confluence of factors drove the industry toward standards-based alternatives:

- **Bundler fragmentation.** Webpack, Vite, Rollup, esbuild, Turbopack, Rspack, Parcel -- the JavaScript ecosystem could not agree on a single build tool, making bundler-specific federation increasingly untenable.
- **ES Modules everywhere.** All modern browsers support `<script type="module">`, dynamic `import()`, and import maps. The platform now provides what bundlers had to polyfill.
- **Import maps reach universal support.** Chrome 89 (Mar 2021), Edge 89, Firefox 108 (Dec 2022), Safari 16.4 (Mar 2023). By 2024, no polyfill was needed for any major browser.
- **The Mercedes-Benz.io provocation.** Their January 2023 article ["You Might Not Need Module Federation"](https://www.mercedes-benz.io/blog/2023-01-05-you-might-not-need-module-federation-orchestrate-your-microfrontends-at-runtime-with-import-maps) demonstrated a production-grade micro frontend architecture using only import maps, ES modules, and a lightweight resolver server -- no Webpack, no Module Federation.

### 4.2 Import Maps Specification Details

Import maps are a [WICG specification](https://github.com/WICG/import-maps) (now part of the HTML standard) that allow web pages to control the behavior of JavaScript imports. They provide a JSON mapping from module specifiers to URLs, resolved at the browser level.

**Basic structure:**

```html
<script type="importmap">
{
  "imports": {
    "react": "https://esm.sh/react@18.3.1",
    "react-dom": "https://esm.sh/react-dom@18.3.1",
    "@company/header": "https://cdn.example.com/header/v2.1.0/index.js",
    "@company/product-card": "https://cdn.example.com/product-card/v3.0.2/index.js"
  }
}
</script>

<script type="module">
  // These bare specifiers are resolved by the import map
  import React from 'react';
  import { ProductCard } from '@company/product-card';
</script>
```

**Key specification features:**

1. **Bare specifier resolution.** Without import maps, browsers can only resolve URLs (`./module.js`, `https://...`). Import maps add support for "bare" specifiers (`react`, `@company/widget`) -- the same syntax Node.js uses.

2. **Trailing slash for package prefixes.** A trailing slash creates a prefix mapping:
   ```json
   { "imports": { "lodash/": "https://esm.sh/lodash-es@4.17.21/" } }
   ```
   Now `import get from 'lodash/get'` resolves to `https://esm.sh/lodash-es@4.17.21/get`.

3. **Multiple specifiers for versioning.** Different URLs for different package versions allow gradual migration:
   ```json
   {
     "imports": {
       "react": "https://esm.sh/react@18.3.1",
       "react-v17": "https://esm.sh/react@17.0.2"
     }
   }
   ```

### 4.3 Scopes for Version Isolation

The `scopes` feature is the import map equivalent of Module Federation's per-consumer version negotiation. It allows different modules to resolve the same specifier to different URLs based on the importing module's own URL.

```json
{
  "imports": {
    "react": "https://esm.sh/react@18.3.1",
    "lodash": "https://esm.sh/lodash-es@4.17.21"
  },
  "scopes": {
    "https://cdn.example.com/team-a/": {
      "lodash": "https://esm.sh/lodash-es@3.10.1"
    },
    "https://cdn.example.com/team-b/": {
      "lodash": "https://esm.sh/lodash-es@4.17.21"
    }
  }
}
```

**How scopes work:**

When `https://cdn.example.com/team-a/widget.js` imports `lodash`, the browser checks:
1. Does any scope key match the importing module's URL prefix?
2. If yes, use the scope's mapping: `lodash` resolves to `lodash-es@3.10.1`
3. If no scope matches, fall back to the top-level `imports`

This provides per-micro-frontend version isolation **without** any build tool involvement. The browser resolves it natively.

**Comparison with Module Federation:**

| Concern | Module Federation | Import Maps Scopes |
|---------|------------------|-------------------|
| Version isolation | Runtime negotiation in JS | Declarative JSON in HTML |
| Singleton enforcement | `singleton: true` option | Use top-level `imports` (no scope override) |
| Per-consumer versions | Not directly supported | Scope keys match consumer URL prefixes |
| Build tool required | Yes (Webpack/Rspack) | No |
| Configuration location | webpack.config.js (per app) | Single `<script type="importmap">` in host HTML |

### 4.4 The `integrity` Field (Subresource Integrity)

Chrome 127 (July 2024) and Safari 18 (September 2024) added an `integrity` field to import maps, enabling [Subresource Integrity (SRI)](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity) for ES modules. This was driven by Shopify's engineering team.

```json
{
  "imports": {
    "react": "https://esm.sh/react@18.3.1"
  },
  "integrity": {
    "https://esm.sh/react@18.3.1": "sha384-abc123def456..."
  }
}
```

**How it works:**

1. When the browser loads a module whose URL appears in the `integrity` map, it computes the cryptographic hash of the fetched content.
2. If the hash matches the declared integrity value, the module executes normally.
3. If the hash does not match (indicating tampering or CDN corruption), the browser **refuses to execute** the module and fires a network error.

**Significance for micro frontends:**

This is the first platform-native mechanism for verifying the integrity of dynamically loaded ES modules. Before this, Module Federation had no built-in integrity verification -- a compromised CDN serving a tampered `remoteEntry.js` would execute without detection.

### 4.5 The `importmap.lock` Proposal (2026)

[Andrew Nesbitt's January 2026 proposal](https://nesbitt.io/2026/01/19/importmap-lock.html) identifies a critical gap: import maps declare what URLs to load and (with `integrity`) can verify their content, but they lack the **dependency metadata** that lockfiles in other ecosystems provide.

**The problem:**

```
What a lockfile captures          What an import map captures
---------------------------------  --------------------------------
Package identity (name@version)   URL (opaque string)
Dependency graph (A depends on B)  Nothing (flat list of mappings)
Resolution constraints (^18.0.0)  Nothing
Provenance (registry source)      Nothing
```

For compliance frameworks like the EU Cyber Resilience Act, organizations must produce Software Bills of Materials (SBOMs). With bundled applications, tools like `npm audit` can walk `package-lock.json`. With import-map-based architectures loading from CDNs, there is no equivalent metadata.

**Proposed structure:**

```json
{
  "imports": {
    "react": "https://esm.sh/react@18.3.1"
  },
  "integrity": {
    "https://esm.sh/react@18.3.1": "sha384-..."
  },
  "packages": {
    "react@18.3.1": {
      "purl": "pkg:npm/react@18.3.1",
      "from": "^18.0.0",
      "dependencies": ["react-dom@18.3.1"],
      "integrity": "sha384-..."
    }
  }
}
```

**Key design decisions:**

- Uses [Package URL (purl)](https://github.com/package-url/purl-spec) identifiers -- a standardized, ecosystem-agnostic format for identifying packages (`pkg:npm/react@18.3.1`, `pkg:pypi/django@4.2`, etc.)
- Browsers would **ignore** the `packages` block (graceful degradation)
- Tooling (SBOM generators, audit tools, deployment validators) would consume it
- Avoids Node.js-specific concepts (`package.json`, `node_modules`) -- this is a web-native format

**Current status (February 2026):** The proposal is in discussion phase. JSPM and ES Module Shims provide tooling foundations that could generate this format. Browser implementation is not yet proposed -- the initial target is tooling-only adoption.

### 4.6 How Rails importmap-rails Blazed the Trail

[DHH](https://world.hey.com/dhh/modern-web-apps-without-javascript-bundling-or-transpiling-a20f2755) and the Rails team shipped [importmap-rails](https://github.com/rails/importmap-rails) as the **default** JavaScript management approach in Rails 7 (December 2021). This was a deliberate architectural statement: modern web applications do not need transpiling or bundling for JavaScript.

**What importmap-rails does:**

1. Provides a Ruby DSL for declaring JavaScript dependencies:
   ```ruby
   # config/importmap.rb
   pin "react", to: "https://esm.sh/react@18.3.1"
   pin "application", preload: true
   pin_all_from "app/javascript/controllers", under: "controllers"
   ```

2. Generates the `<script type="importmap">` tag with digested URLs (for cache busting)

3. Includes the [ES Module Shims](https://github.com/guybedford/es-module-shims) polyfill for browsers that lack import map support

4. Uses Sprockets for asset fingerprinting -- no Node.js, no npm, no Webpack, no Yarn required

**Why this matters for micro frontends:**

importmap-rails proved at scale that:
- Production applications can run without a JavaScript bundler
- CDN-hosted ESM modules are a viable dependency management strategy
- Import maps can be generated server-side (not just static HTML)
- The "you need Node.js to build JavaScript" assumption is false

This validation gave confidence to teams like Mercedes-Benz.io to build production micro frontend architectures on import maps rather than Module Federation.

### 4.7 The Mercedes-Benz.io Architecture

The [Mercedes-Benz.io approach](https://www.mercedes-benz.io/blog/2023-01-05-you-might-not-need-module-federation-orchestrate-your-microfrontends-at-runtime-with-import-maps) is the most detailed public case study of import-map-based micro frontends. Their architecture consists of:

**1. Import Map Resolver Server (Nest.js)**

A lightweight service that:
- Stores the current import map as a JSON document
- Accepts updates from micro frontend CI/CD pipelines
- Serves the import map to the host application at runtime

Analogous to single-spa's [import-map-deployer](https://github.com/single-spa/import-map-deployer).

**2. Per-Team Build Artifacts**

Each micro frontend team produces three artifacts:
- **ESM bundle** -- production-ready ES module (built with Vite, Webpack, Rollup, or any tool)
- **Manifest** -- JSON mapping non-hashed filenames to hashed versions
- **Static assets** -- images, fonts, etc.

The team's CI/CD pipeline publishes these to an assets server and notifies the Resolver.

**3. Publisher Component**

A CLI or CI step that reads the build manifest, extracts the bundle filename and externalized dependencies, and publishes the mapping to the Import Map Resolver.

**4. Assets Server + CDN**

- A web-enabled storage service (e.g., S3 + CloudFront) hosts JavaScript bundles
- A third-party CDN (e.g., esm.sh, unpkg, jsdelivr) serves framework dependencies as ES modules

**5. Host Application**

The host application:
1. Fetches the import map from the Resolver at runtime
2. Injects it into the DOM as `<script type="importmap">`
3. Loads the application entry point
4. All bare specifier imports (`import { Header } from '@company/header'`) resolve via the import map

**Advantages over Module Federation demonstrated:**
- No Webpack/Rspack requirement -- teams can use any build tool
- Instant rollback -- revert the import map to a previous version (no rebuild needed)
- Instant deployment -- update the import map to point to a new bundle URL
- Standard-based -- import maps are a browser standard, not a library feature

---

## 5. Communication Patterns (Technical Detail)

Micro frontends sharing a page must communicate. The fundamental tension: loose coupling (micro frontends should not know about each other) versus feature requirements (the shopping cart must know when a product is added). The following patterns navigate this tension from loosest to tightest coupling.

### 5.1 Custom Events (`composed: true` for Shadow DOM)

The simplest and most standards-aligned approach: micro frontends dispatch and listen for DOM CustomEvents.

**Publishing an event:**

```javascript
// Product card micro frontend
function addToCart(product) {
  const event = new CustomEvent('cart:item-added', {
    detail: { productId: product.id, name: product.name, price: product.price },
    bubbles: true,
    composed: true,  // CRITICAL: allows event to cross Shadow DOM boundaries
  });
  this.dispatchEvent(event);  // Dispatch from the element, not window
}
```

**Consuming an event:**

```javascript
// Shopping cart micro frontend
connectedCallback() {
  // Listen on window to catch events from anywhere in the DOM
  window.addEventListener('cart:item-added', (e) => {
    this.items.push(e.detail);
    this.render();
  });
}
```

**The `composed: true` detail:**

When a Custom Element uses Shadow DOM, events dispatched inside the shadow root do NOT propagate beyond the shadow boundary by default. Setting `composed: true` allows the event to cross shadow boundaries and bubble up through the light DOM. Without this, events from Shadow DOM-encapsulated micro frontends are invisible to the rest of the page.

Note: Some native events (e.g., `click`, `focus`) are composed by default. CustomEvents are NOT composed by default -- you must explicitly set `composed: true`.

**Strengths:** Zero dependencies, framework-agnostic, browser-native, inspectable in DevTools.

**Weaknesses:** No guaranteed delivery (if the listener is not mounted when the event fires, it misses it). No type safety. Event name collisions require conventions (namespace prefixes like `cart:` or `product:`).

### 5.2 Pub/Sub / Event Bus Implementations

A step up from raw CustomEvents: a centralized message broker that decouples publishers from subscribers and adds features like message buffering, wildcard subscriptions, and type safety.

**Minimal implementation:**

```javascript
class EventBus {
  #handlers = new Map();

  subscribe(event, handler) {
    if (!this.#handlers.has(event)) this.#handlers.set(event, new Set());
    this.#handlers.get(event).add(handler);
    return () => this.#handlers.get(event)?.delete(handler); // unsubscribe
  }

  publish(event, data) {
    this.#handlers.get(event)?.forEach(handler => handler(data));
  }
}

// Shared instance (e.g., on window or via import map)
window.__eventBus = window.__eventBus || new EventBus();
```

**Production-grade libraries:**
- [trutoo/event-bus](https://github.com/trutoo/event-bus) -- typesafe, cross-platform, designed for micro frontends
- [PubSubJS](https://github.com/mroderick/PubSubJS) -- lightweight, framework-agnostic
- Custom implementations using `BroadcastChannel` (see Section 5.6)

**Strengths:** Decoupled communication, supports buffering (late subscribers can receive missed messages), wildcard subscriptions, debuggable (log all events through the bus).

**Weaknesses:** The bus itself is a shared dependency that must be loaded before any micro frontend. If it crashes, all communication stops. Tempting to overuse -- when everything goes through the bus, you end up with a distributed monolith.

### 5.3 Shared State (Redux, Zustand, Signals)

When micro frontends need to **read** the same state (not just react to events), a shared state store becomes necessary.

**Pattern: Shared Zustand store via Module Federation/import maps:**

```javascript
// Shared store (loaded once, shared via federation or import map)
import { createStore } from 'zustand/vanilla';

export const cartStore = createStore((set) => ({
  items: [],
  addItem: (item) => set((state) => ({ items: [...state.items, item] })),
  removeItem: (id) => set((state) => ({
    items: state.items.filter(i => i.id !== id)
  })),
}));
```

```javascript
// React micro frontend consuming shared state
import { useStore } from 'zustand';
import { cartStore } from 'shared-stores/cart';

function CartIcon() {
  const count = useStore(cartStore, (s) => s.items.length);
  return <span class="cart-badge">{count}</span>;
}
```

```javascript
// Vue micro frontend consuming the same store
import { cartStore } from 'shared-stores/cart';

export default {
  setup() {
    const count = ref(cartStore.getState().items.length);
    cartStore.subscribe((state) => { count.value = state.items.length; });
    return { count };
  }
}
```

**Signals (2024-2026 trend):**

The TC39 Signals proposal and implementations like Preact Signals, SolidJS signals, and Angular signals provide reactive primitives that are lighter than Redux/Zustand and framework-agnostic by design:

```javascript
// Shared signal (framework-agnostic)
import { signal, computed } from '@preact/signals-core';

export const cartItems = signal([]);
export const cartTotal = computed(() =>
  cartItems.value.reduce((sum, item) => sum + item.price, 0)
);
```

**Strengths:** Consistent state across micro frontends, reactive updates, familiar patterns.

**Weaknesses:** Tight coupling through shared state shape. The store is a shared dependency with version and API compatibility requirements. Harder to maintain independent deployability -- a store schema change affects all consumers.

### 5.4 URL-Based Communication

The URL (hash, query parameters, pathname) is a natural shared state medium that is visible, bookmarkable, and framework-agnostic.

```javascript
// Micro frontend A: update URL to signal filter change
function onFilterChange(category) {
  const url = new URL(window.location.href);
  url.searchParams.set('category', category);
  history.pushState({}, '', url);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

// Micro frontend B: react to URL changes
window.addEventListener('popstate', () => {
  const category = new URL(window.location.href).searchParams.get('category');
  this.filterByCategory(category);
});
```

**Strengths:** Zero shared dependencies. State survives page refresh. Deep-linkable. Inspectable. Works with any framework.

**Weaknesses:** Limited to serializable, small-size data. URL length limits (2,048 characters in practice). Only suitable for navigation-level state, not fine-grained UI state.

### 5.5 postMessage (for iframe Isolation)

When micro frontends are isolated in iframes or separate origins, `window.postMessage()` is the only available communication channel.

```javascript
// Parent (host) sending to iframe
const iframe = document.querySelector('#team-a-iframe');
iframe.contentWindow.postMessage(
  { type: 'USER_AUTHENTICATED', payload: { userId: 42, token: 'jwt...' } },
  'https://team-a.example.com'  // target origin (NEVER use '*' in production)
);

// Inside iframe (team-a) receiving
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://app.example.com') return; // Verify origin
  if (event.data.type === 'USER_AUTHENTICATED') {
    setAuthToken(event.data.payload.token);
  }
});
```

**Strengths:** Works across origins. Provides security isolation. The only option for iframe-based micro frontends.

**Weaknesses:** Asynchronous and untyped. No request/response pattern (must implement correlation IDs manually). Serialization overhead for large payloads (structured clone algorithm). Origin verification is manual and error-prone.

### 5.6 BroadcastChannel API

The [BroadcastChannel API](https://developer.mozilla.org/en-US/docs/Web/API/Broadcast_Channel_API) provides a simple message bus that works across browsing contexts (tabs, windows, iframes, workers) within the same origin.

```javascript
// Any micro frontend can create a channel
const channel = new BroadcastChannel('app-events');

// Publishing
channel.postMessage({ type: 'THEME_CHANGED', theme: 'dark' });

// Subscribing (in a different micro frontend, tab, or worker)
const channel = new BroadcastChannel('app-events');
channel.onmessage = (event) => {
  if (event.data.type === 'THEME_CHANGED') {
    document.documentElement.setAttribute('data-theme', event.data.theme);
  }
};

// Cleanup
channel.close();
```

**Key differences from postMessage:**

| Feature | postMessage | BroadcastChannel |
|---------|------------|------------------|
| Scope | Point-to-point (specific window) | Broadcast (all contexts on channel) |
| Cross-origin | Yes (with origin checks) | No (same origin only) |
| Target | Must have reference to target window | Any context with the same channel name |
| Tabs/Workers | Requires window reference | Works across tabs, workers, service workers |

**Strengths:** Native API, framework-agnostic, works across tabs and workers, simple pub/sub model.

**Weaknesses:** Same-origin only. No message history/buffering. No guaranteed delivery order across contexts. No acknowledgment mechanism.

### 5.7 Actor Model (Relevant to PyBend's Matrix)

The Actor model treats each component as an independent "actor" that:
- Has private state that cannot be directly accessed
- Communicates exclusively via asynchronous message passing
- Processes one message at a time (no concurrency within an actor)
- Can create other actors and send messages to known addresses

**PyBend's Matrix implementation:**

PyBend's `Matrix.js` implements an actor-based message bus for the frontend. Components extend `Actor` and communicate through the Matrix rather than through direct references or shared state. This model maps naturally to micro frontends because:

1. **No shared mutable state.** Each actor (micro frontend) owns its state. Other actors cannot reach in and modify it.
2. **Location transparency.** An actor sends a message to an address, not a specific object. The Matrix routes it. This decouples the sender from the receiver's implementation, framework, or deployment location.
3. **Inspectable.** All messages flow through the Matrix, creating a natural audit log.
4. **Fault isolation.** An actor that crashes does not corrupt other actors' state.

**Implementation sketch (simplified from PyBend's Matrix):**

```javascript
class Matrix {
  #actors = new Map();

  register(address, actor) {
    this.#actors.set(address, actor);
  }

  send(to, message) {
    const actor = this.#actors.get(to);
    if (actor) actor.receive(message);
    else console.warn(`No actor at address: ${to}`);
  }

  ask(to, message) {
    return new Promise((resolve) => {
      const replyAddress = `reply-${crypto.randomUUID()}`;
      this.register(replyAddress, { receive: (msg) => {
        this.#actors.delete(replyAddress);
        resolve(msg);
      }});
      this.send(to, { ...message, replyTo: replyAddress });
    });
  }
}
```

**Strengths:** Strongest decoupling of all communication patterns. Natural fit for distributed systems. Enables request/response via `ask()` (unlike fire-and-forget events). Dead letter handling for undelivered messages.

**Weaknesses:** Higher conceptual overhead. Requires all participants to adopt the actor model. Debugging message flows requires tooling (message tracing). Not a browser standard -- requires a custom or library implementation.

---

## 6. Testing Strategies for MFEs

### 6.1 Unit Testing Individual MFEs

Each micro frontend should be testable in complete isolation, without the host application, other micro frontends, or the federation runtime.

**Principles:**
- Mock external dependencies (shared stores, event buses, remote modules)
- Test the component's public API: attributes/props in, rendered DOM + events out
- Use the same test runner and assertions as any component library (Jest, Vitest, Playwright Component Testing)

**Example (Web Component MFE with Vitest):**

```javascript
import { describe, it, expect, vi } from 'vitest';
import '../src/product-card.js';  // Registers the custom element

describe('product-card', () => {
  it('renders product name from attribute', async () => {
    document.body.innerHTML = '<product-card product-id="42"></product-card>';
    const el = document.querySelector('product-card');
    // Wait for async rendering
    await el.updateComplete;
    expect(el.shadowRoot.querySelector('.name').textContent).toBe('Widget');
  });

  it('dispatches cart:item-added on add-to-cart click', async () => {
    const handler = vi.fn();
    window.addEventListener('cart:item-added', handler);
    document.body.innerHTML = '<product-card product-id="42"></product-card>';
    const el = document.querySelector('product-card');
    await el.updateComplete;
    el.shadowRoot.querySelector('.add-to-cart').click();
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ detail: { productId: '42' } })
    );
  });
});
```

**Key challenge: Mocking federation.**

When a micro frontend uses `import('remote/Component')`, the test environment must either:
1. Provide a mock for the remote module (e.g., via Vitest's `vi.mock()`)
2. Run a local dev server for the remote (slow, fragile)
3. Use a federation-aware test harness (e.g., `@module-federation/testing`)

### 6.2 Contract Testing Between MFEs

Contract testing verifies that the **interfaces** between micro frontends remain compatible, without requiring them to run together.

**What contracts cover:**
- Event names and payload shapes (Custom Events, event bus messages)
- Shared state store shape and action signatures
- URL parameter conventions
- Attribute/property APIs of Web Component micro frontends
- HTTP API contracts (if MFEs communicate via backend APIs)

**Pact for micro frontends:**

[Pact](https://docs.pact.io/) is the leading consumer-driven contract testing framework. While traditionally used for backend API contracts, it applies to MFE interfaces:

```javascript
// Consumer test (shopping cart MFE)
describe('Product Card Contract', () => {
  it('dispatches cart:item-added with expected payload', () => {
    // Define the contract
    const expectedEvent = {
      type: 'cart:item-added',
      detail: {
        productId: like('string'),      // Any string
        name: like('Widget'),            // Any string
        price: like(29.99),              // Any number
      }
    };

    // Pact records this as a contract
    return provider.addInteraction({
      state: 'product 42 exists',
      uponReceiving: 'an add-to-cart event',
      withContent: expectedEvent,
    });
  });
});
```

**Custom contract validation (lightweight alternative):**

Many teams find Pact's HTTP-focused model awkward for frontend event contracts. A simpler approach uses JSON Schema or TypeScript types as contracts:

```typescript
// contracts/cart-events.ts (shared package)
export interface CartItemAddedEvent {
  type: 'cart:item-added';
  detail: {
    productId: string;
    name: string;
    price: number;
    quantity?: number;
  };
}

// Each MFE imports and validates against this contract
```

**Strengths:** Catches breaking changes before they reach integration testing. Enables independent deployment with confidence. Fast (no servers needed).

**Weaknesses:** Only tests interfaces, not behavior. Requires discipline to keep contracts updated. Pact's infrastructure (Pact Broker) adds operational overhead.

### 6.3 Integration Testing of Composed Applications

Integration tests verify that micro frontends work correctly when composed together, but without end-to-end browser automation.

**Approaches:**

1. **Module-level integration:** Import multiple MFE modules into a single test and verify they communicate correctly through the shared event bus or state store.

2. **Dev server composition:** Run all MFE dev servers simultaneously, use the host application to compose them, and run tests against the composed page with a headless browser.

3. **Snapshot composition:** Record the outputs of each MFE (HTML fragments, event sequences) and verify they compose correctly through static analysis.

**Practical setup with Playwright:**

```javascript
// integration/product-to-cart.spec.js
import { test, expect } from '@playwright/test';

test('adding product to cart updates cart count', async ({ page }) => {
  // Start composed application (all MFEs running)
  await page.goto('http://localhost:3000/products');

  // Interact with product card MFE
  await page.click('[data-testid="add-to-cart-42"]');

  // Verify cart MFE updated
  await expect(page.locator('.cart-badge')).toHaveText('1');

  // Verify via event trace (if event bus exposes debug API)
  const events = await page.evaluate(() => window.__eventBus.getLog());
  expect(events).toContainEqual(
    expect.objectContaining({ type: 'cart:item-added', detail: { productId: '42' } })
  );
});
```

### 6.4 E2E Testing Across MFE Boundaries

End-to-end tests exercise the full system as a user would: browser, network, backend, database.

**Challenges specific to micro frontends:**

1. **Environment setup.** N micro frontends means N services to start, each with its own dependencies. Docker Compose or a similar orchestration tool is essential.

2. **Test data isolation.** Each MFE may have its own backend/database. Test data must be seeded consistently across all backends.

3. **Flakiness from independent deployments.** If E2E tests run against production-like environments where MFEs deploy independently, a deployment during a test run causes failures. Solution: pin MFE versions for E2E test environments.

4. **Slow execution.** E2E tests across MFE boundaries are inherently slower. Budget carefully -- focus E2E tests on critical cross-MFE user journeys, not exhaustive coverage.

**Recommended E2E test structure:**

```
E2E Tests
  |
  +-- Critical Paths (cross-MFE, always run)
  |     +-- User registers -> browses products -> adds to cart -> checks out
  |     +-- Admin creates product -> user sees it in listing
  |
  +-- MFE-specific journeys (run per-MFE, faster feedback)
  |     +-- Product search, filter, sort (product MFE only)
  |     +-- Cart manipulation (cart MFE only)
  |
  \-- Visual regression (screenshot comparison)
        +-- Composed pages at key breakpoints
```

### 6.5 Consumer-Driven Contracts (Pact Workflow)

The full Pact workflow for micro frontends:

```
1. Consumer (Cart MFE) writes test specifying expected events/APIs
         |
         v
2. Pact generates .pact file (contract artifact)
         |
         v
3. Contract published to Pact Broker (shared registry)
         |
         v
4. Provider (Product MFE) CI pipeline pulls contract from Broker
         |
         v
5. Provider verifies it satisfies the contract
         |
         v
6. Pass: Provider can deploy safely
   Fail: Provider must fix breaking change before deploying
```

**can-i-deploy check:**

Pact Broker provides a `can-i-deploy` API that checks whether all contracts are satisfied between the versions currently deployed and the version about to deploy. This is the key enabler for independent deployment with confidence:

```bash
# In Product MFE CI pipeline, before deployment
pact-broker can-i-deploy \
  --pacticipant "product-mfe" \
  --version $(git rev-parse HEAD) \
  --to-environment production
```

---

## 7. DevOps and CI/CD for MFEs

### 7.1 Independent Deployment Pipelines

The primary value proposition of micro frontends is independent deployment. Each micro frontend has its own CI/CD pipeline:

```
Team A pushes to team-a/product-card repo
         |
         v
CI Pipeline (GitHub Actions / GitLab CI / Jenkins)
  1. Install dependencies
  2. Lint + type check
  3. Unit tests
  4. Build ESM bundle
  5. Contract verification (Pact)
  6. Upload bundle to CDN/assets server
  7. Update import map / Module Federation manifest
  8. Smoke test against staging
  9. Deploy to production (update resolver / CDN)
         |
         v
Production: new bundle is live within minutes
No other team's pipeline touched.
```

**Key infrastructure components:**

| Component | Purpose | Examples |
|-----------|---------|---------|
| Asset storage | Host JavaScript bundles | S3 + CloudFront, GCS, Azure Blob |
| Import map resolver | Track which bundle versions are active | Custom service, import-map-deployer |
| CDN | Serve bundles with edge caching | Cloudflare, Fastly, CloudFront |
| Feature flags | Control which MFE version is active | LaunchDarkly, Unleash, Flagsmith |

### 7.2 Versioning Strategies

**Semantic versioning (semver):**

Each micro frontend follows semver. The import map or Module Federation manifest references specific versions:

```json
{
  "imports": {
    "@company/product-card": "https://cdn.example.com/product-card/v3.2.1/index.js"
  }
}
```

**Advantages:** Clear communication of breaking changes. Consumers can pin to compatible ranges.
**Disadvantages:** Requires discipline. "Is this a patch or a minor?" debates consume time.

**Content-hash versioning:**

Bundle filenames include a content hash. The import map resolver tracks which hash is "current":

```json
{
  "imports": {
    "@company/product-card": "https://cdn.example.com/product-card/index.a1b2c3d4.js"
  }
}
```

**Advantages:** Immutable URLs enable aggressive caching. No version semantics to debate -- every change is a new hash.
**Disadvantages:** Rollback requires knowing the previous hash. No semantic signal about change magnitude.

**Hybrid approach (recommended):**

Use semver for the package version (in the resolver's metadata) and content hashes for the URL (for caching). The resolver maps `product-card@3.2.1` to `product-card/index.a1b2c3d4.js`.

### 7.3 Canary Releases and A/B Testing

Canary releases deploy a new micro frontend version to a subset of users before full rollout.

**Implementation patterns:**

**1. Import map branching:**

The import map resolver serves different import maps based on user attributes:

```
User in canary group?
  Yes --> Import map with product-card@3.3.0-canary
  No  --> Import map with product-card@3.2.1
```

The resolver makes this decision at the edge (CDN worker) or in the host application's server-side rendering.

**2. Feature flag gating:**

```javascript
// Host application
const version = featureFlags.isEnabled('product-card-v4', { userId })
  ? 'https://cdn.example.com/product-card/v4.0.0-beta/index.js'
  : 'https://cdn.example.com/product-card/v3.2.1/index.js';
```

**3. Weighted traffic splitting (edge):**

Cloudflare Workers or Lambda@Edge can route a percentage of traffic to a different MFE version:

```javascript
// Cloudflare Worker
export default {
  async fetch(request) {
    const canary = Math.random() < 0.05; // 5% canary traffic
    const version = canary ? 'v4.0.0-beta' : 'v3.2.1';
    // Modify import map or route to different worker
  }
};
```

**Metrics to monitor during canary:**
- Error rate (JavaScript errors, API errors)
- Core Web Vitals (LCP, FID/INP, CLS)
- Business metrics (conversion rate, engagement)
- Bundle load time
- Memory usage

### 7.4 Rollback Strategies

**Import map rollback (fastest):**

Update the import map to point to the previous bundle URL. No rebuild required. Effective immediately (subject to CDN cache TTL).

```bash
# Rollback product-card from v3.3.0 to v3.2.1
curl -X PUT https://resolver.example.com/api/map \
  -d '{"@company/product-card": "https://cdn.example.com/product-card/v3.2.1/index.js"}'
```

**CDN cache considerations:**
- If bundles use content-hash URLs, the old version is still cached at the edge. Rollback is instant.
- If the import map itself is cached, you need to invalidate the import map's cache entry (typically a single URL).
- Use short TTLs for the import map (e.g., 60 seconds) and long TTLs for hashed bundles (e.g., 1 year).

**Module Federation rollback:**

Update the remote entry URL in the host's configuration. This may require redeploying the host application (unless the remote URL is dynamically resolved).

**Blue-green with micro frontends:**

Maintain two complete sets of bundle URLs ("blue" and "green"). The import map resolver switches between them atomically:

```
Blue (current):  product-card -> v3.2.1, cart -> v2.1.0, header -> v1.5.3
Green (next):    product-card -> v3.3.0, cart -> v2.1.0, header -> v1.5.3
                                 ^ only this changed

Cutover: resolver.setActive('green')
Rollback: resolver.setActive('blue')
```

### 7.5 Monitoring and Observability Across MFEs

**The challenge:**

A user interaction may span multiple micro frontends, each with its own error handling, performance characteristics, and backend dependencies. A slow page load could be caused by any MFE's bundle, any MFE's API calls, or the composition layer itself.

**Frontend observability stack:**

```
Browser
  |
  +-- Performance Observer API
  |     +-- LCP, FID/INP, CLS per MFE
  |     +-- Resource timing (bundle load times)
  |     +-- Long tasks (which MFE is blocking the main thread?)
  |
  +-- Error tracking (Sentry, Datadog RUM)
  |     +-- Source maps per MFE (each deploys its own source maps)
  |     +-- Error grouping by MFE (tag errors with MFE name)
  |     +-- Session replay across MFE boundaries
  |
  +-- Distributed tracing (OpenTelemetry)
  |     +-- Trace context propagation from browser to backends
  |     +-- Span per MFE initialization, render, API call
  |     +-- Correlation with backend traces
  |
  \-- Custom metrics
        +-- MFE mount time (connectedCallback to first render)
        +-- Inter-MFE communication latency (event dispatch to handler)
        +-- Shared dependency load time (React, design system)
```

**OpenTelemetry for frontend MFEs:**

```javascript
import { trace } from '@opentelemetry/api';

const tracer = trace.getTracer('product-card-mfe');

class ProductCard extends HTMLElement {
  async connectedCallback() {
    const span = tracer.startSpan('product-card.mount');
    try {
      const product = await this.fetchProduct();
      this.render(product);
      span.setAttributes({
        'mfe.name': 'product-card',
        'product.id': this.getAttribute('product-id'),
        'render.time_ms': performance.now() - span.startTime,
      });
    } catch (error) {
      span.recordException(error);
      span.setStatus({ code: 2 }); // ERROR
    } finally {
      span.end();
    }
  }
}
```

**Dashboarding by MFE:**

Aggregate metrics by MFE name to answer:
- Which MFE has the highest error rate this week?
- Which MFE is the largest contributor to page LCP?
- Which MFE's bundle size has grown the most over the last month?
- Are there version-specific regressions (v3.2.1 vs v3.3.0)?

---

## 8. Security Considerations

### 8.1 Cross-Origin Concerns (CORS, CSP)

Micro frontends often load JavaScript, CSS, and API data from multiple origins. This immediately engages two browser security mechanisms:

**CORS (Cross-Origin Resource Sharing):**

When MFE-A (served from `https://team-a.example.com`) makes an API request to `https://api.example.com`, the browser enforces CORS:

```
Browser                          API Server
  |-- Preflight OPTIONS --------->|
  |<-- Access-Control headers ----|
  |-- Actual GET/POST ----------->|
  |<-- Response ------------------|
```

**Required CORS headers for MFE architectures:**

```
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, x-access-token
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
```

**Critical CORS mistakes in MFE architectures:**

1. **`Access-Control-Allow-Origin: *` with credentials.** The CORS specification forbids this combination. If MFEs send cookies or auth headers, the server must echo the specific requesting origin.

2. **Missing preflight for custom headers.** If MFEs use `x-access-token` (as PyBend does), the server must handle `OPTIONS` requests and include the header in `Access-Control-Allow-Headers`.

3. **CDN CORS caching.** If the CDN caches a CORS response for one origin, it may serve it to a different origin with the wrong `Access-Control-Allow-Origin` header. Solution: include `Vary: Origin` in the response.

### 8.2 Content Security Policy with Multiple MFE Origins

CSP controls which resources the browser is allowed to load. With micro frontends loaded from multiple origins, CSP configuration becomes complex.

**Typical MFE CSP header:**

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self'
    https://cdn.example.com
    https://team-a.example.com
    https://team-b.example.com
    https://esm.sh;
  style-src 'self' 'unsafe-inline'
    https://cdn.example.com;
  connect-src 'self'
    https://api.example.com
    https://team-a-api.example.com
    https://team-b-api.example.com;
  img-src 'self' data: https:;
  font-src 'self' https://cdn.example.com;
  frame-src https://team-c.example.com;
```

**Challenges:**

1. **CSP bloat.** Each new micro frontend origin requires adding entries to `script-src`, `connect-src`, and potentially other directives. With 10+ MFEs, the CSP header becomes unwieldy.

2. **`unsafe-inline` pressure.** Many frameworks and libraries inject inline styles or scripts. Shadow DOM's `<style>` tags inside shadow roots are NOT blocked by CSP (they are not inline in the document), but dynamically created `<style>` elements in the light DOM are. This often forces `style-src 'unsafe-inline'`.

3. **`unsafe-eval` pressure.** Some template engines and libraries use `eval()` or `new Function()`. Module Federation's runtime does NOT require `unsafe-eval`, but some older libraries do.

4. **Nonce propagation.** If using CSP nonces (`script-src 'nonce-abc123'`), the nonce must be passed to each micro frontend's server so it can include the nonce in dynamically generated script tags. This couples MFE deployment to the host's nonce generation.

**Mitigation strategies:**

- Consolidate MFE assets under a single CDN origin (`cdn.example.com`) to minimize CSP entries
- Use CSP `strict-dynamic` which allows scripts loaded by trusted scripts to execute without explicit origin listing
- Use `Content-Security-Policy-Report-Only` during development to detect violations without breaking the page
- For iframe-based MFEs, each iframe can enforce its own CSP independently

### 8.3 Shared Authentication (JWT, Cookies Across Origins)

Micro frontends must share authentication state. The three primary approaches:

**1. JWT in HTTP header (recommended for same-origin MFEs):**

```javascript
// Shared auth module (loaded via import map)
export function getAuthToken() {
  return localStorage.getItem('auth_token');
}

export function authFetch(url, options = {}) {
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'x-access-token': getAuthToken(),  // PyBend convention
    },
  });
}
```

All MFEs import this shared auth module and use `authFetch` for API requests. The JWT is stored in `localStorage` (accessible to all same-origin scripts) or in a shared cookie.

**2. Cookie-based auth (for cross-origin MFEs):**

Set authentication cookies with appropriate attributes:

```
Set-Cookie: session=abc123;
  Domain=.example.com;    // Available to all subdomains
  Path=/;
  Secure;                 // HTTPS only
  HttpOnly;               // Not accessible to JavaScript
  SameSite=Lax;           // Sent with top-level navigations
```

`Domain=.example.com` makes the cookie available to `team-a.example.com`, `team-b.example.com`, etc.

**Caveat:** `SameSite=Lax` does not send cookies with cross-origin subrequests (fetch/XHR). For API calls from `team-a.example.com` to `api.example.com`, use `SameSite=None; Secure` (requires HTTPS and `Access-Control-Allow-Credentials: true`).

**3. Token relay via postMessage (for iframe MFEs):**

```javascript
// Host application: relay token to iframe MFEs
document.querySelectorAll('iframe[data-mfe]').forEach(iframe => {
  iframe.addEventListener('load', () => {
    iframe.contentWindow.postMessage(
      { type: 'AUTH_TOKEN', token: getAuthToken() },
      iframe.src  // target origin
    );
  });
});
```

**Security requirements for all approaches:**

- Tokens must be short-lived (15-60 minutes) with refresh token rotation
- Never pass tokens in URL query parameters (logged by proxies, visible in Referer headers)
- Validate token signatures on every backend, not just the auth service
- Implement token revocation for logout across all MFEs

### 8.4 Supply Chain Security (Dependency Integrity)

Micro frontends amplify supply chain risk because they load JavaScript from multiple origins at runtime. A compromised CDN, tampered npm package, or malicious MFE update has immediate access to the user's session, DOM, and data.

**The September 2025 npm supply chain attack:**

In September 2025, attackers compromised 18 widely-used npm packages -- including `chalk`, `debug`, `ansi-styles`, and `strip-ansi` -- collectively downloaded over 2.6 billion times per week. Through a targeted phishing campaign against a maintainer, the attackers published malicious versions containing obfuscated JavaScript designed to intercept cryptocurrency transactions. This attack affected applications loading these packages both at build time (via npm install) and at runtime (via CDN).

**Defense layers for MFE architectures:**

**Layer 1: Subresource Integrity (SRI)**

Use import map integrity (Chrome 127+, Safari 18+) or traditional `<script integrity>` attributes:

```json
{
  "imports": {
    "react": "https://esm.sh/react@18.3.1"
  },
  "integrity": {
    "https://esm.sh/react@18.3.1": "sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/..."
  }
}
```

If the CDN serves tampered content, the hash will not match, and the browser will refuse to execute it.

**Layer 2: Pin dependency versions**

Never use open ranges in production import maps:

```json
// DANGEROUS: CDN resolves "latest" -- attacker publishes malicious version
{ "react": "https://esm.sh/react" }

// SAFE: pinned version, content is immutable
{ "react": "https://esm.sh/react@18.3.1" }
```

**Layer 3: First-party CDN for critical dependencies**

Host critical shared dependencies (React, auth libraries) on your own infrastructure rather than relying on public CDNs:

```json
{
  "imports": {
    "react": "https://cdn.yourcompany.com/vendor/react@18.3.1/index.js"
  }
}
```

This ensures you control the content and can verify it during your CI/CD pipeline.

**Layer 4: CSP as a safety net**

Even if a dependency is compromised, CSP limits the damage:
- `connect-src` restricts which domains the script can send data to (blocking exfiltration)
- `script-src` prevents the compromised script from loading additional malicious scripts from unauthorized origins

**Layer 5: Cloudflare's Page Shield / Client-Side Security**

Cloudflare's Page Shield monitors JavaScript execution in real-time. During the September 2025 npm attack, Cloudflare's client-side security scanning detected the malicious code and blocked it before it could execute, making the attack "a non-event" for protected customers.

**Layer 6: Adoption delay policy**

Implement a 7-14 day waiting period before adopting new packages or major updates. Most supply chain attacks are detected within days of publication. This policy would have prevented most 2025 attacks.

**Organizational practices:**

- Mandate phishing-resistant MFA on all developer accounts (GitHub, npm, CDN dashboards)
- Audit import maps in CI/CD: verify that only approved origins and packages are referenced
- Generate and maintain SBOMs (the `importmap.lock` proposal, when adopted, will formalize this)
- Monitor for dependency takeover: watch for maintainer changes on critical packages

---

## Sources

### Historical Evolution
- [ThoughtWorks Technology Radar: Micro Frontends](https://www.thoughtworks.com/radar/techniques/micro-frontends)
- [Martin Fowler: Micro Frontends (Cam Jackson, 2019)](https://martinfowler.com/articles/micro-frontends.html)
- [micro-frontends.org](https://micro-frontends.org/)
- [ThoughtWorks Technology Radar November 2016 (PDF)](https://www.thoughtworks.com/content/dam/thoughtworks/documents/radar/2016/11/tr_technology_radar_vol_15_en.pdf)
- [ThoughtWorks: Micro Frontend Anarchy](https://www.thoughtworks.com/radar/techniques/micro-frontend-anarchy)

### Architecture Patterns
- [Micro Frontend Architecture: Complete Guide 2026 (ThinkSys)](https://thinksys.com/development/micro-frontend-architecture/)
- [Micro-Frontends in 2025 (NashTech)](https://blog.nashtechglobal.com/micro-frontends-in-2025-architecture-trade-offs-and-best-practices/)
- [Complete Guide to Frontend Architecture Patterns 2026 (DEV)](https://dev.to/sizan_mahmud0_e7c3fd0cb68/the-complete-guide-to-frontend-architecture-patterns-in-2026-3ioo)
- [Project Mosaic (Zalando)](https://www.mosaic9.org/)
- [Micro Frontends in Action, Chapter 4: Server-Side Composition (Manning)](https://livebook.manning.com/book/micro-frontends-in-action/chapter-4)
- [Single-SPA Documentation](https://single-spa.js.org/)
- [Microfrontend.dev: Web Components](https://microfrontend.dev/web-standards/micro-frontends-web-components/)
- [Web Components 2025: Shadow DOM and Lit 4.0](https://markaicode.com/web-components-2025-shadow-dom-lit-browser-compatibility/)

### Module Federation
- [Webpack Module Federation Documentation](https://webpack.js.org/concepts/module-federation/)
- [Module Federation Official Site](https://module-federation.io/)
- [Module Federation Shared Dependency Deep Dive](https://maxkim-j.github.io/en/posts/module-federation-shared/)
- [Getting Out of Version-Mismatch-Hell (Angular Architects)](https://www.angulararchitects.io/en/blog/getting-out-of-version-mismatch-hell-with-module-federation/)
- [Rspack Module Federation](https://rspack.rs/guide/features/module-federation)
- [Rspack with Module Federation v2 (DEV)](https://dev.to/ibrahimshamma99/rspack-with-module-federation-v2-is-the-future-3g89)

### Import Maps and Native Federation
- [Mercedes-Benz.io: You Might Not Need Module Federation](https://www.mercedes-benz.io/blog/2023-01-05-you-might-not-need-module-federation-orchestrate-your-microfrontends-at-runtime-with-import-maps)
- [Angular Architects: Import Maps for Micro Frontends](https://www.angulararchitects.io/en/blog/import-maps-the-next-evolution-step-for-micro-frontends-article/)
- [MDN: Import Maps](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script/type/importmap)
- [importmap.lock Proposal (Andrew Nesbitt)](https://nesbitt.io/2026/01/19/importmap-lock.html)
- [JSPM: JavaScript Integrity Manifests with Import Maps](https://jspm.org/js-integrity-with-import-maps)
- [Chrome Intent to Ship: Importmap Integrity](https://groups.google.com/a/chromium.org/g/blink-dev/c/mn0sRHwK7Dc)
- [importmap-rails (GitHub)](https://github.com/rails/importmap-rails)
- [DHH: Modern Web Apps Without Bundling](https://world.hey.com/dhh/modern-web-apps-without-javascript-bundling-or-transpiling-a20f2755)

### Edge Composition
- [Cloudflare: Building Vertical Microfrontends](https://blog.cloudflare.com/vertical-microfrontends/)
- [InfoQ: Cloudflare Vertical Microfrontend Template](https://www.infoq.com/news/2026/02/cloudflare-vmfe-template/)
- [Cloudflare Workers: Microfrontends](https://developers.cloudflare.com/workers/framework-guides/web-apps/microfrontends/)
- [Edge Side Composition Pattern (DEV)](https://dev.to/okmttdhr/micro-frontends-patterns-11-23h0)

### Communication Patterns
- [Share Events and Data Between MFEs (The Architect)](https://blog.wlava.in/2025/07/29/share-events-and-data-between-micro-frontends-mfes/)
- [Framework Agnostic Communication Patterns (Zablocki)](https://ezablocki.com/posts/framework-agnostic-communication-patterns-for-micro-frontends/)
- [Micro Frontends in Action, Chapter 6: Communication (Manning)](https://livebook.manning.com/book/micro-frontends-in-action/chapter-6)
- [MDN: BroadcastChannel API](https://developer.mozilla.org/en-US/docs/Web/API/Broadcast_Channel_API)
- [trutoo/event-bus (GitHub)](https://github.com/trutoo/event-bus)

### Testing
- [Pact Documentation](https://docs.pact.io/)
- [Contract Testing Guide 2025 (TestingMind)](https://www.testingmind.com/contract-testing-an-introduction-and-guide/)
- [Consumer-Driven Contract Testing with Pact (DEV)](https://dev.to/paulsebastianmanole/consumer-driven-contract-testing-with-pact-the-basics-4fk9)

### CI/CD and DevOps
- [Deployment Strategies for Composable Microfrontends (Bits and Pieces)](https://blog.bitsrc.io/deployment-strategies-for-composable-microfrontends-f8a697f7a0ee)
- [Handling Versioning in a Microfrontend Setup (Medium)](https://article.arunangshudas.com/handling-versioning-in-a-microfrontend-setup-27e7902b6f51)
- [Martin Fowler: Canary Release](https://martinfowler.com/bliki/CanaryRelease.html)
- [Building CI/CD for Microservices 2026 (DasRoot)](https://dasroot.net/posts/2026/01/building-ci-cd-microservices-multi-service-deployment-2026/)

### Security
- [Ionic: Best Practices for Building Secure Micro Frontends](https://ionic.io/blog/best-practices-for-building-secure-micro-frontends)
- [CISA: npm Supply Chain Compromise (Sept 2025)](https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem)
- [Cloudflare: How Client-Side Security Made npm Attack a Non-Event](https://blog.cloudflare.com/how-cloudflares-client-side-security-made-the-npm-supply-chain-attack-a-non/)
- [npm Supply Chain Attacks 2026: Defense Guide (Bastion)](https://bastion.tech/blog/npm-supply-chain-attacks-2026-saas-security-guide)
- [Securing Front-end Apps with CORS and CSP (OpenReplay)](https://blog.openreplay.com/securing-front-end-apps-with-cors-and-csp/)

### Observability
- [OpenTelemetry for Distributed Tracing 2025 (Medium)](https://medium.com/@shbhggrwl/backend-observability-in-2025-distributed-tracing-with-opentelemetry-af338a987abb)
- [Observability and Monitoring 2025 (Madrigan)](https://blog.madrigan.com/en/blog/202512120852/)
- [Top 15 Distributed Tracing Tools 2026 (SigNoz)](https://signoz.io/blog/distributed-tracing-tools/)
