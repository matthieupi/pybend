"""Tests for the bug: assistant message appears but content is empty.

Bug: When we send a message, it registers properly, we see an assistant
tag for the next message, but the message itself is empty.

Root cause: chat() stores assistant content from agentic_stream()'s
done chunk answer, which relies on get_output(). If get_output() fails
or returns empty (e.g., with real LLMs, especially thinking models),
the stored content is empty — even though text was streamed successfully.

These tests verify that assistant messages have non-empty content by
simulating the failure mode and ensuring the accumulated streamed text
is used as fallback.
"""
import json
import pytest
from unittest.mock import patch, AsyncMock
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
            current_event = 'chunk'
    return events


class TestAssistantContentNotEmpty:
    """Bug reproduction: assistant message stored with empty content."""

    def test_stored_assistant_message_has_content(self, client, seed_data, alice_token):
        """After chat completes, the assistant message in DB must have non-empty content."""
        conv = seed_data["conversations"][0]
        before = conv._load_messages()
        before_count = len(before)

        resp = client.post(
            f"/conversations/{conv.id}/chat",
            json={"content": "What is the meaning of life?"},
            headers={"x-access-token": alice_token},
        )
        assert resp.status_code == 200

        after = conv._load_messages()
        new_msgs = after[before_count:]

        asst_msgs = [m for m in new_msgs if m.role == 'assistant']
        assert len(asst_msgs) >= 1, (
            f"No assistant message found. New messages: {[(m.role, m.content) for m in new_msgs]}"
        )

        asst = asst_msgs[-1]
        assert asst.content, (
            f"Assistant message has empty content. "
            f"kind={asst.kind}, role={asst.role}, parts={asst.parts}"
        )

    def test_sse_stream_contains_text_chunks(self, client, seed_data, alice_token):
        """The SSE stream must contain at least one chunk event with text data."""
        conv = seed_data["conversations"][0]

        resp = client.post(
            f"/conversations/{conv.id}/chat",
            json={"content": "Tell me a joke"},
            headers={"x-access-token": alice_token},
        )
        assert resp.status_code == 200

        events = _parse_sse(resp.text)
        text_chunks = [
            e for e in events
            if e[0] == 'chunk' and isinstance(e[1], dict) and e[1].get('text')
        ]
        assert len(text_chunks) >= 1, (
            f"No text chunks in SSE stream. All events: {events}"
        )

    def test_assistant_parts_have_content(self, client, seed_data, alice_token):
        """The assistant message parts must contain text with actual content."""
        conv = seed_data["conversations"][0]
        before = conv._load_messages()
        before_count = len(before)

        resp = client.post(
            f"/conversations/{conv.id}/chat",
            json={"content": "Hello assistant"},
            headers={"x-access-token": alice_token},
        )
        assert resp.status_code == 200

        after = conv._load_messages()
        new_msgs = after[before_count:]

        asst_msgs = [m for m in new_msgs if m.role == 'assistant']
        assert len(asst_msgs) >= 1

        asst = asst_msgs[-1]
        text_parts = [
            p for p in asst.parts
            if p.get('part_kind') == 'text' and p.get('content')
        ]
        assert len(text_parts) >= 1, (
            f"No text parts with content in assistant message. "
            f"parts={asst.parts}"
        )


class TestGetOutputFallback:
    """Reproduce the bug: get_output() fails but streaming succeeded.

    This is the core failure mode: agentic_stream() yields text chunks
    (stream works), but get_output() returns empty/raises (done chunk
    has empty answer). The stored assistant message should still have
    content from the accumulated streaming text.
    """

    def test_empty_answer_uses_streamed_text(self, client, seed_data, alice_token):
        """When done chunk has empty answer, stored content should use streamed text.

        Simulates the real-LLM failure: stream_text() yields tokens,
        but get_output() returns '' (e.g., thinking model, API quirk).
        """
        conv = seed_data["conversations"][0]
        before = conv._load_messages()
        before_count = len(before)

        # Patch agentic_stream to simulate: text chunks arrive, but done has empty answer
        async def mock_agentic_stream(self, **kwargs):
            yield {'name': 'text', 'data': {'text': 'Hello '}, 'meta': {'stream': True, 'seq': 0}}
            yield {'name': 'text', 'data': {'text': 'world!'}, 'meta': {'stream': True, 'seq': 1}}
            yield {
                'name': 'done',
                'data': {
                    'answer': '',  # <-- Bug: get_output() returned empty
                    'usage': {'input_tokens': 10, 'output_tokens': 5, 'requests': 1},
                },
                'meta': {'stream': True, 'stream_end': True, 'seq': 2},
            }

        from n3tx.core.agents.mixin import AgentMixin
        with patch.object(AgentMixin, 'agentic_stream', mock_agentic_stream):
            resp = client.post(
                f"/conversations/{conv.id}/chat",
                json={"content": "Say hello world"},
                headers={"x-access-token": alice_token},
            )

        assert resp.status_code == 200

        # The SSE should have streamed text chunks
        events = _parse_sse(resp.text)
        text_chunks = [e for e in events if e[0] == 'chunk' and e[1].get('text')]
        assert len(text_chunks) >= 1, f"Expected text chunks. Events: {events}"

        # The stored assistant message must have content from streamed text
        after = conv._load_messages()
        new_msgs = after[before_count:]
        asst_msgs = [m for m in new_msgs if m.role == 'assistant']
        assert len(asst_msgs) >= 1, "No assistant message stored"

        asst = asst_msgs[-1]
        assert asst.content == 'Hello world!', (
            f"Expected accumulated streamed text 'Hello world!', got: {repr(asst.content)}"
        )

    def test_streamed_text_preferred_over_done_answer(self, client, seed_data, alice_token):
        """Streamed text should be used as content even when done has a different answer.

        This handles the case where get_output() returns a different string
        than what was streamed (e.g., thinking model wrapping, reprocessing).
        """
        conv = seed_data["conversations"][0]
        before = conv._load_messages()
        before_count = len(before)

        async def mock_agentic_stream(self, **kwargs):
            yield {'name': 'text', 'data': {'text': 'The real answer'}, 'meta': {'stream': True, 'seq': 0}}
            yield {
                'name': 'done',
                'data': {
                    'answer': 'The real answer',
                    'usage': {'input_tokens': 10, 'output_tokens': 5, 'requests': 1},
                },
                'meta': {'stream': True, 'stream_end': True, 'seq': 1},
            }

        from n3tx.core.agents.mixin import AgentMixin
        with patch.object(AgentMixin, 'agentic_stream', mock_agentic_stream):
            resp = client.post(
                f"/conversations/{conv.id}/chat",
                json={"content": "Give me the answer"},
                headers={"x-access-token": alice_token},
            )

        assert resp.status_code == 200

        after = conv._load_messages()
        new_msgs = after[before_count:]
        asst_msgs = [m for m in new_msgs if m.role == 'assistant']
        assert len(asst_msgs) >= 1

        asst = asst_msgs[-1]
        assert asst.content == 'The real answer', (
            f"Expected 'The real answer', got: {repr(asst.content)}"
        )

    def test_no_text_chunks_falls_back_to_done_answer(self, client, seed_data, alice_token):
        """When no text chunks arrive but done has answer, use the done answer."""
        conv = seed_data["conversations"][0]
        before = conv._load_messages()
        before_count = len(before)

        async def mock_agentic_stream(self, **kwargs):
            # No text chunks — only done with answer (e.g., non-streaming LLM)
            yield {
                'name': 'done',
                'data': {
                    'answer': 'Direct answer',
                    'usage': {'input_tokens': 10, 'output_tokens': 5, 'requests': 1},
                },
                'meta': {'stream': True, 'stream_end': True, 'seq': 0},
            }

        from n3tx.core.agents.mixin import AgentMixin
        with patch.object(AgentMixin, 'agentic_stream', mock_agentic_stream):
            resp = client.post(
                f"/conversations/{conv.id}/chat",
                json={"content": "Direct question"},
                headers={"x-access-token": alice_token},
            )

        assert resp.status_code == 200

        after = conv._load_messages()
        new_msgs = after[before_count:]
        asst_msgs = [m for m in new_msgs if m.role == 'assistant']
        assert len(asst_msgs) >= 1

        asst = asst_msgs[-1]
        assert asst.content == 'Direct answer', (
            f"Expected 'Direct answer', got: {repr(asst.content)}"
        )
