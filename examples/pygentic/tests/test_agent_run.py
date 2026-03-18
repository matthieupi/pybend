"""Tests for agent execution in Pygentic."""
import json
import pytest
from helpers import auth_header
from n3tx_agents.actor import AgentActor

pytestmark = pytest.mark.integration


@pytest.fixture(scope='session')
def simple_agent(test_db, seed_data):
    """Create a simple agent with no tools for clean HTTP pipeline tests."""
    agent = AgentActor(
        name='Simple Test Agent',
        prompt='You are a helpful test agent.',
        llm='test',
    )
    return AgentActor.create(agent)


class TestAgentAgentic:
    def test_agentic_via_http(self, client, simple_agent, alice_token):
        resp = client.post(
            f'/agents/{simple_agent.id}/agentic',
            json={'task': 'List tasks'},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, str):
            data = json.loads(data)
        if 'result' in data and '_debug' in data:
            data = data['result']
        assert 'answer' in data

    @pytest.mark.asyncio
    async def test_agentic_direct(self, test_db, seed_data):
        from pydantic_ai.models.test import TestModel
        agent = AgentActor.get(seed_data['agent'].id)
        result_str = await agent.agentic(
            task='List tasks',
            llm=TestModel(call_tools=[]),
        )
        result = json.loads(result_str)
        assert 'answer' in result
