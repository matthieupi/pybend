# Fix: STREAM TX — Route Streaming Through the Actor System

## Context

When streaming methods (like `Product.ask()`) error, the frontend shows nothing — no inline display, no toast, no debug log. Investigation revealed a deeper architectural issue: `NTTStream.callMethod()` bypasses the actor system entirely via direct `HTTP.stream()`.

Digging further, we found that the backend **already creates proper TXs** for stream chunks (`tx.chunk()` in `tx.py`), but `_sse_from_stream()` strips the TX envelope at the SSE boundary, serializing only `chunk.data`. The chunks travel the entire backend actor system as proper transactions, then get demoted to raw data at the last step.

### Decisions Made

1. **TX name**: `STREAM` for all stream chunk TXs
2. **Full TX serialization** at the SSE boundary — frontend receives complete transactions
3. **Envelope pattern**: Outer TX = transport (routing, global seq), inner data = application event (text, done, error, message-level seq). Double meta is intentional — outer tracks global stream, inner tracks current message
4. **`NTTMethod` extends `Component`** — method components become first-class actors with `addr`, `send`, `inbox`. The component sends TXs as itself (`source: this.addr`) and receives replies directly in its own inbox. No `meta.inbox` hack, no handler installation on entities, no observer pattern. `_response_` moves from the TT prototype to the component where it belongs. This also eliminates duplicated entity lifecycle code in `NTTMethod`.
5. **NetworkAdapter.send()** detects `meta.stream` via a single `else if` branch before the catch-all — one line, not a rewrite. Each chunk is atomic and self-describing — no correlation infrastructure needed.
6. **CANCEL** deferred — will be handled via plain transactions in a future pass. No `AbortController` tracking, no `_activeStreams` map.
7. **Toast stays in `NTTStream._onError()`**, actor system handles logging via ERROR TX

## Architecture

```
Envelope Pattern:
┌──────────────────────────────────────────────────────────────────┐
│ TX (transport)                                                   │
│   name: STREAM                                                   │
│   source/target: routing                                         │
│   meta: {req, seq (global), stream: true}                        │
│   uuid, timestamp                                                │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ data (application event)                                     │ │
│ │   name: thinking | text | tool_call | tool_call_delta         │ │
│ │       | done | error                                          │ │
│ │   data: {text: "..."} | {tool_name, args, tool_call_id}      │ │
│ │       | {answer, usage, tool_calls, messages}                  │ │
│ │   meta: {seq (message-level), ...}                            │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

Event types in the inner `name` field:
| name | Source | data shape |
|------|--------|------------|
| `thinking` | `ThinkingPart` / `ThinkingPartDelta` | `{text: "..."}` |
| `text` | `TextPart` / `TextPartDelta` | `{text: "..."}` |
| `tool_call` | `ToolCallPart` (start) | `{tool_name, args, tool_call_id}` |
| `tool_call_delta` | `ToolCallPartDelta` | `{tool_name_delta, args_delta}` |
| `done` | Stream complete | `{answer, usage, tool_calls, messages}` |
| `error` | Exception / missing config | `{message, code}` |

## WebSocket Analysis

**Verdict: No changes needed.** `_stream_to_ws()` in `network_ws.py:207-230` calls `self._translate_outgoing(chunk)` which creates a full TX-shaped dict:

```python
return {
    'name': name,              # from meta['inbox'] or ws_name
    'source': ws_target,       # response source = original target
    'target': ws_source,       # response target = original source
    'data': response.data,     # FULL data preserved (the inner application event)
    'meta': wire_meta,
    'timestamp': response.timestamp,
}
```

Key difference from SSE:
- **SSE** (`_sse_from_stream`): `json.dumps(chunk.data)` — **strips TX envelope** → needs fix
- **WS** (`_stream_to_ws`): `self._translate_outgoing(chunk)` — **preserves full TX structure** → already correct

After the `tx.py` change (name → 'STREAM'), the WS adapter's `_translate_outgoing` still uses `ws_name` from meta (the original frontend event name, e.g., 'ask'), not the raw TX name. This is correct — WS does protocol translation, SSE sends raw backend TXs.

## TODO Triage

TODOs found in `mixin.py` and `product.py`. Relevant ones are included in the changes below; the rest are follow-up work:

| File:Line | TODO | Action |
|-----------|------|--------|
| `mixin.py:505` | `print("RUNNING TASK: ", task)` — dead debug | **Remove** (cleanup) |
| `mixin.py:559` | Returns should be wrapped in proper TX | **Remove comment** (addressed by this plan — `actor_model.py:141` wraps in `tx.chunk()`) |
| `mixin.py:582-583` | Should throw on missing LLM, not silent fallback | **Fix** (error visibility — throw instead of silent default) |
| `mixin.py:644-654` | Add type (tool_call, thinking, etc.) | **Fix** — replace `stream_text()` with typed `ModelResponseStreamEvent` iteration |
| `mixin.py:656-682` | Replace with full output (text, thinking, tool calls) | **Fix** — include tool_calls + message count in done chunk |
| `product.py:106-107` | AsyncGenerator return type validation | Keep — separate concern |
| `product.py:114` | Save agent results in framework | Keep — separate concern |

## Files to Modify

| File | Change |
|------|--------|
| `src/n3tx/core/actors/tx.py` | Rename `stream_chunk()` → `chunk()`, `stream_end()` → `end()`, name → `'STREAM'` |
| `src/n3tx/core/api/network_api.py` | `_sse_from_stream()`: serialize full TX, not just `chunk.data` |
| `src/n3tx/core/agents/mixin.py` | Remove debug print, remove resolved TODO, fix LLM error handling, enrich chunk types + done output |
| `src/n3tx/static/core/transport/NetworkAdapter.js` | `send()`: one `else if (meta?.stream)` branch before the catch-all |
| `src/n3tx/static/core/transport/Socket.js` | Remove stream interception — let stream chunks flow through `matrix.dispatch()` |
| `src/n3tx/static/components/ntx-method.js` | Extend `Component` instead of `HTMLElement` — makes method components first-class actors |
| `src/n3tx/static/components/ntx-stream.js` | Use `this.send()` directly (component is an actor), add `STREAM` handler on inbox |

## Changes

### 1. Backend: `tx.py` — Rename + STREAM TX name

Rename `stream_chunk()` → `chunk()` and `stream_end()` → `end()`. The `STREAM` TX name and `meta.stream` already communicate the context — the method names don't need the prefix.

```python
def chunk(self, data, seq: int) -> 'TX':
    """Create a stream chunk reply."""
    return TX(
        name='STREAM',
        source=self.target, target=self.source,
        data=data if isinstance(data, dict) else {'chunk': data},
        meta={**self.meta, 'req': self.uuid, 'stream': True, 'seq': seq},
    )

def end(self, data=None, seq: int = 0) -> 'TX':
    """Create a stream-end reply."""
    return TX(
        name='STREAM',
        source=self.target, target=self.source,
        data=data if data is not None else {},
        meta={**self.meta, 'req': self.uuid, 'stream': True, 'stream_end': True, 'seq': seq},
    )
```

**Note**: The `meta['stream_end']` wire protocol key stays as-is — only the method names change.

**Call sites to update:**
- `actor_model.py:141` — `tx.stream_chunk(chunk_data, seq)` → `tx.chunk(chunk_data, seq)`
- `actor_model.py:143` — `tx.stream_end(seq=seq)` → `tx.end(seq=seq)`
- `test_streaming.py` — ~30 test calls (`tx.stream_chunk(...)` → `tx.chunk(...)`, `tx.stream_end(...)` → `tx.end(...)`)

### 2. Backend: `network_api.py` — Full TX serialization

Change `_sse_from_stream()` to serialize the full TX, not just `chunk.data`:

```python
from dataclasses import asdict

async def _sse_from_stream(adapter, tx):
    """Convert NetworkAdapter.stream() into SSE text lines."""
    async for chunk in adapter.stream(tx, timeout=120.0):
        tx_dict = asdict(chunk)
        if chunk.is_error:
            yield f"event: error\ndata: {json.dumps(tx_dict)}\n\n"
            return
        if chunk.meta.get('stream_end'):
            yield f"event: done\ndata: {json.dumps(tx_dict, default=str)}\n\n"
            return
        yield f"event: chunk\ndata: {json.dumps(tx_dict, default=str)}\n\n"
```

Now the frontend receives full TXs:
```
event: chunk
data: {"name": "STREAM", "source": "products", "target": "api/...",
       "data": {"name": "text", "data": {"text": "Hello..."},
                "meta": {"stream": true, "seq": 0}},
       "meta": {"req": "abc123", "stream": true, "seq": 0},
       "uuid": "def456", "timestamp": 1710000000}
```

### 3. Backend: `mixin.py` — Cleanup + LLM error handling

**b) Remove resolved TODO** (line 559) — the plan addresses this at the actor system boundary (`actor_model.py:141` wraps yields in `tx.chunk()`):
```python
# DELETE this comment:
# TODO Returns should be wrapped in proper TX, even for stream chunks
```

**c) Fix LLM resolution — throw on missing config** (line 582-583):

Instead of silently falling back to `ollama:llama3.1`, raise an error that flows through the actor system as an ERROR TX:

```python
# In agentic_stream():
llm = _resolve_llm(llm)
if not llm:
    yield {
        'name': 'error',
        'data': {'message': 'No LLM configured. Set __agent__["llm"], pass llm= to run(), or set AGENT_DEFAULTS["llm"].', 'code': 500},
        'meta': {'stream': True, 'error': True, 'seq': 0},
    }
    return
constraints = constraints or {}
```

Same pattern in `agentic()`:
```python
llm = _resolve_llm(llm)
if not llm:
    raise RuntimeError('No LLM configured. Set __agent__["llm"], pass llm= to run(), or set AGENT_DEFAULTS["llm"].')
constraints = constraints or {}
```

The `or 'ollama:llama3.1'` fallback is removed from both `agentic()` and `agentic_stream()`. The 3-tier cascade in `run()`/`run_stream()` still provides `defaults.get('llm', 'ollama:llama3.1')` — so the default is set at the policy layer, not the engine. If someone calls `agentic()` directly without an LLM, they get a clear error instead of a silent wrong default.

**d) Replace `stream_text()` with typed event streaming** (lines 644-654)

**Root cause**: `stream_text(delta=True)` only yields raw `str` tokens and **deliberately discards `ThinkingPart`/`ThinkingPartDelta` events**. That's why there's no way to distinguish thinking from answer in the current output. This is by design in pydantic-ai — `stream_text()` is a convenience that strips metadata.

**Fix**: Replace with iteration over `ModelResponseStreamEvent` objects via the stream's `__aiter__`. pydantic-ai v1.66.0 exposes typed, discriminated events:

| Event | `part_kind` / `part_delta_kind` | Maps to chunk `name` |
|-------|---------------------------------|----------------------|
| `PartStartEvent(part=ThinkingPart)` | `'thinking'` | `'thinking'` |
| `PartDeltaEvent(delta=ThinkingPartDelta)` | `'thinking'` | `'thinking'` |
| `PartStartEvent(part=TextPart)` | `'text'` | `'text'` |
| `PartDeltaEvent(delta=TextPartDelta)` | `'text'` | `'text'` |
| `PartStartEvent(part=ToolCallPart)` | `'tool-call'` | `'tool_call'` |
| `PartDeltaEvent(delta=ToolCallPartDelta)` | `'tool_call'` | `'tool_call'` |

```python
from pydantic_ai.messages import (
    PartStartEvent, PartDeltaEvent,
    TextPart, TextPartDelta,
    ThinkingPart, ThinkingPartDelta,
    ToolCallPart, ToolCallPartDelta,
)

# Replace:
#   async for text in result.stream_text(delta=True):
#       yield {'name': 'text', 'data': {'text': text}, ...}

# With:
streamed_text = ''
async with ai_agent.call_stream(task, **run_kwargs) as result:
    async for event in result:
        if isinstance(event, PartStartEvent):
            if isinstance(event.part, ThinkingPart) and event.part.content:
                yield {
                    'name': 'thinking',
                    'data': {'text': event.part.content},
                    'meta': {'stream': True, 'seq': seq},
                }
                seq += 1
            elif isinstance(event.part, TextPart) and event.part.content:
                streamed_text += event.part.content
                yield {
                    'name': 'text',
                    'data': {'text': event.part.content},
                    'meta': {'stream': True, 'seq': seq},
                }
                seq += 1
            elif isinstance(event.part, ToolCallPart):
                yield {
                    'name': 'tool_call',
                    'data': {
                        'tool_name': event.part.tool_name,
                        'args': event.part.args,
                        'tool_call_id': event.part.tool_call_id,
                    },
                    'meta': {'stream': True, 'seq': seq},
                }
                seq += 1

        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta,
                          ThinkingPartDelta) and event.delta.content_delta:
                yield {
                    'name': 'thinking',
                    'data': {'text': event.delta.content_delta},
                    'meta': {'stream': True, 'seq': seq},
                }
                seq += 1
            elif isinstance(event.delta,
                            TextPartDelta) and event.delta.content_delta:
                streamed_text += event.delta.content_delta
                yield {
                    'name': 'text',
                    'data': {'text': event.delta.content_delta},
                    'meta': {'stream': True, 'seq': seq},
                }
                seq += 1
            elif isinstance(event.delta, ToolCallPartDelta):
                yield {
                    'name': 'tool_call_delta',
                    'data': {
                        'tool_name_delta': event.delta.tool_name_delta,
                        'args_delta': event.delta.args_delta,
                    },
                    'meta': {'stream': True, 'seq': seq},
                }
                seq += 1
```

This gives the frontend typed chunks where `name` distinguishes `thinking` | `text` | `tool_call` | `tool_call_delta` | `done` | `error`. The envelope pattern is now fully realized — the inner `data.name` carries semantic event type, not just `'text'` for everything.

**Provider compatibility**: pydantic-ai handles provider differences transparently:
- **Anthropic**: Native thinking API → `ThinkingPart` with `signature` field (needed for multi-turn)
- **Ollama/local models**: `<think>...</think>` tags → pydantic-ai's `_parts_manager` auto-converts to `ThinkingPart`/`ThinkingPartDelta`
- **OpenAI**: No thinking support → only `TextPart`/`ToolCallPart` events emitted

**e) Enrich done chunk with full output** (lines 656-682)

Currently the done chunk only includes `answer` (text) and `usage`. After switching to typed events, we have richer data. Include tool calls and thinking summary from the message history:

```python
    # After the streaming loop completes:
    usage = result.usage()
    try:
        output = await result.get_output()
    except Exception:
        output = ''
    if not output and streamed_text:
        output = streamed_text

    all_messages = result.all_messages()

    # Extract tool calls from message history
    tool_calls = []
    for msg in all_messages:
        if hasattr(msg, 'parts'):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    tool_calls.append({
                        'tool_name': part.tool_name,
                        'args': part.args,
                        'tool_call_id': part.tool_call_id,
                    })

    yield {
        'name': 'done',
        'data': {
            'answer': str(output),
            'usage': {
                'input_tokens': usage.input_tokens,
                'output_tokens': usage.output_tokens,
                'requests': usage.requests,
            },
            'tool_calls': tool_calls,
            'messages': len(all_messages),
        },
        'meta': {
            'stream': True,
            'stream_end': True,
            'seq': seq,
        },
    }
```

Keep `streamed_text` as a fallback for `get_output()` — some providers (especially Ollama) may return empty output. But now `streamed_text` only accumulates `TextPart`/`TextPartDelta` content (not thinking), which is correct — the answer should not include reasoning tokens.

### 4. Frontend: `NetworkAdapter.send()` — Streaming transport

`send()` already translates TX events into transport-specific calls (GET/POST/PUT/DELETE for HTTP, `socket.send` for WS). Streaming is just another transport mode — no rewrite needed, just two additions.

**The change**: Add one `else if` branch before the existing catch-all `else`.

```javascript
// In send(), before the final else:
else if (meta?.stream) HTTP.stream(`${target}/${name.toLowerCase()}`, data, callback, callback, onError);
else {
    HTTP.post(`${target}/${name.toLowerCase()}`, data, callback, onError);
}
```

That's it — one line. `httpCallback` already wraps raw responses in a reply TX with swapped source/target and dispatches through `matrix.dispatch()`. Each SSE chunk hits `callback` → `httpCallback` → reply TX → `matrix.dispatch()`. No new mechanism — same path as any other HTTP response.

Both `onChunk` and `onDone` use the same `callback` because chunks are self-describing — `meta.stream_end` distinguishes them at the entity level, not the transport level.

**CANCEL**: Not implemented in this pass. Will be handled via plain transactions in the future — no `AbortController` tracking, no `_activeStreams` map.

**`sendStream()` becomes dead code** — `send()` now handles streaming internally. Can be removed or deprecated.

### 5. Frontend: `Socket.js` — Remove stream interception

Currently (lines 75-90), `Socket.js` intercepts stream chunks with `meta.stream && meta.req` and routes them directly to registered handlers, **bypassing `matrix.dispatch()` entirely**:

```javascript
// CURRENT — stream chunks never enter actor system
if (data.meta?.stream && data.meta?.req) {
    const handler = this._streams.get(data.meta.req);
    if (handler) {
        // ... direct callback, return early
        return;
    }
}
if (this.onmessage) this.onmessage(data);  // only non-stream gets here
```

**Remove the interception**. Let stream chunks flow through `onmessage` → `matrix.dispatch()` like every other TX:

```javascript
// AFTER — all messages flow through actor system
this.ws.onmessage = (event) => {
    let data = JSON.parse(event.data);
    if (data.heartbeat) return;
    if (this.onmessage) this.onmessage(data);  // Everything → matrix.dispatch()
};
```

Remove `registerStream()`, `_streams` map, and related correlation infrastructure. The actor system handles routing — no separate stream plumbing needed.

### 6. Frontend: `ntx-method.js` — Extend `Component` (prerequisite)

**Why**: `NTTMethod` currently extends `HTMLElement` and manually reimplements entity lifecycle that `Component` already provides (shadow DOM, model/proto/schema, value management). More importantly, it's not an actor — it can't be a TX target. This forces workarounds like `meta.inbox` to route responses through the entity instead of directly to the component.

`Component` (base for `NTTElement`, `NTTItem`, etc.) is already an actor — it has `addr`, `send`, `inbox`, registers with Matrix. Making `NTTMethod` extend `Component` means both `ntx-method` and `ntx-stream` become first-class actors. Responses route directly to the component's inbox — no `meta.inbox` hack, no handler installation on entities.

**What changes**:

```javascript
import { Component } from '../core/Component.js';

export class NTTMethod extends Component {
    constructor() {
        super();  // Component handles shadow DOM, addr, Matrix registration
        this.value = {};
        this.schema = null;
        this.response = null;
    }
    // ...
}
```

**What `Component` provides for free** (remove from `NTTMethod`):
- `attachShadow({ mode: 'open' })` — done in `Component` constructor
- `model`, `proto`, `schema` getters — inherited
- `addr`, `send`, `inbox` — actor interface
- Matrix registration — automatic in constructor
- `connectedCallback` / `disconnectedCallback` lifecycle with cleanup

**`callMethod()` simplification** — the component sends directly as itself:

```javascript
callMethod() {
    const target = this.ntt?.href || this.proto?.href;
    if (!target) return;

    this.send(new TX({
        name: this.method,
        source: this.addr,       // component IS the source
        target: target,
        data: { ...this.value },
    }));
    this.response = { status: 'sent' };
    this.#postCall();
}
```

Reply TXs route back to `this.addr` → `component.inbox()` → `component._response_(data, tx)`. No `meta.inbox` needed — the component is the source, so `tx.reply()` on the backend swaps source/target naturally.

**`_response_` moves to the component**:

```javascript
_response_(data, tx) {
    this.response = data;
    // Trigger entity refresh so list/item components update
    if (this.ntt?.pull) this.ntt.pull();
    else if (this.proto?.pull) this.proto.pull();
}
```

This replaces `DynamicClass.prototype._response_` on the entity (NTT.js:1097). The `_response_` on TT was always a workaround — it belongs on the component that initiated the call.

**Migration scope**: `ntx-method.js` refactor + remove `_response_` from NTT.js prototype + update tests. `ntx-item.js` and `ntx-ref-picker.js` also use `{inbox: '_response_'}` — those can be migrated in a follow-up since they already extend `Component`.

### 7. Frontend: `ntx-stream.js` — `STREAM` handler on component inbox

With `NTTMethod` extending `Component`, `NTTStream` inherits the actor interface. The component sends the TX as itself and receives stream chunks directly in its own inbox. No handler installation on entities, no `meta.inbox`.

Add imports:
```javascript
import Logging from '../utils/Logging.js';
import { showToast } from '../utils/Toast.js';
```

Remove `HTTP` import (no longer used directly).

Add the `STREAM` handler — this is an inbox handler, same as `_response_`:

```javascript
STREAM(data, tx)
{
    if (tx.meta?.error) return this.#onError(data);
    if (tx.meta?.stream_end) return this.#onDone(data);
    this.#onChunk(data);
}
```

Refactor `callMethod()`:

```javascript
callMethod()
{
    const target = this.ntt?.href || this.proto?.href;
    if (!target) return;
    
    this._chunks = [];
    this.response = null;
    this._streaming = true;
    this.#renderOutput();
    
    // Send through actor system — component IS the source
    this.send(new TX({
        name: this.method,
        source: this.addr,
        target: target,
        data: {...this.value},
        meta: {stream: true},
    }));
}
```

Reply TXs have `target: this.addr` (from `tx.reply()` source/target swap). They arrive at `component.inbox()` → `Actor._inbox` dispatches by `tx.name` → `this.STREAM(data, tx)` for stream chunks. No `meta.inbox`, no handler installation, no cleanup — the component is a proper actor.

**Cancel**: Deferred to a future pass. Will be a CANCEL TX through the actor system.

Fix `_onError()` — toast + inline rendering:

```javascript
#onError(data)
{
    this._streaming = false;
    const msg = (typeof data === 'string') ? data
        : data?.message || data?.detail || data?.error || 'Stream error';
    this.response = {error: msg};
    showToast(msg, 'error');
    Logging.error(`[ntx-stream] ${this.model}.${this.method} error`, msg);
    this.#renderOutput();
}
```

Fix `_onDone()`:

```javascript
#onDone(data)
{
    this._streaming = false;
    if (data && Object.keys(data).length) this.#chunks.push(data);
    this.#renderOutput();
    if (this.ntt?.pull) this.ntt.pull();
}
```

Fix `_renderOutput()` — render error state + handle typed chunks:

```javascript
#renderOutput()
{
    let el = this.shadowRoot.querySelector('.stream-output');
    if (!el) {
        el = document.createElement('div');
        el.className = 'stream-output';
        this.shadowRoot.appendChild(el);
    }
    if (this.response?.error) {
        el.innerHTML = `<div class="stream-error">${this.#esc(this.response.error)}</div>`;
        return;
    }
    const text = this.#chunks
        .map(c => c.data?.text || c.text || c.chunk || c.content || '')
        .join('');
    el.innerHTML = `<div class="stream-text">${this.#esc(text)}</div>`
        + (this.#streaming ? '<span class="stream-cursor">|</span>' : '');
}
```

Add `.stream-error` CSS to `static streamStyles`:
```css
.stream-error { color: var(--error, #f87171); font-style: italic; line-height: 1.5; }
```

## Data Flow: Before vs After

**Before (broken):**
```
Backend: tx.chunk() creates proper TX
  → actor system routes TX correctly
  → _sse_from_stream(): json.dumps(chunk.data)  ← STRIPS TX ENVELOPE
  → Frontend: HTTP.stream() direct call  ← BYPASSES ACTOR SYSTEM
    → Socket.js intercepts stream chunks before Matrix  ← BYPASSES ACTOR SYSTEM
    → _onError(): no toast, no logging, no display
```

**After (correct):**
```
Backend: tx.chunk() creates STREAM TX
  → actor system routes TX correctly
  → _sse_from_stream(): json.dumps(asdict(chunk))  ← FULL TX SERIALIZED

Frontend send:
  component.send(TX { name: 'ask', source: component.addr, target: entity.href, meta: {stream: true} })
    → Matrix → NetworkAdapter.send()
    → send() detects meta.stream → HTTP.stream() / socket.send()

Frontend receive:
  HTTP chunk → httpCallback() wraps in reply TX (target: component.addr) → matrix.dispatch()
    → component.inbox() → Actor._inbox: this['STREAM'](data, tx) → _onChunk()
  WS chunk → matrix.dispatch() (no interception)
    → component.inbox() → Actor._inbox: this['STREAM'](data, tx) → _onChunk()

Cancel (future):
  entity.send(CANCEL TX) → Matrix → NetworkAdapter.send()
    → plain TX handling (deferred — no AbortController in this pass)
```

## Consumers to Update

After the SSE format changes (full TX instead of just data), check consumers:

1. **`ntx-method.js`** — Extend `Component`, `callMethod()` uses `this.send()`, `_response_` on component (§6)
2. **`ntx-stream.js`** — `STREAM` handler on component inbox (§7)
3. **`NTT.js`** — Remove `DynamicClass.prototype._response_` (moved to component in §6)
4. **`ntx-item.js`** / **`ntx-ref-picker.js`** — Still use `{inbox: '_response_'}` through entity. Can migrate to `this.send()` in follow-up (already extend `Component`).
5. **`ntx-chat.js`** — Framework chat widget uses `HTTP.stream()` directly. Needs to migrate to `this.send()` + `STREAM` handler (separate task).
6. **`example_chat/` components** — `ntx-chat-input.js` uses `HTTP.stream()`. Same — migrate (separate task).
7. **`Socket.js`** — Remove `registerStream()`, `_streams` map, stream interception in `onmessage` (§5)
8. **`NetworkAdapter.sendStream()`** — Can be removed or deprecated. `send()` now handles streaming internally (§4).
9. **Backend tests** — `test_streaming.py` SSE assertions need to expect full TX format.

## Verification

```bash
# Backend streaming tests (update assertions for new SSE format)
cd /workspace && python3 -m pytest example_actor/tests/test_streaming.py -v

# Full actor test suite
cd /workspace && python3 -m pytest example_actor/tests/ -v

# Chat tests (verify envelope unwrapping)
cd /workspace && python3 -m pytest example_chat/tests/ -v

# Framework unit tests
cd /workspace/src/n3tx/core && python3 -m pytest tests/unit/ -v

# Frontend unit tests
cd /workspace/src/n3tx/static && npx vitest run
```
