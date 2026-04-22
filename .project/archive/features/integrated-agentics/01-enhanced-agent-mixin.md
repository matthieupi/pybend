# Enhanced AgentMixin: Self-Aware Models

## Context

Currently, `AgentMixin` provides a single method (`agent_run()`) that requires explicit `prompt`, `tools`, and `task` parameters. This makes the split between AgentMixin and AgentActor feel thin — the mixin is just a function wrapper around pydantic-ai.

By making the mixin auto-discover tools and generate context from the model's own schema, we create a meaningful architectural distinction:
- **AgentMixin**: "self-aware model" — any model with `__agent__ = True` can reason about itself with zero config
- **AgentActor**: "configurable orchestrator" — spans multiple models, DB-stored config

The agent loop uses a two-method split for security and composability:
- **`run()`** — orchestration: config cascade, prompt assembly, tool discovery, adapter lifecycle, guardrails
- **`agentic()`** — pure LLM execution: receives resolved prompt, tools, deps, runs pydantic-ai

This separation lets subclasses override `run()` to add guardrails, audit logging, or rate limiting without touching LLM plumbing. Advanced users can call `agentic()` directly to bypass orchestration entirely.

This follows N3TX philosophy: the model IS the app. Now the model is also its own agent.

## Files to Modify

| File | Change |
|------|--------|
| `src/n3tx/core/utils/descriptors.py` | **New** — extract `fullmethod` and `fullproperty` descriptors |
| `src/n3tx/core/actors/actor.py` | Import from `descriptors.py`, alias `actormethod = fullmethod` / `actorproperty = fullproperty` for backward compat |
| `src/n3tx/core/config.py` | Add `AGENT_DEFAULTS` dict |
| `src/n3tx/core/agents/mixin.py` | Add `ctx`, `tools()`, `run()` + `agentic()`, `run_stream()` + `agentic_stream()` using `fullproperty`/`fullmethod` |
| `src/n3tx/core/agents/schema_ext.py` | Expose `__agent__` config in schema |
| `src/n3tx/core/agents/tests/test_mixin.py` | New test classes for all new features |

No changes needed to: `tools.py`, `deps.py`, `proto_model.py` (injection mechanism unchanged).

**Streaming integration note:** The framework now has full SSE streaming support (`@expose_route(stream=True)`, `TX.stream_chunk()`/`stream_end()`, `NetworkAdapter.stream()`, `_sse_from_stream()`, `<ntx-stream>` component). The enhanced mixin leverages this for `agentic_stream()` — a streaming counterpart to `agentic()` that yields LLM output and tool call progress as SSE chunks.

## Implementation Steps

### Step 0: Extract `fullmethod` / `fullproperty` descriptors

`actormethod` and `actorproperty` in `actor.py` are pure Python descriptors with zero Actor dependencies — they work on any class. Now that AgentMixin needs them too, extract to a shared location and rename to reflect their general scope.

**New file: `src/n3tx/core/utils/descriptors.py`**

```python
"""Descriptors for unified class/instance dispatch.

fullmethod  — a method where the first param receives cls or self
fullproperty — a property that resolves class or instance state

These work on any class, not just Actors. The descriptor protocol
dispatches based on how they're accessed:

    MyClass.thing   → __get__(None, MyClass) → fn(MyClass)
    instance.thing  → __get__(instance, type) → fn(instance)
"""

from types import MethodType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TypeVar
    _F = TypeVar('_F')

    def fullmethod(fn: _F) -> _F: ...
    def fullproperty(fn: _F) -> _F: ...
else:
    class fullmethod:
        """A method that works on both classes and instances.

        The first parameter receives the class (when called as cls.method())
        or the instance (when called as self.method()). One function, one
        implementation.
        """
        def __init__(self, fn):
            self.fn = fn
            self.__doc__ = fn.__doc__
            self.__name__ = fn.__name__

        def __set_name__(self, owner, name):
            self.__name__ = name

        def __get__(self, obj, cls=None):
            target = obj if obj is not None else cls
            return MethodType(self.fn, target)

    class fullproperty:
        """A property that works on both classes and instances.

        The function receives the class or instance and returns a value
        directly — not a callable.
        """
        def __init__(self, fn):
            self.fn = fn
            self.__doc__ = fn.__doc__

        def __set_name__(self, owner, name):
            self.__name__ = name

        def __get__(self, obj, cls=None):
            target = obj if obj is not None else cls
            return self.fn(target)
```

**Update `src/n3tx/core/actors/actor.py`:**

Replace the inline descriptor definitions with imports and backward-compat aliases:

```python
from n3tx.core.utils.descriptors import fullmethod, fullproperty

# Backward compatibility — existing code uses these names
actormethod = fullmethod
actorproperty = fullproperty
```

The `TYPE_CHECKING` block in `actor.py` that defines stubs for `actormethod`/`actorproperty` is also replaced by the stubs in `descriptors.py`. All existing `@actormethod` / `@actorproperty` decorators in `actor.py` continue to work via the aliases.

### Step 1: Add `AGENT_DEFAULTS` to config.py

Add a module-level dict for global agent defaults, following the existing pattern (`BACKEND`, `HOST`, etc.):

```python
# Agent configuration (global defaults, overridable per-model via __agent__)
AGENT_DEFAULTS = {
    'self_tools': True,      # auto-discover own CRUD + methods
    'neighbors': False,      # auto-discover related model tools
    'neighbor_depth': 1,     # levels of ListRef relationships to follow
    'llm': 'ollama:llama3.1',
}
```

Settable via `config.configure(agent_defaults={...})` or env var `N3TX_AGENT_DEFAULTS` (JSON string).

**`__agent__` is dual-purpose** — it serves as both the injection flag and the config dict:

```python
# Default config (boolean — all defaults from config.AGENT_DEFAULTS)
class Product(ActorModel):
    __agent__ = True

# Custom config (dict — merged over defaults)
class Product(ActorModel):
    __agent__ = {
        'self_tools': True,
        'neighbors': True,
        'llm': 'anthropic:claude-sonnet-4-5-20250929',
        'prompt_prefix': 'You are a product expert.',
    }
```

The injection check in `proto_model.py` already uses `getattr(cls, '__agent__', False)` — a truthy dict passes naturally. Config resolution:

```python
agent_flag = getattr(cls, '__agent__', False)
agent_config = agent_flag if isinstance(agent_flag, dict) else {}
```

### Step 2: Add `ctx` to AgentMixin (via `fullproperty`)

A `fullproperty` that auto-generates LLM context from the model's schema. Class vs instance dispatch is handled by the descriptor — one definition, two behaviors:

```python
from n3tx.core.utils.descriptors import fullproperty, fullmethod

class AgentMixin:

    @fullproperty
    def ctx(target) -> str:
        """Agent context. Class: schema context. Instance: schema + instance data."""
        cls = target if isinstance(target, type) else target.__class__
        schema = cls.schema()
        context = _schema_ctx(schema, cls)
        if not isinstance(target, type):
            context += _instance_ctx(target, schema)
        return context
```

| Access | Result |
|--------|--------|
| `Product.ctx` | Schema description: fields, types, constraints, methods |
| `product.ctx` | Schema description + current instance state |

**`_schema_ctx(schema, cls)`** (module-level helper) generates:

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

**`_instance_ctx(target, schema)`** (module-level helper) appends:

```
## Current State
You are operating on Product instance #42:
- name: Widget Pro
- price: 29.99
- description: A great widget
```

Uses `target.model_dump()`. Truncates long values to 200 chars.

### Step 3: Add `tools()` to AgentMixin (via `fullmethod`)

A `fullmethod` that auto-discovers tools from the model's own schema. Works on class or instance (tools are the same either way — they come from the schema, not instance state).

```python
class AgentMixin:

    @fullmethod
    def tools(target, root=None) -> list:
        """Discover self-tools from model schema. Returns list of ToolSpec."""
        cls = target if isinstance(target, type) else target.__class__
        if root is None:
            from n3tx.core.actors.actor import Actor
            root = Actor.root()
        return _discover_self_tools(cls, root)
```

| Access | Result |
|--------|--------|
| `Product.tools(root)` | CRUD + method ToolSpecs for Product |
| `product.tools(root)` | Same (tools come from schema, not instance) |
| `Product.tools()` | Auto-resolves root from `Actor.root()` |

**`_discover_self_tools(cls, root)`** (module-level helper) calls existing `_crud_tool_specs()` and `_method_tool_specs()` from `tools.py` directly on the class's own schema. Filters out `run` and `agentic` methods to prevent recursive agent invocation.

### Step 4: Add `_discover_neighbor_tools()` to AgentMixin

Module-level helper that follows `ListRef` fields one level deep using existing `get_list_fields()` from `introspection.py`. For each related model, checks if it's registered in Matrix. If found, delegates to existing `discover_tools()`.

```python
from n3tx.core.utils.introspection import get_list_fields
from n3tx.core.agents.tools import discover_tools
```

### Step 6: Split into `run()` (orchestration) and `agentic()` (execution)

The agent loop is split into two methods with distinct responsibilities:

| Concern | `run()` (orchestration) | `agentic()` (execution) |
|---------|------------------------|------------------------|
| Config cascade (3-tier) | Yes | No — receives resolved config |
| Prompt assembly (`self.ctx` + prefix/suffix) | Yes | No — receives final prompt |
| Tool discovery (`self.tools()` + neighbors) | Yes | No — receives final tool list |
| Adapter lifecycle (create/cleanup) | Yes | No — receives adapter |
| Guardrails / validation | Yes | No |
| LLM call (pydantic-ai Agent) | No | Yes |
| Result formatting | No | Yes |

**Why two methods?**
- **Security**: `agentic()` is a pure executor with no config resolution — subclasses can override `run()` to add guardrails, audit logging, or rate limiting without touching LLM plumbing
- **Composability**: `run()` can be called with zero args (full auto-discovery) or with explicit overrides. `agentic()` can be called directly by advanced users who want to bypass the orchestration layer entirely
- **Testability**: `agentic()` is easy to unit test (pass prompt + tools, get result). `run()` tests cover config cascade and discovery logic independently

#### `run()` — orchestration

```python
async def run(self, task: str, prompt: str = None, tools: list = None,
              user: dict = None, **kwargs) -> dict:
    """Orchestrate an agent run: resolve config, build prompt, discover tools, execute.

    Config resolution (3-tier cascade):
        config.AGENT_DEFAULTS < __agent__ dict < run() kwargs
    """
    # ── Config cascade ──
    from n3tx.core import config
    defaults = getattr(config, 'AGENT_DEFAULTS', {})
    agent_flag = getattr(self.__class__, '__agent__', False)
    model_config = agent_flag if isinstance(agent_flag, dict) else {}
    resolved = {**defaults, **model_config, **kwargs}

    # ── Prompt assembly ──
    if prompt is None:
        parts = []
        prefix = resolved.get('prompt_prefix', '')
        if prefix:
            parts.append(prefix)
        parts.append(self.ctx)  # fullproperty: schema + instance context
        suffix = resolved.get('prompt_suffix', '')
        if suffix:
            parts.append(suffix)
        prompt = "\n".join(parts)

    # ── Tool discovery ──
    from n3tx.core.actors.actor import Actor
    root = Actor.root()
    if tools is None:
        tool_specs = []
        if resolved.get('self_tools', True):
            tool_specs.extend(self.tools(root))
        if resolved.get('neighbors', False):
            tool_specs.extend(_discover_neighbor_tools(
                self.__class__, root, depth=resolved.get('neighbor_depth', 1)
            ))
    else:
        # Explicit tools list — existing behavior unchanged
        from n3tx.core.agents.tools import discover_tools
        tool_specs = discover_tools(tools, root)

    # ── Adapter lifecycle ──
    adapter = _create_transient_adapter(root)
    try:
        return await self.agentic(
            task=task, prompt=prompt, tool_specs=tool_specs,
            adapter=adapter, user=user, llm=resolved.get('llm'),
            **{k: v for k, v in resolved.items()
               if k not in ('self_tools', 'neighbors', 'neighbor_depth',
                            'prompt_prefix', 'prompt_suffix', 'llm')}
        )
    finally:
        _cleanup_adapter(root, adapter)
```

#### `agentic()` — pure LLM execution

```python
async def agentic(self, task: str, prompt: str, tool_specs: list,
                  adapter=None, user: dict = None,
                  llm: str = None, **kwargs) -> dict:
    """Execute the LLM agent loop. Pure execution — no config resolution.

    Receives fully resolved prompt, tools, and adapter from run().
    Can also be called directly for advanced use cases.
    """
    from pydantic_ai import Agent, UsageLimits
    from n3tx.core.agents.tools import make_tool
    from n3tx.core.agents.deps import AgentDeps

    pydantic_tools = [make_tool(spec, adapter) for spec in tool_specs]
    deps = AgentDeps(user=user, adapter=adapter)
    llm = llm or 'ollama:llama3.1'

    ai_agent = Agent(llm, system_prompt=prompt, tools=pydantic_tools, deps_type=AgentDeps)
    usage_limits = UsageLimits(request_limit=kwargs.get('request_limit', 10))

    result = await ai_agent.run(task, deps=deps, usage_limits=usage_limits)
    return {
        'output': result.output,
        'usage': {
            'input_tokens': result.usage().input_tokens,
            'output_tokens': result.usage().output_tokens,
        }
    }
```

**Backward compatibility**: `AgentActor.run()` currently calls `self.agent_run(prompt=..., tools=..., task=...)`. After rename, it calls `self.agentic(task=..., prompt=..., tool_specs=...)` — passing explicit prompt and tools, so the orchestration layer (`run()`) is bypassed. AgentActor keeps full control over its own config.

### Step 7: Add `run_stream()` and `agentic_stream()` to AgentMixin

Same two-method split as `run()` / `agentic()`, but for streaming:

- **`run_stream()`** — orchestration (config cascade, prompt, tools, adapter lifecycle), delegates to `agentic_stream()`
- **`agentic_stream()`** — pure LLM streaming execution via pydantic-ai's `Agent.iter()` API

#### `run_stream()` — streaming orchestration

```python
async def run_stream(self, task: str, prompt: str = None, tools: list = None,
                     user: dict = None, **kwargs):
    """Streaming orchestration — same config cascade as run(), yields SSE chunks."""
    # ... identical config cascade, prompt assembly, tool discovery as run() ...
    adapter = _create_transient_adapter(root)
    try:
        async for chunk in self.agentic_stream(
            task=task, prompt=prompt, tool_specs=tool_specs,
            adapter=adapter, user=user, llm=resolved.get('llm'), **filtered_kwargs
        ):
            yield chunk
    finally:
        _cleanup_adapter(root, adapter)
```

#### `agentic_stream()` — pure streaming execution

```python
async def agentic_stream(self, task: str, prompt: str, tool_specs: list,
                         adapter=None, user: dict = None,
                         llm: str = None, **kwargs):
    """Streaming agent loop — yields chunks as the LLM generates output.

    Pure execution — no config resolution. Receives resolved params.
    Yields dicts suitable for SSE: {type, data} where type is one of:
    - 'text': LLM text output chunk
    - 'tool_call': tool being called {name, args}
    - 'tool_result': tool result {name, result}
    - 'usage': final usage stats
    """
    from pydantic_ai import Agent, UsageLimits
    from n3tx.core.agents.tools import make_tool
    from n3tx.core.agents.deps import AgentDeps

    pydantic_tools = [make_tool(spec, adapter) for spec in tool_specs]
    deps = AgentDeps(user=user, adapter=adapter)
    llm = llm or 'ollama:llama3.1'

    ai_agent = Agent(llm, system_prompt=prompt, tools=pydantic_tools, deps_type=AgentDeps)
    usage_limits = UsageLimits(request_limit=kwargs.get('request_limit', 10))

    async with ai_agent.iter(task, deps=deps, usage_limits=usage_limits) as run:
        async for node in run:
            if Agent.is_model_request_node(node):
                yield {'type': 'thinking', 'data': {}}
            elif Agent.is_call_tools_node(node):
                for call in node.tool_calls:
                    yield {'type': 'tool_call', 'data': {'name': call.tool_name, 'args': call.args}}
            elif Agent.is_end_node(node):
                yield {'type': 'text', 'data': {'content': run.result.output}}

    usage = run.result.usage()
    yield {'type': 'usage', 'data': {
        'input_tokens': usage.input_tokens,
        'output_tokens': usage.output_tokens,
        'requests': usage.requests,
    }}
```

**Usage in models:**

```python
class Product(ActorModel):
    __agent__ = True
    __storable__ = True

    @expose_route('/analyze', methods=['POST'], stream=True)
    async def analyze(self, query: str):
        async for chunk in self.run_stream(task=query):  # full auto-discovery
            yield chunk
```

This plugs directly into the existing streaming stack:
- Level 1/2: `routes_fastapi.py` detects async generator → `StreamingResponse` with SSE
- Level 3: `actor_model.py` handler detects async generator → `tx.stream_chunk()` per yield → `_sse_from_stream()`
- Frontend: `<ntx-stream>` renders progressive output via `HTTP.stream()`

**AgentActor integration:** `AgentActor.run()` stays non-streaming (calls `self.agentic()` directly). A future `AgentActor.stream()` `@expose_route(stream=True)` method could delegate to `self.agentic_stream()` for streaming agent execution via API.

### Step 8: Update schema extension

In `schema_ext.py`, include `__agent__` config in the schema output so the frontend can see agent configuration:

```python
agent_flag = getattr(cls, '__agent__', False)
if isinstance(agent_flag, dict):
    agent_meta['config'] = dict(agent_flag)
```

### Step 9: Tests

Add to `test_mixin.py`:

- **TestCtx**: `Product.ctx` returns schema context (fields, types, methods). `product.ctx` returns schema + instance data. Includes constraints, skips hidden fields.
- **TestTools**: `Product.tools()` discovers CRUD for storable. Discovers methods for non-storable. Filters out `run`/`agentic`/streaming methods.
- **TestRun**: zero-config `run(task=...)` auto-discovers prompt from `self.ctx` and tools from `self.tools()`. `__agent__` dict config respected. Config cascade works (defaults < model < kwargs). Adapter lifecycle (create + cleanup).
- **TestAgentic**: direct `agentic(task=..., prompt=..., tool_specs=...)` call works with explicit params. No config resolution occurs. Returns `{output, usage}` dict.
- **TestRunVsAgentic**: `run()` delegates to `agentic()` with resolved params. Overriding `run()` in subclass adds guardrails without touching `agentic()`. Direct `agentic()` call bypasses `run()` entirely.
- **TestConfigCascade**: config.py defaults < `__agent__` dict < `run()` kwargs
- **TestRunStream**: `run_stream()` yields dicts, handles adapter lifecycle, works with auto-discovery (no explicit prompt/tools)
- **TestAgenticStream**: `agentic_stream()` yields dicts with `type` field, includes tool_call/text/usage types

All tests use existing `fresh_matrix`, `memory_storage` fixtures and `TestModel(call_tools=[])`.

### Step 10: Update docs

- Update CLAUDE.md agent sections to reflect the simplified API and streaming
- Update the `agentic()` and `agentic_stream()` docstrings

## Edge Cases Handled

- **Self-tool recursion**: `tools()` filters out `run`, `agentic`, and streaming delegate methods from method tools
- **Backward compat**: `AgentActor.run()` calls `self.agentic()` directly with explicit prompt and tool_specs — bypasses the `run()` orchestration layer entirely. Existing tests that call `agent_run(prompt=..., tools=..., task=...)` map cleanly to the new `agentic(task=..., prompt=..., tool_specs=...)` signature
- **Direct `agentic()` call**: Advanced users can call `agentic()` directly, bypassing config cascade and auto-discovery. This is the "escape hatch" for full control
- **Zero-arg `run()`**: `run(task='...')` with no other args triggers full auto-discovery — prompt from `self.ctx`, tools from `self.tools()`, config from cascade
- **Class vs instance**: `ctx` is a `fullproperty` — `Product.ctx` returns schema-only context, `product.ctx` returns schema + instance data. No branching needed at call sites
- **Schema cache**: `cls.schema()` is already cached after first call. No performance concern
- **Empty models**: If a model has no fields or methods, the context is minimal but valid
- **Stream cleanup**: `run_stream()` uses try/finally to ensure transient adapter removal even if consumer abandons the generator mid-stream
- **Stream + existing stack**: `agentic_stream()` yields plain dicts — the existing streaming infrastructure (`actor_model.py` handler → `tx.stream_chunk()` → `_sse_from_stream()` → `<ntx-stream>`) handles the rest. No new wire protocol
- **Security boundary**: `run()` is the only place where config is resolved — subclasses can override it to add guardrails, audit logging, rate limiting, or approval gates without touching LLM plumbing in `agentic()`

## Streaming Integration

The enhanced mixin integrates with the existing streaming stack at the right level:

```
agentic_stream() yields dicts
    ↓
@expose_route(stream=True) method yields them
    ↓
Level 1/2: routes_fastapi.py → StreamingResponse (SSE)
Level 3:   actor_model.py → tx.stream_chunk() → NetworkAdapter → _sse_from_stream()
WebSocket: network_ws.py → _stream_to_ws()
    ↓
Frontend: HTTP.stream() → <ntx-stream> renders progressive output
```

**Key files in the streaming stack** (no modifications needed — agentic_stream plugs in):
- `src/n3tx/core/utils/decorators.py` — `expose_route(stream=True)`
- `src/n3tx/core/actors/tx.py` — `stream_chunk()`, `stream_end()`
- `src/n3tx/core/api/routes_fastapi.py` — async generator → SSE detection
- `src/n3tx/core/api/network_api.py` — `_add_streaming_handler()`, `_sse_from_stream()`
- `src/n3tx/core/api/network_adapter.py` — `stream()` with Queue correlation
- `src/n3tx/core/models/actor_model.py` — handler async generator detection
- `src/n3tx/static/components/ntx-stream.js` — `<ntx-stream>` progressive renderer
- `src/n3tx/static/core/transport/HTTP.js` — `HTTP.stream()` SSE client

## Verification

1. Run existing tests: `cd /workspace/src/n3tx/core && python3 -m pytest agents/tests/ -v` — all must pass unchanged
2. Run new tests: same command covers new test classes
3. Run integration suites: `python3 -m pytest example_grants/tests/` (uses AgentActor with explicit params)
4. Run streaming tests: `python3 -m pytest example_actor/tests/test_streaming.py -v` — ensure streaming stack still works
5. Manual test: define a model with `__agent__ = True`, `__storable__ = True`, and a `@expose_route(stream=True)` method that delegates to `self.agentic_stream(task=query)` — verify SSE chunks flow to `<ntx-stream>` frontend
