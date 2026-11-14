"""Composable authorization rules with model-validated SQL predicates.

API: AccessRule supplies evaluation, SQL pushdown and schema serialization;
leaf rules and logical compositions implement application access policies.
Boundary: entrypoints supply AccessContext and enforce the resulting policy.
Where shares the model-field compiler with native list filtering."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from n3tx_core.utils.where import OPERATORS, compile_where, parse_where

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
        """Return SQL and parameters, or None if pushdown is unsupported."""
        return None

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize this rule to a JSON-compatible dict for schema exposure."""
        ...

    def __or__(self, other: AccessRule) -> OrRule:
        """Combine rules with logical OR."""
        return OrRule(self, other)

    def __and__(self, other: AccessRule) -> AndRule:
        """Combine rules with logical AND."""
        return AndRule(self, other)

    def __invert__(self) -> NotRule:
        """Negate this rule."""
        return NotRule(self)

    def __repr__(self) -> str:
        """Describe the serialized policy."""
        return f"{self.__class__.__name__}({self.to_dict()})"


# ── Composite rules ──────────────────────────────────────

class OrRule(AccessRule):
    """Logical OR: passes if ANY child rule passes."""

    def __init__(self, *rules: AccessRule):
        """Store child rules in evaluation order."""
        self.rules = rules

    def evaluate(self, ctx: AccessContext) -> bool:
        """Allow when any child permits the context."""
        return any(r.evaluate(ctx) for r in self.rules)

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """OR child predicates when every child supports SQL."""
        # 0. Collect clauses and ordered parameters, preserving unsupported SQL.
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
        """Serialize the OR operation and its children."""
        return {"op": "or", "rules": [r.to_dict() for r in self.rules]}


class AndRule(AccessRule):
    """Logical AND: passes only if ALL child rules pass."""

    def __init__(self, *rules: AccessRule):
        """Store child rules in evaluation order."""
        self.rules = rules

    def evaluate(self, ctx: AccessContext) -> bool:
        """Allow only when all children permit the context."""
        return all(r.evaluate(ctx) for r in self.rules)

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """AND child predicates when every child supports SQL."""
        # 0. Collect clauses and ordered parameters, preserving unsupported SQL.
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
        """Serialize the AND operation and its children."""
        return {"op": "and", "rules": [r.to_dict() for r in self.rules]}


class NotRule(AccessRule):
    """Logical NOT: inverts the child rule."""

    def __init__(self, rule: AccessRule):
        """Store the child rule."""
        self.rule = rule

    def evaluate(self, ctx: AccessContext) -> bool:
        """Invert the child decision."""
        return not self.rule.evaluate(ctx)

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Negate the child predicate when available."""
        f = self.rule.sql_filter(ctx)
        if f is None:
            return None
        clause, params = f
        return (f"NOT ({clause})", params)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the negation and child policy."""
        return {"op": "not", "rule": self.rule.to_dict()}


# ── Leaf rules ────────────────────────────────────────────

class _Anyone(AccessRule):
    """Always grants access. No authentication required."""

    def evaluate(self, ctx: AccessContext) -> bool:
        """Allow every context."""
        return True

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Return an unrestricted predicate."""
        return ("1=1", [])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize public access."""
        return {"rule": "anyone"}


ANYONE = _Anyone()


class _Never(AccessRule):
    """Always denies access. Bottom element — complement of ANYONE.

    Algebraic properties:
        A & NEVER == NEVER   (annihilation)
        A | NEVER == A       (identity)
        ~ANYONE == NEVER     (complement)"""

    def evaluate(self, ctx: AccessContext) -> bool:
        """Deny every context."""
        return False

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Exclude every row."""
        return ("1=0", [])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the deny-all marker."""
        return {"rule": "never"}


NEVER = _Never()


class _Authenticated(AccessRule):
    """Grants access to any authenticated user."""

    def evaluate(self, ctx: AccessContext) -> bool:
        """Check authenticated identity."""
        return ctx.is_authenticated

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Preserve the existing unrestricted SQL predicate."""
        return ("1=1", [])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the identity requirement."""
        return {"rule": "authenticated"}


AUTHENTICATED = _Authenticated()


class _Owner(AccessRule):
    """Grants access only when user_id matches the resource's owner field.

    The owner field name defaults to 'user_owner' but can be overridden
    via __owner_field__ on the model class."""

    def __init__(self, owner_field: Optional[str] = None):
        """Store an optional explicit ownership field."""
        self._field = owner_field

    def _resolve_field(self, ctx: AccessContext) -> str:
        """Resolve the explicit or model-defined ownership field."""
        if self._field:
            return self._field
        return getattr(ctx.model_class, '__owner_field__', 'user_owner')

    def evaluate(self, ctx: AccessContext) -> bool:
        """Compare the authenticated caller with the resource owner."""
        # 0. Gate identity before comparing the resource's owner value.
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
        """Restrict rows to the authenticated owner."""
        if not ctx.is_authenticated:
            return ("1=0", [])
        field = self._resolve_field(ctx)
        return (f"{field} = ?", [ctx.user_id])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ownership with an optional field override."""
        d = {"rule": "owner"}
        if self._field:
            d["field"] = self._field
        return d


OWNER = _Owner()


class _Role(AccessRule):
    """Grants access if the user's role is in the allowed set."""

    def __init__(self, *roles: str):
        """Store the allowed roles."""
        self.roles = set(roles)

    def evaluate(self, ctx: AccessContext) -> bool:
        """Check authenticated role membership."""
        return ctx.is_authenticated and ctx.user_role in self.roles

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Allow all or no rows according to role membership."""
        if self.evaluate(ctx):
            return ("1=1", [])
        return ("1=0", [])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the allowed role names."""
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
        field__contains -> literal case-sensitive substring

    Logical groups use $or for alternatives and $and for conjunctions."""
    _OPS = OPERATORS

    def __init__(self, **conditions):
        """Store conditions for resource and SQL evaluation."""
        self.conditions = conditions

    def _parse(self) -> list:
        """Returns list of (field, operator_symbol, value)."""
        return parse_where(self.conditions)

    def evaluate(self, ctx: AccessContext) -> bool:
        """Require each condition to match a loaded resource."""
        # 0. Defer evaluation when the context has no resource.
        if ctx.resource is None:
            return True
        for field, op, value in self._parse():
            if op in ('OR', 'AND'):
                combine = any if op == 'OR' else all
                if not combine(
                    Where(**branch).evaluate(ctx) for branch in value
                ):
                    return False
                continue
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
            elif op == 'CONTAINS' and not (
                isinstance(actual, str) and isinstance(value, str)
                and value in actual
            ):
                return False
        return True

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Compile conditions against the context's declared model fields."""
        return compile_where(ctx.model_class, self.conditions, public=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the model-field conditions."""
        return {"rule": "where", "conditions": self.conditions}


# ── Federation rules ─────────────────────────────────────

class Federated(AccessRule):
    """Grants access only to federated (non-local) actors.

    Checks for ``meta.federated`` flag set by the ActivityPub adapter
    when translating inbound activities to TX messages."""

    def evaluate(self, ctx: AccessContext) -> bool:
        """Check the federation marker."""
        return bool(ctx.user.get('federated', False))

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Allow all or no rows according to federation state."""
        if self.evaluate(ctx):
            return ("1=1", [])
        return ("1=0", [])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the federation requirement."""
        return {"rule": "federated"}


FEDERATED = Federated()


class Local(AccessRule):
    """Grants access only to local (non-federated) users.

    Complement of Federated — passes when the request did NOT
    originate from an ActivityPub federation adapter."""

    def evaluate(self, ctx: AccessContext) -> bool:
        """Check that the caller is not federated."""
        return not ctx.user.get('federated', False)

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]:
        """Allow all or no rows according to local caller state."""
        if self.evaluate(ctx):
            return ("1=1", [])
        return ("1=0", [])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the local-caller requirement."""
        return {"rule": "local"}


LOCAL = Local()


class Follower(AccessRule):
    """Grants access only to users who follow the resource owner.

    Requires ``ctx.user.get('following')`` to contain the owner's URI
    or ID, as populated by the federation adapter or auth middleware."""

    def __init__(self, owner_field: Optional[str] = None):
        """Store an optional explicit ownership field."""
        self._field = owner_field

    def _resolve_field(self, ctx: AccessContext) -> str:
        """Resolve the explicit or model-defined ownership field."""
        if self._field:
            return self._field
        return getattr(ctx.model_class, '__owner_field__', 'user_owner')

    def evaluate(self, ctx: AccessContext) -> bool:
        """Compare the resource owner with the caller's followed identities."""
        # 0. Require caller and resource before checking the social graph.
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
        """Filter followed owners, preserving the absent-graph fallback."""
        # 0. Distinguish unauthenticated, unknown and empty following state.
        if not ctx.is_authenticated:
            return ("1=0", [])
        following = ctx.user.get('following')
        if following is None:
            # Absent following data preserves permissive SQL behavior.
            return ("1=1", [])
        if not following:
            # Empty following list — no one is followed
            return ("1=0", [])
        field = self._resolve_field(ctx)
        placeholders = ','.join(['?'] * len(following))
        return (f"{field} IN ({placeholders})", list(following))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize follower policy with an optional field override."""
        d: Dict[str, Any] = {"rule": "follower"}
        if self._field:
            d["field"] = self._field
        return d


FOLLOWER = Follower()


# Changelog
# - 2026-11-13: Evaluate AND groups alongside existing OR groups.
# - 2026-11-02: Share validated SQL conditions and add literal contains rules.
# - 2026-11-10: Restore shared Where compilation and evaluation from 123d825.
