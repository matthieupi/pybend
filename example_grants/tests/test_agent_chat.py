"""Tests for AgentActor /agentic endpoint via HTTP.

Verifies the full pipeline: HTTP POST -> actor routing -> agent.agentic() -> LLM -> response.
Uses pydantic-ai's built-in 'test' model string which maps to TestModel.
"""
import json
import pytest
from helpers import auth_header
from n3tx.core.agents.actor import AgentActor

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def simple_agent(test_db, seed_data):
    """Create a simple agent with no tools for clean HTTP pipeline tests."""
    agent = AgentActor(
        name="Simple Test Agent",
        prompt="You are a helpful test agent.",
        llm="test",  # pydantic-ai resolves 'test' to TestModel
    )
    return AgentActor.create(agent)


class TestAgentAgenticHTTP:
    """POST /agents/{id}/agentic — non-streaming agent endpoint via HTTP."""

    def test_agentic_requires_auth(self, client, simple_agent):
        resp = client.post(
            f"/agents/{simple_agent.id}/agentic",
            json={"task": "Hello"},
        )
        assert resp.status_code in (401, 403)

    def test_agentic_returns_json_with_answer(self, client, simple_agent, alice_token):
        """POST /agents/{id}/agentic should return JSON with answer field."""
        resp = client.post(
            f"/agents/{simple_agent.id}/agentic",
            json={"task": "List grants"},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        # AgentActor.agentic() returns JSON string, response may be nested
        if isinstance(data, str):
            data = json.loads(data)
        # In debug mode, result may be wrapped in a debug envelope
        if 'result' in data and '_debug' in data:
            data = data['result']
        assert 'answer' in data, f"No 'answer' key in response: {list(data.keys())}"

    def test_agentic_returns_usage(self, client, simple_agent, alice_token):
        """Response should include usage stats."""
        resp = client.post(
            f"/agents/{simple_agent.id}/agentic",
            json={"task": "What sources exist?"},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, str):
            data = json.loads(data)
        if 'result' in data and '_debug' in data:
            data = data['result']
        assert 'usage' in data
        assert data['usage']['requests'] >= 1


class TestAgentSchema:
    """AgentActor schema should include agent section."""

    def test_schema_has_agent_section(self, client):
        resp = client.get("/AgentActor")
        assert resp.status_code == 200
        schema = resp.json()
        assert 'agent' in schema
        assert schema['agent']['enabled'] is True

    def test_schema_has_agentic_method(self, client):
        resp = client.get("/AgentActor")
        schema = resp.json()
        methods = schema.get('methods', {})
        assert 'agentic' in methods, f"agentic not in methods: {list(methods.keys())}"
