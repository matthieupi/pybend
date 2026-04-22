# Streaming Distill Design

## Summary

The streaming subsystem should become one public capability with one public event contract, regardless of whether the backend executes through direct SSE, actor/TX routing, or agent-specific tooling. The core recut is to keep TX as the private transport substrate, add a normalization layer that emits `{name, data, meta}` before UI dispatch, and treat agent streaming as a vocabulary on top of generic streaming instead of as a parallel system.

This keeps `stream=True` as the primary authoring affordance, reduces transport leakage into frontend components, and turns `NTTStream` / `NTTStreamAgent` into a clean generic/specialized pair rather than overlapping implementations.

## Entropy Reduction

Before: 18 concepts

- `stream=True`
- `events=`
- Level 1/2 direct SSE wrappers in `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- Level 3 SSE translation in `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- TX stream meta (`req`, `stream`, `seq`, `stream_end`, `error`)
- `TX.chunk()` / `TX.end()` in `packages/n3tx-actors/src/n3tx_actors/tx.py`
- `NetworkAdapter.stream()` queue correlation in `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py`
- WebSocket stream translation in `packages/n3tx-actors/src/n3tx_actors/api/network_ws.py`
- HTTP SSE parsing in `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js`
- transport branching in `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js`
- dynamic handler aliasing in `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js`
- generic stream UI state in `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js`
- agent event models in `packages/n3tx-agents/src/n3tx_agents/actor.py`
- `AgentMixin.run_stream()` in `packages/n3tx-agents/src/n3tx_agents/mixin.py`
- `AgentActor.agentic_stream()` override in `packages/n3tx-agents/src/n3tx_agents/actor.py`
- `NTTStreamAgent` agent rendering in `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`
- duplicated live/chat agent renderers in `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` and `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`
- public agent naming overlap (`agentic`, `run`, `agentic_stream`, `run_stream`)

After: 8 concepts

- stream declaration: `@expose_route(..., stream=True)`
- one public stream event shape: `{name, data, meta}`
- optional event vocabulary declaration/inference for schema and UI hints
- one stream normalization layer above transports
- TX as private, documented transport infrastructure
- `NTTStream` as the generic stream primitive
- `NTTStreamAgent` as the semantic specialization for agent vocabularies
- one public agent verb pair at most: one request/response verb and one streaming verb

## The Design

### 1. Public contract: one event shape everywhere

All backend-authored streaming visible to application code and UI should normalize to:

```json
{
  "name": "text",
  "data": {"text": "hello"},
  "meta": {"seq": 3}
}
```

Rules:

- `name` is the semantic event name, not the transport message type.
- `data` is the payload for that semantic event.
- `meta` is public stream metadata only: sequence, completion, diagnostic hints, correlation fields that are safe for consumers.
- UI and app components never consume raw TX envelopes or transport-specific SSE/WS framing.

This matches the shape already yielded by `AgentMixin.run_stream()` in `packages/n3tx-agents/src/n3tx_agents/mixin.py:472`, but makes it the universal public shape instead of an agent-only convention.

### 2. Private transport: TX stays internal and documented

TX remains the transport substrate for actor-routed streaming:

- `TX.chunk()` / `TX.end()` remain the backend correlation and transport helpers in `packages/n3tx-actors/src/n3tx_actors/tx.py`.
- `NetworkAdapter.stream()` remains the queue-based bridge in `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py`.
- `req`, `stream`, `seq`, `stream_end`, and `error` remain internal wire semantics.

But TX stops being the public stream API. It should be documented as framework internals and debugging infrastructure, not what components are expected to parse directly.

### 3. Add a stream normalization layer above transports

Introduce a normalization layer that sits above direct SSE / actor SSE / WebSocket transport output and below frontend component dispatch.

Responsibilities:

- convert Level 1/2 direct async-generator chunks from `routes_fastapi.py` into `{name, data, meta}`
- convert Level 3 SSE chunks from `_sse_from_stream()` in `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` into the same shape before they leave the backend or immediately on the frontend transport boundary
- convert WebSocket stream messages from `packages/n3tx-actors/src/n3tx_actors/api/network_ws.py` into the same shape before Matrix/UI dispatch
- normalize terminal conditions so completion and errors are expressed consistently

Target behavior:

- `chunk` SSE frames become one normalized event object
- `done` SSE frames become one normalized event object, usually `{name: 'done', data: ..., meta: {stream_end: true, ...}}`
- error frames become `{name: 'error', data: {message, code?}, meta: {error: true, stream_end: true?}}`

The important design decision is architectural, not placement-specific: transports may keep different wire details, but the system must have exactly one place that turns them into the public stream contract before UI sees them.

### 4. Keep `stream=True` as the primary declaration surface

`stream=True` remains the main public marker because it is already the routing and schema switch in:

- `packages/n3tx-core/src/n3tx_core/utils/decorators.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

Refinement:

- move toward inferred streaming when the decorated function is an async generator, with `stream=True` still supported explicitly
- keep `events=` optional and advanced
- if `events=` is omitted, the method still streams correctly and exposes a generic stream capability in schema
- if `events=` is present, it remains a schema/UI aid, not mandatory mental overhead for ordinary streaming methods

For agent streams, default event vocabularies should be available without repeating the same inline mapping in each surface.

### 5. Unify route-level streaming behavior

The direct FastAPI path in `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py:340` and `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py:388` currently emits bare chunk payloads and lacks symmetric error handling. The actor-routed path in `packages/n3tx-actors/src/n3tx_actors/api/network_api.py:469` emits full TX envelopes.

Target behavior for both paths:

- both produce the same normalized public event object
- both send explicit error events on stream failure
- both send explicit terminal events
- neither requires frontend format sniffing by routing level

This is the highest-leverage entropy reduction because it removes the Level 1/2 vs Level 3 mental branch.

### 6. WebSocket should match the same public stream contract

Current code in `packages/n3tx-actors/src/n3tx_actors/api/network_ws.py:207` already has a translation step, which means WebSocket has no obvious architectural blocker to matching the same normalized shape. The design assumes WS can and should emit the same public `{name, data, meta}` event shape seen by SSE consumers.

Implementation intent:

- keep WS correlation and routing internals intact
- normalize outbound stream messages to the same public event contract used by SSE
- make `Socket.js`, `HTTP.js`, and `NetworkAdapter.js` deliver identical stream objects into frontend Matrix/component dispatch

Human confirmation is still needed through integration verification because current WS behavior preserves more TX-ish metadata than the final public contract should expose.

### 7. Recut frontend streaming around one primitive and one specialization

`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js` should remain the generic primitive.

Responsibilities of `NTTStream`:

- invoke a streaming method
- own lifecycle, cancellation state, and generic output area
- accept normalized `{name, data, meta}` events only
- dispatch semantic events consistently
- provide simple default behavior for plain text / generic chunks

`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` should become a true semantic specialization.

Responsibilities of `NTTStreamAgent`:

- define shared agent stream semantics (`thinking`, `tool_call`, `tool_result`, `text`, `done`, `error`)
- own progressive text/thinking rendering, tool cards, footer stats, and markdown behavior
- expose hooks so leaf components reuse semantics without copying handler code

`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` and `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js` should stop extending `NTTStream` directly as a pattern. They should become thin wrappers over `NTTStreamAgent` or a renderer core hosted there.

### 8. Remove transport-aware app components as a pattern

No app-facing component should care whether the stream arrived via:

- direct SSE
- actor/TX SSE
- WebSocket

That means:

- no route-level envelope sniffing in leaf components
- no TX-envelope assumptions in `NTTStream` subclasses
- no stream UI code that branches by transport or routing level
- transport selection remains in transport/adapter code only

The current transport-aware branch in `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js:150` is the right layer to absorb differences; it should become normalization-and-dispatch plumbing, not a source of component-visible format differences.

### 9. Agent streaming is one vocabulary on top of generic streaming

Agent streaming is not a separate subsystem. It is one named event vocabulary layered on the generic stream contract.

Default agent vocabulary:

- `thinking`
- `tool_call`
- `tool_result`
- `text`
- `done`
- `error`

The existing models in `packages/n3tx-agents/src/n3tx_agents/actor.py:41` should become a reusable default vocabulary helper rather than being incidental inline definitions attached to `AgentActor.agentic_stream()`.

This keeps agent behavior schema-visible while reducing duplication between backend method declarations and frontend agent renderers.

### 10. Collapse public agent API naming

Streaming design should align with the agent distill direction already captured in `.traces/features/agents-distill/design.md`: the public surface should expose one non-streaming verb and one streaming verb at most.

Recommended public pair:

- non-streaming: `agentic`
- streaming: `agentic_stream`

Implications:

- `run()` and `run_stream()` remain engine-level helpers or advanced/internal surfaces
- docs, schema affordances, examples, and UI defaults should point to the public pair only
- `AgentActor` should stop carrying a parallel policy/config path that bypasses shared mixin semantics where possible

## Constraints

- The backend schema remains authoritative, so stream capability and event vocabulary must stay schema-visible.
- TX must remain inspectable and documented for framework internals and debugging.
- `stream=True` is already the least-surprising declaration surface and should not be replaced by a more complex typed API.
- `events=` should stay optional/advanced rather than becoming required ceremony for simple streams.
- The design prefers recutting `NTTStream` / `NTTStreamAgent`, not deleting them.
- Existing direct, actor-routed, and agent streaming must coexist during migration; this is a normalization exercise, not a flag day rewrite.
- WebSocket should conform to the same public contract unless integration verification exposes a blocker.
- Existing tests show current behavior that the design must preserve internally: queue correlation in `NetworkAdapter.stream()`, async-generator handling in `ActorModel.handler()`, and first-token handling in `AgentMixin.run_stream()`.

## Migration Path

### Phase 1 - Normalize the contract without deleting infrastructure

- introduce a shared stream-normalization utility and define the canonical public event object
- make SSE paths emit normalized events consistently for direct and actor routing
- make frontend transport code consume one normalized event contract
- add tests that assert the same public event shape across Level 1/2 SSE, Level 3 SSE, and WS

### Phase 2 - Make declaration simpler, not broader

- keep `stream=True` as the visible authoring surface
- support inference for async-generator handlers so Level 1/2 and Level 3 do not diverge on declaration semantics
- make `events=` optional and add a default vocabulary helper for agent streams
- document `events=` as schema/UI enrichment rather than required runtime ceremony

### Phase 3 - Recut frontend primitives

- simplify `NTTStream` to normalized-event dispatch plus generic lifecycle/cancel behavior
- move shared agent semantics into `NTTStreamAgent`
- convert `ntx-agent-live` and `ntx-chat` into thin wrappers over the shared agent specialization
- remove transport-aware stream handling from leaf components

### Phase 4 - Collapse public naming and docs

- present one public agent verb pair only
- demote `run()` / `run_stream()` to engine-level/internal guidance
- update schema/UI affordances, examples, and docs to the public pair
- keep compatibility shims until downstream usage has moved

### Phase 5 - Optional hardening after behavioral unification

- add server-side handling for `STREAM_CANCEL` so cancel becomes real, not advisory
- centralize stream timeout configuration
- consider schema-driven fallback rendering for unknown event names once the public contract is stable

## Files Affected

| File | Change | Scope |
|---|---|---|
| `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` | Normalize direct SSE output to `{name, data, meta}` and emit explicit error/end events | direct HTTP streaming |
| `packages/n3tx-core/src/n3tx_core/utils/decorators.py` | Keep `stream=True` primary, support inferred async-generator streaming, keep `events=` optional | declaration surface |
| `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` | Replace raw TX-envelope SSE output with normalized public stream events or call the shared normalizer | actor HTTP streaming |
| `packages/n3tx-actors/src/n3tx_actors/api/network_ws.py` | Normalize outbound WS stream messages to the same public event shape | websocket transport |
| `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py` | Keep queue/TX internals, possibly host shared stream normalization helpers for adapter outputs | transport core |
| `packages/n3tx-actors/src/n3tx_actors/tx.py` | Keep TX stream helpers documented as private/internal transport primitives | transport contract |
| `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py` | Preserve async-generator wrapping while aligning chunk/end behavior with the public event contract expectations | actor runtime |
| `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js` | Parse SSE into normalized event objects only, with consistent done/error semantics | frontend SSE transport |
| `packages/n3tx-core/src/n3tx_core/static/core/transport/Socket.js` | Ensure WS messages flow through the same normalized event path | frontend WS transport |
| `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js` | Introduce response normalization above transport choice and remove stream-format branching from component callers | frontend transport adapter |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js` | Recut as the generic normalized-event stream primitive; remove transport-shaped assumptions | generic stream UI |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` | Become the shared semantic specialization for agent stream vocabularies | agent stream UI core |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` | Thin wrapper over `NTTStreamAgent` semantics instead of duplicated handler stack | live monitor UI |
| `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js` | Thin wrapper over `NTTStreamAgent` semantics instead of duplicated handler stack | chat UI |
| `packages/n3tx-agents/src/n3tx_agents/mixin.py` | Keep `run_stream()` as engine outputting canonical public events; align docs and defaults with normalized contract | agent runtime |
| `packages/n3tx-agents/src/n3tx_agents/actor.py` | Extract a reusable default agent event vocabulary helper and stop treating agent streaming as a parallel contract | persisted agent model |
| `docs/AGENTS.md` | Reframe agent streaming as one vocabulary on generic streaming and demote internal surfaces | cross-cutting docs |
| `docs/ACTORS.md` | Keep TX stream semantics documented as internal transport/debugging infrastructure | cross-cutting docs |
| `FRONTEND.md` | Update frontend streaming docs around normalization and `NTTStream` / `NTTStreamAgent` roles | agent/frontend docs |
| `BACKEND.md` | Update backend streaming docs around one public event contract and one private TX layer | backend docs |

## Assumptions Requiring Human Confirmation

- The preferred public agent verb pair is `agentic` / `agentic_stream`; if product/docs want `run` / `run_stream` instead, naming guidance changes but the streaming architecture does not.
- WebSocket can be normalized to the same public shape without exposing a hidden blocker in existing frontend Matrix correlation; source review suggests no blocker, but this still needs integration verification.
- `events=` should remain schema/UI enrichment only; if strict runtime validation per chunk is desired, the implementation plan needs an additional validation layer and performance review.
- `done` should remain the canonical terminal semantic event name for public consumers; if the team wants transport-neutral completion without a named semantic event, UI dispatch rules would change slightly.
- The normalization layer can live either server-side, client-side transport-side, or split across both as long as UI sees one contract; the design is strict about the contract boundary, not the exact code location.
