"""Tests for schema endpoints in the chat app."""
import pytest


class TestSchemaEndpoints:
    def test_conversation_schema(self, client, seed_data):
        resp = client.get("/Conversation")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "Conversation"
        assert schema["__tablename__"] == "conversations"
        props = schema["properties"]
        assert "name" in props
        assert "prompt" in props
        assert "llm" in props
        assert "messages" in props

    def test_conversation_has_agent_section(self, client, seed_data):
        resp = client.get("/Conversation")
        schema = resp.json()
        assert "agent" in schema
        assert schema["agent"]["enabled"] is True

    def test_message_schema(self, client, seed_data):
        resp = client.get("/Message")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "Message"
        props = schema["properties"]
        assert "kind" in props
        assert "parts" in props
        assert "content" in props
        assert "role" in props

    def test_user_schema(self, client, seed_data):
        resp = client.get("/User")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "User"
