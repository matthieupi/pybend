"""Tests for Product agent chat — __agent__ = True + /ask streaming endpoint.

Verifies:
- Product schema includes `agent` section (from schema extension)
- Product schema includes `ask` method with stream: true
- POST /products/{id}/ask returns SSE streaming response
- Agent run uses TestModel (no real LLM)
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
    """Patch AGENT_DEFAULTS to use TestModel for all tests.
    Product.__agent__ = True (bool), so LLM comes from AGENT_DEFAULTS.
    """
    from pydantic_ai.models.test import TestModel
    from n3tx_core import config

    original = config.AGENT_DEFAULTS.copy()
    config.AGENT_DEFAULTS['llm'] = TestModel(call_tools=[])
    yield
    config.AGENT_DEFAULTS.clear()
    config.AGENT_DEFAULTS.update(original)


class TestProductAgentSchema:
    """Product schema should reflect __agent__ = True."""

    def test_schema_has_agent_section(self, client):
        resp = client.get("/Product")
        assert resp.status_code == 200
        schema = resp.json()
        assert 'agent' in schema, f"No 'agent' section in schema keys: {list(schema.keys())}"
        assert schema['agent']['enabled'] is True

    def test_schema_has_ask_method(self, client):
        resp = client.get("/Product")
        schema = resp.json()
        methods = schema.get('methods', {})
        assert 'ask' in methods, f"ask not in methods: {list(methods.keys())}"
        assert methods['ask'].get('stream') is True

    def test_schema_ask_method_has_task_param(self, client):
        resp = client.get("/Product")
        schema = resp.json()
        ask = schema['methods']['ask']
        # Method schema uses 'parameters' not 'properties'
        params = ask.get('parameters', ask.get('properties', {}))
        assert 'task' in params, f"task not in method params: {list(params.keys())}"


class TestProductAgentAsk:
    """POST /products/{id}/ask — streaming agent endpoint."""

    def test_ask_requires_auth(self, client, seed_data):
        """Streaming endpoints in Level 3 always return 200 — auth errors are in the stream."""
        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/ask",
            json={"task": "Tell me about this product"},
        )
        # Level 3 actor routing: streaming returns 200, errors are SSE events
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error_events = [e for e in events if e['event'] == 'error']
        assert len(error_events) >= 1, "Should have auth error in stream"

    def test_ask_returns_event_stream(self, client, seed_data, alice_token):
        """Streaming endpoint should return text/event-stream content type."""
        from helpers import auth_header

        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/ask",
            json={"task": "Describe this product"},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        content_type = resp.headers.get('content-type', '')
        assert 'text/event-stream' in content_type

    def test_ask_streams_text_and_done(self, client, seed_data, alice_token):
        """Should receive text chunk events followed by a done event."""
        from helpers import auth_header

        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/ask",
            json={"task": "What is the price?"},
            headers=auth_header(alice_token),
        )

        events = _parse_sse_events(resp.text)
        event_types = [e['event'] for e in events]
        assert 'done' in event_types, f"No done event. Events: {event_types}"

    def test_ask_stream_has_answer_and_usage(self, client, seed_data, alice_token):
        """Stream should contain a chunk with answer and usage fields.

        In Level 3 actor routing, agentic_stream yields TX-aligned chunks that
        include a 'done' chunk with answer+usage. These are sent as SSE 'chunk'
        events (the SSE 'done' sentinel is empty).
        """
        from helpers import auth_header

        product = seed_data["products"][0]
        resp = client.post(
            f"/products/{product.id}/ask",
            json={"task": "Summarize"},
            headers=auth_header(alice_token),
        )

        events = _parse_sse_events(resp.text)
        # Look for the done chunk in the stream (name='done' inside chunk data)
        chunk_events = [e for e in events if e['event'] == 'chunk']
        done_chunks = [e for e in chunk_events
                       if isinstance(e['data'], dict) and e['data'].get('name') == 'done']
        assert len(done_chunks) >= 1, f"No done chunk. Chunks: {[e['data'] for e in chunk_events]}"
        done_data = done_chunks[0]['data'].get('data', {})
        assert 'answer' in done_data
        assert 'usage' in done_data
