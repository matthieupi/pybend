# example/models/comment.py
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from pybend.core.models.actor_model import ActorModel
from pybend.core.models.ref import ListRef, Ref
from models.like import Like
from typing import ClassVar, Optional
from models.user import User
from pybend.core.utils.decorators import expose_route
from pybend.core.utils.registrar import join_models
from pybend.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from pybend.core.utils.erroring import MethodError
from pybend.core.widgets import TextareaField


class Comment(ActorModel):
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
    description: TextareaField = Field(default='')
    user_owner: User = Field(default=None, alias='user_owner', description="User who owns the comment",
                             json_schema_extra={'access': {'view': 'authenticated', 'edit': 'owner'}})
    parent_id: Optional[Ref['self']] = Field(default=None, description="Parent comment for nesting")
    likes: ListRef[Like] = Field(default=[], description="Likes on this comment")

    @expose_route('/like', methods=['POST'], access=AUTHENTICATED)
    def like(self, user: User = None) -> str:
        """Toggle like — create if not liked, delete if already liked."""
        if not user:
            raise MethodError("authentication required", 401)
        join_cls = join_models.get(('Comment', 'Like'))
        if not join_cls:
            raise MethodError("CommentLike join model not registered", 500)
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
            from models.product import Product
            comment.__owner__ = Product.get(product_id)
        created = comment.save()
        return created.model_dump_json() if created else comment.model_dump_json()

Comment.model_rebuild()
