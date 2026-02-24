# tests/test_authorization.py
"""
Test Plan Section 7: Authorization & Access Control
Tests ANYONE, AUTHENTICATED, OWNER, ROLE, composite rules, SQL pushdown.
"""

import pytest
from tests.helpers import auth_header


class TestAnyoneRule:
    """ANYONE rule -- no authentication required."""

    def test_schema_endpoint_no_auth_needed(self, client):
        resp = client.get("/Product")
        assert resp.status_code == 200

    def test_comment_read_anyone_no_auth(self, client, seed_data):
        """Comment __access__.read = ANYONE."""
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/products/{product.id}/comments/{comment.id}")
        assert resp.status_code == 200

    def test_comment_list_anyone_no_auth(self, client, seed_data):
        """Comment list should also work without auth (ANYONE for read/list)."""
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}/comments")
        assert resp.status_code == 200


class TestAuthenticatedRule:
    """AUTHENTICATED rule -- requires valid JWT."""

    def test_create_product_no_token_403(self, client):
        resp = client.post("/products", json={
            "name": "Fail", "price": 10.00,
        })
        assert resp.status_code == 403

    def test_create_product_with_token_201(self, client, alice_token):
        resp = client.post("/products", json={
            "name": "Auth OK", "price": 10.00,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201

    def test_create_comment_no_token_403(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/products/{product.id}/comments", json={
            "name": "No auth", "description": "Should fail",
        })
        assert resp.status_code == 403

    def test_create_comment_with_token_201(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/products/{product.id}/comments", json={
            "name": "Auth OK", "description": "Should pass",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201


class TestOwnerRule:
    """OWNER rule -- resource.user_owner must match JWT user_id."""

    def test_owner_can_update_own_comment(self, client, bob_token, seed_data):
        """Comment 0 was created by bob. Owner can update."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.put(f"/products/{product.id}/comments/{comment.id}", json={
            "name": "Owner update",
        }, headers=auth_header(bob_token))
        assert resp.status_code == 200

    def test_non_owner_cannot_update_comment(self, client, charlie_token, seed_data):
        """Comment 0 was created by bob. Charlie is not owner."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.put(f"/products/{product.id}/comments/{comment.id}", json={
            "name": "Not my comment",
        }, headers=auth_header(charlie_token))
        assert resp.status_code == 403

    def test_owner_can_delete_own_comment(self, client, alice_token, seed_data):
        """Create then delete own comment."""
        product = seed_data["products"][3]
        create_resp = client.post(f"/products/{product.id}/comments", json={
            "name": "Delete me", "description": "Owner delete test",
        }, headers=auth_header(alice_token))
        comment_id = create_resp.json()["id"]

        resp = client.delete(f"/products/{product.id}/comments/{comment_id}",
                             headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_non_owner_cannot_delete_comment(self, client, alice_token, bob_token, seed_data):
        """Create as alice, bob cannot delete."""
        product = seed_data["products"][3]
        create_resp = client.post(f"/products/{product.id}/comments", json={
            "name": "Alice only", "description": "Bob can't delete",
        }, headers=auth_header(alice_token))
        comment_id = create_resp.json()["id"]

        resp = client.delete(f"/products/{product.id}/comments/{comment_id}",
                             headers=auth_header(bob_token))
        assert resp.status_code == 403


class TestRoleRule:
    """ROLE rule -- user.role must match."""

    def test_admin_can_update_any_comment(self, client, admin_token, seed_data):
        """Admin has ROLE('admin'), which is part of OWNER | ROLE('admin')."""
        comment = seed_data["comments"][2]
        product = seed_data["products"][1]
        resp = client.put(f"/products/{product.id}/comments/{comment.id}", json={
            "name": "Admin override",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200

    def test_admin_can_delete_any_comment(self, client, admin_token, alice_token, seed_data):
        """Admin should be able to delete any comment."""
        product = seed_data["products"][3]
        create_resp = client.post(f"/products/{product.id}/comments", json={
            "name": "Admin deletable", "description": "admin test",
        }, headers=auth_header(alice_token))
        comment_id = create_resp.json()["id"]

        resp = client.delete(f"/products/{product.id}/comments/{comment_id}",
                             headers=auth_header(admin_token))
        assert resp.status_code == 200


class TestCompositeOrRule:
    """OWNER | ROLE('admin') -- passes if either condition is true."""

    def test_owner_passes_or_rule(self, client, bob_token, seed_data):
        """Bob owns comment 0. OWNER | ROLE('admin') should pass for bob."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.put(f"/products/{product.id}/comments/{comment.id}", json={
            "name": "Or rule owner",
        }, headers=auth_header(bob_token))
        assert resp.status_code == 200

    def test_admin_passes_or_rule(self, client, admin_token, seed_data):
        """Admin passes via ROLE('admin') even though not owner."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.put(f"/products/{product.id}/comments/{comment.id}", json={
            "name": "Or rule admin",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200

    def test_non_owner_non_admin_fails_or_rule(self, client, charlie_token, seed_data):
        """Charlie is neither owner nor admin. Should fail."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.put(f"/products/{product.id}/comments/{comment.id}", json={
            "name": "Or rule fail",
        }, headers=auth_header(charlie_token))
        assert resp.status_code == 403


class TestProtectedFieldsAuthorization:
    """Protected fields are auto-injected on create and stripped on update."""

    def test_user_owner_auto_injected_on_create(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        alice = seed_data["users"]["alice"]
        resp = client.post(f"/products/{product.id}/comments", json={
            "name": "Protected test", "description": "Test",
        }, headers=auth_header(alice_token))
        data = resp.json()
        user_owner = data.get("user_owner")
        if isinstance(user_owner, str) and "/" in user_owner:
            user_owner = int(user_owner.rstrip("/").rsplit("/", 1)[-1])
        assert user_owner == alice.id

    def test_user_owner_stripped_on_update(self, client, bob_token, seed_data):
        """Sending user_owner in update body should be ignored."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        bob = seed_data["users"]["bob"]
        resp = client.put(f"/products/{product.id}/comments/{comment.id}", json={
            "name": "Strip test",
            "user_owner": 999,  # Should be stripped
        }, headers=auth_header(bob_token))
        data = resp.json()
        user_owner = data.get("user_owner")
        if isinstance(user_owner, str) and "/" in user_owner:
            user_owner = int(user_owner.rstrip("/").rsplit("/", 1)[-1])
        assert user_owner == bob.id

    def test_protected_field_marked_in_schema(self, client):
        """Comment is registered as ProductComment join model."""
        schema = client.get("/ProductComment").json()
        user_owner_prop = schema["properties"]["user_owner"]
        assert user_owner_prop.get("ui", {}).get("protected") is True
