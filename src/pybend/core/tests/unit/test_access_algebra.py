"""Tests for AccessRule boolean algebra properties.

Verifies that the ABAC rule composition operators (|, &, ~) satisfy
the laws of boolean algebra. This is critical before extending the
algebra with agent and federation rules (Wave 1c).

Properties tested:
    - Commutativity:   A | B == B | A,  A & B == B & A
    - Associativity:   (A | B) | C == A | (B | C)
    - Distributivity:  A & (B | C) == (A & B) | (A & C)
    - De Morgan:       ~(A | B) == ~A & ~B,  ~(A & B) == ~A | ~B
    - Identity:        A | NEVER == A,  A & ANYONE == A
    - Annihilation:    A & NEVER == NEVER,  A | ANYONE == ANYONE
    - Complement:      ~ANYONE == NEVER behavior,  ~NEVER == ANYONE behavior
    - Involution:      ~~A == A
    - Idempotence:     A | A == A,  A & A == A
"""

import pytest
from unittest.mock import MagicMock

from pybend.core.authorize.rules import (
    ANYONE, NEVER, AUTHENTICATED, OWNER, ROLE, Where,
    Federated, FEDERATED, Local, LOCAL, Follower, FOLLOWER,
    OrRule, AndRule, NotRule,
)
from pybend.core.authorize.context import AccessContext

pytestmark = pytest.mark.unit


# ── Helpers ──────────────────────────────────────────────────────


def _ctx(authenticated=True, user_id=1, role='user', owner_id=1,
         federated=False, following=None):
    """Build an AccessContext for testing."""
    user = {}
    if authenticated:
        user = {'user_id': user_id, 'role': role}
    if federated:
        user['federated'] = True
    if following is not None:
        user['following'] = following

    resource = None
    if owner_id is not None:
        resource = MagicMock()
        resource.user_owner = owner_id

    model_cls = MagicMock()
    model_cls.__owner_field__ = 'user_owner'

    return AccessContext(
        user=user,
        action='read',
        model_class=model_cls,
        resource=resource,
    )


def _eval_eq(rule_a, rule_b, contexts):
    """Assert two rules evaluate identically across all given contexts."""
    for ctx in contexts:
        assert rule_a.evaluate(ctx) == rule_b.evaluate(ctx), (
            f"Mismatch on {ctx}: "
            f"{rule_a} -> {rule_a.evaluate(ctx)}, "
            f"{rule_b} -> {rule_b.evaluate(ctx)}"
        )


# Standard test contexts covering key dimensions
CONTEXTS = [
    _ctx(authenticated=False),                      # anonymous
    _ctx(authenticated=True, user_id=1, owner_id=1),  # owner
    _ctx(authenticated=True, user_id=2, owner_id=1),  # non-owner
    _ctx(authenticated=True, role='admin'),           # admin
    _ctx(authenticated=True, federated=True),         # federated
    _ctx(authenticated=True, federated=False),        # local
]

# Leaf rules to test combinations with
LEAF_RULES = [ANYONE, NEVER, AUTHENTICATED, OWNER, ROLE('admin'), FEDERATED, LOCAL]


# ── NEVER element tests ─────────────────────────────────────────


class TestNever:

    def test_never_always_denies(self):
        for ctx in CONTEXTS:
            assert NEVER.evaluate(ctx) is False

    def test_never_sql_filter(self):
        ctx = _ctx()
        clause, params = NEVER.sql_filter(ctx)
        assert clause == "1=0"
        assert params == []

    def test_never_to_dict(self):
        assert NEVER.to_dict() == {"rule": "never"}


# ── Identity laws: A | NEVER == A,  A & ANYONE == A ─────────────


class TestIdentity:

    @pytest.mark.parametrize("rule", LEAF_RULES, ids=lambda r: type(r).__name__)
    def test_or_identity_never(self, rule):
        """A | NEVER == A"""
        _eval_eq(rule | NEVER, rule, CONTEXTS)

    @pytest.mark.parametrize("rule", LEAF_RULES, ids=lambda r: type(r).__name__)
    def test_and_identity_anyone(self, rule):
        """A & ANYONE == A"""
        _eval_eq(rule & ANYONE, rule, CONTEXTS)


# ── Annihilation: A & NEVER == NEVER,  A | ANYONE == ANYONE ─────


class TestAnnihilation:

    @pytest.mark.parametrize("rule", LEAF_RULES, ids=lambda r: type(r).__name__)
    def test_and_annihilation_never(self, rule):
        """A & NEVER == NEVER"""
        _eval_eq(rule & NEVER, NEVER, CONTEXTS)

    @pytest.mark.parametrize("rule", LEAF_RULES, ids=lambda r: type(r).__name__)
    def test_or_annihilation_anyone(self, rule):
        """A | ANYONE == ANYONE"""
        _eval_eq(rule | ANYONE, ANYONE, CONTEXTS)


# ── Commutativity: A | B == B | A,  A & B == B & A ──────────────


class TestCommutativity:

    @pytest.mark.parametrize("a,b", [
        (AUTHENTICATED, OWNER),
        (ROLE('admin'), FEDERATED),
        (LOCAL, AUTHENTICATED),
        (ANYONE, NEVER),
    ])
    def test_or_commutative(self, a, b):
        _eval_eq(a | b, b | a, CONTEXTS)

    @pytest.mark.parametrize("a,b", [
        (AUTHENTICATED, OWNER),
        (ROLE('admin'), FEDERATED),
        (LOCAL, AUTHENTICATED),
        (ANYONE, NEVER),
    ])
    def test_and_commutative(self, a, b):
        _eval_eq(a & b, b & a, CONTEXTS)


# ── Associativity: (A | B) | C == A | (B | C) ──────────────────


class TestAssociativity:

    @pytest.mark.parametrize("a,b,c", [
        (AUTHENTICATED, OWNER, ROLE('admin')),
        (FEDERATED, LOCAL, ANYONE),
        (NEVER, AUTHENTICATED, OWNER),
    ])
    def test_or_associative(self, a, b, c):
        _eval_eq((a | b) | c, a | (b | c), CONTEXTS)

    @pytest.mark.parametrize("a,b,c", [
        (AUTHENTICATED, OWNER, ROLE('admin')),
        (FEDERATED, LOCAL, ANYONE),
        (NEVER, AUTHENTICATED, OWNER),
    ])
    def test_and_associative(self, a, b, c):
        _eval_eq((a & b) & c, a & (b & c), CONTEXTS)


# ── Distributivity: A & (B | C) == (A & B) | (A & C) ───────────


class TestDistributivity:

    @pytest.mark.parametrize("a,b,c", [
        (AUTHENTICATED, OWNER, ROLE('admin')),
        (LOCAL, FEDERATED, ANYONE),
    ])
    def test_and_distributes_over_or(self, a, b, c):
        """A & (B | C) == (A & B) | (A & C)"""
        _eval_eq(a & (b | c), (a & b) | (a & c), CONTEXTS)

    @pytest.mark.parametrize("a,b,c", [
        (AUTHENTICATED, OWNER, ROLE('admin')),
        (LOCAL, FEDERATED, ANYONE),
    ])
    def test_or_distributes_over_and(self, a, b, c):
        """A | (B & C) == (A | B) & (A | C)"""
        _eval_eq(a | (b & c), (a | b) & (a | c), CONTEXTS)


# ── De Morgan's laws ────────────────────────────────────────────


class TestDeMorgan:

    @pytest.mark.parametrize("a,b", [
        (AUTHENTICATED, OWNER),
        (ROLE('admin'), FEDERATED),
        (LOCAL, ANYONE),
        (NEVER, AUTHENTICATED),
    ])
    def test_not_or(self, a, b):
        """~(A | B) == ~A & ~B"""
        _eval_eq(~(a | b), ~a & ~b, CONTEXTS)

    @pytest.mark.parametrize("a,b", [
        (AUTHENTICATED, OWNER),
        (ROLE('admin'), FEDERATED),
        (LOCAL, ANYONE),
        (NEVER, AUTHENTICATED),
    ])
    def test_not_and(self, a, b):
        """~(A & B) == ~A | ~B"""
        _eval_eq(~(a & b), ~a | ~b, CONTEXTS)


# ── Complement: ~ANYONE behaves as NEVER, ~NEVER behaves as ANYONE


class TestComplement:

    def test_not_anyone_is_never(self):
        """~ANYONE always denies (behaves as NEVER)."""
        _eval_eq(~ANYONE, NEVER, CONTEXTS)

    def test_not_never_is_anyone(self):
        """~NEVER always allows (behaves as ANYONE)."""
        _eval_eq(~NEVER, ANYONE, CONTEXTS)


# ── Involution: ~~A == A ────────────────────────────────────────


class TestInvolution:

    @pytest.mark.parametrize("rule", LEAF_RULES, ids=lambda r: type(r).__name__)
    def test_double_negation(self, rule):
        """~~A == A"""
        _eval_eq(~~rule, rule, CONTEXTS)


# ── Idempotence: A | A == A,  A & A == A ────────────────────────


class TestIdempotence:

    @pytest.mark.parametrize("rule", LEAF_RULES, ids=lambda r: type(r).__name__)
    def test_or_idempotent(self, rule):
        """A | A == A"""
        _eval_eq(rule | rule, rule, CONTEXTS)

    @pytest.mark.parametrize("rule", LEAF_RULES, ids=lambda r: type(r).__name__)
    def test_and_idempotent(self, rule):
        """A & A == A"""
        _eval_eq(rule & rule, rule, CONTEXTS)


# ── Absorption: A | (A & B) == A,  A & (A | B) == A ────────────


class TestAbsorption:

    @pytest.mark.parametrize("a,b", [
        (AUTHENTICATED, OWNER),
        (ROLE('admin'), FEDERATED),
    ])
    def test_absorption_or(self, a, b):
        """A | (A & B) == A"""
        _eval_eq(a | (a & b), a, CONTEXTS)

    @pytest.mark.parametrize("a,b", [
        (AUTHENTICATED, OWNER),
        (ROLE('admin'), FEDERATED),
    ])
    def test_absorption_and(self, a, b):
        """A & (A | B) == A"""
        _eval_eq(a & (a | b), a, CONTEXTS)


# ── Federation rules ────────────────────────────────────────────


class TestFederatedRule:

    def test_federated_allows_federated_user(self):
        ctx = _ctx(federated=True)
        assert FEDERATED.evaluate(ctx) is True

    def test_federated_denies_local_user(self):
        ctx = _ctx(federated=False)
        assert FEDERATED.evaluate(ctx) is False

    def test_federated_denies_anonymous(self):
        ctx = _ctx(authenticated=False)
        assert FEDERATED.evaluate(ctx) is False

    def test_federated_to_dict(self):
        assert FEDERATED.to_dict() == {"rule": "federated"}

    def test_federated_sql_filter_allows(self):
        ctx = _ctx(federated=True)
        clause, params = FEDERATED.sql_filter(ctx)
        assert clause == "1=1"

    def test_federated_sql_filter_denies(self):
        ctx = _ctx(federated=False)
        clause, params = FEDERATED.sql_filter(ctx)
        assert clause == "1=0"


class TestLocalRule:

    def test_local_allows_local_user(self):
        ctx = _ctx(federated=False)
        assert LOCAL.evaluate(ctx) is True

    def test_local_denies_federated_user(self):
        ctx = _ctx(federated=True)
        assert LOCAL.evaluate(ctx) is False

    def test_local_allows_anonymous(self):
        ctx = _ctx(authenticated=False)
        assert LOCAL.evaluate(ctx) is True

    def test_local_to_dict(self):
        assert LOCAL.to_dict() == {"rule": "local"}


class TestFollowerRule:

    def test_follower_allows_when_following_owner(self):
        ctx = _ctx(user_id=2, owner_id=1, following=[1])
        assert FOLLOWER.evaluate(ctx) is True

    def test_follower_denies_when_not_following(self):
        ctx = _ctx(user_id=2, owner_id=1, following=[3, 4])
        assert FOLLOWER.evaluate(ctx) is False

    def test_follower_denies_when_no_following_list(self):
        ctx = _ctx(user_id=2, owner_id=1)
        assert FOLLOWER.evaluate(ctx) is False

    def test_follower_denies_anonymous(self):
        ctx = _ctx(authenticated=False, owner_id=1)
        assert FOLLOWER.evaluate(ctx) is False

    def test_follower_denies_no_resource(self):
        ctx = _ctx(user_id=2, owner_id=None, following=[1])
        # No resource → can't determine owner
        assert FOLLOWER.evaluate(ctx) is False

    def test_follower_to_dict(self):
        assert FOLLOWER.to_dict() == {"rule": "follower"}

    def test_follower_with_custom_field(self):
        f = Follower(owner_field='author_id')
        assert f.to_dict() == {"rule": "follower", "field": "author_id"}

    def test_follower_sql_filter_with_following(self):
        ctx = _ctx(following=[1, 3])
        clause, params = FOLLOWER.sql_filter(ctx)
        assert 'IN' in clause
        assert params == [1, 3]

    def test_follower_sql_filter_empty_following(self):
        ctx = _ctx(following=[])
        clause, params = FOLLOWER.sql_filter(ctx)
        assert clause == "1=0"
        assert params == []

    def test_follower_sql_filter_no_following_key(self):
        ctx = _ctx()  # no following kwarg
        clause, params = FOLLOWER.sql_filter(ctx)
        assert clause == "1=1"  # permissive — evaluate() still guards

    def test_follower_sql_filter_unauthenticated(self):
        ctx = _ctx(authenticated=False)
        clause, params = FOLLOWER.sql_filter(ctx)
        assert clause == "1=0"


# ── Composition with new rules ──────────────────────────────────


class TestFederationComposition:

    def test_local_and_authenticated(self):
        """LOCAL & AUTHENTICATED — local authenticated users only."""
        rule = LOCAL & AUTHENTICATED
        assert rule.evaluate(_ctx(federated=False)) is True
        assert rule.evaluate(_ctx(federated=True)) is False
        assert rule.evaluate(_ctx(authenticated=False)) is False

    def test_federated_and_follower(self):
        """FEDERATED & FOLLOWER — federated followers only."""
        rule = FEDERATED & FOLLOWER
        ctx_yes = _ctx(federated=True, user_id=2, owner_id=1, following=[1])
        ctx_no = _ctx(federated=True, user_id=2, owner_id=1, following=[3])
        assert rule.evaluate(ctx_yes) is True
        assert rule.evaluate(ctx_no) is False

    def test_owner_or_federated_follower(self):
        """OWNER | (FEDERATED & FOLLOWER) — typical federation access."""
        rule = OWNER | (FEDERATED & FOLLOWER)
        # Local owner
        assert rule.evaluate(_ctx(user_id=1, owner_id=1)) is True
        # Federated follower
        assert rule.evaluate(_ctx(federated=True, user_id=2, owner_id=1, following=[1])) is True
        # Federated non-follower
        assert rule.evaluate(_ctx(federated=True, user_id=2, owner_id=1, following=[])) is False

    def test_never_with_federation_rules(self):
        """NEVER composes correctly with federation rules."""
        assert (FEDERATED & NEVER).evaluate(_ctx(federated=True)) is False
        assert (LOCAL | NEVER).evaluate(_ctx()) is True

    def test_serialization_roundtrip(self):
        """Composed federation rules serialize correctly."""
        rule = LOCAL & AUTHENTICATED
        d = rule.to_dict()
        assert d['op'] == 'and'
        assert {'rule': 'local'} in d['rules']
        assert {'rule': 'authenticated'} in d['rules']


# ── sql_filter Completeness ────────────────────────────────────────


class TestSqlFilterCompleteness:
    """Verify that no leaf rule returns None from sql_filter, and that
    no composition of real rules produces None."""

    @pytest.mark.parametrize("rule", LEAF_RULES, ids=lambda r: type(r).__name__)
    def test_leaf_sql_filter_not_none_authenticated(self, rule):
        """Every leaf rule returns a valid SQL fragment for authenticated ctx."""
        ctx = _ctx(authenticated=True, following=[1])
        result = rule.sql_filter(ctx)
        assert result is not None, f"{type(rule).__name__}.sql_filter() returned None"
        clause, params = result
        assert isinstance(clause, str)
        assert isinstance(params, list)

    @pytest.mark.parametrize("rule", LEAF_RULES, ids=lambda r: type(r).__name__)
    def test_leaf_sql_filter_not_none_anonymous(self, rule):
        """Every leaf rule returns a valid SQL fragment for anonymous ctx."""
        ctx = _ctx(authenticated=False)
        result = rule.sql_filter(ctx)
        assert result is not None, f"{type(rule).__name__}.sql_filter() returned None"

    @pytest.mark.parametrize("a,b", [
        (OWNER, FOLLOWER),
        (AUTHENTICATED, FOLLOWER),
        (FOLLOWER, ROLE('admin')),
    ])
    def test_or_composition_not_none(self, a, b):
        """OR of real leaf rules never returns None."""
        rule = a | b
        ctx = _ctx(following=[1])
        result = rule.sql_filter(ctx)
        assert result is not None

    @pytest.mark.parametrize("a,b", [
        (OWNER, FOLLOWER),
        (FEDERATED, FOLLOWER),
    ])
    def test_and_composition_not_none(self, a, b):
        """AND of real leaf rules never returns None."""
        rule = a & b
        ctx = _ctx(following=[1])
        result = rule.sql_filter(ctx)
        assert result is not None

    def test_not_follower_not_none(self):
        """NOT(FOLLOWER) returns valid SQL fragment."""
        rule = ~FOLLOWER
        ctx = _ctx(following=[1])
        result = rule.sql_filter(ctx)
        assert result is not None

    def test_owner_or_follower_produces_valid_sql(self):
        """OWNER | FOLLOWER — the motivating composition."""
        rule = OWNER | FOLLOWER
        ctx = _ctx(user_id=1, following=[2, 3])
        clause, params = rule.sql_filter(ctx)
        assert 'OR' in clause
        assert 1 in params  # OWNER's user_id
        assert 2 in params  # FOLLOWER's following IDs
        assert 3 in params
