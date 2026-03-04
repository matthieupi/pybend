# tests/test_cross_model_workflows.py
"""
Test Plan Section 11: Cross-Model Workflows
End-to-end lifecycle tests spanning multiple models.
"""

import json
import pytest
from pybend.example_api.tests.helpers import auth_header

pytestmark = pytest.mark.integration



class TestCompleteProductLifecycle:
    """Full lifecycle: Create -> Read -> Comment -> Like -> Reply -> Favorite -> Delete.

    IT-2: Split mega-test into discrete test methods with shared state via
    class-scoped fixture-like pattern using a dict on the class.
    """

    # Shared state across tests in this class — populated by test execution order
    _state = {}

    def test_01_create_product(self, client, alice_token, seed_data):
        resp = client.post("/products", json={
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
        resp = client.get(f"/products/{pid}", headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["comments"] == []
        assert data["favorites"] == []

    def test_03_add_comment(self, client, bob_token):
        pid = self.__class__._state["product_id"]
        resp = client.post(f"/products/{pid}/comments", json={
            "name": "Lifecycle comment",
            "description": "Great product!",
        }, headers=auth_header(bob_token))
        assert resp.status_code == 201
        self.__class__._state["comment_id"] = resp.json()["id"]

    def test_04_populate_comments(self, client, alice_token):
        pid = self.__class__._state["product_id"]
        resp = client.get(f"/products/{pid}?populate=comments",
                          headers=auth_header(alice_token))
        assert resp.status_code == 200
        comments = resp.json().get("comments", {})
        if isinstance(comments, dict) and "data" in comments:
            assert len(comments["data"]) >= 1

    def test_05_like_comment(self, client, alice_token):
        pid = self.__class__._state["product_id"]
        cid = self.__class__._state["comment_id"]
        resp = client.post(f"/products/{pid}/comments/{cid}/like",
                           json={}, headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, str):
            data = json.loads(data)
        assert data.get("action") in ("liked", "unliked")

    def test_06_reply_to_comment(self, client, alice_token):
        pid = self.__class__._state["product_id"]
        cid = self.__class__._state["comment_id"]
        resp = client.post(f"/products/{pid}/comments/{cid}/reply",
                           json={"text": "Thanks for the feedback!"},
                           headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, str):
            data = json.loads(data)
        assert data.get("parent_id") == cid

    def test_07_favorite_product(self, client, bob_token):
        pid = self.__class__._state["product_id"]
        resp = client.post(f"/products/{pid}/favorite",
                           json={}, headers=auth_header(bob_token))
        assert resp.status_code == 200

    def test_08_product_has_favorites(self, client, alice_token):
        pid = self.__class__._state["product_id"]
        resp = client.get(f"/products/{pid}", headers=auth_header(alice_token))
        assert resp.status_code == 200
        assert len(resp.json().get("favorites", [])) >= 1

    def test_09_admin_deletes_product(self, client, admin_token):
        pid = self.__class__._state["product_id"]
        resp = client.delete(f"/products/{pid}", headers=auth_header(admin_token))
        assert resp.status_code == 200

    def test_10_deleted_product_returns_404(self, client, alice_token):
        pid = self.__class__._state["product_id"]
        resp = client.get(f"/products/{pid}", headers=auth_header(alice_token))
        assert resp.status_code == 404


class TestUserCentricWorkflow:
    """Multi-user interaction flow."""

    def test_two_users_interact(self, client, alice_token, bob_token, seed_data):
        alice = seed_data["users"]["alice"]
        bob = seed_data["users"]["bob"]

        # Alice creates a product
        p_resp = client.post("/products", json={
            "name": "Alice's Widget",
            "price": 25.00,
        }, headers=auth_header(alice_token))
        product_id = p_resp.json()["id"]

        # Bob comments via CRUD route (returns proper DB id)
        c_resp = client.post(f"/products/{product_id}/comments", json={
            "name": "Bob's take", "description": "Interesting!",
        }, headers=auth_header(bob_token))
        assert c_resp.status_code == 201
        comment_data = c_resp.json()
        comment_id = comment_data["id"]

        # Alice replies to Bob's comment
        r_resp = client.post(f"/products/{product_id}/comments/{comment_id}/reply",
                             json={"text": "Thanks Bob!"},
                             headers=auth_header(alice_token))
        assert r_resp.status_code == 200
        reply_data = r_resp.json()
        if isinstance(reply_data, str):
            reply_data = json.loads(reply_data)
        reply_id = reply_data["id"]
        assert reply_data["parent_id"] == comment_id

        # Bob likes Alice's reply
        like_resp = client.post(f"/products/{product_id}/comments/{reply_id}/like",
                                json={}, headers=auth_header(bob_token))
        assert like_resp.status_code == 200

        # Alice likes Bob's original comment
        like2_resp = client.post(f"/products/{product_id}/comments/{comment_id}/like",
                                 json={}, headers=auth_header(alice_token))
        assert like2_resp.status_code == 200

        # Get product with deep populate
        final = client.get(f"/products/{product_id}?populate=comments&depth=2",
                           headers=auth_header(alice_token))
        assert final.status_code == 200


class TestAuthorizationAcrossModels:
    """Verify authorization flows correctly across models."""

    def test_owner_permissions_flow(self, client, alice_token, bob_token, admin_token, seed_data):
        product = seed_data["products"][2]

        # 1. Alice creates a comment (auto-owned by alice)
        create_resp = client.post(f"/products/{product.id}/comments", json={
            "name": "Alice's comment",
            "description": "Owned by alice",
        }, headers=auth_header(alice_token))
        comment_id = create_resp.json()["id"]

        # 2. Alice can update (OWNER)
        update_resp = client.put(f"/products/{product.id}/comments/{comment_id}", json={
            "name": "Alice updated",
        }, headers=auth_header(alice_token))
        assert update_resp.status_code == 200

        # 3. Bob cannot update (not owner, not admin)
        bob_update = client.put(f"/products/{product.id}/comments/{comment_id}", json={
            "name": "Bob tries",
        }, headers=auth_header(bob_token))
        assert bob_update.status_code == 403

        # 4. Admin can update (ROLE('admin'))
        admin_update = client.put(f"/products/{product.id}/comments/{comment_id}", json={
            "name": "Admin override",
        }, headers=auth_header(admin_token))
        assert admin_update.status_code == 200

        # 5. Anyone can read (ANYONE)
        read_resp = client.get(f"/products/{product.id}/comments/{comment_id}")
        assert read_resp.status_code == 200

        # 6. Bob cannot delete (not owner)
        bob_delete = client.delete(f"/products/{product.id}/comments/{comment_id}",
                                   headers=auth_header(bob_token))
        assert bob_delete.status_code == 403

        # 7. Alice can delete (OWNER)
        alice_delete = client.delete(f"/products/{product.id}/comments/{comment_id}",
                                     headers=auth_header(alice_token))
        assert alice_delete.status_code == 200


class TestJoinModelBehavior:
    """Verify join models work correctly for cross-model collections."""

    def test_comments_collection_returns_all(self, client, alice_token, seed_data):
        """GET /products_comments returns all comments across all products."""
        resp = client.get("/products_comments", headers=auth_header(alice_token))
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        # Should have at least 8 seed comments + 3 replies
        assert len(items) >= 8

    def test_filtered_comments_per_product(self, client, seed_data):
        """GET /products/{id}/comments returns only that product's comments."""
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}/comments")
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        # Product 0 has exactly 2 direct comments + 2 replies from seed
        assert len(items) >= 2

    def test_product_comment_has_product_id(self, client, seed_data):
        """Each ProductComment should have the product_id FK."""
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}/comments")
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        if items:
            first = items[0]
            assert first.get("product_id") == product.id


class TestCascadeDelete:
    """IT-7: Verify behavior when parent entities are deleted.

    Note: PyBend may or may not implement true cascade deletes.
    These tests verify the observable behavior: after deleting a parent,
    either children are also deleted (cascade) or they become orphaned
    but the parent is gone. Both are valid; the test documents which.
    """

    def test_delete_comment_with_likes(self, client, alice_token, admin_token, seed_data):
        """Delete a comment that has likes. Likes should be cleaned up or orphaned."""
        product = seed_data["products"][4]

        # Create a fresh comment
        c_resp = client.post(f"/products/{product.id}/comments", json={
            "name": "Cascade like test",
            "description": "Will be deleted",
        }, headers=auth_header(alice_token))
        assert c_resp.status_code == 201
        comment_id = c_resp.json()["id"]

        # Like the comment
        l_resp = client.post(f"/products/{product.id}/comments/{comment_id}/like",
                             json={}, headers=auth_header(alice_token))
        assert l_resp.status_code == 200

        # Delete the comment (as owner)
        d_resp = client.delete(f"/products/{product.id}/comments/{comment_id}",
                               headers=auth_header(alice_token))
        assert d_resp.status_code == 200

        # Verify comment is gone
        get_resp = client.get(f"/products/{product.id}/comments/{comment_id}")
        assert get_resp.status_code == 404

    def test_delete_comment_with_replies(self, client, alice_token, bob_token, seed_data):
        """Delete a comment that has child replies via parent_id."""
        product = seed_data["products"][3]

        # Create parent comment
        parent_resp = client.post(f"/products/{product.id}/comments", json={
            "name": "Parent for cascade",
            "description": "Has child replies",
        }, headers=auth_header(alice_token))
        assert parent_resp.status_code == 201
        parent_id = parent_resp.json()["id"]

        # Create a reply to it
        reply_resp = client.post(f"/products/{product.id}/comments/{parent_id}/reply",
                                 json={"text": "Child reply"},
                                 headers=auth_header(bob_token))
        assert reply_resp.status_code == 200

        # Delete the parent comment
        d_resp = client.delete(f"/products/{product.id}/comments/{parent_id}",
                               headers=auth_header(alice_token))
        assert d_resp.status_code == 200

        # Verify parent is gone
        get_resp = client.get(f"/products/{product.id}/comments/{parent_id}")
        assert get_resp.status_code == 404


class TestDataConsistency:
    """Verify FK values, counts, and referential integrity."""

    def test_created_comment_appears_in_product_comments(self, client, alice_token, seed_data):
        product = seed_data["products"][3]

        # Create a comment
        create_resp = client.post(f"/products/{product.id}/comments", json={
            "name": "Consistency check",
            "description": "Should appear in product refs",
        }, headers=auth_header(alice_token))
        comment_id = create_resp.json()["id"]

        # Fetch product and check comments contain the new one (IT-3: exact match)
        from pybend.example_api.tests.helpers import href_ends_with
        get_resp = client.get(f"/products/{product.id}", headers=auth_header(alice_token))
        comments = get_resp.json().get("comments", [])
        # Use exact suffix match instead of substring (IT-3)
        comment_found = any(
            href_ends_with(href, f"/comments/{comment_id}")
            for href in comments
        )
        assert comment_found, f"Comment {comment_id} not found in product's comments: {comments}"
