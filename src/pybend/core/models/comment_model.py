# app/models/comment_model.py
from __future__ import annotations

from pydantic import Field

from .proto_model import ProtoModel
from .ref import ListRef, Ref
from .like_model import Like
from typing import ClassVar, Optional
from .user_model import User
from utils.decorators import expose_route


class Comment(ProtoModel):
    __tablename__: ClassVar[str] = 'comments'
    __storable__: ClassVar[bool] = True
    __ui__: ClassVar[dict] = {
        'field_order': ['user_owner', 'name', 'description', 'likes'],
    }
    name: str = Field(min_length=1, max_length=500)
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    user_owner: User = Field(default=None, alias='user_owner', description="User who owns the comment",
                             json_schema_extra={'access': {'view': 'authenticated', 'edit': 'owner'}})
    parent_id: Optional[Ref['self']] = Field(default=None, description="Parent comment for nesting")
    likes: ListRef[Like] = Field(default=[], description="Likes on this comment")

    @expose_route('/like', methods=['POST'])
    def like(self, like: Like, user: User = None) -> str:
        """
        Add a like to the comment.
        """
        like.user = user.id if user else None
        like.__owner__ = self
        like.save()
        return like.model_dump_json()

Comment.model_rebuild()
