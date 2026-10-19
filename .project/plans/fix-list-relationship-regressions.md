# ✅ Fix Plan: `list[T]` Relationship Regression Hardening

## ✅ Recommendation

Ship this as a **stabilization patch in three thin slices** before merging the `list[T]` refactor:

1. **Make flat child identity the only frontend action-response URL shape**.
2. **Restore strict relationship validation** for inline `list[T]` payloads and hydration failures.
3. **Preserve caller serialization constraints** when overlaying hydrated relationship responses.

This keeps the architectural direction intact: **owned local collections are `list[T]` JSON id arrays on the parent**, children keep **flat class-name identity**, and nested routes/join models stay removed.

---

## 📍 Current State

The current diff removes join-model/nested-route behavior and stores owned collections as parent JSON arrays. That simplifies the model, but review reproduced these regressions:

| Priority | Area | Problem |
|---|---|---|
| P1 | Frontend identity | `NTT.js` still fabricates `/Parent/1/field/child` URLs after backend removed nested routes. |
| P1 | Validation | Invalid inline child dicts are swallowed and become empty collections. |
| P1 | Hydration | Any batch hydration exception erases the full relationship list. |
| P2 | Serialization | Nested `include`/`exclude` constraints are lost when children are replaced with `model_response()`. |

Validated signals:

```text
core unit:              1103 passed, 5 skipped
examples/core backend:   415 passed
examples/actors backend: 408 passed, 11 failed
frontend focused test:     6 passed, but asserts obsolete nested URL
diff check:             clean
browser e2e:            blocked by missing Playwright browser
```

---

## 🎯 Target State

```text
Model: Product.comments: list[Comment]
        |
        v
Storage: products.comments = [1, 2, 3]
        |
        v
API read: Product.comments = [{$id: /Comment/1, ...}, ...]
        |
        v
Frontend method response: action + _field + id -> /Comment/{id}
```

Key invariants:

- Flat identity only: child `$id` and frontend hrefs use `/{ChildClass}/{id}`.
- No silent validation loss: invalid inline child payloads raise validation errors.
- No false empty collections: hydration failures are observable errors, not empty arrays.
- Serialization kwargs are honored across relationship overlays.
- `list[T]` remains a normal parent-owned value updated through the existing model update path.

---

## 💻 Method Signature Surface

```text
n3tx_core.models.proto_model
  / def _hydrate_fk_list(target_cls: Type[PydanticBaseModel], values: Any) -> list

n3tx_core.models.proto_dump
  / def base(instance, **kwargs) -> dict
  / def _overlay_local_relationship_responses(instance, data: dict, seen: set, dump_kwargs: dict) -> None
  / def _relationship_response(value, seen: set, dump_kwargs: dict | None = None)
  + def _relationship_dump_kwargs_for_field(dump_kwargs: dict, field_name: str, index: int | None = None) -> dict

Frontend DynamicClass instance response handler
  / DynamicClass.prototype._response_ = function(data, tx)
```

---

## 🧩 Implementation Slices

### Slice 1 — Frontend flat child hrefs

📍 Files:

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `tests/frontend/tests/integration/method-response-pull.test.js`
- Relevant frontend/E2E fixtures that still assert nested URLs

Change action response handling from parent-scoped URL construction to schema-derived child class identity.

💻 Current bug:

```javascript
const childHref = `${this.href}/${field}/${data.id}`;
```

💻 Target shape:

```javascript
const props = DynamicClass._schema?.properties?.[field];
const childModel = props ? resolveModelName(props) : null;
if (!childModel) return this.pull();
const ChildDC = childModel ? NTT.get(childModel) : null;
const childHref = `${API_URL}/${childModel}/${data.id}`;

if (ChildDC) registerInstance(ChildDC, { ...data, $id: childHref, $schema: `${API_URL}/${childModel}` });
```

Prefer using the existing runtime URL source rather than hardcoding `API_URL` if `NTT.js` already has a helper/config value nearby.

🧪 Tests:

- Update focused integration test expectation from `/Product/1/favorites/99` to `/Like/99`.
- Add a test that action responses register the child under `NTT.get('Like').children` with flat `$id`.
- Add a regression that generated href path is resolvable by backend route grammar (`/Like/{id}`), not nested route grammar.

---

### Slice 2 — Strict relationship hydration validation

📍 Files:

- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_model.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py`

Replace broad exception swallowing with explicit behavior:

- Inline child dict without `id`/`$id`: construct `target_cls(**value)` and let validation errors propagate.
- Batch fetch by ids: if storage raises, log hydration context and re-raise the original exception unchanged.
- Missing ids: still skip or preserve current documented behavior if intentional; tests currently expect missing child ids to be skipped.

💻 Code shape:

```python
for value in values:
    if isinstance(value, dict) and 'id' not in value and '$id' not in value:
        hydrated.append(target_cls(**value))  # no blanket except

if ids:
    try:
        fetched = target_cls.list(ids=ids)
    except Exception:
        logger.exception(
            "Failed to hydrate %s relationship ids=%s",
            target_cls.__name__,
            ids,
        )
        raise
```

🧪 Tests:

- `Parent(children=[{}])` raises a Pydantic validation error when `Child.required` is missing.
- A mocked `Child.list()` failure preserves the original exception type and traceback.
- The hydration failure is logged with the child model name and requested ids.
- Existing missing-id behavior remains explicit: `[valid_id, 9999]` returns only valid children if that is the desired contract.

---

### Slice 3 — Preserve nested serialization kwargs

📍 Files:

- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py`

When `base()` overlays local relationship values with `model_response()`, propagate field-specific `include`/`exclude` constraints.

💻 Target shape:

```python
def _overlay_local_relationship_responses(instance, data, seen, dump_kwargs):
    ...
    child_kwargs = _relationship_dump_kwargs_for_field(dump_kwargs, field_name)
    data[field_name] = _relationship_response(value, seen, child_kwargs)

def _relationship_response(value, seen, dump_kwargs=None):
    ...
    return value.model_response(_seen=seen, **(dump_kwargs or {}))
```

Support at minimum:

- `exclude={'children': {'__all__': {'secret'}}}`
- `include={'children': {'__all__': {'name'}}}`
- single relationship field excludes such as `exclude={'child': {'secret'}}`

🧪 Tests:

- `parent.model_response(exclude={...})` does not reintroduce child `secret`.
- `parent.model_response(include={...})` limits child fields as requested while still preserving `$schema`/`$id` unless explicitly excluded.
- Cycle fallback path still returns identity metadata without recursion.

---

## 📦 `list[T]` Update Contract

Keep updates straightforward and use the existing full-field replacement path:

```python
# Append
favorites = [*self.favorites, saved]
self.update({'favorites': favorites})

# Remove
favorites = [favorite for favorite in self.favorites if favorite.id != deleted_id]
self.update({'favorites': favorites})
```

This matches the ownership model: the parent owns one ordered JSON value and an update replaces that value in one SQL statement. Concurrent read-modify-write operations remain last-write-wins. That is an accepted constraint for this pass.

If concurrent collection mutation becomes a concrete requirement, solve it once through generic optimistic concurrency/versioned model updates rather than adding field-specific append/remove storage methods.

---

## 🧪 Verification Plan

Run in this order:

```bash
cd /workspace && .venv-agents/bin/python -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/ -q
cd /workspace/examples/core && /workspace/.venv-agents/bin/python -m pytest tests/ --ignore=tests/e2e -q
cd /workspace/examples/actors && /workspace/.venv-agents/bin/python -m pytest tests/ --ignore=tests/e2e -q
cd /workspace/tests/frontend && npx vitest run tests/integration/method-response-pull.test.js
cd /workspace/tests/frontend && npx vitest run
cd /workspace && git diff --check -- packages/n3tx-core examples/core examples/actors tests/frontend
```

If Playwright browsers are available later:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js
```

Expected post-fix state:

| Suite | Expected |
|---|---|
| Core unit | Pass |
| Core example backend | Pass |
| Actor example backend | Pass or only intentional auth status expectation updates remain |
| Frontend vitest | Pass with flat child href expectations |
| Diff check | Clean |

---

## ⚠️ Risks and Decisions

| Decision | Recommendation | Why |
|---|---|---|
| Missing child ids in JSON arrays | Continue skipping, but document/test | Existing test expects skip; raising would be stricter but may break stale refs. |
| Hydration storage errors | Raise | Empty list is false data. |
| Frontend action URL fallback | Temporary fallback acceptable | But schema-derived flat URL should be primary path. |
| List update concurrency | Accept last-write-wins | Keep the API simple; add generic optimistic concurrency only when required. |
| Legacy FK migration | Out of scope | This migration does not preserve the legacy FK representation. |

---

## ✨ Execution Order

1. Strict hydration + tests.
2. Serialization kwargs propagation + tests.
3. Frontend flat href fix + vitest updates.
4. Actor/core example expectation cleanup.
5. Docs updates for strict hydration and flat identity contracts.

This order fixes false-data behavior first, then aligns frontend/runtime contracts.

---

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`
- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`

## Saved Plan

- `.project/plans/fix-list-relationship-regressions.md`
