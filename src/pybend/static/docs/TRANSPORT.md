# Transport Layer Reference

Documentation for the network bridge between the Actor/Matrix system and the PyBend backend.

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
this.remote = new NetworkAdapter(this, url);

// Also exported as a module-level singleton (legacy):
export const remote = new NetworkAdapter('http');
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

If mode is `"ws"`, the event is sent as a WebSocket frame instead.

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

### Common Behavior

1. Creates `Headers` with `x-access-token` if JWT exists in localStorage.
2. For POST/PUT: stringifies data to JSON, sets `Content-Type: application/json`.
3. On success: parses response as JSON, calls `onSuccess(json)`.
4. On 401: redirects to `/#login`.
5. On error: calls `onError(message)`.

### Static Helpers

| Method | Description |
|--------|-------------|
| `HTTP.rpc(method, args, kwargs, onSuccess)` | RPC-style POST to `/api/rpc`. |
| `HTTP.checkIfUnauthorized(res)` | Returns true if status is 401. |
| `HTTP.checkValidCode(res)` | Returns true for 2xx status codes. |

---

## Socket

**File:** `core/transport/Socket.js`

WebSocket client with automatic heartbeat, reconnection, and message queuing.

**Note:** WebSocket mode is not actively used in the current v0.8 development. The system defaults to HTTP mode. A WebSocket bridge connecting frontend actors to backend actors is planned for Wave 3 (see [ARCHITECTURE.md](./ARCHITECTURE.md#upcoming-backend-actor-bridge)).

### Construction

```javascript
new Socket(url, targets={}, ttl=1000)
```

- Connects to `ws://{url}`
- Starts a heartbeat watchdog at `ttl` interval
- Registers itself in `Socket.resources`

### State Machine

```
CONNECTING -> WAITING -> CONNECTED
                |
                v
FAILED -> reconnect() (up to MAX_TRIES=5)
                |
                v
DISCONNECTED
```

### Key Methods

| Method | Description |
|--------|-------------|
| `connect(url)` | Opens WebSocket, sets up event handlers. |
| `reconnect()` | Closes and reopens connection (retries up to 5 times). |
| `disconnect()` | Closes connection, clears watchdog interval. |
| `sendMessage(key, msg)` | Sends JSON message. Queues if not connected. |
| `sendEvent(event)` | Sends event as raw string. |
| `heartbeat()` | Resets LRH timer, sends heartbeat. |
| `watchdog()` | Runs on interval. Checks connection health, triggers reconnect if needed. |

### Message Handling

Incoming messages are parsed as JSON and dispatched to registered targets via `dispatchEvent(event)`. Heartbeat messages are handled internally.

Queued messages (sent while disconnected) are flushed when the connection is re-established.

### Target Registration

```javascript
socket.setTarget(targetAddr, callback);
socket.removeTarget(targetAddr);
```

Targets receive events dispatched by the socket's `onMessage` handler.

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
    Creates/updates NTT instances from data array
    Replays pending instance ATTACHes
    Notifies all watchers with instance address array
```
