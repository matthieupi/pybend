# Issue 003 Plan: Member Default View and Class-Name Read Mirror

## Goal

Deliver the first complete member route path in the new hypermedia grammar:

```text
#Product/1/@  -> frontend member default view route
/Product/1    -> backend class-name read mirror for /products/1
/Product/1/@  -> backend HTML member default view route
```

This issue introduces two related but distinct backend capabilities:

```text
StorableMixin  -> class-name read mirror for entity data
ViewableMixin  -> member default HTML/view route
```

The design keeps capability ownership aligned:

- A class-name data read mirror exists because a model is storable.
- A member HTML route exists because a model is viewable.

The identity contract does not change in this issue:

```text
$schema -> class-name schema URL
$id     -> existing table-name instance URL
```

---

## Depends on prior issues

Issue 003 assumes the previous route grammar work has established:

```text
#Product/@      -> collection default view route
#Product/@table -> named collection view route
/Product/@      -> collection default HTML route via ViewableMixin
/Product/@table -> named collection HTML route via ViewableMixin
```

and that backend view routes are registered through a capability hook such as:

```python
class ViewableMixin:
    @classmethod
    def register_view_routes(cls, router, *, tag: str) -> None:
        ...
```

Issue 003 extends that hook for member default HTML routes and adds a separate
storable capability path for class-name read mirrors.

---

## Scope for issue 003

Implement:

```text
Frontend:
  {ClassName}/{id}/@

Backend direct routes:
  GET /{ClassName}/{id:int}
  GET /{ClassName}/{id:int}/@
```

Examples:

```text
Product/1/@
GET /Product/1
GET /Product/1/@
```

Do **not** implement yet:

```text
Product/1/@item
Product/1/@detail
Product/1/@chat
Product/1/@run
GET /{ClassName}/{id:int}/@{view}
GET /{ClassName}/{id:int}/{method}
POST /{ClassName}/{id:int}
PUT /{ClassName}/{id:int}
DELETE /{ClassName}/{id:int}
actor routing parity
sidebar migration
browser E2E smoke
$id migration
```

---

## Core behavior contract

### Frontend member default route

```text
Product/1/@
```

means:

```text
Model: Product
ID: 1
View: default member view
```

It is not:

```text
action = '@'
method = '@'
collection route
```

### Member default renderer resolution

Member default views resolve in this order:

```text
1. schema.ui.renderer.detail
2. schema.ui.renderer.item
3. ntx-item
```

Mounted attrs:

```javascript
{
  ref: 'Product/1',
  display: 'lg'
}
```

Query params should pass through except internal route controls:

```text
Product/1/@?tab=history
  -> attrs: { ref: 'Product/1', display: 'lg', tab: 'history' }
```

Named member views remain issue 004.

### Backend class-name read mirror

```text
GET /Product/1
```

mirrors:

```text
GET /products/1
```

The mirror must reuse the same read, authorization, population, and
serialization behavior as the table-name route.

Required invariant:

```text
GET /Product/1 and GET /products/1 return the same domain entity data.
```

Allowed identity shape for this phase:

```json
{
  "$schema": ".../Product",
  "$id": ".../products/1"
}
```

### Backend member HTML route

```text
GET /Product/1/@
```

returns HTML that mounts or bootstraps the member default view:

```html
<ntx-item ref="Product/1" display="lg"></ntx-item>
```

or schema-selected equivalent:

```html
<ntx-product-detail ref="Product/1" display="lg"></ntx-product-detail>
```

It must not return JSON by accident, and it must not shadow `/Product/1`.

---

## Capability ownership

### 1. StorableMixin owns class-name data read mirrors

Issue 003 should avoid treating `/Product/1` as a generic route added for every
registered model. Only storable models should expose a class-name read mirror.

Recommended capability shape:

```python
class StorableMixin:
    @classmethod
    def register_data_mirror_routes(cls, router, *, tag: str, read_handler_factory) -> None:
        ...
```

or a narrower issue-003 shape:

```python
class StorableMixin:
    @classmethod
    def register_class_read_route(cls, router, *, tag: str, read_handler) -> None:
        ...
```

However, because `StorableMixin` currently does not own route registration in
the existing system, there are two acceptable implementation paths:

#### Preferred path

Move toward capability-owned route registration:

```text
StorableMixin.register_data_routes(...)       -> future CRUD ownership
StorableMixin.register_class_read_route(...)  -> issue 003 mirror
ViewableMixin.register_view_routes(...)       -> HTML/view ownership
```

For issue 003, implement only the class-name read mirror method if a full CRUD
route ownership refactor would be too large.

#### Minimal compatibility path

Keep the actual route registration in `routes_fastapi.py` for now, but express
the ownership through a small helper name and tests:

```python
if is_storable:
    router.get(f"/{model_class.__name__}/{{id:int}}", tags=[tag])(
        make_get_instance(model_class)
    )
```

This is acceptable only if tests and comments clearly mark it as a storable
capability mirror and no non-storable model receives it.

Recommendation: use the narrow capability method if it can be introduced with
low churn; otherwise use the minimal compatibility path and leave full
StorableMixin route ownership for a dedicated cleanup.

### 2. ViewableMixin owns member HTML routes

Extend `ViewableMixin.register_view_routes()`:

```text
GET /{ClassName}/@          -> collection default view       (issue 001)
GET /{ClassName}/@{view}    -> named collection view         (issue 002)
GET /{ClassName}/{id:int}/@ -> member default view           (issue 003)
```

Do not add:

```text
GET /{ClassName}/{id:int}/@{view}
```

until issue 004.

---

## Route registration order

The target direct route order per model after issue 003 should be:

```text
GET /{ClassName}                         schema
GET /{ClassName}/@                       collection default HTML
GET /{ClassName}/@{view}                 collection named HTML
GET /{ClassName}/{id:int}/@              member default HTML
GET /{ClassName}/{id:int}                class-name read mirror

existing /{tablename}/... routes remain registered as today
```

Why this order matters:

- `/Product/@table` must match collection HTML, not an ID route.
- `/Product/1/@` must match member HTML, not a future method route.
- `/Product/1` must match the class-name read mirror.

Use `{id:int}` for class-name read mirrors and member view routes so `@table`
cannot be parsed as an ID.

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

#### Parser behavior

```javascript
parseRoute('Product/1/@')
```

returns:

```javascript
{
  type: 'detail',
  model: 'Product',
  id: '1',
  action: null,
  view: null,
  isViewRoute: true,
  params: {},
}
```

Legacy behavior remains:

```javascript
parseRoute('Product/1')
  -> { type: 'detail', model: 'Product', id: '1', action: null }

parseRoute('Product/1/run')
  -> { type: 'action', model: 'Product', id: '1', action: 'run' }
```

#### Builder behavior

```javascript
buildRoute({
  type: 'detail',
  model: 'Product',
  id: '1',
  isViewRoute: true,
})
```

returns:

```text
Product/1/@
```

With params:

```javascript
buildRoute({
  type: 'detail',
  model: 'Product',
  id: '1',
  isViewRoute: true,
  params: { tab: 'history' },
})
```

returns:

```text
Product/1/@?tab=history
```

#### Resolver behavior

Use the same internal view-tag helper introduced in issues 001/002, now with
member scope:

```javascript
resolveViewTag(schema, null, 'member')
```

Member default logic:

```text
renderer.detail -> renderer.item -> ntx-item
```

Result:

```javascript
{
  tag: 'ntx-product-detail',
  attrs: { ref: 'Product/1', display: 'lg' },
  title: 'Product'
}
```

if schema declares:

```json
{
  "ui": {
    "renderer": {
      "detail": "ntx-product-detail",
      "item": "ntx-product-card"
    }
  }
}
```

Fallback when no schema renderer:

```javascript
{ tag: 'ntx-item', attrs: { ref: 'Product/1', display: 'lg' } }
```

---

### 2. Router state actor

No new state model is needed. Add tests proving `Product/1/@` behaves like a
normal route string:

```text
NAVIGATE('Product/1/@') -> current 'Product/1/@'
hash sync              -> #Product/1/@
duplicate route         -> no-op
BACK/RESET              -> unchanged behavior
initial hash load       -> no fake back history
resolved getter         -> member mount instruction
```

---

### 3. Router DOM mount

`ntx-router` should remain grammar-free and consume `Router.resolved`.

Test mount behavior:

```text
#Product/1/@ -> <schema-selected-detail-tag ref="Product/1" display="lg">
```

Important issue-003 assertion:

```text
member view components do not receive method="@"
```

---

### 4. Backend direct class-name read mirror

Primary route:

```text
GET /{ClassName}/{id:int}
```

This should call the same logical handler as:

```text
GET /{tablename}/{id:int}
```

Recommended low-duplication approach:

```python
read_instance = make_get_instance(model_class)

router.get(f"{endpoint_base}/{{id:int}}", tags=[tag])(read_instance)
router.get(f"/{model_class.__name__}/{{id:int}}", tags=[tag])(read_instance)
```

This works because `make_get_instance(model_class)` already owns:

```text
model_class.get(id, populate=...)
404 behavior
serialization through model_response()
```

If FastAPI handler reuse creates naming/OpenAPI conflicts, wrap it with a thin
delegating handler that calls the same inner logic. Do not duplicate the read
logic itself.

The mirror should be GET-only for this phase.

---

### 5. Backend ViewableMixin member default route

Extend `ViewableMixin.register_view_routes()`:

```python
@router.get(f"/{cls.__name__}/{{id:int}}/@", include_in_schema=False)
async def member_default_view(id: int):
    return render_model_member_view(cls, id=id, view=None)
```

Helper behavior:

```python
def resolve_member_view_tag(model_class: type, view: str | None) -> str:
    renderer = (getattr(model_class, '__ui__', None) or {}).get('renderer', {})
    if view is None:
        return renderer.get('detail') or renderer.get('item') or 'ntx-item'
    ... # named member views deferred to issue 004
```

HTML contains:

```html
<{tag} ref="Product/1" display="lg"></{tag}>
```

Do not perform a backend existence check for `/Product/1/@` unless the existing
view-route design has already chosen backend 404s for missing IDs. The current
short-term HTML route design can return a shell and let the frontend handle the
data fetch. If adding an existence check is trivial and desired, it must be
consistent with the documented behavior and tested.

Recommended issue-003 default:

```text
/Product/1/@ returns shell HTML for any integer id; frontend entity load handles missing data.
```

This keeps the HTML route a view entrypoint, not a data read endpoint.

---

## Test-first plan

### Frontend route function tests

Update:

```text
tests/frontend/tests/core/route-functions.test.js
```

Parser tests:

```javascript
expect(parseRoute('Product/1/@')).toEqual({
  type: 'detail',
  model: 'Product',
  id: '1',
  action: null,
  view: null,
  isViewRoute: true,
  params: {},
});
```

Builder tests:

```javascript
expect(buildRoute({
  type: 'detail', model: 'Product', id: '1', isViewRoute: true,
})).toBe('Product/1/@');

expect(buildRoute(parseRoute('Product/1/@'))).toBe('Product/1/@');
```

Resolver tests:

```javascript
const schema = { ui: { renderer: { detail: 'ntx-product-detail', item: 'ntx-product-card' } } };
const r = resolveRoute(parseRoute('Product/1/@'), () => schema);
expect(r.tag).toBe('ntx-product-detail');
expect(r.attrs).toEqual({ ref: 'Product/1', display: 'lg' });
expect(r.attrs.method).toBeUndefined();

const fallback = resolveRoute(parseRoute('Product/1/@'), () => null);
expect(fallback.tag).toBe('ntx-item');
```

Regression tests:

```javascript
expect(parseRoute('Product/1').type).toBe('detail');
expect(parseRoute('Product/1/run').type).toBe('action');
expect(resolveRoute(parseRoute('Product/1/run'), getSchema).attrs.method).toBe('run');
```

---

### Router state tests

Update:

```text
tests/frontend/tests/core/Router.test.js
tests/frontend/tests/integration/router-navigation.test.js
```

Required assertions:

```text
NAVIGATE('Product/1/@') sets current and hash
initial #Product/1/@ does not create fake back history
BACK from Product/1/@ returns to previous route
resolved getter returns member tag/ref/display
```

---

### Router DOM tests

Update:

```text
tests/frontend/tests/components/ntx-router.test.js
```

Required assertions:

```text
deep-link #Product/1/@ mounts schema-selected detail tag
mounted element has ref="Product/1"
mounted element has display="lg"
mounted element does not have method attr
deep-linked member view has hidden chrome when no back history
```

---

### Backend route generation and behavior tests

Use focused route tests in:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

or a new direct route test file if clearer.

#### Route generation tests

Required route paths:

```text
/Product                         schema
/Product/@                       collection default HTML
/Product/@{view}                 collection named HTML
/Product/{id:int}/@              member default HTML
/Product/{id:int}                class-name read mirror
/products                        table-name list/create
/products/{id:int}               table-name read/update/delete
```

Do not generate:

```text
POST /Product/{id:int}
PUT /Product/{id:int}
DELETE /Product/{id:int}
```

#### Class-name read mirror behavior tests

Required assertions:

```text
GET /Product/1 returns 200 for an existing product
GET /Product/1 returns same domain fields as GET /products/1
GET /Product/1 preserves $schema ending in /Product
GET /Product/1 preserves $id ending in /products/1
GET /Product/999999 mirrors table-name 404 behavior
GET /Product/not-an-int does not match the class-name read mirror
GET /Product/1?populate=comments&depth=1 forwards query behavior
auth behavior mirrors table-name read behavior
```

#### Member HTML behavior tests

Required assertions:

```text
GET /Product/1/@ returns 200 text/html
HTML contains ref="Product/1"
HTML contains display="lg"
HTML contains renderer.detail when declared
HTML falls back to renderer.item, then ntx-item
GET /Product/1/@ does not shadow GET /Product/1
GET /Product/@table still hits collection named HTML route
GET /Product remains schema
```

---

## Implementation steps

### Step 1 — Red: frontend member default route tests

Add failing tests for `Product/1/@` parser, builder, resolver, router state, and
DOM mount behavior.

Expected failure before implementation:

```text
Product/1/@ parses as action route with action='@'
```

### Step 2 — Green: frontend member default grammar

Update `Router.js`:

1. Detect third segment exactly `@` as a detail view route.
2. Return `type: 'detail'`, `view: null`, `isViewRoute: true`.
3. Extend `buildRoute()` for detail view routes.
4. Extend `resolveViewTag()` for member default scope.
5. Make `resolveRoute()` use member view resolution when `parsed.isViewRoute`.
6. Ensure no `method` attr is emitted for member view routes.

### Step 3 — Red: backend route tests

Add failing tests for:

```text
GET /Product/1
GET /Product/1/@
```

Expected failures before implementation:

```text
/Product/1 returns 404 or static fallback
/Product/1/@ returns 404
```

### Step 4 — Green: class-name read mirror

Register GET-only class-name read mirror for storable models. Prefer reusing the
same handler produced by `make_get_instance(model_class)`.

Do not add write mirrors.

### Step 5 — Green: ViewableMixin member default route

Extend `ViewableMixin.register_view_routes()` with:

```text
GET /{ClassName}/{id:int}/@
```

and a member HTML helper that resolves:

```text
renderer.detail -> renderer.item -> ntx-item
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

- Named member views such as `Product/1/@item`
- Method/view collision route `Product/1/@run`
- Actor route parity
- Sidebar selected-state or link migration
- Browser E2E smoke
- Backend unsafe view-token policy beyond routes already introduced
- `$id` migration to class-name URLs
- Class-name create/update/delete mirrors
- Class-name method mirrors

---

## Acceptance checklist

- [ ] `Product/1/@` parses as a detail view route.
- [ ] `Product/1/@` builds and round-trips canonically.
- [ ] `Product/1/@` resolves through `renderer.detail -> renderer.item -> ntx-item`.
- [ ] `Product/1/@` resolved attrs include `ref="Product/1"` and `display="lg"`.
- [ ] `Product/1/@` resolved attrs do not include `method`.
- [ ] Router hash sync works for `#Product/1/@`.
- [ ] `ntx-router` mounts the resolved member component for `#Product/1/@`.
- [ ] `/Product/1` mirrors `/products/1` for GET reads.
- [ ] `/Product/1` preserves `$schema` as class-name based.
- [ ] `/Product/1` preserves `$id` as table-name based.
- [ ] `/Product/1` preserves populate/depth query behavior.
- [ ] `/Product/999999` mirrors table-name not-found behavior.
- [ ] POST/PUT/DELETE `/Product/1` are not added.
- [ ] `/Product/1/@` returns `text/html`.
- [ ] `/Product/1/@` does not shadow `/Product/1`.
- [ ] `/Product/@table` and `/Product` still route correctly.
