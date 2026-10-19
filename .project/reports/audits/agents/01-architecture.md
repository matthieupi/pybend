# N3TX Agents Subsystem: Architecture & Design Patterns Audit

**Auditor**: Claude Opus 4.6
**Date**: 2026-03-26
**Scope**: `packages/n3tx-agents/` — all Python backend, JS frontend, docs, and usage sites
**Commit base**: Branch `v0.9`, commit `779137c`

---

## 1. Component Inventory

### 1.1 Python Backend Modules

| Module | File | Role |
|--------|------|------|
| `__init__.py` | `n3tx_agents/__init__.py` | Package entry: registers AgentMixin via `register_mixin()`, re-exports public API, triggers `schema_ext` side-effect import |
| `AgentMixin` | `n3tx_agents/mixin.py` | Mixin injected into models with `__agent__ = True`; provides 6 `@fullmethod` methods for LLM reasoning |
| `AgentActor` | `n3tx_agents/actor.py` | Concrete ActorModel whose DB instances ARE agents; overrides `agentic()` and `agentic_stream()` to read config from fields |
| `AgentTool` | `n3tx_agents/tool_model.py` | Simple storable model linking an agent to an actor address via ListRef join table |
| `AgentDeps` | `n3tx_agents/deps.py` | Dataclass passed as `deps` to Pydantic AI tool functions via `RunContext[AgentDeps]` |
| `Thread` | `n3tx_agents/thread.py` | Per-conversation history ActorModel; standard CRUD, static serialization helpers |
| `ToolSpec` | `n3tx_agents/tools.py` | Dataclass describing a single tool derived from a model schema |
| `discover_tools()` | `n3tx_agents/tools.py` | Discovers CRUD and custom method tools from a list of actor addresses |
| `create_tool_function()` | `n3tx_agents/tools.py` | Generates an async function with typed signature via `exec()` from a ToolSpec |
| `make_tool()` | `n3tx_agents/tools.py` | Wraps a generated function in `pydantic_ai.tools.Tool` |
| `_route_tool_call()` | `n3tx_agents/tools.py` | Routes tool calls through Matrix as TX messages with request-response correlation |
| `_resolve_llm()` | `n3tx_agents/mixin.py` | Module-level function resolving LLM string (including `ollama:` prefix) to pydantic-ai model instance |
| `schema_ext` | `n3tx_agents/schema_ext.py` | Registers two schema pipeline extensions: `agent` stage (default pipeline) and `base`+`clean` stages (LLM pipeline) |
| Stream event models | `n3tx_agents/actor.py:41-66` | 5 non-storable ProtoModels (`TextChunk`, `ToolCallEvent`, `ToolResultEvent`, `ThinkingChunk`, `DoneChunk`) for typed SSE events |

### 1.2 JavaScript Frontend Components

| Component | File | Tag | Role |
|-----------|------|-----|------|
| `NTTStreamAgent` | `ntx-stream-agent.js` | `<ntx-stream-agent>` | Rich agent output renderer: typed entries (thinking, tool calls, text), markdown, collapsible sections |
| `NTTAgentLive` | `ntx-agent-live.js` | `<ntx-agent-live>` | Standalone agent activity panel with input textarea, run button, status badge, structured log |
| `NTTChat` | `ntx-chat.js` | `<ntx-chat>` | Floating chat panel with instance selector, conversational UX, tool cards inline |
| `NtxAgent` | `ntx-agent.js` | `<ntx-agent>` | Purpose-built entity renderer for AgentActor instances; multi-size (xs/sm/md/lg/xl) with hero banners |

### 1.3 Module Dependency Graph (Internal)

```
__init__.py
    |
    +-- mixin.py  (AgentMixin)
    |     +-- deps.py (AgentDeps)
    |     +-- tools.py (discover_tools, make_tool)
    |     +-- thread.py (Thread.to_history, Thread.from_history)
    |
    +-- actor.py  (AgentActor, stream event models)
    |     +-- tool_model.py (AgentTool)
    |     +-- mixin.py (AgentMixin.__dict__['run'].fn — descriptor bypass)
    |
    +-- schema_ext.py (schema pipeline extensions)
    |     +-- actor.py (AgentActor — issubclass check)
    |
    +-- tool_model.py (AgentTool — standalone)
    +-- thread.py (Thread — standalone)
```

---

## 2. Responsibility Map

### 2.1 Why Each Component Exists

| Component | What It Does | Why It Exists | What Breaks If Removed |
|-----------|-------------|---------------|----------------------|
| `AgentMixin` | Provides `ctx()`, `tools()`, `agentic()`, `run()`, `agentic_stream()`, `run_stream()` | Enables any model to become "self-aware" with one flag (`__agent__ = True`), following the StorableMixin pattern | No model can reason via LLM; the entire agent subsystem becomes inert |
| `AgentActor` | DB-storable agent with fields for prompt, llm, tools, constraints | Enables agents-as-data: create/configure agents via API without code changes | Cannot create agents at runtime; all agents must be defined in code |
| `AgentTool` | Stores a `target` actor address + description | Enables the join-table pattern for agent-tool relationships via ListRef | AgentActor loses its tool reference mechanism; must hardcode tool addresses |
| `AgentDeps` | Carries `user` dict and `agent_addr` through Pydantic AI tool calls | Tool functions need auth context for TX routing; Pydantic AI requires a typed deps object | Tool calls lose auth context; all TX tool calls execute without user identity |
| `Thread` | Stores conversation history as TX-shaped dicts | Multi-turn conversations require persisted message history; Thread is the store | Single-turn only; no conversation memory between requests |
| `ToolSpec` | Holds actor_addr, method_name, tool_name, description, parameters | Intermediate representation between schema discovery and Pydantic AI tool creation | No bridge between N3TX schemas and Pydantic AI tool system |
| `discover_tools()` | Reads schemas from Matrix children, generates CRUD + method ToolSpecs | Agents need tools; tools are derived from registered actors' schemas | Agents have no tools; must manually construct Pydantic AI tools |
| `create_tool_function()` | Generates async Python functions via `exec()` with proper type signatures | Pydantic AI introspects function signatures for JSON Schema; dynamic functions need dynamic signatures | Tools have no typed parameters; LLM cannot use schema-guided tool calling |
| `_route_tool_call()` | Creates TX, sends via Matrix `request()`, returns JSON response | Tool calls must route through the actor system, not bypass it | Tools cannot communicate with actors; agent reasoning is disconnected from the system |
| `_resolve_llm()` | Handles `ollama:model` prefix, creates `OpenAIChatModel` with `OllamaProvider` | Ollama requires special provider setup; framework hides this complexity | `ollama:*` LLM strings fail; users must manually construct model objects |
| `schema_ext` | Adds `agent` metadata to schemas + provides LLM-clean schema pipeline | Frontend needs to know if a model is agent-enabled; LLM needs clean schemas without UI noise | Frontend cannot discover agent capabilities; LLM context includes irrelevant UI metadata |
| Stream event models | Define typed schemas for SSE events (TextChunk, ToolCallEvent, etc.) | `@expose_route(events={...})` needs ProtoModel subclasses; enables frontend handler discovery via schema | Frontend cannot validate stream events; no schema-declared event vocabulary |
| `NTTStreamAgent` | UPPERCASE handlers for rich rendering of agent stream events | Base `NTTStream` only handles plain text; agent output needs typed entries, markdown, tool cards | Agent streaming renders as raw text dump; no structured visual output |
| `NTTAgentLive` | Standalone panel with textarea input and structured log | Provides a ready-to-use agent interaction surface that can be embedded in any view | No standalone agent interaction UI; must build custom for each use case |
| `NTTChat` | Floating chat widget with instance selector and conversational UX | Provides a chat-style interface for conversational agent interaction | No chat-style agent interface; only method-card or live-panel styles available |
| `NtxAgent` | Multi-size renderer for AgentActor entities with provider-themed visuals | Standard `ntx-item` doesn't know about agent-specific fields (prompt, llm, tools) | AgentActor instances render as generic entity cards without agent-specific information |

---

## 3. Design Patterns

### 3.1 Mixin Injection (via Registry)

**Where**: `__init__.py:18` calls `register_mixin('__agent__', AgentMixin)` which adds to `proto_model._mixin_registry`. `ProtoModel.__init_subclass__` checks each registered flag on the new class and dynamically prepends the mixin to `cls.__bases__`.

**Why chosen**: Follows the established StorableMixin pattern. A model opts in with a single ClassVar flag. No imports, no MI declaration, no boilerplate. The injection is transparent — the class gains methods without the developer touching its inheritance chain.

**Assessment**: Correct choice. Directly aligns with the "zero to working, then customize" philosophy. The only risk is the **import ordering constraint** — `n3tx_agents` must be imported before any `__agent__ = True` model is defined. This is documented in CLAUDE.md and enforced by convention but not by code. A model defined too early silently misses the mixin.

**Risk**: Silent failure on import misordering (mixin.py:18 via `__init__.py`). No runtime check verifies that a model with `__agent__ = True` actually has AgentMixin in its MRO.

### 3.2 fullmethod Descriptor (Unified Dispatch)

**Where**: All 6 AgentMixin methods (`ctx`, `tools`, `agentic`, `run`, `agentic_stream`, `run_stream`) at `mixin.py:158-691`.

**Why chosen**: Agent methods need to work on both classes (`Product.ctx()` for schema-level context) and instances (`product.ctx()` for instance-level context). The `fullmethod` descriptor (`descriptors.py:18-44`) uses `__get__` to bind either the class or instance as the first argument.

**Assessment**: Elegant and correct. Avoids the classmethod/instancemethod split that would require two implementations. The pattern is transparent — you can read `def ctx(target)` and understand it receives either. The one wrinkle is that `fullmethod` instances are not regular methods, so `AgentActor.agentic()` bypasses the descriptor via `AgentMixin.__dict__['run'].fn` (actor.py:157). This is a necessary escape hatch but creates a tight coupling between AgentActor and AgentMixin's internal descriptor representation.

### 3.3 Strategy Pattern (Config Cascade)

**Where**: `agentic()` (mixin.py:220-265) resolves config from 3 tiers: `config.AGENT_DEFAULTS` < `__agent__` dict < kwargs. Same cascade in `agentic_stream()` (mixin.py:423-459).

**Why chosen**: Agents need layered configuration — global defaults, per-model settings, and per-call overrides. The cascade pattern lets each layer override the previous one without special syntax.

**Assessment**: Well-designed. The `'tools' in kwargs` check (mixin.py:244) is particularly thoughtful — it distinguishes "no tools" (`tools=[]`) from "auto-discover" (omit `tools`). The cascade is easy to reason about and debug. The duplication between `agentic()` and `agentic_stream()` is minor and justified — the two methods have slightly different downstream paths.

### 3.4 Mediator Pattern (Matrix as Tool Router)

**Where**: `_route_tool_call()` (tools.py:201-222) creates a TX and sends it through `Actor.root().request()`. The Matrix routes the TX to the target actor, which processes it and replies.

**Why chosen**: Tool calls must go through the actor system to respect auth, interceptors, and message routing. Direct function calls would bypass the architecture.

**Assessment**: Correct and essential. This is what makes agent tools participate in the full N3TX lifecycle — authorization, logging, interceptors all apply. The `ModelRetry` raise on error TX (tools.py:221) is a smart integration point: it tells the LLM "this tool call failed, try differently" rather than crashing the agent loop.

### 3.5 Factory Pattern (Dynamic Tool Generation)

**Where**: `create_tool_function()` (tools.py:225-296) uses `exec()` to generate async functions with proper Python signatures. `make_tool()` (tools.py:299-313) wraps them in Pydantic AI `Tool` objects.

**Why chosen**: Pydantic AI introspects function signatures to generate JSON Schema for the LLM. N3TX schemas are dynamic (defined at runtime), so tool functions must also be dynamic. The `exec()` approach is the same one used by `dataclasses`, `namedtuple`, and `attrs`.

**Assessment**: Correct approach, well-documented justification. The security note (tools.py:7-9 — "All input comes from trusted model schemas, not user input") is important and accurate. The namespace is carefully controlled (tools.py:286-291). However, the `_JSON_TYPE_MAP` (tools.py:21-28) is incomplete — it lacks `null` handling and complex types like `allOf`, `oneOf`, `$ref`. These edge cases would fall through to the default `'str'` type, which is a reasonable degradation but could cause runtime type errors for complex schemas.

### 3.6 Adapter Pattern (LLM Resolution)

**Where**: `_resolve_llm()` (mixin.py:76-102) converts `ollama:model` strings to `OpenAIChatModel` with `OllamaProvider`.

**Why chosen**: Different LLM providers have different client construction. The framework normalizes this behind a string convention.

**Assessment**: Minimal but effective. Currently only handles `ollama:` prefix; all other strings are passed through to Pydantic AI (which handles `anthropic:`, `openai:`, etc. natively). The function is a thin adapter that fills a gap in Pydantic AI's native resolution for local Ollama instances.

### 3.7 Template Method Pattern (NTTStreamAgent)

**Where**: `NTTStream.STREAM()` (ntx-stream.js:22-35) dispatches to UPPERCASE handlers: `THINKING()`, `TOOL_CALL()`, `TOOL_RESULT()`, `TEXT()`, `DONE()`, `STREAM_END()`, `STREAM_ERROR()`. Subclasses override these handlers.

**Why chosen**: Different agent UIs (live panel, chat, embedded card) need different rendering for the same event types. The base class handles event dispatch; subclasses handle presentation.

**Assessment**: Clean separation. The UPPERCASE naming convention mirrors the backend actor handler pattern. The dispatch mechanism in `NTTStream.STREAM()` uses `data?.name?.toUpperCase()` to find handlers, which means any new event type is automatically dispatched without code changes to the base class.

### 3.8 Composite Pattern (NtxAgent Size Methods)

**Where**: `ntx-agent.js:89-132` — `md()`, `lg()`, `xl()` compose section renderers (`renderHeader()`, `renderPrompt()`, `renderTools()`, `renderActivity()`) to build different-sized views.

**Why chosen**: Agent entity cards vary dramatically by display size. Composable section renderers let each size pick the sections it needs without duplicating HTML generation.

**Assessment**: Well-structured. Each section renderer is independently overridable by subclasses. The `renderActivity()` method (ntx-agent.js:305-313) embeds an `<ntx-agent-live>` component, creating a component composition boundary.

---

## 4. Data Flow

### 4.1 Non-Streaming Agent Execution

```
User/API                     AgentMixin                    Pydantic AI              Matrix/Actors
  |                              |                              |                        |
  | POST /products/1/analyze     |                              |                        |
  |----------------------------->|                              |                        |
  |                              |                              |                        |
  |               agentic(task)  |                              |                        |
  |               [config cascade]                              |                        |
  |                    |         |                              |                        |
  |               run(task,prompt,tools,...)                    |                        |
  |                    |         |                              |                        |
  |                    | _resolve_llm()                         |                        |
  |                    | discover_tools(addrs, root)            |                        |
  |                    |    |    |                              |                        |
  |                    |    |----|--- cls.schema() ------------>|--- root._children[addr]|
  |                    |    |<---|--- ToolSpec[] <----          |                        |
  |                    |    |    |                              |                        |
  |                    | make_tool(spec) per spec               |                        |
  |                    |         |                              |                        |
  |                    | [Thread: TX get → threads actor]-------|----------------------->|
  |                    |         |                              |                        |
  |                    |--- Agent(llm, tools, prompt) -------->|                        |
  |                    |         |     agent.run(task, deps)    |                        |
  |                    |         |                              |                        |
  |                    |         |     [LLM calls tool] ------>| _route_tool_call()     |
  |                    |         |                              |---> TX(name,target) -->|
  |                    |         |                              |<--- TX response <------|
  |                    |         |                              |                        |
  |                    |         |     [LLM returns answer]    |                        |
  |                    |         |<----- result ----------------|                        |
  |                    |         |                              |                        |
  |                    | [Thread: TX update → threads actor]----|----------------------->|
  |                    |         |                              |                        |
  |<--- {answer, usage, messages}                              |                        |
```

### 4.2 Streaming Agent Execution

```
User/API                     AgentMixin.run_stream()        Pydantic AI iter()       Matrix
  |                              |                              |                       |
  | POST /agents/1/agentic_stream (SSE)                        |                       |
  |----------------------------->|                              |                       |
  |                              | agent.iter(task, deps)       |                       |
  |                              |----------------------------->|                       |
  |                              |                              |                       |
  |                              | <-- ModelRequestNode --------|                       |
  |                              |   <-- PartStartEvent(TextPart)                       |
  | <--yield {name:'text'}-------|                              |                       |
  |                              |   <-- PartDeltaEvent         |                       |
  | <--yield {name:'text'}-------|                              |                       |
  |                              |   <-- PartStartEvent(ToolCallPart)                   |
  | <--yield {name:'tool_call'}- |                              |                       |
  |                              |                              |                       |
  |                              | <-- CallToolsNode ----------|                       |
  |                              |   FunctionToolResultEvent    | TX(name,target) ----->|
  |                              |                              | <--- TX response -----|
  | <--yield {name:'tool_result'}|                              |                       |
  |                              |                              |                       |
  |                              | <-- iteration complete       |                       |
  | <--yield {name:'done'}-------|                              |                       |
  |                              |                              |                       |
  | (SSE: event:done, stream_end)|                              |                       |
```

### 4.3 Frontend Event Flow

```
Backend SSE                  NTTStream               NTTStreamAgent/Live/Chat
  |                              |                              |
  | event: chunk                 |                              |
  | data: {name:'text',...}      |                              |
  |----------------------------->|                              |
  |                              | STREAM(data, tx)             |
  |                              |   name = 'TEXT'              |
  |                              |   this['TEXT'](data.data)    |
  |                              |----------------------------->|
  |                              |                              | #textBuf += text
  |                              |                              | #scheduleRender()
  |                              |                              | #renderMd() (markdown)
  |                              |                              |
  | event: chunk                 |                              |
  | data: {name:'tool_call',...} |                              |
  |----------------------------->|                              |
  |                              | STREAM(data, tx)             |
  |                              |   name = 'TOOL_CALL'        |
  |                              |----------------------------->|
  |                              |                              | #addEntry('tool-call')
  |                              |                              | #toolCards.set(call_id)
  |                              |                              |
  | event: done                  |                              |
  | meta: {stream_end: true}     |                              |
  |----------------------------->|                              |
  |                              | STREAM_END()                 |
  |                              |----------------------------->|
  |                              |                              | status='done', enable btn
```

### 4.4 Tool Discovery Pipeline

```
actor_addrs: ['grants', 'web_tools']
        |
        v
discover_tools(addrs, root, caller_addr)     # tools.py:43
        |
        +-- for each addr:
        |     root._children[addr] → child actor
        |     cls = child.__class__
        |     schema = cls.schema()
        |     |
        |     +-- is_storable?
        |     |     _crud_tool_specs()  → 5 ToolSpecs (list/get/create/update/delete)
        |     |       - filter out id, protected, hidden fields
        |     |       - writable fields get create/update params
        |     |
        |     +-- schema.methods?
        |           _method_tool_specs()  → 1 ToolSpec per @expose_route method
        |             - strip 'user' param (server-injected)
        |             - add 'id' for instancemethods
        |             - exclude run/stream_run for AgentActor subclasses
        |
        v
list[ToolSpec]
        |
        v (per spec)
create_tool_function(spec)                   # tools.py:225
        |
        +-- build parameter list from JSON Schema properties
        |     required: no default
        |     optional: default=None
        |
        +-- exec() → async function with typed signature
        |     function calls _route_tool_call(ctx, target, method, data)
        |
        v
make_tool(spec)                              # tools.py:299
        |
        +-- pydantic_ai.Tool(fn, takes_ctx=True, name, description)
        |
        v
Tool (registered on pydantic_ai.Agent)
```

---

## 5. State Management

### 5.1 State Locations

| State | Location | Lifecycle | Mutability |
|-------|----------|-----------|------------|
| Mixin registry | `proto_model._mixin_registry` (module global) | Process lifetime | Write-once at import time |
| Agent config (mixin path) | `cls.__agent__` ClassVar | Class lifetime | Immutable after class definition |
| Agent config (actor path) | Instance fields (`name`, `prompt`, `llm`, `constraints`, `tools`) in DB | DB-persisted | Mutable via CRUD |
| LLM model instance | Created per `run()`/`run_stream()` call in `_resolve_llm()` | Request-scoped | Immutable once created |
| Pydantic AI Agent | Created per `run()`/`run_stream()` call | Request-scoped | Immutable once created |
| Tool specs | Created per `discover_tools()` call | Request-scoped | Immutable (dataclass) |
| Thread messages | `Thread.messages` field in DB | Persisted across requests | Appended after each agent run |
| AgentDeps | Created per `run()`/`run_stream()` call | Request-scoped | Immutable (dataclass) |
| Sequence counter (`seq`) | Local variable in `run_stream()` | Stream-scoped | Incremented per event |
| Streamed text accumulator | `streamed_text` in `run_stream()` | Stream-scoped | Appended per text event |
| Frontend text buffers | `#textBuf`, `#thinkBuf` private fields | Component instance | Reset per `callMethod()` |
| Frontend tool cards | `#toolCards` Map | Component instance | Cleared per `callMethod()` |
| Schema cache | `cls.schema()` returns deep copy from internal cache | Process lifetime | Cache busted only by schema changes |

### 5.2 State Flow Observations

**No shared mutable state between agent runs.** Each call to `run()` or `run_stream()` creates a fresh Pydantic AI Agent, fresh tool functions, and fresh AgentDeps. This is correct for concurrency — concurrent agent runs cannot interfere with each other.

**Thread state is externalized.** Thread reads/writes go through TX to the `threads` actor, which uses standard CRUD. This means thread operations participate in auth, storage, and the full actor lifecycle. No in-memory thread caching exists.

**Frontend state is component-scoped.** Each `NTTStreamAgent`/`NTTAgentLive`/`NTTChat` instance manages its own buffers. The `callMethod()` reset pattern (clearing `#textBuf`, `#thinkBuf`, `#toolCards`) ensures no state leaks between consecutive runs.

---

## 6. Coupling Analysis

### 6.1 Python Backend Coupling

| Source | Target | Type | Rating | Notes |
|--------|--------|------|--------|-------|
| `mixin.py` → `n3tx_core.config` | Import | Loose | Reads `AGENT_DEFAULTS`, `OLLAMA_BASE_URL` — config is a stable interface |
| `mixin.py` → `n3tx_core.models.proto_schema` | Import | Loose | Calls `run_pipeline(cls, pipeline='llm')` — pipeline is a published API |
| `mixin.py` → `n3tx_core.utils.descriptors` | Import | Tight | `@fullmethod` is a framework primitive; unlikely to change |
| `mixin.py` → `n3tx_actors.tx.TX` | Import | Tight | TX is the message envelope; core to the architecture |
| `mixin.py` → `n3tx_actors.actor.Actor` | Import | Tight | Calls `Actor.root()` for Matrix access |
| `mixin.py` → `pydantic_ai` | Import | **Tight** | Imports internal graph API (`_agent_graph`) and message types; breakage risk on pydantic-ai upgrades |
| `actor.py` → `mixin.py` | Descriptor bypass | **Tight** | `AgentMixin.__dict__['run'].fn` accesses the raw function inside the fullmethod descriptor (actor.py:157, 192) |
| `tools.py` → `n3tx_actors.tx.TX` | Import | Tight | TX construction for tool routing |
| `tools.py` → `n3tx_core.models.storable_mixin` | Import (lazy) | Loose | `issubclass(cls, StorableMixin)` check in `discover_tools()` |
| `tools.py` → `pydantic_ai.tools.Tool` | Import (lazy) | Moderate | Public API of pydantic-ai |
| `tools.py` → `pydantic_ai.ModelRetry` | Import (lazy) | Moderate | Used for LLM retry signaling; public API |
| `schema_ext.py` → `n3tx_core.models.proto_schema` | Import | Tight | Uses `schema_extension` decorator and `register_stage` function |
| `schema_ext.py` → `actor.py` | Import (lazy) | Moderate | `issubclass(cls, AgentActor)` check for endpoint pattern |
| `thread.py` → `pydantic_ai.messages` | Import (lazy) | **Moderate** | `ModelMessagesTypeAdapter` for serialization; more stable than internal APIs |
| `__init__.py` → `n3tx_core.models.proto_model` | Import | Tight | `register_mixin()` — must run before any model definition |

### 6.2 Critical Coupling: pydantic-ai Internals

The most significant coupling risk is in `mixin.py:47-55`:

```python
from pydantic_ai._agent_graph import (
    ModelRequestNode, CallToolsNode, UserPromptNode, End,
)
from pydantic_ai.messages import (
    PartStartEvent, PartDeltaEvent, PartEndEvent,
    FunctionToolCallEvent, FunctionToolResultEvent,
    TextPart, ToolCallPart, ThinkingPart,
    TextPartDelta, ThinkingPartDelta, ToolCallPartDelta,
)
```

The `_agent_graph` import is from a private module (underscore prefix). This is used in `run_stream()` to iterate over the agent graph nodes for fine-grained stream event dispatch. A pydantic-ai version bump could break this without notice.

**Mitigation**: The messages module (`pydantic_ai.messages`) appears to be public API. The `_agent_graph` module is the risky one. The `agent.iter()` API (used at mixin.py:559) is the graph streaming interface — if pydantic-ai stabilizes this, the internal imports can be replaced.

### 6.3 Frontend Coupling

| Source | Target | Type | Rating |
|--------|--------|------|--------|
| `ntx-stream-agent.js` → `NTTStream` (n3tx-ui) | Inheritance | Tight | Core streaming base class |
| `ntx-stream-agent.js` → `showToast` (n3tx-ui) | Import | Loose | Utility function |
| `ntx-agent-live.js` → `NTTStream` (n3tx-ui) | Inheritance | Tight | Core streaming base class |
| `ntx-agent-live.js` → `NTT` (n3tx-core) | Import | Moderate | Entity registry for instance lookup |
| `ntx-agent-live.js` → `JsonTree` utils | Import | Loose | Rendering utility |
| `ntx-chat.js` → `NTTStream` (n3tx-ui) | Inheritance | Tight | Core streaming base class |
| `ntx-chat.js` → `HTTP` (n3tx-core) | Import | Moderate | Transport for instance loading |
| `ntx-agent.js` → `NTTItem` (n3tx-ui) | Inheritance | Tight | Entity renderer base class |
| `ntx-agent.js` → `permissions` (n3tx-ui) | Import | Moderate | Access control checks |
| `ntx-agent.js` → `ntx-agent-live.js` | Side-effect import | Loose | Ensures `<ntx-agent-live>` is registered |

The frontend coupling is structurally sound. All agent components depend on their respective base classes from n3tx-ui/n3tx-core, which is correct given the dependency graph (`n3tx-agents` depends on both `n3tx-core` and `n3tx-actors`; UI components use base classes from `n3tx-ui`).

---

## 7. Cohesion Assessment

### 7.1 Module-by-Module

| Module | Cohesion | Assessment |
|--------|----------|------------|
| `mixin.py` | **High** | Single responsibility: AgentMixin with its 6 methods. The module-level helpers (`_resolve_llm`, `_build_schema_text`, `_build_instance_text`) are private functions used exclusively by the mixin. At ~690 lines, it is the largest module but not bloated — `run_stream()` alone is ~200 lines due to the pydantic-ai graph iteration logic. |
| `actor.py` | **High** | Contains AgentActor (the model) and its 5 stream event models. The event models are defined here rather than in a separate file because they are used exclusively by AgentActor's `@expose_route(events={...})` declaration. Cohesive grouping. |
| `tools.py` | **High** | Complete tool pipeline: discovery, spec, function generation, routing. All functions serve the same concern (bridging N3TX schemas to Pydantic AI tools). |
| `deps.py` | **High (trivially)** | 9 lines. One dataclass with two fields. Could be inlined but is correctly separated because it is imported independently by both mixin.py and tool functions. |
| `thread.py` | **High** | Model + two static serialization helpers. No extra responsibilities. |
| `tool_model.py` | **High (trivially)** | 14 lines. One model with two fields. Correctly separated from actor.py because it is independently registered and stored. |
| `schema_ext.py` | **Moderate** | Contains two distinct pipelines (default `agent` stage and LLM `base`+`clean` stages). These are related (both about schema enrichment for agents) but serve different consumers (frontend schema vs LLM context). Acceptable cohesion — splitting would create two tiny files with shared imports. |
| `ntx-stream-agent.js` | **High** | UPPERCASE handlers + rendering helpers + CSS. All serve one purpose: rendering structured agent stream output. |
| `ntx-agent-live.js` | **Moderate-High** | Contains significant rendering code that overlaps with `ntx-stream-agent.js`. The UPPERCASE handlers, `#setThinking()`, `#scheduleRender()`, `#renderMd()`, `#addEntry()` are near-duplicates. See Observation 7.2. |
| `ntx-chat.js` | **High** | Distinct UX pattern (floating chat with message history) that justifies its own component. Handler implementations are appropriately simplified for the chat context. |
| `ntx-agent.js` | **High** | Purpose-built entity renderer with clear section composition. All code serves the single concern of rendering AgentActor instances at various sizes. |

### 7.2 Duplication: NTTStreamAgent vs NTTAgentLive

`NTTAgentLive` (451 lines) and `NTTStreamAgent` (353 lines) share approximately 70% of their handler logic:

- `THINKING()`, `TOOL_CALL()`, `TOOL_RESULT()`, `TEXT()`, `DONE()` — near-identical implementations
- `#setThinking()`, `#scheduleRender()`, `#renderMd()`, `#flushRender()`, `#addEntry()` — duplicated private helpers
- `#scrollToBottom()`, `#esc()` — trivial but duplicated

`NTTAgentLive` extends `NTTStream` directly rather than `NTTStreamAgent`. This means it cannot inherit the rich rendering logic. The architectural intent appears to be: `NTTStreamAgent` is for embedded method-card context; `NTTAgentLive` is for standalone panel context. But the rendering logic is identical.

**Recommendation**: `NTTAgentLive` should extend `NTTStreamAgent` instead of `NTTStream`, adding only the panel shell (`prerender()`, `#cacheEls()`, `#bindListeners()`, `#reset()`) and overriding `STREAM_END`/`STREAM_ERROR` for status badge updates. This would eliminate ~200 lines of duplication.

---

## 8. Boundary Analysis

### 8.1 Public Surface

The package explicitly declares its public API via `__all__` in `__init__.py:29-33`:

```python
__all__ = [
    'AgentMixin', 'AgentActor', 'AgentTool', 'AgentDeps',
    'ToolSpec', 'discover_tools', 'make_tool',
    'Thread',
]
```

### 8.2 Boundary Enforcement

| Boundary | Mechanism | Enforced? |
|----------|-----------|-----------|
| Public API | `__all__` in `__init__.py` | Yes — conventional |
| Private functions | Underscore prefix (`_resolve_llm`, `_build_schema_text`, `_route_tool_call`, `_crud_tool_specs`, `_method_tool_specs`) | Yes — conventional |
| AgentActor descriptor bypass | `AgentMixin.__dict__['run'].fn` | No — reaches into descriptor internals |
| Schema pipeline stages | `@schema_extension`, `register_stage` | Yes — framework API |
| Frontend privates | JS private fields (`#textBuf`, `#toolCards`, `#els`) | Yes — language-enforced (ES2022 private fields) |
| Import order constraint | Documentation + convention | No — no programmatic enforcement |

### 8.3 Internal vs External

**Internal implementation** (not exported, not documented for external use):
- `_resolve_llm()`, `_build_schema_text()`, `_build_instance_text()` (mixin.py)
- `_route_tool_call()`, `_crud_tool_specs()`, `_method_tool_specs()`, `_JSON_TYPE_MAP`, `create_tool_function()` (tools.py)
- `_llm_base()`, `_llm_clean()`, `_LLM_STRIP_KEYS`, `_METHOD_STRIP_KEYS` (schema_ext.py)
- Stream event models (`TextChunk`, `ToolCallEvent`, etc.) — used by AgentActor but also imported by apps (veille/models/run.py:11-13, veille/models/grant.py:7-8)

**Observation**: The stream event models are imported from `n3tx_agents.actor` by application code (`apps/veille/models/run.py:11-13`) but are not in `__all__`. They function as a de facto public API. They should either be added to `__all__` and exported from `__init__.py`, or applications should define their own event models (which they already do for app-specific events like `SourceStartEvent`, `GrantFoundEvent`).

---

## 9. Configuration Surface

### 9.1 Configurable

| Config Point | Location | Default | Scope |
|-------------|----------|---------|-------|
| `llm` | `config.AGENT_DEFAULTS['llm']` / `__agent__['llm']` / kwargs | None (ValueError if unresolved) | Global / per-model / per-call |
| `constraints.max_iterations` | `config.AGENT_DEFAULTS['constraints']` / `__agent__['constraints']` / kwargs | None (no limit) | Global / per-model / per-call |
| `self_tools` | `__agent__['self_tools']` | `True` | Per-model |
| `neighbors` | `__agent__['neighbors']` | `True` | Per-model |
| `tools` (extra addresses) | `__agent__['tools']` | `[]` | Per-model |
| `prompt` | `__agent__['prompt']` | `''` | Per-model |
| `result_type` | `__agent__['result_type']` / kwargs | `None` | Per-model / per-call |
| `OLLAMA_BASE_URL` | `config.OLLAMA_BASE_URL` | (from config.py) | Global |
| Thread access control | `Thread.__access__` ClassVar | `OWNER \| ROLE('admin')` | Static |
| AgentActor UI renderer | `AgentActor.__ui__['renderer']` | `{'item': 'ntx-agent', 'detail': 'ntx-agent'}` | Static |

### 9.2 Hardcoded (Should Be Configurable?)

| Item | Location | Value | Should Be Configurable? |
|------|----------|-------|------------------------|
| Instance data truncation length | `mixin.py:128` | `200` chars | Possibly — large contexts may need full field values |
| Tool call self-exclusion | `tools.py:65-66` | Agent always excluded from its own tools | No — preventing self-loops is correct by default |
| AgentActor method exclusion | `tools.py:94-96` | `{'run', 'stream_run'}` excluded | No — correct safety default |
| Markdown render delay | `ntx-stream-agent.js:198` | `300ms` timeout | Possibly — UX tuning parameter |
| Tool result truncation | `ntx-stream-agent.js:56` | `500` chars | Possibly — diagnostic detail level |
| Chat result truncation | `ntx-chat.js:134` | `120` chars | Possibly — display density preference |
| Agent output max-height | `ntx-stream-agent.js:249` | `500px` | Yes — should use CSS custom property |
| Live panel max-height | `ntx-agent-live.js:299` | `600px` | Yes — should use CSS custom property |
| LLM clean strip keys | `schema_ext.py:53-55` | Hardcoded sets | No — these are architectural; not domain-specific |

### 9.3 Observation: Missing `constraints` Configuration

The `constraints` dict currently only maps `max_iterations` to `UsageLimits.request_limit` (mixin.py:370-373). Other potential constraint dimensions are not implemented:

- `max_tokens` (output length limit)
- `max_time` (wall-clock timeout)
- `allowed_tools` (tool whitelist)
- `forbidden_tools` (tool blacklist)

The constraint surface is minimal but extensible — new keys can be added to the constraints dict and handled in `run()`/`run_stream()` without breaking existing code.

---

## 10. Error Propagation

### 10.1 Error Flow Map

```
Layer               Error Type              Handling                        Visible To
─────               ──────────              ────────                        ──────────
_resolve_llm()      ValueError              Raised directly                 Caller (agentic/run)
                    "No LLM provided"

Actor.root()        RuntimeError            Raised directly                 Caller
                    "No Matrix root"

Thread TX           is_error on TX          RuntimeError raised             Caller (run/run_stream)
                                            in run(); yielded as error
                                            chunk in run_stream()

discover_tools()    Missing actor           logger.warning, skipped         Log only (silent skip)
                    No schema               logger.warning, skipped         Log only (silent skip)

Tool call           is_error on TX          ModelRetry raised               Pydantic AI (LLM retries)
(_route_tool_call)                          (tools.py:220-221)

run() failures      Any Exception           Raised directly                 HTTP layer (500)

run_stream()        Any Exception           Yielded as error chunk          Frontend (STREAM_ERROR)
                                            (mixin.py:685-691)              SSE consumer

Frontend SSE        Network error           STREAM_ERROR handler            User (error entry + toast)
                    Parse error             showToast()                     User (toast notification)
```

### 10.2 Error Handling Assessment

**run() vs run_stream() asymmetry**: `run()` (mixin.py:268-421) lets exceptions propagate to the caller. `run_stream()` (mixin.py:461-691) catches all exceptions and yields them as error chunks (mixin.py:685-691). This is correct: streaming responses cannot use HTTP status codes after the stream has started, so errors must be in-band.

**Silent tool discovery failures**: When `discover_tools()` encounters a missing actor or one without a `schema()` method (tools.py:71-78), it logs a warning and skips the actor. This means an agent may silently lose tools if an actor is not registered. The agent proceeds with fewer tools than expected, which could lead to confusing LLM behavior.

**ModelRetry for tool errors**: When a tool call's TX response has `is_error` (tools.py:219-221), the code raises `pydantic_ai.ModelRetry` rather than a generic exception. This allows the LLM to attempt a different approach rather than crashing the entire agent run. This is well-designed — it uses the LLM's native retry mechanism.

**Thread update failure**: When the post-run thread update fails (mixin.py:401-407, 655-661), it logs a warning but does not fail the agent run. This is correct — the agent's answer has already been computed; losing the thread update is a degradation, not a failure.

**Missing error chunk in run()**: If `run()` fails after partially executing (e.g., LLM call succeeds but thread update raises), the successful result is lost. This is unlikely but possible. The `run_stream()` variant handles this better by yielding results incrementally.

### 10.3 Specific Concerns

**Broad exception catch in run_stream()** (mixin.py:685):

```python
except Exception as e:
    yield {
        'name': 'error',
        'data': {'message': str(e), 'code': 500},
        'meta': {'stream': True, 'error': True, 'seq': seq},
    }
```

This catches all exceptions including `KeyboardInterrupt` (via `Exception` base) — actually no, `KeyboardInterrupt` inherits from `BaseException`, not `Exception`, so this is correct. However, it silently catches programming errors (AttributeError, TypeError, etc.) and converts them to user-facing error messages. In development, this can hide bugs. A `logger.exception()` call before the yield would help.

**_build_instance_text silent failure** (mixin.py:117-120):

```python
try:
    data = target.model_dump()
except Exception:
    return ''
```

If `model_dump()` fails, the instance context is silently omitted. The agent receives schema context but no instance data, which could lead to confusing results. This should at least log a warning.

---

## Appendix A: Component Hierarchy (JS)

```
HTMLElement
  └── Component (n3tx-core)
        └── Actor bridge
              └── NTTMethod (n3tx-ui)
                    └── NTTStream (n3tx-ui)
                          ├── NTTStreamAgent (n3tx-agents)     <ntx-stream-agent>
                          ├── NTTAgentLive (n3tx-agents)       <ntx-agent-live>
                          └── NTTChat (n3tx-agents)            <ntx-chat>

HTMLElement
  └── Component
        └── NTTElement (n3tx-ui)
              └── NTTItem (n3tx-ui)
                    └── NtxAgent (n3tx-agents)                 <ntx-agent>
```

## Appendix B: Configuration Cascade (Visual)

```
config.AGENT_DEFAULTS          Tier 1: Global defaults
        |                      (set in config.py or env vars)
        v
__agent__ = {                  Tier 2: Model-level
    'llm': 'ollama:llama3.1',  (ClassVar on the model)
    'tools': ['extra_actor'],
    'constraints': {...},
    'prompt': 'You are...',
}
        |
        v
agentic(task,                  Tier 3: Per-call overrides
    llm='anthropic:claude-sonnet-4-5-20250929',  (kwargs to agentic())
    tools=['specific_actor'],
    constraints={'max_iterations': 5},
)

AgentActor bypass:
DB fields → _resolve_tool_addrs() → AgentMixin.run() directly
(skips Tier 2 cascade; DB fields ARE the config)
```

## Appendix C: Files Reviewed

**Python backend** (8 files):
- `/workspace/packages/n3tx-agents/src/n3tx_agents/__init__.py`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/mixin.py`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/actor.py`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/tools.py`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/deps.py`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/schema_ext.py`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/thread.py`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/tool_model.py`

**JS frontend** (4 files):
- `/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js`

**Docs** (3 files):
- `/workspace/packages/n3tx-agents/docs/mixin.md`
- `/workspace/packages/n3tx-agents/docs/agent-actor.md`
- `/workspace/packages/n3tx-agents/docs/tool-discovery.md`

**Usage sites** (5 files):
- `/workspace/apps/veille/models/run.py`
- `/workspace/apps/veille/models/grant.py`
- `/workspace/examples/grants/main.py`
- `/workspace/examples/grants/seed.py`
- `/workspace/examples/pygentic/main.py`

**Supporting files** (2 files):
- `/workspace/packages/n3tx-core/src/n3tx_core/utils/descriptors.py`
- `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js`
