# Issue 001 Plan: Collection Default View Route

## Goal

Build the first end-to-end tracer bullet for the hypermedia route grammar:

```text
#Product/@   -> frontend collection default view route
/Product/@   -> backend HTML collection default view route
```

The important architectural correction is that backend view routes should be
owned by **ViewableMixin**, not by generic route registration logic. This mirrors
the existing design where:

```text
StorableMixin  -> model can have CRUD/data routes
ViewableMixin  -> model can have view/HTML routes
```

This keeps route ownership aligned with model capabilities: a model becomes
view-route-capable because it is viewable (`__viewable__ = True` or `__ui__` is
present), not because every registered model receives HTML routes by default.

---

## Current state confirmed

### Frontend

`Router.js` currently supports:

```text
@profile
Product
Product/1
Product/1/run
Product?view=table
```

It currently misclassifies:

```text
Product/@
```

as a detail route with `id='@'`.

### Backend direct routes

`routes_fastapi.py` currently registers schema, CRUD, and custom method routes
centrally:

```text
GET    /Product       -> schema
GET    /products      -> list
POST   /products      -> create
GET    /products/{id} -> read
PUT    /products/{id} -> update
DELETE /products/{id} -> delete
POST   /products/{id}/method
```

View routes do not exist yet.

### ViewableMixin

`ViewableMixin` currently lives in `n3tx-ui` and owns schema UI metadata:

```text
packages/n3tx-ui/src/n3tx_ui/mixin.py
```

It is injected when:

```python
__viewable__ = True
```

or when:

```python
__ui__ = {...}
```

via:

```python
register_mixin('__viewable__', ViewableMixin, also_if=['__ui__'])
```

At present it has no route-registration surface.

---

## Architectural decision

### Route ownership

Backend HTML/view routes should be registered for models that are viewable:

```text
issubclass(model_class, ViewableMixin)
```

or equivalently through a route-registration method exposed by that mixin.

The direct FastAPI route registrar should delegate view-route registration to
the capability owner, the same way CRUD behavior is conceptually tied to
`StorableMixin`.

### Package boundary

Because `ViewableMixin` lives in `n3tx-ui`, `n3tx-core` must not require
`n3tx-ui` at import time unconditionally.

The plan should preserve the package dependency boundary:

```text
n3tx-core  -> foundation, should not hard-depend on n3tx-ui
n3tx-ui    -> visual/view capability package, depends on n3tx-core
```

Therefore the integration should be capability/protocol based rather than a
hard core import of `n3tx_ui.mixin.ViewableMixin`.

Recommended contract:

```python
class ViewableMixin:
    @classmethod
    def register_view_routes(cls, router, *, tag: str) -> None:
        ...
```

Then `routes_fastapi.register_routes()` can check for the method without
importing the UI package:

```python
register_view_routes = getattr(model_class, 'register_view_routes', None)
if callable(register_view_routes):
    register_view_routes(router, tag=tag)
```

This keeps `n3tx-core` generic: it knows only that a model class can register
extra routes, not which package provided that capability.

---

## Scope for Issue 001

Only implement the collection default view route:

```text
GET /{ClassName}/@
```

Only implement frontend hash support for:

```text
{ClassName}/@
```

Do **not** implement yet:

```text
/{ClassName}/@{view}
/{ClassName}/{id:int}
/{ClassName}/{id:int}/@
/{ClassName}/{id:int}/@{view}
#{ClassName}/@table
#{ClassName}/{id}/@
actor routing parity
sidebar link migration
view-token hardening beyond the exact default route
```

---

## Proposed module shape

### 1. Frontend route grammar deep module

Module:

```text
Router.js route functions
```

Public interface remains:

```javascript
parseRoute(route)
buildRoute(parts)
resolveRoute(parsed, getSchema)
```

This is the frontend deep module for route grammar. It should encapsulate the
new `@` semantics behind the same small interface.

#### Parser behavior for issue 001

```javascript
parseRoute('Product/@')
```

returns:

```javascript
{
  type: 'model',
  model: 'Product',
  id: null,
  action: null,
  view: null,
  isViewRoute: true,
  params: {},
}
```

Legacy routes remain unchanged:

```javascript
parseRoute('Product')
parseRoute('Product/1')
parseRoute('Product/1/run')
parseRoute('@profile')
```

#### Builder behavior for issue 001

```javascript
buildRoute({ type: 'model', model: 'Product', isViewRoute: true })
```

returns:

```text
Product/@
```

#### Resolver behavior for issue 001

```javascript
resolveRoute(parseRoute('Product/@'), getSchema)
```

resolves collection default view in this order:

```text
schema.ui.renderer.page
schema.ui.renderer.list
ntx-list
```

and returns attrs:

```javascript
{ model: 'Product' }
```

---

### 2. Router state actor

Module:

```text
Router class in Router.js
```

No new state concept is required. `Router` already treats routes as strings.
Issue 001 only needs tests proving that the new route string behaves like an
ordinary route:

```text
NAVIGATE('Product/@') -> hash '#Product/@'
duplicate route        -> no-op
BACK/RESET             -> unchanged behavior
resolved getter        -> collection mount instruction
```

---

### 3. Router DOM mount

Module:

```text
ntx-router.js
```

No grammar logic should be added here. `ntx-router` should remain a thin mount
container that consumes `Router.resolved`.

Issue 001 tests should prove:

```html
#Product/@ -> <resolved-tag model="Product" router="main">
```

For a schema with:

```json
{
  "ui": {
    "renderer": {
      "page": "ntx-products-page",
      "list": "ntx-products"
    }
  }
}
```

the mounted tag should be:

```html
<ntx-products-page model="Product" router="main"></ntx-products-page>
```

For no schema renderer, fallback remains:

```html
<ntx-list model="Product" router="main"></ntx-list>
```

---

### 4. Backend ViewableMixin route ownership

Module:

```text
n3tx-ui ViewableMixin
```

Add a route-registration method to `ViewableMixin` so view-capable models own
their HTML route grammar.

Recommended interface:

```python
class ViewableMixin:
    @classmethod
    def register_view_routes(cls, router, *, tag: str) -> None:
        ...
```

For issue 001 this method registers exactly:

```text
GET /{cls.__name__}/@
```

with:

```python
include_in_schema=False
```

The route returns an `HTMLResponse` generated by a helper.

#### Why classmethod on mixin?

The model class already carries:

```text
cls.__name__
cls.__ui__
cls.schema()
```

so the view-route capability has everything it needs to register routes without
duplicating knowledge in `routes_fastapi.py`.

#### Why not register for every model?

Only viewable models should expose HTML view routes. This mirrors how only
storable models expose CRUD/data routes.

---

### 5. Backend route registrar delegation

Module:

```text
routes_fastapi.register_routes()
```

Add a small delegation point after the schema route and before generic data
routes where relevant:

```python
router.get(f"/{model_class.__name__}", tags=[tag])(make_get_schema(model_class))

register_view_routes = getattr(model_class, 'register_view_routes', None)
if callable(register_view_routes):
    register_view_routes(router, tag=tag)
```

For issue 001, route-order risk is low because `/Product/@` is exact and
`/Product` remains exact. Still, putting view routes immediately after schema
registration establishes the intended order for later slices.

---

### 6. HTML rendering helper

Module options:

```text
n3tx-ui-owned helper, because ViewableMixin owns view routes
```

or:

```text
n3tx-core SSR helper, if kept package-neutral
```

Given the package boundary, the recommended issue-001 shape is:

```text
n3tx-ui provides view route registration
n3tx-core may provide package-neutral HTML shell utilities only if needed
```

For the first slice, the helper can be intentionally small:

```python
def render_model_collection_view(model_class: type) -> HTMLResponse:
    ...
```

It should emit deterministic HTML containing enough to bootstrap the normal
frontend runtime, and at minimum include the mounted collection component:

```html
<ntx-list model="Product"></ntx-list>
```

or, if the schema declares a page/list renderer:

```html
<ntx-products-page model="Product"></ntx-products-page>
```

Renderer resolution for backend collection default should match frontend issue
001 behavior:

```text
renderer.page -> renderer.list -> ntx-list
```

Important: this is **not** server-side component rendering. It is a shell that
boots the existing frontend component system.

---

## Backend route flow

```text
create_app(...)
  |
  v
register_model(Product)
  |
  v
ProtoModel.__init_subclass__
  |
  +-- __ui__ or __viewable__ triggers ViewableMixin injection
  |
  v
routes_fastapi.register_routes()
  |
  +-- GET /Product -> schema
  |
  +-- Product.register_view_routes(router, tag='Products')
  |     |
  |     +-- GET /Product/@ -> HTML collection default view
  |
  +-- if StorableMixin: /products CRUD routes
```

---

## Test-first plan

### Frontend tests

Add or update tests in:

```text
tests/frontend/tests/core/route-functions.test.js
tests/frontend/tests/core/Router.test.js
tests/frontend/tests/components/ntx-router.test.js
```

#### Route function tests

Required assertions:

```javascript
expect(parseRoute('Product/@')).toEqual({
  type: 'model',
  model: 'Product',
  id: null,
  action: null,
  view: null,
  isViewRoute: true,
  params: {},
});

expect(buildRoute({
  type: 'model',
  model: 'Product',
  isViewRoute: true,
})).toBe('Product/@');

expect(buildRoute(parseRoute('Product/@'))).toBe('Product/@');
```

Resolver fallback order:

```javascript
resolveRoute(parseRoute('Product/@'), () => ({
  ui: { renderer: { page: 'ntx-products-page', list: 'ntx-products' } }
})).tag === 'ntx-products-page'

resolveRoute(parseRoute('Product/@'), () => ({
  ui: { renderer: { list: 'ntx-products' } }
})).tag === 'ntx-products'

resolveRoute(parseRoute('Product/@'), () => null).tag === 'ntx-list'
```

Legacy assertions remain:

```javascript
parseRoute('Product')          -> model
parseRoute('Product/1')        -> detail
parseRoute('Product/1/run')    -> action
parseRoute('@profile')         -> app
```

#### Router state tests

Required assertions:

```javascript
router.NAVIGATE('Product/@')
router.current === 'Product/@'
window.location.hash === '#Product/@'
```

Also test:

```text
initial hash '#Product/@' does not create fake back history
resolved getter returns collection mount instruction
```

#### Router DOM tests

Required assertions:

```text
deep-link #Product/@ mounts collection component
mounted component gets model="Product"
mounted collection component gets router attr when it has model attr
deep-linked route has hidden chrome when no back history
```

---

### Backend tests

Add or update tests in the most focused location:

```text
packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

Recommended split:

1. `n3tx-ui` tests verify `ViewableMixin` owns the route registration method.
2. `n3tx-core` route tests verify `routes_fastapi.register_routes()` delegates
   to any model class with `register_view_routes` without importing `n3tx_ui`.
3. A direct TestClient behavior test verifies `/Product/@` returns HTML when
   `n3tx_ui` is imported and the model is viewable.

#### ViewableMixin route ownership tests

Required assertions:

```text
Model with __ui__ is subclass of ViewableMixin
ViewableMixin exposes register_view_routes
register_view_routes registers GET /Product/@
registered route is include_in_schema=False
```

#### Direct route behavior tests

Required assertions:

```text
GET /Product/@ -> 200
Content-Type includes text/html
HTML contains collection component with model="Product"
GET /Product -> still returns JSON Schema
GET /products -> legacy collection route still works for storable models
```

For a schema with:

```python
__ui__ = {'renderer': {'page': 'ntx-products-page', 'list': 'ntx-products'}}
```

HTML should contain:

```html
<ntx-products-page model="Product">
```

For no renderer but viewable model:

```html
<ntx-list model="Product">
```

---

## Implementation steps

### Step 1 — Red: frontend route tests

Add failing tests for `Product/@` parser, builder, resolver, router state, and
DOM mount behavior.

Expected failure before implementation:

```text
Product/@ parses as detail id='@'
```

### Step 2 — Green: frontend route functions

Update `Router.js` route functions:

1. Keep root `@profile` handling first.
2. Split query params as today.
3. Normalize path enough for `Product/@`.
4. Detect collection default view when second segment is exactly `@`.
5. Add `isViewRoute` and `view` fields.
6. Extend `buildRoute()` for view routes.
7. Extend `resolveRoute()` default collection view fallback order.

### Step 3 — Red: backend ViewableMixin tests

Add failing tests proving route ownership belongs to `ViewableMixin`, not generic
route registration.

Expected failure before implementation:

```text
ViewableMixin has no register_view_routes method
GET /Product/@ is 404 or static fallback
```

### Step 4 — Green: ViewableMixin route registration

Add `register_view_routes()` to `ViewableMixin`.

For issue 001, it registers only:

```text
GET /{ClassName}/@
```

and calls a helper that renders the collection default component.

### Step 5 — Green: direct route registrar delegation

Update `routes_fastapi.register_routes()` to call `model_class.register_view_routes`
when present.

The core registrar remains package-neutral: no hard import of `n3tx_ui`.

### Step 6 — Verify focused suites

Run:

```bash
cd /workspace/tests/frontend && npx vitest run tests/core/route-functions.test.js tests/core/Router.test.js tests/components/ntx-router.test.js
cd /workspace && python3 -m pytest packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py -q
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py -q
```

If a new backend behavior test file is added, run it explicitly too.

---

## Non-goals for this issue

- Named collection views such as `Product/@table`
- Member views such as `Product/1/@`
- Class-name read mirrors such as `/Product/1`
- Actor routing parity
- Sidebar link generation changes
- Browser E2E route smoke
- Full security policy for arbitrary view names
- `$id` migration
- Class-name CRUD write mirrors

---

## Open implementation questions

These do not block the plan, but should be decided during implementation if the
code makes one option clearly better:

1. Should the HTML helper live in `n3tx_ui.routes` / `n3tx_ui.views`, or in a
   package-neutral `n3tx_core.ssr` helper used by `ViewableMixin`?
2. Should `/Product/@` include only a mounted component, or should it reuse the
   full app index shell when one is available?
3. Should SSR schema injection be preserved for `/Product/@` in issue 001, or
   deferred until the broader HTML route slice?

Recommended default for issue 001:

- Keep helper ownership close to `ViewableMixin` in `n3tx-ui`.
- Emit deterministic shell HTML sufficient for tests and bootstrapping.
- Defer rich SSR/index-shell reuse until later unless it is already trivial.

---

## Acceptance checklist

- [ ] `Product/@` parses as collection default view route.
- [ ] `Product/@` builds from parsed/structured route data.
- [ ] `Product/@` resolves through `renderer.page -> renderer.list -> ntx-list`.
- [ ] Router hash sync works for `#Product/@`.
- [ ] Router duplicate navigation/back/reset behavior remains unchanged.
- [ ] `ntx-router` mounts the resolved collection component for `#Product/@`.
- [ ] Viewable models own backend view route registration.
- [ ] `routes_fastapi` delegates view route registration without hard importing `n3tx_ui`.
- [ ] `/Product/@` returns `text/html` for viewable models.
- [ ] `/Product` remains the schema endpoint.
- [ ] Legacy `#Product` and `/products` behavior remains unchanged.
