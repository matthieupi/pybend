"""
Shared fixtures for N3TX unit tests.
Provides mock storage, test models, auth fixtures, and cleanup hooks.

Note: The parent tests/conftest.py imports from main.py which triggers
model registration. Unit tests should use mocks where possible and
reset registries between tests.
"""

import os
import sys
import sqlite3
import pytest
from unittest.mock import MagicMock
from typing import ClassVar

from n3tx.core import config


# ---------------------------------------------------------------------------
# Ensure DEBUG=False for all unit tests (example_api conftest sets it True)
# Individual tests can opt-in to DEBUG=True via their own fixtures.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _ensure_debug_off():
    original = config.DEBUG
    config.DEBUG = False
    yield
    config.DEBUG = original


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def jwt_secret():
    return 'test-secret-key-for-unit-tests'


@pytest.fixture
def configure_auth(jwt_secret):
    """Configure the authorize package with test settings."""
    from n3tx.core.authorize.auth import configure
    from n3tx.core import config
    configure(jwt_secret=jwt_secret, jwt_expiry_hours=1)
    yield
    # Restore to the n3tx config secret (not the authorize package default)
    configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=config.JWT_EXPIRY_HOURS)


@pytest.fixture
def test_user_dict():
    """A user dict as would come from JWT decode."""
    return {
        'user_id': 1,
        'email': 'test@example.com',
        'role': 'user',
    }


@pytest.fixture
def admin_user_dict():
    return {
        'user_id': 2,
        'email': 'admin@example.com',
        'role': 'admin',
    }


@pytest.fixture
def anonymous_user_dict():
    return {}


@pytest.fixture
def test_token(configure_auth, jwt_secret):
    """A valid JWT token for the test user."""
    from n3tx.core.authorize.auth import create_token
    return create_token(user_id=1, email='test@example.com', role='user')


@pytest.fixture
def admin_token(configure_auth, jwt_secret):
    """A valid JWT token for the admin user."""
    from n3tx.core.authorize.auth import create_token
    return create_token(user_id=2, email='admin@example.com', role='admin')


# ---------------------------------------------------------------------------
# Mock request fixture for route tests
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_request():
    """A mock FastAPI Request object."""
    request = MagicMock()
    request.state = MagicMock()
    request.state.user = {'user_id': 1, 'email': 'test@example.com', 'role': 'user'}
    return request


@pytest.fixture
def mock_anon_request():
    """A mock FastAPI Request for anonymous user."""
    request = MagicMock()
    request.state = MagicMock()
    request.state.user = {}
    return request


# ---------------------------------------------------------------------------
# Mock storage fixture (for unit tests that don't need real DB)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_storage():
    """A fully-mocked storage backend."""
    storage = MagicMock()
    storage.create.return_value = None
    storage.list.return_value = []
    storage.get.return_value = None
    storage.update.return_value = None
    storage.delete.return_value = None
    storage.create_table.return_value = None
    storage.migrate_table.return_value = None
    return storage
