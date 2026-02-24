"""Tests for seed.py — seed() function structure and behavior."""

import pytest
from unittest.mock import patch, MagicMock

import seed as seed_module


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
        assert hasattr(seed_module, 'join_models')

    def test_imports_hash_password(self):
        assert hasattr(seed_module, 'hash_password')

    def test_imports_generate_join_model(self):
        assert hasattr(seed_module, 'generate_join_model')
