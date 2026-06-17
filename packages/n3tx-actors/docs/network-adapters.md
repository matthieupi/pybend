# Network Adapters

> Part of [n3tx-actors](../README.md)

## What This Covers

The NetworkAdapter base class and its concrete adapters: NetworkAPI (HTTP), NetworkWebSocket, NetworkMCP, NetworkAP, and RemoteMatrix. Covers the request/response bridging mechanism, protocol translation, streaming, distributed refs, and route generation. Does not cover the auth interceptor in detail (see [interceptors.md](interceptors.md)).

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

n3tx://storage/File/1
                    -->  RemoteMatrix.send(tx)     --> GET remote /File/1
                    <--  TX reply/error            <-- REST JSON/error
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

`create_api_routes()` generates: schema routes (`GET /{ClassName}`), class-name JSON mirrors for storable root models (`GET /{ClassName}/_`, `POST /{ClassName}`, `GET/PUT/DELETE /{ClassName}/{id:int}`), nested class-name mirrors for unique join pairs (`/{ParentClass}/{parent_id:int}/{ChildClass}[/{child_id:int}]`), legacy table-name CRUD routes (`POST/GET/PUT/DELETE /{tablename}/...`), literal custom method routes from `@expose_route` under both table-name and class-name paths, and streaming routes (SSE for `stream=True` methods). Data/API routes create TXs, call `api.request()` or `api.stream()`, and convert responses via `_response_or_raise()` or SSE framing.

Models may also expose optional HTML/view routes through a package-neutral capability hook:

```python
class Product(ActorModel):
    @classmethod
    def register_view_routes(cls, router, *, tag: str) -> None: ...
```

`n3tx-ui` provides this hook via `ViewableMixin` for models with `__ui__` / `__viewable__`. NetworkAPI delegates to the hook when present, so actor routing supports the same hypermedia routes as direct routing without importing `n3tx_ui`:

- `GET /{ClassName}/@`
- `GET /{ClassName}/@{view}`
- `GET /{ClassName}/{id}/@`
- `GET /{ClassName}/{id}/@{view}`

These HTML/view routes are served directly by the capability hook and do not dispatch CRUD or method TXs. Class-name JSON mirrors still dispatch normal CRUD or literal method TXs to the table-name actor address, preserving payload shape, `populate`, `depth`, authenticated user metadata, `model_cls` metadata, Tier 1/Tier 2 authorization, lifecycle hooks, and streaming metadata. Nested class-name mirrors dispatch to the generated join model actor address, not to the parent or child root model. `GET /{ClassName}` remains the schema endpoint; `GET /{ClassName}/_` is the explicit JSON collection mirror. There is no generic class-name method catch-all.

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

### RemoteMatrix

```python
from n3tx_actors.api.remote_matrix import RemoteMatrix, MatrixReferenceResolver

remote = RemoteMatrix(remotes={'storage': {'url': 'http://storage:7100', 'token': '...'}})
matrix.register(remote)
matrix.register_adapter(remote)
storage.set_reference_resolver(MatrixReferenceResolver(matrix))
```

`RemoteMatrix` handles canonical distributed refs via existing class-name REST routes:

| TX | REST call |
|---|---|
| `TX(name='get', target='n3tx://storage/File/12')` | `GET http://storage:7100/File/12` |
| `TX(name='process', target='n3tx://storage/File/12', data={...})` | `POST http://storage:7100/File/12/process` |
| `TX(name='generate', target='n3tx://compute/Job/12', meta={'stream': True})` | `POST http://compute:7200/Job/12/<schema route>` as SSE |

Remote streaming uses the same TX stream contract as local `NetworkAdapter.stream()`.
`RemoteMatrix.stream(tx)` opens the remote generated SSE route, parses
`event: chunk|done|error` frames incrementally, reconstructs the serialized TX
envelopes, and yields TX chunks until an error or `meta.stream_end` terminates
the stream.

Streaming method URLs are resolved schema-first. The adapter fetches
`GET /{ClassName}`, reads `schema.methods[tx.name].route`, and uses method
`scope` to choose the route shape:

```text
classmethod/staticmethod: /{ClassName}{route}
instance method:          /{ClassName}/{id}{route}
```

If schema lookup fails or the method is not present, `RemoteMatrix` falls back to
the original method route shape `/{ClassName}/{id}/{tx.name}` for compatibility.
This preserves N3TX's model/schema authority while keeping existing simple
remote method calls working.

It attaches service/user context headers:

```text
Authorization: Bearer <remote-or-service-token>
X-N3TX-Service: <local-service-name>
X-N3TX-User: <json-user-context>  # when tx.meta.user is present
```

The receiving N3TX service accepts those headers through the core auth
middleware when `Authorization` matches its configured `SERVICE_TOKEN`. The
forwarded `X-N3TX-User` JSON becomes `request.state.user`, so generated routes
and ActorModel handlers continue through the normal ABAC path. Remote response
`$id` values that point back at the configured remote URL are normalized to the
canonical `n3tx://service/Class/id` identity before returning to Matrix callers.

`MatrixReferenceResolver` is the storage-facing adapter: `SQLiteStorage` can
receive it as `reference_resolver` and keep core independent from actors.

For explicit Python method calls, prefer the model-centric `ActorModel.ref()`
helper:

```python
artifact = Artifact.ref('n3tx://storage/Artifact/42', matrix=matrix)
data = await artifact.get()
result = await artifact.call('process', mode='fast')
```

Internally this returns a `RemoteRef` handle. `ActorProxy` is different: it wraps
a local Python object/class as an actor; `RemoteRef` calls a remote `n3tx://...`
identity through Matrix.

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

Frames are intentionally anti-buffered: each SSE message starts with a large
comment padding line and responses set `Cache-Control: no-cache, no-transform`
plus `X-Accel-Buffering: no`. This keeps browser/proxy stacks from coalescing
small model-generated chunks and preserves progressive first-token delivery.

## Gotchas

- **All adapters must use `auto_register=False`** and be manually registered via `matrix.register()`. They require constructor arguments and manual setup (interceptors, etc.).
- **`request()` timeout returns an error TX, not an exception.** Always check `response.is_error` before accessing `response.data`.
- **`stream()` launches `send()` as a background task** (`asyncio.create_task`). This prevents the full async generator from being consumed before chunks can be yielded. Do not change this to `await self.send(tx)`.
- **WebSocket protocol translation strips API_URL prefix** from targets and maps frontend UPPERCASE names. If `config.API_URL` is not set correctly, routing will fail silently.
- **MCP tool names use `rsplit('_', 1)`** to parse `{tablename}_{action}`. Model tablenames containing underscores will be parsed incorrectly (e.g., `product_reviews_list` splits as `product_reviews` + `list`, which is correct, but `my_products_list` would also work if tablename is `my_products`).
- **NetworkAP stores outbox in memory** (`_outbox` dict). Activities are lost on restart. Persistent outbox storage is deferred to Wave 4+.
- **RemoteMatrix is REST-backed in the first slice.** It intentionally reuses
  existing class-name routes instead of introducing generic `/_tx` ingress.
