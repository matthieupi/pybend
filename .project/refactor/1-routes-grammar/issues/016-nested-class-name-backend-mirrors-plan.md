# Issue 016 Plan — Nested Class-Name Backend Mirrors

## ✅ Recommendation

Implement issue `016` as a focused backend parity slice: add nested class-name routes that reuse the existing parent-scoped join handlers/dispatch paths instead of creating a new nested-resource subsystem.

Target grammar from issue `015`:

```text
/{ParentClass}/{parent_id}/{ChildClass}/{child_id}

Example:
/Product/1/Comment/2
```

For collection/create routes, use the same class-name prefix without `{child_id}`:

```text
GET    /Product/1/Comment
POST   /Product/1/Comment
GET    /Product/1/Comment/2
PUT    /Product/1/Comment/2
DELETE /Product/1/Comment/2
```

This mirrors the existing legacy nested table grammar:

```text
GET    /products/1/comments
POST   /products/1/comments
GET    /products/1/comments/2
PUT    /products/1/comments/2
DELETE /products/1/comments/2
```

Do **not** mutate stored href arrays in this issue. Issue `010` already moved response `$id` to class-name identity; this issue only makes the nested class-name backend routes resolvable.

---

## 📍 Current Baseline

Relevant current code paths:

| Area | Current behavior | Gap for 016 |
|---|---|---|
| Direct FastAPI | Join models register legacy nested paths from `__owner__`, `__tagname__` | Add `/ParentClass/{parent_id}/ChildClass...` mirrors |
| Actor API | Join models register equivalent legacy nested paths through TX | Add class-name nested TX mirror paths |
| Dump pipeline | Join model `$id` is class-name nested: `/OwnerClass/parent_id/ChildClass/id` | Ensure routes make that `$id` resolvable |
| Registrar | `join_models[(ParentClass, ChildClass)] = JoinModel` | Use this as canonical relationship metadata |
| Issue 015 | Drops relation/tag segment from class-name grammar | Preserve limitation: duplicate same-child relationships are not supported yet |

Core relationship metadata to reuse:

```python
owner_cls = join_model.__owner__       # Product
child_cls = join_model.__parent__      # Comment
tagname = join_model.__tagname__       # comments, favorites, etc. legacy segment
fk_field = f"{owner_cls.__name__.lower()}_id"  # product_id
```

---

## 🧭 Route Shape

For each registered join model, derive two bases:

```python
legacy_base = f"/{owner_cls.__tablename__}/{{parent_id:int}}/{join_cls.__tagname__}"
class_base = f"/{owner_cls.__name__}/{{parent_id:int}}/{child_cls.__name__}"
```

Then register equivalent operations:

| Operation | Legacy route | New class-name route | Handler/dispatch target |
|---|---|---|---|
| list | `GET /products/{parent_id}/comments` | `GET /Product/{parent_id}/Comment` | join model list, filtered by parent |
| create | `POST /products/{parent_id}/comments` | `POST /Product/{parent_id}/Comment` | join model create with parent FK injection |
| read | `GET /products/{parent_id}/comments/{id}` | `GET /Product/{parent_id}/Comment/{id}` | join model read |
| update | `PUT /products/{parent_id}/comments/{id}` | `PUT /Product/{parent_id}/Comment/{id}` | join model update with parent FK injection |
| delete | `DELETE /products/{parent_id}/comments/{id}` | `DELETE /Product/{parent_id}/Comment/{id}` | join model delete |

Class-name nested routes are mirrors; they should not introduce new authorization or storage semantics in this issue.

---

## 🏗️ Direct FastAPI Implementation Plan

Primary file:

```text
packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py
```

### Step 1 — Add a small route metadata helper

Add a helper near route registration helpers so nested route derivation is single-source:

```python
def _nested_route_bases(join_cls):
    owner_cls = getattr(join_cls, '__owner__', None)
    child_cls = getattr(join_cls, '__parent__', None)
    if not owner_cls or not child_cls:
        return None

    return {
        'owner_cls': owner_cls,
        'child_cls': child_cls,
        'legacy_base': f"/{owner_cls.__tablename__}/{{parent_id:int}}/{join_cls.__tagname__}",
        'class_base': f"/{owner_cls.__name__}/{{parent_id:int}}/{child_cls.__name__}",
    }
```

Keep this helper local to route generation unless another module needs it later.

### Step 2 — Reuse existing direct route factories

For join models, create the same handler functions once:

```python
create_instance = make_create_instance(join_cls)
list_instances = make_get_all_instances(join_cls)
read_instance = make_get_instance(join_cls)
update_instance = make_update_instance(join_cls)
delete_instance = make_delete_instance(join_cls)
```

Register them under both bases:

```python
for base in (legacy_base, class_base):
    router.post(base, tags=[tag], status_code=201)(create_instance)
    router.get(base, tags=[tag])(list_instances)
    router.get(f"{base}/{{id:int}}", tags=[tag])(read_instance)
    router.put(f"{base}/{{id:int}}", tags=[tag])(update_instance)
    router.delete(f"{base}/{{id:int}}", tags=[tag])(delete_instance)
```

The current code already registers the legacy `endpoint_base`. The implementation can either:

1. keep the existing legacy calls and add only the class-name calls, or
2. refactor the join-model branch to loop over both bases.

Prefer option 2 if it reduces duplication without changing behavior.

### Step 3 — Preserve root model class-name routes

Only root models should keep these flat class-name collection/CRUD mirrors:

```text
/Product/_
/Product/{id:int}
/Product/{id:int}/{method}
```

For join models, nested class-name routes should be the advertised resolvable identity. If existing `/ProductComment/{id}` mirrors are already present, do not remove them in this issue unless tests require it; treat cleanup/deprecation as separate work.

### Step 4 — Route order guardrails

Keep route registration order deterministic:

```text
1. Static legacy join collection routes:        /products_comments
2. Schema/view routes:                         /Product, /Product/@...
3. Nested join routes:                         /products/{pid}/comments..., /Product/{pid}/Comment...
4. Root class/table CRUD routes:               /Product/{id}, /products/{id}
5. Literal custom method routes
6. Static catch-all mounted by backend
```

FastAPI path matching is exact enough that `/Product/{id:int}` should not match `/Product/1/Comment`, but tests should still lock this down.

---

## 🎭 Actor API Implementation Plan

Primary file:

```text
packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

### Step 1 — Share the same route metadata shape

Add a local helper equivalent to the direct helper:

```python
def _nested_route_bases(join_cls):
    owner_cls = getattr(join_cls, '__owner__', None)
    child_cls = getattr(join_cls, '__parent__', None)
    if not owner_cls or not child_cls:
        return None
    return {
        'legacy_base': f"/{owner_cls.__tablename__}/{{parent_id:int}}/{join_cls.__tagname__}",
        'class_base': f"/{owner_cls.__name__}/{{parent_id:int}}/{child_cls.__name__}",
    }
```

If duplication between core and actors becomes annoying, extract later; for 016, local helpers keep package boundaries simple.

### Step 2 — Register actor nested class-name CRUD routes for join models

In `create_api_routes()`, when `has_parent=True`, call `_register_crud_routes()` for both bases or extend `_register_crud_routes()` to accept extra mirror bases.

Recommended shape:

```python
if parent_class:
    bases = [legacy_base, class_base]
else:
    bases = [endpoint_base]

for base in bases:
    _register_crud_routes(..., endpoint_base=base, has_parent=parent_class is not None)
```

Ensure route names remain unique. If decorator-generated names collide, pass a `name_suffix` into `_register_crud_routes()`.

### Step 3 — Preserve identical TX contracts

Class-name nested mirrors should dispatch to the same join model actor address as legacy nested routes:

```python
TX(
    name='get' | 'list' | 'create' | 'update' | 'delete',
    source='api',
    target=join_cls.__tablename__,
    data=...,
    meta={'user': user, 'model_cls': join_cls},
)
```

Expected payload parity:

| Operation | Expected class-name TX data |
|---|---|
| list | includes `parent_id`, plus `limit`/`offset`/`populate`/`depth` when present |
| create | flattened body plus injected `{owner_lower}_id` FK |
| read | same as legacy read: `{'id': child_id, ...populate/depth}` |
| update | flattened body plus `id` and injected `{owner_lower}_id` FK |
| delete | same as legacy delete: `{'id': child_id}` |

Do not dispatch to `Product` or `Comment`; dispatch to the generated join model table address such as `products_comments`.

---

## 🧪 Test Plan

Follow red/green by layer: add failing tests first, implement direct routes, then actor routes, then examples.

### 1. Core route-generation tests

File:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

Add a test app with `Parent`, `Child`, and `generate_join_model(Parent, Child)` or use the app builder with `join_models=[(Parent, Child)]`.

Assert route presence:

```text
/Parent/{parent_id:int}/Child
/Parent/{parent_id:int}/Child/{id:int}
/parents/{parent_id:int}/children
/parents/{parent_id:int}/children/{id:int}
```

Assert methods:

```text
GET, POST on /Parent/{parent_id:int}/Child
GET, PUT, DELETE on /Parent/{parent_id:int}/Child/{id:int}
```

### 2. Direct behavior tests

Files:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
examples/core/tests/test_cross_model_workflows.py
```

Required cases:

1. `GET /Product/{pid}/Comment` returns the same item IDs/domain fields as `GET /products/{pid}/comments`.
2. `POST /Product/{pid}/Comment` injects `product_id == pid` exactly like the legacy route.
3. `GET /Product/{pid}/Comment/{cid}` returns the same domain fields as legacy nested read.
4. `PUT /Product/{pid}/Comment/{cid}` has the same owner/admin auth behavior as legacy nested update.
5. `DELETE /Product/{pid}/Comment/{cid}` has the same owner/admin auth behavior as legacy nested delete.
6. Response `$id` ends with `/Product/{pid}/Comment/{cid}`.
7. `/Product/{pid}/NotAChild/{cid}` returns deterministic `404`.
8. `/Product/not-int/Comment/{cid}` returns FastAPI validation/404 and does not hit unrelated routes.

Also add a parent-mismatch characterization test before changing semantics:

```text
GET /Product/{wrong_pid}/Comment/{cid}
GET /products/{wrong_pid}/comments/{cid}
```

The 016 mirror must match legacy behavior. If legacy behavior is undesirable, fix both paths in a separate explicit bugfix slice.

### 3. Actor route-generation tests

File:

```text
packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
```

Extend existing join model route tests to assert:

```text
/MockModel/{parent_id:int}/MockChildModel
/MockModel/{parent_id:int}/MockChildModel/{id:int}
```

And method sets:

```text
GET, POST collection
GET, PUT, DELETE member
```

### 4. Actor TX contract tests

File:

```text
packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
```

Use mocked `api.request()` and compare legacy vs class-name nested calls:

```text
GET    /mock_models/7/children/5
GET    /MockModel/7/MockChildModel/5

POST   /mock_models/7/children
POST   /MockModel/7/MockChildModel

PUT    /mock_models/7/children/5
PUT    /MockModel/7/MockChildModel/5

DELETE /mock_models/7/children/5
DELETE /MockModel/7/MockChildModel/5
```

Assertions:

```python
assert table_tx.name == class_tx.name
assert table_tx.target == class_tx.target == 'mock_children'
assert table_tx.data == class_tx.data
assert table_tx.meta['user'] == class_tx.meta['user']
assert table_tx.meta['model_cls'] is class_tx.meta['model_cls'] is MockChildModel
```

### 5. Example parity tests

Files:

```text
examples/core/tests/test_cross_model_workflows.py
examples/actors/tests/test_cross_model_workflows.py
```

Keep the example assertions behavior-focused:

- create comment through `/Product/{pid}/Comment`
- read it through both class-name nested and legacy nested route
- update/delete auth parity for Alice/Bob/Admin
- `$id` is nested class-name identity
- product population still returns expected comments shape

---

## 📚 Documentation Updates

Update after implementation:

```text
BACKEND.md
docs/CORE.md
packages/n3tx-core/docs/app-bootstrap.md
packages/n3tx-actors/docs/network-adapters.md
```

Document the nested class-name backend grammar:

```text
GET    /{ParentClass}/{parent_id}/{ChildClass}
POST   /{ParentClass}/{parent_id}/{ChildClass}
GET    /{ParentClass}/{parent_id}/{ChildClass}/{child_id}
PUT    /{ParentClass}/{parent_id}/{ChildClass}/{child_id}
DELETE /{ParentClass}/{parent_id}/{ChildClass}/{child_id}
```

Also document the known limitation from issue `015`: duplicate relationships from one parent model to the same child model are not represented by this grammar yet.

---

## ⚠️ Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Parent mismatch semantics are already loose | Existing legacy nested routes may not verify `child.parent_id == parent_id` for read/delete | Characterize legacy behavior first; mirror it in 016; fix both paths later if needed |
| Duplicate same-child relationships | `/Product/1/Comment/2` omits relation/tag segment | Preserve issue 015 limitation and rely on current `join_models[(Parent, Child)]` key |
| Route-name collisions in actor decorators | Same handler registered under legacy and class-name bases | Add route-name suffixes for class nested routes if needed |
| Wrong TX target in actor mode | Dispatching to child/root model would bypass join FK behavior | Always target generated join model `__tablename__` |
| Accidental route shadowing | Class-name root routes, views, and nested routes share prefix | Use `{parent_id:int}` and explicit child class segment; add route-order tests |

---

## Verification Commands

Narrow checks during implementation:

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py -q
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py -q
cd /workspace && python3 -m pytest examples/core/tests/test_cross_model_workflows.py -q
cd /workspace && python3 -m pytest examples/actors/tests/test_cross_model_workflows.py -q
```

Final backend verification:

```bash
cd /workspace && python3 scripts/test-backend.py --short
```

---

## Suggested Commit Slices

### Commit 1 — Direct nested mirrors

```text
feat(core): Add nested class-name route mirrors [routes-grammar]
```

Includes:

- direct route-generation tests
- direct behavior/auth/identity tests
- `routes_fastapi.py` implementation

### Commit 2 — Actor nested parity

```text
feat(actors): Add nested class-name route parity [routes-grammar]
```

Includes:

- actor route-generation tests
- actor TX parity tests
- `network_api.py` implementation

### Commit 3 — Example parity and docs

```text
docs(core): Document nested class-name route mirrors [routes-grammar]
```

Includes:

- core/actor example parity tests
- backend docs updates

---

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py`
- `examples/core/tests/test_cross_model_workflows.py`
