# N3TX File Capability Implementation Plan

## ✅ Recommendation

Implement the PRD as an optional **`n3tx-files` package** whose public primitive is `File(ActorModel)`. Keep CDN/object-store behavior behind provider strategies; the first release should make local file storage, metadata CRUD, upload/download, `ensure_local()`, and typed method materialization work end-to-end.

The default path:

1. Add `packages/n3tx-files` as a separate package depending on `n3tx-core` + `n3tx-actors`.
2. Add a deep file module: `File`, `FileStore`, `LocalFileStore`, `ProjectionCache`, address parsing.
3. Add neutral core/actor materialization hooks so `File`-typed method args resolve consistently in direct and actor routing.
4. Add package-local upload/download route adapters only where generated JSON method routes cannot handle multipart/binary responses.
5. Defer remote node providers, signed URLs, and CDN purge until local behavior and route parity are proven.

## 📍 Current State

| Area | Evidence | Implementation implication |
|---|---|---|
| Direct custom methods | `routes_fastapi.py::make_custom_post()` parses JSON body and invokes methods directly | Add shared argument materialization here |
| Actor custom methods | `network_api.py::_parse_method_args()` builds TX payload; `ActorModel.handler()` invokes exposed methods | Hook both HTTP parsing and actor invocation to cover internal TX/tool calls |
| Static assets | `backend.py::_discover_static_dirs()` and `_CascadingStaticFiles` serve unauthenticated runtime assets | Do not use static mounting for user files |
| Optional packages | `n3tx_agents.__init__`, `n3tx_ui.__init__` register extensions at import time | `n3tx_files` should register materializers/schema only when imported |
| Test runner | `scripts/test-backend.py` manually lists suites and package paths | Add `files` suite explicitly |

## 🎯 Target Architecture

```text
Application method / UI / agent tool
        |
        v
   File address or upload
        |
        v
  File(ActorModel)  <---- metadata CRUD/auth/schema/tools
        |
        +--> FileStore provider       (bytes: local/S3/R2/GCS later)
        +--> ProjectionCache          (local path for compute)
        +--> AddressResolver          (n3tx://files/1, /File/1)
        +--> Route adapters           (multipart upload, binary/range download)
```

Package shape:

```text
packages/n3tx-files/
  pyproject.toml
  README.md
  docs/file.md
  src/n3tx_files/
    __init__.py
    file.py
    store.py
    projection.py
    address.py
    materialize.py
    routes.py
    config.py
    tests/
```

## 🧩 Implementation Slices

### Slice 1 — Package skeleton + `File` metadata model

Create `packages/n3tx-files` with setuptools `src/` layout. Export `File`, `FileStore`, and `LocalFileStore` from `n3tx_files.__init__`.

Core model shape:

```python
class File(ActorModel):
    __tablename__ = "files"
    __storable__ = True
    __protected_fields__ = {"user_owner", "storage_key", "sha256", "size"}
    __access__ = {
        "read": ANYONE,
        "create": AUTHENTICATED,
        "update": OWNER | ROLE("admin"),
        "delete": OWNER | ROLE("admin"),
    }

    filename: str
    content_type: str = "application/octet-stream"
    size: int = 0
    sha256: str = ""
    storage_key: str = ""
    origin: str | None = None
    public: bool = False
    user_owner: int | None = None
    meta: dict = Field(default_factory=dict)
```

### Slice 2 — `LocalFileStore`

Implement byte storage outside SQLite. The DB stores metadata only.

```python
class FileStore(Protocol):
    async def put_stream(self, source, *, key: str | None = None, meta: dict | None = None) -> FileStat: ...
    async def open_stream(self, key: str, *, start: int | None = None, end: int | None = None): ...
    async def stat(self, key: str) -> FileStat: ...
    async def delete(self, key: str) -> None: ...
```

Use deterministic content-addressed keys where possible: `sha256[:2]/sha256`.

### Slice 3 — Upload/download route adapters

Generated custom method routes currently expect JSON bodies. Add package-local route registration for multipart upload and binary/range download, but delegate to `File` methods internally.

```python
class File(ActorModel):
    @classmethod
    @expose_route("/upload", methods=["POST"])
    async def upload(cls, upload, user=None) -> "File": ...

    @expose_route("/download", methods=["GET"])
    async def download(self, user=None): ...
```

If needed, `n3tx_files.routes.register_file_routes(router, File)` should mount:

- `POST /files/upload` for `UploadFile`
- `GET /files/{id}/download` and `GET /File/{id}/download` for bytes/ranges

Guardrail: these routes must perform the same resource authorization as N3TX CRUD/method routes before streaming bytes.

### Slice 4 — Local projection cache

Add `ProjectionCache.ensure(file)` so compute libraries can use local paths.

```python
@expose_route("/ensure_local", methods=["POST"])
async def ensure_local(self, user=None) -> dict:
    projection = await projection_cache.ensure(self, store=file_store)
    return {"path": projection.path, "sha256": projection.sha256, "size": projection.size}
```

Rules: verify checksum, share in-flight work per file, expose quota/TTL hooks, never mutate canonical bytes.

### Slice 5 — Address resolution

Implement internal address parsing first:

```text
n3tx://files/{id}
/File/{id}
/files/{id}
```

```python
@classmethod
@expose_route("/resolve", methods=["POST"])
async def resolve(cls, address: str, user=None) -> "File":
    parsed = parse_file_address(address)
    file = cls.get(parsed.id)
    authorize read before returning
    return file
```

External HTTP imports should be disabled by default and require explicit allowlists.

### Slice 6 — Neutral materialization registry

Add a tiny registry to core, then use it in direct and actor invocation.

Proposed core helper:

```python
# n3tx_core/utils/materialize.py
_materializers = []

def register_materializer(fn):
    _materializers.append(fn)
    return fn

async def materialize_arg(value, expected_type, *, user=None, context=None):
    for fn in _materializers:
        changed, new_value = await maybe_await(fn(value, expected_type, user=user, context=context))
        if changed:
            return new_value
    return value
```

`n3tx_files.materialize` registers:

```python
@register_materializer
async def materialize_file(value, expected_type, *, user=None, context=None):
    if expected_type is File and isinstance(value, str):
        return True, await File.resolve(value, user=user)
    if expected_type is File and isinstance(value, dict):
        return True, File.model_validate(value)
    return False, value
```

Hook points:

- `routes_fastapi.py::make_custom_post()` after primitive/Pydantic parsing
- `network_api.py::_parse_method_args()` for HTTP actor requests
- `actor_model.py::ActorModel.handler()` before exposed method invocation for internal TX/tool parity

### Slice 7 — Tests and docs

Add `packages/n3tx-files/src/n3tx_files/tests/` and register the suite in `scripts/test-backend.py`.

Verification matrix:

| Coverage | Required tests |
|---|---|
| Model/schema | `File.schema()`, protected fields, CRUD metadata |
| Store | streaming write/read/stat/delete, checksum, no whole-file loading for large streams |
| Upload/download | auth, content-type, content-length, ETag, 403/404/416, range `206` |
| Projection | deterministic path, checksum verification, repeat/concurrent calls |
| Resolution | valid internal addresses, invalid addresses, unauthorized reads |
| Materialization | `File` args resolve; `str` args untouched; direct/actor/internal TX parity |
| Optional absence | core/actors examples pass without importing `n3tx_files` |

Suggested commands:

```bash
python3 scripts/test-backend.py --suite core -- -q
python3 scripts/test-backend.py --suite actors -- -q
python3 scripts/test-backend.py --suite files -- -q
python3 scripts/test-backend.py --short
```

## ⚠️ Risks and Guardrails

| Risk | Guardrail |
|---|---|
| Static auth bypass | Never serve dynamic user bytes through static catch-all paths |
| Direct/actor divergence | Shared materialization helper + parity tests |
| Hidden IO latency | Only resolve typed `File` args; byte download remains explicit via `ensure_local()`/download |
| SSRF | External URL import disabled unless allowlisted |
| Disk pressure | Projection quotas/TTL/LRU hooks in first projection slice |
| Dependency bloat | Cloud providers only as optional extras |
| Meta-package ambiguity | Keep `n3tx-files` separate initially; add `files` extra later after dependency policy is settled |

## ✨ Next Steps

1. Start with tests for `File.schema()` and `LocalFileStore`.
2. Implement package skeleton and metadata-only `File` model.
3. Add upload/download route adapters with auth tests.
4. Add `ensure_local()` projection.
5. Add neutral materialization registry and parity tests.
6. Only then add remote N3TX node/provider/CDN strategies.

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
- `packages/n3tx-core/src/n3tx_core/api/backend.py`
- `scripts/test-backend.py`

## Saved Plan

- `.project/plans/n3tx-cdn-implementation-plan.md`
