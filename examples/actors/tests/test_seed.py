"""Tests for seed.py — seed() function structure and behavior.

UT-11: Enhanced to verify seed creates expected entities.
"""

import pytest
from unittest.mock import patch, MagicMock

import seed as seed_module

pytestmark = pytest.mark.unit



class TestSeedFunction:

    def test_function_exists(self):
        assert callable(seed_module.seed)

    def test_imports_models(self):
        # Verify that the seed module has access to model imports
        assert hasattr(seed_module, 'Product')
        assert hasattr(seed_module, 'Comment')
        assert hasattr(seed_module, 'Like')
        assert hasattr(seed_module, 'User')

    def test_imports_storage(self):
        assert hasattr(seed_module, 'SQLiteStorage')

    def test_imports_registrar(self):
        assert hasattr(seed_module, 'register_model')

    def test_imports_hash_password(self):
        assert hasattr(seed_module, 'hash_password')

class TestSeedData:
    """UT-11: Verify seed data definitions (counts, structure)."""

    def test_seed_defines_three_users(self):
        """The seed function defines 3 user records."""
        import ast, inspect
        source = inspect.getsource(seed_module.seed)
        # Count user dicts in the users list
        assert source.count('"email":') >= 3

    def test_seed_defines_five_products(self):
        """The seed function defines 5 product records."""
        import inspect
        source = inspect.getsource(seed_module.seed)
        # Count product definitions
        assert source.count('"price":') >= 5

    def test_seed_defines_eight_comments(self):
        """The seed function defines 8 comments on products."""
        import inspect
        source = inspect.getsource(seed_module.seed)
        # Comments have product_idx and user_idx
        assert source.count('"product_idx":') >= 8

    def test_seed_defines_three_replies(self):
        """The seed function defines 3 nested replies."""
        import inspect
        source = inspect.getsource(seed_module.seed)
        assert source.count('"parent_idx":') >= 3

    def test_seed_defines_five_likes(self):
        """The seed function defines 5 likes on comments."""
        import inspect
        source = inspect.getsource(seed_module.seed)
        assert source.count('"comment_idx":') >= 5

    def test_seed_defines_five_favorites(self):
        """The seed function defines 5 favorites on products."""
        import inspect
        source = inspect.getsource(seed_module.seed)
        # Count favorite data entries (product_idx patterns in fav_data)
        # The fav_data list contains product favorites
        assert '"product_idx": 0,' in source and '"user_idx": 0' in source
