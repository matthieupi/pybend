# Class-Name Identity and API Migration Plan

## 0. Executive Summary

This phase updates the work intentionally deferred by the first hypermedia route
grammar refactor, with one simplification: **flip `$id` directly to class-name
identity** instead of introducing `$href` or `links` as intermediate metadata.

```text
1. migrate $id to /ClassName/id immediately
2. migrate nested $id to /ParentClass/parent_id/ChildClass/child_id
3. add full class-name CRUD mirrors
4. add class-name method mirrors
5. bring actor routing to parity
6. add friendly model aliases later
7. keep arbitrary ntx-${view} fallback disabled in production
```

Recommended implementation order:

```text
Phase A  Flip response $id to class-name identity
Phase B  Verify frontend runtime on class-name $id
Phase C  Add direct FastAPI class-name write/method mirrors
Phase D  Add actor class-name CRUD/method parity
Phase E  Implement nested class-name backend/frontend support
Phase F  Add backend-authoritative route aliases
Phase G  Lock schema-only view fallback contract
```

The existing table-name API remains supported throughout the migration. It is
compatibility transport, not the advertised response identity.

---

## 1. Current State

The completed route grammar refactor added these contracts:

```text
GET /{ClassName}                 JSON Schema
GET /{ClassName}/{id:int}        read-only class-name mirror
GET /{ClassName}/@...            HTML/view routes
GET /{tablename}/...             legacy/current JSON API
```

### 1.1 Identity today

Schema identity is already class-name based:

```json
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Product",
  "__name__": "Product",
  "__tablename__": "products"
}
```

Entity identity is currently table-name based:

```json
{
  "$schema": "http://localhost:5000/Product",
  "$id": "http://localhost:5000/products/1"
}
```

Nested/join identity is currently parent-scoped and table-name based:

```text
/products/1/comments/2
```

### 1.2 Target identity

Regular entity response:

```json
{
  "$schema": "http://localhost:5000/Product",
  "$id": "http://localhost:5000/Product/1"
}
```

Nested/join response:

```json
{
  "$schema": "http://localhost:5000/Comment",
  "$id": "http://localhost:5000/Product/1/Comment/2"
}
```

There is no `$href` and no `links` object in this plan.

---

## 2. Target Architecture

### 2.1 Route layers

```text
/{ClassName}                         schema/type endpoint
/{ClassName}/{id:int}                canonical entity identity/read route
/{ClassName}/@...                    HTML/view routes
/{ClassName}/{id:int}/{method}       method mirrors
/{ParentClass}/{pid}/{ChildClass}/{id} nested class-name identity

/{tablename}/...                     legacy API compatibility
```

`GET /{ClassName}` remains schema. Therefore a class-name list mirror still
cannot use `GET /{ClassName}` unless schema routing is redesigned. List remains
table-name based for this phase.

### 2.2 Frontend mental model

The frontend already treats `$id` as the instance href. Under this simplified
plan, that remains true:

```text
response.$id -> instance.href -> READ/UPDATE/DELETE/method target
```

Because `$id` becomes class-name based, class-name write/method/nested routes
must be added promptly so frontend operations continue to work.

---

## 3. Phase Plan

## Phase A — Flip Response `$id` to Class-Name Identity

Issue: `010-dual-link-response-metadata.yaml` (retitled in content)

Goal: make model responses advertise class-name identity directly.

### Files

```text
packages/n3tx-core/src/n3tx_core/models/proto_dump.py
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

### Implementation sketch

Regular model URL generation:

```python
def instance_url(instance, d: dict) -> dict:
    cls = instance.__class__
    instance_id = getattr(instance, 'id', None)
    d['$id'] = f"{config.API_URL}/{cls.__name__}/{instance_id}" if instance_id is not None else None
    return d
```

Join/nested URL generation:

```python
owner_cls = getattr(cls, '__owner__', None)
child_cls = getattr(cls, '__parent__', None) or cls
parent_id = getattr(instance, f"{owner_cls.__name__.lower()}_id", None)
d['$id'] = f"{config.API_URL}/{owner_cls.__name__}/{parent_id}/{child_cls.__name__}/{instance_id}"
```

Storage populated-child overrides must use the same class-name nested shape.

### Acceptance highlights

- Regular `$id` is `/ClassName/id`.
- Nested `$id` is `/ParentClass/parent_id/ChildClass/child_id`.
- `$href` is not emitted.
- `links` is not emitted.
- Legacy table-name routes remain available.

---

## Phase B — Frontend Runtime Verification on Class-Name `$id`

Issue: `011-frontend-identity-transport-split.yaml` (retitled in content)

Goal: audit and update the frontend so class-name `$id` works as the instance
href without adding a separate transport field.

### Files

```text
packages/n3tx-core/src/n3tx_core/static/core/NTT.js
packages/n3tx-core/src/n3tx_core/static/core/Component.js
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list-field.js
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js
tests/frontend/tests/core/NTT.test.js
tests/frontend/tests/integration/schema-bootstrap.test.js
```

### Implementation sketch

Keep the simple invariant:

```js
this.href = data.$id || `${DynamicClass.href}/${data.id}`;
```

Update tests so class-name `$id` values are accepted and used for reads,
updates, deletes, methods, and component refs. Remove any expectation that
`$href` or `links` exist.

---

## Phase C — Direct Class-Name Write and Method Mirrors

Issues:

```text
012-direct-class-name-write-mirrors.yaml
013-direct-class-name-method-mirrors.yaml
```

Goal: add direct FastAPI class-name write/method routes by reusing existing
handlers.

### Route target

Add:

```text
POST   /Product
PUT    /Product/{id:int}
DELETE /Product/{id:int}
POST   /Product/{id:int}/run
```

Do not add:

```text
GET /Product  # already schema, not list
```

Method mirrors should be literal decorator routes only; do not add a generic
`/Product/{id:int}/{method}` catch-all.

---

## Phase D — Actor Class-Name CRUD and Method Parity

Issue: `014-actor-class-name-crud-method-parity.yaml`

Goal: Level 3 actor routing behaves like direct routing for class-name
write/method mirrors. Class-name routes still dispatch to table-name actor
addresses so authorization, lifecycle hooks, storage, and method execution stay
centralized.

---

## Phase E — Nested Class-Name Backend and Frontend Support

Issues:

```text
015-nested-class-name-grammar-decision.yaml
016-nested-class-name-backend-mirrors.yaml
017-frontend-nested-class-route-support.yaml
```

Chosen grammar:

```text
/{ParentClass}/{parent_id}/{ChildClass}/{child_id}
```

Examples:

```text
GET    /Product/1/Comment/2
PUT    /Product/1/Comment/2
DELETE /Product/1/Comment/2
```

This intentionally drops the relation segment for simplicity. If N3TX later
needs multiple relationships from the same parent model to the same child class,
the grammar will need a relation-aware extension or alias strategy.

Frontend parser shape:

```js
{
  type: 'nested-detail',
  parentModel: 'Product',
  parentId: '1',
  model: 'Comment',
  id: '2',
  params: {},
}
```

---

## Phase F — Backend-Authoritative Route Aliases

Issues:

```text
019-backend-route-aliases.yaml
020-frontend-alias-resolution.yaml
```

Goal: allow friendly routes without weakening canonical schema identity.

---

## Phase G — Lock Schema-Only View Fallback

Issue: `021-lock-schema-only-view-fallback.yaml`

Goal: keep arbitrary `ntx-${view}` fallback disabled in production.

---

## 4. Dependency Graph

```text
010 flip $id identity
  ├── 011 frontend class-name $id audit
  ├── 012 direct write mirrors
  │    └── 013 direct method mirrors
  │         └── 014 actor parity
  └── 015 nested grammar decision
       └── 016 nested backend mirrors
            └── 017 frontend nested support

019 backend aliases
  └── 020 frontend aliases

021 schema-only view fallback can run independently
```

---

## 5. Risk Table

| Risk | Why it matters | Mitigation |
|---|---|---|
| `$id` flip breaks writes | Frontend uses `$id` as transport href | Add direct/actor class-name writes and methods immediately after identity flip |
| `GET /ClassName` conflict | Already schema endpoint | Do not add class-name list mirror in this phase |
| Method mirrors shadow view routes | `/Product/1/@run` must remain view | Register literal method routes only; preserve route order |
| Nested grammar ambiguity | Multiple relations can point to same child type | Accept simple grammar now; revisit if duplicate same-child relations become a requirement |
| Alias collision | Root URL namespace is shared | Strict bootstrap validation |
| Actor/direct drift | Level 3 must behave like direct mode | Add actor parity tests for every direct mirror |
| External clients store table `$id` | Identity migration is public API change | Keep legacy table-name routes and document the change |
| Arbitrary component mounting | URL could mount undeclared tags | Keep schema-only custom views and safe tag validation |

---

## 6. Acceptance Checklist

| Area | Required proof |
|---|---|
| `$id` identity | Responses use `/ClassName/id` and nested `/Parent/id/Child/id` |
| Frontend runtime | Existing href/caching logic works with class-name `$id` |
| Direct API | Class-name create/update/delete/method mirrors reuse existing handlers |
| Actor API | Class-name mirrors dispatch equivalent TXs to table-name actor targets |
| Nested routes | Simple nested class grammar works direct + actor + frontend |
| Aliases | Backend validates aliases and frontend resolves them to canonical models |
| View fallback | Unknown custom `@view` does not auto-mount arbitrary `ntx-*` components |
| Compatibility | Existing table-name routes continue working |
| Docs | `BACKEND.md`, `FRONTEND.md`, `docs/CORE.md`, and package docs reflect final contracts |

---

## 7. Issue Map

Follow-up issues for this phase live in:

```text
.project/refactor/1-routes-grammar/issues/
```

| ID | File | Type |
|---:|---|---|
| 010 | `010-dual-link-response-metadata.yaml` | AFK |
| 011 | `011-frontend-identity-transport-split.yaml` | AFK |
| 012 | `012-direct-class-name-write-mirrors.yaml` | AFK |
| 013 | `013-direct-class-name-method-mirrors.yaml` | AFK |
| 014 | `014-actor-class-name-crud-method-parity.yaml` | AFK |
| 015 | `015-nested-class-name-grammar-decision.yaml` | HITL |
| 016 | `016-nested-class-name-backend-mirrors.yaml` | AFK |
| 017 | `017-frontend-nested-class-route-support.yaml` | AFK |
| 019 | `019-backend-route-aliases.yaml` | HITL |
| 020 | `020-frontend-alias-resolution.yaml` | AFK |
| 021 | `021-lock-schema-only-view-fallback.yaml` | AFK |

Issue 018 is superseded by issue 010 because the `$id` flip now happens first.

---

## 8. Recommended First Commit Sequence

### Commit 1 — Flip response identity

```text
feat(core): Flip responses to class-name identity [routes-grammar]
```

Scope:

- `proto_dump.py`
- `sqlite_storage.py` populated child override
- proto dump tests
- route mirror identity tests

### Commit 2 — Frontend class-name identity audit

```text
test(frontend): Verify class-name response identity [routes-grammar]
```

Scope:

- `NTT.js` if needed
- `Component.js` if needed
- frontend identity/cache tests

### Commit 3 — Direct write mirrors

```text
feat(core): Add class-name write route mirrors [routes-grammar]
```

### Commit 4 — Direct method mirrors

```text
feat(core): Add class-name method route mirrors [routes-grammar]
```

### Commit 5 — Actor parity

```text
feat(actors): Add class-name CRUD and method parity [routes-grammar]
```

---

## 9. Final Recommendation

Keep the identity model simple:

```text
$schema  model schema URL: /ClassName
$id      model instance URL: /ClassName/id or /Parent/id/Child/id
```

Do not add `$href` or `links` until a concrete consumer requires them. The
migration cost moves to route availability and tests, which is easier to reason
about than carrying parallel identity fields across the stack.
