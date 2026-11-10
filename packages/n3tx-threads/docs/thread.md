# TTX storage and model notes

## Current contract — 2026-11-09

The package exports `TTX` from `ttx.py`, `Note` and `NoteMixin` from `note.py`,
and `Thread` from `thread.py`; package-level imports remain unchanged.
Only TTX is registered with storage, in table `ttx`. Legacy
`n3tx_agents.Thread`/`TXRecord` remain independent and unchanged. The contract
below the historical heading describes the discarded November 4 integration.

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
Typed schemas describe their kind constant, empty backing data and canonical
projection. Runtime `.value` validation and persistence remain unchanged.

The stage adds `ttx` metadata (`canonical_model`, `canonical_schema`,
`kind_field`, `transport_kind`, and `representation`). Matching existing named
native host definitions receive the same metadata and typed kind/data
invariants. Native stages own fields, methods, schema IDs and definitions.
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

Implementation: [TTX](../src/n3tx_threads/ttx.py),
[semantic Thread](../src/n3tx_threads/thread.py),
[entry helpers](../src/n3tx_threads/mixin.py),
[NotesMixin](../src/n3tx_threads/notes_mixin.py).

## Changelog

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
