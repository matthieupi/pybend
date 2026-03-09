# Enhanced AgentMixin v2: Self-Aware Models — Unified Plan

**Status:** Plan (approved)
**Date:** 2026-03-08
**Synthesizes:** `01-enhanced-agent-mixin.md` (Plan 01) + `02-agent-mixin-proposal.md` (Plan 02)
**Base:** Plan 02 structure with Plan 01's 3-tier config cascade and TX-aligned streaming chunks

---

## Context

`__storable__ = True` gives a model zero-config persistence. But `__agent__ = True` gives almost nothing — just `agent_run()` requiring manual prompt, tools, and task. The goal: make `__agent__ = True` as powerful as `__storable__ = True`. One flag, zero config, the model reasons about itself.

### Design Decisions

| Decision | Source | Rationale |
|----------|--------|-----------|
| `ctx()` as `@fullmethod` (callable) | Plan 02 | Extensible for future `format=` param |
| `tools()` returns `list[str]` (addresses) | Plan 02 | Lightweight, composable, deferred resolution |
| `__agent__['prompt']` prepend in `ctx()` | Plan 02 | Config-driven prompt composition |
| Token-level streaming via `node.stream()` | Plan 02 | True progressive output |
| 3-tier config cascade | Plan 01 | Site-wide defaults via `config.AGENT_DEFAULTS` |
| Separate `agentic_stream()` method | Plan 01 | No union return types |
| Explicit adapter lifecycle | Plan 01 | Testability + stream cleanup |
| Self-tool recursion guard | Plan 01 | `discover_tools(caller_addr=)` already handles |
| TX-aligned chunk format (full parity) | Hybrid | `name` + `data` + `meta` mirrors TX fields |

### Split Justified

| | AgentMixin ("self-aware model") | AgentActor ("orchestrator agent") |
|---|---|---|
| **Tools** | Auto: own CRUD + methods + neighbor models | Configured: any models, stored in DB |
| **Prompt** | Auto: generated from schema metadata | Stored in DB, fully custom |
| **Config** | Derived from model definition | Data — user-editable at runtime |
| **Streaming** | Built-in via `run_stream()` | Same, delegates to mixin |
| **Use case** | "Product, analyze yourself" | "Agent, coordinate across Products, Sources, Grants" |
| **Entry point** | `self.run(task=...)` | `POST /agents/{id}/run` → overridden `run()` |
| **Persistence** | No agent config to store — it IS the model | Agent config lives in DB rows |

---

## New API Surface

| Method | Type | Role |
|--------|------|------|
| `ctx()` | `@fullmethod` | Build LLM context (schema on class, schema+data on instance) |
| `tools()` | `@fullmethod` | Discover tool addresses (self + neighbors + extras) |
| `run()` | `@fullmethod` | **Policy** — config cascade, prompt/tool assembly, adapter lifecycle |
| `agentic()` | instance method | **Engine** — raw LLM loop, explicit params, no config magic |
| `run_stream()` | `@fullmethod` | Streaming policy (delegates to `agentic_stream()`) |
| `agentic_stream()` | instance method | Streaming engine — yields TX-aligned chunks |

The split: `run()` is the boundary where you enforce constraints and resolve config. `agentic()` is the engine that just works. You expose `run()` via HTTP, never `agentic()` directly.

```python
# Actor pattern (existing):
Product.addr       # 'products'        (class)
product.addr       # 'products/1'      (instance)

# AgentMixin pattern (new):
Product.ctx()      # schema context          (class)
product.ctx()      # schema + instance data  (instance)
Product.tools()    # ['products', 'comments'] (class)
product.tools()    # ['products', 'comments'] (instance — same)
Product.run(task=...) # resolves config, calls agentic()  (class)
product.run(task=...) # same, with instance context        (instance)
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/n3tx/core/utils/descriptors.py` | **NEW** — `fullmethod`, `fullproperty` descriptors |
| `src/n3tx/core/actors/actor.py` | Import from descriptors, alias `actormethod`/`actorproperty` |
| `src/n3tx/core/config.py` | Add `AGENT_DEFAULTS` dict |
| `src/n3tx/core/agents/mixin.py` | **Major** — rename + add ctx, tools, run, run_stream, agentic_stream |
| `src/n3tx/core/agents/actor.py` | Update `agent_run` → `agentic` call site |
| `src/n3tx/core/agents/schema_ext.py` | Expose `__agent__` config in schema |
| `src/n3tx/core/agents/tests/test_mixin.py` | **Major** — new TestCtx, TestTools, TestRun, TestStream classes |
| `src/n3tx/core/agents/tests/test_agent_actor.py` | Update `agent_run` refs |
| `CLAUDE.md` | Document new APIs |

**NOT changed:** `tools.py`, `deps.py`, `proto_model.py`, `actor_model.py`, `routes_fastapi.py`, `network_adapter.py`, `ntx-stream.js`

---

## Implementation Steps

### Step 0: Extract `fullmethod`/`fullproperty` to `utils/descriptors.py`

**Create** `src/n3tx/core/utils/descriptors.py` with the exact descriptor classes currently defined inline in `actor.py` (lines ~82-137), renamed `actormethod` → `fullmethod`, `actorproperty` → `fullproperty`. Include the same `TYPE_CHECKING` passthrough for IDE support.

```python
# src/n3tx/core/utils/descriptors.py
"""Descriptors for unified class/instance dispatch.

fullmethod  — a method where the first param receives cls or self
fullproperty — a property that resolves class or instance state

These work on any class, not just Actors.
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
        def __init__(self, fn):
            self.fn = fn
            self.__doc__ = fn.__doc__

        def __set_name__(self, owner, name):
            self.__name__ = name

        def __get__(self, obj, cls=None):
            target = obj if obj is not None else cls
            return self.fn(target)
```

**Update** `src/n3tx/core/actors/actor.py`:
```python
from n3tx.core.utils.descriptors import fullmethod, fullproperty
actormethod = fullmethod      # backward compat
actorproperty = fullproperty  # backward compat
```

Remove the inline class definitions and TYPE_CHECKING block. All `@actormethod`/`@actorproperty` decorators and `model_config = ConfigDict(ignored_types=(actormethod, actorproperty))` continue to work via aliases (identity check passes).

### Step 1: Add `AGENT_DEFAULTS` to `config.py`

```python
# Agent configuration (global defaults, overridable per-model via __agent__)
AGENT_DEFAULTS = {
    'self_tools': True,       # auto-discover own CRUD + methods
    'neighbors': True,        # auto-discover ListRef neighbor tools
    'neighbor_depth': 1,      # levels of ListRef relationships to follow
    'llm': 'ollama:llama3.1', # default LLM provider:model string
}

if os.getenv("N3TX_AGENT_DEFAULTS"):
    import json as _json
    AGENT_DEFAULTS.update(_json.loads(os.environ["N3TX_AGENT_DEFAULTS"]))
```

`__agent__` is dual-purpose — both the injection flag and the config dict:
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
        'prompt': 'You are a product expert.',
    }
```

### Step 2: Rename `agent_run()` → `agentic()`

Rename in `mixin.py`, reorder params (`task` first):
```python
# Before: agent_run(self, prompt, tools, task, user, **kwargs)
# After:  agentic(self, task, prompt, tools, user, **kwargs)
```

Update call site in `actor.py` and all test references.

### Step 3: Add `ctx()` fullmethod

```python
@fullmethod
def ctx(target) -> str:
    """Build LLM context from model schema.

    Class:    Product.ctx()  → schema context (fields, types, methods)
    Instance: product.ctx() → schema context + current instance data

    If __agent__['prompt'] is set, it is prepended to the auto-generated context.
    """
    cls = target if isinstance(target, type) else target.__class__
    agent_flag = getattr(cls, '__agent__', False)
    conf = agent_flag if isinstance(agent_flag, dict) else {}
    schema = cls.schema()

    context = _build_schema_text(cls, schema)

    # Prepend __agent__['prompt'] if configured
    prompt_prefix = conf.get('prompt', '')
    if prompt_prefix:
        context = prompt_prefix + '\n\n' + context

    # Instance context: append current state
    if not isinstance(target, type):
        context += _build_instance_text(target)

    return context
```

Module-level helpers:
- **`_build_schema_text(cls, schema)`** — generates text from:
  - Model identity: `cls.__name__`, `cls.__tablename__`
  - Fields from `schema['properties']`: name, type, required, constraints (minLength, maxLength, gt, etc.), widget hints. Skips `ui.display=False` fields. Marks protected fields.
  - Relationships from `get_list_fields(cls)`: field name and target model name
  - Access rules from `schema['access']`: human-readable strings
  - Methods from `schema['methods']`: name, params, return type, scope, stream flag

- **`_build_instance_text(target)`** — appends `model_dump()` with values truncated to 200 chars

**Example output for `Product.ctx()`:**
```
You operate on Product entities (table: products).

Fields:
  - name (string, required, 1-200 chars): Product name
  - price (number, required, > 0, currency format)
  - description (string, optional, textarea)

Relationships:
  - comments → Comment (list)

Access rules:
  - read: anyone
  - create: authenticated users
  - update: resource owner only
  - delete: admin role only

Available methods:
  - comment(comment: Comment) → string [instancemethod]
```

**`product.ctx()` appends:**
```
Current instance (id=42):
{
  "name": "Widget Pro",
  "price": 29.99,
  "description": "A professional widget"
}
```

### Step 4: Add `tools()` fullmethod

```python
@fullmethod
def tools(target) -> list:
    """Discover tool actor addresses for this model.

    Returns list[str] of actor addresses. Tool resolution (addr → ToolSpec)
    is deferred to agentic() where discover_tools() is called.

    Product.tools()  → ['products', 'comments']
    product.tools()  → same (tools come from schema, not instance)
    """
    cls = target if isinstance(target, type) else target.__class__
    agent_flag = getattr(cls, '__agent__', False)
    conf = agent_flag if isinstance(agent_flag, dict) else {}

    addrs = []

    # Self tools (own CRUD + methods)
    if conf.get('self_tools', True):
        tablename = getattr(cls, '__tablename__', cls.__name__)
        addrs.append(tablename)

    # Neighbor tools (ListRef relationships)
    if conf.get('neighbors', True):
        from n3tx.core.utils.introspection import get_list_fields
        for field_name, model_cls in get_list_fields(cls):
            if hasattr(model_cls, '__tablename__'):
                addrs.append(model_cls.__tablename__)

    # Extra tools from __agent__ config
    extra = conf.get('tools', [])
    if extra:
        addrs.extend(extra)

    # Deduplicate, preserve order
    return list(dict.fromkeys(addrs))
```

Returns addresses only — `discover_tools()` resolves to ToolSpecs at runtime. This keeps `tools()` pure introspection that works without a running Matrix.

### Step 5: Add `run()` fullmethod — 3-tier config cascade

```python
@fullmethod
async def run(target, task: str, **kwargs) -> dict:
    """Public entry point for agent reasoning. Resolves config, builds
    prompt, discovers tools, manages adapter lifecycle, delegates to agentic().

    Config resolution (3-tier cascade):
        config.AGENT_DEFAULTS < __agent__ dict < run() kwargs

    Product.run(task='...')   → class-level (schema context)
    product.run(task='...')   → instance-level (schema + instance data)

    Override this to add guardrails, audit logging, or rate limiting.
    Call agentic() directly to bypass this layer entirely.
    """
```

Resolution chain:
- `prompt`: kwargs > `target.ctx()`
- `tools`: kwargs > `target.tools()`
- `llm`: kwargs > `__agent__['llm']` > `getattr(target, 'llm', ...)` > default
- `constraints`: merged from all tiers
- `user`, `message_history`, `result_type`: from kwargs

Adapter lifecycle: create transient `NetworkAdapter`, register with Matrix, cleanup in `finally`.

Delegates to `target.agentic()` with all resolved params.

Design notes:
- `prompt` kwarg REPLACES auto-generated context entirely. To compose: `product.run(task=..., prompt=product.ctx() + "\n\nExtra...")`
- `tools` kwarg replaces auto-discovery. Accepts `list[str]` (actor addresses).
- `AgentActor.run()` overrides this method — reads from DB fields, calls `self.agentic()` directly.

### Step 6: Refactor `agentic()` — pure engine

```python
async def agentic(self, task: str, prompt: str, tools: list,
                  user: dict = None, llm=None, constraints: dict = None,
                  adapter=None, message_history=None,
                  result_type=None, **kwargs) -> dict:
    """Execute the LLM agent loop. Pure execution — no config resolution.

    Receives fully resolved params from run(). Can also be called directly
    for advanced use cases (testing, pipelines, custom workflows).

    Returns:
        dict with keys:
            answer: The LLM's final output (str or structured type).
            usage: {input_tokens, output_tokens, requests}
            messages: All conversation messages (for history).
            message_count: Number of messages (backward compat).
    """
```

Key changes from current `agent_run()`:
- Accepts `adapter` param (from `run()`), or creates its own if None (`owns_adapter` flag)
- Accepts `message_history` → passed to `Agent.run(message_history=...)`
- Accepts `result_type` → passed as `Agent(output_type=...)`
- Returns `messages: result.all_messages()` (list) for history support
- Adds `message_count: len(...)` for backward compat

### Step 7: Add `run_stream()` + `agentic_stream()` — TX-aligned chunks

**`run_stream()`** — `@fullmethod`, same config cascade as `run()`, delegates to `agentic_stream()`:
```python
@fullmethod
async def run_stream(target, task: str, **kwargs):
    """Streaming orchestration — same config cascade as run(), yields chunks.

    Product.run_stream(task='...')  → async gen of TX-aligned chunks
    product.run_stream(task='...')  → async gen with instance context
    """
```

**`agentic_stream()`** — pure streaming engine using pydantic-ai `Agent.iter()` with token-level streaming via `node.stream(run.ctx)`:
```python
async def agentic_stream(self, task: str, prompt: str, tools: list,
                         user: dict = None, llm=None, constraints: dict = None,
                         adapter=None, message_history=None,
                         result_type=None, **kwargs):
    """Streaming agent loop — yields TX-aligned chunks.

    Pure execution — no config resolution. Same params as agentic()
    but returns an async generator instead of a dict.
    """
```

**TX-Aligned Chunk Format (full TX parity):**

Each chunk carries `name`, `data`, and `meta` — the same three semantic fields as a TX message. `agentic_stream()` manages its own `seq` counter:

```python
# Text chunk (LLM token delta)
{'name': 'text',        'data': {'text': 'partial...'},                         'meta': {'stream': True, 'seq': 0}}
{'name': 'text',        'data': {'text': 'more text'},                          'meta': {'stream': True, 'seq': 1}}

# Tool invocation
{'name': 'tool_call',   'data': {'tool': 'products_list', 'args': {...}},       'meta': {'stream': True, 'seq': 2}}

# Tool result
{'name': 'tool_result', 'data': {'tool': 'products_list', 'result': {...}},     'meta': {'stream': True, 'seq': 3}}

# Stream end with final result
{'name': 'done',        'data': {'answer': '...', 'usage': {...}},              'meta': {'stream': True, 'stream_end': True, 'seq': 4}}

# Error
{'name': 'error',       'data': {'message': '...', 'code': 500},               'meta': {'stream': True, 'error': True, 'seq': 5}}
```

This mirrors TX conventions exactly:
- `name` → TX.name (event type discriminator)
- `data` → TX.data (payload)
- `meta.stream` → same as TX.stream_chunk() sets
- `meta.seq` → sequence number for ordering
- `meta.stream_end` → terminal signal (same as TX.stream_end())
- `meta.error` → error flag (same as TX.error())

**Integration with existing stack (zero changes needed):**

The `actor_model.py` handler already does:
```python
if inspect.isasyncgen(result):
    seq = 0
    async for chunk in result:
        chunk_data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
        await target.send(tx.stream_chunk(chunk_data, seq))
        seq += 1
    await target.send(tx.stream_end(seq=seq))
```

It wraps the whole chunk dict as `stream_chunk` data. The handler adds its own outer `meta.stream`/`meta.seq` on the TX envelope — the chunk's internal `meta` rides along as nested data. The frontend receives the full structure in each SSE event.

The `routes_fastapi.py` handler similarly JSON-serializes the full chunk dict into SSE data.

`ntx-stream` currently falls back to `JSON.stringify(c)` for unrecognized formats — backward compatible. Richer rendering (dispatching on `name` field, reading `meta.seq` for ordering) is a follow-up frontend enhancement.

**Usage in models:**

```python
class Product(ActorModel):
    __agent__ = True
    __storable__ = True

    @expose_route('/analyze', methods=['POST'], stream=True)
    async def analyze(self, query: str):
        async for chunk in self.run_stream(task=query):
            yield chunk
```

This plugs directly into the existing streaming stack:
- Level 1/2: `routes_fastapi.py` detects async generator → `StreamingResponse` with SSE
- Level 3: `actor_model.py` handler detects async generator → `tx.stream_chunk()` per yield
- Frontend: `<ntx-stream>` renders progressive output via `HTTP.stream()`

### Step 8: Conversation History Support

Already woven into Steps 5-7:
- `run()` / `run_stream()` accept `message_history` kwarg
- `agentic()` / `agentic_stream()` pass it to pydantic-ai `Agent.run(message_history=...)` / `Agent.iter(message_history=...)`
- `agentic()` returns `messages: result.all_messages()` for persistence

```python
# First turn
result1 = await product.run(task='What are my fields?')
history = result1['messages']

# Second turn (continues conversation)
result2 = await product.run(task='Now explain the price constraints', message_history=history)
```

Storage of history is the caller's responsibility. The mixin provides plumbing only.

### Step 9: Structured Output / `result_type`

Already woven into Steps 5-7:
- `__agent__ = {'result_type': ProductAnalysis}` flows through config cascade
- `run()` kwargs can override: `run(task=..., result_type=dict)`
- `agentic()` passes as `Agent(output_type=result_type)`
- Return value's `answer` key contains typed output

```python
from pydantic import BaseModel

class ProductAnalysis(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
    score: float

# Via __agent__ config
class Product(ActorModel):
    __agent__ = {'result_type': ProductAnalysis}

result = await product.run(task='Analyze this product')
analysis = result['answer']  # ProductAnalysis instance

# Via run() kwarg (overrides config)
result = await product.run(task='...', result_type=dict)
```

### Step 10: Update schema extension

In `schema_ext.py`, expose `__agent__` config dict (safe keys only — no LLM credentials):
```python
@schema_extension(after='methods')
def agent(cls, schema: dict) -> dict:
    agent_flag = getattr(cls, '__agent__', False)
    if not agent_flag:
        return schema

    agent_meta = {'enabled': True}

    if isinstance(agent_flag, dict):
        safe_keys = {'self_tools', 'neighbors', 'neighbor_depth'}
        agent_meta['config'] = {k: v for k, v in agent_flag.items() if k in safe_keys}

    from n3tx.core.agents.actor import AgentActor
    if issubclass(cls, AgentActor):
        tablename = schema.get('__tablename__', cls.__tablename__)
        agent_meta['run_endpoint'] = f'/{tablename}/{{id}}/run'

    agent_meta['methods'] = ['run', 'run_stream', 'ctx', 'tools']
    schema['agent'] = agent_meta
    return schema
```

### Step 11: Update `AgentActor.run()` call site

```python
@expose_route('/run', methods=['POST'])
async def run(self, task: str, **kwargs) -> str:
    """Override — resolves tools from DB instead of __agent__ config."""
    tool_addrs = self._resolve_tool_addrs()
    result = await self.agentic(
        task=task,
        prompt=self.prompt,
        tools=tool_addrs,
        llm=kwargs.get('llm', self.llm),
        constraints={**self.constraints, **kwargs.get('constraints', {})},
        user=kwargs.get('user'),
        message_history=kwargs.get('message_history'),
        result_type=kwargs.get('result_type'),
    )
    return json.dumps(result, default=str)
```

AgentActor.run() calls `self.agentic()` directly (pure engine), NOT `super().run()`. It has its own config (DB fields), so it bypasses the mixin's cascade.

### Step 12: Tests

New test classes in `test_mixin.py`:

**TestCtx:**
- `test_class_ctx_has_schema` — `Product.ctx()` returns schema context with fields, types, methods
- `test_instance_ctx_has_state` — `product.ctx()` returns schema + instance data
- `test_ctx_skips_hidden_fields` — omits fields with `ui.display=False`
- `test_ctx_includes_methods` — includes `@expose_route` methods
- `test_ctx_prepends_agent_prompt` — `__agent__={'prompt': 'Custom'}` prepends
- `test_ctx_includes_access_rules` — includes `__access__` rules

**TestTools:**
- `test_self_tools_default` — includes own tablename
- `test_neighbor_tools` — discovers ListRef neighbor tablenames
- `test_class_and_instance_same` — `Product.tools() == product.tools()`
- `test_extra_tools_from_config` — `__agent__={'tools': ['extra']}` adds addresses
- `test_self_tools_disabled` — `__agent__={'self_tools': False}` omits own tablename
- `test_neighbors_disabled` — `__agent__={'neighbors': False}` omits neighbors
- `test_deduplication` — duplicate addresses deduplicated

**TestRun:**
- `test_zero_config_run` — `run(task='...')` auto-discovers prompt and tools
- `test_config_cascade` — `config.AGENT_DEFAULTS < __agent__ dict < run() kwargs`
- `test_explicit_prompt_overrides` — `run(task='...', prompt='custom')` uses custom
- `test_explicit_tools_overrides` — `run(task='...', tools=['grants'])` uses explicit
- `test_adapter_lifecycle` — transient adapter created and cleaned up
- `test_class_vs_instance_run` — class uses schema context, instance uses instance context

**TestAgentic (updated):**
- `test_direct_call` — explicit params, bypasses `run()` cascade
- `test_accepts_adapter` — external adapter, no transient creation
- `test_message_history` — multi-turn with `message_history`
- `test_result_type` — structured output with `result_type`

**TestRunStream:**
- `test_yields_chunks` — yields dicts with `name` field
- `test_adapter_cleanup` — cleanup even if consumer abandons generator
- `test_auto_discovery` — auto-discovers from `ctx()` and `tools()`

**TestAgenticStream:**
- `test_yields_text_chunks` — yields text chunks with `name='text'`
- `test_done_chunk` — yields final done chunk with usage
- `test_error_chunk` — yields error chunk on failure

All use existing `fresh_matrix` fixture + `TestModel(call_tools=[])`.

### Step 13: Update docs (CLAUDE.md)

- Document `fullmethod`/`fullproperty` extraction and new location
- Document `__agent__` dual-purpose pattern (True vs config dict)
- Document `run()`/`agentic()` split (policy vs mechanism)
- Document `ctx()`/`tools()` fullmethod API
- Add `AGENT_DEFAULTS` to config section
- Add streaming usage examples
- Update AgentMixin vs AgentActor distinction

---

## Usage: Before and After

### Before (v1 — everything manual)
```python
class Product(ActorModel):
    __agent__ = True

    @expose_route('/analyze', methods=['POST'])
    async def analyze(self, query: str) -> str:
        result = await self.agent_run(
            prompt="You are a product manager...",
            tools=['products', 'comments'],
            task=query, llm='ollama:llama3.1', constraints={},
        )
        return result['answer']
```

### After (v2 — via `run()`)
```python
class Product(ActorModel):
    __agent__ = True

    @expose_route('/analyze', methods=['POST'])
    async def analyze(self, query: str) -> str:
        result = await self.run(task=query)
        return result['answer']
```

### Streaming variant
```python
class Product(ActorModel):
    __agent__ = True

    @expose_route('/analyze', methods=['POST'], stream=True)
    async def analyze(self, query: str):
        async for chunk in self.run_stream(task=query):
            yield chunk
```

### Override `run()` for custom behavior
```python
class Product(ActorModel):
    __agent__ = True

    async def run(self, task, **kwargs):
        """Add pre/post processing without touching the LLM loop."""
        validated = self.validate_task(task)
        result = await self.agentic(
            validated, prompt=self.ctx(), tools=self.tools(),
            llm='anthropic:claude-sonnet-4-5-20250929',
            constraints={'max_iterations': 5})
        await self.log_usage(result['usage'])
        return result
```

### Call `agentic()` directly for raw control
```python
# Testing, pipelines, custom workflows — bypass run() entirely
result = await product.agentic(
    task=query,
    prompt="Fully custom prompt...",
    tools=['products', 'comments', 'suppliers'],
    llm='ollama:llama3.1', constraints={},
)
```

---

## Execution Order

```
Step 0+1  (parallel, independent)  — descriptors extraction + AGENT_DEFAULTS
Step 2    (rename agent_run → agentic)
Step 6+11 (refactor agentic + update AgentActor) — restore compat
Step 3+4  (parallel) — add ctx() + tools()
Step 5    (add run() — ties 3+4 together)
Step 7    (streaming — run_stream + agentic_stream)
Step 10   (schema extension)
Step 12   (tests)
Step 13   (docs)
```

---

## Edge Cases

- **Self-tool recursion**: `discover_tools(caller_addr=)` already skips the caller's own actor address
- **Class vs instance `ctx()`**: descriptor dispatches automatically — `isinstance(target, type)` branches
- **Adapter cleanup on stream abort**: `try/finally` in `run_stream()` ensures removal
- **Access control flows naturally**: `_route_tool_call()` creates TX with `meta: {user}`, target model's `__access__` + `@expose_route(access=)` enforced by interceptors and `handler_crud`
- **Pydantic `ignored_types`**: `actormethod = fullmethod` alias means identity check passes
- **Empty models**: `ctx()` returns minimal valid text (`You operate on EmptyModel entities.`)
- **`messages` key change**: returns list (not count) — adds `message_count` for backward compat
- **Schema cache**: `cls.schema()` is already cached; `ctx()` re-generates text each call (cheap string formatting from cached dict)
- **Direct `agentic()` call without adapter**: creates its own transient adapter (`owns_adapter` flag)
- **`prompt` kwarg to `run()`**: replaces auto-context entirely (compose via `product.ctx() + extra`)

---

## Verification

1. Run existing agent tests: `cd /workspace/src/n3tx/core && python3 -m pytest agents/tests/ -v`
2. Run new tests: same command covers new test classes
3. Run integration suites: `python3 -m pytest example_grants/tests/`
4. Run actor tests (descriptor extraction): `python3 -m pytest src/n3tx/core/tests/unit/test_actor_system.py -v`
5. Manual: define model with `__agent__ = True`, call `Product.ctx()`, `Product.tools()`, `await product.run(task='...')`
