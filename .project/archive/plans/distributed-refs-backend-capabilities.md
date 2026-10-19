# Distributed Refs and Backend-to-Backend Capabilities Plan

✅ **Goal**

Add distributed backend-to-backend capabilities to N3TX by extending the existing `Ref` + `Matrix` architecture instead of introducing a parallel distributed object system.

The intent-preserving semantic change is:

```text
Ref[T] means “a pointer to a T actor/model identity that Matrix can resolve.”

It does not necessarily mean “an integer FK in this process-local database.”
```

This plan preserves N3TX’s existing developer model:

- models remain the single source of truth;
- refs remain normal model fields;
- storage/hydration/populate continue to do the plumbing;
- Matrix remains the routing abstraction;
- backend-to-backend communication reuses existing class-name REST routes for the first end-to-end slice.

---

## ✅ Final Decisions Captured

| Topic | Decision | Rationale |
|---|---|---|
| First milestone | **End-to-end thin slice** | Prove parser → storage → populate → remote REST call → method call as one vertical capability. |
| Route identity | **Class-name routes** | Distributed identity should be semantic model identity, not table-name storage identity. |
| Canonical distributed ref | **`n3tx://<service>/<ClassName>/<id>`** | Lets Matrix distinguish N3TX-distributed refs from arbitrary external links. |
| Accepted input refs | local ints, local paths, current API URLs, configured remote HTTP URLs, canonical `n3tx://` refs | Preserve existing behavior while accepting deployment-friendly URLs. |
| `ListRef[T]` semantics | **Local owned relationship only** | Avoid conflating ownership/join-table relationships with distributed pointers. |
| `list[Ref[T]]` semantics | **Local/remote identity pointer array** | Minimal, explicit home for app state like `files: [n3tx://storage/File/12]`. |
| Remote transport | **Existing REST class-name routes** | Avoid adding generic `/_tx` in first slice; reuse `/Model/id` and `/Model/id/method`. |
| Remote populate | **Immediate, best-effort** | Distributed graphs are partial; parent reads should survive remote failures. |
| Auth | **Service token + forwarded user context** | Preserve service trust and current user ABAC continuity. |
| Config | **Config/env first, `create_app(remotes=...)` override** | Remotes are often deployment configuration; app override keeps tests ergonomic. |
| Python dereferencing | **Preserve current behavior: href/canonical ref normally, populate for eager resolution, explicit async proxy/helper for remote method calls** | Python cannot safely hide async network IO behind normal attribute access. |
| Address representation | **An address is a string** | Avoid introducing a new public `ReferenceAddress` object; keep the mental model simple. |
| Ref module ownership | **Promote ref semantics into `models/ref.py`** | `Ref`, `ListRef`, parser/canonicalizer helpers, and public string semantics live together. Remote dereference is injected into storage/app wiring, not registered globally. |
| Implementation style | **Opt-in/additive by default** | Existing local apps should not need to understand distributed refs; guarded changes only where current code would corrupt remote refs. |

---

## 📍 Current System Behavior

### `Ref[T]` today

Current single refs are local-FK-oriented.

```python
owner: Ref[User]
```

Normal reads hydrate the field as an href-like string:

```json
{
  "owner": "http://localhost:5000/users/12"
}
```

`populate=owner` eagerly loads the referenced row and overlays populated data during serialization through `instance.__dict__['_populated']` and the `proto_dump.populate` stage.

Important current files:

- `packages/n3tx-core/src/n3tx_core/utils/typer.py`
  - `Ref`
  - `flatten_refs()`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
  - `list()` local href hydration
  - `get()` local href hydration
  - `_populate_fields()` eager loading
- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`
  - `populate()` overlay stage

### `ListRef[T]` today

`ListRef[T]` is a local relationship primitive, not a stored list on the parent row.

```python
comments: ListRef[Comment]
```

Normal reads derive href arrays from child/join tables:

```json
{
  "comments": ["http://localhost:5000/products/1/comments/2"]
}
```

`populate=comments` overlays a paginated collection:

```json
{
  "comments": {
    "data": [{"$id": "http://localhost:5000/Product/1/Comment/2", "text": "..."}],
    "meta": {"total": 1, "limit": 20, "offset": 0, "has_more": false}
  }
}
```

Important current files:

- `packages/n3tx-core/src/n3tx_core/models/ref.py`
  - `ListRef`
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
  - `get_list_fields()`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
  - collection href hydration and eager populate
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
  - skips `ListRef[T]` columns on parent tables

### Matrix today

`Matrix.inbox()` already has the right distributed-routing seam:

```text
TX(target='products/1')
  -> Matrix.inbox()
  -> local child first
  -> adapter fallback second
```

Relevant files:

- `packages/n3tx-actors/src/n3tx_actors/matrix.py`
  - `Matrix.inbox()`
  - `Matrix.request()`
  - `Matrix.stream()`
  - `Matrix.register_adapter()`
- `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py`
  - request/response correlation
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
  - current REST → TX bridge for actor routing

---

## 🗺️ Target Mental Model

```python
class Job(ActorModel):
    __tablename__ = "jobs"
    __storable__ = True

    owner: Ref[User] | None = None              # local or remote T identity
    files: list[Ref[File]] = []                 # pointer array, JSON-backed
    artifacts: list[Ref[Artifact]] = []         # pointer array, JSON-backed
    comments: ListRef[Comment] = []             # local owned children
```

### Meaning by field type

| Field shape | Meaning | Storage | Populate behavior |
|---|---|---|---|
| `Ref[T]` | Single local or distributed identity pointer | local id for local refs; canonical `n3tx://...` for remote refs | local SQLite or remote REST |
| `list[Ref[T]]` | JSON-backed list of local/distributed identity pointers | JSON TEXT array of canonical refs | best-effort local + remote resolution |
| `ListRef[T]` | Local owned/scoped relationship | child/join tables | existing local paginated collection behavior |

### Example serialized app state

Input may be deployment-native HTTP URLs:

```json
{
  "files": ["http://storage:7100/File/12"],
  "artifacts": ["http://storage:7100/Artifact/42"]
}
```

After canonicalization, N3TX stores/returns Matrix-resolvable refs:

```json
{
  "files": ["n3tx://storage/File/12"],
  "artifacts": ["n3tx://storage/Artifact/42"]
}
```

---

## 🧭 Canonical Reference Rules

### Canonical forms

| Input | If configured/current | Canonical interpretation |
|---|---|---|
| `12` | target type known | local `File/12` identity, storage may keep `12` for single `Ref[T]` |
| `/File/12` | local path | local class-name identity |
| `http://current-api/File/12` | equals `config.API_URL` | local class-name identity |
| `http://storage:7100/File/12` | matches remote `storage` config | `n3tx://storage/File/12` |
| `n3tx://storage/File/12` | remote exists | distributed N3TX ref |
| `https://external.example/file.pdf` | not configured as N3TX remote | external link, not a `Ref[T]` unless explicitly allowed elsewhere |

### Canonical distributed shape

```text
n3tx://<service-name>/<ClassName>/<id>
```

Examples:

```text
n3tx://storage/File/12
n3tx://storage/Artifact/42
```

### Why canonicalize

Canonicalization prevents ambiguous strings:

```text
https://example.com/foo.pdf       -> external URL
n3tx://storage/File/12            -> Matrix-resolvable distributed object
http://storage:7100/File/12       -> accepted input, canonicalized if storage is configured
```

---

## 🧩 Architecture

```text
Model field value
  Ref[T] / list[Ref[T]]
        |
        v
ReferenceAddress parser/canonicalizer
        |
        +-- local int/path/current API URL
        |       |
        |       v
        |   SQLite storage + local Matrix
        |
        +-- n3tx://service/ClassName/id
                |
                v
          SQLiteStorage reference_resolver
                |
                v
          Matrix / RemoteMatrix REST adapter
                |
                +-- GET  http://service/ClassName/id
                +-- POST http://service/ClassName/id/method
```

### No generic `/_tx` in the first slice

The long-term TX-native option remains valid, but first implementation should use class-name REST routes:

```text
GET  /File/12
POST /File/12/process
```

This keeps the new distributed slice aligned with existing generated route behavior and avoids opening a broad generic TX endpoint before auth and trust boundaries are fully designed.

---

## 📊 Approaches and Tradeoffs

### Option A — String-address `Ref` helpers + REST-backed RemoteMatrix ✅ Chosen

| Dimension | Result |
|---|---|
| Developer API | Minimal: `Ref[T]`, `list[Ref[T]]`, and canonical string refs. |
| Architecture fit | Strong: uses existing storage, populate, Matrix, route grammar. |
| First-slice scope | End-to-end but bounded. |
| Remote method calls | Via class-name REST routes. |
| Risk | Requires careful parser/canonicalization and best-effort error shape, but no new public address object. |

### Option B — Plain URL strings only

| Dimension | Result |
|---|---|
| Developer API | Easy to store, poor to use. |
| Architecture fit | Weak: bypasses Matrix and typed model contracts. |
| Risk | Creates ad hoc fetch logic throughout the codebase. |

Rejected as the main design.

### Option C — Extend `ListRef[T]` for remote refs

| Dimension | Result |
|---|---|
| Developer API | Superficially convenient. |
| Architecture fit | Weak: conflates local ownership with remote pointers. |
| Risk | Requires auxiliary tables and more ambiguous relationship semantics. |

Rejected for the first implementation. Keep `ListRef[T]` local.

### Option D — Generic TX ingress (`POST /_tx`)

| Dimension | Result |
|---|---|
| Architecture fit | Strong long-term. |
| First-slice cost | Higher: new endpoint, auth, streaming, and arbitrary target semantics. |
| Risk | Expands public/protocol surface too early. |

Deferred. Revisit after REST-backed distributed refs prove the contract.

---

## 🛠️ Implementation Plan

### Slice 1 — Promote `models/ref.py` into the canonical ref module

Update:

```text
packages/n3tx-core/src/n3tx_core/models/ref.py
packages/n3tx-core/src/n3tx_core/utils/typer.py
```

Responsibilities:

- Co-locate `Ref[T]`, `ListRef[T]`, string ref parser helpers, and canonicalization helpers.
- Move or re-home the current `Ref` implementation from `utils/typer.py` into `models/ref.py`.
- Keep `utils/typer.py` as a compatibility import surface during migration:

  ```python
  from n3tx_core.models.ref import Ref, flatten_refs
  ```

- Parse local ids, local paths, current API URLs, configured remote URLs, and `n3tx://` URLs.
- Canonicalize configured remote HTTP(S) URLs to `n3tx://<service>/<Class>/<id>`.
- Reject or classify unconfigured external URLs so Matrix does not treat arbitrary links as distributed refs.
- Preserve class-name route identity.
- Provide storage and hydration helpers for `Ref[T]` and `list[Ref[T]]`.
- Avoid a public `ReferenceAddress` object. An address is a string; helper functions return strings, ids, booleans, or lightweight private parse dicts/tuples as needed.

Code shape:

```python
class Ref(Generic[T]):
    """Typed model/actor identity pointer."""


class ListRef:
    """Local owned relationship marker."""


def is_distributed_ref(value: object) -> bool:
    """True for canonical n3tx://service/Class/id refs."""


def is_external_link(value: object, *, remotes=None) -> bool:
    """True for non-N3TX URLs that should not route through Matrix."""


def parse_ref_string(value: str) -> tuple[str | None, str | None, str | None]:
    """Return (service, class_name, id) for canonical refs/paths.

    This is an internal helper shape, not a public address object.
    """


def canonicalize_ref(value, *, target_cls=None, api_url=None, remotes=None) -> str | int | None:
    """Return local id for local single refs where appropriate, else canonical URI/path."""


def local_ref_id(value, *, target_cls=None, api_url=None, remotes=None) -> int | None:
    """Return id only if the ref is local/current-service."""


def public_ref(value, *, target_cls=None, api_url=None, remotes=None) -> str | None:
    """Return response-facing local href or canonical n3tx URI."""


```

Remote dereference is not a `models/ref.py` registry. It is an optional storage
dependency so default SQLite behavior remains local-only:

```python
SQLiteStorage(reference_resolver=None)
SQLiteStorage(reference_resolver=MatrixReferenceResolver(matrix))
```

Tests:

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_references.py`
- Mirror `n3tx_files/tests/test_address.py` style.
- Cover:
  - int id;
  - `/File/12`;
  - current `API_URL` absolute URL;
  - configured remote HTTP URL;
  - canonical `n3tx://storage/File/12`;
  - unconfigured external URL;
  - invalid class/id shape;
  - table-name path rejection or class-name normalization policy.

---

### Slice 2 — Configure remote services

Update:

```text
packages/n3tx-core/src/n3tx_core/config.py
packages/n3tx-core/src/n3tx_core/app.py
```

Add config/env support:

```text
N3TX_SERVICE_NAME=api
N3TX_SERVICE_TOKEN=...
N3TX_REMOTES={"storage":{"url":"http://storage:7100","token":"..."}}
```

Recommended Python shape:

```python
REMOTES = {
    "storage": {
        "url": "http://storage:7100",
        "token": "...",
    }
}
```

Add app override:

```python
create_app(
    models=[Job],
    routing="actor",
    remotes={
        "storage": {
            "url": "http://storage:7100",
            "token": "...",
        }
    },
)
```

Precedence:

```text
create_app(remotes=...) > config/env defaults
```

Builder behavior:

- Parse/store remotes in config for both direct and actor routing.
- Register `RemoteMatrix` automatically only in `routing='actor'` when remotes exist.
- Direct routing can store/canonicalize remote refs but remote method calls/populate may need a resolver path or should be explicitly unsupported until actor routing is used.

---

### Slice 3 — Promote `Ref[T]` storage and validation

Update:

```text
packages/n3tx-core/src/n3tx_core/utils/typer.py
packages/n3tx-core/src/n3tx_core/models/storable_mixin.py
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py
```

Behavior:

- `Ref.__init__()` accepts:
  - `BaseModel`;
  - `int`;
  - `dict` containing `id` or `$id`;
  - local path strings;
  - current-service HTTP URLs;
  - configured remote HTTP URLs;
  - canonical `n3tx://` refs.
- `flatten_refs()` stores:
  - local single refs as local ids when possible;
  - remote single refs as canonical `n3tx://...` strings.
- Existing integer DB values continue to read as local refs.

Additive policy:

- Do not change local `Ref[T]` behavior for existing integer/local refs.
- Do not require apps to opt into distributed refs unless they use `n3tx://...`, configured remote HTTP refs, or remote resolver setup.
- Keep all new parsing/canonicalization behavior behind `models/ref.py` helpers.
- Existing call sites should delegate to helpers only where the old code currently assumes “everything is an int/local href”.

Migration policy:

- New `Ref[T]` columns should be `TEXT` compatible so they can store local ids or canonical remote refs.
- Existing DBs with integer columns should continue to work because SQLite is permissive, but code should not rely on that indefinitely.
- No eager migration of old data in the first slice.

Schema policy:

- Preserve JSON Schema ref semantics (`$ref` to target model) where possible.
- Consider adding N3TX-specific metadata later:

```json
{
  "type": "$ref",
  "$ref": "#/$defs/File",
  "x-n3tx-ref": {
    "distributed": true,
    "canonical": "n3tx://<service>/<ClassName>/<id>"
  }
}
```

Do not require frontend changes for the first backend-focused slice unless tests reveal schema consumers need explicit string format metadata.

---

### Slice 4 — Add `list[Ref[T]]` introspection/storage/schema behavior

Update:

```text
packages/n3tx-core/src/n3tx_core/utils/introspection.py
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
packages/n3tx-core/src/n3tx_core/models/proto_schema.py
```

Add:

```python
def get_ref_list_fields(model_class) -> list[tuple[str, type]]:
    """Return fields typed list[Ref[T]] / Optional[list[Ref[T]]]."""
```

Behavior:

- `list[Ref[T]]` is JSON TEXT storage.
- It is **not** a `ListRef[T]` local relationship.
- Writes normalize every item to local/public/canonical distributed ref form.
- Reads return canonical refs.
- `populate=files` can resolve items into a best-effort populated wrapper.

Target normal read:

```json
{
  "files": ["n3tx://storage/File/12"]
}
```

Target populated read:

```json
{
  "files": {
    "data": [{"$id": "n3tx://storage/File/12", "name": "report.pdf"}],
    "refs": ["n3tx://storage/File/12"],
    "errors": []
  }
}
```

Failure shape:

```json
{
  "files": {
    "data": [],
    "refs": ["n3tx://storage/File/12"],
    "errors": [
      {"ref": "n3tx://storage/File/12", "message": "Remote service unavailable"}
    ]
  }
}
```

---

### Slice 5 — Update local hydration and populate

Update:

```text
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
packages/n3tx-core/src/n3tx_core/models/proto_dump.py
```

Replace duplicated local href logic and fragile id extraction:

```diff
- record[field_name] = f"{config.API_URL}/{target_table}/{val}"
+ if is_distributed_ref(val):
+     record[field_name] = public_ref(val, target_cls=target_cls)
+ else:
+     record[field_name] = existing_local_href_behavior(...)

- fk_id = val.rsplit('/', 1)[-1] if isinstance(val, str) and '/' in val else val
- fk_ids.append(int(fk_id))
+ fk_id = local_ref_id(val, target_cls=target_cls)
+ if fk_id is not None:
+     fk_ids.append(fk_id)
+ else:
+     remote_refs.append(val)
```

Important: this slice should be the smallest guarded storage change possible. The goal is not to rewrite `sqlite_storage.py`; it is to prevent two existing assumptions from breaking distributed refs:

1. Hydration must not convert `n3tx://storage/File/12` into `API_URL/table/n3tx://storage/File/12`.
2. Populate must not cast distributed refs to `int`.

All substantive semantics should remain in `models/ref.py`.

Populate behavior by ref kind:

| Ref kind | Populate result |
|---|---|
| local id/path/current-service URL | Existing SQLite eager load. |
| configured remote `n3tx://service/Class/id` | Remote REST GET, best-effort overlay. |
| unconfigured external URL | Leave as ref/string; include error only if field is explicitly a `Ref[T]`. |
| malformed ref | Do not crash parent read; attach best-effort error where possible. |

Best-effort rules:

- Parent `get/list` succeeds even if remote refs fail.
- Remote errors are per-field/per-ref.
- Local populate behavior remains strict enough to preserve existing tests.
- Remote response data should have `$id` rewritten/canonicalized to `n3tx://service/Class/id` if the remote returns `http://service/Class/id`.

---

### Slice 6 — Add REST-backed `RemoteMatrix`

Add:

```text
packages/n3tx-actors/src/n3tx_actors/api/remote_matrix.py
```

Responsibilities:

- Map canonical `n3tx://service/Class/id` references to configured remote base URLs.
- Support remote `get` via:

```text
GET {remote.url}/{ClassName}/{id}
```

- Support remote instance method calls via:

```text
POST {remote.url}/{ClassName}/{id}/{method}
```

- Attach service token and forwarded user context.
- Return TX-compatible responses for Matrix callers.

Code shape:

```python
class RemoteMatrix(NetworkAdapter, auto_register=False):
    def __init__(self, remotes=None, **kwargs):
        kwargs.setdefault("addr", "remote")
        super().__init__(**kwargs)
        self.remotes = normalize_remotes(remotes)

    def can_handle(self, tx: TX) -> bool:
        return is_n3tx_remote_target(tx.target) or bool(tx.meta.get("remote"))

    async def send(self, tx: TX) -> None:
        response = await self.request_remote_rest(tx)
        await self.inbox(response)
```

TX mapping:

| TX | REST call |
|---|---|
| `TX(name='get', target='n3tx://storage/File/12')` | `GET http://storage:7100/File/12` |
| `TX(name='process', target='n3tx://storage/File/12', data={...})` | `POST http://storage:7100/File/12/process` |
| `TX(name='schema', target='n3tx://storage/File')` | optional later: `GET http://storage:7100/File` |

Auth headers proposal:

```text
Authorization: Bearer <service-token>
X-N3TX-Service: <local-service-name>
X-N3TX-User: <json-or-jwt-user-context>   # exact encoding to define during implementation
```

Prefer using existing JWT/user middleware conventions if present. If forwarding full user objects is too invasive, start with a compact signed/JSON user context and document it clearly.

Dependencies:

- Use `httpx` if already available in project dependencies.
- If not available in core actors package dependencies, either add package dependency deliberately or use standard-library async-unfriendly fallback only for tests. Prefer `httpx` for correctness.

---

### Slice 7 — Add remote resolve/proxy helper

Add:

```text
packages/n3tx-actors/src/n3tx_actors/remote_proxy.py
```

or a small helper under `api/remote_matrix.py` if keeping surface area smaller.

Intent:

- Do not overload normal Python attribute access with hidden network IO.
- Provide a clean explicit API for remote method calls.

Code shape:

```python
class RemoteRef:
    def __init__(self, ref, *, model_cls=None, matrix=None, user=None):
        self.ref = parse_reference(ref, target_cls=model_cls)
        self.model_cls = model_cls
        self.matrix = matrix or Actor.root()
        self.user = user

    async def get(self):
        return await self.call("get")

    async def call(self, method: str, **data):
        tx = TX(
            name=method,
            source="remote-proxy",
            target=self.ref.canonical,
            data=data,
            meta={"user": self.user},
        )
        response = await self.matrix.request(tx)
        if response.is_error:
            raise RemoteRefError(response.data)
        return response.data
```

Developer usage:

```python
artifact = Artifact.ref("n3tx://storage/Artifact/42")
data = await artifact.get()
result = await artifact.call("process", mode="fast")
```

Future ergonomic layer:

```python
artifact = Artifact.ref(job.artifacts[0])
await artifact.call("process")
```

---

### Slice 8 — Remote populate integration

Add remote resolver path used by storage populate.

Potential implementation choices:

| Shape | Pros | Cons | Recommendation |
|---|---|---|---|
| Storage imports actors resolver directly | Simple | Core → actors dependency violation | Avoid. |
| Core resolver registry/callback | Preserves package boundary | Adds global plugin bus outside the core storage pattern | Avoid. |
| Injected storage resolver | Preserves package boundary; mirrors storage dependency injection; defaults to local-only behavior | Requires app/bootstrap wiring | ✅ Use this. |
| Actor-only populate support | Simple package-wise | Direct routing cannot remote-populate | Acceptable if explicit. |

Recommended boundary-preserving shape:

```text
SQLiteStorage(reference_resolver=None)
  default: local-only Ref populate; remote refs remain canonical strings

SQLiteStorage(reference_resolver=MatrixReferenceResolver(matrix))
  optional: remote refs resolve through Matrix/RemoteMatrix
```

This mirrors `n3tx_files.materialize` and avoids importing actors from core storage.

Behavior:

- `SQLiteStorage._populate_fields()` uses its optional `reference_resolver` for non-local refs.
- If no resolver is injected, remote refs remain refs; populated `list[Ref[T]]` includes best-effort per-ref errors.
- Actor/app bootstrap injects a Matrix-backed resolver when RemoteMatrix is configured.

---

### Slice 9 — Documentation updates

Update after implementation:

| Doc | Required update |
|---|---|
| `docs/MODELS.md` | New `Ref[T]` semantics, `list[Ref[T]]`, `ListRef[T]` distinction. |
| `docs/ACTORS.md` | RemoteMatrix, REST-backed distributed routing, service auth. |
| `docs/ARCHITECTURE.md` | Distributed ref flow in architecture diagram. |
| `BACKEND.md` | Key files, config/env, test commands. |
| `packages/n3tx-core/docs/storage.md` | Ref column compatibility and JSON-backed ref arrays. |
| `packages/n3tx-actors/docs/network-adapters.md` if present | RemoteMatrix adapter contract. |

---

## 🧪 Test Plan

### Unit tests

| Area | Test file |
|---|---|
| Reference parser/canonicalizer | `packages/n3tx-core/src/n3tx_core/tests/unit/test_references.py` |
| Single `Ref[T]` storage compatibility | `packages/n3tx-core/src/n3tx_core/tests/unit/test_ref_storage.py` |
| `list[Ref[T]]` JSON storage | core storage tests |
| Schema for distributed refs | core schema tests |
| Best-effort populate local/remote split | core populate tests with fake resolver |
| RemoteMatrix REST mapping | `packages/n3tx-actors/src/n3tx_actors/tests/test_remote_matrix.py` |
| Remote proxy method calls | actor remote proxy tests |

### Integration tests

Create a two-service test fixture:

```text
storage service:
  File, Artifact models
  routes: /File/{id}, /Artifact/{id}

app service:
  Job model
  files: list[Ref[File]]
  artifacts: list[Ref[Artifact]]
  remotes: {"storage": {"url": storage_url, "token": test_token}}
```

Assertions:

1. App accepts HTTP remote refs and stores canonical `n3tx://` refs.
2. Normal app read returns canonical refs.
3. `populate=files,artifacts` fetches remote data best-effort.
4. Failed remote fetch leaves parent read successful and includes per-ref error.
5. Remote method proxy maps to `POST /Class/id/method`.
6. Service token is attached.
7. User context is forwarded where available.

### Verification commands

```bash
cd /workspace && python3 scripts/test-backend.py --suite core -- -q
cd /workspace && python3 scripts/test-backend.py --suite actors -- -q
cd /workspace && python3 scripts/test-backend.py --short
```

---

## ⚠️ Risks and Guardrails

| Risk | Guardrail |
|---|---|
| Conflating remote refs with arbitrary URLs | Canonicalize configured N3TX remotes to `n3tx://`; classify unconfigured URLs as external. |
| Confusing `ListRef[T]` and `list[Ref[T]]` | Document and test sharply: relationship vs pointer array. |
| Core importing actors | Inject a Matrix-backed reference resolver into storage/app wiring; core never imports actors. |
| Hidden async IO | Keep normal field access as refs; use populate or explicit proxy/resolve helpers. |
| Remote service outage breaks local reads | Best-effort populate with per-ref errors. |
| Auth leakage | Forward user context only under configured service trust; use service token for backend identity. |
| URL/table/class ambiguity | Class-name identity is canonical; table-name support only if deliberately added as compatibility input. |
| Column migration surprises | Tolerant read path; TEXT-compatible new refs; no forced migration in first slice. |
| Overbroad first slice | REST-backed only; defer generic TX ingress and streams. |

---

## ✨ Implementation Order

1. **Ref module promotion**: move/promote `Ref`, `ListRef`, and string helpers into `models/ref.py`; keep `utils/typer.py` compatibility exports.
2. **Config/env remotes**: `N3TX_REMOTES`, `N3TX_SERVICE_NAME`, app override.
3. **Single `Ref[T]` promotion**: validation, flattening, storage/hydration compatibility.
4. **`list[Ref[T]]` support**: introspection, JSON normalization, schema hints.
5. **Populate update**: local/remote split, best-effort error wrapper, injected storage resolver.
6. **RemoteMatrix**: REST-backed GET/method POST mapping, service token + user forwarding.
7. **Remote proxy/helper**: explicit method-call API for remote object refs.
8. **Two-service integration test**: prove end-to-end distributed refs.
9. **Docs**: update model, actor, backend, architecture, package docs.

This order keeps each slice reviewable while still reaching the requested end-to-end capability early.

---

## 📍 Critical Files

### Core

- `packages/n3tx-core/src/n3tx_core/models/ref.py` — canonical `Ref`, `ListRef`, string parser/canonicalizer.
- `packages/n3tx-core/src/n3tx_core/utils/typer.py` — compatibility re-export/migration surface for `Ref` and `flatten_refs()`.
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py` — `get_ref_list_fields()`.
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` — minimal guarded delegation so distributed refs are not local-href-wrapped or int-cast during populate.
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py` — TEXT-compatible `Ref[T]` column handling.
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py` — schema hints for distributed ref arrays if needed.
- `packages/n3tx-core/src/n3tx_core/config.py` — service/remotes config.
- `packages/n3tx-core/src/n3tx_core/app.py` — `create_app(remotes=...)` and actor registration hook.

### Actors

- `packages/n3tx-actors/src/n3tx_actors/api/remote_matrix.py` — REST-backed distributed adapter.
- `packages/n3tx-actors/src/n3tx_actors/remote_proxy.py` — explicit remote ref method-call helper.
- `packages/n3tx-actors/src/n3tx_actors/matrix.py` — likely no behavior change required; validate adapter fallback remains enough.
- `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py` — likely no behavior change required; reuse correlation patterns.
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` — ensure class-name routes satisfy remote GET/method POST needs.

### Tests and docs

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_references.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_ref_storage.py`
- `packages/n3tx-actors/src/n3tx_actors/tests/test_remote_matrix.py`
- `docs/MODELS.md`
- `docs/ACTORS.md`
- `docs/ARCHITECTURE.md`
- `BACKEND.md`

---

## ✅ Definition of Done for First End-to-End Slice

The first implementation milestone is complete when:

1. A model can define:

   ```python
   files: list[Ref[File]] = []
   ```

2. The app accepts:

   ```json
   {"files": ["http://storage:7100/File/12"]}
   ```

3. The value stores/returns as:

   ```json
   {"files": ["n3tx://storage/File/12"]}
   ```

4. `GET /Job/1?populate=files` fetches `GET http://storage:7100/File/12` and overlays data.
5. Remote populate failure does not fail `GET /Job/1`; it returns the canonical ref plus an error entry.
6. A remote proxy/helper can call `POST http://storage:7100/File/12/{method}`.
7. Local `Ref[T]` and existing `ListRef[T]` tests still pass.
8. Service token and user context behavior is covered by tests or documented if partially deferred.
9. Relevant docs are updated.

---

## Saved Plan

- `.project/plans/distributed-refs-backend-capabilities.md`
