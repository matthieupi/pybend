# Issue 004 Plan: Named Member Views and Method/View Collision

## Goal

Complete the member view grammar by adding named member views and locking the
critical method-vs-view distinction:

```text
#Product/1/@item   -> member view named "item"
#Product/1/@detail -> member view named "detail"
#Product/1/@chat   -> member view named "chat"
#Product/1/@run    -> member view named "run"

#Product/1/run     -> method/action route named "run"
```

Backend parity for view entrypoints:

```text
GET /Product/1/@item -> HTML member view route
GET /Product/1/@run  -> HTML member view route, not method route
```

Legacy method routes remain table-name based:

```text
POST /products/1/run -> method/action route
```

This is the most important grammar-collision slice: `@` is the explicit marker
for view/html/component routes, while the same segment without `@` remains an
action/method route.

---

## Depends on issue 003

Issue 004 assumes issue 003 has established:

```text
#Product/1/@ -> member default view route
/Product/1   -> class-name read mirror
/Product/1/@ -> member default HTML route via ViewableMixin
```

Issue 004 extends only the member view route shape:

```text
Product/1/@{view}
GET /Product/1/@{view}
```

It does not introduce class-name method mirrors.

---

## Scope for issue 004

Implement:

```text
Frontend:
  {ClassName}/{id}/@{view}

Backend direct routes:
  GET /{ClassName}/{id:int}/@{view}
```

Examples:

```text
Product/1/@item
Product/1/@detail
Product/1/@chat
Product/1/@custom-card
Product/1/@run

GET /Product/1/@item
GET /Product/1/@run
```

Preserve:

```text
Product/1/run        -> frontend action route
POST /products/1/run -> existing backend table-name method route
```

Do **not** implement:

```text
GET /Product/1/run       # class-name method mirror
POST /Product/1/run      # class-name method mirror
class-name CRUD writes
actor routing parity
sidebar migration
browser E2E smoke
strict unsafe view-token policy from issue 005
```

---

## Core behavior contract

### Semantic rule

These two routes are intentionally different:

```text
Product/1/run   -> action route named "run"
Product/1/@run  -> member view route named "run"
```

The first invokes or mounts method/action UI. The second asks for a UI
projection named `run` and must never receive `method="run"`.

### Frontend parser contract

```javascript
parseRoute('Product/1/@item')
```

returns:

```javascript
{
  type: 'detail',
  model: 'Product',
  id: '1',
  action: null,
  view: 'item',
  isViewRoute: true,
  params: {},
}
```

Collision assertion:

```javascript
parseRoute('Product/1/run')
  -> { type: 'action', action: 'run', isViewRoute: false/undefined }

parseRoute('Product/1/@run')
  -> { type: 'detail', view: 'run', isViewRoute: true, action: null }
```

### Frontend resolver contract

Named member views resolve in this order:

```text
1. schema.ui.renderer[view]
2. framework fallback for known member views
3. ergonomic ntx-${view} fallback for safe custom view names
```

Known member fallbacks:

```text
item   -> renderer.item if present, else ntx-item
detail -> renderer.detail or renderer.item if present, else ntx-item
chat   -> ntx-chat
```

Custom safe fallbacks:

```text
custom-card     -> ntx-custom-card
ntx-custom-card -> ntx-custom-card
run             -> ntx-run unless schema.renderer.run exists
```

Resolved member view attrs:

```javascript
{
  ref: 'Product/1',
  display: 'lg',
  ...passthroughParams
}
```

Must not include:

```javascript
method
view
isViewRoute
action
```

### Backend route contract

`ViewableMixin` owns member HTML routes:

```text
GET /{ClassName}/{id:int}/@        -> member default view       (issue 003)
GET /{ClassName}/{id:int}/@{view}  -> member named view         (issue 004)
```

The named member HTML route returns `text/html` and mounts/bootstraps:

```html
<{resolved-tag} ref="Product/1" display="lg"></{resolved-tag}>
```

For example:

```text
GET /Product/1/@item
  -> renderer.item -> ntx-item fallback

GET /Product/1/@chat
  -> renderer.chat -> ntx-chat fallback

GET /Product/1/@run
  -> renderer.run -> ntx-run fallback
```

`GET /Product/1/run` remains unavailable unless a later issue intentionally adds
class-name method mirrors.

---

## Route registration order

Target direct route order after issue 004:

```text
GET /{ClassName}                         schema
GET /{ClassName}/@                       collection default HTML
GET /{ClassName}/@{view}                 collection named HTML
GET /{ClassName}/{id:int}/@              member default HTML
GET /{ClassName}/{id:int}/@{view}        member named HTML
GET /{ClassName}/{id:int}                class-name read mirror

existing /{tablename}/... routes remain registered as today
```

Important route-order assertions:

```text
/Product/1/@item -> member HTML route, not method/action route
/Product/1/@run  -> member HTML route, not method/action route
/Product/1       -> class-name read mirror
/Product/@table  -> collection named HTML route
/Product         -> schema
```

Use `{id:int}` so `@table` can never be captured as an ID.

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

Extend issue 003’s third-segment `@` detection:

```javascript
third === '@'              -> view: null
third?.startsWith('@')     -> view: third.slice(1)
```

Examples:

```javascript
parseRoute('Product/1/@item').view === 'item'
parseRoute('Product/1/@detail').view === 'detail'
parseRoute('Product/1/@chat').view === 'chat'
parseRoute('Product/1/@custom-card').view === 'custom-card'
parseRoute('Product/1/@run').view === 'run'
```

Normalization:

```text
/Product/1/@item/ -> Product/1/@item
```

More complex malformed-route behavior remains issue 005 unless already handled
cleanly by the current parser.

#### Builder behavior

```javascript
buildRoute({
  type: 'detail',
  model: 'Product',
  id: '1',
  isViewRoute: true,
  view: 'item',
})
```

returns:

```text
Product/1/@item
```

With params:

```javascript
buildRoute({
  type: 'detail',
  model: 'Product',
  id: '1',
  isViewRoute: true,
  view: 'chat',
  params: { thread: 'abc' },
})
```

returns:

```text
Product/1/@chat?thread=abc
```

#### Resolver behavior

Extend the internal view resolver for member named views:

```javascript
resolveViewTag(schema, view, 'member')
```

Recommended logic:

```javascript
const renderer = schema?.ui?.renderer || {};

if (view && renderer[view]) return renderer[view];

if (!view) return renderer.detail || renderer.item || 'ntx-item';

const known = {
  item: renderer.item || 'ntx-item',
  detail: renderer.detail || renderer.item || 'ntx-item',
  chat: 'ntx-chat',
};

if (known[view]) return known[view];
return view.startsWith('ntx-') ? view : `ntx-${view}`;
```

Action routes remain separate:

```javascript
if (parsed.type === 'action') {
  // existing method renderer behavior
  attrs.method = parsed.action;
}
```

Member view routes must never pass through `method`.

---

### 2. Router state actor

No new state machinery is needed. Add tests proving named member view route
strings behave normally:

```text
NAVIGATE('Product/1/@item') -> current 'Product/1/@item'
hash sync                  -> #Product/1/@item
duplicate route             -> no-op
BACK/RESET                  -> unchanged behavior
initial hash load           -> no fake back history
resolved getter             -> member named view mount instruction
```

Add an explicit collision state test:

```text
Product/1/run and Product/1/@run are different current route strings and resolve differently.
```

---

### 3. Router DOM mount

`ntx-router` remains grammar-free and consumes `Router.resolved`.

DOM assertions:

```text
#Product/1/@item mounts schema-selected item tag
#Product/1/@chat mounts schema-selected chat tag or ntx-chat fallback
#Product/1/@run mounts view tag, not method component
```

Critical attr assertion:

```text
mounted member view for #Product/1/@run has no method attr
```

---

### 4. Backend ViewableMixin member named route

Extend `ViewableMixin.register_view_routes()` from issue 003:

```python
@router.get(f"/{cls.__name__}/{{id:int}}/@{{view}}", include_in_schema=False)
async def member_named_view(id: int, view: str):
    return render_model_member_view(cls, id=id, view=view)
```

The helper should now support named member views:

```python
def resolve_member_view_tag(model_class: type, view: str | None) -> str:
    renderer = (getattr(model_class, '__ui__', None) or {}).get('renderer', {})

    if view and renderer.get(view):
        return renderer[view]

    if view is None:
        return renderer.get('detail') or renderer.get('item') or 'ntx-item'

    known = {
        'item': renderer.get('item') or 'ntx-item',
        'detail': renderer.get('detail') or renderer.get('item') or 'ntx-item',
        'chat': 'ntx-chat',
    }
    if view in known:
        return known[view]

    return view if view.startswith('ntx-') else f'ntx-{view}'
```

This should match frontend resolver behavior for member views.

### 5. Backend method route preservation

Do not register class-name method mirrors in this issue.

Existing table-name method routes remain as they are:

```text
POST /products/{id:int}/run
```

Test expectations:

```text
GET /Product/1/@run      -> HTML view route
GET /Product/1/run       -> not found or method-not-allowed, depending current router fallback
POST /products/1/run     -> existing method handler still works
```

The exact status for `GET /Product/1/run` should be tested against the chosen
non-mirror behavior, but the key invariant is that it is not treated as the view
route and not added as a successful method mirror.

---

## Test-first plan

### Frontend route function tests

Update:

```text
tests/frontend/tests/core/route-functions.test.js
```

Parser tests:

```javascript
expect(parseRoute('Product/1/@item')).toMatchObject({
  type: 'detail', model: 'Product', id: '1', view: 'item', isViewRoute: true,
});

expect(parseRoute('Product/1/@detail')).toMatchObject({ view: 'detail' });
expect(parseRoute('Product/1/@chat')).toMatchObject({ view: 'chat' });
expect(parseRoute('Product/1/@custom-card')).toMatchObject({ view: 'custom-card' });
expect(parseRoute('Product/1/@run')).toMatchObject({ type: 'detail', view: 'run', isViewRoute: true });

expect(parseRoute('Product/1/run')).toMatchObject({ type: 'action', action: 'run' });
```

Builder tests:

```javascript
expect(buildRoute({
  type: 'detail', model: 'Product', id: '1', isViewRoute: true, view: 'item'
})).toBe('Product/1/@item');

expect(buildRoute(parseRoute('Product/1/@chat?thread=abc')))
  .toBe('Product/1/@chat?thread=abc');
```

Resolver tests:

```javascript
const schema = {
  ui: { renderer: {
    item: 'ntx-product-card',
    detail: 'ntx-product-detail',
    chat: 'ntx-product-chat',
    run: 'ntx-run-view',
  }},
  methods: { run: { ui: { renderer: 'ntx-run-method' } } },
};

expect(resolveRoute(parseRoute('Product/1/@item'), () => schema).tag)
  .toBe('ntx-product-card');
expect(resolveRoute(parseRoute('Product/1/@detail'), () => schema).tag)
  .toBe('ntx-product-detail');
expect(resolveRoute(parseRoute('Product/1/@chat'), () => schema).tag)
  .toBe('ntx-product-chat');

const action = resolveRoute(parseRoute('Product/1/run'), () => schema);
expect(action.tag).toBe('ntx-run-method');
expect(action.attrs.method).toBe('run');

const view = resolveRoute(parseRoute('Product/1/@run'), () => schema);
expect(view.tag).toBe('ntx-run-view');
expect(view.attrs.method).toBeUndefined();
```

Fallback tests:

```javascript
expect(resolveRoute(parseRoute('Product/1/@item'), () => null).tag).toBe('ntx-item');
expect(resolveRoute(parseRoute('Product/1/@detail'), () => null).tag).toBe('ntx-item');
expect(resolveRoute(parseRoute('Product/1/@chat'), () => null).tag).toBe('ntx-chat');
expect(resolveRoute(parseRoute('Product/1/@custom'), () => null).tag).toBe('ntx-custom');
```

Query param test:

```javascript
const r = resolveRoute(parseRoute('Product/1/@chat?thread=abc&method=run'), () => schema);
expect(r.attrs.thread).toBe('abc');
expect(r.attrs.method).toBeUndefined();
```

---

### Router state and integration tests

Update:

```text
tests/frontend/tests/core/Router.test.js
tests/frontend/tests/integration/router-navigation.test.js
```

Required assertions:

```text
NAVIGATE('Product/1/@item') sets current and hash
initial #Product/1/@item does not create fake back history
duplicate Product/1/@item is a no-op
BACK from Product/1/@item returns to previous route
resolved getter returns member named view tag/ref/display
Product/1/run and Product/1/@run resolve to different mount instructions
```

---

### Router DOM tests

Update:

```text
tests/frontend/tests/components/ntx-router.test.js
```

Required assertions:

```text
deep-link #Product/1/@item mounts schema-selected item tag
deep-link #Product/1/@chat mounts schema-selected chat tag or fallback
deep-link #Product/1/@run mounts view tag with no method attr
legacy action route Product/1/run still mounts method/action route with method attr
member view route has ref="Product/1" and display="lg"
```

---

### Backend ViewableMixin tests

Update:

```text
packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py
```

Required assertions:

```text
register_view_routes registers /Product/{id:int}/@{view}
route is include_in_schema=False
member named helper resolves renderer.item for item
member named helper resolves renderer.detail for detail
member named helper resolves renderer.chat for chat
member named helper resolves renderer.run for run
fallback item/detail -> ntx-item
fallback chat -> ntx-chat
fallback custom -> ntx-custom
```

---

### Backend direct route behavior tests

Update or add focused direct route tests:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

Required assertions:

```text
GET /Product/1/@item -> 200 text/html
HTML contains ref="Product/1"
HTML contains display="lg"
HTML contains renderer.item tag when declared

GET /Product/1/@detail -> renderer.detail tag when declared
GET /Product/1/@chat   -> renderer.chat tag or ntx-chat fallback
GET /Product/1/@run    -> renderer.run tag or ntx-run fallback

GET /Product/1/@run hits HTML view route, not method route
GET /Product/1/run is not a successful class-name method mirror
POST /products/1/run legacy method route remains unchanged

GET /Product/1/@item does not shadow GET /Product/1
GET /Product/@table still hits collection named route
GET /Product remains schema
```

If the test model needs an exposed method, define a small test model with:

```python
@expose_route('/run', methods=['POST'])
def run(self): ...
```

and `__ui__.renderer.run = 'ntx-run-view'` to prove collision separation.

---

## Implementation steps

### Step 1 — Red: frontend named member tests

Add failing tests for parser, builder, resolver, router state, integration, and
DOM mount behavior for `Product/1/@item`, `Product/1/@chat`, and
`Product/1/@run`.

Expected failures before implementation:

```text
Product/1/@item parses as action route with action='@item'
Product/1/@run may be confused with method/action behavior
```

### Step 2 — Green: frontend named member grammar

Update `Router.js`:

1. Extend member view detection from `third === '@'` to also
   `third?.startsWith('@')`.
2. Return `view: null` for `@`, and `view: third.slice(1)` for `@item`.
3. Extend `buildRoute()` for detail view routes with named views.
4. Extend `resolveViewTag()` for member named views.
5. Ensure `resolveRoute()` omits `method` for all member view routes.
6. Preserve action-route behavior for non-`@` third segments.

### Step 3 — Red: backend named member tests

Add failing tests for:

```text
GET /Product/1/@item
GET /Product/1/@run
```

Expected failures before implementation:

```text
/Product/1/@item returns 404
/Product/1/@run returns 404 or wrong route
```

### Step 4 — Green: ViewableMixin named member route

Extend `ViewableMixin.register_view_routes()` with:

```text
GET /{ClassName}/{id:int}/@{view}
```

and generalize member HTML rendering to accept `view`.

### Step 5 — Green: route conflict protection

Ensure route registration order preserves:

```text
member named view before class-name read mirror
no class-name method mirror
legacy table-name methods unchanged
```

Add route-order/conflict tests.

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

- Actor routing parity
- Sidebar selected-state or link migration
- Browser E2E smoke
- Strict unsafe view-token policy from issue 005
- `$id` migration to class-name URLs
- Class-name create/update/delete mirrors
- Class-name method mirrors
- Changing existing table-name method route behavior

---

## Acceptance checklist

- [ ] `Product/1/@item`, `Product/1/@detail`, `Product/1/@chat`, and custom member views parse as detail view routes.
- [ ] `Product/1/@run` parses as a view route, not an action route.
- [ ] `Product/1/run` remains an action route.
- [ ] Named member view routes build and round-trip canonically.
- [ ] Named member view routes resolve through schema renderers before fallbacks.
- [ ] `Product/1/@item` falls back to `ntx-item` when no schema renderer exists.
- [ ] `Product/1/@detail` falls back to `renderer.item` or `ntx-item`.
- [ ] `Product/1/@chat` falls back to `ntx-chat`.
- [ ] `Product/1/@run` resolves to `renderer.run` or `ntx-run`, with no `method` attr.
- [ ] `Product/1/run` resolves as an action with `method="run"`.
- [ ] `ntx-router` mounts named member views with `ref` and `display` attrs.
- [ ] `ViewableMixin` owns backend named member view routes.
- [ ] `/Product/1/@item` returns `text/html`.
- [ ] `/Product/1/@run` hits the HTML view route, not a method route.
- [ ] `/Product/1/run` is not added as a class-name method mirror.
- [ ] Legacy `/products/1/run` method behavior remains unchanged.
- [ ] Member view routes do not shadow `/Product/1` read mirror.
