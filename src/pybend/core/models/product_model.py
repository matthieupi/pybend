# app/models/product_model.py
from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from models.viewable_mixin import ViewableMixin
from .comment_model import Comment
from .like_model import Like
from .proto_model import ProtoModel
from .user_model import User
from .ref import ListRef
from typing import ClassVar
from utils.decorators import expose_route
from utils.registrar import join_models
from authorize import AUTHENTICATED


class Product(ProtoModel):
    """
    Product model representing a product in the system.
    """
    __tablename__: ClassVar[str] = 'products'
    __storable__: ClassVar[bool] = True
    __ui__: ClassVar[dict] = {
        'field_order': ['name', 'price', 'description', 'comments', 'favorites'],
        'groups': {
            'main': ['name', 'description', 'price'],
            'Social': ['comments', 'favorites'],
        },
        'methods': {
            'comment': {
                'layout': 'inline',
                'attach_to': 'comments',
                'button_label': 'Post',
                'placeholder': 'Add your comment...',
                'widget': 'textarea',
            },
            'favorite': {
                'layout': 'button',
                'icon': 'star',
                'count_field': 'favorites',
                'attach_to': 'favorites',
            },
        },
        'populate': {'depth': 2},
        'renderer': {
            'item': 'ntt-item',
            'list': 'ntt-list',
        },
    }
    image: str = Field(default='https://placehold.co/400x300/e2e8f0/64748b?text=No+Image')
    name: str = Field(min_length=1, max_length=200, json_schema_extra={'ui': {'placeholder': 'Product name...'}})
    price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}, 'access': {'view': 'anyone', 'edit': 'admin'}})
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    comments: ListRef[Comment] = Field(default=[], alias='comments', description="List of comments associated with the product")
    favorites: ListRef[Like] = Field(default=[], description="Users who favorited this product")


    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment, user: User = None) -> str:
        """
        Add a comment to the product.
        """
        comment.user_owner = user.id if user else 1
        comment.__owner__ = self
        comment.save()
        return comment.model_dump_json()

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> str:
        """Toggle favorite — add if not favorited, remove if already favorited."""
        if not user:
            return '{"error": "authentication required"}'
        join_cls = join_models.get(('Product', 'Like'))
        if not join_cls:
            return '{"error": "ProductLike join model not registered"}'
        existing = join_cls.list(sql_filter=("product_id = ? AND user = ?", [self.id, user.id]))
        items = existing if isinstance(existing, list) else existing.get('data', [])
        if items:
            join_cls.delete(items[0].id)
            return '{"action": "unfavorited"}'
        new_like = Like(user=user.id, created_at=datetime.now().isoformat())
        new_like.__owner__ = self
        new_like.save()
        return '{"action": "favorited"}'


Product.update_forward_refs()
