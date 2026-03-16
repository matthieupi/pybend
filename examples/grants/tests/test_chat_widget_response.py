"""Tests for ntx-chat widget response extraction — non-streaming path.

Bug: The assistant message appears but its text is empty.
The non-streaming path (AgentActor.run) returns JSON that may be wrapped
in a debug envelope. The widget must extract the answer correctly.
"""
import json
import pytest
from helpers import auth_header
from n3tx_agents.actor import AgentActor

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def simple_agent(test_db, seed_data):
    """Create a simple agent with no tools for clean tests."""
    agent = AgentActor(
        name="Widget Response Test Agent",
        prompt="You are a helpful test agent.",
        llm="test",
    )
    return AgentActor.create(agent)


class TestNonStreamingResponseExtraction:
    """Verify the widget's _sendPost logic can extract answer from response."""

    def test_run_response_answer_extractable_by_widget(self, client, simple_agent, alice_token):
        """Bug repro: widget reads resp.answer but debug mode wraps in {result, _debug}.

        Widget does: answer = resp.answer || resp.result || JSON.stringify(resp)
        In debug mode, resp.result is an object, not a string, so the widget
        would display [object Object] or pass an object to _appendMsg.
        """
        resp = client.post(
            f"/agents/{simple_agent.id}/run",
            json={"task": "hello"},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()

        # Simulate what the widget does
        if isinstance(data, str):
            data = json.loads(data)

        # Widget logic: answer = resp.answer || resp.result || JSON.stringify(resp)
        answer = data.get('answer')
        if not answer:
            answer = data.get('result')

        # answer should be a non-empty string, not an object
        assert answer is not None, f"No answer in response: {list(data.keys())}"
        assert isinstance(answer, str), (
            f"Widget would get a non-string answer: {type(answer).__name__}. "
            f"In debug mode, resp.result is the whole result object, not a string."
        )
        assert len(answer) > 0, "Answer is empty string"
