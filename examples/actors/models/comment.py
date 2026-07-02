# example/models/comment.py
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.ref import Ref
from models.like import Like
from typing import ClassVar, Optional
from models.user import User
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.registrar import join_models
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.utils.erroring import MethodError
from n3tx_core.widgets import TextareaField


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
    likes: list[Like] = Field(default=[], description="Likes on this comment")

    @expose_route('/like', methods=['POST'], access=AUTHENTICATED)
    def like(self, user: User = None) -> dict:
        """Toggle like — create if not liked, delete if already liked."""
        if not user:
            raise MethodError("authentication required", 401)
        join_cls = join_models.get(('Comment', 'Like'))
        if not join_cls:
            raise MethodError("CommentLike join model not registered", 500)
        existing = join_cls.list(sql_filter=(f"comment_id = ? AND user = ?", [self.id, user.id]))
        items = existing if isinstance(existing, list) else existing.get('data', [])
        if items:
            deleted_id = items[0].id
            join_cls.delete(deleted_id)
            return {'action': 'unliked', 'id': deleted_id, '_field': 'likes'}
        new_like = Like(user=user.id, created_at=datetime.now().isoformat())
        new_like.__owner__ = self
        saved = new_like.save()
        return {
            'action': 'liked', '_field': 'likes',
            'id': saved.id, 'user': user.id,
            'created_at': saved.created_at,
        }

    @expose_route('/reply', methods=['POST'], access=AUTHENTICATED | OWNER )
    def reply(self, text: str, user: User = None) -> Comment:
        """Add a reply to this comment."""
        comment = Comment(name=text, user_owner=user.id if user else None, parent_id=self.id)
        # Find the product parent so the reply goes into the same ProductComment join table
        product_id = getattr(self, 'product_id', None)
        if product_id:
            from models.product import Product
            comment.__owner__ = Product.get(product_id)
        created = comment.save()
        return created if created else comment

Comment.model_rebuild()
