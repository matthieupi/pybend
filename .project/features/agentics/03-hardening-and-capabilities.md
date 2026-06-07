# Agent Primitives: Hardening & Capabilities

**Status:** Plan
**Date:** 2026-03-08
**Depends on:** 02-agent-mixin-proposal.md (streaming, ctx/tools, agentic rename)
**Branch:** `v0.9`

---

## Context

The agent system (AgentMixin, AgentActor, tool discovery) was built during v0.9 as the foundation for LLM-powered reasoning within the actor model. It works end-to-end (example_grants demonstrates full CRUD + tool calling), but a thorough code review reveals correctness bugs, missing test coverage, and capabilities that should be added before the primitives are production-ready.

This document covers **three concerns**:
1. Bug fixes and code quality improvements in existing code
2. Test hardening to fill coverage gaps
3. New capabilities: structured output, run history, agent-to-agent delegation

Streaming is handled by `02-agent-mixin-proposal.md` (the `agentic(stream=True)` + `Agent.iter()` approach).

---

## Phase 1: Bug Fixes & Code Quality

### ~~1.1 Wasteful UUID generation~~ — REMOVED

Deferred. The TX instantiation pattern will be useful later when we add richer run tracking. Not worth optimizing now.

---

### 1.2 Method parameters all marked required

**Files:** `src/n3tx/core/models/proto_model.py:146-177`, `src/n3tx/core/agents/tools.py:155`

**Problem:** `__n3tx_methods_json_signature__()` doesn't emit a `required` list in method entries. Then `_method_tool_specs()` does `required = list(filtered.keys())`, treating ALL params as required. Parameters with defaults (e.g., `selector: str = 'body'` in `WebTools.extract()`) are incorrectly forced-required for the LLM.

**Fix in proto_model.py** (line 146-177): Compute required list from `param.default is inspect.Parameter.empty`, add to `method_entry`:

```python
parameters = {}
required_params = []
for name, param in sig.parameters.items():
    if name in ('cls', 'self', 'user'):
        continue
    ptype = type_hints.get(name, param.annotation)
    parameters[name] = pydantic_schema_for_type(ptype)
    record_model_type(cls, ptype)
    if param.default is inspect.Parameter.empty:
        required_params.append(name)

method_entry = {
    'route': endpoint_info['route'],
    'methods': endpoint_info['methods'],
    'scope': method_type,
    'parameters': parameters,
    'required': required_params,  # NEW
    'returns': return_type_schema,
}
```

**Fix in tools.py** (line 155): Read from schema instead of treating all as required:

```python
# Before:
required = list(filtered.keys())

# After:
schema_required = set(method_info.get('required', []))
required = [k for k in filtered if k in schema_required] if schema_required else list(filtered.keys())
```

**Impact:** Schema output gains a new `required` key in method entries. Additive — frontend consumers that ignore unknown keys are unaffected. Verify `<ntx-method>` and `Formidable` don't break.

---

### 1.3 Optional param filtering too aggressive

**File:** `src/n3tx/core/agents/tools.py:243`

```python
# Before: strips 0, False, "" alongside None
_d = {k: v for k, v in _d.items() if v is not None}

# After: only strip None for optional params
_d = {k: v for k, v in _d.items() if not (v is None and k not in _required)}
```

Inject `_required` set into the exec namespace:

```python
ns = {
    '_route': _route_tool_call,
    '_target': spec.actor_addr,
    '_method': spec.method_name,
    '_required': set(spec.parameters.get('required', [])),  # NEW
}
```

---

### 1.4 N+1 query in href resolution — add `ids` param to `list()`

**Files:**
- `src/n3tx/core/storage/abstract_storage.py:21` — add `ids` param to abstract `list()`
- `src/n3tx/core/storage/sqlite_storage.py:161` — implement `WHERE id IN (?, ...)` when `ids` provided
- `src/n3tx/core/models/storable_mixin.py:92` — pass `ids` through to storage
- `src/n3tx/core/agents/actor.py:84-88` — use `tool_cls.list(ids=[...])` instead of per-ID `.get()`

**Problem:** `_resolve_tool_addrs()` fetches each tool individually via `tool_cls.get(tool_id)` in a loop (N+1 queries).

**Fix:** Extend `StorableMixin.list()` and `SQLiteStorage.list()` to accept an optional `ids` parameter. When provided, adds `WHERE id IN (?, ?, ...)` to the query. Default behavior (no `ids`) is unchanged.

```python
# storable_mixin.py
@classmethod
def list(cls, sql_filter=None, limit=None, offset=None, populate=None, ids=None):
    return cls.storage.list(cls, sql_filter=sql_filter, limit=limit,
                            offset=offset, populate=populate, ids=ids)

# sqlite_storage.py
def list(self, model_class, sql_filter=None, limit=None, offset=None,
         populate=None, ids=None):
    ...
    if ids is not None and ids:
        placeholders = ','.join('?' * len(ids))
        id_clause = f"id IN ({placeholders})"
        if sql_filter and sql_filter[0]:
            clause = f"({sql_filter[0]}) AND {id_clause}"
            filter_params = list(sql_filter[1] or []) + list(ids)
            sql_filter = (clause, filter_params)
        else:
            sql_filter = (id_clause, list(ids))
    ...
```

Then in `_resolve_tool_addrs()`:

```python
# Collect all href IDs, batch fetch once
if href_ids:
    tools = tool_cls.list(ids=href_ids)
    records = tools['data'] if isinstance(tools, dict) else tools
    for tool in records:
        tool_addrs.append(tool.target)
```

---

### 1.5 Loose type hint on AgentDeps.adapter

**File:** `src/n3tx/core/agents/deps.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from n3tx.core.api.network_adapter import NetworkAdapter

@dataclass
class AgentDeps:
    adapter: NetworkAdapter  # was: Any
    user: Optional[dict]
    agent_addr: str
```

---

### 1.6 Inconsistent Optional + mutable default

**File:** `src/n3tx/core/agents/actor.py:60`

```python
# Before:
tools: Optional[ListRef[AgentTool]] = Field(default=[])

# After:
tools: ListRef[AgentTool] = Field(default=[])
```

Verify no code passes `tools=None`.

---

### 1.7 Automatic loop detection in tool discovery

**Files:** `src/n3tx/core/agents/tools.py`, `src/n3tx/core/agents/mixin.py`

When discovering tools from AgentActor, `agents_run` shows up as a callable tool — which would cause infinite recursion if the LLM calls it. Instead of requiring manual `__tool_exclude__` flags, detect loops automatically.

**Two automatic detection mechanisms:**

**A. Self-exclusion:** The calling agent's own address is passed to `discover_tools()` and skipped entirely. An agent never needs itself as a tool.

```python
# mixin.py — pass caller_addr to discover_tools
tool_specs = discover_tools(tools, root, caller_addr=agent_addr)

# tools.py
def discover_tools(actor_addrs: list, root, caller_addr: str = None) -> list[ToolSpec]:
    ...
    for addr in actor_addrs:
        if addr == caller_addr:
            logger.debug("Tool discovery: skipping self '%s'", addr)
            continue
        ...
```

**B. AgentActor detection:** Any `AgentActor` subclass's `run`/`stream_run` methods are meta-operations (they trigger reasoning loops), not business tools. Auto-exclude them — no manual flags needed.

```python
# tools.py — in discover_tools(), after getting cls
from n3tx.core.agents.actor import AgentActor

agent_methods = set()
if isinstance(cls, type) and issubclass(cls, AgentActor):
    agent_methods = {'run', 'stream_run'}

specs.extend(_method_tool_specs(addr, tablename, model_name, schema, exclude=agent_methods))
```

Update `_method_tool_specs()` to accept the exclude set:

```python
def _method_tool_specs(addr, tablename, model_name, schema, exclude=None):
    exclude = exclude or set()
    specs = []
    for method_name, method_info in schema.get('methods', {}).items():
        if method_name in exclude:
            continue
        ...
```

**Why this is better than manual flags:**
- No `__tool_exclude__` needed on any class — detection is structural
- Works for subclasses of AgentActor without them having to redeclare
- Self-exclusion prevents a whole category of bugs (agent discovers its own CRUD as tools, then calls itself in a loop)
- The pattern is transparent: log messages explain what was skipped and why

---

## Phase 2: Test Hardening

All unit tests in `src/n3tx/core/agents/tests/`. Integration tests in `example_grants/tests/`.

### T1. ModelRetry on tool error

`_route_tool_call()` raises `ModelRetry` when `response.is_error` (tools.py:194-196). No test covers this path.

```python
# test_tools.py — new TestRouteToolCall class
@pytest.mark.asyncio
async def test_error_response_raises_model_retry(self, fresh_matrix):
    """_route_tool_call raises ModelRetry when tool returns error TX."""
    # Register target actor that returns error TX
    # Create adapter, build mock RunContext with AgentDeps
    # Call _route_tool_call, assert ModelRetry raised with error message
```

### T2. Concurrent agent runs

Verify adapter isolation — each run gets its own transient adapter.

```python
# test_mixin.py
@pytest.mark.asyncio
async def test_concurrent_runs_isolated(self, fresh_matrix):
    """Multiple concurrent agent_run() calls don't cross-contaminate."""
    # Launch 3 concurrent runs with asyncio.gather
    # Verify all return independently, no adapter collisions
    # Verify all transient adapters cleaned up (no _agent_* in children)
```

### T3. User auth context propagation

Tool TXs should carry `meta.user` through the Matrix.

```python
# test_mixin.py
@pytest.mark.asyncio
async def test_user_context_in_tool_calls(self, fresh_matrix, tmp_path):
    """Tool TX messages carry meta.user from agent_run(user=...)."""
    # Register target actor with interceptor that captures tx.meta
    # Run agent_run(user={'id': 42, 'role': 'admin'})
    # Verify captured TX has correct user
```

### T4. Tool call to missing/erroring actor

```python
# test_tools.py
@pytest.mark.asyncio
async def test_tool_call_to_missing_actor(self, fresh_matrix):
    """_route_tool_call to non-existent actor handles gracefully."""
```

### T5. AgentActor.run() kwargs passthrough

```python
# test_agent_actor.py
@pytest.mark.asyncio
async def test_run_passes_user_to_agent_run(self, ...):
    """run(task=..., user={...}) passes user to agent_run."""

@pytest.mark.asyncio
async def test_run_passes_constraints_override(self, ...):
    """run(task=..., constraints={...}) overrides instance constraints."""
```

### T6. Edge cases for create_tool_function

```python
# test_tools.py
def test_all_optional_params(self): ...
def test_invalid_param_name_skipped(self): ...
def test_description_with_special_chars(self): ...
```

### T7. Multi-tool integration test

```python
# example_grants/tests/test_agent_run.py
@pytest.mark.asyncio
async def test_agent_multi_tool_sequence(self, test_db, seed_data):
    """Agent calls grants_list, then sources_list in sequence."""
    agent = AgentActor.get(seed_data["agent"].id)
    result_str = await agent.call(
        task="Compare grants with sources",
        llm=TestModel(call_tools=['grants_list', 'sources_list']),
    )
    result = json.loads(result_str)
    assert result["usage"]["requests"] >= 2
```

---

## Phase 3: New Capabilities (LATER — after stable base)

> Phase 3 is documented for planning purposes but will not be implemented until Phases 1+2 are complete and stable. Build the foundation first.

### A. Structured Output Support

**Value:** `agent_run()` always returns `{answer: str}`. Many use cases need typed output (parsed Grant, list of URLs, validation result). Pydantic AI supports `result_type` natively.

**File:** `src/n3tx/core/agents/mixin.py`

Add optional `result_type` kwarg:

```python
async def agent_run(self, prompt, tools, task, user=None, **kwargs):
    result_type = kwargs.pop('result_type', str)

    ai_agent = Agent(
        llm,
        system_prompt=prompt,
        deps_type=AgentDeps,
        tools=ai_tools,
        result_type=result_type,  # NEW
    )
    ...
    return {
        'answer': result.output,  # typed when result_type is not str
        ...
    }
```

HTTP endpoint (`AgentActor.run()`) remains string-only. Direct `agent_run()` callers from code get typed output.

**Tests:**

```python
@pytest.mark.asyncio
async def test_agent_run_structured_output(self, fresh_matrix):
    from pydantic_ai.models.test import TestModel
    result = await Scanner.agent_run(
        Scanner, prompt='test', tools=[], task='test',
        llm=TestModel(call_tools=[]),
        result_type=dict,
    )
    # answer should be the structured type, not necessarily a string
    assert 'answer' in result
```

---

### B. Run History / Logging

**Value:** No record of past runs. Debugging, auditing, cost tracking all need logged runs.

**New file:** `src/n3tx/core/agents/run_model.py`

```python
class AgentRun(ActorModel):
    __tablename__ = 'agent_runs'
    __storable__ = True

    agent_id: int = Field(description="ID of the agent that ran")
    task: str = Field(description="The user's task/query")
    answer: str = Field(default='')
    status: str = Field(default='success')  # success | error
    tools_called: list = Field(default=[])   # JSON-serialized list
    usage: dict = Field(default={})          # {input_tokens, output_tokens, requests}
    duration_ms: float = Field(default=0)
```

**In mixin.py:** After `agent_run()` completes, optionally create a run record:

```python
import time

start = time.monotonic()
result = await ai_agent.call(...)
elapsed = (time.monotonic() - start) * 1000

if getattr(self.__class__, '__log_runs__', False):
    from n3tx.core.agents.run_model import AgentRun

    AgentRun.create(AgentRun(
        agent_id=getattr(self, 'id', 0),
        task=task, answer=str(result.output),
        usage={...}, duration_ms=elapsed,
        status='success',
    ))
```

**Opt-in:** `__log_runs__ = True` class variable. AgentActor sets it by default.

**Files changed:**
- New: `src/n3tx/core/agents/run_model.py`
- Modified: `src/n3tx/core/agents/mixin.py` (logging at end of agent_run)
- Modified: `src/n3tx/core/agents/__init__.py` (export AgentRun)
- New: `src/n3tx/core/agents/tests/test_run_model.py`

---

### C. Agent-to-Agent Delegation

**Value:** An agent should be able to use another agent as a tool — e.g., "ask the research agent to find X". Currently agents can only call CRUD and `@expose_route` methods.

**Problem:** If an agent's `run` method is exposed as a tool, calling it creates infinite recursion. Fix 1.7 excludes `run` from tool discovery. But we need a controlled delegation mechanism.

**Design:** In `discover_tools()`, detect AgentActor targets and generate a special `{tablename}_delegate` tool:

```python
# In discover_tools(), after getting cls:
from n3tx.core.agents.actor import AgentActor

if isinstance(cls, type) and issubclass(cls, AgentActor):
    specs.append(ToolSpec(
        actor_addr=addr,
        method_name='run',
        tool_name=f'{tablename}_delegate',
        description=f'Delegate a task to the {model_name} agent',
        parameters={
            'type': 'object',
            'properties': {
                'id': {'type': 'integer', 'description': f'{model_name} instance ID'},
                'task': {'type': 'string', 'description': 'Task to delegate'},
            },
            'required': ['id', 'task'],
        },
    ))
```

**Circular delegation prevention:** Add `depth` counter to `AgentDeps`:

```python
@dataclass
class AgentDeps:
    adapter: NetworkAdapter
    user: Optional[dict]
    agent_addr: str
    depth: int = 0  # NEW — delegation depth
```

In `agent_run()`, pass `depth + 1` when creating deps. In `_route_tool_call()`, check depth before delegation calls. Reject at depth > 3 (configurable via constraints).

**Files changed:**
- `src/n3tx/core/agents/tools.py` — delegation tool spec in `discover_tools()`
- `src/n3tx/core/agents/deps.py` — add `depth` field
- `src/n3tx/core/agents/mixin.py` — pass depth to deps
- `src/n3tx/core/agents/tests/test_tools.py` — test delegation tool discovery
- `src/n3tx/core/agents/tests/test_mixin.py` — test depth limiting

---

## Execution Order

```
Phase 1 (bug fixes — build stable base):
  1.5, 1.6             parallel, trivial
  1.2                   schema change, verify test impact
  1.3                   depends on 1.2 for required set concept
  1.4                   StorableMixin.list(ids=) + batch resolve
  1.7                   auto loop detection in discover_tools

Phase 2 (tests — harden the base):
  T6                    no dependencies, edge cases
  T1, T4                tool error handling
  T5                    kwargs passthrough
  T2, T3                concurrency and auth
  T7                    integration, needs seed data

Phase 3 (capabilities — LATER, after stable base):
  A: Structured output  small, additive
  B: Run history        independent, new model
  C: Delegation         depends on 1.7, needs depth guard
```

---

## Verification

1. **Unit tests:** `cd /workspace/src/n3tx/core && python3 -m pytest agents/tests/ -v`
2. **Framework tests:** `cd /workspace/src/n3tx/core && python3 -m pytest tests/unit/ -v`
3. **Integration tests:** `cd /workspace && python3 -m pytest example_grants/tests/ -v`
4. **Manual:** Start server, create agent via API, call `/agents/1/run`
5. **Schema check:** `curl http://localhost:5000/AgentActor | python3 -m json.tool` — verify `methods.run.required` list, `agent` section

---

## Critical Files

| File | Changes |
|------|---------|
| `src/n3tx/core/agents/mixin.py` | 1.7 pass caller_addr to discover_tools |
| `src/n3tx/core/agents/actor.py` | 1.6 Optional removal |
| `src/n3tx/core/agents/tools.py` | 1.2 required params, 1.3 None filtering, 1.7 auto loop detection |
| `src/n3tx/core/agents/deps.py` | 1.5 type hint |
| `src/n3tx/core/models/proto_model.py:129-179` | 1.2 method required list in schema |
| `src/n3tx/core/storage/abstract_storage.py` | 1.4 add `ids` param to abstract `list()` |
| `src/n3tx/core/storage/sqlite_storage.py` | 1.4 implement `WHERE id IN (...)` |
| `src/n3tx/core/models/storable_mixin.py` | 1.4 pass `ids` through to storage |
| `src/n3tx/core/agents/tests/` | T1-T7 new tests |
| `example_grants/tests/test_agent_run.py` | T7 multi-tool integration |
| *Later:* `src/n3tx/core/agents/run_model.py` | Phase 3 — run history model |
| *Later:* `src/n3tx/core/agents/deps.py` | Phase 3 — delegation depth |
