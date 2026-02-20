from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Type


@dataclass(frozen=True)
class AccessContext:
    """Immutable snapshot of everything an access rule needs to evaluate."""
    user: Dict[str, Any]
    action: str
    model_class: Type[Any]
    resource: Optional[Any] = None
    parent_id: Optional[int] = None

    @property
    def user_id(self) -> Optional[int]:
        return self.user.get("user_id")

    @property
    def user_role(self) -> Optional[str]:
        return self.user.get("role")

    @property
    def user_email(self) -> Optional[str]:
        return self.user.get("email")

    @property
    def is_authenticated(self) -> bool:
        return bool(self.user and self.user.get("user_id"))
