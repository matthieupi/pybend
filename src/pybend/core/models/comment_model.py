# app/models/comment_model.py
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .proto_model import ProtoModel
from .ref import ListRef, Ref
from .like_model import Like
from typing import ClassVar, Optional
from .user_model import User
from utils.decorators import expose_route
from utils.registrar import join_models
from authorize import ANYONE, AUTHENTICATED, OWNER, ROLE


class Comment(ProtoModel):
    __tablename__: ClassVar[str] = 'comments'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': ['user_owner', 'name', 'description', 'likes'],
        'methods': {
            'like':  {'layout': 'button', 'icon': 'heart', 'count_field': 'likes', 'attach_to': 'likes'},
            'reply': {'layout': 'inline', 'attach_to': 'description', 'button_label': 'Reply',
                      'placeholder': 'Write a reply...', 'widget': 'textarea'},
        },
    }
    name: str = Field(min_length=1, max_length=500)
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    user_owner: User = Field(default=None, alias='user_owner', description="User who owns the comment",
                             json_schema_extra={'access': {'view': 'authenticated', 'edit': 'owner'}})
    parent_id: Optional[Ref['self']] = Field(default=None, description="Parent comment for nesting")
    likes: ListRef[Like] = Field(default=[], description="Likes on this comment")

    @expose_route('/like', methods=['POST'], access=AUTHENTICATED)
    def like(self, user: User = None) -> str:
        """Toggle like — create if not liked, delete if already liked."""
        if not user:
            return '{"error": "authentication required"}'
        join_cls = join_models.get(('Comment', 'Like'))
        if not join_cls:
            return '{"error": "CommentLike join model not registered"}'
        existing = join_cls.list(sql_filter=(f"comment_id = ? AND user = ?", [self.id, user.id]))
        items = existing if isinstance(existing, list) else existing.get('data', [])
        if items:
            join_cls.delete(items[0].id)
            return '{"action": "unliked"}'
        new_like = Like(user=user.id, created_at=datetime.now().isoformat())
        new_like.__owner__ = self
        new_like.save()
        return '{"action": "liked"}'

    @expose_route('/reply', methods=['POST'], access=AUTHENTICATED)
    def reply(self, text: str, user: User = None) -> str:
        """Add a reply to this comment."""
        comment = Comment(name=text, user_owner=user.id if user else None, parent_id=self.id)
        # Find the product parent so the reply goes into the same ProductComment join table
        product_id = getattr(self, 'product_id', None)
        if product_id:
            from models.product_model import Product
            comment.__owner__ = Product.get(product_id)
        created = comment.save()
        return created.model_dump_json() if created else comment.model_dump_json()

Comment.model_rebuild()
