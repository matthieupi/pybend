# tests/test_authorization.py
"""
Test Plan Section 7: Authorization & Access Control
Tests ANYONE, AUTHENTICATED, OWNER, ROLE, composite rules, SQL pushdown.
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration


def _create_comment(client, token, product_id, name="Auth comment", description="Auth test"):
    resp = client.post(f"/Product/{product_id}/comment", json={
        "comment": {"name": name, "description": description},
    }, headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestAnyoneRule:
    """ANYONE rule -- no authentication required."""

    def test_schema_endpoint_no_auth_needed(self, client):
        resp = client.get("/Product")
        assert resp.status_code == 200

    def test_comment_read_anyone_no_auth(self, client, seed_data):
        """Comment __access__.read = ANYONE."""
        comment = seed_data["comments"][0]
        resp = client.get(f"/Comment/{comment.id}")
        assert resp.status_code == 200

    def test_comment_list_anyone_no_auth(self, client, seed_data):
        """Comment list should also work without auth (ANYONE for read/list)."""
        resp = client.get("/Comment/_?limit=100")
        assert resp.status_code == 200


class TestAuthenticatedRule:
    """AUTHENTICATED rule -- requires valid JWT."""

    def test_create_product_no_token_401(self, client):
        resp = client.post("/Product", json={
            "name": "Fail", "price": 10.00,
        })
        assert resp.status_code == 401

    def test_create_product_with_token_201(self, client, alice_token):
        resp = client.post("/Product", json={
            "name": "Auth OK", "price": 10.00,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201

    def test_create_comment_no_token_401(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/comment", json={
            "comment": {"name": "No auth", "description": "Should fail"},
        })
        assert resp.status_code == 401

    def test_create_comment_with_token_201(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/comment", json={
            "comment": {"name": "Auth OK", "description": "Should pass"},
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200


class TestOwnerRule:
    """OWNER rule -- resource.user_owner must match JWT user_id."""

    def test_owner_can_update_own_comment(self, client, bob_token, seed_data):
        """Comment 0 was created by bob. Owner can update."""
        comment = seed_data["comments"][0]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Owner update",
        }, headers=auth_header(bob_token))
        assert resp.status_code == 200

    def test_non_owner_cannot_update_comment(self, client, charlie_token, seed_data):
        """Comment 0 was created by bob. Charlie is not owner."""
        comment = seed_data["comments"][0]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Not my comment",
        }, headers=auth_header(charlie_token))
        assert resp.status_code == 403

    def test_owner_can_delete_own_comment(self, client, alice_token, seed_data):
        """Create then delete own comment."""
        product = seed_data["products"][3]
        comment = _create_comment(client, alice_token, product.id, name="Delete me")

        resp = client.delete(f"/Comment/{comment['id']}", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_non_owner_cannot_delete_comment(self, client, alice_token, bob_token, seed_data):
        """Create as alice, bob cannot delete."""
        product = seed_data["products"][3]
        comment = _create_comment(client, alice_token, product.id, name="Alice only")

        resp = client.delete(f"/Comment/{comment['id']}", headers=auth_header(bob_token))
        assert resp.status_code == 403


class TestRoleRule:
    """ROLE rule -- user.role must match."""

    def test_admin_can_update_any_comment(self, client, admin_token, seed_data):
        """Admin has ROLE('admin'), which is part of OWNER | ROLE('admin')."""
        comment = seed_data["comments"][2]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Admin override",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200

    def test_admin_can_delete_any_comment(self, client, admin_token, alice_token, seed_data):
        """Admin should be able to delete any comment."""
        product = seed_data["products"][3]
        comment = _create_comment(client, alice_token, product.id, name="Admin deletable")

        resp = client.delete(f"/Comment/{comment['id']}", headers=auth_header(admin_token))
        assert resp.status_code == 200


class TestCompositeOrRule:
    """OWNER | ROLE('admin') -- passes if either condition is true."""

    def test_owner_passes_or_rule(self, client, bob_token, seed_data):
        """Bob owns comment 0. OWNER | ROLE('admin') should pass for bob."""
        comment = seed_data["comments"][0]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Or rule owner",
        }, headers=auth_header(bob_token))
        assert resp.status_code == 200

    def test_admin_passes_or_rule(self, client, admin_token, seed_data):
        """Admin passes via ROLE('admin') even though not owner."""
        comment = seed_data["comments"][0]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Or rule admin",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200

    def test_non_owner_non_admin_fails_or_rule(self, client, charlie_token, seed_data):
        """Charlie is neither owner nor admin. Should fail."""
        comment = seed_data["comments"][0]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Or rule fail",
        }, headers=auth_header(charlie_token))
        assert resp.status_code == 403


class TestSQLPushdownForLists:
    """IT-5: Verify SQL pushdown filters list results based on access rules."""

    def test_product_list_returns_all_for_authenticated(self, client, alice_token, seed_data):
        """Products default to AUTHENTICATED for read — all returned for any user."""
        resp = client.get("/Product/_?limit=100", headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["total"] >= 5

    def test_comment_list_returns_all_for_anyone(self, client, seed_data):
        """Comments have read=ANYONE — list should work without auth."""
        resp = client.get("/Comment/_?limit=100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["total"] >= 8


# IT-8: TestProtectedFieldsAuthorization moved to test_protected_fields.py
# (the dedicated file provides more comprehensive coverage)
