# app/models/product_model.py
from __future__ import annotations

from pydantic import Field, field_validator

from models.viewable_mixin import ViewableMixin
from .comment_model import Comment
from .proto_model import ProtoModel
from .user_model import User
from .ref import ListRef
from typing import ClassVar
from utils.decorators import expose_route


class Product(ProtoModel):
    """
    Product model representing a product in the system.
    """
    __tablename__: ClassVar[str] = 'products'
    __storable__: ClassVar[bool] = True
    __ui__: ClassVar[dict] = {
        'field_order': ['name', 'price', 'description', 'comments'],
        'groups': {
            'main': ['name', 'description', 'price'],
            'Social': ['comments'],
        },
        'methods': {
            'comment': {
                'layout': 'inline',
                'attach_to': 'comments',
                'button_label': 'Post',
                'placeholder': 'Add your comment...',
                'widget': 'textarea',
            }
        },
        'populate': {'depth': 2},
        'renderer': {
            'item': 'ntt-item',      # Custom component tag for single entity views
            'list': 'ntt-list',      # Custom component tag for collection views
        },
    }
    image: str = Field(default='https://placehold.co/400x300/e2e8f0/64748b?text=No+Image')
    name: str = Field(min_length=1, max_length=200, json_schema_extra={'ui': {'placeholder': 'Product name...'}})
    price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}, 'access': {'view': 'anyone', 'edit': 'admin'}})
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    comments: ListRef[Comment] = Field(default=[], alias='comments', description="List of comments associated with the product")

    """
    @field_validator('comments', mode='before')
    @classmethod
    def default_comments(cls, v):
        return v if v is not None else []
    """


    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment, user: User = None) -> str:
        """
        Add a comment to the product.
        """
        comment.user_owner = user.id if user else 1
        comment.__owner__ = self
        comment.save()
        return comment.model_dump_json()


Product.update_forward_refs()