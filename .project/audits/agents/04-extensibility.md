# Agents Subsystem: Extensibility & Integration Audit

> Audit date: 2026-03-26 | Branch: v0.9 | Auditor: Claude Opus 4.6

## Table of Contents

- [Extension Points](#extension-points)
- [Integration Boundaries](#integration-boundaries)
- [Dependency Graph](#dependency-graph)
- [Data Contracts at Boundaries](#data-contracts-at-boundaries)
- [What's Easy to Change](#whats-easy-to-change)
- [What's Hard to Change](#whats-hard-to-change)
- [Constraints & Limitations](#constraints--limitations)
- [Feature Integration Guide](#feature-integration-guide)
- [Comparison with Alternatives](#comparison-with-alternatives)
- [Evolution Trajectory](#evolution-trajectory)
- [Cross-Cutting Concerns](#cross-cutting-concerns)

---

## Extension Points

The agents subsystem provides eight distinct extension mechanisms, ordered from highest to lowest leverage.

### 1. `__agent__` Flag (Model-Level Opt-In)

| Aspect | Detail |
|--------|--------|
| Mechanism | ClassVar flag on any ActorModel subclass |
| Difficulty | Easy |
| Location | `proto_model.py:112-119` (mixin injection loop) |

Setting `__agent__ = True` or `__agent__ = {config dict}` on any ActorModel triggers AgentMixin injection via `ProtoModel.__init_subclass__`. The mixin registry (`_mixin_registry` at `proto_model.py:29`) is populated at `n3tx_agents/__init__.py:18` via `register_mixin('__agent__', AgentMixin)`.

**Boolean form** — zero config, full capability:
```python
class Task(ActorModel):
    __agent__ = True
```

**Dict form** — fine-grained control:
```python
class Grant(ActorModel):
    __agent__ = {
        'self_tools': True,
        'neighbors': False,
        'tools': ['organizations'],
        'prompt': 'You are a grant analyst.',
    }
```

The dict form accepts: `self_tools`, `neighbors`, `tools` (extra addrs), `prompt`, `llm`, `constraints`, `result_type`. These flow into the 3-tier config cascade in `mixin.py:237-265`.

**Limitation**: The `__agent__` flag must be a ClassVar. It cannot be changed at runtime on a class. For runtime-configurable agents, use AgentActor (DB fields).

### 2. AgentActor Subclassing

| Aspect | Detail |
|--------|--------|
| Mechanism | Python class inheritance |
| Difficulty | Easy |
| Location | `actor.py:68-205` |

AgentActor is a concrete ActorModel. Subclassing it creates a new agent type with custom fields and behavior. The `Conversation` model in `/workspace/examples/chat/models/conversation.py:33` demonstrates this: it overrides `tools` to `list` (disabling AgentTool ListRef), adds `messages: ListRef[Message]`, and provides a custom `chat()` streaming endpoint.

The pattern is: subclass AgentActor, override fields you need, add `@expose_route` methods. All agent capabilities (agentic, run, run_stream) are inherited.

### 3. `@expose_route` + `stream=True` + `events={}`

| Aspect | Detail |
|--------|--------|
| Mechanism | Decorator on model methods |
| Difficulty | Easy |
| Location | `decorators.py` (core), consumed in `actor.py:170-174` |

Any model with `__agent__ = True` can define custom streaming endpoints that internally call `self.agentic_stream()`. The `events=` parameter declares the SSE event vocabulary as ProtoModel subclasses, which the schema pipeline serializes into `methods[m].events` for frontend consumption.

Example from `apps/veille/models/run.py:214-215`:
```python
@expose_route('/execute', methods=['POST'], stream=True, access=AUTHENTICATED,
              events=_STREAM_EVENTS)
async def execute(self, user=None):
    async for chunk in self._scrape_source(...):
        yield chunk
```

Custom event types (e.g., `SourceStartEvent`, `GrantFoundEvent` at `run.py:27-43`) extend the stream vocabulary beyond the five default agent events.

### 4. Schema Pipeline Extension (LLM Pipeline)

| Aspect | Detail |
|--------|--------|
| Mechanism | `@schema_extension` decorator / `register_stage()` |
| Difficulty | Moderate |
| Location | `schema_ext.py:25-101` |

The agents subsystem registers two pipeline extensions:

1. **Default pipeline** — `agent` stage (after `methods`): Injects `agent` metadata into JSON Schema for `__agent__ = True` models (`schema_ext.py:25-47`).

2. **LLM pipeline** — `base` + `clean` stages: Produces a clean schema stripped of frontend-only keys (`schema_ext.py:58-101`). Consumed by `_build_schema_text()` in `mixin.py:108-112` via `run_pipeline(cls, pipeline='llm')`.

New pipelines can be registered without modifying existing code:
```python
register_stage('my_stage', my_func, after='clean', pipeline='llm')
```

### 5. Frontend Component Hierarchy (UPPERCASE Handlers)

| Aspect | Detail |
|--------|--------|
| Mechanism | JS class inheritance + UPPERCASE method override |
| Difficulty | Easy-Moderate |
| Location | `ntx-stream-agent.js`, `ntx-agent-live.js`, `ntx-chat.js`, `ntx-agent.js` |

The component inheritance chain is:

```
Component -> NTTMethod -> NTTStream -> NTTStreamAgent -> App subclasses
                                    -> NTTAgentLive
                                    -> NTTChat
```

`NTTStream` (`ntx-stream.js:22-35`) receives all stream events via the `STREAM()` handler and dispatches to UPPERCASE methods: `TEXT()`, `THINKING()`, `TOOL_CALL()`, `TOOL_RESULT()`, `DONE()`, `STREAM_END()`, `STREAM_ERROR()`.

Subclasses override individual handlers. For example:
- `NTXGrantAnalyze` (`ntx-grant-analyze.js:11-32`) overrides only `TOOL_CALL()` to show friendly tool descriptions.
- `NTXRunOutput` (`ntx-run-output.js:21-516`) adds `SOURCE_START()`, `SOURCE_DONE()`, `GRANT_FOUND()` without touching the parent's TEXT/THINKING/TOOL handlers.

The `__ui__['methods'][name]['renderer']` schema key maps method names to custom element tags, enabling per-method rendering customization.

### 6. Tool Discovery Filtering

| Aspect | Detail |
|--------|--------|
| Mechanism | Post-discovery ToolSpec filtering |
| Difficulty | Easy |
| Location | `tools.py:43-101` |

`discover_tools()` returns `list[ToolSpec]`, which can be filtered before passing to `make_tool()`:
```python
specs = discover_tools(['products'], root)
read_specs = [s for s in specs if s.method_name in ('list', 'get')]
tools = [make_tool(s) for s in read_specs]
```

This is documented in `docs/tool-discovery.md:117-122` but there is no built-in hook for automatic filtering. The filtering must be done in application code between `discover_tools()` and `make_tool()`.

### 7. AgentDeps Extension

| Aspect | Detail |
|--------|--------|
| Mechanism | Dataclass with two fields |
| Difficulty | Hard (requires forking) |
| Location | `deps.py:17-22` |

`AgentDeps` is a simple dataclass with `user` and `agent_addr` fields. It is passed to every tool function via `RunContext[AgentDeps]`. Currently it cannot be extended without modifying `deps.py` and the tool function generation in `tools.py:261-262`.

Adding new fields (e.g., `session_id`, `tenant_id`) requires changes to:
1. `deps.py` — add the field
2. `mixin.py:362-365` and `mixin.py:538-540` — populate the field in `AgentDeps()` construction
3. `tools.py:210-216` — make the field available in `_route_tool_call()`

### 8. `_resolve_llm()` LLM Provider Extension

| Aspect | Detail |
|--------|--------|
| Mechanism | Module-level function |
| Difficulty | Moderate (requires code change) |
| Location | `mixin.py:76-102` |

Currently handles `ollama:model` strings by creating `OpenAIChatModel` with `OllamaProvider`. All other strings are passed through to pydantic-ai, which handles `openai:`, `anthropic:`, `google:`, etc. natively.

To add a custom provider prefix (e.g., `local:model`), you must modify `_resolve_llm()`. There is no plugin mechanism.

---

## Integration Boundaries

### Boundary 1: Agents <-> Core (Schema Pipeline)

| Aspect | Detail |
|--------|--------|
| What crosses | Python function calls, dict data |
| Direction | Agents calls into Core |
| Coupling | Moderate — depends on pipeline API but not internals |

**Inbound**: `schema_ext.py` imports `schema_extension` and `register_stage` from `n3tx_core.models.proto_schema`. The `@schema_extension(after='methods')` decorator inserts the `agent` stage into the default pipeline.

**Outbound**: `mixin.py:109` calls `run_pipeline(cls, pipeline='llm')` to generate LLM-clean schemas. This depends on the pipeline registry being populated with stages from `schema_ext.py:100-101`.

**Contract**: Stages receive `(cls, schema: dict) -> dict`. The `schema` dict follows the JSON Schema structure enriched by prior stages. The `agent` stage expects `methods` to already be in the schema (hence `after='methods'`).

**Stability**: High. The pipeline API (`register_stage`, `schema_extension`, `run_pipeline`) is a stable extension point. Changes to stage ordering or new stages don't break existing ones.

### Boundary 2: Agents <-> Actors (TX Messaging)

| Aspect | Detail |
|--------|--------|
| What crosses | TX dataclass messages, `Actor.root()` singleton |
| Direction | Bidirectional |
| Coupling | Strong — agents require a live Matrix |

The agents subsystem depends on the actor system for:

1. **Tool routing** (`tools.py:201-222`): `_route_tool_call()` creates TX messages and sends them through `Actor.root().request()`. This is the only way tool calls reach their target actors.

2. **Thread persistence** (`mixin.py:327-341`, `mixin.py:388-407`): Thread read/update operations use TX messages to the `threads` actor address.

3. **Tool discovery** (`tools.py:61`): `root._children` is accessed directly to find registered actors.

4. **Matrix root requirement** (`mixin.py:319-323`): `Actor.root()` must return a Matrix instance or `run()` raises `RuntimeError`.

**Contract**: TX messages follow a strict envelope format:
```python
TX(name=str, source=str, target=str, data=dict, meta=dict)
```
Response TXs use `tx.reply(data=dict)` or `tx.error(str)`. The `is_error` property on response TX signals failure.

**Stability**: Moderate. The TX format is stable, but the dependency on `root._children` (private attribute) is fragile. A public API like `root.has(addr)` would be more appropriate.

### Boundary 3: Agents <-> Pydantic AI (LLM Engine)

| Aspect | Detail |
|--------|--------|
| What crosses | Agent/Tool objects, message types, streaming events |
| Direction | Agents wraps Pydantic AI |
| Coupling | Very strong — deep dependency on internal APIs |

The agents subsystem imports extensively from pydantic-ai:

From `mixin.py:44-55`:
```python
from pydantic_ai import Agent, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
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

The `_agent_graph` import is a **private API** (underscore prefix). The streaming implementation in `run_stream()` (`mixin.py:555-683`) directly iterates the agent graph nodes (`ModelRequestNode`, `CallToolsNode`) and processes low-level streaming events. This is the tightest coupling in the entire subsystem.

From `tools.py:305`:
```python
from pydantic_ai.tools import Tool
```

From `tools.py:220`:
```python
from pydantic_ai import ModelRetry
```

From `thread.py:70-72`:
```python
from pydantic_ai.messages import ModelMessagesTypeAdapter
```

**Stability**: Low for the streaming path. Any pydantic-ai version bump that changes `_agent_graph` internals will break `run_stream()`. The non-streaming path (`run()` at `mixin.py:382`) uses only the public `agent.run()` API, which is stable.

### Boundary 4: Agents <-> Frontend (SSE/WebSocket)

| Aspect | Detail |
|--------|--------|
| What crosses | JSON SSE events, JSON Schema |
| Direction | Backend -> Frontend (streaming), Frontend -> Backend (requests) |
| Coupling | Moderate — contract defined by TX chunk format |

The stream chunk format (defined at `mixin.py:472-478`) is the protocol contract:
```
{name: 'text|tool_call|tool_result|thinking|done|error',
 data: {type-specific fields},
 meta: {stream: true, seq: N, stream_end?: true, error?: true}}
```

Frontend components (`NTTStream`, `NTTStreamAgent`, etc.) consume these via the UPPERCASE dispatch mechanism (`ntx-stream.js:22-35`). The `NTTStream.STREAM()` handler normalizes the event name to uppercase and calls `this[name](data.data, data.meta)`.

Schema-declared events (`events=` on `@expose_route`) add type validation on both sides. The backend serializes event ProtoModels into `methods[m].events` in the JSON Schema. The frontend can use these schemas for validation but currently does not — it trusts the event shape.

**Stability**: High. The chunk format is well-defined and both sides implement it consistently. New event types (like `SOURCE_START`, `GRANT_FOUND`) are additive — they don't break existing consumers.

### Boundary 5: Agents <-> Storage (via Core)

| Aspect | Detail |
|--------|--------|
| What crosses | SQL queries, model instances |
| Direction | Indirect — through StorableMixin |
| Coupling | Low — agents use standard CRUD |

AgentActor, AgentTool, and Thread all use `__storable__ = True`, which injects StorableMixin. Storage operations (create, get, list, update, delete) go through the same path as any other storable model.

The `constraints` field on AgentActor (`dict` type) is auto-serialized to JSON TEXT by `sqlite_storage.py`. The `tools` field uses the standard `ListRef[AgentTool]` join-table pattern.

Thread's `messages` field (`list` type) is also auto-serialized to JSON TEXT — conversation history is stored as a single JSON blob per thread, not as individual records.

---

## Dependency Graph

```
                     ┌─────────────────────┐
                     │    pydantic-ai       │
                     │  (external library)  │
                     └──────────┬──────────┘
                                │ Agent, Tool, UsageLimits
                                │ _agent_graph (PRIVATE)
                                │ messages.*
                                │
┌──────────────┐    ┌───────────▼──────────┐    ┌──────────────────┐
│   n3tx-core   │◄───┤    n3tx-agents       │───►│   n3tx-actors    │
│              │    │                      │    │                  │
│ ProtoModel   │    │ AgentMixin           │    │ Actor            │
│ proto_schema │    │ AgentActor           │    │ ActorModel       │
│ proto_dump   │    │ AgentTool            │    │ TX               │
│ config       │    │ Thread               │    │ Matrix           │
│ StorableMixin│    │ tools/deps/schema_ext│    │ actor_proxy      │
│ decorators   │    │                      │    │                  │
│ descriptors  │    │ JS: NTTStreamAgent   │    │                  │
│ registrar    │    │     NTTAgentLive     │    │                  │
│ introspection│    │     NTTChat          │    │                  │
│ SQLiteStorage│    │     NtxAgent         │    │                  │
└──────────────┘    └──────────────────────┘    └──────────────────┘
       ▲                      ▲                         ▲
       │                      │                         │
       │              ┌───────┴─────────┐               │
       │              │  n3tx-ui        │               │
       │              │                 │               │
       │              │ NTTStream       │───────────────┘
       │              │ NTTMethod       │ (JS class that agents
       │              │ NTTItem         │  components inherit from)
       │              │ Formidable      │
       │              └─────────────────┘
       │
       │     ┌────────────────────────────────────┐
       └─────┤  Application Code                  │
             │  (veille, grants, pygentic, chat)  │
             │                                    │
             │  Uses: __agent__ flag, AgentActor,  │
             │  agentic_stream(), stream events,   │
             │  NTTStreamAgent subclasses          │
             └────────────────────────────────────┘
```

### Inbound Dependencies (what agents imports)

| Package | Imports | Files |
|---------|---------|-------|
| n3tx-core | `config`, `ProtoModel`, `proto_schema.run_pipeline`, `proto_schema.schema_extension`, `proto_schema.register_stage`, `Field`, `ListRef`, `expose_route`, `fullmethod`, `register_model`, `register_mixin`, `get_list_fields`, `AUTHENTICATED`, `OWNER`, `ROLE` | `mixin.py`, `actor.py`, `schema_ext.py`, `thread.py`, `tool_model.py` |
| n3tx-actors | `Actor`, `ActorModel`, `TX`, `Matrix` | `mixin.py`, `actor.py`, `tools.py`, `thread.py`, `tool_model.py` |
| pydantic-ai | `Agent`, `UsageLimits`, `OpenAIChatModel`, `OllamaProvider`, `Tool`, `ModelRetry`, `_agent_graph.*`, `messages.*`, `ModelMessagesTypeAdapter` | `mixin.py`, `tools.py`, `thread.py` |

### Outbound Dependencies (what depends on agents)

| Consumer | What it uses | How |
|----------|-------------|-----|
| Application models | `__agent__ = True`, `agentic_stream()`, stream event models | `run.py:11-13`, `grant.py:6-8`, `task.py:15` |
| Application frontends | `NTTStreamAgent` subclass, UPPERCASE handlers | `ntx-run-output.js:19`, `ntx-grant-analyze.js:9` |
| n3tx-core (indirectly) | `register_mixin` callback | `__init__.py:18` — side-effect at import |
| n3tx-ui (indirectly) | `NTTStream` base class | `ntx-stream-agent.js:1` imports from ui package |

---

## Data Contracts at Boundaries

### Contract 1: Mixin Config Dict (`__agent__`)

**Type**: Implicit (convention-based). No schema validation.

```python
# Accepted keys (from mixin.py:168-169, 196-201, 237-254):
{
    'prompt': str,           # prepended to auto-generated ctx
    'self_tools': bool,      # include own tablename in tools (default True)
    'neighbors': bool,       # include ListRef neighbor tablenames (default True)
    'tools': list[str],      # extra actor addresses
    'llm': str,              # provider:model string
    'constraints': dict,     # {"max_iterations": int}
    'result_type': type,     # Pydantic model for structured output
}
```

Unknown keys are silently ignored. There is no validation at class definition time.

### Contract 2: Stream Chunk Format

**Type**: Explicit (documented, schema-declared via `events=`).

Six chunk types, each with a fixed `name` and typed `data`:

| name | data fields | meta fields |
|------|-------------|-------------|
| `text` | `{text: str}` | `{stream: true, seq: int}` |
| `tool_call` | `{tool: str, args: dict, call_id: str}` | `{stream: true, seq: int}` |
| `tool_result` | `{tool: str, result: str, call_id: str}` | `{stream: true, seq: int}` |
| `thinking` | `{text: str}` | `{stream: true, seq: int}` |
| `done` | `{answer: str, usage: dict, tool_calls: int}` | `{stream: true, stream_end: true, seq: int}` |
| `error` | `{message: str, code: int}` | `{stream: true, error: true, seq: int}` |

ProtoModel subclasses in `actor.py:41-65` (`TextChunk`, `ToolCallEvent`, etc.) formalize these as typed models. When declared via `events=`, the schema pipeline serializes them into `methods[m].events`.

### Contract 3: Tool TX Messages

**Type**: Explicit (TX dataclass).

Tool calls create TXs with:
```python
TX(name=method_name, source=root.addr, target=actor_addr,
   data={param: value, ...}, meta={'user': user_dict})
```

Responses follow the standard TX reply convention: `tx.reply(data=dict)` for success, `tx.error(str)` for failure.

### Contract 4: Thread Message Format

**Type**: Explicit (TX-shaped dicts wrapping pydantic-ai messages).

Stored in `Thread.messages` as:
```python
[{
    'name': 'request|response|...',
    'source': str,
    'target': str,
    'data': {pydantic-ai ModelMessage dict},
    'meta': {},
    'timestamp': float,
}, ...]
```

Conversion uses `ModelMessagesTypeAdapter` from pydantic-ai (`thread.py:70-72`, `thread.py:91-92`).

### Contract 5: AgentDeps

**Type**: Explicit (typed dataclass).

```python
@dataclass
class AgentDeps:
    user: Optional[dict]     # JWT user dict
    agent_addr: str          # agent's actor address
```

Passed to every tool function via `RunContext[AgentDeps]`.

---

## What's Easy to Change

### Add a new agent-enabled model (< 30 min)

Add `__agent__ = True` (or a config dict) to any ActorModel. Optionally add a streaming `@expose_route` that calls `self.agentic_stream()`. The mixin auto-injects `ctx()`, `tools()`, `agentic()`, `run()`, `agentic_stream()`, `run_stream()`.

Evidence: `task.py:15-39` — 25 lines for a complete agent-enabled model with streaming analysis.

### Add a new stream event type (< 15 min)

Define a ProtoModel subclass, add it to the `events=` dict on `@expose_route`, yield chunks with that name. Frontend components receive it via the UPPERCASE dispatch and can handle it with a new method.

Evidence: `run.py:27-43` and `run.py:94-103` — custom `SourceStartEvent`, `SourceDoneEvent`, `GrantFoundEvent` added alongside the standard agent events.

### Add a custom frontend stream renderer (< 1 hour)

Subclass `NTTStreamAgent`, override UPPERCASE handlers or add new ones. Register via `customElements.define()`. Wire via `__ui__['methods'][name]['renderer']`.

Evidence: `ntx-grant-analyze.js` — 35 lines to customize tool call display. `ntx-run-output.js` — more complex but still a clean subclass.

### Change the default LLM (< 5 min)

Set `N3TX_AGENT_DEFAULTS='{"llm": "anthropic:claude-sonnet-4-5-20250929"}'` as an environment variable. Or set `config.AGENT_DEFAULTS['llm']` in application code. Or set `__agent__ = {'llm': 'anthropic:claude-sonnet-4-5-20250929'}` per model.

### Add tools to an existing agent model (< 10 min)

Add actor addresses to `__agent__['tools']` list, or for AgentActor instances, `POST /agents/{id}/agent_tools {"target": "new_actor"}`.

### Customize the system prompt (< 10 min)

Set `__agent__['prompt']` for static prompts. For dynamic prompts, override the `agentic()` call with `prompt=` kwarg, as `grant.py:120` and `run.py:314` demonstrate.

---

## What's Hard to Change

### Replace pydantic-ai with another LLM framework

**Difficulty**: Very hard. Requires rewriting `mixin.py`, `tools.py`, `deps.py`, and `thread.py`.

The streaming implementation (`run_stream()`, 130+ lines at `mixin.py:461-691`) is deeply coupled to pydantic-ai's internal graph API (`_agent_graph.ModelRequestNode`, `CallToolsNode`). The non-streaming path (`run()`) uses `agent.run()`. Tool wrapping (`make_tool()`) creates `pydantic_ai.tools.Tool` objects. Thread serialization uses `ModelMessagesTypeAdapter`.

Estimated effort: 2-3 weeks of refactoring, plus test rewrites.

### Add multi-agent orchestration (agent-to-agent communication)

**Difficulty**: Hard. The current design assumes a single agent per request.

`run()` and `run_stream()` create a fresh `pydantic_ai.Agent` on every call (`mixin.py:360`, `mixin.py:536`). There is no mechanism for one agent to delegate to another agent, wait for its result, and incorporate it. The `AgentActor.run` and `stream_run` methods are auto-excluded from tool discovery (`tools.py:94-96`) specifically to prevent recursive loops, but this also prevents intentional delegation.

Workaround: An agent can call another agent's `agentic` endpoint as a tool, but this creates a nested Agent instance with independent context.

### Change the tool routing from TX to direct function calls

**Difficulty**: Hard. Tool routing through Matrix TX is fundamental to the architecture.

`_route_tool_call()` (`tools.py:201-222`) creates TX messages and routes through `Actor.root().request()`. This provides auth propagation, interceptor chains, and protocol-agnostic routing. Bypassing it would require duplicating auth logic and losing interceptor support.

### Add custom AgentDeps fields

**Difficulty**: Moderate-Hard. Requires changes to 3 files.

As noted in [Extension Point 7](#7-agentdeps-extension), adding a field to `AgentDeps` requires updating `deps.py`, the two `AgentDeps()` construction sites in `mixin.py`, and potentially `_route_tool_call()` in `tools.py`.

### Support non-ActorModel agents (e.g., plain ProtoModel with agents)

**Difficulty**: Hard. The agents subsystem assumes the actor system is present.

`run()` at `mixin.py:319-323` calls `Actor.root()` and raises if no Matrix exists. Tool routing goes through Matrix. The mixin could theoretically be injected into a ProtoModel, but `tools()` at `mixin.py:202` looks for `__tablename__` (actor addressing) and `run()` requires Matrix.

---

## Constraints & Limitations

### 1. Single LLM per agent invocation

Each call to `run()` or `run_stream()` creates a fresh `pydantic_ai.Agent` with a single LLM model (`mixin.py:360`, `mixin.py:536`). There is no support for model routing (e.g., use a fast model for tool selection, a powerful model for reasoning). The LLM is resolved once via `_resolve_llm()` and used for the entire conversation.

### 2. Synchronous tool discovery

`discover_tools()` (`tools.py:43-101`) reads schemas synchronously from `root._children`. It accesses in-memory class attributes, not the network. However, it calls `cls.schema()` which runs the full schema pipeline for each discovered actor. For applications with many actors (20+), this adds latency to every `agentic()` call.

Tool specs are not cached. Every `run()` invocation re-discovers tools from scratch.

### 3. Thread storage as single JSON blob

Thread messages are stored as a single `list` field serialized to JSON TEXT (`thread.py:52`). For long conversations (100+ messages), this creates large reads and writes on every turn. There is no message-level indexing, pagination, or incremental append.

### 4. No tool-level access control

Tool discovery filters out `user` parameters (`tools.py:170`) and propagates the user dict in TX meta (`tools.py:215`). But there is no mechanism for an agent to be restricted from specific tools based on the user's role. If a model's tools include `['users', 'products']`, the agent can call any CRUD operation on both, regardless of the user's access level.

Access control is enforced by the target actor's handler (Tier 2 auth in `ActorModel`), so unauthorized operations will fail. But the agent may waste LLM tokens attempting them before receiving an error.

### 5. No streaming backpressure

`run_stream()` yields chunks as fast as pydantic-ai produces them. There is no mechanism for the frontend to signal backpressure (slow down, pause). SSE is inherently one-directional. WebSocket streaming could support backpressure but is not implemented for agent streams.

### 6. Import ordering constraint

`n3tx_agents` must be imported **before** any model with `__agent__ = True` is defined (`__init__.py:16-18` calls `register_mixin`). If a model is defined before this import, the mixin is silently not injected. This is documented in CLAUDE.md but remains a footgun for new developers.

Evidence: `apps/veille/main.py:13` has the explicit comment `# CRITICAL: Must import n3tx_agents BEFORE model imports`.

---

## Feature Integration Guide

### Adding a New Agent-Powered Feature (End-to-End)

**Scenario**: Add a "summarize" streaming endpoint to an existing Product model.

#### Step 1: Enable Agent on the Model

```python
# models/product.py
class Product(ActorModel):
    __agent__ = {
        'self_tools': True,
        'tools': ['reviews'],  # optional: include review CRUD as tools
    }
    # ... existing fields ...
```

**Files**: Your model file only.
**Watch out for**: Import ordering. Ensure `import n3tx_agents` happens before your model is defined (in `main.py` or an early import).

#### Step 2: Add the Streaming Endpoint

```python
from n3tx_agents.actor import TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk

@expose_route('/summarize', methods=['POST'], stream=True, access=AUTHENTICATED,
              events={
                  'text': TextChunk, 'tool_call': ToolCallEvent,
                  'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
                  'done': DoneChunk,
              })
async def summarize(self, user=None):
    """Summarize this product. Streams agent reasoning."""
    task = f"Summarize product: {self.name}. Description: {self.description}"
    async for chunk in self.agentic_stream(task=task, user=user):
        yield chunk
```

**Files**: Your model file only.
**Pattern**: Always pass `user=user` through to `agentic_stream()` for auth context propagation.

#### Step 3: (Optional) Custom Frontend Renderer

```javascript
// static/components/ntx-product-summary.js
import { NTTStreamAgent } from './ntx-stream-agent.js';

class NTXProductSummary extends NTTStreamAgent {
    TOOL_CALL(data, meta) {
        if (data.tool?.includes('reviews_list')) {
            data = { ...data, tool: 'Reading reviews' };
        }
        super.TOOL_CALL(data, meta);
    }
}
customElements.define('ntx-product-summary', NTXProductSummary);
```

Wire it via `__ui__`:
```python
__ui__ = {
    'methods': {
        'summarize': {'renderer': 'ntx-product-summary'},
    },
}
```

**Files**: New JS file + model `__ui__` update.

#### Step 4: Test

```python
# tests/test_product_summarize.py
import pytest
from pydantic_ai.models.test import TestModel

@pytest.mark.asyncio
async def test_summarize_streams_chunks(setup_matrix_and_models):
    product = Product.create(Product(name="Test", description="A product"))
    chunks = []
    async for chunk in product.summarize(user={'user_id': 1, 'role': 'user'}):
        chunks.append(chunk)
    # Should get at least text + done chunks
    names = [c['name'] for c in chunks]
    assert 'done' in names
```

**Watch out for**: Tests need a live Matrix. Use the `fresh_matrix` fixture from `conftest.py`. Pass `llm=TestModel(call_tools=[])` to avoid real LLM calls.

---

## Comparison with Alternatives

### vs. LangChain/LangGraph

| Dimension | N3TX Agents | LangChain/LangGraph |
|-----------|------------|---------------------|
| Tool discovery | Automatic from model schemas | Manual tool definition |
| Streaming | TX-aligned chunks with typed events | Callback-based or LCEL streaming |
| State management | Actor system + StorableMixin | Memory classes, graph state |
| Multi-turn | Thread model (TX-shaped history) | ConversationBufferMemory, etc. |
| Framework coupling | Deep (requires N3TX stack) | Standalone (can use anywhere) |
| LLM abstraction | Pydantic-ai wrapper | Own LLM abstraction |

N3TX's approach is more opinionated and integrated but provides zero-config agent capabilities from model definitions alone. LangChain requires explicit tool and chain construction.

### vs. Direct pydantic-ai Usage

| Dimension | N3TX AgentMixin | Direct pydantic-ai |
|-----------|----------------|-------------------|
| Tool generation | Auto from schemas via `discover_tools()` | Manual `@agent.tool` decorators |
| Config cascade | 3-tier (global < model < call) | Manual per-agent |
| Streaming format | TX-aligned chunks | Raw pydantic-ai events |
| Auth propagation | Automatic via TX meta | Manual |
| Schema integration | Automatic (agent stage in pipeline) | None |

N3TX adds significant value on top of pydantic-ai: automatic tool generation, auth propagation, and schema-driven config. The cost is the coupling to pydantic-ai internals (especially `_agent_graph` for streaming).

### Migration Path: If Pydantic-AI Breaks

The `_agent_graph` dependency is the primary risk. If pydantic-ai v2+ changes its internal streaming API:

1. **Non-streaming path**: `agent.run()` is a public API — likely stable.
2. **Streaming path**: Would need to be rewritten. The chunk format (TX-aligned dicts) should be preserved as the public contract. Only the internal generation logic changes.
3. **Tool wrapping**: `pydantic_ai.tools.Tool` is a public API — likely stable.
4. **Thread serialization**: `ModelMessagesTypeAdapter` is public — likely stable.

Mitigation: Pin pydantic-ai version, monitor changelog, maintain a thin adapter layer around the streaming internals.

---

## Evolution Trajectory

### Git History Analysis

The agents subsystem evolved through clear phases:

1. **Package split** (`ae41a78`, `1f5842e`, `d108be1`): Moved from monolithic `src/n3tx/core/agents/` to `packages/n3tx-agents/`. Clean separation.

2. **Thread + Matrix.request()** (`10b4cdb`): Added Thread model, refactored mixin from adapter-based routing to `Actor.root().request()`. Simplified tool call routing.

3. **Rich streaming** (`1a13a99`, `a8ee099`): Replaced simple text streaming with graph-based streaming via `agent.iter()`. Added tool/thinking event types. This introduced the `_agent_graph` dependency.

4. **Frontend component hierarchy** (`75b22f4`, `cd247d4`, `4cf06e3`): Evolved from a `StreamActor` mixin to the `NTTStream -> NTTStreamAgent` class hierarchy. The UPPERCASE handler pattern emerged here.

5. **Stream events schema** (`55cd002`): Added `events=` parameter on `@expose_route` and ProtoModel event types. Formalized the stream contract.

6. **Application usage** (`7c649df`, `f22b6bf`, `5bab6d7`): Veille app drove feature development: multi-source scraping, grant analysis, custom event types.

### Current Direction

The trajectory is toward:
- **More domain-specific agent patterns**: The veille app shows models (Run, Grant) that compose agent capabilities with domain logic, rather than using AgentActor directly.
- **Richer stream rendering**: The frontend components are getting more sophisticated (NTXRunOutput with multi-phase rendering).
- **Custom event vocabularies**: Applications define their own event types beyond the core five.

### Sustainability Assessment

The trajectory is sustainable with one caveat: the pydantic-ai `_agent_graph` dependency. The rest of the architecture follows N3TX patterns cleanly: mixin injection, schema extension, actor routing, component hierarchy. The per-application customization layer (subclass + override) is well-proven.

The main risk is that pydantic-ai is still a young library (< 2 years). If it undergoes major API changes, the streaming path will need significant rework. The non-streaming path and tool generation are built on stable public APIs.

---

## Cross-Cutting Concerns

### Logging

All agents modules use Python's standard `logging` under the `n3tx.agents` namespace:
- `mixin.py:71`: `logger = logging.getLogger('n3tx.agents')`
- `actor.py:36`: `logger = logging.getLogger('n3tx.agents')`
- `tools.py:13`: `logger = logging.getLogger('n3tx.agents')`
- `thread.py:29`: `logger = logging.getLogger('n3tx.agents.thread')`

Key logging points:
- Tool discovery warnings for missing actors (`tools.py:71`)
- No-tools-discovered warning (`mixin.py:347`)
- Thread update failures (`mixin.py:403-407`, `mixin.py:656-660`)
- `run_stream()` errors are caught and yielded as error chunks (`mixin.py:685-691`), but **not** logged. This is a gap — errors in streaming are silently converted to stream events without backend log entries.

### Error Handling

Two distinct error handling strategies:

1. **Non-streaming (`run()`)**: Exceptions propagate normally. No try/catch wrapper. Callers (the HTTP route layer) handle errors.

2. **Streaming (`run_stream()`)**: A top-level try/except at `mixin.py:506-691` catches all exceptions and yields them as error chunks. This prevents unhandled exceptions from breaking the SSE connection but can mask bugs during development.

Tool call errors use pydantic-ai's `ModelRetry` (`tools.py:221`), which tells the LLM to retry with a different approach rather than crashing the agent loop.

### Configuration

Three-tier cascade (`config.AGENT_DEFAULTS < __agent__ dict < call kwargs`) is the central config pattern. Implemented in `agentic()` at `mixin.py:237-265`.

Global defaults are in `n3tx_core/config.py:31-36`:
```python
AGENT_DEFAULTS = {
    'self_tools': True,
    'neighbors': True,
    'neighbor_depth': 1,
    'llm': 'ollama:llama3.1',
}
```

Overridable via `N3TX_AGENT_DEFAULTS` env var (JSON string, `config.py:38-40`).

### Authentication

Auth propagation follows a clean chain:

1. HTTP layer extracts JWT and injects `user` into `@expose_route` method kwargs.
2. Model method passes `user` to `agentic_stream(user=user)`.
3. `agentic_stream()` passes it to `run_stream(user=user)`.
4. `run_stream()` stores it in `AgentDeps(user=user)` (`mixin.py:538-540`).
5. Tool functions access it via `ctx.deps.user` (`deps.py:21`).
6. `_route_tool_call()` includes it in TX meta: `meta={'user': ctx.deps.user}` (`tools.py:215`).
7. Target actor's handler receives the user in `tx.meta['user']` for Tier 2 auth.

This is complete and traceable. No auth information is lost between the HTTP boundary and the tool execution boundary.

### Serialization

Three serialization layers interact:

1. **Pydantic model serialization**: `model_dump()` for instance context in `_build_instance_text()` (`mixin.py:117-118`).
2. **JSON Schema serialization**: `run_pipeline(cls, pipeline='llm')` for LLM context (`mixin.py:109`).
3. **TX serialization**: Tool call results are `json.dumps(response.data, default=str)` (`tools.py:222`). Thread messages use `ModelMessagesTypeAdapter.dump_python(mode='json')` (`thread.py:92`).

The `default=str` fallback in tool result serialization (`tools.py:222`) is a pragmatic choice — it prevents crashes on non-serializable types but can produce lossy output (e.g., datetime objects become strings without timezone info). The same pattern appears in `actor.py:168` where `agentic()` returns `json.dumps(result, default=str)`.

### Testing

Test infrastructure in `tests/conftest.py:12-31` provides:
- `reset_actor_state`: Autouse fixture that isolates Matrix/Actor state between tests.
- `fresh_matrix`: Creates an isolated Matrix instance.
- `memory_storage`: In-memory SQLite for fast tests.

Tests use `pydantic_ai.models.test.TestModel` for deterministic LLM behavior:
```python
result = await Product.agentic(task='Test', llm=TestModel(call_tools=[]))
```

Test coverage spans: mixin methods (`test_mixin.py`), tool discovery and generation (`test_tools.py`), AgentActor CRUD (`test_agent_actor.py`), Thread persistence (`test_thread.py`), streaming first-token (`test_run_stream_first_token.py`), and tool call auth (`test_tool_call_auth.py`).

Missing test coverage: the LLM pipeline (`schema_ext.py:58-101`), `_resolve_llm()` edge cases, and `AgentActor._resolve_tool_addrs()` with mixed href/instance formats.
