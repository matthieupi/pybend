# N3TX Plan — Resource-Aware Auth for Actor-Routed Instance Methods

✅ **Recommendation:** fix this at the actor framework boundary, not in app code. `@expose_route(..., access=OWNER | ROLE("admin"))` must mean the same thing for actor-routed instance methods as it does for direct FastAPI routes: load the target instance, evaluate the method rule with `AccessContext.resource`, then execute.

📍 **Scope:** `n3tx-actors` runtime auth path, tests, and docs. Avoid changing `OWNER.evaluate()` globally.

---

## Current State

Actor-routed custom methods currently have two auth checks, but both are resource-blind for instance methods:

```text
HTTP /media/11/files
  -> NetworkAPI route parses args and sends TX(name="upload_files", data={id: 11})
  -> auth_interceptor evaluates method access with resource=None
  -> ActorModel.handler evaluates method access with resource=None
  -> ActorModel.handler fetches Media.get(11)
  -> method executes
```

Important evidence:

| File | Behavior |
|---|---|
| `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` | Generated table/class method routes send TX with `meta={'user': user, 'model_cls': cls}` and `data['id']`. |
| `packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py` | Tier 1 evaluates custom method `access=` with `AccessContext(user, action, model_class)` only. |
| `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py` | Tier 2 custom method auth runs before instance fetch, also without `resource`. |
| `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` | Direct instance custom routes fetch `model_class.get(id)` before `_check_access(..., resource=instance)`. |

⚠️ Because `OWNER.evaluate()` and `Where.evaluate()` intentionally return `True` when `resource is None` for create/list-style contexts, an authenticated non-owner can pass actor-routed instance method prechecks unless a later resource-aware check exists.

---

## Target State

```text
HTTP /{tablename}/{id}/{method}
  -> parse args/query params
  -> TX(name=method, data={id, args...}, meta={user, model_cls})
  -> Tier 1 auth only rejects safe boundary cases
  -> ActorModel.handler identifies exposed method and instance scope
  -> require id
  -> fetch instance once
  -> evaluate method access with AccessContext(resource=instance)
  -> materialize args / inject already-parsed user payload
  -> execute method(instance, **kwargs)
```

Security contract:

| Case | Expected |
|---|---:|
| Owner calls `OWNER` / `OWNER | ROLE('admin')` instance method | 200 |
| Admin calls `OWNER | ROLE('admin')` instance method | 200 |
| Authenticated non-owner calls owner-guarded instance method | 403 |
| Anonymous calls auth-required method | 401 at actor boundary |
| Missing instance for authenticated caller | 404 |
| Table-name and class-name custom method mirrors | Same behavior |

🔎 Note: direct FastAPI custom method auth currently maps anonymous access-denied to `403`, while actor routing docs/tests already use `401` for unauthenticated boundary rejection. Preserve actor `401` behavior unless the team explicitly chooses full status-code parity as a separate breaking change.

---

## Implementation Slices

### 1. Add failing unit tests for `ActorModel.handler()`

Extend `packages/n3tx-actors/src/n3tx_actors/tests/unit/test_handler_internal_method_auth.py` with a storable owner-scoped model:

```python
class _OwnedMethodModel(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = "owned_method_test"
    __owner_field__: ClassVar[str] = "user_owner"
    __access__: ClassVar[dict] = {"read": OWNER | ROLE("admin")}

    name: str = ""
    secret: str = ""
    user_owner: int | None = None
    executed: ClassVar[bool] = False

    @expose_route("/reveal", methods=["GET"], access=OWNER | ROLE("admin"))
    def reveal(self) -> dict:
        type(self).executed = True
        return {"secret": self.secret}
```

Use `patch.object(_OwnedMethodModel, "get", return_value=instance)` and the existing `capture_send` pattern.

Required red tests:

1. owner succeeds and sees result.
2. admin succeeds and sees result.
3. authenticated non-owner gets `403` and `executed` remains `False`.
4. anonymous external TX (`meta={'user': {}}`) gets denied and `executed` remains `False`.
5. missing instance returns `404` and does not evaluate method body.
6. internal TX without `meta.user` preserves existing bypass semantics.

### 2. Refactor `ActorModel.handler()` exposed-method path

Move signature/scope detection before method auth. Fetch instance once for instance methods before final method access evaluation.

💻 Code shape:

```diff
 if is_exposed:
+    from inspect import signature as get_sig
+    from typing import get_type_hints
+    signature_target = exposed.func if exposed is not None else method
+    sig = get_sig(signature_target)
+    type_hints = get_type_hints(signature_target)
+    is_instance = exposed.requires_instance if exposed is not None else 'self' in sig.parameters
+
+    instance = None
+    if is_instance:
+        entity_id = data.get('id')
+        if not entity_id:
+            await target.send(tx.error("'id' required for instance method", code=400))
+            return
+        instance = cls.get(entity_id)
+        if not instance:
+            await target.send(tx.error(f"{cls.__name__} {entity_id} not found", code=404))
+            return
+
     endpoint_info = getattr(method, '__endpoint__', {})
     method_access = endpoint_info.get('access')
     if method_access is not None:
-        ctx = AccessContext(user=user, action=tx.name, model_class=cls)
+        ctx = AccessContext(user=user, action=tx.name, model_class=cls, resource=instance)
         if not method_access.evaluate(ctx):
             await target.send(tx.error("Access denied", code=403))
             return
```

Then reuse `instance` for execution:

```python
kwargs = {k: v for k, v in data.items() if k != "id"}
# existing materialize_arg loop remains

if is_instance:
    result = method(instance, **kwargs)
else:
    result = method(**kwargs)
```

Keep these invariants:

- Do **not** change `OWNER.evaluate()` / `Where.evaluate()` globally.
- Do **not** fetch resources in `auth_interceptor`; resource ownership belongs in Tier 2.
- Preserve `user is None` internal-message bypass in `ActorModel.handler()`.
- Preserve class/static custom method behavior with `resource=None`.
- Preserve streaming, because streaming methods use the same `ActorModel.handler()` path after TX dispatch.

### 3. Make Tier 1 custom method auth an instance-safe precheck

`auth_interceptor` should not be a final grant/deny authority for authenticated instance methods, because rules such as `~OWNER`, `~Where(...)`, or composed resource predicates can be wrong when evaluated with `resource=None`.

Recommended shape:

```python
if action not in _CRUD_OPS:
    method_access = _get_method_access(model_cls, action)
    if method_access is not None:
        is_instance_method = _method_requires_instance(model_cls, action)
        ctx = AccessContext(user=user, action=action, model_class=model_cls)

        if is_instance_method:
            # Boundary auth only: reject anonymous when the declared rule
            # cannot allow anonymous without a resource. Authenticated users
            # always proceed to Tier 2 for resource-aware final auth.
            if not user.get("user_id") and not method_access.evaluate(ctx):
                return _deny(tx, user)
            return tx

        # Class/collection method has no resource; this is final.
        if not method_access.evaluate(ctx):
            return _deny(tx, user)
        return tx
```

Implement `_method_requires_instance()` using `exposed_method_info(model_cls, action)` when possible, falling back to signature inspection for backward compatibility. This keeps one source of truth with the schema/method-scope machinery.

### 4. Add actor-routing HTTP regression coverage

Prefer adding focused framework tests under `packages/n3tx-actors/src/n3tx_actors/tests/` if a small `create_app(..., routing='actor')` fixture is practical. Otherwise extend `examples/actors/tests/test_custom_methods.py` with a model/path already guarded by owner rules.

Minimum integration assertions:

| Route | Assertion |
|---|---|
| `GET /secret_documents/1/reveal` | non-owner gets 403 |
| `GET /SecretDocument/1/reveal` | non-owner gets 403 |
| owner/admin routes | 200 |
| missing resource as authenticated user | 404 |
| `GET ...?limit=2&offset=1` style method | query parsing still works |

### 5. Update docs

Update at least:

- `packages/n3tx-actors/docs/actor-model.md`
- `packages/n3tx-actors/docs/interceptors.md`
- `packages/n3tx-actors/docs/network-adapters.md` if route/auth flow details are changed
- `docs/ACTORS.md` or `BACKEND.md` if the public two-tier auth contract is clarified

Doc statement to add:

> Tier 1 is a boundary gate. For actor-routed instance custom methods, final `access=` evaluation happens in `ActorModel.handler()` after the target instance is loaded, with `AccessContext.resource` set to that instance.

---

## Risks and Decisions

| Risk / decision | Recommendation |
|---|---|
| Status-code parity with direct routes | Keep actor `401` for unauthenticated boundary rejection for now; direct-route `403` parity can be a separate cleanup. |
| Internal actor messages | Preserve existing `meta` has no `user` key => internal bypass. External anonymous HTTP continues to be `meta={'user': {}}`. |
| Tier 1 false denial for resource-dependent rules | Avoid final Tier 1 denial for authenticated instance method calls. |
| Global `OWNER` semantics | Do not change; create-time `resource=None` behavior may be relied on. |
| Double fetch | Fetch once in `ActorModel.handler()` and reuse for execution. |

---

## Verification

Run focused tests first:

```bash
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/unit/test_handler_internal_method_auth.py -q
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/unit/test_auth_interceptor.py -q
```

Then run package/example regression suites:

```bash
cd /workspace && python3 scripts/test-backend.py --suite actors -- -q
cd /workspace && python3 -m pytest examples/actors/tests/test_custom_methods.py examples/actors/tests/test_error_handling.py -q
cd /workspace && python3 scripts/test-backend.py --suite core -- -q
```

✅ Definition of done:

- Actor-routed instance methods evaluate method `access=` with `resource=instance`.
- Authenticated non-owners are denied before method body execution.
- Owner/admin access still succeeds.
- Table-name and class-name method mirrors match.
- Existing CRUD, class-method, streaming, query parsing, and internal TX behavior remain intentional.
- Docs explain the two-tier contract.

---

## Critical Files for Implementation

- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
- `packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py`
- `packages/n3tx-actors/src/n3tx_actors/tests/unit/test_handler_internal_method_auth.py`
- `packages/n3tx-actors/src/n3tx_actors/tests/unit/test_auth_interceptor.py`
- `packages/n3tx-actors/docs/actor-model.md`

## Saved Plan

- `.project/plans/n3tx-actor-custom-method-resource-auth.md`
