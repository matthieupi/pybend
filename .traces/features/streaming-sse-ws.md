# Streaming Infrastructure (SSE + WebSocket)

## Context

N3TX has an agentic feature (`AgentMixin`, `AgentActor`) that executes LLM reasoning loops. Currently, `agent_run()` blocks until the full LLM loop completes, then returns the final result. There's no way to stream intermediate output (token deltas, tool calls, progress) to the client.

More broadly, **any** long-running interaction (not just agents) would benefit from streaming. The framework needs general-purpose streaming infrastructure so that any handler — agent runs, data exports, multi-step workflows — can stream progressive results to the client.

**The goal**: Build the transport-level streaming primitive into the TX/Actor/Transport architecture. The handler doesn't know whether it's streaming over SSE or WebSocket — the transport layer decides based on the app's configuration at startup.

---

## Design: Streaming as Multi-Reply TX

**Core insight**: Streaming is a request that produces multiple correlated replies instead of one. The existing `request()` → single `Future` becomes `stream()` → `asyncio.Queue` of chunks. Everything else (interceptors, auth, routing) stays unchanged.

**TX protocol** (no changes to TX dataclass — uses `meta` for extensibility):

| Message | `meta` fields |
|---------|--------------|
| Chunk | `req: uuid`, `stream: True`, `seq: N` |
| End | `req: uuid`, `stream: True`, `stream_end: True`, `seq: N` |
| Error | Existing `tx.error()` — `is_error` terminates the stream |

### Rename: `in_reply_to` → `req`

The `in_reply_to` field in `meta` is renamed to `req` across the entire stack. This is shorter, clearer, and aligns with the TX vocabulary (a reply references the request it answers).

**Collision check:** `req` is NOT used as a meta field anywhere in the codebase. It only appears as local variable names in test files (e.g., `req = Mock(spec=Request)`), which are completely separate namespaces.

**End-to-end rename locations:**

| File | What changes |
|------|-------------|
| `src/n3tx/core/actors/tx.py` | `reply()`, `error()` — `meta['in_reply_to']` → `meta['req']` |
| `src/n3tx/core/api/network_adapter.py` | `inbox()` — `tx.meta.get('in_reply_to')` → `tx.meta.get('req')` |
| `src/n3tx/core/api/network_adapter.py` | Docstrings referencing `in_reply_to` |
| `src/n3tx/core/actors/tests/test_tx.py` | Assertions on `meta['in_reply_to']` → `meta['req']` |
| `src/n3tx/core/api/tests/test_network_adapter.py` | All `in_reply_to` references in test assertions and TX construction |
| `src/n3tx/core/tests/unit/test_actor_system.py` | `assert reply.meta['in_reply_to']` → `meta['req']` |
| `src/n3tx/core/tests/unit/test_actor_model_crud.py` | `test_error_tx_has_in_reply_to` → rename test + assertions |
| `src/n3tx/core/actors/tests/test_actormodel_auth.py` | `meta.get('in_reply_to')` → `meta.get('req')` |

The frontend `TX.js` does NOT use `in_reply_to` — it only passes through `meta` as-is. No frontend TX changes needed for the rename itself, but the WS streaming code will use `meta.req` for correlation.

---

## Implementation

### Phase 0: Rename `in_reply_to` → `req`

This is a standalone refactor that should be done first, before any streaming code. It touches only `tx.py`, `network_adapter.py`, and their tests.

**File: `src/n3tx/core/actors/tx.py`** — 3 occurrences:

```python
# reply() line 34
meta={**self.meta, 'req': self.uuid},

# error() line 44
meta={**self.meta, 'req': self.uuid, 'error': True},

# docstring line 28
"""Gets a new uuid; stores original uuid in meta['req']."""
```

**File: `src/n3tx/core/api/network_adapter.py`** — 2 occurrences:

```python
# inbox() line 65
reply_to = tx.meta.get('req')

# docstring references
```

**Tests** — update all assertions from `meta['in_reply_to']` to `meta['req']`.

---

### Phase 1: TX Primitives & Decorator

**File: `src/n3tx/core/actors/tx.py`** — Add two helper methods to TX:

```python
def stream_chunk(self, data, seq: int) -> 'TX':
    """Create a stream chunk reply."""
    return TX(
        name=self.name,
        source=self.target, target=self.source,
        data=data if isinstance(data, dict) else {'chunk': data},
        meta={**self.meta, 'req': self.uuid, 'stream': True, 'seq': seq},
    )

def stream_end(self, data=None, seq: int = 0) -> 'TX':
    """Create a stream-end reply."""
    return TX(
        name=self.name,
        source=self.target, target=self.source,
        data=data if data is not None else {},
        meta={**self.meta, 'req': self.uuid, 'stream': True, 'stream_end': True, 'seq': seq},
    )
```

**File: `src/n3tx/core/utils/decorators.py`** — Add `stream` kwarg:

```python
def expose_route(route, methods=["POST"], access=None, stream=False):
    def decorator(func):
        func.__endpoint__ = {
            'route': route, 'methods': methods, 'access': access,
            'stream': stream,  # NEW — schema metadata only
        }
        return func
    return decorator
```

**File: `src/n3tx/core/models/proto_model.py`** (line ~172) — Include `stream` in method schema:

```python
method_entry = {
    'route': endpoint_info['route'],
    'methods': endpoint_info['methods'],
    'scope': method_type,
    'parameters': parameters,
    'returns': return_type_schema,
}
if endpoint_info.get('stream'):
    method_entry['stream'] = True
if endpoint_info.get('access') and hasattr(endpoint_info['access'], 'to_dict'):
    method_entry['access'] = endpoint_info['access'].to_dict()
```

---

### Phase 2: Actor Handler — Async Generator Detection

**File: `src/n3tx/core/models/actor_model.py`** (line ~116-145) — After getting the result from method dispatch, detect async generators:

Insert after `result = method(instance, **kwargs)` / `result = method(**kwargs)` and before the existing result dispatch block:

```python
import inspect

# If result is a coroutine, await it first
if asyncio.iscoroutine(result):
    result = await result

# Streaming: handler returned an async generator
if inspect.isasyncgen(result):
    seq = 0
    try:
        async for chunk in result:
            chunk_data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
            await target.send(tx.stream_chunk(chunk_data, seq))
            seq += 1
        await target.send(tx.stream_end(seq=seq))
    except Exception as e:
        logger.error(f"[{target.addr}] Stream error in {tx.name}: {e}")
        await target.send(tx.exception(e))
    return

# Existing result dispatch (dict, list, str, TX, None) — unchanged
```

This goes in the `else` branch (line 78) of `handler()`, inside the `try` block after the method call, before the `isinstance(result, TX)` check chain.

---

### Phase 3: NetworkAdapter.stream()

**File: `src/n3tx/core/api/network_adapter.py`**

**3a.** Modify `inbox()` to handle both `Future` and `Queue`:

```python
async def inbox(self, tx: TX) -> None:
    reply_to = tx.meta.get('req')
    if reply_to and reply_to in self._pending:
        pending = self._pending[reply_to]
        if isinstance(pending, asyncio.Future):
            self._pending.pop(reply_to)
            pending.set_result(tx)
        elif isinstance(pending, asyncio.Queue):
            await pending.put(tx)
            if tx.is_error or tx.meta.get('stream_end'):
                self._pending.pop(reply_to, None)
        return
    await super().inbox(tx)
```

**3b.** Add `stream()` async generator method:

```python
async def stream(self, tx: TX, timeout: float = 120.0):
    """Send TX and yield correlated stream chunks.

    Like request() but yields multiple TX responses. Terminates on
    stream_end or error TX. Uses asyncio.Queue for correlation.
    """
    from n3tx.core.actors.actor import Actor
    interceptors = Actor._get_interceptors(self, 'request')
    if interceptors:
        tx = await Actor._run_interceptors(interceptors, tx)
        if tx.is_error:
            yield tx
            return

    queue = asyncio.Queue()
    self._pending[tx.uuid] = queue
    await self.send(tx)
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                yield tx.error(f"Stream timed out after {timeout}s", code=504)
                return
            yield chunk
            if chunk.is_error or chunk.meta.get('stream_end'):
                return
    finally:
        self._pending.pop(tx.uuid, None)
```

---

### Phase 4: HTTP SSE — NetworkAPI (Level 3)

**File: `src/n3tx/core/api/network_api.py`** — Modify `_register_custom_routes()` and add `_add_streaming_handler()`

When `attr.__endpoint__.get('stream')` is True, generate a streaming route handler that returns `StreamingResponse` instead of a JSON response.

Add a new function `_add_streaming_handler()` and call it from `_register_custom_routes()` when `stream=True`, falling back to the existing `_add_custom_handler()` otherwise:

```python
from fastapi.responses import StreamingResponse

def _add_streaming_handler(
    router, api_adapter, model_class, attr, attr_name,
    full_route, methods, tag, is_instance_method, addr,
):
    """SSE route for streaming @expose_route methods (Level 3)."""
    from inspect import signature as get_sig
    from typing import get_type_hints
    sig = get_sig(attr)
    type_hints = get_type_hints(attr)

    if is_instance_method:
        @router.api_route(full_route, methods=methods, tags=[tag],
                          name=f"stream_{addr}_{attr_name}")
        async def stream_with_id(
            request: Request, id: int = Path(...),
            data: Dict[str, Any] = Body(default={}),
            _attr=attr, _attr_name=attr_name, _sig=sig,
            _type_hints=type_hints, _addr=addr, _cls=model_class,
        ):
            user = _get_user(request)
            payload = _parse_method_args(_sig, _type_hints, data, request)
            payload['id'] = id
            tx = TX(
                name=_attr_name, source=api_adapter.addr, target=_addr,
                data=payload,
                meta={'user': user, 'model_cls': _cls, 'stream': True},
            )
            return StreamingResponse(
                _sse_from_stream(api_adapter, tx),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
    else:
        @router.api_route(full_route, methods=methods, tags=[tag],
                          name=f"stream_{addr}_{attr_name}")
        async def stream_no_id(
            request: Request,
            data: Dict[str, Any] = Body(default={}),
            _attr=attr, _attr_name=attr_name, _sig=sig,
            _type_hints=type_hints, _addr=addr, _cls=model_class,
        ):
            user = _get_user(request)
            payload = _parse_method_args(_sig, _type_hints, data, request)
            tx = TX(
                name=_attr_name, source=api_adapter.addr, target=_addr,
                data=payload,
                meta={'user': user, 'model_cls': _cls, 'stream': True},
            )
            return StreamingResponse(
                _sse_from_stream(api_adapter, tx),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )


async def _sse_from_stream(adapter, tx):
    """Convert NetworkAdapter.stream() into SSE text lines."""
    async for chunk in adapter.stream(tx, timeout=120.0):
        if chunk.is_error:
            yield f"event: error\ndata: {json.dumps(chunk.data)}\n\n"
            return
        if chunk.meta.get('stream_end'):
            yield f"event: done\ndata: {json.dumps(chunk.data)}\n\n"
            return
        yield f"event: chunk\ndata: {json.dumps(chunk.data, default=str)}\n\n"
```

Update `_register_custom_routes()` to branch:

```python
route_info = attr.__endpoint__
is_stream = route_info.get('stream', False)
if is_stream:
    _add_streaming_handler(router, api_adapter, model_class, ...)
else:
    _add_custom_handler(router, api_adapter, model_class, ...)
```

### Phase 4b: HTTP SSE — routes_fastapi.py (Level 1/2)

**File: `src/n3tx/core/api/routes_fastapi.py`** — Modify `make_custom_post()` (line 278)

After calling `attr(instance, **parsed_args)` (line 332), check if result is an async generator:

```python
import inspect
from fastapi.responses import StreamingResponse

result = attr(instance, **parsed_args)
if asyncio.iscoroutine(result):
    result = await result

if inspect.isasyncgen(result):
    async def sse():
        async for chunk in result:
            data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
            yield f"event: chunk\ndata: {json.dumps(data, default=str)}\n\n"
        yield f"event: done\ndata: {{}}\n\n"
    return StreamingResponse(
        sse(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
# else: existing return path
```

Same pattern for `post_no_id` (line 364-367).

---

### Phase 5: WebSocket Streaming

**File: `src/n3tx/core/api/network_ws.py`** — Modify `handle_message()` and `websocket_endpoint()`

**Important**: WS streaming must run in a background task to avoid blocking the client's message loop. If the stream iteration runs inline in `handle_message()`, the WS connection can't process other messages (heartbeats, other requests) until the stream finishes.

```python
async def handle_message(self, client_id: str, msg: dict) -> dict | None:
    """Process a single message. Returns None for streaming (sent directly)."""
    conn = self._connections.get(client_id)
    user = conn['user'] if conn else {}
    tx = self._translate_incoming(msg, user)

    is_stream = msg.get('meta', {}).get('stream', False)
    if is_stream:
        ws = conn['ws']
        # Run stream in background task to avoid blocking the message loop
        asyncio.create_task(self._stream_to_ws(ws, tx))
        return None  # Already handled asynchronously
    else:
        response = await self.request(tx, timeout=30.0)
        return self._translate_outgoing(response)

async def _stream_to_ws(self, ws, tx):
    """Stream chunks directly to a WebSocket client."""
    try:
        async for chunk in self.stream(tx, timeout=120.0):
            response = self._translate_outgoing(chunk)
            response['meta']['stream'] = True
            if chunk.meta.get('stream_end'):
                response['meta']['stream_end'] = True
            await ws.send_json(response)
    except Exception as e:
        logger.error("WS stream error: %s", e)
        try:
            await ws.send_json({
                'name': 'ERROR', 'source': 'ws', 'target': '',
                'data': {'message': str(e), 'code': 500},
                'meta': {'error': True, 'stream_end': True},
            })
        except Exception:
            pass
```

Update `websocket_endpoint()` to handle `None` return:

```python
response = await ws_adapter.handle_message(client_id, raw)
if response is not None:
    await websocket.send_json(response)
```

---

### Phase 6: Frontend Transport — HTTP SSE + Socket.js

**File: `src/n3tx/static/core/transport/HTTP.js`** — Add `stream()` static method:

```javascript
static stream(url, data, onChunk, onDone, onError) {
    const token = window.localStorage?.getItem('jwtToken');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['x-access-token'] = token;

    const controller = new AbortController();

    fetch(url, {
        method: 'POST', headers,
        body: JSON.stringify(data),
        signal: controller.signal,
    }).then(response => {
        if (!response.ok) return response.json().then(onError);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function pump() {
            reader.read().then(({ done, value }) => {
                if (done) { onDone({}); return; }
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();
                let eventType = 'chunk';
                for (const line of lines) {
                    if (line.startsWith('event: ')) eventType = line.slice(7).trim();
                    else if (line.startsWith('data: ')) {
                        try {
                            const parsed = JSON.parse(line.slice(6));
                            if (eventType === 'error') onError(parsed);
                            else if (eventType === 'done') onDone(parsed);
                            else onChunk(parsed);
                        } catch (e) { /* partial JSON, wait */ }
                    }
                }
                pump();
            }).catch(e => {
                if (e.name !== 'AbortError') onError(e);
            });
        }
        pump();
    }).catch(e => {
        if (e.name !== 'AbortError') onError(e);
    });

    // Return abort handle for cancellation
    return { cancel: () => controller.abort() };
}
```

**File: `src/n3tx/static/core/transport/Socket.js`** — Add stream correlation for WS mode:

When in WS mode, the backend sends multiple JSON messages with `meta.stream = true` and the same `meta.req` uuid. Socket.js needs to detect these and dispatch them to a registered stream handler instead of the generic `onmessage`. Without this, stream chunks would route through `matrix.dispatch()` with no component-level correlation.

```javascript
constructor(url) {
    // ... existing ...
    this._streams = new Map();  // req uuid → {onChunk, onDone, onError}
}

/**
 * Register a stream handler for correlated WS messages.
 * @param {string} reqId - The TX uuid that identifies the stream
 * @param {Function} onChunk - Called for each chunk
 * @param {Function} onDone - Called on stream_end
 * @param {Function} onError - Called on error
 * @returns {Function} cancel - Call to unregister the stream
 */
registerStream(reqId, onChunk, onDone, onError) {
    this._streams.set(reqId, { onChunk, onDone, onError });
    return () => this._streams.delete(reqId);
}

// In ws.onmessage handler, before the generic dispatch:
ws.onmessage = (event) => {
    let data;
    try { data = JSON.parse(event.data); }
    catch (e) { Logging.error('[Socket] Failed to parse message', e); return; }

    if (data.heartbeat) return;

    // Stream correlation: route to registered stream handler
    if (data.meta?.stream && data.meta?.req) {
        const handler = this._streams.get(data.meta.req);
        if (handler) {
            if (data.meta.error) {
                handler.onError(data.data);
                this._streams.delete(data.meta.req);
            } else if (data.meta.stream_end) {
                handler.onDone(data.data);
                this._streams.delete(data.meta.req);
            } else {
                handler.onChunk(data.data);
            }
            return;
        }
    }

    // Regular dispatch
    if (this.onmessage) this.onmessage(data);
};
```

**File: `src/n3tx/static/core/transport/NetworkAdapter.js`** — Add `sendStream()`:

```javascript
/**
 * Send a streaming request. Works over both WS and HTTP (SSE).
 *
 * @param {TX|Object} event - The TX to send
 * @param {Function} onChunk - Called for each streamed chunk
 * @param {Function} onDone - Called when stream completes
 * @param {Function} onError - Called on error
 * @returns {{ cancel: Function }} - Call cancel() to abort the stream
 */
sendStream(event, onChunk, onDone, onError) {
    if (this.socket && this.socket.ready) {
        const tx = event instanceof TX ? event : new TX(event);
        tx.meta = { ...(tx.meta || {}), stream: true };
        const reqId = tx._hash || tx.meta._reqId || Date.now().toString(36);
        tx.meta._reqId = reqId;
        const cancel = this.socket.registerStream(reqId, onChunk, onDone, onError);
        this.socket.send(tx);
        return { cancel };
    }
    // HTTP SSE fallback
    const { name, data, target } = event;
    const url = `${target}/${name.toLowerCase()}`;
    return HTTP.stream(url, data, onChunk, onDone, onError);
}
```

---

### Phase 7: Frontend Component — `ntx-stream`

**New file: `src/n3tx/static/components/ntx-stream.js`**

Extends `NTTMethod`. Overrides `callMethod()` to use streaming, adds progressive output rendering. Supports cancellation.

```javascript
import { NTTMethod } from './ntx-method.js';
import HTTP from '../core/transport/HTTP.js';

export class NTTStream extends NTTMethod {
    constructor() {
        super();
        this._chunks = [];
        this._streaming = false;
        this._streamHandle = null;
    }

    callMethod() {
        // Cancel any in-progress stream
        if (this._streamHandle) {
            this._streamHandle.cancel();
            this._streamHandle = null;
        }

        const payload = { ...this.value };
        this._chunks = [];
        this._streaming = true;
        this._renderOutput();

        const href = this.ntt ? `${this.ntt.href}` : this.proto?.href;
        if (!href) return;
        const url = `${href}/${this.method}`;

        this._streamHandle = HTTP.stream(url, payload,
            (chunk) => this._onChunk(chunk),
            (data)  => this._onDone(data),
            (err)   => this._onError(err),
        );
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        // Cancel stream when component is removed from DOM
        if (this._streamHandle) {
            this._streamHandle.cancel();
            this._streamHandle = null;
        }
    }

    _onChunk(data) {
        this._chunks.push(data);
        this._renderOutput();
    }

    _onDone(data) {
        this._streaming = false;
        this._streamHandle = null;
        if (data && Object.keys(data).length) this._chunks.push(data);
        this._renderOutput();
        if (this.ntt?.pull) this.ntt.pull();
    }

    _onError(data) {
        this._streaming = false;
        this._streamHandle = null;
        this.response = { error: data?.message || 'Stream error' };
        this._renderOutput();
    }

    _renderOutput() {
        let el = this.shadowRoot.querySelector('.stream-output');
        if (!el) {
            el = document.createElement('div');
            el.className = 'stream-output';
            this.shadowRoot.appendChild(el);
        }
        const text = this._chunks
            .map(c => c.chunk || c.text || c.content || JSON.stringify(c))
            .join('');
        el.innerHTML = `<div class="stream-text">${this._esc(text)}</div>`
            + (this._streaming ? '<span class="stream-cursor">|</span>' : '');
    }

    _esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

    render() {
        super.render();
        const style = this.shadowRoot.querySelector('style');
        if (style && !style.textContent.includes('stream-output')) {
            style.textContent += NTTStream.streamStyles;
        }
    }

    static streamStyles = `
        .stream-output { margin-top: .75rem; padding: .8rem; background: var(--surface-3);
            border: 1px solid var(--border); border-radius: .5rem; min-height: 2rem;
            max-height: 400px; overflow-y: auto; white-space: pre-wrap; color: var(--text-1); }
        .stream-cursor { animation: blink 1s step-end infinite; color: var(--accent); }
        @keyframes blink { 50% { opacity: 0; } }
        .stream-text { line-height: 1.5; }
    `;
}

customElements.define('ntx-stream', NTTStream);
```

---

## ActivityPub & Streaming

ActivityPub is a discrete-activity protocol — it has no native streaming concept. Activities (Create, Update, Delete) are posted to inboxes as individual HTTP requests. The NetworkAP adapter receives lifecycle events and converts them to AP Activities stored in the outbox.

**Streaming doesn't apply to AP directly.** However, the streaming infrastructure could be used *alongside* AP in two ways:

1. **SSE live feed**: Add an SSE endpoint to `create_federation_routes()` (e.g., `GET /{tablename}/stream`) that streams new activities as they're recorded in the outbox. Remote followers could subscribe for real-time updates instead of polling the outbox. This is what Mastodon does with its Streaming API (`/api/v1/streaming`).

2. **Internal streaming**: When the AP adapter receives an inbound activity that triggers a long-running process (e.g., an agent run), it could use the streaming infrastructure internally to track progress. The AP response would still be a single `202 Accepted` — streaming is for the internal consumer, not the federated peer.

Neither of these is needed now. The streaming infrastructure is AP-compatible by design — when the use case arises, NetworkAP can use `adapter.stream()` or expose an SSE endpoint with zero framework changes.

---

## Files Summary

### Modified
| File | Change |
|------|--------|
| `src/n3tx/core/actors/tx.py` | Rename `in_reply_to` → `req`, add `stream_chunk()` and `stream_end()` |
| `src/n3tx/core/utils/decorators.py` | Add `stream=False` param to `expose_route` |
| `src/n3tx/core/models/proto_model.py` | Include `stream` in method schema (line ~172) |
| `src/n3tx/core/models/actor_model.py` | Async gen detection in `handler()` (line ~116) |
| `src/n3tx/core/api/network_adapter.py` | Rename `in_reply_to` → `req`, add `stream()`, modify `inbox()` for Queue |
| `src/n3tx/core/api/network_api.py` | SSE handler for streaming routes (Level 3) |
| `src/n3tx/core/api/routes_fastapi.py` | SSE support in `make_custom_post()` (Level 1/2) |
| `src/n3tx/core/api/network_ws.py` | WS streaming via background task in `handle_message()` |
| `src/n3tx/static/core/transport/HTTP.js` | Add `stream()` with AbortController cancellation |
| `src/n3tx/static/core/transport/Socket.js` | Add `_streams` Map and `registerStream()` for WS stream correlation |
| `src/n3tx/static/core/transport/NetworkAdapter.js` | Add `sendStream()` with WS/HTTP dual-path |

### Created
| File | Purpose |
|------|---------|
| `src/n3tx/static/components/ntx-stream.js` | Streaming component extending NTTMethod |
| `src/n3tx/core/tests/unit/test_streaming.py` | TX helpers + handler async gen tests |

### Tests to update (Phase 0 rename)
| File | Change |
|------|--------|
| `src/n3tx/core/actors/tests/test_tx.py` | `meta['in_reply_to']` → `meta['req']` |
| `src/n3tx/core/api/tests/test_network_adapter.py` | All `in_reply_to` refs → `req` |
| `src/n3tx/core/tests/unit/test_actor_system.py` | `meta['in_reply_to']` → `meta['req']` |
| `src/n3tx/core/tests/unit/test_actor_model_crud.py` | Test name + assertions |
| `src/n3tx/core/actors/tests/test_actormodel_auth.py` | `meta.get('in_reply_to')` → `meta.get('req')` |

---

## Verification

### Unit tests (`test_streaming.py`)
1. TX.stream_chunk() produces correct meta fields (including `req`)
2. TX.stream_end() produces correct meta fields with stream_end=True
3. NetworkAdapter.inbox() resolves Queue for stream chunks, Future for single replies
4. NetworkAdapter.stream() yields chunks and terminates on stream_end
5. ActorModel.handler() detects async generators and sends stream chunks

### Integration test (add to `example_api/tests/` or `example_actor/tests/`)
1. Create a test model with a streaming `@expose_route(stream=True)` method
2. POST to the endpoint → verify SSE format response (event/data lines)
3. Verify all chunks arrive in order (seq field)
4. Verify stream terminates with `event: done`
5. Verify error during stream produces `event: error`

### Manual frontend test
1. Add `<ntx-stream model="Agent" method="run">` to a page
2. Trigger a streaming method call
3. Verify text appears progressively
4. Verify cursor blinks during streaming, disappears on done
5. Navigate away mid-stream → verify no errors (cancellation works)

### Server startup commands
```bash
# Level 1/2 (direct routes)
cd /workspace/src/n3tx/example && python3 main.py

# Level 3 (actor routing)
cd /workspace && python3 -m n3tx.example.main  # with routing='actor'

# Unit tests
cd /workspace/src/n3tx/core && python3 -m pytest tests/unit/test_streaming.py

# Integration tests
cd /workspace && python3 -m pytest example_actor/tests/
```
