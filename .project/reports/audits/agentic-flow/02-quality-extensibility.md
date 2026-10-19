# Agentic Flow: Quality & Extensibility Audit

**Scope**: `src/n3tx/core/agents/` (mixin.py, actor.py, deps.py, tools.py, schema_ext.py, tool_model.py), config.py, and integration boundaries.
**Branch**: v0.9 | **Date**: 2026-03-09

---

## PART 1: Quality & Risk Assessment

### 1.1 Potential Bugs

#### BUG-1: `neighbor_depth` config declared but never implemented

`config.py:30` declares `'neighbor_depth': 1` in `AGENT_DEFAULTS` and `schema_ext.py:32` lists it as a safe key for schema exposure. However, `tools()` in `mixin.py:252-257` only discovers direct ListRef neighbors — it never reads `neighbor_depth` or recurses beyond depth 1.

```python
# mixin.py:252-257 — flat neighbor discovery, ignores neighbor_depth
if conf.get('neighbors', True):
    from n3tx.core.utils.introspection import get_list_fields
    for field_name, model_cls in get_list_fields(cls):
        if hasattr(model_cls, '__tablename__'):
            addrs.append(model_cls.__tablename__)
```

**Impact**: Low. The config key exists but depth > 1 has no effect. Users who set `neighbor_depth: 2` get silent failure (no error, just depth-1 behavior). This violates "transparent, not magical."

**Likelihood**: Medium — the key is documented in CLAUDE.md and exposed in schema output.

#### BUG-2: `run()` creates empty instances for class-level calls

`mixin.py:331-332` creates `target()` when called at class level:

```python
if isinstance(target, type):
    instance = target()
```

For models with required fields (no defaults), this raises `ValidationError`. Example: `AgentActor.run(task='...')` would fail because `name: str = Field(min_length=1)` has no default.

**Impact**: Medium. Class-level `run()` only works on models where all fields have defaults.

**Likelihood**: Medium — the example `AgenticProduct` in tests has defaults, masking this.

#### BUG-3: `_build_schema_text` parenthesis imbalance for fields without type

`mixin.py:76` produces `(` with no type when `ptype` is empty:

```python
if ptype:
    parts.append(f'({ptype}')
else:
    parts.append('(')
```

Combined with line 103 (`parts[-1] += ')'`), a field with no type produces `(, optional)` or `(, required)` — cosmetically broken but syntactically correct for LLM consumption.

**Impact**: Low (cosmetic). **Likelihood**: Low (most schema properties have a type).

#### BUG-4: `_build_instance_text` truncation inconsistency

`mixin.py:169-174`:

```python
truncated = {}
for k, v in data.items():
    s = str(v)
    if len(s) > 200:
        s = s[:200] + '...'
    truncated[k] = v if len(str(v)) <= 200 else s
```

`str(v)` is called twice per field — once to measure, once to decide. If `v` has a non-deterministic `__str__`, this could truncate inconsistently. Also, `v` (original value) is kept for short values while `s` (string) is used for long values, producing a mixed-type dict passed to `json.dumps`.

**Impact**: Low. **Likelihood**: Low — model fields are typically deterministic.

#### BUG-5: `AgentActor.run()` returns JSON string, not dict

`actor.py:129` returns `json.dumps(result, default=str)` while `AgentMixin.run()` returns a `dict`. The same method name with different return types depending on the class creates a confusing API boundary. When `AgentActor.run()` is called via `@expose_route`, `ActorModel.handler` at line 156-160 tries `json.loads(result)` on the returned string and wraps it as `tx.reply(data=parsed)`, so it works — but the contract is fragile.

**Impact**: Medium — consumers must know which `run()` variant they're calling.

**Likelihood**: Medium — direct Python callers will get `str` and need `json.loads()`.

---

### 1.2 Edge Cases

| Edge Case | Location | Risk |
|-----------|----------|------|
| Empty `tools` list passed to `agentic()` | `mixin.py:413` | Works: logs warning, runs LLM with no tools. OK. |
| `None` adapter + no Matrix root | `mixin.py:393-405` | `RuntimeError` raised. Clean. |
| Concurrent `run()` with same adapter addr | `mixin.py:319` | UUID-based adapter names (`_agent_{uuid}`) prevent collision. Safe. |
| `_resolve_tool_addrs()` with href parse failure | `actor.py:87-89` | Logs warning, skips. Silent data loss. |
| LLM returns structured output with `result_type` | `mixin.py:425-426` | Passed to `Agent()` as `output_type`. Works with pydantic-ai. |
| `message_history` with incompatible format | `mixin.py:449` | Pydantic AI will raise `ValidationError`. Uncaught in `agentic()`. |
| Schema with `anyOf`/`oneOf` union types | `tools.py:252` | `_JSON_TYPE_MAP` has no union handling. Falls back to `str`. |
| Tool name collision across actors | `tools.py:36` | `tool_name = f'{tablename}_{action}'` — unique if tablenames unique. |
| Tool parameter named `ctx` | `tools.py:260` | Collision with the RunContext `ctx` param. Would break. |

---

### 1.3 Test Coverage Analysis

**What IS tested** (high coverage):

| Area | Test File | Key Cases |
|------|-----------|-----------|
| Mixin injection + MRO | `test_mixin.py:90-143` | injection, coexistence with StorableMixin, MRO order |
| `ctx()` class vs instance | `test_mixin.py:148-211` | schema text, instance data, prompt prepend, relationships |
| `tools()` discovery | `test_mixin.py:215-257` | self, neighbors, extras, disable flags, dedup |
| `agentic()` direct call | `test_mixin.py:262-402` | basic, adapter provided, message history, no Matrix, tool calling |
| `run()` config cascade | `test_mixin.py:407-498` | zero-config, overrides, adapter lifecycle, error cleanup |
| Concurrent runs | `test_mixin.py:503-528` | 3-way `asyncio.gather`, adapter isolation |
| User auth propagation | `test_mixin.py:533-575` | meta.user carried in tool TX |
| Streaming | `test_mixin.py:580-711` | chunk yielding, adapter cleanup, error chunks |
| Tool discovery | `test_tools.py:54-105` | CRUD, methods, multi-actor, missing actor, instance id |
| Tool function gen | `test_tools.py:107-206` | typed params, ordering, no-params, type mapping, async |
| Tool edge cases | `test_tools.py:292-363` | all-optional, invalid identifiers, special chars, hyphens |
| Loop detection | `test_tools.py:410-458` | self-exclusion, AgentActor.run excluded |
| Route tool call errors | `test_tools.py:233-289` | error TX -> ModelRetry, missing actor |
| AgentActor CRUD | `test_agent_actor.py:169-239` | create, get, list, update, delete |
| AgentActor.run() | `test_agent_actor.py:242-359` | basic, with tools, user, constraints |
| Schema extension | `test_agent_actor.py:362-409` | agent section, run_endpoint, non-agent model |
| Integration (grants) | `test_agent_run.py:12-67` | no tools, tool call, sources, href resolution |

**What is NOT tested** (coverage gaps):

| Gap | Risk | Location |
|-----|------|----------|
| `run_stream()` at class level with required fields | High | BUG-2 applies here too |
| `agentic_stream()` with actual tool calls | Medium | Only tested with `tools=[]` |
| `result_type` structured output path | Medium | `mixin.py:425-426` never tested |
| `_build_schema_text` with access rules formatting | Low | `mixin.py:126-134` |
| `_build_instance_text` with non-serializable fields | Low | `mixin.py:177-178` |
| `create_tool_function` with parameter named `ctx` | Medium | Would shadow RunContext |
| Config env var override (`N3TX_AGENT_DEFAULTS`) | Low | `config.py:34-36` |
| `AgentActor._resolve_tool_addrs()` batch fetch path with join model | Medium | `actor.py:95-99` |
| `run()` with `constraints.max_iterations` actually limiting iterations | Medium | Only tested that it runs |
| Schema cache invalidation after agent mixin injection | Low | `proto_model.py:186-190` |
| `agentic_stream()` adapter cleanup when generator not fully consumed | High | `mixin.py:650-652` |

---

### 1.4 Test Quality Assessment

**Strengths**:
- Tests use `pydantic_ai.models.test.TestModel` consistently — no external LLM dependency.
- `conftest.py` properly isolates Matrix/Actor state between tests via save/restore pattern.
- Concurrent isolation test (`test_concurrent_runs_isolated`) is a good design.
- Error path coverage for `_route_tool_call` is thorough.

**Weaknesses**:

1. **Assertion gaps in streaming tests**: `test_yields_chunks` at `test_mixin.py:597` asserts `chunks[-1]['name'] in ('done', 'error')` — accepting either success or failure is too permissive. A test that passes on error is not verifying streaming works.

2. **`test_agent_run.py:55` type confusion**: `assert result["messages"] >= 2` compares a `list` with `int`. This test would always pass because Python 2-style comparisons... actually, in Python 3 this raises `TypeError`. This is a latent bug in the test itself.

```python
# example_grants/tests/test_agent_run.py:55
assert result["messages"] >= 2  # BUG: result["messages"] is a list, not int
```

3. **`memory_storage` fixture uses `:memory:`**: `conftest.py:42` creates `SQLiteStorage(':memory:')`. Per the project memory note, `:memory:` opens separate connections = separate DBs. Tests using this for storage that requires `create_table()` will silently fail. Most agent tests use `tmp_path` for file-based storage, which is correct — but `setup_models` in `test_tools.py:50` uses `memory_storage` for `Grant` registration with `register_model`. This works only because `discover_tools` reads schemas (not storage), so the storage never gets queried.

4. **No negative test for `exec()` injection**: `create_tool_function` at `tools.py:291` uses `exec()`. While the input comes from trusted schemas, no test verifies that adversarial schema content (e.g., a description containing `"""`) cannot break the generated code. The existing test at `test_tools.py:341-351` does test special chars but only as a smoke test (no assertion on correct escaping of the docstring content).

---

### 1.5 Error Handling Gaps

| Location | Issue | Severity |
|----------|-------|----------|
| `mixin.py:382` | `llm = llm or 'ollama:llama3.1'` — invalid default falls through to pydantic-ai which throws opaque provider errors | Low |
| `mixin.py:451` | `await ai_agent.run(task, **run_kwargs)` — no catch. LLM provider errors (network, auth, rate limit) propagate as raw exceptions to caller | Medium |
| `mixin.py:623-626` | `result.get_output()` wrapped in try/except but catches all exceptions silently, setting `output = ''` | Low |
| `actor.py:96` | `tool_cls.list(ids=href_ids)` — if storage not configured for join model, raises. Uncaught. | Medium |
| `tools.py:291` | `exec(code, ns)` — if code generation produces syntax error (shouldn't happen normally), `SyntaxError` propagates with no context | Low |
| `tools.py:218-219` | `ModelRetry` on error TX — message is `response.data.get('message', 'Tool call failed')` — if `response.data` is not a dict (edge case), `.get()` raises `AttributeError` | Low |

---

### 1.6 Security Considerations

#### SEC-1: `exec()` in tool function generation

`tools.py:291` uses `exec()` to create dynamic functions. The code is constructed from:
- `func_name`: sanitized via `.replace('-', '_').replace('.', '_')` and `.isidentifier()` check
- `params_str`: built from `safe_name` (validated via `.isidentifier()`) and `type_str` (from `_JSON_TYPE_MAP`, fixed set)
- `desc`: description string escaped via `.replace('\\', '\\\\').replace('"""', "'''")`

**Risk**: Low. The inputs come from model schemas defined in backend code — not user input. The escaping covers the main injection vector (triple quotes in docstrings). The `noqa: S102` acknowledges the pattern. Same approach as `dataclasses` stdlib.

**Residual risk**: If a model's `@expose_route` description or parameter name is set from untrusted user input at runtime (e.g., dynamic model creation from API), the `exec()` becomes an injection vector. This is not currently possible in N3TX.

#### SEC-2: LLM credential exposure in schema

`schema_ext.py:31-33` filters safe keys from `__agent__` config:

```python
safe_keys = {'self_tools', 'neighbors', 'neighbor_depth'}
agent_meta['config'] = {k: v for k, v in agent_flag.items() if k in safe_keys}
```

This correctly excludes `llm`, `prompt`, `tools`, `constraints`. The LLM provider string (which may contain API keys in some configurations) is never exposed in schema.

#### SEC-3: User context in tool TXs

`tools.py:208` injects user context into TX meta: `meta = {'user': ctx.deps.user} if ctx.deps.user else {}`. The full JWT user dict flows through to target actors. This is correct for auth checking but means tool target actors receive the calling user's full auth context. If a malicious tool actor existed, it could exfiltrate user data.

**Risk**: Low in current architecture (all actors are backend-defined).

---

### 1.7 Performance Risks

#### PERF-1: Schema generation per agent run

`mixin.py:216` calls `cls.schema()` on every `ctx()` invocation. While `ProtoModel.schema()` is cached (`proto_model.py:200-206`), the cache returns `copy.deepcopy()`, which is O(n) in schema size. For large models with many `$defs`, this is nontrivial.

**Mitigation**: Cache the `_build_schema_text` output alongside the schema. Since schemas are immutable at runtime, context text could be built once.

#### PERF-2: Tool discovery on every agentic() call

`mixin.py:412` calls `discover_tools()` on every invocation. This iterates all tool addresses, fetches schemas (cached), builds ToolSpecs, and calls `create_tool_function` + `exec()` for each. For an agent with 5 tool actors and 30 total methods, this creates ~30 functions per call.

**Mitigation**: Cache ToolSpecs and generated functions keyed by `frozenset(tools)`. Schema immutability makes this safe.

#### PERF-3: TX object creation for adapter UUID

`mixin.py:319` creates a throwaway `TX(name='', source='', target='')` solely to get a UUID:

```python
run_id = TX(name='', source='', target='').uuid
```

This instantiates a full TX dataclass (with `time.time()` call) just for `uuid4().hex[:12]`. Minor but wasteful — occurs 3 times (in `run()`, `run_stream()`, and `agentic()` adapter fallback).

#### PERF-4: `_resolve_tool_addrs` N+1 partially mitigated

`actor.py:80-99` collects href IDs then batch-fetches via `tool_cls.list(ids=href_ids)`. This avoids N+1 for href resolution. However, the `list(ids=...)` API is used which may not exist on all storage backends — checking `SQLiteStorage.list()` would confirm.

---

### 1.8 Concurrency Issues

#### CONC-1: Adapter lifecycle under concurrent streaming

If `run_stream()` is called concurrently (multiple HTTP requests to `/agents/1/run` stream endpoint), each creates its own adapter with UUID-based address (`mixin.py:503-504`). This is safe — no shared state between concurrent streams.

#### CONC-2: `root._children` mutation not thread-safe

`mixin.py:327` does `root.register(adapter)` and `mixin.py:348` does `root._children.pop(adapter_addr, None)`. Both mutate a plain `dict` on the Matrix root. In an async context with `asyncio.gather`, this is safe (single-threaded event loop). But if the server uses multi-process workers (uvicorn with `--workers N`), each process has its own Matrix — also safe.

#### CONC-3: `agentic_stream()` generator lifecycle

`mixin.py:644-652` has a try/except/finally around the streaming loop. If the consumer stops iterating (HTTP client disconnects), the generator's `finally` block runs on `.aclose()`. However, `root` at line 652 references the variable from line 579, which is inside the `try`. If the `try` block at line 577 fails before line 579, `root` would be unbound — but `owns_adapter` would be False (set at 560), so the `finally` at 651-652 would skip cleanup. Fragile but not buggy.

---

### 1.9 Resource Management

**Adapter cleanup**: The `try/finally` pattern in `run()` (mixin.py:329-348), `agentic()` (mixin.py:408-468), and `run_stream()` (mixin.py:513-532) properly cleans up transient adapters. This is well-designed.

**Potential leak**: If `agentic_stream()` is called directly (bypassing `run_stream()`'s lifecycle management) and the caller does not fully consume the generator or call `.aclose()`, the adapter registered at line 574 will leak in `root._children`. The `owns_adapter` check at 651 ensures cleanup only happens for self-created adapters, which is correct — but the leak scenario is real if `agentic_stream()` is called without adapter and not fully consumed.

---

### 1.10 Technical Debt

| Item | Location | Notes |
|------|----------|-------|
| `neighbor_depth` declared but unimplemented | `config.py:30`, `mixin.py:252` | Documented feature that doesn't exist |
| Duplicated config cascade code | `run()` vs `run_stream()` | `mixin.py:268-312` duplicated at `mixin.py:471-496`. Extract to `_resolve_config()`. |
| Duplicated adapter lifecycle code | `run()`, `agentic()`, `run_stream()`, `agentic_stream()` | Four copies of create-adapter-register-cleanup. Extract to context manager. |
| UUID generation via throwaway TX | `mixin.py:319, 398, 503, 566` | Should use `uuid4().hex[:12]` directly |
| `_build_schema_text` coupled to schema format | `mixin.py:50-158` | Fragile string building. Changes to schema format silently break context. |
| No `__all__` in `mixin.py` | — | Minor. Module exports are implicit. |

---

### 1.11 Failure Modes

```
Failure: LLM provider unreachable
Path:    mixin.py:451 → pydantic_ai Agent.run() → provider HTTP call
Result:  Exception propagates to caller. In run(): uncaught.
         In agentic_stream(): caught at mixin.py:644, yields error chunk.
Impact:  run() caller gets raw exception; stream consumer gets structured error.
Fix:     Wrap agentic() LLM call in try/except, return structured error dict.

Failure: Matrix not initialized
Path:    mixin.py:322-326
Result:  RuntimeError("No Matrix root")
Impact:  Clean failure. All three entry points check this.

Failure: Tool target actor not in Matrix
Path:    tools.py:70-72 → discover_tools logs warning, skips
Result:  Agent runs with fewer tools than expected. Silent.
Impact:  LLM may fail the task. Warning is logged but no error raised.

Failure: Tool call to non-existent actor
Path:    tools.py:216 → adapter.request() → Matrix routes → no child found
Result:  Error TX → ModelRetry raised → LLM retries or gives up
Impact:  Clean. Tested at test_tools.py:269-289.

Failure: Tool call returns unexpected data format
Path:    tools.py:220 → json.dumps(response.data, default=str)
Result:  Always serializable due to default=str. Safe.

Failure: Schema cache stale after dynamic model change
Path:    proto_model.py:200-201 → returns cached schema
Result:  Agent tools discovered from stale schema. Wrong tool signatures.
Impact:  Tool calls may fail with wrong parameters. Low probability at runtime.
```

---

## PART 2: Extensibility & Integration

### 2.1 Extension Points

| Extension Point | Mechanism | Difficulty | Example |
|----------------|-----------|------------|---------|
| Add schema stage | `@schema_extension(after='agent')` | Easy | Add `federation` stage for AP metadata |
| Custom tool discovery | Override `tools()` fullmethod | Easy | Filter tools by user role |
| Custom config cascade | Override `run()` fullmethod | Easy | Add rate limiting, audit logging |
| Custom LLM engine | Override `agentic()` | Medium | Swap pydantic-ai for custom LLM client |
| New tool types | Extend `discover_tools()` | Medium | Non-actor tools (HTTP endpoints, MCP) |
| Custom prompt builder | Override `ctx()` fullmethod | Easy | RAG-augmented prompts |
| Structured output | `result_type` param | Easy | `run(task=..., result_type=AnalysisResult)` |
| Multi-turn conversations | `message_history` param | Easy | Already supported |
| Interceptors on agent TX | `Actor.use(fn, on='inbox')` | Easy | Log all agent tool calls |
| Custom agent actor | Subclass `AgentActor` | Medium | Domain-specific agent with extra fields |
| New adapter protocol | Subclass `NetworkAdapter` | Medium | WebSocket-based agent communication |

### 2.2 Integration Boundaries

```
                        DEPENDENCY GRAPH
                        ================

  ┌──────────────────────────────────────────────────────┐
  │                    config.py                          │
  │  AGENT_DEFAULTS, N3TX_AGENT_DEFAULTS env var         │
  └──────────────┬───────────────────────────────────────┘
                 │ reads defaults
                 v
  ┌──────────────────────────────────────────────────────┐
  │                  agents/mixin.py                      │
  │  AgentMixin: ctx(), tools(), run(), agentic(),       │
  │              run_stream(), agentic_stream()           │
  │                                                      │
  │  INBOUND DEPS:                                       │
  │    - descriptors.py (fullmethod)                     │
  │    - config.py (AGENT_DEFAULTS)                      │
  │    - introspection.py (get_list_fields)              │
  │    - network_adapter.py (NetworkAdapter)             │
  │    - actor.py (Actor.root)                           │
  │    - tx.py (TX for UUID gen)                         │
  │    - pydantic_ai (Agent, UsageLimits)                │
  │    - agents/deps.py (AgentDeps)                      │
  │    - agents/tools.py (discover_tools, make_tool)     │
  │                                                      │
  │  OUTBOUND DEPS (consumed by):                        │
  │    - proto_model.py (__init_subclass__ injection)     │
  │    - agents/actor.py (inherits via __agent__=True)   │
  │    - any model with __agent__ = True                 │
  └──────────┬───────────────────────────────────────────┘
             │
  ┌──────────v───────────────────────────────────────────┐
  │                  agents/tools.py                      │
  │  ToolSpec, discover_tools(), create_tool_function(),  │
  │  make_tool(), _route_tool_call()                      │
  │                                                      │
  │  INBOUND DEPS:                                       │
  │    - tx.py (TX envelope for routing)                 │
  │    - storable_mixin.py (isinstance check)            │
  │    - agents/actor.py (AgentActor for exclusion)      │
  │    - pydantic_ai (Tool, ModelRetry)                  │
  │    - agents/deps.py (AgentDeps in RunContext)        │
  │                                                      │
  │  OUTBOUND DEPS:                                      │
  │    - NetworkAdapter.request() (tool call routing)    │
  │    - Matrix children (schema reading)                │
  └──────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────┐
  │                  agents/actor.py                      │
  │  AgentActor: storable agent instances                 │
  │                                                      │
  │  INBOUND DEPS:                                       │
  │    - actor_model.py (ActorModel base)                │
  │    - agents/tool_model.py (AgentTool via ListRef)    │
  │    - agents/mixin.py (AgentMixin via __agent__)      │
  │    - decorators.py (expose_route)                    │
  │                                                      │
  │  OUTBOUND DEPS:                                      │
  │    - registered as Matrix child (routable)           │
  │    - exposes /run HTTP endpoint                      │
  └──────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────┐
  │                agents/schema_ext.py                   │
  │  @schema_extension(after='methods')                   │
  │  Injects 'agent' section into JSON Schema             │
  │                                                      │
  │  INBOUND DEPS:                                       │
  │    - proto_schema.py (schema_extension decorator)    │
  │    - agents/actor.py (AgentActor subclass check)     │
  │                                                      │
  │  OUTBOUND DEPS:                                      │
  │    - Schema consumed by frontend (agent detection)   │
  └──────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────┐
  │                  agents/deps.py                       │
  │  AgentDeps dataclass (adapter, user, agent_addr)     │
  │                                                      │
  │  INBOUND DEPS: None (TYPE_CHECKING only)             │
  │  OUTBOUND DEPS: Injected into every tool function    │
  └──────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────┐
  │               agents/tool_model.py                    │
  │  AgentTool: storable tool reference (target, desc)   │
  │                                                      │
  │  INBOUND DEPS: actor_model.py                        │
  │  OUTBOUND DEPS: AgentActor.tools ListRef             │
  └──────────────────────────────────────────────────────┘
```

#### Integration with Actor System

The agent subsystem is deeply integrated with the Actor system:

1. **Tool routing**: All tool calls flow through `NetworkAdapter.request()` -> `Actor.send()` -> `Matrix._route()` -> target actor's `handler()`. This is the same path as HTTP requests in Level 3 routing.

2. **Adapter lifecycle**: Each agent run creates a transient `NetworkAdapter` registered as a Matrix child. The adapter's `inbox()` handles response correlation via `pending` futures. Cleanup happens in `finally` blocks.

3. **Message format**: Tool calls use `TX` envelopes with `meta.user` for auth context, same as network requests.

#### Integration with Schema Pipeline

`schema_ext.py` uses `@schema_extension(after='methods')` — the standard pipeline extension mechanism from `proto_schema.py`. The `agent` stage runs after `methods` (so method signatures are available). The schema output feeds the frontend for agent-aware UI rendering.

#### Integration with Storage

`AgentActor` and `AgentTool` are `__storable__ = True` models using the standard `StorableMixin` + `SQLiteStorage` path. `AgentActor.constraints` is a `dict` field, auto-serialized to JSON TEXT by the framework's existing JSON field handling.

#### Integration with Routes

`AgentActor.run()` is decorated with `@expose_route('/run', methods=['POST'])`, creating a standard REST endpoint. The route layer handles auth, parameter injection, and response serialization identically to any other model method.

#### Integration with Frontend

The `agent` section in schema (from `schema_ext.py`) tells the frontend that a model is agent-capable. The `run_endpoint` pattern (`/agents/{id}/run`) enables UI components to trigger agent runs. The streaming variant works via the standard `<ntx-stream>` SSE component.

---

### 2.3 What's Easy to Change

1. **Add a new config key**: Add to `AGENT_DEFAULTS` in `config.py`, read it in `run()`, done.

2. **Change the default LLM**: `config.py:31` — single line change, cascades everywhere.

3. **Add guardrails to `run()`**: Override `run()` on a model — the `fullmethod` descriptor makes this natural:
   ```python
   class SafeProduct(ActorModel):
       __agent__ = True
       async def run(self, task, **kwargs):
           if 'delete' in task.lower():
               return {'answer': 'Deletion not allowed', 'usage': {}}
           return await super().call(task, **kwargs)
   ```

4. **Add a new schema extension**: Write a function, decorate with `@schema_extension`, import it. Zero modification to existing code.

5. **Add tools to an existing agent**: Via API (`POST /agents/1/agent_tools`) or code (`join_cls.create(...)`). No code changes.

6. **Custom prompt**: Pass `prompt=` to `run()` or set `__agent__ = {'prompt': '...'}`.

---

### 2.4 What's Hard to Change

1. **Replace pydantic-ai**: `agentic()` and `agentic_stream()` are tightly coupled to pydantic-ai's `Agent`, `UsageLimits`, `Tool`, `RunContext`, `ModelRetry`, and `TestModel`. Swapping to a different LLM framework requires rewriting both engine methods and all tool generation code.

2. **Non-actor tool sources**: `discover_tools()` only discovers from Matrix children. Adding tools from external HTTP APIs, MCP servers, or databases requires a new discovery mechanism. The `ToolSpec` abstraction helps — but `_route_tool_call` hardcodes `adapter.request(TX(...))`.

3. **Synchronous agent execution**: The entire agent stack is `async`. Running agents from synchronous code requires `asyncio.run()` or equivalent. There is no sync wrapper.

4. **Tool call authentication granularity**: All tool calls carry the same user context (`meta.user`). There is no mechanism for tool-level permission scoping — an agent with `user=admin` can call any tool with admin privileges.

5. **Agent-to-agent communication**: An agent cannot currently invoke another agent's `run()` as a tool (auto-excluded at `tools.py:95-96`). Enabling this requires careful loop detection beyond the current self-exclusion.

6. **Streaming with tool calls**: `agentic_stream()` uses `result.stream_text(delta=True)` which only streams the final text output. Tool call results are not streamed — they appear as gaps in the text stream. Changing this requires deeper pydantic-ai integration.

---

### 2.5 Constraints & Limitations

1. **Single event loop**: The agent subsystem assumes a single `asyncio` event loop. Multi-threaded deployments (e.g., Django with thread-based workers) are incompatible.

2. **Matrix required**: Agents cannot function without a Matrix root. This means agents only work in Level 2+ bootstrapping. Level 1 (`create_app` without `routing='actor'`) may or may not have a Matrix depending on implementation.

3. **Flat tool namespace**: Tool names are `{tablename}_{method}`. Two models cannot have the same tablename (enforced elsewhere) but method name collisions across models are possible if tablenames are similar.

4. **No tool output validation**: Tool results are returned as JSON strings to the LLM. The LLM may misinterpret the format. There is no schema for tool return types.

5. **No conversation persistence**: `message_history` is in-memory only. Multi-turn conversations across HTTP requests require the client to persist and resend history.

6. **No agent orchestration**: There is no built-in mechanism for agent pipelines, parallel agent execution, or agent delegation. Each `run()` is independent.

---

### 2.6 Feature Integration Guide

**Example: Adding a "cost budget" constraint to agent runs**

Step 1 — Add config default:
```python
# config.py
AGENT_DEFAULTS = {
    ...
    'max_cost_usd': None,  # None = unlimited
}
```

Step 2 — Read in `run()` config cascade:
```python
# mixin.py, inside run()
max_cost = (kwargs.get('max_cost_usd')
            or model_conf.get('max_cost_usd')
            or defaults.get('max_cost_usd'))
if max_cost:
    constraints['max_cost_usd'] = max_cost
```

Step 3 — Enforce in `agentic()`:
```python
# mixin.py, inside agentic()
if constraints.get('max_cost_usd'):
    usage_limits = usage_limits or UsageLimits()
    # pydantic-ai supports token_limit which can approximate cost
    usage_limits.request_tokens_limit = int(constraints['max_cost_usd'] * 100000)
```

Step 4 — Expose in schema:
```python
# schema_ext.py
safe_keys = {'self_tools', 'neighbors', 'neighbor_depth', 'max_cost_usd'}
```

Step 5 — Add test:

```python
# test_mixin.py
async def test_cost_budget_constraint(self, fresh_matrix):
    result = await AgenticProduct.call(
        task='Test',
        llm=TestModel(call_tools=[]),
        constraints={'max_cost_usd': 0.01},
    )
    assert 'answer' in result
```

Step 6 — Update CLAUDE.md with new config key.

**Files touched**: `config.py`, `mixin.py`, `schema_ext.py`, `test_mixin.py`, `CLAUDE.md`.
**Files NOT touched**: `tools.py`, `deps.py`, `actor.py`, `tool_model.py`, `proto_model.py`, frontend.

This demonstrates the design's strength: new features flow through the existing cascade without modifying the engine.

---

### 2.7 Cross-Cutting Concerns

#### Logging

All agent modules use `logging.getLogger('n3tx.agents')`. Coverage:
- Tool discovery warnings: `tools.py:71, 77` (missing actors, no schema)
- Self-exclusion debug: `tools.py:66`
- No tools warning: `mixin.py:414-416`

**Gap**: No logging in `run()` or `agentic()` for start/end/duration. An agent run that takes 30 seconds produces zero log output. Add structured logging with run_id, tool count, LLM model, token usage.

#### Authentication

Auth flows through three layers:
1. HTTP layer: JWT validated by route middleware
2. `run(user=...)`: user dict passed to `agentic()`
3. `_route_tool_call`: user injected into TX meta
4. Target actor: `handler_crud._authorize()` checks `__access__` rules

**Gap**: No auth on `agentic()` itself. If called directly (bypassing `run()`), any user context can be fabricated. The design intentionally separates policy (`run()`) from engine (`agentic()`), so this is by design — but it means `agentic()` must never be exposed via HTTP directly.

#### Configuration

The 3-tier cascade (`AGENT_DEFAULTS < __agent__ dict < run() kwargs`) is clean and consistent. The `N3TX_AGENT_DEFAULTS` env var override (`config.py:34-36`) uses `json.loads()` — a malformed JSON env var would crash at import time with an opaque error.

#### Serialization

`AgentActor.run()` returns `json.dumps(result, default=str)` — the `default=str` handles pydantic-ai message objects that are not natively JSON-serializable. This is pragmatic but lossy (complex objects become their `str()` representation).

---

### Summary: Top 5 Action Items

| Priority | Item | Effort |
|----------|------|--------|
| 1 | Fix `test_agent_run.py:55` comparison bug (`list >= int`) | 5 min |
| 2 | Extract duplicated config cascade + adapter lifecycle into shared helpers | 1 hr |
| 3 | Implement `neighbor_depth` or remove it from config + docs | 1 hr |
| 4 | Add structured logging to `run()`/`agentic()` (start, end, usage, run_id) | 30 min |
| 5 | Cache `discover_tools()` + `create_tool_function()` results per tool address set | 1 hr |
