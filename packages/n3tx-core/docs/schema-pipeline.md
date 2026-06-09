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
Stage 3: methods(cls,s)       -- Inject @expose_route signatures + stream events
Stage 4: defs(cls,s)          -- Collect referenced models into $defs
Stage 5: access(cls,s)        -- Serialize __access__ ABAC rules
Stage 6: widget(cls,s)        -- Inject ui.widget from Widget annotations [via @schema_extension, n3tx-core.widgets]
Stage 7: ui(cls,s)            -- Field exclusion, __protected_fields__ [field-level only — core]
Stage 8: viewable(cls,s)      -- Emit __ui__ class config into schema['ui'] [via @schema_extension, n3tx-ui]
Stage 9: agent(cls,s)         -- Emit agent metadata into schema['agent'] [via @schema_extension, n3tx-agents]
Stage N: metadata(cls,s)      -- Stamp $schema and $id
  |
  v
dict (JSON Schema with N3TX extensions)
```

Stages 8 (`viewable`), 9 (`agent`), and any widget stage are registered by their respective packages at import time. Only the 7 core stages (`base` through `ui`, `metadata`) are guaranteed present when running core alone.

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

## Mixin Registry

### `register_mixin(flag, mixin_cls, *, also_if=None)`

External packages register mixins for auto-injection into `ProtoModel` subclasses. Called at import time (typically in the package `__init__.py`).

```python
from n3tx_core.models.proto_model import register_mixin
from my_package.mixin import MyMixin

register_mixin('__my_flag__', MyMixin)
```

When a model class is defined with the flag set, `__init_subclass__` injects the mixin automatically:

```python
class Widget(ProtoModel):
    __my_flag__ = True
    # → MyMixin is prepended to Widget.__bases__ automatically
```

**`also_if`** — additional ClassVar names that also trigger injection, with flag normalization:

```python
# __ui__ = {...} is a guardrail: auto-sets __viewable__ = True and injects ViewableMixin
register_mixin('__viewable__', ViewableMixin, also_if=['__ui__'])
```

**Timing requirement**: `register_mixin()` must be called **before** any model with that flag is defined. Both `n3tx-ui` and `n3tx-agents` register at their `__init__.py` import time. Applications using `__agent__ = True` must `import n3tx_agents` before importing model files.

**Built-in registrations:**
- `n3tx_ui.__init__` registers `ViewableMixin` for `__viewable__` (also fires on `__ui__`)
- `n3tx_agents.__init__` registers `AgentMixin` for `__agent__`

`StorableMixin` is **not** in the registry — it's special-cased in `__init_subclass__` because it rewrites FK annotations at injection time.

---

## Typed Argument Materialization Registry

Optional packages can register runtime method-argument materializers without
making core depend on those packages.

**File**: `n3tx_core.utils.materialize`

```python
from n3tx_core.utils.materialize import register_materializer

@register_materializer
async def materialize_file(value, expected_type, *, user=None, context=None):
    if expected_type is File and isinstance(value, str):
        return True, await File.resolve(value, user=user)
    return False, value
```

`materialize_arg()` is called by direct custom-method routing, actor HTTP
method routing, and actor exposed-method dispatch. This keeps Level 1/2 and
Level 3 behavior aligned for typed capabilities.

Current built-in optional registration:

- `n3tx_files.__init__` imports `n3tx_files.materialize`, which registers a
  materializer for parameters annotated as `File`.

Rules:

- Registration happens only when the optional package is imported.
- Materializers are type-gated and should leave unrelated parameters untouched.
- Materializers may enforce authorization using the supplied `user` context.

---

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
- **`__ui__` config (`field_order`, `groups`, `renderer`, etc.) lives in the `viewable` stage** (n3tx-ui), not the `ui` stage (core). If you call `schema()` without importing `n3tx_ui`, the `ui` key will be absent from the schema. This is intentional — core has zero dependency on n3tx-ui.
- **`register_mixin()` requires pre-import.** If a model is defined before its mixin package is imported, the flag fires with an empty registry and injection is skipped silently. Always import external packages (e.g., `n3tx_agents`, `n3tx_ui`) before importing model files that use their flags.
