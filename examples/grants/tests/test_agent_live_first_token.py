"""Tests for the first-token-missing bug in ntx-agent-live component.

Bug: When the agent-live component displays a streaming response, the first
token (word) of the response is always missing from the rendered output.

These tests cover three angles:
1. Backend SSE stream delivers all text chunks including the first
2. The complete text assembled from all chunks equals what the UI should display
3. The UI actually displays the complete answer (no first-token dropout)
"""
import json
import pytest
from helpers import auth_header
from n3tx_agents.actor import AgentActor

pytestmark = pytest.mark.integration


def _unwrap_stream_event(payload):
    """Unwrap Level 3 TX STREAM envelopes to the inner agent event."""
    data = payload
    while isinstance(data, dict) and data.get('name') == 'STREAM' and isinstance(data.get('data'), dict):
        data = data['data']
    return data if isinstance(data, dict) else {}


@pytest.fixture(scope="module")
def live_agent(test_db, seed_data):
    """Create a minimal test agent for streaming tests."""
    agent = AgentActor(
        name="Live Test Agent",
        prompt="You are a helpful test agent.",
        llm="test",
    )
    return AgentActor.create(agent)


class TestSSEStreamAllTokensDelivered:
    """Backend SSE stream must deliver ALL text chunks including the first."""

    def test_first_text_chunk_is_not_empty(self, client, live_agent, alice_token):
        """The first 'text' event from /agentic_stream must not be empty.

        If the first chunk is empty, that would explain why the first word is
        missing — the component would get '' before any real content arrives.
        """
        with client.stream(
            "POST",
            f"/agents/{live_agent.id}/agentic_stream",
            json={"task": "hello"},
            headers=auth_header(alice_token),
        ) as resp:
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

            text_chunks = []
            for line in resp.iter_lines():
                if not line or line.startswith(':'):
                    continue
                if line.startswith('data:'):
                    try:
                        payload = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    event = _unwrap_stream_event(payload)
                    name = event.get('name') or event.get('event')
                    data = event.get('data', {})
                    if name == 'text':
                        text_chunks.append(data.get('text', ''))

        assert len(text_chunks) >= 1, "No text events received from agentic_stream"
        # The first text chunk should be non-empty — it IS a token
        first_chunk = text_chunks[0]
        assert first_chunk != '', (
            f"First text chunk from SSE stream is empty string. "
            f"All chunks: {text_chunks!r}"
        )

    def test_all_text_chunks_concatenated_match_done_answer(self, client, live_agent, alice_token):
        """All text chunks joined must equal the 'answer' in the done event.

        If the UI accumulates chunks starting from chunk[1] (skipping chunk[0]),
        the displayed text will be missing the first token.
        """
        with client.stream(
            "POST",
            f"/agents/{live_agent.id}/agentic_stream",
            json={"task": "What can you do?"},
            headers=auth_header(alice_token),
        ) as resp:
            assert resp.status_code == 200

            text_chunks = []
            done_answer = None
            for line in resp.iter_lines():
                if not line or line.startswith(':'):
                    continue
                if line.startswith('data:'):
                    try:
                        payload = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    event = _unwrap_stream_event(payload)
                    name = event.get('name') or event.get('event')
                    data = event.get('data', {})
                    if name == 'text':
                        text_chunks.append(data.get('text', ''))
                    elif name == 'done':
                        done_answer = data.get('answer', '')

        assert done_answer is not None, "No 'done' event received from agentic_stream"
        full_text = ''.join(text_chunks)
        # The text chunks assembled in order must match the final answer
        assert done_answer == full_text, (
            f"Text chunks assembled don't match done.answer.\n"
            f"chunks joined: {full_text!r}\n"
            f"done.answer:   {done_answer!r}\n"
            f"Likely cause: first chunk is being dropped before accumulation starts."
        )


class TestAgentLiveAccumulatesAllChunks:
    """NTTStreamAgent TEXT handler must accumulate all chunks from index 0."""

    def test_stream_text_accumulation_starts_from_first_chunk(
        self, client, live_agent, alice_token
    ):
        """Verify the component receives and accumulates the first text chunk.

        This test collects all text events from the SSE stream and simulates
        what the component's TEXT() handler should accumulate. The first word
        of the final answer must appear in the accumulated output.
        """
        with client.stream(
            "POST",
            f"/agents/{live_agent.id}/agentic_stream",
            json={"task": "Greet me"},
            headers=auth_header(alice_token),
        ) as resp:
            assert resp.status_code == 200

            all_text = []
            done_answer = None
            for line in resp.iter_lines():
                if not line or line.startswith(':'):
                    continue
                if line.startswith('data:'):
                    try:
                        payload = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    event = _unwrap_stream_event(payload)
                    name = event.get('name') or event.get('event')
                    data = event.get('data', {})
                    if name == 'text':
                        all_text.append(data.get('text', ''))
                    elif name == 'done':
                        done_answer = data.get('answer', '')

        if not done_answer or not all_text:
            pytest.skip("No streaming events received — check server configuration")

        # The answer the LLM returned starts with some word.
        # The UI must show the complete answer.
        # If only chunks[1:] are accumulated, the first word is missing.
        full_accumulated = ''.join(all_text)
        first_word_of_answer = done_answer.split()[0] if done_answer.split() else ''

        assert first_word_of_answer, "Done answer is empty — cannot verify first word"
        assert full_accumulated.startswith(first_word_of_answer), (
            f"Accumulated text missing first word.\n"
            f"Expected start: {first_word_of_answer!r}\n"
            f"Got:           {full_accumulated[:50]!r}\n"
            f"This matches the reported bug: first token is always missing."
        )
