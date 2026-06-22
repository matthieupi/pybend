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

from n3tx_actors.tx import TX
from n3tx_core.authorize import AccessContext, DefaultResolver, AccessDenied
from n3tx_core.utils.decorators import exposed_method_info

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


def _method_requires_instance(model_cls, method_name):
    """Return True when a custom method needs a resource instance.

    Actor routing cannot make a final resource-aware auth decision in Tier 1
    because the NetworkAPI boundary has not loaded the target row. Use the
    same exposed-method metadata as schema/tool routing when available, and
    fall back to signature inspection for plain decorated methods.
    """
    exposed = exposed_method_info(model_cls, method_name)
    if exposed is not None:
        return exposed.requires_instance

    attr = getattr(model_cls, method_name, None)
    if not callable(attr):
        return False
    try:
        import inspect
        return 'self' in inspect.signature(attr).parameters
    except (TypeError, ValueError):
        return False


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
            if _method_requires_instance(model_cls, action):
                # Instance-method access can depend on the target resource.
                # Tier 1 only rejects anonymous callers when the rule cannot
                # allow them without a resource; authenticated users continue
                # to Tier 2, where ActorModel.handler loads the instance and
                # evaluates the final AccessContext(resource=instance).
                if not user.get('user_id') and not method_access.evaluate(ctx):
                    return _deny(tx, user)
                return tx
            if not method_access.evaluate(ctx):
                return _deny(tx, user)
            return tx
        # No explicit access= on @expose_route — default to AUTHENTICATED (matches Level 1/2)
        if not user.get('user_id'):
            return tx.error("Authentication required", code=401)
        return tx

    # Map TX action to semantic access action (e.g., 'get' -> 'read')
    access_action = _ACCESS_ACTION.get(action, action)

    # Fall through to model-level __access__ check (resolver defaults to AUTHENTICATED)

    if action == 'list':
        # Compute SQL filter (handles OWNER as WHERE clause via sql_filter_for)
        ctx = AccessContext(user=user, action=access_action, model_class=model_cls)
        try:
            tx.meta['sql_filter'] = _resolver.sql_filter_for(ctx)
        except AccessDenied as e:
            return _deny(tx, user, str(e))
        return tx

    if action == 'create':
        # Full check — no resource instance needed for create
        rule = _resolver.resolve_rule(model_cls, 'create')
        ctx = AccessContext(user=user, action='create', model_class=model_cls)
        if not rule.evaluate(ctx):
            return _deny(tx, user)
        return tx

    # read/update/delete: identity gate only
    # Full OWNER/Where check happens at Tier 2 (handler_crud has the instance)
    rule = _resolver.resolve_rule(model_cls, access_action)
    ctx = AccessContext(user=user, action=access_action, model_class=model_cls)
    # Rules like ANYONE pass through even without a user. OWNER/ROLE/AUTHENTICATED
    # fail if no user_id — the rule's evaluate() handles this correctly.
    if not rule.evaluate(ctx):
        if not user.get('user_id'):
            return tx.error("Authentication required", code=401)
        # Authenticated user — pass through to Tier 2 for resource-level check
    return tx


def _deny(tx: TX, user: dict, message: str = None) -> TX:
    """Return 401 for unauthenticated, 403 for authenticated-but-forbidden."""
    if not user.get('user_id'):
        return tx.error("Authentication required", code=401)
    return tx.error(message or "Access denied", code=403)
