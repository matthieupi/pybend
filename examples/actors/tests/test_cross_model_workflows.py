# tests/test_cross_model_workflows.py
"""
Test Plan Section 11: Cross-Model Workflows
End-to-end lifecycle tests spanning multiple models.
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration


def _create_product_comment(client, token, product_id, *, name, description):
    resp = client.post(f"/Product/{product_id}/comment", json={
        "comment": {"name": name, "description": description},
    }, headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestCompleteProductLifecycle:
    """Full lifecycle: Create -> Read -> Comment -> Like -> Reply -> Favorite -> Delete.

    IT-2: Split mega-test into discrete test methods with shared state via
    class-scoped fixture-like pattern using a dict on the class.
    """

    _state = {}

    def test_01_create_product(self, client, alice_token, seed_data):
        resp = client.post("/Product", json={
            "name": "Lifecycle Product",
            "price": 49.99,
            "description": "Full lifecycle test",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
        product = resp.json()
        assert product["name"] == "Lifecycle Product"
        self.__class__._state["product_id"] = product["id"]

    def test_02_new_product_has_empty_refs(self, client, alice_token):
        pid = self.__class__._state["product_id"]
        resp = client.get(f"/Product/{pid}", headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["comments"] == []
        assert data["favorites"] == []

    def test_03_add_comment(self, client, bob_token):
        pid = self.__class__._state["product_id"]
        comment = _create_product_comment(
            client, bob_token, pid,
            name="Lifecycle comment",
            description="Great product!",
        )
        self.__class__._state["comment_id"] = comment["id"]

    def test_04_populate_comments(self, client, alice_token):
        pid = self.__class__._state["product_id"]
        resp = client.get(f"/Product/{pid}?populate=comments",
                          headers=auth_header(alice_token))
        assert resp.status_code == 200
        comments = resp.json().get("comments", [])
        assert isinstance(comments, list)
        assert len(comments) >= 1

    def test_05_like_comment(self, client, alice_token):
        cid = self.__class__._state["comment_id"]
        resp = client.post(f"/Comment/{cid}/like",
                           json={}, headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("action") in ("liked", "unliked")

    def test_06_reply_to_comment(self, client, alice_token):
        cid = self.__class__._state["comment_id"]
        resp = client.post(f"/Comment/{cid}/reply",
                           json={"text": "Thanks for the feedback!"},
                           headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("parent_id") == cid

    def test_07_favorite_product(self, client, bob_token):
        pid = self.__class__._state["product_id"]
        resp = client.post(f"/Product/{pid}/favorite",
                           json={}, headers=auth_header(bob_token))
        assert resp.status_code == 200

    def test_08_product_has_favorites(self, client, alice_token):
        pid = self.__class__._state["product_id"]
        resp = client.get(f"/Product/{pid}", headers=auth_header(alice_token))
        assert resp.status_code == 200
        assert len(resp.json().get("favorites", [])) >= 1

    def test_09_admin_deletes_product(self, client, admin_token):
        pid = self.__class__._state["product_id"]
        resp = client.delete(f"/Product/{pid}", headers=auth_header(admin_token))
        assert resp.status_code == 200

    def test_10_deleted_product_returns_404(self, client, alice_token):
        pid = self.__class__._state["product_id"]
        resp = client.get(f"/Product/{pid}", headers=auth_header(alice_token))
        assert resp.status_code == 404


class TestUserCentricWorkflow:
    """Multi-user interaction flow."""

    def test_two_users_interact(self, client, alice_token, bob_token, seed_data):
        p_resp = client.post("/Product", json={
            "name": "Alice's Widget",
            "price": 25.00,
        }, headers=auth_header(alice_token))
        product_id = p_resp.json()["id"]

        comment_data = _create_product_comment(
            client, bob_token, product_id,
            name="Bob's take",
            description="Interesting!",
        )
        comment_id = comment_data["id"]

        r_resp = client.post(f"/Comment/{comment_id}/reply",
                             json={"text": "Thanks Bob!"},
                             headers=auth_header(alice_token))
        assert r_resp.status_code == 200
        reply_data = r_resp.json()
        reply_id = reply_data["id"]
        assert reply_data["parent_id"] == comment_id

        like_resp = client.post(f"/Comment/{reply_id}/like",
                                json={}, headers=auth_header(bob_token))
        assert like_resp.status_code == 200

        like2_resp = client.post(f"/Comment/{comment_id}/like",
                                 json={}, headers=auth_header(alice_token))
        assert like2_resp.status_code == 200

        final = client.get(f"/Product/{product_id}?populate=comments&depth=2",
                           headers=auth_header(alice_token))
        assert final.status_code == 200


class TestAuthorizationAcrossModels:
    """Verify authorization flows correctly across models."""

    def test_owner_permissions_flow(self, client, alice_token, bob_token, admin_token, seed_data):
        product = seed_data["products"][2]
        comment = _create_product_comment(
            client, alice_token, product.id,
            name="Alice's comment",
            description="Owned by alice",
        )
        comment_id = comment["id"]

        update_resp = client.put(f"/Comment/{comment_id}", json={
            "name": "Alice updated",
        }, headers=auth_header(alice_token))
        assert update_resp.status_code == 200

        bob_update = client.put(f"/Comment/{comment_id}", json={
            "name": "Bob tries",
        }, headers=auth_header(bob_token))
        assert bob_update.status_code == 403

        admin_update = client.put(f"/Comment/{comment_id}", json={
            "name": "Admin override",
        }, headers=auth_header(admin_token))
        assert admin_update.status_code == 200

        read_resp = client.get(f"/Comment/{comment_id}")
        assert read_resp.status_code == 200

        bob_delete = client.delete(f"/Comment/{comment_id}", headers=auth_header(bob_token))
        assert bob_delete.status_code == 403

        alice_delete = client.delete(f"/Comment/{comment_id}", headers=auth_header(alice_token))
        assert alice_delete.status_code == 200


class TestFlatRelationshipBehavior:
    """Verify flat collections and parent list[T] relationships."""

    def test_comments_collection_returns_all(self, client, alice_token, seed_data):
        resp = client.get("/Comment/_?limit=100", headers=auth_header(alice_token))
        items = resp.json().get("data", [])
        assert len(items) >= 8

    def test_filtered_comments_per_product(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        items = resp.json().get("comments", [])
        assert len(items) >= 2

    def test_product_comment_membership_uses_hydrated_comments(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}")
        items = resp.json().get("comments", [])
        if items:
            first = items[0]
            assert first["$id"].endswith(f"/Comment/{first['id']}")


class TestCascadeDelete:
    """IT-7: Verify behavior when parent entities are deleted."""

    def test_delete_comment_with_likes(self, client, alice_token, admin_token, seed_data):
        product = seed_data["products"][4]
        comment = _create_product_comment(
            client, alice_token, product.id,
            name="Cascade like test",
            description="Will be deleted",
        )
        comment_id = comment["id"]

        l_resp = client.post(f"/Comment/{comment_id}/like",
                             json={}, headers=auth_header(alice_token))
        assert l_resp.status_code == 200

        d_resp = client.delete(f"/Comment/{comment_id}", headers=auth_header(alice_token))
        assert d_resp.status_code == 200

        get_resp = client.get(f"/Comment/{comment_id}")
        assert get_resp.status_code == 404

    def test_delete_comment_with_replies(self, client, alice_token, bob_token, seed_data):
        product = seed_data["products"][3]
        parent = _create_product_comment(
            client, alice_token, product.id,
            name="Parent for cascade",
            description="Has child replies",
        )
        parent_id = parent["id"]

        reply_resp = client.post(f"/Comment/{parent_id}/reply",
                                 json={"text": "Child reply"},
                                 headers=auth_header(bob_token))
        assert reply_resp.status_code == 200

        d_resp = client.delete(f"/Comment/{parent_id}", headers=auth_header(alice_token))
        assert d_resp.status_code == 200

        get_resp = client.get(f"/Comment/{parent_id}")
        assert get_resp.status_code == 404


class TestDataConsistency:
    """Verify FK values, counts, and referential integrity."""

    def test_created_comment_appears_in_product_comments(self, client, alice_token, seed_data):
        product = seed_data["products"][3]
        comment = _create_product_comment(
            client, alice_token, product.id,
            name="Consistency check",
            description="Should appear in product refs",
        )
        comment_id = comment["id"]

        get_resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        comments = get_resp.json().get("comments", [])
        comment_found = any(comment.get("id") == comment_id for comment in comments)
        assert comment_found, f"Comment {comment_id} not found in product's comments: {comments}"
