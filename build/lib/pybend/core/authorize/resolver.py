from __future__ import annotations

import logging
from typing import Any, List, Optional, Protocol, Tuple, Type, runtime_checkable

from .context import AccessContext
from .rules import AccessRule, AUTHENTICATED
from .errors import AccessDenied

logger = logging.getLogger('pybend.authorize')


@runtime_checkable
class AuthorizationResolver(Protocol):
    """Protocol for authorization resolution. Implement this to swap strategies."""

    def resolve_rule(self, model_class: Type[Any], action: str) -> AccessRule:
        """Return the AccessRule that governs the given action on the model."""
        ...

    def authorize(self, ctx: AccessContext) -> None:
        """Raise AccessDenied if the rule denies access."""
        ...

    def sql_filter_for(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Return SQL filter clause + params for list-level pushdown, or None."""
        ...


class DefaultResolver:
    """
    Default resolver: reads __access__ from model class, falls back to AUTHENTICATED.

    Resolution order:
    1. model.__access__[action]  (if __access__ dict exists and has the action key)
    2. model.__access__["*"]     (wildcard default within __access__)
    3. AUTHENTICATED             (global fallback -- backward compatible)
    """

    def resolve_rule(self, model_class: Type[Any], action: str) -> AccessRule:
        access = getattr(model_class, '__access__', None)
        if access is None:
            return AUTHENTICATED
        if action in access:
            return access[action]
        if '*' in access:
            return access['*']
        return AUTHENTICATED

    def authorize(self, ctx: AccessContext) -> None:
        rule = self.resolve_rule(ctx.model_class, ctx.action)
        if not rule.evaluate(ctx):
            raise AccessDenied(
                action=ctx.action,
                model=ctx.model_class.__name__,
                user_id=ctx.user_id,
            )

    def sql_filter_for(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        rule = self.resolve_rule(ctx.model_class, ctx.action)
        return rule.sql_filter(ctx)
