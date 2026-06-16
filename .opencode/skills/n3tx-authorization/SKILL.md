---
name: n3tx-authorization
description: N3TX authorization and authentication with BaseUser, JWT, service-token remote refs, ABAC access rules, OWNER, ROLE, Where, field protection, and frontend access adaptation. Use when working on auth/access behavior.
argument-hint: "<auth or access task>"
---

# N3TX Authorization

Authorization is backend-owned and schema-exposed. The frontend adapts; it is not the source of truth.

## Built-in rules

```python
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE, Where
```

Rules compose:

```python
OWNER | ROLE('admin')
OWNER & Where(status='draft')
~ROLE('banned')
```

## Model access

```python
class Product(ActorModel):
    __owner_field__ = 'user_owner'
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }
```

If `__access__` is omitted, the schema exposes the authenticated wildcard fallback.

## Method access

```python
@expose_route('/publish', methods=['POST'], access=OWNER | ROLE('admin'))
def publish(self) -> dict:
    return {'status': 'published'}
```

## User injection

Custom methods can receive authenticated user context by declaring `user`:

```python
@expose_route('/comment', methods=['POST'], access=AUTHENTICATED)
def comment(self, text: str, user: User = None) -> dict:
    return {'author': user.id if user else None, 'text': text}
```

The `user` parameter is injected by the route layer and is not read from request body.

## Protected fields

```python
class Comment(ActorModel):
    __owner_field__ = 'user_owner'
    __protected_fields__ = {'user_owner'}
    user_owner: int | None = None
```

Protected fields are hidden in edit forms, auto-injected on create, and stripped on update.

## Actor routing auth

In Level 3, auth is two-tier:

```text
NetworkAPI.request interceptor
   -> identity/role gate and list SQL filter
Matrix -> ActorModel.handler_crud
   -> resource-aware OWNER check
```

## Service-to-service auth for distributed refs

`RemoteMatrix` sends trusted backend identity and optional user continuity:

```text
Authorization: Bearer <remote-or-service-token>
X-N3TX-Service: <local-service-name>
X-N3TX-User: <json-user-context>  # optional
```

The receiving backend accepts the request only when the bearer token matches its
configured `SERVICE_TOKEN`. If `X-N3TX-User` is present, it must be a JSON object
and becomes `request.state.user`, so generated routes and ActorModel ABAC remain
the authoritative authorization path. Service auth establishes backend trust; it
does not replace model `__access__` or method `access=` rules.

## Guardrails

- Do not rely on UI-only auth.
- Do not duplicate access logic in frontend code as source of truth.
- Do not bypass `__access__` with custom routes.
- Do not trust request body for protected ownership fields.
- Do not treat service tokens as user permissions; forward user context and let ABAC evaluate it.

## Verification

- Unauthorized create/update/delete fails.
- OWNER succeeds for owned records and fails for others.
- Admin/role rules behave as expected.
- Schema `access` section reflects rules for frontend adaptation.
- Service-token remote calls reject invalid tokens and preserve forwarded user context.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
