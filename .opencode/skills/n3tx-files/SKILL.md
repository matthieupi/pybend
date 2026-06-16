---
name: n3tx-files
description: N3TX file capability with n3tx-files, File metadata, FileStore providers, multipart upload, binary/range download, file addresses, and File-typed method materialization. Use when adding user files, blob storage, uploads, downloads, or file arguments.
argument-hint: "<file/upload/blob task>"
---

# N3TX Files

`n3tx-files` adds a first-class file resource without making core depend on
file storage. Files are normal N3TX metadata records; bytes live behind a
`FileStore` provider.

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

If `configure_file_store()` is not called, `LocalFileStore` uses
`N3TX_FILE_STORE_DIR` or `.n3tx-files/blobs`.

## Routes and addresses

Package-owned routes:

```text
POST /files/upload          multipart upload, form field: upload
GET  /files/{id}/download   binary download with optional Range support
GET  /File/{id}/download    class-name download mirror
```

Supported internal addresses:

```text
n3tx://files/{id}
/files/{id}
/File/{id}
```

External HTTP imports are deliberately not enabled by default.

## File-typed materialization

Importing `n3tx_files` registers a typed argument materializer for parameters
annotated as `File`:

```python
from n3tx_files import File


class AudioJob(ActorModel):
    __tablename__ = 'audio_jobs'
    __storable__ = True

    @expose_route('/transcribe', methods=['POST'])
    async def transcribe(self, audio: File) -> dict:
        local = await audio.ensure_local()
        return {'path': str(local)}
```

Payloads like `{"audio": "/File/1"}` resolve to authorized `File` instances
before the method runs. Plain `str` parameters are not materialized.

## Extension points

- `FileStore` providers implement `put_stream`, `open_stream`, `stat`, and `delete`.
- `File.register_extra_routes()` mounts package-owned upload/download routes.
- `n3tx_files.materialize` registers File-typed argument materialization at import time.
- S3/R2/GCS/CDN/remote-node integrations should be optional providers that preserve the same metadata/auth/address contract.

## Guardrails

- Do not store blob bytes in SQLite.
- Do not serve dynamic user files through static asset mounting.
- Keep cloud/CDN dependencies optional.
- Keep this package absent-by-default; import it only when an app uses files.
- Do not auto-fetch plain strings; only `File`-typed method parameters resolve.
- App code should pass `File` metadata or file addresses, not provider-specific handles.

## Verification

- `GET /File` returns the file schema when `File` is registered.
- `POST /files/upload` returns file metadata.
- `GET /files/{id}/download` and `GET /File/{id}/download` stream bytes.
- Range requests return `206` and `Content-Range`.
- `File`-typed method parameters materialize `/File/{id}` or `n3tx://files/{id}`.
- Bytes are written through the configured `FileStore` provider.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
