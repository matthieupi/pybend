---
name: n3tx-networking
description: N3TX networking through TX, Matrix, NetworkAPI, WebSocket, MCP, ActivityPub, adapters, and protocol boundaries. Use when designing internal/external network flows.
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

## Internal networking rule

Do not make internal backend components call each other through plain HTTP. Use direct model/actor calls at local boundaries or TX/Matrix when crossing actor boundaries.

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
- Do not bypass auth interceptors/ActorModel auth by custom transport paths.

## Verification

- Adapter/tool actor is addressable.
- Method appears in schema if it is a tool capability.
- Agent/MCP/UI can reuse the same capability.
- Auth and errors propagate through TX responses.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
