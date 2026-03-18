# example/models/product.py
from __future__ import annotations

import asyncio
from datetime import datetime

from pydantic import Field, field_validator

from n3tx_actors.tx import TX
from models.comment import Comment
from models.like import Like
from n3tx_actors.models.actor_model import ActorModel
from models.user import User
from n3tx_core.models.ref import ListRef
from typing import ClassVar, Any, AsyncGenerator
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.registrar import join_models
from n3tx_core.authorize import ANYONE, AUTHENTICATED
from n3tx_core.utils.erroring import MethodError
from n3tx_core.widgets import CurrencyField, TextareaField


class Product(ActorModel):
    """
    Product model representing a product in the system.
    """
    __tablename__: ClassVar[str] = 'products'
    __storable__: ClassVar[bool] = True
    __agent__: ClassVar[dict] = True
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
            'ask': {
                'layout': 'inline',
                'button_label': 'Ask AI',
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
    comments: ListRef[Comment] = Field(default=[], alias='comments', description="List of comments associated with the product")
    favorites: ListRef[Like] = Field(default=[], description="Users who favorited this product")


    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment, user: User = None) -> Comment:
        """
        Add a comment to the product.
        """
        comment.user_owner = user.id if user else 1
        comment.__owner__ = self
        comment.save()
        return comment

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
        join_cls = join_models.get(('Product', 'Like'))
        if not join_cls:
            raise MethodError("ProductLike join model not registered", 500)
        existing = join_cls.list(sql_filter=("product_id = ? AND user = ?", [self.id, user.id]))
        items = existing if isinstance(existing, list) else existing.get('data', [])
        if items:
            join_cls.delete(items[0].id)
            return {'action': 'unfavorited'}
        new_like = Like(user=user.id, created_at=datetime.now().isoformat())
        new_like.__owner__ = self
        new_like.save()
        return {'action': 'favorited'}

    # TODO We just added the return type, we have to make sure this plays well within the framework
    #  (fastapi, automatic docs, type checking in N3TX etc) as this is the first we use a AsyncGen return type.
    #  we should also add tests for this case (return type)
    @expose_route('/ask', methods=['POST'], stream=True, access=AUTHENTICATED)
    async def ask(self, task: str, user: User = None) -> AsyncGenerator[TX, Any]:
        """Ask the agent about this product."""
        async for tx in self.agentic_stream(task=task, user=user):
            yield tx
        # TODO When finished we should save the results somewhere. Should be in N3tx models/ not example app


Product.update_forward_refs()
