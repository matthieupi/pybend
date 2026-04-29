# Canonical Auth Principal Refactor Plan

## ✅ Recommendation

Introduce a single framework-owned **AuthPrincipal** contract for authorization context, and keep full `User` model injection as an application-method convenience only.

The goal is not to remove `user: User = None` from custom methods. That is useful app-facing API. The goal is to stop reusing that method argument as the authorization context. Internally, every auth decision and actor/tool/thread auth hop should receive one normalized principal shape.

Recommended default path:

1. Add a small, dependency-free `AuthPrincipal` in `n3tx_core.authorize`.
2. Normalize identity once at boundaries and again defensively at subsystem entrypoints.
3. Update `AccessContext` to coerce any supported input into `AuthPrincipal`.
4. Update direct routes, actor routes, auth interceptor, `ActorModel`, agents tools, and thread helpers to use principal semantics.
5. Preserve compatibility for custom methods that declare `user: User = None` by continuing to inject the full model instance into method kwargs.
6. Remove the agents-local `_thread_user()` tactical adapter after `AgentMixin` uses the shared normalizer.

## 📍 Current State

There are two user shapes today:

| Context | Current shape | Purpose |
|---|---|---|
| `request.state.user`, `tx.meta['user']`, `AccessContext.user` | JWT-shaped `dict`: `{user_id, email, role, exp?, iat?}` | Authorization / ABAC |
| custom `@expose_route` method arg `user: User = None` | full app `User` model instance | Business logic convenience |

That split is valid, but it is currently implicit. The bug appeared because `AgentMixin.run(..., user=user)` received the business-method `User` instance and forwarded it into Thread CRUD auth, where ABAC expected the JWT-shaped dict.

### Existing control flow

```text
HTTP x-access-token
  -> JWTAuthMiddleware
       request.state.user = decoded JWT dict
  -> Direct routes OR NetworkAPI routes
       AccessContext(user=<dict>) for auth
       custom method user arg may become User.get(user_id)
  -> custom method calls AgentMixin.run(user=<User instance>)
  -> AgentMixin Thread CRUD TX meta expected dict
       tactical _thread_user() currently bridges this
```

### Evidence from code exploration

- `AccessContext.user` is typed as `Dict[str, Any]` and uses `.get('user_id')`, `.get('role')`, `.get('email')`.
- `routes_fastapi._resolve_user()` and `network_api._parse_method_args()` convert a `user: User` parameter to `User.get(user_id)`.
- `NetworkAPI` still places raw JWT dicts in `tx.meta['user']` for auth.
- `ActorModel._authorize()` and `auth_interceptor()` pass `tx.meta['user']` directly into `AccessContext`.
- `AgentDeps.user` is typed as `Optional[dict]`; tool calls forward it into `TX.meta['user']`.
- `n3tx_agents.mixin._thread_user()` is a narrow local adapter for one symptom.

## 🎯 Target State

```text
Boundary JWT/user/model object
  -> AuthPrincipal.coerce(...)
       user_id, email, role, claims
  -> AccessContext(principal)
  -> tx.meta['user'] carries AuthPrincipal-compatible auth identity
  -> AgentDeps.principal carries same auth identity
  -> Thread/tool/Actor auth all consume the same identity contract

Custom methods may still receive:
  user: User = None       # full app model, for business logic
  user: dict = None       # compatibility/raw payload where requested
```

Important distinction:

- **Authorization principal**: framework identity used by ABAC.
- **Injected user argument**: app-level method input, optionally a full `User` model.

These should not be treated as the same object.

## 🗺️ Architecture Diagram

```text
                    +-----------------------------+
HTTP JWT payload -->| AuthPrincipal.coerce(payload)|
                    +--------------+--------------+
                                   |
                                   v
                 +-----------------+-----------------+
                 | Principal in request / TX metadata |
                 +-----------------+-----------------+
                                   |
        +--------------------------+--------------------------+
        |                                                     |
        v                                                     v
+------------------+                               +----------------------+
| AccessContext    |                               | Custom method kwargs |
| ABAC only        |                               | user: User optional  |
+------------------+                               +----------------------+
        |                                                     |
        v                                                     v
+------------------+                               +----------------------+
| OWNER / ROLE /   |                               | Business logic /     |
| AUTHENTICATED    |                               | app model methods    |
+------------------+                               +----------------------+
        |
        v
+------------------+
| Agent Thread /   |
| Tool TX auth     |
+------------------+
```

## 📊 Design Decisions

| Decision | Recommendation | Intent |
|---|---|---|
| Principal representation | Add `AuthPrincipal` in `n3tx_core.authorize` | One explicit contract for auth identity |
| Keep dict compatibility? | Yes, phase 1 should support `.get()` and `.as_dict()` | Avoid breaking callers/tests immediately |
| App method `user: User` | Preserve | Existing examples/tests rely on `.id`, `.email`, `.role` |
| `tx.meta['user']` key | Keep key, normalize value | Minimize blast radius while improving contract |
| `Optional[User]` support | Add type-unwrapping | Current resolver likely falls back to dict for `Optional[User]` |
| Agent field name | Prefer `principal`; keep `user` alias temporarily | Clarify auth vs business-user semantics |

## 💻 Core Code Shape Preview

### 1. Add canonical principal

File: `packages/n3tx-core/src/n3tx_core/authorize/principal.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: str = 'user'
    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.claims,
            'user_id': self.user_id,
            'email': self.email,
            'role': self.role,
        }

    def get(self, key: str, default=None):
        # Transitional dict-like compatibility for existing code.
        return self.as_dict().get(key, default)

    @classmethod
    def anonymous(cls) -> 'AuthPrincipal':
        return cls()

    @classmethod
    def coerce(cls, value: Any) -> 'AuthPrincipal':
        if value is None:
            return cls.anonymous()
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(
                user_id=value.get('user_id') or value.get('id'),
                email=value.get('email'),
                role=value.get('role', 'user'),
                claims=dict(value),
            )
        # Duck-typed app User model; no N3TX imports, keeps authorize standalone.
        user_id = getattr(value, 'user_id', None) or getattr(value, 'id', None)
        return cls(
            user_id=user_id,
            email=getattr(value, 'email', None),
            role=getattr(value, 'role', 'user'),
        )
```

Export from `packages/n3tx-core/src/n3tx_core/authorize/__init__.py`.

### 2. Make `AccessContext` normalize its user

File: `packages/n3tx-core/src/n3tx_core/authorize/context.py`

```python
@dataclass(frozen=True)
class AccessContext:
    user: AuthPrincipal | dict | Any
    action: str
    model_class: Type[Any]
    resource: Optional[Any] = None
    parent_id: Optional[int] = None

    def __post_init__(self):
        object.__setattr__(self, 'user', AuthPrincipal.coerce(self.user))

    @property
    def user_id(self) -> Optional[int]:
        return self.user.user_id

    @property
    def user_role(self) -> Optional[str]:
        return self.user.role

    @property
    def user_email(self) -> Optional[str]:
        return self.user.email

    @property
    def is_authenticated(self) -> bool:
        return self.user.is_authenticated
```

Intent: after this change, every ABAC rule sees a principal even if callers still pass old dicts.

### 3. Centralize request principal extraction

Files:
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`

Add shared helper location if desired:

```python
def _get_principal(request) -> AuthPrincipal:
    return AuthPrincipal.coerce(getattr(request.state, 'user', None))
```

Then use it for:

- `AccessContext(user=_get_principal(request), ...)`
- protected `user_owner` injection via `principal.user_id`
- `/auth/me` responses via `principal.as_dict()` subset
- `TX.meta['user'] = principal`

Keep `_get_user()` temporarily as compatibility wrapper returning `.as_dict()` where tests or public responses expect dicts.

### 4. Preserve app-facing full `User` injection, but improve type handling

Files:
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`

Replace duplicate type checks with a shared local helper or utility:

```python
from typing import get_args, get_origin, Union

def _unwrap_optional_user_type(type_hint):
    origin = get_origin(type_hint)
    if origin is Union:
        args = [a for a in get_args(type_hint) if a is not type(None)]
        return args[0] if len(args) == 1 else type_hint
    return type_hint


def resolve_method_user(type_hint, principal):
    if not principal.is_authenticated:
        return None
    user_type = _unwrap_optional_user_type(type_hint)
    if (isinstance(user_type, type)
            and issubclass(user_type, StorableMixin)
            and hasattr(user_type, 'get')):
        return user_type.get(principal.user_id)
    return principal.as_dict()
```

Intent: method `user` remains business-level, but the principal is the source of truth.

### 5. Update actor auth code to stop assuming dicts

Files:
- `packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`

Pattern:

```python
principal = AuthPrincipal.coerce(tx.meta.get('user'))
ctx = AccessContext(user=principal, ...)

if not principal.is_authenticated:
    return tx.error('Authentication required', code=401)
```

Intent: `tx.meta['user']` may be a dict, `AuthPrincipal`, or model-like object during migration; auth remains stable.

### 6. Fix agents by using principal explicitly

Files:
- `packages/n3tx-agents/src/n3tx_agents/deps.py`
- `packages/n3tx-agents/src/n3tx_agents/mixin.py`
- `packages/n3tx-agents/src/n3tx_agents/tools.py`

Plan:

```python
@dataclass
class AgentDeps:
    principal: AuthPrincipal | None
    agent_addr: str

    @property
    def user(self):
        # temporary compatibility
        return self.principal.as_dict() if self.principal else None
```

At the start of `AgentMixin.run()` and `run_stream()`:

```python
principal = AuthPrincipal.coerce(user)
deps = AgentDeps(principal=principal, agent_addr=agent_addr)
```

Thread CRUD helpers should receive `principal`, not arbitrary `user`:

```python
meta = {'user': principal}
payload['user_owner'] = principal.user_id
```

Tool calls should use the same principal:

```python
meta = {'user': ctx.deps.principal}
```

Then remove `_thread_user()`.

## 🧩 Implementation Slices

### Slice 1 — Define and test the principal primitive

Files:
- `packages/n3tx-core/src/n3tx_core/authorize/principal.py`
- `packages/n3tx-core/src/n3tx_core/authorize/context.py`
- `packages/n3tx-core/src/n3tx_core/authorize/__init__.py`
- core auth unit tests

Tests to add:

- `AuthPrincipal.coerce(None)` is anonymous.
- `AuthPrincipal.coerce(jwt_dict)` preserves `user_id/email/role` and claims.
- `AuthPrincipal.coerce(user_model_like)` reads `.id`, `.email`, `.role`.
- `AccessContext(user=dict).user_id` still works.
- `AccessContext(user=AuthPrincipal).is_authenticated` works.

### Slice 2 — Migrate direct route auth context

Files:
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

Changes:

- Add `_get_principal(request)`.
- Build `AccessContext` with principal.
- Inject protected `user_owner` from `principal.user_id`.
- Update `_resolve_user()` to use principal and support `Optional[User]`.
- Keep `_get_user()` for response compatibility until a later cleanup.

Tests:

- Existing direct CRUD/auth tests pass.
- Add/adjust a direct custom method test for `user: Optional[User] = None` resolving to the full model.

### Slice 3 — Migrate actor routing and two-tier auth

Files:
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`

Changes:

- Normalize request user into principal in `NetworkAPI` handlers.
- Store principal in `tx.meta['user']`.
- Update `auth_interceptor` and `ActorModel._authorize()` to use principal accessors.
- Update `_parse_method_args()` to use the same `resolve_method_user()` shape as direct routes.

Tests:

- Existing actors example auth tests pass.
- Add actor custom method test for `Optional[User]`.
- Add regression that `tx.meta['user']` as dict and as `AuthPrincipal` both authorize correctly.

### Slice 4 — Migrate agents Thread/tool auth

Files:
- `packages/n3tx-agents/src/n3tx_agents/deps.py`
- `packages/n3tx-agents/src/n3tx_agents/mixin.py`
- `packages/n3tx-agents/src/n3tx_agents/tools.py`
- `packages/n3tx-agents/src/n3tx_agents/thread.py` tests only unless behavior changes

Changes:

- Normalize `user` once at the top of `run()` / `run_stream()`.
- Rename internal variable to `principal`.
- Pass principal through `AgentDeps` and Thread CRUD TX meta.
- Set `Thread.user_owner` from `principal.user_id`.
- Remove `_thread_user()`.

Tests:

- Regression: route-injected full User passed to `AgentMixin.run(user=user)` creates/updates Thread under correct owner.
- Cross-user denial: user 2 cannot get/update a thread owned by user 1 through actor-routed Thread CRUD.
- Tool auth propagation still sends authenticated principal to tool TX meta.

### Slice 5 — Documentation and deprecation cleanup

Files:
- `docs/AUTHORIZATION.md`
- `docs/AGENTS.md`
- `BACKEND.md`
- `packages/n3tx-core/docs/authorization.md`
- `packages/n3tx-agents/docs/mixin.md`

Docs should explicitly state:

- Auth principal is the internal auth identity.
- Custom method `user: User` is application convenience, not the auth context.
- `tx.meta['user']` carries an auth principal-compatible object.
- Agent tools and thread CRUD propagate principal, not arbitrary route user objects.

## 🧪 Verification Plan

Run in this order:

```bash
/workspace/.venv/bin/python scripts/run-backend-tests.py --suite core -- -q
/workspace/.venv/bin/python scripts/run-backend-tests.py --suite actors -- -q
/workspace/.venv/bin/python scripts/run-backend-tests.py --suite agents -- -q
/workspace/.venv/bin/python scripts/run-backend-tests.py --suite examples-core -- -q
/workspace/.venv/bin/python scripts/run-backend-tests.py --suite examples-actors -- -q
/workspace/.venv/bin/python scripts/run-backend-tests.py --suite examples-grants -- -q
```

Focused tests worth adding/running before full suites:

```bash
/workspace/.venv/bin/python -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/ -q -k 'auth or principal or user'
/workspace/.venv/bin/python -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py packages/n3tx-agents/src/n3tx_agents/tests/test_tool_call_auth.py -q
```

## ⚠️ Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Existing code expects `dict.get()` | Interceptor/tests use `user.get(...)` | `AuthPrincipal.get()` compatibility during migration |
| TX metadata serialization | Dataclass in TX meta may not be JSON-safe for some adapters | Convert to `as_dict()` at external wire boundaries if needed; keep `AccessContext` coercion |
| App methods rely on full `User` | Examples use `user.id` | Preserve method user injection behavior |
| Optional type hints are currently under-supported | `Optional[User]` can receive dict today | Add type unwrap helper and tests |
| Internal messages bypass auth | Existing documented behavior | Do not change in this refactor; only normalize when auth context exists |
| `user_id=0` semantic change | Current `bool(user_id)` treats 0 as unauthenticated | Decide explicitly in tests; recommended principal uses `is not None` |

## 🚫 Non-goals

- Do not remove `user: User = None` method injection.
- Do not redesign JWT token payloads.
- Do not change access rule semantics beyond principal normalization.
- Do not make all internal actor messages authenticated.
- Do not require `authorize` to import N3TX model classes.

## ✅ Handoff Summary

The tactical `_thread_user()` helper should be treated as evidence of a boundary problem, not as the final design. The durable solution is a canonical, dependency-free principal contract in `n3tx_core.authorize`, used by `AccessContext`, HTTP routes, actor auth, agent tools, and thread CRUD. Business methods may still receive full `User` model instances, but auth must always consume a normalized principal.

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/authorize/context.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py`
- `packages/n3tx-agents/src/n3tx_agents/mixin.py`
