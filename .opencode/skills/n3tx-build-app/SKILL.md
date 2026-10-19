---
name: n3tx-build-app
description: N3TX end-to-end app workflow: choose capabilities and routing, define models, bootstrap, wire UI/auth/storage/agents/files, and verify. Use when creating a new app or vertical feature.
argument-hint: "<app or feature to build>"
---

# N3TX Build App

Use this skill for end-to-end application development on top of N3TX.

## Development sequence

```text
1. Identify domain models and capabilities
2. Define backend models as source of truth
3. Choose model capabilities and HTTP routing independently
4. Add relationships, files, auth, methods, and UI hints
5. Wrap reusable/external compute in actors/adapters
6. Bootstrap app with create_app() or N3TXApp
7. Seed data if useful
8. Verify schema, API/TX behavior, and UI rendering
```

## Choose Capabilities And Routing

| Choice | Shape | Use when |
|---|---|---|
| Direct models | `ProtoModel` + direct routes | Simple CRUD/schema-driven apps |
| Actor capabilities | `ActorModel` + direct routes | Actor capabilities with direct HTTP |
| Actor HTTP | `ActorModel` + `routing='actor'` | HTTP must dispatch through NetworkAPI and Matrix |

Choose only the capabilities required. Agents do not inherently require actor
HTTP. Factory/builder/raw construction is independent of these choices. Verify
each enabled protocol's authorization rather than assuming parity.

## Minimal app

```python
from pydantic import Field

from n3tx_core.app import create_app
from n3tx_core.models.proto_model import ProtoModel


class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True

    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)


app = create_app(
    models=[Product],
    storage='sqlite:///app.db',
)
```

Use `ActorModel` and `routing='actor'` only when actor routing is part of the
capability being built.

## Delegate focused work

| Need | Load |
|---|---|
| Model fields, schema, validation | `n3tx-models` |
| Relationships, pagination, ownership | `n3tx-storage-relationships` |
| Dict/list JSON TEXT fields | `n3tx-json-fields` |
| Uploads, downloads, `FileStore`, file materialization | `n3tx-files` |
| Auth/access/protected fields | `n3tx-authorization` |
| Custom methods/routes | `n3tx-methods-routes` |
| Actor-backed reusable compute | `n3tx-actors` |
| Protocol routing/WebSocket/MCP/AP | `n3tx-networking` |
| LLM agents/tools/chat | `n3tx-agents` |
| Schema-driven UI | `n3tx-ui-schema`, `n3tx-ui-components`, `n3tx-widgets` |
| Tests and verification | `n3tx-testing` |

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
- Local collections use `list[T]`; URL pointers use `Ref[T]`/`list[Ref[T]]`.
- Prefer explicit models for shared links; ManyToMany is legacy, not the default.
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
# From the checkout root, using the approved interpreter:
"${N3TX_PYTHON:-/workspace/.venv-agents/bin/python}" scripts/test-backend.py --suite core -- -q
npm --prefix tests/frontend test
```

When working in an example app, run from that example directory when starting the server.

## Source-reading policy

Read `AGENTS.md` and relevant `docs/` or package docs first. Then
read `BACKEND.md`, `FRONTEND.md`, or both based on the affected surface.
Inspect framework source only when documentation is insufficient, stale, or
contradicted by observed behavior. If source resolves a gap, update or propose
updates to docs/skills.
