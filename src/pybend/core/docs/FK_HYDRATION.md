# FK Hydration — Approach & Design

## The Problem

When `GET /products` returns, the `comments` array is always empty.

### Root Cause

`Product` declares `comments: Optional[List[Comment]]`. The hydration code in
`sqlite_storage.py` resolves the child table via `Comment.__tablename__` →
`"comments"`. But that table doesn't exist.

The actual data lives in the **join table** `products_comments`, created by:

```python
register_model(generate_join_model(Product, Comment), storage=storage_backend)
```

`generate_join_model()` produces `ProductComment` with:
- `__tablename__ = "products_comments"`
- `__owner__ = Product`
- All `Comment` fields + `product_id` FK

The hydration queries `SELECT * FROM comments WHERE product_id = ?` →
`OperationalError` → caught silently → `[]`.

---

## Design Decisions

### 1. Return hrefs, not embedded objects

Collection fields return **arrays of hrefs** — fully qualified URLs pointing
at each child entity. The frontend resolves them independently via the NTT
actor system.

**Before** (embedded objects):
```json
{
  "id": 1, "name": "Keyboard",
  "comments": [
    {"id": 1, "name": "Great!", "description": "Love it"},
    {"id": 2, "name": "OK", "description": "Decent"}
  ]
}
```

**After** (href references):
```json
{
  "id": 1, "name": "Keyboard",
  "comments": [
    "http://mybackend:5000/products/1/comments/1",
    "http://mybackend:5000/products/1/comments/2"
  ]
}
```

**Why hrefs?**
- Aligns with the NTT actor model — every entity is independently addressable
- Enables **decentralization** — Frontend A can load data that spans Backend B
  and Backend C, each href carries its own origin
- Less data per response — parent endpoints stay lightweight
- Frontend already knows how to resolve addresses (ATTACH → DESCRIBE)

### 2. Nested URL format: `/{parent_table}/{parent_id}/{field_name}/{id}`

We keep the existing nested REST routes — no route changes needed:

| Option | Example | Verdict |
|--------|---------|---------|
| **a) Nested** | `/products/1/comments/3` | **Chosen** — matches existing routes, no changes needed |
| b) Hybrid | `/products/comments/3` | Ambiguous, no matching route |
| c) Flat | `/products_comments/3` | Independent but requires new routes — can migrate later |

Nested addressing means:
- Hrefs match routes already registered by `routes_fastapi.py`
- No route changes needed — existing `GET /{parent_table}/{parent_id}/{field_name}/{id}` works
- Parent context is available during hydration (we're iterating over parent records)
- The **field name** on the parent (e.g., `"comments"`) is used as the URL segment —
  no `__tagname__` attribute needed, the field name is already available during hydration
- URL construction: `{API_URL}/{parent_table}/{parent_id}/{field_name}/{child_id}`

**Future:** can migrate to flat addressing later if decentralization requires it.

### 3. Base URL from config

The href prefix comes from `config.API_URL` — constructed from the existing
`HOST` and `PORT` values in `config.py`:

```python
# config.py
HOST = "0.0.0.0"
PORT = 5000
API_URL = f"http://localhost:{PORT}"
```

Simple, explicit, works for the current single-backend setup. Can be extended
later for multi-backend/proxy scenarios.

### 4. Custom Pydantic type: `ListRef[Comment]`

The model currently declares `comments: Optional[List[Comment]]`. Returning
strings would break Pydantic validation. We introduce a `ListRef[T]` type that:
- Accepts both a model instance and a string href
- **Serializes to a string href** in JSON responses
- Preserves schema information (the `T` parameter tells the frontend what
  type lives at that href)

```python
class Product(ProtoModel):
    comments: Optional[List[ListRef[Comment]]] = []
```

Serialization: `ListRef[Comment]` → `"http://host/products/1/comments/3"`

#### Approach: Type alias factory (Option A)

`ListRef` uses `Annotated[Union[T, str]]` — Pydantic validates natively (tries `T`
first, falls back to `str`). A `_ListRefMarker` metadata tag lets schema generation
detect ListRef fields and customize the JSON schema output.

```python
from typing import Annotated, Union

class _ListRefMarker:
    """Metadata tag to identify ListRef fields during schema generation."""
    def __init__(self, model_type):
        self.model_type = model_type

class ListRef:
    def __class_getitem__(cls, model_type):
        return Annotated[Union[model_type, str], _ListRefMarker(model_type)]
```

Default JSON schema: `{"anyOf": [{"$ref": "#/$defs/Comment"}, {"type": "string"}]}`

#### Future: Self-contained Pydantic type (Option B) — *not implemented in this pass*

Option B replaces the type alias with a class that implements Pydantic's two
hooks directly: `__get_pydantic_core_schema__` (validation + serialization) and
`__get_pydantic_json_schema__` (JSON schema output). Everything lives in one
place — no external schema customization needed.

```python
from typing import Any
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import CoreSchema, core_schema
from pydantic.json_schema import JsonSchemaValue

class ListRef:
    def __class_getitem__(cls, model_type):

        class _ListRefType:
            __ref_model__ = model_type

            @classmethod
            def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
                model_schema = handler.generate_schema(model_type)
                str_schema = core_schema.str_schema()
                return core_schema.union_schema([model_schema, str_schema])

            @classmethod
            def __get_pydantic_json_schema__(cls, _schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
                return {
                    "type": "string",
                    "format": "uri",
                    "x-ref": model_type.__name__,
                }

        _ListRefType.__name__ = f"ListRef[{model_type.__name__}]"
        return _ListRefType
```

| Aspect | Option A (current) | Option B (future) |
|--------|-------------------|-------------------|
| **Validation** | `Union[T, str]` via Pydantic | `union_schema([T, str])` via core_schema — same behavior |
| **JSON Schema** | Default `anyOf` — needs external override | Inline: `{"type": "string", "format": "uri", "x-ref": "Comment"}` |
| **Schema logic lives in** | Scattered (ProtoModel / GenerateJsonSchema) | Self-contained in `ListRef` |
| **Serialization hook** | None — relies on storage providing strings | Can add `serialization=` to force href output |
| **Complexity** | ~10 lines + schema fix elsewhere | ~25 lines, all in one place |
| **Pydantic API surface** | Standard `Annotated`/`Union` | Requires `pydantic_core.core_schema` API |

**When to migrate:** when we need the frontend to receive a clean
`{"type": "string", "format": "uri", "x-ref": "Comment"}` schema instead
of the default `anyOf`, or when we want built-in serialization guarantees.

---

## Implementation

### 1. Cache join models on the parent class

Add `__fk_models__` to `ProtoModel`:

```python
class ProtoModel(BaseModel, StorableMixin, ViewableMixin):
    __fk_models__: ClassVar[Dict[str, Type]] = {}
```

Maps **field names** to their **join model classes**:

```python
Product.__fk_models__ == {"comments": ProductComment}
```

### 2. Populate during `generate_join_model()`

After creating the join class, scan the owner for the matching `List[ref_model]`
field and register it:

```python
def generate_join_model(owner_cls, ref_model, field_name=None):
    ...
    join_model = type(class_name, (ref_model,), fields)

    # Resolve field_name if not provided
    if not field_name:
        for fname, child_cls in get_list_fields(owner_cls):
            if child_cls is ref_model:
                field_name = fname
                break

    # Cache on the parent class
    if field_name:
        owner_cls.__fk_models__[field_name] = join_model

    return join_model
```

### 3. Hydrate as hrefs in storage

In `sqlite_storage.py` `list()` and `get()`:

```python
import config

for field_name, child_class in list_fields:
    # Resolve join table via parent's cached FK models
    effective_cls = model_class.__fk_models__.get(field_name, child_class)
    child_table = effective_cls.__tablename__
    fk_col = f"{model_class.__name__.lower()}_id"

    cursor.execute(
        f"SELECT id FROM {child_table} WHERE {fk_col} = ?",
        (parent_id,)
    )
    child_rows = cursor.fetchall()
    record[field_name] = [
        f"{config.API_URL}/{model_class.__tablename__}/{parent_id}/{field_name}/{row[0]}"
        for row in child_rows
    ]
```

Note: we only `SELECT id` now — we don't need the full row, just enough
to construct the href. The **field name** (e.g., `"comments"`) is used as the
URL segment — no `__tagname__` needed. The nested URL matches the existing route:
`GET /{parent_table}/{parent_id}/{field_name}/{id}`

### 4. No route changes needed

The existing nested routes already support the href format we generate.
No new routes required. Can add flat routes later if needed.

---

## Why `__fk_models__` on the class?

| Concern | Global `join_models` dict | `__fk_models__` on class |
|---------|--------------------------|--------------------------|
| **Self-describing** | No — external registry | Yes — model knows its own relationships |
| **Lookup key** | `(ParentName, ChildName)` tuple | Field name (more precise) |
| **Import needed** | `from utils.registrar import join_models` | None — already have `model_class` |
| **Multiple fields of same type** | Ambiguous (same key) | Distinct (different field names) |
| **Populated when** | `register_model()` | `generate_join_model()` |

---

## Files to Change

1. **`models/proto_model.py`**
   - Add `__fk_models__: ClassVar[Dict[str, Type]] = {}` to `ProtoModel`
   - In `generate_join_model()`: resolve field name, populate `owner_cls.__fk_models__`

2. **`storage/sqlite_storage.py`**
   - In `list()` and `get()`: resolve table via `model_class.__fk_models__`,
     `SELECT id` only, construct nested hrefs with `config.API_URL`

3. **`storage/sqlite_helpers.py`**
   - Update `get_list_fields()` to unwrap `ListRef[T]` → extract `T` (the model class).
     Uses `_ListRefMarker` from the `Annotated` metadata to detect ListRef fields.

4. **`config.py`**
   - Add `API_URL = f"http://localhost:{PORT}"`

5. **new `models/ref.py`**
   - Implement `ListRef[T]` as `Annotated[Union[T, str], _ListRefMarker(T)]` (Option A)

6. **`models/product_model.py`**
   - Change `comments: Optional[List[Comment]]` → `Optional[List[ListRef[Comment]]]`

---

## Data Flow After Fix

```
GET /products
  → storage.list(Product)
  → get_list_fields(Product) → [("comments", Comment)]
  → Product.__fk_models__["comments"] → ProductComment
  → SELECT id FROM products_comments WHERE product_id = ?
  → Construct hrefs: http://localhost:5000/products/{parent_id}/comments/{id}
  → Product(comments=["http://.../products/1/comments/1", "http://.../products/1/comments/2"])
  → ListRef[Comment] accepts strings ✓ → JSON response with href array

Frontend receives product with comment hrefs
  → PTT creates NTT instances with href addresses
  → Each <ntt-item ref="ProductComment/1"> independently ATTACHes
  → NTT fetches via GET /products/1/comments/1 (existing nested route)
  → DESCRIBE → Item renders comment card
```
