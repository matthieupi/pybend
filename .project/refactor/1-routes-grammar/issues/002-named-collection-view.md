# Issue 002 Plan: Named Collection View Route

## Goal

Extend the collection view route tracer bullet from issue 001 to named
collection views:

```text
#Product/@table       -> frontend named collection view route
#Product/@list        -> frontend named collection view route
#Product/@custom-card -> frontend custom named collection view route

/Product/@table       -> backend HTML named collection view route
```

This issue makes view routing useful beyond the default collection page. A
developer should be able to name a semantic collection view in the URL and have
that semantic view resolve through the model schema before framework fallbacks.

Backend route ownership remains with **ViewableMixin**, continuing the issue 001
decision:

```text
StorableMixin  -> CRUD/data routes
ViewableMixin  -> HTML/view routes
```

---

## Depends on issue 001

Issue 002 assumes issue 001 has established:

```text
#Product/@   -> collection default view route
/Product/@   -> backend HTML collection default view route
```

and a backend capability hook such as:

```python
class ViewableMixin:
    @classmethod
    def register_view_routes(cls, router, *, tag: str) -> None:
        ...
```

Issue 002 extends that same hook instead of introducing route ownership in
`routes_fastapi.py`.

---

## Scope for issue 002

Implement named collection views only:

```text
Frontend:
  {ClassName}/@{view}

Backend:
  GET /{ClassName}/@{view}
```

Examples:

```text
Product/@table
Product/@list
Product/@custom-card
Product/@ntx-custom-card
```

Do **not** implement yet:

```text
/{ClassName}/{id:int}
/{ClassName}/{id:int}/@
/{ClassName}/{id:int}/@{view}
#{ClassName}/{id}/@
#{ClassName}/{id}/@item
actor routing parity
sidebar link migration
full unsafe token policy beyond safe deterministic named views
```

---

## Core behavior contract

### Route semantics

Inside a model route, a segment beginning with `@` is a view segment:

```text
Product/@table -> collection view named "table"
```

It is not:

```text
id = '@table'
action = '@table'
data route
schema route
```

Root app routes are unchanged:

```text
@profile        -> app route
@settings?tab=x -> app route with params
```

### Renderer resolution

Named collection views resolve in this order:

```text
1. schema.ui.renderer[view]
2. framework fallback for known views
3. ergonomic ntx-${view} fallback for safe custom view names
```

Issue 002 should support at least these known framework fallbacks:

```text
list  -> ntx-list
table -> ntx-table
```

Custom safe names use deterministic fallback:

```text
custom-card     -> ntx-custom-card
ntx-custom-card -> ntx-custom-card
```

The stricter production policy for unsafe view tokens remains issue 005. Issue
002 should still avoid obviously unsafe behavior by keeping frontend fallback as
a tag string only and letting issue 005 formalize validation/rejection.

### Query params

Path view selection is authoritative:

```text
Product/@table?view=list -> table wins
```

Query params pass through to mounted components except internal route controls:

```text
Product/@table?limit=10&offset=20
  -> attrs: { model: 'Product', limit: '10', offset: '20' }
```

`view` should not be passed through as a DOM attr:

```text
Product/@table?view=list
  -> attrs.view is undefined
```

Legacy query-based view selection remains supported:

```text
Product?view=table
```

For issue 002, legacy `?view=` should use the same semantic resolver as path
views so schema renderer declarations are honored consistently:

```text
Product?view=table + renderer.table='ntx-product-table'
  -> ntx-product-table
```

---

## Proposed module shape

### 1. Frontend route grammar deep module

Module:

```text
Router.js route functions
```

The public interface remains:

```javascript
parseRoute(route)
buildRoute(parts)
resolveRoute(parsed, getSchema)
```

Issue 002 extends the issue 001 `@` route branch from exactly `@` to also accept
`@{view}`.

#### Parser behavior

```javascript
parseRoute('Product/@table')
```

returns:

```javascript
{
  type: 'model',
  model: 'Product',
  id: null,
  action: null,
  view: 'table',
  isViewRoute: true,
  params: {},
}
```

Additional examples:

```javascript
parseRoute('Product/@list').view === 'list'
parseRoute('Product/@custom-card').view === 'custom-card'
parseRoute('Product/@ntx-custom-card').view === 'ntx-custom-card'
parseRoute('Product/@table?limit=10').params.limit === '10'
```

Normalization from the PRD should apply:

```text
/Product/@table/ -> Product/@table
```

Issue 002 can normalize by trimming leading/trailing slashes and filtering empty
segments. More extensive malformed-route rejection remains issue 005.

#### Builder behavior

```javascript
buildRoute({
  type: 'model',
  model: 'Product',
  isViewRoute: true,
  view: 'table',
})
```

returns:

```text
Product/@table
```

With params:

```javascript
buildRoute({
  type: 'model',
  model: 'Product',
  isViewRoute: true,
  view: 'table',
  params: { limit: '10' },
})
```

returns:

```text
Product/@table?limit=10
```

#### Resolver behavior

Add or refine a helper inside the route module:

```javascript
resolveViewTag(schema, view, scope)
```

For issue 002 only `scope === 'collection'` is needed.

Recommended collection logic:

```javascript
function resolveViewTag(schema, view, scope) {
  const renderer = schema?.ui?.renderer || {};

  if (view && renderer[view]) return renderer[view];

  if (!view && scope === 'collection') {
    return renderer.page || renderer.list || 'ntx-list';
  }

  const known = {
    list: 'ntx-list',
    table: 'ntx-table',
  };

  if (view && known[view]) return known[view];
  if (view) return view.startsWith('ntx-') ? view : `ntx-${view}`;

  return 'ntx-list';
}
```

This helper should remain internal until a later design decision says otherwise.

---

### 2. Router state actor

Module:

```text
Router class in Router.js
```

No new state machinery is required. Add tests that named collection view route
strings behave as normal route strings:

```text
NAVIGATE('Product/@table') -> current 'Product/@table'
hash sync                 -> #Product/@table
initial hash load          -> no fake back history
resolved getter            -> schema-mapped named collection view
```

---

### 3. Router DOM mount

Module:

```text
ntx-router.js
```

No grammar logic should be added here. It should continue to consume
`Router.resolved` only.

Add tests proving:

```text
#Product/@table -> <schema-selected-table-tag model="Product" router="main">
```

For schema:

```json
{
  "ui": {
    "renderer": {
      "table": "ntx-product-table"
    }
  }
}
```

mount:

```html
<ntx-product-table model="Product" router="main"></ntx-product-table>
```

For no schema renderer:

```text
Product/@table -> ntx-table
```

---

### 4. Backend ViewableMixin route ownership

Module:

```text
n3tx-ui ViewableMixin
```

Extend `ViewableMixin.register_view_routes()` from issue 001:

```text
GET /{ClassName}/@       -> collection default view
GET /{ClassName}/@{view} -> collection named view
```

The named route should remain:

```python
include_in_schema=False
```

For issue 002, route registration should intentionally be **collection-only**.
Member routes are not part of this issue.

#### Route order

Register default and named collection routes before later generic class-name
instance routes exist:

```text
GET /Product
GET /Product/@
GET /Product/@{view}
future: GET /Product/{id:int}
```

For issue 002, exact `/Product/@` and `/Product/@{view}` should not shadow
`/Product` schema.

---

### 5. Backend HTML rendering helper

The issue 001 helper should be generalized from “default collection view” to
“collection view with optional view key”.

Recommended helper shape near `ViewableMixin`:

```python
def resolve_collection_view_tag(model_class: type, view: str | None) -> str:
    renderer = (getattr(model_class, '__ui__', None) or {}).get('renderer', {})
    if view and renderer.get(view):
        return renderer[view]
    if view is None:
        return renderer.get('page') or renderer.get('list') or 'ntx-list'
    known = {'list': 'ntx-list', 'table': 'ntx-table'}
    if view in known:
        return known[view]
    return view if view.startswith('ntx-') else f'ntx-{view}'
```

Then:

```python
def render_model_collection_view(model_class: type, view: str | None = None):
    tag = resolve_collection_view_tag(model_class, view)
    ... HTMLResponse containing f'<{tag} model="{model_class.__name__}"></{tag}>'
```

Important: this should match frontend collection resolver behavior for this
slice.

---

## Test-first plan

### Frontend route function tests

Update:

```text
tests/frontend/tests/core/route-functions.test.js
```

Add parser cases:

```javascript
expect(parseRoute('Product/@table')).toMatchObject({
  type: 'model', model: 'Product', view: 'table', isViewRoute: true,
});

expect(parseRoute('Product/@list')).toMatchObject({ view: 'list' });
expect(parseRoute('Product/@custom-card')).toMatchObject({ view: 'custom-card' });
expect(parseRoute('Product/@ntx-custom-card')).toMatchObject({ view: 'ntx-custom-card' });

expect(parseRoute('Product/@table?limit=10&offset=20').params)
  .toEqual({ limit: '10', offset: '20' });
```

Add normalization cases:

```javascript
expect(buildRoute(parseRoute('/Product/@table/'))).toBe('Product/@table');
```

Add builder cases:

```javascript
expect(buildRoute({
  type: 'model', model: 'Product', isViewRoute: true, view: 'table'
})).toBe('Product/@table');

expect(buildRoute({
  type: 'model', model: 'Product', isViewRoute: true,
  view: 'table', params: { limit: '10' }
})).toBe('Product/@table?limit=10');
```

Add resolver cases:

```javascript
const schema = { ui: { renderer: { table: 'ntx-product-table' } } };
expect(resolveRoute(parseRoute('Product/@table'), () => schema).tag)
  .toBe('ntx-product-table');

expect(resolveRoute(parseRoute('Product/@table'), () => null).tag)
  .toBe('ntx-table');

expect(resolveRoute(parseRoute('Product/@custom'), () => null).tag)
  .toBe('ntx-custom');

expect(resolveRoute(parseRoute('Product/@ntx-custom'), () => null).tag)
  .toBe('ntx-custom');
```

Add query compatibility cases:

```javascript
const r = resolveRoute(parseRoute('Product/@table?limit=10&view=list'), () => schema);
expect(r.tag).toBe('ntx-product-table');
expect(r.attrs).toEqual({ model: 'Product', limit: '10' });
expect(r.attrs.view).toBeUndefined();

const legacy = resolveRoute(parseRoute('Product?view=table'), () => schema);
expect(legacy.tag).toBe('ntx-product-table');
expect(legacy.attrs.view).toBeUndefined();
```

Legacy regression cases remain:

```text
Product       -> model route
Product/1     -> detail route
Product/1/run -> action route
@profile      -> app route
```

---

### Router state tests

Update:

```text
tests/frontend/tests/core/Router.test.js
tests/frontend/tests/integration/router-navigation.test.js
```

Required assertions:

```javascript
router.NAVIGATE('Product/@table')
expect(router.current).toBe('Product/@table')
expect(window.location.hash).toBe('#Product/@table')
```

Also test:

```text
initial hash #Product/@table does not create fake back history
BACK from Product/@table returns to previous route
resolved getter returns schema-mapped tag and attrs
```

---

### Router DOM tests

Update:

```text
tests/frontend/tests/components/ntx-router.test.js
```

Mock schema through `window.NTT.get('Product').schema` and assert:

```text
#Product/@table mounts <ntx-product-table model="Product" router="...">
```

Also assert fallback behavior:

```text
#Product/@table with no renderer mounts <ntx-table model="Product">
```

and current issue 001 behavior remains:

```text
#Product/@ still mounts page/list/default collection renderer
```

---

### Backend ViewableMixin tests

Update:

```text
packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py
```

Add tests for backend helper/route ownership:

```text
register_view_routes registers /Product/@{view}
route is include_in_schema=False
default route /Product/@ remains registered
named route handler returns text/html
renderer.table is preferred for view='table'
known fallback table -> ntx-table
custom fallback custom-card -> ntx-custom-card
```

If route behavior is easier to verify through a FastAPI app, use a minimal
APIRouter or TestClient around the mixin route registration method.

---

### Backend direct route behavior tests

Update or add focused tests in:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

or a new focused route-view file if that keeps the tests clearer.

Required assertions:

```text
GET /Product/@table -> 200 text/html
HTML contains schema renderer tag for table when declared
GET /Product/@list -> 200 text/html
GET /Product/@custom-card -> 200 text/html with fallback tag for this phase
GET /Product/@table does not shadow GET /Product schema
GET /products remains legacy JSON collection for storable models
```

Route presence/order assertions:

```text
/Product
/Product/@
/Product/@{view}
/products
```

`/Product/@table` should match the HTML route, not schema/static fallback.

---

## Implementation steps

### Step 1 — Red: frontend named collection tests

Add failing tests for parser, builder, resolver, router state, integration, and
DOM mount behavior for `Product/@table`.

Expected failures before implementation:

```text
Product/@table parses as detail id='@table'
schema renderer table is not used for path view routes
```

### Step 2 — Green: frontend named collection grammar

Update `Router.js`:

1. Extend collection view detection from `second === '@'` to also
   `second?.startsWith('@')`.
2. Return `view: null` for `@`, and `view: second.slice(1)` for `@table`.
3. Normalize route path segments consistently.
4. Extend `buildRoute()` to append `/@${view || ''}` for collection view routes.
5. Add or refine `resolveViewTag()` for collection named views.
6. Make legacy `?view=` use the same collection view resolver.
7. Filter query `view` from attrs for both path and legacy query routes.

### Step 3 — Red: backend named view tests

Add failing tests for `ViewableMixin.register_view_routes()` registering and
serving `/Product/@{view}`.

Expected failures before implementation:

```text
/Product/@table returns 404
ViewableMixin helper does not accept a view name
```

### Step 4 — Green: ViewableMixin named collection route

Extend `ViewableMixin.register_view_routes()`:

```python
@router.get(f"/{cls.__name__}/@{{view}}", include_in_schema=False)
async def collection_named_view(view: str):
    return render_model_collection_view(cls, view=view)
```

Route syntax may need to be adjusted to FastAPI’s exact path behavior, but the
external route contract must be:

```text
GET /Product/@table
```

### Step 5 — Green: backend renderer resolution parity

Generalize the backend helper so frontend and backend choose the same component
tag for collection named views:

```text
renderer[view] -> known fallback -> ntx-${view}
```

### Step 6 — Verify focused suites

Run:

```bash
cd /workspace/tests/frontend && npx vitest run tests/core/route-functions.test.js tests/core/Router.test.js tests/integration/router-navigation.test.js tests/components/ntx-router.test.js
cd /workspace && python3 -m pytest packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py -q
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py -q
```

If a new backend route-view test file is added, run it explicitly.

---

## Non-goals for this issue

- Member routes such as `Product/1/@` or `Product/1/@item`
- Class-name read mirrors such as `/Product/1`
- Method/view collision for member routes (`Product/1/run` vs `Product/1/@run`)
- Actor routing parity
- Sidebar generation or selected-state migration
- Browser E2E smoke
- Final unsafe-token policy from issue 005
- `$id` migration
- Class-name CRUD write mirrors

---

## Acceptance checklist

- [ ] `Product/@table`, `Product/@list`, and custom collection view routes parse as model view routes.
- [ ] Named collection view routes build and round-trip canonically.
- [ ] Leading/trailing slash variants normalize canonically.
- [ ] `resolveRoute()` uses `schema.ui.renderer[view]` before fallbacks.
- [ ] `Product/@table` falls back to `ntx-table` when schema does not declare a table renderer.
- [ ] Custom safe views fall back deterministically to `ntx-${view}`.
- [ ] Query params pass through except internal `view`.
- [ ] Legacy `Product?view=table` remains supported and uses schema renderer lookup.
- [ ] Path view selection wins over query `view`.
- [ ] `ntx-router` mounts schema-selected named collection view components.
- [ ] `ViewableMixin` owns backend named collection view routes.
- [ ] `/Product/@table` returns `text/html`.
- [ ] `/Product/@table` does not shadow `/Product` schema.
- [ ] Legacy `/products` data routes remain unchanged.
