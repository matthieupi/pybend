# app/models/product_model.py

from .proto_model import ProtoModel
from typing import ClassVar
from ..utils.decorators import expose_route
from flask import jsonify

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
    def list():
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
            {'id': 1, 'name': 'Product A', 'price': 10.0, 'description': 'Description A'},
            {'id': 2, 'name': 'Product B', 'price': 20.0, 'description': 'Description B'},
        ]
        return jsonify(products), 200
