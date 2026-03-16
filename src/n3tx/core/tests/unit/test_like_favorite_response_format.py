"""Tests for like/favorite response format at the HTTP level.

Verifies that like/favorite methods return plain dicts (not wrapped in
{result: ...}) and that the response is a JSON object the frontend can
parse and route correctly.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import ClassVar

from pydantic import Field

from n3tx.core.models.actor_model import ActorModel
from n3tx.core.actors.tx import TX
from n3tx.core.actors.actor import Actor
from n3tx.core.utils.descriptors import fullmethod
from n3tx.core.actors.matrix import Matrix

pytestmark = pytest.mark.unit


class _LikeTestModel(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = 'like_test'
    name: str = Field(default='')

    @classmethod
    def LIKE_RETURNS_DICT(cls, data, tx):
        """Simulates a like method that returns a dict."""
        return {'action': 'liked'}

    @classmethod
    def FAVORITE_RETURNS_DICT(cls, data, tx):
        """Simulates a favorite method that returns a dict."""
        return {'action': 'favorited'}


@pytest.fixture(autouse=True)
def reset_actor_state():
    saved_matrix = Actor.__matrix__
    saved_actor_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_model_children = _LikeTestModel.__children__.copy()
    yield
    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_actor_children
    Matrix.__children__ = saved_matrix_children
    _LikeTestModel.__children__ = saved_model_children


@pytest.fixture
def capture_send():
    sent = []

    @fullmethod
    async def mock_send(target, tx):
        sent.append(tx)

    original = _LikeTestModel.__dict__.get('send')
    type.__setattr__(_LikeTestModel, 'send', mock_send)
    yield sent
    if original:
        type.__setattr__(_LikeTestModel, 'send', original)
    else:
        type.__delattr__(_LikeTestModel, 'send')


class TestLikeFavoriteResponseFormat:
    """Response from like/favorite methods should be plain dicts, not wrapped."""

    @pytest.mark.asyncio
    async def test_like_returns_action_dict_not_wrapped(self, capture_send):
        """Like method returning {'action': 'liked'} should send that dict
        directly in the reply, not wrapped in {'result': ...}."""
        tx = TX(name='LIKE_RETURNS_DICT', source='client', target='like_test', data={})
        await _LikeTestModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert reply.name == 'LIKE_RETURNS_DICT_RESPONSE'
        # Response data must be the raw dict, no wrapper
        assert reply.data == {'action': 'liked'}
        assert 'result' not in (reply.data if isinstance(reply.data, dict) else {})

    @pytest.mark.asyncio
    async def test_favorite_returns_action_dict_not_wrapped(self, capture_send):
        """Favorite method returning {'action': 'favorited'} should send that
        dict directly in the reply, not wrapped."""
        tx = TX(name='FAVORITE_RETURNS_DICT', source='client', target='like_test', data={})
        await _LikeTestModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert reply.name == 'FAVORITE_RETURNS_DICT_RESPONSE'
        assert reply.data == {'action': 'favorited'}

    @pytest.mark.asyncio
    async def test_response_data_is_json_serializable_dict(self, capture_send):
        """The response data should be a dict that json.dumps can handle,
        not a string that needs double-parsing."""
        import json
        tx = TX(name='LIKE_RETURNS_DICT', source='client', target='like_test', data={})
        await _LikeTestModel.handler(tx)

        reply = capture_send[0]
        assert isinstance(reply.data, dict)
        # Should be directly serializable without double-encoding
        serialized = json.dumps(reply.data)
        parsed = json.loads(serialized)
        assert parsed == {'action': 'liked'}
