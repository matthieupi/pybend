"""Tests for Matrix — root actor and message router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from n3tx.core.actors.actor import Actor
from n3tx.core.actors.matrix import Matrix
from n3tx.core.actors.tx import TX
from .conftest import mock_method, make_tx

pytestmark = pytest.mark.unit


class TestMatrixInit:
    """Matrix construction and auto-registration."""

    def test_default_addr(self):
        m = Matrix()
        assert m.addr == 'matrix'

    def test_custom_addr(self):
        m = Matrix(addr='custom')
        assert m.addr == 'custom'

    def test_auto_registers_as_root(self):
        m = Matrix()
        assert Actor.root() is m

    def test_second_matrix_does_not_replace_root(self):
        m1 = Matrix()
        m2 = Matrix(addr='secondary')
        assert Actor.root() is m1

    def test_explicit_root_override(self):
        m1 = Matrix()
        m2 = Matrix(addr='m2')
        Actor.root(m2)
        assert Actor.root() is m2


class TestMatrixHas:
    """Matrix.has() — check child existence."""

    def test_true_for_registered_child(self):
        m = Matrix()
        m.register(Actor(addr='worker'))
        assert m.has('worker') is True

    def test_true_for_nested_addr(self):
        m = Matrix()
        m.register(Actor(addr='worker'))
        assert m.has('worker/sub') is True

    def test_false_for_unknown(self):
        m = Matrix()
        assert m.has('nonexistent') is False


class TestMatrixInbox:
    """Matrix.inbox() — message routing."""

    @pytest.mark.asyncio
    async def test_routes_to_local_child(self):
        m = Matrix()
        child = Actor(addr='worker')
        m.register(child)

        received = []
        async def cap(tx):
            received.append(tx)

        tx = make_tx(target='worker')
        with mock_method(child, 'inbox', cap):
            await m.inbox(tx)
        assert len(received) == 1
        assert received[0] is tx

    @pytest.mark.asyncio
    async def test_self_send_blocked(self):
        m = Matrix()
        tx = make_tx(target='matrix')
        # Should not raise, just log and return
        await m.inbox(tx)

    @pytest.mark.asyncio
    async def test_self_send_logs_error(self):
        m = Matrix()
        tx = make_tx(target='matrix')
        with patch('n3tx.core.actors.matrix.logger') as mock_logger:
            await m.inbox(tx)
            mock_logger.error.assert_called_once()
            assert 'Cannot route to self' in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_delegates_to_adapter(self):
        m = Matrix()
        adapter = MagicMock()
        adapter.can_handle = MagicMock(return_value=True)
        adapter.send = AsyncMock()
        m.register_adapter(adapter)

        tx = make_tx(target='remote')
        await m.inbox(tx)
        adapter.send.assert_awaited_once_with(tx)

    @pytest.mark.asyncio
    async def test_adapter_skip_when_cant_handle(self):
        m = Matrix()
        adapter1 = MagicMock()
        adapter1.can_handle = MagicMock(return_value=False)
        adapter1.send = AsyncMock()
        adapter2 = MagicMock()
        adapter2.can_handle = MagicMock(return_value=True)
        adapter2.send = AsyncMock()
        m.register_adapter(adapter1)
        m.register_adapter(adapter2)

        tx = make_tx(target='remote')
        await m.inbox(tx)
        adapter1.send.assert_not_awaited()
        adapter2.send.assert_awaited_once_with(tx)

    @pytest.mark.asyncio
    async def test_no_route_logs_warning(self):
        m = Matrix()
        tx = make_tx(target='nowhere')
        with patch('n3tx.core.actors.matrix.logger') as mock_logger:
            await m.inbox(tx)
            mock_logger.warning.assert_called_once()
            assert 'No route' in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_route_with_adapters_logs_warning(self):
        """All adapters refuse → warning logged."""
        m = Matrix()
        adapter = MagicMock()
        adapter.can_handle = MagicMock(return_value=False)
        m.register_adapter(adapter)

        tx = make_tx(target='nowhere')
        with patch('n3tx.core.actors.matrix.logger') as mock_logger:
            await m.inbox(tx)
            mock_logger.warning.assert_called_once()


class TestMatrixSend:
    """Matrix.send() routes internally via inbox()."""

    @pytest.mark.asyncio
    async def test_send_delegates_to_inbox(self):
        m = Matrix()
        received = []
        async def cap(tx):
            received.append(tx)

        tx = make_tx(target='somewhere')
        with mock_method(m, 'inbox', cap):
            await m.send(tx)
        assert len(received) == 1


class TestMatrixAdapter:
    """Adapter registration."""

    def test_register_adapter(self):
        m = Matrix()
        adapter = MagicMock()
        m.register_adapter(adapter)
        assert adapter in m._adapters

    def test_multiple_adapters(self):
        m = Matrix()
        a1, a2 = MagicMock(), MagicMock()
        m.register_adapter(a1)
        m.register_adapter(a2)
        assert len(m._adapters) == 2


class TestModuleLevelMatrix:
    """Module-level default matrix instance."""

    def test_exists(self):
        from n3tx.core.actors.matrix import matrix as default_matrix
        assert default_matrix is not None
        assert isinstance(default_matrix, Matrix)

    def test_addr_is_matrix(self):
        from n3tx.core.actors.matrix import matrix as default_matrix
        assert default_matrix.addr == 'matrix'
