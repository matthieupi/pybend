# Issue 015 Plan — Nested Class-Name Route Grammar Decision

## ✅ Recommendation

Adopt the nested class-name grammar already proposed in issue `015`:

```text
/{ParentClass}/{parent_id}/{ChildClass}/{child_id}
```

Example:

```text
/Product/1/Comment/2
```

This should be the canonical nested identity route after issue `010`'s class-name
`$id` migration. The grammar deliberately omits the relationship/tag segment to
keep public URLs compact and model-centric. The generated join model remains the
implementation detail that owns storage, FK fields, authorization shape, and
serialization behavior.

```text
Legacy table route:       /products/1/comments/2
Canonical class route:    /Product/1/Comment/2
Concrete storage model:   ProductComment
Public child identity:    Comment under Product 1
```

---

## 📍 Current State

| Area | Current behavior | Decision needed |
|---|---|---|
| Legacy nested table routes | `/products/{parent_id}/comments/{id}` via generated join model routes | Preserve as compatibility transport |
| Generated join model | `ProductComment(Comment)` with `__owner__=Product`, `__parent__=Comment`, `__tagname__='comments'` | Keep as implementation model |
| Response identity after issue 010 | Join `$id` already points to `/Product/{parent_id}/Comment/{id}` | Confirm as canonical |
| Href arrays | Product `comments` refs may still be legacy-tag or class-name depending current slice | Future slices should converge, not issue 015 |
| Frontend router | Flat routes only; >3 segments invalid | Issue 017 adds narrow nested parse shape |
| Backend mirrors | Root class-name CRUD/method mirrors exist; nested class-name mirrors are not the main completed path | Issue 016 implements direct/actor nested mirrors |

---

## 🧭 Architecture Invariants

1. **The model remains the source of truth.** Nested grammar is derived from
   `__owner__`, `__parent__`, and generated join metadata, not duplicated route
   declarations.
2. **Legacy table routes remain supported.** `/products/1/comments/2` continues
   to work as compatibility transport.
3. **Class-name nested URLs are canonical identity.** After issue `010`, nested
   `$id` uses `/ParentClass/parent_id/ChildClass/child_id`.
4. **Generated join models stay internal.** URLs expose the semantic child class
   (`Comment`), not the generated class (`ProductComment`).
5. **No `$href` or `links` metadata.** The response `$id` is the resolvable
   identity; route availability carries the migration.
6. **No arbitrary-depth grammar yet.** Support exactly one parent-child hop in
   issues `016` and `017`.
7. **Duplicate same-child relationships are not silently supported.** If a parent
   has two relationships to the same child class, class-name nested mirrors must
   fail or skip deterministically until relation aliases exist.

---

## Target Grammar

### Backend JSON routes

For a `Product.comments: ListRef[Comment]` relationship represented by generated
join model `ProductComment`:

| Operation | Legacy route | Class-name nested route |
|---|---|---|
| List children | `GET /products/1/comments` | `GET /Product/1/Comment` |
| Create child | `POST /products/1/comments` | `POST /Product/1/Comment` |
| Read child | `GET /products/1/comments/2` | `GET /Product/1/Comment/2` |
| Update child | `PUT /products/1/comments/2` | `PUT /Product/1/Comment/2` |
| Delete child | `DELETE /products/1/comments/2` | `DELETE /Product/1/Comment/2` |
| Literal method | `POST /products/1/comments/2/like` | `POST /Product/1/Comment/2/like` |

Notes:

- Method mirrors should remain literal `@expose_route` method paths only.
- Do not add a generic nested method catch-all.
- `GET /Product` remains schema and is unaffected.
- `GET /Product/_` remains the root collection class-name marker and is
  unrelated to nested collection routes.

### Backend HTML/view routes

View routes can be reserved now, even if issue `016` chooses not to implement all
of them in the first tracer bullet:

| View route | Meaning |
|---|---|
| `GET /Product/1/Comment/@` | Nested collection default view shell |
| `GET /Product/1/Comment/@table` | Nested collection named view shell |
| `GET /Product/1/Comment/2/@` | Nested member default view shell |
| `GET /Product/1/Comment/2/@item` | Nested member named view shell |

The same `@` invariant applies: view routes never dispatch CRUD or method TXs.

### Frontend hash routes

Issue `017` should support only the approved narrow nested grammar:

```text
#Product/1/Comment/2
#Product/1/Comment/2/@
#Product/1/Comment/2/@item
#Product/1/Comment/2/like
```

Nested collection hash routes may be added if a concrete UI mounts them:

```text
#Product/1/Comment
#Product/1/Comment/@
#Product/1/Comment/@table
```

---

## Join Model Identity Decision

### Public URL exposes the semantic child class

Use this canonical nested identity:

```text
/Product/1/Comment/2
```

Do **not** expose generated join model names as canonical public identity:

```text
/Product/1/ProductComment/2   # rejected
/ProductComment/2             # rejected
```

### `$schema` should identify the actual response shape

Generated join models inherit from child models but often carry relationship
fields such as `product_id`. Therefore the most accurate schema remains the
concrete generated model schema:

```json
{
  "$schema": "http://localhost:5000/ProductComment",
  "$id": "http://localhost:5000/Product/1/Comment/2",
  "id": 2,
  "product_id": 1
}
```

If a future product decision wants semantic child schemas in nested responses,
that should be a separate serialization decision because it may hide
relationship-specific fields.

### `$id` after issue 010

For generated join models:

```python
owner_cls = Product
child_cls = Comment  # from __parent__
parent_id = instance.product_id
child_id = instance.id
```

`$id` becomes:

```text
{API_URL}/Product/{parent_id}/Comment/{child_id}
```

No `$href` and no `links` are emitted.

---

## Duplicate Same-Child Relationship Decision

The chosen grammar is intentionally simple but cannot distinguish multiple
relationships from the same parent class to the same child class:

```python
class Product(ProtoModel):
    comments: ListRef[Comment]
    reviews: ListRef[Comment]
```

Both would want:

```text
/Product/1/Comment/2
```

Decision for issues `016` and `017`:

1. Detect duplicate `(owner_class, child_class)` relationship registrations.
2. Register a nested class-name mirror only when the pair is unique.
3. If duplicates exist, fail route registration or skip class-name nested mirrors
   for that pair with a clear warning/error.
4. Preserve legacy tag routes, which remain unambiguous:

```text
/products/1/comments/2
/products/1/reviews/2
```

Future relation-aware extension, if needed:

```text
/Product/1/@comments/Comment/2
/Product/1/@reviews/Comment/2
```

That relation-aware grammar should be introduced only when the framework has a
backend-authoritative route alias/relation layer.

---

## Alias Interaction

Issue `019` may introduce backend-authoritative aliases. Nested canonical routes
should remain class-name based unless aliases are explicitly resolved by the
same central alias registry.

Future examples:

```text
/Product/1/Comment/2         # canonical
/products/1/comments/2       # legacy table transport
/catalog/1/review/2          # possible alias, only if registry maps it
```

Alias rules:

1. Aliases must resolve to canonical model classes before route dispatch.
2. Aliases must not alter `$schema` or `$id` canonical identity unless a future
   alias-identity policy explicitly changes that.
3. Duplicate aliases that make nested routes ambiguous must fail at bootstrap.
4. Relation aliases should be the future solution for duplicate same-child
   relationships, not response-side `$href`/`links` metadata.

---

## Route Order Constraints

Backend route registration must keep static/view routes from being captured by
generic integer routes.

Recommended direct/actor ordering per owner-child pair:

```text
GET    /{ParentClass}                                  schema/root routes first
GET    /{ParentClass}/@...                             root view routes
GET    /{ParentClass}/_                                root collection marker
GET    /{ParentClass}/{parent_id:int}                  root instance route
GET    /{ParentClass}/{parent_id:int}/@...             root member view routes

GET    /{ParentClass}/{parent_id:int}/{ChildClass}/@...
GET    /{ParentClass}/{parent_id:int}/{ChildClass}
POST   /{ParentClass}/{parent_id:int}/{ChildClass}
GET    /{ParentClass}/{parent_id:int}/{ChildClass}/{child_id:int}/@...
GET    /{ParentClass}/{parent_id:int}/{ChildClass}/{child_id:int}
PUT    /{ParentClass}/{parent_id:int}/{ChildClass}/{child_id:int}
DELETE /{ParentClass}/{parent_id:int}/{ChildClass}/{child_id:int}
POST   /{ParentClass}/{parent_id:int}/{ChildClass}/{child_id:int}/{literal_method}
```

Constraints:

- Use `{parent_id:int}` and `{child_id:int}`.
- Register `@` view routes before any method-like nested routes.
- Register literal methods only; no catch-all method route.
- Existing legacy join/static routes remain registered before table-name
  parameterized routes.

---

## Parser and Runtime Implications

Issue `017` should extend `Router.parseRoute()` without weakening current invalid
route handling.

### New parsed shapes

Nested collection:

```js
{
  type: 'nested-collection',
  parentModel: 'Product',
  parentId: '1',
  model: 'Comment',
  params: {}
}
```

Nested detail:

```js
{
  type: 'nested-detail',
  parentModel: 'Product',
  parentId: '1',
  model: 'Comment',
  id: '2',
  params: {}
}
```

Nested member view:

```js
{
  type: 'nested-detail',
  parentModel: 'Product',
  parentId: '1',
  model: 'Comment',
  id: '2',
  isViewRoute: true,
  view: 'item',
  params: {}
}
```

Nested action:

```js
{
  type: 'nested-action',
  parentModel: 'Product',
  parentId: '1',
  model: 'Comment',
  id: '2',
  action: 'like',
  params: {}
}
```

### Mount/ref contract

For nested detail/member views, `resolveRoute()` should produce a nested class-name
ref so the mounted component uses canonical transport identity:

```js
{
  tag: 'ntx-item',
  attrs: {
    ref: 'Product/1/Comment/2',
    display: 'lg'
  }
}
```

For nested action:

```js
{
  tag: 'ntx-item', // or method renderer
  attrs: {
    ref: 'Product/1/Comment/2',
    method: 'like',
    display: 'lg'
  }
}
```

Do not implement arbitrary-depth parsing such as:

```text
Product/1/Comment/2/Like/3/...
```

unless a later issue defines recursive nested grammar.

---

## Alternatives Rejected or Deferred

| Alternative | Status | Reason |
|---|---:|---|
| `/Product/1/comments/2` | Rejected | Uses relation/tag name as public identity; duplicates legacy grammar shape. |
| `/Product/1/comments/Comment/2` | Deferred | Solves duplicate relationships but is noisier; keep for future relation-aware extension. |
| `/Product/1/@comments/Comment/2` | Deferred | Good future alias/relation shape, but requires explicit relation namespace design. |
| `/Product/1/ProductComment/2` | Rejected | Exposes generated implementation class in public identity. |
| `/ProductComment/2` | Rejected | Drops parent scope and weakens nested ownership semantics. |
| `$href` plus `$id` split | Rejected by current migration | Issue 010 chose direct `$id` class-name identity without parallel link metadata. |

---

## Implementation Plan for Follow-Up Issues

### Phase 1 — Document and lock the decision

Files:

- `.project/refactor/1-routes-grammar/issues/015-nested-class-name-grammar-decision.yaml`
- `.project/refactor/1-routes-grammar/issues/015-nested-class-name-grammar-decision-plan.md`
- `docs/CORE.md`
- `BACKEND.md`
- `FRONTEND.md`

Actions:

1. Record the grammar and examples.
2. Record the join model identity decision.
3. Record duplicate same-child relationship limitation.
4. Record alias interaction and route-order constraints.

Verification: documentation review only.

### Phase 2 — Direct backend nested mirrors (`016`)

Files:

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-core/src/n3tx_core/utils/registrar.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `examples/core/tests/`

Actions:

1. Build owner-child lookup from join metadata.
2. Detect duplicate `(owner_class, child_class)` relationships.
3. Register nested class-name list/create/read/update/delete mirrors for unique
   relationships.
4. Reuse existing join-model handlers so FK injection, auth, populate, and
   serialization remain centralized.
5. Add tests comparing class-name nested routes against legacy table nested
   routes.

### Phase 3 — Actor nested parity (`016`)

Files:

- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py`
- `examples/actors/tests/`

Actions:

1. Register the same nested route shapes in `NetworkAPI`.
2. Dispatch TXs to the generated join model's table-name actor address.
3. Preserve `meta.user` and `meta.model_cls`.
4. Add TX equivalence tests against legacy nested routes.

### Phase 4 — Frontend nested route support (`017`)

Files:

- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`
- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Component.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`
- `tests/frontend/tests/core/route-functions.test.js`
- `tests/frontend/tests/core/Router.test.js`
- `tests/frontend/tests/components/ntx-router.test.js`

Actions:

1. Add narrow parser support for nested collection/detail/action/view routes.
2. Add build-route round trips.
3. Resolve nested detail refs to `Parent/id/Child/id`.
4. Preserve invalid-route behavior for unsupported extra segments.
5. Add router state and DOM mount tests.

---

## Test Matrix for Issues 016–017

### Backend behavior tests

```text
GET    /Product/1/Comment
POST   /Product/1/Comment
GET    /Product/1/Comment/2
PUT    /Product/1/Comment/2
DELETE /Product/1/Comment/2
POST   /Product/1/Comment/2/like
```

Assertions:

- Domain fields match legacy `/products/1/comments/...` routes.
- Create injects `product_id=1`.
- Update/delete enforce same auth rules.
- Missing parent/child returns deterministic 404 or 403 matching legacy behavior.
- `$id` ends with `/Product/1/Comment/2`.
- `$schema` identifies the concrete generated join model unless explicitly changed.

### Frontend route tests

```text
parseRoute('Product/1/Comment/2')
parseRoute('Product/1/Comment/2/@item')
parseRoute('Product/1/Comment/2/like')
buildRoute(parseRoute('Product/1/Comment/2'))
resolveRoute(parseRoute('Product/1/Comment/2'))
```

Assertions:

- `Product/1/Comment/2` is `nested-detail`.
- `Product/1/Comment/2/@item` is nested detail view, no `method` attr.
- `Product/1/Comment/2/like` is nested action with `method='like'`.
- Extra unsupported segments remain invalid.

---

## Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Duplicate same-child relationships | `/Product/1/Comment/2` cannot distinguish `comments` vs `reviews` | Detect duplicates and defer to legacy routes or future relation aliases |
| Generated join schema confusion | URL says `Comment`, schema may say `ProductComment` | Document `$id` vs `$schema`: identity vs concrete response shape |
| Route shadowing | Nested class names and `@` segments could be misparsed | Use int path converters and register view/static routes before parameter routes |
| Frontend parser broadening | Arbitrary segments could mount wrong components | Add only fixed nested shapes and keep invalid-route tests |
| Actor/direct drift | Level 3 must behave like direct routes | Add TX equivalence tests for every nested mirror |
| Identity/transport mismatch | Frontend uses `$id` as transport href | Ensure backend nested mirrors exist before relying on nested `$id` refs |

---

## Acceptance Checklist

- [x] Grammar chosen: `/{ParentClass}/{parent_id}/{ChildClass}/{child_id}`.
- [x] CRUD, method, and view route examples documented.
- [x] Join model identity decision documented: URL uses child class, concrete model remains generated join class.
- [x] Nested `$id` after issue `010` documented without `$href` or `links`.
- [x] Duplicate same-child relationship trade-off documented.
- [x] Alias interaction documented.
- [x] Route-order constraints documented.
- [x] Parser changes for issue `017` identified.

---

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`
- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
