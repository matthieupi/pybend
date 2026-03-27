# Agents Subsystem: Quality & Risk Assessment

**Audit date**: 2026-03-26
**Scope**: `packages/n3tx-agents/` — all Python backend, JS frontend, and test files
**Auditor**: Claude Opus 4.6

---

## 1. Potential Bugs

### 1.1 `agentic_stream()` creates empty instance for class-level calls

**File**: `mixin.py:444-447`
```python
if isinstance(target, type):
    instance = target()
else:
    instance = target
```

When `Product.agentic_stream(task='...')` is called at the class level, this creates a default instance with no meaningful field values and no actor address. The newly created `instance` has `_addr = ''` (empty string) because no `addr=` kwarg is passed to the constructor. This empty-address instance is then used to call `instance.run_stream()`, which reads `getattr(target, '_addr', '')` at line 493 and passes it as `agent_addr`.

**Scenario**: Any class-level `agentic_stream()` call creates a throwaway instance. If the model has required fields without defaults (e.g., `name: str = Field(min_length=1)`), this will raise a Pydantic validation error.

**Likelihood**: Medium. The test suite only tests `AgenticProduct.agentic_stream()` where all fields have defaults. Any model with a required field would fail.

**Contrast**: `agentic()` (non-streaming) at line 220 calls `target.run()` directly on the class, which works because `run()` is also a `@fullmethod`. The streaming path gratuitously forces instance creation.

### 1.2 `_build_instance_text()` truncation logic is inconsistent

**File**: `mixin.py:122-129`
```python
truncated = {}
for k, v in data.items():
    s = str(v)
    if len(s) > 200:
        s = s[:200] + '...'
    truncated[k] = v if len(str(v)) <= 200 else s
```

The code calls `str(v)` three times per field: once to get `s`, once in the `if` check, and once in the ternary. This is wasteful but also subtly wrong: `truncated[k] = v` preserves the original value (which may not be JSON-serializable), while the `else` branch stores the truncated string. The subsequent `json.dumps(truncated, indent=2, default=str)` at line 132 may produce different representations depending on which branch was taken for the same value. The inline comment at line 123 acknowledges this needs review.

**Likelihood**: Low functional impact but adds noise to LLM context.

### 1.3 `_resolve_tool_addrs()` batch fetch uses wrong model class

**File**: `actor.py:128-132`
```python
if href_ids:
    tools = tool_cls.list(ids=href_ids)
    records = tools['data'] if isinstance(tools, dict) else tools
    for tool in records:
        tool_addrs.append(tool.target)
```

The `tool_cls.list(ids=href_ids)` call passes an `ids` parameter to `list()`. However, `StorableMixin.list()` (the standard list method) accepts `limit`, `offset`, and potentially filter kwargs -- but not `ids` as a batch-fetch parameter. This would silently fall back to listing all records, ignoring the `ids` filter entirely, returning more tool addresses than expected.

**Likelihood**: High when agents have tools stored as hrefs. The test `test_from_hrefs` at `test_agent_actor.py:147-162` only creates one tool, masking this issue.

### 1.4 `_llm_clean()` mutates properties dict from original schema

**File**: `schema_ext.py:82-87`
```python
if 'properties' in cleaned:
    original_props = schema.get('properties', {})
    for name in list(cleaned['properties']):
        prop_ui = original_props.get(name, {}).get('ui', {})
        if prop_ui.get('display') is False or prop_ui.get('protected'):
            del cleaned['properties'][name]
```

The `_strip()` function at line 70 creates new dicts via comprehension, so `cleaned['properties']` is a new dict. However, the values within each property dict are shared references with the original schema. Deleting keys from `cleaned['properties']` is safe, but if any downstream code mutated the property values, it would affect the cached schema. This is not currently exploited but is a latent risk.

**Likelihood**: Low. The function's current use is read-only after cleaning.

### 1.5 `ntx-chat.js` TOOL_RESULT uses `innerHTML +=` which re-parses DOM

**File**: `ntx-chat.js:135`
```javascript
card.innerHTML += `<div class="tool-result">${this.#esc(summary)}</div>`;
```

Using `innerHTML +=` causes the browser to serialize the existing DOM to HTML, concatenate the new string, and re-parse the entire thing. This destroys event listeners and can corrupt DOM state on the existing card content. The other components (`ntx-stream-agent.js`, `ntx-agent-live.js`) correctly use `appendChild()` instead.

**Likelihood**: Medium. Triggers every time a tool result arrives in the chat widget. Visible symptoms: tool header spinners may freeze or disappear incorrectly.

### 1.6 `Thread.messages` mutable default

**File**: `thread.py:52`
```python
messages: list = Field(default=[], description='Conversation history (TX-shaped dicts)')
```

Similarly in `actor.py:48,64,91,93`:
```python
args: dict = Field(default={})
usage: dict = Field(default={})
tools: ListRef[AgentTool] = Field(default=[])
constraints: dict = Field(default={})
```

In Pydantic V2, `Field(default=[])` and `Field(default={})` use mutable defaults. Pydantic V2 handles this safely by deep-copying defaults during model instantiation, so this is not a runtime bug. However, it violates Python best practices and could cause confusion. The idiomatic pattern is `Field(default_factory=list)` or `Field(default_factory=dict)`.

**Likelihood**: None (Pydantic V2 protects against this). Flagged as a code quality concern only.

---

## 2. Edge Cases

### 2.1 Empty tool list produces warning but continues execution

**File**: `mixin.py:346-348`
```python
if not tool_specs:
    logger.warning(
        "[%s] No tools discovered from addresses: %s", agent_addr, tools
    )
```

When `discover_tools()` returns zero specs (e.g., all addresses are missing from Matrix), the agent runs with no tools. The LLM receives a system prompt referencing capabilities it cannot exercise. This is correct behavior for the "zero to working" philosophy, but the warning could be more actionable.

### 2.2 Very large `model_dump()` in `_build_instance_text()`

If a model instance has a field containing megabytes of data (e.g., a `dict` field with a large JSON blob), `model_dump()` at line 118 will serialize the entire thing into memory. The truncation at line 127 only truncates string representations of individual fields, not the overall size. With many fields or deeply nested data, the context string could be enormous.

**Scenario**: An AgentActor with a large `constraints` dict or a Thread with thousands of messages.

### 2.3 `agentic_stream()` error chunk does not include `stream_end`

**File**: `mixin.py:687-691`
```python
yield {
    'name': 'error',
    'data': {'message': str(e), 'code': 500},
    'meta': {'stream': True, 'error': True, 'seq': seq},
}
```

The error chunk has `error: True` but not `stream_end: True`. The frontend `NTTStream` base class may not recognize this as a terminal event, potentially leaving the stream in a "running" state. The `STREAM_ERROR` handler in `ntx-agent-live.js:179-186` does re-enable the run button, but only because the SSE connection closes naturally on error.

### 2.4 Thread with non-existent agent_addr

A Thread can be created with any `agent_addr` string, including one that does not correspond to any registered actor. Thread CRUD does not validate that the agent exists. When `run()` later tries to use the thread, the agent_addr is only used in `Thread.from_history()` metadata -- not for routing -- so this is cosmetic, not a crash bug.

### 2.5 Concurrent thread updates can lose messages

**File**: `mixin.py:388-407` (and duplicate at lines 642-661)

The thread update pattern is read-then-write:
1. `run()` reads thread messages (line 328-341)
2. LLM runs (potentially for seconds/minutes)
3. `run()` writes back all_messages (line 388-407)

If two concurrent `run()` calls use the same `thread_id`, the second writer overwrites the first writer's messages. There is no optimistic locking, version check, or append-only semantics.

**Likelihood**: Low in current usage (threads are per-user, single-request), but becomes a real problem if thread sharing or background agents are introduced.

---

## 3. Test Coverage Analysis

### 3.1 What IS tested (good coverage)

| Area | Coverage | Key Tests |
|------|----------|-----------|
| Mixin injection | Strong | `test_mixin.py::TestMixinInjection` — 5 tests |
| `ctx()` class vs instance | Strong | `test_mixin.py::TestCtx` — 6 tests |
| `tools()` discovery config | Strong | `test_mixin.py::TestTools` — 7 tests |
| `run()` engine basics | Good | `test_mixin.py::TestRunEngine` — 3 tests |
| `agentic()` config cascade | Good | `test_mixin.py::TestAgentic` — 5 tests |
| Tool discovery (CRUD + methods) | Strong | `test_tools.py::TestToolDiscovery` — 6 tests |
| Tool function generation | Strong | `test_tools.py::TestToolFunctionGeneration` — 5 tests |
| Self-exclusion / loop detect | Good | `test_tools.py::TestLoopDetection` — 4 tests |
| Thread CRUD | Good | `test_thread.py::TestThreadCRUD` — 4 tests |
| Thread round-trip conversion | Strong | `test_thread.py::TestConversionUtilities` — 5 tests |
| Thread integration with run() | Good | `test_thread.py::TestRunWithThread` — 4 tests |
| AgentActor CRUD | Good | `test_agent_actor.py::TestAgentActorCRUD` — 4 tests |
| First-token streaming bug | Excellent | `test_run_stream_first_token.py` — 3 targeted tests |
| Tool call auth bypass | Good | `test_tool_call_auth.py` — 4 tests |
| Stream event types | Good | `test_mixin.py::TestRunStreamTypedEvents` — 6 tests |
| Concurrent isolation | Basic | `test_mixin.py::TestConcurrentRuns` — 1 test |

### 3.2 What is NOT tested (coverage gaps)

| Gap | Risk Level | Notes |
|-----|-----------|-------|
| **`_resolve_llm()` with various provider strings** | Medium | Only ollama prefix tested indirectly. No tests for anthropic, openai, groq, google strings or model instances passed through. |
| **`_resolve_llm()` with falsy but non-None values** | Low | Empty string `''` raises ValueError, but `0`, `False` are not tested. |
| **`result_type` (structured output)** | High | Neither `run()` nor `agentic()` tests pass `result_type`. The code path at `mixin.py:357-358` that sets `output_type` is completely untested. |
| **`AgentActor._resolve_tool_addrs()` batch fetch** | High | `test_from_hrefs` uses a single href. The batch path (multiple hrefs) is untested, and as noted in bug 1.3, likely broken. |
| **`agentic_stream()` with thread_id** | Medium | `test_thread.py::TestRunStreamWithThread` tests `run_stream()` with thread_id, but `agentic_stream()` thread pass-through is not tested. |
| **`agentic_stream()` class-level call with required fields** | Medium | See bug 1.1. Only tested with models that have all defaults. |
| **`constraints` max_iterations enforcement** | Medium | Tests pass constraints but never verify that `UsageLimits` actually limits the LLM. |
| **Schema extension `_llm_clean()` pipeline** | Medium | The LLM pipeline registered at `schema_ext.py:100-101` is never tested directly. |
| **`AgentActor.agentic()` return value serialization** | Low | `agentic()` returns `json.dumps(result, default=str)`. The `default=str` serializer is not tested with non-serializable types in the result. |
| **Frontend components** | Zero | No JS tests exist for `ntx-stream-agent.js`, `ntx-agent-live.js`, `ntx-chat.js`, or `ntx-agent.js`. |
| **Error recovery in streaming** | Low | `test_error_chunk_on_failure` checks error emission, but not that the frontend correctly handles error-then-close sequences. |
| **Thread access control enforcement** | Medium | Thread has OWNER-based access, but no test verifies that user A cannot read user B's thread. |
| **ToolCallPartDelta handling in `run_stream()`** | Low | The streaming loop handles `ToolCallPartDelta` implicitly via `PartDeltaEvent` but never emits a chunk for it. This is fine (args arrive in PartStartEvent), but there is no test confirming delta args are ignored safely. |

### 3.3 Integration test gaps

The `examples/grants/tests/` provide good HTTP-level integration tests for `agentic()`, but:
- **No streaming HTTP test**: No test sends `POST /agents/{id}/agentic_stream` and validates the SSE event stream.
- **No multi-turn chat test**: The chat widget test (`test_chat_widget_response.py`) only tests response extraction, not a multi-turn conversation.
- **No concurrent HTTP test**: No test sends multiple simultaneous requests to the same agent.

---

## 4. Test Quality Assessment

### 4.1 Strengths

- **Fixture isolation is excellent**: The `conftest.py` `reset_actor_state` fixture properly saves/restores global state (Matrix, children, registered_models). This prevents test pollution.
- **Real Matrix routing**: Tests use actual Matrix instances and TX routing rather than mocking. This gives high confidence that the integration actually works.
- **TestModel usage**: Pydantic AI's `TestModel` is used consistently, avoiding real LLM calls while exercising the full agent pipeline.
- **Bug-driven tests**: `test_run_stream_first_token.py` and `test_tool_call_auth.py` follow the TDD bug-fix pattern with clear reproduction scenarios.

### 4.2 Weaknesses

- **Assertion gaps in concurrent test**: `test_concurrent_runs_isolated` at `test_mixin.py:418-433` runs 3 concurrent tasks but only checks that results have `answer` and `usage` keys. It does not verify isolation (e.g., that task text does not leak between results).

- **Over-reliance on `'answer' in result`**: Many tests only assert that the result dict has an `answer` key, without checking the value's type or that it is non-empty. Example: `test_mixin.py:283` just checks `assert 'answer' in result`.

- **Module-level model definitions leak across tests**: Models like `AgenticProduct`, `Comment`, `ToolTarget` are defined at module level in `test_mixin.py`. Because `ActorModel` auto-registers in `Actor.__children__` at class creation time, these registrations persist across test modules if the `reset_actor_state` fixture doesn't run for a given test. The fixture does clean up, but the ordering dependency is fragile.

- **`memory_storage` fixture uses `:memory:` SQLite**: The conftest provides `SQLiteStorage(':memory:')`, but as noted in project memory, `:memory:` connections create separate databases. This fixture works for tests that don't need cross-connection persistence, but could confuse developers who add tests expecting shared state.

- **Missing negative tests for `make_tool()`**: No test verifies what happens when `make_tool()` receives a spec with no properties, or with conflicting parameter names like `ctx` (which would shadow the RunContext parameter).

---

## 5. Error Handling Gaps

### 5.1 `_build_instance_text()` swallows all exceptions

**File**: `mixin.py:117-119`
```python
try:
    data = target.model_dump()
except Exception:
    return ''
```

Any error during `model_dump()` — including programming errors like wrong field types or missing validators — is silently swallowed. The LLM gets no instance context, with no indication of why.

### 5.2 `run_stream()` error handler catches too broadly

**File**: `mixin.py:685-691`
```python
except Exception as e:
    yield {
        'name': 'error',
        'data': {'message': str(e), 'code': 500},
        'meta': {'stream': True, 'error': True, 'seq': seq},
    }
```

This catches `KeyboardInterrupt`-derived exceptions (via `Exception` base), `SystemExit`-adjacent errors, and any programming bugs in the streaming loop. The error message is `str(e)` which may leak internal details (stack traces, file paths, database errors) to the frontend.

### 5.3 Thread update failure is only logged, not propagated

**File**: `mixin.py:401-407`
```python
if update_resp.is_error:
    logger.warning(
        "Failed to update thread %s: %s",
        thread_id,
        update_resp.data.get('message', 'unknown'),
    )
```

If the thread update fails (e.g., DB write error, permission denied), the agent's result is still returned successfully. The user believes their conversation was saved, but it was not. The same pattern appears in `run_stream()` at lines 655-661.

### 5.4 `_route_tool_call()` error response access

**File**: `tools.py:219-221`
```python
if response.is_error:
    from pydantic_ai import ModelRetry
    raise ModelRetry(response.data.get('message', 'Tool call failed'))
```

If `response.data` is not a dict (e.g., it is a string error message or None), the `.get('message', ...)` call will raise `AttributeError`. The code assumes error TXs always have `data` as a dict with a `message` key.

**Likelihood**: Low if all error TXs follow the convention, but there is no type enforcement on TX.data.

### 5.5 No timeout on tool calls

**File**: `tools.py:218`
```python
response = await root.request(tx)
```

Tool calls route through Matrix with no timeout. If a target actor hangs (e.g., network call in an `@expose_route` method), the entire agent loop blocks indefinitely. The pydantic-ai `UsageLimits.request_limit` only limits LLM requests, not individual tool call durations.

---

## 6. Security Considerations

### 6.1 `exec()` in tool function generation

**File**: `tools.py:293`
```python
exec(code, ns)  # noqa: S102
```

The `exec()` call generates async functions from `ToolSpec` data. The inputs come from model schemas (`cls.schema()`), which are generated by the framework from Python class definitions. The comment at line 7-9 correctly notes this is the same pattern as `dataclasses`. The namespace is isolated (`ns` dict with only `_route`, `_target`, `_method`, `_required`).

**Risk**: Low. The input is not user-controlled. An attacker would need to inject a malicious model schema, which requires code-level access to the backend.

However, the `desc` variable at line 276 (used in the docstring) escapes backslashes and triple-quotes but does not handle all injection vectors:
```python
desc = (spec.description or spec.tool_name).replace('\\', '\\\\').replace('"""', "'''")
```
If a description contained `"""\nimport os; os.system('rm -rf /');\n"""`, the replacement would convert it to `'''\nimport os...`. This is safe because the string is inside a docstring, not executable code. But a description containing a single `\n` followed by valid Python could potentially break the docstring boundary. In practice, descriptions come from `@expose_route` method docstrings or hardcoded CRUD descriptions, both framework-controlled.

### 6.2 XSS via `marked.parse()` on LLM output

**Files**: `ntx-stream-agent.js:214`, `ntx-agent-live.js:268`
```javascript
content.innerHTML = marked.parse(buf);
```

LLM output is passed through `marked.parse()` (Markdown to HTML) and injected via `innerHTML`. If the LLM generates markdown containing malicious HTML (e.g., `<img onerror="...">`), it will be rendered. The `marked` library has built-in sanitization options (`marked.setOptions({sanitize: true})`), but there is no evidence this is configured.

**Risk**: Medium. An LLM can be manipulated via prompt injection to output arbitrary HTML. The Shadow DOM provides some isolation (scripts in shadow roots are inert), but event handlers on elements (`onerror`, `onload`) execute in the main context.

**Mitigation**: The fallback path (`content.textContent = buf`) is safe. Only the `marked` path is vulnerable.

### 6.3 Tool call auth bypass (known, tested, and fixed)

**File**: `test_tool_call_auth.py` documents and tests the scenario where `_route_tool_call` sends TX with `meta={'user': None}`, which the handler interprets as an internal (trusted) call. This is the intended design: agent tool calls are internal TX messages, not external HTTP requests. The test at line 42-63 confirms this works.

**Residual risk**: Any actor that distinguishes between "no user" and "internal system call" based solely on `meta.user is None` could be tricked by an agent call into performing privileged operations. The two-tier auth model (Tier 1 at protocol boundary, Tier 2 in handler) mitigates this because internal TX messages bypass Tier 1.

### 6.4 LLM credential exposure in schema

**File**: `schema_ext.py:34-37`
```python
if isinstance(agent_flag, dict):
    safe_keys = {'self_tools', 'neighbors', 'neighbor_depth'}
    agent_meta['config'] = {k: v for k, v in agent_flag.items() if k in safe_keys}
```

The schema extension correctly filters to safe keys, excluding `llm`, `prompt`, and `tools` from the public schema. However, `AgentActor` stores `llm` as a regular field, and the schema's `properties` section includes it. An unauthenticated `GET /AgentActor` reveals the LLM provider and model name (e.g., `ollama:llama3.1`). This is informational disclosure, not credential leakage, since the provider string does not contain API keys.

### 6.5 No input validation on `task` parameter

**File**: `mixin.py:220`, `actor.py:137`

The `task` parameter is passed directly to the LLM as a user message. There is no sanitization, length limit, or content filtering. While the LLM itself handles arbitrary input, an extremely large `task` string could cause excessive token consumption or timeout.

---

## 7. Performance Risks

### 7.1 Tool discovery is synchronous and uncached

**File**: `tools.py:43-101`

`discover_tools()` is called on every `run()` and `run_stream()` invocation. It:
1. Iterates all actor addresses
2. Calls `cls.schema()` for each (cached, but still a dict lookup + deep copy)
3. Generates `ToolSpec` objects
4. Calls `create_tool_function()` with `exec()` for each spec

For an agent with 5 tool addresses and 5 CRUD ops + 3 methods each, this generates ~40 tool functions per invocation. The `exec()` calls are not cached.

**Impact**: Microseconds per call in practice (schema is cached, exec is fast). Not a bottleneck yet, but becomes relevant at high concurrency.

### 7.2 `Thread.to_history()` deserializes all messages every run

**File**: `thread.py:71-72`
```python
raw = [msg['data'] for msg in tx_messages]
return list(ModelMessagesTypeAdapter.validate_python(raw))
```

For a long conversation (hundreds of turns), this validates every historical message through Pydantic's type adapter on every agent invocation. The messages were already validated when stored, so this is redundant validation.

### 7.3 Thread stores full conversation, not deltas

**File**: `mixin.py:393-396`
```python
'messages': Thread.from_history(
    all_messages,
    source=root.addr,
    target=agent_addr,
),
```

After each run, the entire conversation history (including all prior messages) is serialized and written back to the thread. For a 100-turn conversation, this writes ~100 messages each time. An append-only pattern would be more efficient: store only the new messages from this turn.

### 7.4 No pagination in `_resolve_tool_addrs()` batch fetch

**File**: `actor.py:129`
```python
tools = tool_cls.list(ids=href_ids)
```

If an agent has hundreds of tools (unlikely but possible), this fetches all of them in a single query. There is no limit or pagination. Combined with bug 1.3 (the `ids` parameter likely being ignored), this could return the entire `agent_tools` table.

### 7.5 Markdown rendering blocks the main thread

**Files**: `ntx-stream-agent.js:213-214`, `ntx-agent-live.js:267-268`

`marked.parse(buf)` is called synchronously on the main thread. For very long LLM outputs (thousands of words with complex markdown), this could cause UI jank. The 300ms debounce timer helps, but the final `#flushRender()` call processes the entire buffer at once.

---

## 8. Concurrency Issues

### 8.1 Global `Actor.__matrix__` singleton

**File**: `mixin.py:319`
```python
root = Actor.root()
```

All agent operations depend on `Actor.root()` returning the global Matrix singleton. This is safe for single-process deployment but means:
- All concurrent agent runs share the same Matrix instance
- Matrix message routing is the serialization point for all tool calls
- If Matrix state is corrupted, all agents fail simultaneously

### 8.2 `run_stream()` seq counter is per-invocation (safe)

**File**: `mixin.py:505`
```python
seq = 0
```

The sequence counter is a local variable, so concurrent streams have independent counters. This is correct.

### 8.3 Frontend timer conflicts on rapid re-invocation

**File**: `ntx-stream-agent.js:126-131`
```javascript
callMethod() {
    this.#toolCards.clear();
    this.#textBuf = ''; this.#textRendered = 0; clearTimeout(this.#textTimer);
    this.#thinkBuf = ''; this.#thinkRendered = 0; clearTimeout(this.#thinkTimer);
    this.#outputEl = null;
    super.callMethod();
}
```

`callMethod()` clears state before starting a new stream, but if the previous stream is still delivering events (SSE events are async), the old stream's handlers will write into the newly cleared state. The `super.callMethod()` should abort the previous EventSource first. Whether it does depends on `NTTStream.callMethod()` implementation (outside audit scope).

### 8.4 Thread read-write race condition

As described in edge case 2.5, the read-modify-write pattern on Thread is not atomic. Two concurrent `run()` calls with the same `thread_id` will race.

---

## 9. Resource Management

### 9.1 Pydantic AI Agent instances are not reused

**File**: `mixin.py:352-360`
```python
ai_agent = Agent(llm, **agent_kwargs)
```

A new `Agent` instance is created for every `run()` and `run_stream()` call. Pydantic AI Agents are lightweight (no connection pooling or persistent state), so this is acceptable. However, if the LLM provider requires connection setup (e.g., HTTP session initialization), this adds latency.

### 9.2 `agent.iter()` context manager properly cleans up

**File**: `mixin.py:559`
```python
async with ai_agent.iter(task, **run_kwargs) as agent_run:
```

The `async with` ensures the agent run is properly cleaned up even if the generator is abandoned. This is correct.

### 9.3 No explicit cleanup of abandoned generators

If the caller of `agentic_stream()` or `run_stream()` abandons the async generator mid-stream (e.g., client disconnects), Python's garbage collector will eventually call `aclose()`, which triggers the `finally` block. However, there is no `finally` block in the generator -- the `except Exception` at line 685 only catches exceptions, not generator cleanup via `GeneratorExit`. The `async with ai_agent.iter(...)` context manager will handle LLM cleanup, but any thread update logic at lines 642-661 will not execute.

**Impact**: If a client disconnects mid-stream during a threaded conversation, the thread will not be updated with partial results.

---

## 10. Technical Debt Inventory

### 10.1 Acknowledged debt

| Location | Note | Impact |
|----------|------|--------|
| `mixin.py:123` | `# We will need to review the trucation to make sure we are not removing relevant context.` | Truncation logic is functional but unreviewed. |

### 10.2 Code duplication

**Major duplication between `run()` and `run_stream()`**: Lines 268-421 (`run()`) and 461-691 (`run_stream()`) share approximately 80% identical code:
- LLM resolution (lines 300-309 vs 483-490)
- Matrix root check (lines 319-323 vs 498-503)
- Thread pre-read (lines 327-341 vs 508-522)
- Tool discovery (lines 344-349 vs 525-526)
- Agent construction (lines 352-366 vs 528-540)
- Deps creation (lines 369-372 vs 538-541)
- Usage limits (lines 375-378 vs 543-547)
- Thread post-write (lines 388-407 vs 642-661)

Extracting the shared setup into a private method would reduce ~100 lines of duplication.

**Duplication between `agentic()` and `agentic_stream()`**: Lines 220-265 and 424-459 have identical config cascade logic (prompt resolution, tool resolution, constraint merging).

**Frontend component duplication**: `ntx-stream-agent.js` and `ntx-agent-live.js` share nearly identical implementations of:
- `THINKING()`, `TOOL_CALL()`, `TOOL_RESULT()`, `TEXT()`, `DONE()` handlers
- `#scheduleRender()`, `#renderMd()`, `#flushRender()`, `#scrollToBottom()`
- `#addEntry()`, `#setThinking()`, `#esc()`
- Agent-specific CSS styles

The `NTTStreamAgent` is meant to be the reusable base, but `NTTAgentLive` does not extend it -- both extend `NTTStream` independently. This means bug fixes in one must be manually applied to the other.

### 10.3 Implicit dependencies

- `_resolve_llm()` at `mixin.py:96` reads `config.OLLAMA_BASE_URL` which must be defined in `n3tx_core.config`. If missing, it will raise `AttributeError`.
- The `import n3tx_agents` ordering requirement (noted in CLAUDE.md) is a footgun: if any model with `__agent__ = True` is defined before `n3tx_agents` is imported, the mixin is silently not injected.

### 10.4 Dead code / unused patterns

- `_JSON_TYPE_MAP` in `tools.py:21-28` maps `'object': 'dict'` and `'array': 'list'`, but generated tool functions with `dict` or `list` parameters will receive those types from Pydantic AI's JSON deserialization, not from the Python type hints. The type hints are cosmetic for these cases.

---

## 11. Failure Modes

### 11.1 LLM provider unavailable

If the Ollama server or cloud LLM API is down, `ai_agent.run()` raises an exception. In `run()`, this propagates as an unhandled exception to the caller (likely a 500 HTTP response). In `run_stream()`, it is caught by the broad `except Exception` and yielded as an error chunk. The frontend displays the error.

**Blast radius**: Single request fails. Other agents are unaffected.

### 11.2 Matrix unavailable

If `Actor.root()` returns `None`, both `run()` and `run_stream()` raise `RuntimeError("No Matrix root")`. This is a hard failure -- no agents can function.

**Blast radius**: All agent functionality is disabled. Recoverable by restarting the Matrix.

### 11.3 Storage unavailable

If SQLite is unreachable during a thread read/write:
- Thread read failure raises `RuntimeError` (lines 334-337)
- Thread write failure is logged but not propagated (lines 401-407)
- AgentActor CRUD failures propagate as storage exceptions

**Blast radius**: Thread-dependent operations fail; non-threaded agent calls are unaffected.

### 11.4 Tool actor crashes

If a tool actor raises an unhandled exception, Matrix returns an error TX. `_route_tool_call()` converts this to `ModelRetry`, which tells the LLM the tool failed and to try a different approach. This is graceful degradation.

**Blast radius**: Single tool unavailable; LLM may retry or work around it.

### 11.5 Cascading failure: Agent calls Agent

An AgentActor can have another AgentActor's address in its tools list. If Agent A calls Agent B which calls Agent A, the loop detection (`caller_addr` exclusion in `discover_tools`) only prevents an agent from discovering itself as a tool -- it does not prevent A -> B -> A recursive invocations. The `max_iterations` constraint limits LLM requests but not the depth of inter-agent calls.

**Blast radius**: Stack overflow or timeout. No built-in circuit breaker.

---

## 12. Summary: Top 10 Risks by Priority

| # | Risk | Severity | Likelihood | Location |
|---|------|----------|-----------|----------|
| 1 | `_resolve_tool_addrs()` batch fetch likely broken (bug 1.3) | High | High | `actor.py:129` |
| 2 | XSS via `marked.parse()` on unsanitized LLM output | High | Medium | `ntx-stream-agent.js:214`, `ntx-agent-live.js:268` |
| 3 | No timeout on tool calls via Matrix | Medium | Medium | `tools.py:218` |
| 4 | Thread update failure silently swallowed | Medium | Medium | `mixin.py:401-407` |
| 5 | `result_type` (structured output) entirely untested | Medium | High | `mixin.py:357-358` |
| 6 | `run()`/`run_stream()` ~100 lines of duplicated setup | Medium (debt) | N/A | `mixin.py:268-691` |
| 7 | `agentic_stream()` class-level creates invalid instance (bug 1.1) | Medium | Medium | `mixin.py:444-445` |
| 8 | `ntx-stream-agent.js` / `ntx-agent-live.js` duplicated handler code | Medium (debt) | N/A | Both files |
| 9 | Agent-to-agent recursive invocation has no depth limit | Medium | Low | N/A |
| 10 | Abandoned stream generator skips thread update | Low | Medium | `mixin.py:642-661` |
