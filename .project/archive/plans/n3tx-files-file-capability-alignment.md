# N3TX Files Alignment Plan: Make `File` the Public Capability

✅ **Recommendation**: keep `FileStore` as a small internal byte-provider strategy, but make `File(ActorModel)` the single N3TX-facing file capability.

The goal is not to add abstraction. The goal is to **remove provider mechanics from routes and callers** so application code speaks in N3TX terms:

```python
created = await File.create_from_stream(upload, filename="audio.wav", user=user)
stream = created.open_stream(start=0, end=1023)
local = await created.ensure_local()
resolved = await File.resolve("/File/1", user=user)
```

`FileStore` remains useful only as an internal strategy for local, remote-node, S3/R2/GCS, or CDN-backed bytes.

---

## 1. Problem Statement

`n3tx-files` already has the right high-level model:

```text
File(ActorModel)       -> metadata, schema, auth, actor/tool visibility
FileStore provider     -> byte persistence implementation
routes.py              -> multipart/binary HTTP adapters
materialize.py         -> File-typed method argument resolution
```

But some behavior currently leaks provider mechanics into route glue:

- `routes.py` calls `get_file_store().put_stream(...)` directly during upload.
- `routes.py` calls `get_file_store().open_stream(file.storage_key, ...)` during download.
- `File.ensure_local()` checks `isinstance(store, LocalFileStore)`, making local storage a special case inside the model.
- Distributed/remote storage should be accessible through `File` behavior, not app-specific gateway glue.

This makes `FileStore` feel like a parallel concept instead of a hidden provider strategy behind the `File` resource.

---

## 2. N3TX Alignment Goal

Make `File` the N3TX-native source of truth for file behavior while preserving explicit byte routes for protocol-specific IO.

```text
HTTP multipart/binary route
        |
        v
File class/instance capability
        |
        v
FileStore provider strategy
```

### Boundary Rule

> Application code, routes, agents, and typed method callers should speak to `File`. Only `File` internals, provider implementations, and provider tests should speak directly to `FileStore`.

---

## 3. Proposed Architecture

### Public N3TX primitive: `File`

`packages/n3tx-files/src/n3tx_files/file.py`

Add or refine `File` methods so they express file intent:

```python
class File(ActorModel):
    @classmethod
    async def create_from_stream(
        cls,
        source,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        user: dict | None = None,
        meta: dict | None = None,
    ) -> "File":
        """Store bytes and create the corresponding File metadata record."""

    def open_stream(
        self,
        *,
        start: int | None = None,
        end: int | None = None,
    ):
        """Open this file's bytes through the configured provider."""

    async def ensure_local(self, user=None) -> dict:
        """Return or create a local projection for consumers requiring a path."""
```

Keep existing N3TX-visible behavior:

```python
@classmethod
@expose_route("/resolve", methods=["POST"])
async def resolve(cls, address: str, user=None): ...
```

### Internal provider strategy: `FileStore`

`packages/n3tx-files/src/n3tx_files/store.py`

Keep the provider protocol small:

```python
class FileStore(Protocol):
    async def put_stream(...): ...
    def open_stream(...): ...
    async def stat(...): ...
    async def delete(...): ...
```

Add an optional local projection capability instead of checking concrete provider classes:

```python
class SupportsLocalPath(Protocol):
    def local_path(self, key: str) -> Path | None: ...
```

or equivalent minimal method naming.

### Thin protocol adapters: routes

`packages/n3tx-files/src/n3tx_files/routes.py`

Routes should keep HTTP-specific work:

- multipart extraction
- Range header parsing
- HTTP status/header construction
- `StreamingResponse`
- request user extraction and route-level authorization

Routes should delegate file behavior:

```python
created = await file_model.create_from_stream(
    upload,
    filename=upload.filename,
    content_type=upload.content_type,
    user=user,
)

return StreamingResponse(
    file.open_stream(start=start, end=end),
    ...
)
```

---

## 4. Why Not Remove `FileStore`?

Removing `FileStore` and putting byte behavior directly on `File` would initially look simpler:

```python
class File(ActorModel):
    @classmethod
    async def put_stream(cls, source): ...
    @classmethod
    def open_stream(cls, key): ...
```

But over time `File` would accumulate provider-specific mechanics:

- local filesystem paths
- checksum/chunk writes
- remote node clients
- S3/R2/GCS SDK calls
- signed URLs
- CDN projection
- retry/backoff/cache behavior

That makes `File` a mixed resource/provider/client object. The more N3TX-native shape is:

| Concern | Owner |
|---|---|
| Metadata/schema/auth/resource identity | `File` |
| File lifecycle intent | `File` |
| Multipart/binary HTTP protocol details | `routes.py` |
| Byte persistence mechanics | `FileStore` provider |
| Local/remote/cloud specifics | Provider implementation |
| Typed method argument resolution | `materialize.py` + `File.resolve()` |

---

## 5. Implementation Sequence

### Step 1 — Move upload lifecycle into `File.create_from_stream()`

Files:

- `packages/n3tx-files/src/n3tx_files/file.py`
- `packages/n3tx-files/src/n3tx_files/routes.py`
- `packages/n3tx-files/src/n3tx_files/tests/test_routes.py`
- new or existing model-level test file for `File.create_from_stream()`

Work:

1. Add `File.create_from_stream(...)`.
2. Move metadata construction from `routes.py` into that method.
3. Keep route authorization and HTTP error translation in `routes.py`.
4. Add direct tests for the class method.
5. Preserve existing upload route behavior.

### Step 2 — Move byte opening behind `file.open_stream()`

Files:

- `packages/n3tx-files/src/n3tx_files/file.py`
- `packages/n3tx-files/src/n3tx_files/routes.py`
- `packages/n3tx-files/src/n3tx_files/tests/test_routes.py`

Work:

1. Add `File.open_stream(start=None, end=None)`.
2. Replace direct `get_file_store().open_stream(file.storage_key, ...)` route call.
3. Keep range parsing and response header logic in `routes.py`.
4. Verify full and partial download tests still pass.

### Step 3 — Replace `ensure_local()` concrete store check with provider capability

Files:

- `packages/n3tx-files/src/n3tx_files/file.py`
- `packages/n3tx-files/src/n3tx_files/store.py`
- tests for `ensure_local()` behavior

Work:

1. Add a small optional local projection capability to the provider layer.
2. Implement it for `LocalFileStore`.
3. Update `File.ensure_local()` to use capability detection instead of `isinstance(LocalFileStore)`.
4. Add tests for supported and unsupported stores.

### Step 4 — Make remote storage accessible through `File`

Files:

- `packages/n3tx-files/src/n3tx_files/store.py` or new provider module
- distributed-node tests
- `packages/n3tx-files/docs/file.md`

Work:

1. Introduce a remote provider such as `RemoteFileStore` / `N3TXFileNodeStore` when needed.
2. Ensure the app still calls `File.create_from_stream()`, `File.resolve()`, and `file.open_stream()`.
3. Hide remote upload/download mechanics behind the provider.
4. Update distributed tests to configure the provider rather than define app-specific gateway flows.

### Step 5 — Clarify deletion lifecycle semantics

Files:

- `packages/n3tx-files/src/n3tx_files/file.py`
- `packages/n3tx-files/src/n3tx_files/store.py`
- `packages/n3tx-files/docs/file.md`
- lifecycle tests if behavior changes

Work:

1. Decide whether metadata deletion should delete bytes automatically.
2. If storage keys can be shared/content-addressed, prefer explicit blob cleanup or documented GC.
3. If not shared, consider a clear `File.delete_blob()` or model-level lifecycle hook.
4. Document the contract.

---

## 6. Compatibility Notes

- Keep existing public routes:
  - `POST /files/upload`
  - `GET /files/{id}/download`
  - `GET /File/{id}/download`
- Keep `configure_file_store(...)` for now.
- Keep `File.resolve(...)` address semantics:
  - `n3tx://files/{id}`
  - `/files/{id}`
  - `/File/{id}`
- Keep typed materialization behavior unchanged.
- Do not move multipart/binary IO into normal JSON `@expose_route` methods yet.

---

## 7. Test Strategy

Run targeted file tests first:

```bash
cd /workspace && python3 scripts/test-backend.py --suite files -- -q
```

Recommended coverage:

| Area | Test intent |
|---|---|
| `File.create_from_stream()` | Stores bytes and creates correct metadata |
| Upload route | Still returns metadata response and persists bytes |
| `file.open_stream()` | Delegates byte reads through provider |
| Download route | Full/range download behavior unchanged |
| `ensure_local()` | Uses provider capability, no concrete class check |
| Materialization | `File` annotations still resolve addresses |
| Distributed storage | Remote/provider implementation remains accessible through `File` |

Broader verification after implementation:

```bash
cd /workspace && python3 scripts/test-backend.py --short
```

---

## 8. Risks and Open Questions

| Risk / Question | Notes |
|---|---|
| Multipart/binary routes are still explicit | Acceptable today; N3TX method routes are JSON-oriented. |
| Global provider state | `configure_file_store()` is process-wide; may need app-scoped provider later. |
| Remote auth delegation | Remote provider needs clear service-token/user-token behavior. |
| Blob deletion semantics | Need to decide GC vs automatic delete vs explicit cleanup. |
| Shared content-addressed blobs | Automatic delete can be unsafe if multiple rows share a key. |
| Provider protocol growth | Keep `FileStore` small; do not let it become a parallel framework. |

---

## 9. Small Reviewable Implementation Steps

1. Add `File.create_from_stream()` and update upload route.
2. Add `File.open_stream()` and update download route.
3. Add provider local projection capability and update `ensure_local()`.
4. Update tests around model-level file behavior.
5. Update `packages/n3tx-files/docs/file.md` to state the boundary rule.
6. Optionally introduce remote provider in a separate follow-up PR/slice.

---

## 10. Expected Outcome

After this refactor, the system should feel like:

```text
N3TX application code sees: File
Provider code sees: FileStore
Routes adapt protocols only
```

Expected simplifications:

- Less file lifecycle logic in HTTP route glue.
- Fewer call sites touching `get_file_store()` directly.
- Cleaner support for remote/cloud providers.
- More discoverable file behavior through the `File` model.
- Better alignment with “the model is the app” without forcing binary IO into JSON method routes prematurely.
