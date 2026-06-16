# N3TX JSON Fields

This guide explains how N3TX stores `dict` and `list` model fields as JSON,
when to use them, how they differ from relationships, and which implementation
points agents and developers should inspect before changing this part of the
system.

## Mental Model

JSON fields are ordinary model fields whose Python value is a `dict` or `list`,
but whose SQLite representation is a `TEXT` column containing serialized JSON.

```text
Model annotation
  -> get_json_fields(model_class)
  -> SQLite TEXT column
  -> json.dumps(value, default=str) on write
  -> json.loads(value) on read
  -> Pydantic validation / model instance
```

Example:

```python
from pydantic import Field
from n3tx_core.models.proto_model import ProtoModel


class AgentConfig(ProtoModel):
    __tablename__ = "agent_configs"
    __storable__ = True

    tools: list[str] = Field(default=[])
    constraints: dict = Field(default={})
    metadata: dict = Field(default={})
```

SQLite stores these fields as text:

```text
tools        TEXT -> '["search", "scrape"]'
constraints  TEXT -> '{"max_iterations": 30}'
metadata     TEXT -> '{"provider": "ollama", "nested": {"ok": true}}'
```

The storage layer deserializes them before model construction, so application
code sees normal Python values:

```python
config.tools == ["search", "scrape"]
config.constraints == {"max_iterations": 30}
```

## Supported Field Shapes

JSON field detection is implemented by
`n3tx_core.utils.introspection.get_json_fields()`.

| Annotation | JSON TEXT field? | Notes |
|---|---:|---|
| `dict` | Yes | Stored with `json.dumps()` |
| `Dict[str, Any]` | Yes | Any `dict` origin is included |
| `Optional[dict]` | Yes | `typing.Optional` / `typing.Union` is unwrapped |
| `list` | Yes | Stored with `json.dumps()` |
| `List[str]`, `list[str]` | Yes | Primitive typed lists are JSON fields |
| `List[int]`, `list[int]` | Yes | Primitive typed lists are JSON fields |
| `ListRef[T]` | No | Relationship field, backed by FK/join table |
| `List[BaseModel]` | No | Relationship-style collection, not JSON |
| many-to-many field marker | No | Relationship field |

Use the current, test-backed style for nullable JSON fields:

```python
from typing import Optional

config: Optional[dict] = Field(default=None)
```

Avoid assuming every newer union spelling is handled equally in all storage and
migration paths unless there is a test for it.

## JSON Field vs Relationship Field

The most important distinction is whether the nested data needs independent
identity and lifecycle.

```python
# JSON field: embedded data, no identity
tags: list[str] = Field(default=[])
payload: dict = Field(default={})

# Relationship field: child resources, routes, identity, auth, hydration
comments: ListRef[Comment] = Field(default=[])
```

| Concern | JSON field | Relationship / `ListRef` |
|---|---|---|
| Storage | One SQLite `TEXT` column | Child table / join table |
| API identity | No nested `$id` | Child resources get route identity |
| Access control | Whole field only | Per child resource possible |
| Updates | Replace whole field | Row/resource-level updates |
| Querying | No first-class nested query API | Normal row/filter patterns |
| Schema | Pydantic property schema | Full model schema and `$defs` |
| Good for | Config, metadata, payloads | Comments, likes, children, owned records |

Rule of thumb:

- Use JSON fields for simple embedded values that belong entirely to the parent.
- Use models and relationships when the nested thing should be addressable,
  authorized, queried, rendered, or updated independently.

## Write Path

Implementation:

```text
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
```

Key function:

```python
def _coerce_value(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    ...
```

`SQLiteStorage.create()` and `SQLiteStorage.update()` both pass values through
`_coerce_value()` before binding them to SQLite parameters.

Important behavior:

- Python `dict` and `list` become JSON strings.
- Nested dict/list structures are serialized recursively.
- Non-JSON-native nested values are converted with `default=str`.
- Other non-SQLite-native top-level values also fall back to `str()`.

Example:

```python
Job.create({
    "name": "scan",
    "payload": {
        "source": "api",
        "params": {"q": "renewable grants"},
        "tags": ["energy", "funding"],
    },
})
```

## Read Path

Implementation:

```text
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
```

Key function:

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

This runs before model instantiation in the main read paths:

- `SQLiteStorage.get()`
- `SQLiteStorage.list()`
- relationship population paths inside `_populate_fields()`

If a stored value is not valid JSON, the helper leaves it unchanged. Pydantic may
still reject the resulting value if the model field requires `dict` or `list`.

## Migration Behavior

Implementation:

```text
packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py
```

During table creation:

- `dict` fields become `TEXT` columns.
- non-relationship `list` fields become `TEXT` columns.
- `ListRef[T]` and `List[BaseModel]` are skipped because they are relationship
  fields, not parent-table JSON columns.

During auto-migration:

- new `dict` fields are added as `TEXT DEFAULT '{}'`.
- new `list` fields are added as `TEXT DEFAULT '[]'`.

## Common Usage Patterns

### Agent configuration

```python
class AgentProfile(ProtoModel):
    __tablename__ = "agent_profiles"
    __storable__ = True

    tools: list[str] = Field(default=[])
    constraints: dict = Field(default={})
```

Good for:

```json
{
  "tools": ["grants", "web_tools"],
  "constraints": {"max_iterations": 30}
}
```

### Flexible external API payload

```python
class ImportJob(ProtoModel):
    __tablename__ = "import_jobs"
    __storable__ = True

    source: str = ""
    request_payload: dict = Field(default={})
    response_summary: dict = Field(default={})
```

Good when the exact external payload shape is not central to N3TX's domain
model.

### Primitive arrays and metadata

```python
class Document(ProtoModel):
    __tablename__ = "documents"
    __storable__ = True

    title: str
    tags: list[str] = Field(default=[])
    metadata: dict = Field(default={})
```

Good for labels, provider metadata, lightweight flags, and other embedded data.

## Tradeoffs and Gotchas

### JSON fields are not independently addressable

Nested JSON values do not get routes, `$id`, lifecycle events, ownership, or
per-item authorization.

If a nested value should be a resource, model it as a `ProtoModel`/`ActorModel`
and connect it with `ListRef` or another relationship primitive.

### Updates replace the whole field

Partial updates do not deep-merge JSON fields.

```python
Job.update(1, {"payload": {"status": "done"}})
```

This replaces `payload`; it does not preserve other keys from the previous
payload unless the caller includes them.

### There is no first-class nested JSON query API

N3TX currently treats these as serialized text fields. The framework does not
provide a public query builder for expressions like:

```sql
json_extract(payload, '$.status') = 'queued'
```

If an application needs first-class filtering, sorting, or indexing by nested
properties, prefer explicit model fields or related models.

### `default=str` is convenient but lossy

`json.dumps(..., default=str)` prevents many serialization crashes, but it can
silently convert rich values into strings.

Examples:

| Python value | Stored JSON value |
|---|---|
| `datetime.datetime(...)` | string timestamp representation |
| `AnyHttpUrl(...)` | URL string |
| custom object | `str(object)` |

Use explicit field types when round-trip fidelity matters.

### Invalid stored JSON is tolerated, not repaired

`_deserialize_json_fields()` leaves invalid JSON strings unchanged. This avoids
masking or rewriting corrupted data, but Pydantic validation may fail later.

### Mutable defaults rely on Pydantic behavior

Existing examples use `Field(default=[])` and `Field(default={})`. Pydantic v2
handles model defaults safely for normal model construction, but new code may
still prefer `default_factory=list` or `default_factory=dict` when that improves
clarity.

## Implementation Map for Agents

Start with these files when investigating or changing JSON-field behavior:

| File | Why it matters |
|---|---|
| `packages/n3tx-core/src/n3tx_core/utils/introspection.py` | `get_json_fields()` decides which fields are JSON TEXT |
| `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` | `_coerce_value()` writes JSON; `_deserialize_json_fields()` reads JSON |
| `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py` | Creates and migrates JSON fields as `TEXT` columns |
| `packages/n3tx-core/docs/storage.md` | Package-level storage behavior reference |
| `packages/n3tx-core/src/n3tx_core/tests/unit/test_json_fields.py` | Round-trip and migration coverage |
| `packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py` | Detection coverage for JSON vs relationship fields |

## Change Checklist

When changing JSON-field behavior:

1. Preserve the relationship boundary: `ListRef[T]`, many-to-many fields, and
   `List[BaseModel]` must not become JSON fields accidentally.
2. Update both storage and migration behavior if detection rules change.
3. Add tests for detection, migration, create/get/list/update, and populate if
   the change affects related records.
4. Verify existing relationship hydration still returns href arrays for
   relationship fields.
5. Update this guide and `packages/n3tx-core/docs/storage.md` if the public
   behavior changes.

Recommended verification:

```bash
cd /workspace && python3 scripts/test-backend.py --suite core -- -q
```

For a narrow check while developing:

```bash
cd /workspace && python3 -m pytest \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_json_fields.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py \
  -q
```
