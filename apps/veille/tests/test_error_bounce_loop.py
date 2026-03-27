"""Tests for infinite error bounce loop between ActorModel actors.

Bug: When an ActorModel receives an ERROR TX it can't handle, it sends
another error back instead of silently dropping it. This creates an
infinite bounce loop where source/target addresses grow by one segment
per round trip (e.g., runs/runs/runs/..., grants/grants/grants/...).

Root cause: ActorModel.handler() overrides Actor.handler() but omits
the is_error drop guard that prevents infinite error bouncing.
"""

import sys
import os
import asyncio
import pytest
from typing import ClassVar

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import AUTHENTICATED
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model, registered_models


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


class TestErrorBounceLoop:
    """Reproduce the infinite error bounce between ActorModel actors."""

    @pytest.mark.asyncio
    async def test_error_between_run_and_grant_no_recursion(self, fresh_matrix):
        """Simulate the Veille bug: ERROR bounces between runs and grants
        actors, growing addresses with each hop until RecursionError.

        Observed in production:
            source: runs/runs/runs/... (82 segments)
            target: grants/grants/grants/... (82 segments)
        """
        class Run(ActorModel):
            __tablename__: ClassVar[str] = 'runs'
            __storable__: ClassVar[bool] = False

        class Grant(ActorModel):
            __tablename__: ClassVar[str] = 'grants'
            __storable__: ClassVar[bool] = False

        error_tx = TX(
            name='ERROR',
            source='runs',
            target='grants',
            data={'message': 'Some error', 'code': 500},
            meta={'error': True},
        )

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            await fresh_matrix.inbox(error_tx)
        except RecursionError:
            pytest.fail(
                "ERROR TX bounced infinitely between runs and grants actors! "
                "This is the exact bug observed in production with "
                "runs/runs/runs/... and grants/grants/grants/... addresses."
            )
        finally:
            sys.setrecursionlimit(old_limit)

    @pytest.mark.asyncio
    async def test_unhandled_message_error_does_not_bounce(self, fresh_matrix):
        """When runs sends an unhandled message to grants, the error
        response should reach runs — not bounce infinitely."""

        errors_received = []

        class Run(ActorModel):
            __tablename__: ClassVar[str] = 'runs'
            __storable__: ClassVar[bool] = False

            @classmethod
            def ERROR(cls, data, tx):
                errors_received.append((data, tx))

        class Grant(ActorModel):
            __tablename__: ClassVar[str] = 'grants'
            __storable__: ClassVar[bool] = False

        tx = TX(
            name='nonexistent_action',
            source='runs',
            target='grants',
            data={'some': 'data'},
        )

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            await fresh_matrix.inbox(tx)
        except RecursionError:
            pytest.fail(
                "Unhandled message error bounced infinitely! "
                "The error response from grants to runs triggered another "
                "error back to grants, creating an infinite loop."
            )
        finally:
            sys.setrecursionlimit(old_limit)

        # After fix: runs should receive exactly one error
        assert len(errors_received) == 1, (
            f"Expected runs to receive 1 error, got {len(errors_received)}"
        )

    @pytest.mark.asyncio
    async def test_veille_e2e_request_unhandled_returns_error(self, fresh_matrix, tmp_path):
        """End-to-end: matrix.request() with an unhandled message should
        return a clean error, not timeout from infinite bounce."""
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            __tablename__: ClassVar[str] = 'grants'
            __storable__: ClassVar[bool] = True
            __access__: ClassVar[dict] = {'read': AUTHENTICATED, 'create': AUTHENTICATED}
            title: str = Field(default='')

        register_model(Grant, storage=storage)

        class Run(ActorModel):
            __tablename__: ClassVar[str] = 'runs'
            __storable__: ClassVar[bool] = False

        tx = TX(
            name='nonexistent_action',
            source='matrix',
            target='grants',
            data={'some': 'data'},
        )

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            response = await fresh_matrix.request(tx, timeout=2.0)
        except RecursionError:
            pytest.fail(
                "matrix.request() hit RecursionError from error bounce loop! "
                "The error response should be returned cleanly."
            )
        finally:
            sys.setrecursionlimit(old_limit)

        assert response.is_error
        assert 'Unhandled message' in response.data.get('message', '')
        # Source should not have grown beyond the actor's addr
        assert response.source.count('/') <= 2, (
            f"Response source grew unreasonably: {response.source}"
        )
