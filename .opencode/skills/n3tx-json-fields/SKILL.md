---
name: n3tx-json-fields
description: N3TX JSON fields for dict/list model fields, SQLite TEXT serialization, schema/storage detection, migrations, usage tradeoffs, and relationship boundaries. Use ONLY when designing, debugging, or changing embedded dict/list nested field persistence.
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

Relationship collections also use JSON TEXT, but store identities rather than
arbitrary embedded child data:

```python
children: list[Comment] = []      # ordered local child IDs, hydrated on reads
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

- Do not revive removed ListRef/generated joins. Distinguish JSON representation
  from relationship semantics; ManyToMany remains a separate legacy helper.
- Do not store domain relationships as arbitrary JSON arrays when N3TX should own
  identity, auth, routes, and hydration.
- Do not query or mutate SQLite JSON text directly from app feature code.
- Remember JSON-field updates replace the whole field; there is no deep merge.
- Remember `json.dumps(..., default=str)` is lossy for non-JSON-native values.

## Verification

Narrow checks:

```bash
# From the N3TX root, using the approved interpreter and package environment:
"${N3TX_PYTHON:-/workspace/.venv-agents/bin/python}" -m pytest \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_json_fields.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py \
  -q
```

Core suite:

```bash
"${N3TX_PYTHON:-/workspace/.venv-agents/bin/python}" scripts/test-backend.py --suite core -- -q
```

## Source-reading policy

Start from `docs/JSON_FIELDS.md`. Inspect source when implementing or when docs
do not explain observed behavior. If behavior changes, update the guide and this
skill together.
