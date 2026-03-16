"""Re-export authorize package for convenient access.

Legacy location — use ``from n3tx_core.authorize import ...`` directly.
"""
from n3tx_core.authorize import *  # noqa: F401,F403
from n3tx_core.authorize import (  # noqa: F401 — explicit re-exports for type checkers
    configure,
    AccessRule, ANYONE, AUTHENTICATED, OWNER, ROLE, Where,
    AndRule, OrRule, NotRule,
    AccessContext, AuthorizationResolver, DefaultResolver,
    AccessDenied,
    hash_password, verify_password, create_token, decode_token,
)
from n3tx_core.authorize.schema import access_schema  # noqa: F401
