---
name: n3tx-networking
description: N3TX networking through TX, Matrix, NetworkAPI, RemoteMatrix distributed refs, WebSocket, MCP, ActivityPub, adapters, and protocol boundaries. Use when designing internal/external network flows.
argument-hint: "<networking task>"
---

# N3TX Networking

All external protocol interaction should be translated into TX messages at a network adapter boundary.

## Network architecture

```text
HTTP / WebSocket / MCP / ActivityPub / external protocol
   -> NetworkAdapter
   -> TX
   -> Matrix
   -> ActorModel / Actor
   -> TX response/stream
   -> protocol response
```

No protocol is special. Adapters translate protocols to the actor system.

## Built-in adapters

| Adapter | Protocol | Use |
|---|---|---|
| `NetworkAPI` | HTTP REST | Level 3 app routing |
| `NetworkWebSocket` | WebSocket | frontend Matrix bridge |
| `NetworkMCP` | MCP JSON-RPC 2.0 | AI/tool clients |
| `NetworkAP` | ActivityPub | federation |
| `RemoteMatrix` | REST class-name routes + SSE | Distributed `n3tx://service/Class/id` refs and remote streaming |

## Internal networking rule

Do not make internal backend components call each other through plain HTTP. Use direct model/actor calls at local boundaries or TX/Matrix when crossing actor boundaries.

Distributed backend-to-backend refs are the exception that proves the boundary:
code still sends TX to Matrix, and `RemoteMatrix` is the network adapter that
translates canonical `n3tx://service/Class/id` targets into remote REST calls.

```text
TX(name='get', target='n3tx://storage/File/12')
  -> Matrix adapter fallback
  -> RemoteMatrix
  -> GET http://storage:7100/File/12

TX(name='generate', target='n3tx://compute/Job/12', meta={'stream': True})
  -> Matrix adapter fallback
  -> RemoteMatrix.stream()
  -> POST remote generated SSE route
  -> yields TX stream chunks/errors/end
```

Remote requests carry:

```text
Authorization: Bearer <remote-or-service-token>
X-N3TX-Service: <local-service-name>
X-N3TX-User: <json-user-context>  # optional
```

Remote response `$id` values pointing at the configured remote URL are
canonicalized back to `n3tx://service/Class/id` before returning to callers.

For remote streaming methods, prefer schema-first route resolution. `RemoteMatrix`
fetches `GET /{ClassName}` and reads `schema.methods[tx.name].route`, so
decorator routes such as `/upload-to-splat` are not guessed from Python method
names such as `upload_to_splat`. If schema lookup fails, it falls back to the
legacy `/{ClassName}/{id}/{tx.name}` shape for compatibility.

## External networking rule

If an external API must be called, wrap it:

| Use case | Boundary |
|---|---|
| App-specific API client | Non-storable `ActorModel` with `@expose_route` methods |
| API client with persisted credentials/state | Storable `ActorModel` |
| Protocol bridge with custom wire semantics | `NetworkAdapter` |
| Agent-usable external capability | Actor/ActorModel method exposed in schema |

## Example external tool actor

```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False

    @expose_route('/scrape', methods=['POST'])
    async def scrape(self, url: str) -> dict:
        # External HTTP is contained here, behind an actor boundary.
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        return {'url': url, 'text': resp.text[:50000]}
```

## Guardrails

- Do not scatter external clients across app code.
- Do not use raw frontend `fetch()` for N3TX entity behavior.
- Do not create one-off internal HTTP bridges where TX/Matrix is the intended abstraction.
- Do not bypass `RemoteMatrix` for distributed N3TX refs.
- Do not bypass auth interceptors/ActorModel auth by custom transport paths.

## Verification

- Adapter/tool actor is addressable.
- Method appears in schema if it is a tool capability.
- Agent/MCP/UI can reuse the same capability.
- Auth and errors propagate through TX responses.
- RemoteMatrix maps get/method TXs to class-name REST routes and preserves canonical refs.
- RemoteMatrix streaming parses `event: chunk|done|error` SSE frames into TX envelopes and terminates on error or `meta.stream_end`.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
