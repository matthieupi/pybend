# Authorization

> Part of [n3tx-core](../README.md)

## What This Covers

The `authorize` subpackage: access rules, the resolver protocol, JWT auth, SQL pushdown, and how rules flow into JSON Schema. This package has zero N3TX imports -- it is standalone by design.

## Architecture

```
Model __access__ dict
  |
  v
DefaultResolver.resolve_rule(model_class, action)
  |
  +-- __access__[action]       -- Exact match
  +-- __access__['*']          -- Wildcard fallback
  +-- AUTHENTICATED            -- Global fallback (no __access__)
  |
  v
AccessRule.evaluate(ctx)       -- Boolean: grant or deny
AccessRule.sql_filter(ctx)     -- SQL WHERE clause for list pushdown
AccessRule.to_dict()           -- JSON serialization for schema
```

The route layer constructs an `AccessContext` from the HTTP request, then calls the resolver. For list endpoints, `sql_filter_for()` returns a WHERE clause that the storage layer appends to the SELECT query -- authorization is pushed down to the database.

## Interface

### Access Rules

| Rule | Constructor | Behavior |
|------|-------------|----------|
| `ANYONE` | singleton | Always grants. SQL: `1=1` |
| `NEVER` | singleton | Always denies. SQL: `1=0` |
| `AUTHENTICATED` | singleton | Grants if `user_id` present in JWT |
| `OWNER` | singleton | Grants if `user_id == resource.__owner_field__` |
| `ROLE('admin')` | factory | Grants if `user.role` in allowed set |
| `Where(status='published')` | factory | Grants if `resource.status == 'published'` |
| `FEDERATED` | singleton | Grants for federated (non-local) actors |
| `LOCAL` | singleton | Grants for local (non-federated) users |
| `FOLLOWER` | singleton | Grants if user follows resource owner |

### Rule Composition

```python
OWNER | ROLE('admin')                    # OR: owner or admin
AUTHENTICATED & Where(status='published') # AND: authenticated + published
~ANYONE                                  # NOT: equivalent to NEVER

# Algebraic properties:
# A & NEVER == NEVER  (annihilation)
# A | NEVER == A      (identity)
# A | ANYONE == ANYONE (absorption)
```

### Where Operators

```python
Where(status='published')       # field = value
Where(price__gt=10)             # field > value
Where(price__lt=100)            # field < value
Where(price__gte=10)            # field >= value
Where(price__lte=100)           # field <= value
Where(status__ne='draft')       # field != value
Where(role__in=['admin','mod']) # field IN (...)
```

### AccessContext

```python
@dataclass(frozen=True)
class AccessContext:
    user: dict           # JWT payload: {user_id, email, role}
    action: str          # 'read', 'create', 'update', 'delete', or method name
    model_class: Type    # The model class being accessed
    resource: Any = None # The specific instance (None for create/list)
    parent_id: int = None

    # Properties:
    user_id -> int | None
    user_role -> str | None
    is_authenticated -> bool
```

### DefaultResolver

```python
class DefaultResolver:
    def resolve_rule(self, model_class, action) -> AccessRule: ...
    def authorize(self, ctx: AccessContext) -> None: ...        # Raises AccessDenied
    def sql_filter_for(self, ctx: AccessContext) -> tuple: ...  # (WHERE, params)
```

### Auth Functions

```python
from n3tx_core.authorize import configure, hash_password, verify_password, create_token, decode_token

configure(jwt_secret='...', jwt_expiry_hours=24)  # Call once at startup
hashed = hash_password('plain')
ok = verify_password('plain', hashed)
token = create_token(user_id=1, email='a@b.com', role='user')
payload = decode_token(token)  # -> {user_id, email, role, exp, iat}
```

## Usage Patterns

### Model-Level Access

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __owner_field__ = 'user_owner'  # Field checked by OWNER rule (default: 'user_owner')
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }
    user_owner: int = Field(default=0)
```

### Method-Level Access

```python
@expose_route('/publish', methods=['POST'], access=OWNER & Where(status='draft'))
def publish(self) -> str:
    self.status = 'published'
    return 'Published'
```

### Custom Resolver

```python
from n3tx_core.authorize import AuthorizationResolver, AccessRule, AccessContext

class TenantResolver:
    def resolve_rule(self, model_class, action) -> AccessRule:
        # Custom resolution logic
        ...
    def authorize(self, ctx: AccessContext) -> None:
        ...
    def sql_filter_for(self, ctx: AccessContext) -> tuple:
        ...
```

## Gotchas

- **No `__access__` defaults to `AUTHENTICATED` for all actions.** This is backward compatible -- unauthenticated users cannot access models without explicit `ANYONE` rules.
- **OWNER rule returns True for create actions** when no resource exists yet (ownership is established at creation time). The `user_owner` field is auto-injected from the JWT by the route layer.
- **OWNER checks href-hydrated values.** If `user_owner` is stored as `3` but hydrated to `http://localhost:5000/users/3`, the OWNER rule extracts the trailing ID from the href string.
- **`sql_filter` returns None for non-filterable rules.** When a rule cannot produce a SQL clause (e.g., requires resource-level data), it returns `None`. OrRule/AndRule return `None` if any child returns `None`.
- **Insecure JWT secrets trigger warnings.** The auth module checks against a known list of default secrets and emits a `UserWarning` at startup. Always set `N3TX_JWT_SECRET` in production.
- **The authorize package is imported as `n3tx_core.authorize`** in the split-package layout. The old import `from authorize import ...` no longer works.
