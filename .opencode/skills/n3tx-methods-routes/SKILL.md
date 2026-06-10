---
name: n3tx-methods-routes
description: N3TX custom methods, generated routes, @expose_route, method schemas, user injection, route grammar, and action design. Use when adding API actions or model behavior.
argument-hint: "<method or route task>"
---

# N3TX Methods and Routes

Custom behavior belongs in model/actor methods exposed with `@expose_route`.

## Basic method

```python
from n3tx_core.utils.decorators import expose_route

class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True

    @expose_route('/discount', methods=['POST'])
    def discount(self, percent: float) -> dict:
        return {'new_price': self.price * (1 - percent / 100)}
```

Routes generated:

```text
POST /products/{id}/discount
POST /Product/{id}/discount
```

The method also appears in schema under `methods.discount`, allowing frontend buttons and agent tool discovery.

## Method parameters

- Parameters come from function signatures.
- Type hints become schema.
- `user` is injected by auth layer and omitted from request body/tool args.
- Return annotations can describe response models.

## Toggle method pattern

```python
@expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
def favorite(self, user: User = None) -> dict:
    return {'action': 'favorited', '_field': 'favorites', 'id': 123, 'user': user.id}
```

Toggle endpoints may accept empty bodies. Return structured payloads so the frontend can update local collections.

## Route grammar

```text
/{tablename}/...       JSON data API and custom methods
/{ClassName}           schema endpoint
/{ClassName}/_         JSON collection mirror
/{ClassName}/{id}      JSON instance mirror
/{ClassName}/{id}/{method} literal method mirror
/{ClassName}/@...      HTML/view shell entrypoints
```

`@` is reserved for views and never invokes methods.

## Guardrails

- Do not add custom FastAPI routes for normal model actions.
- Do not create generic catch-all method routes.
- Do not manually parse request bodies when signatures can declare types.
- Do not make methods call internal HTTP endpoints; call model/actor boundaries directly or use TX where appropriate.

## Verification

- Schema method includes route, methods, parameters, return, access, stream/events when applicable.
- Table-name and class-name method mirrors behave consistently.
- Frontend renders method via `ntx-method`/`ntx-stream` when schema says so.
- Agent tool discovery can see the method if actor/model is in tools list.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
