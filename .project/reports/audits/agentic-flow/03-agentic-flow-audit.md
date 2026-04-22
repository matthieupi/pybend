# Agentic Flow -- Deep Audit Report

**Scope**: `src/n3tx/core/agents/` (mixin.py, actor.py, deps.py, tools.py, schema_ext.py, tool_model.py) + integration boundaries (config.py, network_adapter.py, descriptors.py, proto_schema.py)
**Branch**: v0.9 (commits through 0.10 agent features)
**Date**: 2026-03-09
**Sources**: Architecture & API analysis (01), Quality & Extensibility analysis (02), direct source verification

---

## Executive Summary

The agentic flow subsystem gives any N3TX model LLM-powered self-awareness via a single flag (`__agent__ = True`). It comprises seven modules totaling roughly 950 lines of Python. The architecture follows a clean **policy/engine split** (`run()` vs `agentic()`), a **3-tier config cascade** (global defaults < model-level dict < call-site kwargs), and a **stateless execution model** where each agent run creates and destroys its own adapter, tools, and pydantic-ai Agent instance. The subsystem integrates deeply with the actor system (tool calls route as TX messages through Matrix) and the schema pipeline (an `agent` stage injects metadata for frontend consumption). The design is consistent with the framework's core philosophy: zero-config, transparent, schema-driven.

**The subsystem is well-designed and functional.** Cohesion is high across all modules. The mixin injection pattern mirrors `StorableMixin`, making it instantly familiar. The `fullmethod` descriptor eliminates class/instance duplication. Tool discovery from live actor schemas is elegant -- tools reflect the actual runtime state. The `exec()`-based function generation follows stdlib precedent (`dataclasses`, `namedtuple`) with appropriate input sanitization.

**The most important findings are:** (1) A confirmed test bug (`test_agent_run.py:54`) comparing a list with an integer, which will raise `TypeError` in Python 3 and is currently masked by the test not being exercised in CI. (2) Significant code duplication -- the config cascade is copied verbatim between `run()` and `run_stream()`, and the adapter lifecycle pattern is repeated four times across the entry points. (3) The `neighbor_depth` config key is declared, documented, and exposed in schema output but never read by any code -- a dead feature that violates "transparent, not magical." (4) `AgentActor.run()` returns a JSON string while `AgentMixin.run()` returns a dict -- the same method name with different return types creates a fragile API boundary.

**Top 3 recommendations:** (1) Fix the test bug immediately (5 minutes). (2) Extract the duplicated config cascade and adapter lifecycle into `_resolve_config()` and an `_adapter_context()` context manager (1 hour, eliminates ~60 lines of duplication and 4 copies of the same bug-prone pattern). (3) Either implement `neighbor_depth` or remove it from config, schema extension, and CLAUDE.md (1 hour to remove, 2-3 hours to implement).

---

## Component Overview

### Module Inventory

| Module | Primary Export | Lines | Role |
|--------|---------------|-------|------|
| `mixin.py` | `AgentMixin` | ~653 | Core mixin: ctx, tools, run, agentic, streaming |
| `actor.py` | `AgentActor` | ~130 | DB-storable agent instances with /run endpoint |
| `tools.py` | `discover_tools`, `make_tool` | ~312 | Schema-to-tool pipeline: discovery, generation, routing |
| `deps.py` | `AgentDeps` | ~28 | 3-field dataclass bridging pydantic-ai to N3TX |
| `schema_ext.py` | `agent()` | ~44 | Schema pipeline extension for agent metadata |
| `tool_model.py` | `AgentTool` | ~33 | Thin model storing tool actor addresses |
| `__init__.py` | (re-exports) | ~27 | Public API + schema_ext side-effect import |
| `config.py` (partial) | `AGENT_DEFAULTS` | ~6 | Global agent config defaults |

### Subsystem Architecture Diagram

```
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                           EXTERNAL DEPENDENCIES                                 │
  │  pydantic_ai (Agent, Tool, UsageLimits, ModelRetry, RunContext, TestModel)      │
  │  descriptors.py (fullmethod, fullproperty)                                      │
  │  network_adapter.py (NetworkAdapter)                                            │
  │  actor.py (Actor, Actor.root())   tx.py (TX)                                    │
  └──────────────────────┬──────────────────────────────────────────────────────────┘
                         │
  ┌──────────────────────┼──────────────────────────────────────────────────────────┐
  │                      │   agents/                                                │
  │                      ▼                                                          │
  │  ┌──────────────────────────────────────────────┐                               │
  │  │           config.py: AGENT_DEFAULTS           │                               │
  │  │  {self_tools, neighbors, neighbor_depth, llm} │                               │
  │  └──────────────────┬───────────────────────────┘                               │
  │                     │ reads defaults                                             │
  │                     ▼                                                            │
  │  ┌──────────────────────────────────────────────┐                               │
  │  │          mixin.py: AgentMixin                 │                               │
  │  │                                               │                               │
  │  │  @fullmethod ctx()  ──► _build_schema_text()  │                               │
  │  │                     ──► _build_instance_text() │                               │
  │  │  @fullmethod tools() ──► addrs from schema    │                               │
  │  │  @fullmethod run()   ──► config cascade       │──── creates ───► adapter      │
  │  │           └─► agentic()  (engine)             │                    │           │
  │  │  @fullmethod run_stream()──► config cascade   │                    │           │
  │  │           └─► agentic_stream() (engine)       │                    │           │
  │  └──────────────┬───────────────────────────────┘                    │           │
  │                 │ calls                                               │           │
  │                 ▼                                                     │           │
  │  ┌──────────────────────────────────────────────┐                    │           │
  │  │          tools.py: Tool Pipeline              │                    │           │
  │  │                                               │                    │           │
  │  │  discover_tools(addrs, root)                  │                    │           │
  │  │    └─► _crud_tool_specs()                     │                    │           │
  │  │    └─► _method_tool_specs()                   │                    │           │
  │  │  create_tool_function(spec) ──► exec()        │                    │           │
  │  │  make_tool(spec) ──► pydantic_ai.Tool         │                    │           │
  │  │  _route_tool_call(ctx, ...) ─────────────────►├── adapter.request()│           │
  │  └──────────────────────────────────────────────┘         │          │           │
  │                                                           ▼          ▼           │
  │  ┌──────────────────────┐   ┌──────────────┐    ┌──────────────────┐            │
  │  │ deps.py: AgentDeps   │   │ tool_model.py│    │ Matrix (routing) │            │
  │  │ adapter, user, addr  │   │ AgentTool     │    │ ──► target actor │            │
  │  └──────────────────────┘   │ target, desc  │    │     handler()    │            │
  │                              └───────┬──────┘    └──────────────────┘            │
  │                                      │ ListRef                                   │
  │  ┌───────────────────────────────────┴──────────────────────┐                    │
  │  │          actor.py: AgentActor                             │                    │
  │  │  __storable__, __agent__ = True                           │                    │
  │  │  name, prompt, tools (ListRef[AgentTool]), llm, constraints│                   │
  │  │  @expose_route('/run') run() ──► self.agentic()           │                    │
  │  │  _resolve_tool_addrs() ──► href batch fetch               │                    │
  │  └──────────────────────────────────────────────────────────┘                    │
  │                                                                                  │
  │  ┌──────────────────────────────────────────────┐                               │
  │  │      schema_ext.py: @schema_extension         │                               │
  │  │  agent(cls, schema) ──► schema['agent'] = ... │                               │
  │  │  Side-effect imported in __init__.py           │                               │
  │  └──────────────────────────────────────────────┘                               │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Findings

### Critical Issues

#### F-01: Test Bug -- List Compared to Integer

- **Finding**: `test_agent_run.py:54` asserts `result["messages"] >= 2` where `result["messages"]` is a `list`, not an `int`. In Python 3, `list >= int` raises `TypeError`.
- **Evidence**: `example_grants/tests/test_agent_run.py:54`:
  ```python
  assert result["messages"] >= 2  # at least prompt + response
  ```
  The `messages` key in the return dict is always a list (defined at `mixin.py:462`: `'messages': all_messages`). The correct assertion is `len(result["messages"]) >= 2` or `result["message_count"] >= 2`.
- **Severity**: High -- this test will crash with `TypeError` when executed. If it currently passes in CI, it means this specific test case is not being run, which is itself a coverage gap.
- **Recommendation**: Change to `assert result["message_count"] >= 2` or `assert len(result["messages"]) >= 2`.

#### F-02: Class-level `run()` Fails on Models with Required Fields

- **Finding**: `run()` creates `target()` (no-arg construction) for class-level calls. Models with required fields (no defaults) raise `ValidationError`.
- **Evidence**: `mixin.py:331-332`:
  ```python
  if isinstance(target, type):
      instance = target()
  ```
  `AgentActor` has `name: str = Field(min_length=1)` with no default. `AgentActor.run(task='...')` would fail with `ValidationError` before reaching the LLM.
- **Severity**: Medium -- class-level `run()` silently only works on models with all-default fields. The same pattern at `mixin.py:514-515` affects `run_stream()`.
- **Recommendation**: Either (a) document that class-level `run()` requires all fields to have defaults, (b) catch `ValidationError` and raise a clearer error, or (c) use `model_construct()` to skip validation for the throwaway instance.

#### F-03: `agentic_stream()` May Reference Unbound `root` in `finally`

- **Finding**: If `agentic_stream()` is called with `adapter=None` and the `try` block at line 577 fails after setting `owns_adapter=True` but before line 579 (`root = Actor.root()`), the `finally` block at line 651-652 references `root` which would be unbound.
- **Evidence**: `mixin.py:560-652`:
  ```python
  owns_adapter = adapter is None       # line 560
  if owns_adapter:                      # line 561
      ...
      root = Actor.root()              # line 569 — sets root inside the if block
      root.register(adapter)           # line 574
  ...
  try:
      root = Actor.root()             # line 579 — sets root again inside try
      ...
  finally:
      if owns_adapter:
          root._children.pop(...)      # line 652 — which root?
  ```
  In the `owns_adapter=True` path, `root` is set at line 569 (before try) and again at line 579 (inside try). If line 578-579 raises, the `finally` block uses the `root` from line 569, which is valid. However, if `owns_adapter=False`, `root` is only set at line 579. If that line raises, the `finally` block skips because `owns_adapter=False`. So this is fragile but not currently buggy.
- **Severity**: Low -- the logic happens to be correct due to the `owns_adapter` guard, but the control flow is brittle and easy to break during refactoring.
- **Recommendation**: Set `root = None` before the `try` block and check `root is not None` in `finally`.

#### F-04: `_route_tool_call` Assumes `response.data` Is a Dict

- **Finding**: On error TX, `response.data.get('message', 'Tool call failed')` assumes `response.data` is a dict. If it is a string or other type, `AttributeError` is raised.
- **Evidence**: `tools.py:218-219`:
  ```python
  if response.is_error:
      raise ModelRetry(response.data.get('message', 'Tool call failed'))
  ```
  The TX `error()` constructor at `tx.py` creates `data={'message': msg, 'code': code}` -- so normally this is a dict. But if an actor returns a non-standard error TX, this would crash.
- **Severity**: Low -- in practice, all error TXs in the codebase use the standard format. But the assumption is undocumented.
- **Recommendation**: Guard with `msg = response.data.get('message', '...') if isinstance(response.data, dict) else str(response.data)`.

---

### Design Strengths

#### S-01: Clean Policy/Engine Split

The separation between `run()` (policy: config cascade, prompt assembly, adapter lifecycle) and `agentic()` (engine: raw LLM loop, no config magic) is a textbook separation of concerns. `AgentActor.run()` overrides only the policy layer while reusing `agentic()` unchanged -- proving the split works in practice. Evidence: `actor.py:103-129` calls `self.agentic()` with DB-sourced config, completely bypassing the mixin's 3-tier cascade.

#### S-02: Stateless Execution Model

No state accumulates between runs. Each `run()` or `agentic()` call creates its own adapter, discovers tools fresh, builds a new pydantic-ai Agent, and cleans up in `finally`. This eliminates an entire class of bugs (stale state, memory leaks, cross-contamination between concurrent runs). Evidence: the concurrent isolation test at `test_mixin.py:503-528` runs 3 simultaneous agents with `asyncio.gather` and verifies independent results.

#### S-03: Framework-Consistent Mixin Injection

`__agent__ = True` mirrors `__storable__ = True` exactly. The injection happens in `ProtoModel.__init_subclass__()` -- the same mechanism, the same pattern, the same mental model. A developer who understands one understands both. Evidence: `mixin.py:18-20` documents this parallel explicitly.

#### S-04: Self-Loop Prevention

`discover_tools()` excludes the caller's own address (`tools.py:64-67`) and auto-excludes `run`/`stream_run` methods from AgentActor subclasses (`tools.py:94-96`). This prevents the most obvious infinite recursion scenario (agent calls its own `run()` as a tool) without complex graph analysis. Evidence: `test_tools.py:410-458` verifies both exclusion mechanisms.

#### S-05: TX-Aligned Streaming Protocol

Streaming chunks follow the framework's existing `{name, data, meta}` TX format with `stream`, `stream_end`, and `seq` fields. This means the frontend's `<ntx-stream>` component works with agent streaming out of the box -- no custom protocol needed. Evidence: `mixin.py:544-547` documents the format, and `mixin.py:614-642` implements it.

#### S-06: Adapter Lifecycle Management

All four entry points (`run`, `agentic`, `run_stream`, `agentic_stream`) use `try/finally` to guarantee adapter cleanup. The `owns_adapter` pattern in `agentic()` and `agentic_stream()` correctly distinguishes between self-created and caller-provided adapters. Evidence: `mixin.py:329-348` (run), `mixin.py:408-468` (agentic), `mixin.py:513-532` (run_stream), `mixin.py:560-652` (agentic_stream).

#### S-07: Schema Extension for Frontend Integration

The `@schema_extension(after='methods')` decorator plugs agent metadata into the existing schema pipeline without modifying `proto_schema.py`. The `safe_keys` filter at `schema_ext.py:31-33` correctly prevents LLM credentials from leaking into the schema. Evidence: `schema_ext.py:21-43`.

---

### Design Trade-offs

#### T-01: `exec()` for Tool Function Generation

**Gained**: Tool functions have proper Python signatures with type annotations that pydantic-ai can introspect for JSON Schema. The LLM sees accurately-typed tool parameters. **Sacrificed**: Static analysis cannot verify the generated code. Debugging requires understanding the `exec()` machinery. **Assessment**: This trade-off still makes sense. The input is trusted (model schemas from backend code), the approach follows stdlib precedent (`dataclasses`), and the alternative (manually building pydantic models for each tool) would be far more complex. The `noqa: S102` at `tools.py:291` acknowledges the pattern.

#### T-02: Per-Run Tool Discovery (No Caching)

**Gained**: Tools always reflect the actual runtime state -- if a model is added or a method is changed, the next agent run sees it immediately. **Sacrificed**: Every `agentic()` call rediscovers tools, regenerates function signatures via `exec()`, and rebuilds pydantic-ai Tool objects. For 5 tool actors with 30 methods, this creates ~30 functions per run. **Assessment**: Acceptable for now. Schema generation is cached (via `ProtoModel.schema()`), so the main cost is the `exec()` calls and ToolSpec construction. If profiling shows this is a bottleneck, caching ToolSpecs keyed by `frozenset(tool_addrs)` would be safe since schemas are immutable at runtime.

#### T-03: Transient Adapter per Run (No Connection Pooling)

**Gained**: Complete isolation between concurrent agent runs. No shared state, no coordination needed. UUID-based adapter names prevent collision. **Sacrificed**: Each run creates a `NetworkAdapter`, registers it with Matrix, and removes it afterward. This is a dict insert/pop on `root._children`. **Assessment**: Correct trade-off. The overhead is negligible (dict operations), and the isolation guarantees are valuable. Connection pooling would add complexity for minimal gain.

#### T-04: `AgentActor.run()` Returns JSON String

**Gained**: Compatible with `@expose_route` which expects string returns for the HTTP layer. `ActorModel.handler()` at the route level does `json.loads()` on the result. **Sacrificed**: Programmatic callers get a string instead of a dict, requiring `json.loads()`. The `default=str` in `json.dumps()` at `actor.py:129` is lossy for complex objects (pydantic-ai message objects become their `str()` representation). **Assessment**: This trade-off is increasingly problematic. The `@expose_route` requirement forces a string return, but this creates a surprising API asymmetry (`AgentMixin.run()` returns dict, `AgentActor.run()` returns str). Consider having `@expose_route`'s handler serialize the result, so `run()` can return a dict consistently.

#### T-05: Async-Only API

**Gained**: Natural integration with pydantic-ai (which is async-native), FastAPI, and the actor system. **Sacrificed**: Cannot call agent methods from synchronous code without `asyncio.run()`. **Assessment**: Correct for this framework. N3TX is built on FastAPI (async) with an actor system (async). Adding sync wrappers would add complexity for an uncommon use case.

---

### Improvement Opportunities

| # | Improvement | Impact | Effort | Category |
|---|-------------|--------|--------|----------|
| 1 | Fix `test_agent_run.py:54` list-vs-int comparison | High (correctness) | 5 min | Bug fix |
| 2 | Extract config cascade to `_resolve_config()` helper | Medium (maintainability) | 30 min | Refactor |
| 3 | Extract adapter lifecycle to `_adapter_context()` context manager | Medium (maintainability) | 30 min | Refactor |
| 4 | Replace `TX(name='',source='',target='').uuid` with `uuid4().hex[:12]` | Low (cleanliness) | 10 min | Refactor |
| 5 | Implement `neighbor_depth` or remove from config/schema/docs | Medium (transparency) | 1-3 hr | Feature/Cleanup |
| 6 | Add structured logging to `run()`/`agentic()` (start, end, usage, run_id) | Medium (observability) | 30 min | Enhancement |
| 7 | Cache `discover_tools()` results per tool address set | Medium (performance) | 1 hr | Performance |
| 8 | Type-annotate `_route_tool_call` ctx parameter | Low (static analysis) | 5 min | Quality |
| 9 | Make `create_tool_function` part of `__all__` | Low (discoverability) | 2 min | API surface |
| 10 | Add timeout configuration to agent tool calls | Medium (reliability) | 30 min | Enhancement |
| 11 | Fix `_build_schema_text` parenthesis cosmetic issue | Low (cosmetic) | 5 min | Bug fix |
| 12 | Unify `AgentActor.run()` return type with `AgentMixin.run()` | Medium (consistency) | 1 hr | Refactor |

---

## Downstream Use Guide

### For Bug Hunting

#### Known Risk Areas (Ranked by Probability)

1. **`agentic_stream()` generator lifecycle** (`mixin.py:534-652`): The most complex control flow in the subsystem. Multiple adapter ownership paths, exception handling, and `finally` cleanup. The `root` variable binding (F-03) is fragile. If any change introduces a new exception path between `owns_adapter` assignment and `root` assignment, an `UnboundLocalError` will surface.

2. **`_resolve_tool_addrs()` href parsing** (`actor.py:80-99`): Parses URLs by splitting on `/` and extracting IDs. Sensitive to URL format changes, trailing slashes, and non-integer IDs. The `try/except` at line 86-89 catches parse failures but silently drops tools.

3. **`create_tool_function()` `exec()` code generation** (`tools.py:223-294`): Any schema with unusual field names (containing characters beyond what the sanitizer handles) could produce invalid Python. The `isidentifier()` check at line 247 catches most cases, but edge cases (e.g., Python keywords like `class`, `return`) are not tested.

4. **Config cascade divergence** (`mixin.py:283-312` vs `mixin.py:483-496`): The two copies can drift. If a new config key is added to `run()` but not `run_stream()`, streaming will silently use different defaults.

#### Untested Edge Cases

| Edge Case | Location | Test to Write |
|-----------|----------|---------------|
| Class-level `run()` on model with required fields | `mixin.py:331-332` | `test_class_level_run_required_fields` -- verify behavior when `target()` raises `ValidationError` |
| `agentic_stream()` with tool calls mid-stream | `mixin.py:612-619` | `test_streaming_with_tool_calls` -- verify tool call gaps in text stream |
| `result_type` structured output | `mixin.py:425-426` | `test_structured_output` -- pass a Pydantic model as `result_type`, verify `answer` type |
| Parameter named `ctx` in tool schema | `tools.py:260` | `test_ctx_parameter_collision` -- verify collision with RunContext `ctx` param |
| Python keyword as parameter name | `tools.py:246-249` | `test_keyword_parameter_name` -- e.g., `class`, `return` as field names |
| `agentic_stream()` not fully consumed | `mixin.py:650-652` | `test_stream_partial_consumption` -- call `.aclose()` mid-stream, verify adapter cleanup |
| Concurrent `run()` with adapter name collision | `mixin.py:319` | Already tested (UUID prevents), but verify under high concurrency |
| `N3TX_AGENT_DEFAULTS` env var with malformed JSON | `config.py:35-36` | `test_malformed_agent_defaults_env` -- verify error message clarity |
| `constraints.max_iterations` limiting actual iterations | `mixin.py:439-442` | `test_max_iterations_actually_limits` -- verify the LLM stops after N requests |

#### Suggested Test Cases

```python
# test_mixin.py
async def test_class_level_run_required_fields(self, fresh_matrix):
    """Class-level run() on a model with required fields should fail clearly."""
    # AgentActor has name: str = Field(min_length=1) with no default
    with pytest.raises((ValidationError, RuntimeError)):
        await AgentActor.run(task='test', llm=TestModel(call_tools=[]))

async def test_structured_output_result_type(self, fresh_matrix, setup_models):
    """run() with result_type returns structured output."""
    from pydantic import BaseModel
    class Analysis(BaseModel):
        summary: str
        score: float
    result = await AgenticProduct.run(
        task='Analyze', llm=TestModel(call_tools=[]),
        result_type=Analysis,
    )
    # Verify result shape (TestModel behavior may vary)
    assert 'answer' in result

async def test_stream_partial_consumption(self, fresh_matrix, setup_models):
    """Partially consuming agentic_stream() cleans up adapter."""
    from n3tx.core.actors.actor import Actor
    root = Actor.root()
    initial = len(root._children)
    gen = AgenticProduct.run_stream(task='test', llm=TestModel(call_tools=[]))
    # Consume only first chunk
    chunk = await gen.__anext__()
    assert chunk is not None
    await gen.aclose()
    # Verify adapter was cleaned up
    assert len(root._children) == initial

# test_tools.py
def test_ctx_parameter_collision(self):
    """Tool with 'ctx' parameter should not shadow RunContext."""
    spec = ToolSpec(
        actor_addr='test', method_name='go', tool_name='test_go',
        description='Test', parameters={
            'type': 'object',
            'properties': {'ctx': {'type': 'string'}},
        },
    )
    # Should either rename the param or raise
    fn = create_tool_function(spec)
    # Verify the function signature handles the collision
    import inspect
    sig = inspect.signature(fn)
    # 'ctx' from RunContext should not be overwritten
```

### For Feature Development

#### Extension Points with Difficulty Ratings

| Extension Point | Mechanism | Difficulty | Template Code |
|----------------|-----------|------------|---------------|
| Custom prompt builder | Override `ctx()` via `fullmethod` | Easy | `mixin.py:204-229` -- override on subclass |
| Custom tool filter | Override `tools()` via `fullmethod` | Easy | `mixin.py:231-265` -- override on subclass |
| Guardrails/rate limiting | Override `run()` via `fullmethod` | Easy | `actor.py:103-129` demonstrates the pattern |
| New config key | Add to `AGENT_DEFAULTS` + read in `run()` | Easy | `config.py:27-32` + `mixin.py:289-308` |
| Schema enrichment | `@schema_extension(after='agent')` | Easy | `schema_ext.py:21-43` |
| New tool source (MCP, HTTP) | Extend `discover_tools()` or new discovery fn | Medium | `tools.py:43-101` |
| Custom LLM engine | Override `agentic()` instance method | Medium | `mixin.py:350-468` |
| Agent-to-agent calls | Modify exclusion logic in `tools.py:94-96` | Hard | Requires loop detection beyond self-exclusion |

#### Patterns to Follow

**Adding a new config key** (cite `config.py:27-32`, `mixin.py:283-312`, `schema_ext.py:31-33`):
1. Add default to `AGENT_DEFAULTS` in `config.py`
2. Read in `run()` cascade: `kwargs.get('key') or model_conf.get('key') or defaults.get('key')`
3. IMPORTANT: Also add to `run_stream()` cascade (currently duplicated)
4. If exposed to frontend: add to `safe_keys` in `schema_ext.py:32`
5. Pass through to `agentic()` if needed
6. Add test in `test_mixin.py`

**Adding a custom method to AgentActor** (cite `actor.py:103-129`):
```python
@expose_route('/analyze', methods=['POST'], stream=True)
async def analyze(self, query: str):
    async for chunk in self.run_stream(task=query):
        yield chunk
```

#### Constraints to Be Aware Of

1. **Matrix must exist** before any `run()` call. Level 1 bootstrapping (`create_app` without `routing='actor'`) may not have a Matrix. Verify with `Actor.root()`.
2. **`agentic()` must never be exposed via HTTP directly.** It bypasses all policy enforcement. Only `run()` should be an `@expose_route`.
3. **All tool calls carry the same user context.** There is no per-tool permission scoping. An agent running as admin can call any tool with admin privileges.
4. **Schema changes require server restart.** Tool discovery reads cached schemas. Dynamic model changes at runtime will not be reflected until the cache is invalidated.
5. **`run()` kwargs are `**kwargs`** -- no IDE autocomplete. Valid kwargs: `prompt`, `tools`, `llm`, `constraints`, `user`, `message_history`, `result_type`.

#### Common Pitfalls

1. **Forgetting to update both `run()` and `run_stream()`** when changing the config cascade. They are separate copies of the same logic (see improvement #2).
2. **Testing with `:memory:` SQLite** for agent storage. Per project memory: `:memory:` creates separate databases per connection. Use `tmp_path` with file-based SQLite.
3. **Calling `agentic()` at class level.** It is an instance method, not a `fullmethod`. `Product.agentic(...)` will raise `TypeError`.
4. **Expecting `AgentActor.run()` to return a dict.** It returns a JSON string. Use `json.loads()` on the result.
5. **Adding a tool parameter named `ctx`.** It collides with the pydantic-ai `RunContext` parameter.

### For Integration Planning

#### Integration Boundaries and Data Contracts

| Boundary | Direction | Contract | Stability |
|----------|-----------|----------|-----------|
| AgentMixin <-> config.py | Inbound | `AGENT_DEFAULTS` dict with keys: `self_tools`, `neighbors`, `neighbor_depth`, `llm` | Stable. Adding keys is additive. |
| AgentMixin <-> NetworkAdapter | Outbound | Creates `NetworkAdapter(addr=str)`, registers via `root.register()`, removes via `root._children.pop()` | Stable. Adapter API is well-established. |
| tools.py <-> Matrix children | Outbound | Reads `root._children[addr]`, calls `cls.schema()` | Stable. Schema format is framework-wide contract. |
| tools.py <-> pydantic_ai | Outbound | `Agent(llm, system_prompt, deps_type, tools)`, `Tool(function, takes_ctx, name, desc)`, `ModelRetry`, `RunContext[AgentDeps]`, `UsageLimits` | Moderate. External dependency. Major version changes could break. |
| schema_ext <-> proto_schema.py | Inbound | `@schema_extension(after='methods')` decorator registration | Stable. Pipeline extension is a first-class framework pattern. |
| AgentActor <-> route layer | Outbound | `@expose_route('/run')` returns `str` (JSON) | Stable. Standard expose_route contract. |
| _route_tool_call <-> target actors | Outbound | TX envelope: `{name: method, source: adapter_addr, target: actor_addr, data: params, meta: {user: dict}}` | Stable. TX is the universal message format. |

#### Dependencies and Stability

| Dependency | Version Sensitivity | Risk |
|------------|-------------------|------|
| `pydantic_ai` | High -- `Agent`, `Tool`, `RunContext`, `UsageLimits`, `ModelRetry` APIs used directly | If pydantic-ai changes its Tool or Agent API, `agentic()` and `make_tool()` break. Pin version. |
| `fullmethod` descriptor | Low -- stable, minimal API (just `__get__`) | Unlikely to change. |
| Actor system (Actor, Matrix, TX) | Low -- stable since v0.8 | Core framework. Changes are rare and backward-compatible. |
| NetworkAdapter | Low -- `request()` API is stable | Well-tested across Level 3 integration tests. |
| StorableMixin | Low -- only used for `isinstance` check in `tools.py:86` | Detection logic, not deep coupling. |

#### Impact Analysis Checklist

When changing the agent subsystem, verify:
- [ ] `run()` and `run_stream()` config cascades are still in sync
- [ ] Adapter cleanup in all 4 entry points (run, agentic, run_stream, agentic_stream)
- [ ] Unit tests: `cd /workspace/src/n3tx/core && python3 -m pytest tests/unit/test_mixin.py tests/unit/test_tools.py tests/unit/test_agent_actor.py`
- [ ] Integration tests: `cd /workspace && python3 -m pytest example_grants/tests/test_agent_run.py`
- [ ] Schema extension output: run server, `curl /AgentActor`, verify `agent` section
- [ ] CLAUDE.md agent section is still accurate
- [ ] `__all__` in `__init__.py` reflects any new exports
- [ ] `safe_keys` in `schema_ext.py:32` includes any new config keys that should be public

### For Refactoring

#### Technical Debt (Ranked by Severity and Coupling Risk)

| # | Debt Item | Severity | Coupling | Location |
|---|-----------|----------|----------|----------|
| 1 | Duplicated config cascade in `run()` vs `run_stream()` | Medium | High -- changes to one must be mirrored in the other | `mixin.py:283-312` and `mixin.py:483-496` |
| 2 | Duplicated adapter lifecycle in 4 methods | Medium | High -- 4 copies of create/register/cleanup | `mixin.py:314-348`, `392-468`, `498-532`, `560-652` |
| 3 | `neighbor_depth` dead config | Low | Medium -- in config.py, schema_ext.py, CLAUDE.md | `config.py:30`, `schema_ext.py:32` |
| 4 | UUID via throwaway TX | Low | Low -- 4 occurrences, no coupling | `mixin.py:319, 398, 503, 566` |
| 5 | `AgentActor.run()` return type mismatch | Medium | Medium -- affects all programmatic callers | `actor.py:129` |
| 6 | `_build_schema_text` parenthesis cosmetic bug | Low | Low -- affects LLM prompt formatting | `mixin.py:74-76` |
| 7 | `_build_instance_text` double `str(v)` call | Low | Low -- performance only | `mixin.py:169-174` |
| 8 | No `__all__` in `mixin.py` | Low | Low -- implicit exports | `mixin.py` |

#### Suggested Refactoring Sequence

The dependency order matters. Refactor in this sequence to minimize risk:

**Step 1: Extract `_resolve_config()` helper** (addresses debt #1)
```python
# mixin.py — new helper
def _resolve_config(target, kwargs: dict) -> dict:
    """Resolve 3-tier agent config cascade.

    Returns dict with keys: prompt, tools, llm, constraints, user,
    message_history, result_type.
    """
    from n3tx.core import config
    cls = target if isinstance(target, type) else target.__class__
    agent_flag = getattr(cls, '__agent__', False)
    model_conf = agent_flag if isinstance(agent_flag, dict) else {}
    defaults = config.AGENT_DEFAULTS

    return {
        'prompt': kwargs.get('prompt') or target.ctx(),
        'tools': kwargs.get('tools') or target.tools(),
        'llm': (kwargs.get('llm')
                or model_conf.get('llm')
                or getattr(target, 'llm', None)
                or defaults.get('llm', 'ollama:llama3.1')),
        'constraints': {
            **defaults.get('constraints', {}),
            **model_conf.get('constraints', {}),
            **kwargs.get('constraints', {}),
        },
        'user': kwargs.get('user'),
        'message_history': kwargs.get('message_history'),
        'result_type': kwargs.get('result_type') or model_conf.get('result_type'),
    }
```
Risk: Low. Pure extraction, no behavior change. Test by verifying `run()` and `run_stream()` produce identical results before and after.

**Step 2: Extract `_agent_adapter()` context manager** (addresses debt #2 and #4)
```python
# mixin.py — new context manager
from contextlib import asynccontextmanager
from uuid import uuid4

@asynccontextmanager
async def _agent_adapter():
    """Create, register, and auto-cleanup a transient agent adapter."""
    from n3tx.core.api.network_adapter import NetworkAdapter
    from n3tx.core.actors.actor import Actor

    run_id = uuid4().hex[:12]
    adapter_addr = f'_agent_{run_id}'
    adapter = NetworkAdapter(addr=adapter_addr)
    root = Actor.root()
    if not root:
        raise RuntimeError("No Matrix root. Initialize a Matrix before running agents.")
    root.register(adapter)
    try:
        yield adapter
    finally:
        root._children.pop(adapter_addr, None)
```
Risk: Low. Replaces 4 copies of the same pattern. The `agentic()`/`agentic_stream()` conditional adapter ownership can use `_agent_adapter()` when `adapter is None` and skip it otherwise.

**Step 3: Fix UUID generation** (part of step 2 -- already uses `uuid4().hex[:12]`)

**Step 4: Resolve `neighbor_depth`** (addresses debt #3)
Decision needed: implement or remove. Removing is safer and faster:
- Delete `'neighbor_depth': 1` from `config.py:30`
- Remove from `safe_keys` in `schema_ext.py:32`
- Update CLAUDE.md
Risk: Low if removing. No code reads it.

**Step 5: Unify `AgentActor.run()` return type** (addresses debt #5)
This is the highest-risk refactoring. Options:
- (A) Have `AgentActor.run()` return dict, let `@expose_route` handler serialize. Requires checking that `ActorModel.handler()` can handle dict returns.
- (B) Keep string return, document the asymmetry prominently.
Risk: Medium for option (A) -- requires verifying the route layer handles dict returns. Option (B) is zero risk but preserves the inconsistency.

#### Risk Assessment

| Refactoring | Risk | Mitigation |
|-------------|------|------------|
| `_resolve_config()` extraction | Low | Run existing tests; config output should be identical |
| `_agent_adapter()` context manager | Low | Run concurrent isolation test (`test_concurrent_runs_isolated`) |
| Remove `neighbor_depth` | Low | Grep for all references; update docs |
| UUID generation change | Low | UUID format is only used for adapter naming uniqueness |
| Unify return types | Medium | Test all callers: HTTP API, programmatic, test fixtures |

---

## Appendix: Complete Finding Index

| ID | Dimension | Severity | Finding | File(s) | Status |
|----|-----------|----------|---------|---------|--------|
| F-01 | Quality | High | Test bug: `result["messages"] >= 2` compares list to int | `example_grants/tests/test_agent_run.py:54` | Open |
| F-02 | API | Medium | Class-level `run()` fails on models with required fields (no defaults) | `mixin.py:331-332`, `mixin.py:514-515` | Open |
| F-03 | Quality | Low | `agentic_stream()` fragile `root` variable binding in `finally` block | `mixin.py:560-652` | Open (not currently buggy) |
| F-04 | Quality | Low | `_route_tool_call` assumes `response.data` is a dict on error | `tools.py:218-219` | Open |
| F-05 | Architecture | Medium | `neighbor_depth` config declared but never implemented | `config.py:30`, `schema_ext.py:32`, `mixin.py:252-257` | Open (dead code) |
| F-06 | Quality | Medium | Duplicated config cascade in `run()` vs `run_stream()` (~14 lines identical) | `mixin.py:283-312`, `mixin.py:483-496` | Open (tech debt) |
| F-07 | Quality | Medium | Duplicated adapter lifecycle in 4 methods | `mixin.py:314-348`, `392-468`, `498-532`, `560-652` | Open (tech debt) |
| F-08 | Quality | Low | UUID generated via throwaway TX object (4 occurrences) | `mixin.py:319, 398, 503, 566` | Open (code smell) |
| F-09 | API | Medium | `AgentActor.run()` returns str, `AgentMixin.run()` returns dict | `actor.py:129`, `mixin.py:455-464` | Open (inconsistency) |
| F-10 | Quality | Low | `_build_schema_text` cosmetic: fields without type produce `(, required)` | `mixin.py:74-76` | Open (cosmetic) |
| F-11 | Quality | Low | `_build_instance_text` calls `str(v)` twice per field | `mixin.py:169-174` | Open (minor perf) |
| F-12 | API | Low | `_route_tool_call` ctx parameter untyped (duck-typed) | `tools.py:201` | Open |
| F-13 | API | Low | `create_tool_function` not in `__all__` | `tools.py:223`, `__init__.py:23-26` | Open |
| F-14 | Quality | Low | No structured logging in `run()`/`agentic()` (start/end/duration/usage) | `mixin.py:268-468` | Open |
| F-15 | API | Low | `run()` kwargs not typed -- no IDE autocomplete for valid kwargs | `mixin.py:268` | Open |
| F-16 | Architecture | Low | Adapter request timeout hardcoded to 30s, not configurable from agent layer | `network_adapter.py:79` | Open |
| F-17 | Quality | Low | `agentic_stream()` error handling catches all exceptions silently at `get_output()` | `mixin.py:623-626` | Open |
| F-18 | Quality | Low | Streaming assertion too permissive: accepts either success or error | `test_mixin.py:597` | Open |
| F-19 | Architecture | Medium | LLM default `'ollama:llama3.1'` hardcoded in `agentic()` in addition to `AGENT_DEFAULTS` | `mixin.py:382`, `config.py:31` | Open (duplication) |
| F-20 | Quality | Low | `exec()`-generated tool functions: no test for Python keyword param names | `tools.py:246-249` | Open (coverage gap) |
| S-01 | Architecture | -- | Clean policy/engine split (run vs agentic) | `mixin.py`, `actor.py:103-129` | Strength |
| S-02 | Architecture | -- | Stateless execution model (no state between runs) | `mixin.py` (all entry points) | Strength |
| S-03 | Architecture | -- | Framework-consistent mixin injection (`__agent__ = True`) | `mixin.py:18-20` | Strength |
| S-04 | Architecture | -- | Self-loop prevention in tool discovery | `tools.py:64-67, 94-96` | Strength |
| S-05 | Architecture | -- | TX-aligned streaming protocol | `mixin.py:544-547, 614-642` | Strength |
| S-06 | Quality | -- | Adapter lifecycle management with `try/finally` | All 4 entry points | Strength |
| S-07 | Architecture | -- | Schema extension for frontend integration (safe_keys filter) | `schema_ext.py:21-43` | Strength |
| T-01 | Architecture | -- | `exec()` for tool signatures (justified, stdlib precedent) | `tools.py:291` | Trade-off (acceptable) |
| T-02 | Performance | -- | Per-run tool discovery (no caching, but reflects runtime state) | `mixin.py:412`, `tools.py:43-101` | Trade-off (acceptable for now) |
| T-03 | Architecture | -- | Transient adapter per run (isolation over reuse) | `mixin.py:314-327` | Trade-off (correct) |
| T-04 | API | -- | `AgentActor.run()` returns str for `@expose_route` compat | `actor.py:129` | Trade-off (increasingly problematic) |
| T-05 | Architecture | -- | Async-only API (no sync wrappers) | All entry points | Trade-off (correct for framework) |
