"""
Tests for ActorModel lifecycle event publishing.

Covers _publish_lifecycle() method and _subscribers ClassVar behavior:
class isolation, no-subscriber no-op, task creation, event types, TX shape.
"""

import asyncio
import pytest
from typing import ClassVar
from unittest.mock import patch

from pydantic import Field

from pybend.core.actors.actor import Actor, actormethod
from pybend.core.actors.tx import TX
from pybend.core.models.actor_model import ActorModel

pytestmark = pytest.mark.unit


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def reset_actor_state():
    """Save and restore Actor class-level state between tests."""
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children


# ===================================================================
# TestSubscribersDefault
# ===================================================================

class TestSubscribersDefault:
    """_subscribers ClassVar defaults and class isolation."""

    def test_default_subscribers_is_empty_list(self):
        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'sub_default'
            name: str = Field(default='')

        assert _M._subscribers == []

    def test_each_subclass_has_own_subscribers(self):
        class _A(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'sub_a'
            _subscribers: ClassVar[list] = ['audit/logger']
            name: str = Field(default='')

        class _B(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'sub_b'
            _subscribers: ClassVar[list] = ['federation/outbox']
            name: str = Field(default='')

        assert _A._subscribers == ['audit/logger']
        assert _B._subscribers == ['federation/outbox']

    def test_modifying_one_subclass_subscribers_does_not_affect_another(self):
        class _C(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'sub_c'
            _subscribers: ClassVar[list] = ['x']
            name: str = Field(default='')

        class _D(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'sub_d'
            _subscribers: ClassVar[list] = ['y']
            name: str = Field(default='')

        _C._subscribers.append('z')
        assert 'z' in _C._subscribers
        assert 'z' not in _D._subscribers

    def test_modifying_subclass_subscribers_does_not_affect_base(self):
        class _E(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'sub_e'
            _subscribers: ClassVar[list] = ['audit']
            name: str = Field(default='')

        _E._subscribers.append('extra')
        assert 'extra' not in ActorModel._subscribers


# ===================================================================
# TestPublishLifecycleNoSubscribers
# ===================================================================

class TestPublishLifecycleNoSubscribers:
    """_publish_lifecycle with empty _subscribers does nothing."""

    def test_no_subscribers_does_not_error(self):
        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_noop'
            name: str = Field(default='')

        # Should not raise
        _M._publish_lifecycle('after_create', {'id': 1})

    def test_no_subscribers_does_not_create_task(self):
        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_notask'
            name: str = Field(default='')

        with patch('pybend.core.models.actor_model.asyncio.create_task') as mock_ct:
            _M._publish_lifecycle('after_create', {'id': 1})
            assert mock_ct.call_count == 0


# ===================================================================
# TestPublishLifecycleWithSubscribers
# ===================================================================

class TestPublishLifecycleWithSubscribers:
    """_publish_lifecycle creates async tasks when subscribers exist."""

    def test_one_subscriber(self):
        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_one'
            _subscribers: ClassVar[list] = ['audit/logger']
            name: str = Field(default='')

        with patch('pybend.core.models.actor_model.asyncio.create_task') as mock_ct:
            _M._publish_lifecycle('after_create', {'id': 1})
            assert mock_ct.call_count == 1

    def test_multiple_subscribers_one_task_per_subscriber(self):
        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_multi'
            _subscribers: ClassVar[list] = [
                'audit/logger',
                'federation/outbox',
                'websocket/bridge',
            ]
            name: str = Field(default='')

        with patch('pybend.core.models.actor_model.asyncio.create_task') as mock_ct:
            _M._publish_lifecycle('after_update', {'id': 5, 'name': 'updated'})
            assert mock_ct.call_count == 3


# ===================================================================
# TestPublishLifecycleEvents
# ===================================================================

class TestPublishLifecycleEvents:
    """Verify the three event types produce correct TX."""

    def _capture_tx(self, model_cls, event, entity_data):
        """Helper: run _publish_lifecycle and capture the TX passed to send."""
        sent = []

        original_send = model_cls.send

        @actormethod
        async def capture_send(target, tx):
            sent.append(tx)

        # Temporarily override send on the class
        model_cls.send = capture_send

        loop = asyncio.new_event_loop()
        try:
            with patch(
                'pybend.core.models.actor_model.asyncio.create_task',
                side_effect=lambda coro: loop.run_until_complete(coro),
            ):
                model_cls._publish_lifecycle(event, entity_data)
        finally:
            model_cls.send = original_send
            loop.close()

        return sent

    def test_after_create_event(self):
        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_evt_create'
            _subscribers: ClassVar[list] = ['target/addr']
            name: str = Field(default='')

        sent = self._capture_tx(_M, 'after_create', {'id': 1, 'name': 'new'})
        assert len(sent) == 1
        assert sent[0].data['event'] == 'after_create'

    def test_after_update_event(self):
        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_evt_update'
            _subscribers: ClassVar[list] = ['target/addr']
            name: str = Field(default='')

        sent = self._capture_tx(_M, 'after_update', {'id': 2, 'name': 'changed'})
        assert len(sent) == 1
        assert sent[0].data['event'] == 'after_update'

    def test_after_delete_event(self):
        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_evt_delete'
            _subscribers: ClassVar[list] = ['target/addr']
            name: str = Field(default='')

        sent = self._capture_tx(_M, 'after_delete', {'id': 3})
        assert len(sent) == 1
        assert sent[0].data['event'] == 'after_delete'


# ===================================================================
# TestPublishLifecycleTXShape
# ===================================================================

class TestPublishLifecycleTXShape:
    """The TX created by _publish_lifecycle has correct structure."""

    def test_tx_shape(self):
        sent = []

        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_shape'
            _subscribers: ClassVar[list] = ['target/addr']
            name: str = Field(default='')

            @actormethod
            async def send(target, tx):
                sent.append(tx)

        loop = asyncio.new_event_loop()
        with patch(
            'pybend.core.models.actor_model.asyncio.create_task',
            side_effect=lambda coro: loop.run_until_complete(coro),
        ):
            _M._publish_lifecycle('after_create', {'id': 1, 'name': 'test'})

        assert len(sent) == 1
        tx = sent[0]
        assert tx.name == 'LIFECYCLE'
        assert tx.source == 'lc_shape'
        assert tx.target == 'target/addr'
        assert tx.data['event'] == 'after_create'
        assert tx.data['entity'] == {'id': 1, 'name': 'test'}
        loop.close()

    def test_tx_is_instance_of_TX(self):
        sent = []

        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_txtype'
            _subscribers: ClassVar[list] = ['monitor']
            name: str = Field(default='')

            @actormethod
            async def send(target, tx):
                sent.append(tx)

        loop = asyncio.new_event_loop()
        with patch(
            'pybend.core.models.actor_model.asyncio.create_task',
            side_effect=lambda coro: loop.run_until_complete(coro),
        ):
            _M._publish_lifecycle('after_update', {'id': 5})

        assert len(sent) == 1
        assert isinstance(sent[0], TX)
        loop.close()

    def test_tx_source_matches_tablename_addr(self):
        """__addr__ is derived from __tablename__ by ActorMeta."""
        sent = []

        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'my_custom_table'
            _subscribers: ClassVar[list] = ['sub']
            name: str = Field(default='')

            @actormethod
            async def send(target, tx):
                sent.append(tx)

        loop = asyncio.new_event_loop()
        with patch(
            'pybend.core.models.actor_model.asyncio.create_task',
            side_effect=lambda coro: loop.run_until_complete(coro),
        ):
            _M._publish_lifecycle('after_delete', {'id': 99})

        assert sent[0].source == 'my_custom_table'
        loop.close()

    def test_tx_target_is_subscriber_address(self):
        """Each subscriber gets a TX with target set to their address."""
        sent = []

        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_target'
            _subscribers: ClassVar[list] = ['audit/logger', 'federation/outbox']
            name: str = Field(default='')

            @actormethod
            async def send(target, tx):
                sent.append(tx)

        loop = asyncio.new_event_loop()
        with patch(
            'pybend.core.models.actor_model.asyncio.create_task',
            side_effect=lambda coro: loop.run_until_complete(coro),
        ):
            _M._publish_lifecycle('after_create', {'id': 1})

        assert len(sent) == 2
        targets = {tx.target for tx in sent}
        assert targets == {'audit/logger', 'federation/outbox'}
        loop.close()

    def test_tx_data_entity_is_passed_data(self):
        """The entity field in TX data is the exact dict passed to _publish_lifecycle."""
        sent = []
        entity_data = {'id': 42, 'name': 'Widget', 'price': 9.99}

        class _M(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'lc_entity'
            _subscribers: ClassVar[list] = ['sub']
            name: str = Field(default='')

            @actormethod
            async def send(target, tx):
                sent.append(tx)

        loop = asyncio.new_event_loop()
        with patch(
            'pybend.core.models.actor_model.asyncio.create_task',
            side_effect=lambda coro: loop.run_until_complete(coro),
        ):
            _M._publish_lifecycle('after_create', entity_data)

        assert sent[0].data['entity'] == entity_data
        loop.close()
