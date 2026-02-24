from __future__ import annotations

from pydantic import Field

from .proto_model import ProtoModel
from typing import ClassVar
from .user_model import User


class Like(ProtoModel):
    __tablename__: ClassVar[str] = 'likes'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user'}
    user: User = Field(description="User who liked")
    created_at: str = Field(default='')
