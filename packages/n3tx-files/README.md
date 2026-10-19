# n3tx-files

Optional File metadata, local byte storage, multipart upload/download, and typed
method-argument materialization. Install `n3tx-files` in a Python 3.10+
environment; declared dependencies are core and actors. Upload route registration
also requires `python-multipart`, which this package does not declare. Install it
explicitly in the application's environment. See [package metadata](pyproject.toml).

```text
File(ActorModel) -> N3TX storage: metadata
       |
       +--------> FileStore: bytes
```

## Start here

The [File guide](docs/file.md#provider-free-local-example) contains a complete
temporary-storage upload/range-download/materialization example. It needs no
server or external storage service. Importing `n3tx_files` registers the typed
materializer; register File with application storage to mount its byte routes.

| Export | Role |
|---|---|
| `File` | Actor-backed metadata record |
| `FileStore` | Byte provider protocol |
| `FileStat` | Key, size, SHA-256, content type |
| `LocalFileStore` | Filesystem-backed implementation |
| `configure_file_store` / `get_file_store` | Process-wide provider selection |

## Important defaults

- `File.__access__['read']` is `ANYONE`: metadata and downloads are public even
  when `public=False`. That field is descriptive, not a privacy gate.
- Upload requires an authenticated caller; update/delete require owner or admin.
- Canonical URL resolution is local to the configured API; no automatic external
  HTTP import or remote-file projection is shipped.
- Metadata deletion is not blob deletion. Back up and reconcile both stores.
- Typed dictionary inputs are validated as File data, not reloaded/authorized
  records. Do not treat materialization or a local path as a security sandbox.

Read [security and operations](docs/file.md#security-and-operations) before using
private documents or accepting untrusted file inputs. Dynamic bytes belong on
the package's API routes, never in the frontend static mount.
