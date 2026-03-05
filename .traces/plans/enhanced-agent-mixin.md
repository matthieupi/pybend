# Enhanced AgentMixin: Self-Aware Models

## Context

Currently, `AgentMixin` provides a single method (`agent_run()`) that requires explicit `prompt`, `tools`, and `task` parameters. This makes the split between AgentMixin and AgentActor feel thin — the mixin is just a function wrapper around pydantic-ai.

By making the mixin auto-discover tools and generate context from the model's own schema, we create a meaningful architectural distinction:
- **AgentMixin**: "self-aware model" — any model with `__agent__ = True` can reason about itself with zero config
- **AgentActor**: "configurable orchestrator" — spans multiple models, DB-stored config

This follows N3TX philosophy: the model IS the app. Now the model is also its own agent.

## Files to Modify

| File | Change |
|------|--------|
| `src/n3tx/core/config.py` | Add `AGENT_DEFAULTS` dict |
| `src/n3tx/core/agents/mixin.py` | Add auto-context, self-tool discovery, enhanced `agent_run()` |
| `src/n3tx/core/agents/schema_ext.py` | Expose `__agent_config__` in schema |
| `src/n3tx/core/agents/tests/test_mixin.py` | New test classes for all new features |

No changes needed to: `actor.py`, `tools.py`, `deps.py`, `proto_model.py` (injection mechanism unchanged).

## Implementation Steps

### Step 1: Add `AGENT_DEFAULTS` to config.py

Add a module-level dict for global agent defaults, following the existing pattern (`BACKEND`, `HOST`, etc.):

```python
# Agent configuration (global defaults, overridable per-model via __agent_config__)
AGENT_DEFAULTS = {
    'self_tools': True,      # auto-discover own CRUD + methods
    'neighbors': False,      # auto-discover related model tools
    'neighbor_depth': 1,     # levels of ListRef relationships to follow
    'llm': 'ollama:llama3.1',
}
```

Settable via `config.configure(agent_defaults={...})` or env var `N3TX_AGENT_DEFAULTS` (JSON string).

### Step 2: Add `_build_schema_context()` to AgentMixin

Classmethod that generates a system prompt section from `cls.schema()`. Returns a string like:

```
You are a Product assistant. You manage Product entities.

## Data Model
Product has the following fields:
- name (string, required, minLength=1, maxLength=200): Product name
- price (number, required, gt=0): Product price
- description (string, optional)
- comments (array): Collection of Comment records

## Available Operations
You can list, get, create, update, and delete Product records.
Custom methods:
- comment(comment): Add a comment
- favorite(): Mark as favorite
```

Sources data from `schema['properties']`, `schema['required']`, `schema['methods']`, and `__storable__` flag. Skips hidden fields (`ui.display=False`). Reuses the schema that's already cached.

### Step 3: Add `_build_instance_context()` to AgentMixin

Instance method that adds current state to the prompt when called on an instance (not a class):

```
## Current State
You are operating on Product instance #42:
- name: Widget Pro
- price: 29.99
- description: A great widget
```

Uses `self.model_dump()`. Truncates long values to 200 chars. Returns empty string when called on a class.

### Step 4: Add `_discover_self_tools()` to AgentMixin

Classmethod that discovers tools for the model itself by calling the existing `_crud_tool_specs()` and `_method_tool_specs()` from `tools.py` directly on the class's own schema. No Matrix lookup needed — the class already has its schema.

Filters out `run` and `agent_run` methods to prevent recursive agent invocation.

```python
from n3tx.core.agents.tools import _crud_tool_specs, _method_tool_specs
```

### Step 5: Add `_discover_neighbor_tools()` to AgentMixin

Classmethod that follows `ListRef` fields one level deep using existing `get_list_fields()` from `introspection.py`. For each related model, checks if it's registered in Matrix. If found, delegates to existing `discover_tools()`.

```python
from n3tx.core.utils.introspection import get_list_fields
from n3tx.core.agents.tools import discover_tools
```

### Step 6: Enhance `agent_run()` signature and logic

**New signature** (task moves first, prompt/tools become optional):

```python
async def agent_run(self, task: str, prompt: str = None, tools: list = None,
                    user: dict = None, **kwargs) -> dict:
```

**Backward compatible**: all existing call sites use keyword args (`prompt=`, `tools=`, `task=`).

**Config resolution** (3-tier cascade):

```python
from n3tx.core import config
defaults = getattr(config, 'AGENT_DEFAULTS', {})
model_config = getattr(cls, '__agent_config__', {})
# kwargs override model_config override defaults
```

**Auto-generation logic** (at top of method, before existing adapter/tool setup):

```python
# Auto-generate prompt if not provided
if prompt is None:
    parts = []
    prefix = resolved_config.get('prompt_prefix', '')
    if prefix:
        parts.append(prefix)
    parts.append(cls._build_schema_context())
    if not isinstance(self, type):
        parts.append(self._build_instance_context())
    suffix = resolved_config.get('prompt_suffix', '')
    if suffix:
        parts.append(suffix)
    prompt = "\n".join(parts)

# Auto-discover tools if not provided
if tools is None:
    tool_specs = []
    if self_tools_enabled:
        tool_specs.extend(cls._discover_self_tools(root))
    if neighbors_enabled:
        tool_specs.extend(cls._discover_neighbor_tools(root, depth=...))
    # skip the normal discover_tools() path
else:
    # Explicit tools list — existing behavior unchanged
    tool_specs = discover_tools(tools, root)
```

### Step 7: Update schema extension

In `schema_ext.py`, include `__agent_config__` in the schema output so the frontend can see agent configuration:

```python
agent_config = getattr(cls, '__agent_config__', None)
if agent_config:
    agent_meta['config'] = dict(agent_config)
```

### Step 8: Tests

Add to `test_mixin.py`:

- **TestBuildSchemaContext**: generates model description, includes constraints, includes methods, skips hidden fields
- **TestBuildInstanceContext**: includes instance data, class-level returns empty
- **TestDiscoverSelfTools**: discovers CRUD for storable, discovers methods for non-storable, filters out `run`/`agent_run`
- **TestAutoAgentRun**: zero-config `agent_run(task=...)` works, explicit params override auto, `__agent_config__` respected, instance context included
- **TestConfigCascade**: config.py defaults < `__agent_config__` < `agent_run()` kwargs

All tests use existing `fresh_matrix`, `memory_storage` fixtures and `TestModel(call_tools=[])`.

### Step 9: Update docs

- Update CLAUDE.md agent sections to reflect the simplified API
- Update the `agent_run()` docstring

## Edge Cases Handled

- **Self-tool recursion**: `_discover_self_tools()` filters out `run` and `agent_run` from method tools
- **Backward compat**: `prompt=None` triggers auto-gen, explicit `prompt='...'` suppresses it. `tools=None` triggers auto-discovery, explicit `tools=[...]` (even empty `tools=[]`) uses the explicit list
- **AgentActor unchanged**: `AgentActor.run()` passes `prompt=self.prompt, tools=tool_addrs` — explicit params, no auto-generation kicks in
- **Class vs instance**: `_build_instance_context()` returns empty string when called on class. `_build_schema_context()` works on both.
- **Schema cache**: `cls.schema()` is already cached after first call. No performance concern.
- **Empty models**: If a model has no fields or methods, the context is minimal but valid.

## Verification

1. Run existing tests: `cd /workspace/src/n3tx/core && python3 -m pytest agents/tests/ -v` — all must pass unchanged
2. Run new tests: same command covers new test classes
3. Run integration suites: `python3 -m pytest example_grants/tests/` (uses AgentActor with explicit params)
4. Manual test: define a model with just `__agent__ = True` and `__storable__ = True`, call `await Model.agent_run(Model, task='List all records', llm=TestModel(call_tools=[]))` — should auto-discover self-tools and generate prompt
