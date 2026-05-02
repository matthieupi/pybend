# Issue 014 Plan — Actor Class-Name CRUD and Method Parity

## ✅ Recommendation

Treat issue `014` as a **parity closure and hardening slice** for Level 3 actor routing.

The current `NetworkAPI` implementation already shows the desired shape in several places:

- class-name collection/write mirrors are registered for root storable models:
  - `POST /{ClassName}`
  - `GET /{ClassName}/_`
  - `PUT /{ClassName}/{id:int}`
  - `DELETE /{ClassName}/{id:int}`
- literal class-name method mirrors are registered alongside table-name methods.
- all class-name actor routes still target the table-name actor address.
- HTML/view routes remain delegated to `register_view_routes()` and do not dispatch CRUD TXs.

So the implementation plan should avoid a broad rewrite. The right build phase is:

```text
1. Lock explicit tests for the issue-014 contract.
2. Refactor only if tests expose duplicate naming, route drift, or stream parity gaps.
3. Update actor docs to reflect class-name write/method parity.
```

---

## Target Contract

```text
GET    /Product                 -> schema TX, unchanged
GET    /Product/_               -> list TX to target='products'
POST   /Product                 -> create TX to target='products'
GET    /Product/1               -> get TX to target='products'
PUT    /Product/1               -> update TX to target='products'
DELETE /Product/1               -> delete TX to target='products'
POST   /Product/1/favorite      -> method TX to target='products'
GET    /Product/1/@favorite     -> HTML/view route, no CRUD/method TX

Legacy table-name routes remain:
GET    /products
POST   /products
GET    /products/1
PUT    /products/1
DELETE /products/1
POST   /products/1/favorite
```

Important grammar rule:

```text
/Product/1/run   -> method/action mirror
/Product/1/@run  -> view/html route named run
```

---

## Architecture View

```text
HTTP /Product/1/update-like-route
          |
          v
NetworkAPI FastAPI route
          |
          v
TX(name=<action>, source='api', target='products')
          |
          v
api_adapter.request(tx)
  |  Tier 1 auth interceptor
  v
Matrix -> ActorModel.handler()
  |  CRUD or @expose_route fallback
  |  Tier 2 ActorModel authorization
  v
StorableMixin / method execution / lifecycle
          |
          v
reply TX -> HTTP response

HTML /Product/1/@item
          |
          v
ViewableMixin.register_view_routes() handler
          |
          v
HTMLResponse, no TX dispatch
```

The key ownership split must stay intact:

| Concern | Owner | Why |
|---|---|---|
| JSON schema | `NetworkAPI` schema route | schema is actor-routed through `schema` TX |
| JSON CRUD/method mirrors | `NetworkAPI` | protocol adapter maps HTTP to TX |
| HTML/view routes | `ViewableMixin.register_view_routes()` capability hook | UI package owns view rendering without actor/core importing UI |
| Auth/resource checks | `auth_interceptor` + `ActorModel` | same path as table-name actor routes |

---

## Current Implementation Observations

### `network_api.py`

Current route registration already includes:

```python
if not has_parent:
    class_base = f"/{model_class.__name__}"
    router.post(class_base, ...)(create_instance)
    router.get(f"{class_base}/_", ...)(list_instances)
    router.put(f"{class_base}/{{id:int}}", ...)(update_instance)
    router.delete(f"{class_base}/{{id:int}}", ...)(delete_instance)
```

and custom method mirrors:

```python
if not parent_class:
    if is_instance_method:
        class_route = f"/{model_class.__name__}/{{id:int}}{route}"
    else:
        class_route = f"/{model_class.__name__}{route}"
```

This is consistent with issue `012` and issue `013`. Issue `014` should therefore focus on proving this behavior is complete for actor mode and then tightening duplication if needed.

### Existing unit tests

`test_network_api.py` already tests some class-name actor routes:

- route generation includes `/MockModel/_`, `/MockModel/{id:int}`, and `/MockModel/{id:int}/custom`.
- `POST /MockModel`, `GET /MockModel/_`, `GET /MockModel/5`, `PUT /MockModel/5`, and `DELETE /MockModel/5` send the expected CRUD TX names.
- HTML view routes do not call `api.request()`.

Gaps to close for issue `014`:

- explicit side-by-side table-name vs class-name TX equivalence tests for create/list/update/delete.
- explicit metadata parity (`user`, `model_cls`) for write mirrors.
- explicit class-name method metadata parity.
- streaming method class-name mirror test.
- route-name duplicate check if FastAPI operation names collide.
- examples/actors parity coverage for real app behavior.

---

## Implementation Plan

## Phase 1 — Add Contract Tests for Route Generation

Goal: prove every issue-014 route shape exists, and no schema/view routes are shadowed.

File:

```text
packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
```

Add or extend tests in `TestCreateAPIRoutesRouteGeneration`:

```python
routes = {r.path for r in router.routes}

assert '/MockModel' in routes                 # schema
assert '/MockModel/_' in routes               # class list mirror
assert '/MockModel/{id:int}' in routes        # class read/update/delete path
assert '/MockModel/{id:int}/custom' in routes # class instance method mirror
assert '/mock_models' in routes               # legacy list/create
assert '/mock_models/{id:int}' in routes      # legacy read/update/delete
assert '/mock_models/{id:int}/custom' in routes
assert '/MockModel/@' in routes               # view route from capability hook
assert '/MockModel/{id:int}/@{view}' in routes
```

Also assert method support per path, not just path presence. Because FastAPI stores multiple methods for one path, inspect `(route.path, route.methods)`:

```python
methods_by_path = {r.path: r.methods for r in router.routes if hasattr(r, 'methods')}
assert 'POST' in methods_by_path['/MockModel']
assert 'GET' in methods_by_path['/MockModel']  # schema route only; create uses POST
assert 'GET' in methods_by_path['/MockModel/_']
assert {'GET', 'PUT', 'DELETE'} <= methods_by_path['/MockModel/{id:int}']
```

Expected outcome:

- `GET /MockModel` remains schema.
- `GET /MockModel/_` is list.
- `POST /MockModel` is create.
- view paths remain present and hidden from OpenAPI where the hook marks them so.

---

## Phase 2 — Add TX Equivalence Tests for CRUD Mirrors

Goal: prove class-name mirrors create the same TXs as table-name actor routes.

Add a helper in test code only:

```python
def make_app_with_captured_request(router, api, captured):
    async def capture(tx, timeout=30.0):
        captured.append(tx)
        return tx.reply(data={'ok': True, 'id': tx.data.get('id', 1), **tx.data})
```

Test pairs:

| Operation | Table route | Class route | Expected TX |
|---|---|---|---|
| create | `POST /mock_models` | `POST /MockModel` | `name='create'`, `target='mock_models'` |
| list | `GET /mock_models?limit=2` | `GET /MockModel/_?limit=2` | `name='list'`, same pagination data |
| read | `GET /mock_models/5` | `GET /MockModel/5` | `name='get'`, `data.id=5` |
| update | `PUT /mock_models/5` | `PUT /MockModel/5` | `name='update'`, same flattened payload + id |
| delete | `DELETE /mock_models/5` | `DELETE /MockModel/5` | `name='delete'`, `data.id=5` |

Representative assertion:

```python
assert table_tx.name == class_tx.name == 'update'
assert table_tx.target == class_tx.target == 'mock_models'
assert table_tx.source == class_tx.source == 'api'
assert table_tx.data == class_tx.data
assert table_tx.meta['model_cls'] is class_tx.meta['model_cls'] is MockModel
assert table_tx.meta['user'] == class_tx.meta['user']
```

This directly protects the core invariant: class-name routes are transport mirrors, not new actor addresses.

---

## Phase 3 — Add Method Mirror Parity Tests

Goal: prove class-name literal method mirrors behave exactly like table-name method routes.

Add tests for instance methods:

```python
POST /mock_models/5/custom
POST /MockModel/5/custom
```

Expected for both:

```python
tx.name == 'custom_method'
tx.target == 'mock_models'
tx.data == {'id': 5, 'arg1': 'test', 'arg2': 10}
tx.meta['user'] == authenticated_user
tx.meta['model_cls'] is MockModel
```

Add or preserve class/static method tests:

```python
POST /mock_models/class_method
POST /MockModel/class_method
```

Expected:

```python
tx.name == 'class_method'
tx.target == 'mock_models'
tx.data == {'value': 21}
```

Method-vs-view collision assertion:

```python
POST /MockModel/5/custom  -> TX method route
GET  /MockModel/5/@custom -> HTML view route, no TX
```

This locks the grammar distinction from earlier route issues.

---

## Phase 4 — Add Streaming Method Mirror Tests

Goal: prove class-name streaming method mirrors preserve SSE behavior and stream metadata.

Add a mock model method in `test_network_api.py`:

```python
@expose_route('/stream_custom', methods=['POST'], stream=True)
async def stream_custom(self, prompt: str = ''):
    yield {'chunk': prompt}
```

Route assertions:

```python
assert '/mock_models/{id:int}/stream_custom' in routes
assert '/MockModel/{id:int}/stream_custom' in routes
```

Behavior test:

```python
POST /MockModel/5/stream_custom
```

Mock `api.stream()` to capture the TX and yield chunks:

```python
assert captured_tx.name == 'stream_custom'
assert captured_tx.target == 'mock_models'
assert captured_tx.data == {'id': 5, 'prompt': 'hello'}
assert captured_tx.meta['stream'] is True
assert captured_tx.meta['user'] == user
assert captured_tx.meta['model_cls'] is MockModel
```

Response assertions:

```python
assert response.status_code == 200
assert 'text/event-stream' in response.headers['content-type']
assert 'event: chunk' in response.text
assert 'event: done' in response.text
```

This is the highest-risk missing coverage because streaming uses `api_adapter.stream()` instead of `api_adapter.request()`.

---

## Phase 5 — Refactor Only If Tests Reveal Duplication Risk

Goal: keep `network_api.py` simple without changing behavior unnecessarily.

Current helpers already reuse actual handler functions for class-name CRUD mirrors:

```python
router.post(class_base)(create_instance)
router.get(f"{class_base}/_")(list_instances)
router.put(f"{class_base}/{{id:int}}")(update_instance)
router.delete(f"{class_base}/{{id:int}}")(delete_instance)
```

If tests reveal duplicate operation names or ambiguous route diagnostics, use a tiny local wrapper helper rather than rewriting route construction:

```python
def _register_root_class_crud_mirrors(router, model_class, tag, handlers, addr):
    class_base = f"/{model_class.__name__}"
    router.post(class_base, tags=[tag], status_code=201, name=f"create_{addr}_class")(handlers.create)
    router.get(f"{class_base}/_", tags=[tag], name=f"list_{addr}_class")(handlers.list)
    router.put(f"{class_base}/{{id:int}}", tags=[tag], name=f"update_{addr}_class")(handlers.update)
    router.delete(f"{class_base}/{{id:int}}", tags=[tag], name=f"delete_{addr}_class")(handlers.delete)
```

For custom method routes, if duplicate names surface, make names route-mode-aware:

```python
name=f"custom_{addr}_{attr_name}_class"
name=f"stream_{addr}_{attr_name}_class"
```

Do not change TX construction. The implementation must continue to construct TXs inside the shared handlers so table-name and class-name routes cannot drift.

---

## Phase 6 — Add Example-App Parity Coverage

Goal: prove `examples/actors` exposes the same public route grammar as direct routing in a real Level 3 app.

Files:

```text
examples/actors/tests/test_products_crud.py
examples/actors/tests/test_custom_methods.py
examples/actors/tests/test_streaming.py
examples/actors/tests/test_comments_crud.py
```

Recommended new file if the suite is already crowded:

```text
examples/actors/tests/test_class_name_actor_parity.py
```

Test cases:

1. `POST /Product` creates a product and returns `$id` ending in `/Product/{id}`.
2. `GET /Product/_` lists products and returns the same shape as `GET /products`.
3. `PUT /Product/{id}` updates the same entity as `PUT /products/{id}`.
4. `DELETE /Product/{id}` deletes the same entity as `DELETE /products/{id}`.
5. A real custom method reachable under table-name is also reachable under class-name.
6. A real streaming method, if present in the actor example, preserves `text/event-stream` through the class-name mirror.
7. `GET /Product/{id}/@item` still returns HTML and is not confused with method mirrors.

If nested class-name route support is already present in the example suite, keep it separate from issue `014` unless needed for parity. Issue `014` is root model CRUD/method parity; nested route support belongs to issues `016`–`017`.

---

## Phase 7 — Documentation Updates

Update actor route docs after tests are green.

Files:

```text
packages/n3tx-actors/docs/network-adapters.md
BACKEND.md
docs/ARCHITECTURE.md
```

Required wording changes:

- `NetworkAPI.create_api_routes()` now generates class-name collection/write/method mirrors, not only read mirrors.
- `GET /{ClassName}` remains schema; `GET /{ClassName}/_` is the explicit JSON collection mirror.
- class-name CRUD/method routes dispatch to table-name actor addresses.
- HTML/view routes remain direct capability-hook responses and do not dispatch CRUD TXs.
- streaming method mirrors preserve SSE behavior.

Avoid saying class-name routes create class-name actor addresses. They do not.

---

## Risk Table

| Risk | Why it matters | Mitigation |
|---|---|---|
| Class-name routes target class-name actor addresses | Would bypass existing actor registration and auth/storage flow | Assert every class-name TX target is `__tablename__` |
| `GET /ClassName` collides with list | Schema endpoint must remain stable | Use only `GET /ClassName/_` for list mirror |
| Method mirror shadows view route | `/Product/1/@run` must stay view/html | No generic method catch-all; literal method routes only |
| Streaming parity drifts | Streaming uses `stream()`, not `request()` | Add dedicated SSE class-name method tests |
| Duplicate FastAPI route names | OpenAPI/debuggability can degrade | Use `_class` suffix if needed |
| Auth metadata drift | Tier 1/Tier 2 parity depends on `meta.user` and `meta.model_cls` | Pairwise TX equivalence tests |

---

## Verification Commands

Run narrow actor API tests first:

```bash
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py -q
```

Then actor example parity:

```bash
cd /workspace && python3 -m pytest examples/actors/tests/ -q
```

Then backend short suite if route behavior changed:

```bash
cd /workspace && python3 scripts/test-backend.py --suite actors -- -q
cd /workspace && python3 scripts/test-backend.py --short -- -q
```

---

## Acceptance Checklist

```text
[ ] Route generation includes actor class-name list/write/method mirrors.
[ ] GET /ClassName remains schema; GET /ClassName/_ is list.
[ ] Class-name CRUD mirrors send equivalent TXs to table-name routes.
[ ] Class-name method mirrors send equivalent TXs to table-name methods.
[ ] Streaming method mirrors preserve SSE response and stream TX metadata.
[ ] Auth/user/model metadata matches table-name routes.
[ ] HTML/view routes do not call api.request() or api.stream().
[ ] Existing table-name routes remain unchanged.
[ ] Actor docs describe the completed class-name parity contract.
```

---

## Suggested Commit Slices

### Commit 1 — Unit parity tests

```text
test(actors): Lock class-name CRUD and method route parity [routes-grammar]
```

Scope:

- route generation assertions
- CRUD TX equivalence tests
- method TX equivalence tests
- streaming method mirror test

### Commit 2 — Minimal NetworkAPI cleanup, if needed

```text
refactor(actors): Clarify class-name route mirror registration [routes-grammar]
```

Scope:

- only if tests reveal operation-name collisions or duplicated route intent
- no TX behavior changes

### Commit 3 — Example parity and docs

```text
docs(actors): Document class-name actor route parity [routes-grammar]
```

Scope:

- examples/actors route parity tests
- actor/backend architecture docs

---

### Critical Files for Implementation

- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py`
- `examples/actors/tests/test_class_name_actor_parity.py`
- `packages/n3tx-actors/docs/network-adapters.md`
- `BACKEND.md`
