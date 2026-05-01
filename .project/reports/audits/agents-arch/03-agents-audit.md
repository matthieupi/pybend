# Agents (LLM Integration) -- Deep Audit Report

**Subsystem:** `src/n3tx/core/agents/`
**Branch:** v0.9 (through v0.10 development)
**Date:** 2026-03-09
**Sources:** Architecture & API analysis (01), Quality & Extensibility analysis (02), direct source verification

---

## Executive Summary

The agents subsystem adds LLM-powered reasoning to N3TX models via a single flag (`__agent__ = True`). It bridges the Pydantic AI engine with the N3TX actor/matrix messaging system, enabling any model to reason about its own schema, call tools on itself and its neighbors, and stream progressive output -- all with zero configuration. The subsystem comprises 8 files (5 classes, 8 functions, 1 config dict) and is tested by 68 test methods across 1,649 lines of test code.

The architecture is sound. The policy/engine split between `run()` and `agentic()` is the standout design decision: it cleanly separates configuration resolution and guardrails from the raw LLM execution loop, enabling both zero-config usage and advanced control. Tool discovery is schema-driven and routes through the existing actor messaging system as TX messages, which means tool calls inherit existing auth, routing, and interceptor infrastructure for free. The mixin injection pattern (`__agent__ = True` triggers MRO insertion) is consistent with the framework's established `__storable__` pattern.

The most significant issues are: (1) a confirmed test bug where a list is compared to an integer (`test_agent_run.py:54`), (2) the `neighbor_depth` configuration key is declared and exposed in schema but never implemented, creating a misleading API surface, (3) the `_route_tool_call` error handler assumes `response.data` is always a dict (verified safe given `TX.error()` always produces a dict, but the code is fragile if error paths change), and (4) approximately 120 lines of near-identical adapter lifecycle and config cascade code are duplicated across four methods.

**Top 3 recommendations:**
1. **Fix the test bug** at `example_grants/tests/test_agent_run.py:54` -- change `result["messages"] >= 2` to `result["message_count"] >= 2`. This is a correctness issue that will raise `TypeError` in Python 3 if the test ever runs.
2. **Decide on `neighbor_depth`** -- either implement recursive neighbor traversal with cycle detection, or remove it from `AGENT_DEFAULTS` and `schema_ext.safe_keys` to stop advertising unimplemented functionality.
3. **Extract adapter lifecycle** into a shared helper or context manager to eliminate the 4x code duplication in `mixin.py` and reduce the surface area for lifecycle bugs.

---

## Component Overview

```
                         +------------------+
                         |    config.py     |
                         | AGENT_DEFAULTS   |
                         +--------+---------+
                                  |
           3-tier cascade:  defaults < __agent__ < kwargs
                                  |
  +-----------+          +--------v---------+          +------------------+
  |proto_model|--inject->|   AgentMixin     |<-inherit-|   AgentActor     |
  |__init_sub |          | (mixin.py)       |          | (actor.py)       |
  | class__   |          |                  |          |                  |
  +-----------+          | ctx()            |          | run() override   |
                         | tools()          |          | _resolve_tool_   |
                         | run()     policy |          |   addrs()        |
                         | agentic() engine |          +--------+---------+
                         | run_stream()     |                   |
                         | agentic_stream() |                   | ListRef
                         +--------+---------+                   v
                                  |                   +------------------+
                                  v                   |  AgentTool       |
                         +------------------+         | (tool_model.py)  |
                         |    tools.py      |         | target, desc     |
                         |                  |         +------------------+
                         | discover_tools() |
                         | _crud_tool_specs |
                         | _method_tool_   |
                         |   specs()       |
                         | create_tool_    |<--- exec() dynamic signatures
                         |   function()   |
                         | make_tool()     |
                         | _route_tool_   |--> adapter.request(TX) --> Matrix
                         |   call()       |
                         +--------+--------+
                                  |
                    +-------------+-------------+
                    |                           |
           +--------v--------+        +--------v--------+
           | pydantic_ai     |        | NetworkAdapter   |
           | Agent.run()     |        | request(TX)      |
           | Agent.run_      |        | inbox(response)  |
           |   stream()     |        +------------------+
           +-----------------+
                                      +------------------+
                         +----------->| schema_ext.py    |
                         | @schema_   | agent() stage    |
                         | extension  | -> schema.agent  |
                         +----------->+------------------+

           +------------------+
           |    deps.py       |
           | AgentDeps        |
           |   adapter        |
           |   user (dict)    |
           |   agent_addr     |
           +------------------+
```

**File inventory:**

| File | Size | Role |
|------|------|------|
| `__init__.py` | 27 lines | Package exports + schema_ext side-effect registration |
| `mixin.py` | 653 lines | Core mixin: ctx, tools, run, agentic, run_stream, agentic_stream |
| `actor.py` | 130 lines | Concrete agent model with DB-stored config |
| `tools.py` | 312 lines | Tool discovery, function generation, TX routing |
| `deps.py` | 28 lines | Pydantic AI dependency injection container |
| `schema_ext.py` | 44 lines | Schema pipeline extension for agent metadata |
| `tool_model.py` | 33 lines | Simple model for storable tool references |
| `config.py` | Lines 27-36 | `AGENT_DEFAULTS` global dict |

---

## Data Flow

### Non-Streaming Request Lifecycle

```
User Code / HTTP
    |
    v
run(task='...', **kwargs)                    @fullmethod -- receives cls or self
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
    |       |-- For each addr: matrix._children[addr].schema()
    |       |-- _crud_tool_specs()  (if storable)
    |       |-- _method_tool_specs() (from schema.methods)
    |       v
    |   List[ToolSpec]
    |
    |-- make_tool(spec) for each ToolSpec
    |       |-- create_tool_function(spec)  [exec()-based]
    |       |-- pydantic_ai.Tool(fn, takes_ctx=True)
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
    |       v
    |   tool_function(ctx, param1, param2, ...)
    |       |-- _route_tool_call(ctx, target_addr, method, data)
    |       |       |-- TX(name=method, source=adapter.addr, target=target_addr)
    |       |       |-- adapter.request(tx) -> Future
    |       |       |-- Matrix routes TX -> target actor
    |       |       |-- Actor handler: CRUD or method dispatch
    |       |       |-- reply TX -> adapter.inbox() -> resolves Future
    |       |       v
    |       |-- json.dumps(response.data) -> return to LLM
    |       v
    |   LLM processes result, may call more tools or generate final answer
    |
    v
result = {answer, usage, messages, message_count}
    |
    v
finally: root._children.pop(adapter_addr)   cleanup
```

### State Lifecycle

| State | Location | Lifetime | Mutated By |
|-------|----------|----------|------------|
| `AGENT_DEFAULTS` | `config.py` module global | Process lifetime | `config.configure()`, env var |
| `__agent__` flag/dict | ClassVar on model class | Class lifetime | Set once at class definition |
| AgentMixin in MRO | `cls.__bases__` | Class lifetime | `__init_subclass__` in ProtoModel |
| Transient adapter | `matrix._children[addr]` | Single `run()` call | Created in `run()`, removed in `finally` |
| `_pending` futures | `adapter._pending` dict | Per-request | Set in `request()`, resolved in `inbox()` |
| Tool specs | Local variable in `agentic()` | Single `run()` call | Rebuilt every call (no caching) |
| Pydantic AI Agent | Local variable in `agentic()` | Single `run()` call | Created fresh every call |
| AgentActor DB fields | SQLite rows | Persistent | Standard CRUD operations |

---

## Key Findings

### Critical Issues

#### F-01: Test bug -- list compared to integer
- **Finding:** `test_agent_run.py:54` compares `result["messages"]` (a list) to `2` (an integer), which raises `TypeError` in Python 3.
- **Evidence:** `example_grants/tests/test_agent_run.py:54`
  ```python
  assert result["messages"] >= 2  # at least prompt + response
  ```
  `result` comes from `json.loads(result_str)` where `result_str` is the output of `AgentActor.run()`, which calls `json.dumps(result, default=str)` on the dict from `agentic()`. The `messages` key is a list of conversation messages, not an integer.
- **Severity:** High -- this test will raise `TypeError` if it ever reaches this line with a real result. The fact that it has not been caught suggests either the test is not running or an earlier assertion fails first.
- **Recommendation:** Change to `assert result["message_count"] >= 2` or `assert len(result["messages"]) >= 2`.

#### F-02: `neighbor_depth` is declared but never implemented
- **Finding:** The `neighbor_depth` configuration key exists in `AGENT_DEFAULTS` and is exposed in the schema via `schema_ext.safe_keys`, but the `tools()` method only follows direct ListRef relationships with no recursion.
- **Evidence:** `config.py:30` declares `'neighbor_depth': 1`. `schema_ext.py:32` lists it in `safe_keys`. But `mixin.py:252-257` iterates `get_list_fields(cls)` with no depth parameter and no recursive call.
  ```python
  # mixin.py:252-257 -- no depth control
  if conf.get('neighbors', True):
      from n3tx.core.utils.introspection import get_list_fields
      for field_name, model_cls in get_list_fields(cls):
          if hasattr(model_cls, '__tablename__'):
              addrs.append(model_cls.__tablename__)
  ```
- **Severity:** Medium -- a developer setting `neighbor_depth: 2` would expect transitive discovery (Product -> Comment -> User) but get nothing beyond depth 1.
- **Recommendation:** Either implement BFS/DFS traversal with cycle detection in `tools()`, or remove `neighbor_depth` from `AGENT_DEFAULTS` and `schema_ext.safe_keys` to avoid advertising non-existent functionality.

#### F-03: `_build_instance_text()` double-evaluates `str(v)`
- **Finding:** The truncation loop calls `str(v)` twice per iteration -- once to compute `s` and again in the conditional assignment.
- **Evidence:** `mixin.py:170-174`
  ```python
  for k, v in data.items():
      s = str(v)
      if len(s) > 200:
          s = s[:200] + '...'
      truncated[k] = v if len(str(v)) <= 200 else s  # <-- str(v) again
  ```
- **Severity:** Low -- functionally correct in nearly all cases, but wasteful and could produce inconsistent results if `__str__` has side effects.
- **Recommendation:** Change line 174 to `truncated[k] = v if len(s) <= 200 else s`.

#### F-04: `agentic_stream()` error handler exposes internal details
- **Finding:** The catch-all `except Exception` in `agentic_stream()` yields `str(e)` as the error message, which could contain LLM API keys, stack traces, or other sensitive information from Pydantic AI or HTTP client errors.
- **Evidence:** `mixin.py:644-649`
  ```python
  except Exception as e:
      yield {
          'name': 'error',
          'data': {'message': str(e), 'code': 500},
          'meta': {'stream': True, 'error': True, 'seq': seq},
      }
  ```
- **Severity:** Medium -- depends on what the LLM client includes in exception messages. API key leaks are possible if the HTTP client includes the full request URL with embedded credentials.
- **Recommendation:** Sanitize the error message before yielding. Log the full exception internally, but yield only a generic message to the client: `{'message': 'Agent execution failed', 'code': 500}`.

---

### Design Strengths

#### S-01: Policy/engine split (run vs agentic)
The separation between `run()` (policy: config cascade, guardrails, adapter lifecycle) and `agentic()` (engine: raw LLM loop with explicit params) is the single best design decision in this subsystem. It enables zero-config usage for simple cases and full programmatic control for advanced use. The same split is mirrored cleanly for streaming (`run_stream` / `agentic_stream`).

**Evidence:** `mixin.py:267-348` (run) delegates to `mixin.py:350-468` (agentic) after resolving all configuration. `AgentActor.run()` at `actor.py:103-129` demonstrates the override pattern: it reads config from DB fields and calls `agentic()` directly, bypassing the mixin's cascade.

#### S-02: Schema-driven tool discovery
Tools are discovered from actor schemas at runtime, not hardcoded. CRUD operations are auto-generated from model properties, and custom methods are discovered from the `schema.methods` section. This means adding a new `@expose_route` method to any actor automatically makes it available as an agent tool.

**Evidence:** `tools.py:43-101` (discover_tools), `tools.py:104-158` (_crud_tool_specs), `tools.py:161-196` (_method_tool_specs). The tool system reads schemas the same way the frontend does, maintaining the "schema is the contract" principle.

#### S-03: TX-based tool routing inherits auth for free
Tool calls route through the existing actor system as TX messages. This means they automatically pass through any interceptors (including auth interceptors) registered on target actors. Agent tool calls are authorized the same way as HTTP requests -- no separate auth system needed.

**Evidence:** `tools.py:207-214` -- user context is placed in `TX.meta`, following the same convention as `auth_interceptor.py`. The agent does not bypass any auth layer.

#### S-04: Transient adapter isolation with cleanup
Each `run()` call creates a UUID-addressed adapter that is cleaned up in a `finally` block. Concurrent agent runs on the same model never share adapters.

**Evidence:** `mixin.py:319-348` (create + cleanup). Tested by `TestConcurrentRuns.test_concurrent_runs_isolated` and `TestRun.test_adapter_cleaned_up_on_error`.

#### S-05: Self-loop prevention in tool discovery
An agent never discovers itself as a tool, preventing infinite reasoning loops. Additionally, `run` and `stream_run` methods on AgentActor subclasses are auto-excluded from tool discovery.

**Evidence:** `tools.py:64-66` (self-exclusion), `tools.py:94-96` (AgentActor method exclusion).

#### S-06: Consistent mixin injection pattern
The `__agent__ = True` injection follows the same MRO pattern as `__storable__ = True`, keeping the framework's extension model uniform. One ClassVar flag, zero imports for the model developer.

**Evidence:** `proto_model.py:90-94` (conditional import + `__bases__` mutation). Same pattern as StorableMixin injection.

---

### Design Trade-offs

#### T-01: Per-run Agent/tool recreation vs caching
**Gained:** Correctness -- schemas may change between runs, and a cached agent would use stale tool definitions. Simplicity -- no cache invalidation logic.
**Sacrificed:** Performance -- every `run()` call re-discovers tools, re-generates `exec()`-based functions (one per tool), and re-creates the Pydantic AI Agent. For a model with 5 neighbors averaging 7 tools each, that is 35 `exec()` calls per run.
**Assessment:** Correct trade-off for v0.10. Cache when benchmarks show it matters. The fix (cache ToolSpecs by schema hash, cache Agent by config fingerprint) is straightforward and localized.

#### T-02: `exec()` for tool function generation
**Gained:** Properly typed Python functions with real signatures that Pydantic AI can introspect for JSON Schema generation. This is the same approach used by Python's `dataclasses`, `namedtuple`, and `attrs`.
**Sacrificed:** Readability and debuggability -- exec'd code does not appear in stack traces with useful file/line information.
**Assessment:** Correct. The alternatives (metaclasses, closures with `__signature__`) are more complex and less reliable for Pydantic AI's introspection. The namespace is tightly controlled, input comes from trusted model schemas, and description strings are properly escaped (`tools.py:274`).

#### T-03: `AgentActor.run()` returns JSON string vs AgentMixin.run() returns dict
**Gained:** `AgentActor.run()` is an `@expose_route` method that must return a value suitable for HTTP serialization. Returning a JSON string avoids double-serialization issues in the route layer.
**Sacrificed:** API consistency -- a developer holding an `AgentActor` reference must `json.loads()` the result, unlike `AgentMixin.run()` which returns a dict directly.
**Assessment:** Acceptable but should be documented. The asymmetry is an inherent tension between the HTTP API contract (strings) and the programmatic API contract (dicts). Consider adding a `run_dict()` helper on AgentActor for programmatic callers.

#### T-04: Sync error propagation vs streaming error yielding
**Gained:** `agentic()` raises exceptions to the caller (standard Python pattern). `agentic_stream()` catches exceptions and yields error chunks (required for SSE/WebSocket consumers who need in-band error signaling).
**Sacrificed:** Consistency -- callers must handle errors differently depending on execution mode.
**Assessment:** This asymmetry is inherent to the sync-vs-streaming paradigm and is the correct approach. The key is documentation: both paths should be explicitly documented with error handling examples.

---

### Improvement Opportunities

| # | Improvement | Impact | Effort | Category |
|---|------------|--------|--------|----------|
| 1 | Extract adapter lifecycle into `_adapter_context()` context manager | Eliminates 4x code duplication (~60 lines), reduces lifecycle bugs | Low | Refactoring |
| 2 | Extract `_resolve_config()` helper from `run()` and `run_stream()` | Eliminates 2x config cascade duplication (~25 lines) | Low | Refactoring |
| 3 | Replace `TX(name='', source='', target='').uuid` with `str(uuid.uuid4())` | Removes 4 wasteful TX instantiations per run | Trivial | Performance |
| 4 | Add typed kwargs to `run()` instead of `**kwargs` | Catches typos at call site; enables IDE autocomplete | Low | Type Safety |
| 5 | Use `config.AGENT_DEFAULTS['llm']` as fallback in `agentic()` instead of hardcoded `'ollama:llama3.1'` | Single source of truth for default LLM | Trivial | Consistency |
| 6 | Add structured logging for tool discovery and tool calls | Enables observability, debugging, and cost tracking | Medium | Observability |
| 7 | Add `Actor.unregister()` public method; stop reaching into `_children` | Cleaner boundary; removes private-attribute access | Low | Encapsulation |
| 8 | Cache tool functions by ToolSpec fingerprint | Eliminates repeated `exec()` calls for identical tools | Medium | Performance |
| 9 | Add streaming + tool-calling tests | Covers an untested interaction | Medium | Test Coverage |
| 10 | Discover `schema_ext.methods` list from class instead of hardcoding | Prevents list going stale when new agent methods are added | Low | Correctness |

---

## Downstream Use Guide

### For Bug Hunting

**Risk areas ranked by probability of containing bugs:**

1. **`_resolve_tool_addrs()` href parsing** (`actor.py:82-93`) -- Parses URLs by splitting on `/` and extracting the last segment as an integer ID. Fragile if URL format changes or trailing slashes vary. The `try/except` handles failures gracefully, but incorrect IDs would silently resolve wrong tools.

2. **Streaming adapter cleanup** (`mixin.py:513-532`) -- The `finally` block in `run_stream()` only runs when the async generator is properly closed (via `aclose()` or full exhaustion). If a consumer abandons the generator, cleanup depends on GC finalization timing.

3. **Config cascade edge cases** (`mixin.py:283-312`) -- The 3-tier cascade uses `dict.update()` for constraints, which replaces keys rather than deep-merging. Nested constraint dicts (if ever added) would not merge correctly.

4. **`_build_schema_text()` with unusual schema shapes** (`mixin.py:50-158`) -- Assumes standard schema structure. Custom schema extensions that add non-standard keys to `properties` entries could produce garbled context text.

**Untested edge cases with specific scenarios:**

- `run_stream()` with a tool-calling LLM (streaming + tools interaction)
- `result_type` (structured output) with `message_history` (multi-turn)
- Full 3-tier cascade with all three tiers providing different values for the same key
- `constraints` with `max_iterations` actually hitting the limit (TestModel completes too quickly)
- Two actors with the same `__tablename__` prefix generating colliding tool names
- `N3TX_AGENT_DEFAULTS` env var override at startup
- Generator abandonment without `aclose()` in a production HTTP handler

**Suggested test cases to write:**

```python
# ---- Test: run() kwargs validation ----
# File: src/n3tx/core/agents/tests/test_mixin.py
# Purpose: Ensure misspelled kwargs are not silently ignored

@pytest.mark.asyncio
async def test_run_kwargs_with_typo_logged_or_rejected(matrix_fixture, tmp_path):
    """Verify run() does not silently ignore misspelled kwargs."""
    class M(ActorModel):
        __agent__ = True
        __tablename__ = 'typo_test'
        name: str = Field(default='x')

    # 'tak' is a typo for 'task' -- should either raise or log a warning
    # Currently: typos like run(tak='...') are silently ignored
    # Expected: TypeError or logged warning
    with pytest.warns(UserWarning) or pytest.raises(TypeError):
        await M.run(task='hello', promt='custom prompt',
                    llm=TestModel(call_tools=[]))


# ---- Test: streaming + tool-calling ----
# File: src/n3tx/core/agents/tests/test_mixin.py
# Purpose: Cover the untested streaming+tools interaction

@pytest.mark.asyncio
async def test_streaming_with_tool_calls(matrix_fixture, tmp_path):
    """run_stream() with TestModel(call_tools=['xxx_list'])
    should yield text chunks and a done chunk."""
    # Setup: register a storable actor, create test model with call_tools
    chunks = []
    async for chunk in Agent.run_stream(
        task='List items',
        llm=TestModel(call_tools=['items_list']),
    ):
        chunks.append(chunk)
    assert any(c['name'] == 'text' for c in chunks)
    assert chunks[-1]['name'] == 'done'


# ---- Test: structured output ----
# File: src/n3tx/core/agents/tests/test_mixin.py
# Purpose: Verify result_type produces typed output

@pytest.mark.asyncio
async def test_result_type_structured_output(matrix_fixture, tmp_path):
    """run(result_type=MyModel) returns a validated MyModel instance."""
    from pydantic import BaseModel
    class Summary(BaseModel):
        title: str
        score: float

    result = await Agent.run(
        task='Summarize',
        result_type=Summary,
        llm=TestModel(call_tools=[]),
    )
    assert isinstance(result['answer'], Summary)


# ---- Test: 3-tier cascade completeness ----
# File: src/n3tx/core/agents/tests/test_mixin.py
# Purpose: All three tiers contribute simultaneously

@pytest.mark.asyncio
async def test_full_3_tier_cascade(matrix_fixture, tmp_path, monkeypatch):
    """AGENT_DEFAULTS, __agent__ dict, and run() kwargs all contribute;
    higher tiers override lower for the same key."""
    import n3tx.core.config as config
    monkeypatch.setattr(config, 'AGENT_DEFAULTS', {
        'llm': 'tier1_llm',
        'constraints': {'max_iterations': 10},
    })
    class M(ActorModel):
        __agent__ = {'llm': 'tier2_llm', 'constraints': {'max_iterations': 5}}
        __tablename__ = 'cascade_test'
    # kwargs override: llm should be tier3, constraints should merge
    # This test would need to intercept the agentic() call to verify params


# ---- Test: tool name collision ----
# File: src/n3tx/core/agents/tests/test_tools.py
# Purpose: Detect if duplicate tool names cause Pydantic AI errors

def test_tool_name_collision_across_actors():
    """Two actors with same tablename prefix could generate
    colliding tool names like 'items_create'."""
    # Create two actors with overlapping method names
    # Verify that discover_tools handles or deduplicates them


# ---- Test: generator abandon cleanup ----
# File: src/n3tx/core/agents/tests/test_mixin.py
# Purpose: Verify adapter is cleaned up even without aclose()

@pytest.mark.asyncio
async def test_adapter_cleanup_on_generator_abandon(matrix_fixture, tmp_path):
    """Adapter is eventually cleaned up if generator is
    abandoned without explicit aclose()."""
    from n3tx.core.actors.actor import Actor
    root = Actor.root()
    initial_count = len(root._children)
    gen = Agent.run_stream(task='test', llm=TestModel(call_tools=[]))
    # Consume one chunk then abandon
    chunk = await gen.__anext__()
    # Delete without aclose
    del gen
    import gc; gc.collect()
    # After GC, adapter should be cleaned up
    assert len(root._children) == initial_count
```

### For Feature Development

**Extension points with difficulty ratings:**

| Extension | How | Difficulty |
|-----------|-----|-----------|
| Add a new tool type | Create an actor with `@expose_route`, add its tablename to `__agent__['tools']` | Trivial |
| Change LLM provider | Pass `run(llm='anthropic:claude-sonnet-4-5-20250929')` or any Pydantic AI model | Trivial |
| Custom system prompt | Set `__agent__['prompt']` or `run(prompt='...')` | Trivial |
| Add guardrails/audit | Override `run()` on the model class (it is the policy layer) | Easy |
| Result processors | Wrap `agentic()` call in a `run()` override | Easy |
| Tool interceptors | Use actor `use()` interceptors on target actors | Easy |
| Structured output | Pass `run(result_type=MyPydanticModel)` | Easy |
| Cost tracking | Override `run()`, inspect `result['usage']` after `agentic()` | Easy |
| Custom tool functions | Create `ToolSpec` manually and pass to `make_tool()` | Medium |
| Multi-agent delegation | Wrap another agent's `run()` as a tool with cycle detection | Hard |
| Replace Pydantic AI | Rewrite `agentic()`, `agentic_stream()`, tool generation | Hard |

**Patterns to follow (cite existing code as templates):**

- **Override `run()` for custom policy:** See `AgentActor.run()` at `actor.py:103-129`. It reads config from DB fields, resolves tool addresses from the join table, and delegates to `agentic()` with explicit params. Template:

  ```python
  # File: your_app/models/audited_product.py
  class AuditedProduct(ActorModel):
      __agent__ = True
      __tablename__ = 'audited_products'
      name: str = Field(min_length=1)

      @fullmethod
      async def run(target, task: str, **kwargs):
          """Policy override: add audit logging and cost tracking."""
          import time
          start = time.monotonic()
          user = kwargs.get('user')
          logger.info("Agent run started: task=%s user=%s", task[:50], user)

          # Delegate to the engine via the mixin's run()
          result = await AgentMixin.run(target, task=task, **kwargs)

          elapsed = time.monotonic() - start
          logger.info("Agent run completed: tokens=%s time=%.2fs",
                      result['usage'], elapsed)
          return result
  ```

- **Add a new schema extension:** See `schema_ext.py` -- use `@schema_extension(after='methods')` decorator. The function receives `(cls, schema)` and returns the modified schema dict. Template:

  ```python
  # File: your_app/schema_extensions.py
  from n3tx.core.models.proto_schema import schema_extension

  @schema_extension(after='agent')
  def cost_tracking(cls, schema: dict) -> dict:
      """Add cost tracking metadata to agent-enabled models."""
      if not schema.get('agent', {}).get('enabled'):
          return schema
      schema['agent']['cost_tracking'] = {
          'enabled': True,
          'budget_field': 'max_cost_per_run',
      }
      return schema
  ```

- **Add interceptors to tool targets:** See `auth_interceptor.py` for the pattern. This applies to all TX messages the actor receives, including tool calls from agents. Template:

  ```python
  # File: your_app/interceptors.py
  async def rate_limit_interceptor(tx):
      """Rate-limit tool calls from agents."""
      if tx.meta.get('user'):
          user_id = tx.meta['user'].get('id')
          if not check_rate_limit(user_id, tx.name):
              return tx.error("Rate limit exceeded", code=429)
      return tx

  # In setup:
  grants_actor.use(rate_limit_interceptor, on='inbox')
  ```

- **Create custom tool functions:** Use `ToolSpec` and `make_tool()` for tools that do not correspond to any actor. Template:

  ```python
  # File: your_app/custom_tools.py
  from n3tx.core.agents.tools import ToolSpec, make_tool

  web_search_spec = ToolSpec(
      actor_addr='web_tools',
      method_name='search',
      tool_name='web_search',
      description='Search the web for information',
      parameters={
          'type': 'object',
          'properties': {
              'query': {'type': 'string', 'description': 'Search query'},
              'max_results': {'type': 'integer', 'description': 'Max results'},
          },
          'required': ['query'],
      },
  )
  web_search_tool = make_tool(web_search_spec)
  # Pass to agentic() via tools list or register the web_tools actor
  ```

**Constraints to be aware of:**

1. `agentic()` requires a Matrix root to exist. If you are testing agent code in isolation, you must create a Matrix instance first (see `conftest.py` in the agents tests).
2. `AgentActor.run()` returns `str` (JSON), not `dict`. If calling programmatically, wrap with `json.loads()`.
3. The `__agent__` flag must be set at class definition time -- it cannot be toggled at runtime because MRO injection happens in `__init_subclass__`.
4. Tool discovery accesses `root._children` (private attribute). If the actor system's internal representation changes, tool discovery will break.

**Common pitfalls:**

- Calling `agentic()` directly without setting up an adapter (it creates one internally, but the resulting transient adapter gets a `root` reference that may not be the one you expect if multiple Matrix instances exist).
- Expecting `run()` at class level to have instance data -- `Product.run(task='...')` creates a `Product()` with default field values. The LLM context will show defaults.
- Modifying `AGENT_DEFAULTS` at runtime after agents have already been configured -- the dict is read each time `run()` is called, so changes take effect immediately, but any agents that cached their config in `__agent__` dicts won't pick up the changes.

### For Integration Planning

**Integration boundaries with data contracts:**

| Boundary | Direction | Contract | Stability |
|----------|-----------|----------|-----------|
| Agents -> Actor system | AgentMixin creates/registers/removes NetworkAdapter; calls `Actor.root()`, `root.register()`, `root._children` | Private API (`_children`) | Medium -- depends on Actor internals |
| Agents -> Schema pipeline | `@schema_extension(after='methods')` registers the `agent` stage | Public decorator API | High |
| Agents -> Storage layer | `discover_tools()` checks `issubclass(cls, StorableMixin)` | Public class check | High |
| Agents -> Route layer | `AgentActor.run()` uses `@expose_route` | Public decorator API | High |
| Agents -> Pydantic AI | Uses `Agent`, `UsageLimits`, `Tool`, `ModelRetry` | Pydantic AI public API, version-sensitive | Medium |
| Agents -> Frontend | Schema `agent` section: `{enabled, config, methods, run_endpoint}` | Read-only JSON Schema contract | High |
| Agents -> Config | Reads `config.AGENT_DEFAULTS` dict | Module-level global | High |
| ProtoModel -> Agents | Conditional import of `AgentMixin` in `__init_subclass__` | Internal injection mechanism | High |

**Impact analysis checklist -- what to verify when changing this subsystem:**

- [ ] Run agent unit tests: `cd /workspace/src/n3tx/core && python3 -m pytest agents/tests/`
- [ ] Run grants integration tests: `cd /workspace && python3 -m pytest example_grants/tests/`
- [ ] Verify schema output for `__agent__ = True` models (check `agent` section in JSON Schema)
- [ ] Test class-level and instance-level `run()` calls
- [ ] Test streaming path (`run_stream` / `agentic_stream`)
- [ ] Verify adapter cleanup after both success and error paths
- [ ] Check `AgentActor.run()` returns valid JSON string
- [ ] Verify tool discovery excludes self and AgentActor meta-methods

**Compatibility considerations:**

- Pydantic AI version changes may break the `Agent.run()`, `Agent.run_stream()`, `Tool()`, or `ModelRetry` APIs. Pin the Pydantic AI version. The specific imports used are:
  - `from pydantic_ai import Agent, UsageLimits` (mixin.py:377)
  - `from pydantic_ai.tools import Tool` (tools.py:303)
  - `from pydantic_ai import ModelRetry` (tools.py:218)
  - `result.usage()`, `result.all_messages()`, `result.output` (mixin.py:453-456)
  - `result.stream_text(delta=True)`, `result.get_output()` (mixin.py:613,624)
- Adding new agent methods to `AgentMixin` requires updating the hardcoded `methods` list in `schema_ext.py:41`.
- The `TX.error()` data format (`{'message': ..., 'code': ...}`) is assumed by `_route_tool_call()` at `tools.py:219`. Verified safe: `TX.error()` at `tx.py:37-45` always produces `data={'message': ..., 'code': ...}`. But if any custom actor handler returns a raw error TX with non-dict data, `_route_tool_call` would raise `AttributeError`.

**Dependency inventory:**

| Dependency | Import Site | Version Sensitivity | Fallback |
|-----------|------------|---------------------|----------|
| `pydantic_ai` | `mixin.py:377`, `tools.py:218,303` | High -- `Agent`, `Tool`, `ModelRetry` APIs | None -- hard dependency |
| `pydantic_ai.models.test.TestModel` | Tests only | Medium -- testing API | None -- needed for deterministic tests |
| `NetworkAdapter` | `mixin.py:315,394,499,562` | Medium -- `request()`, `inbox()` APIs | None -- core to TX routing |
| `Actor.root()` | `mixin.py:316,322,395,401,500,506,563,569,578,411` | Low -- stable classmethod | None -- fundamental to actor system |
| `introspection.get_list_fields()` | `mixin.py:117,254` | Low -- stable utility | None |
| `StorableMixin` | `tools.py:57` | Low -- type check only | None |

**Lifecycle ordering requirements:**

```
1. Matrix must be instantiated              (Actor.__matrix__ set)
    |
2. Models must be registered                (register_model() for storable)
    |
3. Models must be Matrix children           (ActorMeta auto-registers)
    |
4. AgentMixin injected via __agent__        (class definition time)
    |
5. Schema extension registered              (import time via __init__.py)
    |
6. Agent can run                            (run/agentic requires 1-3)
```

**Risk:** If `agents/__init__.py` is never imported (e.g., only `mixin.py` is imported directly via `__init_subclass__`), the schema extension is not registered. In practice this works because example apps import `AgentActor` from the package, triggering `__init__.py`. But a minimal app using only `__agent__ = True` without importing anything from the agents package could miss the schema extension.

### For Refactoring

**Technical debt ranked by severity and coupling risk:**

| # | Debt Item | Severity | Coupling | Risk |
|---|-----------|----------|----------|------|
| D-01 | Adapter lifecycle duplicated 4x in `mixin.py` | Medium | Low | Safe to extract -- each instance is nearly identical |
| D-02 | Config cascade duplicated between `run()` and `run_stream()` | Medium | Low | Safe to extract -- identical logic |
| D-03 | Default LLM `'ollama:llama3.1'` hardcoded in 6 places | Low | Low | Point all to `config.AGENT_DEFAULTS['llm']` |
| D-04 | `neighbor_depth` dead config | Medium | Low | Either implement or remove |
| D-05 | `_children` private access for adapter cleanup | Low | Medium | Requires adding `Actor.unregister()` method |
| D-06 | `schema_ext.py:41` hardcoded method list | Low | Low | Discover from class attributes |
| D-07 | TX created for UUID generation | Trivial | None | Replace with `uuid.uuid4()` |

**Suggested refactoring sequence (dependency order):**

1. **D-07: TX UUID** (zero risk, zero dependencies) -- Replace `TX(name='', source='', target='').uuid` with `str(uuid.uuid4())` in 4 locations. No tests affected.

2. **D-03: Default LLM consolidation** (low risk) -- In `agentic()` and `agentic_stream()`, change `llm = llm or 'ollama:llama3.1'` to `llm = llm or config.AGENT_DEFAULTS.get('llm', 'ollama:llama3.1')`. Keep `actor.py:59` Field default as-is (it is a DB default, not a runtime fallback).

3. **D-01 + D-02: Extract helpers** (medium risk, high impact) -- Create `_resolve_config(target, kwargs)` helper returning a config dict. Create `_create_transient_adapter()` returning `(adapter, root, adapter_addr)`. The async generator methods (`run_stream`, `agentic_stream`) cannot use `async with` context managers easily (async generators and context managers interact poorly in Python), so use a helper function + `try/finally` pattern:

   ```python
   def _create_transient_adapter():
       from n3tx.core.actors.tx import TX
       import uuid
       adapter_addr = f'_agent_{uuid.uuid4()}'
       adapter = NetworkAdapter(addr=adapter_addr)
       root = Actor.root()
       if not root:
           raise RuntimeError("No Matrix root.")
       root.register(adapter)
       return adapter, root, adapter_addr

   def _cleanup_adapter(root, adapter_addr):
       root._children.pop(adapter_addr, None)
   ```

4. **D-05: `Actor.unregister()`** (medium risk, cross-cutting) -- Add a public `unregister(addr)` method to Actor/Matrix. Update all 4 cleanup sites in `mixin.py`. This touches the actor subsystem, so coordinate with actor system tests.

5. **D-04: `neighbor_depth`** (medium risk, product decision) -- If implementing: add a `_discover_neighbors(cls, depth)` BFS in `mixin.py` that follows ListRef fields recursively with cycle detection. If removing: delete from `config.py:30` and `schema_ext.py:32`.

6. **D-06: Dynamic method list** (low risk) -- In `schema_ext.py:41`, replace the hardcoded list with introspection:
   ```python
   agent_methods = [name for name in ('run', 'run_stream', 'ctx', 'tools')
                    if hasattr(cls, name)]
   ```

**Before/after sketches for major refactoring candidates:**

**D-01: Adapter lifecycle extraction**

Before (`mixin.py:314-348`, repeated 4 times):
```python
from n3tx.core.api.network_adapter import NetworkAdapter
from n3tx.core.actors.actor import Actor
from n3tx.core.actors.tx import TX

run_id = TX(name='', source='', target='').uuid
adapter_addr = f'_agent_{run_id}'
adapter = NetworkAdapter(addr=adapter_addr)
root = Actor.root()
if not root:
    raise RuntimeError("No Matrix root.")
root.register(adapter)
try:
    # ... body ...
finally:
    root._children.pop(adapter_addr, None)
```

After (one helper, four call sites):
```python
# At module level in mixin.py
def _create_run_adapter():
    """Create a transient NetworkAdapter registered with Matrix root."""
    import uuid
    from n3tx.core.api.network_adapter import NetworkAdapter
    from n3tx.core.actors.actor import Actor
    adapter_addr = f'_agent_{uuid.uuid4()}'
    adapter = NetworkAdapter(addr=adapter_addr)
    root = Actor.root()
    if not root:
        raise RuntimeError("No Matrix root. Initialize a Matrix before running agents.")
    root.register(adapter)
    return adapter, root, adapter_addr

def _cleanup_adapter(root, adapter_addr):
    """Remove a transient adapter from Matrix children."""
    root._children.pop(adapter_addr, None)

# In run():
adapter, root, adapter_addr = _create_run_adapter()
try:
    return await instance.agentic(task=task, ..., adapter=adapter)
finally:
    _cleanup_adapter(root, adapter_addr)
```

**D-02: Config cascade extraction**

Before (`mixin.py:283-312`, duplicated in `run_stream` at `mixin.py:483-496`):
```python
from n3tx.core import config
cls = target if isinstance(target, type) else target.__class__
agent_flag = getattr(cls, '__agent__', False)
model_conf = agent_flag if isinstance(agent_flag, dict) else {}
defaults = config.AGENT_DEFAULTS
prompt = kwargs.get('prompt') or target.ctx()
tools = kwargs.get('tools') or target.tools()
llm = (kwargs.get('llm') or model_conf.get('llm')
       or getattr(target, 'llm', None) or defaults.get('llm', 'ollama:llama3.1'))
constraints = dict(defaults.get('constraints', {}))
constraints.update(model_conf.get('constraints', {}))
constraints.update(kwargs.get('constraints', {}))
user = kwargs.get('user')
message_history = kwargs.get('message_history')
result_type = kwargs.get('result_type') or model_conf.get('result_type')
```

After:
```python
def _resolve_config(target, kwargs: dict) -> dict:
    """Resolve the 3-tier config cascade for agent runs.

    Returns dict with keys: prompt, tools, llm, constraints,
    user, message_history, result_type.
    """
    from n3tx.core import config
    cls = target if isinstance(target, type) else target.__class__
    agent_flag = getattr(cls, '__agent__', False)
    model_conf = agent_flag if isinstance(agent_flag, dict) else {}
    defaults = config.AGENT_DEFAULTS

    constraints = dict(defaults.get('constraints', {}))
    constraints.update(model_conf.get('constraints', {}))
    constraints.update(kwargs.get('constraints', {}))

    return {
        'prompt': kwargs.get('prompt') or target.ctx(),
        'tools': kwargs.get('tools') or target.tools(),
        'llm': (kwargs.get('llm') or model_conf.get('llm')
                or getattr(target, 'llm', None)
                or defaults.get('llm', 'ollama:llama3.1')),
        'constraints': constraints,
        'user': kwargs.get('user'),
        'message_history': kwargs.get('message_history'),
        'result_type': kwargs.get('result_type') or model_conf.get('result_type'),
    }

# In run():
conf = _resolve_config(target, kwargs)
adapter, root, adapter_addr = _create_run_adapter()
try:
    instance = target() if isinstance(target, type) else target
    return await instance.agentic(task=task, adapter=adapter, **conf)
finally:
    _cleanup_adapter(root, adapter_addr)
```

**Risk assessment for each proposed change:**

| Change | Files Touched | Tests Affected | Risk Level |
|--------|--------------|----------------|------------|
| D-07: TX UUID | `mixin.py` (4 lines) | None | Trivial |
| D-03: Default LLM | `mixin.py` (2 lines) | Existing tests pass | Low |
| D-01: Adapter helper | `mixin.py` (new helper + 4 call sites) | `test_mixin.py` adapter tests | Low-Medium |
| D-02: Config helper | `mixin.py` (new helper + 2 call sites) | `test_mixin.py` config tests | Low |
| D-05: `Actor.unregister()` | `actor.py`, `mixin.py` | `test_actor_system.py`, `test_mixin.py` | Medium |
| D-04: `neighbor_depth` | `config.py`, `schema_ext.py`, possibly `mixin.py` | `test_mixin.py`, `test_schema_ext.py` | Medium |
| D-06: Dynamic method list | `schema_ext.py` | `test_agent_actor.py` (schema test) | Low |

---

## Contracts and Invariants

### Preconditions

| API | Precondition | Validated? | File:Line |
|-----|-------------|------------|-----------|
| `run()` / `agentic()` | Matrix root must exist | Yes | `mixin.py:322-325` |
| `run()` / `agentic()` | `task` must be a string | No (trusted) | `mixin.py:268` |
| `discover_tools()` | `root` must have `_children` dict | No | `tools.py:61` |
| `discover_tools()` | Child actors must have `schema()` method | Yes (skips) | `tools.py:76-78` |
| `_route_tool_call()` | `ctx.deps.adapter` must be registered | Implicitly | `tools.py:207` |
| `AgentActor.run()` | Instance must have valid `self.prompt` | No | `actor.py:121` |

### Postconditions

| API | Postcondition | Guaranteed? | File:Line |
|-----|--------------|-------------|-----------|
| `run()` | Transient adapter removed from Matrix | Yes (finally) | `mixin.py:347-348` |
| `run()` | Returns dict with `answer, usage, messages, message_count` | Yes | `mixin.py:455-464` |
| `agentic_stream()` | Final chunk has `name='done'` or `name='error'` | Yes | `mixin.py:627-642, 644-649` |
| `ctx()` | Returns non-empty string | Yes (at minimum schema text) | `mixin.py:218` |
| `tools()` | Returns deduplicated list | Yes (dict.fromkeys) | `mixin.py:265` |

### Invariants

1. **Adapter isolation:** Every `run()` call gets its own UUID-addressed adapter. Concurrent runs never share adapters. (Verified: `TestConcurrentRuns`)
2. **Self-exclusion:** An agent never discovers itself as a tool. (`tools.py:64-66`)
3. **Auth propagation:** User context flows from `run(user={...})` through `AgentDeps.user` into `TX.meta['user']` on every tool call. (Verified: `TestUserAuthPropagation`)
4. **AgentActor meta-exclusion:** `run` and `stream_run` methods are auto-excluded from tool discovery. (`tools.py:94-96`)

---

## Error Propagation Paths

### Tool call failure
```
_route_tool_call() -> response.is_error ->
    ModelRetry(response.data['message']) -> Pydantic AI retries with error context
```
Good design: tool failures become LLM-visible retries, not hard crashes. File: `tools.py:217-219`.

### No Matrix root
```
run() / agentic() -> Actor.root() is None ->
    RuntimeError("No Matrix root. Initialize a Matrix before running agents.")
```
Not caught -- propagates to caller. Correct behavior for a configuration error. File: `mixin.py:322-325`.

### Missing actor in tool discovery
```
discover_tools() -> children.get(addr) is None ->
    logger.warning() -> continue (skip this actor)
```
If ALL actors missing: `agentic()` logs warning at `mixin.py:413-416` but proceeds (agent runs without tools). File: `tools.py:69-72`.

### Streaming exception
```
agentic_stream() -> except Exception ->
    yield {'name': 'error', 'data': {'message': str(e)}} -> cleanup adapter
```
Streaming errors are yielded as error chunks, not raised. Non-streaming `agentic()` does NOT catch exceptions -- they propagate. This asymmetry is intentional (see T-04). File: `mixin.py:644-649`.

### model_dump failure in context building
```
_build_instance_text() -> model_dump() raises ->
    except Exception: return '' (silently)
```
LLM gets schema context but no instance data. Silent swallowing could mask bugs. File: `mixin.py:163-166`.

---

## Appendix: Complete Finding Index

| ID | Dimension | Severity | Finding | File(s) | Status |
|----|-----------|----------|---------|---------|--------|
| F-01 | Quality | High | Test bug: `result["messages"] >= 2` compares list to int | `example_grants/tests/test_agent_run.py:54` | Open |
| F-02 | Arch+Quality | Medium | `neighbor_depth` declared in config/schema but never implemented | `config.py:30`, `schema_ext.py:32`, `mixin.py:252-257` | Open |
| F-03 | Quality | Low | `_build_instance_text()` double-evaluates `str(v)` per iteration | `mixin.py:174` | Open |
| F-04 | Quality | Medium | `agentic_stream()` error handler may expose internal details | `mixin.py:644-649` | Open |
| F-05 | Arch | Medium | Adapter lifecycle code duplicated 4x (~60 lines) | `mixin.py:315-348,392-468,498-532,559-652` | Open |
| F-06 | Arch | Medium | Config cascade duplicated between `run()` and `run_stream()` | `mixin.py:283-312,483-496` | Open |
| F-07 | Arch | Low | Default LLM `'ollama:llama3.1'` hardcoded in 6 places | `config.py:31`, `mixin.py:302,382,490,552`, `actor.py:59` | Open |
| F-08 | Arch | Low | `run()` kwargs are unvalidated -- typos silently ignored | `mixin.py:293-312` | Open |
| F-09 | Arch | Low | TX created just for UUID (4x) | `mixin.py:319,398,503,566` | Open |
| F-10 | Quality | Low | `_build_instance_text()` silently swallows `model_dump()` errors | `mixin.py:163-166` | Open |
| F-11 | Arch | Low | `_route_tool_call` assumes `response.data` is dict | `tools.py:219` | Open (low risk: `TX.error()` always produces dict) |
| F-12 | Quality | Low | `schema_ext.py:41` hardcodes agent method list | `schema_ext.py:41` | Open |
| F-13 | Quality | Low | `run_stream()` adapter cleanup depends on `aclose()` or GC | `mixin.py:513-532` | Open |
| F-14 | Quality | Low | No structured logging for tool discovery or tool calls | `tools.py`, `mixin.py` | Open |
| F-15 | Arch | Low | `AgentActor.run()` returns `str` vs mixin's `dict` (documented) | `actor.py:129` vs `mixin.py:268` | Accepted |
| F-16 | Arch | Low | Schema extension registration depends on `__init__.py` side-effect import | `__init__.py:21` | Open |
| F-17 | Quality | Low | `tools()` return type annotated as `list` not `list[str]` | `mixin.py:232` | Open |
| F-18 | Quality | Low | No tests for streaming + tool-calling interaction | `agents/tests/test_mixin.py` | Open |
| F-19 | Quality | Low | No tests for `result_type` (structured output) | `agents/tests/test_mixin.py` | Open |
| F-20 | Quality | Low | `root._children` accessed as private attribute for cleanup | `mixin.py:348,468,532,652` | Open |
| F-21 | Quality | Info | Prompt injection via tool results is inherent to tool-calling LLMs | `tools.py:220` | Accepted (document) |
| F-22 | Quality | Info | Per-run overhead from uncached tool/agent recreation | `mixin.py:408-428` | Accepted (optimize later) |
| F-23 | Quality | Info | `_resolve_tool_addrs()` batch fetch verified working (SQLite `list(ids=)` supported) | `actor.py:95-99`, `sqlite_storage.py:161-163` | Verified OK |

### Cross-Reference Notes

**Contradiction resolved: `_resolve_tool_addrs()` batch fetch (F-23).** Report 02 (Section 2.3) flagged `tool_cls.list(ids=href_ids)` as potentially unsupported. Direct verification of `sqlite_storage.py:161-163` and `abstract_storage.py:21-23` confirms `ids` is a supported parameter in both the abstract interface and the SQLite implementation. The `ids` filter is implemented at `sqlite_storage.py:172-180` with proper `WHERE id IN (?, ?, ...)` clause. This finding is closed as verified OK.

**Contradiction resolved: `_route_tool_call` error format (F-11).** Report 02 (Section 5.3) flagged that `response.data.get('message', ...)` would raise `AttributeError` if `response.data` is not a dict. Direct verification of `tx.py:37-45` confirms `TX.error()` always creates `data={'message': message, 'code': code}`. All 50+ call sites of `tx.error()` in the codebase use the `tx.error(message_string, code=int)` signature, which always produces a dict. The risk is theoretical -- it would require a custom actor handler to construct an error TX with non-dict data outside the `TX.error()` method. Severity downgraded from Medium to Low.

**Consolidated: adapter lifecycle duplication (F-05) and config cascade duplication (F-06).** Both reports flagged these independently. The architecture report identified the adapter lifecycle as duplicated in 4 places; the quality report identified the config cascade as duplicated in 2 places. These are related but distinct issues: the adapter lifecycle is a structural concern (create/register/use/cleanup pattern), while the config cascade is a data concern (3-tier resolution). Both should be extracted, but independently -- they serve different purposes and have different signatures. The refactoring sequence in the "For Refactoring" section addresses both.

**Confirmed: `neighbor_depth` dead config (F-02).** Both reports flagged this finding. The architecture report at Section 14 (Issue 2) and the quality report at Section 10.2 both identify the same root cause: `config.py:30` declares the key, `schema_ext.py:32` exposes it, but `mixin.py:252-257` never reads it. No contradiction between reports.
