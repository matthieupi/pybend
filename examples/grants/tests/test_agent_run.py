"""Tests for AgentActor.agentic() — the LLM execution endpoint.

Uses Pydantic AI's TestModel to mock the LLM. The agent discovers
tools from real registered actors and routes calls through Matrix.
"""
import json
import pytest
from helpers import auth_header
from n3tx_agents.actor import AgentActor


class TestAgentAgentic:
    @pytest.mark.asyncio
    async def test_agent_agentic_no_tools(self, test_db, seed_data):
        """Agent with no tools returns a simple answer."""
        from pydantic_ai.models.test import TestModel

        agent = AgentActor.get(seed_data["agent"].id)
        result_str = await agent.agentic(
            task="Hello, what can you do?",
            llm=TestModel(call_tools=[]),
        )
        result = json.loads(result_str)
        assert "answer" in result
        assert "usage" in result
        assert result["usage"]["requests"] >= 1

    @pytest.mark.asyncio
    async def test_agent_agentic_with_tool_call(self, test_db, seed_data):
        """Agent discovers tools and the LLM calls one."""
        from pydantic_ai.models.test import TestModel

        agent = AgentActor.get(seed_data["agent"].id)
        result_str = await agent.agentic(
            task="List all grants",
            llm=TestModel(call_tools=['grants_list']),
        )
        result = json.loads(result_str)
        assert "answer" in result
        assert result["usage"]["requests"] >= 1

    @pytest.mark.asyncio
    async def test_agent_agentic_sources_list(self, test_db, seed_data):
        """Agent can call sources_list to discover grant sources."""
        from pydantic_ai.models.test import TestModel

        agent = AgentActor.get(seed_data["agent"].id)
        result_str = await agent.agentic(
            task="What sources do we monitor?",
            llm=TestModel(call_tools=['sources_list']),
        )
        result = json.loads(result_str)
        assert "answer" in result
        assert len(result["messages"]) >= 2  # at least prompt + response

    @pytest.mark.asyncio
    async def test_agent_resolves_tool_hrefs(self, test_db, seed_data):
        """Agent resolves tool hrefs to actor addresses for discovery."""
        agent = AgentActor.get(seed_data["agent"].id)
        # After loading from DB, tools should be href strings
        assert isinstance(agent.tools, list)
        assert len(agent.tools) >= 3
        # _resolve_tool_addrs should resolve hrefs to addr strings
        addrs = agent.tool_addrs()
        assert 'grants' in addrs
        assert 'sources' in addrs
        assert 'web_tools' in addrs
