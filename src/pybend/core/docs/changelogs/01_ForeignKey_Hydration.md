# FK Hydration — Implementation Report

## What Changed

Collection fields (e.g., `Product.comments`) now return **arrays of hrefs**
instead of embedded objects. Each href is a fully qualified URL that the
frontend can resolve independently.

**Before:**
```json
{
  "id": 1, "name": "Keyboard",
  "comments": [
    {"id": 1, "name": "Great!", "description": "Love it"},
    {"id": 2, "name": "OK", "description": "Decent"}
  ]
}
```

**After:**
```json
{
  "id": 1, "name": "Keyboard",
  "comments": [
    "http://localhost:5000/products/1/comments/1",
    "http://localhost:5000/products/1/comments/2"
  ]
}
```

Each href resolves via the existing nested routes:

```
GET /products/1/comments/1
→ { "id": 1, "name": "Great!", "description": "Love it", "user_owner": 1, "product_id": 1 }
```

---

## URL Format

```
{API_URL}/{parent_table}/{parent_id}/{field_name}/{child_id}
```

| Segment | Source | Example |
|---------|--------|---------|
| `API_URL` | `config.API_URL` (`http://localhost:5000`) | `http://localhost:5000` |
| `parent_table` | `Product.__tablename__` | `products` |
| `parent_id` | Record ID from parent query | `1` |
| `field_name` | Field name on the parent model | `comments` |
| `child_id` | `id` column from join table query | `3` |

No new routes were added — the hrefs match the nested routes already
registered by `routes_fastapi.py`.

---

## What the Frontend Needs to Handle

### 1. Collection fields are now string arrays

When a PTT pulls schema for `Product`, the `comments` property schema is:

```json
{
  "anyOf": [
    { "$ref": "#/$defs/Comment" },
    { "type": "string" }
  ]
}
```

And the actual data contains **strings** (hrefs), not objects:

```json
"comments": [
  "http://localhost:5000/products/1/comments/1",
  "http://localhost:5000/products/1/comments/2"
]
```

### 2. Each href is independently resolvable

Each comment href is a full URL. The frontend should resolve them the same way
it resolves any entity — via the NTT actor system:

```
Frontend receives Product with comment hrefs
  → For each href string in comments[]:
    → Create/resolve an NTT with that href
    → ATTACH → NTT fetches via GET {href}
    → DESCRIBE → renders comment card
```

### 3. The href carries its own origin

The full URL means the frontend doesn't need to know which backend hosts
the child entity. This enables future decentralization where child entities
could live on different backends.

---

## Backend Architecture (for context)

### `ListRef[T]` — New Pydantic type

`models/ref.py` introduces `ListRef[T]`, a type alias that tells Pydantic to
accept a list of either model instances or string hrefs:

```python
# Model declaration
comments: Optional[ListRef[Comment]] = []

# Expands to: Annotated[List[Union[Comment, str]], _ListRefMarker(Comment)]
```

A `_ListRefMarker` metadata tag on the `Annotated` type carries the model class,
allowing introspection code to detect ListRef fields and extract the referenced
model type via duck-typing (`hasattr(meta, 'model_type')`).

### `__fk_models__` — Join model cache on parent class

Each parent model now has a `__fk_models__` dict mapping field names to their
join model classes. Populated automatically by `generate_join_model()`:

```python
Product.__fk_models__ == {"comments": ProductComment}
```

This lets the storage layer resolve the correct table (`products_comments`)
instead of the base model table (`comments`, which doesn't exist).

### Hydration flow

```
GET /products
  → storage.list(Product)
  → get_list_fields(Product) → [("comments", Comment)]
  → Product.__fk_models__["comments"] → ProductComment
  → SELECT id FROM products_comments WHERE product_id = ?
  → Construct hrefs: http://localhost:5000/products/{parent_id}/comments/{id}
  → Product(comments=["http://...", "http://..."])
  → ListRef[Comment] accepts strings ✓
  → JSON response with href array
```

### Files changed

| File | Change |
|------|--------|
| `config.py` | Added `API_URL = f"http://localhost:{PORT}"` |
| `models/ref.py` | **New.** `_ListRefMarker` + `ListRef[T]` type alias |
| `models/product_model.py` | `comments: Optional[ListRef[Comment]]` (was `Optional[List[Comment]]`) |
| `models/proto_model.py` | Added `__fk_models__` ClassVar. `generate_join_model()` populates it |
| `utils/introspection.py` | Added `_unwrap_listref()` + `get_list_fields()` — storage-agnostic type introspection |
| `storage/sqlite_helpers.py` | Re-exports `get_list_fields` from introspection. `get_parent_fk_columns` delegates to it |
| `storage/sqlite_storage.py` | `list()` and `get()` hydrate via `__fk_models__`, `SELECT id` only, construct href strings |

---

## Future: Option B for ListRef

The current `ListRef` (Option A) uses a simple `Annotated[List[Union[T, str]]]`
approach. The JSON schema it produces is the default Pydantic `anyOf`.

A future Option B would implement `__get_pydantic_core_schema__` and
`__get_pydantic_json_schema__` directly on the `ListRef` class, producing a
cleaner schema:

```json
{ "type": "string", "format": "uri", "x-ref": "Comment" }
```

This would also allow adding a serialization hook that automatically converts
model instances to hrefs. Migrate to Option B when the frontend needs the
cleaner schema or when built-in serialization guarantees are needed.
