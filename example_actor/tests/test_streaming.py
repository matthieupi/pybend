# tests/test_streaming.py
"""
Test SSE streaming endpoints via @expose_route(stream=True) over actor routing.

Verifies:
- Streaming endpoint returns text/event-stream content type
- SSE events arrive in correct order (chunk events with countdown)
- Stream terminates with an event: done sentinel
- Works without authentication (access=ANYONE)
- Actor routing (Level 3) handles async generators correctly
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
            current_event = 'chunk'  # reset to default after consuming
    return events


class TestStreamingCountdown:
    """POST /products/{id}/countdown -- SSE streaming via actor routing."""

    def test_streaming_returns_event_stream_content_type(self, client, seed_data):
        """Streaming endpoint should return text/event-stream."""
        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/countdown",
            json={"n": 3},
        )
        assert resp.status_code == 200
        content_type = resp.headers.get('content-type', '')
        assert 'text/event-stream' in content_type

    def test_streaming_returns_chunk_events(self, client, seed_data):
        """Should receive chunk events with countdown data."""
        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/countdown",
            json={"n": 3},
        )
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        chunk_events = [e for e in events if e['event'] == 'chunk']

        # n=3 yields: {count:3}, {count:2}, {count:1}, {count:0}
        assert len(chunk_events) >= 3  # at least the countdown chunks

    def test_streaming_chunks_arrive_in_order(self, client, seed_data):
        """Countdown chunks should arrive in descending order."""
        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/countdown",
            json={"n": 4},
        )
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        chunk_events = [e for e in events if e['event'] == 'chunk']

        counts = [e['data']['count'] for e in chunk_events if 'count' in e['data']]
        # Should be descending: 4, 3, 2, 1, 0
        assert counts == [4, 3, 2, 1, 0]

    def test_streaming_ends_with_done_event(self, client, seed_data):
        """Stream should terminate with event: done."""
        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/countdown",
            json={"n": 2},
        )
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        done_events = [e for e in events if e['event'] == 'done']
        assert len(done_events) == 1

    def test_streaming_no_auth_required(self, client, seed_data):
        """countdown has access=ANYONE, so no auth header is needed."""
        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/countdown",
            json={"n": 2},
        )
        # Should succeed without any auth header
        assert resp.status_code == 200
        assert 'text/event-stream' in resp.headers.get('content-type', '')

    def test_streaming_on_nonexistent_product_returns_error(self, client):
        """Streaming on a nonexistent product should return an error event.

        In Level 3 (actor routing), streaming responses always start with HTTP 200
        because the SSE stream is opened immediately. Errors are communicated
        within the event stream as event: error payloads.
        """
        resp = client.post(
            "/products/99999/countdown",
            json={"n": 2},
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error_events = [e for e in events if e['event'] == 'error']
        assert len(error_events) >= 1
        # Error should mention not found
        error_data = error_events[0]['data']
        assert error_data.get('code') == 404 or 'not found' in str(error_data).lower()

    def test_streaming_countdown_messages(self, client, seed_data):
        """Each chunk should contain a message string."""
        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/countdown",
            json={"n": 2},
        )
        events = _parse_sse_events(resp.text)
        chunk_events = [e for e in events if e['event'] == 'chunk']
        for event in chunk_events:
            assert 'message' in event['data']

    def test_streaming_schema_includes_stream_flag(self, client):
        """Product schema should include stream: true for countdown method."""
        resp = client.get("/Product")
        assert resp.status_code == 200
        schema = resp.json()
        methods = schema.get('methods', {})
        assert 'countdown' in methods, f"countdown not in methods: {list(methods.keys())}"
        assert methods['countdown'].get('stream') is True
