# Frontend Router -- Deep Audit Report

**Date**: 2026-03-25
**Auditor**: Claude Opus 4.6
**Scope**: Router.js, ntx-router.js, ntx-sidebar.js, Observable.js, Component.js, Actor.js, TX.js, Matrix.js, ListElement.js, ntx-item.js, all usage sites and test files.
**Source Reports**: 01-architecture.md, 02-api-contracts.md, 03-quality-risks.md, 04-extensibility.md, 05-improvements.md

---

## Executive Summary

The N3TX frontend routing subsystem manages client-side navigation for a schema-driven framework where Python model definitions are the single source of truth. It is split into two layers: **Router** (in n3tx-core), a pure Actor + Observable state machine that manages a LIFO history stack, hash synchronization, and change notifications with zero DOM knowledge; and **NTTRouter** (in n3tx-ui), a Web Component view container that mounts and destroys child components in response to Router state changes. Navigation producers -- NTTSidebar for model discovery and ListElement for item-click forwarding -- dispatch TX messages through the Matrix actor bus. This architecture totals roughly 700 lines across three primary files and correctly separates state from view, reuses the framework's own Actor/TX messaging primitives rather than inventing a routing-specific protocol, and delivers zero-config entity navigation that works out of the box.

The audit identifies **one critical security issue, three high-severity design risks, and nine improvement opportunities**. The critical issue is an XSS vector: route titles derived from user-controlled URL hash fragments are interpolated directly into `innerHTML` without sanitization (`ntx-router.js:114`), allowing script execution via crafted URLs that could steal JWT tokens from `localStorage`. The three high-severity design risks are: (1) route data polymorphism -- three shapes (entity string, app string, programmatic object) flow through the same channel with different serialization, deduplication, and hash-sync behavior, creating a "some routes survive refresh, some don't" developer experience; (2) the NTTSidebar is the only interactive component in the system that does not extend Component, forcing it to use async dynamic imports for Matrix dispatch with a hardcoded `source: 'sidebar'` string; and (3) full shadow DOM rebuild on every navigation, destroying and recreating all chrome and content without caching.

The **top three recommendations** are: (1) sanitize all route-derived strings before innerHTML injection -- a one-line fix using `textContent` assignment that eliminates the XSS surface; (2) standardize route data to strings only, adding `parseRoute()` / `buildRoute()` utility functions that unify the route grammar, make all routes hash-serializable, and eliminate the fragile `JSON.stringify` object dedup; (3) cap the history stack at 50 entries and add a Router `destroy()` method to prevent memory leaks in dynamic scenarios.

The **top three strategic improvement propositions** are: (P1) string-only route data with parse/build utilities -- the foundation that enables hash round-trips for all navigation, eliminates object routes, and simplifies the entire resolution pipeline; (P4) schema-driven route resolution via `ui.renderer.list` -- extending the "backend is authoritative" philosophy to list views so the sidebar no longer needs to construct client-side route objects; and (P8) a pluggable route resolver registry -- enabling apps like veille to register custom resolvers instead of building parallel routing systems that bypass the framework entirely. These propositions form an incremental migration path across four phases, each independently deployable, totaling approximately 400 lines changed across 6 files.

---

## Component Overview

```
                        +-----------+
                        |   User    |
                        +-----+-----+
                              |
                 +------------+------------+
                 |                         |
            clicks item             clicks sidebar
                 |                         |
                 v                         v
          +----------+             +-------------+
          | NTTItem  |             | NTTSidebar  |
          | card.click|             | .model-name |
          +----+-----+             +------+------+
               |                          |
         TX SELECT                  matrix.dispatch()
       target=list              NAVIGATE TX (object)
               |                          |
               v                          v
        +------------+            +---------+
        | ListElement|            |  Matrix  |
        | .SELECT()  |            | .inbox() |
        +-----+------+            +----+----+
              |                        |
        TX NAVIGATE              routes to child
       target=router                   |
              |                        |
              +----------+------------+
                         |
                         v
                   +-----------+
                   |  Router   |  (Actor + Observable)
                   |-----------|
                   | #current  |  <-- state
                   | #stack    |  <-- history
                   | #hashSync |  <-- URL binding
                   +-----+-----+
                         |
                   notify('route')
                         |
                         v
                  +------------+
                  |  NTTRouter  |  (Component)
                  |------------|
                  | render()   |  --> #mountView() or #showSlot()
                  +------+-----+
                         |
                         v
                +------------------+
                | Dynamic Element  |
                | <ntx-item>       |
                | <ntx-list>       |
                | <ntx-table>      |
                | <ntx-profile>    |
                +------------------+

Package boundaries:
  n3tx-core:  Router, Actor, Observable, TX, Matrix, Component, NTT
  n3tx-ui:    NTTRouter, NTTSidebar, ListElement, NTTItem
  Dependency direction: n3tx-ui --> n3tx-core (never reverse)
```

### Component Inventory

| Component | File | Lines | Role |
|-----------|------|-------|------|
| Router | `packages/n3tx-core/src/n3tx_core/static/core/Router.js` | 94 | Pure navigation state Actor; stack, hash sync, Observable notifications |
| NTTRouter | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js` | 159 | View container; mounts/destroys child components based on Router state |
| NTTSidebar | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js` | 498 | Navigation producer; slide-in panel dispatching NAVIGATE TXs |
| ListElement | `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js` | ~200 | Collection base; forwards child SELECT as NAVIGATE to router |
| NTTItem | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` | ~800 | Entity renderer; dispatches SELECT TX on card click |
| Observable | `packages/n3tx-core/src/n3tx_core/static/core/Observable.js` | 133 | Mixin adding observe/notify/signal to Router |
| Actor | `packages/n3tx-core/src/n3tx_core/static/core/Actor.js` | 337 | Base class for message-passing entities |
| TX | `packages/n3tx-core/src/n3tx_core/static/core/TX.js` | 117 | Message envelope dataclass |
| Matrix | `packages/n3tx-core/src/n3tx_core/static/core/Matrix.js` | 81 | Root actor singleton, message bus |
| Component | `packages/n3tx-core/src/n3tx_core/static/core/Component.js` | 450+ | HTMLElement + Actor bridge |

---

## Key Findings

### Critical Issues

#### F1. XSS via Hash Injection in NTTRouter Title
- **Finding**: Route titles derived from user-controlled URL hash fragments are interpolated directly into `innerHTML` without sanitization.
- **Evidence**: `ntx-router.js:114`
  ```javascript
  <h1 class="router-title">${title}</h1>
  ```
  The `title` variable originates from `routeData.split('/')[0]` (line 97) for entity refs, from `routeName` for `@` routes (line 95), and from `routeData.title` for object routes (line 104). The hash route is the most accessible vector: a URL like `https://app.example.com/#<img/src=x/onerror=alert(document.cookie)>/1` would inject directly. Shadow DOM does not prevent script execution.
- **Severity**: Critical
- **Recommendation**: Replace innerHTML title injection with `textContent` assignment. After building the chrome HTML, use:
  ```javascript
  this.shadowRoot.querySelector('.router-title').textContent = title;
  ```
  Alternatively, sanitize via `title.replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":"&#39;"}[c]))` before interpolation. The `textContent` approach is simpler and eliminates the entire class of injection.

#### F2. XSS via `data-model` Attribute Injection in NTTSidebar
- **Finding**: `modelName` is interpolated into `data-model` attribute via template literal inside `innerHTML`.
- **Evidence**: `ntx-sidebar.js:425`
  ```javascript
  return `<div class="model-section" data-model="${modelName}">`;
  ```
  If `modelName` contains a double-quote followed by malicious attributes (e.g., `Foo" onmouseover="alert(1)`), attribute injection is possible. Similarly, `entry.href` at line 455 (`data-href="${entry.href}"`) has the same pattern.
- **Severity**: Medium (developer-controlled input, not user-controlled in typical usage)
- **Recommendation**: Escape attribute values or use DOM APIs (`el.dataset.model = modelName`) instead of string interpolation.

#### F3. Hash-Clear Stack Inconsistency
- **Finding**: When the URL hash is manually cleared, `#fromHash()` resets `#current` to null but does not push the old route onto `#stack`, creating an asymmetry with NAVIGATE's always-push behavior.
- **Evidence**: `Router.js:81-85`
  ```javascript
  } else if (!hash && this.#current) {
      const old = this.#current;
      this.#current = null;
      this.notify('route', this.#current, old);
  }
  ```
  Compare with `#fromHash` when a new hash is set (line 77-80) which correctly pushes old to stack. After hash-clear, the user cannot use the internal BACK button to return to the previous route, and the internal stack diverges from browser history.
- **Severity**: Medium
- **Recommendation**: Push old route to stack before clearing, matching the NAVIGATE behavior:
  ```javascript
  } else if (!hash && this.#current) {
      const old = this.#current;
      this.#stack.push(old);
      this.#current = null;
      this.notify('route', this.#current, old);
  }
  ```

#### F4. Router Instances Never Garbage Collected
- **Finding**: Router instances are stored in a module-level `Map` with strong references. No `destroy()` method exists. The `hashchange` listener uses an anonymous arrow function that cannot be removed.
- **Evidence**: `Router.js:21` (`const routers = new Map();`), `Router.js:37` (`routers.set(addr, this);`), `Router.js:34` (`window.addEventListener('hashchange', () => this.#fromHash());`)
- **Severity**: Medium (memory leak in dynamic scenarios; harmless in single-page apps with one router)
- **Recommendation**: Add a `destroy()` method:
  ```javascript
  destroy() {
      routers.delete(this.addr);
      if (this.#hashListener) {
          window.removeEventListener('hashchange', this.#hashListener);
      }
  }
  ```
  Store the listener reference in a private field during construction.

#### F5. Object Routes Cannot Survive Hash Round-Trip
- **Finding**: Sidebar-initiated navigation creates object route data (`{tag, attrs, title}`) that is silently dropped by `#toHash()`. Page refresh, browser back/forward, and bookmarking all lose sidebar-initiated navigation state.
- **Evidence**: `Router.js:66-71`
  ```javascript
  #toHash() {
      if (typeof this.#current === 'string') {
          location.hash = this.#current;
      } else if (this.#current === null) {
          history.replaceState(null, '', location.pathname + location.search);
      }
      // Object routes: silently not serialized
  }
  ```
- **Severity**: High (largest architectural gap; directly impacts user experience)
- **Recommendation**: Standardize all route data to strings (see Proposition P1). Object routes become `"Grant?view=table"` strings that round-trip through hash.

#### F6. No Render Debounce on NTTRouter
- **Finding**: NTTRouter observes route changes with a direct `render()` call, bypassing the Component base class's `scheduleRender()` frame coalescing.
- **Evidence**: `ntx-router.js:43`
  ```javascript
  this.#routerUnsub = router.observe('route', () => this.render());
  ```
  Rapid navigations cause synchronous full shadow DOM rebuilds without animation frame batching. The Component base class provides `scheduleRender()` via `requestAnimationFrame` for exactly this purpose.
- **Severity**: High (performance; rapid navigation causes DOM thrashing and potential orphaned network requests)
- **Recommendation**: Use `scheduleRender()` or debounce the render callback.

#### F7. JSON.stringify Equality Check is Fragile
- **Finding**: Object route deduplication uses `JSON.stringify` which is key-order-dependent and throws on circular references.
- **Evidence**: `Router.js:47-48`
  ```javascript
  if (typeof data === 'object' && typeof this.#current === 'object'
      && JSON.stringify(data) === JSON.stringify(this.#current)) return;
  ```
- **Severity**: Low (unlikely to trigger with current sidebar-generated objects, but violates semantic intent)
- **Recommendation**: Eliminated entirely by Proposition P1 (string-only routes). Short-term: use a proper deep-equal utility.

---

### Design Strengths

**S1. Clean State/View Separation.** Router (state) and NTTRouter (view) are properly separated. Router is 94 lines of pure state with zero DOM knowledge. NTTRouter is pure view with no state management. This is the most important architectural decision and it is correct. It enables testing Router without DOM and lets NTTRouter focus on component mounting. Evidence: Router.js has zero DOM imports; NTTRouter reads state via `this.#router.current` (ntx-router.js:63).

**S2. Consistent Actor/TX Messaging.** Navigation commands flow through the same TX/Matrix system as all other N3TX communication. No routing-specific protocol exists. NAVIGATE and BACK are standard UPPERCASE TX handlers (Router.js:45, 56), consistent with SELECT, UPDATE, READ, and DESCRIBE used elsewhere. This embodies the "primitives, not opinions" philosophy.

**S3. Strong Encapsulation.** All three primary classes use true private fields (`#`). Router: `#current`, `#stack`, `#hashSync`, `#toHash()`, `#fromHash()`. NTTRouter: `#router`, `#routerUnsub`, `#currentView`, `#mountView()`, `#showSlot()`, `#resolveTag()`. NTTSidebar: `#entries`, `#models`, `#routeTemplates`, `#dynamicClasses`, `#itemRefs`, `#expanded`. Internal state cannot be accidentally accessed or mutated from outside.

**S4. Loose Coupling in the Navigation Chain.** Items know only a `select-target` address (ntx-item.js:751). Lists know only a `router` address from an HTML attribute (ListElement.js:106-109). Neither knows about the Router class or each other. This indirection permits flexible composition and is exemplary loose coupling.

**S5. Slot-Based Default Content.** NTTRouter uses native Shadow DOM slot projection for the "home page" (ntx-router.js:77). Children declared in `<ntx-router>` are projected without cloning. Navigation replaces them; going back restores them. This is idiomatic Web Components requiring zero framework code.

**S6. Declarative HTML Configuration.** The sidebar-router-content relationship is expressed in HTML attributes (`router="main"`, `name="main"`, `hash`). Route templates are declared as child elements of `<ntx-sidebar>`. A developer can read the HTML and understand the navigation structure without consulting source code.

---

### Design Trade-offs

**T1. Route Data Polymorphism vs. Simplicity.** Three route shapes (entity string, `@` app route, `{tag, attrs, title}` object) allow maximum flexibility but create inconsistent behavior: strings survive hash round-trips, objects do not; strings use `===` dedup, objects use `JSON.stringify`; strings produce readable URLs, objects are opaque. The trade-off was flexibility over consistency. **Assessment**: The flexibility is rarely exercised (only sidebar uses objects), and the inconsistency actively confuses the developer experience. This trade-off no longer makes sense -- string-only routes with a route parser deliver the same flexibility with full consistency.

**T2. Sidebar as Plain HTMLElement vs. Actor Consistency.** NTTSidebar extends `HTMLElement` directly (ntx-sidebar.js:61) rather than `Component`. This avoids the overhead of Component's schema/model/display lifecycle for a navigation panel that doesn't render entities. The cost: no `send()` method, requiring dynamic `import('../core/Matrix.js')` for dispatch (ntx-sidebar.js:282). **Assessment**: The overhead concern is valid but minimal -- Component's extra properties (schema, proto, value) are harmless when unused. The async dispatch pattern is the only instance in the codebase, creating a real consistency gap. Converting to Component would be a net improvement.

**T3. Full DOM Rebuild vs. Implementation Simplicity.** NTTRouter rebuilds the entire shadow DOM on every navigation (`this.shadowRoot.innerHTML = ...` at ntx-router.js:111). No component caching or keep-alive. This is simple to implement and reason about -- no stale state concerns, no cache eviction logic. The cost: every navigation triggers full schema resolution, data fetch, and render. **Assessment**: Acceptable for the current app complexity (1-3 models) but will become a performance concern as apps grow. A persistent-chrome approach (Proposition P7) offers a middle ground.

---

### Improvement Opportunities

| # | Improvement | Impact | Effort | Category |
|---|-------------|--------|--------|----------|
| 1 | Sanitize route-derived strings before innerHTML (F1) | Critical (security) | Trivial | Security |
| 2 | Standardize route data to strings only (F5, T1) | High (consistency) | Low | Architecture |
| 3 | Add `parseRoute()` / `buildRoute()` utilities | High (DX) | Low | Architecture |
| 4 | Cap history stack at 50 entries | Low (resilience) | Trivial | Resilience |
| 5 | Add Router `destroy()` method (F4) | Medium (cleanup) | Low | Resource mgmt |
| 6 | Fix hash-clear stack asymmetry (F3) | Medium (correctness) | Trivial | Bug fix |
| 7 | Use `scheduleRender()` in NTTRouter observer (F6) | High (performance) | Trivial | Performance |
| 8 | Add `ui.renderer.list` schema convention | Medium (schema completeness) | Low | Convention |
| 9 | Convert NTTSidebar to extend Component (T2) | Medium (consistency) | Medium | Consistency |
| 10 | Add unknown custom element fallback in NTTRouter | Medium (DX) | Low | Resilience |
| 11 | Persistent chrome in NTTRouter (T3) | Medium (performance) | Low | Performance |
| 12 | Add route guard hooks on NTTRouter | Medium (feature) | Medium | Extensibility |

---

## Strategic Propositions

### Simplification Propositions

#### P1. String-Only Route Data

- **Current state**: Route data is polymorphic -- three shapes with different serialization and dedup behavior. Router.js:45-54 accepts any value. NTTRouter's `#mountView()` (ntx-router.js:81-107) uses a chain of `typeof` checks and string prefix detection to resolve routes. The sidebar constructs `{tag, attrs, title}` objects (ntx-sidebar.js:283-288) that cannot round-trip through hash.
- **Proposed change**: Route data is always a string. The NAVIGATE handler rejects non-strings with a deprecation warning during migration:
  ```javascript
  NAVIGATE(data, tx) {
      if (typeof data !== 'string') {
          if (typeof data === 'object' && data?.attrs?.model) {
              console.warn('[Router] Object route data is deprecated. Use string routes.');
              data = data.attrs.model;
          } else { return; }
      }
      if (data === this.#current) return;
      // ... rest unchanged, minus JSON.stringify dedup
  }
  ```
- **What gets simpler**: Dedup is always `===` (delete 2 lines). Hash sync is total (all routes round-trip). `#mountView()` shape detection reduces from 4 branches to 2 (`@` prefix and entity grammar). The "some routes survive refresh, some don't" dichotomy disappears.
- **Migration path**: Phase 1: add `parseRoute()`/`buildRoute()` utilities (additive, no breakage). Phase 2: update sidebar to emit strings. Phase 3: remove object-route support from Router after deprecation period.
- **Risk**: Low. Only the sidebar emits object routes. ListElement already sends strings. Backward-compat wrapper handles the transition.

#### P2. parseRoute() and buildRoute() Utilities

- **Current state**: Route string interpretation is embedded in `#mountView()` (ntx-router.js:81-107) with inline `split('/')`, `startsWith('@')`, and `startsWith('#')` checks. Route construction is scattered: ListElement sends raw entity refs (ListElement.js:108), sidebar constructs objects (ntx-sidebar.js:264-291), links send raw hrefs (ntx-sidebar.js:324-337).
- **Proposed change**: Add two exported utility functions to Router.js:
  ```javascript
  export function parseRoute(route) {
      if (!route || typeof route !== 'string') return null;
      if (route.startsWith('@')) return { type: 'app', name: route.slice(1) };
      const [path, query] = route.split('?');
      const parts = path.split('/');
      return {
          type: 'entity', model: parts[0], id: parts[1] || null,
          action: parts[2] || null,
          params: query ? Object.fromEntries(new URLSearchParams(query)) : {},
      };
  }

  export function buildRoute(model, { id, action, params } = {}) {
      let route = model;
      if (id) route += `/${id}`;
      if (action) route += `/${action}`;
      if (params && Object.keys(params).length) {
          route += '?' + new URLSearchParams(params).toString();
      }
      return route;
  }
  ```
- **What gets simpler**: `#mountView()` becomes `const parsed = parseRoute(route); const {tag, attrs} = this.#resolveComponent(parsed);`. Route construction in the sidebar becomes `buildRoute(modelName, {params: {view: 'table'}})`. One grammar, one parser, one builder.
- **Migration path**: Purely additive. Add functions, then update consumers one at a time.
- **Risk**: Minimal. The grammar `Model[/id[/action]][?params]` covers all current routes plus the planned veille routes.

#### P7. Persistent Chrome in NTTRouter

- **Current state**: `ntx-router.js:111` does `this.shadowRoot.innerHTML = ...` on every navigation, rebuilding the entire shadow DOM including back button and title bar. Back button event listeners are re-created each time.
- **Proposed change**: Use `prerender()` to create persistent chrome, swap only content:
  ```javascript
  prerender() {
      this.shadowRoot.innerHTML = `
          <div class="router-chrome" hidden></div>
          <div class="router-content"><slot></slot></div>
      `;
  }

  #mountView(routeData) {
      const chrome = this.shadowRoot.querySelector('.router-chrome');
      const content = this.shadowRoot.querySelector('.router-content');
      chrome.hidden = false;
      chrome.querySelector('.router-title').textContent = title; // textContent, not innerHTML
      if (this.#currentView) this.#currentView.remove();
      content.querySelector('slot')?.remove();
      const el = document.createElement(tag);
      // ... set attrs ...
      this.#currentView = el;
      content.appendChild(el);
  }

  #showSlot() {
      const chrome = this.shadowRoot.querySelector('.router-chrome');
      chrome.hidden = true;
      if (this.#currentView) { this.#currentView.remove(); this.#currentView = null; }
      const content = this.shadowRoot.querySelector('.router-content');
      if (!content.querySelector('slot')) content.innerHTML = '<slot></slot>';
  }
  ```
- **What gets simpler**: Back button listener is bound once. Chrome DOM elements persist. Only the content area changes on navigation. This also fixes F1 (XSS) by using `textContent` for the title.
- **Migration path**: Single commit. Replace `render()`, `#mountView()`, and `#showSlot()`. Add `prerender()`. No external API changes.
- **Risk**: Low. Must verify that `<slot>` projection works correctly when re-added to an existing container.

---

### Composability & Extensibility Propositions

#### P4. Schema-Driven Route Resolution

- **Current friction**: NTTRouter's `#resolveTag()` (ntx-router.js:148-155) only handles detail views via `ui.renderer.detail` / `ui.renderer.item`. List views have no schema resolution -- the sidebar must construct the tag client-side. This violates "backend is authoritative."
- **Proposed design**: Extend `#resolveTag()` to a `#resolveComponent(parsed)` that handles both list and detail routes:
  ```javascript
  #resolveComponent(parsed) {
      const DC = NTT.get(parsed.model);
      const renderer = DC?.schema?.ui?.renderer || {};
      if (parsed.id) {
          return { tag: renderer.detail || renderer.item || 'ntx-item',
                   attrs: { ref: `${parsed.model}/${parsed.id}` } };
      } else {
          const tag = renderer.list || 'ntx-list';
          const attrs = { model: parsed.model };
          if (parsed.params?.['allow-create']) attrs['allow-create'] = '';
          return { tag, attrs };
      }
  }
  ```
  Backend models declare `__ui__ = {'renderer': {'list': 'ntx-table'}}` and the frontend resolves list components from schema.
- **What it enables**: Sidebar emits `"Grant"` (a simple string). NTTRouter resolves it to `<ntx-table model="Grant">` via schema. Adding a new model with a custom list view requires only a backend `__ui__` change -- zero frontend modification. Full "backend is authoritative" for list views.
- **Effort estimate**: Medium (backend schema convention + frontend resolver update + sidebar simplification).

#### P6. NTTSidebar Extends Component

- **Current friction**: Sidebar extends `HTMLElement` (ntx-sidebar.js:61), not `Component`. It cannot use `this.send()` and must use `import('../core/Matrix.js').then(({matrix}) => matrix.dispatch({...}))` with a hardcoded `source: 'sidebar'` string (ntx-sidebar.js:282-289). This is the only component in the system using this pattern.
- **Proposed design**:
  ```javascript
  class NTTSidebar extends Component {
      constructor() { super({}); }

      #navigateToModel(modelName) {
          const routerAddr = this.getAttribute('router');
          if (!routerAddr) return;
          const route = buildRoute(modelName, { params });
          this.send(new TX({ name: 'NAVIGATE', source: this.addr,
                             target: routerAddr, data: route }));
          this.close();
      }
  }
  ```
- **What it enables**: Synchronous navigation dispatch (no async import gap). Proper actor identity (`this.addr` instead of hardcoded `'sidebar'`). Participation in interceptor chains if frontend interceptors are added. Consistent with every other interactive component.
- **Effort estimate**: Medium (change base class, remove manual `attachShadow`, replace 3 dynamic imports with `this.send()`).

#### P8. Route Resolver Registry

- **Current friction**: Adding a new route type (e.g., `Grant/3/analyze`) requires modifying NTTRouter's `#mountView()`. The veille app bypasses the router entirely with a manual `handleRoute()` function (apps/veille/static/index.html:275-303).
- **Proposed design**:
  ```javascript
  // Router.js -- exported, extensible
  const _resolvers = [];
  export function addRouteResolver(resolver) { _resolvers.push(resolver); }

  export function resolveRoute(routeString) {
      const parsed = parseRoute(routeString);
      for (const resolver of _resolvers) {
          const result = resolver(parsed, routeString);
          if (result) return result;
      }
      return defaultResolve(parsed);
  }
  ```
  Apps register custom resolvers:
  ```javascript
  addRouteResolver((parsed) => {
      if (parsed.action === 'analyze')
          return { tag: 'ntx-grant-analyze', attrs: { model: 'Grant', uuid: parsed.id } };
      return null; // fall through to default
  });
  ```
- **What it enables**: Veille migrates from a parallel routing system to a registered resolver. New route types are added without framework modification. Open-closed principle for route resolution.
- **Effort estimate**: Medium (add registry to Router.js, update NTTRouter to call `resolveRoute()`, migrate veille).

---

### Resilience Propositions

#### P10. History Stack Depth Cap

- **Current failure mode**: `Router.js:50` pushes every navigation onto `#stack` with no upper bound. A long browsing session (hundreds of navigations) grows the array indefinitely.
- **Proposed improvement**:
  ```javascript
  this.#stack.push(old);
  if (this.#stack.length > 50) this.#stack.shift();
  ```
  One-line change. Zero API impact. Matches typical browser history caps.
- **Blast radius reduction**: Prevents unbounded memory growth. Drops the oldest entries that users would never navigate back to.

#### P11. Hash Sync Re-entrancy Guard

- **Current failure mode**: When NAVIGATE calls `#toHash()` which sets `location.hash`, the browser fires a `hashchange` event, which calls `#fromHash()`. The `hash !== this.#current` check (Router.js:76) prevents infinite loops, but the timing depends on browser hashchange coalescing behavior. Two NAVIGATE calls in the same tick could cause intermediate states.
- **Proposed improvement**:
  ```javascript
  #suppressHash = false;

  #toHash() {
      this.#suppressHash = true;
      if (typeof this.#current === 'string') { location.hash = this.#current; }
      else if (this.#current === null) {
          history.replaceState(null, '', location.pathname + location.search);
      }
      requestAnimationFrame(() => { this.#suppressHash = false; });
  }

  #fromHash() {
      if (this.#suppressHash) return;
      // ... existing logic
  }
  ```
- **Blast radius reduction**: Eliminates the possibility of re-entrant stack manipulation during programmatic navigation.

#### P12. Unknown Custom Element Fallback

- **Current failure mode**: `document.createElement(tag)` at `ntx-router.js:127` silently creates an `HTMLUnknownElement` if the tag is not registered. The user sees a blank content area with chrome. No error, no feedback.
- **Proposed improvement**:
  ```javascript
  if (tag.includes('-') && !customElements.get(tag)) {
      console.warn(`[ntx-router] Component <${tag}> not registered for route "${routeData}".`);
      // Show informative fallback
      const fallback = document.createElement('div');
      fallback.className = 'router-error';
      fallback.textContent = `Component <${tag}> is not registered.`;
      content.appendChild(fallback);
      return;
  }
  ```
- **Blast radius reduction**: Converts a silent blank page into a visible, diagnosable error. Aligns with the "transparent, not magical" philosophy.

---

### Proposition Priority Matrix

| # | Proposition | Simplifies | Impact | Effort | Risk | Enables |
|---|-------------|------------|--------|--------|------|---------|
| P1 | String-only route data | Eliminates object routes, unifies hash sync | High | Low | Low | P2, P4, P5, P8, P15 |
| P2 | `parseRoute()` + `buildRoute()` | Centralized route grammar | High | Low | Low | P4, P5, P8, P14 |
| P7 | Persistent chrome in NTTRouter | Eliminates full DOM rebuild | Medium | Low | Low | Independent |
| P10 | Stack depth cap (50) | Prevents unbounded growth | Low | Trivial | None | Independent |
| P12 | Unknown element fallback | Visible error instead of blank | Medium | Low | None | Independent |
| P4 | Schema-driven route resolution | Convention-driven list resolution | High | Medium | Low | P9; requires P1, P2 |
| P5 | Sidebar emits route strings | Hash round-trip for all nav | High | Low | Low | Requires P1, P2 |
| P3 | Schema `ui.renderer.list` | Backend-authoritative list views | Medium | Low | None | Independent |
| P6 | Sidebar extends Component | Actor consistency | Medium | Medium | Low | Independent |
| P8 | Route resolver registry | Pluggable route resolution | High | Medium | Low | Requires P2 |
| P9 | Route guards on NTTRouter | Unsaved-changes, auth redirects | Medium | Medium | Medium | Requires P4 |
| P11 | Hash sync re-entrancy guard | Prevents race conditions | Low | Low | None | Independent |
| P13 | Default `hash: true` | Convention over config | Low | Trivial | Low | Independent |
| P14 | Title from schema | Richer page titles | Low | Low | None | Requires P2 |
| P15 | Eliminate hash-redirect case | Remove bypass mechanism | Low | Low | Low | Requires P1 |

**Quick wins** (high impact, low effort): P1, P2, P10, P12, P7
**Strategic investments** (high impact, medium+ effort, unlocks future work): P4, P8, P6
**Dependencies**: P2 depends on P1. P4, P5, P8, P14 depend on P2. P9 depends on P4. P15 depends on P1.

---

## Downstream Use Guide

### For Bug Hunting

**Risk areas ranked by probability of containing bugs:**

1. **Hash sync edge cases** (`Router.js:66-86`): Stack/hash divergence when user manually edits URL, clears hash, or uses browser back during object-route navigation. The asymmetric `#fromHash()` behavior (F3) is a confirmed bug.
2. **NTTRouter `#mountView()` string interpolation** (`ntx-router.js:111-117`): Any route-derived value reaching innerHTML is a potential XSS vector (F1, confirmed).
3. **Rapid navigation sequence** (`ntx-router.js:43, 62-68`): No debounce means rapid clicks cause synchronous DOM rebuilds. Orphaned network requests from destroyed components are likely.
4. **Sidebar async dispatch timing** (`ntx-sidebar.js:282-290`): `close()` fires before `matrix.dispatch()`. If user interaction during the async gap modifies state, dispatch may use stale data.
5. **Router name collision** (`Router.js:37`): Two `<ntx-router name="main">` elements silently overwrite each other in the `routers` Map. `getRouter("main")` returns the second; the first NTTRouter still holds the original reference.

**Untested edge cases with specific scenarios:**
- NAVIGATE with `undefined`, `false`, `0`, `NaN`, or `[]` as data (all accepted, stored in stack)
- Two NTTRouter elements with the same `name` attribute, one with `hash`, one without
- Sidebar dispatching NAVIGATE before the NTTRouter's `connectedCallback` creates the Router
- Hash route `#settings` in NTTRouter triggering both `#showSlot()` and a `hashchange` event
- Browser back button after navigating: entity click -> sidebar model click -> entity click (mixed object/string stack)

**Suggested test cases:**
- `test_xss_hash_injection`: Navigate to a route with `<img/src=x/onerror=...>` in the hash; verify no script execution.
- `test_hash_clear_preserves_back_stack`: Navigate A -> B, clear hash manually, verify BACK returns to A.
- `test_navigate_undefined_no_stack_corruption`: Call `NAVIGATE(undefined)`, verify `canGoBack` is false and stack is clean.
- `test_router_name_collision_second_wins`: Create two Routers with same addr, verify `getRouter` returns the second.
- `test_sidebar_to_router_object_route_renders`: Verify sidebar model click produces a mounted list component (currently untested).
- `test_rapid_navigation_no_orphaned_elements`: Navigate 10 times rapidly, verify only 1 child in `.router-content`.

### For Feature Development

**Extension points with difficulty ratings:**

| Extension Point | Difficulty | Example |
|----------------|-----------|---------|
| New `@appRoute` page | Easy | Create `<ntx-settings>` component, navigate via `@settings` |
| Schema `ui.renderer.detail` override | Easy | Set `__ui__['renderer']['detail'] = 'ntx-custom'` on model |
| Sidebar route template | Easy | Add `<ntx-table model="X">` as child of `<ntx-sidebar>` |
| Observable route listener | Easy | `getRouter('main').observe('route', callback)` |
| Multiple independent routers | Easy | `<ntx-router name="panel-a">` and `<ntx-router name="panel-b">` |
| Custom route resolver (after P8) | Easy | `addRouteResolver((parsed) => ...)` |
| Subclassing NTTRouter | Hard | Private fields block access; must override `render()` entirely |
| Route guards / navigation prevention | Hard | No hook exists; requires Router.js modification |
| Keep-alive / component caching | Hard | Requires component pool, hide/show, cache eviction |
| Nested / hierarchical routes | Hard | Requires route parsing, parent-child router coordination |

**Patterns to follow:**
- For new navigation producers: see `ListElement.SELECT()` at `ListElement.js:104-109` -- read `router` attribute, construct TX with NAVIGATE name and target.
- For new route observers: see `ntx-router.js:43` -- `getRouter(name).observe('route', callback)`, store unsub, call in `disconnectedCallback`.
- For new rendered components: see `ntx-router.js:127-144` -- `document.createElement(tag)`, set attrs, set router on model-bearing children, append to content.

**Constraints to be aware of:**
- Router accepts any value as route data -- add input validation if producing routes from user input.
- The `router` attribute must exactly match the NTTRouter's `name` attribute (case-sensitive, no validation).
- Object routes do not appear in the URL hash -- if your feature needs deep linking, use string routes.
- NTTRouter uses `window.NTT` global (not an import) for tag resolution -- NTT must be loaded before the first navigation.

**Common pitfalls:**
- Forgetting to set `router` attribute on a new list component causes clicks to be silently swallowed.
- Using `render()` instead of `scheduleRender()` in observer callbacks causes synchronous DOM rebuilds.
- Creating a Router with `hash: true` after another Router already has hash sync causes hash fights.
- Inserting HTML from route data into innerHTML creates XSS vectors.

### For Integration Planning

**All integration boundaries with data contracts:**

| Boundary | From | To | Data Contract | Stability |
|----------|------|----|---------------|-----------|
| Router -> NTTRouter | Observable.notify | observe callback | `(newRoute, oldRoute, 'route', router)` | Stable |
| Producers -> Router | TX via Matrix | NAVIGATE handler | `TX.data: string \| object` (string preferred) | Stable |
| NTTRouter -> NTT | `window.NTT.get()` | Schema lookup | `DC.schema.ui.renderer.{detail,item}` | Fragile (window global) |
| Sidebar -> NTT | `NTT.attach()` | Schema bootstrap | `callback(DynamicClass)` | Stable |
| Sidebar -> Matrix | `matrix.dispatch()` | Message bus | `{name, source, target, data}` | Stable (but inconsistent) |
| Router -> Browser | `location.hash`, `hashchange` | Hash sync | String hash values only | Problematic (dual-system conflict) |
| Sidebar -> Document | `sidebar-toggle`, `keydown` | DOM events | Standard events | Stable |

**Dependencies and stability:**
- Actor.js: Foundation. Extremely stable. No routing-specific changes needed.
- Observable.js: Stable. Clean API. Used by Router and DynamicClasses identically.
- Matrix.js: Stable. Standard message routing. One concern: unregistered targets silently route to NetworkAdapter.
- Component.js: Heavy but stable. NTTRouter uses ~10% of its surface area.
- NTT.js: Semi-stable. `window.NTT` global is a side effect; `_paginationMeta` and `_schema` are internal.

**Impact analysis checklist when changing this subsystem:**
- [ ] Does the change affect hash sync? If so, test with browser back/forward, manual URL editing, and page refresh.
- [ ] Does the change affect route data shape? If so, update Router dedup, `#toHash()`, `#fromHash()`, and NTTRouter `#mountView()`.
- [ ] Does the change affect the sidebar? If so, verify all three entry types (model, item, link) still navigate correctly.
- [ ] Does the change affect NTTRouter rendering? If so, verify slot projection, chrome visibility, back button, and detail display mode.
- [ ] Run: `Router.test.js`, `router-navigation.test.js`, `ntx-router.test.js`, `ntx-router-unit.spec.js` (E2E).

### For Refactoring

**Technical debt items ranked by severity and coupling risk:**

| # | Debt Item | Severity | Coupling Risk | Location |
|---|-----------|----------|---------------|----------|
| 1 | XSS via innerHTML title injection | Critical | Low (local fix) | ntx-router.js:114 |
| 2 | Object route data support (complexity source) | High | Medium (sidebar, Router, NTTRouter) | Router.js:47-48, ntx-router.js:101-104, ntx-sidebar.js:282-289 |
| 3 | Sidebar not an Actor (inconsistency) | Medium | Medium (changes base class) | ntx-sidebar.js:61 |
| 4 | No Router cleanup/destroy | Medium | Low (additive) | Router.js:21,37 |
| 5 | `window.NTT` global access in `#resolveTag` | Low | Low (change to import) | ntx-router.js:149 |
| 6 | Full shadow DOM rebuild on navigation | Low | Low (NTTRouter internal) | ntx-router.js:111 |
| 7 | Hardcoded `'ntx-'` prefix for `@` routes | Low | Low (NTTRouter internal) | ntx-router.js:94 |
| 8 | Duplicated router auto-config logic | Low | Low (NTTRouter internal) | ntx-router.js:46-49 and 139-142 |

**Suggested refactoring sequence (dependency order):**

1. **Fix F1 (XSS)** -- zero dependencies, critical severity, one-line change. Do this first.
2. **Fix F3 (hash-clear stack)** -- zero dependencies, bug fix, one-line change.
3. **Add P10 (stack cap)** -- zero dependencies, one-line change.
4. **Add P2 (`parseRoute`/`buildRoute`)** -- additive, no existing code changes.
5. **Implement P7 (persistent chrome)** -- internal to NTTRouter, fixes F1 structurally.
6. **Implement P1 (string-only routes)** -- requires P2. Changes Router + NTTRouter + sidebar.
7. **Implement P5 (sidebar strings)** -- requires P1. Changes sidebar only.
8. **Implement P4 (schema resolution)** -- requires P1+P2. Changes NTTRouter `#mountView()`.
9. **Implement P6 (sidebar as Component)** -- independent. Changes sidebar base class.
10. **Implement P8 (resolver registry)** -- requires P2. Additive to Router.js.

**Risk assessment for major candidates:**

| Refactoring | Risk | Mitigation |
|-------------|------|------------|
| String-only routes (P1) | Medium: sidebar emits objects today | Backward-compat wrapper with deprecation warning |
| Sidebar as Component (P6) | Medium: changes base class, may affect lifecycle | Verify that unused Component features (schema, proto) are harmless |
| Persistent chrome (P7) | Low: internal to NTTRouter | Verify slot projection works when re-added to existing container |
| Schema resolution (P4) | Medium: changes how all routes resolve | Comprehensive test coverage before and after |

---

## Appendix: Complete Finding Index

| ID | Dimension | Type | Severity | Finding/Proposition | File(s) | Status |
|----|-----------|------|----------|---------------------|---------|--------|
| F1 | Quality | Finding | Critical | XSS via hash injection in innerHTML title | ntx-router.js:114 | Open |
| F2 | Quality | Finding | Medium | XSS via `data-model` attribute injection | ntx-sidebar.js:425 | Open |
| F3 | Quality | Finding | Medium | Hash-clear does not push old route to stack | Router.js:81-85 | Open |
| F4 | Quality | Finding | Medium | Router instances never garbage collected | Router.js:21,37 | Open |
| F5 | Architecture | Finding | High | Object routes cannot survive hash round-trip | Router.js:66-71 | Open |
| F6 | Quality | Finding | High | No render debounce on NTTRouter observer | ntx-router.js:43 | Open |
| F7 | Quality | Finding | Low | JSON.stringify equality is key-order-dependent | Router.js:47-48 | Open |
| F8 | Architecture | Finding | Medium | Sidebar not an Actor (inconsistency) | ntx-sidebar.js:61 | Open |
| F9 | Quality | Finding | Low | Null pushed onto stack on first NAVIGATE | Router.js:49-50 | Accepted |
| F10 | Quality | Finding | Low | Observable._initObservable() on every notify | Observable.js:117 | Accepted |
| F11 | API | Finding | Medium | Silent navigation failure on mismatched names | ntx-sidebar.js:265, ntx-router.js:35 | Open |
| F12 | API | Finding | Medium | Hash config race condition between NTTRouters | ntx-router.js:36-39 | Open |
| F13 | Quality | Finding | Low | Disconnected NTTRouter leaks hashchange listener | Router.js:34 | Open |
| F14 | Quality | Finding | Medium | No error boundary in #mountView | ntx-router.js:127 | Open |
| F15 | API | Finding | Low | NAVIGATE re-entrancy during observer notification | Router.js:53, Observable.js:126 | Open |
| F16 | Architecture | Finding | Medium | `window.NTT` global access instead of import | ntx-router.js:149 | Open |
| F17 | Quality | Finding | Low | Unbounded history stack | Router.js:50 | Open |
| F18 | Quality | Finding | Low | Sidebar JWT token key hardcoded | ntx-sidebar.js:196 | Accepted |
| F19 | Architecture | Finding | Medium | Veille bypasses router with parallel hash system | apps/veille/static/index.html:275-303 | Open |
| F20 | Quality | Finding | Low | Hash route `#` prefix causes double-render | ntx-router.js:85-88 | Open |
| F21 | API | Finding | Low | No validation on NAVIGATE data type | Router.js:45 | Open |
| P1 | Improvements | Proposition | High | String-only route data | Router.js, ntx-router.js, ntx-sidebar.js | Proposed |
| P2 | Improvements | Proposition | High | parseRoute() + buildRoute() utilities | Router.js | Proposed |
| P3 | Improvements | Proposition | Medium | Schema `ui.renderer.list` convention | Backend schema, ntx-router.js | Proposed |
| P4 | Improvements | Proposition | High | Schema-driven route resolution | ntx-router.js | Proposed |
| P5 | Improvements | Proposition | High | Sidebar emits route strings | ntx-sidebar.js | Proposed |
| P6 | Improvements | Proposition | Medium | Sidebar extends Component | ntx-sidebar.js | Proposed |
| P7 | Improvements | Proposition | Medium | Persistent chrome in NTTRouter | ntx-router.js | Proposed |
| P8 | Improvements | Proposition | High | Route resolver registry | Router.js | Proposed |
| P9 | Improvements | Proposition | Medium | Route guards on NTTRouter | ntx-router.js | Proposed |
| P10 | Improvements | Proposition | Low | Stack depth cap (50 entries) | Router.js:50 | Proposed |
| P11 | Improvements | Proposition | Low | Hash sync re-entrancy guard | Router.js | Proposed |
| P12 | Improvements | Proposition | Medium | Unknown element fallback | ntx-router.js:127 | Proposed |
| P13 | Improvements | Proposition | Low | Default hash: true | Router.js:29 | Proposed |
| P14 | Improvements | Proposition | Low | Title resolution from schema | ntx-router.js | Proposed |
| P15 | Improvements | Proposition | Low | Eliminate hash-redirect special case | ntx-router.js:85-89 | Proposed |
