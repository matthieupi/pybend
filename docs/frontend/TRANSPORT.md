# Transport Layer Reference

Documentation for the network bridge between the Actor/Matrix system and the N3TX backend.

## Table of Contents

1. [NetworkAdapter](#networkadapter)
2. [HTTP](#http)
3. [Socket (WebSocket)](#socket)
4. [Request/Response Cycle](#requestresponse-cycle)

---

## NetworkAdapter

**File:** `core/transport/NetworkAdapter.js`

The Matrix's network bridge. Created by the Matrix singleton on construction. Translates TX messages into HTTP requests (or WebSocket frames) and routes responses back through the Matrix.

### Construction

```javascript
// Created inside Matrix constructor:
this.remote = new NetworkAdapter(this, url, mode);
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `matrix` | `Matrix` | Reference to the parent Matrix for dispatching responses. |
| `mode` | `string` | Transport mode: `"http"` or `"ws"`. |
| `url` | `string` | Base API URL (from `config.API_URL`). |
| `socket` | `Socket\|null` | WebSocket instance (only if mode is `"ws"`). |

### send(event)

The main outbound method. Called by `Matrix.inbox()` when a target cannot be resolved locally.

Maps TX event names to HTTP methods:

| `tx.name` (uppercase) | HTTP Method | URL | Data Handling |
|------------------------|-------------|-----|---------------|
| `LOAD` | GET | `{target}` | Ignored |
| `READ` | GET | `{target}?{data as query params}` | Object → URL query params |
| `SCHEMA` | GET | `{target}` | Ignored |
| `CREATE` | POST | `{target}` | JSON body |
| `UPDATE` | PUT | `{target}` | JSON body |
| `DELETE` | DELETE | `{target}` | Ignored |
| `TEST` | GET | `{target}` | Ignored |
| (anything else) | POST | `{target}/{name}` | JSON body |

The `target` field of the TX is used directly as the URL (it's already a full URL like `http://localhost:5000/products`).

**READ query param encoding**: When `tx.data` is a non-null object for a READ event, its entries are encoded as URL query parameters. For example, `{limit: 20, offset: 0}` becomes `?limit=20&offset=0`. Null values are skipped. If the URL already contains a query string, params are appended with `&`.

**Note:** FK hydration hrefs (e.g., `http://localhost:5000/products/1/comments/2`)
are also valid targets. They resolve via the same nested routes registered by the
backend. A READ to such a URL returns the child entity directly.

If mode is `"ws"` and the socket is connected, the event is wrapped as a
TX and sent over WebSocket via `socket.send(tx)`. If the socket is not ready,
the adapter falls back to HTTP.

### httpCallback(event, response)

Called when an HTTP request completes successfully.

```javascript
httpCallback(event, response) {
  // 1. If meta.inbox is set, use it as the new event name
  if (event.meta['inbox'])
    event.name = event.meta['inbox'];

  // 2. Swap source and target (response goes back to the original sender)
  let source = event.source, target = event.target;
  event.source = target;
  event.target = source;

  // 3. Set data to the response body
  event.data = response;

  // 4. Dispatch back through the Matrix
  this.matrix.dispatch(event);
}
```

The `meta.inbox` field is key: it allows the caller to specify what event name the response should arrive as. For example, `DynClass.call('READ', {}, {inbox: 'UPDATE'})` means the response will be dispatched as an UPDATE event rather than READ.

### onError(event, response)

Creates an ERROR event with the original event as data and dispatches it back to the original source.

### pull(target, callback)

Convenience method to send a READ event to a target URL.

### sendStream(event, onChunk, onDone, onError)

Deprecated compatibility helper. The preferred path is `send()` with
`meta.stream = true`, which uses the normal TX/HTTP streaming flow.

Current behavior uses `HTTP.stream()` for SSE.

```javascript
const handle = adapter.sendStream(
    { name: 'generate', target: 'http://localhost:5000/products/1', data: { prompt: 'hello' } },
    (chunk) => console.log('Chunk:', chunk),
    (data)  => console.log('Done:', data),
    (err)   => console.error('Error:', err),
);

// Cancel mid-stream:
handle.cancel();
```

Returns `{ cancel: Function }` for both transports.

---

## HTTP

**File:** `core/transport/HTTP.js`

Static utility class wrapping the Fetch API. All methods use `window.localStorage['jwtToken']` for auth if present.

### Methods

| Method | Signature | HTTP Method |
|--------|-----------|-------------|
| `HTTP.get(url, onSuccess, onError)` | | GET |
| `HTTP.post(url, data, onSuccess, onError)` | | POST |
| `HTTP.put(url, data, onSuccess, onError)` | | PUT |
| `HTTP.remove(url, onSuccess, onError)` | | DELETE |
| `HTTP.stream(url, data, onChunk, onDone, onError)` | | POST (SSE) |

### Common Behavior

1. Creates `Headers` with `x-access-token` if JWT exists in localStorage.
2. For POST/PUT: stringifies data to JSON, sets `Content-Type: application/json`.
3. On success: parses response as JSON, calls `onSuccess(json)`.
4. On 401: redirects to `/login.html`.
5. On error: calls `onError(message)`.

### Static Helpers

| Method | Description |
|--------|-------------|
| `HTTP.rpc(method, args, kwargs, onSuccess)` | RPC-style POST to `/api/rpc`. |
| `HTTP.checkIfUnauthorized(res)` | Returns true if status is 401. |
| `HTTP.checkValidCode(res)` | Returns true for 2xx status codes. |

### stream(url, data, onChunk, onDone, onError)

SSE client for streaming endpoints. Sends a POST request and reads the response as a `ReadableStream`, parsing SSE `event:`/`data:` lines.

```javascript
const handle = HTTP.stream(
    'http://localhost:5000/products/1/generate',
    { prompt: 'hello' },
    (chunk) => console.log('Chunk:', chunk),    // event: chunk
    (data)  => console.log('Done:', data),      // event: done
    (err)   => console.error('Error:', err),    // event: error
);

// Cancel mid-stream:
handle.cancel();
```

**SSE format** expected from server:
```
event: chunk
data: {"chunk": "Part 0"}

event: done
data: {}
```

**Returns** `{ cancel: Function }` — calls `AbortController.abort()` to terminate the stream. Auth token from `localStorage['jwtToken']` is included automatically.

---

## Socket

**File:** `core/transport/Socket.js`

TX-native WebSocket client with:

- auto-reconnect with exponential backoff
- outbound message queue while disconnected
- heartbeat keep-alive every 30s
- optional JWT auth via query parameter

### Construction

```javascript
const socket = new Socket('ws://localhost:5000/ws');
```

### Public Surface

| Property / Method | Description |
|---|---|
| `url` | WebSocket URL |
| `ws` | Underlying `WebSocket` instance or `null` |
| `ready` | `true` when the socket is open and ready to send |
| `onmessage` | callback invoked with parsed non-heartbeat message payloads |
| `connect(token)` | opens the socket; appends `?token=...` when provided |
| `send(tx)` | sends `tx.repr()` or plain payload; queues if disconnected |
| `close()` | closes the socket and disables auto-reconnect |

### Usage

```javascript
const socket = new Socket(wsUrl);
socket.onmessage = (data) => matrix.dispatch(data);
socket.connect(token);
socket.send(tx);
socket.close();
```

### Message Handling

- Incoming WS frames are parsed as JSON.
- Heartbeat frames (`{ heartbeat: true }`) are ignored.
- All other payloads are forwarded to `socket.onmessage(data)`.
- Outbound payloads are JSON-stringified.

### Reconnect / Queue Behavior

- When the socket closes unexpectedly, reconnect is scheduled with exponential backoff.
- Messages sent while disconnected are stored in an internal queue.
- The queue is flushed when the socket opens successfully.

### Obsolete Contract Notes

Older docs/tests referenced a larger Socket API with `sendEvent()`,
`sendMessage()`, `watchdog()`, `Socket.resources`, `Socket.defaultSocket`,
and target registration helpers. That is no longer the intended public
contract for the current transport layer.

### Stream Correlation

`registerStream(reqId, onChunk, onDone, onError)` registers stream handlers for correlated WS messages. When an incoming message has `meta.stream` and `meta.req` matching a registered stream, it is dispatched to the stream handler instead of the generic `onmessage`.

```javascript
const cancel = socket.registerStream(txUuid,
    (chunk) => console.log('Chunk:', chunk),
    (data)  => console.log('Done:', data),
    (err)   => console.error('Error:', err),
);

// Unregister the stream handler:
cancel();
```

Messages are routed based on `meta` fields:
- `meta.error` -> `onError`, then unregister
- `meta.stream_end` -> `onDone`, then unregister
- otherwise -> `onChunk`

---

## Request/Response Cycle

Complete lifecycle of a remote call:

```
1. Actor calls:     DynClass.call('READ', {})

2. DynClass.call() creates TX:
   { name: READ, target: "http://localhost:8000/products",
     data: {}, meta: {} }
   (source omitted — Actor._send assigns DynClass.name during Case 3 bubble)

3. DynClass.send() -> Actor._send()
   Target "http://..." is not in DynClass.children
   -> Bubbles to Matrix

4. Matrix.inbox():
   First segment "http:" not in matrix.children
   -> matrix.remote.send(tx)

5. NetworkAdapter.send():
   name="READ" -> HTTP.get("http://localhost:8000/products", callback, onError)

6. Fetch completes:
   HTTP.get -> onSuccess(jsonData)
   -> NetworkAdapter.httpCallback(originalEvent, jsonData)

7. httpCallback:
   event.name = meta.inbox (if set) or stays "READ"
   event.source = "http://localhost:8000/products"  (was target)
   event.target = "Product"                          (was source)
   event.data = [{id:1, name:"Keyboard",...}, ...]
   matrix.dispatch(event)

8. Matrix.inbox():
   First segment "Product" -> found in matrix.children (DynClass)
   -> DynClass.inbox(tx)

9. DynClass (static) inbox:
   tx.target = "Product" matches DynClass.addr
   -> this["READ"](tx.data) dispatches to DynClass.READ()

10. DynClass.READ():
    Creates/updates N3TX instances from data array
    Replays pending instance ATTACHes
    Notifies all watchers with instance address array
```
