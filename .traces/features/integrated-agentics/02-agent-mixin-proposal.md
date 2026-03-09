# AgentMixin v2: Self-Aware Models

**Status:** Plan
**Date:** 2026-03-08 (updated)
**Context:** Conversation exploring whether to keep the AgentMixin/AgentActor split or collapse them. Conclusion: the split becomes genuinely valuable if the mixin auto-derives tools and context from the model it's mixed into. Updated to integrate the streaming infrastructure added in v0.9.

---

## The Insight

Today `__storable__ = True` gives a model zero-config persistence. But `__agent__ = True` gives almost nothing — just an `agentic()` method that still requires the developer to provide prompt, tools, and task manually.

`__agent__` serves dual purpose — it is both the mixin injection flag and the configuration. `True` means default config; a dict provides overrides. Both are truthy, so `__init_subclass__` injection works unchanged.

```python
# Default — auto-derive everything
__agent__ = True

# With overrides — any key is optional
__agent__ = {
    'llm': 'anthropic:claude-sonnet-4-5-20250929',
    'prompt': 'Custom base prompt prepended to auto-context...',
    'tools': ['extra_tool'],           # additional tools (merged with auto-discovered)
    'constraints': {'max_iterations': 10},
    'context_format': 'text',          # 'text' | 'xml' | 'json'
    'include_neighbors': True,         # auto-discover ListRef neighbor tools
}
```

The model's `schema()` already contains everything the mixin needs: field names, types, constraints, descriptions, methods, access rules, relationships, widget hints. The mixin just doesn't use any of it.

**Goal:** Make `__agent__ = True` as powerful as `__storable__ = True`. One flag, zero config, the model can reason about itself — with streaming support out of the box.

---

## What Changes

### AgentMixin API: `ctx()`, `tools()`, `run()`, `agentic()`

`__agent__` is read directly — `True` is treated as `{}` (all defaults), a dict provides overrides.

Four methods, two layers:

| Method | Type | Role |
|--------|------|------|
| `ctx()` | `@fullmethod` | Build LLM context (schema on class, schema + instance data on instance) |
| `tools()` | `@fullmethod` | Discover tool addresses (self + neighbors + config extras) |
| `run()` | `@fullmethod` | **Policy** — public entry point. Reads config, resolves defaults, enforces constraints. Override this. |
| `agentic()` | `async method` | **Mechanism** — raw LLM loop. Takes explicit params. No config resolution. Trusts its caller. |

The split: `run()` is the boundary where you enforce constraints and resolve config. `agentic()` is the engine that just works. You expose `run()` via HTTP, never `agentic()` directly.

```python
class AgentMixin:

    # ── Introspection ──

    @fullmethod
    def tools(target) -> list[str]:
        """Actor addresses for self + neighbor models from ListRef fields.

        Product.tools()  → ['products', 'comments']
        product.tools()  → ['products', 'comments']  (same — tools don't vary per instance)
        """
        cls = target if isinstance(target, type) else target.__class__
        conf = cls.__agent__ if isinstance(cls.__agent__, dict) else {}
        addrs = [cls.__tablename__]
        if conf.get('include_neighbors', True):
            for field_name, model_cls in get_list_fields(cls):
                if hasattr(model_cls, '__tablename__'):
                    addrs.append(model_cls.__tablename__)
        extra = conf.get('tools', [])
        return list(dict.fromkeys(addrs + extra))  # deduplicated, order-preserved

    @fullmethod
    def ctx(target) -> str:
        """Build LLM context from schema. Instance calls append instance data.

        Product.ctx()  → schema context only (fields, access, methods)
        product.ctx()  → schema context + current instance data
        """
        cls = target if isinstance(target, type) else target.__class__
        conf = cls.__agent__ if isinstance(cls.__agent__, dict) else {}
        schema = cls.schema()

        # ── Schema context (always included) ──
        # - Model name + tablename
        # - Field descriptions, types, constraints (from properties)
        # - Widget hints (currency → decimal format, textarea → multiline, etc.)
        # - Relationships (ListRef fields → related model names)
        # - Access rules (who can read/create/update/delete)
        # - Protected fields (auto-injected, warn LLM not to set)
        # - Available methods (from schema['methods'])
        context = _build_schema_text(cls, schema)

        # If conf['prompt'] is set, prepend it
        if conf.get('prompt'):
            context = conf['prompt'] + '\n\n' + context

        # ── Instance context (only when called on an instance) ──
        if not isinstance(target, type):
            data = target.model_dump(exclude={'id'})
            context += f"\n\nCurrent instance (id={target.id}):\n"
            context += json.dumps(data, indent=2, default=str)

        return context

    # ── Execution ──

    @fullmethod
    async def run(target, task: str, **kwargs):
        """Public entry point. Reads __agent__ config, resolves defaults,
        enforces constraints. Override this to customize behavior.

        Product.run(task=...)   → class-level (schema context only)
        product.run(task=...)   → instance-level (schema + instance data)
        """
        cls = target if isinstance(target, type) else target.__class__
        conf = cls.__agent__ if isinstance(cls.__agent__, dict) else {}

        prompt = kwargs.pop('prompt', None) or target.ctx()
        tools = kwargs.pop('tools', None) or target.tools()
        llm = kwargs.pop('llm', None) or conf.get('llm') or getattr(target, 'llm', 'ollama:llama3.1')
        constraints = {**conf.get('constraints', {}), **kwargs.pop('constraints', {})}
        stream = kwargs.pop('stream', False)

        return await target.agentic(
            task, prompt=prompt, tools=tools, llm=llm,
            constraints=constraints, stream=stream, **kwargs)

    async def agentic(self, task: str, prompt: str, tools: list, llm: str,
                      constraints: dict = None, stream: bool = False,
                      user: dict = None, **kwargs) -> dict | AsyncGenerator:
        """Raw LLM loop. Takes explicit params. No config resolution. No magic.

        This is the engine — it does exactly what you tell it.
        Call run() for the default config-aware entry point.
        Call agentic() directly for full control (testing, pipelines, custom workflows).
        """
        # create pydantic-ai Agent, discover tools, run loop, return result
        # if stream=True, return async generator via _agent_stream()
```

This mirrors Actor's existing patterns:
```python
# Actor pattern:
Product.addr       # 'products'        (class)
product.addr       # 'products/1'      (instance)
Product.children   # class children    (class)
product.children   # instance children (instance)

# AgentMixin pattern:
Product.ctx()      # schema context          (class)
product.ctx()      # schema + instance data  (instance)
Product.tools()    # ['products', 'comments'] (class)
product.tools()    # ['products', 'comments'] (instance — same)
Product.run(task=...) # resolves config, calls agentic()  (class)
product.run(task=...) # same, with instance context        (instance)
```

### AgentActor overrides `run()` — `agentic()` is the shared engine

AgentActor's `run()` overrides the mixin's `run()` — resolves tools from DB join table and reads prompt/llm/constraints from instance fields instead of `__agent__` config. But `agentic()` is the same engine underneath.

```python
class AgentActor(ActorModel):
    @expose_route('/run', methods=['POST'])
    async def run(self, task: str, **kwargs):
        """Override — resolves tools from DB instead of __agent__ config."""
        tool_addrs = self._resolve_tool_addrs()
        result = await self.agentic(
            task, prompt=self.prompt, tools=tool_addrs,
            llm=self.llm, constraints=self.constraints, **kwargs)
        return json.dumps(result, default=str)
```

---

## The Split Justified

| | AgentMixin ("self-aware model") | AgentActor ("orchestrator agent") |
|---|---|---|
| **Tools** | Auto: own CRUD + methods + neighbor models | Configured: any models, stored in DB |
| **Prompt** | Auto: generated from schema metadata | Stored in DB, fully custom |
| **Config** | Derived from model definition | Data — user-editable at runtime |
| **Streaming** | Built-in via `stream=True` param | Same, delegates to mixin |
| **Use case** | "Product, analyze yourself" | "Agent, coordinate across Products, Sources, Grants" |
| **Entry point** | `self.run(task=...)` (or `self.agentic()` for raw control) | `POST /agents/{id}/run` → overridden `run()` |
| **Persistence** | No agent config to store — it IS the model | Agent config lives in DB rows |

---

## Auto-Generated Context Example

Given:
```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __agent__ = True  # or __agent__ = {'llm': 'anthropic:claude-sonnet-4-5-20250929'}
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED, 'update': OWNER, 'delete': ROLE('admin')}

    name: str = Field(min_length=1, max_length=200, description="Product name")
    price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}})
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    comments: ListRef[Comment] = Field(default=[])

    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment) -> str: ...
```

`Product.ctx()` returns (class-level — schema only):
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
  - comment(comment: Comment) → string [POST, instance method]
```

`product.ctx()` returns (instance-level — schema + instance data):
```
You operate on Product entities (table: products).
...same schema context as above...

Current instance (id=42):
  name: "Widget Pro"
  price: 29.99
  description: "A professional widget"
```

`Product.tools()` / `product.tools()` returns: `['products', 'comments']`

---

## Usage: Before and After

### Before (v1 — everything manual)
```python
class Product(ActorModel):
    __agent__ = True
    # ...

    @expose_route('/analyze', methods=['POST'])
    async def analyze(self, query: str) -> str:
        result = await self.agentic(
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
    # ...

    @expose_route('/analyze', methods=['POST'])
    async def analyze(self, query: str) -> str:
        result = await self.run(task=query)
        return result['answer']
```

Same behavior. Zero manual config. `run()` reads `__agent__` config, calls `self.ctx()` and `self.tools()`, then delegates to `agentic()`.

### Streaming variant
```python
class Product(ActorModel):
    __agent__ = True
    # ...

    @expose_route('/analyze', methods=['POST'], stream=True)
    async def analyze(self, query: str):
        async for chunk in self.run(task=query, stream=True):
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
            llm='anthropic:claude-sonnet-4-5-20250929', constraints={'max_iterations': 5})
        await self.log_usage(result['usage'])
        return result
```

### Call `agentic()` directly for raw control
```python
# Testing, pipelines, custom workflows — bypass run() entirely
result = await self.agentic(
    task=query,
    prompt="Fully custom prompt...",
    tools=['products', 'comments', 'suppliers'],
    llm='ollama:llama3.1', constraints={},
)
```

---

## Streaming Integration

The framework already has full streaming infrastructure (v0.9). The enhanced mixin plugs into it naturally.

### What exists today

| Layer | Component | What it does |
|-------|-----------|-------------|
| **TX** | `tx.stream_chunk()`, `tx.stream_end()` | Create correlated stream messages with `meta.stream`, `meta.seq`, `meta.req` |
| **Decorator** | `@expose_route(..., stream=True)` | Marks async generator methods as streaming endpoints |
| **Level 1/2** | `routes_fastapi.py` `make_custom_post()` | Detects `isasyncgen(result)` → wraps in SSE `StreamingResponse` |
| **Level 3** | `actor_model.py` handler + `network_api.py` | Detects async gen → sends stream chunks as TX → `_sse_from_stream()` converts to SSE |
| **Adapter** | `NetworkAdapter.stream()` | Queue-based chunk correlation by `tx.uuid` |
| **Middleware** | Pure ASGI `JWTAuthMiddleware` | No buffering (critical — `BaseHTTPMiddleware` breaks SSE) |
| **Frontend** | `HTTP.stream()` | `fetch()` + `ReadableStream` parser, dispatches `onChunk`/`onDone`/`onError` |
| **Frontend** | `Socket._streams` | WebSocket chunk correlation via `meta.req` map |
| **Component** | `<ntx-stream>` | Renders progressive chunks with blinking cursor, extends `NTTMethod` |
| **Schema** | `method.stream = true` | Frontend uses `ntx-stream` instead of `ntx-method` |

### What the enhanced mixin adds

**`run(stream=True)`** (or `agentic(stream=True)` directly) returns an async generator that yields chunks as the LLM responds. Internally, `agentic()` delegates to `_agent_stream()`:

```python
async def _agent_stream(self, ai_agent, task, deps, usage_limits):
    """Async generator that yields chunks from the LLM agent loop."""
    async with ai_agent.iter(task, deps=deps, usage_limits=usage_limits) as run:
        async for node in run:
            if Agent.is_model_request_node(node):
                async with node.stream(run.ctx) as request_stream:
                    async for event in request_stream:
                        if hasattr(event, 'delta'):
                            yield {'text': event.delta, 'type': 'text'}
                        elif hasattr(event, 'tool_name'):
                            yield {'tool': event.tool_name, 'type': 'tool_call'}
            elif Agent.is_call_tools_node(node):
                yield {'type': 'tool_running', 'tools': [t.tool_name for t in node.tool_calls]}
    yield {'type': 'done'}
```

This uses pydantic-ai's `Agent.iter()` API — the node-based streaming that gives control over each step of the agent loop.

### How it connects to existing infrastructure

The developer writes a streaming `@expose_route` that delegates to `run(stream=True)`:

```python
@expose_route('/analyze', methods=['POST'], stream=True)
async def analyze(self, query: str):
    async for chunk in self.run(task=query, stream=True):
        yield chunk
```

From here, the existing stack handles everything:

```
run(stream=True) → agentic(stream=True)
    ↓ yields {'text': '...', 'type': 'text'}
@expose_route(stream=True) async generator
    ↓ yield chunk
Level 1/2: isasyncgen(result) → SSE StreamingResponse
    ↓ event: chunk\ndata: {"text": "...", "type": "text"}
Level 3: handler detects async gen → tx.stream_chunk() → adapter.stream()
    ↓ SSE via _sse_from_stream()
Frontend: HTTP.stream() / Socket._streams
    ↓ onChunk({text: '...', type: 'text'})
<ntx-stream> component
    ↓ progressive render with cursor
```

No new transport, no new components, no new protocols. The mixin just produces an async generator — the framework does the rest.

### Chunk format

Standardized chunk types that `ntx-stream` can render:

```python
{'type': 'text',         'text': 'partial response...'}     # LLM text delta
{'type': 'tool_call',    'tool': 'products_list'}            # Tool invocation starting
{'type': 'tool_result',  'tool': 'products_list', 'data': {...}}  # Tool result
{'type': 'tool_running', 'tools': ['products_list']}         # Tools executing
{'type': 'thinking',     'text': '...'}                      # Extended thinking (if supported)
{'type': 'done'}                                             # Stream complete
{'type': 'error',        'message': '...'}                   # Error
```

The `ntx-stream` component already handles this — it extracts text from `chunk.text || chunk.content || chunk.chunk` and concatenates. Tool events could render as status indicators between text blocks.

---

## Implementation Plan

### Step 0: Refactors (descriptors + rename)

**Extract and rename descriptors:** `actormethod` → `fullmethod`, `actorproperty` → `fullproperty`

These descriptors are no longer Actor-specific — AgentMixin uses them too. Extract to a shared module and rename.

- Create `src/n3tx/core/utils/descriptors.py` with `fullmethod` and `fullproperty`
- Same implementation, same `TYPE_CHECKING` passthrough for IDE support
- Update `src/n3tx/core/actors/actor.py`:
  - `from n3tx.core.utils.descriptors import fullmethod, fullproperty`
  - Replace all `@actormethod` → `@fullmethod`, `@actorproperty` → `@fullproperty`
  - Keep `actormethod`/`actorproperty` as re-exports or aliases for backward compat (optional — check if anything external imports them)
- Update `src/n3tx/core/actors/__init__.py` re-exports if needed
- Run existing Actor tests to verify no regressions
- ~10 lines new file, find-and-replace in actor.py

**Rename `agent_run()` → `agentic()`**

- Rename in `src/n3tx/core/agents/mixin.py`
- Update call site in `src/n3tx/core/agents/actor.py` (`self.agentic(...)`)
- Update all tests referencing `agent_run`
- Update CLAUDE.md references

### Step 1: Add `ctx()` and `tools()` fullmethods to AgentMixin
- Both decorated with `@fullmethod` — `target` is cls or self
- **`ctx(target)`**: Reads `cls.schema()` for fields, constraints, descriptions, access rules, methods, protected fields. If `__agent__['prompt']` set, prepend it. On instance: appends `target.model_dump()` as current instance data. ~40 lines.
- **`tools(target)`**: Returns `[cls.__tablename__]` + neighbor tablenames from `get_list_fields(cls)` (if `include_neighbors` not disabled). Merges `__agent__['tools']` extras, deduplicates. ~10 lines.

### Step 2: Add `run()` fullmethod to AgentMixin
- Decorated with `@fullmethod` — `target` is cls or self
- Reads `__agent__` config, resolves defaults via `target.ctx()` and `target.tools()`
- LLM resolved from: `kwargs['llm']` > `__agent__['llm']` > `self.llm` > default
- Constraints merged: `__agent__['constraints']` + `kwargs['constraints']`
- Delegates to `target.agentic()` with all resolved params
- ~15 lines

### Step 3: Refactor `agentic()` to take explicit params only
- No config resolution — receives `prompt`, `tools`, `llm`, `constraints` as required/explicit args
- Add `stream: bool = False` parameter
- Existing logic stays (create pydantic-ai Agent, discover tools, run loop)
- ~10 lines of signature changes to existing method

### Step 4: Add `_agent_stream()` async generator
- Uses pydantic-ai's `Agent.iter()` for node-level control
- Yields standardized chunk dicts (`text`, `tool_call`, `tool_result`, `done`)
- Handles errors gracefully (yields error chunk, doesn't raise)
- Respects `usage_limits` from constraints
- ~30 lines

### Step 5: Tests
- Test `Product.ctx()` produces schema context (fields, access, methods)
- Test `product.ctx()` produces schema context + instance data
- Test `ctx()` prepends `__agent__['prompt']` when present
- Test `Product.tools()` discovers self + neighbor models
- Test `product.tools()` returns same as class (tools don't vary per instance)
- Test `tools()` merges `__agent__['tools']` extras and deduplicates
- Test `tools()` respects `include_neighbors: False`
- Test `run(task=...)` resolves defaults via `ctx()` and `tools()`, delegates to `agentic()`
- Test `run()` reads `__agent__` config for llm, constraints
- Test `run()` kwargs override config (prompt, tools, llm, constraints)
- Test `run(stream=True)` returns async generator
- Test `agentic()` takes explicit params, no config resolution
- Test `agentic()` called directly bypasses `run()` entirely
- Test LLM resolution chain in `run()`: kwargs > `__agent__` config > field > default
- Test streaming yields correct chunk types in order
- Test AgentActor.run() overrides mixin's run() (resolves from DB fields)
- Test custom `run()` override with pre/post processing still works

### Step 6: Update CLAUDE.md
- Document `fullmethod`/`fullproperty` extraction and new location
- Document the `__agent__` dual-purpose pattern (True vs config dict)
- Document the `run()` + `agentic()` split (policy vs mechanism)
- Document `ctx()`/`tools()` fullmethod API
- Update the AgentMixin vs AgentActor distinction
- Add streaming usage examples

---

## Estimated Effort

~100 lines of new code in mixin.py, ~150 lines of tests. No changes to AgentActor, tools.py, deps.py, schema_ext.py, or any streaming infrastructure.

---

## Open Questions

1. **Prompt composition vs replacement:** When the developer passes `prompt=` to `run()` or `agentic()`, it fully replaces the auto-generated context. The developer can call `self.ctx()` explicitly to compose: `prompt=self.ctx() + "\n\nAlso consider..."`. The `__agent__['prompt']` config key is different — it's *prepended* to the auto-generated schema context by `ctx()` itself.

2. **Neighbor depth:** Should auto-discovery follow ListRef one level deep (Product → Comment) or recursively (Product → Comment → User)? Current plan: one level only. Recursive could bloat the tool list.

3. **Tool deduplication:** If a developer passes `tools=['comments']` and auto-discovery also finds `comments`, should we deduplicate? Yes — simple set union.

4. **Context format:** Plain text (current plan) vs structured (JSON/YAML) vs XML tags? Plain text is most token-efficient and LLMs handle it well. Configurable via `__agent__ = {'context_format': 'xml'}` if needed later.

5. **Streaming chunk granularity:** Should `_agent_stream()` yield every text delta (character-level) or buffer into sentence/word chunks? Current plan: pass through whatever pydantic-ai's `Agent.iter()` yields — let the LLM provider determine granularity.

6. **Tool event rendering in ntx-stream:** The component currently concatenates all chunks as text. Tool call/result events would need a rendering decision — inline status text ("Searching products...") or structured indicators. Could be a follow-up enhancement to the component.
