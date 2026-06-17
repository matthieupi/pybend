---
name: n3tx-streaming
description: N3TX streaming methods, SSE, TX stream protocol, @expose_route(stream=True), schema-declared events, NTTStream, NTTStreamAgent, and progressive UI. Use when building or debugging long-running or realtime output.
argument-hint: "<streaming feature>"
---

# N3TX Streaming

Streaming is schema-declared and TX-correlated.

## Backend streaming method

```python
from pydantic import Field
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.utils.decorators import expose_route

class TextChunk(ProtoModel):
    text: str = Field(default='')

class DoneChunk(ProtoModel):
    answer: str = Field(default='')


class Report(ActorModel):
    __tablename__ = 'reports'
    __storable__ = True

    @expose_route('/generate', methods=['POST'], stream=True,
                  events={'text': TextChunk, 'done': DoneChunk})
    async def generate(self, topic: str):
        yield {'name': 'text', 'data': {'text': f'Starting {topic}'}}
        yield {'name': 'done', 'data': {'answer': 'Complete'}}
```

## TX stream protocol

| Message | Meta |
|---|---|
| chunk | `req`, `stream: True`, `seq` |
| end | `req`, `stream: True`, `stream_end: True`, `seq` |
| error | error TX terminates stream |

## SSE wire format

```text
event: chunk|done|error
data: {json}\n\n
```

Generated N3TX SSE routes serialize the full TX envelope in `data`, not only
`chunk.data`. Consumers should reconstruct or dispatch TXs and stop on an error
TX or `meta.stream_end`.

## Distributed streaming

For backend-to-backend streaming across services, use `RemoteMatrix.stream(tx)`
instead of ad hoc HTTP/SSE clients:

```python
tx = TX(
    name='generate',
    source='app',
    target='n3tx://compute/Job/12',
    data={'prompt': '...'},
    meta={'stream': True, 'user': user},
)
async for chunk in matrix.stream(tx, timeout=120.0):
    if chunk.is_error:
        ...
    elif chunk.meta.get('stream_end'):
        break
    else:
        ...
```

Remote streaming resolves method routes from schema first:
`GET /{ClassName}` -> `schema.methods[tx.name].route`. This preserves decorator
routes such as `/upload-to-splat` and avoids guessing from Python method names.

## Frontend components

| Component | Use |
|---|---|
| `ntx-stream` | Generic streaming method UI |
| `NTTStream` | Base for custom streaming components |
| `NTTStreamAgent` | Rich agent output rendering |
| `ntx-chat` | Agent chat surface |
| `ntx-agent-live` | Agent activity stream |

UPPERCASE handlers process stream events:

```javascript
class MyStream extends NTTStreamAgent {
  TEXT(data, meta) { /* data.text */ }
  DONE(data, meta) { /* data.answer */ }
  STREAM_END(data) { /* cleanup */ }
}
```

## Lifecycle guidance

- Use `prerender()` for structural DOM before schema loads.
- `render()` should be additive and must not wipe `prerender()` output.
- Cancel active streams in `disconnectedCallback()`.

## Guardrails

- Declare event schemas with `events=` for typed frontend contracts.
- Do not invent a parallel streaming protocol for app methods.
- Do not hand-roll backend-to-backend SSE clients for N3TX methods; use TX/Matrix/RemoteMatrix.
- Do not duplicate stream event shapes in frontend code; read method schema.

## Verification

- Schema method has `stream: true` and `events`.
- SSE or WebSocket chunks arrive in order and terminate.
- RemoteMatrix streaming preserves TX chunks, error TXs, service/user headers, and `stream_end` termination.
- Frontend handlers render each event type and clean up on disconnect.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
