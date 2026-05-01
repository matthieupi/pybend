# Issue 006 Plan: Actor Routing Parity for Class-Name Mirrors and HTML View Routes

## Goal

Bring Level 3 actor-routed HTTP APIs to parity with the direct FastAPI route
grammar introduced by issues 001–004.

Direct routing now supports:

```text
GET /{ClassName}                         schema
GET /{ClassName}/@                       collection default HTML
GET /{ClassName}/@{view}                 collection named HTML
GET /{ClassName}/{id:int}/@              member default HTML
GET /{ClassName}/{id:int}/@{view}        member named HTML
GET /{ClassName}/{id:int}                class-name read mirror

/{tablename}/...                         legacy JSON API and methods
```

Actor routing should expose the same externally observable grammar for Level 3
apps while preserving actor-system semantics:

```text
HTTP request -> NetworkAPI route -> TX -> Matrix -> ActorModel handler
```

The important contract is parity without bypassing the actor data path for JSON
reads. HTML view routes are view entrypoints and should not send CRUD TXs unless
preloading is deliberately added later.

---

## Depends on prior issues

Issue 006 assumes issues 001–004 have established these direct-route behaviors:

```text
/Product/@
/Product/@table
/Product/1
/Product/1/@
/Product/1/@item
```

and that `ViewableMixin` owns view route registration through a capability hook
such as:

```python
model_class.register_view_routes(router, tag=tag)
```

Issue 006 reuses that same view-route capability in actor routing. It should not
move view routes into NetworkAPI-specific code when the model already owns the
view capability.

---

## Scope for issue 006

Implement actor-route parity for:

```text
GET /{ClassName}/{id:int}
GET /{ClassName}/@
GET /{ClassName}/@{view}
GET /{ClassName}/{id:int}/@
GET /{ClassName}/{id:int}/@{view}
```

Preserve actor-routed legacy routes:

```text
GET    /{ClassName}                    schema through schema TX
GET    /{tablename}                    list TX
POST   /{tablename}                    create TX
GET    /{tablename}/{id:int}           get TX
PUT    /{tablename}/{id:int}           update TX
DELETE /{tablename}/{id:int}           delete TX
POST   /{tablename}/{id:int}/{method}  method TX
```

Do **not** implement:

```text
POST /{ClassName}/{id:int}
PUT /{ClassName}/{id:int}
DELETE /{ClassName}/{id:int}
GET/POST /{ClassName}/{id:int}/{method}
actor-side SSR preloading
browser E2E smoke
sidebar migration
```

---

## Core behavior contract

### Class-name actor read mirror

```text
GET /MockModel/5
```

must dispatch the same logical TX as:

```text
GET /mock_models/5
```

Expected TX shape:

```python
TX(
    name='get',
    source='api',
    target='mock_models',
    data={'id': 5, ...query_params},
    meta={'user': user, 'model_cls': MockModel},
)
```

The mirror must preserve:

- target table-name actor address
- `id`
- `populate`
- `depth`
- request user metadata
- model class metadata
- `_response_or_raise()` error handling
- response body from the actor reply, including `$schema` and `$id`

Because actor replies are already serialized by the ActorModel handler, the
route must not rewrite identity fields. `$id` remains table-name based during
this migration.

### Actor HTML view routes

HTML routes should behave like direct routes:

```text
GET /MockModel/@
GET /MockModel/@table
GET /MockModel/5/@
GET /MockModel/5/@item
```

Expected behavior:

```text
200 text/html
ViewableMixin-rendered shell/component markup
No CRUD TX sent for basic shell rendering
```

These routes are not data routes. They bootstrap the frontend component system
and should not call `api_adapter.request()` unless a future preloading feature
explicitly chooses to do so.

### Route conflict contract

Actor route generation must preserve the same conflict rules as direct routes:

```text
/MockModel/@table   -> collection HTML route, not ID route
/MockModel/5/@item  -> member HTML route, not method route
/MockModel/5        -> class-name read mirror
/MockModel          -> schema route
/mock_models/5/custom -> legacy method route
/MockModel/5/custom -> not added in this issue
```

---

## Package boundary and capability ownership

`n3tx-actors` depends on `n3tx-core`, not `n3tx-ui`. Therefore NetworkAPI must
not hard-import `ViewableMixin` or n3tx-ui helper modules.

Use the same capability/protocol style as direct routing:

```python
register_view_routes = getattr(model_class, 'register_view_routes', None)
if callable(register_view_routes):
    register_view_routes(router, tag=tag)
```

This allows apps that import `n3tx_ui` before defining models with `__ui__` to
get view routes in both direct and actor modes, while keeping actor routing
package-neutral.

For class-name read mirrors, NetworkAPI can register the route directly because
it already owns actor-routed CRUD route generation. The mirror should be limited
to storable models:

```python
if is_storable:
    _register_class_read_mirror(...)
```

---

## Target actor route registration order

Inside `create_api_routes()` per model:

```text
1. GET /{ClassName}                         schema route
2. ViewableMixin routes, if model exposes register_view_routes:
   - GET /{ClassName}/@
   - GET /{ClassName}/@{view}
   - GET /{ClassName}/{id:int}/@
   - GET /{ClassName}/{id:int}/@{view}
3. GET /{ClassName}/{id:int}                class-name get mirror, if storable
4. Existing actor CRUD routes under /{tablename}/...
5. Existing custom methods under /{tablename}/...
```

Join/static collection routes remain first globally as they are today, so
existing parent-child route precedence is preserved.

Why order matters:

- View routes should be registered before future generic class-name routes.
- `{id:int}` prevents `@table` from being captured as an ID.
- No class-name method route is registered, so `/MockModel/5/custom` should not
  become successful by accident.

---

## Proposed module shape

### 1. NetworkAPI route generation

Module:

```text
packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

Add a helper for class-name read mirrors:

```python
def _register_class_read_mirror(router, api_adapter, model_class, tag):
    ...
```

Route:

```python
@router.get(f"/{model_class.__name__}/{{id:int}}", tags=[tag], name=f"get_{addr}_class")
async def get_instance_by_class(...):
    ... send TX(name='get', target=addr, data={'id': id, ...}, meta={...})
```

This should reuse the same data-payload construction as the existing table-name
`get_instance` route. If duplication appears, extract a tiny helper:

```python
def _read_data(id: int, populate: str | None, depth: int | None) -> dict:
    ...
```

Do not duplicate response/error handling; continue using `_response_or_raise()`.

### 2. View route delegation

Still in `create_api_routes()`:

```python
_register_schema_route(router, api_adapter, model_class, tag)

register_view_routes = getattr(model_class, 'register_view_routes', None)
if callable(register_view_routes):
    register_view_routes(router, tag=tag)

if is_storable:
    _register_class_read_mirror(...)
    _register_crud_routes(...)
```

The view routes should not know about `api_adapter` unless the capability method
interface later chooses to accept it. For this slice, ViewableMixin-generated
HTML shells are enough.

### 3. Test model viewability

Current NetworkAPI tests use `MockModel(StorableMixin, Actor)`, not real
`ProtoModel`/`ViewableMixin`. For route-generation and HTML-route tests, use one
of these approaches:

#### Option A — Protocol test model

Add a classmethod directly to `MockModel` in the test file:

```python
@classmethod
def register_view_routes(cls, router, *, tag):
    ... minimal test HTML routes ...
```

Pros:
- Tests NetworkAPI capability delegation without requiring n3tx-ui import.
- Keeps n3tx-actors package tests isolated.

Cons:
- Does not test real ViewableMixin rendering.

#### Option B — Real ViewableMixin integration test

Import `n3tx_ui` and define a model with `__ui__` so the real mixin injects.

Pros:
- Tests true integration.

Cons:
- Adds optional package coupling to n3tx-actors tests.

Recommendation:

```text
Use Option A in n3tx-actors unit tests to prove capability delegation.
Rely on n3tx-ui/direct route tests from issues 001–005 for real HTML rendering.
```

Example protocol route body for actor tests:

```python
from fastapi.responses import HTMLResponse

@classmethod
def register_view_routes(cls, router, *, tag):
    @router.get(f"/{cls.__name__}/@", include_in_schema=False)
    async def collection_default():
        return HTMLResponse(f'<ntx-list model="{cls.__name__}"></ntx-list>')

    @router.get(f"/{cls.__name__}/@{{view}}", include_in_schema=False)
    async def collection_named(view: str):
        return HTMLResponse(f'<ntx-{view} model="{cls.__name__}"></ntx-{view}>')

    @router.get(f"/{cls.__name__}/{{id:int}}/@", include_in_schema=False)
    async def member_default(id: int):
        return HTMLResponse(f'<ntx-item ref="{cls.__name__}/{id}" display="lg"></ntx-item>')

    @router.get(f"/{cls.__name__}/{{id:int}}/@{{view}}", include_in_schema=False)
    async def member_named(id: int, view: str):
        return HTMLResponse(f'<ntx-{view} ref="{cls.__name__}/{id}" display="lg"></ntx-{view}>')
```

This mirrors the capability surface without making NetworkAPI own view rendering.

---

## Test-first plan

### Route generation tests

Update:

```text
packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
```

Add route presence assertions:

```python
assert '/MockModel' in routes
assert '/MockModel/@' in routes
assert '/MockModel/@{view}' in routes
assert '/MockModel/{id:int}/@' in routes
assert '/MockModel/{id:int}/@{view}' in routes
assert '/MockModel/{id:int}' in routes

assert '/mock_models' in routes
assert '/mock_models/{id:int}' in routes
assert '/mock_models/{id:int}/custom' in routes
```

Also assert no class-name method mirror:

```python
assert '/MockModel/{id:int}/custom' not in routes
```

If a non-storable test model exists or is added, assert it does not receive the
class-name read mirror.

### Class-name read mirror dispatch tests

Add tests using mocked `api.request()`:

```text
GET /MockModel/5 sends TX(name='get', target='mock_models', data={'id': 5})
GET /MockModel/5?populate=children&depth=1 forwards query params
user metadata matches table-name get route
model_cls metadata matches table-name get route
error TX maps through _response_or_raise() to the same HTTP error
```

Representative assertion:

```python
response = client.get('/MockModel/5?populate=children&depth=1')

assert captured_tx.name == 'get'
assert captured_tx.target == 'mock_models'
assert captured_tx.data == {'id': 5, 'populate': 'children', 'depth': 1}
assert captured_tx.meta['user'] == expected_user
assert captured_tx.meta['model_cls'] is MockModel
```

### Identity behavior test

Because the actor handler owns serialization, the route should return reply data
unchanged:

```python
reply_data = {
    'id': 5,
    'name': 'Test',
    '$schema': 'http://test/MockModel',
    '$id': 'http://test/mock_models/5',
}

GET /MockModel/5 -> exactly reply_data
```

This proves NetworkAPI does not rewrite `$id` to class-name URLs.

### Actor HTML view route tests

Using protocol view-route model or real ViewableMixin model, assert:

```text
GET /MockModel/@ -> 200 text/html
GET /MockModel/@table -> 200 text/html
GET /MockModel/5/@ -> 200 text/html
GET /MockModel/5/@item -> 200 text/html
```

Critical no-CRUD-TX assertion:

```text
api.request is not called for HTML view routes
```

This prevents accidental data-route coupling.

### Route conflict tests

Required assertions:

```text
GET /MockModel/@table -> HTML route, not class-name read mirror
GET /MockModel/5/@item -> HTML route, not class-name method mirror
GET /MockModel/5 -> class-name read mirror
GET /MockModel -> schema route
GET /MockModel/5/custom -> not successful / not registered
POST /mock_models/5/custom -> existing custom method route still works
GET /mock_models/5 -> existing table-name get route still works
```

### Existing actor route regression tests

Ensure existing tests still cover and pass:

```text
schema route sends schema TX
create/list/get/update/delete TX dispatch
custom method dispatch
streaming method dispatch if present
parent-child path structure
join collection route precedence
```

---

## Implementation steps

### Step 1 — Red: route generation tests

Add failing route-generation tests for:

```text
/MockModel/{id:int}
/MockModel/@
/MockModel/@{view}
/MockModel/{id:int}/@
/MockModel/{id:int}/@{view}
```

Expected failures before implementation:

```text
class-name read mirror is missing
view routes are missing in actor mode
```

### Step 2 — Red: class-name mirror dispatch tests

Add failing TestClient tests for `GET /MockModel/5` dispatching a `get` TX to
`mock_models`.

### Step 3 — Green: class-name actor read mirror

Implement `_register_class_read_mirror()` in `network_api.py`.

Keep it GET-only and storable-only.

Use the same metadata and query behavior as the table-name get route.

### Step 4 — Red: HTML route delegation tests

Add failing tests proving NetworkAPI delegates view route registration to model
capability methods and that HTML routes do not call `api.request()`.

### Step 5 — Green: Viewable route delegation

In `create_api_routes()`, after schema route registration and before class-name
read mirror registration, call:

```python
register_view_routes = getattr(model_class, 'register_view_routes', None)
if callable(register_view_routes):
    register_view_routes(router, tag=tag)
```

Do not import `n3tx_ui`.

### Step 6 — Green: conflict and regression fixes

Adjust route order as needed so:

```text
/MockModel/@table
/MockModel/5/@item
/MockModel/5
```

all hit the intended routes.

### Step 7 — Verify focused suites

Run:

```bash
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py -q
cd /workspace && python3 -m pytest examples/actors/tests/ -q
```

If direct-route tests are nearby and recently changed, also run:

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py -q
cd /workspace && python3 -m pytest packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py -q
```

---

## Non-goals for this issue

- Actor class-name CRUD write mirrors.
- Actor class-name method mirrors.
- Actor-side HTML/data preloading.
- Changing actor custom method route behavior.
- Changing direct route behavior.
- Sidebar migration.
- Browser E2E smoke.
- `$id` migration to class-name URLs.
- Hardening beyond the ViewableMixin safety policy already established in issue 005.

---

## Acceptance checklist

- [ ] Actor route generation includes `/MockModel/{id:int}` for storable models.
- [ ] Actor route generation does not add class-name read mirrors for non-storable models.
- [ ] Actor route generation delegates collection/member HTML routes to model view capability methods.
- [ ] `GET /MockModel/5` sends `TX(name='get', target='mock_models', data.id=5)`.
- [ ] Class-name actor read mirrors forward `populate` and `depth` query params.
- [ ] Class-name actor read mirrors preserve `meta.user` and `meta.model_cls`.
- [ ] Error TX responses from class-name mirrors map to HTTP exceptions via `_response_or_raise()`.
- [ ] Actor read mirror responses are returned unchanged, preserving `$schema` and `$id`.
- [ ] Actor HTML routes return `text/html`.
- [ ] Actor HTML routes do not call `api.request()` for CRUD data unless preloading is explicitly added later.
- [ ] `/MockModel/@table` is not captured as an ID.
- [ ] `/MockModel/5/@item` is not captured as a method/action.
- [ ] `/MockModel/5/custom` is not added as a class-name method mirror.
- [ ] Existing `/mock_models/...` CRUD and custom method routes remain unchanged.
- [ ] Parent-child actor routes remain unchanged.
