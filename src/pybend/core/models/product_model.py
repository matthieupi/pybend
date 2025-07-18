# app/models/product_model.py
from __future__ import annotations

from pydantic import Field

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
    comments: List[Comment] = Field(default=[], alias='comments', description="List of comments associated with the product")
    id: Optional[int] = Field(default=None, alias='product_id')

    @staticmethod
    @expose_route('/list', methods=['GET'])
    def list() -> List[Product]:
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
        products = [
            Product(id=1, name='Product A', price=10.0, description='Description A'),
            Product(id=2, name='Product B', price=20.0, description='Description B'),
        ]
        return products


    @expose_route('/comments', methods=['POST'])
    def comment(self, comment: Comment ) -> str:
        """
        Add a comment to the product.
        ---
        tags:
          - products
        requestBody:
          required: true
          content:
            application/json:
              schema:
                type: object
                properties:
                  comment:
                    type: string
        responses:
          200:
            description: Comment added successfully
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    message:
                      type: string
        """
        print(f"Adding comment to product {self.id}: {comment}")
        new_comment = Comment(name=comment, description=f"Comment for product {self.id}")
        self.comments.append(new_comment)
        return comment


Product.update_forward_refs()