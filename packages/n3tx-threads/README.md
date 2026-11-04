# n3tx-threads

Low-level TTX storage and optional model-owned notes. Requires Python 3.10+,
`n3tx-core` and `n3tx-actors`; no agent package or LLM SDK is required.

There is no separate Thread container. `Thread(TTX)` is a semantic Python name
for conversation roots, with no additional fields or behavior. Each interaction
targets its owning entity; a stream is a scoped query over TTX records.

## Usage

Import the package before declaring `__notes__` models. Register the host and
TTX with native storage explicitly; importing does not create tables.

```python
from typing import ClassVar

import n3tx_threads
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, OWNER
from n3tx_threads import TTX


class Notebook(ActorModel):
    """Own a stream of notes through native model permissions."""

    __tablename__ = "notebooks"
    __storable__ = True
    __notes__ = True
    __access__: ClassVar[dict] = {
        "read": AUTHENTICATED,
        "update": OWNER,
    }
    user_owner: int
    title: str


# After explicit registration with disposable/native storage:
# register_model(Notebook, storage=storage)
# register_model(TTX, storage=storage)
notebook = Notebook.create(Notebook(user_owner=1, title="Ideas"))
caller = {"user_id": 1, "role": "user"}  # Trusted server context only.
note = notebook.NOTE("Hello", user=caller)
assert note.value == "Hello"
notes = notebook.NOTES(user=caller)  # list[TTX], oldest timestamp first.
```

| Export | Responsibility |
|---|---|
| `TTX` | TX snapshot, `.value`, child `APPEND` and timestamp-page `threads` |
| `Thread` | Semantic TTX subclass for conversation roots; register TTX only |
| `ThreadedMixin` | Parent-authorized entry append and timestamp-ordered reads |
| `NotesMixin` | `__notes__` capability exposing `NOTE(message)` and `NOTES()` |

`Thread` inherits TTX storage once TTX is registered. `Thread.get(id)` loads a
Thread-shaped Python instance from the same table; it does not select only
conversation entries. Consumers must check the entry name and authorize access.
It does not auto-register as an actor. Do not register it as a second model or
publish `/Thread/<id>` identities; stored links and inherited child operations
use `/TTX/<id>`. Native `model_response()` uses the Python class name, so use the
canonical TTX representation at public identity boundaries.

## Child interactions

A saved TTX can own child records without inheriting a mixin:

```python
from n3tx_actors.tx import TX

# Trusted Python: the calling action must authorize access first.
reply = note.APPEND(
    TX("Message", "assistant", str(note.target), data="Following up"),
    user_owner=caller["user_id"],
)
page = note.threads(limit=20)
```

`APPEND` replaces the supplied target with the parent's canonical TTX reference,
preserving name, source, UUID and timestamp. Appender attribution is explicit;
neither parent ownership nor `tx.meta.user` supplies it. These are trusted Python
helpers, not exposed HTTP actions or recursive permission checks.

`threads(cursor=None, limit=50)` returns `{data, cursor, has_more}` for immediate
children in descending timestamp order. The next cursor is exclusive; equal
timestamps may be omitted at page boundaries. No ID tie-breaker, recursion,
automatic hydration, deduplication or concurrent snapshot guarantee is added.
The existing parent is checked, but that check and the write are not atomic.

## Notes API

```text
Direct generated HTTP:
  POST /Notebook/<id>/NOTE   {"message": "Hello"}
  POST /Notebook/<id>/NOTES  {}

Native actor requests to the registered model:
  NOTE   {"id": <id>, "message": "Hello"}
  NOTES  {"id": <id>}
```

An instance actor omits `id`. Actor callers belong in trusted `tx.meta.user`,
not the body. Direct HTTP uses native named `user` injection; there is no `tx`
parameter. Both return full TTX records, not custom note projections or pages.

- `NOTE` requires parent `update`; `NOTES` requires parent `read`.
- Notes add no field to the parent and do not update it during append.
- Raw message text is limited to 16000 characters and must not be blank.
- TTX parses JSON text once: `"123"` becomes `123`, `"null"` becomes `None`.
  Reference-looking strings become unhydrated references on `.value` access.
- Reads filter by canonical host target and `name="NOTE"`, then order only by
  `timestamp`. The list is unbounded; ties have no defined relative order.
- Native storage binds note content and filter values as SQL parameters; note
  text cannot supply SQL syntax or query identifiers.

## Integration status and limits

The old Thread container, `TXRecord`, `read_notes`, notes pointer, and manifest
capture APIs are removed. `ThreadedMixin` no longer intercepts inboxes or
exports `current_execution` / `invoke_threaded`. Native bootstrap now registers
canonical TTX for selected capabilities; the agents package uses semantic
Thread roots and parent-authorized TTX history. Collagen application consumers
and their legacy data still require separate migration. The example above
shows explicit registration rather than the bootstrap convenience.

The physical TTX table remains `tx_records`; existing database schemas/data
are not automatically compatible. No migration or deployment is implied.
TTX declares deny-all access, enforced by configured HTTP boundaries. Raw
Matrix LIST relies on an upstream policy filter; caller metadata alone is not
a list authorization boundary. Do not expose raw TTX collection tools.
Trusted native storage operations do not enforce authorization; host actions
must do so. References do not grant access, and this package does not implement
graph traversal or graph ACLs.

See [TTX storage and model notes](docs/thread.md) for the current contract.

## Changelog

- 2026-11-04: Document TTX-only streams and thin parent-authorized Notes actions;
  retire container and automatic manifest-capture contracts. Document direct
  TTX child append and timestamp-only paging without graph authorization.
  Export a semantic Thread subclass without restoring the old container API.
  Record native bootstrap/agents integration and the raw LIST trust boundary.
