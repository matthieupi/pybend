# n3tx-files

Optional N3TX file capability package.

`n3tx-files` provides an actor-backed `File` model for file metadata and a
provider interface for blob bytes. The base package is intentionally local and
lightweight: metadata lives in normal N3TX storage, while bytes live in a
`FileStore` such as `LocalFileStore`.

## Quick start

```python
from n3tx_core.app import create_app
from n3tx_files import File, LocalFileStore, configure_file_store

configure_file_store(LocalFileStore('./file-blobs'))

app = create_app(
    models=[File],
    storage='sqlite:///app.db',
)
```

Upload bytes:

```bash
curl -X POST http://localhost:5000/files/upload \
  -H "x-access-token: $TOKEN" \
  -F "upload=@./sample.pdf;type=application/pdf"
```

Download bytes:

```bash
curl http://localhost:5000/files/1/download -o sample.pdf
curl http://localhost:5000/File/1/download -H "Range: bytes=0-1023"
```

Use a file in a method:

```python
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route
from n3tx_files import File

class Transcriber(ActorModel):
    __tablename__ = 'transcribers'
    __storable__ = False

    @expose_route('/transcribe', methods=['POST'])
    async def transcribe(audio: File) -> dict:
        local = await audio.ensure_local()
        return {'path': local['path']}
```

Request body:

```json
{"audio": "/File/1"}
```

## Routes

| Route | Purpose |
|---|---|
| `POST /files/upload` | Multipart upload, form field `upload`; creates `File` metadata |
| `GET /files/{id}/download` | Binary download |
| `GET /File/{id}/download` | Class-name download mirror |

Downloads support inclusive byte ranges via `Range: bytes=start-end`.

## Addresses

`File.resolve(address)` accepts internal addresses:

```text
n3tx://files/{id}
/files/{id}
/File/{id}
```

External HTTP imports are intentionally not enabled by default; add providers
explicitly when your deployment needs them.

## Distributed nodes

An app node can delegate byte operations to a storage node while still treating
the resource as a `File` capability. The storage node owns `File` metadata and
bytes; the app node forwards upload/download requests or resolves file addresses
through a provider/client seam. Tests cover this two-node behavior with isolated
ASGI apps.

## Extension boundaries

- Metadata is normal N3TX storage (`File(ActorModel)`).
- Bytes live in `FileStore` providers (`LocalFileStore` in the base package).
- Dynamic file bytes are served by explicit API routes, not static mounts.
- Importing `n3tx_files` registers type-driven `File` materialization. Core does
  not import this package directly.

CDN, object-store, and remote-node providers are additive strategies layered
behind the same public `File` primitive.
