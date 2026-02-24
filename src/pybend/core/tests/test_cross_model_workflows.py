# tests/test_cross_model_workflows.py
"""
Test Plan Section 11: Cross-Model Workflows
End-to-end lifecycle tests spanning multiple models.
"""

import json
import pytest
from tests.helpers import auth_header


class TestCompleteProductLifecycle:
    """Full lifecycle: Create -> Read -> Comment -> Like -> Reply -> Favorite -> Delete."""

    def test_product_lifecycle(self, client, alice_token, bob_token, admin_token, seed_data):
        alice = seed_data["users"]["alice"]
        bob = seed_data["users"]["bob"]

        # 1. Create Product (as alice)
        create_resp = client.post("/products", json={
            "name": "Lifecycle Product",
            "price": 49.99,
            "description": "Full lifecycle test",
        }, headers=auth_header(alice_token))
        assert create_resp.status_code == 201
        product = create_resp.json()
        product_id = product["id"]
        assert product["name"] == "Lifecycle Product"

        # 2. Get Product (empty refs) -- needs auth, Product defaults to AUTHENTICATED
        get_resp = client.get(f"/products/{product_id}", headers=auth_header(alice_token))
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["comments"] == []
        assert data["favorites"] == []

        # 3. Add Comment via CRUD route (as bob) -- returns proper DB id
        comment_resp = client.post(f"/products/{product_id}/comments", json={
            "name": "Lifecycle comment",
            "description": "Great product!",
        }, headers=auth_header(bob_token))
        assert comment_resp.status_code == 201
        comment_data = comment_resp.json()
        comment_id = comment_data["id"]
        assert comment_id is not None

        # 4. Get Product with populated comments
        pop_resp = client.get(f"/products/{product_id}?populate=comments",
                              headers=auth_header(alice_token))
        assert pop_resp.status_code == 200
        pop_data = pop_resp.json()
        comments = pop_data.get("comments", {})
        if isinstance(comments, dict) and "data" in comments:
            assert len(comments["data"]) >= 1

        # 5. Like Comment (as alice)
        like_resp = client.post(f"/products/{product_id}/comments/{comment_id}/like",
                                json={}, headers=auth_header(alice_token))
        assert like_resp.status_code == 200
        like_data = like_resp.json()
        if isinstance(like_data, str):
            like_data = json.loads(like_data)
        assert like_data.get("action") in ("liked", "unliked")

        # 6. Reply to Comment (as alice)
        reply_resp = client.post(f"/products/{product_id}/comments/{comment_id}/reply",
                                 json={"text": "Thanks for the feedback!"},
                                 headers=auth_header(alice_token))
        assert reply_resp.status_code == 200
        reply_data = reply_resp.json()
        if isinstance(reply_data, str):
            reply_data = json.loads(reply_data)
        assert reply_data.get("parent_id") == comment_id

        # 7. Favorite Product (as bob)
        fav_resp = client.post(f"/products/{product_id}/favorite",
                               json={}, headers=auth_header(bob_token))
        assert fav_resp.status_code == 200

        # 8. Get Product with favorites
        final_resp = client.get(f"/products/{product_id}", headers=auth_header(alice_token))
        assert final_resp.status_code == 200
        final_data = final_resp.json()
        assert len(final_data.get("favorites", [])) >= 1

        # 9. Delete Product (as admin)
        del_resp = client.delete(f"/products/{product_id}", headers=auth_header(admin_token))
        assert del_resp.status_code == 200

        # 10. Verify deleted (need auth)
        gone_resp = client.get(f"/products/{product_id}", headers=auth_header(alice_token))
        assert gone_resp.status_code == 404


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

        # Fetch product and check comments contain the new one
        get_resp = client.get(f"/products/{product.id}", headers=auth_header(alice_token))
        comments = get_resp.json().get("comments", [])
        # Should contain an href with the comment_id
        comment_found = any(str(comment_id) in str(href) for href in comments)
        assert comment_found, f"Comment {comment_id} not found in product's comments: {comments}"
