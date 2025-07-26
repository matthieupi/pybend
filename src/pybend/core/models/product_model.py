# app/models/product_model.py
from __future__ import annotations

from pydantic import Field, field_validator

from models.viewable_mixin import ViewableMixin
from .comment_model import Comment
from .proto_model import ProtoModel
from typing import ClassVar, List, Optional
from utils.decorators import expose_route


class Product(ProtoModel):
    """
    Product model representing a product in the system.
    """
    __tablename__: ClassVar[str] = 'products'
    __storable__: ClassVar[bool] = True
    name: str
    price: float
    description: str = ''
    comments: Optional[List[Comment]] = Field(default=[], alias='comments', description="List of comments associated with the product")
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
        comment.__owner__ = self
        comment.save()
        return comment.model_dump_json()


Product.update_forward_refs()