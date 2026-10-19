# example/models/product.py
from __future__ import annotations

import asyncio
from datetime import datetime

from pydantic import Field, field_validator

from models.comment import Comment
from models.like import Like
from n3tx_core.models.proto_model import ProtoModel
from models.user import User
from n3tx_core.models.ref import local_ref_id
from typing import ClassVar
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import ANYONE, AUTHENTICATED
from n3tx_core.utils.erroring import MethodError
from n3tx_core.widgets import CurrencyField, TextareaField


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
            'item': 'ntx-item',
            'list': 'ntx-list',
        },
    }
    image: str = Field(default='https://placehold.co/400x300/e2e8f0/64748b?text=No+Image')
    name: str = Field(min_length=1, max_length=200, json_schema_extra={'ui': {'placeholder': 'Product name...'}})
    price: CurrencyField = Field(gt=0, json_schema_extra={'access': {'view': 'anyone', 'edit': 'admin'}})
    description: TextareaField = Field(default='')
    comments: list[Comment] = Field(default=[], alias='comments', description="List of comments associated with the product")
    favorites: list[Like] = Field(default=[], description="Users who favorited this product")


    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment, user: User = None) -> Comment:
        """
        Add a comment to the product.
        """
        comment.user_owner = user.id if user else 1
        saved = Comment.create(comment)
        comments = list(self.comments or [])
        comments.append(saved)
        type(self).update(self.id, {'comments': comments})
        return saved

    @expose_route('/countdown', methods=['POST'], stream=True, access=ANYONE)
    async def countdown(self, n: int = 5):
        """Stream a countdown from n to 0 with delays."""
        for i in range(n, 0, -1):
            await asyncio.sleep(0.3)
            yield {'count': i, 'message': f'Counting down: {i}'}
        yield {'count': 0, 'message': 'Done!'}

    @expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
    def favorite(self, user: User = None) -> dict:
        """Toggle favorite — add if not favorited, remove if already favorited."""
        if not user:
            raise MethodError("authentication required", 401)
        favorites = list(self.favorites or [])
        existing = next(
            (fav for fav in favorites if local_ref_id(getattr(fav, 'user', None), target_cls=User) == user.id),
            None,
        )
        if existing:
            deleted_id = existing.id
            Like.delete(deleted_id)
            favorites = [fav for fav in favorites if getattr(fav, 'id', None) != deleted_id]
            type(self).update(self.id, {'favorites': favorites})
            return {'action': 'unfavorited', 'id': deleted_id, '_field': 'favorites'}
        new_like = Like(user=user.id, created_at=datetime.now().isoformat())
        saved = Like.create(new_like)
        favorites.append(saved)
        type(self).update(self.id, {'favorites': favorites})
        return {
            'action': 'favorited', '_field': 'favorites',
            'id': saved.id, 'user': user.id,
            'created_at': saved.created_at,
        }


Product.update_forward_refs()
