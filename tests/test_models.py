# tests/test_models.py

import pytest
from server.models.user_model import User
from server.models.product_model import Product
from pydantic import ValidationError


def test_user_model_validation():
    # Test valid user creation
    user = User(name="Alice", email="alice@example.com", age=30)
    assert user.name == "Alice"
    assert user.email == "alice@example.com"
    assert user.age == 30

    # Test missing required fields
    with pytest.raises(ValidationError):
        User(email="missing_name@example.com")


def test_product_model_validation():
    # Test valid product creation
    product = Product(name="Widget", price=9.99)
    assert product.name == "Widget"
    assert product.price == 9.99

    # Test default values
    assert product.description == ''
    assert product.id is None

    # Test missing required fields
    with pytest.raises(ValidationError):
        Product(price=9.99)
