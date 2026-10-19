# Authorization & Authentication

`n3tx_core.authorize` contains JWT helpers and composable access rules. It has
no N3TX model imports. Entrypoints supply identity and resource context; a model
declaration alone does not protect every way of calling Python code.

## Quick Start

Use the [tutorial](GETTING_STARTED.md) for a complete tested policy: users can
register/login, read their own identity, and create/read/update/delete their own
issues; labels are public. It deliberately avoids a broad authenticated list
policy because of the direct-list limitation below.

## Authentication (JWT)

BaseUser login verifies a bcrypt hash and returns `{token, user}`. The client sends
`x-access-token: <JWT>`. Middleware verifies a supplied token and installs its
payload as `request.state.user`; invalid/expired tokens return 401. **A missing
token is not rejected by middleware**: it installs empty identity and continues.
Static asset extensions bypass token processing.

Tokens contain `user_id`, `email`, `role`, `iat`, `exp`. Roles are a login-time
snapshot, not reloaded on every request. Changing a user's stored role does not
retroactively change existing claims. Secret rotation invalidates old tokens;
the basic helpers do not provide a per-token revocation service.

Set `N3TX_JWT_SECRET` before bootstrap, or pass `jwt_secret` explicitly. Factory
`jwt_expiry_hours` defaults to 24; pass it explicitly when changing expiry.

⚠️ `BaseUser.register_user()` is explicitly ANYONE and assigns **admin** under
global DEBUG. Use `N3TX_DEBUG=false`. `debug=False` does not reset an already true
global config. User model `__access__` does not override the inherited method's
explicit ANYONE rule. Closing registration requires a deliberate application
method/policy change, not just a wildcard on generic CRUD.

Generic User writes can allow role or password-hash manipulation if you grant
them. The tutorial denies generic create/update/delete and uses inherited auth
methods. BaseUser does not supply email verification, password-reset workflow,
rate limiting or concurrent uniqueness enforcement.

## Authorization (ABAC)

### Declaring Access Rules on Models

Resolution order is exact action key, `'*'`, then AUTHENTICATED. `read` and `list`
are separate actions; setting one does not configure the other.

```python
__owner_field__ = 'user_owner'
__protected_fields__ = {'user_owner'}
__access__ = {
    '*': NEVER,
    'create': AUTHENTICATED,
    'read': OWNER, 'list': OWNER,
    'update': OWNER, 'delete': OWNER,
}
```

This is a class-body fragment; import rules from `n3tx_core.authorize` and declare
`user_owner: int = 0`. Ownership must be assigned by trusted code, not a client
claim. In direct generated create, protected `user_owner` is injected from JWT.
Generated update strips all protected fields. Other protected fields are not
generically stripped on create; define defaults/validators and policies accordingly.

### Declaring Access Rules on Methods

`@expose_route(..., access=OWNER)` takes precedence over model fallback. Without
explicit access, the direct route resolves policy using the **Python method
name**, not its URL suffix. Reserved `user` is injected from identity, never read
from the body. See [custom endpoints](API_CUSTOM_ENDPOINTS.md).

### Built-in Rules

| Rule | Evaluation | List behavior |
|---|---|---|
| ANYONE | Always true | Unrestricted |
| NEVER | Always false | Empty result |
| AUTHENTICATED | Identity has user_id | Unrestricted SQL, including anonymous direct list requests |
| OWNER | Authenticated owner matches resource | Owner-column filter; anonymous returns empty |
| ROLE('admin', 'moderator') | Authenticated role in set | Unrestricted if matched, empty otherwise |
| Where(status='published') | Resource attribute condition | Matching SQL condition |

OWNER with no resource returns true for an authenticated caller. Where with no
resource also returns true. These are not ownership/attribute checks on an
arbitrary create payload or class action.

### Composing Rules

`|` is OR, `&` is AND, `~` is NOT. Evaluation and SQL generation are separate
contracts. `AUTHENTICATED & Where(...)` does not fix the direct-list identity
gap because AUTHENTICATED's SQL fragment is still `1=1`.

### The Where Rule

Equality and `__lt`, `__gt`, `__lte`, `__gte`, `__ne`, `__in` are supported.
Use trusted model field names and test NULL/composite cases against actual SQL;
do not accept arbitrary user-written SQL conditions.

## Architecture

| Entrypoint | Enforcement boundary | Important limit |
|---|---|---|
| Public schema / HTML shell | No entity policy evaluation | Metadata and presentation are discoverable |
| Direct create/read/update/delete | DefaultResolver.authorize | Trusted internal calls bypass this |
| Direct list | DefaultResolver.sql_filter_for | No separate authorize call; AUTHENTICATED and None-filter gaps |
| Direct exposed action | Explicit access or resolver, then reserved caller injection | Internal reads/writes need their own target policy |
| Actor HTTP | NetworkAPI interceptor plus actor handlers | Verify configured adapter, list and method paths separately |
| Raw TX | Actor dispatch/handler path | Does not necessarily traverse HTTP request interceptors |
| Agent tool | Tool selection then TX execution | Discovery is not authorization; caller propagation must be tested |
| Direct Python CRUD | No automatic route policy | Trusted application boundary |
| Hydrated/populated child | Storage/serialization | Not independently equivalent to a child HTTP read check |

This is a boundary map, not a blanket transport security certification. Consult
[Actors](ACTORS.md) and [agent tool discovery](../packages/n3tx-agents/docs/tool-discovery.md)
before enabling those paths.

### Request Lifecycle

```text
HTTP identity middleware -> request.state.user
    -> direct member/action: AccessContext -> evaluate -> allow or 403
    -> direct list: AccessContext -> SQL filter -> matching rows
```

### SQL Pushdown

SQL filtering avoids loading all rows, but its current fallback is not fail-closed.
`DefaultResolver.sql_filter_for()` calls only `rule.sql_filter(ctx)`.
AUTHENTICATED returns `('1=1', [])`; a non-filterable rule returns None, meaning
no WHERE restriction. Composite AND/OR returns None when a child cannot produce
SQL. There is no automatic per-row Python fallback in the direct list handler.

Do not use an evaluate-only custom rule to protect lists. Implement a correct
filter or deny/avoid the list exposure until the framework supports the policy.
Test anonymous, wrong-role, wrong-owner, empty and paginated results.

### Schema Exposure

Rules serialize into schema for UI adaptation. `ui.display`, `ui.protected` and
field `access` hints are not general backend field-redaction/write enforcement.
Use appropriate exclusion, policies and response design for secrets. Child
hydration must not leak data through a less-restricted parent.

### The Resolver Protocol

The protocol provides `resolve_rule`, `authorize`, `sql_filter_for`. See
[package API](../packages/n3tx-core/docs/authorization.md). The current app factory
does not expose a global resolver injection parameter; direct routes and actor
components construct resolvers independently. Replacing one module variable is
not a supported all-entrypoint policy migration.

## Extending the System

Custom rules implement evaluation, SQL filtering and schema serialization where
needed. Keep them independent of frontend controls. Test direct HTTP, enabled
actor/tool paths, nested exposure and internal actions. A service token is a
separate trust grant because it permits forwarded user context; see
[remote trust](../packages/n3tx-actors/docs/network-adapters.md#remotematrix-and-remoteref).

## Reference

Canonical details: [authorization API](../packages/n3tx-core/docs/authorization.md),
[BaseUser](MODELS.md#baseuser), [operations checklist](OPERATIONS.md).
