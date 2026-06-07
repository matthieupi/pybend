# Agentic Flow Subsystem -- Deep Audit Report

**Scope**: `src/n3tx/core/agents/` + integration points
**Branch**: v0.9 (commits through 0.10 agent features)
**Date**: 2026-03-09

---

## PART 1: Architecture & Design Patterns

### 1.1 Component Inventory

| Module | Class/Function | Role |
|--------|---------------|------|
| `agents/__init__.py` | (re-exports) | Public API surface + side-effect import of `schema_ext` to register pipeline stage |
| `agents/mixin.py` | `AgentMixin` | Core mixin injected via `__agent__ = True`; provides `ctx`, `tools`, `run`, `agentic`, `run_stream`, `agentic_stream` |
| `agents/mixin.py` | `_build_schema_text()` | Module-level helper: generates LLM-readable context from JSON Schema |
| `agents/mixin.py` | `_build_instance_text()` | Module-level helper: serializes instance state for LLM context |
| `agents/actor.py` | `AgentActor` | Concrete model whose instances ARE agents; config lives in DB fields; overrides `run()` to bypass mixin cascade |
| `agents/tool_model.py` | `AgentTool` | Simple ActorModel storing an actor address + description; linked to AgentActor via ListRef join table |
| `agents/deps.py` | `AgentDeps` | Dataclass injected into pydantic-ai `RunContext`; carries adapter, user, agent_addr |
| `agents/tools.py` | `ToolSpec` | Dataclass describing a single discovered tool (addr, method, name, description, params) |
| `agents/tools.py` | `discover_tools()` | Reads schemas from Matrix children, generates ToolSpecs for CRUD + custom methods |
| `agents/tools.py` | `_crud_tool_specs()` | Internal: generates 5 CRUD ToolSpecs (list, get, create, update, delete) from schema |
| `agents/tools.py` | `_method_tool_specs()` | Internal: generates ToolSpecs from `schema.methods` entries |
| `agents/tools.py` | `_route_tool_call()` | Async function: routes tool invocations through Matrix as TX messages |
| `agents/tools.py` | `create_tool_function()` | Factory: generates async functions with typed signatures via `exec()` |
| `agents/tools.py` | `make_tool()` | Wraps a ToolSpec into a `pydantic_ai.Tool` object |
| `agents/schema_ext.py` | `agent()` | Schema pipeline extension: injects `agent` section into JSON Schema |
| `config.py` | `AGENT_DEFAULTS` | Module-level dict: global defaults for agent config (self_tools, neighbors, llm, etc.) |
| `utils/descriptors.py` | `fullmethod` | Descriptor enabling unified class/instance dispatch (target = cls or self) |
| `utils/descriptors.py` | `fullproperty` | Descriptor returning values from class or instance context |

### 1.2 Responsibility Map

**AgentMixin** (`mixin.py:188-653`): The heart of the subsystem. Without it, no model has agent capabilities. Provides the full lifecycle: context generation, tool discovery, config cascade, LLM execution (sync + streaming). Removing it breaks every `__agent__ = True` model.

**AgentActor** (`actor.py:38-129`): The "agents as data" pattern. Without it, agents cannot be stored in DB, managed via API, or have per-instance configs. Its `run()` override (`actor.py:103-129`) bypasses the mixin's 3-tier cascade and reads config from DB fields instead. Removing it eliminates dynamic agent creation.

**AgentTool** (`tool_model.py:19-32`): A thin record model. Without it, AgentActor has no way to persistently associate tool addresses. The ListRef join table pattern means tools are managed through the standard N3TX collection API.

**AgentDeps** (`deps.py:22-27`): Bridges pydantic-ai's dependency injection to N3TX's actor system. Without it, tool functions cannot route through Matrix or carry auth context. Only 3 fields, but critical glue.

**discover_tools / make_tool** (`tools.py:43-311`): The schema-to-tool pipeline. Without it, agents have no tools. Reads live schemas from Matrix children, meaning tool discovery reflects the actual runtime state (models registered, methods exposed).

**schema_ext.agent()** (`schema_ext.py:21-43`): Injects agent metadata into JSON Schema. Without it, the frontend cannot know a model is agent-enabled. Side-effect imported in `__init__.py` (line 21).

**config.AGENT_DEFAULTS** (`config.py:27-32`): Base tier of the 3-tier cascade. Without it, the cascade has no defaults. Overridable via `N3TX_AGENT_DEFAULTS` env var (`config.py:34-36`).

**fullmethod** (`descriptors.py:18-44`): Enables `Product.run()` and `product.run()` with one implementation. Without it, every agent method would need separate classmethod + instance method implementations.

### 1.3 Design Patterns

| Pattern | Where Applied | Why Chosen | Assessment |
|---------|--------------|------------|------------|
| **Mixin Injection** | `__agent__ = True` triggers AgentMixin insertion into MRO | Mirrors StorableMixin pattern; zero-config, consistent with framework | Correct. Maintains the "one flag, full capability" principle. |
| **Descriptor (fullmethod)** | `ctx()`, `tools()`, `run()`, `run_stream()` on AgentMixin | Single implementation handles both class-level and instance-level calls | Correct. Eliminates code duplication. The `target` parameter pattern is clean. |
| **3-Tier Config Cascade** | `run()` and `run_stream()` | Layered defaults: global < model < call-site | Correct. Matches the "zero to working, then customize" principle. |
| **Policy/Engine Split** | `run()` (policy) vs `agentic()` (engine) | Separates config resolution from execution; enables direct engine access for testing/pipelines | Correct. Clean boundary. AgentActor's `run()` override demonstrates the value. |
| **Factory via exec()** | `create_tool_function()` in tools.py | Dynamic function signatures that pydantic-ai can introspect for JSON Schema | Justified. Same approach as stdlib `dataclasses` and `namedtuple`. Input is trusted (own schemas). |
| **Transient Actor** | Adapter lifecycle in `run()` | Each run creates a unique NetworkAdapter for request correlation | Correct. Prevents cross-contamination between concurrent runs. UUID-based naming ensures uniqueness. |
| **Correlation-based RPC** | `NetworkAdapter.request()` used by `_route_tool_call()` | Bridges fire-and-forget actor messaging to request/response tool calls | Correct. Reuses existing infrastructure. |
| **Self-exclusion** | `discover_tools()` skips `caller_addr` | Prevents recursive agent-calls-itself loops | Correct. Simple and effective. |
| **Schema Extension** | `@schema_extension(after='methods')` | Plugs into existing pipeline without modifying core proto_schema.py | Correct. Follows the framework's extension pattern. |

### 1.4 Data Flow

#### Primary Flow: `run()` to Response

```
  Developer Call                 Config Resolution              Engine
  ─────────────                 ─────────────────              ──────
  Product.run(task='...')
       │
       ▼
  ┌─────────────────────┐
  │  run() [fullmethod]  │
  │  mixin.py:268        │
  │                      │
  │  1. Resolve cls/self │
  │  2. 3-tier cascade:  │
  │     DEFAULTS < model │
  │     dict < kwargs    │
  │  3. prompt = ctx()   │
  │  4. tools = tools()  │
  │  5. Create adapter   │
  │  6. Register adapter │
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────────┐
  │  agentic() [instance]    │
  │  mixin.py:350             │
  │                           │
  │  1. discover_tools(addrs) │──────► Schema reads from Matrix children
  │  2. make_tool(spec) each  │──────► exec() generates typed functions
  │  3. Build pydantic_ai     │
  │     Agent(llm, prompt,    │
  │           tools, deps)    │
  │  4. agent.run(task)       │──────► LLM reasoning loop
  │  5. Return {answer,       │
  │     usage, messages}      │
  └──────────┬────────────────┘
             │
             ▼ (during LLM loop, per tool call)
  ┌────────────────────────────┐
  │  _route_tool_call()         │
  │  tools.py:201               │
  │                             │
  │  1. Build TX(name, source,  │
  │     target, data, meta)     │
  │  2. adapter.request(tx)     │──────► Matrix routing
  │  3. Check response.is_error │       │
  │  4. Return JSON string      │       ▼
  └─────────────────────────────┘  ┌──────────────┐
                                   │ ActorModel    │
                                   │ handler_crud  │
                                   │ or handler()  │
                                   └──────────────┘
```

#### Tool Discovery Flow

```
  discover_tools(['grants', 'web_tools'], matrix)
       │
       ▼ for each addr
  ┌─────────────────────────────┐
  │ root._children[addr]        │ ── child not found? → log warning, skip
  │                             │
  │ cls = child if type else    │
  │       child.__class__       │
  │                             │
  │ schema = cls.schema()       │
  └──────────┬──────────────────┘
             │
       ┌─────┴─────┐
       │            │
  is_storable?   has methods?
       │            │
       ▼            ▼
  _crud_tool_    _method_tool_
  specs()        specs()
       │            │
       │   5 specs   │   N specs (one per @expose_route)
       └──────┬──────┘
              │
              ▼
         list[ToolSpec]
              │
              ▼ make_tool(spec)
         list[pydantic_ai.Tool]
```

#### Streaming Flow

```
  run_stream(task)
       │
       ▼ (same cascade as run())
  agentic_stream()
       │
       ▼
  ai_agent.run_stream(task)
       │
       ▼ async for text in result.stream_text(delta=True)
  yield {'name': 'text', 'data': {'text': ...}, 'meta': {'stream': True, 'seq': N}}
       │
       ▼ (after stream completes)
  yield {'name': 'done', 'data': {'answer': ..., 'usage': ...}, 'meta': {'stream_end': True}}
```

### 1.5 State Management

| State | Location | Mutated By | Lifecycle |
|-------|----------|-----------|-----------|
| `AGENT_DEFAULTS` | `config.py:27` module global | `configure()` or env var at import | Process lifetime |
| `__agent__` flag | Class attribute on model | Set at class definition time | Class lifetime |
| Transient adapter | `root._children[adapter_addr]` | `run()`/`run_stream()` create, `finally` block removes | Single run() call |
| `_pending` futures | `NetworkAdapter._pending` dict | `request()` adds, `inbox()` resolves | Single request/response cycle |
| Tool function closures | `exec()` namespace in `create_tool_function` | Created per `make_tool()` call, never mutated | Single `agentic()` call |
| `AgentDeps` | Passed via pydantic-ai `RunContext` | Created once per `agentic()` call | Single `agentic()` call |

Key observation: **No persistent state accumulates between runs.** Each `run()` or `agentic()` call creates its own adapter, tools, deps, and pydantic-ai Agent. This is by design -- stateless execution model.

### 1.6 Coupling Analysis

```
  ┌─────────────┐     depends on      ┌──────────────────┐
  │ AgentMixin   │ ──────────────────► │ fullmethod        │ (descriptors.py)
  │              │ ──────────────────► │ config.AGENT_DEFS │ (config.py)
  │              │ ──────────────────► │ NetworkAdapter    │ (network_adapter.py)
  │              │ ──────────────────► │ Actor.root()      │ (actor.py)
  │              │ ──────────────────► │ TX                │ (tx.py)
  │              │ ──────────────────► │ discover_tools    │ (tools.py)
  │              │ ──────────────────► │ make_tool         │ (tools.py)
  │              │ ──────────────────► │ AgentDeps         │ (deps.py)
  │              │ ──────────────────► │ pydantic_ai       │ (external)
  └─────────────┘
  ┌─────────────┐     depends on      ┌──────────────────┐
  │ AgentActor   │ ──────────────────► │ ActorModel        │ (actor_model.py)
  │              │ ──────────────────► │ AgentTool         │ (tool_model.py)
  │              │ ──────────────────► │ AgentMixin.agentic│ (mixin.py)
  └─────────────┘
  ┌─────────────┐     depends on      ┌──────────────────┐
  │ tools.py     │ ──────────────────► │ TX                │ (tx.py)
  │              │ ──────────────────► │ StorableMixin     │ (storable_mixin.py)
  │              │ ──────────────────► │ AgentActor        │ (actor.py) *circular*
  │              │ ──────────────────► │ pydantic_ai       │ (external)
  └─────────────┘
```

**Coupling rating**: MODERATE. The subsystem has necessary dependencies on the actor system and pydantic-ai, but internal coupling is low. The only potentially concerning coupling is `tools.py` importing `AgentActor` for self-exclusion detection (`tools.py:58,95`), creating a soft circular dependency (resolved by deferred import at function call time).

### 1.7 Cohesion Assessment

| Module | Cohesion | Notes |
|--------|----------|-------|
| `mixin.py` | **HIGH** | Single responsibility: agent capability injection. All 6 methods serve one purpose. The module-level helpers (`_build_schema_text`, `_build_instance_text`) are private and cohesive. |
| `actor.py` | **HIGH** | Single class, single purpose: data-driven agent. Clean override of `run()`. |
| `tools.py` | **HIGH** | Discovery + generation pipeline. All functions serve tool lifecycle. |
| `deps.py` | **HIGH** | 3-field dataclass. Minimal and focused. |
| `schema_ext.py` | **HIGH** | Single function, single purpose: schema enrichment. |
| `tool_model.py` | **HIGH** | Minimal model, 2 fields. |
| `config.py` | **MODERATE** (for agent concerns) | AGENT_DEFAULTS is 4 lines in a 69-line file. Appropriate -- agent config belongs with other config. |

### 1.8 Boundary Analysis

**Public surface** (exported in `__init__.py:23-26`):
- `AgentMixin`, `AgentActor`, `AgentTool`, `AgentDeps`
- `ToolSpec`, `discover_tools`, `make_tool`

**Internal implementation** (not exported):
- `_build_schema_text`, `_build_instance_text` (mixin.py)
- `_crud_tool_specs`, `_method_tool_specs`, `_route_tool_call` (tools.py)
- `create_tool_function` (tools.py -- usable but not in `__all__`)
- `_JSON_TYPE_MAP` (tools.py)

**Boundary quality**: Good. The public surface is what a developer needs. Internal helpers are prefixed with `_`. One gap: `create_tool_function` is public-looking but not in `__all__`. It is useful for advanced users who want to build custom tools.

### 1.9 Configuration Surface

| Config Key | Default | Source | Overridable Via |
|-----------|---------|--------|----------------|
| `self_tools` | `True` | `AGENT_DEFAULTS` | `__agent__` dict, not via `run()` kwargs |
| `neighbors` | `True` | `AGENT_DEFAULTS` | `__agent__` dict, not via `run()` kwargs |
| `neighbor_depth` | `1` | `AGENT_DEFAULTS` | `__agent__` dict (not yet implemented in discovery logic) |
| `llm` | `'ollama:llama3.1'` | `AGENT_DEFAULTS` | `__agent__` dict, `run()` kwargs, instance `.llm` attr |
| `prompt` | `''` (auto-generated) | N/A | `__agent__` dict, `run()` kwargs |
| `constraints` | `{}` | `AGENT_DEFAULTS` | `__agent__` dict, `run()` kwargs |
| `max_iterations` | None | `constraints` dict | Via constraints cascade |
| `result_type` | `None` | N/A | `__agent__` dict, `run()` kwargs |
| `tools` (extra addrs) | `[]` | N/A | `__agent__` dict |

**Hardcoded values**:
- Adapter timeout: `30.0s` in `NetworkAdapter.request()` (`network_adapter.py:79`). Not configurable from agent layer.
- LLM fallback: `'ollama:llama3.1'` repeated in `agentic()` (`mixin.py:382`) AND `run()` (`mixin.py:302`). Duplication risk.
- Agent adapter prefix: `'_agent_'` (`mixin.py:320`). Convention, not configurable.
- `safe_keys` for schema extension: `{'self_tools', 'neighbors', 'neighbor_depth'}` (`schema_ext.py:32`). Adding new config keys requires updating this set.

**Finding: `neighbor_depth` is configured but never used.** The `tools()` method (`mixin.py:251-257`) does a flat scan of `get_list_fields(cls)` -- it does not recurse. The `neighbor_depth` config key in `AGENT_DEFAULTS` (`config.py:30`) and `safe_keys` (`schema_ext.py:32`) has no effect. This is a stale config or planned-but-unimplemented feature.

### 1.10 Error Propagation

```
  Error Source              Propagation Path                       Surface
  ────────────              ────────────────                       ───────
  No Matrix root            RuntimeError in run()/agentic()        Raises to caller
                            (mixin.py:325-326, 403-405)

  Actor not found           Warning log + skip in discover_tools   Silent (no tools)
  in discovery              (tools.py:70-72)

  Tool call error TX        _route_tool_call raises ModelRetry     pydantic_ai retries
                            (tools.py:218-219)                     or surfaces error

  LLM provider error        pydantic_ai raises, caught in          agentic() raises;
                            agentic_stream() try/except            agentic_stream() yields
                            (mixin.py:644-649)                     error chunk

  Adapter timeout           NetworkAdapter returns error TX         _route_tool_call →
                            (network_adapter.py:113-116)           ModelRetry

  Invalid tool param name   Warning log + skip                     Silent (param omitted)
                            (tools.py:248-249)
```

**Asymmetry finding**: `agentic()` lets exceptions propagate to the caller (`mixin.py:350-468`), while `agentic_stream()` catches all exceptions and yields error chunks (`mixin.py:644-649`). This is intentional -- streaming must not leave the generator in a broken state -- but means error handling differs between sync and streaming paths. Callers of `agentic()` must use try/except; consumers of `agentic_stream()` check `chunk['name'] == 'error'`.

**Finding: `run()` does not catch exceptions from `agentic()`.** If pydantic-ai raises (e.g., invalid LLM model string), the exception propagates through `run()` after the `finally` block cleans up the adapter (`mixin.py:347-348`). The adapter cleanup is correct, but the caller gets a raw pydantic-ai exception. This is arguably correct (transparent, not magical), but could surprise developers expecting a structured error response.

---

## PART 2: API Surface & Contracts

### 2.1 Public API Inventory

#### AgentMixin Methods

| Method | Decorator | Params | Return | Side Effects |
|--------|-----------|--------|--------|-------------|
| `ctx(target)` | `@fullmethod` | (none beyond target) | `str` -- LLM context text | Calls `cls.schema()`, `get_list_fields()`, `model_dump()` |
| `tools(target)` | `@fullmethod` | (none beyond target) | `list[str]` -- actor addresses | Calls `get_list_fields()` |
| `run(target, task, **kwargs)` | `@fullmethod` | `task: str`, kwargs: `prompt`, `tools`, `llm`, `constraints`, `user`, `message_history`, `result_type` | `dict` with keys: `answer`, `usage`, `messages`, `message_count` | Creates/destroys transient adapter, registers with Matrix |
| `agentic(self, task, prompt, tools, ...)` | (instance method) | `task: str`, `prompt: str`, `tools: list`, `user: dict=None`, `llm=None`, `constraints: dict=None`, `adapter=None`, `message_history=None`, `result_type=None` | `dict` (same shape as `run()`) | Creates adapter if none provided; tool discovery; LLM execution |
| `run_stream(target, task, **kwargs)` | `@fullmethod` | Same as `run()` | async generator yielding `dict` chunks | Same as `run()` |
| `agentic_stream(self, task, prompt, tools, ...)` | (instance method) | Same as `agentic()` | async generator yielding `dict` chunks | Same as `agentic()` |

#### AgentActor Methods

| Method | Decorator | Params | Return | Side Effects |
|--------|-----------|--------|--------|-------------|
| `run(self, task, **kwargs)` | `@expose_route('/run', methods=['POST'])` | `task: str`, kwargs: `llm`, `constraints`, `user`, `message_history`, `result_type` | `str` (JSON) | Resolves tool addrs from DB, calls `self.agentic()` |
| `_resolve_tool_addrs(self)` | (private) | (none) | `list[str]` | May query DB for href resolution |

#### Tool Functions

| Function | Params | Return | Side Effects |
|----------|--------|--------|-------------|
| `discover_tools(actor_addrs, root, caller_addr=None)` | `actor_addrs: list`, `root: Matrix`, `caller_addr: str` | `list[ToolSpec]` | Reads schemas from Matrix children |
| `make_tool(spec)` | `spec: ToolSpec` | `pydantic_ai.Tool` | Creates function via `exec()` |
| `create_tool_function(spec)` | `spec: ToolSpec` | `async function` | Creates function via `exec()` |

#### Schema Extension

| Function | Params | Return | Side Effects |
|----------|--------|--------|-------------|
| `agent(cls, schema)` | `cls: type`, `schema: dict` | `dict` (mutated schema) | Adds `schema['agent']` section |

### 2.2 Contracts & Invariants

**`run()` contract:**
- PRE: Matrix must exist (`Actor.root()` is not None). Violation raises `RuntimeError`.
- PRE: `task` must be a non-empty string. (Not validated -- pydantic-ai handles this.)
- POST: Returns dict with exactly 4 keys: `answer`, `usage`, `messages`, `message_count`.
- POST: Transient adapter is always cleaned up (guaranteed by `finally` block).
- INVARIANT: `run()` kwargs override `__agent__` dict which overrides `AGENT_DEFAULTS`.

**`agentic()` contract:**
- PRE: Must be called on an instance (not a class). `run()` handles this by creating `target()` if target is a type (`mixin.py:331-332`).
- PRE: `prompt` and `tools` must be explicitly provided (no auto-discovery).
- POST: Same return shape as `run()`.
- POST: If `adapter` was provided, it is NOT cleaned up (caller owns it). If `adapter` was None, a transient one is created and cleaned up.

**`discover_tools()` contract:**
- PRE: `root` must be a Matrix instance with `_children` dict.
- POST: Returns `list[ToolSpec]` (possibly empty). Never raises for missing actors.
- INVARIANT: `caller_addr` is excluded from results (self-loop prevention).
- INVARIANT: AgentActor subclasses have `run` and `stream_run` auto-excluded.

**`_route_tool_call()` contract:**
- PRE: `ctx.deps.adapter` must be a registered NetworkAdapter.
- POST on success: Returns JSON string.
- POST on error: Raises `pydantic_ai.ModelRetry` with error message.

**`AgentActor.run()` contract:**
- PRE: Instance must exist (typically loaded from DB via `.get(id)`).
- POST: Returns JSON string (not dict). This differs from `AgentMixin.run()` which returns dict.

### 2.3 Error Handling Contracts

| API | Error Condition | Behavior | Location |
|-----|----------------|----------|----------|
| `run()` | No Matrix root | `RuntimeError("No Matrix root...")` | `mixin.py:325-326` |
| `run()` | Invalid LLM string | Exception from pydantic-ai propagates | Not caught in `run()` |
| `agentic()` | No Matrix root | `RuntimeError("No Matrix root...")` | `mixin.py:403-405` |
| `agentic()` | No tools discovered | Warning log, continues with empty tools | `mixin.py:413-416` |
| `agentic_stream()` | Any exception | Yields `{'name': 'error', ...}` chunk | `mixin.py:644-649` |
| `_route_tool_call()` | Error TX response | `ModelRetry(message)` | `tools.py:218-219` |
| `_route_tool_call()` | Timeout (30s default) | Error TX from adapter, then `ModelRetry` | `network_adapter.py:113-116` |
| `discover_tools()` | Actor not in Matrix | Warning log, skipped | `tools.py:70-72` |
| `discover_tools()` | Actor has no schema | Warning log, skipped | `tools.py:76-78` |
| `create_tool_function()` | Invalid param name | Warning log, param skipped | `tools.py:248-249` |
| `AgentActor.run()` | Empty tools list | Calls `agentic()` with `[]`, LLM runs with no tools | `actor.py:118-119` |

### 2.4 Type Safety

**Enforced types:**
- `ToolSpec` fields: enforced by `@dataclass` (runtime).
- `AgentDeps` fields: enforced by `@dataclass` (runtime).
- `AgentActor` fields: enforced by Pydantic validators (`name: str = Field(min_length=1)`).
- `AgentTool.target`: enforced by Pydantic (`min_length=1`).
- Tool function signatures: enforced by `exec()`-generated type annotations that pydantic-ai validates.

**Assumed types (not validated at boundary):**
- `run(task=...)`: `task` is assumed to be `str`. No explicit check. Pydantic-ai will catch it downstream.
- `run(tools=[...])`: Assumed to be `list[str]`. No check that elements are strings.
- `run(constraints={...})`: Assumed to be `dict`. No schema for valid constraint keys.
- `run(user={...})`: Assumed to be `dict` or `None`. No validation of user dict shape.
- `run(llm=...)`: Can be string or pydantic-ai Model instance. No validation -- pydantic-ai handles it.
- `_route_tool_call()` takes a duck-typed `ctx` (needs `.deps.adapter`, `.deps.user`, `.deps.agent_addr`). Test code uses `MockCtx` (`test_tools.py:261-263`).

**Finding: `ctx` parameter in `_route_tool_call` is not typed.** The function signature is `async def _route_tool_call(ctx, target_addr, method_name, data)` -- no type annotation on `ctx`. It duck-types on `ctx.deps.adapter` and `ctx.deps.user`. This works because pydantic-ai's `RunContext[AgentDeps]` provides these, but the lack of type annotation means static analysis tools cannot catch misuse.

### 2.5 Usage Patterns

**Pattern 1: Zero-config agent model** (most common)

```python
# Definition
class Product(ActorModel):
    __agent__ = True
    name: str = Field(...)


# Usage
result = await Product.run(task='Analyze products',
                           llm=TestModel(call_tools=[]))
# or
result = await product.call(task='Analyze this', llm='anthropic:...')
```
Evidence: `test_mixin.py:411-416`, `test_mixin.py:477-486`

**Pattern 2: Configured agent model** (custom prompt, tools)
```python
class Product(ActorModel):
    __agent__ = {
        'prompt': 'You are a product expert.',
        'self_tools': True,
        'neighbors': False,
        'tools': ['grants', 'sources'],
        'llm': 'anthropic:claude-sonnet-4-5-20250929',
    }
```
Evidence: `test_mixin.py:51-58`, `test_mixin.py:79-85`

**Pattern 3: Data-driven agent** (AgentActor)

```python
agent = AgentActor.create(AgentActor(
    name='Grant Scanner',
    prompt='List all grants.',
    llm='anthropic:...',
))
join_cls.create(join_cls(target='grants', agentactor_id=agent.id))
result_str = await agent.call(task='Find grants', llm=TestModel(...))
result = json.loads(result_str)
```
Evidence: `test_agent_actor.py:291-306`, `test_agent_run.py:28-40`

**Pattern 4: Streaming agent**

```python
async for chunk in product.call_stream(task='Describe yourself', llm=...):
    yield chunk  # {'name': 'text'|'done'|'error', 'data': {...}, 'meta': {...}}
```
Evidence: `test_mixin.py:588-597`

**Pattern 5: Direct engine call** (bypassing config cascade)
```python
result = await scanner.agentic(
    task='Find something',
    prompt='You find things.',
    tools=[],
    llm=TestModel(call_tools=[]),
)
```
Evidence: `test_mixin.py:266-288`

### 2.6 Developer Experience Assessment

**Intuitive**: YES. `__agent__ = True` is as simple as `__storable__ = True`. The mental model is clear: one flag enables agent capabilities.

**Discoverable**: MOSTLY. The module docstring in `mixin.py:1-39` is excellent -- it documents the API surface, the split between `run()` and `agentic()`, and includes usage examples. However:
- The 3-tier cascade is documented in docstrings but not in type hints. A developer cannot see `run()`'s full kwargs from IDE autocomplete because they are `**kwargs`.
- `AgentActor.run()` returns `str` (JSON), while `AgentMixin.run()` returns `dict`. This is a surprising asymmetry.

**Consistent**: MOSTLY.
- `run()` and `run_stream()` have parallel config cascades (good).
- `agentic()` and `agentic_stream()` have parallel signatures (good).
- BUT: `AgentActor.run()` returns JSON string while `AgentMixin.run()` returns dict (inconsistent).

### 2.7 Parameter Validation

| Parameter | Validated? | Where |
|-----------|-----------|-------|
| `task` | No explicit validation | Pydantic-ai validates downstream |
| `prompt` | No | Passed directly to LLM |
| `tools` (list) | Partial -- `discover_tools` logs warnings for missing actors | No type check on elements |
| `llm` | No | Pydantic-ai validates/raises on invalid model string |
| `constraints` | No | Only `max_iterations` key is read; others silently ignored |
| `user` | No | Passed through to `AgentDeps` and TX meta |
| `message_history` | No | Passed to pydantic-ai which validates |
| `result_type` | No | Passed to pydantic-ai as `output_type` |
| `adapter` (in agentic) | Partial -- checked for None to decide ownership | No type check |

**Finding**: No boundary validation. The subsystem trusts its callers entirely. This is consistent with the "transparent, not magical" principle -- the framework doesn't add validation layers that pydantic-ai already provides. However, it means error messages for misuse come from deep in the stack (pydantic-ai internals) rather than from N3TX.

### 2.8 Return Value Contracts

**`run()` / `agentic()` return dict:**
```python
{
    'answer': str | structured_type,  # LLM output
    'usage': {
        'input_tokens': int,
        'output_tokens': int,
        'requests': int,
    },
    'messages': list,                # All conversation messages
    'message_count': int,            # len(messages)
}
```
Defined at `mixin.py:455-464`. Always has exactly these 4 keys.

**`AgentActor.run()` return str:**
```python
json.dumps(result, default=str)  # actor.py:129
```
Same dict as above, but serialized to JSON. This means `messages` (which contains pydantic-ai message objects) goes through `default=str` serialization, potentially losing structure.

**`run_stream()` / `agentic_stream()` yield dicts:**
```python
# Text chunk:
{'name': 'text', 'data': {'text': str}, 'meta': {'stream': True, 'seq': int}}
# Done chunk:
{'name': 'done', 'data': {'answer': str, 'usage': dict}, 'meta': {'stream': True, 'stream_end': True, 'seq': int}}
# Error chunk:
{'name': 'error', 'data': {'message': str, 'code': int}, 'meta': {'stream': True, 'error': True, 'seq': int}}
```
Defined at `mixin.py:544-547`. TX-aligned format matching the framework's streaming protocol.

### 2.9 Lifecycle & Ordering

**Required initialization sequence:**
1. Matrix must exist before any `run()` / `agentic()` call. Typically: `Matrix()` at app startup.
2. Models must be registered with storage and have tables created before tool discovery can read their schemas.
3. For AgentActor: create instance, create tools via join table, then call `run()`.

**Adapter lifecycle within `run()`:**
```
create TX (for uuid) → build adapter_addr → create NetworkAdapter →
register with Matrix → [execute agentic()] → finally: remove from Matrix._children
```
Location: `mixin.py:317-348`

**Finding: TX created solely for UUID generation.** At `mixin.py:319`, a dummy TX is created just to get a uuid for the adapter name: `TX(name='', source='', target='').uuid`. This is wasteful -- `uuid4().hex[:12]` would suffice. The same pattern appears at `mixin.py:398`, `mixin.py:503`, and `mixin.py:566`. Four instances of this anti-pattern.

### 2.10 Documentation Gaps

1. **`neighbor_depth` is documented in config but not implemented.** `AGENT_DEFAULTS` includes `'neighbor_depth': 1` (`config.py:30`), and `schema_ext.py:32` exposes it as a safe key, but `tools()` in `mixin.py:252-257` does a flat scan without any depth parameter. No code reads `neighbor_depth` from the config.

2. **`run()` kwargs not typed.** The `**kwargs` signature means IDE autocomplete shows nothing. Developers must read the docstring to discover valid kwargs (`prompt`, `tools`, `llm`, `constraints`, `user`, `message_history`, `result_type`).

3. **AgentActor.run() return type mismatch.** The docstring says "Returns: JSON string with {answer, usage, messages, message_count}" but the type hint is `-> str`. The mixin's `run()` returns `dict`. This asymmetry is documented in the AgentActor docstring (`actor.py:116`) but not in the mixin.

4. **`agentic()` adapter ownership semantics.** The docstring explains that `agentic()` creates an adapter if none is provided (`mixin.py:392-393`), but the dual-ownership pattern (run() owns adapter AND agentic() can own adapter) means the adapter might be cleaned up twice if both run() and agentic() think they own it. In practice this doesn't happen because run() always passes its adapter, but the contract is subtle.

5. **`create_tool_function()` not in `__all__`.** Useful for advanced users building custom tools, but not discoverable through the public API.

6. **User injection in tool calls.** `_route_tool_call()` puts `user` in `tx.meta` (`tools.py:208`), and ActorModel's handler reads `tx.meta.get('user')` for Tier 2 auth. This chain is tested (`test_mixin.py:537-575`) but not documented in the tool function's docstring.

7. **LLM default repeated in two places.** `'ollama:llama3.1'` appears as a fallback in both `run()` (`mixin.py:302`) and `agentic()` (`mixin.py:382`). If someone changes `AGENT_DEFAULTS['llm']`, the `agentic()` fallback would still be `'ollama:llama3.1'`. The `run()` cascade correctly reads from `AGENT_DEFAULTS`, but `agentic()` has a hardcoded fallback because it is the engine (no config cascade). This is intentional but could confuse developers calling `agentic()` directly.

---

## Summary of Findings

### Design Strengths

1. **Clean policy/engine split**: `run()` vs `agentic()` is a textbook separation of concerns. The AgentActor override demonstrates why this split exists.
2. **Stateless execution**: No state leaks between runs. Each call is self-contained.
3. **Consistent with framework**: `__agent__ = True` mirrors `__storable__ = True`. The mixin injection pattern is proven.
4. **Self-loop prevention**: `caller_addr` exclusion in `discover_tools()` and AgentActor method exclusion prevent infinite recursion.
5. **Adapter lifecycle management**: `try/finally` cleanup in all 4 entry points (run, agentic, run_stream, agentic_stream) ensures no orphaned adapters.
6. **TX-aligned streaming**: Streaming chunks follow the framework's existing stream protocol, enabling reuse of `<ntx-stream>` frontend component.

### Risks and Issues

1. **`neighbor_depth` config is dead code** -- configured in `AGENT_DEFAULTS` and exposed in schema but never read by any logic. Should be documented as planned or removed. (`config.py:30`, `schema_ext.py:32`)

2. **UUID generation via dummy TX** -- `TX(name='', source='', target='').uuid` is used 4 times solely to generate a UUID. This creates and discards a TX object with a timestamp, 3 empty strings, and 2 empty dicts for each run. Minor waste but a code smell. (`mixin.py:319, 398, 503, 566`)

3. **AgentActor.run() returns JSON string, AgentMixin.run() returns dict** -- callers must know which they are dealing with. The `@expose_route` decorator on AgentActor.run() means the HTTP layer expects a string, so this is necessary for the API, but it creates an inconsistency when calling `.run()` programmatically.

4. **Duplicated config cascade logic** -- The 3-tier cascade is implemented identically in both `run()` (`mixin.py:283-312`) and `run_stream()` (`mixin.py:483-496`). This is approximately 14 lines of exact duplication. A `_resolve_config()` helper would eliminate this.

5. **Duplicated adapter lifecycle logic** -- Adapter creation/registration/cleanup appears in `run()`, `run_stream()`, `agentic()`, and `agentic_stream()`. Four implementations of the same pattern. The run/run_stream versions always create an adapter; the agentic/agentic_stream versions conditionally create one. A context manager would reduce this to one implementation.

6. **`_route_tool_call()` ctx parameter is untyped** -- works via duck typing on `ctx.deps`. Static analysis cannot verify correctness.

7. **No timeout configuration for tool calls** -- The `NetworkAdapter.request()` timeout is hardcoded to `30.0s`. Long-running tools (e.g., web scraping, large DB queries) may timeout. No way to configure this from the agent layer.
