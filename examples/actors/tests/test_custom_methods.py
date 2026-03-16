# tests/test_custom_methods.py
"""
Test Plan Section 6: Custom Methods with @expose_route
Tests Product.comment(), Product.favorite(), Comment.like(), Comment.reply()
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration



class TestProductComment:
    """POST /products/{id}/comment -- add comment via custom method."""

    def test_comment_on_product_returns_200(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/products/{product.id}/comment", json={
            "comment": {
                "name": "Nice product!",
                "description": "Love this item",
            },
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_comment_auto_resolves_user(self, client, alice_token, seed_data):
        """user: User parameter should be auto-resolved from JWT."""
        product = seed_data["products"][1]
        alice = seed_data["users"]["alice"]
        resp = client.post(f"/products/{product.id}/comment", json={
            "comment": {
                "name": "User resolve test",
                "description": "Testing auto user resolution",
            },
        }, headers=auth_header(alice_token))
        data = resp.json()
        # Comment should have user_owner set to alice's ID
        user_owner = data.get("user_owner")
        if isinstance(user_owner, str) and "/" in user_owner:
            user_owner = int(user_owner.rstrip("/").rsplit("/", 1)[-1])
        assert user_owner == alice.id

    def test_comment_unauthenticated_returns_401(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/products/{product.id}/comment", json={
            "comment": {
                "name": "No auth",
                "description": "Should fail",
            },
        })
        assert resp.status_code == 401

    def test_comment_missing_comment_field_returns_400(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/products/{product.id}/comment", json={},
                           headers=auth_header(alice_token))
        assert resp.status_code == 400

    def test_comment_on_nonexistent_product_returns_404(self, client, alice_token):
        resp = client.post("/products/99999/comment", json={
            "comment": {
                "name": "Ghost",
                "description": "No product",
            },
        }, headers=auth_header(alice_token))
        assert resp.status_code == 404


class TestProductFavorite:
    """POST /products/{id}/favorite -- toggle favorite."""

    def test_favorite_first_call_returns_favorited(self, client, charlie_token, seed_data):
        """Use charlie who may not have favorited product 3 yet."""
        product = seed_data["products"][3]
        resp = client.post(f"/products/{product.id}/favorite", json={},
                           headers=auth_header(charlie_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "action" in data
        assert data["action"] in ("favorited", "unfavorited")

    def test_favorite_toggle_changes_action(self, client, charlie_token, seed_data):
        """Two consecutive calls should return opposite actions."""
        product = seed_data["products"][4]
        resp1 = client.post(f"/products/{product.id}/favorite", json={},
                            headers=auth_header(charlie_token))
        data1 = resp1.json()

        resp2 = client.post(f"/products/{product.id}/favorite", json={},
                            headers=auth_header(charlie_token))
        data2 = resp2.json()

        assert data1["action"] != data2["action"]

    def test_favorite_unauthenticated_returns_401(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/products/{product.id}/favorite", json={})
        assert resp.status_code == 401


class TestCommentLike:
    """POST /products/{pid}/comments/{cid}/like -- toggle like."""

    def test_like_comment_returns_action(self, client, alice_token, seed_data):
        product = seed_data["products"][1]
        comment = seed_data["comments"][3]  # comment on product 1
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/like",
                           json={}, headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "action" in data
        assert data["action"] in ("liked", "unliked")

    def test_like_toggle(self, client, bob_token, seed_data):
        """Two consecutive likes should toggle."""
        product = seed_data["products"][1]
        comment = seed_data["comments"][3]

        resp1 = client.post(f"/products/{product.id}/comments/{comment.id}/like",
                            json={}, headers=auth_header(bob_token))
        data1 = resp1.json()

        resp2 = client.post(f"/products/{product.id}/comments/{comment.id}/like",
                            json={}, headers=auth_header(bob_token))
        data2 = resp2.json()

        assert data1["action"] != data2["action"]

    def test_like_unauthenticated_returns_401(self, client, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/like", json={})
        assert resp.status_code == 401


class TestCommentReply:
    """POST /products/{pid}/comments/{cid}/reply -- reply to comment."""

    def test_reply_returns_created_comment(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/reply",
                           json={"text": "Great point!"},
                           headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("name") == "Great point!"

    def test_reply_has_parent_id(self, client, bob_token, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][1]
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/reply",
                           json={"text": "Reply with parent_id"},
                           headers=auth_header(bob_token))
        data = resp.json()
        assert data.get("parent_id") == comment.id

    def test_reply_has_user_owner(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        alice = seed_data["users"]["alice"]
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/reply",
                           json={"text": "Reply owner test"},
                           headers=auth_header(alice_token))
        data = resp.json()
        user_owner = data.get("user_owner")
        if isinstance(user_owner, str) and "/" in user_owner:
            user_owner = int(user_owner.rstrip("/").rsplit("/", 1)[-1])
        assert user_owner == alice.id

    def test_reply_has_nonzero_id(self, client, charlie_token, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/reply",
                           json={"text": "ID check reply"},
                           headers=auth_header(charlie_token))
        data = resp.json()
        assert data.get("id", 0) > 0

    def test_reply_unauthenticated_returns_401(self, client, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/reply",
                           json={"text": "No auth"})
        assert resp.status_code == 401


class TestCustomMethodPersistence:
    """IT-11: Verify custom method side effects are actually persisted."""

    def test_comment_method_creates_persisted_record(self, client, alice_token, seed_data):
        """After calling /comment, the comment should appear in the product's comments.
        Note: The custom method returns model_dump_json of the pre-save object
        (id=0), so we verify persistence by listing the product's comments."""
        product = seed_data["products"][2]
        # Get before count
        before = client.get(f"/products/{product.id}/comments?limit=100")
        before_items = before.json().get("data", []) if "data" in before.json() else before.json()
        before_count = len(before_items)

        resp = client.post(f"/products/{product.id}/comment", json={
            "comment": {
                "name": "Persist check",
                "description": "Verify this is stored",
            },
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200

        # Verify a new comment was created
        after = client.get(f"/products/{product.id}/comments?limit=100")
        after_items = after.json().get("data", []) if "data" in after.json() else after.json()
        assert len(after_items) == before_count + 1
        # Find the new comment
        new_comments = [c for c in after_items if c["name"] == "Persist check"]
        assert len(new_comments) == 1

    def test_reply_method_creates_persisted_record(self, client, alice_token, seed_data):
        """After calling /reply, the reply should be fetchable."""
        product = seed_data["products"][0]
        comment = seed_data["comments"][1]
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/reply",
                           json={"text": "Persist reply"},
                           headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        reply_id = data.get("id")
        assert reply_id is not None

        get_resp = client.get(f"/products/{product.id}/comments/{reply_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["parent_id"] == comment.id

    def test_like_method_persists_like_record(self, client, bob_token, seed_data):
        """After calling /like, the like count should change."""
        product = seed_data["products"][2]
        comment = seed_data["comments"][4]

        before = client.get(f"/products/{product.id}/comments/{comment.id}")
        before_likes = len(before.json().get("likes", []))

        resp = client.post(f"/products/{product.id}/comments/{comment.id}/like",
                           json={}, headers=auth_header(bob_token))
        assert resp.status_code == 200
        data = resp.json()
        action = data["action"]

        after = client.get(f"/products/{product.id}/comments/{comment.id}")
        after_likes = len(after.json().get("likes", []))

        if action == "liked":
            assert after_likes == before_likes + 1
        else:
            assert after_likes == before_likes - 1


class TestCustomMethodNegativeCases:
    """SD-5: Negative authorization tests for custom methods."""

    def test_anonymous_comment_returns_401(self, client, seed_data):
        """Anonymous user gets 401 on custom method."""
        product = seed_data["products"][0]
        resp = client.post(f"/products/{product.id}/comment", json={
            "comment": {"name": "Anon", "description": "test"},
        })
        assert resp.status_code == 401

    def test_anonymous_favorite_returns_401(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/products/{product.id}/favorite", json={})
        assert resp.status_code == 401

    def test_anonymous_like_returns_401(self, client, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/like",
                           json={})
        assert resp.status_code == 401

    def test_anonymous_reply_returns_401(self, client, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.post(f"/products/{product.id}/comments/{comment.id}/reply",
                           json={"text": "nope"})
        assert resp.status_code == 401

    def test_custom_method_on_nonexistent_entity_returns_404(self, client, alice_token):
        resp = client.post("/products/99999/comment", json={
            "comment": {"name": "Ghost", "description": "test"},
        }, headers=auth_header(alice_token))
        assert resp.status_code == 404

    def test_comment_missing_required_field_returns_400(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/products/{product.id}/comment", json={},
                           headers=auth_header(alice_token))
        assert resp.status_code == 400
