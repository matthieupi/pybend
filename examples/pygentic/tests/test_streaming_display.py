"""Tests for agent streaming display.

Validates:
1. SSE wire format: Level 3 actor routing wraps chunks in TX envelope
   {name: 'STREAM', data: {name: 'text', ...}}. Inner events must be
   accessible at the correct nested path.
2. Schema events: GET /AgentActor must expose event schemas in the
   methods.agentic_stream.events section.
"""
import json
import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration


# -- Helper: parse SSE lines from raw bytes ---------------------------------

def _parse_sse_events(raw_text):
    """Parse SSE text into list of (event_type, parsed_data) tuples."""
    events = []
    event_type = 'chunk'  # SSE default
    for line in raw_text.splitlines():
        line = line.rstrip()
        if line.startswith('event: '):
            event_type = line[7:].strip()
        elif line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                events.append((event_type, data))
            except json.JSONDecodeError:
                pass
        elif line == '':
            event_type = 'chunk'  # reset after blank line
    return events


def _unwrap_stream_chunk(chunk_data):
    """Unwrap STREAM envelope to get inner TX-aligned dict.

    Level 3: {name:'STREAM', data:{name:'text', data:{...}}} -> {name:'text', data:{...}}
    Level 1/2: {name:'text', data:{...}} -> {name:'text', data:{...}}
    """
    if chunk_data.get('name') == 'STREAM' and isinstance(chunk_data.get('data'), dict):
        return chunk_data['data']
    return chunk_data


def _create_simple_agent(client, alice_token):
    """Create a no-tools agent that uses TestModel.

    With no tools, pydantic-ai TestModel produces text+done events
    instead of looping through tool calls and erroring.
    """
    resp = client.post(
        '/agents',
        json={'name': 'Simple Test Agent', 'prompt': 'You are a test assistant.', 'llm': 'test'},
        headers=auth_header(alice_token),
    )
    assert resp.status_code in (200, 201), f"Failed to create agent: {resp.text}"
    data = resp.json()
    return data.get('id')


# -- Test 1: SSE chunks carry valid inner events ----------------------------

class TestSseChunkFormat:
    """Verify the Level 3 actor routing path emits properly structured chunks."""

    def test_agentic_stream_inner_events_are_accessible(
        self, client, seed_data, alice_token
    ):
        """Each SSE chunk should carry an inner event accessible via unwrapping.
        The inner event names should be 'text', 'done', etc. -- not 'STREAM'.
        """
        agent_id = seed_data['agent'].id
        resp = client.post(
            f'/agents/{agent_id}/agentic_stream',
            json={'task': 'Say hello'},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        assert 'text/event-stream' in resp.headers.get('content-type', '')

        events = _parse_sse_events(resp.text)
        assert events, "No SSE events received"

        chunk_events = [(et, d) for et, d in events if et == 'chunk']
        assert chunk_events, "No chunk events in stream"

        # Unwrap and check inner event names
        inner_names = set()
        for _, chunk_data in chunk_events:
            inner = _unwrap_stream_chunk(chunk_data)
            if inner.get('name'):
                inner_names.add(inner['name'])

        assert inner_names, (
            f"No inner event names found after unwrapping. "
            f"Raw chunk names: {[d.get('name') for _, d in chunk_events]}"
        )
        # Inner names should be actual event types, not 'STREAM'
        assert 'STREAM' not in inner_names, (
            f"Inner events still contain 'STREAM' after unwrapping: {inner_names}"
        )

    def test_agentic_stream_text_accessible_via_unwrap(
        self, client, seed_data, alice_token
    ):
        """Text data should be accessible at inner.data.text after unwrapping.

        Uses a no-tools agent so pydantic-ai TestModel emits text+done
        events rather than looping through tool calls and erroring.
        """
        agent_id = _create_simple_agent(client, alice_token)
        resp = client.post(
            f'/agents/{agent_id}/agentic_stream',
            json={'task': 'Briefly say "hello"'},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)

        chunk_events = [(et, d) for et, d in events if et == 'chunk']
        # Unwrap and find text events
        text_chunks = []
        for _, chunk_data in chunk_events:
            inner = _unwrap_stream_chunk(chunk_data)
            if inner.get('name') == 'text':
                text_chunks.append(inner)

        assert text_chunks, (
            f"No 'text' events found after unwrapping. "
            f"Inner event names: {[_unwrap_stream_chunk(d).get('name') for _, d in chunk_events]}"
        )

        for chunk in text_chunks:
            assert 'data' in chunk, f"text event missing 'data' key: {chunk}"
            assert 'text' in chunk['data'], (
                f"text event.data missing 'text' key: {chunk['data']}"
            )

    def test_agentic_stream_done_carries_answer_via_unwrap(
        self, client, seed_data, alice_token
    ):
        """The done event should carry answer accessible at inner.data.answer.

        Uses a no-tools agent so pydantic-ai TestModel emits text+done
        events rather than looping through tool calls and erroring.
        """
        agent_id = _create_simple_agent(client, alice_token)
        resp = client.post(
            f'/agents/{agent_id}/agentic_stream',
            json={'task': 'Complete a task'},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)

        chunk_events = [(et, d) for et, d in events if et == 'chunk']
        # Unwrap and find done events
        done_chunks = []
        for _, chunk_data in chunk_events:
            inner = _unwrap_stream_chunk(chunk_data)
            if inner.get('name') == 'done':
                done_chunks.append(inner)

        assert done_chunks, (
            f"No 'done' events found after unwrapping. "
            f"Inner event names: {[_unwrap_stream_chunk(d).get('name') for _, d in chunk_events]}"
        )

        done = done_chunks[-1]
        assert 'data' in done, f"done event missing 'data': {done}"
        assert 'answer' in done['data'], (
            f"done event.data missing 'answer' key. "
            f"Keys: {list(done['data'].keys())}"
        )


# -- Test 2: Schema events --------------------------------------------------

class TestStreamEventSchema:
    """Verify stream event schemas appear in GET /AgentActor."""

    def test_agentic_stream_method_has_events_in_schema(self, client):
        """The agentic_stream method should declare event schemas."""
        resp = client.get('/AgentActor')
        assert resp.status_code == 200
        schema = resp.json()

        assert 'methods' in schema, f"Schema missing 'methods' key"
        assert 'agentic_stream' in schema['methods'], (
            f"Schema methods missing 'agentic_stream'. "
            f"Available: {list(schema['methods'].keys())}"
        )

        method = schema['methods']['agentic_stream']
        assert 'events' in method, (
            f"agentic_stream missing 'events'. Keys: {list(method.keys())}"
        )

        events = method['events']
        expected = {'text', 'tool_call', 'tool_result', 'thinking', 'done'}
        assert set(events.keys()) == expected, (
            f"Event keys mismatch. Got: {set(events.keys())}, expected: {expected}"
        )

    def test_event_schemas_have_correct_properties(self, client):
        """Each event schema should have valid JSON Schema properties."""
        resp = client.get('/AgentActor')
        schema = resp.json()
        events = schema['methods']['agentic_stream']['events']

        # TextChunk should have 'text' property
        assert 'properties' in events['text'], f"text event missing properties"
        assert 'text' in events['text']['properties'], (
            f"text event missing 'text' property. "
            f"Properties: {list(events['text']['properties'].keys())}"
        )

        # DoneChunk should have 'answer', 'usage', 'tool_calls'
        assert 'properties' in events['done'], f"done event missing properties"
        done_props = set(events['done']['properties'].keys())
        assert {'answer', 'usage', 'tool_calls'}.issubset(done_props), (
            f"done event missing expected properties. Got: {done_props}"
        )

        # ToolCallEvent should have 'tool', 'args', 'call_id'
        assert 'properties' in events['tool_call'], f"tool_call event missing properties"
        tc_props = set(events['tool_call']['properties'].keys())
        assert {'tool', 'args', 'call_id'}.issubset(tc_props), (
            f"tool_call event missing expected properties. Got: {tc_props}"
        )
