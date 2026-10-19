# Hypermedia Route Grammar — Phase-by-Phase Implementation Plan

## ✅ Recommendation

Implement the route grammar refactor as an additive, test-first migration. Land the frontend `@` grammar first, then direct backend read mirrors, then HTML entrypoints, then actor parity, and only then migrate first-party navigation links.

Default path:

```text
Phase 0  Freeze decisions + legacy regression tests
Phase 1  Pure frontend parser/builder grammar
Phase 2  Schema-driven route resolution
Phase 3  Router state + DOM mounting
Phase 4  Direct FastAPI class-name read mirrors
Phase 5  Direct FastAPI HTML/view entrypoints
Phase 6  Actor API class-name read parity
Phase 7  Sidebar/app link migration
Phase 8  Browser E2E + docs/cleanup
```

Keep these constraints strict through all phases:

1. `/tablename/...` remains the compatibility JSON API.
2. `/ClassName` remains the schema endpoint.
3. `/ClassName/{id:int}` is read-only mirror initially.
4. `/ClassName/@...` returns HTML/view shell, never JSON.
5. `Model/id/action` remains method/action; `Model/id/@action` is a view.
6. `$id` remains table-name based until a separate identity migration.

```text
             +--------------------+
             | Python model class |
             +----------+---------+
                        |
       +----------------+----------------+
       |                                 |
       v                                 v
 /ClassName schema                 /tablename JSON API
       |                                 |
       v                                 v
 #ClassName/@view                /ClassName/id read mirror
 frontend view grammar                  |
       |                                 v
       v                         same model_response()
 schema.ui.renderer                       |
       |                                 v
       v                         $id stays /tablename/id
 mounted component

 /ClassName/@view -> HTML shell -> same frontend router/component runtime
```

---

## 📍 Current State Summary

| Area | Current behavior | Gap to close |
|---|---|---|
| Frontend parser | `Model`, `Model/id`, `Model/id/action`, `@app`, `?view=` | No `Model/@view` or `Model/id/@view` grammar |
| Frontend resolver | Uses schema renderers for list/detail/action; `?view=` list override | No semantic `@view` resolver contract |
| `ntx-router` | Thin consumer of `{ tag, attrs, title }` | Mostly reusable; needs tests for new resolved shapes |
| Direct routes | `/ClassName` schema, `/tablename/...` CRUD/methods | No `/ClassName/{id}` mirror; no `/ClassName/@...` HTML |
| Actor routes | Level 3 mirrors table-name CRUD/methods via TX | No class-name read mirror |
| SSR/static | `/` and `/index.html` app shell support | No model-view shell helper/route |
| Sidebar | Legacy links `#Model`, `#Model/id`, app route mapping | Needs selected-state support first, generated-link migration later |

---

## Phase 0 — Freeze Decisions + Legacy Regression Tests

Goal: lock the non-negotiable behavior before changing grammar.

### Steps

1. Add/verify legacy parser tests in `tests/frontend/tests/core/route-functions.test.js`:
   - `Product` -> model route.
   - `Product/3` -> detail route.
   - `Product/3/run` -> action route.
   - `@profile` and `@settings?tab=security` -> app routes.
   - `Product?view=table` remains supported.
2. Add method-vs-view baseline expectations before implementation:
   - `Product/3/run` must stay action.
   - `Product/3/@run` will become detail view route after Phase 1.
3. Add direct backend compatibility tests in `examples/core/tests/` or core route unit tests:
   - `GET /Product` still schema.
   - `GET /products`, `GET /products/{id}`, custom methods still work.
4. Add actor compatibility tests in `examples/actors/tests/` or `test_network_api.py`:
   - existing `/products/{id}` and method TX dispatch unchanged.

### Verification

```bash
cd /workspace/tests/frontend && npx vitest run tests/core/route-functions.test.js
cd /workspace && python3 -m pytest examples/core/tests/ examples/actors/tests/
```

---

## Phase 1 — Pure Frontend `@` Parser/Builder Grammar

Goal: make route strings unambiguous without touching DOM or backend.

Primary file:

- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

Primary tests:

- `tests/frontend/tests/core/route-functions.test.js`

### Steps

1. Normalize model routes by trimming leading/trailing slashes and filtering empty path segments.
2. Extend `parseRoute(route)` with explicit view metadata:

```js
{
  type: 'model' | 'detail' | 'action' | 'app' | 'home',
  model,
  id,
  action,
  view,
  isViewRoute,
  params,
}
```

3. Parse collection view routes before legacy detail parsing:
   - `Product/@` -> `{ type:'model', isViewRoute:true, view:null }`
   - `Product/@table` -> `{ type:'model', isViewRoute:true, view:'table' }`
4. Parse member view routes before action parsing:
   - `Product/3/@` -> `{ type:'detail', id:'3', isViewRoute:true, view:null }`
   - `Product/3/@item` -> `{ type:'detail', id:'3', isViewRoute:true, view:'item' }`
5. Keep root app routes first:
   - `@profile` is still app route, not a model view.
6. Extend `buildRoute(parts)` so every supported view route round-trips.
7. Decide and test invalid extra segments. Recommended first implementation: return a deterministic `action`/legacy parse only for non-`@` routes; treat extra `@` paths as invalid/home or stable fallback, but do not silently mount a method.

### Code-shape preview

```js
const [path, query] = route.split('?');
const params = query ? Object.fromEntries(new URLSearchParams(query)) : {};
const parts = path.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean);
const [model, second, third] = parts;

if (second === '@' || second?.startsWith('@')) {
  return { type: 'model', model, view: second === '@' ? null : second.slice(1), isViewRoute: true, params };
}

if (third === '@' || third?.startsWith('@')) {
  return { type: 'detail', model, id: second, view: third === '@' ? null : third.slice(1), isViewRoute: true, params };
}
```

### Verification

```bash
cd /workspace/tests/frontend && npx vitest run tests/core/route-functions.test.js
```

---

## Phase 2 — Schema-Driven View Resolution

Goal: resolve `@view` through `schema.ui.renderer` first, with stable framework fallbacks.

Primary file:

- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

### Steps

1. Add `resolveViewTag(schema, view, scope)` as a small pure helper.
2. Fallback order:

| Route | Resolver order |
|---|---|
| `Model/@` | `renderer.page` -> `renderer.list` -> `ntx-list` |
| `Model/@table` | `renderer.table` -> known `ntx-table` -> `ntx-table` |
| `Model/@custom` | `renderer.custom` -> `ntx-custom` |
| `Model/id/@` | `renderer.detail` -> `renderer.item` -> `ntx-item` |
| `Model/id/@chat` | `renderer.chat` -> `ntx-chat` |

3. Update `resolveRoute()`:
   - For `parsed.isViewRoute`, use `resolveViewTag()`.
   - Preserve legacy `?view=` for collection routes.
   - Path `@view` takes precedence over query `view`.
   - Filter internal controls: do not pass `view` or `isViewRoute` as attrs.
4. Preserve action routes:
   - `Product/3/run` gets `attrs.method='run'`.
   - `Product/3/@run` does not get `method`.

### Code-shape preview

```js
function resolveViewTag(schema, view, scope) {
  const renderer = schema?.ui?.renderer || {};
  if (view && renderer[view]) return renderer[view];
  if (!view && scope === 'collection') return renderer.page || renderer.list || 'ntx-list';
  if (!view && scope === 'member') return renderer.detail || renderer.item || 'ntx-item';
  const known = { list: 'ntx-list', table: 'ntx-table', item: 'ntx-item', detail: renderer.detail || renderer.item || 'ntx-item' };
  return known[view] || (view ? (view.startsWith('ntx-') ? view : `ntx-${view}`) : (scope === 'collection' ? 'ntx-list' : 'ntx-item'));
}
```

### Verification

```bash
cd /workspace/tests/frontend && npx vitest run tests/core/route-functions.test.js
```

---

## Phase 3 — Router State + DOM Mounting

Goal: prove `@` routes behave like normal navigation routes and mount clean components.

Primary files:

- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`

Primary tests:

- `tests/frontend/tests/core/Router.test.js`
- `tests/frontend/tests/integration/router-navigation.test.js`
- `tests/frontend/tests/components/ntx-router.test.js`

### Steps

1. Add Router state tests:
   - `NAVIGATE('Product/@table')` updates `current` and hash.
   - Initial `#Product/@table` loads without fake history.
   - Duplicate view route is no-op.
   - `BACK()` and reset-to-home clear hashes correctly.
2. Add integration tests:
   - `buildRoute()` -> `NAVIGATE()` -> `parseRoute()` -> `resolveRoute()`.
   - Root app routes still work.
3. Add `ntx-router` DOM tests:
   - `#Product/@table` mounts schema-selected collection tag.
   - `#Product/9/@item` mounts member tag with `ref="Product/9"`, `display="lg"`.
   - Member view does not receive `method` attr.
   - Home restores slot.
4. Avoid changing `ntx-router` unless tests reveal a real attr/mounting gap; it is already the correct thin boundary.

### Verification

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/core/Router.test.js \
  tests/integration/router-navigation.test.js \
  tests/components/ntx-router.test.js
```

---

## Phase 4 — Direct FastAPI Class-Name Read Mirrors

Goal: add `GET /{ClassName}/{id:int}` as a read-only mirror of `GET /{tablename}/{id:int}`.

Primary file:

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

Primary tests:

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `examples/core/tests/test_class_name_routes.py` or equivalent

### Steps

1. Add route-generation tests asserting presence of:
   - `/Product`
   - `/Product/{id:int}`
   - existing `/products/{id:int}`
2. Register class-name read mirror for storable models only.
3. Delegate to the exact existing `make_get_instance(model_class)` handler.
4. Do not add class-name POST/PUT/DELETE/method mirrors in this phase.
5. Test behavior:
   - `/Product/1` response equals `/products/1` for domain fields.
   - `$schema` ends with `/Product`.
   - `$id` still ends with `/products/1`.
   - populate/depth query params mirror table route.
   - missing records and auth behavior match.

### Code-shape preview

```python
read_instance = make_get_instance(model_class)
router.get(f"/{model_class.__name__}/{{id:int}}", tags=[tag])(read_instance)
router.get(f"{endpoint_base}/{{id:int}}", tags=[tag])(read_instance)
```

### Verification

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py examples/core/tests/
```

---

## Phase 5 — Direct FastAPI HTML/View Entrypoints

Goal: add `/ClassName/@...` routes that return an HTML shell using the normal frontend runtime.

Primary files:

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-core/src/n3tx_core/api/backend.py`
- `packages/n3tx-core/src/n3tx_core/ssr/html.py` or new `packages/n3tx-core/src/n3tx_core/ssr/views.py`

Primary tests:

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_ssr.py`
- new `packages/n3tx-core/src/n3tx_core/tests/unit/test_ssr_views.py` or `test_model_view_routes.py`

### Steps

1. Extract or add a small HTML helper that can render the app shell for a route.
2. Add safe view-token validation before inserting route/view data into HTML:
   - recommended pattern: `[A-Za-z0-9_-]+`
   - default `@` is `view=None`.
3. Implement `render_model_view(model_class, id, view, scope, request)`.
4. Prefer bootstrapping the router route over inventing server-side components:

```html
<script>window.NTX_INITIAL_ROUTE = "Product/1/@item";</script>
<ntx-router name="main"></ntx-router>
```

or mount the component directly if consistent with the existing shell:

```html
<ntx-item ref="Product/1" display="lg"></ntx-item>
```

5. Register explicit routes before static catch-all:
   - `GET /{ClassName}/@`
   - `GET /{ClassName}/@{view}`
   - `GET /{ClassName}/{id:int}/@`
   - `GET /{ClassName}/{id:int}/@{view}`
6. Hide HTML routes from OpenAPI with `include_in_schema=False` unless explicitly desired.
7. Decide unknown-safe view behavior. Recommended: frontend-compatible fallback for safe tokens, `400` for unsafe tokens.

### Verification

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_ssr.py packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py examples/core/tests/
```

---

## Phase 6 — Actor API Class-Name Read Parity

Goal: make Level 3 `GET /ClassName/{id:int}` dispatch the exact same `get` TX as `/tablename/{id:int}`.

Primary file:

- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`

Primary tests:

- `packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py`
- `examples/actors/tests/`

### Steps

1. Add route-generation test for `/MockModel/{id:int}`.
2. Factor current table-name read handler or register class-name mirror with identical TX construction:

```python
TX(
  name='get',
  source=api_adapter.addr,
  target=_addr,              # table-name actor address
  data={'id': id, 'populate': populate, 'depth': depth},
  meta={'user': user, 'model_cls': _cls},
)
```

3. Assert class-name route does not dispatch `schema` TX.
4. Assert auth metadata is identical to table-name route.
5. Do not implement actor HTML routes through TX. HTML is a shell/static concern; reuse core route/static machinery if actor-mode apps need it.
6. Add actor example parity:
   - `/Product/{id}` mirrors `/products/{id}`.
   - unauthenticated/authenticated behavior matches.
   - `$id` remains table-name based.

### Verification

```bash
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py examples/actors/tests/
```

---

## Phase 7 — Sidebar/App Link Migration

Goal: migrate first-party navigation gradually after parser/resolver/backend behavior is green.

Primary files:

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar-link-item.js`

### Steps

1. Before changing generated links, add selected-state compatibility tests:
   - `#Product/@`, `#Product/@table`, `#Product/3/@`, `#Product/3/@item` mark Product selected.
   - `#@settings` still marks app link.
   - bare `#` still means home.
2. Migrate generated model links from `#Product` to `#Product/@` only once tests are stable.
3. Migrate record links from `#Product/5` to `#Product/5/@` only if desired for first-party UI.
4. Keep legacy route support indefinitely during this migration window.
5. Preserve sidebar route-template behavior; for custom route templates, emit `@view` only when there is a semantic view key, not arbitrary internal attrs.

### Verification

```bash
cd /workspace/tests/frontend && npx vitest run tests/components/ntx-sidebar.test.js tests/components/ntx-sidebar-link-item.test.js
```

---

## Phase 8 — Browser E2E + Docs/Cleanup

Goal: prove user-visible refresh/back/deep-link behavior and document the final contract.

### Steps

1. Add Playwright tests for core example:
   - `/#Product/@` renders collection.
   - `/#Product/@table` renders table or documented fallback.
   - `/#Product/{id}/@` renders detail.
   - refresh preserves the mounted view.
   - browser back returns to previous route.
   - legacy `/#Product` and `/#Product/{id}` still work.
2. Add Veille tests after app migration:
   - `/#AgentActor/@` renders agents surface.
   - `/#AgentActor/{id}/@chat` mounts chat if renderer declares it.
   - dashboard/home links still clear hash and never become `#@`.
3. Update docs:
   - `FRONTEND.md` route grammar and renderer resolution.
   - `BACKEND.md` direct/actor route grammar.
   - `docs/CORE.md` schema renderer route contract if needed.
4. Run broad verification.

### Verification

```bash
cd /workspace/tests/frontend && npx vitest run
cd /workspace && python3 scripts/test-backend.py --short
cd /workspace/tests/frontend && npm run test:e2e:fast
```

---

## 📊 Phase Dependency Table

| Phase | Can land independently? | Depends on | Main regression surface |
|---|---:|---|---|
| 0 | yes | none | accidental legacy breakage |
| 1 | yes | 0 | parser ambiguity |
| 2 | yes | 1 | wrong component/tag resolution |
| 3 | yes | 1-2 | hash/back/DOM mount regressions |
| 4 | yes | 0 | backend auth/identity drift |
| 5 | mostly | 2,4 recommended | HTML routes shadow schema/data |
| 6 | yes | 4 for parity model | actor/direct drift, auth metadata |
| 7 | yes | 1-3 | first-party navigation breakage |
| 8 | no | all relevant phases | refresh/back/user-visible regressions |

---

## ⚠️ Key Risks and Mitigations

| Risk | Mitigation |
|---|---|
| `@table` parsed as ID/action | Parse `@` branches first in frontend; use `{id:int}` backend routes |
| View named like method triggers method | Tests for `Product/3/run` vs `Product/3/@run` |
| `$id` identity drift | Reuse existing read serializers; assert `$id=/tablename/id` |
| Auth bypass in mirrors | Delegate to existing direct handler or identical actor `get` TX |
| HTML shell becomes second rendering system | Bootstrap existing frontend runtime only |
| OpenAPI noise/confusion | `include_in_schema=False` for HTML routes |
| Unsafe view token injection | Validate/sanitize view names before HTML generation |

---

## Concrete Next Step

Start with Phase 0 and Phase 1 in one small branch/commit pair:

1. Add failing route-function tests for `@` grammar.
2. Update only `Router.js` parser/builder.
3. Run `tests/frontend/tests/core/route-functions.test.js` until green.

Do not start backend routes until the frontend grammar and resolver contracts are green.

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-core/src/n3tx_core/api/backend.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`

## Saved Plan

- `.project/refactor/1-routes-grammar/3-phase-by-phase-implementation-plan.md`
