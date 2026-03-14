"""
Tests for ActorModel.handler() — the dispatch logic that tries handler_crud
first, then falls back to generic Actor dispatch.

ActorModel.handler() override flow:
    1. Call handler_crud(tx) — returns result or _NOT_HANDLED sentinel
    2. If CRUD handled it: wrap result (TX pass-through, dict → reply, BaseModel → model_dump(), scalar → pass-through, None → empty reply)
    3. If _NOT_HANDLED: fall back to generic Actor dispatch (getattr → call → wrap result)
    4. Errors in either path are caught and sent as tx.error()
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import ClassVar

from pydantic import Field

from n3tx.core.models.actor_model import ActorModel
from n3tx.core.actors.tx import TX
from n3tx.core.actors.actor import Actor, actormethod
from n3tx.core.actors.matrix import Matrix

pytestmark = pytest.mark.unit


# ===================================================================
# Test model — non-CRUD methods for generic fallback testing
# ===================================================================

class _HandlerModel(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = 'handler_test'
    name: str = Field(default='')

    @classmethod
    def CUSTOM_OP(cls, data, tx):
        return {'custom': True, 'received': data}

    @classmethod
    def FAILING_OP(cls, data, tx):
        raise ValueError("intentional test error")

    @classmethod
    def RETURNS_TX(cls, data, tx):
        return tx.reply(data={'direct': True})

    @classmethod
    def RETURNS_NONE(cls, data, tx):
        return None

    @classmethod
    def RETURNS_STRING(cls, data, tx):
        return "hello"


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def reset_actor_state():
    """Save and restore Actor/Matrix class-level state between tests."""
    saved_matrix = Actor.__matrix__
    saved_actor_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_handler_children = _HandlerModel.__children__.copy()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_actor_children
    Matrix.__children__ = saved_matrix_children
    _HandlerModel.__children__ = saved_handler_children


@pytest.fixture
def capture_send():
    """Replace send with a capturing mock, restore after test.

    Since handler() calls send() which routes through the actor tree,
    capture outgoing TXs by temporarily replacing send with a mock.
    """
    sent = []

    @actormethod
    async def mock_send(target, tx):
        sent.append(tx)

    original = _HandlerModel.__dict__.get('send')
    type.__setattr__(_HandlerModel, 'send', mock_send)
    yield sent
    if original:
        type.__setattr__(_HandlerModel, 'send', original)
    else:
        type.__delattr__(_HandlerModel, 'send')


# ===================================================================
# TestHandlerCrudDispatch
# ===================================================================

class TestHandlerCrudDispatch:
    """handler() routes CRUD operations through handler_crud first."""

    @pytest.mark.asyncio
    async def test_schema_routed_to_handler_crud(self, capture_send):
        """TX(name='schema') dispatches to handler_crud which calls cls.schema().

        The reply should contain a schema dict with at least 'properties' key.
        """
        tx = TX(name='schema', source='client', target='handler_test')
        await _HandlerModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert reply.name == 'schema_RESPONSE'
        assert isinstance(reply.data, dict)
        # Schema should contain properties (from ProtoModel.schema())
        assert 'properties' in reply.data

    @pytest.mark.asyncio
    async def test_get_without_id_returns_error(self, capture_send):
        """TX(name='get') with no id in data triggers an error from handler_crud."""
        tx = TX(name='get', source='client', target='handler_test', data={})
        await _HandlerModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        # handler_crud returns tx.error(...) which is a TX — sent directly
        assert reply.is_error
        assert reply.name == 'ERROR'
        assert 'id' in reply.data.get('message', '').lower()


# ===================================================================
# TestHandlerGenericFallback
# ===================================================================

class TestHandlerGenericFallback:
    """Non-CRUD messages fall through to generic Actor dispatch (getattr)."""

    @pytest.mark.asyncio
    async def test_custom_op_dispatches_to_classmethod(self, capture_send):
        """TX(name='CUSTOM_OP') dispatches to CUSTOM_OP classmethod.

        The dict return is wrapped in tx.reply(data=...).
        """
        input_data = {'key': 'value'}
        tx = TX(name='CUSTOM_OP', source='client', target='handler_test', data=input_data)
        await _HandlerModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert reply.name == 'CUSTOM_OP_RESPONSE'
        assert reply.data['custom'] is True
        assert reply.data['received'] == input_data

    @pytest.mark.asyncio
    async def test_returns_tx_sent_directly(self, capture_send):
        """TX(name='RETURNS_TX') — method returns a TX, which is sent as-is."""
        tx = TX(name='RETURNS_TX', source='client', target='handler_test', data={})
        await _HandlerModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        # The method returns tx.reply(data={'direct': True})
        assert reply.name == 'RETURNS_TX_RESPONSE'
        assert reply.data == {'direct': True}
        # Verify it's the TX returned by the method, not re-wrapped
        assert isinstance(reply, TX)

    @pytest.mark.asyncio
    async def test_returns_none_sends_empty_reply(self, capture_send):
        """TX(name='RETURNS_NONE') — None return wraps into empty reply."""
        tx = TX(name='RETURNS_NONE', source='client', target='handler_test', data={})
        await _HandlerModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert reply.name == 'RETURNS_NONE_RESPONSE'
        assert reply.data == {}

    @pytest.mark.asyncio
    async def test_returns_string_passes_through(self, capture_send):
        """TX(name='RETURNS_STRING') — string return passed through without wrapping."""
        tx = TX(name='RETURNS_STRING', source='client', target='handler_test', data={})
        await _HandlerModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert reply.name == 'RETURNS_STRING_RESPONSE'
        assert reply.data == 'hello'


# ===================================================================
# TestHandlerErrors
# ===================================================================

class TestHandlerErrors:
    """Error handling in both CRUD and generic dispatch paths."""

    @pytest.mark.asyncio
    async def test_failing_op_sends_error_tx(self, capture_send):
        """TX(name='FAILING_OP') — exception caught, error TX sent.

        The error TX should have is_error=True and contain the error message.
        """
        tx = TX(name='FAILING_OP', source='client', target='handler_test', data={})
        await _HandlerModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert reply.is_error
        assert reply.name == 'ERROR'
        assert 'intentional test error' in reply.data['message']

    @pytest.mark.asyncio
    async def test_nonexistent_method_sends_unhandled_error(self, capture_send):
        """TX(name='NONEXISTENT') — no method found, sends 'Unhandled message' error."""
        tx = TX(name='NONEXISTENT', source='client', target='handler_test', data={})
        await _HandlerModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert reply.is_error
        assert reply.name == 'ERROR'
        assert 'Unhandled message: NONEXISTENT' in reply.data['message']
