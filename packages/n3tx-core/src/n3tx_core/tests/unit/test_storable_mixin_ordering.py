"""Protect optional ordering delegation and legacy storage compatibility."""

from inspect import Parameter, signature
from typing import ClassVar
from unittest.mock import Mock

import pytest

from n3tx_core.models.proto_model import ProtoModel

pytestmark = pytest.mark.unit


@pytest.fixture
def ordering_model():
    """Build an unregistered model so no database or registry is changed."""
    # 0. Keep declaration and backend attachment local to each test.
    class OrderingModel(ProtoModel):
        """Delegate list requests to an explicitly attached backend."""

        __tablename__: ClassVar[str] = 'ordering_delegate'
        __storable__: ClassVar[bool] = True
        score: int = 0

    return OrderingModel


@pytest.mark.parametrize('ordering', ['order_asc', 'order_desc'])
def test_explicit_ordering_reaches_storage_unchanged(ordering_model, ordering):
    """Forward the requested field alongside every existing list option."""
    # 0. Use sentinel values to detect dropped or replaced arguments.
    backend = Mock()
    ordering_model.set_storage(backend)
    sql_filter = ('score > ?', [10])
    populate = object()
    # 1. Exercise the model's public list entrypoint.
    result = ordering_model.list(
        sql_filter=sql_filter, limit=2, offset=1, populate=populate,
        ids=[1, 3], **{ordering: 'score'},
    )
    # 2. Preserve the response and the explicitly requested sort direction.
    assert result is backend.list.return_value
    kwargs = backend.list.call_args.kwargs
    assert backend.list.call_args.args == (ordering_model,)
    assert kwargs[ordering] == 'score'
    assert kwargs['sql_filter'] is sql_filter
    assert kwargs['populate'] is populate
    assert kwargs['limit'] == 2
    assert kwargs['offset'] == 1
    assert kwargs['ids'] == [1, 3]


@pytest.mark.parametrize(
    'options', [{}, {'order_asc': None, 'order_desc': None}],
)
def test_unordered_call_supports_old_storage_signature(
    ordering_model, options,
):
    """Omit absent sort keywords rather than breaking existing backends."""
    # 0. Model a backend implementing only the historical list signature.
    calls = []

    class LegacyStorage:
        """Reject unexpected keywords by retaining the pre-ordering API."""

        def list(self, model, sql_filter=None, limit=None, offset=None,
                 populate=None, ids=None):
            """Record the historical arguments without new sort keywords."""
            calls.append((model, sql_filter, limit, offset, populate, ids))
            return ['legacy-result']

    ordering_model.set_storage(LegacyStorage())
    # 1. Explicit None and omitted ordering must both remain compatible.
    result = ordering_model.list(**options)
    # 2. Assert delegation instead of merely accepting no exception.
    assert result == ['legacy-result']
    assert calls == [(ordering_model, None, None, None, None, None)]


def test_new_model_ordering_parameters_are_keyword_only(ordering_model):
    """Do not change positional meanings of the existing list arguments."""
    # 0. Inspect the public bound method rather than implementation locals.
    parameters = signature(ordering_model.list).parameters
    # 1. Both new directions are optional keyword-only parameters.
    for name in ('order_asc', 'order_desc'):
        assert parameters[name].kind is Parameter.KEYWORD_ONLY
        assert parameters[name].default is None


# Changelog
# - 2026-11-02: Protect sort forwarding and legacy unordered delegation.
# - 2026-11-10: Restore the original ordering delegation tests.
