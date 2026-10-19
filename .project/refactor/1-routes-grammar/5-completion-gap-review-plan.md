# Hypermedia Route Grammar — Completion Gap Review Plan

## ✅ Executive Summary

Issues `001` through `009` are mostly implemented. The remaining work is not a broad architecture rebuild; it is a focused closure pass around **proof, parity, browser coverage, and status documentation**.

The main implementation risk is actor-mode parity in the real example app:

```text
NetworkAPI route parity exists and is unit-tested,
but examples/actors may not expose ViewableMixin HTML routes unless n3tx_ui
is imported before model definitions.
```

Recommended closure order:

```text
1. Actor example parity and import-order check
2. Direct class-name mirror parity tests for auth/populate
3. Browser smoke coverage gaps
4. Standalone custom renderer browser/integration proof
5. Documentation/status cleanup
```

---

## 1. Current Completion Status

| Phase | Status | Evidence summary | Remaining work |
|---|---:|---|---|
| Phase 0 — legacy regression lock | ✅ Done | Legacy frontend/backend routes remain covered | None obvious |
| Phase 1 — parser/builder `@` grammar | ✅ Done | `Product/@`, `Product/@table`, `Product/1/@`, `Product/1/@item` supported | None obvious |
| Phase 2 — schema-driven view resolution | ✅ Done | Renderer lookup and method/view distinction implemented | None obvious |
| Phase 3 — router state + DOM mounting | ✅ Done | Hash sync, back/reset, `ntx-router` mount covered | None obvious |
| Phase 4 — direct class-name read mirrors | ✅ Implemented | `/ClassName/{id}` mirrors table-name read via shared handler | Add explicit auth/populate parity tests |
| Phase 5 — direct HTML/view entrypoints | ✅ Done | `ViewableMixin` owns `/ClassName/@...` HTML routes | Document missing-id shell behavior |
| Phase 6 — actor API parity | ⚠️ Mostly done | `NetworkAPI` unit tests cover class-name mirror and HTML hook delegation | Add `examples/actors` parity tests and import-order fix if needed |
| Phase 7 — sidebar migration | ✅ Done | Sidebar selected-state and generated links support `@` routes | None obvious |
| Phase 8 — browser smoke/docs | ⚠️ Mostly done | Core route grammar smoke exists | Add named-member refresh, optional legacy refresh, Veille smoke if migrated |

---

## 2. Issue-by-Issue Review

| Issue | Status | Notes |
|---|---:|---|
| `001` collection default view | ✅ Done | Frontend `Product/@` and backend `/Product/@` implemented through `ViewableMixin` |
| `002` named collection view | ✅ Done | `Product/@table` and `/Product/@table` implemented |
| `003` member default + class read | ✅ Implemented | `/Product/1`, `Product/1/@`, `/Product/1/@` implemented; explicit parity tests still needed |
| `004` named member collision | ✅ Done | `Product/1/run` vs `Product/1/@run` distinction covered |
| `005` token hardening | ✅ Done | Policy became stricter: unknown custom views require schema-declared renderers |
| `006` actor parity | ⚠️ Partial proof | `NetworkAPI` unit parity exists; real `examples/actors` parity unproven |
| `007` sidebar migration | ✅ Done | Sidebar selected state and first-party link generation migrated |
| `008` browser smoke | ⚠️ Mostly done | Core smoke exists; named-member refresh and Veille/AgentActor smoke remain |
| `009` standalone imports | ✅ Implemented | String/unit-tested; needs browser/integration proof for custom element upgrade |

---

## 3. Important Design Deviations to Preserve

### 3.1 View routes are owned by `ViewableMixin`

This is a beneficial architectural correction from the earlier generic route-registration idea.

```text
StorableMixin  -> data/CRUD capability
ViewableMixin  -> HTML/view capability
```

Core delegates without importing `n3tx_ui` directly:

```python
register_view_routes = getattr(model_class, 'register_view_routes', None)
if callable(register_view_routes):
    register_view_routes(router, tag=tag)
```

Keep this boundary. Do not move view route ownership back into generic core route logic.

### 3.2 Backend HTML routes mount direct components

The implemented shell renders direct component entrypoints such as:

```html
<ntx-list model="Product"></ntx-list>
<ntx-item ref="Product/1" display="lg"></ntx-item>
```

This is simpler than bootstrapping a router shell with an initial route, and is appropriate for standalone view entrypoints.

### 3.3 Unknown custom views are stricter than the early plan

The original architecture sketch allowed ergonomic fallback:

```text
custom-card -> ntx-custom-card
```

The completed hardening work requires unknown custom views to be schema-declared. Preserve this stricter policy unless a future product decision explicitly relaxes it.

---

## 4. Remaining Work Plan

## P0 — Actor Example Parity

Goal: prove Level 3 example apps expose the same route grammar as direct apps.

### Files to inspect/update

```text
examples/actors/main.py
examples/actors/models/*.py
examples/actors/tests/
packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

### Steps

1. Check import ordering in `examples/actors/main.py`.
   - If `n3tx_ui` is not imported before models with `__ui__`, add it before model imports.
   - This is needed so `ViewableMixin` is registered before model class creation.
2. Add `examples/actors` tests for class-name read mirror:

```text
GET /Product/{id}
```

Expected behavior:

```text
mirrors GET /products/{id}
$schema ends with /Product
$id ends with /products/{id}
```

3. Add `examples/actors` tests for HTML routes if actor example is expected to expose view routes:

```text
GET /Product/@
GET /Product/@table
GET /Product/{id}/@
GET /Product/{id}/@item
```

Expected behavior:

```text
200 text/html
collection/member renderer shell present
routes do not dispatch CRUD TXs for HTML shell rendering
```

4. Run actor-focused verification:

```bash
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py examples/actors/tests/ -q
```

### Acceptance checklist

- [ ] `examples/actors` imports `n3tx_ui` before viewable models are defined, if HTML routes are expected.
- [ ] `GET /Product/{id}` mirrors `GET /products/{id}` in actor example.
- [ ] Actor example class-name mirror preserves `$schema` and `$id` contracts.
- [ ] Actor example class-name mirror preserves auth behavior.
- [ ] Actor example HTML routes return `text/html`.
- [ ] Legacy actor table-name routes remain unchanged.

---

## P1 — Direct Class-Name Mirror Parity Tests

Goal: prove direct `/ClassName/{id}` mirrors table-name reads for auth and query-driven data shape, not only basic payload identity.

### Files to update

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
examples/core/tests/
```

### Steps

1. Add explicit populate/depth parity test:

```text
GET /Product/{id}?populate=comments&depth=1
GET /products/{id}?populate=comments&depth=1
```

Assert equivalent domain shape and unchanged `$id`.

2. Add auth parity test for a protected/owner-aware resource:

```text
GET /ProtectedModel/{id}
GET /protected_models/{id}
```

Assert matching status and error shape for unauthenticated/unauthorized requests.

3. Add example-level smoke if practical:

```text
examples/core/tests/test_class_name_routes.py
```

Cover:

```text
/Product/{id}
/Product/@
/Product/@table
/Product/{id}/@
/Product/{id}/@item
```

### Verification

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py examples/core/tests/ -q
```

### Acceptance checklist

- [ ] `/ClassName/{id}?populate=...&depth=...` mirrors table-name query behavior.
- [ ] `/ClassName/{id}` auth behavior matches `/tablename/{id}`.
- [ ] Example core app covers at least one real model class-name read route.
- [ ] Example core app covers at least one real model HTML view route.

---

## P1 — Browser Smoke Coverage Gaps

Goal: close the last browser-level route grammar gaps.

### Files to update

```text
tests/frontend/tests/e2e/route-grammar-smoke.spec.js
tests/frontend/tests/e2e/veille*.spec.js   # only if Veille is considered migrated
```

### Steps

1. Add refresh test for named member route:

```text
/#Product/{seeded_id}/@item
refresh
same member view remounts
```

2. Optionally add refresh tests for legacy routes:

```text
/#Product
/#Product/{seeded_id}
```

3. Add Veille/AgentActor smoke only if that app has migrated to the new grammar:

```text
/#AgentActor/@
/#AgentActor/{id}/@
/#AgentActor/{id}/@chat
```

4. Verify dashboard/home route still clears hash and does not produce `#@`.

### Verification

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/route-grammar-smoke.spec.js
```

For Veille, if added:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/veille.playwright.config.js
```

### Acceptance checklist

- [ ] Refresh on `/#Product/{id}/@item` remounts the named member view.
- [ ] Browser back from member view to collection view remains green.
- [ ] Legacy route refresh remains green if added.
- [ ] Veille/AgentActor route smoke exists if the app is migrated.

---

## P2 — Standalone Custom Renderer Browser/Integration Proof

Goal: prove issue `009` works beyond string-level script assertions.

### Files to inspect/update

```text
packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py
tests/frontend/tests/e2e/
apps/veille/
```

### Steps

1. Add or extend a test that requests a real standalone custom-renderer route, such as:

```text
GET /Grant/{id}/@
```

2. Assert HTML includes the resolved custom renderer module:

```text
/components/ntx-grant-item.js
```

3. Add browser-level proof if practical:
   - navigate directly to the standalone backend URL,
   - wait for the custom element to upgrade,
   - assert non-empty rendered content.

### Acceptance checklist

- [ ] Standalone custom member shell includes custom renderer module import.
- [ ] Default imports remain de-duplicated.
- [ ] Browser/integration test proves a custom renderer upgrades and renders.

---

## P2 — Document Missing-ID HTML Shell Behavior

Current behavior appears to return shell HTML for any integer member ID:

```text
GET /Product/999999/@ -> 200 text/html shell
```

This is reasonable if the route is defined as a **view entrypoint** and the frontend entity fetch owns the missing-record state. It should be documented explicitly.

### Files to update

```text
BACKEND.md
docs/CORE.md
packages/n3tx-ui/docs/viewable-mixin.md
```

### Acceptance checklist

- [ ] Docs state that member HTML routes may return shell HTML without verifying entity existence.
- [ ] Docs state that actual record missing/error state is handled by the mounted frontend component/data fetch.
- [ ] If behavior changes to backend 404 later, tests and docs are updated together.

---

## P2 — Status Documentation Cleanup

Goal: prevent future implementers from treating completed phases as still pending.

### Files to update

```text
.project/refactor/1-routes-grammar/3-phase-by-phase-implementation-plan.md
.project/refactor/1-routes-grammar/5-completion-gap-review-plan.md
```

Recommended approach:

1. Keep `3-phase-by-phase-implementation-plan.md` as historical implementation plan.
2. Add a short status pointer near the top:

```markdown
> Status note: issues 001-009 have since implemented most phases. See
> `5-completion-gap-review-plan.md` for remaining closure work.
```

3. Do not rewrite the old plan wholesale unless needed.

### Acceptance checklist

- [ ] Historical plan points to this completion review.
- [ ] Remaining work is tracked in one place.
- [ ] Completed work is not represented as current gap.

---

## 5. Final Remaining Checklist

```text
[ ] Add examples/actors route grammar parity tests
[ ] Ensure examples/actors imports n3tx_ui before models if HTML routes are expected
[ ] Add direct /ClassName/{id} auth parity tests
[ ] Add direct /ClassName/{id}?populate/depth tests
[ ] Add browser refresh test for #Product/{id}/@item
[ ] Add Veille/AgentActor smoke if migrated
[ ] Add browser/integration proof for standalone custom renderer imports
[ ] Document missing-id HTML shell behavior
[ ] Add status pointer from plan 3 to this completion review
```

---

## 6. Suggested Commit Slices

### Commit 1 — Actor example parity

```text
test(actors): Cover class-name route grammar in example app [wave]
```

Includes:

- `examples/actors` import-order fix if needed
- actor example class-name read tests
- actor example HTML route tests if expected

### Commit 2 — Direct parity tests

```text
test(core): Verify class-name read mirror parity [wave]
```

Includes:

- auth parity tests
- populate/depth parity tests
- optional examples/core route grammar tests

### Commit 3 — Browser smoke closure

```text
test(frontend): Extend route grammar browser smoke [wave]
```

Includes:

- named member refresh
- optional legacy refresh
- optional Veille smoke

### Commit 4 — Standalone shell proof and docs

```text
docs(ui): Document standalone view shell route behavior [wave]
```

Includes:

- custom renderer browser/integration proof if practical
- missing-id shell docs
- status pointer in historical plan
