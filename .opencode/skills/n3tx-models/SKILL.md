---
name: n3tx-models
description: N3TX model definitions with ProtoModel, ActorModel, BaseUser, schema, fields, UI metadata, validation, and app data contracts. Use when defining or changing N3TX models.
argument-hint: "<model or data contract>"
---

# N3TX Models

Models are the source of truth for the whole stack.

## Choose a base class

| Base | Use when |
|---|---|
| `ProtoModel` | Data/schema/storage without actor capabilities |
| `ActorModel` | Model should receive TX, expose tools, participate in agents/networking/lifecycle |
| `BaseUser` | User model with login/register/password hashing |
| `AgentActor` | Dynamic persisted agent instances |

Default for new app entities: **`ActorModel`** if the app may use agents, workflows, actor routing, or reusable capabilities.

## Canonical model

```python
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.models.ref import ListRef
from n3tx_core.utils.decorators import expose_route


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
    __ui__ = {
        'icon': 'box',
        'field_order': ['name', 'price', 'description', 'comments'],
        'groups': {'main': ['name', 'price', 'description'], 'Social': ['comments']},
        'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
    }

    name: str = Field(min_length=1, max_length=200, json_schema_extra={'ui': {'placeholder': 'Product name'}})
    price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}})
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    user_owner: int | None = None
    comments: ListRef['Comment'] = Field(default=[])

    @expose_route('/discount', methods=['POST'], access=OWNER | ROLE('admin'))
    def discount(self, percent: float) -> dict:
        return {'new_price': self.price * (1 - percent / 100)}
```

## BaseUser pattern

```python
from typing import Optional
from pydantic import Field
from n3tx_core.models.base_user import BaseUser


class User(BaseUser):
    __tablename__ = 'users'
    __abstract__ = False
    image: Optional[str] = Field(default=None)
```

`BaseUser` provides `name`, `email`, `role`, hidden `password_hash`, `login()`, and `register_user()`.

## Schema output to expect

`GET /Product` returns a JSON Schema with:

- `$schema`, `$id`, `__name__`, `__tablename__`
- `properties`, `required`
- `methods` from `@expose_route`
- `access` serialized from `__access__`
- `ui` hints from `__ui__`
- `$defs` for referenced models

## Model guardrails

- Do not put frontend-only duplicate contracts in JS; put them in schema via fields/`__ui__`.
- Do not implement storage manually for storable models.
- Do not make model methods call internal HTTP endpoints.
- Do not hide reusable app capabilities in free functions; expose them through actors/model methods.

## Verification

- Check `GET /{ClassName}` schema includes fields, UI, access, and methods.
- Check create/read/update/delete work through generated routes.
- Check `model_response()`-backed responses include `$schema` and `$id`.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs if a gap is found.
