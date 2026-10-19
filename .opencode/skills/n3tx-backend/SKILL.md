---
name: n3tx-backend
description: N3TX backend index/workflow: models, storage, distributed refs, auth, methods, actors, agents, files, app bootstrap, external integrations, and backend verification. Use when backend scope is broad or unclear; delegate focused tasks to specialist N3TX skills.
argument-hint: "<backend feature>"
---

# N3TX Backend

Backend work in N3TX starts from models and actor boundaries, not hand-written controllers.

If the task is focused, prefer the specialist skill directly. Use
`n3tx-skill-routing` when skill choice is ambiguous.

## Backend mental model

```text
Pydantic model definition
  -> ProtoModel schema pipeline
  -> registered storage and routes
  -> ActorModel TX dispatch when actor-capable
  -> frontend/agent/tool discovery from schema
```

The backend is authoritative. It owns schema, validation, access control, routes, entity identity, and capability discovery.

## Public imports

```python
from n3tx_core.app import create_app, N3TXApp
from n3tx_core.models.proto_model import ProtoModel, generate_join_model
from n3tx_core.models.base_user import BaseUser
from n3tx_core.models.ref import Ref, ListRef
from n3tx_core.models.relationships import ManyToMany
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE, Where
from n3tx_core.utils.decorators import expose_route
from n3tx_actors.models.actor_model import ActorModel
from n3tx_files import File, LocalFileStore, configure_file_store
```

Use `ActorModel` when the model should participate in TX routing, agents, MCP, WebSocket, federation, lifecycle events, or reusable compute.

## Delegate focused work

| Backend task | Prefer |
|---|---|
| Model fields/schema/validation | `n3tx-models` |
| Relationships/pagination/ownership | `n3tx-storage-relationships` |
| Distributed `Ref[T]`, `list[Ref[T]]`, remote populate | `n3tx-storage-relationships` + `n3tx-networking` |
| Dict/list JSON storage | `n3tx-json-fields` |
| File uploads/downloads/blob providers/materialization | `n3tx-files` |
| Auth/access/JWT/protected fields | `n3tx-authorization` |
| `@expose_route` methods/user injection/route grammar | `n3tx-methods-routes` |
| Actor/TX/Matrix/lifecycle | `n3tx-actors` |
| NetworkAPI/WebSocket/MCP/AP protocol bridges | `n3tx-networking` |
| AgentMixin/AgentActor/tool discovery | `n3tx-agents` |
| App bootstrap/static/import ordering | `n3tx-app-bootstrap` |
| External APIs/webhooks/scraping/cloud services | `n3tx-external-integrations` |

## Backend feature shape

```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __owner_field__ = 'user_owner'
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }
    __ui__ = {'field_order': ['name', 'price'], 'renderer': {'item': 'ntx-item'}}

    name: str
    price: float
    user_owner: int | None = None

    @expose_route('/publish', methods=['POST'], access=OWNER | ROLE('admin'))
    def publish(self, user=None) -> dict:
        return {'status': 'published'}
```

## Relationships

Prefer field-declared relationships over manual plumbing:

```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    comments: ListRef['Comment'] = []       # parent-scoped children
    tags: ManyToMany[Tag] = []              # shared independent entities
```

`ListRef[T]` expresses parent/child nesting. `ManyToMany[T]` expresses shared
membership and is discovered by `create_app()` / `N3TXApp`, which generates the
link model/table during bootstrap.

## Distributed refs

Use `Ref[T]` for a single local/distributed model identity and `list[Ref[T]]` for
JSON-backed pointer arrays. Keep `ListRef[T]` for local owned relationships.

```python
class Job(ActorModel):
    __tablename__ = 'jobs'
    __storable__ = True

    owner: Ref[User] | None = None
    files: list[Ref[File]] = []
    comments: ListRef[Comment] = []
```

Configured remote HTTP refs canonicalize to `n3tx://service/Class/id`. Actor
routing with `remotes={...}` registers `RemoteMatrix` and injects a
`MatrixReferenceResolver` so populate can best-effort resolve remote refs without
making `n3tx-core` import actors.

## Files

For detailed file behavior, load `n3tx-files`. This backend index only names the
boundary: files are first-class metadata records and bytes live behind a
`FileStore` provider.

```python
from n3tx_files import File, LocalFileStore, configure_file_store

configure_file_store(LocalFileStore('./file-blobs'))
app = create_app(models=[File, Product], storage='sqlite:///app.db')
```

Package-owned routes:

```text
POST /files/upload
GET  /files/{id}/download
GET  /File/{id}/download
```

Annotate method parameters as `File` to materialize addresses such as `/File/1`
or `n3tx://files/1` into authorized `File` instances. Plain `str` parameters are
not materialized.

## What not to do

- Do not add app-specific FastAPI routes when a model method with `@expose_route` works.
- Do not query SQLite directly from feature code; use model CRUD/storage.
- Do not store file bytes in SQLite; files are metadata plus `FileStore` bytes.
- Do not duplicate auth decisions outside `__access__`/`access=`.
- Do not call internal N3TX HTTP endpoints from backend code; use TX/Matrix or direct model methods at the correct boundary.
- Do not build ad hoc remote fetches for N3TX refs; use canonical `Ref[T]`, Matrix, and `RemoteMatrix`.
- Do not place reusable compute in unaddressable helper functions.

## Backend verification

- Check schema: `GET /{ClassName}`.
- Check routes: CRUD and method endpoints use generated grammar.
- Check auth: unauthorized requests fail, authorized requests pass.
- Check response identity: `$schema` and `$id` are present.
- Check actor routing if `routing='actor'` is used.
- Check distributed refs canonicalize and remote populate remains best-effort.
- Check `ManyToMany` link models/routes when using shared relationships.
- Check file upload/download/range behavior and File-typed method materialization when using `n3tx-files`.

## Source-reading policy

Read `AGENTS.md` and relevant `/workspace/docs/` or package docs first. Then
read `BACKEND.md`. Read `FRONTEND.md` too for full-stack behavior. Inspect
framework source only when docs/skills are insufficient, stale, or contradicted
by observed behavior. If source resolves a gap, update or propose docs/skills.
