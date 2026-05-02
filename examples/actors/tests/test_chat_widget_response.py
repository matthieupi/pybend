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

    SSE data is a full TX envelope: {name: 'STREAM', data: {name, data, meta}, ...}
    The inner chunk is at chunk['data'] where chunk = e['data'] (the TX envelope).
    """
    text = ''
    for e in events:
        if e['event'] == 'chunk':
            tx = e['data']
            if not isinstance(tx, dict):
                continue
            # Navigate TX envelope: inner chunk is tx['data']
            inner = tx.get('data', {})
            if not isinstance(inner, dict):
                continue
            # Done chunk carries the final answer as fallback
            if inner.get('name') == 'done':
                answer = inner.get('data', {}).get('answer', '')
                if answer and not text:
                    text = answer
                continue
            # Text extraction from inner chunk
            if inner.get('name') == 'text':
                t = inner.get('data', {}).get('text', '')
                text += t
    return text


class TestStreamingChunkTextExtraction:
    """Verify the widget can extract non-empty text from streaming SSE responses."""

    def test_widget_extracts_text_from_streaming_response(self, client, seed_data, alice_token):
        """Core bug repro: widget must produce non-empty assistant text from SSE stream."""
        from helpers import auth_header

        product = seed_data["products"][0]
        resp = client.post(
            f"/Product/{product.id}/ask",
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
            f"/Product/{product.id}/ask",
            json={"task": "describe"},
            headers=auth_header(alice_token),
        )
        events = _parse_sse_events(resp.text)
        # SSE data is TX envelope; inner chunk name is at e['data']['data']['name']
        text_chunks = [e for e in events
                       if e['event'] == 'chunk'
                       and isinstance(e['data'], dict)
                       and isinstance(e['data'].get('data'), dict)
                       and e['data']['data'].get('name') == 'text']

        assert len(text_chunks) >= 1, "No text chunks in SSE response"

        # Extract text from inner chunk: tx['data']['data']['text']
        extracted = ''
        for tc in text_chunks:
            inner = tc['data']['data']
            t = inner.get('data', {}).get('text', '') if isinstance(inner.get('data'), dict) else ''
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
            f"/Product/{product.id}/ask",
            json={"task": "hello"},
            headers=auth_header(alice_token),
        )
        events = _parse_sse_events(resp.text)
        # SSE data is TX envelope; inner chunk name is at e['data']['data']['name']
        done_chunks = [e for e in events
                       if e['event'] == 'chunk'
                       and isinstance(e['data'], dict)
                       and isinstance(e['data'].get('data'), dict)
                       and e['data']['data'].get('name') == 'done']

        assert len(done_chunks) >= 1, "No done chunk in SSE stream"
        inner = done_chunks[0]['data']['data']
        answer = inner.get('data', {}).get('answer', '')
        assert answer != '', (
            f"Done chunk missing answer. Data: {done_chunks[0]['data']}"
        )
