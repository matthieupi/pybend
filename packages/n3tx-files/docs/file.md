# File Capability

`n3tx-files` adds a first-class file resource to N3TX without making the core
framework depend on file storage.

## Architecture

```text
File(ActorModel)
  |-- metadata in N3TX storage
  |-- bytes in FileStore providers
  |-- methods exposed through normal schema/actor tooling
```

The first provider is `LocalFileStore`, which streams bytes to and from a local
filesystem directory while computing checksums.

## App integration

```python
from n3tx_core.app import create_app
from n3tx_files import File, LocalFileStore, configure_file_store

configure_file_store(LocalFileStore('./file-blobs'))

app = create_app(
    models=[File],
    storage='sqlite:///app.db',
)
```

`configure_file_store()` sets the process-wide byte provider used by `File`
methods and routes. If it is not called, `LocalFileStore` uses
`N3TX_FILE_STORE_DIR` or `.n3tx-files/blobs`.

## Routes and methods

`File` uses normal N3TX schema/actor metadata for file records, plus explicit
byte routes for multipart and binary IO:

```text
POST /files/upload          multipart upload -> File metadata response
GET  /files/{id}/download   binary download with optional Range support
GET  /File/{id}/download    class-name download mirror
```

Canonical local File resolution is available through `File.resolve(ref)`, where
`ref` is the File metadata response's absolute `$id`, such as
`http://localhost:5000/File/1`.

External HTTP imports are deliberately not enabled by default.

## Type-driven materialization

Importing `n3tx_files` registers a neutral core materializer for parameters
annotated as `File`:

```python
async def transcribe(audio: File) -> dict:
    local = await audio.ensure_local()
    ...
```

When the payload contains `{"audio": "http://localhost:5000/File/1"}`, direct
and actor routing resolve that URL into an authorized `File` instance before invoking the
method. Plain `str` parameters are not materialized.

## Distributed app/storage nodes

The intended multi-node shape is:

```text
App node                         Storage node
--------                         ------------
Receives workflow/upload   -->   POST /files/upload
Stores/uses returned File        owns File metadata + blob bytes
Later needs bytes          -->   GET /files/{id}/download
Returns/processes stream         streams bytes through FileStore
```

In production this can be implemented by a provider/client that talks to a
remote N3TX file node or object store. The public app code should still deal in
`File` metadata and canonical refs, not provider-specific handles. The test suite
includes a two-node ASGI test that validates upload delegation to a storage node
and later app-node access loading the bytes from that storage node.

## Developer extension points

- `FileStore` providers implement byte storage (`put_stream`, `open_stream`,
  `stat`, `delete`).
- `File.register_extra_routes()` mounts package-owned multipart/binary routes
  through the core/actor-neutral `register_extra_routes` hook.
- `n3tx_files.materialize` registers the `File` typed-argument materializer at
  import time through `n3tx_core.utils.materialize.register_materializer`.
- Future S3/R2/GCS/CDN providers should be optional extras and must preserve the
  same metadata/auth/address contract.

## Guardrails

- Do not store blob bytes in SQLite.
- Do not serve dynamic user files through N3TX static asset mounting.
- Keep cloud/CDN dependencies optional.
- Keep this package absent-by-default; import it only when an app uses files.
- Do not auto-fetch plain strings; only `File`-typed method parameters resolve.
