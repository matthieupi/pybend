# Network adapters and remote references

[Package](../README.md) · [Interceptors](interceptors.md) · [ActorModel](actor-model.md)

Adapters translate protocols into TX messages or translate outbound TXs into
network requests. They share messaging primitives, not identical authorization,
validation, response or cancellation guarantees.

```text
HTTP / WS / MCP / AP -> protocol adapter -> TX -> Matrix -> ActorModel
HTTP(S) remote ref  <- RemoteMatrix     <- TX <- Matrix caller
```

## Base adapter

`NetworkAdapter(Actor, auto_register=False)` supplies:

| Method | Behavior |
|---|---|
| `request(tx, timeout=30.0)` | Request interceptors, Future correlation by `meta.req`, response/error TX |
| `stream(tx, timeout=120.0)` | Request interceptors, Queue correlation, background send, async TX iterator |
| `inbox(tx)` | Resolves pending replies before normal Actor dispatch |

Register instances with `matrix.register(adapter)`; adapter constructors do not
automatically mount routes. Outbound adapters additionally need
`matrix.register_adapter(adapter)`. Request timeout is a reply-wait timeout
after inline send, not a total execution budget. Stream timeout applies between
chunks; generator cleanup removes pending state and cancels unfinished sends.
Check `is_error` rather than assuming a returned TX succeeded.

## Protocol decision table

| Adapter | Surface | Important limit |
|---|---|---|
| NetworkAPI | Generated FastAPI CRUD/actions/schema and SSE | Requires the boundary auth interceptor; raw Matrix is different |
| NetworkWebSocket | `/ws?token=JWT`, frontend TX translation | Invalid token becomes anonymous; broadcasts have no per-recipient filtering |
| NetworkMCP | `POST /mcp`, `GET /mcp/tools` | Stock tools/call does not propagate HTTP caller or model metadata |
| NetworkAP | WebFinger, `/{tablename}/inbox`, `/{tablename}/outbox` | No HTTP-signature verification; in-memory outbox/followers |
| RemoteMatrix | HTTP(S) class/entity targets, remote SSE | General outbound URLs; configured remotes are not an allowlist |

### NetworkAPI

Prefer `create_app(..., routing='actor')` or the builder equivalent. Bootstrap
registers finalized actor models, NetworkAPI and its auth interceptor. Manual
integration uses `create_api_routes(api_adapter, registered_models)` on a
registered adapter, with application auth middleware configured separately.

Schema is `GET /ClassName`; table routes provide CRUD; class-name mirrors use
`/ClassName/_` for lists and `/ClassName/{id}` for members. Only declared literal
exposed methods get method routes; there is no generic method catch-all.
`register_view_routes` and `register_extra_routes` hooks can mount capability
routes directly. HTML shells and File byte IO do not round-trip as CRUD TXs.

Generated routes supply trusted user/model metadata. HTTP updates strip
protected fields; raw TX does not reproduce that preprocessing. ActorModel's
JSON-string parsing also differs from direct HTTP string responses.

SSE uses `event: chunk|done|error` and `data: <serialized TX>`, with comment
padding, `Cache-Control: no-cache, no-transform`, and `X-Accel-Buffering: no`.
These discourage buffering but do not guarantee proxy flush timing. Application
events nested in TX data are distinct from outer completion/error flags.

### WebSocket

`create_ws_routes(ws)` mounts the endpoint; configure
`ws.use(auth_interceptor, on='request')` and register it with Matrix. Incoming
frontend names map to backend names (`READ` to list/get, `LOAD` to schema).
Canonical API URLs are stripped and class names mapped through registered
models. Connection user metadata is supplied separately from incoming data.

The explicit class collection target `ClassName/_` currently forces `list`
regardless of the incoming operation. In particular, do not assume a WebSocket
CREATE to that target performs a create; the adapter tests expose this mismatch.

Connection acceptance is not authorization. Token decode failure is logged and
the connection is accepted anonymously. Lifecycle subscriptions broadcast entity
data to **all** connections; do not subscribe private models assuming ABAC
filters the broadcast. Custom-method kwargs do not use NetworkAPI's HTTP
argument parser. Stream tasks are launched in the background; the endpoint does
not implement a complete per-request cancellation/task registry on disconnect.

### MCP

`create_mcp_routes(mcp)` exposes JSON-RPC `initialize`, `ping`, `tools/list` and
`tools/call`. Discovery requests model schemas and caches tool descriptions;
call `invalidate_cache()` after registry changes. Its schema conversion is
separate from n3tx-agents discovery: it generates CRUD specs without the same
storable check and does not supply the same instance-method ID handling.

Tool names split with `rsplit('_', 1)`: underscores in table names work for
simple actions; underscores in method names are ambiguous. Calls return MCP
text content containing JSON, with `isError=True` for error TXs.

**Do not expose stock MCP as an authenticated user API.** The route does not
forward request identity; tools/call builds TXs without `user` or `model_cls`.
Attaching `auth_interceptor` alone therefore does not establish authorization.

### ActivityPub

NetworkAP converts lifecycle create/update/delete into activities and records
them in an in-memory outbox. It supports actor-document generation, WebFinger,
Follow and Undo Follow. Generated routes mount collection inbox/outbox and
WebFinger, not every URL advertised by actor documents.

Inbound CRUD activities use `send()` with federation metadata, no caller and no
model authorization context. There is no HTTP-signature verification or durable
delivery/outbox. `__federated__` discovery is not an ingress authorization gate.
Keep this adapter off untrusted networks unless a separately reviewed boundary
supplies the missing controls; it is not production federation parity.

## RemoteMatrix and RemoteRef

RemoteMatrix preserves absolute HTTP(S) identities. It does not translate them
into `n3tx://` identities. Configured remote base URLs disambiguate API prefixes
and select credentials. Queries/fragments and non-HTTP schemes are rejected.

| Operation | Network behavior |
|---|---|
| `get` on entity target | GET canonical entity URL |
| Other operation | Fetch class schema, resolve method route/scope, POST JSON |
| Instance method without schema metadata | Legacy `/<Class>/<id>/<method>` fallback |
| Class method without schema metadata | No placeholder-ID fallback |
| `remote.stream(tx)` | POST SSE; reconstruct TX envelopes until error/end |

This is not a general CRUD-to-HTTP verb mapper: non-get operations use POST.
Remote streaming is an explicit adapter API, not proof that ordinary Matrix
adapter delegation streams every remote call. RemoteRef supplies async `get()`
and `call(method, **data)`, returning response data or raising RemoteRefError.
`Model.ref(url, matrix=..., user=...)` checks the URL schema matches the model.

Advanced wiring excerpt (requires an existing Matrix, compatible storage,
reachable remote and reviewed credentials; **not** a local smoke test):

```python
from n3tx_actors.api.remote_matrix import RemoteMatrix, MatrixReferenceResolver

remote = RemoteMatrix(remotes=remote_config)
matrix.register(remote)
matrix.register_adapter(remote)
storage.set_reference_resolver(MatrixReferenceResolver(matrix))
```

Outgoing headers include `X-N3TX-Service`, optional `X-N3TX-User` JSON and bearer
token selected from remote token or service-token fallback. Receiving core
middleware trusts forwarded identity only with a matching service token. Such a
token is authority to assert users, not an ordinary user credential.

RemoteMatrix accepts unconfigured entity URLs too and can use the service-token
fallback for them. Restrict destinations before dispatch; never let arbitrary
user URLs receive service credentials. Add egress/SSRF controls and timeouts.
MatrixReferenceResolver can block synchronous storage while resolving remotely;
explicit populate is not free or implicitly safe.

## Evidence and verification

Sources: [API](../src/n3tx_actors/api/network_api.py),
[WS](../src/n3tx_actors/api/network_ws.py),
[MCP](../src/n3tx_actors/api/network_mcp.py),
[AP](../src/n3tx_actors/api/network_ap.py),
[remote](../src/n3tx_actors/api/remote_matrix.py).
Tests: [adapter tests](../src/n3tx_actors/api/tests/),
[remote tests](../src/n3tx_actors/tests/test_remote_matrix.py),
[shutdown tests](../src/n3tx_actors/tests/test_streaming_shutdown.py).
Test each enabled ingress for denied calls, caller spoofing, resource ownership,
stream failure and disconnect; shared TX primitives are not a parity certificate.
