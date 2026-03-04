"""Tests for models/product_model.py — Product model fields and methods."""

import json
import pytest
from unittest.mock import MagicMock, patch
from typing import ClassVar

from pydantic import Field, ValidationError

from pybend.example_api.models import Product, Comment, Like
from pybend.core.utils.erroring import MethodError

pytestmark = pytest.mark.unit



class TestProductFields:

    def test_name_min_length(self):
        with pytest.raises(ValidationError):
            Product(name='', price=10.0)

    def test_name_max_length(self):
        Product(name='x' * 200, price=10.0)  # Should not raise

    def test_name_over_max_length(self):
        with pytest.raises(ValidationError):
            Product(name='x' * 201, price=10.0)

    def test_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            Product(name='Test', price=0)

    def test_price_negative(self):
        with pytest.raises(ValidationError):
            Product(name='Test', price=-1)

    def test_price_small_positive(self):
        p = Product(name='Test', price=0.01)
        assert p.price == 0.01

    def test_description_default_empty(self):
        p = Product(name='Test', price=10.0)
        assert p.description == ''

    def test_comments_default_empty(self):
        p = Product(name='Test', price=10.0)
        assert p.comments == []

    def test_favorites_default_empty(self):
        p = Product(name='Test', price=10.0)
        assert p.favorites == []

    def test_tablename(self):
        assert Product.__tablename__ == 'products'

    def test_storable(self):
        assert Product.__storable__ is True

    def test_has_ui_config(self):
        assert 'field_order' in Product.__ui__
        assert 'groups' in Product.__ui__

    def test_image_default(self):
        p = Product(name='Test', price=10.0)
        assert 'placehold' in p.image or p.image == ''


class TestProductComment:

    def test_comment_sets_owner(self):
        p = Product(id=1, name='Test', price=10.0)
        c = Comment(name='Hello', description='world')

        # Mock the save to avoid storage calls
        with patch.object(Comment, 'save', return_value=c) as mock_save:
            c_mock = Comment(name='Hello', description='world')
            c_mock.model_dump_json = MagicMock(return_value='{}')
            with patch.object(Comment, 'save', return_value=c_mock):
                result = p.comment(c_mock, user=None)

    def test_comment_user_owner_set_with_user(self):
        p = Product(id=1, name='Test', price=10.0)
        c = Comment(name='Hello')
        mock_user = MagicMock()
        mock_user.id = 42

        with patch.object(Comment, 'save', return_value=c):
            c.model_dump_json = MagicMock(return_value='{}')
            p.comment(c, user=mock_user)
            assert c.user_owner == 42

    def test_comment_user_owner_default_no_user(self):
        p = Product(id=1, name='Test', price=10.0)
        c = Comment(name='Hello')

        with patch.object(Comment, 'save', return_value=c):
            c.model_dump_json = MagicMock(return_value='{}')
            p.comment(c, user=None)
            assert c.user_owner == 1


class TestProductFavorite:

    def test_favorite_no_user(self):
        p = Product(id=1, name='Test', price=10.0)
        with pytest.raises(MethodError):
            p.favorite(user=None)

    def test_favorite_join_model_not_registered(self):
        p = Product(id=1, name='Test', price=10.0)
        mock_user = MagicMock()
        mock_user.id = 1

        with patch('pybend.example_api.models.product.join_models', {}):
            with pytest.raises(MethodError):
                p.favorite(user=mock_user)

    def test_favorite_creates_new(self):
        p = Product(id=1, name='Test', price=10.0)
        mock_user = MagicMock()
        mock_user.id = 1

        mock_join = MagicMock()
        mock_join.list.return_value = []

        with patch('pybend.example_api.models.product.join_models', {('Product', 'Like'): mock_join}):
            with patch.object(Like, 'save', return_value=Like(user=1)):
                result = p.favorite(user=mock_user)
                parsed = json.loads(result)
                assert parsed['action'] == 'favorited'

    def test_unfavorite_existing(self):
        p = Product(id=1, name='Test', price=10.0)
        mock_user = MagicMock()
        mock_user.id = 1

        existing_like = MagicMock()
        existing_like.id = 10
        mock_join = MagicMock()
        mock_join.list.return_value = [existing_like]

        with patch('pybend.example_api.models.product.join_models', {('Product', 'Like'): mock_join}):
            result = p.favorite(user=mock_user)
            parsed = json.loads(result)
            assert parsed['action'] == 'unfavorited'
            mock_join.delete.assert_called_once_with(10)
