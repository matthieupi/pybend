---
name: n3tx-networking
description: N3TX Matrix, NetworkAPI, RemoteMatrix, WebSocket, MCP and ActivityPub transport boundaries. Use when designing internal or external network flows.
argument-hint: "<networking task>"
---

# N3TX Networking

Read [adapters](../../../packages/n3tx-actors/docs/network-adapters.md),
[interceptors](../../../packages/n3tx-actors/docs/interceptors.md) and
[authorization](../../../docs/AUTHORIZATION.md).

| Boundary | Mechanism |
|---|---|
| Direct HTTP | Core route layer, not inherently TX |
| Actor HTTP | NetworkAPI translates HTTP to TX |
| Browser socket | NetworkWebSocket; review collection translation and broadcasts |
| Tool protocol | NetworkMCP; caller policy is not implied by registration |
| Federation | NetworkAP; inspect ingress trust and error contract |
| Remote N3TX identity | RemoteMatrix with absolute HTTP(S) targets |

For example, a configured remote entity target is
`https://storage.example.com/File/12`. Responses retain absolute URL identity;
there is no conversion to a service-name scheme. Remote method streaming resolves
schema-declared routes before fallback. Distinguish domain events from transport
end/error and check timeout/disconnect behavior.

Keep actor communication in Matrix/TX where that boundary is intended. Wrap
reusable third-party I/O in a named capability; do not scatter duplicate clients.
Use local methods for local work when appropriate, without assuming HTTP guards.

Remote tokens and forwarded caller metadata cross a trust boundary. Review
destination allowlists, redirects, credential forwarding and transport-specific
authorization before exposure. A URL pointer or adapter registration is not an
authorization grant. Do not copy unrestricted URL-fetch examples into production.

Test each enabled protocol independently: success, denial, caller continuity,
invalid payloads, errors, correlation and streaming. Do not promise transport
parity or durable delivery. Commands: [AGENTS](../../../AGENTS.md).
