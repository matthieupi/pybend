# app/models/product_model.py
from __future__ import annotations

from pydantic import Field, field_validator

from models.viewable_mixin import ViewableMixin
from .comment_model import Comment
from .proto_model import ProtoModel
from .ref import ListRef
from typing import ClassVar, Optional
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
            'main': ['name', 'description'],
            'pricing': ['price'],
            'relations': ['comments'],
        },
    }
    name: str = Field(min_length=1, max_length=200, json_schema_extra={'ui': {'placeholder': 'Product name...'}})
    price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}})
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    comments: Optional[ListRef[Comment]] = Field(default=[], alias='comments', description="List of comments associated with the product")
    id: Optional[int] = Field(default=None, alias='id')

    """
    @field_validator('comments', mode='before')
    @classmethod
    def default_comments(cls, v):
        return v if v is not None else []
    """


    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment) -> str:
        """
        Add a comment to the product.
        """
        print(f"Adding comment to product {self.id}: {comment}")
        print(type(comment))
        comment.user_owner = 1  # TODO: use actual authenticated user
        comment.__owner__ = self
        comment.save()
        return comment.model_dump_json()


Product.update_forward_refs()