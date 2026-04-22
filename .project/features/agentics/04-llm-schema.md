# AgentMixin: Replace `_build_schema_text` with LLM pipeline

**Status:** Plan
**Date:** 2026-03-14
**Depends on:** 03-hardening-and-capabilities.md
**Branch:** `v0.9`

---

## Context

`_build_schema_text()` is ~110 lines of manual translation that converts a JSON Schema into a custom text format for LLM prompts. All modern LLMs understand JSON Schema natively — this translation is unnecessary complexity. Any new schema feature requires updating this function.

**Replace with**: a named `'llm'` pipeline in `proto_schema.py`, registered from `schema_ext.py` — strips frontend-only keys, returns a clean dict that gets `json.dumps()`'d into the prompt.

## Decision: Why JSON Schema instead of text

LLMs (Claude, GPT, Llama, etc.) understand JSON Schema natively. The current `_build_schema_text` manually translates schema properties into a custom format like:
```
Fields:
  - name (string, required, 1-200 chars)
  - price (number, required, > 0, currency)
```

This is ~110 lines of code that:
- Must be manually updated when schema adds new features
- Loses information (drops defaults, descriptions, access rules detail)
- Is a custom format the LLM has never seen before

Passing the cleaned JSON Schema directly is more accurate, self-maintaining, and standard.

## Decision: Why a separate pipeline (revised)

~~Previously decided a single function was sufficient. Revised:~~ the existing `proto_schema.py` pipeline machinery already solves composable schema transformations. Adding multi-pipeline support is a small, backward-compatible change that:

1. **Reuses existing infrastructure** — same `register_stage`, `@schema_extension`, `run_pipeline` API
2. **Enables future consumers** — MCP tool schemas, documentation generators, cost estimators can each register their own pipeline
3. **Composable** — stages can be inserted between base and clean for any pipeline

The change is minimal: add a `pipeline='default'` parameter to existing functions, use a `_pipelines` dict internally. All existing code works unchanged.

---

## File: `src/n3tx/core/models/proto_schema.py`

### Add multi-pipeline support (backward compatible)

```python
# Before:
_stages: list[tuple[str, callable]] = []

# After:
_pipelines: dict[str, list[tuple[str, callable]]] = {'default': []}
_stages = _pipelines['default']  # backward compat — same list object
```

Add `pipeline='default'` parameter to all public functions:

- `_find_stage(name, pipeline='default')` — looks in named pipeline
- `register_stage(name, func, *, after=None, before=None, pipeline='default')` — auto-creates pipeline list if new
- `schema_extension(*, after=None, before=None, pipeline='default')` — passes through
- `run_pipeline(cls, pipeline='default')` — runs named pipeline
- `get_pipeline(pipeline='default')` — returns stage names
- `clear_pipeline(pipeline=None)` — None clears all, string clears specific
- `remove_stage(name, pipeline='default')` — removes from named pipeline

All existing callers pass no `pipeline` argument → default behavior unchanged.

`_stages` remains a valid reference because it's the same list object as `_pipelines['default']`. Test fixtures that save/restore `_stages` work as-is.

---

## File: `src/n3tx/core/agents/schema_ext.py`

### Register `'llm'` pipeline stages

Two stages: `base` (seed from default schema) and `clean` (strip frontend noise).

```python
from n3tx.core.models.proto_schema import schema_extension, register_stage

# Keys that are frontend-only noise for the LLM
_LLM_STRIP_KEYS = {'ui', '$id', '$schema', '__owner__', '__parent__', 'additionalProperties'}
# Method keys that are routing/frontend concerns
_METHOD_STRIP_KEYS = {'route', 'methods', 'scope', 'ui', 'access'}


def _llm_base(cls):
    """Seed LLM pipeline from the cached default schema."""
    return cls.schema()  # deep copy from cache — safe to mutate


def _llm_clean(cls, schema):
    """Strip frontend-only keys for LLM consumption.

    Removes UI hints, routing metadata, $defs, and hidden/protected
    properties. Returns a clean JSON Schema that any LLM understands.
    """
    def _strip(obj):
        if isinstance(obj, dict):
            return {k: _strip(v) for k, v in obj.items() if k not in _LLM_STRIP_KEYS}
        if isinstance(obj, list):
            return [_strip(item) for item in obj]
        return obj

    cleaned = _strip(schema)

    # Remove $defs — tool discovery provides related model schemas separately
    cleaned.pop('$defs', None)

    # Filter hidden/protected properties (check original schema's ui values)
    if 'properties' in cleaned:
        original_props = schema.get('properties', {})
        for name in list(cleaned['properties']):
            prop_ui = original_props.get(name, {}).get('ui', {})
            if prop_ui.get('display') is False or prop_ui.get('protected'):
                del cleaned['properties'][name]

    # Strip routing/frontend keys from methods, remove 'user' param
    if 'methods' in cleaned:
        for minfo in cleaned['methods'].values():
            for k in _METHOD_STRIP_KEYS:
                minfo.pop(k, None)
            params = minfo.get('parameters', {})
            params.pop('user', None)

    return cleaned


register_stage('base', _llm_base, pipeline='llm')
register_stage('clean', _llm_clean, pipeline='llm')
```

---

## File: `src/n3tx/core/agents/mixin.py`

### Replace `_build_schema_text()` body (~110 lines → ~5 lines)

```python
def _build_schema_text(cls):
    """Generate LLM context from model schema as cleaned JSON."""
    from n3tx.core.models.proto_schema import run_pipeline
    cleaned = run_pipeline(cls, pipeline='llm')
    tablename = getattr(cls, '__tablename__', cls.__name__)
    return (f'You operate on {cls.__name__} entities (table: {tablename}).\n\n'
            f'Schema:\n{json.dumps(cleaned, indent=2)}')
```

Update `ctx()` — remove unused `schema = cls.schema()` line, call `_build_schema_text(cls)` without schema param.

`_build_instance_text()` stays unchanged — it dumps instance data, not schema.

The `get_list_fields` import stays — `tools()` still uses it.

---

## No caller changes needed

`ctx()` is the only caller of `_build_schema_text()`. The signature change (drop `schema` param) is internal.

## Verification

1. Run agent mixin tests: `python3 -m pytest src/n3tx/core/agents/tests/test_mixin.py -v`
2. Run agent actor tests: `python3 -m pytest src/n3tx/core/agents/tests/test_agent_actor.py -v`
3. Run proto_schema tests: `python3 -m pytest src/n3tx/core/tests/unit/test_schema_ext.py -v`
4. Print `Product.ctx()` before/after to visually compare quality
