"""Tests for ActorModel error/response drop guard.

Bug: ActorModel.handler() overrides Actor.handler() but is missing the
is_error / _RESPONSE drop guard. This allows ERROR TXs to bounce
infinitely between actors, growing addresses each hop.

The fix: log the error, bubble up to Matrix root for correlation handling,
and stop — don't create a new ERROR TX in response to an ERROR.
"""

import asyncio
import sys
import pytest
from typing import ClassVar

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.api.network_adapter import NetworkAdapter
from n3tx_actors.tx import TX
from n3tx_core.utils.registrar import registered_models


@pytest.fixture(autouse=True)
def reset_state():
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_models = dict(registered_models)

    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    registered_models.clear()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children
    registered_models.clear()
    registered_models.update(saved_models)


@pytest.fixture
def fresh_matrix():
    return Matrix()


class TestActorModelErrorDropGuard:
    """ActorModel.handler() must silently drop ERROR and _RESPONSE TXs
    when no explicit handler method exists for them."""

    @pytest.mark.asyncio
    async def test_error_tx_dropped_no_recursion(self, fresh_matrix):
        """An ERROR TX routed between two ActorModels must NOT cause
        infinite recursion. The buggy behavior hits RecursionError."""

        class ActorA(ActorModel):
            __tablename__: ClassVar[str] = 'actor_a'
            __storable__: ClassVar[bool] = False

        class ActorB(ActorModel):
            __tablename__: ClassVar[str] = 'actor_b'
            __storable__: ClassVar[bool] = False

        error_tx = TX(
            name='ERROR',
            source='actor_a',
            target='actor_b',
            data={'message': 'Something failed', 'code': 500},
            meta={'error': True},
        )

        # This will hit RecursionError if the drop guard is missing
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)  # Lower limit to fail fast
        try:
            await fresh_matrix.inbox(error_tx)
        except RecursionError:
            pytest.fail(
                "ERROR TX caused infinite recursion between ActorModels! "
                "ActorModel.handler() is missing the is_error drop guard "
                "from Actor.handler()."
            )
        finally:
            sys.setrecursionlimit(old_limit)

    @pytest.mark.asyncio
    async def test_response_tx_dropped_no_recursion(self, fresh_matrix):
        """A _RESPONSE TX routed to an ActorModel without a handler must
        NOT cause infinite recursion."""

        class ActorA(ActorModel):
            __tablename__: ClassVar[str] = 'actor_a'
            __storable__: ClassVar[bool] = False

        class ActorB(ActorModel):
            __tablename__: ClassVar[str] = 'actor_b'
            __storable__: ClassVar[bool] = False

        response_tx = TX(
            name='CUSTOM_ACTION_RESPONSE',
            source='actor_a',
            target='actor_b',
            data={'result': 'ok'},
            meta={'req': 'some_uuid'},
        )

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            await fresh_matrix.inbox(response_tx)
        except RecursionError:
            pytest.fail(
                "_RESPONSE TX caused infinite recursion! "
                "ActorModel.handler() is missing the _RESPONSE drop guard."
            )
        finally:
            sys.setrecursionlimit(old_limit)

    @pytest.mark.asyncio
    async def test_normal_unhandled_message_still_errors(self, fresh_matrix):
        """Non-error, non-response unhandled messages should still produce
        an error TX — only error/response TXs are silently dropped."""

        errors_received = []

        class SourceActor(ActorModel):
            __tablename__: ClassVar[str] = 'source_actor'
            __storable__: ClassVar[bool] = False

            # Explicit ERROR handler to capture the error response
            @classmethod
            def ERROR(cls, data, tx):
                errors_received.append((data, tx))

        class TargetModel(ActorModel):
            __tablename__: ClassVar[str] = 'target_model'
            __storable__: ClassVar[bool] = False

        normal_tx = TX(
            name='TOTALLY_UNKNOWN',
            source='source_actor',
            target='target_model',
            data={'some': 'data'},
        )

        await fresh_matrix.inbox(normal_tx)

        # Normal unhandled messages SHOULD produce an error back to sender
        assert len(errors_received) == 1, (
            f"Expected exactly 1 error for unhandled normal message, "
            f"got {len(errors_received)}"
        )
        assert 'Unhandled message: TOTALLY_UNKNOWN' in errors_received[0][0].get('message', '')

    @pytest.mark.asyncio
    async def test_error_tx_with_meta_error_flag_dropped(self, fresh_matrix):
        """TX with meta.error=True but non-ERROR name should also be dropped."""

        class ActorA(ActorModel):
            __tablename__: ClassVar[str] = 'actor_a'
            __storable__: ClassVar[bool] = False

        class ActorB(ActorModel):
            __tablename__: ClassVar[str] = 'actor_b'
            __storable__: ClassVar[bool] = False

        # A TX where is_error is True via meta, not name
        error_tx = TX(
            name='SOME_FAILED_OP',
            source='actor_a',
            target='actor_b',
            data={'message': 'Failed', 'code': 500},
            meta={'error': True},
        )

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            await fresh_matrix.inbox(error_tx)
        except RecursionError:
            pytest.fail(
                "TX with meta.error=True caused infinite recursion! "
                "ActorModel.handler() should check tx.is_error, not just tx.name."
            )
        finally:
            sys.setrecursionlimit(old_limit)


class TestErrorPropagation:
    """Errors must still reach callers via correlation — the fix must NOT
    swallow errors that have a pending request waiting for them."""

    @pytest.mark.asyncio
    async def test_unhandled_message_error_reaches_matrix_request(self, fresh_matrix):
        """matrix.request() must receive the error response for an
        unhandled message. This is the primary frontend delivery path."""

        class TargetModel(ActorModel):
            __tablename__: ClassVar[str] = 'target_model'
            __storable__: ClassVar[bool] = False

        tx = TX(
            name='nonexistent_action',
            source='matrix',
            target='target_model',
            data={'some': 'data'},
        )

        response = await fresh_matrix.request(tx, timeout=2.0)

        assert response.is_error, "Expected error response for unhandled message"
        assert 'Unhandled message: nonexistent_action' in response.data.get('message', '')

    @pytest.mark.asyncio
    async def test_unhandled_message_error_reaches_adapter_request(self, fresh_matrix):
        """NetworkAdapter.request() (HTTP/MCP path) must receive the error.
        This proves errors propagate to the frontend via the API layer."""

        class TargetModel(ActorModel):
            __tablename__: ClassVar[str] = 'target_model'
            __storable__: ClassVar[bool] = False

        adapter = NetworkAdapter(addr='api')
        fresh_matrix.register(adapter)

        tx = TX(
            name='nonexistent_action',
            source='api',
            target='target_model',
            data={'some': 'data'},
        )

        response = await adapter.request(tx, timeout=2.0)

        assert response.is_error, "Expected error response via adapter"
        assert 'Unhandled message: nonexistent_action' in response.data.get('message', '')
        assert response.data.get('code') == 500

    @pytest.mark.asyncio
    async def test_crud_error_reaches_adapter_request(self, fresh_matrix):
        """CRUD errors (e.g., missing id) still reach the adapter caller."""

        class TargetModel(ActorModel):
            __tablename__: ClassVar[str] = 'target_model'
            __storable__: ClassVar[bool] = False

        adapter = NetworkAdapter(addr='api')
        fresh_matrix.register(adapter)

        tx = TX(
            name='get',
            source='api',
            target='target_model',
            data={},  # Missing 'id' — should error
        )

        response = await adapter.request(tx, timeout=2.0)

        assert response.is_error, "Expected error for missing id"
        assert response.data.get('code') == 400

    @pytest.mark.asyncio
    async def test_error_bubbled_to_root_resolves_correlation(self, fresh_matrix):
        """When an ERROR TX bounces to an actor that can't handle it,
        the fix bubbles it to root. If the root has a pending correlation,
        the error should resolve it — not get lost."""

        class ActorA(ActorModel):
            __tablename__: ClassVar[str] = 'actor_a'
            __storable__: ClassVar[bool] = False

        class ActorB(ActorModel):
            __tablename__: ClassVar[str] = 'actor_b'
            __storable__: ClassVar[bool] = False

        # matrix.request sends to actor_b, which can't handle it.
        # The error should resolve the correlation, not timeout.
        original_tx = TX(
            name='some_action',
            source='matrix',
            target='actor_b',
            data={},
        )

        response = await fresh_matrix.request(original_tx, timeout=2.0)

        assert response.is_error, "Expected error, not timeout"
        assert 'Unhandled message' in response.data.get('message', '')
