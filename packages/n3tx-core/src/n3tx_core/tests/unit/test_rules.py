"""Tests for authorize/rules.py — Access control rules."""

from unittest.mock import MagicMock

import pytest

from n3tx_core.authorize.rules import (
    AccessRule, ANYONE, AUTHENTICATED, OWNER, ROLE, Where,
    OrRule, AndRule, NotRule,
    _Anyone, _Authenticated, _Owner, _Role,
)
from n3tx_core.authorize.context import AccessContext
from n3tx_core.models.proto_model import ProtoModel

pytestmark = pytest.mark.unit


class RuleModel(ProtoModel):
    """Declare real fields required by policy SQL validation."""

    status: str = ''
    price: int = 0


def _make_ctx(
    user_id=None, role='user', email='test@test.com',
    model_class=None, resource=None, action='read',
):
    """Build synthetic identity and resource context for rule evaluation."""
    # 0. Preserve anonymous identity and use declared model fields for SQL.
    user = {}
    if user_id is not None:
        user = {'user_id': user_id, 'role': role, 'email': email}
    if model_class is None:
        model_class = RuleModel
    return AccessContext(user=user, action=action, model_class=model_class,
                         resource=resource)


# ===================================================================
# ANYONE
# ===================================================================

class TestAnyone:
    """Protect unconditional public access."""

    def test_evaluate_always_true(self):
        """Allow anonymous callers."""
        # 0. Evaluate public access.
        ctx = _make_ctx(user_id=None)
        assert ANYONE.evaluate(ctx) is True

    def test_evaluate_authenticated(self):
        """Allow authenticated callers."""
        # 0. Evaluate public access.
        ctx = _make_ctx(user_id=1)
        assert ANYONE.evaluate(ctx) is True

    def test_sql_filter(self):
        """Preserve unrestricted public SQL."""
        # 0. Compile and inspect the predicate.
        ctx = _make_ctx()
        result = ANYONE.sql_filter(ctx)
        assert result == ('1=1', [])

    def test_to_dict(self):
        """Serialize public access metadata."""
        # 0. Inspect the descriptor.
        assert ANYONE.to_dict() == {'rule': 'anyone'}

    def test_is_singleton(self):
        """Retain the exported singleton type."""
        # 0. Inspect the public rule.
        assert isinstance(ANYONE, _Anyone)


# ===================================================================
# AUTHENTICATED
# ===================================================================

class TestAuthenticated:
    """Protect authentication evaluation and existing SQL behavior."""

    def test_authenticated_user(self):
        """Allow a known caller."""
        # 0. Evaluate a synthetic identity.
        ctx = _make_ctx(user_id=1)
        assert AUTHENTICATED.evaluate(ctx) is True

    def test_anonymous_user(self):
        """Deny an anonymous caller."""
        # 0. Evaluate absent identity.
        ctx = _make_ctx(user_id=None)
        assert AUTHENTICATED.evaluate(ctx) is False

    def test_sql_filter(self):
        """Preserve existing unrestricted authentication SQL."""
        # 0. Compile and inspect the predicate.
        ctx = _make_ctx(user_id=1)
        result = AUTHENTICATED.sql_filter(ctx)
        assert result == ('1=1', [])

    def test_to_dict(self):
        """Serialize authentication metadata."""
        # 0. Inspect the descriptor.
        assert AUTHENTICATED.to_dict() == {'rule': 'authenticated'}


# ===================================================================
# OWNER
# ===================================================================

class TestOwner:
    """Protect owner resolution and ownership SQL."""

    def test_owner_matches(self):
        """Allow matching owner identity."""
        # 0. Evaluate a synthetic owned resource.
        resource = MagicMock()
        resource.user_owner = 5
        ctx = _make_ctx(user_id=5, resource=resource)
        assert OWNER.evaluate(ctx) is True

    def test_owner_mismatch(self):
        """Deny a different owner identity."""
        # 0. Evaluate a synthetic resource and caller.
        resource = MagicMock()
        resource.user_owner = 5
        ctx = _make_ctx(user_id=99, resource=resource)
        assert OWNER.evaluate(ctx) is False

    def test_no_resource_create(self):
        """Retain authenticated resource-free evaluation."""
        # 0. Evaluate a create-style context.
        ctx = _make_ctx(user_id=1, resource=None)
        assert OWNER.evaluate(ctx) is True

    def test_not_authenticated(self):
        """Deny anonymous ownership evaluation."""
        # 0. Evaluate a resource without identity.
        resource = MagicMock()
        resource.user_owner = 5
        ctx = _make_ctx(user_id=None, resource=resource)
        assert OWNER.evaluate(ctx) is False

    def test_owner_href_extraction(self):
        """Resolve ownership from a hydrated URL."""
        # 0. Evaluate the URL representation.
        resource = MagicMock()
        resource.user_owner = 'http://localhost:5000/users/5'
        ctx = _make_ctx(user_id=5, resource=resource)
        assert OWNER.evaluate(ctx) is True

    def test_owner_with_model_id(self):
        """Resolve ownership from a related object's ID."""
        # 0. Evaluate a synthetic related owner.
        owner_obj = MagicMock()
        owner_obj.id = 5
        resource = MagicMock()
        resource.user_owner = owner_obj
        ctx = _make_ctx(user_id=5, resource=resource)
        assert OWNER.evaluate(ctx) is True

    def test_custom_owner_field(self):
        """Honor an explicit owner field."""
        # 0. Evaluate matching custom ownership.
        owner = _Owner(owner_field='author_id')
        resource = MagicMock()
        resource.author_id = 5
        ctx = _make_ctx(user_id=5, resource=resource)
        assert owner.evaluate(ctx) is True

    def test_custom_owner_field_mismatch(self):
        """Deny mismatched custom ownership."""
        # 0. Evaluate a different caller.
        owner = _Owner(owner_field='author_id')
        resource = MagicMock()
        resource.author_id = 5
        ctx = _make_ctx(user_id=99, resource=resource)
        assert owner.evaluate(ctx) is False

    def test_model_owner_field_override(self):
        """Honor the model's owner-field declaration."""
        # 0. Evaluate a synthetic custom model.
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
        """Bind the authenticated owner ID."""
        # 0. Compile and inspect owner SQL.
        ctx = _make_ctx(user_id=5)
        clause, params = OWNER.sql_filter(ctx)
        assert 'user_owner' in clause
        assert params == [5]

    def test_sql_filter_unauthenticated(self):
        """Restrict anonymous owner lists to no rows."""
        # 0. Compile anonymous owner SQL.
        ctx = _make_ctx(user_id=None)
        clause, params = OWNER.sql_filter(ctx)
        assert clause == '1=0'

    def test_to_dict(self):
        """Serialize default ownership metadata."""
        # 0. Inspect the descriptor.
        assert OWNER.to_dict() == {'rule': 'owner'}

    def test_to_dict_custom_field(self):
        """Serialize the configured owner field."""
        # 0. Inspect custom ownership metadata.
        owner = _Owner(owner_field='creator')
        d = owner.to_dict()
        assert d == {'rule': 'owner', 'field': 'creator'}


# ===================================================================
# ROLE
# ===================================================================

class TestRole:
    """Protect role membership and role-based SQL."""

    def test_matching_role(self):
        """Allow a matching role."""
        # 0. Evaluate a synthetic role identity.
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ROLE('admin')
        assert rule.evaluate(ctx) is True

    def test_non_matching_role(self):
        """Deny an unlisted role."""
        # 0. Evaluate an ordinary caller.
        ctx = _make_ctx(user_id=1, role='user')
        rule = ROLE('admin')
        assert rule.evaluate(ctx) is False

    def test_multiple_roles(self):
        """Allow either declared role."""
        # 0. Evaluate the second allowed role.
        ctx = _make_ctx(user_id=1, role='moderator')
        rule = ROLE('admin', 'moderator')
        assert rule.evaluate(ctx) is True

    def test_not_authenticated(self):
        """Deny role checks without identity."""
        # 0. Evaluate an anonymous caller.
        ctx = _make_ctx(user_id=None, role='admin')
        rule = ROLE('admin')
        assert rule.evaluate(ctx) is False

    def test_sql_filter_matching(self):
        """Allow all rows for a matching role."""
        # 0. Compile matching role SQL.
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ROLE('admin')
        clause, params = rule.sql_filter(ctx)
        assert clause == '1=1'

    def test_sql_filter_not_matching(self):
        """Allow no rows for a denied role."""
        # 0. Compile nonmatching role SQL.
        ctx = _make_ctx(user_id=1, role='user')
        rule = ROLE('admin')
        clause, params = rule.sql_filter(ctx)
        assert clause == '1=0'

    def test_to_dict(self):
        """Serialize the allowed role."""
        # 0. Inspect the descriptor.
        rule = ROLE('admin')
        assert rule.to_dict() == {'rule': 'role', 'roles': ['admin']}

    def test_to_dict_multiple(self):
        """Serialize every allowed role."""
        # 0. Inspect multi-role metadata.
        rule = ROLE('admin', 'moderator')
        d = rule.to_dict()
        assert d['rule'] == 'role'
        assert sorted(d['roles']) == ['admin', 'moderator']


# ===================================================================
# Where
# ===================================================================

class TestWhere:
    """Protect resource predicates and shared SQL compilation."""

    def test_equal(self):
        """Allow an equal attribute."""
        # 0. Evaluate an exact resource match.
        resource = MagicMock()
        resource.status = 'published'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status='published')
        assert rule.evaluate(ctx) is True

    def test_equal_mismatch(self):
        """Deny a different attribute."""
        # 0. Evaluate a mismatched status.
        resource = MagicMock()
        resource.status = 'draft'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status='published')
        assert rule.evaluate(ctx) is False

    def test_lt(self):
        """Allow a strictly lower price."""
        # 0. Evaluate a numeric predicate.
        resource = MagicMock()
        resource.price = 50
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(price__lt=100)
        assert rule.evaluate(ctx) is True

    def test_gt(self):
        """Allow a strictly higher price."""
        # 0. Evaluate a numeric predicate.
        resource = MagicMock()
        resource.price = 200
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(price__gt=100)
        assert rule.evaluate(ctx) is True

    def test_lte(self):
        """Include the lower comparison boundary."""
        # 0. Evaluate equality at the price boundary.
        resource = MagicMock()
        resource.price = 100
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(price__lte=100)
        assert rule.evaluate(ctx) is True

    def test_gte(self):
        """Include the upper comparison boundary."""
        # 0. Evaluate equality at the price boundary.
        resource = MagicMock()
        resource.price = 100
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(price__gte=100)
        assert rule.evaluate(ctx) is True

    def test_ne(self):
        """Allow a value different from the excluded status."""
        # 0. Evaluate resource inequality.
        resource = MagicMock()
        resource.status = 'draft'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status__ne='published')
        assert rule.evaluate(ctx) is True

    def test_in(self):
        """Allow membership in the configured statuses."""
        # 0. Evaluate resource membership.
        resource = MagicMock()
        resource.status = 'published'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status__in=['published', 'draft'])
        assert rule.evaluate(ctx) is True

    def test_in_not_found(self):
        """Deny values outside the configured statuses."""
        # 0. Evaluate nonmembership.
        resource = MagicMock()
        resource.status = 'archived'
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status__in=['published', 'draft'])
        assert rule.evaluate(ctx) is False

    def test_no_resource(self):
        """Retain resource-free condition evaluation."""
        # 0. Evaluate a class-level context.
        ctx = _make_ctx(user_id=1, resource=None)
        rule = Where(status='published')
        assert rule.evaluate(ctx) is True

    def test_multiple_conditions(self):
        """Require every condition to match."""
        # 0. Evaluate matching status and price.
        resource = MagicMock()
        resource.status = 'published'
        resource.price = 50
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status='published', price__lt=100)
        assert rule.evaluate(ctx) is True

    def test_multiple_conditions_one_fails(self):
        """Deny when one condition fails."""
        # 0. Evaluate a mismatched status with matching price.
        resource = MagicMock()
        resource.status = 'draft'
        resource.price = 50
        ctx = _make_ctx(user_id=1, resource=resource)
        rule = Where(status='published', price__lt=100)
        assert rule.evaluate(ctx) is False

    def test_sql_filter_equal(self):
        """Quote declared fields and bind equality values."""
        # 0. Compile equality against declared fields.
        ctx = _make_ctx(user_id=1)
        rule = Where(status='published')
        clause, params = rule.sql_filter(ctx)
        assert '"status" = ?' in clause
        assert 'published' in params

    def test_sql_filter_lt(self):
        """Quote declared fields and bind numeric values."""
        # 0. Compile a numeric comparison.
        ctx = _make_ctx(user_id=1)
        rule = Where(price__lt=100)
        clause, params = rule.sql_filter(ctx)
        assert '"price" < ?' in clause
        assert 100 in params

    def test_sql_filter_in(self):
        """Bind membership values in order."""
        # 0. Compile a membership predicate.
        ctx = _make_ctx(user_id=1)
        rule = Where(status__in=['a', 'b'])
        clause, params = rule.sql_filter(ctx)
        assert 'IN' in clause
        assert params == ['a', 'b']

    def test_to_dict(self):
        """Serialize the configured conditions."""
        # 0. Inspect predicate metadata.
        rule = Where(status='published')
        d = rule.to_dict()
        assert d == {'rule': 'where', 'conditions': {'status': 'published'}}


# ===================================================================
# OrRule
# ===================================================================

class TestOrRule:
    """Protect disjunction evaluation and serialization."""

    def test_first_true(self):
        """Allow the first matching alternative."""
        # 0. Evaluate an admin identity.
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ROLE('admin') | ROLE('user')
        assert rule.evaluate(ctx) is True

    def test_second_true(self):
        """Allow the second matching alternative."""
        # 0. Evaluate an ordinary identity.
        ctx = _make_ctx(user_id=1, role='user')
        rule = ROLE('admin') | ROLE('user')
        assert rule.evaluate(ctx) is True

    def test_neither_true(self):
        """Deny when neither alternative matches."""
        # 0. Evaluate an unlisted role.
        ctx = _make_ctx(user_id=1, role='guest')
        rule = ROLE('admin') | ROLE('user')
        assert rule.evaluate(ctx) is False

    def test_sql_filter(self):
        """Compose child predicates with OR."""
        # 0. Compile SQL-capable children.
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ANYONE | AUTHENTICATED
        clause, params = rule.sql_filter(ctx)
        assert 'OR' in clause

    def test_sql_filter_none_child(self):
        """Preserve the non-filterable child fallback."""
        # 0. Compose a child without SQL support.
        # If any child returns None, entire filter should be None
        child_with_none = MagicMock(spec=AccessRule)
        child_with_none.sql_filter.return_value = None
        rule = OrRule(ANYONE, child_with_none)
        ctx = _make_ctx(user_id=1)
        result = rule.sql_filter(ctx)
        assert result is None

    def test_to_dict(self):
        """Serialize both alternative rules."""
        # 0. Inspect composite metadata.
        rule = OWNER | ROLE('admin')
        d = rule.to_dict()
        assert d['op'] == 'or'
        assert len(d['rules']) == 2


# ===================================================================
# AndRule
# ===================================================================

class TestAndRule:
    """Protect conjunction evaluation and serialization."""

    def test_both_true(self):
        """Allow when both conditions succeed."""
        # 0. Evaluate an authenticated admin.
        ctx = _make_ctx(user_id=1, role='admin')
        rule = AUTHENTICATED & ROLE('admin')
        assert rule.evaluate(ctx) is True

    def test_one_false(self):
        """Deny when a condition fails."""
        # 0. Evaluate an authenticated non-admin.
        ctx = _make_ctx(user_id=1, role='user')
        rule = AUTHENTICATED & ROLE('admin')
        assert rule.evaluate(ctx) is False

    def test_sql_filter(self):
        """Compose child predicates with AND."""
        # 0. Compile SQL-capable children.
        ctx = _make_ctx(user_id=1, role='admin')
        rule = ANYONE & AUTHENTICATED
        clause, params = rule.sql_filter(ctx)
        assert 'AND' in clause

    def test_sql_filter_none_child(self):
        """Preserve the non-filterable child fallback."""
        # 0. Compose a child without SQL support.
        child_with_none = MagicMock(spec=AccessRule)
        child_with_none.sql_filter.return_value = None
        rule = AndRule(ANYONE, child_with_none)
        ctx = _make_ctx(user_id=1)
        result = rule.sql_filter(ctx)
        assert result is None

    def test_to_dict(self):
        """Serialize both required rules."""
        # 0. Inspect composite metadata.
        rule = AUTHENTICATED & Where(status='published')
        d = rule.to_dict()
        assert d['op'] == 'and'
        assert len(d['rules']) == 2


# ===================================================================
# NotRule
# ===================================================================

class TestNotRule:
    """Protect negation evaluation and serialization."""

    def test_inverts_true(self):
        """Negate allowance to denial."""
        # 0. Evaluate negated public access.
        ctx = _make_ctx(user_id=1)
        rule = ~ANYONE
        assert rule.evaluate(ctx) is False

    def test_inverts_false(self):
        """Negate denial to allowance."""
        # 0. Evaluate negated anonymous authentication.
        ctx = _make_ctx(user_id=None)
        rule = ~AUTHENTICATED
        assert rule.evaluate(ctx) is True

    def test_double_negation(self):
        """Retain the original result under double negation."""
        # 0. Evaluate twice-negated public access.
        ctx = _make_ctx(user_id=1)
        rule = ~~ANYONE
        assert rule.evaluate(ctx) is True

    def test_sql_filter(self):
        """Negate a SQL predicate."""
        # 0. Compile a SQL-capable child.
        ctx = _make_ctx(user_id=1)
        rule = ~ANYONE
        clause, params = rule.sql_filter(ctx)
        assert 'NOT' in clause

    def test_sql_filter_none_child(self):
        """Preserve absent SQL under negation."""
        # 0. Negate a child without SQL support.
        child_with_none = MagicMock(spec=AccessRule)
        child_with_none.sql_filter.return_value = None
        rule = NotRule(child_with_none)
        ctx = _make_ctx(user_id=1)
        result = rule.sql_filter(ctx)
        assert result is None

    def test_to_dict(self):
        """Serialize the negated child."""
        # 0. Inspect negation metadata.
        rule = ~OWNER
        d = rule.to_dict()
        assert d['op'] == 'not'
        assert 'rule' in d


# ===================================================================
# Operator composition
# ===================================================================

class TestComposition:
    """Protect native operator construction and diagnostic output."""

    def test_or_operator(self):
        """Construct a native disjunction."""
        # 0. Inspect the composed type.
        rule = OWNER | ROLE('admin')
        assert isinstance(rule, OrRule)

    def test_and_operator(self):
        """Construct a native conjunction."""
        # 0. Inspect the composed type.
        rule = AUTHENTICATED & Where(status='published')
        assert isinstance(rule, AndRule)

    def test_not_operator(self):
        """Construct a native negation."""
        # 0. Inspect the composed type.
        rule = ~OWNER
        assert isinstance(rule, NotRule)

    def test_complex_composition(self):
        """Preserve nested native composition."""
        # 0. Build an OR nested within an AND.
        rule = (OWNER | ROLE('admin')) & AUTHENTICATED
        assert isinstance(rule, AndRule)

    def test_repr(self):
        """Keep the public rule representation recognizable."""
        # 0. Inspect the diagnostic representation.
        r = repr(ANYONE)
        assert 'Anyone' in r or 'anyone' in r.lower()


# Changelog
# - 2026-11-02: Use declared policy fields and quoted compiler identifiers.
