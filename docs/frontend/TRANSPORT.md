# Browser transport

Matrix delegates unknown local targets to `NetworkAdapter`. Application entity UI
should use NTT/components rather than maintaining a second fetching/state layer.

```text
NTT/component TX -> Matrix -> NetworkAdapter
                              +-> ready configured Socket -> WebSocket
                              +-> otherwise HTTP -> reply/error -> Matrix
```

## Configuration

Core `config.js` defaults `API_URL` to the browser origin and `WS_URL` to empty.
Matrix selects WebSocket mode only when `WS_URL` is nonempty at initialization.
Changing config after importing the runtime is not a reliable reinitialization
mechanism. A custom deployment config must preserve the event/constants exports
consumed by the runtime; use native same-origin hosting for the basic app.

Backend schema `$id` determines the model API base used by DynamicClasses.
Configure backend identity and browser origin/CORS consistently. A browser URL
target is not evidence that the destination is trusted to receive credentials.
Do not send authenticated transport calls to arbitrary user-supplied origins.

## HTTP mapping

| TX name | HTTP | Target handling |
|---|---|---|
| `SCHEMA`, `LOAD` | GET | Supplied URL |
| `READ` | GET | Object data encoded as query params; null entries skipped |
| `CREATE` | POST | Trailing collection `/_` removed; JSON body |
| `UPDATE` | PUT | Supplied member URL; JSON body |
| `DELETE` | DELETE | Supplied URL; no body |
| Other/domain method | POST | Remove trailing `/_`, append lowercased message name |
| Domain method with `meta.stream` | POST SSE | Same method URL construction |

Current native collection calls begin at `/Model/_`; creates target `/Model`,
member calls target `/Model/id`. Table-name API routes remain backend compatibility
endpoints, not the current NTT class href convention.

**Method-route limit:** this generic adapter constructs a lowercased method-name
suffix. It does not interpret arbitrary `schema.methods[name].route` or choose
arbitrary HTTP verbs. Do not promise automatic support for renamed/hyphenated
paths or GET-only actions without testing the actual component/transport path.

Successful HTTP replies swap source/target and use `meta.inbox || event.name`.
Debug `{data,_debug}` envelopes are unwrapped. Errors dispatch `ERROR` with the
original event in data and the response/error information in meta. A valid
request source must be registered for reply routing.

## HTTP utility API

Import the default `HTTP` export from `/core/transport/HTTP.js` for low-level
integration. These callback APIs are not promise-returning entity RPC methods.

```text
HTTP.get(url, onSuccess, onError)
HTTP.post(url, data, onSuccess, onError)
HTTP.put(url, data, onSuccess, onError)
HTTP.remove(url, onSuccess, onError)
HTTP.stream(url, data, onChunk, onDone, onError) -> {cancel}
```

Ordinary calls read `localStorage['jwtToken']` and send `x-access-token`. The
ordinary unauthorized path clears stale tokens and redirects to login. SSE has
its own error path; do not assume it performs the same redirect. Client token
storage is exposed to page JavaScript, making XSS prevention important.
Config timeout/retry constants do not establish a universal retry guarantee.

## Streaming

Prefer `ntx-stream` for model methods. The lower-level API below is useful when
testing an already-existing POST streaming endpoint:

```javascript
import HTTP from '/core/transport/HTTP.js';
const handle = HTTP.stream('/Issue/1/generate', {prompt: 'Summarize'},
  chunk => console.log('chunk', chunk),
  done => console.log('complete', done),
  error => console.error(error),
);
// When the caller wants to stop reading:
// handle.cancel();
```

This requires that exact endpoint and parameter schema; it does not create them.
`HTTP.stream` uses Fetch/ReadableStream and returns an AbortController handle.
Its parser expects JSON `data:` lines and `event: chunk|done|error` frames. It is
not a complete general-purpose SSE parser: multiline data and event lines split
across reader chunks need independent verification. The done guard avoids a
second completion callback on normal reader closure after a parsed done event.

| Cancellation surface | Actual guarantee |
|---|---|
| `HTTP.stream(...).cancel()` | Aborts this browser fetch |
| `Socket.registerStream(... )` returned cleanup | Unregisters local callback routing |
| `NTTStream.cancel()` | Ignores later chunks, updates UI, sends cancel-intent TX |
| Backend computation | No general stop/rollback guarantee from those client actions |

The main `NetworkAdapter.send()` SSE path discards the returned abort handle.
`STREAM_CANCEL` currently falls through generic method transport rather than a
dedicated abort registry. Do not claim disconnect automatically cancels backend
work. `sendStream(event,onChunk,onDone,onError)` is a deprecated HTTP compatibility
helper; it is not the preferred WS/HTTP abstraction.

## WebSocket

`Socket` (default export) provides `connect(token)`, `send(tx)`, `close()`, `ready`
and `onmessage`. It queues sends while disconnected, reconnects with backoff, and
sends heartbeat frames. Token authentication is a query parameter; avoid leaking
query strings through logs. The backend must explicitly expose a compatible WS
endpoint; setting `WS_URL` does not create one.

`registerStream(reqId,onChunk,onDone,onError)` handles correlated messages:
`meta.error` terminates with error, `meta.stream_end` terminates with done,
otherwise calls onChunk. Non-correlated messages go to `onmessage`. Matrix's
adapter dispatches those replies back to local actors.

Socket queuing is not durable delivery or exactly-once execution. HTTP fallback
does not prove identical auth, error, ordering or method behavior across transports.
Verify the enabled backend adapter before relying on cross-transport parity.

## Sources and tests

[NetworkAdapter](../../packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js) ·
[HTTP](../../packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js) ·
[Socket](../../packages/n3tx-core/src/n3tx_core/static/core/transport/Socket.js) ·
[transport tests](../../tests/frontend/tests/transport/) ·
[message protocol](MESSAGE_PROTOCOL.md).
