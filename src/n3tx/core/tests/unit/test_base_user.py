"""
Test plan for models/base_user.py
==================================

LOGIN TESTS
  - test_login_with_correct_credentials_returns_token
  - test_login_with_wrong_password_returns_401
  - test_login_with_non_existent_email_returns_401
  - test_login_email_case_insensitive
  - test_login_response_contains_user_object
  - test_login_password_not_in_response

REGISTER TESTS
  - test_register_user_creates_user_with_hashed_password
  - test_register_user_with_duplicate_email_returns_409
  - test_register_user_email_case_insensitive
  - test_register_user_response_contains_token
  - test_register_user_password_not_in_response
  - test_register_user_default_role_is_user
"""

import pytest
import tempfile
import os
from typing import ClassVar
from fastapi import HTTPException

from n3tx_core.models.base_user import BaseUser
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.authorize import configure, verify_password, decode_token
from n3tx_core import config

pytestmark = pytest.mark.unit


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def test_db(tmp_path):
    """Create a temporary SQLite database for testing."""
    db_path = tmp_path / "test_base_user.db"
    storage = SQLiteStorage(database=str(db_path))
    yield storage, str(db_path)
    # Cleanup
    if os.path.exists(str(db_path)):
        os.unlink(str(db_path))


@pytest.fixture
def user_model(test_db):
    """A concrete User model extending BaseUser."""
    storage, db_path = test_db

    class User(BaseUser):
        __tablename__: ClassVar[str] = 'users'
        __abstract__: ClassVar[bool] = False

    User.set_storage(storage)
    User.create_table()

    yield User

    # Clear any created users
    User._storage = None


@pytest.fixture
def configure_test_auth():
    """Configure auth with test secret."""
    configure(jwt_secret='test-base-user-secret', jwt_expiry_hours=1)
    yield
    # Restore to default
    from n3tx_core import config
    configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=config.JWT_EXPIRY_HOURS)


# ===================================================================
# LOGIN TESTS
# ===================================================================

class TestLogin:
    """BaseUser.login() method tests."""

    def test_login_with_correct_credentials_returns_token(self, user_model, configure_test_auth):
        """Login with correct credentials should return a JWT token."""
        user = user_model(name='Alice', email='alice@example.com')
        user._plain_password = 'alice123'
        created = user_model.create(user)

        result = user_model.login(email='alice@example.com', password='alice123')

        assert 'token' in result
        assert isinstance(result['token'], str)
        decoded = decode_token(result['token'])
        assert decoded['user_id'] == created.id
        assert decoded['email'] == 'alice@example.com'

    def test_login_with_wrong_password_returns_401(self, user_model, configure_test_auth):
        """Login with wrong password should raise HTTPException 401."""
        user = user_model(name='Bob', email='bob@example.com')
        user._plain_password = 'bob123'
        user_model.create(user)

        with pytest.raises(HTTPException) as exc_info:
            user_model.login(email='bob@example.com', password='wrong-password')

        assert exc_info.value.status_code == 401
        assert 'Invalid credentials' in exc_info.value.detail

    def test_login_with_non_existent_email_returns_401(self, user_model, configure_test_auth):
        """Login with non-existent email should raise HTTPException 401."""
        with pytest.raises(HTTPException) as exc_info:
            user_model.login(email='nonexistent@example.com', password='password')

        assert exc_info.value.status_code == 401
        assert 'Invalid credentials' in exc_info.value.detail

    def test_login_email_case_insensitive(self, user_model, configure_test_auth):
        """Login should be case-insensitive on email."""
        user = user_model(name='Charlie', email='charlie@example.com')
        user._plain_password = 'charlie123'
        user_model.create(user)

        result = user_model.login(email='CHARLIE@EXAMPLE.COM', password='charlie123')

        assert 'token' in result

    def test_login_response_contains_user_object(self, user_model, configure_test_auth):
        """Login response should include user object with schema metadata."""
        user = user_model(name='Diana', email='diana@example.com')
        user._plain_password = 'diana123'
        created = user_model.create(user)

        result = user_model.login(email='diana@example.com', password='diana123')

        assert 'user' in result
        assert result['user']['name'] == 'Diana'
        assert result['user']['email'] == 'diana@example.com'
        assert '$schema' in result['user']
        assert '$id' in result['user']

    def test_login_password_not_in_response(self, user_model, configure_test_auth):
        """Login response should NOT include password or password_hash."""
        user = user_model(name='Eve', email='eve@example.com')
        user._plain_password = 'eve123'
        user_model.create(user)

        result = user_model.login(email='eve@example.com', password='eve123')

        assert 'password' not in result['user']
        assert 'password_hash' not in result['user']
        assert '_plain_password' not in result['user']


# ===================================================================
# REGISTER TESTS
# ===================================================================

class TestRegisterUser:
    """BaseUser.register_user() method tests."""

    def test_register_user_creates_user_with_hashed_password(self, user_model, configure_test_auth):
        """Registration should create user with hashed password."""
        result = user_model.register_user(
            name='Frank',
            email='frank@example.com',
            password='frank123'
        )

        assert 'token' in result
        assert 'user' in result

        # Verify user was created
        users = user_model.list()
        frank = next((u for u in users if u.email == 'frank@example.com'), None)
        assert frank is not None
        assert frank.name == 'Frank'
        assert frank.password_hash is not None
        # Verify password was hashed correctly
        assert verify_password('frank123', frank.password_hash)

    def test_register_user_with_duplicate_email_returns_409(self, user_model, configure_test_auth):
        """Registration with duplicate email should raise HTTPException 409."""
        user_model.register_user(name='Grace', email='grace@example.com', password='grace123')

        with pytest.raises(HTTPException) as exc_info:
            user_model.register_user(name='Grace2', email='grace@example.com', password='different')

        assert exc_info.value.status_code == 409
        assert 'Email already registered' in exc_info.value.detail

    def test_register_user_email_case_insensitive(self, user_model, configure_test_auth):
        """Registration should treat emails as case-insensitive."""
        user_model.register_user(name='Hank', email='hank@example.com', password='hank123')

        with pytest.raises(HTTPException) as exc_info:
            user_model.register_user(name='Hank2', email='HANK@EXAMPLE.COM', password='different')

        assert exc_info.value.status_code == 409

    def test_register_user_response_contains_token(self, user_model, configure_test_auth):
        """Registration response should include JWT token."""
        result = user_model.register_user(
            name='Ivy',
            email='ivy@example.com',
            password='ivy123'
        )

        assert 'token' in result
        decoded = decode_token(result['token'])
        assert decoded['email'] == 'ivy@example.com'
        assert decoded['role'] == 'user'

    def test_register_user_password_not_in_response(self, user_model, configure_test_auth):
        """Registration response should NOT include password or password_hash."""
        result = user_model.register_user(
            name='Jack',
            email='jack@example.com',
            password='jack123'
        )

        assert 'password' not in result['user']
        assert 'password_hash' not in result['user']
        assert '_plain_password' not in result['user']

    def test_register_user_default_role_is_user(self, user_model, configure_test_auth):
        """Newly registered users should have default role 'user'."""
        result = user_model.register_user(
            name='Karen',
            email='karen@example.com',
            password='karen123'
        )

        assert result['user']['role'] == 'user'
        decoded = decode_token(result['token'])
        assert decoded['role'] == 'user'

    def test_register_user_email_normalized_to_lowercase(self, user_model, configure_test_auth):
        """Registration should normalize email to lowercase."""
        result = user_model.register_user(
            name='Leo',
            email='LEO@EXAMPLE.COM',
            password='leo123'
        )

        assert result['user']['email'] == 'leo@example.com'

        # Verify stored email is lowercase
        users = user_model.list()
        leo = next((u for u in users if u.name == 'Leo'), None)
        assert leo.email == 'leo@example.com'
