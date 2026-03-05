"""
Tests for debug mode features.

Covers:
  - N3TXApp debug -> config.DEBUG propagation
  - BaseUser.register_user() auto-admin in debug mode
  - _build_meta() debug flag exposure
  - DebugLoggingMiddleware in FastAPIBackend
"""

import pytest
from unittest.mock import patch, MagicMock

from n3tx.core import config

pytestmark = pytest.mark.unit


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def restore_debug():
    """Ensure config.DEBUG is restored after each test."""
    original = config.DEBUG
    yield
    config.DEBUG = original


# ===================================================================
# 1. N3TXApp debug -> config.DEBUG propagation
# ===================================================================

class TestN3TXAppDebugPropagation:
    """N3TXApp(debug=True) should set config.DEBUG = True."""

    def test_debug_true_sets_config(self):
        """N3TXApp(debug=True) propagates to config.DEBUG."""
        config.DEBUG = False
        from n3tx.core.app import N3TXApp
        N3TXApp(debug=True)
        assert config.DEBUG is True

    def test_debug_false_does_not_override_env(self):
        """N3TXApp(debug=False) does NOT reset config.DEBUG."""
        config.DEBUG = True  # Simulate env var N3TX_DEBUG=true
        from n3tx.core.app import N3TXApp
        N3TXApp(debug=False)  # Default
        assert config.DEBUG is True  # NOT overridden

    def test_create_app_debug_true_sets_config(self):
        """create_app(debug=True) propagates to config.DEBUG."""
        config.DEBUG = False
        from n3tx.core.app import N3TXApp
        # Just test the constructor, not full build (which needs models)
        N3TXApp(debug=True)
        assert config.DEBUG is True


# ===================================================================
# 3. Auto-Admin Registration
# ===================================================================

class TestAutoAdminRegistration:
    """register_user() assigns role='admin' when config.DEBUG is True."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a temporary SQLite database."""
        from n3tx.core.storage.sqlite_storage import SQLiteStorage
        db_path = tmp_path / "test_debug_admin.db"
        storage = SQLiteStorage(database=str(db_path))
        yield storage

    @pytest.fixture
    def user_model(self, test_db):
        """A concrete User model extending BaseUser."""
        from typing import ClassVar
        from n3tx.core.models.base_user import BaseUser

        class DebugUser(BaseUser):
            __tablename__: ClassVar[str] = 'debug_users'
            __abstract__: ClassVar[bool] = False

        DebugUser.set_storage(test_db)
        DebugUser.create_table()
        yield DebugUser
        DebugUser._storage = None

    @pytest.fixture
    def configure_test_auth(self):
        """Configure auth with test secret."""
        from n3tx.core.authorize import configure
        configure(jwt_secret='test-debug-admin-secret', jwt_expiry_hours=1)
        yield
        configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=config.JWT_EXPIRY_HOURS)

    def test_register_user_admin_when_debug_true(self, user_model, configure_test_auth):
        """When DEBUG=True, new registrations get role='admin'."""
        config.DEBUG = True
        result = user_model.register_user(
            name='DebugAlice',
            email='debugalice@example.com',
            password='pass123',
        )
        # Debug envelope wraps the result
        inner = result['result']
        assert inner['user']['role'] == 'admin'

    def test_register_user_normal_when_debug_false(self, user_model, configure_test_auth):
        """When DEBUG=False, new registrations get role='user' (default)."""
        config.DEBUG = False
        result = user_model.register_user(
            name='NormalBob',
            email='normalbob@example.com',
            password='pass123',
        )
        assert result['user']['role'] == 'user'

    def test_register_user_token_has_admin_role_when_debug(self, user_model, configure_test_auth):
        """When DEBUG=True, the JWT token also carries role='admin'."""
        config.DEBUG = True
        from n3tx.core.authorize import decode_token
        result = user_model.register_user(
            name='DebugCharlie',
            email='debugcharlie@example.com',
            password='pass123',
        )
        inner = result['result']
        decoded = decode_token(inner['token'])
        assert decoded['role'] == 'admin'

    def test_register_user_stored_role_is_admin_when_debug(self, user_model, configure_test_auth):
        """When DEBUG=True, the stored user record has role='admin'."""
        config.DEBUG = True
        user_model.register_user(
            name='DebugDiana',
            email='debugdiana@example.com',
            password='pass123',
        )
        users = user_model.list()
        diana = next((u for u in users if u.email == 'debugdiana@example.com'), None)
        assert diana is not None
        assert diana.role == 'admin'

    def test_existing_user_role_unaffected_by_debug(self, user_model, configure_test_auth):
        """DEBUG mode only affects new registrations, not existing users."""
        # Register with DEBUG=False
        config.DEBUG = False
        user_model.register_user(
            name='ExistingEve',
            email='existingeve@example.com',
            password='pass123',
        )

        # Turn on DEBUG — existing user should still be 'user'
        config.DEBUG = True
        users = user_model.list()
        eve = next((u for u in users if u.email == 'existingeve@example.com'), None)
        assert eve.role == 'user'


# ===================================================================
# 4. _build_meta() debug flag
# ===================================================================

class TestBuildMetaDebugFlag:
    """_build_meta() should include 'debug' key from config.DEBUG."""

    def test_debug_true_in_meta(self):
        """When DEBUG=True, meta includes debug: True."""
        config.DEBUG = True
        from n3tx.core.api.discovery import _build_meta
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        assert meta['debug'] is True

    def test_debug_false_in_meta(self):
        """When DEBUG=False, meta includes debug: False."""
        config.DEBUG = False
        from n3tx.core.api.discovery import _build_meta
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        assert meta['debug'] is False

    def test_debug_key_exists(self):
        """The 'debug' key is always present in meta output."""
        from n3tx.core.api.discovery import _build_meta
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        assert 'debug' in meta

    def test_debug_is_boolean(self):
        """The 'debug' value is a boolean, not a string."""
        from n3tx.core.api.discovery import _build_meta
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        assert isinstance(meta['debug'], bool)


# ===================================================================
# 5. Debug Logging Middleware
# ===================================================================

class TestDebugLoggingMiddleware:
    """FastAPIBackend adds DebugLoggingMiddleware when DEBUG=True."""

    def test_middleware_added_when_debug_true(self):
        """When DEBUG=True, the app has more middleware than DEBUG=False."""
        config.DEBUG = True
        from n3tx.core.api.backend import FastAPIBackend
        backend_debug = FastAPIBackend(
            name="test", description="test", version="1.0.0",
        )
        debug_middleware_count = len(backend_debug.app.user_middleware)

        config.DEBUG = False
        backend_nodebug = FastAPIBackend(
            name="test", description="test", version="1.0.0",
        )
        nodebug_middleware_count = len(backend_nodebug.app.user_middleware)

        assert debug_middleware_count > nodebug_middleware_count

    def test_middleware_not_added_when_debug_false(self):
        """When DEBUG=False, no debug logging middleware is added."""
        config.DEBUG = False
        from n3tx.core.api.backend import FastAPIBackend
        backend = FastAPIBackend(
            name="test", description="test", version="1.0.0",
        )
        # Collect middleware class names
        middleware_names = [m.cls.__name__ for m in backend.app.user_middleware]
        assert 'DebugLoggingMiddleware' not in middleware_names

    def test_middleware_present_when_debug_true(self):
        """When DEBUG=True, DebugLoggingMiddleware is in the stack."""
        config.DEBUG = True
        from n3tx.core.api.backend import FastAPIBackend
        backend = FastAPIBackend(
            name="test", description="test", version="1.0.0",
        )
        middleware_names = [m.cls.__name__ for m in backend.app.user_middleware]
        assert 'DebugLoggingMiddleware' in middleware_names
