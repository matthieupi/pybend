"""Tests for ActorModel._authorize() and handler_crud() auth integration.

Test plan for ActorModel authorization
=======================================

UNIT TESTS — _authorize() classmethod behavior
  - test_authorize_no_meta_user_passes_through
  - test_authorize_no_access_rules_passes_through
  - test_authorize_anyone_read_with_authenticated_user_passes
  - test_authorize_authenticated_create_with_unauthenticated_user_denies
  - test_authorize_authenticated_create_with_authenticated_user_passes
  - test_authorize_owner_check_user_owns_resource_passes
  - test_authorize_owner_check_user_does_not_own_resource_denies
  - test_authorize_role_admin_user_has_admin_role_passes
  - test_authorize_role_admin_user_has_user_role_denies

INTEGRATION TESTS — handler_crud() auth integration
  - test_handler_crud_create_checks_auth_before_creating
  - test_handler_crud_get_fetches_then_checks_auth_with_resource
  - test_handler_crud_list_reads_sql_filter_from_meta
  - test_handler_crud_update_fetches_then_checks_auth_with_resource
  - test_handler_crud_delete_fetches_then_checks_auth_with_resource
  - test_handler_crud_schema_has_no_auth_check
  - test_handler_crud_internal_message_passes_all_crud_ops

CONTRACT TESTS — error TX structure
  - test_authorize_returns_error_tx_with_403_code
  - test_authorize_error_tx_has_correct_structure
  - test_handler_crud_auth_denial_returns_error_directly

EDGE CASES — composite rules
  - test_authorize_or_rule_first_passes
  - test_authorize_or_rule_second_passes
  - test_authorize_and_rule_both_pass
  - test_authorize_and_rule_second_fails
  - test_authorize_owner_check_with_none_resource_passes_create
"""

import asyncio
from unittest.mock import patch, MagicMock

import pytest
from pydantic import Field

from n3tx_actors.tx import TX
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from .conftest import make_tx

pytestmark = pytest.mark.unit


# ===================================================================
# Test Model Fixtures
# ===================================================================

class AuthTestModel(ActorModel, auto_register=False):
    """Test model with comprehensive access rules.

    Note: __storable__ = False, so CRUD methods need to be mocked in tests
    that use handler_crud(). The _authorize() tests don't need mocking.
    """
    __tablename__ = 'auth_things'
    __storable__ = False
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': ROLE('admin'),
    }
    __owner_field__ = 'user_owner'

    name: str = Field(default='test')
    user_owner: int = Field(default=1)

    # Add stub methods for testing (handler_crud calls these)
    @classmethod
    def create(cls, instance):
        """Stub create method."""
        return instance

    @classmethod
    def get(cls, entity_id):
        """Stub get method."""
        return None

    @classmethod
    def list(cls, sql_filter=None, limit=None, offset=None):
        """Stub list method."""
        return {'data': [], 'meta': {}}

    @classmethod
    def update(cls, entity_id, data):
        """Stub update method."""
        return None

    @classmethod
    def delete(cls, entity_id):
        """Stub delete method."""
        pass


class NoAccessModel(ActorModel, auto_register=False):
    """Model with no __access__ declared."""
    __tablename__ = 'no_access_things'
    __storable__ = False
    name: str = Field(default='test')


class CompositeRuleModel(ActorModel, auto_register=False):
    """Model with composite access rules (OR, AND)."""
    __tablename__ = 'composite_things'
    __storable__ = False
    __access__ = {
        'read': OWNER | ROLE('admin'),  # OR rule
        'update': AUTHENTICATED & OWNER,  # AND rule
    }
    __owner_field__ = 'user_owner'

    name: str = Field(default='test')
    user_owner: int = Field(default=1)


# ===================================================================
# UNIT TESTS — _authorize() classmethod behavior
# ===================================================================

class TestAuthorizeClassmethod:
    """Test the _authorize() classmethod in isolation."""

    def test_authorize_no_meta_user_passes_through(self):
        """Internal message (no meta.user) should pass through unchecked."""
        tx = make_tx(name='create', target='auth_things', data={'name': 'test'})
        result = AuthTestModel._authorize('create', tx)
        assert result is None

    def test_authorize_no_access_rules_passes_through(self):
        """Model without __access__ should pass through unchecked."""
        tx = make_tx(
            name='create',
            target='no_access_things',
            data={'name': 'test'},
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        result = NoAccessModel._authorize('create', tx)
        assert result is None

    def test_authorize_anyone_read_with_authenticated_user_passes(self):
        """ANYONE read rule should pass for authenticated user."""
        tx = make_tx(
            name='read',
            target='auth_things',
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        result = AuthTestModel._authorize('read', tx)
        assert result is None

    def test_authorize_authenticated_create_with_unauthenticated_user_denies(self):
        """AUTHENTICATED create rule should deny unauthenticated user."""
        tx = make_tx(
            name='create',
            target='auth_things',
            data={'name': 'test'},
            meta={'user': {}},  # No user_id
        )
        result = AuthTestModel._authorize('create', tx)
        assert result is not None
        assert isinstance(result, TX)
        assert result.name == 'ERROR'
        assert result.data['code'] == 403
        assert 'Access denied' in result.data['message']

    def test_authorize_authenticated_create_with_authenticated_user_passes(self):
        """AUTHENTICATED create rule should pass for authenticated user."""
        tx = make_tx(
            name='create',
            target='auth_things',
            data={'name': 'test'},
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        result = AuthTestModel._authorize('create', tx)
        assert result is None

    def test_authorize_owner_check_user_owns_resource_passes(self):
        """OWNER update rule should pass when user owns the resource."""
        resource = AuthTestModel(id=1, name='thing', user_owner=1)
        tx = make_tx(
            name='update',
            target='auth_things',
            data={'id': 1, 'name': 'updated'},
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        result = AuthTestModel._authorize('update', tx, resource=resource)
        assert result is None

    def test_authorize_owner_check_user_does_not_own_resource_denies(self):
        """OWNER update rule should deny when user does not own the resource."""
        resource = AuthTestModel(id=1, name='thing', user_owner=2)  # Owner is user 2
        tx = make_tx(
            name='update',
            target='auth_things',
            data={'id': 1, 'name': 'updated'},
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        result = AuthTestModel._authorize('update', tx, resource=resource)
        assert result is not None
        assert isinstance(result, TX)
        assert result.name == 'ERROR'
        assert result.data['code'] == 403

    def test_authorize_role_admin_user_has_admin_role_passes(self):
        """ROLE('admin') delete rule should pass when user has admin role."""
        resource = AuthTestModel(id=1, name='thing', user_owner=1)
        tx = make_tx(
            name='delete',
            target='auth_things',
            data={'id': 1},
            meta={'user': {'user_id': 2, 'email': 'admin@test.com', 'role': 'admin'}},
        )
        result = AuthTestModel._authorize('delete', tx, resource=resource)
        assert result is None

    def test_authorize_role_admin_user_has_user_role_denies(self):
        """ROLE('admin') delete rule should deny when user has 'user' role."""
        resource = AuthTestModel(id=1, name='thing', user_owner=1)
        tx = make_tx(
            name='delete',
            target='auth_things',
            data={'id': 1},
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        result = AuthTestModel._authorize('delete', tx, resource=resource)
        assert result is not None
        assert isinstance(result, TX)
        assert result.name == 'ERROR'
        assert result.data['code'] == 403


# ===================================================================
# INTEGRATION TESTS — handler_crud() auth integration
# ===================================================================

class TestHandlerCrudAuthIntegration:
    """Test handler_crud() auth checks at correct points in the CRUD flow."""

    def test_handler_crud_create_checks_auth_before_creating(self):
        """Create should check auth BEFORE creating the instance."""
        tx = make_tx(
            name='create',
            target='auth_things',
            data={'name': 'test'},
            meta={'user': {}},  # Unauthenticated
        )
        result = AuthTestModel.handler_crud(tx)

        # Should return error TX immediately, never call create()
        assert isinstance(result, TX)
        assert result.name == 'ERROR'
        assert result.data['code'] == 403

    def test_handler_crud_get_fetches_then_checks_auth_with_resource(self):
        """Get should fetch instance THEN check auth with resource."""
        resource = AuthTestModel(id=1, name='thing', user_owner=1)

        with patch.object(AuthTestModel, 'get', return_value=resource) as mock_get:
            # User 2 trying to read (ANYONE rule allows read)
            tx = make_tx(
                name='get',
                target='auth_things',
                data={'id': 1},
                meta={'user': {'user_id': 2, 'email': 'other@test.com', 'role': 'user'}},
            )
            result = AuthTestModel.handler_crud(tx)

            # Should call get first (handler_crud passes populate from data)
            mock_get.assert_called_once_with(1, populate=None)

            # ANYONE read rule passes
            assert isinstance(result, dict)
            assert result['id'] == 1

    def test_handler_crud_list_reads_sql_filter_from_meta(self):
        """List should read sql_filter from tx.meta if present."""
        with patch.object(AuthTestModel, 'list', return_value={'data': [], 'meta': {}}) as mock_list:
            tx = make_tx(
                name='list',
                target='auth_things',
                data={'limit': 10, 'offset': 0},
                meta={
                    'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'},
                    'sql_filter': ('user_owner = ?', [1]),
                },
            )
            AuthTestModel.handler_crud(tx)

            # Should pass sql_filter from meta (handler_crud also passes populate)
            mock_list.assert_called_once_with(
                sql_filter=('user_owner = ?', [1]),
                limit=10,
                offset=0,
                populate=None,
            )

    def test_handler_crud_update_fetches_then_checks_auth_with_resource(self):
        """Update should fetch instance THEN check auth with resource."""
        resource = AuthTestModel(id=1, name='thing', user_owner=2)  # Owner is user 2

        with patch.object(AuthTestModel, 'get', return_value=resource):
            # User 1 trying to update (OWNER rule denies)
            tx = make_tx(
                name='update',
                target='auth_things',
                data={'id': 1, 'name': 'updated'},
                meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
            )
            result = AuthTestModel.handler_crud(tx)

            # Should deny after fetching
            assert isinstance(result, TX)
            assert result.name == 'ERROR'
            assert result.data['code'] == 403

    def test_handler_crud_delete_fetches_then_checks_auth_with_resource(self):
        """Delete should fetch instance THEN check auth with resource."""
        resource = AuthTestModel(id=1, name='thing', user_owner=1)

        with patch.object(AuthTestModel, 'get', return_value=resource):
            # User 1 trying to delete (ROLE('admin') denies for 'user' role)
            tx = make_tx(
                name='delete',
                target='auth_things',
                data={'id': 1},
                meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
            )
            result = AuthTestModel.handler_crud(tx)

            # Should deny after fetching
            assert isinstance(result, TX)
            assert result.name == 'ERROR'
            assert result.data['code'] == 403

    def test_handler_crud_schema_has_no_auth_check(self):
        """Schema action should have no auth check (always passes)."""
        with patch.object(AuthTestModel, 'schema', return_value={'name': 'AuthTestModel'}) as mock_schema:
            # Unauthenticated request for schema
            tx = make_tx(name='schema', target='auth_things', meta={})
            result = AuthTestModel.handler_crud(tx)

            # Should call schema without auth
            mock_schema.assert_called_once()
            assert result == {'name': 'AuthTestModel'}

    def test_handler_crud_internal_message_passes_all_crud_ops(self):
        """Internal message (no meta.user) should pass through all CRUD operations."""
        resource = AuthTestModel(id=1, name='thing', user_owner=1)

        # Test update (no user in meta)
        with patch.object(AuthTestModel, 'get', return_value=resource):
            with patch.object(AuthTestModel, 'update', return_value=resource) as mock_update:
                tx = make_tx(
                    name='update',
                    target='auth_things',
                    data={'id': 1, 'name': 'updated'},
                    meta={},  # No user
                )
                result = AuthTestModel.handler_crud(tx)

                # Should proceed without auth check
                mock_update.assert_called_once()
                assert isinstance(result, dict)


# ===================================================================
# CONTRACT TESTS — error TX structure
# ===================================================================

class TestErrorTXStructure:
    """Verify error TX structure matches contract."""

    def test_authorize_returns_error_tx_with_403_code(self):
        """Error TX should have code=403 for access denial."""
        tx = make_tx(
            name='create',
            target='auth_things',
            data={'name': 'test'},
            meta={'user': {}},  # Unauthenticated
        )
        result = AuthTestModel._authorize('create', tx)

        assert result is not None
        assert result.data.get('code') == 403

    def test_authorize_error_tx_has_correct_structure(self):
        """Error TX should have correct structure."""
        tx = make_tx(
            name='create',
            target='auth_things',
            data={'name': 'test'},
            meta={'user': {}},
        )
        result = AuthTestModel._authorize('create', tx)

        # Check TX structure
        assert result.name == 'ERROR'
        assert result.source == tx.target  # Swapped
        assert result.target == tx.source  # Swapped
        assert 'message' in result.data
        assert 'code' in result.data
        assert result.meta.get('error') is True
        assert result.meta.get('req') == tx.uuid

    def test_handler_crud_auth_denial_returns_error_directly(self):
        """handler_crud() should return error TX directly (not wrapped)."""
        tx = make_tx(
            name='create',
            target='auth_things',
            data={'name': 'test'},
            meta={'user': {}},
        )
        result = AuthTestModel.handler_crud(tx)

        # Should be a TX, not a dict
        assert isinstance(result, TX)
        assert result.name == 'ERROR'


# ===================================================================
# EDGE CASES — composite rules
# ===================================================================

class TestCompositeRules:
    """Test authorization with composite rules (OR, AND)."""

    def test_authorize_or_rule_first_passes(self):
        """OR rule should pass if first condition passes (owner match)."""
        resource = CompositeRuleModel(id=1, name='thing', user_owner=1)
        tx = make_tx(
            name='read',
            target='composite_things',
            data={'id': 1},
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        result = CompositeRuleModel._authorize('read', tx, resource=resource)
        assert result is None  # OWNER passes

    def test_authorize_or_rule_second_passes(self):
        """OR rule should pass if second condition passes (admin role)."""
        resource = CompositeRuleModel(id=1, name='thing', user_owner=2)  # Not owner
        tx = make_tx(
            name='read',
            target='composite_things',
            data={'id': 1},
            meta={'user': {'user_id': 1, 'email': 'admin@test.com', 'role': 'admin'}},
        )
        result = CompositeRuleModel._authorize('read', tx, resource=resource)
        assert result is None  # ROLE('admin') passes

    def test_authorize_and_rule_both_pass(self):
        """AND rule should pass only if both conditions pass."""
        resource = CompositeRuleModel(id=1, name='thing', user_owner=1)
        tx = make_tx(
            name='update',
            target='composite_things',
            data={'id': 1, 'name': 'updated'},
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        result = CompositeRuleModel._authorize('update', tx, resource=resource)
        assert result is None  # AUTHENTICATED & OWNER both pass

    def test_authorize_and_rule_second_fails(self):
        """AND rule should fail if second condition fails."""
        resource = CompositeRuleModel(id=1, name='thing', user_owner=2)  # Not owner
        tx = make_tx(
            name='update',
            target='composite_things',
            data={'id': 1, 'name': 'updated'},
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        result = CompositeRuleModel._authorize('update', tx, resource=resource)
        assert isinstance(result, TX)
        assert result.name == 'ERROR'

    def test_authorize_owner_check_with_none_resource_passes_create(self):
        """OWNER check with None resource should pass (for create operations)."""
        tx = make_tx(
            name='create',
            target='composite_things',
            data={'name': 'new'},
            meta={'user': {'user_id': 1, 'email': 'test@test.com', 'role': 'user'}},
        )
        # Even though OWNER is in update rule, this tests the OWNER.evaluate() None behavior
        result = CompositeRuleModel._authorize('update', tx, resource=None)
        # AUTHENTICATED passes, OWNER with None resource returns True
        assert result is None


# ===================================================================
# CLEANUP / RESOURCE TESTS
# ===================================================================

class TestResourceCleanup:
    """Verify no auth state leaks between operations."""

    def test_multiple_auth_checks_isolated(self):
        """Multiple auth checks should not interfere with each other."""
        resource1 = AuthTestModel(id=1, name='thing1', user_owner=1)
        resource2 = AuthTestModel(id=2, name='thing2', user_owner=2)

        tx1 = make_tx(
            name='update',
            target='auth_things',
            data={'id': 1},
            meta={'user': {'user_id': 1, 'role': 'user'}},
        )
        tx2 = make_tx(
            name='update',
            target='auth_things',
            data={'id': 2},
            meta={'user': {'user_id': 1, 'role': 'user'}},
        )

        result1 = AuthTestModel._authorize('update', tx1, resource=resource1)
        result2 = AuthTestModel._authorize('update', tx2, resource=resource2)

        # First passes (owner), second denies (not owner)
        assert result1 is None
        assert isinstance(result2, TX)
        assert result2.name == 'ERROR'
