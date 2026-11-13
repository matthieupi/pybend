# TTX storage and model notes

## Current contract — 2026-11-11

The package exports `TTX` from `ttx.py`, `Note` and `NoteMixin` from `note.py`,
`Thread` from `thread.py`, `Message` from `message.py`, and `ThreadedMixin` from
`mixin.py`; existing package-level imports remain available.
Only TTX is registered with storage, in table `ttx`. Legacy
`n3tx_agents.Thread`/`TXRecord` are retired without aliases or runtime fallback.
The separate Thread and Message exports here are typed User-DM content, not agent
history containers. Agent-root owner/admin policy, SDK decoding and execution
capture are owned by the [agent history guide](../../n3tx-agents/docs/ttx-history.md),
and never grant admins generic access to User DMs. The contract below the
historical heading describes the discarded November 4 integration.
`ttx-pre.py` and `ttx-draft.py` are historical/concept source, not public APIs.

### Representation and persistence

The canonical row stores envelope fields, `kind`, `data`, and `meta` alongside
native identity and caller attribution. `kind=""` denotes base TTX. Subclasses
derive their kind from their class name; renaming a class changes its stored
and wire contract. Ordinary TX transport carries the kind in `meta["kind"]`;
canonical metadata excludes that reserved key. Conflicting values are rejected.

Subclasses declare content fields. `tx()` packs them for transport; `ttx()`
projects them to a canonical row without writing or cloning its identity.
`value` validates known content and returns a typed view; unknown kinds return
detached raw JSON. There is no automatic JSON-text parsing or reference I/O.
Transaction-owned relationship hydration is disabled for embedded content;
ordinary application-model hydration is not changed.

Raw data is allowed on typed objects. Packing merges detached raw data first,
then serialized declared content, so declared fields win. Decoding splits only
the selected kind's declared content into attributes; remaining keys stay raw.
An unknown raw key such as `source`, `id` or `status` cannot override envelope
fields. No flatten-all-unknown-keys construction or compatibility branch exists.

Top-level `$id` and `$schema` string extras are accepted so native FastAPI CRUD
response-model validation can retain public identity metadata. Every other
undeclared top-level key is rejected, including on assignment. The same two
reserved keys are accepted on input: native response validation uses the model
without a separate response-only context. They remain nonauthoritative and are
excluded from `_storage_dict()`, declared model fields and database columns.
`model_response()` canonicalizes the object before native identity synthesis
when response extras are present, so supplied metadata cannot override `$id` or
`$schema`. Plain `model_dump()` can retain those validated response strings.

Local canonical fields are `archived: bool = False` and
`status: Literal["READ", "UNREAD", "ASK"] = "READ"`. Conversion through `.ttx()`
and `.value` retains both; `from_tx` accepts them as explicit keyword arguments.
They are not added to the native seven-field TX envelope or `meta` implicitly.

Canonical payloads use field names and ordinary model construction, retaining
strictness and before-validators. **Field aliases are an unsupported gap**:
aliased content can fail reconstruction or be reinterpreted through Pydantic
alias precedence. There is no translation layer or alias-specific rejection.
Custom non-TTX nested constructors retain their own hydration/I/O behavior.
Standard Pydantic exclusions remain in effect: an excluded field is not packed
into content, even for persistence. A required excluded field may make a
typed roundtrip impossible; a defaulted excluded field can reconstruct its
default instead of the original value. This limitation is intentionally retained.

Typed create/get/list/update/delete/save project through canonical native storage.
Get returns None for missing/wrong kinds. Lists bind the exact kind before
pagination and counting. Updates reload current state, validate merged fields,
and replace supplied values rather than deep-merging. Save preserves ID and
rejects deleted-row resurrection or kind changes. Exact-kind read/write checks
are not atomic; callers must not infer concurrency or authorization guarantees.

`get(..., archived=False)` and `list(..., archived=False)` hide archived rows;
True includes both states. Archive predicates are ANDed with trusted filters
and kind restrictions in SQL before counting or pagination. Typed get supports
`as_dict=True`, returning the native canonical storage dictionary after kind
selection, not a typed dictionary or public response. Internal update/save/
delete reads include archived rows. Mutation return values include the written
row even after it becomes archived; native update's final default get cannot
be used as the sole mutation result. Typed population remains unsupported.

Raw dictionary reads decode `archived` with Pydantic boolean validation before
testing visibility. Native new-table creation currently declares booleans as
TEXT, so dictionary reads can contain `"0"`/`"1"`; Python string truthiness is
not an archive predicate. Returned dictionaries retain the decoded boolean.

### Native TX sending

TTX overrides the inherited fullmethod without changing its callable surface:

```python
async def send(target, tx: TX) -> None
```

Callers use `await record.send(tx)`; target is the bound receiver, not a second
destination argument. The outgoing TX already contains its destination.
For a saved instance, native storage reloads the canonical row including archives,
the envelope is deep-copied, and native class bubbling qualifies the source as
`ttx/<id>`. Data, metadata, UUID and time survive; the input remains unchanged.
An overridden actor address does not replace canonical identity. Unsaved or
deleted instances fail before routing. This remains trusted Python, not access
control, an atomic existence check or a delivery acknowledgement.

The supported instance route is concrete model class to native Matrix, with
canonical class address `ttx`, no class routing children and canonical TTX
registered on that same Matrix. Other parent/binding topologies fail before
sending. This avoids prefix stripping, alternate dispatchers or global Actor
changes. Native send/inbox interceptors still run; trusted source rewrites remain
possible. Noncopyable Python payloads may fail copying without a fallback.

Class-bound sends delegate unchanged to the inherited Actor implementation, so
native responses do not require an instance or storage lookup. The override adds
no HTTP action, request method, persisted outgoing record, agent history capture
or caller injection. Convert typed content with `.tx()` before sending it.

### Explicit local messaging actions

Message has `name="MESSAGE"`, `kind="Message"` and strict nonblank `desc`.
Thread has `name="THREAD"`, `kind="Thread"` and `latest: TTX | None = None`.
latest is a canonical embedded snapshot packed into Thread data, not a Ref or
implicit foreign key. Only TTX is registered; `/Message` and `/Thread` are not
new persistent resources.

```python
# TTX: inherited unchanged by Thread
@classmethod
def OPEN_THREAD(
    cls, peer: str, user: dict | None = None,
) -> dict[str, object]
def ATTACH(self, entry: TTX) -> TTX
async def MESSAGE(
    self, desc: str, user: dict | None = None,
) -> dict[str, object]
def MARK_READ(self, user: dict | None = None) -> dict[str, object]

# ThreadedMixin: compose explicitly on public User
def MESSAGE(
    self, desc: str, uuid: str = "", timestamp: float = 0,
    user: dict | None = None,
) -> dict[str, object]
def THREADS(self, user: dict | None = None) -> list[dict[str, object]]
```

These actions are implemented in source; runtime acceptance is separate.
ATTACH is internal, not exposed. Exposed suffixes are lowercase `/open_thread`,
`/message`, `/mark_read` and `/threads`, matching native browser transport.
Public methods advertise `dict[str, object]` or `list[dict[str, object]]` and
explicitly serialize canonical `model_response()` results. A typed return
annotation does not automatically run the response pipeline and can lose or
misrepresent canonical identity under native response-model handling.
Native type inference recognizes parameterized dictionaries as objects; bare
`dict` currently falls through to its string schema fallback. This is not a
postponed-annotation resolution issue, and no global schema repair is installed.

Owned-root MESSAGE sends; User.MESSAGE receives only and must not forward again.
The sender forwards `id`, `desc`, `uuid` and `timestamp` in wire data and user
through native transport context. Receiver attribution requires injected
`user_id`, never body identity. Native `Actor.send` stays unchanged. There is no
REPLY action, `_receive_message`, dispatch override or automatic capture.
Bootstrap is `TTX.OPEN_THREAD(peer, user)` followed by the root's MESSAGE action,
not generic public CREATE or a second receiver-as-sender API. It validates an
existing local `users/<id>` peer, rejects self and finds/creates the caller's
owner-local root. Archived matches reopen without clearing existing read state.
No global create authorization or another model's caller context is changed.
Application permissions/activation remain separate; Note access is not widened.

Roots are peer-to-owner local views: `source` is the peer, `target` is the owner,
and `user_owner` is the owner ID. For owner 1/peer 2, use source `users/2`, target
`users/1`, user_owner 1. The opposite full view uses source `users/1`, target
`users/2`, user_owner 2. Each view contains the full bidirectional conversation;
send uses the saved root's peer source. Message transport and directional graph
query filters retain their own source/target semantics.

Sender and read actions reload exact Thread roots, verify existing caller,
`user_owner` and owner target, and reject remote/self peers. Send constructs
Message(source=owner, target=peer), attaches an owner-local clone, then uses
native `Actor.root().send` targeting the registered `users` actor with recipient
`id` in data. This avoids instance/class bubbling prefixes on the logical
source. Caller metadata is deep-copied for transport and never persisted.
The canonical local-root return is not a delivery receipt or delivered flag.

Receiver MESSAGE validates the saved registered User host and injected author,
then performs an inline pair lookup including archives and attaches locally.
An empty UUID generates a fresh identity; nonempty UUID and finite nonnegative
time are retained. Invalid UUID/time are rejected before roots are created.
Direct native parsing still requires explicit UUID/time despite defaults.
Receiver identity comes from the host, never a replacement caller dictionary.

ATTACH is trusted Python: it accepts any saved TTX parent and any TTX entry,
including Thread containers. The detached copy has a fresh local row ID,
target `ttx/<parent-id>`, parent-owner attribution and no `meta.user`.
UUID/time survive; the copy's archived state resets false. The input and its
stored row remain unchanged; descendant rows are not cloned. Non-Thread parents
remain unchanged and their copies retain entry status. Thread parents reopen,
mark incoming entries UNREAD and preserve existing UNREAD/ASK on outgoing attach.
Only non-Thread entries replace latest with the canonical saved snapshot. Thread
entries appear in direct history but leave the existing preview unchanged,
consistent with nonrecursive mutation cache maintenance.
MARK_READ changes only the authorized root status; THREADS checks host/caller
ownership and selects exact visible Thread roots by target and owner in SQL.

Child update/archive/delete refreshes only directly targeted Thread caches from
visible non-Thread children, ordered by descending event timestamp. No visible
child yields latest=None; equal timestamps have no defined relative order.
Root-cache updates do not recursively propagate to another root. Deleting a
root does not cascade children. Pair create, append/cache and send/receive are
separate writes, not atomic or concurrency-safe operations. Partial history,
uncertain delivery and duplicate roots/retries remain possible.

`threads()` reads direct outgoing source matches; `history()` reads direct
incoming target matches. Both use canonical local `ttx/<id>` identity and return
unordered, unbounded canonical rows without recursion or implicit permissions.

### Notes and caller propagation

Explicit `NoteMixin` inheritance adds exposed NOTE(message, user) -> Note and
NOTES(user) -> list[Note]. Authorization belongs to the configured ingress.
Direct HTTP uses native action-policy resolution; raw ActorModel dispatch lacks
the same default-policy fallback. The mixin adds no authorization checks.
No extra host CRUD guard, saved-host check or fresh
host reload occurs in the mixin; direct Python calls are trusted. NOTE targets
`self.addr`; NOTES filters that address and Note kind in storage. No notes pointer
or Thread is allocated.

Named caller injection is native: direct HTTP uses authenticated request state;
ActorModel uses trusted `tx.meta.user` and ignores body identity. The mixin does
not install a handler or register a global flag. Notes create fresh envelopes
with caller-derived source, so incoming TX UUID/source/time are not retained.
NOTE uses `user` for attribution, with anonymous source when no caller ID exists.
NOTES retains `user` for native injection compatibility, not an extra access check.

### Schema registration

The package initializer side-effect imports `schema_ext.py`, like other optional
N3TX packages. Native `@schema_extension(after="metadata")` registers its `ttx`
stage. TTX.schema() describes canonical projection without kind-specific `data`
validation. Known and unknown canonical kinds retain native object schemas.
Typed schemas describe their kind constant, raw backing data and canonical
projection. Runtime `.value` validation and persistence remain unchanged.

The stage adds `ttx` metadata (`canonical_model`, `canonical_schema`,
`kind_field`, `transport_kind`, and `representation`). Matching existing named
native host definitions receive the same metadata and typed kind constants.
Native stages own fields, methods, schema IDs and definitions.
Top-level `additionalProperties` remains false with a `patternProperties`
exception for string `$id`/`$schema`. This describes the same runtime metadata
boundary without declaring new persisted fields or allowing arbitrary extras.
The stage adds no payload definitions, conditional payload constraints, recursive
reference repair or schema bundling. New kinds invalidate cached canonical
schemas and hosts containing a TTX definition.

This is schema registration, not storage/actor/HTTP route registration or browser
NTT implementation. Native complex/recursive schema and reference-closure gaps
remain unsupported by this extension. Core's earlier native defs stage can reject
plain BaseModel references in complex direct subtype schemas before this stage
executes; embedded named resources can lack closure for their local references.
Verification results must identify their source snapshot; this guide does not
certify deployment.

## Historical contract — November 4

The following describes the discarded implementation and is retained only as
historical evidence. Use the current contract above for this working package.

`n3tx-threads` stores interactions without a separate Thread container. A TTX
targets the canonical reference of its owning entity. Host capabilities supply
authorization and domain validation; TTX supplies serialization and native storage.

`Thread(TTX)` is an empty semantic subclass for conversation-oriented Python
code, such as `read_history(thread: Thread)`. It inherits the same fields, table,
storage binding and operations without registering another actor. Register TTX
only. `Thread.get(id)` constructs the subclass from the shared table; it does
not filter by entry name or add authorization. APPEND still returns TTX children.

Stored identities remain `/TTX/<id>`. Do not independently register Thread or
derive persistent references from its class name. Native `model_response()`
would synthesize `/Thread/<id>`; public identity serialization must use TTX.

```text
Host model
  |
  +-- NOTE(message, user) -> ThreadedMixin -> TTX.create(...)
  |
  +-- NOTES(user) --------> ThreadedMixin -> TTX.list(...)
```

## TTX contract

`TTX(tx, user_owner=...)` builds an unsaved snapshot. `TTX(**fields)` follows
ordinary native reconstruction without rewrapping stored content. Construction
does not authorize, save or dispatch the envelope. TTX declares deny-all access
for configured HTTP boundaries; trusted Python storage calls remain available.
Raw Matrix LIST does not derive a model policy filter, even with a caller in
metadata. Use an authorized boundary; do not expose raw TTX collection tools.

| Field | Meaning |
|---|---|
| `uuid` | Supplied TX identity; not an enforced deduplication key |
| `name` | Entry name, such as `NOTE` |
| `source` | Sender address, not proof of caller authority |
| `target` | Canonical owning-entity reference |
| `timestamp` | TX event time, not a server insertion timestamp |
| `user_owner` | Trusted appender's positive integer user ID, or `None` |
| `data` | Internal `{"payload": normalized_value}` JSON storage wrapper |
| `meta` | Primitive correlation, stream and error metadata only |

Raw JSON values and valid JSON text are normalized once. Ordinary non-JSON
strings remain text. Saved ActorModels become references; transient Actors
serialize their declared JSON fields. TTX does not look up payload classes by
name or reconstruct them on read.

`.value` returns detached JSON or an unhydrated top-level reference. It does
not parse strings again, recursively expand references, or perform target I/O.
Nested JSON remains ordinary data. Callers own explicit casting and hydration.

`user_owner` uses native-supported `Optional[int]` schema inference so new
SQLite tables declare an INTEGER column while retaining strict validation.
Existing TEXT columns require separate migration; this declaration does not
repair old data.

### Direct child operations

```python
APPEND(self, tx: TX, *, user_owner: int | None = None) -> TTX
threads(self, *, cursor: float | None = None, limit: int = 50) -> dict
```

These are low-level trusted Python helpers, like native `create` and `list`.
They do not expose HTTP routes, authorize the caller, resolve an owning business
entity, or traverse parent permissions. The calling action must establish access.
TTX does not inherit ThreadedMixin.

`APPEND` requires a saved parent and a TX, then creates a new TTX targeting the
parent's canonical `/TTX/<id>` reference. Other envelope fields survive before
normal TTX serialization. `user_owner` must be supplied explicitly when needed;
it is not copied from the parent or incoming caller metadata. The original TX is
not modified. Parent existence checking and insertion are separate operations.

`threads` requires an existing parent and returns its immediate children only:
`{"data": [...], "cursor": ..., "has_more": ...}`. Native selection filters by
the parent's canonical reference and, when supplied, `timestamp < cursor`.
Ordering is descending timestamp, never ID. A positive integer limit is required;
the cursor is a finite number or `None`. The returned cursor is `None` on the
last page, otherwise the last returned timestamp. Ties can be omitted across
page boundaries; this is not a complete replay or stable concurrent snapshot.

## Shared entry operations

`ThreadedMixin` is a plain reusable model capability with no persisted fields,
inbox interception, execution context or root-creation behavior.

```python
_append_entry(self, tx: TX, *, user: dict | None) -> TTX
_entries(self, *, name: str, user: dict | None) -> list[TTX]
```

Both helpers reload the host before evaluating native policy against its current
state. Append checks `update`; reads check `read`. Missing users are anonymous
(`{}`), not trusted-internal authorization bypasses. Attribution grants no access.

Append replaces transport addressing with the saved host's canonical reference,
retains UUID/source/timestamp, and delegates payload/metadata normalization to
TTX. It performs one native record insert and never changes the host row.

Reads select canonical target and entry name before fetching records, ordered by
ascending `timestamp` alone. There is no ID tie-breaker, pagination, stable
concurrent snapshot or automatic reference resolution. The result is unbounded.

Note content and query values use the native storage layer's bound SQL
parameters. They are never interpolated into SQL statements or identifiers.
Quotes and SQL-looking text remain user data; manual SQL escaping or keyword
filtering is neither required nor performed.

## Notes capability

Import `n3tx_threads` before defining models with `__notes__ = True`.
Registration injects `NotesMixin`, which inherits the shared entry helpers.
It adds no `notes` field or protected pointer and does not create a container.
TTX storage must be registered explicitly.

```python
NOTE(self, message: str, user: dict = None) -> TTX
NOTES(self, user: dict = None) -> list[TTX]
```

At model definition, native action permissions map `NOTE` to the parent's
`update` rule and `NOTES` to its `read` rule. Unrelated access and protected-field
declarations are preserved. Each operation also rechecks the current parent
through the shared helper. There is no Notes-specific or per-author policy.

`NOTE` validates nonblank text up to 16000 characters, then stores the raw
message as the TX payload. There is no `{"content": text}` domain wrapper:
`"123"` becomes a number, `"null"` becomes `None`, and native reference URLs
remain live pointers. The internal TTX storage wrapper is unchanged.

Direct HTTP uses `/NOTE` with `{"message": "..."}` and `/NOTES` with `{}`.
Native named `user` injection supplies caller identity. Direct/Python note
creation uses the server-derived `users/<user_id>` source address, or
`anonymous` when no caller ID exists. Parent policy still decides access.

Actor calls carry `NOTE` with `{id, message}` or `NOTES` with `{id}` when
addressing the model class. A registered instance can omit `id`; a conflicting
ID is rejected. Body `user`, `tx`, target and other undeclared arguments are
rejected on the actor path. The original NOTE source/UUID/timestamp survive;
only `meta.user` supplies attribution. Responses are sent once with native
correlation. Other actions delegate without recording notes.

The API returns full serialized TTX records, with content in `data.payload`,
`timestamp` and `user_owner`. Python callers receive TTX instances and can use
`.value`. There is no `kind`, `recorded_at`, `recorded_by`, `thread_id`, custom
note projection or `read_notes` compatibility endpoint.

## Explicit limits and migration boundary

- Parent access does not authorize hydration of a referenced entity.
- There is no automatic UPDATE history, replay, graph traversal or inherited
  graph permission engine.
- One insert is not SQL-level immutability, UUID deduplication, or a transaction
  shared with other business mutations. Response failure can leave a saved note;
  automatic retry is not safe.
- The old Thread container, `TXRecord`, `current_execution`, `invoke_threaded`,
  and execution-capture implementation are retired. Native bootstrap and agents
  now use canonical TTX; legacy application consumers still require integration.
  Old APIs are not restored by the semantic shim.
- This source cut does not migrate old notes pointers, containers, database
  columns, or snapshot targets. Do not start old applications against existing
  data assuming native registration makes the schema compatible.
- Focused test results must be reported separately; historical acceptance
  does not establish readiness of the new contract or deployed applications.

Historical implementation paths: `src/n3tx_threads/ttx.py`, `thread.py`,
`mixin.py` and the removed `notes_mixin.py`. Present files at reused paths no
longer establish this historical API; an archived copy has not been verified.
Use the module map at the top for the current implementation, not a restored
legacy file.

## Changelog

- 2026-11-12: Align the current introduction with TTX-only agent history and
  separate User-DM kinds; mark obsolete historical implementation links explicitly.

- 2026-11-11: Document same-signature native send with detached canonical
  instance sources, unchanged class replies and explicit topology limits.

- 2026-11-11: Accept any TTX parent/entry in ATTACH, retaining detached-copy
  semantics, unchanged non-Thread parents and non-Thread latest previews.

- 2026-11-10: Allow only string public identity extras for native CRUD response
  validation, exclude metadata from storage and rederive canonical identities;
  describe the same narrow top-level schema exceptions.

- 2026-11-10: Implement local OPEN_THREAD bootstrap and explicit sender/receiver,
  attach/cache, read and owner-list behavior without generic CREATE changes;
  document direct child cache maintenance and non-atomic delivery limitations.

- 2026-11-10: Declare contract-only messaging actions and embedded latest;
  merge raw extras with authoritative declared content, add archive/read state,
  and filter archive reads before counts while preserving mutation results.
  Note adaptation is deferred; its API/schema compatibility is not a gate.
  Parameterize public dictionary returns for native object discovery, decode
  raw archive booleans, and clarify peer-source/owner-target root direction.

- 2026-11-10: Relocate Note/NoteMixin and Thread to their own modules without
  changing behavior or package-level imports.
- 2026-11-09: Limit the current schema stage to descriptive metadata and typed
  kind/data invariants; retain native ownership of definitions and document
  canonical payload-validation and complex/recursive reference-closure limits.

- 2026-11-09: Remove the current NoteMixin host helper; rely on native action
  authorization and trusted Python calls, target `self.addr`, and omit extra
  CRUD checks, saved-host checks and fresh host reloads.

- 2026-11-09: Document canonical typed projection and explicit Notes alongside
  legacy storage; explain exclusions and native schema-stage registration.

- 2026-11-04: Replace the container/codec/manifest documentation with TTX-backed
  host streams, raw Notes wrappers and parent read/update permission mapping.
  Add direct TTX child append and timestamp-page contracts.
  Rename the shared capability implementation to mixin.py.
  Add the empty semantic Thread subclass; keep TTX as the registered identity.
  Record native bootstrap/agents integration and the raw LIST trust boundary.
- 2026-11-02: Move generic thread documentation to the standalone package and
  document codec-neutral payload reads; agent runtime details remain agent-owned.
