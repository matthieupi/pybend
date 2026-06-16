---
name: n3tx-build-app
description: Build complete N3TX applications and features. Use when creating an app, adding an end-to-end feature, choosing routing level, defining models, wiring UI, agents, storage, auth, ManyToMany relationships, files, and verification.
argument-hint: "<app or feature to build>"
---

# N3TX Build App

Use this skill for end-to-end application development on top of N3TX.

## Development sequence

```text
1. Identify domain models and capabilities
2. Define backend models as source of truth
3. Choose routing level
4. Add relationships, files, auth, methods, and UI hints
5. Wrap reusable/external compute in actors/adapters
6. Bootstrap app with create_app() or N3TXApp
7. Seed data if useful
8. Verify schema, API/TX behavior, and UI rendering
```

## Choose the right routing level

| Level | Shape | Use when |
|---|---|---|
| Level 1 | `ProtoModel` + direct routes | Simple CRUD/schema-driven apps |
| Level 2 | `ActorModel` + direct routes | App needs actor capabilities but plain HTTP route layer is enough |
| Level 3 | `ActorModel` + `routing='actor'` | Networking, agents, MCP, WebSocket, federation, or strict actor routing matters |

Default recommendation for new serious N3TX apps: **use `ActorModel` and Level 3** unless there is a reason to stay simpler. It keeps capabilities inside the actor system from the beginning.

## Minimal app

```python
from pydantic import Field

from n3tx_core.app import create_app
from n3tx_actors.models.actor_model import ActorModel


class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True

    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)


app = create_app(
    models=[Product],
    storage='sqlite:///app.db',
    routing='actor',
)
```

## App with UI and agents

Import capability packages **before** defining models that depend on their mixins:

```python
import n3tx_ui      # registers ViewableMixin for __ui__
import n3tx_agents  # registers AgentMixin for __agent__
import n3tx_files   # registers File typed-argument materialization, when used

from n3tx_core.app import create_app
from n3tx_actors.models.actor_model import ActorModel

from models import Product, User

app = create_app(models=[User, Product], storage='sqlite:///app.db', routing='actor')
```

## Feature implementation checklist

- Model fields encode validation with Pydantic types/`Field()`.
- `__tablename__` is plural/snake-like and becomes the API/actor address.
- `__storable__ = True` only for persisted entities.
- `__access__` declares backend authorization.
- `__ui__` carries field order, groups, icons, renderers, and method UI hints.
- Parent/child relationships use `ListRef[T]`.
- Shared relationships use `ManyToMany[T]` and are discovered during app bootstrap.
- File workflows use `n3tx-files`: `File` metadata plus `FileStore` bytes.
- Custom actions use `@expose_route`.
- Reusable services are actors/tool actors.
- External IO is wrapped in a dedicated actor or adapter.
- Agents use `AgentActor` or `__agent__ = True`.

## Route and schema contract

```text
GET  /{ClassName}           -> JSON Schema
GET  /{tablename}           -> collection data
POST /{tablename}           -> create
GET  /{tablename}/{id}      -> read
PUT  /{tablename}/{id}      -> update
DELETE /{tablename}/{id}    -> delete
POST /{tablename}/{id}/{method} -> @expose_route method
GET  /{ClassName}/@...      -> UI shell/view route
POST /files/upload          -> multipart upload when n3tx-files File is registered
GET  /File/{id}/download    -> binary download mirror when n3tx-files is registered
```

Responses should include:

```json
{"$schema": "http://localhost:5000/Product", "$id": "http://localhost:5000/Product/1"}
```

## Verification

For application work, verify the narrow contract first:

```bash
cd /workspace && python3 scripts/test-backend.py --suite core -- -q
cd /workspace/tests/frontend && npx vitest run
```

When working in an example app, run from that example directory when starting the server.

## Source-reading policy

Prefer these skills and project docs. Inspect framework source only when documentation is insufficient, does not cover the intended implementation, or observed behavior contradicts docs. If that happens, update or propose updates to docs/skills.
