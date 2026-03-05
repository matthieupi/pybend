"""Tests for the send_message chat handler.

Uses pydantic-ai's TestModel to avoid real LLM calls. Tests send_message
directly (bypassing WebSocket) since the actor handler dispatches to it.
"""
import json
import pytest
from models import Conversation, Message
from n3tx.core.actors.tx import TX


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_basic(self, test_db, seed_data):
        """send_message stores user + assistant messages and returns response."""
        from pydantic_ai.models.test import TestModel

        conv = seed_data["conversations"][0]
        alice = seed_data["users"]["alice"]

        tx = TX(
            name='send_message',
            source='test',
            target='conversations',
            data={'id': conv.id, 'content': 'Hello!', 'llm': TestModel()},
            meta={'user': {'user_id': alice.id, 'email': alice.email}},
        )

        result = await Conversation.send_message(tx.data, tx)

        assert isinstance(result, dict)
        assert 'response' in result
        assert 'usage' in result
        assert 'message_ids' in result
        assert len(result['message_ids']) >= 2  # at least request + response

    @pytest.mark.asyncio
    async def test_messages_stored_in_db(self, test_db, seed_data):
        """Messages are persisted via the join table."""
        conv = seed_data["conversations"][0]

        # Load messages from the join table
        messages = conv._load_messages()
        assert len(messages) >= 2  # from the previous test

        # Check we have both request and response
        kinds = [m.kind for m in messages]
        assert 'request' in kinds
        assert 'response' in kinds

        # Check the user message
        user_msgs = [m for m in messages if m.role == 'user']
        assert len(user_msgs) >= 1
        assert user_msgs[0].content == 'Hello!'

    @pytest.mark.asyncio
    async def test_multi_turn_history(self, test_db, seed_data):
        """Second message includes history from first turn."""
        from pydantic_ai.models.test import TestModel

        conv = seed_data["conversations"][0]
        alice = seed_data["users"]["alice"]

        # Count messages before
        before = conv._load_messages()
        before_count = len(before)

        tx = TX(
            name='send_message',
            source='test',
            target='conversations',
            data={'id': conv.id, 'content': 'Follow up question', 'llm': TestModel()},
            meta={'user': {'user_id': alice.id, 'email': alice.email}},
        )

        result = await Conversation.send_message(tx.data, tx)
        assert isinstance(result, dict)

        # More messages now
        after = conv._load_messages()
        assert len(after) > before_count

    @pytest.mark.asyncio
    async def test_history_round_trip(self, test_db, seed_data):
        """Stored messages convert back to valid pydantic-ai objects."""
        conv = seed_data["conversations"][0]
        history = conv._load_history()

        assert len(history) >= 2
        for msg in history:
            assert msg.kind in ('request', 'response')
            assert hasattr(msg, 'parts')

    @pytest.mark.asyncio
    async def test_send_message_missing_content(self, test_db, seed_data):
        """Empty content returns error."""
        conv = seed_data["conversations"][0]
        alice = seed_data["users"]["alice"]

        tx = TX(
            name='send_message',
            source='test',
            target='conversations',
            data={'id': conv.id, 'content': ''},
            meta={'user': {'user_id': alice.id, 'email': alice.email}},
        )

        result = await Conversation.send_message(tx.data, tx)
        assert isinstance(result, TX)
        assert result.is_error

    @pytest.mark.asyncio
    async def test_send_message_missing_id(self, test_db, seed_data):
        """Missing conversation ID returns error."""
        alice = seed_data["users"]["alice"]

        tx = TX(
            name='send_message',
            source='test',
            target='conversations',
            data={'content': 'hello'},
            meta={'user': {'user_id': alice.id}},
        )

        result = await Conversation.send_message(tx.data, tx)
        assert isinstance(result, TX)
        assert result.is_error

    @pytest.mark.asyncio
    async def test_send_message_wrong_owner(self, test_db, seed_data):
        """Non-owner gets access denied."""
        alice_conv = seed_data["conversations"][0]
        bob = seed_data["users"]["bob"]

        tx = TX(
            name='send_message',
            source='test',
            target='conversations',
            data={'id': alice_conv.id, 'content': 'hello'},
            meta={'user': {'user_id': bob.id, 'email': bob.email}},
        )

        result = await Conversation.send_message(tx.data, tx)
        assert isinstance(result, TX)
        assert result.is_error

    @pytest.mark.asyncio
    async def test_send_message_not_found(self, test_db, seed_data):
        """Non-existent conversation returns 404."""
        alice = seed_data["users"]["alice"]

        tx = TX(
            name='send_message',
            source='test',
            target='conversations',
            data={'id': 99999, 'content': 'hello'},
            meta={'user': {'user_id': alice.id}},
        )

        result = await Conversation.send_message(tx.data, tx)
        assert isinstance(result, TX)
        assert result.is_error
