"""Tier 1 auth interceptor for NetworkAPI.

Registered on a NetworkAdapter via: adapter.use(auth_interceptor, on='request')

Fast gate at the protocol boundary. Rejects obviously unauthorized requests
before they enter the actor system. Does NOT replace Tier 2 (handler_crud
_authorize) — that handles resource-dependent OWNER checks.

Tier 1 handles:
    - schema: pass-through (always public)
    - custom methods: check method-level access from @expose_route
    - list: compute sql_filter and store in tx.meta['sql_filter']
    - create: full rule check (no resource instance needed)
    - read/update/delete: identity gate only (OWNER check deferred to Tier 2)
"""

from pybend.core.actors.tx import TX
from pybend.core.authorize import AccessContext, DefaultResolver, AccessDenied

_resolver = DefaultResolver()

# CRUD message names handled at model level
_CRUD_OPS = frozenset({'schema', 'create', 'get', 'list', 'update', 'delete'})

# Map TX action names to __access__ semantic names (Level 1/2 uses 'read', TX uses 'get')
_ACCESS_ACTION = {'get': 'read', 'list': 'read'}  # others map 1:1


def _get_method_access(model_cls, method_name):
    """Look up the access rule from @expose_route on a custom method.

    Returns the access rule if found, None otherwise.
    """
    attr = getattr(model_cls, method_name, None)
    if attr and callable(attr) and hasattr(attr, '__endpoint__'):
        return attr.__endpoint__.get('access')
    return None


async def auth_interceptor(tx: TX) -> TX:
    """Tier 1: Authentication gate + sql_filter computation.

    Interceptor signature: async (TX) -> TX
    Returns error TX to short-circuit (request rejected before entering actor system).
    """
    model_cls = tx.meta.get('model_cls')
    if not model_cls:
        return tx  # No model context (e.g., non-model request)

    action = tx.name.lower()
    user = tx.meta.get('user', {})

    if action == 'schema':
        return tx  # Schemas are always public

    # Custom methods (non-CRUD): check method-level access from @expose_route
    if action not in _CRUD_OPS:
        method_access = _get_method_access(model_cls, action)
        if method_access is not None:
            ctx = AccessContext(user=user, action=action, model_class=model_cls)
            if not method_access.evaluate(ctx):
                return tx.error("Access denied", code=403)
            return tx
        # No @expose_route access found — fall through to model-level check

    # Map TX action to semantic access action (e.g., 'get' -> 'read')
    access_action = _ACCESS_ACTION.get(action, action)

    # Fall through to model-level __access__ check (resolver defaults to AUTHENTICATED)

    if action == 'list':
        # Compute SQL filter (handles OWNER as WHERE clause via sql_filter_for)
        ctx = AccessContext(user=user, action=access_action, model_class=model_cls)
        try:
            tx.meta['sql_filter'] = _resolver.sql_filter_for(ctx)
        except AccessDenied as e:
            return tx.error(str(e), code=403)
        return tx

    if action == 'create':
        # Full check — no resource instance needed for create
        rule = _resolver.resolve_rule(model_cls, 'create')
        ctx = AccessContext(user=user, action='create', model_class=model_cls)
        if not rule.evaluate(ctx):
            return tx.error("Access denied", code=403)
        return tx

    # read/update/delete: identity gate only
    # Full OWNER/Where check happens at Tier 2 (handler_crud has the instance)
    rule = _resolver.resolve_rule(model_cls, access_action)
    ctx = AccessContext(user=user, action=access_action, model_class=model_cls)
    # Rules like ANYONE pass through even without a user. OWNER/ROLE/AUTHENTICATED
    # fail if no user_id — the rule's evaluate() handles this correctly.
    if not rule.evaluate(ctx):
        if not user.get('user_id'):
            # Unauthenticated: reject with 403 (matches Level 1/2 AccessDenied behavior).
            # OWNER/ROLE rules that need a resource are deferred to Tier 2, but only
            # for authenticated users — unauthenticated users always fail here.
            return tx.error("Access denied", code=403)
        # Authenticated user — pass through to Tier 2 for resource-level check
    return tx
