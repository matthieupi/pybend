# N3TX Ref System Overhaul Plan

✅ **Finalized direction**

N3TX should collapse its reference system into one web-native mental model:

> **`$id` is the canonical absolute HTTP(S) identity URL. Local storage may use compact DB ids, but every public reference should be directly resolvable without `n3tx://` translation, service-name registries, or parallel address concepts.**

This plan supersedes the earlier distributed-ref direction. The new refactor is deliberately removal-first:

1. **Remove `ListRef[T]` entirely before the rest of the overhaul. No compatibility path.**
2. **Remove `n3tx://service/...` entirely. Use absolute `http://` or `https://` URLs.**
3. **Keep `$id` as the JSON-Schema-compatible canonical full identity URL. Do not add `$addr`.**
4. **Standardize field semantics around `T`, `list[T]`, `Ref[T]`, and `list[Ref[T]]`.**

### Execution model

Every implementation slice must use the same small, reversible loop:

```text
┌────────────────────────────────────────────────────────────────────┐
│  1. Write/update tests                                               │
│     Characterize current behavior, migration inputs, and target      │
│     contract before deleting anything.                               │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                v
┌────────────────────────────────────────────────────────────────────┐
│  2. Remove the previous abstraction                                  │
│     Delete the obsolete path in the smallest coherent slice.          │
│     Do not preserve parallel old/new implementations by default.      │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                v
┌────────────────────────────────────────────────────────────────────┐
│  3. Implement the simplified path                                    │
│     Replace deleted behavior with the new canonical model.            │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                v
┌────────────────────────────────────────────────────────────────────┐
│  4. Run the relevant test gates                                      │
│     Install missing test tools into `.venv-agents` or the project     │
│     test environment as needed; never rely on undeclared system deps. │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                v
┌────────────────────────────────────────────────────────────────────┐
│  5. Propose improvements                                             │
│     If the slice exposes a simpler design, propose it and loop back   │
│     before adding compatibility glue or new abstractions.             │
└────────────────────────────────────────────────────────────────────┘
```

Compatibility in this plan means **tested migration safety and explicitly supported input normalization**, not preserving old public abstractions indefinitely. The final state must have no `ListRef`, no `_ListRefMarker`, no public `n3tx://`, and no `$addr`.

---

## 🧭 North Star

```text
Python field type          Storage shape                       Runtime / response shape
-----------------          ---------------------------------   -------------------------------
T                          local FK id                         shallow hydrated T object
list[T: ProtoModel]        JSON ordered local FK ids            shallow hydrated list[T]
ManyToMany[T]              generated shared relationship table  relationship objects/refs per existing contract
Ref[T]                     absolute HTTP(S) $id string         URL string; explicit hydrate only
list[Ref[T]]               JSON list of absolute $id URLs       URL string list; explicit hydrate only
list[primitive] / dict      JSON TEXT                           JSON value
```

### Canonical identity

```json
{
  "$id": "https://storage.example.com/File/file-1"
}
```

Rules:

- `$id` is always absolute, including local responses.
- `$id` is the only public address field.
- `$addr` is not introduced.
- `n3tx://service/Class/id` is removed.
- A `Ref[T]` stores and emits the target entity's absolute `$id` URL.
- Entity identity uses class-name routes: `{API_URL}/{ClassName}/{id}`.
- Schema identity uses class-name routes: `{API_URL}/{ClassName}`.
- Table-name routes may remain transport/collection compatibility paths, but they are not canonical identity.

### Hard invariants

- No relationship with independent identity, auth, lifecycle, pagination, or generated routes may silently become an opaque JSON blob.
- `list[T: ProtoModel]` is allowed to use JSON local ids as its storage optimization only if N3TX still owns validation, hydration, auth filtering, schema, and route behavior for that relationship.
- `ManyToMany[T]` remains a distinct relationship primitive and must not be collapsed into `list[T]`.
- Default local hydration is shallow: hydrate direct `T` / `list[T]` fields one level, include `$schema` and `$id`, and do not recursively hydrate child relationship fields unless an explicit populate/depth contract requests it.
- Remote/dereference I/O must stay explicit and adapter-owned. Storage, validation, and dump paths must not perform implicit remote HTTP requests.

### Contract decisions before implementation

These are locked for this overhaul unless a later slice explicitly proposes and tests a change:

| Contract | Decision |
|---|---|
| Public entity identity | `{API_URL}/{ClassName}/{id}` |
| Public schema identity | `{API_URL}/{ClassName}` |
| Base URL source | `config.API_URL` is canonical; request host/proxy-derived URLs are out of scope for this refactor |
| Local id type | Preserve existing DB ids; global UUID/string-id migration is out of scope |
| Hydration depth | Shallow by default; deeper graph expansion requires explicit populate/depth semantics |
| Hydrated metadata | Every hydrated model object emits `$schema` + `$id` |
| Ref metadata | Unhydrated `Ref[T]` and `list[Ref[T]]` emit URL string(s), not object wrappers |
| Local relationship auth | Embedded hydrated children must pass the same read/access filtering as direct child reads |
| Missing/denied related rows | Must be deterministic per field: omit, null, or structured error; tests must lock the chosen behavior before rollout |

---

## ✅ Finalized Design Decisions

| Topic | Decision | Rationale |
|---|---|---|
| Public identity | `$id = absolute HTTP(S) URL` | JSON-Schema-compatible and frontend-compatible |
| `$addr` | Do not introduce | Avoid duplicate identity concepts |
| `n3tx://...` | Remove completely | HTTP(S) refs are usable from servers, browsers, CLIs, and external systems |
| `ListRef[T]` | Remove completely before starting | Slays duplicated relationship abstractions |
| `T` field | Local FK, auto-hydrated | Type annotation means local object relationship |
| `list[T: ProtoModel]` field | Ordered local relationship stored as JSON local FK ids, auto-hydrated shallowly | One model-list annotation; batch load with `T.list(ids=...)` while preserving N3TX relationship semantics |
| `ManyToMany[T]` | Preserve as separate shared relationship primitive | Do not flatten shared relationships into JSON arrays |
| `Ref[T]` field | Absolute URL string, no auto hydration | Explicit distributed pointer |
| `list[Ref[T]]` field | JSON absolute URL list, no auto hydration | Explicit distributed pointer collection |
| `Ref[T]` runtime shape | Validated string wrapper/value object | Publicly behaves and serializes as URL string while allowing helper methods |
| `Ref[T]` hydration | `ref.hydrate()` / helper only; returns `T` and does not mutate the ref | Avoid surprising remote fetches and hidden latency |
| Hydrated model metadata | Include both `$schema` and `$id` | Embedded objects stay self-describing and frontend-compatible |

---

## 🧹 Phase Zero: Full `ListRef[T]` Removal

`ListRef[T]` must be removed before the new reference semantics are considered complete. There should be no compatibility shim and no transitional public behavior in the final state. The removal slice must still be migration-safe: tests must characterize old data/input shapes before deletion, and the simplified path must preserve intended N3TX relationship behavior through `list[T: ProtoModel]`, `ManyToMany[T]`, or explicit route/view metadata.

### Replacement mapping

| Existing `ListRef[T]` usage | Replacement |
|---|---|
| Local owned child collection | `list[T: ProtoModel]` with N3TX-owned relationship semantics and shallow hydration |
| Pointer/reference collection | `list[Ref[T]]` |
| Nested route identity | Generated from model relationship metadata, not from a `ListRef` marker |
| FK hydration href arrays | Removed; `list[T]` hydrates objects by default |
| Generated join model from field type | Removed only after equivalent relationship behavior is represented by model annotation / explicit metadata |

### Files and concepts to remove/update

| Area | Required change |
|---|---|
| `models/ref.py` | Remove `ListRef` and `_ListRefMarker` |
| `utils/introspection.py` | Make list detection mean plain `list[T]`; keep `list[Ref[T]]` distinct |
| `models/proto_model.py` | Remove `generate_join_model()` dependency on `ListRef`; revisit `__fk_models__`, `__owner__`, `__parent__`, `__tagname__` |
| `storage/sqlite_storage.py` | Remove ListRef href-array hydration path |
| `storage/sqlite_migration.py` | Persist `list[T]` as JSON ids, not relationship/join table |
| `routes_fastapi.py` / `network_api.py` | Remove ListRef-driven nested route assumptions; keep generated routes only where replacement relationship metadata requires them |
| frontend components | Stop relying on ListRef href arrays as relationship UI substrate |
| examples/docs/tests | Replace every `ListRef[T]` with `list[T]` or `list[Ref[T]]` |

### Known usage surfaces

Initial search found `ListRef` and ListRef-derived concepts in:

- `packages/n3tx-core/src/n3tx_core/models/ref.py`
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-core/src/n3tx_core/widgets/schema_ext.py`
- `packages/n3tx-core/src/n3tx_core/utils/populate.py`
- `packages/n3tx-core/src/n3tx_core/utils/scaffold.py`
- core unit tests, examples, docs, and frontend components that consume href arrays

### Required relationship migration design

`ListRef` removal is not just a Python type rename. Existing relationships may be represented by child/join-table rows rather than a JSON column on the parent. The removal slice must include a data migration plan before implementation.

Migration requirements:

1. Inventory every current `ListRef[T]` field in framework tests, examples, and package docs.
2. For each field, classify intent:
   - owned local relationship -> `list[T: ProtoModel]`
   - shared relationship -> existing `ManyToMany[T]` or explicit relationship primitive
   - remote/pointer collection -> `list[Ref[T]]`
3. For owned local relationships currently stored through child/join FKs:
   - add the new parent JSON field if needed
   - backfill ordered child ids into parent rows
   - use deterministic ordering, defaulting to `ORDER BY id` unless the model declares an order field
   - decide whether old FK columns/tables are kept for rollback or dropped in a later manual migration
4. Add migration tests from an old-shape SQLite fixture before deleting the old read path.
5. Verify generated schema/routes/frontend behavior still reflects the model relationship after `ListRef` is gone.

No automatic production data migration is assumed unless this phase implements and tests it. If existing DB migration is intentionally out of scope, the release notes and docs must say so explicitly.

---

## 🔁 Standard Field Semantics

### `field: T`

Meaning: local object relationship.

```python
class Comment(ProtoModel):
    author: User
```

Storage:

```json
{
  "author": "user-1"
}
```

Runtime/response:

```json
{
  "author": {
    "$schema": "https://api.example.com/User",
    "$id": "https://api.example.com/User/user-1",
    "name": "Alice"
  }
}
```

Directive:

- Save as local FK id.
- Accepted write inputs: existing local `T` instance, dict/object with `id` or `$id`, raw local id, or current-service canonical `$id` URL.
- Reject remote/external HTTP(S) URLs for `T`; use `Ref[T]` for remote pointers.
- Hydrate by default when loading or constructing the parent from storage.
- Runtime parent instances should hold an actual `T` instance for this field, not a URL string or metadata stub.
- Response emits the full hydrated child object with `$schema`, `$id`, and its normal response-visible fields.
- Hydration must be local only, shallow by default, and must apply child read/access rules.
- A denied or missing child must follow a tested deterministic policy: omit, null, or structured error.

### `field: list[T]`

Meaning: local ordered collection of object relationships.

```python
class Playlist(ProtoModel):
    tracks: list[Track]
```

Storage:

```json
{
  "tracks": ["track-1", "track-2"]
}
```

Hydration:

```python
items = Track.list(ids=["track-1", "track-2"])
```

Response:

```json
{
  "tracks": [
    {
      "$schema": "https://api.example.com/Track",
      "$id": "https://api.example.com/Track/track-1",
      "track_prop1": "...",
      "track_prop2": "..."
    },
    {
      "$schema": "https://api.example.com/Track",
      "$id": "https://api.example.com/Track/track-2",
      "track_prop1": "...",
      "track_prop2": "..."
    }
  ]
}
```

Directive:

- Store as JSON list of local FK ids.
- Accepted write inputs: local `T` instances, dicts/objects with `id` or `$id`, raw local ids, or current-service canonical `$id` URLs.
- Reject remote/external HTTP(S) URLs for `list[T]`; use `list[Ref[T]]` for remote pointer collections.
- Update semantics are replace-by-default for the whole ordered list unless a future explicit patch operation is introduced.
- Hydrate by default when loading or constructing the parent from storage.
- Runtime parent instances should hold actual `T` instances in the list, not URL strings or metadata stubs.
- Use existing `StorableMixin.list(ids=...)` / `SQLiteStorage.list(ids=...)` batch path.
- Preserve stored order after batch fetch because SQL `WHERE id IN (...)` does not guarantee ordering.
- Emit each hydrated child as a full self-describing model object with `$schema`, `$id`, and normal response-visible fields.
- Apply child read/access rules during hydration.
- Missing/denied child ids must follow the same deterministic policy chosen for `T` fields.

Ordering pattern:

```python
ids = ["track-1", "track-2"]
items = Track.list(ids=ids)
by_id = {str(item.id): item for item in items}
hydrated = [by_id[str(id_)] for id_ in ids if str(id_) in by_id]
```

### `field: Ref[T]`

Meaning: globally resolvable pointer to `T`.

```python
class Job(ProtoModel):
    input_file: Ref[File]
```

Storage and default response:

```json
{
  "input_file": "https://storage.example.com/File/file-1"
}
```

Directive:

- Store as canonical absolute `$id` URL string.
- Accepted write inputs: absolute HTTP(S) URL string or object/dict with `$id`.
- Runtime shape is a validated string wrapper/value object: it compares, stores, and serializes like a URL string while exposing explicit helper methods.
- Emit as URL string.
- Never auto-hydrate.
- Explicit hydration only via `ref.hydrate()`.
- `Ref[T].hydrate()` returns a hydrated `T` instance and does not mutate or replace the ref value.
- Hydration must be async/transport-aware for remote URLs and must not happen during storage read, validation, or dump.

Runtime contract:

```python
class Job(ProtoModel):
    input_file: Ref[File]

job.input_file == "https://storage.example.com/File/file-1"
str(job.input_file) == "https://storage.example.com/File/file-1"

file = job.input_file.hydrate()
assert isinstance(file, File)
assert job.input_file == "https://storage.example.com/File/file-1"  # unchanged
```

Implementation direction:

```python
class Ref(str, Generic[T]):
    """Validated absolute HTTP(S) entity URL.

    Ref[T] is string-like for storage and JSON serialization, but keeps enough
    type information to support explicit helper methods such as hydrate().
    """

    target_cls: ClassVar[type | None] = None

    def __new__(cls, value: object):
        return str.__new__(cls, cls.url(value))

    @classmethod
    def url(cls, value: object) -> str:
        """Return the canonical absolute HTTP(S) URL for this ref value."""
        ...

    def hydrate(self, *, user=None, context=None) -> T:
        """Explicitly resolve this ref and return a hydrated T without mutating self."""
        ...
```

### `field: list[Ref[T]]`

Meaning: ordered collection of globally resolvable pointers.

```python
class Pipeline(ProtoModel):
    artifacts: list[Ref[File]]
```

Storage and default response:

```json
{
  "artifacts": [
    "https://storage.example.com/File/file-1",
    "https://storage.example.com/File/file-2"
  ]
}
```

Directive:

- Store as JSON list of absolute `$id` URL strings.
- Accepted write inputs: absolute HTTP(S) URL strings or objects/dicts with `$id`.
- Emit as URL string list.
- Never auto-hydrate.
- Optional explicit batch hydration can come later and must be async/transport-aware.

---

## 🗺️ Target Flow

```text
                   +-------------------------+
                   | Python model annotation |
                   +-----------+-------------+
                               |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v
      T or list[T]          Ref[T]           list[Ref[T]]
          |                    |                    |
          v                    v                    v
 local FK id(s)          absolute URL       JSON absolute URLs
          |                    |                    |
          v                    v                    v
 default full local hydrate explicit hydrate explicit hydrate only
          |                    |                    |
          +----------+---------+--------------------+
                     |
                     v
        API response uses full embedded objects for T/list[T]
        and absolute $id URL strings for Ref/list[Ref[T]]
```

---

## 📦 Existing Batch ID Support

Confirmed current capability:

```python
class StorableMixin:
    @classmethod
    def list(cls, sql_filter=None, limit=None, offset=None, populate=None, ids: list = None): ...
```

`SQLiteStorage.list(..., ids=...)` already implements:

```sql
WHERE id IN (?, ?, ...)
```

So `list[T]` hydration does **not** need a new public API. It needs a small ordering wrapper after fetch.

---

## 💻 Method Signature Surface

Planning artifact only; no callable/interface signatures changed by this document.

Proposed future implementation signatures:

```text
n3tx_core.models.ref
  + class Ref(str, Generic[T])  # validated string wrapper; serializes as URL string
      + @classmethod def url(cls, value: object) -> str
      + def hydrate(self, *, user=None, context=None) -> T
  + def is_ref_url(value: object) -> bool
  + def local_id_from_ref_url(value: object, *, target_cls=None, api_url=None) -> str | int | None
  + def public_id_url(value: object, *, target_cls=None, api_url=None) -> str
  - class ListRef
  - class _ListRefMarker
  - def hydrate_ref(...)
  - def canonical_ref_url(...)
  - def is_distributed_ref(value: object) -> bool
  - def parse_ref_string(value: str) -> tuple[str | None, str | None, str | None]
  - def canonicalize_ref(... n3tx:// ...)

n3tx_core.utils.introspection
  + def get_model_fields(model_class: type) -> list[tuple[str, type]]
  + def get_model_list_fields(model_class: type) -> list[tuple[str, type]]
  / def get_ref_fields(model_class: type) -> list[tuple[str, type]]
  / def get_ref_list_fields(model_class: type) -> list[tuple[str, type]]
  - def get_list_fields(...)  # if kept, rename semantics away from ListRef

n3tx_core.storage.sqlite_storage
  + def _hydrate_model_field(record: dict, field_name: str, target_cls: type) -> None
  + def _hydrate_model_list_field(record: dict, field_name: str, target_cls: type) -> None
  + def _hydrate_ordered_ids(target_cls: type, ids: list) -> list
  / def _normalize_ref_storage_values(model_class, data)
  - def _local_ref_href(value, target_cls)
  - def _public_storage_ref(value, target_cls)  # replace with URL canonicalization

n3tx_actors.api.remote_matrix
  - class RemoteMatrix  # or heavily simplify/replace with HTTP URL adapter
  - class MatrixReferenceResolver  # revisit once Ref[T] is explicit-hydrate only
```

---

## 🧩 Implementation Plan

### Phase 0 — Remove `ListRef[T]` completely

Outcome: no source, tests, examples, or docs import or depend on `ListRef`.

Steps:

1. Inventory all `ListRef`, `_ListRefMarker`, `get_list_fields`, `__fk_models__`, `__owner__`, `__parent__`, and `__tagname__` usages.
2. Convert model fields:
   - local collections -> `list[T]`
   - pointer collections -> `list[Ref[T]]`
3. Remove generated join-model behavior that exists only because of `ListRef`.
4. Remove ListRef route assumptions from direct and actor routing.
5. Update widgets/schema/scaffold/populate docs to describe `list[T]` and `list[Ref[T]]`.
6. Delete ListRef tests and replace with `list[T]` / `list[Ref[T]]` tests.

Verification:

```bash
python3 scripts/test-backend.py --suite core -- -q
python3 -m pytest examples/core/tests/ -q
```

### Phase 1 — Lock the new identity contract with tests

Add/adjust characterization tests before changing behavior:

- `$id` is always absolute HTTP(S).
- No `$addr` exists.
- No `n3tx://` appears in emitted responses.
- `Ref[T]` stores/emits absolute URL strings.
- `list[Ref[T]]` stores/emits JSON URL string arrays.
- `T` and `list[T]` hydrate by default.
- `list[T]` hydration uses `T.list(ids=...)` and preserves order.

### Phase 2 — Simplify `Ref[T]` around HTTP(S) URLs

Refactor `models/ref.py`:

- remove `n3tx://` parsing and service registry canonicalization
- validate/normalize absolute HTTP(S) URLs
- move canonical URL normalization onto `Ref.url(value)` rather than a standalone `canonical_ref_url()` helper
- allow current-service URL -> local id extraction where storage needs FK behavior
- implement explicit hydration on `Ref.hydrate()`; remove standalone `hydrate_ref()` if it exists

Target behavior:

```python
job.input_file == "https://storage.example.com/File/file-1"
file = job.input_file.hydrate()
```

### Phase 3 — Make storage match the four field semantics

Storage behavior:

```text
T              -> local FK id column or JSON scalar id, hydrate by default
list[T]        -> JSON id list, hydrate by default via T.list(ids=...)
Ref[T]         -> TEXT URL string, no auto hydrate
list[Ref[T]]   -> JSON URL string list, no auto hydrate
```

Key work:

- update introspection to distinguish model fields from ref fields
- update migration to store `list[T]` as JSON
- update read/list/get paths to hydrate local model fields by default
- remove href-array generation from storage

### Phase 4 — Update API/dump/schema contract

Keep `$id` as the full URL and keep `$schema` on every hydrated model object.

```json
{
  "$schema": "https://api.example.com/Product",
  "$id": "https://api.example.com/Product/product-1"
}
```

Response metadata rule:

```text
hydrated model object       -> includes $schema + $id
unhydrated Ref[T]           -> absolute URL string only
unhydrated list[Ref[T]]     -> absolute URL string array only
```

Rationale:

- preserves N3TX's schema-driven contract for embedded hydrated objects
- keeps frontend DynamicClass/runtime behavior simple and type-aware
- avoids inferring model type from URL path parsing
- gives agents/tools self-describing embedded entities
- keeps pointer refs lightweight when hydration is not requested

Remove schema/docs/tests implying:

- `$id` is a DB id
- `$addr` exists
- href arrays are the default relationship representation
- `n3tx://` is a supported public reference

### Phase 5 — Replace remote actor refs with HTTP(S) URL routing

Current `RemoteMatrix` exists to translate `n3tx://service/Class/id` into HTTP routes. That role should disappear.

New behavior:

```text
TX.target = "https://storage.example.com/File/file-1"

if target host == local API host:
  route internally
else:
  issue HTTP request to the URL directly
```

Route/method invocation should still use schema-declared `@expose_route` method metadata where needed.

### Phase 6 — Frontend cleanup

Frontend already mostly treats `$id` as entity href. Standardize that fully:

- `$id` is the entity's canonical href
- ref fields are URL strings
- `list[T]` fields are hydrated object arrays
- `list[Ref[T]]` fields are URL string arrays
- no ListRef href arrays
- no `n3tx://` handling

---

## ⚠️ Risks and Design Pressure

| Risk | Why it matters | Mitigation |
|---|---|---|
| Large ListRef blast radius | ListRef currently drives join models, nested routes, docs, UI assumptions | Remove first in a focused branch/PR with exhaustive grep-backed checklist |
| `list[T]` default hydration can create cycles | Parent/child graphs may recursively load | Add depth/cycle guards before broad use |
| `list[T]` ordering | SQL `IN` does not preserve order | Reorder results after batch fetch |
| Remote auth | HTTP(S) URLs are resolvable but may require credentials | Keep auth/user propagation at transport adapter layer |
| Existing frontend href assumptions | Components expect href arrays for relationships | Convert relationship UI to object arrays for `list[T]`, URL arrays for `list[Ref[T]]` |
| Nested routes | Previously emerged from ListRef/join model machinery | Treat as route/view feature, not storage primitive |

---

## 🧪 Verification Plan

Backend:

```bash
python3 scripts/test-backend.py --suite core -- -q
python3 scripts/test-backend.py --suite actors -- -q
python3 scripts/test-backend.py --suite files -- -q
python3 -m pytest examples/core/tests/ -q
python3 -m pytest examples/grants/tests/ -q
```

Frontend:

```bash
cd tests/frontend && npx vitest run
cd tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js
```

Search gates:

```bash
rg "ListRef|_ListRefMarker|n3tx://|\$addr" .
```

Expected after migration:

- no `ListRef` source usage
- no `_ListRefMarker` source usage
- no public `n3tx://` docs/tests/source behavior
- no `$addr`

---

## ✨ Critical Files

### Core model/ref/storage

- `packages/n3tx-core/src/n3tx_core/models/ref.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`
- `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`

### Routes/actors/network

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/api/remote_matrix.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`

### Frontend/UI

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Component.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list-field.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js`
- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`

### Optional packages/docs/examples/tests

- `packages/n3tx-files/src/n3tx_files/address.py`
- `docs/CORE.md`
- `docs/ACTORS.md`
- `BACKEND.md`
- examples under `examples/core`, `examples/actors`, `examples/grants`
- unit tests under all affected packages

---

## ✅ Execution Directive

Do not start by trying to support both old and new systems.

Start by removing `ListRef[T]` completely, then make the remaining field-type matrix simple and explicit:

```text
T              local hydrated object
list[T]        local hydrated object list
Ref[T]         absolute URL pointer
list[Ref[T]]   absolute URL pointer list
```

The expected result is fewer concepts, fewer hydration paths, fewer route-specific identity shapes, and a reference model that works naturally across backend, frontend, agents, and remote services.
