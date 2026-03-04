from __future__ import annotations

from pydantic import Field

from pybend.core.models.actor_model import ActorModel
from typing import ClassVar
from models.user import User


class Like(ActorModel):
    __tablename__: ClassVar[str] = 'likes'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user'}
    user: User = Field(description="User who liked")
    created_at: str = Field(default='')
