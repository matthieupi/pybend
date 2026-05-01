# Hypermedia Route Grammar Regression Testing Plan

## 0. Purpose

This artifact defines the complete regression test strategy for the hypermedia route grammar refactor described in:

```text
.project/plans/6-hypermedia-representation-architecture-plan.md
```

The goal is not merely to add a few happy-path tests. The goal is to protect every architectural invariant before, during, and after the refactor:

```text
/{tablename}/...       legacy/current data API
/{ClassName}/...       class-name schema + mirrored model API grammar
/{ClassName}/@...      server HTML/view entrypoints
#{ClassName}/@...      frontend hash-router view routes during migration
```

This document is intentionally exhaustive. It is written so an implementer can add the tests before and during the refactor and know exactly what must pass to avoid regressions.

---

## 1. Testing Philosophy

### 1.1 Non-negotiable invariants

Every test added for this refactor should defend at least one of these invariants:

1. Existing table-name routes continue working exactly as before.
2. Existing schema routes continue working exactly as before.
3. Existing hash-router routes continue working exactly as before.
4. `@` inside a model route means view/html, never method/action or id.
5. Root `@profile` style app routes remain app routes.
6. `@view` resolves through `schema.ui.renderer[view]` before fallback.
7. `Model/id/action` remains a method/action route.
8. `Model/id/@action` is a view route, not a method route.
9. Class-name instance mirrors return the same entity data as table-name reads.
10. `$id` remains table-name based in the first migration waves.
11. HTML view routes return HTML, not JSON.
12. Direct routes and actor routes remain behaviorally equivalent once actor parity lands.
13. Hash refresh/deep-link behavior remains intact.
14. Route registration order prevents `@` segments from being captured as IDs.

### 1.2 Required test layers

The refactor crosses multiple layers. It must not be tested at only one layer.

```text
Pure route functions       -> parse/build/resolve exact behavior
Router actor state         -> NAVIGATE/BACK/hash sync/current/resolved
Router component           -> DOM mounting and slot/chrome behavior
Sidebar/link integration   -> generated links and selected states
Direct backend routes      -> FastAPI Level 1/2 behavior
Actor backend routes       -> NetworkAPI Level 3 behavior
SSR/HTML helpers           -> view shell output and content type
Example apps               -> real model registration and backwards compatibility
E2E browser flows          -> user-visible navigation/refresh behavior
```

---

## 2. Current Coverage Audit

### 2.1 Frontend route function coverage

Current files:

```text
tests/frontend/tests/core/route-functions.test.js
tests/frontend/tests/core/Router.test.js
tests/frontend/tests/integration/router-navigation.test.js
tests/frontend/tests/components/ntx-router.test.js
```

Currently covered:

- `parseRoute(null | '' | undefined | non-string)` -> home
- root app route parsing: `@profile`, `@settings?tab=security`
- model route parsing: `Product`
- detail route parsing: `Product/3`
- action route parsing: `Grant/5/analyze`
- query params on model/detail/action routes
- `buildRoute()` for home/app/model/detail/action
- basic parse/build round-trip for legacy routes
- `resolveRoute()` for app/model/detail/action
- `view=` query override for model routes
- filtering `view` from pass-through attrs
- schema renderer lookup for `list`, `detail`, `item`, method renderer, streaming method
- `Router.NAVIGATE`, `BACK`, stack, duplicate nav, hash sync, initial hash load
- `ntx-router` slot/home behavior and basic deep-link mount

Current gaps for the new architecture:

- no tests for `Model/@`
- no tests for `Model/@view`
- no tests for `Model/id/@`
- no tests for `Model/id/@view`
- no tests for differentiating `Model/id/action` from `Model/id/@action`
- no tests for root app `@profile` remaining distinct from model `Model/@view`
- no tests for `@` route normalization with leading/trailing slashes
- no tests for build/parse round-trip of view routes
- no tests for `@view` resolving through `schema.ui.renderer[view]`
- no tests for view fallback ordering
- no tests for default collection view route (`Model/@`) resolving to page/list fallback
- no tests for default member view route (`Model/id/@`) resolving to detail/item fallback
- no tests ensuring `view` and `isViewRoute` are not passed through as DOM attrs
- no tests for hash sync with `#Model/@view`
- no tests for `ntx-router` mounting the resolved tag for `@` routes

### 2.2 Sidebar/link coverage

Current files:

```text
tests/frontend/tests/components/ntx-sidebar.test.js
tests/frontend/tests/components/ntx-sidebar-link-item.test.js
```

Currently covered:

- model list parsing
- route-template derivation
- route-template dropdown fallback for `ntx-table`
- selected state for `#Product`
- selected app links for `#@settings`
- bare `href="#"` maps to router home
- sidebar record links render `href="#Grant/5"`

Current gaps for the new architecture:

- no test for selected model state when hash is `#Product/@`
- no test for selected model state when hash is `#Product/@table`
- no test for selected model state when hash is `#Product/3/@`
- no test for selected model state when hash is `#Product/3/@item`
- no test for future migrated sidebar links rendering `#Model/@` instead of `#Model`
- no test for future sidebar record links rendering `#Model/id/@` instead of `#Model/id`
- no test that app links `#settings` still map to `@settings`, not model-view routes
- no test that `href="#"` still maps to home after `@` grammar lands

### 2.3 Direct backend route coverage

Current files:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
examples/core/tests/*.py
```

Current direct unit coverage is mostly helper-level:

- `_get_user()`
- `_build_context()`
- `_serialize()`
- `_resolve_user()`
- `register_route()`

Example coverage protects current table-name API behavior:

- schema endpoints
- products CRUD
- comments CRUD
- collection routes
- pagination
- custom methods
- auth/authorization
- protected fields
- FK hydration

Current gaps for the new architecture:

- no direct route-generation test asserting `/ClassName/{id:int}` mirrors exist
- no direct test that `/ClassName/{id:int}` returns same payload as `/tablename/{id:int}`
- no direct test that `$id` remains table-name based when fetched through `/ClassName/{id:int}`
- no direct route-generation test for `/ClassName/@` HTML routes
- no direct route-generation test for `/ClassName/@{view}` HTML routes
- no direct route-generation test for `/ClassName/{id:int}/@` HTML routes
- no direct route-generation test for `/ClassName/{id:int}/@{view}` HTML routes
- no direct test that `/ClassName/@table` is not captured by `/ClassName/{id:int}`
- no direct test that HTML routes are hidden from OpenAPI if that is the chosen contract
- no direct test that legacy `/tablename` routes are unchanged after class-name routes are added

### 2.4 Actor backend route coverage

Current files:

```text
packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
examples/actors/tests/*.py
```

Currently covered:

- NetworkAPI init/helper behavior
- schema route generation: `/MockModel`
- CRUD route generation: `/mock_models`, `/mock_models/{id:int}`
- custom method route generation: `/mock_models/{id:int}/custom`
- join/parent-child path structure
- schema route through adapter
- create/list/get/update/delete route TX dispatch
- custom method dispatch
- examples/actors parity with core app behavior

Current gaps for the new architecture:

- no actor route-generation test for `/MockModel/{id:int}` class-name mirror
- no actor route-generation test for `/MockModel/@` and view routes
- no actor route TX test for class-name read mirror dispatching `get` to table-name actor address
- no actor route test ensuring class-name read mirror preserves auth meta/user handling
- no actor route test that `$id` remains table-name based through class-name mirror
- no actor route test that `/MockModel/@table` cannot be confused with an ID
- no actor/direct parity test for the new grammar

### 2.5 SSR/HTML coverage

Current files:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_ssr.py
```

Currently covered:

- SSR off/root/index behavior
- schema injection mode
- bundle mode
- full mode
- schema tags validity
- content type for existing SSR shell
- bundle CSS/module transformations

Current gaps for the new architecture:

- no tests for a model-specific HTML view helper
- no tests for collection view HTML shell output
- no tests for member view HTML shell output
- no tests that HTML view shell embeds the expected model/ref/view/component
- no tests for default view fallback in generated HTML
- no tests for named view lookup in generated HTML
- no tests that `/ClassName/@` returns `text/html`
- no tests that `/ClassName/@table` returns `text/html`
- no tests that `/ClassName/{id}/@` returns `text/html`
- no tests that `/ClassName/{id}/@item` returns `text/html`
- no tests preserving `/` and `/index.html` SSR behavior after adding model HTML routes

---

## 3. Required Frontend Tests

### 3.1 `parseRoute()` exhaustive matrix

File:

```text
tests/frontend/tests/core/route-functions.test.js
```

Add a new describe block:

```js
describe('parseRoute(route) — @ view grammar', () => { ... })
```

Required cases:

| Input | Expected |
|---|---|
| `Product/@` | `{ type: 'model', model: 'Product', view: null, isViewRoute: true, params: {} }` |
| `Product/@list` | `{ type: 'model', model: 'Product', view: 'list', isViewRoute: true, params: {} }` |
| `Product/@table` | `{ type: 'model', model: 'Product', view: 'table', isViewRoute: true, params: {} }` |
| `Product/@custom-component` | `{ type: 'model', model: 'Product', view: 'custom-component', isViewRoute: true, params: {} }` |
| `Product/@table?limit=10&offset=20` | model view route with params preserved |
| `Product/3/@` | detail view route, `view: null` |
| `Product/3/@item` | detail view route, `view: 'item'` |
| `Product/3/@detail` | detail view route, `view: 'detail'` |
| `Product/3/@chat?thread=abc` | detail view route with params preserved |
| `Product/3/run` | action route, not view route |
| `Product/3/@run` | detail view route, not action route |
| `@profile` | app route unchanged |
| `@settings?tab=security` | app route unchanged |
| `/Product/@table/` | normalized to model view route |
| `/Product/3/@item/` | normalized to detail view route |

Important assertions:

```js
expect(parseRoute('Product/3/run').type).toBe('action');
expect(parseRoute('Product/3/@run').type).toBe('detail');
expect(parseRoute('Product/3/@run').isViewRoute).toBe(true);
expect(parseRoute('@profile').type).toBe('app');
```

### 3.2 `buildRoute()` exhaustive matrix

File:

```text
tests/frontend/tests/core/route-functions.test.js
```

Add cases:

| Parts | Expected route |
|---|---|
| `{ type: 'model', model: 'Product', isViewRoute: true }` | `Product/@` |
| `{ type: 'model', model: 'Product', isViewRoute: true, view: 'table' }` | `Product/@table` |
| `{ type: 'model', model: 'Product', isViewRoute: true, view: 'table', params: { limit: '10' } }` | `Product/@table?limit=10` |
| `{ type: 'detail', model: 'Product', id: '3', isViewRoute: true }` | `Product/3/@` |
| `{ type: 'detail', model: 'Product', id: '3', isViewRoute: true, view: 'item' }` | `Product/3/@item` |
| `{ type: 'detail', model: 'Product', id: '3', action: 'run' }` | still `Product/3/run` |
| `{ type: 'app', app: 'profile' }` | still `@profile` |

### 3.3 parse/build round-trip tests

File:

```text
tests/frontend/tests/core/route-functions.test.js
```

Add these to the round-trip matrix:

```js
const cases = [
  'Product/@',
  'Product/@list',
  'Product/@table?limit=10&offset=20',
  'Product/3/@',
  'Product/3/@item',
  'Product/3/@chat?thread=abc',
  'Product/3/@run',
];
```

Also add normalization tests where exact round-trip is not expected but semantic parse is expected:

```js
expect(buildRoute(parseRoute('/Product/@table/'))).toBe('Product/@table');
```

### 3.4 `resolveRoute()` collection view tests

File:

```text
tests/frontend/tests/core/route-functions.test.js
```

Add cases:

1. `Product/@` uses `renderer.page` before `renderer.list`.
2. `Product/@` falls back to `renderer.list` when no `page`.
3. `Product/@` falls back to `ntx-list` when no schema renderer.
4. `Product/@list` uses `renderer.list`.
5. `Product/@table` uses `renderer.table`.
6. `Product/@table` falls back to `ntx-table` when schema has no table renderer.
7. `Product/@custom` uses `renderer.custom` when declared.
8. `Product/@custom` falls back to `ntx-custom` if fallback remains allowed.
9. Params pass through except internal route params.
10. `view`, `isViewRoute`, and route internals are not emitted as attrs.

Representative assertions:

```js
const schema = { ui: { renderer: { page: 'ntx-products-page', list: 'ntx-products' } } };
const r = resolveRoute(parseRoute('Product/@'), () => schema);
expect(r.tag).toBe('ntx-products-page');
expect(r.attrs).toEqual({ model: 'Product' });
```

```js
const schema = { ui: { renderer: { table: 'ntx-product-table' } } };
const r = resolveRoute(parseRoute('Product/@table?limit=10'), () => schema);
expect(r.tag).toBe('ntx-product-table');
expect(r.attrs).toEqual({ model: 'Product', limit: '10' });
```

### 3.5 `resolveRoute()` member view tests

File:

```text
tests/frontend/tests/core/route-functions.test.js
```

Add cases:

1. `Product/3/@` uses `renderer.detail` before `renderer.item`.
2. `Product/3/@` falls back to `renderer.item`.
3. `Product/3/@` falls back to `ntx-item`.
4. `Product/3/@item` uses `renderer.item`.
5. `Product/3/@detail` uses `renderer.detail`.
6. `Product/3/@chat` uses `renderer.chat`.
7. `Product/3/@chat` falls back to `ntx-chat` if fallback is allowed.
8. `Product/3/@run` resolves a view tag, not method/action attrs.
9. `Product/3/run` still resolves action route with `method: 'run'`.
10. Params pass through except internal route params.

Representative assertions:

```js
const schema = { ui: { renderer: { detail: 'ntx-product-detail', item: 'ntx-product-card' } } };
const r = resolveRoute(parseRoute('Product/3/@'), () => schema);
expect(r.tag).toBe('ntx-product-detail');
expect(r.attrs).toEqual({ ref: 'Product/3', display: 'lg' });
expect(r.attrs.method).toBeUndefined();
```

```js
const action = resolveRoute(parseRoute('Product/3/run'), () => ({ methods: { run: {} } }));
expect(action.attrs.method).toBe('run');

const view = resolveRoute(parseRoute('Product/3/@run'), () => ({ ui: { renderer: { run: 'ntx-run-view' } } }));
expect(view.tag).toBe('ntx-run-view');
expect(view.attrs.method).toBeUndefined();
```

### 3.6 Router actor hash-sync tests

File:

```text
tests/frontend/tests/core/Router.test.js
```

Add cases:

1. `NAVIGATE('Product/@table')` sets `window.location.hash` to `#Product/@table`.
2. `NAVIGATE('Product/3/@item')` sets `#Product/3/@item`.
3. initial load from `#Product/@table` sets `router.current` without fake back history.
4. initial load from `#Product/3/@item` sets `router.current` without fake back history.
5. returning to root from a view route clears current and back state.
6. duplicate navigate to same view route is no-op.
7. reset navigate to `Product/@` clears prior history.
8. `router.resolved` for `Product/@table` returns correct tag/attrs.
9. `router.resolved` for `Product/3/@item` returns correct tag/attrs.

### 3.7 Router integration tests

File:

```text
tests/frontend/tests/integration/router-navigation.test.js
```

Add full flow cases:

1. `buildRoute()` -> `NAVIGATE()` -> `parseRoute()` -> `resolveRoute()` for `Product/@table`.
2. Same for `Product/3/@item`.
3. `BACK()` correctly steps through `Product/@table` and `Product/3/@item` routes.
4. hash sync preserves `#Product/@table` exactly.
5. root app route `@profile` remains unaffected.

### 3.8 `ntx-router` DOM tests

File:

```text
tests/frontend/tests/components/ntx-router.test.js
```

Add cases:

1. Deep-link `#Product/@table` mounts `<ntx-table model="Product">`.
2. Deep-link `#Product/3/@item` mounts schema renderer item tag or fallback `<ntx-item ref="Product/3">`.
3. Home route still shows slot and removes mounted view.
4. Router chrome remains hidden on initial deep-link with no back history.
5. Navigating from home to `Product/@` removes slot and mounts view.
6. Navigating back to home restores slot.
7. Mounted collection view receives `router` attr when it has `model`.
8. Mounted member view does not accidentally receive `method` attr for `@view` route.

### 3.9 Sidebar and link tests

Files:

```text
tests/frontend/tests/components/ntx-sidebar.test.js
tests/frontend/tests/components/ntx-sidebar-link-item.test.js
```

Add cases now if behavior changes; otherwise add as migration-phase tests when sidebar links switch to explicit `@` defaults.

Required eventual cases:

1. `#Product/@` marks Product section selected.
2. `#Product/@table` marks Product section selected.
3. `#Product/3/@` marks Product section selected.
4. `#Product/3/@item` marks Product section selected.
5. `#@settings` still marks only the app link selected.
6. bare `#` home link still dispatches `NAVIGATE` with empty data.
7. migrated model header links render `href="#Product/@"`.
8. migrated sidebar record links render `href="#Grant/5/@"`.
9. legacy record links `#Grant/5` remain supported until migration flag flips.

---

## 4. Required Direct Backend Tests

### 4.1 Route generation tests for direct FastAPI routes

File:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

The current direct unit file does not exercise `register_routes()` route generation deeply. Add either:

1. a new class in `test_routes.py`, or
2. a new file `test_route_generation.py`.

Required route presence tests:

```text
/MockModel                         schema
/mock_models                       table list/create
/mock_models/{id:int}              table get/update/delete
/MockModel/{id:int}                class-name read mirror
/MockModel/@                       collection default HTML
/MockModel/@{view}                 collection named HTML
/MockModel/{id:int}/@              member default HTML
/MockModel/{id:int}/@{view}        member named HTML
```

Also assert table-name routes still exist exactly as before.

### 4.2 Direct route behavior tests: class-name read mirror

File options:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
examples/core/tests/test_class_name_routes.py
```

Use `examples/core` for end-to-end behavior with real storage, because it best protects actual app behavior.

Required cases:

1. `GET /Product/{id}` returns `200` for existing product.
2. `GET /Product/{id}` response JSON equals `GET /products/{id}` except for any expected debug envelope differences.
3. `$id` remains table-name based: ends with `/products/{id}`.
4. `$schema` remains class-name based: ends with `/Product`.
5. `GET /Product/999999` mirrors table-name 404 behavior.
6. auth behavior mirrors table-name route for protected models.
7. query params like `populate` and `depth` are preserved if supported by the table-name route.
8. invalid id path, e.g. `/Product/not-an-int`, returns validation error and does not fall through to view route.

### 4.3 Direct route behavior tests: HTML routes

Required cases:

1. `GET /Product/@` returns `200` and `content-type` contains `text/html`.
2. `GET /Product/@list` returns HTML and embeds/mounts the expected list renderer.
3. `GET /Product/@table` returns HTML and embeds/mounts the expected table renderer.
4. `GET /Product/{id}/@` returns HTML and embeds/mounts default detail renderer.
5. `GET /Product/{id}/@item` returns HTML and embeds/mounts item renderer.
6. `GET /Product/@unknown` behavior is explicit: either fallback component or 404. The expected behavior must be documented and tested.
7. `GET /Product/{id}/@unknown` same explicit behavior.
8. `GET /Product/@table` does not return JSON.
9. `GET /Product/@table` is not included in OpenAPI if `include_in_schema=False` is chosen.
10. `GET /Product/@` does not break `GET /Product` schema endpoint.

### 4.4 Direct route registration order tests

These tests prevent the most dangerous regression: `@table` being parsed as an ID.

Required cases:

1. `/Product/@table` hits HTML route, not item route.
2. `/Product/@` hits HTML route, not schema route.
3. `/Product/1/@item` hits member HTML route, not method route.
4. `/Product/1/run` still hits method route if method exists.
5. `/Product/1/@run` hits view route, not method route.
6. `/products/1/run` legacy method route remains unchanged.

### 4.5 Direct route compatibility tests

In `examples/core/tests`, add a compatibility test file that snapshots the legacy API behavior around this refactor.

Required cases:

1. `GET /Product` still returns schema.
2. `GET /products` still returns paginated collection.
3. `POST /products` still creates.
4. `GET /products/{id}` still reads.
5. `PUT /products/{id}` still updates.
6. `DELETE /products/{id}` still deletes.
7. custom method endpoints under `/products/{id}/...` still work.
8. collection/join routes like `/products/{id}/comments` still work.

---

## 5. Required Actor Backend Tests

### 5.1 Route generation tests

File:

```text
packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
```

Add to `TestCreateAPIRoutesRouteGeneration`:

```text
assert '/MockModel/{id:int}' in routes
assert '/MockModel/@' in routes
assert '/MockModel/@{view}' in routes or exact FastAPI path form chosen
assert '/MockModel/{id:int}/@' in routes
assert '/MockModel/{id:int}/@{view}' in routes or exact chosen path form
```

Also assert existing actor routes remain:

```text
/MockModel
/mock_models
/mock_models/{id:int}
/mock_models/{id:int}/custom
```

### 5.2 Actor class-name read mirror dispatch tests

File:

```text
packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
```

Required cases:

1. `GET /MockModel/5` sends `TX(name='get', target='mock_models', data={'id': 5})`.
2. response equals `_response_or_raise()` payload.
3. user metadata is included exactly like `/mock_models/5`.
4. `populate` and `depth` query params are forwarded exactly like table-name route.
5. error TX maps to same HTTP exception as table-name route.

### 5.3 Actor HTML route tests

If actor HTML routes are implemented in `network_api.py`, add:

1. `GET /MockModel/@` returns `text/html`.
2. `GET /MockModel/@table` returns `text/html`.
3. `GET /MockModel/5/@` returns `text/html`.
4. `GET /MockModel/5/@item` returns `text/html`.
5. HTML route does not send CRUD TX unless explicitly needed for preloading.
6. route registration order protects `@` from ID capture.

### 5.4 Direct/actor parity tests

Add parity tests at example level:

```text
examples/core/tests/test_class_name_route_parity.py
examples/actors/tests/test_class_name_route_parity.py
```

Both suites should assert the same externally observable behavior for:

- `/Product/{id}` or actor equivalent model class
- `/Product/@`
- `/Product/{id}/@`
- legacy `/products/{id}`

---

## 6. Required SSR / HTML Helper Tests

### 6.1 HTML helper unit tests

If a new helper is added, likely:

```text
packages/n3tx-core/src/n3tx_core/ssr/views.py
```

Create:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_ssr_views.py
```

Required cases for `render_model_view()` or equivalent:

1. collection default with `view=None` chooses list/page fallback.
2. collection named view chooses schema renderer.
3. collection named unknown view follows documented fallback or error behavior.
4. member default chooses detail/item fallback.
5. member named item chooses item renderer.
6. member named detail chooses detail renderer.
7. member named custom chooses declared renderer.
8. generated HTML includes schema preload if SSR mode requires it.
9. generated HTML includes expected custom element tag.
10. generated HTML includes expected `model="ClassName"` for collection.
11. generated HTML includes expected `ref="ClassName/id"` or chosen ref contract for member.
12. generated HTML does not expose unsafe unsanitized route/view values.
13. response media type is `text/html`.

### 6.2 Existing SSR regression tests

File:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_ssr.py
```

Ensure existing tests still pass:

- `/` serves app shell.
- `/index.html` serves app shell.
- SSR schema mode still injects schemas.
- bundle/full modes still work.
- static file serving remains intact.

Add regression cases if model HTML routes are wired through backend app:

1. `/Product/@` does not shadow `/Product` schema.
2. `/Product/@` does not shadow static assets.
3. `/index.html` remains unchanged.
4. `/` remains unchanged.

---

## 7. Required E2E / Browser Tests

### 7.1 Frontend Playwright routes

Existing command:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js
```

Add E2E tests for seeded `examples/core` once router grammar lands.

Required browser cases:

1. Navigate to `/#Product/@` and verify list view renders.
2. Navigate to `/#Product/@table` and verify table view renders.
3. Navigate to `/#Product/{seeded_id}/@` and verify detail view renders.
4. Navigate to `/#Product/{seeded_id}/@item` and verify item renderer renders.
5. Refresh on `/#Product/@table`; same view remains mounted.
6. Refresh on `/#Product/{seeded_id}/@item`; same view remains mounted.
7. Browser back from detail view returns to prior collection view.
8. Sidebar highlights model for `#Product/@table`.
9. Legacy `/#Product` still renders list.
10. Legacy `/#Product/{seeded_id}` still renders detail.

### 7.2 Veille app E2E routes

Existing command:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/veille.playwright.config.js
```

Required cases after Veille migration:

1. `/#AgentActor/@` loads dashboard/agents collection surface as intended.
2. `/#AgentActor/@table` loads table if available or documented fallback.
3. `/#AgentActor/{id}/@` loads `ntx-agent` detail.
4. Refresh on each route preserves view.
5. DASHBOARD home link still clears hash and does not become `#@`.
6. app routes like `#@profile` still work.

---

## 8. Negative and Edge Case Matrix

These are required because route grammar bugs usually happen at boundaries.

### 8.1 Frontend parser negatives

Add explicit behavior for each. If behavior is “best effort parse,” document it in the test name.

| Input | Required behavior |
|---|---|
| `Product//` | normalize to model route or home? choose and test |
| `Product//@@` | documented fallback or parse as invalid? choose and test |
| `Product/@/extra` | should not silently become valid detail/action route |
| `Product/3/@/extra` | should not silently become valid method route |
| `Product/@?view=table` | explicit precedence: `@` default view wins, params pass through |
| `Product/@table?view=list` | explicit precedence: path view `table` wins; `view` param filtered or passed? choose and test |
| `Product/3/@item?method=run` | must remain member view, not method route |
| `@` | app route with empty app or invalid? choose and test |
| `Product/@0` | view name `0` or invalid? choose and test |

Recommended decisions:

- Normalize leading/trailing slashes.
- Path `@view` takes precedence over `?view=`.
- Do not pass `view` query param as DOM attr.
- Treat root `@` as app route only if existing behavior expects it; otherwise home/invalid. Test whatever current behavior is preserved.
- Reject or safely return `null` for extra path segments beyond supported grammar.

### 8.2 Backend route negatives

| Request | Required behavior |
|---|---|
| `GET /Product/@table` | HTML route, not ID route |
| `GET /Product/@` | HTML route, not schema route |
| `GET /Product/not-int` | validation/404, not view route |
| `GET /Product/1/@run` | HTML view route, not method route |
| `GET /Product/1/run` | method/action route if registered |
| `GET /products/@table` | should not exist unless explicitly added |
| `GET /products/1/@` | should not exist unless explicitly added |
| `POST /Product/1` | not allowed until full class-name CRUD mirror is deliberately implemented |
| `PUT /Product/1` | not allowed until deliberately implemented |
| `DELETE /Product/1` | not allowed until deliberately implemented |

---

## 9. Coverage Targets

### 9.1 Frontend coverage target

Run:

```bash
cd /workspace/tests/frontend && npx vitest run --coverage
```

Required practical target for touched files:

| File | Required coverage after refactor |
|---|---:|
| `core/Router.js` | 100% branch coverage for parse/build/resolve helpers |
| `components/ntx-router.js` | all route rendering branches covered |
| `components/ntx-sidebar.js` | selected-state and navigation conversion branches covered if touched |
| `components/ntx-sidebar-link-item.js` | href generation branches covered if migrated |

### 9.2 Backend coverage target

For touched route modules, require behavior coverage rather than numeric-only coverage:

| Module | Required behavior coverage |
|---|---|
| `routes_fastapi.py` | every new route shape generated and exercised |
| `network_api.py` | every new actor route shape generated and exercised |
| `ssr/views.py` if added | every renderer fallback branch and error branch covered |

---

## 10. Required Test Commands Before Merge

### Frontend unit/integration

```bash
cd /workspace/tests/frontend && npx vitest run
```

### Frontend coverage for router work

```bash
cd /workspace/tests/frontend && npx vitest run --coverage
```

### Core backend unit tests

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/
```

### Actor backend tests

```bash
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/ packages/n3tx-actors/src/n3tx_actors/api/tests/
```

### Core example compatibility

```bash
cd /workspace && python3 -m pytest examples/core/tests/
```

### Actor example compatibility

```bash
cd /workspace && python3 -m pytest examples/actors/tests/
```

### Frontend E2E

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js
```

### Veille E2E once migrated

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/veille.playwright.config.js
```

---

## 11. Recommended Test Implementation Sequence

### Test wave 1 — Lock current behavior before refactor

Add tests proving existing behavior remains:

1. legacy route parsing/building still passes.
2. `@profile` remains app route.
3. `Model/id/action` remains action route.
4. table-name API routes still work.
5. `$id` remains table-name based.

### Test wave 2 — Add failing tests for new frontend grammar

Add `parseRoute`, `buildRoute`, `resolveRoute`, `Router`, and `ntx-router` tests for `@` grammar. They should fail before implementation.

### Test wave 3 — Implement frontend grammar until green

Only after wave 2 is red, implement router changes.

### Test wave 4 — Add failing backend direct route tests

Add class-name mirror and HTML route tests for direct FastAPI routes.

### Test wave 5 — Implement direct backend routes until green

Keep `$id` unchanged.

### Test wave 6 — Add failing actor parity tests

Add actor route-generation and dispatch tests.

### Test wave 7 — Implement actor parity until green

### Test wave 8 — Add E2E refresh/navigation tests

Protect actual user-visible flows.

---

## 12. Exit Criteria

The refactor is not complete until all of these are true:

1. All legacy route tests still pass.
2. All new `@` grammar parser/build/resolve tests pass.
3. `#Model/@view` refreshes correctly in browser tests.
4. `Model/id/action` and `Model/id/@action` are proven distinct.
5. `/ClassName/{id}` mirrors `/tablename/{id}` for reads.
6. `$id` remains table-name based until intentionally migrated.
7. `/ClassName/@...` routes return HTML and do not shadow schema routes.
8. Actor routing has parity with direct routing or is explicitly marked not yet implemented.
9. Core and actor examples still pass their current test suites.
10. Veille dashboard/sidebar behavior remains fixed: no `#@` for dashboard, no blank main pane.

---

## 13. Critical Files for Test Implementation

- `tests/frontend/tests/core/route-functions.test.js`
- `tests/frontend/tests/core/Router.test.js`
- `tests/frontend/tests/components/ntx-router.test.js`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py`
