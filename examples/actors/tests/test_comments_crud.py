# tests/test_comments_crud.py
"""
Test Plan Section 4: Full CRUD lifecycle for comments.

Comments are first-class flat entities. Product-owned comment creation uses the
Product.comment custom method so the product's ordered ``comments: list[Comment]``
field is updated through the model API.
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration


def _user_id(value):
    if isinstance(value, str) and "/" in value:
        return int(value.rstrip("/").rsplit("/", 1)[-1])
    return value


def _product_comments(client, product_id, token=None):
    headers = auth_header(token) if token else {}
    resp = client.get(f"/Product/{product_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json().get("comments", [])


class TestCreateComment:
    """POST /Product/{id}/comment -- create and attach comment."""

    def test_create_comment_authenticated_returns_200(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/comment", json={
            "comment": {
                "name": "Test comment",
                "description": "A test comment description",
            },
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_create_comment_attaches_to_product_comments(self, client, alice_token, seed_data):
        product = seed_data["products"][1]
        resp = client.post(f"/Product/{product.id}/comment", json={
            "comment": {
                "name": "Attach test",
                "description": "Testing list[T] update",
            },
        }, headers=auth_header(alice_token))
        data = resp.json()
        comments = _product_comments(client, product.id, alice_token)
        assert any(comment["id"] == data["id"] for comment in comments)

    def test_create_comment_user_owner_auto_injected(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        alice = seed_data["users"]["alice"]
        resp = client.post(f"/Product/{product.id}/comment", json={
            "comment": {
                "name": "Owner test",
                "description": "Testing user_owner injection",
                "user_owner": 999,
            },
        }, headers=auth_header(alice_token))
        assert _user_id(resp.json().get("user_owner")) == alice.id

    def test_create_comment_parent_id_is_null(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/comment", json={
            "comment": {
                "name": "No parent",
                "description": "Top-level comment",
            },
        }, headers=auth_header(alice_token))
        assert resp.json().get("parent_id") is None

    def test_create_comment_unauthenticated_returns_401(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/comment", json={
            "comment": {
                "name": "No auth",
                "description": "Should fail",
            },
        })
        assert resp.status_code == 401


class TestReadComment:
    """GET /Comment/{id} -- read single comment."""

    def test_read_comment_returns_200(self, client, seed_data):
        comment = seed_data["comments"][0]
        resp = client.get(f"/Comment/{comment.id}")
        assert resp.status_code == 200

    def test_read_comment_has_schema_metadata(self, client, seed_data):
        comment = seed_data["comments"][0]
        data = client.get(f"/Comment/{comment.id}").json()
        assert data["$schema"].endswith("/Comment")
        assert data["$id"].endswith(f"/Comment/{comment.id}")

    def test_read_comment_has_user_owner(self, client, seed_data):
        comment = seed_data["comments"][0]
        data = client.get(f"/Comment/{comment.id}").json()
        assert "user_owner" in data

    def test_read_comment_has_likes_field(self, client, seed_data):
        comment = seed_data["comments"][0]
        data = client.get(f"/Comment/{comment.id}").json()
        assert isinstance(data["likes"], list)

    def test_read_comment_not_found_returns_404(self, client):
        resp = client.get("/Comment/99999")
        assert resp.status_code == 404

    def test_read_comment_no_auth_required(self, client, seed_data):
        comment = seed_data["comments"][0]
        resp = client.get(f"/Comment/{comment.id}")
        assert resp.status_code == 200


class TestListComments:
    """Product comment membership is exposed through Product.comments."""

    def test_list_comments_returns_product_comments(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        comments = _product_comments(client, product.id, alice_token)
        assert len(comments) >= 2
        assert all(comment["$id"].endswith(f"/Comment/{comment['id']}") for comment in comments)

    def test_comment_collection_endpoint_is_flat_and_paginated(self, client, alice_token):
        resp = client.get("/Comment/_?limit=1", headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_list_comments_for_nonexistent_product_returns_404(self, client, alice_token):
        resp = client.get("/Product/99999", headers=auth_header(alice_token))
        assert resp.status_code == 404


class TestUpdateComment:
    """PUT /Comment/{id} -- update comment."""

    def test_update_comment_as_owner_returns_200(self, client, bob_token, seed_data):
        comment = seed_data["comments"][0]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Updated by owner",
        }, headers=auth_header(bob_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated by owner"

    def test_update_comment_user_owner_not_modified(self, client, bob_token, seed_data):
        comment = seed_data["comments"][0]
        bob = seed_data["users"]["bob"]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Protected test",
            "user_owner": 999,
        }, headers=auth_header(bob_token))
        assert _user_id(resp.json().get("user_owner")) == bob.id

    def test_update_comment_as_non_owner_non_admin_returns_403(self, client, alice_token, seed_data):
        comment = seed_data["comments"][0]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Should fail",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 403

    def test_update_comment_as_admin_returns_200(self, client, admin_token, seed_data):
        comment = seed_data["comments"][0]
        resp = client.put(f"/Comment/{comment.id}", json={
            "name": "Updated by admin",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200


class TestDeleteComment:
    """DELETE /Comment/{id} -- delete comment."""

    def test_delete_comment_as_owner_returns_200(self, client, alice_token, seed_data):
        product = seed_data["products"][2]
        create_resp = client.post(f"/Product/{product.id}/comment", json={
            "comment": {
                "name": "To delete",
                "description": "Will be deleted",
            },
        }, headers=auth_header(alice_token))
        comment_id = create_resp.json()["id"]

        resp = client.delete(f"/Comment/{comment_id}", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_delete_comment_as_non_owner_non_admin_returns_403(self, client, bob_token, alice_token, seed_data):
        product = seed_data["products"][2]
        create_resp = client.post(f"/Product/{product.id}/comment", json={
            "comment": {
                "name": "Alice's comment",
                "description": "Only alice can delete",
            },
        }, headers=auth_header(alice_token))
        comment_id = create_resp.json()["id"]

        resp = client.delete(f"/Comment/{comment_id}", headers=auth_header(bob_token))
        assert resp.status_code == 403
