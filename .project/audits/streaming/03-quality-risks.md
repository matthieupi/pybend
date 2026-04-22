# Streaming Subsystem: Quality & Risk Assessment

**Auditor:** Claude Opus 4.6
**Date:** 2026-03-26
**Scope:** All streaming infrastructure across backend (Python), transport (SSE/WS), and frontend (JS)
**Files reviewed:** 22 core + test files as specified in audit brief

---

## Table of Contents

1. [Potential Bugs](#1-potential-bugs)
2. [Edge Cases & Boundary Conditions](#2-edge-cases--boundary-conditions)
3. [Test Coverage Analysis](#3-test-coverage-analysis)
4. [Test Quality Assessment](#4-test-quality-assessment)
5. [Error Handling Gaps](#5-error-handling-gaps)
6. [Security Considerations](#6-security-considerations)
7. [Performance Risks](#7-performance-risks)
8. [Concurrency Issues](#8-concurrency-issues)
9. [Resource Management](#9-resource-management)
10. [Technical Debt Inventory](#10-technical-debt-inventory)
11. [Failure Modes & Blast Radius](#11-failure-modes--blast-radius)

---

## 1. Potential Bugs

### BUG-1: Level 1/2 SSE missing error handling for async generator exceptions (HIGH)

**File:** `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py:341-349`

```python
async def sse(_gen=result):
    async for chunk in _gen:
        data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
        yield f"event: chunk\ndata: {json.dumps(data, default=str)}\n\n"
    yield f"event: done\ndata: {{}}\n\n"
```

If the async generator raises an exception mid-stream, the `sse()` wrapper does not catch it. The `StreamingResponse` will terminate abruptly without sending an `event: error` frame. The client will see a truncated stream with no error indication.

**Contrast with Level 3:** `actor_model.py:155-163` properly wraps the generator in try/except and sends `tx.exception(e)` on failure.

**Likelihood:** Medium-high. Any streaming method that queries external APIs (LLM, HTTP) can throw.

### BUG-2: `expose_route` wrapper breaks async generators in non-DEBUG mode (HIGH)

**File:** `packages/n3tx-core/src/n3tx_core/utils/decorators.py:29-33`

```python
def wrapper(*args, **kwargs):
    if not config.DEBUG:
        return func(*args, **kwargs)

    result = func(*args, **kwargs)

    # Async generators must pass through
    if inspect.isasyncgen(result):
        return result
```

In non-DEBUG mode, `func(*args, **kwargs)` is called and its return value is returned directly. This is correct for async generators because Python evaluates the call to create the generator object. However, in DEBUG mode, `func(*args, **kwargs)` is called **twice** if it is a regular function (once at line 33, then the result is inspected). For async generators, it is only called once (line 33), and the generator passthrough at line 37 is correct.

The real issue: in DEBUG mode, the wrapper calls `func(*args, **kwargs)` at line 33. If the function is a regular (non-async) function, it runs synchronously. But the timing measurement at lines 43-44 is meaningless -- `start` is set at line 43, and `elapsed` is computed immediately at line 44, capturing ~0ms since the function already ran at line 33.

**Likelihood:** Low for streaming correctness (async generators pass through correctly), but the debug envelope timing is always 0ms for synchronous methods.

### BUG-3: `_parse_method_args` treats missing optional params as errors (MEDIUM)

**File:** `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py:316-322`

```python
for name, param in sig.parameters.items():
    if name in ('self', 'cls', 'user'):
        continue
    param_type = type_hints.get(name, str)
    raw = data.get(name)
    if raw is None:
        raise HTTPException(status_code=400, detail=f"Missing field: {name}")
```

Every parameter that is not `self`, `cls`, or `user` is treated as required. Parameters with default values (e.g., `n: int = 5`) will trigger a 400 error if not provided in the request body. This affects streaming endpoints at Level 1/2.

**Contrast with Level 3:** `network_api.py:559` uses `if raw is None: continue` -- silently skips missing params, which is the opposite bug (never raises for truly required params).

**Likelihood:** High. Users defining `@expose_route` methods with optional parameters will get spurious 400 errors at Level 1/2, or silently missing values at Level 3.

### BUG-4: Frontend HTTP.stream() silently swallows partial JSON (MEDIUM)

**File:** `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js:386`

```javascript
} catch (e) { /* partial JSON, wait for more data */ }
```

This catch silently discards any JSON parse error. If the server sends malformed JSON (not just partial), the client will never know. The comment says "wait for more data" but the buffer is only appended per `reader.read()` call -- there is no mechanism to re-assemble the partial JSON across multiple reads. A `data:` line that spans two TCP segments will be split by the `lines.pop()` logic at line 376, so the next iteration will process the remainder. But genuine JSON corruption is silently dropped.

**Likelihood:** Low in practice (server serializes valid JSON), but makes debugging extremely difficult when it does happen.

### BUG-5: `NetworkAdapter.stream()` sends TX with interceptors but stream doesn't check error during initial send (LOW)

**File:** `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py:147`

```python
send_task = asyncio.create_task(self.send(tx))
```

The `send_task` is created but its result/exception is never inspected. If `self.send(tx)` raises an exception (e.g., no actor registered for the target address), the exception is silently swallowed by the task. The consumer will timeout waiting for chunks that will never arrive.

**Likelihood:** Low. `Actor.send()` typically does not raise (it routes or drops), but error diagnosis is poor if it does.

### BUG-6: NTTStreamAgent re-parses already-parsed `data.args` (LOW)

**File:** `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js:33-34`
**Also:** `packages/n3tx-agents/src/n3tx_agents/mixin.py:569-574`

The backend `run_stream()` already normalizes `args` from string to dict at mixin.py:569-574. Then NTTStreamAgent at line 33-34 attempts to parse `data.args` again:

```javascript
if (typeof data.args === 'string') {
    try { data.args = JSON.parse(data.args); } catch { data.args = { raw: data.args }; }
}
```

This double-parsing is defensive but indicates a contract ambiguity -- the wire format for `args` is inconsistent across paths. Not a bug per se, but a symptom of undocumented data shape.

---

## 2. Edge Cases & Boundary Conditions

### EDGE-1: Empty async generator (zero chunks)

If a streaming method yields nothing, the behavior differs by level:

- **Level 1/2** (`routes_fastapi.py:341-345`): Only `event: done\ndata: {}\n\n` is sent. Correct.
- **Level 3** (`actor_model.py:156-160`): Loop body never executes, `seq=0`. Sends `tx.end(seq=0)`. Correct.
- **Agent streaming** (`mixin.py:559`): If the LLM produces no output, `streamed_text` stays `''`, and the done chunk has `answer: ''`. Correct but potentially confusing.

**Risk:** Low. Behavior is consistent.

### EDGE-2: Very large stream chunks

No limit on chunk size anywhere in the pipeline. A streaming method that yields a 100MB dict will:

1. Backend: Serialize to JSON (memory spike), send as a single SSE frame
2. Frontend: Parse the entire frame as one JSON.parse() call (potential OOM)

**Risk:** Medium. No chunking or size limits are enforced at any layer.

### EDGE-3: Concurrent streams from the same client

Frontend `NTTStream.callMethod()` (ntx-stream.js:44-66) resets state via `#reset()` then starts a new stream. If a previous stream is still active, the old dynamic handler `this[name]` is overwritten but the old backend stream continues producing chunks. These orphaned chunks will arrive at the adapter but the frontend correlation ID has changed.

At the backend, `NetworkAdapter._pending` stores the queue by TX uuid, so old chunks will accumulate in a queue that no one reads (memory leak until GC).

For WebSocket transport: `_stream_to_ws()` launches background tasks. Multiple concurrent streams from the same WS client will interleave chunks without clear demarcation.

**Risk:** Medium. Multiple rapid clicks of a stream button will create orphaned backend tasks.

### EDGE-4: Stream cancellation is frontend-only

`NTTStream.cancel()` (ntx-stream.js:138-154) sends a `STREAM_CANCEL` TX but the comment says "for future backend support." The backend has no handler for `STREAM_CANCEL`. The async generator on the backend continues to completion, consuming resources unnecessarily.

**Risk:** Medium for long-running streams (e.g., agent reasoning with many tool calls).

### EDGE-5: SSE newline in data payload

If a chunk's JSON-serialized data contains literal `\n` characters (which JSON encoding does not produce -- newlines become `\\n`), the SSE parser would break. This is safe because `json.dumps()` escapes newlines. However, if a custom serializer is used, this could cause frame corruption.

**Risk:** Very low.

---

## 3. Test Coverage Analysis

### What IS tested

| Area | Tests | Coverage quality |
|------|-------|-----------------|
| TX.chunk()/end() | `test_streaming.py` (unit) -- 19 tests | Thorough: meta fields, source/target swap, data wrapping, uuid, backward compat |
| NetworkAdapter inbox routing | `test_streaming.py` (unit) -- 5 tests | Good: Future vs Queue, stream_end cleanup, error cleanup, multiple chunks |
| NetworkAdapter.stream() | `test_streaming.py` (unit) -- 7 tests | Good: chunks+end, error termination, timeout, pending cleanup, seq numbers |
| ActorModel async gen handler | `test_streaming.py` (unit) -- 5 tests | Good: chunk sending, meta fields, req correlation, non-dict wrapping, error in gen |
| Shutdown/cancellation | `test_streaming_shutdown.py` -- 3 tests | Targeted: CancelledError propagation, send_task cleanup, generator termination |
| Agent run_stream first token | `test_run_stream_first_token.py` -- 3 tests | Targeted: PartStartEvent handling for OpenAI-style models |
| Level 1/2 SSE integration | `examples/core/tests/test_streaming.py` -- 7 tests | Good: content type, chunk order, done event, no auth, 404, schema flag |
| Level 3 SSE integration | `examples/actors/tests/test_streaming.py` -- 7 tests | Good: mirrors core tests with TX envelope differences |
| E2E progressive delivery | `examples/*/tests/e2e/test_streaming.py` -- 1 test each | Critical: proves chunks are not buffered (timing-based) |

### What is NOT tested -- highest-risk gaps

| Gap | Risk | Why it matters |
|-----|------|---------------|
| **WebSocket streaming** (`_stream_to_ws()`) | HIGH | Zero tests. WS streaming is a separate code path from SSE. Error handling, translation, concurrent streams are all untested. |
| **Level 1/2 SSE error mid-stream** | HIGH | No test verifies what happens when an async generator raises. BUG-1 would be caught by such a test. |
| **`_sse_from_stream()` Level 3** | MEDIUM | The SSE serialization of TX envelopes is only tested indirectly via integration tests. No unit test for the function itself. |
| **Frontend NTTStream UPPERCASE dispatch** | MEDIUM | Zero JS unit tests for the STREAM handler's event routing (typed vs untyped chunks). |
| **Frontend HTTP.stream()** | MEDIUM | Zero JS unit tests for SSE parsing, buffer handling, cancel(), error cases. |
| **Agent `agentic_stream()` config cascade** | MEDIUM | The streaming equivalent of `agentic()` is untested for its config resolution (3-tier cascade). Only `run_stream()` is tested directly. |
| **AgentActor.agentic_stream() override** | MEDIUM | The `actor.py` streaming override that resolves tools from DB is untested. |
| **Stream with interceptors** | MEDIUM | `NetworkAdapter.stream()` runs request interceptors but no test verifies that auth rejection works for streaming endpoints. |
| **`_parse_method_args` for streaming** | LOW | The Level 3 argument parsing for streaming methods is not tested in isolation. |
| **NTTChat streaming** | LOW | The chat component's UPPERCASE handlers are untested. |
| **Multiple concurrent streams** | LOW | No test for overlapping streams on the same adapter. |
| **Stream timeout recovery** | LOW | Frontend has no timeout; backend timeout is tested but frontend behavior on timeout is not. |

### Recommended test additions (priority order)

1. **Level 1/2 SSE error propagation**: Streaming method that raises mid-stream; verify `event: error` is sent.
2. **WebSocket streaming integration**: A test that exercises `_stream_to_ws()` with chunk/end/error scenarios.
3. **Stream with auth interceptor**: Verify that an unauthorized streaming request is rejected before the SSE stream starts.
4. **Concurrent stream cleanup**: Start two streams in rapid succession; verify no memory leak in `_pending`.
5. **Frontend SSE parsing**: Jest/Vitest test for `HTTP.stream()` with mock fetch responses.

---

## 4. Test Quality Assessment

### Strengths

- **Unit tests are well-structured**: Each test class covers one concept (TX chunk, TX end, adapter inbox, adapter stream, actor model handler). Clear naming.
- **Integration tests mirror Level 1/2 vs Level 3 differences**: The actors test correctly accounts for TX envelope wrapping (e.g., `e['data']['data']['count']`).
- **E2E tests validate progressive delivery**: Timing-based assertions prove chunks are not buffered.
- **First-token bug test is exemplary**: Creates a fake model that mimics real OpenAI behavior. Tests the exact failure mode with clear error messages.

### Weaknesses

- **No assertion on _pending dict size after concurrent operations**: Tests verify cleanup after single streams but never test overlapping or rapid-fire streams.
- **`mock_method` context manager** duplicates across test files. Should be a shared fixture.
- **Shutdown tests use `asyncio.shield` + sleep**: Inherently timing-sensitive. Could flake on slow CI.
  - `test_streaming_shutdown.py:95`: `await asyncio.wait_for(asyncio.shield(task), timeout=2.0)` -- if the machine is slow, the 2s timeout might not be enough, though this is generous.
  - `test_streaming_shutdown.py:99`: `await asyncio.sleep(0.1)` -- relies on cleanup propagating within 100ms.
- **E2E streaming tests have a hard-coded timing threshold**: `assert total_time_ms > 800` (line 94 in both e2e tests). On a heavily loaded CI machine, 5 chunks * 0.3s could take longer than expected and still pass, but network latency could cause false positives.
- **Integration tests do not verify stream termination semantics**: They parse the full response text (which implies the stream completed) but don't test mid-stream disconnection.

### Assertion gaps

- `test_streaming_shutdown.py:102`: Asserts `tx.uuid not in adapter._pending` but does not check that the send_task was actually cancelled (only that the pending entry was cleaned up).
- `test_streaming.py:291` (unit): Asserts `len(chunks) == 4` but doesn't verify chunk ordering by seq number (only implicitly via list order).

---

## 5. Error Handling Gaps

### GAP-1: Level 1/2 streaming -- no try/except around async generator (CRITICAL)

**File:** `routes_fastapi.py:341-345` and `389-393`

The `sse()` inner function iterates the async generator without any error handling. If the generator raises:
- The `StreamingResponse` terminates abruptly
- The client receives a truncated stream with no error event
- The server logs nothing (no except block)

### GAP-2: `_sse_from_stream()` -- no fallback for non-JSON-serializable data (MEDIUM)

**File:** `network_api.py:478`

```python
yield f"event: chunk\ndata: {json.dumps(tx_dict, default=str)}\n\n"
```

The `default=str` parameter handles most cases, but `dataclasses.asdict()` at line 478 will fail if the TX contains non-serializable objects in meta (e.g., class references). The `_NON_SERIALIZABLE_META` filter exists in `network_ws.py:49` but is not applied in `_sse_from_stream()`.

**Scenario:** If `model_cls` is in `tx.meta` (set by `_add_streaming_handler` at line 513), `asdict()` will attempt to serialize the class itself, causing `TypeError`.

Wait -- `dataclasses.asdict()` on a TX with `meta={'model_cls': <class Product>}` will try to `deepcopy` the class, which may work but produces meaningless output. The `default=str` in `json.dumps` would then serialize it as `"<class 'Product'>"`. Not a crash, but wasteful and potentially confusing data sent to the frontend.

### GAP-3: WebSocket stream error -- exception detail exposed to client (LOW)

**File:** `network_ws.py:222-230`

```python
except Exception as e:
    logger.error("WS stream error: %s", e)
    try:
        await ws.send_json({
            'name': 'ERROR', ...
            'data': {'message': str(e), 'code': 500},
        })
    except Exception:
        pass
```

`str(e)` may contain sensitive information (stack traces, DB connection strings, etc.). In production, error messages should be sanitized.

### GAP-4: Agent `run_stream()` catches all exceptions as 500 (LOW)

**File:** `mixin.py:685-691`

```python
except Exception as e:
    yield {
        'name': 'error',
        'data': {'message': str(e), 'code': 500},
        'meta': {'stream': True, 'error': True, 'seq': seq},
    }
```

All exceptions map to code 500. A `ValueError` for bad user input would benefit from a 400 code. The non-streaming `run()` does not have this issue because it raises exceptions that are caught by `tx.exception()` / `TX.from_exception()` which maps exception types to semantic codes.

---

## 6. Security Considerations

### SEC-1: Level 3 streaming bypasses Tier 2 auth for streaming methods (MEDIUM)

**File:** `network_api.py:510-514`

```python
tx = TX(
    name=_attr_name, source=api_adapter.addr, target=_addr,
    data=payload,
    meta={'user': user, 'model_cls': _cls, 'stream': True},
)
```

The TX is sent to the actor system where `ActorModel.handler()` dispatches to the method. For streaming methods, the handler at `actor_model.py:98-115` checks `@expose_route(access=...)` before executing. However, the Tier 2 auth at `actor_model.py:200-227` (`_authorize()`) is only called for CRUD ops inside `handler_crud()`. For `@expose_route` methods, auth is checked via the method's `access` attribute at line 102-115.

If a streaming method lacks an explicit `access=` parameter on `@expose_route`, it falls through to the model's `__access__` dict resolved via `_resolver.authorize(ctx)`. But `actor_model.py:100` only checks `is_exposed` methods' `access` attribute -- if `access` is `None` (not set), line 104 (`if method_access is not None`) skips the auth check entirely. The method then executes without authorization.

**Mitigation:** The Tier 1 interceptor (`auth_interceptor`) on the `request()` path provides a first line of defense. But if the interceptor only checks basic authentication (is user logged in?) and not method-level authorization, streaming methods without explicit `access=` are effectively unprotected at Tier 2.

### SEC-2: WebSocket JWT validated only at connection time (LOW)

**File:** `network_ws.py:287-292`

The JWT token is validated once at WebSocket connection time. If the token expires during a long-lived WebSocket session, subsequent messages (including stream requests) continue to be processed with the stale user context. This is standard WebSocket behavior but worth noting for long-running agent streams.

### SEC-3: Internal exception messages exposed via SSE (LOW)

**Files:** `routes_fastapi.py:351-352`, `network_api.py:480`, `mixin.py:689`

Exception messages from `str(e)` are sent directly to the client in SSE error events. In production, Python exception messages can contain file paths, SQL queries, or internal state.

---

## 7. Performance Risks

### PERF-1: `dataclasses.asdict()` deep-copies every TX in Level 3 SSE (MEDIUM)

**File:** `network_api.py:478`

```python
tx_dict = asdict(chunk)
```

`dataclasses.asdict()` performs a deep copy of the entire TX, including all nested dicts in `data` and `meta`. For agent streams with large tool results (e.g., a full DB query result in `data`), this doubles memory usage per chunk.

**Alternative:** A shallow dict conversion (`{'name': chunk.name, 'source': chunk.source, ...}`) would be more efficient and sufficient for JSON serialization.

### PERF-2: Frontend re-parses entire Markdown buffer on every chunk (MEDIUM)

**Files:** `ntx-stream-agent.js:207-221`, `ntx-agent-live.js:261-275`

```javascript
#renderMd(entry, kind) {
    const buf = kind === 'text' ? this.#textBuf : this.#thinkBuf;
    content.innerHTML = marked.parse(buf);
}
```

Every time a text chunk arrives and triggers a render (either via newline or 300ms timer), the entire accumulated buffer is re-parsed by `marked.parse()`. For long agent responses (10KB+ of Markdown), this is O(n^2) overall -- each of the N chunks re-parses all previous content.

The `#textRendered` / `#thinkRendered` tracking variables suggest incremental rendering was considered but not implemented -- they track how much was rendered but the actual render always processes the full buffer.

### PERF-3: No backpressure on actor-to-SSE pipeline (LOW)

**File:** `network_adapter.py:139-162`

The `asyncio.Queue()` used for stream correlation has unbounded capacity. If the backend actor generates chunks faster than the SSE response can flush them (e.g., network congestion), the queue grows without limit.

**Risk:** Low in practice because:
1. LLM streaming is typically slow (token-by-token)
2. Local countdown endpoints have artificial delays
3. Network is usually faster than content generation

But for batch-processing streams (e.g., scanning many records), this could accumulate significant memory.

### PERF-4: `model_cls` class reference in TX meta propagated through entire pipeline (LOW)

**Files:** `network_api.py:513`, `network_ws.py:139`

The `model_cls` key in TX meta carries a Python class reference through the entire actor system. This prevents garbage collection of the class and is unnecessary beyond the initial route handler. The `_NON_SERIALIZABLE_META` filter in WebSocket translation strips it for the wire, but it persists in backend memory throughout the stream's lifetime.

---

## 8. Concurrency Issues

### CONC-1: `_connections` dict mutated during iteration in LIFECYCLE broadcast (LOW)

**File:** `network_ws.py:261-269`

```python
dead_clients = []
for client_id, conn in self._connections.items():
    try:
        await conn['ws'].send_json(broadcast)
    except Exception:
        dead_clients.append(client_id)
# Clean up dead connections
for client_id in dead_clients:
    self._connections.pop(client_id, None)
```

This is correctly implemented with a two-phase approach (collect dead, then remove). However, if `handle_message()` is processing a stream for client A while LIFECYCLE removes client A's connection (due to a send failure during broadcast), the in-flight stream will fail on its next `ws.send_json()`.

**Risk:** Low. The `_stream_to_ws()` error handler catches this at line 221-230.

### CONC-2: `_pending` dict not thread-safe (LOW)

**File:** `network_adapter.py:56`

```python
_pending: dict = PrivateAttr(default_factory=dict)
```

The `_pending` dict is accessed from multiple coroutines: `inbox()` reads and pops, `request()`/`stream()` writes, timeout handlers pop. In Python's asyncio model, this is safe because all access is from the same event loop thread. But if an adapter is ever used from a sync context (e.g., tests with `asyncio.run()`), race conditions could occur.

**Risk:** Very low. The actor system is inherently single-threaded (asyncio).

### CONC-3: Frontend `callMethod()` can fire multiple concurrent streams (MEDIUM)

**File:** `ntx-stream.js:42-67`

```javascript
callMethod() {
    // ...
    this.#reset();
    this.#streaming = true;
    this.#cancelled = false;
    // ...
    this.send(new TX({...}));
}
```

There is no guard against double-invocation. If the user clicks the submit button twice quickly, two streams start. The second call resets the state (`#reset()`), overwriting `#textBuf` and the dynamic handler. The first stream's chunks will still arrive but will be processed by the handler bound to the second stream's method name (same name, so it works). But the `#streamReqId` changes, so the old stream can't be cancelled.

**Mitigation in subclasses:** `NTTAgentLive.callMethod()` (ntx-agent-live.js:69-89) disables the run button: `this.#els.runBtn.disabled = true`. But `NTTStreamAgent` and base `NTTStream` do not disable their submit buttons.

---

## 9. Resource Management

### RES-1: `send_task` may not be properly awaited on cancellation (LOW)

**File:** `network_adapter.py:161-162`

```python
finally:
    self._pending.pop(tx.uuid, None)
    if not send_task.done():
        send_task.cancel()
```

When the stream generator is cancelled (e.g., client disconnect), `send_task.cancel()` is called but the cancellation is not awaited. The task will be garbage-collected eventually, but Python may emit a "Task was destroyed but it is pending" warning.

### RES-2: WebSocket `_stream_to_ws` background tasks are fire-and-forget (LOW)

**File:** `network_ws.py:201`

```python
asyncio.create_task(self._stream_to_ws(ws, tx))
```

The created task is not stored anywhere. If the WebSocket connection closes while a stream is active, the task continues running until the adapter's `stream()` method detects the timeout or error. There is no mechanism to cancel the task when the client disconnects.

The `handle_message()` method returns `None` for streaming requests, so the main WS loop at `network_ws.py:301-315` continues processing other messages. But if the client disconnects, the `finally` block at line 330-331 only removes the connection from `_connections` -- it does not cancel active stream tasks.

### RES-3: Frontend timer cleanup on disconnectedCallback (GOOD)

**Files:** `ntx-stream-agent.js:133-137`, `ntx-agent-live.js:92-96`, `ntx-chat.js` (implicit via NTTStream)

All three streaming components properly clear their timers in `disconnectedCallback()`. `NTTStream.cancel()` is called from `disconnectedCallback()` at line 156-159. This is correct resource management.

### RES-4: `#toolCards` Map grows unbounded during long agent sessions (LOW)

**Files:** `ntx-stream-agent.js:6`, `ntx-agent-live.js:22`, `ntx-chat.js:29`

The `#toolCards` Map stores DOM references keyed by `call_id`. It is cleared on `callMethod()` but not on `STREAM_END` or `STREAM_ERROR` in `NTTStreamAgent`. In `NTTChat`, it is set to `null` on `STREAM_END` (line 167). Inconsistent cleanup patterns.

**Risk:** Very low. Each stream starts fresh with `#toolCards.clear()`.

---

## 10. Technical Debt Inventory

### DEBT-1: Code duplication across streaming components

The following code blocks are duplicated nearly verbatim:

| Code block | Locations |
|---|---|
| `#scheduleRender()` / `#renderMd()` / `#flushRender()` | `ntx-stream-agent.js:189-231`, `ntx-agent-live.js:243-284` |
| `#setThinking()` | `ntx-stream-agent.js:169-187`, `ntx-agent-live.js:224-241` |
| `#addEntry()` | `ntx-stream-agent.js:160-167`, `ntx-agent-live.js:215-221` |
| `TOOL_CALL` / `TOOL_RESULT` / `TEXT` handlers | `ntx-stream-agent.js:30-75`, `ntx-agent-live.js:100-156` |
| `#esc()` | `ntx-stream-agent.js:242`, `ntx-stream.js:131`, `ntx-agent-live.js:290`, `ntx-chat.js:242` |
| CSS for entries, thinking, tool-call, etc. | `ntx-stream-agent.js:246-350`, `ntx-agent-live.js:292-450` |

`NTTAgentLive` extends `NTTStream` (not `NTTStreamAgent`), yet reimplements most of `NTTStreamAgent`'s logic. The component hierarchy should be `NTTStream -> NTTStreamAgent -> NTTAgentLive`, sharing the UPPERCASE handlers and rendering helpers.

### DEBT-2: Two SSE serialization formats

- **Level 1/2** (`routes_fastapi.py:343`): `data: {chunk_data}` -- bare inner data
- **Level 3** (`network_api.py:485`): `data: {full_tx_envelope}` -- TX with name, source, target, data, meta

The frontend `HTTP.stream()` (HTTP.js:382-386) parses the raw JSON and passes it to `onChunk`. The `NetworkAdapter.send()` (NetworkAdapter.js:150-166) calls `HTTP.stream()` with `httpCallback` which dispatches through the Matrix. This means:

- Level 1/2 SSE chunks arrive as bare data dicts (e.g., `{count: 3, message: '...'}`)
- Level 3 SSE chunks arrive as TX envelopes (e.g., `{name: 'STREAM', source: 'products', target: 'api', data: {count: 3}, meta: {...}}`)

The actors integration test at `examples/actors/tests/test_streaming.py:79-80` accounts for this:
```python
counts = [e['data']['data']['count'] for e in chunk_events ...]
```

This inconsistency between levels means frontend components must handle both formats. The `NetworkAdapter.js:150-166` stream path uses `httpCallback` which expects the SSE data to be a response object, not a TX envelope.

### DEBT-3: TODO/FIXME comments

| File | Line | Comment |
|---|---|---|
| `HTTP.js:113` | `// TODO: remove this fallback once responses use TX-based wire format` | Appears 3 times (lines 113, 171, 227). Debug envelope unwrapping. |
| `decorators.py:43-44` | Timing measurement | `start`/`elapsed` computed at lines 43-44 but function already ran at line 33. |

### DEBT-4: `parse_obj` deprecated in Pydantic V2

**File:** `routes_fastapi.py:325`

```python
parsed_args[name] = param_type(**raw) if isinstance(raw, dict) else param_type.parse_obj(raw)
```

`parse_obj` was renamed to `model_validate` in Pydantic V2. This line will emit a deprecation warning.

### DEBT-5: Dead code in `register_routes()`

**File:** `routes_fastapi.py:488-519`

The `custom_method` variable is assigned in several branches (lines 491-518) but never used after `handler = make_custom_post(...)` at line 520 overwrites the route. The entire `custom_method` logic (lines 488-518) is dead code that was superseded by `make_custom_post()`.

### DEBT-6: `sendStream()` deprecation

**File:** `NetworkAdapter.js:177-181`

```javascript
/**
 * @deprecated Use send() with meta.stream instead
 */
sendStream(event, onChunk, onDone, onError) { ... }
```

This deprecated method still exists. No callers found in the current codebase, suggesting it can be removed.

---

## 11. Failure Modes & Blast Radius

### FAIL-1: LLM provider timeout during agent streaming

**Trigger:** Ollama/OpenAI API becomes unresponsive mid-stream.

**Behavior chain:**
1. `pydantic_ai` agent hangs on LLM request inside `run_stream()` (`mixin.py:559`)
2. `async with ai_agent.iter(task)` blocks at `ModelRequestNode.stream()`
3. No internal timeout in pydantic-ai's iteration loop
4. The backend SSE connection stays open (uvicorn doesn't kill it)
5. Frontend cursor blinks indefinitely
6. After `NetworkAdapter.stream()` timeout (120s), a timeout error TX is yielded
7. `_sse_from_stream()` sends `event: error` and returns

**Blast radius:** Single stream. Other requests are unaffected (asyncio is cooperative, not blocking).

**Recovery:** The 120s timeout in `NetworkAdapter.stream()` provides eventual recovery. The frontend can call `cancel()` to abort sooner (but see EDGE-4 -- backend doesn't handle cancellation).

### FAIL-2: Database unavailable during CRUD in handler_crud

**Trigger:** SQLite DB locked or file deleted.

**Behavior chain:**
1. `handler_crud()` catches the exception at `actor_model.py:322-324`
2. Returns `tx.exception(e)` which maps to an error TX
3. For streaming: the error TX is sent as an SSE error event
4. For non-streaming: the error TX is sent as an HTTP error response

**Blast radius:** Single request. Well-contained.

### FAIL-3: WebSocket disconnect during active stream

**Trigger:** Client browser closes tab while agent stream is running.

**Behavior chain:**
1. `websocket_endpoint` loop (network_ws.py:301) catches `WebSocketDisconnect`
2. `finally` block removes connection from `_connections`
3. `_stream_to_ws()` background task (launched at line 201) continues running
4. Next `ws.send_json()` call in `_stream_to_ws()` raises exception
5. Error handler at line 221-230 catches it, tries to send error to dead WS (fails silently)
6. `_stream_to_ws()` returns
7. The underlying `adapter.stream()` generator continues until the backend async generator completes
8. Backend resources (LLM connection, memory) are held until completion

**Blast radius:** Wasted backend resources for one stream. No cascading failure, but for expensive LLM calls this could be significant.

### FAIL-4: Matrix not initialized when agent streaming starts

**Trigger:** Calling `agentic_stream()` before Matrix is created.

**Behavior chain:**
1. `run_stream()` at mixin.py:499: `root = Actor.root()` returns `None`
2. `RuntimeError("No Matrix root.")` is raised
3. The except block at mixin.py:685 catches it and yields an error chunk
4. Frontend displays "No Matrix root. Initialize a Matrix before running agents."

**Blast radius:** Single request. Error message is clear. Good degradation.

### FAIL-5: Frontend schema not loaded when stream button clicked

**Trigger:** User clicks a streaming method button before schema fetch completes.

**Behavior chain:**
1. `NTTMethod.callMethod()` at ntx-method.js:99: `caller = this.ntt || this.proto`
2. If neither exists (schema not loaded), `caller?.call` is falsy, function returns silently
3. No user feedback

**Blast radius:** None. But poor UX -- the user thinks nothing happened.

---

## Summary: Top 10 Issues by Priority

| # | Issue | Type | Severity | File |
|---|-------|------|----------|------|
| 1 | Level 1/2 SSE has no error handling for generator exceptions | Bug | HIGH | `routes_fastapi.py:341-349` |
| 2 | WebSocket streaming has zero test coverage | Coverage | HIGH | `network_ws.py:207-230` |
| 3 | `_parse_method_args` treats all params as required (Level 1/2) | Bug | MEDIUM | `routes_fastapi.py:316-322` |
| 4 | Stream cancellation is frontend-only; backend keeps running | Gap | MEDIUM | `ntx-stream.js:138-154` |
| 5 | O(n^2) Markdown re-parsing on every text chunk | Performance | MEDIUM | `ntx-stream-agent.js:207-221` |
| 6 | Level 3 streaming bypasses Tier 2 auth for methods without explicit `access=` | Security | MEDIUM | `actor_model.py:100-115` |
| 7 | Massive code duplication between NTTStreamAgent and NTTAgentLive | Debt | MEDIUM | 3 JS files |
| 8 | Two incompatible SSE formats between Level 1/2 and Level 3 | Debt | MEDIUM | `routes_fastapi.py` vs `network_api.py` |
| 9 | WS stream tasks not cancelled on client disconnect | Resource | LOW | `network_ws.py:201` |
| 10 | `dataclasses.asdict()` deep-copies every TX in Level 3 SSE | Performance | LOW | `network_api.py:478` |
