# Agents Subsystem Audit: API Surface & Contracts

> Audit date: 2026-03-26 | Branch: v0.9 | Auditor: Claude Opus 4.6

## 1. Public API Inventory

### 1.1 Python Backend API

#### Module Exports (`__init__.py:29-33`)

| Symbol | Type | Source | Purpose |
|--------|------|--------|---------|
| `AgentMixin` | class | `mixin.py` | Injected into `__agent__ = True` models |
| `AgentActor` | class | `actor.py` | Concrete storable agent model |
| `AgentTool` | class | `tool_model.py` | Tool reference model for AgentActor |
| `AgentDeps` | dataclass | `deps.py` | Pydantic AI RunContext dependency |
| `ToolSpec` | dataclass | `tools.py` | Intermediate tool specification |
| `discover_tools` | function | `tools.py` | Actor-addr-to-ToolSpec discovery |
| `make_tool` | function | `tools.py` | ToolSpec-to-Pydantic-AI-Tool wrapper |
| `Thread` | class | `thread.py` | Per-conversation history model |

Side-effect imports: `register_mixin('__agent__', AgentMixin)` at `__init__.py:18`, `schema_ext` at `__init__.py:27`.

#### AgentMixin Methods (all `@fullmethod`)

| Method | Signature | Returns | Async | Side Effects |
|--------|-----------|---------|-------|-------------|
| `ctx` | `(target) -> str` | LLM context string | No | None |
| `tools` | `(target) -> list[str]` | Actor addresses | No | None |
| `agentic` | `(target, task: str, **kwargs) -> dict` | `{answer, usage, messages, message_count, ?thread_id}` | Yes | Thread read/update via TX |
| `run` | `(target, task, prompt, tools, user=None, constraints=None, thread_id=None, result_type=None, **kwargs) -> dict` | Same as `agentic` | Yes | Thread read/update, tool calls via TX |
| `agentic_stream` | `(target, task: str, **kwargs)` | async gen of chunk dicts | Yes | Thread read/update via TX |
| `run_stream` | `(target, task, prompt, tools, user=None, constraints=None, thread_id=None, result_type=None, **kwargs)` | async gen of chunk dicts | Yes | Thread read/update, tool calls via TX |

#### AgentActor Methods

| Method | Signature | Returns | Exposed | Notes |
|--------|-----------|---------|---------|-------|
| `agentic` | `(self, task: str, **kwargs) -> str` | JSON string | `POST /agents/{id}/agentic` | Overrides mixin, returns str not dict |
| `agentic_stream` | `(self, task: str, **kwargs)` | async gen | `POST /agents/{id}/agentic_stream` (stream) | Overrides mixin |
| `_resolve_tool_addrs` | `(self) -> list[str]` | Actor addresses | Internal | Handles hrefs, AgentTool instances, plain strings |

#### Tool Discovery Functions

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `discover_tools` | `(actor_addrs: list, root, caller_addr: str = None) -> list[ToolSpec]` | ToolSpec list | Synchronous |
| `make_tool` | `(spec: ToolSpec) -> pydantic_ai.Tool` | Pydantic AI Tool | Synchronous |
| `create_tool_function` | `(spec: ToolSpec) -> async fn` | Async callable | Uses `exec()` |
| `_route_tool_call` | `(ctx, target_addr: str, method_name: str, data: dict) -> str` | JSON string | Async, raises `ModelRetry` on error |
| `_crud_tool_specs` | `(addr, tablename, model_name, schema) -> list[ToolSpec]` | ToolSpec list | Internal |
| `_method_tool_specs` | `(addr, tablename, model_name, schema, exclude=None) -> list[ToolSpec]` | ToolSpec list | Internal |

#### Thread Static Methods

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `to_history` | `(tx_messages: list) -> list[ModelMessage]` | pydantic-ai messages | Static |
| `from_history` | `(model_messages: list, source='', target='') -> list[dict]` | TX-shaped dicts | Static |

#### Module-Level Helpers (mixin.py)

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `_resolve_llm` | `(llm) -> Model` | pydantic-ai Model | Raises `ValueError` if falsy |
| `_build_schema_text` | `(cls) -> str` | Context string | Uses `run_pipeline(cls, pipeline='llm')` |
| `_build_instance_text` | `(target) -> str` | Instance data string | Truncates at 200 chars per field |

### 1.2 JavaScript Frontend API

#### Component Hierarchy

```
Component -> NTTMethod -> NTTStream -> NTTStreamAgent -> (app subclasses)
                                    -> NTTAgentLive
                                    -> NTTChat
NTTItem -> NtxAgent
```

#### UPPERCASE Handler Protocol (TX Inbox)

All three streaming components implement the same handler set:

| Handler | Data Shape | Dispatched By |
|---------|-----------|---------------|
| `THINKING(data, meta)` | `{text: string}` | NTTStream base |
| `TOOL_CALL(data, meta)` | `{tool, args, call_id}` | NTTStream base |
| `TOOL_RESULT(data, meta)` | `{tool, result, call_id}` | NTTStream base |
| `TEXT(data, meta)` | `{text: string}` | NTTStream base |
| `DONE(data, meta)` | `{answer, usage, tool_calls}` | NTTStream base |
| `STREAM_END(data)` | varies | NTTStream base |
| `STREAM_ERROR(data)` | `{message}` or string | NTTStream base |

---

## 2. Contracts & Invariants

### 2.1 AgentMixin Injection Contract

**Precondition**: `import n3tx_agents` must execute BEFORE any model with `__agent__ = True` is defined (`__init__.py:17-18` calls `register_mixin`).

**Invariant**: Any class with `__agent__ = True` has AgentMixin in its MRO before ActorModel. Verified at `test_mixin.py:132-133`.

**Postcondition**: The class gains `ctx`, `tools`, `agentic`, `run`, `agentic_stream`, `run_stream` methods.

**Risk**: Silent failure. If models are defined before `import n3tx_agents`, the mixin is never injected and no error is raised. The model simply lacks agent methods. This is documented in `CLAUDE.md` but has no runtime guard.

### 2.2 `ctx()` Contract

**Preconditions**: None (works on any model with `__agent__` flag).

**Postconditions**:
- Class call: returns string containing class name, tablename, schema properties.
- Instance call: returns same + "Current instance (id=...)" section with field values.
- If `__agent__['prompt']` is a string, it is prepended before the schema text.

**Invariant**: `ctx()` is purely read-only. No mutations, no network calls.

### 2.3 `tools()` Contract

**Preconditions**: None.

**Postconditions**:
- Returns `list[str]` of deduplicated actor addresses, order-preserving.
- With default config (`self_tools=True, neighbors=True`): includes own tablename + ListRef neighbor tablenames.
- `tools=[]` in `__agent__` config adds nothing; `tools=['x']` appends `'x'`.

**Invariant**: `tools()` is purely read-only. Same result for class and instance. No network calls.

### 2.4 `agentic()` Contract

**Preconditions**:
- Matrix must be initialized (`Actor.root()` must return non-None).
- `task` parameter is required (positional).

**Postconditions**:
- Returns dict with keys: `answer`, `usage`, `messages`, `message_count`.
- If `thread_id` is provided, also includes `thread_id` key.
- Thread is read before LLM call and updated after.

**Config cascade** (3-tier, `mixin.py:237-249`):
```
config.AGENT_DEFAULTS < __agent__ dict < agentic() kwargs
```

- `prompt`: kwargs override auto-generated `ctx()`.
- `tools`: presence check via `'tools' in kwargs` (not truthiness). `tools=[]` means no tools.
- `constraints`: merged across all three tiers (not replaced).
- `llm`: passed through to `run()` only if explicitly provided.

### 2.5 `run()` Contract

**Preconditions**:
- Matrix must be initialized.
- `task`, `prompt`, `tools` are all required positional parameters.
- LLM must resolve from the 4-tier cascade: `kwargs['llm']` > `__agent__['llm']` > `target.llm` attr > `config.AGENT_DEFAULTS['llm']`. Raises `ValueError` if all are falsy.

**Postconditions**:
- Returns dict: `{answer, usage: {input_tokens, output_tokens, requests}, messages: list, message_count: int, ?thread_id}`.
- `answer` type depends on `result_type`: string by default, structured Pydantic model if specified.
- All tool calls route through `Actor.root().request()` as TX messages.

**Error behavior**:
- `ValueError` if no LLM resolves (`mixin.py:87-91`).
- `RuntimeError("No Matrix root")` if no Matrix (`mixin.py:321-323`).
- `RuntimeError("Thread ... not found")` if `thread_id` points to nonexistent thread (`mixin.py:336-338`).
- Tool call errors raise `pydantic_ai.ModelRetry` (the LLM retries).
- Thread update failures are logged as warnings but do not raise (`mixin.py:403-407`).

### 2.6 `run_stream()` Contract

**Preconditions**: Same as `run()`.

**Postconditions**:
- Yields dicts with shape `{name: str, data: dict, meta: dict}`.
- `meta.seq` is monotonically increasing across all chunks.
- `meta.stream = True` on all non-terminal chunks.
- Terminal chunk is always `name='done'` with `meta.stream_end = True`.
- On exception: yields single `name='error'` chunk with `meta.error = True`, then stops.
- Error chunks have `data.code = 500` hardcoded.

**Critical invariant**: Errors are caught and yielded, never raised. The caller always gets a complete stream ending in either `done` or `error`. This is by design -- verified at `test_mixin.py:576-596`.

### 2.7 AgentActor.agentic() Override Contract

**Key difference from mixin**: Returns `str` (JSON), not `dict`.

The override at `actor.py:136-168`:
1. Resolves tools from DB via `_resolve_tool_addrs()`, not from `__agent__` config.
2. Calls `AgentMixin.__dict__['run'].fn` directly, bypassing MRO.
3. Returns `json.dumps(result, default=str)`.

**Caller must `json.loads()` the return value** when calling from Python code. When called via HTTP, the string is the response body directly.

**Constraint merging**: `{**self.constraints, **kwargs.get('constraints', {})}` -- kwargs override instance constraints per-key, unlike mixin which merges three tiers.

### 2.8 Tool Discovery Contract

`discover_tools()` at `tools.py:43`:

**Preconditions**:
- `root` must be a Matrix instance with `_children` dict.
- Actor addresses in `actor_addrs` must correspond to keys in `root._children`.

**Postconditions**:
- Returns `list[ToolSpec]`.
- Storable models get 5 CRUD specs (list, get, create, update, delete).
- All `@expose_route` methods get one spec each.
- Missing actors are skipped with a warning.
- Caller's own address (via `caller_addr`) is excluded (self-loop prevention).
- AgentActor subclasses have `run` and `stream_run` auto-excluded.

**Invariant**: Tool names follow `{tablename}_{method}` convention.

### 2.9 Thread Conversion Contract

`Thread.to_history()` at `thread.py:56`:
- Input: list of TX-shaped dicts (each has `data` key containing pydantic-ai message).
- Output: list of `ModelMessage` objects.
- Empty input returns empty list.

`Thread.from_history()` at `thread.py:75`:
- Input: list of `ModelMessage` objects (or dicts that pydantic-ai can serialize).
- Output: list of TX-shaped dicts with `name`, `source`, `target`, `data`, `meta`, `timestamp`.
- Empty input returns empty list.

**Invariant**: `from_history(to_history(msgs))` produces structurally equivalent output (verified at `test_thread.py:159-179`), though timestamps and source/target fields are set fresh by `from_history()`.

---

## 3. Error Handling Contracts

### 3.1 Error Type Taxonomy

| Error | Raised By | When | Caller Experience |
|-------|-----------|------|-------------------|
| `ValueError` | `_resolve_llm` | No LLM resolves from cascade | Propagates to caller |
| `RuntimeError("No Matrix root")` | `run`, `run_stream` | Matrix not initialized | Propagates to caller |
| `RuntimeError("Thread ... not found")` | `run`, `run_stream` | Invalid thread_id | Propagates to caller (run) or yielded as error chunk (run_stream) |
| `pydantic_ai.ModelRetry` | `_route_tool_call` | Tool returns error TX | LLM sees error, retries |
| Logged warning | `run`, `run_stream` | Thread update fails post-run | Swallowed -- caller unaware |
| Logged warning | `discover_tools` | Actor address not found | Skipped silently |

### 3.2 Error Asymmetry: `run()` vs `run_stream()`

**`run()`** (`mixin.py:268-421`): Exceptions propagate directly. No try/except wrapper. If the pydantic-ai agent raises, the caller gets a raw exception. If `_resolve_llm` raises `ValueError`, it propagates. If thread read fails, `RuntimeError` propagates.

**`run_stream()`** (`mixin.py:461-691`): The entire body is wrapped in `try/except Exception` at `mixin.py:506,685`. ALL exceptions become error chunks: `{'name': 'error', 'data': {'message': str(e), 'code': 500}, 'meta': {'stream': True, 'error': True, 'seq': seq}}`.

**Issue**: This asymmetry means `ValueError("No LLM provided")` becomes a proper exception from `run()` but an opaque error chunk from `run_stream()`. The error chunk hardcodes `code: 500` regardless of the actual error type. A `ValueError` (client error) should arguably be a 400, not 500. This is a minor inconsistency but could mislead debugging.

### 3.3 Thread Error Handling Gap

When `thread_id` is provided:
- Pre-run: `RuntimeError` on failed thread read (`mixin.py:334-338`).
- Post-run: Warning log on failed thread update (`mixin.py:403-407`).

The asymmetry means a successful agent run can silently lose its conversation history update. The caller has no indication that thread persistence failed. The `result_dict` still includes `thread_id`, implying success.

### 3.4 Tool Call Error Recovery

`_route_tool_call` at `tools.py:201-222` raises `ModelRetry` on error TXs. This is correct -- Pydantic AI will present the error to the LLM and retry. The error message comes from `response.data.get('message', 'Tool call failed')`. If the actor returns an error TX without a `message` key, the LLM sees the generic "Tool call failed" string.

---

## 4. Type Safety Analysis

### 4.1 Strong Typing

| Location | Mechanism | Notes |
|----------|-----------|-------|
| `AgentDeps` | `@dataclass` | Fields: `user: Optional[dict]`, `agent_addr: str` |
| `ToolSpec` | `@dataclass` | All 5 fields typed |
| `Thread` | Pydantic model | `messages: list`, `agent_addr: str`, `user_owner: Optional[int]` |
| `AgentTool` | Pydantic model | `target: str` (min_length=1), `description: str` |
| `AgentActor` fields | Pydantic | `name: str` (min_length=1), `prompt: str`, `llm: str`, `constraints: dict` |
| Stream event models | Pydantic | `TextChunk`, `ToolCallEvent`, etc. with typed fields |

### 4.2 Weak Typing / Type Leaks

**`user` parameter** -- typed as `dict` everywhere but never validated:
- `AgentDeps.user: Optional[dict]` (`deps.py:21`) -- any dict shape accepted.
- `run(user: dict = None)` (`mixin.py:270`) -- no validation of expected keys.
- Tool calls pass `meta={'user': ctx.deps.user}` (`tools.py:213`) -- downstream actors must know the dict shape.
- Real shape is `{user_id/id: int, email: str, role: str}` but this is never enforced.

**`constraints` parameter** -- typed as `dict` but only `max_iterations` is consumed:
- `mixin.py:370-372`: `constraints.get('max_iterations')` is the only read.
- Other keys are accepted and silently ignored.
- No validation that `max_iterations` is an integer.

**`tools` parameter** -- typed as `list` in docstrings but actual type hint is bare `list`:
- `run(tools: list)` (`mixin.py:269`) -- should be `list[str]`.
- `tools()` return annotation is `list` (`mixin.py:185`) -- should be `list[str]`.

**`result_type` parameter** -- typed as `None` default but no type annotation:
- `run(result_type=None)` (`mixin.py:271`) -- should be `type | None`.
- Passed directly to `Agent(output_type=result_type)` -- Pydantic AI validates it, but the error would be confusing.

**Dynamic attributes on target** -- several `getattr` calls with silent fallbacks:
- `getattr(target, '_addr', '')` (`mixin.py:313-315`): empty string if no actor addr.
- `getattr(target, 'llm', None)` (`mixin.py:307`): instance-level LLM attribute.
- `getattr(cls, '__agent__', False)` (`mixin.py:168-169`): returns False or dict.

**`_build_instance_text` silently swallows exceptions** (`mixin.py:117-137`):
- `model_dump()` failure returns empty string.
- `json.dumps()` failure falls back to `str()`.
- No logging -- errors in context generation are invisible.

### 4.3 The `args` Normalization Issue

Tool call args arrive as either `str` or `dict` from pydantic-ai (`mixin.py:568-574`). The backend normalizes `str` to `dict` via `json.loads`. On the frontend, `NTTStreamAgent.TOOL_CALL` (`ntx-stream-agent.js:33-34`) and `NTTAgentLive.TOOL_CALL` (`ntx-agent-live.js:115-116`) also independently parse JSON string args. This double-normalization is defensive but reveals that the wire format is not fully specified -- args can be either type depending on the LLM provider.

---

## 5. Usage Patterns in the Codebase

### 5.1 Pattern: Custom Model with `__agent__` Dict

The `veille` app's `Grant` model (`apps/veille/models/grant.py:48-52`):
```python
__agent__: ClassVar[dict] = {
    'self_tools': True,
    'neighbors': False,
    'tools': ['organizations'],
}
```

And `Run` model (`apps/veille/models/run.py:114-118`):
```python
__agent__: ClassVar[dict] = {
    'self_tools': False,
    'neighbors': False,
    'tools': ['web_tools', 'grants', 'sources'],
}
```

These demonstrate the config dict pattern: disabling auto-discovery and explicitly listing tool addresses. Both models call `self.agentic_stream()` from `@expose_route` streaming methods, forwarding chunks to the HTTP response.

### 5.2 Pattern: Importing Stream Event Models from actor.py

Both `grant.py:6-8` and `run.py:11-13` import stream event models:
```python
from n3tx_agents.actor import (
    TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk,
)
```

These are used in `@expose_route(events={...})` declarations. This import path (`n3tx_agents.actor`) is the only way to access these models -- they are not re-exported from `__init__.py`.

**Gap**: The event models are not in `__all__`. A developer looking at `__init__.py` would not discover them. They must know to look in `actor.py`.

### 5.3 Pattern: AgentActor via Example App

`examples/grants/main.py:36-39`:
```python
app = create_app(
    models=[User, Grant, Source, WebTools, AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool)],
    ...
)
```

This shows the required registration ceremony: both `AgentTool` and `AgentActor` must be in `models`, and their join relationship in `join_models`. The conftest (`examples/grants/tests/conftest.py:123-149`) shows the manual join-table seeding pattern.

### 5.4 Pattern: Direct `AgentMixin.__dict__['run'].fn` Bypass

`actor.py:156-157`:
```python
run_fn = AgentMixin.__dict__['run'].fn
result = await run_fn(self, task=task, prompt=self.prompt, ...)
```

AgentActor accesses the raw function inside the `fullmethod` descriptor to bypass MRO. This is necessary because AgentActor's own `agentic()` is decorated with `@expose_route`, which would conflict with the mixin's `agentic()`. The same pattern appears for `run_stream` at `actor.py:192`.

**Coupling risk**: This bypasses the descriptor protocol entirely and directly references `fullmethod`'s `.fn` attribute. If `fullmethod` is refactored to store the function differently, this breaks.

### 5.5 Anti-Pattern: `agentic()` Return Type Inconsistency

- `AgentMixin.agentic()` returns `dict` (mixin.py:220).
- `AgentActor.agentic()` returns `str` (JSON string) (actor.py:137).

Callers must know which path they are on:
- `test_mixin.py:354`: `result = await AgenticProduct.agentic(...)` -- gets dict, accesses `result['answer']` directly.
- `test_agent_actor.py:264-268`: `result_str = await agent.agentic(...)` then `result = json.loads(result_str)`.
- `test_agent_chat.py:45-46`: HTTP response is parsed with `json.loads(data)` after checking if it is a string.

---

## 6. Developer Experience Analysis

### 6.1 Positive Patterns

**Zero-config simplicity**: Adding `__agent__ = True` to any ActorModel immediately gives it 6 methods. No imports, no configuration. This aligns perfectly with "zero to working, then customize."

**Config cascade is intuitive**: The 3-tier cascade (`AGENT_DEFAULTS < __agent__ dict < kwargs`) follows a natural specificity progression. The `tools` presence check (`'tools' in kwargs`) is a clever design that distinguishes "I want no tools" from "give me the default."

**Stream chunk format is consistent**: All 6 chunk types follow the same `{name, data, meta}` shape. `meta.seq` provides ordering. `meta.stream_end` marks termination. This is a clean wire protocol.

**TestModel integration**: Every async test can pass `llm=TestModel(call_tools=[])` to avoid real LLM calls. Tool call simulation via `call_tools=['grants_list']` is elegant.

### 6.2 Pain Points

**Import ordering trap**: `import n3tx_agents` must precede model definition. This is the #1 surprise for new developers. The failure mode is silent -- no error, just missing methods. A runtime check in `AgentMixin.__init_subclass__` or at model-definition time would convert this from silent failure to loud failure.

**Return type surprise**: `AgentActor.agentic()` returns `str` while `AgentMixin.agentic()` returns `dict`. A developer calling `result['answer']` on an AgentActor response gets a `TypeError` with no clear message. This violates the Liskov substitution principle -- a subclass's override changes the return type.

**Thread creation is manual**: To use threads, the caller must create a `Thread` record via CRUD, then pass its `id` to `agentic()`. There is no `auto_thread` convenience. Compare to the zero-config philosophy of `__agent__ = True`.

**Event model discoverability**: `TextChunk`, `ToolCallEvent`, etc. are defined in `actor.py` but not exported from `__init__.py`. The pattern of importing them (`from n3tx_agents.actor import TextChunk`) requires knowing the internal file structure.

**Streaming vs non-streaming method choice**: The relationship between `agentic`/`agentic_stream` and `run`/`run_stream` is clear in docs but subtle in practice. `agentic()` is the public API; `run()` is the engine. But AgentActor exposes both `agentic` and `agentic_stream` via HTTP while the mixin's `run()` is never exposed. A new developer might try to expose `run()` via `@expose_route`, which would bypass the config cascade.

### 6.3 Error Message Quality

- `ValueError("No LLM provided. Pass an llm= argument ...")` at `mixin.py:87-91`: Excellent. Lists all resolution paths.
- `RuntimeError("No Matrix root. Initialize a Matrix before running agents.")` at `mixin.py:321-323`: Clear and actionable.
- `RuntimeError("Thread ... not found or access denied: ...")` at `mixin.py:336-338`: Includes the downstream error message.
- `ModelRetry("Tool call failed")` at `tools.py:221`: Generic fallback. When the actor's error TX lacks a `message` field, the LLM gets this uninformative string.

---

## 7. Naming Analysis

### 7.1 Consistent Naming

- `agentic` / `agentic_stream`: Policy layer naming is consistent.
- `run` / `run_stream`: Engine layer naming is consistent.
- `ctx` / `tools`: Short, descriptive, discoverable.
- `tool_name = {tablename}_{method}`: Convention is clear and predictable.
- TX chunk names (`text`, `tool_call`, `tool_result`, `thinking`, `done`, `error`): Match the event models.

### 7.2 Naming Issues

**`target` overloading**: In `fullmethod`, the first parameter is called `target` (class or instance). In `ToolSpec`, `actor_addr` is the target actor. In `AgentTool`, the field is called `target` (the actor address). In `TX`, `target` is the destination actor. These are all different things named similarly.

**`agentic` as both noun and verb**: `AgentActor.agentic()` is a method (verb). `schema['agent']['agentic_endpoint']` uses it as an adjective. `__agent__` is a flag. The naming cluster (`agent`, `agentic`, `__agent__`) is somewhat overloaded.

**`run` name collision potential**: `AgentMixin.run()` vs pydantic-ai's `agent.run()`. In `mixin.py:382`, `result = await ai_agent.run(task, **run_kwargs)` calls pydantic-ai's run. The variable name `ai_agent` disambiguates, but `run` appearing twice in the call chain (`self.run -> ai_agent.run`) is confusing when reading stack traces.

**`make_tool` vs `create_tool_function`**: `make_tool` wraps `create_tool_function`. The naming distinction is unclear -- `create_tool_function` creates the raw async function, `make_tool` wraps it in `pydantic_ai.Tool`. "make" vs "create" does not convey this difference. Better: `create_tool_fn` and `wrap_as_pydantic_tool`.

**`stream_run` vs `run_stream`**: The agent exclusion list at `tools.py:96` references `{'run', 'stream_run'}`, but the actual method name in AgentMixin is `run_stream`. The schema may or may not expose a method called `stream_run`. This is a potential mismatch bug -- if `run_stream` is exposed in the schema under its actual name, the exclusion filter would miss it.

### 7.3 Bug: `stream_run` vs `run_stream` Exclusion

At `tools.py:94-96`:
```python
if isinstance(cls, type) and issubclass(cls, AgentActor):
    agent_methods = {'run', 'stream_run'}
```

The actual method defined by AgentMixin is `run_stream` (not `stream_run`). If `run_stream` were exposed via `@expose_route` on an AgentActor subclass, it would NOT be excluded by this filter. Currently, `run_stream` is NOT decorated with `@expose_route` on AgentActor (only `agentic` and `agentic_stream` are), so this bug is latent. However, the doc at `agent-actor.md:159` says "AgentActor.run and AgentActor.stream_run are auto-excluded" using the wrong name.

The corresponding test at `test_tools.py:416-436` only checks that `run` is excluded, not `stream_run` or `run_stream`, so the bug is not caught by tests.

---

## 8. Parameter Validation Analysis

### 8.1 Boundary Validation

| Parameter | Validated | How | Risk |
|-----------|-----------|-----|------|
| `task` (agentic/run) | Partially | Positional arg, Python raises TypeError if missing | Empty string is valid but useless |
| `prompt` (run) | No | Accepted as-is, passed to pydantic-ai | Empty string produces undefined LLM behavior |
| `tools` (run) | No | Each address looked up in Matrix children | Unknown addresses logged, skipped |
| `llm` (run) | Yes | `_resolve_llm` validates truthy, handles `ollama:*` | `ValueError` on falsy |
| `thread_id` (run) | Yes | Thread fetched via TX, RuntimeError on not found | Type not validated (could be string, would fail differently) |
| `result_type` (run) | No | Passed to pydantic-ai Agent, which validates it | Error message from pydantic-ai may be confusing |
| `constraints` (run) | No | `constraints.get('max_iterations')` reads one key | No check that `max_iterations` is positive integer |
| `user` (run) | No | Passed through to TX meta and AgentDeps | Any dict shape accepted |

### 8.2 Schema-Level Validation

`AgentActor` fields:
- `name: str = Field(min_length=1, max_length=200)` -- validated by Pydantic.
- `llm: str = Field(default='ollama:llama3.1')` -- validated as string, but not validated as a valid provider:model format.
- `constraints: dict = Field(default={})` -- any dict accepted.
- `tools: ListRef[AgentTool]` -- validates via ListRef pattern at storage level.

`AgentTool`:
- `target: str = Field(min_length=1)` -- non-empty string required.
- `description: str = Field(default='')` -- optional.

### 8.3 Tool Function Parameter Validation

`create_tool_function` at `tools.py:225-296` generates functions with Python type annotations. Pydantic AI validates tool parameters against these types before calling the function. The type mapping (`_JSON_TYPE_MAP`) covers 6 JSON Schema types. Unknown types default to `str` via `_JSON_TYPE_MAP.get(prop.get('type', 'string'), 'str')`.

**Gap**: `$ref` and `anyOf`/`oneOf` types in JSON Schema are not handled. If a parameter has a complex type, it falls through to `str`. This would cause type mismatches at runtime when the LLM provides a dict and the function expects a string.

---

## 9. Return Value Contracts

### 9.1 `run()` / `agentic()` Return Shape

```python
{
    'answer': str | structured_type,  # LLM output (str default, result_type if specified)
    'usage': {
        'input_tokens': int | None,
        'output_tokens': int | None,
        'requests': int,
    },
    'messages': list,          # pydantic-ai ModelMessage objects (not JSON-serializable)
    'message_count': int,      # len(messages) -- backward compat
    'thread_id': int,          # ONLY present when thread_id was provided
}
```

**Issue with `messages` field**: The `messages` list contains pydantic-ai `ModelMessage` objects. These are not directly JSON-serializable. When `AgentActor.agentic()` calls `json.dumps(result, default=str)` at `actor.py:168`, the `messages` field is serialized via `str()`, producing repr strings rather than useful data. This means the HTTP response's `messages` field is essentially garbage -- stringified Python objects.

### 9.2 Stream Chunk Shapes

All chunks follow `{name: str, data: dict, meta: dict}`.

| name | data keys | meta keys |
|------|-----------|-----------|
| `text` | `text` | `stream`, `seq` |
| `tool_call` | `tool`, `args`, `call_id` | `stream`, `seq` |
| `tool_result` | `tool`, `result`, `call_id` | `stream`, `seq` |
| `thinking` | `text` | `stream`, `seq` |
| `done` | `answer`, `usage`, `tool_calls`, `?thread_id` | `stream`, `stream_end`, `seq` |
| `error` | `message`, `code` | `stream`, `error`, `seq` |

**Consistency**: The `done` chunk includes `answer` as string (via `str(output)` at `mixin.py:664`), while `run()` returns `answer` as the raw output object. If `result_type` is used, `run()` returns the structured object but `run_stream()`'s done chunk stringifies it.

### 9.3 AgentActor.agentic() vs AgentMixin.agentic()

| Aspect | AgentMixin.agentic() | AgentActor.agentic() |
|--------|---------------------|---------------------|
| Return type | `dict` | `str` (JSON) |
| `messages` field | ModelMessage objects | `str()` of ModelMessage objects |
| HTTP exposure | Not directly exposed | `@expose_route('/agentic')` |
| Tool resolution | Auto-discovered from `tools()` | DB-resolved via `_resolve_tool_addrs()` |
| Config source | 3-tier cascade | DB fields + kwargs |

---

## 10. Lifecycle & Ordering Requirements

### 10.1 Initialization Sequence

```
1. import n3tx_agents             # registers AgentMixin, schema extension
2. Define models with __agent__   # mixin injected via __init_subclass__
3. Matrix()                       # creates root actor
4. register_model(...)            # registers models as Matrix children
5. create_app() or manual setup   # wires routes
```

Violations:
- Step 1 after step 2: Silent failure -- models lack agent methods.
- Step 4 before step 3: Actor registration fails (no root).
- `run()`/`agentic()` before step 3: `RuntimeError("No Matrix root")`.

### 10.2 Thread Lifecycle

```
1. Thread.create(Thread(agent_addr='...', user_owner=N))
2. Pass thread.id to agentic(thread_id=...)
3. Agent reads thread, runs LLM, updates thread
4. Repeat step 2 for multi-turn
```

Thread lifecycle is fully manual. No auto-creation, no auto-cleanup. Orphan threads (no agent references them) persist indefinitely.

### 10.3 Stream Lifecycle

```
1. callMethod() on frontend
2. Backend yields chunks via SSE
3. Frontend dispatches UPPERCASE handlers per chunk name
4. DONE received -> update UI footer
5. STREAM_END received -> re-enable UI, refresh parent entity
6. STREAM_ERROR received -> show error, re-enable UI
```

**Frontend cleanup**: All three components (`NTTStreamAgent`, `NTTAgentLive`, `NTTChat`) clear timers in `disconnectedCallback()`. `NTTStreamAgent.callMethod()` clears buffers and tool card maps before each new call.

### 10.4 Tool Function Lifecycle

Tool functions are created per-run (not cached). Each call to `run()` or `run_stream()`:
1. Calls `discover_tools()` -- reads schemas from Matrix children.
2. Calls `make_tool()` per spec -- generates a new async function via `exec()`.
3. Creates a new `pydantic_ai.Agent` with these tools.
4. Runs the agent.

Functions are GC'd after the run completes. No caching. This means repeated calls to the same agent regenerate all tool functions. For most use cases this is fine (tools can change between runs), but it is worth noting for high-frequency scenarios.

---

## 11. Documentation Gaps

### 11.1 Documented but Wrong/Stale

**`agent-actor.md:159`**: "AgentActor.run and AgentActor.stream_run are auto-excluded" -- the method name is `run_stream`, not `stream_run`. This matches the bug in `tools.py:96`.

**`tool-discovery.md:97-98`**: "_route_tool_call ... sends via adapter.request()" -- it actually sends via `Actor.root().request()` (Matrix root), not an adapter. The adapter reference is outdated.

### 11.2 Undocumented Behaviors

**`_build_instance_text` truncation** (`mixin.py:123-129`): Field values over 200 characters are truncated with `...`. This is noted in a code comment as needing review but is not documented in `mixin.md`. Truncation affects the LLM's context quality.

**`_resolve_llm` Ollama URL normalization** (`mixin.py:96-98`): Appends `/v1` to `config.OLLAMA_BASE_URL` if not present. This OpenAI-compatibility shim is not documented.

**Stream event models** (`actor.py:41-66`): Five ProtoModel subclasses. Not in `__all__`, not in `__init__.py` exports. The pattern of importing them from `n3tx_agents.actor` is shown in app code but not documented.

**`agentic_stream` class-level instantiation** (`mixin.py:444-448`): When called on a class, `agentic_stream` creates a new instance via `target()`. This is a significant behavior not called out in the method's docstring. If the constructor requires arguments, this will fail. It is also inconsistent with `agentic()` which calls `target.run()` without instantiation.

**Thread access control** (`thread.py:44-49`): Thread has `OWNER | ROLE('admin')` on read/update/delete. This means only the thread creator (or admin) can read thread history. Agent tool calls accessing threads go through Matrix TX, which may or may not enforce this depending on the TX meta. The access control interaction between agent internal TX and Thread CRUD is not documented.

### 11.3 Documentation-Code Alignment

| Doc Claim | Code Reality | Match? |
|-----------|-------------|--------|
| "3-tier cascade" (mixin.md) | `AGENT_DEFAULTS < __agent__ < kwargs` | Yes |
| "LLM 4-tier in run()" (mixin.md:87-89) | `kwargs > __agent__ > instance.llm > AGENT_DEFAULTS` | Yes |
| "tool_calls count in done chunk" (mixin.md:107) | `done_data['tool_calls'] = tool_call_count` at mixin.py:670 | Yes |
| "error chunks have code: 500" (mixin.md:108) | `'code': 500` hardcoded at mixin.py:689 | Yes |
| "seq monotonically increasing" (mixin.md:107) | `seq` incremented per event, verified in test | Yes |
| "run() raises ValueError for no LLM" (mixin.md:173) | `_resolve_llm` raises ValueError | Yes |

---

## 12. Cross-Cutting Concerns

### 12.1 Frontend Code Duplication

`NTTStreamAgent` and `NTTAgentLive` implement nearly identical UPPERCASE handlers with nearly identical CSS. Key differences:

| Aspect | NTTStreamAgent | NTTAgentLive |
|--------|---------------|-------------|
| Base class | NTTStream | NTTStream |
| Output container | `.agent-output` (created dynamically) | `#log` (in prerender) |
| Auto-scroll | Respects user scroll position (within 10px) | Always scrolls to bottom |
| Tool result rendering | `textContent` (plain text, 500 char limit) | `renderJson()` (rich JSON tree) |
| CSS injection | Via `style.textContent +=` | Via prerender `<style>` |
| Markdown | `marked.parse` if available, else `textContent` | Same |
| `#esc()` | Same implementation | Same implementation |

The rendering logic (`#scheduleRender`, `#renderMd`, `#flushRender`, `#setThinking`) is copy-pasted between the two components. This is ~100 lines of duplicated logic. A shared mixin or base class between them would reduce maintenance burden.

`NTTChat` has a simpler version of the same handlers (no markdown, no collapsible entries, no scheduled rendering). The duplication is lower but the handler structure is the same.

### 12.2 `marked` Library Dependency

Both `NTTStreamAgent` (`ntx-stream-agent.js:213`) and `NTTAgentLive` (`ntx-agent-live.js:267`) check `typeof marked !== 'undefined'`. The `marked` library is a runtime dependency loaded separately (not bundled). If missing, text is rendered as `textContent` (no markdown). This graceful degradation is good, but the dependency is not documented in the component files or the package metadata.

### 12.3 Security: innerHTML Usage

Both `NTTStreamAgent` and `NTTAgentLive` use `content.innerHTML = marked.parse(buf)` for markdown rendering. Since `buf` is accumulated from LLM output (which itself may be influenced by user input via the task prompt), this is a potential XSS vector if `marked` does not sanitize HTML. The `#esc()` helper is used for tool names and error messages but NOT for the main text/thinking content rendered via markdown.

### 12.4 Security: `exec()` in Tool Generation

`create_tool_function` at `tools.py:293` uses `exec(code, ns)`. The namespace is tightly controlled: only `_route`, `_target`, `_method`, and `_required` are injected. The code template at `tools.py:278-283` constructs the function from schema-derived parameter names and types. Parameter names are sanitized (`isidentifier()` check at `tools.py:249`), and the description is escaped. The input (schema) comes from our own model definitions, not user input. This is acceptable and follows the same pattern as Python's `dataclasses` module.

---

## 13. Summary of Findings

### Critical Issues

1. **`stream_run` vs `run_stream` name mismatch** (`tools.py:96`): The exclusion set uses `stream_run` but the actual method is `run_stream`. This is a latent bug that would manifest if `run_stream` were exposed via `@expose_route` on an AgentActor subclass.

2. **`messages` field serialization** (`actor.py:168`): `json.dumps(result, default=str)` stringifies `ModelMessage` objects into repr strings. The HTTP response's `messages` field is not useful.

### Significant Issues

3. **Return type inconsistency**: `AgentMixin.agentic()` returns `dict`, `AgentActor.agentic()` returns `str`. This violates substitutability and surprises callers.

4. **Silent mixin injection failure**: No runtime warning if `__agent__ = True` model is defined before `import n3tx_agents`.

5. **Error code hardcoding**: `run_stream()` yields `code: 500` for all errors including `ValueError` (which should be 4xx).

6. **Thread update failure is silent**: Post-run thread update failures are logged but the result dict still includes `thread_id`, implying success.

### Minor Issues

7. **Event models not exported**: `TextChunk`, `ToolCallEvent`, etc. not in `__all__` or `__init__.py`.

8. **Frontend code duplication**: ~100 lines of rendering logic duplicated between `NTTStreamAgent` and `NTTAgentLive`.

9. **`user` parameter untyped**: `dict` with no shape validation anywhere in the pipeline.

10. **`constraints` parameter sparsely consumed**: Only `max_iterations` is read; other keys are silently ignored.

11. **`agentic_stream` class-level creates empty instance** (`mixin.py:444-448`): Undocumented, fragile if constructor requires arguments.

12. **`marked` library undocumented**: Runtime dependency for markdown rendering in streaming components.

### Architecture Alignment

The agents subsystem follows the project's "model is the app" philosophy well. `__agent__ = True` mirrors `__storable__ = True`. The schema extension pipeline integrates cleanly. The TX-based tool routing through Matrix is consistent with the actor system's design.

The main tension is between AgentActor (data-driven, DB-config) and AgentMixin (code-driven, config-cascade). They solve different problems but share the same method names with different return types and config resolution paths. This dual nature is powerful but requires careful documentation and consistent contracts.
