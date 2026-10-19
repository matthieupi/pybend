"""Tests for schema endpoints in the grant-watching app."""
import pytest


class TestSchemaEndpoints:
    def test_grant_schema(self, client, seed_data):
        resp = client.get("/Grant")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "Grant"
        assert schema["__tablename__"] == "grants"
        props = schema["properties"]
        assert "title" in props
        assert "agency" in props
        assert "url" in props
        assert "status" in props

    def test_source_schema(self, client, seed_data):
        resp = client.get("/Source")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "Source"
        assert "name" in schema["properties"]
        assert "url" in schema["properties"]
        assert "category" in schema["properties"]

    def test_agent_schema(self, client, seed_data):
        resp = client.get("/AgentActor")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "AgentActor"
        assert schema["ui"]["renderer"]["item"] == "ntx-agent"
        assert schema["ui"]["renderer"]["detail"] == "ntx-agent"
        assert "agent" in schema
        assert schema["agent"]["enabled"] is True
        assert "agentic" in schema.get("methods", {})

    def test_web_tools_schema(self, client, seed_data):
        resp = client.get("/WebTools")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "WebTools"
        methods = schema.get("methods", {})
        assert "scrape" in methods
        assert "extract" in methods
