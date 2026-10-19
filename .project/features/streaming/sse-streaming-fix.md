# SSE Streaming Bug: Deep Analysis of Option B vs Option C

## Context

When using Level 3 (actor routing) SSE streaming (e.g., `Product.ask`), events arrive correctly but nothing is displayed in `<ntx-stream>`. Three interacting bugs cause this:

1. **Double-wrapping**: `_sse_from_stream()` sends full TX envelope; `httpCallback()` wraps it again as `reply.data`
2. **Lost meta**: Reply uses original request's meta, not the SSE chunk's meta (stream_end/error invisible)
3. **Same callback**: `HTTP.stream(url, data, callback, callback, onError)` — chunk/done distinction lost

**Files**: NetworkAdapter.js:37-52 (httpCallback), :146-162 (stream branch), network_api.py:469-485 (_sse_from_stream), ntx-stream.js:101-103 (#renderOutput)

---

## The Architectural Inconsistency

The bug reveals a deeper issue: **the HTTP/SSE and WebSocket adapters follow different patterns for streaming**.

### WebSocket Adapter (already works correctly)
`network_ws.py` implements a clean translate-in/translate-out pattern:

```
Frontend TX → _translate_incoming() → Backend TX → Actor → Response TX → _translate_outgoing() → Frontend TX
```

Key: `_translate_incoming()` (line 84-87) **preserves frontend identity** in meta:
```python
tx_meta = {
    'ws_source': original_source,    # 'NTTStream-abc123'
    'ws_target': original_target,    # 'http://localhost:5000/products/42'
    'ws_name': original_name,        # 'ask'
}
```

`_translate_outgoing()` (line 153-181) **reconstructs frontend addresses** from meta:
```python
return {
    'name': meta.get('inbox', ws_name),
    'source': ws_target,   # Response source = original target
    'target': ws_source,   # Response target = original source
    'data': response.data, # Unwrapped from TX envelope
    'meta': wire_meta,     # Cleaned, serializable
}
```

`_stream_to_ws()` (line 207-230) calls `_translate_outgoing(chunk)` on **each streaming chunk** — proper unwrapping + address reconstruction.

### HTTP/SSE Adapter (currently broken for streaming)
`network_api.py` has **no translate pattern** for streaming:

```
HTTP Request → TX(source='api') → Actor → Response TX → asdict(chunk) → raw SSE → Frontend must figure it out
```

For non-streaming requests, the adapter simply returns `response.data` (the TX payload), and the frontend `httpCallback` handles the rest. But for streaming, `_sse_from_stream()` serializes the **entire TX envelope** — backend addresses (`source: 'products'`, `target: 'api'`), non-serializable meta (`model_cls`), everything — and the frontend has no translation layer to handle it.

**This is not just a bug — it's a missing adapter feature.** The WS adapter has it. The HTTP adapter doesn't.

---

## Option B: Frontend-Side Translation

### Mental Model
*"The HTTP adapter sends raw TX envelopes. The frontend NetworkAdapter.js knows how to unwrap them based on format detection."*

### What Changes
**1 file**: `NetworkAdapter.js` — replace the streaming branch (lines 146-162)

The frontend detects TX envelopes (`response?.uuid && response?.source`) and unwraps:
- `data: isTxEnvelope ? response.data : response` — strips TX wrapper
- `meta: isTxEnvelope ? response.meta : event.meta` — uses chunk's meta (has stream_end, error)
- `source/target`: from original request event (frontend addresses already known)
- Separate `onStreamChunk`/`onStreamDone` callbacks + double-done guard

### What This Gives You
- **Immediate bug fix** — streaming displays text, stream_end detected, errors propagated
- **Both Level 1/2 and Level 3 work** — format detection handles both transparently
- **UUID pass-through** — `uuid: response.uuid` gives cross-boundary correlation for free
- **Zero backend changes** — no risk to existing backend behavior

### What This Doesn't Give You
- **No backend observability** — backend logs don't know which frontend component requested the stream
- **No server-push targeting** — backend can't route a message to a specific component
- **Pattern inconsistency** — WS does translation on backend (`_translate_outgoing`), HTTP does it on frontend (closure vars)
- **Per-transport logic** — each transport (HTTP, WS, future gRPC) needs its own frontend handling code

### Developer Experience
- Frontend devs need to understand that SSE data format differs between Level 1/2 (raw chunk) and Level 3 (TX envelope)
- The `isTxEnvelope` heuristic is a format-sniffing workaround, not a contract
- Adding a new transport means adding new frontend detection/unwrapping logic

### Implementation Cost
~20 LOC changed, 1 file, ~6 new frontend tests.

---

## Option C: Backend-Side Translation (Aligned with WS)

### Mental Model
*"Every transport adapter (HTTP, WS, future) preserves frontend identity and delivers translated responses. The frontend just dispatches. One pattern, all transports."*

### What Changes
**3 files**: NetworkAdapter.js, network_api.py, (optionally HTTP.js for header support)

#### Backend: Add `_translate_outgoing` to SSE path

`_sse_from_stream()` currently does `asdict(chunk)`. Change it to translate each chunk like the WS adapter does:

```python
async def _sse_from_stream(adapter, tx):
    async for chunk in adapter.stream(tx, timeout=120.0):
        # Translate: unwrap TX envelope, reconstruct frontend addresses
        translated = _translate_outgoing(chunk)
        event_type = 'error' if chunk.is_error else ('done' if chunk.meta.get('stream_end') else 'chunk')
        yield f"event: {event_type}\ndata: {json.dumps(translated, default=str)}\n\n"
        if event_type in ('error', 'done'):
            return
```

Where `_translate_outgoing` mirrors the WS adapter's pattern:
```python
def _translate_outgoing(response: TX) -> dict:
    meta = response.meta or {}
    return {
        'name': meta.get('inbox', meta.get('frontend_name', response.name)),
        'source': meta.get('frontend_target', response.source),
        'target': meta.get('frontend_source', response.target),
        'data': response.data,
        'meta': {k: v for k, v in meta.items()
                 if k not in _NON_SERIALIZABLE_META | _FRONTEND_META_KEYS},
        'timestamp': response.timestamp,
        'uuid': response.uuid,
    }
```

#### Backend: Preserve frontend identity in TX meta

`_add_streaming_handler()` reads frontend source from HTTP header:
```python
tx = TX(
    name=_attr_name,
    source=api_adapter.addr,       # backend routing (stays 'api')
    target=_addr,                  # backend routing (stays 'products')
    meta={
        'user': user,
        'model_cls': _cls,
        'stream': True,
        'frontend_source': request.headers.get('X-TX-Source', ''),
        'frontend_target': str(request.url),
        'frontend_name': _attr_name.upper(),
    },
)
```

#### Frontend: Send source header + dispatch directly

```javascript
// In NetworkAdapter.send(), streaming branch:
else if (meta?.stream) {
    let streamEnded = false;
    const onStreamData = (response) => {
        // SSE data is already translated by backend — dispatch directly
        if (!response?.name) return;
        this.matrix.dispatch(response);
    };
    const onStreamDone = (response) => {
        if (streamEnded) return;
        streamEnded = true;
        const data = response?.name ? response : {
            name: meta?.['inbox'] || name,
            source: target, target: source,
            data: {}, meta: { stream_end: true },
        };
        if (!data.meta) data.meta = {};
        data.meta.stream_end = true;
        this.matrix.dispatch(data);
    };
    // Include frontend source address in header for backend identity preservation
    HTTP.stream(`${target}/${name.toLowerCase()}`, data, onStreamData, onStreamDone, onError,
        { 'X-TX-Source': source });
}
```

### What This Gives You
- **Everything Option B gives** (bug fix, both levels, UUID correlation)
- **Backend observability** — backend can log `"Streaming to NTTStream-abc on product 42"`
- **Server-push targeting** — backend knows which component to notify (future: agent redirects output to a different component)
- **Pattern consistency** — HTTP and WS streaming follow the same translate-in/translate-out pattern
- **One frontend path** — all transports deliver pre-translated responses; frontend just dispatches
- **Foundation for multi-modal output** — agent streams text to NTTStream, chart data to NTTChart (different targets in same stream)

### What This Costs
- **HTTP header convention** — `X-TX-Source` header (simple, but new convention)
- **Backend meta keys** — `frontend_source`, `frontend_target`, `frontend_name` (mirrors WS's `ws_source` etc.)
- **Broader change surface** — 3 files, ~40 LOC, backend + frontend
- **Level 1/2 gap** — Level 1/2 `routes_fastapi.py` doesn't use the adapter pattern; would need separate handling or remain unchanged (SSE data stays raw, frontend Option B detection still needed as fallback)

### Developer Experience
- One pattern for all transports: "adapter preserves frontend identity, translates on response"
- SSE data on the wire is clean, pre-translated — no format sniffing needed
- New transport = implement `_translate_incoming` + `_translate_outgoing` on the backend adapter
- Frontend adapter just dispatches what it receives

### Implementation Cost
~40 LOC changed, 3 files, same tests as Option B plus backend translation tests.

---

## Head-to-Head Comparison

| Dimension | Option B (Frontend Translation) | Option C (Backend Translation) |
|-----------|-------------------------------|-------------------------------|
| **Fix effort** | 1 file, ~20 LOC | 3 files, ~40 LOC |
| **Backend changes** | None | 2 files (read header, translate outgoing) |
| **Bug fix** | Complete | Complete |
| **Mental model** | Two address spaces, frontend bridges | One TX with identity preservation |
| **Pattern consistency** | HTTP ≠ WS (different translation locations) | HTTP = WS (same adapter pattern) |
| **Observability** | Frontend-only tracing | End-to-end tracing (UUID + component addr) |
| **Server push to component** | Not possible | Possible (backend knows component) |
| **Agent output routing** | Not possible | Possible (change meta target) |
| **Multi-modal streaming** | Not possible | Possible (different targets per chunk) |
| **Level 1/2 compat** | Full (format detection) | Partial (Level 1/2 stays raw, needs B as fallback) |
| **New transport cost** | Frontend detection per transport | Backend translate per adapter |
| **Wire format** | Raw TX envelope (Level 3) or raw data (Level 1/2) | Pre-translated, clean JSON (all levels) |
| **Address coupling** | None (clean separation) | Frontend addr in backend meta (pass-through only) |

---

## What Each Approach Means for the Architecture

### Option B preserves the current contract:
> "The HTTP boundary is a clean break. Frontend and backend are separate worlds. The adapter translates at the edge."

This is the REST mindset. Each side is self-contained. The adapter does the minimum translation. Frontend code handles transport-specific quirks.

### Option C extends the actor model across the network:
> "The TX is the universal message. It flows from component to actor and back. The network transport is just plumbing — it doesn't create new TXs or lose identity."

This is the actor system mindset. Messages have identity and addressability. The adapter preserves identity across transport boundaries. The WS adapter already works this way — Option C aligns HTTP to match.

---

## Recommendation

**Both options fix the bug equally well.** The choice depends on where you want the architecture to go:

- **If HTTP/SSE streaming is an edge case** and WS is the primary streaming transport → **Option B** is sufficient. Fix the frontend, move on.

- **If you want all transports to follow the same pattern** and want backend observability + future server-push capabilities → **Option C** is the right investment. It's 2x the code but aligns the architecture.

- **Pragmatic hybrid**: Implement **Option B now** (immediate fix), then refactor to **Option C** as a separate architectural alignment task. Option B's `isTxEnvelope` detection naturally serves as a fallback when Option C's backend translation is added later.

---

## Implementation Scope Summary

### Option B Touches
| File | Change |
|------|--------|
| `packages/n3tx-core/.../transport/NetworkAdapter.js` | Replace streaming branch (lines 146-162): TX envelope detection, separate chunk/done callbacks, double-done guard |

### Option C Touches
| File | Change |
|------|--------|
| `packages/n3tx-core/.../transport/NetworkAdapter.js` | Simplify streaming branch: dispatch pre-translated SSE directly, send `X-TX-Source` header |
| `packages/n3tx-actors/.../api/network_api.py` | `_sse_from_stream()`: translate each chunk via `_translate_outgoing()`. `_add_streaming_handler()`: read `X-TX-Source` header, store in meta |
| `packages/n3tx-core/.../transport/HTTP.js` | (Optional) Pass custom headers to `fetch()` in `stream()` method |

### Files Not Changed (either option)
| File | Why |
|------|-----|
| `packages/n3tx-ui/.../components/ntx-stream.js` | `#renderOutput()` extraction `c.data?.text` works correctly once TX envelope is unwrapped |
| `packages/n3tx-actors/.../api/network_ws.py` | Already works — serves as the reference pattern for Option C |
| `packages/n3tx-actors/.../api/network_adapter.py` | Base adapter class — stream()/inbox() correlation by UUID already correct |
| `packages/n3tx-actors/.../tx.py` | TX.chunk()/end() already produce correct envelopes |

### Test Coverage Needed
Both options need the same frontend unit tests:
1. TX envelope chunks unwrapped correctly (Level 3)
2. Raw chunks pass through unchanged (Level 1/2)
3. stream_end detected from correct source (TX meta or done callback)
4. Method name preserved in dispatch (not "STREAM")
5. Double-done guard (reader close after SSE done)

Option C additionally needs backend tests for `_translate_outgoing()` and `X-TX-Source` header preservation.
