# P4: Search & Filter — Generic N3TX Core Feature

## Summary

Full-stack generic search, filter, and sort capability built directly into N3TX core. Any N3TX app gets search/filter for free — no app-specific code needed.

## Architecture & Data Flow

**Current list flow:**
```
Frontend: proto.call('READ', {limit, offset})
  -> NetworkAdapter.send() encodes tx.data as URL query params
  -> GET /products?limit=20&offset=0
Backend: routes extract limit/offset -> StorableMixin.list() -> SQLiteStorage.list()
```

**New flow (additive — no changes to transport):**
```
Frontend: proto.call('READ', {limit, offset, search, status, price_min, sort_by, sort_order})
  -> GET /products?limit=20&offset=0&search=widget&status=active&price_min=10&sort_by=price&sort_order=desc
Backend: routes extract known + filter params -> list(filters={...}, search=..., sort_by=..., sort_order=...)
  -> SQLiteStorage builds parameterized WHERE clauses
```

Key insight: Frontend's `NetworkAdapter.send()` already encodes `tx.data` as URL query params for READ events. No transport changes needed.

## Backend: Storage Layer

### `src/n3tx/core/storage/sqlite_storage.py`

**Extended `list()` signature:**
```python
def list(self, model_class, sql_filter=None, limit=None, offset=None, populate=None,
         filters=None, search=None, sort_by=None, sort_order=None)
```

**New `_build_filter_clauses(model_class, filters, search)` method:**
- Inspects `model_class.model_fields` for valid field names
- Pattern matching on filter keys:
  - `{field}` → exact match: `WHERE {field} = ?`
  - `{field}_min` → range: `WHERE {field} >= ?`
  - `{field}_max` → range: `WHERE {field} <= ?`
  - `{field}_after` → date: `WHERE {field} >= ?`
  - `{field}_before` → date: `WHERE {field} <= ?`
  - `{field}_like` → partial: `WHERE {field} LIKE ?` (wrapped with `%`)
- Column names validated via `_validate_identifier()` (existing function)
- All values parameterized (injection-safe)

**Sort:** `ORDER BY {validated_column} {ASC|DESC}` — sort_order whitelisted to `asc`/`desc` only.

**Integration with ABAC `sql_filter`:** Security filter comes first (AND), then user filters appended.

### FTS5 Full-Text Search

**New methods in `sqlite_storage.py`:**
- `create_fts_index(model_class)`: Creates FTS5 virtual table for string fields
  - Uses `content='{tablename}'` for external-content FTS
  - Tokenizer: `'porter unicode61'` (stemming + unicode)
- `_ensure_fts_triggers(model_class, conn)`: AFTER INSERT/UPDATE/DELETE triggers for sync

**Opt-in via `__searchable__ = True`** (default for storable models).

**Search fallback:** If no FTS5 table exists, falls back to OR chain of LIKE on string fields.

### `src/n3tx/core/storage/abstract_storage.py`
Update abstract `list()` signature with new optional parameters.

### `src/n3tx/core/models/storable_mixin.py`
Pass through new parameters to storage.

### `src/n3tx/core/storage/sqlite_migration.py`
Add `create_fts_table()` and `migrate_fts_table()` methods.

## Backend: Route Layer

### `src/n3tx/core/api/filter_utils.py` (New — shared helper)

```python
def _extract_filters(request, model_class) -> dict | None:
    """Extract filter params from query string, validated against model fields."""
    # Skip known params: limit, offset, populate, depth, search, sort_by, sort_order, scaffold
    # For remaining: check if base field (stripped of _min/_max/_after/_before/_like suffix)
    # exists in model_class.model_fields
    # Return filter dict or None
```

### `src/n3tx/core/api/routes_fastapi.py` (Level 1/2)

Add to `make_get_all_instances()`:
```python
search: str = Query(default=None)
sort_by: str = Query(default=None)
sort_order: str = Query(default=None, regex="^(asc|desc)$")
```
Extract filters via `_extract_filters(request, model_class)`.

Same change for `make_collection_list()`.

### `src/n3tx/core/api/network_api.py` (Level 3)

Extract filter params, include in TX data:
```python
data['filters'] = filters
data['search'] = search
data['sort_by'] = sort_by
data['sort_order'] = sort_order
```

### `src/n3tx/core/models/actor_model.py` (Level 3 handler)

Pass through in `handler_crud` list branch:
```python
result = cls.list(
    sql_filter=tx.meta.get('sql_filter'),
    limit=data.get('limit'), offset=data.get('offset'),
    filters=data.get('filters'), search=data.get('search'),
    sort_by=data.get('sort_by'), sort_order=data.get('sort_order'),
)
```

## Backend: Schema Extension

### `src/n3tx/core/models/filter_schema.py` (New)

```python
@schema_extension(after='widget', before='ui')
def filterable(cls, schema: dict) -> dict:
    """Inject filterable metadata into schema properties."""
```

Per-field metadata based on type:

| JSON Schema type | filterable annotation |
|-----------------|----------------------|
| `string` | `{"type": "text", "operators": ["exact", "like"]}` |
| `number`/`integer` | `{"type": "range", "operators": ["exact", "min", "max"]}` |
| `boolean` | `{"type": "boolean", "operators": ["exact"]}` |
| date widget | `{"type": "daterange", "operators": ["after", "before"]}` |
| status widget + options | `{"type": "select", "operators": ["exact"], "options": {...}}` |
| array / $ref / selfref | not filterable |

Also adds: `search: true` (if `__searchable__`), `sort: true`.

## Frontend: Filter Bar Component

### New: `src/n3tx/static/components/ntx-filter-bar.js`

Auto-generates filter controls from schema `filterable` metadata.

```html
<ntx-filter-bar>
  <div class="filter-bar">
    <div class="search-box"><input type="search" placeholder="Search..." /></div>
    <div class="filters">
      <!-- Auto-generated from schema.properties[field].filterable -->
      <select data-filter="status">        <!-- for select type -->
      <input type="number" data-filter="price_min">  <!-- for range type -->
      <input type="date" data-filter="deadline_after"> <!-- for daterange -->
    </div>
    <div class="sort">
      <select data-sort>...</select>
      <button class="sort-order">↑↓</button>
    </div>
    <div class="filter-actions">
      <span class="filter-count">3 filters</span>
      <button class="clear-btn">Clear</button>
    </div>
  </div>
</ntx-filter-bar>
```

**Properties:** `schema` (set by parent), `filters` (get: current state)
**Events:** `filter-change` (debounced 300ms for text, immediate for select)

### New: `src/n3tx/static/components/ntx-filter-bar.css`

### Modified: `src/n3tx/static/components/ntx-table.js`
- Render `<ntx-filter-bar>` before table header
- Wire `filter-change` event to `#applyFilters(criteria)`
- `#applyFilters()`: Resets offset to 0, sends READ with filter data
- `loadMore()`: Preserves `#currentFilters` when paginating

### Modified: `src/n3tx/static/components/ListElement.js`
- Add `#currentFilters` property
- `loadMore()` includes current filters in READ data

### Modified: `src/n3tx/static/components/ntx-list.js`
- Same filter bar integration as ntx-table

## Security

1. **SQL injection**: All values parameterized, column names validated via `_validate_identifier()`
2. **Schema-aware**: Only fields in `model_class.model_fields` can be filtered
3. **ABAC preserved**: `sql_filter` always applied first, combined with AND
4. **FTS5 safe**: MATCH queries parameterized
5. **Input sanitized**: Numeric filters type-coerced, dates validated as ISO format

## Tests

### `src/n3tx/core/tests/unit/test_filter_storage.py`
- Filter exact string, like string, numeric range, date range, boolean
- Filters compose with ABAC sql_filter via AND
- Unknown field names silently ignored
- SQL injection prevented
- Sort ascending/descending
- Pagination with filters (total reflects filtered count)
- FTS5 search, fallback LIKE search

### `src/n3tx/core/tests/unit/test_fts.py`
- FTS5 index creation, trigger insert/update/delete
- Search ranking, prefix search, phrase search
- `__searchable__ = False` opt-out

### `src/n3tx/core/tests/unit/test_filter_schema.py`
- String → text filterable, numeric → range, date → daterange
- Status with options → select, array → not filterable
- Hidden fields not filterable
- `search: true` flag, `$defs` get filterable

### `src/n3tx/static/tests/components/ntx-filter-bar.test.js`
- Renders search input, select for status, range for numeric, daterange for date
- Emits filter-change on input/select, clear resets all
- Filter count updates

### Integration tests
- `GET /products?search=keyword` returns filtered results
- `GET /products?status=active` returns filtered
- `GET /products?sort_by=price&sort_order=desc` returns sorted
- Filters respect auth (OWNER rules still enforced)

## Execution Order

```
Day 1: Storage layer (_build_filter_clauses, extend list(), tests)
Day 2: FTS5 + Route layer (filter_utils.py, routes_fastapi.py, network_api.py, actor_model.py)
Day 3: Schema extension + Frontend filter bar (filter_schema.py, ntx-filter-bar.js)
Day 4: Integration + Polish (ntx-table.js, ntx-list.js, ListElement.js, integration tests)
```

## Files Summary

**New files (5):**
- `src/n3tx/core/api/filter_utils.py`
- `src/n3tx/core/models/filter_schema.py`
- `src/n3tx/static/components/ntx-filter-bar.js`
- `src/n3tx/static/components/ntx-filter-bar.css`
- `src/n3tx/static/tests/components/ntx-filter-bar.test.js`

**New test files (3):**
- `src/n3tx/core/tests/unit/test_filter_storage.py`
- `src/n3tx/core/tests/unit/test_fts.py`
- `src/n3tx/core/tests/unit/test_filter_schema.py`

**Modified files (6):**
- `src/n3tx/core/storage/sqlite_storage.py`
- `src/n3tx/core/storage/abstract_storage.py`
- `src/n3tx/core/models/storable_mixin.py`
- `src/n3tx/core/api/routes_fastapi.py`
- `src/n3tx/core/api/network_api.py`
- `src/n3tx/core/models/actor_model.py`

**Modified frontend files (3):**
- `src/n3tx/static/components/ntx-table.js`
- `src/n3tx/static/components/ntx-list.js`
- `src/n3tx/static/components/ListElement.js`
