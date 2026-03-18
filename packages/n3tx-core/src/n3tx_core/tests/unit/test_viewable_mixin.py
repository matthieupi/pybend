"""Tests for the register_mixin() API in proto_model.py.

ViewableMixin itself moved to n3tx-ui. These tests verify the core
registry mechanism that external packages use to inject mixins.
"""

import pytest

from n3tx_core.models.proto_model import register_mixin, _mixin_registry, ProtoModel
from typing import ClassVar

pytestmark = pytest.mark.unit


# ===================================================================
# register_mixin() API
# ===================================================================

class _TestMixinA:
    pass


class _TestMixinB:
    pass


class TestRegisterMixin:

    def teardown_method(self):
        """Remove test-only entries from registry after each test."""
        _mixin_registry[:] = [
            (f, m, a) for f, m, a in _mixin_registry
            if m not in (_TestMixinA, _TestMixinB)
        ]

    def test_register_adds_to_registry(self):
        initial_len = len(_mixin_registry)
        register_mixin('__test_flag_a__', _TestMixinA)
        assert len(_mixin_registry) == initial_len + 1
        assert any(flag == '__test_flag_a__' and mixin is _TestMixinA
                   for flag, mixin, _ in _mixin_registry)

    def test_also_if_stored(self):
        register_mixin('__test_flag_b__', _TestMixinB, also_if=['__alt_flag__'])
        entry = next(
            (e for e in _mixin_registry if e[1] is _TestMixinB), None
        )
        assert entry is not None
        assert '__alt_flag__' in entry[2]

    def test_flag_triggers_injection(self):
        register_mixin('__test_flag_a__', _TestMixinA)

        class Flagged(ProtoModel):
            __tablename__: ClassVar[str] = 'tm_flagged'
            __test_flag_a__ = True

        assert issubclass(Flagged, _TestMixinA)

    def test_also_if_triggers_injection_and_normalizes_flag(self):
        register_mixin('__test_flag_b__', _TestMixinB, also_if=['__alt_trigger__'])

        class AltFlagged(ProtoModel):
            __tablename__: ClassVar[str] = 'tm_alt_flagged'
            __alt_trigger__ = {'some': 'value'}

        assert issubclass(AltFlagged, _TestMixinB)
        assert AltFlagged.__test_flag_b__ is True

    def test_plain_model_not_injected(self):
        register_mixin('__test_flag_a__', _TestMixinA)

        class Plain(ProtoModel):
            __tablename__: ClassVar[str] = 'tm_plain'

        assert not issubclass(Plain, _TestMixinA)

    def test_already_subclass_not_double_injected(self):
        register_mixin('__test_flag_a__', _TestMixinA)

        class AlreadyHasMixin(_TestMixinA, ProtoModel):
            __tablename__: ClassVar[str] = 'tm_already'
            __test_flag_a__ = True

        # Should still be a subclass (just not double-injected)
        assert issubclass(AlreadyHasMixin, _TestMixinA)
        # _TestMixinA should appear once in MRO
        assert AlreadyHasMixin.__mro__.count(_TestMixinA) == 1
