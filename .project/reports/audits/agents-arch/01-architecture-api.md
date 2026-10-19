# Agent Subsystem Deep Audit: Architecture & API

**Scope:** `src/n3tx/core/agents/` + integration sites
**Branch:** v0.9 (commits through 0.10 development)
**Auditor:** Claude Opus 4.6
**Date:** 2026-03-09

---

## 1. Component Inventory

| Module | Class/Function | Role |
|--------|---------------|------|
| `__init__.py` | _(package)_ | Re-exports public API; side-effect imports `schema_ext` to register the pipeline stage |
| `mixin.py` | `AgentMixin` | Mixin class injected via `__agent__ = True`; provides `ctx`, `tools`, `run`, `agentic`, `run_stream`, `agentic_stream` |
| `mixin.py` | `_build_schema_text()` | Module-level helper: converts model schema dict to LLM-readable context string |
| `mixin.py` | `_build_instance_text()` | Module-level helper: serializes instance state to LLM-readable context string |
| `actor.py` | `AgentActor` | Concrete ActorModel whose DB instances ARE agents; fields = config |
| `tool_model.py` | `AgentTool` | Simple ActorModel storing an actor address + description; linked to AgentActor via ListRef join table |
| `tools.py` | `ToolSpec` | Dataclass: specification for one tool (actor_addr, method_name, tool_name, description, parameters) |
| `tools.py` | `discover_tools()` | Reads schemas from Matrix children, generates ToolSpecs for CRUD + custom methods |
| `tools.py` | `_crud_tool_specs()` | Internal: generates 5 ToolSpecs (list/get/create/update/delete) for a storable model |
| `tools.py` | `_method_tool_specs()` | Internal: generates ToolSpecs from `schema.methods` entries (@expose_route methods) |
| `tools.py` | `_route_tool_call()` | Async: routes a tool invocation through Matrix as TX, returns JSON string |
| `tools.py` | `create_tool_function()` | exec()-based metaprogramming: creates async function with typed Python signature from ToolSpec |
| `tools.py` | `make_tool()` | Wraps a ToolSpec into a `pydantic_ai.tools.Tool` object ready for Agent registration |
| `deps.py` | `AgentDeps` | Dataclass: dependency injection container for Pydantic AI RunContext (adapter, user, agent_addr) |
| `schema_ext.py` | `agent()` | Schema pipeline extension: injects `agent` metadata section into JSON Schema for `__agent__` models |
| `config.py` | `AGENT_DEFAULTS` | Global dict: default agent config (self_tools, neighbors, neighbor_depth, llm) |

**Total:** 8 files, 5 classes, 8 functions, 1 global config dict.

---

## 2. Responsibility Map

### AgentMixin (mixin.py)
**Does:** Provides the 6-method API surface for LLM-powered reasoning on any model with `__agent__ = True`. Handles config cascade, adapter lifecycle, Pydantic AI agent creation, and tool discovery orchestration.
**Why it exists:** Separates agent capability from model identity. Same injection pattern as StorableMixin: a ClassVar flag triggers MRO insertion at class creation time.
**If removed:** All `__agent__ = True` models lose `ctx()`, `tools()`, `run()`, `agentic()`, `run_stream()`, `agentic_stream()`. AgentActor breaks (it inherits these methods).

### AgentActor (actor.py)
**Does:** A concrete storable model where agent configuration is data (DB fields) rather than code (class attributes). Overrides `run()` to read config from instance fields and resolve tools from the join table.
**Why it exists:** Enables runtime-defined agents: create via API, configure via DB, trigger via HTTP endpoint. "Agents are data, not code."
**If removed:** No runtime-defined agents. All agent config must be hardcoded in class definitions.

### AgentTool (tool_model.py)
**Does:** Simple model storing a `target` (actor address string) and `description`. Linked to AgentActor via ListRef join table.
**Why it exists:** Enables agents to have a configurable, storable list of tool references. The join table pattern means tools can be added/removed via standard CRUD API.
**If removed:** AgentActor would need a different storage mechanism for tool references (e.g., a JSON list field).

### tools.py (discover_tools + make_tool)
**Does:** Bridges the actor schema world to the Pydantic AI tool world. Reads schemas from Matrix children, generates ToolSpecs, creates properly-typed Python functions via `exec()`, wraps them as Pydantic AI Tool objects.
**Why it exists:** The LLM needs typed function signatures to generate correct tool calls. The actor system has schemas but not Python callables. This module is the adapter between them.
**If removed:** No tool calling capability. Agents can only answer from their training data, never interact with the actor system.

### AgentDeps (deps.py)
**Does:** A 3-field dataclass injected into every Pydantic AI tool function via `RunContext[AgentDeps]`. Provides the NetworkAdapter (for TX routing), user dict (for auth propagation), and agent address (for TX.source).
**Why it exists:** Pydantic AI's dependency injection mechanism requires a typed deps object. This is the bridge between the N3TX actor world and the Pydantic AI tool runtime.
**If removed:** Tool functions have no way to route calls through Matrix or propagate auth context.

### schema_ext.py
**Does:** Registers a schema pipeline stage that injects `agent` metadata into JSON Schema for `__agent__` models. Exposes: enabled flag, safe config keys, available methods, run_endpoint pattern.
**Why it exists:** Frontend needs to know whether a model supports agent operations, and if so, what endpoint to call. Follows the schema_extension pattern (zero ProtoModel modification).
**If removed:** Frontend has no way to discover agent capabilities from schema. The `agent` section disappears from JSON Schema responses.

---

## 3. Design Patterns

### 3.1 Mixin Injection via `__init_subclass__`

**Where:** `proto_model.py:90-94`
**How:** When a class declares `__agent__ = True`, ProtoModel's `__init_subclass__` dynamically prepends `AgentMixin` to `cls.__bases__`.

```python
# proto_model.py:90-94
__agent__ = getattr(cls, '__agent__', False)
if __agent__:
    from n3tx.core.agents.mixin import AgentMixin
    if not issubclass(cls, AgentMixin):
        cls.__bases__ = (AgentMixin,) + cls.__bases__
```

**Why chosen:** Same pattern as `__storable__ = True` -> StorableMixin. One ClassVar flag, zero imports for the model developer. Consistent with the "zero config, then customize" principle.
**Assessment:** Correct choice. The pattern is well-understood within this codebase. One risk: mutating `__bases__` after class creation can interact poorly with metaclasses, but it works here because Pydantic V2 model_rebuild is not called after injection and the mixin adds only new methods (no field changes).

### 3.2 fullmethod Descriptor for Class/Instance Dispatch

**Where:** `mixin.py` (ctx, tools, run, run_stream all use `@fullmethod`)
**How:** The `fullmethod` descriptor returns `MethodType(fn, cls)` for class access and `MethodType(fn, instance)` for instance access. The function receives `target` (either cls or self) and branches internally.

```python
# mixin.py:204-229
@fullmethod
def ctx(target) -> str:
    cls = target if isinstance(target, type) else target.__class__
    # ... builds schema text, appends instance data if target is instance
```

**Why chosen:** Avoids duplicating logic across `@classmethod` and instance methods. One implementation serves both `Product.ctx()` and `product.ctx()`.
**Assessment:** Good pattern. It works well for the API surface where class-level and instance-level operations differ only in whether instance data is included. The `isinstance(target, type)` check is readable and explicit.

### 3.3 exec()-based Metaprogramming for Tool Functions

**Where:** `tools.py:223-294` (`create_tool_function`)
**How:** Builds a Python function source string with typed parameters, then `exec()`s it in a controlled namespace.

```python
# tools.py:276-291
code = (
    f'async def {func_name}({params_str}) -> str:\n'
    f'    """{desc}"""\n'
    f'    {collect}\n'
    f'    return await _route(ctx, _target, _method, _d)\n'
)
ns = {
    '_route': _route_tool_call,
    '_target': spec.actor_addr,
    '_method': spec.method_name,
    '_required': set(spec.parameters.get('required', [])),
}
exec(code, ns)
```

**Why chosen:** Pydantic AI introspects function signatures to generate JSON Schema for tool descriptions. The function must have proper typed parameters (not `**kwargs`). The same approach is used by Python's `dataclasses`, `namedtuple`, and `attrs`.
**Assessment:** Correct pattern for this use case. The input comes from trusted model schemas (our own code), not user input. The namespace is tightly controlled. One consideration: docstrings with `"""` are escaped (`tools.py:274`), which prevents injection via description fields.

### 3.4 Transient Adapter Pattern

**Where:** `mixin.py:315-348` (in `run()`) and `mixin.py:392-468` (in `agentic()`)
**How:** Creates a short-lived NetworkAdapter with a UUID-based address, registers it with Matrix, uses it for tool call routing, then removes it in a `finally` block.

```python
# mixin.py:319-320
run_id = TX(name='', source='', target='').uuid
adapter_addr = f'_agent_{run_id}'
adapter = NetworkAdapter(addr=adapter_addr)
root.register(adapter)
try:
    # ... run agent ...
finally:
    root._children.pop(adapter_addr, None)
```

**Why chosen:** Each agent run needs its own adapter for request/response correlation. Adapters must be Matrix children for TX routing to work. The transient pattern prevents adapter accumulation.
**Assessment:** Sound design. Well-tested (see `TestRun.test_adapter_lifecycle`, `test_adapter_cleaned_up_on_error`, `TestConcurrentRuns`). However, see Issue 1 below for a duplication concern.

### 3.5 Policy/Engine Split (run vs agentic)

**Where:** `mixin.py:267-348` (run) vs `mixin.py:350-468` (agentic)
**How:** `run()` is the policy layer: resolves the 3-tier config cascade, creates transient adapter, instantiates target if class-level, delegates to `agentic()`. `agentic()` is the engine: receives fully resolved params, builds Pydantic AI Agent, executes the loop, returns results.
**Why chosen:** Separation of concerns. `run()` enforces constraints and resolves config. `agentic()` just works. "Expose `run()` via HTTP, never `agentic()` directly."
**Assessment:** Excellent design. Clean separation that enables both zero-config usage (via `run()`) and advanced control (via `agentic()`). The same split is mirrored for streaming (`run_stream` / `agentic_stream`).

---

## 4. Data Flow

### 4.1 `run()` Call Flow (Non-Streaming)

```
User Code / HTTP
    |
    v
run(task='...', **kwargs)                    @fullmethod — receives cls or self
    |
    |-- 3-tier config cascade:
    |   config.AGENT_DEFAULTS < __agent__ dict < kwargs
    |
    |-- prompt = kwargs.prompt || target.ctx()
    |   ctx() -> _build_schema_text(cls, schema) + _build_instance_text(self)
    |
    |-- tools = kwargs.tools || target.tools()
    |   tools() -> [self_tablename] + [neighbor_tablenames] + [extra addrs]
    |
    |-- Create transient NetworkAdapter(_agent_{uuid})
    |-- Register adapter with Matrix root
    |
    v
agentic(task, prompt, tools, llm, constraints, adapter, ...)
    |
    |-- discover_tools(tool_addrs, matrix_root, caller_addr)
    |       |
    |       |-- For each addr:
    |       |     matrix._children[addr].schema()
    |       |     -> _crud_tool_specs()  (if storable)
    |       |     -> _method_tool_specs() (from schema.methods)
    |       |
    |       v
    |   List[ToolSpec]
    |
    |-- make_tool(spec) for each ToolSpec
    |       |
    |       |-- create_tool_function(spec)  [exec()-based]
    |       |-- pydantic_ai.Tool(fn, takes_ctx=True, ...)
    |       v
    |   List[Tool]
    |
    |-- Agent(llm, system_prompt=prompt, deps_type=AgentDeps, tools=...)
    |-- AgentDeps(adapter=adapter, user=user, agent_addr=...)
    |
    v
ai_agent.run(task, deps=deps, ...)         Pydantic AI loop
    |
    |-- LLM generates tool call
    |       |
    |       v
    |   tool_function(ctx, param1, param2, ...)
    |       |
    |       |-- _route_tool_call(ctx, target_addr, method_name, data)
    |       |       |
    |       |       |-- TX(name=method_name, source=adapter.addr, target=target_addr, data={...})
    |       |       |-- adapter.request(tx)
    |       |       |       |
    |       |       |       |-- adapter.send(tx)
    |       |       |       |       |
    |       |       |       |       v
    |       |       |       |   Matrix.inbox(tx) -> route to target actor
    |       |       |       |       |
    |       |       |       |       v
    |       |       |       |   ActorModel.handler(tx) -> handler_crud() or method dispatch
    |       |       |       |       |
    |       |       |       |       v
    |       |       |       |   result -> tx.reply(data=result) -> send back to adapter.addr
    |       |       |       |
    |       |       |       v
    |       |       |   adapter.inbox(response_tx) -> resolve Future
    |       |       |
    |       |       v
    |       |   json.dumps(response.data) -> return to LLM
    |       |
    |       v
    |   LLM processes result, may call more tools or generate final answer
    |
    v
result = {answer, usage, messages, message_count}
    |
    v
finally: root._children.pop(adapter_addr)   cleanup
```

### 4.2 Tool Call TX Routing Detail

```
  Generated Tool Function          NetworkAdapter             Matrix           Target Actor
  ─────────────────────           ──────────────            ──────           ────────────
  _route_tool_call(ctx,...)
       |
       | TX(name='list',
       |    source='_agent_abc',
       |    target='grants',
       |    data={limit:10})
       |
       +----> adapter.request(tx)
                    |
                    | future = Future()
                    | pending[tx.uuid] = future
                    | adapter.send(tx)
                    |          |
                    |          +----> matrix.inbox(tx)
                    |                      |
                    |                      | route: target='grants'
                    |                      | -> grants.inbox(tx)
                    |                              |
                    |                              | handler(tx)
                    |                              | handler_crud: 'list'
                    |                              | data = cls.list()
                    |                              | reply = tx.reply(data=data)
                    |                              |   (reply.target = '_agent_abc')
                    |                              | grants.send(reply)
                    |                              |         |
                    |                              |         +----> matrix.inbox(reply)
                    |                                                    |
                    |                                                    | route: target='_agent_abc'
                    |                                                    | -> adapter.inbox(reply)
                    |                                                             |
                    |                                                             | meta['req'] matches
                    |                                                             | future.set_result(reply)
                    |
                    | return await future
                    |
       <----  response TX
       |
       | json.dumps(response.data) -> str
       |
       v
  Return to Pydantic AI
```

---

## 5. State Management

| State | Location | Lifetime | Mutated By |
|-------|----------|----------|------------|
| `AGENT_DEFAULTS` | `config.py` module global | Process lifetime | `config.configure()`, env var `N3TX_AGENT_DEFAULTS` at import |
| `__agent__` flag/dict | ClassVar on model class | Class lifetime | Set once at class definition, never mutated |
| AgentMixin in MRO | `cls.__bases__` | Class lifetime | `__init_subclass__` in ProtoModel, once at class creation |
| Transient adapter | `matrix._children[adapter_addr]` | Single `run()` call | Created in `run()`, removed in `finally` block |
| `_pending` futures | `adapter._pending` dict | Per-request | Set in `request()`, resolved/removed in `inbox()` |
| Tool specs | Local variable in `agentic()` | Single `run()` call | Rebuilt every call (no caching) |
| Pydantic AI Agent | Local variable in `agentic()` | Single `run()` call | Created fresh every call |
| AgentActor DB fields | SQLite rows | Persistent | Standard CRUD operations |
| AgentTool DB records | SQLite join table rows | Persistent | Standard CRUD via join model |

**Notable:** Tool specs and the Pydantic AI Agent are recreated on every `run()` call. There is no caching or reuse. This is correct for correctness (schemas may change) but has a performance cost for high-frequency agent runs.

---

## 6. Coupling Analysis

| Component A | Component B | Direction | Coupling Type | Rating |
|-------------|-------------|-----------|---------------|--------|
| AgentMixin | config.py | A->B | Import (AGENT_DEFAULTS) | Low -- clean config read |
| AgentMixin | Actor.root() | A->B | Runtime dependency | Medium -- requires Matrix to exist |
| AgentMixin | NetworkAdapter | A->B | Creates instances | Medium -- tight lifecycle coupling |
| AgentMixin | pydantic_ai | A->B | Creates Agent, Tool | Medium -- versioned API dependency |
| AgentActor | AgentMixin | A inherits B | MRO injection | Low -- standard mixin pattern |
| AgentActor | AgentTool | A->B | ListRef (data relationship) | Low -- standard FK pattern |
| tools.py | Actor schemas | reads | Schema-driven | Low -- loose coupling via dict |
| tools.py | TX / Matrix | routes calls through | Message passing | Low -- fire-and-forget messaging |
| tools.py | pydantic_ai.Tool | wraps | Library adapter | Medium -- must match Tool API |
| schema_ext.py | proto_schema | registers via | Plugin extension | Low -- decorator-based, no modification |
| schema_ext.py | AgentActor | checks subclass | issubclass check | Low -- for run_endpoint generation |
| ProtoModel | AgentMixin | injects | __init_subclass__ | Medium -- ProtoModel knows about AgentMixin |

**Verdict:** Coupling is generally well-managed. The main coupling point is ProtoModel's `__init_subclass__` knowing about AgentMixin -- but this mirrors the StorableMixin pattern and is the accepted injection mechanism. The agents package has zero reverse dependencies into the core framework beyond standard extension points.

---

## 7. Error Propagation

### 7.1 Error Path: Tool Call Failure

```
_route_tool_call()
    |
    adapter.request(tx) -> response TX
    |
    if response.is_error:
        raise ModelRetry(response.data.get('message', 'Tool call failed'))
```

`ModelRetry` is Pydantic AI's retry mechanism -- it feeds the error message back to the LLM so it can try a different approach. **Good design**: tool failures become LLM-visible retries, not hard crashes.

File: `tools.py:217-219`

### 7.2 Error Path: No Matrix Root

```python
# mixin.py:323-326
root = Actor.root()
if not root:
    raise RuntimeError("No Matrix root. Initialize a Matrix before running agents.")
```

**Raised:** `RuntimeError`
**Caught:** Not caught -- propagates to caller. Correct behavior: this is a configuration error.

Same check exists in `agentic()` at `mixin.py:402-405`, `run_stream()` at `mixin.py:507-510`, and `agentic_stream()` at `mixin.py:569-572`.

### 7.3 Error Path: Missing Actor in Tool Discovery

```python
# tools.py:70-72
child = children.get(addr)
if child is None:
    logger.warning("Tool discovery: actor '%s' not found in Matrix", addr)
    continue
```

**Behavior:** Warning logged, actor skipped, execution continues. If ALL actors are missing, `agentic()` logs a separate warning at `mixin.py:414-416` but proceeds anyway (agent runs without tools).

**Assessment:** This is arguably correct for the zero-config philosophy -- an agent should still answer questions even without tools. But the warning is easy to miss in logs.

### 7.4 Error Path: agentic_stream() Exception

```python
# mixin.py:644-649
except Exception as e:
    yield {
        'name': 'error',
        'data': {'message': str(e), 'code': 500},
        'meta': {'stream': True, 'error': True, 'seq': seq},
    }
```

**Assessment:** Good -- streaming errors are yielded as error chunks rather than raised as exceptions. This is correct for SSE/WebSocket consumers. Note that `agentic()` (non-streaming) does NOT catch exceptions -- they propagate to the caller. This asymmetry is intentional: `run()` callers can try/except, but stream consumers need in-band error signaling.

### 7.5 Error Path: _build_instance_text() Failure

```python
# mixin.py:163-166
try:
    data = target.model_dump()
except Exception:
    return ''
```

**Assessment:** Silently returns empty string on any model_dump failure. This is a defensive fallback -- the LLM still gets schema context even if instance serialization fails. However, the silent swallowing means bugs in model_dump could go undetected in agent contexts.

### 7.6 Error Path: AgentActor.run() -- No Adapter Provided

`AgentActor.run()` (`actor.py:103-129`) calls `self.agentic()` without passing an adapter. `agentic()` then creates its own transient adapter (`mixin.py:393-406`, the `owns_adapter = adapter is None` path). This works correctly but means AgentActor always creates a transient adapter on every run, unlike `AgentMixin.run()` which also creates one but through the policy layer.

---

## 8. Configuration Surface

### 8.1 Three-Tier Cascade

```
Tier 1: config.AGENT_DEFAULTS (process-wide global)
    |
    v
Tier 2: cls.__agent__ dict (per-model class, set at definition)
    |
    v
Tier 3: run() kwargs (per-call, highest precedence)
```

**Resolved keys:**

| Key | Tier 1 Default | Tier 2 Override | Tier 3 Override | Used In |
|-----|---------------|-----------------|-----------------|---------|
| `self_tools` | `True` | `__agent__['self_tools']` | N/A (via `tools` kwarg) | `tools()` |
| `neighbors` | `True` | `__agent__['neighbors']` | N/A (via `tools` kwarg) | `tools()` |
| `neighbor_depth` | `1` | `__agent__['neighbor_depth']` | N/A | **UNUSED** (see Issue 2) |
| `llm` | `'ollama:llama3.1'` | `__agent__['llm']` | `run(llm=...)` | `agentic()` |
| `prompt` | _(auto-generated)_ | `__agent__['prompt']` | `run(prompt=...)` | Prepended to ctx() |
| `constraints` | `{}` | `__agent__['constraints']` | `run(constraints=...)` | `agentic()` -> UsageLimits |
| `tools` (addrs) | _(auto-discovered)_ | `__agent__['tools']` | `run(tools=...)` | Additional tool addrs |
| `result_type` | `None` | `__agent__['result_type']` | `run(result_type=...)` | `Agent(output_type=...)` |

### 8.2 What's Hardcoded

| Value | Location | Should Be Configurable? |
|-------|----------|------------------------|
| Default LLM fallback `'ollama:llama3.1'` | `mixin.py:302`, `mixin.py:382`, `mixin.py:490`, `mixin.py:552` | Already in AGENT_DEFAULTS, but the hardcoded fallbacks in agentic() are redundant |
| Adapter timeout `30.0s` | `network_adapter.py:79` | Yes -- agent tool calls to slow LLMs could timeout |
| TX source naming `_agent_{uuid}` | `mixin.py:320` | No -- internal convention, not user-facing |
| `_JSON_TYPE_MAP` | `tools.py:21-28` | No -- covers all JSON Schema types, correct mapping |
| `safe_keys` whitelist | `schema_ext.py:32` | Low priority -- extend as new config keys are added |

---

## 9. Public API Inventory

### 9.1 AgentMixin Methods

| Method | Signature | Returns | Side Effects | Exceptions |
|--------|-----------|---------|--------------|------------|
| `ctx()` | `(target) -> str` | LLM context string | None | None (swallows model_dump errors) |
| `tools()` | `(target) -> list` | `list[str]` of actor addrs | None | None |
| `run()` | `(target, task: str, **kwargs) -> dict` | `{answer, usage, messages, message_count}` | Creates/removes transient adapter in Matrix | `RuntimeError` if no Matrix |
| `agentic()` | `(self, task, prompt, tools, ...) -> dict` | Same as run() | Creates/removes adapter if none provided | `RuntimeError` if no Matrix (when no adapter) |
| `run_stream()` | `(target, task: str, **kwargs) -> AsyncGenerator` | Yields `{name, data, meta}` dicts | Creates/removes transient adapter | `RuntimeError` if no Matrix |
| `agentic_stream()` | `(self, task, prompt, tools, ...) -> AsyncGenerator` | Yields `{name, data, meta}` dicts | Creates/removes adapter if none provided | Yields error chunk on exception |

### 9.2 AgentActor Methods

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `run()` | `(self, task: str, **kwargs) -> str` | JSON string of `{answer, usage, messages, message_count}` | @expose_route('/run', POST); overrides mixin's run() |
| `_resolve_tool_addrs()` | `(self) -> list` | `list[str]` of actor addrs from DB tools | Handles AgentTool instances, hrefs, plain strings |

### 9.3 Tool System Functions

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `discover_tools()` | `(actor_addrs, root, caller_addr=None) -> list[ToolSpec]` | List of ToolSpecs | Reads schemas from Matrix children |
| `create_tool_function()` | `(spec: ToolSpec) -> Callable` | Async function with typed params | Uses exec() |
| `make_tool()` | `(spec: ToolSpec) -> pydantic_ai.Tool` | Pydantic AI Tool object | Combines create_tool_function + Tool wrapper |
| `_route_tool_call()` | `(ctx, target_addr, method_name, data) -> str` | JSON string | Raises ModelRetry on error TX |

---

## 10. Contracts & Invariants

### 10.1 Preconditions

| API | Precondition | Validated? | Consequence if Violated |
|-----|-------------|------------|------------------------|
| `run()` / `agentic()` | Matrix root must exist | Yes (`mixin.py:323`) | `RuntimeError` raised |
| `run()` / `agentic()` | `task` must be a string | No (trusted from caller) | Pydantic AI receives it as-is |
| `discover_tools()` | `root` must have `_children` dict | No | `AttributeError` on None |
| `discover_tools()` | Child actors must have `schema()` method | Yes (`tools.py:76-78`) | Warning logged, actor skipped |
| `_route_tool_call()` | `ctx.deps.adapter` must be a registered NetworkAdapter | Implicitly (adapter.send routes through Matrix) | TX lost silently if not registered |
| `AgentActor.run()` | Instance must have valid `self.prompt` | No | Empty prompt passed to LLM |
| `AgentActor._resolve_tool_addrs()` | `self.tools` is list of AgentTool, href strings, or plain strings | Yes (handles all three cases) | Warning logged for unresolvable hrefs |

### 10.2 Postconditions

| API | Postcondition | Guaranteed? |
|-----|--------------|-------------|
| `run()` | Transient adapter removed from Matrix | Yes (finally block) |
| `run()` | Returns dict with `answer`, `usage`, `messages`, `message_count` | Yes (built in agentic) |
| `agentic_stream()` | Final chunk has `name='done'` or `name='error'` | Yes (explicit yield in both paths) |
| `agentic_stream()` | Adapter cleaned up | Yes (finally block) |
| `ctx()` | Returns non-empty string | Yes (at minimum, builds schema text) |
| `tools()` | Returns deduplicated list | Yes (dict.fromkeys pattern) |

### 10.3 Invariants

1. **Adapter isolation:** Every `run()` call gets its own adapter with a UUID-based address. Concurrent runs never share adapters. (Verified by `TestConcurrentRuns.test_concurrent_runs_isolated`)
2. **Self-exclusion:** An agent never discovers itself as a tool. (`discover_tools` checks `caller_addr == addr`, `tools.py:65-66`)
3. **AgentActor.run excludes meta-operations:** `run` and `stream_run` methods on AgentActor subclasses are auto-excluded from tool discovery. (`tools.py:94-96`)
4. **Auth propagation:** User context flows from `run(user={...})` through `AgentDeps.user` into `TX.meta['user']` on every tool call. (Verified by `TestUserAuthPropagation`)

---

## 11. Type Safety Analysis

### 11.1 Well-Typed

- `ToolSpec` fields: all typed via dataclass annotations
- `AgentDeps` fields: typed with Optional and TYPE_CHECKING guard
- `create_tool_function()`: generates functions with proper Python type annotations from `_JSON_TYPE_MAP`
- `AgentActor` fields: all Pydantic Field-typed

### 11.2 Assumed / Weakly Typed

| Location | Issue | Risk |
|----------|-------|------|
| `run(task: str, **kwargs)` | `kwargs` is untyped -- user, llm, constraints, tools, message_history, result_type all extracted by key | Typos silently ignored (`run(tak='...')` passes without error) |
| `agentic(user: dict = None)` | `user` typed as `dict` but actually expects a JWT-shaped dict with `id`, `role`, etc. | No validation of user structure |
| `AgentDeps.user: Optional[dict]` | Same issue -- `dict` is too broad | Tool calls could fail if user dict is malformed |
| `tools()` return type | Annotated as `list` not `list[str]` | Minor -- the return type hint is imprecise |
| `run()` return type | Annotated as `dict` not a typed dict or dataclass | Consumers must know the shape `{answer, usage, messages, message_count}` |
| `_route_tool_call()` returns `str` | Tool results are always stringified JSON | LLM sees everything as text; structured data is double-serialized |
| `agentic_stream()` chunk format | Returns raw dicts, not typed objects | Consumer must know `{name, data, meta}` schema |

### 11.3 Type Leakage

**`AgentActor.run()` returns `str` (JSON) but `AgentMixin.run()` returns `dict`.**

This is an intentional asymmetry: `AgentActor.run()` is an `@expose_route` method whose return goes through the HTTP layer (which needs a string), while `AgentMixin.run()` is called programmatically (where a dict is more useful). But it creates a potential surprise if someone holds an `AgentActor` reference and calls `run()` expecting a dict.

File references: `actor.py:104,129` vs `mixin.py:268`.

---

## 12. Usage Patterns (From Tests and Example Apps)

### 12.1 Zero-Config Agent (test_mixin.py)

```python
class AgenticProduct(ActorModel):
    __agent__ = True
    name: str = Field(...)

# Class-level
result = await AgenticProduct.run(task='Describe yourself', llm=TestModel(call_tools=[]))

# Instance-level
product = AgenticProduct(name='Widget', price=29.99, addr='agentic_products/1')
result = await product.run(task='Analyze me', llm=TestModel(call_tools=[]))
```

### 12.2 Runtime-Defined Agent (example_grants)

```python
agent = AgentActor.create(AgentActor(
    name="Grant Scanner",
    prompt="You are a grant discovery agent.",
    llm="ollama:llama3.1",
))
# Add tools via join table
join_cls.create(join_cls(target='grants', agentactor_id=agent.id))

# Later, from DB
agent = AgentActor.get(1)
result_str = await agent.call(task='Scan all sources')
result = json.loads(result_str)
```

### 12.3 Subclassed AgentActor (example_chat)

```python
class Conversation(AgentActor):
    __tablename__ = 'conversations'
    __agent__ = True  # inherited from AgentActor
    messages: ListRef[Message] = Field(default=[])
    user_owner: int = Field(default=None)
    # Does NOT use run() -- has its own send_message handler
```

### 12.4 Streaming (test_mixin.py)

```python
async for chunk in AgenticProduct.call_stream(task='Describe yourself',
                                              llm=TestModel(call_tools=[])):
    if chunk['name'] == 'text':
        print(chunk['data']['text'], end='')
    elif chunk['name'] == 'done':
        print('\nUsage:', chunk['data']['usage'])
```

### 12.5 Tool Calling Through Matrix (test_mixin.py)

```python
class Grant(ActorModel):
    __tablename__ = 'grants'
    __storable__ = True
    title: str = Field(default='')

register_model(Grant, storage=file_storage)
file_storage.create_table(Grant)

scanner = Scanner(addr='scanners/1')
result = await scanner.agentic(
    task='List all grants',
    prompt='List available grants.',
    tools=['grants'],
    llm=TestModel(call_tools=['grants_list']),
)
```

---

## 13. Developer Experience Assessment

### 13.1 What Works Well

1. **Zero to working is real.** Adding `__agent__ = True` to any ActorModel gives it full agent capabilities with no other changes. The promise is delivered.

2. **The policy/engine split is intuitive.** `run()` for normal use, `agentic()` for advanced control. Clear separation, well-documented.

3. **Tool discovery is automatic.** Self-tools and neighbor tools are discovered from the schema. No manual tool registration needed for the common case.

4. **Streaming follows the same pattern as non-streaming.** `run_stream()` mirrors `run()` in config cascade, adapter lifecycle, and API shape. Only the return type differs (async generator vs dict).

5. **Tests are comprehensive.** 200+ lines of tests covering injection, ctx generation, tool discovery, concurrent runs, adapter cleanup, auth propagation, error handling, streaming.

### 13.2 What Would Surprise a New Developer

1. **`AgentActor.run()` returns `str`, `AgentMixin.run()` returns `dict`.** The @expose_route requirement forces JSON serialization in AgentActor, but this means `json.loads()` is needed after every call. A developer holding a typed AgentActor reference might not expect this.

2. **`tools()` returns addresses, not ToolSpecs.** The method name suggests it returns tools, but it returns string addresses. The actual ToolSpec resolution happens inside `agentic()` via `discover_tools()`. This is an intentional design (lazy resolution) but the naming could be clearer.

3. **`run()` on a class creates a throwaway instance.** `mixin.py:331-332`: `if isinstance(target, type): instance = target()`. This means `Product.run(task='...')` silently creates a `Product()` with default field values. The instance is used for `agentic()` but the model_dump in ctx() will show default values, which may confuse the LLM.

4. **No tool caching.** Every `run()` call re-discovers tools, re-creates functions, re-builds the Pydantic AI Agent. For chatbots or tight loops, this is wasteful. A developer might expect tool discovery to be cached.

5. **`neighbor_depth` is configured but never used.** See Issue 2 below.

---

## 14. Issues and Risks

### Issue 1: Duplicated Adapter Lifecycle Code (Medium)

The transient adapter creation pattern (create adapter, register, try/finally cleanup) is duplicated 4 times:

- `mixin.py:315-348` (run)
- `mixin.py:392-468` (agentic, when no adapter provided)
- `mixin.py:498-532` (run_stream)
- `mixin.py:559-652` (agentic_stream, when no adapter provided)

Each copy creates a TX just to get a UUID (`TX(name='', source='', target='').uuid`), which instantiates a full TX dataclass just for its UUID field. A context manager or helper function would eliminate this duplication.

**Recommendation:** Extract an `_adapter_context()` async context manager or a helper `_create_transient_adapter()` / `_cleanup_adapter()` pair.

### Issue 2: `neighbor_depth` Is Declared But Never Implemented (Low-Medium)

`config.py:30` declares `'neighbor_depth': 1` as a default. `schema_ext.py:32` lists it as a safe key for schema exposure. But `tools()` in `mixin.py:252-257` only traverses direct ListRef relationships -- there is no recursive traversal controlled by `neighbor_depth`.

File: `mixin.py:252-257` -- no depth parameter, no recursion.

**Impact:** A developer reading the config might set `neighbor_depth: 2` expecting transitive tool discovery (e.g., Product -> Comment -> User), but it would have no effect.

**Recommendation:** Either implement depth-controlled recursive neighbor discovery or remove `neighbor_depth` from `AGENT_DEFAULTS` and `schema_ext.safe_keys`.

### Issue 3: run() kwargs Are Unvalidated (Low)

`run(target, task: str, **kwargs)` extracts keys like `prompt`, `tools`, `llm`, `constraints`, `user`, `message_history`, `result_type` from `**kwargs`. A typo like `run(task='...', promt='custom')` silently ignores the misspelled key.

File: `mixin.py:293-312` -- all `kwargs.get()` calls.

**Recommendation:** Either use explicit keyword arguments or validate that kwargs keys are in an allowed set.

### Issue 4: Default LLM Hardcoded in Multiple Places (Low)

The string `'ollama:llama3.1'` appears as a fallback in:
- `config.py:31` (AGENT_DEFAULTS)
- `mixin.py:302` (run, 4th fallback)
- `mixin.py:382` (agentic, default)
- `mixin.py:490` (run_stream, 4th fallback)
- `mixin.py:552` (agentic_stream, default)
- `actor.py:59` (AgentActor field default)

The `agentic()` and `agentic_stream()` fallbacks (`mixin.py:382`, `mixin.py:552`) are redundant since `run()` already resolves the LLM before calling `agentic()`. But if someone calls `agentic()` directly without an LLM, they get the hardcoded default rather than `config.AGENT_DEFAULTS['llm']`.

**Recommendation:** `agentic()` should read from `config.AGENT_DEFAULTS` rather than hardcoding.

### Issue 5: test_agent_run.py Line 54 Compares int to list (Bug)

```python
# example_grants/tests/test_agent_run.py:54
assert result["messages"] >= 2  # at least prompt + response
```

`result["messages"]` is a list (from `agentic()`), not an integer. This assertion compares a list to an int, which in Python 3 raises `TypeError`. This test line appears to be a bug -- it should be `len(result["messages"]) >= 2` or `result["message_count"] >= 2`.

**However**, `AgentActor.run()` returns `json.dumps(result, default=str)` and the test does `json.loads(result_str)`, so `result["messages"]` is a deserialized list. The comparison `list >= 2` would raise `TypeError` if this test ever runs with a real result.

File: `example_grants/tests/test_agent_run.py:54`

### Issue 6: `_build_instance_text()` Truncation Inconsistency (Low)

```python
# mixin.py:170-174
for k, v in data.items():
    s = str(v)
    if len(s) > 200:
        s = s[:200] + '...'
    truncated[k] = v if len(str(v)) <= 200 else s
```

The variable `s` is computed, truncated if needed, but then the assignment rechecks `len(str(v)) <= 200` -- calling `str(v)` a second time. This is wasteful but also potentially inconsistent if `str(v)` has side effects or changes between calls (unlikely but not impossible for custom `__str__` methods).

**Recommendation:** Use the already-computed `s` and `len(s)`:
```python
truncated[k] = v if len(s) <= 200 else s
```

---

## 15. Documentation Gaps

| Gap | Location | Impact |
|-----|----------|--------|
| `tools()` return type is `list`, should be `list[str]` | `mixin.py:232` | Minor -- imprecise type hint |
| `run()` return shape `{answer, usage, messages, message_count}` is only in the docstring of `agentic()`, not `run()` | `mixin.py:268` vs `mixin.py:370-376` | Developers must read `agentic()` docs to know what `run()` returns |
| `neighbor_depth` config key is documented in CLAUDE.md but not implemented | Multiple | Misleading config surface |
| Streaming chunk format (`name`, `data`, `meta` keys) is documented only in `agentic_stream()` docstring | `mixin.py:544-547` | Frontend consumers have no schema-level documentation |
| `AgentActor.run()` returns `str` (JSON) -- not documented that it differs from mixin's `dict` | `actor.py:115-116` | Developer surprise |
| `_resolve_tool_addrs()` is private but critical for AgentActor operation | `actor.py:62` | No public documentation of href resolution behavior |
| `_route_tool_call()` timeout (inherited from `adapter.request()` 30s default) is not configurable from agent config | `network_adapter.py:79` | Tool calls to slow endpoints (scraping, LLM chains) may timeout silently |
| No documentation of the `constraints` dict shape -- only `max_iterations` is used | `mixin.py:439-441` | Developers don't know what constraint keys are supported |

---

## 16. Lifecycle & Ordering Requirements

```
1. Matrix must be instantiated              (Actor.__matrix__ must be set)
    |
2. Models must be registered                (register_model() for storable models)
    |
3. Models must be Matrix children           (ActorMeta auto-registers, or manual m.register())
    |
4. AgentMixin injected via __agent__        (happens at class definition time)
    |
5. Schema extension registered              (happens at import time via __init__.py side-effect)
    |
6. Agent can run                            (run/agentic requires steps 1-3)
```

**Critical ordering:** If `agents/__init__.py` is never imported, `schema_ext.py` is never registered, and `__agent__` models won't have the `agent` section in their schema. The `__init__.py` uses a side-effect import (`from . import schema_ext as _schema_ext`) to handle this, which is triggered by any import from the agents package.

**Risk:** If a developer imports only `from n3tx.core.agents.mixin import AgentMixin` (bypassing `__init__.py`), the schema extension won't be registered. In practice this doesn't happen because `__init_subclass__` in ProtoModel imports `AgentMixin` directly from `mixin.py`, not through `__init__.py`. The schema extension registration depends on someone importing from the agents package properly (e.g., `from n3tx.core.agents import AgentActor`). In the example apps, this works because `main.py` imports `AgentActor` from the package.

**Mitigation recommendation:** Register the schema extension in `mixin.py` itself (or in ProtoModel's `__init_subclass__`) to guarantee it runs whenever AgentMixin is injected.

---

## 17. Summary Scorecard

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Cohesion** | 9/10 | Each module has a clear, single responsibility |
| **Coupling** | 8/10 | Well-managed; only ProtoModel knows about injection |
| **API Design** | 7/10 | Policy/engine split is excellent; kwargs bag is weak |
| **Type Safety** | 6/10 | Tool functions are well-typed; run() kwargs are not |
| **Error Handling** | 7/10 | Tool errors become ModelRetry; some silent swallowing |
| **Test Coverage** | 9/10 | Comprehensive unit tests; one bug in integration test |
| **Documentation** | 7/10 | Good docstrings; some gaps in return types and config |
| **Code Duplication** | 5/10 | Adapter lifecycle duplicated 4x; config cascade 2x |
| **Consistency** | 8/10 | Follows codebase patterns (mixin injection, schema extension) |
| **DX (Developer Experience)** | 8/10 | Zero-config works; advanced use is well-supported |

**Overall:** The agent subsystem is a well-designed, architecturally sound addition that faithfully follows N3TX's principles. The policy/engine split, schema-driven tool discovery, and TX-based tool routing are elegant. The main areas for improvement are reducing code duplication (adapter lifecycle, config cascade), implementing or removing `neighbor_depth`, strengthening type safety on the `run()` kwargs boundary, and fixing the test bug in `example_grants/tests/test_agent_run.py:54`.
