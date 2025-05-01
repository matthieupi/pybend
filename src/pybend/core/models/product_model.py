# app/models/product_model.py
from __future__ import annotations
from .proto_model import ProtoModel
from typing import ClassVar, List
from utils.decorators import expose_route

class Product(ProtoModel):
    """
    Product model representing a product in the system.
    """
    __tablename__: ClassVar[str] = 'products'
    name: str
    price: float
    description: str = ''
    id: int = None  # Primary key

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

