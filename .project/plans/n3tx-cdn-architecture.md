# N3TX CDN Capability Architecture Plan

## ✅ Recommendation

Build CDN as a new optional package, `n3tx-cdn`, plus two small generic extension seams in the existing framework:

1. **App extensions in `n3tx-core`** — so packages can mount routes before the root static catch-all without core hard-importing them.
2. **Typed address materialization in `n3tx-actors` / shared core** — so actor methods can accept file addresses and receive validated file handles/metadata.

The default out-of-the-box mode should be a local filesystem CDN server backed by normal N3TX metadata storage. Production mode swaps only the blob provider, not the model, routes, or actor interface.

```text
Compute N3TX node                         CDN N3TX node
-----------------                         -------------
Actor method input                         /cdn/upload
  {"file": "n3tx://assets/42"}  ----->    CDNAsset metadata DB
        |                                  BlobStore provider
        v                                    | local FS / S3 / R2
materialize(CDNFile)                         v
        |                                  /cdn/assets/42/download
        v
method receives CDNFile handle <----- stream/range/signed URL
```

This keeps N3TX's philosophy intact: **models and schemas describe behavior; adapters and mixins provide plumbing; developers consume simple typed primitives.**

---

## 📍 Current State

### What exists today

| Area | Current behavior | Relevance |
|---|---|---|
| Static files | `FastAPIBackend.get_app()` mounts app files and package statics, then root `StaticFiles` at `/` | Post-build CDN route mounting is fragile because `/` catch-all is last |
| App bootstrap | `N3TXApp.build()` registers models, routes, discovery, then calls `backend.get_app()` | Best place for package app-extension hooks |
| Actor routing | `NetworkAPI` translates HTTP to `TX`; `ActorModel.handler()` invokes CRUD/custom methods | Best transport-neutral point for method input materialization |
| Response identity | `model_response()` emits `$schema` and `$id`; refs serialize as hrefs | Strong base for addressable resources, but no reverse resolver yet |
| Optional packages | `n3tx-ui` / `n3tx-agents` register mixins and schema extensions at import time | `n3tx-cdn` should follow this exact pattern |
| Lifecycle events | `ActorModel._publish_lifecycle()` sends `LIFECYCLE` to subscribers | Useful for CDN purge/invalidation |

### Key gap

There is no first-class concept of a **large binary resource** or a shared resolver that turns an address (`n3tx://assets/42`, `/CDNAsset/42`, remote HTTPS URL) into a typed object for model or actor methods.

---

## 🎯 Target Architecture

### Core concepts

| Concept | Package | Purpose |
|---|---|---|
| `CDNAsset` | `n3tx-cdn` | Storable metadata model for blobs/files |
| `BlobStore` | `n3tx-cdn` | Provider interface for binary storage |
| `LocalBlobStore` | `n3tx-cdn` | Zero-config filesystem implementation |
| `CDNFile` / `FileRef` | `n3tx-cdn` | Typed materialized method input |
| `CDNExtension` | `n3tx-cdn` | App extension that mounts upload/download routes |
| `AddressResolver` registry | core/actors seam | Generic scheme-based address resolution |
| `NetworkEdge` / purge provider | later `n3tx-cdn` phase | Optional external CDN invalidation adapter |

### Package dependency shape

```text
n3tx-core
  ↑
n3tx-actors ──────┐
  ↑               │ optional, if actor-aware integration enabled
n3tx-cdn ─────────┘

n3tx meta-package -> depends on n3tx-cdn
```

Avoid any `n3tx-core -> n3tx-cdn` import. Core should expose neutral registries/hooks; CDN registers into them.

---

## 🗺️ Flow Design

### Upload and serve flow

```text
POST /cdn/upload
  -> authenticate user
  -> stream UploadFile to BlobStore.put_stream()
  -> compute sha256, size, content_type
  -> create CDNAsset metadata row
  -> return model_response() with addresses

GET /cdn/assets/{id}
  -> authorize read against CDNAsset
  -> return metadata + signed/public URLs

GET /cdn/assets/{id}/download
  -> authorize read or verify signature
  -> stream BlobStore.open_stream(storage_key)
  -> support Range, ETag, Content-Length, Cache-Control
```

### Actor materialization flow

```text
TX(name='transcribe', data={'audio': 'n3tx://assets/42'})
  -> ActorModel.handler()
  -> inspect method signature: transcribe(self, audio: CDNFile)
  -> materialize_kwargs(...)
       -> resolver registry sees n3tx:// scheme
       -> loads CDNAsset metadata
       -> enforces access with tx.meta.user
       -> returns CDNFile(asset=..., open=...)
  -> method(instance, audio=CDNFile(...))
```

Materialization should be **explicit by type hint**. A plain `str` URL remains a string. This avoids surprise network fetches and SSRF hazards.

---

## 💻 Code Shape Preview

### 1. Generic app extension seam in core

```python
# n3tx_core/app_extensions.py
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass
class AppContext:
    backend: Any
    app: Any
    registered_models: dict[str, type]
    storage: Any
    routing: str
    matrix: Any = None
    static_dirs: list[str] = None

class AppExtension(Protocol):
    def mount(self, ctx: AppContext) -> None: ...
```

```python
# N3TXApp
def use(self, extension) -> "N3TXApp":
    self._extensions.append(extension)
    return self

# build(), after API/discovery routes and before backend.get_app()
for extension in self._extensions:
    extension.mount(AppContext(...))
```

### 2. CDN package public API

```python
# n3tx_cdn/__init__.py
from .asset import CDNAsset, CDNFile, FileRef
from .extension import CDNExtension, cdn
from .stores import BlobStore, LocalBlobStore

__all__ = [
    "CDNAsset", "CDNFile", "FileRef",
    "CDNExtension", "cdn",
    "BlobStore", "LocalBlobStore",
]
```

### 3. Metadata model, not blob storage in DB

```python
class CDNAsset(ActorModel):
    __tablename__ = "cdn_assets"
    __storable__ = True
    __access__ = {
        "read": ANYONE,              # configurable default
        "create": AUTHENTICATED,
        "update": OWNER | ROLE("admin"),
        "delete": OWNER | ROLE("admin"),
    }

    filename: str
    content_type: str = "application/octet-stream"
    size: int = 0
    sha256: str = ""
    storage_key: str
    public: bool = False
    user_owner: int | None = None
    meta: dict = Field(default={})
```

### 4. Blob provider interface

```python
class BlobStore(Protocol):
    async def put_stream(self, source, *, key: str | None = None, meta: dict = None) -> BlobStat: ...
    async def open_stream(self, key: str, *, start: int | None = None, end: int | None = None): ...
    async def stat(self, key: str) -> BlobStat: ...
    async def delete(self, key: str) -> None: ...
    async def sign_url(self, key: str, *, expires: int = 3600) -> str | None: ...
```

### 5. Address resolver/materializer

```python
class AddressResolver(Protocol):
    schemes: tuple[str, ...]
    async def resolve(self, address: str, *, expected_type: type, user: dict | None) -> object: ...

def register_resolver(resolver: AddressResolver) -> None: ...

async def materialize_kwargs(sig, type_hints, data: dict, tx: TX) -> dict:
    out = {}
    for name, value in data.items():
        expected = type_hints.get(name)
        if expected and is_materializable(expected) and isinstance(value, str):
            out[name] = await resolve_address(value, expected_type=expected, user=tx.meta.get("user"))
        else:
            out[name] = value
    return out
```

```python
class CDNResolver:
    schemes = ("n3tx", "https", "http")

    async def resolve(self, address: str, *, expected_type: type, user=None):
        # Only fetch/stream remote HTTPS if explicitly configured and expected_type is CDNFile.
        # Internal n3tx://assets/{id} resolves through CDNAsset + BlobStore.
        ...
```

### 6. Developer-facing usage

```python
from n3tx_cdn import CDNFile, cdn

app = (N3TXApp(storage="sqlite:///app.db", routing="actor")
    .model(MyJob)
    .use(cdn())              # zero-config local file store
    .build())

class MyJob(ActorModel):
    __tablename__ = "jobs"
    __storable__ = True

    @expose_route("/transcribe", methods=["POST"])
    async def transcribe(self, audio: CDNFile) -> dict:
        async with audio.open() as stream:
            return await transcribe_stream(stream, content_type=audio.content_type)
```

---

## 📊 Architectural Decisions

| Decision | Recommendation | Why |
|---|---|---|
| Package vs core feature | Optional `n3tx-cdn` package | Keeps core small and dependency graph clean |
| Store blobs in DB? | No; store metadata only | Large files need streaming, range reads, provider swap |
| Implicit URL fetching? | No; type-hint-gated materialization only | Prevents SSRF and surprising latency |
| CDN node separate from compute node? | Yes, via HTTP/signed URLs/address resolver | Enables distributed deployments without shared DB |
| First provider | Local filesystem | Useful out of box with minimal config |
| Production providers | S3/R2/GCS via `BlobStore` extras | Extensible without changing routes or actors |
| Route integration | Generic `N3TXApp.use()` extension | Avoids root static mount ordering issues |
| Invalidation | Lifecycle subscriber adapter later | Fits existing actor event model |

---

## 🧩 Implementation Slices

### Slice 1 — Generic app extension hook

Files:
- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-core/src/n3tx_core/app_extensions.py`
- `packages/n3tx-core/docs/app-bootstrap.md`

Add `N3TXApp.use(extension)` and `create_app(extensions=[...])`. Run extensions after API/discovery routes and before `backend.get_app()` mounts static.

### Slice 2 — `n3tx-cdn` package skeleton + local provider

Files:
- `packages/n3tx-cdn/pyproject.toml`
- `packages/n3tx-cdn/src/n3tx_cdn/stores.py`
- `packages/n3tx-cdn/src/n3tx_cdn/asset.py`

Create `BlobStore`, `LocalBlobStore`, `CDNAsset`, `CDNFile`, and `FileRef`. Keep provider dependencies as extras.

### Slice 3 — CDN routes and zero-config server mode

Files:
- `packages/n3tx-cdn/src/n3tx_cdn/extension.py`
- `packages/n3tx-cdn/src/n3tx_cdn/routes.py`

Mount `/cdn/upload`, `/cdn/assets/{id}`, `/cdn/assets/{id}/download`, and `/cdn/health`. Use streaming reads/writes and correct headers.

### Slice 4 — Address resolver and actor materialization

Files:
- `packages/n3tx-core/src/n3tx_core/addressing.py` or `packages/n3tx-actors/src/n3tx_actors/materialize.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

Add resolver registry and call `materialize_kwargs()` before invoking exposed actor methods. Mirror behavior in direct routes to avoid Level 1/2 vs Level 3 drift.

### Slice 5 — Cache metadata and CDN headers

Files:
- `packages/n3tx-cdn/src/n3tx_cdn/schema_ext.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`

Add schema-level CDN/cache hints and emit `Cache-Control`, `ETag`, `Content-Disposition`, `Accept-Ranges`, `Content-Length`, and `Vary` where appropriate.

### Slice 6 — Distributed node support

Files:
- `packages/n3tx-cdn/src/n3tx_cdn/config.py`
- `packages/n3tx-cdn/src/n3tx_cdn/client.py`

Support compute-node configuration such as:

```python
cdn(base_url="https://cdn.example.com", mode="client")
cdn(storage=LocalBlobStore("./cdn-data"), mode="server")
```

Client mode materializes remote `n3tx://` / HTTPS file addresses without mounting upload routes.

### Slice 7 — Optional purge adapter

Files:
- `packages/n3tx-cdn/src/n3tx_cdn/network_edge.py`
- `packages/n3tx-cdn/src/n3tx_cdn/providers/cloudflare.py`

Implement lifecycle-event-driven purge for external CDNs. This can wait until basic serving/materialization works.

---

## 🧪 Verification Plan

| Coverage | Tests |
|---|---|
| App hook ordering | Extension routes are reachable and not shadowed by `/` static mount |
| Local blob store | Upload, stat, range read, checksum, delete |
| Asset model | CRUD, ownership, public/private read rules |
| Routes | Upload/download streaming, headers, 404/403/416 handling |
| Materialization | Actor method receives `CDNFile`; plain `str` stays string; invalid address returns 422/404 |
| Direct/actor parity | Same method behavior under direct and actor routing |
| Distribution | Compute node resolves remote CDN URL without shared storage |
| Security | SSRF denylist/allowlist, max size, content type validation, signed URL expiry |

Suggested commands:

```bash
python3 scripts/test-backend.py --suite core -- -q
python3 scripts/test-backend.py --suite actors -- -q
python3 -m pytest packages/n3tx-cdn/src/n3tx_cdn/tests/ -q
python3 scripts/test-backend.py --short
```

---

## ⚠️ Risks and Guardrails

| Risk | Guardrail |
|---|---|
| Route shadowing by root static mount | Mount CDN through `N3TXApp.use()` before `get_app()` |
| SSRF from remote URLs | Only materialize URLs for explicit `CDNFile`/`FileRef` types; default deny private IP ranges; allowlist schemes/hosts |
| Loading huge files into memory | All provider and route APIs are streaming-first |
| Auth leaks during materialization | Resolve metadata and enforce asset read access before opening blob stream |
| Behavior drift between routing modes | Shared materialization helper used by direct routes and actor routes |
| Provider lock-in | Provider interface returns streams/stats/signed URLs; no Cloudflare concepts in core model |
| Stale edge caches | Start with short TTL + ETag; add lifecycle purge adapter later |

---

## ✨ Next Steps

1. Implement the generic `N3TXApp.use()` app-extension seam first.
2. Build `n3tx-cdn` with local filesystem storage and `CDNAsset` metadata.
3. Add upload/download routes and tests before adding any external provider.
4. Add typed actor materialization once the CDN asset/address contract is stable.
5. Add distributed client mode and purge adapters after the local server works end-to-end.

### Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-core/src/n3tx_core/api/backend.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

### Saved Plan

- `.project/plans/n3tx-cdn-architecture.md`
