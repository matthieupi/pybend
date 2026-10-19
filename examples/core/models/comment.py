# example/models/comment.py
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import Ref, local_ref_id
from models.like import Like
from typing import ClassVar, Optional
from models.user import User
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.utils.erroring import MethodError
from n3tx_core.widgets import TextareaField


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
        likes = list(self.likes or [])
        existing = next(
            (like for like in likes if local_ref_id(getattr(like, 'user', None), target_cls=User) == user.id),
            None,
        )
        if existing:
            deleted_id = existing.id
            Like.delete(deleted_id)
            likes = [like for like in likes if getattr(like, 'id', None) != deleted_id]
            type(self).update(self.id, {'likes': likes})
            return {'action': 'unliked', 'id': deleted_id, '_field': 'likes'}
        new_like = Like(user=user.id, created_at=datetime.now().isoformat())
        saved = Like.create(new_like)
        likes.append(saved)
        type(self).update(self.id, {'likes': likes})
        return {
            'action': 'liked', '_field': 'likes',
            'id': saved.id, 'user': user.id,
            'created_at': saved.created_at,
        }

    @expose_route('/reply', methods=['POST'], access=AUTHENTICATED)
    def reply(self, text: str, user: User = None) -> Comment:
        """Add a reply to this comment."""
        comment = Comment(name=text, user_owner=user.id if user else None, parent_id=self.id)
        created = Comment.create(comment)
        try:
            from models.product import Product
            products = Product.list()
            products = products.get('data', products) if isinstance(products, dict) else products
            for product in products:
                comments = list(product.comments or [])
                if any(getattr(item, 'id', None) == self.id for item in comments):
                    comments.append(created)
                    Product.update(product.id, {'comments': comments})
                    break
        except Exception:
            pass
        return created

Comment.model_rebuild()
