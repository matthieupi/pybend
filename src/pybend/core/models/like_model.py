from __future__ import annotations

from pydantic import Field

from .proto_model import ProtoModel
from typing import ClassVar, Optional
from .user_model import User


class Like(ProtoModel):
    __tablename__: ClassVar[str] = 'likes'
    __storable__: ClassVar[bool] = True
    user: User = Field(description="User who liked")
    created_at: str = Field(default='')
    id: Optional[int] = Field(default=None)
