# Authorization & Authentication

The `authorize/` package provides JWT-based authentication and a Policy-as-Schema ABAC (Attribute-Based Access Control) authorization layer. It is a **standalone package** with zero framework dependencies — it can be used in any Python project, not just PyBend.

## Table of Contents

- [Quick Start](#quick-start)
- [Authentication (JWT)](#authentication-jwt)
- [Authorization (ABAC)](#authorization-abac)
  - [Declaring Access Rules on Models](#declaring-access-rules-on-models)
  - [Declaring Access Rules on Methods](#declaring-access-rules-on-methods)
  - [Built-in Rules](#built-in-rules)
  - [Composing Rules](#composing-rules)
  - [The Where Rule](#the-where-rule)
- [Architecture](#architecture)
  - [Request Lifecycle](#request-lifecycle)
  - [SQL Pushdown](#sql-pushdown)
  - [Schema Exposure](#schema-exposure)
  - [The Resolver Protocol](#the-resolver-protocol)
- [Extending the System](#extending-the-system)
  - [Custom Rules](#custom-rules)
  - [Swapping the Resolver](#swapping-the-resolver)
- [Reference](#reference)

---

## Quick Start

```python
from authorize import ANYONE, AUTHENTICATED, OWNER, ROLE, Where

class Product(ProtoModel):
    __storable__ = True
    __tablename__ = 'products'
    __owner_field__ = 'user_owner'
    __access__ = {
        'read':   ANYONE,
        'list':   ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }

    name: str
    user_owner: Ref[User] = None

    @expose_route('/publish', methods=['POST'], access=OWNER & Where(status='draft'))
    def publish(self): ...
```

That's it. CRUD routes are automatically protected. Custom methods use the `access=` parameter.

---

## Authentication (JWT)

### How It Works

1. User calls `POST /users/login` with email + password
2. Server verifies credentials, returns a JWT token
3. Client sends `x-access-token: <token>` header on every request
4. `JWTAuthMiddleware` decodes the token and stores the payload in `request.state.user`

### Token Payload

```json
{
    "user_id": 1,
    "email": "alice@example.com",
    "role": "user",
    "exp": 1771678445,
    "iat": 1771592045
}
```

The `role` field is read from the `User.role` model field and embedded in the token at login/register time.

### Configuration

The package reads `JWT_SECRET` and `JWT_EXPIRY_HOURS` from environment variables by default. To override, call `configure()` at application startup:

```python
import authorize

authorize.configure(
    jwt_secret="your-production-secret",
    jwt_expiry_hours=48,
)
```

In PyBend, this is done in `main.py` using values from `config.py`.

### Key Functions (`authorize/auth.py`)

| Function | Purpose |
|---|---|
| `configure(jwt_secret, jwt_expiry_hours)` | Set JWT config at startup |
| `hash_password(plain)` | Bcrypt hash for storage |
| `verify_password(plain, hashed)` | Bcrypt verification |
| `create_token(user_id, email, role)` | Creates a signed JWT |
| `decode_token(token)` | Validates and decodes a JWT |

### Auth-Exempt Paths

The JWT middleware skips authentication for:
- `/login`, `/register`, `/docs`, `/openapi.json`, `/redoc`
- Static files: `.html`, `.js`, `.css`, `.png`, `.ico`, `.svg`, `.woff`, `.woff2`, `.ttf`

These are configured in `FastAPIBackend.AUTH_EXEMPT_PATHS` and `AUTH_EXEMPT_EXTENSIONS`.

---

## Authorization (ABAC)

Authorization happens **after** authentication. The middleware verifies identity; the authorize layer decides what that identity can do.

### Declaring Access Rules on Models

Add an `__access__` class variable mapping action names to rules:

```python
class Comment(ProtoModel):
    __access__ = {
        'create': AUTHENTICATED,
        'read':   ANYONE,
        'list':   ANYONE,
        'update': OWNER,
        'delete': OWNER | ROLE('admin', 'moderator'),
    }
    __owner_field__ = 'user_owner'  # which field holds the owner's user ID
```

**Action names** correspond to CRUD operations: `create`, `read`, `list`, `update`, `delete`.

**Wildcard fallback:** Use `'*'` as a catch-all for any action not explicitly listed:

```python
__access__ = {
    '*': AUTHENTICATED,          # default for all actions
    'delete': ROLE('admin'),     # override for delete
}
```

**No `__access__` at all:** Falls back to `AUTHENTICATED` for all actions (backward compatible).

### Protected Fields

Models can declare `__protected_fields__` to mark fields as backend-owned:

```python
class Comment(ProtoModel):
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }
```

**What protected fields do:**

| Layer | Behavior |
|-------|----------|
| **Create** | Route layer auto-injects `user_owner` from JWT payload (`user_id`) |
| **Update** | Route layer strips protected fields from incoming data — cannot be modified via API |
| **Schema** | Marked with `ui.protected = true` in JSON Schema properties |
| **Frontend** | `form.js` hides protected fields in edit mode; display mode shows them normally |

This ensures that ownership assignment is server-authoritative — clients can never set or change `user_owner` directly.

### Declaring Access Rules on Methods

Custom methods use the `access=` parameter on `@expose_route()`:

```python
@expose_route('/like', methods=['POST'], access=AUTHENTICATED)
def like(self) -> str: ...

@expose_route('/admin-reset', methods=['POST'], access=ROLE('admin'))
def admin_reset(self) -> str: ...

@expose_route('/login', methods=['POST'], access=ANYONE)
def login(email: str, password: str) -> dict: ...
```

If no `access=` is provided, the method falls back to the model's `__access__` dict, then to `AUTHENTICATED`.

### Built-in Rules

| Rule | Grants access when... | SQL filter |
|---|---|---|
| `ANYONE` | Always | `1=1` (no filter) |
| `AUTHENTICATED` | User has a valid JWT | `1=1` (middleware handles) |
| `OWNER` | `resource.{owner_field} == user.id` (handles FK-hydrated hrefs) | `{owner_field} = ?` |
| `ROLE('admin')` | `user.role == 'admin'` | `1=1` if match, `1=0` if not |
| `ROLE('a', 'b')` | `user.role in {'a', 'b'}` | Same |
| `Where(field=val)` | `resource.field == val` | `field = ?` |

### Composing Rules

Rules compose with Python operators:

```python
# OR: either condition grants access
OWNER | ROLE('admin')

# AND: both conditions must be true
OWNER & Where(status='draft')

# NOT: inverts the rule
~ROLE('banned')

# Complex:
(OWNER | ROLE('admin')) & ~ROLE('suspended')
```

Composites produce `OrRule`, `AndRule`, `NotRule` objects that evaluate recursively and generate combined SQL.

### The Where Rule

`Where` checks resource attributes with optional comparison operators:

```python
Where(status='published')           # status = 'published'
Where(price__lt=100)                # price < 100
Where(price__gte=50)                # price >= 50
Where(category__in=['A', 'B'])      # category IN ('A', 'B')
Where(status__ne='archived')        # status != 'archived'
```

Supported operators: `__lt`, `__gt`, `__lte`, `__gte`, `__ne`, `__in`.

---

## Architecture

### Package Layout

```
authorize/
  __init__.py       Public API re-exports
  auth.py           JWT: password hashing, token create/decode
  rules.py          AccessRule base class + all built-in rules
  context.py        AccessContext dataclass
  resolver.py       AuthorizationResolver Protocol + DefaultResolver
  errors.py         AccessDenied exception
  schema.py         Serialize access rules for JSON Schema
```

### Request Lifecycle

```
Client request
    │
    ▼
JWTAuthMiddleware (api/backend.py)
    │  Decodes JWT → request.state.user = {user_id, email, role}
    │  Returns 401 if missing/invalid (except exempt paths)
    ▼
Route handler (api/routes_fastapi.py)
    │  Builds AccessContext(user, action, model_class, resource)
    │  Calls _resolver.authorize(ctx) or _resolver.sql_filter_for(ctx)
    ▼
DefaultResolver (authorize/resolver.py)
    │  Reads model.__access__[action] → AccessRule
    │  Falls back: __access__['*'] → AUTHENTICATED
    ▼
AccessRule.evaluate(ctx) → True/False
    │  If False → AccessDenied → HTTP 403
    │  If True  → proceed to storage operation
    ▼
For list queries: AccessRule.sql_filter(ctx)
    │  Returns (WHERE_clause, params) → injected into SQL
    ▼
Storage layer executes query with authorization filter
```

### SQL Pushdown

For `list` operations, the authorization rule produces a SQL WHERE clause that is injected directly into the database query. This avoids loading all rows and filtering in Python.

```python
# OWNER rule for user_id=5:
sql_filter = ("user_owner = ?", [5])
# Becomes: SELECT * FROM products WHERE user_owner = 5

# Composite OWNER | ROLE('admin') for an admin:
sql_filter = ("(user_owner = ?) OR (1=1)", [5])
# Simplifies to: all rows (admin sees everything)

# Where(visibility='public') for non-owner:
sql_filter = ("visibility = ?", ["public"])
# Becomes: SELECT * FROM products WHERE visibility = 'public'
```

If a rule cannot produce SQL (returns `None` from `sql_filter()`), no filter is applied. Custom rules that can't express their logic as SQL should fall back to `None`.

### Schema Exposure

Access rules are serialized into the JSON Schema response so frontends can adapt their UI:

```json
{
    "$schema": "http://localhost:5000/Schema",
    "$id": "http://localhost:5000/Product",
    "properties": { ... },
    "methods": {
        "publish": {
            "route": "/publish",
            "methods": ["POST"],
            "access": {"op": "and", "rules": [{"rule": "owner"}, {"rule": "where", "conditions": {"status": "draft"}}]}
        }
    },
    "access": {
        "read": {"rule": "anyone"},
        "create": {"rule": "authenticated"},
        "update": {"op": "or", "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin"]}]},
        "delete": {"rule": "role", "roles": ["admin"]}
    }
}
```

Frontends can use the `access` key to show/hide edit buttons, delete icons, etc.

### The Resolver Protocol

The `DefaultResolver` is one implementation of the `AuthorizationResolver` protocol:

```python
class AuthorizationResolver(Protocol):
    def resolve_rule(self, model_class, action: str) -> AccessRule: ...
    def authorize(self, ctx: AccessContext) -> None: ...
    def sql_filter_for(self, ctx: AccessContext) -> tuple[str, list] | None: ...
```

The resolver is instantiated once in `routes_fastapi.py` as `_resolver = DefaultResolver()`. To swap strategies, replace that single line.

---

## Extending the System

### Custom Rules

Subclass `AccessRule` to create domain-specific rules:

```python
from authorize import AccessRule

class IsVerifiedEmail(AccessRule):
    """Only allows users with verified email domains."""
    def __init__(self, *domains):
        self.domains = domains

    def evaluate(self, ctx):
        if not ctx.is_authenticated:
            return False
        email = ctx.user_email or ''
        return any(email.endswith(f'@{d}') for d in self.domains)

    def sql_filter(self, ctx):
        # Can't express email domain check as SQL on the resource table
        return None

    def to_dict(self):
        return {"rule": "verified_email", "domains": list(self.domains)}
```

Usage:

```python
class InternalTool(ProtoModel):
    __access__ = {
        '*': IsVerifiedEmail('company.com', 'company.org'),
    }
```

Custom rules compose with built-in rules via `|`, `&`, `~`:

```python
__access__ = {
    'read': IsVerifiedEmail('company.com') | ROLE('admin'),
}
```

### Swapping the Resolver

To add DB-stored policy overrides, implement the protocol:

```python
class OverrideResolver:
    def __init__(self, base_resolver, override_store):
        self.base = base_resolver
        self.store = override_store

    def resolve_rule(self, model_class, action):
        override = self.store.get(model_class.__tablename__, action)
        if override:
            return override
        return self.base.resolve_rule(model_class, action)

    def authorize(self, ctx):
        rule = self.resolve_rule(ctx.model_class, ctx.action)
        if not rule.evaluate(ctx):
            raise AccessDenied(...)

    def sql_filter_for(self, ctx):
        rule = self.resolve_rule(ctx.model_class, ctx.action)
        return rule.sql_filter(ctx)
```

Then in `routes_fastapi.py`:

```python
_resolver = OverrideResolver(DefaultResolver(), db_override_store)
```

---

## Reference

### AccessContext Fields

| Field | Type | Description |
|---|---|---|
| `user` | `dict` | JWT payload |
| `action` | `str` | Action being performed |
| `model_class` | `Type` | The ProtoModel subclass |
| `resource` | `Any \| None` | The specific instance (None for list/create) |
| `parent_id` | `int \| None` | Parent resource ID for nested routes |
| `user_id` | `int \| None` | Property: `user['user_id']` |
| `user_role` | `str \| None` | Property: `user['role']` |
| `user_email` | `str \| None` | Property: `user['email']` |
| `is_authenticated` | `bool` | Property: user_id is present |

### Settings

| Setting | How to set | Default |
|---|---|---|
| `JWT_SECRET` | `configure(jwt_secret=...)` or `JWT_SECRET` env var | `authorize-dev-secret-change-in-production` |
| `JWT_EXPIRY_HOURS` | `configure(jwt_expiry_hours=...)` or `JWT_EXPIRY_HOURS` env var | `24` |
| Default role | `User.role` field default (app-level) | `'user'` |
| Default access | `DefaultResolver` fallback | `AUTHENTICATED` |
