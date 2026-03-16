# Storage Layer

> Part of [n3tx-core](../README.md)

## What This Covers

The storage abstraction, SQLite backend internals, JSON field serialization, FK hydration, eager loading (populate), and migration system. Does not cover the authorize package's SQL pushdown (see [authorization.md](authorization.md)).

## Architecture

```
StorableMixin (injected into ProtoModel when __storable__=True)
  |
  +-- create(data) / get(id) / list(...) / update(id, data) / delete(id)
  |
  v
AbstractStorage (interface)
  |
  +-- SQLiteStorage   -- Production: connection pool, WAL mode, migrations
  +-- JSONStorage     -- Development: simple JSON file per model
```

`StorableMixin` delegates all operations to `cls.storage`, which is set via `register_model(Model, storage=backend)`. The mixin is injected into the class hierarchy by `ProtoModel.__init_subclass__` when `__storable__ = True`.

### SQLiteStorage Internals

```
SQLiteStorage(database='app.db', pool_size=4)
  |
  +-- _pool (queue.Queue)       -- Connection pool
  +-- _migration (SQLiteMigration)  -- Schema management
  +-- _connection() context mgr -- Pool-managed connections
```

WAL mode enabled on first connection. `busy_timeout=5000` prevents lock errors under concurrent writes. `check_same_thread=False` for FastAPI thread dispatch.

## Interface

### AbstractStorage

```python
class AbstractStorage(ABC):
    def create_table(self, model_class: Type) -> None: ...
    def create(self, model_class: Type, data: dict) -> Any: ...
    def list(self, model_class: Type, sql_filter=None, limit=None, offset=None,
             populate=None, ids=None) -> list | dict: ...
    def get(self, model_class: Type, id_: int, as_dict=False, populate=None) -> Any: ...
    def update(self, model_class: Type, id_: int, data: dict) -> None: ...
    def delete(self, model_class: Type, id_: int) -> None: ...
```

### StorableMixin CRUD

```python
# Create
product = Product(name='Widget', price=9.99)
created = Product.create(product)  # Returns model instance with id set

# Read
product = Product.get(1)                          # Model instance
product = Product.get(1, as_dict=True)             # Plain dict
product = Product.get(1, populate=pop_spec)        # With eager loading

# List
products = Product.list()                          # All records (list)
products = Product.list(limit=20, offset=0)        # Paginated (dict with data/meta)
products = Product.list(sql_filter=('price > ?', [10]))  # Filtered
products = Product.list(ids=[1, 2, 3])             # By ID set

# Update
updated = Product.update(1, {'price': 19.99})      # Returns updated instance
updated = Product.update(1, product_instance)       # Accepts model or dict

# Delete
Product.delete(1)

# Save (create or update based on id)
product.save()
```

### Pagination Response Shape

When `limit` is provided, `list()` returns a dict instead of a list:

```python
{
    'data': [<model instances>],
    'meta': {
        'total': 100,    # Total matching rows (before pagination)
        'limit': 20,
        'offset': 0,
        'has_more': True
    }
}
```

### JSON Field Handling

`dict` and `list` fields are transparently serialized to JSON TEXT columns. No model-level boilerplate needed.

```python
class Config(ProtoModel):
    __tablename__ = 'configs'
    __storable__ = True
    tags: list = Field(default=[])           # TEXT column, json.dumps/loads
    metadata: dict = Field(default={})       # TEXT column, json.dumps/loads
    scores: List[int] = Field(default=[])    # TEXT column, json.dumps/loads
    comments: ListRef[Comment] = Field(default=[])  # FK join table (NOT JSON)
```

Detection: `get_json_fields(model_class)` in `introspection.py` returns fields for JSON treatment. It matches `dict`, `Dict[str, Any]`, `list`, `List[str]`, `List[int]` but excludes `ListRef[T]` and `List[BaseModel]`.

Write path: `_coerce_value()` calls `json.dumps(v, default=str)` for dict/list values.
Read path: `_deserialize_json_fields()` calls `json.loads()` on string values before model instantiation.

### FK Hydration

`Ref[T]` fields are stored as plain integers but serialized as href URLs in API responses:

```python
# Stored in DB: user_owner = 3
# Returned by get()/list(): user_owner = "http://localhost:5000/users/3"
```

`ListRef[T]` fields are stored in join tables and serialized as href arrays:

```python
# Returned: comments = ["http://localhost:5000/products/1/comments/5", ...]
```

### Eager Loading (Populate)

The `populate` parameter controls eager loading of related entities via `PopulateSpec`:

```python
from n3tx_core.utils.populate import parse_populate

# Field-specific: load comments
spec = parse_populate("comments", None)

# Depth-based: load all relations 1 level deep
spec = parse_populate(None, 1)

# Nested: load comments and their likes
spec = parse_populate("comments.likes", None)

# Combined: multiple fields
spec = parse_populate("comments,tags", None)
```

Populated data is attached to `instance.__dict__['_populated']` and merged into the response by the dump pipeline's `populate` stage.

## Gotchas

- **`list()` return type changes with pagination.** Without `limit`, returns `list[Model]`. With `limit`, returns `dict` with `data` and `meta` keys. Always check `isinstance(result, dict)` if the caller might pass optional pagination.
- **SQLite `:memory:` with separate connections.** `create_table()` opens a pooled connection. If tests use `:memory:`, each connection gets a separate database. Use file-based SQLite in tests via `tmp_path` fixture.
- **`_coerce_value()` converts non-native types to string.** Any value that is not `int`, `float`, `str`, `bytes`, `bool`, `None`, `datetime`, `dict`, or `list` gets `str()` applied. This includes Pydantic types like `AnyHttpUrl`.
- **Collection fields are excluded from INSERT/UPDATE.** `get_list_fields()` identifies `ListRef[T]` and `List[BaseModel]` fields. These are excluded from column lists because they live in join tables, not as columns on the parent table.
- **Join model FK column naming:** `{ParentClassName.lower()}_id`. The FK column on `ProductComment` is `product_id`. Aliasing the `id` field on models can cause naming clashes.
- **`_validate_identifier()` rejects unsafe SQL identifiers.** Table and column names must match `^[a-zA-Z_][a-zA-Z0-9_]*$`. This prevents SQL injection but also means table names cannot contain hyphens or special characters.
- **Populate cycle prevention.** `_populate_fields` tracks visited model names in `_visited` to prevent infinite recursion on circular relationships. Each branch gets an immutable copy of the visited set.
