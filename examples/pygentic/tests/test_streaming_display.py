"""Tests for agent streaming display bug.

Bug: When using actor routing (Level 3), the SSE chunks sent to the frontend
have {name: 'STREAM', data: {name: 'text', ...}} instead of {name: 'text', data: {...}}.
The frontend switch(chunk.name) matches 'STREAM' (no case) instead of 'text'/'tool_call'
etc., so nothing is rendered.

Root cause: _sse_from_stream in network_api.py serializes the full TX envelope
(asdict(chunk)) instead of chunk.data for regular stream chunks.

Expected SSE format: event: chunk / data: {"name": "text", "data": {"text": "..."}}
Actual (broken):     event: chunk / data: {"name": "STREAM", "data": {"name": "text", ...}}
"""
import json
import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration


# ── Helper: parse SSE lines from raw bytes ───────────────────────────────────

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


# ── Test 1: SSE chunk.data should be the TX-aligned event, not a STREAM wrapper ─

class TestSseChunkFormat:
    """Verify the Level 3 actor routing path emits unwrapped chunk payloads."""

    def test_agentic_stream_chunks_have_name_at_top_level(
        self, client, seed_data, alice_token
    ):
        """Each SSE event: chunk should have {name: 'text'|'done'|..., data: {...}}
        NOT {name: 'STREAM', data: {name: 'text', ...}}.

        This is the primary symptom: frontend switch(chunk.name) sees 'STREAM'
        instead of 'text', so nothing renders.
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

        # FAILING: currently chunk.name is 'STREAM', should be 'text', 'tool_call', etc.
        top_level_names = {d.get('name') for _, d in chunk_events}
        assert 'STREAM' not in top_level_names, (
            f"SSE chunks contain 'STREAM' wrapper — frontend can't dispatch them. "
            f"Chunk names found: {top_level_names}. "
            f"Expected names like 'text', 'done', 'thinking', 'tool_call'."
        )

    def test_agentic_stream_text_chunk_has_data_with_text_key(
        self, client, seed_data, alice_token
    ):
        """When the agent produces text, the SSE chunk should be:
           {name: 'text', data: {text: '...'}, meta: {...}}
        NOT:
           {name: 'STREAM', data: {name: 'text', data: {text: '...'}, meta: {...}}, ...}
        """
        agent_id = seed_data['agent'].id
        resp = client.post(
            f'/agents/{agent_id}/agentic_stream',
            json={'task': 'Briefly say "hello"'},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)

        chunk_events = [(et, d) for et, d in events if et == 'chunk']
        # Find any text chunk
        text_chunks = [d for _, d in chunk_events if d.get('name') == 'text']

        # FAILING: text_chunks is empty because all chunks have name='STREAM'
        assert text_chunks, (
            f"No 'text' chunks found. Chunk names: "
            f"{[d.get('name') for _, d in chunk_events]}. "
            f"This means the frontend sees name='STREAM' and renders nothing."
        )

        for chunk in text_chunks:
            assert 'data' in chunk, f"text chunk missing 'data' key: {chunk}"
            assert 'text' in chunk['data'], (
                f"text chunk.data missing 'text' key: {chunk['data']}"
            )

    def test_agentic_stream_done_chunk_carries_answer(
        self, client, seed_data, alice_token
    ):
        """The 'done' event chunk should carry {answer, usage, tool_calls} directly,
        accessible as chunk.data.answer in the frontend.

        If the STREAM wrapper bug is present, done data is nested two levels deep:
        chunk.data.data.answer instead of chunk.data.answer.
        """
        agent_id = seed_data['agent'].id
        resp = client.post(
            f'/agents/{agent_id}/agentic_stream',
            json={'task': 'Complete a task'},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)

        chunk_events = [(et, d) for et, d in events if et == 'chunk']
        done_chunks = [d for _, d in chunk_events if d.get('name') == 'done']

        # FAILING: no 'done' chunk found at top level (wrapped as 'STREAM')
        assert done_chunks, (
            "No 'done' chunk found at top level of SSE events. "
            f"Available chunk names: {[d.get('name') for _, d in chunk_events]}"
        )

        done = done_chunks[-1]
        assert 'data' in done, f"done chunk missing 'data': {done}"
        assert 'answer' in done['data'], (
            f"done chunk.data missing 'answer' key — frontend can't extract the result. "
            f"done.data keys: {list(done['data'].keys())}"
        )
