# File capability: metadata, bytes, and materialization

[Package](../README.md) · [Actor boundaries](../../n3tx-actors/docs/actor-model.md)

## Concepts

File is a normal storable ActorModel (`files`). Its metadata participates in
schema, CRUD and model relationships. FileStore owns bytes separately; no blob
column or alternate application CRUD layer is needed.

```text
multipart upload -> authorize create -> FileStore.put_stream -> File.create
                                                             |
                                               metadata + canonical $id
                                                             |
download -> authorize read -> FileStore.open_stream <----------+
typed File URL -> File.resolve -> authorized metadata instance
```

`configure_file_store(store)` sets one process-wide provider. Without it,
`get_file_store()` lazily creates LocalFileStore using `N3TX_FILE_STORE_DIR`
(read at import time), default `.n3tx-files/blobs`. Do not configure different
providers concurrently for separate apps in the same process.

## Provider-free local example

Prerequisites: installed `n3tx-files`, `python-multipart` (required for route
registration but not declared by this package), FastAPI's TestClient/httpx test
dependency, and Python 3.10+. Save and run as a script in a fresh process. Storage is temporary,
the token is generated locally for testing, and no real user, server, external
provider or paid agent is contacted. Do not reuse the test secret in deployment.

```python
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.app import create_app
from n3tx_core.authorize import AUTHENTICATED, create_token
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import expose_route
from n3tx_files import File, LocalFileStore, configure_file_store

class Inspector(ActorModel):
    __tablename__ = 'inspectors'
    __storable__ = False

    @staticmethod
    @expose_route('/inspect', methods=['POST'], access=AUTHENTICATED)
    async def inspect_file(file: File) -> dict:
        return {'filename': file.filename, 'size': file.size}

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    configure_file_store(LocalFileStore(root / 'blobs'))
    app = create_app(
        models=[File, Inspector],
        storage=SQLiteStorage(str(root / 'files.db')),
        static_dir=None,
        jwt_secret='documentation-test-secret-not-for-production',
    )
    headers = {'x-access-token': create_token(1, 'test@example.com', 'user')}
    with TestClient(app) as client:
        denied = client.post('/files/upload', files={'upload': ('n.txt', b'0123456789')})
        assert denied.status_code == 403
        uploaded = client.post('/files/upload', headers=headers,
            files={'upload': ('n.txt', b'0123456789', 'text/plain')})
        assert uploaded.status_code == 201
        record = uploaded.json()
        ranged = client.get(f"/File/{record['id']}/download",
                            headers={'Range': 'bytes=2-5'})
        assert ranged.status_code == 206 and ranged.content == b'2345'
        inspected = client.post('/inspectors/inspect', headers=headers,
                                json={'file': record['$id']})
        assert inspected.status_code == 200
        assert inspected.json() == {'filename': 'n.txt', 'size': 10}
    print('upload, range and typed File verified')
```

The anonymous download is intentional: the built-in read policy is public.
For an actual service, use the application's authenticated login/token flow and
review privacy policy before uploading sensitive data.

## Metadata reference

| Field | Default / constraint | Role |
|---|---|---|
| `filename` | Required nonempty string | Display/original filename |
| `content_type` | `application/octet-stream` | Declared MIME type, not content inspection |
| `size` | 0, nonnegative | Byte length |
| `sha256` | `''` | Digest from upload |
| `storage_key` | `''` | Provider key |
| `origin` | None | Descriptive source |
| `public` | False | Descriptive only; not used by read authorization |
| `user_owner` | None | Upload assigns verified caller ID |
| `meta` | Empty dictionary | Application metadata |

Protected fields are `user_owner`, `storage_key`, `sha256`, `size`. Protection
does not mean secrecy or uniform enforcement across direct Python, HTTP and raw
TX. Do not expose generic metadata creation as a substitute for verified upload.

## Routes and methods

| Interface | Contract |
|---|---|
| `POST /files/upload` | Multipart field `upload`; authorize create, store bytes, create metadata; 201 |
| `GET /files/{id}/download` | Authorize read on record; binary response |
| `GET /File/{id}/download` | Same download handler |
| `await File.resolve(ref, user=None)` | Canonical current-API File URL -> read-authorized record |
| `await file.ensure_local(user=None)` | Local store only: `{path, sha256, size}`; no remote projection |

`register_extra_routes` installs the byte routes in direct and actor HTTP modes.
These package-owned routes are direct binary/multipart adapters, not JSON TX
transports. Their paths are hard-coded to `files`/`File`, so subclassing/renaming
the model does not imply independently namespaced byte endpoints.

Range support is a single inclusive `bytes=start-end`, open-ended `bytes=start-`,
or suffix `bytes=-N`. Valid ranges return 206 with Content-Range; invalid or
unsatisfiable ranges return 416. No range returns 200. Headers include stored
size, SHA-256 ETag, attachment filename and `nosniff`; do not infer conditional
GET, multi-range, MIME verification or filename sanitization from those headers.

## Store protocol

```text
async put_stream(source, *, key=None, meta=None) -> FileStat
open_stream(key, *, start=None, end=None) -> AsyncIterator[bytes]
async stat(key) -> FileStat
async delete(key) -> None
```

LocalFileStore accepts bytes, bytearray, a local path or an object with sync/async
`read()`. It does not accept arbitrary async iterators in the shipped helper.
Writes pass through `.tmp`, compute SHA-256, then move to an explicit key or
`<digest[:2]>/<digest>`. Default chunks are 1 MiB. `stat()` rereads/hashes bytes;
it does not recover the original MIME type. Local filesystem operations are
synchronous inside async methods and can block the event loop.

`path_for()` resolves paths and rejects escape outside the root, including
resolved symlink escape. This containment check is not protection against a
hostile process racing filesystem changes. Keep the root writable only by trusted
service accounts. Explicit keys can overwrite existing content; checksum-derived
keys can be shared by multiple metadata rows.

## Typed materialization

Importing `n3tx_files` registers a materializer through core's neutral hook.

| Incoming value for exact `File` annotation | Behavior |
|---|---|
| Canonical URL string | `File.resolve` reloads and authorizes read |
| File instance | Returned unchanged; no new authorization |
| Dictionary | `File.model_validate`; no stored-record lookup/read authorization |
| Other annotation/value | Not handled by this materializer |

Plain strings are not auto-fetched. The registration matches exact File, not a
promise for every subclass, union or collection annotation. URL resolution
requires an absolute HTTP(S) entity ref targeting schema `File`, current
`config.API_URL` base, and a nonnegative integer ID. Relative refs, another
schema or another API base are rejected (400); missing row is 404, denied read
403. Use the metadata response's `$id`, not a guessed table-name URL.

`ensure_local()` only checks the configured LocalFileStore path exists. It does
not itself authorize read or verify the stored checksum, and its `user` argument
is unused. Do not return server filesystem paths to clients as in older examples.
Dictionary/instance inputs are not proof of ownership; reject or re-resolve them
at a reviewed application boundary before private byte processing.

## Security and operations

| Risk | Required deployment decision |
|---|---|
| Public reads by default | Set and verify an explicit private-data policy; `public=False` is insufficient |
| Upload resource use | Enforce size, rate, quota and concurrency limits; package has no explicit total-byte limit |
| Untrusted content | Validate filenames/content types, scan/quarantine as needed; hashing is not malware detection |
| Split persistence | Back up metadata DB and blob directory consistently; test restoration of both |
| Failed metadata write | Bytes were already written; reconcile orphan blobs, no cross-store transaction |
| Metadata deletion | No automatic FileStore.delete; implement reviewed retention/GC with shared-key awareness |
| Local path disclosure | Restrict ensure_local and downstream processors; filesystem access is not a sandbox |
| Process-wide provider | One configuration per process; do not mutate it during concurrent requests |

Do not statically serve the blob directory. Keep credentials and files out of
source/build inputs. Reconcile missing blobs and metadata size/checksum drift;
downloads trust stored metadata and do not preflight `stat()`.

## Distributed extension boundary

The shipped provider is local. Remote object-store providers can implement
FileStore, but `ensure_local` projection/cache for those providers is not
implemented. `File.resolve` does not fetch remote File URLs.
The [two-node test](../src/n3tx_files/tests/test_distributed_nodes.py) uses a
test-only gateway/client forwarding uploads/downloads between ASGI apps. It is
an extension demonstration, **not** a shipped distributed provider or automatic
remote materializer. Review remote authorization, egress, buffering and cleanup
before implementing such an extension.

Evidence: [file.py](../src/n3tx_files/file.py), [store.py](../src/n3tx_files/store.py),
[routes.py](../src/n3tx_files/routes.py), [materialize.py](../src/n3tx_files/materialize.py),
[address.py](../src/n3tx_files/address.py), [tests](../src/n3tx_files/tests/).
