# First-Class JSON Field Support

**Date:** 2026-03-05
**Scope:** Promote dict/list JSON serialization from per-model boilerplate to a framework-level storage feature.
**Status:** Implemented

---

## 1. Problem

The agents module (AgentActor and SchedulerJob) has a 3-part boilerplate pattern for storing `dict`/`list` fields in SQLite:

1. `_JSON_FIELDS = ('constraints',)` module constant
2. `_storage_dict()` override to `json.dumps()` values before write
3. `@model_validator(mode='before')` to `json.loads()` string values on read
4. `update()` override to serialize before update

This same pattern would be needed by any model with dict/list fields. A developer declaring `constraints: dict = Field(default={})` should not need to write 30 lines of serialization boilerplate -- the framework should handle it.

---

## 2. Design

Handle JSON serialization in the **storage layer**, not the model layer. Four framework changes, then cleanup.

### What counts as a JSON field

A field whose type (after unwrapping `Optional`) is:
- `dict` / `Dict[str, Any]` / any dict variant
- `list` / `List[str]` / `List[int]` -- but **NOT** `ListRef[T]` or `List[BaseModel]` (those use FK join tables)

### Architecture touchpoints

**Write path:** `StorableMixin._storage_dict()` -> `SQLiteStorage.create()`/`update()` -> `_coerce_value(v)` per value. Adding dict/list handling to `_coerce_value()` covers ALL write paths with a single change.

**Read path:** `SQLiteStorage.get()`/`list()`/`_populate_fields()` build record dicts from raw SQL rows, then instantiate models via `model_class(**record)`. JSON TEXT strings must be deserialized before instantiation.

**Migration path:** `sqlite_migration.py` currently skips ALL list fields (`if origin_type is list: continue`). Must distinguish ListRef/List[BaseModel] (skip -- FK join table) from bare list/dict (TEXT column).

---

## 3. Implementation Plan

### Step 1: Add `get_json_fields()` to introspection

**File:** `src/pybend/core/utils/introspection.py`

Cached function returning field names that should be stored as JSON TEXT:

```python
@functools.lru_cache(maxsize=None)
def get_json_fields(model_class: Type[Any]) -> List[str]:
    results = []
    for field_name, field_info in model_class.model_fields.items():
        field_type = field_info.annotation
        origin = get_origin(field_type)
        # Unwrap Optional
        if origin is Union and type(None) in get_args(field_type):
            field_type = get_args(field_type)[0]
            origin = get_origin(field_type)
        # dict (any variant)
        if field_type is dict or origin is dict:
            results.append(field_name)
            continue
        # list -- only if NOT ListRef and NOT List[BaseModel]
        if field_type is list or origin is list:
            ref_model = _unwrap_listref(field_type, getattr(field_info, 'metadata', None))
            if ref_model is not None:
                continue
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                continue
            results.append(field_name)
    return results
```

### Step 2: Enhance `_coerce_value()` for serialization

**File:** `src/pybend/core/storage/sqlite_storage.py`

Add dict/list handling before the `str(v)` fallback:

```python
def _coerce_value(v):
    if isinstance(v, _SQLITE_NATIVE):
        return v
    import datetime
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    return str(v)
```

This covers both `create()` and `update()` paths automatically since both call `_coerce_value()`.

### Step 3: Add deserialization helper

**File:** `src/pybend/core/storage/sqlite_storage.py`

```python
def _deserialize_json_fields(model_class, record):
    for field_name in get_json_fields(model_class):
        val = record.get(field_name)
        if isinstance(val, str):
            try:
                record[field_name] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
```

Call in **4 read paths**:
- `get()` -- before `model_class(**data)` (~line 328)
- `list()` -- inside record loop, before appending (~line 203)
- `_populate_fields()` -- before `effective_cls(**rec)` (~line 469)
- `_populate_fields()` -- before `target_cls(**record)` (~line 543)

### Step 4: Fix migration for list/dict columns

**File:** `src/pybend/core/storage/sqlite_migration.py`

Import `_unwrap_listref` from introspection.

**`create_table()` -- replace the unconditional list skip:**

```python
# Before:
if origin_type is list:
    continue

# After:
if origin_type is list:
    ref_model = _unwrap_listref(field_type, getattr(field_info, 'metadata', None))
    if ref_model is not None:
        continue  # ListRef[T] -- FK join table
    args = get_args(field_type)
    if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
        continue  # List[BaseModel] -- FK join table
    columns.append(f"{field_name} TEXT")
    continue
```

**`migrate_table()` -- same distinction, plus correct defaults:**

Replace the unconditional list skip. Add explicit dict/list detection before the else fallback, with defaults `'{}'` and `'[]'` respectively.

### Step 5: Remove boilerplate from agents

**Files:**
- `src/pybend/core/agents/actor.py` -- Remove `_JSON_FIELDS`, `_deserialize_json_fields()`, `_storage_dict()`, `update()`
- `src/pybend/core/agents/scheduler.py` -- Remove same 4 pieces

Must be done in the same commit as framework changes to avoid double-serialization.

---

## 4. Edge Cases

| Case | Handling |
|------|----------|
| Nested dicts `{"a": {"b": 1}}` | `json.dumps()` handles recursively; `json.loads()` restores |
| `None` value for dict field | `_coerce_value(None)` returns None; NULL coercion restores field default |
| Empty string in DB for dict column | `json.loads("")` raises JSONDecodeError; caught by try/except |
| `datetime` inside dict | `json.dumps(v, default=str)` converts to ISO string |
| `Optional[dict]` | `get_json_fields()` unwraps Optional before checking |
| `List[str]` vs `ListRef[Comment]` | `get_json_fields()` checks `_unwrap_listref()` and `issubclass(BaseModel)` |
| Double-serialization risk | Agent boilerplate removed in same commit as framework change |
| Legacy data from `str(v)` | `try/except` on `json.loads()` prevents crashes |

---

## 5. Test Plan

### Unit tests for `get_json_fields()`
- `dict` detected, `Dict[str, Any]` detected, `Optional[dict]` detected
- `list` detected, `List[str]` detected, `List[int]` detected
- `ListRef[T]` NOT detected, `List[BaseModel]` NOT detected
- Model with no JSON fields returns empty list

### Integration test for round-trip
- Model with `tags: list`, `metadata: dict`, `scores: List[int]`
- Create, get, update, list -- verify Python types survive round-trip
- Verify migration creates TEXT columns for dict/list

### Existing tests must pass
- `cd /workspace/src/pybend/core && python3 -m pytest tests/unit/`
- `cd /workspace && python3 -m pytest example_grants/tests/`
- `cd /workspace && python3 -m pytest example_api/tests/`
- `cd /workspace && python3 -m pytest example_actor/tests/`

---

## 6. Key Files

| File | Change |
|------|--------|
| `src/pybend/core/utils/introspection.py` | Add `get_json_fields()` |
| `src/pybend/core/storage/sqlite_storage.py` | `_coerce_value()` + `_deserialize_json_fields()` + 4 call sites |
| `src/pybend/core/storage/sqlite_migration.py` | Fix list skip in `create_table()` + `migrate_table()` |
| `src/pybend/core/agents/actor.py` | Remove JSON boilerplate |
| `src/pybend/core/agents/scheduler.py` | Remove JSON boilerplate |

---

## 7. Developer Experience (After)

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True

    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    tags: list = Field(default=[])           # Just works
    metadata: dict = Field(default={})       # Just works
    scores: List[int] = Field(default=[])    # Just works
```

No `_JSON_FIELDS`, no `_storage_dict()`, no `@model_validator`, no `update()` override. The framework handles serialization and deserialization transparently in the storage layer.
