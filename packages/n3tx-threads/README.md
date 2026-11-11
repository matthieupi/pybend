# n3tx-threads

## Current working contract — 2026-11-10

This package is being developed alongside the existing `n3tx_agents.Thread`
and `TXRecord`. It does not replace their bootstrap, consumers, or stored data.
The November 4 integration description retained below is historical.
The current scaffold declares Pydantic 2.11 or newer (below 3).

```python
from n3tx_threads import TTX, Note, Thread, NoteMixin

# After explicitly registering only TTX against chosen native storage:
saved = Note.create(Note(
    source="users/1", target="emails/42", desc="Hello",
))
loaded = Note.get(saved.id)
loaded.desc = "Updated"
loaded = loaded.save()
```

Only `TTX` owns the `ttx` table. Note and Thread are typed projections of the
same canonical resource; never register their storage separately. Concrete
class names identify kinds. An empty stored `kind` means base TTX.

| API | Responsibility |
|---|---|
| `tx()` | Transport projection; discriminator goes in `meta.kind` |
| `ttx()` | Canonical projection; discriminator is the stored `kind` field |
| `value` | Decode known content; preserve unknown kinds as detached JSON |
| `create/get/list/update/delete/save` | Canonical or exact-kind typed storage |
| `threads()` | Direct outgoing rows: `source == "ttx/<id>"` |
| `history()` | Direct incoming rows: `target == "ttx/<id>"` |

Typed content merges raw `data` with declared fields; declared fields win on
collisions. `.value` extracts only declared content keys into attributes and
keeps all other keys in raw `data`, including envelope-looking keys. Raw extras
cannot override envelope identity, routing or local state. Nonempty typed data
is supported. `archived: bool = False` and
`status: Literal["READ", "UNREAD", "ASK"] = "READ"` are local canonical fields:
`.ttx()` and `.value` preserve them; native TX transport remains unchanged.

Native CRUD response validation accepts only string `$id`/`$schema` top-level
extras alongside declared fields. All other undeclared top-level keys remain
invalid on construction/validation and assignment. These two reserved keys are
also accepted on input because native response validation uses the same model;
they are nonauthoritative, never storage fields, and never database columns.
`model_response()` rederives canonical identity rather than trusting supplied
metadata. Raw content extras still belong inside `data`. Schema describes the
two reserved string exceptions while rejecting other top-level extras.

`get(..., archived=False)` and `list(..., archived=False)` hide archived rows.
`archived=True` includes all rows, not only archived ones. Lists apply archive
and exact-kind restrictions in SQL before counts/pages. Internal update/save/
delete reads include archived rows, and updates return the written row even
when archived. Typed `get(as_dict=True)` returns the canonical native storage
dictionary after exact-kind selection. These are trusted Python read controls,
not a new HTTP query parameter or authorization policy.

Strings remain text. Reconstruction uses canonical field names and ordinary
model validation. **Field aliases are an unsupported gap**: aliased content can
fail reconstruction or follow Pydantic alias precedence instead of preserving
the snapshot. No alias translation or alias-specific rejection is installed.
Transaction content does not use transaction-level relationship hydration.
Custom non-TTX nested constructors retain their own hydration/I/O behavior.
Excluded fields are intentionally omitted during packing: required excluded
fields can prevent reconstruction, and defaulted ones can reconstruct defaults.

### Explicit local messaging

The package now exports `Message` and `ThreadedMixin`. Message defaults to
`name="MESSAGE"` and validates strict nonblank `desc`. Thread adds
`latest: TTX | None = None`, a cached embedded canonical snapshot, not a Ref,
foreign key, separate resource or implicit lookup.

Messaging actions are implemented in source. Only TTX owns storage; compose
ThreadedMixin on the registered local User model and register its native actor.
Runtime/transport verification and application activation are separate work:

| Owner | Callable | HTTP suffix | Result contract |
|---|---|---|---|
| TTX class | `OPEN_THREAD(peer, user=None)` | `/open_thread` | dict |
| TTX, inherited by Thread | `ATTACH(entry: TTX)` | None; internal only | TTX |
| TTX, inherited by Thread | `async MESSAGE(desc, user=None)` | `/message` | dict |
| TTX, inherited by Thread | `MARK_READ(user=None)` | `/mark_read` | dict |
| ThreadedMixin on User | `MESSAGE(desc, uuid='', timestamp=0, user=None)` | `/message` | dict |
| ThreadedMixin on User | `THREADS(user=None)` | `/threads` | list[dict] |

Public actions explicitly return canonical `model_response()` dictionaries,
not typed response models. Return annotations use `dict[str, object]` and
`list[dict[str, object]]`: native schema inference recognizes parameterized
dictionaries as objects but currently describes bare `dict` as a string.
Raw `get(as_dict=True)` normalizes the archive boolean before visibility checks;
native new-table boolean columns use TEXT, so raw `"0"` must not hide a row.
The User action is receiver-only; owned-root MESSAGE
is the sender. Native `Actor.send` is unchanged; there is no REPLY action,
receive helper, inbox interception or loop-back sending. Application policy and
activation remain separately owned; this package does not widen Note access or
certify enabled chat.

Conversation root direction is peer-to-owner: `source` identifies the peer,
`target` identifies the owner, and `user_owner` is the owner ID. For owner 1 and
peer 2: `source="users/2"`, `target="users/1"`, `user_owner=1`. The other full
view has `source="users/1"`, `target="users/2"`, `user_owner=2`. Sending uses the
saved root's peer **source**, not its owner target. This root convention does
not reverse Message transport or the existing directional graph-query filters.

Bootstrap uses `POST /TTX/open_thread {"peer":"users/2"}` with trusted caller 1,
then `POST /TTX/<returned-id>/message {"desc":"Hello"}`. OPEN_THREAD validates
local `users/<id>` peers, rejects self, and finds or creates the caller-owned
view, including archived matches which it reopens without clearing read state.
It does not grant generic TTX CREATE or alter another model's auth context.

Sender actions reload a saved Thread and check both `user_owner` and owner
target against an existing injected caller. They build Message(source=owner,
target=peer), save an owner-local clone, then call native Matrix.send with
target `users`, explicit recipient `id`, `desc`, `uuid`, `timestamp`, and detached
caller metadata. Transport caller metadata is never packed into local history.
The result is the canonical sender root, not a delivered flag or receipt proof.

Receiver MESSAGE validates the saved local User host and existing caller,
finds/creates the opposite owner-local view and attaches without sending onward.
Empty UUID generates a fresh Message identity; nonempty UUID and finite
nonnegative event time are preserved. Native direct callers must still supply
both arguments because the direct parser does not honor signature defaults.

Internal ATTACH clones, resets row ID, sets target to `ttx/<root-id>`, copies
root ownership and drops `meta.user`. It rejects nested Thread containers,
updates latest with the canonical saved snapshot, and reopens archived roots.
Inbound author addresses mark UNREAD; outbound append does not clear existing
UNREAD or ASK. MARK_READ changes only the authorized root to READ. THREADS
requires caller/host identity and filters Thread kind, target and owner in SQL.

Child update/archive/delete refreshes only its directly targeted root's latest
from visible non-Thread children by descending timestamp; ties have no defined
order. It does not recursively propagate cache changes or remove child history
when deleting a root. Pair creation, append/cache writes and send/receive writes
are not atomic. Duplicate concurrent roots, partial history, uncertain delivery
and duplicate retries remain possible; no deduplication or durability is claimed.

### Explicit Notes capability

Compose `NoteMixin` before the host ActorModel base. It adds no fields, pointer,
container, global `__notes__` registration, or custom actor handler:

```python
from n3tx_actors.models.actor_model import ActorModel

class Email(NoteMixin, ActorModel):
    __tablename__ = "emails"
    __storable__ = True
    subject: str

# Saved host, registered host/TTX storage, and trusted caller context:
note = email.NOTE("Hello", user=caller)
notes = email.NOTES(user=caller)  # list[Note]
```

Authorization belongs to the configured ingress. Direct HTTP uses native action
policy resolution; raw ActorModel dispatch lacks the same default-policy fallback.
The mixin adds no authorization checks, host CRUD guard or fresh reload. Direct Python
calls are trusted and do not require a saved host. Both actions use `self.addr`
as the note target. Caller injection comes from native HTTP or ActorModel's
named-user bridge, not the body. NOTE uses it for attribution; NOTES retains its
`user` parameter for injection compatibility. Envelopes are fresh: original
incoming TX source/UUID/time are not captured. Reads are unordered and unbounded.

### Native schema extension

Package import loads `schema_ext.py`, registering the `ttx` stage after native
`metadata` in the default schema pipeline. It creates no tables or actor targets.
It adds descriptive metadata to TTX schemas and matching existing named host
`$defs`. Native stages own fields, methods, schema IDs and definitions.

Schema `ttx` metadata describes canonical TTX identity, typed versus canonical
representation, stored `kind`, and transport `meta.kind`. Canonical `data` has
no kind-specific schema validation; runtime `.value` validation and persistence
remain separate and unchanged. Typed schemas describe their class-name kind
and unrestricted raw backing data. No payload definitions or payload constraints,
reference rewriting or schema bundling are added. Native complex/recursive
schema and reference-closure gaps remain unsupported by this extension.
Named schema IDs are not new storage resources or implemented HTTP aliases.
Browser NTT projection/dispatch is not installed by this metadata.

Native CRUD and directional queries are trusted Python, not policy boundaries.
Kind checks and writes are not atomic. No migration, deployment, automatic
execution capture, recursive permission engine, or application acceptance follows
from this package. See [the current contract](docs/thread.md).

## Historical TTX integration — November 4

The remaining sections describe the discarded implementation, not the current
working contract above. They are retained for provenance.

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

- 2026-11-10: Retain reserved string response identities through native CRUD
  response validation while rejecting other top-level extras; keep metadata
  nonpersisted and rederive canonical identity for public responses.

- 2026-11-10: Implement explicit OPEN_THREAD bootstrap, owned send/read actions,
  receiver-only local receipt and owner-scoped roots; clone/cache entries and
  refresh direct latest snapshots after child mutations without recursive flow.

- 2026-11-10: Add Message/ThreadedMixin contract-only actions, Thread latest,
  archive/read state and raw-plus-declared content conversion. Archive reads
  filter before counts; mutations retain archived rows. Preserve Note source;
  adaptation to the new architecture is deferred, not a compatibility gate.
  Parameterize dictionary returns for native object schemas, decode raw archive
  booleans for dictionary reads, and clarify peer-source/owner-target roots.

- 2026-11-09: Limit the current schema stage to descriptive metadata and typed
  kind/data invariants; document the absence of canonical kind-specific payload
  validation and native complex/recursive schema and reference-closure gaps.

- 2026-11-09: Remove the current NoteMixin host helper; use native action
  authorization and trusted direct Python calls without extra CRUD checks or
  fresh host reloads. Both actions target `self.addr`.

- 2026-11-09: Document the coexisting typed scaffold, explicit NoteMixin,
  documented exclusions and native schema-stage registration; mark the prior
  integration contract as historical.

- 2026-11-04: Document TTX-only streams and thin parent-authorized Notes actions;
  retire container and automatic manifest-capture contracts. Document direct
  TTX child append and timestamp-only paging without graph authorization.
  Export a semantic Thread subclass without restoring the old container API.
  Record native bootstrap/agents integration and the raw LIST trust boundary.
