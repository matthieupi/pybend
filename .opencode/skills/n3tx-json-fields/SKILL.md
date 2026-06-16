---
name: n3tx-json-fields
description: N3TX JSON fields for dict/list model fields, SQLite TEXT serialization, schema/storage detection, migrations, usage tradeoffs, and relationship boundaries. Use when designing, debugging, or changing dict/list nested field persistence.
argument-hint: "<json field or nested data task>"
---

# N3TX JSON Fields

Use this skill when working with `dict`, `list`, typed list, or nested payload
fields on N3TX models.

Authoritative guide: `docs/JSON_FIELDS.md`.

## Mental model

```text
Model annotation
  -> get_json_fields(model_class)
  -> SQLite TEXT column
  -> json.dumps(value, default=str) on write
  -> json.loads(value) on read
  -> Pydantic validation / model instance
```

JSON fields are embedded data owned by the parent row. They are not independent
resources.

## Supported shapes

Stored as JSON TEXT:

```python
metadata: dict = {}
config: Optional[dict] = None
tags: list[str] = []
scores: list[int] = []
payloads: list = []
```

Not JSON fields:

```python
comments: ListRef[Comment] = []   # relationship / join table
children: list[Comment] = []      # relationship-style collection
```

## Use JSON fields for

- metadata blobs
- agent constraints/config
- primitive tag arrays
- external API payload fragments
- cache-like embedded data
- settings that do not need independent identity

## Use relationships for

- comments, likes, child resources
- anything with owner/auth requirements
- values needing `$id`, routes, lifecycle events, or pagination
- data that must be queried, updated, or rendered independently

## Implementation map

| File | Purpose |
|---|---|
| `docs/JSON_FIELDS.md` | Full developer/agent guide |
| `packages/n3tx-core/src/n3tx_core/utils/introspection.py` | `get_json_fields()` detection |
| `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` | `_coerce_value()` write path and `_deserialize_json_fields()` read path |
| `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py` | Creates/migrates JSON fields as `TEXT` |
| `packages/n3tx-core/src/n3tx_core/tests/unit/test_json_fields.py` | Round-trip and migration tests |
| `packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py` | Detection tests |

## Guardrails

- Do not turn `ListRef[T]`, many-to-many fields, or `List[BaseModel]` into JSON
  storage accidentally.
- Do not store domain relationships as arbitrary JSON arrays when N3TX should own
  identity, auth, routes, and hydration.
- Do not query or mutate SQLite JSON text directly from app feature code.
- Remember JSON-field updates replace the whole field; there is no deep merge.
- Remember `json.dumps(..., default=str)` is lossy for non-JSON-native values.

## Verification

Narrow checks:

```bash
cd /workspace && python3 -m pytest \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_json_fields.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py \
  -q
```

Core suite:

```bash
cd /workspace && python3 scripts/test-backend.py --suite core -- -q
```

## Source-reading policy

Start from `docs/JSON_FIELDS.md`. Inspect source when implementing or when docs
do not explain observed behavior. If behavior changes, update the guide and this
skill together.
