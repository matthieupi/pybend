# Agents -- Deep Audit Report

**Audit date**: 2026-03-26
**Branch**: v0.9 (commit `779137c`)
**Scope**: `packages/n3tx-agents/` -- all Python backend, JS frontend, tests, docs, and application usage sites
**Synthesized from**: 01-architecture, 02-api-contracts, 03-quality-risks, 04-extensibility, 05-improvements

---

## Executive Summary

The N3TX agents subsystem delivers on the project's core promise: add `__agent__ = True` to any model and get LLM-powered reasoning with zero boilerplate. The architecture is sound -- mixin injection mirrors StorableMixin, tool discovery derives from schemas, tool calls route through the actor system preserving auth and interceptors, and the frontend component hierarchy provides a clean override surface via UPPERCASE handlers. The subsystem is well-aligned with the "model is the app" philosophy and the "zero to working, then customize" design principle.

The most significant risks are at the boundaries, not in the core design. The streaming implementation depends on pydantic-ai's private `_agent_graph` API, which could break without notice on a version bump. The `_resolve_tool_addrs()` batch fetch in AgentActor likely ignores its `ids` filter, silently returning too many tools. And the three frontend streaming components (`NTTStreamAgent`, `NTTAgentLive`, `NTTChat`) share ~70% identical handler code without sharing an implementation, meaning bug fixes must be manually propagated across all three.

**Top 3 recommendations (fix now):**
1. Fix `_resolve_tool_addrs()` batch fetch (`actor.py:129`) -- the `ids` parameter is likely ignored by `StorableMixin.list()`, producing incorrect tool resolution for AgentActor instances with multiple href-referenced tools.
2. Add a runtime warning when `__agent__ = True` models are defined before `import n3tx_agents` -- this silent failure is the #1 developer trap and costs zero effort to detect.
3. Export `AGENT_EVENTS` from `__init__.py` -- every streaming endpoint repeats the same five-event import and dict construction. One constant eliminates the boilerplate.

**Top 3 strategic investments:**
1. Extract a shared `AgentStreamRenderer` to eliminate ~400 lines of duplicated frontend rendering logic across the three streaming components. This reduces maintenance burden and ensures consistent behavior.
2. Introduce a provider registry for LLM resolution, replacing the hardcoded `ollama:` prefix handler. This unlocks self-hosted endpoints (vLLM, Together) without framework modification.
3. Merge the four-method public API (`agentic`/`run`/`agentic_stream`/`run_stream`) into two methods, making `run` and `run_stream` internal. This reduces cognitive load, eliminates the `fullmethod` descriptor bypass hack in AgentActor, and unifies the return type contract.

---

## Component Overview

### Python Backend (8 modules)

```
n3tx_agents/
  __init__.py          register_mixin('__agent__', AgentMixin), re-exports, schema_ext side-effect
  mixin.py             AgentMixin: ctx, tools, agentic, run, agentic_stream, run_stream
  actor.py             AgentActor (concrete ActorModel) + 5 stream event ProtoModels
  tools.py             discover_tools, create_tool_function, make_tool, _route_tool_call
  deps.py              AgentDeps dataclass (user, agent_addr)
  thread.py            Thread ActorModel + to_history/from_history converters
  tool_model.py        AgentTool model (target addr + description)
  schema_ext.py        Schema pipeline: 'agent' stage (default) + 'base'/'clean' stages (LLM)
```

### JavaScript Frontend (4 components)

```
static/components/
  ntx-stream-agent.js  NTTStreamAgent: rich agent output (thinking, tools, markdown)
  ntx-agent-live.js    NTTAgentLive: standalone panel with input + structured log
  ntx-chat.js          NTTChat: floating chat widget with instance selector
  ntx-agent.js         NtxAgent: multi-size entity renderer for AgentActor instances
```

### Internal Dependency Graph

```
                     +------------------+
                     |   pydantic-ai    |
                     | (external lib)   |
                     +--------+---------+
                              |  Agent, Tool, UsageLimits
                              |  _agent_graph (PRIVATE)
                              |  messages.*
                              |
+---------------+   +---------v---------+   +----------------+
|   n3tx-core   |<--+   n3tx-agents     +-->|  n3tx-actors   |
|               |   |                   |   |                |
| ProtoModel    |   | AgentMixin        |   | Actor, Matrix  |
| proto_schema  |   | AgentActor        |   | TX             |
| StorableMixin |   | Thread, AgentTool |   | ActorModel     |
| config        |   | tools/deps        |   |                |
| descriptors   |   | schema_ext        |   |                |
+---------------+   +---+---+-----------+   +----------------+
                        |   |
              +---------+   +---------+
              v                       v
    +------------------+    +------------------+
    |  n3tx-ui (JS)    |    |  Application     |
    |                  |    |  (veille, grants) |
    | NTTStream (base) |    |                  |
    | NTTItem (base)   |    | __agent__ = True |
    +------------------+    | NTTStreamAgent   |
                            |   subclasses     |
                            +------------------+
```

### Data Flow: Agent Execution

```
HTTP/API  ->  agentic(task)  ->  [config cascade]  ->  run(task, prompt, tools, ...)
                                                           |
                 +-- _resolve_llm() --------+              |
                 +-- discover_tools(addrs) --+--- cls.schema() per addr
                 +-- ThreadContext: TX get ---+--- root.request(tx)
                 |                           |
                 +-- pydantic_ai.Agent(llm, tools, prompt)
                 |       |
                 |       +-- agent.run(task) / agent.iter(task)
                 |       |       |
                 |       |       +-- [LLM calls tool] -> _route_tool_call()
                 |       |       |       TX(name, target, data, meta) -> Matrix
                 |       |       |       <- TX response (or ModelRetry on error)
                 |       |       |
                 |       |       +-- [LLM returns answer]
                 |       |
                 +-- ThreadContext: TX update
                 |
                 +-- return {answer, usage, messages, message_count, ?thread_id}
```

---

## Key Findings

### Critical Issues

**F1. `_resolve_tool_addrs()` batch fetch likely broken**
- **Evidence**: `actor.py:129` -- `tool_cls.list(ids=href_ids)`. `StorableMixin.list()` accepts `limit`, `offset`, and filter kwargs but not `ids` as a batch-fetch parameter. The `ids` parameter is silently ignored, returning all records instead of the requested subset.
- **Severity**: High
- **Recommendation**: Replace with individual `tool_cls.get(id=href_id)` calls or implement a `list(ids=[...])` filter in StorableMixin. The test at `test_agent_actor.py:147-162` only uses one href, masking the bug.

**F2. `stream_run` vs `run_stream` name mismatch in tool exclusion**
- **Evidence**: `tools.py:96` -- `agent_methods = {'run', 'stream_run'}`. The actual method name is `run_stream`, not `stream_run`. If `run_stream` were exposed via `@expose_route` on an AgentActor subclass, it would not be excluded from tool discovery.
- **Severity**: High (latent -- currently unexploited because `run_stream` is not decorated with `@expose_route`)
- **Recommendation**: Change to `agent_methods = {'run', 'run_stream'}`. Update `agent-actor.md:159` which uses the same wrong name.

**F3. XSS via `marked.parse()` on unsanitized LLM output**
- **Evidence**: `ntx-stream-agent.js:214` and `ntx-agent-live.js:268` -- `content.innerHTML = marked.parse(buf)`. LLM output passes through markdown-to-HTML conversion and is injected via `innerHTML`. If the LLM generates `<img onerror="...">`, the handler executes in the main context.
- **Severity**: High
- **Recommendation**: Configure `marked` with `{sanitize: true}` or use DOMPurify as a post-processing step. Shadow DOM provides partial isolation but event handlers (`onerror`, `onload`) still fire.

**F4. `agentic_stream()` class-level call creates invalid instance**
- **Evidence**: `mixin.py:444-447` -- `if isinstance(target, type): instance = target()`. Creates a default instance with no meaningful field values. If the model has required fields without defaults (e.g., `name: str = Field(min_length=1)`), this raises a Pydantic validation error.
- **Severity**: Medium
- **Recommendation**: Follow the same pattern as `agentic()` (line 220), which calls `target.run()` directly on the class without forced instantiation. Or document that class-level streaming requires all fields to have defaults.

**F5. `messages` field serialization in AgentActor.agentic() produces garbage**
- **Evidence**: `actor.py:168` -- `json.dumps(result, default=str)`. The `messages` list contains pydantic-ai `ModelMessage` objects, which `str()` serializes into Python repr strings (e.g., `"ModelRequest(parts=[...])"`) rather than useful JSON. HTTP callers receive an essentially unusable `messages` field.
- **Severity**: Medium
- **Recommendation**: Either serialize messages through `Thread.from_history()` before `json.dumps`, or exclude `messages` from the HTTP response (it is already persisted in the Thread).

**F6. Silent mixin injection failure on import misordering**
- **Evidence**: `__init__.py:17-18` calls `register_mixin('__agent__', AgentMixin)`. If any model with `__agent__ = True` is defined before this line executes, the mixin is never injected. No error, no warning. The model simply lacks agent methods. Confirmed in `apps/veille/main.py:13` which has an explicit "CRITICAL" comment about this.
- **Severity**: Medium (developer experience -- silent failure)
- **Recommendation**: Add a validation check in `ProtoModel.__init_subclass__()` that emits `RuntimeWarning` when `__agent__` is set but AgentMixin is not in the class MRO.

**F7. Thread update failure is silently swallowed**
- **Evidence**: `mixin.py:401-407` and `mixin.py:655-661` -- thread update failures are logged as warnings but the result dict still includes `thread_id`, implying success. The user believes their conversation was saved when it was not.
- **Severity**: Medium
- **Recommendation**: Include a `thread_updated: bool` flag in the result dict. In streaming, emit a warning event when the thread update fails.

### Design Strengths

**S1. Mixin injection pattern is consistent with StorableMixin.**
`__agent__ = True` mirrors `__storable__ = True`. The mixin registry in `proto_model._mixin_registry` provides a single, well-understood injection mechanism. One flag, full capability. Evidence: `__init__.py:18`, `proto_model.py:112-119`.

**S2. Tool calls route through Matrix, preserving the full actor lifecycle.**
`_route_tool_call()` at `tools.py:201-222` creates TX messages that flow through the actor system. This means auth interceptors, logging, and protocol adapters all apply to agent tool calls, not just HTTP requests. The `ModelRetry` raise on error TX at `tools.py:221` gracefully tells the LLM to try a different approach.

**S3. The 3-tier config cascade is intuitive and well-designed.**
`config.AGENT_DEFAULTS < __agent__ dict < call kwargs` at `mixin.py:237-265`. The `'tools' in kwargs` presence check (not truthiness check) correctly distinguishes "no tools" from "auto-discover." Evidence: `mixin.py:244`.

**S4. Stream chunk format is a clean, consistent protocol.**
All chunks follow `{name, data, meta}` with `meta.seq` for ordering and `meta.stream_end` for termination. Six event types with fixed shapes. Evidence: `mixin.py:472-478`, verified in tests.

**S5. Frontend UPPERCASE handler dispatch is elegant and extensible.**
`NTTStream.STREAM()` at `ntx-stream.js:22-35` normalizes event names to uppercase and calls `this[name]()`. New event types are automatically dispatched without base class changes. App-specific handlers (e.g., `SOURCE_START()`, `GRANT_FOUND()` in `ntx-run-output.js`) compose naturally.

**S6. No shared mutable state between agent runs.**
Each `run()`/`run_stream()` call creates a fresh pydantic-ai Agent, fresh tool functions, and fresh AgentDeps. Request-scoped isolation means concurrent agent runs cannot interfere. Evidence: `mixin.py:352-366` (state creation per call).

**S7. Auth propagation chain is complete and traceable.**
HTTP JWT -> `user` param -> `agentic_stream(user=)` -> `AgentDeps(user=)` -> `_route_tool_call(meta={'user': ctx.deps.user})` -> target actor handler. No auth information is lost. Evidence: `tools.py:213-215`.

### Design Trade-offs

**T1. Deep coupling to pydantic-ai internals for streaming.**
The streaming path imports from `pydantic_ai._agent_graph` (private module) at `mixin.py:47-55`. This enables fine-grained event dispatch (tool starts, thinking deltas, text deltas) that the public API does not expose. **Gained**: rich streaming events that power the structured frontend rendering. **Sacrificed**: stability across pydantic-ai version bumps. **Still valid?** Yes, until pydantic-ai stabilizes its streaming API. The non-streaming path (`agent.run()`) uses only public API.

**T2. Tool functions are regenerated on every invocation.**
`discover_tools()` + `create_tool_function()` + `make_tool()` run on every `run()`/`run_stream()` call. No caching. **Gained**: tools always reflect current actor state; no cache invalidation bugs. **Sacrificed**: microseconds of latency per call (schema is cached; exec is fast). **Still valid?** Yes at current scale. Would need caching if agents are invoked at high frequency (>100/sec).

**T3. AgentMixin vs AgentActor dual nature.**
Code-driven agents (mixin, ClassVar config) and data-driven agents (AgentActor, DB fields) share the same method names but have different config resolution, return types, and override patterns. **Gained**: flexibility for both use cases. **Sacrificed**: substitutability -- `AgentActor.agentic()` returns `str` while `AgentMixin.agentic()` returns `dict`. **Still valid?** The dual nature is architecturally justified, but the return type inconsistency should be fixed (see F5 and P-S1).

**T4. Thread messages stored as single JSON blob.**
`Thread.messages` is a `list` field serialized to JSON TEXT. **Gained**: simplicity -- no separate messages table, no join queries. **Sacrificed**: performance on long conversations (full rewrite on every turn), no message-level indexing or pagination. **Still valid?** Yes for current usage (single-digit to low-double-digit message counts). Would need migration to append-only storage if conversations regularly exceed ~100 messages.

### Improvement Opportunities

| # | Improvement | Impact | Effort | Category |
|---|-------------|--------|--------|----------|
| 1 | Export `AGENT_EVENTS` constant from `__init__.py` | High | Very Low | Boilerplate reduction |
| 2 | Add `RuntimeWarning` for misordered `__agent__` import | High | Very Low | Developer experience |
| 3 | Fix `stream_run` -> `run_stream` in tool exclusion set | High | Very Low | Bug fix |
| 4 | Fix `_resolve_tool_addrs()` batch fetch | High | Low | Bug fix |
| 5 | AgentActor.agentic() returns dict (not str) | Medium | Very Low | Consistency |
| 6 | Add `logger.exception()` in `run_stream()` error handler | Medium | Very Low | Observability |
| 7 | Provider registry for `_resolve_llm()` | High | Low | Extensibility |
| 8 | Agent execution timeout via constraints | High | Low | Resilience |
| 9 | Thread context manager to deduplicate lifecycle | Medium | Low | Code quality |
| 10 | Shared AgentStreamRenderer (frontend) | High | Medium | Code quality |
| 11 | Merge `run`/`run_stream` into private `_run`/`_run_stream` | High | Medium | API simplification |
| 12 | Make `llm` an explicit parameter (remove `**kwargs`) | Low | Very Low | Interface clarity |
| 13 | Sanitize `marked.parse()` output with DOMPurify | High | Low | Security |
| 14 | Add `thread_updated: bool` to result dict | Medium | Very Low | Correctness |
| 15 | Stream event models re-exported from `__init__.py` | Low | Very Low | Discoverability |

---

## Strategic Propositions

### Simplification Propositions

**P-S1. Merge the four-method API into two public methods**

- **Current state**: AgentMixin exposes 6 public methods: `ctx`, `tools`, `agentic`, `run`, `agentic_stream`, `run_stream`. The `run`/`run_stream` pair is the "engine" that `agentic`/`agentic_stream` delegates to. AgentActor bypasses `agentic()` entirely via `AgentMixin.__dict__['run'].fn` descriptor hack at `actor.py:157`.
- **Proposed change**: Make `run()` and `run_stream()` private (`_run`, `_run_stream`). The public API becomes `ctx`, `tools`, `agentic`, `agentic_stream`. Config resolution in `agentic()` fills in any missing params before calling `_run()`. When all params are explicit (as AgentActor does), the cascade is a no-op.

```python
# Proposed AgentMixin (simplified)
class AgentMixin:
    @fullmethod
    async def agentic(target, task: str, **kwargs) -> dict:
        prompt = kwargs.get('prompt') or target.ctx()
        tools = kwargs['tools'] if 'tools' in kwargs else target.tools()
        llm = kwargs.get('llm') or _resolve_from_config(target)
        return await _run(target, task=task, prompt=prompt, tools=tools,
                          llm=llm, ...)


# AgentActor no longer needs descriptor hack
@expose_route('/agentic', methods=['POST'])
async def agentic(self, task: str, **kwargs) -> dict:
    tool_addrs = self.tool_addrs()
    return await super().agentic(
        task=task, prompt=self.prompt, tools=tool_addrs,
        llm=kwargs.get('llm', self.llm), ...
    )
```

- **What gets simpler**: API surface shrinks from 6 to 4 methods. The descriptor `.fn` access hack is eliminated. Return type is consistently `dict` across mixin and actor.
- **Migration path**: (1) Rename `run` -> `_run` and `run_stream` -> `_run_stream`. (2) Move config cascade logic from `agentic()`/`agentic_stream()` into a shared `_resolve_config()` helper. (3) Update AgentActor to call `super().agentic()` with explicit params. (4) Update tests that call `run()` directly.
- **Risk**: Medium. Tests and AgentActor use `run()` directly. Must update all call sites. No external consumers (run is documented as internal-use).

**P-S2. Extract thread lifecycle into a context manager**

- **Current state**: Thread read-before/update-after logic is duplicated between `run()` (`mixin.py:326-408`) and `run_stream()` (`mixin.py:507-661`). ~40 lines duplicated, any change must be made in two places.
- **Proposed change**:

```python
class ThreadContext:
    def __init__(self, thread_id, root, user=None, agent_addr=''):
        self.thread_id = thread_id
        self.root = root
        self.message_history = None

    async def __aenter__(self):
        if not self.thread_id:
            return self
        tx = TX(name='get', source=self.root.addr, target='threads',
                data={'id': self.thread_id}, meta={'user': self.user} if self.user else {})
        resp = await self.root.request(tx)
        if resp.is_error:
            raise RuntimeError(f"Thread {self.thread_id} not found: {resp.data.get('message')}")
        self.message_history = Thread.to_history(resp.data.get('messages', []))
        return self

    async def update(self, all_messages):
        if not self.thread_id:
            return True
        tx = TX(name='update', ...)
        resp = await self.root.request(tx)
        if resp.is_error:
            logger.warning("Failed to update thread %s", self.thread_id)
            return False
        return True

    async def __aexit__(self, *exc):
        pass
```

- **What gets simpler**: Single source of truth for thread lifecycle. Both `_run` and `_run_stream` shrink by ~20 lines.
- **Migration path**: Extract ThreadContext, replace inline code in both methods. Non-breaking.
- **Risk**: Low. Thread logic is self-contained.

### Composability & Extensibility Propositions

**P-C1. Provider registry for LLM resolution**

- **Current friction**: Adding a custom LLM endpoint (vLLM, Together, local inference) requires modifying `_resolve_llm()` at `mixin.py:76-102`. It is a module-level function, not overridable.
- **Proposed design**:

```python
# mixin.py (or new providers.py)
_PROVIDER_RESOLVERS = {}

def register_provider(prefix: str, resolver):
    _PROVIDER_RESOLVERS[prefix] = resolver

def _resolve_llm(llm):
    if not llm:
        raise ValueError("No LLM provided. Pass an llm= argument, ...")
    if not isinstance(llm, str):
        return llm  # already a model instance
    prefix = llm.split(':', 1)[0] if ':' in llm else None
    if prefix and prefix in _PROVIDER_RESOLVERS:
        return _PROVIDER_RESOLVERS[prefix](llm)
    return llm  # pass through to pydantic-ai native resolution

# Default registration
register_provider('ollama', lambda llm: OpenAIChatModel(
    llm.split(':', 1)[1],
    provider=OllamaProvider(base_url=config.OLLAMA_BASE_URL.rstrip('/') + '/v1'),
))
```

```python
# Application code (main.py)
from n3tx_agents.mixin import register_provider
register_provider('vllm', lambda llm: OpenAIChatModel(
    llm.split(':', 1)[1], base_url='http://vllm:8000/v1'))
```

- **What it enables**: Self-hosted inference endpoints, custom API gateways, provider-specific configuration -- all without framework modification.
- **Effort estimate**: Small (1-2 hours). Non-breaking migration.

**P-C2. Export AGENT_EVENTS constant and add to `__all__`**

- **Current friction**: Every streaming agent endpoint repeats the same import and dict construction (`from n3tx_agents.actor import TextChunk, ToolCallEvent, ...` + `events={...}`). Seen in `grant.py:6-8,87`, `run.py:11-13,214`, `actor.py:170-174`.
- **Proposed design**:

```python
# n3tx_agents/__init__.py
from .actor import TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk

AGENT_EVENTS = {
    'text': TextChunk, 'tool_call': ToolCallEvent,
    'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
    'done': DoneChunk,
}

# Usage in application code
from n3tx_agents import AGENT_EVENTS

@expose_route('/analyze', methods=['POST'], stream=True, events=AGENT_EVENTS)
async def analyze(self, user=None):
    async for chunk in self.agentic_stream(task=..., user=user):
        yield chunk

# Composing with app-specific events
@expose_route('/execute', stream=True, events={**AGENT_EVENTS,
    'source_start': SourceStartEvent, 'grant_found': GrantFoundEvent})
```

- **What it enables**: One import replaces five. App-specific events compose via dict spread. Stream event models become discoverable through `__init__.py`.
- **Effort estimate**: Small (30 minutes). Non-breaking.

**P-C3. Shared AgentStreamRenderer for frontend components**

- **Current friction**: `NTTStreamAgent` (353 lines), `NTTAgentLive` (454 lines), and `NTTChat` (377 lines) share ~70% identical handler and rendering logic. `NTTAgentLive` extends `NTTStream` directly instead of `NTTStreamAgent`, duplicating `THINKING()`, `TOOL_CALL()`, `TEXT()`, `DONE()`, `#setThinking()`, `#scheduleRender()`, `#renderMd()`, `#flushRender()`, `#addEntry()`, `#esc()`, and ~120 lines of CSS.
- **Proposed design**:

```javascript
// agent-stream-renderer.js -- shared rendering logic
export class AgentStreamRenderer {
    #toolCards = new Map();
    #textBuf = ''; #textRendered = 0; #textTimer = null;
    #thinkBuf = ''; #thinkRendered = 0; #thinkTimer = null;

    constructor(getOutput) { this.getOutput = getOutput; }

    handleThinking(data) { /* single implementation */ }
    handleToolCall(data)  { /* single implementation */ }
    handleToolResult(data){ /* single implementation */ }
    handleText(data)      { /* single implementation */ }
    handleDone(data)      { /* single implementation */ }
    reset()   { /* clear buffers, timers */ }
    flush()   { /* force-render pending */ }
    dispose() { /* clear timers */ }
}

// Components delegate
class NTTStreamAgent extends NTTStream {
    #renderer;
    connectedCallback() {
        super.connectedCallback();
        this.#renderer = new AgentStreamRenderer(() => this.#outputEl);
    }
    THINKING(data) { this.#renderer.handleThinking(data); }
    TEXT(data)     { this.#renderer.handleText(data); }
    // ...
    disconnectedCallback() { this.#renderer.dispose(); super.disconnectedCallback(); }
}
```

- **What it enables**: Single source of truth for rendering logic. Bug fixes apply once. NTTChat can use a compact rendering mode. Shared CSS tokens (`--agent-thinking`, `--agent-tool-active`) ensure visual consistency.
- **Effort estimate**: Medium (1-2 days). Must extract, test, and update all three components.

### Resilience Propositions

**P-R1. Agent execution timeout**

- **Current failure mode**: Neither `run()` nor `run_stream()` has a wall-clock timeout. A slow LLM or a hanging tool call blocks indefinitely. `constraints['max_iterations']` only limits LLM requests, not elapsed time or individual tool call duration.
- **Proposed improvement**:

```python
# In _run():
timeout = constraints.get('timeout', config.AGENT_DEFAULTS.get('timeout', 300))
try:
    result = await asyncio.wait_for(ai_agent.call(task, **run_kwargs),
                                    timeout=timeout)
except asyncio.TimeoutError:
    raise RuntimeError(f"Agent execution timed out after {timeout}s")

# In _run_stream():
async with asyncio.timeout(timeout):
    async with ai_agent.iter(task, **run_kwargs) as agent_run:
        ...  # existing streaming logic
```

- **Blast radius reduction**: Without timeout, a single hung tool call blocks the agent indefinitely. With timeout, the agent fails cleanly after a configurable duration. The error propagates normally (exception in `run()`, error chunk in `run_stream()`). Configurable per-model via `__agent__ = {'constraints': {'timeout': 60}}`.

**P-R2. Structured tool discovery results**

- **Current failure mode**: `discover_tools()` at `tools.py:70-71` silently skips missing actors with a log warning. If all tool addresses are invalid, the agent runs with zero tools and produces a poor answer. The caller has no signal that tool resolution failed.
- **Proposed improvement**:

```python
@dataclass
class DiscoveryResult:
    specs: list[ToolSpec]
    resolved: list[str]    # addresses that resolved
    missing: list[str]     # addresses not found
    skipped: list[str]     # self-exclusion, no schema

# In _run() / _run_stream():
discovery = discover_tools(tools, root, caller_addr=agent_addr)
if tools and not discovery.specs:
    msg = f"All {len(tools)} tool addresses failed: {discovery.missing}"
    logger.error(msg)
    raise RuntimeError(msg)  # or yield warning chunk in streaming
```

- **Blast radius reduction**: Silent tool loss becomes an explicit error or warning. The agent either fails fast with an actionable message or the developer can inspect `discovery.missing` in logs.

**P-R3. Agent-to-agent recursion depth limit**

- **Current failure mode**: Agent A can discover Agent B as a tool, and Agent B can discover Agent A. The self-exclusion at `tools.py:65-66` only prevents an agent from discovering itself, not A -> B -> A cycles. The `max_iterations` constraint limits LLM requests per agent but not the total call depth. Result: potential stack overflow or resource exhaustion.
- **Proposed improvement**: Add a `depth` counter to AgentDeps, checked at the start of `_run()`:

```python
@dataclass
class AgentDeps:
    user: Optional[dict]
    agent_addr: str
    depth: int = 0
    max_depth: int = 3

# In _run():
if deps.depth >= deps.max_depth:
    raise RuntimeError(f"Agent call depth limit ({deps.max_depth}) exceeded")
# When creating deps for nested calls, increment depth
```

- **Blast radius reduction**: Prevents unbounded recursion. Default depth limit of 3 is generous for orchestration patterns while catching accidental loops.

### Proposition Priority Matrix

| # | Proposition | Simplifies | Impact | Effort | Risk | Enables | Dependencies |
|---|-------------|-----------|--------|--------|------|---------|-------------|
| P-C2 | Export AGENT_EVENTS | Boilerplate | **High** | Very Low | None | Auto-expose endpoint | -- |
| F6 | Import ordering warning | Dev experience | **High** | Very Low | None | -- | -- |
| F2 | Fix stream_run -> run_stream | Correctness | **High** | Very Low | None | -- | -- |
| F5 | AgentActor.agentic returns dict | Consistency | Medium | Very Low | Low | -- | -- |
| F1 | Fix batch tool fetch | Correctness | **High** | Low | Low | -- | -- |
| P-R1 | Execution timeout | Resilience | **High** | Low | Low | -- | -- |
| P-C1 | Provider registry | Extensibility | **High** | Low | Low | Custom endpoints | -- |
| F3 | Sanitize marked.parse | Security | **High** | Low | None | -- | -- |
| P-S2 | Thread context manager | Code quality | Medium | Low | Low | -- | -- |
| P-R2 | DiscoveryResult | Diagnostics | Medium | Low | Low | -- | -- |
| P-S1 | Merge 4-method -> 2-method | Mental model | **High** | Medium | Medium | P-C3 cleaner | -- |
| P-C3 | AgentStreamRenderer | Code quality | **High** | Medium | Low | CSS tokens | -- |
| P-R3 | Recursion depth limit | Resilience | Medium | Low | Low | Multi-agent | -- |

**Quick wins** (ship in 1-2 days): P-C2, F6, F2, F5, F3. Zero risk, high collective impact.

**Strategic investments** (1-2 weeks, unlocks future work): P-S1 simplifies the API surface and eliminates the descriptor hack, making P-C3 and future AgentActor changes cleaner. P-C1 unlocks self-hosted LLM endpoints. P-C3 eliminates ~400 lines of frontend duplication.

**Dependency chain**: P-S1 (merge methods) enables cleaner P-C3 (AgentActor no longer needs descriptor bypass). P-C2 (AGENT_EVENTS) is a prerequisite for auto-exposing streaming endpoints. P-R1 (timeout) and P-R2 (discovery results) are independent and can ship anytime.

---

## Downstream Use Guide

### For Bug Hunting

**Risk areas ranked by probability:**

1. **`actor.py:128-132`** -- `_resolve_tool_addrs()` batch fetch. The `list(ids=href_ids)` call likely ignores the filter. Test with an AgentActor that has 3+ href-referenced AgentTools and verify only those tools are returned.

2. **`tools.py:96`** -- `stream_run` vs `run_stream` exclusion. Currently latent. Would manifest if anyone adds `@expose_route` to `run_stream` on an AgentActor subclass.

3. **`mixin.py:444-447`** -- Class-level `agentic_stream()` on models with required fields. Test: define a model with `name: str = Field(min_length=1)` and call `MyModel.agentic_stream(task='test')`.

4. **`tools.py:219-221`** -- `_route_tool_call()` assumes `response.data` is a dict. If an actor returns a string error, `.get('message')` raises `AttributeError`.

5. **Frontend timer conflicts** -- `ntx-stream-agent.js:126-131`. Rapidly invoking `callMethod()` while a previous stream is active could cause old events to write into newly cleared state. Test: click a stream button twice in rapid succession.

6. **`ntx-chat.js:135`** -- `innerHTML +=` re-parses the entire card DOM on every tool result. Destroys event listeners and can corrupt existing card content (e.g., spinner animations freeze).

7. **`mixin.py:685-691`** -- `run_stream()` error handler catches all exceptions but does not log them. Errors are silently converted to stream events with no backend trace. Add `logger.exception()` before the yield.

**Untested edge cases:**

- `_resolve_llm()` with empty string `''`, `0`, `False` (non-None falsy values)
- `result_type` parameter in `run()` or `agentic()` (code path at `mixin.py:357-358` is completely untested)
- `agentic_stream()` with `thread_id` (only `run_stream` + thread is tested)
- `constraints.max_iterations` actually limiting the LLM (tests pass constraints but never verify enforcement)
- Thread access control: user A cannot read user B's thread
- Concurrent `run()` calls with the same `thread_id` (read-modify-write race)
- Tool functions with `dict` or `list` parameters (JSON type mapping edge cases at `tools.py:21-28`)
- `_llm_clean()` stripping `$ref` and `anyOf`/`oneOf` types from tool parameter schemas
- `AgentActor._resolve_tool_addrs()` with mixed href/instance/string tool formats
- Abandoned stream generator mid-conversation (client disconnect during threaded stream)

**Suggested test cases:**

```python
# High priority -- covers known bugs
test_resolve_tool_addrs_multiple_hrefs
    # Setup: AgentActor with 3 href-referenced AgentTools
    # Assert: returns exactly 3 addresses, not all tools in table

test_resolve_tool_addrs_mixed_types
    # Setup: tools field with mix of hrefs, AgentTool instances, and plain strings
    # Assert: all three types resolve correctly

test_tool_exclusion_run_stream_not_stream_run
    # Setup: AgentActor subclass with @expose_route on run_stream
    # Assert: run_stream is excluded from tool discovery

test_agentic_stream_class_level_required_fields
    # Setup: model with name: str = Field(min_length=1)
    # Assert: MyModel.agentic_stream(task='test') raises clear error

# Medium priority -- untested code paths
test_result_type_structured_output
    # Setup: define OutputModel(ProtoModel) with typed fields
    # Assert: agentic(task=..., result_type=OutputModel) returns typed result

test_agentic_stream_with_thread_id
    # Setup: create Thread, call agentic_stream(task=..., thread_id=thread.id)
    # Assert: stream completes, thread.messages updated

test_route_tool_call_string_error_data
    # Setup: mock actor that returns tx.error('plain string')
    # Assert: _route_tool_call raises ModelRetry, not AttributeError

test_thread_access_control_cross_user
    # Setup: user A creates thread, user B tries to read via TX
    # Assert: access denied

test_schema_ext_llm_pipeline_strips_ui_keys
    # Setup: model with ui-heavy schema
    # Assert: run_pipeline(cls, pipeline='llm') has no 'ui', 'access', 'renderer' keys

# Lower priority -- edge cases
test_concurrent_thread_race_condition
    # Setup: two simultaneous run() calls with same thread_id
    # Assert: no messages lost (or document the limitation)

test_resolve_llm_falsy_values
    # Setup: _resolve_llm(''), _resolve_llm(0), _resolve_llm(False)
    # Assert: all raise ValueError with actionable message

test_constraints_max_iterations_enforced
    # Setup: agentic(constraints={'max_iterations': 1})
    # Assert: LLM makes at most 1 request
```

### For Feature Development

**Extension points with difficulty ratings:**

| Extension Point | Difficulty | Example | Template Code |
|----------------|-----------|---------|---------------|
| Add `__agent__` to a model | Easy | `apps/veille/models/grant.py:48-52` | Set flag, add `@expose_route` streaming method |
| Add custom stream event types | Easy | `apps/veille/models/run.py:27-43` | Define ProtoModel, add to `events=`, handle in frontend |
| Subclass NTTStreamAgent | Easy-Moderate | `apps/veille/static/components/ntx-grant-analyze.js` | Override UPPERCASE handlers |
| Create a new LLM provider | Moderate* | `mixin.py:92-98` (currently) | Modify `_resolve_llm()` (or use P-C1 registry) |
| Customize tool discovery/filtering | Easy | `tools.py:43-101` | Filter ToolSpecs between discover_tools() and make_tool() |
| Add custom AgentDeps fields | Hard | `deps.py` + `mixin.py:362-365` + `tools.py:210-216` | Three files must be updated |
| Replace pydantic-ai | Very Hard | -- | Rewrite mixin, tools, deps, thread |

**Patterns to follow (cite existing code as templates):**

**Pattern 1: Basic agent-enabled model**
Template: `apps/veille/models/grant.py:48-52`
```python
class MyModel(ActorModel):
    __agent__: ClassVar[dict] = {
        'self_tools': True,      # include own CRUD as tools
        'neighbors': False,       # exclude ListRef neighbors
        'tools': ['other_actor'], # additional tool addresses
    }
```

**Pattern 2: Streaming agent endpoint**
Template: `apps/veille/models/grant.py:87-125`
```python
from n3tx_agents.actor import TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk

@expose_route('/analyze', methods=['POST'], stream=True, access=AUTHENTICATED,
              events={'text': TextChunk, 'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
                      'done': DoneChunk})
async def analyze(self, user=None):
    task = f"Analyze {self.name}: {self.description}"
    async for chunk in self.agentic_stream(task=task, user=user):
        yield chunk
```

**Pattern 3: Custom prompt with dynamic context**
Template: `apps/veille/models/run.py:314`
```python
async def execute(self, user=None):
    context = f"Sources: {self.sources}\nScope: {self.scope}"
    async for chunk in self.agentic_stream(
        task=f"Execute scan for: {self.objective}",
        prompt=f"You are a research agent.\n\n{context}",
        user=user
    ):
        yield chunk
```

**Pattern 4: Custom stream event types**
Template: `apps/veille/models/run.py:27-43`
```python
class SourceStartEvent(ProtoModel):
    __storable__ = False
    source_name: str = Field(default='')
    source_url: str = Field(default='')

# Add to events dict alongside standard events
_STREAM_EVENTS = {
    'text': TextChunk, 'tool_call': ToolCallEvent,
    'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
    'done': DoneChunk,
    'source_start': SourceStartEvent,  # custom
}
```

**Pattern 5: Frontend stream handler subclass**
Template: `apps/veille/static/components/ntx-grant-analyze.js`
```javascript
import { NTTStreamAgent } from './ntx-stream-agent.js';

class MyStreamView extends NTTStreamAgent {
    TOOL_CALL(data, meta) {
        // Customize tool display
        if (data.tool?.includes('my_model_list')) {
            data = { ...data, tool: 'Searching records' };
        }
        super.TOOL_CALL(data, meta);
    }
    // Add handler for custom events
    SOURCE_START(data, meta) {
        const entry = this.addEntry('source-start');
        entry.textContent = `Scanning: ${data.source_name}`;
    }
}
customElements.define('ntx-my-stream', MyStreamView);
```

Wire via `__ui__`:
```python
__ui__ = {'methods': {'analyze': {'renderer': 'ntx-my-stream'}}}
```

**Pattern 6: AgentActor instances via API (data-driven agents)**
Template: `examples/grants/seed.py`
```python
# Register in create_app
app = create_app(
    models=[..., AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool)],
    ...
)

# Create via API or seed script
agent = AgentActor(name='Analyst', prompt='You analyze data.',
                   llm='ollama:llama3.1', constraints={'max_iterations': 5})
AgentActor.create(agent)
# Add tools
tool = AgentTool(target='products', description='Product CRUD')
AgentTool.create(tool)
```

**Constraints to be aware of:**

1. `import n3tx_agents` MUST happen before any model with `__agent__ = True` is defined. This is enforced by convention, not code. Violation is silent.
2. Tool calls always route through Matrix as TX messages. You cannot bypass the actor system for tool execution.
3. `agentic()` on AgentMixin returns `dict`; on AgentActor returns `str` (JSON). Know which you are calling. This is a known inconsistency (finding F8).
4. Thread support requires the Thread model to be registered as an actor (usually handled automatically by `create_app` when Thread is in models list).
5. `run()` and `run_stream()` require a live Matrix (`Actor.root()` must be non-None). Tests need the `fresh_matrix` fixture.
6. The `marked` library must be loaded separately in the HTML page for markdown rendering. Without it, agent text renders as plain text (graceful degradation).
7. Tool parameter types are mapped from JSON Schema via `_JSON_TYPE_MAP` (`tools.py:21-28`). Complex types (`$ref`, `anyOf`, `oneOf`) are not handled and fall through to `str`.

**Common pitfalls:**

- Defining a model with `__agent__ = True` in a file that is imported before `n3tx_agents` -- the model silently has no agent methods. Always check that `import n3tx_agents` appears before model imports in your `main.py`.
- Forgetting to pass `user=user` through to `agentic_stream()` -- tool calls lose auth context and execute without user identity.
- Assuming `AgentActor.agentic()` returns a dict -- it returns a JSON string. Call `json.loads()` on the result.
- Testing without a Matrix -- `run()` raises `RuntimeError("No Matrix root")`. Use the `fresh_matrix` fixture from conftest.
- Using `TestModel` without specifying `call_tools` -- by default it makes no tool calls. Use `TestModel(call_tools=['tool_name'])` to simulate tool usage.
- Creating a Thread but not passing `user_owner` -- thread access control uses OWNER policy, so threads without an owner are inaccessible to non-admin users.

### For Integration Planning

**Integration boundaries with data contracts:**

| Boundary | Direction | Contract | Stability |
|----------|-----------|----------|-----------|
| Agents -> Core (schema pipeline) | Outbound | `@schema_extension(after='methods')`, `register_stage()`, `run_pipeline(cls, pipeline='llm')` | High |
| Agents -> Actors (TX messaging) | Bidirectional | `TX(name, source, target, data, meta)` + `tx.reply()/tx.error()` | Moderate (uses `root._children` private attr) |
| Agents -> Pydantic AI | Outbound | `Agent`, `Tool`, `UsageLimits` (public); `_agent_graph` (private) | Low for streaming path |
| Backend -> Frontend (SSE) | One-way | `{name, data, meta}` chunks with `meta.seq` ordering | High |
| Agents -> Storage | Indirect (via StorableMixin) | Standard CRUD on AgentActor, AgentTool, Thread | High |

**Detailed data contracts at each boundary:**

**Contract 1: Stream Chunk Format (Backend -> Frontend)**
```
{
    name: 'text' | 'tool_call' | 'tool_result' | 'thinking' | 'done' | 'error',
    data: {
        // text/thinking: {text: str}
        // tool_call: {tool: str, args: dict|str, call_id: str}
        // tool_result: {tool: str, result: str, call_id: str}
        // done: {answer: str, usage: {input_tokens, output_tokens, requests}, tool_calls: int}
        // error: {message: str, code: int}
    },
    meta: {
        stream: true,           // always true for non-terminal
        seq: int,               // monotonically increasing
        stream_end?: true,      // only on 'done'
        error?: true,           // only on 'error'
    }
}
```

**Contract 2: Tool TX Messages (Agents -> Actors)**
```python
# Outbound (tool call)
TX(name=method_name, source=root.addr, target=actor_addr,
   data={param: value, ...}, meta={'user': user_dict_or_none})

# Inbound (tool response)
tx.reply(data={'result': ..., 'meta': ...})   # success
tx.error('error message')                      # failure -> ModelRetry
```

**Contract 3: AgentMixin Config Dict**
```python
__agent__: ClassVar[dict] = {
    'prompt': str,           # prepended to auto-generated ctx
    'self_tools': bool,      # include own tablename (default True)
    'neighbors': bool,       # include ListRef neighbors (default True)
    'tools': list[str],      # extra actor addresses
    'llm': str,              # provider:model string
    'constraints': dict,     # {'max_iterations': int}
    'result_type': type,     # Pydantic model for structured output
}
# Unknown keys are silently ignored. No validation at class definition time.
```

**Contract 4: `agentic()` / `run()` Return Shape**
```python
{
    'answer': str | structured_type,
    'usage': {'input_tokens': int|None, 'output_tokens': int|None, 'requests': int},
    'messages': list,           # pydantic-ai ModelMessage objects (NOT JSON-serializable)
    'message_count': int,
    'thread_id': int,           # ONLY present when thread_id was provided
}
# WARNING: AgentActor.agentic() wraps this in json.dumps(result, default=str),
# which stringifies ModelMessage objects into useless repr strings.
```

**Dependency stability assessment:**

| Dependency | Version Sensitivity | Risk | Mitigation |
|-----------|-------------------|------|------------|
| n3tx-core | Low | ProtoModel, schema pipeline, config -- all mature | None needed |
| n3tx-actors | Low | Actor, TX, Matrix -- core architecture | None needed |
| pydantic-ai (public API) | Low | `Agent.run()`, `Tool`, `UsageLimits` | Standard semver |
| pydantic-ai (`_agent_graph`) | **High** | Private API used for streaming graph iteration | Pin version in requirements; monitor changelog |
| pydantic-ai (messages) | Moderate | `ModelMessagesTypeAdapter` for thread serialization | Pin version |
| marked (JS) | Low | Optional runtime dependency for markdown | Graceful degradation to textContent |

**Impact analysis checklist -- when changing this subsystem, verify:**

- [ ] Schema pipeline: `GET /ClassName` still includes `agent` metadata for `__agent__` models
- [ ] Tool discovery: `discover_tools()` returns correct CRUD + method specs for all registered actors
- [ ] Stream protocol: all six chunk types (`text`, `tool_call`, `tool_result`, `thinking`, `done`, `error`) follow `{name, data, meta}` shape
- [ ] Auth propagation: `user` flows from HTTP layer to `AgentDeps` to TX meta to target handler
- [ ] Thread lifecycle: read-before, update-after pattern works for both streaming and non-streaming
- [ ] Frontend dispatch: UPPERCASE handlers are called correctly by `NTTStream.STREAM()`
- [ ] Config cascade: 3-tier resolution (`AGENT_DEFAULTS < __agent__ < kwargs`) produces correct values
- [ ] Example tests pass: `cd /workspace && python3 -m pytest examples/grants/tests/`
- [ ] Agent unit tests pass: `cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/`
- [ ] Schema endpoint returns `agent` key for `__agent__` models
- [ ] `agentic_stream` SSE connection opens, delivers chunks, and closes cleanly

**Compatibility considerations for connecting new subsystems:**

- **Adding a new network adapter** (e.g., gRPC): The agents subsystem routes all tool calls through `Actor.root().request()`. A new adapter works automatically if it is registered on the Matrix and handles the standard TX format.
- **Adding a new storage backend**: AgentActor, AgentTool, and Thread use StorableMixin. Any backend that implements the StorableMixin interface works. The `constraints` and `messages` fields use JSON serialization -- the backend must handle `dict`/`list` field types.
- **Adding a new LLM provider**: Currently requires modifying `_resolve_llm()`. With P-C1 (provider registry), it would be additive. For now, pass a pre-constructed model instance: `agentic(task=..., llm=my_custom_model)`.
- **Connecting to external tool APIs**: The tool router (`_route_tool_call`) is hardcoded to Matrix TX. To call external APIs, either (a) create a proxy actor that wraps the external API, or (b) implement P-5b (injectable tool router).

### For Refactoring

**Technical debt ranked by severity and coupling risk:**

| # | Debt Item | Severity | Coupling Risk | Location |
|---|-----------|----------|--------------|----------|
| 1 | `run()`/`run_stream()` ~100 lines duplicated setup | Medium | Low | `mixin.py:268-691` |
| 2 | Frontend handler duplication across 3 components | Medium | Low | `ntx-stream-agent.js`, `ntx-agent-live.js`, `ntx-chat.js` |
| 3 | AgentActor descriptor `.fn` bypass | Medium | **High** | `actor.py:157,192` |
| 4 | `agentic()`/`agentic_stream()` duplicated config cascade | Low | Low | `mixin.py:220-265`, `mixin.py:424-459` |
| 5 | `_build_instance_text()` silently swallows all exceptions | Low | Low | `mixin.py:117-119` |
| 6 | Mutable defaults (`Field(default=[])`) | Low | None | `thread.py:52`, `actor.py:48,64,91,93` |

**Suggested refactoring sequence (dependency order):**

1. **Fix bugs first**: F1 (`_resolve_tool_addrs`), F2 (`stream_run` -> `run_stream`). No architectural impact.
2. **Export AGENT_EVENTS** (P-C2): Trivial, unblocks downstream changes.
3. **Thread context manager** (P-S2): Extract shared code, reduces duplication in step 4.
4. **Merge run/agentic** (P-S1): Depends on step 3 being done. This is the big change.
5. **Clean AgentActor override** (consequence of step 4): Descriptor hack is eliminated.
6. **Shared AgentStreamRenderer** (P-C3): Independent of backend changes. Can be done in parallel with steps 3-5.

**Risk assessment:**

| Refactoring | Risk | Mitigation |
|-------------|------|-----------|
| Fix `_resolve_tool_addrs` | Low | Add test with multiple hrefs first (red-green) |
| Export AGENT_EVENTS | None | Additive change |
| Thread context manager | Low | Behavior-preserving extraction; existing tests cover |
| Merge run/agentic | Medium | Update all test call sites; verify AgentActor override |
| Shared frontend renderer | Low | Extract-and-delegate; visual regression test with screenshots |

**Before/after sketch for P-S1 (merge run/agentic):**

Before (current):
```
agentic(target, task, **kwargs)         -> config cascade -> run(target, task, prompt, tools, ...)
agentic_stream(target, task, **kwargs)  -> config cascade -> run_stream(target, task, prompt, tools, ...)

AgentActor.agentic(self, task, **kwargs)
  -> AgentMixin.__dict__['run'].fn(self, task=task, prompt=self.prompt, ...)  # descriptor hack
```

After (proposed):
```
agentic(target, task, **kwargs)         -> _resolve_config() -> _run(target, task, prompt, tools, ...)
agentic_stream(target, task, **kwargs)  -> _resolve_config() -> _run_stream(target, task, prompt, tools, ...)

AgentActor.agentic(self, task, **kwargs)
  -> super().agentic(task=task, prompt=self.prompt, tools=tool_addrs, llm=self.llm, ...)  # normal call
```

---

## Appendix: Complete Finding Index

| ID | Dimension | Type | Severity | Finding/Proposition | File(s) | Status |
|----|-----------|------|----------|---------------------|---------|--------|
| F1 | Quality | Finding | High | `_resolve_tool_addrs()` batch fetch ignores `ids` filter | `actor.py:129` | Open -- likely broken |
| F2 | API | Finding | High | `stream_run` vs `run_stream` name mismatch in exclusion set | `tools.py:96` | Open -- latent bug |
| F3 | Quality | Finding | High | XSS via `marked.parse()` on unsanitized LLM output | `ntx-stream-agent.js:214`, `ntx-agent-live.js:268` | Open |
| F4 | Quality | Finding | Medium | `agentic_stream()` class-level creates invalid instance for models with required fields | `mixin.py:444-447` | Open |
| F5 | API | Finding | Medium | `messages` field in AgentActor.agentic() serialized as Python repr strings | `actor.py:168` | Open |
| F6 | API | Finding | Medium | Silent mixin injection failure on import misordering | `__init__.py:17-18` | Open -- documented but not enforced |
| F7 | Quality | Finding | Medium | Thread update failure silently swallowed, result implies success | `mixin.py:401-407`, `mixin.py:655-661` | Open |
| F8 | API | Finding | Medium | AgentActor.agentic() returns str, AgentMixin.agentic() returns dict | `actor.py:137` vs `mixin.py:220` | Open -- violates Liskov |
| F9 | Quality | Finding | Medium | `run_stream()` error chunk hardcodes `code: 500` for all errors | `mixin.py:689` | Open |
| F10 | Quality | Finding | Medium | `run_stream()` errors caught but not logged | `mixin.py:685-691` | Open |
| F11 | Quality | Finding | Low | `_build_instance_text()` silently swallows all model_dump exceptions | `mixin.py:117-119` | Open |
| F12 | Quality | Finding | Low | `_route_tool_call()` assumes error TX data is dict | `tools.py:219-221` | Open |
| F13 | Quality | Finding | Low | No timeout on individual tool calls via Matrix | `tools.py:218` | Open |
| F14 | Quality | Finding | Low | `ntx-chat.js` uses `innerHTML +=` which re-parses DOM | `ntx-chat.js:135` | Open |
| F15 | API | Finding | Low | Stream event models not in `__all__` or `__init__.py` exports | `actor.py:41-66` | Open |
| F16 | Quality | Finding | Low | `_build_instance_text()` truncation logic inconsistent (stores original vs truncated) | `mixin.py:122-129` | Open |
| F17 | API | Finding | Low | `result_type` (structured output) code path entirely untested | `mixin.py:357-358` | Open |
| F18 | Extensibility | Finding | Low | Mutable defaults `Field(default=[])` on Pydantic models | `thread.py:52`, `actor.py:48,64,91,93` | Open -- cosmetic only |
| F19 | Quality | Finding | Low | Abandoned stream generator skips thread update | `mixin.py:642-661` | Open |
| F20 | API | Finding | Info | `agent-actor.md:159` and `tool-discovery.md:97-98` have stale references | docs | Open |
| P-S1 | Simplification | Proposition | -- | Merge run/agentic into 2 public + 2 private methods | `mixin.py`, `actor.py` | Proposed |
| P-S2 | Simplification | Proposition | -- | Thread context manager to deduplicate lifecycle | `mixin.py` | Proposed |
| P-C1 | Extensibility | Proposition | -- | Provider registry for `_resolve_llm()` | `mixin.py:76-102` | Proposed |
| P-C2 | Composability | Proposition | -- | Export AGENT_EVENTS constant | `__init__.py`, `actor.py` | Proposed |
| P-C3 | Composability | Proposition | -- | Shared AgentStreamRenderer (frontend) | `ntx-stream-agent.js`, `ntx-agent-live.js`, `ntx-chat.js` | Proposed |
| P-R1 | Resilience | Proposition | -- | Agent execution timeout via constraints | `mixin.py` | Proposed |
| P-R2 | Resilience | Proposition | -- | DiscoveryResult from discover_tools() | `tools.py:43-101` | Proposed |
| P-R3 | Resilience | Proposition | -- | Agent-to-agent recursion depth limit | `deps.py`, `mixin.py` | Proposed |
