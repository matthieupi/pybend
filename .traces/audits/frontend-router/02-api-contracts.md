# Frontend Router — API Surface & Contracts Audit

## 1. Public API Inventory

### 1.1 Router (n3tx-core/static/core/Router.js)

| API | Signature | Returns | Side Effects | Notes |
|-----|-----------|---------|-------------|-------|
| `constructor` | `new Router(addr: string, { hash?: boolean })` | `Router` | Registers in Matrix, registers in module-level `routers` Map, optionally binds `hashchange` listener and reads initial hash | `hash` defaults to `false` |
| `current` (getter) | `.current` | `string \| object \| null` | None | Read-only via private field `#current` |
| `canGoBack` (getter) | `.canGoBack` | `boolean` | None | `#stack.length > 0` |
| `NAVIGATE` (TX handler) | `NAVIGATE(data: any, tx?: TX)` | `void` | Pushes old route to `#stack`, sets `#current`, updates hash, calls `notify('route', ...)` | Dedup: identity for strings, `JSON.stringify` for objects |
| `BACK` (TX handler) | `BACK(data?: any, tx?: TX)` | `void` | Pops from `#stack`, sets `#current`, updates hash, calls `notify('route', ...)` | No-op if `canGoBack` is false |
| `getRouter` (module export) | `getRouter(addr: string)` | `Router \| undefined` | None | Reads from module-level `routers` Map |

Observable mixin methods (applied via `Actor.subclass(Router, Observable)` at line 93):

| API | Signature | Returns | Side Effects | Notes |
|-----|-----------|---------|-------------|-------|
| `observe` | `.observe(property: string, callback: Function)` | `() => void` (unsub) | Registers callback in `__observers` Map | Asserts property is non-empty string, callback is function |
| `notify` | `.notify(property: string, newValue, oldValue)` | `void` | Calls all registered callbacks for `property` | Callbacks receive `(newValue, oldValue, property, this)` |
| `signal` | `.signal(callback?, wait?)` | `(() => void) \| void` | Registers/triggers signal callbacks | Not used by Router directly |

Actor inherited methods (from `Actor.js`):

| API | Signature | Returns | Notes |
|-----|-----------|---------|-------|
| `addr` (getter) | `.addr` | `string` | Immutable after construction |
| `inbox` | `.inbox(event)` | `TX` | Routes to UPPERCASE handler by `tx.name` |
| `send` | `.send(event)` | varies | Routes through class hierarchy to Matrix |
| `register` | `.register(actor)` | `void` | Registers child actor |
| `children` (getter) | `.children` | `Map` | Instance-level child actors |

### 1.2 NTTRouter (n3tx-ui/static/components/ntx-router.js)

| API | Signature | Returns | Side Effects | Notes |
|-----|-----------|---------|-------------|-------|
| `constructor` | `new NTTRouter()` | `NTTRouter` | Calls `super({})`, creates shadow DOM | No parameters |
| `styles` (getter) | `.styles` | `string` (URL) | None | Returns URL to `ntx-router.css` |
| `connectedCallback` | `.connectedCallback()` | `void` | Creates/retrieves Router actor, subscribes to route changes, auto-wires `router` attr on `[model]` children, calls `render()` | Main initialization |
| `disconnectedCallback` | `.disconnectedCallback()` | `void` | Unsubscribes from Router observation | Cleanup |
| `render` | `.render()` | `void` | Dispatches to `#mountView()` or `#showSlot()` based on `Router.current` | Called on every route change |

HTML attributes:

| Attribute | Type | Default | Effect |
|-----------|------|---------|--------|
| `name` | string | `router-{auto-addr}` | Router actor address. Used by sidebar/list to target NAVIGATE TXs |
| `hash` | boolean (presence) | absent | Enables hash sync on the underlying Router actor |

Private methods (internal API, not callable externally):

| Method | Purpose |
|--------|---------|
| `#showSlot()` | Removes current view, sets `shadowRoot.innerHTML = '<slot></slot>'` |
| `#mountView(routeData)` | Resolves route data to tag/attrs, creates element, builds chrome, mounts in shadow DOM |
| `#resolveTag(model)` | Looks up component tag from NTT DynamicClass schema `ui.renderer.detail \|\| ui.renderer.item \|\| 'ntx-item'` |

### 1.3 NTTSidebar (n3tx-ui/static/components/ntx-sidebar.js)

| API | Signature | Returns | Side Effects | Notes |
|-----|-----------|---------|-------------|-------|
| `constructor` | `new NTTSidebar()` | `NTTSidebar` | Attaches shadow DOM, appends stylesheet link | No parameters |
| `toggle()` | `.toggle()` | `void` | Toggles `open` attribute | Public |
| `open()` | `.open()` | `void` | Sets `open` attribute | Public |
| `close()` | `.close()` | `void` | Removes `open` attribute | Public |

HTML attributes:

| Attribute | Type | Default | Effect |
|-----------|------|---------|--------|
| `models` | string (CSV) | `''` | Legacy: comma-separated model names |
| `router` | string | none | Router actor address for navigation dispatch |
| `view` | `'grid' \| 'table'` | `'grid'` | Default list component tag |
| `open` | boolean (presence) | absent | Sidebar visibility |

### 1.4 ListElement.SELECT (n3tx-ui/static/components/ListElement.js)

| API | Signature | Returns | Side Effects |
|-----|-----------|---------|-------------|
| `SELECT(data, tx)` | Handler | `void` | Toggles selection, sends NAVIGATE TX if `router` attribute present |

### 1.5 NTTItem click handler (n3tx-ui/static/components/ntx-item.js)

The card click handler at line 747 dispatches a `SELECT` TX to the `select-target` attribute address, which is typically the parent ListElement's addr.

---

## 2. Contracts & Invariants

### 2.1 Router State Machine Contracts

**INV-1: Stack integrity.** `#stack` is a strict LIFO array. Every `NAVIGATE` pushes the previous `#current` (even if `null`). Every `BACK` pops exactly one entry.

```
Before NAVIGATE(X):  current=A, stack=[..., prev]
After  NAVIGATE(X):  current=X, stack=[..., prev, A]

Before BACK():       current=B, stack=[..., A]
After  BACK():       current=A, stack=[...]
```

**INV-2: Null initial state.** `#current` starts as `null`. `#stack` starts empty. The first `NAVIGATE` pushes `null` onto the stack.

**INV-3: Observer notification.** Every state change (successful `NAVIGATE` or `BACK`) calls `notify('route', newCurrent, oldCurrent)`. The only silent operations are: (a) duplicate NAVIGATE, (b) BACK when stack is empty.

**INV-4: Hash reflects string routes.** When `#hashSync` is true, `location.hash` is set to `#current` after every state change -- but only for string routes. Object routes silently do not update the hash. Null routes clear the hash via `history.replaceState`.

**INV-5: Deduplication.** NAVIGATE is idempotent for identical data. String dedup uses `===`. Object dedup uses `JSON.stringify` comparison (Router.js:47-48).

**INV-6: Router global uniqueness.** Each addr maps to exactly one Router in the module-level `routers` Map. However, **there is no enforcement** -- constructing a second Router with the same addr silently overwrites the first in the map (Router.js:37).

### 2.2 NTTRouter View Contracts

**PRE-1: Router actor must exist.** `connectedCallback` creates one if `getRouter(name)` returns falsy. The `hash` option is only set on creation -- if a Router already exists (e.g., created by another NTTRouter with the same name), its hash setting is not modified.

**POST-1: Render consistency.** After `render()`, exactly one of these is true:
- `Router.current` is falsy: shadow DOM contains `<slot></slot>`, `#currentView` is null
- `Router.current` is truthy: shadow DOM contains `.router-chrome` + `.router-content` with a mounted component, `#currentView` references the mounted element

**INV-7: Auto-router wiring.** On connect, NTTRouter sets `router="{name}"` on all descendant `[model]` elements that lack a router attribute (ntx-router.js:46-49). This also happens for dynamically mounted views (ntx-router.js:140-142).

**INV-8: Display mode for entity refs.** When route data contains a `ref` attribute, the mounted component gets `display="lg"` unless it already has a `display` attribute (ntx-router.js:136-138). This enforces detail-view rendering for entity navigation.

### 2.3 NTTSidebar Navigation Contracts

**PRE-2: Router attribute required.** All three `#navigateTo*` methods check `this.getAttribute('router')` and return early if absent (ntx-sidebar.js:265-266, 293-294, 324-325). No error is raised -- navigation is silently dropped.

**POST-2: Sidebar closes after navigation.** Every navigation method calls `this.close()` after dispatching the NAVIGATE TX (ntx-sidebar.js:290, 321, 336).

**INV-9: Dynamic import for Matrix.** The sidebar dynamically imports `../core/Matrix.js` for every navigation dispatch (ntx-sidebar.js:282, 309, 328). This is because NTTSidebar does not extend Component/Actor -- it has no `send()` method.

---

## 3. Error Handling Contracts

### 3.1 Router Error Handling

| Situation | Behavior | Location |
|-----------|----------|----------|
| NAVIGATE with same data | Silent no-op (return) | Router.js:46-48 |
| BACK with empty stack | Silent no-op (return) | Router.js:57 |
| `getRouter` with unknown addr | Returns `undefined` | Router.js:90 |
| NAVIGATE with invalid data (null, undefined, 0) | **BUG**: `null` is treated as "no route" by NTTRouter but `0` or `''` are falsy and would trigger `#showSlot` | Router.js:46, ntx-router.js:64 |

The Router does not throw exceptions. All error conditions are handled by early return. There is no validation of route data shape -- any value is accepted.

### 3.2 NTTRouter Error Handling

| Situation | Behavior | Location |
|-----------|----------|----------|
| Unknown tag in `document.createElement` | Browser creates `HTMLUnknownElement`; no crash but no rendering | ntx-router.js:127 |
| `#resolveTag` with missing NTT registry | Returns `'ntx-item'` fallback | ntx-router.js:150-154 |
| Route object without `tag` property | Falls through to `#showSlot()` | ntx-router.js:105-106 |
| Hash route (`#settings`) | Delegates to `window.location.hash`, shows slot | ntx-router.js:85-89 |
| `#router` is null when `render()` called | Safe: optional chain `this.#router?.current` returns `undefined` (falsy) | ntx-router.js:63 |

### 3.3 NTTSidebar Error Handling

| Situation | Behavior | Location |
|-----------|----------|----------|
| No `router` attribute | All navigation silently aborted | ntx-sidebar.js:265-266 |
| Model fetch fails | `console.warn` logged, no crash | ntx-sidebar.js:221 |
| Item ref not yet loaded | Falls back to model list navigation | ntx-sidebar.js:298-301 |

### 3.4 Error Type Consistency

Error handling is ad hoc across the routing subsystem. There are no custom error types, no error events, and no error boundaries. The pattern is consistent in its approach (silent degradation) but this means **routing failures are invisible to the developer**. A misspelled router name, a missing model, or a broken component tag will all fail silently.

---

## 4. Type Safety Analysis

### 4.1 Route Data Polymorphism

Route data flowing through `NAVIGATE` is completely untyped. Three distinct shapes are treated identically:

```javascript
// Shape 1: Entity ref string
"Product/3"

// Shape 2: App route string
"@profile"

// Shape 3: Programmatic object
{ tag: 'ntx-table', attrs: { model: 'Grant' }, title: 'Grant' }

// Shape 4: Hash route string (undocumented)
"#settings"
```

**Where types are enforced**: Nowhere. Route data validation happens only at consumption time in `#mountView()` via a chain of `typeof` checks (ntx-router.js:85-107).

**Where types leak**:

1. **Router.NAVIGATE** accepts `any`. Passing `null`, `undefined`, `42`, or an array will all be accepted and stored as `#current`. The dedup check at line 46 (`data === this.#current`) means `NAVIGATE(null)` compares `null === null`, matches if already null, which prevents notification -- this is correct behavior but only by accident.

2. **JSON.stringify dedup is fragile** (Router.js:48). Two objects `{a:1, b:2}` and `{b:2, a:1}` have different JSON stringifications, so the dedup fails. This is documented in the audit at `.traces/features/improve-routing/audit.md` line 87.

3. **`#mountView` attribute setting** (ntx-router.js:128-134). Object-valued attributes are set as properties (`el[key] = val`), string-valued ones use `setAttribute`. There's no schema validation -- any attribute key from the route object is blindly applied.

4. **Title is unescaped HTML** (ntx-router.js:113). The title is interpolated directly into `innerHTML`:
   ```javascript
   <h1 class="router-title">${title}</h1>
   ```
   If route data contains a malicious `title` string (e.g. from a hash URL), this is an XSS vector. For entity refs, the title comes from `model.split('/')[0]` which is safe. For object routes, the title comes from the sidebar which constructs it from model names. But hash routes could theoretically inject HTML if `@` routes contained special characters.

### 4.2 TX Construction

TX messages are constructed ad hoc with plain objects in multiple places:

| Location | TX Construction |
|----------|----------------|
| ntx-router.js:122 | `new TX({ name: 'BACK', source: this.addr, target: this.#router.addr })` |
| ListElement.js:108 | `new TX({ name: 'NAVIGATE', source: this.addr, target: routerAddr, data: data })` |
| ntx-item.js:751-752 | `new TX({ name: 'SELECT', source: this.addr, target: target, data: this.ref })` |
| ntx-sidebar.js:283-288 | `matrix.dispatch({ name: 'NAVIGATE', source: 'sidebar', target: routerAddr, data: {...} })` |

The sidebar dispatches a plain object (not a TX instance) to `matrix.dispatch()` (ntx-sidebar.js:283-288). Matrix.inbox() wraps it in a TX at line 28 of Matrix.js, so this works, but it's inconsistent with other call sites that construct TX explicitly.

### 4.3 Observable Callback Signature

Callbacks registered via `observe('route', cb)` receive `(newValue, oldValue, property, this)` -- a 4-argument signature (Observable.js:126). However, the NTTRouter subscription at ntx-router.js:43 ignores all arguments:

```javascript
this.#routerUnsub = router.observe('route', () => this.render());
```

This is correct -- the render method reads `this.#router.current` directly. But a developer reading the observe call has no indication of the callback signature without reading Observable.js.

---

## 5. Usage Patterns in the Codebase

### 5.1 Standard Usage (examples/core/static/index.html)

```html
<ntx-sidebar router="main">
    <ntx-list model="Product" allow-create></ntx-list>
</ntx-sidebar>

<ntx-router name="main" hash>
    <ntx-list model="Product" id="product-list" allow-create></ntx-list>
</ntx-router>
```

Pattern: `router` attribute on sidebar matches `name` attribute on router. Slot content serves as home page. Hash sync enabled. This is the simplest correct usage.

### 5.2 Multi-Model Usage (examples/grants/static/index.html)

```html
<ntx-sidebar router="main">
    <ntx-list model="Grant" allow-create></ntx-list>
    <ntx-table model="Source"></ntx-table>
    <ntx-list model="AgentActor"></ntx-list>
</ntx-sidebar>

<ntx-router name="main" hash>
    <ntx-table model="Grant" id="grant-table" allow-create></ntx-table>
</ntx-router>
```

Pattern: Multiple models in sidebar, each as a different component type. Clicking a model name in the sidebar sends a programmatic route object (Shape 3) with the correct tag and attrs. The router's slot content shows the primary model.

### 5.3 Complex App with Dual Routing (apps/veille/static/index.html)

```html
<ntx-sidebar router="main">
    <ntx-table model="Source" allow-create></ntx-table>
    <ntx-list model="Grant" allow-create></ntx-list>
    <ntx-item model="Organization"></ntx-item>
</ntx-sidebar>

<ntx-router name="main">
    <ntx-run-panel id="run-panel"></ntx-run-panel>
    <div id="source-panel" style="display:none">...</div>
    <ntx-grant-analyze id="analyze-panel" style="display:none"></ntx-grant-analyze>
    <ntx-run-report id="report-panel" style="display:none"></ntx-run-report>
</ntx-router>
```

**Notable**: Hash sync is NOT enabled on the router (`<ntx-router name="main">` -- no `hash` attribute). Instead, the app implements its own hash-based routing in a `<script>` block that manually shows/hides panels by `display:none`. This is a **parallel routing system** that bypasses the Router actor entirely.

The sidebar dispatches NAVIGATE TXs to the "main" router, but the custom `handleRoute()` function (veille index.html:275-303) listens to `hashchange` separately. This creates a dual-routing conflict where:

1. Sidebar model clicks go through the Router actor -> NTTRouter renders a view
2. Hash-based panel switches (sources, analyze, report) go through the custom `handleRoute()` -> panels are shown/hidden

The NTTRouter's slot content includes ALL panels (run, source, analyze, report) visible in the slot. Only `run-panel` is visible by default; the others are `display:none`. When the Router actor has no current route, `<slot></slot>` is shown, which shows all panels -- but only `run-panel` is visible because the custom hash routing hides the others.

This works in practice but is architecturally fragile. If the Router actor ever gets a current route (e.g., from sidebar navigation), the slot content is hidden and the custom panels disappear.

### 5.4 Navigation Flow: Item Click to Detail View

The complete chain from a user click to a rendered detail view:

```
1. User clicks item card in ntx-list
   ntx-item.js:747  .card click handler fires

2. ntx-item sends SELECT TX to its select-target (parent ListElement)
   ntx-item.js:751-753  new TX({ name: 'SELECT', target: target, data: this.ref })

3. ListElement.SELECT handler receives the TX
   ListElement.js:104-109  Calls this.toggle(data), then checks for router attr

4. ListElement sends NAVIGATE TX to the router address
   ListElement.js:108  new TX({ name: 'NAVIGATE', target: routerAddr, data: data })

5. Matrix routes the TX to the Router actor
   Matrix.js:37-40  this.children.get(targetAddr).inbox(tx)

6. Router.NAVIGATE handler processes the route
   Router.js:45-54  Dedup check -> push stack -> set current -> hash -> notify

7. NTTRouter's observer callback fires
   ntx-router.js:43  router.observe('route', () => this.render())

8. NTTRouter.render() dispatches to #mountView()
   ntx-router.js:62-68  if (route) this.#mountView(route) else this.#showSlot()

9. #mountView resolves tag and creates the element
   ntx-router.js:96-98  model = routeData.split('/')[0]; tag = this.#resolveTag(model)
   ntx-router.js:127-144  createElement, set attrs, set display="lg", mount
```

### 5.5 Navigation Flow: Sidebar Model Click

```
1. User clicks model name in sidebar
   ntx-sidebar.js:468  .model-name click handler fires

2. #navigateToModel constructs route object
   ntx-sidebar.js:264-278  { tag, attrs: { model: name, ...template.attrs }, title: name }

3. Dynamic import of Matrix, then dispatch
   ntx-sidebar.js:282-289  matrix.dispatch({ name: 'NAVIGATE', ... })

4. Router.NAVIGATE processes the object route
   (same as steps 6-9 above, but #mountView takes the object path)
   ntx-router.js:101-104  tag = routeData.tag; attrs = routeData.attrs
```

---

## 6. Developer Experience Assessment

### 6.1 Intuitive Aspects

**Declarative HTML API.** The relationship between sidebar, router, and content is expressed in HTML attributes. A new developer can read the index.html and understand the structure.

**Convention-based routing.** Entity refs like `Product/3` and app routes like `@profile` use recognizable conventions. The `@` prefix for app routes is distinctive and unlikely to collide with model names.

**Slot content as home page.** Using the Web Component slot mechanism for default content is natural and aligns with web standards.

### 6.2 Surprises and Pitfalls

**S-1: The `name`/`router` attribute coupling is string-based and unvalidated.** If a sidebar has `router="main"` but the NTTRouter has `name="Main"` (capitalization mismatch), navigation silently fails. No error, no warning. The NAVIGATE TX is sent to the Matrix, which forwards to `NetworkAdapter` since no local actor has address "Main" -- likely triggering a network request to the backend for a nonexistent target.

**S-2: Hash sync is set only at Router creation time.** If NTTRouter A creates a Router with hash sync, then NTTRouter B references the same Router name (without `hash` attribute), B inherits A's hash sync behavior silently. If B is created first (without hash), and A is created second, A's `hash` attribute is ignored because `getRouter(name)` returns B's non-hash Router. This is a **configuration race condition** in the constructor at ntx-router.js:36-39:

```javascript
let router = getRouter(name);
if (!router) {
    router = new Router(name, { hash: this.hasAttribute('hash') });
}
```

**S-3: Multiple NTTRouter elements sharing one Router.** Because `getRouter(name)` returns a shared Router, two `<ntx-router name="main">` elements will both observe the same Router and both render. Both will mount views independently, potentially creating duplicate components. There is no guard against this.

**S-4: `#showSlot()` wipes the shadow DOM.** Every call to `#showSlot()` replaces the entire shadow DOM content with `<slot></slot>` (ntx-router.js:77). This means the constructable stylesheet adopted in the Component constructor is lost. The style URL getter exists (`get styles()` at line 29), and Component's constructor adopts it into `adoptedStyleSheets`, but `innerHTML = '<slot></slot>'` does not destroy adopted stylesheets -- they survive. However, any dynamically added styles in the shadow DOM would be lost.

**S-5: `#mountView()` rebuilds chrome on every navigation.** Every route change re-creates the entire shadow DOM including the back button and chrome bar. This means event listeners on the back button are re-created each time. Since there's no AbortController or cleanup, the old listeners are garbage-collected with the old DOM -- this is correct but could be more efficient.

**S-6: The sidebar's dynamic import pattern.** `import('../core/Matrix.js').then(({matrix}) => { ... })` at ntx-sidebar.js:282 is asynchronous. This means `this.close()` at line 290 executes immediately, but the NAVIGATE dispatch happens later. If the user rapidly clicks multiple items, multiple NAVIGATE TXs could be dispatched asynchronously, with close() happening before the first dispatch. In practice this works because the Router deduplicates, but the ordering is not guaranteed.

**S-7: The first NAVIGATE pushes `null` onto the stack.** When navigating from the home view (null current), `null` is pushed to the stack (Router.js:50). This means `BACK` after a single navigation returns to `null`, which NTTRouter renders as the slot content. This is correct and intentional, but a developer might not expect `null` in the stack.

### 6.3 Discoverability

**API discovery requires reading source code.** There is no JSDoc on the public methods of NTTRouter. The Router has a block comment at the top of the file but no per-method documentation. The Observable mixin's callback signature is documented only in Observable.js.

**The route data contract is implicit.** Nowhere is there a formal definition of what shapes route data can take. A developer must read `#mountView()` to discover the string prefixes (`@`, `#`) and the object shape (`{tag, attrs, title}`).

---

## 7. Naming Analysis

### 7.1 Consistency Assessment

| Name | Convention | Assessment |
|------|-----------|------------|
| `Router` / `NTTRouter` | Actor class / Component class | **Consistent** with Actor/NTTItem, Actor/NTTElement pattern |
| `NAVIGATE` / `BACK` | UPPERCASE TX handler | **Consistent** with project convention (SELECT, UPDATE, READ, etc.) |
| `current` | getter | **Clear** and standard |
| `canGoBack` | boolean getter with `can` prefix | **Clear** |
| `getRouter` | module function | **Consistent** with `get*` naming for lookups |
| `#mountView` | private method | **Descriptive** |
| `#showSlot` | private method | **Descriptive** |
| `#resolveTag` | private method | **Descriptive** |
| `#hashSync` | private field | **Clear** |
| `#fromHash` / `#toHash` | private methods | **Slightly opaque**: "from hash" means "read URL hash into state", "to hash" means "write state to URL hash" |

### 7.2 Naming Issues

**ISSUE-N1: `NTTRouter` vs `Router`.** The naming convention `NTT*` for UI components is documented (CLAUDE.md: "NTT is the core entity concept"). However, NTTRouter is not an entity component -- it's a view container. The `NTT` prefix suggests it renders an entity, but it renders arbitrary views. This is a minor semantic mismatch.

**ISSUE-N2: `render()` overloaded semantics.** In NTTRouter, `render()` means "decide what to show and rebuild the entire shadow DOM." In NTTItem/NTTElement, `render()` means "rebuild the view of the current entity data." Same name, different responsibilities. This is confusing but tolerable given the inheritance chain.

**ISSUE-N3: Sidebar method names.** `open()` conflicts mentally with `window.open()`. In practice, it just sets an attribute, so the mismatch is harmless. `toggle()` is standard DOM API naming.

**ISSUE-N4: `#navigateToModel` vs `#navigateToItem` vs `#navigateToLink`.** Three methods with parallel structure and naming. Clear and consistent.

---

## 8. Parameter Validation

### 8.1 Boundary Validation Summary

| Method | Parameter | Validated? | What happens with bad input |
|--------|-----------|------------|---------------------------|
| `Router(addr)` | `addr` | No | Empty string uses Actor's auto-generated addr |
| `Router({hash})` | `hash` | No | Any falsy value = no hash sync |
| `NAVIGATE(data)` | `data` | Dedup only | Any value accepted and stored as `#current` |
| `BACK(data)` | `data` | Not used | Parameter ignored entirely |
| `getRouter(addr)` | `addr` | No | Returns `undefined` for any non-matching key |
| `observe(prop, cb)` | `prop`, `cb` | Yes (assert) | Throws on empty string or non-function |
| `NTTRouter name attr` | string | No | Falls back to `router-{addr}` |
| Sidebar `router` attr | string | No | Navigation silently dropped if missing |
| `#mountView(routeData)` | routeData | Type-checked | Falls through to `#showSlot()` for unrecognized shapes |

### 8.2 Input That Can Sneak Through

**Bad route data.** Since `NAVIGATE` accepts anything, the following all succeed at the Router level but cause problems downstream:

```javascript
router.NAVIGATE(42);          // NTTRouter: typeof 42 !== 'string' and !42.tag → showSlot
router.NAVIGATE([1,2,3]);     // typeof [] === 'object' but no .tag → showSlot
router.NAVIGATE('');          // Empty string: identical to no-route in NTTRouter (falsy)
router.NAVIGATE(undefined);   // Router: undefined === null is false, so proceeds
router.NAVIGATE(false);       // Router: false !== null, pushes null, sets current=false
```

The `NAVIGATE(undefined)` case at Router.js:46 is notable: `undefined === this.#current` when `#current` is `null` evaluates to `false`, so the dedup check passes and `undefined` is stored as the current route. NTTRouter then checks `if (route)` at line 64 -- `undefined` is falsy, so it shows the slot. But `undefined` is now in the stack, which means `canGoBack` returns `true` and `BACK` will transition from whatever-comes-next back to `undefined` (showing slot again). This creates a phantom stack entry.

**Unregistered custom element tag.** If route data specifies `tag: 'nonexistent-component'`, `document.createElement('nonexistent-component')` creates an `HTMLUnknownElement`. No error, no warning. The element is mounted in the router content area but renders nothing. The developer must inspect the DOM to diagnose.

---

## 9. Return Value Contracts

### 9.1 Router Methods

| Method | Return | Consistency |
|--------|--------|-------------|
| `NAVIGATE` | `void` (implicit `undefined`) | **Inconsistent** with Actor convention where handlers return `TX` |
| `BACK` | `void` (implicit `undefined`) | Same as NAVIGATE |
| `current` | `string \| object \| null` | **Consistent** but polymorphic |
| `canGoBack` | `boolean` | **Consistent** |

The Router's TX handlers do not return the TX object, unlike the Actor.inbox convention where handlers return `tx`. This means the caller of `matrix.dispatch({name:'NAVIGATE', ...})` gets no feedback about whether the navigation succeeded.

### 9.2 Observable.observe Return

`observe()` returns an unsubscribe function `() => void`. This is a clean pattern and is correctly used in NTTRouter.disconnectedCallback (ntx-router.js:57). The NTTSidebar uses a slightly different pattern: it collects unsubscribe functions in `#unsubs` array and iterates on disconnect (ntx-sidebar.js:151).

### 9.3 getRouter Return

Returns `Router | undefined`. Callers must null-check. NTTRouter does this correctly at ntx-router.js:36-38. However, there is no runtime guarantee that a Router with a given name will ever be created -- the window between "sidebar sends NAVIGATE to router addr" and "NTTRouter creates the Router" could cause lost messages if the sidebar is connected before the router.

---

## 10. Lifecycle & Ordering Requirements

### 10.1 Required Initialization Sequence

```
1. Matrix singleton created (Matrix.js:81)
   └─ Actor.registerRoot(this) sets ROOT_ACTOR

2. Router(addr, {hash}) constructor
   ├─ super(addr) → Actor constructor → registers in constructor's children map
   ├─ matrix.register(this) → registers Router in Matrix.children
   ├─ If hash: window.addEventListener('hashchange', ...)
   ├─ If hash: #fromHash() → reads current URL hash
   └─ routers.set(addr, this)

3. NTTRouter connected to DOM (connectedCallback)
   ├─ super.connectedCallback() → Component lifecycle
   ├─ getRouter(name) || new Router(name, {hash})
   ├─ router.observe('route', () => this.render())
   ├─ Auto-wire router attr on [model] children
   └─ this.render()
```

**Ordering constraint**: Matrix must be created before any Router. This is guaranteed by ES module import order: Router.js imports from Matrix.js, which creates the singleton at module evaluation time.

**Ordering constraint**: NTTSidebar must have its `router` attribute match an existing or future Router name. Since the sidebar dispatches NAVIGATE via `matrix.dispatch()`, the Router must be registered in the Matrix for the message to route correctly. If the sidebar dispatches before the Router is created, Matrix.inbox routes to `this.remote.send(tx)` (Matrix.js:45), which sends the NAVIGATE message to the backend -- where it will be ignored or cause an error.

### 10.2 Cleanup Requirements

| Component | Cleanup | What happens if skipped |
|-----------|---------|----------------------|
| NTTRouter | `#routerUnsub()` in disconnectedCallback | Router observer callback references stale DOM; renders to detached shadow root |
| NTTRouter (super) | Component.disconnectedCallback stops ResizeObserver, detaches NTT, unsubscribes observable | Memory leak, stale callbacks |
| NTTSidebar | Removes 3 document/window listeners + iterates `#unsubs` | Event listener leaks on document |
| Router | **No cleanup** | hashchange listener persists; Router stays in `routers` Map forever |

**BUG: Router has no cleanup path.** There is no `destroy()`, `dispose()`, or `disconnectedCallback()` on Router. The hashchange listener added at Router.js:34 is never removed. The Router is never removed from the `routers` Map. The Router is never unregistered from Matrix.children. In a single-page app that never creates/destroys routers, this is fine. But if routers are dynamically created (e.g., in a test harness or a component that creates routers on connect and expects them cleaned up on disconnect), this is a memory leak and a source of stale callbacks.

### 10.3 Re-entrancy Concerns

`NAVIGATE` calls `notify('route', ...)` which triggers observers synchronously. If an observer calls `NAVIGATE` (e.g., a redirect), it re-enters `NAVIGATE` while the first call is still on the stack. The dedup check at line 46 will see the *new* current (set at line 51) not the one from the outer call. This could cause stack corruption:

```
Outer NAVIGATE('A'):
  stack.push(null)        → stack = [null]
  current = 'A'
  notify('route', 'A', null)
    → Observer calls NAVIGATE('B'):
        stack.push('A')   → stack = [null, 'A']
        current = 'B'
        notify('route', 'B', 'A')
  // Outer NAVIGATE returns, but current is now 'B' not 'A'
```

This is technically correct (last write wins), but the intermediate state during notification could surprise observers that expect `current` to match the value they were notified with.

---

## 11. Documentation Gaps

### 11.1 Undocumented API Surface

| Item | Status |
|------|--------|
| Route data shapes (string entity ref, `@` app route, `#` hash route, object) | Documented in file header comment of Router.js but not in any reference doc |
| Observable callback signature `(newValue, oldValue, property, instance)` | Documented only in Observable.js source |
| `NTTRouter` auto-wiring of `router` attr on `[model]` children | Not documented anywhere |
| `NTTRouter` auto-setting `display="lg"` on entity ref views | Not documented |
| `NTTSidebar` route template system (child elements as route config) | Documented in ntx-sidebar.js header comment only |
| `NTTSidebar` three entry types (model, item, link) | Documented in ntx-sidebar.js header comment only |
| `NTTSidebar.VIEW_TAGS` static property | Not documented |
| Router global registry (`routers` Map, `getRouter()`) | Not documented outside source |
| Hash route pass-through (`#settings` → `window.location.hash`) | Not documented |

### 11.2 Documented but Potentially Stale

The Router.js header comment (lines 1-16) is accurate and concise. The NTTRouter header comment (lines 1-13) is accurate. The NTTSidebar header comment (lines 1-38) is comprehensive and accurate for the current implementation. No stale documentation was found.

### 11.3 Missing Cross-Reference Documentation

There is no documentation that describes the complete navigation flow end-to-end: how a click in ntx-item becomes a SELECT TX, how ListElement forwards it as NAVIGATE, how Router processes it, and how NTTRouter renders the result. A developer must trace through 5 files to reconstruct this flow. The audit document at `.traces/features/improve-routing/audit.md` contains this flow, but it is in a development trace, not in an official doc.

### 11.4 Missing Error Documentation

None of the routing components document their failure modes. What happens when the Router name doesn't match? What happens with unknown model names? What happens with invalid route data? The answers are "silent failure" in all cases, but this is not documented.

---

## 12. Summary of Findings

### Critical Issues

1. **XSS via title interpolation** (ntx-router.js:113): Route titles are interpolated into `innerHTML` without escaping. App routes derive titles from hash content which could be user-controlled.

2. **No Router cleanup** (Router.js): Router instances are never removed from the global map or Matrix, and hashchange listeners are never removed. This prevents garbage collection and causes stale callbacks in dynamic scenarios.

### Moderate Issues

3. **Silent navigation failures**: Mismatched `name`/`router` attributes, missing models, invalid route data -- all fail silently with no diagnostic output.

4. **Race condition on Router hash configuration** (ntx-router.js:36-39): First NTTRouter to create the Router determines hash sync; later NTTRouters cannot change it.

5. **`JSON.stringify` dedup is order-dependent** (Router.js:48): Object routes with same properties in different order bypass dedup.

6. **NAVIGATE re-entrancy** during observer notification can cause unexpected intermediate states.

### Minor Issues

7. **Phantom stack entries**: `NAVIGATE(undefined)` or `NAVIGATE(false)` creates valid but meaningless stack entries.

8. **Sidebar async dispatch timing**: `close()` executes before `matrix.dispatch()` due to dynamic import Promise.

9. **No API for programmatic Router removal**: No `destroy()` or `removeRouter()` exists.

10. **Inconsistent TX construction**: Sidebar dispatches plain objects; other components construct TX instances explicitly.
