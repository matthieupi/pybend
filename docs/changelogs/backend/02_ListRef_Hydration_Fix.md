# ListRef Hydration Fix — Pydantic v2 Metadata Compatibility

> **Status:** Complete.
> **Scope:** Fixed `get_list_fields()` failing to detect `ListRef[T]` fields due to Pydantic v2's metadata separation.

---

## What Broke

Collection fields (e.g., `Product.comments: ListRef[Comment]`) returned **empty arrays** in API responses despite the database containing data.

```json
{
  "id": 1, "name": "Wireless Headphones",
  "comments": []
}
```

Should have been:

```json
{
  "id": 1, "name": "Wireless Headphones",
  "comments": [
    "http://localhost:5000/products/1/comments/1",
    "http://localhost:5000/products/1/comments/2"
  ]
}
```

---

## Root Cause

`ListRef[Comment]` produces `Annotated[List[Union[Comment, str]], _ListRefMarker(Comment)]`.

Pydantic v2 separates the `Annotated` metadata when building `FieldInfo`:
- **`field_info.annotation`** becomes `List[Union[Comment, str]]` (no `__metadata__`)
- **`field_info.metadata`** contains `[_ListRefMarker(Comment)]`

The `_unwrap_listref()` function only checked `field_type.__metadata__` (the annotation), which is now empty. It never found the `_ListRefMarker`, so `get_list_fields()` returned `[]`, and the SQL hydration query was never executed.

---

## Fix

**File:** `utils/introspection.py`

`_unwrap_listref()` now accepts an optional `field_metadata` parameter and checks both sources:

```python
def _unwrap_listref(field_type, field_metadata=None):
    # Check type-level Annotated metadata
    if hasattr(field_type, '__metadata__'):
        for meta in field_type.__metadata__:
            if hasattr(meta, 'model_type'):
                return meta.model_type
    # Check Pydantic FieldInfo.metadata (Pydantic v2 separates Annotated metadata here)
    if field_metadata:
        for meta in field_metadata:
            if hasattr(meta, 'model_type'):
                return meta.model_type
    return None
```

`get_list_fields()` passes `field_info.metadata` to the updated function:

```python
ref_model = _unwrap_listref(field_type, getattr(field_info, 'metadata', None))
```

---

## Verification

```python
>>> from models.product_model import Product
>>> from utils.introspection import get_list_fields
>>> get_list_fields(Product)
[('comments', <class 'models.comment_model.Comment'>)]
```

```bash
curl http://localhost:5000/products | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data[0]['comments'][:2])
"
# ['http://localhost:5000/products/1/comments/1', 'http://localhost:5000/products/1/comments/2']
```

---

## Files Changed

| File | Change |
|------|--------|
| `utils/introspection.py` | `_unwrap_listref()` signature + dual metadata check, `get_list_fields()` passes `field_info.metadata` |
