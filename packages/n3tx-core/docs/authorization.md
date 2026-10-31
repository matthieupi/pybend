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

The route layer constructs an `AccessContext` from the HTTP request. Direct
member routes call authorization, but direct list routes call only
`sql_filter_for()`. Evaluation and SQL filtering are separate contracts, not
interchangeable enforcement. See the [entrypoint matrix](../../../docs/AUTHORIZATION.md).

## Interface

### Access Rules

| Rule | Constructor | Behavior |
|------|-------------|----------|
| `ANYONE` | singleton | Always grants. SQL: `1=1` |
| `NEVER` | singleton | Always denies. SQL: `1=0` |
| `AUTHENTICATED` | singleton | Evaluation requires user_id; SQL is `1=1`, even anonymously |
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
    patch: Mapping[str, Any] | None = None

    # Properties:
    user_id -> int | None
    user_role -> str | None
    is_authenticated -> bool
```

`patch` is optional transport-supplied input, not a request-body context. Only
the generated **direct HTTP PUT** routes populate it automatically. They load
the resource, canonicalize aliases (rejecting duplicate spellings), remove
`$id`/`$schema`, then remove `id` and `__protected_fields__` before authorization.
Unknown keys remain visible so allowlist rules can reject them. Values are still
input values, before merged-model validation/coercion. The same effective patch
is passed to `instance.update`; normal model validation and supplied-key
persistence remain authoritative.

Before policy, the stripped patch must also be a fixed point of the model's
canonicalizer: canonicalizing it again must leave the mapping unchanged. A
field name that is also another field's input alias can otherwise redirect the
second pass inside `instance.update`. Such unstable patches return 400 before
authorization, including for admins. This uses the same native alias and
`AliasChoices` resolution as persistence. Stable patches on the same schema
remain usable; unknown keys remain visible and cannot bypass the field policy.

The frozen context deep-copies the supplied mapping and wraps its outer level
in a read-only mapping. Nested values are not recursively frozen, but mutations
to them cannot change the update payload. It is a defensive snapshot, not a
sandbox for untrusted policy code. Existing user/resource inputs are unchanged.

Empty effective input is `{}`, distinct from absent input (`None`). A policy may
deny empty input; an allowed empty patch retains the existing no-op behavior.
For example, an owner-only field policy should require `ctx.patch is not None`
and `set(ctx.patch) == {'active'}` as well as its authenticated owner check.
Protected-field attempts are stripped, not exposed for auditing: an allowed
field plus a protected field becomes the allowed field alone. Alias conflicts
are rejected before stripping, including conflicts on protected fields.

Other direct operations, exposed actions, actor transports and tools do **not**
gain patch propagation from this extension. Patch-dependent rules must deny when
it is absent. Never accept body-supplied `user` or `context` as authorization
input; direct route identity still comes exclusively from middleware.

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
    __protected_fields__ = {'user_owner'}
    user_owner: int = Field(default=0)
```

### Method-Level Access

```python
@expose_route('/publish', methods=['POST'], access=OWNER & Where(status='draft'))
def publish(self) -> str:
    self.update({'status': 'published'})
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

- **Missing policy defaults to AUTHENTICATED, but direct lists remain unrestricted by that rule's SQL.** Do not infer privacy from the default. Test anonymous collection requests explicitly.
- **OWNER rule returns True for create actions** when no resource exists yet (ownership is established at creation time). The `user_owner` field is auto-injected from the JWT by the route layer.
- **OWNER checks href-hydrated values.** If `user_owner` is stored as `3` but hydrated to `http://localhost:5000/users/3`, the OWNER rule extracts the trailing ID from the href string.
- **None SQL filters are not fail-closed.** Non-filterable rules can return None;
  OrRule/AndRule propagate None if a child does. Direct lists then have no policy
  restriction and do not fall back to per-row evaluation. Private collection
  policies must provide a correct SQL predicate, including anonymous denial.
- **Python CRUD is trusted.** Calling Model.get/list/update directly does not run
  route authorization. Schema rule metadata and frontend hiding are not security
  gates. Verify caller propagation separately for actors and tools.
- **Insecure JWT secrets trigger warnings.** The auth module checks against a known list of default secrets and emits a `UserWarning` at startup. Always set `N3TX_JWT_SECRET` in production.
- **The authorize package is imported as `n3tx_core.authorize`** in the split-package layout. The old import `from authorize import ...` no longer works.
