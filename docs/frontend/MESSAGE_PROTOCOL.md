# Browser message protocol

TX is the local browser message envelope. Network adapters translate it; this
document does not promise byte-identical Python/JavaScript envelopes.

## Envelope

```javascript
import TX from '/core/TX.js';
const message = new TX({
  name: 'READ',
  source: 'Issue',
  target: `${window.location.origin}/Issue/_`,
  data: {limit: 20, offset: 0},
  meta: {inbox: 'UPDATE'},
});
console.log(message.repr()); // inspection only; not dispatched here
```

`name`, `source`, `target`, `data`, `meta` are the routing fields. Construction
accepts `timestamp`; serialization uses `tst` and a cached `hash` field. The hash
is not a signature or authorization credential. Do not rely on timestamp/hash
round-trip fidelity as a wire guarantee. Stream correlation is explicit `meta.req`.

| Metadata | Use |
|---|---|
| `inbox` | Response handler name override |
| `remote` | Network-path marker, not a permission grant |
| `stream`, `req`, `seq` | Stream marker, correlation and sequence |
| `stream_end` | Terminal transport message |
| `error`, `response`, `validationErrors` | Error marker and transport error details |

## Lifecycle trace

```text
component -- ATTACH(model/ref) --> NTT registry
registry  -- SCHEMA -----------> API /Model
schema    -- class creation ---> queued attachments replayed
list      -- READ -------------> API /Model/_
response  -- READ/UPDATE ------> DynamicClass cache
class     -- UPDATE(addrs) ----> list -> child components
entity    -- DESCRIBE ---------> child {proto: schema, data: value}
```

SCHEMA completion does not initiate collection reads. `ListElement` owns those
reads; member ATTACH can initiate an individual read. This distinction prevents
confusing a class-ready callback with a data-ready callback.

## Message reference

| Name | From -> to | Payload/effect |
|---|---|---|
| `ATTACH` | Component -> `NTT` -> class/entity | Model name or `Model/id`; subscribe/resolve |
| `SCHEMA` | NTT <-> API | Schema request/response; `$defs` registration |
| `READ` | Class/entity -> API | Query data; response upserts entities |
| `UPDATE` | Class -> list | Array of entity addresses |
| `DESCRIBE` | Entity -> component | `{proto, data}` initializes schema/value |
| `CREATE` | Class <-> API | New entity; success adds to cache and notifies lists |
| `UPDATE` | Component -> entity -> API | Save; local mutation may precede response |
| `DELETE` | Item through class <-> API | Success removes cached ID and notifies lists |
| `_response_` | API -> entity | Domain action result; local merge or pull |
| `ERROR` | Adapter -> request source | Original request in data, response details in meta |
| `CONNECT` | Component -> Matrix | Legacy local type connection path |
| `SELECT` | Item -> list | Toggle selected address, optionally navigate |
| `NAVIGATE`, `BACK` | UI -> Router | Navigation state, not entity mutation |
| `STREAM` / method-named reply | Adapter -> stream component | Typed event dispatch or text fallback |
| `STREAM_CANCEL` | Stream component -> transport | Cancel intent; no guaranteed server abort |

## Writes and responses

The native save path sends an UPDATE to the entity reference. It can update local
state optimistically and send the current full value. A send return value is not
an acknowledgement. Observe successful responses and errors; do not advertise
automatic rollback on denial.

Partial HTTP updates preserve omitted fields; supplied collections replace their
field and writes remain last-write-wins. Canonical contract:
[CRUD update](../API_CRUD_ENDPOINTS.md#update-resource).

Deletion should go through the class-aware item flow if the collection cache must
be cleaned up. Sending a bare network DELETE is not equivalent to coordinating
cache removal and list notifications. Relationship membership and child deletion
are also different; see the [list-field warning](../../packages/n3tx-ui/docs/formidable.md#arrays-and-references).

Method responses with recognized `{action,_field,id}` toggle shapes can update
local collections. Same-entity payloads update the entity; child-model or ambiguous
results cause a pull. Do not invent response shapes solely to suppress reads.

## Streams

SSE frame names (`chunk`, `done`, `error`) belong to transport. A payload such as
`{name:'done', data:{...}}` belongs to the application's event vocabulary. These
are not interchangeable completion signals. `NTTStream.STREAM` handles envelope
variants and dispatches named data to uppercase handlers. Plain output requires
`show-output`; custom consumers can own their output DOM.

See [transport](TRANSPORT.md#streaming) for actual cancellation and SSE limits.
Schema-declared events describe expected payloads; the browser does not thereby
validate every chunk against a complete JSON Schema implementation.

## Debugging order

1. Check module registration and component `model`/`ref`.
2. Inspect schema request and class cache with `NTT.get(model)`.
3. Inspect collection/member request, token and response status.
4. Trace reply `target` and `meta.inbox`; request source must be routable.
5. Check cache IDs, component subscription and render/update hooks.

Sources: [TX](../../packages/n3tx-core/src/n3tx_core/static/core/TX.js),
[NTT](../../packages/n3tx-core/src/n3tx_core/static/core/NTT.js),
[NetworkAdapter](../../packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js).
