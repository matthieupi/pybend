---
name: n3tx-actors
description: N3TX actors, ActorModel, TX messages, Matrix routing, reusable compute capabilities, lifecycle events, and actor-oriented app design. Use when building actor-backed capabilities.
argument-hint: "<actor capability>"
---

# N3TX Actors

Actors are the reusable compute and message boundary in N3TX.

## Core concept

```text
TX(name, source, target, data, meta)
   -> Matrix routes by target address
   -> Actor / ActorModel handler
   -> reply/error/stream TX
```

`ActorModel` combines model/schema/storage with actor messaging.

## Use ActorModel for app capabilities

```python
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route


class Calculator(ActorModel):
    __tablename__ = 'calculators'
    __storable__ = False

    @expose_route('/add', methods=['POST'])
    def add(self, a: float, b: float) -> dict:
        return {'result': a + b}
```

This capability can be used by UI, agents, MCP/tools, workflows, or other actors.

## Addressing

```text
Class actor:    products
Instance actor: products/1
```

For storable `ActorModel`, CRUD TX names include `schema`, `create`, `get`, `list`, `update`, `delete`.

## When to use each shape

| Shape | Use when |
|---|---|
| `ActorModel` storable | Entity plus actor behavior |
| `ActorModel` non-storable | Tool/service capability with schema-discoverable methods |
| Plain `Actor` | Low-level actor without model/schema/storage needs |
| `ActorProxy` | Wrap third-party object as actor |
| `NetworkAdapter` | Protocol bridge or external network boundary |

## Lifecycle events

`ActorModel` publishes lifecycle TX after create/update/delete. Subscribers can power federation, audit, agents, or realtime bridges.

## Guardrails

- Put reusable compute in actors, not hidden helpers.
- Do not route internal work through plain HTTP.
- Do not bypass `ActorModel` CRUD when actor routing is the app architecture.
- Do not make the actor system depend on UI/HTML concerns.

## Verification

- Actor is registered with Matrix under the expected address.
- TX reaches the correct handler.
- Errors return error TXs.
- Exposed methods appear in schema and can be discovered as tools.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
