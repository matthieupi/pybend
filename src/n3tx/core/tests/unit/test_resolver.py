"""Tests for authorize/resolver.py — DefaultResolver."""

import pytest
from unittest.mock import MagicMock

from n3tx.core.authorize.resolver import DefaultResolver, AuthorizationResolver
from n3tx.core.authorize.context import AccessContext
from n3tx.core.authorize.rules import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx.core.authorize.errors import AccessDenied

pytestmark = pytest.mark.unit



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


class TestCustomResolver:
    """UT-10: Custom resolver implementation tests."""

    def test_custom_resolver_satisfies_protocol(self):
        """A custom class implementing the protocol should be recognized."""
        class CustomResolver:
            def resolve_rule(self, model_class, action):
                return ANYONE

            def authorize(self, context):
                pass

            def sql_filter_for(self, context):
                return ('1=1', [])

        resolver = CustomResolver()
        # Protocol structural check
        assert hasattr(resolver, 'resolve_rule')
        assert hasattr(resolver, 'authorize')
        assert hasattr(resolver, 'sql_filter_for')

    def test_custom_resolver_resolve_rule(self):
        """Custom resolver can return any rule."""
        class AlwaysAdminResolver:
            def resolve_rule(self, model_class, action):
                return ROLE('admin')
            def authorize(self, context):
                pass
            def sql_filter_for(self, context):
                return ('1=1', [])

        resolver = AlwaysAdminResolver()
        model = MagicMock()
        rule = resolver.resolve_rule(model, 'read')
        # Rule should be ROLE('admin')
        assert rule.to_dict()['rule'] == 'role'


class TestDefaultResolverEdgeCases:
    """UT-10: Edge cases for DefaultResolver."""

    def test_none_access_defaults_to_authenticated(self):
        """__access__ = None should default to AUTHENTICATED."""
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = None
        rule = resolver.resolve_rule(model, 'read')
        assert rule is AUTHENTICATED

    def test_empty_access_dict(self):
        """Empty __access__ dict — no matching action, no wildcard."""
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {}
        rule = resolver.resolve_rule(model, 'read')
        assert rule is AUTHENTICATED

    def test_authorize_owner_with_resource(self):
        """OWNER rule should check resource.user_owner."""
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'update': OWNER}
        model.__name__ = 'TestModel'
        resource = MagicMock()
        resource.user_owner = 5
        ctx = AccessContext(
            user={'user_id': 5, 'role': 'user'},
            action='update',
            model_class=model,
            resource=resource,
        )
        # Should not raise
        resolver.authorize(ctx)

    def test_authorize_owner_denies_non_owner(self):
        """OWNER rule should deny when user_id != resource.user_owner."""
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'update': OWNER}
        model.__name__ = 'TestModel'
        resource = MagicMock()
        resource.user_owner = 5
        ctx = AccessContext(
            user={'user_id': 99, 'role': 'user'},
            action='update',
            model_class=model,
            resource=resource,
        )
        with pytest.raises(AccessDenied):
            resolver.authorize(ctx)

    def test_sql_filter_for_anyone_returns_1eq1(self):
        """ANYONE rule should produce 1=1 filter."""
        resolver = DefaultResolver()
        model = MagicMock()
        model.__access__ = {'read': ANYONE}
        model.__name__ = 'TestModel'
        ctx = AccessContext(
            user={},
            action='read',
            model_class=model,
        )
        clause, params = resolver.sql_filter_for(ctx)
        assert clause == '1=1'
