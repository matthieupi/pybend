# Stream Actor PRD — Task Breakdown

**Feature:** Schema-Declared Stream Events + StreamActor Mixin
**Source plan:** `.traces/plans/stream-consumer-and-events.md`
**Tasks:** 9 tasks in 4 waves

---

## Wave 1 — Foundation (no dependencies, parallel)

### task-01: Add `events=` parameter to `@expose_route` decorator
- **File:** `packages/n3tx-core/src/n3tx_core/utils/decorators.py`
- **Change:** Add `events=None` parameter to function signature + `__endpoint__` dict
- **Verify:** Import succeeds, existing behavior unchanged

### task-02: Inject stream events into schema pipeline
- **File:** `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- **Change:** After `stream` flag injection in `__n3tx_methods_json_signature__`, add events dict using `model_json_schema()`
- **Verify:** Import succeeds, backward compatible

---

## Wave 2 — Event models + transport (depends on wave 1)

### task-03: Add stream event ProtoModel subclasses and `events=` to AgentActor
- **File:** `packages/n3tx-agents/src/n3tx_agents/actor.py`
- **Depends on:** task-01, task-02
- **Change:** Define TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk as non-storable ProtoModel subclasses. Wire to `agentic_stream` via `events=`
- **Verify:** Models importable, schema generation works

### task-04: Add done guard to `HTTP.stream()` in HTTP.js
- **File:** `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js`
- **Depends on:** (none, but wave 2 for ordering)
- **Change:** Add `_done` flag to prevent double `onDone` callback
- **Verify:** Guard logic correct

### task-05: Create StreamActor mixin in StreamActor.js
- **File:** `packages/n3tx-agents/src/n3tx_agents/static/components/StreamActor.js` (NEW)
- **Depends on:** (none, but wave 2 for ordering)
- **Change:** New mixin: `StreamActor(Base)` with `stream()`, `streamClose()`, `#dispatch()`, `_validateStreamHandlers()`
- **Verify:** File exists, exports mixin, unwrap logic correct

---

## Wave 3 — Component refactors (depends on StreamActor)

### task-06: Refactor `ntx-agent-live.js` to extend StreamActor
- **File:** `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`
- **Depends on:** task-05
- **Change:** `extends StreamActor(HTMLElement)`, `#` private fields, UPPERCASE handlers (THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE, STREAM_END, STREAM_ERROR)
- **Verify:** All functionality preserved, no direct HTTP.stream() calls

### task-07: Refactor `ntx-chat.js` to extend StreamActor
- **File:** `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`
- **Depends on:** task-05
- **Change:** Same StreamActor migration. Keeps HTTP import for non-streaming ops. Per-message state in `#currentMsgEl`/`#currentTextEl`/`#currentText`
- **Verify:** Both streaming and non-streaming send paths work

### task-08: Add StreamActor.js modulepreload to index.html
- **File:** `examples/pygentic/static/index.html`
- **Depends on:** task-05
- **Change:** One line: `<link rel="modulepreload" href="./components/StreamActor.js">`
- **Verify:** Appears before dependent component preloads

---

## Wave 4 — Tests (depends on backend changes)

### task-09: Update SSE tests and add schema events test
- **File:** `examples/pygentic/tests/test_streaming_display.py`
- **Depends on:** task-03
- **Change:** Update 3 SSE tests to unwrap STREAM envelope before checking inner events. Add `_unwrap_stream_chunk` helper. Add `TestStreamEventSchema` class with 2 tests.
- **Verify:** `pytest examples/pygentic/tests/test_streaming_display.py -v`

---

## File Conflict Analysis

| Wave | Files Modified | Conflicts |
|------|---------------|-----------|
| 1 | `decorators.py`, `proto_model.py` | None — different files |
| 2 | `actor.py`, `HTTP.js`, `StreamActor.js` (new) | None — different files |
| 3 | `ntx-agent-live.js`, `ntx-chat.js`, `index.html` | None — different files |
| 4 | `test_streaming_display.py` | None — single file |

All tasks within each wave touch different files — full parallel execution possible.
