# Agents Subsystem Audit: Quality, Risks, Extensibility & Integration

**Date:** 2026-03-09
**Scope:** `/workspace/src/n3tx/core/agents/` (mixin.py, actor.py, tools.py, deps.py, schema_ext.py, tool_model.py, config.py) + tests + integration sites
**Branch:** v0.9

---

## 1. Architecture Summary

```
                      +-----------------+
                      |  config.py      |
                      |  AGENT_DEFAULTS |
                      +--------+--------+
                               |
              3-tier cascade   |   __agent__ dict   |   run() kwargs
                               v
+------------------+   +----------------+   +------------------+
| AgentMixin       |   | AgentActor     |   | Conversation     |
| (injected via    |   | (extends       |   | (extends         |
|  __agent__=True) |   |  ActorModel)   |   |  AgentActor)     |
+--------+---------+   +--------+-------+   +--------+---------+
         |                       |                    |
         | ctx(), tools()        | _resolve_tool_addrs|
         | run(), agentic()      | run() override     |
         | run_stream()          |                    |
         | agentic_stream()      |                    |
         +----------+------------+--------------------+
                    |
                    v
         +-------------------+
         | tools.py          |
         | discover_tools()  |
         | create_tool_fn()  |<--- exec() for dynamic signatures
         | make_tool()       |
         | _route_tool_call()|---> adapter.request(TX) ---> Matrix
         +-------------------+
                    |
                    v
         +-------------------+     +-------------------+
         | pydantic_ai.Agent |     | NetworkAdapter     |
         | .run() / .stream()|     | .request() / .inbox|
         +-------------------+     +-------------------+
```

**Files read (all):** `__init__.py`, `mixin.py`, `actor.py`, `tools.py`, `deps.py`, `schema_ext.py`, `tool_model.py`, `config.py`, `tests/conftest.py`, `tests/test_mixin.py`, `tests/test_tools.py`, `tests/test_agent_actor.py`, `example_grants/main.py`, `example_grants/tests/test_agent_run.py`, `example_chat/models/conversation.py`, `network_adapter.py`, `proto_schema.py`, `actor.py`.

---

## 2. Potential Bugs

### 2.1 `run_stream()` adapter cleanup may leak on early generator exit without `aclose()`

**File:** `mixin.py:513-532` (run_stream)
**Code:**
```python
try:
    ...
    async for chunk in instance.agentic_stream(...):
        yield chunk
finally:
    root._children.pop(adapter_addr, None)
```

**Issue:** `run_stream()` is an async generator. The `finally` block only runs when the generator is properly closed (via `aclose()` or full exhaustion). If a caller abandons the generator without calling `aclose()` -- e.g., an HTTP handler that disconnects or an exception in the consumer -- the adapter remains registered in `root._children` until GC collects the generator object and triggers the finalization. In CPython, GC is prompt; in PyPy or under memory pressure, this could leak adapters indefinitely.

The test at `test_mixin.py:607-618` explicitly calls `await gen.aclose()`, demonstrating awareness of this risk, but production HTTP handlers may not.

**Likelihood:** Possible (depends on framework layer cleanup behavior)
**Impact:** Adapter leak in Matrix children dict; stale entries accumulate over time

### 2.2 `agentic_stream()` catches all exceptions but does not clean up pydantic_ai resources

**File:** `mixin.py:577-652` (agentic_stream)
**Code:**
```python
try:
    ...
    async with ai_agent.run_stream(task, **run_kwargs) as result:
        async for text in result.stream_text(delta=True):
            yield ...
        ...
except Exception as e:
    yield {'name': 'error', 'data': {'message': str(e), ...}, ...}
finally:
    if owns_adapter:
        root._children.pop(adapter._addr, None)
```

**Issue:** The `except Exception` at line 644 catches everything, including `KeyboardInterrupt` if wrapped, and yields an error chunk instead of propagating. This is intentional for resilience, but it means that if `ai_agent.run_stream()` context manager raises during `__aenter__` or `__aexit__`, the exception is swallowed. The error chunk's `message` field is `str(e)` which may expose internal details (LLM API keys in error messages, stack info).

**Likelihood:** Possible
**Impact:** Silent swallowing of unexpected errors; potential info leak in error messages

### 2.3 `_resolve_tool_addrs()` batch fetch uses `list(ids=href_ids)` which may not be supported

**File:** `actor.py:95-99`
```python
if href_ids:
    tools = tool_cls.list(ids=href_ids)
    records = tools['data'] if isinstance(tools, dict) else tools
```

**Issue:** The `list(ids=href_ids)` call passes an `ids` keyword argument to `StorableMixin.list()`. This relies on the storage layer supporting an `ids` filter. If `list()` does not accept this parameter, it silently falls through to returning all records. I could not verify that `SQLiteStorage.list()` supports an `ids` parameter -- if it does not, every tool in the table would be returned, leading to incorrect tool resolution.

**Likelihood:** Possible (depends on StorableMixin.list() signature)
**Impact:** Wrong tools resolved from DB if `ids` filter is ignored

### 2.4 `target()` called on class creates an empty instance with no storage context

**File:** `mixin.py:331-332`
```python
if isinstance(target, type):
    instance = target()
```

When `run()` is called at the class level (e.g., `Product.run(task='...')`), it creates an ephemeral instance via `target()`. This instance has default field values and no database identity. If `agentic()` or any tool callback tries to access `self.id` or other instance state, it gets defaults (typically `None` for id). This is documented behavior but could surprise callers.

**Likelihood:** Unlikely (documented)
**Impact:** Confusing behavior if instance-specific operations are attempted on class-level runs

### 2.5 `_build_schema_text` accesses `__tablename__` from schema dict, not class

**File:** `mixin.py:52`
```python
tablename = schema.get('__tablename__', cls.__name__)
```

The schema dict uses `__tablename__` as a key (with double underscores). This is a Python dunder convention used as a dict key, which is unusual but consistent with the schema pipeline's `metadata()` stage. Not a bug, but a coupling to the schema dict format that could break if the metadata stage changes the key name.

**Likelihood:** Unlikely
**Impact:** Minor (wrong tablename in LLM context text)

---

## 3. Edge Cases

| Scenario | Current Behavior | Risk |
|----------|-----------------|------|
| **Empty tools list** | `discover_tools([], root)` returns `[]`; `agentic()` logs warning, proceeds with no tools | Safe. LLM runs without tools. |
| **Missing Matrix** | `RuntimeError("No Matrix root")` in both `run()` and `agentic()` | Safe. Clear error. |
| **Concurrent runs** | Each run creates a unique adapter via UUID; tested in `TestConcurrentRuns` | Safe. UUIDs prevent collision. |
| **Large schemas** | `_build_schema_text()` iterates all properties; no truncation on field count | Possible token overflow for LLMs with small context windows. No guard. |
| **Malformed hrefs** | `_resolve_tool_addrs()` catches `ValueError`/`TypeError` on int parse, logs warning | Safe but silently skips bad tools. |
| **Invalid LLM string** | Pydantic AI raises on unknown provider; `agentic()` lets it propagate; `agentic_stream()` catches and yields error chunk | Inconsistent: `agentic()` raises, `agentic_stream()` yields error. |
| **tools list with only self** | `caller_addr` exclusion removes it; agent gets zero tools | Warning logged. LLM proceeds without tools. |
| **Duplicate tool names** | Multiple actors with same tablename prefix could generate `xxx_create` collisions | Pydantic AI may reject duplicate tool names. No dedup on tool_name. |
| **AgentActor with empty prompt** | `prompt` field defaults to `''`; `agentic()` receives empty system prompt | LLM operates without system prompt guidance. |

---

## 4. Test Coverage Analysis

### 4.1 Test Inventory

| File | Classes | Test Methods | Lines |
|------|---------|-------------|-------|
| `test_mixin.py` | 8 | 29 | 712 |
| `test_tools.py` | 8 | 19 | 485 |
| `test_agent_actor.py` | 6 | 20 | 409 |
| `conftest.py` | - | 3 fixtures | 43 |
| **Total** | **22** | **68** | **1649** |

### 4.2 What IS Tested

- Mixin injection via `__init_subclass__` (5 tests)
- `ctx()` class vs instance, prompt prepend, relationships, methods (7 tests)
- `tools()` self/neighbor/extra discovery, dedup, disable flags (7 tests)
- `agentic()` direct call, adapter passthrough, message history, no-matrix error, tool calling (5 tests)
- `run()` zero-config, overrides, adapter lifecycle, cleanup on error, class vs instance (6 tests)
- Concurrent runs isolation (1 test)
- User auth propagation through tool TX (1 test)
- `run_stream()` chunk yielding, adapter cleanup, auto-discovery (3 tests)
- `agentic_stream()` text chunks, done chunk with usage, error chunk (3 tests)
- Tool discovery: CRUD, methods, multi-actor, missing actor, empty list, id param (6 tests)
- Tool function generation: typed params, ordering, no params, type mapping, async (5 tests)
- `make_tool()` Pydantic AI wrapper (1 test)
- `_route_tool_call` error handling and missing actor (2 tests)
- Edge cases: all-optional params, invalid param names, special char descriptions, hyphenated names (4 tests)
- Method required params from schema (2 tests)
- Loop detection: self-exclusion, AgentActor run exclusion, exclude set (4 tests)
- AgentActor: class structure, CRUD, run with/without tools, schema extension (13 tests)
- `_resolve_tool_addrs()` from instances, strings, hrefs, empty (4 tests)

### 4.3 What is NOT Tested (Gaps)

| Gap | Risk | Priority |
|-----|------|----------|
| **`run()` 3-tier config cascade with all tiers active** | Config from `AGENT_DEFAULTS`, `__agent__` dict, AND kwargs simultaneously | Medium |
| **`result_type` (structured output)** | `agentic()` passes `output_type` to Agent but no test verifies structured output works | Medium |
| **`constraints` with `max_iterations` actually limiting** | Test passes constraints but TestModel completes in 1-2 rounds; no test for hitting the limit | Medium |
| **`neighbor_depth > 1`** | Config key exists in `AGENT_DEFAULTS` and `schema_ext.py` safe_keys but is never read in `tools()` | High -- dead config |
| **`N3TX_AGENT_DEFAULTS` env var override** | `config.py:34-36` parses JSON from env but no test | Low |
| **Tool name collision across actors** | Two actors with overlapping method names could produce duplicate tool names | Medium |
| **`_build_instance_text` with non-serializable fields** | `model_dump()` fallback to `str()` but `json.dumps(default=str)` could still fail | Low |
| **`agentic()` with `result_type` AND `message_history`** | Interaction between structured output and multi-turn is untested | Medium |
| **`AgentActor.run()` return type is JSON string** | The `@expose_route` method returns `str`, but the dict serialization via `json.dumps(result, default=str)` could lose types | Low |
| **`run_stream()` with tool-calling LLM** | Streaming + tools is untested (only streaming without tools) | High |
| **Streaming generator cleanup without `aclose()`** | Only tested with explicit `aclose()` call | Medium |
| **Schema extension ordering conflicts** | `@schema_extension(after='methods')` -- no test for stage ordering | Low |

### 4.4 Test Quality Assessment

**Strengths:**
- Tests use `pydantic_ai.models.test.TestModel` correctly for deterministic LLM behavior
- `conftest.py` properly isolates Matrix/Actor state between tests (save/restore pattern)
- File-based SQLite via `tmp_path` avoids the `:memory:` separate-connection gotcha
- Tests verify both positive paths and error conditions

**Weaknesses:**
- Several tests assert only `'answer' in result` without checking the value -- they verify structure but not semantic correctness
- `test_agent_run.py:54` has `assert result["messages"] >= 2` which compares a list to an int (will always be True since list `>=` int is truthy in Python). This is a bug in the test itself.
- `TestRunStream.test_adapter_cleanup` requires manual `aclose()` -- no test for what happens without it
- No negative test for passing invalid `result_type` (non-Pydantic model)

---

## 5. Error Handling Gaps

### 5.1 Bare `except Exception` in `_build_instance_text`

**File:** `mixin.py:163-166`
```python
try:
    data = target.model_dump()
except Exception:
    return ''
```

Silently returns empty string on any failure. If `model_dump()` raises due to a corrupt instance, the LLM gets no instance context with no indication why.

### 5.2 No error boundary in `run()` between config resolution and `agentic()`

**File:** `mixin.py:268-348`

If `target.ctx()` or `target.tools()` raises (e.g., schema generation fails), the exception propagates with the transient adapter already registered. The `finally` block at line 348 cleans up the adapter, but the error message will be about schema generation, not about agent execution -- potentially confusing.

### 5.3 `_route_tool_call` error response format assumption

**File:** `tools.py:219`
```python
raise ModelRetry(response.data.get('message', 'Tool call failed'))
```

Assumes `response.data` is a dict with a `message` key. If an actor handler returns a non-dict error (e.g., a string), `.get()` raises `AttributeError`. This should use `response.data.get('message', ...) if isinstance(response.data, dict) else str(response.data)`.

**Likelihood:** Possible -- depends on actor handler implementations
**Impact:** Unhandled `AttributeError` inside tool call, which pydantic_ai may not recover from gracefully

---

## 6. Security Considerations

### 6.1 `exec()` Usage in `create_tool_function()`

**File:** `tools.py:291`
```python
exec(code, ns)
```

**Assessment:** ACCEPTABLE. The `exec()` call generates tool functions from ToolSpec objects that are derived from model schemas -- our own trusted code, not user input. The namespace is locked down (`ns` contains only `_route`, `_target`, `_method`, `_required`). Parameter names are validated as Python identifiers (line 247). This follows the same pattern as `dataclasses`, `namedtuple`, and `attrs`.

**Residual risk:** If an attacker could control a model's `__tablename__` or method name, they could inject code into the generated function name or description docstring. However, these come from Python class definitions, not user input.

### 6.2 Prompt Injection via Tool Results

Tool results from `_route_tool_call()` are JSON-serialized and returned to the LLM as tool output. If a database record contains adversarial text (e.g., `"title": "Ignore previous instructions and..."`), it flows directly into the LLM context. There is no sanitization layer between tool results and the LLM.

**Mitigation:** This is a known limitation of all tool-calling LLM systems. The framework cannot solve it generically, but it should be documented.

### 6.3 User Context Propagation

**File:** `tools.py:208`
```python
meta = {'user': ctx.deps.user} if ctx.deps.user else {}
```

User auth context is propagated via TX meta to tool calls. This is correct -- the actor system's auth interceptor can check `tx.meta.user`. However, if `ctx.deps.user` contains sensitive fields (password hash, tokens), they flow through the entire actor system. The `user` dict should be scoped to identity fields only.

### 6.4 `schema_ext.py` Correctly Filters Sensitive Config

**File:** `schema_ext.py:31-33`
```python
safe_keys = {'self_tools', 'neighbors', 'neighbor_depth'}
agent_meta['config'] = {k: v for k, v in agent_flag.items() if k in safe_keys}
```

LLM model strings and prompts are correctly excluded from the public schema. Good.

---

## 7. Performance Risks

### 7.1 Per-Run Overhead: Agent + Adapter + Tool Discovery

Every call to `run()` or `agentic()`:
1. Creates a `TX` object just to get a UUID (line 319: `TX(name='', source='', target='').uuid`) -- wasteful
2. Creates a `NetworkAdapter` instance
3. Registers it in Matrix children
4. Calls `discover_tools()` which iterates all actor addresses, calls `.schema()` on each
5. Calls `create_tool_function()` + `exec()` for each tool spec
6. Creates a `pydantic_ai.Agent` object
7. Cleans up adapter

For a model with 5 neighbors and 5 CRUD ops + 2 methods each, that is 35 `exec()` calls per run. Schema generation is cached at the framework level, so step 4 is fast, but the function generation at step 5 is not cached.

**Mitigation:** Cache tool functions by ToolSpec fingerprint. Cache Agent objects for repeated identical configurations.

### 7.2 `_build_schema_text` is O(fields * constraints)

Linear in field count. For a model with 100 fields, this generates a large text block. No truncation or summarization. Could exceed LLM context window.

### 7.3 `discover_tools()` calls `.schema()` per actor

**File:** `tools.py:80`

Each actor's schema is regenerated per discovery call. If schema generation is not memoized, this is expensive. The framework does cache schemas via `_cached_schema` on ProtoModel, so this is acceptable in practice.

---

## 8. Concurrency Issues

### 8.1 `root._children` Dict Mutation

**File:** `mixin.py:327,348`
```python
root.register(adapter)      # line 327
root._children.pop(...)     # line 348
```

`root._children` is a plain Python `dict`. Concurrent `run()` calls mutate it from different coroutines. In CPython with the GIL, dict operations are atomic at the bytecode level, so `pop()` and `__setitem__` won't corrupt the dict. However, this is an implementation detail, not a guarantee. Under free-threaded Python (PEP 703), this could race.

**Likelihood:** Unlikely under CPython GIL; possible under free-threaded builds
**Impact:** Corrupt children dict, lost adapter references

### 8.2 Multiple Concurrent Runs on Same Instance

Nothing prevents `await product.run(task='A')` and `await product.run(task='B')` concurrently on the same instance. Each creates its own adapter and Agent, so they are isolated. However, if either run modifies instance state (e.g., via a tool that updates the same product), the modifications are not coordinated.

**Tested:** `TestConcurrentRuns.test_concurrent_runs_isolated` verifies adapter isolation but only at class level, not instance level with state mutations.

---

## 9. Resource Management

### 9.1 Adapter Lifecycle

| Entry Point | Creates Adapter | Cleans Up | Mechanism |
|------------|----------------|-----------|-----------|
| `run()` | Yes (line 321) | Yes (line 348) | `try/finally` |
| `agentic()` | Conditional (line 393) | Conditional (line 467) | `try/finally` with `owns_adapter` |
| `run_stream()` | Yes (line 505) | Yes (line 532) | `try/finally` in async generator |
| `agentic_stream()` | Conditional (line 560) | Conditional (line 651) | `try/finally` in async generator |

The `owns_adapter` pattern is correct: if the caller provides an adapter, the callee does not clean it up. Duplication of the lifecycle code across 4 methods is a debt item (see Section 10).

### 9.2 Pydantic AI Agent Objects

A new `pydantic_ai.Agent` object is created per run. These are lightweight (no connection pools, no background tasks), so no cleanup is needed. However, Agent construction includes tool schema introspection which is not free.

### 9.3 TX Objects for UUID Generation

**File:** `mixin.py:319`
```python
run_id = TX(name='', source='', target='').uuid
```

Creating a full TX dataclass just to generate a UUID is wasteful. A direct `uuid.uuid4()` call would suffice. This pattern appears 4 times (lines 319, 398, 503, 566).

---

## 10. Technical Debt

### 10.1 Code Duplication: run/run_stream and agentic/agentic_stream

The 3-tier config cascade is duplicated between `run()` (lines 283-308) and `run_stream()` (lines 483-496). The adapter lifecycle is duplicated across all four methods. A refactor extracting `_resolve_config()` and a context manager for adapter lifecycle would eliminate ~60 lines of duplication.

### 10.2 `neighbor_depth` is Configured but Never Used

`config.py:30` defines `'neighbor_depth': 1` in `AGENT_DEFAULTS`. `schema_ext.py:32` includes it in safe_keys. But `tools()` in `mixin.py:253-257` only follows direct `ListRef` relationships -- it never recurses to depth > 1. This is dead configuration that promises functionality it does not deliver.

### 10.3 Inconsistent Error Handling Between Sync and Streaming

`agentic()` raises exceptions to the caller. `agentic_stream()` catches all exceptions and yields an error chunk. This inconsistency means callers must handle errors differently depending on the execution mode.

### 10.4 `AgentActor.run()` Returns JSON String

**File:** `actor.py:129`
```python
return json.dumps(result, default=str)
```

The `@expose_route` decorator expects a return value that becomes the HTTP response. Returning a JSON string means the route layer will double-serialize it (wrapping the string in quotes). The mixin's `agentic()` returns a dict, but `AgentActor.run()` converts it to a string. This impedance mismatch suggests the route layer handles string returns specially, but it's a fragile coupling.

---

## 11. Extension Points

### 11.1 Where New Functionality Can Be Added

| Extension | How | Difficulty |
|-----------|-----|-----------|
| **Custom tools** | Add actor addresses to `__agent__['tools']` list | Trivial |
| **New LLM provider** | Pass provider string or `pydantic_ai.Model` instance to `run(llm=...)` | Trivial |
| **Custom prompt** | Set `__agent__['prompt']` or pass `run(prompt=...)` | Trivial |
| **Add constraints** | Set `__agent__['constraints']` or pass `run(constraints=...)` | Trivial |
| **Guardrails/middleware** | Override `run()` on the model class (it's the policy layer) | Easy |
| **Result processors** | Wrap `agentic()` call in `run()` override | Easy |
| **Tool interceptors** | Use actor `use()` interceptors on target actors | Easy |
| **New schema metadata** | Use `@schema_extension` decorator | Easy |
| **Structured output** | Pass `result_type=MyModel` to `run()` | Easy |
| **Custom tool functions** | Create `ToolSpec` manually and pass to `make_tool()` | Medium |
| **Multi-agent orchestration** | Not built-in; requires manual coordination of multiple `run()` calls | Hard |
| **Replace pydantic_ai** | Requires rewriting `agentic()`, `agentic_stream()`, tool generation | Hard |
| **Change TX routing** | Deep coupling to `_route_tool_call()` and NetworkAdapter | Hard |

### 11.2 The `run()` / `agentic()` Split as Extension Seam

The cleanest extension point is overriding `run()`. The split between `run()` (policy) and `agentic()` (engine) is the key design decision for extensibility:

```python
class AuditedProduct(ActorModel):
    __agent__ = True

    @fullmethod
    async def run(target, task, **kwargs):
        # Pre-processing: audit log, rate limit, input validation
        log_agent_run(task, kwargs.get('user'))

        # Delegate to engine
        result = await AgentMixin.run(target, task=task, **kwargs)

        # Post-processing: cost tracking, output filtering
        track_cost(result['usage'])
        return result
```

This pattern works because `run()` is a `@fullmethod` that can be overridden per-class. The `AgentActor.run()` already demonstrates this pattern (lines 103-129).

---

## 12. Integration Boundaries

### 12.1 Dependency Graph

```
INBOUND (what agents depends on):

  proto_model.py ----[__init_subclass__]----> mixin.py (AgentMixin injection)
  proto_schema.py ---[@schema_extension]----> schema_ext.py (agent stage)
  actor.py ----------[Actor base class]-----> actor.py (AgentActor extends ActorModel)
  network_adapter.py [request/response]-----> mixin.py (adapter lifecycle)
  introspection.py --[get_list_fields]------> mixin.py (neighbor discovery)
  tx.py ------------[TX dataclass]--------->> tools.py (message routing)
  config.py --------[AGENT_DEFAULTS]--------> mixin.py (3-tier cascade)
  storable_mixin.py [CRUD operations]-------> tools.py (discover_tools checks)
  decorators.py ----[expose_route]----------> tools.py (method discovery)

OUTBOUND (what depends on agents):

  example_grants/main.py ----[imports AgentActor, AgentTool]
  example_chat/models/conversation.py ----[extends AgentActor]
  proto_model.py ----[conditional import of AgentMixin in __init_subclass__]
```

### 12.2 Boundary Coupling Assessment

| Boundary | Coupling | Assessment |
|----------|---------|------------|
| **Agents -> Actor system** | Medium. Uses `Actor.root()`, `root._children`, `root.register()`. Accesses private `_children` dict directly (`root._children.pop()`). | Could use a public `unregister()` method instead of reaching into `_children`. |
| **Agents -> Schema pipeline** | Low. Uses `@schema_extension` decorator. One-way: schema_ext reads model attrs, does not modify them. | Clean boundary. |
| **Agents -> Storage layer** | Low. Only `discover_tools()` checks `issubclass(cls, StorableMixin)`. `AgentActor._resolve_tool_addrs()` calls `tool_cls.list()`. | Clean boundary. |
| **Agents -> Route layer** | Low. `AgentActor.run()` uses `@expose_route`. No direct route manipulation. | Clean boundary. |
| **Agents -> Pydantic AI** | High. Direct dependency on `Agent`, `UsageLimits`, `Tool`, `ModelRetry`, `TestModel`. Version-locked to Pydantic AI API surface. | Acceptable for a v0.10 subsystem. Would benefit from an adapter layer if Pydantic AI API changes. |
| **Agents -> Frontend** | None. Schema extension adds `agent` section to JSON schema. Frontend reads it. No direct JS imports. | Clean boundary via schema contract. |
| **Agents -> Config** | Low. Reads `AGENT_DEFAULTS` dict. Does not modify it. | Clean boundary. |

### 12.3 Proto_model Injection Coupling

**File:** `proto_model.py:89-94`
```python
__agent__ = getattr(cls, '__agent__', False)
if __agent__:
    from n3tx.core.agents.mixin import AgentMixin
    if not issubclass(cls, AgentMixin):
        cls.__bases__ = (AgentMixin,) + cls.__bases__
```

The conditional import means the agents package is only loaded when a model uses `__agent__`. This is good for tree-shaking but creates a hidden dependency: `proto_model.py` knows about agents but agents does not know about proto_model. The `__init__.py` side-effect import of `schema_ext` (line 21) registers the schema stage at import time.

---

## 13. What's Easy to Change

1. **Add a new tool type** -- Create a new actor with `@expose_route` methods, add its tablename to `__agent__['tools']`. Zero framework changes.

2. **Change LLM provider** -- Pass any Pydantic AI-compatible model string or object to `run(llm=...)`. The framework is provider-agnostic.

3. **Customize prompt** -- Three options: `__agent__['prompt']`, `run(prompt=...)`, or override `ctx()`.

4. **Add cost tracking** -- Override `run()`, read `result['usage']` after `agentic()` returns.

5. **Add tool access control** -- Use actor `use()` interceptors on target actors. Tool calls flow through normal TX routing, so existing auth interceptors apply.

---

## 14. What's Hard to Change

1. **Tool routing mechanism** -- Tools are deeply coupled to `_route_tool_call()` -> `adapter.request(TX)` -> Matrix routing. Changing to direct function calls or HTTP would require rewriting `create_tool_function()` and the entire `tools.py` module.

2. **Replace Pydantic AI** -- `agentic()` and `agentic_stream()` use Pydantic AI's `Agent.run()` and `Agent.run_stream()` APIs directly. The `Tool` wrapper, `RunContext[AgentDeps]` pattern, and `ModelRetry` exception are all Pydantic AI-specific. Replacing it would require rewriting ~150 lines across `mixin.py` and `tools.py`.

3. **TX message format** -- Tool calls use TX with specific meta conventions (`meta.user`, `meta.req` for correlation). Changing the TX format would break tool routing.

4. **Adapter lifecycle pattern** -- The create-register-use-cleanup pattern is duplicated across 4 methods. Extracting it requires understanding the async generator semantics of `run_stream()` and `agentic_stream()`, which cannot use a simple context manager (async generators and context managers interact poorly).

---

## 15. Feature Gaps

### 15.1 Multi-Agent Orchestration

There is no built-in mechanism for agent-to-agent communication. An agent can call tools on other actors, but cannot delegate reasoning to another agent. The `AgentActor.run` method is auto-excluded from tool discovery (line 95-96 in `tools.py`), which prevents naive recursion but also prevents intentional delegation.

**To add:** A `delegate` tool type that wraps another agent's `run()` as a tool, with cycle detection via the `caller_addr` chain.

### 15.2 Observability / Tracing

No structured logging of:
- Which tools were discovered and presented to the LLM
- Which tools the LLM called and what they returned
- Token usage per tool call vs. reasoning
- Wall-clock time per run

The `logger.warning()` calls in `tools.py` are the only instrumentation.

### 15.3 Tool Result Caching

Every tool call goes through `adapter.request(TX)` to the actor system. Repeated identical queries (e.g., `grants_list` with same params) hit the database every time. No caching layer.

### 15.4 Cost Tracking and Budgets

`constraints['max_iterations']` limits request count via `UsageLimits`. There is no:
- Token budget (max input + output tokens)
- Dollar budget (cost per model * tokens)
- Per-tool-call limits
- Cumulative tracking across runs

### 15.5 Guardrails Beyond Iteration Limits

No input/output content filtering, no PII detection, no output validation beyond `result_type`. The `run()` policy layer is the intended extension point, but no reference implementation exists.

### 15.6 `neighbor_depth > 1`

As noted in Section 10.2, the config exists but the code does not implement recursive neighbor discovery. Adding it would require a BFS/DFS traversal of `get_list_fields()` with cycle detection.

---

## 16. Cross-Cutting Concerns

### 16.1 Auth

User context flows through: `run(user=dict)` -> `AgentDeps.user` -> `TX.meta.user` -> actor auth interceptor. This is correct and consistent with the two-tier auth pattern. The agent itself is not authorized -- authorization happens at the tool-call level when the target actor processes the TX.

### 16.2 Logging

Agents use `logging.getLogger('n3tx.agents')`. Tool discovery warnings log to the same logger. No structured logging (no JSON, no trace IDs, no correlation between runs).

### 16.3 Configuration

The 3-tier cascade (`AGENT_DEFAULTS` < `__agent__` dict < `run()` kwargs) is clean but undocumented in terms of precedence for nested dicts. `constraints` uses `dict.update()` which means kwargs completely override the same key from lower tiers -- no deep merge.

### 16.4 Frontend Schema Contract

The `agent` section in the schema (from `schema_ext.py`) is consumed by the frontend to show agent-specific UI. The contract is:
```json
{
  "agent": {
    "enabled": true,
    "config": {"self_tools": true, "neighbors": true},
    "methods": ["run", "run_stream", "ctx", "tools"],
    "run_endpoint": "/agents/{id}/run"
  }
}
```

This is a read-only contract -- the frontend cannot configure agent behavior, only display it. The `methods` list is hardcoded (line 41 of `schema_ext.py`), not discovered from the actual class, so adding a new agent method requires updating this list manually.

---

## 17. Summary of Findings

### Critical (should fix before v1.0)
1. **`neighbor_depth` is dead config** -- promises functionality that doesn't exist (Section 10.2)
2. **`_route_tool_call` error data format assumption** -- can raise `AttributeError` on non-dict error data (Section 5.3)
3. **Test bug in `test_agent_run.py:54`** -- `result["messages"] >= 2` compares list to int (Section 4.4)

### Important (should address in near term)
4. **Code duplication** across `run/run_stream/agentic/agentic_stream` -- ~120 lines of near-identical config + adapter code (Section 10.1)
5. **No observability** -- no structured logging of tool discovery, tool calls, or usage (Section 15.2)
6. **Streaming adapter cleanup depends on `aclose()`** (Section 2.1)
7. **Inconsistent error handling** between sync and streaming paths (Section 10.3)
8. **Missing tests** for streaming + tools, result_type, full 3-tier cascade (Section 4.3)

### Minor / Low Risk
9. **TX created just for UUID** -- use `uuid.uuid4()` directly (Section 9.3)
10. **`schema_ext.py` hardcodes method list** (Section 16.4)
11. **No prompt injection mitigation** documentation (Section 6.2)
12. **Per-run overhead** from uncached tool function generation (Section 7.1)
