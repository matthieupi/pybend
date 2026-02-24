"""Tests for authorize/rules.py — Access control rules."""

import pytest
from unittest.mock import MagicMock
from typing import ClassVar

from pydantic import Field

from authorize.rules import (
    AccessRule, ANYONE, AUTHENTICATED, OWNER, ROLE, Where,
    OrRule, AndRule, NotRule,
    _Anyone, _Authenticated, _Owner, _Role,
)
from authorize.context import AccessContext
from models.proto_model import ProtoModel


def _make_ctx(user_id=None, role='user', email='test@test.com',
              model_class=None, resource=None, action='read'):
    user = {}
    if user_id is not None:
        user = {'user_id': user_id, 'role': role, 'email': email}
    if model_class is None:
        model_class = MagicMock()
        model_class.__name__ = 'TestModel'
    return AccessContext(user=user, action=action, model_class=model_class,
                         resource=resource)


# ===================================================================
# ANYONE
# ===================================================================

class TestAnyone:

    def test_evaluate_always_true(self):
        ctx = _make_ctx(user_id=None)
        assert ANYONE.evaluate(ctx) is True

    def test_evaluate_authenticated(self):
        ctx = _make_ctx(user_id=1)
        assert ANYONE.evaluate(ctx) is True

    def test_sql_filter(self):
        ctx = _make_ctx()
        result = ANYONE.sql_filter(ctx)
        assert result == ('1=1', [])

    def test_to_dict(self):
        assert ANYONE.to_dict() == {'rule': 'anyone'}

    def test_is_singleton(self):
        assert isinstance(ANYONE, _Anyone)


# ===================================================================
# AUTHENTICATED
# ===================================================================

class TestAuthenticated:

    def test_authenticated_user(self):
        ctx = _make_ctx(user_id=1)
        assert AUTHENTICATED.evaluate(ctx) is True

    def test_anonymous_user(self):
        ctx = _make_ctx(user_id=None)
        assert AUTHENTICATED.evaluate(ctx) is False

    def test_sql_filter(self):
        ctx = _make_ctx(user_id=1)
        result = AUTHENTICATED.sql_filter(ctx)
        assert result == ('1=1', [])

    def test_to_dict(self):
        assert AUTHENTICATED.to_dict() == {'rule': 'authenticated'}


# ===================================================================
# OWNER
# ===================================================================

class TestOwner:

    def test_owner_matches(self):
        resource = MagicMock()
        resource.user_owner = 5
        ctx = _make_ctx(user_id=5, resource=resource)
        assert OWNER.evaluate(ctx) is True

    def test_owner_mismatch(self):
        resource = MagicMock()
        resource.user_owner = 5
        ctx = _make_ctx(user_id=99, resource=resource)
        assert OWNER.evaluate(ctx) is False

    def test_no_resource_create(self):
        ctx = _make_ctx(user_id=1, resource=None)
        assert OWNER.evaluate(ctx) is True

    def test_not_authenticated(self):
        resource = MagicMock()
        resource.user_owner = 5
        ctx = _make_ctx(user_id=None, resource=resource)
        assert OWNER.evaluate(ctx) is False

    def test_owner_href_extraction(self):
        resource = MagicMock()
        resource.user_owner = 'http://localhost:5000/users/5'
        ctx = _make_ctx(user_id=5, resource=resource)
        assert OWNER.evaluate(ctx) is True

    def test_owner_with_model_id(self):
        owner_obj = MagicMock()
        owner_obj.id = 5
        resource = MagicMock()
        resource.user_owner = owner_obj
        ctx = _make_ctx(user_id=5, resource=resource)
        assert OWNER.evaluate(ctx) is True

    def test_custom_owner_field(self):
        owner = _Owner(owner_field='author_id')
        resource = MagicMock()
        resource.author_id = 5
        ctx = _make_ctx(user_id=5, resource=resource)
        assert owner.evaluate(ctx) is True

    def test_custom_owner_field_mismatch(self):
        owner = _Owner(owner_field='author_id')
        resource = MagicMock()
        resource.author_id = 5
        ctx = _make_ctx(user_id=99, resource=resource)
        assert owner.evaluate(ctx) is False

    def test_model_owner_field_override(self):
        model = MagicMock()
        model.__name__ = 'M'
        model.__owner_field__ = 'creator'
        resource = MagicMock()
        resource.creator = 5
        ctx = AccessContext(
            user={'user_id': 5, 'role': 'user'},
            action='read',
            model_class=model,
            resource=resource,
        )
        assert OWNER.evaluate(ctx) is True

    def test_sql_filter_authenticated(self):
        ctx = _make_ctx(user_id=5)
        clause, params = OWNER.sql_filter(ctx)
        assert 'user_owner' in clause
        assert params == [5]

    def test_sql_filter_unauthenticated(self):
        ctx = _make_ctx(user_id=None)
        clause, params = OWNER.sql_filter(ctx)
        assert clause == '1=0'

    def test_to_dict(self):
        assert OWNER.to_dict() == {'rule': 'owner'}

    def test_to_dict_custom_field(self):
        owner = _Owner(owner_field='creator')
        d = owner.to_dict()
        assert d == {'rule': 'owner', 'field': 'creator'}


# ===================================================================
# ROLE
# ===================================================================

class TestRole:

    def test_matching_role(self):
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ROLE('admin')
        assert rule.evaluate(ctx) is True

    def test_non_matching_role(self):
        ctx = _make_ctx(user_id=1, role='user')
        rule = ROLE('admin')
        assert rule.evaluate(ctx) is False

    def test_multiple_roles(self):
        ctx = _make_ctx(user_id=1, role='moderator')
        rule = ROLE('admin', 'moderator')
        assert rule.evaluate(ctx) is True

    def test_not_authenticated(self):
        ctx = _make_ctx(user_id=None, role='admin')
        rule = ROLE('admin')
        assert rule.evaluate(ctx) is False

    def test_sql_filter_matching(self):
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ROLE('admin')
        clause, params = rule.sql_filter(ctx)
        assert clause == '1=1'

    def test_sql_filter_not_matching(self):
        ctx = _make_ctx(user_id=1, role='user')
        rule = ROLE('admin')
        clause, params = rule.sql_filter(ctx)
        assert clause == '1=0'

    def test_to_dict(self):
        rule = ROLE('admin')
        assert rule.to_dict() == {'rule': 'role', 'roles': ['admin']}

    def test_to_dict_multiple(self):
        rule = ROLE('admin', 'moderator')
        d = rule.to_dict()
        assert d['rule'] == 'role'
        assert sorted(d['roles']) == ['admin', 'moderator']


# ===================================================================
# Where
# ===================================================================

class TestWhere:

    def test_equal(self):
        resource = MagicMock()
        resource.status = 'published'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status='published')
        assert rule.evaluate(ctx) is True

    def test_equal_mismatch(self):
        resource = MagicMock()
        resource.status = 'draft'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status='published')
        assert rule.evaluate(ctx) is False

    def test_lt(self):
        resource = MagicMock()
        resource.price = 50
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(price__lt=100)
        assert rule.evaluate(ctx) is True

    def test_gt(self):
        resource = MagicMock()
        resource.price = 200
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(price__gt=100)
        assert rule.evaluate(ctx) is True

    def test_lte(self):
        resource = MagicMock()
        resource.price = 100
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(price__lte=100)
        assert rule.evaluate(ctx) is True

    def test_gte(self):
        resource = MagicMock()
        resource.price = 100
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(price__gte=100)
        assert rule.evaluate(ctx) is True

    def test_ne(self):
        resource = MagicMock()
        resource.status = 'draft'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status__ne='published')
        assert rule.evaluate(ctx) is True

    def test_in(self):
        resource = MagicMock()
        resource.status = 'published'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status__in=['published', 'draft'])
        assert rule.evaluate(ctx) is True

    def test_in_not_found(self):
        resource = MagicMock()
        resource.status = 'archived'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status__in=['published', 'draft'])
        assert rule.evaluate(ctx) is False

    def test_no_resource(self):
        ctx = _make_ctx(user_id=1, resource=None)
        rule = Where(status='published')
        assert rule.evaluate(ctx) is True

    def test_multiple_conditions(self):
        resource = MagicMock()
        resource.status = 'published'
        resource.price = 50
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status='published', price__lt=100)
        assert rule.evaluate(ctx) is True

    def test_multiple_conditions_one_fails(self):
        resource = MagicMock()
        resource.status = 'draft'
        resource.price = 50
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status='published', price__lt=100)
        assert rule.evaluate(ctx) is False

    def test_sql_filter_equal(self):
        ctx = _make_ctx(user_id=1)
        rule = Where(status='published')
        clause, params = rule.sql_filter(ctx)
        assert 'status = ?' in clause
        assert 'published' in params

    def test_sql_filter_lt(self):
        ctx = _make_ctx(user_id=1)
        rule = Where(price__lt=100)
        clause, params = rule.sql_filter(ctx)
        assert 'price < ?' in clause
        assert 100 in params

    def test_sql_filter_in(self):
        ctx = _make_ctx(user_id=1)
        rule = Where(status__in=['a', 'b'])
        clause, params = rule.sql_filter(ctx)
        assert 'IN' in clause
        assert params == ['a', 'b']

    def test_to_dict(self):
        rule = Where(status='published')
        d = rule.to_dict()
        assert d == {'rule': 'where', 'conditions': {'status': 'published'}}


# ===================================================================
# OrRule
# ===================================================================

class TestOrRule:

    def test_first_true(self):
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ROLE('admin') | ROLE('user')
        assert rule.evaluate(ctx) is True

    def test_second_true(self):
        ctx = _make_ctx(user_id=1, role='user')
        rule = ROLE('admin') | ROLE('user')
        assert rule.evaluate(ctx) is True

    def test_neither_true(self):
        ctx = _make_ctx(user_id=1, role='guest')
        rule = ROLE('admin') | ROLE('user')
        assert rule.evaluate(ctx) is False

    def test_sql_filter(self):
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ANYONE | AUTHENTICATED
        clause, params = rule.sql_filter(ctx)
        assert 'OR' in clause

    def test_sql_filter_none_child(self):
        # If any child returns None, entire filter should be None
        child_with_none = MagicMock(spec=AccessRule)
        child_with_none.sql_filter.return_value = None
        rule = OrRule(ANYONE, child_with_none)
        ctx = _make_ctx(user_id=1)
        result = rule.sql_filter(ctx)
        assert result is None

    def test_to_dict(self):
        rule = OWNER | ROLE('admin')
        d = rule.to_dict()
        assert d['op'] == 'or'
        assert len(d['rules']) == 2


# ===================================================================
# AndRule
# ===================================================================

class TestAndRule:

    def test_both_true(self):
        ctx = _make_ctx(user_id=1, role='admin')
        rule = AUTHENTICATED & ROLE('admin')
        assert rule.evaluate(ctx) is True

    def test_one_false(self):
        ctx = _make_ctx(user_id=1, role='user')
        rule = AUTHENTICATED & ROLE('admin')
        assert rule.evaluate(ctx) is False

    def test_sql_filter(self):
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ANYONE & AUTHENTICATED
        clause, params = rule.sql_filter(ctx)
        assert 'AND' in clause

    def test_sql_filter_none_child(self):
        child_with_none = MagicMock(spec=AccessRule)
        child_with_none.sql_filter.return_value = None
        rule = AndRule(ANYONE, child_with_none)
        ctx = _make_ctx(user_id=1)
        result = rule.sql_filter(ctx)
        assert result is None

    def test_to_dict(self):
        rule = AUTHENTICATED & Where(status='published')
        d = rule.to_dict()
        assert d['op'] == 'and'
        assert len(d['rules']) == 2


# ===================================================================
# NotRule
# ===================================================================

class TestNotRule:

    def test_inverts_true(self):
        ctx = _make_ctx(user_id=1)
        rule = ~ANYONE
        assert rule.evaluate(ctx) is False

    def test_inverts_false(self):
        ctx = _make_ctx(user_id=None)
        rule = ~AUTHENTICATED
        assert rule.evaluate(ctx) is True

    def test_double_negation(self):
        ctx = _make_ctx(user_id=1)
        rule = ~~ANYONE
        assert rule.evaluate(ctx) is True

    def test_sql_filter(self):
        ctx = _make_ctx(user_id=1)
        rule = ~ANYONE
        clause, params = rule.sql_filter(ctx)
        assert 'NOT' in clause

    def test_sql_filter_none_child(self):
        child_with_none = MagicMock(spec=AccessRule)
        child_with_none.sql_filter.return_value = None
        rule = NotRule(child_with_none)
        ctx = _make_ctx(user_id=1)
        result = rule.sql_filter(ctx)
        assert result is None

    def test_to_dict(self):
        rule = ~OWNER
        d = rule.to_dict()
        assert d['op'] == 'not'
        assert 'rule' in d


# ===================================================================
# Operator composition
# ===================================================================

class TestComposition:

    def test_or_operator(self):
        rule = OWNER | ROLE('admin')
        assert isinstance(rule, OrRule)

    def test_and_operator(self):
        rule = AUTHENTICATED & Where(status='published')
        assert isinstance(rule, AndRule)

    def test_not_operator(self):
        rule = ~OWNER
        assert isinstance(rule, NotRule)

    def test_complex_composition(self):
        rule = (OWNER | ROLE('admin')) & AUTHENTICATED
        assert isinstance(rule, AndRule)

    def test_repr(self):
        r = repr(ANYONE)
        assert 'Anyone' in r or 'anyone' in r.lower()
