from __future__ import annotations

import logging
from typing import Any, Dict, Type

from .rules import AccessRule, AUTHENTICATED

logger = logging.getLogger('pybend.authorize')


def access_schema(model_class: Type[Any]) -> Dict[str, Any]:
    """
    Returns a JSON-serializable dict of access rules for schema exposure.

    Example output:
    {
        "create": {"rule": "authenticated"},
        "read": {"rule": "anyone"},
        "update": {"op": "or", "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin"]}]},
    }
    """
    access = getattr(model_class, '__access__', None)
    if access is None:
        return {"*": AUTHENTICATED.to_dict()}

    result = {}
    for action, rule in access.items():
        if isinstance(rule, AccessRule):
            result[action] = rule.to_dict()
        else:
            result[action] = {"rule": str(rule)}
    return result
