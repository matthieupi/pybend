# N3TX JSON Fields

SQLite stores model dict/list fields as JSON TEXT. Application code normally
receives Python values after deserialization and model validation.

## Mental Model

```text
annotation -> introspection -> TEXT column
write: Python dict/list -> json.dumps(default=str)
read: stored string -> json.loads -> hydration/model validation
```

## Supported Field Shapes

| Shape | Stored value | Meaning |
|---|---|---|
| dict / typed dict | JSON object | Embedded data |
| list / list[str] / list[int] | JSON array | Embedded primitive values |
| list[T] | JSON local ID array | Local relationship, hydrated on read |
| list[Ref[T]] | JSON URL array | Explicit HTTP(S) pointers |
| Optional dict/list | Nullable JSON where supported | Test the exact union spelling through migration and storage |
| ManyToMany[T] | Legacy link mechanism | Not a parent JSON list |

Use `Field(default_factory=dict)` or `Field(default_factory=list)` for clear
mutable defaults. Existing Pydantic model examples with default={} or [] do not
mean arbitrary Python function mutable defaults are safe.

## JSON Field vs Relationship Field

| Concern | Embedded JSON | Local model relationship |
|---|---|---|
| Identity | No independent ID | Child has its own row and flat class-name identity |
| Update | Replace whole field | Replace association list; child rows can update separately |
| Authorization | Parent operation boundary | Child routes can have policies; parent hydration does not automatically apply them |
| Query | No public nested JSON query builder | Child collection can be queried independently |
| Use | Settings, metadata, primitive tags | Independently addressable domain records |

Keep scalar filter/index fields explicit when they drive core queries. Use a
related model when data needs its own lifecycle, not a parallel JSON copy of it.

## Write Path

`SQLiteStorage.create/update` bind values through `_coerce_value`.
Dicts/lists serialize recursively; unsupported nested values use `str()`.
Construct a model before calling `Model.create`:

```python
# Fragment: Job is an already registered model with declared name/payload fields.
saved = Job.create(Job(name='scan', payload={'tags': ['energy'], 'status': 'queued'}))
Job.update(saved.id, {'payload': {'status': 'done'}})
```

The update replaces payload entirely; it does not retain tags.

## Read Path

`_deserialize_json_fields` uses `get_json_fields` and parses string values before
get/list/model construction and population. Invalid JSON is left unchanged, not
repaired. Pydantic can then reject it. Non-JSON-native values stringified on write
do not automatically regain their original type.

## Migration Behavior

New dict columns use TEXT with `{}` defaults; typed list columns use TEXT with
`[]` defaults in the migration path. Annotation detection and nullable forms need
tests across both create-table and migrate-table. Migration may also drop columns
missing from the model; read [Operations](OPERATIONS.md#migrations) before startup
against existing data.

## Tradeoffs and Gotchas

- Generated PUT and Python update preserve omitted fields. Explicit [] or {} clears
  the whole field. Neither path deep-merges JSON.
- Local relationship IDs and URL pointer arrays have different validation and
  hydration despite both being stored as JSON.
- An embedded JSON object has no independent route, lifecycle event or per-item
  permission boundary.
- `default=str` can lose datetime, URL-type or custom-object fidelity. Use typed
  fields and round-trip tests where that matters.
- There is no public nested JSON query builder; raw SQL JSON expressions are
  application-specific trusted queries, not a portable storage contract.
- Replacing a stale large dictionary can overwrite a newer update. Domain methods
  do not automatically add atomic nested mutation.

## Implementation Map for Agents

Paths below are relative to `packages/n3tx-core/src/n3tx_core/`:

| File | Responsibility |
|---|---|
| `utils/introspection.py` | JSON/local relationship/ref field detection |
| `storage/sqlite_storage.py` | Encoding, decoding, normalization and hydration |
| `storage/sqlite_migration.py` | Table/column types and defaults |
| `tests/unit/test_json_fields.py` | Round-trip and migration cases |
| `tests/unit/test_introspection.py` | Detection cases |

## Change Checklist

Test detection, create-table, migrate-table, create/get/list/update and population.
Check omitted versus empty fields, invalid stored JSON, nullable values, missing
children and URL pointers. Preserve the distinct local/remote relationship
contract. Run the core suite through the [test runner](../README.md#testing).
The package [storage guide](../packages/n3tx-core/docs/storage.md) owns mechanism
details; this page owns JSON design choices.
