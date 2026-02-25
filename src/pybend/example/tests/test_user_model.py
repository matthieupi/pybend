"""Tests for models/user_model.py — User model, Bot model, field validators.

CG-8: Coverage gap — user_model.py has zero test coverage.
Tests User fields, role coercion, hidden fields, Bot model.
"""

import pytest
from typing import ClassVar
from unittest.mock import MagicMock

from pybend.example.models import User, Bot
from pybend.core.models.proto_model import ProtoModel
from pybend.core.models.storable_mixin import StorableMixin

pytestmark = pytest.mark.unit



class TestUserModel:

    def test_is_protomodel(self):
        assert issubclass(User, ProtoModel)

    def test_is_storable(self):
        assert issubclass(User, StorableMixin)

    def test_tablename(self):
        assert User.__tablename__ == 'users'

    def test_default_image(self):
        u = User(name="Test", email="test@test.com")
        assert 'ui-avatars.com' in u.image

    def test_default_role(self):
        u = User(name="Test", email="test@test.com")
        assert u.role == 'user'

    def test_age_optional(self):
        u = User(name="Test", email="test@test.com")
        assert u.age is None

    def test_password_hash_default_none(self):
        u = User(name="Test", email="test@test.com")
        assert u.password_hash is None

    def test_password_hash_excluded_from_dump(self):
        u = User(name="Test", email="test@test.com")
        u.password_hash = "hashed"
        data = u.model_dump()
        assert 'password_hash' not in data


class TestUserRoleValidator:

    def test_none_role_coerced(self):
        u = User(name="Test", email="test@test.com", role=None)
        assert u.role == 'user'

    def test_empty_string_coerced(self):
        u = User(name="Test", email="test@test.com", role='')
        assert u.role == 'user'

    def test_quoted_empty_coerced(self):
        u = User(name="Test", email="test@test.com", role="''")
        assert u.role == 'user'

    def test_admin_role_preserved(self):
        u = User(name="Test", email="test@test.com", role='admin')
        assert u.role == 'admin'

    def test_moderator_role_preserved(self):
        u = User(name="Test", email="test@test.com", role='moderator')
        assert u.role == 'moderator'


class TestUserHiddenFields:

    def test_hidden_fields_set(self):
        assert 'password_hash' in User.__hidden_fields__

    def test_hidden_fields_stripped_from_schema(self):
        schema = User.schema()
        assert 'password_hash' not in schema.get('properties', {})


class TestUserUIConfig:

    def test_renderer_item(self):
        assert User.__ui__['renderer']['item'] == 'ntt-user'


class TestUserExposedMethods:

    def test_login_has_endpoint(self):
        assert hasattr(User.login, '__endpoint__')

    def test_login_route(self):
        assert User.login.__endpoint__['route'] == '/login'

    def test_login_method_is_post(self):
        assert 'POST' in User.login.__endpoint__['methods']

    def test_register_has_endpoint(self):
        assert hasattr(User.register, '__endpoint__')

    def test_register_route(self):
        assert User.register.__endpoint__['route'] == '/register'

    def test_register_method_is_post(self):
        assert 'POST' in User.register.__endpoint__['methods']


class TestBotModel:

    def test_is_protomodel(self):
        assert issubclass(Bot, ProtoModel)

    def test_is_storable(self):
        assert issubclass(Bot, StorableMixin)

    def test_tablename(self):
        assert Bot.__tablename__ == 'bots'

    def test_has_required_fields(self):
        fields = Bot.model_fields
        for name in ('name', 'description', 'owner', 'version', 'status', 'prompt'):
            assert name in fields, f"Bot missing field: {name}"

    def test_basic_creation(self):
        b = Bot(name="TestBot", description="A bot", owner="alice",
                version="1.0", status="active", prompt="Be helpful")
        assert b.name == "TestBot"
        assert b.status == "active"
