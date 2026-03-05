"""Tests for Conversation CRUD operations."""
import pytest
from helpers import auth_header


class TestConversationCRUD:
    def test_create_conversation(self, client, alice_token, seed_data):
        resp = client.post(
            "/conversations",
            json={"name": "New Chat", "prompt": "Be concise."},
            headers=auth_header(alice_token),
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["name"] == "New Chat"
        assert data["prompt"] == "Be concise."
        assert "id" in data

    def test_create_requires_auth(self, client, seed_data):
        resp = client.post(
            "/conversations",
            json={"name": "No Auth Chat"},
        )
        assert resp.status_code in (401, 403)

    def test_list_conversations(self, client, alice_token, seed_data):
        resp = client.get(
            "/conversations",
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("data", data) if isinstance(data, dict) else data
        assert len(items) >= 1

    def test_get_conversation(self, client, alice_token, seed_data):
        conv = seed_data["conversations"][0]
        resp = client.get(
            f"/conversations/{conv.id}",
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == conv.name

    def test_owner_only_read(self, client, bob_token, seed_data):
        """Bob cannot read Alice's conversation."""
        alice_conv = seed_data["conversations"][0]
        resp = client.get(
            f"/conversations/{alice_conv.id}",
            headers=auth_header(bob_token),
        )
        assert resp.status_code == 403

    def test_update_conversation(self, client, alice_token, seed_data):
        conv = seed_data["conversations"][0]
        resp = client.put(
            f"/conversations/{conv.id}",
            json={"name": "Updated Title"},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Title"

    def test_update_denied_non_owner(self, client, bob_token, seed_data):
        alice_conv = seed_data["conversations"][0]
        resp = client.put(
            f"/conversations/{alice_conv.id}",
            json={"name": "Hacked"},
            headers=auth_header(bob_token),
        )
        assert resp.status_code == 403
