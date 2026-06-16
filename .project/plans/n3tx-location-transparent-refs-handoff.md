# N3TX Handoff Plan — Location-Transparent `Ref[T]` Resolution Through Matrix

## ✅ Executive recommendation

Implement **location-transparent references** in N3TX so `Ref[T]` stores a resolvable actor/model identity and resolves through Matrix:

```python
media: Ref[Media]                  # existing single reference shape
files: list[Ref[File]]             # independent local/remote actor refs
artifacts: list[Ref[Artifact]]     # independent local/remote actor refs
```

Serialized app state should be able to look like this:

```json
{
  "files": ["http://storage:7100/File/12"],
  "artifacts": ["http://storage:7100/Artifact/42"]
}
```

The crucial semantic change is:

```text
Ref[T] means “a pointer to a T actor/model identity that Matrix can resolve.”
It does not necessarily mean “an integer FK in this process-local database.”
```

This should be additive and backward-compatible: current local integer refs, relative URL refs, and same-origin URL refs must continue to behave as local references.

---

## 🎯 Intent

N3TX’s architecture already centers actor routing:

```text
Model definition
  -> schema
  -> generated route / TX
  -> Matrix
  -> ActorModel / storage / remote adapter
```

For distributed N3TX applications, references should follow the same architecture. App code should not decide whether a `File`, `Artifact`, `User`, or other model lives locally or on a remote node. That is Matrix’s job.

Target developer experience:

```python
file_ref: Ref[File] = "http://storage:7100/File/12"

file = await file_ref.resolve()          # Matrix-routed
local = await file_ref.materialize()     # File-capability materialization, when T is File-like
```

Target model shape in our app:

```python
class Media(ActorModel):
    files: list[Ref[File]] = Field(default_factory=list)


class Run(ActorModel):
    artifacts: list[Ref[Artifact]] = Field(default_factory=list)
```

This allows the app to own **relationship/context membership** while storage owns the target entities and bytes.

---

## 🧩 Problems this solves

### 1. Avoids local mirror rows

Without location-transparent refs, generated local relationships tend to force app-local mirror rows:

```text
storage.db artifacts.id = 42   # canonical storage-owned Artifact
app.db     artifacts.id = 7    # local mirror only, for FK compatibility
```

That creates duplicate identity, drift risk, and unclear authority.

With `list[Ref[Artifact]]`, the app can store the canonical remote identity directly:

```json
"artifacts": ["http://storage:7100/Artifact/42"]
```

### 2. Preserves storage authority

For the Gaussian Splat Capture Portal, the storage node should own:

```text
File metadata rows
FileStore bytes
Artifact metadata rows
Artifact download routes
canonical File/Artifact $id values
```

The app should own:

```text
User-facing Media
Run lifecycle state
which Files belong to a Media capture
which Artifacts belong to a Run
```

Location-transparent refs express this boundary cleanly.

### 3. Moves local-vs-remote branching out of domain code

Without framework-level refs, app code tends toward:

```python
if is_remote(value):
    call_storage(value)
else:
    File.get(id)
```

Target code should be:

```python
file = await ref.resolve()
```

Routing belongs in Matrix and remote actor aliases.

### 4. Keeps schema semantics richer than `list[str]`

This field:

```python
files: list[Ref[File]]
```

is semantically different from:

```python
files: list[str]
```

It tells schema consumers, UI components, agents, and tools:

```text
This is a collection of File references, not arbitrary strings.
```

---

## 📍 Existing app-local tracer bullet available to N3TX team

The Gaussian Splat Capture Portal already includes a local prototype under:

```text
modules/n3tx_ext/
```

These files will be made available to the N3TX team. Treat them as implementation evidence and a behavioral tracer bullet, not as the final framework API.

### Existing files

```text
modules/n3tx_ext/
  remote_actors.py
  service_bootstrap.py
  file_mirror.py
```

### `remote_actors.py`

Provides a `RemoteActorAlias` Matrix child that forwards ordinary actor TX traffic to another N3TX HTTP node.

Intent already proven:

```text
Domain code keeps targeting normal actor addresses:
  files
  artifacts
  compute_pipeline

The local Matrix decides whether those addresses are local actors or remote aliases.
```

Representative registration:

```python
register_remote_actor_alias(
    local_addr="artifacts",
    remote_base_url=os.environ["SPLAT_STORAGE_URL"],
    remote_addr="artifacts",
    class_name="Artifact",
)
```

Current TX-to-HTTP translation shape:

| TX name | Remote HTTP route |
| --- | --- |
| `schema` | `GET /{ClassName}` |
| `list` | `GET /{remote_addr}` |
| `get` | `GET /{remote_addr}/{id}` |
| `create` | `POST /{remote_addr}` |
| `update` | `PUT /{remote_addr}/{id}` |
| `delete` | `DELETE /{remote_addr}/{id}` |
| instance method | `POST /{remote_addr}/{id}/{method}` |
| class method | `POST /{remote_addr}/{method}` |

Framework ask: absorb this into a general N3TX remote actor alias / network routing primitive so `Ref.resolve()` can route through Matrix instead of direct HTTP clients.

### `service_bootstrap.py`

Provides env-driven alias registration:

```python
configure_remote_aliases(node="app")
configure_remote_aliases(node="compute")
```

Current deployment mapping:

```text
SPLAT_STORAGE_URL -> files, artifacts
SPLAT_COMPUTE_URL -> compute_pipeline
SPLAT_INTERNAL_TOKEN -> forwarded x-access-token
```

Current behavior:

```text
app:
  files            -> storage
  artifacts        -> storage
  compute_pipeline -> compute

compute:
  files     -> storage
  artifacts -> storage
```

Framework ask: support distributed service bootstrap where Matrix children can be local actors or remote aliases based on configuration.

### `file_mirror.py`

Provides compute-side File materialization:

```python
local_path = await materialize_file(
    {"$id": "http://storage:7100/File/12", "filename": "capture.jpg"},
    cache_dir=paths.uploads,
)
```

Current behavior:

```text
File ref/payload
  -> derive download URL
  -> GET storage /files/{id}/download
  -> write bytes into compute-local scratch/cache
  -> return local Path
```

Framework ask: generalize this so file materialization can consume `Ref[File]` and route through the file capability/Matrix.

---

## 🧠 Current behavior that must remain compatible

Current N3TX and app code already use URL strings as local refs.

Example from referral behavior:

```python
child.referred_by_id = "http://localhost:7000/User/1"
child.referred_by_id = "http://localhost:7000/users/1"
```

Those must remain local references to user id `1` when the URL origin matches the current API origin.

Therefore the new rule must **not** be “URL means remote.”

Safe additive classification:

| Input value | Meaning |
| --- | --- |
| `12` | local ref to id 12 |
| `"12"` | local ref to id 12 |
| `"/File/12"` | local ref to File 12 |
| `"http://localhost:7000/File/12"` | local ref if same origin as `config.API_URL` |
| `"http://storage:7100/File/12"` | remote ref if foreign origin / registered alias |
| `"n3tx://storage/File/12"` | remote named Matrix-node ref |

The distinction is:

```text
same-origin or relative identity -> local
foreign-origin or named node identity -> Matrix-routed remote
```

---

## 🏗️ Proposed framework implementation

### Phase 1 — Reference identity parsing and preservation

Add an internal value object, likely in `n3tx_core.utils.typer` or adjacent module:

```python
@dataclass(frozen=True)
class RefIdentity:
    raw: str | int
    model_name: str | None
    table_name: str | None
    object_id: str | int
    origin: str | None
    is_remote: bool
    actor_addr: str
```

Parsing examples:

```text
12
  -> object_id=12, origin=None, is_remote=False

"/File/12"
  -> model_name=File, object_id=12, origin=None, is_remote=False

"http://localhost:7000/File/12"
  -> same-origin local when config.API_URL matches

"http://storage:7100/File/12"
  -> foreign-origin remote

"n3tx://storage/File/12"
  -> remote named Matrix node
```

### Phase 2 — Update `Ref[T]` without breaking integer refs

Target shape:

```python
class Ref(Generic[T]):
    def __init__(self, value=None):
        self.identity = parse_ref_identity(value, target_type=T)

    @property
    def id(self):
        return self.identity.object_id

    @property
    def href(self):
        return canonical_ref_href(self.identity)

    async def resolve(self, user=None) -> T:
        return await resolve_ref(self, user=user)
```

Backward compatibility requirements:

```python
int(Ref[User](1)) == 1
Ref[User]({"id": 1}).id == 1
Ref[User]("http://localhost:7000/User/1") remains local when same-origin
```

For remote refs, do **not** discard origin during validation, dump, storage, or serialization.

### Phase 3 — Matrix-backed resolution

Add framework-level resolution along these lines:

```python
async def resolve_ref(ref: Ref[T], *, user=None) -> T:
    identity = ref.identity

    tx = TX(
        name="get",
        source="ref_resolver",
        target=identity.actor_addr,
        data={"id": identity.object_id},
        meta={"user": user},
    )

    result = await matrix.request(tx)
    return ref.target_type(**result)
```

Important: `Ref` should not own direct HTTP logic. Remote HTTP forwarding should be implemented by Matrix child aliases / network adapters.

Target routing:

```text
Ref[File]("/File/12").resolve()
  -> TX(name="get", target="files", data={"id": 12})
  -> local File actor or local storage

Ref[File]("http://storage:7100/File/12").resolve()
  -> TX(name="get", target="files", data={"id": 12}, meta={origin: storage})
  -> Matrix alias routes to storage
```

The exact target addressing is up to the N3TX team, but domain code should not branch on local vs remote.

### Phase 4 — Store `list[Ref[T]]` as JSON membership lists

For fields like:

```python
files: list[Ref[File]] = Field(default_factory=list)
```

SQLite should store a JSON list:

```json
[
  "http://storage:7100/File/12",
  "http://storage:7100/File/13"
]
```

This should **not** be treated as a `ListRef[T]` child collection or `ManyToMany[T]` generated join table.

Semantics:

```text
Parent owns membership/context.
Target entity lifecycle belongs wherever the Ref resolves.
```

### Phase 5 — Schema metadata for references

For:

```python
media: Ref[Media]
```

Schema should expose something like:

```json
{
  "type": "string",
  "format": "n3tx-ref",
  "x-n3tx-ref": {
    "model": "Media",
    "resolve": "matrix",
    "remote": true
  }
}
```

For:

```python
files: list[Ref[File]]
```

Schema should expose:

```json
{
  "type": "array",
  "items": {
    "type": "string",
    "format": "n3tx-ref",
    "x-n3tx-ref": {
      "model": "File",
      "resolve": "matrix",
      "remote": true
    }
  }
}
```

This is essential so schema-driven UI, agents, and tooling know these are model references, not arbitrary strings.

### Phase 6 — Populate and hydration behavior

Current local ref population should continue to work.

For remote refs:

```text
Default read:
  return raw refs; do not require remote service availability.

Explicit populate:
  resolve through Matrix; return populated payloads when available.
```

Suggested shape:

```text
GET /media/1
  -> files: ["http://storage:7100/File/12"]

GET /media/1?populate=files
  -> files: {
       "refs": ["http://storage:7100/File/12"],
       "data": [{...remote File payload...}],
       "meta": {...}
     }
```

Remote availability should not be required for ordinary entity reads.

### Phase 7 — File materialization integration

Generalize the app-local `modules/n3tx_ext/file_mirror.py` behavior into the file capability.

Target ergonomic API:

```python
file_ref: Ref[File] = "http://storage:7100/File/12"

local_path = await file_ref.materialize(cache_dir=paths.uploads)
```

or:

```python
file = await file_ref.resolve()
local_path = await file.ensure_local()
```

The N3TX team can choose the final API, but it should preserve the same boundary:

```text
File metadata resolves through Matrix.
Bytes materialize through File/FileStore download or provider semantics.
Compute code receives a local Path.
```

---

## 🔐 Compatibility and non-goals

### Must preserve

- `Ref[T]` with integer IDs.
- `Ref[T]` with numeric strings where currently supported.
- Same-origin absolute URL refs as local refs.
- Relative local refs such as `/File/12`.
- Existing `ListRef[T]` parent-child behavior.
- Existing `ManyToMany[T]` local join-model behavior.

### Explicit non-goals for first pass

- Do not redefine `ListRef[T]` globally.
- Do not make every URL remote.
- Do not require remote services for basic reads.
- Do not add app-specific storage/client logic to `Ref[T]`.
- Do not make `n3tx-core` depend on `n3tx-files`; file materialization should remain optional/package-level.

---

## 🧪 Suggested N3TX test plan

### Unit tests — `Ref[T]` parsing

Cases:

```python
Ref[File](12)
Ref[File]("12")
Ref[File]("/File/12")
Ref[File]("http://localhost:7000/File/12")
Ref[File]("http://storage:7100/File/12")
Ref[File]("n3tx://storage/File/12")
```

Assert:

- target model preserved
- object ID parsed
- local vs remote classification correct
- same-origin URL remains local
- remote origin is preserved during serialization

### Backward compatibility tests

```python
int(Ref[User](1)) == 1
Ref[User]({"id": 1}).id == 1
Ref[User]("http://localhost:7000/User/1") behaves like local user id 1
```

Existing referral-style tests should keep passing.

### Storage tests — `list[Ref[T]]`

Given:

```python
class Capture(ActorModel):
    __tablename__ = "captures"
    __storable__ = True
    files: list[Ref[File]] = Field(default_factory=list)
```

Assert:

- migration creates `files TEXT`
- create stores JSON list of refs
- read returns list of refs/address values
- no local `File` row is required
- no join table is generated

### Matrix resolution tests

Local case:

```text
matrix child "files" = local File actor
await Ref[File]("/File/12").resolve()
```

Remote case:

```text
matrix child "files" = RemoteActorAlias(storage)
await Ref[File]("http://storage:7100/File/12").resolve()
```

Assert TX reaches the expected actor/alias.

### Populate tests

- Local refs populate locally.
- Remote refs populate through Matrix when explicitly requested.
- Basic reads return raw refs even when remote service is unavailable.

### File materialization tests

- `Ref[File]` can materialize a remote File into a local temp/cache path.
- Materialization preserves filename safety checks.
- Materialization forwards internal auth token/metadata through the configured file/remote route.

---

## 📦 Suggested delivery phases

| Phase | Deliverable | Acceptance |
| --- | --- | --- |
| 1 | Ref identity parsing/preservation | local refs unchanged; remote origin not discarded |
| 2 | `list[Ref[T]]` JSON storage | JSON list roundtrips without local target rows |
| 3 | Matrix-backed `Ref.resolve()` | local and remote refs route through Matrix |
| 4 | Schema metadata | `format: n3tx-ref` + target model metadata appears |
| 5 | Populate integration | explicit populate resolves local/remote refs |
| 6 | File materialization | `Ref[File]` can become local `Path` through file capability |

---

## 🧭 Impact on Gaussian Splat Capture Portal

Once this exists, our app can replace local mirror-row plans with direct refs:

```python
class Media(ActorModel):
    files: list[Ref[File]] = Field(default_factory=list)


class Run(ActorModel):
    artifacts: list[Ref[Artifact]] = Field(default_factory=list)
```

Upload result:

```json
{
  "files": ["http://storage:7100/File/12"]
}
```

Compute result:

```json
{
  "artifacts": ["http://storage:7100/Artifact/42"]
}
```

Benefits:

- No app-local `File` rows for storage-owned uploads.
- No app-local `Artifact` rows for storage-owned outputs.
- No mirror synchronization.
- No DTO-only artifact model.
- No domain-code branching between local and remote.
- Storage remains the byte and artifact authority.
- App keeps schema-visible `Media` and `Run` relationship/context fields.

---

## ✅ Final ask to N3TX team

Please implement **location-transparent `Ref[T]`** as the canonical N3TX primitive for model/actor references across local and remote nodes.

Core requirement:

```text
A Ref stores actor identity.
Ref resolution goes through Matrix.
Local vs remote is determined by origin/alias/Matrix routing, not app domain code.
```

Initial target API:

```python
files: list[Ref[File]]
artifacts: list[Ref[Artifact]]
```

Initial serialized target:

```json
{
  "files": ["http://storage:7100/File/12"],
  "artifacts": ["http://storage:7100/Artifact/42"]
}
```

Use `modules/n3tx_ext/remote_actors.py`, `modules/n3tx_ext/service_bootstrap.py`, and `modules/n3tx_ext/file_mirror.py` from the Gaussian Splat Capture Portal as concrete implementation evidence for remote Matrix aliases and File materialization.

---

## 📍 Likely framework files to touch

- `packages/n3tx-core/src/n3tx_core/utils/typer.py`
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`
- `packages/n3tx-actors/src/n3tx_actors/matrix.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py`
- `packages/n3tx-files/src/n3tx_files/file.py`
- `packages/n3tx-files/src/n3tx_files/materialize.py`
