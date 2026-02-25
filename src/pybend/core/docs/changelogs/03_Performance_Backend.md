# Backend Performance Optimizations

> **Status:** Complete.
> **Scope:** Eliminated major backend performance bottlenecks — schema caching, N+1 query batching, connection pooling, introspection caching, and FK indexing.

---

## Table of Contents

1. [Summary](#1-summary)
2. [Schema Caching](#2-schema-caching)
3. [Batch FK Hydration](#3-batch-fk-hydration)
4. [Connection Pooling + WAL Mode](#4-connection-pooling--wal-mode)
5. [Field Introspection Caching](#5-field-introspection-caching)
6. [FK Index Creation](#6-fk-index-creation)
7. [File-by-File Changes](#7-file-by-file-changes)
8. [Verification](#8-verification)

---

## 1. Summary

Five optimizations targeting the backend hot path — the code that runs on every HTTP request:

| Optimization | Problem | Fix | Impact |
|---|---|---|---|
| Schema caching | `schema()` rebuilt full JSON Schema on every `GET /{Class}` | Cache per class, return `deepcopy` | O(1) schema serving after first call |
| Batch FK hydration | N+1 queries: one `SELECT` per parent row per ListRef field | Single `WHERE fk IN (?, ?, ...)` per field | O(fields) instead of O(rows * fields) |
| Connection pooling | New `sqlite3.connect()` on every operation | `queue.Queue`-based pool with WAL mode | Reuse connections, concurrent reads |
| Introspection caching | `get_list_fields()`/`get_ref_fields()` re-introspected on every call | `functools.lru_cache(maxsize=None)` | Zero-cost after first call per class |
| FK indexes | No indexes on `product_id`, `parent_id` etc. | `CREATE INDEX` in migration | O(log n) lookups instead of O(n) scans |

---

## 2. Schema Caching

### Problem

`ProtoModel.schema()` walks the entire Pydantic model, collects referenced models, builds method signatures, injects `$defs`, access rules, and UI hints — then throws the result away. Every `GET /Product` rebuilt everything from scratch.

### Fix

Added two class-level caches on `ProtoModel`:

```python
_schema_cache: ClassVar[dict] = {}       # cls -> full schema dict
_response_meta_cache: ClassVar[dict] = {} # cls -> ($schema URL, tablename prefix)
```

`schema()` checks the cache first and returns `copy.deepcopy(cached)` to protect the cached dict from mutation by callers. The `model_dump(response=True)` path also caches the per-class URL metadata (`$schema` string, tablename prefix) so it doesn't rebuild them on every serialization.

### Key Decision: Cache Key

The cache uses the **class object itself** as the dict key (not `cls.__name__` or `id(cls)`):
- `cls.__name__` collides when test classes share names (e.g., two `class M` with different `__tablename__`)
- `id(cls)` gets reused by Python when classes are garbage collected
- `cls` as key creates a strong reference that prevents GC — which is correct, since cached schemas should persist

An `invalidate_schema_cache()` classmethod is provided for testing and dynamic model changes.

---

## 3. Batch FK Hydration

### Problem

Classic N+1 query pattern in `sqlite_storage.list()`. For a parent with one ListRef field and 20 results:

```
SELECT COUNT(*) FROM products                           -- 1 query
SELECT * FROM products LIMIT 20 OFFSET 0               -- 1 query
SELECT id FROM comments WHERE product_id = 1            -- per row
SELECT id FROM comments WHERE product_id = 2            -- per row
...                                                     -- 20 more
```

Total: 22 queries. With 3 ListRef fields: 62 queries. With populate depth > 0 it multiplies further.

### Fix

Replaced per-row queries with batched `WHERE IN`:

```sql
-- One query per ListRef field, regardless of row count
SELECT id, product_id FROM comments WHERE product_id IN (1, 2, 3, ..., 20)
```

Results are grouped into a dict keyed by FK value, then distributed to each parent row. Same pattern applied in `_populate_fields()` for nested ListRef hydration on child records.

Total after fix: 4 queries (count + select + 1 per ListRef field), regardless of result count.

---

## 4. Connection Pooling + WAL Mode

### Problem

Every storage operation opened a new `sqlite3.connect()` and closed it after. Connection setup includes file locking, journal mode negotiation, and pragma initialization — repeated on every request.

SQLite's default journal mode (`DELETE`) also serializes all writes and blocks concurrent reads during writes.

### Fix

Added a `queue.Queue`-based connection pool to `SQLiteStorage`:

```python
def __init__(self, database: str = 'database.db', pool_size: int = 4):
    self._pool = queue.Queue(maxsize=pool_size)
    init_conn = sqlite3.connect(database, check_same_thread=False)
    init_conn.execute("PRAGMA journal_mode=WAL")
    init_conn.execute("PRAGMA busy_timeout=5000")
    self._pool.put(init_conn)
```

All operations use a `_connection()` context manager that borrows from the pool and returns on exit. New connections are created on demand up to `pool_size`.

WAL (Write-Ahead Logging) mode enables concurrent reads during writes — critical for FastAPI's multi-threaded request handling. `check_same_thread=False` is required because FastAPI dispatches requests across threads.

---

## 5. Field Introspection Caching

### Problem

`get_list_fields()` and `get_ref_fields()` walk `model_class.model_fields`, unwrap `Optional`, check `Annotated` metadata, and resolve forward references — on every call. These are called in `list()`, `get()`, `create()`, `_populate_fields()`, and `_hydrate_fks()`.

For a single paginated list request with populate, these functions were called 6+ times with the same model class.

### Fix

Added `@functools.lru_cache(maxsize=None)` to both functions. The input (a model class) is hashable, and the output is deterministic — model fields don't change after class creation.

---

## 6. FK Index Creation

### Problem

FK columns like `product_id` on the `comments` table had no index. The batched `WHERE product_id IN (?, ?, ...)` query from fix #3 still required a full table scan.

### Fix

Added `CREATE INDEX IF NOT EXISTS` in both `create_table()` and `migrate_table()` in `sqlite_migration.py`:

- Auto-generated parent FK columns (e.g., `product_id`)
- Self-referential FK columns (e.g., `parent_id` from `Ref['self']`)

The `IF NOT EXISTS` clause makes it idempotent — safe on both new and existing tables.

---

## 7. File-by-File Changes

| File | Changes |
|---|---|
| `models/proto_model.py` | Added `_schema_cache`, `_response_meta_cache` class vars; `schema()` caches and returns deepcopy; `model_dump(response=True)` caches URL metadata; added `invalidate_schema_cache()` |
| `storage/sqlite_storage.py` | Added `queue.Queue` connection pool with WAL mode; replaced all bare `sqlite3.connect()`/`close()` with `_connection()` context manager; batched FK hydration in `list()` and `_populate_fields()` |
| `storage/sqlite_migration.py` | Added `CREATE INDEX IF NOT EXISTS` for FK columns in `create_table()` and `migrate_table()` |
| `utils/introspection.py` | Added `@functools.lru_cache(maxsize=None)` to `get_list_fields()` and `get_ref_fields()` |

---

## 8. Verification

All changes verified against the full test suite:
- **485 unit tests** — all passing
- **386 integration tests** — all passing
- No behavioral changes — purely performance improvements
