---
name: n3tx-backend
description: Broad N3TX backend application development. Use for models, storage, auth, routes, actors, agents, app bootstrap, external integrations, and backend verification without framework source lookup.
argument-hint: "<backend feature>"
---

# N3TX Backend

Backend work in N3TX starts from models and actor boundaries, not hand-written controllers.

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
from n3tx_core.models.ref import ListRef
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE, Where
from n3tx_core.utils.decorators import expose_route
from n3tx_actors.models.actor_model import ActorModel
```

Use `ActorModel` when the model should participate in TX routing, agents, MCP, WebSocket, federation, lifecycle events, or reusable compute.

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

## What not to do

- Do not add app-specific FastAPI routes when a model method with `@expose_route` works.
- Do not query SQLite directly from feature code; use model CRUD/storage.
- Do not duplicate auth decisions outside `__access__`/`access=`.
- Do not call internal N3TX HTTP endpoints from backend code; use TX/Matrix or direct model methods at the correct boundary.
- Do not place reusable compute in unaddressable helper functions.

## Backend verification

- Check schema: `GET /{ClassName}`.
- Check routes: CRUD and method endpoints use generated grammar.
- Check auth: unauthorized requests fail, authorized requests pass.
- Check response identity: `$schema` and `$id` are present.
- Check actor routing if `routing='actor'` is used.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or behavior contradicts docs. If source resolves a gap, update or propose docs/skills.
