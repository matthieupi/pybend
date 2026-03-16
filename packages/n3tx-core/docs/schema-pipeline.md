# Schema Pipeline

> Part of [n3tx-core](../README.md)

## What This Covers

The composable pipeline that generates JSON Schema from model classes. Covers the default stages, the extension mechanism, and how external packages add stages without modifying core. Does not cover the dump pipeline (see [storage.md](storage.md)) or the frontend schema consumption (see n3tx-ui docs).

## Architecture

```
ProtoModel.schema()
  |
  v
proto_schema.run_pipeline(cls, pipeline='default')
  |
  v
Stage 1: base(cls)           -- Pydantic model_json_schema() + Ref patching
Stage 2: strip_hidden(cls,s)  -- Remove __hidden_fields__
Stage 3: methods(cls,s)       -- Inject @expose_route signatures
Stage 4: defs(cls,s)          -- Collect referenced models into $defs
Stage 5: access(cls,s)        -- Serialize __access__ ABAC rules
Stage 6: widget(cls,s)        -- Inject ui.widget from Widget annotations [via @schema_extension]
Stage 7: ui(cls,s)            -- Field exclusion, __protected_fields__, __ui__ config
Stage 8: metadata(cls,s)      -- Stamp $schema and $id
  |
  v
dict (JSON Schema with N3TX extensions)
```

Each stage is a pure `dict -> dict` function. The first stage (`base`) takes only `cls` and returns the seed dict. All subsequent stages take `(cls, schema)` and return the modified schema.

Results are cached per model class in `ProtoModel._schema_cache`. Call `cls.invalidate_schema_cache()` to clear (tests only -- schemas are immutable at runtime).

## Interface

### Pipeline Registration

```python
from n3tx_core.models.proto_schema import register_stage, schema_extension

# Imperative registration
register_stage('federation', federation_stage, after='methods')

# Decorator registration (stage name = function name)
@schema_extension(after='methods')
def federation(cls, schema: dict) -> dict:
    if getattr(cls, '__federated__', False):
        schema['federation'] = {'inbox': f'/api/{cls.__tablename__}/inbox'}
    return schema
```

**`register_stage(name, func, *, after=None, before=None, pipeline='default')`**

| Param | Type | Description |
|-------|------|-------------|
| `name` | str | Unique stage name within the pipeline |
| `func` | callable | `(cls) -> dict` for seed, `(cls, schema) -> dict` for transforms |
| `after` | str | Insert after this named stage |
| `before` | str | Insert before this named stage |
| `pipeline` | str | Pipeline name (default: `'default'`) |

Raises `ValueError` if: duplicate stage name, both `after` and `before` specified, or referenced stage not found.

**`schema_extension(*, after=None, before=None, pipeline='default')`** -- Decorator form. Function name becomes the stage name.

### Pipeline Introspection

```python
from n3tx_core.models.proto_schema import get_pipeline, clear_pipeline, remove_stage

get_pipeline()          # -> ['base', 'strip_hidden', 'methods', ...]
get_pipeline('llm')     # -> stages for a custom pipeline
remove_stage('widget')  # Remove a stage by name
clear_pipeline()        # Clear all pipelines (testing only)
```

### Named Pipelines

Multiple pipelines can coexist. The `'default'` pipeline produces the full frontend schema. A separate `'llm'` pipeline could produce a stripped-down schema for AI consumption.

```python
register_stage('base', llm_base, pipeline='llm')
register_stage('fields', llm_fields, pipeline='llm')
result = run_pipeline(cls, pipeline='llm')
```

## Usage Patterns

### Adding a ClassVar-Driven Feature

The canonical extension pattern: a model sets a ClassVar flag, the schema stage reads it.

```python
# In your package's schema_ext.py
from n3tx_core.models.proto_schema import schema_extension

@schema_extension(after='methods')
def agent(cls, schema: dict) -> dict:
    agent_config = getattr(cls, '__agent__', False)
    if not agent_config:
        return schema
    schema['agent'] = {
        'enabled': True,
        'config': agent_config if isinstance(agent_config, dict) else {},
    }
    return schema
```

The import of this module triggers registration. Ensure it is imported before any `schema()` call (typically via your package's `__init__.py`).

### Injecting Into $defs

The `defs` stage collects all referenced models. To enrich $defs entries, insert your stage after `defs`:

```python
@schema_extension(after='defs')
def enrich_defs(cls, schema: dict) -> dict:
    for name, def_schema in schema.get('$defs', {}).items():
        def_schema['custom'] = 'value'
    return schema
```

## Gotchas

- **Stage names must be unique per pipeline.** Duplicate registration raises `ValueError`. Check `get_pipeline()` before registering if your package might be imported multiple times.
- **Import order matters.** Extensions registered via `@schema_extension` run at import time. If your extension module is not imported before `ProtoModel.schema()` is called, the stage will be missing. Put the import in your package `__init__.py`.
- **Schemas are cached.** Once `schema()` is called for a model class, the result is cached. Extensions registered after the first call will not affect cached schemas. Call `cls.invalidate_schema_cache()` in tests.
- **The `base` stage patches Ref fields.** Pydantic serializes `Ref[T]` as `{"type": "integer"}`. The `base` stage patches these back to `{"type": "$ref", "$ref": "#/$defs/{TargetName}"}`. If you add a stage that reads field types, account for this patching.
- **`_apply_field_exclusion` auto-hides `id`, `image`, `created_at`, `updated_at`, and `*_id` fields** by setting `ui.display = false`. Existing `display` values are preserved -- only unset fields get the default.
- **The `widget` stage is registered by `n3tx_core.widgets`** (via `@schema_extension(before='ui')`). It runs only if the widgets package is imported. The default pipeline includes it because `n3tx_core.widgets.__init__` imports `schema_ext`.
