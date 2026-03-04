"""Re-export authorize package for convenient access.

Usage::

    from n3tx.authorize import ANYONE, AUTHENTICATED, ROLE, OWNER
    from n3tx.authorize import configure, create_token, decode_token
"""
from .core.authorize import *  # noqa: F401,F403
from .core.authorize import (  # noqa: F401 — explicit re-exports for type checkers
    configure,
    AccessRule, ANYONE, AUTHENTICATED, OWNER, ROLE, Where,
    AndRule, OrRule, NotRule,
    AccessContext, AuthorizationResolver, DefaultResolver,
    AccessDenied,
    hash_password, verify_password, create_token, decode_token,
)
from .core.authorize.schema import access_schema  # noqa: F401
