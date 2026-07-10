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

### Update boundary contract

Storage and `StorableMixin.update()` are patch-oriented: only keys present in
the supplied dictionary are written.

```python
Product.update(1, {'price': 19.99})  # all omitted fields remain unchanged
```

Generated HTTP `PUT` routes currently have a stricter boundary: they validate a
complete model before calling `update()`. Callers must send all required fields
and include current values for defaulted collections/JSON fields they need to
preserve. Otherwise model validation may materialize omitted defaults such as
`[]` or `{}` and storage will correctly treat those values as explicit
replacements.

For every collection field, storage replacement semantics are:

| Payload state | Storage behavior |
|---|---|
| Field omitted from a direct Python/TX patch | Leave field unchanged |
| Field supplied with values | Replace the complete stored field |
| Field supplied as `[]` or `{}` | Clear the complete stored field |

`list[T]` stores ordered local child IDs; `list[Ref[T]]` stores ordered
local/distributed pointers. Neither performs an atomic append/remove operation.
Read-modify-write updates are last-write-wins, so use domain-specific methods for
concurrency-sensitive relationship mutations.

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
For the complete developer and agent guide, including tradeoffs and change
checklists, see `/workspace/docs/JSON_FIELDS.md`.

```python
class Config(ProtoModel):
    __tablename__ = 'configs'
    __storable__ = True
    tags: list = Field(default=[])           # TEXT column, json.dumps/loads
    metadata: dict = Field(default={})       # TEXT column, json.dumps/loads
    scores: List[int] = Field(default=[])    # TEXT column, json.dumps/loads
    related_refs: list[Ref[Comment]] = Field(default=[])  # TEXT column, json.dumps/loads
```

Detection: `get_json_fields(model_class)` in `introspection.py` returns fields for JSON treatment. It matches `dict`, `Dict[str, Any]`, `list`, `List[str]`, `List[int]`, and distributed pointer arrays such as `list[Ref[T]]`.

Write path: `_coerce_value()` calls `json.dumps(v, default=str)` for dict/list values.
Read path: `_deserialize_json_fields()` calls `json.loads()` on string values before model instantiation.

Use JSON fields for metadata, settings, primitive arrays, external payload
fragments, distributed pointer arrays, and local owned `list[T]` relationship
ids. If nested data needs independent routes, authorization, lifecycle events,
or row-level updates, model the child as its own storable resource and store its
ids in a parent `list[T]` field.

The read path also normalizes legacy empty-string values before Pydantic
validation. If a bool field contains `''` or the literal string `"''"` from an
older/default SQLite column, storage coerces it to `False` so existing rows
remain loadable. If a nullable numeric field such as `Optional[float]` or
`Optional[int]` contains the same empty-string sentinel, storage coerces it to
`None`. The write path applies the nullable numeric normalization as well, so
partial updates from forms or tools do not reintroduce invalid empty strings.
Valid bool strings such as `'true'`, `'false'`, `'0'`, and `'1'`, and valid
numeric strings such as `'123.45'`, are left intact for Pydantic's normal
parsing.

### FK Hydration

`Ref[T]` fields historically store local refs as plain integers and serialize
them as href URLs in API responses:

```python
# Stored in DB: user_owner = 3
# Returned by get()/list(): user_owner = "http://localhost:5000/users/3"
```

Distributed ref support keeps that local behavior and adds canonical string
addresses for configured remote N3TX services. The reference helpers in
`n3tx_core.models.ref` accept local ids, `/ClassName/{id}` paths,
current-service API URLs, configured remote HTTP URLs, and canonical
`n3tx://service/ClassName/id` refs. Configured remote HTTP refs canonicalize to
`n3tx://...`; arbitrary HTTP(S) links are classified as external links rather
than Matrix refs.

Remote dereferencing is opt-in. `SQLiteStorage(reference_resolver=None)` is the
default and preserves local-only populate behavior: remote refs are stored and
returned as canonical strings but are not fetched. Actor-mode or app bootstrap
can inject a Matrix-backed resolver with `SQLiteStorage(...,
reference_resolver=resolver)` or `storage.set_reference_resolver(resolver)`.
The resolver may expose `resolve(ref, target_cls=None, user=None, context=None)`
or be directly callable with that signature.

For distributed pointer arrays, use JSON-backed `list[Ref[T]]`. For local owned
collections, use `list[T]`: SQLite stores the parent column as a JSON array of
local child ids and hydrates it into self-describing child objects on read.

```python
# Stored in DB: comments = [5, 9]
# Returned by get()/list(): comments = [{"id": 5, "$id": "/Comment/5", ...}, ...]
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
- **Collection fields are JSON columns.** Local `list[T]` fields store child ids in the parent row and hydrate to objects on read. Updates replace the stored id list for that field.
- **`_validate_identifier()` rejects unsafe SQL identifiers.** Table and column names must match `^[a-zA-Z_][a-zA-Z0-9_]*$`. This prevents SQL injection but also means table names cannot contain hyphens or special characters.
- **Populate cycle prevention.** `_populate_fields` tracks visited model names in `_visited` to prevent infinite recursion on circular relationships. Each branch gets an immutable copy of the visited set.
