# Network Adapters

> Part of [n3tx-actors](../README.md)

## What This Covers

The NetworkAdapter base class and its four concrete adapters: NetworkAPI (HTTP), NetworkWebSocket, NetworkMCP, NetworkAP. Covers the request/response bridging mechanism, protocol translation, streaming, and route generation. Does not cover the auth interceptor in detail (see [interceptors.md](interceptors.md)).

## Architecture

```
External Protocol         NetworkAdapter             Matrix / Actor Tree
-----------------         ---------------            -------------------
HTTP POST /products  -->  NetworkAPI.request(tx)  --> matrix.inbox(tx)
                          [interceptors: auth]        --> Product.handler_crud()
                          future = pending[uuid]      <-- reply TX
                     <--  future.set_result(reply)    (via adapter.inbox correlation)

WebSocket message    -->  NetworkWebSocket            --> matrix.inbox(tx)
                          .handle_message(msg)
                          _translate_incoming()
                     <--  _translate_outgoing()

MCP JSON-RPC         -->  NetworkMCP                  --> matrix.inbox(tx)
                          .handle_jsonrpc(body)
                     <--  JSON-RPC response

AP Activity          -->  NetworkAP                   --> matrix.inbox(tx)
                          .handle_inbox(activity)
                     <--  AP response
```

All adapters extend `NetworkAdapter(Actor, auto_register=False)`. They register as Matrix children via `matrix.register(adapter)`. Response TXs route back through normal Matrix routing -- the adapter's `inbox()` checks for pending correlation before falling through to normal dispatch.

## Interface

### NetworkAdapter (base)

```python
class NetworkAdapter(Actor, auto_register=False):
    async def inbox(self, tx: TX) -> None: ...
    async def request(self, tx: TX, timeout=30.0) -> TX: ...
    async def stream(self, tx: TX, timeout=120.0) -> AsyncGenerator[TX]: ...
```

`request()` bridges synchronous protocols to async actors: stores a Future keyed by `tx.uuid`, sends the TX, awaits the correlated reply (matched via `meta['req']`). Timeout returns error TX with code 504.

`stream()` uses an `asyncio.Queue` instead of a Future. Yields TX chunks until `stream_end` or error. Launches `send()` as a background task to enable progressive delivery.

### NetworkAPI

```python
api = NetworkAPI(addr='api')   # default addr='api'
matrix.register(api)
api.use(auth_interceptor, on='request')
router = create_api_routes(api, registered_models)
app.include_router(router)
```

`create_api_routes()` generates: schema routes (`GET /{ClassName}`), CRUD routes (`POST/GET/PUT/DELETE /{tablename}/...`), custom method routes (from `@expose_route`), streaming routes (SSE for `stream=True` methods). All routes create TX, call `api.request()`, convert response via `_response_or_raise()`.

### NetworkWebSocket

```python
ws = NetworkWebSocket(addr='ws')
matrix.register(ws)
router = create_ws_routes(ws)
app.include_router(router)
```

WebSocket endpoint at `/ws?token=JWT`. Protocol translation: frontend UPPERCASE names mapped to backend lowercase (`READ`->`list`, `LOAD`->`schema`). Full URL targets stripped to local addresses. Lifecycle events broadcast to all connected clients.

### NetworkMCP

```python
mcp = NetworkMCP(addr='mcp')
matrix.register(mcp)
router = create_mcp_routes(mcp)
app.include_router(router)
```

JSON-RPC 2.0 endpoint at `POST /mcp`. Supports `initialize`, `tools/list`, `tools/call`, `ping`. Tool names follow `{tablename}_{action}` pattern. Schemas cached, invalidated via `mcp.invalidate_cache()`.

### NetworkAP

```python
ap = NetworkAP(addr='ap', base_url='https://example.com')
matrix.register(ap)
router = create_federation_routes(ap)
app.include_router(router)
```

Endpoints: `GET /.well-known/webfinger`, `GET /{tablename}/outbox`, `POST /{tablename}/inbox`. Models with `__federated__ = True` get AP actor documents, outbox recording, Follow/Unfollow handling.

## Usage Patterns

### Level 3 wiring (full actor routing)

```python
from n3tx_actors import matrix
from n3tx_actors.api.network_api import NetworkAPI, create_api_routes
from n3tx_actors.api.network_ws import NetworkWebSocket, create_ws_routes
from n3tx_actors.api.auth_interceptor import auth_interceptor

api = NetworkAPI()
ws = NetworkWebSocket()
matrix.register(api)
matrix.register(ws)
api.use(auth_interceptor, on='request')
ws.use(auth_interceptor, on='request')

app.include_router(create_api_routes(api, registered_models))
app.include_router(create_ws_routes(ws))
```

### SSE streaming through NetworkAPI

Streaming `@expose_route(stream=True)` methods produce SSE responses. The adapter calls `stream()` internally and converts TX chunks to SSE format: `event: chunk|done|error`, `data: {json TX envelope}`.

## Gotchas

- **All adapters must use `auto_register=False`** and be manually registered via `matrix.register()`. They require constructor arguments and manual setup (interceptors, etc.).
- **`request()` timeout returns an error TX, not an exception.** Always check `response.is_error` before accessing `response.data`.
- **`stream()` launches `send()` as a background task** (`asyncio.create_task`). This prevents the full async generator from being consumed before chunks can be yielded. Do not change this to `await self.send(tx)`.
- **WebSocket protocol translation strips API_URL prefix** from targets and maps frontend UPPERCASE names. If `config.API_URL` is not set correctly, routing will fail silently.
- **MCP tool names use `rsplit('_', 1)`** to parse `{tablename}_{action}`. Model tablenames containing underscores will be parsed incorrectly (e.g., `product_reviews_list` splits as `product_reviews` + `list`, which is correct, but `my_products_list` would also work if tablename is `my_products`).
- **NetworkAP stores outbox in memory** (`_outbox` dict). Activities are lost on restart. Persistent outbox storage is deferred to Wave 4+.
