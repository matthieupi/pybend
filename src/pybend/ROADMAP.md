# PyBend v0.8.0 Roadmap

> Generated from deep-dive codebase analysis on 2026-02-22.
> Current state: v0.7.0 on branch `v0.7.0`.

---

## Quick Wins (Tighten What Exists)

### 1. Fix `user_owner = 1` hardcoding in Product.comment()

**Problem:** `product_model.py:61` hardcodes `comment.user_owner = 1` instead of using the authenticated user.

**Root cause:** `make_custom_post()` in `routes_fastapi.py` extracts the user via `_get_user(request)` for access checks but never passes it to the model method. The method signature `comment(self, comment: Comment)` has no way to receive user context.

**Fix (2 files):**
- `routes_fastapi.py`: In `make_custom_post()`, detect if the method type-hints a `user` parameter; if so, inject `_get_user(request)` as a kwarg before calling `attr(instance, **parsed_args)`
- `product_model.py`: Change signature to `comment(self, comment: Comment, user: dict = None)` and set `comment.user_owner = user['user_id']`
- Same pattern applies to `Comment.like()`

**Effort:** ~1 hour | **Difficulty:** Low

---

### 2. Pagination on List Endpoints

**Problem:** `StorableMixin.list()` -> `SQLiteStorage.list()` -> `SELECT * FROM table` with no LIMIT/OFFSET. All records returned always.

**Current state:** Zero pagination anywhere in the stack. Frontend `ListElement.definedCallback()` calls `proto.call('READ', {})` with no page args. `NetworkAdapter` sends READ as bare `HTTP.get(target)`.

**Implementation layers:**

| Layer | File | Change |
|-------|------|--------|
| SQL | `sqlite_storage.py` | Add `LIMIT ? OFFSET ?`, return `{data, meta: {total, limit, offset, has_more}}` |
| Mixin | `storable_mixin.py` | Add `limit`/`offset` params to `list()` |
| Route | `routes_fastapi.py` | Add `limit: int = 20, offset: int = 0` query params to `make_get_all_instances()` |
| Transport | `NetworkAdapter.js` | Encode `tx.data` as query params for READ |
| List | `ListElement.js` | Store pagination meta, add "Load More" button |
| DynamicClass | `NTT.js` | Handle new `{data: [], meta: {}}` response shape in `READ()` |

**Key design decision:** Response format changes from flat array to `{data: [], meta: {}}`. `DynamicClass.READ()` must detect the new shape.

**UI pattern:** "Load More" button (simpler, fits card grid). Infinite scroll is a future enhancement.

**Effort:** ~5 hours | **Difficulty:** Medium

---

### 3. DELETE Action in Frontend UI

**Problem:** Backend DELETE is 100% implemented (route, auth, handler). Frontend has transport (`NetworkAdapter` routes DELETE -> `HTTP.remove()`), permissions (`canAction(schema.access, 'delete')`), and config (`E.delete`). Only the UI button is missing.

**Implementation (3 files):**
- `ntt-item.js`: Add trash icon button in `md()` next to edit button, gated by `permissions.canAction(schema.access, 'delete')`. Add click handler -> `confirm()` -> send `TX { name: 'DELETE', target: this.value.$id }`
- `ntt-item.css`: Add `.delete-btn` styles (trash icon, red hover)
- `ListElement.js` or `DynamicClass`: Post-delete cleanup — remove from `instances` Map, re-notify watchers

**Effort:** ~2 hours | **Difficulty:** Low

---

## Framework Capabilities (Expand What the Schema Can Drive)

### 4. `display_modes` per Breakpoint in `__ui__`

**Problem:** `ntt-item.js` uses hardcoded heuristics for field selection per size. `xs()` shows name only, `sm()` picks first 3 fields via `#topFields(3)`, `md()` shows full form, `lg()`/`xl()` just delegate to `md()`. No schema control.

**Proposed schema format:**
```python
__ui__ = {
    'field_order': ['name', 'price', 'description'],
    'display_modes': {
        'xs': [],                    # pill shows name only (implicit)
        'sm': ['name', 'price'],     # compact row
        'md': '*',                   # all fields
        'lg': '*',                   # future: + metadata
        'xl': '*',                   # future: + embedded children
    }
}
```

**Implementation (4 files):**
- `proto_model.py`: Serialize `display_modes` into JSON Schema under `ui.display_modes`
- `product_model.py`: Add `display_modes` to `__ui__`
- `ntt-item.js`: Replace `#topFields()` heuristic with `schema.ui.display_modes[size]` lookup, fall back to current heuristic if absent
- `form.js`: `getForm()` accepts optional field filter list

**Effort:** ~4 hours | **Difficulty:** Low-Medium

---

### 5. Search/Filter API + UI

**Problem:** No query parameter support for filtering on list endpoints. However, ABAC already demonstrates SQL WHERE clause generation — the `sql_filter` parameter on `StorableMixin.list()` already exists.

**Implementation:**

| Layer | File | Change |
|-------|------|--------|
| Route | `routes_fastapi.py` | Add `q` (text search) and `{field}={value}` query params to `make_get_all_instances()` |
| SQL | `sqlite_storage.py` | Build WHERE clauses from query params, compose with ABAC filter via AND |
| Schema | `proto_model.py` | Optional `ui.searchable: true` per field, or default to string fields |
| List UI | `ntt-list.js` | Add search bar in list header |
| List logic | `ListElement.js` | Debounced input -> re-send READ with query params |
| Transport | `NetworkAdapter.js` | Encode query params into GET URL |

**Effort:** ~5 hours | **Difficulty:** Medium

---

### 6. File/Image Upload Flow

**Problem:** Image fields are plain URL strings defaulting to placeholder services. No upload endpoint, no multipart handling, no local file storage.

**Implementation:**
- **Backend:** Add `POST /upload` endpoint accepting `UploadFile`, save to `static/uploads/`, return URL
- **Schema signal:** `json_schema_extra={'ui': {'widget': 'image-upload'}}` on image fields
- **Frontend:** `form.js` adds `image-upload` widget case — file input + preview in edit mode, `<img>` in display mode. On file select: POST to `/upload`, get URL, set field value
- **Storage:** Local filesystem under `static/uploads/` (served by existing `StaticFiles` mount in `backend.py`)

**Files:** `routes_fastapi.py` (new route), `backend.py` (ensure uploads dir served), `form.js` (new widget), `product_model.py` + `user_model.py` (add widget hint)

**Effort:** ~5 hours | **Difficulty:** Medium

---

## Developer Experience

### 7. Expand Automated Test Suite

**Current state:** Tests exist at `src/pybend/core/tests/` — `test_models.py`, `test_storage.py`, `test_api.py` with `conftest.py` (temp DB isolation via `monkeypatch`). Coverage is thin.

**Missing coverage (priority order):**
1. FastAPI routes with JWT auth (TestClient + token)
2. Custom method routes (`@expose_route` handlers)
3. Join model CRUD (nested routes `/products/{id}/comments/...`)
4. Schema generation (`ProtoModel.schema()` produces valid JSON Schema)
5. Authorization filtering (ABAC SQL WHERE clause generation)
6. Migration system (auto-add/remove columns)

**Frontend tests (Playwright):**
- matrix.html loads and shows product list
- Click product -> detail view navigation
- Back button works
- Edit toggle + save
- Login/logout flow

**Effort:** ~7 hours | **Difficulty:** Medium

---

### 8. Multi-Model Matrix Layout / Model Selector

**Problem:** `matrix.html` hardcodes `<ntt-list model="Product">`. No endpoint to discover models. No selector UI.

**Implementation:**
- **Backend:** Add `GET /models` endpoint returning model metadata from `registered_models`
- **Frontend:** Add model selector (sidebar, tabs, or dropdown) that fetches `/models` on load
- **Navigation:** Click model -> Router NAVIGATE -> ntt-router mounts `<ntt-list model="ModelName">`
- Multiple `<ntt-list>` instances can coexist safely (independent Matrix registration)

**Files:** `routes_fastapi.py` (1 new route), `matrix.html` (layout refactor), `ntt-topbar.js` or new `ntt-model-selector.js`

**Effort:** ~4 hours | **Difficulty:** Low-Medium

---

### 9. Clean Up Debug Console Output

**Current state:** Very noisy. ~79 `console.*` calls across 17 JS files, ~63 `print()` calls across 12 Python files. `Logging.js` utility exists with level-gated methods but most code bypasses it.

**Noisiest files:**
- `HTTP.js`: 16+ status/debug logs
- `Actor.js`: 9 debug/warn calls
- `NTT.js`: 8 calls (mixed debug/error)
- `routes_fastapi.py`: 12 request-tracing prints

**Cleanup approach:**
- **Frontend:** Replace bare `console.log` with `Logging.debug()`, remove purely temporary dumps (`console.log(this.children)`, `console.log("ATTACHING")`), keep `console.error` for genuine errors
- **Backend:** Remove debug `print()` from `routes_fastapi.py`, `sqlite_storage.py`, `storable_mixin.py`, `product_model.py`. Keep migration/seed/CLI prints. Optionally add Python `logging` module
- **Config:** Add production mode (`config.LOGGING = 1` silences debug)

**Effort:** ~3 hours | **Difficulty:** Low (mechanical)

---

## Summary

| # | Area | Effort | Difficulty | Backend Ready? | Frontend Ready? |
|---|------|--------|-----------|----------------|-----------------|
| 1 | Fix user_owner | ~1h | Low | Route needs user injection | N/A |
| 2 | Pagination | ~5h | Medium | Needs SQL + response format | Needs scroll UI |
| 3 | DELETE UI | ~2h | Low | **100% done** | Needs button + handler |
| 4 | display_modes | ~4h | Low-Med | Schema extension | Size methods read config |
| 5 | Search/Filter | ~5h | Medium | sql_filter exists, needs wiring | Needs search bar |
| 6 | Image upload | ~5h | Medium | New endpoint needed | New widget type |
| 7 | Test suite | ~7h | Medium | Foundation exists, thin coverage | Zero frontend tests |
| 8 | Multi-model | ~4h | Low-Med | Need /models endpoint | Need selector UI |
| 9 | Debug cleanup | ~3h | Low | ~63 prints | ~79 console.* |

**Suggested execution order (quickest wins first):**
1. DELETE UI (#3) — all backend done, just wire the button
2. Fix user_owner (#1) — 1-hour bug fix
3. Debug cleanup (#9) — mechanical, immediate polish
4. Multi-model (#8) — showcases framework generality
5. display_modes (#4) — schema power, isolated change
6. Pagination (#2) — response contract change, coordinate both sides
7. Search/Filter (#5) — builds on pagination
8. Image upload (#6) — new capability
9. Test suite (#7) — ongoing, highest long-term value
