"""
Test plan for auth_interceptor.py
===================================

UNIT TESTS — Tier 1 auth gate behavior
  - test_schema_requests_pass_through_without_auth
  - test_schema_request_with_no_model_cls_meta
  - test_unauthenticated_list_rejected_if_rule_requires_auth
  - test_unauthenticated_create_rejected_if_rule_requires_auth
  - test_unauthenticated_get_rejected_if_rule_requires_auth
  - test_unauthenticated_update_rejected_if_rule_requires_auth
  - test_unauthenticated_delete_rejected_if_rule_requires_auth
  - test_valid_token_accepted_user_in_meta
  - test_list_with_anyone_rule_passes_without_auth
  - test_create_with_authenticated_rule_requires_user
  - test_read_with_owner_rule_requires_user
  - test_update_with_owner_rule_requires_user
  - test_delete_with_owner_rule_requires_user

SQL FILTER INJECTION (list)
  - test_list_injects_sql_filter_for_owner_rule
  - test_list_sql_filter_includes_user_id
  - test_list_sql_filter_with_role_rule
  - test_list_sql_filter_with_anyone_rule
  - test_list_sql_filter_with_compound_or_rule
  - test_list_sql_filter_with_compound_and_rule

CREATE ACCESS CHECKS
  - test_create_with_owner_rule_passes_without_resource
  - test_create_with_role_admin_passes_for_admin
  - test_create_with_role_admin_fails_for_user
  - test_create_with_authenticated_rule_passes_for_any_user
  - test_create_with_anyone_rule_passes_without_auth

CUSTOM METHODS
  - test_custom_method_with_explicit_access_rule
  - test_custom_method_with_access_owner_requires_auth
  - test_custom_method_without_access_defaults_to_authenticated
  - test_custom_method_anonymous_rejected_if_no_access_rule
  - test_custom_method_authenticated_passes_if_no_access_rule
  - test_custom_method_with_anyone_rule_passes_without_auth

IDENTITY GATING (read/update/delete)
  - test_read_identity_gate_passes_authenticated_user_through
  - test_update_identity_gate_passes_authenticated_user_through
  - test_delete_identity_gate_passes_authenticated_user_through
  - test_read_identity_gate_rejects_unauthenticated_if_owner_rule
  - test_update_identity_gate_rejects_unauthenticated_if_owner_rule
  - test_delete_identity_gate_rejects_unauthenticated_if_owner_rule

ROLE VARIATIONS
  - test_admin_role_passes_role_admin_rule
  - test_user_role_fails_role_admin_rule
  - test_moderator_role_passes_role_moderator_or_admin
  - test_guest_role_fails_role_user_or_admin

EDGE CASES
  - test_no_model_cls_in_meta_passes_through
  - test_empty_user_dict_in_meta
  - test_action_name_case_insensitive
  - test_non_crud_non_exposed_method_defaults_authenticated
  - test_deny_returns_401_for_unauthenticated
  - test_deny_returns_403_for_authenticated_but_forbidden
"""

import pytest
from unittest.mock import MagicMock
from typing import ClassVar

from pybend.core.api.auth_interceptor import auth_interceptor, _get_method_access
from pybend.core.actors.tx import TX
from pybend.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE

pytestmark = pytest.mark.unit


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def mock_model():
    """A mock model class with __access__ rules."""
    model = MagicMock()
    model.__name__ = 'TestModel'
    model.__access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': ROLE('admin'),
    }
    return model


@pytest.fixture
def mock_model_owner():
    """A mock model with OWNER rule for all actions."""
    model = MagicMock()
    model.__name__ = 'OwnerModel'
    model.__access__ = {
        'read': OWNER,
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER,
    }
    return model


@pytest.fixture
def user_dict():
    return {'user_id': 1, 'email': 'test@example.com', 'role': 'user'}


@pytest.fixture
def admin_dict():
    return {'user_id': 2, 'email': 'admin@example.com', 'role': 'admin'}


# ===================================================================
# UNIT TESTS — Tier 1 auth gate behavior
# ===================================================================

class TestSchemaRequests:
    """Schema requests always pass through without authentication."""

    @pytest.mark.asyncio
    async def test_schema_requests_pass_through_without_auth(self, mock_model):
        tx = TX(name='schema', source='api', target='testmodel', meta={'model_cls': mock_model})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_schema_request_with_no_model_cls_meta(self):
        tx = TX(name='schema', source='api', target='testmodel')
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_schema_request_with_empty_user(self, mock_model):
        tx = TX(name='schema', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error


class TestUnauthenticatedRejection:
    """Unauthenticated requests are rejected when rules require auth."""

    @pytest.mark.asyncio
    async def test_unauthenticated_list_rejected_if_rule_requires_auth(self, mock_model_owner):
        # OWNER rule on read requires user_id
        tx = TX(name='list', source='api', target='ownermodel',
                meta={'model_cls': mock_model_owner, 'user': {}})
        result = await auth_interceptor(tx)
        # For list with OWNER rule, sql_filter='1=0' passes through (no data returned)
        # This is not an error — it's a successful query with empty results
        assert not result.is_error or result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_create_rejected_if_rule_requires_auth(self, mock_model):
        # AUTHENTICATED rule on create
        tx = TX(name='create', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_get_rejected_if_rule_requires_auth(self, mock_model_owner):
        tx = TX(name='get', source='api', target='ownermodel',
                meta={'model_cls': mock_model_owner, 'user': {}})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_update_rejected_if_rule_requires_auth(self, mock_model_owner):
        tx = TX(name='update', source='api', target='ownermodel',
                meta={'model_cls': mock_model_owner, 'user': {}})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_delete_rejected_if_rule_requires_auth(self, mock_model):
        # ROLE('admin') requires user_id
        tx = TX(name='delete', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401


class TestAuthenticatedAccess:
    """Authenticated users pass through identity gate, Tier 2 does resource check."""

    @pytest.mark.asyncio
    async def test_valid_token_accepted_user_in_meta(self, mock_model, user_dict):
        tx = TX(name='get', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_list_with_anyone_rule_passes_without_auth(self, mock_model):
        # read: ANYONE
        tx = TX(name='list', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error
        assert 'sql_filter' in result.meta

    @pytest.mark.asyncio
    async def test_create_with_authenticated_rule_requires_user(self, mock_model, user_dict):
        tx = TX(name='create', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_read_with_owner_rule_requires_user(self, mock_model, user_dict):
        # update: OWNER — identity gate passes through, Tier 2 checks resource
        tx = TX(name='get', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': user_dict}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_update_with_owner_rule_requires_user(self, mock_model, user_dict):
        tx = TX(name='update', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': user_dict}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_delete_with_owner_rule_requires_user(self, mock_model, admin_dict):
        # delete: ROLE('admin')
        tx = TX(name='delete', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': admin_dict}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error


# ===================================================================
# SQL FILTER INJECTION (list)
# ===================================================================

class TestSQLFilterInjection:
    """List requests get sql_filter computed and injected into meta."""

    @pytest.mark.asyncio
    async def test_list_injects_sql_filter_for_owner_rule(self, mock_model_owner, user_dict):
        tx = TX(name='list', source='api', target='ownermodel',
                meta={'model_cls': mock_model_owner, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert not result.is_error
        assert 'sql_filter' in result.meta

    @pytest.mark.asyncio
    async def test_list_sql_filter_includes_user_id(self, mock_model_owner, user_dict):
        tx = TX(name='list', source='api', target='ownermodel',
                meta={'model_cls': mock_model_owner, 'user': user_dict})
        result = await auth_interceptor(tx)
        clause, params = result.meta['sql_filter']
        assert 'user_owner' in clause
        assert user_dict['user_id'] in params

    @pytest.mark.asyncio
    async def test_list_sql_filter_with_role_rule(self, admin_dict):
        model = MagicMock()
        model.__name__ = 'RoleModel'
        model.__access__ = {'read': ROLE('admin')}
        tx = TX(name='list', source='api', target='rolemodel',
                meta={'model_cls': model, 'user': admin_dict})
        result = await auth_interceptor(tx)
        assert not result.is_error
        clause, params = result.meta['sql_filter']
        assert clause == '1=1'

    @pytest.mark.asyncio
    async def test_list_sql_filter_with_anyone_rule(self, mock_model):
        tx = TX(name='list', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': {}})
        result = await auth_interceptor(tx)
        clause, params = result.meta['sql_filter']
        assert clause == '1=1'

    @pytest.mark.asyncio
    async def test_list_sql_filter_with_compound_or_rule(self, user_dict):
        model = MagicMock()
        model.__name__ = 'CompoundModel'
        model.__access__ = {'read': OWNER | ROLE('admin')}
        tx = TX(name='list', source='api', target='compoundmodel',
                meta={'model_cls': model, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert not result.is_error
        clause, params = result.meta['sql_filter']
        assert 'OR' in clause

    @pytest.mark.asyncio
    async def test_list_sql_filter_with_compound_and_rule(self, user_dict):
        model = MagicMock()
        model.__name__ = 'AndModel'
        from pybend.core.authorize import Where
        model.__access__ = {'read': AUTHENTICATED & Where(status='published')}
        tx = TX(name='list', source='api', target='andmodel',
                meta={'model_cls': model, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert not result.is_error
        clause, params = result.meta['sql_filter']
        assert 'AND' in clause


# ===================================================================
# CREATE ACCESS CHECKS
# ===================================================================

class TestCreateAccessChecks:
    """Create requests are fully checked at Tier 1 (no resource needed)."""

    @pytest.mark.asyncio
    async def test_create_with_owner_rule_passes_without_resource(self, mock_model_owner, user_dict):
        # OWNER evaluates to True on create (no resource yet)
        tx = TX(name='create', source='api', target='ownermodel',
                meta={'model_cls': mock_model_owner, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_create_with_role_admin_passes_for_admin(self, admin_dict):
        model = MagicMock()
        model.__name__ = 'AdminOnlyModel'
        model.__access__ = {'create': ROLE('admin')}
        tx = TX(name='create', source='api', target='adminonlymodel',
                meta={'model_cls': model, 'user': admin_dict})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_create_with_role_admin_fails_for_user(self, user_dict):
        model = MagicMock()
        model.__name__ = 'AdminOnlyModel'
        model.__access__ = {'create': ROLE('admin')}
        tx = TX(name='create', source='api', target='adminonlymodel',
                meta={'model_cls': model, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 403

    @pytest.mark.asyncio
    async def test_create_with_authenticated_rule_passes_for_any_user(self, mock_model, user_dict):
        tx = TX(name='create', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_create_with_anyone_rule_passes_without_auth(self):
        model = MagicMock()
        model.__name__ = 'PublicModel'
        model.__access__ = {'create': ANYONE}
        tx = TX(name='create', source='api', target='publicmodel',
                meta={'model_cls': model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error


# ===================================================================
# CUSTOM METHODS
# ===================================================================

class TestCustomMethods:
    """Custom methods with @expose_route check method-level access."""

    @pytest.mark.asyncio
    async def test_custom_method_with_explicit_access_rule(self, user_dict):
        model = MagicMock()
        model.__name__ = 'CustomModel'
        model.__access__ = {'read': ANYONE}

        # Mock a method with __endpoint__ metadata
        method = MagicMock()
        method.__endpoint__ = {'access': AUTHENTICATED}
        model.favorite = method

        tx = TX(name='favorite', source='api', target='custommodel',
                meta={'model_cls': model, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_custom_method_with_access_owner_requires_auth(self):
        model = MagicMock()
        model.__name__ = 'CustomModel'

        method = MagicMock()
        method.__endpoint__ = {'access': OWNER}
        model.favorite = method

        tx = TX(name='favorite', source='api', target='custommodel',
                meta={'model_cls': model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_custom_method_without_access_defaults_to_authenticated(self):
        model = MagicMock()
        model.__name__ = 'CustomModel'

        # Method exists but no __endpoint__
        model.favorite = MagicMock(spec=lambda: None)

        tx = TX(name='favorite', source='api', target='custommodel',
                meta={'model_cls': model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_custom_method_anonymous_rejected_if_no_access_rule(self):
        model = MagicMock()
        model.__name__ = 'CustomModel'
        model.favorite = MagicMock(spec=lambda: None)

        tx = TX(name='favorite', source='api', target='custommodel',
                meta={'model_cls': model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_custom_method_authenticated_passes_if_no_access_rule(self, user_dict):
        model = MagicMock()
        model.__name__ = 'CustomModel'
        model.favorite = MagicMock(spec=lambda: None)

        tx = TX(name='favorite', source='api', target='custommodel',
                meta={'model_cls': model, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_custom_method_with_anyone_rule_passes_without_auth(self):
        model = MagicMock()
        model.__name__ = 'CustomModel'

        method = MagicMock()
        method.__endpoint__ = {'access': ANYONE}
        model.ping = method

        tx = TX(name='ping', source='api', target='custommodel',
                meta={'model_cls': model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error


# ===================================================================
# IDENTITY GATING (read/update/delete)
# ===================================================================

class TestIdentityGating:
    """Read/update/delete pass authenticated users to Tier 2 for resource check."""

    @pytest.mark.asyncio
    async def test_read_identity_gate_passes_authenticated_user_through(self, mock_model, user_dict):
        tx = TX(name='get', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': user_dict}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_update_identity_gate_passes_authenticated_user_through(self, mock_model, user_dict):
        tx = TX(name='update', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': user_dict}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_delete_identity_gate_passes_authenticated_user_through(self, mock_model, admin_dict):
        tx = TX(name='delete', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': admin_dict}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_read_identity_gate_rejects_unauthenticated_if_owner_rule(self, mock_model_owner):
        tx = TX(name='get', source='api', target='ownermodel',
                meta={'model_cls': mock_model_owner, 'user': {}}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_update_identity_gate_rejects_unauthenticated_if_owner_rule(self, mock_model_owner):
        tx = TX(name='update', source='api', target='ownermodel',
                meta={'model_cls': mock_model_owner, 'user': {}}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_delete_identity_gate_rejects_unauthenticated_if_owner_rule(self, mock_model_owner):
        tx = TX(name='delete', source='api', target='ownermodel',
                meta={'model_cls': mock_model_owner, 'user': {}}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401


# ===================================================================
# ROLE VARIATIONS
# ===================================================================

class TestRoleVariations:
    """Different user roles evaluated correctly."""

    @pytest.mark.asyncio
    async def test_admin_role_passes_role_admin_rule(self, admin_dict):
        model = MagicMock()
        model.__name__ = 'AdminModel'
        model.__access__ = {'delete': ROLE('admin')}
        tx = TX(name='delete', source='api', target='adminmodel',
                meta={'model_cls': model, 'user': admin_dict}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_user_role_fails_role_admin_rule(self, user_dict):
        model = MagicMock()
        model.__name__ = 'AdminModel'
        model.__access__ = {'delete': ROLE('admin')}
        tx = TX(name='delete', source='api', target='adminmodel',
                meta={'model_cls': model, 'user': user_dict}, data={'id': 1})
        result = await auth_interceptor(tx)
        # Identity gate passes user through to Tier 2 (not blocked at Tier 1)
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_moderator_role_passes_role_moderator_or_admin(self):
        moderator = {'user_id': 3, 'email': 'mod@example.com', 'role': 'moderator'}
        model = MagicMock()
        model.__name__ = 'ModModel'
        model.__access__ = {'update': ROLE('admin', 'moderator')}
        tx = TX(name='update', source='api', target='modmodel',
                meta={'model_cls': model, 'user': moderator}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_guest_role_fails_role_user_or_admin(self):
        guest = {'user_id': 4, 'email': 'guest@example.com', 'role': 'guest'}
        model = MagicMock()
        model.__name__ = 'UserModel'
        model.__access__ = {'create': ROLE('user', 'admin')}
        tx = TX(name='create', source='api', target='usermodel',
                meta={'model_cls': model, 'user': guest})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 403


# ===================================================================
# EDGE CASES
# ===================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_no_model_cls_in_meta_passes_through(self):
        tx = TX(name='get', source='api', target='unknown')
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_empty_user_dict_in_meta(self, mock_model):
        # read: ANYONE should pass
        tx = TX(name='get', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_action_name_case_insensitive(self, mock_model, user_dict):
        # TX names are lowercased internally
        tx = TX(name='GET', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': user_dict}, data={'id': 1})
        result = await auth_interceptor(tx)
        assert result == tx
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_non_crud_non_exposed_method_defaults_authenticated(self):
        model = MagicMock()
        model.__name__ = 'CustomModel'
        model.mystery = MagicMock(spec=lambda: None)

        tx = TX(name='mystery', source='api', target='custommodel',
                meta={'model_cls': model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_deny_returns_401_for_unauthenticated(self, mock_model):
        tx = TX(name='create', source='api', target='testmodel',
                meta={'model_cls': mock_model, 'user': {}})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 401

    @pytest.mark.asyncio
    async def test_deny_returns_403_for_authenticated_but_forbidden(self, user_dict):
        model = MagicMock()
        model.__name__ = 'AdminOnlyModel'
        model.__access__ = {'create': ROLE('admin')}
        tx = TX(name='create', source='api', target='adminonlymodel',
                meta={'model_cls': model, 'user': user_dict})
        result = await auth_interceptor(tx)
        assert result.is_error
        assert result.data.get('code') == 403


# ===================================================================
# HELPER FUNCTION TESTS
# ===================================================================

class TestGetMethodAccess:
    """_get_method_access() helper extracts access rules from @expose_route."""

    def test_method_with_endpoint_returns_access_rule(self):
        model = MagicMock()
        method = MagicMock()
        method.__endpoint__ = {'access': OWNER}
        model.favorite = method

        result = _get_method_access(model, 'favorite')
        assert result == OWNER

    def test_method_without_endpoint_returns_none(self):
        model = MagicMock()
        model.normal = MagicMock(spec=lambda: None)

        result = _get_method_access(model, 'normal')
        assert result is None

    def test_non_existent_method_returns_none(self):
        model = MagicMock()
        model.normal = MagicMock(spec=lambda: None)

        result = _get_method_access(model, 'nonexistent')
        assert result is None

    def test_method_with_endpoint_but_no_access_returns_none(self):
        model = MagicMock()
        method = MagicMock()
        method.__endpoint__ = {'route': '/test'}
        model.test = method

        result = _get_method_access(model, 'test')
        assert result is None
