from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import AccessContext

logger = logging.getLogger('n3tx.authorize')


class AccessRule(ABC):
    """Base class for all authorization rules."""

    @abstractmethod
    def evaluate(self, ctx: AccessContext) -> bool:
        """Return True if access is granted."""
        ...

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Return (WHERE_clause, params) for SQL pushdown, or None if not filterable."""
        return None

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize this rule to a JSON-compatible dict for schema exposure."""
        ...

    def __or__(self, other: AccessRule) -> OrRule:
        return OrRule(self, other)

    def __and__(self, other: AccessRule) -> AndRule:
        return AndRule(self, other)

    def __invert__(self) -> NotRule:
        return NotRule(self)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_dict()})"


# ── Composite rules ──────────────────────────────────────

class OrRule(AccessRule):
    """Logical OR: passes if ANY child rule passes."""
    def __init__(self, *rules: AccessRule):
        self.rules = rules

    def evaluate(self, ctx: AccessContext) -> bool:
        return any(r.evaluate(ctx) for r in self.rules)

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        parts, params = [], []
        for r in self.rules:
            f = r.sql_filter(ctx)
            if f is None:
                return None
            clause, p = f
            parts.append(f"({clause})")
            params.extend(p)
        return (" OR ".join(parts), params)

    def to_dict(self) -> Dict[str, Any]:
        return {"op": "or", "rules": [r.to_dict() for r in self.rules]}


class AndRule(AccessRule):
    """Logical AND: passes only if ALL child rules pass."""
    def __init__(self, *rules: AccessRule):
        self.rules = rules

    def evaluate(self, ctx: AccessContext) -> bool:
        return all(r.evaluate(ctx) for r in self.rules)

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        parts, params = [], []
        for r in self.rules:
            f = r.sql_filter(ctx)
            if f is None:
                return None
            clause, p = f
            parts.append(f"({clause})")
            params.extend(p)
        return (" AND ".join(parts), params)

    def to_dict(self) -> Dict[str, Any]:
        return {"op": "and", "rules": [r.to_dict() for r in self.rules]}


class NotRule(AccessRule):
    """Logical NOT: inverts the child rule."""
    def __init__(self, rule: AccessRule):
        self.rule = rule

    def evaluate(self, ctx: AccessContext) -> bool:
        return not self.rule.evaluate(ctx)

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        f = self.rule.sql_filter(ctx)
        if f is None:
            return None
        clause, params = f
        return (f"NOT ({clause})", params)

    def to_dict(self) -> Dict[str, Any]:
        return {"op": "not", "rule": self.rule.to_dict()}


# ── Leaf rules ────────────────────────────────────────────

class _Anyone(AccessRule):
    """Always grants access. No authentication required."""
    def evaluate(self, ctx: AccessContext) -> bool:
        return True

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        return ("1=1", [])

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": "anyone"}


ANYONE = _Anyone()


class _Never(AccessRule):
    """Always denies access. Bottom element — complement of ANYONE.

    Algebraic properties:
        A & NEVER == NEVER   (annihilation)
        A | NEVER == A       (identity)
        ~ANYONE == NEVER     (complement)
    """
    def evaluate(self, ctx: AccessContext) -> bool:
        return False

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        return ("1=0", [])

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": "never"}


NEVER = _Never()


class _Authenticated(AccessRule):
    """Grants access to any authenticated user."""
    def evaluate(self, ctx: AccessContext) -> bool:
        return ctx.is_authenticated

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        return ("1=1", [])

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": "authenticated"}


AUTHENTICATED = _Authenticated()


class _Owner(AccessRule):
    """Grants access only when user_id matches the resource's owner field.

    The owner field name defaults to 'user_owner' but can be overridden
    via __owner_field__ on the model class.
    """
    def __init__(self, owner_field: Optional[str] = None):
        self._field = owner_field

    def _resolve_field(self, ctx: AccessContext) -> str:
        if self._field:
            return self._field
        return getattr(ctx.model_class, '__owner_field__', 'user_owner')

    def evaluate(self, ctx: AccessContext) -> bool:
        if not ctx.is_authenticated:
            return False
        if ctx.resource is None:
            return True  # For create: ownership is established at creation time
        field = self._resolve_field(ctx)
        owner_val = getattr(ctx.resource, field, None)
        if hasattr(owner_val, 'id'):
            owner_val = owner_val.id
        elif isinstance(owner_val, str) and '/' in owner_val:
            # FK-hydrated href (e.g. "http://.../users/3") → extract trailing ID
            try:
                owner_val = int(owner_val.rstrip('/').rsplit('/', 1)[-1])
            except (ValueError, IndexError):
                pass
        return owner_val == ctx.user_id

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        if not ctx.is_authenticated:
            return ("1=0", [])
        field = self._resolve_field(ctx)
        return (f"{field} = ?", [ctx.user_id])

    def to_dict(self) -> Dict[str, Any]:
        d = {"rule": "owner"}
        if self._field:
            d["field"] = self._field
        return d


OWNER = _Owner()


class _Role(AccessRule):
    """Grants access if the user's role is in the allowed set."""
    def __init__(self, *roles: str):
        self.roles = set(roles)

    def evaluate(self, ctx: AccessContext) -> bool:
        return ctx.is_authenticated and ctx.user_role in self.roles

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        if self.evaluate(ctx):
            return ("1=1", [])
        return ("1=0", [])

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": "role", "roles": sorted(self.roles)}


def ROLE(*roles: str) -> _Role:
    """Factory function for role-based rules."""
    return _Role(*roles)


class Where(AccessRule):
    """Attribute-based condition on the resource.

    Usage: Where(status="published") or Where(price__lt=100)

    Supported operators (via dunder suffixes):
        field          -> field = value
        field__lt      -> field < value
        field__gt      -> field > value
        field__lte     -> field <= value
        field__gte     -> field >= value
        field__ne      -> field != value
        field__in      -> field IN (...)
    """
    _OPS = {
        'lt': '<', 'gt': '>', 'lte': '<=', 'gte': '>=',
        'ne': '!=', 'in': 'IN',
    }

    def __init__(self, **conditions):
        self.conditions = conditions

    def _parse(self) -> list:
        """Returns list of (field, operator_symbol, value)."""
        parsed = []
        for key, value in self.conditions.items():
            parts = key.split('__')
            if len(parts) == 2 and parts[1] in self._OPS:
                parsed.append((parts[0], self._OPS[parts[1]], value))
            else:
                parsed.append((key, '=', value))
        return parsed

    def evaluate(self, ctx: AccessContext) -> bool:
        if ctx.resource is None:
            return True
        for field, op, value in self._parse():
            actual = getattr(ctx.resource, field, None)
            if op == '=' and actual != value:
                return False
            elif op == '<' and not (actual is not None and actual < value):
                return False
            elif op == '>' and not (actual is not None and actual > value):
                return False
            elif op == '<=' and not (actual is not None and actual <= value):
                return False
            elif op == '>=' and not (actual is not None and actual >= value):
                return False
            elif op == '!=' and actual == value:
                return False
            elif op == 'IN' and actual not in value:
                return False
        return True

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        parts, params = [], []
        for field, op, value in self._parse():
            if op == 'IN':
                placeholders = ','.join(['?'] * len(value))
                parts.append(f"{field} IN ({placeholders})")
                params.extend(value)
            else:
                parts.append(f"{field} {op} ?")
                params.append(value)
        return (" AND ".join(parts), params) if parts else ("1=1", [])

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": "where", "conditions": self.conditions}


# ── Federation rules ─────────────────────────────────────

class Federated(AccessRule):
    """Grants access only to federated (non-local) actors.

    Checks for ``meta.federated`` flag set by the ActivityPub adapter
    when translating inbound activities to TX messages.
    """
    def evaluate(self, ctx: AccessContext) -> bool:
        return bool(ctx.user.get('federated', False))

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        if self.evaluate(ctx):
            return ("1=1", [])
        return ("1=0", [])

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": "federated"}


FEDERATED = Federated()


class Local(AccessRule):
    """Grants access only to local (non-federated) users.

    Complement of Federated — passes when the request did NOT
    originate from an ActivityPub federation adapter.
    """
    def evaluate(self, ctx: AccessContext) -> bool:
        return not ctx.user.get('federated', False)

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        if self.evaluate(ctx):
            return ("1=1", [])
        return ("1=0", [])

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": "local"}


LOCAL = Local()


class Follower(AccessRule):
    """Grants access only to users who follow the resource owner.

    Requires ``ctx.user.get('following')`` to contain the owner's URI
    or ID, as populated by the federation adapter or auth middleware.
    """
    def __init__(self, owner_field: Optional[str] = None):
        self._field = owner_field

    def _resolve_field(self, ctx: AccessContext) -> str:
        if self._field:
            return self._field
        return getattr(ctx.model_class, '__owner_field__', 'user_owner')

    def evaluate(self, ctx: AccessContext) -> bool:
        if not ctx.is_authenticated:
            return False
        if ctx.resource is None:
            return False
        following = ctx.user.get('following', [])
        field = self._resolve_field(ctx)
        owner_val = getattr(ctx.resource, field, None)
        if owner_val is None:
            return False
        return owner_val in following or str(owner_val) in following

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        if not ctx.is_authenticated:
            return ("1=0", [])
        following = ctx.user.get('following')
        if following is None:
            # No following data — can't filter, be permissive (evaluate() still guards)
            return ("1=1", [])
        if not following:
            # Empty following list — no one is followed
            return ("1=0", [])
        field = self._resolve_field(ctx)
        placeholders = ','.join(['?'] * len(following))
        return (f"{field} IN ({placeholders})", list(following))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"rule": "follower"}
        if self._field:
            d["field"] = self._field
        return d


FOLLOWER = Follower()
