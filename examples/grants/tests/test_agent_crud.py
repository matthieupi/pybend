"""Tests for AgentActor CRUD in the grant-watching app."""
import pytest
from helpers import auth_header


class TestAgentCRUD:
    def test_list_agents(self, client, seed_data, alice_token):
        resp = client.get("/agents", headers=auth_header(alice_token))
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"] if isinstance(body, dict) else body
        assert len(data) >= 1

    def test_get_agent(self, client, seed_data, alice_token):
        agent = seed_data["agent"]
        resp = client.get(f"/agents/{agent.id}", headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Grant Scanner"
        # tools are hydrated from the agent's list[AgentTool] collection
        assert isinstance(data["tools"], list)
        assert len(data["tools"]) == 3

    def test_get_agent_tools_are_objects(self, client, seed_data, alice_token):
        """Tools field should contain hydrated tool objects."""
        agent = seed_data["agent"]
        resp = client.get(f"/agents/{agent.id}", headers=auth_header(alice_token))
        data = resp.json()
        for tool in data["tools"]:
            assert isinstance(tool, dict)
            assert "$id" in tool
            assert "target" in tool

    def test_create_agent_via_api(self, client, alice_token):
        resp = client.post("/agents", json={
            "name": "Quick Scanner",
            "prompt": "Scan for grants quickly.",
            "llm": "ollama:llama3.1",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Quick Scanner"

    def test_update_agent(self, client, seed_data, alice_token):
        agent = seed_data["agent"]
        resp = client.put(f"/agents/{agent.id}", json={
            "name": agent.name,
            "prompt": "Updated prompt for grant scanning.",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200
        assert "Updated prompt" in resp.json()["prompt"]

    def test_add_tool_via_join(self, client, seed_data, alice_token):
        """Add a tool to an agent via the nested join route."""
        agent = seed_data["agent"]
        resp = client.post(
            f"/agents/{agent.id}/tools",
            json={"target": "new_tool", "description": "A new tool"},
            headers=auth_header(alice_token),
        )
        # Should create successfully (201) via the join model route
        assert resp.status_code == 201
        data = resp.json()
        assert data["target"] == "new_tool"
