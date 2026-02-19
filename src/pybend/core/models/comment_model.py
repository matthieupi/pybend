# app/models/comment_model.py
from __future__ import annotations

from pydantic import Field

from .proto_model import ProtoModel
from .ref import ListRef
from .like_model import Like
from typing import ClassVar, Optional
from .user_model import User


class Comment(ProtoModel):
    __tablename__: ClassVar[str] = 'comments'
    __storable__: ClassVar[bool] = True
    name: str
    description: str = ''
    user_owner: User = Field(default=None, alias='user_owner', description="User who owns the comment")
    replies: Optional[ListRef['Comment']] = Field(default=[], description="Replies to this comment")
    likes: Optional[ListRef[Like]] = Field(default=[], description="Likes on this comment")
    id: Optional[int] = Field(default=None)

Comment.model_rebuild()

