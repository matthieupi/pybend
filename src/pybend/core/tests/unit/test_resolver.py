"""Tests for authorize/resolver.py — DefaultResolver."""

import pytest
from unittest.mock import MagicMock

from authorize.resolver import DefaultResolver, AuthorizationResolver
from authorize.context import AccessContext
from authorize.rules import ANYONE, AUTHENTICATED, OWNER, ROLE
from authorize.errors import AccessDenied


def _make_ctx(user_id=None, role='user', action='read',
              model_class=None, resource=None):
    user = {}
    if user_id is not None:
        user = {'user_id': user_id, 'role': role, 'email': 'test@test.com'}
    if model_class is None:
        model_class = MagicMock()
        model_class.__name__ = 'TestModel'
    return AccessContext(user=user, action=action, model_class=model_class,
                         resource=resource)


class TestResolveRule:

    def test_from_access_dict(self):
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'read': ANYONE, 'create': AUTHENTICATED}
        rule = resolver.resolve_rule(model, 'read')
        assert rule is ANYONE

    def test_from_access_dict_create(self):
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'read': ANYONE, 'create': AUTHENTICATED}
        rule = resolver.resolve_rule(model, 'create')
        assert rule is AUTHENTICATED

    def test_wildcard_fallback(self):
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'*': ANYONE}
        rule = resolver.resolve_rule(model, 'anything')
        assert rule is ANYONE

    def test_no_access_defaults_authenticated(self):
        resolver = DefaultResolver()
        model = MagicMock(spec=[])
        delattr(model, '__access__')  # ensure no __access__
        model_no_access = type('Model', (), {})()
        # Use a real mock without __access__
        m = MagicMock()
        m.__access__ = None
        rule = resolver.resolve_rule(m, 'read')
        assert rule is AUTHENTICATED

    def test_action_not_in_dict_no_wildcard(self):
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'read': ANYONE}
        rule = resolver.resolve_rule(model, 'delete')
        assert rule is AUTHENTICATED


class TestAuthorize:

    def test_allowed(self):
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'read': ANYONE}
        model.__name__ = 'TestModel'
        ctx = AccessContext(
            user={},
            action='read',
            model_class=model,
        )
        # Should not raise
        resolver.authorize(ctx)

    def test_denied(self):
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'create': AUTHENTICATED}
        model.__name__ = 'TestModel'
        ctx = AccessContext(
            user={},  # anonymous
            action='create',
            model_class=model,
        )
        with pytest.raises(AccessDenied):
            resolver.authorize(ctx)

    def test_denied_attributes(self):
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'create': AUTHENTICATED}
        model.__name__ = 'TestModel'
        ctx = AccessContext(
            user={},
            action='create',
            model_class=model,
        )
        try:
            resolver.authorize(ctx)
            assert False, "Should have raised AccessDenied"
        except AccessDenied as e:
            assert e.action == 'create'
            assert e.model == 'TestModel'


class TestSqlFilterFor:

    def test_returns_filter(self):
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'read': ANYONE}
        model.__name__ = 'TestModel'
        ctx = AccessContext(
            user={'user_id': 1, 'role': 'user'},
            action='read',
            model_class=model,
        )
        result = resolver.sql_filter_for(ctx)
        assert result is not None
        clause, params = result
        assert isinstance(clause, str)

    def test_owner_filter(self):
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'read': OWNER}
        model.__name__ = 'TestModel'
        ctx = AccessContext(
            user={'user_id': 5, 'role': 'user'},
            action='read',
            model_class=model,
        )
        clause, params = resolver.sql_filter_for(ctx)
        assert 'user_owner' in clause
        assert 5 in params


class TestProtocol:

    def test_protocol_check(self):
        resolver = DefaultResolver()
        assert isinstance(resolver, AuthorizationResolver)
