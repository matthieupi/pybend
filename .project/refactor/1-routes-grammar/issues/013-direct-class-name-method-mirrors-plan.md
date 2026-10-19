# Issue 013 Plan — Direct FastAPI Class-Name Method Mirrors

## ✅ Recommendation

Complete issue `013` as a focused hardening slice, not a broad route rewrite.

The current direct FastAPI route layer already registers class-name custom method mirrors for root models in `routes_fastapi.py`, and unit coverage includes a basic `POST /ClassName/{id}/method` parity test. The remaining work should close the acceptance gaps: route-generation proof, access/user-injection parity, async/SSE behavior, `MethodError` parity, GET/class-level behavior, and method-vs-view collision protection.

```text
Existing table route:      POST /products/1/run
Class-name method mirror:  POST /Product/1/run
View route remains view:   GET  /Product/1/@run

Preferred literal route:   /Product/{id:int}/run       ✅
Catch-all tolerated now:   /Product/{id:int}/{method}  ⚠️ if it cannot shadow @ views
```

---

## 📍 Current State

| Area | Current status | Gap |
|---|---:|---|
| Direct class-name custom route registration | Partially implemented | Needs route table and edge-case tests |
| Basic instance POST mirror | Covered by `test_class_name_method_mirror_matches_table_name_method` | Add auth, user injection, errors, async, stream |
| Class/static custom methods | Actor tests cover class route shape; direct path needs explicit decision/tests | Verify direct behavior and preserve parity if supported |
| GET custom methods | Existing code has known quirks | Mirror exactly; do not redesign in this slice |
| View/method collision | `@` routes are registered before custom methods | Add explicit `/Product/1/@run` regression test |
| Generic catch-all risk | Catch-all is tolerated for now | Assert `@` view routes still win and unknown methods fail safely |

---

## 🧭 Architecture Invariants

1. `GET /Product` remains schema.
2. `POST /Product/{id}/run` is a literal method mirror only if `run` is declared with `@expose_route('/run')`.
3. `GET /Product/{id}/@run` remains an HTML/view route and must never invoke `run`.
4. Class-name method mirrors reuse the same handler object/path as table-name methods where practical.
5. Prefer literal method mirrors, but a guarded generic `/ClassName/{id:int}/{method}` catch-all is acceptable for now if it cannot shadow `@` view routes and unknown methods fail safely.
6. Response identity is already class-name based after issue `010`; tests should assert `$id` where method responses return models/entities.
7. Root storable models get class-name method mirrors; nested class-name method mirrors are handled by nested route work and should not be expanded here unless already present.

---

## 🗺️ Flow

```text
@expose_route('/run') on Product.run
          |
          v
register_routes()
          |
          +--> table route: /products/{id:int}/run
          |        |
          |        v
          |   make_custom_post(attr, Product, table_route)
          |
          +--> class route: /Product/{id:int}/run
                   |
                   v
              same handler semantics
                   |
                   v
          Product.get(id) -> auth/access -> parse args/user -> call method
                   |
                   v
        JSON result or StreamingResponse or MethodError->HTTPException
```

---

## Implementation Plan

### Phase 1 — Lock route-generation behavior

**Files**

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

**Add tests first**

Create/extend direct route-generation coverage for a storable root model with multiple custom methods:

```python
class MethodMirrorModel(ProtoModel):
    __tablename__ = 'method_mirror_models'
    __storable__ = True

    @expose_route('/run', methods=['POST'], access=ANYONE)
    def run(self) -> dict: ...

    @expose_route('/status', methods=['GET'], access=ANYONE)
    def status(self) -> dict: ...
```

Assert route table contains literal routes when the implementation uses explicit registration:

```text
/method_mirror_models/{id:int}/run
/MethodMirrorModel/{id:int}/run
/method_mirror_models/{id:int}/status
/MethodMirrorModel/{id:int}/status
```

If the implementation uses or keeps a catch-all, replace the route-table absence assertion with behavior assertions:

```text
POST /MethodMirrorModel/{id}/not_declared -> 404 or documented MethodError/HTTP error
GET  /MethodMirrorModel/{id}/@run         -> HTML view route, not method dispatch
```

**Likely code change**

If route-generation tests already pass, no functional edit is needed. If not, adjust only the custom-route registration loop to register class-name method access for root models from the same handler path. Literal routes remain clearer, but a catch-all is acceptable in this slice if it preserves the `@` grammar boundary.

---

### Phase 2 — Prove parity for instance POST methods

**Files**

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- optionally `examples/core/tests/test_custom_methods.py`

**Add tests**

1. Table and class-name POST method responses match:

```text
POST /method_mirror_models/{id}/rename
POST /MethodMirrorModel/{id}/rename
```

2. Required argument validation matches:

```text
POST /MethodMirrorModel/{id}/rename {} -> same status/detail as table route
```

3. Missing instance behavior matches:

```text
POST /MethodMirrorModel/999999/rename -> 404
```

4. `MethodError` mapping matches:

```python
@expose_route('/fail', methods=['POST'], access=ANYONE)
def fail(self):
    raise MethodError('bad method', 409)
```

Expected:

```text
POST /MethodMirrorModel/{id}/fail -> 409 {detail: 'bad method'}
```

**Likely code change**

The existing `make_custom_post()` already catches `MethodError` for both `post_with_id` and `post_no_id`. If tests fail, fix in `make_custom_post()` rather than adding route-specific wrappers.

---

### Phase 3 — User injection and access parity

**Files**

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `examples/core/tests/test_custom_methods.py`

**Add tests**

1. Method-level `access=AUTHENTICATED` rejects unauthenticated calls through both paths.
2. `user` parameter injection produces the same result through both paths:

```python
@expose_route('/whoami', methods=['POST'], access=AUTHENTICATED)
def whoami(self, user: dict = None) -> dict:
    return {'user_id': user['user_id'] if user else None}
```

3. If using a real storable user type, verify `_resolve_user()` still returns the full model instance on the class-name path.

**Likely code change**

None expected if the class-name route reuses `make_custom_post()`. If there is drift, centralize the fix inside `_resolve_user()` or `make_custom_post()`, not per route.

---

### Phase 4 — Async and SSE streaming parity

**Files**

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- possibly `examples/core/tests/` if an existing streaming model is available

**Add tests**

1. Async method mirror:

```python
@expose_route('/async_echo', methods=['POST'], access=ANYONE)
async def async_echo(self, text: str) -> dict:
    return {'text': text}
```

Assert table and class-name responses match.

2. Async-generator streaming method mirror:

```python
@expose_route('/stream_echo', methods=['POST'], access=ANYONE, stream=True)
async def stream_echo(self, text: str):
    yield {'chunk': text}
```

Assert:

```text
POST /MethodMirrorModel/{id}/stream_echo -> 200
content-type contains text/event-stream
body contains event: chunk
body contains event: done
```

**Likely code change**

The existing `make_custom_post()` detects `inspect.isasyncgen(result)` and returns `StreamingResponse`; class-name route reuse should inherit this. If not, keep the fix in `make_custom_post()`.

---

### Phase 5 — GET, class/static custom method decision

**Files**

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

**Decision to lock**

Issue `013` says static/class-level `@expose_route` methods need either an intentional class-name mirror or an explicit test proving they remain table-name only.

Recommended contract:

```text
If table-name direct route is generated for a non-instance custom method,
generate the corresponding class-name direct route too.
```

Examples:

```text
POST /method_mirror_models/reindex
POST /MethodMirrorModel/reindex
```

For GET custom instance methods, preserve current table-route semantics exactly and add the class-name mirror only by reusing the same handler. Do not redesign existing GET quirks in this issue.

**Important code audit**

`routes_fastapi.py` currently contains dead/legacy local `custom_get/custom_post` closures in the registration loop before it always calls `make_custom_post()`. If GET/class/static tests expose confusion, simplify by making `make_custom_post()` the single route-handler factory for all custom route methods, but keep behavior-compatible parsing.

---

### Phase 6 — Method-vs-view collision hardening

**Files**

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py` if view shell behavior needs direct proof

**Add tests**

For a viewable model that declares both:

```python
__ui__ = {'renderer': {'run': 'ntx-run-view'}}

@expose_route('/run', methods=['POST'], access=ANYONE)
def run(self): ...
```

Assert:

```text
POST /Product/{id}/run  -> method JSON
GET  /Product/{id}/@run -> text/html view shell
```

Also assert unsupported method verbs do not route accidentally:

```text
GET /Product/{id}/run -> 405 or documented FastAPI behavior
```

**Likely code change**

Route order is already favorable: schema, view routes, CRUD mirrors, then custom method mirrors. Keep it that way.

---

### Phase 7 — Example-level smoke

**Files**

- `examples/core/tests/test_custom_methods.py`

Add real app coverage for existing Product methods:

```text
POST /Product/{id}/comment   mirrors /products/{id}/comment
POST /Product/{id}/favorite  mirrors /products/{id}/favorite
```

Use existing auth fixtures and seeded products. Prefer assertions on externally observable behavior/status and key fields rather than exact side-effect order for toggle methods.

---

## Main Code Shape

The target registration shape should stay simple:

```python
handler = make_custom_post(attr, model_class, full_route)
router.add_api_route(full_route, handler, methods=methods, ...)

if not parent_class:
    class_route = (
        f"/{model_class.__name__}/{{id:int}}{route}"
        if is_instance_method
        else f"/{model_class.__name__}{route}"
    )
    router.add_api_route(class_route, handler, methods=methods, ...)
```

If this code already exists and passes expanded tests, issue `013` should land mostly as test hardening plus minor cleanup.

---

## Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Generic method route shadows views | `/Product/1/@run` could invoke a method | Prefer literal routes; if using catch-all, register/prove `@` routes win and test `@run` as HTML |
| Class/static method detection is inconsistent | Python descriptors make `classmethod`/`staticmethod` tricky after `getattr()` | Test actual decorated forms and preserve table behavior |
| GET custom handling has existing quirks | Issue notes not to redesign it | Mirror behavior exactly; defer cleanup |
| Streaming response buffering | SSE must remain progressive | Reuse existing `StreamingResponse` helper and headers |
| Auth bypass through mirror | Method access/user injection must match | Reuse `make_custom_post()` and add parity tests |

---

## Verification Plan

Narrow checks during implementation:

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py -q
cd /workspace && python3 -m pytest examples/core/tests/test_custom_methods.py -q
```

Acceptance check for issue `013`:

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py examples/core/tests/ -q
```

Broader backend sanity if route registration changes are non-trivial:

```bash
cd /workspace && python3 scripts/test-backend.py --suite core -- -q
```

---

## Acceptance Checklist

```text
[ ] Literal instance method mirrors exist under /ClassName/{id}/method
[ ] Literal routes are preferred, or any catch-all is guarded so @ view routes still win
[ ] Table and class-name method paths share auth/user injection semantics
[ ] Missing instance, missing fields, validation errors, and MethodError map identically
[ ] Async method mirrors work
[ ] Async-generator streaming method mirrors return SSE
[ ] Static/class-level custom method behavior is explicitly mirrored or explicitly table-only
[ ] /ClassName/{id}/@method remains HTML/view route
[ ] Real examples/core Product custom method smoke passes
```

### Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `examples/core/tests/test_custom_methods.py`
- `packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py`
- `packages/n3tx-core/src/n3tx_core/utils/decorators.py`
