from __future__ import annotations

from pydantic import Field

from n3tx.core.models.actor_model import ActorModel
from n3tx.core.models.ref import Ref
from typing import ClassVar
from models.user import User


class Like(ActorModel):
    __tablename__: ClassVar[str] = 'likes'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user'}
    user: Ref[User] = Field(description="User who liked")
    created_at: str = Field(default='')
