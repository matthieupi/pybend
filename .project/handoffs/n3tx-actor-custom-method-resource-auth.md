# N3TX Backend Handoff — Resource-Aware Authorization for Actor-Routed Instance Custom Methods

✅ **Request type:** Security-sensitive framework bug fix / backend feature request  
📍 **Subsystem:** `n3tx-actors` HTTP actor routing + `n3tx-core` authorization integration  
⚠️ **Severity:** High for apps that rely on `OWNER`/resource rules on actor-routed instance methods  
🧭 **Desired outcome:** Actor-routed instance `@expose_route` methods evaluate method access against the target resource instance before method execution, matching direct-route behavior.

---

## 1. Executive Summary

Actor-routed N3TX custom methods currently appear to evaluate method-level access rules without passing the target resource instance into `AccessContext`.

This is a problem for instance methods guarded by resource-dependent rules such as:

```python
@expose_route("/files", methods=["GET"], access=OWNER | ROLE("admin"))
def upload_files(self, limit: int | None = None, offset: int = 0) -> dict:
    ...
```

Under actor routing, the observed framework path is:

```text
HTTP generated custom method route
  -> TX(name="upload_files", target="media", data={"id": 11, ...})
  -> auth_interceptor evaluates OWNER without resource
  -> ActorModel.handler evaluates OWNER without resource
  -> ActorModel.handler fetches Media.get(11)
  -> method executes
```

Because `OWNER.evaluate()` returns `True` for authenticated users when `ctx.resource is None`, an instance method guarded by `OWNER | ROLE("admin")` can behave like “any authenticated user or admin” instead of “resource owner or admin”.

This differs from direct-route behavior, where N3TX fetches the instance and evaluates access with `resource=instance` before calling the method.

---

## 2. Why This Matters

N3TX’s contract is that backend-declared access rules are authoritative and schema-visible. App developers should be able to trust:

```python
@expose_route(..., access=OWNER | ROLE("admin"))
```

on both direct routes and actor-routed routes.

If actor-routed instance method auth is not resource-aware, applications may accidentally expose sensitive resource-specific actions or reads to authenticated non-owners.

### Concrete app impact

The Gaussian Splat Capture Portal has a `Media` model:

```python
class Media(ActorModel):
    __tablename__ = "media"
    __storable__ = True
    __owner_field__ = "user_owner"
    __access__ = {
        "read": OWNER | ROLE("admin"),
        "list": OWNER | ROLE("admin"),
        "create": AUTHENTICATED,
        "update": OWNER | ROLE("admin"),
        "delete": OWNER | ROLE("admin"),
    }

    @expose_route("/files", methods=["GET"], access=OWNER | ROLE("admin"))
    def upload_files(self, limit: int | None = None, offset: int = 0) -> dict:
        ...
```

The app wants to remove a duplicate custom FastAPI adapter for:

```text
GET /media/{id}/files
```

and rely on the generated N3TX route instead:

```text
GET /media/{id}/files
GET /Media/{id}/files
```

That cleanup is blocked until generated actor-routed method auth is proven security-equivalent to the current app adapter’s explicit owner/admin check.

---

## 3. Current Behavior Evidence

This evidence comes from read-only inspection of the framework checkout at `/workspace/lib/n3tx`.

### 3.1 Actor NetworkAPI registers generated instance custom method routes

File:

```text
/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

Relevant path:

```python
def _register_custom_routes(router, api_adapter, model_class, endpoint_base, tag, nested_class_base=None):
    ...
    is_instance_method = 'self' in sig.parameters

    if is_instance_method:
        full_route = f"{endpoint_base}/{{id:int}}{route}"
    else:
        full_route = f"{endpoint_base}{route}"
    ...

    if not parent_class:
        if is_instance_method:
            class_route = f"/{model_class.__name__}/{{id:int}}{route}"
```

For `Media.__tablename__ == "media"` and `@expose_route("/files")`, this generates:

```text
GET /media/{id}/files
GET /Media/{id}/files
```

### 3.2 Actor NetworkAPI custom method handler sends TX before loading resource

File:

```text
/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

Relevant path:

```python
@router.api_route(full_route, methods=methods, tags=[tag], name=f"custom_{addr}_{attr_name}")
async def custom_with_id(...):
    user = _get_user(request)
    payload = await _parse_method_args(_sig, _type_hints, data, request)
    payload['id'] = id

    response = await api_adapter.request(
        TX(
            name=_attr_name,
            source=api_adapter.addr,
            target=_addr,
            data=payload,
            meta={'user': user, 'model_cls': _cls},
        ),
        timeout=30.0,
    )
```

The route handler does not fetch the resource instance before TX dispatch. That may be desirable architecturally, but then the actor side must perform resource-aware method authorization before method execution.

### 3.3 Tier 1 auth interceptor evaluates method access without resource

File:

```text
/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py
```

Relevant path:

```python
if action not in _CRUD_OPS:
    method_access = _get_method_access(model_cls, action)
    if method_access is not None:
        ctx = AccessContext(user=user, action=action, model_class=model_cls)
        if not method_access.evaluate(ctx):
            return _deny(tx, user)
        return tx
```

No `resource` is supplied.

The module header says resource-dependent OWNER checks are deferred to Tier 2 for CRUD:

```python
# read/update/delete: identity gate only
# Full OWNER/Where check happens at Tier 2 (handler_crud has the instance)
```

But custom methods are not CRUD and are handled separately. There does not appear to be an equivalent resource-aware Tier 2 path for instance custom methods.

### 3.4 ActorModel.handler also evaluates method access without resource before fetching instance

File:

```text
/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/models/actor_model.py
```

Relevant path:

```python
if is_exposed:
    endpoint_info = getattr(method, '__endpoint__', {})
    method_access = endpoint_info.get('access')
    if method_access is not None:
        user = tx.meta.get('user')
        if user is not None:
            from n3tx_core.authorize import AccessContext
            ctx = AccessContext(
                user=user,
                action=tx.name,
                model_class=cls,
            )
            if not method_access.evaluate(ctx):
                await target.send(tx.error("Access denied", code=403))
                return
```

Only after that access evaluation does the code fetch the instance:

```python
if is_instance:
    entity_id = data.get('id')
    if not entity_id:
        await target.send(tx.error("'id' required for instance method", code=400))
        return
    instance = cls.get(entity_id)
    if not instance:
        await target.send(tx.error(f"{cls.__name__} {entity_id} not found", code=404))
        return
    result = method(instance, **kwargs)
```

### 3.5 OWNER currently passes for authenticated users when no resource exists

File:

```text
/workspace/lib/n3tx/packages/n3tx-core/src/n3tx_core/authorize/rules.py
```

Relevant path:

```python
def evaluate(self, ctx: AccessContext) -> bool:
    if not ctx.is_authenticated:
        return False
    if ctx.resource is None:
        return True  # For create: ownership is established at creation time
    field = self._resolve_field(ctx)
    owner_val = getattr(ctx.resource, field, None)
    ...
    return owner_val == ctx.user_id
```

This create-time behavior makes sense for create actions, but it is unsafe for instance custom methods where the resource id is known and the resource can be loaded.

### 3.6 Direct-route behavior appears resource-aware

File:

```text
/workspace/lib/n3tx/packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py
```

Observed behavior from inspection:

```text
direct instance custom method route
  -> fetch instance
  -> evaluate access with resource=instance
  -> execute method
```

This should be the parity target for actor routing.

---

## 4. Reproduction Sketch

The N3TX backend team should reproduce this in the framework test suite, preferably under `n3tx-actors` tests because the issue is actor-routing-specific.

### Minimal model

```python
from typing import ClassVar

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, OWNER, ROLE
from n3tx_core.utils.decorators import expose_route


class SecretDocument(ActorModel):
    __tablename__ = "secret_documents"
    __storable__ = True
    __owner_field__: ClassVar[str] = "user_owner"
    __access__ = {
        "read": OWNER | ROLE("admin"),
        "list": OWNER | ROLE("admin"),
        "create": AUTHENTICATED,
        "update": OWNER | ROLE("admin"),
        "delete": OWNER | ROLE("admin"),
    }

    title: str
    secret: str
    user_owner: int | None = None

    @expose_route("/reveal", methods=["GET"], access=OWNER | ROLE("admin"))
    def reveal(self) -> dict:
        return {"secret": self.secret}
```

### Expected access matrix

For a stored document:

```python
SecretDocument(id=1, title="A", secret="classified", user_owner=10)
```

The generated actor-routed endpoint should behave as follows:

| Request user | Route | Expected |
|---|---|---|
| owner `user_id=10, role=user` | `GET /secret_documents/1/reveal` | `200` |
| admin `user_id=99, role=admin` | `GET /secret_documents/1/reveal` | `200` |
| non-owner `user_id=20, role=user` | `GET /secret_documents/1/reveal` | `403` |
| anonymous / no token | `GET /secret_documents/1/reveal` | `401` |
| owner, missing id | `GET /secret_documents/999/reveal` | `404` |
| non-owner class mirror | `GET /SecretDocument/1/reveal` | `403` |

### Current suspected failure

The non-owner request likely returns `200` because `OWNER` is evaluated with `resource=None` and the user is authenticated.

---

## 5. Desired Framework Behavior

Actor-routed instance custom methods should evaluate method-level access with the target instance as `AccessContext.resource` before method execution.

Target control flow:

```text
HTTP /{tablename}/{id}/{method}
  -> parse args
  -> TX(name=method, data={id, args...}, meta={user, model_cls})
  -> Tier 1 auth interceptor performs identity-only or method-rule precheck where safe
  -> ActorModel.handler receives TX
  -> identify exposed instance method
  -> require id
  -> fetch instance
  -> 404 if missing
  -> evaluate method access with AccessContext(resource=instance)
  -> 401 if unauthenticated and rule requires user
  -> 403 if authenticated but unauthorized
  -> materialize args if needed
  -> execute method(instance, **kwargs)
```

For class methods / static collection methods, resource remains `None`, and create-like semantics may continue to allow `OWNER` only if that is an intended framework contract. The key bug is instance custom methods where the id and resource exist.

---

## 6. Proposed Implementation Direction

This section is intentionally implementation-grade but not prescriptive if the N3TX backend team sees a cleaner architecture.

### 6.1 Do not change `OWNER.evaluate()` globally

Avoid changing:

```python
if ctx.resource is None:
    return True
```

globally unless the team deliberately wants a broader semantic change. That behavior may be relied on for create-time ownership establishment.

Instead, ensure instance custom method evaluation supplies `resource`.

### 6.2 Treat Tier 1 custom method auth as a precheck only

`auth_interceptor` cannot reliably evaluate resource-dependent rules without fetching the resource. For custom methods:

- It can reject unauthenticated requests when the method rule cannot possibly allow anonymous access.
- It should not grant final access for resource-dependent method rules.
- It should defer final decision to `ActorModel.handler` when an instance method id exists.

Possible strategy:

```text
auth_interceptor for custom method:
  - if no explicit method access and no user -> 401
  - if explicit method access is ANYONE-ish -> allow
  - if explicit method access requires identity and no user -> 401
  - otherwise pass through for Tier 2 resource-aware evaluation
```

If introspecting rule shape is not clean, the safe minimal behavior is:

```text
custom method with explicit access:
  - if no authenticated user and access does not evaluate for anonymous -> deny
  - if authenticated -> pass through; do not treat Tier 1 as final authorization
```

Tier 2 then performs final resource-aware authorization.

### 6.3 Move instance fetch before method access check in ActorModel.handler

In `ActorModel.handler`, for exposed methods:

1. Determine `is_instance` from the method signature.
2. If `is_instance`, require `id` and fetch the instance before method-level auth evaluation.
3. Evaluate `method_access` with `resource=instance`.
4. Execute against that already-loaded instance.

Pseudo-diff shape:

```diff
 if is_exposed:
-    endpoint_info = getattr(method, '__endpoint__', {})
-    method_access = endpoint_info.get('access')
-    if method_access is not None:
-        user = tx.meta.get('user')
-        if user is not None:
-            ctx = AccessContext(user=user, action=tx.name, model_class=cls)
-            if not method_access.evaluate(ctx):
-                await target.send(tx.error("Access denied", code=403))
-                return
-
     sig = get_sig(method)
     is_instance = 'self' in sig.parameters
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
+    endpoint_info = getattr(method, '__endpoint__', {})
+    method_access = endpoint_info.get('access')
+    if method_access is not None:
+        user = tx.meta.get('user')
+        if user is not None:
+            ctx = AccessContext(
+                user=user,
+                action=tx.name,
+                model_class=cls,
+                resource=instance,
+            )
+            if not method_access.evaluate(ctx):
+                code = 401 if not getattr(ctx, "is_authenticated", False) else 403
+                await target.send(tx.error("Authentication required" if code == 401 else "Access denied", code=code))
+                return

     kwargs = {k: v for k, v in data.items() if k != 'id'}
     ... materialize args ...

     if is_instance:
-        entity_id = data.get('id')
-        ... fetch instance ...
         result = method(instance, **kwargs)
     else:
         result = method(**kwargs)
```

### 6.4 Preserve internal-message behavior deliberately

Current code appears to treat `user is None` as internal/no-auth context:

```python
# user is None -> internal message, no auth context
```

The fix should explicitly preserve or revisit that contract.

Recommended explicit rule:

| TX user meta state | Meaning | Method access behavior |
|---|---|---|
| `meta` has no `user` key | Internal actor message | Preserve existing bypass if intentional |
| `meta.user == {}` | External anonymous HTTP request | Evaluate and return `401` where auth required |
| `meta.user` has `user_id` | External authenticated request | Evaluate against resource for instance methods |

Currently `_get_user(request)` returns `{}` for anonymous requests, so HTTP anonymous requests should be distinguishable from truly internal messages if `user` is always included by NetworkAPI.

### 6.5 Avoid double-fetch when practical

The actor method path may need the instance for auth and execution. Fetch once and reuse:

```python
instance = cls.get(entity_id)
...
result = method(instance, **kwargs)
```

This reduces storage calls and makes the access/execute target unambiguous.

---

## 7. Acceptance Criteria

### 7.1 Security behavior

For actor-routed instance custom methods with `access=OWNER | ROLE("admin")`:

| User | Expected |
|---|---|
| Owner | `200` |
| Admin | `200` |
| Authenticated non-owner | `403` |
| Missing token | `401` |
| Missing resource | `404` |

Both generated path styles must pass:

```text
/{tablename}/{id}/{method-route}
/{ClassName}/{id}/{method-route}
```

Example:

```text
GET /secret_documents/1/reveal
GET /SecretDocument/1/reveal
```

### 7.2 Parity with direct route behavior

Actor routing and direct routing should agree for instance custom method auth:

```text
direct route: resource-aware OWNER custom method access
actor route:  resource-aware OWNER custom method access
```

### 7.3 Query parsing remains intact

Existing actor custom method GET query parsing should continue to work:

```text
GET /media/11/files?limit=2&offset=1
```

should still pass `limit` and `offset` into the method.

### 7.4 Error codes remain stable and intentional

Expected status codes:

| Condition | Status |
|---|---:|
| Method requires auth, no token | `401` |
| Authenticated but not allowed by resource rule | `403` |
| Instance id not found | `404` |
| Missing required id for instance method TX | `400` |
| Invalid argument coercion/materialization | `422` where currently used |

### 7.5 No framework-local app workaround required

After the fix, applications should not need to add duplicate app-level guards inside methods solely to compensate for actor route auth behavior.

---

## 8. Test Plan for N3TX Backend Team

### 8.1 Unit tests: ActorModel custom method auth

Add tests under a suitable `n3tx-actors` test module, e.g.:

```text
packages/n3tx-actors/src/n3tx_actors/tests/unit/test_actor_model_method_authorize.py
```

or extend an existing authorization test file.

Recommended cases:

1. `OWNER` instance method succeeds for owner.
2. `OWNER` instance method fails for authenticated non-owner.
3. `OWNER | ROLE("admin")` instance method succeeds for admin.
4. `OWNER | ROLE("admin")` instance method fails for anonymous.
5. Missing instance returns `404` before method execution.
6. Method body is not executed for denied users.
7. Resource is fetched once if feasible to assert cleanly.

### 8.2 Integration tests: NetworkAPI generated route behavior

Add tests under the actor API tests, e.g.:

```text
packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
```

Recommended cases:

1. Table-name generated custom method route enforces owner/admin:

   ```text
   GET /secret_documents/1/reveal
   ```

2. Class-name generated mirror enforces the same policy:

   ```text
   GET /SecretDocument/1/reveal
   ```

3. GET query args still coerce into method parameters:

   ```python
   @expose_route("/slice", methods=["GET"], access=OWNER)
   def slice(self, limit: int = 0, offset: int = 0) -> dict:
       return {"limit": limit, "offset": offset}
   ```

4. Non-owner cannot infer secret output from either path.

### 8.3 Regression tests for CRUD auth

Ensure existing CRUD resource authorization still passes:

```text
get/read/update/delete OWNER checks
list sql_filter behavior
create AUTHENTICATED/OWNER behavior
```

### 8.4 Regression tests for class/collection methods

Ensure class methods that do not have a resource continue to work according to documented semantics:

```python
@classmethod
@expose_route("/create-capture", methods=["POST"], access=AUTHENTICATED)
def create_capture(cls, ...):
    ...
```

The fix should not accidentally require `resource` for class-level actions.

---

## 9. Compatibility and Migration Notes

### 9.1 Expected breaking surface

This is a security correction. Some apps may currently rely unintentionally on permissive actor-routed custom method access. After the fix, those methods may begin returning `403` for authenticated non-owners.

That is desirable if the declared access rule is resource-dependent.

### 9.2 Apps with explicit internal actor messages

If internal actor-to-actor messages call exposed instance methods without `meta.user`, the fix should preserve the existing internal-call contract or document the new requirement.

Recommended compatibility stance:

```text
No user key in TX meta       -> internal call, preserve existing behavior if intentional
user key exists but empty {} -> external anonymous request, enforce auth
user has user_id             -> external authenticated request, enforce resource auth
```

### 9.3 Schema contract should not change

This fix should not change schema output for methods. It should only change runtime authorization correctness.

Expected schema remains:

```json
{
  "methods": {
    "upload_files": {
      "route": "/files",
      "methods": ["GET"],
      "access": ...
    }
  }
}
```

### 9.4 Route contract should not change

Generated route paths and route names should remain stable:

```text
GET /{tablename}/{id}/{route}
GET /{ClassName}/{id}/{route}
```

Example route names are currently shaped like:

```text
custom_{tablename}_{method_name}
```

Changing route names is not required and would create unnecessary app churn.

---

## 10. App-Level Blocker This Fix Unblocks

The Gaussian Splat Capture Portal has a planned cleanup:

```text
.project/plans/039.1-media-files-generated-route.md
```

The goal is to delete an app duplicate adapter:

```text
modules/app/adapters/media_api.py
```

That adapter currently protects:

```text
GET /media/{media_id:int}/files
```

with explicit resource-aware owner/admin checks:

```python
if user.get("role") == "admin":
    return
if user.get("user_id") == getattr(media, "user_owner", None):
    return
raise HTTPException(status_code=403, detail="Access denied")
```

Once N3TX actor-routed instance custom method auth is resource-aware, the app can remove the duplicate route and rely on:

```python
@expose_route("/files", methods=["GET"], access=OWNER | ROLE("admin"))
```

as the single source of truth.

---

## 11. Suggested Developer Workflow

```text
1. Add failing actor-routing tests for instance custom method OWNER access.
2. Confirm non-owner currently succeeds or otherwise document current failure mode.
3. Refactor ActorModel.handler exposed-instance-method path to fetch resource before final method access evaluation.
4. Adjust auth_interceptor so Tier 1 does not incorrectly grant final custom-method access for resource-dependent rules.
5. Preserve class method and internal TX behavior intentionally.
6. Run n3tx-actors, n3tx-core authorization, and example actor app tests.
7. Update docs for actor-routing auth semantics.
```

---

## 12. Documentation Updates Requested

Please update backend/framework docs to explicitly state:

1. Actor-routed instance custom methods evaluate `access=` with `resource=instance`.
2. Tier 1 `auth_interceptor` is not the final authority for resource-dependent custom method rules.
3. Internal actor messages without user context either bypass access intentionally or must supply service/user context — whichever contract the backend team chooses.
4. Direct routing and actor routing have parity for method-level `OWNER`, `ROLE`, `Where`, and composed ABAC rules.

Candidate docs:

```text
packages/n3tx-actors/docs/actor-model.md
packages/n3tx-actors/docs/network-adapters.md
packages/n3tx-core/docs/authorization.md
docs/AUTHORIZATION.md
docs/ACTORS.md
BACKEND.md
```

---

## 13. Open Questions for the Backend Team

1. Should `OWNER.evaluate(ctx)` continue returning `True` for `resource=None`, or should create-specific behavior be represented more explicitly by action type?
2. Should `auth_interceptor` attempt to introspect rule resource-dependence, or should it always defer final custom-method auth to the actor handler for authenticated users?
3. Should anonymous external HTTP requests be distinguished from internal actor messages by checking whether `"user" in tx.meta` rather than `tx.meta.get("user") is None`?
4. Should actor custom method auth support SQL/resource preloading hooks for non-standard ownership fields, remote refs, or service-token user continuity?
5. Should method auth errors preserve exact direct-route error messages for full parity?

---

## 14. Definition of Done

✅ The fix is complete when:

- Actor-routed instance custom methods enforce `OWNER`, `ROLE`, `Where`, and composed access rules against the actual target instance.
- Non-owner authenticated users receive `403` for `OWNER`-guarded instance methods.
- Anonymous users receive `401` where authentication is required.
- Missing resources still return `404`.
- Table-name and class-name method mirrors behave identically.
- Direct-route and actor-route method auth semantics are documented as equivalent.
- Framework tests cover the regression.
- Existing CRUD, class-method, list-filter, and internal actor-message behavior remains intentional and covered.

---

## 15. Reference App Test That Should Pass After Upstream Fix

Once fixed upstream, this app should be able to remove its duplicate media files adapter and rely on tests like:

```python
def test_generated_media_files_rejects_non_owner(self):
    from unittest.mock import patch

    from fastapi.testclient import TestClient
    from n3tx_core.authorize import create_token

    from modules.app.actors import Media
    from modules.app.main import app

    media = Media(
        id=11,
        kind="images",
        upload_id="upload-1",
        filenames=["a.jpg"],
        user_owner=5,
    )
    token = create_token(user_id=99, email="other@example.local", role="user")

    with patch.object(Media, "get", return_value=media):
        response = TestClient(app).get(
            "/media/11/files?limit=1&offset=0",
            headers={"x-access-token": token},
        )

    assert response.status_code == 403
```

And:

```python
def test_generated_media_files_allows_owner(self):
    ...
    token = create_token(user_id=5, email="owner@example.local", role="user")
    response = TestClient(app).get("/media/11/files?limit=1&offset=0", headers={"x-access-token": token})
    assert response.status_code == 200
```

---

## 16. Summary Recommendation

Fix this in the N3TX backend rather than app code.

The correct abstraction is framework-level: `access=OWNER | ROLE("admin")` on an instance custom method should mean the same thing under direct and actor routing. App-level guards are acceptable as temporary mitigations, but they duplicate authorization logic and weaken N3TX’s “model is the app” contract.
