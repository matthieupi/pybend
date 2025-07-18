# app/models/product_model.py
from __future__ import annotations

from pydantic import Field

from models.viewable_mixin import ViewableMixin
from .proto_model import ProtoModel
from typing import ClassVar, List, Optional
from utils.decorators import expose_route


class Comment(ProtoModel):
    """
    Product model representing a product in the system.
    """
    __tablename__: ClassVar[str] = 'comments'
    __storable__: ClassVar[bool] = True
    name: str
    description: str = ''
    id: Optional[int] = Field(default=None, alias='comment_id')

    @staticmethod
    @expose_route('/list', methods=['GET'])
    def list() -> str:
        """
        List all products.
        ---
        tags:
          - products
        responses:
          200:
            description: A list of products bis
        """
        # Example static data
        print("Hello from Product.list()")
        comments = [
            Comment(id=1, name='Product A', description='Description A'),
            Comment(id=2, name='Product B', description='Description B'),
        ]
        return comments

