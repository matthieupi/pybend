# Router Entropy Reduction — Implementation Plan

## Context

The N3TX routing system has two layers split across packages:

| Layer | File | Package | Role |
|-------|------|---------|------|
| **Router** | `packages/n3tx-core/src/n3tx_core/static/core/Router.js` | n3tx-core | Pure state Actor + Observable. Manages `#current`, `#stack`, `#hashSync`. |
| **NTTRouter** | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js` | n3tx-ui | View container web component. Mounts/unmounts DOM based on Router state. |

### Why this refactor

The current system requires developers to hold 8 concepts (Router, NTTRouter, routers Map, Observable mixin, 3 route shapes, hash sync, SELECT/NAVIGATE double-hop, sidebar as special citizen). This refactor reduces that to 4: `<ntx-router>`, route string grammar, pure utility functions, schema `ui.renderer` resolution.

**Problems being solved:**
1. **Route data polymorphism**: Routes can be strings (`"Product/3"`), @-prefixed strings (`"@profile"`), or objects (`{tag, attrs, title}`). Each has different hash sync behavior (objects don't survive hash round-trip), different dedup logic (objects use fragile `JSON.stringify`), and different resolution code paths in NTTRouter.
2. **Wrong boundary**: Router is too thin (dumb state holder), NTTRouter is too thick (state wiring + route resolution + chrome rendering + component mounting). The intelligence should be in Router (framework-agnostic, reusable) and NTTRouter should be a thin DOM adapter (replaceable with a React equivalent).
3. **Sidebar special citizen**: NTTSidebar extends `HTMLElement` (not `Component`/`Actor`), uses async `import('../core/Matrix.js').then(...)` for TX dispatch, and constructs object route data that doesn't survive refresh.
4. **Full shadow DOM rebuild** on every navigation (chrome + content rebuilt from scratch).

### Design decisions

1. **Keep both Router and NTTRouter** — The package split is load-bearing: Router (n3tx-core) must be framework-agnostic so a future React `<NtxRouter>` can reuse the same navigation brain with a different DOM adapter.

2. **Recut the boundary** — Router becomes the COMPLETE navigation brain (state + hash sync + route parsing + route resolution). NTTRouter becomes a THIN DOM adapter (~70 lines) that reads `router.resolved` and mounts the result.

3. **All routes are strings** — One grammar: `@appName | Model[/id[/action]][?params]`. No objects. All routes survive hash round-trip. The `view=` query parameter overrides the schema's default component (e.g., `Grant?view=table` uses `ntx-table` instead of the schema default). Other query params pass through as element attributes.

4. **Resolution as pure functions, NOT Router methods** — `parseRoute()`, `buildRoute()`, and `resolveRoute()` are stateless functions exported alongside the Router class. Router calls them internally but they're independently importable and testable. A React adapter would call `resolveRoute()` with its own schema accessor.

5. **`resolveRoute()` takes a `getSchema` callback** — Default: `(model) => null` (all fallback tags). In web components context: `(model) => window.NTT?.get(model)?.schema || null`. This keeps Router zero-coupled to the NTT entity system.

6. **Observable stays, carries the route STRING** — Router notifies with `notify('route', routeString, oldRouteString)`. NTTRouter's observer callback reads `router.resolved` (which calls the pure function pipeline internally). This keeps Router schema-free while giving NTTRouter everything it needs.

7. **Router gets imperative API sugar** — `router.navigate(route)` and `router.back()` wrap the TX handlers. This eliminates the need to construct TX objects for the common case.

---

## Current State of Key Files

Before implementing, read these files to understand what exists:

### Router.js (`packages/n3tx-core/src/n3tx_core/static/core/Router.js`)
- 94 lines. Imports: `Actor`, `Observable`, `matrix`.
- Module-level: `const routers = new Map()` — parallel registry to Matrix.
- Class `Router extends Actor` with private fields: `#current = null`, `#stack = []`, `#hashSync = false`.
- Constructor: `(addr, { hash = false } = {})` — registers in Matrix and routers Map, optionally listens to `hashchange`.
- Getters: `current` (returns `#current`), `canGoBack` (returns `#stack.length > 0`).
- TX handler `NAVIGATE(data, tx)`: dedup check (string `===` and object `JSON.stringify`), push old to stack, set current, hash sync, notify.
- TX handler `BACK(data, tx)`: early return if no stack, pop, set current, hash sync, notify.
- `#toHash()`: writes `location.hash` for strings, `history.replaceState` for null, **silently skips objects**.
- `#fromHash()`: reads hash, pushes to stack if different, notifies.
- Export: `getRouter(addr)` — looks up routers Map.
- Bottom: `Actor.subclass(Router, Observable)` — applies Observable mixin.

### NTTRouter (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`)
- 159 lines. Imports: `Component`, `Router`, `getRouter`, `TX`.
- `connectedCallback()`: creates/gets Router by `name` attr, observes `'route'` with `() => this.render()`, auto-sets `router` attr on `[model]` children.
- `render()`: if `route` → `#mountView(route)`, else → `#showSlot()`.
- `#showSlot()`: removes currentView, sets `shadowRoot.innerHTML = '<slot></slot>'` — full wipe.
- `#mountView(routeData)`: BIG method with shape detection:
  - `#` prefix → set `window.location.hash`, show slot (bypass)
  - `@` prefix → `ntx-{name}` tag, capitalize for title
  - plain string → split on `/`, `#resolveTag(model)` for component, `ref` attr
  - object with `.tag` → use tag/attrs/title directly
  - Builds chrome HTML (back button + title) via `innerHTML`, creates element, sets attrs, mounts.
  - Forces `display='lg'` on ref-bearing elements.
  - Auto-sets `router` attr on mounted `[model]` elements.
- `#resolveTag(model)`: reads `window.NTT.get(model)?.schema?.ui?.renderer?.detail || .item || 'ntx-item'`.

### NTTSidebar (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js`)
- 499 lines. Extends `HTMLElement` (NOT Component/Actor).
- Scans child elements for route templates: `<ntx-table model="Grant" allow-create>` → stores `{tag: 'ntx-table', attrs: {'allow-create': ''}}` in `#routeTemplates` Map.
- Three navigation methods, all using async dynamic import:
  - `#navigateToModel(modelName)`: reads template → constructs `{tag, attrs: {model, ...templateAttrs}, title}` → `import('../core/Matrix.js').then(({matrix}) => matrix.dispatch({name:'NAVIGATE', source:'sidebar', target:routerAddr, data:objectRoute}))` → close.
  - `#navigateToItem(modelName)`: similar but includes `ref` in attrs.
  - `#navigateToLink(href)`: dispatches raw href string.
- Listens to `hashchange` for auto-close.

### Observable.js (`packages/n3tx-core/src/n3tx_core/static/core/Observable.js`)
- 134 lines. Mixin applied via `Observable.apply(Base)` which mutates prototype.
- Adds `observe(property, callback)` → returns unsubscribe function.
- Adds `notify(property, newValue, oldValue)` → calls all callbacks as `cb(newValue, oldValue, property, this)`.

### Existing schema ui.renderer declarations (Python models)
- `Product`: `'renderer': {'item': 'ntx-item', 'list': 'ntx-list'}` — already has `list`!
- `User`: `'renderer': {'item': 'ntx-user'}`
- `AgentActor`: `'renderer': {'item': 'ntx-agent', 'detail': 'ntx-agent'}`
- `Grant`: `'renderer': {'item': 'ntx-grant-item'}` — no `list`
- `Run`: `'renderer': {'item': 'ntx-run-item'}` — no `list`

### Existing test files
- **Unit**: `tests/frontend/tests/core/Router.test.js` — 17 tests covering NAVIGATE, BACK, getRouter, observers, dedup (including object routes), hash sync.
- **Integration**: `tests/frontend/tests/integration/router-navigation.test.js` — 16 tests, uses `vi.resetModules()`, covers same + matrix registration.
- **Component**: `tests/frontend/tests/components/ntx-router.test.js` — 5 tests, basic registration/shadow DOM/render.
- **E2E (Playwright)**: `tests/frontend/tests/e2e/ntx-router-unit.spec.js` — 10 test suites covering root state, detail nav, back nav, hash routing, special @routes, history, edge cases. Asserts on shadow DOM selectors: `.router-chrome`, `.router-content`, `.back-btn`, `.router-title`, `slot`.

### Test commands
```bash
cd /workspace/tests/frontend && npx vitest                                    # unit + integration
cd /workspace/tests/frontend && npx playwright test tests/e2e/ntx-router-unit.spec.js  # E2E
```

---

## Phase 1: Foundation — Pure Functions + Imperative API + Stack Cap

**Goal**: Add `parseRoute()`, `buildRoute()`, `resolveRoute()` as exported pure functions in Router.js. Add `navigate()`/`back()` sugar. Add stack cap. ALL ADDITIVE — zero changes to existing code paths.

### 1.1 Modify `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

**Add module-level constant** (before Router class):
```javascript
const STACK_MAX = 50;
```

**Add three exported pure functions** (before Router class, after imports):

**`parseRoute(route)`**:
```javascript
/**
 * Parse a route string into structured data.
 * Grammar: @appName[?params] | Model[/id[/action]][?params]
 * @param {string|null} route
 * @returns {{ type: string, app?: string, model?: string, id?: string, action?: string, params?: object } | null}
 */
export function parseRoute(route) {
    if (!route || typeof route !== 'string') return { type: 'home' };

    // App routes: @profile, @settings?tab=security
    if (route.startsWith('@')) {
        const [path, query] = route.slice(1).split('?');
        return {
            type: 'app',
            app: path,
            params: query ? Object.fromEntries(new URLSearchParams(query)) : {},
        };
    }

    // Entity routes: Model, Model/id, Model/id/action, all with optional ?params
    const [path, query] = route.split('?');
    const parts = path.split('/');
    const params = query ? Object.fromEntries(new URLSearchParams(query)) : {};
    const model = parts[0];
    const id = parts[1] || null;
    const action = parts[2] || null;

    let type = 'model';
    if (id && action) type = 'action';
    else if (id) type = 'detail';

    return { type, model, id, action, params };
}
```

**`buildRoute(parts)`**:
```javascript
/**
 * Build a route string from structured parts (inverse of parseRoute).
 * @param {{ type: string, app?: string, model?: string, id?: string, action?: string, params?: object }} parts
 * @returns {string}
 */
export function buildRoute(parts) {
    if (!parts || parts.type === 'home') return '';

    let route;
    if (parts.type === 'app') {
        route = '@' + parts.app;
    } else {
        route = parts.model || '';
        if (parts.id) route += '/' + parts.id;
        if (parts.action) route += '/' + parts.action;
    }

    const params = parts.params;
    if (params && Object.keys(params).length > 0) {
        route += '?' + new URLSearchParams(params).toString();
    }
    return route;
}
```

**`resolveRoute(parsed, getSchema)`**:
```javascript
/**
 * Resolve a parsed route to a mount instruction: { tag, attrs, title }.
 * Pure function — no side effects, no global state access.
 *
 * @param {object} parsed — output of parseRoute()
 * @param {function} [getSchema] — (modelName) => schema object or null
 * @returns {{ tag: string, attrs: object, title: string } | null}
 */
export function resolveRoute(parsed, getSchema = () => null) {
    if (!parsed || parsed.type === 'home') return null;

    const params = parsed.params || {};

    if (parsed.type === 'app') {
        return {
            tag: 'ntx-' + parsed.app,
            attrs: { ...params },
            title: parsed.app.charAt(0).toUpperCase() + parsed.app.slice(1),
        };
    }

    const schema = getSchema(parsed.model);
    const renderer = schema?.ui?.renderer || {};

    // Filter out 'view' from pass-through params
    const passthrough = {};
    for (const [k, v] of Object.entries(params)) {
        if (k !== 'view') passthrough[k] = v;
    }

    if (parsed.type === 'model') {
        // List view: view= param overrides schema default
        let tag;
        if (params.view) {
            tag = params.view.startsWith('ntx-') ? params.view : 'ntx-' + params.view;
        } else {
            tag = renderer.list || 'ntx-list';
        }
        return {
            tag,
            attrs: { model: parsed.model, ...passthrough },
            title: schema?.title || schema?.__name__ || parsed.model,
        };
    }

    if (parsed.type === 'detail') {
        const tag = renderer.detail || renderer.item || 'ntx-item';
        return {
            tag,
            attrs: { ref: parsed.model + '/' + parsed.id, display: 'lg', ...passthrough },
            title: schema?.title || schema?.__name__ || parsed.model,
        };
    }

    if (parsed.type === 'action') {
        // Action view: check schema methods for renderer hint
        const methodDef = schema?.methods?.[parsed.action];
        const tag = methodDef?.ui?.renderer
            || (methodDef?.stream ? 'ntx-stream' : null)
            || renderer.detail || renderer.item || 'ntx-item';
        return {
            tag,
            attrs: {
                ref: parsed.model + '/' + parsed.id,
                method: parsed.action,
                display: 'lg',
                ...passthrough,
            },
            title: (schema?.title || schema?.__name__ || parsed.model) + ' / ' + parsed.action,
        };
    }

    return null;
}
```

**Add imperative methods to Router class** (after BACK handler):
```javascript
/** Imperative navigate — sugar over NAVIGATE TX handler. */
navigate(route) { this.NAVIGATE(route); }

/** Imperative back — sugar over BACK TX handler. */
back() { this.BACK(); }
```

**Add stack cap** — in the `NAVIGATE` method, after `this.#stack.push(old)`, add:
```javascript
if (this.#stack.length > STACK_MAX) this.#stack.shift();
```

**Update exports** at bottom of file. The file currently just has `Actor.subclass(Router, Observable)`. The Router class and getRouter are already exported. Add the three new functions to the named exports. The final export set should be: `Router` (class), `getRouter` (function), `parseRoute` (function), `buildRoute` (function), `resolveRoute` (function).

**DO NOT change** any existing behavior of NAVIGATE, BACK, hash sync, Observable, or the routers Map. This phase is purely additive.

### 1.2 Create `tests/frontend/tests/core/route-functions.test.js`

New test file for the three pure functions. Use the same mock pattern as `Router.test.js` (mock Assert.js, config.js, Logging.js). Import `{ parseRoute, buildRoute, resolveRoute }` from `'../../core/Router.js'`.

**parseRoute tests** (one `describe` block):
- `null` → `{ type: 'home' }`
- `''` → `{ type: 'home' }`
- `'@profile'` → `{ type: 'app', app: 'profile', params: {} }`
- `'@settings?tab=security'` → `{ type: 'app', app: 'settings', params: { tab: 'security' } }`
- `'Product'` → `{ type: 'model', model: 'Product', id: null, action: null, params: {} }`
- `'Grant?view=table&allow-create='` → `{ type: 'model', model: 'Grant', ..., params: { view: 'table', 'allow-create': '' } }`
- `'Product/3'` → `{ type: 'detail', model: 'Product', id: '3', action: null, params: {} }`
- `'Grant/5/analyze'` → `{ type: 'action', model: 'Grant', id: '5', action: 'analyze', params: {} }`
- `'Product/3?expanded=true'` → `{ type: 'detail', ..., params: { expanded: 'true' } }`

**buildRoute tests** (one `describe` block):
- `{ type: 'home' }` → `''`
- `{ type: 'app', app: 'profile' }` → `'@profile'`
- `{ type: 'model', model: 'Grant', params: { view: 'table' } }` → `'Grant?view=table'`
- `{ type: 'detail', model: 'Product', id: '3' }` → `'Product/3'`
- `{ type: 'action', model: 'Grant', id: '5', action: 'analyze' }` → `'Grant/5/analyze'`

**Round-trip tests**: `parseRoute(buildRoute(x))` deep-equals `x` for representative inputs (normalize params to `{}` when empty).

**resolveRoute tests** (one `describe` block):
- `null` parsed → returns `null`
- `{ type: 'home' }` → returns `null`
- `{ type: 'app', app: 'profile', params: {} }` → `{ tag: 'ntx-profile', attrs: {}, title: 'Profile' }`
- `{ type: 'model', model: 'Product', params: {} }` with no schema → `{ tag: 'ntx-list', attrs: { model: 'Product' }, title: 'Product' }`
- `{ type: 'model', model: 'Grant', params: { view: 'table' } }` → `{ tag: 'ntx-table', attrs: { model: 'Grant' }, title: 'Grant' }` (view= override)
- `{ type: 'model', model: 'Grant', params: { view: 'table', 'allow-create': '' } }` → attrs has `model` and `allow-create` but NOT `view` (filtered out)
- `{ type: 'detail', model: 'Product', id: '3', params: {} }` with schema `{ui:{renderer:{detail:'ntx-custom'}}}` → `{ tag: 'ntx-custom', attrs: { ref: 'Product/3', display: 'lg' } }`
- `{ type: 'detail', ... }` with schema `{ui:{renderer:{item:'ntx-user'}}}` (no detail) → falls back to `ntx-user`
- `{ type: 'detail', ... }` with no schema → falls back to `ntx-item`
- `{ type: 'action', model: 'Grant', id: '5', action: 'analyze', params: {} }` with schema `{methods:{analyze:{ui:{renderer:'ntx-grant-analyze'}}}}` → tag is `ntx-grant-analyze`, attrs include `ref`, `method: 'analyze'`

### 1.3 Update `tests/frontend/tests/core/Router.test.js`

**Add** to existing `describe('NAVIGATE')` block:
- Test for stack cap: navigate 55 times (routes 'r1' through 'r55'), then BACK 55 times. Verify that after 50 BACKs, `canGoBack` is `false` (oldest 5 entries were dropped).

**Add** new `describe('navigate() / back() sugar')` block:
- `router.navigate('Product/1')` → `router.current === 'Product/1'`
- `router.navigate('A'); router.navigate('B'); router.back()` → `router.current === 'A'`
- Sugar methods trigger the same observers as TX handlers.

### 1.4 Verify

Run `cd /workspace/tests/frontend && npx vitest` — all existing tests must still pass, new tests must pass.

---

## Phase 2: Router Brain Upgrade — String-Only + Resolved Getter

**Goal**: Router stores strings only. Object routes get deprecation warning + auto-conversion. New `resolved` getter returns mount-ready data.

### 2.1 Modify `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

**Add new private field** to Router class:
```javascript
#schemaAccessor = () => null;
```

**Modify constructor** — accept optional `getSchema` in options:
```javascript
constructor(addr, { hash = false, getSchema = null } = {}) {
    super(addr);
    matrix.register(this);
    this.#hashSync = hash;
    if (getSchema) this.#schemaAccessor = getSchema;
    if (hash) {
        window.addEventListener('hashchange', () => this.#fromHash());
        this.#fromHash();
    }
    routers.set(addr, this);
}
```

**Add `resolved` getter** (after `canGoBack` getter):
```javascript
/** Fully resolved mount instruction for the current route. */
get resolved() {
    return resolveRoute(parseRoute(this.#current), this.#schemaAccessor);
}
```

**Modify `NAVIGATE(data, tx)`** — replace the entire method:
```javascript
NAVIGATE(data, tx) {
    // Backward compat: convert object routes to strings with deprecation warning
    if (typeof data === 'object' && data !== null) {
        if (data.tag) {
            console.warn('[Router] Object route data is deprecated. Use string routes via buildRoute().');
            // Best-effort conversion: extract the most meaningful string
            if (data.attrs?.ref) {
                data = String(data.attrs.ref);
            } else if (data.attrs?.model) {
                const params = {};
                const tag = data.tag;
                if (tag === 'ntx-table') params.view = 'table';
                for (const [k, v] of Object.entries(data.attrs || {})) {
                    if (k !== 'model') params[k] = v;
                }
                data = buildRoute({ type: 'model', model: data.attrs.model, params });
            } else {
                data = '@' + data.tag.replace('ntx-', '');
            }
        } else {
            return; // Unknown object shape, ignore
        }
    }

    if (typeof data !== 'string') return;
    if (data === this.#current) return;

    const old = this.#current;
    this.#stack.push(old);
    if (this.#stack.length > STACK_MAX) this.#stack.shift();
    this.#current = data;
    if (this.#hashSync) this.#toHash();
    this.notify('route', this.#current, old);
}
```

**Simplify `#toHash()`** — since `#current` is now always a string or null:
```javascript
#toHash() {
    if (this.#current) {
        location.hash = this.#current;
    } else {
        history.replaceState(null, '', location.pathname + location.search);
    }
}
```

### 2.2 Modify `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`

**Modify `connectedCallback()`** — pass `getSchema` when creating Router:
```javascript
connectedCallback() {
    super.connectedCallback();
    const name = this.getAttribute('name') || `router-${this.addr}`;
    let router = getRouter(name);
    if (!router) {
        const getSchema = (model) => window.NTT?.get(model)?.schema || null;
        router = new Router(name, {
            hash: this.hasAttribute('hash'),
            getSchema,
        });
    }
    this.#router = router;
    this.#routerUnsub = router.observe('route', () => this.render());
    this.querySelectorAll('[model]').forEach(el => {
        if (!el.hasAttribute('router')) el.setAttribute('router', name);
    });
    this.render();
}
```

**Modify `render()`** — use `resolved` instead of raw `current`:
```javascript
render() {
    const resolved = this.#router?.resolved;
    if (resolved) {
        this.#mountView(resolved);
    } else {
        this.#showSlot();
    }
}
```

**Modify `#mountView(resolved)`** — replace the ENTIRE method. It now receives `{tag, attrs, title}` directly (no more shape detection):
```javascript
/** Mount a resolved route: { tag, attrs, title } */
#mountView(resolved) {
    const { tag, attrs, title } = resolved;
    const showBack = this.#router.canGoBack;

    this.shadowRoot.innerHTML = `
        <div class="router-chrome">
            ${showBack ? '<button class="back-btn" title="Back"></button>' : ''}
            <h1 class="router-title">${title}</h1>
        </div>
        <div class="router-content"></div>
    `;

    if (showBack) {
        this.shadowRoot.querySelector('.back-btn').addEventListener('click', () => {
            this.send(new TX({ name: 'BACK', source: this.addr, target: this.#router.addr }));
        });
    }

    const el = document.createElement(tag);
    for (const [key, val] of Object.entries(attrs)) {
        if (typeof val === 'object') {
            el[key] = val;
        } else {
            el.setAttribute(key, String(val));
        }
    }
    if (el.hasAttribute('model') && !el.hasAttribute('router')) {
        el.setAttribute('router', this.#router.addr);
    }
    this.#currentView = el;
    this.shadowRoot.querySelector('.router-content').appendChild(el);
}
```

**Delete `#resolveTag(model)`** — its logic is now in `resolveRoute()`.

**Remove the hash-redirect special case** — the `routeData.startsWith('#')` branch in the old `#mountView` is gone. Hash links from sidebar will be converted to `@appRoutes` in Phase 4. During transition, if any `#`-prefixed routes arrive, they'll be treated as model routes (harmless — the `#` will be part of the model name, which won't resolve, and a default component will be shown).

### 2.3 Update tests

**`tests/frontend/tests/core/Router.test.js`**:
- Update "should handle object routes" test → verify object gets converted to string with console.warn:
  ```javascript
  it('should convert object routes to strings with deprecation warning', () => {
      const warnSpy = vi.spyOn(console, 'warn');
      router.NAVIGATE({ tag: 'ntx-profile', attrs: {}, title: 'Profile' });
      expect(router.current).toBe('@profile');
      expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('deprecated'));
      warnSpy.mockRestore();
  });
  ```
- Update "should return early if navigating to same route (object)" → test string dedup after conversion.
- Add test for `resolved` getter:
  ```javascript
  it('resolved getter returns resolveRoute output', () => {
      router.NAVIGATE('Product/3');
      const r = router.resolved;
      expect(r.tag).toBe('ntx-item');  // no schema → default
      expect(r.attrs.ref).toBe('Product/3');
  });
  ```

**`tests/frontend/tests/integration/router-navigation.test.js`**:
- Update "object route data is supported" → verify string conversion.
- Update "duplicate object route data is detected via JSON.stringify" → verify string dedup.

### 2.4 Verify

Run vitest and E2E tests. All should pass — object routes are auto-converted, same components get mounted.

---

## Phase 3: NTTRouter Thinning — Persistent Chrome, Clean Mounting

**Goal**: NTTRouter becomes ~70 lines. Chrome rendered once in `prerender()`, updated in-place on navigation. No more full shadow DOM rebuild.

### 3.1 Rewrite `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`

The ENTIRE file content should be replaced. The new NTTRouter:

```javascript
/**
 * NTTRouter — Thin view container ("mini browser").
 *
 * Mounts components based on Router.resolved output.
 * Chrome (back button, title) rendered once, updated in-place.
 *
 * Attributes:
 *   name  — Router actor address (required for addressing)
 *   hash  — Enable hash sync (presence = true)
 */
import { Component } from '../core/Component.js';
import { Router, getRouter } from '../core/Router.js';
import TX from '../core/TX.js';

export class NTTRouter extends Component {

    #router = null;
    #routerUnsub = null;
    #currentView = null;

    constructor() {
        super({});
    }

    get styles() { return new URL('./ntx-router.css', import.meta.url).href; }

    prerender() {
        this.shadowRoot.innerHTML = `
            <div class="router-chrome" hidden>
                <button class="back-btn" title="Back"></button>
                <h1 class="router-title"></h1>
            </div>
            <div class="router-content"><slot></slot></div>
        `;
        // Wire back button once — persists across navigations
        this.shadowRoot.querySelector('.back-btn').addEventListener('click', () => {
            if (this.#router) {
                this.send(new TX({ name: 'BACK', source: this.addr, target: this.#router.addr }));
            }
        });
    }

    connectedCallback() {
        super.connectedCallback();

        const name = this.getAttribute('name') || `router-${this.addr}`;
        let router = getRouter(name);
        if (!router) {
            const getSchema = (model) => window.NTT?.get(model)?.schema || null;
            router = new Router(name, {
                hash: this.hasAttribute('hash'),
                getSchema,
            });
        }
        this.#router = router;
        this.#routerUnsub = router.observe('route', () => this.render());

        // Auto-configure router attr on slot children
        this.querySelectorAll('[model]').forEach(el => {
            if (!el.hasAttribute('router')) el.setAttribute('router', name);
        });

        this.render();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        this.#routerUnsub?.();
    }

    render() {
        const resolved = this.#router?.resolved;
        const chrome = this.shadowRoot.querySelector('.router-chrome');
        const content = this.shadowRoot.querySelector('.router-content');
        if (!chrome || !content) return;  // prerender not called yet

        if (!resolved) {
            // Home state: hide chrome, show slot, remove any mounted view
            chrome.hidden = true;
            if (this.#currentView) {
                this.#currentView.remove();
                this.#currentView = null;
            }
            if (!content.querySelector('slot')) {
                content.innerHTML = '<slot></slot>';
            }
            return;
        }

        // Navigation state: show chrome, mount component
        chrome.hidden = false;
        chrome.querySelector('.router-title').textContent = resolved.title;
        chrome.querySelector('.back-btn').hidden = !this.#router.canGoBack;

        // Remove slot and previous view
        const slot = content.querySelector('slot');
        if (slot) slot.remove();
        if (this.#currentView) this.#currentView.remove();

        // Check for unregistered custom element
        if (!customElements.get(resolved.tag)) {
            console.warn(`[ntx-router] Unknown element <${resolved.tag}>. Is the component imported?`);
        }

        // Create and mount
        const el = document.createElement(resolved.tag);
        for (const [key, val] of Object.entries(resolved.attrs)) {
            if (typeof val === 'object') {
                el[key] = val;
            } else {
                el.setAttribute(key, String(val));
            }
        }
        if (el.hasAttribute('model') && !el.hasAttribute('router')) {
            el.setAttribute('router', this.#router.addr);
        }
        this.#currentView = el;
        content.appendChild(el);
    }
}

customElements.define('ntx-router', NTTRouter);
```

**Key changes from current file**:
- `prerender()` creates persistent chrome + content structure (called once by Component base class from connectedCallback before render)
- `render()` is a single method that updates in-place: shows/hides chrome, updates title and back button visibility, swaps content
- No `#showSlot()`, `#mountView()`, or `#resolveTag()` — all deleted
- Back button wired ONCE in prerender, not re-created each navigation
- Unknown element warning added
- `shadowRoot.innerHTML` is only set ONCE (in prerender), not on every navigation

### 3.2 Update tests

**`tests/frontend/tests/components/ntx-router.test.js`** — update existing tests:
- "should show slot when no route" → verify via `content.querySelector('slot')` presence and `chrome.hidden === true`
- Add: prerender creates `.router-chrome` and `.router-content` structure
- Add: unknown element tag logs warning (spy on console.warn)

**E2E tests** (`tests/frontend/tests/e2e/ntx-router-unit.spec.js`):
- Should pass unchanged — same CSS classes (`.router-chrome`, `.router-content`, `.back-btn`, `.router-title`), same `slot` behavior.
- The E2E test "at root, router shows slot content" checks `hasSlot` and `!hasRouterContent`. With persistent chrome, `.router-content` always exists (it contains the slot). Update assertion: instead of `hasRouterContent: false`, check that `.router-content` contains a `slot` element and chrome is hidden.

### 3.3 Verify

Run vitest and E2E tests. The E2E test for root state may need the assertion update described above.

---

## Phase 4: Sidebar Simplification — String Routes + Static Import

**Goal**: Sidebar emits string routes via `buildRoute()`. Static Matrix import (synchronous dispatch). Hash links become @appRoutes.

### 4.1 Modify `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js`

**Add imports** at top of file (after existing `import { NTT } from '../core/NTT.js'`):
```javascript
import { matrix } from '../core/Matrix.js';
import { buildRoute } from '../core/Router.js';
```

**Replace `#navigateToModel(modelName)`** (currently lines 264-291):
```javascript
#navigateToModel(modelName) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    const template = this.#routeTemplates.get(modelName);
    const params = {};

    if (template) {
        // Map template tag to view= param
        if (template.tag === 'ntx-table') params.view = 'table';
        else if (template.tag !== 'ntx-list') params.view = template.tag.replace('ntx-', '');
        // Forward template attrs as query params
        for (const [k, v] of Object.entries(template.attrs)) {
            params[k] = v;
        }
    } else {
        // Legacy: view attribute on sidebar element
        const view = this.getAttribute('view') || 'grid';
        if (view === 'table') params.view = 'table';
        params['allow-create'] = '';
    }

    const route = buildRoute({
        type: 'model',
        model: modelName,
        params: Object.keys(params).length > 0 ? params : undefined,
    });

    matrix.dispatch({
        name: 'NAVIGATE',
        source: 'sidebar',
        target: routerAddr,
        data: route,
    });
    this.close();
}
```

**Replace `#navigateToItem(modelName)`** (currently lines 293-322):
```javascript
#navigateToItem(modelName) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    const itemRef = this.#itemRefs[modelName];
    if (!itemRef) {
        this.#navigateToModel(modelName);
        return;
    }

    // itemRef is already "Model/id" — a valid route string
    matrix.dispatch({
        name: 'NAVIGATE',
        source: 'sidebar',
        target: routerAddr,
        data: itemRef,
    });
    this.close();
}
```

**Replace `#navigateToLink(href)`** (currently lines 324-337):
```javascript
#navigateToLink(href) {
    const routerAddr = this.getAttribute('router');
    if (!routerAddr) return;

    // Convert hash links to @appRoutes
    const route = href.startsWith('#') ? '@' + href.slice(1) : href;

    matrix.dispatch({
        name: 'NAVIGATE',
        source: 'sidebar',
        target: routerAddr,
        data: route,
    });
    this.close();
}
```

**Remove** all three `import('../core/Matrix.js').then(({matrix}) => { ... })` patterns. They're replaced by the static import at the top and synchronous `matrix.dispatch()` calls above.

### 4.2 Update tests

**Sidebar tests** (`tests/frontend/tests/components/ntx-sidebar.test.js` if it exists):
- Update any assertions on NAVIGATE dispatch data from object shapes to string shapes.
- Verify: `#navigateToModel('Grant')` with template `<ntx-table model="Grant" allow-create>` dispatches `'Grant?view=table&allow-create='`.
- Verify: `#navigateToItem('Organization')` with `#itemRefs = {'Organization': 'Organization/1'}` dispatches `'Organization/1'`.
- Verify: `#navigateToLink('#settings')` dispatches `'@settings'`.

### 4.3 Verify

Run vitest and E2E. Sidebar navigation should produce the same components with the same attributes, but routes are now strings that get hash-synced (sidebar navigation becomes bookmarkable).

---

## Phase 5: Test Consolidation + Cleanup

**Goal**: Remove object-route code paths and tests. Full test pass. Clean up.

### 5.1 Modify `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

**Remove object-route deprecation code** from NAVIGATE — after Phase 4, nothing sends objects anymore. The NAVIGATE handler simplifies to:
```javascript
NAVIGATE(data, tx) {
    if (typeof data !== 'string' || !data) return;
    if (data === this.#current) return;
    const old = this.#current;
    this.#stack.push(old);
    if (this.#stack.length > STACK_MAX) this.#stack.shift();
    this.#current = data;
    if (this.#hashSync) this.#toHash();
    this.notify('route', this.#current, old);
}
```

### 5.2 Update test files

**`tests/frontend/tests/core/Router.test.js`**:
- Remove: "should convert object routes to strings with deprecation warning" (Phase 2 test — deprecation code is now gone)
- Remove: "should return early if navigating to same route (object)" — no more objects
- Keep: all string route tests, stack cap test, sugar method tests
- Add: verify non-string data is silently ignored

**`tests/frontend/tests/integration/router-navigation.test.js`**:
- Remove: "object route data is supported" test
- Remove: "duplicate object route data is detected via JSON.stringify" test
- Add: full flow test — sidebar-style `buildRoute` → Router NAVIGATE → `router.resolved` → verify correct `{tag, attrs, title}`
- Add: `'Grant?view=table'` → resolves to `{tag: 'ntx-table', attrs: {model: 'Grant'}, ...}`
- Add: `'@profile'` → resolves to `{tag: 'ntx-profile', ...}`

**`tests/frontend/tests/core/route-functions.test.js`**:
- Add edge cases if not already covered: model names with numbers, empty query string (`Model?`), params with encoded characters

**E2E tests**: verify full suite passes. No changes expected.

### 5.3 Final verify

```bash
cd /workspace/tests/frontend && npx vitest           # all unit + integration
cd /workspace/tests/frontend && npx playwright test   # all E2E
```

---

## Files Modified (Summary)

| File | Phase | Change |
|------|-------|--------|
| `packages/n3tx-core/src/n3tx_core/static/core/Router.js` | 1,2,5 | Add pure functions, imperative API, stack cap, getSchema, resolved getter, string-only NAVIGATE |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js` | 2,3 | Pass getSchema, use resolved, rewrite to thin adapter with persistent chrome |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js` | 4 | Static imports, string routes via buildRoute, hash→@app conversion |
| `tests/frontend/tests/core/route-functions.test.js` | 1 | NEW — parseRoute, buildRoute, resolveRoute tests |
| `tests/frontend/tests/core/Router.test.js` | 1,2,5 | Add sugar/cap tests, update object tests, final cleanup |
| `tests/frontend/tests/integration/router-navigation.test.js` | 2,5 | Update object tests, add flow tests |
| `tests/frontend/tests/components/ntx-router.test.js` | 3 | Update for persistent chrome, add unknown element test |

## Files NOT Modified

- `packages/n3tx-core/src/n3tx_core/static/core/Actor.js` — untouched
- `packages/n3tx-core/src/n3tx_core/static/core/Observable.js` — untouched
- `packages/n3tx-core/src/n3tx_core/static/core/Matrix.js` — untouched
- `packages/n3tx-core/src/n3tx_core/static/core/Component.js` — untouched
- `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js` — already sends string routes
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` — SELECT flow unchanged
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.css` — CSS classes preserved
- Any Python model files — no changes needed (existing `ui.renderer` declarations work as-is)
- `apps/veille/static/index.html` — dual routing untouched (separate concern for later)

## Risks

1. **E2E root state assertion**: The persistent chrome changes the shadow DOM structure slightly (`.router-content` always exists, contains `<slot>`). E2E test "at root, router shows slot content" checks `hasRouterContent: false` — this will need updating to check slot presence instead.

2. **Query params in hash**: `#Grant?view=table` is valid per URL spec (the `?` is part of the fragment). Router's `#fromHash()` will pass `Grant?view=table` to `parseRoute()`. Verify this works correctly.

3. **Template attr encoding**: Sidebar template `<ntx-table model="Grant" allow-create>` has `allow-create=""`. This becomes `Grant?view=table&allow-create=` in the route string. URLSearchParams will encode/decode this correctly, and `resolveRoute` passes it through as an attribute.
