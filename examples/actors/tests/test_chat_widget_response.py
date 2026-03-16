"""Tests for ntx-chat widget response extraction — the data shapes the frontend receives.

Bug: The assistant message appears but its text is empty.

These tests verify that the SSE chunks from the streaming agent endpoint
contain the data the widget needs to display assistant responses.
They simulate the widget's extraction logic against real backend responses.
"""
import json
import pytest

pytestmark = pytest.mark.integration


def _parse_sse_events(text):
    """Parse SSE event stream text into a list of {event, data} dicts."""
    events = []
    current_event = 'chunk'
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('event: '):
            current_event = line[7:].strip()
        elif line.startswith('data: '):
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                data = line[6:]
            events.append({'event': current_event, 'data': data})
            current_event = 'chunk'
    return events


@pytest.fixture(autouse=True)
def _use_test_model():
    from pydantic_ai.models.test import TestModel
    from n3tx_core import config
    original = config.AGENT_DEFAULTS.copy()
    config.AGENT_DEFAULTS['llm'] = TestModel(call_tools=[])
    yield
    config.AGENT_DEFAULTS.clear()
    config.AGENT_DEFAULTS.update(original)


def _widget_extract_text(events):
    """Simulate the ntx-chat widget's streaming chunk processing.

    Mirrors the onChunk + onDone callbacks in ntx-chat.js _sendStream().
    Returns the text the widget would display in the assistant message.
    """
    text = ''
    for e in events:
        if e['event'] == 'chunk':
            chunk = e['data']
            # Widget handles TX-aligned chunks: {name, data, meta}
            if isinstance(chunk, dict) and chunk.get('name') == 'done':
                # Done chunk carries the final answer as fallback
                if chunk.get('data', {}).get('answer') and not text:
                    text = chunk['data']['answer']
                continue
            # Text extraction: try chunk.data.text first (TX format), then direct keys
            t = ''
            if isinstance(chunk, dict):
                t = (chunk.get('data', {}).get('text') if isinstance(chunk.get('data'), dict) else None) \
                    or chunk.get('text') or chunk.get('chunk') or chunk.get('content') or ''
            text += t
    return text


class TestStreamingChunkTextExtraction:
    """Verify the widget can extract non-empty text from streaming SSE responses."""

    def test_widget_extracts_text_from_streaming_response(self, client, seed_data, alice_token):
        """Core bug repro: widget must produce non-empty assistant text from SSE stream."""
        from helpers import auth_header

        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/ask",
            json={"task": "hello"},
            headers=auth_header(alice_token),
        )
        events = _parse_sse_events(resp.text)
        text = _widget_extract_text(events)

        assert text != '', (
            f"Widget shows empty assistant text. Chunks: "
            f"{[e['data'] for e in events if e['event'] == 'chunk']}"
        )

    def test_widget_extracts_text_from_text_chunks(self, client, seed_data, alice_token):
        """Text chunks (name='text') must have extractable text content."""
        from helpers import auth_header

        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/ask",
            json={"task": "describe"},
            headers=auth_header(alice_token),
        )
        events = _parse_sse_events(resp.text)
        text_chunks = [e for e in events
                       if e['event'] == 'chunk'
                       and isinstance(e['data'], dict)
                       and e['data'].get('name') == 'text']

        assert len(text_chunks) >= 1, "No text chunks in SSE response"

        # Widget must be able to extract text from at least one text chunk
        extracted = ''
        for tc in text_chunks:
            chunk = tc['data']
            t = (chunk.get('data', {}).get('text') if isinstance(chunk.get('data'), dict) else None) \
                or chunk.get('text') or chunk.get('chunk') or chunk.get('content') or ''
            extracted += t

        assert extracted != '', (
            f"Cannot extract text from text chunks. "
            f"Chunk structure: {text_chunks[0]['data']}"
        )

    def test_widget_has_fallback_from_done_chunk(self, client, seed_data, alice_token):
        """Done chunk (name='done') carries the answer as fallback text."""
        from helpers import auth_header

        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/ask",
            json={"task": "hello"},
            headers=auth_header(alice_token),
        )
        events = _parse_sse_events(resp.text)
        done_chunks = [e for e in events
                       if e['event'] == 'chunk'
                       and isinstance(e['data'], dict)
                       and e['data'].get('name') == 'done']

        assert len(done_chunks) >= 1, "No done chunk in SSE stream"
        answer = done_chunks[0]['data'].get('data', {}).get('answer', '')
        assert answer != '', (
            f"Done chunk missing answer. Data: {done_chunks[0]['data']}"
        )
