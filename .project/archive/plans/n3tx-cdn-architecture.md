# N3TX File Capability Architecture Plan

## ✅ Recommendation

Build the CDN capability around a **deep, unified `File(ActorModel)` module** instead of a CDN-first subsystem with separate `FileActor`, `CDNAsset`, resolver, and app-extension concepts.

The public idea should be simple:

> A file is an N3TX model, an actor, a schema contract, a stored metadata record, and a reusable capability.

```python
from n3tx_files import File

class Transcriber(ActorModel):
    __tablename__ = "transcribers"
    __storable__ = False

    @expose_route("/transcribe", methods=["POST"])
    async def transcribe(self, audio: File) -> dict:
        projected = await audio.ensure_local()
        return await transcribe_path(projected.path)
```

CDN behavior then becomes a **deployment/provider strategy of `File`**, not the base abstraction. Out of the box, `File` stores metadata in normal N3TX storage and projects bytes to a local cache. In production, the same model can use S3/R2/GCS, another N3TX file node, or an external CDN in the background.

```text
Other N3TX actor/method
  needs a File
      |
      v
File.resolve(address)  or  automatic File materialization
      |
      +-- local? return projected File
      +-- remote? auth + download/cache/project
      +-- external CDN? fetch/sign/sync behind FileStore
      |
      v
method receives File with .ensure_local(), .open(), .path, metadata
```

This direction preserves the original CDN goals — serving large files, distributed nodes, local resolution for compute, and future CDN integration — while reducing the architecture to one N3TX-native concept.

---

## 🧭 Intent and Philosophy

This plan should be implemented with the following intent, not only the surface API.

### The model is the app

`File` should not be a dumb DTO with a separate manager hidden elsewhere. It should be the authoritative contract for:

- file metadata and validation
- API routes and method schemas
- actor/tool discoverability
- access control
- local projection behavior
- storage/provider policy
- user-visible file identity

### Actors are reusable compute boundaries

File resolution is reusable compute. It should be addressable through Matrix/TX, exposed to agents and MCP tooling, callable from UI and workflows, and inspectable from schema. A unified `File(ActorModel)` gives this automatically.

### Deep module, shallow interface

Files involve hard machinery: streaming, checksums, remote fetches, disk pressure, auth, cache eviction, signed URLs, range requests, and CDN invalidation. That complexity should live inside the `File` module, behind a small interface:

```python
File.resolve(address)
file.ensure_local()
file.open()
file.download()
```

The module should feel pleasant because developers do not have to learn the machinery to use it.

### Transparent, not magical

N3TX already materializes references (`Ref`, `ListRef`, `populate`). File materialization should extend that pattern, but only when the type asks for it. A plain `str` should remain a string. A `File` annotation means “resolve this into a usable file resource.”

```text
str   -> no materialization
File  -> authorized metadata + projected local access when needed
```

### CDN is a strategy, not the primitive

The first primitive is “addressable file resource.” CDN serving, external object storage, edge purge, and remote file nodes are strategies behind that resource. This avoids overfitting the core architecture to one deployment mode.

### Completely modular and additive

The file capability must follow the same package philosophy as `n3tx-ui` and `n3tx-agents`: N3TX must run completely without it. If `n3tx-files` is not installed or imported, core applications, actor routing, schemas, agents, frontend components, and examples must continue to work without warnings, import errors, feature probes, or conditional burden on app developers.

When a developer chooses to use it, the experience should flip from “absent” to “fully integrated”:

```python
import n3tx_files
from n3tx_files import File

app = create_app(models=[File, Job], routing="actor")
```

At that point the package should provide a complete out-of-the-box system:

- `File` model and actor capability
- local filesystem `FileStore` default
- upload, resolve, ensure-local, and download methods
- schema and method metadata
- agent/MCP tool discoverability through normal `@expose_route` methods
- type-driven materialization for `File`-annotated method inputs
- optional static/UI widgets only if the package provides them

Provider features such as S3/R2/GCS, remote N3TX file nodes, signed URLs, or commercial CDN purge should be additive extras. Installing the base package should not force heavy cloud SDK dependencies.

---

## 📍 Current State

| Area | Current behavior | Relevance |
|---|---|---|
| `ActorModel` | Combines model/schema/storage with actor messaging | Perfect home for `File` as data + capability |
| `@expose_route` | Methods become API actions, schema methods, and agent/MCP tools | File operations can be normal model methods |
| References | `Ref`, `ListRef`, href responses, and `populate` already materialize relationships | Strong precedent for type-driven materialization |
| Static files | Framework statics are mounted by `FastAPIBackend`; app statics are explicit routes | Static serving exists, but not dynamic user files |
| Storage | SQLite handles metadata well; not suitable for large blob bytes | Store metadata in DB, bytes in `FileStore` |
| Actors | Matrix routes by address; storable actor instances use `files/{id}` | Natural address shape for file instances |
| Lifecycle | CRUD emits lifecycle events to subscribers | Useful for projection cleanup and CDN purge |

### Key gap

N3TX has no first-class file resource that can:

1. store file metadata as a model,
2. own blob/provider operations,
3. resolve local or remote file addresses,
4. project remote bytes to a local path for compute libraries,
5. expose file operations as actor tools, and
6. serve bytes with correct streaming/cache semantics.

---

## 🎯 Target Architecture

### Public concept

```text
File(ActorModel)
  fields: metadata, storage identity, origin, cache/projection hints
  class actor methods: upload, resolve, import_url
  instance actor methods: ensure_local, open/read, download, purge, refresh
  internals: FileStore, projection cache, fetcher, signer, CDN purge provider
```

### Naming

Use the public name **`File`**.

| Name | Role |
|---|---|
| `File` | Public actor-backed file resource: metadata + methods + materialized capability |
| `FileStore` | Provider interface for blob bytes |
| `LocalFileStore` | Zero-config filesystem byte store |
| `FileProjection` | Local cached projection record/path |
| `FileHandle` | Optional internal stream/path helper returned by `open()` |

Avoid exposing `CDNAsset`, `CDNFile`, or `FileActor` as primary concepts. Those names split what should be one deep module.

### Package shape

Prefer an optional package named `n3tx-files` or `n3tx-filesystem` over `n3tx-cdn` if package naming is still open. If the package must be named `n3tx-cdn`, its primary export should still be `File`.

```text
n3tx_files/
  __init__.py       # exports File, FileStore, LocalFileStore
  file.py           # File(ActorModel)
  store.py          # FileStore providers
  projection.py     # local projection cache
  materialize.py    # type-driven materialization hook
  routes.py         # streaming/range helpers if generated routes are insufficient
  schema_ext.py     # file/cache hints if needed
  providers/
    s3.py
    r2.py
    http.py
    cloudflare.py   # optional purge/signing later
```

Dependency direction should remain acyclic:

```text
n3tx-core
  ↑
n3tx-actors
  ↑
n3tx-files

n3tx meta-package -> may depend on n3tx-files
```

Core must not import `n3tx_files` directly. Integration should happen through neutral extension seams and import-time registration, mirroring existing optional packages:

| Existing package pattern | File capability equivalent |
|---|---|
| `n3tx_agents` imports register `AgentMixin` and schema stages | `n3tx_files` imports register File materializer/schema stages |
| `n3tx_ui` registers mixins through core registries | File package registers only through core/actor-neutral registries |
| Apps must import optional packages before flagged model definitions | Apps import `n3tx_files` before using `File` or file materialization |
| Core keeps running without package installed | Core must not feature-probe or hard import file package |

If a new neutral registry is needed, add the registry to core/actors and let `n3tx_files` register into it. Do not add `try: import n3tx_files` to core bootstrap as the primary integration mechanism.

---

## 🗺️ Flow Design

### Upload flow

```text
POST /files/upload  or  TX(name='upload', target='files')
  -> authenticate user
  -> stream bytes to FileStore.put_stream()
  -> compute sha256, size, content_type
  -> create File metadata row
  -> return File.model_response()
```

### Resolve/materialize flow

```text
address: n3tx://files/42 | /File/42 | https://cdn.example.com/files/42
  -> File.resolve(address)
  -> parse address
  -> enforce access with user context
  -> find or import File metadata
  -> return File instance
  -> ensure_local() downloads/projects bytes only when local access is needed
```

### Method input flow

```text
TX(name='transcribe', data={'audio': 'n3tx://files/42'})
  -> ActorModel.handler()
  -> inspect signature: transcribe(self, audio: File)
  -> materialize only because expected type is File
  -> File.resolve(address, user=tx.meta.user)
  -> method(instance, audio=<File id=42>)
  -> method calls await audio.ensure_local()
```

### Distributed compute/CDN node flow

```text
Compute node                         File/CDN node
------------                         -------------
method gets File address
  |
  v
File.resolve(address)
  |
  +-- remote file node? -----------> GET /File/42 metadata
  |                                  GET /files/42/download or signed URL
  |                                  stream bytes
  v
projection cache writes local path
  |
  v
compute library reads local file path
```

The compute node does not need to know whether the origin is another N3TX server, object storage, or a commercial CDN. It only asks `File` to become usable locally.

---

## 💻 Code Shape Preview

### `File` as the unified component

```python
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.utils.decorators import expose_route


class File(ActorModel):
    __tablename__ = "files"
    __storable__ = True
    __access__ = {
        "read": ANYONE,              # configurable default
        "create": AUTHENTICATED,
        "update": OWNER | ROLE("admin"),
        "delete": OWNER | ROLE("admin"),
    }
    __protected_fields__ = {"user_owner", "storage_key", "sha256", "size"}

    filename: str
    content_type: str = "application/octet-stream"
    size: int = 0
    sha256: str = ""
    storage_key: str = ""
    origin: str | None = None
    public: bool = False
    user_owner: int | None = None
    meta: dict = Field(default={})

    @classmethod
    @expose_route("/resolve", methods=["POST"])
    async def resolve(cls, address: str, user=None) -> "File":
        """Resolve an address into a File record, importing if policy allows."""

    @classmethod
    @expose_route("/upload", methods=["POST"])
    async def upload(cls, file, user=None) -> "File":
        """Create a File from uploaded bytes."""

    @expose_route("/ensure_local", methods=["POST"])
    async def ensure_local(self, user=None) -> dict:
        """Return a projected local path, downloading/caching if needed."""

    @expose_route("/download", methods=["GET"])
    async def download(self, user=None):
        """Stream bytes with cache/range headers."""
```

### FileStore interface

```python
class FileStore(Protocol):
    async def put_stream(self, source, *, key: str | None = None, meta: dict = None) -> FileStat: ...
    async def open_stream(self, key: str, *, start: int | None = None, end: int | None = None): ...
    async def stat(self, key: str) -> FileStat: ...
    async def delete(self, key: str) -> None: ...
    async def sign_url(self, key: str, *, expires: int = 3600) -> str | None: ...
```

### File projection

```python
class FileProjection(BaseModel):
    file_id: int
    path: str
    sha256: str
    size: int
    created_at: datetime
    last_accessed_at: datetime
    source: str
```

Projection rules:

- projection path is deterministic from file ID + checksum when possible,
- concurrent `ensure_local()` calls for the same file share one in-flight download,
- checksum is verified before returning the path,
- cache eviction is explicit and quota-aware,
- projection never mutates canonical metadata except access/cache bookkeeping.

### Type-driven materialization

```python
async def materialize_method_arg(value, expected_type, *, user):
    if expected_type is File and isinstance(value, str):
        return await File.resolve(value, user=user)
    if expected_type is File and isinstance(value, dict):
        return File.model_validate(value)
    return value
```

Materialization should happen in the method invocation layer, not in Matrix itself:

```text
NetworkAPI / direct route parses primitive payload
  -> ActorModel.handler or direct custom route helper sees method type hints
  -> File materialization runs before method call
  -> method receives File
```

This mirrors existing N3TX reference materialization while keeping Matrix as a routing primitive rather than a schema-aware file resolver.

---

## 📊 Architectural Decisions

| Decision | Recommendation | Why |
|---|---|---|
| Base abstraction | `File(ActorModel)` | One model/capability instead of split FileActor + File DTO |
| Public name | `File` | Simple and semantic; module namespace disambiguates from Python handles |
| Package integration | Fully optional, import-registered capability | Core must work without files; using files should feel integrated |
| CDN framing | Provider/deployment strategy | Prevents CDN infrastructure from dominating the developer API |
| Separate `FileActor`? | No | `ActorModel` already unifies entity and actor behavior |
| Blob bytes in DB? | No | DB stores metadata; providers stream bytes |
| Automatic materialization | Yes, but only for `File`-typed args | Consistent with refs while avoiding surprise string fetching |
| Local projection | Built into `File.ensure_local()` | Compute libraries often require real paths |
| Distributed nodes | Resolve through File addresses and remote providers | Compute nodes can project remote files locally |
| External CDN purge | Later lifecycle subscriber/provider | Useful but not needed for first working slice |
| Cloud providers | Optional extras | Base package stays lightweight and useful locally |

---

## ⚖️ Tradeoffs of Unified `File`

### Advantages

| Benefit | Why it matters |
|---|---|
| One concept | Developers learn `File`, not `FileActor` + `CDNAsset` + resolver |
| N3TX-native | Model, schema, routes, storage, actor methods, and tools align |
| Deep module | Hard machinery is hidden behind a small interface |
| Agent-friendly | File methods become tools through existing discovery |
| Distributed-friendly | `File.resolve()` can hide remote node/CDN/provider details |
| Local-path friendly | `ensure_local()` serves libraries that require filesystem paths |
| Extensible | Providers add capability without changing application methods |

### Costs and risks

| Risk | Detail | Guardrail |
|---|---|---|
| Hidden IO latency | A `File` argument may imply remote resolution | Type-gated materialization; `ensure_local()` remains explicit for byte download |
| Disk pressure | Projection cache may grow | Quotas, TTLs, LRU, per-tenant limits |
| SSRF | Remote URL import could fetch private networks | Default deny arbitrary HTTP; require allowlists/providers |
| Auth leaks | Resolution can reveal file existence | Authorize metadata before projection/download |
| Stampede downloads | Many actors resolve the same remote file | Per-file/address in-flight locks |
| Python `File` naming ambiguity | Could be confused with raw handles | Always import from `n3tx_files`; use `FileHandle` internally |
| Method hook complexity | Direct and actor routing both need materialization | Shared helper with parity tests |

---

## 🧩 Implementation Slices

### Slice 1 — Package skeleton and `File` model

Files:
- `packages/n3tx-files/pyproject.toml` or `packages/n3tx-cdn/pyproject.toml`
- `packages/n3tx-files/src/n3tx_files/__init__.py`
- `packages/n3tx-files/src/n3tx_files/file.py`
- `packages/n3tx-files/docs/file.md`

Implement `File(ActorModel)` with metadata fields, access rules, schema visibility, and storable registration. At this stage, bytes can still be handled by a minimal local store.

Package import should perform only safe, additive registration:

```python
# n3tx_files/__init__.py
from .file import File
from .store import FileStore, LocalFileStore
from . import materialize as _materialize  # registers materializer if registry exists
from . import schema_ext as _schema_ext    # registers schema stage if needed

__all__ = ["File", "FileStore", "LocalFileStore"]
```

No application that omits `import n3tx_files` should pay any cost or see any errors.

### Slice 2 — Local `FileStore`

Files:
- `packages/n3tx-files/src/n3tx_files/store.py`
- `packages/n3tx-files/src/n3tx_files/tests/test_store.py`

Implement streaming local filesystem storage with checksum calculation, stat, delete, and open-stream behavior. Avoid loading whole files into memory.

### Slice 3 — Upload and download methods

Files:
- `packages/n3tx-files/src/n3tx_files/file.py`
- `packages/n3tx-files/src/n3tx_files/routes.py` if generated method routes cannot stream uploads/downloads cleanly

Expose `File.upload()` and `file.download()` while preserving N3TX auth, schema, and tool discoverability. If FastAPI `UploadFile` requires a route helper, keep that helper package-local and route to `File` methods internally.

### Slice 4 — Local projection cache

Files:
- `packages/n3tx-files/src/n3tx_files/projection.py`
- `packages/n3tx-files/src/n3tx_files/file.py`

Implement `file.ensure_local()` with deterministic paths, checksum verification, in-flight locking, and simple eviction hooks.

### Slice 5 — Address resolution

Files:
- `packages/n3tx-files/src/n3tx_files/address.py`
- `packages/n3tx-files/src/n3tx_files/file.py`

Support canonical addresses:

```text
n3tx://files/{id}
/File/{id}
http(s)://trusted-file-node/File/{id}
```

Start with internal N3TX addresses. Add external HTTP import only behind explicit config.

### Slice 6 — Type-driven method materialization

Files:
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-files/src/n3tx_files/materialize.py`

Add a package-registered materializer so methods annotated with `File` receive a `File` instance when the payload contains an address. Keep plain strings untouched. Use the same helper in direct and actor routing.

The materialization registry must be neutral and safe when empty:

```text
No n3tx-files installed/imported:
  materializer registry empty
  method parsing behaves exactly as today

n3tx-files imported:
  File materializer registered
  only File-annotated args resolve through File.resolve()
```

### Slice 7 — Distributed file nodes

Files:
- `packages/n3tx-files/src/n3tx_files/providers/http.py`
- `packages/n3tx-files/src/n3tx_files/config.py`

Allow one N3TX node to resolve and project files from another N3TX file node. Preserve auth propagation through existing user/JWT metadata where possible.

### Slice 8 — CDN/cache strategy

Files:
- `packages/n3tx-files/src/n3tx_files/schema_ext.py`
- `packages/n3tx-files/src/n3tx_files/providers/cloudflare.py`

Add cache hints, signed URL support, range headers, and optional lifecycle-event-driven purge. This slice is deliberately later: first make `File` useful locally and across N3TX nodes.

Cloud provider integrations should use optional extras, for example:

```text
n3tx-files              # local store only, zero-config
n3tx-files[s3]          # S3 provider
n3tx-files[r2]          # Cloudflare R2 provider
n3tx-files[gcs]         # Google Cloud Storage provider
n3tx-files[cloudflare]  # purge/signing strategy
```

---

## 🧪 Verification Plan

| Coverage | Tests |
|---|---|
| File model | Schema, CRUD, access rules, protected fields |
| Local store | Stream write/read, checksum, stat, delete, large-file memory behavior |
| Upload/download | Auth, content type, size, ETag, Range, 404/403/416 |
| Projection | `ensure_local()`, checksum verification, repeated calls, concurrent calls, eviction |
| Address resolution | `n3tx://files/{id}`, `/File/{id}`, invalid addresses, unauthorized addresses |
| Materialization | `File`-typed method args resolve; `str` args do not; direct/actor parity |
| Optional absence | Core/apps/tests pass with no `n3tx-files` installed/imported |
| Optional presence | Importing `n3tx_files` registers materialization/schema hooks without extra app glue |
| Distribution | Remote file node metadata + byte projection; auth propagation |
| CDN strategy | Cache headers, signed URLs, purge hooks when enabled |

Suggested commands:

```bash
python3 scripts/test-backend.py --suite core -- -q
python3 scripts/test-backend.py --suite actors -- -q
python3 -m pytest packages/n3tx-files/src/n3tx_files/tests/ -q
python3 scripts/test-backend.py --short
```

---

## ⚠️ Guardrails for the Implementing Team

1. **Do not split `File` and `FileActor` unless a concrete implementation pressure proves the split necessary.** Start with `File(ActorModel)`.
2. **Do not make CDN the first abstraction.** CDN is one provider/deployment strategy behind `File`.
3. **Do not auto-fetch plain strings.** Materialize only typed `File` parameters or explicit `File.resolve(address)` calls.
4. **Do not put blob bytes in SQLite.** Store metadata in N3TX storage, stream bytes through `FileStore`.
5. **Do not bypass actor/schema routes with unrelated FastAPI handlers.** If special upload/download routes are needed, keep them as package-local adapters that call `File` methods and preserve access/schema semantics.
6. **Do not let local projection be unbounded.** Every implementation must have quotas or eviction hooks.
7. **Do not fetch arbitrary external URLs by default.** Remote import requires explicit allowlist/provider configuration.
8. **Keep direct and actor routing behavior aligned.** A method annotated with `File` must behave the same in Level 1/2 and Level 3 routing.
9. **Keep the package absent by default.** No core, actor, UI, or agent module should require `n3tx-files` to import or run.
10. **Make first use delightful.** Once a developer imports/registers `File`, local storage and core file operations should work with minimal or no configuration.

---

## ✨ Next Steps

1. Rename the implementation target from “CDN capability” to “File capability with CDN strategy.”
2. Build the first tracer bullet around `File(ActorModel)` + `LocalFileStore` + `ensure_local()`.
3. Add address resolution for internal N3TX file IDs.
4. Add type-driven materialization only after explicit `File.resolve()` and `ensure_local()` semantics are stable.
5. Add remote node and external CDN providers after local projection is proven.

### Critical Files for Implementation

- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`

### Saved Plan

- `.project/plans/n3tx-cdn-architecture.md`
