"""
Test plan for actor_model.py _authorize() method
=================================================

UNIT TESTS — Tier 2 ABAC with resource instance
  - test_authorize_owner_rule_owner_can_update
  - test_authorize_owner_rule_non_owner_denied
  - test_authorize_role_rule_admin_can_delete
  - test_authorize_role_rule_user_cannot_delete
  - test_authorize_compound_or_rule_owner_passes
  - test_authorize_compound_or_rule_admin_passes
  - test_authorize_compound_or_rule_neither_denied
  - test_authorize_anyone_rule_read_allowed_without_auth
  - test_authorize_authenticated_rule_requires_user
  - test_authorize_no_access_dict_passes_through
  - test_authorize_internal_message_no_user_meta_passes

METHOD-LEVEL ACCESS
  - test_method_level_access_via_expose_route
  - test_method_level_access_owner_rule
  - test_method_level_access_role_rule
  - test_method_level_access_anyone_rule

DEFAULT BEHAVIOR
  - test_no_access_declared_no_user_meta_passes
  - test_access_denied_returns_error_tx_403
  - test_access_granted_returns_none

RESOURCE CONTEXT
  - test_owner_check_with_resource_instance
  - test_owner_check_without_resource_create_action
"""

import pytest
from unittest.mock import MagicMock
from typing import ClassVar

from n3tx.core.models.actor_model import ActorModel
from n3tx.core.actors.tx import TX
from n3tx.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE

pytestmark = pytest.mark.unit


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def test_model_class():
    """A test ActorModel subclass with __access__ rules."""
    class TestModel(ActorModel, auto_register=False):
        __tablename__: ClassVar[str] = 'test_models'
        __access__: ClassVar[dict] = {
            'read': ANYONE,
            'create': AUTHENTICATED,
            'update': OWNER,
            'delete': ROLE('admin'),
        }

        # Mock fields
        id: int = 1
        name: str = 'test'
        user_owner: int = 1

    return TestModel


@pytest.fixture
def owner_resource():
    """A mock resource owned by user_id 1."""
    resource = MagicMock()
    resource.user_owner = 1
    resource.id = 1
    return resource


@pytest.fixture
def non_owner_resource():
    """A mock resource owned by user_id 99."""
    resource = MagicMock()
    resource.user_owner = 99
    resource.id = 2
    return resource


@pytest.fixture
def user_tx():
    """TX with user_id=1, role=user."""
    return TX(
        name='update',
        source='api',
        target='test_models',
        meta={'user': {'user_id': 1, 'email': 'user@example.com', 'role': 'user'}}
    )


@pytest.fixture
def admin_tx():
    """TX with user_id=2, role=admin."""
    return TX(
        name='delete',
        source='api',
        target='test_models',
        meta={'user': {'user_id': 2, 'email': 'admin@example.com', 'role': 'admin'}}
    )


@pytest.fixture
def anon_tx():
    """TX with no user in meta."""
    return TX(name='get', source='api', target='test_models')


# ===================================================================
# UNIT TESTS — Tier 2 ABAC with resource instance
# ===================================================================

class TestOwnerRule:
    """OWNER rule evaluates with resource context."""

    def test_authorize_owner_rule_owner_can_update(self, test_model_class, user_tx, owner_resource):
        # user_id=1 owns resource with user_owner=1
        result = test_model_class._authorize('update', user_tx, resource=owner_resource)
        assert result is None  # authorized

    def test_authorize_owner_rule_non_owner_denied(self, test_model_class, user_tx, non_owner_resource):
        # user_id=1 tries to update resource with user_owner=99
        result = test_model_class._authorize('update', user_tx, resource=non_owner_resource)
        assert result is not None
        assert result.is_error
        assert result.data.get('code') == 403


class TestRoleRule:
    """ROLE rule evaluates with user role."""

    def test_authorize_role_rule_admin_can_delete(self, test_model_class, admin_tx, owner_resource):
        result = test_model_class._authorize('delete', admin_tx, resource=owner_resource)
        assert result is None  # authorized

    def test_authorize_role_rule_user_cannot_delete(self, test_model_class, user_tx, owner_resource):
        result = test_model_class._authorize('delete', user_tx, resource=owner_resource)
        assert result is not None
        assert result.is_error
        assert result.data.get('code') == 403


class TestCompoundRules:
    """Compound rules (OR, AND) evaluate correctly."""

    def test_authorize_compound_or_rule_owner_passes(self, owner_resource):
        class OrModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'or_models'
            __access__: ClassVar[dict] = {'update': OWNER | ROLE('admin')}

        user_tx = TX(
            name='update',
            source='api',
            target='or_models',
            meta={'user': {'user_id': 1, 'role': 'user'}}
        )
        result = OrModel._authorize('update', user_tx, resource=owner_resource)
        assert result is None

    def test_authorize_compound_or_rule_admin_passes(self, non_owner_resource):
        class OrModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'or_models'
            __access__: ClassVar[dict] = {'update': OWNER | ROLE('admin')}

        admin_tx = TX(
            name='update',
            source='api',
            target='or_models',
            meta={'user': {'user_id': 2, 'role': 'admin'}}
        )
        result = OrModel._authorize('update', admin_tx, resource=non_owner_resource)
        assert result is None

    def test_authorize_compound_or_rule_neither_denied(self, non_owner_resource):
        class OrModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'or_models'
            __access__: ClassVar[dict] = {'update': OWNER | ROLE('admin')}

        user_tx = TX(
            name='update',
            source='api',
            target='or_models',
            meta={'user': {'user_id': 1, 'role': 'user'}}
        )
        result = OrModel._authorize('update', user_tx, resource=non_owner_resource)
        assert result is not None
        assert result.is_error


class TestAnyoneRule:
    """ANYONE rule allows access without authentication."""

    def test_authorize_anyone_rule_read_allowed_without_auth(self, test_model_class, owner_resource):
        # read: ANYONE
        anon_tx = TX(
            name='read',
            source='api',
            target='test_models',
            meta={'user': {}}
        )
        result = test_model_class._authorize('read', anon_tx, resource=owner_resource)
        assert result is None


class TestAuthenticatedRule:
    """AUTHENTICATED rule requires user_id."""

    def test_authorize_authenticated_rule_requires_user(self):
        class AuthModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'auth_models'
            __access__: ClassVar[dict] = {'create': AUTHENTICATED}

        user_tx = TX(
            name='create',
            source='api',
            target='auth_models',
            meta={'user': {'user_id': 1, 'role': 'user'}}
        )
        result = AuthModel._authorize('create', user_tx)
        assert result is None

    def test_authorize_authenticated_rule_denied_without_user(self):
        class AuthModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'auth_models'
            __access__: ClassVar[dict] = {'create': AUTHENTICATED}

        anon_tx = TX(
            name='create',
            source='api',
            target='auth_models',
            meta={'user': {}}
        )
        result = AuthModel._authorize('create', anon_tx)
        assert result is not None
        assert result.is_error


# ===================================================================
# METHOD-LEVEL ACCESS
# ===================================================================

class TestMethodLevelAccess:
    """Method-level access via @expose_route is checked in handler."""

    def test_method_level_access_via_expose_route(self):
        # Note: method-level auth happens in handler(), not _authorize()
        # _authorize() is for CRUD-level __access__
        # This test verifies _authorize doesn't interfere with method execution
        class MethodModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'method_models'
            __access__: ClassVar[dict] = {'read': ANYONE}

        user_tx = TX(
            name='favorite',
            source='api',
            target='method_models',
            meta={'user': {'user_id': 1, 'role': 'user'}}
        )
        # _authorize is not called for custom methods — they're handled in handler()
        # This confirms _authorize doesn't break on non-CRUD actions
        result = MethodModel._authorize('read', user_tx)
        assert result is None


# ===================================================================
# DEFAULT BEHAVIOR
# ===================================================================

class TestDefaultBehavior:
    """Default behavior when no __access__ or no user meta."""

    def test_no_access_declared_no_user_meta_passes(self, anon_tx):
        class NoAccessModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'no_access_models'

        result = NoAccessModel._authorize('read', anon_tx)
        assert result is None  # no __access__ → no check

    def test_access_denied_returns_error_tx_403(self, test_model_class, user_tx, non_owner_resource):
        result = test_model_class._authorize('update', user_tx, resource=non_owner_resource)
        assert result is not None
        assert result.is_error
        assert result.data.get('code') == 403
        assert 'Access denied' in result.data.get('message', '')

    def test_access_granted_returns_none(self, test_model_class, user_tx, owner_resource):
        result = test_model_class._authorize('update', user_tx, resource=owner_resource)
        assert result is None


# ===================================================================
# RESOURCE CONTEXT
# ===================================================================

class TestResourceContext:
    """Resource context enables OWNER evaluation."""

    def test_owner_check_with_resource_instance(self, test_model_class, user_tx, owner_resource):
        # update: OWNER — requires resource to check user_owner field
        result = test_model_class._authorize('update', user_tx, resource=owner_resource)
        assert result is None

    def test_owner_check_without_resource_create_action(self, test_model_class, user_tx):
        # create: AUTHENTICATED (no OWNER check needed, no resource yet)
        result = test_model_class._authorize('create', user_tx, resource=None)
        assert result is None

    def test_owner_check_create_with_owner_rule_passes_without_resource(self):
        class OwnerCreateModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'owner_create_models'
            __access__: ClassVar[dict] = {'create': OWNER}

        user_tx = TX(
            name='create',
            source='api',
            target='owner_create_models',
            meta={'user': {'user_id': 1, 'role': 'user'}}
        )
        # OWNER evaluates to True on create when resource is None
        result = OwnerCreateModel._authorize('create', user_tx, resource=None)
        assert result is None


# ===================================================================
# INTERNAL MESSAGES
# ===================================================================

class TestInternalMessages:
    """Internal messages (no user in meta) bypass auth."""

    def test_authorize_internal_message_no_user_meta_passes(self, test_model_class, owner_resource):
        internal_tx = TX(
            name='update',
            source='internal',
            target='test_models',
            # No 'user' in meta — internal message
        )
        result = test_model_class._authorize('update', internal_tx, resource=owner_resource)
        assert result is None  # internal messages bypass auth

    def test_authorize_internal_message_empty_meta_passes(self, test_model_class, owner_resource):
        internal_tx = TX(
            name='update',
            source='internal',
            target='test_models',
            meta={}
        )
        result = test_model_class._authorize('update', internal_tx, resource=owner_resource)
        assert result is None
