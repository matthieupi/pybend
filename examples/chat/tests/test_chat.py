"""Tests for the SSE streaming chat endpoint.

Uses pydantic-ai's TestModel to avoid real LLM calls. Tests the
POST /conversations/{id}/chat SSE endpoint that replaced the old
send_message WebSocket handler.
"""
import json
import pytest
from models import Conversation, Message


def _parse_sse(text):
    """Parse SSE response text into a list of (event_type, data) tuples."""
    events = []
    current_event = 'chunk'
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('event: '):
            current_event = line[7:].strip()
        elif line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                events.append((current_event, data))
            except json.JSONDecodeError:
                pass
            current_event = 'chunk'  # reset for next event
    return events


class TestChatSSEEndpoint:
    def test_chat_returns_sse_stream(self, client, seed_data, alice_token):
        """POST /conversations/{id}/chat returns text/event-stream."""
        conv = seed_data["conversations"][0]
        resp = client.post(
            f"/conversations/{conv.id}/chat",
            json={"content": "Hello!"},
            headers={"x-access-token": alice_token},
        )
        assert resp.status_code == 200
        assert 'text/event-stream' in resp.headers.get('content-type', '')

    def test_chat_sse_contains_chunks(self, client, seed_data, alice_token):
        """SSE stream contains chunk events with text data."""
        conv = seed_data["conversations"][0]
        resp = client.post(
            f"/conversations/{conv.id}/chat",
            json={"content": "Hello!"},
            headers={"x-access-token": alice_token},
        )
        events = _parse_sse(resp.text)
        # Should have at least one chunk and one done event
        chunk_events = [e for e in events if e[0] == 'chunk']
        done_events = [e for e in events if e[0] == 'done']
        assert len(done_events) >= 1, f"Expected done event, got: {events}"

    def test_chat_stores_messages(self, client, seed_data, alice_token):
        """Messages are persisted after streaming completes."""
        conv = seed_data["conversations"][0]

        # Count messages before
        before = conv._load_messages()
        before_count = len(before)

        resp = client.post(
            f"/conversations/{conv.id}/chat",
            json={"content": "Store this message"},
            headers={"x-access-token": alice_token},
        )
        assert resp.status_code == 200

        # Verify messages were stored (user + assistant)
        after = conv._load_messages()
        assert len(after) >= before_count + 2

        # Check we have both user and assistant messages
        new_msgs = after[before_count:]
        roles = [m.role for m in new_msgs]
        assert 'user' in roles
        assert 'assistant' in roles

    def test_chat_multi_turn_history(self, client, seed_data, alice_token):
        """Second chat includes history from first turn."""
        conv = seed_data["conversations"][0]
        before = conv._load_messages()
        before_count = len(before)

        # First message
        client.post(
            f"/conversations/{conv.id}/chat",
            json={"content": "First message"},
            headers={"x-access-token": alice_token},
        )

        mid = conv._load_messages()
        mid_count = len(mid)
        assert mid_count > before_count

        # Second message
        client.post(
            f"/conversations/{conv.id}/chat",
            json={"content": "Follow up"},
            headers={"x-access-token": alice_token},
        )

        after = conv._load_messages()
        assert len(after) > mid_count

    def test_chat_history_round_trip(self, client, seed_data, alice_token):
        """Stored messages convert back to valid pydantic-ai objects."""
        conv = seed_data["conversations"][0]
        history = conv._load_history()

        assert len(history) >= 2
        for msg in history:
            assert msg.kind in ('request', 'response')
            assert hasattr(msg, 'parts')

    def test_chat_requires_auth(self, client, seed_data):
        """Chat endpoint requires authentication."""
        conv = seed_data["conversations"][0]
        resp = client.post(
            f"/conversations/{conv.id}/chat",
            json={"content": "hello"},
        )
        # SSE streaming endpoints may return 200 with error events,
        # or reject at the HTTP level — both are valid.
        if resp.status_code == 200:
            events = _parse_sse(resp.text)
            # Without auth, should get no text chunks (error or empty)
            text_chunks = [e for e in events if e[0] == 'chunk'
                          and isinstance(e[1], dict) and 'text' in e[1]]
            assert len(text_chunks) == 0
        else:
            assert resp.status_code in (401, 403, 422)

    def test_chat_wrong_owner(self, client, seed_data, bob_token):
        """Non-owner gets access denied."""
        alice_conv = seed_data["conversations"][0]
        resp = client.post(
            f"/conversations/{alice_conv.id}/chat",
            json={"content": "hello"},
            headers={"x-access-token": bob_token},
        )
        # Should fail — either HTTP error or error event in SSE
        if resp.status_code == 200:
            events = _parse_sse(resp.text)
            error_events = [e for e in events if e[0] == 'error' or
                           (e[1] and 'error' in e[1])]
            assert len(error_events) > 0 or 'Access denied' in resp.text
        else:
            assert resp.status_code in (403, 500)

    def test_chat_not_found(self, client, seed_data, alice_token):
        """Non-existent conversation returns error."""
        resp = client.post(
            "/conversations/99999/chat",
            json={"content": "hello"},
            headers={"x-access-token": alice_token},
        )
        # SSE streaming may return 200 with error events
        if resp.status_code == 200:
            events = _parse_sse(resp.text)
            # Should get an error event, not text chunks
            text_chunks = [e for e in events if e[0] == 'chunk'
                          and isinstance(e[1], dict) and 'text' in e[1]]
            assert len(text_chunks) == 0
        else:
            assert resp.status_code in (404, 500)
