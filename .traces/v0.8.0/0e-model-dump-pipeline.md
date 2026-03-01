# 0e model_dump as Pipeline — Design & Implementation

> Composable dump pipeline, mirroring proto_schema.

**Date**: 2026-03-01
**Status**: Implemented

## Design Decision

Instead of `model_dump(response=True)` (boolean flag bifurcating one method),
use the same composable pipeline pattern as `proto_schema`:

- `proto_dump.py` — registered stages, each `(instance, dict) → dict`
- `@dump_extension()` — add stages without modifying core
- Each stage checks its own relevance via ClassVars (e.g., `__federated__`)

**Why pipeline over separate methods:**
- Same pattern as proto_schema — one pattern to learn
- Extensions are additive (federation, MCP, agents register stages)
- Each stage is a pure transformation — testable, composable
- No proliferation of `model_dump_*()` variants

## Pipeline Stages (Wave 0)

| Stage | Input | Output | Purpose |
|-------|-------|--------|---------|
| `base` | instance | plain dict | Pydantic `model_dump()` |
| `response` | instance + dict | dict + `$schema`/`$id` | HTTP API responses |

Future stages (registered via `@dump_extension`):
- `activity` — `@context`, ActivityStreams type (federation)
- `mcp` — tool-response format (agent system)
- `audit` — audit trail fields

## API

```python
# Plain data for storage — Pydantic native, no pipeline
data = instance.model_dump()

# Enriched data via pipeline — all registered stages run
data = instance.model_response()

# Extension example (federation package):
@dump_extension(after='response')
def activity(instance, d: dict) -> dict:
    if getattr(instance.__class__, '__federated__', False):
        d['@context'] = 'https://www.w3.org/ns/activitystreams'
    return d
```

## Files Changed

| File | Change |
|------|--------|
| `models/proto_dump.py` | **NEW** — pipeline module (base + response stages) |
| `models/proto_model.py` | Removed `response=` param from `model_dump()`, added `model_response()` |
| `models/actor_model.py` | 5 calls → `model_response()` |
| `models/base_user.py` | 2 calls → `model_response()` |
| `api/routes_fastapi.py` | 3 calls → `model_response()` |
| `storage/sqlite_storage.py` | 2 calls → `model_response()` |
| `tests/unit/test_proto_model.py` | 4 calls → `model_response()` |

**Zero `model_dump(response=True)` calls remain in the codebase.**

## Tests

647 unit + 386 integration — zero regression.
