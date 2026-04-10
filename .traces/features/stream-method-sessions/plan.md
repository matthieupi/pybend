# Stream Method Sessions Plan

## Goal

Add a generic, resumable session layer for all `ProtoModel` / `ActorModel`
methods declared with `stream=True`, so users can navigate away from a live
streaming view and come back to the same in-flight session without losing
progress.

This plan replaces Veille-specific recovery logic with a framework-level
abstraction that works for `Grant.analyze`, `Run.execute`, agent live streams,
and any future streaming method exposed through `@expose_route(..., stream=True)`.

## Why

Current streamed methods are UI-bound:

- `ntx-stream` and `ntx-stream-agent` keep live stream state in component memory
- rerouting destroys the component and loses buffered output
- the backend may continue running, but the user cannot reconnect to the live task
- Veille exposes this clearly with `Grant/<id>/analyze`

The goal is to make resumability a property of the framework, not a special case
in one app.

## Non-Goals For Wave 1

- no DB persistence for stream sessions
- no restart recovery across server restarts
- no multi-node shared session store
- no generic historical task browser UI yet
- no deep cancellation semantics beyond the current best-effort behavior

## Design Principles

- one route grammar, one router, one streaming contract
- runtime orchestration belongs in a dedicated subsystem, not on model classes
- replayed events and live events must use the same frontend path
- session reuse must be auth-scoped
- the generic feature should work for both direct routing and actor routing
- Veille should consume the framework feature, not fork it

## User-Facing Behavior

For any streaming method route such as `Grant/12/analyze`:

- first visit starts a session if none exists
- revisiting the same route while the stream is active reopens the same session
- the view replays buffered events, then continues following live events
- users do not accidentally start duplicate sessions by simple navigation
- when the session completes, the final state remains available until session TTL expiry

## Session Model

Introduce an in-memory runtime object, not a storable model in wave 1.

Suggested fields:

- `id`
- `target_ref` - e.g. `Grant/12`, `Run/4`, `AgentActor/3`
- `model`
- `entity_id`
- `method`
- `user_key`
- `status` - `pending`, `running`, `done`, `error`, `cancelled`
- `created_at`
- `started_at`
- `completed_at`
- `request_args`
- `events` - normalized buffered event list
- `seq`
- `result`
- `error`
- `subscriber_count`
- `last_seen_at`

Wave 1 uniqueness rule:

- one active session per `(user_key, target_ref, method)`

This supports the desired "leave and come back" behavior without introducing
accidental duplicate runs.

## Event Model

Do not invent a second event protocol.

Store and replay the same normalized event payload the frontend already consumes:

- stream event kind (`chunk`, `done`, `error`)
- inner TX-ish payload or normalized `{name, data, meta}` chunk
- session id
- sequence number

Replayed events must pass through the same `STREAM()` handler path as live events.

## Backend Architecture

### New subsystem: MethodSessionRegistry

Add a dedicated backend runtime service, not class state on `ProtoModel`.

Responsibilities:

- create or reuse active sessions
- append normalized stream events
- expose snapshots for reconnecting clients
- provide async follow/replay generators for SSE
- mark sessions `done` / `error` / `cancelled`
- enforce bounded event retention and TTL cleanup

Suggested public API:

- `get_active(user_key, target_ref, method)`
- `create_or_reuse(user_key, target_ref, method, request_args=None, force_new=False)`
- `start(session_id)`
- `append(session_id, event)`
- `complete(session_id, result=None)`
- `fail(session_id, error)`
- `snapshot(session_id)`
- `follow(session_id, after_seq=0)`
- `cancel(session_id)`
- `list_active(user_key=None, model=None, method=None)`
- `prune()`

### Generic session endpoints

Add framework-level endpoints under `/_sessions`:

- `GET /_sessions/active?target_ref=Grant/12&method=analyze`
- `GET /_sessions/{session_id}`
- `GET /_sessions/{session_id}/stream?after=17`
- `POST /_sessions/{session_id}/cancel`

Auth rules:

- only the owning authenticated user may inspect or follow a session
- anonymous access should not be allowed for active session APIs

### Streaming route integration

Any method exposed with `stream=True` should:

1. compute `target_ref`
2. compute `user_key`
3. look up or create the active session
4. wrap the underlying async generator so each chunk is:
   - normalized
   - appended to the registry
   - emitted to the current SSE response
5. mark terminal state on success or failure

Important:

- the original method route remains the invocation entrypoint
- `/_sessions/{id}/stream` becomes the reconnect entrypoint

### Session ownership and identity

Preferred `user_key` in wave 1:

- authenticated user id if present
- reject session creation/follow for unauthenticated users rather than trying to share public sessions

This keeps semantics simple and avoids leaking active work between users.

## Frontend Architecture

### Generic session client

Add a small runtime helper for session discovery and follow:

- `getActiveSession(ref, method)`
- `getSession(sessionId)`
- `followSession(sessionId, { after })`
- `cancelSession(sessionId)`

This should be a tiny client module, not embedded in a single component.

### `ntx-method` ref support

Strengthen `ntx-method` so routed action renderers can initialize from `ref`.

Needed behavior:

- accept `ref="Grant/12"`
- derive `model="Grant"` and `uuid="12"`
- keep explicit `model` / `uuid` behavior unchanged

This is required for routed action components mounted by `ntx-router`.

### `ntx-stream` session awareness

Upgrade `ntx-stream` to support resumable sessions.

Suggested behavior:

- new attributes/state:
  - `session-id`
  - `resume="auto|always|never"` (default `auto`)
  - internal `lastSeq`
- before starting a fresh stream:
  - ask backend for active session for `(ref, method)` when resume mode allows it
- if active session exists:
  - fetch snapshot
  - replay buffered events through `STREAM()`
  - connect to `/_sessions/{id}/stream?after=<lastSeq>`
- if no session exists:
  - call the streaming method route
  - capture returned session id
  - switch to follow mode

The component should not maintain separate rendering paths for live vs replay.

### `ntx-stream-agent`

`ntx-stream-agent` should inherit the resumable behavior from `ntx-stream`.

Validation goals:

- replayed `THINKING`, `TOOL_CALL`, `TOOL_RESULT`, `TEXT`, `DONE` render correctly
- session resume does not duplicate footer or tool cards incorrectly
- terminal states remain visually correct after remount

### Router contract

No new route grammar is required.

Canonical routes remain:

- home: `''`
- model list: `Grant?allow-create=`
- model detail: `Grant/12`
- action route: `Grant/12/analyze`
- app route: `@profile`

The difference is that action renderers become session-aware rather than fire-and-forget.

## Veille Plan

Veille should consume the generic framework feature with minimal app glue.

### Canonical routes

- dashboard: `''`
- grants: `Grant?allow-create=`
- sources: `Source?view=table&allow-create=`
- run report: `Run/<id>/report`
- analyze: `Grant/<id>/analyze`

### Veille-specific outcome

- `Grant/<id>/analyze` reopens the existing active session instead of starting a duplicate
- dashboard/sidebar/topbar routes stop depending on lowercase custom hashes
- leaving and returning to an analysis becomes safe and generic

## File-by-File Implementation Plan

### 1. New backend registry module

File:

- `packages/n3tx-core/src/n3tx_core/stream_sessions.py`

Add:

- `MethodSession` runtime data object
- `MethodSessionRegistry`
- singleton registry accessor
- bounded event buffer and TTL pruning logic

Notes:

- keep implementation explicit and inspectable
- avoid clever concurrency machinery; use plain asyncio queues for followers if needed

### 2. New session API routes

File:

- `packages/n3tx-core/src/n3tx_core/api/session_routes.py`

Add:

- active lookup endpoint
- snapshot endpoint
- SSE follow endpoint
- cancel endpoint

Notes:

- keep route registration separate from CRUD route generation
- use the same auth extraction pattern as other FastAPI routes

### 3. Direct routing stream integration

File:

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

Changes:

- extract stream handling into reusable helpers
- when `inspect.isasyncgen(result)`:
  - compute `target_ref`
  - create or reuse active session
  - normalize chunks and append to session registry
  - emit SSE with session metadata
- ensure both instance and class-level streaming methods are supported

Preferred target ref rules:

- instance method: `ModelName/<id>`
- class-level stream: `ModelName`

Notes:

- do not break existing non-streaming behavior
- keep response shape predictable for the frontend

### 4. Actor routing stream integration

File:

- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`

Changes:

- mirror the same session creation/reuse and event buffering behavior in `_add_streaming_handler()` and `_sse_from_stream()`
- keep parity with direct routing

Notes:

- if scope pressure is high, implement this immediately after direct routing but keep the API identical

### 5. Frontend session client module

File:

- `packages/n3tx-core/src/n3tx_core/static/core/stream-sessions.js`

Add:

- thin fetch/EventSource helpers for session APIs
- no DOM logic

### 6. Generic method ref support

File:

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`

Changes:

- add `ref` to `observedAttributes`
- derive `model` and `uuid` from `ref`
- preserve existing explicit attribute behavior

### 7. Generic resumable streaming component

File:

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js`

Changes:

- add session lookup before stream start
- add replay + follow mode
- store `session-id` and `lastSeq`
- route cancel through session API when present
- continue using existing `STREAM()` dispatch for both replayed and live chunks

### 8. Agent streaming compatibility

Files:

- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`

Changes:

- validate replay compatibility
- remove any duplicate ad hoc `ref` parsing that becomes unnecessary
- optionally surface a resumed status indicator

### 9. Veille route cleanup and adoption

Files:

- `apps/veille/static/index.html`
- `apps/veille/static/components/ntx-run-panel.js`
- `apps/veille/static/components/ntx-grant-item.js`
- `apps/veille/static/components/ntx-run-output.js`
- `apps/veille/static/components/ntx-run-report.js`
- `apps/veille/static/components/veille-routes.js` (new)
- `apps/veille/models/run.py`

Changes:

- remove lowercase parallel hash routing
- use canonical router-native routes everywhere
- keep upload UI only on dashboard
- add Dashboard as the first sidebar link
- convert run report to `Run/<id>/report`
- let `Grant/<id>/analyze` rely on generic session reuse behavior

## Testing Plan

### Backend tests

Add:

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_stream_sessions.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes_fastapi_stream_sessions.py`

Cover:

- create/reuse semantics
- auth scoping
- event append/replay ordering
- terminal transitions
- TTL pruning
- route-level session reuse for streaming methods

### Actor tests

Add:

- `packages/n3tx-actors/src/n3tx_actors/tests/test_network_api_stream_sessions.py`

Cover:

- actor-routed SSE parity with direct routing

### Frontend tests

Add or extend:

- `tests/frontend/tests/components/ntx-method.test.js`
- `tests/frontend/tests/components/ntx-stream.test.js`
- `tests/frontend/tests/components/ntx-router.test.js`

Cover:

- `ref` parsing
- session resume and replay
- remount behavior after reroute
- action route mounting with `ref`

### Veille regression tests

Add:

- `tests/frontend/tests/integration/veille-routing.test.js`

Cover:

- sidebar/topbar canonical routes
- `Grant/<id>/analyze` reopening active session
- `Run/<id>/report` mounting correctly

## Documentation Updates

Update after implementation:

- `docs/ARCHITECTURE.md`
- `BACKEND.md`
- `FRONTEND.md`
- `docs/AGENTS.md`
- `docs/frontend/ARCHITECTURE.md`
- `CLAUDE.md` only if key file lists or architectural patterns change materially

## Safe Implementation Slices

### Slice 1 - Backend session foundation

- add registry module
- add session API routes
- add unit tests for the registry

### Slice 2 - Direct-route streaming integration

- wire `routes_fastapi.py` to create/reuse sessions and buffer events
- add direct-route stream tests

### Slice 3 - Frontend resumable stream support

- add session client helper
- add `ref` support to `ntx-method`
- add resume/replay behavior to `ntx-stream`
- verify `ntx-stream-agent` compatibility

### Slice 4 - Veille adoption and route cleanup

- remove lowercase routing layer
- switch Veille to canonical routes
- move report route to `Run/<id>/report`
- add Veille regression tests

### Slice 5 - Actor-routing parity

- integrate `network_api.py`
- add Level 3 parity tests

## Risks

### Event normalization drift

Risk:

- direct-route streaming currently emits raw chunk dicts, while actor routing emits full TX envelopes

Mitigation:

- define a single normalized session event shape and adapt both routing modes into it before buffering/replay

### Duplicate rendering on replay

Risk:

- rich components may duplicate footers, tool cards, or final content if replay is not idempotent enough

Mitigation:

- replay through the same dispatch path used for live events and test `DONE` / terminal states explicitly

### Session lifecycle leaks

Risk:

- in-memory sessions could accumulate forever or orphan subscribers

Mitigation:

- bounded buffers, TTL pruning, explicit cleanup on terminal state and disconnect

### Overloading route handlers

Risk:

- `routes_fastapi.py` and `network_api.py` become harder to read if session logic is inlined

Mitigation:

- extract session wrapping into dedicated helpers rather than burying logic inside route closures

## Recommendation

Build this as a generic streaming-method session layer first, then let Veille adopt it.

That keeps the framework elegant:

- one streaming contract
- one resumability mechanism
- one canonical router
- no Veille-only orchestration hacks

It also preserves a clean upgrade path later to a persisted `MethodSession` model if restart-safe history becomes necessary.
