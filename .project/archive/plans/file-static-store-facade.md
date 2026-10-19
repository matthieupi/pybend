# File Static Store Facade Plan

✅ **Recommendation:** make `File` the primary byte-store facade through explicit class/static APIs, but do **not** remove the provider seam yet. Keep `FileStore`, `LocalFileStore`, `FileStat`, `configure_file_store()`, and `get_file_store()` as compatibility exports while routing them through `File`.

This gives the ergonomics the user wants — app code can mostly say `File.configure_local_store(...)`, `File.store()`, `File.put_stream(...)`, `File.open_stream(...)` — without breaking the current tests, docs, route flow, or future S3/R2/CDN provider strategy.

## 📍 Current state

`n3tx-files` currently has a three-part split:

```text
File(ActorModel) metadata row
  +-- schema/auth/routes/materialization
  +-- fields: filename, content_type, size, sha256, storage_key, ...

FileStore protocol
  +-- put_stream(source) -> FileStat
  +-- open_stream(key, range) -> AsyncIterator[bytes]
  +-- stat(key), delete(key)

LocalFileStore implementation
  +-- filesystem-backed provider
  +-- checksum-derived keys
  +-- path traversal protection
```

Critical runtime paths today:

- `packages/n3tx-files/src/n3tx_files/file.py`
  - Owns `_file_store`, `configure_file_store()`, `get_file_store()`.
  - `File.ensure_local()` requires `LocalFileStore.path_for()`.
- `packages/n3tx-files/src/n3tx_files/store.py`
  - Defines `FileStat`, `FileStore`, `LocalFileStore`.
- `packages/n3tx-files/src/n3tx_files/routes.py`
  - Upload calls `get_file_store().put_stream(...)`.
  - Download calls `get_file_store().open_stream(...)`.
- Tests directly instantiate `LocalFileStore` and assert range reads, stats, checksum keys, and path-safety behavior.

## 🎯 Target state

Make `File` the ergonomic public surface:

```python
from n3tx_files import File

File.configure_local_store("./file-blobs")

stat = await File.put_stream(upload, meta={"content_type": "application/pdf"})
stream = File.open_stream(file.storage_key, start=0, end=1023)
local = await file.ensure_local()
```

Keep current compatibility:

```python
from n3tx_files import File, LocalFileStore, configure_file_store

configure_file_store(LocalFileStore("./file-blobs"))
```

The mental model becomes:

```text
Application code
  |
  v
File class/static facade  <---- compatibility module functions
  |
  v
Configured provider       <---- LocalFileStore now, S3/R2/CDN later
  |
  v
Blob bytes
```

## 📊 Design options

| Option | Shape | Pros | Cons | Recommendation |
|---|---|---|---|---|
| A. Remove `FileStore`/`LocalFileStore` | Put all byte logic directly on `File` | Fewest names | Breaks public API, tests, docs, provider extensibility | ❌ No |
| B. `File` as facade over providers | Add `File.store()`, `File.configure_store()`, `File.configure_local_store()`, byte classmethods | Ergonomic, compatible, keeps CDN seam | Slightly more names during migration | ✅ Yes |
| C. Alias `LocalFileStore = File` | Make `File` pretend to be both model and provider | Superficial simplification | Confuses metadata CRUD with blob IO; MRO/name collision risk | ❌ No |

## 🧩 Implementation slices

### Slice 1 — Add `File` class-level store facade

Change `packages/n3tx-files/src/n3tx_files/file.py`.

Add class/static methods to `File` that own the public byte-store facade:

```python
class File(ActorModel):
    ...

    @classmethod
    def configure_store(cls, store: FileStore) -> None:
        global _file_store
        _file_store = store

    @classmethod
    def configure_local_store(cls, root: str | os.PathLike = FILE_STORE_DIR) -> LocalFileStore:
        store = LocalFileStore(root)
        cls.configure_store(store)
        return store

    @classmethod
    def store(cls) -> FileStore:
        return get_file_store()

    @classmethod
    async def put_stream(cls, source, *, key: str | None = None, meta: dict | None = None) -> FileStat:
        return await cls.store().put_stream(source, key=key, meta=meta)

    @classmethod
    def open_stream(cls, key: str, *, start: int | None = None, end: int | None = None):
        return cls.store().open_stream(key, start=start, end=end)

    @classmethod
    async def stat_blob(cls, key: str) -> FileStat:
        return await cls.store().stat(key)

    @classmethod
    async def delete_blob(cls, key: str) -> None:
        await cls.store().delete(key)
```

⚠️ Use `stat_blob` / `delete_blob`, not `stat` / `delete`, to avoid collisions with model/storage semantics and future CRUD expectations.

### Slice 2 — Route old module functions through `File`

Keep imports stable, but make old functions wrappers:

```python
def configure_file_store(store: FileStore) -> None:
    File.configure_store(store)

def get_file_store() -> FileStore:
    global _file_store
    if _file_store is None:
        _file_store = LocalFileStore(FILE_STORE_DIR)
    return _file_store
```

Because `configure_file_store()` is defined before `File` today, either:

1. Move `configure_file_store()` below the `File` class, or
2. Keep it above and have it mutate `_file_store` directly, while `File.configure_store()` delegates to it.

✅ Prefer option 2 for a smaller diff:

```python
def configure_file_store(store: FileStore) -> None:
    global _file_store
    _file_store = store

class File(ActorModel):
    @classmethod
    def configure_store(cls, store: FileStore) -> None:
        configure_file_store(store)
```

### Slice 3 — Update upload/download routes to use the facade

Change `packages/n3tx-files/src/n3tx_files/routes.py` from module store access to model facade access.

Pseudo-diff:

```diff
- from .file import File, get_file_store
+ from .file import File

- stat = await get_file_store().put_stream(...)
+ stat = await file_model.put_stream(...)

- get_file_store().open_stream(file.storage_key, start=start, end=end)
+ file_model.open_stream(file.storage_key, start=start, end=end)
```

This reinforces that routes delegate to the `File` model capability, not directly to a global provider.

### Slice 4 — Add tests for the new facade, preserve old tests

Extend `packages/n3tx-files/src/n3tx_files/tests/test_store.py` or add a small test in `test_file_model.py`:

```python
async def test_file_class_facade_configures_and_uses_local_store(tmp_path):
    store = File.configure_local_store(tmp_path / "blobs")

    stat = await File.put_stream(b"hello", meta={"content_type": "text/plain"})

    assert isinstance(store, LocalFileStore)
    assert stat.size == 5
    assert b"".join([chunk async for chunk in File.open_stream(stat.key)]) == b"hello"
```

Also keep existing tests for:

- `LocalFileStore` direct behavior.
- `configure_file_store(LocalFileStore(...))` compatibility.
- Upload/download route behavior.
- `ensure_local()` behavior.

### Slice 5 — Documentation cleanup toward `File`-first API

Update docs to show `File` as the normal surface and provider classes as advanced/customization API.

Docs to update:

- `packages/n3tx-files/README.md`
- `packages/n3tx-files/docs/file.md`
- `docs/ARCHITECTURE.md`
- `docs/CORE.md`
- `docs/MODELS.md`
- `BACKEND.md`
- Root/package READMEs if they list public API names.

Example docs direction:

```python
from n3tx_files import File

File.configure_local_store("./file-blobs")
app = create_app(models=[File], storage="sqlite:///app.db")
```

Advanced provider docs remain:

```python
from n3tx_files import File, LocalFileStore

File.configure_store(LocalFileStore("./file-blobs"))
```

## ⚠️ Risks and guardrails

| Risk | Mitigation |
|---|---|
| Confusing model CRUD with byte IO | Use explicit blob/stream names; do not overload `File.create()`, `File.get()`, or `File.delete()` |
| Breaking existing imports | Keep `FileStore`, `LocalFileStore`, `FileStat`, `configure_file_store`, `get_file_store` exported |
| Losing provider extensibility | Keep protocol/strategy seam internally and publicly for advanced providers |
| Making `File` too magical | Keep methods explicit: `configure_store`, `configure_local_store`, `put_stream`, `open_stream` |
| Remote/CDN future blocked | Keep provider interface unchanged; facade only delegates |

## 🧪 Verification

Run when implementation is done:

```bash
python3 scripts/test-backend.py --suite files -- -q
python3 scripts/test-backend.py --short
```

If frontend/docs package surfaces changed, also inspect package exports:

```bash
python3 - <<'PY'
from n3tx_files import File, FileStore, FileStat, LocalFileStore, configure_file_store, get_file_store
print(File, FileStore, FileStat, LocalFileStore, configure_file_store, get_file_store)
PY
```

## ✨ Next steps

1. Implement the additive `File` facade first.
2. Rewire routes to call `file_model` byte methods.
3. Add facade tests while preserving compatibility tests.
4. Update docs to show the `File`-first API.
5. Only later, after a release cycle, consider whether `configure_file_store()` should be documented as legacy.

## Critical Files for Implementation

- `packages/n3tx-files/src/n3tx_files/file.py`
- `packages/n3tx-files/src/n3tx_files/routes.py`
- `packages/n3tx-files/src/n3tx_files/store.py`
- `packages/n3tx-files/src/n3tx_files/tests/test_store.py`
- `packages/n3tx-files/docs/file.md`

## Saved Plan

- `.project/plans/file-static-store-facade.md`
