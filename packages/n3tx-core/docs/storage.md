# Storage Layer

Part of [n3tx-core](../README.md). Storage owns persistence and hydration, not
HTTP authorization. See [Models](../../../docs/MODELS.md) for declarations and
[Operations](../../../docs/OPERATIONS.md) for deployment procedure.

## Architecture

```text
ProtoModel + injected StorableMixin
    -> validated model/patch -> AbstractStorage -> SQLite
    <- hydrated model       <- rows + JSON columns
```

`register_model(Model, storage=backend)` attaches storage and creates/migrates
the table by default. Factory/builder registration uses the same machinery.
An explicit `SQLiteStorage(auto_migrate=False)` creates absent model tables but
only validates existing ones, as described below.

## Interface

The current AbstractStorage contract is in
`n3tx_core.storage.abstract_storage`. Implement all six operations, including
optional filter/pagination/population inputs. Verify those semantics before
substituting a backend; sharing an interface does not prove parity.

```python
create_table(self, model_class)
create(self, model_class, data)
list(self, model_class, sql_filter=None, limit=None, offset=None, populate=None, ids=None, *, order_asc=None, order_desc=None)
get(self, model_class, id_=None, as_dict=False, populate=None)
update(self, model_class, id_, data)
delete(self, model_class, id_)
```

These are signature summaries; concrete SQLite's get/update/delete parameter is
named `id`. Pass it positionally through the model API.

### SQLiteStorage Internals

```python
SQLiteStorage(
    database='database.db', pool_size=4, reference_resolver=None,
    auto_migrate=True,
)
```

`auto_migrate` is a keyword-only Boolean, defaulting to True. Storage uses pooled
connections with `check_same_thread=False`, WAL and a 5000 ms busy timeout.
The timeout waits for locks; it does **not** prevent lock errors or make
read-modify-write operations atomic. SQLite still serializes writers.

Use a file-backed temporary database in tests. Separate migration/pool
connections to `:memory:` can see different databases. Table/column identifiers
must match `^[a-zA-Z_][a-zA-Z0-9_]*$`; values use parameter binding. Application
SQL filters and model identifiers must remain trusted inputs.

The legacy JSONStorage class implements old `get_all`/`get_by_id` names rather
than current abstract `list`/`get`; it cannot currently be instantiated as a
complete backend. Do not present it as a drop-in alternative to SQLite.

### StorableMixin CRUD

Given a registered Product model (reference fragments):

```python
saved = Product.create(Product(name='Widget', price=9.99))
product = Product.get(saved.id)
rows = Product.list()
page = Product.list(limit=20, offset=0)
selected = Product.list(ids=[1, 2])
filtered = Product.list(sql_filter=('price > ?', [10]))
matching = Product.list(
    where={'name__contains': 'Widget', 'price__lt': 100},
    order_asc='name', limit=20,
)
ordered = Product.list(order_asc='price', limit=20, offset=0)
updated = Product.update(saved.id, {'price': 19.99})
Product.delete(saved.id)
```

`create` expects an instance with `_storage_dict`, not a bare dictionary.
`save()` creates when ID is falsey and updates otherwise. `get(as_dict=True)`
returns storage-oriented data; `model_response()` is the response boundary.
Direct Python operations are trusted and do not apply route policy.

`list(where=...)` accepts ANDed model-field conditions: equality, `__lt`,
`__gt`, `__lte`, `__gte`, `__ne`, `__in`, and `__contains`. The shared
`utils.where.compile_where` validates field identifiers and declared model
fields, binds scalar values, and combines caller conditions with the trusted
`sql_filter`. Storage still receives only the existing SQL predicate contract.
The reserved `$or` key accepts a nonempty array of nonempty condition objects.
Each branch is validated and parenthesized; sibling fields still AND with the
whole OR group, and authorization remains outside it. Nesting is limited to
eight levels. Date/datetime values use the model annotation and native SQLite
ISO representation for binding, without UTC normalization or timezone-aware
SQL comparisons. Mixed-offset temporal ordering is not guaranteed.
Contains uses literal, case-sensitive SQLite `instr`; `%` and `_` are ordinary
characters. Membership requires a list/tuple; an empty one matches nothing.
Equality/inequality with `None` uses `IS NULL`/`IS NOT NULL`.
Invalid field names, operators, value shapes, and non-finite/out-of-range
numbers raise `ValueError`. No nested fields or raw SQL are accepted in `where`.
Caller filtering and ordering reject private/dunder names, methods, undeclared
aliases, hidden and excluded fields (including conditional exclusion).
Write-protected readable fields remain filterable and sortable; query selection
does not grant write access or bypass row policies.
Contains requires a text annotation, not a numeric or JSON-backed field.
This protects selection from hidden-field probes; it is not response redaction
or model-value coercion. Trusted authorization `Where` rules may still reference
hidden/excluded fields, but cannot bypass identifier validation.

### Update Boundary Contract

`Model.update(id, patch)` and `instance.update(patch)` canonicalize input aliases,
strip identity metadata, merge with current state and validate through the
original model. Only supplied keys are persisted. An instance call may use its
in-memory state; it is not guaranteed to refetch before validation.

| Input | Behavior |
|---|---|
| Omitted field | Unchanged |
| Supplied collection/dict | Whole-field replacement |
| Empty list/dict | Clears field if valid |
| Duplicate alias/canonical key | Rejected as ambiguous |
| Invalid local list child | Update rejects unresolved/shortened list |
| Empty patch | Returns current entity without a write |

Model validators can inspect complete merged state. Changes they derive in
omitted fields are not written automatically. Verify persisted invariants after
update. Generated HTTP additionally strips protected fields; trusted Python
update does not provide that protection.

No optimistic version check or transaction spans read/validation/write. Domain
actions can centralize append/remove/toggle behavior, but still race unless
their implementation explicitly addresses concurrency. Multiple model saves are
not one transaction merely because they occur in one method.

### Pagination Response Shape

SQLite validates supplied `limit` and `offset` before opening a connection:
each must be an integer from zero through `2**63 - 1`, or omitted/None.
Booleans, strings, floats, negatives and oversized integers raise `ValueError`.
Internal `limit=0` count probes remain supported; generated HTTP retains its
separate limit1–100 constraint. Native HTTP/actor adapters map invalid storage
pagination to422. Offsets above the former application32-bit cap remain valid.

Without limit, `list()` returns model instances in a list. With limit it returns
`{'data': [instances], 'meta': {'total', 'limit', 'offset', 'has_more'}}`.
HTTP serialization turns instances into response dictionaries. Count and page
selection are not a stable snapshot under concurrent writes.

### Native list ordering

`order_asc` and `order_desc` are optional keyword-only single field names, and
are mutually exclusive. SQLite accepts only declared model fields that also
exist as physical table columns, not properties, aliases or SQL expressions.
Invalid names or conflicting directions raise `ValueError`; generated direct
and actor HTTP list routes return 422. Ordering is applied after filtering and
before limit/offset; the total count and hydration are unchanged.

SQLite uses its native column comparison and NULL ordering (NULL first for
ascending, last for descending). No secondary tie order is added. With neither
option, the existing unspecified ordering and backend delegation are preserved.

### Datetime limitations

Datetime values use SQLite's native adapter and Pydantic validation/serialization,
without custom offset decoding, response normalization or UTC-overflow guards.
UTC offsets containing seconds or fractional seconds are intentionally unsupported:
stored values may fail hydration and JSON output may lose offset precision.
Use ordinary minute-aligned offsets or UTC; timestamp microseconds remain supported.

### JSON Field Handling

Dicts and lists use TEXT columns and JSON encoding. Primitive lists, local
list[T] ID arrays and list[Ref[T]] URL arrays share a physical representation,
not identical semantics. `_coerce_value` uses `json.dumps(..., default=str)`;
`_deserialize_json_fields` parses strings before model construction. Invalid JSON
is left unchanged and may fail validation. Rich nested values can lose type
information through string conversion. See [JSON fields](../../../docs/JSON_FIELDS.md).

Legacy `''` and literal `"''"` sentinels are normalized to false for bools and
None for supported nullable numeric fields. Nullable numeric write normalization
also exists; valid numeric/bool strings remain for Pydantic parsing. Do not use
this compatibility behavior as a substitute for clean inputs or a data migration.

### Local Relationships and URL Refs

Local model fields hydrate through model storage; scalar annotations have the
[first-injection rewrite caveat](../../../docs/MODELS.md#scalar-annotation-rewriting).
Local `list[T]` stores ordered child IDs on the parent and batch-loads children.
Use saved children and register every target class. Ordinary reads can omit
missing children; update validates that every supplied child resolves. Clearing
the list does not delete child rows.

Ref[T] and list[Ref[T]] contain HTTP(S) URL strings. Validation and ordinary
unpopulated reads do not perform remote I/O. They do not accept legacy n3tx://
addresses or treat all URLs as local IDs.

### Eager Loading (Populate)

```python
from n3tx_core.utils.populate import parse_populate

fields = parse_populate('comments.likes,tags', None)
one_level = parse_populate(None, 1)
```

Pass the resulting spec to model get/list. HTTP uses `populate` and `depth`
query parameters. Populated values live in `_populated` and overlay the response
through the dump pipeline. Traversal tracks visited model names to limit cycles;
this is not a general graph query engine.

Explicit URL population uses an injected reference resolver. `Ref.hydrate`
requires an explicit resolver context; storage without a resolver cannot fetch
remote entities. Pointer-list population can retain per-reference errors instead
of failing the whole parent. Verify partial results and credentials. Do not
assume storage population carries the same caller policy as a separate HTTP read.

## Migrations

### Default model reconciliation

`SQLiteStorage(auto_migrate=True)` retains ordinary native registration behavior.
`SQLiteMigration.create_table` creates tables. `migrate_table` adds missing columns
and **attempts to drop orphaned columns**, including columns whose names start
with underscores. It is not additive-only. Unmarked SQL defaults are type-based
and may differ from application Field defaults. Type changes, renames, data
backfills and joins-to-JSON conversion need explicit planning.

### Non-migrating model registration

Pass a configured backend instance to native bootstrap or registration:

```python
from n3tx_core.storage.sqlite_storage import SQLiteStorage

storage = SQLiteStorage('app.db', auto_migrate=False)
# Pass storage=storage to create_app(...) or register_model(...).
```

In this mode both `create_table` and `migrate_table`:

- Create an absent model table and its native relationship indexes.
- For an existing table, compare its physical column names with the same native
  projection used by creation, including nested-model `_id` columns and `id`.
  Missing or surplus columns raise `ValueError` before model DDL; there is no
  ADD, DROP, rebuild, index creation or automatic repair on an existing table.
- Validate type, NOT NULL and literal default metadata only for the opted-in
  fields below, through SQLite PRAGMA metadata. Unmarked types, defaults and
  nullability are not compared. Unrelated extension tables are not inspected.

Ordinary false-mode registration does not initialize or replay the manual
`_migrations` ledger. This is a schema policy, **not a read-only storage backend**:
the usual WAL/pool initialization and CRUD remain, and absent tables are created.
Registration across several models is not one atomic schema transaction; an
earlier absent table can be created before a later model refuses its schema.
Use explicit offline preparation for incompatible existing stores.

### Opt-in NOT NULL defaults

Set `json_schema_extra['x-sqlite-not-null-default'] = True` on an ordinary stored
field to derive its SQL constraint from a static `Field.default`:

```python
from pydantic import Field

# Fields inside a model declaration:
status: str = Field(
    default='created',
    json_schema_extra={'x-sqlite-not-null-default': True},
)
is_read: bool = Field(
    default=False,
    json_schema_extra={'x-sqlite-not-null-default': True},
)
```

The string default produces `TEXT NOT NULL DEFAULT 'created'`; the Boolean
produces `INTEGER NOT NULL DEFAULT 0` (`True` produces `1`). String contents are
single-quote escaped as literal data, never interpreted as SQL. Missing defaults,
None, factories, non-string/non-Boolean defaults and strings containing NUL raise
`ValueError`. Factories are never executed to derive a SQL default.

Marked Boolean defaults use INTEGER consistently for creation, validation and
native round trips: SQLite binds bools as integers and Pydantic restores bools on
model reads. Unmarked Boolean creation remains TEXT, and its legacy migration and
read normalization behavior is unchanged.

False mode requires the marked column's PRAGMA type (case-insensitive), NOT NULL
flag and literal default to match this projection. It does not evaluate default
expressions or accept arbitrary equivalent SQL expressions. Default true mode
uses the hint for new tables or missing columns but does not retrofit constraints
on existing columns; review such changes as an explicit offline migration.

### Explicit manual migrations

Manual migrations subclass `Migration` with `up(cursor)` and `down(cursor)`.
`SQLiteMigration.run_migrations()`, `rollback(steps=1)` and `migration_status()`
manage recorded migrations from the configured directory. `SQLiteMigration` also
accepts keyword-only `auto_migrate=True`; storage passes its policy through.
The flag controls model registration only, not these explicitly invoked manual
APIs. Their first use in false mode initializes the tracking ledger. A down method
is not a guarantee that lost data can be recovered. See
[Operations](../../../docs/OPERATIONS.md#migrations).

## Gotchas

- Registration is a database-changing operation; inspect startup logs and backups.
- No general cascade, inverse-relation maintenance or child authorization follows
  from a field declaration.
- JSON arrays do not offer per-element SQL updates through the model API.
- Raw storage writes bypass merged-model validation and route policy.
- Do not advertise pooled connections or WAL as distributed-write support.

## Changelog

- 2026-11-12: Document opt-in non-migrating registration, shared native column
  projection and safe static string/Boolean NOT NULL defaults. Distinguish model
  validation from explicit manual migrations and read-only storage.
