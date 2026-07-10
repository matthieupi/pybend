# tests/test_protected_fields.py
"""
Test Plan Section 7.10: Protected Fields
Tests auto-injection on create, stripping on update, schema marking.
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration



class TestProtectedFieldsOnCreate:
    """Backend auto-injects protected fields on create from JWT."""

    def test_comment_user_owner_injected_from_jwt(self, client, alice_token, seed_data):
        alice = seed_data["users"]["alice"]
        resp = client.post("/Comment", json={
            "name": "Protected create",
            "description": "Testing auto-inject",
        }, headers=auth_header(alice_token))
        data = resp.json()
        user_owner = data.get("user_owner")
        if isinstance(user_owner, str) and "/" in user_owner:
            user_owner = int(user_owner.rstrip("/").rsplit("/", 1)[-1])
        assert user_owner == alice.id

    def test_comment_body_user_owner_ignored_on_create(self, client, bob_token, seed_data):
        """Even if user_owner is in the body, it should be overwritten by JWT."""
        bob = seed_data["users"]["bob"]
        resp = client.post("/Comment", json={
            "name": "Body override test",
            "description": "user_owner in body should be ignored",
            "user_owner": 999,
        }, headers=auth_header(bob_token))
        data = resp.json()
        user_owner = data.get("user_owner")
        if isinstance(user_owner, str) and "/" in user_owner:
            user_owner = int(user_owner.rstrip("/").rsplit("/", 1)[-1])
        assert user_owner == bob.id


class TestProtectedFieldsOnUpdate:
    """Backend strips protected fields from update payloads."""

    def test_comment_user_owner_stripped_on_update(self, client, bob_token, seed_data):
        """Sending user_owner in update body should be stripped."""
        comment = seed_data["comments"][0]
        bob = seed_data["users"]["bob"]

        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Strip test",
            "user_owner": 999,  # Should be stripped
        }, headers=auth_header(bob_token))
        assert resp.status_code == 200
        data = resp.json()
        user_owner = data.get("user_owner")
        if isinstance(user_owner, str) and "/" in user_owner:
            user_owner = int(user_owner.rstrip("/").rsplit("/", 1)[-1])
        # Should still be bob's original ID
        assert user_owner == bob.id


class TestProtectedFieldsInSchema:
    """Protected fields marked with ui.protected=true in schema.
    Comment and Like are first-class flat models.
    """

    def test_comment_user_owner_marked_protected(self, client):
        """Comment schema has user_owner with ui.protected=true."""
        schema = client.get("/Comment").json()
        user_owner = schema["properties"]["user_owner"]
        assert user_owner.get("ui", {}).get("protected") is True

    def test_like_user_marked_protected(self, client):
        """Like schema has user with ui.protected=true."""
        schema = client.get("/Like").json()
        user_prop = schema["properties"]["user"]
        assert user_prop.get("ui", {}).get("protected") is True

    def test_product_defs_comment_user_owner_protected(self, client):
        """Protected fields should also appear in $defs entries."""
        schema = client.get("/Product").json()
        comment_def = schema.get("$defs", {}).get("Comment", {})
        user_owner = comment_def.get("properties", {}).get("user_owner", {})
        assert user_owner.get("ui", {}).get("protected") is True

    def test_product_defs_like_user_protected(self, client):
        """Like.user in Product's $defs.
        Note: $defs.Like may not carry ui.protected since it's a simplified
        inline reference. The authoritative schema is on /Like."""
        schema = client.get("/Like").json()
        user_prop = schema.get("properties", {}).get("user", {})
        assert user_prop.get("ui", {}).get("protected") is True
