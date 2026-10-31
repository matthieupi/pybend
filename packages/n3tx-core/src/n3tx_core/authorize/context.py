"""Transport-supplied inputs for independent authorization rules."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Type


@dataclass(frozen=True)
class AccessContext:
    """Authorization inputs with an optional detached direct-update patch.

    Patch keys are read-only; nested values are deep-copied, not recursively
    frozen. Policy changes to nested values cannot alter the update payload.
    Entrypoints without a patch leave it None; rules must handle that case."""

    user: Dict[str, Any]
    action: str
    model_class: Type[Any]
    resource: Optional[Any] = None
    parent_id: Optional[int] = None
    patch: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Detach supplied patch values and prevent top-level mutation."""
        # 0. Snapshot only the optional patch, preserving other context inputs.
        if self.patch is not None:
            snapshot = MappingProxyType(deepcopy(dict(self.patch)))
            object.__setattr__(self, 'patch', snapshot)

    @property
    def user_id(self) -> Optional[int]:
        """Return the authenticated identity's local user ID, if supplied."""
        return self.user.get("user_id")

    @property
    def user_role(self) -> Optional[str]:
        """Return the role claim supplied by the authentication layer."""
        return self.user.get("role")

    @property
    def user_email(self) -> Optional[str]:
        """Return the email claim supplied by the authentication layer."""
        return self.user.get("email")

    @property
    def is_authenticated(self) -> bool:
        """Report whether the context contains a nonempty user ID."""
        return bool(self.user and self.user.get("user_id"))


# Changelog
# - 2026-10-26: Add a detached, read-only outer mapping for update policy input.
