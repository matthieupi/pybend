# Agents Distilled Design

## Summary

The agents subsystem should be presented as one capability: an actor/model that can reason with a prompt, tools, and conversation state. The existing class-configured path (`__agent__`) and instance-configured path (`AgentActor`) both remain, but they converge on one execution contract centered on `agentic()` and `agentic_stream()`.

This design reduces the visible surface area without removing needed flexibility. It keeps transparency, preserves inspection and audit needs, and recuts the boundary so storage shape, frontend rendering, streaming, and config precedence all line up behind one mental model.

## Entropy Reduction

Before: 9 concepts

- class-configured agents (`__agent__` + `AgentMixin`)
- instance-configured agents (`AgentActor`)
- separate `AgentTool` persistence model
- separate `Thread` CRUD surface for conversation history
- mixed config rules across defaults, class config, instance fields, and call kwargs
- broad public execution surface (`ctx`, `tools`, `agentic`, `run`, streaming variants)
- ad hoc default stream event vocabulary in `actor.py`
- duplicated frontend agent renderers (`ntx-stream-agent`, `ntx-agent-live`, `ntx-chat`)
- import-order-dependent mixin registration

After: 6 concepts

- one agent capability with two config sources
- typed `AgentConfig` with one precedence rule: defaults < class < instance < call
- primary execution contract: `agentic()` and `agentic_stream()`
- embedded `ToolRef { target, description }` value shape
- narrow `Conversation` audit/admin surface keyed by `conversation_id`
- shared frontend agent renderer core plus thin wrappers, using one standard stream event vocabulary

## The Design

### 1. One capability, two configuration sources

Recast the subsystem around a single concept: "agent capability". A model is agent-capable when its schema exposes an explicit top-level `agent` marker and it can execute the shared agent contract.

Two configuration sources remain:

- **Class-configured agents**: models with `__agent__` enabled and optional class-level config.
- **Instance-configured agents**: persisted agent records such as `AgentActor` (or an equivalent persisted record type) with per-record config.

These are not separate capabilities. They are two ways to source `AgentConfig`.

### 2. A single typed config object

Introduce a typed `AgentConfig` that normalizes what is currently spread across `config.AGENT_DEFAULTS`, `__agent__`, `AgentActor` fields, and call kwargs.

Canonical fields:

- `prompt: str`
- `tools: list[ToolRef] | list[str]` during migration, normalized to `list[ToolRef]`
- `llm: str | model`
- `constraints: dict`
- `result_type: type | None`
- optional discovery flags that remain safe to expose in schema

One explicit precedence rule applies everywhere:

`defaults < class config < instance config < call overrides`

This precedence should be implemented once and shared by both `agentic()` and `agentic_stream()`. `AgentActor` should stop bypassing the mixin policy layer with its own parallel config resolution; instead, it should contribute instance config into the same merge path.

### 3. Public API hierarchy

Keep these public for now:

- `ctx()`
- `tools()`
- `agentic()`
- `run()`
- `agentic_stream()`
- `run_stream()`

But the subsystem should document a clear hierarchy:

- **Primary API**: `agentic()` and `agentic_stream()`
- **Advanced/high-entropy API**: `ctx()`, `tools()`, `run()`, `run_stream()`, and similar lower-level helpers

Implementation and docs should consistently steer normal usage to the primary pair. The advanced surfaces remain available for debugging, extension, and experimentation, but are explicitly not the first mental model.

### 4. Schema contract

Keep a minimal top-level schema capability marker. Do not rely on inferring agent capability only from method names.

Target shape:

```json
{
  "agent": {
    "enabled": true,
    "mode": "class" | "instance",
    "primary_methods": ["agentic", "agentic_stream"]
  }
}
```

`AgentActor`-style schemas may continue to expose an execution endpoint pattern, but the marker should stay minimal and capability-oriented.

### 5. Tools: value object, not app-domain model

The target design is an embedded tool reference value object:

```json
{
  "target": "grants",
  "description": "Grant CRUD and search"
}
```

Call this `ToolRef`. Preserve per-tool description. Treat it as agent configuration, not as a first-class app-domain entity.

Implications:

- `discover_tools()` should accept normalized `ToolRef` inputs.
- persisted agents should store tools inline as config data rather than through a join-table-oriented domain model.
- `AgentTool` can remain temporarily as a compatibility shim for migration and hydration, but it is not the target public concept.

### 6. Conversations: narrow system-owned surface

Conversation history remains persisted and queryable, but it moves conceptually out of ordinary CRUD.

Normal execution flow should center on `conversation_id`:

- callers pass or receive a `conversation_id`
- the agent runtime loads history, appends messages, and persists it
- lifecycle/plumbing stays hidden behind the agent execution layer

The persisted conversation store should still be inspectable and exportable for transparency, audit, admin, and support tooling. But its surface should be narrow and system-owned: admin/audit/export/read, not ordinary app-domain list/create/update/delete usage.

This is a recut, not a removal. The system keeps durable history while reducing the number of concepts application developers must hold.

### 7. Streaming contract

Standardize one public default stream event vocabulary helper/primitive for agent streams. The current built-in event models in `packages/n3tx-agents/src/n3tx_agents/actor.py` prove the vocabulary, but they should become an explicit reusable contract rather than an incidental implementation detail attached to `AgentActor`.

Default vocabulary:

- `thinking`
- `tool_call`
- `tool_result`
- `text`
- `done`
- `error`

Provide one helper that returns the schema/event mapping used by default agent streams so both backend and frontend bind to the same contract.

### 8. Frontend recut

There is already a partial shared core in `ntx-stream-agent.js`, but `ntx-agent-live.js` and `ntx-chat.js` still duplicate agent-stream rendering logic while extending `NTTStream` directly.

Target frontend shape:

- one shared agent renderer core for event handling, progressive text/thinking rendering, tool cards, footer stats, and error handling
- thin wrappers for embedded method output, live activity, and chat-specific chrome

This preserves specialized UX while collapsing duplicated stream semantics.

### 9. Registration and failure mode

Remove the import-order footgun around `register_mixin('__agent__', AgentMixin)`.

Acceptable target behaviors:

- **preferred**: lazy registration / deferred mixin binding so `__agent__` works regardless of import order
- **minimum**: loud failure when a model declares `__agent__` before the agent package has registered the mixin

The current silent failure mode is the one outcome the design should eliminate.

## Constraints

- The project philosophy favors one clear model per capability, but also preserves real boundaries when storage or replacement concerns differ.
- Current code already proves that class-configured and instance-configured agents share one execution engine; the redesign should amplify that truth rather than fork it further.
- Transparency matters: conversations, tool descriptions, schemas, and stream events must remain inspectable.
- The backend schema remains authoritative, so the agent capability marker and default stream vocabulary must stay schema-visible.
- Existing public helpers and examples use `ctx()`, `tools()`, `run()`, and streaming internals; demotion must be rhetorical first, not immediately breaking.
- The migration must respect existing persisted data (`AgentTool`, `Thread`) and existing consumers in examples/apps.

## Migration Path

### Phase 1 - Normalize without breaking APIs

- add `AgentConfig` and centralize precedence resolution
- route both class-configured and instance-configured execution through the same policy merge path
- keep `AgentTool` and `Thread`, but treat them as legacy persistence backing
- add a shared default stream event helper and point `AgentActor.agentic_stream()` at it
- add a loud failure mode for unregistered `__agent__`

### Phase 2 - Recut persistence and schema

- introduce `ToolRef` normalization and allow persisted agents to read/write embedded tools
- narrow thread/history access behind a conversation-oriented service/surface and rename the public concept to `conversation_id`
- simplify schema `agent` output to the minimal capability marker plus primary methods

### Phase 3 - Frontend consolidation

- extract shared agent renderer behavior from `ntx-stream-agent.js`, `ntx-agent-live.js`, and `ntx-chat.js`
- convert live/chat wrappers to the shared core
- keep existing custom elements as thin entry points for compatibility

### Phase 4 - Compatibility cleanup

- retain shims for `AgentTool` and thread CRUD export paths as needed
- update docs/examples toward `agentic()` / `agentic_stream()` and `conversation_id`
- once downstream usage is migrated, demote legacy surfaces in docs and optionally hide them from default schema/UI affordances

## Files Affected

| File | Change | Scope |
|---|---|---|
| `packages/n3tx-agents/src/n3tx_agents/mixin.py` | Centralize `AgentConfig` merge, keep `agentic()`/`agentic_stream()` as policy entrypoints, demote lower-level surfaces in docs/API guidance | core runtime |
| `packages/n3tx-agents/src/n3tx_agents/actor.py` | Stop parallel config logic, normalize persisted config into shared contract, replace inline default event declaration with shared helper | persisted agent model |
| `packages/n3tx-agents/src/n3tx_agents/tools.py` | Accept normalized `ToolRef` input shape, preserve per-tool description, keep compat for `AgentTool`-backed records during migration | tool discovery |
| `packages/n3tx-agents/src/n3tx_agents/tool_model.py` | Recast as compatibility shim or migration bridge rather than target public model | legacy persistence |
| `packages/n3tx-agents/src/n3tx_agents/thread.py` | Recut from ordinary thread CRUD concept toward narrow conversation/audit surface keyed by `conversation_id` | history persistence |
| `packages/n3tx-agents/src/n3tx_agents/schema_ext.py` | Keep explicit top-level `agent` marker, reduce it to minimal capability metadata, expose primary methods consistently | schema contract |
| `packages/n3tx-agents/src/n3tx_agents/__init__.py` | Remove import-order footgun via lazy registration or enforce loud failure mode | package bootstrap |
| `packages/n3tx-core/src/n3tx_core/models/proto_model.py` | Support lazy mixin registration or explicit failure when flagged capabilities are unavailable at class definition time | mixin injection |
| `packages/n3tx-core/src/n3tx_core/config.py` | Align `AGENT_DEFAULTS` with typed `AgentConfig` defaults | global defaults |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` | Become the shared renderer core (or host it) for agent stream semantics | frontend core |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` | Thin wrapper over shared renderer core | frontend live view |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js` | Thin wrapper over shared renderer core | frontend chat view |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js` | Align embedded activity view with consolidated renderer assumptions | frontend entity view |
| `docs/AGENTS.md` | Rewrite subsystem docs around one capability, two config sources, and `conversation_id`-centered execution | cross-cutting docs |
| `packages/n3tx-agents/docs/mixin.md` | Reframe advanced vs primary API surfaces and document `AgentConfig` precedence | package docs |
| `packages/n3tx-agents/docs/agent-actor.md` | Reframe persisted agents as one config source for the shared capability; document `ToolRef` migration | package docs |
| `packages/n3tx-agents/docs/tool-discovery.md` | Update discovery inputs, `ToolRef`, and default event vocabulary helper | package docs |
