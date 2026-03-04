"""Tests for authorize/context.py — AccessContext dataclass."""

import pytest
from unittest.mock import MagicMock
from dataclasses import FrozenInstanceError

from n3tx.core.authorize.context import AccessContext

pytestmark = pytest.mark.unit



class TestAccessContextProperties:

    def test_user_id(self):
        ctx = AccessContext(
            user={'user_id': 5, 'email': 'a@b.com', 'role': 'user'},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.user_id == 5

    def test_user_role(self):
        ctx = AccessContext(
            user={'user_id': 1, 'role': 'admin'},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.user_role == 'admin'

    def test_user_email(self):
        ctx = AccessContext(
            user={'user_id': 1, 'email': 'test@example.com'},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.user_email == 'test@example.com'

    def test_is_authenticated_true(self):
        ctx = AccessContext(
            user={'user_id': 1},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.is_authenticated is True

    def test_is_authenticated_false_empty(self):
        ctx = AccessContext(
            user={},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.is_authenticated is False

    def test_is_authenticated_false_no_user_id(self):
        ctx = AccessContext(
            user={'email': 'a@b.com'},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.is_authenticated is False

    def test_user_id_none_for_empty(self):
        ctx = AccessContext(
            user={},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.user_id is None

    def test_user_role_none_for_empty(self):
        ctx = AccessContext(
            user={},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.user_role is None


class TestAccessContextDefaults:

    def test_resource_default_none(self):
        ctx = AccessContext(
            user={'user_id': 1},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.resource is None

    def test_parent_id_default_none(self):
        ctx = AccessContext(
            user={'user_id': 1},
            action='read',
            model_class=MagicMock(),
        )
        assert ctx.parent_id is None

    def test_resource_set(self):
        resource = MagicMock()
        ctx = AccessContext(
            user={'user_id': 1},
            action='read',
            model_class=MagicMock(),
            resource=resource,
        )
        assert ctx.resource is resource

    def test_parent_id_set(self):
        ctx = AccessContext(
            user={'user_id': 1},
            action='read',
            model_class=MagicMock(),
            parent_id=42,
        )
        assert ctx.parent_id == 42


class TestAccessContextFrozen:

    def test_frozen_immutable(self):
        ctx = AccessContext(
            user={'user_id': 1},
            action='read',
            model_class=MagicMock(),
        )
        with pytest.raises(FrozenInstanceError):
            ctx.action = 'write'


class TestAccessContextAction:

    def test_standard_actions(self):
        for action in ('read', 'create', 'update', 'delete', 'list'):
            ctx = AccessContext(
                user={'user_id': 1},
                action=action,
                model_class=MagicMock(),
            )
            assert ctx.action == action

    def test_custom_action(self):
        ctx = AccessContext(
            user={'user_id': 1},
            action='publish',
            model_class=MagicMock(),
        )
        assert ctx.action == 'publish'
