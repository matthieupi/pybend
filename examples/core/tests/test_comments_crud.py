# tests/test_comments_crud.py
"""
Test Plan Section 4: Full CRUD Lifecycle for Comments (nested under Products)
Comments are stored as ProductComment join models.
Routes: /Product/{parent_id}/Comment/...
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration



class TestCreateComment:
    """POST /Product/{parent_id}/Comment -- create comment."""

    def test_create_comment_authenticated_returns_201(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/Comment", json={
            "name": "Test comment",
            "description": "A test comment description",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201

    def test_create_comment_has_product_id_fk(self, client, alice_token, seed_data):
        product = seed_data["products"][1]
        resp = client.post(f"/Product/{product.id}/Comment", json={
            "name": "FK test",
            "description": "Testing FK injection",
        }, headers=auth_header(alice_token))
        data = resp.json()
        assert data.get("product_id") == product.id

    def test_create_comment_user_owner_auto_injected(self, client, alice_token, seed_data):
        """user_owner should be auto-injected from JWT, not from request body."""
        product = seed_data["products"][0]
        alice = seed_data["users"]["alice"]
        resp = client.post(f"/Product/{product.id}/Comment", json={
            "name": "Owner test",
            "description": "Testing user_owner injection",
            "user_owner": 999,  # Should be ignored/overwritten
        }, headers=auth_header(alice_token))
        data = resp.json()
        # user_owner should be alice's ID (from JWT), not 999
        user_owner_val = data.get("user_owner")
        if isinstance(user_owner_val, str) and "/" in user_owner_val:
            # It's an href, extract the ID
            user_owner_id = int(user_owner_val.rstrip("/").rsplit("/", 1)[-1])
        else:
            user_owner_id = user_owner_val
        assert user_owner_id == alice.id

    def test_create_comment_parent_id_is_null(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/Comment", json={
            "name": "No parent",
            "description": "Top-level comment",
        }, headers=auth_header(alice_token))
        data = resp.json()
        assert data.get("parent_id") is None

    def test_create_comment_unauthenticated_returns_403(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/Comment", json={
            "name": "No auth",
            "description": "Should fail",
        })
        assert resp.status_code == 403


class TestReadComment:
    """GET /Product/{parent_id}/Comment/{id} -- read single comment."""

    def test_read_comment_returns_200(self, client, seed_data):
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{comment.id}")
        assert resp.status_code == 200

    def test_read_comment_has_schema_metadata(self, client, seed_data):
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{comment.id}")
        data = resp.json()
        assert "$schema" in data
        assert "$id" in data

    def test_read_comment_has_user_owner(self, client, seed_data):
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{comment.id}")
        data = resp.json()
        assert "user_owner" in data

    def test_read_comment_has_likes_field(self, client, seed_data):
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{comment.id}")
        data = resp.json()
        assert "likes" in data
        assert isinstance(data["likes"], list)

    def test_read_comment_not_found_returns_404(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment/99999")
        assert resp.status_code == 404

    def test_read_comment_no_auth_required(self, client, seed_data):
        """Comment read access is ANYONE."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{comment.id}")
        assert resp.status_code == 200


class TestListComments:
    """GET /Product/{parent_id}/Comment -- list comments for product."""

    def test_list_comments_returns_200(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment")
        assert resp.status_code == 200

    def test_list_comments_only_for_product(self, client, seed_data):
        """Should only return comments for the specified product."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment")
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        assert len(items) >= 2  # product 0 has at least 2 comments from seed

    def test_list_comments_paginated(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment?limit=1")
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_list_comments_for_nonexistent_product(self, client):
        resp = client.get("/Product/99999/Comment")
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        # Should return empty rather than error
        assert len(items) == 0


class TestUpdateComment:
    """PUT /Product/{parent_id}/Comment/{id} -- update comment."""

    def test_update_comment_as_owner_returns_200(self, client, bob_token, seed_data):
        """Comment 0 was created by bob. Bob should be able to update it."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.put(f"/Product/{product.id}/Comment/{comment.id}", json={
            "name": "Updated by owner",
        }, headers=auth_header(bob_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated by owner"

    def test_update_comment_user_owner_not_modified(self, client, bob_token, seed_data):
        """Protected field user_owner should NOT be updated even if sent in body."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        bob = seed_data["users"]["bob"]
        resp = client.put(f"/Product/{product.id}/Comment/{comment.id}", json={
            "name": "Protected test",
            "user_owner": 999,  # Should be stripped
        }, headers=auth_header(bob_token))
        data = resp.json()
        # user_owner should still be bob's ID
        user_owner_val = data.get("user_owner")
        if isinstance(user_owner_val, str) and "/" in user_owner_val:
            user_owner_id = int(user_owner_val.rstrip("/").rsplit("/", 1)[-1])
        else:
            user_owner_id = user_owner_val
        assert user_owner_id == bob.id

    def test_update_comment_as_non_owner_non_admin_returns_403(self, client, alice_token, seed_data):
        """Comment 0 was created by bob. Alice (non-owner, non-admin) should be denied."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.put(f"/Product/{product.id}/Comment/{comment.id}", json={
            "name": "Should fail",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 403

    def test_update_comment_as_admin_returns_200(self, client, admin_token, seed_data):
        """Admin should be able to update any comment."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.put(f"/Product/{product.id}/Comment/{comment.id}", json={
            "name": "Updated by admin",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200


class TestDeleteComment:
    """DELETE /Product/{parent_id}/Comment/{id} -- delete comment."""

    def test_delete_comment_as_owner_returns_200(self, client, alice_token, seed_data):
        """Create a comment as alice, then delete it as alice."""
        product = seed_data["products"][2]
        # Create comment
        create_resp = client.post(f"/Product/{product.id}/Comment", json={
            "name": "To delete",
            "description": "Will be deleted",
        }, headers=auth_header(alice_token))
        comment_id = create_resp.json()["id"]

        resp = client.delete(f"/Product/{product.id}/Comment/{comment_id}",
                             headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_delete_comment_as_non_owner_non_admin_returns_403(self, client, bob_token, alice_token, seed_data):
        """Comment created by alice cannot be deleted by bob."""
        product = seed_data["products"][2]
        # Create comment as alice
        create_resp = client.post(f"/Product/{product.id}/Comment", json={
            "name": "Alice's comment",
            "description": "Only alice can delete",
        }, headers=auth_header(alice_token))
        comment_id = create_resp.json()["id"]

        resp = client.delete(f"/Product/{product.id}/Comment/{comment_id}",
                             headers=auth_header(bob_token))
        assert resp.status_code == 403
