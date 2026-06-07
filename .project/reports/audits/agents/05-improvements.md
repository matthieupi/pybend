# Agents Subsystem: Strategic Improvements

> Audit date: 2026-03-26 | Branch: v0.9 | Auditor: Claude Opus 4.6

## Table of Contents

1. [Mental Model Simplification](#1-mental-model-simplification)
2. [Interface Tightening](#2-interface-tightening)
3. [Composability Improvements](#3-composability-improvements)
4. [Resilience & Error Recovery](#4-resilience--error-recovery)
5. [Extensibility Without Modification](#5-extensibility-without-modification)
6. [Convention Over Configuration](#6-convention-over-configuration)
7. [Consistency Gaps](#7-consistency-gaps)
8. [Propositions Summary Table](#8-propositions-summary-table)

---

## 1. Mental Model Simplification

### 1a. The agentic/run Duality Creates Confusion

**Current model:**

```
agentic(task, **kwargs)         agentic_stream(task, **kwargs)
  |  config cascade               |  config cascade
  v                               v
run(task, prompt, tools, ...)   run_stream(task, prompt, tools, ...)
  |  LLM resolution               |  LLM resolution
  v                               v
pydantic-ai Agent.run()         pydantic-ai Agent.iter()
```

Four public methods (agentic, run, agentic_stream, run_stream) on every agent-enabled model. The documentation says "Expose agentic() via HTTP, never run() directly" (mixin.py:16), yet `run()` is a `@fullmethod` on the public API surface. The split exists to allow bypassing the config cascade, but in practice:

- `agentic()` always delegates to `run()` (mixin.py:265)
- `agentic_stream()` always delegates to `run_stream()` (mixin.py:458)
- AgentActor bypasses `agentic()` entirely and calls `run()`/`run_stream()` directly via descriptor access (actor.py:157, actor.py:193)
- No usage site calls `run()` or `run_stream()` directly except tests and AgentActor

The real distinction is "with config cascade" vs "without config cascade" -- but that is a parameter (`resolve_config=True/False`), not two methods.

**Proposed simpler model:**

```
agentic(task, **kwargs)             agentic_stream(task, **kwargs)
  |                                   |
  | resolve config if not explicit    | resolve config if not explicit
  | build pydantic-ai Agent           | build pydantic-ai Agent
  | Agent.run() / Agent.iter()        | yields TX-aligned chunks
  v                                   v
dict                                async generator
```

Two methods instead of four. `run()` and `run_stream()` become internal (`_run`, `_run_stream`). The public API is `agentic()` and `agentic_stream()`. When all params are passed explicitly (as AgentActor does), the config cascade is a no-op -- no behavior change.

```python
# Proposed mixin interface
class AgentMixin:
    @fullmethod
    def ctx(target) -> str: ...

    @fullmethod
    def tools(target) -> list: ...

    @fullmethod
    async def agentic(target, task: str, **kwargs) -> dict:
        """Single entry point. Config cascade runs only for missing params."""
        prompt = kwargs.get('prompt') or target.ctx()
        tools = kwargs['tools'] if 'tools' in kwargs else target.tools()
        # ... resolve remaining params ...
        return await _run(target, task=task, prompt=prompt, tools=tools, ...)

    @fullmethod
    async def agentic_stream(target, task: str, **kwargs):
        """Single streaming entry point."""
        # ... same resolution ...
        async for chunk in _run_stream(target, ...):
            yield chunk
```

**What breaks:** AgentActor currently accesses `AgentMixin.__dict__['run'].fn` (actor.py:157) and `AgentMixin.__dict__['run_stream'].fn` (actor.py:192). After the change, AgentActor would simply call `self.agentic(task=task, prompt=self.prompt, tools=tool_addrs, llm=self.llm, ...)` -- passing all params explicitly makes the cascade a no-op.

**Trade-offs:** API surface shrinks from 6 to 4 public methods. Eliminates the descriptor `.fn` access hack in AgentActor. The "engine" is still accessible as `_run()` for framework internals and testing. Loss: advanced users who want to bypass cascade without passing all params would need to pass `prompt=` and `tools=` explicitly -- but this is already clearer.

### 1b. Thread Management Is Split Across Two Layers

**Current model:** Thread read/update logic is embedded inside `run()` (mixin.py:326-408) and duplicated in `run_stream()` (mixin.py:507-661). The Thread model itself (thread.py) is a clean data model, but the "read before, update after" lifecycle is hard-coded into the engine.

```
run()                                  run_stream()
  |-- TX get thread                      |-- TX get thread
  |-- convert to history                 |-- convert to history
  |-- Agent.run(message_history=...)     |-- Agent.iter(message_history=...)
  |-- TX update thread                   |-- TX update thread
  |-- return result                      |-- yield done chunk
```

This duplication (mixin.py:326-341 mirrors mixin.py:507-523; mixin.py:388-407 mirrors mixin.py:642-661) means any change to thread lifecycle must be made in two places.

**Proposed simpler model:** Extract thread lifecycle into a context manager:

```python
class ThreadContext:
    """Read-before / update-after thread lifecycle."""

    def __init__(self, thread_id, root, user=None, agent_addr=''):
        self.thread_id = thread_id
        self.root = root
        self.user = user
        self.agent_addr = agent_addr
        self.message_history = None

    async def __aenter__(self):
        if self.thread_id is None:
            return self
        tx = TX(name='get', source=self.root.addr, target='threads',
                data={'id': self.thread_id},
                meta={'user': self.user} if self.user else {})
        resp = await self.root.request(tx)
        if resp.is_error:
            raise RuntimeError(f"Thread {self.thread_id} not found")
        self.message_history = Thread.to_history(resp.data.get('messages', []))
        return self

    async def update(self, all_messages):
        if self.thread_id is None:
            return
        tx = TX(name='update', source=self.root.addr, target='threads',
                data={'id': self.thread_id,
                      'messages': Thread.from_history(all_messages,
                          source=self.root.addr, target=self.agent_addr)},
                meta={'user': self.user} if self.user else {})
        resp = await self.root.request(tx)
        if resp.is_error:
            logger.warning("Failed to update thread %s", self.thread_id)

    async def __aexit__(self, *exc):
        pass  # update is explicit, not automatic
```

Both `run()` and `run_stream()` shrink by ~20 lines each. Single source of truth for thread lifecycle.

---

## 2. Interface Tightening

### 2a. run() and run_stream() Accept Kwargs They Shouldn't

**Current state:** `run()` signature (mixin.py:269):
```python
async def run(target, task: str, prompt: str, tools: list,
              user: dict = None, constraints: dict = None,
              thread_id=None, result_type=None, **kwargs) -> dict:
```

The `**kwargs` catch-all is used only for `llm` (mixin.py:305). This hides what `run()` actually accepts. A caller passing `kwargs['nonexistent']` gets silently ignored.

**Proposed change:** Make `llm` an explicit parameter:

```python
async def run(target, task: str, prompt: str, tools: list,
              user: dict = None, constraints: dict = None,
              thread_id=None, result_type=None, llm=None) -> dict:
```

Same for `run_stream()` (mixin.py:462). This is a non-breaking change -- callers already pass `llm=` as a keyword argument.

### 2b. AgentDeps Is Too Thin

**Current state:** `AgentDeps` (deps.py) has exactly two fields:

```python
@dataclass
class AgentDeps:
    user: Optional[dict]
    agent_addr: str
```

Every tool function receives this via `RunContext[AgentDeps]`, but only `ctx.deps.user` is used (tools.py:211). The `agent_addr` field is set (mixin.py:366) but never read by any code in the codebase.

**Proposed change:** Keep `AgentDeps` but make it useful. Add fields that tool functions actually need:

```python
@dataclass
class AgentDeps:
    user: Optional[dict]
    agent_addr: str
    root: Any = None  # Matrix root -- tools currently import Actor.root() internally
```

This lets `_route_tool_call()` use `ctx.deps.root` instead of importing and calling `Actor.root()` (tools.py:208) at every tool invocation. Minor but removes a repeated lookup.

### 2c. _resolve_llm Handles Only One Provider Specially

**Current state:** `_resolve_llm()` (mixin.py:76-102) has special handling for `ollama:` prefix strings, converting them to `OpenAIChatModel` with `OllamaProvider`. All other strings are passed through as-is to pydantic-ai.

This works because pydantic-ai handles `anthropic:model`, `openai:model`, etc. natively. The Ollama special case exists because Ollama requires a custom base URL (mixin.py:96-97).

**Problem:** If another provider needs a custom base URL (e.g., a self-hosted vLLM endpoint), developers must override `_resolve_llm()` -- but it is a module-level function, not overridable via the mixin or model.

**Proposed change:** Make provider resolution a registry:

```python
# In mixin.py or a new providers.py
_PROVIDER_RESOLVERS = {}

def register_provider(prefix: str, resolver):
    """Register a provider resolver for LLM strings like 'prefix:model'."""
    _PROVIDER_RESOLVERS[prefix] = resolver

def _resolve_llm(llm):
    if not llm:
        raise ValueError("No LLM provided.")
    if not isinstance(llm, str):
        return llm
    prefix = llm.split(':', 1)[0] if ':' in llm else None
    if prefix and prefix in _PROVIDER_RESOLVERS:
        return _PROVIDER_RESOLVERS[prefix](llm)
    return llm

# Default: register ollama
register_provider('ollama', lambda llm: OpenAIChatModel(
    llm.split(':', 1)[1],
    provider=OllamaProvider(base_url=config.OLLAMA_BASE_URL.rstrip('/') + '/v1'),
))
```

**Migration:** Non-breaking. Existing `ollama:` strings work identically. New providers are additive.

---

## 3. Composability Improvements

### 3a. Stream Event Models Are Not Reusable Across Models

**Current state:** The five stream event models (TextChunk, ToolCallEvent, etc.) are defined in actor.py:41-66 and imported by every model that uses `events=` on `@expose_route`:

```python
# apps/veille/models/run.py:11-13
from n3tx_agents.actor import (
    TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk,
)
```

```python
# apps/veille/models/grant.py:7-8
from n3tx_agents.actor import (
    TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk,
)
```

Every streaming agent endpoint repeats the same import and the same `events=` dict:

```python
events={
    'text': TextChunk, 'tool_call': ToolCallEvent,
    'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
    'done': DoneChunk,
}
```

This is boilerplate. The "standard agent event vocabulary" is a known, fixed set but must be manually assembled at every usage site.

**Proposed change:** Export a pre-built events dict:

```python
# In n3tx_agents/__init__.py or a new events.py
AGENT_EVENTS = {
    'text': TextChunk,
    'tool_call': ToolCallEvent,
    'tool_result': ToolResultEvent,
    'thinking': ThinkingChunk,
    'done': DoneChunk,
}
```

Usage becomes:

```python
from n3tx_agents import AGENT_EVENTS

@expose_route('/analyze', methods=['POST'], stream=True, events=AGENT_EVENTS)
async def analyze(self, user=None):
    async for chunk in self.agentic_stream(task=...):
        yield chunk
```

App-specific events compose naturally:

```python
from n3tx_agents import AGENT_EVENTS

@expose_route('/execute', stream=True, events={**AGENT_EVENTS,
    'source_start': SourceStartEvent, 'source_done': SourceDoneEvent})
```

### 3b. Frontend Agent Rendering Logic Is Duplicated Three Times

**Current state:** The UPPERCASE handlers (THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE, STREAM_END, STREAM_ERROR) and their rendering helpers (#addEntry, #setThinking, #scheduleRender, #renderMd, #flushRender, #scrollToBottom, #esc) are implemented three times with near-identical code:

| Component | File | Lines |
|-----------|------|-------|
| NTTStreamAgent | ntx-stream-agent.js | 1-353 |
| NTTAgentLive | ntx-agent-live.js | 1-454 |
| NTTChat | ntx-chat.js | 1-377 |

Concrete duplication (comparing NTTStreamAgent and NTTAgentLive):
- `THINKING()`: ntx-stream-agent.js:17-28 vs ntx-agent-live.js:100-111 -- identical logic
- `TOOL_CALL()`: ntx-stream-agent.js:30-46 vs ntx-agent-live.js:113-128 -- identical except `renderJson` vs `#esc`
- `TOOL_RESULT()`: ntx-stream-agent.js:48-62 vs ntx-agent-live.js:130-142 -- near-identical
- `TEXT()`: ntx-stream-agent.js:64-75 vs ntx-agent-live.js:145-156 -- identical
- `DONE()`: ntx-stream-agent.js:77-93 vs ntx-agent-live.js:158-168 -- identical
- `#setThinking()`: ntx-stream-agent.js:169-187 vs ntx-agent-live.js:224-241 -- identical
- `#scheduleRender()`: ntx-stream-agent.js:189-205 vs ntx-agent-live.js:243-259 -- identical
- `#renderMd()`: ntx-stream-agent.js:207-221 vs ntx-agent-live.js:261-275 -- identical
- CSS for entries: ~120 identical lines in both files

NTTChat has a slimmer version of the same handlers (no markdown, no collapsible entries) but still duplicates the dispatch structure.

**Proposed change:** Extract a `AgentStreamRenderer` mixin or utility class that owns the UPPERCASE handlers and rendering:

```javascript
// agent-stream-renderer.js — shared rendering logic
export class AgentStreamRenderer {
    #toolCards = new Map();
    #textBuf = ''; #textRendered = 0; #textTimer = null;
    #thinkBuf = ''; #thinkRendered = 0; #thinkTimer = null;

    constructor(outputFn) {
        this.output = outputFn;  // () => HTMLElement (the log container)
    }

    handleThinking(data) { /* single implementation */ }
    handleToolCall(data) { /* single implementation */ }
    handleToolResult(data) { /* single implementation */ }
    handleText(data) { /* single implementation */ }
    handleDone(data) { /* single implementation */ }
    handleError(data) { /* single implementation */ }
    reset() { /* clear buffers */ }
    flush() { /* force-render pending buffers */ }
    dispose() { /* clear timers */ }
}
```

Components delegate:

```javascript
class NTTStreamAgent extends NTTStream {
    #renderer;

    connectedCallback() {
        super.connectedCallback();
        this.#renderer = new AgentStreamRenderer(() => this.#output());
    }

    THINKING(data) { this.#renderer.handleThinking(data); }
    TEXT(data)     { this.#renderer.handleText(data); }
    // ... one-liner delegations
}
```

**Trade-offs:** Adds one file, removes ~400 lines of duplication. Each component keeps its own layout (panel, chat bubbles, embedded card) but delegates event rendering. NTTChat's simpler rendering could use a `ChatStreamRenderer` subclass or the same renderer with a `mode: 'compact'` option.

### 3c. AgentActor's agentic() Override Uses Descriptor Internals

**Current state:** AgentActor.agentic() (actor.py:157) and agentic_stream() (actor.py:192) access `AgentMixin.__dict__['run'].fn` directly:

```python
run_fn = AgentMixin.__dict__['run'].fn
result = await run_fn(self, task=task, prompt=self.prompt, ...)
```

This reaches into the `fullmethod` descriptor's internal `.fn` attribute -- a pattern not used anywhere else in the codebase. It exists because AgentActor's `agentic()` has `@expose_route` and would shadow the mixin's `agentic()`, so it needs to call the engine directly.

**Problem:** Fragile coupling to descriptor internals. If `fullmethod` changes its implementation, this breaks silently.

**Proposed change (if keeping current 4-method API):** Call through the normal protocol by passing all params explicitly to `self.agentic()` on the mixin, which becomes a no-op cascade:

```python
# In AgentActor, after simplification from 1a:
@expose_route('/agentic', methods=['POST'])
async def agentic(self, task: str, **kwargs) -> str:
    tool_addrs = self.tool_addrs()
    # Call parent's agentic with all params explicit -- cascade is no-op
    result = await AgentMixin.agentic.__get__(self)(
        task=task,
        prompt=self.prompt,
        tools=tool_addrs,
        llm=kwargs.get('llm', self.llm),
        constraints={**self.constraints, **kwargs.get('constraints', {})},
        user=kwargs.get('user'),
        thread_id=kwargs.get('thread_id'),
        result_type=kwargs.get('result_type'),
    )
    return json.dumps(result, default=str)
```

This uses the normal `__get__` protocol on `fullmethod`, which is its public interface.

---

## 4. Resilience & Error Recovery

### 4a. run_stream() Catches All Exceptions But run() Does Not

**Current state:** `run_stream()` wraps its entire body in try/except and yields an error chunk (mixin.py:506-691):

```python
try:
    # ... entire streaming logic ...
    yield {'name': 'done', ...}
except Exception as e:
    yield {'name': 'error', 'data': {'message': str(e), 'code': 500}, ...}
```

`run()` has no equivalent guard (mixin.py:268-421). If the LLM call fails, the exception propagates to the caller. This asymmetry means:

- Streaming endpoints degrade gracefully (error chunk sent to client)
- Non-streaming endpoints crash with 500 (no structured error)

**Proposed change:** The asymmetry is intentional for non-streaming (callers can try/except), but `run()` should at minimum log the error consistently. The real gap is that `run()` does not handle thread update failure -- if the LLM succeeds but thread update fails (mixin.py:401-407), the result is still returned but the thread is silently stale. `run_stream()` has the same issue (mixin.py:653-661) but logs a warning.

Add structured error handling to `run()`:

```python
async def run(target, task, prompt, tools, ...):
    # ... existing setup ...
    try:
        result = await ai_agent.call(task, **run_kwargs)
    except Exception as e:
        logger.error("[%s] Agent run failed: %s", agent_addr, e)
        raise  # re-raise -- callers handle it

    # Thread update with retry
    if thread_id is not None:
        for attempt in range(2):
            update_resp = await root.request(update_tx)
            if not update_resp.is_error:
                break
            logger.warning("Thread update attempt %d failed", attempt + 1)

    return result_dict
```

### 4b. Tool Discovery Fails Silently for Missing Actors

**Current state:** `discover_tools()` (tools.py:70-71) logs a warning and skips missing actors:

```python
child = children.get(addr)
if child is None:
    logger.warning("Tool discovery: actor '%s' not found in Matrix", addr)
    continue
```

If all tool addresses are invalid, the agent runs with zero tools and likely produces a poor answer. The caller gets no signal that tools failed to resolve.

**Proposed change:** Return discovery metadata alongside specs:

```python
@dataclass
class DiscoveryResult:
    specs: list[ToolSpec]
    resolved: list[str]    # addresses that resolved successfully
    missing: list[str]     # addresses that were not found
    skipped: list[str]     # addresses skipped (self-exclusion, no schema)
```

Then in `run()`/`run_stream()`, if all requested tools are missing, yield a warning event or raise early:

```python
discovery = discover_tools(tools, root, caller_addr=agent_addr)
if tools and not discovery.specs:
    logger.error("All %d tool addresses failed to resolve: %s", len(tools), discovery.missing)
    # In streaming: yield warning chunk
    # In non-streaming: raise with actionable message
```

### 4c. No Timeout on Agent Execution

**Current state:** Neither `run()` nor `run_stream()` has a timeout. The only limit is `constraints['max_iterations']` which maps to `UsageLimits(request_limit=N)` (mixin.py:370-373). A slow LLM or a tool that hangs blocks indefinitely.

**Proposed change:** Add `timeout` to constraints:

```python
constraints = constraints or {}
timeout = constraints.get('timeout', config.AGENT_DEFAULTS.get('timeout', 300))

# In run():
result = await asyncio.wait_for(ai_agent.call(task, **run_kwargs),
                                timeout=timeout)

# In run_stream():
async with asyncio.timeout(timeout):
    async with ai_agent.iter(task, **run_kwargs) as agent_run:
# ...
```

Default 300s (5 min) is generous but prevents infinite hangs. Configurable per-model via `__agent__ = {'constraints': {'timeout': 60}}`.

---

## 5. Extensibility Without Modification

### 5a. Adding a New LLM Provider Requires Modifying _resolve_llm

**Current state:** The `ollama:` prefix is hard-coded in `_resolve_llm()` (mixin.py:92). Adding vLLM, Together, or any custom endpoint requires editing this function.

**Proposed change:** Provider registry (detailed in 2c above). Key difference from 2c: this also enables app-level registration:

```python
# In app code (e.g., main.py)
from n3tx_agents.mixin import register_provider
from pydantic_ai.models.openai import OpenAIChatModel

register_provider('vllm', lambda llm: OpenAIChatModel(
    llm.split(':', 1)[1],
    base_url='http://vllm-server:8000/v1',
))
```

### 5b. Tool Routing Is Hardcoded to Matrix Request-Response

**Current state:** `_route_tool_call()` (tools.py:201-222) always uses `Actor.root().request(tx)`. This is the correct default but prevents:

- Testing tools without a live Matrix
- Routing tools to external APIs (HTTP, MCP)
- Adding middleware to tool calls (logging, caching, rate-limiting)

**Proposed change:** Make the tool router injectable via AgentDeps:

```python
@dataclass
class AgentDeps:
    user: Optional[dict]
    agent_addr: str
    tool_router: Any = None  # callable(tx) -> TX; defaults to Matrix.request

async def _route_tool_call(ctx, target_addr, method_name, data):
    router = ctx.deps.tool_router or _default_router
    return await router(target_addr, method_name, data, ctx.deps)

async def _default_router(target_addr, method_name, data, deps):
    root = Actor.root()
    tx = TX(name=method_name, source=root.addr, target=target_addr,
            data=data, meta={'user': deps.user})
    response = await root.request(tx)
    # ...
```

For testing:

```python
async def mock_router(target, method, data, deps):
    return json.dumps({"data": [], "meta": {"total": 0}})

deps = AgentDeps(user=None, agent_addr='test', tool_router=mock_router)
```

### 5c. No Hook Points in the Agent Lifecycle

**Current state:** The agent lifecycle (resolve config -> discover tools -> build agent -> run -> return) has no hook points. If a developer wants to:

- Log every tool call (audit trail)
- Cache tool results
- Add custom system prompt sections
- Transform the result before returning

They must either override `agentic()` entirely or monkeypatch.

**Proposed change:** Add lifecycle hooks following the interceptor pattern from actors (Actor.use()):

```python
class AgentMixin:
    @fullmethod
    async def agentic(target, task, **kwargs):
        # Hook: before_run
        hooks = getattr(target, '__agent_hooks__', {})
        if 'before_run' in hooks:
            task, kwargs = await hooks['before_run'](target, task, kwargs)

        # ... existing logic ...
        result = await _run(target, ...)

        # Hook: after_run
        if 'after_run' in hooks:
            result = await hooks['after_run'](target, result)

        return result
```

Configuration:

```python
class Grant(ActorModel):
    __agent__ = True
    __agent_hooks__ = {
        'before_run': log_agent_start,
        'after_run': save_audit_trail,
    }
```

This aligns with the actor interceptor pattern (`Actor.use(fn, on='inbox')`) without requiring actor-level coupling.

---

## 6. Convention Over Configuration

### 6a. Import Ordering Trap

**Current state:** From CLAUDE.md: "n3tx_agents must be imported BEFORE any model with `__agent__ = True` is defined." This is enforced by a side-effect import in `__init__.py:17-18`:

```python
from n3tx_core.models.proto_model import register_mixin
register_mixin('__agent__', AgentMixin)
```

The veille app has a comment about this (main.py:13):

```python
# CRITICAL: Must import n3tx_agents BEFORE model imports.
import n3tx_agents  # noqa: F401, E402
```

**Problem:** Silent failure if ordering is wrong. The mixin is simply not injected, and the model works without agent capabilities. No error, no warning.

**Proposed change:** Add a validation check in `ProtoModel.__init_subclass__()`:

```python
# In proto_model.py __init_subclass__
if getattr(cls, '__agent__', False) and not issubclass(cls, _mixin_registry.get('__agent__', type)):
    import warnings
    warnings.warn(
        f"{cls.__name__} has __agent__ = True but AgentMixin is not registered. "
        f"Import n3tx_agents before defining this model.",
        RuntimeWarning,
        stacklevel=2,
    )
```

This turns a silent failure into an actionable warning. Alternatively, use lazy mixin injection (check at first use rather than at class definition).

### 6b. Agent Streaming Endpoint Boilerplate

**Current state:** Every model that wants streaming agent output writes the same pattern:

```python
@expose_route('/analyze', methods=['POST'], stream=True, access=AUTHENTICATED,
              events={...same 5 events...})
async def analyze(self, user=None):
    async for chunk in self.agentic_stream(task=..., prompt=..., user=user):
        yield chunk
```

This is repeated in:
- Grant.analyze (grant.py:87-125)
- Run.execute (run.py:214-236)
- Run.adhoc (run.py:237-254)
- AgentActor.agentic_stream (actor.py:170-204)

The pattern is: `@expose_route(stream=True, events=AGENT_EVENTS)` + `async for chunk in self.agentic_stream(): yield chunk`.

**Proposed change:** Since AgentMixin knows about streaming, it could auto-expose an `agentic_stream` endpoint when `__agent__ = True`:

```python
# In AgentMixin injection or schema_ext
if agent_flag and not hasattr(cls, 'agentic_stream_route'):
    @expose_route('/agentic_stream', methods=['POST'], stream=True,
                  events=AGENT_EVENTS, access=AUTHENTICATED)
    async def agentic_stream_route(self, task: str, user=None, **kwargs):
        async for chunk in self.agentic_stream(task=task, user=user, **kwargs):
            yield chunk
    cls.agentic_stream_route = agentic_stream_route
```

This follows the StorableMixin pattern where CRUD methods are auto-provided. Custom streaming endpoints (like Grant.analyze with its own task construction) would override this default.

### 6c. Thread Registration Requires Manual Setup

**Current state:** Thread is an ActorModel that must be explicitly registered and have its table created. No example or app code shows Thread registration -- it is only used in mixin.py via TX routing (mixin.py:328-341). If Thread is not registered, thread_id support silently fails with a "Thread not found" error.

**Proposed change:** Auto-register Thread when any model with `__agent__` and thread support is present:

```python
# In n3tx_agents/__init__.py, after register_mixin
def _ensure_thread_registered():
    from n3tx_core.utils.registrar import registered_models
    if 'threads' not in registered_models:
        # Thread auto-registers when first needed
        pass  # Thread's ActorModel auto-registration handles it via Matrix
```

Or, document this requirement prominently and have `create_app()` auto-register Thread when it detects any `__agent__` models.

---

## 7. Consistency Gaps

### 7a. AgentActor.agentic() Returns String, Mixin.agentic() Returns Dict

**Current state:**
- `AgentMixin.agentic()` returns `dict` (mixin.py:220)
- `AgentActor.agentic()` returns `str` via `json.dumps()` (actor.py:168)

From agent-actor.md:149: "agentic() returns a JSON string, not a dict. This is because it is decorated with @expose_route."

But `@expose_route` handles dict returns fine -- the framework serializes them. The `json.dumps()` is defensive but means API callers get a double-serialized JSON string, and in-code callers must `json.loads()` the result.

**Proposed change:** Return dict from AgentActor.agentic(), let the route layer serialize:

```python
@expose_route('/agentic', methods=['POST'])
async def agentic(self, task: str, **kwargs) -> dict:
    # ... existing logic ...
    return result  # dict, not json.dumps(result)
```

This is consistent with how every other `@expose_route` method works in the codebase.

### 7b. NTTStreamAgent Imports Differ from NTTAgentLive

**Current state:**
- NTTStreamAgent imports `NTTStream` from `'./ntx-stream.js'` (ntx-stream-agent.js:1)
- NTTAgentLive imports `NTTStream` from `'./ntx-stream.js'` (ntx-agent-live.js:17) but also imports `NTT` from `'../core/NTT.js'` and `renderJson` from `'../widgets/JsonTree.js'`

NTTStreamAgent uses `this.#esc()` (DOM-based escaping) for tool args display. NTTAgentLive uses `renderJson()` for the same purpose. Same data, different rendering.

**Proposed change:** NTTStreamAgent should use `renderJson` when available (progressive enhancement):

```javascript
TOOL_CALL(data, meta) {
    // ...
    const argsHtml = data.args && Object.keys(data.args).length
        ? `<div class="tool-json">${typeof renderJson === 'function'
            ? renderJson(data.args) : this.#esc(JSON.stringify(data.args, null, 2))}</div>`
        : '';
    // ...
}
```

But this is minor -- the real fix is the shared renderer from 3b.

### 7c. Mixin Pattern Divergence from StorableMixin

**Current state:** StorableMixin (storable_mixin.py) injects class methods (`create`, `list`, `get`, `update`, `delete`) that are standard Python classmethods. AgentMixin (mixin.py) injects `@fullmethod` descriptors that work on both classes and instances.

This divergence exists for a good reason -- agent methods genuinely need dual dispatch (class-level context vs instance-level context). But it means:

- StorableMixin methods: `Product.create(data)`, `Product.list()`
- AgentMixin methods: `Product.agentic(task='...')`, `product.agentic(task='...')`

The difference is architecturally justified. No change needed, but it should be explicitly documented as a deliberate divergence, not an oversight.

### 7d. CSS Variables Are Inconsistent Across Agent Components

**Current state:** The three frontend components use slightly different CSS variable fallbacks:

| Variable | NTTStreamAgent | NTTAgentLive | NTTChat |
|----------|---------------|--------------|---------|
| `--thinking` | `#a78bfa` | `#a78bfa` | n/a |
| `--text-accent` | `#38bdf8` | `#38bdf8` | n/a |
| `--surface-1` | `#1a1a2e` | `#1a1a2e` | `#1a1a2e` |
| Tool border | `--warning, #f59e0b` | `--warning, #f59e0b` | `--accent, #4cc9f0` |

NTTChat uses `--accent` for tool card borders while the others use `--warning`. This creates visual inconsistency when the same agent task is viewed in different components.

**Proposed change:** Extract shared agent CSS tokens:

```css
/* agent-tokens.css or as part of theme */
--agent-thinking: var(--thinking, #a78bfa);
--agent-tool-active: var(--warning, #f59e0b);
--agent-tool-done: var(--success, #22c55e);
--agent-text-accent: var(--text-accent, #38bdf8);
```

All three components reference these tokens. Single point of theming.

---

## 8. Propositions Summary Table

| # | Proposition | Simplifies | Impact | Effort | Risk | Dependencies |
|---|-------------|-----------|--------|--------|------|-------------|
| 1a | Merge run/agentic into 2 methods | Mental model: 6 -> 4 methods | **High** | Medium | Medium (AgentActor override) | None |
| 1b | Thread context manager | Eliminates 40-line duplication | Medium | Low | Low | None |
| 2a | Make `llm` explicit param | Interface clarity | Low | Low | None | None |
| 2b | Enrich AgentDeps with root | Remove repeated lookups | Low | Low | None | None |
| 2c | Provider registry for LLM resolution | Extensibility | **High** | Low | Low | None |
| 3a | Export AGENT_EVENTS constant | Remove boilerplate at every usage site | **High** | **Very Low** | None | None |
| 3b | Shared AgentStreamRenderer | Remove ~400 lines of frontend duplication | **High** | Medium | Low | None |
| 3c | Remove descriptor .fn access hack | Clean AgentActor -> Mixin interface | Medium | Low | Low | Blocked by 1a |
| 4a | Symmetric error handling run/run_stream | Consistent resilience | Medium | Low | None | None |
| 4b | Return DiscoveryResult from discover_tools | Actionable diagnostics | Medium | Low | Low | None |
| 4c | Agent execution timeout | Prevent infinite hangs | **High** | Low | Low | None |
| 5a | Provider registry (see 2c) | Additive LLM support | **High** | Low | Low | Same as 2c |
| 5b | Injectable tool router via deps | Testability + routing flexibility | Medium | Medium | Low | 2b |
| 5c | Agent lifecycle hooks | Extension without modification | Medium | Medium | Medium | None |
| 6a | Validate __agent__ mixin injection | Prevent silent failures | **High** | **Very Low** | None | None |
| 6b | Auto-expose agentic_stream endpoint | Convention over config | Medium | Medium | Medium | 3a |
| 6c | Auto-register Thread model | Convention over config | Low | Low | Low | None |
| 7a | AgentActor.agentic returns dict | Consistency with all other routes | Medium | **Very Low** | Low | None |
| 7b | Unified tool args rendering | Visual consistency | Low | Low | None | 3b |
| 7c | Document fullmethod vs classmethod divergence | Clarity | Low | **Very Low** | None | None |
| 7d | Shared agent CSS tokens | Visual consistency | Low | Low | None | 3b |

### Recommended Implementation Order

**Wave 1 -- Quick wins (1-2 days, zero risk):**
1. **3a** Export AGENT_EVENTS constant
2. **6a** Validate __agent__ mixin injection
3. **7a** AgentActor.agentic returns dict
4. **2a** Make `llm` explicit param
5. **7c** Document the fullmethod/classmethod divergence

**Wave 2 -- Medium effort, high impact (3-5 days):**
6. **2c/5a** Provider registry for LLM resolution
7. **4c** Agent execution timeout
8. **1b** Thread context manager
9. **4b** DiscoveryResult from discover_tools

**Wave 3 -- Architectural (1-2 weeks):**
10. **3b** Shared AgentStreamRenderer (frontend)
11. **1a** Merge run/agentic (enables 3c)
12. **3c** Clean AgentActor -> Mixin interface
13. **5b** Injectable tool router

**Wave 4 -- Extension patterns (when needed):**
14. **5c** Agent lifecycle hooks
15. **6b** Auto-expose agentic_stream endpoint
16. **6c** Auto-register Thread model

### Critical Path

```
3a (AGENT_EVENTS) ──────────────────────> 6b (auto-expose endpoint)
                                            |
1a (merge run/agentic) ──> 3c (clean AgentActor override)
                                            |
2b (enrich AgentDeps) ───> 5b (injectable tool router)
                                            |
3b (shared renderer) ────> 7b (unified rendering) + 7d (CSS tokens)
```

3a and 6a are independent and can ship immediately. 1a is the most impactful single change but requires careful migration of AgentActor's override pattern.
