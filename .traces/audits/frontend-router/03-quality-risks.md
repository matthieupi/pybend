# Frontend Router: Quality & Risk Assessment

**Auditor:** Claude Opus 4.6
**Date:** 2025-03-25
**Scope:** Router.js, ntx-router.js, ntx-sidebar.js, Observable.js, Component.js, Actor.js, TX.js, Matrix.js, ListElement.js, ntx-item.js, usage sites, all test files.

---

## 1. Potential Bugs

### 1.1 XSS via Title Injection in NTTRouter

**Severity: HIGH | Likelihood: MEDIUM**

`ntx-router.js:115` injects the `title` variable directly into `innerHTML` without sanitization:

```js
// ntx-router.js:111-117
this.shadowRoot.innerHTML = `
    <div class="router-chrome">
        ${showBack ? '<button class="back-btn" title="Back"></button>' : ''}
        <h1 class="router-title">${title}</h1>
    </div>
    <div class="router-content"></div>
`;
```

The `title` is derived from multiple untrusted sources:

- **Entity ref strings** (`ntx-router.js:100`): `title = model`, where `model = routeData.split('/')[0]`. A hash like `#<img src=x onerror=alert(1)>/1` would inject directly.
- **Object routes** (`ntx-router.js:104`): `title = routeData.title || tag`, where `routeData` comes from TX dispatch. Any component sending a NAVIGATE with a crafted `title` can inject.
- **App routes** (`ntx-router.js:95`): `title = routeName.charAt(0).toUpperCase() + routeName.slice(1)`. A hash like `#@<script>alert(1)</script>` would inject.

The hash route is the most accessible vector. While Shadow DOM prevents style leakage, script execution is not blocked by shadow boundaries. Since the hash is user-controlled (directly via URL), this is a real XSS surface.

**Impact:** Script execution in the context of the application. An attacker could craft a URL with a malicious hash fragment, and if a user clicks the link, arbitrary JavaScript runs with full access to `localStorage` (JWT tokens), the DOM, and the N3TX actor system.

### 1.2 XSS via `data-model` and `data-href` in NTTSidebar

**Severity: MEDIUM | Likelihood: LOW**

`ntx-sidebar.js:425` injects `modelName` into `data-model` attribute via template literals inside `innerHTML`:

```js
// ntx-sidebar.js:425
return `<div class="model-section" data-model="${modelName}">`;
```

If `modelName` contains a double-quote followed by malicious attributes or event handlers (e.g., `Foo" onmouseover="alert(1)`), attribute injection is possible. The `modelName` comes from child elements' `model` attribute or the `models` attribute string, both set by the developer in HTML. Low likelihood in practice since these are developer-authored, but the pattern is unsafe.

Similarly, `ntx-sidebar.js:455` injects `entry.href` into `data-href="${entry.href}"` with the same risk profile.

### 1.3 Null Pushed onto History Stack

**Severity: LOW | Likelihood: HIGH (occurs on every first navigation)**

`Router.js:50` unconditionally pushes `old` onto the stack, including `null`:

```js
// Router.js:49-50
const old = this.#current;
this.#stack.push(old);
```

On the very first NAVIGATE call, `this.#current` is `null`, so `null` is pushed onto the stack. When the user goes BACK, `this.#current` is correctly set to `null` via `this.#stack.pop() ?? null` at line 59, but the `?? null` fallback is redundant because `null` was already explicitly pushed. This is not a bug per se -- the behavior is correct -- but the `null` sentinel on the stack is an implicit convention. If future code ever checks `this.#stack.length` to count "real" history entries, it will be off by one.

### 1.4 JSON.stringify Equality Check is Fragile

**Severity: LOW | Likelihood: MEDIUM**

`Router.js:48` uses `JSON.stringify` for deep equality of object routes:

```js
// Router.js:47-48
if (typeof data === 'object' && typeof this.#current === 'object'
    && JSON.stringify(data) === JSON.stringify(this.#current)) return;
```

`JSON.stringify` is key-order-dependent. `{a:1, b:2}` and `{b:2, a:1}` serialize differently and would be treated as different routes, causing a redundant navigation. Since route objects are typically created by sidebar navigation (`ntx-sidebar.js:287`) with a fixed key order (`tag`, `attrs`, `title`), this is unlikely to trigger in practice, but it violates the semantic intent of "same route = no-op."

Additionally, `JSON.stringify` throws on circular references, which would propagate as an unhandled exception. If someone passes a route object with a DOM element reference or other circular structure, the router would crash.

### 1.5 #fromHash Does Not Clear Stack on Hash Removal

**Severity: MEDIUM | Likelihood: MEDIUM**

`Router.js:81-85` handles the case where the hash is cleared:

```js
// Router.js:81-85
} else if (!hash && this.#current) {
    const old = this.#current;
    this.#current = null;
    this.notify('route', this.#current, old);
}
```

This resets `#current` to null but does **not** touch `#stack`. If the user navigated A -> B -> C and then manually clears the hash (e.g., by clicking a plain link), `#current` becomes `null` but `#stack` still contains `[null, A, B]`. If the user then navigates to D, the stack becomes `[null, A, B, null]`, and BACK would cycle through stale entries.

Compare this to `#fromHash` when a new hash is set (line 78): it pushes the old current onto the stack, which is correct for forward navigation, but after a hash-clear, the stack state is inconsistent with the actual browser history.

### 1.6 Hash Route `#` Prefix Stripping Mismatch

**Severity: LOW | Likelihood: LOW**

When a route string starts with `#`, `ntx-router.js:85-88` handles it:

```js
// ntx-router.js:85-88
if (typeof routeData === 'string' && routeData.startsWith('#')) {
    window.location.hash = routeData.slice(1);
    this.#showSlot();
    return;
}
```

This sets `location.hash` to the value *without* the `#`. But `location.hash` setter automatically prepends `#`. So if `routeData` is `#settings`, `location.hash` becomes `#settings` (correct). However, this triggers a `hashchange` event, which `Router.#fromHash()` picks up. `#fromHash` reads `location.hash.slice(1)` = `"settings"` and pushes it as a new route, calling `notify()`. This means NTTRouter.render() fires twice: once from the `#showSlot()` in `#mountView`, and once from the hashchange-triggered route change. The second render may overwrite the slot with a mounted view for "settings" (treated as an entity ref `settings/undefined`).

This is a logic conflict: `#mountView` tries to show slot content but simultaneously triggers a hash navigation that may mount a different view. The veille app (`apps/veille/static/index.html`) uses `#settings`, `#sources` etc. via its own `handleRoute()` function, bypassing the router entirely, which masks this bug.

### 1.7 Observable Not Initialized Before `notify()` in Router

**Severity: LOW | Likelihood: LOW**

`Router.js:53` calls `this.notify(...)` which is mixed in via `Actor.subclass(Router, Observable)` at line 93. The Observable mixin's `notify()` method (Observable.js:117) calls `this._initObservable()` which lazily creates `__observers` if missing. Since `_initObservable` is called inside `notify`, this works correctly even if no `observe()` was called first. However, the `notify` function at `Observable.js:123` does:

```js
const set = this.__observers && this.__observers.get(property);
```

This safely handles the case where `__observers` doesn't exist (returns undefined, no-op). But if `_initObservable` is called first (which it is, at line 117), `__observers` will exist as an empty Map, so `.get(property)` returns `undefined`, and the early return triggers. This is correct behavior, but it means every `notify()` call pays the cost of `_initObservable()` check even when there are zero observers. See Performance section.


---

## 2. Edge Cases

### 2.1 Rapid Navigation (Race Condition)

When multiple NAVIGATE calls fire in quick succession (e.g., rapid item clicks), `NTTRouter.render()` is called synchronously for each `notify('route', ...)`. Each call wipes `shadowRoot.innerHTML` at line 111 and rebuilds the DOM. This means:

1. The first child component is created and appended to `.router-content`.
2. Before it can fully initialize (fetch schema, render), a second NAVIGATE fires.
3. `shadowRoot.innerHTML = ...` destroys the first component mid-initialization.
4. The component's `disconnectedCallback` fires, cleaning up its actor registration and observer subscriptions.

This is not a crash but can cause:
- Orphaned network requests (the first component's schema fetch completes after it's destroyed).
- Actor registry pollution: if `disconnectedCallback` doesn't fully clean up Matrix registrations.
- Flash of content: brief rendering artifacts between navigations.

The NTTRouter does not debounce `render()` -- it renders synchronously on every observer notification. The Component base class has `scheduleRender()` with `requestAnimationFrame` coalescing, but NTTRouter calls `render()` directly.

### 2.2 Empty or Whitespace-Only Hash

`Router.js:75` does `location.hash.slice(1)`. If the hash is `#` (empty after slicing), the condition `if (hash && hash !== this.#current)` at line 76 evaluates `hash` as `""` which is falsy. So it falls to the `else if (!hash && this.#current)` branch at line 81, which clears the current route. This is correct.

But if the hash is `# ` (hash with a space), `hash` is `" "` which is truthy. This would attempt to navigate to the route `" "`, which would pass through `#mountView` as a string route, parsing `model = " ".split('/')[0]` = `" "`, and creating a component with tag resolved from `#resolveTag(" ")`. Since no NTT class would match `" "`, it falls back to `'ntx-item'` and sets `ref=" "`, triggering an ATTACH TX to NTT with data `" "`.

### 2.3 Route Data as `undefined` or Non-Standard Types

`Router.NAVIGATE(data)` checks `data === this.#current` at line 46 for dedup. If `data` is `undefined`, this comparison with `null` (initial `#current`) returns false, so it proceeds. `undefined` is then pushed as the new current. `#toHash` at line 67 checks `typeof this.#current === 'string'`, which fails for undefined, and `this.#current === null` at line 69 also fails. So the hash is not updated, but the route state is corrupted.

Similarly, passing `0`, `false`, `NaN`, or `[]` as route data would behave unexpectedly. The NAVIGATE handler has no type validation.

### 2.4 Router Name Collision

`Router.js:37` stores routers in a module-level `Map` keyed by `addr`:

```js
routers.set(addr, this);
```

There is no check for existing entries. If two `<ntx-router name="main">` elements exist in the DOM (e.g., in the veille app which has complex panel layouts), the second constructor call silently overwrites the first in the routers map. The first NTTRouter's `this.#router` reference is still valid (it holds the actual object), but `getRouter("main")` now returns the second instance. This can cause navigation commands sent to "main" to be handled by the wrong router.

### 2.5 Component Created with Unknown Tag

`ntx-router.js:127` calls `document.createElement(tag)` where `tag` can be any string:

```js
const el = document.createElement(tag);
```

If the tag is not registered as a custom element, this creates an `HTMLUnknownElement`. The element mounts into the DOM without error but renders nothing visible. For `@` routes, `tag = 'ntx-' + routeName`, so `@unknown` creates `<ntx-unknown>` which silently fails. The test suite (`ntx-router-unit.spec.js:219`) confirms this doesn't crash, but there's no user-facing feedback that the route was invalid.

### 2.6 Disconnected NTTRouter Leaks hashchange Listener

`NTTRouter` does not remove the `hashchange` listener in `disconnectedCallback`. The `Router` constructor (`Router.js:34`) adds a `hashchange` listener to `window`, but neither `Router` nor `NTTRouter` provides cleanup for it. If an `<ntx-router hash>` element is removed from the DOM and re-added, a new `hashchange` listener is registered each time (via `connectedCallback` -> `new Router()`), but the old one persists because Router instances are never destroyed.

The `routers` Map at `Router.js:21` also never removes entries, so Router instances are never garbage collected as long as the module is loaded.


---

## 3. Test Coverage Analysis

### 3.1 What IS Tested

| Area | Test File | Coverage |
|------|-----------|----------|
| Router state machine (NAVIGATE/BACK) | `Router.test.js`, `router-navigation.test.js` | Good: string routes, object routes, dedup, stack depth, observer notification |
| Hash sync (basic) | `router-navigation.test.js` | Partial: NAVIGATE updates hash, BACK clears hash |
| `getRouter()` lookup | `Router.test.js` | Good: registered and unregistered lookups |
| NTTRouter custom element registration | `ntx-router.test.js` | Minimal: existence check only |
| NTTRouter shadow DOM creation | `ntx-router.test.js` | Minimal: truthy check |
| NTTRouter render with no route | `ntx-router.test.js` | Minimal: checks slot exists |
| E2E root state | `ntx-router-unit.spec.js` | Good: slot visible, no chrome, no back button |
| E2E detail navigation | `ntx-router-unit.spec.js` | Good: content area, item element, chrome, title |
| E2E back navigation | `ntx-router-unit.spec.js` | Good: back button click, hash clears, slot restores |
| E2E hash routing | `ntx-router-unit.spec.js` | Good: direct URL, programmatic hash, clear hash |
| E2E special routes (@favorites, @profile) | `ntx-router-unit.spec.js` | Good: component creation verified |
| E2E rapid hash changes | `ntx-router-unit.spec.js` | Good: no crash verified |
| E2E responsive viewports | `ntx-router-unit.spec.js` | Good: mobile and desktop |

### 3.2 What is NOT Tested (Gaps)

| Missing Test | Risk | Priority |
|-------------|------|----------|
| **Sidebar -> Router navigation flow** | NAVIGATE TX dispatch from sidebar to router is entirely untested. The sidebar uses dynamic `import('../core/Matrix.js')` for dispatch, which is an unusual pattern that could break silently. | **HIGH** |
| **Object route rendering** | No test verifies that `{ tag, attrs, title }` route data correctly creates the specified element with the specified attributes. All E2E tests use string routes. | **HIGH** |
| **Router name collision** | No test verifies behavior when two routers share the same name. | **MEDIUM** |
| **Hash sync edge cases** | `#fromHash` stack inconsistency on hash-clear (Bug 1.5) is untested. Browser back button after multiple hash navigations only has one basic test. | **MEDIUM** |
| **ListElement.SELECT -> NAVIGATE forwarding** | The `SELECT` handler in `ListElement.js:104-109` that bridges item clicks to router navigation is untested in isolation. | **MEDIUM** |
| **`#resolveTag` schema lookup** | No test verifies that `NTT.get(model)` schema renderer resolution works for routing. | **MEDIUM** |
| **`display="lg"` auto-set** | `ntx-router.js:136-138` sets `display="lg"` on ref-bearing elements, but no test verifies this. | **LOW** |
| **XSS vectors** | No test attempts HTML/script injection through route data or hash values. | **HIGH** |
| **Router cleanup on disconnect** | No test verifies that disconnecting NTTRouter properly unsubscribes from the Router's observable. | **MEDIUM** |
| **Multiple NTTRouter instances** | No test verifies behavior with multiple `<ntx-router>` elements on the same page. | **LOW** |
| **Hash route (#-prefixed string)** | The `#settings` handling path in `#mountView` (line 85-88) is untested. | **MEDIUM** |

### 3.3 Test Quality Assessment

**Router.test.js** (unit, Vitest): **GOOD**. Clean isolated tests with proper observer verification. Each test creates a fresh router with a random name. One gap: hash sync tests are minimal (only checks router creation, doesn't verify hash behavior).

**ntx-router.test.js** (unit, Vitest): **WEAK**. Three superficial tests that check existence of the custom element, shadow DOM truthiness, and slot presence. No actual navigation behavior is tested. The render test at line 49 calls `el.render()` directly without going through `connectedCallback`, skipping Router setup entirely.

**router-navigation.test.js** (integration, Vitest): **GOOD**. Comprehensive state machine testing with hash sync verification. Uses `vi.resetModules()` for clean module state. Tests hash sync correctly by checking `window.location.hash`. Strong coverage of the Router class.

**ntx-router-unit.spec.js** (E2E, Playwright): **GOOD but BRITTLE**.

Brittleness concerns:
- Heavy reliance on `waitForTimeout` with hard-coded delays (1000-3000ms). These will cause flaky tests in CI.
- Shadow DOM traversal via `evaluate()` callbacks is fragile -- any DOM structure change breaks multiple tests.
- Tests depend on a running server with seeded data (Product/1 must exist).

Assertion quality is solid: tests verify both positive presence (element exists) and negative absence (no back button at root, no chrome at root).


---

## 4. Error Handling Gaps

### 4.1 No Error Boundary in NTTRouter.#mountView

`ntx-router.js:127` calls `document.createElement(tag)` which can throw if `tag` contains invalid characters (e.g., spaces, uppercase-only strings without hyphens). No try/catch wraps this section.

```js
// ntx-router.js:127
const el = document.createElement(tag);
```

If an `@` route resolves to an invalid custom element name (e.g., `@123` -> `ntx-123` which starts with a digit after the prefix), `createElement` will throw a `DOMException: The tag name provided is not valid`. This propagates up through `render()` and `#mountView`, leaving the router in a broken state with partially rendered shadow DOM.

### 4.2 Silent Failure in `#resolveTag`

`ntx-router.js:149-155`:

```js
#resolveTag(model) {
    const NTT = window.NTT;
    if (!NTT) return 'ntx-item';
    const DC = NTT.get(model);
    return DC?.schema?.ui?.renderer?.detail
        || DC?.schema?.ui?.renderer?.item
        || 'ntx-item';
}
```

This accesses `window.NTT` directly rather than importing NTT. The NTT module sets `window.NTT` as a side effect. If NTT hasn't loaded yet (e.g., during initial page load when Router processes a hash before NTT module initializes), this silently falls back to `ntx-item`. The user sees a generic item view instead of the model-specific renderer, with no indication that something went wrong.

### 4.3 Sidebar Fetch Errors Swallowed

`ntx-sidebar.js:220-222`:

```js
} catch (e) {
    console.warn(`[ntx-sidebar] Failed to fetch item for ${modelName}:`, e);
}
```

The `#fetchItemRef` catch block logs a warning but does not indicate to the user that the sidebar item is in a degraded state. The sidebar entry remains clickable but will fall back to model list navigation instead of singleton item navigation. This silent degradation could confuse users.

### 4.4 Missing Validation on `routerAddr`

Both `ntx-sidebar.js` (`#navigateToModel`, `#navigateToItem`, `#navigateToLink`) and `ListElement.js:107` read the `router` attribute and send NAVIGATE TXes to it. If `router` is set to a non-existent address, the Matrix attempts to route to it, fails to find a child, and sends the TX to the NetworkAdapter (treating it as a remote target). This causes an HTTP request to `{API_URL}/{routerAddr}` which fails silently.

```js
// ListElement.js:106-109
const routerAddr = this.getAttribute('router');
if (routerAddr) {
    this.send(new TX({ name: 'NAVIGATE', source: this.addr, target: routerAddr, data: data }));
}
```

No validation checks whether `routerAddr` is actually a registered Router actor.


---

## 5. Security Considerations

### 5.1 Hash-Based XSS (Critical)

As detailed in Bug 1.1, the hash fragment is user-controlled and directly interpolated into `innerHTML`. This is the primary security concern.

**Attack vector:**
```
https://app.example.com/#<img/src=x/onerror=alert(document.cookie)>/1
```

The Router's `#fromHash()` reads this as the route string `<img/src=x/onerror=alert(document.cookie)>/1`. NTTRouter's `#mountView` splits on `/`, gets `model = "<img/src=x/onerror=alert(document.cookie)>"`, sets `title = model`, and injects it into `innerHTML`.

**Mitigation:** Sanitize `title` before insertion, or use `textContent` assignment instead of `innerHTML` for the title element.

### 5.2 JWT Token Exposure in Sidebar

`ntx-sidebar.js:196-198`:

```js
const token = localStorage.getItem('jwtToken');
const headers = {};
if (token) headers['x-access-token'] = token;
```

The sidebar sends the JWT token in `#fetchItemRef`. This is necessary for authenticated API access, but the token is sent as a custom header (`x-access-token`) rather than in the `Authorization` header. This means CORS preflight is always required for cross-origin scenarios. Additionally, the token key `'jwtToken'` is hardcoded rather than read from config, creating a coupling risk if the storage key changes.

### 5.3 No Input Sanitization on Sidebar innerHTML

`ntx-sidebar.js:427` injects `gradient` CSS values via `style="background: ${gradient}"`. The gradients come from the hardcoded `AVATAR_GRADIENTS` array, so this is safe. However, the model's `initial` at line 421:

```js
const initial = modelName[0].toUpperCase();
```

is inserted into innerHTML at line 427. Since `modelName` comes from child element attributes (developer-controlled), this is low risk but follows an unsafe pattern.


---

## 6. Performance Risks

### 6.1 Full Shadow DOM Rebuild on Every Navigation

`ntx-router.js:111` does `this.shadowRoot.innerHTML = ...` on every route change. This destroys and rebuilds the entire shadow DOM including the back button, title, and content area. Since `render()` is called directly (not via `scheduleRender()`), there's no frame coalescing.

For the back button, this means event listeners are re-created on every navigation. While the back button is simple, the child component mounted in `.router-content` may be heavyweight (e.g., `<ntx-table model="Grant">` with hundreds of rows). Destroying and re-creating it on every navigation forces a full schema fetch + data load cycle.

**Recommendation:** Cache previously created views and hide/show them instead of destroy/create. This is a common "keep-alive" pattern in routers.

### 6.2 JSON.stringify on Every NAVIGATE

`Router.js:48` calls `JSON.stringify` on both the current route and the incoming data for every object-type NAVIGATE. For large route objects (e.g., with many attrs), this is O(n) serialization on every navigation event. While route objects are typically small, this is an unnecessary cost for a hot path.

### 6.3 Observable._initObservable() Called on Every notify()

`Observable.js:117` calls `this._initObservable()` inside every `notify()` call. This checks and potentially creates `__signals` and `__observers` Maps. For Router, `notify('route', ...)` is called on every NAVIGATE and BACK, so this initialization check runs on every navigation. After the first call, it's a no-op (just an `if` check), but it adds unnecessary overhead.

### 6.4 Sidebar Dynamic Import on Every Navigation

`ntx-sidebar.js:282-289`:

```js
import('../core/Matrix.js').then(({ matrix }) => {
    matrix.dispatch({...});
});
```

Each navigation call in the sidebar uses a dynamic `import()`. After the first import, the module is cached by the browser's module loader, so the cost is a microtask (Promise resolution) rather than a network request. However, this means navigation dispatch is always asynchronous, even though the module is already loaded. The `this.close()` at line 290 executes synchronously before the dispatch, so the sidebar closes before navigation happens -- a minor visual timing issue.

### 6.5 Unbounded History Stack

`Router.js:50` pushes every navigation onto `#stack` with no upper bound. A long browsing session (hundreds of navigations) would accumulate a large array. Each entry is a route data object (string or object), so memory growth is linear but unbounded. The stack is never trimmed.

For reference, most browser implementations cap the history stack at ~50 entries. The Router has no such limit.


---

## 7. Concurrency Issues

### 7.1 Async Import Race in Sidebar Navigation

`ntx-sidebar.js:282` uses `import('../core/Matrix.js').then(...)` for dispatching navigation. If the user clicks two sidebar items in rapid succession, two async dispatches are queued. Since Promise resolution order matches creation order, the second navigation will fire after the first, resulting in two NAVIGATE events hitting the router in sequence. The router processes both, and the user ends up two levels deep in the stack.

This is correct behavior (each click is a navigation), but since `this.close()` fires synchronously on line 290, the sidebar closes immediately after the first click. The second click would require the sidebar to be reopened. So in practice, double-navigation is unlikely unless the user is extremely fast.

### 7.2 hashchange and NAVIGATE Race

When hash sync is enabled, both external hash changes (browser back, manual URL edit) and programmatic NAVIGATE calls can modify route state. `Router.NAVIGATE()` calls `#toHash()` which sets `location.hash`, which triggers a `hashchange` event, which calls `#fromHash()`.

`#fromHash` at line 76 checks `hash !== this.#current`. Since NAVIGATE already set `#current` before calling `#toHash`, the `#fromHash` handler sees that hash matches current and does nothing. This is correct.

However, if two NAVIGATE calls fire within the same event loop tick:
1. First NAVIGATE: sets `#current = "A"`, calls `#toHash()` which sets `location.hash = "A"`.
2. Second NAVIGATE: sets `#current = "B"`, calls `#toHash()` which sets `location.hash = "B"`.
3. The `hashchange` event for the first `location.hash = "A"` fires. `#fromHash` reads `location.hash` which is now `"B"`. It checks `"B" !== this.#current("B")` -- false, so no-op.
4. The `hashchange` event for `location.hash = "B"` fires. Same check, no-op.

This works correctly because `hashchange` fires asynchronously (after the current task completes), and by then `#current` is already updated. But it depends on the browser's `hashchange` coalescing behavior. If the browser fires separate `hashchange` events for each `location.hash` assignment, intermediate states could cause issues.

### 7.3 NTT.attach Async Bootstrap

`ntx-sidebar.js:177` calls `NTT.attach(modelName, callback)`. This is asynchronous -- it fetches the schema from the backend. If the user clicks a sidebar model entry before the schema loads, `#navigateToModel` dispatches a NAVIGATE TX with a `{tag, attrs, title}` object. The `tag` comes from the route template (developer-provided) so it's valid. But if the NTT DynamicClass hasn't loaded yet, the mounted component won't have schema data and will show a skeleton/loading state. This is acceptable degradation, not a bug.


---

## 8. Resource Management

### 8.1 Router Instances Never Garbage Collected

`Router.js:21`:
```js
const routers = new Map();
```

`Router.js:37`:
```js
routers.set(addr, this);
```

Router instances are stored in a module-level Map with strong references. There is no `destroy()` method or way to remove a router from the map. Since `NTTRouter.disconnectedCallback()` only unsubscribes from the route observer (line 57), the Router actor itself persists indefinitely. In a single-page application this is fine (routers are long-lived), but in a scenario where `<ntx-router>` elements are dynamically created and destroyed (e.g., in a test harness), this constitutes a memory leak.

The Matrix also holds a reference to each Router via `matrix.register(this)` at `Router.js:31`. Matrix's children map is never cleaned up either.

### 8.2 Event Listeners Not Cleaned Up

**Router hashchange listener** (`Router.js:34`):
```js
window.addEventListener('hashchange', () => this.#fromHash());
```

This arrow function captures `this` (the Router instance) but is never removed. Even if all references to the Router are dropped, the `hashchange` listener prevents garbage collection. The arrow function is anonymous, so `removeEventListener` cannot target it.

**NTTRouter back button listener** (`ntx-router.js:121-123`): Created on every render, but since `innerHTML` wipes the previous DOM, old listeners are cleaned up via element destruction. This is correct.

**NTTSidebar listeners** (`ntx-sidebar.js:133-144`): Properly cleaned up in `disconnectedCallback` (lines 148-153) for document-level listeners. The internal click listeners on shadow DOM elements are cleaned up when the elements are destroyed (they're part of the shadow DOM which is managed by the component lifecycle).

### 8.3 NTTRouter #currentView Not Cleaned Up on Disconnect

`NTTRouter.disconnectedCallback()` at `ntx-router.js:55-58`:

```js
disconnectedCallback() {
    super.disconnectedCallback();
    this.#routerUnsub?.();
}
```

This unsubscribes from route changes but does not call `this.#currentView?.remove()` or otherwise clean up the currently mounted view. If the NTTRouter is removed from the DOM while a view is mounted, the view's `disconnectedCallback` fires automatically (because it's in the shadow DOM which is being removed), so this is likely fine. But `#currentView` remains referenced, preventing garbage collection of the mounted component until the NTTRouter itself is collected.


---

## 9. Technical Debt Inventory

### 9.1 TODO / FIXME Comments

- `Actor.js:179`: `// TODO: Make callable via ChildClass.subclass()` -- commented-out code for an alternative calling convention.
- `Actor.js:236`: `// TODO ths can easily execute with another Type before the Matrix is setup` -- acknowledged race condition in actor subclass registration.
- `Matrix.js:67`: `// Todo: Analalyze if we need to handle network init for a class here` -- unresolved architecture question.

No TODOs in the Router/NTTRouter/Sidebar files themselves.

### 9.2 Dead Code

- `TX.js:40-43`: The `dispatch()` method is commented out but still has its JSDoc. The comment-closing `*/` at line 44 is misplaced -- it's inside the `repr()` method, making the `dispatch()` method's documentation a dangling comment block.

- `TX.js:76-117`: Five TX subclasses (`ConnectEvent`, `EnableEvent`, `DisableEvent`, `UpdateEvent`, `GetEvent`, `DescribeEvent`, `ReadEvent`) are defined but only `ConnectEvent` and `ReadEvent` are exported. `DisableEvent` and `UpdateEvent` have incorrect constructor signatures (passing positional args to `super()` instead of an object), which would crash if instantiated.

- `Actor.js:104-116`: The parent delegation traversal is commented out with `/* Temporarily disabled */`. This means all unrouted messages go directly to the root Matrix instead of traversing the class hierarchy.

### 9.3 Inconsistent Patterns

**Module-level import vs. window global**: `ntx-router.js:149` uses `window.NTT` while the rest of the codebase uses ES module imports (`import { NTT } from '../core/NTT.js'`). This inconsistency means `#resolveTag` depends on a side effect (`NTT.js` setting `window.NTT`) rather than a direct dependency.

**Sidebar not an Actor**: `NTTSidebar` extends plain `HTMLElement` (line 61), not `Component`. It cannot send TXes directly and must use `import('../core/Matrix.js').then(...)` to dispatch. Every other UI component in the system extends `Component` which has built-in `send()`. This asymmetry adds complexity and introduces the async dispatch pattern.

**NTTRouter observe vs. Component subscribe**: `NTTRouter.connectedCallback` at line 43 uses `router.observe('route', () => this.render())`. The callback is an arrow function that calls `render()` directly, bypassing `scheduleRender()`. Other components use `this.subscribe(proto, 'UPDATE', callback)` which goes through the Component subscription system. NTTRouter should use `scheduleRender()` to get frame coalescing.

### 9.4 Duplication

- **Router auto-config** is duplicated: `ntx-router.js:46-49` (connectedCallback) and `ntx-router.js:139-142` (`#mountView`) both set the `router` attribute on model-bearing children. The pattern is identical but split across two methods.

- **`display="lg"` force** at `ntx-router.js:136-138` partially duplicates the intent of `Component.normalizeDisplay` and `displayBreakpoints`. The router forces detail display mode, but the Component's ResizeObserver may override it.


---

## 10. Failure Modes

### 10.1 Matrix Not Initialized

If `Router.js` is imported before `Matrix.js` (which creates the root actor), `matrix.register(this)` at line 31 would call `register` on an uninitialized Matrix. However, the ES module import at line 19 (`import { matrix } from './Matrix.js'`) ensures Matrix.js is loaded first, and `Matrix.js:81` creates the singleton before the export is available. So this failure mode is prevented by module ordering.

If for some reason the Matrix module fails to load (network error), the `import` would throw and Router.js would not execute at all. This is a hard failure -- the router system is completely unavailable.

### 10.2 Schema Service Unavailable

If the backend API is down:
- `#resolveTag` falls back to `'ntx-item'` (no crash).
- The mounted `<ntx-item>` shows a skeleton placeholder indefinitely (no error indication to user).
- Sidebar `#fetchItemRef` catches the error and logs a warning.
- NTT.attach callbacks never fire, so sidebar model counts stay empty.

This is graceful degradation -- the app is non-functional but doesn't crash.

### 10.3 Custom Element Not Registered

If a required custom element (`ntx-item`, `ntx-list`, `ntx-table`) is not imported:
- `document.createElement('ntx-item')` creates an `HTMLUnknownElement`.
- The element is appended to the DOM but renders nothing.
- No error is thrown or logged.
- The user sees a blank content area with just the router chrome (back button + title).

This silent failure violates "Transparent, not magical" -- the developer gets no signal that something is missing.

### 10.4 Blast Radius Analysis

| Failure | Blast Radius | Recovery |
|---------|-------------|----------|
| XSS via hash | **App-wide** -- attacker has full JS context | Requires page reload; stolen tokens require password reset |
| Router Actor crash | **Navigation system** -- no routing until page reload | Page reload |
| Matrix failure | **Entire app** -- all TX routing stops | Page reload |
| Schema service down | **Data display** -- skeletons everywhere, no data | Automatic when service recovers (requires user action to trigger re-fetch) |
| Single component error | **One view** -- error in mounted component doesn't affect router | Navigate away and back |
| Sidebar unavailable | **Navigation UX** -- can still use hash URLs directly | Hash-based navigation still works |


---

## 11. Summary: Top 5 Risks by Priority

| # | Risk | Severity | File:Line | Recommended Fix |
|---|------|----------|-----------|-----------------|
| 1 | **XSS via hash injection** | CRITICAL | `ntx-router.js:115` | Use `textContent` instead of `innerHTML` for title, or sanitize all route-derived strings |
| 2 | **No debounce on NTTRouter.render()** | HIGH | `ntx-router.js:43` | Use `scheduleRender()` instead of direct `render()` in observer callback |
| 3 | **Hash-clear stack inconsistency** | MEDIUM | `Router.js:81-85` | Clear the stack when hash is manually cleared, or at minimum push to make stack match browser history |
| 4 | **Router instances never cleaned up** | MEDIUM | `Router.js:21,37` | Add `destroy()` method that removes from `routers` Map and Matrix, removes `hashchange` listener |
| 5 | **Sidebar not an Actor** | LOW (tech debt) | `ntx-sidebar.js:61` | Extend Component or use ActorProxy to enable direct `send()` and eliminate async import pattern |
