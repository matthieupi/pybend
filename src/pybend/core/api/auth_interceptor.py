"""Tier 1 auth interceptor for NetworkAPI.

Registered on a NetworkAdapter via: adapter.use(auth_interceptor, on='request')

Fast gate at the protocol boundary. Rejects obviously unauthorized requests
before they enter the actor system. Does NOT replace Tier 2 (handler_crud
_authorize) — that handles resource-dependent OWNER checks.

Tier 1 handles:
    - schema: pass-through (always public)
    - list: compute sql_filter and store in tx.meta['sql_filter']
    - create: full rule check (no resource instance needed)
    - read/update/delete: identity gate only (OWNER check deferred to Tier 2)
"""

from pybend.core.actors.tx import TX
from pybend.core.authorize import AccessContext, DefaultResolver, AccessDenied

_resolver = DefaultResolver()


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

    access = getattr(model_cls, '__access__', None)

    if not access:
        # No __access__ declared -> default AUTHENTICATED for all actions
        if not user.get('user_id'):
            return tx.error("Authentication required", code=401)
        return tx

    if action == 'list':
        # Compute SQL filter (handles OWNER as WHERE clause via sql_filter_for)
        ctx = AccessContext(user=user, action='list', model_class=model_cls)
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
    rule = _resolver.resolve_rule(model_cls, action)
    ctx = AccessContext(user=user, action=action, model_class=model_cls)
    # Only reject if the rule requires authentication and user is not authenticated.
    # Rules like ANYONE pass through even without a user. OWNER/ROLE/AUTHENTICATED
    # fail if no user_id — the rule's evaluate() handles this correctly.
    if not rule.evaluate(ctx):
        # For unauthenticated users: 401. For authenticated but denied: let Tier 2 handle
        # (Tier 1 can't check OWNER without the resource, so if the user IS authenticated
        #  we pass through and let Tier 2 do the full check)
        if not user.get('user_id'):
            return tx.error("Authentication required", code=401)
        # Authenticated user — pass through to Tier 2 for resource-level check
    return tx
